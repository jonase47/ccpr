"""test_quality_scan_sast_patterns.py -- WI-0126 tranche 3c: per-entry
coverage for scripts/lib/quality_scan_sast_patterns.py's PATTERNS rules.

Unlike every earlier WI-0126 tranche, this target is a real importable
Python module (see the module's own docstring for why it was pulled out of
a heredoc in the first place: WI-0055). That means the tranche-2 shape
applies directly -- `unittest.mock.patch.dict` on the imported PATTERNS
object, then a call to the REAL `main()` -- rather than the extract-a-
heredoc-verbatim-and-subprocess-it shape tranches 3a/3b needed for
scripts/quality-scan.sh's inline Python.

## Measured scope (do not re-derive; see WI-0126 briefing for the audit)

  - PATTERNS (:29): 5 rules (eval/exec, innerHTML, SQL-String,
    hardcoded-secret, console-log). Four of the five had zero prior coverage
    in the suite (innerHTML, SQL-String, hardcoded-secret, console-log --
    `pattern-SQL-String` appears nowhere before this file). `eval/exec` is
    the exception: `pattern-eval/exec` was already asserted against the REAL
    pipeline in three places (test_quality_scan.py:173, :614, :665, the
    latter two inside SastScanToolBranchTest) -- but only for one extension
    (.py) and only on the rendered type string, never on its severity,
    message, or any of its other two extensions. Corrected 28.08.2026: an
    earlier version of this claim said `eval/exec` and `SQL-String` "appear
    only inside a frozen WI-0055 fixture", found by grepping the raw dict
    key `eval/exec` -- which finds the key but not what the code emits.
    Tests assert on the RENDERED value `"pattern-" + name`, not the key;
    searching the rendered form is what separates a live pipeline assertion
    from a frozen fixture string.
  - Per-rule `extensions` lists: 19 entries across the five rules
    (3/4/1/7/4). The sharpest gap named in the briefing: a wrong or missing
    extension makes a rule silently never fire.
  - Per-rule field set: 4 keys (pattern, extensions, severity, message).
  - The :66 os.walk skip tuple is already bound by tranche 3b
    (SkipDirsMatchesSastModuleTest in test_quality_scan.py) -- not redone
    here.

## Fixture isolation

The five rules overlap in what they claim: console-log and innerHTML share
all four of their extensions, and three rules (eval/exec, SQL-String,
hardcoded-secret) share .py. main()'s own extension gate
(`if ext in rule["extensions"] and re.search(...)`) means a rule is only
ever a candidate for a file whose extension it claims -- so cross-rule
contamination can only happen between rules that share an extension, never
across rules that do not. Every fixture below is still built so its CONTENT
matches only its own rule's regex (not just its own extension), and
FixtureContentIsolationTest below proves that by running all five regexes
against all five fixtures, rather than asserting it by eye (the briefing's
own warning, and the exact way tranche 3b lost time on the IBAN/phone-de
pair).

## Deliverable 3's failure-mode claim -- corrected, not just pinned

The briefing describes a missing PATTERNS key as producing "an unhandled
KeyError at scan time, not a skipped rule". Measured directly (see
MissingKeyDoesNotRaiseTest and MissingKeyPositionDependentTruncationTest
below): that is not what happens. main()'s per-file loop is wrapped in its
own `try/except Exception: pass` (quality_scan_sast_patterns.py:70-77),
which catches KeyError like any other exception -- main() never raises, and
the caller (scripts/quality-scan.sh's scan_sast()) sees a normal, non-empty,
exit-0 JSON array. The real, measured consequence is subtler and arguably
worse than a crash: PATTERNS is a plain dict, so `for name, rule in
PATTERNS.items()` iterates in insertion order (eval/exec, innerHTML,
SQL-String, hardcoded-secret, console-log) on EVERY line of EVERY scanned
file, regardless of that file's own extension -- the exception fires the
first time the broken rule's entry is reached in that iteration, evaluating
`ext in rule["extensions"]` (or `rule["pattern"]`/`rule["severity"]`/
`rule["message"]`, depending on which key is missing) irrespective of
whether the file's extension has anything to do with the broken rule. Since
the per-file try wraps the WHOLE nested loop (all lines, all rules) for
that one file, the exception aborts the REST OF THAT FILE's scan the moment
it is hit -- but findings already appended to the function-level `findings`
list for THAT SAME LINE, from rules iterated before the broken one, survive.
Concretely, measured against a real two-line eval(x)/eval(y) .js fixture:
breaking "eval/exec" (first in dict order) drops BOTH of that file's
findings to zero, even though the content matches eval/exec's own pattern
twice and eval/exec's own fields are otherwise correct; breaking
"console-log" (last in dict order) drops only the SECOND line's finding,
because line 1's eval/exec check already ran (and appended) before the loop
reaches console-log and raises. This is recorded in WI-0126's Result
section as a corrected finding, not silently substituted for the briefing's
framing (G-136: the briefing's stated cause is a hypothesis until run
against the real code path, the printed stdout is the observation).

## Deliverable 4's severity mismatch -- verified via a verbatim extraction,
never a retyped copy

quality-scan.sh's own summary combiner (the final `python3 -c "..."` block,
:590-624 as of this tranche, not a `<<'EOF'` heredoc like TOOL_REPORT_PY but
still bash-double-quoted Python source) explicitly buckets only 'critical',
'high' and 'warning' by name and assigns EVERYTHING else to 'info' by
subtraction. The npm-side SEVERITIES vocabulary (also in quality-scan.sh,
inside the separate TOOL_REPORT_PY heredoc) is `("info", "low", "moderate",
"high", "critical")` -- a rule with severity "low" or "moderate" is
legitimate there but would land in the summary's 'info' bucket, silently.
SeverityBindingTest below extracts the summary combiner's exact source
(never retyped) and runs it as a real subprocess against synthetic findings
to CONFIRM this before pinning it -- not fixed here (that is a behaviour
decision the briefing has no approval for), and today's three rule
severities (high, critical, info) are all in the safe set.

## Deliverable 6 (enumerate)

A full read of this ~90-line module found no other enumerated constant
besides PATTERNS and the already-bound :66 skip tuple. No omission to
report for this module.
"""

import ast
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from quality_scan_sast_patterns import PATTERNS, main  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY_SCAN_SH = REPO_ROOT / "scripts" / "quality-scan.sh"

RULE_NAMES = ("eval/exec", "innerHTML", "SQL-String", "hardcoded-secret", "console-log")
FOUR_KEYS = frozenset({"pattern", "extensions", "severity", "message"})

# Per-rule extension counts named in the briefing (3/4/1/7/4), total 19.
EXPECTED_EXTENSION_COUNTS = {
    "eval/exec": 3,
    "innerHTML": 4,
    "SQL-String": 1,
    "hardcoded-secret": 7,
    "console-log": 4,
}

# One extension each rule claims, one line of content that matches ONLY
# that rule's regex (verified by FixtureContentIsolationTest below), and one
# extension the rule does NOT claim (used for the deliverable-2 negative
# proof). Every foreign extension chosen here is a real extension some OTHER
# rule in this module claims, not an arbitrary unused one, so the negative
# proof exercises the actual per-rule gate rather than a trivial "unknown
# extension" case.
FIXTURES = {
    "eval/exec": (".py", 'eval(x)\n', ".jsx"),
    "innerHTML": (".tsx", 'el.innerHTML = "<b>x</b>";\n', ".py"),
    "SQL-String": (".py", 'q = f"SELECT * FROM t"\n', ".js"),
    "hardcoded-secret": (".env", 'api_key = "abcdefgh12345"\n', ".jsx"),
    "console-log": (".jsx", 'console.log("debug output message")\n', ".py"),
}


def _run_main_against(files):
    """Writes {relative_path_under_src: content} into a scratch project,
    chdir's into it (main() walks "src" relative to cwd, matching how
    scan_sast() invokes it after cd'ing into the target project), runs the
    REAL main(), and returns the parsed findings list. Restores cwd in a
    finally so a failing assertion in the caller cannot leave the process
    chdir'd into a deleted temp directory."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src"
        src.mkdir()
        for rel_path, content in files.items():
            full = src / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content)

        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                main()
            return json.loads(buf.getvalue())
        finally:
            os.chdir(cwd)


def _finding_types(findings):
    return [f["type"] for f in findings]


# ---------------------------------------------------------------------------
# Deliverable 3 (partial): rule count + key-set shape, checked up front since
# several tests below assume PATTERNS has exactly these 5 rules and 4 keys.
# ---------------------------------------------------------------------------

class PatternsRuleCountTest(unittest.TestCase):
    def test_rule_count_is_pinned_at_5(self):
        self.assertEqual(len(PATTERNS), 5)

    def test_rule_names_match_the_measured_set(self):
        self.assertEqual(set(PATTERNS), set(RULE_NAMES))


class PatternsRuleCountRemovalRedProofTest(unittest.TestCase):
    """patch.dict on the real, already-imported PATTERNS object (not a
    rebuilt copy) -- restored on exit even if an assertion raises.

    Carries no count assertion of its own beyond the per-iteration
    len(PATTERNS) == 4 check: an emptied PATTERNS would make `list(PATTERNS)`
    yield nothing and the loop below run zero times, proving nothing. The
    guard against that is the sibling PatternsRuleCountTest above, which
    pins len(PATTERNS) == 5 directly against today's real object."""

    def test_removing_one_rule_breaks_the_count_pin(self):
        for rule_name in list(PATTERNS):
            with self.subTest(rule=rule_name):
                with patch.dict(PATTERNS):
                    del PATTERNS[rule_name]
                    self.assertEqual(len(PATTERNS), 4)
                    self.assertNotEqual(len(PATTERNS), 5)

                # patch.dict restored the deleted key.
                self.assertIn(rule_name, PATTERNS)


class RuleShapeKeysTest(unittest.TestCase):
    """Carries no count assertion of its own: an emptied PATTERNS would make
    the loop below vacuous. The guard against that degenerate input is the
    sibling PatternsRuleCountTest above, which pins len(PATTERNS) == 5 AND
    compares the key set against RULE_NAMES -- both run in the same suite,
    so an emptied PATTERNS fails there even if this loop stayed silent."""

    def test_every_rule_has_exactly_the_four_keys(self):
        for rule_name, rule in PATTERNS.items():
            with self.subTest(rule=rule_name):
                self.assertEqual(set(rule.keys()), FOUR_KEYS)


# ---------------------------------------------------------------------------
# Fixture isolation proof -- run every rule's regex against every fixture's
# content, not by eye.
# ---------------------------------------------------------------------------

class FixtureContentIsolationTest(unittest.TestCase):
    def test_each_fixture_matches_only_its_own_rules_pattern(self):
        for owner, (_ext, content, _foreign_ext) in FIXTURES.items():
            for candidate_name, candidate_rule in PATTERNS.items():
                with self.subTest(fixture=owner, candidate=candidate_name):
                    matched = bool(
                        re.search(candidate_rule["pattern"], content, re.IGNORECASE)
                    )
                    self.assertEqual(matched, candidate_name == owner)


# ---------------------------------------------------------------------------
# Deliverable 1: per-rule positive fixture (5), fired through the real
# main() code path.
# ---------------------------------------------------------------------------

class PerRulePositiveFixtureTest(unittest.TestCase):
    def test_each_rule_fires_on_its_own_fixture(self):
        for rule_name, (ext, content, _foreign_ext) in FIXTURES.items():
            with self.subTest(rule=rule_name):
                findings = _run_main_against({"fixture" + ext: content})
                self.assertEqual(len(findings), 1)
                finding = findings[0]
                rule = PATTERNS[rule_name]
                self.assertEqual(finding["type"], "pattern-%s" % rule_name)
                self.assertEqual(finding["severity"], rule["severity"])
                self.assertEqual(finding["message"], rule["message"])
                self.assertEqual(finding["line"], 1)


# ---------------------------------------------------------------------------
# Deliverable 2: per-extension coverage (19 entries: 3/4/1/7/4), positive +
# the discriminating negative half, plus a structural removal proof.
# ---------------------------------------------------------------------------

class ExtensionCountTest(unittest.TestCase):
    def test_per_rule_extension_counts_match_the_measured_table(self):
        for rule_name, expected in EXPECTED_EXTENSION_COUNTS.items():
            with self.subTest(rule=rule_name):
                self.assertEqual(len(PATTERNS[rule_name]["extensions"]), expected)

    def test_total_extension_count_is_pinned_at_19(self):
        total = sum(len(rule["extensions"]) for rule in PATTERNS.values())
        self.assertEqual(total, 19)


class PerExtensionPositiveFixtureTest(unittest.TestCase):
    """For every one of the 19 (rule, extension) pairs: a file with that
    extension and the rule's own isolated content produces exactly that
    rule's finding. Content is isolated (FixtureContentIsolationTest), so
    even an extension shared with another rule cannot produce a second
    finding here."""

    def test_every_claimed_extension_fires_the_rule(self):
        checked = 0
        for rule_name, rule in PATTERNS.items():
            _own_ext, content, _foreign_ext = FIXTURES[rule_name]
            for ext in rule["extensions"]:
                checked += 1
                with self.subTest(rule=rule_name, extension=ext):
                    findings = _run_main_against({"fixture" + ext: content})
                    self.assertEqual(
                        _finding_types(findings), ["pattern-%s" % rule_name]
                    )
        self.assertEqual(checked, 19)


class PerExtensionRemovalRedProofTest(unittest.TestCase):
    """Removes ONE extension entry at a time from a rule's `extensions`
    list (patch.dict against the real PATTERNS[rule] mapping, restored on
    exit even if an assertion raises) and fires the REAL main() against a
    file using exactly that extension. G-109: this mutates structure (one
    entry gone, the rest of the list intact), not mere presence -- a sweep
    that only checked "extensions is non-empty" would stay green here."""

    def test_removing_one_extension_silences_the_rule_for_that_extension(self):
        checked = 0
        for rule_name, rule in PATTERNS.items():
            _own_ext, content, _foreign_ext = FIXTURES[rule_name]
            for ext in rule["extensions"]:
                checked += 1
                with self.subTest(rule=rule_name, extension=ext):
                    original_extensions = rule["extensions"]
                    mutated_rule = dict(rule)
                    mutated_rule["extensions"] = [
                        e for e in original_extensions if e != ext
                    ]
                    self.assertEqual(
                        len(mutated_rule["extensions"]), len(original_extensions) - 1
                    )

                    with patch.dict(PATTERNS, {rule_name: mutated_rule}):
                        findings = _run_main_against({"fixture" + ext: content})
                        self.assertEqual(findings, [])

                    # patch.dict restored the original rule dict object.
                    self.assertEqual(PATTERNS[rule_name]["extensions"], original_extensions)
        self.assertEqual(checked, 19)


class PerRuleForeignExtensionNegativeTest(unittest.TestCase):
    """The discriminating half: the rule's own content, under an extension
    it does NOT claim (but a real extension used elsewhere in this module),
    produces no finding for that rule -- e.g. SQL-String claims only .py, so
    an f-string SELECT under .js must stay silent for SQL-String."""

    def test_foreign_extension_produces_no_finding_for_that_rule(self):
        for rule_name, (_own_ext, content, foreign_ext) in FIXTURES.items():
            with self.subTest(rule=rule_name, foreign_extension=foreign_ext):
                self.assertNotIn(foreign_ext, PATTERNS[rule_name]["extensions"])
                findings = _run_main_against({"fixture" + foreign_ext: content})
                self.assertNotIn("pattern-%s" % rule_name, _finding_types(findings))
                # Every fixture above was built so no OTHER rule's regex
                # matches it either (FixtureContentIsolationTest) -- so the
                # foreign-extension file is silent altogether, not just
                # silent for its own rule.
                self.assertEqual(findings, [])


# ---------------------------------------------------------------------------
# Deliverable 3 (continued): the missing-key failure mode, measured and
# corrected against the briefing's framing (see module docstring).
# ---------------------------------------------------------------------------

class MissingKeyDoesNotRaiseTest(unittest.TestCase):
    """For each rule and each of its four keys: removing that key (in-memory,
    via patch.dict on PATTERNS[rule_name], restored on exit) and firing
    main() against that rule's own fixture does NOT propagate an exception
    out of main() -- the per-file try/except inside main() (:70-77) catches
    it -- and the rule's own finding for that file is silently absent. If
    main() ever stopped swallowing this exception, this test would itself
    error with the KeyError traceback rather than merely fail an assertion,
    which is the honest way to notice a change in that behaviour."""

    def test_missing_key_is_swallowed_and_the_finding_is_dropped(self):
        for rule_name, (ext, content, _foreign_ext) in FIXTURES.items():
            for key in FOUR_KEYS:
                with self.subTest(rule=rule_name, missing_key=key):
                    original_rule = PATTERNS[rule_name]
                    mutated_rule = {k: v for k, v in original_rule.items() if k != key}

                    with patch.dict(PATTERNS, {rule_name: mutated_rule}):
                        findings = _run_main_against({"fixture" + ext: content})
                        self.assertNotIn(
                            "pattern-%s" % rule_name, _finding_types(findings)
                        )

                    self.assertEqual(set(PATTERNS[rule_name].keys()), FOUR_KEYS)


class MissingKeyPositionDependentTruncationTest(unittest.TestCase):
    """Corrects the briefing's "unhandled KeyError" framing with the actual
    measured mechanism: PATTERNS.items() iterates in insertion order
    (eval/exec, innerHTML, SQL-String, hardcoded-secret, console-log) on
    every line of every file. Breaking a rule near the FRONT of that order
    loses the whole file's findings, including that rule's own genuine
    matches, the moment line 1 is processed. Breaking a rule near the BACK
    loses only what would have been found from that rule onward -- findings
    already appended for earlier rules on an earlier-processed line survive.
    Measured against a real two-line eval(x)/eval(y) .js fixture (eval/exec
    is dict-order first, console-log is dict-order last)."""

    FIXTURE = {"a.js": "eval(x)\neval(y)\n"}

    def test_control_finds_both_lines(self):
        findings = _run_main_against(self.FIXTURE)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["line"], 1)
        self.assertEqual(findings[1]["line"], 2)

    def test_breaking_the_first_rule_in_dict_order_loses_the_whole_file(self):
        original_rule = PATTERNS["eval/exec"]
        mutated_rule = {k: v for k, v in original_rule.items() if k != "extensions"}
        with patch.dict(PATTERNS, {"eval/exec": mutated_rule}):
            findings = _run_main_against(self.FIXTURE)
            self.assertEqual(findings, [])
        self.assertEqual(PATTERNS["eval/exec"]["extensions"], original_rule["extensions"])

    def test_breaking_the_last_rule_in_dict_order_loses_only_the_tail(self):
        original_rule = PATTERNS["console-log"]
        mutated_rule = {k: v for k, v in original_rule.items() if k != "extensions"}
        with patch.dict(PATTERNS, {"console-log": mutated_rule}):
            findings = _run_main_against(self.FIXTURE)
            # Line 1's eval/exec check runs (and appends) BEFORE the same
            # line's console-log check raises and aborts the rest of the
            # file -- so line 1 survives and line 2 is lost.
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["line"], 1)
        self.assertEqual(PATTERNS["console-log"]["extensions"], original_rule["extensions"])


# ---------------------------------------------------------------------------
# Deliverable 4: severity binding, verified via a verbatim extraction of
# quality-scan.sh's own summary combiner before pinning it.
# ---------------------------------------------------------------------------

SUMMARY_START_MARKER = '# Combine results into single JSON\npython3 -c "\n'
SUMMARY_END_MARKER = '\n" <<< "$(printf'

SEVERITIES_RE = re.compile(r"SEVERITIES = \(([^)]*)\)")


def _extract_summary_combiner_source(script_text):
    assert script_text.count(SUMMARY_START_MARKER) == 1, (
        "fixture assumption: exactly one combine-results-into-JSON marker "
        "in quality-scan.sh"
    )
    start = script_text.index(SUMMARY_START_MARKER) + len(SUMMARY_START_MARKER)
    end = script_text.index(SUMMARY_END_MARKER, start)
    return script_text[start:end]


def _run_summary_combiner(source, findings):
    scan_line = json.dumps({"findings": findings})
    proc = subprocess.run(
        [sys.executable, "-c", source],
        input=scan_line + "\n",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["summary"]


class SeverityBindingTest(unittest.TestCase):
    """quality-scan.sh's summary combiner (extracted verbatim below, never
    retyped) explicitly buckets 'critical', 'high' and 'warning' by name and
    assigns everything else to 'info' by subtraction. The npm-side
    SEVERITIES vocabulary (a separate heredoc in the same script) legitimises
    'low' and 'moderate' too -- a rule using either would be silently
    mis-bucketed as 'info'. Verified against the real extracted source via a
    real subprocess before pinning, per the briefing: do not fix, report.

    Its two `for rule_name, rule in PATTERNS.items()` loops (bucketing and
    safe-set membership) carry no count assertion of their own: an emptied
    PATTERNS would make either loop vacuous. The guard is the sibling
    PatternsRuleCountTest in this module, which pins len(PATTERNS) == 5
    directly and runs in the same suite."""

    @classmethod
    def setUpClass(cls):
        script_text = QUALITY_SCAN_SH.read_text()
        cls.summary_source = _extract_summary_combiner_source(script_text)

        severities_match = SEVERITIES_RE.search(script_text)
        assert severities_match is not None, (
            "fixture assumption: SEVERITIES tuple found in quality-scan.sh"
        )
        cls.npm_severities = ast.literal_eval("(" + severities_match.group(1) + ")")

    def test_todays_pattern_severities_are_bucketed_correctly(self):
        for rule_name, rule in PATTERNS.items():
            with self.subTest(rule=rule_name, severity=rule["severity"]):
                summary = _run_summary_combiner(
                    self.summary_source, [{"severity": rule["severity"]}]
                )
                self.assertEqual(summary["total_findings"], 1)
                self.assertEqual(summary[rule["severity"]], 1)
                for other in ("critical", "high", "warning", "info"):
                    if other != rule["severity"]:
                        self.assertEqual(summary[other], 0)

    def test_pattern_severities_are_within_the_safe_set(self):
        safe = {"critical", "high", "warning", "info"}
        for rule_name, rule in PATTERNS.items():
            with self.subTest(rule=rule_name):
                self.assertIn(rule["severity"], safe)

    def test_low_and_moderate_are_legitimate_in_the_npm_severities_vocabulary(self):
        self.assertIn("low", self.npm_severities)
        self.assertIn("moderate", self.npm_severities)

    def test_low_and_moderate_are_silently_miscounted_as_info(self):
        """The real mismatch, verified against the real extracted summary
        combiner: a finding whose severity is 'low' or 'moderate' -- both
        legitimate per SEVERITIES -- is counted into 'info', not dropped and
        not counted under its own name (there is no bucket for either).
        Not fixed here (that is a behaviour decision outside this
        tranche's approval); PATTERNS uses neither severity today."""
        for sev in ("low", "moderate"):
            with self.subTest(severity=sev):
                summary = _run_summary_combiner(self.summary_source, [{"severity": sev}])
                self.assertEqual(summary["info"], 1)
                self.assertEqual(summary["critical"], 0)
                self.assertEqual(summary["high"], 0)
                self.assertEqual(summary["warning"], 0)


# ---------------------------------------------------------------------------
# Deliverable 5: the silent 50-finding cap. Pinned, not fixed -- the missing
# marker is a reported gap, not a change made in this tranche.
# ---------------------------------------------------------------------------

class TruncationCapTest(unittest.TestCase):
    def test_more_than_50_matches_are_capped_at_50(self):
        content = "eval(x)\n" * 60
        findings = _run_main_against({"many.py": content})
        self.assertEqual(len(findings), 50)

    def test_exactly_50_matches_also_produce_50(self):
        content = "eval(x)\n" * 50
        findings = _run_main_against({"exact.py": content})
        self.assertEqual(len(findings), 50)

    def test_the_emitted_shape_carries_no_truncation_marker(self):
        """60-match and exactly-50-match runs must be structurally
        indistinguishable from the emitted JSON alone: both a bare list of
        length 50, and no finding dict carries any extra key that could
        signal "there were more". This is the module docstring's
        documented "up to 50" behaviour, and the gap the briefing asks to
        be recorded, not closed: a consumer parsing this stdout has no way
        to tell "exactly 50 findings" from "at least 51 findings"."""
        over_cap = _run_main_against({"many.py": "eval(x)\n" * 60})
        at_cap = _run_main_against({"exact.py": "eval(x)\n" * 50})

        self.assertIsInstance(over_cap, list)
        self.assertIsInstance(at_cap, list)
        self.assertEqual(len(over_cap), len(at_cap))

        expected_keys = {"type", "severity", "message", "file", "line"}
        for findings in (over_cap, at_cap):
            for finding in findings:
                self.assertEqual(set(finding.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
