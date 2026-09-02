"""fake_youtrack_transport.py – In-memory stand-in for YouTrack's REST + Command API.

No network, no urllib: simulates just enough of the JSON shape (issues, custom fields,
commands, comments) for YouTrackBackend to be exercised end-to-end against the shared
contract fixture and dedicated youtrack tests, per ADR-0003's operation mapping.
"""

import re
import urllib.parse

from workitems import WorkItemError


class FakeYouTrackTransport:
    """Implements the same `.request(method, url, token, body=None)` interface as the
    real `_HttpTransport`, so YouTrackBackend cannot tell the difference."""

    # Default phrase (as sent by `linkTypeMap`'s mechanical dehyphenate default,
    # or overridden) -> the real instance's link TYPE name (`linkType.name`). A
    # live instance's `linkType.name` is the type's own name -- "Depend", not
    # "depends on" -- independent of whatever Command-API phrase is configured to
    # send (verified 09.07.2026, see ADR-0008). `symmetric` type names are
    # reported with `direction: "BOTH"` from either side (e.g. "Relates"); every
    # other type is reported `INWARD` on the ISSUER's own side and `OUTWARD` on
    # the target's side (also verified against a live instance -- the opposite of
    # what an earlier version of this fake assumed).
    _DEFAULT_LINK_TYPE_NAMES = {
        "depends on": "Depend",
        "relates to": "Relates",
        "subtask of": "Subtask",
    }
    _DEFAULT_SYMMETRIC_TYPE_NAMES = frozenset({"Relates"})

    # /api/groups default, matching what a live probe measured (see youtrack.py's
    # tagVisibilityGroup docstrings): a real instance always has an "All Users"
    # group alongside project-team groups. Tests that need a missing or ambiguous
    # group override `known_groups` explicitly; this default keeps every OTHER
    # test (which never configures tagVisibilityGroup at all) unaffected.
    _DEFAULT_GROUPS = [{"id": "102-0", "name": "All Users"}]

    def __init__(self, project_short_name="TEST", page_size_cap=None,
                 known_states=None, known_users=None, known_types=None, known_tags=None,
                 known_sprints=None, estimate_field_name=None, link_type_names=None,
                 symmetric_type_names=None, known_groups=None,
                 corrupt_tag_visibility_readback=False):
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
        # visible from BOTH linked issues (with an opposite `direction`), matching
        # how a real YouTrack link record works. `link_type_names` resolves the
        # Command-API phrase a link was created with to the real instance's link
        # TYPE name (`linkType.name`) -- see the class-level docstring above and
        # _links_for.
        self._links = []
        self._link_type_names = {
            **self._DEFAULT_LINK_TYPE_NAMES, **(link_type_names or {}),
        }
        self._symmetric_type_names = (
            symmetric_type_names if symmetric_type_names is not None
            else self._DEFAULT_SYMMETRIC_TYPE_NAMES
        )
        # comments are NOT idempotent (unlike the Command-API paths above, which all
        # reject via known_states/known_users/known_types/known_tags/known_sprints):
        # `POST /api/issues/<id>/comments` has no pre-check of its own, so a caller
        # (migrate.py's comment-copy phase) that resumes after a crash must be able
        # to observe a rejected write. `_fail_comment_at_indices` counts calls
        # GLOBALLY across every issue (not per-issue): a test can simulate a crash
        # mid-way through one issue's own comment list, OR between two different
        # issues, purely by counting -- without needing to predict the target id a
        # not-yet-created issue will be assigned (see fail_comment_at's docstring).
        self._fail_comment_at_indices = set()
        self._comment_post_count = 0
        # Same idea, for typed-link Command-API calls (migrate.py's links pass):
        # unlike the State/tag/Type/Sprint command branches above, an add-link
        # command has no known-value set to reject against --
        # a caller resuming after a crash relies on the target rejecting or
        # dropping the write, which this hook simulates directly. Counted
        # globally (not per-issue), same rationale as `_fail_comment_at_indices`.
        self._fail_link_at_indices = set()
        self._link_command_count = 0
        # Tag registry (/api/tags), separate from the Command-API `tag <name>`
        # branch's per-issue application above: on a real instance a tag is a
        # standalone resource with its own id/owner/visibleFor, created either
        # explicitly (POST /api/tags, this backend's new tagVisibilityGroup path)
        # or implicitly the first time a `tag <name>` command names one that
        # doesn't exist yet (mirrored by `_ensure_tag_registered`, called from
        # both places) -- visibleFor is None (private) on either creation path,
        # matching the measured live-instance shape.
        self._tags = {}  # name -> {"id", "name", "visibleFor", "updateableBy"}
        self._next_tag_number = 1
        # Test hook: names created via an EXPLICIT POST /api/tags call (as
        # opposed to a tag springing into existence implicitly via a `tag <name>`
        # Command-API call, see _ensure_tag_registered) -- lets a test prove a
        # tag that already exists was left untouched (no explicit POST at all),
        # distinct from asserting the shared Command-API request log stayed the
        # same shape.
        self.explicit_tag_creation_calls = []
        self._groups = (
            list(known_groups) if known_groups is not None else list(self._DEFAULT_GROUPS)
        )
        # Test hook: makes the fake's GET /api/tags/{id} report visibleFor/
        # updateableBy as if the tag were still private, regardless of what a
        # prior POST /api/tags/{id} actually recorded -- simulates a real
        # instance's set call reporting success while the value didn't actually
        # take, which the backend's read-back-after-set step must catch.
        self.corrupt_tag_visibility_readback = corrupt_tag_visibility_readback
        # Same counting/rejection shape as _fail_comment_at_indices/
        # _fail_link_at_indices: the (0-based) index-th POST /api/tags/{id}
        # visibility-set call raises instead of applying, simulating a real
        # instance rejecting the write outright (as opposed to silently not
        # taking it, which corrupt_tag_visibility_readback simulates).
        self._fail_tag_visibility_set_at_indices = set()
        self._tag_visibility_set_count = 0

    def request(self, method, url, token, body=None):
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        query_params = dict(urllib.parse.parse_qsl(parsed.query))

        if method == "GET" and path == "/api/admin/projects":
            return [{"id": self.project_internal_id, "shortName": self.project_short_name}]

        if method == "POST" and path == "/api/issues":
            return self._create_issue(body)

        if method == "GET" and path == "/api/issues":
            query = query_params.get("query")
            self.list_queries_received.append(query)
            matching_issues = [
                issue for issue in self._issues.values() if self._matches_query(issue, query)
            ]
            all_issues = [self._render_issue(issue) for issue in matching_issues]
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
            index = self._comment_post_count
            self._comment_post_count += 1
            if index in self._fail_comment_at_indices:
                # Rejected BEFORE mutating -- same atomic-reject discipline as the
                # Command-API paths above: a rejected write leaves the issue
                # unchanged, no partial apply.
                raise WorkItemError(
                    f"YouTrack comment rejected (simulated failure, call #{index}) "
                    f"for {item_id}"
                )
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

        if method == "GET" and path == "/api/groups":
            return list(self._groups)

        if method == "GET" and path == "/api/tags":
            return [self._tag_public(tag) for tag in self._tags.values()]

        if method == "POST" and path == "/api/tags":
            self.explicit_tag_creation_calls.append(body["name"])
            return self._tag_public(self._ensure_tag_registered(body["name"]))

        if method == "POST" and path.startswith("/api/tags/"):
            tag_id = path.rsplit("/", 1)[-1]
            return self._tag_public(self._set_tag_visibility(tag_id, body))

        if method == "GET" and path.startswith("/api/tags/"):
            tag_id = path.rsplit("/", 1)[-1]
            tag = self._require_tag_by_id(tag_id)
            if self.corrupt_tag_visibility_readback:
                return {
                    "id": tag["id"], "name": tag["name"],
                    "visibleFor": None, "updateableBy": None,
                }
            return self._tag_public(tag)

        raise AssertionError(f"FakeYouTrackTransport: unhandled request {method} {path}")

    def _matches_query(self, issue, query):
        """Naive stand-in for YouTrack's own query language: collects every
        `project: <NAME>` token mentioned anywhere in `query` (however it got there --
        including via an `or` a caller-supplied query string injects) and matches if
        the issue's project is one of them. This is deliberately loose (no real
        boolean-operator handling) -- its only job is to reproduce, in-memory, that a
        naive `f"project: {self.project} {query}"` prefix does NOT reliably scope
        results server-side once the passed-through query contains its own `project:`
        clause (the leak this backend's client-side post-filter guards against)."""
        if not query:
            return True
        mentioned_projects = set(re.findall(r"project:\s*(\S+)", query, re.IGNORECASE))
        if not mentioned_projects:
            return True
        return issue["project"] in mentioned_projects

    def fail_comment_at(self, index):
        """Test hook: makes the (0-based) `index`-th `POST /api/issues/.../comments`
        call across the WHOLE session -- every issue, every caller, comment() and
        append_result() alike, since both hit this same endpoint -- raise
        WorkItemError instead of recording the comment, simulating a real instance
        rejecting or dropping a write. Global (not per-issue) so a test can target
        "the 2nd of this issue's own 3 comments" or "the 1st comment of the NEXT
        issue" purely by counting calls, without having to predict a not-yet-created
        issue's id up front (ids are only assigned inside create(), which the test
        may not have called yet when it needs to arm this)."""
        self._fail_comment_at_indices.add(index)

    def fail_tag_visibility_set_at(self, index):
        """Test hook: makes the (0-based) `index`-th POST /api/tags/{id}
        visibility-set call raise WorkItemError instead of applying, simulating a
        real instance rejecting the write outright (same counting/rejection shape
        as fail_comment_at/fail_link_at)."""
        self._fail_tag_visibility_set_at_indices.add(index)

    def _ensure_tag_registered(self, name):
        """Returns the registry entry for `name`, creating a fresh PRIVATE one
        (visibleFor/updateableBy both None) if it doesn't exist yet -- mirrors a
        real instance's own behaviour, where a tag springs into existence private
        to the executing identity the first time it's named, whether via an
        explicit POST /api/tags or implicitly via a `tag <name>` command."""
        if name not in self._tags:
            tag_id = f"10-{self._next_tag_number}"
            self._next_tag_number += 1
            self._tags[name] = {
                "id": tag_id, "name": name, "visibleFor": None, "updateableBy": None,
            }
        return self._tags[name]

    def _require_tag_by_id(self, tag_id):
        for tag in self._tags.values():
            if tag["id"] == tag_id:
                return tag
        raise WorkItemError(f"YouTrack tag not found: {tag_id}")

    def _set_tag_visibility(self, tag_id, body):
        tag = self._require_tag_by_id(tag_id)
        index = self._tag_visibility_set_count
        self._tag_visibility_set_count += 1
        if index in self._fail_tag_visibility_set_at_indices:
            raise WorkItemError(
                f"YouTrack tag visibility update rejected (simulated failure, "
                f"call #{index}) for tag {tag['name']!r}"
            )
        for field in ("visibleFor", "updateableBy"):
            if field not in body:
                continue
            group_ref = body[field]
            group_id = group_ref.get("id") if isinstance(group_ref, dict) else group_ref
            matched = next((g for g in self._groups if g["id"] == group_id), None)
            tag[field] = matched or {"id": group_id}
        return tag

    def _tag_public(self, tag):
        return {
            "id": tag["id"], "name": tag["name"],
            "visibleFor": tag["visibleFor"], "updateableBy": tag["updateableBy"],
        }

    def fail_link_at(self, index):
        """Test hook: makes the (0-based) `index`-th add-link Command-API call
        (a `POST /api/commands` query that doesn't match any known field/tag/
        remove-link branch in `_run_command`) raise WorkItemError instead of
        applying it, simulating a real instance rejecting or dropping a link
        write. Global (not per-issue), same rationale as `fail_comment_at`: a
        test can target "the 2nd of this issue's own links" or "the 1st link
        of the NEXT issue" purely by counting calls."""
        self._fail_link_at_indices.add(index)

    def seed_foreign_issue(self, item_id, project_short_name, summary="Foreign issue"):
        """Test helper: injects an issue belonging to a DIFFERENT project directly,
        bypassing backend.create() (which always creates issues in the configured
        project). Used to prove `--query` cannot leak results across a project
        boundary (ADR-0002 2nd addendum)."""
        self._issues[item_id] = {
            "idReadable": item_id,
            "summary": summary,
            "description": "",
            "state": None,
            "assignee_login": None,
            "type": None,
            "sprint": None,
            "priority": None,
            "estimate": None,
            "comments": [],
            "tags": [],
            "project": project_short_name,
        }

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
            "project": self.project_short_name,
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
                self._ensure_tag_registered(tag_name)
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
                index = self._link_command_count
                self._link_command_count += 1
                if index in self._fail_link_at_indices:
                    # Rejected BEFORE mutating -- same atomic-reject discipline
                    # as every other command branch above and the comments
                    # endpoint: a rejected write leaves the issue unchanged.
                    raise WorkItemError(
                        f"YouTrack link command rejected (simulated failure, "
                        f"call #{index}) for {item_id}: {query!r}"
                    )
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
        for phrase, from_id, to_id in self._links:
            type_name = self._link_type_names.get(phrase, phrase)
            symmetric = type_name in self._symmetric_type_names
            if issue_id == from_id:
                other, direction = to_id, ("BOTH" if symmetric else "INWARD")
            elif issue_id == to_id:
                other, direction = from_id, ("BOTH" if symmetric else "OUTWARD")
            else:
                continue
            links.append({
                "direction": direction, "linkType": {"name": type_name},
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
            "project": {"shortName": issue["project"]},
            "customFields": custom_fields,
            "comments": issue["comments"],
            "tags": [{"name": t} for t in issue["tags"]],
            "links": self._links_for(issue["idReadable"]),
        }
