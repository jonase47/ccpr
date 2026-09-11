"""test_agent_handover_write_boundary.py -- CCP-1178: pins the corrected
`## Handover` block across agents/*.md.

## The defect

13 files in `agents/` carried the identical instruction "read it at the start
for context. Update it at the end of your work with your result and the next
steps." -- present since the initial public release (`0845801`). This
contradicted the rest of the framework, which treats `docs/HANDOVER.md` as
orchestrator-owned state: `commands/p3-architecture.md` already states "The
orchestrator owns the final `docs/HANDOVER.md` update", and `CLAUDE.md` says
`code-reviewer` "never writes source, tests or project docs -- only its own
memory silo" while `code-reviewer`'s own agent file told it to update
HANDOVER. `project-guide.md` and `wingman.md` are explicitly OUT of scope
(project-guide's own <=5-line `## Memory & Handover` section is a documented,
separate exception; wingman never had the block).

## PO decision (11.09.2026, option B of three)

Remove the generic block-rewrite instruction from all 13 agents; keep the
`## Open Points` append-only inbox (CCP-1001) as the only permitted agent
write, gated on running in the MAIN working tree -- a worktree-isolated agent
reports the line in its final message instead, since a worktree cannot safely
append to a file shared with the orchestrator's own tree. `code-reviewer` is
report-only even for the inbox line, matching `CLAUDE.md`'s "only its own
memory silo": it hands the finding over as a ready-made line instead of
appending it itself.

## Why this module asserts the POSITIVE form, not just the absence of the
old sentence

`test_handover_epilogue_bullet.py` states the house rule first (cited there
from `test_absence_only_assertions.py`'s own module docstring): a
negative-only check ("the old string does not occur") passes vacuously on a
file that never carried the concept at all, and would not catch a NEW agent
file reintroducing the same instruction under different wording. This module
follows the same shape: `AbsenceTest` proves the removed sentence is gone,
and `PresenceTest` independently proves the CORRECTED block is present in
exactly the 13 in-scope files -- neither assertion alone would catch every
regression the other misses.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "agents"

# The removed instruction. Present, byte-for-byte identical, in all 13
# in-scope files before this fix (`grep -l "Update it at the end of your
# work" agents/*.md` -> 13).
OLD_SENTENCE = (
    "Update it at the end of your work with your result and the next steps."
)

# The common, unchanged prefix every one of the 13 files' `## Handover`
# block still opens with.
READ_FOR_CONTEXT_PREFIX = (
    "If `docs/HANDOVER.md` exists in the project directory, read it at the "
    "start for context. "
)

# The corrected instruction shared by the 12 non-reviewer agents: read-only
# for context, the orchestrator consolidates, and the one narrow write
# exception (the inbox line) is gated on the main working tree.
STANDARD_INSTRUCTION = (
    "Do not edit it: the orchestrator owns it and consolidates after your "
    "run — report your result and the next steps in your final message "
    "instead. One exception: a finding outside your assignment may be "
    "appended as one `- INBOX | …` line under `## Open Points`, in the "
    "format defined in `templates/HANDOVER_TEMPLATE.md`, and only when you "
    "run in the main working tree; in a worktree-isolated run, put that "
    "line in your final message instead."
)

# code-reviewer's variant: report-only even for the inbox line, matching
# CLAUDE.md's "never writes source, tests or project docs -- only its own
# memory silo" and its own `tools:` comment ("Edit + Write are permitted
# ONLY for agent memory files").
CODE_REVIEWER_INSTRUCTION = (
    "Do not edit it: the orchestrator owns it and consolidates after your "
    "run — report your result and the next steps in your final message "
    "instead. Your `Edit`/`Write` access is memory-only, so the `## Open "
    "Points` inbox append is not yours to make either: hand any finding "
    "outside your assignment over as a ready-made `- INBOX | …` line, "
    "in the format defined in `templates/HANDOVER_TEMPLATE.md`, for the "
    "orchestrator to append."
)

STANDARD_BLOCK = READ_FOR_CONTEXT_PREFIX + STANDARD_INSTRUCTION
CODE_REVIEWER_BLOCK = READ_FOR_CONTEXT_PREFIX + CODE_REVIEWER_INSTRUCTION

# The 12 agents that get the standard, byte-identical block -- one pattern,
# easy to guard. `code-reviewer` carries its own variant (see above);
# `project-guide` and `wingman` are out of scope (see module docstring).
STANDARD_AGENTS = frozenset({
    "business-analyst", "debugger", "devops", "konzeptor", "pentester",
    "project-planner", "qa-tester", "security-master", "senior-developer",
    "system-architekt", "tech-writer", "ux-designer",
})

REVIEWER_AGENT = "code-reviewer"

IN_SCOPE_AGENTS = STANDARD_AGENTS | {REVIEWER_AGENT}

# project-guide's own `## Memory & Handover` section is a documented,
# separate exception (out of scope per the PO decision); wingman never
# carried the removed sentence at all. Both stay OUT of IN_SCOPE_AGENTS.
OUT_OF_SCOPE_AGENTS = frozenset({"project-guide", "wingman"})


def _agent_names():
    return sorted(p.stem for p in AGENTS_DIR.glob("*.md"))


def _read(name):
    return (AGENTS_DIR / (name + ".md")).read_text(encoding="utf-8")


class AbsenceTest(unittest.TestCase):
    """The removed sentence must not occur in ANY agents/*.md file --
    including project-guide.md and wingman.md, which never had a reason to
    carry it and must not gain it back either."""

    def test_the_old_update_instruction_is_gone_from_every_agent_file(self):
        # Built as a for/append loop rather than a comprehension -- the same
        # shape test_handover_epilogue_bullet.py's own `violations` uses --
        # so the assertion states an invariant ("must be empty"), not a count
        # that ages with the repository.
        offenders = []
        for name in _agent_names():
            if OLD_SENTENCE in _read(name):
                offenders.append(name)
        self.assertEqual(
            [],
            offenders,
            "agent file(s) still instruct rewriting docs/HANDOVER.md: "
            + ", ".join(offenders),
        )


class PresenceTest(unittest.TestCase):
    """The corrected block must be present in exactly the 13 in-scope
    files -- 12 with STANDARD_BLOCK, code-reviewer with
    CODE_REVIEWER_BLOCK -- and in no other agent file."""

    def test_all_agent_names_accounted_for(self):
        # Fixture integrity: if a new agent file is added, it must be
        # triaged into IN_SCOPE_AGENTS or OUT_OF_SCOPE_AGENTS deliberately,
        # not silently skipped by this test.
        self.assertEqual(
            set(_agent_names()), IN_SCOPE_AGENTS | OUT_OF_SCOPE_AGENTS
        )

    def test_the_12_standard_agents_carry_the_identical_block(self):
        for name in sorted(STANDARD_AGENTS):
            with self.subTest(agent=name):
                self.assertIn(STANDARD_BLOCK, _read(name))

    def test_code_reviewer_carries_the_report_only_variant(self):
        text = _read(REVIEWER_AGENT)
        self.assertIn(CODE_REVIEWER_BLOCK, text)
        self.assertNotIn(STANDARD_BLOCK, text)

    def test_12_files_carry_the_standard_block(self):
        # A real pin (ADR-0012): 12 ages if an agent is added, removed, or
        # rewritten to a different block -- see pin_registry.py's PIN_GROUPS
        # for what "derived" commits to.
        count = sum(
            1 for name in _agent_names() if STANDARD_BLOCK in _read(name)
        )
        self.assertEqual(  # pin: derived agent-handover-standard-block-count
            12, count
        )

    def test_exactly_one_file_carries_the_reviewer_block(self):
        count = sum(
            1 for name in _agent_names() if CODE_REVIEWER_BLOCK in _read(name)
        )
        self.assertEqual(  # pin: derived agent-handover-reviewer-block-count
            1, count
        )

    def test_out_of_scope_agents_carry_neither_block(self):
        for name in sorted(OUT_OF_SCOPE_AGENTS):
            with self.subTest(agent=name):
                text = _read(name)
                self.assertNotIn(STANDARD_BLOCK, text)
                self.assertNotIn(CODE_REVIEWER_BLOCK, text)


if __name__ == "__main__":
    unittest.main()
