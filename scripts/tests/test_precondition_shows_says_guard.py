"""test_precondition_shows_says_guard.py -- CCP-1187: a command precondition
must read a document's MACHINE-READABLE field (e.g. frontmatter `gate:`),
never describe what the document "shows" or "says" in prose.

## The defect this guards

`commands/p5-polish.md`'s "Preconditions (Hard Block on Violation)" section
stated its gate-p5 precondition as: 'Last `gate-p5` entry in `SPRINT.md`
shows `Sprint Done` or `Conditionally Done`.' Two problems layered on top of
each other: (1) "shows" points a reader at prose in the document body, not
at the frontmatter `gate:` field `scripts/phase-docs-lint.sh` and
`scripts/command-check.py` actually validate/read; (2) the quoted values
themselves, `Sprint Done` / `Conditionally Done`, are not members of either
closed vocabulary `scripts/lib/gate_checklists.py`'s GATE_VERDICT_VOCABULARIES
defines (`SPRINT.md`'s own values are `pending` / `done` /
`conditionally_done` / `not_done`, snake_case, no title-case prose form).
A precondition phrased this way cannot be checked mechanically and, read
literally, checks for values that never appear in a real SPRINT.md.

## What counts as a violation, deliberately narrow

A line in commands/*.md that combines BOTH:
  (a) the verb "shows" or "says" (word-boundary, case-insensitive: a
      command may legitimately say "the CLI shows an error" about a running
      tool's own output -- that is not this defect), AND
  (b) a backtick-quoted reference to a Markdown document in the same line
      (`` `...*.md` ``) -- the shape that identifies "the document says/
      shows X" specifically, as opposed to "shows" describing something
      else entirely (a diff, a monitoring dashboard, a CLI response).

Measured against the full commands/*.md corpus before the fix: this
combination matches exactly one line, `p5-polish.md`'s precondition #1.
Every other "shows"/"says" occurrence in the corpus (anchor.md's "document
that merely shows drift", cross-check.md's "an Inviolable says
'local-only'", lean-promote.md's "If LEARNINGS says 'pivot'",
specialize.md's "shows a diff", p8-iteration.md's "Monitoring shows no
critical anomalies") has no backtick `.md` reference on the same line and
is correctly left alone -- none of them describe a document's own prose as
a gate precondition.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "commands"

SHOWS_SAYS_RE = re.compile(r"\b(shows|says)\b", re.IGNORECASE)
MD_BACKTICK_REF_RE = re.compile(r"`[^`\n]*\.md[^`\n]*`")


def _violations():
    violations = []
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        rel = path.relative_to(REPO_ROOT)
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if SHOWS_SAYS_RE.search(line) and MD_BACKTICK_REF_RE.search(line):
                violations.append(f"{rel}:{line_no}  {line.strip()}")
    return violations


class PreconditionShowsSaysGuardTest(unittest.TestCase):
    """No commands/*.md line may state a precondition in terms of what a
    Markdown document 'shows' or 'says' -- see module docstring for the
    exact, narrow matching rule and the honest scope measurement."""

    def test_no_command_states_a_precondition_via_a_document_shows_or_says(self):
        violations = _violations()
        self.assertEqual(
            violations, [],
            "commands/*.md line(s) describing a precondition as what a "
            "document 'shows'/'says' instead of reading its machine-"
            "readable field:\n" + "\n".join(violations),
        )


class GuardMatchingRuleSanityTest(unittest.TestCase):
    """Pins the guard's own matching rule on synthetic lines, independent of
    the corpus's current state -- both the catch and the two deliberate
    non-catches (no .md reference; .md reference but no shows/says)."""

    def test_a_document_shows_line_with_md_reference_is_flagged(self):
        line = "1. Last `gate-p5` entry in `SPRINT.md` shows `Sprint Done`."
        self.assertTrue(SHOWS_SAYS_RE.search(line) and MD_BACKTICK_REF_RE.search(line))

    def test_shows_without_an_md_reference_is_not_flagged(self):
        line = "No auto-commit. It writes files and shows a diff."
        self.assertFalse(SHOWS_SAYS_RE.search(line) and MD_BACKTICK_REF_RE.search(line))

    def test_an_md_reference_without_shows_or_says_is_not_flagged(self):
        line = "Read `SPRINT.md`'s frontmatter `gate:` field."
        self.assertFalse(SHOWS_SAYS_RE.search(line) and MD_BACKTICK_REF_RE.search(line))


if __name__ == "__main__":
    unittest.main()
