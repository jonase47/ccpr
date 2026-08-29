r"""test_run_tests_argument_quoting.py -- WI-0129 finding F8: run-tests.sh's
own `TEST_PATH` CLI argument (the caller's first positional, `${1:-}`)
reaches four of its six consumption sites unquoted:

    npx vitest run ${test_arg} --reporter=json ...   (line 189)
    npx jest ${test_arg} --json --outputFile=...     (line 191)
    cargo test ${test_arg} ...                        (line 245)
    go test -v -count=1 ${test_arg} ...                (line 295)

Unquoted, bash word-splits and glob-expands `test_arg` before the runner
ever sees it: `./scripts/run-tests.sh "src/my tests"` reaches the runner as
TWO arguments instead of one, and a path containing `*` gets glob-expanded
against run-tests.sh's own CWD (it `cd`s into `PROJECT_DIR` at line 9,
before any runner is invoked). This is an argument-handling correctness
bug, not an injection: no shell re-evaluation of the value occurs, only
word splitting and pathname expansion of a single already-fixed argument.

## Why a new module, not an extension of test_run_tests_heredoc_injection.py

That module's subject is orthogonal: it exercises a fake `go`/`cargo`
binary that prints a crafted PAYLOAD to STDOUT to prove run-tests.sh's own
heredoc interpolation can't be hijacked by test-runner output content. This
module's subject is the ARGUMENT VECTOR run-tests.sh hands to a runner
BEFORE that runner ever produces output -- the fixture needs to capture
`"$@"` inside the fake binary, not print a payload for run-tests.sh to
consume. Sharing one module for two fixture shapes (payload-emitting fake
tool vs. argv-recording fake tool) would make each test's actual subject
harder to see at the call site, not easier -- a new file names the
subject once, in its own path and docstring, rather than growing the
existing one's already-long module docstring with an unrelated concern.

## Fixture shape

A fake binary is shadowed on PATH under the name run-tests.sh actually
invokes for each runner (`npx` for both `vitest` and `jest` -- the shipped
script always execs `npx <tool> ...`, never `vitest`/`jest` directly;
`cargo` and `go` are invoked directly). The fake binary's entire body is
`printf '%s\n' "$@" > <argv-file>` -- one line per argument it actually
received, so a word-split or glob-expanded `test_arg` shows up as EXTRA
lines rather than one line with embedded whitespace or wildcards. This
generalises `_run_fake_tool`'s scratch-dir-plus-PATH-shadow pattern from
test_run_tests_heredoc_injection.py (mkdtemp + addCleanup(shutil.rmtree...)
rather than a `with TemporaryDirectory()` block, for the same reason that
module documents: returning from inside the `with` block would delete the
scratch tree, argv file included, before the caller's assertion runs).

## The glob fixture is built to visibly fail an unfixed script

A glob pattern with zero matches proves nothing: an unquoted `${test_arg}`
containing `*` that matches no files in the CWD expands to the literal
pattern string anyway (bash's default, non-nullglob behaviour), so an
unfixed AND a fixed script would both pass such a test for the wrong
reason. Each glob test creates two real files in the scratch project
directory whose names the glob pattern matches (`glob_a.txt`,
`glob_b.txt`), so an unquoted, unfixed `${test_arg}` visibly expands into
two separate argv entries (the matched filenames) instead of remaining one
entry (the literal pattern).

## The discriminating case this module exists to pin

Quoting all four sites unconditionally (`"${test_arg}"`) is not the fix --
three of the four (vitest, jest, cargo) default `test_arg` to the EMPTY
STRING when no `TEST_PATH` is given (see run-tests.sh lines 184, 239), and
`cargo test ""` is not equivalent to `cargo test`: a quoted empty
expansion hands the runner a literal empty-string filter argument, not "no
filter argument at all". Today's unquoted form happens to get this right
by accident (an unquoted, unset-to-empty expansion contributes zero words),
which is exactly why naive blanket quoting is a regression, not a fix --
`test_*_empty_test_path_passes_no_extra_argument` below pins that this
must keep being true under the real fix too. `go`'s default (`./...`) is
never empty, so quoting alone is correct there -- see
`test_go_default_test_path_reaches_runner_as_one_argument`, which pins the
OPPOSITE shape: the default argument must still arrive, not vanish.
"""

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


class ArgumentQuotingTest(unittest.TestCase):
    def _run_capturing_argv(self, tool_name, marker_project_file, marker_content, test_path, extra_files=None):
        """Runs run-tests.sh with `tool_name` shadowed on PATH by a fake
        binary that records its own exact argument vector -- see the
        module docstring for why this fixture captures argv instead of
        emitting a stdout payload."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        tmp_path = Path(tmp)
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / marker_project_file).write_text(marker_content)
        for name in extra_files or ():
            (project_dir / name).write_text("")
        argv_file = tmp_path / "argv.captured"

        script = "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"{argv}\"\nexit 1\n".format(argv=argv_file)
        _write_executable(bin_dir / tool_name, script)

        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

        result = subprocess.run(
            ["bash", str(RUN_TESTS), test_path, str(project_dir)],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        argv_lines = argv_file.read_text().splitlines() if argv_file.exists() else []
        return result, argv_lines

    # -- vitest (npx vitest run ${test_arg} --reporter=json) --

    def test_vitest_space_in_test_path_reaches_runner_as_one_argument(self):
        result, argv = self._run_capturing_argv(
            "npx", "package.json", '{"devDependencies": {"vitest": "^1.0.0"}}', "my tests"
        )
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(["vitest", "run", "my tests", "--reporter=json"], argv)

    def test_vitest_glob_in_test_path_is_not_expanded(self):
        result, argv = self._run_capturing_argv(
            "npx",
            "package.json",
            '{"devDependencies": {"vitest": "^1.0.0"}}',
            "glob_*",
            extra_files=["glob_a.txt", "glob_b.txt"],
        )
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(["vitest", "run", "glob_*", "--reporter=json"], argv)

    def test_vitest_empty_test_path_passes_no_extra_argument(self):
        result, argv = self._run_capturing_argv(
            "npx", "package.json", '{"devDependencies": {"vitest": "^1.0.0"}}', ""
        )
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(["vitest", "run", "--reporter=json"], argv)

    # -- jest (npx jest ${test_arg} --json --outputFile=<tmpfile>) --

    def test_jest_space_in_test_path_reaches_runner_as_one_argument(self):
        result, argv = self._run_capturing_argv(
            "npx", "package.json", '{"devDependencies": {"jest": "^29.0.0"}}', "my tests"
        )
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(4, len(argv), argv)
        self.assertEqual("jest", argv[0])
        self.assertEqual("my tests", argv[1])
        self.assertEqual("--json", argv[2])
        self.assertTrue(argv[3].startswith("--outputFile="), argv)

    def test_jest_glob_in_test_path_is_not_expanded(self):
        result, argv = self._run_capturing_argv(
            "npx",
            "package.json",
            '{"devDependencies": {"jest": "^29.0.0"}}',
            "glob_*",
            extra_files=["glob_a.txt", "glob_b.txt"],
        )
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(4, len(argv), argv)
        self.assertEqual("jest", argv[0])
        self.assertEqual("glob_*", argv[1])
        self.assertEqual("--json", argv[2])
        self.assertTrue(argv[3].startswith("--outputFile="), argv)

    def test_jest_empty_test_path_passes_no_extra_argument(self):
        result, argv = self._run_capturing_argv(
            "npx", "package.json", '{"devDependencies": {"jest": "^29.0.0"}}', ""
        )
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(3, len(argv), argv)
        self.assertEqual("jest", argv[0])
        self.assertEqual("--json", argv[1])
        self.assertTrue(argv[2].startswith("--outputFile="), argv)

    # -- cargo (cargo test ${test_arg}) --

    def test_cargo_space_in_test_path_reaches_runner_as_one_argument(self):
        result, argv = self._run_capturing_argv("cargo", "Cargo.toml", "", "my tests")
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(["test", "my tests"], argv)

    def test_cargo_glob_in_test_path_is_not_expanded(self):
        result, argv = self._run_capturing_argv(
            "cargo", "Cargo.toml", "", "glob_*", extra_files=["glob_a.txt", "glob_b.txt"]
        )
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(["test", "glob_*"], argv)

    def test_cargo_empty_test_path_passes_no_extra_argument(self):
        result, argv = self._run_capturing_argv("cargo", "Cargo.toml", "", "")
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(["test"], argv)

    # -- go (go test -v -count=1 ${test_arg}) --

    def test_go_space_in_test_path_reaches_runner_as_one_argument(self):
        result, argv = self._run_capturing_argv("go", "go.mod", "", "my tests")
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(["test", "-v", "-count=1", "my tests"], argv)

    def test_go_glob_in_test_path_is_not_expanded(self):
        result, argv = self._run_capturing_argv(
            "go", "go.mod", "", "glob_*", extra_files=["glob_a.txt", "glob_b.txt"]
        )
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(["test", "-v", "-count=1", "glob_*"], argv)

    def test_go_default_test_path_reaches_runner_as_one_argument(self):
        """No `TEST_PATH` given -- go's default (`./...`) must still arrive
        as exactly one argument. This is the opposite pin from the other
        three runners' `..._empty_test_path_passes_no_extra_argument`
        tests: go's default is never empty, so "no path given" must NOT
        mean "no argument" here."""
        result, argv = self._run_capturing_argv("go", "go.mod", "", "")
        self.assertEqual(0, result.returncode, f"run-tests.sh crashed: {result.stderr!r}")
        self.assertEqual(["test", "-v", "-count=1", "./..."], argv)


if __name__ == "__main__":
    unittest.main()
