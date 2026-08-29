#!/usr/bin/env python3
"""
Agent Monitor – Central monitoring script for Claude Code hooks.

Processes all hook events and provides:
1. Activity logging (who does what when)
2. Loop detection (detect and block infinite loops)
3. Error logging (tool errors, subagent crashes)
4. Performance tracking (duration per agent/command)

Log files:
- ~/.claude/logs/sessions/{session_id}/activity.jsonl
- ~/.claude/logs/sessions/{session_id}/errors.jsonl
- ~/.claude/logs/sessions/{session_id}/performance.jsonl
- ~/.claude/logs/activity.jsonl          (aggregated, rotated at 10MB)
- ~/.claude/logs/errors.jsonl            (aggregated, rotated at 10MB)
- ~/.claude/logs/performance.jsonl       (aggregated, rotated at 10MB)

Loop state:
- {tempfile.gettempdir()}/claude-loop-{session_id}.json (honours TMPDIR; on macOS this is
  a private, mode-700 per-user directory, not the shared /tmp)

session_id is hook-supplied, unvalidated input (see sanitize_session_id below): every path
built from it -- the session log directory and the loop-state file -- goes through that one
function first, so a value shaped like a path (a "/" or ".." component) cannot relocate
either.
"""

import errno
import json
import re
import sys
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# === Configuration ===

LOG_BASE = Path.home() / ".claude" / "logs"
SESSION_LOG_BASE = LOG_BASE / "sessions"
MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Loop detection thresholds
LOOP_WARN_THRESHOLD = 3       # Same call 3x -> Warning
LOOP_BLOCK_THRESHOLD = 5      # Same call 5x -> Block
TOTAL_TOOLS_WARN = 200        # Total tool calls -> Warning
TOTAL_TOOLS_CRITICAL = 500    # Total tool calls -> Critical
AGENT_DURATION_WARN_S = 600   # 10 minutes -> Slow agent warning
EISDIR_WARN_THRESHOLD = 3     # 3x EISDIR -> Pattern warning

# Duplicate batch detection
DUPLICATE_BATCH_WINDOW_S = 1800   # 30 min lookback for batch comparison
BATCH_GROUP_WINDOW_S = 30         # Agents within 30s = one batch
STALE_TOOL_THRESHOLD_S = 3600     # tool_starts > 1h clean up

# Strategic compact & handover (3-level reminder)
COMPACT_HINT_THRESHOLD = 75        # After 75 tool calls -> soft hint
COMPACT_REMINDER_THRESHOLD = 90    # After 90 tool calls -> compact reminder
COMPACT_URGENT_THRESHOLD = 100     # After 100 tool calls -> urgent reminder
TOKEN_BUDGET_WARNING = 150         # After 150 tool calls -> update HANDOVER.md
STAGNATION_TOOLS = {"Write", "Edit"}  # Tools counted as "productive"
STAGNATION_WINDOW_S = 900         # 15 min without Write/Edit -> stagnation warning

# HANDOVER staleness check (run on SubagentStop / Stop)
HANDOVER_STALENESS_TOLERANCE_S = 60  # docs/HANDOVER.md may lag this much behind newest docs/*.md

# HANDOVER size cap check (run on SessionStart / PostToolUse of a HANDOVER write)
HANDOVER_DEFAULT_CAP_BYTES = 5 * 1024   # templates/HANDOVER_TEMPLATE.md default (KB = 1024 B)
HANDOVER_DEFAULT_CAP_LINES = 150        # ...and its line dimension
HANDOVER_CAP_HEADER_LINES = 20          # only the header may declare a per-file cap
# Warn at 80 % of the cap, not at 100 %. Measured in this repo on 18.08.2026: one skill run
# grew docs/HANDOVER.md by 1021 B, i.e. ~20 % of the 5 KB cap. A threshold one run's growth
# below the cap is therefore the last moment at which a warning is still preventive — at any
# higher value the very next run breaches the cap without ever having been announced.
HANDOVER_WARN_PCT = 80
# Tools that can change the file's size. A Read does not, so it must not trigger a re-check.
HANDOVER_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Token tracking (approximate values)
CHARS_PER_TOKEN = 4               # Rough average for DE/EN text
SYSTEM_PROMPT_ESTIMATE = 8000     # Estimated tokens for CLAUDE.md + system context
TOKEN_RESULT_ESTIMATES = {        # Estimated output tokens per tool (median)
    "Read": 2000,
    "Grep": 500,
    "Glob": 300,
    "Bash": 500,
    "Edit": 200,
    "Write": 200,
    "Agent": 3000,
    "Skill": 1000,
    "default": 300,
}
TOKEN_LOG_INTERVAL = 25           # Log token status every N tool calls


# === Helper functions ===

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# A hook-supplied session_id is untrusted input (it comes from the harness over stdin, not
# from this process), and it is used as a filesystem path component in several places below.
# Only the shapes actually seen are accepted: a UUID4 ("0a954ab5-388e-4954-b5d5-9a037cb0e981")
# and the literal "no-session" (main()'s own fallback for a payload missing the key) both
# match [A-Za-z0-9_-]+ with no path separators and no dots. Anything else -- containing "/"
# or ".." (both of which pathlib and the OS can turn into a real directory traversal once
# concatenated into a larger path, e.g. SESSION_LOG_BASE / "../evil"), or empty, or not a
# string at all -- falls back to FALLBACK_SESSION_ID rather than raising: the hook's contract
# (main()'s blanket except + sys.exit(0)) is that a check must never break a session, and a
# validator that raises one function away from that guard is not validation, it is a crash
# the guard happens to catch.
SAFE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
FALLBACK_SESSION_ID = "invalid-session"


def sanitize_session_id(session_id) -> str:
    """Returns session_id unchanged if it is safe to use as a path component, else the
    fixed fallback. Never raises."""
    if isinstance(session_id, str) and SAFE_SESSION_ID_RE.match(session_id):
        return session_id
    return FALLBACK_SESSION_ID


def session_log_dir(session_id: str) -> Path:
    """The per-session log directory, with session_id sanitized first.

    Single source of truth for turning a hook-supplied session_id into a path component
    under SESSION_LOG_BASE. Every call site that used to build SESSION_LOG_BASE / session_id
    directly (ensure_dirs' mkdir, the three log_* functions' file paths, and the SessionEnd
    summary path) now goes through here -- sanitizing only inside ensure_dirs while leaving
    those other call sites on the raw value would create a directory under the safe name and
    then try to write the log file at a different, unsafe path, which is not a fix, only a
    mismatch.
    """
    return SESSION_LOG_BASE / sanitize_session_id(session_id)


def ensure_dirs(session_id: str):
    """Creates all required log directories, owner-only (0o700).

    Session logs carry prompt text, notification messages, and raw tool input (see the
    module docstring's Log files list) -- a local user should not be able to read
    another user's session, the same argument the loop-state file's 0o600 already
    applies to its counters-only content, applied here to content that matters more.

    mkdir(mode=...) is masked by the umask, AND Path.mkdir(parents=True) does not
    propagate the requested mode to any intermediate directory it creates along the
    way -- cpython's own implementation recurses into `self.parent.mkdir(parents=True,
    exist_ok=True)` without forwarding `mode` at all, so an intermediate dir gets
    pathlib's own default (0o777, masked by umask) regardless of what was asked for the
    leaf. Verified empirically: creating SESSION_LOG_BASE/<id> in one call under a
    stock 022 umask left LOG_BASE (an auto-created parent) at 0o755, not 0o700 --
    see docs/memory/senior-developer/session-permission-hardening.md.

    The fix is to never trust mkdir's mode argument and chmod every directory in the
    chain explicitly, on every call -- not only the leaf, and not only when the
    directory is freshly created (Path.mkdir(exist_ok=True) silently ignores `mode`
    for a directory that already exists). Re-chmod'ing on every call also tightens a
    directory that predates this fix (PO decision 29.08.2026: the existing backlog is
    fixed on its next write, not only for new sessions going forward).
    """
    session_dir = session_log_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    LOG_BASE.mkdir(parents=True, exist_ok=True)
    for directory in (LOG_BASE, SESSION_LOG_BASE, session_dir):
        os.chmod(directory, 0o700)


def rotate_if_needed(filepath: Path):
    """Rotates log file if it exceeds MAX_LOG_SIZE_BYTES."""
    if not filepath.exists():
        return
    if filepath.stat().st_size < MAX_LOG_SIZE_BYTES:
        return

    # Find next available rotation number
    i = 1
    while True:
        rotated = filepath.with_suffix(f".{i}{filepath.suffix}")
        if not rotated.exists():
            break
        i += 1
    filepath.rename(rotated)


def open_owner_only(path: Path, flags: int) -> int:
    """Opens path with O_CREAT at owner-only mode (0o600), re-asserting that mode via
    fchmod so a file that already existed -- created before this fix shipped, or by
    something else -- is tightened on THIS write rather than trusted (mirrors
    save_loop_state's long-standing os.open + os.fchmod shape; PO decision 29.08.2026
    extends the same "tighten on next write" discipline from the loop-state file to
    the session logs, whose content -- prompt text, tool input -- matters more).

    Callers wrap the returned fd in os.fdopen and close it via that context manager.
    Do not add a second os.close after fdopen has taken ownership of the fd -- this
    exact shape hit a double-close bug once already (fdopen's __exit__ closing an fd
    os.close had already closed, on the error path), see
    docs/memory/senior-developer/session-id-path-hardening.md.

    O_NOFOLLOW here too (M2 follow-up, 29.08.2026 -- corrects the shipped M2 rationale,
    which argued this from the threat-model axis only: planting a symlink under $HOME
    needs an attacker who already owns $HOME, so the indirection crosses no privilege
    boundary M1's fix exists to close. That argument is not wrong, but this call is not
    a read -- it appends JSON and then fchmod's the target to 0600, and THAT needs no
    attacker at all: a stale symlink left behind by a backup tool, a sync tool, or an
    earlier manual experiment is enough to get silently corrupted and have its
    permissions changed. It is a robustness argument, not a threat-model one, and holds
    regardless of who can write to $HOME. It also does not cost the legitimate case:
    O_NOFOLLOW rejects only a symlinked FINAL path component, so a symlinked log
    DIRECTORY (e.g. ~/.claude/logs -> /elsewhere) still works -- only symlinking an
    individual .jsonl file fails, which nobody sets up on purpose. When the target IS a
    symlink, os.open raises OSError (ELOOP); append_log (the sole caller) catches that
    specifically and reports to stderr instead of letting it propagate, because this
    helper is invoked twice per event (session log, then the aggregated log) and an
    uncaught raise here would abort the second, unrelated write along with the first.
    """
    fd = os.open(path, flags | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        os.close(fd)
        raise
    return fd


def append_log(filepath: Path, entry: dict):
    """Writes a log entry as a JSON line, owner-only (0o600, tightened on every write).

    ELOOP (open_owner_only's O_NOFOLLOW rejecting a symlinked filepath) is caught HERE,
    not left to main()'s blanket except: each log_* function calls this twice (session
    log, then the aggregated log), so a raise on the first call would silently lose the
    second, unrelated write too. Reported to stderr -- this file's existing idiom for a
    non-blocking diagnostic (see e.g. the HANDOVER-size warning above) -- rather than
    via log_error, which itself calls append_log and could recurse into the very path
    that just failed.
    """
    rotate_if_needed(filepath)
    try:
        fd = open_owner_only(filepath, os.O_WRONLY | os.O_APPEND)
    except OSError as e:
        if e.errno != errno.ELOOP:
            raise
        print(f"agent-monitor: refusing to write through a symlink at {filepath}: {e}",
              file=sys.stderr)
        return
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_activity(session_id: str, entry: dict):
    """Logs to session log and aggregated log."""
    ensure_dirs(session_id)
    append_log(session_log_dir(session_id) / "activity.jsonl", entry)
    append_log(LOG_BASE / "activity.jsonl", entry)


def log_error(session_id: str, entry: dict):
    """Logs errors to session log and aggregated log."""
    ensure_dirs(session_id)
    append_log(session_log_dir(session_id) / "errors.jsonl", entry)
    append_log(LOG_BASE / "errors.jsonl", entry)


def log_performance(session_id: str, entry: dict):
    """Logs performance data to session log and aggregated log."""
    ensure_dirs(session_id)
    append_log(session_log_dir(session_id) / "performance.jsonl", entry)
    append_log(LOG_BASE / "performance.jsonl", entry)


# === Loop detection state ===

def get_loop_state_path(session_id: str) -> Path:
    """The per-session loop-state file, under the user's own temp directory.

    tempfile.gettempdir() honours TMPDIR (and TEMP/TMP) before falling back to a
    platform default -- on macOS that default is a private, mode-700 per-user directory,
    not the shared, world-writable /tmp a hardcoded path would have used. session_id is
    sanitized first (see sanitize_session_id), so a malformed value cannot relocate this
    file outside that directory.
    """
    return Path(tempfile.gettempdir()) / f"claude-loop-{sanitize_session_id(session_id)}.json"


def load_loop_state(session_id: str) -> dict:
    defaults = {
        "total_tool_calls": 0,
        "last_tool": None,
        "last_input_hash": None,
        "repeat_count": 0,
        "agent_starts": {},     # agent_id -> start_timestamp
        "agent_types": {},      # agent_id -> agent_type
        "tool_starts": {},      # tool_use_id -> start_timestamp
        "error_patterns": {"eisdir": 0},
        # Ghost event batching (new)
        "ghost_count": 0,
        "ghost_first_ts": None,
        # Duplicate batch detection (new)
        "recent_agent_batches": [],  # [{ts, types: [sorted agent_types]}]
        "last_skill_name": None,
        # Strategic compact & handover
        "compact_hint_sent": False,
        "compact_reminded": False,
        "compact_urgent_sent": False,
        "token_budget_warned": False,
        "last_productive_ts": None,
        "stagnation_warned": False,
        # Token tracking
        "token_input": 0,          # Estimated input tokens (tool_input + prompts)
        "token_output_est": 0,     # Estimated output tokens (heuristic)
        "token_system": SYSTEM_PROMPT_ESTIMATE,  # One-time system prompt
        "token_by_tool": {},       # Tokens per tool type
        "token_by_agent": {},      # Tokens per agent type
    }
    path = get_loop_state_path(session_id)
    if path.exists():
        try:
            with open(path, "r") as f:
                state = json.load(f)
            # Migration: add missing fields
            for key, value in defaults.items():
                state.setdefault(key, value)
            return state
        except (json.JSONDecodeError, OSError):
            pass
    return defaults.copy()


def save_loop_state(session_id: str, state: dict):
    """Writes the loop state, creating the file with owner-only permissions.

    The state contains counters, timestamps, agent ids and an input hash -- no prompt
    text -- but it is still session metadata a local user should not be able to read off
    another user's session. os.open's mode is applied atomically at creation (no window
    where the file exists world-readable before a later chmod call narrows it), and
    os.fchmod re-asserts 0o600 on every write so a file that happens to already exist
    with looser permissions (e.g. pre-created by something else) gets tightened rather
    than trusted.

    O_NOFOLLOW (M1, security-master review of F10, 29.08.2026): O_TRUNC on an existing
    path does not create a new inode, so without this flag a local user who pre-plants
    a symlink at the predictable claude-loop-<session_id>.json name -- before this
    process ever runs -- gets that symlink's TARGET truncated and rewritten with this
    process's privileges. The 0o600 mode and the fchmod re-assert below are correct as
    far as they go but do not address symlink-following at all; O_NOFOLLOW does. Not
    exploitable where TMPDIR is a private per-user directory (macOS default);
    exploitable on a Linux host falling back to a shared /tmp. When the target IS a
    symlink, os.open raises OSError (ELOOP) here, before the try/except below even
    starts -- deliberately NOT caught in this function. It propagates up through the
    calling handler to main()'s blanket `except Exception: log_error(...); exit(0)`,
    which is the intended degrade path: the session is never broken (exit 0 either
    way), but the attempt is filed as a MonitorError with the offending path and errno
    rather than silently discarded as if the write had succeeded. A rejected create-
    and-rename dance was explicitly ruled out for this file: it is a regenerable,
    secret-free cache, not worth the extra complexity.
    """
    path = get_loop_state_path(session_id)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        # fdopen has not taken ownership of fd yet, so this is the only path that
        # needs to close it manually.
        os.close(fd)
        raise
    with os.fdopen(fd, "w") as f:
        json.dump(state, f)


def cleanup_loop_state(session_id: str):
    path = get_loop_state_path(session_id)
    if path.exists():
        path.unlink()


def estimate_tokens(text) -> int:
    """Estimates token count from text (characters / CHARS_PER_TOKEN)."""
    if text is None:
        return 0
    if isinstance(text, dict):
        text = json.dumps(text, ensure_ascii=False)
    elif not isinstance(text, str):
        text = str(text)
    return max(1, len(text) // CHARS_PER_TOKEN)


def get_token_total(state: dict) -> int:
    """Calculates estimated total tokens from state."""
    return (state.get("token_system", 0)
            + state.get("token_input", 0)
            + state.get("token_output_est", 0))


def make_input_hash(tool_name: str, tool_input: dict) -> str:
    """Creates a simple hash from tool name + input for loop detection."""
    raw = json.dumps({"t": tool_name, "i": tool_input}, sort_keys=True)
    return str(hash(raw))


# === Input validation ===

def validate_ask_user_question(tool_input: dict, session_id: str) -> bool:
    """Validates AskUserQuestion input before execution.

    Checks that each question has at least 2 options (Claude Code schema requirement).
    Returns True if valid, False if the call should be blocked.
    """
    questions = tool_input.get("questions", [])
    if not questions:
        return True  # Empty questions – framework handles this itself

    errors = []
    for i, q in enumerate(questions):
        options = q.get("options", [])
        if len(options) < 2:
            errors.append(
                f"Question {i+1} (\"{q.get('question', '?')[:60]}\"): "
                f"only {len(options)} option(s) – at least 2 required"
            )
        elif len(options) > 4:
            errors.append(
                f"Question {i+1} (\"{q.get('question', '?')[:60]}\"): "
                f"{len(options)} options – maximum 4 allowed"
            )

    if errors:
        log_error(session_id, {
            "ts": now_iso(),
            "event": "InputValidation",
            "tool": "AskUserQuestion",
            "errors": errors,
            "session": session_id,
        })
        print(
            "AskUserQuestion validation failed:\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nEach question needs 2-4 options. "
            "The user can always choose 'Other', so 2 real options are sufficient.",
            file=sys.stderr
        )
        return False

    return True


PRETOOL_VALIDATORS = {
    "AskUserQuestion": validate_ask_user_question,
}


# === Ghost event batching ===

def flush_ghost_summary(state: dict, session_id: str):
    """Logs ghost event summary when ghost events have accumulated."""
    ghost_count = state.get("ghost_count", 0)
    if ghost_count > 0:
        log_activity(session_id, {
            "ts": now_iso(),
            "event": "GhostEventSummary",
            "ghost_count": ghost_count,
            "first_ghost_ts": state.get("ghost_first_ts"),
            "session": session_id,
        })
        log_error(session_id, {
            "ts": now_iso(),
            "event": "GhostEventSummary",
            "ghost_count": ghost_count,
            "first_ghost_ts": state.get("ghost_first_ts"),
            "message": f"{ghost_count} ghost SubagentStop events without preceding SubagentStart",
            "session": session_id,
        })
        # Reset counter
        state["ghost_count"] = 0
        state["ghost_first_ts"] = None


# === Event handlers ===

def check_handover_staleness(session_id: str, source_event: str):
    """Soft warning if docs/HANDOVER.md is older than the newest docs/*.md.

    Catches the autonomous-pipeline failure mode where an agent writes a
    phase artefact (DISCOVERY.md, CONCEPT.md, GATE_P0.md, ...) but does
    not update the HANDOVER. Logs an error event and prints to stderr —
    NEVER blocks (no exit(2)), so the pipeline keeps running.

    Only warns once per (session, source_event) combination to avoid spam.
    Silent no-op if no docs/HANDOVER.md exists in cwd (= not a project run).
    """
    try:
        cwd = Path.cwd()
        docs_dir = cwd / "docs"
        handover = docs_dir / "HANDOVER.md"
        if not docs_dir.is_dir() or not handover.exists():
            return

        handover_mtime = handover.stat().st_mtime
        newest_other_mtime = 0.0
        newest_other_name = None
        for md in docs_dir.glob("*.md"):
            if md.name == "HANDOVER.md":
                continue
            mt = md.stat().st_mtime
            if mt > newest_other_mtime:
                newest_other_mtime = mt
                newest_other_name = md.name

        if newest_other_name is None:
            return
        if handover_mtime + HANDOVER_STALENESS_TOLERANCE_S >= newest_other_mtime:
            return

        state = load_loop_state(session_id)
        warned_key = f"handover_stale_warned_{source_event}"
        if state.get(warned_key):
            return
        state[warned_key] = True
        save_loop_state(session_id, state)

        age_diff_min = round((newest_other_mtime - handover_mtime) / 60, 1)
        log_error(session_id, {
            "ts": now_iso(),
            "event": "HandoverStale",
            "source": source_event,
            "newest_doc": newest_other_name,
            "age_diff_minutes": age_diff_min,
            "session": session_id,
        })
        print(
            f"HANDOVER warning: docs/{newest_other_name} is {age_diff_min} min "
            f"newer than docs/HANDOVER.md. Update HANDOVER.md before this run ends.",
            file=sys.stderr
        )
    except Exception:
        # Never block the pipeline due to a check failure
        pass


def parse_handover_cap(text: str) -> tuple:
    """Reads the size cap the HANDOVER declares in its own header.

    Mirrors what /cleanup §2 does: look for a line like `Size cap: ≤N KB` (the shipped
    template wraps it in markdown, so match on the `≤N KB` part) plus its line dimension
    `(~N lines)`. Falls back to the template default when the header declares neither.

    Only the first HANDOVER_CAP_HEADER_LINES lines are scanned. A file's own cap is a
    header statement; a threshold quoted somewhere in the body is prose about something
    else and must not silently redefine the cap.

    Returns (cap_bytes, cap_lines).
    """
    header = "\n".join(text.splitlines()[:HANDOVER_CAP_HEADER_LINES])

    cap_bytes = HANDOVER_DEFAULT_CAP_BYTES
    kb_match = re.search(r"[≤<]\s*=?\s*(\d+(?:[.,]\d+)?)\s*KB", header, re.IGNORECASE)
    if kb_match:
        cap_bytes = int(round(float(kb_match.group(1).replace(",", ".")) * 1024))

    cap_lines = HANDOVER_DEFAULT_CAP_LINES
    lines_match = re.search(r"(\d+)\s*lines", header, re.IGNORECASE)
    if lines_match:
        cap_lines = int(lines_match.group(1))

    return cap_bytes, cap_lines


def is_at_least_pct(count: int, cap: int, pct_of_cap: int) -> bool:
    """True when count has reached pct_of_cap percent of cap, compared exactly.

    Integer arithmetic on purpose: `100 * count >= pct * cap` is the same question as
    `count / cap >= pct / 100` without ever building a float, so no boundary can be moved
    by a rounding step. A cap of 0 or None is "no cap declared" and can never be reached.
    """
    return bool(cap) and 100 * count >= pct_of_cap * cap


def is_handover_write(tool_name, tool_input) -> bool:
    """True when a tool call just changed a HANDOVER.md, i.e. may have changed its size.

    The gate that keeps check_handover_size off the other ~99 % of PostToolUse events. A
    Read of the same file is excluded on purpose: it cannot move the file past its cap, so
    re-measuring would only cost time and risk a duplicate warning.

    Contains its own input, like its sibling check_handover_size does. A hook payload is
    JSON produced by another process, so nothing guarantees the declared types: an
    unhashable tool_name breaks the set lookup, a non-str file_path breaks
    os.path.basename, and a tool_input that is not a mapping breaks .get. None of that
    blocks — main()'s catch-all holds and the exit code stays 0 — but the check silently
    does not run and the event is filed as a MonitorError, i.e. as a defect of the monitor
    rather than as the malformed payload it is. A payload the gate cannot read is simply
    not a HANDOVER write, so False is the honest answer.

    The containment costs three isinstance checks on a path that runs on every PostToolUse
    — nanoseconds against the ~20 ms process startup that dominates any hook invocation.
    """
    if not isinstance(tool_name, str) or tool_name not in HANDOVER_WRITE_TOOLS:
        return False
    if not isinstance(tool_input, dict):
        return False
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return False
    return os.path.basename(file_path) == "HANDOVER.md"


def check_handover_size(session_id: str, source_event: str):
    """Soft warning when docs/HANDOVER.md approaches or exceeds its own size cap.

    The cap is documented in templates/HANDOVER_TEMPLATE.md and enforced by /cleanup §2,
    but nothing triggered it: a file drifts past 5 KB unnoticed until someone happens to
    run the command. scripts/doc-volume-check.sh does not cover it — its thresholds start
    at 25 KB, five times this cap.

    Sibling of check_handover_staleness and follows the same discipline: logs an error
    event and prints to stderr, NEVER blocks (no exit(2)), silent no-op when there is no
    docs/HANDOVER.md in cwd (= not a project run).

    Deduplication is per (session, source_event, level). Adding the level to the key is a
    deliberate widening of the staleness check's (session, source_event): a file warned
    about at "approaching" and later breaching the cap in the same session must still be
    able to say so, and an escalation swallowed by its own predecessor is the failure mode
    this check exists to remove. The bound stays small — two events x two levels.
    """
    try:
        cwd = Path.cwd()
        handover = cwd / "docs" / "HANDOVER.md"
        if not handover.is_file():
            return

        raw = handover.read_bytes()
        size_bytes = len(raw)
        text = raw.decode("utf-8", errors="replace")
        line_count = text.count("\n")
        if text and not text.endswith("\n"):
            line_count += 1

        cap_bytes, cap_lines = parse_handover_cap(text)
        byte_pct = round(100 * size_bytes / cap_bytes) if cap_bytes else 0
        line_pct = round(100 * line_count / cap_lines) if cap_lines else 0
        pct = max(byte_pct, line_pct)

        # The level is decided on the exact counts, never on the rounded percentages
        # above. Rounding is a presentation concern, and letting it pick the level moves
        # both boundaries by half a percentage point: 5097 B against the 5120 B cap is
        # 99.55 %, i.e. under the cap, yet rounds to 100 and was announced as a breach —
        # while /cleanup section 2, computing the same percentage from the same numbers,
        # calls that file approaching. Two checks disagreeing about one file is worse
        # than either staying silent. The same error sits at the warn threshold, where
        # 4071 B is 79.51 % and rounds onto 80. The reported numbers stay rounded.
        if (is_at_least_pct(size_bytes, cap_bytes, 100)
                or is_at_least_pct(line_count, cap_lines, 100)):
            level = "over"
        elif (is_at_least_pct(size_bytes, cap_bytes, HANDOVER_WARN_PCT)
                or is_at_least_pct(line_count, cap_lines, HANDOVER_WARN_PCT)):
            level = "approaching"
        else:
            return

        state = load_loop_state(session_id)
        warned_key = f"handover_size_warned_{source_event}_{level}"
        if state.get(warned_key):
            return
        state[warned_key] = True
        save_loop_state(session_id, state)

        log_error(session_id, {
            "ts": now_iso(),
            "event": "HandoverSize",
            "source": source_event,
            "level": level,
            "bytes": size_bytes,
            "lines": line_count,
            "cap_bytes": cap_bytes,
            "cap_lines": cap_lines,
            "pct_of_cap_rounded": pct,
            "session": session_id,
        })
        verdict = (
            "Over cap" if level == "over"
            else f"Approaching the cap (warn at {HANDOVER_WARN_PCT} %)"
        )
        print(
            f"HANDOVER size warning: docs/HANDOVER.md is "
            f"{size_bytes / 1024:.1f} KB ({byte_pct} % of the {cap_bytes / 1024:g} KB cap) / "
            f"{line_count} lines ({line_pct} % of {cap_lines}). "
            f"{verdict} — run /cleanup to archive the oldest block.",
            file=sys.stderr
        )
    except Exception:
        # Never block the pipeline due to a check failure
        pass


def handle_session_start(data: dict, session_id: str):
    source = data.get("source", "unknown")
    log_activity(session_id, {
        "ts": now_iso(),
        "event": "SessionStart",
        "source": source,
        "session": session_id,
    })
    # Initialize fresh loop state
    state = load_loop_state(session_id)
    state["last_productive_ts"] = time.time()
    save_loop_state(session_id, state)

    # Size cap before the writing starts: at session start the warning is still actionable
    # (run /cleanup first), at session end it would arrive after the fact.
    check_handover_size(session_id, "SessionStart")


def handle_session_end(data: dict, session_id: str):
    reason = data.get("reason", "unknown")
    state = load_loop_state(session_id)
    now = time.time()

    # 1. Flush ghost event summary
    flush_ghost_summary(state, session_id)

    # 2. Incomplete agent detection: agents without SubagentStop
    agent_starts = state.get("agent_starts", {})
    agent_types = state.get("agent_types", {})
    if agent_starts:
        incomplete = []
        for agent_id, start_ts in agent_starts.items():
            duration_s = round(now - start_ts, 1)
            agent_type = agent_types.get(agent_id, "unknown")
            incomplete.append({
                "agent_id": agent_id,
                "agent_type": agent_type,
                "estimated_duration_s": duration_s,
            })
        log_error(session_id, {
            "ts": now_iso(),
            "event": "IncompleteAgents",
            "agents": incomplete,
            "message": f"{len(incomplete)} agent(s) without SubagentStop (likely interrupted by compact)",
            "session": session_id,
        })
        log_activity(session_id, {
            "ts": now_iso(),
            "event": "IncompleteAgents",
            "count": len(incomplete),
            "agents": [a["agent_type"] for a in incomplete],
            "session": session_id,
        })

    # 3. Log stale tool_starts (>5 orphaned entries)
    tool_starts = state.get("tool_starts", {})
    if len(tool_starts) > 5:
        log_error(session_id, {
            "ts": now_iso(),
            "event": "StaleToolStarts",
            "count": len(tool_starts),
            "message": f"{len(tool_starts)} orphaned tool_starts at SessionEnd",
            "session": session_id,
        })

    # 4. Write session summary for postmortem
    token_total = get_token_total(state)
    summary = {
        "session_id": session_id,
        "ts_end": now_iso(),
        "total_tool_calls": state.get("total_tool_calls", 0),
        "agents_used": list(set(state.get("agent_types", {}).values())),
        "had_loops": state.get("repeat_count", 0) >= LOOP_WARN_THRESHOLD,
        "compact_reminded": state.get("compact_reminded", False),
        "stagnation_warned": state.get("stagnation_warned", False),
        "incomplete_agents": len(state.get("agent_starts", {})),
        "token_estimate": {
            "total": token_total,
            "system": state.get("token_system", 0),
            "input": state.get("token_input", 0),
            "output_est": state.get("token_output_est", 0),
            "by_tool": state.get("token_by_tool", {}),
            "by_agent": state.get("token_by_agent", {}),
        },
    }
    summary_path = session_log_dir(session_id) / "session-summary.json"
    try:
        ensure_dirs(session_id)
        fd = open_owner_only(summary_path, os.O_WRONLY | os.O_TRUNC)
        with os.fdopen(fd, "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    except OSError:
        pass  # Summary is best-effort, don't break session end

    # 5. Final performance summary
    log_performance(session_id, {
        "ts": now_iso(),
        "event": "SessionEnd",
        "reason": reason,
        "total_tool_calls": state.get("total_tool_calls", 0),
        "token_estimate_total": token_total,
        "token_by_tool": state.get("token_by_tool", {}),
        "token_by_agent": state.get("token_by_agent", {}),
        "session": session_id,
    })
    log_activity(session_id, {
        "ts": now_iso(),
        "event": "SessionEnd",
        "reason": reason,
        "session": session_id,
    })
    cleanup_loop_state(session_id)


def handle_subagent_start(data: dict, session_id: str):
    agent_id = data.get("agent_id", "unknown")
    agent_type = data.get("agent_type", "unknown")

    log_activity(session_id, {
        "ts": now_iso(),
        "event": "SubagentStart",
        "agent": agent_id,
        "agent_type": agent_type,
        "session": session_id,
    })

    # Record start time and type for performance tracking
    state = load_loop_state(session_id)
    now = time.time()
    state["agent_starts"][agent_id] = now
    state.setdefault("agent_types", {})[agent_id] = agent_type

    # Duplicate batch detection
    batches = state.get("recent_agent_batches", [])

    # Add agent to current batch or start a new batch
    if batches and (now - batches[-1]["ts"]) < BATCH_GROUP_WINDOW_S:
        # Add to last batch
        batches[-1]["types"].append(agent_type)
        batches[-1]["types"].sort()
    else:
        # New batch
        batches.append({"ts": now, "types": [agent_type]})

    # Clean up old batches (outside the lookback window)
    batches = [b for b in batches if now - b["ts"] < DUPLICATE_BATCH_WINDOW_S]

    # Duplicate check: did an earlier batch have the same type set?
    if len(batches) >= 2:
        current_types = batches[-1]["types"]
        for older_batch in batches[:-1]:
            if older_batch["types"] == current_types:
                minutes_ago = round((now - older_batch["ts"]) / 60, 1)
                log_error(session_id, {
                    "ts": now_iso(),
                    "event": "DuplicateBatchWarning",
                    "batch_types": current_types,
                    "previous_batch_minutes_ago": minutes_ago,
                    "message": f"Identical agent set {current_types} was already started {minutes_ago} min ago",
                    "session": session_id,
                })
                print(
                    f"Duplicate batch: agent set {current_types} was already started "
                    f"{minutes_ago} min ago. Intentional repetition?",
                    file=sys.stderr
                )
                break  # One warning is enough

    state["recent_agent_batches"] = batches
    save_loop_state(session_id, state)


def handle_subagent_stop(data: dict, session_id: str):
    state = load_loop_state(session_id)
    # Agent ID is unfortunately not directly available in SubagentStop,
    # so we track via the most recently started agent
    agent_starts = state.get("agent_starts", {})

    # Ghost event: SubagentStop without preceding SubagentStart
    if not agent_starts:
        ghost_count = state.get("ghost_count", 0)

        if ghost_count == 0:
            # First ghost event: log once as a marker
            log_activity(session_id, {
                "ts": now_iso(),
                "event": "SubagentStop",
                "agent": "ghost",
                "ghost": True,
                "duration_s": None,
                "session": session_id,
            })
            state["ghost_first_ts"] = now_iso()

        # Increment counter, but do not log each event individually
        state["ghost_count"] = ghost_count + 1
        save_loop_state(session_id, state)

        # Silently ignore – NO stderr output and exit(0) instead of exit(2).
        # exit(2) + stderr generates feedback to the agent, which responds to it,
        # which in turn triggers a new SubagentStop event -> infinite loop.
        # (Root cause of the 1h20m QA tester hang from 27.02.2026)
        sys.exit(0)

    # Find the agent that has been running the shortest time (= most recently started)
    last_agent = max(agent_starts, key=agent_starts.get)
    start_time = agent_starts.pop(last_agent, None)
    duration_s = round(time.time() - start_time, 1) if start_time else None

    # Get agent type from state
    agent_type = state.get("agent_types", {}).get(last_agent, "unknown")

    # Token tracking: estimate agent tokens (subagent conversation)
    # Heuristic: ~2000 token base + 500/min runtime
    agent_tokens_est = 2000
    if duration_s is not None:
        agent_tokens_est += int(duration_s / 60 * 500)
    state["token_output_est"] = state.get("token_output_est", 0) + agent_tokens_est
    agent_tokens = state.get("token_by_agent", {})
    agent_tokens[agent_type] = agent_tokens.get(agent_type, 0) + agent_tokens_est
    state["token_by_agent"] = agent_tokens

    log_activity(session_id, {
        "ts": now_iso(),
        "event": "SubagentStop",
        "agent": last_agent,
        "agent_type": agent_type,
        "duration_s": duration_s,
        "token_est": agent_tokens_est,
        "session": session_id,
    })

    if duration_s is not None:
        log_performance(session_id, {
            "ts": now_iso(),
            "event": "AgentComplete",
            "agent": last_agent,
            "agent_type": agent_type,
            "duration_s": duration_s,
            "token_est": agent_tokens_est,
            "session": session_id,
        })

        # Slow agent warning
        if duration_s > AGENT_DURATION_WARN_S:
            log_error(session_id, {
                "ts": now_iso(),
                "event": "AgentSlow",
                "agent": last_agent,
                "agent_type": agent_type,
                "duration_s": duration_s,
                "message": f"Agent '{agent_type}' ran for {duration_s / 60:.1f} minutes",
                "session": session_id,
            })
            print(
                f"Agent '{agent_type}' ran for {duration_s / 60:.1f} minutes",
                file=sys.stderr
            )

    save_loop_state(session_id, state)
    check_handover_staleness(session_id, "SubagentStop")


def handle_pre_tool_use(data: dict, session_id: str):
    tool_name = data.get("tool_name", "unknown")
    tool_input = data.get("tool_input", {})

    # Input validation (before loop detection, so invalid calls are never counted)
    validator = PRETOOL_VALIDATORS.get(tool_name)
    if validator and not validator(tool_input, session_id):
        sys.exit(2)  # Blocks the tool call, stderr feedback goes to Claude

    state = load_loop_state(session_id)
    state["total_tool_calls"] = state.get("total_tool_calls", 0) + 1

    # Loop detection
    current_hash = make_input_hash(tool_name, tool_input)

    if state.get("last_tool") == tool_name and state.get("last_input_hash") == current_hash:
        state["repeat_count"] = state.get("repeat_count", 0) + 1
    else:
        state["repeat_count"] = 1
        state["last_tool"] = tool_name
        state["last_input_hash"] = current_hash

    repeat = state["repeat_count"]
    total = state["total_tool_calls"]

    # Start time for performance tracking
    tool_use_id = data.get("tool_use_id", str(time.time()))
    now = time.time()
    state.setdefault("tool_starts", {})[tool_use_id] = now

    # Clean up stale tool_starts (older than 1h)
    tool_starts = state.get("tool_starts", {})
    stale_ids = [tid for tid, ts in tool_starts.items() if now - ts > STALE_TOOL_THRESHOLD_S]
    for tid in stale_ids:
        del tool_starts[tid]

    # Skill tracking: record name when tool == Skill
    if tool_name == "Skill":
        skill_name = tool_input.get("skill", tool_input.get("args", "unknown"))
        state["last_skill_name"] = skill_name
        log_activity(session_id, {
            "ts": now_iso(),
            "event": "SkillInvocation",
            "skill": skill_name,
            "session": session_id,
        })

    # Token tracking: measure input + estimate output
    input_tokens = estimate_tokens(tool_input)
    output_est = TOKEN_RESULT_ESTIMATES.get(tool_name, TOKEN_RESULT_ESTIMATES["default"])
    state["token_input"] = state.get("token_input", 0) + input_tokens
    state["token_output_est"] = state.get("token_output_est", 0) + output_est

    # Aggregate per tool type
    tool_tokens = state.get("token_by_tool", {})
    tool_tokens[tool_name] = tool_tokens.get(tool_name, 0) + input_tokens + output_est
    state["token_by_tool"] = tool_tokens

    save_loop_state(session_id, state)

    # Log token status periodically
    if total > 0 and total % TOKEN_LOG_INTERVAL == 0:
        token_total = get_token_total(state)
        log_performance(session_id, {
            "ts": now_iso(),
            "event": "TokenEstimate",
            "total_calls": total,
            "token_total": token_total,
            "token_input": state.get("token_input", 0),
            "token_output_est": state.get("token_output_est", 0),
            "token_system": state.get("token_system", 0),
            "top_tools": dict(sorted(
                state.get("token_by_tool", {}).items(),
                key=lambda x: x[1], reverse=True
            )[:5]),
            "session": session_id,
        })

    # Log entry
    log_activity(session_id, {
        "ts": now_iso(),
        "event": "PreToolUse",
        "tool": tool_name,
        "repeat": repeat,
        "total_calls": total,
        "session": session_id,
    })

    # Loop detection: warning
    if repeat == LOOP_WARN_THRESHOLD:
        log_error(session_id, {
            "ts": now_iso(),
            "event": "LoopWarning",
            "tool": tool_name,
            "repeat_count": repeat,
            "message": f"Tool '{tool_name}' was called {repeat}x with identical input",
            "session": session_id,
        })

    # Loop detection: block
    if repeat >= LOOP_BLOCK_THRESHOLD:
        log_error(session_id, {
            "ts": now_iso(),
            "event": "LoopBlocked",
            "tool": tool_name,
            "repeat_count": repeat,
            "message": f"BLOCKED: Tool '{tool_name}' was called {repeat}x with identical input",
            "session": session_id,
        })
        # Exit 2 = block, stderr is sent as feedback to Claude
        print(
            f"Loop detected: '{tool_name}' was called {repeat}x in a row with the same input. "
            f"Please change your approach or ask the user for help.",
            file=sys.stderr
        )
        sys.exit(2)

    # Total tool count warnings
    if total == TOTAL_TOOLS_WARN:
        log_error(session_id, {
            "ts": now_iso(),
            "event": "HighToolCount",
            "total_calls": total,
            "message": f"Already {total} tool calls in this session",
            "session": session_id,
        })

    if total == TOTAL_TOOLS_CRITICAL:
        log_error(session_id, {
            "ts": now_iso(),
            "event": "CriticalToolCount",
            "total_calls": total,
            "message": f"CRITICAL: {total} tool calls in this session!",
            "session": session_id,
        })

    # Strategic compact: 3-level reminder
    if total >= COMPACT_HINT_THRESHOLD and not state.get("compact_hint_sent"):
        state["compact_hint_sent"] = True
        log_activity(session_id, {
            "ts": now_iso(),
            "event": "CompactHint",
            "total_calls": total,
            "session": session_id,
        })
        print(
            f"{total} tool calls reached. Consider /compact when convenient.",
            file=sys.stderr
        )

    if total >= COMPACT_REMINDER_THRESHOLD and not state.get("compact_reminded"):
        state["compact_reminded"] = True
        log_activity(session_id, {
            "ts": now_iso(),
            "event": "CompactReminder",
            "total_calls": total,
            "session": session_id,
        })
        print(
            f"{total} tool calls – /compact recommended. "
            f"Update docs/HANDOVER.md first!",
            file=sys.stderr
        )

    if total >= COMPACT_URGENT_THRESHOLD and not state.get("compact_urgent_sent"):
        state["compact_urgent_sent"] = True
        log_activity(session_id, {
            "ts": now_iso(),
            "event": "CompactUrgent",
            "total_calls": total,
            "session": session_id,
        })
        print(
            f"{total} tool calls – context is filling up. "
            f"Update docs/HANDOVER.md and run /compact!",
            file=sys.stderr
        )

    # Token budget early warning (after TOKEN_BUDGET_WARNING tool calls)
    if total == TOKEN_BUDGET_WARNING and not state.get("token_budget_warned"):
        state["token_budget_warned"] = True
        log_activity(session_id, {
            "ts": now_iso(),
            "event": "TokenBudgetWarning",
            "total_calls": total,
            "session": session_id,
        })
        print(
            f"{total} tool calls – token budget is running low. "
            f"Please update docs/HANDOVER.md now if you haven't already!",
            file=sys.stderr
        )

    # Stagnation detection: track productive tools
    now = time.time()
    if tool_name in STAGNATION_TOOLS:
        state["last_productive_ts"] = now
        state["stagnation_warned"] = False
    else:
        last_productive = state.get("last_productive_ts")
        if (last_productive is not None
                and not state.get("stagnation_warned")
                and (now - last_productive) > STAGNATION_WINDOW_S):
            state["stagnation_warned"] = True
            minutes = round((now - last_productive) / 60, 1)
            log_error(session_id, {
                "ts": now_iso(),
                "event": "StagnationWarning",
                "minutes_since_productive": minutes,
                "session": session_id,
            })
            print(
                f"Stagnation: no Write/Edit for {minutes} min. "
                f"Stuck? Consider rethinking the approach or asking the user.",
                file=sys.stderr
            )


def handle_post_tool_use(data: dict, session_id: str):
    tool_name = data.get("tool_name", "unknown")
    tool_use_id = data.get("tool_use_id", "")

    # Performance: calculate duration
    state = load_loop_state(session_id)
    tool_starts = state.get("tool_starts", {})
    start_time = tool_starts.pop(tool_use_id, None)
    duration_ms = round((time.time() - start_time) * 1000) if start_time else None
    save_loop_state(session_id, state)

    log_activity(session_id, {
        "ts": now_iso(),
        "event": "PostToolUse",
        "tool": tool_name,
        "duration_ms": duration_ms,
        "session": session_id,
    })

    if duration_ms is not None:
        log_performance(session_id, {
            "ts": now_iso(),
            "event": "ToolComplete",
            "tool": tool_name,
            "duration_ms": duration_ms,
            "session": session_id,
        })

    # Size cap right after a HANDOVER write: this is the moment the file grows, and a full
    # skill run can cross the cap between two SessionStarts. The gate keeps the cost of the
    # check off every other tool call — a set lookup plus one basename comparison.
    if is_handover_write(tool_name, data.get("tool_input", {})):
        check_handover_size(session_id, "PostToolUse")


def handle_post_tool_use_failure(data: dict, session_id: str):
    tool_name = data.get("tool_name", "unknown")
    tool_input = data.get("tool_input", {})
    error = data.get("error", "unknown error")

    log_error(session_id, {
        "ts": now_iso(),
        "event": "ToolFailure",
        "tool": tool_name,
        "error": error,
        "input_summary": str(tool_input)[:500],  # Truncated to keep log size manageable
        "session": session_id,
    })

    log_activity(session_id, {
        "ts": now_iso(),
        "event": "ToolFailure",
        "tool": tool_name,
        "error": error[:200],
        "session": session_id,
    })

    # EISDIR pattern detection
    if "EISDIR" in str(error) or "Is a directory" in str(error):
        state = load_loop_state(session_id)
        error_patterns = state.setdefault("error_patterns", {"eisdir": 0})
        error_patterns["eisdir"] = error_patterns.get("eisdir", 0) + 1
        eisdir_count = error_patterns["eisdir"]
        save_loop_state(session_id, state)

        if eisdir_count >= EISDIR_WARN_THRESHOLD:
            log_error(session_id, {
                "ts": now_iso(),
                "event": "LoopWarning",
                "pattern": "EISDIR",
                "count": eisdir_count,
                "message": f"Repeated EISDIR errors ({eisdir_count}x) – agent is trying to read directories",
                "session": session_id,
            })
            print(
                f"EISDIR pattern: read a directory instead of a file {eisdir_count}x. "
                f"Agent should use Glob/ls instead of Read on directories.",
                file=sys.stderr
            )


def handle_stop(data: dict, session_id: str):
    log_activity(session_id, {
        "ts": now_iso(),
        "event": "Stop",
        "session": session_id,
    })
    check_handover_staleness(session_id, "Stop")


def handle_notification(data: dict, session_id: str):
    message = data.get("message", "")
    title = data.get("title", "")
    log_activity(session_id, {
        "ts": now_iso(),
        "event": "Notification",
        "title": title,
        "message": message[:200],
        "session": session_id,
    })


def handle_user_prompt(data: dict, session_id: str):
    prompt = data.get("prompt", "")

    # Token tracking: measure user prompt
    state = load_loop_state(session_id)
    prompt_tokens = estimate_tokens(prompt)
    state["token_input"] = state.get("token_input", 0) + prompt_tokens
    save_loop_state(session_id, state)

    log_activity(session_id, {
        "ts": now_iso(),
        "event": "UserPrompt",
        "prompt_length": len(prompt),
        "prompt_tokens_est": prompt_tokens,
        "prompt_preview": prompt[:100],
        "session": session_id,
    })


# === Dispatcher ===

EVENT_HANDLERS = {
    "SessionStart": handle_session_start,
    "SessionEnd": handle_session_end,
    "SubagentStart": handle_subagent_start,
    "SubagentStop": handle_subagent_stop,
    "PreToolUse": handle_pre_tool_use,
    "PostToolUse": handle_post_tool_use,
    "PostToolUseFailure": handle_post_tool_use_failure,
    "Stop": handle_stop,
    "Notification": handle_notification,
    "UserPromptSubmit": handle_user_prompt,
}


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)

        data = json.loads(raw)
        event_name = data.get("hook_event_name", "unknown")
        session_id = data.get("session_id", "no-session")

        handler = EVENT_HANDLERS.get(event_name)
        if handler:
            handler(data, session_id)
        else:
            # Log unknown events anyway
            log_activity(session_id, {
                "ts": now_iso(),
                "event": f"Unknown:{event_name}",
                "session": session_id,
            })

    except json.JSONDecodeError:
        # Not valid JSON – exit silently
        sys.exit(0)
    except Exception as e:
        # Error in the monitor itself – do not block Claude
        try:
            log_error("monitor-internal", {
                "ts": now_iso(),
                "event": "MonitorError",
                "error": str(e),
            })
        except Exception:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
