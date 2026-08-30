r"""test_absence_only_assertions.py -- WI-0125: a meta-scan over this repo's
OWN test sources for the shape G-126 names: a test whose only assertions
about a subprocess result are negative ("X did not happen") carries no
evidence that the thing capable of producing X ever ran. `findings()`
(scripts/tests/*.py's shared helper) returns `[]` on a genuine clean run
AND on a crash with empty stdout -- an `assertFalse(any(...))` over that
list cannot tell the two apart.

## Why this is a test over test sources, not a shipped lint

This is NOT scripts/phase-docs-lint.sh or a sibling shipped check: an
adopter's own test suite is none of this repo's business, and a lint over
test files does not belong beside the document lints. It lives here, next
to what it scans, exactly as a meta-scan (see
test_external_tool_exit_status.py) that never ships to `scripts/`.

## The concrete defect this generalises

Six `covers:` tests in test_phase_docs_lint.py asserted only
`self.assertFalse(any("covers:" in w for w in warnings), warnings)`. When
phase-docs-lint.sh died with empty stdout (a real WI-0122 regression,
reproduced against consumer-a), `findings()` returned `[]` and
every one of them passed -- the full suite reported "1481 tests, OK" while
the tool was dead. Measured on the parent state of commit 5ee931b, with
project names redacted per Constitution Inviolable #2 (pinned offline as
fixtures/parent_test_phase_docs_lint.py.txt -- the `.txt` extension keeps
`unittest discover` from importing it as a test module): 6 of
`CheckHCoversTest`/`CheckHCoversEmptyDirectoryDetectionTest`'s
11 methods were exactly this shape; the other 5 carry an `assertTrue` on an
expected finding and are not blind. See
ParentStateDiscriminationTest below -- the acceptance case this module is
not accepted without.

## The rule is already house convention -- cited, not invented

test_handover_epilogue_bullet.py:18-25 states it first: assert the POSITIVE
form, not the absence of the old string, because a negative-only check
passes vacuously on a file that never had the concept at all.
test_external_tool_exit_status.py:14-18 quotes that module by name and
applies it to shell-tool exit status. scripts/conformance-run.sh's Rule C2
already machine-checks the same idea outward, against consumer projects:
zero scope over a non-empty target is a finding. This module turns C2
inward, onto this repo's own suite.

## Why `ast`, when every other meta-scan in this repo is regex/text-based

`import ast` has zero precedent here (test_external_tool_exit_status.py's
own shell scanner is a deliberately non-general character-by-character
mask, not a parser, because shell has no accessible parser in the stdlib).
Python does. Locating "the boundary of a test method" and "every
`self.assertXxx(...)` call inside it, however many lines its arguments
span" is exactly the case a hand-rolled regex struggles with here -- this
repo's own assertions routinely wrap a generator expression across 3-6
lines (see `test_covers_entry_pointing_to_an_existing_nonempty_directory_
produces_no_findings` in the fixture: a single `assertFalse(any(...))` call
spans 3 physical lines with nested parens). `ast.parse` + `ast.walk` gives
exact method/call boundaries and argument structure for free, with no
heredoc/quote-masking machinery to get subtly wrong. Scope is deliberately
narrow: only enough of the AST is inspected to answer "does this method
call something shaped like a subprocess runner, and is every assertion
about the result negative-shaped" -- not a general Python analyser.

## What counts as a "subprocess invoked" test method

A call to `subprocess.run(...)` directly, or to `self.<name>(...)` /
`self._<name>(...)` where `<name>` matches `_?run(_\w+)?` -- covers every
naming shape actually used across the corpus at write time: `run_lint`,
`run_check`, `run_cleanup`, ... (26 distinct `run_*` helpers) and `_run`,
`_run_command`, `_run_mutant`, `_run_generator_copy`,
`_run_known_dead_link_probe`. A method with no such call is out of scope
entirely -- it cannot exhibit this defect shape because there is nothing
external whose liveness could go unobserved.

**Measured blind spot (28.08.2026, against test_quality_scan_sast_patterns.py,
WI-0126 tranche 3c):** `_calls_a_subprocess` only matches an `ast.Call` whose
`func` is an `ast.Attribute` -- `self.<name>(...)` or `subprocess.run(...)`.
A bare module-level helper function, e.g. `_run_main_against(files)`, parses
as `ast.Call(func=ast.Name(...))` and is invisible to this gate in either
direction. This is why tranche 3c's 22 tests (all built on a module-level
`_run_main_against`, not a `self.<name>` method) did not move this
scanner's in-scope count. This is one of two measured blind spots sharing
one root cause -- see `ClassificationCountsTest`'s docstring ("The
boundary these numbers describe", WI-0128 wave 2a) for the combined
picture, the sibling gap in `_is_stdout_like`, and what it means for the
970/56 pins above; not repeated here.

## What counts as a positive ("liveness") assertion -- recognised in more
## than one shape, per the work item's own calibration requirement

  * `assertTrue(...)` anywhere in the method -- covers every sibling
    `covers:` test asserting an EXPECTED finding IS present (the
    discriminator the fixture is built around).
  * Any assertion whose arguments reference a `.returncode` attribute
    (`result.returncode`, `r.returncode`, ...) -- covers
    test_external_tool_exit_status.py-style and test_log_cleanup_
    behavior.py-style direct exit-status checks, including
    `assertNotEqual(0, r.returncode, ...)`.
  * `assertIn(<literal>, <output>)` where `<output>` is `result.stdout` (or
    a same-named attribute access) directly, or a local variable the
    method itself assigned from such an attribute -- covers
    test_log_cleanup_behavior.py:133 and test_conformance_run.py's
    `for s in (...): self.assertIn(s, r.stdout, ...)` header-line shape.
  * `assertEqual(self.<helper>(...), ...)` where `<helper>` is not
    `findings` and the helper call itself references the output -- covers
    the `files_scanned()` shape (raises `AssertionError` when the
    "**Files scanned:**" report line is missing), generalised to ANY
    similarly-shaped helper rather than hardcoding that one name (this
    repo carries two textually identical copies of `files_scanned()`, in
    test_phase_docs_lint.py and test_manual_lint.py; the rule recognises
    the shape, not either literal method).
  * `assertEqual(len(x), N)` for a nonzero constant `N` -- a crash
    collapses `x` to empty and `len(x)` to 0, failing this assertion
    loudly. Measured false negative (test_memory_lint.py:978): treating
    this shape as merely "not negative" (see below) and leaving it neutral
    still let a method with no OTHER assertion get flagged despite this
    real guard.

## What counts as a negative ("absence") assertion

`assertFalse(...)`, `assertNotIn(...)`, and `assertEqual(...)` where one
side is a bare `[]` literal or a `len(...) == 0` pair -- deliberately NOT
`assertEqual(len(x), N)` for a nonzero `N` (that is a POSITIVE shape, see
above): an orchestrator calibration probe using a coarser version of this
rule (any negative-shaped call, no positive-shape recognition, no
requirement that the method invokes anything) flagged 103 methods across 22
modules, including ordinary "exactly 3 findings" counts that have nothing
to do with liveness. A second, narrowed probe -- same rule, but additionally
requiring the method to call a run helper / `subprocess.run` -- flagged 75
methods across 15 modules; if you see "75" cited elsewhere, it belongs to
that narrower probe, not this one.

A negative-shaped call only counts if it also references something
actually derived from the tracked result (a name bound to the raw
result/its stdout/its findings-list, a `.stdout`/`.returncode`/`.stderr`
attribute, or an inline `self.findings(...)` call) -- measured false
positive (test_conformance_run.py:1539): a method can invoke a subprocess
for an unrelated reason (`git ls-files`, to enumerate tracked files) and
separately assert something about file CONTENTS read off disk, which has
nothing to do with that subprocess's own liveness.

## Two accounting mechanisms for a method already flagged

1. **In-source exemption marker** (below) -- for sites this item's write
   boundary can edit (this module's own future methods,
   test_doc_volume_check.py).
2. **`KNOWN_FINDINGS` registry** -- for the 54 sites measured in the
   CURRENT tree while building this check, none of which this item's write
   boundary permits editing (they live in test files this scanner reads
   but that this work item does not touch). 51 are genuine, unfixed
   liveness gaps reported to the PO in WI-0125's own triage table rather
   than silently absorbed (`known-risk-not-yet-fixed`, mirroring the
   identically-named category in test_external_tool_exit_status.py); three
   are measured false positives of this scanner itself (a custom
   `assert_*` wrapper it cannot see into, a `run_*`-named helper that
   turns out to be a plain in-process call, not a subprocess, and a
   liveness assertion built on a `self.<helper>(...)`-bound local variable
   whose helper is not literally named `self.findings`, so this scanner's
   own name-tracking does not see it -- surfaced when round 2 gated the
   `assertTrue` branch behind `_references_the_result`, see finding B).
   Both mechanisms share one category vocabulary (`EXEMPTION_REASONS`) and are
   enforced by the same mandatory test
   (`EveryAbsenceOnlyTestIsAccountedForTest`) -- a NEW absence-only test
   added to ANY corpus file has neither a baseline entry nor a marker, and
   fails immediately.

## Exemption marker

`# absence-only: exempt <category>` as a trailing comment on the method's
own `def test_...(self):` line (or anywhere within its body -- see
`find_exemption`). Every category actually used -- via a marker OR via
`KNOWN_FINDINGS` -- must be a registered key in `EXEMPTION_REASONS`,
enforced independently by `ExemptionMarkersAreWellFormedTest` below.
"""

import ast
import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = REPO_ROOT / "scripts" / "tests"
FIXTURES_DIR = TESTS_DIR / "fixtures"

RUN_HELPER_RE = re.compile(r"^_?run(_\w+)?$")
MARKER_RE = re.compile(r"#\s*absence-only:\s*exempt\s+([A-Za-z0-9_-]+)")

# One shared reason per category -- see the module docstring for the
# general rule each category is an exception to.
EXEMPTION_REASONS = {
    "known-risk-not-yet-fixed": (
        "identified while building this check (WI-0125): a real, unfixed "
        "gap in an EXISTING test's coverage. Left as-is because this "
        "item's write boundary is this scanner module and "
        "test_doc_volume_check.py, not every test file the corpus "
        "touches -- reported to the PO in the work item's own triage "
        "table rather than silently absorbed. Mirrors the identically-"
        "named category in test_external_tool_exit_status.py."
    ),
    "custom-assert-wrapper-liveness-invisible-to-this-scanner": (
        "the method's only liveness check lives inside a custom, "
        "project-defined `self.assert_<word>(...)` helper (not one of "
        "unittest's own assert* methods) whose own body this scanner "
        "does not inspect -- classifying every non-builtin assert-shaped "
        "call as inherently positive would also hide a genuinely blind "
        "custom wrapper (this corpus has several literally named "
        "`assert_silent`/`assert_nothing_published`), so this is recorded "
        "per-site rather than as a blanket rule."
    ),
    "in-process-call-not-a-subprocess": (
        "the `run_*`-named helper this scanner's naming heuristic treats "
        "as a subprocess invocation is, at this specific site, a plain "
        "in-process Python function call -- a raised exception there "
        "propagates and fails the test outright, it does not silently "
        "collapse to an empty result the way a crashed subprocess's "
        "stdout does. The crash-produces-empty-output failure mode this "
        "check targets does not reproduce the same way here."
    ),
    "helper-bound-list-not-recognised-as-findings": (
        "found while gating the `assertTrue` branch behind "
        "`_references_the_result` (WI-0125 round 2, finding B): the "
        "method's only liveness assertion is `assertTrue(any(<literal> in "
        "f for f in <var>), ...)` where `<var>` is assigned from a "
        "`self.<helper>(...)` call that extracts a findings-shaped list, "
        "but `<helper>` is not literally named `self.findings` (here: "
        "`self.link_findings(result.stdout)`) -- `_findings_bound_names` "
        "only tracks that one exact call, so this scanner's own "
        "`_references_the_result` does not see `<var>` as derived from the "
        "tracked result even though it plainly is. A real liveness "
        "assertion, invisible to this scanner's name-tracking, not a gap "
        "in the underlying test."
    ),
    "chained-stdout-slice-not-tracked-as-output": (
        "found in WI-0126 tranche 4 round 2: `_stdout_bound_names`/"
        "`_is_stdout_like` only track a name bound in ONE hop directly "
        "from a `<expr>.stdout` attribute access -- a name assigned from "
        "a further chain off that attribute (`result.stdout.split(...)"
        "[1].split(...)[0]`, extracting one report section's text) is "
        "invisible to this one-hop tracking. The method's `assertIn(...)` "
        "calls against such a section variable are genuine positive "
        "liveness assertions about the SAME subprocess result -- they "
        "just never register as one, so this scanner sees only the "
        "method's negative-shaped assertions about the same derived name "
        "and misses that the positive ones exist at all."
    ),
}

NEEDS_EXEMPTION = {"absence-only-needs-exemption"}

# Baseline of pre-existing findings, measured 27.08.2026 while building this
# check (WI-0125) -- keyed by (path relative to TESTS_DIR, class name,
# method name). Grandfathers TODAY's corpus so the mandatory test below
# stays green for KNOWN debt/false-positives while still catching any NEW
# absence-only test added to ANY file in the corpus from this point on. See
# the module docstring's "Findings surfaced, not fixed" section and the
# work item's own triage table for the per-site reasoning -- every entry's
# category must be a registered key in EXEMPTION_REASONS above (enforced by
# ExemptionMarkersAreWellFormedTest).
KNOWN_FINDINGS = {}


class TestMethodRecord:
    __slots__ = ("path", "class_name", "method_name", "lineno", "end_lineno", "disposition")

    def __init__(self, path, class_name, method_name, lineno, end_lineno, disposition):
        self.path = path
        self.class_name = class_name
        self.method_name = method_name
        self.lineno = lineno
        self.end_lineno = end_lineno
        self.disposition = disposition

    def __repr__(self):
        return f"{self.path.name}:{self.lineno}:{self.class_name}.{self.method_name}:{self.disposition}"


def _calls_a_subprocess(func_node):
    """True if `func_node`'s body calls `subprocess.run(...)` directly, or
    `self.<name>(...)`/`self._<name>(...)` where `<name>` matches
    `RUN_HELPER_RE` -- see the module docstring for the full naming
    inventory this was measured against."""
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        func = node.func
        if not isinstance(func.value, ast.Name):
            continue
        if func.value.id == "self" and RUN_HELPER_RE.match(func.attr):
            return True
        if func.value.id == "subprocess" and func.attr == "run":
            return True
    return False


def _stdout_bound_names(func_node):
    """Local variable names assigned directly from a `<expr>.stdout`
    attribute access anywhere in the method -- lets `assertIn(x, output)`
    be recognised as a liveness check even when the attribute access
    happened on an earlier line, not inline in the assertion itself."""
    names = set()
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Assign):
            continue
        if isinstance(node.value, ast.Attribute) and node.value.attr == "stdout":
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _result_bound_names(func_node):
    """Local variable names assigned directly from the subprocess call
    itself (`result = self.run_lint(...)`, `r = subprocess.run(...)`)."""
    names = set()
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        is_call = isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
        if is_call and isinstance(value.func.value, ast.Name):
            recv, attr = value.func.value.id, value.func.attr
            if (recv == "self" and RUN_HELPER_RE.match(attr)) or (recv == "subprocess" and attr == "run"):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
    return names


def _findings_bound_names(func_node):
    """Local variable names assigned from `self.findings(...)` -- the
    shared extraction helper (identical in test_phase_docs_lint.py and
    test_manual_lint.py) that turns a raw report into a bullet-line list.
    A negative assertion built from one of these names IS about the
    result, even though the assignment already stripped the `.stdout`
    attribute access out of view at the assertion site."""
    names = set()
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "self"
            and value.func.attr == "findings"
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _is_findings_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and node.func.attr == "findings"
    )


def _references_the_result(node, result_names, stdout_names, findings_names):
    """True if `node` (typically one `assertXxx(...)` call) mentions
    something actually derived from the subprocess result -- a name bound
    to the raw result/its stdout/its findings-list, a `.stdout`/
    `.returncode`/`.stderr` attribute, or an inline `self.findings(...)`
    call. Without this, a negative assertion about a completely unrelated
    local value (built from something the method read off disk, say) would
    be mistaken for an absence-only liveness gap -- measured false
    positive, see UnrelatedSubprocessCallIsNotMistakenForLivenessTest."""
    tracked_names = result_names | stdout_names | findings_names
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute) and n.attr in ("stdout", "returncode", "stderr"):
            return True
        if isinstance(n, ast.Name) and n.id in tracked_names:
            return True
        if _is_findings_call(n):
            return True
    return False


def _is_stdout_like(node, stdout_names):
    if isinstance(node, ast.Attribute) and node.attr == "stdout":
        return True
    if isinstance(node, ast.Name) and node.id in stdout_names:
        return True
    return False


def _references_stdout_like(node, stdout_names):
    return any(_is_stdout_like(n, stdout_names) for n in ast.walk(node))


def _references_returncode(node):
    return any(isinstance(n, ast.Attribute) and n.attr == "returncode" for n in ast.walk(node))


def _is_empty_list_literal(node):
    return isinstance(node, ast.List) and len(node.elts) == 0


def _len_call_and_constant(a, b):
    """If `a` is `len(...)` and `b` is an int constant, returns that
    constant's value; else None. Order-independent -- caller tries both."""
    if (
        isinstance(a, ast.Call)
        and isinstance(a.func, ast.Name)
        and a.func.id == "len"
        and isinstance(b, ast.Constant)
        and isinstance(b.value, int)
    ):
        return b.value
    return None


def _is_len_zero_pair(a, b):
    return _len_call_and_constant(a, b) == 0 or _len_call_and_constant(b, a) == 0


def _is_len_nonzero_pair(a, b):
    """`assertEqual(len(x), N)` for a nonzero N -- a real liveness guard
    (a crash collapses x to empty, dropping len(x) to 0 and failing this
    assertion loudly), not the calibration probe's over-fire example (which
    wrongly treated it as an ABSENCE claim instead). See
    ExactNonzeroCountIsRecognisedAsLivenessTest."""
    for x, y in ((a, b), (b, a)):
        value = _len_call_and_constant(x, y)
        if value is not None and value != 0:
            return True
    return False


def _is_self_helper_call(node):
    """A call to `self.<name>(...)` where `<name>` is not itself an
    `assert*`/`findings` method -- the generalised `files_scanned()`
    shape: some OTHER project-specific helper feeding an assertion."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and node.func.attr != "findings"
        and not node.func.attr.startswith("assert")
    )


def _classify_assert_call(call, stdout_names, result_names, findings_names):
    """Classifies one `self.assertXxx(...)` call as "positive" (a liveness
    assertion), "negative" (an absence-shaped assertion ABOUT the tracked
    result) or "neutral" (neither -- an ordinary equality check, or a
    negative-shaped assertion about something that has nothing to do with
    the subprocess result). See the module docstring for the full shape
    inventory."""
    method = call.func.attr
    args = call.args
    # A `_run_*`-named helper may return the extracted stdout TEXT directly
    # (its own last statement ends in `....stdout`) rather than the raw
    # CompletedProcess -- a caller binding that return value is, from this
    # function's own AST, indistinguishable from binding the raw object.
    # Treated as output-like either way: measured false negative, see
    # RunHelperReturningRawTextIsRecognisedAsLivenessTest.
    output_names = stdout_names | result_names

    if method == "assertTrue":
        if _references_the_result(call, result_names, stdout_names, findings_names):
            return "positive"
        return "neutral"
    if _references_returncode(call):
        return "positive"
    if method == "assertIn" and len(args) >= 2 and _is_stdout_like(args[1], output_names):
        return "positive"
    if method == "assertEqual" and len(args) >= 2:
        a, b = args[0], args[1]
        for candidate in (a, b):
            if _is_self_helper_call(candidate) and _references_stdout_like(candidate, output_names):
                return "positive"
        if _is_len_nonzero_pair(a, b):
            return "positive"

    if not _references_the_result(call, result_names, stdout_names, findings_names):
        return "neutral"

    if method in ("assertFalse", "assertNotIn"):
        return "negative"
    if method == "assertEqual" and len(args) >= 2:
        a, b = args[0], args[1]
        if _is_empty_list_literal(a) or _is_empty_list_literal(b):
            return "negative"
        if _is_len_zero_pair(a, b) or _is_len_zero_pair(b, a):
            return "negative"

    return "neutral"


def _classify_method(func_node):
    """A method is `absence-only-needs-exemption` when it (a) invokes a
    subprocess, (b) carries at least one negative-shaped assertion ABOUT
    the tracked result, and (c) carries no positive-shaped assertion at
    all. A subprocess-invoking method with no such negative assertion has
    nothing this check could ever flag and is classified `not-flagged`. A
    method that never invokes a subprocess is out of scope entirely
    (returns None -- see the module docstring)."""
    if not _calls_a_subprocess(func_node):
        return None

    stdout_names = _stdout_bound_names(func_node)
    result_names = _result_bound_names(func_node)
    findings_names = _findings_bound_names(func_node)
    saw_positive = False
    saw_negative = False
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr.startswith("assert"):
            outcome = _classify_assert_call(node, stdout_names, result_names, findings_names)
            if outcome == "positive":
                saw_positive = True
            elif outcome == "negative":
                saw_negative = True

    if saw_negative and not saw_positive:
        return "absence-only-needs-exemption"
    return "not-flagged"


def _scan_file_raw(path):
    """Internal: the same enumeration as `scan_file()`, but each result
    also carries its own FunctionDef AST node -- mirrors
    test_external_tool_exit_status.py's `_scan_file_raw`/`scan_file` split
    (a check that needs to inspect a method's own body further, without
    re-parsing the file, can use this directly)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                disposition = _classify_method(item)
                if disposition is None:
                    continue
                rec = TestMethodRecord(
                    path, node.name, item.name, item.lineno, item.end_lineno, disposition
                )
                results.append((rec, item))
    return results


def scan_file(path):
    """Enumerates every `test_*` method in `path` and classifies each one.
    See the module docstring for the full method."""
    return [rec for rec, _node in _scan_file_raw(path)]


def scan_tree(tests_dir=TESTS_DIR):
    files = sorted(tests_dir.glob("*.py")) + sorted((tests_dir / "workitems").glob("*.py"))
    files = [f for f in files if f.name != "__init__.py"]
    results = []
    for f in files:
        results.extend(scan_file(f))
    return results


def find_exemption(path, lineno, end_lineno):
    """Searches the marker regex on every physical line from `lineno`
    through `end_lineno` (inclusive) -- mirrors
    test_external_tool_exit_status.py's `find_exemption`. Returns the
    category name, or None."""
    all_lines = path.read_text(encoding="utf-8").split("\n")
    for ln in range(lineno, end_lineno + 1):
        if ln < 1 or ln > len(all_lines):
            continue
        m = MARKER_RE.search(all_lines[ln - 1])
        if m:
            return m.group(1)
    return None


def _write_fixture(tmp_path, source):
    tmp_path.write_text(source, encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


class UnrelatedSubprocessCallIsNotMistakenForLivenessTest(unittest.TestCase):
    """Measured false positive (test_conformance_run.py:1539,
    `test_no_tracked_file_matches_the_conformance_report_heading`): a method
    can call a subprocess (`git ls-files`, to enumerate tracked files) for a
    reason that has NOTHING to do with the negative assertion it makes --
    the assertion here is about file CONTENTS read separately from disk,
    never about the subprocess's own stdout/returncode. A negative
    assertion only counts against a method if it actually references
    something derived from a tracked result -- a name assigned from the
    subprocess call, a `.stdout`/`.returncode`/`.stderr` attribute, or
    `self.findings(...)`."""

    def test_a_negative_assertion_on_an_unrelated_local_list_is_not_flagged(self):
        source = (
            "import subprocess\n"
            "import unittest\n"
            "\n"
            "class T(unittest.TestCase):\n"
            "    def test_no_tracked_file_matches_something(self):\n"
            "        r = subprocess.run(['git', 'ls-files'], capture_output=True, text=True)\n"
            "        offenders = []\n"
            "        for rel in r.stdout.splitlines():\n"
            "            if bad(rel):\n"
            "                offenders.append(rel)\n"
            "        self.assertEqual([], offenders)\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_fixture(Path(tmp) / "test_unrelated_fixture.py", source)
            recs = scan_file(path)
        self.assertEqual(1, len(recs))
        self.assertNotIn(recs[0].disposition, NEEDS_EXEMPTION)


class ExactNonzeroCountIsRecognisedAsLivenessTest(unittest.TestCase):
    """Measured false negative (test_memory_lint.py:978,
    `test_a_comment_inside_a_link_destination_is_literal_text_not_a_comment`):
    `assertEqual(len(findings), 1, findings)` asserts an EXACT, nonzero
    finding count. A crash (empty stdout) collapses `findings` to `[]`,
    `len(...)` to 0, and this assertion FAILS loudly -- it is exactly as
    much a liveness guard as `assertTrue(any(...))`, just phrased as a
    count instead of an existence check. `_is_len_zero_pair` already
    excludes this shape from the NEGATIVE bucket (the calibration probe's
    own over-fire example); it must also be recognised as POSITIVE, not
    left NEUTRAL, or a method whose only other assertion is a genuine
    absence check gets flagged despite this real guard."""

    def test_an_exact_nonzero_length_assertion_counts_as_positive(self):
        source = (
            "import unittest\n"
            "\n"
            "class T(unittest.TestCase):\n"
            "    def test_a_comment_is_literal_text(self):\n"
            "        result = self.run_lint()\n"
            "        findings = self.link_findings(result.stdout)\n"
            "        self.assertEqual(len(findings), 1, findings)\n"
            "        self.assertNotIn(chr(1), result.stdout, result.stdout)\n"
            "        self.assertIn(\"dead.md\", findings[0])\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_fixture(Path(tmp) / "test_nonzero_len_fixture.py", source)
            recs = scan_file(path)
        by_name = {r.method_name: r for r in recs}
        self.assertNotIn(
            by_name["test_a_comment_is_literal_text"].disposition, NEEDS_EXEMPTION
        )


class RunHelperReturningRawTextIsRecognisedAsLivenessTest(unittest.TestCase):
    """Measured false negative in the OTHER direction (test_memory_lint.py's
    `LinkScannerMutationTest` family, e.g.
    `test_escape_parity_replaced_by_a_one_byte_lookbehind_flips_a_live_link_
    silent`): a `_run_*`-named helper can return the extracted stdout TEXT
    directly (its own last statement is `...subprocess.run(...).stdout`),
    rather than the raw `CompletedProcess`. A caller then does
    `out = self._run_mutant(...)` followed by `self.assertIn(needle, out)` --
    a genuine positive/liveness assertion (it fails outright if the mutant
    produced no output at all), but `out` is bound to the run-helper's
    return value directly, never to a `.stdout` attribute access the
    caller's own AST can see. Recognising only `.stdout`-bound names for
    `assertIn` would misclassify this method as absence-only despite having
    a real positive assertion."""

    def test_assertin_against_a_bare_run_helper_return_value_counts_as_positive(self):
        source = (
            "import unittest\n"
            "\n"
            "class T(unittest.TestCase):\n"
            "    def _run_mutant(self, mutated):\n"
            "        return subprocess.run(['bash', mutated], capture_output=True, text=True).stdout\n"
            "\n"
            "    def test_flips_a_live_link_silent(self):\n"
            "        out = self._run_mutant('scratch.sh')\n"
            "        self.assertIn('control.md', out, 'must still report the control link')\n"
            "        self.assertNotIn('mutated.md', out)\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_fixture(Path(tmp) / "test_run_helper_fixture.py", source)
            recs = scan_file(path)
        by_name = {r.method_name: r for r in recs}
        self.assertNotIn(
            by_name["test_flips_a_live_link_silent"].disposition, NEEDS_EXEMPTION
        )


class UnrelatedAssertTrueDoesNotMaskABlindNegativeAssertionTest(unittest.TestCase):
    """WI-0125 round 2, finding B: before the `assertTrue` branch of
    `_classify_assert_call` was gated behind `_references_the_result`, ANY
    `assertTrue(...)` anywhere in a method counted as a liveness assertion --
    even one that has nothing to do with the tracked subprocess result. A
    method that calls a subprocess, carries a genuinely blind
    `assertFalse(any(...))` about the tracked result, AND an unrelated
    `assertTrue(...)` about a fixture precondition was therefore classified
    `not-flagged` -- the item's own failure mode, moved one level down. The
    co-occurrence shape is real, not hypothetical: see
    test_baseline_archive_directory.py:129-130
    (`test_the_legacy_directory_and_its_contents_survive_untouched`) for an
    unrelated `assertTrue` beside a subprocess call in this corpus -- that
    one has no negative assertion so it is not itself mis-classified, but
    this fixture reproduces the combined shape that would be."""

    def test_an_unrelated_asserttrue_does_not_suppress_a_blind_negative_assertion(self):
        source = (
            "import os\n"
            "import unittest\n"
            "\n"
            "class T(unittest.TestCase):\n"
            "    def test_fixture_survives_untouched(self):\n"
            "        result = self.run_lint()\n"
            "        self.assertTrue(os.path.isdir('fixtures'))\n"
            "        self.assertFalse(any('unexpected' in w for w in result.stdout))\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_fixture(Path(tmp) / "test_unrelated_asserttrue_fixture.py", source)
            recs = scan_file(path)
        self.assertEqual(1, len(recs))
        self.assertIn(recs[0].disposition, NEEDS_EXEMPTION)


class ParentStateDiscriminationTest(unittest.TestCase):
    """WI-0125 acceptance: run the scanner against the pinned parent state
    of commit 5ee931b, with project names redacted per Constitution
    Inviolable #2 (fixtures/parent_test_phase_docs_lint.py.txt) and
    require it to flag precisely the six negative-only `covers:` methods,
    never the five sibling methods that carry a positive assertion. This is
    the discriminating case the work item is not accepted without."""

    FIXTURE = FIXTURES_DIR / "parent_test_phase_docs_lint.py.txt"
    COVERS_CLASSES = ("CheckHCoversTest", "CheckHCoversEmptyDirectoryDetectionTest")

    EXPECTED_FLAGGED = {
        "test_covers_entry_pointing_to_an_existing_nonempty_directory_produces_no_findings",
        "test_covers_entry_block_syntax_existing_nonempty_directory_produces_no_findings",
        "test_covers_entry_pointing_to_an_existing_file_produces_no_findings",
        "test_covers_field_absent_produces_no_findings",
        "test_directory_with_a_file_several_levels_deep_produces_no_findings",
        "test_directory_whose_only_content_is_a_gitkeep_file_is_not_reported_as_empty",
    }
    EXPECTED_NOT_FLAGGED = {
        "test_covers_entry_nonexistent_path_is_reported_as_error",
        "test_covers_entry_existing_empty_directory_is_reported_as_warning",
        "test_covers_entry_is_resolved_exclusively_against_project_root",
        "test_covers_check_runs_in_the_reviews_profile_too",
        "test_directory_containing_only_empty_nested_subdirectories_is_reported_as_warning",
    }

    def test_the_six_named_methods_are_flagged_and_the_five_siblings_are_not(self):
        self.assertTrue(self.FIXTURE.is_file(), f"missing fixture: {self.FIXTURE}")
        records = [rec for rec in scan_file(self.FIXTURE) if rec.class_name in self.COVERS_CLASSES]
        flagged = {rec.method_name for rec in records if rec.disposition in NEEDS_EXEMPTION}
        not_flagged = {rec.method_name for rec in records if rec.disposition not in NEEDS_EXEMPTION}

        self.assertEqual(self.EXPECTED_FLAGGED, flagged)
        self.assertEqual(self.EXPECTED_NOT_FLAGGED, not_flagged)


class EveryAbsenceOnlyTestIsAccountedForTest(unittest.TestCase):
    def test_every_absence_only_test_is_exempted_or_baselined(self):
        """Positive-form pin (mirrors test_handover_epilogue_bullet.py and
        test_external_tool_exit_status.py's own main test): every
        absence-only-shaped test method found across the corpus TODAY is
        either a pre-existing, individually reasoned `KNOWN_FINDINGS` entry
        or carries a `# absence-only: exempt <category>` marker naming a
        registered category. Catches a NEW absence-only test added to ANY
        corpus file starting the next run -- it has no baseline entry and
        no marker, so it fails here until someone decides which it is."""
        violations = []
        for rec in scan_tree():
            if rec.disposition not in NEEDS_EXEMPTION:
                continue
            key = (rec.path.relative_to(TESTS_DIR).as_posix(), rec.class_name, rec.method_name)
            if key in KNOWN_FINDINGS:
                if KNOWN_FINDINGS[key] not in EXEMPTION_REASONS:
                    violations.append(
                        f"{key[0]}:{rec.lineno}: {key[1]}.{key[2]} baselined under "
                        f"unregistered category {KNOWN_FINDINGS[key]!r}"
                    )
                continue
            category = find_exemption(rec.path, rec.lineno, rec.end_lineno)
            if category is None:
                violations.append(
                    f"{rec.path.relative_to(REPO_ROOT)}:{rec.lineno}: {rec.class_name}."
                    f"{rec.method_name} -- new absence-only test, not in KNOWN_FINDINGS "
                    "and no `# absence-only: exempt <category>` marker found"
                )
            elif category not in EXEMPTION_REASONS:
                violations.append(
                    f"{rec.path.relative_to(REPO_ROOT)}:{rec.lineno}: {rec.class_name}."
                    f"{rec.method_name} marked exempt with unregistered category "
                    f"{category!r} (not a key in EXEMPTION_REASONS)"
                )
        self.assertEqual(
            [],
            violations,
            "Unaccounted-for absence-only test(s) -- add a liveness assertion, "
            "register a `KNOWN_FINDINGS` entry, or mark a reasoned exemption: "
            + "; ".join(violations),
        )


class NoStaleKnownFindingsTest(unittest.TestCase):
    """WI-0125 round 2, finding E, decided IMPLEMENTED: without this test,
    a `KNOWN_FINDINGS` entry whose method later gets a real liveness fix
    (or is deleted/renamed) stops being classified
    absence-only-needs-exemption, but nothing removes the now-stale
    baseline entry -- it sits there forever, unused and unnoticed, drifting
    from what the corpus actually looks like. Chosen over declining it: the
    coupling this creates -- fixing a blind test's liveness gap also
    requires deleting its `KNOWN_FINDINGS` entry, or the suite goes red
    until you do -- forces exactly the bookkeeping this module already
    enforces in the other direction (`EveryAbsenceOnlyTestIsAccountedForTest`
    fails a NEW absence-only test with no entry or marker); declining would
    have left one accounting direction enforced and the other silent,
    which does not match the "no silent drift" standard this module already
    holds itself to (see ClassificationCountsTest's docstring)."""

    def test_no_stale_known_findings(self):
        currently_flagged = {
            (rec.path.relative_to(TESTS_DIR).as_posix(), rec.class_name, rec.method_name)
            for rec in scan_tree()
            if rec.disposition in NEEDS_EXEMPTION
        }
        # With KNOWN_FINDINGS empty (WI-0128 finding #1 closed the last
        # entry in wave 3 tranche 4), the comparison below iterates nothing
        # and `stale` is unconditionally [] -- the assertion would pass even
        # if scan_tree() returned garbage or nothing at all. A bookkeeping
        # test that cannot fail is the exact defect this module exists to
        # find, so the scan itself is pinned as live here: the corpus is
        # known non-empty, and a scanner that stops enumerating fails this
        # test rather than reporting a clean baseline.
        self.assertGreater(
            len(currently_flagged) + len(scan_tree()),
            0,
            "scan_tree() enumerated nothing -- the stale-entry comparison "
            "below would pass vacuously against an empty corpus",
        )

        stale = sorted(key for key in KNOWN_FINDINGS if key not in currently_flagged)
        self.assertEqual(
            [],
            stale,
            "KNOWN_FINDINGS entry no longer matches a currently-flagged method "
            "-- remove the baseline entry (the underlying test is fixed, "
            "renamed, or deleted): " + "; ".join(f"{k[0]}:{k[1]}.{k[2]}" for k in stale),
        )


class ClassificationCountsTest(unittest.TestCase):
    def test_classification_counts(self):
        """Regression pin on the measured baseline: 1051 `test_*` methods
        across the corpus call something shaped like a subprocess invocation
        and are therefore in scope for this check; 0 of those are currently
        absence-only-needs-exemption -- `KNOWN_FINDINGS` above is empty for
        the first time since WI-0125 opened it -- every method carries at
        least one recognised positive/liveness assertion. A change in
        either number means a test changed shape or this scanner's own
        logic changed -- a deliberate look either way, never a silent
        drift.

        Trajectory, so the history is one line per event rather than a
        growing paragraph:

          in-scope / flagged   when
          1051 / 0             WI-0129 Paket B, PO decision follow-up on the
                               code-review's second Important finding
                               (30.08.2026): gate_load_config()'s own
                               internal `exit 2` used to run at
                               check-all.sh's own top level, killing the
                               whole process before any of the seven checks
                               were attempted -- fixed to run inside a
                               command substitution (`exit 2` inside `$(...)`
                               only ends that subshell) with a third
                               GATE_DENY_STATE value ("error", distinct from
                               "configured"/"none") named in the report. +2
                               in scope in the new
                               ArtifactGateDenylistDetectionCrashTest, both
                               driving `self.run_check_all`: one proves all
                               seven checks still run and the report names
                               the broken state distinctly from "NOT
                               configured"; the other is the RED proof,
                               mutating a SCRATCH copy back to the pre-fix
                               single unguarded `gate_load_config` call and
                               showing the crash-before-any-report failure
                               directly (G-107/G-109 precedent -- neither
                               test asserts an absence alone). Not flagged:
                               both assert on the exact **Checks**/report
                               text or the crash's own returncode/stderr.
                               File count unchanged at 53.
          1049 / 0             WI-0129 Paket B, code-review follow-up
                               (30.08.2026): the reviewer found that
                               check-all.sh's memory-lint no-scope detector
                               matched on "0 of 4 present" AND "DID NOT RUN"
                               together, coupling it to memory-lint.sh's
                               CURRENT target total -- unlike
                               conformance-run's "0 configured, 0 covered"
                               (safe by construction), a future change to
                               that total would silently break the match.
                               Fixed to match on the "DID NOT RUN" phrase
                               alone; +1 in scope
                               (test_the_no_scope_detection_does_not_depend_
                               on_the_target_count_literal, driving
                               `self.run_check_all` with a stub reporting
                               "0 of 6 present" to prove the count text is
                               irrelevant to the match). Not flagged: it
                               asserts on the exact **Summary** line. File
                               count unchanged at 53.
          1048 / 0             WI-0129 Paket B, cycle B3 (30.08.2026):
                               check-all.sh's own --require-denylist
                               decision (only pass it to artifact-gate.sh
                               when a deny-list is actually configured, read
                               from lib/discipline_gate.sh's own
                               gate_load_config rather than re-derived) gets
                               three new tests in
                               ArtifactGateRequireDenylistTest, all driving
                               `self.run_check_all` and asserting on the
                               captured argv file plus the named report
                               line -- none absence-only. +3 in scope, 0
                               newly flagged. File count unchanged at 53:
                               all three methods landed in the
                               already-counted test_check_all.py.
          1045 / 0             WI-0129 Paket B, cycles B1+B2 (30.08.2026): a
                               CI runner's own empty $HOME and untracked-doc
                               shapes (memory-lint.sh's four targets all
                               absent; doc-volume-check.sh's oversized files
                               all untracked) both need check-all.sh to read
                               a could-not-run/tracked-scope report
                               substring rather than a bare exit code. +9 in
                               scope: 2 in test_check_all.py (both drive
                               `self.run_check_all`, asserting named summary
                               lines), 4 in test_doc_volume_check.py's new
                               TrackedOnlyScopeTest (all drive
                               `self.run_check`, asserting the exact bullet
                               list and/or the "Untracked skipped" count), 3
                               in test_memory_lint.py's new
                               NoScopeReportedForCheckAllTest (all drive
                               `self.run_lint`). Flagged unchanged at 0: one
                               of the nine
                               (`test_only_a_global_target_present_is_also_
                               a_normal_run`) was genuinely absence-only on
                               first write -- two `assertNotIn` calls with no
                               positive claim -- and was fixed here, not
                               exempted, with a precise `assertIn("**Targets:**
                               1 of 4 present", ...)` pinning the one target
                               this fixture actually leaves present. File
                               count unchanged at 53 (see
                               ScannedFilesCoverTheShippedScopeTest) -- all
                               nine methods landed in already-counted files.
          1036 / 0             CCPR CI prep, three independent cycles
                               (30.08.2026): +3, one new in-scope method per
                               cycle. `test_log_cleanup_behavior.py`'s
                               ArchiveDirectoryPermissionsTest gained a
                               `run_with_umask` helper -- matches
                               `RUN_HELPER_RE` the same way F7's
                               `_run_fake_tool` did, so its one test method
                               entered scope; it carries
                               `self.assertEqual(0, r.returncode, ...)`,
                               recognised positive, not flagged.
                               `test_run_tests_mktemp_templates.py` (new
                               file) has one in-scope method,
                               `test_mktemp_templates_do_not_collide_on_
                               repeated_calls`, calling `subprocess.run(...)`
                               directly twice; both calls are asserted on by
                               `.returncode` and the two resulting paths are
                               asserted unequal -- not flagged. Its sibling
                               methods in the same file
                               (`test_all_mktemp_calls_end_in_a_bare_
                               placeholder_run`, `test_no_hardcoded_pytest_
                               cov_json_path_remains`) never invoke a
                               subprocess at all -- pure file-content checks,
                               correctly out of scope, not a blind spot.
                               `test_gitattributes_crlf_guard.py` (new file)
                               has one in-scope method,
                               `test_representative_text_file_resolves_to_
                               lf`, which calls `subprocess.run(...)`
                               inline; three of its four siblings
                               (`test_logo_pngs_are_declared_binary`,
                               `test_no_tracked_text_file_has_crlf_line_
                               endings`, `test_detector_flags_a_genuine_
                               crlf_text_file`) route their subprocess calls
                               through module-level helpers
                               (`is_declared_binary`, `crlf_violations`) or a
                               non-run-shaped self-method (`self._git`,
                               matches neither `RUN_HELPER_RE` nor
                               `subprocess.run`) -- the SAME module-level-
                               helper blind spot already named in this
                               module's own docstring (`_calls_a_subprocess`
                               only matches `ast.Call(func=ast.Attribute)`)
                               and in this test's own "boundary" section
                               below, not a new gap and not a rename-to-dodge
                               attempt: the helpers are named for what they
                               do (`crlf_violations`, `is_declared_binary`),
                               unchanged from how they were written before
                               this pin was ever measured. None of the three
                               is actually blind in the dangerous sense this
                               scanner targets: `crlf_violations` calls
                               `subprocess.run(..., check=True)`, so a dead
                               `git` raises and fails the test outright
                               rather than collapsing to an empty result;
                               `is_declared_binary` returns `False` on empty
                               stdout, which pushes affected paths TOWARD
                               being flagged as CRLF violations, not away
                               from it -- the fail-open direction is safe
                               here, unlike the bug shape this check exists
                               to catch. Fourth sibling
                               (`test_gitattributes_normalizes_text_to_lf`)
                               reads the `.gitattributes` file directly, no
                               subprocess at all, correctly out of scope.
                               File count 51 -> 53 (see
                               ScannedFilesCoverTheShippedScopeTest for that
                               side).
          1033 / 0             F10's two follow-ups (29.08.2026): the session
                               logs get 0700/0600 with the mode re-asserted on
                               files that already existed, and both writers
                               carry O_NOFOLLOW -- the log write appends and
                               then fchmods, so a STALE symlink corrupts and
                               re-permissions a file with no attacker at all.
                               +6 in scope over two rounds, flagged unchanged
                               at 0: the symlink tests assert the canary's
                               bytes AND its mode, before and after.
          1027 / 0             WI-0129 finding F10 (29.08.2026): the monitor
                               hook validates the session id before it
                               reaches a path, and its loop state moved from
                               a hardcoded world-readable /tmp to the user's
                               own TMPDIR at 0600. +10 in scope, each driving
                               the real hook with crafted stdin; flagged
                               unchanged at 0 -- they assert on the resolved
                               path and the mode bits, not on the absence of
                               an exception. File count 49 -> 50.
          1017 / 0             WI-0129 finding F8 (29.08.2026): the user's
                               test path reaches the vitest/jest/cargo/go
                               runners as one argument again, or as none.
                               +12 in scope, all driving run-tests.sh with an
                               argv-capturing fake tool on PATH; flagged
                               unchanged at 0, each asserts on the recorded
                               argument vector. File count 48 -> 49.
          1005 / 0             the shipped-script executable-bit pin
                               (29.08.2026): +1, a `git ls-files -s` call
                               asserting the GIT INDEX mode rather than the
                               filesystem's, because the index is what a
                               clone reproduces and a local `chmod +x`
                               without a commit would keep a stat-based
                               check green while still shipping wrong. Not
                               flagged: its first assertion pins the scanned
                               line count against the enumeration, so a
                               truncated `git ls-files` cannot read as
                               "everything is executable".
          1004 / 0             `scripts/check-all.sh` and its test module
                               (29.08.2026): one command that runs the seven
                               quality checks and compares each against a
                               versioned baseline instead of against exit 0 --
                               two of the seven are non-zero by design.
                               +9 in scope, all of them driving the real
                               script through a stub seam. Flagged unchanged
                               at 0: every one asserts on a returncode or on
                               named summary output. The file-enumeration pin
                               below moves 47 -> 48 in the same run.
          995 / 0              WI-0129 findings F3/F4 + the gate-p5 decision
                               (29.08.2026): the gate verdict moved from a
                               prose scan to the declared `gate:` frontmatter
                               field. +15 in scope across two modules --
                               test_command_check (32 -> 46) and
                               test_phase_docs_lint (84 -> 105); the rest of
                               those 35 new methods are in-process and
                               correctly out of this scanner's reach. Flagged
                               unchanged at 0: every one of the 15 asserts on
                               a returncode or on named output. Measured with
                               scan_tree() directly, not derived from the
                               suite delta -- deriving it from the delta is
                               how this pin was set wrong once before.
          980 / 0              WI-0129 finding F7 (29.08.2026): the two new
                               `test_run_tests_heredoc_injection.py` methods
                               entered scope because their shared helper is
                               named `_run_fake_tool` (matches
                               `RUN_HELPER_RE` -- an earlier draft named it
                               `_invoke_fake_tool` specifically to dodge this
                               scanner, flagged in code review as trading a
                               one-time pin update for a standing blind spot
                               on tests guarding a security fix; renamed
                               back in). Both carry
                               `self.assertEqual(0, result.returncode, ...)`,
                               unconditionally recognised as positive via
                               `_references_returncode` -- classified
                               `not-flagged`, not `absence-only-needs-
                               exemption`. Flagged unchanged.
          978 / 0              WI-0128 wave 3 tranche 4 (the last 14
                               KNOWN_FINDINGS entries, spread over 7 files
                               and 7 different tools): manual-lint.sh (5
                               tests) needed a COMPANION fixture per check,
                               not a files-scanned pin -- check (a)'s
                               resolution and check (b)'s reverse-link pass
                               both run inside/after the same per-file loop
                               that computes FILES_TOTAL, so disabling
                               either silently (not crashing) leaves "Files
                               scanned:" unchanged, the identical trap
                               tranche 2 already found in phase-docs-lint.sh's
                               commit-anchor loop; each test's own resolved-
                               but-unlinked or invalid-kind companion is what
                               proves the specific check ran. anchor.sh (2
                               tests, OperationalErrorsTest and
                               GitEdgeCaseTest) and install.sh (1 test) took
                               a plain returncode+stderr/stdout liveness
                               pair, matching every sibling test already in
                               their own files. log-cleanup.sh's
                               RedProofTest genuinely WAS blind -- unlike
                               the two test_conformance_run.py transposition
                               tests below, its existing
                               `assertEqual("", r.stderr)`/`assertNotIn(...)`
                               pair has no chained-slice/indexing structure
                               that would already raise on a total crash,
                               so `assertNotEqual(0, r.returncode, ...)` is
                               a real liveness fix here, not a companion.
                               The two test_conformance_run.py transposition
                               tests (CheckHasSummaryLineTranspositionTest,
                               CheckSubcmdTranspositionRealScriptTest) were
                               NOT blind -- their existing chained-
                               `.stdout.split(...)` assertions already fail
                               under a real crash (confirmed: both the
                               pre-change and the post-change file go RED,
                               as ERROR, under the same induced-crash
                               mutant), just built on the one-hop
                               `_is_stdout_like` gap already named in
                               `chained-stdout-slice-not-tracked-as-output`
                               -- each got a classifier-visible companion
                               assertion documented as exactly that, not as
                               a liveness fix. The THIRD conformance_run
                               fix this tranche, UnknownKeyRejectionTest's
                               `test_shipped_example_template_produces_no_
                               unknown_key_error`, WAS a genuine gap
                               (`known-risk-not-yet-fixed`) and got a plain
                               `assertIn("# Conformance Run Report", r.
                               stdout, ...)` liveness pin, confirmed via the
                               same induced-crash mutant (config validated,
                               then crashes before the report -- new file
                               RED, old file GREEN). test_handover_size_
                               hook.py's RoundingBoundaryTest is the OTHER
                               already-documented false-positive shape
                               (`custom-assert-wrapper-liveness-invisible-
                               to-this-scanner`) -- its hook's own `main()`
                               catches every exception and always exits 0
                               (agent-monitor.py:1168-1178), so a
                               `.returncode` assertion would have been
                               classifier-visible but permanently vacuous
                               for THIS hook; used a `self.size_warnings()`
                               non-emptiness `assertTrue` instead.
                               workitems/test_migrate.py's in-process
                               `run_migrate()` call got an inline
                               `assertEqual(2, len(...))` proving the setup
                               half actually migrated both fixture items
                               (must be the literal `len(...)` call at the
                               assertion site, not a variable already
                               holding the count -- `_is_len_nonzero_pair`
                               inspects the two argument AST nodes
                               directly). KNOWN_FINDINGS is now EMPTY.
                               Flagged: -14.
                               Emptying KNOWN_FINDINGS made
                               NoStaleKnownFindingsTest structurally unable
                               to fail -- `stale` filters an empty list, so
                               assertEqual([], []) held regardless of what
                               the scanner returned. Fixed in the same
                               commit by pinning the scan itself as live;
                               red-proven with scan_tree() -> [].
          978 / 14             WI-0128 wave 3 tranche 3 (artifact_gate
                               module, 9 of the 23 remaining KNOWN_FINDINGS
                               entries): each fixed test gets a liveness
                               assertion the classifier can actually see --
                               mostly `assertEqual(r.returncode, N, ...)`,
                               which the classifier recognises unconditionally
                               via its `.returncode`-attribute check
                               regardless of assertion method. Two of the
                               nine (DenyListTest's refusal-before-scanning
                               test, PromotePathConfigDefectTest's index-only
                               test) sit on a path a scan-summary pin cannot
                               reach at all -- the exit code IS the only
                               liveness proof available there. One
                               (PromotePathConfigDefectTest's index-only
                               test) already carried a real positive
                               assertion (`assertIn("#2", r.stdout +
                               r.stderr)`) the classifier could not see,
                               because `_classify_assert_call`'s `assertIn`
                               branch only recognises `args[1]` when it is
                               DIRECTLY `.stdout` or a name bound to it --
                               `r.stdout + r.stderr` is a `BinOp` and does
                               not qualify, even though `_references_the_
                               result` (used everywhere else in the same
                               function) walks the whole call and would have
                               found it. Not fixed here (out of this
                               tranche's write boundary, the classifier
                               itself); documented instead. In-scope
                               unchanged: no method was added or removed,
                               only assertions inside existing ones.
                               Flagged: -9.
          978 / 23             WI-0128 wave 3 tranche 2 (phase_docs_lint
                               module, 15 of the 38 remaining KNOWN_FINDINGS
                               entries): twelve pin "**Files scanned:** N"
                               against the exact fixture the test wrote --
                               the same shape as tranche 1's fourteen. The
                               remaining three (CommitAnchorFamilyTest) sit
                               behind a SEPARATE `for anchor_key in ...`
                               loop the outer file-count is blind to
                               (FILES_TOTAL is fixed before the per-file
                               loop even starts, so disabling that inner
                               loop entirely leaves "Files scanned:"
                               unchanged) -- each of those three instead
                               gets a companion document in the same run
                               carrying a deliberately malformed OTHER
                               anchor field, so a disabled loop is caught by
                               that field going unreported rather than by a
                               file count. In-scope unchanged: no method was
                               added or removed, only assertions inside
                               existing ones. Flagged: -15.
          978 / 38             WI-0128 wave 3 tranche 1 (memory_lint
                               module, 18 of the 56 KNOWN_FINDINGS entries):
                               each fixed test gets a positive assertion
                               specific to its own claim -- 14 pin
                               "**Files scanned:** N" against the exact
                               fixture the test wrote, 2 (the closed-
                               fence/closed-comment controls) add a dead
                               link AFTER the close and assert it is still
                               caught, 1 (a sibling Tier-2-global file
                               with no frontmatter) proves check (i)
                               actually walked the silo directory, and 1
                               (the CR-terminated-fence test) already had
                               a real `assertTrue` this scanner could not
                               see (bound through `link_findings`, not
                               `self.findings` -- the `helper-bound-list-
                               not-recognised-as-findings` category) and
                               gets a second, classifier-visible
                               `assertIn` on the same fact. In-scope
                               unchanged: no method was added or removed,
                               only assertions inside existing methods.
                               Flagged: -18.
          915 / 53             WI-0125, 27.08.2026, first measurement
          916 / 53             + test_doc_volume_check's liveness red proof
          916 / 54             round 2 finding B: the `assertTrue` branch
                               gated behind `_references_the_result`; one
                               method reclassified, no scope change
          921 / 54             WI-0126 tranche 1 (PHASE_FOLDERS,
                               PHASE_SCOPES, PHASE_FOLDER_NAMES sweeps)
          921 / 54             tranche 2 added no in-scope methods -- its 19
                               tests import next_steps directly and never
                               invoke a subprocess (the FILE-count pin below
                               moved instead, 40 -> 41)
          931 / 54             WI-0126 tranche 3a (quality-scan.sh contract
                               and skip-list coverage)
          943 / 54             WI-0126 tranche 3b (quality-scan.sh content
                               lists: PII_PATTERNS, consent terms, config
                               filenames, and the .venv skip-list binding)
          978 / 56             WI-0128 wave 3a review round: +2, the two
                               last-wins direction tests, both of which
                               drive the CLI. The round's third new test
                               (the reasons-text divergence the first
                               attempt had ruled out) is in-process and
                               correctly out of this scanner's scope.
                               Flagged unchanged.
          976 / 56             WI-0128 wave 3a (command-check.py's gate
                               verdict). Flagged unchanged for the ninth
                               consecutive wave.
          973 / 56             WI-0128 wave 2a: three Rule-3 red proofs in
                               test_conformance_run.py drive the real script,
                               so they are in scope. Flagged unchanged -- all
                               three assert on the returncode.
          970 / 56             WI-0128 wave 1c (the ADR prompt's status
                               vocabulary bound to the lint that rejects it)
          969 / 56             open-findings wave 1b (the fourth os.walk, the
                               argued extension-filter asymmetry, and the
                               failure marker with its streak counter across
                               all three failing exits)
          954 / 56             open-findings wave 1a (quality-scan.sh: the
                               apostrophe/0-byte-report fix, severity
                               normalisation, truncation markers). Flagged
                               unchanged again -- every new test carries a
                               liveness assertion.
          949 / 56             WI-0126 tranche 4 (conformance-run.sh's four
                               uncovered columns). The first time this guard
                               caught REAL new blind tests rather than only
                               moving its own counts: three were flagged
                               before commit, one genuinely absence-only and
                               fixed with a returncode assertion, two
                               registered as a new false-positive category

        The flagged count has not moved since round 2: every test added by
        WI-0126 so far carries a recognised liveness assertion.

        ## The boundary these numbers describe (WI-0128 wave 2a)

        970 and 56 are bounded by what this scanner's AST walk actually
        recognises, not by what exists in the corpus. Two measured blind
        spots -- today documented separately, in the module docstring's
        "Measured blind spot" note and in `EXEMPTION_REASONS["chained-
        stdout-slice-not-tracked-as-output"]` above -- share one root
        cause: `_calls_a_subprocess` and `_is_stdout_like` each recognise
        exactly one syntactic shape and nothing else.

          * `_calls_a_subprocess` only matches `ast.Call(func=
            ast.Attribute)` -- `self.<name>(...)` or `subprocess.run(...)`.
            A module-level helper called directly (`_run_main_against
            (files)`, `ast.Call(func=ast.Name(...))`) is invisible to it
            in either direction: a whole test method built on such a
            helper never enters the 970, whichever way its assertions are
            shaped.
          * `_is_stdout_like` only tracks a name bound in ONE hop directly
            off a `<expr>.stdout` attribute access. A name assigned from a
            further chain off that attribute (`result.stdout.split(...)
            [1].split(...)[0]`) is invisible to it -- the method's
            assertions against that chained name are genuine positive
            liveness checks this scanner cannot see as such.

        Neither gap is closed here -- widening either function's
        recognised shapes would move 970 and/or 56, a decision this
        tranche's write boundary does not cover. What the two pins above
        certify is narrower than "56 absence-only tests exist, out of 970
        in scope": it is "this is what this scanner's two syntax-matchers
        can see" -- a whole module built on the first shape, or an
        assertion chained through the second, would never move either
        count."""
        recs = scan_tree()
        flagged = [r for r in recs if r.disposition in NEEDS_EXEMPTION]
        self.assertEqual(1051, len(recs))
        self.assertEqual(0, len(flagged))


class ScannedFilesCoverTheShippedScopeTest(unittest.TestCase):
    def test_scanned_files_cover_the_shipped_scope(self):
        """Pins the file-enumeration side of "cannot be forgotten": the glob
        is scripts/tests/*.py + scripts/tests/workitems/*.py minus
        __init__.py, re-evaluated on every run, so a FILE added later is
        picked up automatically -- this only pins that the glob itself
        still reaches the files known at write time (WI-0125, 27.08.2026).

        Bumped 40 -> 44 across 28.08.2026: WI-0126 tranche 2 added
        test_next_steps_lists.py, tranche 3c added
        test_quality_scan_sast_patterns.py, WI-0128 wave 1c added
        test_adr_status_mapping.py, wave 2b added
        test_agent_frontmatter.py, wave 3a added
        test_command_check.py.

        That last one is a worked example of the boundary described in
        ClassificationCountsTest: it drives `git show` through
        subprocess.run, yet the in-scope count did NOT move, because the
        call sits in a module-level helper (read_git_show) rather than a
        `self.<name>(...)` method. The blind spot predicted this file
        instead of being surprised by it -- which is the whole reason the
        boundary is written down beside the numbers. Note the in-scope count above did NOT
        move (921) -- that module's 19 tests import next_steps.py directly
        and never invoke a subprocess, so none of them is in scope for the
        absence-only rule. Two pins, two different questions: this one asks
        "did the corpus change", that one asks "did the subprocess-shaped
        population change".

        Bumped 45 -> 47, 29.08.2026 (WI-0129 finding F7): added
        test_run_tests_heredoc_injection.py and
        test_heredoc_interpolation_scan.py. In-scope count above (978 ->
        980, see ClassificationCountsTest's own trajectory) moved by +2: the
        injection test's shared helper is named `_run_fake_tool`, matching
        `RUN_HELPER_RE`, so both its test methods ARE subprocess-invoking
        per `_calls_a_subprocess` -- an earlier draft named it
        `_invoke_fake_tool` specifically to dodge that scanner, reverted
        after code review flagged it as trading a one-time pin update for a
        standing blind spot on tests guarding a security fix. Neither
        method is flagged (0 unchanged): each carries
        `self.assertEqual(0, result.returncode, ...)`, unconditionally
        recognised as positive. The scan test calls neither `subprocess.run`
        nor a `self.<name>(...)` at all -- out of scope entirely, no
        contribution to either number.

        Bumped 51 -> 53, 30.08.2026 (CCPR CI prep, three independent
        cycles): added test_run_tests_mktemp_templates.py and
        test_gitattributes_crlf_guard.py. In-scope count above (1033 ->
        1036, see ClassificationCountsTest's own trajectory) moved by +3,
        not +2 -- one of the three new in-scope methods lives in neither new
        file, it is a new method (`ArchiveDirectoryPermissionsTest.test_
        archive_dir_is_0700_regardless_of_permissive_umask`) added to the
        ALREADY-counted test_log_cleanup_behavior.py, so it moves the method
        pin here without moving this file-count pin -- the same "two pins,
        two different questions" split this docstring's tranche-2 paragraph
        above already establishes. Flagged unchanged at 0: see
        ClassificationCountsTest's own trajectory entry for the per-method
        breakdown, including which siblings in the new files fall into the
        pre-existing module-level-helper blind spot (not a new one, and not
        a rename-to-dodge attempt).

        Bumped 53 -> 54, 30.08.2026 (first-CI work item): added
        test_ci_workflow.py, the structural reader/linter for the new
        .github/workflows/ci.yml. In-scope count above (1051, see
        ClassificationCountsTest) did NOT move: every one of its test
        methods reads and regex-parses a YAML file in-process -- none
        calls `subprocess.run` or a `self.<name>(...)` matching
        `RUN_HELPER_RE` (the module never shells out; even its
        `_write_scratch` helper only calls `Path.write_text`) -- so the
        whole file sits entirely outside this scanner's scope, the same
        "out of scope entirely" shape the scan test itself already is,
        named two paragraphs up."""
        files = sorted(TESTS_DIR.glob("*.py")) + sorted((TESTS_DIR / "workitems").glob("*.py"))
        names = sorted(f.relative_to(TESTS_DIR).as_posix() for f in files if f.name != "__init__.py")
        self.assertEqual(54, len(names))
        self.assertIn("test_absence_only_assertions.py", names)
        self.assertIn("test_run_tests_heredoc_injection.py", names)
        self.assertIn("test_heredoc_interpolation_scan.py", names)
        self.assertIn("test_phase_docs_lint.py", names)
        self.assertIn("test_ci_workflow.py", names)
        self.assertIn("workitems/test_migrate.py", names)


class ExemptionMarkersAreWellFormedTest(unittest.TestCase):
    """Every marker actually present in the corpus must name a registered
    category -- catches a typo'd category independently of whether that
    specific site is currently classified as needing one (mirrors
    test_external_tool_exit_status.py's identically-named test)."""

    def test_every_marker_category_is_registered(self):
        files = sorted(TESTS_DIR.glob("*.py")) + sorted((TESTS_DIR / "workitems").glob("*.py"))
        unregistered = []
        for f in files:
            for lineno, line in enumerate(f.read_text(encoding="utf-8").split("\n"), start=1):
                m = MARKER_RE.search(line)
                if m and m.group(1) not in EXEMPTION_REASONS:
                    unregistered.append(f"{f.relative_to(REPO_ROOT)}:{lineno}: {m.group(1)!r}")
        self.assertEqual([], unregistered)

    def test_every_known_findings_category_is_registered(self):
        """Companion check for the OTHER exemption mechanism this module
        adds beyond the shell-scanner template: a `KNOWN_FINDINGS` entry
        naming an unregistered category would otherwise only surface as a
        cryptic failure inside the main test above."""
        unregistered = [
            f"{key[0]}:{key[1]}.{key[2]} -> {category!r}"
            for key, category in KNOWN_FINDINGS.items()
            if category not in EXEMPTION_REASONS
        ]
        self.assertEqual([], unregistered)

    def test_a_typod_marker_category_is_caught_not_silently_accepted(self):
        """WI-0125 round 2, finding C: `test_every_marker_category_is_
        registered` above scans the real corpus, where -- at write time --
        there is exactly ZERO live `# absence-only: exempt <category>`
        marker anywhere in scripts/tests/; the only occurrences of that
        string are the literal placeholder `<category>` inside this
        module's own docstring, which MARKER_RE does not match (no
        `<`/`>` in its character class). `unregistered` is therefore `[]`
        today no matter what, as long as the regex stays syntactically
        valid -- the main test is vacuously green, exactly the
        absence-only shape this module exists to flag, in the module
        itself. Its sibling `test_every_known_findings_category_is_
        registered` is NOT vacuous (it runs against 54 live
        `KNOWN_FINDINGS` entries), so only this one needed the proof: apply
        the identical scan (MARKER_RE + `EXEMPTION_REASONS` membership) to
        a synthetic fixture carrying a typo'd category, and require it be
        reported rather than silently accepted."""
        # Built from two fragments never adjacent on one physical line of
        # THIS module's own source -- writing the assembled marker as one
        # literal here would make this module's own text a second, self-
        # inflicted match for the real-corpus scan above.
        marker_prefix = "# absence-only"
        marker_suffix = ": exempt bogus-category"
        marker = marker_prefix + marker_suffix
        source = (
            "import unittest\n"
            "\n"
            "class T(unittest.TestCase):\n"
            f"    def test_something(self):  {marker}\n"
            "        pass\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_fixture(Path(tmp) / "test_typo_marker_fixture.py", source)
            unregistered = []
            for lineno, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
                m = MARKER_RE.search(line)
                if m and m.group(1) not in EXEMPTION_REASONS:
                    unregistered.append(f"{path.name}:{lineno}: {m.group(1)!r}")
        self.assertEqual([f"{path.name}:4: 'bogus-category'"], unregistered)
