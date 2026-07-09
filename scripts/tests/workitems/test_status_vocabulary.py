"""test_status_vocabulary.py – Tests for the shared STATUS_VALUES vocabulary
(Manual/WORKITEMS.md §2 / ADR-0002).

`In Review` was added as a distinct gate between `In Progress` and `Waiting for
Approval` (two-gate P5: code review, then acceptance) -- see Manual/WORKITEMS.md §8's
status-verb mapping. Pinning both membership and position here (not just relying on
the contract suite's set-status round-trip) makes an accidental reordering or removal
fail loudly at the single source of truth, rather than only downstream in whichever
command file's prose happens to reference the wrong state name.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import STATUS_VALUES  # noqa: E402


class StatusVocabularyTest(unittest.TestCase):
    def test_in_review_is_part_of_the_vocabulary(self):
        self.assertIn("In Review", STATUS_VALUES)

    def test_in_review_sits_between_in_progress_and_waiting_for_approval(self):
        in_progress_index = STATUS_VALUES.index("In Progress")
        in_review_index = STATUS_VALUES.index("In Review")
        waiting_for_approval_index = STATUS_VALUES.index("Waiting for Approval")

        self.assertEqual(in_review_index, in_progress_index + 1)
        self.assertLess(in_review_index, waiting_for_approval_index)
