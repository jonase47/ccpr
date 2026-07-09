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
        # its own fresh in-memory "project" instead.
        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        return youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
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
