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

## Rule 5 and the trap in it

Rule 5 mirrors Rule 4 for a different capability: an agent whose BODY names
the `Bash` TOOL must carry `Bash` in `tools`. The naive way to build this --
grep the body for anything shell-command-shaped (a backtick-quoted `git`,
`grep`, `npm`, ...) -- was measured against the ALREADY-FIXED tree (finding
F9, 29.08.2026) and produces exactly the false positives Rule 4's own trap
predicts: `code-reviewer.md` denying it "cannot run `git diff`",
`project-guide.md` explaining "this is a Grep-tool call, not a `grep -c`
command", and `tech-writer.md`'s style guidance quoting `npm install` as an
example of a backticked code term. All three name a COMMAND, never the word
`Bash`, and two of the three are the exact sentences the F9 fix added to
DENY the capability. A command-shaped detector flags the cure as the
disease -- see BashToolDetectorBoundaryTest for these three as named
regression pins.

Rule 5 therefore keys on the literal word `Bash` (the tool name, not a
command) appearing in the BODY -- restricted the same way Rule 4 is
restricted, since `tools: ... Bash` is itself a mention of the word -- with
one guard: a mention immediately preceded by "no " ("you have no Bash
access", the correct way to document absence -- see `project-guide.md` and
`project-planner.md`) does not count as a claim of the capability. This is
a narrow, snapshot-style guard, not a general negation parser -- a
differently-phrased denial ("Bash is not available", "cannot use Bash") is
NOT covered and would need a matching guard added deliberately, the same
posture KNOWN_TOOLS takes for a new tool name (see "What Rule 3 is and is
not" above).

What this shape sees and what it does not: it sees an agent's body claiming
or instructing use of the Bash TOOL by name. It does NOT see an agent
telling itself to run a shell command without ever naming the tool --
`code-reviewer.md`'s original defect ("Use `git diff`, `git diff --cached`,
`git log --oneline -10`") named commands, never "Bash", and Rule 5 would
have missed it exactly as it was written before the F9 fix. That gap is
intentional and stays open; closing it needs a command-shaped detector,
which the false-positive measurement above rules out as a naive regex and
which this wave does not attempt.

## Rule 5, measured against today's tree

Rule 5 reports zero findings, and has done since `961165f` -- the commit that
introduced this module and corrected the agents in the same change.

The wave's starting assumption was that the rule would be clean from the
outset; it was not. Run against `961165f^` it flags FOUR agents whose body
affirmatively names the Bash tool while `tools:` lacks it: `konzeptor.md`
("**Bash**: As needed for file operations or research in the project
directory"), `system-architekt.md` (three mentions -- "using available tools
(Read, Grep, Glob, Bash)", "You have access to Read, Write, Edit, Bash,
Grep, and Glob tools", "**Bash**: Run commands to inspect infrastructure
configs..."), `tech-writer.md`'s OTHER Bash mention, distinct from the one
F9 already fixed ("Use the available tools (Read, Grep, Glob, Bash) to
thoroughly understand..."), and `security-master.md`.

F9 resolved all four in `961165f` (29.08.2026), by two different routes: the
first three had the incidental prose corrected, while `security-master.md`
GAINED the tool it names (PO decision -- dependency auditing is in its
brief). Only the prose route is visible as a body change, which is why an
earlier revision of this section counted three.

Until 30.08.2026 this section and AgentBashToolRequiredTest's own docstring
both reported the test as failing for those three reasons. That was never
true of any committed state -- the fix and the claim landed together, so the
register was stale from its first line. `test_live_status_claims.py` scans
prose for exactly this shape.
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


# Rule 5: a literal mention of the Bash TOOL in the body -- "Bash" as a
# capitalized whole word. Guarded against the one denial shape seen in the
# corpus ("you have no Bash access"); see the module docstring's "Rule 5
# and the trap in it" for what this guard does and does not cover.
BASH_TOOL_RE = re.compile(r"\bBash\b")
BASH_DENIAL_PREFIX = "no "


def body_names_bash_tool(body):
    """Rule 5's detector: True if `body` (already restricted to the
    post-frontmatter text) affirmatively names the Bash tool -- i.e. some
    occurrence of the word "Bash" is not immediately preceded by "no "
    (the corpus's one denial shape, "you have no Bash access"). See the
    module docstring's "Rule 5 and the trap in it" for the boundary this
    narrow guard draws."""
    for m in BASH_TOOL_RE.finditer(body):
        prefix = body[max(0, m.start() - len(BASH_DENIAL_PREFIX)):m.start()]
        if prefix.lower() == BASH_DENIAL_PREFIX:
            continue
        return True
    return False


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


class BashToolDetectorBoundaryTest(unittest.TestCase):
    """Unit-level RED proofs for body_names_bash_tool/BASH_TOOL_RE itself --
    mirrors InvocationDetectorBoundaryTest. Proves the detector fires on an
    affirmative mention, stays silent on the one denial shape seen in the
    corpus, and -- the reason a command-shaped detector was rejected, see
    the module docstring's "Rule 5 and the trap in it" -- stays silent on
    three real sentences that name a shell COMMAND but never the word
    "Bash". These three are regression pins: if they ever go red, Rule 5
    widened past naming the tool and started matching commands again."""

    def test_an_affirmative_bash_mention_is_detected(self):
        body = "**Bash**: Run `npm audit`, `pip audit` to check dependencies."
        self.assertTrue(body_names_bash_tool(body))

    def test_no_bash_access_denial_is_not_detected(self):
        body = "you have no Bash access, so you cannot run `workitems list` yourself."
        self.assertFalse(body_names_bash_tool(body))

    def test_code_reviewer_git_diff_denial_sentence_is_not_detected(self):
        # Regression pin -- code-reviewer.md's F9 fix wording: denies a
        # COMMAND ("git diff"), never names "Bash".
        body = "**You have no shell.** ... You cannot run `git diff`."
        self.assertFalse(body_names_bash_tool(body))

    def test_project_guide_grep_c_sentence_is_not_detected(self):
        # Regression pin -- project-guide.md's F9 fix wording: denies a
        # COMMAND ("grep -c"), never names "Bash".
        body = "You have no shell; this is a Grep-tool call, not a `grep -c` command."
        self.assertFalse(body_names_bash_tool(body))

    def test_tech_writer_npm_install_backtick_sentence_is_not_detected(self):
        # Regression pin -- tech-writer.md's style-guide example, quoting
        # `npm install` as a backticked code term; no relation to Bash.
        body = "- Code terms in backticks: `config.yaml`, `npm install`"
        self.assertFalse(body_names_bash_tool(body))


class BashToolMentionInBodyTest(unittest.TestCase):
    """Measured corpus (mirrors BodyInvocationDetectionTest): which agents'
    bodies affirmatively name the Bash tool today, regardless of whether
    they carry it in tools:. Restricted to the BODY -- if a mutation makes
    this scan the frontmatter too, `tools: ... Bash` is itself a mention of
    the word, and business-analyst/devops/ux-designer (Bash in tools:, no
    body mention) would spuriously join this set. If this count changes,
    Rule 5's "restrict to body" premise needs re-triage, not a widened
    acceptance.

    The set was seven when Rule 5 was first written and is four now. The
    same run that introduced the rule found three further agents claiming
    the tool in prose while `tools:` did not carry it -- `konzeptor`,
    `system-architekt`, and a second `tech-writer` mention beyond the one
    finding F9 named. Nobody had reported them; the external review found
    only `code-reviewer`, and the orchestrator's own first sweep missed
    them because it searched for backticked shell COMMANDS rather than for
    the tool's name. All three were incidental "you have these tools"
    sentences, not job requirements, so the prose was corrected to the
    truth rather than the capability granted. `security-master` went the
    other way -- its documented job is dependency auditing, so it gained
    `Bash` (PO decision, 29.08.2026). Each of the four that remain carries
    the tool it names."""

    def test_four_agent_bodies_name_the_bash_tool(self):
        mentioners = set()
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            if body_names_bash_tool(body):
                mentioners.add(field_value(fm, "name"))
        self.assertEqual(
            mentioners,
            {"debugger", "pentester", "security-master", "senior-developer"},
            "the set of agents whose body names the Bash tool diverged "
            "from the measured corpus; got: {}".format(sorted(mentioners)),
        )


class AgentBashToolRequiredTest(unittest.TestCase):
    """Rule 5, applied to the current tree: any agent whose body
    affirmatively names the Bash tool must carry `Bash` in its own tools:.
    Like Rule 4, it holds against the tree as shipped. Run against
    `961165f^` it flags four agents (konzeptor.md, system-architekt.md,
    tech-writer.md's second Bash mention, and security-master.md); all four
    were resolved in `961165f`, the commit that also introduced this module
    -- see the module docstring's "Rule 5, measured against today's tree"."""

    def test_every_body_bash_mention_is_covered_by_tools(self):
        violations = []
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            if body_names_bash_tool(body) and "Bash" not in parse_tools(fm):
                violations.append(path.name)
        self.assertFalse(
            violations,
            "agent(s) whose body names the Bash tool without carrying it "
            "in tools: -- see the module docstring's \"Rule 5, measured "
            "against today's tree\" for what each one says and why it is "
            "out of this wave's write boundary:\n" + "\n".join(sorted(violations)),
        )


class SyntheticBashViolationTest(unittest.TestCase):
    """In-memory RED proofs for the end-to-end Rule 5 check (detector +
    tools: cross-check together) -- mirrors RequiredFieldsTest's synthetic
    pattern (G-107/G-143: no real agents/*.md file may be mutated for
    this). The real corpus already has non-synthetic violations (see
    AgentBashToolRequiredTest), but a violation found by accident does not
    prove the check discriminates -- these two are the deliberate positive
    and negative it is measured against."""

    def test_a_synthetic_agent_naming_bash_without_the_tool_is_a_violation(self):
        fm = "name: fake-agent\ndescription: x\ntools: Read, Grep\nmodel: sonnet"
        body = "**Bash**: Run `npm audit` to check dependencies."
        is_violation = body_names_bash_tool(body) and "Bash" not in parse_tools(fm)
        self.assertTrue(is_violation)

    def test_a_synthetic_agent_naming_bash_and_carrying_it_is_not_a_violation(self):
        fm = "name: fake-agent\ndescription: x\ntools: Read, Grep, Bash\nmodel: sonnet"
        body = "**Bash**: Run `npm audit` to check dependencies."
        is_violation = body_names_bash_tool(body) and "Bash" not in parse_tools(fm)
        self.assertFalse(is_violation)



if __name__ == "__main__":
    unittest.main()
