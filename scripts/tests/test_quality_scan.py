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

import ast
import json
import os
import re
import shutil
import signal
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
        "bash", "sh", "python3", "mktemp", "dirname", "date", "mkdir", "cat", "rm", "mv",
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
        directly: a scratch copy whose SUMMARY_PY step succeeds (exit 0) but
        prints nothing -- the exact shape the `[ ! -s "${SUMMARY_TMP}" ]`
        guard exists to catch, as opposed to an ordinary command failure
        (already covered by `set -e` on its own).

        Updated 28.08.2026 (WI-0128 wave 1a, defect 1's zusatzauflage): the
        pre-fix assertion here was `self.assertEqual(0, ...stat().st_size)`
        -- it PINNED the exact 0-byte artefact this wave's fix removes. The
        combiner now writes to a scratch file first and only `mv`s it into
        place once python3 has both exited 0 AND produced non-empty output
        (scripts/quality-scan.sh's SUMMARY_TMP block), so a failed
        generation now leaves no report file at all, not a 0-byte one.

        Updated again 28.08.2026 (WI-0128 wave 1b, PO decision): wave 1a's
        own "leaves no report file at all" is superseded -- a failed run now
        overwrites the report with an explicit failure marker instead
        (FailureMarkerTest below covers the marker's shape and streak
        counter in full; this test only re-confirms the leftover-scratch-
        file guarantee still holds now that a marker IS written)."""
        with tempfile.TemporaryDirectory(prefix="ccpr-quality-scan-mutant-") as tmp:
            mutant = Path(tmp) / "quality-scan.sh"
            shutil.copy2(SCRIPT, mutant)
            shutil.copytree(REPO_ROOT / "scripts" / "lib", Path(tmp) / "lib")

            content = mutant.read_text(encoding="utf-8")
            needle = 'print(json.dumps(report, indent=2, ensure_ascii=False))\nSUMMARYEOF'
            self.assertEqual(
                1, content.count(needle), "fixture assumption: report-write step moved"
            )
            mutated = content.replace(
                needle, 'pass  # deliberately writes nothing, still exits 0\nSUMMARYEOF'
            )
            mutant.write_text(mutated, encoding="utf-8")

            r = subprocess.run(
                ["bash", str(mutant), "sast", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
            self.assertIn("FAILED", r.stderr)
            self.assertTrue(
                self.report_path().is_file(),
                "a failed report generation must leave a failure marker behind, "
                "not silence (WI-0128 wave 1b)",
            )
            marker = json.loads(self.report_path().read_text(encoding="utf-8"))
            self.assertEqual("failed", marker.get("status"))
            docs_dir = self.report_path().parent
            leftover = sorted(p.name for p in docs_dir.glob("*"))
            self.assertEqual(
                [self.report_path().name], leftover,
                "a failed report generation must leave exactly the marker behind, "
                "no scratch file (WI-0128 wave 1a round 2, defect A's guarantee "
                "still applies to the marker's own scratch-then-mv write)",
            )

    def test_the_scratch_report_file_is_created_next_to_the_final_report(self):
        """Defect A (WI-0128 wave 1a round 2): the pre-round-2 code built
        SUMMARY_TMP as "${TMPDIR}/quality-scan-report.json.tmp" -- TMPDIR is
        `mktemp -d /tmp/quality-scan-XXXXXX`, a DIFFERENT filesystem from
        REPORT_FILE (`${PROJECT_DIR}/docs/...`) whenever /tmp and the project
        volume are separate mounts (the documented Docker deployment target,
        see CLAUDE.md). `mv` is only atomic within one filesystem; across two
        it degrades to copy+unlink, and a kill mid-copy leaves exactly the
        partial report the atomic-write fix exists to prevent. Fixed by
        creating the scratch file directly under the same directory as
        REPORT_FILE, so the later `mv` is a same-directory rename by
        construction. Asserted structurally (grep the source), not by
        forcing a real cross-filesystem mount in a unit test."""
        content = SCRIPT.read_text(encoding="utf-8")
        needle = 'SUMMARY_TMP="${TMPDIR}/quality-scan-report.json.tmp"'
        self.assertEqual(
            0, content.count(needle),
            "the scratch file must no longer be created under ${TMPDIR} "
            "(a different filesystem from REPORT_FILE in the documented "
            "Docker deployment target)",
        )
        self.assertIn(
            'SUMMARY_TMP=$(mktemp "${PROJECT_DIR}/docs/', content,
            "the scratch file must be created directly under the same "
            "directory as REPORT_FILE, so mv is a same-filesystem rename",
        )


class FailureMarkerTest(QualityScanTestBase):
    """WI-0128 wave 1b deliverable 3, PO decision 28.08.2026: a failed
    report-generation run overwrites docs/.quality-scan-report.json with an
    explicit failure marker instead of leaving a stale report -- or, as
    wave 1a's own unresolved "open question" comment put it, writing
    nothing at all. Same line CLAUDE.md's /p6-audit and /p6-pentest already
    draw ("use the file if it exists") and conformance-run.sh's loud
    "DID NOT RUN" already models.

    Wave 1b covered the two failure paths inside the SUMMARY_TMP combiner
    block ("report generation exited non-zero" / "report generation
    produced no output"). Wave 2 (28.08.2026) closes the two remaining
    non-marker exits PO review found: run_py() itself (:332, a helper
    script exited non-zero -- the scan ran and broke) and the "a scan
    produced no record" empty-entry guard (:640, a scan silently produced
    nothing -- the scan ran and broke too, just without a non-zero exit
    anywhere). The "unknown scope" exit (:629) is a deliberate, ARGUED
    exception -- see test_an_unknown_scope_still_writes_no_marker below
    and the comment at its call site in quality-scan.sh -- because it is a
    usage error raised BEFORE any scan runs; nothing was attempted, so
    overwriting a valid earlier report there would be pure data loss. The
    "missing project directory" early exit is untouched for the same
    reason one level earlier: `cd` fails before `mkdir -p docs` even runs,
    so there is no docs/ directory to write a marker into.

    run_py() and the empty-entry guard are mutually exclusive within one
    run -- corrected 28.08.2026, the wording here previously overgeneralised
    the mechanism to "every scan_X() function's body is bash's SOLE/LAST
    command in its own `$(scan_X)` subshell", which holds for only two of
    the four. scan_deps()/scan_sast() are protected by run_py()'s own
    explicit `exit 1`, which fires regardless of WHERE inside the function
    it is reached (see run_py()'s own comment in quality-scan.sh);
    scan_config()/scan_dsgvo() carry no such explicit exit -- each is a
    single heredoc body with nothing after it, so their crash protection
    depends entirely on being their own function's literal last/sole
    command. Either mechanism means a genuine crash (non-zero exit)
    propagates via errexit immediately and aborts the WHOLE script at its
    own `results+=("$(scan_X)")` line -- the empty-entry loop is never
    reached in the same run. The loop's guard is only reachable via the
    OPPOSITE shape: a scan that exits 0 (nothing "failed" from bash's point
    of view) while printing nothing at all -- the pre-existing WI-0102
    mutation shape reused by build_scan_crash_mutant() below. Two disjoint
    trigger conditions for two disjoint call sites means no same-run
    double-count is possible,
    and write_failure_marker() needs no de-duplication guard.

    The marker carries its OWN consecutive-failure counter, because nothing
    else records a failed run today (measured 28.08.2026: quality-scan.sh
    writes only the report; ~/.claude/logs/ is written by
    hooks/agent-monitor.py from Claude-Code tool calls, not by this
    script). Before overwriting, the existing report -- if any -- is read:
    if it is already a failure marker, the counter increments and the
    FIRST failure's timestamp in the streak is kept; otherwise (a real
    report, no file at all, or something unreadable/corrupt) the streak
    restarts at 1. A successful run implicitly resets the streak by
    replacing the marker with a real report. The streak also survives a
    change in failure REASON within the same ongoing streak (across
    separate runs) -- test_a_run_py_failure_following_a_report_generation_
    failure_continues_the_streak below."""

    NO_OUTPUT_NEEDLE = 'print(json.dumps(report, indent=2, ensure_ascii=False))\nSUMMARYEOF'
    NO_OUTPUT_MUTATION = 'pass  # deliberately writes nothing, still exits 0\nSUMMARYEOF'
    NONZERO_EXIT_MUTATION = 'raise SystemExit(1)  # deliberately exits non-zero\nSUMMARYEOF'

    # :332 -- run_py() itself. TOOL_REPORT_PY's --merge branch is the ONE
    # run_py() call reachable with no external tool and no planted fixture
    # at all (scan_deps() calls it unconditionally at its own end); mutated
    # to raise BEFORE printing anything, so the call fails exactly the way
    # run_py() detects (python3 exits non-zero) with empty stdout, exactly
    # like a real broken helper would.
    MERGE_NEEDLE = (
        'if len(argv) == 4 and argv[1] == "--merge":\n'
        '        print(json.dumps(merge(argv[2], argv[3])))\n'
        '        return 0'
    )
    MERGE_MUTATION = (
        'if len(argv) == 4 and argv[1] == "--merge":\n'
        '        raise SystemExit(1)  # deliberately exits non-zero, before any output'
    )

    # :640 -- the empty-entry guard. Measured 28.08.2026: a scan_X() function
    # here is bash's SOLE/LAST command in its own subshell (the whole body
    # is one `python3 <<'PYEOF'` heredoc), so a python3 CRASH (non-zero
    # exit) propagates via errexit immediately and aborts the WHOLE script
    # at its own `results+=("$(scan_X)")` line -- never reaching this loop
    # at all (the same mechanism as run_py()'s own `exit 1` below). The
    # guard's actually-reachable shape is the opposite: python3 exits 0
    # (nothing "crashed") but prints nothing, exactly the pre-existing
    # WI-0102 mutation this reuses -- see
    # QualityScanFindingIntegrityTest.test_a_scan_producing_no_record_at_
    # all_fails_loudly, which already pins this exact needle/mutation pair.
    CONFIG_SCAN_NEEDLE = 'print(json.dumps({"scan": "config", "findings": findings}))\n'
    CONFIG_SCAN_MUTATION = 'pass\n'

    def build_failing_mutant(self, tmp, mutation):
        mutant = Path(tmp) / "quality-scan.sh"
        shutil.copy2(SCRIPT, mutant)
        shutil.copytree(REPO_ROOT / "scripts" / "lib", Path(tmp) / "lib")
        content = mutant.read_text(encoding="utf-8")
        self.assertEqual(
            1, content.count(self.NO_OUTPUT_NEEDLE),
            "fixture assumption: report-write step moved",
        )
        mutant.write_text(
            content.replace(self.NO_OUTPUT_NEEDLE, mutation), encoding="utf-8"
        )
        return mutant

    def build_run_py_failing_mutant(self, tmp):
        mutant = Path(tmp) / "quality-scan.sh"
        shutil.copy2(SCRIPT, mutant)
        shutil.copytree(REPO_ROOT / "scripts" / "lib", Path(tmp) / "lib")
        content = mutant.read_text(encoding="utf-8")
        self.assertEqual(
            1, content.count(self.MERGE_NEEDLE),
            "fixture assumption: TOOL_REPORT_PY's --merge branch moved",
        )
        mutant.write_text(
            content.replace(self.MERGE_NEEDLE, self.MERGE_MUTATION), encoding="utf-8"
        )
        return mutant

    def run_run_py_failing_scan(self, scope="deps"):
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-runpy-") as tmp:
            mutant = self.build_run_py_failing_mutant(tmp)
            return subprocess.run(
                ["bash", str(mutant), scope, str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )

    def build_scan_crash_mutant(self, tmp):
        mutant = Path(tmp) / "quality-scan.sh"
        shutil.copy2(SCRIPT, mutant)
        shutil.copytree(REPO_ROOT / "scripts" / "lib", Path(tmp) / "lib")
        content = mutant.read_text(encoding="utf-8")
        self.assertEqual(
            1, content.count(self.CONFIG_SCAN_NEEDLE),
            "fixture assumption: scan_config()'s heredoc import line moved",
        )
        mutant.write_text(
            content.replace(self.CONFIG_SCAN_NEEDLE, self.CONFIG_SCAN_MUTATION), encoding="utf-8"
        )
        return mutant

    def run_failing_scan(self, mutation=None, scope="sast"):
        mutation = mutation or self.NO_OUTPUT_MUTATION
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-failmarker-") as tmp:
            mutant = self.build_failing_mutant(tmp, mutation)
            return subprocess.run(
                ["bash", str(mutant), scope, str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )

    def marker(self):
        return json.loads(self.report_path().read_text(encoding="utf-8"))

    def test_a_failed_run_overwrites_a_stale_report_with_a_marker(self):
        self.plant_sast_finding()
        good = self.run_scan("sast")
        self.assertEqual(0, good.returncode, good.stdout + good.stderr)
        stale_report = self.report_path().read_text(encoding="utf-8")

        r = self.run_failing_scan()
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)

        self.assertTrue(self.report_path().is_file())
        self.assertNotEqual(stale_report, self.report_path().read_text(encoding="utf-8"))
        marker = self.marker()
        self.assertEqual("failed", marker.get("status"))
        self.assertEqual(1, marker.get("consecutive_failures"))

    def test_the_marker_is_not_mistakable_for_a_zero_findings_report(self):
        r = self.run_failing_scan()
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
        marker = self.marker()
        self.assertNotIn(
            "summary", marker,
            "a marker with a summary key risks being read as a real report",
        )
        self.assertNotIn(
            "scans", marker,
            "a marker with a scans key risks being read as a real report",
        )
        self.assertEqual("failed", marker.get("status"))

    def test_the_marker_is_recognisable_from_its_content_alone(self):
        """Requirement from the briefing: recognisable as a non-result
        WITHOUT a consumer knowing the run's exit code -- /p6-audit and
        /p6-pentest only check the file's existence (CLAUDE.md), never the
        exit status of whatever produced it."""
        self.run_failing_scan()
        marker = self.marker()
        self.assertEqual("failed", marker.get("status"))

    def test_marker_states_timestamp_reason_and_first_of_streak(self):
        r = self.run_failing_scan()
        marker = self.marker()
        self.assertIn("timestamp", marker)
        self.assertTrue(marker["timestamp"], "timestamp must not be empty")
        self.assertIn("reason", marker)
        self.assertIn("report generation produced no output", marker["reason"])
        self.assertEqual(1, marker["consecutive_failures"])
        self.assertEqual(marker["timestamp"], marker["first_failure_at"])

    def test_the_other_failure_path_also_produces_a_marker(self):
        """The second of the two named failure paths: python3 itself exits
        non-zero (as opposed to exiting 0 but printing nothing)."""
        r = self.run_failing_scan(mutation=self.NONZERO_EXIT_MUTATION)
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
        marker = self.marker()
        self.assertEqual("failed", marker.get("status"))
        self.assertIn("report generation exited non-zero", marker["reason"])

    def test_consecutive_failures_increment_and_reset_on_a_successful_run(self):
        r1 = self.run_failing_scan()
        self.assertNotEqual(0, r1.returncode, r1.stdout + r1.stderr)
        m1 = self.marker()
        self.assertEqual(1, m1["consecutive_failures"])
        first_failure_at = m1["first_failure_at"]

        r2 = self.run_failing_scan()
        self.assertNotEqual(0, r2.returncode, r2.stdout + r2.stderr)
        m2 = self.marker()
        self.assertEqual(2, m2["consecutive_failures"])
        self.assertEqual(first_failure_at, m2["first_failure_at"])

        r3 = self.run_failing_scan()
        self.assertNotEqual(0, r3.returncode, r3.stdout + r3.stderr)
        m3 = self.marker()
        self.assertEqual(3, m3["consecutive_failures"])
        self.assertEqual(first_failure_at, m3["first_failure_at"])

        self.plant_sast_finding()
        good = self.run_scan("sast")
        self.assertEqual(0, good.returncode, good.stdout + good.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        self.assertNotIn(
            "status", report,
            "a successful run must replace the marker with a real report, "
            "implicitly resetting the streak",
        )
        self.assertIn("summary", report)

    def test_an_unreadable_existing_report_does_not_block_the_marker_and_restarts_the_streak(self):
        self.report_path().parent.mkdir(parents=True, exist_ok=True)
        self.report_path().write_text("{not valid json at all", encoding="utf-8")

        r = self.run_failing_scan()
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
        marker = self.marker()
        self.assertEqual("failed", marker.get("status"))
        self.assertEqual(1, marker["consecutive_failures"])
        self.assertEqual(marker["timestamp"], marker["first_failure_at"])

    def test_a_normal_report_is_not_mistaken_for_a_marker_and_restarts_the_streak(self):
        """A pre-existing, perfectly valid, real report (no "status" key at
        all) must not be misread as a failure-marker streak in progress."""
        self.plant_sast_finding()
        good = self.run_scan("sast")
        self.assertEqual(0, good.returncode, good.stdout + good.stderr)

        r = self.run_failing_scan()
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
        marker = self.marker()
        self.assertEqual(1, marker["consecutive_failures"])

    def test_no_scratch_file_is_left_behind_after_a_failed_run(self):
        r = self.run_failing_scan()
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
        docs_dir = self.report_path().parent
        leftover = sorted(p.name for p in docs_dir.glob("*"))
        self.assertEqual([self.report_path().name], leftover)

    def test_a_sigterm_between_mktemp_and_move_leaves_an_orphan_marker_scratch_file(self):
        """RED proof (WI-0128 wave 2 follow-up): write_failure_marker()'s
        own scratch file is `local marker_tmp`, so the top-level EXIT trap
        near TMPDIR's declaration -- which only ever references TMPDIR and
        SUMMARY_TMP -- never sees it. A SIGTERM delivered while python3 is
        still writing the marker (i.e. AFTER mktemp has already created the
        scratch file, BEFORE the `mv`/`rm -f` branch decides its fate) must
        leave that scratch file behind on the current code.

        No existing test in this file exercises this via an external
        signal to mirror (grepped for "SIGTERM"/"kill"/"orphan": the only
        neighbouring "no scratch file" coverage,
        test_no_scratch_file_is_left_behind_after_a_failed_run right above,
        only ever drives the trap's SUCCESS path through an ordinary
        `exit 1` -- the process itself always runs to completion there, so
        it can never catch a mid-write external kill). This test builds the
        window from scratch instead: the run_py() failure mutant
        (build_run_py_failing_mutant, the same one
        test_a_run_py_helper_failure_gets_a_marker_naming_the_helper below
        uses) reaches write_failure_marker() unconditionally at
        scan_deps()'s own end. A `python3` stub placed at the FRONT of PATH
        signals its OWN process group only when invoked with
        quality_scan_failure_marker.py as its script argument -- every
        OTHER python3 call the script makes (the scan heredocs,
        TOOL_REPORT_PY, SUMMARY_PY) passes straight through to the real
        interpreter.

        An earlier version of this test drove the kill from the OUTSIDE:
        an external poll loop watched for the scratch file to appear via
        glob, then sent the group SIGTERM itself -- measured flaky (see
        the commit message for the run count and root-cause trace).
        `MARKER_TMP=$(mktemp ...)` is itself a command substitution -- a
        subshell that creates the file, then reports its path back to the
        parent over a pipe, and ONLY THEN does bash perform the
        `MARKER_TMP=` assignment. An external poll can observe the file on
        disk (mktemp already created it) and fire the group-kill BEFORE
        that assignment lands, taking the still-running `mktemp` subshell
        down with it -- bash's own EXIT trap then runs with `MARKER_TMP`
        still at its declared-empty value, so `rm -f "${MARKER_TMP}"` is a
        no-op and the file is genuinely orphaned. That is a real window,
        but a DIFFERENT one than the "python3 still writing" window this
        test exists to pin, and no outside poll loop can tell the two
        apart -- it races bash's own instruction pointer, not the thing
        under test. This test does not exercise that narrower
        mktemp-assignment window at all; it would need its own
        construction and is left as a known, accepted gap.

        Fix: let the STUB signal itself instead of waiting to be observed
        and signalled from outside. `kill -TERM 0` inside the stub can
        only run once python3 has actually been invoked, which bash's own
        program order guarantees happens strictly AFTER
        `MARKER_TMP=$(mktemp ...)` has already completed and assigned --
        there is no longer a race to win, because the precondition
        (MARKER_TMP correctly set) is structurally satisfied before the
        signal can even be sent. `sleep 5` right after the kill just gives
        the kernel room to deliver the self-sent, already-pending signal
        before this stub would otherwise fall through to `exec`ing the
        real interpreter."""
        real_python3 = shutil.which("python3")
        self.assertIsNotNone(real_python3, "test host has no python3 on PATH")
        slow_python3 = self.stubdir / "python3"
        slow_python3.write_text(
            "#!/bin/sh\n"
            'case "$1" in\n'
            "  */quality_scan_failure_marker.py) kill -TERM 0; sleep 5 ;;\n"
            "esac\n"
            'exec "%s" "$@"\n' % real_python3,
            encoding="utf-8",
        )
        slow_python3.chmod(0o755)

        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-marker-sigterm-") as tmp:
            mutant = self.build_run_py_failing_mutant(tmp)
            docs_dir = self.project / "docs"
            proc = subprocess.Popen(
                ["bash", str(mutant), "deps", str(self.project)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=self.env(), start_new_session=True,
            )
            try:
                proc.wait(timeout=5)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()

            leftover = sorted(p.name for p in docs_dir.glob("*"))
            self.assertEqual(
                [], leftover,
                "a SIGTERM between mktemp and mv/rm must leave no scratch "
                "file behind, got %r" % leftover,
            )

    def test_a_run_py_helper_failure_gets_a_marker_naming_the_helper(self):
        """:332 -- run_py() itself, not the SUMMARY_TMP combiner. scope=deps
        with no manifest planted: the only run_py() call that fires is the
        unconditional `run_py "${TOOL_REPORT_PY}" --merge deps "${parts}"`
        at the end of scan_deps(). run_py()'s `exit 1` is the LAST command
        bash ever runs in that `$(scan_deps)` subshell, so it propagates
        via errexit and aborts the whole script immediately -- this is a
        single, first-failure event, never reaching (or needing to reach)
        the :640 empty-entry guard in the same run, hence
        consecutive_failures == 1 with no de-duplication required."""
        r = self.run_run_py_failing_scan(scope="deps")
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("FAILED -- quality_scan_tool_report.py exited non-zero", r.stderr)
        marker = self.marker()
        self.assertEqual("failed", marker.get("status"))
        self.assertIn("quality_scan_tool_report.py exited non-zero", marker["reason"])
        self.assertEqual(1, marker["consecutive_failures"])

    def test_a_scan_producing_no_record_gets_a_marker(self):
        """:640 -- reached via the OPPOSITE shape from a run_py() crash: the
        scan itself exits 0 (nothing "fails" from bash's point of view) but
        prints nothing at all, reusing the pre-existing WI-0102 mutation for
        the same guard (QualityScanFindingIntegrityTest.test_a_scan_
        producing_no_record_at_all_fails_loudly). The irony worth noting:
        this guard exists precisely because a scan that silently produces
        nothing would otherwise be dropped from the report while the run
        still exits 0 with a plausible summary -- the same confusion the
        marker itself exists to prevent, one level up."""
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-emptyentry-") as tmp:
            mutant = self.build_scan_crash_mutant(tmp)
            r = subprocess.run(
                ["bash", str(mutant), "config", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("FAILED -- a scan produced no record (scope=config)", r.stderr)
        marker = self.marker()
        self.assertEqual("failed", marker.get("status"))
        self.assertIn("a scan produced no record", marker["reason"])
        self.assertEqual(1, marker["consecutive_failures"])

    def test_an_unknown_scope_still_writes_no_marker(self):
        """:629 -- ARGUED exception (see the comment at its call site in
        quality-scan.sh): a usage error raised before any scan runs must
        not destroy a valid earlier report. Complements
        QualityScanExitStatusTest.test_an_unknown_scope_exits_non_zero_and_
        writes_no_report, which covers the no-file-at-all case; this one
        covers the case that actually motivates the exception -- a GOOD
        report already sitting there must survive a typo'd scope
        argument untouched."""
        self.plant_sast_finding()
        good = self.run_scan("sast")
        self.assertEqual(0, good.returncode, good.stdout + good.stderr)
        good_report = self.report_path().read_text(encoding="utf-8")

        r = self.run_scan("not-a-real-scope")
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual(good_report, self.report_path().read_text(encoding="utf-8"))

    def test_a_run_py_failure_following_a_report_generation_failure_continues_the_streak(self):
        """Cross-reason streak proof: the counter tracks consecutive FAILED
        RUNS, not one specific failure reason -- a run_py() failure
        following a report-generation failure must land as failure 2 of
        the same streak, not restart at 1."""
        r1 = self.run_failing_scan()  # report generation produced no output
        self.assertNotEqual(0, r1.returncode, r1.stdout + r1.stderr)
        m1 = self.marker()
        self.assertEqual(1, m1["consecutive_failures"])
        first_failure_at = m1["first_failure_at"]

        r2 = self.run_run_py_failing_scan(scope="deps")
        self.assertNotEqual(0, r2.returncode, r2.stdout + r2.stderr)
        m2 = self.marker()
        self.assertEqual(2, m2["consecutive_failures"])
        self.assertEqual(first_failure_at, m2["first_failure_at"])
        self.assertIn("quality_scan_tool_report.py exited non-zero", m2["reason"])

    def test_the_shipped_script_is_untouched_by_the_failure_marker_mutation_probes(self):
        before = SCRIPT.read_bytes()
        before_mode = stat.S_IMODE(SCRIPT.stat().st_mode)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-failmarker-") as tmp:
            self.build_failing_mutant(tmp, self.NO_OUTPUT_MUTATION)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-failmarker-") as tmp:
            self.build_failing_mutant(tmp, self.NONZERO_EXIT_MUTATION)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-failmarker-") as tmp:
            self.build_run_py_failing_mutant(tmp)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-failmarker-") as tmp:
            self.build_scan_crash_mutant(tmp)
        self.assertEqual(before, SCRIPT.read_bytes())
        self.assertEqual(before_mode, stat.S_IMODE(SCRIPT.stat().st_mode))


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


class ApostropheInProjectPathTest(QualityScanTestBase):
    """WI-0128 wave 1a, defect 1: the final report-combiner step (quoting-scan.sh
    :592-624 as of fc7e7bc) interpolated ${TIMESTAMP}/${SCOPE}/${PROJECT_DIR}
    straight into `python3 -c "..."` source -- the exact class of defect this
    file's own header (:58-65, rule 2) forbids in writing, and the one WI-0055
    already fixed twice in the OTHER two Python blocks here. Measured
    28.08.2026 against a real project directory containing an apostrophe:
    SyntaxError, exit 1, and docs/.quality-scan-report.json left behind at 0
    bytes -- a file CLAUDE.md tells /p6-audit and /p6-pentest to trust "if it
    exists"."""

    def setUp(self):
        super().setUp()
        self.project = self.project / "jonas's project"
        self.project.mkdir()

    def test_an_apostrophe_in_the_project_path_does_not_break_the_scan(self):
        self.plant_sast_finding()
        r = self.run_scan("sast")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertNotIn("SyntaxError", r.stderr)

        report_file = self.report_path()
        self.assertTrue(report_file.is_file(), "no report was written")
        self.assertGreater(report_file.stat().st_size, 0)

        report = json.loads(report_file.read_text(encoding="utf-8"))
        self.assertEqual(str(self.project), report["project"])
        self.assertEqual("sast", report["scope"])
        self.assertEqual(1, len(report["scans"][0]["findings"]))

    def test_an_apostrophe_in_the_scope_argument_does_not_break_the_scan(self):
        """SCOPE reaches the same interpolation site as PROJECT_DIR. The
        `case "${SCOPE}" in ...` gate rejects any value that is not one of
        the five known scopes before the combiner ever runs, so this is a
        defence-in-depth proof, not a live exploit today -- the fix removes
        the interpolation class for all three values uniformly regardless."""
        r = self.run_scan("sa'st")
        self.assertNotEqual(0, r.returncode)
        self.assertNotIn("SyntaxError", r.stderr)
        self.assertIn("Unknown scope", r.stderr)


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


# =============================================================================
# WI-0126 tranche 3a -- three disagreeing SKIP_DIRS tuples unified (Deliverable
# 1), and per-entry coverage for the TOOL_REPORT_PY producer contract
# (COMPLETED/HANDLERS, Deliverable 2) and SEVERITIES (Deliverable 3).
#
# scan_config()'s CORS walk and scan_dsgvo()'s consent walk used to skip
# ("node_modules", ".git", "__pycache__") only -- no "venv" -- while
# scan_dsgvo()'s PII walk (the same heredoc, two loops down) already carried
# "venv". PO decision (28.08.2026): unify on the superset. That edit lands in
# scripts/quality-scan.sh alone in this tranche; the classes below prove it.
# =============================================================================


class SkipDirsVenvBehaviourChangeTest(QualityScanTestBase):
    """Deliverable 1's required proof: before unifying the CORS and consent
    walks' skip lists on the superset including "venv", both walks
    descended into a src/venv/ fixture; after, neither does. This is a
    scratch-copy MUTATION proof of the shipped script itself -- the same
    shape as QualityScanQuotingMutationTest/DepsScanRedProofTest above --
    not a stubbed-tool test: the mutant reverts ONLY the two walks' skip
    tuples to their measured pre-fix shape (`("node_modules", ".git",
    "__pycache__")`, no "venv"), leaving the PII walk (which already
    carried "venv" before this tranche -- see the briefing's own table)
    and the SKIP_DIRS constant definitions themselves untouched.

    The two walks' own semantics make "produces a finding from it" look
    different for each. The CORS walk emits a POSITIVE per-file finding
    when it opens a matching file, so "descends into venv" shows up
    directly as a CORS finding whose "file" is under src/venv/. The
    consent walk has no per-file finding at all -- it sets a boolean that
    SUPPRESSES the "no consent mechanism found" finding the moment any
    file anywhere contains a consent-ish term. Descending into venv there
    means the walk reads venv noise as if it were the project's own
    consent handling, which SUPPRESSES a finding that should have fired --
    the observable effect is the finding's ABSENCE before the fix and its
    PRESENCE after, the inverse of the CORS case but the same root cause."""

    CORS_NEEDLE = (
        '# CORS wildcard check\n'
        'for root, dirs, files in os.walk("src"):\n'
        '    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]\n'
        '    for fname in files:\n'
    )
    CORS_PRE_FIX = CORS_NEEDLE.replace(
        "d not in SKIP_DIRS", 'd not in ("node_modules", ".git", "__pycache__")'
    )

    CONSENT_NEEDLE = (
        '# Check for consent mechanism\n'
        'consent_found = False\n'
        'for root, dirs, files in os.walk("src"):\n'
        '    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]\n'
        '    for fname in files:\n'
    )
    CONSENT_PRE_FIX = CONSENT_NEEDLE.replace(
        "d not in SKIP_DIRS", 'd not in ("node_modules", ".git", "__pycache__")'
    )

    def build_pre_venv_fix_mutant(self, tmp):
        mutant = Path(tmp) / "quality-scan.sh"
        shutil.copy2(SCRIPT, mutant)
        content = mutant.read_text(encoding="utf-8")
        for needle in (self.CORS_NEEDLE, self.CONSENT_NEEDLE):
            self.assertEqual(
                1, content.count(needle),
                "fixture assumption: walk moved -- %r" % needle,
            )
        content = content.replace(self.CORS_NEEDLE, self.CORS_PRE_FIX)
        content = content.replace(self.CONSENT_NEEDLE, self.CONSENT_PRE_FIX)
        mutant.write_text(content, encoding="utf-8")
        return mutant

    def plant_cors_venv_fixture(self):
        venv_file = self.project / "src" / "venv" / "lib" / "sitecustomize.py"
        venv_file.parent.mkdir(parents=True, exist_ok=True)
        venv_file.write_text(
            "ALLOW_ORIGIN = 'Access-Control-Allow-Origin: *'\n", encoding="utf-8"
        )

    def plant_consent_venv_fixture(self):
        venv_file = self.project / "src" / "venv" / "consent_stub.py"
        venv_file.parent.mkdir(parents=True, exist_ok=True)
        venv_file.write_text("# consent management stub\n", encoding="utf-8")
        # Enough real project files outside venv for the "no consent" check
        # to fire at all (it requires more than 2 files total) -- none of
        # them contain a consent-ish term, so the ONLY source of that term
        # anywhere in the tree is the venv fixture above.
        for name in ("a.py", "b.py", "c.py"):
            (self.project / "src" / name).write_text("x = 1\n", encoding="utf-8")

    def test_before_the_fix_the_cors_walk_descends_into_venv_and_finds_it(self):
        self.plant_cors_venv_fixture()
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-skipdirs-") as tmp:
            mutant = self.build_pre_venv_fix_mutant(tmp)
            r = subprocess.run(
                ["bash", str(mutant), "config", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            report = json.loads(self.report_path().read_text(encoding="utf-8"))
            findings = report["scans"][0]["findings"]
            self.assertEqual(1, len(findings), findings)
            self.assertIn("venv", findings[0]["file"])

    def test_after_the_fix_the_cors_walk_does_not_descend_into_venv(self):
        self.plant_cors_venv_fixture()
        r = self.run_scan("config")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        self.assertEqual([], report["scans"][0]["findings"])

    def test_before_the_fix_venv_noise_suppresses_the_missing_consent_finding(self):
        self.plant_consent_venv_fixture()
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-skipdirs-") as tmp:
            mutant = self.build_pre_venv_fix_mutant(tmp)
            r = subprocess.run(
                ["bash", str(mutant), "dsgvo", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            report = json.loads(self.report_path().read_text(encoding="utf-8"))
            types = [f["type"] for f in report["scans"][0]["findings"]]
            self.assertNotIn(
                "dsgvo-consent", types,
                "fixture assumption: pre-fix walk no longer picks up venv noise",
            )

    def test_after_the_fix_the_missing_consent_finding_fires_correctly(self):
        self.plant_consent_venv_fixture()
        r = self.run_scan("dsgvo")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        types = [f["type"] for f in report["scans"][0]["findings"]]
        self.assertIn("dsgvo-consent", types)

    def test_the_shipped_script_is_untouched_by_the_venv_mutation_probe(self):
        before = SCRIPT.read_bytes()
        before_mode = stat.S_IMODE(SCRIPT.stat().st_mode)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-skipdirs-") as tmp:
            self.build_pre_venv_fix_mutant(tmp)
        self.assertEqual(before, SCRIPT.read_bytes())
        self.assertEqual(before_mode, stat.S_IMODE(SCRIPT.stat().st_mode))


# -----------------------------------------------------------------------------
# WI-0126 tranche 3a round 2, item B: nothing previously kept the TWO
# SKIP_DIRS = (...) definitions above (scan_config() and scan_dsgvo(), see
# the module-docstring-style comment beside the first one for why there are
# two heredoc-local copies rather than one shared constant) in sync with
# each other. A future edit that adds e.g. "dist" to one and not the other
# would pass every test above -- both walks would still run, just filter
# different things -- which is the same "two walks in the same file quietly
# disagree" bug class the PO decision closed one level up, one file below.
# -----------------------------------------------------------------------------

SKIP_DIRS_LITERAL_RE = re.compile(r'SKIP_DIRS = \(([^)]*)\)')


def extract_skip_dirs_tuples(content):
    """Returns every `SKIP_DIRS = (...)` literal found in `content`, each
    ast.literal_eval'd into a real tuple (never re-typed by hand), in the
    order they appear in the source."""
    return [ast.literal_eval("(" + m + ")") for m in SKIP_DIRS_LITERAL_RE.findall(content)]


class SkipDirsDefinitionsStayEqualTest(unittest.TestCase):
    """Both SKIP_DIRS literals are string-extracted verbatim from the
    shipped script and compared directly -- not retyped copies compared to
    each other, which would only prove two humans could type the same
    tuple twice. The length pin catches the failure mode the equality
    check alone would miss: both definitions shrinking in lockstep (e.g.
    both losing "venv" again) stays equal to itself the whole time. Pinned
    at 5, not 4, since tranche 3b (WI-0126) added ".venv" to both -- see
    DotVenvSkipBehaviourChangeTest below for the behaviour proof."""

    def test_both_skip_dirs_definitions_are_identical(self):
        content = SCRIPT.read_text(encoding="utf-8")
        tuples = extract_skip_dirs_tuples(content)
        self.assertEqual(
            2, len(tuples),
            "fixture assumption: exactly two SKIP_DIRS definitions expected, "
            "found %d -- did a definition move or get renamed?" % len(tuples),
        )
        first, second = tuples
        self.assertEqual(first, second, "the two SKIP_DIRS definitions have diverged")
        self.assertEqual(5, len(first), first)


class SkipDirsDefinitionsGuardFiresOnDivergenceTest(unittest.TestCase):
    """Proof the guard above is not vacuously true (G-141: a mutation that
    does not grip still reports "passed"). Both mutations below work on a
    SCRATCH STRING held only in memory -- never a copy written to disk,
    let alone the shipped file itself -- so there is nothing here for
    `git stash` or any other abortable step to lose."""

    NEEDLE = 'SKIP_DIRS = ("node_modules", ".git", "__pycache__", "venv", ".venv")'

    def setUp(self):
        self.content = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(
            2, self.content.count(self.NEEDLE),
            "fixture assumption: both definitions still share this literal text",
        )

    def test_a_pair_that_diverges_in_one_definition_is_caught_by_equality(self):
        mutated = self.content.replace(
            self.NEEDLE,
            'SKIP_DIRS = ("node_modules", ".git", "__pycache__", "venv")',
            1,  # only the FIRST occurrence -- the second stays on the superset
        )
        first, second = extract_skip_dirs_tuples(mutated)
        self.assertNotEqual(
            first, second,
            "mutation did not create a divergent pair -- guard proof is meaningless",
        )

    def test_a_pair_that_shrinks_in_lockstep_stays_equal_and_needs_the_length_pin(self):
        mutated = self.content.replace(
            self.NEEDLE,
            'SKIP_DIRS = ("node_modules", ".git", "__pycache__", "venv")',
            2,  # BOTH occurrences -- equality alone would not catch this
        )
        first, second = extract_skip_dirs_tuples(mutated)
        self.assertEqual(
            first, second,
            "fixture assumption: a lockstep shrink is still equal to itself",
        )
        self.assertNotEqual(
            5, len(first),
            "mutation did not actually shrink the tuple -- guard proof is meaningless",
        )


# =============================================================================
# WI-0126 tranche 3b, deliverable 4 continued: a FIFTH skip list surfaced
# while auditing this one -- scripts/lib/quality_scan_sast_patterns.py:66
# carries its own os.walk("src") skip tuple, inline in the loop rather than
# a named constant, and it already carried ".venv" alongside "venv" before
# this tranche touched anything. The PO decision behind tranche 3a's
# SKIP_DIRS unification was taken over three lists; the true superset
# across all four is FIVE entries, not four. ".venv" is added to both
# SKIP_DIRS definitions in scripts/quality-scan.sh -- the only shipped-
# script edit this tranche is authorised to make. quality_scan_sast_
# patterns.py's own tuple is untouched: it was already the superset.
# =============================================================================


class DotVenvSkipBehaviourChangeTest(QualityScanTestBase):
    """The required proof, the same shape as SkipDirsVenvBehaviourChangeTest
    above but for ".venv": before adding it to both SKIP_DIRS definitions,
    a src/.venv/ fixture behaved exactly like the pre-fix src/venv/
    fixture did in tranche 3a -- the CORS walk descended into it, and the
    consent walk read its noise as the project's own consent handling.
    After, ".venv" is skipped the same way "venv" already was.

    Unlike SkipDirsVenvBehaviourChangeTest's per-walk-loop-line mutation
    (needed there because tranche 3a introduced the named SKIP_DIRS
    constant AS PART OF the fix being proven, so the constant itself had
    to stay in place while individual walks were reverted), both SKIP_DIRS
    DEFINITIONS already exist post-3a here -- reverting them directly to
    their pre-".venv" 4-entry shape is itself a structural removal
    (G-109), not a smaller step than what this test proves."""

    POST_FIX = 'SKIP_DIRS = ("node_modules", ".git", "__pycache__", "venv", ".venv")'
    PRE_FIX = 'SKIP_DIRS = ("node_modules", ".git", "__pycache__", "venv")'

    def build_pre_dotvenv_fix_mutant(self, tmp):
        mutant = Path(tmp) / "quality-scan.sh"
        content = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(
            2, content.count(self.POST_FIX),
            "fixture assumption: exactly two SKIP_DIRS definitions carry .venv",
        )
        content = content.replace(self.POST_FIX, self.PRE_FIX)
        mutant.write_text(content, encoding="utf-8")
        return mutant

    def plant_cors_dotvenv_fixture(self):
        f = self.project / "src" / ".venv" / "lib" / "sitecustomize.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("ALLOW_ORIGIN = 'Access-Control-Allow-Origin: *'\n", encoding="utf-8")

    def plant_consent_dotvenv_fixture(self):
        f = self.project / "src" / ".venv" / "consent_stub.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# consent management stub\n", encoding="utf-8")
        for name in ("a.py", "b.py", "c.py"):
            (self.project / "src" / name).write_text("x = 1\n", encoding="utf-8")

    def test_before_the_fix_the_cors_walk_descends_into_dotvenv_and_finds_it(self):
        self.plant_cors_dotvenv_fixture()
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-dotvenv-") as tmp:
            mutant = self.build_pre_dotvenv_fix_mutant(tmp)
            r = subprocess.run(
                ["bash", str(mutant), "config", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            report = json.loads(self.report_path().read_text(encoding="utf-8"))
            findings = report["scans"][0]["findings"]
            self.assertEqual(1, len(findings), findings)
            self.assertIn(".venv", findings[0]["file"])

    def test_after_the_fix_the_cors_walk_does_not_descend_into_dotvenv(self):
        self.plant_cors_dotvenv_fixture()
        r = self.run_scan("config")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        self.assertEqual([], report["scans"][0]["findings"])

    def test_before_the_fix_dotvenv_noise_suppresses_the_missing_consent_finding(self):
        self.plant_consent_dotvenv_fixture()
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-dotvenv-") as tmp:
            mutant = self.build_pre_dotvenv_fix_mutant(tmp)
            r = subprocess.run(
                ["bash", str(mutant), "dsgvo", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            report = json.loads(self.report_path().read_text(encoding="utf-8"))
            types = [f["type"] for f in report["scans"][0]["findings"]]
            self.assertNotIn(
                "dsgvo-consent", types,
                "fixture assumption: pre-fix walk still picks up .venv noise",
            )

    def test_after_the_fix_the_missing_consent_finding_fires_correctly(self):
        self.plant_consent_dotvenv_fixture()
        r = self.run_scan("dsgvo")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        types = [f["type"] for f in report["scans"][0]["findings"]]
        self.assertIn("dsgvo-consent", types)

    def test_the_shipped_script_is_untouched_by_the_dotvenv_mutation_probe(self):
        before = SCRIPT.read_bytes()
        before_mode = stat.S_IMODE(SCRIPT.stat().st_mode)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-dotvenv-") as tmp:
            self.build_pre_dotvenv_fix_mutant(tmp)
        self.assertEqual(before, SCRIPT.read_bytes())
        self.assertEqual(before_mode, stat.S_IMODE(SCRIPT.stat().st_mode))


SAST_SKIP_DIRS_RE = re.compile(
    r'dirs\[:\] = \[d for d in dirs if d not in \(([^)]*)\)\]'
)


def sast_module_skip_dirs():
    """The fourth, previously unnoticed skip list -- extracted verbatim
    from scripts/lib/quality_scan_sast_patterns.py, which this tranche's
    write boundary explicitly does not touch (it was already the
    superset). Returns None if the tuple's shape moved, rather than
    raising, so the caller controls the failure message."""
    content = (REPO_ROOT / "scripts" / "lib" / "quality_scan_sast_patterns.py").read_text(
        encoding="utf-8"
    )
    m = SAST_SKIP_DIRS_RE.search(content)
    return None if m is None else ast.literal_eval("(" + m.group(1) + ")")


class SkipDirsMatchesSastModuleTest(unittest.TestCase):
    """The point of the whole item, in the briefing's own words: the SAST
    module's skip tuple and quality-scan.sh's two SKIP_DIRS definitions
    must now be equal, so the next divergence between the fourth skip
    list and the first three is caught here instead of surfacing as a
    fifth tranche. Compared as SETS -- the SAST tuple's own element order
    is its own concern, not something this binding should pin."""

    def test_sast_module_skip_dirs_equals_both_quality_scan_sh_definitions(self):
        sast_dirs = sast_module_skip_dirs()
        self.assertIsNotNone(sast_dirs, "fixture assumption: SAST module's skip tuple moved")
        sast_dirs = set(sast_dirs)
        script_dirs = extract_skip_dirs_tuples(SCRIPT.read_text(encoding="utf-8"))
        self.assertEqual(2, len(script_dirs))
        for dirs in script_dirs:
            self.assertEqual(sast_dirs, set(dirs))

    def test_the_binding_fires_on_a_scratch_divergence(self):
        """G-141: proof the equality check above is not vacuously true.
        Removes one entry from an in-memory COPY of the SAST tuple -- the
        real file on disk is never touched -- and confirms the sets
        diverge."""
        sast_dirs = sast_module_skip_dirs()
        self.assertIsNotNone(sast_dirs, "fixture assumption: SAST module's skip tuple moved")
        sast_dirs = set(sast_dirs)
        mutated = sast_dirs - {"venv"}
        self.assertNotEqual(
            sast_dirs, mutated,
            "mutation did not shrink the set -- guard proof is meaningless",
        )


class SrcFilesCountWalkVenvBehaviourChangeTest(QualityScanTestBase):
    """WI-0128 wave 1b deliverable 1: the counting walk scan_dsgvo() uses to
    decide whether the "no consent mechanism found" finding is even worth
    reporting (`src_files = sum(...)` / `if src_files > 2:`) was, until this
    fix, the ONLY one of the file's four os.walk("src") call sites without a
    SKIP_DIRS filter -- tranche 3a/3b's CHANGELOG entry recorded this as
    "report, not fixed" (see the comment above scan_config()'s SKIP_DIRS
    definition for the full reasoning). PO decision (WI-0128 wave 1b,
    28.08.2026): filter it too, on the same superset as its three siblings.

    Same scratch-copy MUTATION shape as SkipDirsVenvBehaviourChangeTest
    above: the mutant reverts ONLY this walk's two lines back to their
    measured pre-fix form (an unfiltered `os.walk("src")` sum), leaving the
    other three walks and both SKIP_DIRS definitions untouched.

    Fixture: every file under src/ lives under src/venv/, and none of them
    contain a consent-ish term -- so consent_found stays False either way,
    since the consent-TERM walk (a separate walk, a few lines above this
    one) already skips venv since wave 1a and never even opens them. Before
    this fix, the unfiltered COUNT walk still counts those venv files,
    pushes src_files past the >2 threshold, and fires "no consent mechanism
    found" on venv noise alone -- exactly the confusion this whole wave is
    about, just one level removed (a false POSITIVE finding rather than a
    suppressed one). After the fix, the same fixture has zero non-venv
    files, so the finding does not fire."""

    COUNT_NEEDLE = (
        '    src_files = 0\n'
        '    for r, d, f in os.walk("src"):\n'
        '        d[:] = [x for x in d if x not in SKIP_DIRS]\n'
        '        src_files += len(f)\n'
        '    if src_files > 2:\n'
    )
    COUNT_PRE_FIX = (
        '    src_files = sum(1 for r, d, f in os.walk("src") for _ in f)\n'
        '    if src_files > 2:\n'
    )

    def build_pre_fix_mutant(self, tmp):
        mutant = Path(tmp) / "quality-scan.sh"
        shutil.copy2(SCRIPT, mutant)
        content = mutant.read_text(encoding="utf-8")
        self.assertEqual(
            1, content.count(self.COUNT_NEEDLE),
            "fixture assumption: the counting walk's fixed form moved",
        )
        content = content.replace(self.COUNT_NEEDLE, self.COUNT_PRE_FIX)
        mutant.write_text(content, encoding="utf-8")
        return mutant

    def plant_venv_only_fixture(self):
        venv_dir = self.project / "src" / "venv" / "lib"
        venv_dir.mkdir(parents=True, exist_ok=True)
        for name in ("a.py", "b.py", "c.py"):
            (venv_dir / name).write_text("x = 1\n", encoding="utf-8")

    def test_before_the_fix_venv_only_files_trip_the_missing_consent_finding(self):
        self.plant_venv_only_fixture()
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-countwalk-") as tmp:
            mutant = self.build_pre_fix_mutant(tmp)
            r = subprocess.run(
                ["bash", str(mutant), "dsgvo", str(self.project)],
                capture_output=True, text=True, env=self.env(),
            )
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            report = json.loads(self.report_path().read_text(encoding="utf-8"))
            types = [f["type"] for f in report["scans"][0]["findings"]]
            self.assertIn(
                "dsgvo-consent", types,
                "fixture assumption: pre-fix walk still counts venv-only files",
            )

    def test_after_the_fix_venv_only_files_no_longer_trip_the_finding(self):
        self.plant_venv_only_fixture()
        r = self.run_scan("dsgvo")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        types = [f["type"] for f in report["scans"][0]["findings"]]
        self.assertNotIn("dsgvo-consent", types)

    def test_the_shipped_script_is_untouched_by_the_countwalk_mutation_probe(self):
        before = SCRIPT.read_bytes()
        before_mode = stat.S_IMODE(SCRIPT.stat().st_mode)
        with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-countwalk-") as tmp:
            self.build_pre_fix_mutant(tmp)
        self.assertEqual(before, SCRIPT.read_bytes())
        self.assertEqual(before_mode, stat.S_IMODE(SCRIPT.stat().st_mode))


class ExtensionFilterAsymmetryTest(unittest.TestCase):
    """WI-0128 wave 1a's own CHANGELOG entry recorded the three content
    os.walk("src") walks' differing extension filters as "report, not
    fixed" -- a fact, not a judgement. Wave 1b's task was to make that
    judgement: is each filter's breadth defensible given what the walk
    looks FOR, or is one of the three an unargued accident?

    - CORS wildcard walk (.py/.js/.ts): a CORS header is set from
      server-side/config code -- Python backends, Node/Express middleware,
      TypeScript API route handlers. .jsx/.tsx files are UI components (the
      extension itself signals JSX markup); setting an HTTP response header
      is not something that shape of file does.
    - PII-in-logging walk (.py/.js/.ts/.jsx/.tsx): a hardcoded email, phone
      number or IBAN can appear anywhere a developer types a literal string
      -- including inline in a React/Vue component's JSX markup, or a
      console.log left in one. The wider set matches the wider claim ("any
      code"), not a specific header-setting statement.
    - Consent-mechanism walk (no filter): a cookie banner, privacy-policy
      link or "datenschutz" mention is at least as likely to live in an
      .html template, a .md legal page or a JSON i18n string table under
      src/ as in a .py/.js/.ts file -- narrowing this one to source-code
      extensions would make the walk blind to the exact places a consent
      notice usually lives.

    All three read as a defensible, ARGUED asymmetry, not an accident --
    none of the three lacks a reason once read against what it searches
    for. Pinned here in the same form `ReviewsScopeDeliberatelyAbsentTest`
    (test_anchor.py) uses for `reviews`' absence from `PHASE_SCOPES`: the
    shipped extensions read structurally (never retyped), with the reason
    in the code (see quality-scan.sh's own comments above each walk) and
    here, not left as a silent "report, not fixed" CHANGELOG line."""

    def setUp(self):
        self.content = SCRIPT.read_text(encoding="utf-8")

    def test_cors_walk_filters_py_js_ts_only(self):
        needle = (
            '    for fname in files:\n'
            '        if fname.endswith((".py", ".js", ".ts")):\n'
        )
        self.assertEqual(
            1, self.content.count(needle),
            "CORS walk's extension filter moved or changed shape",
        )

    def test_pii_walk_additionally_covers_jsx_and_tsx(self):
        needle = (
            '    for fname in files:\n'
            '        if not fname.endswith((".py", ".js", ".ts", ".jsx", ".tsx")):\n'
            '            continue\n'
        )
        self.assertEqual(
            1, self.content.count(needle),
            "PII walk's extension filter moved or changed shape",
        )

    def test_consent_walk_has_no_extension_filter_at_all(self):
        needle = (
            'consent_found = False\n'
            'for root, dirs, files in os.walk("src"):\n'
            '    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]\n'
            '    for fname in files:\n'
            '        fpath = os.path.join(root, fname)\n'
        )
        self.assertEqual(
            1, self.content.count(needle),
            "consent walk's shape moved -- re-check for a filter having been added",
        )
        self.assertNotIn(
            "endswith", needle,
            "consent walk must keep reading every file, not just a code-extension subset",
        )


# =============================================================================
# WI-0126 tranche 3b, deliverable 1: PII_PATTERNS (scripts/quality-scan.sh,
# scan_dsgvo() heredoc) -- 4 entries, zero references by name anywhere in
# this module before this tranche. Each entry's regex is checked against a
# fixture built to trip ONLY that one entry: phone-de and iban are
# permissive enough that a careless fixture satisfies both at once (an
# IBAN-shaped digit run containing a literal "0" also reads as a phone
# number under phone-de's very permissive tail), which would collapse the
# per-entry claim -- each fixture line below is hand-checked against all
# four regexes to confirm it matches only its own.
# =============================================================================

PII_PATTERN_NAMES = ("email", "phone-de", "iban", "geburtsdatum")

PII_FIXTURE_LINES = {
    # No digits at all -- clear of phone-de (needs "0"/"+49") and iban
    # (needs two letters directly followed by two digits).
    "email": 'logger.info("user@example.com")\n',
    # No "@", no two letters directly followed by two digits -- clear of
    # email and iban.
    "phone-de": 'logger.info("0151 23456789")\n',
    # No "@", and no literal "0" digit anywhere in the line -- clear of
    # email and phone-de (whose very permissive tail would otherwise
    # swallow most of an IBAN's digit run).
    "iban": 'logger.info("AT12 3456 7891 2345 6789 12")\n',
    # No digits, no "@" -- clear of all three other patterns.
    "geburtsdatum": 'logger.info("geburtsdatum")\n',
}


def dict_entry_line(source, key):
    """Returns every source line defining a `    "key": ...` dict entry,
    verbatim -- located by a plain prefix search, never retyped."""
    prefix = '    "%s":' % key
    return [l for l in source.splitlines(keepends=True) if l.startswith(prefix)]


PII_KEY_LINE_RE = re.compile(r'^    "([\w-]+)": r\'', re.MULTILINE)


def pii_pattern_names_from_source(source=None):
    source = source if source is not None else SCRIPT.read_text(encoding="utf-8")
    start = source.index("PII_PATTERNS = {")
    end = source.index("\n}\n", start)
    return PII_KEY_LINE_RE.findall(source[start:end])


class PiiPatternsShapeTest(unittest.TestCase):
    """Count pin at 4 -- the key list is extracted from the source block
    with its own regex, not compared against a retyped copy of itself."""

    def test_pii_patterns_are_pinned_at_4_entries(self):
        names = pii_pattern_names_from_source()
        self.assertEqual(list(PII_PATTERN_NAMES), names)
        self.assertEqual(4, len(names))


class PiiPatternsPerEntryTest(QualityScanTestBase):
    """Deliverable 1: each of the four PII_PATTERNS regexes finds its own
    shape and names it in the finding's type (dsgvo-pii-<name>). One probe
    file per entry, planted together in a single project and scanned
    once -- each file's content is hand-checked (see PII_FIXTURE_LINES
    above) to trigger only its own regex, so accumulating all four in one
    run does not collapse the per-entry claim.

    This class carries no count assertion of its own: an emptied
    PII_PATTERN_NAMES would make the loop below vacuous, and the guard
    against that is PiiPatternsShapeTest above, which pins the count at 4
    AND compares the tuple against the names extracted from the shipped
    source. Noted so a later edit to that sibling does not silently remove
    this class's degenerate-input guard along with it."""

    def test_each_pii_pattern_finds_its_own_shape(self):
        src = self.project / "src"
        src.mkdir(parents=True, exist_ok=True)
        for name in PII_PATTERN_NAMES:
            probe_name = "probe_%s.py" % name.replace("-", "_")
            (src / probe_name).write_text(PII_FIXTURE_LINES[name], encoding="utf-8")

        r = self.run_scan("dsgvo")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        types = [f["type"] for f in report["scans"][0]["findings"]]
        for name in PII_PATTERN_NAMES:
            with self.subTest(name=name):
                self.assertIn("dsgvo-pii-%s" % name, types, types)


class PiiPatternsRemovalRedProofTest(QualityScanTestBase):
    """Removal proof through the real subprocess (G-107/G-109), not an
    in-memory dict rebuild: PII_PATTERNS is a bash-heredoc-local dict, so
    the mutation is the same scratch-copy shape as
    SkipDirsVenvBehaviourChangeTest -- one dict-entry LINE removed from a
    copy of the shipped script, run against that entry's own fixture. The
    unmutated "before" run is measured first, so a failure here can never
    be blamed on a broken fixture (CompletedHandlersRemovalRedProofTest's
    own rule)."""

    def test_removing_a_pii_pattern_entry_makes_its_own_finding_disappear(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for name in PII_PATTERN_NAMES:
            with self.subTest(name=name):
                lines = dict_entry_line(source, name)
                self.assertEqual(
                    1, len(lines),
                    "fixture assumption: PII_PATTERNS[%r] entry moved" % name,
                )
                needle = lines[0]

                probe = self.project / "src" / "probe.py"
                probe.parent.mkdir(parents=True, exist_ok=True)
                probe.write_text(PII_FIXTURE_LINES[name], encoding="utf-8")

                before = self.run_scan("dsgvo")
                self.assertEqual(0, before.returncode, before.stdout + before.stderr)
                before_report = json.loads(self.report_path().read_text(encoding="utf-8"))
                before_types = [f["type"] for f in before_report["scans"][0]["findings"]]
                self.assertIn(
                    "dsgvo-pii-%s" % name, before_types,
                    "fixture assumption: entry's own probe produces no finding before removal",
                )

                mutated_source = source.replace(needle, "", 1)
                self.assertNotEqual(source, mutated_source)

                with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-pii-") as tmp:
                    mutant = Path(tmp) / "quality-scan.sh"
                    mutant.write_text(mutated_source, encoding="utf-8")
                    after = subprocess.run(
                        ["bash", str(mutant), "dsgvo", str(self.project)],
                        capture_output=True, text=True, env=self.env(),
                    )
                self.assertEqual(0, after.returncode, after.stdout + after.stderr)
                after_report = json.loads(self.report_path().read_text(encoding="utf-8"))
                after_types = [f["type"] for f in after_report["scans"][0]["findings"]]
                self.assertNotIn(
                    "dsgvo-pii-%s" % name, after_types,
                    "removing %r from PII_PATTERNS did not make its finding disappear" % name,
                )


# =============================================================================
# WI-0126 tranche 3b, deliverables 2 and 3: the consent-terms and config-
# filenames lists are INLINE literals, not named constants -- the briefing
# explicitly forbids renaming them into constants (a shipped-script edit
# this tranche has no approval for). Both are tested behaviourally, and
# both share the same extraction/rebuild helpers below.
# =============================================================================


def extract_bracket_literal(line):
    """Extracts a `[...]` list literal substring from a source line,
    verbatim -- never retyped."""
    start = line.index("[")
    end = line.index("]", start) + 1
    return line[start:end]


def rebuild_list_literal(entries):
    """Serialises a list of plain strings back into the same double-quoted
    literal style the shipped lists use -- used only to build a MUTATED
    in-memory literal for a removal proof, never to reconstruct the
    original (which is always extracted verbatim instead)."""
    return "[" + ", ".join('"%s"' % e for e in entries) + "]"


CONSENT_TERMS = ("consent", "cookie-banner", "datenschutz", "privacy-policy")

CONSENT_LOOP_NEEDLE = (
    '            if any(term in content for term in '
    '["consent", "cookie-banner", "datenschutz", "privacy-policy"]):\n'
)


class ConsentTermsShapeTest(unittest.TestCase):
    def test_consent_terms_list_is_pinned_at_4_entries(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(
            1, source.count(CONSENT_LOOP_NEEDLE),
            "fixture assumption: consent terms list moved",
        )
        terms = ast.literal_eval(extract_bracket_literal(CONSENT_LOOP_NEEDLE))
        self.assertEqual(list(CONSENT_TERMS), terms)
        self.assertEqual(4, len(terms))


class ConsentTermsPerEntryTest(QualityScanTestBase):
    """Deliverable 2: each of the four consent terms, alone in a src/
    file, suppresses the "No consent mechanism found" finding. Two
    gotchas from the briefing, both measured here rather than assumed:
    the finding is gated on `src_files > 2` (see the SKIP_DIRS comment
    block above scan_config() for the unfiltered counting walk this
    refers to), so every fixture plants two filler files alongside the
    probe; and the content is lowercased before the match, so one entry
    is probed in mixed case deliberately."""

    def plant_filler_files(self, src):
        for i in range(2):
            (src / ("filler_%d.py" % i)).write_text("x = 1\n", encoding="utf-8")

    def fresh_src(self):
        src = self.project / "src"
        if src.exists():
            shutil.rmtree(src)
        src.mkdir(parents=True)
        return src

    def test_each_consent_term_alone_suppresses_the_missing_consent_finding(self):
        for term in CONSENT_TERMS:
            with self.subTest(term=term):
                src = self.fresh_src()
                self.plant_filler_files(src)
                (src / "consent_probe.py").write_text("# %s\n" % term, encoding="utf-8")

                r = self.run_scan("dsgvo")
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                report = json.loads(self.report_path().read_text(encoding="utf-8"))
                types = [f["type"] for f in report["scans"][0]["findings"]]
                self.assertNotIn("dsgvo-consent", types, types)

    def test_a_mixed_case_consent_term_still_suppresses_the_finding(self):
        src = self.fresh_src()
        self.plant_filler_files(src)
        (src / "consent_probe.py").write_text("# COOKIE-Banner Notice\n", encoding="utf-8")

        r = self.run_scan("dsgvo")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        types = [f["type"] for f in report["scans"][0]["findings"]]
        self.assertNotIn("dsgvo-consent", types, types)

    def test_none_of_the_terms_present_fires_the_finding(self):
        src = self.fresh_src()
        self.plant_filler_files(src)
        (src / "no_consent.py").write_text("x = 1\n", encoding="utf-8")

        r = self.run_scan("dsgvo")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        types = [f["type"] for f in report["scans"][0]["findings"]]
        self.assertIn("dsgvo-consent", types)


class ConsentTermsRemovalRedProofTest(QualityScanTestBase):
    """Removal proof: removes one term from the inline consent-terms list
    in a scratch copy of the shipped script and confirms the "No consent
    mechanism found" finding -- suppressed by that term alone before the
    removal -- fires again after. The inverse framing of
    SkipDirsVenvBehaviourChangeTest's consent proof: there, an ADDED skip
    entry suppresses noise that used to leak in; here, a REMOVED
    recognised term stops suppressing a real signal it used to catch."""

    def test_removing_a_consent_term_makes_the_finding_fire_again(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(
            1, source.count(CONSENT_LOOP_NEEDLE),
            "fixture assumption: consent terms list moved",
        )
        for term in CONSENT_TERMS:
            with self.subTest(term=term):
                src = self.project / "src"
                if src.exists():
                    shutil.rmtree(src)
                src.mkdir(parents=True)
                for i in range(2):
                    (src / ("filler_%d.py" % i)).write_text("x = 1\n", encoding="utf-8")
                (src / "consent_probe.py").write_text("# %s\n" % term, encoding="utf-8")

                before = self.run_scan("dsgvo")
                self.assertEqual(0, before.returncode, before.stdout + before.stderr)
                before_report = json.loads(self.report_path().read_text(encoding="utf-8"))
                before_types = [f["type"] for f in before_report["scans"][0]["findings"]]
                self.assertNotIn(
                    "dsgvo-consent", before_types,
                    "fixture assumption: term suppresses the finding before removal",
                )

                remaining = [t for t in CONSENT_TERMS if t != term]
                mutated_needle = CONSENT_LOOP_NEEDLE.replace(
                    extract_bracket_literal(CONSENT_LOOP_NEEDLE),
                    rebuild_list_literal(remaining),
                )
                self.assertNotEqual(CONSENT_LOOP_NEEDLE, mutated_needle)
                mutated_source = source.replace(CONSENT_LOOP_NEEDLE, mutated_needle, 1)

                with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-consent-") as tmp:
                    mutant = Path(tmp) / "quality-scan.sh"
                    mutant.write_text(mutated_source, encoding="utf-8")
                    after = subprocess.run(
                        ["bash", str(mutant), "dsgvo", str(self.project)],
                        capture_output=True, text=True, env=self.env(),
                    )
                self.assertEqual(0, after.returncode, after.stdout + after.stderr)
                after_report = json.loads(self.report_path().read_text(encoding="utf-8"))
                after_types = [f["type"] for f in after_report["scans"][0]["findings"]]
                self.assertIn(
                    "dsgvo-consent", after_types,
                    "removing %r from the consent terms list did not make the finding fire again" % term,
                )


CONFIG_FILENAMES = (
    "config.json", "config.yaml", "config.yml",
    "settings.py", "app.config.ts", "app.config.js",
)

CONFIG_LOOP_NEEDLE = (
    'for cfg_file in ["config.json", "config.yaml", "config.yml", '
    '"settings.py", "app.config.ts", "app.config.js"]:\n'
)


class ConfigFilenamesShapeTest(unittest.TestCase):
    def test_config_filenames_list_is_pinned_at_6_entries(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(
            1, source.count(CONFIG_LOOP_NEEDLE),
            "fixture assumption: config filenames list moved",
        )
        names = ast.literal_eval(extract_bracket_literal(CONFIG_LOOP_NEEDLE))
        self.assertEqual(list(CONFIG_FILENAMES), names)
        self.assertEqual(6, len(names))


class ConfigFilenamesPerEntryTest(QualityScanTestBase):
    """Deliverable 3: for each of the six config filenames, a file of
    that name with a debug-true setting produces the "Debug mode possibly
    active" finding naming that file. The debug condition (`"debug" in
    content and ("true" in content or "= true" in content)`) is looser
    than it looks -- `debug = true\\n` satisfies it for the right reason
    (both literal substrings actually present), not by accident."""

    def test_each_config_filename_produces_its_own_debug_finding(self):
        for name in CONFIG_FILENAMES:
            (self.project / name).write_text("debug = true\n", encoding="utf-8")

        r = self.run_scan("config")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        debug_files = [
            f["file"] for f in report["scans"][0]["findings"]
            if f["message"].startswith("Debug mode possibly active")
        ]
        self.assertEqual(6, len(debug_files), debug_files)
        for name in CONFIG_FILENAMES:
            with self.subTest(name=name):
                self.assertIn(name, debug_files)


class ConfigFilenamesRemovalRedProofTest(QualityScanTestBase):
    """Removal proof: removes one filename from the inline config-
    filenames list in a scratch copy of the shipped script and confirms
    that filename's debug finding -- present before the removal --
    disappears after. The unmutated "before" run is measured first."""

    def test_removing_a_config_filename_makes_its_own_finding_disappear(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(
            1, source.count(CONFIG_LOOP_NEEDLE),
            "fixture assumption: config filenames list moved",
        )
        for name in CONFIG_FILENAMES:
            with self.subTest(name=name):
                (self.project / name).write_text("debug = true\n", encoding="utf-8")

                before = self.run_scan("config")
                self.assertEqual(0, before.returncode, before.stdout + before.stderr)
                before_report = json.loads(self.report_path().read_text(encoding="utf-8"))
                before_files = [
                    f["file"] for f in before_report["scans"][0]["findings"]
                    if f["message"].startswith("Debug mode possibly active")
                ]
                self.assertIn(
                    name, before_files,
                    "fixture assumption: this filename's own probe produces no finding before removal",
                )

                remaining = [n for n in CONFIG_FILENAMES if n != name]
                mutated_needle = CONFIG_LOOP_NEEDLE.replace(
                    extract_bracket_literal(CONFIG_LOOP_NEEDLE),
                    rebuild_list_literal(remaining),
                )
                self.assertNotEqual(CONFIG_LOOP_NEEDLE, mutated_needle)
                mutated_source = source.replace(CONFIG_LOOP_NEEDLE, mutated_needle, 1)

                with tempfile.TemporaryDirectory(prefix="ccpr-wi0126-config-") as tmp:
                    mutant = Path(tmp) / "quality-scan.sh"
                    mutant.write_text(mutated_source, encoding="utf-8")
                    after = subprocess.run(
                        ["bash", str(mutant), "config", str(self.project)],
                        capture_output=True, text=True, env=self.env(),
                    )
                self.assertEqual(0, after.returncode, after.stdout + after.stderr)
                after_report = json.loads(self.report_path().read_text(encoding="utf-8"))
                after_files = [
                    f["file"] for f in after_report["scans"][0]["findings"]
                    if f["message"].startswith("Debug mode possibly active")
                ]
                self.assertNotIn(
                    name, after_files,
                    "removing %r from the config filenames list did not make its finding disappear" % name,
                )


# -----------------------------------------------------------------------------
# Deliverables 2 and 3: TOOL_REPORT_PY's SEVERITIES / COMPLETED / HANDLERS.
#
# These three constants live inside the TOOL_REPORT_PY heredoc (scripts/
# quality-scan.sh:73-292) -- a generated temp script quality-scan.sh writes
# out at runtime, never an importable module. test_quality_scan.py never
# referenced any of the three by name before this tranche.
#
# Mechanism: extract the heredoc body VERBATIM out of the shipped script
# (never retyped -- the same rule test_next_steps_lists.py's module
# docstring states for next_steps.py's constants) and either (a) run it as a
# real subprocess with the exact argv shape quality-scan.sh's own run_py()
# uses, to exercise read_tool()'s CLI contract end to end including its exit
# code and traceback on an unhandled error, or (b) exec() it into an
# in-memory namespace when only the constants themselves are needed with no
# process boundary. Both read the SAME extracted text; (a) proves the
# behaviour production code sees, (b) proves the data shape. A mutation
# proof for either constant is built by string-replacing the ONE line that
# defines it in the extracted text -- never a rebuilt/retyped copy -- and
# feeding the mutated text back through the same two paths.
# -----------------------------------------------------------------------------

TOOL_REPORT_HEREDOC_START = "cat > \"${TOOL_REPORT_PY}\" <<'TOOLREPORTEOF'\n"
TOOL_REPORT_HEREDOC_END = "\nTOOLREPORTEOF\n"


def tool_report_source():
    """The exact text quality-scan.sh writes to TOOL_REPORT_PY at runtime,
    extracted verbatim between its heredoc markers."""
    content = SCRIPT.read_text(encoding="utf-8")
    start = content.index(TOOL_REPORT_HEREDOC_START) + len(TOOL_REPORT_HEREDOC_START)
    end = content.index(TOOL_REPORT_HEREDOC_END, start)
    return content[start:end]


def load_tool_report_module(source=None):
    """exec()s the extracted source into a fresh namespace and returns it.
    __name__ is deliberately not "__main__" so the module's own `if
    __name__ == "__main__": sys.exit(main(sys.argv))` guard does not fire
    against this process's real argv."""
    ns = {"__name__": "quality_scan_tool_report_under_test"}
    exec(
        compile(source if source is not None else tool_report_source(),
                "<quality_scan_tool_report.py>", "exec"),
        ns,
    )
    return ns


class ToolReportPyTestBase(unittest.TestCase):
    """Writes the extracted TOOL_REPORT_PY source (optionally mutated) to a
    real scratch .py file and runs it exactly the way quality-scan.sh's
    run_py()/run_tool_report() do: `python3 <script> <kind> <report>
    <status>`, reading argv, stdout, stderr and the exit code directly --
    never through a pipe."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-tool-report-py-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.report_dir = self.tmp / "reports"
        self.report_dir.mkdir()
        self._script_seq = 0

    def write_script(self, source=None):
        self._script_seq += 1
        script = self.tmp / ("quality_scan_tool_report_%d.py" % self._script_seq)
        script.write_text(source if source is not None else tool_report_source(), encoding="utf-8")
        return script

    def write_report(self, name, doc):
        path = self.report_dir / name
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def run_tool_report(self, script, *args):
        return subprocess.run(
            ["python3", str(script)] + list(args), capture_output=True, text=True,
        )


# A minimal report doc per producer that findings_X() parses WITHOUT raising
# ReportError -- used to isolate the COMPLETED-status branch (:254) from the
# separate error paths a malformed report would also produce.
VALID_REPORT_DOC = {
    "npm-audit": {"metadata": {"vulnerabilities": {"info": 0}}},
    "pip-audit": {"dependencies": []},
    "semgrep": {"results": []},
    "pattern-scan": [],
}

# Exactly the shipped COMPLETED tuples (scripts/quality-scan.sh:98-103),
# copied here ONLY to drive the sweep below -- every value asserted against
# in this module is checked against the extracted SOURCE (tool_report_source
# / load_tool_report_module), never against this copy alone, so a drift
# between this literal and the shipped one would surface as a test failure
# rather than silently validating itself.
COMPLETED_SHAPE = {
    "npm-audit": ("0", "1"),
    "pip-audit": ("0", "1"),
    "semgrep": ("0", "1"),
    "pattern-scan": ("0",),
}


class ToolReportCompletedShapeMatchesSourceTest(ToolReportPyTestBase):
    """Guards COMPLETED_SHAPE above against silently drifting from the
    shipped COMPLETED dict -- if this ever goes red, every other class in
    this section is testing a copy, not the real thing."""

    def test_completed_shape_equals_the_extracted_source(self):
        ns = load_tool_report_module()
        self.assertEqual(COMPLETED_SHAPE, ns["COMPLETED"])


class ToolReportCompletedStatusTest(ToolReportPyTestBase):
    """Deliverable 2, part 1: for each of the four producers, a status
    INSIDE its COMPLETED tuple parses (real findings, never "did not run to
    completion"), and a status OUTSIDE it does not -- regardless of whether
    the report itself is otherwise well-formed. pattern-scan's tuple is
    ("0",) only, unlike the other three's ("0", "1"): status "1" is
    legitimate for npm-audit/pip-audit/semgrep and an error for
    pattern-scan. A sweep that only ever tries "0" (the briefing's own
    warning) would never exercise that asymmetry, so it gets its own named
    test below in addition to the generic sweep."""

    def test_a_status_inside_completed_parses_without_a_completion_error(self):
        script = self.write_script()
        for kind, statuses in COMPLETED_SHAPE.items():
            for status in statuses:
                with self.subTest(kind=kind, status=status):
                    report = self.write_report(
                        "%s-%s-in.json" % (kind, status), VALID_REPORT_DOC[kind]
                    )
                    r = self.run_tool_report(script, kind, str(report), status)
                    self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                    findings = json.loads(r.stdout)
                    self.assertEqual([], findings, findings)

    OUTSIDE_STATUS = {
        "npm-audit": "2",
        "pip-audit": "3",
        "semgrep": "9",
        "pattern-scan": "1",  # the discriminating case, named again below
    }

    def test_a_status_outside_completed_is_reported_as_did_not_run_to_completion(self):
        script = self.write_script()
        for kind, status in self.OUTSIDE_STATUS.items():
            with self.subTest(kind=kind, status=status):
                report = self.write_report(
                    "%s-%s-out.json" % (kind, status), VALID_REPORT_DOC[kind]
                )
                r = self.run_tool_report(script, kind, str(report), status)
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                findings = json.loads(r.stdout)
                self.assertEqual(1, len(findings), findings)
                self.assertEqual("scan-error", findings[0]["type"])
                self.assertIn("did not run to completion", findings[0]["message"])

    def test_status_1_is_accepted_for_three_producers_and_an_error_for_pattern_scan(self):
        """The discriminating case, named explicitly rather than folded into
        the generic loops above: the literal status string "1" is INSIDE
        npm-audit/pip-audit/semgrep's COMPLETED tuple and OUTSIDE
        pattern-scan's -- same input, opposite verdict, depending only on
        which producer it is."""
        script = self.write_script()
        for kind in ("npm-audit", "pip-audit", "semgrep"):
            with self.subTest(kind=kind, expect="accepted"):
                report = self.write_report("%s-one.json" % kind, VALID_REPORT_DOC[kind])
                r = self.run_tool_report(script, kind, str(report), "1")
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                self.assertEqual([], json.loads(r.stdout))

        report = self.write_report("pattern-scan-one.json", VALID_REPORT_DOC["pattern-scan"])
        r = self.run_tool_report(script, "pattern-scan", str(report), "1")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        findings = json.loads(r.stdout)
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("scan-error", findings[0]["type"])


class CompletedHandlersBindingTest(ToolReportPyTestBase):
    """Deliverable 2, part 2: COMPLETED and HANDLERS must share the same
    key set. read_tool() checks `kind not in HANDLERS` (:246) BEFORE it
    ever touches `COMPLETED[kind]` (:254) -- a kind present in HANDLERS but
    missing from COMPLETED passes that guard and only then raises, as an
    UNHANDLED KeyError, never a scan_error. Count pinned at 4 for both, so
    a removal shrinks the sweep below instead of narrowing it silently."""

    def test_completed_and_handlers_share_the_same_key_set(self):
        ns = load_tool_report_module()
        self.assertEqual(set(ns["COMPLETED"]), set(ns["HANDLERS"]))

    def test_both_dicts_are_pinned_at_4_entries(self):
        ns = load_tool_report_module()
        self.assertEqual(4, len(ns["COMPLETED"]))
        self.assertEqual(4, len(ns["HANDLERS"]))


class CompletedHandlersRemovalRedProofTest(ToolReportPyTestBase):
    """Removes one producer's COMPLETED entry at a time from a scratch copy
    of the extracted TOOL_REPORT_PY source (never scripts/quality-scan.sh
    itself), leaving its HANDLERS entry untouched, and confirms read_tool()
    reacts exactly as CompletedHandlersBindingTest's docstring predicts: an
    UNHANDLED KeyError (non-zero exit, "KeyError" + the kind's own name on
    stderr), not a scan_error finding -- proving the `if kind not in
    HANDLERS` guard at :246 really does not catch this case. Each entry's
    line is removed via a single, asserted-unique string match on the
    extracted text (G-141) -- never a retyped/rebuilt dict -- and the
    original (unmutated) run is checked first so a failure of THIS test can
    never be blamed on a broken fixture."""

    def test_removing_a_completed_entry_still_present_in_handlers_raises_keyerror(self):
        source = tool_report_source()
        for kind, statuses in COMPLETED_SHAPE.items():
            with self.subTest(kind=kind):
                needle = '    "%s": (' % kind
                self.assertEqual(
                    1, source.count(needle),
                    "fixture assumption: COMPLETED literal moved -- %r" % needle,
                )
                lines = source.splitlines(keepends=True)
                mutated_lines = [l for l in lines if not l.startswith(needle)]
                self.assertEqual(len(lines) - 1, len(mutated_lines))
                mutated_source = "".join(mutated_lines)

                report = self.write_report("%s.json" % kind, VALID_REPORT_DOC[kind])
                status = statuses[0]

                before_script = self.write_script(source)
                before = self.run_tool_report(before_script, kind, str(report), status)
                self.assertEqual(0, before.returncode, before.stdout + before.stderr)
                self.assertEqual([], json.loads(before.stdout))

                after_script = self.write_script(mutated_source)
                after = self.run_tool_report(after_script, kind, str(report), status)
                self.assertNotEqual(0, after.returncode, after.stdout + after.stderr)
                self.assertIn("KeyError", after.stderr)
                self.assertIn(kind, after.stderr)


# SEVERITIES (scripts/quality-scan.sh:91), consumed by findings_npm()'s
# `buckets = [k for k in SEVERITIES if k in meta]` (:114). Copied here ONLY
# to drive the per-entry sweep; SeveritiesShapeMatchesSourceTest below binds
# it to the extracted source the same way COMPLETED_SHAPE is bound above.
SEVERITIES_SHAPE = ("info", "low", "moderate", "high", "critical")


class SeveritiesShapeMatchesSourceTest(ToolReportPyTestBase):
    def test_severities_shape_equals_the_extracted_source(self):
        ns = load_tool_report_module()
        self.assertEqual(SEVERITIES_SHAPE, tuple(ns["SEVERITIES"]))


class SeveritiesPerEntryTest(ToolReportPyTestBase):
    """Deliverable 3: a missing severity name means that bucket is silently
    DROPPED from findings_npm()'s total -- the report still parses and the
    run still exits 0, the count is just wrong (never an error of its
    own). Per-entry proof: an npm report carrying ONLY that one severity
    bucket must produce exactly that count, for every one of the 5
    entries, plus a count pin at 5."""

    def test_each_severity_bucket_alone_produces_its_own_count(self):
        script = self.write_script()
        for sev in SEVERITIES_SHAPE:
            with self.subTest(severity=sev):
                report = self.write_report(
                    "%s.json" % sev, {"metadata": {"vulnerabilities": {sev: 3}}}
                )
                r = self.run_tool_report(script, "npm-audit", str(report), "0")
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                findings = json.loads(r.stdout)
                self.assertEqual(1, len(findings), findings)
                self.assertIn("3 npm", findings[0]["message"])

    def test_severities_count_is_pinned_at_5(self):
        self.assertEqual(5, len(SEVERITIES_SHAPE))


class SeveritiesRemovalRedProofTest(ToolReportPyTestBase):
    """Removes one SEVERITIES entry at a time from a scratch copy of the
    extracted TOOL_REPORT_PY source and confirms the SAME report that
    produced a real finding before the removal is now silently read as
    ZERO findings -- G-109's structural mutation (a tuple element removed,
    not merely an inequality assertion), and the specific failure mode
    quality-scan.sh's own SEVERITIES comment warns about: the report still
    parses, the run still exits 0, the number is just wrong. Both the
    before-run and the after-run go through the extracted source verbatim
    -- the "before" value is not assumed, it is measured on the same
    script object per subTest."""

    SEVERITIES_NEEDLE = 'SEVERITIES = ("info", "low", "moderate", "high", "critical")\n'

    def test_removing_a_severity_silently_drops_its_bucket_from_the_count(self):
        source = tool_report_source()
        self.assertEqual(
            1, source.count(self.SEVERITIES_NEEDLE),
            "fixture assumption: SEVERITIES literal moved",
        )

        for sev in SEVERITIES_SHAPE:
            with self.subTest(severity=sev):
                # All 5 buckets present, every one but the target at 0. This
                # (not a single-bucket report) is what isolates "silently
                # dropped from the total": after the target is removed from
                # SEVERITIES, `buckets` is still non-empty (the other 4
                # names are still in `meta`), so findings_npm() takes the
                # SILENT sum-goes-to-0 path rather than raising
                # ReportError("names no severity bucket") -- which is what
                # a single-bucket report would trigger instead, proving a
                # different (louder) failure mode than the one this
                # deliverable is about.
                meta = {s: (3 if s == sev else 0) for s in SEVERITIES_SHAPE}
                report = self.write_report("%s.json" % sev, {"metadata": {"vulnerabilities": meta}})

                before_script = self.write_script(source)
                before = self.run_tool_report(before_script, "npm-audit", str(report), "0")
                self.assertEqual(0, before.returncode, before.stdout + before.stderr)
                before_findings = json.loads(before.stdout)
                self.assertEqual(1, len(before_findings), before_findings)

                remaining = tuple(s for s in SEVERITIES_SHAPE if s != sev)
                mutated_source = source.replace(
                    self.SEVERITIES_NEEDLE, "SEVERITIES = %r\n" % (remaining,)
                )
                self.assertNotEqual(source, mutated_source)

                after_script = self.write_script(mutated_source)
                after = self.run_tool_report(after_script, "npm-audit", str(report), "0")
                self.assertEqual(0, after.returncode, after.stdout + after.stderr)
                after_findings = json.loads(after.stdout)
                self.assertEqual(
                    [], after_findings,
                    "removing %r from SEVERITIES did not silently drop its bucket" % sev,
                )


# ---------------------------------------------------------------------------
# WI-0128 wave 1a, defect 3 (second half): findings_semgrep()'s own silent
# cap at 20 results (:168 as of fc7e7bc) -- unlike the pattern-scan's 50-cap,
# this one carries no docstring at all. Same fix shape: one extra finding,
# appended only when the cap actually trims something, naming the real
# total.
# ---------------------------------------------------------------------------

def _semgrep_doc(count):
    return {
        "results": [
            {
                "check_id": "rule-%d" % i,
                "path": "app.py",
                "start": {"line": i},
                "extra": {"severity": "warning", "message": "m%d" % i},
            }
            for i in range(count)
        ]
    }


class SemgrepResultsCapTest(ToolReportPyTestBase):
    def test_more_than_20_results_are_capped_plus_one_truncation_marker(self):
        script = self.write_script()
        report = self.write_report("semgrep-25.json", _semgrep_doc(25))
        r = self.run_tool_report(script, "semgrep", str(report), "0")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        findings = json.loads(r.stdout)
        self.assertEqual(21, len(findings))
        marker = findings[-1]
        self.assertEqual("scan-truncated", marker["type"])
        self.assertIn("25", marker["message"])
        self.assertIn("20", marker["message"])

    def test_the_20_real_findings_preceding_the_marker_are_unaffected(self):
        script = self.write_script()
        report = self.write_report("semgrep-25.json", _semgrep_doc(25))
        r = self.run_tool_report(script, "semgrep", str(report), "0")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        findings = json.loads(r.stdout)
        real = findings[:-1]
        self.assertEqual(len(real), 20)
        for finding in real:
            self.assertEqual(finding["type"], "semgrep")

    def test_exactly_20_results_produce_20_with_no_marker(self):
        script = self.write_script()
        report = self.write_report("semgrep-20.json", _semgrep_doc(20))
        r = self.run_tool_report(script, "semgrep", str(report), "0")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        findings = json.loads(r.stdout)
        self.assertEqual(20, len(findings))
        self.assertNotIn("scan-truncated", [f["type"] for f in findings])


if __name__ == "__main__":
    unittest.main()
