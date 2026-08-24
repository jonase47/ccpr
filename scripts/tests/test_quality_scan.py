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

## WI-0102: the "found something" branch

Everything above exercises the branches that need no external tool. None of
it ever reached the branch that runs when npm / pip-audit / semgrep IS
installed and DOES report something -- which is exactly where the scan lied:
each tool prints its full JSON report and still exits non-zero when it finds
vulnerabilities, so the `|| echo '{}'` arm appended a SECOND JSON document,
`json.load` died on "Extra data", and a bare `except: print(0)` reported
zero findings. Measured 24.08.2026 against a throwaway project pinning
minimist 0.0.8: npm's own answer was `{critical: 1, total: 1}` with exit 1,
the shipped chain's answer was 0. pip-audit behaves identically (measured:
6 vulnerabilities, exit 1, shipped chain 0).

The tests below reach that branch with STUB tools on PATH -- a two-line
`/bin/sh` script that prints a canned report and exits with a chosen status.
That keeps the suite free of network access and of any installed toolchain
(this repository has no third-party test dependency), while reproducing the
one behaviour that matters: prints a report AND exits non-zero. The real
tools were measured separately as a probe, outside this suite.
"""

import json
import os
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
        self.stubdir = Path(tempfile.mkdtemp(prefix="ccpr-quality-scan-stubs-"))
        self.addCleanup(shutil.rmtree, self.stubdir, ignore_errors=True)

    # The handful of binaries the script itself resolves through PATH. Used
    # to build a hermetic PATH for the WI-0102 classes: a test that asserts
    # what happens when npm is ABSENT is worthless on a machine where npm
    # happens to be installed, and a test about a stubbed tool should not
    # depend on the real one's version either.
    REQUIRED_BINARIES = (
        "bash", "sh", "python3", "mktemp", "dirname", "date", "mkdir", "cat", "rm",
    )
    SANDBOX_PATH = False

    def sandbox_bin(self):
        binroot = self.stubdir / "_sandbox-bin"
        binroot.mkdir(exist_ok=True)
        for name in self.REQUIRED_BINARIES:
            target = shutil.which(name)
            self.assertIsNotNone(target, "test host has no %s on PATH" % name)
            link = binroot / name
            if not link.exists():
                link.symlink_to(target)
        return binroot

    def env(self):
        # The script reads no personal config, only PATH-resolved tools
        # (python3, and optionally npm/pip-audit/semgrep) plus the explicit
        # project directory argument -- so PATH is the only thing worth
        # sandboxing. The stub directory always goes in FRONT; it is empty
        # unless a test calls install_stub(), and an empty leading entry
        # shadows nothing, so the pre-WI-0102 tests are unaffected.
        env = dict(os.environ)
        if self.SANDBOX_PATH:
            env["PATH"] = os.pathsep.join([str(self.stubdir), str(self.sandbox_bin())])
        else:
            env["PATH"] = str(self.stubdir) + os.pathsep + env["PATH"]
        return env

    def install_stub(self, name, stdout_text, exit_status, stderr_text=""):
        """Put a fake external tool on PATH.

        The one behaviour being reproduced is the defect's cause: the tool
        PRINTS its full report on stdout and STILL exits non-zero. Payload
        lives in a sibling file rather than inline in the stub, so a report
        containing quotes/apostrophes cannot change the stub's own shell
        quoting -- the failure mode WI-0055 documented and WI-0102 measured
        again on a real semgrep message."""
        payload = self.stubdir / (name + ".stdout")
        payload.write_text(stdout_text, encoding="utf-8")
        err_payload = self.stubdir / (name + ".stderr")
        err_payload.write_text(stderr_text, encoding="utf-8")
        stub = self.stubdir / name
        stub.write_text(
            "#!/bin/sh\n"
            'cat "%s"\n'
            'cat "%s" >&2\n'
            "exit %d\n" % (payload, err_payload, exit_status),
            encoding="utf-8",
        )
        stub.chmod(0o755)
        return stub

    def plant_node_lockfile(self):
        (self.project / "package-lock.json").write_text(
            '{"name": "probe", "lockfileVersion": 3}\n', encoding="utf-8"
        )

    def plant_python_manifest(self):
        (self.project / "requirements.txt").write_text("minimist==0\n", encoding="utf-8")

    def deps_findings(self, scope="deps"):
        r = self.run_scan(scope)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        return report["scans"][0]["findings"]

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

    # Retargeted 24.08.2026 (WI-0102): the fixed line moved when scan_sast
    # stopped capturing the pattern pass into a variable and started
    # appending it to the findings-parts file. The MUTATION itself is
    # unchanged -- still the exact WI-0055 construct (a Python heredoc
    # opened inside a `$(...)` command substitution whose body carries an
    # odd number of apostrophes).
    PRE_FIX_LINE = (
        '    run_tool_report pattern-scan "${TMPDIR}/pattern-scan.json" \\\n'
        '        python3 "${SCRIPT_DIR}/lib/quality_scan_sast_patterns.py" >> "${parts}"\n'
    )

    # Reduced to the two patterns that carry the load-bearing apostrophe
    # (SQL-String) plus one clean one, but otherwise the exact shape WI-0055
    # measured: a heredoc opened with `python3 << 'PYEOF'` INSIDE a `$(...)`
    # command substitution, whose body contains an ODD number of apostrophes.
    PRE_FIX_BLOCK = """    local grep_findings
    grep_findings=$(python3 << 'PYEOF'  # exit-status: exempt set-e-sufficient
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
    printf '%s\n' "${grep_findings}" >> "${parts}"
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



# -- WI-0102 fixtures ---------------------------------------------------
#
# Shapes copied from the real tools as measured 24.08.2026 (npm 10.9.2,
# pip-audit 2.10.1, semgrep 1.174.0), trimmed to the fields the script
# reads. The exit statuses are the measured ones, not assumed ones.

NPM_ONE_CRITICAL = json.dumps({
    "auditReportVersion": 2,
    "vulnerabilities": {
        "minimist": {"name": "minimist", "severity": "critical", "range": "<0.2.1"},
    },
    "metadata": {
        "vulnerabilities": {
            "info": 0, "low": 0, "moderate": 0, "high": 0, "critical": 1, "total": 1,
        },
        "dependencies": {"total": 1},
    },
})

NPM_CLEAN = json.dumps({
    "auditReportVersion": 2,
    "vulnerabilities": {},
    "metadata": {
        "vulnerabilities": {
            "info": 0, "low": 0, "moderate": 0, "high": 0, "critical": 0, "total": 0,
        },
    },
})

NPM_REGISTRY_ERROR = json.dumps({
    "error": {"code": "ENOTFOUND", "summary": "request to registry failed"},
})

# pip-audit >= 2.x. One dependency carrying six advisories -- the exact
# shape measured against jinja2==2.10 ("Found 6 known vulnerabilities in 1
# package").
PIP_SIX_VULNS = json.dumps({
    "dependencies": [
        {"name": "certifi", "version": "2026.7.22", "vulns": []},
        {"name": "jinja2", "version": "2.10", "vulns": [
            {"id": "PYSEC-2019-217", "fix_versions": ["2.10.1"]},
            {"id": "PYSEC-2021-66", "fix_versions": ["2.11.3"]},
            {"id": "GHSA-462w-v97r-4m45", "fix_versions": ["2.10.1"]},
            {"id": "GHSA-h5c8-rqwp-cp95", "fix_versions": ["3.1.3"]},
            {"id": "GHSA-h75v-3vvj-5mfj", "fix_versions": ["3.1.3"]},
            {"id": "GHSA-q2x7-8rv6-6q7h", "fix_versions": ["3.1.3"]},
        ]},
    ],
    "fixes": [],
})

PIP_CLEAN = json.dumps({
    "dependencies": [
        {"name": "certifi", "version": "2026.7.22", "vulns": []},
        {"name": "urllib3", "version": "2.7.0", "vulns": []},
    ],
    "fixes": [],
})

# pip-audit 1.x wrote a bare list instead of the {"dependencies": ...}
# object. Kept covered so a downgrade does not silently re-open the count.
PIP_LEGACY_LIST_TWO_VULNS = json.dumps([
    {"name": "jinja2", "version": "2.10", "vulns": [{"id": "PYSEC-2019-217"}, {"id": "PYSEC-2021-66"}]},
    {"name": "certifi", "version": "2026.7.22", "vulns": []},
])

# The apostrophes in this message are load-bearing: they are copied verbatim
# from the first rule real semgrep hits on a subprocess(shell=True) call.
SEMGREP_APOSTROPHE_MESSAGE = (
    "Found 'subprocess' function 'call' with 'shell=True'. This is dangerous "
    "because this call will spawn the command using a shell process."
)

SEMGREP_TWO_RESULTS = json.dumps({
    "results": [
        {
            "check_id": "python.lang.security.audit.subprocess-shell-true",
            "path": "app.py",
            "start": {"line": 3},
            "extra": {"severity": "ERROR", "message": SEMGREP_APOSTROPHE_MESSAGE},
        },
        {
            "check_id": "python.lang.security.audit.eval-detected",
            "path": "app.py",
            "start": {"line": 4},
            "extra": {"severity": "WARNING", "message": "Detected the use of eval()."},
        },
    ],
    "errors": [],
})

SEMGREP_FATAL = json.dumps({"results": [], "errors": [{"message": "invalid configuration"}]})


class DepsScanReportsRealFindingsTest(QualityScanTestBase):
    """WI-0102's binding acceptance, in stub form: a tool that PRINTS a
    report and EXITS NON-ZERO must be reported as a non-zero count.

    Before the fix every test in this class reported 0 findings, because
    `|| echo '{}'` appended a second JSON document to a complete one and
    the consumer's bare `except:` printed 0."""

    SANDBOX_PATH = True

    def test_npm_reporting_one_critical_is_not_reported_as_clean(self):
        self.plant_node_lockfile()
        self.install_stub("npm", NPM_ONE_CRITICAL, exit_status=1)
        findings = self.deps_findings()
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("npm-audit", findings[0]["type"])

    def test_npm_count_is_not_double_counted(self):
        """The second defect: `sum(meta.values())` added the severity
        buckets AND npm's own 'total' key, so one vulnerability came out
        as two."""
        self.plant_node_lockfile()
        self.install_stub("npm", NPM_ONE_CRITICAL, exit_status=1)
        findings = self.deps_findings()
        self.assertIn("1 npm", findings[0]["message"])
        self.assertNotIn("2 npm", findings[0]["message"])

    def test_npm_finding_nothing_stays_an_empty_finding_list(self):
        self.plant_node_lockfile()
        self.install_stub("npm", NPM_CLEAN, exit_status=0)
        self.assertEqual([], self.deps_findings())

    def test_pip_audit_reporting_six_vulns_is_not_reported_as_clean(self):
        self.plant_python_manifest()
        self.install_stub("pip-audit", PIP_SIX_VULNS, exit_status=1)
        findings = self.deps_findings()
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("pip-audit", findings[0]["type"])
        self.assertIn("6 ", findings[0]["message"])

    def test_pip_audit_finding_nothing_does_not_invent_two_vulnerabilities(self):
        """The third defect, measured on the real tool: `len(json.load(...))`
        counted the TOP-LEVEL KEYS of pip-audit 2.x's report object, so a
        clean project was reported as "2 Python vulnerabilities found"."""
        self.plant_python_manifest()
        self.install_stub("pip-audit", PIP_CLEAN, exit_status=0)
        self.assertEqual([], self.deps_findings())

    def test_pip_audit_legacy_list_format_is_still_counted_by_vulnerability(self):
        self.plant_python_manifest()
        self.install_stub("pip-audit", PIP_LEGACY_LIST_TWO_VULNS, exit_status=1)
        findings = self.deps_findings()
        self.assertEqual(1, len(findings), findings)
        self.assertIn("2 ", findings[0]["message"])

    def test_both_ecosystems_report_side_by_side(self):
        """Pre-fix, pip-audit's record OVERWROTE npm's (both wrote the same
        temp file), so a project with a lockfile and a requirements.txt lost
        its npm findings whenever pip-audit had something to say."""
        self.plant_node_lockfile()
        self.plant_python_manifest()
        self.install_stub("npm", NPM_ONE_CRITICAL, exit_status=1)
        self.install_stub("pip-audit", PIP_SIX_VULNS, exit_status=1)
        types = sorted(f["type"] for f in self.deps_findings())
        self.assertEqual(["npm-audit", "pip-audit"], types)


class ToolFailureIsDistinguishableFromZeroFindingsTest(QualityScanTestBase):
    """The class-level half of WI-0102: "could not measure" and "found
    nothing" must not produce the same number. A silent fallback to 0 is
    what hid the original defect, so there is no silent fallback left --
    an unusable report becomes a finding of its own."""

    SANDBOX_PATH = True

    def assert_scan_error(self, findings, tool):
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("scan-error", findings[0]["type"])
        self.assertEqual(tool, findings[0]["tool"])
        self.assertNotEqual([], findings)

    def test_npm_printing_an_error_object_is_a_scan_error_not_a_clean_bill(self):
        self.plant_node_lockfile()
        self.install_stub("npm", NPM_REGISTRY_ERROR, exit_status=1)
        self.assert_scan_error(self.deps_findings(), "npm-audit")

    def test_npm_printing_unparseable_output_is_a_scan_error(self):
        self.plant_node_lockfile()
        self.install_stub("npm", "npm ERR! code ENOENT\n", exit_status=254)
        self.assert_scan_error(self.deps_findings(), "npm-audit")

    def test_npm_printing_nothing_at_all_is_a_scan_error(self):
        self.plant_node_lockfile()
        self.install_stub("npm", "", exit_status=1)
        self.assert_scan_error(self.deps_findings(), "npm-audit")

    def test_npm_exiting_with_an_undocumented_status_is_a_scan_error(self):
        """A valid, empty-looking report plus a status neither 0 ("clean")
        nor 1 ("found something") means the tool did not complete. Reading
        that as "0 vulnerabilities" is the same wrong direction the item
        was opened for."""
        self.plant_node_lockfile()
        self.install_stub("npm", NPM_CLEAN, exit_status=7)
        self.assert_scan_error(self.deps_findings(), "npm-audit")

    def test_pip_audit_printing_unparseable_output_is_a_scan_error(self):
        self.plant_python_manifest()
        self.install_stub("pip-audit", "Traceback (most recent call last):\n", exit_status=2)
        self.assert_scan_error(self.deps_findings(), "pip-audit")

    def test_a_lockfile_without_npm_is_reported_as_unmeasured_not_as_clean(self):
        """The same class one step earlier: a project that HAS something to
        scan and no tool to scan it with used to produce `findings: []`,
        which reads as a clean bill. npm and pip-audit have no fallback --
        without them the deps scan measures nothing at all."""
        self.plant_node_lockfile()
        findings = self.deps_findings()
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("scan-skipped", findings[0]["type"])
        self.assertEqual("npm-audit", findings[0]["tool"])

    def test_a_project_with_nothing_to_scan_reports_nothing(self):
        """The counterpart that keeps the rule above from degenerating into
        "always warn": no lockfile, no manifest, no finding."""
        self.assertEqual([], self.deps_findings())


class SastScanToolBranchTest(QualityScanTestBase):
    """The semgrep site. Its exit code was the benign one of the three
    (measured: `semgrep --config=auto --json -q .` exits 0 WITH findings),
    but the shape is identical and `--error` flips it -- measured too:
    with `--error` the same run prints the same report and exits 1."""

    SANDBOX_PATH = True

    def test_semgrep_findings_are_merged_with_the_grep_fallback(self):
        self.plant_sast_finding()
        self.install_stub("semgrep", SEMGREP_TWO_RESULTS, exit_status=0)
        r = self.run_scan("sast")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        findings = report["scans"][0]["findings"]
        types = sorted(f["type"] for f in findings)
        self.assertEqual(["pattern-eval/exec", "semgrep", "semgrep"], types)

    def test_a_semgrep_message_containing_an_apostrophe_does_not_abort_the_scan(self):
        """Measured 24.08.2026 against real semgrep 1.174.0: the very first
        rule it hits on a `subprocess(..., shell=True)` call carries
        apostrophes in its message, and the merge step interpolated that
        text straight into Python source -- SyntaxError, `set -e`, no
        report at all, exit 1. Same apostrophe class as WI-0055, one
        function further down."""
        self.plant_sast_finding()
        self.install_stub("semgrep", SEMGREP_TWO_RESULTS, exit_status=0)
        r = self.run_scan("sast")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertNotIn("SyntaxError", r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        messages = [f["message"] for f in report["scans"][0]["findings"]]
        self.assertTrue(
            any("shell=True" in m for m in messages),
            "the apostrophe-carrying message did not survive into the report",
        )

    def test_semgrep_exiting_non_zero_with_results_still_reports_them(self):
        """The latent half: `--error` makes semgrep exit 1 while printing
        the same report. Pre-fix the `|| echo '{\"results\":[]}'` arm would
        have appended a second document and dropped every finding."""
        self.plant_sast_finding()
        self.install_stub("semgrep", SEMGREP_TWO_RESULTS, exit_status=1)
        r = self.run_scan("sast")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        self.assertEqual(
            2, sum(1 for f in report["scans"][0]["findings"] if f["type"] == "semgrep")
        )

    def test_a_failed_semgrep_run_is_a_scan_error_not_zero_findings(self):
        self.plant_sast_finding()
        self.install_stub("semgrep", SEMGREP_FATAL, exit_status=2)
        r = self.run_scan("sast")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        errors = [f for f in report["scans"][0]["findings"] if f["type"] == "scan-error"]
        self.assertEqual(1, len(errors), report["scans"][0]["findings"])
        self.assertEqual("semgrep", errors[0]["tool"])

    def test_a_failed_semgrep_run_does_not_suppress_the_grep_fallback(self):
        self.plant_sast_finding()
        self.install_stub("semgrep", SEMGREP_FATAL, exit_status=2)
        r = self.run_scan("sast")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        types = sorted(f["type"] for f in report["scans"][0]["findings"])
        self.assertEqual(["pattern-eval/exec", "scan-error"], types)


class DepsScanRedProofTest(QualityScanTestBase):
    """Mutation proof that the tests above can actually go red, in the
    structural form the item requires: restore the EXACT pre-fix construct
    (`|| echo '{}'` plus the `except: print(0)` consumer) in a scratch copy
    and confirm the reproduced defect -- one real critical reported as
    zero findings. Removing an assertion would prove nothing; this puts the
    original code back."""

    SANDBOX_PATH = True

    PRE_FIX_NPM_BLOCK = """            local audit_raw
            audit_raw=$(npm audit --json 2>/dev/null || echo '{}')
            local vuln_count
            vuln_count=$(echo "${audit_raw}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    meta = d.get('metadata', {}).get('vulnerabilities', {})
    total = sum(meta.values()) if isinstance(meta, dict) else 0
    print(total)
except:
    print(0)
" 2>/dev/null || echo "0")

            python3 -c "
import json
findings = []
if int('${vuln_count}') > 0:
    findings.append({
        'type': 'npm-audit',
        'severity': 'warning',
        'message': '${vuln_count} npm vulnerabilities found',
        'detail': 'Run npm audit --json for details',
    })
print(json.dumps(findings))
" >> "${parts}"
"""

    FIXED_LINE = (
        '            run_tool_report npm-audit "${TMPDIR}/npm-audit.json" '
        'npm audit --json >> "${parts}"\n'
    )

    def build_pre_fix_copy(self, tmp):
        """Swap the one line that measures npm for the exact chain it
        replaced. Everything the defect consisted of comes back verbatim:
        `|| echo '{}'`, the `except: print(0)` consumer, and
        `sum(meta.values())`. Only the last statement differs -- it prints
        the findings ARRAY into the parts file instead of a whole scan
        record into a per-tool file -- because the surrounding plumbing is
        not what was broken, and a mutant has to be runnable to be
        measurable."""
        mutant = Path(tmp) / "quality-scan.sh"
        shutil.copy2(SCRIPT, mutant)
        shutil.copytree(REPO_ROOT / "scripts" / "lib", Path(tmp) / "lib")
        content = mutant.read_text(encoding="utf-8")
        self.assertIn(self.FIXED_LINE, content, "fixture assumption: fixed line moved")
        mutant.write_text(
            content.replace(self.FIXED_LINE, self.PRE_FIX_NPM_BLOCK), encoding="utf-8"
        )
        return mutant

    def test_the_restored_pre_fix_construct_reproduces_the_measured_zero(self):
        self.plant_node_lockfile()
        self.install_stub("npm", NPM_ONE_CRITICAL, exit_status=1)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0102-prefix-") as tmp:
            mutant = self.build_pre_fix_copy(tmp)
            r = subprocess.run(
                ["bash", str(mutant), "deps", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            report = json.loads(self.report_path().read_text(encoding="utf-8"))
            self.assertEqual(
                [], report["scans"][0]["findings"],
                "the pre-fix construct no longer reproduces the defect -- the "
                "mutation missed its target, so the tests above prove nothing",
            )

    def test_the_pre_fix_copy_double_counts_a_single_vulnerability(self):
        """Second half of the same mutation: with the concatenation removed
        but `sum(meta.values())` restored, one vulnerability counts as two.
        Pins that the count fix and the parse fix are independent."""
        self.plant_node_lockfile()
        self.install_stub("npm", NPM_ONE_CRITICAL, exit_status=0)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0102-prefix-") as tmp:
            mutant = self.build_pre_fix_copy(tmp)
            r = subprocess.run(
                ["bash", str(mutant), "deps", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            report = json.loads(self.report_path().read_text(encoding="utf-8"))
            self.assertIn("2 npm", report["scans"][0]["findings"][0]["message"])

    def test_the_shipped_script_is_untouched_by_the_pre_fix_probe(self):
        before = SCRIPT.read_bytes()
        before_mode = stat.S_IMODE(SCRIPT.stat().st_mode)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0102-prefix-") as tmp:
            self.build_pre_fix_copy(tmp)
        self.assertEqual(before, SCRIPT.read_bytes())
        self.assertEqual(before_mode, stat.S_IMODE(SCRIPT.stat().st_mode))



class SetEDoesNotReachIntoCommandSubstitutionTest(QualityScanTestBase):
    """The layer under the tool sites, measured 24.08.2026 while stubbing
    them: bash 3.2 -- the /bin/bash macOS ships and this project pins --
    does NOT honour `set -e` inside a `$(...)` command substitution. A
    failing command inside `results+=("$(scan_sast)")` aborts neither the
    function nor the script; execution continues and the outer script exits
    0. Every scan function is called that way, so "set -e will catch it"
    was not true for any of them, and a producer that died left an empty or
    truncated record behind that read exactly like a clean scan."""

    SANDBOX_PATH = True

    def test_a_pattern_scan_that_cannot_run_is_a_scan_error_not_zero_patterns(self):
        """The pattern pass lives in scripts/lib/. Run the script from a
        copy without that directory -- python3 exits non-zero having
        printed nothing, which pre-fix vanished into the findings list."""
        self.plant_sast_finding()
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0102-nolib-") as tmp:
            copy = Path(tmp) / "quality-scan.sh"
            shutil.copy2(SCRIPT, copy)  # deliberately WITHOUT scripts/lib
            r = subprocess.run(
                ["bash", str(copy), "sast", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            report = json.loads(self.report_path().read_text(encoding="utf-8"))
            findings = report["scans"][0]["findings"]
            self.assertEqual(1, len(findings), findings)
            self.assertEqual("scan-error", findings[0]["type"])
            self.assertEqual("pattern-scan", findings[0]["tool"])
            self.assertIn(
                "quality_scan_sast_patterns.py", findings[0]["detail"],
                "the producer's own last word did not reach the report",
            )
            self.assertIn("exit status 2", findings[0]["detail"])

    def test_a_scan_producing_no_record_at_all_fails_loudly(self):
        """The backstop for the same fact one level up: a scan function that
        prints nothing arrives at the combiner as an empty string, and the
        combiner skips empty lines -- so the whole scan used to disappear
        from the report while the run still exited 0 with a plausible
        summary. Mutation: make scan_config print nothing."""
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0102-emptyscan-") as tmp:
            mutant = Path(tmp) / "quality-scan.sh"
            shutil.copy2(SCRIPT, mutant)
            shutil.copytree(REPO_ROOT / "scripts" / "lib", Path(tmp) / "lib")
            content = mutant.read_text(encoding="utf-8")
            needle = 'print(json.dumps({"scan": "config", "findings": findings}))\n'
            self.assertIn(needle, content, "fixture assumption: config scan moved")
            mutant.write_text(content.replace(needle, "pass\n"), encoding="utf-8")

            r = subprocess.run(
                ["bash", str(mutant), "config", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
            self.assertIn("produced no record", r.stderr)

    def test_the_shipped_script_is_untouched_by_these_probes(self):
        before = SCRIPT.read_bytes()
        before_mode = stat.S_IMODE(SCRIPT.stat().st_mode)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0102-emptyscan-") as tmp:
            shutil.copy2(SCRIPT, Path(tmp) / "quality-scan.sh")
        self.assertEqual(before, SCRIPT.read_bytes())
        self.assertEqual(before_mode, stat.S_IMODE(SCRIPT.stat().st_mode))


if __name__ == "__main__":
    unittest.main()
