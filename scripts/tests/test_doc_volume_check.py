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


if __name__ == "__main__":
    unittest.main()
