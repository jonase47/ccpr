"""test_sweep.py – Tests for `ccpr workitems sweep` (ADR-0005): reconciles abandoned
claims into Parked.

Tested against a minimal in-memory fake backend (not the full YouTrackBackend) so
sweep()'s own logic — the stale-AND-has-commits rule — is proven in isolation from
any one backend's claim/heartbeat representation. Clock and the branch-commits check
are both injected, matching migrate()'s clock-injection pattern; no real git repo and
no real "now" anywhere in this file.
"""

import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import sweep  # noqa: E402

FIXED_NOW = datetime.datetime(2026, 7, 8, 16, 0, 0, tzinfo=datetime.timezone.utc)


def iso(dt):
    return dt.isoformat()


class _FakeBackend:
    """In-memory stand-in exposing just what sweep() needs: list(status=...) and
    set_status(). Items are plain dicts, directly mutable by the test."""

    def __init__(self, items):
        self._items = {item["id"]: item for item in items}
        self.status_changes = []

    def list(self, status=None, owner=None):
        items = list(self._items.values())
        if status is not None:
            items = [i for i in items if i["status"] == status]
        return [dict(i) for i in items]

    def set_status(self, item_id, status):
        self._items[item_id]["status"] = status
        self.status_changes.append((item_id, status))
        return dict(self._items[item_id])


class SweepTest(unittest.TestCase):
    def test_stale_heartbeat_with_branch_commits_becomes_parked(self):
        stale_heartbeat = iso(FIXED_NOW - datetime.timedelta(hours=2))
        backend = _FakeBackend([
            {"id": "WI-0001", "status": "In Progress", "heartbeat": stale_heartbeat},
        ])

        report = sweep.sweep(
            backend, clock=lambda: FIXED_NOW,
            has_branch_commits=lambda item_id: True,
            stale_after_seconds=3600,
        )

        self.assertEqual(report["parked"], ["WI-0001"])
        self.assertEqual(backend.list(status="Parked")[0]["id"], "WI-0001")

    def test_stale_heartbeat_without_branch_commits_stays_in_progress(self):
        stale_heartbeat = iso(FIXED_NOW - datetime.timedelta(hours=2))
        backend = _FakeBackend([
            {"id": "WI-0001", "status": "In Progress", "heartbeat": stale_heartbeat},
        ])

        report = sweep.sweep(
            backend, clock=lambda: FIXED_NOW,
            has_branch_commits=lambda item_id: False,
            stale_after_seconds=3600,
        )

        self.assertEqual(report["parked"], [])
        self.assertEqual(report["left_in_progress"], ["WI-0001"])
        self.assertEqual(backend.list(status="In Progress")[0]["id"], "WI-0001")

    def test_fresh_heartbeat_stays_in_progress_regardless_of_branch_commits(self):
        fresh_heartbeat = iso(FIXED_NOW - datetime.timedelta(minutes=5))
        backend = _FakeBackend([
            {"id": "WI-0001", "status": "In Progress", "heartbeat": fresh_heartbeat},
        ])

        report = sweep.sweep(
            backend, clock=lambda: FIXED_NOW,
            has_branch_commits=lambda item_id: True,
            stale_after_seconds=3600,
        )

        self.assertEqual(report["parked"], [])
        self.assertEqual(backend.status_changes, [])

    def test_item_with_no_heartbeat_at_all_is_never_swept(self):
        # This is what makes sweep() a natural no-op for `local`: every local item
        # always has heartbeat=None, so it never even reaches the staleness check.
        backend = _FakeBackend([
            {"id": "WI-0001", "status": "In Progress", "heartbeat": None},
        ])

        report = sweep.sweep(
            backend, clock=lambda: FIXED_NOW,
            has_branch_commits=lambda item_id: True,
            stale_after_seconds=3600,
        )

        self.assertEqual(report["parked"], [])
        self.assertEqual(backend.status_changes, [])

    def test_only_in_progress_items_are_considered(self):
        backend = _FakeBackend([
            {"id": "WI-0001", "status": "Done", "heartbeat": iso(FIXED_NOW - datetime.timedelta(hours=5))},
        ])

        report = sweep.sweep(
            backend, clock=lambda: FIXED_NOW,
            has_branch_commits=lambda item_id: True,
            stale_after_seconds=3600,
        )

        self.assertEqual(report["parked"], [])
        self.assertEqual(backend.status_changes, [])


if __name__ == "__main__":
    unittest.main()
