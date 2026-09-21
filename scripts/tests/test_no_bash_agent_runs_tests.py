"""test_no_bash_agent_runs_tests.py -- CCP-1182: no command instructs an
agent whose frontmatter `tools:` lacks `Bash` to execute a test suite.

## Why this exists

`agents/qa-tester.md:4` carries `tools: Glob, Grep, Read, Write, Edit` -- no
`Bash` -- and `:133` states it outright: "You have no shell: you cannot run
tests yourself. Analyze test output the orchestrator hands you." Four
commands ordered the opposite: `commands/p6-func-integration.md:28` ("Write
and **run** integration tests"), `commands/p6-func-e2e.md:27`,
`commands/p6-func-regression.md:27`, and `commands/p5-acceptance.md:46`
("Run acceptance tests for the following feature") all delegated to
qa-tester and asked it to execute a suite it has no way to run, then report
pass/fail counts (`commands/p6-func-regression.md:33`'s `Passed | Failed`
columns, `commands/p6-func-integration.md:38`'s "Summary: X passed, Y
failed") that could only be invented. `commands/p7-deploy.md:59` carried the
same shape ("Execute the smoke tests after deployment") for its qa-tester
support delegation, found while building this guard's general sweep (it was
not in CCP-1182's own named list, but is the identical defect).

## What this guard checks, and what it deliberately does not

This module derives which agents lack `Bash` from `agents/*.md`'s own
frontmatter -- never a hard-coded "qa-tester is the one" list, so a future
agent gaining or losing Bash is picked up automatically. It then finds every
delegation block in `commands/*.md` (`## Agent` / `**Type**:` for
single-agent commands, `Delegate ... to the **<agent>** agent:` for
multi-agent commands) and attributes the blockquote (`> ...`) text that
immediately follows each trigger to that specific agent -- not the whole
file, since one command can delegate to several agents with very different
tool access (`p5-polish.md`'s `project-planner` triage step carries no
violation, but its own `senior-developer` execution step two sections later
legitimately says "Run full test suite", and a whole-file scan would
misattribute that line to whichever agent it saw first).

The violation pattern is the verb "run"/"execute" (case-insensitive, so it
catches both a clause-initial "Run regression tests" and a mid-clause "Write
and **run** integration tests") followed within a short window by
"test(s)". Two shapes are deliberately exempted, both pinned by their own
regression test:

- **Exploratory testing** (`ExploratoryIsNotFlaggedTest`): manual/heuristic
  by this project's own QA methodology (`agents/qa-tester.md`'s "For
  Exploratory Testing" section: timebox, charter, freeform protocol), never
  an automated suite a shell executes -- "Run exploratory tests for:
  $ARGUMENTS" (`commands/p6-exploratory.md:40`) is not this defect shape.
- **"How to run tests" as documentation content** (`HowToRunTestsIsNotFlaggedTest`):
  `commands/p4-docs.md` asks tech-writer (no Bash) to WRITE a README section
  explaining "How to run tests, what is tested" to a human reader -- content
  the agent authors, not an instruction it executes itself.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "agents"
COMMANDS_DIR = REPO_ROOT / "commands"

TOOLS_LINE_RE = re.compile(r"^tools:\s*(.+)$", re.MULTILINE)
AGENT_TYPE_RE = re.compile(r"^-?\s*\*\*Type\*\*:\s*([a-z][a-z-]*)\s*$", re.MULTILINE)
DELEGATE_TRIGGER_RE = re.compile(
    r"(?:Delegat\w*[^\n]*?to the|to the)\s+\*\*([a-z][a-z-]*)\*\*\s+agent",
)
BLOCKQUOTE_BLOCK_RE = re.compile(r"(?:^>[^\n]*\n?)+", re.MULTILINE)
# A directive verb aimed at the agent, not a past-tense mention -- "Run" /
# "Execute", capitalised (clause-initial, the shape every real trigger in
# this corpus uses), followed within a short window by "test(s)".
VIOLATION_RE = re.compile(r"\b(?:run|execute)\b(?!-)[^\n]{0,60}?\btests?\b", re.IGNORECASE)


def agents_without_bash():
    """{agent_name: tools_line} for every agents/*.md whose `tools:`
    frontmatter omits Bash -- read from the files themselves, never a
    remembered list, so a future frontmatter change is picked up."""
    result = {}
    for path in sorted(AGENTS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        m = TOOLS_LINE_RE.search(text)
        assert m, f"{path.name} has no `tools:` frontmatter line"
        tools = [t.strip() for t in m.group(1).split(",")]
        if "Bash" not in tools:
            result[path.stem] = m.group(1)
    return result


def _agent_blockquote_blocks(text):
    """[(agent_name, blockquote_text, trigger_offset)] for every delegation
    trigger in a command file's text -- either the single `## Agent` /
    `**Type**:` header (whole-file, single-agent commands) or a
    `Delegate ... to the **<agent>** agent:` trigger (multi-agent commands),
    each paired with the blockquote block immediately following it."""
    blocks = []
    # Multi-agent commands: one blockquote block per trigger.
    triggers = list(DELEGATE_TRIGGER_RE.finditer(text))
    if triggers:
        for trig in triggers:
            after = text[trig.end():]
            bq = BLOCKQUOTE_BLOCK_RE.search(after)
            if bq is None:
                continue
            # A trigger's own blockquote must start at (or near) the top of
            # `after` -- skip stray blockquotes far downstream that belong
            # to a LATER trigger (already covered by that trigger's own
            # match) rather than double-counting them here.
            prefix = after[:bq.start()]
            cleaned_prefix = prefix.strip(" \n:")
            if cleaned_prefix and not cleaned_prefix.startswith("#"):
                continue
            blocks.append((trig.group(1), bq.group(0)))
        return blocks
    # Single-agent commands: `## Agent` / `**Type**:` header, blockquote(s)
    # anywhere under `## Prompt Template`.
    type_match = AGENT_TYPE_RE.search(text)
    if type_match is None:
        return blocks
    agent = type_match.group(1)
    prompt_section = re.search(
        r"^## Prompt Template\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL,
    )
    if prompt_section is None:
        return blocks
    for bq in BLOCKQUOTE_BLOCK_RE.finditer(prompt_section.group(1)):
        blocks.append((agent, bq.group(0)))
    return blocks


def find_violations(commands_dir=None):
    """[(command filename, agent, matched text)] for every no-Bash agent
    instructed, inside its own delegation block, to run/execute a test
    suite. Exploratory-testing mentions are excluded (see module docstring).
    """
    if commands_dir is None:
        commands_dir = COMMANDS_DIR
    no_bash = agents_without_bash()
    findings = []
    for path in sorted(commands_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for agent, block in _agent_blockquote_blocks(text):
            if agent not in no_bash:
                continue
            for m in VIOLATION_RE.finditer(block):
                window = block[max(0, m.start() - 20):m.end() + 20].lower()
                if "exploratory" in window:
                    continue
                # "How to run tests" documents usage for a human reader --
                # it is content the agent WRITES, not an instruction the
                # agent itself executes (commands/p4-docs.md's README
                # outline: "**Tests**: How to run tests, what is tested").
                if "how to" in block[max(0, m.start() - 15):m.start()].lower():
                    continue
                findings.append((path.name, agent, m.group(0)))
    return findings


class NoBashAgentIsInstructedToRunTestsTest(unittest.TestCase):
    def test_no_command_instructs_a_shell_less_agent_to_execute_tests(self):
        findings = find_violations()
        self.assertEqual(
            findings, [],
            "command(s) instruct a Bash-less agent to run/execute tests it "
            "cannot execute: " + "; ".join(
                f"{cmd}: {agent} <- {text!r}" for cmd, agent, text in findings
            ),
        )


class QaTesterHasNoBashPreconditionTest(unittest.TestCase):
    """Pins the precondition the rest of this module relies on."""

    def test_qa_tester_is_in_the_derived_no_bash_set(self):
        self.assertIn("qa-tester", agents_without_bash())

    def test_senior_developer_is_not_in_the_derived_no_bash_set(self):
        # senior-developer DOES carry Bash -- used below as the negative
        # control for the attribution logic (p5-polish.md's own
        # "Run full test suite" line belongs to senior-developer, not the
        # earlier project-planner trigger in the same file).
        self.assertNotIn("senior-developer", agents_without_bash())


class ExploratoryIsNotFlaggedTest(unittest.TestCase):
    def test_run_exploratory_tests_is_not_a_violation(self):
        block = "> Run exploratory tests for: **$ARGUMENTS**\n"
        m = VIOLATION_RE.search(block)
        self.assertIsNotNone(m, "the pattern itself must still match the phrase")
        window = block[max(0, m.start() - 20):m.end() + 20]
        self.assertIn("exploratory", window.lower())


class RunTestsScriptNameIsNotFlaggedTest(unittest.TestCase):
    """`scripts/run-tests.sh` is a filename, not an instruction -- the
    orchestrator-run test-runner commands/p6-func-regression.md etc. now
    cite by name inside the agent's own blockquote (e.g. "already produced
    by the orchestrator, via `scripts/run-tests.sh`"). The hyphen in
    "run-tests" makes it a single compound token, not the verb "run"
    followed by the noun "tests" -- VIOLATION_RE's `(?!-)` after the verb
    excludes it."""

    def test_run_tests_sh_filename_mention_is_not_a_violation(self):
        block = "> Results (already produced by the orchestrator, via `scripts/run-tests.sh`):\n"
        self.assertIsNone(VIOLATION_RE.search(block))


class HowToRunTestsIsNotFlaggedTest(unittest.TestCase):
    """commands/p4-docs.md asks tech-writer (no Bash) to WRITE a README
    section documenting "How to run tests, what is tested" -- content the
    agent authors for a human reader, not an instruction the agent itself
    executes. Regression guard for the false positive this produced before
    the "how to" exclusion was added."""

    def test_how_to_run_tests_in_a_readme_outline_is_not_flagged(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="ccpr-no-bash-runs-tests-") as tmp:
            d = Path(tmp)
            fixture = d / "p9-fake-docs.md"
            fixture.write_text(
                "Delegate the documentation creation to the **tech-writer** agent:\n\n"
                "> Create the project documentation.\n"
                "> - **Tests**: How to run tests, what is tested\n",
                encoding="utf-8",
            )
            self.assertEqual(find_violations(commands_dir=d), [])


class AttributionDoesNotBleedAcrossDelegationsTest(unittest.TestCase):
    """p5-polish.md's project-planner triage block must not absorb the
    LATER senior-developer block's "Run full test suite" line -- the
    concrete case that makes whole-file scanning wrong for this corpus."""

    def test_p5_polish_projectplanner_block_has_no_run_test_suite_line(self):
        text = (COMMANDS_DIR / "p5-polish.md").read_text(encoding="utf-8")
        blocks = _agent_blockquote_blocks(text)
        planner_blocks = [b for agent, b in blocks if agent == "project-planner"]
        self.assertTrue(planner_blocks, "no project-planner block found in p5-polish.md")
        for b in planner_blocks:
            self.assertNotIn("Run full test suite", b)

    def test_p5_polish_seniordeveloper_block_carries_the_run_test_suite_line(self):
        text = (COMMANDS_DIR / "p5-polish.md").read_text(encoding="utf-8")
        blocks = _agent_blockquote_blocks(text)
        dev_blocks = [b for agent, b in blocks if agent == "senior-developer"]
        self.assertTrue(
            any("Run full test suite" in b for b in dev_blocks),
            "expected senior-developer's own block to carry the line -- "
            "attribution parser regressed",
        )


class MutationProofTest(unittest.TestCase):
    """Proves find_violations actually fires on the CCP-1182 defect shape,
    on a synthetic fixture -- the real corpus is fixed now, so it can no
    longer manufacture a RED case (G-107/G-109)."""

    def test_fires_on_a_synthetic_qa_tester_run_tests_command(self, tmp_path=None):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="ccpr-no-bash-runs-tests-") as tmp:
            d = Path(tmp)
            fixture = d / "p9-fake.md"
            fixture.write_text(
                "## Agent\n- **Type**: qa-tester\n\n"
                "## Prompt Template\n"
                "> **Goal**: Run integration tests for: [area]\n"
                "> Summary: X passed, Y failed\n",
                encoding="utf-8",
            )
            findings = find_violations(commands_dir=d)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0][0], "p9-fake.md")
            self.assertEqual(findings[0][1], "qa-tester")


if __name__ == "__main__":
    unittest.main()
