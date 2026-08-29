"""test_check_all.py -- coverage for scripts/check-all.sh, the single
command CONTRIBUTING.md's "Quality checks before opening a PR" section asks
a contributor to remember by hand: seven commands, two of which are
non-zero on a correct tree BY DESIGN, and none of which anyone was
verifying were actually all run.

## Why exit code alone is the wrong pass criterion, and what replaces it

Measured directly on this repository (29.08.2026, HEAD 961165f):
memory-lint.sh exits 1 (long-standing memory-freshness warnings) and
doc-volume-check.sh exits 2 (known oversized files pending a split) on a
CLEAN tree. A script that failed on any non-zero exit would be permanently
red on a correct tree; a script that always reports "exit 0 = pass" would
never notice one of those two silently becoming exit 0 for the wrong
reason (a warning that stopped being detected, not one that got fixed).
check-all.sh instead compares each check's ACTUAL exit code against an
EXPECTED one declared once in scripts/check-all.baseline.tsv, and reports
agreement ("match") or disagreement ("divergent") — never bare pass/fail
against zero. `AllChecksMatchBaselineTest` and
`CompareAgainstZeroInsteadOfBaselineRedProofTest` are the positive/negative
pair that pins this directly: the former asserts the two by-design-nonzero
checks report "match", not "divergent"; the latter mutates the comparison
to `= "0"` in a scratch copy and shows both then go red.

## The could-not-run class

A check that cannot run (python-tests and artifact-gate/conformance-run
outside this repository's own checkout; conformance-run.sh's own
"consumers not configured" shape, which is exit-0 and therefore invisible
to exit-code comparison alone) is neither a pass nor a failure. Reporting
"could-not-run" as if it were a pass is exactly the shape KA-G-017 already
names for conformance-run.sh's own not-configured state, one level further
in: a check that never ran must never look like a check that ran and found
nothing. `CouldNotRunIsNeverCountedAsPassTest` pins both could-not-run
triggers (the CCPR-only precondition, and conformance-run.sh's own report
substring); `AllCouldNotRunTest` pins the degenerate all-could-not-run case
(nothing was actually verified, so the run must not report success); and
`CouldNotRunCountsAsPassRedProofTest` mutates the shared `state=
"could-not-run"` assignment to `state="match"` in a scratch copy and shows
BOTH of the previous two tests' pins go red against it.

## The seam: CCPR_CHECK_ALL_SCRIPT_DIR

check-all.sh's own header explains the choice at length; the summary here
is only the test-facing half. Six of the seven checks are shipped sibling
scripts, invoked as `$CHECK_SCRIPT_DIR/<name>.sh <args>`, where
CHECK_SCRIPT_DIR defaults to check-all.sh's own directory and is
overridable via CCPR_CHECK_ALL_SCRIPT_DIR — the same seam
conformance-run.sh already ships as CCPR_CONFORMANCE_SCRIPT_DIR, for the
identical reason: the real checks never violate their own contracts against
this repository's own fixtures, and running the real ones (four minutes for
the python suite alone, per CONTRIBUTING.md) in every test of the
comparison logic would mean nobody runs these tests. `CheckAllTestBase.
setUp` therefore points CCPR_CHECK_ALL_SCRIPT_DIR at a scratch directory
holding one tiny `exit <N>` stub per sibling script, all clean (exit 0)
against an all-zero scratch baseline unless a test overrides one — the same
"clean unless overridden" default `ConformanceRunTestBase.setUp` already
uses in test_conformance_run.py.

The seventh check, python-tests, is not a sibling script — it is a fixed
`python3 -m unittest discover -s <project-dir>/scripts/tests -t
<project-dir>` invocation — and needs no separate seam: it is already
parametrised by <project-dir>, so setUp gives every test a real, tiny,
FAST test package (one trivial passing test) instead of this repository's
own suite.

## House pattern

Own TestBase in this module (this repository's convention: test bases are
duplicated per module rather than shared — see test_manual_lint.py:82 and
test_conformance_run.py:27). `tempfile.mkdtemp` + `addCleanup`, subprocess
against the shipped script (never sourced internals). Every mutation-based
RED-proof test below (a) asserts the literal it is about to replace occurs
the EXACT expected number of times before mutating (G-141: a mutation that
does not land reports "passed" and proves nothing), (b) writes the mutation
to a SCRATCH copy only and asserts the shipped scripts/check-all.sh is
byte-for-byte and mode-for-mode unchanged afterwards (G-143 — mutating and
restoring a tracked file must never be separated by anything abortable; the
scratch-copy shape sidesteps the restore step entirely), and (c) demonstrates
the SPECIFIC assertions from the corresponding positive/negative test now
fail against the mutated copy, rather than asserting some unrelated
difference exists.

## The contract test

`BaselineCatalogueContractTest` derives BOTH sides from their own artifacts
— the catalogue from scripts/check-all.sh's own `CHECK_NAMES=(...)` bash
array literal (parsed with a regex, never hand-copied into this file), and
the baseline names from scripts/check-all.baseline.tsv itself — and asserts
they are exactly equal. `DroppedBaselineEntryRedProofTest` proves this
comparison actually discriminates: drop one line from a SCRATCH copy of the
real baseline and show the same set comparison this test performs no
longer holds.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-all.sh"
BASELINE_PATH = REPO_ROOT / "scripts" / "check-all.baseline.tsv"


def parse_bash_array(source, varname):
    """Extracts the whitespace-separated contents of a single-line bash
    array literal (`VARNAME=(tok tok "tok")`), quote-stripped. check-all.sh
    ships its catalogue as exactly this shape (parallel arrays, bash 3.2 has
    no associative arrays) -- see its own CHECK_NAMES/CHECK_KIND/
    CHECK_SCRIPTS/CHECK_CCPR_ONLY declarations."""
    m = re.search(r"^%s=\(([^)]*)\)" % re.escape(varname), source, re.MULTILINE)
    assert m is not None, (
        "could not find %s=(...) literal in check-all.sh -- its shape changed, update this test" % varname
    )
    return [tok.strip('"').strip("'") for tok in m.group(1).split()]


def parse_baseline_names(text):
    """The first tab-separated column of every non-comment, non-blank line
    of a check-all.sh baseline TSV -- the same parse check-all.sh's own
    baseline reader performs, reimplemented independently here rather than
    shelling out to the script under test for what is, at this point, pure
    text parsing."""
    names = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name = line.split("\t", 1)[0]
        if name:
            names.append(name)
    return names


_SCRIPT_SOURCE = SCRIPT_PATH.read_text(encoding="utf-8")
CATALOGUE_NAMES = parse_bash_array(_SCRIPT_SOURCE, "CHECK_NAMES")
CATALOGUE_KIND = parse_bash_array(_SCRIPT_SOURCE, "CHECK_KIND")
CATALOGUE_SCRIPTS = parse_bash_array(_SCRIPT_SOURCE, "CHECK_SCRIPTS")


def _write_mutated_script(tmpdir, mutate_fn):
    """Copies scripts/check-all.sh into tmpdir, applying
    mutate_fn(original_text) -> mutated_text. Asserts the shipped file is
    byte-for-byte and mode-for-mode unchanged afterwards (G-143) -- the
    mutation lives ONLY in the scratch copy, which is what every RED-proof
    test below actually runs against."""
    before = SCRIPT_PATH.read_bytes()
    before_mode = SCRIPT_PATH.stat().st_mode
    original = before.decode("utf-8")
    mutated = mutate_fn(original)
    assert mutated != original, "mutation had no effect on check-all.sh's source"
    scratch = tmpdir / "check-all.sh"
    scratch.write_text(mutated, encoding="utf-8")
    scratch.chmod(0o755)
    assert before == SCRIPT_PATH.read_bytes(), "shipped scripts/check-all.sh content changed"
    assert before_mode == SCRIPT_PATH.stat().st_mode, "shipped scripts/check-all.sh mode bits changed"
    return scratch


class CheckAllTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-check-all-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.stub_dir = self.tmp / "stubs"
        self.stub_dir.mkdir()
        self.project_dir = self.tmp / "project"
        self.project_dir.mkdir()
        self.baseline_path = self.tmp / "baseline.tsv"

        # Every sibling-script check gets a clean (exit 0) stub, matching an
        # all-zero scratch baseline, unless a test overrides one --
        # ConformanceRunTestBase.setUp's same "clean unless overridden"
        # default (test_conformance_run.py:180-201).
        for name, kind, script in zip(CATALOGUE_NAMES, CATALOGUE_KIND, CATALOGUE_SCRIPTS):
            if kind == "script":
                self.write_stub(script, 0)
        self.write_baseline({name: 0 for name in CATALOGUE_NAMES})

        # python-tests needs <project-dir>/scripts/tests to exist, both to
        # be attempted at all (check-all.sh's own CCPR-only precondition)
        # and to have something real, tiny and FAST to discover instead of
        # this repository's own ~1850-test suite.
        self.make_trivial_test_package()

    # --- fixtures ------------------------------------------------------

    def make_trivial_test_package(self, passing=True):
        tests_dir = self.project_dir / "scripts" / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")
        assertion = "self.assertEqual(1, 1)" if passing else "self.assertEqual(1, 2)"
        (tests_dir / "test_trivial.py").write_text(
            "import unittest\n\n\n"
            "class TrivialTest(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        %s\n" % assertion,
            encoding="utf-8",
        )

    def write_stub(self, script_filename, exit_code, stdout_text="", stderr_text=""):
        """Writes (or overwrites) one check stub in self.stub_dir. Payloads
        go through a quoted heredoc so a report containing '$' is never
        re-interpreted by the stub's own shell (same reasoning
        ConformanceRunTestBase.write_stub already gives)."""
        path = self.stub_dir / script_filename
        lines = ["#!/usr/bin/env bash"]
        if stderr_text:
            lines += ["cat <<'STUB_EOF' >&2", stderr_text, "STUB_EOF"]
        if stdout_text:
            lines += ["cat <<'STUB_EOF'", stdout_text, "STUB_EOF"]
        lines.append("exit %d" % exit_code)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path.chmod(0o755)

    def remove_stub(self, script_filename):
        path = self.stub_dir / script_filename
        if path.exists():
            path.unlink()

    def write_baseline(self, mapping, extra_lines=None):
        lines = ["# scratch baseline for test_check_all.py"]
        for name, exit_code in mapping.items():
            lines.append("%s\t%d\tstub" % (name, exit_code))
        if extra_lines:
            lines.extend(extra_lines)
        self.baseline_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- invocation ------------------------------------------------------

    def run_check_all(self, *args, script_path=None, baseline_path=None, project_dir=None):
        env = dict(os.environ)
        env["CCPR_CHECK_ALL_SCRIPT_DIR"] = str(self.stub_dir)
        argv = [
            "bash", str(script_path or SCRIPT_PATH),
            "--baseline", str(baseline_path or self.baseline_path),
            *[str(a) for a in args],
            str(project_dir if project_dir is not None else self.project_dir),
        ]
        return subprocess.run(argv, capture_output=True, text=True, env=env, timeout=60)

    @staticmethod
    def output(r):
        return "returncode: %s\nstdout:\n%s\nstderr:\n%s" % (r.returncode, r.stdout, r.stderr)


# ---------------------------------------------------------------------------
# Every check matches its baseline
# ---------------------------------------------------------------------------
class AllChecksMatchBaselineTest(CheckAllTestBase):
    def setUp(self):
        super().setUp()
        # Mirrors this repository's own real baseline shape: two checks are
        # non-zero BY DESIGN and must still report "match", not "divergent".
        self.write_stub("memory-lint.sh", 1)
        self.write_stub("doc-volume-check.sh", 2)
        mapping = {name: 0 for name in CATALOGUE_NAMES}
        mapping["memory-lint"] = 1
        mapping["doc-volume-check"] = 2
        self.write_baseline(mapping)

    def test_every_check_matching_its_baseline_reports_match_and_exits_0(self):
        r = self.run_check_all()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Exit:** 0", r.stdout, self.output(r))
        self.assertIn(
            "**Summary:** 7 catalogued, 7 matched, 0 divergent, 0 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )
        self.assertIn("memory-lint: exit 1 (expected 1) — match", r.stdout, self.output(r))
        self.assertIn("doc-volume-check: exit 2 (expected 2) — match", r.stdout, self.output(r))
        self.assertNotIn("DIVERGENT", r.stdout, self.output(r))


# ---------------------------------------------------------------------------
# One check diverges
# ---------------------------------------------------------------------------
class OneCheckDivergesTest(CheckAllTestBase):
    def test_a_divergence_names_the_check_expected_and_actual_and_exits_nonzero(self):
        self.write_stub("phase-docs-lint.sh", 3)  # baseline still expects 0
        r = self.run_check_all()
        self.assertNotEqual(0, r.returncode, self.output(r))
        self.assertIn("phase-docs-lint: exit 3 (expected 0) — DIVERGENT", r.stdout, self.output(r))
        self.assertIn("phase-docs-lint: expected exit 0, got exit 3", r.stdout, self.output(r))
        self.assertIn(
            "**Summary:** 7 catalogued, 6 matched, 1 divergent, 0 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )
        self.assertIn("**Exit:** 1", r.stdout, self.output(r))


# ---------------------------------------------------------------------------
# Could-not-run: never a pass, never a failure, always its own bucket
# ---------------------------------------------------------------------------
class CouldNotRunIsNeverCountedAsPassTest(CheckAllTestBase):
    def test_ccpr_only_checks_could_not_run_outside_the_ccpr_checkout(self):
        shutil.rmtree(self.project_dir / "scripts" / "tests")
        r = self.run_check_all()
        self.assertEqual(0, r.returncode, self.output(r))  # could-not-run alone must not fail the run
        self.assertIn("artifact-gate: could-not-run", r.stdout, self.output(r))
        self.assertIn("conformance-run: could-not-run", r.stdout, self.output(r))
        self.assertIn("python-tests: could-not-run", r.stdout, self.output(r))
        self.assertIn(
            "**Checks:** 7 catalogued, 4 ran, 3 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )
        self.assertIn(
            "**Summary:** 7 catalogued, 4 matched, 0 divergent, 3 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )

    def test_conformance_runs_own_not_configured_shape_is_could_not_run_not_a_match(self):
        # exit-code-invisible by conformance-run.sh's own documented design
        # (always exit 0) -- check-all.sh must read its report substring,
        # not just its exit code, to classify this correctly.
        self.write_stub(
            "conformance-run.sh", 0,
            stdout_text="# Conformance Run Report\n\n"
                        "**Consumers:** 0 configured, 0 covered — the conformance check DID NOT RUN\n"
                        "**Exit:** 0\n",
        )
        r = self.run_check_all()
        self.assertIn("conformance-run: could-not-run", r.stdout, self.output(r))
        self.assertNotIn("conformance-run: exit 0 (expected 0) — match", r.stdout, self.output(r))
        self.assertIn(
            "**Summary:** 7 catalogued, 6 matched, 0 divergent, 1 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )


# ---------------------------------------------------------------------------
# Catalogue <-> baseline mismatch: both directions must be loud
# ---------------------------------------------------------------------------
class CatalogueBaselineMismatchTest(CheckAllTestBase):
    def test_unknown_baseline_entry_and_uncovered_catalogue_check_are_both_reported(self):
        mapping = {name: 0 for name in CATALOGUE_NAMES if name != "python-tests"}
        self.write_baseline(mapping, extra_lines=["totally-unknown-check\t0\tstub"])
        r = self.run_check_all()
        self.assertNotEqual(0, r.returncode, self.output(r))
        self.assertIn(
            "python-tests: in the catalogue, but the baseline has no entry for it",
            r.stdout, self.output(r),
        )
        self.assertIn(
            "totally-unknown-check: in the baseline, but the catalogue has no check by that name",
            r.stdout, self.output(r),
        )
        self.assertIn(
            "**Summary:** 7 catalogued, 6 matched, 0 divergent, 0 could-not-run, 2 mismatched",
            r.stdout, self.output(r),
        )


# ---------------------------------------------------------------------------
# The all-could-not-run case: nothing verified is not a pass (KA-G-017 shape)
# ---------------------------------------------------------------------------
class AllCouldNotRunTest(CheckAllTestBase):
    def test_nothing_verified_must_not_report_success(self):
        for script in CATALOGUE_SCRIPTS:
            if script:
                self.remove_stub(script)
        shutil.rmtree(self.project_dir / "scripts" / "tests")
        r = self.run_check_all()
        self.assertNotEqual(0, r.returncode, self.output(r))
        self.assertIn(
            "**Checks:** 7 catalogued, 0 ran, 7 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )
        self.assertIn(
            "**Summary:** 7 catalogued, 0 matched, 0 divergent, 7 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )
        self.assertIn("NOTHING WAS VERIFIED", r.stderr, self.output(r))


# ---------------------------------------------------------------------------
# The contract test: derive both sides, hand-type neither
# ---------------------------------------------------------------------------
class BaselineCatalogueContractTest(unittest.TestCase):
    def test_real_baseline_names_exactly_match_the_real_catalogue(self):
        catalogue_names = set(CATALOGUE_NAMES)
        baseline_names = set(parse_baseline_names(BASELINE_PATH.read_text(encoding="utf-8")))
        self.assertEqual(catalogue_names, baseline_names)

    def test_real_baseline_file_is_actually_readable_by_the_shipped_reader(self):
        # Drives the REAL script's REAL baseline reader (not this module's
        # independent parse_baseline_names re-implementation) against
        # scripts/check-all.baseline.tsv itself, over a scope where every
        # check is could-not-run (empty stub dir, no scripts/tests) so the
        # run stays fast -- what is proven here is that the baseline file
        # PARSES (no die(), CHECK_COUNT baseline lines read), not that any
        # check runs.
        empty_stub_dir = Path(tempfile.mkdtemp(prefix="ccpr-check-all-contract-"))
        self.addCleanup(shutil.rmtree, empty_stub_dir, ignore_errors=True)
        bare_project_dir = Path(tempfile.mkdtemp(prefix="ccpr-check-all-contract-project-"))
        self.addCleanup(shutil.rmtree, bare_project_dir, ignore_errors=True)

        env = dict(os.environ)
        env["CCPR_CHECK_ALL_SCRIPT_DIR"] = str(empty_stub_dir)
        r = subprocess.run(
            ["bash", str(SCRIPT_PATH), "--baseline", str(BASELINE_PATH), str(bare_project_dir)],
            capture_output=True, text=True, env=env, timeout=30,
        )
        detail = "returncode: %s\nstdout:\n%s\nstderr:\n%s" % (r.returncode, r.stdout, r.stderr)
        self.assertNotEqual(2, r.returncode, detail)  # 2 = baseline could not be parsed
        self.assertNotIn("baseline line", r.stderr, detail)
        self.assertIn("**Checks:** 7 catalogued", r.stdout, detail)


# ---------------------------------------------------------------------------
# Mutation-based RED proofs (G-107/G-109 precedent: a checker of this kind
# is untrustworthy until it has been SEEN red)
# ---------------------------------------------------------------------------
class CouldNotRunCountsAsPassRedProofTest(CheckAllTestBase):
    """check-all.sh's three could-not-run branches all assign the literal
    `state="could-not-run"`. Flipping that literal to `state="match"` in a
    scratch copy simulates a defect where an unavailable check is silently
    folded into the pass count. Both CouldNotRunIsNeverCountedAsPassTest's
    and AllCouldNotRunTest's pins must go red against this mutated copy."""

    def setUp(self):
        super().setUp()
        self.scratch_dir = Path(tempfile.mkdtemp(prefix="ccpr-check-all-redproof-a-"))
        self.addCleanup(shutil.rmtree, self.scratch_dir, ignore_errors=True)

    def test_could_not_run_folded_into_match_breaks_both_pins(self):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        needle = 'state="could-not-run"'
        occurrences = original.count(needle)
        self.assertEqual(
            3, occurrences,
            "check-all.sh's own could-not-run assignment literal changed -- update this test",
        )
        match_before = original.count('state="match"')

        def _mutate(text):
            return text.replace(needle, 'state="match"')

        scratch = _write_mutated_script(self.scratch_dir, _mutate)
        mutated_text = scratch.read_text(encoding="utf-8")
        self.assertEqual(0, mutated_text.count(needle), "mutation left the needle behind — it did not fully land")
        self.assertEqual(
            match_before + occurrences, mutated_text.count('state="match"'),
            "replacement count did not land as expected",
        )

        # The mixed could-not-run scenario (CouldNotRunIsNeverCountedAsPassTest)
        # would have asserted this; with the mutation it is false instead.
        shutil.rmtree(self.project_dir / "scripts" / "tests")
        r = self.run_check_all(script_path=scratch)
        # ": could-not-run —" is the per-check finding shape ("- name:
        # could-not-run — reason"), never the zero-count label the
        # **Checks:**/**Summary:** lines always print ("0 could-not-run") --
        # asserting plain "could-not-run" not in stdout would be vacuous,
        # since that substring is present even on a fully clean report.
        self.assertNotIn(": could-not-run —", r.stdout, self.output(r))
        self.assertNotIn(
            "**Summary:** 7 catalogued, 4 matched, 0 divergent, 3 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )

        # The all-could-not-run scenario (AllCouldNotRunTest) would have
        # asserted a non-zero exit; with the mutation a run that verified
        # nothing reports success instead.
        for script in CATALOGUE_SCRIPTS:
            if script:
                self.remove_stub(script)
        r2 = self.run_check_all(script_path=scratch)
        self.assertEqual(0, r2.returncode, self.output(r2))
        self.assertNotIn("NOTHING WAS VERIFIED", r2.stderr, self.output(r2))


class CompareAgainstZeroInsteadOfBaselineRedProofTest(CheckAllTestBase):
    """Mutates the one comparison line check-all.sh uses to classify
    match/divergent (`[ "$rc_str" = "$expected" ]`) to always compare
    against the literal "0" instead. AllChecksMatchBaselineTest's pin on
    the two by-design-nonzero checks (memory-lint expects 1, doc-volume-
    check expects 2) must go red against this mutated copy."""

    def setUp(self):
        super().setUp()
        self.write_stub("memory-lint.sh", 1)
        self.write_stub("doc-volume-check.sh", 2)
        mapping = {name: 0 for name in CATALOGUE_NAMES}
        mapping["memory-lint"] = 1
        mapping["doc-volume-check"] = 2
        self.write_baseline(mapping)
        self.scratch_dir = Path(tempfile.mkdtemp(prefix="ccpr-check-all-redproof-b-"))
        self.addCleanup(shutil.rmtree, self.scratch_dir, ignore_errors=True)

    def test_comparing_against_exit_zero_breaks_the_two_by_design_nonzero_checks(self):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        needle = 'if [ "$rc_str" = "$expected" ]; then'
        self.assertEqual(
            1, original.count(needle),
            "check-all.sh's own match/divergent comparison literal changed -- update this test",
        )
        replacement = 'if [ "$rc_str" = "0" ]; then'

        def _mutate(text):
            return text.replace(needle, replacement, 1)

        scratch = _write_mutated_script(self.scratch_dir, _mutate)
        mutated_text = scratch.read_text(encoding="utf-8")
        self.assertEqual(0, mutated_text.count(needle))
        self.assertEqual(1, mutated_text.count(replacement))

        # AllChecksMatchBaselineTest would have asserted "match" and exit 0
        # for both by-design-nonzero checks; with the mutation both are
        # DIVERGENT instead, and the run fails.
        r = self.run_check_all(script_path=scratch)
        self.assertNotEqual(0, r.returncode, self.output(r))
        self.assertIn("memory-lint: exit 1 (expected 1) — DIVERGENT", r.stdout, self.output(r))
        self.assertIn("doc-volume-check: exit 2 (expected 2) — DIVERGENT", r.stdout, self.output(r))


class DroppedBaselineEntryRedProofTest(unittest.TestCase):
    """Drops one line from a SCRATCH copy of the real baseline file and
    shows the exact set comparison BaselineCatalogueContractTest performs
    no longer holds -- proving that test actually discriminates a baseline
    drift rather than passing vacuously."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="ccpr-check-all-redproof-c-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_a_baseline_missing_one_entry_is_caught_by_the_contract_comparison(self):
        before = BASELINE_PATH.read_bytes()
        original_lines = BASELINE_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
        dropped = [l for l in original_lines if l.startswith("conformance-run\t")]
        self.assertEqual(
            1, len(dropped),
            "scripts/check-all.baseline.tsv's own conformance-run line changed -- update this test",
        )
        mutated_lines = [l for l in original_lines if l not in dropped]
        self.assertEqual(len(original_lines) - 1, len(mutated_lines))

        scratch = self.tmpdir / "check-all.baseline.tsv"
        scratch.write_text("".join(mutated_lines), encoding="utf-8")

        self.assertEqual(before, BASELINE_PATH.read_bytes(), "shipped baseline file content changed")

        catalogue_names = set(CATALOGUE_NAMES)
        baseline_names = set(parse_baseline_names(scratch.read_text(encoding="utf-8")))
        self.assertNotEqual(catalogue_names, baseline_names)
        self.assertIn("conformance-run", catalogue_names - baseline_names)


if __name__ == "__main__":
    unittest.main()
