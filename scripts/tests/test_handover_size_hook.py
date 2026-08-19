"""test_handover_size_hook.py – End-to-end tests for the HANDOVER size-cap hook check.

Invokes the real entry point as a subprocess (`python3 hooks/agent-monitor.py`) with a
crafted hook payload on stdin, exactly as Claude Code drives it, rather than importing
internals. That keeps the documented hook contract inside the test surface: the payload
shape, the cwd-relative `docs/HANDOVER.md` lookup, the stderr rendering, and above all
the exit code — an advisory check that ever returns non-zero would block the pipeline.

Two environment redirections make a run reproducible on any machine:

* **HOME** points at a throwaway directory. `agent-monitor.py` derives all log paths from
  `~/.claude/logs/**`; without the redirection a run would append to the developer's own
  logs and read their state.
* **session_id** is unique per test. The loop state that carries the once-per-session
  dedup lives in `/tmp/claude-loop-{session_id}.json`, i.e. NOT under HOME — a shared id
  would leak the "already warned" flag from one test into the next. tearDown deletes the
  file so a re-run starts clean.

The tests are grouped by the question they answer:

* **Does it warn at all?** — threshold behaviour (under, approaching, over), on both
  dimensions (bytes and lines), and the header-declared cap override.
* **Does it stay quiet when it must?** — no `docs/HANDOVER.md`, unrelated tool calls,
  repeated events in one session.
* **Does it ever block?** — the exit code across every state, including a HANDOVER that
  cannot be decoded.
* **Does the gate contain its own input?** — a malformed `tool_input` must read as "not a
  HANDOVER write", not as an internal monitor error.
* **Are the constants pinned?** — the warn threshold and the `is_file()` guard are load-bearing
  values that behaviour tests alone leave free to drift.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "agent-monitor.py"


def _load_agent_monitor_module():
    """Loads hooks/agent-monitor.py as a module, for its constants only.

    Used exclusively as the source of truth for parametrized tests (e.g.
    HANDOVER_WRITE_TOOLS below) — every behaviour assertion in this file still drives
    the real entry point as a subprocess (see module docstring); nothing here calls a
    function from the loaded module directly. __name__ is "ccpr_agent_monitor", not
    "__main__", so the `if __name__ == "__main__": main()` guard at the bottom of the
    hook does not fire and no hook logic runs as a side effect of the import.
    """
    spec = importlib.util.spec_from_file_location("ccpr_agent_monitor", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AGENT_MONITOR = _load_agent_monitor_module()

# The shipped default from templates/HANDOVER_TEMPLATE.md. KB is 1024 bytes, matching
# scripts/doc-volume-check.sh.
DEFAULT_CAP_BYTES = 5 * 1024
DEFAULT_CAP_LINES = 150

# Every hook run is bounded. A normal invocation costs ~20 ms (process startup dominates);
# this ceiling exists so a guard regression that makes the hook block turns into a failing
# test instead of a wedged test runner.
HOOK_TIMEOUT_S = 10

# Measured in this repo on 18.08.2026 and recorded in the hook's own comment above
# HANDOVER_WARN_PCT: one skill run grew docs/HANDOVER.md by this many bytes. The warn
# threshold is derived from it — see ThresholdDerivationTest.
SINGLE_RUN_GROWTH_BYTES = 1021

# The last moment at which a warning is still preventive: one run's growth below the cap.
# Anything higher and the very next run breaches the cap without ever having been announced.
DERIVED_WARN_PCT = round(100 * (DEFAULT_CAP_BYTES - SINGLE_RUN_GROWTH_BYTES) / DEFAULT_CAP_BYTES)

# The rounding band at the cap: every file from 5095 B up rounds to 100 % of the 5120 B
# cap while still being under it. 5097 B (99.55 %) is the case reported on WI-0003.
JUST_UNDER_CAP_BYTES = 5097
LAST_BYTE_UNDER_CAP_BYTES = DEFAULT_CAP_BYTES - 1        # 5119 B, 99.98 %
# The same band at the warn threshold: 4071 B is 79.51 %, under 80 % but rounding onto it.
JUST_UNDER_WARN_BYTES = 4071
AT_WARN_BYTES = DERIVED_WARN_PCT * DEFAULT_CAP_BYTES // 100      # 4096 B, exactly 80 %
# A declared line cap of 200 puts 199 lines at exactly 99.5 %, which rounds up to 100.
# The 150-line default has no such line count (149 is 99.33 %), so the line dimension can
# only be pinned against a declared cap.
DECLARED_LINE_CAP = 200

# Substring that identifies a size warning in the rendered stderr. The staleness check in
# the same file prints "HANDOVER warning:" too, so this marker must not be that prefix.
SIZE_MARKER = "size"

TEMPLATE_HEADER = (
    "# Handover – Work State\n"
    "\n"
    "> **Size cap**: HANDOVER.md is a **snapshot**, not a journal. "
    "Keep it ≤5 KB (~150 lines).\n"
    "\n"
)


def handover_of_size(target_bytes: int, header: str = TEMPLATE_HEADER) -> str:
    """Builds HANDOVER text of (at least) target_bytes with few, long lines.

    Long lines keep the line count far below its cap, so a byte-driven test cannot be
    satisfied accidentally by the line dimension.
    """
    filler_line = "x" * 500 + "\n"
    text = header
    while len(text.encode("utf-8")) < target_bytes:
        text += filler_line
    return text


def handover_of_exact_size(target_bytes: int, header: str = TEMPLATE_HEADER) -> str:
    """Builds HANDOVER text of exactly target_bytes, byte for byte.

    handover_at_pct can only express whole percentages of the cap, i.e. steps of 51 B
    against the 5 KB default. Both level boundaries live *inside* one such step (the
    band that rounds to 100 % is 5095-5119 B, 25 B wide), so no whole-percentage
    fixture can reach them — the helper is not imprecise, it cannot address the range
    at all. Filler lines are 100 B, keeping the line dimension far below its own cap so
    that `max(byte_pct, line_pct)` is decided by bytes.
    """
    base = header.encode("utf-8")
    remaining = target_bytes - len(base)
    if remaining < 0:
        raise ValueError(f"header alone already exceeds {target_bytes} bytes")
    filler = ("x" * 99 + "\n") * (remaining // 100) + "x" * (remaining % 100)
    return header + filler


def handover_at_pct(pct: int, header: str = TEMPLATE_HEADER) -> str:
    """Builds HANDOVER text whose *byte* percentage of the default cap is exactly `pct`.

    handover_of_size only guarantees "at least N bytes", which is too coarse to pin a
    threshold: the boundary test needs the file to land on one specific percentage and its
    neighbour on the next one down. For sub-percentage boundaries use
    handover_of_exact_size, which this delegates to.
    """
    return handover_of_exact_size(round(pct * DEFAULT_CAP_BYTES / 100), header=header)


def handover_of_lines(line_count: int, header: str = TEMPLATE_HEADER) -> str:
    """Builds HANDOVER text with line_count short lines, staying small in bytes."""
    return header + "".join(f"- item {i}\n" for i in range(line_count))


class HandoverSizeHookTestCase(unittest.TestCase):
    """Shared fixture: a temp project dir, a temp HOME, and a unique session id."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-handover-hook-"))
        self.project = self.tmp / "project"
        (self.project / "docs").mkdir(parents=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.session_id = f"test-{uuid.uuid4().hex[:12]}"
        self._session_ids = {self.session_id}

    def tearDown(self):
        for sid in self._session_ids:
            loop_state = Path(f"/tmp/claude-loop-{sid}.json")
            if loop_state.exists():
                loop_state.unlink()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- helpers -----------------------------------------------------------------

    def write_handover(self, text: str):
        (self.project / "docs" / "HANDOVER.md").write_text(text, encoding="utf-8")

    def run_hook(self, event: str, session_id: str = None, cwd: Path = None,
                 timeout: float = HOOK_TIMEOUT_S, **payload):
        """Drives agent-monitor.py with one hook payload and returns the CompletedProcess."""
        sid = session_id or self.session_id
        self._session_ids.add(sid)
        body = {"hook_event_name": event, "session_id": sid}
        body.update(payload)
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        return subprocess.run(
            ["python3", str(HOOK_PATH)],
            input=json.dumps(body),
            cwd=str(cwd or self.project),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def size_warnings(self, result) -> list:
        """Returns the stderr lines belonging to the size check, ignoring other output."""
        return [
            line for line in result.stderr.splitlines()
            if "HANDOVER" in line and SIZE_MARKER in line.lower()
        ]

    def monitor_error_events(self) -> list:
        """Errors the hook attributes to itself rather than to the session.

        main()'s catch-all writes these under the fixed "monitor-internal" session. A check
        that declines to run because its input is malformed must not appear here — the log
        would blame the monitor for a payload it merely failed to contain.
        """
        return self.error_events("monitor-internal")

    def error_events(self, session_id: str = None) -> list:
        """Reads the structured error log the hook writes under the redirected HOME."""
        sid = session_id or self.session_id
        log = self.home / ".claude" / "logs" / "sessions" / sid / "errors.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


# === Does it warn at all? ========================================================

class ThresholdTest(HandoverSizeHookTestCase):

    def test_under_cap_is_silent(self):
        self.write_handover(handover_of_size(2000))
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual([], self.size_warnings(result))

    def test_over_byte_cap_warns(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)

    def test_over_line_cap_warns_even_when_bytes_are_small(self):
        text = handover_of_lines(DEFAULT_CAP_LINES + 20)
        self.assertLess(len(text.encode("utf-8")), DEFAULT_CAP_BYTES,
                        "fixture must isolate the line dimension")
        self.write_handover(text)
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)

    def test_approaching_cap_warns_before_the_cap_is_reached(self):
        # 85 % of the byte cap: past the warn threshold, still under the cap itself.
        self.write_handover(handover_of_size(int(DEFAULT_CAP_BYTES * 0.85)))
        result = self.run_hook("SessionStart", source="startup")
        warnings = self.size_warnings(result)
        self.assertEqual(1, len(warnings), result.stderr)
        self.assertIn("approaching", warnings[0].lower())

    def test_just_below_the_warn_threshold_is_silent(self):
        # 70 % of the byte cap: comfortably below the threshold, must not warn.
        self.write_handover(handover_of_size(int(DEFAULT_CAP_BYTES * 0.70)))
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual([], self.size_warnings(result))

    def test_warning_reports_size_cap_and_percentage(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook("SessionStart", source="startup")
        line = self.size_warnings(result)[0]
        self.assertIn("%", line, "a warning without a number is one the reader must go and check")
        self.assertIn("KB", line)
        self.assertIn("lines", line)

    def test_warning_names_the_remedy(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook("SessionStart", source="startup")
        self.assertIn("/cleanup", self.size_warnings(result)[0])

    def test_over_cap_logs_a_structured_error_event(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        self.run_hook("SessionStart", source="startup")
        events = [e for e in self.error_events() if e.get("event") == "HandoverSize"]
        self.assertEqual(1, len(events), self.error_events())
        entry = events[0]
        self.assertEqual("SessionStart", entry.get("source"))
        self.assertEqual(DEFAULT_CAP_BYTES, entry.get("cap_bytes"))
        self.assertEqual(DEFAULT_CAP_LINES, entry.get("cap_lines"))
        self.assertEqual("over", entry.get("level"))
        self.assertGreater(entry.get("bytes", 0), DEFAULT_CAP_BYTES)


class DeclaredCapTest(HandoverSizeHookTestCase):
    """The file's own header wins over the template default, as /cleanup §2 specifies."""

    def test_header_declared_smaller_byte_cap_is_honoured(self):
        header = (
            "# Handover – Work State\n"
            "\n"
            "> **Size cap**: keep it ≤2 KB (~40 lines).\n"
            "\n"
        )
        # 2.5 KB: over the declared 2 KB cap, well under the 5 KB default.
        self.write_handover(handover_of_size(2560, header=header))
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)
        entry = [e for e in self.error_events() if e.get("event") == "HandoverSize"][0]
        self.assertEqual(2 * 1024, entry.get("cap_bytes"))
        self.assertEqual(40, entry.get("cap_lines"))

    def test_header_declared_larger_cap_suppresses_the_default_warning(self):
        header = (
            "# Handover – Work State\n"
            "\n"
            "> **Size cap**: keep it ≤20 KB (~600 lines).\n"
            "\n"
        )
        # 6 KB: over the 5 KB default, far under the declared 20 KB cap.
        self.write_handover(handover_of_size(6 * 1024, header=header))
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual([], self.size_warnings(result))

    def test_missing_header_falls_back_to_the_template_default(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600, header="# Handover\n\n"))
        self.run_hook("SessionStart", source="startup")
        entry = [e for e in self.error_events() if e.get("event") == "HandoverSize"][0]
        self.assertEqual(DEFAULT_CAP_BYTES, entry.get("cap_bytes"))
        self.assertEqual(DEFAULT_CAP_LINES, entry.get("cap_lines"))

    def test_a_cap_mentioned_deep_in_the_body_is_not_read_as_the_cap(self):
        # A body line quoting a different threshold must not redefine the file's own cap.
        # Short lines put the note far past the header window — the fixture has to make the
        # word "deep" true, otherwise it only re-tests the header parse.
        text = handover_of_lines(DEFAULT_CAP_LINES + 20, header="# Handover\n\n")
        text += "\nNote: doc-volume-check flags files ≤50 KB differently.\n"
        self.assertGreater(text.splitlines().index(text.splitlines()[-1]), 150,
                           "the quoted threshold must sit well below the header window")
        self.write_handover(text)
        self.run_hook("SessionStart", source="startup")
        entry = [e for e in self.error_events() if e.get("event") == "HandoverSize"][0]
        self.assertEqual(DEFAULT_CAP_BYTES, entry.get("cap_bytes"))


class CapParserToleranceTest(HandoverSizeHookTestCase):
    """parse_handover_cap was deliberately given tolerances every other fixture in this
    file happens not to exercise, because they all use the canonical header shape. Each
    test here departs from that shape on exactly the one dimension it pins.
    """

    def test_a_cap_declared_past_a_narrower_header_window_is_still_honoured(self):
        """The header window is 20 lines; a longer preamble must not push the
        declaration out of it. Only the *lower* bound of that window (a regression to
        e.g. 5 lines) is at risk — a widening is already caught by the deep-body test
        above — so the preamble here is built to land the declaration on line 8: past a
        5-line window, comfortably inside the real 20-line one.
        """
        header = (
            "# Handover – Work State\n"
            "\n"
            "## Context\n"
            "Preamble line 1.\n"
            "Preamble line 2.\n"
            "Preamble line 3.\n"
            "\n"
            "> **Size cap**: keep it ≤2 KB (~40 lines).\n"
            "\n"
        )
        cap_line_index = [i for i, line in enumerate(header.splitlines()) if "Size cap" in line][0]
        self.assertGreaterEqual(cap_line_index, 5,
                                "fixture must place the declaration past a 5-line window")
        self.assertLess(cap_line_index, 20,
                        "fixture must still land inside the real 20-line window")
        # 2.5 KB: over the declared 2 KB cap, well under the 5 KB default fallback.
        self.write_handover(handover_of_size(2560, header=header))
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)
        entry = [e for e in self.error_events() if e.get("event") == "HandoverSize"][0]
        self.assertEqual(2 * 1024, entry.get("cap_bytes"))

    def test_the_kb_unit_is_matched_case_insensitively(self):
        """The shipped template writes "KB"; the parser must not silently stop
        recognising a header that writes "kb" instead."""
        header = (
            "# Handover – Work State\n"
            "\n"
            "> **Size cap**: keep it ≤2 kb (~40 lines).\n"
            "\n"
        )
        # 2.5 KB: over the declared 2 KB cap, well under the 5 KB default fallback.
        self.write_handover(handover_of_size(2560, header=header))
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)
        entry = [e for e in self.error_events() if e.get("event") == "HandoverSize"][0]
        self.assertEqual(2 * 1024, entry.get("cap_bytes"))

    def test_a_handover_with_invalid_utf8_bytes_still_gets_size_checked(self):
        """The decode guard (errors="replace") must not be removable.

        Without it, an undecodable HANDOVER would raise inside check_handover_size's own
        try/except, which silently swallows the exception -- the exit code is 0 either
        way, so only the warning going missing tells the two states apart. The invalid
        lead bytes below decode to U+FFFD replacement characters and do not match any
        cap-declaration pattern, so this exercises the fallback-to-default path together
        with the guard.
        """
        raw = b"\xff\xfe" + b"x" * (DEFAULT_CAP_BYTES + 600)
        (self.project / "docs" / "HANDOVER.md").write_bytes(raw)
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual(0, result.returncode)
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)

    def test_a_file_missing_its_trailing_newline_still_crosses_its_line_cap(self):
        """The trailing-partial-line increment in the line count must not be dropped.

        A file whose last line has no terminating newline has one fewer "\\n" than its
        true line count; without the +1 correction a 200-line file would report 199 and
        read as "approaching" instead of "over" its declared 200-line cap.
        """
        header = (
            "# Handover – Work State\n"
            "\n"
            f"> **Size cap**: keep it ≤5 KB (~{DECLARED_LINE_CAP} lines).\n"
            "\n"
        )
        text = handover_of_lines(DECLARED_LINE_CAP - header.count("\n"), header=header)
        self.assertEqual(DECLARED_LINE_CAP, text.count("\n"),
                         "fixture must land on the exact declared line cap")
        text = text[:-1]  # strip the final line's trailing newline
        self.assertFalse(text.endswith("\n"))
        self.assertLess(len(text.encode("utf-8")), DEFAULT_CAP_BYTES,
                        "fixture must isolate the line dimension")
        self.write_handover(text)
        result = self.run_hook("SessionStart", source="startup")
        entry = [e for e in self.error_events() if e.get("event") == "HandoverSize"][0]
        self.assertEqual("over", entry.get("level"), result.stderr)


# === Does it stay quiet when it must? ============================================

class SilenceTest(HandoverSizeHookTestCase):

    def test_no_handover_is_a_silent_no_op(self):
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual([], self.size_warnings(result))
        self.assertEqual(0, result.returncode)

    def test_no_docs_directory_is_a_silent_no_op(self):
        bare = self.tmp / "bare"
        bare.mkdir()
        result = self.run_hook("SessionStart", source="startup", cwd=bare)
        self.assertEqual([], self.size_warnings(result))
        self.assertEqual(0, result.returncode)

    def test_warns_once_per_session_and_event(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        first = self.run_hook("SessionStart", source="startup")
        second = self.run_hook("SessionStart", source="startup")
        self.assertEqual(1, len(self.size_warnings(first)), first.stderr)
        self.assertEqual([], self.size_warnings(second), second.stderr)

    def test_a_fresh_session_warns_again(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        self.run_hook("SessionStart", source="startup")
        other = self.run_hook("SessionStart", session_id=f"test-{uuid.uuid4().hex[:12]}",
                              source="startup")
        self.assertEqual(1, len(self.size_warnings(other)), other.stderr)

    def test_escalation_from_approaching_to_over_is_not_swallowed(self):
        """The dedup must not silence a genuine escalation inside one session."""
        self.write_handover(handover_of_size(int(DEFAULT_CAP_BYTES * 0.85)))
        first = self.run_hook("PostToolUse", tool_name="Edit",
                              tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")})
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        second = self.run_hook("PostToolUse", tool_name="Edit",
                               tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")})
        self.assertIn("approaching", self.size_warnings(first)[0].lower())
        self.assertEqual(1, len(self.size_warnings(second)), second.stderr)
        self.assertNotIn("approaching", self.size_warnings(second)[0].lower())

    def test_session_start_and_post_tool_use_each_warn_in_the_same_session(self):
        """The dedup key is (session, source_event, level) — source_event is part of it.

        A SessionStart warning must not suppress the PostToolUse warning that follows in
        the same session, and vice versa: they are two different moments a human could
        plausibly see, on two different surfaces (a session boot vs. a live edit).
        Dropping source_event from the dedup key would collapse both onto one slot and
        the second call would go silent.
        """
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        first = self.run_hook("SessionStart", source="startup")
        second = self.run_hook(
            "PostToolUse", tool_name="Edit",
            tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")})
        self.assertEqual(1, len(self.size_warnings(first)), first.stderr)
        self.assertEqual(1, len(self.size_warnings(second)), second.stderr)


class EventScopeTest(HandoverSizeHookTestCase):
    """Only the deliberately chosen events run the check."""

    def handover_edit_payload(self):
        return {"tool_name": "Edit",
                "tool_input": {"file_path": str(self.project / "docs" / "HANDOVER.md")}}

    def test_post_tool_use_on_a_handover_write_warns(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook("PostToolUse", **self.handover_edit_payload())
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)

    def test_post_tool_use_on_an_unrelated_file_is_silent(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook("PostToolUse", tool_name="Edit",
                               tool_input={"file_path": str(self.project / "docs" / "BACKLOG.md")})
        self.assertEqual([], self.size_warnings(result))

    def test_post_tool_use_of_a_read_on_the_handover_is_silent(self):
        """Reading the file does not change its size — no reason to re-check."""
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook("PostToolUse", tool_name="Read",
                               tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")})
        self.assertEqual([], self.size_warnings(result))

    def test_pre_tool_use_does_not_run_the_check(self):
        """Before the write the number would be stale; the check belongs after it."""
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook("PreToolUse", **self.handover_edit_payload())
        self.assertEqual([], self.size_warnings(result))

    def test_a_handover_backup_file_is_silent(self):
        """docs/HANDOVER.md.bak must not count as a HANDOVER write.

        Pins exact-basename comparison against a substring-match relaxation: the real,
        over-cap docs/HANDOVER.md sits on disk throughout, so a gate that answered "yes"
        to the .bak suffix would surface as a warning here, not only as a missing
        exception.
        """
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook(
            "PostToolUse", tool_name="Edit",
            tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md.bak")})
        self.assertEqual([], self.size_warnings(result))

    def test_a_handover_prefixed_file_is_silent(self):
        """docs/xHANDOVER.md must not count as a HANDOVER write either.

        Same pin as the .bak case, from the other side: "HANDOVER.md" is a substring of
        "xHANDOVER.md" too, so a substring-match relaxation would catch this shape while
        missing the .bak one, or vice versa, depending on which side of the match it
        checks. Both must stay silent under the exact-basename comparison.
        """
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook(
            "PostToolUse", tool_name="Edit",
            tool_input={"file_path": str(self.project / "docs" / "xHANDOVER.md")})
        self.assertEqual([], self.size_warnings(result))


class WriteGateCoverageTest(HandoverSizeHookTestCase):
    """Every tool declared in HANDOVER_WRITE_TOOLS actually triggers the size check.

    Before this test class, only "Edit" was exercised by a test that asserts the size
    warning itself; "Write", "MultiEdit" and "NotebookEdit" were declared in the set but
    never independently verified. Reducing HANDOVER_WRITE_TOOLS to {"Edit"} left every
    test in this file green (confirmed 18.08.2026) — a set lookup on an untested tool
    name is a gap the exit-code-only NeverBlocksTest cases cannot see, because the hook
    never blocks in either world.
    """

    def test_write_on_the_handover_warns(self):
        """The full-rewrite case: what a compaction pass actually does to HANDOVER.md."""
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook(
            "PostToolUse", tool_name="Write",
            tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")})
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)

    def test_multiedit_on_the_handover_warns(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook(
            "PostToolUse", tool_name="MultiEdit",
            tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")})
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)

    def test_notebookedit_on_the_handover_warns(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        result = self.run_hook(
            "PostToolUse", tool_name="NotebookEdit",
            tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")})
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)

    def test_every_declared_write_tool_warns(self):
        """Data-driven over HANDOVER_WRITE_TOOLS itself, so a tool added to the set in
        the future is exercised automatically instead of staying silent until someone
        remembers to add a named test for it."""
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))
        for tool_name in sorted(AGENT_MONITOR.HANDOVER_WRITE_TOOLS):
            with self.subTest(tool_name=tool_name):
                result = self.run_hook(
                    "PostToolUse", tool_name=tool_name,
                    tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")},
                    session_id=f"test-{uuid.uuid4().hex[:12]}")
                self.assertEqual(1, len(self.size_warnings(result)), result.stderr)


# === Does it ever block? =========================================================

class NeverBlocksTest(HandoverSizeHookTestCase):

    def test_exit_code_is_zero_over_cap(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES * 4))
        self.assertEqual(0, self.run_hook("SessionStart", source="startup").returncode)

    def test_exit_code_is_zero_on_a_handover_that_cannot_be_decoded(self):
        (self.project / "docs" / "HANDOVER.md").write_bytes(b"\xff\xfe\x00binary\x00")
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual(0, result.returncode)

    def test_exit_code_is_zero_when_the_handover_is_an_unreadable_directory(self):
        (self.project / "docs" / "HANDOVER.md").mkdir()
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual(0, result.returncode)

    def test_exit_code_is_zero_on_a_handover_write_post_tool_use(self):
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES * 4))
        result = self.run_hook("PostToolUse", tool_name="Write",
                               tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")})
        self.assertEqual(0, result.returncode)


# === Does the gate contain its own input? ========================================

class MalformedPayloadTest(HandoverSizeHookTestCase):
    """`is_handover_write` must answer "no" to junk, not raise.

    The hook never blocks either way — main()'s catch-all swallows the exception and the
    exit code stays 0. What is lost is quieter and worse: the check silently does not run,
    and the incident is filed as a MonitorError, i.e. as a defect of the monitor rather
    than as a payload it declined. The sibling `check_handover_size` contains its own
    input; this gate has to as well.

    An over-cap HANDOVER is on disk in every case, so a gate that wrongly said "yes" would
    be visible as a warning, not only as a missing exception.
    """

    def setUp(self):
        super().setUp()
        self.write_handover(handover_of_size(DEFAULT_CAP_BYTES + 600))

    def assert_declined_quietly(self, result):
        self.assertEqual(0, result.returncode)
        self.assertEqual([], self.size_warnings(result), result.stderr)
        self.assertEqual([], self.monitor_error_events(),
                         "a malformed payload is not a monitor defect")

    def test_non_string_file_path_is_not_a_handover_write(self):
        result = self.run_hook("PostToolUse", tool_name="Edit", tool_input={"file_path": 42})
        self.assert_declined_quietly(result)

    def test_non_dict_tool_input_is_not_a_handover_write(self):
        result = self.run_hook("PostToolUse", tool_name="Edit", tool_input="not-a-dict")
        self.assert_declined_quietly(result)

    def test_null_tool_input_is_not_a_handover_write(self):
        result = self.run_hook("PostToolUse", tool_name="Edit", tool_input=None)
        self.assert_declined_quietly(result)

    def test_missing_tool_input_is_not_a_handover_write(self):
        result = self.run_hook("PostToolUse", tool_name="Edit")
        self.assert_declined_quietly(result)

    def test_unhashable_tool_name_is_not_a_handover_write(self):
        """The tool-name half of the gate is a set lookup, so it has the same exposure."""
        result = self.run_hook("PostToolUse", tool_name=["Edit"],
                               tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")})
        self.assert_declined_quietly(result)

    def test_a_valid_payload_still_warns(self):
        """Containment must not be bought by making the gate say no to everything."""
        result = self.run_hook("PostToolUse", tool_name="Edit",
                               tool_input={"file_path": str(self.project / "docs" / "HANDOVER.md")})
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)


# === Are the constants pinned? ===================================================

class ThresholdDerivationTest(HandoverSizeHookTestCase):
    """Pins HANDOVER_WARN_PCT to the measurement it was derived from.

    The behavioural tests above bracket the threshold loosely (85 % warns, 70 % is silent),
    which leaves every value from 71 to 85 green. That is not a pin: the number came from a
    measurement — one skill run grows the file by SINGLE_RUN_GROWTH_BYTES — and the whole
    point is that the warning fires at the last moment at which it is still preventive. A
    threshold any higher means the next run breaches the cap unannounced.

    The pin is the pair of boundary cases, not a literal. **The step between them is one
    percentage point, not one run's growth**: the constant is expressed in percent, so a
    growth-sized step (~20 pp) would still leave 71–80 free. One pp on each side of the
    derived value is the smallest step that can move the constant, and therefore the only
    step that pins it exactly. The two-growth-steps case the derivation also implies is
    covered by monotonicity — a smaller file cannot warn once the larger one is silent.
    """

    def test_the_last_preventive_moment_warns(self):
        # cap minus one run's growth == DERIVED_WARN_PCT of the cap.
        self.assertEqual(DERIVED_WARN_PCT,
                         round(100 * (DEFAULT_CAP_BYTES - SINGLE_RUN_GROWTH_BYTES) / DEFAULT_CAP_BYTES),
                         "fixture arithmetic must follow the documented derivation")
        self.write_handover(handover_at_pct(DERIVED_WARN_PCT))
        result = self.run_hook("SessionStart", source="startup")
        warnings = self.size_warnings(result)
        self.assertEqual(1, len(warnings),
                         f"a file one run's growth below the cap must warn; stderr={result.stderr}")
        self.assertIn("approaching", warnings[0].lower())
        entry = [e for e in self.error_events() if e.get("event") == "HandoverSize"][0]
        self.assertEqual(DERIVED_WARN_PCT, entry.get("pct_of_cap"),
                         "the fixture must land exactly on the threshold, not merely above it")

    def test_one_step_below_the_last_preventive_moment_is_silent(self):
        self.write_handover(handover_at_pct(DERIVED_WARN_PCT - 1))
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual([], self.size_warnings(result),
                         "warning earlier than the derivation allows makes the threshold arbitrary")
        self.assertEqual([], [e for e in self.error_events() if e.get("event") == "HandoverSize"])


class RoundingBoundaryTest(HandoverSizeHookTestCase):
    """The level is decided on the exact counts; only the report is rounded.

    Rounding is a presentation concern. Let it decide the level and half a percentage
    point on each side of every boundary is classified wrongly: against the 5120 B cap
    every file from 5095 B up rounds to 100 % and is announced as "Over cap" although
    it is legally under it. /cleanup section 2 computes the same percentage from the
    same numbers and calls that file *approaching* — two checks contradicting each other
    about one file is worse than either of them staying silent.

    The band is one rounding step wide (25 B here), so it sits entirely inside a single
    percentage point and no whole-percentage fixture can reach it; these tests are
    byte-exact for that reason. Both boundaries are pinned from both sides, and the line
    dimension separately: it needs a declared cap to have a band at all.
    """

    # --- helpers -----------------------------------------------------------------

    def write_handover_of_exactly(self, size_bytes: int):
        text = handover_of_exact_size(size_bytes)
        self.assertEqual(size_bytes, len(text.encode("utf-8")),
                         "a fixture that only lands near the boundary cannot pin it")
        self.write_handover(text)

    def size_event(self, result=None):
        """The structured HandoverSize event, or None when the check stayed silent."""
        events = [e for e in self.error_events() if e.get("event") == "HandoverSize"]
        self.assertLessEqual(len(events), 1, events)
        return events[0] if events else None

    def assert_level(self, result, expected):
        entry = self.size_event(result)
        self.assertIsNotNone(entry, f"expected a {expected} warning; stderr={result.stderr}")
        self.assertEqual(expected, entry.get("level"), result.stderr)
        self.assertEqual(1, len(self.size_warnings(result)), result.stderr)
        return entry

    # --- the cap boundary --------------------------------------------------------

    def test_a_file_just_under_the_cap_that_rounds_to_100_is_approaching(self):
        """The reported defect: 5097 B against a 5120 B cap is 99.55 %, not a breach."""
        self.write_handover_of_exactly(JUST_UNDER_CAP_BYTES)
        result = self.run_hook("SessionStart", source="startup")
        self.assert_level(result, "approaching")
        self.assertNotIn("over cap", self.size_warnings(result)[0].lower())

    def test_the_last_byte_under_the_cap_is_still_approaching(self):
        """The far end of the same band — 5119 B is 99.98 %, and still under the cap."""
        self.write_handover_of_exactly(LAST_BYTE_UNDER_CAP_BYTES)
        result = self.run_hook("SessionStart", source="startup")
        self.assert_level(result, "approaching")

    def test_a_file_exactly_at_the_cap_is_over(self):
        """The other side of the boundary: the fix must not buy itself an off-by-one."""
        self.write_handover_of_exactly(DEFAULT_CAP_BYTES)
        result = self.run_hook("SessionStart", source="startup")
        self.assert_level(result, "over")
        self.assertIn("over cap", self.size_warnings(result)[0].lower())

    # --- the approaching boundary ------------------------------------------------

    def test_a_file_just_under_the_warn_threshold_that_rounds_onto_it_is_silent(self):
        """Same defect one threshold down: 4071 B is 79.51 %, below the 80 % trigger."""
        self.write_handover_of_exactly(JUST_UNDER_WARN_BYTES)
        result = self.run_hook("SessionStart", source="startup")
        self.assertEqual([], self.size_warnings(result), result.stderr)
        self.assertIsNone(self.size_event(result))

    def test_a_file_exactly_on_the_warn_threshold_warns(self):
        self.write_handover_of_exactly(AT_WARN_BYTES)
        result = self.run_hook("SessionStart", source="startup")
        self.assert_level(result, "approaching")

    # --- the report --------------------------------------------------------------

    def test_the_reported_percentage_stays_the_rounded_number(self):
        """Deciding on the exact ratio must not push the exact ratio into the message.

        The rounded percentage is what a reader can check against the KB figure next to
        it; 99.5507812 % in a warning line is noise. So the same file reads "100 % of
        the 5 KB cap" and is still classified as approaching — the number describes the
        size, the verdict describes the level.
        """
        self.write_handover_of_exactly(JUST_UNDER_CAP_BYTES)
        result = self.run_hook("SessionStart", source="startup")
        entry = self.assert_level(result, "approaching")
        self.assertIn("100 % of the 5 KB cap", self.size_warnings(result)[0])
        self.assertEqual(100, entry.get("pct_of_cap"))

    # --- the line dimension ------------------------------------------------------

    def declared_line_cap_header(self):
        return (
            "# Handover – Work State\n"
            "\n"
            f"> **Size cap**: keep it \u22645 KB (~{DECLARED_LINE_CAP} lines).\n"
            "\n"
        )

    def write_handover_of_lines(self, total_lines: int):
        header = self.declared_line_cap_header()
        text = handover_of_lines(total_lines - header.count("\n"), header=header)
        self.assertEqual(total_lines, text.count("\n"),
                         "the fixture must land on the exact line count")
        self.assertLess(len(text.encode("utf-8")), DEFAULT_CAP_BYTES,
                        "fixture must isolate the line dimension")
        self.write_handover(text)

    def test_the_line_dimension_is_decided_on_the_exact_count_too(self):
        """199 of 200 lines is exactly 99.5 % and rounds up — the same class of error."""
        self.write_handover_of_lines(DECLARED_LINE_CAP - 1)
        result = self.run_hook("SessionStart", source="startup")
        entry = self.assert_level(result, "approaching")
        self.assertEqual(DECLARED_LINE_CAP, entry.get("cap_lines"))

    def test_the_line_dimension_at_its_exact_cap_is_over(self):
        self.write_handover_of_lines(DECLARED_LINE_CAP)
        result = self.run_hook("SessionStart", source="startup")
        self.assert_level(result, "over")

    def test_the_line_dimensions_reported_percentage_is_also_rounded(self):
        """The byte dimension's rounding is pinned above; the line dimension's is not.

        199 of 200 lines is 99.5 % exactly. round(99.5) is 100 (round-half-to-even
        picks the even neighbour); int(99.5) truncates to 99. Both give "approaching"
        as the level (decided on the exact ratio, not on this field), so only a direct
        assertion on pct_of_cap tells the two implementations apart.
        """
        self.write_handover_of_lines(DECLARED_LINE_CAP - 1)
        result = self.run_hook("SessionStart", source="startup")
        entry = self.assert_level(result, "approaching")
        self.assertEqual(100, entry.get("pct_of_cap"))


@unittest.skipUnless(hasattr(os, "mkfifo"), "platform has no FIFOs")
class NonRegularFileGuardTest(HandoverSizeHookTestCase):
    """Pins `is_file()` against a relaxation to `exists()`.

    `exists()` is true for a FIFO, and reading a FIFO with no writer blocks forever — a
    PostToolUse hook that never returns wedges the session rather than warning about it.
    `is_file()` is false for a FIFO, so the check declines before it opens anything.

    The test is bounded by run_hook's timeout: if the guard is ever relaxed this fails with
    a TimeoutExpired-derived message instead of hanging the runner. A test that hangs the
    runner is worse than no test, so the timeout is part of the assertion, not a nicety.
    """

    def make_fifo_handover(self):
        path = self.project / "docs" / "HANDOVER.md"
        try:
            os.mkfifo(path)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"cannot create a FIFO here: {exc}")
        return path

    def test_a_fifo_named_handover_is_declined_without_reading_it(self):
        self.make_fifo_handover()
        try:
            result = self.run_hook("SessionStart", source="startup")
        except subprocess.TimeoutExpired:
            self.fail(
                f"the hook blocked for {HOOK_TIMEOUT_S}s on a FIFO named HANDOVER.md — the "
                "check opened a non-regular file, i.e. the is_file() guard is gone"
            )
        self.assertEqual(0, result.returncode)
        self.assertEqual([], self.size_warnings(result), result.stderr)
        self.assertEqual([], self.monitor_error_events())

    def test_a_fifo_handover_write_post_tool_use_is_declined(self):
        """The PostToolUse path is the one that runs on every write, so pin it too."""
        path = self.make_fifo_handover()
        try:
            result = self.run_hook("PostToolUse", tool_name="Write",
                                   tool_input={"file_path": str(path)})
        except subprocess.TimeoutExpired:
            self.fail(
                f"the hook blocked for {HOOK_TIMEOUT_S}s after a write to a FIFO named "
                "HANDOVER.md — the is_file() guard is gone"
            )
        self.assertEqual(0, result.returncode)
        self.assertEqual([], self.size_warnings(result), result.stderr)


if __name__ == "__main__":
    unittest.main()
