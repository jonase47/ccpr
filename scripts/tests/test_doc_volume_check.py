"""test_doc_volume_check.py -- WI-0101: first test coverage for
scripts/doc-volume-check.sh.

## Why this exists

The script shipped with zero dedicated coverage: only the generic `bash -n`
sweep (test_shell_script_syntax.py) and the exit-status contract inventory
(test_external_tool_exit_status.py) touched it, and neither ever RUNS it.

WI-0101's defect lived in `h2_count()`:

    grep -c '^## [^#]' "$file" 2>/dev/null || echo 0

`grep -c` PRINTS "0" and STILL exits 1 when nothing matched, so the `||` arm
fired on top of the printed zero and the function emitted "0\n0". Both
`(( ))` tests in `split_suggestion()` then aborted with a syntax error on
stderr, and the report line broke mid-sentence:

    - <file> (46 KB) -> no obvious splitting point (0
    0 H2 sections) -- review content

The VERDICT was accidentally right (both arithmetic tests failed, so the
branch fell through to the else arm, which is the correct advice for a file
with no H2 sections). Broken were the output line and the stderr noise -- so
these tests pin the rendered line and the silence of stderr, not just the
suggestion keyword.

## Why the fixture shapes are what they are

The defect has an EXACT precondition: a file with zero `## ` headings, big
enough to reach the 25 KB reporting threshold. A file WITH H2 sections never
triggers it -- which is why it survived so long. Every test therefore states
which side of that precondition it stands on, and the positive controls
(H2 present) exist so a future "fix" that simply stopped counting could not
pass this module.

Each test drives the SHIPPED scripts/doc-volume-check.sh as a subprocess
against a throwaway docs root (tempfile.mkdtemp), never this repository's
own docs/.

RED proof: with `|| echo 0` restored as the last arm of `h2_count()` (the
exact pre-fix text, not an assertion removed here), the zero-H2 cases fail
on both counts -- non-empty stderr and a truncated bullet line.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "doc-volume-check.sh"

# A body line that is not a heading of any level, used to pad a fixture past
# a size threshold without changing its H2 count.
FILLER = "Body text that carries no heading marker at all.\n"

# The three size bands the script documents: info 25-40 KB, warning 40-50 KB,
# error >=50 KB. Byte targets sit mid-band so the KB rounding in size_kb()
# ((bytes + 512) / 1024) cannot drift a fixture across a boundary.
INFO_BYTES = 30 * 1024
WARNING_BYTES = 44 * 1024
ERROR_BYTES = 55 * 1024


def padded(prefix, target_bytes=INFO_BYTES):
    """Grow `prefix` past `target_bytes` using heading-free filler."""
    text = prefix
    while len(text.encode("utf-8")) < target_bytes:
        text += FILLER
    return text


def doc_with_h2(section_count, target_bytes=INFO_BYTES):
    text = "# Title\n\n"
    for i in range(section_count):
        text += f"## Section {i}\n\nSome prose under the section.\n\n"
    return padded(text, target_bytes)


def doc_without_h2(target_bytes=INFO_BYTES):
    return padded("# Title\n\nOne H1 only, no H2 anywhere in this file.\n", target_bytes)


def doc_with_h3_only(target_bytes=INFO_BYTES):
    """The real-world shape that surfaced the defect in this repo's own docs:
    a long file whose every section heading is an H3, so `^## [^#]` matches
    nothing even though `^##` matches six times."""
    text = "# Title\n\n"
    for i in range(6):
        text += f"### Subsection {i}\n\nSome prose under the subsection.\n\n"
    return padded(text, target_bytes)


class DocVolumeCheckTestBase(unittest.TestCase):
    def setUp(self):
        self.docs_root = self.fresh_docs_root()

    def fresh_docs_root(self):
        root = Path(tempfile.mkdtemp(prefix="ccpr-doc-volume-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    def write_doc(self, rel_path, text, docs_root=None):
        path = (docs_root or self.docs_root) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_check(self, docs_root=None):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), str(docs_root or self.docs_root)],
            capture_output=True, text=True,
        )

    @staticmethod
    def reported_kb(path):
        """Mirror of size_kb(): (bytes + 512) / 1024, integer division."""
        return (path.stat().st_size + 512) // 1024

    @staticmethod
    def bullets(output):
        """Every finding line of the report, across all three sections."""
        return [line[2:] for line in output.splitlines() if line.startswith("- ")]

    @staticmethod
    def files_scanned(output):
        """WI-0125: mirrors test_phase_docs_lint.py's/test_manual_lint.py's
        identically-named helper -- raises if the "**Files scanned:**" line
        is missing, so a caller can tell a genuine zero-finding run apart
        from one that never reached the report at all (or reached it with
        an empty/wrong SCOPE)."""
        for line in output.splitlines():
            if line.startswith("**Files scanned:**"):
                return int(line.split(":**", 1)[1].strip())
        raise AssertionError(f"no 'Files scanned' line in output: {output!r}")


class BaselineTest(DocVolumeCheckTestBase):
    """The shared negative fixture. Without it, every "exactly one bullet"
    assertion below could pass on a script that reported nothing at all."""

    def test_a_file_below_the_info_threshold_is_not_reported(self):
        self.write_doc("small.md", "# Title\n\nShort enough to stay unreported.\n")
        result = self.run_check()
        # Liveness first (WI-0125): stderr=="" / bullets==[] / returncode==0
        # ALSO hold if the script scanned zero files (a wrong/empty SCOPE),
        # not just on a genuine clean run over the one real file below --
        # see BaselineLivenessRedProofTest for the measured proof.
        self.assertEqual(self.files_scanned(result.stdout), 1)
        self.assertEqual("", result.stderr)
        self.assertEqual([], self.bullets(result.stdout))
        self.assertEqual(0, result.returncode, result.stdout)


class BaselineLivenessRedProofTest(DocVolumeCheckTestBase):
    """Proves BaselineTest's PRE-fix shape (stderr/bullets/returncode only,
    no scope assertion) was genuinely unguarded -- not merely "could
    theoretically be", per G-107/G-109. Mutates a SCRATCH COPY of the
    script's file-collection `find` glob to a pattern that matches nothing
    IN THE SAME, REAL `$DOCS_ROOT` (not a nonexistent path -- that would
    make `find` itself print to stderr, a liveness signal of its own kind
    and not the silent scope-collapse this fix targets), so it reports
    zero files scanned even though the fixture's one real file exists and
    is well below every size threshold. The OLD-shaped assertions
    (stderr/bullets/returncode) all still pass on that mutant -- a wrong,
    empty SCOPE is indistinguishable from a genuine clean run by those
    three alone. The shipped file itself is never touched; mutate-then-
    restore is not needed because the mutation never happens on the
    tracked file (G-143)."""

    FIND_NEEDLE = 'find "$DOCS_ROOT" -type f -name "*.md" -not -path "*/.handover-archive/*"'

    def test_a_zero_scope_scan_passes_the_old_assertions_and_fails_the_new_one(self):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn(
            self.FIND_NEEDLE, original,
            "fixture assumption broken -- the file-collection find's own literal line changed, update this test",
        )
        mutated = original.replace(
            self.FIND_NEEDLE,
            'find "$DOCS_ROOT" -type f -name "*.NEVER_MATCHES_ANYTHING_zzz"',
            1,
        )
        self.assertNotEqual(original, mutated)

        scratch_dir = Path(tempfile.mkdtemp(prefix="ccpr-doc-volume-mutant-"))
        self.addCleanup(shutil.rmtree, scratch_dir, ignore_errors=True)
        mutant_script = scratch_dir / "doc-volume-check.sh"
        mutant_script.write_text(mutated, encoding="utf-8")

        self.write_doc("small.md", "# Title\n\nShort enough to stay unreported.\n")
        result = subprocess.run(
            ["bash", str(mutant_script), str(self.docs_root)],
            capture_output=True, text=True,
        )

        # The pre-fix BaselineTest shape: all three still pass, vacuously.
        self.assertEqual("", result.stderr)
        self.assertEqual([], self.bullets(result.stdout))
        self.assertEqual(0, result.returncode, result.stdout)
        # What the fix actually catches: the scope collapsed to zero, not one.
        self.assertEqual(0, self.files_scanned(result.stdout))

        self.assertEqual(original, SCRIPT_PATH.read_text(encoding="utf-8"), "shipped file content changed")


class FileWithoutH2SectionsTest(DocVolumeCheckTestBase):
    """WI-0101's precondition side: zero H2 sections."""

    def test_the_bullet_line_is_complete_and_stderr_stays_silent(self):
        path = self.write_doc("no-h2.md", doc_without_h2())
        result = self.run_check()
        self.assertEqual("", result.stderr)
        self.assertEqual(
            [
                f"no-h2.md ({self.reported_kb(path)} KB) → "
                "no obvious splitting point (0 H2 sections) — review content"
            ],
            self.bullets(result.stdout),
        )

    def test_h3_headings_alone_still_count_as_zero_h2(self):
        path = self.write_doc("h3-only.md", doc_with_h3_only())
        result = self.run_check()
        self.assertEqual("", result.stderr)
        self.assertEqual(
            [
                f"h3-only.md ({self.reported_kb(path)} KB) → "
                "no obvious splitting point (0 H2 sections) — review content"
            ],
            self.bullets(result.stdout),
        )

    def test_the_zero_h2_verdict_is_unchanged_in_every_size_band(self):
        """The suggestion text is band-independent; only the KB figure and
        the exit code move. Pins that the fix changed OUTPUT, not JUDGEMENT."""
        for band_bytes, expected_exit in (
            (INFO_BYTES, 0), (WARNING_BYTES, 1), (ERROR_BYTES, 2),
        ):
            with self.subTest(band_bytes=band_bytes):
                docs_root = self.fresh_docs_root()
                path = self.write_doc("banded.md", doc_without_h2(band_bytes), docs_root)
                result = self.run_check(docs_root)
                self.assertEqual("", result.stderr)
                self.assertEqual(
                    [
                        f"banded.md ({self.reported_kb(path)} KB) → "
                        "no obvious splitting point (0 H2 sections) — review content"
                    ],
                    self.bullets(result.stdout),
                )
                self.assertEqual(expected_exit, result.returncode, result.stdout)


class FileWithH2SectionsTest(DocVolumeCheckTestBase):
    """The positive controls: a counting fix that silently stopped counting
    (or always answered 0) would pass the zero-H2 cases above and fail here."""

    def test_six_or_more_sections_suggest_splitting_per_h2(self):
        path = self.write_doc("many.md", doc_with_h2(7))
        result = self.run_check()
        self.assertEqual("", result.stderr)
        self.assertEqual(
            [f"many.md ({self.reported_kb(path)} KB) → split-per-H2 (7 H2 sections)"],
            self.bullets(result.stdout),
        )

    def test_three_to_five_sections_suggest_moderate_splitting(self):
        path = self.write_doc("few.md", doc_with_h2(3))
        result = self.run_check()
        self.assertEqual("", result.stderr)
        self.assertEqual(
            [
                f"few.md ({self.reported_kb(path)} KB) → "
                "moderate splitting possible (3 H2 sections)"
            ],
            self.bullets(result.stdout),
        )

    def test_one_or_two_sections_fall_through_to_the_no_split_advice(self):
        """The boundary between the counted path and the else arm -- the same
        arm the zero-H2 case reaches, but with a non-zero count rendered."""
        path = self.write_doc("two.md", doc_with_h2(2))
        result = self.run_check()
        self.assertEqual("", result.stderr)
        self.assertEqual(
            [
                f"two.md ({self.reported_kb(path)} KB) → "
                "no obvious splitting point (2 H2 sections) — review content"
            ],
            self.bullets(result.stdout),
        )


class MixedScanTest(DocVolumeCheckTestBase):
    """One run over both fixture shapes at once: the pre-fix defect polluted
    a SHARED stderr, so a report that renders correct lines for its H2 files
    is still defective if a sibling zero-H2 file breaks the same run."""

    def test_zero_h2_and_many_h2_files_coexist_in_one_run(self):
        blank = self.write_doc("no-h2.md", doc_without_h2())
        rich = self.write_doc("many.md", doc_with_h2(7))
        result = self.run_check()
        self.assertEqual("", result.stderr)
        self.assertEqual(
            sorted([
                f"many.md ({self.reported_kb(rich)} KB) → split-per-H2 (7 H2 sections)",
                f"no-h2.md ({self.reported_kb(blank)} KB) → "
                "no obvious splitting point (0 H2 sections) — review content",
            ]),
            sorted(self.bullets(result.stdout)),
        )


class TrackedOnlyScopeTest(DocVolumeCheckTestBase):
    """WI-0129 Paket B, cycle B2: this check exists to flag oversized SHIPPED
    documentation pending a split (CONTRIBUTING.md's "known, stable baseline
    of findings"), not an adopter's own untracked working state -- drafts,
    persona memory silos (docs/memory/**, gitignored in this repository),
    generated reports. Measured directly on this repository's own working
    tree (30.08.2026): of 19 findings, all 5 critical and all 6 warning were
    untracked; only 3 of 8 info findings were tracked. When <docs-root> sits
    inside a git working tree, only TRACKED files are scanned.

    The counter-proof (`test_outside_a_git_repo_every_file_is_still_scanned`)
    matters as much as the positive case: a fix that unconditionally
    restricted to git-tracked files, with no fallback, would break every
    other test in this module (none of their docs roots are git repos) --
    and would silently stop scanning any non-git project entirely, which
    doc-volume-check.sh has always supported (it takes a bare docs-root, no
    project-identity assumption).
    """

    def fresh_git_docs_root(self):
        repo_root = Path(tempfile.mkdtemp(prefix="ccpr-doc-volume-git-"))
        self.addCleanup(shutil.rmtree, repo_root, ignore_errors=True)
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True)
        docs_root = repo_root / "docs"
        docs_root.mkdir()
        return repo_root, docs_root

    @staticmethod
    def commit(repo_root, *rel_paths):
        subprocess.run(["git", "add", *rel_paths], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo_root, check=True)

    def test_an_untracked_oversized_file_is_not_reported(self):
        repo_root, docs_root = self.fresh_git_docs_root()
        tracked = self.write_doc("tracked.md", doc_without_h2(INFO_BYTES), docs_root)
        self.commit(repo_root, "docs/tracked.md")
        # Never committed -- an ERROR-band file that must NOT surface.
        self.write_doc("untracked.md", doc_without_h2(ERROR_BYTES), docs_root)

        result = self.run_check(docs_root)

        self.assertEqual("", result.stderr, result.stderr)
        self.assertEqual(1, self.files_scanned(result.stdout), result.stdout)
        self.assertEqual(
            [
                f"tracked.md ({self.reported_kb(tracked)} KB) → "
                "no obvious splitting point (0 H2 sections) — review content"
            ],
            self.bullets(result.stdout),
        )
        self.assertEqual(0, result.returncode, result.stdout)

    def test_outside_a_git_repo_every_file_is_still_scanned(self):
        # Clean fallback: self.docs_root (DocVolumeCheckTestBase.setUp) is a
        # bare tempdir, never a git repo -- an oversized file there must
        # still be reported exactly as before this cycle.
        path = self.write_doc("plain.md", doc_without_h2(ERROR_BYTES))
        result = self.run_check()
        self.assertEqual("", result.stderr, result.stderr)
        self.assertEqual(1, self.files_scanned(result.stdout), result.stdout)
        self.assertEqual(
            [
                f"plain.md ({self.reported_kb(path)} KB) → "
                "no obvious splitting point (0 H2 sections) — review content"
            ],
            self.bullets(result.stdout),
        )
        self.assertEqual(2, result.returncode, result.stdout)

    def test_untracked_skip_count_is_named_in_the_report(self):
        # The behaviour change (fewer findings for an adopter with real,
        # untracked docs) must not pass silently -- the report says how many
        # files were skipped as untracked, the same "name what was NOT
        # covered" discipline artifact-gate.sh already applies to its own
        # binary/symlink skips.
        repo_root, docs_root = self.fresh_git_docs_root()
        self.write_doc("tracked.md", "# Title\n\nsmall, tracked.\n", docs_root)
        self.commit(repo_root, "docs/tracked.md")
        self.write_doc("draft-one.md", "# Draft\n\nnever committed.\n", docs_root)
        self.write_doc("draft-two.md", "# Draft\n\nalso never committed.\n", docs_root)

        result = self.run_check(docs_root)

        self.assertIn("**Untracked skipped:** 2 file(s)", result.stdout, result.stdout)

    def test_a_docs_root_one_level_below_the_git_root_still_resolves_scope(self):
        # doc-volume-check.sh is always invoked with the DOCS root
        # (<project>/docs), not the project/repository root -- the git
        # top-level sits one directory above. git itself walks up to find
        # .git, but this pins that this script's own detection does too.
        repo_root, docs_root = self.fresh_git_docs_root()
        tracked = self.write_doc("nested/tracked.md", doc_without_h2(INFO_BYTES), docs_root)
        self.commit(repo_root, "docs/nested/tracked.md")
        self.write_doc("nested/untracked.md", doc_without_h2(ERROR_BYTES), docs_root)

        result = self.run_check(docs_root)

        self.assertEqual(1, self.files_scanned(result.stdout), result.stdout)
        self.assertEqual(
            [
                f"nested/tracked.md ({self.reported_kb(tracked)} KB) → "
                "no obvious splitting point (0 H2 sections) — review content"
            ],
            self.bullets(result.stdout),
        )


class AutoloadedContextScopeTest(DocVolumeCheckTestBase):
    """A DIFFERENT corpus from DOCS_ROOT: the documents Claude Code actually
    loads into every session. Derived (ADR-0012), not typed: starting at
    <project-root>/CLAUDE.md and following `^@<path>$` import lines
    transitively, each resolved relative to the FILE THAT IMPORTS IT --
    never a name glob (a file merely NAMED like CLAUDE.md, e.g.
    templates/CLAUDE_LEAN_TEMPLATE.md, is not autoloaded unless something
    actually imports it).

    <project-root> is one directory ABOVE <docs-root> -- the mirror image
    of TrackedOnlyScopeTest's git-root note, since this script is always
    invoked with <project>/docs.

    Like DOCS_ROOT, this corpus IS restricted to git-tracked files (reversed
    01.09.2026, PO override, no work item): this tool judges the SHIPPED state --
    what `check-all.sh` sees from a fresh clone of a given commit -- not one
    machine's local Claude Code setup. An untracked file reachable only
    through someone's own uncommitted `@import` line is real context cost on
    THEIR machine, but it is not part of the shipped commit, so a
    `check-all.sh` run against that same commit from a different machine
    would never see it -- see
    test_an_untracked_autoload_source_over_50kb_produces_zero_findings,
    which replaces this class's former
    test_an_untracked_claude_md_is_still_reported (the test that encoded the
    now-overturned "always reported" decision). The import graph still
    decides WHICH FILES ARE CANDIDATES (unchanged, still exercised by every
    other test in this class); tracking now additionally decides which of
    those candidates GET REPORTED.
    """

    def fresh_project_root(self):
        root = Path(tempfile.mkdtemp(prefix="ccpr-doc-volume-autoload-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        docs_root = root / "docs"
        docs_root.mkdir()
        return root, docs_root

    @staticmethod
    def write_project_file(project_root, rel_path, text):
        path = project_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_an_oversized_root_claude_md_is_reported(self):
        project_root, docs_root = self.fresh_project_root()
        claude = self.write_project_file(project_root, "CLAUDE.md", doc_without_h2(INFO_BYTES))

        result = self.run_check(docs_root)

        self.assertEqual("", result.stderr, result.stderr)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn(
            f"CLAUDE.md ({self.reported_kb(claude)} KB, info) → "
            "no obvious splitting point (0 H2 sections) — review content",
            result.stdout,
        )

    def test_import_chain_is_followed_transitively_and_reported_as_critical(self):
        project_root, docs_root = self.fresh_project_root()
        self.write_project_file(project_root, "CLAUDE.md", "# Root\n\n@extra.md\n")
        extra = self.write_project_file(project_root, "extra.md", doc_without_h2(ERROR_BYTES))

        result = self.run_check(docs_root)

        self.assertEqual("", result.stderr, result.stderr)
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn(
            f"extra.md ({self.reported_kb(extra)} KB, critical) → "
            "no obvious splitting point (0 H2 sections) — review content",
            result.stdout,
        )

    def test_nested_import_resolves_relative_to_the_importing_file(self):
        # @deep.md sits inside sub/inner.md -- it must resolve to
        # sub/deep.md, not project_root/deep.md (which does not exist). A
        # resolver that always resolves against project_root would miss it
        # entirely, which is exactly what this test would catch.
        project_root, docs_root = self.fresh_project_root()
        self.write_project_file(project_root, "CLAUDE.md", "# Root\n\n@sub/inner.md\n")
        self.write_project_file(project_root, "sub/inner.md", "# Inner\n\n@deep.md\n")
        deep = self.write_project_file(project_root, "sub/deep.md", doc_without_h2(WARNING_BYTES))

        result = self.run_check(docs_root)

        self.assertEqual("", result.stderr, result.stderr)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(
            f"sub/deep.md ({self.reported_kb(deep)} KB, warning) → "
            "no obvious splitting point (0 H2 sections) — review content",
            result.stdout,
        )

    def test_a_claude_named_file_that_is_not_imported_is_not_reported(self):
        # templates/CLAUDE_LEAN_TEMPLATE.md's real-world shape: matches a
        # naive "CLAUDE*.md" glob but nothing imports it -- only the import
        # graph, never a name pattern, decides membership.
        project_root, docs_root = self.fresh_project_root()
        self.write_project_file(project_root, "CLAUDE.md", "# Root\n\nNo imports here.\n")
        self.write_project_file(
            project_root, "templates/CLAUDE_LEAN_TEMPLATE.md", doc_without_h2(ERROR_BYTES)
        )

        result = self.run_check(docs_root)

        self.assertEqual("", result.stderr, result.stderr)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("**Autoloaded context files found:** 1", result.stdout)
        self.assertNotIn("CLAUDE_LEAN_TEMPLATE", result.stdout)

    def test_a_non_imported_root_file_is_not_reported(self):
        project_root, docs_root = self.fresh_project_root()
        self.write_project_file(project_root, "CLAUDE.md", "# Root\n\nNo imports here.\n")
        self.write_project_file(project_root, "CHANGELOG.md", doc_without_h2(ERROR_BYTES))

        result = self.run_check(docs_root)

        self.assertEqual("", result.stderr, result.stderr)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("**Autoloaded context files found:** 1", result.stdout)
        self.assertNotIn("CHANGELOG.md", result.stdout)

    def test_adding_an_at_import_line_brings_its_target_into_scope(self):
        # No list to edit anywhere -- the import line itself is the only
        # thing that changes between the two runs (ADR-0012).
        project_root, docs_root = self.fresh_project_root()
        self.write_project_file(project_root, "CLAUDE.md", "# Root\n\nNo imports yet.\n")
        extra = self.write_project_file(project_root, "extra.md", doc_without_h2(INFO_BYTES))

        before = self.run_check(docs_root)
        self.assertEqual(0, before.returncode, before.stdout)
        self.assertNotIn("extra.md", before.stdout)

        self.write_project_file(project_root, "CLAUDE.md", "# Root\n\n@extra.md\n")
        after = self.run_check(docs_root)

        self.assertEqual(0, after.returncode, after.stdout)
        self.assertIn(
            f"extra.md ({self.reported_kb(extra)} KB, info) → "
            "no obvious splitting point (0 H2 sections) — review content",
            after.stdout,
        )

    def test_no_claude_md_at_project_root_reports_zero_scope_without_crashing(self):
        project_root, docs_root = self.fresh_project_root()
        self.write_doc("small.md", "# Title\n\nShort.\n", docs_root)

        result = self.run_check(docs_root)

        self.assertEqual("", result.stderr, result.stderr)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("**Autoloaded context files found:** 0", result.stdout)

    def test_an_untracked_autoload_source_over_50kb_produces_zero_findings(self):
        """The PO's probe case (01.09.2026): an untracked file over 50 KB,
        imported via CLAUDE.md, is a real thing on the machine that authored
        it but not part of the SHIPPED commit -- a `check-all.sh` run
        against the same commit from a different machine would never see
        it. Before the tracked-only restriction on the autoload corpus,
        this exact fixture reported "1 critical" and drove the exit code to
        2 (measured directly, RED); after it, zero findings, exit 0 (GREEN).
        Replaces test_an_untracked_claude_md_is_still_reported, which
        asserted the opposite of this."""
        project_root, docs_root = self.fresh_project_root()
        subprocess.run(["git", "init", "-q"], cwd=project_root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=project_root, check=True)
        self.write_project_file(project_root, "CLAUDE.md", doc_without_h2(ERROR_BYTES))
        # Deliberately never `git add`/`git commit` -- CLAUDE.md stays
        # untracked.

        result = self.run_check(docs_root)

        self.assertEqual("", result.stderr, result.stderr)
        self.assertEqual(0, result.returncode, result.stdout)
        # The import graph still finds it as a candidate (unaffected --
        # tracking narrows REPORTING, not the candidate set)...
        self.assertIn("**Autoloaded context files found:** 1", result.stdout)
        # ...but it raises no finding and appears in no bullet.
        self.assertEqual([], self.bullets(result.stdout), result.stdout)
        self.assertIn("**Autoloaded summary:** 0 critical, 0 warning, 0 info.", result.stdout)


if __name__ == "__main__":
    unittest.main()
