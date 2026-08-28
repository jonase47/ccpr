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

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "phase-docs-lint.sh"
FRONTMATTER_LIB = Path(__file__).resolve().parents[1] / "lib" / "frontmatter.sh"


def read_phase_folders(script_path=SCRIPT_PATH):
    """Parses PHASE_FOLDERS=(bare word1 word2 ...) out of phase-docs-lint.sh's
    own source text -- never retyped here (WI-0126). A single-line,
    unquoted bash array (bash 3.2 floor: plain positional arrays only).
    Fails loudly if the shape changes underneath this test."""
    text = script_path.read_text(encoding="utf-8")
    m = re.search(r"^PHASE_FOLDERS=\(([^)]*)\)", text, re.MULTILINE)
    if m is None:
        raise AssertionError("could not find PHASE_FOLDERS=(...) in %s" % script_path)
    return tuple(m.group(1).split())


def read_enum(varname, script_path=SCRIPT_PATH):
    """Parses NAME="a b c" (a space-separated shell-string constant) out of
    a shipped script's own source text -- never retyped here (WI-0126
    tranche 5). The canonical home for this parser shape: it started as a
    private, phase-docs-lint.sh-only helper in
    test_frontmatter_examples_match_the_lint.py (VALID_PHASES/VALID_STATUS),
    lifted here and generalised with a script_path parameter so
    test_manual_lint.py's VALID_KINDS (manual-lint.sh) and test_anchor.py's
    LIVING_FILES (anchor.sh) reuse it instead of each growing a near-
    identical sixth regex. Fails loudly if the constant's DECLARATION
    disappears or changes shape (renamed, or turned into a bash array).
    Measured limit, so nobody reads more into it than it does: a constant
    emptied in place -- NAME="" -- still matches and returns () without
    raising. Every caller pairs this with its own non-zero count pin, which
    is what actually catches that case (WI-0126 tranche 5 review)."""
    text = script_path.read_text(encoding="utf-8")
    m = re.search(r'^%s="([^"]*)"' % re.escape(varname), text, re.MULTILINE)
    if m is None:
        raise AssertionError('could not find %s="..." in %s' % (varname, script_path))
    return tuple(m.group(1).split())


# The six status values phase-docs-lint.sh's VALID_STATUS accepts today,
# parsed from source (WI-0126 tranche 5) rather than retyped -- a retyped
# copy catches the shipped list SHRINKING (the sweep below still expects a
# now-missing value) but not GROWING (a new value is simply never swept);
# CheckDStatusEnumTest's own count-pin test catches the shrink side this
# parse-from-source form cannot. Enumerated individually in
# CheckDStatusEnumTest -- exactly the kind of regression a later "add a 7th
# status" change would otherwise miss silently.
VALID_STATUSES = read_enum("VALID_STATUS")

# The nine phase values phase-docs-lint.sh's VALID_PHASES accepts today,
# parsed from source (WI-0126 tranche 5) -- same shrink/grow reasoning as
# VALID_STATUSES above. Enumerated individually in CheckCPhaseEnumTest,
# whose own count-pin test catches a narrowing this parse alone would not.
VALID_PHASES = read_enum("VALID_PHASES")

# The exact literal the (d) error message embeds ($VALID_STATUS, space-joined).
VALID_STATUS_LITERAL = " ".join(VALID_STATUSES)

VALID_DATE = "04.05.2026"
DATE_WITH_NOTE = "04.05.2026 (cross-phase update)"

# basename set LIVING_FILES skips unconditionally, before check (a) even
# runs. Parsed from source (WI-0126 tranche 5), paired with
# LivingFilesSkipTest's own count-pin test for the shrink side a parse
# alone cannot catch. Duplicated verbatim in anchor.sh's own LIVING_FILES
# (deliberately, per that script's own comment -- sourcing this script
# would execute its whole scan); see test_anchor.py's
# LivingFilesCrossScriptBindingTest for the binding between the two.
LIVING_FILE_NAMES = read_enum("LIVING_FILES")


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

    def init_git_repo(self):
        """Turns self.project_dir into a one-commit git repo, for the
        commit-anchor-family resolvability checks. Returns the HEAD SHA.
        Pattern borrowed from test_artifact_gate.py -- no HOME sandboxing
        needed here (see module docstring), so this uses the real
        environment plus author/committer identity overrides."""
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@host.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@host.invalid",
        }
        subprocess.run(["git", "init", "-q"], cwd=self.project_dir, check=True, env=env)
        (self.project_dir / "README.md").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.project_dir, check=True, env=env)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=self.project_dir, check=True, env=env)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project_dir, check=True,
            capture_output=True, text=True, env=env,
        ).stdout.strip()
        return head

    def add_worktree(self, branch="wt-branch"):
        """Adds a linked worktree of self.project_dir (which must already be
        a git repo via init_git_repo()) at a fresh temp directory and returns
        its path. This is the reproduction vehicle for the `.git`-is-a-file
        case: a linked worktree's `.git` is a FILE containing `gitdir: ...`,
        not a directory -- the same is true for a git submodule's checkout.
        Both are the case GIT_CHECKABLE's `-d "$PROJECT_DIR/.git"` guard
        historically missed."""
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@host.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@host.invalid",
        }
        worktree_dir = Path(tempfile.mkdtemp(prefix="ccpr-phase-docs-lint-wt-"))
        subprocess.run(
            ["git", "worktree", "add", "-q", str(worktree_dir), "-b", branch],
            cwd=self.project_dir, check=True, env=env,
        )

        def cleanup():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_dir)],
                cwd=self.project_dir, env=env, capture_output=True,
            )
            shutil.rmtree(worktree_dir, ignore_errors=True)

        self.addCleanup(cleanup)
        return worktree_dir

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

    def test_valid_phases_count_is_pinned_at_nine(self):
        # WI-0126 tranche 5: VALID_PHASES is now parsed from source, which
        # alone only catches a value being ADDED (the sweep below simply
        # gains an entry). This pin catches a value being REMOVED -- the
        # blind spot the previous retyped copy had in the opposite
        # direction.
        self.assertEqual(9, len(VALID_PHASES))

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

    def test_valid_statuses_count_is_pinned_at_six(self):
        # WI-0126 tranche 5: same shrink-vs-grow reasoning as
        # CheckCPhaseEnumTest.test_valid_phases_count_is_pinned_at_nine above.
        self.assertEqual(6, len(VALID_STATUSES))

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

    # The three cases below are what "optionally with a trailing note" means in
    # the negative, and they exist because the positive tests above could not
    # tell a correct pattern from a loose one. Measured 25.08.2026, against
    # mutants of check (e)'s pattern: `[[:space:]]+` -> `[[:space:]]*`, dropping
    # the parentheses from the note group, and dropping the trailing `$` ALL
    # survived this class -- the ISO case above is rejected by any of them,
    # because `2026-05-04` does not start with DD.MM.YYYY under any variant. The
    # tolerance was written down here and in PHASE_DOC_SCHEMA.md, but its shape
    # was not held by anything. Each case below kills one of those mutants.
    #
    # Same values, same verdicts as memory-lint.sh's check (e) after WI-0106 --
    # one rule, one answer. The two still differ on a well-formed date that is
    # not a day (`32.13.2026`, `99.99.9999`): rejected there by a real parse,
    # accepted here, which has no date check beyond this pattern. Left as is on
    # purpose -- closing it rejects content this script accepts today, which is
    # a promotion decision (ADR-0001), not the pinning of an existing rule.

    def test_a_note_without_parentheses_is_rejected(self):
        """Kills the "note group without parentheses" mutant: the note is a
        parenthesised group, not "anything after the date"."""
        value = f"{VALID_DATE} a trailing note"
        self.write_doc("architecture/date-bare-note.md", doc_text(last_updated=value))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("date-bare-note.md" in e and f"last_updated='{value}' not in format" in e
                for e in errors),
            errors,
        )

    def test_a_note_not_separated_by_whitespace_is_rejected(self):
        """Kills the `[[:space:]]*` mutant: at least one space separates the
        date from its note -- `04.05.2026(WI-0000)` is not the documented form."""
        value = f"{VALID_DATE}(WI-0000)"
        self.write_doc("architecture/date-no-space.md", doc_text(last_updated=value))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("date-no-space.md" in e and f"last_updated='{value}' not in format" in e
                for e in errors),
            errors,
        )

    def test_text_in_front_of_the_date_is_rejected(self):
        """Kills the "drop the leading `^`" mutant. Unlike memory-lint.sh, this
        script has no date parse behind the pattern to catch a prefixed value --
        the anchor is the only thing standing between `updated 04.05.2026` and
        acceptance, so it needs its own case here rather than parity alone."""
        value = f"updated {VALID_DATE}"
        self.write_doc("architecture/date-prefixed.md", doc_text(last_updated=value))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("date-prefixed.md" in e and f"last_updated='{value}' not in format" in e
                for e in errors),
            errors,
        )

    def test_an_unclosed_note_is_rejected(self):
        """Kills the "drop the trailing `$`" mutant: the note group runs to the
        END of the value, so an unclosed parenthesis is not a note."""
        value = f"{VALID_DATE} (unclosed"
        self.write_doc("architecture/date-unclosed.md", doc_text(last_updated=value))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("date-unclosed.md" in e and f"last_updated='{value}' not in format" in e
                for e in errors),
            errors,
        )

    # WI-0107 (26.08.2026): the ADR-0001 promotion closing the gap the block
    # comment above used to document -- a well-formed-but-impossible date
    # (right shape, no such day) is now rejected here too, matching
    # memory-lint.sh's check (e) since WI-0106. Both go through the same
    # pair of helpers in scripts/lib/frontmatter.sh now -- `fm_date_shape_ok`
    # for the pattern, `fm_date_to_epoch` for the parse -- so there is exactly
    # one place left to get this wrong, not two.

    def test_a_shape_valid_but_impossible_month_is_rejected(self):
        """13 is not a month -- `32.13.2026` has the right shape and no
        matching calendar day."""
        value = "32.13.2026"
        self.write_doc("architecture/date-impossible-month.md", doc_text(last_updated=value))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("date-impossible-month.md" in e and f"last_updated='{value}' not in format" in e
                for e in errors),
            errors,
        )

    def test_a_shape_valid_but_impossible_day_is_rejected(self):
        """99.99.9999 has the right shape and no matching calendar day."""
        value = "99.99.9999"
        self.write_doc("architecture/date-impossible-day.md", doc_text(last_updated=value))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("date-impossible-day.md" in e and f"last_updated='{value}' not in format" in e
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
        infos = self.findings(result.stdout, "Info")
        self.assertFalse(any("related:" in e for e in errors), errors)
        # A document-relative hit must stay completely silent -- no root
        # fallback info (WI-0071). The order-swap regression this guards
        # against is exercised more precisely in
        # WI0071RootFallbackTest.test_related_entry_resolvable_document_relative_produces_no_info,
        # where a root-relative hit also exists so a "check root first"
        # implementation would be forced to disagree with this assertion.
        self.assertEqual(infos, [], infos)

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
        infos = self.findings(result.stdout, "Info")
        self.assertFalse(any("related:" in e for e in errors), errors)
        self.assertEqual(infos, [], infos)

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
        infos = self.findings(result.stdout, "Info")
        self.assertFalse(any("parent_index=" in e for e in errors), errors)
        self.assertEqual(infos, [], infos)

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


class WI0071RootFallbackTest(PhaseDocsLintTestBase):
    """WI-0071: related:/parent_index: entries are resolved document-relative
    first (the documented, preferred form) -- but when that misses, a
    project-root-relative resolution is tried before declaring the entry
    dead. PO decision 21.08.2026: a root-relative hit is `info`, not silence
    and not `err` -- silently accepting two bases would be exactly the kind
    of unvalidated frontmatter drift this lint exists to catch. Root-cause:
    real projects write entries like `docs/CONSTITUTION.md`, meaning "from
    the repo root", not "from this file's own directory"."""

    def test_related_entry_resolvable_only_at_project_root_is_info_not_error(self):
        self.write_doc("architecture/ROOT_TARGET.md", doc_text())
        self.write_doc(
            "architecture/main-root.md",
            doc_text(extra_lines=["related: [docs/architecture/ROOT_TARGET.md]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        infos = self.findings(result.stdout, "Info")
        self.assertFalse(any("related:" in e for e in errors), errors)
        self.assertTrue(
            any(
                "main-root.md" in i
                and "related:'docs/architecture/ROOT_TARGET.md'" in i
                and "root fallback" in i
                for i in infos
            ),
            infos,
        )

    def test_related_entry_resolvable_at_neither_base_stays_an_error(self):
        self.write_doc(
            "architecture/main-neither.md",
            doc_text(extra_lines=["related: [docs/architecture/GHOST3.md]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        infos = self.findings(result.stdout, "Info")
        self.assertTrue(
            any(
                "main-neither.md" in e
                and "related:'docs/architecture/GHOST3.md' points to non-existent file" in e
                for e in errors
            ),
            errors,
        )
        self.assertFalse(any("main-neither.md" in i for i in infos), infos)

    def test_related_entry_resolvable_document_relative_produces_no_info(self):
        """Order guard: the entry resolves at BOTH bases (document-relative
        AND project-root), so a "check root first" resolution-order
        regression would still succeed silently -- but would do so via the
        wrong branch. Pinning "no info" here only proves the fallback
        wasn't needed; the entry text intentionally does not collide with
        the wording pinned in the Info-branch tests above, so this test
        cannot pass by accident if the info() call fires unconditionally."""
        self.write_doc("architecture/DOC_RELATIVE_SIDECAR.md", doc_text())
        # Root-relative would resolve against $PROJECT_DIR (not docs/) for an
        # entry with no "docs/" prefix -- plant it there, not via write_doc
        # (which always writes under docs/).
        (self.project_dir / "DOC_RELATIVE_SIDECAR.md").write_text(doc_text(), encoding="utf-8")
        self.write_doc(
            "architecture/main-doc-relative.md",
            doc_text(extra_lines=["related: [DOC_RELATIVE_SIDECAR.md]"]),
        )

        result = self.run_lint()

        infos = self.findings(result.stdout, "Info")
        errors = self.findings(result.stdout, "Errors")
        self.assertEqual(infos, [], infos)
        self.assertFalse(any("related:" in e for e in errors), errors)

    def test_parent_index_entry_resolvable_only_at_project_root_is_info_not_error(self):
        self.write_doc("architecture/ROOT_INDEX.md", doc_text())
        self.write_doc(
            "architecture/detail-root.md",
            doc_text(extra_lines=["parent_index: docs/architecture/ROOT_INDEX.md"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        infos = self.findings(result.stdout, "Info")
        self.assertFalse(any("parent_index=" in e for e in errors), errors)
        self.assertTrue(
            any(
                "detail-root.md" in i
                and "parent_index='docs/architecture/ROOT_INDEX.md'" in i
                and "root fallback" in i
                for i in infos
            ),
            infos,
        )

    def test_parent_index_entry_resolvable_at_neither_base_stays_an_error(self):
        self.write_doc(
            "architecture/detail-neither.md",
            doc_text(extra_lines=["parent_index: docs/architecture/GHOST_INDEX3.md"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        infos = self.findings(result.stdout, "Info")
        self.assertTrue(
            any(
                "detail-neither.md" in e
                and "parent_index='docs/architecture/GHOST_INDEX3.md' points to "
                "non-existent file" in e
                for e in errors
            ),
            errors,
        )
        self.assertFalse(any("detail-neither.md" in i for i in infos), infos)

    def test_parent_index_entry_resolvable_document_relative_produces_no_info(self):
        """Same order guard as the related: case above, for parent_index:."""
        self.write_doc("architecture/DOC_RELATIVE_INDEX.md", doc_text())
        (self.project_dir / "DOC_RELATIVE_INDEX.md").write_text(doc_text(), encoding="utf-8")
        self.write_doc(
            "architecture/detail-doc-relative.md",
            doc_text(extra_lines=["parent_index: DOC_RELATIVE_INDEX.md"]),
        )

        result = self.run_lint()

        infos = self.findings(result.stdout, "Info")
        errors = self.findings(result.stdout, "Errors")
        self.assertEqual(infos, [], infos)
        self.assertFalse(any("parent_index=" in e for e in errors), errors)


class CheckHCoversTest(PhaseDocsLintTestBase):
    """(h) covers: is a new optional field (WI-0020) naming code paths (not
    doc paths) a document describes -- resolved *exclusively* against
    $PROJECT_DIR, no document-relative fallback (unlike WI-0071's
    related:/parent_index: above -- these are code paths, not doc
    cross-refs, so there is no "file's own directory" to fall back from).
    Entries are typically directories, so the existence test must be `-e`,
    not `-f` (a directory always fails `-f`). An existing-but-empty
    directory is a `warn`, not an `err` -- it is not a broken reference,
    but a degenerate one: the list covers nothing (ADR-0009). The check is
    opt-in and runs in every profile, including `reviews` -- it only ever
    fires when `covers:` is actually set, so it cannot regress the "reviews
    only enforces status enum" contract for documents that don't use it."""

    def test_covers_entry_pointing_to_an_existing_nonempty_directory_produces_no_findings(self):
        (self.project_dir / "src" / "domain").mkdir(parents=True)
        (self.project_dir / "src" / "domain" / "widget.py").write_text("# code\n")
        self.write_doc(
            "architecture/covers-ok.md",
            doc_text(extra_lines=["covers: [src/domain/]"]),
        )

        result = self.run_lint()

        # The run must have actually completed, not died silently -- a
        # crash (empty stdout) and a genuine zero-findings result both make
        # the assertFalse()s below vacuously true, so files_scanned() (which
        # raises if the report body is missing) is asserted first.
        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual(result.returncode, 0, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertFalse(any("covers:" in w for w in warnings), warnings)

    def test_covers_entry_block_syntax_existing_nonempty_directory_produces_no_findings(self):
        (self.project_dir / "src" / "adapters").mkdir(parents=True)
        (self.project_dir / "src" / "adapters" / "http.py").write_text("# code\n")
        self.write_doc(
            "architecture/covers-block-ok.md",
            doc_text(extra_lines=["covers:", "  - src/adapters/"]),
        )

        result = self.run_lint()

        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual(result.returncode, 0, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertFalse(any("covers:" in w for w in warnings), warnings)

    def test_covers_entry_nonexistent_path_is_reported_as_error(self):
        self.write_doc(
            "architecture/covers-missing.md",
            doc_text(extra_lines=["covers: [src/ghost/]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any(
                "covers-missing.md" in e
                and "covers:'src/ghost/' points to non-existent path" in e
                for e in errors
            ),
            errors,
        )

    def test_covers_entry_existing_empty_directory_is_reported_as_warning(self):
        (self.project_dir / "src" / "empty").mkdir(parents=True)
        self.write_doc(
            "architecture/covers-empty.md",
            doc_text(extra_lines=["covers: [src/empty/]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertTrue(
            any(
                "covers-empty.md" in w and "covers:'src/empty/' is an empty directory" in w
                for w in warnings
            ),
            warnings,
        )

    def test_covers_entry_directory_holding_only_a_placeholder_is_reported_distinctly(self):
        """WI-0122: a `.gitkeep` satisfies `is_empty_dir`'s `-type f` probe
        (a placeholder IS a file), so the directory does not fall into the
        empty-directory branch above -- but it is not real content either.
        PO decision 27.08.2026 (option b): a distinct warning, not a widened
        empty-directory check, because "reserved, not built" is a different
        and more useful statement than "holds nothing"."""
        (self.project_dir / "src" / "reserved").mkdir(parents=True)
        (self.project_dir / "src" / "reserved" / ".gitkeep").write_text("")
        self.write_doc(
            "architecture/covers-placeholder-only.md",
            doc_text(extra_lines=["covers: [src/reserved/]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        # Distinct from the empty-directory wording ("is an empty
        # directory ... covers nothing") -- the placeholder name itself
        # must be named in the message.
        self.assertFalse(
            any("covers-placeholder-only.md" in w and "is an empty directory" in w for w in warnings),
            warnings,
        )
        self.assertTrue(
            any(
                "covers-placeholder-only.md" in w
                and "covers:'src/reserved/'" in w
                and ".gitkeep" in w
                for w in warnings
            ),
            warnings,
        )

    def test_covers_entry_directory_holding_only_a_dot_keep_placeholder_is_reported(self):
        """Proves the placeholder names live in a real list (AC4), not a
        single hardcoded `.gitkeep` string -- `.keep` must trigger the same
        branch."""
        (self.project_dir / "src" / "reserved-keep").mkdir(parents=True)
        (self.project_dir / "src" / "reserved-keep" / ".keep").write_text("")
        self.write_doc(
            "architecture/covers-placeholder-keep.md",
            doc_text(extra_lines=["covers: [src/reserved-keep/]"]),
        )

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertTrue(
            any(
                "covers-placeholder-keep.md" in w
                and "covers:'src/reserved-keep/'" in w
                and ".keep" in w
                for w in warnings
            ),
            warnings,
        )

    def test_covers_entry_directory_holding_only_a_dot_placeholder_placeholder_is_reported(self):
        """PLACEHOLDER_NAMES lists three names (.gitkeep .keep .placeholder)
        but only the first two had a fixture -- a typo in the third entry
        (e.g. a stray space, or '.placeholde') would pass the whole suite
        today. Mirrors the .gitkeep/.keep tests above so all three list
        entries are independently pinned."""
        (self.project_dir / "src" / "reserved-placeholder").mkdir(parents=True)
        (self.project_dir / "src" / "reserved-placeholder" / ".placeholder").write_text("")
        self.write_doc(
            "architecture/covers-placeholder-dotplaceholder.md",
            doc_text(extra_lines=["covers: [src/reserved-placeholder/]"]),
        )

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertTrue(
            any(
                "covers-placeholder-dotplaceholder.md" in w
                and "covers:'src/reserved-placeholder/'" in w
                and ".placeholder" in w
                for w in warnings
            ),
            warnings,
        )

    def test_covers_entry_directory_holding_two_placeholders_is_reported_once(self):
        """Code-review gap (WI-0122, confirmed independently twice): no
        fixture put TWO placeholder files under one covers: target, so the
        loop in is_placeholder_only_dir() was only ever exercised for its
        first iteration.

        From the second placeholder file onward, the loop's last statement
        `[[ -z "$first" ]] && first="$bn"` evaluates its left side to false
        (first is already set) -- the AND-list's own exit status is 1. Under
        `set -euo pipefail` that looks like it should abort the function
        right there and skip `echo "$first"`, reproducing the exact
        silent-empty-output failure mode this work item exists to close, for
        a different input shape (a multi-file placeholder-only directory
        instead of the crash at the `is_placeholder_only_dir()` call site).
        It does not abort, and -- measured, after this test was written --
        it cannot: the call site is `... || true`, which puts the whole
        command substitution in an AND-OR list and therefore suspends
        `set -e` for the function body outright. Mutation-checked both ways
        against a real project (154 docs, one placeholder-only directory):
        replacing the `&&` with an `if`-form that propagates the failing
        status leaves the full report intact, while ALSO dropping the
        `|| true` brings the silent empty-output death straight back.

        So this test does NOT pin the `set -e` interaction, and no test at
        this call site could -- the guard against that failure mode is the
        `|| true`, and what protects the `|| true` is the five tests that
        turn red when it is removed. What this test does pin is narrower
        and still worth having: a multi-file placeholder-only directory
        completes the run and yields exactly ONE warning, not one per
        placeholder file.

        Two placeholders at different depths (top-level .gitkeep, nested
        .keep) so the multi-file path is genuinely walked, not just a
        same-directory duplicate."""
        (self.project_dir / "src" / "reserved-two").mkdir(parents=True)
        (self.project_dir / "src" / "reserved-two" / ".gitkeep").write_text("")
        (self.project_dir / "src" / "reserved-two" / "nested").mkdir(parents=True)
        (self.project_dir / "src" / "reserved-two" / "nested" / ".keep").write_text("")
        self.write_doc(
            "architecture/covers-two-placeholders.md",
            doc_text(extra_lines=["covers: [src/reserved-two/]"]),
        )

        result = self.run_lint()

        # Liveness first (see placeholder-filtering.md's set -e follow-up):
        # an empty-list result from a crash and a genuine zero-findings run
        # both make a bare assertFalse/assertEqual(count, ...) look
        # trustworthy, so the run's completion is asserted before the
        # finding-shaped assertions below. Exit code is 1 here (not 0) --
        # one warning is the expected, correct outcome, unlike the AC3
        # silent-fixture tests above.
        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual(result.returncode, 1, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)

        placeholder_warnings = [
            w
            for w in warnings
            if "covers-two-placeholders.md" in w and "covers:'src/reserved-two/'" in w
        ]
        self.assertEqual(1, len(placeholder_warnings), warnings)
        self.assertTrue(
            ".gitkeep" in placeholder_warnings[0] or ".keep" in placeholder_warnings[0],
            placeholder_warnings[0],
        )

    def test_covers_entry_directory_holding_placeholder_and_real_file_produces_no_findings(self):
        """AC3: a placeholder alongside real content is not "reserved, not
        built" -- it is built, and stays silent."""
        (self.project_dir / "src" / "started").mkdir(parents=True)
        (self.project_dir / "src" / "started" / ".gitkeep").write_text("")
        (self.project_dir / "src" / "started" / "module.py").write_text("# code\n")
        self.write_doc(
            "architecture/covers-placeholder-plus-real.md",
            doc_text(extra_lines=["covers: [src/started/]"]),
        )

        result = self.run_lint()

        # files_scanned() is the discriminator between "ran and correctly
        # said nothing" and "crashed with empty stdout before saying
        # anything" -- the shape that broke this check silently (WI-0122
        # regression, see test_covers_entry_directory_holding_only_real_
        # files_completes_the_run below for the minimal repro).
        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual(result.returncode, 0, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertFalse(any("covers:" in w for w in warnings), warnings)

    def test_covers_entry_directory_holding_only_real_files_completes_the_run(self):
        """WI-0122 regression: is_placeholder_only_dir() returns 1 (no
        output) the moment it meets a non-placeholder file -- the normal
        case for any real, in-use directory. The call site was a bare
        `var=$(cmd)` assignment; under `set -euo pipefail` a failing command
        substitution kills the whole script, silently (exit 1, zero bytes
        of stdout), before the report is ever printed. Reproduced against a
        real project (games/erfinderwerkstatt, covers: src/adapters/
        purpose-input/, several real files, no placeholder at all) --
        every existing covers: fixture at the time was either empty,
        placeholder-only, or a single file/single-entry directory, so none
        of them exercised the "several real files, iteration must not stop
        on the first non-placeholder one" shape this reproduces."""
        (self.project_dir / "src" / "service").mkdir(parents=True)
        (self.project_dir / "src" / "service" / "handler.py").write_text("# code\n")
        (self.project_dir / "src" / "service" / "router.py").write_text("# code\n")
        self.write_doc(
            "architecture/covers-real-files-only.md",
            doc_text(extra_lines=["covers: [src/service/]"]),
        )

        result = self.run_lint()

        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual(result.returncode, 0, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertFalse(any("covers:" in w for w in warnings), warnings)

    def test_covers_entry_pointing_to_an_existing_file_produces_no_findings(self):
        """Guards `-e` vs `-f`: a single-file covers: entry must stay
        silent. `-f` alone would also accept this case -- the discriminator
        against a `-f`-only implementation is the directory test above,
        which `-f` would wrongly flag as non-existent."""
        (self.project_dir / "src").mkdir(parents=True)
        (self.project_dir / "src" / "single_module.py").write_text("# code\n")
        self.write_doc(
            "architecture/covers-file.md",
            doc_text(extra_lines=["covers: [src/single_module.py]"]),
        )

        result = self.run_lint()

        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual(result.returncode, 0, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertFalse(any("covers:" in w for w in warnings), warnings)

    def test_covers_entry_is_resolved_exclusively_against_project_root(self):
        """No document-relative fallback for covers: -- plant the entry so
        it WOULD resolve under a (wrong) document-relative attempt, and
        assert it is still reported dead because only $PROJECT_DIR counts."""
        (self.docs_dir / "architecture" / "src-lookalike").mkdir(parents=True)
        (self.docs_dir / "architecture" / "src-lookalike" / "x.py").write_text("# code\n")
        self.write_doc(
            "architecture/covers-doc-relative-must-not-resolve.md",
            doc_text(extra_lines=["covers: [src-lookalike/]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any(
                "covers-doc-relative-must-not-resolve.md" in e
                and "covers:'src-lookalike/' points to non-existent path" in e
                for e in errors
            ),
            errors,
        )

    def test_covers_field_absent_produces_no_findings(self):
        self.write_doc("architecture/no-covers.md", doc_text())

        result = self.run_lint()

        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(any("covers" in e for e in self.findings(result.stdout, "Errors")))
        self.assertFalse(any("covers" in w for w in self.findings(result.stdout, "Warnings")))

    def test_covers_check_runs_in_the_reviews_profile_too(self):
        self.write_doc(
            "reviews/covers-in-reviews.md",
            doc_text(
                phase=None, subskill=None, status="active", last_updated=None,
                extra_lines=["covers: [src/ghost-in-reviews/]"],
            ),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any(
                "covers-in-reviews.md" in e
                and "covers:'src/ghost-in-reviews/' points to non-existent path" in e
                for e in errors
            ),
            errors,
        )


class CheckHCoversEmptyDirectoryDetectionTest(PhaseDocsLintTestBase):
    """is_empty_dir() answers "does this directory contain zero entries at
    all" via `find -mindepth 1 -print -quit`, but that probe matches ANY
    entry, including a subdirectory. A directory tree that consists solely
    of nested empty subdirectories therefore counts as non-empty and stays
    silent -- even though it covers zero files, exactly what ADR-0009
    forbids a `covers:` entry from doing unnoticed. Reproduced directly at
    the terminal (21.08.2026) before this test was written: `covers:
    src/leer/` where `src/leer/` contains only the empty `src/leer/
    tiefer_leer/` produced 0 errors, 0 warnings.

    The right question is not "does this directory contain any entry" but
    "does this path cover any actual file" -- so the fix probes for regular
    files at any depth (`find -type f -print -quit`), not just any entry at
    depth 1.
    """

    def test_directory_containing_only_empty_nested_subdirectories_is_reported_as_warning(self):
        (self.project_dir / "src" / "leer" / "tiefer_leer").mkdir(parents=True)
        self.write_doc(
            "architecture/covers-nested-empty.md",
            doc_text(extra_lines=["covers: [src/leer/]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertTrue(
            any(
                "covers-nested-empty.md" in w and "covers:'src/leer/' is an empty directory" in w
                for w in warnings
            ),
            warnings,
        )

    def test_directory_with_a_file_several_levels_deep_produces_no_findings(self):
        deep = self.project_dir / "src" / "tief" / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "file.py").write_text("# code\n")
        self.write_doc(
            "architecture/covers-deep-file.md",
            doc_text(extra_lines=["covers: [src/tief/]"]),
        )

        result = self.run_lint()

        # A real, non-placeholder file is exactly the shape that made
        # is_placeholder_only_dir()'s call site fatal under `set -e`
        # (WI-0122 regression) -- files_scanned() proves the run completed
        # instead of dying silently before the assertFalse()s below.
        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual(result.returncode, 0, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertFalse(any("covers:" in w for w in warnings), warnings)

    def test_directory_whose_only_content_is_a_gitkeep_file_is_not_reported_as_empty(self):
        """`is_empty_dir()` itself is unchanged (WI-0122 PO decision:
        option (b), a distinct warning, not a widened predicate) -- a
        directory whose sole content is a `.gitkeep` still counts as
        non-empty for THIS probe, same as any other file, so it does not
        fall into the "is an empty directory" branch. It is no longer a
        silent non-decision though: check (h) reports it through its own
        placeholder-only branch instead (see CheckHCoversTest's
        placeholder-only tests, which pin the exact wording) -- covered
        here only to confirm this specific probe still stays out of the
        empty-directory branch, not that the directory goes unreported."""
        gitkeep_dir = self.project_dir / "src" / "gitkeep-only"
        gitkeep_dir.mkdir(parents=True)
        (gitkeep_dir / ".gitkeep").write_text("")
        self.write_doc(
            "architecture/covers-gitkeep-only.md",
            doc_text(extra_lines=["covers: [src/gitkeep-only/]"]),
        )

        result = self.run_lint()

        self.assertEqual(self.files_scanned(result.stdout), 1)
        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertFalse(
            any("covers-gitkeep-only.md" in w and "is an empty directory" in w for w in warnings),
            warnings,
        )


class CommitAnchorFamilyTest(PhaseDocsLintTestBase):
    """New check for the commit-anchor family: base_commit, reviewed_head,
    reviewed_base -- CCPR-generated commit-SHA pointers (/p4-sprint sets
    base_commit, /p5-review-sprint sets reviewed_head, /gate-p5 compares
    reviewed_head against HEAD; reviewed_base is a field variant seen in
    the wild). None of the three was validated before this check -- the
    same unvalidated-frontmatter pattern WI-0020 warns about, just
    CCPR-authored rather than user-authored. Form (hex, 7-40 chars) is an
    `err`; unresolvability against the project's git history is a `warn`
    (a shallow clone, rewritten history, or a foreign-repo SHA are all
    legitimate reasons a lint run should not hard-fail on). If the project
    is not a git repository, the resolvability half is skipped entirely
    and silently -- only the form check still applies."""

    ANCHOR_FIELDS = ("base_commit", "reviewed_head", "reviewed_base")

    def test_each_anchor_field_with_malformed_value_is_reported_as_error(self):
        for field in self.ANCHOR_FIELDS:
            with self.subTest(field=field):
                rel = f"architecture/anchor-bad-{field}.md"
                self.write_doc(rel, doc_text(extra_lines=[f"{field}: not-a-sha"]))

                result = self.run_lint()

                errors = self.findings(result.stdout, "Errors")
                self.assertTrue(
                    any(
                        rel in e and f"{field}='not-a-sha' is not a valid commit SHA" in e
                        for e in errors
                    ),
                    (field, errors),
                )
                (self.docs_dir / rel).unlink()

    def test_each_anchor_field_with_too_short_hex_value_is_reported_as_error(self):
        for field in self.ANCHOR_FIELDS:
            with self.subTest(field=field):
                rel = f"architecture/anchor-short-{field}.md"
                # 6 hex chars -- one short of the documented 7-char minimum.
                self.write_doc(rel, doc_text(extra_lines=[f"{field}: abc123"]))

                result = self.run_lint()

                errors = self.findings(result.stdout, "Errors")
                self.assertTrue(
                    any(
                        rel in e and f"{field}='abc123' is not a valid commit SHA" in e
                        for e in errors
                    ),
                    (field, errors),
                )
                (self.docs_dir / rel).unlink()

    def test_each_anchor_field_with_valid_hex_in_a_non_git_project_produces_no_findings(self):
        """self.project_dir deliberately stays a non-git directory here --
        the resolvability half must be skipped entirely (not attempted and
        somehow swallowed), or a "check root guard removed" mutation would
        make `git rev-parse` fail against a non-repository and turn this
        into a false warning."""
        for field in self.ANCHOR_FIELDS:
            with self.subTest(field=field):
                rel = f"architecture/anchor-nongit-{field}.md"
                self.write_doc(rel, doc_text(extra_lines=[f"{field}: abc1234"]))  # 7 hex chars

                result = self.run_lint()

                errors = self.findings(result.stdout, "Errors")
                warnings = self.findings(result.stdout, "Warnings")
                self.assertFalse(any(field in e for e in errors), (field, errors))
                self.assertFalse(any(field in w for w in warnings), (field, warnings))
                (self.docs_dir / rel).unlink()

    def test_anchor_resolvable_to_an_actual_commit_produces_no_findings(self):
        head = self.init_git_repo()
        self.write_doc(
            "architecture/anchor-resolvable.md",
            doc_text(extra_lines=[f"base_commit: {head}"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("base_commit" in e for e in errors), errors)
        self.assertFalse(any("base_commit" in w for w in warnings), warnings)

    def test_anchor_valid_form_but_unresolvable_commit_is_a_warning_not_an_error(self):
        self.init_git_repo()
        fake_sha = "d" * 40  # valid hex, astronomically unlikely to exist
        self.write_doc(
            "architecture/anchor-unresolvable.md",
            doc_text(extra_lines=[f"reviewed_head: {fake_sha}"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("reviewed_head" in e for e in errors), errors)
        self.assertTrue(
            any(
                "anchor-unresolvable.md" in w
                and f"reviewed_head='{fake_sha}' does not resolve to a commit" in w
                for w in warnings
            ),
            warnings,
        )

    def test_anchor_fields_absent_produce_no_findings(self):
        self.write_doc("architecture/no-anchors.md", doc_text())

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        for field in self.ANCHOR_FIELDS:
            self.assertFalse(any(field in e for e in errors), (field, errors))
            self.assertFalse(any(field in w for w in warnings), (field, warnings))

    def test_anchor_check_runs_in_the_reviews_profile_too(self):
        self.write_doc(
            "reviews/anchor-in-reviews.md",
            doc_text(
                phase=None, subskill=None, status="active", last_updated=None,
                extra_lines=["base_commit: not-a-sha"],
            ),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any(
                "anchor-in-reviews.md" in e
                and "base_commit='not-a-sha' is not a valid commit SHA" in e
                for e in errors
            ),
            errors,
        )


class GitCheckableGuardTest(PhaseDocsLintTestBase):
    """The commit-anchor family's resolvability half (check (i)) is gated by
    GIT_CHECKABLE, which the script derives once per run from
    `-d "$PROJECT_DIR/.git"`. That test is true for a normal repository's
    `.git` directory, but FALSE for a linked worktree's or a submodule's
    `.git` -- both are a FILE (`gitdir: /path/to/real/.git/worktrees/...`).
    Before the fix, running the lint from inside a worktree silently skipped
    the resolvability check: same unresolvable base_commit, zero warnings,
    which looks like a clean result rather than a skipped check. Reproduced
    directly at the terminal (21.08.2026) before this test was written."""

    def test_unresolvable_anchor_is_still_warned_from_a_linked_worktree(self):
        self.init_git_repo()
        worktree_dir = self.add_worktree()
        self.assertTrue(
            (worktree_dir / ".git").is_file(),
            "test setup assumption broken: a linked worktree's .git must be "
            "a file, not a directory -- otherwise this test doesn't "
            "reproduce the bug it's meant to catch",
        )
        docs_dir = worktree_dir / "docs" / "architecture"
        docs_dir.mkdir(parents=True)
        (docs_dir / "anchor.md").write_text(
            doc_text(extra_lines=["base_commit: deadbeef"]), encoding="utf-8"
        )

        result = self.run_lint(project_dir=worktree_dir)

        warnings = self.findings(result.stdout, "Warnings")
        self.assertTrue(
            any(
                "anchor.md" in w
                and "base_commit='deadbeef' does not resolve to a commit" in w
                for w in warnings
            ),
            warnings,
        )


class LivingFilesSkipTest(PhaseDocsLintTestBase):
    """LIVING_FILES are skipped entirely, before check (a) even runs -- a
    living file with completely broken/missing frontmatter must still
    produce zero findings, for all six documented names at once."""

    def test_living_file_names_count_is_pinned_at_six(self):
        # WI-0126 tranche 5: LIVING_FILE_NAMES is now parsed from source
        # (read_enum), which alone only catches a name being ADDED. This
        # pin catches one being REMOVED -- the retyped copy's converse
        # blind spot.
        self.assertEqual(6, len(LIVING_FILE_NAMES))

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
    """Scope pin (not a feature test): a document outside the phase folders
    is invisible to a scopeless run today, even with broken frontmatter that
    would otherwise be a hard error. WI-0019 widened PHASE_FOLDERS to include
    `reviews` (with its own restricted check profile -- see
    ReviewsFolderProfileTest below), so this pin now uses `docs/api/` -- a
    folder that stays genuinely outside every profile -- as its "outside"
    example. WI-0020 is expected to widen the scan further; pinning today's
    boundary here makes that widening show up as a deliberate, visible test
    change instead of a silent one.
    """

    def test_document_outside_phase_folders_produces_no_finding_by_default(self):
        self.write_doc("api/outside.md", doc_text(status=None))

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 0)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_scope_glob_reaches_the_same_folder_the_default_scan_cannot_see(self):
        """The other edge of the same pin, still anchored on `reviews/` --
        WI-0019 added `reviews` to PHASE_FOLDERS, so a scopeless run reaches
        it too now (see ReviewsFolderProfileTest), but the *profile* a file
        gets is decided by its path relative to docs/, not by which of the
        two collection paths at phase-docs-lint.sh found it (the default
        PHASE_FOLDERS walk vs. --scope's `find` over the whole docs/ tree).
        This test pins that: reached via --scope, `docs/reviews/*` still
        gets the reviews profile -- (b) required-fields stays silent, but
        (d) status enum still fires on an invalid value.
        """
        self.write_doc(
            "reviews/outside.md",
            doc_text(phase=None, subskill=None, status="obsolete", last_updated=None),
        )

        result = self.run_lint("--scope", "reviews/*")

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("required field missing" in e for e in errors), errors)
        self.assertTrue(
            any("outside.md" in e and "status='obsolete' is not in {" in e for e in errors),
            errors,
        )
        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual(result.returncode, 2, result.stdout)


class PhaseFoldersSweepTest(PhaseDocsLintTestBase):
    """WI-0126: PHASE_FOLDERS (phase-docs-lint.sh:61) names nine folders,
    but before this test only architecture/reviews/quality/operations were
    ever exercised as docs/<folder> anywhere in this suite -- discovery,
    concept, validation, planning and launch had zero coverage as folders
    (the literal string "launch" did not occur anywhere in the test suite
    at all). A folder PHASE_FOLDERS stops naming becomes invisible to a
    scopeless run (DefaultScopeIsLimitedToPhaseFoldersTest above pins that
    exact mechanism for docs/api/), so an invalid `status:` value is the
    right per-entry probe here: check (d) fires in BOTH the "full" and the
    "reviews" profile (doc_profile_for's own docstring: "reviews -- check
    (d) ... plus check (j)"), so one fixture shape proves every entry is
    genuinely REACHED by the default scan without needing a second,
    profile-specific fixture per folder."""

    def test_every_phase_folder_is_reached_by_the_default_scan(self):
        folders = read_phase_folders()
        self.assertEqual(len(folders), 9, folders)  # the count this WI measured
        for folder in folders:
            with self.subTest(folder=folder):
                rel = f"{folder}/bad-status.md"
                self.write_doc(rel, doc_text(status="obsolete"))

                result = self.run_lint()

                errors = self.findings(result.stdout, "Errors")
                expected = f"status='obsolete' is not in {{{VALID_STATUS_LITERAL}}}"
                self.assertTrue(
                    any(rel in e and expected in e for e in errors),
                    (folder, expected, errors),
                )
                (self.docs_dir / rel).unlink()


class ReviewsFolderProfileTest(PhaseDocsLintTestBase):
    """WI-0019: `docs/reviews/**` gets a restricted profile -- only check
    (d) (status enum) applies, and only when `status:` is actually set.
    Checks (a) no-frontmatter, (b) required fields, (c) phase enum, (e) date
    format, (f) related:, (g) parent_index all stay silent there, because
    review reports predate PHASE_DOC_SCHEMA and follow their own frontmatter
    shape (kind, sprint, base_commit or reviewed_base, reviewed_head,
    reviewer, last_updated -- WI-0072, corrected 22.08.2026). `methodology`
    was never part of the validated field set.
    """

    def test_valid_status_in_reviews_produces_no_findings(self):
        self.write_doc(
            "reviews/clean.md",
            doc_text(phase=None, subskill=None, status="active", last_updated=None),
        )

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_invalid_status_in_reviews_is_still_reported_as_error(self):
        self.write_doc(
            "reviews/bad-status.md",
            doc_text(phase=None, subskill=None, status="final", last_updated=None),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("bad-status.md" in e and "status='final' is not in {" in e for e in errors),
            errors,
        )
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_missing_frontmatter_in_reviews_produces_no_findings(self):
        self.write_doc("reviews/no-frontmatter.md", "# Review\n\nNo frontmatter at all.\n")

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 1)

    def test_reviews_folder_is_reached_by_the_default_scan(self):
        """Point 1 of WI-0019: `reviews` joins PHASE_FOLDERS, so a scopeless
        run counts it in Files scanned -- unlike the pre-WI-0019 baseline
        pinned in DefaultScopeIsLimitedToPhaseFoldersTest."""
        self.write_doc(
            "reviews/clean.md",
            doc_text(phase=None, subskill=None, status="active", last_updated=None),
        )

        result = self.run_lint()

        self.assertEqual(self.files_scanned(result.stdout), 1)

    def test_dead_related_entry_is_silenced_in_reviews_but_still_reported_in_phase_folders(self):
        self.write_doc(
            "reviews/dead-related.md",
            doc_text(
                phase=None, subskill=None, status="active", last_updated=None,
                extra_lines=["related: [GHOST.md]"],
            ),
        )
        self.write_doc(
            "architecture/dead-related.md",
            doc_text(extra_lines=["related: [GHOST2.md]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("reviews/dead-related.md" in e for e in errors), errors)
        self.assertTrue(
            any(
                "architecture/dead-related.md" in e
                and "related:'GHOST2.md' points to non-existent file" in e
                for e in errors
            ),
            errors,
        )


# The five keys WI-0072's review-report header schema requires once a
# document self-identifies as the genre via `kind: review` -- the sixth key
# of that schema, `kind` itself, is the trigger, not one of the fields it
# gates.
REVIEW_REQUIRED_FIELDS = ("sprint", "base_commit", "reviewed_head", "reviewer", "last_updated")


def review_doc_text(kind="review", **overrides):
    """Builds a docs/reviews/ document with every WI-0072 field present by
    default, `kind` overridable/omittable (pass None) via the `kind`
    keyword, any REVIEW_REQUIRED_FIELDS entry overridable/omittable the same
    way via **overrides, and any additional key passed through verbatim.
    frontmatter_block()'s own `phase`/`subskill` params are deliberately
    unset (None) -- the `reviews` profile predates and does not use them."""
    defaults = {
        "sprint": "3",
        # Computed, not a literal 40-char hex string in the source -- a
        # literal one trips the artifact gate's token-blob heuristic
        # (scripts/lib/discipline_gate.sh GATE_RE_SECRET_BLOB), the same
        # reason test_phase_docs_lint.py's own CommitAnchorFamilyTest uses
        # `"d" * 40` rather than a hardcoded SHA-looking string.
        "base_commit": "1" * 40,
        "reviewed_head": "2" * 40,
        "reviewer": "code-reviewer @ opus",
    }
    defaults.update(overrides)
    extra_lines = []
    if kind is not None:
        extra_lines.append(f"kind: {kind}")
    for key in ("sprint", "base_commit", "reviewed_head", "reviewer"):
        val = defaults.get(key)
        if val is not None:
            extra_lines.append(f"{key}: {val}")
    last_updated = defaults.get("last_updated", VALID_DATE)
    return doc_text(
        phase=None, subskill=None, status=None,
        last_updated=last_updated, extra_lines=extra_lines,
    )


class ReviewsProfileKindReviewRequiredFieldsTest(PhaseDocsLintTestBase):
    """WI-0072: the review-specific required fields (sprint, base_commit,
    reviewed_head, reviewer, last_updated) are mandatory ONLY once a
    document self-identifies as the genre via `kind: review` -- every other
    document under docs/reviews/ (no `kind:` at all, or a different `kind:`
    such as `story-review`/`review-convention`) stays silent on this check,
    which is what keeps today's real corpus (zero documents carry the
    literal `kind: review`) finding-free without a migration."""

    def test_kind_review_with_all_fields_present_produces_no_findings(self):
        self.write_doc("reviews/complete.md", review_doc_text())

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_kind_review_missing_one_required_field_is_reported_once_per_field(self):
        for field in REVIEW_REQUIRED_FIELDS:
            with self.subTest(field=field):
                self.write_doc("reviews/incomplete.md", review_doc_text(**{field: None}))

                result = self.run_lint()

                errors = self.findings(result.stdout, "Errors")
                self.assertTrue(
                    any(
                        "incomplete.md" in e and f"required field missing: {field}" in e
                        for e in errors
                    ),
                    errors,
                )
                self.assertEqual(result.returncode, 2, result.stdout)

    def test_kind_review_missing_all_fields_reports_each_once(self):
        self.write_doc(
            "reviews/bare-kind.md",
            doc_text(phase=None, subskill=None, status=None, last_updated=None,
                      extra_lines=["kind: review"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        for field in REVIEW_REQUIRED_FIELDS:
            self.assertTrue(
                any("bare-kind.md" in e and f"required field missing: {field}" in e for e in errors),
                errors,
            )
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_no_kind_field_stays_silent_even_without_any_required_field(self):
        """The pre-WI-0072 baseline: none of the three CCPR reference
        projects' review reports carry a `kind:` field at all today -- this
        pins that the new check does not retroactively fail them."""
        self.write_doc(
            "reviews/legacy-no-kind.md",
            doc_text(phase=None, subskill=None, status=None, last_updated=None, extra_lines=[]),
        )

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_different_kind_value_stays_silent_even_without_any_required_field(self):
        """kind: story-review (the per-story-review template in
        docs/reviews/KONVENTION.md) and kind: review-convention (that file
        itself) are a different genre with a different, unvalidated field
        set -- forcing WI-0072's holistic-sprint-review fields onto them
        would be wrong, exactly as the field-set decision says."""
        for other_kind in ("story-review", "review-convention"):
            with self.subTest(kind=other_kind):
                self.write_doc(
                    "reviews/other-kind.md",
                    doc_text(phase=None, subskill=None, status=None, last_updated=None,
                              extra_lines=[f"kind: {other_kind}"]),
                )

                result = self.run_lint()

                self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_kind_review_check_does_not_leak_into_full_profile(self):
        """A phase-folder document carrying `kind: review` (unusual, but not
        forbidden) must not gain the reviews-only required-field check --
        the branch is keyed off `profile == "reviews"`, not off `kind:`
        alone."""
        self.write_doc(
            "architecture/kind-review-in-full-profile.md",
            doc_text(extra_lines=["kind: review"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("required field missing: base_commit" in e for e in errors), errors)
        self.assertFalse(any("required field missing: reviewed_head" in e for e in errors), errors)
        self.assertEqual(result.returncode, 0, result.stdout)


class ReviewsProfileBaseFieldAliasTest(PhaseDocsLintTestBase):
    """WI-0072 correction (22.08.2026): the base-of-reviewed-range
    field is NOT `base_commit` specifically -- it is `base_commit` OR
    `reviewed_base`, exactly the two names the (i) commit-anchor-family
    check already treats as equally valid. The real erfinderwerkstatt
    corpus (SPRINT-02, SPRINT-03) writes `reviewed_base` for every review it
    authored under this schema and never once writes `base_commit` --
    requiring the latter specifically would fail a document that carries
    everything the schema asks for, just under the project's own name for
    it."""

    def _review_doc(self, extra_lines):
        return doc_text(
            phase=None, subskill=None, status=None, last_updated=VALID_DATE,
            extra_lines=[
                "kind: review", "sprint: 2",
                *extra_lines,
                f"reviewed_head: {'2' * 40}",
                "reviewer: code-reviewer @ opus",
            ],
        )

    def test_reviewed_base_alone_satisfies_the_requirement(self):
        self.write_doc(
            "reviews/base-alias.md", self._review_doc([f"reviewed_base: {'1' * 40}"])
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("base_commit" in e for e in errors), errors)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_base_commit_alone_still_satisfies_the_requirement(self):
        self.write_doc(
            "reviews/base-classic.md", self._review_doc([f"base_commit: {'1' * 40}"])
        )

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_both_names_present_satisfies_the_requirement_without_a_duplicate_error(self):
        self.write_doc(
            "reviews/base-both.md",
            self._review_doc([f"base_commit: {'1' * 40}", f"reviewed_base: {'3' * 40}"]),
        )

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_neither_name_present_reports_one_error_naming_both(self):
        self.write_doc("reviews/base-missing.md", self._review_doc([]))

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        matches = [
            e for e in errors
            if "base-missing.md" in e and "base_commit" in e and "reviewed_base" in e
        ]
        self.assertEqual(len(matches), 1, errors)
        self.assertEqual(result.returncode, 2, result.stdout)


if __name__ == "__main__":
    unittest.main()
