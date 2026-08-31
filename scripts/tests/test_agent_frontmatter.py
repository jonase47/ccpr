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
NotebookEdit (1), Agent (1, senior-developer only). `Bash` is 7 as of
29.08.2026 -- `security-master` gained it under finding F9; the 6 above is
part of the quoted briefing snapshot and is left as such.

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

## Rule 6 and the trap in it

Rule 6 covers a third kind of contradiction, and the one this project's own
maintenance produced: an agent told to write into a store whose format
contract its definition never states. Two silos sit behind the same word
"memory" and do NOT share a frontmatter contract --
`~/.claude/memory/{agent}/` (global Tier-2: `scope: tier-2-global` +
`agent:`) and `docs/memory/{agent}/` (project Tier-2: `name`,
`description`, `type`, `last_updated` per `templates/MEMORY_SCHEMA.md`).

The trap is that the obvious rule -- "an agent with memory write access must
state the frontmatter contract" -- is satisfied by all fifteen files and
would have caught nothing. Every one of them states a contract: the GLOBAL
silo's, in the same sentence that grants that silo ("Frontmatter requires
`scope: tier-2-global` + `agent: <name>`", `code-reviewer.md:195` and its
fourteen siblings). What none of them states is the contract of the silo they
are told to write into. The rule therefore has to be evaluated PER SILO; a
rule asking "is a contract stated?" answers yes for a file that states the
wrong one. ProjectSiloContractDetectorBoundaryTest holds that discrimination
as a unit case, and ProjectMemoryContractHistoricalRedProofTest as the same
discrimination against real pre-rollout text.

A second trap sits in the trigger's width. ALL FIFTEEN bodies mention a
project-silo path, but four mention it only to READ it ("Check whether
`docs/memory/{agent}/instincts.md` exists ... Also load ...", the
`## Instincts` section shared by business-analyst, devops, ux-designer and
wingman). A path-only trigger paired with the write marker read body-wide
flags fourteen of the fifteen -- every agent except `wingman`, whose body
never names `Write` or `Edit` at all. The marker alone does not
discriminate; the scope has to.

A proximity window does not supply that scope, and the measurement is worth
writing down precisely, because an earlier revision of this docstring stated
it wrongly. Around those four read-only mentions a +/-200-character window
does reach back into the preceding `## Project Memory (Tier 1)` paragraph and
its "write it as `docs/memory/{type}_{slug}.md` ... and update the project
index" sentence. With a write-VERB marker (`write`, `update`) that window
matches in all four files, so a verb-based proximity trigger false-positives
on all four. With the capitalized tool-name marker this module actually uses,
the same window matches in NONE of them -- the neighbouring sentence names no
tool. So the window is not what keeps those four out, and claiming it is
would be the right verdict for the wrong reason. The section boundary is what
keeps them out, and it holds for either marker.
ProximityWindowIsNotAScopeTest pins both halves against the real files.

The trigger is therefore SECTION-scoped -- a `## `-level section naming both
the agent's own project silo and a write tool.

## What Rule 6 sees and what it does not

It reads the agent DEFINITION, not the run. An agent can carry the contract
in its body and still write a file that breaks it, which is exactly how the
finding arrived: a `code-reviewer` run produced
`docs/memory/code-reviewer/bsd-gnu-portability-wi0130.md` with no frontmatter
block at all, and `memory-lint` went from exit 1 to exit 2 -- inside
`docs/memory/`, which is gitignored, so CI reports could-not-run there and
never sees it. Rule 6 cannot prevent that. What it removes is the excuse: an
agent told to write into that silo is not told what the silo requires.
Enforcing the runtime shape is a different mechanism (a hook, or a lint gate
over `docs/memory/**`) and is not attempted here.

Three further boundaries, each with a named instance:

- The trigger reads the BODY only, as Rules 4 and 5 do. `code-reviewer.md`'s
  frontmatter carries a `#` comment naming both the write permission and the
  path ("Edit + Write are permitted ONLY for agent memory files
  (docs/memory/code-reviewer/*, ...)"), which a whole-file scan would count
  as a directive.
- The obligation is LINE-scoped: the word "frontmatter" and a project-schema
  token (`MEMORY_SCHEMA` or `last_updated`) must share one line.
  `project-guide.md:116` names `last_updated` in a staleness hint
  ("last_updated > 90 days"), dozens of lines from that file's own
  frontmatter mentions; a body-wide co-occurrence test reads that as a
  contract declaration. Up to `PRE_CONTRACT_COMMIT` it was the only
  `last_updated` that had ever appeared under `agents/`, and `MEMORY_SCHEMA`
  had never appeared there at all. Both statements are about that tree, not
  this one: the 30.08.2026 rollout put `MEMORY_SCHEMA` and a second
  `last_updated` into all fifteen bodies.
- `Write`/`Edit` as the write marker is a capability-claim detector, the same
  posture Rule 5 takes toward the word `Bash`. It matches the words, so
  `project-guide.md`'s "## Write Permissions (explicit)" heading matches too
  -- correctly, since that section does grant the write. A section merely
  using the word next to a read-only path mention would be a false positive;
  the four read-only agents are the regression pins showing that shape is
  absent from this corpus.

## Rule 6, measured against the tree

Eleven of the fifteen bodies direct a write into their own project silo: the
ten with a `## Persistent Agent Memory (Tier 2)` section, plus
`project-guide`, which grants it under `## Write Permissions (explicit)` and
`## Memory & Handover`. Four do not -- business-analyst, devops, ux-designer,
wingman -- and they drop out on the DIRECTIVE, not on `tools:`: three of the
four carry `Write` and `Edit` and are excluded anyway. Only wingman also
lacks the tools, so a tools-based filter would look equivalent on it alone
and diverge on the other three; ProjectSiloWriteDirectiveDetectionTest pins
both halves.

At `PRE_CONTRACT_COMMIT` all fifteen state the global silo's contract and
none states the project silo's -- `MEMORY_SCHEMA` appears nowhere under
`agents/` in this repository's history up to that commit, and `last_updated`
appears once, in `project-guide.md`'s staleness hint. The sentence naming
`templates/MEMORY_SCHEMA.md` was added to all fifteen bodies on 30.08.2026
(PO decision), which is why the rule is a clean-tree assertion here rather
than the debt pin an earlier revision of this docstring described. The
pre-state is kept as the red half of
ProjectMemoryContractHistoricalRedProofTest.

## Rule 7 is a trigger, not a rule

The brief that ordered Rule 7 asked for a second rule: an agent directing a
Tier-1 project-memory write (`docs/memory/{type}_{slug}.md`) must state the
same contract. Measuring it turned it into a second TRIGGER on Rule 6's
obligation instead, for one reason: `templates/MEMORY_SCHEMA.md` specifies
the SAME required fields for Tier 1 and for a Tier-2 persona silo. A separate
Rule 7 would have called the identical obligation function over an
overlapping set -- two registers of one fact, and the register that is not
looked at is the one that goes stale.

Both triggers are load-bearing, which is the other half of the measurement
and the part the brief did not predict. The Tier-1 directive is near-identical
boilerplate, but not universal: `project-guide` carries none (its
`## Write Permissions` section lists "memory files of other agents" among the
things it does not write), while three of the four read-only agents --
business-analyst, devops, ux-designer -- carry only that one. The fourth,
`wingman`, carries NEITHER after the Rule 8 fix below removed its write
directive; it is the one agent this rule obliges to nothing.

Neither trigger set contains the other, so the union is what the rule needs
and a single trigger of either kind would leave real agents unchecked.
Tier1WriteDirectiveDetectionTest holds all three measurements -- including
`wingman` as the sole uncovered agent -- and the failure message of
AgentProjectMemoryContractTest names which trigger fired.

## Rule 8, and the third contradiction shape

Rules 4, 5 and 8 are one family: the body claims or is handed a capability
its own `tools:` line does not provide. Rule 4 is about `Agent`, Rule 5 about
`Bash`, Rule 8 about `Write`/`Edit`. Rule 8 adds no trigger of its own -- it
reuses Rules 6/7's -- because what differs is the OBLIGATION (a tool rather
than a documented contract). That is the distinction that makes Rule 8 a rule
and Rule 7 not one.

Its instance: `wingman.md` at `PRE_CONTRACT_COMMIT` carried the Tier-1
directive "write it as `docs/memory/{type}_{slug}.md` ... and update the
project index" with `tools: Read, Grep, Glob`. Resolved by prose, not by a
grant -- `wingman` is a read-only consolidator by design, so granting `Write`
would have moved the role boundary rather than repaired the sentence.
Rule8HistoricalRedProofTest asserts the `tools:` line is IDENTICAL before and
after, so a later "fix" by grant cannot pass as the same repair.

Rewording that paragraph forced the Tier-1 trigger to grow the denial guard
Rule 5 already had: the honest wording is "you have no write tools", and a
trigger keyed on the path plus the word "write" cannot tell that from the
instruction it replaces. The guard skips a write verb immediately preceded by
"no ", and Tier1WriteDetectorBoundaryTest pins both halves -- the denial is
not a directive, and a line that merely contains "no " elsewhere still is.

## Rule 5, widened to ignore case (31.08.2026)

`agents/qa-tester.md` carried "Use bash to run existing tests and analyze
their output" -- lowercase, in a `## Practical Execution` list whose other
bullets all name tools it does have, with `tools: Glob, Grep, Read, Write,
Edit`. The case-sensitive pattern could not see it.

The prediction before measuring was that opening the case would bring back
the F9 false positives that shaped Rule 5's narrow form. It did not: over the
corpus the widened and narrow patterns disagree on exactly one file, the true
positive above, and the three F9 regression pins name a COMMAND (`git diff`,
`grep -c`, `npm install`) and no form of the word "bash" at all. What the
opening does cost is a shape that has not appeared yet: a body writing `bash
script.sh` as a command invocation now counts as naming the tool, which is
defensible but is a different claim from naming it. Rule5CaseWideningRedProofTest
keeps the two patterns compared against each other so that shape shows up as
a disagreement rather than as a silent widening.

`qa-tester` was resolved by prose, the F9 majority route: running a suite is
not in its brief (the project's own guidance is to interpret
`scripts/run-tests.sh` output rather than execute), and the bullet was an
incidental "you have these tools" line, not a job requirement. The one F9
grant, `security-master`, went the other way because dependency auditing IS
its documented job.
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
BASH_TOOL_RE = re.compile(r"\bBash\b", re.IGNORECASE)
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

    def test_qa_testers_no_shell_sentence_is_not_detected(self):
        # Regression pin -- qa-tester.md's 31.08.2026 fix wording. Like the
        # three above it denies an ACTION and names no tool, so the widening
        # to re.IGNORECASE must not make it a claim.
        body = ("- You have no shell: you cannot run tests yourself. Analyze "
                "test output the orchestrator hands you (e.g. "
                "`scripts/run-tests.sh` results) instead of executing a suite")
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


# ---------------------------------------------------------------------------
# Rule 6: the project-scope memory silo's frontmatter contract
# ---------------------------------------------------------------------------

# The agent's own project silo, as the bodies spell it.
PROJECT_SILO_PATH_TMPL = "docs/memory/{}/"

# `## ` headings only -- a `### ` subsection must stay inside its parent, so
# that a shape-A agent's `### Instincts` block is part of the same section as
# the `## Persistent Agent Memory (Tier 2)` write directive above it.
SECTION_RE = re.compile(r"(?m)^## (?!#)")
FENCE_RE = re.compile(r"^\s*```")

# A write marker: the TOOL names, capitalized -- the same posture Rule 5
# takes toward the word `Bash`. See the module docstring for what this
# matches beside a tool invocation.
#
# Known blind spot: a write grant phrased purely as lowercase prose ("save
# your notes into `docs/memory/{agent}/`") names no tool and would drop out
# of RULE6_TRIGGERING_AGENTS. A SHRINKING triggering set fails
# ProjectSiloWriteDirectiveDetectionTest just as a growing one does, so the
# drop is loud -- but the failure says "the set changed", not "a write
# directive stopped being seen", and the re-triage has to make that
# distinction by hand.
WRITE_TOOL_RE = re.compile(r"\b(?:Write|Edit)\b")

# NOT the marker Rule 6 uses -- the verb-based alternative, kept because
# ProximityWindowIsNotAScopeTest measures the two against each other. See
# the module docstring's second trap.
WRITE_VERB_RE = re.compile(r"\b(?:write|writing|update|record|save)\b", re.I)

# "Frontmatter" or "frontmatter"; matched as a substring on purpose so no
# case list has to be maintained.
FRONTMATTER_WORD_RE = re.compile(r"rontmatter")

# The project silo's contract lives in `templates/MEMORY_SCHEMA.md`; a body
# may point at the file or name its required fields. `last_updated` is the
# discriminating field name -- `name`/`description`/`type` are far too common
# as ordinary words to key on.
PROJECT_SCHEMA_TOKEN_RE = re.compile(r"MEMORY_SCHEMA|last_updated")

# The global silo's contract, for the per-silo comparison Rule 6 rests on.
GLOBAL_SILO_CONTRACT_TOKEN = "scope: tier-2-global"

# Rule 6, measured 30.08.2026: the agent bodies that direct a write into
# their OWN project silo. Ten carry a `## Persistent Agent Memory (Tier 2)`
# section; project-guide grants the same thing under `## Write Permissions
# (explicit)` and `## Memory & Handover`.
RULE6_TRIGGERING_AGENTS = frozenset({
    "code-reviewer", "debugger", "konzeptor", "pentester", "project-guide",
    "project-planner", "qa-tester", "security-master", "senior-developer",
    "system-architekt", "tech-writer",
})

# The historical red fixture: the last commit before the contract sentence
# was added to agents/*.md. Every agent file at this ref states the GLOBAL
# silo's frontmatter contract and none states the project one -- the exact
# structural shape the rule has to catch. Pulled as text via `git show`, the
# same way Rule 4 pulls 7af990d^ (see Rule4HistoricalRedProofTest).
PRE_CONTRACT_COMMIT = "17bc391"

# Two fixtures, one per trigger, so neither trigger's half of the rule rests
# on the other's: `code-reviewer` fires both triggers, `business-analyst`
# only Tier-1 (its own-silo mention is read-only). `wingman` was the original
# Tier-1-only fixture and is no longer usable as one -- Rule 8's fix removed
# its write directive on 31.08.2026, so it now differs from its pre-state by
# more than the inserted sentence.
PRE_CONTRACT_FIXTURES = ("code-reviewer", "business-analyst")

# The sentence added to all fifteen bodies (30.08.2026). Two variants, which
# differ only in the antecedent: the eleven that get it in their own-silo
# paragraph say "Files in it", the four whose obligation comes from the
# Tier-1 directive say "Those files" -- "it" there would point at the project
# index rather than at the memory files.
CONTRACT_SENTENCE_OWN_SILO = (
    " Files in it carry frontmatter per `templates/MEMORY_SCHEMA.md`: "
    "`name`, `description`, `type` and `last_updated` are required."
)
CONTRACT_SENTENCE_TIER1 = (
    " Those files carry frontmatter per `templates/MEMORY_SCHEMA.md`: "
    "`name`, `description`, `type` and `last_updated` are required."
)


def mask_fenced_code_blocks(text):
    """Blanks every line of a ``` fenced block (the fence lines included)
    while preserving the line count and each line's length, so offsets stay
    comparable to the unmasked text. A `## ` heading inside a fenced example
    -- `project-guide.md`'s HANDOVER sample section -- is a sample, not a
    section of the agent definition, and must not split the body."""
    out = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(" " * len(line))
            continue
        out.append(" " * len(line) if in_fence else line)
    return "\n".join(out)


def body_sections(body):
    """Splits `body` into `## `-level sections, fenced code masked first.
    Text before the first `## ` is returned as its own leading section."""
    masked = mask_fenced_code_blocks(body)
    starts = [m.start() for m in SECTION_RE.finditer(masked)]
    if not starts:
        return [masked]
    sections = []
    if starts[0] > 0:
        sections.append(masked[:starts[0]])
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(masked)
        sections.append(masked[start:end])
    return sections


def directs_project_silo_write(body, self_name):
    """Rule 6's trigger: True if some `## `-level section of `body` (already
    restricted to the post-frontmatter text) names the agent's own project
    silo AND names a write tool. Section-scoped, because a proximity window
    reaches into the neighbouring Tier-1 paragraph's write sentence -- see
    the module docstring's "Rule 6 and the trap in it"."""
    own_silo = PROJECT_SILO_PATH_TMPL.format(self_name)
    for section in body_sections(body):
        if own_silo in section and WRITE_TOOL_RE.search(section):
            return True
    return False


def declares_project_memory_contract(body):
    """Rule 6's obligation: True if some single LINE of `body` names
    frontmatter together with a token of the project schema. Line-scoped
    because `project-guide.md:116` names `last_updated` in a staleness hint,
    dozens of lines from its own frontmatter mentions."""
    # Deliberately NOT section-scoped, unlike the trigger: this is safe only
    # while the Tier-1 (`docs/memory/{type}_{slug}.md`) and Tier-2
    # (`docs/memory/{agent}/{topic}.md`) required-field sets stay identical,
    # as `templates/MEMORY_SCHEMA.md` currently specifies them. If they ever
    # diverge, a sentence stating the Tier-1 contract would satisfy this for
    # an agent that never documented its own silo, and this function needs
    # the same section scoping the trigger has.
    for line in mask_fenced_code_blocks(body).splitlines():
        if FRONTMATTER_WORD_RE.search(line) and PROJECT_SCHEMA_TOKEN_RE.search(line):
            return True
    return False


def declares_global_silo_contract(body):
    """The same shape for the OTHER silo -- not a rule of its own, but the
    control Rule 6 is measured against: the corpus states this contract
    while leaving the project one unstated."""
    for line in mask_fenced_code_blocks(body).splitlines():
        if FRONTMATTER_WORD_RE.search(line) and GLOBAL_SILO_CONTRACT_TOKEN in line:
            return True
    return False


def _agent_body(name):
    """Reads one agent file's body by agent name -- a read, never a write."""
    text = (AGENTS_DIR / (name + ".md")).read_text(encoding="utf-8")
    return split_frontmatter(text)[1]


class ProjectSiloWriteDirectiveDetectionTest(unittest.TestCase):
    """Rule 6's trigger, measured against the corpus -- mirrors
    BodyInvocationDetectionTest and BashToolMentionInBodyTest. If this set
    changes, the section-scoping premise needs re-triage, not a widened
    acceptance."""

    def test_the_triggering_set_matches_the_measured_corpus(self):
        triggering = set()
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            name = field_value(fm, "name")
            if directs_project_silo_write(body, name):
                triggering.add(name)
        self.assertEqual(
            triggering, set(RULE6_TRIGGERING_AGENTS),
            "the set of agents directing a write into their own project "
            "silo diverged from the measured corpus; got: {}"
            .format(sorted(triggering)),
        )

    def test_the_four_excluded_agents_are_excluded_by_the_directive_not_by_tools(self):
        # `wingman` cannot write at all (`tools: Read, Grep, Glob`), so a
        # tools-based filter would drop it and look equivalent. It is not:
        # business-analyst, devops and ux-designer all carry Write and Edit
        # and are excluded anyway, because their only own-silo mention is a
        # read directive ("Check whether ... exists. Also load ..."). Pinning
        # both halves keeps a later "just filter by tools" simplification
        # from passing as the same rule.
        for name in ("business-analyst", "devops", "ux-designer"):
            fm, body = split_frontmatter(
                (AGENTS_DIR / (name + ".md")).read_text(encoding="utf-8")
            )
            self.assertIn("Write", parse_tools(fm), name)
            self.assertFalse(directs_project_silo_write(body, name), name)
        fm, body = split_frontmatter(
            (AGENTS_DIR / "wingman.md").read_text(encoding="utf-8")
        )
        self.assertNotIn("Write", parse_tools(fm))
        self.assertFalse(directs_project_silo_write(body, "wingman"))


class ProjectSiloWriteDetectorBoundaryTest(unittest.TestCase):
    """Unit-level proofs for directs_project_silo_write itself -- mirrors
    InvocationDetectorBoundaryTest and BashToolDetectorBoundaryTest. Each
    case is a shape the module docstring names."""

    def test_a_read_only_own_silo_section_does_not_trigger(self):
        # `wingman.md`'s `## Instincts`, condensed: the own silo is named to
        # be READ, and the only "write" in the section is a prohibition.
        body = (
            "## Instincts\n"
            "Check if `docs/memory/wingman/instincts.md` exists (project Tier-2). "
            "Also load `~/.claude/memory/wingman/instincts.md` if it exists.\n"
            "After your work: If you discover a new pattern that qualifies as an "
            "Instinct, suggest it to the user (do not write it yourself)."
        )
        self.assertFalse(directs_project_silo_write(body, "wingman"))

    def test_a_write_sentence_in_the_neighbouring_section_does_not_trigger(self):
        # The proximity-window false positive the docstring reports: the
        # Tier-1 write sentence sits in the section directly above the
        # read-only own-silo mention, within a few hundred characters.
        body = (
            "## Project Memory (Tier 1)\n"
            "When you discover something other personas would benefit from, write "
            "it as `docs/memory/{type}_{slug}.md` and update the project index. "
            "Use the Write and Edit tools for this.\n\n"
            "## Instincts\n"
            "Check if `docs/memory/wingman/instincts.md` exists (project Tier-2)."
        )
        self.assertFalse(directs_project_silo_write(body, "wingman"))

    def test_a_write_section_naming_the_own_silo_triggers(self):
        body = (
            "## Persistent Agent Memory (Tier 2)\n"
            "You have a persistent Agent Memory directory at `docs/memory/qa-tester/`.\n"
            "- Use the Write and Edit tools to update your memory files"
        )
        self.assertTrue(directs_project_silo_write(body, "qa-tester"))

    def test_a_subsection_stays_inside_its_parent_section(self):
        # Shape A puts the path in `### Instincts`, one heading level below
        # the write directive. Splitting on `###` too would separate them.
        body = (
            "## Persistent Agent Memory (Tier 2)\n"
            "- Use the Write and Edit tools to update your memory files\n\n"
            "### Instincts\n"
            "Check whether `docs/memory/debugger/instincts.md` exists."
        )
        self.assertTrue(directs_project_silo_write(body, "debugger"))

    def test_a_heading_inside_a_fenced_block_does_not_split_the_section(self):
        # `project-guide.md` carries a fenced HANDOVER example whose first
        # line is `## project-guide`. Unmasked, it starts a new section and
        # cuts the surrounding one in half.
        body = (
            "## Memory & Handover\n"
            "Generally applicable heuristics -> `docs/memory/project-guide/`.\n"
            "```markdown\n"
            "## project-guide\n"
            "- 11.05.2026: an example handover line\n"
            "```\n"
            "You have `Edit` exclusively for your own memory."
        )
        self.assertTrue(directs_project_silo_write(body, "project-guide"))
        # And the mask is what does it: without it, the fenced heading splits
        # the section and the `Edit` grant lands in a section of its own.
        unmasked_sections = [
            s for s in re.split(SECTION_RE, body) if "docs/memory/project-guide/" in s
        ]
        self.assertEqual(len(unmasked_sections), 1)
        self.assertNotIn("Edit", unmasked_sections[0])

    def test_a_silo_write_permission_stated_only_in_frontmatter_is_out_of_scope(self):
        # `code-reviewer.md`'s frontmatter carries a `#` comment naming both
        # the write permission and the path; a whole-file scan would read it
        # as a body directive. Rule 6 reads the body only, like Rules 4 and 5.
        real_fm, _ = split_frontmatter(
            (AGENTS_DIR / "code-reviewer.md").read_text(encoding="utf-8")
        )
        self.assertIn("docs/memory/code-reviewer/", real_fm)
        self.assertIn("Write", real_fm)
        synthetic = (
            "---\n"
            "# Edit + Write are permitted ONLY for agent memory files "
            "(docs/memory/fake-agent/*)\n"
            "name: fake-agent\ndescription: x\ntools: Read, Edit, Write\n"
            "model: sonnet\n---\n\n"
            "## Role\nYou review code.\n"
        )
        _, body = split_frontmatter(synthetic)
        self.assertFalse(directs_project_silo_write(body, "fake-agent"))


class ProjectSiloContractDetectorBoundaryTest(unittest.TestCase):
    """Unit-level proofs for declares_project_memory_contract -- above all the
    one that decides whether Rule 6 is worth having: the sentence every agent
    already carries states the GLOBAL silo's contract and must not count as
    the project silo's."""

    def test_the_global_silo_contract_sentence_is_not_a_project_contract(self):
        # The structural discriminator. This is `code-reviewer.md:195` and
        # its fourteen siblings; a rule asking "is a contract named?" says
        # yes here and catches nothing.
        body = (
            "You also have a **global Tier-2 silo** at "
            "`~/.claude/memory/{your-agent-name}/instincts.md`. Frontmatter "
            "requires `scope: tier-2-global` + `agent: <name>`; ID scheme "
            "`XX-G-NNN`."
        )
        self.assertTrue(declares_global_silo_contract(body))
        self.assertFalse(declares_project_memory_contract(body))

    def test_a_project_contract_sentence_is_detected_in_both_shapes(self):
        self.assertTrue(declares_project_memory_contract(
            "Frontmatter for files in this silo follows `templates/MEMORY_SCHEMA.md`."
        ))
        self.assertTrue(declares_project_memory_contract(
            "Its frontmatter requires `name`, `description`, `type`, `last_updated`."
        ))

    def test_the_staleness_hint_is_not_a_contract_declaration(self):
        # `project-guide.md:116`, verbatim -- up to PRE_CONTRACT_COMMIT the
        # only `last_updated` anywhere in `agents/**`. The 30.08.2026 rollout
        # added a second one to every file, which is why the companion test
        # below reads the historical body rather than the current one.
        body = (
            "- **`docs/memory/MEMORY.md` Tier 1 or Tier 2 stale** (e.g. "
            "last_updated > 90 days in a `feedback`/`project` memory) -> hint "
            "in snapshot."
        )
        self.assertFalse(declares_project_memory_contract(body))

    def test_line_scoping_is_what_excludes_the_staleness_hint(self):
        # Without this pair the guard above could be passing because the
        # word "frontmatter" is absent from the excerpt rather than because
        # of the line scope. Same two tokens, one line apart vs. one line.
        two_lines = (
            "The frontmatter block is required for every memory file.\n"
            "Stale means last_updated is more than 90 days old."
        )
        one_line = "The frontmatter block requires last_updated."
        self.assertFalse(declares_project_memory_contract(two_lines))
        self.assertTrue(declares_project_memory_contract(one_line))

    def test_the_staleness_hint_alone_never_declared_the_contract(self):
        # `project-guide.md` now states the contract, so its current body can
        # no longer show that the staleness hint is not a declaration. The
        # body at PRE_CONTRACT_COMMIT can: same `last_updated > 90 days` line,
        # no contract sentence.
        historical = read_git_show(
            "{}:agents/project-guide.md".format(PRE_CONTRACT_COMMIT)
        )
        _, body = split_frontmatter(historical)
        self.assertIn("last_updated", body)
        self.assertFalse(declares_project_memory_contract(body))


class ProjectMemoryContractHistoricalRedProofTest(unittest.TestCase):
    """Both directions from real history, the shape Rule 4 already uses:
    `PRE_CONTRACT_COMMIT` is the tree before the contract sentence existed,
    the working tree is after. Nothing is mutated -- `git show` pulls a text
    copy, never a checkout.

    The pre-state is the structural fixture that matters: a body stating the
    GLOBAL silo's contract while being told to write project-scope memory.
    That is the shape a naive "is a contract stated?" rule passes, and it is
    the shape the finding had. Both fixtures are asserted to differ from
    their current counterpart ONLY by the inserted sentence, so the two
    directions compare the same file and not two unrelated states."""

    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["git", "rev-parse", "--verify",
             "{}^{{commit}}".format(PRE_CONTRACT_COMMIT)],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        cls.pre = {
            name: read_git_show("{}:agents/{}.md".format(PRE_CONTRACT_COMMIT, name))
            for name in PRE_CONTRACT_FIXTURES
        }

    def test_the_pre_state_states_the_global_contract_and_not_the_project_one(self):
        for name, text in self.pre.items():
            _, body = split_frontmatter(text)
            with self.subTest(agent=name):
                self.assertTrue(project_memory_write_triggers(body, name))
                self.assertTrue(declares_global_silo_contract(body))
                self.assertFalse(declares_project_memory_contract(body))

    def test_each_trigger_carries_its_own_fixture(self):
        # Without this, both fixtures could be firing the same trigger and the
        # Tier-1 half of the rule would be unproved.
        _, cr = split_frontmatter(self.pre["code-reviewer"])
        _, ba = split_frontmatter(self.pre["business-analyst"])
        self.assertEqual(project_memory_write_triggers(cr, "code-reviewer"),
                         {"own-silo", "tier-1"})
        self.assertEqual(project_memory_write_triggers(ba, "business-analyst"),
                         {"tier-1"})

    def test_the_current_tree_clears_the_rule_for_the_same_files(self):
        for name in PRE_CONTRACT_FIXTURES:
            body = _agent_body(name)
            with self.subTest(agent=name):
                self.assertTrue(project_memory_write_triggers(body, name))
                self.assertTrue(declares_project_memory_contract(body))

    def test_the_two_states_differ_only_by_the_inserted_sentence(self):
        # The fixture's own claim, pinned: if a later edit changes anything
        # else in these files, the "both directions" proof is comparing two
        # unrelated states and this says so instead of passing quietly.
        for name in PRE_CONTRACT_FIXTURES:
            current = (AGENTS_DIR / (name + ".md")).read_text(encoding="utf-8")
            sentence = (CONTRACT_SENTENCE_OWN_SILO if name == "code-reviewer"
                        else CONTRACT_SENTENCE_TIER1)
            added = len(current) - len(self.pre[name])
            with self.subTest(agent=name):
                self.assertEqual(current.count(sentence), 1)
                self.assertEqual(added, len(sentence),
                                 "{}: {} chars changed, not the {}-char "
                                 "sentence".format(name, added, len(sentence)))
                self.assertIn("MEMORY_SCHEMA", current)
                self.assertNotIn("MEMORY_SCHEMA", self.pre[name])

    def test_removing_the_global_contract_does_not_clear_the_rule(self):
        # Keys on WHICH contract, not how many: dropping the global sentence
        # from the CURRENT text leaves the project one stated, and dropping
        # the project one leaves the global.
        current = (AGENTS_DIR / "code-reviewer.md").read_text(encoding="utf-8")
        self.assertEqual(current.count(GLOBAL_SILO_CONTRACT_TOKEN), 1)
        without_global = current.replace(GLOBAL_SILO_CONTRACT_TOKEN, "scope: other")
        self.assertNotIn(GLOBAL_SILO_CONTRACT_TOKEN, without_global)
        _, body = split_frontmatter(without_global)
        self.assertFalse(declares_global_silo_contract(body))
        self.assertTrue(declares_project_memory_contract(body))

        # Note what the FIRST attempt at this mirror mutation got wrong, since
        # it is the trap G-141 warns about: replacing only the token
        # `MEMORY_SCHEMA` left the sentence's `last_updated` in place,
        # PROJECT_SCHEMA_TOKEN_RE still matched, and the "mutation" measured
        # nothing. The declaration is a sentence; removing it means removing
        # the sentence.
        self.assertEqual(current.count(CONTRACT_SENTENCE_OWN_SILO), 1)
        without_project = current.replace(CONTRACT_SENTENCE_OWN_SILO, "", 1)
        self.assertEqual(
            len(without_project), len(current) - len(CONTRACT_SENTENCE_OWN_SILO)
        )
        self.assertNotIn("MEMORY_SCHEMA", without_project)
        _, body2 = split_frontmatter(without_project)
        self.assertTrue(declares_global_silo_contract(body2))
        self.assertFalse(declares_project_memory_contract(body2))
        self.assertTrue(project_memory_write_triggers(body2, "code-reviewer"))


class AgentProjectMemoryContractTest(unittest.TestCase):
    """THE rule, applied to the tree: an agent body carrying either write
    trigger -- its own project silo (Rule 6) or Tier-1 project memory
    (Rule 7) -- must state the project-scope frontmatter contract.

    One rule with two triggers rather than two rules, because the OBLIGATION
    is one function: `templates/MEMORY_SCHEMA.md` specifies the same required
    fields for `docs/memory/{type}_{slug}.md` and `docs/memory/{agent}/`, so
    a separate "Rule 7" would have re-asserted Rule 6's obligation over an
    overlapping set -- two registers of one fact. Both triggers are
    nonetheless load-bearing: neither set contains the other
    (Tier1WriteDirectiveDetectionTest). The failure message names the trigger,
    so a violation still says which directive it is about."""

    def test_every_agent_with_a_memory_write_directive_states_the_contract(self):
        violations = []
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            name = field_value(fm, "name")
            triggers = project_memory_write_triggers(body, name)
            if triggers and not declares_project_memory_contract(body):
                violations.append("{}: directs a memory write ({}) but states "
                                  "no frontmatter contract for it"
                                  .format(path.name, "+".join(sorted(triggers))))
        self.assertFalse(
            violations,
            "agent(s) told to write project-scope memory without being told "
            "what the store requires -- add the `templates/MEMORY_SCHEMA.md` "
            "sentence to the body:\n" + "\n".join(sorted(violations)),
        )

    def test_every_agent_states_the_other_silos_contract_too(self):
        # The global Tier-2 contract was never the missing half; it is stated
        # everywhere. Pinned so a future edit cannot "fix" this rule by moving
        # the global sentence around instead of adding the project one.
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            self.assertTrue(declares_global_silo_contract(body), path.name)


class ProximityWindowIsNotAScopeTest(unittest.TestCase):
    """Turns the module docstring's second trap from prose into a
    measurement on the real files. For each of the four agents whose
    own-silo mention is read-only, a +/-200-character window around that
    mention:

      - DOES contain a write VERB (`write`, `update`), pulled in from the
        preceding `## Project Memory (Tier 1)` paragraph -- so a verb-based
        proximity trigger false-positives on all four;
      - does NOT contain the capitalized tool marker Rule 6 uses -- so with
        this marker the window is clean, and the window therefore cannot be
        cited as the reason those four are excluded;
      - is silent under the section-scoped trigger either way, which is the
        reason that actually holds.

    An earlier revision of the docstring claimed the window was what kept
    these four out. It was not, and only for the second marker; this test is
    what would have caught that (code-reviewer finding, 30.08.2026)."""

    READ_ONLY_AGENTS = ("business-analyst", "devops", "ux-designer", "wingman")
    WINDOW = 200

    def _window_around_own_silo(self, name):
        body = _agent_body(name)
        needle = PROJECT_SILO_PATH_TMPL.format(name)
        index = body.index(needle)
        return body[max(0, index - self.WINDOW):index + self.WINDOW]

    # `wingman` is listed but excluded from the verb-window assertion below.
    # Its Tier-1 paragraph was rewritten on 31.08.2026 (Rule 8) and the only
    # write verb left in it, "no write tools", now sits outside the +/-200
    # window. It is still a read-only own-silo mention, so it stays in the
    # other assertions.
    VERB_WINDOW_AGENTS = ("business-analyst", "devops", "ux-designer")

    def test_a_verb_based_proximity_window_matches_the_three_unedited_files(self):
        for name in self.VERB_WINDOW_AGENTS:
            self.assertTrue(
                WRITE_VERB_RE.search(self._window_around_own_silo(name)),
                "{}: the neighbouring Tier-1 sentence no longer reaches into "
                "the window -- the docstring's verb-marker measurement is "
                "stale".format(name),
            )

    def test_the_wingman_window_shows_what_rewording_the_neighbour_costs(self):
        # The same measurement on the file that WAS rewritten: the verb-based
        # window now matches nothing there. Kept rather than deleted, because
        # it is the cleanest evidence that a proximity window measures the
        # neighbourhood's wording rather than the mention itself -- exactly
        # why the trigger is section-scoped and not window-scoped.
        self.assertIsNone(WRITE_VERB_RE.search(self._window_around_own_silo("wingman")))
        self.assertFalse(directs_project_silo_write(_agent_body("wingman"), "wingman"))

    def test_the_tool_marker_is_absent_from_the_same_window(self):
        for name in self.READ_ONLY_AGENTS:
            self.assertIsNone(
                WRITE_TOOL_RE.search(self._window_around_own_silo(name)), name,
            )

    def test_the_section_scoped_trigger_is_silent_for_all_four(self):
        for name in self.READ_ONLY_AGENTS:
            self.assertFalse(directs_project_silo_write(_agent_body(name), name), name)

    def test_every_body_names_its_own_project_silo(self):
        # The count the second trap opens with: fifteen, not fourteen. A
        # path-only trigger has nothing left to discriminate on.
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            name = field_value(fm, "name")
            self.assertIn(PROJECT_SILO_PATH_TMPL.format(name), body, name)

    def test_a_path_only_trigger_flags_fourteen_of_the_fifteen(self):
        # ... and the fifteenth drops out for an unrelated reason: wingman's
        # body never names `Write` or `Edit` at all. Pinned so the docstring
        # number cannot drift away from the tree again.
        flagged = set()
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            name = field_value(fm, "name")
            if (PROJECT_SILO_PATH_TMPL.format(name) in body
                    and WRITE_TOOL_RE.search(body)):
                flagged.add(name)
        self.assertEqual(len(flagged), 14, sorted(flagged))
        self.assertNotIn("wingman", flagged)


class FencedBlockBalanceTest(unittest.TestCase):
    """mask_fenced_code_blocks toggles on every ``` line, so an UNCLOSED
    fence masks everything after it -- silently merging sections and flipping
    both Rule 6 detectors without a single word of the relevant text having
    changed. That failure mode does not announce itself, so the invariant the
    mask relies on is asserted directly (code-reviewer finding, 30.08.2026)."""

    def test_every_agent_body_has_balanced_code_fences(self):
        violations = []
        for path in _iter_agent_files():
            _, body = split_frontmatter(path.read_text(encoding="utf-8"))
            fences = sum(1 for line in body.splitlines() if FENCE_RE.match(line))
            if fences % 2:
                violations.append("{}: {} fence lines (odd)".format(path.name, fences))
        self.assertFalse(
            violations,
            "agent file(s) with an unclosed ``` fence -- every `## ` heading "
            "after it is masked away, which silently reshapes the sections "
            "Rule 6's trigger reads:\n" + "\n".join(violations),
        )

    def test_an_unclosed_fence_flips_the_trigger_verdict(self):
        # The consequence, shown rather than asserted abstractly: the same
        # body with and without its closing fence gives opposite verdicts.
        lines = [
            "## Memory",
            "```markdown",
            "## an example heading inside the fence",
            "```",
            "You have `Edit` for `docs/memory/qa-tester/`.",
        ]
        closed = "\n".join(lines)
        unclosed = "\n".join(line for line in lines if line != "```")
        self.assertEqual(closed.count("\n```\n"), 1)
        self.assertNotIn("\n```\n", unclosed)
        self.assertTrue(directs_project_silo_write(closed, "qa-tester"))
        self.assertFalse(directs_project_silo_write(unclosed, "qa-tester"))

# ---------------------------------------------------------------------------
# Rule 7: the SECOND trigger on Rule 6's obligation (Tier-1 project memory)
# ---------------------------------------------------------------------------
#
# Not a rule of its own. See the module docstring's "Rule 7 is a trigger, not
# a rule" for the measurement that decided this.

TIER1_MEMORY_PATH = "docs/memory/{type}_{slug}.md"

# Lowercase, because the Tier-1 directive is written as prose ("write it as
# ...", "write it to Tier 1 (...)"), not as a tool name. That is the opposite
# choice from WRITE_TOOL_RE and it is deliberate: this trigger keys on the
# PATH, which is unambiguous on its own, so the verb only has to confirm the
# sentence is a directive rather than a mention.
TIER1_WRITE_VERB_RE = re.compile(r"\bwrite\b", re.I)


def directs_tier1_memory_write(body):
    """Rule 7's trigger: True if one LINE of `body` names the Tier-1
    project-memory path together with a write verb. Line-scoped for the same
    reason the obligation is -- a path named in one paragraph and a write
    verb in the next are not one directive."""
    for line in mask_fenced_code_blocks(body).splitlines():
        if TIER1_MEMORY_PATH not in line:
            continue
        for match in TIER1_WRITE_VERB_RE.finditer(line):
            prefix = line[max(0, match.start() - len(BASH_DENIAL_PREFIX)):match.start()]
            if prefix.lower() == BASH_DENIAL_PREFIX:
                continue  # "you have no write tools" documents the absence
            return True
    return False


def project_memory_write_triggers(body, self_name):
    """Every trigger that obliges `body` to state the project-scope memory
    frontmatter contract, as a set of short names. Empty means no obligation.
    Returning the names rather than a bool is what lets a failure say WHICH
    directive it is complaining about."""
    triggers = set()
    if directs_project_silo_write(body, self_name):
        triggers.add("own-silo")
    if directs_tier1_memory_write(body):
        triggers.add("tier-1")
    return triggers


class Tier1WriteDirectiveDetectionTest(unittest.TestCase):
    """Rule 7's trigger, measured against the corpus. It fires on THIRTEEN of
    the fifteen -- the `## Project Memory (Tier 1)` paragraph is near-identical
    boilerplate (two wordings, "write it as ..." and "write it to Tier 1
    (...)", both matched). Two exceptions, for different reasons:
    `project-guide` names no Tier-1 memory path at all (its `## Write
    Permissions (explicit)` section lists "memory files of other agents" under
    what it does NOT write), and `wingman`'s paragraph was reworded on
    31.08.2026 under Rule 8, because it had no write tool to carry it out.

    The brief that ordered this rule assumed it covers "the four Rule 6 does
    not see". It does -- and it also fails to see one that Rule 6 does. The
    two triggers are COMPLEMENTARY, not nested."""

    EXPECTED_TIER1_TRIGGERS = frozenset({
        "business-analyst", "code-reviewer", "debugger", "devops", "konzeptor",
        "pentester", "project-planner", "qa-tester", "security-master",
        "senior-developer", "system-architekt", "tech-writer", "ux-designer",
    })

    def test_the_tier1_trigger_set_matches_the_measured_corpus(self):
        triggering = set()
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            if directs_tier1_memory_write(body):
                triggering.add(field_value(fm, "name"))
        self.assertEqual(
            triggering, set(self.EXPECTED_TIER1_TRIGGERS),
            "the set of agents directing a Tier-1 project-memory write "
            "diverged from the measured corpus; got: {}".format(sorted(triggering)),
        )

    def test_neither_trigger_set_contains_the_other(self):
        # The measurement that decides the shape of the rule. If one set
        # contained the other, the smaller trigger would be redundant and a
        # single trigger would do. Neither does: `project-guide` triggers only
        # on own-silo, three read-only agents only on Tier-1. Both triggers are
        # load-bearing -- and since the OBLIGATION they impose is the same
        # function, they belong to one rule, not two.
        own_silo, tier1 = set(), set()
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            name = field_value(fm, "name")
            if directs_project_silo_write(body, name):
                own_silo.add(name)
            if directs_tier1_memory_write(body):
                tier1.add(name)
        self.assertEqual(own_silo - tier1, {"project-guide"})
        self.assertEqual(
            tier1 - own_silo, {"business-analyst", "devops", "ux-designer"},
        )

    def test_exactly_one_agent_is_obliged_by_neither_trigger(self):
        # `wingman` after the Rule 8 fix: it directs no memory write at all,
        # so the contract rule imposes nothing on it. It keeps the contract
        # sentence anyway, describing the files it READS -- which is why the
        # corpus-wide `MEMORY_SCHEMA` count is 15 while the obliged set is 14.
        # Pinned as a pair so neither number can drift alone.
        uncovered = set()
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            name = field_value(fm, "name")
            if not project_memory_write_triggers(body, name):
                uncovered.add(name)
        self.assertEqual(uncovered, {"wingman"})
        stating = sum(
            1 for path in _iter_agent_files()
            if declares_project_memory_contract(
                split_frontmatter(path.read_text(encoding="utf-8"))[1])
        )
        self.assertEqual(stating, EXPECTED_AGENT_COUNT)


class Tier1WriteDetectorBoundaryTest(unittest.TestCase):
    """Unit-level proofs for directs_tier1_memory_write -- mirrors the
    boundary classes for Rules 4, 5 and 6."""

    def test_the_two_real_wordings_are_both_detected(self):
        # Verbatim from the corpus: the short form (business-analyst, devops,
        # ux-designer, wingman) and the long form (the other eleven).
        short = ("... write it as `docs/memory/{type}_{slug}.md` (`type` "
                 "∈ `feedback` / `project` / `reference`) and update the "
                 "project index.")
        long = ("... write it to Tier 1 (`docs/memory/{type}_{slug}.md` with "
                "`type` ∈ `feedback` / `project` / `reference`) and update "
                "the project index — do not bury it in your silo.")
        self.assertTrue(directs_tier1_memory_write(short))
        self.assertTrue(directs_tier1_memory_write(long))

    def test_a_read_only_mention_of_the_tier1_path_is_not_a_directive(self):
        body = ("Tier-1 memories live at `docs/memory/{type}_{slug}.md`; read "
                "them before consulting your own silo.")
        self.assertFalse(directs_tier1_memory_write(body))

    def test_a_write_verb_on_the_next_line_is_not_the_same_directive(self):
        # Line scoping, proved by the pair rather than asserted: the same two
        # tokens, one line apart, must not combine into a directive.
        two_lines = ("Tier-1 memories live at `docs/memory/{type}_{slug}.md`.\n"
                     "You may write to your own silo.")
        self.assertFalse(directs_tier1_memory_write(two_lines))

    def test_a_denied_write_next_to_the_tier1_path_is_not_a_directive(self):
        # Same guard shape Rule 5 uses for "you have no Bash access": a write
        # verb immediately preceded by "no " documents the ABSENCE of the
        # capability, which is the correct way to write a read-only agent's
        # memory section. Without it, the honest wording is indistinguishable
        # from the instruction it replaces.
        body = ("You have no write tools: name it in your summary and leave "
                "`docs/memory/{type}_{slug}.md` to the orchestrator.")
        self.assertFalse(directs_tier1_memory_write(body))

    def test_the_guard_is_narrow_and_does_not_swallow_a_real_directive(self):
        # The other half: a line that also contains "no " somewhere but whose
        # write verb is affirmative still counts. Without this pair the guard
        # could be disabling the trigger outright.
        body = ("There is no shortcut here: write it as "
                "`docs/memory/{type}_{slug}.md` and update the project index.")
        self.assertTrue(directs_tier1_memory_write(body))

    def test_the_tier1_path_inside_a_fenced_example_is_masked(self):
        body = ("```markdown\n"
                "write it as `docs/memory/{type}_{slug}.md`\n"
                "```\n"
                "This block is an example, not an instruction.")
        self.assertFalse(directs_tier1_memory_write(body))

class Rule5CaseWideningRedProofTest(unittest.TestCase):
    """Both directions for the 31.08.2026 widening of BASH_TOOL_RE to
    re.IGNORECASE, from real history rather than a synthetic body.

    `agents/qa-tester.md` at PRE_CONTRACT_COMMIT carries "Use bash to run
    existing tests and analyze their output" in a `## Practical Execution`
    list whose other bullets all name tools it does have, while `tools:` is
    `Glob, Grep, Read, Write, Edit`. Case-sensitively that sentence is
    invisible: it names the tool in lowercase. The widening is what sees it,
    and the pre-state is what proves the widening was not cosmetic."""

    @classmethod
    def setUpClass(cls):
        cls.pre_text = read_git_show(
            "{}:agents/qa-tester.md".format(PRE_CONTRACT_COMMIT)
        )

    def test_the_pre_state_names_the_tool_in_lowercase_without_carrying_it(self):
        fm, body = split_frontmatter(self.pre_text)
        self.assertIn("Use bash to run existing tests", body)
        self.assertNotIn("Bash", parse_tools(fm))
        self.assertTrue(body_names_bash_tool(body))

    def test_a_case_sensitive_detector_would_have_missed_it(self):
        # The measurement that justifies the widening, as an assertion: the
        # old pattern against the same text finds nothing. Without this the
        # widening could be a no-op dressed up as a fix.
        _, body = split_frontmatter(self.pre_text)
        case_sensitive = re.compile(r"\bBash\b")
        self.assertIsNone(case_sensitive.search(body))
        self.assertIsNotNone(BASH_TOOL_RE.search(body))

    def test_the_current_text_makes_no_claim_at_all(self):
        fm, body = split_frontmatter(
            (AGENTS_DIR / "qa-tester.md").read_text(encoding="utf-8")
        )
        self.assertNotIn("Bash", parse_tools(fm))
        self.assertFalse(body_names_bash_tool(body))
        self.assertIn("You have no shell: you cannot run tests yourself", body)

    def test_the_widening_costs_exactly_one_match_on_this_corpus(self):
        # The price of opening the case, measured on the tree rather than
        # asserted: over the CURRENT corpus the two patterns agree
        # everywhere. The one file where they disagreed is the one that was
        # corrected above -- so the widening bought a true positive and no
        # false one. If a later body says `bash script.sh` as a command
        # rather than as the tool's name, this test is where that shows up:
        # the widened pattern counts it, the narrow one does not.
        narrow = re.compile(r"\bBash\b")
        disagreements = []
        for path in _iter_agent_files():
            _, body = split_frontmatter(path.read_text(encoding="utf-8"))
            wide_hit = body_names_bash_tool(body)
            narrow_hit = any(
                body[max(0, m.start() - len(BASH_DENIAL_PREFIX)):m.start()].lower()
                != BASH_DENIAL_PREFIX
                for m in narrow.finditer(body)
            )
            if wide_hit != narrow_hit:
                disagreements.append(path.name)
        self.assertFalse(disagreements, "widened and narrow Bash detectors "
                                        "disagree on: {}".format(disagreements))

# ---------------------------------------------------------------------------
# Rule 8: a memory write directive needs a write TOOL
# ---------------------------------------------------------------------------
#
# Third member of the same family as Rules 4 and 5: the body claims or is
# given a capability its own `tools:` line does not provide. Rule 4 is about
# `Agent`, Rule 5 about `Bash`, Rule 8 about `Write`/`Edit`. Rule 8 reuses
# Rules 6/7's triggers rather than adding a third one -- what differs is the
# OBLIGATION (a tool, not a documented contract), which is why this is a rule
# of its own and Rule 7 is not.

WRITE_TOOLS = frozenset({"Write", "Edit"})


def has_write_tool(frontmatter):
    """True if `tools:` provides any tool that can create or change a file.
    `Edit` alone counts -- `project-guide` is granted exactly that and its
    body says so ("You have `Edit` exclusively for ...")."""
    return bool(WRITE_TOOLS & set(parse_tools(frontmatter)))


class AgentWriteToolRequiredForMemoryWriteTest(unittest.TestCase):
    """Rule 8, applied to the tree: an agent whose body directs a project
    memory write must carry a write tool.

    The instance this was built for: `wingman.md` at PRE_CONTRACT_COMMIT
    carried the Tier-1 directive "write it as `docs/memory/{type}_{slug}.md`
    ... and update the project index" with `tools: Read, Grep, Glob` -- an
    instruction it could not execute. Resolved by prose, not by a grant:
    `wingman` is a read-only consolidator by design (its own description says
    it reads result files and summarises), so granting `Write` would have
    contradicted the role rather than repaired the sentence."""

    def test_every_memory_write_directive_is_backed_by_a_write_tool(self):
        violations = []
        for path in _iter_agent_files():
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            name = field_value(fm, "name")
            triggers = project_memory_write_triggers(body, name)
            if triggers and not has_write_tool(fm):
                violations.append(
                    "{}: body directs a memory write ({}) but tools: has "
                    "neither Write nor Edit -- {}".format(
                        path.name, "+".join(sorted(triggers)), parse_tools(fm))
                )
        self.assertFalse(
            violations,
            "agent(s) instructed to write a file they have no tool to "
            "write:\n" + "\n".join(sorted(violations)),
        )


class Rule8HistoricalRedProofTest(unittest.TestCase):
    """Both directions from real history, like Rule 4's and the contract
    rule's. Without the pre-state this rule is an assertion that happens to
    hold, not one shown to discriminate."""

    @classmethod
    def setUpClass(cls):
        cls.pre_text = read_git_show(
            "{}:agents/wingman.md".format(PRE_CONTRACT_COMMIT)
        )

    def test_the_pre_state_directs_a_write_it_cannot_perform(self):
        fm, body = split_frontmatter(self.pre_text)
        self.assertEqual(project_memory_write_triggers(body, "wingman"), {"tier-1"})
        self.assertFalse(has_write_tool(fm))
        self.assertEqual(parse_tools(fm), ["Read", "Grep", "Glob"])

    def test_the_current_text_directs_no_write(self):
        fm, body = split_frontmatter(
            (AGENTS_DIR / "wingman.md").read_text(encoding="utf-8")
        )
        self.assertFalse(has_write_tool(fm), "the fix must not have been a "
                                             "tool grant -- wingman is a "
                                             "read-only consolidator")
        self.assertEqual(project_memory_write_triggers(body, "wingman"), set())

    def test_the_tools_line_is_unchanged_between_the_two_states(self):
        # Pins that the repair went through the PROSE and not through the
        # capability: if a later edit grants the tool instead, the two
        # directions above would both pass while the role boundary quietly
        # moved. This is the assertion that notices.
        pre_fm, _ = split_frontmatter(self.pre_text)
        cur_fm, _ = split_frontmatter(
            (AGENTS_DIR / "wingman.md").read_text(encoding="utf-8")
        )
        self.assertEqual(parse_tools(pre_fm), parse_tools(cur_fm))

    def test_a_synthetic_grant_would_clear_the_rule(self):
        # The other direction of the same fix, so the rule is shown to
        # respond to the tool and not only to the prose: the untouched
        # pre-state body plus a write tool is not a violation.
        fm, body = split_frontmatter(self.pre_text)
        granted = fm.replace("tools: Read, Grep, Glob", "tools: Read, Grep, Glob, Write")
        self.assertEqual(fm.count("tools: Read, Grep, Glob"), 1)
        self.assertTrue(has_write_tool(granted))
        self.assertTrue(project_memory_write_triggers(body, "wingman"))


class ModuleHasOneEntrypointTest(unittest.TestCase):
    """A second `unittest.main()` in the middle of a module is a silent
    truncation of its own suite: run as `python3 <file>` rather than through
    the loader, execution stops at the first one, only the classes defined
    above it are discovered, and the short run still reports OK.

    This module carried exactly that from the WI-0128 wave until 31.08.2026
    -- a stray entrypoint after Rule4HistoricalRedProofTest, so a direct
    invocation ran Rules 1-4 and silently skipped Rules 5-8 while printing a
    green summary (code-reviewer finding, 31.08.2026). Found by review, not
    by any run, because `python3 -m unittest` never sets `__name__` to
    `__main__` and is therefore blind to it."""

    # A CALL STATEMENT -- a whole line that is nothing but the call. Counting
    # every occurrence of the string instead was the first attempt and it
    # cannot work here: this class's own docstring and the assertion below
    # both mention the name, so the scan counted itself and stayed red after
    # the real duplicate was gone.
    ENTRYPOINT_CALL_RE = re.compile(r"(?m)^[ \t]*unittest\.main\(\)[ \t]*$")

    def test_this_module_defines_exactly_one_entrypoint(self):
        source = Path(__file__).read_text(encoding="utf-8")
        calls = self.ENTRYPOINT_CALL_RE.findall(source)
        self.assertEqual(
            len(calls), 1,
            "more than one entrypoint call in this module -- a direct "
            "`python3` invocation stops at the first and reports OK on a "
            "partial suite",
        )

    def test_the_scan_sees_a_second_entrypoint_and_ignores_a_mention(self):
        # Both halves, since a scan that counts nothing would also pass the
        # test above once the duplicate was removed.
        two = 'class A:\n    pass\n\nif x:\n    unittest.main()\n\nif y:\n    unittest.main()\n'
        self.assertEqual(len(self.ENTRYPOINT_CALL_RE.findall(two)), 2)
        mention = '# see unittest.main() above\nprint("unittest.main()")\n'
        self.assertEqual(self.ENTRYPOINT_CALL_RE.findall(mention), [])

    def test_the_entrypoint_is_the_last_statement_in_the_file(self):
        # The count alone would pass if the single entrypoint sat in the
        # middle. This pins the position too.
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertTrue(source.rstrip().endswith("unittest.main()"))


if __name__ == "__main__":
    unittest.main()
