"""test_p4_sprint_gate_frontmatter.py -- CCP-1181: commands/p4-sprint.md's
own step 4 prints two ```yaml frontmatter templates for `docs/planning/
SPRINT.md` (the flat layout, 4b, and the sub-index layout, 4c). Neither
carried a `gate:` field, even though SPRINT.md is the one living-file
exception in scripts/phase-docs-lint.sh (check (k), WI-0129,
templates/PHASE_DOC_SCHEMA.md's "Gate verdict" section) that still requires
one -- `/gate-p5` records its verdict there because SPRINT.md is the only
document that carries it. An author who followed either template literally
would write a SPRINT.md that fails the project's own lint.

Ground truth, not retyped: this module extracts the actual ```yaml fences
out of commands/p4-sprint.md's own source text (same house pattern as
test_frontmatter_examples_match_the_lint.py and read_enum() in
test_phase_docs_lint.py) and feeds each, verbatim but with its placeholder
tokens substituted, to the shipped scripts/phase-docs-lint.sh as a real
docs/planning/SPRINT.md. A future edit to either template is caught here
without anyone updating a hand-typed copy.
"""

import re
import subprocess
import unittest
from pathlib import Path

from .test_phase_docs_lint import PhaseDocsLintTestBase

REPO_ROOT = Path(__file__).resolve().parents[2]
P4_SPRINT_MD = REPO_ROOT / "commands" / "p4-sprint.md"

YAML_FENCE_RE = re.compile(r"```yaml\n(.*?\n)```", re.DOTALL)


def _yaml_blocks_after(text, header_marker, stop_marker):
    """Every ```yaml fence between header_marker and stop_marker (both
    literal substrings of commands/p4-sprint.md). Raises loudly if the
    header can no longer be found -- a renamed section should fail this
    test's setup, not silently scan zero blocks."""
    start = text.index(header_marker)
    end = text.index(stop_marker, start)
    section = text[start:end]
    return [m.group(1) for m in YAML_FENCE_RE.finditer(section)]


def _substitute_placeholders(block_text):
    """Fills in the angle-bracket placeholders p4-sprint.md's templates use
    (<DD.MM.YYYY>, <sha>, <N>) with values the lint's own checks accept, so
    the resulting frontmatter tests exactly one thing: whether `gate:` is
    present and valid -- not whether an unrelated placeholder is well-formed."""
    block_text = block_text.replace("<DD.MM.YYYY>", "04.05.2026")
    block_text = block_text.replace("<sha>", "a" * 40)
    block_text = block_text.replace("<N>", "1")
    return block_text


class P4SprintSprintTemplateExtractionTest(unittest.TestCase):
    """Sanity check on the extraction itself -- both templates must still be
    found, exactly once each, at the section markers this module's other
    tests rely on. Fails loudly (not silently-zero) if commands/p4-sprint.md
    is restructured underneath this test."""

    def test_flat_and_subindex_sprint_templates_are_found(self):
        text = P4_SPRINT_MD.read_text(encoding="utf-8")

        flat_blocks = _yaml_blocks_after(
            text,
            "#### 4b. Flat Layout — Sprint",
            "#### 4c. Sub-Index Layout — Sprint",
        )
        # Section 4c contains two ```yaml fences: the docs/planning/SPRINT.md
        # sub-index template itself (first, `kind: sub-index`), followed by
        # the per-sprint detail file template (`kind: sprint-detail`,
        # docs/planning/sprint/SPRINT-NN.md -- a different file, out of this
        # module's scope). Only the first is the SPRINT.md template this
        # test binds to.
        subindex_blocks = _yaml_blocks_after(
            text,
            "#### 4c. Sub-Index Layout — Sprint",
            "#### 4d. Choose Layout — Risks",
        )

        self.assertEqual(len(flat_blocks), 1, flat_blocks)
        self.assertEqual(len(subindex_blocks), 2, subindex_blocks)
        self.assertIn("kind: sub-index", subindex_blocks[0])
        self.assertIn("kind: sprint-detail", subindex_blocks[1])


class P4SprintSprintTemplateGateFieldTest(PhaseDocsLintTestBase):
    """Both SPRINT.md templates p4-sprint.md step 4 prints must pass
    scripts/phase-docs-lint.sh's check (k) unchanged -- a `gate:` field
    present and set to a VALID_SPRINT_VERDICTS token. Writes the extracted
    block verbatim (placeholders substituted) as docs/planning/SPRINT.md and
    runs the real shipped lint against it, exactly as an author who copied
    the template into their own project would end up doing."""

    def _write_and_lint(self, block_text):
        # block_text is the raw fence content, e.g. "---\nphase: P4\n...\n---\n"
        # -- the frontmatter delimiters are already part of the template as
        # printed in commands/p4-sprint.md, so this appends the body as-is
        # rather than adding a second pair of "---" markers.
        doc_text = _substitute_placeholders(block_text) + "\n# Sprint\n\nBody.\n"
        self.write_doc("planning/SPRINT.md", doc_text)
        return self.run_lint()

    def test_flat_layout_template_passes_the_gate_check(self):
        text = P4_SPRINT_MD.read_text(encoding="utf-8")
        block_text = _yaml_blocks_after(
            text,
            "#### 4b. Flat Layout — Sprint",
            "#### 4c. Sub-Index Layout — Sprint",
        )[0]

        result = self._write_and_lint(block_text)

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(
            any("gate" in e for e in errors),
            "flat SPRINT.md template (4b) fails phase-docs-lint.sh's gate "
            "check: {}".format(errors),
        )

    def test_subindex_layout_template_passes_the_gate_check(self):
        text = P4_SPRINT_MD.read_text(encoding="utf-8")
        block_text = _yaml_blocks_after(
            text,
            "#### 4c. Sub-Index Layout — Sprint",
            "#### 4d. Choose Layout — Risks",
        )[0]

        result = self._write_and_lint(block_text)

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(
            any("gate" in e for e in errors),
            "sub-index SPRINT.md template (4c) fails phase-docs-lint.sh's "
            "gate check: {}".format(errors),
        )


if __name__ == "__main__":
    unittest.main()
