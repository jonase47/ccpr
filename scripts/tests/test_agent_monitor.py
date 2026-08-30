"""test_agent_monitor.py -- WI-0129 finding F10: the loop-state file's move out of a
hardcoded /tmp, and the session_id path-traversal guard that makes that move meaningful.

## The defect (measured 29.08.2026, before this fix)

hooks/agent-monitor.py is wired into settings.json on eight hook events and runs on
every session. Two things were true of it:

1. `get_loop_state_path` (main() line ~150 in the pre-fix version) built
   `Path(f"/tmp/claude-loop-{session_id}.json")` -- a hardcoded, world-writable, shared
   directory, not the user's own TMPDIR. On macOS, honouring TMPDIR would have used a
   private, mode-700 per-user directory instead. Live files measured on disk were
   world-readable (mode 644) and their names were fully predictable.
2. `session_id` reaches the filesystem unvalidated -- it comes straight off hook-supplied
   stdin (`data.get("session_id", "no-session")` in main()) and was used as a path
   component in `ensure_dirs`' mkdir AND in `get_loop_state_path`, with no shape check.
   Nothing stopped a "/" or ".." from relocating either path (see the module's own
   sanitize_session_id docstring for the concrete escape shapes).

Both are fixed together here: the state file moves to `tempfile.gettempdir()` (honours
TMPDIR) and is created with 0o600 permissions, and every place that turns session_id into
a path component -- not just the two named in the finding, but every SESSION_LOG_BASE /
session_id site (ensure_dirs, the three log_* functions, and the SessionEnd summary path)
-- now goes through one `sanitize_session_id` gate, so a malformed id cannot slip past one
call site while another still uses the raw value.

## Fixture design

Follows test_handover_size_hook.py's shape: drives the real entry point
(`python3 hooks/agent-monitor.py`) as a subprocess with a crafted hook payload on stdin,
never importing internals for behaviour. Two environment redirections make a run
reproducible and side-effect-free on the developer's own machine:

* **HOME** points at a throwaway directory -- the hook derives all log paths from
  `~/.claude/logs/**`.
* **TMPDIR** points at a throwaway directory too -- the very thing under test. Without
  this redirection the tests could not tell "followed TMPDIR" apart from "happened to
  land in the real /tmp anyway", and a run would leave files in the developer's real temp
  directory.

The tests are grouped by the question they answer:

* **Does the state file land in the right place?** -- TMPDIR is honoured, not the literal
  "/tmp".
* **Is it created with safe permissions?** -- mode bits, not merely "no crash".
* **Does a malformed session_id stay contained?** -- "/", "..", and empty each fall back
  to one fixed, safe name instead of reaching the filesystem raw.
* **Do the real shapes still work unchanged?** -- an actual UUID4 and the literal
  "no-session" default must NOT be replaced by the fallback.
* **Does the hook still never break a session?** -- the pre-existing fail-safe contract
  (malformed/empty stdin, an unknown event) pinned so a later change cannot quietly
  remove it.

## Second subject, added 30.08.2026: the two cleanups nothing ever triggered

Findings #27 and #25 put two housekeeping jobs into handle_session_start -- a
once-per-day run of scripts/log-cleanup.sh, and an age-based sweep of loop-state files
left behind by terminations that raise no SessionEnd. They share this file because they
share the fixture: a throwaway HOME, a throwaway TMPDIR, and the real entry point driven
as a subprocess.

They also share the defect class, which is what the tests below are actually about: a
mechanism that is never triggered looks exactly like a mechanism that had nothing to do.
So the assertions come in pairs -- second start on the same day does NOT run it / first
start the next day DOES; a run that removed nothing files a record / a throttled start
files none. A single-sided test here would survive every broken throttle there is.

One documented exception to this file's subprocess-only rule: LogCleanupTimeoutTest and
LogCleanupClockTest drive the functions in-process via module_with_home, because a
timeout measured in tens of seconds and a UTC day boundary cannot be reached from
outside. Both are inputs to the functions for exactly that reason.
"""

import contextlib
import datetime
import importlib.util
import json
import os
import stat
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "agent-monitor.py"

# Every hook run is bounded. A normal invocation costs ~20 ms (process startup
# dominates); this ceiling exists so a guard regression that makes the hook block turns
# into a failing test instead of a wedged test runner.
HOOK_TIMEOUT_S = 10


def _load_agent_monitor_module():
    """Loads hooks/agent-monitor.py as a module, for its constants only.

    Mirrors test_handover_size_hook.py's helper of the same name and the same rationale:
    used exclusively as the source of truth for FALLBACK_SESSION_ID below -- every
    behaviour assertion in this file still drives the real entry point as a subprocess
    (see module docstring). __name__ is "ccpr_agent_monitor_f10", not "__main__", so the
    `if __name__ == "__main__": main()` guard at the bottom of the hook does not fire.
    """
    spec = importlib.util.spec_from_file_location("ccpr_agent_monitor_f10", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AGENT_MONITOR = _load_agent_monitor_module()

# Real shapes seen on stdin. The UUID is the literal example from the finding; the
# literal default is main()'s own fallback for a payload missing the key entirely.
REAL_UUID_SESSION_ID = "0a954ab5-388e-4954-b5d5-9a037cb0e981"
LITERAL_DEFAULT_SESSION_ID = "no-session"

# Stub bodies for the planted log-cleanup script. Both reproduce the real script's
# "=== Result ===" summary block verbatim in shape (scripts/log-cleanup.sh:237-244) --
# that block is the only machine-readable account the script gives of what it did, and
# the hook parses it to tell "removed something" from "had nothing to do".
CLEANUP_STUB_REMOVED_SOMETHING = """\
echo "=== Log cleanup (keeping last 7 days) ==="
echo "Cutoff: 2026-08-23T00:00:00"
echo ""
echo "Sessions: 4 removed, 19 kept"
echo ""
echo "=== Result ==="
echo "Sessions: 4 removed, 19 kept"
echo "Log lines: 100 -> 40 (60 removed)"
"""

CLEANUP_STUB_FOUND_NOTHING = """\
echo "=== Log cleanup (keeping last 7 days) ==="
echo ""
echo "=== Result ==="
echo "Sessions: 0 removed, 23 kept"
echo "Log lines: 40 -> 40 (0 removed)"
"""


@contextlib.contextmanager
def module_with_home(home: Path, tmpdir: Path = None):
    """Re-imports the hook with HOME pointed at `home`, for the few assertions that
    cannot be made through the subprocess entry point.

    Three things need this: the cleanup subprocess timeout and the UTC day boundary
    (both production values an end-to-end run cannot reach -- a timeout in tens of
    seconds, a date change at midnight), and fault injection into the sweep. Every
    OTHER assertion in this file still drives the real entry point (see the module
    docstring); this is the documented exception, not a second style.

    `tmpdir` is NOT optional decoration for any caller that reaches
    sweep_stale_loop_state: that function DELETES files, and in-process it would
    otherwise resolve `tempfile.gettempdir()` to the developer's REAL temp directory --
    this process has already called mkdtemp in setUp, so tempfile's module-level cache
    is populated and no amount of setting TMPDIR in os.environ would redirect it. The
    cache is overridden directly and restored on the way out.
    """
    old_home = os.environ.get("HOME")
    old_tempdir = tempfile.tempdir
    os.environ["HOME"] = str(home)
    if tmpdir is not None:
        tempfile.tempdir = str(tmpdir)
    try:
        yield _load_agent_monitor_module()
    finally:
        tempfile.tempdir = old_tempdir
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home


# Malformed shapes the finding calls out by name. Each must fall back to the same fixed,
# safe name rather than reaching the filesystem as-is.
SLASH_SESSION_ID = "sneaky/session"
TRAVERSAL_SESSION_ID = "../evil"
EMPTY_SESSION_ID = ""


class AgentMonitorHookTestCase(unittest.TestCase):
    """Shared fixture: a temp project dir, a temp HOME, and a private scratch TMPDIR."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-agent-monitor-hook-"))
        self.project = self.tmp / "project"
        (self.project / "docs").mkdir(parents=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        # The directory under test. Deliberately NOT named "tmp" and deliberately not the
        # real system temp dir, so a mutation that reverts to a hardcoded "/tmp" produces
        # a visibly wrong (empty) result here instead of an accidental pass.
        self.scratch_tmpdir = self.tmp / "private-tmpdir"
        self.scratch_tmpdir.mkdir()
        self.session_id = f"test-{uuid.uuid4().hex[:12]}"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- helpers -----------------------------------------------------------------

    def run_hook(self, event: str, session_id: str = None, cwd: Path = None,
                 tmpdir: Path = None, raw_stdin: str = None,
                 timeout: float = HOOK_TIMEOUT_S, **payload):
        """Drives agent-monitor.py with one hook payload and returns the CompletedProcess.

        raw_stdin, when given, bypasses the JSON envelope entirely (malformed-input
        tests); otherwise a well-formed payload is built from event/session_id/payload.
        """
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["TMPDIR"] = str(tmpdir if tmpdir is not None else self.scratch_tmpdir)

        if raw_stdin is not None:
            stdin_text = raw_stdin
        else:
            body = {"hook_event_name": event}
            if session_id is not None:
                body["session_id"] = session_id
            body.update(payload)
            stdin_text = json.dumps(body)

        return subprocess.run(
            ["python3", str(HOOK_PATH)],
            input=stdin_text,
            cwd=str(cwd or self.project),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def loop_state_files(self, tmpdir: Path = None) -> list:
        """All claude-loop-*.json files directly inside the given (or scratch) tmpdir."""
        return sorted((tmpdir or self.scratch_tmpdir).glob("claude-loop-*.json"))

    def sessions_dir(self) -> Path:
        return self.home / ".claude" / "logs" / "sessions"

    def read_jsonl(self, path: Path) -> list:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]

    # --- log-cleanup / stale-state fixture helpers --------------------------------

    def cleanup_script_path(self) -> Path:
        """Where the hook looks for the cleanup script -- inside the throwaway HOME."""
        return self.home / ".claude" / "scripts" / "log-cleanup.sh"

    def cleanup_stamp_path(self) -> Path:
        return self.home / ".claude" / "logs" / ".log-cleanup-last-run"

    def cleanup_invocations_path(self) -> Path:
        return self.home / "cleanup-invocations.log"

    def install_cleanup_stub(self, body: str = CLEANUP_STUB_REMOVED_SOMETHING) -> Path:
        """Plants a stand-in for scripts/log-cleanup.sh inside the throwaway HOME.

        The REAL script is deliberately not used here: these tests are about WHEN and
        HOW OFTEN a session start triggers a cleanup and how the result is reported,
        not about what the cleanup itself deletes -- that is
        test_log_cleanup_behavior.py's subject, against the real script. A stub
        records every invocation in a file the test can count, and can be told to
        fail, hang, or print any summary shape the parsing side is being probed with.
        """
        script = self.cleanup_script_path()
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            "#!/usr/bin/env bash\n"
            + f'echo "invoked $*" >> "{self.cleanup_invocations_path()}"\n'
            + body,
            encoding="utf-8",
        )
        script.chmod(0o700)
        return script

    def cleanup_invocation_count(self) -> int:
        path = self.cleanup_invocations_path()
        if not path.exists():
            return 0
        return len([line for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()])

    def today_stamp(self) -> str:
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    def write_stamp(self, text: str) -> Path:
        stamp = self.cleanup_stamp_path()
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(text, encoding="utf-8")
        return stamp

    def activity_events(self, session_id: str, event: str) -> list:
        entries = self.read_jsonl(self.sessions_dir() / session_id / "activity.jsonl")
        return [e for e in entries if e.get("event") == event]

    def error_events(self, session_id: str, event: str) -> list:
        entries = self.read_jsonl(self.sessions_dir() / session_id / "errors.jsonl")
        return [e for e in entries if e.get("event") == event]

    def plant_loop_state_file(self, name: str, age_s: float) -> Path:
        """A foreign claude-loop-*.json in the scratch TMPDIR, aged by mtime."""
        path = self.scratch_tmpdir / name
        path.write_text('{"total_tool_calls": 1}', encoding="utf-8")
        when = time.time() - age_s
        os.utime(path, (when, when))
        return path


# === Does the state file land in the right place? ================================

class TmpdirLocationTest(AgentMonitorHookTestCase):

    def test_state_file_is_created_directly_inside_the_configured_tmpdir(self):
        result = self.run_hook("SessionStart", session_id=REAL_UUID_SESSION_ID,
                               source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        expected = self.scratch_tmpdir / f"claude-loop-{REAL_UUID_SESSION_ID}.json"
        self.assertTrue(expected.is_file(),
                        f"expected {expected} to exist; found {self.loop_state_files()}")
        self.assertEqual(self.scratch_tmpdir.resolve(), expected.parent.resolve())

    def test_a_different_tmpdir_relocates_the_state_file(self):
        """Proves the directory is read fresh from the environment each run, not
        pinned to whatever the first invocation happened to see."""
        other_tmpdir = self.tmp / "other-private-tmpdir"
        other_tmpdir.mkdir()
        session_a = f"test-{uuid.uuid4().hex[:12]}"
        session_b = f"test-{uuid.uuid4().hex[:12]}"

        self.run_hook("SessionStart", session_id=session_a, source="startup",
                     tmpdir=self.scratch_tmpdir)
        self.run_hook("SessionStart", session_id=session_b, source="startup",
                     tmpdir=other_tmpdir)

        self.assertTrue((self.scratch_tmpdir / f"claude-loop-{session_a}.json").is_file())
        self.assertTrue((other_tmpdir / f"claude-loop-{session_b}.json").is_file())
        # Cross-check: neither run's file leaked into the other run's directory.
        self.assertFalse((self.scratch_tmpdir / f"claude-loop-{session_b}.json").exists())
        self.assertFalse((other_tmpdir / f"claude-loop-{session_a}.json").exists())


# === Is it created with safe permissions? ==========================================

class FilePermissionsTest(AgentMonitorHookTestCase):

    def test_state_file_is_owner_read_write_only(self):
        result = self.run_hook("SessionStart", session_id=REAL_UUID_SESSION_ID,
                               source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        path = self.scratch_tmpdir / f"claude-loop-{REAL_UUID_SESSION_ID}.json"
        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(0o600, mode, f"expected 0o600, got {oct(mode)}")

    def test_state_file_is_not_group_or_world_readable(self):
        """Same fact as the exact-mode pin above, stated as the property that actually
        matters for the finding: no bit outside owner-rw survives."""
        result = self.run_hook("SessionStart", session_id=REAL_UUID_SESSION_ID,
                               source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        path = self.scratch_tmpdir / f"claude-loop-{REAL_UUID_SESSION_ID}.json"
        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(0, mode & (stat.S_IRWXG | stat.S_IRWXO),
                         f"group/other bits set: {oct(mode)}")
        self.assertTrue(mode & stat.S_IRUSR and mode & stat.S_IWUSR,
                        f"owner must still be able to read+write its own state: {oct(mode)}")


# === Does a malformed session_id stay contained? ===================================

class SessionIdTraversalGuardTest(AgentMonitorHookTestCase):
    """"/", "..", and an empty session_id must all resolve to the same one, fixed,
    safe filename inside the configured tmpdir -- never a path built from the raw
    value."""

    def assert_falls_back_inside_tmpdir(self, malformed_session_id):
        result = self.run_hook("SessionStart", session_id=malformed_session_id,
                               source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        expected = self.scratch_tmpdir / f"claude-loop-{AGENT_MONITOR.FALLBACK_SESSION_ID}.json"
        found = self.loop_state_files()
        self.assertEqual([expected], found,
                         f"expected exactly the fallback file, found {found}")
        self.assertEqual(self.scratch_tmpdir.resolve(), expected.parent.resolve())
        return result

    def test_a_slash_in_session_id_falls_back_inside_tmpdir(self):
        self.assert_falls_back_inside_tmpdir(SLASH_SESSION_ID)

    def test_a_parent_traversal_in_session_id_falls_back_inside_tmpdir(self):
        self.assert_falls_back_inside_tmpdir(TRAVERSAL_SESSION_ID)

    def test_an_empty_session_id_falls_back_inside_tmpdir(self):
        self.assert_falls_back_inside_tmpdir(EMPTY_SESSION_ID)

    def test_a_slash_in_session_id_keeps_the_log_directory_contained_too(self):
        """The same guard applies to ensure_dirs' mkdir under HOME -- not only to the
        loop-state file under TMPDIR. Pins that both call sites agree on one sanitized
        name rather than one being fixed and the other left on the raw value."""
        result = self.run_hook("SessionStart", session_id=SLASH_SESSION_ID, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        logs_dir = self.home / ".claude" / "logs"
        # Nothing besides the aggregated log files and the "sessions" dir may appear
        # directly under logs/ -- a traversal that escaped "sessions/" into its parent
        # would show up here as a stray "session" or similarly-named entry.
        top_level_dirs = sorted(p.name for p in logs_dir.iterdir() if p.is_dir())
        self.assertEqual(["sessions"], top_level_dirs, top_level_dirs)
        session_subdirs = sorted(p.name for p in self.sessions_dir().iterdir() if p.is_dir())
        self.assertEqual([AGENT_MONITOR.FALLBACK_SESSION_ID], session_subdirs, session_subdirs)


# === Do the real shapes still work unchanged? ======================================

class RealisticSessionIdsStillWorkTest(AgentMonitorHookTestCase):

    def test_a_real_uuid_is_used_unchanged_not_replaced_by_the_fallback(self):
        result = self.run_hook("SessionStart", session_id=REAL_UUID_SESSION_ID,
                               source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        expected = self.scratch_tmpdir / f"claude-loop-{REAL_UUID_SESSION_ID}.json"
        self.assertEqual([expected], self.loop_state_files())
        self.assertEqual([REAL_UUID_SESSION_ID],
                         sorted(p.name for p in self.sessions_dir().iterdir() if p.is_dir()))

    def test_the_literal_no_session_default_is_used_unchanged(self):
        """main() itself falls back to the literal "no-session" when the payload omits
        the key entirely -- that pre-existing default must survive this fix unchanged,
        not get swallowed by FALLBACK_SESSION_ID."""
        result = self.run_hook("SessionStart", source="startup")  # no session_id passed
        self.assertEqual(0, result.returncode, result.stderr)
        expected = self.scratch_tmpdir / f"claude-loop-{LITERAL_DEFAULT_SESSION_ID}.json"
        self.assertEqual([expected], self.loop_state_files())
        self.assertNotEqual(AGENT_MONITOR.FALLBACK_SESSION_ID, LITERAL_DEFAULT_SESSION_ID,
                            "fixture assumption: the two constants must differ, or this "
                            "test cannot tell the default apart from the fallback")


# === Does save_loop_state refuse to follow a planted symlink? (M1, security-master
# review of F10, 29.08.2026) ========================================================

class SaveLoopStateSymlinkGuardTest(AgentMonitorHookTestCase):
    """save_loop_state's os.open used O_TRUNC on an existing path without O_NOFOLLOW --
    O_TRUNC does not create a new inode, so a local user who pre-plants a symlink at the
    predictable claude-loop-<session_id>.json name gets that symlink's TARGET truncated
    and rewritten with this process's privileges. Not exploitable where TMPDIR is a
    private per-user directory (macOS default); exploitable on a Linux host falling back
    to a shared /tmp. "No exception" proves nothing here -- the canary's content is the
    only thing that can show the target was left alone."""

    def test_state_write_does_not_follow_a_planted_symlink_onto_a_canary_file(self):
        canary = self.tmp / "canary.txt"
        canary_content = "do-not-touch-me\n"
        canary.write_text(canary_content)

        session_id = f"test-{uuid.uuid4().hex[:12]}"
        state_path = self.scratch_tmpdir / f"claude-loop-{session_id}.json"
        state_path.symlink_to(canary)

        result = self.run_hook("SessionStart", session_id=session_id, source="startup")

        # The hook must never break a session (main()'s blanket except + exit(0)),
        # even when the write it attempted was refused because of the symlink.
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(canary_content, canary.read_text(),
                         "the planted symlink's target must not be truncated/rewritten")
        self.assertTrue(state_path.is_symlink(),
                         "the symlink itself must be left in place, not replaced")


# === Does a session-log write refuse a planted symlink too? (M2's own follow-up,
# 29.08.2026 -- M2 shipped owner-only permissions for session logs but explicitly left
# O_NOFOLLOW off open_owner_only, reasoning that planting a symlink under $HOME needs an
# attacker who already owns $HOME. That reasoning answers the threat-model question, not
# the robustness one: append_log does not just read, it appends JSON and then fchmod's
# the target to 0600 -- a STALE symlink (a backup tool, a sync tool, an earlier manual
# experiment) corrupts a file and silently changes its permissions with no attacker
# required at all.) =================================================================

class LogWriteSymlinkGuardTest(AgentMonitorHookTestCase):
    """Mirrors SaveLoopStateSymlinkGuardTest's shape (same canary-content-and-mode
    pattern) for the session activity log instead of the loop-state file."""

    def test_activity_log_write_does_not_follow_a_planted_symlink_onto_a_canary_file(self):
        canary = self.tmp / "canary.txt"
        canary_content = "do-not-touch-me\n"
        canary.write_text(canary_content)
        canary.chmod(0o644)

        session_dir = self.home / ".claude" / "logs" / "sessions" / REAL_UUID_SESSION_ID
        session_dir.mkdir(parents=True)
        activity_log = session_dir / "activity.jsonl"
        activity_log.symlink_to(canary)

        result = self.run_hook("SessionStart", session_id=REAL_UUID_SESSION_ID,
                               source="startup")

        # The hook must never break a session even when a write it attempted was
        # refused because of a symlink -- ELOOP is handled, not left to main()'s
        # blanket except.
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(canary_content, canary.read_text(),
                         "the planted symlink's target must not be appended to")
        self.assertEqual(0o644, stat.S_IMODE(canary.stat().st_mode),
                         "the planted symlink's target must not be fchmod'd either -- "
                         "'no exception raised' alone proves nothing here, the mode "
                         "change is half of the defect")
        self.assertTrue(activity_log.is_symlink(),
                         "the symlink itself must be left in place, not replaced")

    def test_the_aggregated_log_still_gets_written_when_only_the_session_log_is_symlinked(self):
        """The other half of the fix: append_log is called twice per event (session log,
        aggregated log -- see log_activity). A naked ELOOP propagating out of the first
        call would abort the second too, losing a write that had nothing to do with the
        symlinked path."""
        canary = self.tmp / "canary.txt"
        canary.write_text("do-not-touch-me\n")

        session_dir = self.home / ".claude" / "logs" / "sessions" / REAL_UUID_SESSION_ID
        session_dir.mkdir(parents=True)
        (session_dir / "activity.jsonl").symlink_to(canary)

        result = self.run_hook("SessionStart", session_id=REAL_UUID_SESSION_ID,
                               source="startup")

        self.assertEqual(0, result.returncode, result.stderr)
        aggregated = self.read_jsonl(self.home / ".claude" / "logs" / "activity.jsonl")
        self.assertTrue(any(e.get("event") == "SessionStart" for e in aggregated), aggregated)


# === Are session logs and their directories owner-only? (M2, security-master review
# of F10, 29.08.2026 -- PO decision: fix fully, dirs 0700 / files 0600, tighten
# pre-existing files on next write) =================================================

class LogFilePermissionsTest(AgentMonitorHookTestCase):
    """The loop-state file (M1's target) holds only counters. Session logs hold prompt
    text (UserPromptSubmit's prompt_preview), notification message text, and raw tool
    input -- all world-readable before this fix (dirs drwxr-xr-x, files -rw-r--r--)."""

    def test_new_log_files_are_0600_and_their_directories_are_0700(self):
        result = self.run_hook("SessionStart", session_id=REAL_UUID_SESSION_ID,
                               source="startup")
        self.assertEqual(0, result.returncode, result.stderr)

        logs_base = self.home / ".claude" / "logs"
        sessions_base = logs_base / "sessions"
        session_dir = sessions_base / REAL_UUID_SESSION_ID
        activity_log = session_dir / "activity.jsonl"

        for directory in (logs_base, sessions_base, session_dir):
            mode = stat.S_IMODE(directory.stat().st_mode)
            self.assertEqual(0o700, mode, f"{directory}: expected 0o700, got {oct(mode)}")

        mode = stat.S_IMODE(activity_log.stat().st_mode)
        self.assertEqual(0o600, mode, f"{activity_log}: expected 0o600, got {oct(mode)}")


class ExistingLogFileIsTightenedTest(AgentMonitorHookTestCase):
    """The PO decision's whole point: today's world-readable backlog is tightened on
    its NEXT write, not only on new sessions going forward."""

    def test_a_preexisting_0644_log_file_is_tightened_to_0600_on_next_write(self):
        session_dir = self.home / ".claude" / "logs" / "sessions" / REAL_UUID_SESSION_ID
        session_dir.mkdir(parents=True)
        activity_log = session_dir / "activity.jsonl"
        activity_log.write_text("")
        activity_log.chmod(0o644)
        self.assertEqual(0o644, stat.S_IMODE(activity_log.stat().st_mode),
                         "fixture sanity check")

        result = self.run_hook("SessionStart", session_id=REAL_UUID_SESSION_ID,
                               source="startup")
        self.assertEqual(0, result.returncode, result.stderr)

        mode = stat.S_IMODE(activity_log.stat().st_mode)
        self.assertEqual(0o600, mode,
                         f"pre-existing file must be tightened on next write, got {oct(mode)}")


class UmaskDoesNotDefeatModeTest(AgentMonitorHookTestCase):
    """A mode-bit test that only passes under the developer's own umask is not a real
    test: os.open/os.chmod requests here name absolute bits, but a naive
    Path.mkdir(mode=0o700) (or a plain open() with no explicit mode) would be silently
    narrowed -- or, for a plain open()'s 0o666 default, land on a completely different
    number -- depending on whatever umask happens to be active on the machine running
    the suite. Setting the subprocess's umask to 0o000, the most permissive possible,
    proves the 0700/0600 modes come from an explicit chmod/fchmod call rather than from
    a mode argument that only worked because nobody's umask ever cleared those bits."""

    def test_permissions_hold_even_under_a_permissive_umask(self):
        # os.umask() is process-wide state, not an env var -- inherited by the
        # subprocess via fork/exec, but it must be restored afterwards so it doesn't
        # leak into any other test in this process.
        old_umask = os.umask(0o000)
        try:
            result = self.run_hook("SessionStart", session_id=REAL_UUID_SESSION_ID,
                                   source="startup")
        finally:
            os.umask(old_umask)
        self.assertEqual(0, result.returncode, result.stderr)

        session_dir = self.home / ".claude" / "logs" / "sessions" / REAL_UUID_SESSION_ID
        activity_log = session_dir / "activity.jsonl"
        self.assertEqual(0o700, stat.S_IMODE(session_dir.stat().st_mode))
        self.assertEqual(0o600, stat.S_IMODE(activity_log.stat().st_mode))


# === Does the hook still never break a session? ====================================

class FailSafeContractTest(AgentMonitorHookTestCase):
    """Pins the pre-existing contract (main()'s blanket except + sys.exit(0)) so a
    later change to the session_id handling cannot quietly turn a malformed payload
    into a crash."""

    def test_non_json_stdin_exits_zero_and_writes_no_logs(self):
        result = self.run_hook("SessionStart", raw_stdin="not-json-at-all{{{")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.home / ".claude").exists(),
                         "a JSONDecodeError must exit before touching the filesystem")

    def test_empty_stdin_exits_zero_and_writes_no_logs(self):
        result = self.run_hook("SessionStart", raw_stdin="")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.home / ".claude").exists())

    def test_an_unknown_event_name_exits_zero_and_logs_it_as_activity_not_error(self):
        result = self.run_hook("SomeFutureEventType", session_id=REAL_UUID_SESSION_ID)
        self.assertEqual(0, result.returncode, result.stderr)
        activity = self.read_jsonl(self.sessions_dir() / REAL_UUID_SESSION_ID / "activity.jsonl")
        self.assertTrue(
            any(e.get("event") == "Unknown:SomeFutureEventType" for e in activity),
            activity)
        errors_log = self.sessions_dir() / REAL_UUID_SESSION_ID / "errors.jsonl"
        self.assertEqual([], self.read_jsonl(errors_log),
                         "an unrecognised (not malformed) event name is not an error")


# === Does anything ever TRIGGER the log cleanup? (#27, 30.08.2026) =================
#
# scripts/log-cleanup.sh implements a 7-day retention policy correctly and nothing
# called it: no hook, no cron entry, no settings line. Measured on 30.08.2026, the
# first run ever took 285 session directories down to 23 and 144 MB down to 24 MB.
# The defect is not the accumulated rubbish -- it is that "the cleanup ran and found
# nothing" and "the cleanup never ran" looked identical from the outside.
#
# The trigger is a once-per-day-throttled call from handle_session_start (PO decision
# 30.08.2026: the only trigger that needs no installation step on the adopter's
# machine). The throttle is a date stamp under ~/.claude/logs, and BOTH of its sides
# are pinned below -- a test that only proves "the first start runs it" survives every
# broken throttle there is.


class LogCleanupTriggerTest(AgentMonitorHookTestCase):

    def test_a_first_session_start_runs_the_log_cleanup(self):
        self.install_cleanup_stub()
        result = self.run_hook("SessionStart", session_id=self.session_id,
                               source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, self.cleanup_invocation_count(),
                         f"stderr was: {result.stderr}")
        self.assertEqual(self.today_stamp(),
                         self.cleanup_stamp_path().read_text(encoding="utf-8").strip())

    def test_a_session_start_without_the_script_installed_runs_nothing_and_still_succeeds(self):
        """No stub planted: the hook must not invent a run, and must not fail the
        session start over a missing script either."""
        result = self.run_hook("SessionStart", session_id=self.session_id,
                               source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0, self.cleanup_invocation_count())
        events = self.activity_events(self.session_id, "LogCleanup")
        self.assertEqual(1, len(events), events)
        self.assertFalse(events[0]["ran"], events[0])
        self.assertEqual("script-not-found", events[0]["reason"], events[0])


class LogCleanupThrottleTest(AgentMonitorHookTestCase):
    """Both sides of the once-per-day throttle. Structure, not presence: a throttle
    that never fires and a throttle that never releases are each caught by exactly one
    of these two tests, and neither test alone can see the other's failure."""

    def test_a_second_session_start_on_the_same_day_does_not_run_it_again(self):
        self.install_cleanup_stub()
        first = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(1, self.cleanup_invocation_count(), first.stderr)

        second = self.run_hook("SessionStart", session_id=self.session_id, source="resume")
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(1, self.cleanup_invocation_count(),
                         "the second start on the same day must not run the cleanup again")

    def test_a_third_session_start_on_the_same_day_from_a_different_session_is_throttled_too(self):
        """The stamp is per machine, not per session: a fresh session_id must not
        re-arm the throttle."""
        self.install_cleanup_stub()
        self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.run_hook("SessionStart", session_id=f"other-{uuid.uuid4().hex[:8]}",
                      source="startup")
        self.assertEqual(1, self.cleanup_invocation_count())

    def test_a_second_same_day_start_does_not_re_log_a_missing_script(self):
        """The script-not-found notice sits behind the same stamp as a real run, so it
        cannot turn into a per-session-start nag. No stub is installed here."""
        first = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(1, len(self.activity_events(self.session_id, "LogCleanup")),
                         first.stderr)
        second_id = f"second-{uuid.uuid4().hex[:8]}"
        self.run_hook("SessionStart", session_id=second_id, source="resume")
        self.assertEqual([], self.activity_events(second_id, "LogCleanup"))

    def test_a_session_start_on_a_later_day_runs_it_again(self):
        self.install_cleanup_stub()
        yesterday = (datetime.datetime.now(datetime.timezone.utc)
                     - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        self.write_stamp(yesterday + "\n")

        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, self.cleanup_invocation_count(),
                         "a stamp from a previous day must release the throttle")
        self.assertEqual(self.today_stamp(),
                         self.cleanup_stamp_path().read_text(encoding="utf-8").strip())


class LogCleanupStampFailureModesTest(AgentMonitorHookTestCase):
    """A stamp that is missing, unreadable, or garbage must fail OPEN -- run the
    cleanup and repair the stamp -- and must never fail the session start. A throttle
    file is a convenience; it must not become a way to switch the cleanup off forever."""

    def test_a_missing_stamp_runs_the_cleanup(self):
        self.install_cleanup_stub()
        self.assertFalse(self.cleanup_stamp_path().exists(), "fixture sanity check")
        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, self.cleanup_invocation_count())

    def test_an_unreadable_stamp_runs_the_cleanup_and_is_replaced(self):
        # House idiom, from test_artifact_gate.py's UnreadableFileTest: root ignores
        # the mode bits, so under root this fixture is not "unreadable" at all -- the
        # stamp would read back as today's date and the assertions below would measure
        # the throttle instead of the failure mode they name.
        if os.geteuid() == 0:
            self.skipTest("root reads every file regardless of mode")
        self.install_cleanup_stub()
        stamp = self.write_stamp(self.today_stamp() + "\n")
        stamp.chmod(0o000)
        self.addCleanup(lambda: stamp.exists() and stamp.chmod(0o600))

        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, self.cleanup_invocation_count(),
                         "an unreadable stamp must not silence the cleanup for good")
        self.assertEqual(self.today_stamp(),
                         self.cleanup_stamp_path().read_text(encoding="utf-8").strip())

    def test_a_garbage_stamp_runs_the_cleanup_and_is_replaced(self):
        """Undecodable bytes, not merely a wrong-looking string: a plain read_text
        raises UnicodeDecodeError on these, and an uncaught one would be swallowed by
        the outer guard, leaving the cleanup silently skipped -- which is the exact
        state this fix exists to remove."""
        self.install_cleanup_stub()
        stamp = self.cleanup_stamp_path()
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_bytes(b"\xff\xfe not a date at all\nsecond line\n")

        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, self.cleanup_invocation_count())
        self.assertEqual(self.today_stamp(),
                         self.cleanup_stamp_path().read_text(encoding="utf-8").strip())

    def test_a_stamp_that_is_a_directory_does_not_fail_the_session_start(self):
        """The one shape that cannot be repaired by an atomic replace. It must degrade
        to "no cleanup this time", never to a broken session start."""
        self.install_cleanup_stub()
        stamp = self.cleanup_stamp_path()
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.mkdir()

        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(stamp.is_dir(), "the obstruction is left as found, not deleted")
        activity = self.activity_events(self.session_id, "SessionStart")
        self.assertEqual(1, len(activity),
                         "the rest of SessionStart must still have happened")
        # ...and it must SAY it could not run. Degrading to silence here would put the
        # mechanism straight back into the state this fix exists to leave behind.
        errors = self.error_events(self.session_id, "LogCleanup")
        self.assertEqual(1, len(errors), errors)
        self.assertEqual("stamp-unwritable", errors[0]["reason"], errors[0])
        self.assertEqual(0, self.cleanup_invocation_count(),
                         "a cleanup that cannot be throttled must not run unthrottled")


class LogCleanupStampDirectoryPermissionsTest(AgentMonitorHookTestCase):
    """~/.claude/logs holds prompt text and tool input and is 0700 by contract
    (ensure_dirs). write_log_cleanup_stamp creates that directory too, so it owes the
    same chmod -- Path.mkdir's mode argument is silently narrowed by the umask and is
    ignored outright for a directory that already exists, which is why ensure_dirs
    chmods on every call rather than trusting mkdir once.

    Driven in-process on purpose: through SessionStart the directory is always created
    by log_activity first, so the end-to-end path cannot distinguish a correct chmod
    here from a missing one. Called on its own, it can.
    """

    def test_the_logs_directory_is_owner_only_when_the_stamp_creates_it(self):
        old_umask = os.umask(0o022)   # the stock umask a missing chmod hides behind
        try:
            with module_with_home(self.home) as module:
                self.assertTrue(module.write_log_cleanup_stamp("2026-03-01"))
        finally:
            os.umask(old_umask)

        logs = self.home / ".claude" / "logs"
        self.assertEqual(0o700, stat.S_IMODE(logs.stat().st_mode),
                         f"expected 0o700, got {oct(stat.S_IMODE(logs.stat().st_mode))}")
        self.assertEqual(0o600, stat.S_IMODE(
            (logs / ".log-cleanup-last-run").stat().st_mode))


class LogCleanupVisibilityTest(AgentMonitorHookTestCase):
    """The PO's condition, verbatim: "the run must be visible. A cleanup that silently
    does nothing has the same problem as before." A run that removed nothing and a run
    that never happened must be told apart from the outside."""

    def test_a_run_that_removed_something_reports_what_it_removed(self):
        self.install_cleanup_stub(CLEANUP_STUB_REMOVED_SOMETHING)
        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)

        events = self.activity_events(self.session_id, "LogCleanup")
        self.assertEqual(1, len(events), events)
        event = events[0]
        self.assertTrue(event["ran"], event)
        self.assertEqual(0, event["exit_code"], event)
        self.assertEqual(4, event["sessions_removed"], event)
        self.assertEqual(19, event["sessions_kept"], event)
        self.assertEqual(60, event["lines_removed"], event)
        # The rendered clause, not a bare "4" -- that would also be satisfied by a
        # duration like "0.4 s" and would pass on a report of the wrong number.
        self.assertIn("4 session dir(s) removed, 19 kept", result.stderr)
        self.assertIn("60 log line(s) trimmed", result.stderr)

    def test_a_run_that_found_nothing_is_still_reported_as_a_run(self):
        self.install_cleanup_stub(CLEANUP_STUB_FOUND_NOTHING)
        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)

        events = self.activity_events(self.session_id, "LogCleanup")
        self.assertEqual(1, len(events), events)
        event = events[0]
        self.assertTrue(event["ran"], event)
        self.assertEqual(0, event["sessions_removed"], event)
        self.assertEqual(23, event["sessions_kept"], event)
        self.assertEqual(0, event["lines_removed"], event)
        self.assertIn("log cleanup", result.stderr)

    def test_a_run_that_did_not_happen_leaves_no_run_record(self):
        """The discriminator the two tests above are worth nothing without: the
        THROTTLED start must not produce the same record as a no-op run."""
        self.install_cleanup_stub(CLEANUP_STUB_FOUND_NOTHING)
        self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(1, len(self.activity_events(self.session_id, "LogCleanup")))

        second_id = f"second-{uuid.uuid4().hex[:8]}"
        second = self.run_hook("SessionStart", session_id=second_id, source="resume")
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual([], self.activity_events(second_id, "LogCleanup"),
                         "a throttled start must be distinguishable from a run that "
                         "found nothing -- no LogCleanup record at all")
        self.assertEqual(1, len(self.activity_events(second_id, "SessionStart")),
                         "...while the start itself is still recorded as usual")

    def test_an_unparseable_summary_is_still_reported_as_a_run(self):
        """The script's summary block is plain text, not a machine interface. If it
        ever changes shape, the hook must report "ran, could not read the numbers" --
        not fall back to silence, which is the very state this fix removes."""
        self.install_cleanup_stub('echo "cleanup done, no numbers here"\n')
        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)

        events = self.activity_events(self.session_id, "LogCleanup")
        self.assertEqual(1, len(events), events)
        self.assertTrue(events[0]["ran"], events[0])
        self.assertIsNone(events[0]["sessions_removed"], events[0])
        self.assertIn("log cleanup", result.stderr)

    def test_a_failing_cleanup_script_is_reported_as_an_error_and_the_session_survives(self):
        self.install_cleanup_stub('echo "boom" >&2\nexit 3\n')
        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode,
                         "a failing cleanup must never fail the session start")

        errors = self.error_events(self.session_id, "LogCleanup")
        self.assertEqual(1, len(errors), errors)
        self.assertEqual(3, errors[0]["exit_code"], errors[0])
        self.assertEqual(1, len(self.activity_events(self.session_id, "SessionStart")),
                         "the rest of SessionStart must still have happened")


class LogCleanupTimeoutTest(AgentMonitorHookTestCase):
    """The timeout is the one thing the subprocess entry point cannot show: it is a
    production constant in the tens of seconds. Injected as an argument here -- the
    same treatment the throttle gives the clock -- and driven in-process. Documented
    exception to this file's subprocess-only rule; see module_with_home."""

    def test_a_hanging_cleanup_script_is_abandoned_and_reported(self):
        self.install_cleanup_stub("sleep 30\n")
        session = "timeout-session"
        with module_with_home(self.home) as module:
            started = time.time()
            module.maybe_run_log_cleanup(session, timeout=0.5)
            elapsed = time.time() - started

        self.assertLess(elapsed, 10, "the hook waited for the full sleep")
        errors = self.error_events(session, "LogCleanup")
        self.assertEqual(1, len(errors), errors)
        self.assertEqual("timeout", errors[0]["reason"], errors[0])
        self.assertEqual(self.today_stamp(),
                         self.cleanup_stamp_path().read_text(encoding="utf-8").strip(),
                         "a hanging script must not be retried on every session start")

    def test_the_shipped_timeout_is_generous_enough_for_a_real_run(self):
        """Measured 30.08.2026: a dry run over 24 session directories took 0.43 s, and
        the real first run (285 directories, 144 MB) completed well inside a second.
        The shipped ceiling exists to bound a pathological case, not to cut short a
        normal one."""
        with module_with_home(self.home) as module:
            self.assertGreaterEqual(module.LOG_CLEANUP_TIMEOUT_S, 30)


class LogCleanupClockTest(AgentMonitorHookTestCase):
    """The throttle's day boundary is an injected input, not the wall clock. Same
    pattern as scripts/lib/workitems/sweep.py's `clock` parameter, and for the same
    reason: a daily throttle that can only be tested by waiting for midnight is not
    tested at all."""

    def test_the_stamp_is_the_utc_date_of_the_injected_clock(self):
        self.install_cleanup_stub()
        fixed = datetime.datetime(2026, 3, 1, 12, 0, tzinfo=datetime.timezone.utc)
        with module_with_home(self.home) as module:
            module.maybe_run_log_cleanup("clock-session", clock=lambda: fixed)
        self.assertEqual("2026-03-01",
                         self.cleanup_stamp_path().read_text(encoding="utf-8").strip())
        self.assertEqual(1, self.cleanup_invocation_count())

    def test_a_non_utc_clock_is_normalised_before_the_date_is_taken(self):
        """23:30 on 01.03. in a +02:00 zone is 21:30 UTC on the SAME day; 01:30 on
        02.03. in that zone is 23:30 UTC on the 1st. Taking the local date would put
        those two starts on different days and run the cleanup twice."""
        self.install_cleanup_stub()
        plus_two = datetime.timezone(datetime.timedelta(hours=2))
        late = datetime.datetime(2026, 3, 2, 1, 30, tzinfo=plus_two)
        with module_with_home(self.home) as module:
            module.maybe_run_log_cleanup("tz-session", clock=lambda: late)
        self.assertEqual("2026-03-01",
                         self.cleanup_stamp_path().read_text(encoding="utf-8").strip())


# === Are orphaned loop-state files ever cleaned up? (#25, 30.08.2026) =============
#
# cleanup_loop_state() is correct and was called from exactly one place:
# handle_session_end. Any termination that does not raise SessionEnd -- a killed
# process, a crash, possibly some compact/restart paths -- leaves its state file in
# TMPDIR forever. Measured live on 30.08.2026: two files from 10:00 still sitting
# there while their sessions were long gone. The content is harmless (counters and
# hashes, 0600, in the user's own TMPDIR) -- this is litter, not disclosure -- so the
# fix is an age-based sweep at session start, not a stricter SessionEnd.


class StaleLoopStateSweepTest(AgentMonitorHookTestCase):

    def test_a_state_file_left_behind_without_a_session_end_is_swept_at_the_next_start(self):
        """The red proof for #25, in the shape the defect actually takes: a session
        starts, writes its state, and never reaches SessionEnd."""
        abandoned_id = f"abandoned-{uuid.uuid4().hex[:8]}"
        first = self.run_hook("SessionStart", session_id=abandoned_id, source="startup")
        self.assertEqual(0, first.returncode, first.stderr)
        abandoned = self.scratch_tmpdir / f"claude-loop-{abandoned_id}.json"
        self.assertTrue(abandoned.is_file(), "fixture sanity check: the file exists")

        # No SessionEnd. Age it past the sweep threshold and start the next session.
        old = time.time() - 3 * 24 * 3600
        os.utime(abandoned, (old, old))

        second_id = f"next-{uuid.uuid4().hex[:8]}"
        second = self.run_hook("SessionStart", session_id=second_id, source="startup")
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertFalse(abandoned.exists(), "the orphan survived the next session start")
        self.assertTrue((self.scratch_tmpdir / f"claude-loop-{second_id}.json").is_file(),
                        "...and the new session's own state file must still be there")

    def test_a_recent_foreign_state_file_survives_the_sweep(self):
        """Age-based, not "delete everything that is not mine": a concurrently running
        second session must keep its counters."""
        recent = self.plant_loop_state_file("claude-loop-concurrent.json", age_s=3600)
        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(recent.is_file(),
                        "an hour-old state file belongs to a live session")

    def test_a_file_exactly_at_the_threshold_is_kept_and_one_past_it_is_swept(self):
        """The boundary itself, from both sides -- an off-by-one in either direction
        shows up here and nowhere else."""
        with module_with_home(self.home) as module:
            max_age = module.LOOP_STATE_MAX_AGE_S
        keep = self.plant_loop_state_file("claude-loop-at-threshold.json",
                                          age_s=max_age - 60)
        sweep = self.plant_loop_state_file("claude-loop-past-threshold.json",
                                           age_s=max_age + 60)

        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(keep.is_file(), "a file just inside the window must be kept")
        self.assertFalse(sweep.exists(), "a file just outside the window must go")

    def test_unrelated_files_in_the_temp_directory_are_left_alone(self):
        """The sweep is bounded by the claude-loop-*.json name, not by "old files in
        TMPDIR" -- TMPDIR is shared with everything else the user runs."""
        stranger = self.scratch_tmpdir / "some-other-tool.json"
        stranger.write_text("{}", encoding="utf-8")
        old = time.time() - 30 * 24 * 3600
        os.utime(stranger, (old, old))

        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(stranger.is_file(), "a foreign file must not be touched")

    def test_a_stale_symlink_is_removed_without_following_it(self):
        """A symlink planted at the predictable name must be judged and removed by its
        OWN age -- lstat, not stat -- and its target must survive untouched. "No
        exception raised" proves nothing here; the canary's content does."""
        canary = self.tmp / "sweep-canary.txt"
        canary_content = "do-not-touch-me\n"
        canary.write_text(canary_content, encoding="utf-8")

        link = self.scratch_tmpdir / "claude-loop-symlinked.json"
        link.symlink_to(canary)
        old = time.time() - 5 * 24 * 3600
        os.utime(link, (old, old), follow_symlinks=False)

        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(link.is_symlink(), "the stale symlink itself must be removed")
        self.assertTrue(canary.is_file(), "the target must not be deleted")
        self.assertEqual(canary_content, canary.read_text(encoding="utf-8"))

    def test_a_directory_at_a_state_file_name_does_not_fail_the_session_start(self):
        """An unremovable entry must cost the sweep that one entry, not the session
        start -- and not the rest of the sweep either."""
        obstruction = self.scratch_tmpdir / "claude-loop-obstruction.json"
        obstruction.mkdir()
        old = time.time() - 5 * 24 * 3600
        os.utime(obstruction, (old, old))
        sweepable = self.plant_loop_state_file("claude-loop-sweepable.json",
                                               age_s=5 * 24 * 3600)

        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(obstruction.is_dir(), "left as found")
        self.assertFalse(sweepable.exists(),
                         "one unremovable entry must not abort the whole sweep")
        self.assertEqual(1, len(self.activity_events(self.session_id, "SessionStart")))

    def test_the_sweep_is_reported_when_it_removed_something(self):
        """Same visibility rule as the log cleanup: a sweep that removed files says so,
        and a sweep with nothing to do stays quiet rather than logging a non-event."""
        self.plant_loop_state_file("claude-loop-orphan-a.json", age_s=5 * 24 * 3600)
        self.plant_loop_state_file("claude-loop-orphan-b.json", age_s=5 * 24 * 3600)

        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        events = self.activity_events(self.session_id, "StaleLoopStateSwept")
        self.assertEqual(1, len(events), events)
        self.assertEqual(2, events[0]["removed"], events[0])

    def test_a_sweep_with_nothing_to_remove_logs_no_event(self):
        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.activity_events(self.session_id, "StaleLoopStateSwept"))
        self.assertEqual(1, len(self.activity_events(self.session_id, "SessionStart")),
                         "...but the start itself is still recorded")

    def test_a_partial_sweep_still_reports_what_it_already_removed(self):
        """An unexpected (non-OSError) failure part-way through must not swallow the
        record of the files already deleted. Code review finding, 30.08.2026: the
        function returned early from its `except Exception`, which sits BEFORE the
        reporting block -- so a partial sweep was indistinguishable from a sweep that
        found nothing, the exact confusion this change exists to end.

        In-process with fault injection, because no hook payload can make os.unlink
        raise something other than OSError. `tmpdir=` is mandatory here: this code
        path DELETES files, and tempfile's cached tempdir would otherwise point at the
        developer's real temp directory.
        """
        first = self.plant_loop_state_file("claude-loop-aaa-removable.json",
                                           age_s=5 * 24 * 3600)
        second = self.plant_loop_state_file("claude-loop-bbb-explodes.json",
                                            age_s=5 * 24 * 3600)

        real_unlink = os.unlink

        def exploding_unlink(path, *args, **kwargs):
            if str(path).endswith("claude-loop-bbb-explodes.json"):
                raise RuntimeError("injected non-OSError failure mid-sweep")
            return real_unlink(path, *args, **kwargs)

        with module_with_home(self.home, tmpdir=self.scratch_tmpdir) as module:
            # Guard before anything destructive runs: if the module resolved a
            # different temp directory, this test would be deleting real files.
            self.assertEqual(str(self.scratch_tmpdir), tempfile.gettempdir(),
                             "refusing to run a deleting sweep outside the fixture")
            os.unlink = exploding_unlink
            try:
                removed = module.sweep_stale_loop_state("partial-sweep-session")
            finally:
                os.unlink = real_unlink

        self.assertEqual(1, removed)
        self.assertFalse(first.exists(), "the first file was removed")
        self.assertTrue(second.exists(), "the injected failure stopped the second")
        events = self.activity_events("partial-sweep-session", "StaleLoopStateSwept")
        self.assertEqual(1, len(events),
                         "a partial sweep must still report what it removed")
        self.assertEqual(1, events[0]["removed"], events[0])

    def test_the_sweep_is_not_throttled_by_the_log_cleanup_stamp(self):
        """The two mechanisms share a trigger point, not a throttle. The sweep costs a
        glob, so gating it on the daily stamp would let an orphan outlive its session
        by up to a day for no gain."""
        self.write_stamp(self.today_stamp() + "\n")   # log cleanup already ran today
        orphan = self.plant_loop_state_file("claude-loop-orphan.json", age_s=5 * 24 * 3600)

        result = self.run_hook("SessionStart", session_id=self.session_id, source="startup")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(orphan.exists(),
                         "the sweep must run even on a start where the cleanup is throttled")


if __name__ == "__main__":
    unittest.main()
