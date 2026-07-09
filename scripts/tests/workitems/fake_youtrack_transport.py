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
                 known_states=None, known_users=None, known_types=None, known_tags=None,
                 known_sprints=None, estimate_field_name=None, child_side_link_names=None):
        self.project_short_name = project_short_name
        self.project_internal_id = "0-0"
        self.commands_received = []  # for tests asserting on the exact command string
        # for tests asserting on the exact `query` param sent to GET /api/issues (the
        # --query passthrough's project-scoping prefix, ADR-0002 2nd addendum).
        self.list_queries_received = []
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
        # Same idea, for the project's Type bundle (e.g. Bug/Feature/Task) -- CCPR's
        # own type vocabulary (feat/fix/refactor/docs/chore) generally does NOT match
        # a real project's Type bundle verbatim, which is exactly the mismatch that
        # caused a live orphaned-issue bug (create() raised on the rejected `Type`
        # command AFTER the issue already existed via POST /api/issues).
        self.known_types = known_types
        # Same idea, for a workflow that restricts which tags may be applied --
        # exercises create()'s best-effort tag handling (a rejected tag must warn
        # and continue, never orphan the already-committed issue).
        self.known_tags = known_tags
        # Same idea, for the Sprint enum bundle -- restrictive only in a dedicated
        # hard-fail test (mirrors known_states/known_types).
        self.known_sprints = known_sprints
        # The (project-specific, configurable) custom field name set-estimate writes
        # to -- None means the fake never recognises an estimate command (matching a
        # project that hasn't configured workitems.youtrack.estimateField).
        self.estimate_field_name = estimate_field_name
        # Typed links (ADR-0008): a shared, undirected edge list -- one edge is
        # visible from BOTH linked issues (with an opposite `direction`), matching how
        # a real YouTrack link record works. `child_side_link_names` models the one
        # link type (by default "subtask of", the mechanical default name) whose
        # ISSUER side reads back as INWARD rather than OUTWARD -- see _links_for.
        self._links = []
        self._child_side_link_names = (
            child_side_link_names if child_side_link_names is not None
            else {"subtask of"}
        )

    def request(self, method, url, token, body=None):
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        query_params = dict(urllib.parse.parse_qsl(parsed.query))

        if method == "GET" and path == "/api/admin/projects":
            return [{"id": self.project_internal_id, "shortName": self.project_short_name}]

        if method == "POST" and path == "/api/issues":
            return self._create_issue(body)

        if method == "GET" and path == "/api/issues":
            self.list_queries_received.append(query_params.get("query"))
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

        if method == "POST" and path.startswith("/api/issues/"):
            item_id = path.rsplit("/", 1)[-1]
            issue = self._require_issue(item_id)
            if "summary" in body:
                issue["summary"] = body["summary"]
            if "description" in body:
                issue["description"] = body["description"]
            return {}

        if method == "DELETE" and path.startswith("/api/issues/"):
            item_id = path.rsplit("/", 1)[-1]
            self._require_issue(item_id)
            del self._issues[item_id]
            return None

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
            "type": None,
            "sprint": None,
            "priority": None,
            "estimate": None,
            "comments": [],
            "tags": [],
        }
        return {"idReadable": item_id}

    def _run_command(self, body):
        query = body["query"]
        self.commands_received.append(query)
        for ref in body["issues"]:
            item_id = ref["idReadable"]
            issue = self._require_issue(item_id)
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
                if self.known_tags is not None and tag_name not in self.known_tags:
                    raise WorkItemError(f"YouTrack command rejected (HTTP 400): tag not permitted: {tag_name}")
                if tag_name not in issue["tags"]:
                    issue["tags"].append(tag_name)
            elif query.startswith("Type "):
                value = query[len("Type "):]
                if self.known_types is not None and value not in self.known_types:
                    # Mirrors the real instance: CCPR's own type vocabulary
                    # (feat/fix/refactor/docs/chore) generally does not match a
                    # project's actual Type bundle (e.g. Bug/Feature/Task) verbatim.
                    raise WorkItemError(f"YouTrack command rejected (HTTP 400): Type expected: {value}")
                issue["type"] = value
            elif query.startswith("Sprint "):
                value = query[len("Sprint "):]
                if self.known_sprints is not None and value not in self.known_sprints:
                    raise WorkItemError(f"YouTrack command rejected (HTTP 400): Sprint expected: {value}")
                issue["sprint"] = value
            elif query.startswith("Priority "):
                issue["priority"] = query[len("Priority "):]
            elif self.estimate_field_name and query.startswith(f"{self.estimate_field_name} "):
                issue["estimate"] = query[len(self.estimate_field_name) + 1:]
            elif query.startswith("remove "):
                self._apply_remove_link_command(item_id, query[len("remove "):])
            else:
                self._apply_add_link_command(item_id, query)
        return {}

    def _apply_add_link_command(self, from_id, query):
        # Splitting on the LAST space works regardless of the (possibly multi-word,
        # possibly linkTypeMap-overridden) link-type name, since a work-item id never
        # contains a space -- no need to know the recognised name set up front.
        name, _, target_id = query.rpartition(" ")
        self._require_issue(target_id)
        edge = (name, from_id, target_id)
        if edge not in self._links:
            self._links.append(edge)

    def _apply_remove_link_command(self, from_id, query):
        name, _, target_id = query.rpartition(" ")
        edge = (name, from_id, target_id)
        if edge in self._links:
            self._links.remove(edge)

    def _links_for(self, issue_id):
        links = []
        for name, from_id, to_id in self._links:
            child_side = name in self._child_side_link_names
            if issue_id == from_id:
                other, direction = to_id, ("INWARD" if child_side else "OUTWARD")
            elif issue_id == to_id:
                other, direction = from_id, ("OUTWARD" if child_side else "INWARD")
            else:
                continue
            links.append({
                "direction": direction, "linkType": {"name": name},
                "issues": [{"idReadable": other}],
            })
        return links

    def _render_issue(self, issue):
        custom_fields = []
        if issue["state"] is not None:
            custom_fields.append({"name": "State", "value": {"name": issue["state"]}})
        if issue["assignee_login"] is not None:
            custom_fields.append({"name": "Assignee", "value": {"login": issue["assignee_login"]}})
        if issue["type"] is not None:
            custom_fields.append({"name": "Type", "value": {"name": issue["type"]}})
        if issue["sprint"] is not None:
            custom_fields.append({"name": "Sprint", "value": {"name": issue["sprint"]}})
        if issue["priority"] is not None:
            custom_fields.append({"name": "Priority", "value": {"name": issue["priority"]}})
        if issue["estimate"] is not None and self.estimate_field_name:
            # Simulates a scalar (non-bundle) custom field: `value` is the raw number
            # itself, not a nested {"name": ...} object -- the plausible shape for a
            # Simple/Integer field type (unverified against a live instance, see the
            # architect's note in ADR-0002's 2nd addendum).
            custom_fields.append({"name": self.estimate_field_name, "value": int(issue["estimate"])})
        return {
            "idReadable": issue["idReadable"],
            "summary": issue["summary"],
            "description": issue["description"],
            "customFields": custom_fields,
            "comments": issue["comments"],
            "tags": [{"name": t} for t in issue["tags"]],
            "links": self._links_for(issue["idReadable"]),
        }
