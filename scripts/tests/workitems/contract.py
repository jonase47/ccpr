"""contract.py – Reusable contract test suite for CCPR work-item backends (ADR-0002).

`local` is the reference implementation *and* the contract test fixture (ADR-0002 §9):
any backend that implements the five-operation contract (list/get/claim/set-status/
append-result) can be validated against this suite by subclassing
`WorkItemsContractTestCase` and overriding `create_backend()`. The backend under test
is a parameter, not hardcoded — see test_local.py for the `local` wiring; a future
`youtrack` backend adds its own subclass (e.g. test_youtrack.py) against a sandbox
project instead of a temp directory.
"""

import os
import shutil
import tempfile
from pathlib import Path

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


class WorkItemsContractTestCase:
    """Mixin exercising the five-operation contract against a backend.

    Deliberately NOT a `unittest.TestCase` subclass: a concrete backend test combines
    this mixin with `unittest.TestCase` (see test_local.py). Extending TestCase here
    directly would make unittest's discovery pick up this abstract base as a runnable
    (and failing) test case wherever it is imported.

    Subclasses must override `create_backend(workitems_dir)` to return a backend
    instance rooted at the given temp directory, and `create_item(...)` to seed a
    fixture item the backend-under-test can read back.
    """

    def create_backend(self, workitems_dir):
        raise NotImplementedError("Subclasses must return a backend instance.")

    def create_item(self, item_id, title="Untitled", status="Backlog", owner="",
                     description="Description."):
        """Create a fixture item the backend-under-test can read back.

        No default implementation: for `local` this writes a Markdown file directly
        into the temp workitems dir (see test_local.py); a future `youtrack` backend
        would instead create an issue via its API or seed a sandbox project. Raising
        here — rather than defaulting to a filesystem write — means a new backend
        can't silently inherit a fixture path the real backend never reads.
        """
        raise NotImplementedError("Subclasses must implement create_item().")

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = self.create_backend(self.tmp_dir)

    # --- list ---

    def test_list_returns_all_items(self):
        self.create_item("WI-0001", title="First")
        self.create_item("WI-0002", title="Second")

        items = self.backend.list()

        self.assertEqual({item["id"] for item in items}, {"WI-0001", "WI-0002"})

    def test_list_on_empty_store_returns_empty_list(self):
        self.assertEqual(self.backend.list(), [])

    def test_list_filters_by_status(self):
        self.create_item("WI-0001", status="Backlog")
        self.create_item("WI-0002", status="Done")

        items = self.backend.list(status="Done")

        self.assertEqual([item["id"] for item in items], ["WI-0002"])

    def test_list_filters_by_owner(self):
        self.create_item("WI-0001", owner="alice")
        self.create_item("WI-0002", owner="bob")

        items = self.backend.list(owner="bob")

        self.assertEqual([item["id"] for item in items], ["WI-0002"])

    # --- get ---

    def test_get_returns_full_item(self):
        self.create_item(
            "WI-0001", title="Rate limiting", status="In Progress",
            owner="alice", description="Add a limiter.",
        )

        item = self.backend.get("WI-0001")

        self.assertEqual(item["id"], "WI-0001")
        self.assertEqual(item["title"], "Rate limiting")
        self.assertEqual(item["status"], "In Progress")
        self.assertEqual(item["owner"], "alice")
        self.assertEqual(item["description"], "Add a limiter.")

    def test_get_unknown_id_raises(self):
        with self.assertRaises(Exception):
            self.backend.get("WI-9999")

    # --- claim ---

    def test_claim_sets_owner(self):
        self.create_item("WI-0001", owner="")

        item = self.backend.claim("WI-0001", owner="alice")

        self.assertEqual(item["owner"], "alice")
        self.assertEqual(self.backend.get("WI-0001")["owner"], "alice")

    def test_claim_without_owner_leaves_existing_owner_unchanged(self):
        self.create_item("WI-0001", owner="alice")

        item = self.backend.claim("WI-0001")

        self.assertEqual(item["owner"], "alice")

    # --- set-status ---

    def test_set_status_updates_status(self):
        self.create_item("WI-0001", status="Backlog")

        item = self.backend.set_status("WI-0001", "In Progress")

        self.assertEqual(item["status"], "In Progress")
        self.assertEqual(self.backend.get("WI-0001")["status"], "In Progress")

    def test_set_status_rejects_unknown_status(self):
        self.create_item("WI-0001", status="Backlog")

        with self.assertRaises(Exception):
            self.backend.set_status("WI-0001", "Not-A-Status")
        self.assertEqual(self.backend.get("WI-0001")["status"], "Backlog")

    def test_set_status_accepts_every_vocabulary_value(self):
        self.create_item("WI-0001", status="Backlog")

        for status in (
            "Backlog", "Ready", "In Progress", "Parked",
            "Waiting for Approval", "Done", "Blocked", "Cancelled",
        ):
            item = self.backend.set_status("WI-0001", status)
            self.assertEqual(item["status"], status)

    # --- append-result ---

    def test_append_result_adds_a_reference(self):
        self.create_item("WI-0001")

        item = self.backend.append_result("WI-0001", "https://example.org/pr/1")

        self.assertIn("https://example.org/pr/1", item["result-link"])
        self.assertIn("https://example.org/pr/1", self.backend.get("WI-0001")["result-link"])

    def test_append_result_twice_keeps_both_references_in_order(self):
        self.create_item("WI-0001")

        self.backend.append_result("WI-0001", "https://example.org/pr/1")
        item = self.backend.append_result("WI-0001", "https://example.org/pr/2")

        self.assertEqual(
            item["result-link"],
            ["https://example.org/pr/1", "https://example.org/pr/2"],
        )

    def test_append_result_does_not_touch_other_sections(self):
        self.create_item("WI-0001", description="Original description.")

        item = self.backend.append_result("WI-0001", "https://example.org/pr/1")

        self.assertEqual(item["description"], "Original description.")

    # --- id validation / path traversal ---
    #
    # Ids may end up in filesystem paths (local) today and in `ticket/<id>` branch
    # names (ADR-0005) tomorrow — every backend must reject anything that is not a
    # bare identifier, not just `local`.

    def test_rejects_ids_with_path_separators_or_dots(self):
        for malicious_id in ("../../x", "/etc/x", "a/b", "a.md"):
            with self.subTest(malicious_id=malicious_id):
                with self.assertRaises(Exception):
                    self.backend.get(malicious_id)
                with self.assertRaises(Exception):
                    self.backend.set_status(malicious_id, "Done")
                with self.assertRaises(Exception):
                    self.backend.append_result(malicious_id, "ref")

    def test_path_traversal_id_cannot_read_or_write_outside_workitems_dir(self):
        canary_dir = tempfile.mkdtemp(prefix="ccpr-workitems-canary-")
        self.addCleanup(shutil.rmtree, canary_dir, ignore_errors=True)
        canary_path = Path(canary_dir) / "canary.md"
        canary_path.write_text("original", encoding="utf-8")

        # A relative id that walks out of the workitems dir into the canary dir.
        relative_id = f"{os.path.relpath(canary_dir, self.tmp_dir)}/canary"

        with self.assertRaises(Exception):
            self.backend.get(relative_id)
        with self.assertRaises(Exception):
            self.backend.append_result(relative_id, "https://example.org/pwned")

        self.assertEqual(canary_path.read_text(encoding="utf-8"), "original")
