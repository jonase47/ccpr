"""test_local.py – Wires the `local` backend into the shared contract suite (ADR-0002).

Also carries `local`-specific white-box tests that don't belong in the
backend-agnostic contract suite (e.g. the .tmp-file write-failure cleanup below,
which depends on local's own atomic-write implementation detail).
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import local  # noqa: E402

from .contract import ITEM_TEMPLATE, WorkItemsContractTestCase


class LocalBackendContractTest(WorkItemsContractTestCase, unittest.TestCase):
    def create_backend(self, workitems_dir):
        return local.create({"workitems_dir": workitems_dir})


class LocalBackendWriteFailureTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-writefail-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        (Path(self.tmp_dir) / "WI-0001.md").write_text(
            ITEM_TEMPLATE.format(
                id="WI-0001", title="Untitled", status="Backlog", owner="",
                description="Description.",
            ),
            encoding="utf-8",
        )
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def test_write_failure_does_not_leave_tmp_file_behind(self):
        with mock.patch("workitems.local.Path.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.backend.claim("WI-0001", owner="alice")

        leftover_tmp_files = list(Path(self.tmp_dir).glob("*.tmp"))
        self.assertEqual(leftover_tmp_files, [])


if __name__ == "__main__":
    unittest.main()
