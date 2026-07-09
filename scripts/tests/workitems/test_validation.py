"""test_validation.py – Direct unit tests for the shared, backend-agnostic guard
functions in workitems/__init__.py (validate_tag, validate_item_id) that both
backends rely on before ever touching storage.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import WorkItemError, validate_item_id, validate_tag  # noqa: E402


class ValidateTagTrailingNewlineTest(unittest.TestCase):
    """A bare `$` in a compiled regex (without re.MULTILINE) matches just before a
    trailing "\\n", not only at the true end of the string. `validate_tag`'s charset
    check (`_TAG_PATTERN`) previously let a tag with an embedded trailing newline
    through unrejected, which then corrupted the frontmatter writer's inline-list
    rendering across two physical lines on the next parse (`tags: [security\\n,
    other]`) -- a `parse()` afterwards returns `tags` as the string `"[security"`
    instead of a list, silently losing every other entry (review follow-up,
    09.07.2026)."""

    def test_rejects_a_tag_with_a_trailing_newline(self):
        with self.assertRaises(WorkItemError):
            validate_tag("security\n")


class ValidateItemIdTrailingNewlineTest(unittest.TestCase):
    """Same `$`-vs-`\\n` trap as validate_tag, for `validate_item_id` (used both for
    an item's own id and for a link's target id)."""

    def test_rejects_an_id_with_a_trailing_newline(self):
        with self.assertRaises(WorkItemError):
            validate_item_id("WI-0001\n")
