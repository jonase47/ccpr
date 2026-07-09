"""test_frontmatter.py – Unit tests for the minimal frontmatter parser/renderer.

Round-trips (render then parse) values that are adversarial for a naive line-based
YAML-subset parser: a `#` inside a quoted string, and a scalar that happens to start
with `[` without actually being a list.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import frontmatter  # noqa: E402


class FrontmatterRoundTripTest(unittest.TestCase):
    def test_round_trips_title_containing_hash(self):
        data = {"id": "WI-0001", "title": "Fix #123", "status": "Backlog"}

        text = frontmatter.render(data, "")
        parsed, _ = frontmatter.parse(text)

        self.assertEqual(parsed["title"], "Fix #123")

    def test_round_trips_title_starting_with_bracket(self):
        data = {"id": "WI-0001", "title": "[WIP] Rate limiting", "status": "Backlog"}

        text = frontmatter.render(data, "")
        parsed, _ = frontmatter.parse(text)

        self.assertEqual(parsed["title"], "[WIP] Rate limiting")

    def test_parses_genuine_inline_list(self):
        data = {"id": "WI-0001", "refs": ["ADR-0011", "ADR-0012"]}

        text = frontmatter.render(data, "")
        parsed, _ = frontmatter.parse(text)

        self.assertEqual(parsed["refs"], ["ADR-0011", "ADR-0012"])

    def test_round_trips_title_with_both_apostrophe_and_double_quote(self):
        # The old heuristic ("pick single quote if the text contains a double quote")
        # breaks here: the apostrophe in "It's" gets mistaken for the closing quote.
        # Escaping (not delimiter-picking) is the only thing that handles this.
        data = {"id": "WI-0001", "title": 'It\'s "done" #wip', "status": "Backlog"}

        text = frontmatter.render(data, "")
        parsed, _ = frontmatter.parse(text)

        self.assertEqual(parsed["title"], 'It\'s "done" #wip')

    def test_round_trips_title_containing_a_literal_backslash(self):
        data = {"id": "WI-0001", "title": 'Path is C:\\temp\\"file" #note', "status": "Backlog"}

        text = frontmatter.render(data, "")
        parsed, _ = frontmatter.parse(text)

        self.assertEqual(parsed["title"], 'Path is C:\\temp\\"file" #note')


if __name__ == "__main__":
    unittest.main()
