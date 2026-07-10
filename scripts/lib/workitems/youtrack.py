"""youtrack.py – The `youtrack` work-item backend: a self-hosted YouTrack REST + Command API
(ADR-0003). No MCP, no third-party HTTP library — stdlib `urllib.request` only.

Design points carried over from the ADR (see ADR-0003 for the full rationale):

- Fields and states are resolved BY NAME at runtime, never by hardcoded numeric field/
  bundle ids — that is what keeps this backend generic across YouTrack instances.
  Reads ask for `customFields(name,value(name,login))` and locate values by their
  `name` (or `login`, for the Assignee user field); writes use the name-based Command
  API (`State <name>`, `for <user>`) rather than raw custom-field writes.
- The token VALUE never lives in settings.json (ADR-0002 §3) — only its SOURCE does,
  either the name of an environment variable (`tokenEnv`) or a file path
  (`tokenFile`, e.g. a 600-permission file outside the repo). `tokenEnv` wins when
  both resolve to a non-empty value (see `_resolve_token`).
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
    is_reserved_tag, reject_result_marker, safe_parse_datetime, validate_estimate,
    validate_item_id, validate_link_type, validate_priority, validate_tag,
)

# `links(direction,linkType(name),issues(idReadable))` (ADR-0008) lets _item_from_issue
# normalize each link relative to the issue being read. The customFields selector's
# nested `value(name,login)` is the shape every EXISTING enum/user field (State, Type,
# Assignee) needs; a scalar (non-bundle) custom field -- the one `estimateField` points
# at -- is expected to come back as a bare number regardless of that nested selection
# (unverified against a live instance, flagged here per the architect's note; the
# read-side in _item_from_issue handles both a dict and a bare scalar defensively).
_ISSUE_FIELDS = (
    "idReadable,summary,description,project(shortName),"
    "customFields(name,value(name,login)),"
    "comments(text),tags(name),links(direction,linkType(name),issues(idReadable))"
)

# Typed-link Command API phrases (ADR-0008): the canonical verb, hyphens replaced by
# spaces, is the MECHANICAL default `linkTypeMap` falls back to when a project's
# instance doesn't override it -- unlike stateMap/priorityMap's identity default,
# because a link verb's dehyphenated form is a reasonable, testable starting point
# (see the ADR's "Alternatives considered" for why this one config key gets a default
# and its siblings don't). `blocks` never appears here -- it's swapped/delegated to
# `depends-on` before a Command API phrase is ever resolved (see add_link/remove_link).
#
# `linkTypeMap` is WRITE-side only (canonical verb -> Command-API phrase). The
# READ side is a SEPARATE concern (`linkTypeNameMap` / `_DEFAULT_LINK_TYPE_NAME_MAP`
# below): verified against a live instance (09.07.2026), `links(linkType(name))`
# returns the link TYPE's own name (`"Depend"`, `"Relates"`, `"Subtask"`) -- never
# the directional Command-API phrase -- so matching it against a dehyphenated verb
# never works and silently drops every link. See _resolve_link_family.
_DEFAULT_LINK_TYPE_NAME_MAP = {
    "Depend": "depends-on",
    "Relates": "relates-to",
    "Subtask": "subtask-of",
}

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


def _stripped_or_none(value):
    """Trims a config string and treats whitespace-only values as unset, so
    e.g. `tokenEnv: "   "` is rejected as "not configured" rather than being
    passed through as a (nonsensical) environment variable name to look up."""
    stripped = (value or "").strip()
    return stripped or None


def create(config):
    """Factory used by the CLI dispatcher (scripts/workitems.py)."""
    base_url = config.get("baseUrl")
    project = config.get("project")
    token_env = _stripped_or_none(config.get("tokenEnv"))
    token_file = _stripped_or_none(config.get("tokenFile"))
    missing = [
        name for name, value in (("baseUrl", base_url), ("project", project)) if not value
    ]
    if not token_env and not token_file:
        missing.append("tokenEnv or tokenFile")
    if missing:
        raise WorkItemError(
            "youtrack backend config is missing required key(s) in settings.json's "
            f"workitems.youtrack: {', '.join(missing)}"
        )

    token = _resolve_token(token_env, token_file)

    return YouTrackBackend(
        base_url, project, token, state_map=config.get("stateMap"),
        stale_after_seconds=config.get("stale_after_seconds"),
        link_type_map=config.get("linkTypeMap"),
        link_type_name_map=config.get("linkTypeNameMap"),
        priority_map=config.get("priorityMap"),
        estimate_field=config.get("estimateField"),
    )


def _resolve_token(token_env, token_file):
    """Resolves the YouTrack auth token (ADR-0002/ADR-0003): the token VALUE must
    never live in settings.json, but its SOURCE does -- either an env var name
    (`tokenEnv`) or a file path (`tokenFile`) pointing at a 600-permission file
    outside the repo.

    Resolution order:
    1. `tokenEnv` set AND the named env var is non-empty -- env wins (CI / an
       explicit session export takes precedence over a standing tokenFile).
    2. Otherwise, `tokenFile` set -- read and strip it (a trailing newline from a
       text editor/echo is the common case, not a token character).
    3. Neither resolves to a non-empty token -- WorkItemError naming both options.
    """
    if token_env:
        env_token = (os.environ.get(token_env) or "").strip()
        if env_token:
            return env_token

    if token_file:
        path = os.path.expanduser(token_file)
        try:
            with open(path, "r") as handle:
                file_token = handle.read().strip()
        except OSError as exc:
            raise WorkItemError(
                f"workitems.youtrack.tokenFile is configured ({path!r}) but could not "
                f"be read: {exc.strerror or exc}"
            ) from exc
        if not file_token:
            raise WorkItemError(
                f"workitems.youtrack.tokenFile ({path!r}) is empty -- it must contain "
                "the YouTrack token."
            )
        return file_token

    # Reached only when tokenFile isn't configured at all (a configured tokenFile
    # always either returns above or raises its own dedicated error) -- so if
    # tokenEnv IS configured, name it, since that's the actionable detail here.
    if token_env:
        raise WorkItemError(
            f"environment variable {token_env!r} is not set (or empty) -- set it, or "
            "configure workitems.youtrack.tokenFile to read the token from a file "
            "instead."
        )
    raise WorkItemError(
        "no YouTrack token available: set the environment variable named by "
        "workitems.youtrack.tokenEnv, or point workitems.youtrack.tokenFile at a "
        "file (outside the repo, e.g. mode 600) containing the token."
    )


class YouTrackBackend:
    def __init__(self, base_url, project, token, state_map=None, transport=None,
                 clock=None, stale_after_seconds=None, link_type_map=None,
                 link_type_name_map=None, priority_map=None, estimate_field=None):
        self.base_url = base_url.rstrip("/")
        self.project = project
        self.token = token
        self.state_map = state_map or {}
        self._reverse_state_map = {v: k for k, v in self.state_map.items()}
        self.link_type_map = link_type_map or {}
        # READ-side resolution (ADR-0008, corrected 09.07.2026): stock English
        # defaults, overridable per project the same way stateMap/priorityMap are --
        # an instance's link-type NAMES (as opposed to the Command-API phrase
        # linkTypeMap governs) are themselves renameable/localizable admin config.
        self._link_type_name_map = {
            **_DEFAULT_LINK_TYPE_NAME_MAP, **(link_type_name_map or {}),
        }
        self.priority_map = priority_map or {}
        self._reverse_priority_map = {v: k for k, v in self.priority_map.items()}
        # No default (unlike stateMap/priorityMap): no YouTrack instance ships a
        # story-point-like field by default, so it must be configured explicitly
        # (ADR-0002 2nd addendum) -- set_estimate raises immediately if this is None.
        self.estimate_field = estimate_field
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

    def create(self, title, item_type=None, owner=None, description=None, tags=None):
        if not title:
            raise WorkItemError("title is required")
        # Charset/reserved-namespace violations are structural client-side errors,
        # not a server-side rejection -- validated upfront, before POST /api/issues,
        # so a malformed tag never creates an issue at all (unlike an unmappable-but-
        # well-formed tag, which is a real "rejected by this project's workflow"
        # case handled best-effort below, after the issue already exists).
        tags = list(tags or [])
        for tag in tags:
            validate_tag(tag)

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
        for tag in tags:
            self._apply_optional_create_field(item_id, f"tag {tag}", "tag", tag)

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

    def list(self, status=None, owner=None, tags=None, item_type=None, query=None,
             sprint=None, priority=None):
        # $top=-1 disables pagination explicitly — without it, some YouTrack versions
        # cap /api/issues to a default page size, silently truncating a large project.
        # `query` is passed through verbatim to YouTrack's own query language, always
        # prefixed with `project: <PROJ> ` (ADR-0002 2nd addendum). That textual
        # prefix alone is NOT a reliable scoping guarantee, though: a caller-supplied
        # query containing its own `project:` clause joined with `or` (or unbalanced
        # parens) can defeat it server-side -- the guarantee this backend actually
        # promises must not depend on YouTrack's query-language boolean semantics.
        # So the result is ALSO post-filtered client-side below, structurally, against
        # the `project(shortName)` field _ISSUE_FIELDS now requests: fail-closed (an
        # issue with unexpectedly missing/mismatched project info is dropped, never
        # leaked) and independent of whatever the query string happened to say.
        scoped_query = f"project: {self.project}"
        if query:
            scoped_query = f"{scoped_query} {query}"
        issues = self._request(
            "GET", "/api/issues", fields=_ISSUE_FIELDS, query=scoped_query, top=-1,
        )
        issues = [
            issue for issue in issues
            if (issue.get("project") or {}).get("shortName") == self.project
        ]
        items = [self._item_from_issue(issue) for issue in issues]
        if status is not None:
            items = [item for item in items if item["status"] == status]
        if owner is not None:
            items = [item for item in items if item["owner"] == owner]
        if tags:
            items = [item for item in items if set(tags).issubset(item["tags"])]
        if item_type is not None:
            items = [item for item in items if item["type"] == item_type]
        if sprint is not None:
            items = [item for item in items if item["sprint"] == sprint]
        if priority is not None:
            items = [item for item in items if item["priority"] == priority]
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

    def set_sprint(self, item_id, sprint):
        """Sets the `Sprint` Enum custom field (fixed name, a setup precondition --
        ADR-0002 2nd addendum), single-valued (a later call overwrites, never
        accumulates). No value-mapping: the caller-supplied value IS the Enum value
        name the project's admin configured. Fails hard on rejection, same as
        `set_type` -- a dedicated call with nothing else to protect via atomicity."""
        validate_item_id(item_id)
        self._run_command(item_id, f"Sprint {sprint}")
        return self.get(item_id)

    def set_priority(self, item_id, priority):
        """Validates against the closed CCPR vocabulary (ADR-0002 2nd addendum),
        then maps to the project's own `Priority` bundle name via `priorityMap`
        (identity default, same escape hatch as `stateMap`). Fails hard on
        rejection, same as set_type/set_sprint."""
        validate_item_id(item_id)
        validate_priority(priority)
        mapped = self._map_priority(priority)
        self._run_command(item_id, f"Priority {mapped}")
        return self.get(item_id)

    def set_estimate(self, item_id, points):
        """Sets a project-specific numeric custom field (name configured via
        `estimateField`, no default -- ADR-0002 2nd addendum): raises immediately,
        BEFORE any API call, if it isn't configured, rather than guessing a
        plausible-sounding default that might not exist on a given instance."""
        validate_item_id(item_id)
        validate_estimate(points)
        if not self.estimate_field:
            raise WorkItemError(
                "workitems.youtrack.estimateField is not configured in "
                ".claude/settings.json -- set-estimate needs the name of a numeric "
                "custom field for story-point estimates (no default exists, since no "
                "YouTrack instance ships one by default)."
            )
        self._run_command(item_id, f"{self.estimate_field} {points}")
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

    def add_link(self, item_id, link_type, target_id):
        """Creates a typed edge (ADR-0008), idempotent (checks the current, already
        direction-normalized links[] first, same pattern as add_tag). `blocks` is
        pure sugar: id/target are swapped and delegated to `depends-on` -- there is
        no separate `blocks` Command API phrase, only the three real verbs ever
        appear in `linkTypeMap`."""
        validate_link_type(link_type)
        validate_item_id(item_id)
        validate_item_id(target_id)
        if link_type == "blocks":
            item_id, target_id, link_type = target_id, item_id, "depends-on"
        current = self.get(item_id)
        if {"type": link_type, "target": target_id} in current["links"]:
            return current
        mapped = self._map_link_type(link_type)
        self._run_command(item_id, f"{mapped} {target_id}")
        return self.get(item_id)

    def remove_link(self, item_id, link_type, target_id):
        """Removes an exact `{type, target}` edge; a no-op if it isn't present
        (checked via a `get` first, same idempotence rule as remove_tag)."""
        validate_link_type(link_type)
        validate_item_id(item_id)
        validate_item_id(target_id)
        if link_type == "blocks":
            item_id, target_id, link_type = target_id, item_id, "depends-on"
        current = self.get(item_id)
        if {"type": link_type, "target": target_id} not in current["links"]:
            return current
        mapped = self._map_link_type(link_type)
        self._run_command(item_id, f"remove {mapped} {target_id}")
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

    def _map_priority(self, ccpr_priority):
        """CCPR vocabulary name -> the project's own Priority bundle name."""
        return self.priority_map.get(ccpr_priority, ccpr_priority)

    def _unmap_priority(self, project_priority_name):
        """The project's own Priority bundle name -> CCPR vocabulary name."""
        if project_priority_name is None:
            return None
        return self._reverse_priority_map.get(project_priority_name, project_priority_name)

    def _map_link_type(self, canonical_verb):
        """Canonical verb -> the instance's actual YouTrack link-type name. Unlike
        _map_state's identity default, this falls back to the MECHANICAL dehyphenated
        form (ADR-0008) rather than the bare verb itself."""
        return self.link_type_map.get(canonical_verb, canonical_verb.replace("-", " "))

    def _resolve_link_family(self, project_link_type_name):
        """YouTrack's link TYPE name (`linkType.name`, e.g. `"Depend"`) -> one of
        the three canonical link families, or None if it can't be resolved (an
        unrelated link type present on the issue, e.g. a project's own "Duplicate"
        type -- skipped on read, never surfaced as a made-up verb). Keyed by NAME,
        never by the directional Command-API phrase -- see `_link_type_name_map`'s
        docstring in __init__ and the module-level `_DEFAULT_LINK_TYPE_NAME_MAP`
        comment for why this is a separate map from `linkTypeMap`/`_map_link_type`
        (the write-side counterpart, which goes the other direction: canonical verb
        -> phrase)."""
        if project_link_type_name is None:
            return None
        return self._link_type_name_map.get(project_link_type_name)

    def _parse_links(self, raw_links):
        """Normalizes YouTrack's per-issue direction into the canonical {type,
        target} shape (ADR-0008, the load-bearing rule -- direction convention
        verified against a live instance, 09.07.2026):

        - Depend type,  INWARD  (this item is the dependent)      -> depends-on
        - Depend type,  OUTWARD (this item is depended upon)      -> blocks
        - Relates type, any direction (symmetric, reported BOTH)  -> relates-to
        - Subtask type, INWARD  (this item is the child)          -> subtask-of
        - Subtask type, OUTWARD (this item is the parent)         -> not surfaced
          (documented, intentional gap -- no "has-subtask" verb exists yet)
        """
        links = []
        for link in raw_links:
            link_type_name = (link.get("linkType") or {}).get("name")
            family = self._resolve_link_family(link_type_name)
            if family is None:
                continue
            direction = link.get("direction")
            for linked_issue in link.get("issues", []):
                target = linked_issue.get("idReadable")
                if not target:
                    continue
                if family == "depends-on":
                    if direction == "INWARD":
                        links.append({"type": "depends-on", "target": target})
                    elif direction == "OUTWARD":
                        links.append({"type": "blocks", "target": target})
                elif family == "relates-to":
                    links.append({"type": "relates-to", "target": target})
                elif family == "subtask-of" and direction == "INWARD":
                    links.append({"type": "subtask-of", "target": target})
        return links

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

        sprint_value = custom_fields.get("Sprint")
        sprint = sprint_value.get("name") if isinstance(sprint_value, dict) else None

        priority_value = custom_fields.get("Priority")
        priority_name = priority_value.get("name") if isinstance(priority_value, dict) else None
        priority = self._unmap_priority(priority_name)

        # Unlike the Enum fields above (State/Type/Sprint/Priority, read via
        # value(name)), the estimate field's YouTrack value is a bare SCALAR number
        # -- this is the one field _ISSUE_FIELDS/_item_from_issue must handle
        # differently (unverified against a live instance, see the module docstring
        # note next to _ISSUE_FIELDS). Defensive on both shapes: a dict would mean an
        # unexpected Enum-like wrapping, treated as absent rather than crashing.
        estimate = None
        if self.estimate_field:
            estimate_value = custom_fields.get(self.estimate_field)
            if isinstance(estimate_value, bool):
                estimate = None
            elif isinstance(estimate_value, (int, float)):
                estimate = int(estimate_value)
            elif estimate_value is not None:
                # Anything other than a bare number (and not simply absent) means
                # estimateField is misconfigured -- most likely pointing at an
                # Enum/bundle custom field (which comes back as a {"name": ...}
                # dict, mirroring the Enum fields above) instead of a plain numeric
                # one. Surfaced the same way the state-outside-vocabulary case above
                # is: visible on stderr, not silently swallowed into `estimate: None`.
                print(
                    f"Warning: YouTrack issue {issue.get('idReadable')} has a "
                    f"non-numeric value {estimate_value!r} for the configured "
                    f"estimate field {self.estimate_field!r} (expected a plain "
                    "number). Passing it through as no estimate; check that "
                    "workitems.youtrack.estimateField names a numeric custom field, "
                    "not an Enum/bundle one.",
                    file=sys.stderr,
                )

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
            "sprint": sprint,
            "priority": priority,
            "estimate": estimate,
            "links": self._parse_links(issue.get("links", [])),
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
