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
        target_item = self.target_backend.get(idmap[self.first_id].target_id)
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

    def test_archiving_reports_the_exact_restore_command(self):
        report = self.run_migrate()

        self.assertIn(report["archive_path"], report["restore_command"])
        self.assertIn(str(self.source_dir), report["restore_command"])

    def test_second_full_run_is_a_no_op_no_duplicates(self):
        self.run_migrate()
        # Liveness (WI-0128 finding #1): the first run actually migrated
        # both fixture items -- classifier-visible companion to the two
        # count/no-op comparisons below, which are already sound on their
        # own (`run_migrate` is a plain in-process call: a real regression
        # here raises and errors the test outright rather than silently
        # returning an empty report the way a crashed subprocess's stdout
        # would collapse to ""). The literal `len(...)` call must be
        # inline for the classifier's nonzero-length-pair shape to see it.
        self.assertEqual(2, len(self.target_backend.list()))
        first_target_count = len(self.target_backend.list())

        second_report = self.run_migrate()

        self.assertEqual(len(self.target_backend.list()), first_target_count)
        self.assertEqual(second_report["migrated"], [])

    def test_resumes_from_a_partial_idmap_without_duplicating_already_migrated_items(self):
        # Simulate an interrupted first run: one item already recorded in the idmap,
        # source not yet archived.
        pre_existing = self.target_backend.create(title="First item", owner="alice")
        self.target_backend.set_status(pre_existing["id"], "In Progress")
        migrate.write_idmap(str(self.idmap_path), {
            self.first_id: migrate.IdmapEntry(
                pre_existing["id"],
                frozenset({migrate.PHASE_CREATED, migrate.PHASE_STATUS}),
            ),
        })

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
        self.assertEqual(idmap[self.first_id].target_id, pre_existing["id"])
        self.assertEqual([source_id for source_id, _ in report["migrated"]],
                          [self.first_id, self.second_id])

    def test_carries_over_type_to_the_target(self):
        typed = self.source_backend.create(title="Typed item", item_type="feat")

        self.run_migrate()

        self.assertIn("Type feat", self.transport.commands_received)

    def test_aborts_archiving_if_new_source_items_appeared_since_the_snapshot(self):
        # Wraps the real source backend: the FIRST list() call (migrate()'s initial
        # snapshot) behaves normally, but as a side effect creates one more item
        # directly in the source dir -- so a SECOND list() call (the pre-archive
        # re-check) sees an extra id that was never processed by this run at all.
        class _SourceThatGrowsAfterFirstList:
            def __init__(self, backend):
                self._backend = backend
                self._list_calls = 0

            def list(self, status=None, owner=None):
                items = self._backend.list(status=status, owner=owner)
                self._list_calls += 1
                if self._list_calls == 1:
                    self._backend.create(title="Snuck in after the snapshot")
                return items

            def __getattr__(self, name):
                return getattr(self._backend, name)

        wrapped_source = _SourceThatGrowsAfterFirstList(self.source_backend)

        report = migrate.migrate(
            wrapped_source, self.target_backend, str(self.idmap_path),
            source_workitems_dir=str(self.source_dir), clock=FIXED_CLOCK,
        )

        self.assertFalse(report["archived"])
        self.assertTrue(self.source_dir.is_dir())
        self.assertIn("archive_skipped_new_items_appeared", report)
        self.assertEqual(len(report["archive_skipped_new_items_appeared"]), 1)
        # The two ORIGINAL items still migrated normally -- only archiving is
        # aborted, not the whole run.
        self.assertEqual(len(report["migrated"]), 2)

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


class IdmapPhaseFormatTest(unittest.TestCase):
    """`read_idmap`/`write_idmap` in isolation (WI-0141): the idmap is no longer a
    flat `source-id: target-id` line -- it now records, per item, which phases of
    the migration completed (`created`, `status`, and later `comments`), so a
    resumed run can tell "created but comments not yet copied" apart from "fully
    done" instead of treating idmap-presence as a single yes/no flag."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-idmap-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.idmap_path = str(Path(self.tmp_dir) / "workitems-idmap.yml")

    def test_round_trips_target_id_and_completed_phases(self):
        entry = migrate.IdmapEntry(
            target_id="CT-1", phases=frozenset({migrate.PHASE_CREATED, migrate.PHASE_STATUS}),
        )
        migrate.write_idmap(self.idmap_path, {"WI-0001": entry})

        idmap = migrate.read_idmap(self.idmap_path)

        self.assertEqual(idmap["WI-0001"].target_id, "CT-1")
        self.assertEqual(idmap["WI-0001"].phases, entry.phases)

    def test_round_trips_a_third_phase_not_yet_used_by_migrate_itself(self):
        # Proves the format is extensible (per the task's "later phases slot in
        # without another format change" requirement) without migrate() itself
        # having to know about a "comments" phase yet.
        entry = migrate.IdmapEntry(
            target_id="CT-7",
            phases=frozenset({migrate.PHASE_CREATED, migrate.PHASE_STATUS, migrate.PHASE_COMMENTS}),
        )
        migrate.write_idmap(self.idmap_path, {"WI-0007": entry})

        idmap = migrate.read_idmap(self.idmap_path)

        self.assertEqual(idmap["WI-0007"].phases, entry.phases)

    def test_a_phase_less_line_on_disk_reads_as_created_and_status_complete(self):
        # Simulates a file left over from BEFORE phase-tracking existed at all --
        # not written by this version's write_idmap, but by hand / an older
        # release. migrate.py never recorded an idmap entry before both create()
        # and set_status() had already succeeded (the single write happened after
        # both), so a bare "source: target" line can only ever mean those two
        # phases are done.
        Path(self.idmap_path).write_text("WI-0001: CT-1\n", encoding="utf-8")

        idmap = migrate.read_idmap(self.idmap_path)

        self.assertEqual(idmap["WI-0001"].target_id, "CT-1")
        self.assertEqual(idmap["WI-0001"].phases, frozenset({migrate.PHASE_CREATED, migrate.PHASE_STATUS}))

    def test_a_line_with_extra_whitespace_around_the_phase_list_still_parses_cleanly(self):
        # Defends against a hand-edited file (the module docstring explicitly
        # anticipates one) -- stray spaces between target-id and the phase list,
        # or around individual phase names, must not corrupt a phase name (e.g.
        # produce " created" with a leading space, which would never again match
        # PHASE_CREATED anywhere it's checked).
        Path(self.idmap_path).write_text("WI-0001: CT-1   created, status \n", encoding="utf-8")

        idmap = migrate.read_idmap(self.idmap_path)

        self.assertEqual(idmap["WI-0001"].target_id, "CT-1")
        self.assertEqual(idmap["WI-0001"].phases, frozenset({migrate.PHASE_CREATED, migrate.PHASE_STATUS}))

    def test_write_idmap_refuses_an_entry_with_no_completed_phases(self):
        # An empty phases set would round-trip indistinguishably from a legacy
        # phase-less line (read back as "created+status done" -- see the test
        # above) -- silently turning "nothing done yet" into a false completion
        # claim. write_idmap must reject it outright rather than write it.
        entry = migrate.IdmapEntry(target_id="CT-1", phases=frozenset())

        with self.assertRaises(ValueError):
            migrate.write_idmap(self.idmap_path, {"WI-0001": entry})


if __name__ == "__main__":
    unittest.main()
