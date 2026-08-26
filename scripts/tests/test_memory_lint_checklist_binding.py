"""test_memory_lint_checklist_binding.py -- WI-0110: pin that every check
`scripts/memory-lint.sh` defines has a matching bullet in the "Per file"
checklist chapter of `Manual/system/memory-instincts.md`, and that no bullet
in that chapter names a check the script no longer defines.

## Measured before writing anything (26.08.2026)

WI-0104 already repaired the content -- both sides agree today: 15 unique
check letters (`a b c c2 d e f g h i j k l m n`), one script comment line
each and one chapter bullet each. This test is only the guard against the
NEXT divergence; it cannot go red on its own, so its RED proof (the
`RedProof*` classes below) is constructed deliberately (G-107) rather than
observed, by mutating in-memory copies of the two texts -- the real files
are read-only for this work item and are never edited.

This test deliberately does NOT check that a bullet *describes* its check
correctly -- only that the two LETTER SETS match. That is the part a machine
can hold, and the part that failed before WI-0104.

## The extraction rule, and how it handles the four named traps

1. `c2` is not dropped -- the letter class is `[a-z][a-z0-9]?` (one
   optional trailing digit), not a bare `[a-z]`.
2. Uniqueness, not line count -- both extractors return `set[str]`, so a
   letter referenced on more than one line collapses to a single membership
   test. Measured: the script has 18 lines shaped like `# (x)` but only 15
   unique letters.
3. `# (measured ...)`-style prose parens do not match -- the pattern
   requires the character right after `(` to be `[a-z0-9]?`-terminated
   lowercase, so `measured` and `~6-8` both fail on the very first
   character check.
4. Three of those 18 lines are BACK-REFERENCES to an already-defined check,
   not openers of a new one (measured: script lines 544 `# (g)`, 664
   `# (f)`, 1290 `# (n)`). Verified against all 18 matches: every genuine
   opener is immediately preceded by a BLANK line (a check's comment block
   starts fresh after the previous check's code); every back-reference is
   immediately preceded by ANOTHER comment line (it is a later line of a
   comment paragraph that is still explaining the check whose blank-line-
   preceded opener sits above it). `extract_script_check_letters()` applies
   exactly that rule and closes the false-negative hole the work item names:
   delete check (g)'s block and leave the back-reference at line 544 in
   place, and `g` still correctly drops out of the extracted set, because
   line 544's predecessor is a comment line, not a blank one -- it was never
   counted as an opener in the first place.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "memory-lint.sh"
CHAPTER_PATH = REPO_ROOT / "Manual" / "system" / "memory-instincts.md"

_SCRIPT_CHECK_RE = re.compile(r"^[ \t]*# \(([a-z][a-z0-9]?)\)")
_CHAPTER_CHECK_RE = re.compile(r"^- \*\*\(([a-z][a-z0-9]?)\)", re.MULTILINE)


def extract_script_check_letters(text):
    """Every letter a `# (x)` comment in `text` OPENS -- see trap 4 above.

    A match only counts as an opener when the immediately preceding line is
    blank; a match preceded by another comment line is a back-reference to
    a check defined elsewhere and is skipped.
    """
    lines = text.split("\n")
    letters = set()
    for i, line in enumerate(lines):
        match = _SCRIPT_CHECK_RE.match(line)
        if not match:
            continue
        previous_line = lines[i - 1] if i > 0 else ""
        if previous_line.strip() != "":
            continue
        letters.add(match.group(1))
    return letters


def extract_chapter_check_letters(text):
    """Every letter a `- **(x)` bullet defines in the checklist chapter."""
    return set(_CHAPTER_CHECK_RE.findall(text))


def remove_chapter_bullet(text, letter):
    """Deletes the full bullet (incl. its indented continuation lines) for
    `letter`, on an in-memory copy -- used only by the RED-proof tests."""
    pattern = re.compile(
        rf"^- \*\*\({re.escape(letter)}\).*?(?=\n- \*\*\(|\n\n|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    mutated, count = pattern.subn("", text)
    if count != 1:
        raise AssertionError(
            f"expected exactly one chapter bullet for ({letter}), found {count}"
        )
    return mutated


class ChecklistBindingTest(unittest.TestCase):
    """The real assertion: script checks and chapter bullets name the same
    set of letters, in both directions."""

    def test_every_script_check_has_a_matching_chapter_bullet_and_no_stale_bullets_remain(self):
        script_letters = extract_script_check_letters(
            SCRIPT_PATH.read_text(encoding="utf-8")
        )
        chapter_letters = extract_chapter_check_letters(
            CHAPTER_PATH.read_text(encoding="utf-8")
        )

        undocumented = script_letters - chapter_letters
        stale = chapter_letters - script_letters

        self.assertEqual(
            set(), undocumented,
            f"scripts/memory-lint.sh defines check(s) {sorted(undocumented)} "
            "with no matching bullet in Manual/system/memory-instincts.md",
        )
        self.assertEqual(
            set(), stale,
            f"Manual/system/memory-instincts.md documents check(s) {sorted(stale)} "
            "that scripts/memory-lint.sh no longer defines",
        )


class RedProofRemovingAChapterBulletTest(unittest.TestCase):
    """RED proof, direction 1 (undocumented script check): deleting a
    documented bullet from an in-memory copy of the chapter must surface
    that exact letter as undocumented."""

    def test_removing_the_g_bullet_reports_g_as_undocumented(self):
        chapter_text = CHAPTER_PATH.read_text(encoding="utf-8")
        mutated_chapter = remove_chapter_bullet(chapter_text, "g")
        self.assertNotIn("**(g)", mutated_chapter)

        script_letters = extract_script_check_letters(
            SCRIPT_PATH.read_text(encoding="utf-8")
        )
        chapter_letters = extract_chapter_check_letters(mutated_chapter)

        self.assertEqual({"g"}, script_letters - chapter_letters)


class RedProofAddingAnUndefinedChapterBulletTest(unittest.TestCase):
    """RED proof, direction 2 (stale chapter bullet): adding a bullet for a
    letter the script does not define must surface that exact letter as
    stale."""

    def test_adding_a_z_bullet_reports_z_as_stale(self):
        chapter_text = CHAPTER_PATH.read_text(encoding="utf-8")
        mutated_chapter = chapter_text.replace(
            "Nothing is deliberately omitted:",
            "- **(z) Fake check** -- does not exist in the script.\n\n"
            "Nothing is deliberately omitted:",
            1,
        )
        self.assertIn("**(z)", mutated_chapter)
        self.assertNotEqual(chapter_text, mutated_chapter)

        script_letters = extract_script_check_letters(
            SCRIPT_PATH.read_text(encoding="utf-8")
        )
        chapter_letters = extract_chapter_check_letters(mutated_chapter)

        self.assertEqual({"z"}, chapter_letters - script_letters)


class RedProofRelabelingAScriptOpenerTest(unittest.TestCase):
    """RED proof, structural mutation (G-107/G-109): re-lettering an
    existing opener -- not deleting it -- must surface BOTH a missing letter
    and an unexpected one. This is the proof that the extraction tracks
    check IDENTITY, not merely whether some `# (x)`-shaped comment survives
    at that spot; a presence-only mutation (deletion) would not distinguish
    the two."""

    def test_relabeling_the_e_opener_to_e2_reports_both_a_missing_e_and_an_unexpected_e2(self):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        original_opener = "    # (e) last_updated — its FORM first, then its age."
        relabeled_opener = "    # (e2) last_updated — its FORM first, then its age."
        self.assertIn(original_opener, script_text)

        mutated_script = script_text.replace(original_opener, relabeled_opener, 1)
        self.assertNotEqual(script_text, mutated_script)

        script_letters = extract_script_check_letters(mutated_script)
        chapter_letters = extract_chapter_check_letters(
            CHAPTER_PATH.read_text(encoding="utf-8")
        )

        self.assertIn("e", chapter_letters - script_letters)
        self.assertIn("e2", script_letters - chapter_letters)


if __name__ == "__main__":
    unittest.main()
