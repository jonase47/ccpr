"""test_quality_scan.py -- WI-0055: scripts/quality-scan.sh must actually
RUN and write its report, not merely parse.

## Why this exists

`bash -n` (scripts/tests/test_shell_script_syntax.py) proves the shipped
script parses. It proves nothing about whether it works -- WI-0027's own
result already recorded that distinction ("quoting fidelity is not
executability"). Before this item, the script parsed fine for two of its
three Python-heredoc blocks and still exited 0 while the third one broke it
completely, writing nothing (see the module docstring in
`scripts/lib/quality_scan_sast_patterns.py` for the exact mechanism). This
module pins the honest shape: run the real script against a scratch fixture
project, and assert on the artefact it is documented to produce -- not on
its own exit code alone, which WI-0055 itself showed can lie.

Every test here drives the SHIPPED `scripts/quality-scan.sh` against a
throwaway project directory (never this repository's own `docs/`), across
more than one of its documented scopes (`all, deps, sast, config, dsgvo`).
"""

import json
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "quality-scan.sh"


class QualityScanTestBase(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="ccpr-quality-scan-project-"))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)

    def env(self):
        # No HOME/PATH sandboxing needed here (unlike test_artifact_gate.py):
        # the script never reads a personal config, only PATH-resolved tools
        # (python3, and optionally npm/pip-audit/semgrep if present) plus the
        # explicit project directory argument.
        import os
        return dict(os.environ)

    def run_scan(self, scope, project=None):
        return subprocess.run(
            ["bash", str(SCRIPT), scope, str(project or self.project)],
            capture_output=True, text=True, env=self.env(),
        )

    def report_path(self, project=None):
        return (project or self.project) / "docs" / ".quality-scan-report.json"

    def plant_sast_finding(self):
        src = self.project / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "app.py").write_text("def run(cmd):\n    eval(cmd)\n", encoding="utf-8")

    def plant_config_finding(self):
        (self.project / "config.json").write_text('{"debug": true}\n', encoding="utf-8")


class QualityScanRunsAndWritesReportTest(QualityScanTestBase):
    """The functional half WI-0055 asks for: does the script actually run
    to completion and produce a plausible report -- exercised across at
    least two of its five documented scopes, as the item requires."""

    def test_sast_scope_finds_a_planted_eval_call(self):
        self.plant_sast_finding()
        r = self.run_scan("sast")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

        report_file = self.report_path()
        self.assertTrue(report_file.is_file(), "no report was written")
        report = json.loads(report_file.read_text(encoding="utf-8"))

        self.assertEqual("sast", report["scope"])
        findings = report["scans"][0]["findings"]
        self.assertEqual(1, report["summary"]["total_findings"])
        self.assertEqual(1, len(findings))
        self.assertEqual("pattern-eval/exec", findings[0]["type"])
        self.assertEqual("src/app.py", findings[0]["file"])

    def test_config_scope_finds_a_planted_debug_flag(self):
        self.plant_config_finding()
        r = self.run_scan("config")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        self.assertEqual("config", report["scope"])
        findings = report["scans"][0]["findings"]
        self.assertEqual(1, len(findings))
        self.assertEqual("config.json", findings[0]["file"])

    def test_all_scope_aggregates_every_scan_including_clean_ones(self):
        self.plant_sast_finding()
        self.plant_config_finding()
        r = self.run_scan("all")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        self.assertEqual("all", report["scope"])
        scan_names = [s["scan"] for s in report["scans"]]
        self.assertEqual(["deps", "sast", "config", "dsgvo"], scan_names)
        # deps and dsgvo have nothing planted for them -- a clean scan is
        # still a real, present entry, not a missing one.
        self.assertEqual([], dict(zip(scan_names, report["scans"]))["deps"]["findings"])
        self.assertEqual(2, report["summary"]["total_findings"])

    def test_report_lands_only_under_the_target_project_not_this_repo(self):
        self.plant_sast_finding()
        r = self.run_scan("sast")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

        repo_status = subprocess.run(
            ["git", "status", "--porcelain", "docs/"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        self.assertNotIn(
            ".quality-scan-report.json", repo_status.stdout,
            "the scratch-project run leaked a report into this repo's own docs/",
        )

    def test_stdout_also_carries_the_report_for_piping(self):
        self.plant_sast_finding()
        r = self.run_scan("sast")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        # The script's own last step is `cat "${REPORT_FILE}"` -- stdout
        # must be the same JSON as the file, not empty (WI-0055's broken
        # state produced empty stdout).
        self.assertEqual(
            json.loads(self.report_path().read_text(encoding="utf-8")),
            json.loads(r.stdout),
        )


class QualityScanExitStatusTest(QualityScanTestBase):
    """What this item made the exit status mean, pinned as behaviour:
    0 only when a report was actually written; a distinguishable non-zero
    otherwise. WI-0055's own complaint was that these two were previously
    indistinguishable (both reported exit 0)."""

    def test_a_successful_scan_exits_zero(self):
        r = self.run_scan("sast")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_an_unknown_scope_exits_non_zero_and_writes_no_report(self):
        r = self.run_scan("not-a-real-scope")
        self.assertNotEqual(0, r.returncode)
        self.assertFalse(self.report_path().exists())

    def test_a_missing_project_directory_exits_non_zero(self):
        missing = self.project / "does-not-exist"
        r = self.run_scan("sast", project=missing)
        self.assertNotEqual(0, r.returncode)

    def test_a_scan_that_completes_without_writing_a_report_is_a_distinct_failure(self):
        """Reproduces the narrower half of WI-0055's report-integrity gap
        directly: a scratch copy whose final report-write step succeeds
        (exit 0) but produces an EMPTY file -- the exact shape the new
        `[ ! -s "${REPORT_FILE}" ]` guard exists to catch, as opposed to an
        ordinary command failure (already covered by `set -e` on its own)."""
        with tempfile.TemporaryDirectory(prefix="ccpr-quality-scan-mutant-") as tmp:
            mutant = Path(tmp) / "quality-scan.sh"
            shutil.copy2(SCRIPT, mutant)
            shutil.copytree(REPO_ROOT / "scripts" / "lib", Path(tmp) / "lib")

            content = mutant.read_text(encoding="utf-8")
            needle = (
                'print(json.dumps(report, indent=2, ensure_ascii=False))\n'
                '" <<< "$(printf \'%s\\n\' "${results[@]}")" > "${REPORT_FILE}"'
                '  # exit-status: exempt set-e-sufficient'
            )
            self.assertIn(needle, content, "fixture assumption: report-write step moved")
            mutated = content.replace(
                needle,
                'pass  # deliberately writes nothing, still exits 0\n'
                '" <<< "$(printf \'%s\\n\' "${results[@]}")" > "${REPORT_FILE}"'
                '  # exit-status: exempt set-e-sufficient',
            )
            mutant.write_text(mutated, encoding="utf-8")

            r = subprocess.run(
                ["bash", str(mutant), "sast", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
            self.assertIn("FAILED", r.stderr)
            self.assertEqual(0, self.report_path().stat().st_size)


class QualityScanQuotingMutationTest(QualityScanTestBase):
    """WI-0055's own required mutation proof: reintroduce the EXACT pre-fix
    construct (a Python heredoc nested inside a `$(...)` command
    substitution, carrying the apostrophe that broke bash's quote tracking)
    in a scratch copy, confirm the syntax gate goes red and the real run
    reproduces the measured pre-fix symptom (syntax error on stderr, no
    report, exit 0) -- then confirm the shipped file is untouched."""

    PRE_FIX_LINE = (
        '    grep_findings=$(python3 "${SCRIPT_DIR}/lib/quality_scan_sast_patterns.py")'
        '  # exit-status: exempt set-e-sufficient\n'
    )

    # Reduced to the two patterns that carry the load-bearing apostrophe
    # (SQL-String) plus one clean one, but otherwise the exact shape WI-0055
    # measured: a heredoc opened with `python3 << 'PYEOF'` INSIDE a `$(...)`
    # command substitution, whose body contains an ODD number of apostrophes.
    PRE_FIX_BLOCK = """    grep_findings=$(python3 << 'PYEOF'  # exit-status: exempt set-e-sufficient
import os, re, json

PATTERNS = {
    "eval/exec": {
        "pattern": r"\\b(eval|exec)\\s*\\(",
        "extensions": [".py", ".js", ".ts"],
        "severity": "high",
        "message": "eval/exec found - potential code injection risk",
    },
    "SQL-String": {
        "pattern": r'(f"|f\\').*?(SELECT|INSERT|UPDATE|DELETE)',
        "extensions": [".py"],
        "severity": "high",
        "message": "SQL in f-string - SQL injection risk",
    },
}

findings = []
print(json.dumps(findings[:50]))
PYEOF
    )
"""

    def make_mutant(self, tmp):
        mutant = Path(tmp) / "quality-scan.sh"
        shutil.copy2(SCRIPT, mutant)
        content = mutant.read_text(encoding="utf-8")
        self.assertIn(self.PRE_FIX_LINE, content, "fixture assumption: fixed line moved")
        content = content.replace(self.PRE_FIX_LINE, self.PRE_FIX_BLOCK)
        mutant.write_text(content, encoding="utf-8")
        return mutant

    def test_the_gate_goes_red_on_the_reintroduced_construct(self):
        with tempfile.TemporaryDirectory(prefix="ccpr-quality-scan-quoting-mutant-") as tmp:
            mutant = self.make_mutant(tmp)
            r = subprocess.run(["bash", "-n", str(mutant)], capture_output=True, text=True)
            self.assertNotEqual(0, r.returncode, "mutation did not reproduce a parse failure")
            self.assertIn("syntax error", r.stderr)

    def test_the_reintroduced_construct_reproduces_the_measured_pre_fix_symptom(self):
        with tempfile.TemporaryDirectory(prefix="ccpr-quality-scan-quoting-mutant-") as tmp:
            mutant = self.make_mutant(tmp)
            shutil.copytree(REPO_ROOT / "scripts" / "lib", Path(tmp) / "lib")
            r = subprocess.run(
                ["bash", str(mutant), "sast", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertEqual("", r.stdout)
            self.assertIn("syntax error", r.stderr)
            self.assertEqual(
                0, r.returncode,
                "measured pre-fix shape: a bash-level parse abort is reported as "
                "exit 0 -- see the trap comment in scripts/quality-scan.sh for why "
                "no trap wording can recover this after the fact",
            )
            self.assertFalse(self.report_path().exists())

    def test_the_shipped_script_is_untouched_by_the_mutation_probe(self):
        before = SCRIPT.read_bytes()
        before_mode = stat.S_IMODE(SCRIPT.stat().st_mode)
        with tempfile.TemporaryDirectory(prefix="ccpr-quality-scan-quoting-mutant-") as tmp:
            self.make_mutant(tmp)
        self.assertEqual(before, SCRIPT.read_bytes())
        self.assertEqual(before_mode, stat.S_IMODE(SCRIPT.stat().st_mode))


if __name__ == "__main__":
    unittest.main()
