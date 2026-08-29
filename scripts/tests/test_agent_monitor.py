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
"""

import importlib.util
import json
import os
import stat
import subprocess
import tempfile
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


if __name__ == "__main__":
    unittest.main()
