"""test_baseline_archive_directory.py -- WI-0059: scripts/baseline.sh must
archive HANDOVER.md into the DOTTED `docs/.handover-archive/` directory, not
an undotted sibling no other convention names.

## Why this exists

Three other places already use the dotted spelling: `.gitignore:35` ignores
`docs/.handover-archive/`, `commands/cleanup.md` documents
`docs/.handover-archive/<YYYY-MM-DD>-<slug>.md` twice as the established
convention, and the only such directory that exists on disk in a real
project is the dotted one. `scripts/baseline.sh` was the outlier: it built
`ARCHIVE_DIR` from `${DOCS_DIR}/handover-archive` (no dot) and additionally
hardcoded a SECOND, independent copy of that wrong path as a literal string
in its generated report (`docs/handover-archive/${ARCHIVE_NAME}`) rather
than deriving the report line from `ARCHIVE_DIR` -- the duplication is how
the two could drift, and did.

## What the fix changes

1. `ARCHIVE_DIR` is now `${DOCS_DIR}/.handover-archive`.
2. The report's "Archived as" line is derived from `ARCHIVE_DIR` (via a
   single `ARCHIVE_DIR_REL` computed once, project-root-relative) instead of
   a second hardcoded literal -- the two can no longer drift apart.
3. A pre-existing undotted `docs/handover-archive/` directory is REPORTED
   (named, with its contents listed) and left completely untouched -- no
   migration, no move. Moving a user's files without asking is the action
   that needs consent; leaving them alone does not.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

# The gate scans this repo's own tracked files, so a raw IPv4 literal spelled
# out in source would BE a finding on every sweep (see test_artifact_gate.py's
# leak() docstring and test_memory_sync_transport_errors.py's DEAD_REMOTE for
# the established precedent).
from .test_artifact_gate import leak

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "baseline.sh"

HANDOVER_CONTENT = "# HANDOVER\n\n## Last Action\n\nSomething happened.\n"

# A connection that fails FAST and OFFLINE: nothing binds port 1 on loopback,
# so the kernel refuses immediately instead of the summary step timing out.
DEAD_OLLAMA_URL = leak("http://127.", "0.0.1:1")


class BaselineArchiveTestBase(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="ccpr-baseline-project-"))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        self.docs = self.project / "docs"
        self.docs.mkdir(parents=True)

    def write_handover(self):
        (self.docs / "HANDOVER.md").write_text(HANDOVER_CONTENT, encoding="utf-8")

    def run_baseline(self, version="v1.0.0", script=None):
        # OLLAMA_URL points at a closed local port so the connect fails fast
        # and deterministically -- the summary step is not under test here
        # and must not depend on whether the machine happens to run Ollama.
        import os
        env = dict(os.environ)
        env["OLLAMA_URL"] = DEAD_OLLAMA_URL
        return subprocess.run(
            ["bash", str(script or SCRIPT), version, str(self.project)],
            capture_output=True, text=True, env=env,
        )

    def prep_report_path(self):
        return self.docs / ".baseline-prep.md"


class ArchiveLandsInTheDottedDirectoryTest(BaselineArchiveTestBase):
    def test_handover_is_archived_under_dot_handover_archive(self):
        self.write_handover()
        r = self.run_baseline(version="v2.3.1")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

        dotted_dir = self.docs / ".handover-archive"
        self.assertTrue(dotted_dir.is_dir(), r.stdout + r.stderr)
        archived_files = list(dotted_dir.glob("HANDOVER_v2.3.1_*.md"))
        self.assertEqual(1, len(archived_files), archived_files)
        self.assertEqual(HANDOVER_CONTENT, archived_files[0].read_text(encoding="utf-8"))

    def test_no_undotted_sibling_directory_is_created(self):
        self.write_handover()
        self.run_baseline()
        self.assertFalse((self.docs / "handover-archive").exists())


class ReportNamesTheActualArchivePathTest(BaselineArchiveTestBase):
    def test_report_names_the_dotted_path_the_file_actually_went_to(self):
        self.write_handover()
        r = self.run_baseline(version="v9.9.9")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

        report = self.prep_report_path().read_text(encoding="utf-8")
        dotted_dir = self.docs / ".handover-archive"
        archived_files = list(dotted_dir.glob("HANDOVER_v9.9.9_*.md"))
        self.assertEqual(1, len(archived_files), archived_files)

        self.assertIn(f"docs/.handover-archive/{archived_files[0].name}", report)
        self.assertNotIn("docs/handover-archive/", report)


class PreExistingUndottedDirectoryIsReportedAndUntouchedTest(BaselineArchiveTestBase):
    def setUp(self):
        super().setUp()
        self.legacy_dir = self.docs / "handover-archive"
        self.legacy_dir.mkdir()
        self.legacy_file = self.legacy_dir / "HANDOVER_v0.1.0_01.01.2026.md"
        self.legacy_file.write_text("old archive content, untouched\n", encoding="utf-8")

    def test_the_legacy_directory_is_named_in_the_output(self):
        self.write_handover()
        r = self.run_baseline()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("docs/handover-archive", r.stdout)

    def test_the_legacy_directory_and_its_contents_survive_untouched(self):
        self.write_handover()
        self.run_baseline()

        self.assertTrue(self.legacy_dir.is_dir())
        self.assertTrue(self.legacy_file.is_file())
        self.assertEqual(
            "old archive content, untouched\n",
            self.legacy_file.read_text(encoding="utf-8"),
        )

    def test_the_new_archive_still_lands_in_the_dotted_directory_alongside_it(self):
        self.write_handover()
        r = self.run_baseline(version="v3.0.0")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        dotted_dir = self.docs / ".handover-archive"
        self.assertEqual(1, len(list(dotted_dir.glob("HANDOVER_v3.0.0_*.md"))))


class BaselinePrepOutputStillWorksTest(BaselineArchiveTestBase):
    """Regression guard: docs/.baseline-prep.md is still what the script
    writes as its output (unrelated item requirement WI-0059 must not
    break)."""

    def test_output_file_is_written_with_the_version_heading(self):
        self.write_handover()
        r = self.run_baseline(version="v5.0.0")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = self.prep_report_path()
        self.assertTrue(report.is_file())
        self.assertIn("# Baseline Preparation: v5.0.0", report.read_text(encoding="utf-8"))

    def test_no_handover_present_is_handled_without_creating_an_archive_file(self):
        r = self.run_baseline()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = self.prep_report_path().read_text(encoding="utf-8")
        self.assertIn("No HANDOVER.md present", report)


class RedProofTest(BaselineArchiveTestBase):
    """Mutation proof, inline: restoring each site to its exact pre-fix form
    in a scratch copy of the script must fail at least one test above --
    proving the tests are not vacuously green. Each mutant is a byte-exact
    single-site reversion, not a rewrite."""

    def mutant_script(self, mutated_text):
        scratch = Path(tempfile.mkdtemp(prefix="ccpr-baseline-mutant-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        mutant = scratch / "baseline.sh"
        mutant.write_text(mutated_text, encoding="utf-8")
        return mutant

    def test_reverting_archive_dir_to_the_undotted_form_breaks_the_dotted_dir_test(self):
        current = SCRIPT.read_text(encoding="utf-8")
        pre_fix = current.replace(
            'ARCHIVE_DIR="${DOCS_DIR}/.handover-archive"',
            'ARCHIVE_DIR="${DOCS_DIR}/handover-archive"',
        )
        self.assertNotEqual(current, pre_fix, "fixture did not find the site to mutate")
        mutant = self.mutant_script(pre_fix)

        self.write_handover()
        r = self.run_baseline(version="v1.0.0", script=mutant)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertFalse((self.docs / ".handover-archive").exists())

    def test_reverting_the_report_line_to_a_hardcoded_literal_breaks_the_report_test(self):
        current = SCRIPT.read_text(encoding="utf-8")
        start = current.index('## HANDOVER Archive')
        end = current.index('\n\n', start)
        pre_fix_block = (
            '## HANDOVER Archive\n'
            '$(if [ -n "${ARCHIVE_NAME}" ]; then echo "Archived as: '
            '\\`docs/handover-archive/${ARCHIVE_NAME}\\`"; else echo '
            '"No HANDOVER.md present"; fi)'
        )
        mutated = current[:start] + pre_fix_block + current[end:]
        self.assertNotEqual(current, mutated, "fixture did not find the site to mutate")
        mutant = self.mutant_script(mutated)

        self.write_handover()
        r = self.run_baseline(version="v1.0.0", script=mutant)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = self.prep_report_path().read_text(encoding="utf-8")
        self.assertIn("docs/handover-archive/", report)

    def test_removing_the_legacy_directory_report_breaks_the_legacy_naming_test(self):
        current = SCRIPT.read_text(encoding="utf-8")
        start = current.index("# 0. Report")
        end = current.index("# 1. Archive directory")
        self.assertGreater(end, start, "fixture did not find the site to mutate")
        mutated = current[:start] + current[end:]
        self.assertNotEqual(current, mutated, "fixture did not find the site to mutate")
        mutant = self.mutant_script(mutated)

        legacy_dir = self.docs / "handover-archive"
        legacy_dir.mkdir()
        (legacy_dir / "old.md").write_text("old\n", encoding="utf-8")
        self.write_handover()
        r = self.run_baseline(version="v1.0.0", script=mutant)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertNotIn("docs/handover-archive", r.stdout)


if __name__ == "__main__":
    unittest.main()
