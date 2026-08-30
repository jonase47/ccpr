"""test_check_all.py -- coverage for scripts/check-all.sh, the single
command CONTRIBUTING.md's "Quality checks before opening a PR" section asks
a contributor to remember by hand: eight commands, one of which is
non-zero on a correct tree BY DESIGN, and none of which anyone was
verifying were actually all run.

## Why exit code alone is the wrong pass criterion, and what replaces it

Measured directly on this repository (29.08.2026, HEAD 961165f):
memory-lint.sh exits 1 (long-standing memory-freshness warnings) and
doc-volume-check.sh exits 2 (known oversized files pending a split) on a
CLEAN tree. (doc-volume-check.sh has since moved to 0 -- it scans only
git-tracked files as of 30.08.2026, and the oversized files it used to
report are all untracked working state. The measurement above is kept with
its own date and HEAD because that is what makes it readable as history
rather than as a current claim.) A script that failed on any non-zero exit would be permanently
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
is only the test-facing half. Seven of the eight checks are shipped sibling
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

## The note column: reasons, not measurements

The baseline's third column is free text nothing parses. That makes it the
one place in the file where a wrong value costs nothing and is therefore
never caught -- and it had filled up with run measurements (file counts,
test counts, findings-by-severity) plus values describing the maintainer's
own machine (targets present, deny-list entries, consumers configured),
which are wrong on any CI runner by construction. `BaselineNoteColumn
CarriesNoQuantitiesTest` pins the separation: durable reasons stay,
quantities go. Its detector deliberately judges whitespace-delimited
tokens with an EDGE-only punctuation strip, because the two durable notes
this repository actually ships are exactly the shapes a careless rule
breaks -- `none` (a substring search for "one" flags it) and `non-zero` (a
`\bzero\b` regex flags it, since a hyphen is a word boundary). `NoteColumn
QuantityRedProofTest` re-introduces a quantity in BOTH number forms, digits
and spelled-out cardinal, rather than deleting one: deleting a note makes
any absence check pass and proves nothing.

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


def parse_baseline_entries(text):
    """(name, note) for every non-comment, non-blank line of a check-all.sh
    baseline TSV. `note` is the third tab-separated column, or "" when the
    line carries none -- check-all.sh's own reader tolerates both shapes
    (`IFS=$'\t' read -r b_name b_exit b_rest` leaves b_rest empty), and
    b_rest is a read target it never consumes."""
    entries = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        name = fields[0]
        if not name:
            continue
        entries.append((name, fields[2] if len(fields) > 2 else ""))
    return entries


def parse_baseline_names(text):
    """The first tab-separated column of every non-comment, non-blank line
    of a check-all.sh baseline TSV -- the same parse check-all.sh's own
    baseline reader performs, reimplemented independently here rather than
    shelling out to the script under test for what is, at this point, pure
    text parsing."""
    return [name for name, _note in parse_baseline_entries(text)]


# Spelled-out cardinals. A quantity does not stop being a quantity because
# it was typed as a word -- "three consumers covered" ages exactly like
# "3 consumers covered" does.
_NUMBER_WORDS = frozenset(
    """zero one two three four five six seven eight nine ten eleven twelve
    thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty
    thirty forty fifty sixty seventy eighty ninety hundred thousand
    dozen""".split()
)

# Stripped from the OUTER edges of a whitespace-delimited token only, never
# from inside it. That single choice is what lets the two durable notes this
# repository actually ships through the rule:
#   * `none` (in "CCPR has none of its own") is one token, and `none` is not
#     in _NUMBER_WORDS -- a substring search for "one" would flag it;
#   * `non-zero` (in "non-zero by design") stays `non-zero` because the
#     hyphen is interior -- a `\bzero\b` regex would flag it, since a hyphen
#     IS a word boundary.
_TOKEN_EDGE = " \t.,;:!?()[]{}<>\"'`\u2014\u2013-/*%"

_NUMERAL_RE = re.compile(r"^\d[\d.,]*$")


def quantity_tokens(note):
    """Every whitespace-delimited token of `note` that states a QUANTITY --
    a bare numeral (`332`, `0`, `1,965`) or a spelled-out cardinal
    (`three`). Returns the tokens as they appear, so a failure names them.

    Known limits, stated rather than discovered later. They are pinned by
    `DocumentedDetectorLimitsTest` below, so this list is a checked claim
    rather than prose that can drift away from the code.

    MISSED (false negatives) -- two distinct fusion mechanisms, not one:
      * separator-mediated: a numeral joined to a word or to another numeral
        by an interior separator (`3-consumer`, `22/33`), and a hyphenated
        cardinal (`three-consumer`);
      * direct: a numeral fused to letters with no separator at all -- an
        ordinal (`1st`, `2nd`, `3rd`) or a multiplier (`3x`). `1st` survives
        edge-stripping intact, fails _NUMERAL_RE on its trailing letters,
        and is not a _NUMBER_WORDS member, so it passes through.
    Also missed: vague quantities that use no numeral at all (`several`,
    `a couple of`).

    WRONGLY CAUGHT (false positives): any durable note carrying a VERSION or
    a numeric identifier -- `requires bash >= 3.2`, `pinned to python 3.12`
    -- is flagged, because the detector cannot tell a version pin from a
    measurement; both are just a numeral. No such note exists in the file
    today. If one is ever needed, rephrase it without the numeral (the
    baseline header already states the bash floor once) or widen the rule
    deliberately -- do not silence the test.

    Both lists are the price of the edge-only strip above, and it is the
    right side to err on: the interior-hyphen rule that would catch
    `three-consumer` is the same one that would falsely flag `non-zero`."""
    found = []
    for raw in note.split():
        token = raw.strip(_TOKEN_EDGE)
        if not token:
            continue
        if _NUMERAL_RE.match(token) or token.lower() in _NUMBER_WORDS:
            found.append(raw)
    return found


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

    def write_argv_capturing_stub(self, script_filename, exit_code, capture_path):
        """Like write_stub, but the stub records its OWN argv (one per line)
        to capture_path before exiting -- used to pin exactly which flags
        check-all.sh passed it, not just its exit code."""
        path = self.stub_dir / script_filename
        path.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$@\" > '{capture}'\n"
            "exit {code}\n".format(capture=capture_path, code=exit_code),
            encoding="utf-8",
        )
        path.chmod(0o755)

    def write_fake_discipline_gate_lib(self, deny_source):
        """Installs a minimal scratch lib/discipline_gate.sh under
        self.stub_dir -- the same seam CCPR_CHECK_ALL_SCRIPT_DIR already
        gives the seven sibling-script stubs, extended to this shared
        library. Exercises the actual integration point (check-all.sh
        sources this file and calls gate_load_config, then reads
        $GATE_DENY_SOURCE) without needing the real, ~900-line pattern
        library or a real ~/.claude/memory-sync.json."""
        lib_dir = self.stub_dir / "lib"
        lib_dir.mkdir(exist_ok=True)
        (lib_dir / "discipline_gate.sh").write_text(
            "#!/usr/bin/env bash\n"
            "gate_load_config() {\n"
            "  GATE_DENY_NAMES=\"\"\n"
            "  GATE_DENY_SOURCE=\"%s\"\n"
            "}\n" % deny_source,
            encoding="utf-8",
        )

    def write_crashing_discipline_gate_lib(self):
        """Installs a scratch lib/discipline_gate.sh whose gate_load_config()
        exits 2 -- the shape a genuinely broken deny-list detection has (e.g.
        a malformed CCPR_GATE_DENY_NAMES that crashes the real library's
        internal grep classification, scripts/lib/discipline_gate.sh:287-298).
        Measured directly against the PRE-fix check-all.sh (30.08.2026):
        sourcing this and calling gate_load_config() at top level killed the
        whole process with exit 2 BEFORE any of the eight checks ran -- no
        report, no "NOTHING WAS VERIFIED" diagnosis, just a bare stderr line
        and a process exit. A crash in ONE check's configuration must never
        prevent the other seven from being attempted, and must never look like
        the ordinary "not configured" case either -- see
        ArtifactGateDenylistDetectionCrashTest below."""
        lib_dir = self.stub_dir / "lib"
        lib_dir.mkdir(exist_ok=True)
        (lib_dir / "discipline_gate.sh").write_text(
            "#!/usr/bin/env bash\n"
            "gate_load_config() {\n"
            "  echo 'gate: something crashed' >&2\n"
            "  exit 2\n"
            "}\n",
            encoding="utf-8",
        )

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
        # Deliberately stubs TWO non-zero-by-design checks, not one, so the
        # "match" branch is exercised twice over -- broader than this
        # repository's own real baseline, which has carried only ONE
        # non-zero entry (memory-lint) since 30.08.2026 (doc-volume-check
        # now scans git-tracked files only and reports 0 on a clean tree).
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
            "**Summary:** 8 catalogued, 8 matched, 0 divergent, 0 could-not-run, 0 mismatched",
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
            "**Summary:** 8 catalogued, 7 matched, 1 divergent, 0 could-not-run, 0 mismatched",
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
            "**Checks:** 8 catalogued, 4 ran, 4 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )
        self.assertIn(
            "**Summary:** 8 catalogued, 4 matched, 0 divergent, 4 could-not-run, 0 mismatched",
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
            "**Summary:** 8 catalogued, 7 matched, 0 divergent, 1 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )

    def test_memory_lints_own_no_targets_shape_is_could_not_run_not_a_match(self):
        # memory-lint.sh's own no-scope state (all four of its targets absent:
        # <project-dir>/docs/memory, ~/.claude/instincts.md,
        # ~/.claude/instincts/, ~/.claude/memory/) is exit-code-invisible by
        # the same design conformance-run.sh already uses — memory-lint.sh
        # still exits 0 there (nothing to warn or error about), so
        # check-all.sh must read its report substring, not just its exit
        # code, to tell "ran and found nothing" apart from "had nothing to
        # run against". Baseline expects 1 (this repository's own by-design
        # memory-freshness warnings) so an exit-0 stub would otherwise be
        # read as a genuine DIVERGENT, not could-not-run.
        self.write_stub(
            "memory-lint.sh", 0,
            stdout_text="# Memory Lint Report\n\n"
                        "**Targets:** 0 of 4 present"
                        " — the memory-lint check DID NOT RUN"
                        " (no docs/memory/, no ~/.claude/instincts.md,"
                        " no ~/.claude/instincts/, no ~/.claude/memory/)\n"
                        "**Files scanned:** 0\n\n"
                        "**Exit:** 0\n",
        )
        mapping = {name: 0 for name in CATALOGUE_NAMES}
        mapping["memory-lint"] = 1
        self.write_baseline(mapping)
        r = self.run_check_all()
        self.assertIn("memory-lint: could-not-run", r.stdout, self.output(r))
        self.assertNotIn("memory-lint: exit 0 (expected 1) — DIVERGENT", r.stdout, self.output(r))
        self.assertIn(
            "**Summary:** 8 catalogued, 7 matched, 0 divergent, 1 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )

    def test_memory_lint_with_a_present_target_still_runs_normally(self):
        # Gegenprobe (counter-proof): a stub that reports at least one
        # present target must be compared against the baseline as usual —
        # without this half, a fix that unconditionally reported
        # could-not-run for memory-lint would pass the test above too.
        self.write_stub(
            "memory-lint.sh", 1,
            stdout_text="# Memory Lint Report\n\n"
                        "**Targets:** 1 of 4 present\n"
                        "**Files scanned:** 3\n\n"
                        "**Exit:** 1\n",
        )
        mapping = {name: 0 for name in CATALOGUE_NAMES}
        mapping["memory-lint"] = 1
        self.write_baseline(mapping)
        r = self.run_check_all()
        self.assertIn("memory-lint: exit 1 (expected 1) — match", r.stdout, self.output(r))
        self.assertNotIn("memory-lint: could-not-run", r.stdout, self.output(r))

    def test_the_no_scope_detection_does_not_depend_on_the_target_count_literal(self):
        # Code-review finding (WI-0129 Paket B): matching on "0 of 4
        # present" AND "DID NOT RUN" together coupled this detector to
        # memory-lint.sh's CURRENT target total. If memory-lint.sh ever
        # gains or loses a target, "0 of 4" stops appearing and this
        # detector silently regresses to reading a genuine no-scope exit-0
        # run as a real divergence again -- unlike conformance-run's "0
        # configured, 0 covered" (safe by construction: COVERED can never
        # exceed CONFIGURED), memory-lint's "N of TOTAL" has no such
        # built-in invariant. This stub reports a DIFFERENT total (6, not
        # 4) to prove the detector reacts to the "DID NOT RUN" phrase
        # alone, not to the specific count text.
        self.write_stub(
            "memory-lint.sh", 0,
            stdout_text="# Memory Lint Report\n\n"
                        "**Targets:** 0 of 6 present"
                        " — the memory-lint check DID NOT RUN"
                        " (a future target set, hypothetically larger)\n"
                        "**Files scanned:** 0\n\n"
                        "**Exit:** 0\n",
        )
        mapping = {name: 0 for name in CATALOGUE_NAMES}
        mapping["memory-lint"] = 1
        self.write_baseline(mapping)
        r = self.run_check_all()
        self.assertIn("memory-lint: could-not-run", r.stdout, self.output(r))
        self.assertNotIn("memory-lint: exit 0 (expected 1) — DIVERGENT", r.stdout, self.output(r))
        self.assertIn(
            "**Summary:** 8 catalogued, 7 matched, 0 divergent, 1 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )


# ---------------------------------------------------------------------------
# artifact-gate's --require-denylist is conditional, and the decision is
# named in the report (WI-0129 Paket B, cycle B3)
# ---------------------------------------------------------------------------
class ArtifactGateRequireDenylistTest(CheckAllTestBase):
    """Measured directly (30.08.2026): a fresh clone with an empty $HOME has
    no gate.denyNames configured anywhere, so artifact-gate.sh --repo .
    --require-denylist exits 1 ("--require-denylist was given but no
    deny-list is configured") while the SAME invocation without the flag
    exits 0. check-all.sh used to pass --require-denylist unconditionally
    (a fixed literal at its own invoke_args assignment), which is exactly
    the fail-open-by-omission shape WI-0129 was built to catch: a CI runner
    with no personal, non-distributed deny-list config reproduces this
    divergence on every single run, not as a regression but by construction.

    The fix reads artifact-gate.sh's OWN deny-list detection
    (`gate_load_config` in scripts/lib/discipline_gate.sh, the single
    source of truth artifact-gate.sh itself sources) rather than
    re-implementing the ~/.claude/memory-sync.json / CCPR_GATE_DENY_NAMES
    lookup a second time in check-all.sh. `write_fake_discipline_gate_lib`
    substitutes a minimal scratch copy of that ONE function
    (`gate_load_config`) under the same CCPR_CHECK_ALL_SCRIPT_DIR seam the
    seven sibling-script stubs already use -- proving the INTEGRATION (source
    the lib, read $GATE_DENY_SOURCE, decide the flag) without needing the
    real ~900-line pattern library.
    """

    def test_require_denylist_is_omitted_when_no_deny_names_are_configured(self):
        self.write_fake_discipline_gate_lib(deny_source="none")
        capture_path = self.tmp / "artifact-gate.argv"
        self.write_argv_capturing_stub("artifact-gate.sh", 0, capture_path)

        r = self.run_check_all()

        self.assertTrue(capture_path.exists(), self.output(r))
        argv = capture_path.read_text(encoding="utf-8").splitlines()
        self.assertNotIn("--require-denylist", argv, argv)
        self.assertIn("--repo", argv, argv)
        # The decision is named in the report, not just silently taken --
        # the same "say what was NOT covered" discipline artifact-gate.sh's
        # own summary line already applies to itself.
        self.assertIn(
            "artifact-gate: deny-list NOT configured — running WITHOUT --require-denylist",
            r.stdout, self.output(r),
        )

    def test_require_denylist_is_passed_when_deny_names_are_configured(self):
        self.write_fake_discipline_gate_lib(deny_source="config")
        capture_path = self.tmp / "artifact-gate.argv"
        self.write_argv_capturing_stub("artifact-gate.sh", 0, capture_path)

        r = self.run_check_all()

        self.assertTrue(capture_path.exists(), self.output(r))
        argv = capture_path.read_text(encoding="utf-8").splitlines()
        self.assertIn("--require-denylist", argv, argv)
        self.assertIn("--repo", argv, argv)
        self.assertIn(
            "artifact-gate: deny-list configured — --require-denylist enforced",
            r.stdout, self.output(r),
        )

    def test_missing_discipline_gate_lib_falls_back_to_omitting_the_flag(self):
        # No lib/discipline_gate.sh under the stub dir at all -- the shape a
        # genuinely broken or partial installation has. check-all.sh must
        # not crash, and must take the same safe default as "not
        # configured": no --require-denylist.
        capture_path = self.tmp / "artifact-gate.argv"
        self.write_argv_capturing_stub("artifact-gate.sh", 0, capture_path)

        r = self.run_check_all()

        self.assertTrue(capture_path.exists(), self.output(r))
        argv = capture_path.read_text(encoding="utf-8").splitlines()
        self.assertNotIn("--require-denylist", argv, argv)
        self.assertIn(
            "artifact-gate: deny-list NOT configured — running WITHOUT --require-denylist",
            r.stdout, self.output(r),
        )


# ---------------------------------------------------------------------------
# A crashing deny-list detection must not abort the whole run, and must not
# look like the ordinary "not configured" case either (PO decision on the
# code-review Important finding, WI-0129 Paket B, 30.08.2026)
# ---------------------------------------------------------------------------
class ArtifactGateDenylistDetectionCrashTest(CheckAllTestBase):
    """Three states, not two: `gate_load_config` can report a deny-list is
    `configured`, report `none` (nobody configured one -- the ordinary,
    supported case on a fresh machine), or -- new here -- CRASH while
    trying to find out. Fail-loud (letting the crash propagate, as the
    pre-fix code did) is wrong because it bypasses the exact rule
    check-all.sh exists to enforce: the crash happens at check-all.sh's own
    top level, BEFORE any of the eight checks run and before RAN_COUNT is
    ever counted, so "NOTHING WAS VERIFIED -- this is not a pass" never
    fires and the other seven checks are never attempted over a config
    problem in ONE of them. A silent fallback to "not configured" is
    equally wrong (the exact fail-open class B3 itself was built to close)
    -- "nobody configured a deny-list" and "the configuration is broken"
    are two different findings, and only the second demands action.

    `test_the_pre_fix_shape_would_have_aborted_before_any_check_ran` is the
    RED proof: it demonstrates the OLD behaviour (measured directly,
    30.08.2026) by running check-all.sh with a needle-based mutation that
    restores the pre-fix single unguarded `gate_load_config` call, so this
    module has a red witness for the very crash it now protects against,
    not just an assertion about a code shape.
    """

    def test_a_crashing_deny_list_detection_does_not_abort_the_whole_run(self):
        self.write_crashing_discipline_gate_lib()
        capture_path = self.tmp / "artifact-gate.argv"
        self.write_argv_capturing_stub("artifact-gate.sh", 0, capture_path)

        r = self.run_check_all()

        # (a) all eight checks still ran, not just artifact-gate.
        self.assertIn(
            "**Checks:** 8 catalogued, 8 ran, 0 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )
        self.assertEqual(0, r.returncode, self.output(r))

        # (b) the report names the broken state, in wording distinct from
        # the ordinary "NOT configured" case -- the whole point of the
        # third state.
        self.assertIn("artifact-gate: deny-list detection FAILED", r.stdout, self.output(r))
        self.assertNotIn(
            "artifact-gate: deny-list NOT configured — running WITHOUT --require-denylist",
            r.stdout, self.output(r),
        )

        # (c) --require-denylist was not passed -- a broken detection must
        # not silently escalate to a stricter run either.
        self.assertTrue(capture_path.exists(), self.output(r))
        argv = capture_path.read_text(encoding="utf-8").splitlines()
        self.assertNotIn("--require-denylist", argv, argv)

    def test_the_pre_fix_shape_would_have_aborted_before_any_check_ran(self):
        # RED proof (G-107/G-109 precedent): mutates a SCRATCH copy back to
        # the pre-fix shape -- a single unguarded `gate_load_config` call,
        # not wrapped in a command substitution -- and shows the exact
        # crash-before-any-check-runs failure this class's other test now
        # guards against. The shipped scripts/check-all.sh is asserted
        # byte-for-byte unchanged afterwards (G-143).
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        needle = (
            '  . "$_gate_lib"\n'
            '  _gate_deny_source="$(gate_load_config >/dev/null 2>&1 '
            "&& printf '%s' \"${GATE_DENY_SOURCE:-none}\")\" || _gate_deny_source=\"error\"\n"
        )
        self.assertIn(
            needle, original,
            "check-all.sh's own gate_load_config invocation shape changed -- update this test",
        )
        mutated_source = original.replace(
            needle,
            '  . "$_gate_lib"\n'
            '  gate_load_config\n'
            '  _gate_deny_source="${GATE_DENY_SOURCE:-none}"\n',
            1,
        )
        self.assertNotEqual(original, mutated_source)

        scratch_dir = Path(tempfile.mkdtemp(prefix="ccpr-check-all-redproof-gatecrash-"))
        self.addCleanup(shutil.rmtree, scratch_dir, ignore_errors=True)
        scratch = scratch_dir / "check-all.sh"
        scratch.write_text(mutated_source, encoding="utf-8")
        scratch.chmod(0o755)

        self.write_crashing_discipline_gate_lib()
        r = self.run_check_all(script_path=scratch)

        # The pre-fix shape: the whole process dies with the crashing
        # function's own exit code, before any report is produced at all.
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertNotIn("**Checks:**", r.stdout, self.output(r))
        self.assertIn("gate: something crashed", r.stderr, self.output(r))

        self.assertEqual(original, SCRIPT_PATH.read_text(encoding="utf-8"), "shipped file content changed")


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
            "**Summary:** 8 catalogued, 7 matched, 0 divergent, 0 could-not-run, 2 mismatched",
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
            "**Checks:** 8 catalogued, 0 ran, 8 could-not-run, 0 mismatched",
            r.stdout, self.output(r),
        )
        self.assertIn(
            "**Summary:** 8 catalogued, 0 matched, 0 divergent, 8 could-not-run, 0 mismatched",
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
        self.assertIn("**Checks:** 8 catalogued", r.stdout, detail)


# ---------------------------------------------------------------------------
# Mutation-based RED proofs (G-107/G-109 precedent: a checker of this kind
# is untrustworthy until it has been SEEN red)
# ---------------------------------------------------------------------------
class CouldNotRunCountsAsPassRedProofTest(CheckAllTestBase):
    """check-all.sh's five could-not-run branches (WI-0129 D2 added
    shellcheck-run.sh's own text-detection branch as the fifth) all assign
    the literal `state="could-not-run"`. Flipping that literal to
    `state="match"` in a scratch copy simulates a defect where an
    unavailable check is silently folded into the pass count. Both
    CouldNotRunIsNeverCountedAsPassTest's and AllCouldNotRunTest's pins
    must go red against this mutated copy."""

    def setUp(self):
        super().setUp()
        self.scratch_dir = Path(tempfile.mkdtemp(prefix="ccpr-check-all-redproof-a-"))
        self.addCleanup(shutil.rmtree, self.scratch_dir, ignore_errors=True)

    def test_could_not_run_folded_into_match_breaks_both_pins(self):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        needle = 'state="could-not-run"'
        occurrences = original.count(needle)
        self.assertEqual(
            5, occurrences,
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
            "**Summary:** 8 catalogued, 4 matched, 0 divergent, 4 could-not-run, 0 mismatched",
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
    its two deliberately-stubbed by-design-nonzero checks (memory-lint
    expects 1, doc-volume-check expects 2 -- a test-only pair broader than
    the real baseline's single non-zero entry since 30.08.2026) must go red
    against this mutated copy."""

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


# ---------------------------------------------------------------------------
# The note column carries reasons, not measurements
# ---------------------------------------------------------------------------
class BaselineNoteColumnCarriesNoQuantitiesTest(unittest.TestCase):
    """The baseline's third column is free text nothing parses -- which is
    exactly why a measurement placed there has no reader: no test compares
    it, no check re-derives it, nothing goes red when it is wrong. It only
    rots, while the file's own header asks for deliberate re-measurement.
    (`artifact-gate`'s file count was stale four times in three days:
    313 -> 323 -> 328 -> 332.) Worse, several such notes described the
    maintainer's own machine -- how many memory-lint targets, deny-list
    entries and conformance consumers are present -- values that are simply
    wrong on any CI runner, where those three checks report could-not-run.

    So the column keeps DURABLE REASONS (why this exit code is the right
    expectation) and nothing a commit can change. What the run measured
    belongs in the run's own report, where it is current by definition."""

    def test_every_real_baseline_note_is_free_of_quantities(self):
        entries = parse_baseline_entries(BASELINE_PATH.read_text(encoding="utf-8"))
        # Positive floor first: an absence assertion over an empty parse is
        # vacuous, so pin that this actually read the shipped file's every
        # entry before judging any note.
        self.assertEqual(sorted(CATALOGUE_NAMES), sorted(name for name, _ in entries))
        offenders = {
            name: quantity_tokens(note)
            for name, note in entries
            if quantity_tokens(note)
        }
        self.assertEqual(
            {}, offenders,
            "baseline note column states quantities that nothing reads and every commit can "
            "invalidate; keep the durable reason, drop the measurement: %s" % offenders,
        )

    def test_the_two_durable_reasons_that_look_numeric_are_kept_and_pass(self):
        # Both phrases are legitimate durable justifications AND both are
        # the exact shapes a careless rule mis-flags: `none` contains "one",
        # and `non-zero` contains "zero" behind what a regex calls a word
        # boundary. Pinned here so a future tightening of quantity_tokens
        # cannot quietly start deleting reasons.
        durable = (
            "no phase folders under docs/ (CCPR has none of its own)",
            "non-zero by design (long-standing memory-freshness warnings)",
        )
        text = BASELINE_PATH.read_text(encoding="utf-8")
        for phrase in durable:
            self.assertEqual([], quantity_tokens(phrase), phrase)
            self.assertIn(phrase, text)


class DocumentedDetectorLimitsTest(unittest.TestCase):
    """`quantity_tokens`'s docstring claims a specific set of things it
    misses and one class it wrongly catches. A claim about the code is a
    testable hypothesis (G-128), and an undertested one drifts: this pins
    every documented case to the behaviour it describes, so widening or
    narrowing the detector without updating the docstring goes red.

    Raised by code review (30.08.2026), which found the original limits
    paragraph named only SEPARATOR-mediated fusion and omitted DIRECT
    fusion (`1st`, `3x`) -- a second mechanism with the same effect -- and
    documented no false-positive class at all."""

    # Documented as MISSED: the detector must return nothing for these.
    DOCUMENTED_FALSE_NEGATIVES = (
        "3-consumer runs",          # separator-mediated fusion
        "22/33 files",              # separator between two numerals
        "three-consumer coverage",  # hyphenated cardinal
        "1st run of the day",       # direct fusion: ordinal
        "2nd pass", "3rd attempt",
        "3x slower",                # direct fusion: multiplier
        "several consumers",        # vague, no numeral
    )

    # Documented as WRONGLY CAUGHT: a version pin is indistinguishable from
    # a measurement to this rule.
    DOCUMENTED_FALSE_POSITIVES = (
        ("requires bash >= 3.2", ["3.2"]),
        ("pinned to python 3.12", ["3.12"]),
    )

    def test_the_documented_false_negatives_really_do_slip_through(self):
        for note in self.DOCUMENTED_FALSE_NEGATIVES:
            self.assertEqual(
                [], quantity_tokens(note),
                "docstring documents %r as missed, but the detector caught it -- "
                "the rule was widened; update the docstring" % note,
            )

    def test_the_documented_false_positive_class_really_is_caught(self):
        for note, expected in self.DOCUMENTED_FALSE_POSITIVES:
            self.assertEqual(
                expected, quantity_tokens(note),
                "docstring documents %r as wrongly caught, but the detector let it "
                "through -- the rule was narrowed; update the docstring" % note,
            )

    def test_the_two_forms_the_detector_must_catch_are_unaffected(self):
        # The counterweight: none of the above may be achieved by making the
        # detector blind. Both number forms the red proof injects stay caught.
        self.assertEqual(["332"], quantity_tokens("332 files scanned"))
        self.assertEqual(["three"], quantity_tokens("three consumers covered"))


class NoteColumnQuantityRedProofTest(unittest.TestCase):
    """G-109: removing a note makes any absence check pass and proves
    nothing. This RE-INTRODUCES a quantity into a SCRATCH copy of the real
    baseline text -- once as digits, once as a spelled-out cardinal, the two
    forms a previous sweep in this repository is on record for missing --
    and shows the check above catches both. G-141: each injection asserts
    its own landing (absent before, present exactly once after) before
    anything is measured."""

    INJECTIONS = (
        ("shellcheck", "22 file(s) scanned"),
        ("conformance-run", "three consumers covered"),
    )

    def test_a_reintroduced_quantity_is_caught_in_both_number_forms(self):
        before = BASELINE_PATH.read_bytes()
        original = BASELINE_PATH.read_text(encoding="utf-8")

        for host, injected in self.INJECTIONS:
            self.assertNotIn(injected, original, "%s: needle already present" % injected)
            prefix = "%s\t" % host
            hosts = [l for l in original.splitlines() if l.startswith(prefix)]
            self.assertEqual(
                1, len(hosts),
                "scripts/check-all.baseline.tsv's own %s line changed -- update this test" % host,
            )
            mutated_line = hosts[0].rstrip("\t") + ("\t" if hosts[0].count("\t") < 2 else "; ") + injected
            mutated = original.replace(hosts[0], mutated_line, 1)
            self.assertEqual(1, mutated.count(injected), "mutation did not land: %s" % injected)

            entries = parse_baseline_entries(mutated)
            offenders = {
                name: quantity_tokens(note)
                for name, note in entries
                if quantity_tokens(note)
            }
            # The exact assertion BaselineNoteColumnCarriesNoQuantitiesTest
            # makes is now false, and it is false about the injected host.
            self.assertNotEqual({}, offenders, "%s: not caught" % injected)
            self.assertEqual([host], list(offenders), "%s: wrong host flagged" % injected)
            self.assertEqual([injected.split()[0]], offenders[host])

        self.assertEqual(before, BASELINE_PATH.read_bytes(), "shipped baseline file content changed")



if __name__ == "__main__":
    unittest.main()
