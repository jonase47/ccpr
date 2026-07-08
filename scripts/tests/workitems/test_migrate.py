"""test_migrate.py – Tests for `ccpr workitems migrate` (ADR-0004).

Mechanical only: migrate() uses the six-operation contract (list/get/create/set-status)
- no judgment calls, unlike lift. Source is the `local` backend, target is `youtrack`
backed by FakeYouTrackTransport (no network, per the same pattern as test_youtrack.py).
"""

import datetime
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import local, migrate, youtrack  # noqa: E402

from .fake_youtrack_transport import FakeYouTrackTransport

FIXED_CLOCK = lambda: datetime.datetime(2026, 7, 8, 15, 30, 0)  # noqa: E731


class MigrateLocalToYouTrackTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-migrate-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.source_dir = Path(self.tmp_dir) / "workitems"
        self.source_backend = local.create({"workitems_dir": str(self.source_dir)})

        self.transport = FakeYouTrackTransport(project_short_name="TEST")
        self.target_backend = youtrack.YouTrackBackend(
            base_url="https://faketrack.example.org", project="TEST",
            token="fake-token", transport=self.transport,
        )

        self.idmap_path = Path(self.tmp_dir) / "workitems-idmap.yml"

        first = self.source_backend.create(title="First item", owner="alice", description="Desc one.")
        self.source_backend.set_status(first["id"], "In Progress")
        second = self.source_backend.create(title="Second item", description="Desc two.")
        self.first_id = first["id"]
        self.second_id = second["id"]

    def run_migrate(self):
        return migrate.migrate(
            self.source_backend, self.target_backend, str(self.idmap_path),
            source_workitems_dir=str(self.source_dir), clock=FIXED_CLOCK,
        )

    def test_migrates_every_item_and_carries_over_status_and_owner(self):
        report = self.run_migrate()

        self.assertEqual(len(report["migrated"]), 2)
        target_items = self.target_backend.list()
        self.assertEqual(len(target_items), 2)

        by_title = {item["title"]: item for item in target_items}
        self.assertEqual(by_title["First item"]["status"], "In Progress")
        self.assertEqual(by_title["First item"]["owner"], "alice")
        self.assertEqual(by_title["Second item"]["status"], "Backlog")

    def test_writes_the_idmap_with_source_to_target_ids(self):
        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        self.assertEqual(set(idmap.keys()), {self.first_id, self.second_id})

    def test_target_item_description_carries_the_source_id_for_provenance(self):
        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_item = self.target_backend.get(idmap[self.first_id])
        self.assertIn(self.first_id, target_item["description"])

    def test_archives_the_source_directory_not_deletes_it(self):
        self.assertTrue(self.source_dir.is_dir())

        report = self.run_migrate()

        self.assertFalse(self.source_dir.exists())
        self.assertTrue(report["archived"])
        archive_path = Path(report["archive_path"])
        self.assertTrue(archive_path.is_dir())
        self.assertEqual(len(list(archive_path.glob("*.md"))), 2)
        self.assertIn("20260708153000", archive_path.name)

    def test_second_full_run_is_a_no_op_no_duplicates(self):
        self.run_migrate()
        first_target_count = len(self.target_backend.list())

        second_report = self.run_migrate()

        self.assertEqual(len(self.target_backend.list()), first_target_count)
        self.assertEqual(second_report["migrated"], [])

    def test_resumes_from_a_partial_idmap_without_duplicating_already_migrated_items(self):
        # Simulate an interrupted first run: one item already recorded in the idmap,
        # source not yet archived.
        pre_existing = self.target_backend.create(title="First item", owner="alice")
        self.target_backend.set_status(pre_existing["id"], "In Progress")
        migrate.write_idmap(str(self.idmap_path), {self.first_id: pre_existing["id"]})

        report = self.run_migrate()

        self.assertEqual(report["skipped_already_migrated"], [self.first_id])
        self.assertEqual([source_id for source_id, _ in report["migrated"]], [self.second_id])
        # Exactly 2 target items total: the pre-existing one plus the newly-migrated
        # second item -- NOT a duplicate "First item".
        self.assertEqual(len(self.target_backend.list()), 2)

    def test_recovers_from_a_crash_between_create_and_idmap_write_without_duplicating(self):
        # Simulate a crash strictly narrower than the "partial idmap" scenario above:
        # create() (and set_status()) already succeeded in the target for first_id in
        # a prior run -- the item exists, carrying its provenance marker -- but the
        # process died BEFORE the idmap write for that item, so idmap_path doesn't
        # exist at all yet (unlike the partial-idmap test, where the idmap already
        # correctly recorded the pairing).
        pre_existing = self.target_backend.create(
            title="First item", owner="alice",
            description=f"Desc one.\n\nMigrated from {self.first_id}.",
        )
        self.target_backend.set_status(pre_existing["id"], "In Progress")

        report = self.run_migrate()

        # Exactly 2 target items: the pre-existing (adopted) one plus the second
        # item -- NOT a duplicate "First item" created alongside it.
        self.assertEqual(len(self.target_backend.list()), 2)
        idmap = migrate.read_idmap(str(self.idmap_path))
        self.assertEqual(idmap[self.first_id], pre_existing["id"])
        self.assertEqual([source_id for source_id, _ in report["migrated"]],
                          [self.first_id, self.second_id])

    def test_carries_over_type_to_the_target(self):
        typed = self.source_backend.create(title="Typed item", item_type="feat")

        self.run_migrate()

        self.assertIn("Type feat", self.transport.commands_received)

    def test_report_exposes_fully_migrated_decoupled_from_archived(self):
        # source_workitems_dir=None simulates a non-local source: there is nothing to
        # archive, but every item still made it across -- these are two DIFFERENT
        # facts, and the report must expose both, not conflate them.
        report = migrate.migrate(
            self.source_backend, self.target_backend, str(self.idmap_path),
            source_workitems_dir=None, clock=FIXED_CLOCK,
        )

        self.assertTrue(report["fully_migrated"])
        self.assertFalse(report["archived"])


if __name__ == "__main__":
    unittest.main()
