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

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertFalse(any("covers:" in w for w in warnings), warnings)

    def test_directory_whose_only_content_is_a_gitkeep_file_is_not_reported_as_empty(self):
        """Deliberate non-decision, kept as documented behaviour, not a
        gap: a directory whose sole content is a `.gitkeep` counts as
        non-empty, same as any other file. `.gitkeep` is a convention, not
        something the filesystem or `find -type f` treats specially -- a
        file is a file. Carving out dotfiles would be a rule nobody asked
        for."""
        gitkeep_dir = self.project_dir / "src" / "gitkeep-only"
        gitkeep_dir.mkdir(parents=True)
        (gitkeep_dir / ".gitkeep").write_text("")
        self.write_doc(
            "architecture/covers-gitkeep-only.md",
            doc_text(extra_lines=["covers: [src/gitkeep-only/]"]),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("covers:" in e for e in errors), errors)
        self.assertFalse(any("covers:" in w for w in warnings), warnings)


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
