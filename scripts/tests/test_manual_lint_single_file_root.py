"""test_manual_lint_single_file_root.py -- CCP-1163: manual-lint.sh accepts a
single FILE as a root, not only a directory.

## Why this exists

manual-lint.sh describes itself as "generic over ANY documentation root"
(its own header) and CCP-1151 stage 4 cut 4 already generalised it to accept
MULTIPLE roots in one invocation (test_manual_lint_multi_root.py). Neither
generalisation covers the shape a single loose top-level document needs:
`bash scripts/manual-lint.sh instincts.md` today reports "Files scanned: 0"
and exits 0 -- a silent no-op, not an error, and indistinguishable from "this
file has nothing wrong with it" from the outside (the exact WI-0090/KA-G-017
"a check run that reports no scope is not a pass" class this repository's own
checks are built to avoid everywhere else).

The root cause: every file-collection branch in manual-lint.sh (the
checks-(a)/(b)/(c)/(f) `FILES` array, the check-(g) `G_FILES` array, and
`ROOT_ABS`'s own computation) gates on `[[ -d "$ROOT" ]]` -- true for a
directory, false for an existing regular file, so a file root silently
collects nothing. Worse: the existing-scope stderr notice
(`EmptyScopeTest` in test_manual_lint.py) then misreports an EXISTING file
as "does not exist", because its own test is `[[ ! -d "$ROOT" ]]` -- true
for any non-directory, including a file that is right there on disk. This
module drives that exact defect to a failing test first (RED), then proves
the fix.

## Scope

Only the ROOT-ACCEPTANCE mechanics for a single FILE, mirroring
test_manual_lint_multi_root.py's own scope note: it does not re-test checks
(a)/(b)/(c)/(f)/(g) themselves (already covered by test_manual_lint.py and
test_manual_lint_check_g.py against directory roots) beyond what is needed
to prove a file root actually feeds the SAME per-file loop those checks
already run, not a special-cased shortcut that skips it.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "manual-lint.sh"
ENV_VAR = "CCPR_LINT_FORBIDDEN_PROSE"


class SingleFileRootTestBase(unittest.TestCase):
    def setUp(self):
        self.workdir = Path(tempfile.mkdtemp(prefix="ccpr-manual-lint-file-root-"))
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)

    def write(self, rel_path, text):
        path = self.workdir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_lint(self, *args, config=None):
        env = None
        if config is not None:
            env = dict(os.environ)
            env[ENV_VAR] = json.dumps(config)
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), *[str(a) for a in args]],
            capture_output=True, text=True, env=env,
        )

    @staticmethod
    def findings(output, heading):
        collected, collecting = [], False
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


DOC = "---\nkind: detail\n---\n\n# Doc\n\nBody.\n"


class SingleMarkdownFileRootTest(SingleFileRootTestBase):
    """A bare markdown file, given directly as ROOT, must be scanned as
    itself -- not treated as an empty/missing directory."""

    def test_a_single_markdown_file_root_scans_that_file(self):
        doc = self.write("x.md", DOC)

        result = self.run_lint(doc)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 1, result.stdout)

    def test_check_a_still_runs_against_a_file_root_not_just_counts_it(self):
        """Liveness proof (test_absence_only_assertions.py's own pattern,
        reused here): "Files scanned: 1" alone cannot distinguish a real
        per-file loop from a shortcut that only counts. A parent_index
        pointing nowhere must still be reported."""
        doc = self.write(
            "x.md",
            "---\nkind: detail\nparent_index: does-not-exist.md\n---\n\nBody.\n",
        )

        result = self.run_lint(doc)

        self.assertEqual(result.returncode, 2, result.stdout)
        errs = self.findings(result.stdout, "Errors")
        self.assertTrue(any("does-not-exist.md" in e for e in errs), errs)

    def test_error_line_names_the_file_by_basename_not_its_full_path(self):
        """code-reviewer finding (CCP-1163, second cut): for a DIRECTORY
        root, an error is prefixed with a path relative to that root (a
        short "x.md", never the tempdir it lives under). A FILE root has no
        "inside" to strip $ROOT/ off of -- $ROOT and the single file it
        names are the SAME string, so the naive `${file#$ROOT/}` strip
        never matches and the raw $ROOT survives verbatim into the report.
        `self.workdir` (the caller of `self.write()`) is already an
        ABSOLUTE tempdir path (`tempfile.mkdtemp()`), which is exactly the
        shape check-all.sh's own `PROJECT_DIR="$(cd ... && pwd -P)"`
        produces for every wired file root (CLAUDE.md, instincts.md, ...) --
        so this is not a synthetic edge case, it is the real invocation
        shape in production. An `in` (substring) assertion cannot catch
        this (the basename is still a substring of the full path); this
        test asserts the exact PREFIX instead."""
        doc = self.write(
            "x.md",
            "---\nkind: detail\nparent_index: does-not-exist.md\n---\n\nBody.\n",
        )
        self.assertTrue(doc.is_absolute(), doc)

        result = self.run_lint(doc)

        errs = self.findings(result.stdout, "Errors")
        self.assertEqual(len(errs), 1, errs)
        self.assertTrue(
            errs[0].startswith("x.md "),
            f"expected the error to name the file by its basename alone, "
            f"got: {errs[0]!r}",
        )


class NonexistentFileRootTest(SingleFileRootTestBase):
    """The existing 'root does not exist' notice must stay reserved for a
    path that genuinely is not there -- not fire on a real file just
    because it fails the OLD `-d` test."""

    def test_nonexistent_path_still_reports_does_not_exist(self):
        ghost = self.workdir / "no-such-file.md"

        result = self.run_lint(ghost)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 0)
        self.assertIn("does not exist", result.stderr)
        self.assertNotIn("no markdown files found", result.stderr)


class NonMarkdownFileRootTest(SingleFileRootTestBase):
    """An existing file that is not itself markdown is a genuinely empty
    scope for checks (a)/(b)/(c)/(f) -- audible, not a false 'does not
    exist', and not silently indistinguishable from a clean pass."""

    def test_existing_non_markdown_file_root_is_an_audible_empty_scope(self):
        script = self.write("hello.sh", "#!/usr/bin/env bash\necho hi\n")

        result = self.run_lint(script)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 0)
        self.assertIn("no markdown files found", result.stderr)
        self.assertNotIn("does not exist", result.stderr)


class MixedFileAndDirectoryRootsTest(SingleFileRootTestBase):
    """The multi-root capability (CCP-1151 stage 4 cut 4) must accept a
    mix of file and directory roots in the same invocation, with file
    counts and findings from each attributable correctly."""

    def test_a_file_root_and_a_directory_root_together_sum_files_scanned(self):
        file_root = self.write("loose.md", DOC)
        self.write("tree/a.md", DOC)
        self.write("tree/b.md", DOC)
        dir_root = self.workdir / "tree"

        result = self.run_lint(file_root, dir_root)

        self.assertEqual(self.files_scanned(result.stdout), 3, result.stdout)


class SingleFileRootCheckGTest(SingleFileRootTestBase):
    """Check (g) has its OWN file-collection branch (a wider extension set
    than checks (a)/(b)/(c)/(f)) -- proven separately so a fix that only
    patches the markdown-only FILES array cannot pass this module while
    check (g) still silently skips a file root."""

    def test_a_single_script_file_root_is_scanned_by_check_g(self):
        script = self.write(
            "hello.sh", "#!/usr/bin/env bash\n# This mentions the skill directly.\n"
        )

        result = self.run_lint(script, config=[{"term": "skill"}])

        self.assertEqual(result.returncode, 2, result.stdout)
        errs = self.findings(result.stdout, "Errors")
        g_errs = [e for e in errs if "forbidden prose term" in e]
        self.assertEqual(len(g_errs), 1, errs)
        self.assertIn("hello.sh", g_errs[0])

    def test_check_g_error_line_names_the_file_by_basename_not_its_full_path(self):
        """code-reviewer finding (CCP-1163, second cut): check (g) already
        computes a basename-only `gfile_display` for a file root (used to
        test pathContains) -- but its own `err()` call used the raw,
        unstripped `$grel` instead, so the printed finding still leaked the
        full absolute tempdir path. `self.workdir` is absolute
        (`tempfile.mkdtemp()`), the same shape check-all.sh's own
        `PROJECT_DIR="$(cd ... && pwd -P)"` produces for every wired file
        root -- an `in` (substring) assertion cannot tell a leaked absolute
        path from a correctly-stripped basename (the basename is a
        substring of the full path either way); this asserts the exact
        PREFIX instead."""
        script = self.write(
            "hello.sh", "#!/usr/bin/env bash\n# This mentions the skill directly.\n"
        )
        self.assertTrue(script.is_absolute(), script)

        result = self.run_lint(script, config=[{"term": "skill"}])

        errs = self.findings(result.stdout, "Errors")
        g_errs = [e for e in errs if "forbidden prose term" in e]
        self.assertEqual(len(g_errs), 1, errs)
        self.assertTrue(
            g_errs[0].startswith("hello.sh:"),
            f"expected the error to name the file by its basename alone, "
            f"got: {g_errs[0]!r}",
        )


if __name__ == "__main__":
    unittest.main()
