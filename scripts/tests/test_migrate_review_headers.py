"""test_migrate_review_headers.py -- ground-up coverage for
scripts/migrate-review-headers.sh (WI-0072, corrected 22.08.2026).

Backfills `kind: review` + `sprint` onto the holistic sprint-review reports
(`docs/reviews/SPRINT-<N>-review.md`) that predate WI-0072's header schema.
Three guarantees carry the whole design and are pinned as their own test
classes, not just asserted in passing:

(1) RECONSTRUCTING a missing value is still forbidden -- inferring a
    plausible base_commit/reviewed_head/reviewed_base from git history or
    any other derivation. A wrong guess here lets `/gate-p5` treat a stale
    review as current, which is worse than the avoidable opus re-run a
    missing field costs.

(2) MOVING an already-written value is not the same thing and is now
    allowed, narrowly: a body line that is already an exact
    `<key>: <value>` for one of the three known anchor keys (base_commit,
    reviewed_head, reviewed_base) gets hoisted into frontmatter -- the
    author already wrote the value, it just sits somewhere no machine
    reads it. The body line itself is never removed. A pre-existing
    frontmatter value for the same key is never overwritten; a body value
    that CONTRADICTS an existing frontmatter value is a conflict, warned
    and left untouched, the same pattern as the pre-existing sprint
    conflict check.

(3) A file only gets `kind: review` (+`sprint`) once ALL of WI-0072's
    required fields -- sprint, base_commit-or-reviewed_base, reviewed_head,
    reviewer, last_updated -- are present, counting both what was already
    in frontmatter and what this run just hoisted. Stamping the genre onto
    a document that cannot satisfy the schema would turn a clean lint run
    into a permanently red one with no way back -- worse than leaving the
    document unmigrated and reporting it.

House pattern borrowed from test_freeze_phase_docs.py: invoke the real
entry point as a subprocess against the shipped script (never sourced
internals), against a throwaway project directory (tempfile.mkdtemp),
never this repository's own docs/.

Each check below was seen red at least once via a targeted mutation of the
shipped script (value swap, condition invert, guard removed -- never a
feature removed from the test itself), then restored to its exact original
text, verified byte-identical via md5. The mutation-to-test mapping is
reported in the session summary, not encoded here.
"""

import os
import platform
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "migrate-review-headers.sh"
FRONTMATTER_LIB_PATH = Path(__file__).resolve().parents[1] / "lib" / "frontmatter.sh"

# Every WI-0072-required field, present, so a matching file is COMPLETE and
# eligible for kind: review + sprint to actually be set. Computed hex, never
# a literal 40-char string in the source -- a literal one trips the
# artifact gate's token-blob heuristic (scripts/lib/discipline_gate.sh
# GATE_RE_SECRET_BLOB), the same reason test_phase_docs_lint.py uses
# `"d" * 40` rather than a hardcoded SHA-looking string.
COMPLETE_FRONTMATTER = (
    f"base_commit: {'1' * 40}\n"
    f"reviewed_head: {'2' * 40}\n"
    "reviewer: code-reviewer @ opus\n"
    "last_updated: 21.03.2026\n"
)


def complete_review_text(extra_fm="", body="\n# Review\n"):
    """A docs/reviews/ document with every WI-0072-required field already
    IN FRONTMATTER -- the happy path where Korrektur 3's completeness gate
    is satisfied before the migration even runs, so kind/sprint get set
    regardless of what this run's hoist step does or doesn't find."""
    return f"---\n{COMPLETE_FRONTMATTER}{extra_fm}---\n{body}"


# Every WI-0072-required field EXCEPT reviewed_head -- the fixture for the
# fence-tracking and shape-validation tests below, where the whole point is
# that a body-only reviewed_head value (fenced, malformed, or genuinely
# hoistable) is the ONE thing standing between "incomplete" and "kind:
# review" -- so its fate must be directly observable in both the
# frontmatter block and the completeness verdict.
FRONTMATTER_MISSING_HEAD = (
    f"base_commit: {'1' * 40}\n"
    "reviewer: code-reviewer @ opus\n"
    "last_updated: 21.03.2026\n"
)


class MigrateTestBase(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path(tempfile.mkdtemp(prefix="ccpr-migrate-review-"))
        self.addCleanup(shutil.rmtree, self.project_dir, ignore_errors=True)

    def write(self, rel_path, text):
        """rel_path is relative to project_dir, e.g. 'docs/reviews/foo.md'."""
        path = self.project_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_migrate(self, *args, project_dir=None):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), str(project_dir or self.project_dir), *args],
            capture_output=True, text=True,
        )


class FilenamePatternMatchTest(MigrateTestBase):
    """Only the exact `SPRINT-<N>-review.md` shape is the holistic sprint
    review -- everything else in docs/reviews/ is left untouched, including
    the suffix variants that carry the same sprint number."""

    def test_matching_filename_gets_kind_and_sprint_set(self):
        f = self.write("docs/reviews/SPRINT-21-review.md", complete_review_text())

        result = self.run_migrate()

        text = f.read_text()
        self.assertIn("kind: review", text)
        self.assertIn("sprint: 21", text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_suffix_variant_is_left_untouched(self):
        f = self.write("docs/reviews/SPRINT-21-review-code.md", "---\n---\n\n# Review\n")
        original = f.read_text()

        result = self.run_migrate()

        self.assertEqual(f.read_text(), original)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_suffix_variant_with_ticket_id_is_left_untouched(self):
        f = self.write(
            "docs/reviews/SPRINT-21-review-code-kal150.md", "---\n---\n\n# Review\n"
        )
        original = f.read_text()

        self.run_migrate()

        self.assertEqual(f.read_text(), original)

    def test_per_story_protocol_is_left_untouched(self):
        f = self.write(
            "docs/reviews/sprint-03/WI-0054.md",
            "---\nkind: story-review\nwork_item: WI-0054\n---\n\nBody.\n",
        )
        original = f.read_text()

        self.run_migrate()

        self.assertEqual(f.read_text(), original)

    def test_lowercase_sprint_prefix_is_left_untouched(self):
        f = self.write("docs/reviews/sprint-21-review.md", "---\n---\n\n# Review\n")
        original = f.read_text()

        self.run_migrate()

        self.assertEqual(f.read_text(), original)


class SprintNumberNormalizationTest(MigrateTestBase):
    """The real erfinderwerkstatt corpus zero-pads sprint numbers in the
    filename (SPRINT-01-review.md, SPRINT-02-review.md, SPRINT-03-review.md)
    while its OWN frontmatter already carries the unpadded form (sprint: 3)
    -- the two must compare and write equal, not trigger a false sprint
    conflict warning over a leading zero."""

    def test_zero_padded_filename_number_is_normalized_when_written(self):
        f = self.write("docs/reviews/SPRINT-03-review.md", complete_review_text())

        self.run_migrate()

        text = f.read_text()
        self.assertIn("sprint: 3", text)
        self.assertNotIn("sprint: 03", text)

    def test_zero_padded_filename_does_not_conflict_with_unpadded_existing_sprint(self):
        f = self.write(
            "docs/reviews/SPRINT-03-review.md",
            complete_review_text(extra_fm="sprint: 3\n"),
        )

        result = self.run_migrate()

        self.assertIn("kind: review", f.read_text())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class NoFrontmatterBlockTest(MigrateTestBase):
    """The real NutriMatch corpus: 4 sprint-review-shaped files, zero of
    them carry a `---` block. Since none of WI-0072's five required fields
    can exist without a frontmatter block, and reviewer/last_updated are
    never hoisted (only the three anchor keys are -- Korrektur 2), a
    zero-frontmatter file can never reach completeness through hoisting
    ALONE. It is the block-creation mechanics this class pins, not
    completeness -- `_ensure_frontmatter_block` only runs when there is
    something eligible to actually write."""

    def test_nothing_hoistable_leaves_the_file_completely_untouched(self):
        body = "# Sprint 5 — Holistic Code Review\n\n**Date:** 22.03.2026\n"
        f = self.write("docs/reviews/SPRINT-5-review.md", body)

        result = self.run_migrate()

        self.assertEqual(f.read_text(), body)
        self.assertIn("SPRINT-5-review.md", result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_hoistable_anchor_lines_still_get_lifted_even_without_frontmatter(self):
        body = (
            "# Sprint 5 — Holistic Code Review\n\n"
            f"reviewed_base: {'1' * 40}\n"
            f"reviewed_head: {'2' * 40}\n"
        )
        f = self.write("docs/reviews/SPRINT-5-review.md", body)

        result = self.run_migrate()

        text = f.read_text()
        self.assertTrue(text.startswith("---\n"), text)
        fm_block = text.split("---\n")[1]
        self.assertIn(f"reviewed_base: {'1' * 40}", fm_block)
        self.assertIn(f"reviewed_head: {'2' * 40}", fm_block)
        # reviewer/last_updated are never hoisted -- the document stays
        # incomplete, so kind: review must NOT be set (Korrektur 3).
        self.assertNotIn("kind: review", text)
        self.assertIn(body, text)  # the body lines stay, verbatim
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


class ReconstructionStillForbiddenTest(MigrateTestBase):
    """Korrektur 2 draws the line precisely: RECONSTRUCTING a value that is
    genuinely absent stays forbidden -- this class pins that half only. The
    "moving an existing value" half has its own class below."""

    def test_anchor_fields_absent_in_frontmatter_and_body_stay_absent(self):
        f = self.write("docs/reviews/SPRINT-1-review.md", "---\n---\n\n# Review\n")

        self.run_migrate()

        fm = f.read_text().split("---\n")[1]
        self.assertNotIn("base_commit", fm)
        self.assertNotIn("reviewed_head", fm)
        self.assertNotIn("reviewed_base", fm)

    def test_unknown_body_key_is_never_lifted(self):
        """delta_base is not one of the three known anchor keys the WI-0072
        schema defines -- it stays body text forever, never hoisted, no
        matter how SHA-shaped its value looks."""
        body = f"# Sprint 1 — Holistic Code Review\n\ndelta_base: {'5' * 40}\n"
        f = self.write("docs/reviews/SPRINT-1-review.md", body)

        result = self.run_migrate()

        # Nothing known is hoistable -> file stays completely untouched,
        # same guarantee as NoFrontmatterBlockTest's "nothing hoistable" case.
        self.assertEqual(f.read_text(), body)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_indented_key_value_line_is_not_hoisted(self):
        """Korrektur 2 is explicit: the match is only at the very START of
        a line. An indented `  reviewed_head: ...` (e.g. nested under a
        markdown list item) is not the schema's flat body convention and
        must stay untouched, exactly like an unknown key."""
        body = f"# Sprint 1\n\n- some note\n  reviewed_head: {'4' * 40}\n"
        f = self.write("docs/reviews/SPRINT-1-review.md", body)

        result = self.run_migrate()

        self.assertEqual(f.read_text(), body)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


class MovesExistingAnchorValueTest(MigrateTestBase):
    """Korrektur 2: a body line that is ALREADY an exact `<key>: <value>`
    for one of the three known anchor keys is not a guess -- it gets moved
    (not removed) into frontmatter. This is the real erfinderwerkstatt
    SPRINT-01-review.md shape: reviewed_base/reviewed_head/delta_base/date
    as plain body text directly under the H1, no `---` at all."""

    def test_known_key_bare_body_line_is_hoisted_into_frontmatter(self):
        body = f"# Sprint 1 — Holistic Code Review\n\nreviewed_head: {'4' * 40}\n"
        f = self.write("docs/reviews/SPRINT-1-review.md", body)

        self.run_migrate()

        text = f.read_text()
        fm_block = text.split("---\n")[1]
        self.assertIn(f"reviewed_head: {'4' * 40}", fm_block)
        self.assertIn(body, text)  # body line stays, not removed

    def test_only_the_three_known_anchor_keys_are_hoisted_others_left_in_body(self):
        # Each SHA is computed, not a literal 40-char hex string in the
        # source -- see the module-level note on literal hex strings.
        body = (
            "# Sprint 1 — Holistic Code Review\n\n"
            f"reviewed_base: {'3' * 40}\n"
            f"reviewed_head: {'4' * 40}\n"
            f"delta_base: {'5' * 40}\n"
        )
        f = self.write("docs/reviews/SPRINT-1-review.md", body)

        self.run_migrate()

        text = f.read_text()
        fm_block = text.split("---\n")[1]
        self.assertIn(f"reviewed_base: {'3' * 40}", fm_block)
        self.assertIn(f"reviewed_head: {'4' * 40}", fm_block)
        self.assertNotIn("delta_base", fm_block)
        self.assertIn(body, text)  # original body lines untouched, verbatim

    def test_erfinderwerkstatt_sprint_01_shape_is_hoisted_but_stays_incomplete(self):
        """Direct regression pin for the real corpus shape that surfaced
        this correction: H1 immediately followed (no blank line) by four
        plain-text lines, two of which are known anchor keys, two of which
        are not (delta_base is unknown; date is not part of the WI-0072
        field set at all, so it does not satisfy last_updated either).
        reviewer is entirely absent -- the document must stay incomplete."""
        body = (
            "# Sprint 1 — Holistischer Code-Review (code-reviewer @ opus)\n"
            f"reviewed_base: {'1' * 40}\n"
            f"reviewed_head: {'2' * 40}\n"
            f"delta_base: {'3' * 40}\n"
            "date: 06.08.2026\n"
        )
        f = self.write("docs/reviews/SPRINT-01-review.md", body)

        result = self.run_migrate()

        text = f.read_text()
        fm_block = text.split("---\n")[1]
        self.assertIn(f"reviewed_base: {'1' * 40}", fm_block)
        self.assertIn(f"reviewed_head: {'2' * 40}", fm_block)
        self.assertNotIn("delta_base", fm_block)
        self.assertNotIn("date:", fm_block)
        self.assertNotIn("kind: review", text)
        self.assertIn(body, text)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_pre_existing_frontmatter_anchor_field_with_no_body_duplicate_is_left_untouched(self):
        fake_head = "6" * 40  # computed, see the module-level note
        f = self.write(
            "docs/reviews/SPRINT-2-review.md",
            f"---\nreviewed_head: {fake_head}\nstatus: active\n---\n\n# Review\n",
        )

        self.run_migrate()

        text = f.read_text()
        self.assertIn(f"reviewed_head: {fake_head}", text)

    def test_pre_existing_frontmatter_anchor_field_is_never_overwritten_by_a_hoist(self):
        fake_head = "6" * 40
        other_head = "7" * 40
        f = self.write(
            "docs/reviews/SPRINT-2-review.md",
            f"---\nreviewed_head: {fake_head}\nstatus: active\n---\n\n"
            f"reviewed_head: {other_head}\n",
        )

        result = self.run_migrate()

        text = f.read_text()
        fm_block = text.split("---\n")[1]
        self.assertIn(f"reviewed_head: {fake_head}", fm_block)
        self.assertNotIn(other_head, fm_block)
        self.assertIn("reviewed_head", result.stdout + result.stderr)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_pre_existing_frontmatter_anchor_field_matching_body_is_not_a_conflict(self):
        head = "6" * 40
        f = self.write(
            "docs/reviews/SPRINT-2-review.md",
            f"---\nreviewed_head: {head}\nstatus: active\n---\n\nreviewed_head: {head}\n",
        )

        result = self.run_migrate()

        output = result.stdout + result.stderr
        self.assertNotIn("WARNING:", output)
        self.assertIn("warnings (anchor-field body/frontmatter conflict): 0", output.lower())


class FencedCodeBlockNotHoistedTest(MigrateTestBase):
    """22.08.2026 correction, Befund 1 in review: a review report that
    documents WI-0072's own header schema (commands/p5-review-sprint.md is
    itself an example) routinely shows an illustrative `reviewed_head: ...`
    line inside a fenced code block. That is an example value, not a
    metadatum the author wrote about THIS review -- hoisting it would let
    /gate-p5 treat a stale review as current, worse than leaving the field
    missing. Reproduced directly at the terminal before this class existed
    (see the session report) using the exact body shape below."""

    def test_backtick_fence_example_value_is_not_hoisted(self):
        body = (
            "\n# Sprint 7 — Review\n\n"
            "## Ein Codeblock im Bericht\n\n"
            "```yaml\n"
            f"reviewed_head: {'9' * 40}\n"
            "```\n"
        )
        f = self.write(
            "docs/reviews/SPRINT-7-review.md",
            f"---\n{FRONTMATTER_MISSING_HEAD}---\n{body}",
        )

        result = self.run_migrate()

        text = f.read_text()
        fm_block = text.split("---\n")[1]
        self.assertNotIn("reviewed_head", fm_block)
        self.assertNotIn("kind: review", text)
        output = result.stdout + result.stderr
        self.assertIn("reviewed_head", output)
        self.assertEqual(result.returncode, 1, output)

    def test_tilde_fence_example_value_is_not_hoisted(self):
        body = (
            "\n# Sprint 7 — Review\n\n"
            "~~~yaml\n"
            f"reviewed_head: {'9' * 40}\n"
            "~~~\n"
        )
        f = self.write(
            "docs/reviews/SPRINT-7-review.md",
            f"---\n{FRONTMATTER_MISSING_HEAD}---\n{body}",
        )

        self.run_migrate()

        fm_block = f.read_text().split("---\n")[1]
        self.assertNotIn("reviewed_head", fm_block)

    def test_fence_nested_inside_a_longer_fence_is_not_hoisted(self):
        # An outer 4-backtick fence around an inner 3-backtick fence -- the
        # inner ``` does not close the outer one (CommonMark: a fence only
        # closes with a delimiter run at least as long as the opener), so
        # the reviewed_head line stays inside the OUTER fence the whole way
        # through.
        body = (
            "\n# Sprint 7 — Review\n\n"
            "````markdown\n"
            "```yaml\n"
            f"reviewed_head: {'9' * 40}\n"
            "```\n"
            "````\n"
        )
        f = self.write(
            "docs/reviews/SPRINT-7-review.md",
            f"---\n{FRONTMATTER_MISSING_HEAD}---\n{body}",
        )

        self.run_migrate()

        fm_block = f.read_text().split("---\n")[1]
        self.assertNotIn("reviewed_head", fm_block)

    def test_unclosed_fence_swallows_the_rest_of_the_body(self):
        body = (
            "\n# Sprint 7 — Review\n\n"
            "```yaml\n"
            f"reviewed_head: {'9' * 40}\n"
            # no closing fence -- runs to end of file, CommonMark-correct
        )
        f = self.write(
            "docs/reviews/SPRINT-7-review.md",
            f"---\n{FRONTMATTER_MISSING_HEAD}---\n{body}",
        )

        self.run_migrate()

        fm_block = f.read_text().split("---\n")[1]
        self.assertNotIn("reviewed_head", fm_block)

    def test_fenced_example_in_a_file_without_a_frontmatter_block_is_also_not_hoisted(self):
        # The real erfinderwerkstatt SPRINT-01 shape has NO frontmatter
        # block at all -- fence-tracking must apply in that branch too, not
        # only after a block already exists.
        body = (
            "# Sprint 7 — Review\n\n"
            "```yaml\n"
            f"reviewed_head: {'9' * 40}\n"
            "```\n"
        )
        f = self.write("docs/reviews/SPRINT-7-review.md", body)

        self.run_migrate()

        self.assertEqual(f.read_text(), body)


class AnchorValueShapeValidationTest(MigrateTestBase):
    """22.08.2026 correction, Befund 1 point 2 in review: the second
    defence line -- a hoist candidate must have the SHAPE of a commit SHA
    (`^[0-9a-fA-F]{7,40}$`, the same form phase-docs-lint.sh already
    enforces for these fields). Catches anything a fence gap might miss,
    without inventing a second fence-detection mechanism."""

    def test_non_sha_shaped_bare_value_is_not_hoisted_and_reported(self):
        body = "\n# Review\n\nreviewed_head: not-a-real-commit-sha\n"
        f = self.write(
            "docs/reviews/SPRINT-7-review.md",
            f"---\n{FRONTMATTER_MISSING_HEAD}---\n{body}",
        )

        result = self.run_migrate()

        text = f.read_text()
        fm_block = text.split("---\n")[1]
        self.assertNotIn("reviewed_head", fm_block)
        output = result.stdout + result.stderr
        self.assertIn("WARNING", output)
        self.assertIn("not-a-real-commit-sha", output)
        self.assertEqual(result.returncode, 1, output)

    def test_short_valid_sha_shaped_value_is_still_hoisted(self):
        # 7 hex chars is a valid short commit ref -- the lower bound of the
        # shape check, not just the 40-char full form.
        body = "\n# Review\n\nreviewed_head: abc1234\n"
        f = self.write(
            "docs/reviews/SPRINT-7-review.md",
            f"---\n{FRONTMATTER_MISSING_HEAD}---\n{body}",
        )

        result = self.run_migrate()

        text = f.read_text()
        fm_block = text.split("---\n")[1]
        self.assertIn("reviewed_head: abc1234", fm_block)
        self.assertIn("kind: review", text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CompletenessGateTest(MigrateTestBase):
    """Korrektur 3: kind: review (+sprint) is only set once every WI-0072
    field is present, counting existing frontmatter plus this run's own
    hoist. Otherwise the document is left exactly as the hoist step leaves
    it, unmarked, and reported so a human can fill in the rest."""

    def test_bare_file_stays_unmarked_and_is_reported(self):
        f = self.write("docs/reviews/SPRINT-9-review.md", "---\n---\n\n# Review\n")

        result = self.run_migrate()

        text = f.read_text()
        self.assertNotIn("kind: review", text)
        self.assertIn("SPRINT-9-review.md", result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_file_missing_only_reviewer_stays_unmarked(self):
        f = self.write(
            "docs/reviews/SPRINT-9-review.md",
            "---\n"
            f"base_commit: {'1' * 40}\n"
            f"reviewed_head: {'2' * 40}\n"
            "last_updated: 21.03.2026\n"
            "---\n\n# Review\n",
        )

        result = self.run_migrate()

        text = f.read_text()
        self.assertNotIn("kind: review", text)
        self.assertIn("reviewer", result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_file_with_all_fields_already_present_gets_marked(self):
        f = self.write("docs/reviews/SPRINT-9-review.md", complete_review_text())

        result = self.run_migrate()

        text = f.read_text()
        self.assertIn("kind: review", text)
        self.assertIn("sprint: 9", text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reviewed_base_satisfies_completeness_the_same_as_base_commit(self):
        """The real erfinderwerkstatt SPRINT-02/SPRINT-03 shape: every
        WI-0072 field present, but under `reviewed_base` rather than
        `base_commit` -- both are equally valid (phase-docs-lint.sh
        correction, same date)."""
        f = self.write(
            "docs/reviews/SPRINT-2-review.md",
            "---\n"
            "kind: sprint-review\n"
            f"reviewed_base: {'1' * 40}\n"
            f"reviewed_head: {'2' * 40}\n"
            "reviewer: code-reviewer @ opus\n"
            "last_updated: 09.08.2026\n"
            "---\n\n# Review\n",
        )

        result = self.run_migrate()

        text = f.read_text()
        self.assertIn("kind: review", text)
        self.assertIn("sprint: 2", text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_incomplete_report_names_the_still_missing_fields(self):
        f = self.write(
            "docs/reviews/SPRINT-9-review.md",
            f"---\nbase_commit: {'1' * 40}\n---\n\n# Review\n",
        )

        result = self.run_migrate()

        self.assertIn("reviewed_head", result.stdout)
        self.assertIn("reviewer", result.stdout)
        self.assertIn("last_updated", result.stdout)


class DryRunTest(MigrateTestBase):
    def test_dry_run_on_a_complete_file_writes_nothing(self):
        f = self.write("docs/reviews/SPRINT-4-review.md", complete_review_text())
        original = f.read_text()

        result = self.run_migrate("--dry-run")

        self.assertEqual(f.read_text(), original)
        self.assertIn("SPRINT-4-review.md", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dry_run_on_an_incomplete_file_writes_nothing_and_still_reports_it(self):
        f = self.write("docs/reviews/SPRINT-6-review.md", "---\n---\n\n# Review\n")
        original = f.read_text()

        result = self.run_migrate("--dry-run")

        self.assertEqual(f.read_text(), original)
        self.assertIn("SPRINT-6-review.md", result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_dry_run_on_file_without_frontmatter_still_writes_nothing(self):
        f = self.write("docs/reviews/SPRINT-6-review.md", "# Sprint 6\n\nBody.\n")
        original = f.read_text()

        self.run_migrate("--dry-run")

        self.assertEqual(f.read_text(), original)

    def test_dry_run_hoist_candidate_is_reported_but_not_written(self):
        body = f"# Sprint 6\n\nreviewed_head: {'4' * 40}\n"
        f = self.write("docs/reviews/SPRINT-6-review.md", body)

        result = self.run_migrate("--dry-run")

        self.assertEqual(f.read_text(), body)
        self.assertIn("SPRINT-6-review.md", result.stdout)


class ScopeArgumentTest(MigrateTestBase):
    def test_scope_restricts_the_file_set(self):
        self.write("docs/reviews/SPRINT-1-review.md", complete_review_text())
        self.write("docs/reviews/SPRINT-2-review.md", complete_review_text())

        self.run_migrate("--scope", "SPRINT-1-review.md")

        one = (self.project_dir / "docs/reviews/SPRINT-1-review.md").read_text()
        two = (self.project_dir / "docs/reviews/SPRINT-2-review.md").read_text()
        self.assertIn("kind: review", one)
        self.assertNotIn("kind: review", two)


class NoReviewsDirectoryTest(MigrateTestBase):
    def test_missing_reviews_directory_is_a_clean_no_op(self):
        result = self.run_migrate()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class BadArgumentsTest(MigrateTestBase):
    def test_unknown_option_exits_2(self):
        result = self.run_migrate("--bogus")

        self.assertEqual(result.returncode, 2)

    def test_scope_without_value_exits_2(self):
        result = self.run_migrate("--scope")

        self.assertEqual(result.returncode, 2)


class ModePreservedTest(MigrateTestBase):
    """WI-0021's mode-narrowing defect class applies here too: writing a
    hoisted value (or the complete-path kind/sprint write) still goes
    through mktemp (default 0600) + mv."""

    def test_file_mode_survives_a_complete_write(self):
        f = self.write("docs/reviews/SPRINT-7-review.md", complete_review_text())
        f.chmod(0o644)

        self.run_migrate()

        mode = stat.S_IMODE(f.stat().st_mode)
        self.assertEqual(mode, 0o644)

    def test_file_mode_survives_a_hoist_only_write(self):
        f = self.write(
            "docs/reviews/SPRINT-7-review.md",
            f"# Sprint 7\n\nreviewed_head: {'4' * 40}\n",
        )
        f.chmod(0o644)

        self.run_migrate()

        mode = stat.S_IMODE(f.stat().st_mode)
        self.assertEqual(mode, 0o644)


class ReviewerAndLastUpdatedNeverInventedTest(MigrateTestBase):
    """Only `sprint` (from the filename) and `kind` (from the filename
    match itself) are derived; base_commit/reviewed_head/reviewed_base are
    hoisted only from an exact existing body line (Korrektur 2).
    `reviewer` and `last_updated` are never touched by any of this --
    absent stays absent, present stays untouched."""

    def test_reviewer_and_last_updated_stay_absent_when_not_already_present(self):
        f = self.write("docs/reviews/SPRINT-9-review.md", "---\n---\n\n# Review\n")

        self.run_migrate()

        fm_block = f.read_text().split("---\n")[1]
        self.assertNotIn("reviewer", fm_block)
        self.assertNotIn("last_updated", fm_block)

    def test_pre_existing_reviewer_and_last_updated_are_left_untouched(self):
        f = self.write(
            "docs/reviews/SPRINT-9-review.md",
            "---\nreviewer: code-reviewer @ opus\nlast_updated: 09.08.2026\n---\n\n# Review\n",
        )

        self.run_migrate()

        text = f.read_text()
        self.assertIn("reviewer: code-reviewer @ opus", text)
        self.assertIn("last_updated: 09.08.2026", text)


class SprintConflictWarningTest(MigrateTestBase):
    """A file whose OWN frontmatter already carries a `sprint:` value that
    disagrees with the filename-derived number is a genuine ambiguity --
    the script does not guess which one is right. It warns and leaves the
    file untouched, rather than silently overwriting either value. This
    check runs BEFORE the hoist step, so it applies regardless of whether
    the file would otherwise be complete."""

    def test_conflicting_sprint_value_is_left_untouched_and_warned(self):
        f = self.write(
            "docs/reviews/SPRINT-5-review.md",
            complete_review_text(extra_fm="sprint: 7\n"),
        )
        original = f.read_text()

        result = self.run_migrate()

        self.assertEqual(f.read_text(), original)
        self.assertIn("sprint", result.stdout.lower())
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_matching_sprint_value_is_not_a_conflict(self):
        f = self.write(
            "docs/reviews/SPRINT-5-review.md",
            complete_review_text(extra_fm="sprint: 5\n"),
        )

        result = self.run_migrate()

        self.assertIn("kind: review", f.read_text())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class IdempotentSecondRunTest(MigrateTestBase):
    def test_second_run_on_a_complete_file_makes_no_further_changes(self):
        self.write("docs/reviews/SPRINT-3-review.md", complete_review_text())

        self.run_migrate()
        f = self.project_dir / "docs/reviews/SPRINT-3-review.md"
        after_first = f.read_text()

        self.run_migrate()

        self.assertEqual(f.read_text(), after_first)

    def test_second_run_on_a_partially_hoisted_incomplete_file_makes_no_further_changes(self):
        body = f"# Review\n\nreviewed_head: {'4' * 40}\n"
        self.write("docs/reviews/SPRINT-3-review.md", body)

        self.run_migrate()
        f = self.project_dir / "docs/reviews/SPRINT-3-review.md"
        after_first = f.read_text()

        self.run_migrate()

        self.assertEqual(f.read_text(), after_first)


class MvGuardIsReportedTest(MigrateTestBase):
    """22.08.2026 correction, Befund 3 in review: `_ensure_frontmatter_
    block`'s final `mv "$tmp" "$file"` was unchecked -- a failed rename
    (immutable target, permission race) left an orphaned, unexplained temp
    file with no error message tying it back to the file it was meant to
    replace. `chflags(uchg)` on the TARGET makes the rename fail with a
    normal EPERM (reproduced directly at the terminal, exit 1, no signal)
    -- mktemp still succeeds (creates a new, non-immutable sibling), and
    the write into that sibling still succeeds, so only the `mv` itself is
    exercised."""

    def setUp(self):
        super().setUp()
        if platform.system() != "Darwin":
            self.skipTest("chflags(uchg) is a macOS/BSD mechanism")

    def test_immutable_target_reports_the_stuck_temp_file_and_aborts(self):
        body = f"# Review\n\nreviewed_head: {'4' * 40}\n"
        f = self.write("docs/reviews/SPRINT-9-review.md", body)
        os.chflags(f, stat.UF_IMMUTABLE)
        self.addCleanup(os.chflags, f, 0)

        result = self.run_migrate()

        output = result.stdout + result.stderr
        self.assertIn("failed to move", output.lower())
        leftovers = list((self.project_dir / "docs/reviews").glob("SPRINT-9-review.md.??????"))
        self.assertEqual(len(leftovers), 1, leftovers)
        self.assertIn(str(leftovers[0]), output)
        self.assertNotEqual(result.returncode, 0, output)
        # the original file is untouched -- the failed mv never took effect
        self.assertEqual(f.read_text(), body)


class WriteFailureIsReportedTest(MigrateTestBase):
    """22.08.2026 correction, Befund 2 in review: the write into the temp
    file inside `_ensure_frontmatter_block` (`{ printf; cat; } > "$tmp"`)
    was unchecked -- unlike fm_set/fm_set_many's own write step, which
    already guards with `if ! ... > "$tmp"; then rm -f "$tmp"; ...; fi`. A
    failed write left a half-written temp file with no explanation and no
    non-zero exit naming what happened.

    Forcing a graceful (non-signal) write failure precisely at this one
    step needs a FIXED, pre-lockable temp-file path -- `ulimit -f 0`
    (file-size limit) was tried first and rejected: reproduced directly,
    it kills the WHOLE bash process with SIGXFSZ before `if !` ever
    observes a normal non-zero exit, against both this construct AND the
    pre-existing fm_set write guard equally (bash 3.2, this machine) -- a
    signal-based failure is not equivalent to the return-value-based one
    (full disk, quota) the guard exists for. A stub `mktemp` placed ahead
    of the real one on PATH, always returning one fixed, chflags(uchg)'d
    path, sidesteps that: the write attempt then fails with a normal
    EPERM."""

    def setUp(self):
        super().setUp()
        if platform.system() != "Darwin":
            self.skipTest("chflags(uchg) is a macOS/BSD mechanism")

    def test_write_failure_is_reported_and_original_file_is_untouched(self):
        body = f"# Review\n\nreviewed_head: {'4' * 40}\n"
        f = self.write("docs/reviews/SPRINT-9-review.md", body)

        fixed_tmp = self.project_dir / "docs/reviews/SPRINT-9-review.md.locked"
        stub_dir = self.project_dir / "stub_bin"
        stub_dir.mkdir()
        stub = stub_dir / "mktemp"
        stub.write_text(
            "#!/bin/sh\n"
            f'touch "{fixed_tmp}"\n'
            f'chflags uchg "{fixed_tmp}"\n'
            f'echo "{fixed_tmp}"\n'
        )
        stub.chmod(0o755)
        self.addCleanup(os.chflags, fixed_tmp, 0)

        env = dict(os.environ)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), str(self.project_dir)],
            capture_output=True, text=True, env=env,
        )

        output = result.stdout + result.stderr
        self.assertIn("failed to write", output.lower())
        self.assertIn(str(fixed_tmp), output)
        self.assertNotEqual(result.returncode, 0, output)
        self.assertEqual(f.read_text(), body)


class FrontmatterLibMvGuardTest(unittest.TestCase):
    """22.08.2026 correction, Befund 3 in review, the other two call sites:
    fm_set's and fm_set_many's own final `mv "$tmp" "$file"` were ALSO
    unchecked -- migrate-review-headers.sh is the first caller that writes
    into a foreign project tree, which is what raises the stakes on an
    unexplained leftover, but the gap is older and sits in the shared
    library both callers (and anchor.sh, freeze-phase-docs.sh) depend on.
    Exercised by sourcing scripts/lib/frontmatter.sh directly via
    `bash -c` and calling the functions -- there is no separate
    frontmatter.sh test suite in this repo to extend, and this is the same
    way every real caller uses it."""

    def setUp(self):
        if platform.system() != "Darwin":
            self.skipTest("chflags(uchg) is a macOS/BSD mechanism")
        self.work = Path(tempfile.mkdtemp(prefix="ccpr-fm-mv-guard-"))
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for p in self.work.rglob("*"):
            if p.is_file():
                os.chflags(p, 0)
        shutil.rmtree(self.work, ignore_errors=True)

    def run_bash(self, body):
        script = f'set -euo pipefail\nsource "{FRONTMATTER_LIB_PATH}"\n{body}\n'
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True)

    def test_fm_set_reports_the_stuck_temp_file_when_mv_is_blocked(self):
        target = self.work / "doc.md"
        target.write_text("---\nkey: old\n---\nbody\n", encoding="utf-8")
        os.chflags(target, stat.UF_IMMUTABLE)

        result = self.run_bash(f'fm_set "{target}" key new')

        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("failed to move", output.lower())
        leftovers = list(self.work.glob("doc.md.??????"))
        self.assertEqual(len(leftovers), 1, leftovers)
        self.assertIn(str(leftovers[0]), output)
        os.chflags(target, 0)
        self.assertIn("key: old", target.read_text())

    def test_fm_set_many_reports_the_stuck_temp_file_when_mv_is_blocked(self):
        target = self.work / "doc.md"
        target.write_text("---\nkey: old\n---\nbody\n", encoding="utf-8")
        os.chflags(target, stat.UF_IMMUTABLE)

        result = self.run_bash(f'fm_set_many "{target}" key=new')

        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("failed to move", output.lower())
        leftovers = list(self.work.glob("doc.md.??????"))
        self.assertEqual(len(leftovers), 1, leftovers)
        self.assertIn(str(leftovers[0]), output)
        os.chflags(target, 0)
        self.assertIn("key: old", target.read_text())


if __name__ == "__main__":
    unittest.main()
