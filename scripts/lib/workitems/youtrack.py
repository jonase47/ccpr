"""youtrack.py – The `youtrack` work-item backend: a self-hosted YouTrack REST + Command API
(ADR-0003). No MCP, no third-party HTTP library — stdlib `urllib.request` only.

Design points carried over from the ADR (see ADR-0003 for the full rationale):

- Fields and states are resolved BY NAME at runtime, never by hardcoded numeric field/
  bundle ids — that is what keeps this backend generic across YouTrack instances.
  Reads ask for `customFields(name,value(name,login))` and locate values by their
  `name` (or `login`, for the Assignee user field); writes use the name-based Command
  API (`State <name>`, `for <user>`) rather than raw custom-field writes.
- The token comes only from the environment variable named by `tokenEnv` — never from
  settings.json (ADR-0002 §3).
- `claim`/`set-status` prefer the Command API (POST /api/commands) over direct field
  writes, per the ADR's explicit preference.

Two spec gaps in ADR-0003 that this implementation had to resolve on its own judgment
(reported to the user, not silently assumed away — see the senior-developer's final
report for this increment):

1. **Project reference for issue creation.** The ADR doesn't specify how `project`
   (the short name in settings.json, e.g. "PROJ") becomes the `project.id` YouTrack's
   `POST /api/issues` expects. This resolves it the same way as fields/states: by name,
   at runtime, via `GET /api/admin/projects` — never a numeric id in config.
2. **Disambiguating `append-result` comments from ordinary human comments.** The ADR
   says `append-result` "add[s] a comment with the PR/commit link" but doesn't specify
   how `get`/`list` later recognise which comments are result references versus regular
   issue discussion. This implementation prefixes result comments with `Result: ` and
   only surfaces comments carrying that prefix as `result-link` entries.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from workitems import STATUS_VALUES, WorkItemError, validate_item_id

_ISSUE_FIELDS = "idReadable,summary,description,customFields(name,value(name,login)),comments(text)"
RESULT_COMMENT_PREFIX = "Result: "


def create(config):
    """Factory used by the CLI dispatcher (scripts/workitems.py)."""
    base_url = config.get("baseUrl")
    project = config.get("project")
    token_env = config.get("tokenEnv")
    missing = [
        name for name, value in
        (("baseUrl", base_url), ("project", project), ("tokenEnv", token_env))
        if not value
    ]
    if missing:
        raise WorkItemError(
            "youtrack backend config is missing required key(s) in settings.json's "
            f"workitems.youtrack: {', '.join(missing)}"
        )

    token = os.environ.get(token_env)
    if not token:
        raise WorkItemError(
            f"environment variable {token_env!r} is not set — the YouTrack token must "
            "come from the environment, never from settings.json"
        )

    return YouTrackBackend(base_url, project, token, state_map=config.get("stateMap"))


class YouTrackBackend:
    def __init__(self, base_url, project, token, state_map=None, transport=None):
        self.base_url = base_url.rstrip("/")
        self.project = project
        self.token = token
        self.state_map = state_map or {}
        self._reverse_state_map = {v: k for k, v in self.state_map.items()}
        self.transport = transport or _HttpTransport()
        self._project_id = None

    def create(self, title, item_type=None, owner=None, description=None):
        if not title:
            raise WorkItemError("title is required")

        project_id = self._resolve_project_id()
        body = {"project": {"id": project_id}, "summary": title, "description": description or ""}
        created = self._request("POST", "/api/issues", body=body, fields="idReadable")
        item_id = created["idReadable"]

        # A fresh issue starts in the project's own default state, which is not
        # necessarily one named "Backlog" — drive it explicitly, same as set_status().
        self.set_status(item_id, "Backlog")
        if item_type:
            self._run_command(item_id, f"Type {item_type}")
        if owner:
            self._run_command(item_id, f"for {owner}")

        return self.get(item_id)

    def list(self, status=None, owner=None):
        issues = self._request(
            "GET", "/api/issues", fields=_ISSUE_FIELDS, query=f"project: {self.project}",
        )
        items = [self._item_from_issue(issue) for issue in issues]
        if status is not None:
            items = [item for item in items if item["status"] == status]
        if owner is not None:
            items = [item for item in items if item["owner"] == owner]
        return items

    def get(self, item_id):
        validate_item_id(item_id)
        issue = self._request("GET", f"/api/issues/{item_id}", fields=_ISSUE_FIELDS)
        return self._item_from_issue(issue)

    def claim(self, item_id, owner=None):
        """No-op beyond optionally setting Assignee (the mandatory-claiming lock
        protocol for remote backends is ADR-0005, not part of this increment)."""
        validate_item_id(item_id)
        if owner:
            self._run_command(item_id, f"for {owner}")
        return self.get(item_id)

    def set_status(self, item_id, status):
        validate_item_id(item_id)
        if status not in STATUS_VALUES:
            raise WorkItemError(
                f"Unknown status '{status}'. Valid values: {', '.join(STATUS_VALUES)}"
            )
        mapped = self._map_state(status)
        self._run_command(item_id, f"State {mapped}")
        return self.get(item_id)

    def append_result(self, item_id, ref):
        validate_item_id(item_id)
        self._request(
            "POST", f"/api/issues/{item_id}/comments",
            body={"text": f"{RESULT_COMMENT_PREFIX}{ref}"},
        )
        return self.get(item_id)

    def _resolve_project_id(self):
        if self._project_id is not None:
            return self._project_id
        projects = self._request("GET", "/api/admin/projects", fields="id,shortName")
        for project in projects:
            if project.get("shortName") == self.project:
                self._project_id = project["id"]
                return self._project_id
        raise WorkItemError(f"YouTrack project not found: {self.project!r}")

    def _run_command(self, item_id, query):
        self._request(
            "POST", "/api/commands",
            body={"query": query, "issues": [{"idReadable": item_id}]},
        )

    def _request(self, method, path, body=None, fields=None, query=None):
        url = f"{self.base_url}{path}"
        params = {}
        if fields:
            params["fields"] = fields
        if query:
            params["query"] = query
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return self.transport.request(method, url, self.token, body=body)

    def _map_state(self, ccpr_status):
        """CCPR vocabulary name -> the project's own State bundle name."""
        return self.state_map.get(ccpr_status, ccpr_status)

    def _unmap_state(self, project_state_name):
        """The project's own State bundle name -> CCPR vocabulary name."""
        if project_state_name is None:
            return None
        return self._reverse_state_map.get(project_state_name, project_state_name)

    def _item_from_issue(self, issue):
        custom_fields = {f["name"]: f.get("value") for f in issue.get("customFields", [])}

        state_value = custom_fields.get("State")
        status = state_value.get("name") if isinstance(state_value, dict) else None
        status = self._unmap_state(status)

        assignee_value = custom_fields.get("Assignee")
        owner = None
        if isinstance(assignee_value, dict):
            owner = assignee_value.get("login") or assignee_value.get("name")

        result_links = [
            comment["text"][len(RESULT_COMMENT_PREFIX):]
            for comment in issue.get("comments", [])
            if comment.get("text", "").startswith(RESULT_COMMENT_PREFIX)
        ]

        return {
            "id": issue.get("idReadable"),
            "title": issue.get("summary"),
            "status": status,
            "description": issue.get("description") or "",
            "result-link": result_links,
            "owner": owner,
        }


class _HttpTransport:
    """Real transport: stdlib urllib.request only, no third-party HTTP library."""

    def request(self, method, url, token, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            exc.close()
            raise WorkItemError(
                f"YouTrack API error {exc.code} for {method} {url}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise WorkItemError(f"YouTrack request failed for {method} {url}: {exc}") from exc

        if not raw:
            return None
        return json.loads(raw)
