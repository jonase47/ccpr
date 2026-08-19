"""test_next_steps_placement.py – WI-0024: `next_step` extraction must not depend on
where `## Open Points` sits relative to `## Next Steps` in the file.

`extract_phase_from_handover()`'s inline-field regex (scripts/lib/next_steps.py:83) used
`re.search` with no anchor, so it matched the FIRST occurrence of "Next Steps" anywhere in
the document byte stream, not the first occurrence of an actual "Next Steps" heading/field.
The only thing keeping that safe was templates/HANDOVER_TEMPLATE.md placing the inbox
section below the Next Steps section (a prose note, not an enforced invariant) — WI-0002
already fixed one parser hijack of this shape for the inbox marker itself. This module pins
the anchor as the actual fix, per the work item's stated preference: it removes the ordering
constraint instead of adding a test that only guards the template's current shape.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from next_steps import extract_phase_from_handover  # noqa: E402


def write_handover(project_dir: Path, body: str) -> None:
    docs_dir = project_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "HANDOVER.md").write_text(body, encoding="utf-8")


class NextStepsPlacementTest(unittest.TestCase):
    def test_inbox_finding_text_above_the_real_section_is_not_read_as_the_next_step(self):
        """An inbox line that happens to contain the words 'Next Steps' followed by a
        '/command' reference — sitting ABOVE the real ## Next Steps section, as would
        happen if the inbox were reordered — must not hijack the extracted next step.
        """
        with self._tmp_project() as project_dir:
            write_handover(
                project_dir,
                "## Open Points (append-only inbox)\n"
                "- INBOX | 19.08.2026 | qa-tester | check Next Steps: /malicious-command reference in old doc | file:1\n"
                "\n"
                "## Next Steps\n"
                "1. /correct-command\n"
                "2. After that\n",
            )

            result = extract_phase_from_handover(str(project_dir))

            self.assertEqual(result["next_step"], "correct-command")

    def test_inline_next_steps_field_still_resolves_the_command(self):
        """The inline field form (a real field, at line start) must keep working — this
        is the form the fix must not break while closing the unanchored-match hole.
        """
        with self._tmp_project() as project_dir:
            write_handover(
                project_dir,
                "**Phase:** P3\n"
                "**Next Steps:** Fulfill requirements, then /p3-architecture\n",
            )

            result = extract_phase_from_handover(str(project_dir))

            self.assertEqual(result["next_step"], "p3-architecture")

    def _tmp_project(self):
        import shutil
        import tempfile
        from contextlib import contextmanager

        @contextmanager
        def make():
            tmp = Path(tempfile.mkdtemp(prefix="ccpr-next-steps-"))
            try:
                yield tmp
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

        return make()


if __name__ == "__main__":
    unittest.main()
