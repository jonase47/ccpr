"""test_handover_epilogue_bullet.py – WI-0033: pins the disambiguated Handover-Epilogue
"Open decisions" bullet across commands/*.md.

91 command files carried a bare "- Open points" bullet in their "### Handover Epilogue"
(or "### Handover Epilog") block, instructing the command to record open points in
docs/HANDOVER.md without saying which of the two destinations WI-0002 introduced it means:
the "## Open Decisions" table (PO decisions belonging to THIS command's own assignment) or
the "## Open Points" append-only inbox (findings made OUTSIDE the current assignment, per
templates/HANDOVER_TEMPLATE.md). One further file (p5-review-sprint.md) carried a suffixed
sibling, "- Open points (esp. any CRITICAL/HIGH carried into the gate)". A further 12 files
(gate-p7*, p7-*, p8-*) carried the identical ambiguity in the identical block shape under a
different word, "- Open items" — found while measuring the first 92, initially left as a
"separate finding" and folded into the same fix on review: the defect is the missing
destination, not the literal string "Open points", and the block position/shape (preceded by
"- What was created/changed", followed by "- Next Steps (...)") is byte-for-byte identical
across all 104 files. WI-0033 reworded all 104 to name the destination explicitly.

This module asserts the POSITIVE form — that every Handover-Epilogue bullet naming "Open
..." either is the disambiguated wording or is the one, named, genuinely unrelated exception
below — rather than merely the absence of the old string. A negative-only check ("the old
string does not occur") would pass vacuously on a file that never had the concept at all, and
would not catch a NEW command file added later that reintroduces an ambiguous bare "- Open
points" or "- Open items" bullet under its own Handover-Epilogue heading: that new bullet
starts with "- Open" but not with the disambiguated prefix and is not the specialize.md
exception, so it fails the "resolved or exempted" assertion below. There is deliberately no
allowlist here: an allowlist for files carrying the same defect the test exists to prevent
would read, to the next person, as "these were considered and excused" — which was true of
none of them; the earlier draft of this test allowlisted the 12 "- Open items" files for
exactly that reason and was corrected once the sweep was extended to cover them too.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "commands"

EPILOGUE_HEADING_RE = re.compile(r"^### Handover Epilog(ue)?$")

DISAMBIGUATED_PREFIX = "- Open decisions → the `## Open Decisions` table"
DISAMBIGUATED_BARE = (
    "- Open decisions → the `## Open Decisions` table; a finding outside this "
    "command's scope goes to the `## Open Points` inbox instead"
)
DISAMBIGUATED_SUFFIXED = (
    "- Open decisions → the `## Open Decisions` table (esp. any CRITICAL/HIGH "
    "carried into the gate); a finding outside this command's scope goes to the "
    "`## Open Points` inbox instead"
)

# specialize.md's Handover-Epilogue names a genuinely different concept: unresolved
# "⚠ verify" markers left by a specialization pass, not an open point or an open decision
# about the command's own assignment, and there is no second "## Open ..." destination for
# it to disambiguate between — so it is exempted by its literal line, not allowlisted as an
# instance of the same defect.
SPECIALIZE_VERIFY_BULLET = "- Open `⚠ verify` items"


def extract_epilogue_bullets(text: str):
    """Returns the '- '-prefixed lines inside the first '### Handover Epilog(ue)' block, up
    to the next '## ' heading. Returns None if the file has no such heading."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if EPILOGUE_HEADING_RE.match(line):
            bullets = []
            for later in lines[i + 1 :]:
                if later.startswith("## "):
                    break
                if later.startswith("- "):
                    bullets.append(later)
            return bullets
    return None


def is_resolved_or_exempted(filename: str, bullet: str) -> bool:
    if bullet.startswith(DISAMBIGUATED_PREFIX):
        return True
    if filename == "specialize.md" and bullet == SPECIALIZE_VERIFY_BULLET:
        return True
    return False


class EpilogueOpenBulletTest(unittest.TestCase):
    def test_every_epilogue_open_bullet_is_disambiguated_or_exempted(self):
        """Positive-form pin: every 'Open ...' bullet in a Handover-Epilogue block must
        either be the disambiguated wording or the one named, unrelated exception above.
        Catches reintroduction of an ambiguous bare "- Open points" or "- Open items" bullet
        in ANY commands/*.md file, including one added after this test was written.
        """
        violations = []
        for path in sorted(COMMANDS_DIR.glob("*.md")):
            bullets = extract_epilogue_bullets(path.read_text(encoding="utf-8"))
            if bullets is None:
                continue
            for bullet in bullets:
                if not bullet.startswith("- Open"):
                    continue
                if not is_resolved_or_exempted(path.name, bullet):
                    violations.append(f"{path.name}: {bullet!r}")
        self.assertEqual(
            [],
            violations,
            "Handover-Epilogue bullet(s) using an unresolved 'Open ...' phrasing "
            "(neither the disambiguated wording nor the specialize.md exception): "
            + "; ".join(violations),
        )

    def test_104_files_carry_the_disambiguated_wording(self):
        """Regression pin on WI-0033's full measured scope: 91 bare (original) + 12 bare
        (former "Open items" files, folded into the same fix) + 1 suffixed = 104."""
        bare_count = 0
        suffixed_count = 0
        for path in COMMANDS_DIR.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            if DISAMBIGUATED_SUFFIXED in text:
                suffixed_count += 1
            elif DISAMBIGUATED_BARE in text:
                bare_count += 1
        self.assertEqual(103, bare_count)
        self.assertEqual(1, suffixed_count)


if __name__ == "__main__":
    unittest.main()
