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
   issue discussion. This implementation prefixes result comments with a machine
   marker (`<!-- ccpr:result -->`, not English prose — a human commenting "Result:
   I don't think this fixed it..." must not be mistaken for a real result reference)
   and only surfaces comments carrying that marker as `result-link` entries.
"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from workitems import (
    DEFAULT_STALE_AFTER_SECONDS, RESULT_MARKER, STATUS_VALUES, WorkItemError,
    is_reserved_tag, reject_result_marker, safe_parse_datetime, validate_item_id,
    validate_tag,
)

_ISSUE_FIELDS = (
    "idReadable,summary,description,customFields(name,value(name,login)),"
    "comments(text),tags(name)"
)

# Claiming / branch-runner protocol (ADR-0005). ADR-0003 doesn't specify a concrete
# mechanism for the runner+heartbeat signals ("a concrete heartbeat implementation
# exists as a private tracker-side workflow ... not part of this generic protocol"),
# so this is this implementation's own resolution of that gap, on the same footing
# as the project-resolution and result-comment gaps already documented above:
# runner + heartbeat are modeled as ISSUE TAGS, not custom fields. Rationale:
# - Tags are a single, unambiguous shape (a plain name string) already used
#   elsewhere in the ADR-0003 Command API example ("...tag chore"); a custom field's
#   REST shape for a non-bundle, non-user field type is not something this
#   implementation could verify without a real instance.
# - A runner tag: "runner:<id>". A heartbeat tag: "heartbeat:<compact-utc-timestamp>"
#   (colon-free timestamp body, e.g. "20260708T160000Z" — safe inside a tag name).
# - Refreshing means removing the old runner:/heartbeat: tags and adding new ones
#   (tags don't have an in-place "value" to update) via two Command API calls
#   (`remove tag <old>`, `tag <new>`) per changed tag.
_RUNNER_TAG_PREFIX = "runner:"
_HEARTBEAT_TAG_PREFIX = "heartbeat:"
_HEARTBEAT_TAG_FORMAT = "%Y%m%dT%H%M%SZ"


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

    return YouTrackBackend(
        base_url, project, token, state_map=config.get("stateMap"),
        stale_after_seconds=config.get("stale_after_seconds"),
    )


class YouTrackBackend:
    def __init__(self, base_url, project, token, state_map=None, transport=None,
                 clock=None, stale_after_seconds=None):
        self.base_url = base_url.rstrip("/")
        self.project = project
        self.token = token
        self.state_map = state_map or {}
        self._reverse_state_map = {v: k for k, v in self.state_map.items()}
        self.transport = transport or _HttpTransport()
        self._project_id = None
        # Claiming (ADR-0005): clock is injected (zero-arg callable -> datetime),
        # never a bare datetime.now() buried in claim()/heartbeat() logic, so tests
        # get a deterministic heartbeat timestamp.
        self.clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        self.stale_after_seconds = (
            stale_after_seconds if stale_after_seconds is not None
            else DEFAULT_STALE_AFTER_SECONDS
        )

    def create(self, title, item_type=None, owner=None, description=None):
        if not title:
            raise WorkItemError("title is required")

        project_id = self._resolve_project_id()
        body = {"project": {"id": project_id}, "summary": title, "description": description or ""}
        created = self._request("POST", "/api/issues", body=body, fields="idReadable")
        item_id = created["idReadable"]

        # POST /api/issues above is the actual commit -- the issue exists from this
        # point on, so anything below that raises WITHOUT rolling the issue back
        # would orphan it while create() reports failure (a retry then duplicates
        # it). The initial State command is the one exception to the best-effort
        # treatment below: status is a core, mandatory contract field (ADR-0002
        # §2), not an optional extension, so a rejection here (e.g. "Backlog"
        # missing from stateMap/the project's own State bundle) is a real
        # configuration problem worth surfacing loudly -- but it must not leave an
        # orphan either. This makes create() atomic: either a fully-created item,
        # or nothing.
        #
        # A fresh issue starts in the project's own default state, which is not
        # necessarily one named "Backlog" — drive it explicitly, same as set_status().
        try:
            self.set_status(item_id, "Backlog")
        except WorkItemError as exc:
            self._rollback_failed_create(item_id, "Backlog", exc)

        # `type` and `owner` at create time ARE optional/backend-specific (ADR-0002:
        # the core contract never relies on `type`; `owner` is "optional while
        # unclaimed"). Verified against a real instance: CCPR's own type vocabulary
        # (feat/fix/refactor/docs/chore) generally doesn't match a project's actual
        # Type bundle (e.g. Bug/Feature/Task) verbatim, so this 400s routinely, not
        # as an edge case. A rejected command here must warn and continue, not fail
        # the create that already committed. One Command API call per field, never
        # combined into a single query, so each field's success/failure stays
        # independently attributable.
        if item_type:
            self._apply_optional_create_field(item_id, f"Type {item_type}", "type", item_type)
        if owner:
            self._apply_optional_create_field(item_id, f"for {owner}", "owner", owner)

        return self.get(item_id)

    def _apply_optional_create_field(self, item_id, query, field_name, value):
        """Runs a create-time field command that must never fail create() itself --
        see the comment in create() for why `type`/`owner` are treated this way
        while the initial State command is not."""
        try:
            self._run_command(item_id, query)
        except WorkItemError as exc:
            print(
                f"Warning: could not set {field_name} {value!r} on new issue "
                f"{item_id} (rejected by YouTrack): {exc}. Continuing without it.",
                file=sys.stderr,
            )

    def _rollback_failed_create(self, item_id, attempted_state, original_exc):
        """The initial State command is the one create()-time field that is NOT
        best-effort (see create()): a rejection means the issue was created but
        never reached a valid CCPR status, so it must not survive as an orphan.
        Deletes the just-created issue, then raises -- surfacing the delete
        failure too if THAT also fails, rather than swallowing it, so a genuinely
        stuck issue stays visible instead of silently lost."""
        try:
            self._delete_issue(item_id)
        except WorkItemError as delete_exc:
            raise WorkItemError(
                f"create rolled back: could not set initial state {attempted_state!r} "
                f"on {item_id} ({original_exc}) -- and the rollback delete also failed "
                f"({delete_exc}); issue {item_id} may be orphaned in YouTrack, check "
                "manually."
            ) from original_exc
        raise WorkItemError(
            f"create rolled back: could not set initial state {attempted_state!r} "
            f"on {item_id} ({original_exc})"
        ) from original_exc

    def _delete_issue(self, item_id):
        """Backend-internal recovery only -- NOT part of the six-op contract (the
        contract stays workflow-only: Cancelled, not delete). Used exclusively to
        undo a create() whose mandatory initial state could not be set."""
        self._request("DELETE", f"/api/issues/{item_id}")

    def list(self, status=None, owner=None):
        # $top=-1 disables pagination explicitly — without it, some YouTrack versions
        # cap /api/issues to a default page size, silently truncating a large project.
        issues = self._request(
            "GET", "/api/issues", fields=_ISSUE_FIELDS, query=f"project: {self.project}", top=-1,
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

    def claim(self, item_id, owner=None, runner=None):
        """Claiming is MANDATORY for remote backends (ADR-0002 §6, ADR-0005): when a
        `runner` is given, records the runner:<id> signal + a heartbeat timestamp and
        sets status to In Progress. `owner` (Assignee) is independent of `runner` —
        the responsible human vs. the process executing the item right now.

        ALL guards are evaluated before ANY mutation: a refused claim (terminal
        state, or a live takeover by a different runner) must leave the item exactly
        as it was, including `owner` -- reassigning owner and then raising would be a
        side effect from an operation that's supposed to have failed outright.
        """
        validate_item_id(item_id)

        if runner:
            current = self.get(item_id)
            # Terminal states are not resumable -- claiming one would silently
            # resurrect finished/abandoned work back to In Progress. Reopening is an
            # explicit, deliberate action (set-status), not a side effect of claim().
            if current.get("status") in ("Done", "Cancelled"):
                raise WorkItemError(
                    f"{item_id} is {current['status']}; reopen it explicitly "
                    "(set-status) before claiming."
                )
            current_runner = current.get("runner")
            # The live-takeover check only applies while the item is In Progress --
            # once it's Parked (whether by sweep() or manually), ADR-0005 says ANY
            # runner may resume it unconditionally ("no live runner, resumable"); a
            # stale-but-not-yet-swept heartbeat left over from the abandoned claim
            # must not block that resume.
            if (
                current.get("status") == "In Progress"
                and current_runner
                and current_runner != runner
                and self._is_heartbeat_live(current.get("heartbeat"))
            ):
                raise WorkItemError(
                    f"{item_id} is already claimed by runner {current_runner!r} "
                    "with a live heartbeat; refusing to steal the claim. Wait for it "
                    "to go stale, or have that runner release it first."
                )

        # Every guard above passed (or there was nothing to guard, i.e. no runner
        # given) -- only now is it safe to mutate.
        if owner:
            self._run_command(item_id, f"for {owner}")
        if runner:
            self._refresh_runner_and_heartbeat(item_id, runner)
            self.set_status(item_id, "In Progress")

        return self.get(item_id)

    def heartbeat(self, item_id, runner):
        """Refresh the liveness signal for `runner` on `item_id`. Refuses if the item
        is currently claimed by a DIFFERENT runner (a dead runner's own heartbeat
        call reviving its stale claim would defeat the whole point of staleness)."""
        validate_item_id(item_id)
        current = self.get(item_id)
        current_runner = current.get("runner")
        if current_runner and current_runner != runner:
            raise WorkItemError(
                f"{item_id} is claimed by runner {current_runner!r}, not {runner!r}; "
                "cannot heartbeat as a different runner."
            )
        self._refresh_runner_and_heartbeat(item_id, runner)
        return self.get(item_id)

    def _now_utc(self):
        """self.clock(), normalized to UTC at the point of use. Cheap insurance
        against a future clock injection that returns a naive or non-UTC-aware
        datetime: `strftime` (the heartbeat tag write) formats wall-clock fields
        verbatim and silently ignores any offset, and subtracting a naive from an
        aware datetime raises TypeError outright. `.astimezone(utc)` on an ALREADY
        UTC-aware datetime (every test fixture and the real default clock) is a
        no-op; on a naive datetime, Python assumes it represents the system's local
        timezone (astimezone()'s documented behaviour) rather than raising -- still
        better than a crash, though a naive clock meant to already BE UTC should be
        made aware at the injection site instead of relying on this fallback.
        """
        return self.clock().astimezone(datetime.timezone.utc)

    def _is_heartbeat_live(self, heartbeat_iso):
        heartbeat_dt = safe_parse_datetime(heartbeat_iso, datetime.datetime.fromisoformat)
        if heartbeat_dt is None:
            return False  # missing or malformed -- never considered live
        age_seconds = (self._now_utc() - heartbeat_dt).total_seconds()
        return age_seconds < self.stale_after_seconds

    def _refresh_runner_and_heartbeat(self, item_id, runner):
        # Tags have no in-place "value" to update: remove any existing runner:/
        # heartbeat: tags first, then add the fresh pair.
        current_tags = self._request("GET", f"/api/issues/{item_id}", fields="tags(name)")
        for tag in current_tags.get("tags", []):
            name = tag.get("name") if isinstance(tag, dict) else tag
            if name and (name.startswith(_RUNNER_TAG_PREFIX) or name.startswith(_HEARTBEAT_TAG_PREFIX)):
                self._run_command(item_id, f"remove tag {name}")

        heartbeat_str = self._now_utc().strftime(_HEARTBEAT_TAG_FORMAT)
        self._run_command(item_id, f"tag {_RUNNER_TAG_PREFIX}{runner}")
        self._run_command(item_id, f"tag {_HEARTBEAT_TAG_PREFIX}{heartbeat_str}")

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
            body={"text": f"{RESULT_MARKER} {ref}"},
        )
        return self.get(item_id)

    def comment(self, item_id, text):
        """Writes a plain human comment to the SAME comments endpoint append_result
        uses, but WITHOUT the marker -- get()/list() partition by marker presence
        (see _item_from_issue), so this never surfaces as a result-link (ADR-0002
        addendum, 09.07.2026). Rejects text starting with the marker itself: a human
        typing it would otherwise forge a result-link entry (review follow-up,
        09.07.2026) -- see the shared contract test for the uniform rejection across
        backends."""
        validate_item_id(item_id)
        if not text:
            raise WorkItemError("comment text is required")
        reject_result_marker(text)
        self._request(
            "POST", f"/api/issues/{item_id}/comments",
            body={"text": text},
        )
        return self.get(item_id)

    def set_description(self, item_id, text):
        """Direct field write, same endpoint `create` already uses for the initial
        description (ADR-0003 precedent). An empty string is a valid, deliberate
        clear -- not an error."""
        validate_item_id(item_id)
        self._request("POST", f"/api/issues/{item_id}", body={"description": text or ""})
        return self.get(item_id)

    def set_title(self, item_id, text):
        validate_item_id(item_id)
        if not text:
            raise WorkItemError("title is required")
        self._request("POST", f"/api/issues/{item_id}", body={"summary": text})
        return self.get(item_id)

    def set_type(self, item_id, item_type):
        """A DEDICATED call, unlike create()'s best-effort type-setting: there is
        nothing else to protect via atomicity here (the issue already exists and
        nothing else commits alongside this), and a rejection is a real error the
        caller -- who explicitly chose this value -- needs to see, not routine
        friction to paper over. Fails hard on a rejected Command API call, run
        directly (not wrapped in _apply_optional_create_field). ADR-0002 addendum,
        09.07.2026."""
        validate_item_id(item_id)
        if not item_type:
            raise WorkItemError("type is required")
        self._run_command(item_id, f"Type {item_type}")
        return self.get(item_id)

    def add_tag(self, item_id, tag):
        """Checks the current (already reserved-filtered) tag list first so a
        redundant call is skipped rather than relying on the Command API's own
        idempotence (ADR-0002 2nd addendum, 09.07.2026). `validate_tag` already
        refuses a reserved tag before any request is made, so it can never reach
        the membership check below."""
        validate_item_id(item_id)
        validate_tag(tag)
        current = self.get(item_id)
        if tag in current["tags"]:
            return current
        self._run_command(item_id, f"tag {tag}")
        return self.get(item_id)

    def remove_tag(self, item_id, tag):
        validate_item_id(item_id)
        validate_tag(tag)
        current = self.get(item_id)
        if tag not in current["tags"]:
            return current
        self._run_command(item_id, f"remove tag {tag}")
        return self.get(item_id)

    def _resolve_project_id(self):
        if self._project_id is not None:
            return self._project_id
        # GET /api/admin/projects is admin-scoped; a minimally-scoped token (a
        # realistic setup) may lack it. Re-raise with an actionable message rather
        # than letting the raw HTTP error propagate, since a permission failure
        # would otherwise look identical to a misconfigured project short name.
        try:
            projects = self._request("GET", "/api/admin/projects", fields="id,shortName")
        except WorkItemError as exc:
            raise WorkItemError(
                f"Could not resolve YouTrack project {self.project!r} via "
                "GET /api/admin/projects (requires an admin-scoped token): the token "
                f"may lack project-read permission, or the project may not exist. "
                f"Original error: {exc}"
            ) from exc
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

    def _request(self, method, path, body=None, fields=None, query=None, top=None):
        url = f"{self.base_url}{path}"
        params = {}
        if fields:
            params["fields"] = fields
        if query:
            params["query"] = query
        if top is not None:
            params["$top"] = top
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
        if status is not None and status not in STATUS_VALUES:
            # A project's State bundle may legitimately have values outside CCPR's
            # vocabulary (and outside any stateMap) — pass it through rather than
            # raising (set_status already refuses to WRITE such a value; a value
            # already on the issue must still be readable), but make this visible
            # instead of silently returning an item whose status looks ordinary.
            print(
                f"Warning: YouTrack issue {issue.get('idReadable')} has state "
                f"{status!r}, which is outside the CCPR status vocabulary "
                f"({', '.join(STATUS_VALUES)}). Passing it through as-is; consider "
                "adding it to workitems.youtrack.stateMap.",
                file=sys.stderr,
            )

        assignee_value = custom_fields.get("Assignee")
        owner = None
        if isinstance(assignee_value, dict):
            owner = assignee_value.get("login") or assignee_value.get("name")

        type_value = custom_fields.get("Type")
        item_type = type_value.get("name") if isinstance(type_value, dict) else None

        # comment() and append_result() share the SAME comments stream (both POST to
        # /api/issues/<id>/comments); the marker is the only thing that tells them
        # apart on read-back -- a hard either/or partition, never both (ADR-0002
        # addendum, 09.07.2026).
        result_links = []
        comments = []
        for issue_comment in issue.get("comments", []):
            text = issue_comment.get("text", "")
            if text.startswith(RESULT_MARKER):
                result_links.append(text[len(RESULT_MARKER):].strip())
            else:
                comments.append(text)

        runner, heartbeat = self._runner_and_heartbeat_from_tags(
            issue.get("tags", []), issue.get("idReadable"),
        )

        # runner:/heartbeat: tags are claiming-protocol plumbing (ADR-0005), not
        # tags a human or command added -- they must never leak into the
        # user-facing `tags` field (ADR-0002 2nd addendum, 09.07.2026).
        tags = [
            tag.get("name") if isinstance(tag, dict) else tag
            for tag in issue.get("tags", [])
        ]
        tags = [t for t in tags if t and not is_reserved_tag(t)]

        return {
            "id": issue.get("idReadable"),
            "title": issue.get("summary"),
            "status": status,
            "description": issue.get("description") or "",
            "result-link": result_links,
            "comments": comments,
            "owner": owner,
            "type": item_type,
            "tags": tags,
            "runner": runner,
            "heartbeat": heartbeat,
        }

    def _runner_and_heartbeat_from_tags(self, tags, item_id):
        runner = None
        heartbeat = None
        for tag in tags:
            name = tag.get("name") if isinstance(tag, dict) else tag
            if not name:
                continue
            if name.startswith(_RUNNER_TAG_PREFIX):
                runner = name[len(_RUNNER_TAG_PREFIX):]
            elif name.startswith(_HEARTBEAT_TAG_PREFIX):
                compact = name[len(_HEARTBEAT_TAG_PREFIX):]
                # runner:/heartbeat: tags are editable in the YouTrack UI -- a
                # malformed one must degrade to "no valid heartbeat", never crash.
                heartbeat_dt = safe_parse_datetime(
                    compact, lambda v: datetime.datetime.strptime(v, _HEARTBEAT_TAG_FORMAT),
                )
                if heartbeat_dt is None:
                    print(
                        f"Warning: YouTrack issue {item_id} has a malformed "
                        f"heartbeat tag ({name!r}); treating it as no heartbeat.",
                        file=sys.stderr,
                    )
                    continue
                heartbeat = heartbeat_dt.replace(tzinfo=datetime.timezone.utc).isoformat()
        return runner, heartbeat


_REQUEST_TIMEOUT_SECONDS = 10


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
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_SECONDS) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            exc.close()
            raise WorkItemError(
                f"YouTrack API error {exc.code} for {method} {url}: {detail}"
            ) from exc
        except OSError as exc:
            # Covers urllib.error.URLError (DNS/connection failures) AND a bare
            # TimeoutError/socket.timeout during connect or read. URLError does NOT
            # subclass TimeoutError (and vice versa) — a stall during resp.read()
            # inside the `with` block above raises a plain TimeoutError, which would
            # otherwise bypass this except entirely and surface as a raw traceback.
            raise WorkItemError(f"YouTrack request failed for {method} {url}: {exc}") from exc

        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WorkItemError(
                f"YouTrack returned a response that isn't valid JSON for {method} {url}: {exc}"
            ) from exc
