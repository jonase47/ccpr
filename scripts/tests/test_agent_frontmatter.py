"""test_agent_frontmatter.py -- WI-0128 wave 2b: a frontmatter validator for
agents/*.md (finding #4, the cheap half).

## Why this exists

A shipped defect (found 27.08.2026): `agents/senior-developer.md`'s body
declared invoking `code-reviewer` MANDATORY (":64" in the shipped file) while
its own `tools:` line did not carry `Agent` -- the agent could not do what
its own body required of it. The contradiction sat inside ONE file; finding
it needs no tree comparison, only someone who reads frontmatter and body
together. It was first filed as "shipped tree vs. installed tree" because
the local `~/.claude/` copy happened to already have the fix and hid the
symptom -- see fix commit 7af990d's message. That tree comparison is real
but is a separate, more expensive item; this wave is the half that proves
itself from the repo alone. There was, until this module, no test anywhere
that reads agent frontmatter at all.

## The measured corpus (WI-0128 wave 2b briefing -- not re-derived here)

15 files, all with exactly the same four frontmatter fields: `name`,
`description`, `tools`, `model`. Tool names seen across all 15:
Read/Grep/Glob (15 each), Edit (14), Write (13), Bash (6), WebFetch (1),
NotebookEdit (1), Agent (1, senior-developer only).

## Rule 4 and the trap in it

Rule 4 is the one that would have caught the shipped defect: an agent whose
BODY requires invoking another agent must carry `Agent` in `tools`. The
naive way to build this -- grep the whole file for another agent's name --
returns 9 false positives, because `description:` says WHEN a human/
orchestrator should launch THIS agent ("Use the Task tool to launch the
senior-developer agent"), which is a description of somebody ELSE's
action, never a declaration that this agent invokes another. Restricted to
the BODY (everything after the second `---`) and to an explicit invocation
verb next to a backtick-quoted, known agent name, exactly one match
remains: `senior-developer` invoking `code-reviewer` (its "**Invoke
`code-reviewer` agent** -- MANDATORY..." line). See
BodyInvocationDetectionTest for the count assertion this docstring claims.

## Both directions, from real history

The discriminating fixture is commit 7af990d ("fix(agents): senior-developer
could not run the review its own body calls mandatory"). Its PARENT,
7af990d^, has the pre-fix `tools:` line (`Bash, Glob, Grep, Read, Write,
Edit` -- no `Agent`) with the IDENTICAL body, including the same "Invoke
`code-reviewer` agent -- MANDATORY" line. Rule 4 must fire against that
pre-state and name `senior-developer`, and stay silent against every file
in the tree today. Both directions are pulled as text copies via `git show`
(not `git checkout`, which would touch the working tree) in
Rule4HistoricalRedProofTest.

## What Rule 3 (known tools) is and is not

There is no source of truth in this repo for the set of valid Claude Code
tool names -- that set is owned by Claude Code, not by this project.
KNOWN_TOOLS is therefore a SNAPSHOT, and is documented as one: a new,
legitimate tool appearing in some agent's `tools:` line will fail
KnownToolsTest by design. That failure is the intended signal for a human
to look at the new name and decide whether it is a typo (this project has
already shipped the `Task` vs. `Agent` confusion once) or a genuine
addition that belongs in this snapshot.
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "agents"

# Rule 1: pinned file count. Without this pin, the sweep below silently
# shrinks to whatever is left if a file disappears -- "all N files have
# required fields" over an N that quietly became N-1 proves nothing about
# the missing file.
EXPECTED_AGENT_COUNT = 15

REQUIRED_FIELDS = ("name", "description", "tools", "model")

# Rule 3: snapshot of tool names seen in agents/*.md as of WI-0128 wave 2b
# (28.08.2026). See the module docstring's "What Rule 3 is and is not".
KNOWN_TOOLS = frozenset({
    "Read", "Grep", "Glob", "Edit", "Write", "Bash",
    "WebFetch", "NotebookEdit", "Agent",
})

# Rule 4: an invocation directive in the BODY -- "Invoke `<name>` agent",
# case-sensitive on the verb capital because that is how the one real
# instance ("**Invoke `code-reviewer` agent**") and its historical
# pre-fix twin are both written; a bare-lowercase "invoke" elsewhere in
# prose (not a directive) is not meant to match. `[^\n`]{0,40}` bounds the
# gap between the verb and the backtick so the regex cannot reach across a
# paragraph to an unrelated agent name.
INVOCATION_RE = re.compile(
    r"\bInvoke\b[^\n`]{0,40}`([a-z][a-z-]*)`\s+agent\b"
)

PRE_FIX_COMMIT = "7af990d"
PRE_FIX_AGENT_PATH = "agents/senior-developer.md"


def _iter_agent_files():
    return sorted(AGENTS_DIR.glob("*.md"))


def split_frontmatter(text):
    """Splits `text` into (frontmatter, body) at the first two `---` lines.
    Raises ValueError if the block never closes -- a malformed file should
    fail loudly here, not be silently treated as "no frontmatter"."""
    lines = text.splitlines()
    dash_idx = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if len(dash_idx) < 2:
        raise ValueError("no closed '---' frontmatter block")
    frontmatter = "\n".join(lines[dash_idx[0] + 1:dash_idx[1]])
    body = "\n".join(lines[dash_idx[1] + 1:])
    return frontmatter, body


def field_value(frontmatter, key):
    """Returns the raw value after `key:` on its own line, or None."""
    m = re.search(r"(?m)^" + re.escape(key) + r":[ \t]*(.*?)[ \t]*$", frontmatter)
    return m.group(1) if m else None


def parse_tools(frontmatter):
    raw = field_value(frontmatter, "tools")
    if raw is None:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def all_agent_names():
    """The set of every `name:` value declared across agents/*.md."""
    names = set()
    for path in _iter_agent_files():
        fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        name = field_value(fm, "name")
        if name:
            names.add(name)
    return names


def invoked_agents_in_body(body, self_name, known_names):
    """Rule 4's detector: the set of OTHER known agent names that `body`
    (already restricted to the post-frontmatter text) explicitly directs
    invoking, per INVOCATION_RE. Excludes `self_name` -- a body naming
    itself is not a cross-agent dependency."""
    found = set()
    for m in INVOCATION_RE.finditer(body):
        candidate = m.group(1)
        if candidate in known_names and candidate != self_name:
            found.add(candidate)
    return found


def read_git_show(ref_and_path):
    """Reads a file's content at a historical ref via `git show <ref:path>`
    -- a text copy pulled from history, never a checkout that would touch
    the working tree."""
    result = subprocess.run(
        ["git", "show", ref_and_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


class AgentCountTest(unittest.TestCase):
    """Rule 1 (count pin): agents/*.md must be exactly EXPECTED_AGENT_COUNT
    files. See the module-level comment on why an unpinned count is unsafe."""

    def test_agent_file_count_is_pinned(self):
        files = _iter_agent_files()
        self.assertEqual(
            len(files), EXPECTED_AGENT_COUNT,
            "agents/*.md file count drifted from the pinned {} -- update "
            "EXPECTED_AGENT_COUNT deliberately if a file was added or "
            "removed on purpose:\n{}".format(
                EXPECTED_AGENT_COUNT, [str(p) for p in files],
            ),
        )


class RequiredFieldsTest(unittest.TestCase):
    """Rule 1 (required fields): every agent file carries all four of
    REQUIRED_FIELDS in its frontmatter."""

    def test_every_agent_has_all_required_fields(self):
        violations = []
        for path in _iter_agent_files():
            fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
            missing = [f for f in REQUIRED_FIELDS if field_value(fm, f) is None]
            if missing:
                violations.append("{}: missing {}".format(path.name, missing))
        self.assertFalse(
            violations,
            "agent file(s) missing required frontmatter field(s):\n"
            + "\n".join(violations),
        )

    def test_a_frontmatter_block_missing_a_field_is_detected(self):
        # In-memory RED proof (G-107/G-143: a check is only accepted once
        # seen red; no real agents/*.md file may be mutated for this). The
        # real corpus agrees on all four fields today, so this cannot be
        # demonstrated against it -- a synthetic block missing `model:` is
        # the mutation.
        synthetic_fm = "name: fake-agent\ndescription: x\ntools: Read"
        missing = [f for f in REQUIRED_FIELDS if field_value(synthetic_fm, f) is None]
        self.assertEqual(missing, ["model"])


class NameMatchesFilenameTest(unittest.TestCase):
    """Rule 2: `name:` must equal the filename without `.md`. An agent whose
    declared name does not match its file is addressed under a name it
    cannot be found under."""

    def test_every_agent_name_matches_its_filename(self):
        violations = []
        for path in _iter_agent_files():
            fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
            name = field_value(fm, "name")
            expected = path.stem
            if name != expected:
                violations.append(
                    "{}: name: {!r} != filename stem {!r}".format(
                        path.name, name, expected,
                    )
                )
        self.assertFalse(
            violations,
            "agent file(s) whose name: does not match their filename:\n"
            + "\n".join(violations),
        )

    def test_a_name_filename_mismatch_is_detected(self):
        # In-memory RED proof -- see RequiredFieldsTest's for the rationale.
        synthetic_fm = "name: wrong-name\ndescription: x\ntools: Read\nmodel: sonnet"
        name = field_value(synthetic_fm, "name")
        expected = "senior-developer"  # pretend filename stem
        self.assertNotEqual(name, expected)


class KnownToolsTest(unittest.TestCase):
    """Rule 3: every tool name in `tools:` must be in the KNOWN_TOOLS
    snapshot. See the module docstring on why this is a snapshot, not a
    source of truth, and why failing on a new legitimate tool is by design."""

    def test_every_tool_name_is_in_the_known_snapshot(self):
        violations = []
        for path in _iter_agent_files():
            fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
            for tool in parse_tools(fm):
                if tool not in KNOWN_TOOLS:
                    violations.append("{}: unknown tool {!r}".format(path.name, tool))
        self.assertFalse(
            violations,
            "agent file(s) with a tool name outside the KNOWN_TOOLS "
            "snapshot -- confirm it is a real Claude Code tool (not a "
            "Task/Agent-style typo) and add it to KNOWN_TOOLS deliberately:\n"
            + "\n".join(violations),
        )

    def test_an_unknown_tool_name_is_detected(self):
        # In-memory RED proof -- see RequiredFieldsTest's for the rationale.
        # `Task` is not a coincidental choice: it is the exact confusion
        # this project has already shipped once (Task vs. Agent).
        synthetic_fm = "name: fake-agent\ndescription: x\ntools: Read, Task\nmodel: sonnet"
        tools = parse_tools(synthetic_fm)
        unknown = [t for t in tools if t not in KNOWN_TOOLS]
        self.assertEqual(unknown, ["Task"])


class BodyInvocationDetectionTest(unittest.TestCase):
    """Confirms the restriction the module docstring claims: scanning the
    BODY only (not description:) for an invocation directive finds exactly
    one agent today -- senior-developer. If this ever reports more or
    fewer than one, Rule 4's regex or its "restrict to body" premise needs
    re-triage, not a widened acceptance."""

    def test_exactly_one_agent_body_directs_invoking_another(self):
        known_names = all_agent_names()
        invokers = {}
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            self_name = field_value(fm, "name")
            invoked = invoked_agents_in_body(body, self_name, known_names)
            if invoked:
                invokers[self_name] = invoked
        self.assertEqual(
            invokers, {"senior-developer": {"code-reviewer"}},
            "body-invocation detection diverged from the measured corpus "
            "(exactly senior-developer -> code-reviewer expected); got: {}"
            .format(invokers),
        )


class AgentToolRequiredForInvocationTest(unittest.TestCase):
    """Rule 4, applied to the current tree: any agent whose body directs
    invoking another agent must carry `Agent` in its own `tools:` line.
    Today's tree is clean (senior-developer carries it) -- if this test
    goes red, the briefing's instruction applies: suspect the test before
    suspecting agents/*.md (which this wave must not modify)."""

    def test_every_body_invoker_carries_the_agent_tool(self):
        known_names = all_agent_names()
        violations = []
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            self_name = field_value(fm, "name")
            invoked = invoked_agents_in_body(body, self_name, known_names)
            if invoked and "Agent" not in parse_tools(fm):
                violations.append(
                    "{}: body directs invoking {} but tools: lacks 'Agent'"
                    .format(path.name, sorted(invoked))
                )
        self.assertFalse(
            violations,
            "agent(s) whose body requires invoking another agent without "
            "the Agent tool:\n" + "\n".join(violations),
        )


class InvocationDetectorBoundaryTest(unittest.TestCase):
    """Unit-level RED proofs for invoked_agents_in_body/INVOCATION_RE itself
    -- the historical fixture in Rule4HistoricalRedProofTest proves the
    end-to-end rule on a real file, this proves the detector does not
    over-match the cases the module docstring says it must not (lowercase
    "invoke" in prose, an unknown/self name, a name too far from the verb)."""

    def setUp(self):
        self.known_names = {"code-reviewer", "senior-developer", "debugger"}

    def test_lowercase_invoke_in_prose_does_not_match(self):
        body = "You may invoke `code-reviewer` agent informally if useful."
        self.assertEqual(
            invoked_agents_in_body(body, "senior-developer", self.known_names),
            set(),
        )

    def test_an_unknown_agent_name_is_not_reported(self):
        body = "**Invoke `nonexistent-agent` agent** -- MANDATORY."
        self.assertEqual(
            invoked_agents_in_body(body, "senior-developer", self.known_names),
            set(),
        )

    def test_self_invocation_is_excluded(self):
        body = "**Invoke `senior-developer` agent** -- MANDATORY."
        self.assertEqual(
            invoked_agents_in_body(body, "senior-developer", self.known_names),
            set(),
        )

    def test_a_name_far_from_the_verb_does_not_match(self):
        filler = "x" * 60
        body = "Invoke {} `code-reviewer` agent".format(filler)
        self.assertEqual(
            invoked_agents_in_body(body, "senior-developer", self.known_names),
            set(),
        )

    def test_the_real_shape_matches(self):
        body = "2. **Invoke `code-reviewer` agent** -- MANDATORY after every implementation."
        self.assertEqual(
            invoked_agents_in_body(body, "senior-developer", self.known_names),
            {"code-reviewer"},
        )


class Rule4HistoricalRedProofTest(unittest.TestCase):
    """Both directions, pulled as text copies from real history (WI-0128
    wave 2b briefing) -- without both, Rule 4 is not shown to discriminate
    anything. 7af990d^ (parent of the fix commit) carries the identical
    body -- same "Invoke `code-reviewer` agent" line -- with the pre-fix
    `tools:` line missing `Agent`. 7af990d is the fix itself."""

    @classmethod
    def setUpClass(cls):
        cls.known_names = all_agent_names()
        cls.pre_fix_text = read_git_show(
            "{}^:{}".format(PRE_FIX_COMMIT, PRE_FIX_AGENT_PATH)
        )
        cls.post_fix_text = read_git_show(
            "{}:{}".format(PRE_FIX_COMMIT, PRE_FIX_AGENT_PATH)
        )

    def test_pre_fix_body_is_identical_to_post_fix_body(self):
        # Sanity check pinning the fixture's own claim: the two commits
        # differ ONLY in tools:, not in the invocation-directive line the
        # rule keys on. If this drifts, the "both directions" proof below
        # is comparing apples to oranges, not testing Rule 4.
        _, pre_body = split_frontmatter(self.pre_fix_text)
        _, post_body = split_frontmatter(self.post_fix_text)
        self.assertEqual(pre_body, post_body)

    def test_rule4_fires_against_the_pre_fix_tools_line(self):
        fm, body = split_frontmatter(self.pre_fix_text)
        self_name = field_value(fm, "name")
        invoked = invoked_agents_in_body(body, self_name, self.known_names)
        self.assertEqual(invoked, {"code-reviewer"})
        self.assertNotIn(
            "Agent", parse_tools(fm),
            "fixture assumption broken: pre-fix tools: line already had "
            "Agent -- this is no longer a red fixture",
        )
        # This is the actual Rule 4 verdict: invoked-but-missing-the-tool.
        self.assertTrue(
            invoked and "Agent" not in parse_tools(fm),
            "Rule 4 failed to flag the known-bad pre-fix state",
        )

    def test_rule4_is_silent_against_the_post_fix_tools_line(self):
        fm, body = split_frontmatter(self.post_fix_text)
        self_name = field_value(fm, "name")
        invoked = invoked_agents_in_body(body, self_name, self.known_names)
        self.assertEqual(invoked, {"code-reviewer"})
        self.assertIn("Agent", parse_tools(fm))
        # Rule 4's verdict here must be "compliant": invoked AND has the tool.
        self.assertTrue(
            not invoked or "Agent" in parse_tools(fm),
            "Rule 4 false-positived against the already-fixed post-fix state",
        )


if __name__ == "__main__":
    unittest.main()
