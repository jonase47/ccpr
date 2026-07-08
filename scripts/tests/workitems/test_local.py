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

from .contract import WorkItemsContractTestCase

# Raw fixture template for local-only white-box tests that need to write a Markdown
# file directly (bypassing backend.create()) to set up a specific starting shape.
ITEM_TEMPLATE = """---
id: {id}
title: {title}
status: {status}
type: feat
owner: {owner}
refs: [ADR-0011]
tags: [security]
created: 2026-07-08
---

{description}

## Acceptance Criteria
- Criterion one.
- Criterion two.

## Result
<!-- append-result writes PR/commit links here -->
"""


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


class LocalBackendAppendResultWithoutSectionTest(unittest.TestCase):
    """Every ITEM_TEMPLATE fixture already has a `## Result` heading, so the
    create-the-section branch of _append_to_result_section() was never exercised.
    This fixture deliberately omits it."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-noresult-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        (Path(self.tmp_dir) / "WI-0001.md").write_text(
            "---\n"
            "id: WI-0001\n"
            "title: No result section yet\n"
            "status: Backlog\n"
            "---\n"
            "\n"
            "Description without an existing Result heading.\n",
            encoding="utf-8",
        )
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def test_append_result_creates_missing_section(self):
        item = self.backend.append_result("WI-0001", "https://example.org/pr/1")

        self.assertEqual(item["result-link"], ["https://example.org/pr/1"])
        self.assertEqual(item["description"], "Description without an existing Result heading.")

    def test_second_append_result_adds_to_the_newly_created_section(self):
        self.backend.append_result("WI-0001", "https://example.org/pr/1")

        item = self.backend.append_result("WI-0001", "https://example.org/pr/2")

        self.assertEqual(
            item["result-link"],
            ["https://example.org/pr/1", "https://example.org/pr/2"],
        )


class LocalBackendClaimingTest(unittest.TestCase):
    """Claiming is mandatory for remote backends and a genuine no-op for `local`
    (ADR-0002 §6 / ADR-0005): local has nothing to lock, no runner concept, no
    heartbeat -- these tests confirm the no-op holds, not just "doesn't error"."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-claiming-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def test_items_always_expose_runner_and_heartbeat_as_none(self):
        item = self.backend.create(title="First")

        self.assertIsNone(item["runner"])
        self.assertIsNone(item["heartbeat"])

    def test_claim_with_runner_is_accepted_but_ignored(self):
        item = self.backend.create(title="First")

        claimed = self.backend.claim(item["id"], owner="alice", runner="agent-1")

        self.assertEqual(claimed["owner"], "alice")
        self.assertIsNone(claimed["runner"])
        self.assertIsNone(claimed["heartbeat"])

    def test_heartbeat_is_a_no_op(self):
        item = self.backend.create(title="First")

        result = self.backend.heartbeat(item["id"], runner="agent-1")

        self.assertIsNone(result["runner"])
        self.assertIsNone(result["heartbeat"])
        self.assertEqual(result["status"], "Backlog")

    def test_heartbeat_on_unknown_id_still_raises(self):
        with self.assertRaises(Exception):
            self.backend.heartbeat("WI-9999", runner="agent-1")


class LocalBackendCreateTest(unittest.TestCase):
    """local-specific create() behaviour beyond the backend-neutral contract suite:
    monotonic WI-NNNN id assignment and the body shape written to disk."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-create-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def test_first_item_in_an_empty_store_is_wi_0001(self):
        item = self.backend.create(title="First")

        self.assertEqual(item["id"], "WI-0001")

    def test_ids_are_monotonic_and_zero_padded(self):
        self.backend.create(title="First")
        self.backend.create(title="Second")
        third = self.backend.create(title="Third")

        self.assertEqual(third["id"], "WI-0003")

    def test_next_id_continues_after_the_highest_existing_file_not_the_count(self):
        # A gap (WI-0001 missing, e.g. archived/deleted) must not cause a collision.
        (Path(self.tmp_dir) / "WI-0005.md").write_text(
            ITEM_TEMPLATE.format(
                id="WI-0005", title="Existing", status="Backlog", owner="",
                description="Description.",
            ),
            encoding="utf-8",
        )

        item = self.backend.create(title="Next")

        self.assertEqual(item["id"], "WI-0006")

    def test_created_item_has_empty_acceptance_criteria_and_result_sections(self):
        item = self.backend.create(title="First")

        path = Path(self.tmp_dir) / f"{item['id']}.md"
        text = path.read_text(encoding="utf-8")

        self.assertIn("## Acceptance Criteria", text)
        self.assertIn("## Result", text)
        self.assertEqual(item["result-link"], [])


if __name__ == "__main__":
    unittest.main()
