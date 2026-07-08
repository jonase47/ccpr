"""test_local.py – Wires the `local` backend into the shared contract suite (ADR-0002)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import local  # noqa: E402

from .contract import WorkItemsContractTestCase


class LocalBackendContractTest(WorkItemsContractTestCase, unittest.TestCase):
    def create_backend(self, workitems_dir):
        return local.create({"workitems_dir": workitems_dir})


if __name__ == "__main__":
    unittest.main()
