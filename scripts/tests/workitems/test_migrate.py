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

from workitems import WorkItemError, local, migrate, youtrack  # noqa: E402

from .fake_youtrack_transport import FakeYouTrackTransport

FIXED_CLOCK = lambda: datetime.datetime(2026, 7, 8, 15, 30, 0)  # noqa: E731


class _MigrateFixtureMixin:
    """Shared fixture only -- carries no `test_*` methods of its own (mirrors
    `GateTestBase` in test_artifact_gate.py). `CommentMigrationTest` needs the same
    source/target backends and `run_migrate()` helper as `MigrateLocalToYouTrackTest`
    but must NOT subclass it directly: unittest discovers inherited `test_*` methods
    too, so a `TestCase` subclassing another concrete `TestCase` silently re-runs
    every one of the parent's own tests a second time under the child's identity."""

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


class MigrateLocalToYouTrackTest(_MigrateFixtureMixin, unittest.TestCase):

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


class CommentMigrationTest(_MigrateFixtureMixin, unittest.TestCase):
    """Comments: the first non-idempotent field class migrate()
    carries over. Unlike create()/set_status()/add_tag()/add_link(), `comment()` has
    no dedup of its own -- POST /api/issues/<id>/comments has no pre-check -- so an
    abort mid-item's own comment list must be resumable without duplicating.
    Re-uses MigrateLocalToYouTrackTest's fixture (first_id/second_id, both with ZERO
    comments -- proving the comments phase is a no-op for them, not a crash)."""

    def test_fake_transport_comment_refusal_reaches_the_caller_as_a_work_item_error(self):
        # Not a migrate() test -- a unit test of the test double's OWN new hook,
        # since fail_comment_at has no coverage anywhere else (test_youtrack.py is
        # out of scope for this task).
        created = self.target_backend.create(title="Some item")
        self.transport.fail_comment_at(0)

        with self.assertRaises(WorkItemError):
            self.target_backend.comment(created["id"], "hello")

        # The rejected comment must not have been recorded (atomic reject).
        self.assertEqual(self.target_backend.get(created["id"])["comments"], [])

    def test_full_run_creates_each_comment_once_in_source_order(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.comment(third["id"], "alpha")
        self.source_backend.comment(third["id"], "beta")
        self.source_backend.comment(third["id"], "gamma")

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_item = self.target_backend.get(idmap[third["id"]].target_id)
        self.assertEqual(target_item["comments"], ["alpha", "beta", "gamma"])

    def test_multiline_comment_arrives_byte_identical(self):
        third = self.source_backend.create(title="Third item")
        multiline_text = (
            "First line of a longer note.\n"
            "Second line, no bullet marker.\n"
            "    Indented continuation, byte-preserved."
        )
        self.source_backend.comment(third["id"], multiline_text)

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_item = self.target_backend.get(idmap[third["id"]].target_id)
        self.assertEqual(target_item["comments"], [multiline_text])

    def test_resumes_a_comment_list_interrupted_mid_item_without_duplicating(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.comment(third["id"], "alpha")
        self.source_backend.comment(third["id"], "beta")
        self.source_backend.comment(third["id"], "gamma")

        # first_id/second_id have zero comments (trivial, zero-call phase); "alpha"
        # and "beta" are this run's calls #0 and #1 -- fail #2 ("gamma").
        self.transport.fail_comment_at(2)
        with self.assertRaises(WorkItemError):
            self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_id = idmap[third["id"]].target_id
        self.assertEqual(self.target_backend.get(target_id)["comments"], ["alpha", "beta"])
        # The idmap must not yet claim the comments phase complete for this item.
        self.assertNotIn(migrate.PHASE_COMMENTS, idmap[third["id"]].phases)

        # Resume: no more injected failures -- the remaining comment ("gamma")
        # should be the only one posted, appended after the two already there.
        self.run_migrate()

        self.assertEqual(
            self.target_backend.get(target_id)["comments"], ["alpha", "beta", "gamma"],
        )
        idmap_after = migrate.read_idmap(str(self.idmap_path))
        self.assertIn(migrate.PHASE_COMMENTS, idmap_after[third["id"]].phases)

    def test_idmap_is_written_after_created_and_status_before_comments_begin(self):
        # Proves the idmap write happens at the created+status boundary, BEFORE any
        # comment is attempted -- not only once the whole item (including comments)
        # is done. Abort on the item's very first comment (call #0) and inspect the
        # on-disk idmap.
        third = self.source_backend.create(title="Third item")
        self.source_backend.comment(third["id"], "alpha")

        self.transport.fail_comment_at(0)
        with self.assertRaises(WorkItemError):
            self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        self.assertIn(third["id"], idmap)
        self.assertEqual(
            idmap[third["id"]].phases, frozenset({migrate.PHASE_CREATED, migrate.PHASE_STATUS}),
        )

    def test_aborts_between_items_leaves_the_earlier_items_comments_intact(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.comment(third["id"], "alpha")
        fourth = self.source_backend.create(title="Fourth item")
        self.source_backend.comment(fourth["id"], "delta")

        # "alpha" (call #0) succeeds; "delta" (call #1, a DIFFERENT item) fails.
        self.transport.fail_comment_at(1)
        with self.assertRaises(WorkItemError):
            self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        third_target = idmap[third["id"]].target_id
        self.assertEqual(self.target_backend.get(third_target)["comments"], ["alpha"])
        self.assertIn(migrate.PHASE_COMMENTS, idmap[third["id"]].phases)
        # fourth was already created+status'd (that always precedes its own comment
        # attempt) but its comments phase is NOT complete.
        self.assertIn(fourth["id"], idmap)
        self.assertNotIn(migrate.PHASE_COMMENTS, idmap[fourth["id"]].phases)
        fourth_target = idmap[fourth["id"]].target_id
        self.assertEqual(self.target_backend.get(fourth_target)["comments"], [])

        report = self.run_migrate()

        self.assertEqual(self.target_backend.get(fourth_target)["comments"], ["delta"])
        # Resume never re-creates: nothing new in "migrated" this run.
        self.assertEqual(report["migrated"], [])
        # Every item is now genuinely done -- the resumed run's own report says so.
        self.assertTrue(report["fully_migrated"])

    def test_resume_never_recreates_an_item_whose_comments_are_still_pending(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.comment(third["id"], "alpha")

        # Simulate an idmap that already has third's created+status phase recorded
        # (as if a prior run got that far) but not comments -- built directly via
        # write_idmap rather than via the abort mechanism above, so this test is
        # independent of it.
        pre_existing = self.target_backend.create(title="Third item")
        migrate.write_idmap(str(self.idmap_path), {
            third["id"]: migrate.IdmapEntry(
                pre_existing["id"], frozenset({migrate.PHASE_CREATED, migrate.PHASE_STATUS}),
            ),
        })

        report = self.run_migrate()

        # first_id/second_id are NOT in this deliberately minimal idmap (only
        # third's entry was planted above), so THEY legitimately get created this
        # run -- the assertion here is scoped to third specifically: create() must
        # never be called again for an item already present in the idmap, no matter
        # which of its OWN phases remain incomplete.
        migrated_source_ids = [source_id for source_id, _ in report["migrated"]]
        self.assertNotIn(third["id"], migrated_source_ids)
        self.assertIn(third["id"], report["skipped_already_migrated"])
        # Exactly ONE target item titled "Third item" -- not recreated.
        matching = [i for i in self.target_backend.list() if i["title"] == "Third item"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(self.target_backend.get(pre_existing["id"])["comments"], ["alpha"])

    def _assert_source_order_preserved_as_subsequence(self, source_texts, target_texts):
        """Asserts every text in `source_texts` appears in `target_texts`, in the
        same relative order -- foreign texts interleaved on the target (planted
        directly, not through this migration) are simply skipped over, not
        counted against the match. Deliberately NOT calling into migrate.py's own
        subsequence walk: an independent re-implementation here so this
        acceptance check cannot pass merely because it shares a bug with the
        production code it is checking."""
        pointer = 0
        for text in target_texts:
            if pointer < len(source_texts) and text == source_texts[pointer]:
                pointer += 1
        self.assertEqual(
            pointer, len(source_texts),
            f"expected {source_texts} to appear as an ordered subsequence of "
            f"{target_texts}, but only matched the first {pointer} entr{'y' if pointer == 1 else 'ies'}",
        )

    def test_resumes_past_a_foreign_comment_planted_between_runs_without_losing_any_source_comment(self):
        # Reproduces the exact defect this task fixes: the OLD `_migrate_comments`
        # compared the source's comment list against the target's TOTAL comment
        # COUNT, so a human comment landing on the target between an aborted run
        # and its resume inflated that count and made the old logic skip past a
        # real, still-unposted source comment ("beta" here) as if it had already
        # been copied -- "beta" was lost permanently.
        third = self.source_backend.create(title="Third item")
        self.source_backend.comment(third["id"], "alpha")
        self.source_backend.comment(third["id"], "beta")
        self.source_backend.comment(third["id"], "gamma")

        # "alpha" (call #0) succeeds; "beta" (call #1) fails -- abort mid-item.
        self.transport.fail_comment_at(1)
        with self.assertRaises(WorkItemError):
            self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_id = idmap[third["id"]].target_id
        self.assertEqual(self.target_backend.get(target_id)["comments"], ["alpha"])

        # A human comments on the target directly, between the two runs -- exactly
        # what the old "compare against the TOTAL count" resume logic could not
        # tell apart from one of its own already-posted source comments.
        self.target_backend.comment(target_id, "a human note")

        self.run_migrate()

        final_comments = self.target_backend.get(target_id)["comments"]
        self._assert_source_order_preserved_as_subsequence(
            ["alpha", "beta", "gamma"], final_comments,
        )

    def test_duplicate_comment_texts_within_one_items_list_both_survive_a_resume(self):
        # WI-0077's real shape (measured across the 140-item corpus, see
        # _migrate_comments' docstring): a repeated table-separator row,
        # byte-identical, twice in the same item's own comment list. A
        # membership/set-based resume rule would treat the second occurrence as
        # "already there" the moment the first is seen and never post it.
        third = self.source_backend.create(title="Third item")
        self.source_backend.comment(third["id"], "|---|---|---|")
        self.source_backend.comment(third["id"], "|---|---|---|")
        self.source_backend.comment(third["id"], "gamma")

        # Both copies of "|---|---|---|" (calls #0 and #1) succeed; "gamma"
        # (call #2) fails -- abort mid-item.
        self.transport.fail_comment_at(2)
        with self.assertRaises(WorkItemError):
            self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_id = idmap[third["id"]].target_id
        self.assertEqual(
            self.target_backend.get(target_id)["comments"],
            ["|---|---|---|", "|---|---|---|"],
        )

        self.run_migrate()

        self.assertEqual(
            self.target_backend.get(target_id)["comments"],
            ["|---|---|---|", "|---|---|---|", "gamma"],
        )

    def test_a_postcondition_failure_leaves_the_phase_unrecorded_and_does_not_archive(self):
        # The second required fix: migrate() must not record
        # PHASE_COMMENTS on the strength of `_migrate_comments` merely returning
        # without raising -- it must re-read the target and confirm every source
        # comment actually landed. Simulated with a target wrapper whose
        # comment() ACKNOWLEDGES one write without persisting it -- a scenario
        # `_migrate_comments` itself cannot detect from its own return value (the
        # call it made "succeeded"), but the postcondition re-read does.
        class _TargetThatSilentlyDropsOneComment:
            """Wraps the real target backend: the `drop_at`-th (0-based, counted
            across calls made through THIS wrapper only) `comment()` call
            returns successfully but never actually writes the comment through
            to the backend -- acknowledges a write it silently lost."""

            def __init__(self, backend, drop_at):
                self._backend = backend
                self._drop_at = drop_at
                self._call_count = 0

            def comment(self, item_id, text):
                index = self._call_count
                self._call_count += 1
                if index == self._drop_at:
                    return {"text": text}
                return self._backend.comment(item_id, text)

            def __getattr__(self, name):
                return getattr(self._backend, name)

        third = self.source_backend.create(title="Third item")
        self.source_backend.comment(third["id"], "alpha")
        self.source_backend.comment(third["id"], "beta")

        wrapped_target = _TargetThatSilentlyDropsOneComment(self.target_backend, drop_at=1)

        with self.assertRaises(WorkItemError):
            migrate.migrate(
                self.source_backend, wrapped_target, str(self.idmap_path),
                source_workitems_dir=str(self.source_dir), clock=FIXED_CLOCK,
            )

        idmap = migrate.read_idmap(str(self.idmap_path))
        self.assertNotIn(migrate.PHASE_COMMENTS, idmap[third["id"]].phases)
        self.assertFalse(migrate._all_phases_complete(idmap, self.source_backend.list()))
        # No filesystem side effect from a partial phase -- the source must not
        # have been archived.
        self.assertTrue(self.source_dir.is_dir())


class LinkMigrationTest(_MigrateFixtureMixin, unittest.TestCase):
    """Links (second pass): `add_link` needs the PARTNER's
    target id, which does not exist until the partner item has itself been
    created -- so links cannot ride along in the per-item loop the way
    created/status/comments do; they need their own pass after every item in
    this run has been created. Re-uses MigrateLocalToYouTrackTest's fixture
    (first_id/second_id, both with ZERO links -- proving the links phase is a
    no-op for them, not a crash)."""

    def test_plain_relates_to_and_depends_on_links_arrive_on_the_target(self):
        third = self.source_backend.create(title="Third item")
        fourth = self.source_backend.create(title="Fourth item")
        self.source_backend.add_link(third["id"], "relates-to", fourth["id"])
        self.source_backend.add_link(third["id"], "depends-on", fourth["id"])

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        third_target = idmap[third["id"]].target_id
        fourth_target = idmap[fourth["id"]].target_id
        target_links = self.target_backend.get(third_target)["links"]
        self.assertIn({"type": "relates-to", "target": fourth_target}, target_links)
        self.assertIn({"type": "depends-on", "target": fourth_target}, target_links)

    def test_mutual_depends_on_pair_arrives_as_two_edges_each(self):
        # WI-0005's real shape (measured across the 140-item corpus, see the
        # senior-developer's briefing for this task): two items each record
        # their OWN "depends-on" edge toward the other -- verified against a
        # live instance to be two distinct, both-accepted edges, not a single
        # relationship collapsed to one direction.
        fifth = self.source_backend.create(title="Fifth item")
        sixth = self.source_backend.create(title="Sixth item")
        self.source_backend.add_link(fifth["id"], "depends-on", sixth["id"])
        self.source_backend.add_link(sixth["id"], "depends-on", fifth["id"])

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        fifth_target = idmap[fifth["id"]].target_id
        sixth_target = idmap[sixth["id"]].target_id
        self.assertIn(
            {"type": "depends-on", "target": sixth_target},
            self.target_backend.get(fifth_target)["links"],
        )
        self.assertIn(
            {"type": "depends-on", "target": fifth_target},
            self.target_backend.get(sixth_target)["links"],
        )

    def test_link_resolution_uses_the_idmap_not_positional_id_arithmetic(self):
        # WI-NNNN -> CCP-N positional alignment is dead (a failed create() burns
        # a target-side number, measured in an earlier pilot) -- pre-create an
        # unrelated item directly in the target so the fake transport's own
        # issue numbering is offset from this test's two source items (their
        # WI-numeric suffix no longer lines up with their eventual target-side
        # number). If link resolution ever assumed that alignment instead of
        # reading the idmap, it would call add_link() with the WRONG (or a
        # nonexistent) target id, and the assertion below would fail -- either
        # the expected edge would be missing, or add_link() would itself raise
        # on an unknown target id.
        self.target_backend.create(title="Unrelated pre-existing item")

        seventh = self.source_backend.create(title="Seventh item")
        eighth = self.source_backend.create(title="Eighth item")
        self.source_backend.add_link(seventh["id"], "relates-to", eighth["id"])

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        seventh_target = idmap[seventh["id"]].target_id
        eighth_target = idmap[eighth["id"]].target_id
        # The offset is real, not merely assumed: the naive WI-suffix ==
        # target-suffix guess for `eighth` (WI-0004 -> "TEST-4") is not what
        # this run actually assigned, because of the unrelated item above.
        self.assertNotEqual(eighth_target, "TEST-4")
        self.assertIn(
            {"type": "relates-to", "target": eighth_target},
            self.target_backend.get(seventh_target)["links"],
        )

    def test_a_link_whose_target_is_missing_from_the_idmap_fails_loud(self):
        # add_link() itself refuses to create a dangling link (both ids must
        # exist as real work items -- see local.py's add_link), so the missing
        # idmap entry here has to be one of the two causes named in
        # _resolve_link_target_id's own docstring. This constructs the SECOND
        # one, not a resume with a lost entry: `fourth` (the link's target) is
        # removed from THIS run's source directory entirely, so the first
        # pass never sees it in source_items and never gives it an idmap
        # entry in the first place -- there is nothing to lose, it was never
        # there. `third`'s pre-existing, links-incomplete idmap entry is
        # planted directly so the run reaches the links pass for `third` ->
        # `fourth` without needing a full prior run first.
        third = self.source_backend.create(title="Third item")
        fourth = self.source_backend.create(title="Fourth item")
        self.source_backend.add_link(third["id"], "relates-to", fourth["id"])

        third_target = self.target_backend.create(title="Third item")
        migrate.write_idmap(str(self.idmap_path), {
            third["id"]: migrate.IdmapEntry(
                third_target["id"],
                frozenset({
                    migrate.PHASE_CREATED, migrate.PHASE_STATUS, migrate.PHASE_COMMENTS,
                }),
            ),
        })
        (self.source_dir / f"{fourth['id']}.md").unlink()

        with self.assertRaises(WorkItemError) as ctx:
            self.run_migrate()

        self.assertIn(fourth["id"], str(ctx.exception))
        # Failing loud means failing BEFORE the phase is recorded -- the idmap
        # on disk must still show `third` without PHASE_LINKS.
        idmap_after = migrate.read_idmap(str(self.idmap_path))
        self.assertNotIn(migrate.PHASE_LINKS, idmap_after[third["id"]].phases)

    def test_a_links_postcondition_failure_leaves_the_phase_unrecorded_and_does_not_archive(self):
        # Mirrors CommentMigrationTest's equivalent postcondition test: PHASE_LINKS
        # must not be recorded on the strength of add_link() merely returning
        # without raising -- it must re-read the target and confirm the edge
        # actually landed. Simulated with a target wrapper whose add_link()
        # ACKNOWLEDGES a write without persisting it -- a scenario _migrate_links
        # itself cannot detect from its own return value, but the postcondition
        # re-read does.
        class _TargetThatSilentlyDropsOneLink:
            """Wraps the real target backend: the `drop_at`-th (0-based, counted
            across calls made through THIS wrapper only) `add_link()` call
            returns successfully but never actually writes the edge through to
            the backend -- acknowledges a write it silently lost."""

            def __init__(self, backend, drop_at):
                self._backend = backend
                self._drop_at = drop_at
                self._call_count = 0

            def add_link(self, item_id, link_type, target_id):
                index = self._call_count
                self._call_count += 1
                if index == self._drop_at:
                    return self._backend.get(item_id)
                return self._backend.add_link(item_id, link_type, target_id)

            def __getattr__(self, name):
                return getattr(self._backend, name)

        third = self.source_backend.create(title="Third item")
        fourth = self.source_backend.create(title="Fourth item")
        self.source_backend.add_link(third["id"], "relates-to", fourth["id"])

        wrapped_target = _TargetThatSilentlyDropsOneLink(self.target_backend, drop_at=0)

        with self.assertRaises(WorkItemError):
            migrate.migrate(
                self.source_backend, wrapped_target, str(self.idmap_path),
                source_workitems_dir=str(self.source_dir), clock=FIXED_CLOCK,
            )

        idmap = migrate.read_idmap(str(self.idmap_path))
        self.assertNotIn(migrate.PHASE_LINKS, idmap[third["id"]].phases)
        self.assertFalse(migrate._all_phases_complete(idmap, self.source_backend.list()))
        # No filesystem side effect from a partial phase -- the source must not
        # have been archived.
        self.assertTrue(self.source_dir.is_dir())

    def test_full_run_with_links_present_completes_and_archives(self):
        # The positive counterpart to the postcondition-failure test above: the
        # PHASE_LINKS requirement must not spuriously block an otherwise-normal
        # successful run. Asserts on the REPORT (fully_migrated, archived) --
        # the surface scripts/workitems.py reads to decide whether to flip the
        # active provider (ADR-0002) -- not just on the underlying formula.
        third = self.source_backend.create(title="Third item")
        fourth = self.source_backend.create(title="Fourth item")
        self.source_backend.add_link(third["id"], "relates-to", fourth["id"])

        report = self.run_migrate()

        self.assertTrue(report["fully_migrated"])
        self.assertTrue(report["archived"])

    def test_fake_transport_link_refusal_reaches_the_caller_as_a_work_item_error(self):
        # Not a migrate() test -- a unit test of the test double's OWN new hook
        # (mirrors CommentMigrationTest's equivalent test for fail_comment_at),
        # since fail_link_at has no coverage anywhere else.
        created_a = self.target_backend.create(title="A")
        created_b = self.target_backend.create(title="B")
        self.transport.fail_link_at(0)

        with self.assertRaises(WorkItemError):
            self.target_backend.add_link(created_a["id"], "relates-to", created_b["id"])

        # The rejected link must not have been recorded (atomic reject).
        self.assertEqual(self.target_backend.get(created_a["id"])["links"], [])

    def test_resumes_an_interrupted_link_pass_without_duplicating_and_completes(self):
        third = self.source_backend.create(title="Third item")
        fourth = self.source_backend.create(title="Fourth item")
        fifth = self.source_backend.create(title="Fifth item")
        self.source_backend.add_link(third["id"], "relates-to", fourth["id"])
        self.source_backend.add_link(third["id"], "depends-on", fifth["id"])

        # first_id/second_id (fixture) and fourth/fifth carry no links of their
        # own -- the only two add-link commands this run ever sends are
        # third's own, in source order. "relates-to fourth" (call #0) succeeds;
        # "depends-on fifth" (call #1) fails -- abort mid-item's own link list.
        self.transport.fail_link_at(1)
        with self.assertRaises(WorkItemError):
            self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        third_target = idmap[third["id"]].target_id
        fourth_target = idmap[fourth["id"]].target_id
        fifth_target = idmap[fifth["id"]].target_id
        target_links = self.target_backend.get(third_target)["links"]
        self.assertIn({"type": "relates-to", "target": fourth_target}, target_links)
        self.assertNotIn({"type": "depends-on", "target": fifth_target}, target_links)
        self.assertNotIn(migrate.PHASE_LINKS, idmap[third["id"]].phases)

        # Resume: no more injected failures -- the already-migrated edge must
        # not be duplicated (add_link()'s own idempotence check), and the
        # still-missing one must land.
        report = self.run_migrate()

        target_links_after = self.target_backend.get(third_target)["links"]
        self.assertIn({"type": "relates-to", "target": fourth_target}, target_links_after)
        self.assertIn({"type": "depends-on", "target": fifth_target}, target_links_after)
        self.assertEqual(len(target_links_after), 2)
        self.assertTrue(report["fully_migrated"])


class ResultRefClassificationTest(unittest.TestCase):
    """Unit tests of the classifier itself (rule C, decided by the PO): every
    whitespace-separated token in a `## Result` entry must match a bare sha (with
    an optional `user@` prefix) or a bare URL for the whole entry to count as a
    REF; anything else is prose. Direct tests of a private helper -- same posture
    as `_all_phases_complete` above, which this file already tests directly."""

    def test_a_bare_sha_is_a_ref(self):
        self.assertTrue(migrate._is_result_ref("15ca8cf"))

    def test_a_bare_url_is_a_ref(self):
        self.assertTrue(migrate._is_result_ref("https://example.org/commit/abc1234"))

    def test_a_user_prefixed_sha_is_a_ref(self):
        self.assertTrue(migrate._is_result_ref("bot@abc1234"))

    def test_two_shas_on_one_line_are_both_refs(self):
        # The corpus carries lines with two shas (measured 02.09.2026, see the
        # module docstring) -- every token must match, not just the first.
        self.assertTrue(migrate._is_result_ref("abc1234 def5678"))

    def test_a_sha_embedded_in_prose_is_not_a_ref(self):
        # The accepted gap (per the PO's decision, not to be closed): a sha
        # wrapped in backticks/prose fails the whole-token rule and travels as
        # a comment instead.
        self.assertFalse(
            migrate._is_result_ref("Commit: `15ca8cf` (`git rev-parse HEAD` = ...)")
        )

    def test_a_test_path_line_is_not_a_ref(self):
        self.assertFalse(migrate._is_result_ref("Test: `path.py`"))

    def test_an_empty_entry_is_not_a_ref(self):
        self.assertFalse(migrate._is_result_ref(""))


class ResultRefMigrationTest(_MigrateFixtureMixin, unittest.TestCase):
    """Result refs (`## Result` entries classified as a ref by rule C): migrated
    via `append_result()`, a distinct channel from comments/prose (ADR-0002
    addendum's RESULT_MARKER partition). Re-uses MigrateLocalToYouTrackTest's
    fixture (first_id/second_id, both with ZERO result-link entries -- proving
    the phase is a no-op for them, not a crash). append_result() shares the SAME
    comments endpoint as comment() in the fake (see fail_comment_at's own
    docstring) -- resume/postcondition tests below reuse that hook, no new one
    needed."""

    def test_a_sha_result_entry_arrives_as_a_result_link_on_the_target(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.append_result(third["id"], "15ca8cf")

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_item = self.target_backend.get(idmap[third["id"]].target_id)
        self.assertEqual(target_item["result-link"], ["15ca8cf"])
        self.assertEqual(target_item["comments"], [])

    def test_a_url_result_entry_arrives_as_a_result_link_on_the_target(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.append_result(third["id"], "https://example.org/pr/1")

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_item = self.target_backend.get(idmap[third["id"]].target_id)
        self.assertEqual(target_item["result-link"], ["https://example.org/pr/1"])

    def test_refs_migrate_in_source_order(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.append_result(third["id"], "aaa1111")
        self.source_backend.append_result(third["id"], "bbb2222")
        self.source_backend.append_result(third["id"], "ccc3333")

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_item = self.target_backend.get(idmap[third["id"]].target_id)
        self.assertEqual(target_item["result-link"], ["aaa1111", "bbb2222", "ccc3333"])

    def test_resumes_an_interrupted_result_ref_list_without_duplicating(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.append_result(third["id"], "aaa1111")
        self.source_backend.append_result(third["id"], "bbb2222")
        self.source_backend.append_result(third["id"], "ccc3333")

        # first_id/second_id have zero result-links (a zero-call phase); "aaa1111"
        # and "bbb2222" are this run's calls #0 and #1 -- fail #2 ("ccc3333").
        self.transport.fail_comment_at(2)
        with self.assertRaises(WorkItemError):
            self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_id = idmap[third["id"]].target_id
        self.assertEqual(self.target_backend.get(target_id)["result-link"], ["aaa1111", "bbb2222"])
        self.assertNotIn(migrate.PHASE_RESULT_REFS, idmap[third["id"]].phases)

        self.run_migrate()

        self.assertEqual(
            self.target_backend.get(target_id)["result-link"], ["aaa1111", "bbb2222", "ccc3333"],
        )
        idmap_after = migrate.read_idmap(str(self.idmap_path))
        self.assertIn(migrate.PHASE_RESULT_REFS, idmap_after[third["id"]].phases)

    def test_a_result_ref_postcondition_failure_leaves_the_phase_unrecorded_and_does_not_archive(self):
        # Mirrors CommentMigrationTest's/LinkMigrationTest's equivalent postcondition
        # test: PHASE_RESULT_REFS must not be recorded on the strength of
        # append_result() merely returning without raising -- it must re-read the
        # target and confirm the ref actually landed.
        class _TargetThatSilentlyDropsOneResultRef:
            def __init__(self, backend, drop_at):
                self._backend = backend
                self._drop_at = drop_at
                self._call_count = 0

            def append_result(self, item_id, ref):
                index = self._call_count
                self._call_count += 1
                if index == self._drop_at:
                    return self._backend.get(item_id)
                return self._backend.append_result(item_id, ref)

            def __getattr__(self, name):
                return getattr(self._backend, name)

        third = self.source_backend.create(title="Third item")
        self.source_backend.append_result(third["id"], "aaa1111")

        wrapped_target = _TargetThatSilentlyDropsOneResultRef(self.target_backend, drop_at=0)

        with self.assertRaises(WorkItemError):
            migrate.migrate(
                self.source_backend, wrapped_target, str(self.idmap_path),
                source_workitems_dir=str(self.source_dir), clock=FIXED_CLOCK,
            )

        idmap = migrate.read_idmap(str(self.idmap_path))
        self.assertNotIn(migrate.PHASE_RESULT_REFS, idmap[third["id"]].phases)
        self.assertFalse(migrate._all_phases_complete(idmap, self.source_backend.list()))
        self.assertTrue(self.source_dir.is_dir())

    def test_a_result_prose_entry_does_not_arrive_as_a_result_link(self):
        # Classification boundary: a prose entry (fails rule C) must never reach
        # append_result() -- it belongs to the comments channel (next cycle), not
        # this one. Asserted here as the negative half of THIS cycle's own scope:
        # not a comment-channel assertion (that is ResultProseMigrationTest's job).
        third = self.source_backend.create(title="Third item")
        self.source_backend.append_result(third["id"], "Commit: `15ca8cf` (see log)")

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_item = self.target_backend.get(idmap[third["id"]].target_id)
        self.assertEqual(target_item["result-link"], [])

    def test_full_run_with_result_refs_present_completes_and_archives(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.append_result(third["id"], "aaa1111")

        report = self.run_migrate()

        self.assertTrue(report["fully_migrated"])
        self.assertTrue(report["archived"])


class ResultProseMigrationTest(_MigrateFixtureMixin, unittest.TestCase):
    """Result prose (`## Result` entries classified as prose by rule C, i.e.
    everything a `## Result` entry can be that is not a ref -- see
    ResultRefClassificationTest): joins the comments channel via comment(), in a
    deterministic order -- source comments FIRST, then classified result-link
    prose, each sublist keeping its own relative order (see
    _comment_source_texts's docstring). Re-uses the SAME resume/postcondition
    machinery as CommentMigrationTest -- PHASE_COMMENTS, not a new phase -- since
    the source list is just wider now, not a new kind of write."""

    def test_a_prose_result_entry_migrates_as_a_comment_not_a_result_link(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.append_result(third["id"], "Commit: `15ca8cf` (see log)")

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_item = self.target_backend.get(idmap[third["id"]].target_id)
        self.assertEqual(target_item["comments"], ["Commit: `15ca8cf` (see log)"])
        self.assertEqual(target_item["result-link"], [])

    def test_comments_precede_prose_result_entries_in_the_combined_order(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.comment(third["id"], "a plain comment")
        self.source_backend.append_result(third["id"], "Some prose note about the result.")

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_item = self.target_backend.get(idmap[third["id"]].target_id)
        self.assertEqual(
            target_item["comments"],
            ["a plain comment", "Some prose note about the result."],
        )

    def test_a_mixed_result_link_list_splits_refs_and_prose_onto_their_own_channels(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.append_result(third["id"], "aaa1111")
        self.source_backend.append_result(third["id"], "A prose note.")
        self.source_backend.append_result(third["id"], "bbb2222")

        self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_item = self.target_backend.get(idmap[third["id"]].target_id)
        self.assertEqual(target_item["result-link"], ["aaa1111", "bbb2222"])
        self.assertEqual(target_item["comments"], ["A prose note."])

    def test_resumes_a_combined_comments_and_prose_list_interrupted_at_the_boundary(self):
        third = self.source_backend.create(title="Third item")
        self.source_backend.comment(third["id"], "alpha")
        self.source_backend.append_result(third["id"], "A prose result note.")

        # "alpha" (call #0) succeeds; the prose entry (call #1, posted through
        # the same comment() endpoint once folded into the combined list) fails.
        self.transport.fail_comment_at(1)
        with self.assertRaises(WorkItemError):
            self.run_migrate()

        idmap = migrate.read_idmap(str(self.idmap_path))
        target_id = idmap[third["id"]].target_id
        self.assertEqual(self.target_backend.get(target_id)["comments"], ["alpha"])
        self.assertNotIn(migrate.PHASE_COMMENTS, idmap[third["id"]].phases)

        self.run_migrate()

        self.assertEqual(
            self.target_backend.get(target_id)["comments"],
            ["alpha", "A prose result note."],
        )
        idmap_after = migrate.read_idmap(str(self.idmap_path))
        self.assertIn(migrate.PHASE_COMMENTS, idmap_after[third["id"]].phases)


class FullyMigratedRequiresEveryPhaseTest(unittest.TestCase):
    """`report["fully_migrated"]` gates archiving the source directory AND (in
    scripts/workitems.py's _run_migrate) flipping .claude/settings.json's active
    provider. Before per-item phases existed, "every source id appears in the
    idmap" WAS the complete definition. Now an item can be IN the idmap with its
    comments phase still pending, so bare id-presence is no longer an accurate
    description of "done".

    A direct unit test of the extracted formula, not a full migrate() run --
    deliberately, because a full-run test cannot exercise the disagreement between
    the old and new formulas: under this task's explicit instruction that a comment
    failure propagate the same way create()/set_status() failures always have (no
    internal try/except), an in-progress migrate() call can only ever end in one of
    two ways -- it raises (no report produced at all), or it completes with EVERY
    attempted item's EVERY phase done (see CommentMigrationTest above). So at
    today's one call site, this formula and plain id-presence agree on every
    reachable input -- the actual guard against the archive/flip hazard is the
    uncaught exception, not this formula. What this pins is the formula's OWN
    correctness in isolation (including old-format idmap state left on disk between
    invocations, e.g. from a differently-shaped prior run or hand-editing) so it
    keeps meaning what it says the day a phase might become best-effort rather than
    fail-hard, and id-presence-alone would then silently accept an item that never
    finished."""

    def test_an_item_present_but_missing_a_required_phase_is_not_fully_migrated(self):
        source_items = [{"id": "WI-0001"}, {"id": "WI-0002"}]
        idmap = {
            "WI-0001": migrate.IdmapEntry(
                "CT-1", frozenset({migrate.PHASE_CREATED, migrate.PHASE_STATUS, migrate.PHASE_COMMENTS}),
            ),
            # WI-0002 exists in the idmap (the OLD, id-presence-only definition
            # would call this "fully migrated") but its comments phase never ran.
            "WI-0002": migrate.IdmapEntry(
                "CT-2", frozenset({migrate.PHASE_CREATED, migrate.PHASE_STATUS}),
            ),
        }

        self.assertFalse(migrate._all_phases_complete(idmap, source_items))

    def test_every_item_with_every_required_phase_is_fully_migrated(self):
        source_items = [{"id": "WI-0001"}]
        idmap = {
            "WI-0001": migrate.IdmapEntry(
                "CT-1", frozenset({
                    migrate.PHASE_CREATED, migrate.PHASE_STATUS,
                    migrate.PHASE_COMMENTS, migrate.PHASE_LINKS,
                    migrate.PHASE_RESULT_REFS,
                }),
            ),
        }

        self.assertTrue(migrate._all_phases_complete(idmap, source_items))

    def test_an_id_missing_from_the_idmap_entirely_is_not_fully_migrated(self):
        # Baseline: an item never even created yet -- both the old and new
        # definitions agree here, kept as a guard against a future edit that
        # accidentally drops this case.
        self.assertFalse(migrate._all_phases_complete({}, [{"id": "WI-0001"}]))


class IdmapPhaseFormatTest(unittest.TestCase):
    """`read_idmap`/`write_idmap` in isolation: the idmap is no longer a
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
