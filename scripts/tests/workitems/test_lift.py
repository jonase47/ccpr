"""test_lift.py – Tests for `ccpr workitems lift` (ADR-0004): a SCAFFOLD, not magic.

Dry-run by default; proposes structured local items from Markdown checklists
(`- [ ]` / `- [x]`) and simple bulleted lists (this increment's scope — other
formats are future work, logged under skipped_unsupported, never silently dropped).

CRITICAL: lift does NOT verify status against the code/VCS — see lift.py's
DISCLAIMER, which every report carries. These tests check what lift genuinely does
(parse, propose, dedup, report contradictions) — never that it "verified" anything.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import lift, local  # noqa: E402


class LiftTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-lift-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.workitems_dir = Path(self.tmp_dir) / "workitems"
        self.backend = local.create({"workitems_dir": str(self.workitems_dir)})

        self.source_path = Path(self.tmp_dir) / "legacy_backlog.md"
        self.source_path.write_text(
            "# Legacy Backlog\n"
            "\n"
            "- [ ] Add rate limiting to login endpoint\n"
            "- [x] Fix flaky test in auth module\n"
            "- Some undated idea with no checkbox\n"
            "- [ ] Roll out feature flag for new dashboard\n"
            "This is just a prose paragraph, not a list item at all.\n",
            encoding="utf-8",
        )

    def test_dry_run_writes_nothing(self):
        lift.lift([str(self.source_path)], self.backend, apply=False)

        self.assertEqual(self.backend.list(), [])

    def test_dry_run_proposes_expected_items_with_status_mapping(self):
        report = lift.lift([str(self.source_path)], self.backend, apply=False)

        by_title = {p["title"]: p for p in report["proposed"]}
        self.assertEqual(by_title["Add rate limiting to login endpoint"]["status"], "Backlog")
        self.assertEqual(by_title["Fix flaky test in auth module"]["status"], "Done")

    def test_ambiguous_bullet_is_low_confidence_backlog_and_flagged(self):
        report = lift.lift([str(self.source_path)], self.backend, apply=False)

        entry = next(p for p in report["proposed"] if p["title"] == "Some undated idea with no checkbox")
        self.assertEqual(entry["status"], "Backlog")
        self.assertEqual(entry["confidence"], "low")

    def test_unsupported_line_is_logged_not_silently_dropped(self):
        report = lift.lift([str(self.source_path)], self.backend, apply=False)

        texts = [s["text"] for s in report["skipped_unsupported"]]
        self.assertIn("This is just a prose paragraph, not a list item at all.", texts)

    def test_excluded_line_is_reported_with_reason_not_lifted(self):
        report = lift.lift(
            [str(self.source_path)], self.backend, apply=False,
            exclude_rules=[{"pattern": "feature flag", "reason": "ops rollout note, not a work item"}],
        )

        excluded_texts = [e["text"] for e in report["excluded"]]
        self.assertIn("Roll out feature flag for new dashboard", excluded_texts)
        self.assertNotIn(
            "Roll out feature flag for new dashboard",
            [p["title"] for p in report["proposed"]],
        )
        reason = next(e["reason"] for e in report["excluded"] if "feature flag" in e["text"])
        self.assertEqual(reason, "ops rollout note, not a work item")

    def test_apply_writes_items_with_provenance_and_they_parse_back(self):
        report = lift.lift([str(self.source_path)], self.backend, apply=True)

        created = self.backend.list()
        self.assertEqual(len(created), 4)

        by_title = {item["title"]: item for item in created}
        self.assertIn("Add rate limiting to login endpoint", by_title)
        self.assertEqual(by_title["Add rate limiting to login endpoint"]["status"], "Backlog")
        self.assertIn(str(self.source_path), by_title["Add rate limiting to login endpoint"]["description"])

        for entry in report["proposed"]:
            self.assertIsNotNone(entry["id"])

    def test_reapplying_is_idempotent_no_duplicates(self):
        lift.lift([str(self.source_path)], self.backend, apply=True)
        first_count = len(self.backend.list())

        second_report = lift.lift([str(self.source_path)], self.backend, apply=True)

        self.assertEqual(len(self.backend.list()), first_count)
        self.assertEqual(second_report["proposed"], [])
        self.assertGreater(len(second_report["already_lifted"]), 0)

    def test_contradiction_across_sources_is_reported_not_resolved(self):
        other_source = Path(self.tmp_dir) / "notes.md"
        other_source.write_text("- [x] Add rate limiting to login endpoint\n", encoding="utf-8")

        report = lift.lift([str(self.source_path), str(other_source)], self.backend, apply=False)

        self.assertEqual(len(report["contradictions"]), 1)
        contradiction = report["contradictions"][0]
        self.assertEqual(contradiction["text"], "add rate limiting to login endpoint")
        statuses = {occ["status"] for occ in contradiction["occurrences"]}
        self.assertEqual(statuses, {"Backlog", "Done"})
        # A contradictory item must not be silently proposed with an arbitrary status.
        self.assertNotIn(
            "Add rate limiting to login endpoint",
            [p["title"] for p in report["proposed"]],
        )

    def test_normalize_folds_trailing_punctuation_so_near_duplicates_merge(self):
        # Same behaviour, same status, only a trailing period differs -- must merge
        # into ONE proposed item, not be treated as two different behaviours.
        other_source = Path(self.tmp_dir) / "notes.md"
        other_source.write_text("- [ ] Add rate limiting to login endpoint.\n", encoding="utf-8")

        report = lift.lift([str(self.source_path), str(other_source)], self.backend, apply=False)

        matching = [
            p for p in report["proposed"]
            if p["title"].startswith("Add rate limiting to login endpoint")
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(len(matching[0]["sources"]), 2)

    def test_original_source_file_is_never_modified(self):
        original_text = self.source_path.read_text(encoding="utf-8")

        lift.lift([str(self.source_path)], self.backend, apply=True)

        self.assertEqual(self.source_path.read_text(encoding="utf-8"), original_text)

    def test_report_carries_the_no_verification_disclaimer(self):
        report = lift.lift([str(self.source_path)], self.backend, apply=False)

        self.assertIn("does NOT verify", report["disclaimer"])

    def test_a_title_with_both_apostrophe_and_double_quote_now_writes_successfully(self):
        # The motivating case for the frontmatter escaping fix: this used to break
        # the round-trip and would have been caught by the try/except below as a
        # failure. It no longer fails at all -- proving the root-cause fix, not just
        # the safety net.
        tricky_path = Path(self.tmp_dir) / "tricky.md"
        tricky_path.write_text('- [ ] It\'s "done" #wip\n', encoding="utf-8")

        report = lift.lift([str(tricky_path)], self.backend, apply=True)

        self.assertEqual(report["failed"], [])
        self.assertEqual(len(report["proposed"]), 1)
        self.assertIsNotNone(report["proposed"][0]["id"])
        titles = [item["title"] for item in self.backend.list()]
        self.assertIn('It\'s "done" #wip', titles)

    def test_apply_survives_a_per_item_failure_and_continues_the_batch(self):
        # Fault injection at the backend level, independent of whatever today's
        # frontmatter parser does or doesn't handle -- this proves the try/except
        # safety net itself, not any one specific bug.
        class _BackendThatRejectsOneTitle:
            def __init__(self, backend, poison_title):
                self._backend = backend
                self._poison_title = poison_title

            def create(self, title, item_type=None, owner=None, description=None):
                if title == self._poison_title:
                    raise RuntimeError("simulated failure writing this item")
                return self._backend.create(
                    title=title, item_type=item_type, owner=owner, description=description,
                )

            def __getattr__(self, name):
                return getattr(self._backend, name)

        poison_title = "Add rate limiting to login endpoint"
        faulty_backend = _BackendThatRejectsOneTitle(self.backend, poison_title)

        report = lift.lift([str(self.source_path)], faulty_backend, apply=True)

        self.assertEqual(len(report["failed"]), 1)
        self.assertEqual(report["failed"][0]["title"], poison_title)
        self.assertIn("simulated failure", report["failed"][0]["error"])

        # The rest of the batch still gets written despite the one failure.
        remaining_titles = [item["title"] for item in self.backend.list()]
        self.assertIn("Fix flaky test in auth module", remaining_titles)
        self.assertNotIn(poison_title, remaining_titles)


if __name__ == "__main__":
    unittest.main()
