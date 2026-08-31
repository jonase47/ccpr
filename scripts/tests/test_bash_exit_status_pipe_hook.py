"""test_bash_exit_status_pipe_hook.py -- End-to-end tests for the PreToolUse check that
warns when a Bash command reads an exit status a pipe has already taken away.

## The defect this guards against

Two real incidents in one session, both in commands whose ONLY purpose was to read an
exit code -- and in both, the exit status actually read belonged to the wrong process:

    bash install.sh --verify 2>&1 | tail -6; echo "EXIT=$?"
    -- reported 0. The true exit was 3. `$?` belonged to `tail`, not to `install.sh`.

    gh run watch <id> --exit-status --interval 20 2>&1 | tail -15
    -- the harness read the whole command's exit status as 0 (a green run) although CI
    had in fact failed. `--exit-status` was rendered inert by the pipe to `tail`.

A prose checklist line for this already existed and did not prevent the second instance.
This hook is the only place that can reach an interactive command before it runs.

## Design constraint the fixtures encode

False positives cost more than false negatives here (PO directive): a hook that warns on
every other pipe is ignored within a week. So this file weighs its two halves equally --
positives (the two historical commands, plus the `&&`/`||`-chain and `grep -q` shapes the
detector also claims to cover) and negative controls (ordinary pipes, the *correct* fixed
form, and the two legitimate pipe/exit-status idioms: `pipefail` and `PIPESTATUS`).

## Fixture design

Follows test_handover_size_hook.py's shape: drives the real entry point
(`python3 hooks/agent-monitor.py`) as a subprocess with a crafted PreToolUse payload on
stdin, rather than importing internals for behaviour -- that keeps the payload shape, the
stderr rendering and above all the exit code (an advisory check that ever blocks would be
worse than useless on an interactive Bash call) inside the test surface. HOME is
redirected to a throwaway directory so a run never touches the developer's own
~/.claude/logs/**.

The tests are grouped by the question they answer:

* **Does it fire on the real incidents?** -- both historical commands, verbatim.
* **Does it fire on the other claimed shapes?** -- the `&&`/`||` chain and the masked
  `grep -q` case, each isolated from the historical commands so they are not free rides.
* **Does it stay quiet when it must?** -- ordinary pipes, the corrected form, `pipefail`,
  `PIPESTATUS`, and a flag with no pipe after it.
* **Does it ever block?** -- exit code across every state above, including malformed
  input.
* **Does the gate contain its own input?** -- a non-string / missing `command` must read
  as "nothing to check", not as an internal monitor error.
"""

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

# Every hook run is bounded so a guard regression that makes the hook block turns into a
# failing test instead of a wedged test runner (mirrors test_handover_size_hook.py).
HOOK_TIMEOUT_S = 10

# The exact header line printed once per check_bash_exit_status_pipe_loss invocation --
# NOT the looser substring "exit status", which also occurs inside individual finding
# bullets (e.g. "...the flag's exit status is lost..."), so counting THAT would count
# bullets, not warnings, and a single-invocation, two-finding command would look like two
# separate warnings instead of one.
MARKER = "Exit status behind a pipe:"

# The two commands actually seen in the field. Verbatim, per the briefing.
HISTORICAL_INSTALL_VERIFY = 'bash install.sh --verify 2>&1 | tail -6; echo "EXIT=$?"'
HISTORICAL_GH_RUN_WATCH = "gh run watch 12345 --exit-status --interval 20 2>&1 | tail -15"


class BashExitStatusPipeHookTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-exit-status-pipe-hook-"))
        self.project = self.tmp / "project"
        self.project.mkdir(parents=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.session_id = f"test-{uuid.uuid4().hex[:12]}"

    def tearDown(self):
        loop_state = Path(f"/tmp/claude-loop-{self.session_id}.json")
        if loop_state.exists():
            loop_state.unlink()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- helpers -----------------------------------------------------------------

    def run_bash_command(self, command, timeout=HOOK_TIMEOUT_S):
        """Drives agent-monitor.py with one PreToolUse(Bash) payload."""
        body = {
            "hook_event_name": "PreToolUse",
            "session_id": self.session_id,
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        return subprocess.run(
            ["python3", str(HOOK_PATH)],
            input=json.dumps(body),
            cwd=str(self.project),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def run_raw_payload(self, payload, timeout=HOOK_TIMEOUT_S):
        """Drives agent-monitor.py with an arbitrary, possibly malformed, payload."""
        body = {"hook_event_name": "PreToolUse", "session_id": self.session_id}
        body.update(payload)
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        return subprocess.run(
            ["python3", str(HOOK_PATH)],
            input=json.dumps(body),
            cwd=str(self.project),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def pipe_warnings(self, result):
        return [line for line in result.stderr.splitlines() if MARKER in line]

    def monitor_error_events(self):
        log = self.home / ".claude" / "logs" / "sessions" / "monitor-internal" / "errors.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


# === Does it fire on the real incidents? =========================================

class HistoricalIncidentTest(BashExitStatusPipeHookTestCase):

    def test_install_verify_piped_into_tail_then_dollar_question_warns(self):
        result = self.run_bash_command(HISTORICAL_INSTALL_VERIFY)
        warnings = self.pipe_warnings(result)
        self.assertEqual(1, len(warnings), result.stderr)

    def test_gh_run_watch_exit_status_flag_piped_into_tail_warns(self):
        result = self.run_bash_command(HISTORICAL_GH_RUN_WATCH)
        warnings = self.pipe_warnings(result)
        self.assertEqual(1, len(warnings), result.stderr)


# === Does it fire on the other claimed shapes? ===================================

class OtherPositiveShapesTest(BashExitStatusPipeHookTestCase):

    def test_pipe_chained_with_double_ampersand_warns(self):
        """`… | … && …` -- `&&` reacts to the pipe's LAST stage, not the piped command."""
        result = self.run_bash_command("install.sh --verify 2>&1 | tail -6 && echo done")
        self.assertEqual(1, len(self.pipe_warnings(result)), result.stderr)

    def test_pipe_chained_with_double_pipe_warns(self):
        result = self.run_bash_command("install.sh --verify 2>&1 | tail -6 || echo failed")
        self.assertEqual(1, len(self.pipe_warnings(result)), result.stderr)

    def test_exit_variable_assignment_form_warns(self):
        """The other quoted historical shape: `EXIT=$?` instead of `echo $?`."""
        result = self.run_bash_command("mycmd 2>&1 | tail -20; EXIT=$?")
        self.assertEqual(1, len(self.pipe_warnings(result)), result.stderr)

    def test_grep_quiet_masked_by_a_further_pipe_stage_warns(self):
        """`producer | grep -q pattern | consumer` -- grep -q is not the pipe's last
        stage, so its own exit status never reaches whatever reads $? afterward."""
        result = self.run_bash_command("producer | grep -q pattern | consumer")
        self.assertEqual(1, len(self.pipe_warnings(result)), result.stderr)

    def test_grep_quiet_piped_into_cat_warns(self):
        """`grep -q foo file | cat` -- same shape as above, named after the exact form
        in the briefing's red proof."""
        result = self.run_bash_command("grep -q foo file | cat")
        self.assertEqual(1, len(self.pipe_warnings(result)), result.stderr)

    def test_pipe_into_wc_then_dollar_question_warns(self):
        """`cat f | wc -l; echo $?` -- `wc` is not a status test, so `$?` still belongs
        to it, not to `cat f`. Rule 1's own shape, named after the briefing's red proof
        (distinct from the historical `tail` case so rule 1 is not a free ride off it)."""
        result = self.run_bash_command("cat f | wc -l; echo $?")
        self.assertEqual(1, len(self.pipe_warnings(result)), result.stderr)

    def test_pipe_into_sed_chained_with_double_ampersand_warns(self):
        """`cat f | sed -n 1p && echo weiter` -- `sed` is not a status test, so `&&`
        reacts to it, not to `cat f`."""
        result = self.run_bash_command("cat f | sed -n 1p && echo weiter")
        self.assertEqual(1, len(self.pipe_warnings(result)), result.stderr)


# === Does the status-test regex correctly reject near-miss command names? ========
#
# `_STATUS_TEST_LAST_STAGE_RE` matches `diff`/`cmp`/... with a `\b` terminator so the
# match stops at the command name and does not also swallow a command that merely
# STARTS WITH one of those names. These are negative controls for the MATCHER, not for
# the detector: `diff3`, `diffstat` and `cmpfoo` must NOT be recognised as status
# tests, so the pipe's last stage stays a plain output consumer and rule 2 still warns
# on the `&&` chain. Each held under direct hook invocation before this class existed;
# locked here so weakening the `\b` terminator turns red instead of silently drifting.

class StatusTestRegexWordBoundaryTest(BashExitStatusPipeHookTestCase):

    def test_diff3_is_not_mistaken_for_diff_and_still_warns(self):
        result = self.run_bash_command("cat a | diff3 x y && echo drei")
        self.assertEqual(1, len(self.pipe_warnings(result)), result.stderr)

    def test_diffstat_is_not_mistaken_for_diff_and_still_warns(self):
        result = self.run_bash_command("cat a | diffstat && echo stat")
        self.assertEqual(1, len(self.pipe_warnings(result)), result.stderr)

    def test_cmpfoo_is_not_mistaken_for_cmp_and_still_warns(self):
        result = self.run_bash_command("cat a | cmpfoo b && echo x")
        self.assertEqual(1, len(self.pipe_warnings(result)), result.stderr)


# === Does it stay quiet when the pipe's last stage is itself a status test? ======
#
# Confirmed false positive (measured by direct hook invocation before this narrowing
# existed): shape 2 used to treat "pipeline followed by &&/||" as sufficient on its own,
# without asking what the pipe's LAST stage actually was. When that last stage is itself
# a status-producing test (`grep -q`, `cmp -s`, `diff -q`, `test`, `[`, `[[`), the
# pipeline's exit status IS that test's status -- exactly what `&&`/`||` is supposed to
# read. Each case below was independently confirmed to warn under the pre-narrowing (or,
# for cmp/diff, the pre-widening) code.

class ChainedStatusTestLastStageIsSilentTest(BashExitStatusPipeHookTestCase):

    def test_pipe_ending_in_quiet_grep_chained_with_double_ampersand_is_silent(self):
        result = self.run_bash_command("head -1 f | grep -q x && echo ja")
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_pipe_ending_in_quiet_grep_chained_with_double_pipe_is_silent(self):
        result = self.run_bash_command("cat f | grep -q x || echo nein")
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_for_loop_pipe_into_quiet_grep_chained_with_double_ampersand_is_silent(self):
        """The exact command the orchestrator ran repeatedly in the session that
        commissioned this hook -- and the concrete instance of the false positive."""
        result = self.run_bash_command(
            'for f in commands/*.md; do head -1 "$f" | grep -q \'^---$\' '
            "&& c=$((c+1)); done"
        )
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_pipe_ending_in_cmp_quiet_chained_with_double_ampersand_is_silent(self):
        """`cmp -s` at the pipe's last stage is a status test by the same reasoning as
        bare `grep`: same/different is already `cmp`'s exit code, `-s` only suppresses
        the "differ at byte N" output nobody is reading here."""
        result = self.run_bash_command("cat a | cmp -s - b && echo gleich")
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_pipe_ending_in_diff_quiet_chained_with_double_ampersand_is_silent(self):
        """`diff -q` at the pipe's last stage -- same reasoning as `cmp -s` above."""
        result = self.run_bash_command("cat a | diff -q - b > /dev/null && echo gleich")
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_pipe_ending_in_test_dash_s_chained_with_double_ampersand_is_silent(self):
        """Regression lock: `test -s <file>` at the last stage was already matched by
        the bare `test\\b` branch of the status-test regex before this round."""
        result = self.run_bash_command("cat f | test -s /dev/stdin && echo da")
        self.assertEqual([], self.pipe_warnings(result), result.stderr)


# === Does it stay quiet when a SEQUENCED (not chained) read follows a status-test
# last stage? =======================================================================
#
# Rule 1 (`;`/newline followed by a literal `$?`) had the identical gap rule 2 was
# narrowed for, and was not narrowed in the same round: it warned on
# `head -1 f | grep -q x; echo $?` even though the pipe's last stage is a status test
# and `$?` legitimately belongs to it -- confirmed by direct hook invocation before this
# narrowing existed.

class SequencedStatusTestLastStageIsSilentTest(BashExitStatusPipeHookTestCase):

    def test_pipe_ending_in_quiet_grep_then_dollar_question_is_silent(self):
        result = self.run_bash_command("head -1 f | grep -q x; echo $?")
        self.assertEqual([], self.pipe_warnings(result), result.stderr)


# === Does it stay quiet when it must? =============================================

class NegativeControlTest(BashExitStatusPipeHookTestCase):

    def test_an_ordinary_pipe_with_no_status_read_is_silent(self):
        result = self.run_bash_command("ls | wc -l")
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_output_processing_through_a_pipe_is_silent(self):
        """`grep -c` counts matches; it is not quiet-mode and nothing reads $? after."""
        result = self.run_bash_command("grep -c foo file | head -3")
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_the_corrected_form_is_silent(self):
        """The redirect-then-read form the warning itself recommends must not be
        punished -- otherwise the hook contradicts its own remedy."""
        result = self.run_bash_command('cmd > out.txt 2>&1; echo "EXIT=$?"')
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_a_bare_dollar_question_read_with_no_prior_pipe_is_silent(self):
        result = self.run_bash_command("mycmd; echo $?")
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_pipefail_makes_dollar_question_after_a_pipe_legitimate(self):
        """Diagnosis to verify, not assume (per briefing): under `pipefail` bash reflects
        a failing pipe stage's status in `$?` regardless of its position in the pipe, so
        reading `$?` after a pipe is a correct idiom here, not the historical bug."""
        result = self.run_bash_command(
            'set -o pipefail; bash install.sh --verify 2>&1 | tail -6; echo "EXIT=$?"'
        )
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_pipestatus_read_after_a_pipe_is_silent(self):
        """The other legitimate idiom: reading the array bash always populates, instead
        of `$?`, needs no `pipefail` and must not be flagged either."""
        result = self.run_bash_command(
            'bash install.sh --verify 2>&1 | tail -6; echo "EXIT=${PIPESTATUS[0]}"'
        )
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_exit_status_flag_with_no_pipe_after_it_is_silent(self):
        """Isolates rule 2 from rule 1: the flag alone must not be enough -- a pipe has
        to follow it in the same statement."""
        result = self.run_bash_command("gh run watch 12345 --exit-status --interval 20")
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_a_pipe_character_inside_a_double_quoted_string_is_not_an_operator(self):
        result = self.run_bash_command('echo "a|b" | wc -c')
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_multi_stage_pipe_with_no_status_read_is_silent(self):
        """Three pipe stages, none of them a status read afterward -- the multi-stage
        case must not trip up the last-stage detection added for the &&/|| narrowing."""
        result = self.run_bash_command(
            "git status --short | awk '{print $1}' | sort | uniq -c"
        )
        self.assertEqual([], self.pipe_warnings(result), result.stderr)

    def test_pipe_into_a_python_one_liner_is_silent(self):
        result = self.run_bash_command(
            "gh run view 123 --json jobs | python3 -c 'import json,sys'"
        )
        self.assertEqual([], self.pipe_warnings(result), result.stderr)


# === Does it ever block? ===========================================================

class NeverBlocksTest(BashExitStatusPipeHookTestCase):

    def test_exit_code_is_zero_on_a_positive_match(self):
        result = self.run_bash_command(HISTORICAL_INSTALL_VERIFY)
        self.assertEqual(0, result.returncode)

    def test_exit_code_is_zero_on_a_negative_control(self):
        result = self.run_bash_command("ls | wc -l")
        self.assertEqual(0, result.returncode)

    def test_exit_code_is_zero_on_a_non_bash_tool(self):
        result = self.run_raw_payload({"tool_name": "Read", "tool_input": {"file_path": "x"}})
        self.assertEqual(0, result.returncode)


# === Does the gate contain its own input? =========================================

class MalformedPayloadTest(BashExitStatusPipeHookTestCase):

    def assert_declined_quietly(self, result):
        self.assertEqual(0, result.returncode)
        self.assertEqual([], self.pipe_warnings(result), result.stderr)
        self.assertEqual([], self.monitor_error_events(),
                         "a malformed command is not a monitor defect")

    def test_missing_tool_input_is_declined(self):
        result = self.run_raw_payload({"tool_name": "Bash"})
        self.assert_declined_quietly(result)

    def test_non_string_command_is_declined(self):
        result = self.run_raw_payload({"tool_name": "Bash", "tool_input": {"command": 42}})
        self.assert_declined_quietly(result)

    def test_missing_command_key_is_declined(self):
        result = self.run_raw_payload({"tool_name": "Bash", "tool_input": {}})
        self.assert_declined_quietly(result)

    def test_non_dict_tool_input_is_declined(self):
        result = self.run_raw_payload({"tool_name": "Bash", "tool_input": "not-a-dict"})
        self.assert_declined_quietly(result)

    def test_empty_command_is_declined(self):
        result = self.run_bash_command("")
        self.assert_declined_quietly(result)


if __name__ == "__main__":
    unittest.main()
