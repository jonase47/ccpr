"""test_log_cleanup_behavior.py -- WI-0056: scripts/log-cleanup.sh must not
replace a real log with an empty/partial file when its python3 trim helper
does not complete.

## What was measured before fixing anything

The item's own headline mechanism -- "python3 fails, the temp file is empty,
the unconditional `mv` overwrites the real log" -- was measured two ways
against the UNFIXED script and did **not** reproduce:

  * a PATH-stub `python3` that writes nothing and exits 1;
  * the repository's own established "realistic broken interpreter" method
    (`PYTHONHOME=/nonexistent python3 -c ...`, see test_artifact_gate.py's
    WI-0049 section), which exits 1 before running any of the script's code.

Both abort under this file's own `set -euo pipefail` at the bare `python3`
statement itself, BEFORE the unconditional `mv` on the next line is ever
reached -- the original log survives, but silently: `2>/dev/null` discards
python3's own diagnostic, and bash's `errexit` prints nothing of its own, so
the run stops with exit 1 and empty stderr, no indication of which file (of
three) failed or why.

The measured, reproducible DATA-LOSS shape is narrower and different: a
`python3` that returns exit status 0 without doing the real work (a broken
shim, a hijacked PATH entry -- not a crash in the ordinary sense). Only that
shape defeats an exit-status check by definition, because it does not fail
by that measure. This is reported as a residual, out-of-reach gap in
docs/memory/senior-developer/ -- not silently claimed as closed.

## What the fix changes

1. The trim's `tmpfile` is created in `${LOG_DIR}` (same filesystem as the
   target), so the final `mv` is a single atomic rename -- no window where
   a reader could observe a half-written file, and a process kill either
   lands before that rename (original untouched) or after it (new content
   in place); the only residual cost is a possible orphaned tmpfile on an
   uncatchable SIGKILL, cosmetic, not data loss.
2. python3's exit status is captured EXPLICITLY (`if ... ; then`), not left
   to `set -e` alone -- independent of any future refactor that might wrap
   this code in a context where `errexit` no longer applies.
3. On failure, the ORIGINAL file is left untouched, the tmpfile is removed,
   a clear `[ERROR]` naming the affected logfile is printed to stderr (the
   `2>/dev/null` on the python3 call itself is kept -- python's own
   per-line `except: pass` already absorbs expected bad-JSON noise, but the
   outer failure is now surfaced explicitly rather than through stderr), and
   the loop CONTINUES to the next file rather than aborting the whole run --
   one broken file must not deny cleanup to the other two. The overall
   script still exits non-zero if any file failed, so a cron/CI caller still
   notices.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "log-cleanup.sh"

ORIGINAL_ACTIVITY = (
    '{"ts":"2026-08-10T00:00:00","msg":"a"}\n'
    '{"ts":"2026-08-11T00:00:00","msg":"b"}\n'
    '{"ts":"2026-08-12T00:00:00","msg":"c"}\n'
)
ORIGINAL_ERRORS = '{"ts":"2026-08-10T00:00:00","msg":"err-a"}\n'
ORIGINAL_PERFORMANCE = '{"ts":"2026-08-10T00:00:00","msg":"perf-a"}\n'


class LogCleanupTestBase(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="ccpr-log-cleanup-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.log_dir = self.home / ".claude" / "logs"
        self.log_dir.mkdir(parents=True)

    def write_logs(self):
        (self.log_dir / "activity.jsonl").write_text(ORIGINAL_ACTIVITY, encoding="utf-8")
        (self.log_dir / "errors.jsonl").write_text(ORIGINAL_ERRORS, encoding="utf-8")
        (self.log_dir / "performance.jsonl").write_text(
            ORIGINAL_PERFORMANCE, encoding="utf-8"
        )

    def env(self, **extra):
        e = dict(os.environ)
        e["HOME"] = str(self.home)
        e.update(extra)
        return e

    def run_cleanup(self, *args, **extra_env):
        return subprocess.run(
            ["bash", str(SCRIPT), "--days", "3650", *args],
            capture_output=True, text=True, env=self.env(**extra_env),
        )

    def stray_tmpfiles(self):
        return sorted(
            p.name for p in self.log_dir.glob("*.jsonl.*") if p.is_file()
        )


class BrokenInterpreterLeavesOriginalsUntouchedTest(LogCleanupTestBase):
    """The item's own scenario, measured with this repo's established
    "realistic broken python3" method (PYTHONHOME=/nonexistent)."""

    def test_all_three_logs_survive_byte_for_byte(self):
        self.write_logs()
        r = self.run_cleanup(PYTHONHOME="/nonexistent")

        self.assertEqual(
            ORIGINAL_ACTIVITY,
            (self.log_dir / "activity.jsonl").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            ORIGINAL_ERRORS,
            (self.log_dir / "errors.jsonl").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            ORIGINAL_PERFORMANCE,
            (self.log_dir / "performance.jsonl").read_text(encoding="utf-8"),
        )
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)

    def test_the_run_reaches_its_own_summary_instead_of_aborting_on_the_first_file(self):
        # Before the fix: `set -e` aborts at the FIRST broken python3 call,
        # so "=== Result ===" (printed after all three files) never appears
        # and the second/third files are never even attempted.
        self.write_logs()
        r = self.run_cleanup(PYTHONHOME="/nonexistent")
        self.assertIn("=== Result ===", r.stdout, r.stdout + r.stderr)

    def test_the_failure_is_explained_per_file_not_silent(self):
        # Before the fix: stderr is completely empty (python3's own message
        # is discarded by `2>/dev/null`, and bash's errexit prints nothing
        # of its own) -- a silent, unexplained stop.
        self.write_logs()
        r = self.run_cleanup(PYTHONHOME="/nonexistent")
        self.assertIn("activity.jsonl", r.stderr, r.stderr)
        self.assertIn("errors.jsonl", r.stderr, r.stderr)
        self.assertIn("performance.jsonl", r.stderr, r.stderr)

    def test_no_orphaned_tmpfile_is_left_behind(self):
        self.write_logs()
        self.run_cleanup(PYTHONHOME="/nonexistent")
        self.assertEqual([], self.stray_tmpfiles())


class MalformedButZeroExitOutputTest(LogCleanupTestBase):
    """The actually-reproducible data-loss shape (see module docstring): a
    python3 that returns EXIT 0 without doing the real work. A PATH-stub is
    used deliberately here -- unlike the broken-interpreter tests above,
    this is not simulating "python3 itself is damaged" (this repo's own
    precedent already prefers PYTHONHOME for that, see test_artifact_gate.py)
    but proving THIS SCRIPT's own defensive parsing of python3's output,
    which needs precise, arbitrary stdout content a real interpreter cannot
    be made to produce on demand."""

    def stub_python3(self, script_body):
        stub_dir = Path(tempfile.mkdtemp(prefix="ccpr-log-cleanup-stub-"))
        self.addCleanup(shutil.rmtree, stub_dir, ignore_errors=True)
        stub = stub_dir / "python3"
        stub.write_text("#!/usr/bin/env bash\n" + script_body + "\n", encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        return f"{stub_dir}:/usr/bin:/bin:/usr/sbin:/sbin"

    def test_exit_zero_with_non_numeric_output_does_not_overwrite_the_log(self):
        self.write_logs()
        path = self.stub_python3("echo not-a-number; exit 0")
        r = self.run_cleanup(PATH=path)

        self.assertEqual(
            ORIGINAL_ACTIVITY,
            (self.log_dir / "activity.jsonl").read_text(encoding="utf-8"),
        )
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)

    def test_exit_zero_with_empty_output_does_not_overwrite_the_log(self):
        self.write_logs()
        path = self.stub_python3("exit 0")
        r = self.run_cleanup(PATH=path)

        self.assertEqual(
            ORIGINAL_ACTIVITY,
            (self.log_dir / "activity.jsonl").read_text(encoding="utf-8"),
        )
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)


class NormalTrimStillWorksTest(LogCleanupTestBase):
    """Regression guard: the fix must not change the happy path -- old
    entries are still dropped, recent ones survive, and the swap still
    happens (via a same-directory tmpfile now, still observably a rename)."""

    def test_old_lines_are_dropped_recent_lines_survive(self):
        (self.log_dir / "activity.jsonl").write_text(
            '{"ts":"2000-01-01T00:00:00","msg":"ancient"}\n'
            '{"ts":"2099-01-01T00:00:00","msg":"future"}\n',
            encoding="utf-8",
        )
        r = self.run_cleanup()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

        remaining = (self.log_dir / "activity.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("ancient", remaining)
        self.assertIn("future", remaining)

    def test_no_stray_tmpfile_after_a_successful_run(self):
        self.write_logs()
        r = self.run_cleanup()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual([], self.stray_tmpfiles())


class RedProofTest(LogCleanupTestBase):
    """Mutation proof, inline: restoring the exact pre-fix shape (bare
    `python3 ... 2>/dev/null` immediately followed by an unconditional
    `mv`, no same-directory tmpfile) must fail at least one of the tests
    above -- proving they are not vacuously green."""

    def test_reverting_the_status_check_breaks_the_error_visibility_test(self):
        pre_fix_block = '''
    else
        # Actually trim
        tmpfile=$(mktemp)
        python3 -c "
import json
cutoff = '${CUTOFF_DATE}'
with open('${filepath}') as f_in, open('${tmpfile}', 'w') as f_out:
    for line in f_in:
        try:
            ts = json.loads(line).get('ts', '')
            if ts >= cutoff:
                f_out.write(line)
        except:
            pass  # Discard broken lines
" 2>/dev/null  # exit-status: exempt known-risk-not-yet-fixed
        lines_after=$(wc -l < "${tmpfile}" | tr -d ' ')
        LINES_AFTER=$((LINES_AFTER + lines_after))
        mv "${tmpfile}" "${filepath}"
        echo "  [TRIM] ${logfile}: ${lines_before} -> ${lines_after} lines"
    fi
done
'''
        current = SCRIPT.read_text(encoding="utf-8")
        start = current.index("    else\n        # Actually trim")
        end = current.index("done\n", start) + len("done\n")
        mutated = current[:start] + pre_fix_block.lstrip("\n") + current[end:]

        scratch = Path(tempfile.mkdtemp(prefix="ccpr-log-cleanup-mutant-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        mutant_script = scratch / "log-cleanup.sh"
        mutant_script.write_text(mutated, encoding="utf-8")
        mutant_script.chmod(mutant_script.stat().st_mode | stat.S_IEXEC)

        self.write_logs()
        r = subprocess.run(
            ["bash", str(mutant_script), "--days", "3650"],
            capture_output=True, text=True,
            env=self.env(PYTHONHOME="/nonexistent"),
        )
        # The pre-fix shape's own measured symptom: stderr is empty.
        self.assertEqual("", r.stderr)
        self.assertNotIn("=== Result ===", r.stdout)
        # Liveness (WI-0128 finding #1): the mutant's python3 call itself
        # failed under `set -e` (matching the module docstring's own
        # "exit 1 and empty stderr" measurement) -- not merely "no Result
        # heading" for some unrelated reason, e.g. a broken splice that
        # crashed bash before this point at all (which would print its own,
        # non-empty stderr and already fail the assertion above).
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)


class ArchiveDirectoryPermissionsTest(LogCleanupTestBase):
    """WI-0129/F10 hardened everything under ~/.claude/logs to 0700/0600
    (hooks/agent-monitor.py), but scripts/log-cleanup.sh's own archive-dir
    creation (the `mkdir -p "${ARCHIVE_DIR}"` in the session-sweep loop) was
    never touched by that fix -- it ships with no `-m`/`chmod` hardening at
    all, so it lands wherever the executing process's umask happens to put
    it. Measured on a real machine: after a log-cleanup.sh run under a
    permissive umask, the archive directory sits at the umask-masked default
    (e.g. 0755) while its freshly-hardened siblings sit at 0700.

    The test sets the subprocess's OWN umask explicitly (umask is shell-
    process state, not something `env=` can carry) via a `bash -c` wrapper,
    rather than relying on whatever umask the test-running machine happens
    to have -- a restrictive dev/CI umask (e.g. 077) would make even the
    unfixed script pass by accident and prove nothing.
    """

    def run_with_umask(self, umask, *args, **extra_env):
        return subprocess.run(
            ["bash", "-c", 'umask "$1"; shift; exec bash "$0" "$@"',
             str(SCRIPT), umask, *args],
            capture_output=True, text=True, env=self.env(**extra_env),
        )

    def make_old_session(self, session_id="old-session"):
        session_dir = self.log_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (session_dir / "session-summary.json").write_text("{}\n", encoding="utf-8")
        # Backdate the session directory itself (not just the file inside
        # it): with only a session-summary.json present -- no *.jsonl --
        # the script's own age-detection falls through both its `find
        # -printf` (GNU-only, fails on BSD/macOS find) and its `stat -f '%m'
        # *.jsonl` fallback (no match) to its final fallback, the session
        # DIRECTORY's own mtime.
        old_time = time.time() - 4000 * 86400
        os.utime(session_dir, (old_time, old_time))
        return session_dir

    def test_archive_dir_is_0700_regardless_of_permissive_umask(self):
        session_dir = self.make_old_session()
        r = self.run_with_umask("022", "--days", "1")

        # Sanity: the archive branch actually ran (session was swept), not
        # just "the directory happened to pre-exist from somewhere else".
        self.assertFalse(session_dir.exists(), r.stdout + r.stderr)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

        archive_dir = self.log_dir / "session-archive"
        self.assertTrue(archive_dir.is_dir(), r.stdout + r.stderr)
        mode = stat.S_IMODE(os.stat(archive_dir).st_mode)
        self.assertEqual(0o700, mode, oct(mode))


if __name__ == "__main__":
    unittest.main()
