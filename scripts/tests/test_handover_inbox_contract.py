"""test_handover_inbox_contract.py – Pins the HANDOVER inbox contract shared by
commands/cleanup.md, commands/release-baseline.md and templates/HANDOVER_TEMPLATE.md.

These three files are natural-language prompts, not executable code: no subprocess drives
"the skill" the way test_memory_lint.py drives memory-lint.sh or test_handover_size_hook.py
drives agent-monitor.py. A test for a prompt can therefore only pin two things:

1. **The mechanical parts that are genuinely executable** — the marker regex `^- INBOX [|]`
   is a real `grep` pattern, quoted verbatim in three files. This module extracts it from
   commands/cleanup.md instead of hardcoding a second copy, so a change to the pattern in the
   prompt is what breaks the test, not a maintainer forgetting to update a duplicate.
2. **Whether the documented mechanic exists at all, in words specific enough to build a
   reference implementation from** — for WI-0006 part (b) and WI-0007, this module asserts
   that cleanup.md / release-baseline.md name the report phrase, the exclusion rules, and the
   carry-over behaviour explicitly, then runs a small Python mirror (written in this file,
   not extracted — the source is prose) over real fixtures built from the actual template and
   command files to show the mechanic is at least internally consistent.

What this does **not** prove: that an LLM executing these prompts will actually behave this
way in a live session. It proves the prompt says the right, specific things, and that a
straightforward reading of those things produces the intended split (parseable vs.
unparseable, kept vs. dropped) on the fixtures this file builds from the shipped template.
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLEANUP_PATH = REPO_ROOT / "commands" / "cleanup.md"
RELEASE_BASELINE_PATH = REPO_ROOT / "commands" / "release-baseline.md"
TEMPLATE_PATH = REPO_ROOT / "templates" / "HANDOVER_TEMPLATE.md"

# The exact phrase §1a of cleanup.md must use to report a non-marker line inside the Open
# Points section (WI-0006 part b). Pinned here so the doc-completeness checks and the mirror
# fixtures below stay in sync with the one place this string is allowed to live.
UNPARSEABLE_PHRASE = "unparseable, needs reshaping"

# The exact phrase release-baseline.md §4 must use to report the carried-over inbox count
# (WI-0007). "carried over" is deliberately loose (the surrounding wording is free to vary);
# the count placeholder and "inbox entries" are the load-bearing part.
CARRY_REPORT_SUBSTRING = "inbox entries carried over"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_marker_pattern(cleanup_text: str) -> str:
    """Pulls the inbox marker regex out of cleanup.md's own reference grep command.

    cleanup.md §1 documents the pattern as `grep -c '^- INBOX [|]' docs/HANDOVER.md` — this
    extracts the quoted pattern instead of hardcoding a second copy of it in this test file.
    The pattern is a POSIX bracket expression plus a literal anchor, which behaves identically
    in BRE, ERE and Python's `re` module, so it can be reused directly for the Python-side
    fixtures below without translation.
    """
    match = re.search(r"grep -c '([^']+)' docs/HANDOVER\.md", cleanup_text)
    assert match, (
        "commands/cleanup.md no longer contains the reference grep command "
        "\"grep -c '<pattern>' docs/HANDOVER.md\" for the inbox marker — "
        "extraction target moved or was reworded"
    )
    return match.group(1)


def extract_inbox_placement_comment(template_text: str) -> str:
    """Pulls the literal placement-comment line from the template's Open Points section.

    Used to insert fixture entries at the same place a real agent would append them, so the
    fixtures built in this file are not testing a layout nobody uses.
    """
    match = re.search(r"<!--\s*append inbox entries below this line\s*-->", template_text)
    assert match, "templates/HANDOVER_TEMPLATE.md dropped the inbox placement comment"
    return match.group(0)


def find_section(text: str, heading_prefix: str):
    """Returns the lines strictly between the first heading starting with heading_prefix and
    the next top-level '## ' heading (or EOF). Returns None if no such heading exists.

    This mirrors the section-boundary lookup cleanup.md's unparseable-line pass needs (it is
    the one place in the inbox contract that must look at the heading, not just the marker —
    see cleanup.md §1's own note that the entry *count* is deliberately heading-independent).
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(heading_prefix):
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return lines[start:end]


def find_unparseable_inbox_lines(handover_text: str, marker_pattern: str):
    """Reference mirror of the documented §1a pass: within '## Open Points', every non-blank,
    non-blockquote, non-comment line that does not match the inbox marker is unparseable.

    This function's *logic* is written here (prose cannot be executed), but its inputs
    (the heading text and the marker pattern) are the same ones the doc-completeness checks
    below require cleanup.md to name explicitly — so a doc that removes those specifics fails
    the presence checks before this mirror ever runs on a fixture.
    """
    section = find_section(handover_text, "## Open Points")
    if section is None:
        return None
    marker_re = re.compile(marker_pattern)
    unparseable = []
    for line in section:
        stripped = line.strip()
        if not stripped:
            continue
        if line.startswith(">"):
            continue
        if stripped.startswith("<!--"):
            continue
        if marker_re.match(line):
            continue
        unparseable.append(line)
    return unparseable


def assert_cleanup_documents_unparseable_reporting(cleanup_text: str):
    """Doc-completeness gate for WI-0006 part (b).

    Fails (with the exact missing piece named) unless cleanup.md's §1a explicitly documents:
    the report phrase, that blockquote lines are excluded, and that blank lines are excluded.
    This is the assertion that must be RED before the fix and GREEN after — everything else in
    this module that depends on it inherits that RED/GREEN transition.
    """
    assert UNPARSEABLE_PHRASE in cleanup_text, (
        f"commands/cleanup.md does not report unparseable Open Points lines using the phrase "
        f"{UNPARSEABLE_PHRASE!r} (WI-0006 part b not yet implemented)"
    )
    assert "blockquote" in cleanup_text.lower(), (
        "commands/cleanup.md's unparseable-line pass does not mention excluding blockquote "
        "lines — a fresh template would be reported as full of findings"
    )
    assert "blank" in cleanup_text.lower(), (
        "commands/cleanup.md's unparseable-line pass does not mention excluding blank lines"
    )


def assert_release_baseline_documents_inbox_carry(release_baseline_text: str, marker_pattern: str):
    """Doc-completeness gate for WI-0007.

    Fails (with the exact missing piece named) unless release-baseline.md §4 explicitly
    documents: reuse of the same inbox marker pattern, a verbatim carry-over instruction, and
    a loud report line for the carried count. RED before the fix, GREEN after.
    """
    assert marker_pattern in release_baseline_text, (
        "commands/release-baseline.md does not reuse cleanup.md's inbox marker pattern "
        f"({marker_pattern!r}) — the HANDOVER reset in §4 has no documented way to find "
        "untriaged inbox entries in the outgoing file (WI-0007 not yet implemented)"
    )
    assert "verbatim" in release_baseline_text.lower(), (
        "commands/release-baseline.md §4 does not say inbox entries are carried over verbatim"
    )
    assert CARRY_REPORT_SUBSTRING in release_baseline_text, (
        "commands/release-baseline.md does not report the carried inbox count with the "
        f"phrase {CARRY_REPORT_SUBSTRING!r} (WI-0007 not yet implemented)"
    )


def run_grep(pattern: str, path: Path, extended: bool = False) -> int:
    args = ["grep", "-Ec" if extended else "-c", pattern, str(path)]
    result = subprocess.run(args, capture_output=True, text=True)
    # grep exits 1 when there are zero matches — that is a valid count, not a tool failure.
    assert result.returncode in (0, 1), (
        f"grep failed unexpectedly: {result.returncode}, stderr={result.stderr!r}"
    )
    return int(result.stdout.strip())


def build_handover(open_points_lines, template_text: str, placement_comment: str) -> str:
    """Splices extra lines into a copy of the real template, right where an agent would append
    them (below the placement comment), and returns the resulting HANDOVER text."""
    if not open_points_lines:
        return template_text
    injected = placement_comment + "\n" + "\n".join(open_points_lines)
    assert placement_comment in template_text, "placement comment missing from template copy"
    return template_text.replace(placement_comment, injected, 1)


class MarkerPatternExtractionTest(unittest.TestCase):
    """Does the mechanical, always-executable half of the contract hold?

    Covers: a fresh template counts 0, N real entries count N, and BRE/ERE agree — the three
    properties cleanup.md §1 claims about its own reference grep command.
    """

    @classmethod
    def setUpClass(cls):
        cls.cleanup_text = read(CLEANUP_PATH)
        cls.template_text = read(TEMPLATE_PATH)
        cls.marker_pattern = extract_marker_pattern(cls.cleanup_text)
        cls.placement_comment = extract_inbox_placement_comment(cls.template_text)

    def write_fixture(self, tmp_path: Path, text: str) -> Path:
        fixture = tmp_path / "HANDOVER.md"
        fixture.write_text(text, encoding="utf-8")
        return fixture

    def test_fresh_template_counts_zero_entries(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.write_fixture(Path(tmp), self.template_text)
            self.assertEqual(0, run_grep(self.marker_pattern, fixture))

    def test_n_real_entries_count_n(self):
        import tempfile
        entries = [
            f"- INBOX | 0{i}.01.2026 | tester | finding number {i} | ref-{i}"
            for i in range(1, 4)
        ]
        text = build_handover(entries, self.template_text, self.placement_comment)
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.write_fixture(Path(tmp), text)
            self.assertEqual(3, run_grep(self.marker_pattern, fixture))

    def test_bre_and_ere_agree_on_a_finding_with_pipe_bracket_and_backslash(self):
        import tempfile
        tricky = (
            "- INBOX | 05.01.2026 | tester | "
            r"finding with | pipe and [bracket] and \backslash inside it"
            " | ref-tricky"
        )
        text = build_handover([tricky], self.template_text, self.placement_comment)
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.write_fixture(Path(tmp), text)
            bre_count = run_grep(self.marker_pattern, fixture, extended=False)
            ere_count = run_grep(self.marker_pattern, fixture, extended=True)
            self.assertEqual(bre_count, ere_count)
            self.assertEqual(1, bre_count)


class UnparseableInboxLineTest(unittest.TestCase):
    """WI-0006 part (b): does cleanup.md document reporting unparseable Open Points lines?"""

    @classmethod
    def setUpClass(cls):
        cls.cleanup_text = read(CLEANUP_PATH)
        cls.template_text = read(TEMPLATE_PATH)
        cls.marker_pattern = extract_marker_pattern(cls.cleanup_text)
        cls.placement_comment = extract_inbox_placement_comment(cls.template_text)

    def test_cleanup_documents_the_unparseable_line_mechanic(self):
        """RED before the fix: cleanup.md must name the report phrase and both exclusions."""
        assert_cleanup_documents_unparseable_reporting(self.cleanup_text)

    def test_prose_line_in_open_points_is_flagged_by_the_documented_mechanic(self):
        """RED before the fix (via the doc-completeness gate above), GREEN after.

        Builds a HANDOVER whose Open Points section holds one real marker entry and one
        free-prose line (the shape an unreshaped epilogue bullet produces), then runs the
        mirror mechanic and asserts exactly the prose line is flagged.
        """
        assert_cleanup_documents_unparseable_reporting(self.cleanup_text)
        prose_line = "- Note: consider revisiting the retry backoff (found while fixing WI-9999)"
        marker_line = "- INBOX | 06.01.2026 | tester | a real entry | ref-6"
        text = build_handover([marker_line, prose_line], self.template_text, self.placement_comment)
        unparseable = find_unparseable_inbox_lines(text, self.marker_pattern)
        self.assertEqual([prose_line], unparseable)

    def test_fresh_template_has_no_unparseable_lines(self):
        """Regression pin: the template's own format example lives inside a blockquote and
        must not be flagged — this is the false-positive the task calls out explicitly.
        Independent of the doc-completeness gate: it verifies this file's own exclusion rules
        against the real template, not the prose."""
        unparseable = find_unparseable_inbox_lines(self.template_text, self.marker_pattern)
        self.assertEqual([], unparseable)

    def test_missing_heading_is_not_an_error(self):
        """A HANDOVER without an '## Open Points' heading (older template) must not crash or
        produce a phantom finding — mirrors §1's own 'heading missing' branch."""
        text = "# Handover – Work State\n\n## Next Steps\n1. Do the thing.\n"
        self.assertIsNone(find_unparseable_inbox_lines(text, self.marker_pattern))


class ReleaseBaselineInboxCarryTest(unittest.TestCase):
    """WI-0007: does release-baseline.md's HANDOVER reset carry inbox entries instead of
    silently dropping them?"""

    @classmethod
    def setUpClass(cls):
        cls.cleanup_text = read(CLEANUP_PATH)
        cls.release_baseline_text = read(RELEASE_BASELINE_PATH)
        cls.template_text = read(TEMPLATE_PATH)
        cls.marker_pattern = extract_marker_pattern(cls.cleanup_text)
        cls.placement_comment = extract_inbox_placement_comment(cls.template_text)

    def test_release_baseline_documents_carrying_inbox_entries_across_the_reset(self):
        """RED before the fix: release-baseline.md §4 must reuse the marker pattern, say
        'verbatim', and report the carried count with the pinned phrase."""
        assert_release_baseline_documents_inbox_carry(self.release_baseline_text, self.marker_pattern)

    def test_reset_over_a_handover_with_two_entries_keeps_both(self):
        """RED before the fix (via the doc-completeness gate above), GREEN after.

        Mirrors the documented reset: extract every marker-matching line from the outgoing
        HANDOVER via the real grep pattern, splice them into a fresh copy of the template at
        the documented placement, and assert the marker count on the new file still equals the
        count on the old file — i.e. nothing was dropped by the reset.
        """
        assert_release_baseline_documents_inbox_carry(self.release_baseline_text, self.marker_pattern)
        import tempfile

        old_entries = [
            "- INBOX | 03.01.2026 | senior-developer | a finding from before the cut | WI-0042",
            "- INBOX | 04.01.2026 | qa-tester | another finding, still untriaged | file.py:12",
        ]
        old_text = build_handover(old_entries, self.template_text, self.placement_comment)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            old_file = tmp_path / "old_HANDOVER.md"
            old_file.write_text(old_text, encoding="utf-8")
            old_count = run_grep(self.marker_pattern, old_file)
            self.assertEqual(2, old_count, "fixture setup: expected 2 entries in the old file")

            marker_re = re.compile(self.marker_pattern)
            carried = [line for line in old_text.splitlines() if marker_re.match(line)]
            new_text = build_handover(carried, self.template_text, self.placement_comment)
            new_file = tmp_path / "new_HANDOVER.md"
            new_file.write_text(new_text, encoding="utf-8")
            new_count = run_grep(self.marker_pattern, new_file)

            self.assertEqual(old_count, new_count)
            self.assertEqual(2, new_count)


if __name__ == "__main__":
    unittest.main()
