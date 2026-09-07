"""test_manual_lint_multi_root.py -- CCP-1151 stage 4 cut 4: manual-lint.sh
accepts more than one root in a single invocation.

## Why this exists

check-all.sh's own invocation of manual-lint.sh pointed at a single tree
(`handbook/`) since the script was first written. Constraint 2 of the item
that added check (g) below (a forbidden-prose-term guard, see
test_manual_lint_check_g.py) measured that four more trees --
`commands/`, `agents/`, `templates/`, `instincts/` -- carry the same
`kind:`/`parent_index:` contract checks (a)/(b)/(c)/(f) already validate and
come back clean today, but check-all.sh never looks at them: the structural
guard "would hang entirely on this PR's closing grep" otherwise (the
item's own words). Wiring one check-all.sh entry per new root for one script
would touch `check-all.baseline.tsv`, `conformance-run.sh`'s
`CHECK_NAMES_PY` and `test_check_all.py`'s own pinned check-name list for no
reason the script itself couldn't absorb -- `manual-lint.sh` already
describes itself as "generic over ANY root", so accepting several roots in
one pass, and reporting one combined result, is the same generalisation the
script already makes for a single root, not a new capability class.

## Scope of this module

Only the ROOT-ACCEPTANCE mechanics: multiple positional arguments are all
scanned, findings from each stay attributable to the file that produced
them (not misattributed to a sibling root), file counts and PARENT_LINKS
accumulate across roots rather than only the last one, and every existing
single-root behaviour (default-to-cwd, a missing root, an empty root) still
holds when exactly one root -- or zero -- is given. It does NOT re-test
checks (a)/(b)/(c)/(f)/(g) themselves; those are covered by
test_manual_lint.py and test_manual_lint_check_g.py against a single root
each, and nothing about their own logic changes here -- only how many root
directories feed the same per-file loop.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "manual-lint.sh"


class MultiRootTestBase(unittest.TestCase):
    def setUp(self):
        self.workdir = Path(tempfile.mkdtemp(prefix="ccpr-manual-lint-multiroot-"))
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)

    def write_doc(self, rel_path, text):
        path = self.workdir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_lint(self, *roots):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), *[str(r) for r in roots]],
            capture_output=True, text=True,
        )

    @staticmethod
    def findings(output, heading):
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


def doc_text(kind="detail", body="\n# Doc\n\nBody.\n"):
    return f"---\nkind: {kind}\n---\n" + body


class TwoCleanRootsTest(MultiRootTestBase):
    """The baseline this module exists to prove: two independent, both-clean
    root trees, scanned in one invocation, produce one report whose file
    count is the SUM of both -- not just the first root's count (the shape
    a naive `ROOT="${1:-...}"` scalar would silently produce, quietly
    dropping every root after the first)."""

    def test_files_scanned_is_the_sum_across_both_roots(self):
        root_a = self.workdir / "root-a"
        root_b = self.workdir / "root-b"
        self.write_doc("root-a/one.md", doc_text())
        self.write_doc("root-b/two.md", doc_text())
        self.write_doc("root-b/three.md", doc_text())

        result = self.run_lint(root_a, root_b)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 3, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)


class FindingAttributionTest(MultiRootTestBase):
    """A finding in root B must name a path relative to root B, not root A
    -- proving each root's own files are stripped against ITS OWN root
    rather than whichever root happened to be scanned first (or last)."""

    def test_error_in_second_root_names_a_path_relative_to_that_root(self):
        root_a = self.workdir / "root-a"
        root_b = self.workdir / "root-b"
        self.write_doc("root-a/ok.md", doc_text())
        # A parent_index that resolves at neither base is check (a)'s
        # unambiguous error shape (see test_manual_lint.py's
        # CheckAParentIndexResolutionTest) -- exercised here purely as a
        # traceable marker of WHICH root a finding came from.
        self.write_doc(
            "root-b/broken.md",
            "---\nkind: detail\nparent_index: GHOST.md\n---\n\nBody.\n",
        )

        result = self.run_lint(root_a, root_b)

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any(e.startswith("broken.md") for e in errors),
            f"expected an error naming 'broken.md' (relative to root-b, not "
            f"root-a or the workdir), got: {errors!r}",
        )
        # And root-a's clean file must not have been swept into root-b's
        # relative-path space either (e.g. as "../root-a/ok.md").
        self.assertFalse(any("root-a" in e or "root-b" in e for e in errors), errors)


class CheckBCrossRootAttributionTest(MultiRootTestBase):
    """code-reviewer finding: check (b)'s reverse-link warning is the part
    of this refactor `display_rel()`/`ROOTS_ABS` actually exists for -- the
    single-root code's `ROOT_ABS` scalar is set once per ROOT-LOOP
    ITERATION but check (b) runs only ONCE, after every root has been
    scanned, so it would hold only the LAST root's absolute path by the
    time check (b) reads it. Both roots' index/child pairs deliberately
    fail to link back here, not just root B's: `${path#$ROOT_ABS/}` on a
    path that does not share that ONE prefix leaves the string UNCHANGED
    (bash's `#pattern` removal is a no-op on a non-match, never an error),
    so the pre-fix shape would print root A's warning with its FULL
    ABSOLUTE PATH instead of a relative one -- confirmed by temporarily
    reverting `display_rel()`'s two call sites to the single-scalar form
    during authoring and watching this exact assertion go red (mutate/
    restore proof, not shipped)."""

    def test_reverse_link_warnings_in_both_roots_name_root_relative_paths(self):
        root_a = self.workdir / "root-a"
        root_b = self.workdir / "root-b"

        # Neither INDEX.md links its own child back.
        self.write_doc("root-a/INDEX.md", "# Index\n")
        self.write_doc(
            "root-a/system/child.md",
            "---\nkind: detail\nparent_index: ../INDEX.md\n---\n\nBody.\n",
        )
        self.write_doc("root-b/INDEX.md", "# Index\n")
        self.write_doc(
            "root-b/system/child.md",
            "---\nkind: detail\nparent_index: ../INDEX.md\n---\n\nBody.\n",
        )

        result = self.run_lint(root_a, root_b)

        warnings = self.findings(result.stdout, "Warnings")
        self.assertEqual(len(warnings), 2, warnings)
        for w in warnings:
            self.assertIn("does not link back to system/child.md", w, warnings)
            # Root-relative ("INDEX.md"), never the full absolute path this
            # tempdir's own prefix would reveal, and never cross-attributed
            # with the sibling root's own directory name.
            self.assertTrue(w.startswith("INDEX.md"), warnings)
            self.assertNotIn(str(self.workdir), w)
            self.assertNotIn("root-a", w)
            self.assertNotIn("root-b", w)


class MixedMissingAndPresentRootsTest(MultiRootTestBase):
    """One missing root among several must not abort the whole run -- the
    same "an empty scope says so on stderr, not silently, and still exits
    0" contract test_manual_lint.py's EmptyScopeTest pins for a single root,
    now checked with a SECOND, present root alongside the missing one."""

    def test_missing_root_is_noted_but_the_present_root_still_scans(self):
        present = self.workdir / "present"
        ghost = self.workdir / "does-not-exist"
        self.write_doc("present/x.md", doc_text())

        result = self.run_lint(ghost, present)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 1, result.stdout)
        self.assertIn(str(ghost), result.stderr)
        self.assertIn("does not exist", result.stderr)


class SingleRootBackwardCompatibilityTest(MultiRootTestBase):
    """Exactly one root, or zero, must behave exactly as before this
    module's change -- the multi-root loop is a generalisation, not a
    behaviour change for the case every existing caller already uses."""

    def test_single_explicit_root_behaves_as_before(self):
        self.write_doc("x.md", doc_text())

        result = self.run_lint(self.workdir)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 1, result.stdout)

    def test_zero_roots_defaults_to_the_current_working_directory(self):
        self.write_doc("x.md", doc_text())

        result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            capture_output=True, text=True, cwd=self.workdir,
        )

        self.assertEqual(self.files_scanned(result.stdout), 1, result.stdout)


if __name__ == "__main__":
    unittest.main()
