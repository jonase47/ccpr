"""test_phase_docs_lint.py -- coverage for scripts/phase-docs-lint.sh.

Ground-up test module for a script that shipped with zero dedicated coverage:
only the generic `bash -n` sweep (test_shell_script_syntax.py) and the
exit-status contract inventory (test_external_tool_exit_status.py) mentioned
it. Two work items (WI-0019: a per-directory lint profile, WI-0020: a new
check (h) for `covers:`) are about to change this exact script -- this module
is the test surface those changes will be measured against, not a feature
in itself.

House pattern borrowed from test_memory_lint.py: invoke the real entry point
as a subprocess against the shipped script (never sourced internals), so the
tests also cover report rendering and the documented exit-code contract (0
clean, 1 warnings, 2 errors). Unlike memory-lint.sh, phase-docs-lint.sh never
reads $HOME -- every path it touches is derived from the explicit
<project-dir> argument -- so no HOME sandboxing is needed here.

Every test drives the SHIPPED scripts/phase-docs-lint.sh against a throwaway
project directory (tempfile.mkdtemp), never this repository's own docs/.

Each check below was red at least once during authoring, via a targeted
mutation of the shipped script (value swap, condition invert, order swap --
never a feature removed from the test itself), then restored to its exact
original text. The mutation-to-test mapping is reported in the session
summary, not encoded here.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "phase-docs-lint.sh"

# The six status values phase-docs-lint.sh's VALID_STATUS accepts today.
# Enumerated individually in CheckDStatusEnumTest -- exactly the kind of
# regression a later "add a 7th status" change would otherwise miss silently.
VALID_STATUSES = ("skeleton", "draft", "active", "frozen", "archived", "living")

# The nine phase values phase-docs-lint.sh's VALID_PHASES accepts today.
# Enumerated individually in CheckCPhaseEnumTest for the same reason as
# VALID_STATUSES above: a later change that narrows the list (e.g. dropping
# P0 or P8 at an edge) would otherwise pass silently if only one
# representative value ("P3") were pinned.
VALID_PHASES = tuple(f"P{n}" for n in range(9))

# The exact literal the (d) error message embeds ($VALID_STATUS, space-joined).
VALID_STATUS_LITERAL = " ".join(VALID_STATUSES)

VALID_DATE = "04.05.2026"
DATE_WITH_NOTE = "04.05.2026 (cross-phase update)"

# basename set LIVING_FILES skips unconditionally, before check (a) even runs.
LIVING_FILE_NAMES = (
    "HANDOVER.md", "BASELINE.md", "BACKLOG.md", "SPRINT.md", "MEMORY.md", "instincts.md",
)


def frontmatter_block(phase="P3", subskill="widget-x", status="draft",
                       last_updated=VALID_DATE, extra_lines=()):
    """Build a minimal frontmatter block. Pass a field as None to omit it."""
    lines = []
    if phase is not None:
        lines.append(f"phase: {phase}")
    if subskill is not None:
        lines.append(f"subskill: {subskill}")
    if status is not None:
        lines.append(f"status: {status}")
    if last_updated is not None:
        lines.append(f"last_updated: {last_updated}")
    lines.extend(extra_lines)
    return "---\n" + "\n".join(lines) + "\n---\n"


def doc_text(body="\n# Doc\n\nBody.\n", **fm_kwargs):
    return frontmatter_block(**fm_kwargs) + body


class PhaseDocsLintTestBase(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path(tempfile.mkdtemp(prefix="ccpr-phase-docs-lint-"))
        self.addCleanup(shutil.rmtree, self.project_dir, ignore_errors=True)
        self.docs_dir = self.project_dir / "docs"

    def write_doc(self, rel_path, text):
        """rel_path is relative to docs/, e.g. 'architecture/foo.md'."""
        path = self.docs_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_lint(self, *args, project_dir=None):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), str(project_dir or self.project_dir), *args],
            capture_output=True, text=True,
        )

    @staticmethod
    def findings(output, heading):
        """Collect the bullet lines of one report section ('Errors' / 'Warnings' / 'Info')."""
        collected = []
        collecting = False
        for line in output.splitlines():
            if line.startswith("## "):
                collecting = line.startswith(f"## {heading} (")
            elif collecting and line.startswith("- "):
                collected.append(line[2:])
        return collected

    @staticmethod
    def files_scanned(output):
        for line in output.splitlines():
            if line.startswith("**Files scanned:**"):
                return int(line.split(":**", 1)[1].strip())
        raise AssertionError(f"no 'Files scanned' line in output: {output!r}")


class CleanDocumentBaselineTest(PhaseDocsLintTestBase):
    """The shared negative fixture: a fully valid document must stay silent.

    This is what makes every other check's "no finding on a clean doc" claim
    meaningful -- if the baseline itself produced findings, every negative
    assertion in this module would be vacuous.
    """

    def test_valid_document_produces_no_findings_and_exits_clean(self):
        self.write_doc("architecture/clean.md", doc_text())

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 1)


class CheckAFrontmatterPresenceTest(PhaseDocsLintTestBase):
    """(a) No `---` frontmatter block at all -> warn, and the file is skipped
    for every later check (the `continue` right after)."""

    def test_document_without_frontmatter_is_warned(self):
        self.write_doc("architecture/plain.md", "# Just a heading\n\nNo frontmatter here.\n")

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertTrue(
            any("plain.md" in w and "no YAML frontmatter" in w for w in warnings), warnings
        )
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_document_with_frontmatter_is_not_warned_for_missing_frontmatter(self):
        self.write_doc("architecture/has-fm.md", doc_text())

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("no YAML frontmatter" in w for w in warnings), warnings)


class CheckBRequiredFieldsTest(PhaseDocsLintTestBase):
    """(b) phase, subskill, status, last_updated are each mandatory -- tested
    individually so a later change that drops one from the required list
    cannot hide behind the other three still firing."""

    def test_each_required_field_reported_missing_on_its_own(self):
        required = ["phase", "subskill", "status", "last_updated"]
        for field in required:
            with self.subTest(field=field):
                omitted = {f: None for f in required if f == field}
                rel = f"architecture/req-{field}.md"
                self.write_doc(rel, doc_text(**omitted))

                result = self.run_lint()

                errors = self.findings(result.stdout, "Errors")
                self.assertTrue(
                    any(
                        rel in e and f"required field missing: {field}" in e
                        for e in errors
                    ),
                    (field, errors),
                )
                # Clean up so the next subTest's file count / findings stay isolated.
                (self.docs_dir / rel).unlink()

    def test_document_with_all_required_fields_is_not_reported(self):
        self.write_doc("architecture/complete.md", doc_text())

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("required field missing" in e for e in errors), errors)


class CheckCPhaseEnumTest(PhaseDocsLintTestBase):
    """(c) phase must be one of P0..P8."""

    def test_valid_phase_value_is_not_reported(self):
        self.write_doc("architecture/valid-phase.md", doc_text(phase="P3"))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("is not in {P0" in e for e in errors), errors)

    def test_every_valid_phase_value_is_accepted(self):
        for phase in VALID_PHASES:
            with self.subTest(phase=phase):
                rel = f"architecture/phase-{phase}.md"
                self.write_doc(rel, doc_text(phase=phase))

                result = self.run_lint()

                errors = self.findings(result.stdout, "Errors")
                self.assertFalse(
                    any(rel in e and "is not in {P0" in e for e in errors), (phase, errors)
                )
                (self.docs_dir / rel).unlink()

    def test_invalid_phase_value_is_reported_as_error(self):
        self.write_doc("architecture/invalid-phase.md", doc_text(phase="P9"))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("invalid-phase.md" in e and "phase='P9' is not in {P0…P8}" in e for e in errors),
            errors,
        )


class CheckDStatusEnumTest(PhaseDocsLintTestBase):
    """(d) status must be one of the six VALID_STATUS values -- each checked
    individually. This is exactly the sub-check WI-0019/WI-0020 could
    silently narrow (e.g. by editing VALID_STATUS) without a single test
    noticing if only one representative value were pinned."""

    def test_every_valid_status_value_is_accepted(self):
        for status in VALID_STATUSES:
            with self.subTest(status=status):
                rel = f"architecture/status-{status}.md"
                self.write_doc(rel, doc_text(status=status))

                result = self.run_lint()

                errors = self.findings(result.stdout, "Errors")
                self.assertFalse(
                    any(rel in e and "is not in {" in e for e in errors), (status, errors)
                )
                (self.docs_dir / rel).unlink()

    def test_invalid_status_value_is_reported_as_error(self):
        self.write_doc("architecture/bad-status.md", doc_text(status="obsolete"))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        expected = f"status='obsolete' is not in {{{VALID_STATUS_LITERAL}}}"
        self.assertTrue(
            any("bad-status.md" in e and expected in e for e in errors), (expected, errors)
        )


class CheckELastUpdatedFormatTest(PhaseDocsLintTestBase):
    """(e) last_updated must be DD.MM.YYYY, optionally with a trailing note
    in parentheses -- both forms are accepted."""

    def test_plain_date_is_accepted(self):
        self.write_doc("architecture/date-plain.md", doc_text(last_updated=VALID_DATE))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("last_updated=" in e for e in errors), errors)

    def test_date_with_parenthesised_note_is_accepted(self):
        self.write_doc("architecture/date-note.md", doc_text(last_updated=DATE_WITH_NOTE))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("last_updated=" in e for e in errors), errors)

    def test_iso_date_format_is_rejected(self):
        self.write_doc("architecture/date-iso.md", doc_text(last_updated="2026-05-04"))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("date-iso.md" in e and "last_updated='2026-05-04' not in format" in e
                for e in errors),
            errors,
        )


class CheckFRelatedCrossRefsTest(PhaseDocsLintTestBase):
    """(f) related: entries are resolved relative to the file's own
    directory. fm_list supports two spellings -- inline `[a, b]` and a YAML
    block -- both exercised here so a regression in either extraction path
    would be caught."""

    def test_inline_related_pointing_to_an_existing_file_is_not_reported(self):
        self.write_doc("architecture/SIDECAR.md", doc_text())
        self.write_doc(
            "architecture/main-inline-ok.md",
            doc_text(extra_lines=["related: [SIDECAR.md]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("related:" in e for e in errors), errors)

    def test_inline_related_pointing_to_a_missing_file_is_reported(self):
        self.write_doc(
            "architecture/main-inline-bad.md",
            doc_text(extra_lines=["related: [GHOST.md]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("main-inline-bad.md" in e and "related:'GHOST.md' points to non-existent file"
                in e for e in errors),
            errors,
        )

    def test_block_related_pointing_to_an_existing_file_is_not_reported(self):
        self.write_doc("architecture/SIDECAR2.md", doc_text())
        self.write_doc(
            "architecture/main-block-ok.md",
            doc_text(extra_lines=["related:", "  - SIDECAR2.md"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("related:" in e for e in errors), errors)

    def test_block_related_pointing_to_a_missing_file_is_reported(self):
        self.write_doc(
            "architecture/main-block-bad.md",
            doc_text(extra_lines=["related:", "  - GHOST2.md"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("main-block-bad.md" in e and "related:'GHOST2.md' points to non-existent file"
                in e for e in errors),
            errors,
        )


class CheckGParentIndexTest(PhaseDocsLintTestBase):
    """(g) parent_index -- same file-must-exist rule as (f), single field."""

    def test_parent_index_pointing_to_an_existing_file_is_not_reported(self):
        self.write_doc("architecture/INDEX.md", doc_text())
        self.write_doc(
            "architecture/detail-ok.md",
            doc_text(extra_lines=["parent_index: INDEX.md"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("parent_index=" in e for e in errors), errors)

    def test_parent_index_pointing_to_a_missing_file_is_reported(self):
        self.write_doc(
            "architecture/detail-bad.md",
            doc_text(extra_lines=["parent_index: GHOST_INDEX.md"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("detail-bad.md" in e and "parent_index='GHOST_INDEX.md' points to "
                "non-existent file" in e for e in errors),
            errors,
        )


class LivingFilesSkipTest(PhaseDocsLintTestBase):
    """LIVING_FILES are skipped entirely, before check (a) even runs -- a
    living file with completely broken/missing frontmatter must still
    produce zero findings, for all six documented names at once."""

    def test_all_six_living_filenames_are_skipped_even_with_broken_frontmatter(self):
        for name in LIVING_FILE_NAMES:
            # No leading "---" at all -- would trip check (a) if not skipped.
            self.write_doc(f"architecture/{name}", "Not a frontmatter document at all.\n")

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        # Still counted in the scan total -- only the per-file checks are skipped.
        self.assertEqual(self.files_scanned(result.stdout), len(LIVING_FILE_NAMES))


class ExitCodePrecedenceTest(PhaseDocsLintTestBase):
    """Errors outrank warnings in the exit code -- a mix must exit 2, not 1."""

    def test_error_and_warning_together_exit_2(self):
        self.write_doc("architecture/has-error.md", doc_text(status=None))
        self.write_doc("architecture/has-warning.md", "No frontmatter.\n")

        result = self.run_lint()

        self.assertEqual(result.returncode, 2, result.stdout)


class ReportShapeTest(PhaseDocsLintTestBase):
    """Files scanned and the per-section counts in the headers must match
    the actual finding counts."""

    def test_files_scanned_and_section_counts_match_reality(self):
        self.write_doc("architecture/one-error.md", doc_text(status=None))
        self.write_doc("architecture/one-warning.md", "No frontmatter.\n")
        self.write_doc("architecture/clean.md", doc_text())

        result = self.run_lint()

        self.assertEqual(self.files_scanned(result.stdout), 3)
        self.assertIn("## Errors (1)", result.stdout)
        self.assertIn("## Warnings (1)", result.stdout)
        self.assertIn("## Info (0)", result.stdout)


class ScopeArgumentTest(PhaseDocsLintTestBase):
    """--scope and --scope=<glob> filter the scan relative to docs/. Both
    spellings are parsed on independent code paths and are tested
    separately for that reason."""

    def setUp(self):
        super().setUp()
        self.write_doc("architecture/scoped-in.md", doc_text(status=None))
        self.write_doc("planning/scoped-out.md", doc_text(status=None))

    def test_scope_flag_with_space_restricts_the_scan(self):
        result = self.run_lint("--scope", "architecture/*")

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(any("scoped-in.md" in e for e in errors), errors)
        self.assertFalse(any("scoped-out.md" in e for e in errors), errors)
        self.assertEqual(self.files_scanned(result.stdout), 1)

    def test_scope_flag_with_equals_restricts_the_scan(self):
        result = self.run_lint("--scope=architecture/*")

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(any("scoped-in.md" in e for e in errors), errors)
        self.assertFalse(any("scoped-out.md" in e for e in errors), errors)
        self.assertEqual(self.files_scanned(result.stdout), 1)


class ArgumentAndEnvironmentEdgeCasesTest(PhaseDocsLintTestBase):
    def test_unknown_second_positional_argument_exits_2(self):
        result = self.run_lint("some-extra-argument")

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("unknown argument", result.stderr)

    def test_missing_docs_directory_exits_0_with_a_message(self):
        # self.docs_dir is deliberately never created by this test.
        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("no docs/ structure found", result.stdout)


class DefaultScopeIsLimitedToPhaseFoldersTest(PhaseDocsLintTestBase):
    """Scope pin (not a feature test): a document outside the eight
    PHASE_FOLDERS is invisible to a scopeless run today, even with broken
    frontmatter that would otherwise be a hard error. WI-0020 is expected to
    widen the scan; pinning today's boundary here makes that widening show
    up as a deliberate, visible test change instead of a silent one.
    """

    def test_document_outside_phase_folders_produces_no_finding_by_default(self):
        self.write_doc("reviews/outside.md", doc_text(status=None))

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 0)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_scope_glob_reaches_the_same_folder_the_default_scan_cannot_see(self):
        """The other edge of the same pin: the two collection paths at
        phase-docs-lint.sh:86-104 diverge on purpose -- the default scan
        walks only PHASE_FOLDERS, but --scope's `find` walks the entire
        docs/ tree and filters by glob afterwards, so it already reaches a
        folder the default scan is blind to. WI-0019/WI-0020 are about to
        touch this exact collection switch; pinning both edges here (this
        test + the default-scope test above) makes any future widening of
        either path show up as a deliberate test change instead of a
        silent one.
        """
        self.write_doc("reviews/outside.md", doc_text(status=None))

        result = self.run_lint("--scope", "reviews/*")

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("outside.md" in e and "required field missing: status" in e for e in errors),
            errors,
        )
        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual(result.returncode, 2, result.stdout)


if __name__ == "__main__":
    unittest.main()
