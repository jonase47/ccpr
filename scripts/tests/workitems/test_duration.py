"""test_duration.py – Tests for the shared duration parser (ADR-0005 claiming config).

workitems.claiming.staleAfter / heartbeatInterval need a simple, human-writable
duration format in settings.json. Deliberately not ISO 8601 durations (too heavy a
parser for a feature this narrow) -- see parse_duration_seconds's docstring.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import WorkItemError, parse_duration_seconds  # noqa: E402


class ParseDurationSecondsTest(unittest.TestCase):
    def test_bare_integer_is_seconds(self):
        self.assertEqual(parse_duration_seconds(3600), 3600.0)

    def test_numeric_string_is_seconds(self):
        self.assertEqual(parse_duration_seconds("3600"), 3600.0)

    def test_minutes_suffix(self):
        self.assertEqual(parse_duration_seconds("30m"), 1800.0)

    def test_hours_suffix(self):
        self.assertEqual(parse_duration_seconds("2h"), 7200.0)

    def test_days_suffix(self):
        self.assertEqual(parse_duration_seconds("1d"), 86400.0)

    def test_seconds_suffix(self):
        self.assertEqual(parse_duration_seconds("45s"), 45.0)

    def test_invalid_string_raises(self):
        with self.assertRaises(WorkItemError):
            parse_duration_seconds("soon")

    def test_invalid_type_raises(self):
        with self.assertRaises(WorkItemError):
            parse_duration_seconds(None)


if __name__ == "__main__":
    unittest.main()
