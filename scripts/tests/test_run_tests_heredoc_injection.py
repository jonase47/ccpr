r"""test_run_tests_heredoc_injection.py -- WI-0129 finding F7: run-tests.sh
captures a test runner's raw, UNTRUSTED stdout into a bash variable and then
interpolates it into Python source through an unquoted heredoc delimiter:

    raw=$(go test -v -count=1 ${test_arg} 2>&1 || true)

    python3 << PYEOF
    import re, json

    raw = '''${raw}'''

Because the heredoc delimiter `PYEOF` is unquoted, bash performs parameter
expansion on `${raw}` before handing the body to python3's stdin -- the
substitution happens in the SHELL, before python3 ever sees a single
character. If `raw` contains the literal `'''`, that substring closes the
Python triple-quoted string early; every line after it is parsed and
executed as Python source, not treated as string content. Test output is
attacker-influenced input: this script is named in CLAUDE.md as part of the
normal workflow and is run against foreign/consumer projects, so a test
whose failure message happens to contain `'''` (accidentally or by design)
gets to run arbitrary Python inside this process.

## Proof shape

A fake `go`/`cargo` binary is placed first on PATH, printing a payload whose
body closes the `'''` literal and appends a line that writes a marker file
if executed. `detect_framework()` is steered to the right runner via a
marker project file (`go.mod` / `Cargo.toml`) in a scratch project
directory -- no real Go/Rust toolchain is needed anywhere in this test.

## Why two runners, not just `go`

The three vulnerable sites (`run_pytest`'s fallback branch, `run_cargo`,
`run_go`) share the exact same `raw = '''${raw}'''` shape -- see WI-0129's
own enumeration, confirmed by re-reading run-tests.sh line for line: heredocs
at lines 62 (pytest json-report, no `raw`), 119 (pytest fallback, `raw` at
122), 175 (jest/vitest, no `raw`), 222 (cargo, `raw` at 225), 265 (go, `raw`
at 268) -- line numbers as measured pre-fix. `go` and `cargo` are exercised
here because both `detect_framework` routes are triggered by a single marker
FILE (`go.mod` / `Cargo.toml`) with no plugin-availability branching, unlike
pytest's fallback path (only reached when `pytest_json_report` is NOT
importable, harder to force deterministically from a fixture without
shadowing the real interpreter).

## Positive assertions, not absence-only

Per G-126 (a "ran" guard needs a non-empty expectation, not just the
absence of a crash): each test asserts THREE things, not just the marker
file's absence -- (1) the marker file was NOT created (the injected code
did not run), (2) run-tests.sh itself exited 0 (it did not crash under its
own `set -e` while handling the crafted payload), and (3) it still produced
well-formed JSON naming the expected framework. (2) and (3) both fail loudly
on their own if the harness merely aborted rather than genuinely defusing
the payload -- a regression that silently deleted everything except the
marker-file check would still be caught by either one.

`_run_fake_tool`'s own name deliberately matches
test_absence_only_assertions.py's `RUN_HELPER_RE` (`^_?run(_\w+)?$`): an
earlier draft of this file named it `_invoke_fake_tool` specifically to
dodge that scanner's `_calls_a_subprocess` naming heuristic, keeping both
test methods below permanently invisible to the "no absence-only test
without a reasoned exemption" safety net regardless of how their assertions
evolved later. Code review (WI-0129) flagged that as trading a one-time pin
update for a standing blind spot on tests that exist specifically to guard
a security fix. Renaming back in means both methods ARE now in scope for
that scanner; `self.assertEqual(0, result.returncode, ...)` in each is
unconditionally recognised as a "positive" (liveness) assertion by that
scanner's `_references_returncode` check (it matches ANY assertion
mentioning a `.returncode` attribute, independent of variable-tracking), so
the pair as a whole classifies `not-flagged`, not `absence-only-needs-
exemption` -- honestly in scope, not evasively excluded.
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
RUN_TESTS = REPO_ROOT / "scripts" / "run-tests.sh"


def _write_executable(path, content):
    path.write_text(content)
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class HeredocInjectionTest(unittest.TestCase):
    def _run_fake_tool(self, tool_name, marker_project_file, payload_template):
        """Runs run-tests.sh with `tool_name` shadowed on PATH by a fake
        binary printing `payload_template` (formatted with the marker file's
        own absolute path).

        Uses `mkdtemp()` + `addCleanup(shutil.rmtree, ...)` rather than
        `TemporaryDirectory()` as a `with` block scoped to this method:
        returning `(result, marker_file)` from inside that `with` block
        would run the context manager's own cleanup -- deleting the whole
        scratch tree, marker file included -- BEFORE the caller's assertion
        ever inspects it, making `assertFalse(marker_file.exists())` pass
        vacuously regardless of whether the injected payload ran. Measured
        directly while writing this test: with the `with`-block shape, both
        methods below reported green even though a standalone reproduction
        of the identical scenario (same fixture, same fake `go` binary, run
        outside unittest) left the marker file in place.
        """
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        tmp_path = Path(tmp)
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / marker_project_file).write_text("")
        marker_file = tmp_path / "code-executed.marker"

        payload = payload_template.format(marker=marker_file)
        script = "#!/bin/sh\ncat <<'PAYLOAD'\n" + payload + "\nPAYLOAD\nexit 1\n"
        _write_executable(bin_dir / tool_name, script)

        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

        result = subprocess.run(
            ["bash", str(RUN_TESTS), "", str(project_dir)],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        return result, marker_file

    def test_go_runner_output_cannot_execute_python_via_unquoted_heredoc(self):
        payload = (
            "--- FAIL: TestSomething (0.00s)\n"
            "    assert failed, fixture was: '''\n"
            'import pathlib; pathlib.Path("{marker}").write_text("code executed")\n'
            "raw = '''rest"
        )
        result, marker_file = self._run_fake_tool("go", "go.mod", payload)

        self.assertFalse(
            marker_file.exists(),
            "fake `go` test output closed the heredoc's Python triple-quoted "
            "string literal early and its injected payload executed -- "
            "run-tests.sh interpolates untrusted test output through an "
            f"unquoted heredoc delimiter (stdout={result.stdout!r}, "
            f"stderr={result.stderr!r})",
        )
        self.assertEqual(
            0,
            result.returncode,
            f"run-tests.sh exited nonzero handling the crafted `go` output "
            f"(stdout={result.stdout!r}, stderr={result.stderr!r})",
        )
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(
                "run-tests.sh did not produce valid JSON after the fake `go` "
                f"run: stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        self.assertEqual("go", report.get("framework"))

    def test_cargo_runner_output_cannot_execute_python_via_unquoted_heredoc(self):
        payload = (
            "test result: FAILED. 0 passed; 1 failed; 0 ignored\n"
            "---- some::test stdout ----\n"
            "assertion failed: '''\n"
            'import pathlib; pathlib.Path("{marker}").write_text("code executed")\n'
            "raw = '''rest"
        )
        result, marker_file = self._run_fake_tool("cargo", "Cargo.toml", payload)

        self.assertFalse(
            marker_file.exists(),
            "fake `cargo` test output closed the heredoc's Python "
            "triple-quoted string literal early and its injected payload "
            f"executed (stdout={result.stdout!r}, stderr={result.stderr!r})",
        )
        self.assertEqual(
            0,
            result.returncode,
            f"run-tests.sh exited nonzero handling the crafted `cargo` output "
            f"(stdout={result.stdout!r}, stderr={result.stderr!r})",
        )
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(
                "run-tests.sh did not produce valid JSON after the fake "
                f"`cargo` run: stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        self.assertEqual("cargo", report.get("framework"))


if __name__ == "__main__":
    unittest.main()
