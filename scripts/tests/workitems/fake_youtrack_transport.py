"""fake_youtrack_transport.py – In-memory stand-in for YouTrack's REST + Command API.

No network, no urllib: simulates just enough of the JSON shape (issues, custom fields,
commands, comments) for YouTrackBackend to be exercised end-to-end against the shared
contract fixture and dedicated youtrack tests, per ADR-0003's operation mapping.
"""

import urllib.parse

from workitems import WorkItemError


class FakeYouTrackTransport:
    """Implements the same `.request(method, url, token, body=None)` interface as the
    real `_HttpTransport`, so YouTrackBackend cannot tell the difference."""

    def __init__(self, project_short_name="TEST", page_size_cap=None,
                 known_states=None, known_users=None):
        self.project_short_name = project_short_name
        self.project_internal_id = "0-0"
        self.commands_received = []  # for tests asserting on the exact command string
        self._issues = {}  # idReadable -> internal issue dict
        self._next_number = 1
        # Simulates a real YouTrack instance's default page size: without an explicit
        # "$top=-1", a GET /api/issues that would return more than this many issues is
        # truncated. Used to prove list() actually sends "$top=-1" instead of relying
        # on undocumented server-default behaviour.
        self.page_size_cap = page_size_cap
        # None = permissive (accept any value) — the default so existing tests that
        # don't care about this stay unaffected. A test that DOES care constructs the
        # fake with a specific set, matching a real instance's actual State bundle /
        # project membership: verified against a real instance, an unresolvable
        # `State <name>` or `for <user>` command returns HTTP 400 and leaves the issue
        # unchanged (atomic reject, no partial apply) — the real _HttpTransport
        # already turns that into a WorkItemError; this fake previously accepted any
        # string, silently hiding that error path from tests.
        self.known_states = known_states
        self.known_users = known_users

    def request(self, method, url, token, body=None):
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        query_params = dict(urllib.parse.parse_qsl(parsed.query))

        if method == "GET" and path == "/api/admin/projects":
            return [{"id": self.project_internal_id, "shortName": self.project_short_name}]

        if method == "POST" and path == "/api/issues":
            return self._create_issue(body)

        if method == "GET" and path == "/api/issues":
            all_issues = [self._render_issue(issue) for issue in self._issues.values()]
            if self.page_size_cap is not None and query_params.get("$top") != "-1":
                return all_issues[:self.page_size_cap]
            return all_issues

        if method == "GET" and path.startswith("/api/issues/"):
            item_id = path.rsplit("/", 1)[-1]
            return self._render_issue(self._require_issue(item_id))

        if method == "POST" and path == "/api/commands":
            return self._run_command(body)

        if method == "POST" and path.endswith("/comments"):
            item_id = path.split("/")[-2]
            issue = self._require_issue(item_id)
            issue["comments"].append({"text": body["text"]})
            return {"text": body["text"]}

        raise AssertionError(f"FakeYouTrackTransport: unhandled request {method} {path}")

    def _require_issue(self, item_id):
        issue = self._issues.get(item_id)
        if issue is None:
            raise WorkItemError(f"YouTrack issue not found: {item_id}")
        return issue

    def _create_issue(self, body):
        item_id = f"{self.project_short_name}-{self._next_number}"
        self._next_number += 1
        self._issues[item_id] = {
            "idReadable": item_id,
            "summary": body["summary"],
            "description": body.get("description") or "",
            "state": None,
            "assignee_login": None,
            "comments": [],
            "tags": [],
        }
        return {"idReadable": item_id}

    def _run_command(self, body):
        query = body["query"]
        self.commands_received.append(query)
        for ref in body["issues"]:
            issue = self._require_issue(ref["idReadable"])
            if query.startswith("State "):
                value = query[len("State "):]
                if self.known_states is not None and value not in self.known_states:
                    # Validate BEFORE mutating: atomic reject, matching the real API
                    # (a rejected command leaves the issue unchanged, no partial apply).
                    raise WorkItemError(f"YouTrack command rejected (HTTP 400): State expected: {value}")
                issue["state"] = value
            elif query.startswith("for "):
                value = query[len("for "):]
                if self.known_users is not None and value not in self.known_users:
                    raise WorkItemError(f"YouTrack command rejected (HTTP 400): user expected: {value}")
                issue["assignee_login"] = value
            elif query.startswith("remove tag "):
                tag_name = query[len("remove tag "):]
                if tag_name in issue["tags"]:
                    issue["tags"].remove(tag_name)
            elif query.startswith("tag "):
                tag_name = query[len("tag "):]
                if tag_name not in issue["tags"]:
                    issue["tags"].append(tag_name)
            # "Type <name>" and other commands are accepted but not modeled: "type"
            # is a backend-specific extension, not part of the core contract model.
        return {}

    def _render_issue(self, issue):
        custom_fields = []
        if issue["state"] is not None:
            custom_fields.append({"name": "State", "value": {"name": issue["state"]}})
        if issue["assignee_login"] is not None:
            custom_fields.append({"name": "Assignee", "value": {"login": issue["assignee_login"]}})
        return {
            "idReadable": issue["idReadable"],
            "summary": issue["summary"],
            "description": issue["description"],
            "customFields": custom_fields,
            "comments": issue["comments"],
            "tags": [{"name": t} for t in issue["tags"]],
        }
