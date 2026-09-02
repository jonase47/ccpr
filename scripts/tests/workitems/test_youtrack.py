"""test_youtrack.py – Wires the `youtrack` backend into the shared contract suite
(ADR-0002/ADR-0003), plus youtrack-specific tests for behaviour the backend-neutral
contract doesn't cover: stateMap remapping, the append-result comment-prefix
disambiguation, config validation in create(config), and the real urllib-based
transport's error translation.

No network, no live YouTrack instance anywhere in this file — see
fake_youtrack_transport.py for the in-memory stand-in used by the contract fixture,
and HttpTransportTest below for the urllib-level tests (mocking urllib.request.urlopen
directly, per the reviewer's second suggested option).
"""

import contextlib
import datetime
import io
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import WorkItemError, sweep, youtrack  # noqa: E402

from .contract import WorkItemsContractTestCase
from .fake_youtrack_transport import FakeYouTrackTransport


class YouTrackBackendContractTest(WorkItemsContractTestCase, unittest.TestCase):
    """Proves the youtrack backend satisfies the SAME contract as local — the whole
    point of ADR-0002 §9 (`local` is the reference implementation and the fixture)."""

    def create_backend(self, workitems_dir):
        # workitems_dir is unused: YouTrack has no filesystem concept. Each test gets
        # its own fresh in-memory "project" instead. estimateField is configured here
        # (a fictional "Story Points" field) so the shared happy-path set_estimate
        # tests exercise the real read/write path -- the estimateField-NOT-configured
        # error is a youtrack-only, dedicated test (see YouTrackSetEstimateTest below).
        self.transport = FakeYouTrackTransport(
            project_short_name="TEST", estimate_field_name="Story Points",
        )
        return youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
            estimate_field="Story Points",
        )


class YouTrackStateMapTest(unittest.TestCase):
    """stateMap lets a project whose State bundle doesn't name its values to match
    CCPR's vocabulary supply a name->name mapping (ADR-0003)."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST", token="fake-token",
            state_map={"Backlog": "Open", "In Progress": "Doing", "Done": "Closed"},
            transport=self.transport,
        )

    def test_set_status_sends_the_mapped_project_state_name(self):
        item = self.backend.create(title="New feature")

        self.backend.set_status(item["id"], "In Progress")

        self.assertIn("State Doing", self.transport.commands_received)

    def test_get_reports_back_the_ccpr_vocabulary_name_not_the_project_name(self):
        item = self.backend.create(title="New feature")

        self.backend.set_status(item["id"], "In Progress")
        fetched = self.backend.get(item["id"])

        self.assertEqual(fetched["status"], "In Progress")

    def test_create_maps_backlog_through_the_state_map_too(self):
        item = self.backend.create(title="New feature")

        self.assertEqual(item["status"], "Backlog")
        self.assertIn("State Open", self.transport.commands_received)


class YouTrackPaginationTest(unittest.TestCase):
    """A real YouTrack instance can silently cap GET /api/issues to a default page
    size unless $top=-1 is passed explicitly. FakeYouTrackTransport's page_size_cap
    simulates that default so list() is proven to send $top=-1, not rely on it."""

    def test_list_returns_everything_even_when_the_fake_caps_page_size(self):
        transport = FakeYouTrackTransport(project_short_name="TEST", page_size_cap=2)
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
        )
        for i in range(5):
            backend.create(title=f"Item {i}")

        items = backend.list()

        self.assertEqual(len(items), 5)


class YouTrackInvalidCommandTest(unittest.TestCase):
    """Verified against a real instance: an unresolvable Command API query (an
    unknown State/user name) returns HTTP 400 and leaves the issue UNCHANGED
    (atomic reject, no partial apply) — already surfaced as a WorkItemError by
    _HttpTransport's existing HTTPError handling. The gap was the FAKE transport,
    which accepted any string as a valid state/assignee; this makes it faithful."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(
            project_short_name="TEST",
            known_states={"Backlog", "In Progress", "Done"},
            known_users={"alice"},
        )
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_set_status_with_unresolvable_state_raises_and_leaves_issue_unchanged(self):
        item = self.backend.create(title="New feature")  # create()'s own "Backlog" is known

        with self.assertRaises(WorkItemError):
            # Valid CCPR vocabulary, but not a state name this project's bundle has.
            self.backend.set_status(item["id"], "Waiting for Approval")

        fetched = self.backend.get(item["id"])
        self.assertEqual(fetched["status"], "Backlog")

    def test_claim_with_unresolvable_assignee_raises(self):
        item = self.backend.create(title="New feature")

        with self.assertRaises(WorkItemError):
            self.backend.claim(item["id"], owner="mallory")


class YouTrackCreateOptionalFieldTest(unittest.TestCase):
    """Live-instance bug: `create --type chore` (CCPR's own type vocabulary very
    often does not match a real project's Type bundle, e.g. Bug/Feature/Task) made
    POST /api/issues succeed, then the follow-up `Type chore` command got rejected
    (HTTP 400) -- and create() raised on that, AFTER the issue already existed.
    The result was an orphaned issue while create() reported failure, and a retry
    would create a duplicate. Per ADR-0002, `type` is an optional backend-specific
    extension the core never relies on, so a rejected Type/owner command at create
    time must warn and continue, never fail the create that already committed."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(
            project_short_name="TEST",
            known_types={"Bug", "Feature", "Task"},
            known_users={"alice"},
        )
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_create_with_unmappable_type_succeeds_and_leaves_no_orphan(self):
        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            item = self.backend.create(title="New feature", item_type="chore")

        self.assertEqual(item["id"], "TEST-1")
        self.assertIsNone(item.get("type"))
        self.assertIn("chore", captured_stderr.getvalue())
        # Exactly one issue exists -- not zero-and-raise, not a duplicate on retry.
        self.assertEqual(len(self.transport._issues), 1)

    def test_create_with_known_type_is_set_without_a_warning(self):
        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            self.backend.create(title="New feature", item_type="Feature")

        self.assertIn("Type Feature", self.transport.commands_received)
        self.assertEqual(captured_stderr.getvalue(), "")

    def test_create_with_unresolvable_owner_succeeds_and_leaves_no_orphan(self):
        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            item = self.backend.create(title="New feature", owner="mallory")

        self.assertEqual(item["id"], "TEST-1")
        self.assertIsNone(item.get("owner"))
        self.assertIn("mallory", captured_stderr.getvalue())
        self.assertEqual(len(self.transport._issues), 1)


class YouTrackCreateTagsTest(unittest.TestCase):
    """`create --tag` is best-effort on youtrack, same footing as `create`'s existing
    `type`/`owner` handling (ADR-0002 2nd addendum, 09.07.2026): the issue already
    exists by the time tags are applied, so a rejected tag must warn and continue,
    never roll back an already-committed create."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(
            project_short_name="TEST", known_tags={"security"},
        )
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_create_with_known_tags_sets_them(self):
        item = self.backend.create(title="New feature", tags=["security"])

        self.assertEqual(item["tags"], ["security"])

    def test_create_with_an_unmappable_tag_succeeds_and_leaves_no_orphan(self):
        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            item = self.backend.create(title="New feature", tags=["security", "not-allowed"])

        self.assertEqual(item["tags"], ["security"])
        self.assertIn("not-allowed", captured_stderr.getvalue())
        # Exactly one issue exists -- not zero-and-raise, not a duplicate on retry.
        self.assertEqual(len(self.transport._issues), 1)


class YouTrackSetTypeHardFailTest(unittest.TestCase):
    """Unlike create()'s best-effort type-setting (warn + continue on a rejected
    Type command), a dedicated set-type call has no atomicity to protect (nothing
    else commits alongside it) and no "expected friction" justification (the
    caller explicitly chose this type) -- it fails hard on rejection (ADR-0002
    addendum, 09.07.2026). `local` has no Type bundle to validate against and
    accepts any string -- that's already covered by the shared contract suite;
    this hard-fail behaviour is youtrack-specific."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(
            project_short_name="TEST", known_types={"Bug", "Feature", "Task"},
        )
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_set_type_with_unmappable_type_raises(self):
        item = self.backend.create(title="New feature")

        with self.assertRaises(WorkItemError):
            self.backend.set_type(item["id"], "chore")

    def test_set_type_with_known_type_succeeds(self):
        item = self.backend.create(title="New feature")

        updated = self.backend.set_type(item["id"], "Bug")

        self.assertEqual(updated["type"], "Bug")


class YouTrackCreateRollbackTest(unittest.TestCase):
    """Unlike `type`/`owner` (optional, best-effort per 4c2d0c4), the initial State
    command sets a CORE, mandatory contract field (ADR-0002 §2) -- a rejection there
    (e.g. "Backlog" missing from the project's own State bundle / stateMap) is a real
    configuration problem, not something to silently continue past. But it still
    happens AFTER POST /api/issues already committed the issue, so raising without
    rolling back would orphan it exactly like the type/owner bug did. create() must
    delete the just-created issue before raising: either a fully-created item, or
    nothing -- never an orphan."""

    def setUp(self):
        # Deliberately excludes "Backlog" -- mirrors a real project whose State
        # bundle (or a misconfigured stateMap) doesn't have a value named that.
        self.transport = FakeYouTrackTransport(
            project_short_name="TEST",
            known_states={"Open", "In Progress", "Closed"},
        )
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_create_rolls_back_the_issue_when_initial_state_is_rejected(self):
        with self.assertRaises(WorkItemError) as ctx:
            self.backend.create(title="New feature")

        self.assertIn("TEST-1", str(ctx.exception))
        self.assertIn("Backlog", str(ctx.exception))
        # Zero issues -- proves rollback, not orphan-and-raise. A retry after this
        # is safe: it won't collide with a half-created TEST-1 left behind.
        self.assertEqual(len(self.transport._issues), 0)

    def test_create_does_not_delete_when_initial_state_is_accepted(self):
        transport = FakeYouTrackTransport(
            project_short_name="TEST", known_states={"Backlog", "In Progress", "Done"},
        )
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
        )

        item = backend.create(title="New feature")

        self.assertEqual(item["status"], "Backlog")
        self.assertEqual(len(transport._issues), 1)

    def test_create_reports_both_failures_when_rollback_delete_also_fails(self):
        class DeleteFailingTransport(FakeYouTrackTransport):
            def request(self, method, url, token, body=None):
                if method == "DELETE":
                    raise WorkItemError("YouTrack API error 500 for DELETE: internal error")
                return super().request(method, url, token, body=body)

        transport = DeleteFailingTransport(
            project_short_name="TEST", known_states={"Open", "In Progress", "Closed"},
        )
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
        )

        with self.assertRaises(WorkItemError) as ctx:
            backend.create(title="New feature")

        message = str(ctx.exception)
        self.assertIn("Backlog", message)
        self.assertIn("rollback delete also failed", message)
        self.assertIn("TEST-1", message)


class YouTrackStateOutsideVocabularyTest(unittest.TestCase):
    """A project's State bundle may legitimately have values outside CCPR's status
    vocabulary and outside any configured stateMap (e.g. a custom workflow state).
    get/list pass such a state through as-is rather than raising -- set_status would
    reject it as a WRITE target, but a value already on the issue must still be
    readable -- while emitting a one-line stderr warning so this stays visible
    instead of silently producing an item whose status looks like any other."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_state_outside_vocabulary_passes_through_with_a_stderr_warning(self):
        item = self.backend.create(title="New feature")
        # Simulate a project state outside CCPR's vocabulary and outside any
        # stateMap, set directly via the transport (bypassing set_status's guard).
        self.transport._require_issue(item["id"])["state"] = "Under Review"

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            fetched = self.backend.get(item["id"])

        self.assertEqual(fetched["status"], "Under Review")
        self.assertIn("Under Review", captured_stderr.getvalue())


class YouTrackPriorityOutsideVocabularyTest(unittest.TestCase):
    """Mirrors YouTrackStateOutsideVocabularyTest above, for the Priority field.
    _unmap_priority has the same identity-fallback shape as _unmap_state (a
    project's Priority bundle may legitimately carry a value outside CCPR's
    PRIORITY_VALUES vocabulary and outside any configured priorityMap) -- get/list
    must pass such a value through as-is rather than raising, with the same
    one-line stderr warning so this stays visible instead of silently producing
    an item whose priority looks like any other."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_priority_outside_vocabulary_passes_through_with_a_stderr_warning(self):
        item = self.backend.create(title="New feature")
        # Simulate a project priority outside CCPR's vocabulary and outside any
        # priorityMap, set directly via the transport (bypassing any write-side guard).
        self.transport._require_issue(item["id"])["priority"] = "Urgentissimo"

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            fetched = self.backend.get(item["id"])

        self.assertEqual(fetched["priority"], "Urgentissimo")
        self.assertIn("Urgentissimo", captured_stderr.getvalue())


class YouTrackUnknownFilterValueTest(unittest.TestCase):
    """An issue's State or Priority custom field can carry a value outside CCPR's
    closed vocabulary (see YouTrackStateOutsideVocabularyTest above for State;
    Priority's own bundle is equally unconstrained -- `_unmap_priority` has the same
    identity-fallback shape as `_unmap_state`). `list --status`/`--priority` must
    stay able to find such an item, with a stderr warning so a caller's plain typo in
    the filter value doesn't produce the same silent `[]` a genuine "no match" would."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_list_by_status_finds_the_out_of_vocabulary_state_with_a_warning(self):
        item = self.backend.create(title="New feature")
        self.transport._require_issue(item["id"])["state"] = "Under Review"

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            items = self.backend.list(status="Under Review")

        self.assertEqual([i["id"] for i in items], [item["id"]])
        self.assertIn("Under Review", captured_stderr.getvalue())

    def test_list_by_priority_finds_the_out_of_vocabulary_priority_with_a_warning(self):
        item = self.backend.create(title="New feature")
        self.transport._require_issue(item["id"])["priority"] = "Urgentissimo"

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            items = self.backend.list(priority="Urgentissimo")

        self.assertEqual([i["id"] for i in items], [item["id"]])
        self.assertIn("Urgentissimo", captured_stderr.getvalue())


class YouTrackResolveProjectIdTest(unittest.TestCase):
    """_resolve_project_id() calls GET /api/admin/projects, which requires an
    admin-scoped token -- a minimally-scoped token (a common real-world setup)
    may lack it. These tests cover both failure branches: shortName genuinely
    not found (coverage-add; the existing "not found" branch already worked
    correctly, no bug there), and the admin-projects call itself being
    forbidden (the actual gap: the raw 403 propagated without any indication
    of WHY, and a real token misconfiguration would look identical to a wrong
    project name)."""

    def test_project_short_name_not_found_raises_clear_error(self):
        transport = FakeYouTrackTransport(project_short_name="OTHERPROJECT")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="DOES-NOT-EXIST",
            token="fake-token", transport=transport,
        )

        with self.assertRaises(WorkItemError):
            backend.create(title="New feature")

    def test_admin_projects_permission_error_is_reported_clearly(self):
        class ForbiddenTransport:
            def request(self, method, url, token, body=None):
                if "/api/admin/projects" in url:
                    raise WorkItemError(
                        "YouTrack API error 403 for GET .../api/admin/projects: forbidden"
                    )
                raise AssertionError("should not reach further requests")

        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=ForbiddenTransport(),
        )

        with self.assertRaises(WorkItemError) as ctx:
            backend.create(title="New feature")
        self.assertIn("project-read permission", str(ctx.exception))


class YouTrackAppendResultTest(unittest.TestCase):
    """append-result adds a comment; get/list must recognise ONLY comments carrying
    the result marker as result-link entries — an ordinary human comment on the
    issue must not be mistaken for one (ADR-0003 doesn't specify a disambiguation
    mechanism; this is this implementation's resolution of that gap)."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_ordinary_comment_is_not_treated_as_a_result_link(self):
        item = self.backend.create(title="New feature")
        # Simulate a human leaving an unrelated comment directly via the transport.
        self.transport._require_issue(item["id"])["comments"].append(
            {"text": "Looks good, one nit though."}
        )

        self.backend.append_result(item["id"], "https://example.org/pr/1")
        fetched = self.backend.get(item["id"])

        self.assertEqual(fetched["result-link"], ["https://example.org/pr/1"])

    def test_human_comment_that_happens_to_start_with_the_word_result_is_not_picked_up(self):
        # A human writing prose ("Result: I don't think this fixed it...") must not be
        # mistaken for a result reference — this is exactly why an English prefix isn't
        # a safe marker; only a marker a human would never type naturally qualifies.
        item = self.backend.create(title="New feature")
        self.transport._require_issue(item["id"])["comments"].append(
            {"text": "Result: I don't think this fixed it, reverting."}
        )

        fetched = self.backend.get(item["id"])

        self.assertEqual(fetched["result-link"], [])


class YouTrackMalformedHeartbeatTest(unittest.TestCase):
    """runner:/heartbeat: tags are editable in the YouTrack UI -- a human (or a
    fat-fingered API call) can leave a heartbeat tag that doesn't match the expected
    compact-timestamp format. That must degrade to "no valid heartbeat" (best-effort:
    the item is then simply not considered live), never a raw crash past the CLI
    boundary's `except WorkItemError`."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_get_does_not_crash_on_a_malformed_heartbeat_tag(self):
        item = self.backend.create(title="New feature")
        self.transport._require_issue(item["id"])["tags"].append("heartbeat:not-a-real-timestamp")

        fetched = self.backend.get(item["id"])

        self.assertIsNone(fetched["heartbeat"])

    def test_claim_does_not_crash_on_a_malformed_heartbeat_tag(self):
        item = self.backend.create(title="New feature")
        self.transport._require_issue(item["id"])["tags"].append("runner:agent-1")
        self.transport._require_issue(item["id"])["tags"].append("heartbeat:not-a-real-timestamp")
        self.backend.set_status(item["id"], "In Progress")

        # A malformed heartbeat is never "live" -- treated as stale, so a different
        # runner claiming it must be ALLOWED, not crash and not be refused.
        claimed = self.backend.claim(item["id"], runner="agent-2")

        self.assertEqual(claimed["runner"], "agent-2")


FIXED_NOW = datetime.datetime(2026, 7, 8, 16, 0, 0, tzinfo=datetime.timezone.utc)


class _MutableClock:
    """A settable clock for tests that need to simulate time passing between a
    claim and a later liveness check, without a real sleep()."""

    def __init__(self, initial):
        self.current = initial

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += datetime.timedelta(seconds=seconds)


class YouTrackClaimingTest(unittest.TestCase):
    """Claiming is MANDATORY for remote backends (ADR-0002 SS6, ADR-0005): claim()
    records the runner:<id> signal + a heartbeat timestamp and sets In Progress."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.clock = _MutableClock(FIXED_NOW)
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
            clock=self.clock, stale_after_seconds=3600,
        )

    def test_claim_with_runner_sets_runner_heartbeat_and_in_progress(self):
        item = self.backend.create(title="New feature")

        claimed = self.backend.claim(item["id"], runner="agent-1")

        self.assertEqual(claimed["runner"], "agent-1")
        self.assertEqual(claimed["heartbeat"], FIXED_NOW.isoformat())
        self.assertEqual(claimed["status"], "In Progress")
        # Persisted, not just returned in-memory.
        fetched = self.backend.get(item["id"])
        self.assertEqual(fetched["runner"], "agent-1")
        self.assertEqual(fetched["heartbeat"], FIXED_NOW.isoformat())

    def test_claim_refuses_takeover_of_a_live_claim_by_different_runner(self):
        item = self.backend.create(title="New feature")
        self.backend.claim(item["id"], runner="agent-1")

        self.clock.advance(600)  # 10 minutes later -- well within the 1h staleAfter

        with self.assertRaises(WorkItemError):
            self.backend.claim(item["id"], runner="agent-2")

        fetched = self.backend.get(item["id"])
        self.assertEqual(fetched["runner"], "agent-1")

    def test_a_refused_takeover_leaves_owner_unchanged(self):
        item = self.backend.create(title="New feature", owner="alice")
        self.backend.claim(item["id"], runner="agent-1")

        self.clock.advance(600)  # still live -- this claim attempt must be refused

        with self.assertRaises(WorkItemError):
            self.backend.claim(item["id"], owner="bob", runner="agent-2")

        fetched = self.backend.get(item["id"])
        self.assertEqual(fetched["owner"], "alice")
        self.assertEqual(fetched["runner"], "agent-1")

    def test_a_refused_claim_on_a_done_item_leaves_owner_unchanged(self):
        item = self.backend.create(title="New feature", owner="alice")
        self.backend.set_status(item["id"], "Done")

        with self.assertRaises(WorkItemError):
            self.backend.claim(item["id"], owner="bob", runner="agent-1")

        fetched = self.backend.get(item["id"])
        self.assertEqual(fetched["owner"], "alice")

    def test_claim_allows_takeover_of_a_stale_claim(self):
        item = self.backend.create(title="New feature")
        self.backend.claim(item["id"], runner="agent-1")

        self.clock.advance(7200)  # 2 hours later -- past the 1h staleAfter

        claimed = self.backend.claim(item["id"], runner="agent-2")

        self.assertEqual(claimed["runner"], "agent-2")
        fetched = self.backend.get(item["id"])
        self.assertEqual(fetched["runner"], "agent-2")

    def test_claim_by_the_same_runner_again_is_allowed_and_refreshes(self):
        item = self.backend.create(title="New feature")
        self.backend.claim(item["id"], runner="agent-1")

        self.clock.advance(600)
        claimed = self.backend.claim(item["id"], runner="agent-1")

        self.assertEqual(claimed["runner"], "agent-1")
        self.assertEqual(claimed["heartbeat"], self.clock().isoformat())

    def test_heartbeat_refreshes_the_timestamp(self):
        item = self.backend.create(title="New feature")
        self.backend.claim(item["id"], runner="agent-1")

        self.clock.advance(600)
        result = self.backend.heartbeat(item["id"], runner="agent-1")

        self.assertEqual(result["heartbeat"], self.clock().isoformat())
        self.assertEqual(result["runner"], "agent-1")
        fetched = self.backend.get(item["id"])
        self.assertEqual(fetched["heartbeat"], self.clock().isoformat())

    def test_heartbeat_refuses_for_a_different_runner(self):
        item = self.backend.create(title="New feature")
        self.backend.claim(item["id"], runner="agent-1")

        with self.assertRaises(WorkItemError):
            self.backend.heartbeat(item["id"], runner="agent-2")

    def test_resume_a_parked_item(self):
        item = self.backend.create(title="New feature")
        self.backend.claim(item["id"], runner="agent-1")
        self.backend.set_status(item["id"], "Parked")

        self.clock.advance(600)
        resumed = self.backend.claim(item["id"], runner="agent-2")

        self.assertEqual(resumed["status"], "In Progress")
        self.assertEqual(resumed["runner"], "agent-2")

    def test_claim_refuses_a_done_item(self):
        item = self.backend.create(title="New feature")
        self.backend.set_status(item["id"], "Done")

        with self.assertRaises(WorkItemError):
            self.backend.claim(item["id"], runner="agent-1")

    def test_claim_refuses_a_cancelled_item(self):
        item = self.backend.create(title="New feature")
        self.backend.set_status(item["id"], "Cancelled")

        with self.assertRaises(WorkItemError):
            self.backend.claim(item["id"], runner="agent-1")

    def test_claim_allows_a_waiting_for_approval_item(self):
        item = self.backend.create(title="New feature")
        self.backend.set_status(item["id"], "Waiting for Approval")

        claimed = self.backend.claim(item["id"], runner="agent-1")

        self.assertEqual(claimed["status"], "In Progress")
        self.assertEqual(claimed["runner"], "agent-1")

    def test_a_non_utc_aware_clock_is_normalized_to_utc_in_the_written_heartbeat(self):
        # 18:00 at UTC+2 is 16:00 UTC. strftime() on an aware datetime formats the
        # WALL-CLOCK fields verbatim, ignoring the offset -- writing the heartbeat
        # tag without normalizing to UTC first would literally record "18:00" as if
        # it were UTC, two hours off from the true instant.
        non_utc_now = datetime.datetime(
            2026, 7, 8, 18, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=2)),
        )
        transport = FakeYouTrackTransport(project_short_name="TEST")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            clock=lambda: non_utc_now, stale_after_seconds=3600,
        )
        item = backend.create(title="New feature")

        claimed = backend.claim(item["id"], runner="agent-1")

        self.assertEqual(claimed["heartbeat"], "2026-07-08T16:00:00+00:00")


class YouTrackSweepIntegrationTest(unittest.TestCase):
    """sweep() was tested in isolation (test_sweep.py) against a minimal fake
    backend, decoupled from any one backend's representation. This proves sweep()
    correctly interprets the REAL YouTrackBackend's tag-based runner/heartbeat --
    the two modules actually interoperate, not just each in isolation."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.clock = _MutableClock(FIXED_NOW)
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
            clock=self.clock, stale_after_seconds=3600,
        )

    def test_stale_claim_with_branch_commits_is_parked(self):
        item = self.backend.create(title="New feature")
        self.backend.claim(item["id"], runner="agent-1")
        self.clock.advance(7200)  # 2 hours -- past the 1h staleAfter

        report = sweep.sweep(
            self.backend, clock=self.clock,
            has_branch_commits=lambda item_id: True, stale_after_seconds=3600,
        )

        self.assertEqual(report["parked"], [item["id"]])
        self.assertEqual(self.backend.get(item["id"])["status"], "Parked")

    def test_stale_claim_without_branch_commits_is_left_in_progress(self):
        item = self.backend.create(title="New feature")
        self.backend.claim(item["id"], runner="agent-1")
        self.clock.advance(7200)

        report = sweep.sweep(
            self.backend, clock=self.clock,
            has_branch_commits=lambda item_id: False, stale_after_seconds=3600,
        )

        self.assertEqual(report["parked"], [])
        self.assertEqual(report["left_in_progress"], [item["id"]])
        self.assertEqual(self.backend.get(item["id"])["status"], "In Progress")


class YouTrackCreateFactoryTest(unittest.TestCase):
    """create(config) — the factory the CLI dispatcher calls — validates its own
    config and never reads the token from settings.json (ADR-0002 §3)."""

    def test_missing_required_config_keys_raises(self):
        with self.assertRaises(WorkItemError):
            youtrack.create({})

    def test_missing_token_env_var_raises(self):
        config = {"baseUrl": "https://faketrack.example.org", "project": "TEST",
                   "tokenEnv": "CCPR_TEST_YOUTRACK_TOKEN_DOES_NOT_EXIST"}
        os.environ.pop("CCPR_TEST_YOUTRACK_TOKEN_DOES_NOT_EXIST", None)

        with self.assertRaises(WorkItemError):
            youtrack.create(config)

    def test_happy_path_reads_token_from_environment_not_config(self):
        env_var = "CCPR_TEST_YOUTRACK_TOKEN"
        os.environ[env_var] = "secret-value"
        self.addCleanup(os.environ.pop, env_var, None)
        config = {"baseUrl": "https://faketrack.example.org", "project": "TEST", "tokenEnv": env_var}

        backend = youtrack.create(config)

        self.assertEqual(backend.token, "secret-value")
        self.assertNotIn("secret-value", repr(config))

    def _write_token_file(self, contents):
        fd, path = tempfile.mkstemp(prefix="ccpr-youtrack-token-")
        with os.fdopen(fd, "w") as handle:
            handle.write(contents)
        self.addCleanup(os.remove, path)
        return path

    def test_env_wins_over_token_file_when_both_are_set(self):
        env_var = "CCPR_TEST_YOUTRACK_TOKEN_ENV_WINS"
        os.environ[env_var] = "env-secret"
        self.addCleanup(os.environ.pop, env_var, None)
        token_file = self._write_token_file("file-secret\n")
        config = {
            "baseUrl": "https://faketrack.example.org", "project": "TEST",
            "tokenEnv": env_var, "tokenFile": token_file,
        }

        backend = youtrack.create(config)

        self.assertEqual(backend.token, "env-secret")

    def test_token_file_used_when_env_var_is_not_set(self):
        env_var = "CCPR_TEST_YOUTRACK_TOKEN_FILE_FALLBACK"
        os.environ.pop(env_var, None)
        token_file = self._write_token_file("file-secret\n")
        config = {
            "baseUrl": "https://faketrack.example.org", "project": "TEST",
            "tokenEnv": env_var, "tokenFile": token_file,
        }

        backend = youtrack.create(config)

        self.assertEqual(backend.token, "file-secret")

    def test_token_file_used_when_env_var_is_set_but_empty(self):
        env_var = "CCPR_TEST_YOUTRACK_TOKEN_FILE_EMPTY_ENV"
        os.environ[env_var] = ""
        self.addCleanup(os.environ.pop, env_var, None)
        token_file = self._write_token_file("file-secret\n")
        config = {
            "baseUrl": "https://faketrack.example.org", "project": "TEST",
            "tokenEnv": env_var, "tokenFile": token_file,
        }

        backend = youtrack.create(config)

        self.assertEqual(backend.token, "file-secret")

    def test_token_file_supports_tilde_expansion(self):
        token_file = self._write_token_file("file-secret\n")
        home = os.path.dirname(token_file)
        relative_to_home = os.path.basename(token_file)
        config = {
            "baseUrl": "https://faketrack.example.org", "project": "TEST",
            "tokenFile": os.path.join("~", relative_to_home),
        }

        with mock.patch.dict(os.environ, {"HOME": home}):
            backend = youtrack.create(config)

        self.assertEqual(backend.token, "file-secret")

    def test_missing_token_env_and_token_file_raises_naming_both_options(self):
        config = {"baseUrl": "https://faketrack.example.org", "project": "TEST"}

        with self.assertRaises(WorkItemError) as ctx:
            youtrack.create(config)

        message = str(ctx.exception)
        self.assertIn("tokenEnv", message)
        self.assertIn("tokenFile", message)

    def test_missing_token_env_key_is_not_reported_when_token_file_is_present(self):
        token_file = self._write_token_file("file-secret\n")
        config = {
            "baseUrl": "https://faketrack.example.org", "project": "TEST",
            "tokenFile": token_file,
        }

        backend = youtrack.create(config)

        self.assertEqual(backend.token, "file-secret")

    def test_token_file_configured_but_missing_raises_naming_the_path(self):
        missing_path = os.path.join(tempfile.gettempdir(), "ccpr-youtrack-token-does-not-exist")
        config = {
            "baseUrl": "https://faketrack.example.org", "project": "TEST",
            "tokenFile": missing_path,
        }

        with self.assertRaises(WorkItemError) as ctx:
            youtrack.create(config)

        self.assertIn(missing_path, str(ctx.exception))

    def test_token_file_configured_but_empty_raises(self):
        token_file = self._write_token_file("   \n")
        config = {
            "baseUrl": "https://faketrack.example.org", "project": "TEST",
            "tokenFile": token_file,
        }

        with self.assertRaises(WorkItemError):
            youtrack.create(config)

    def test_env_token_with_trailing_newline_is_stripped(self):
        env_var = "CCPR_TEST_YOUTRACK_TOKEN_TRAILING_NEWLINE"
        os.environ[env_var] = "env-secret\n"
        self.addCleanup(os.environ.pop, env_var, None)
        config = {
            "baseUrl": "https://faketrack.example.org", "project": "TEST",
            "tokenEnv": env_var,
        }

        backend = youtrack.create(config)

        self.assertEqual(backend.token, "env-secret")

    def test_whitespace_only_token_env_and_token_file_raises_naming_both_options(self):
        config = {
            "baseUrl": "https://faketrack.example.org", "project": "TEST",
            "tokenEnv": "   ",
        }

        with self.assertRaises(WorkItemError) as ctx:
            youtrack.create(config)

        message = str(ctx.exception)
        self.assertIn("tokenEnv", message)
        self.assertIn("tokenFile", message)

    def test_token_file_does_not_expand_environment_variables(self):
        token_file = self._write_token_file("file-secret\n")
        env_var = "CCPR_TEST_YOUTRACK_TOKEN_FILE_EXPANDVARS"
        os.environ[env_var] = "should-not-be-expanded"
        self.addCleanup(os.environ.pop, env_var, None)
        config = {
            "baseUrl": "https://faketrack.example.org", "project": "TEST",
            "tokenFile": f"${env_var}",
        }

        with self.assertRaises(WorkItemError) as ctx:
            youtrack.create(config)

        self.assertIn(f"${env_var}", str(ctx.exception))


class YouTrackTagsTest(unittest.TestCase):
    """Tags beyond the backend-neutral contract suite: the reserved runner:/
    heartbeat: namespace must never leak into the user-facing `tags` field, and
    add-tag/remove-tag check the current tag list before sending a Command API call
    so a redundant call is skipped rather than relying on the API's own idempotence
    (ADR-0002 2nd addendum, 09.07.2026)."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_runner_and_heartbeat_tags_never_leak_into_the_tags_field(self):
        item = self.backend.create(title="New feature")
        self.backend.claim(item["id"], runner="agent-1")

        fetched = self.backend.get(item["id"])

        self.assertEqual(fetched["tags"], [])

    def test_add_tag_sends_the_command_only_once_when_already_present(self):
        item = self.backend.create(title="New feature")
        self.backend.add_tag(item["id"], "security")

        self.backend.add_tag(item["id"], "security")

        self.assertEqual(
            [c for c in self.transport.commands_received if c == "tag security"],
            ["tag security"],
        )

    def test_remove_tag_sends_no_command_when_already_absent(self):
        item = self.backend.create(title="New feature")

        self.backend.remove_tag(item["id"], "security")

        self.assertNotIn("remove tag security", self.transport.commands_received)


class YouTrackTagVisibilityTest(unittest.TestCase):
    """A tag `add_tag`/`create(tags=...)` creates via the Command API is owned by
    the executing identity and PRIVATE to it by default (measured against a live
    instance) -- workitems.youtrack.tagVisibilityGroup names a group a fresh tag
    should be made visible to instead (standing PO rule: every tag is visible to
    all users). See youtrack.py's _ensure_tag_visibility for the full design."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
            tag_visibility_group="All Users",
        )

    def test_add_tag_on_a_new_tag_makes_it_visible_to_the_configured_group(self):
        item = self.backend.create(title="New feature")

        self.backend.add_tag(item["id"], "security")

        tag = self.transport._tags["security"]
        # Read the state back through the fake's OWN GET path (not the in-memory
        # dict directly) -- the assertion this AC actually needs is "the read-back
        # shows the group", not "the set call returned something".
        readback = self.transport.request(
            "GET", f"https://faketrack.example.org/api/tags/{tag['id']}", "fake-token",
        )
        self.assertEqual(readback["visibleFor"], {"id": "102-0", "name": "All Users"})

    def test_add_tag_on_an_existing_tag_does_not_re_create_it(self):
        # Simulates one of the 8/20 tags measured already correctly shared on the
        # live instance -- add_tag must not touch it (no re-create, no re-set):
        # a write with no statement, per _ensure_tag_visibility's own docstring.
        self.transport._ensure_tag_registered("already-shared")
        self.transport._set_tag_visibility(
            self.transport._tags["already-shared"]["id"],
            {"visibleFor": {"id": "102-0"}, "updateableBy": {"id": "102-0"}},
        )
        item = self.backend.create(title="New feature")

        self.backend.add_tag(item["id"], "already-shared")

        self.assertEqual(self.transport.explicit_tag_creation_calls, [])
        self.assertEqual(
            self.transport._tags["already-shared"]["visibleFor"], {"id": "102-0", "name": "All Users"},
        )

    def test_add_tag_on_an_existing_but_private_tag_leaves_it_private(self):
        # A tag that already exists but is PRIVATE (12/20 on the probed instance)
        # is a DIFFERENT decision this method does not make -- see the class
        # docstring. Confirms add_tag does not "fix" it along the way.
        self.transport._ensure_tag_registered("already-private")
        item = self.backend.create(title="New feature")

        self.backend.add_tag(item["id"], "already-private")

        self.assertEqual(self.transport.explicit_tag_creation_calls, [])
        self.assertIsNone(self.transport._tags["already-private"]["visibleFor"])


class YouTrackTagVisibilityGroupNotConfiguredTest(unittest.TestCase):
    """workitems.youtrack.tagVisibilityGroup absent must not silently create a
    private tag -- that's the exact silent shape this feature exists to close
    (PO decision, on the record). The tag still gets applied (refusing
    visibility must not refuse the tag itself); the missing key is named in a
    stderr warning instead."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
            # tag_visibility_group intentionally omitted.
        )

    def test_missing_config_key_warns_and_still_applies_the_tag(self):
        item = self.backend.create(title="New feature")

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            fetched = self.backend.add_tag(item["id"], "security")

        self.assertIn("workitems.youtrack.tagVisibilityGroup", captured_stderr.getvalue())
        self.assertIn("security", fetched["tags"])
        self.assertEqual(self.transport.explicit_tag_creation_calls, [])

    def test_a_second_call_for_the_same_tag_name_does_not_warn_again(self):
        """_known_tag_names's own docstring claims a tag this method warned
        about "is never mistaken for missing a second time" -- nothing
        proved that before this test: dropping the cache-add from this warn
        branch would make a real 259-assignment/35-distinct-tag migration
        print 259 warnings instead of 35, and every EXISTING test here
        (which only ever calls add_tag once) would stay green regardless.
        Counts the warning LINES, not a substring -- the warning message
        itself mentions "workitems.youtrack.tagVisibilityGroup" twice, so an
        assertIn/count on that substring would overcount a single warning
        as two."""
        first_item = self.backend.create(title="First feature")
        second_item = self.backend.create(title="Second feature")

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            self.backend.add_tag(first_item["id"], "security")
            self.backend.add_tag(second_item["id"], "security")

        warning_lines = [line for line in captured_stderr.getvalue().splitlines() if line]
        self.assertEqual(len(warning_lines), 1)


class YouTrackTagVisibilityGroupNotFoundTest(unittest.TestCase):
    """The configured group name doesn't match any group on this instance --
    reported, not waved through: the tag still gets applied (same as a missing
    config key), but with its default (private) visibility, and the warning
    names the group that couldn't be found."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
            tag_visibility_group="Team Atlantis",
        )

    def test_group_not_found_warns_by_name_and_still_applies_the_tag(self):
        item = self.backend.create(title="New feature")

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            fetched = self.backend.add_tag(item["id"], "security")

        self.assertIn("Team Atlantis", captured_stderr.getvalue())
        self.assertIn("security", fetched["tags"])
        self.assertEqual(self.transport.explicit_tag_creation_calls, [])

    def test_a_second_call_for_the_same_tag_name_does_not_warn_again(self):
        """Same discriminating-count proof as
        YouTrackTagVisibilityGroupNotConfiguredTest's own version -- this
        warn branch has its own, separate cache-add call."""
        first_item = self.backend.create(title="First feature")
        second_item = self.backend.create(title="Second feature")

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            self.backend.add_tag(first_item["id"], "security")
            self.backend.add_tag(second_item["id"], "security")

        warning_lines = [line for line in captured_stderr.getvalue().splitlines() if line]
        self.assertEqual(len(warning_lines), 1)


class YouTrackTagVisibilityGroupAmbiguousTest(unittest.TestCase):
    """Two groups sharing the configured name -- not observed on the probed live
    instance (every group name there, including "All Users", was unique), but
    nothing in the API rules it out for a different instance, so the guard is
    built and tested regardless (see _resolve_tag_visibility_group_id's own
    docstring). Refuses to guess which one, same reported-not-waved-through
    shape as a group that doesn't resolve at all."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(
            project_short_name="TEST",
            known_groups=[
                {"id": "100-1", "name": "Support"},
                {"id": "100-2", "name": "Support"},
            ],
        )
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
            tag_visibility_group="Support",
        )

    def test_ambiguous_group_warns_by_name_and_still_applies_the_tag(self):
        item = self.backend.create(title="New feature")

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            fetched = self.backend.add_tag(item["id"], "security")

        self.assertIn("Support", captured_stderr.getvalue())
        self.assertIn("security", fetched["tags"])
        self.assertEqual(self.transport.explicit_tag_creation_calls, [])

    def test_a_second_call_for_the_same_tag_name_does_not_warn_again(self):
        """Same discriminating-count proof as
        YouTrackTagVisibilityGroupNotConfiguredTest's own version -- this
        warn branch (group unresolved, shared by "not found" and
        "ambiguous") has its own, separate cache-add call."""
        first_item = self.backend.create(title="First feature")
        second_item = self.backend.create(title="Second feature")

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            self.backend.add_tag(first_item["id"], "security")
            self.backend.add_tag(second_item["id"], "security")

        warning_lines = [line for line in captured_stderr.getvalue().splitlines() if line]
        self.assertEqual(len(warning_lines), 1)


class YouTrackTagVisibilityFailureTest(unittest.TestCase):
    """A set call that RETURNED is not evidence -- only the read-back is (PO
    instruction, on the record). Both ways the instance can lie about a
    visibility write: the set call itself gets rejected outright, or it
    reports success but the read-back shows the value didn't actually take."""

    def test_readback_mismatch_after_set_is_a_failure_not_a_success(self):
        transport = FakeYouTrackTransport(
            project_short_name="TEST", corrupt_tag_visibility_readback=True,
        )
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            tag_visibility_group="All Users",
        )
        item = backend.create(title="New feature")

        with self.assertRaises(WorkItemError):
            backend.add_tag(item["id"], "security")

        # The ordering (_ensure_tag_visibility before the Command API's
        # `tag <name>`) is correct today -- but only asserting the raise
        # (as this test did before) would stay green even if that ordering
        # were ever reversed, leaving the issue tagged after the caller saw
        # an exception. Assert the negative directly.
        fetched = backend.get(item["id"])
        self.assertNotIn("security", fetched["tags"])

    def test_rejected_visibility_set_call_raises(self):
        transport = FakeYouTrackTransport(project_short_name="TEST")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            tag_visibility_group="All Users",
        )
        item = backend.create(title="New feature")
        transport.fail_tag_visibility_set_at(0)

        with self.assertRaises(WorkItemError):
            backend.add_tag(item["id"], "security")

        fetched = backend.get(item["id"])
        self.assertNotIn("security", fetched["tags"])

    def test_readback_failure_after_successful_creation_does_not_retry_creation(self):
        """Code-review follow-up: POST /api/tags can succeed (the tag genuinely
        exists on the server now) while the visibility set/read-back that
        follows still fails -- the tag must not be re-created on a later call
        for the SAME name within the same backend-instance run (the exact
        batch scenario -- 259 assignments over 35 distinct tags -- this
        method's own cache exists to protect)."""
        # self.transport (not a bare local): explicit_tag_creation_calls'
        # expected value ["security"] follows entirely from this test's own
        # fixture (the tag name it chose to pass to add_tag), not from
        # anything measured in the repository -- ADR-0012 doesn't apply to it,
        # same as every other self.transport assertion in this file.
        self.transport = FakeYouTrackTransport(
            project_short_name="TEST", corrupt_tag_visibility_readback=True,
        )
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
            tag_visibility_group="All Users",
        )
        item = backend.create(title="New feature")

        with self.assertRaises(WorkItemError):
            backend.add_tag(item["id"], "security")
        # The tag now genuinely exists server-side (POST /api/tags succeeded
        # before the read-back check failed) -- a second call must not
        # re-issue POST /api/tags for the same name.
        fetched = backend.add_tag(item["id"], "security")

        self.assertEqual(self.transport.explicit_tag_creation_calls, ["security"])
        self.assertIn("security", fetched["tags"])

    def test_a_malformed_tag_creation_response_raises_workitemerror_not_keyerror(self):
        """Code-review follow-up: `created["id"]` was unguarded dict indexing --
        a 2xx response missing the expected "id" key (malformed/non-conformant
        server response) must surface as WorkItemError, matching every other
        boundary error in this backend, not a raw KeyError/TypeError."""
        transport = FakeYouTrackTransport(
            project_short_name="TEST", corrupt_tag_creation_response=True,
        )
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            tag_visibility_group="All Users",
        )
        item = backend.create(title="New feature")

        with self.assertRaises(WorkItemError):
            backend.add_tag(item["id"], "security")


class YouTrackCreateTagVisibilityTest(unittest.TestCase):
    """create(..., tags=[...])'s best-effort tag loop is the OTHER entry point
    that must ensure tag visibility before applying a tag -- add_tag is not the
    only caller that can create a fresh tag."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
            tag_visibility_group="All Users",
        )

    def test_create_with_a_new_tag_makes_it_visible_to_the_configured_group(self):
        item = self.backend.create(title="New feature", tags=["security"])

        tag = self.transport._tags["security"]
        readback = self.transport.request(
            "GET", f"https://faketrack.example.org/api/tags/{tag['id']}", "fake-token",
        )
        self.assertEqual(readback["visibleFor"], {"id": "102-0", "name": "All Users"})
        self.assertIn("security", item["tags"])

    def test_create_visibility_failure_still_leaves_no_orphan(self):
        """Same "must not fail an already-committed create()" rule as the
        existing type/owner/tag best-effort handling: a visibility failure
        (here, a rejected set call) is reported on stderr and swallowed, not
        allowed to raise out of create() -- the issue already exists by the
        time tags are applied."""
        self.transport.fail_tag_visibility_set_at(0)

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            item = self.backend.create(title="New feature", tags=["security"])

        self.assertEqual(len(self.transport._issues), 1)
        self.assertIn("security", item["tags"])
        self.assertIn("security", captured_stderr.getvalue())


class YouTrackCreateTagVisibilityOutcomesTest(unittest.TestCase):
    """create()'s own return value cannot grow a "why wasn't this tag's
    visibility set" field without changing the six-op contract's shape (PO
    decision: migrate.py's report must carry this, but not by widening
    create()'s return). last_create_tag_visibility_outcomes() is the side
    channel migrate.py reads immediately after calling create() -- reset at
    the start of every create() call, so it only ever reflects the MOST
    RECENT call."""

    def test_no_tags_means_no_outcomes(self):
        transport = FakeYouTrackTransport(project_short_name="TEST")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
        )

        backend.create(title="New feature")

        self.assertEqual(backend.last_create_tag_visibility_outcomes(), [])

    def test_a_successfully_shared_tag_produces_no_outcome(self):
        transport = FakeYouTrackTransport(project_short_name="TEST")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            tag_visibility_group="All Users",
        )

        backend.create(title="New feature", tags=["security"])

        self.assertEqual(backend.last_create_tag_visibility_outcomes(), [])

    def test_unconfigured_group_key_is_reported_as_not_configured(self):
        transport = FakeYouTrackTransport(project_short_name="TEST")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            # tag_visibility_group intentionally omitted.
        )

        with contextlib.redirect_stderr(io.StringIO()):
            backend.create(title="New feature", tags=["security"])

        self.assertEqual(
            backend.last_create_tag_visibility_outcomes(),
            [{"tag": "security", "reason": youtrack.TAG_VISIBILITY_NOT_CONFIGURED}],
        )

    def test_group_not_found_is_reported_as_group_not_found(self):
        transport = FakeYouTrackTransport(project_short_name="TEST")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            tag_visibility_group="Team Atlantis",
        )

        with contextlib.redirect_stderr(io.StringIO()):
            backend.create(title="New feature", tags=["security"])

        self.assertEqual(
            backend.last_create_tag_visibility_outcomes(),
            [{"tag": "security", "reason": youtrack.TAG_VISIBILITY_GROUP_NOT_FOUND}],
        )

    def test_ambiguous_group_is_reported_as_group_ambiguous(self):
        transport = FakeYouTrackTransport(
            project_short_name="TEST",
            known_groups=[
                {"id": "100-1", "name": "Support"},
                {"id": "100-2", "name": "Support"},
            ],
        )
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            tag_visibility_group="Support",
        )

        with contextlib.redirect_stderr(io.StringIO()):
            backend.create(title="New feature", tags=["security"])

        self.assertEqual(
            backend.last_create_tag_visibility_outcomes(),
            [{"tag": "security", "reason": youtrack.TAG_VISIBILITY_GROUP_AMBIGUOUS}],
        )

    def test_outcomes_do_not_leak_across_create_calls(self):
        transport = FakeYouTrackTransport(project_short_name="TEST")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            # tag_visibility_group intentionally omitted.
        )

        with contextlib.redirect_stderr(io.StringIO()):
            backend.create(title="First feature", tags=["alpha"])
            backend.create(title="Second feature", tags=["beta"])

        # Only the SECOND call's own outcome -- "alpha" (first call) must
        # not still be sitting in the list.
        self.assertEqual(
            backend.last_create_tag_visibility_outcomes(),
            [{"tag": "beta", "reason": youtrack.TAG_VISIBILITY_NOT_CONFIGURED}],
        )

    def test_a_tag_already_known_to_the_instance_produces_no_outcome(self):
        """A tag that already exists is left untouched entirely (see
        _ensure_tag_visibility's own docstring) -- visibility was never
        attempted for it, so it must not appear as a "not set" outcome
        either, even with the config key unset."""
        transport = FakeYouTrackTransport(project_short_name="TEST")
        transport._ensure_tag_registered("already-shared")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            # tag_visibility_group intentionally omitted.
        )

        with contextlib.redirect_stderr(io.StringIO()):
            backend.create(title="New feature", tags=["already-shared"])

        self.assertEqual(backend.last_create_tag_visibility_outcomes(), [])

    def test_a_rejected_visibility_write_is_reported_as_write_rejected(self):
        """The fourth way a tag ends up without confirmed visibility (PO
        decision, 02.09.2026): unlike the three config-shaped reasons above,
        this one is a genuine instance failure -- _ensure_tag_visibility
        RAISES rather than returning a reason string, and create()'s
        best-effort tag loop (_apply_tag_with_visibility) must turn that
        raise into its own outcome instead of only printing to stderr."""
        transport = FakeYouTrackTransport(project_short_name="TEST")
        transport.fail_tag_visibility_set_at(0)
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            tag_visibility_group="All Users",
        )

        with contextlib.redirect_stderr(io.StringIO()):
            item = backend.create(title="New feature", tags=["security"])

        outcomes = backend.last_create_tag_visibility_outcomes()
        # Same list-of-dict shape as the three existing reasons' own tests
        # above -- "message" compared separately (assertIn), since its exact
        # text is the fake transport's own wording, not this backend's.
        self.assertEqual(
            [{"tag": o["tag"], "reason": o["reason"]} for o in outcomes],
            [{"tag": "security", "reason": youtrack.TAG_VISIBILITY_WRITE_REJECTED}],
        )
        self.assertIn("rejected", outcomes[0]["message"])
        # Same best-effort guarantee as the three existing reasons: the tag
        # is still applied to the item, just without confirmed visibility.
        self.assertIn("security", item["tags"])

    def test_a_readback_mismatch_is_reported_as_write_rejected(self):
        """Same reason as a rejected set call -- a read-back mismatch is the
        failure mode the read-back exists to catch in the first place, not a
        fifth category."""
        transport = FakeYouTrackTransport(
            project_short_name="TEST", corrupt_tag_visibility_readback=True,
        )
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            tag_visibility_group="All Users",
        )

        with contextlib.redirect_stderr(io.StringIO()):
            item = backend.create(title="New feature", tags=["security"])

        outcomes = backend.last_create_tag_visibility_outcomes()
        self.assertEqual(
            [{"tag": o["tag"], "reason": o["reason"]} for o in outcomes],
            [{"tag": "security", "reason": youtrack.TAG_VISIBILITY_WRITE_REJECTED}],
        )
        self.assertIn("read-back", outcomes[0]["message"])
        self.assertIn("security", item["tags"])


class FakeYouTrackTransportTagCreationHonestyTest(unittest.TestCase):
    """FakeYouTrackTransport must not accept anything the live instance
    forbids (code-review finding, measured live 02.09.2026): a fresh
    POST /api/tags for a name is created (visibleFor: null); a SECOND
    POST /api/tags for the SAME name is REJECTED (HTTP 400
    invalid_properties), and the tag count for that name stays at one --
    it is not silently treated as "already exists, here it is again". No
    production code path currently issues a second POST for the same name
    (_ensure_tag_visibility's own cache add happens before this could ever
    be reached -- see youtrack.py), so this exercises the transport's
    request() dispatch directly, the same way the read-back assertions
    elsewhere in this file do."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")

    def _post_tag(self, name):
        return self.transport.request(
            "POST", "https://faketrack.example.org/api/tags", "fake-token",
            body={"name": name},
        )

    def test_first_post_for_a_name_creates_a_private_tag(self):
        created = self._post_tag("security")

        self.assertEqual(created["visibleFor"], None)
        self.assertEqual(self.transport.explicit_tag_creation_calls, ["security"])

    def test_second_post_for_the_same_name_is_rejected_not_returned(self):
        self._post_tag("security")

        with self.assertRaises(WorkItemError):
            self._post_tag("security")

        # Rejected, not silently duplicated: still exactly one tag named
        # "security", and the rejected call never reached the registry.
        matching = [t for t in self.transport._tags.values() if t["name"] == "security"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(self.transport.explicit_tag_creation_calls, ["security"])


class YouTrackQueryTest(unittest.TestCase):
    """`--query` is a project-scoped passthrough to YouTrack's own query language
    (ADR-0002 2nd addendum, 09.07.2026): the `project: <PROJ> ` prefix is always
    applied, so a query can never leak results from another project the token
    happens to have read access to."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_query_is_scoped_to_the_configured_project(self):
        self.backend.create(title="New feature")

        self.backend.list(query="Sprint: 4")

        self.assertEqual(self.transport.list_queries_received[-1], "project: TEST Sprint: 4")

    def test_list_without_query_still_scopes_to_the_project_only(self):
        self.backend.create(title="New feature")

        self.backend.list()

        self.assertEqual(self.transport.list_queries_received[-1], "project: TEST")

    def test_query_cannot_leak_results_from_a_different_project(self):
        """A caller-supplied query containing its own `project:` clause (joined with
        `or`) defeats the plain `f"project: {self.project} {query}"` textual prefix
        server-side -- the guarantee must not depend on the query string's boolean
        semantics, so the backend post-filters the result client-side instead."""
        own_item = self.backend.create(title="Own item")
        self.transport.seed_foreign_issue("OTHER-1", "OTHER", summary="Foreign item")

        items = self.backend.list(query="or project: OTHER")

        ids = [item["id"] for item in items]
        self.assertIn(own_item["id"], ids)
        self.assertNotIn("OTHER-1", ids)


class YouTrackPriorityMapTest(unittest.TestCase):
    """priorityMap lets a project whose Priority bundle doesn't name its values to
    match CCPR's four-value vocabulary supply a name->name mapping -- the same
    escape hatch stateMap already provides for status (ADR-0002 2nd addendum)."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST", token="fake-token",
            priority_map={"Critical": "Show-stopper"},
            transport=self.transport,
        )

    def test_set_priority_sends_the_mapped_project_priority_name(self):
        item = self.backend.create(title="New feature")

        self.backend.set_priority(item["id"], "Critical")

        self.assertIn("Priority Show-stopper", self.transport.commands_received)

    def test_get_reports_back_the_ccpr_vocabulary_name_not_the_project_name(self):
        item = self.backend.create(title="New feature")

        self.backend.set_priority(item["id"], "Critical")
        fetched = self.backend.get(item["id"])

        self.assertEqual(fetched["priority"], "Critical")


class YouTrackSetSprintHardFailTest(unittest.TestCase):
    """Unlike create()'s best-effort field handling, set-sprint is a dedicated call
    with nothing else to protect via atomicity -- it fails hard on an unmappable
    Sprint value, same as set_type (ADR-0002 2nd addendum)."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(
            project_short_name="TEST", known_sprints={"3", "4"},
        )
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_set_sprint_with_unknown_value_raises(self):
        item = self.backend.create(title="New feature")

        with self.assertRaises(WorkItemError):
            self.backend.set_sprint(item["id"], "99")

    def test_set_sprint_with_known_value_succeeds(self):
        item = self.backend.create(title="New feature")

        updated = self.backend.set_sprint(item["id"], "4")

        self.assertEqual(updated["sprint"], "4")


class YouTrackSetEstimateTest(unittest.TestCase):
    """estimateField has NO default (unlike stateMap/priorityMap/Sprint's fixed
    field name) -- set_estimate raises immediately, before any API call, when it
    isn't configured (ADR-0002 2nd addendum)."""

    def test_missing_estimate_field_config_raises_without_any_api_call(self):
        transport = FakeYouTrackTransport(project_short_name="TEST")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
        )
        item = backend.create(title="New feature")
        transport.commands_received.clear()

        with self.assertRaises(WorkItemError):
            backend.set_estimate(item["id"], 3)

        # No Command API call was made -- the config check happens before any
        # network access, not as a rejected-command failure.
        self.assertEqual(transport.commands_received, [])

    def test_configured_but_the_field_does_not_exist_on_the_project_raises(self):
        # Simulates a misconfigured estimateField name: the fake never recognises
        # the resulting command as an estimate write (estimate_field_name unset),
        # so it falls through to the generic link-command branch and fails there
        # (no such issue to link to) -- exercising the same "Command API rejects it"
        # hard-fail path set_type/set_sprint/set_priority already cover.
        transport = FakeYouTrackTransport(project_short_name="TEST")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            estimate_field="Story Points",
        )
        item = backend.create(title="New feature")

        with self.assertRaises(WorkItemError):
            backend.set_estimate(item["id"], 3)

    def test_scalar_estimate_is_not_confused_with_an_enum_shaped_field(self):
        """Regression test for the scalar-vs-Enum read distinction: estimate is read
        as a bare number, never via the value(name) shape the Enum fields use."""
        transport = FakeYouTrackTransport(
            project_short_name="TEST", estimate_field_name="Story Points",
        )
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            estimate_field="Story Points",
        )
        item = backend.create(title="New feature")

        updated = backend.set_estimate(item["id"], 5)

        self.assertEqual(updated["estimate"], 5)
        self.assertIsInstance(updated["estimate"], int)
        # The raw issue's customFields entry for "Story Points" carries a bare
        # scalar value, NOT a {"name": ...} dict like State/Type/Sprint/Priority.
        raw_issue = transport._require_issue(item["id"])
        rendered = transport._render_issue(raw_issue)
        story_points_field = next(
            f for f in rendered["customFields"] if f["name"] == "Story Points"
        )
        self.assertNotIsInstance(story_points_field["value"], dict)


class YouTrackEstimateMisconfigurationTest(unittest.TestCase):
    """A configured estimateField pointing at the WRONG kind of custom field (e.g. an
    Enum/bundle field misconfigured in place of a plain numeric one) comes back from
    YouTrack shaped like an Enum value (a dict), not a bare number. That must be
    visible -- a stderr warning, same as the state-outside-vocabulary case above --
    not silently swallowed into `estimate: None` (review follow-up, 09.07.2026)."""

    def setUp(self):
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=FakeYouTrackTransport(project_short_name="TEST"),
            estimate_field="Story Points",
        )

    def test_non_numeric_estimate_value_passes_through_with_a_stderr_warning(self):
        raw_issue = {
            "idReadable": "TEST-1",
            "summary": "Mismapped estimate",
            "description": "",
            "project": {"shortName": "TEST"},
            "customFields": [{"name": "Story Points", "value": {"name": "Large"}}],
            "comments": [],
            "tags": [],
            "links": [],
        }

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            item = self.backend._item_from_issue(raw_issue)

        self.assertIsNone(item["estimate"])
        self.assertIn("Story Points", captured_stderr.getvalue())


class YouTrackLinksDirectionTest(unittest.TestCase):
    """Direction normalization (ADR-0008, the load-bearing rule): a single shared
    link record reads differently depending on which linked issue you look from --
    this is youtrack-only (local has no cross-file direction concept to normalize)."""

    def setUp(self):
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

    def test_reading_the_target_side_of_a_depends_on_edge_shows_blocks(self):
        item = self.backend.create(title="Dependent")
        target = self.backend.create(title="Dependency")

        self.backend.add_link(item["id"], "depends-on", target["id"])

        blocked_side = self.backend.get(target["id"])
        self.assertIn({"type": "blocks", "target": item["id"]}, blocked_side["links"])

    def test_removing_a_depends_on_edge_removes_it_from_both_sides(self):
        item = self.backend.create(title="Dependent")
        target = self.backend.create(title="Dependency")
        self.backend.add_link(item["id"], "depends-on", target["id"])

        self.backend.remove_link(item["id"], "depends-on", target["id"])

        self.assertEqual(self.backend.get(item["id"])["links"], [])
        self.assertEqual(self.backend.get(target["id"])["links"], [])

    def test_relates_to_is_symmetric_from_both_sides(self):
        item = self.backend.create(title="A")
        other = self.backend.create(title="B")

        self.backend.add_link(item["id"], "relates-to", other["id"])

        self.assertIn(
            {"type": "relates-to", "target": other["id"]}, self.backend.get(item["id"])["links"],
        )
        self.assertIn(
            {"type": "relates-to", "target": item["id"]}, self.backend.get(other["id"])["links"],
        )

    def test_subtask_of_is_only_surfaced_on_the_child_side(self):
        """Regression test for the documented gap (ADR-0008): the parent-looking-down
        view has no canonical verb and must never be surfaced."""
        child = self.backend.create(title="Child")
        parent = self.backend.create(title="Parent")

        self.backend.add_link(child["id"], "subtask-of", parent["id"])

        self.assertIn(
            {"type": "subtask-of", "target": parent["id"]}, self.backend.get(child["id"])["links"],
        )
        self.assertEqual(self.backend.get(parent["id"])["links"], [])


class YouTrackLinkReadShapeTest(unittest.TestCase):
    """Reproduces the exact raw `links[]` shape a live YouTrack instance returns
    (verified against a real instance, 09.07.2026 -- see ADR-0008): `linkType.name`
    is the link TYPE's own name (`"Depend"`, `"Relates"`, `"Subtask"`), never the
    directional Command-API phrase, and each Depend/Subtask link is reported with
    direction `INWARD` on the ISSUER's own side, `OUTWARD` on the target's side --
    the exact opposite of what an earlier, purely mechanical implementation (and
    the fake transport it was tested against) assumed. A prior version of this
    suite could not catch either mistake: the fake modeled BOTH the type-name
    lookup and the direction convention the same (wrong) way the production code
    did, so the two bugs canceled out in every round-trip test. These tests build
    the raw issue dict directly, matching a live capture, to pin the correct
    behaviour independently of the fake."""

    def setUp(self):
        self.backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=FakeYouTrackTransport(project_short_name="TEST"),
        )

    def _raw_issue(self, links):
        return {
            "idReadable": "TEST-1",
            "summary": "Issue with links",
            "description": "",
            "project": {"shortName": "TEST"},
            "customFields": [],
            "comments": [],
            "tags": [],
            "links": links,
        }

    def test_depend_type_inward_direction_reads_as_depends_on(self):
        raw_issue = self._raw_issue([
            {
                "direction": "INWARD",
                "linkType": {"name": "Depend", "sourceToTarget": "is required for", "targetToSource": "depends on"},
                "issues": [{"idReadable": "TEST-2"}],
            },
        ])

        item = self.backend._item_from_issue(raw_issue)

        self.assertEqual(item["links"], [{"type": "depends-on", "target": "TEST-2"}])

    def test_depend_type_outward_direction_reads_as_blocks(self):
        raw_issue = self._raw_issue([
            {
                "direction": "OUTWARD",
                "linkType": {"name": "Depend", "sourceToTarget": "is required for", "targetToSource": "depends on"},
                "issues": [{"idReadable": "TEST-2"}],
            },
        ])

        item = self.backend._item_from_issue(raw_issue)

        self.assertEqual(item["links"], [{"type": "blocks", "target": "TEST-2"}])

    def test_relates_type_reads_as_relates_to_regardless_of_direction(self):
        raw_issue = self._raw_issue([
            {
                "direction": "BOTH",
                "linkType": {"name": "Relates", "sourceToTarget": "relates to", "targetToSource": ""},
                "issues": [{"idReadable": "TEST-2"}],
            },
        ])

        item = self.backend._item_from_issue(raw_issue)

        self.assertEqual(item["links"], [{"type": "relates-to", "target": "TEST-2"}])

    def test_subtask_type_inward_direction_reads_as_subtask_of(self):
        raw_issue = self._raw_issue([
            {
                "direction": "INWARD",
                "linkType": {"name": "Subtask", "sourceToTarget": "parent for", "targetToSource": "subtask of"},
                "issues": [{"idReadable": "TEST-2"}],
            },
        ])

        item = self.backend._item_from_issue(raw_issue)

        self.assertEqual(item["links"], [{"type": "subtask-of", "target": "TEST-2"}])

    def test_subtask_type_outward_direction_is_not_surfaced(self):
        raw_issue = self._raw_issue([
            {
                "direction": "OUTWARD",
                "linkType": {"name": "Subtask", "sourceToTarget": "parent for", "targetToSource": "subtask of"},
                "issues": [{"idReadable": "TEST-2"}],
            },
        ])

        item = self.backend._item_from_issue(raw_issue)

        self.assertEqual(item["links"], [])

    def test_unknown_link_type_name_is_skipped(self):
        """E.g. a project's "Duplicate" link type, which this backend has no
        canonical verb for -- must be silently ignored, not surfaced as a
        made-up verb (ADR-0008)."""
        raw_issue = self._raw_issue([
            {
                "direction": "BOTH",
                "linkType": {"name": "Duplicate", "sourceToTarget": "duplicates", "targetToSource": "is duplicated by"},
                "issues": [{"idReadable": "TEST-2"}],
            },
        ])

        item = self.backend._item_from_issue(raw_issue)

        self.assertEqual(item["links"], [])

    def test_empty_issues_slot_for_a_link_type_is_ignored(self):
        """YouTrack returns one `links[]` entry PER link type present on the
        project, even ones with no actual edge (`"issues": []`) -- must not
        produce a phantom entry."""
        raw_issue = self._raw_issue([
            {
                "direction": "OUTWARD",
                "linkType": {"name": "Depend", "sourceToTarget": "is required for", "targetToSource": "depends on"},
                "issues": [],
            },
        ])

        item = self.backend._item_from_issue(raw_issue)

        self.assertEqual(item["links"], [])


class YouTrackLinkTypeNameMapTest(unittest.TestCase):
    """`linkTypeNameMap` (ADR-0008, corrected 09.07.2026): a SEPARATE read-side
    config from `linkTypeMap` -- YouTrack's `linkType.name` is the type's own
    (renameable/localizable) name, independent of whatever Command-API phrase
    `linkTypeMap` sends. Stock English defaults resolve `Depend`/`Relates`/
    `Subtask` out of the box; a project whose instance renamed the type itself
    (not just the phrase) overrides this map."""

    def test_renamed_link_type_name_resolves_via_config(self):
        raw_issue = {
            "idReadable": "TEST-1",
            "summary": "Issue with a renamed link type",
            "description": "",
            "project": {"shortName": "TEST"},
            "customFields": [],
            "comments": [],
            "tags": [],
            "links": [
                {
                    "direction": "INWARD",
                    "linkType": {"name": "Abhaengt", "sourceToTarget": "wird benoetigt fuer", "targetToSource": "haengt ab von"},
                    "issues": [{"idReadable": "TEST-2"}],
                },
            ],
        }
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=FakeYouTrackTransport(project_short_name="TEST"),
            link_type_name_map={"Abhaengt": "depends-on"},
        )

        item = backend._item_from_issue(raw_issue)

        self.assertEqual(item["links"], [{"type": "depends-on", "target": "TEST-2"}])


class YouTrackLinkTypeMapTest(unittest.TestCase):
    """linkTypeMap (ADR-0008) ships a mechanical default (the verb dehyphenated),
    unlike stateMap/priorityMap's identity default -- and is overridable per project."""

    def test_default_link_type_map_sends_the_dehyphenated_verb(self):
        transport = FakeYouTrackTransport(project_short_name="TEST")
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
        )
        item = backend.create(title="A")
        target = backend.create(title="B")

        backend.add_link(item["id"], "depends-on", target["id"])

        self.assertIn(f"depends on {target['id']}", transport.commands_received)

    def test_overridden_link_type_map_sends_the_configured_name(self):
        """Overriding `linkTypeMap` only changes the WRITE-side Command phrase
        (e.g. a project's outward phrase is "requires" instead of "depends on")
        -- it does NOT imply the underlying YouTrack link TYPE itself was
        renamed, so the fake here is told (like a real "Depend" type with a
        custom phrase would read back) that "requires" is still the "Depend"
        type; no `linkTypeNameMap` override is needed on the backend side for
        this scenario (see YouTrackLinkTypeNameMapTest for when the type NAME
        itself, not just the phrase, differs)."""
        transport = FakeYouTrackTransport(
            project_short_name="TEST", link_type_names={"requires": "Depend"},
        )
        backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=transport,
            link_type_map={"depends-on": "requires"},
        )
        item = backend.create(title="A")
        target = backend.create(title="B")

        backend.add_link(item["id"], "depends-on", target["id"])

        self.assertIn(f"requires {target['id']}", transport.commands_received)
        fetched = backend.get(item["id"])
        self.assertIn({"type": "depends-on", "target": target["id"]}, fetched["links"])


class HttpTransportTest(unittest.TestCase):
    """Direct urllib-level tests for the real transport (mocking urllib.request.urlopen,
    per the reviewer's alternative to the fake-transport approach above) — the fake
    transport bypasses _HttpTransport entirely, so these are the only tests that
    exercise its actual header/error-handling code."""

    def test_sends_bearer_auth_header_and_returns_parsed_json(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def read(self):
                return b'{"ok": true}'

        def fake_urlopen(req, timeout=None):
            captured["auth_header"] = req.get_header("Authorization")
            return FakeResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            transport = youtrack._HttpTransport()
            result = transport.request("GET", "https://example.org/api/issues", "secret-token")

        self.assertEqual(captured["auth_header"], "Bearer secret-token")
        self.assertEqual(result, {"ok": True})

    def test_http_error_is_translated_into_workitemerror(self):
        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 404, "Not Found", None, io.BytesIO(b'{"error":"not found"}'),
            )

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            transport = youtrack._HttpTransport()
            with self.assertRaises(WorkItemError):
                transport.request("GET", "https://example.org/api/issues/PROJ-1", "secret-token")

    def test_read_timeout_is_translated_into_workitemerror_not_a_raw_exception(self):
        # A stall during resp.read() raises a bare TimeoutError (an OSError subclass
        # NOT a urllib.error.URLError subclass) — it must not bypass the except clause
        # and surface as an unhandled traceback to the CLI user.
        class StallingResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def read(self):
                raise TimeoutError("timed out")

        def fake_urlopen(req, timeout=None):
            return StallingResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            transport = youtrack._HttpTransport()
            with self.assertRaises(WorkItemError):
                transport.request("GET", "https://example.org/api/issues", "secret-token")

    def test_invalid_json_response_is_translated_into_workitemerror(self):
        class GarbageResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def read(self):
                return b"not json at all"

        def fake_urlopen(req, timeout=None):
            return GarbageResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            transport = youtrack._HttpTransport()
            with self.assertRaises(WorkItemError):
                transport.request("GET", "https://example.org/api/issues", "secret-token")


if __name__ == "__main__":
    unittest.main()
