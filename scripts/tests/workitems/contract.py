"""contract.py – Reusable contract test suite for CCPR work-item backends (ADR-0002).

`local` is the reference implementation *and* the contract test fixture (ADR-0002 §9):
any backend that implements the five-operation contract (list/get/claim/set-status/
append-result) can be validated against this suite by subclassing
`WorkItemsContractTestCase` and overriding `create_backend()`. The backend under test
is a parameter, not hardcoded — see test_local.py for the `local` wiring; a future
`youtrack` backend adds its own subclass (e.g. test_youtrack.py) against a sandbox
project instead of a temp directory.
"""

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
    instance rooted at the given temp directory.
    """

    def create_backend(self, workitems_dir):
        raise NotImplementedError("Subclasses must return a backend instance.")

    def write_item(self, item_id, title="Untitled", status="Backlog", owner="",
                   description="Description."):
        path = Path(self.tmp_dir) / f"{item_id}.md"
        path.write_text(
            ITEM_TEMPLATE.format(
                id=item_id, title=title, status=status, owner=owner,
                description=description,
            ),
            encoding="utf-8",
        )

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = self.create_backend(self.tmp_dir)

    # --- list ---

    def test_list_returns_all_items(self):
        self.write_item("WI-0001", title="First")
        self.write_item("WI-0002", title="Second")

        items = self.backend.list()

        self.assertEqual({item["id"] for item in items}, {"WI-0001", "WI-0002"})

    def test_list_on_empty_store_returns_empty_list(self):
        self.assertEqual(self.backend.list(), [])

    def test_list_filters_by_status(self):
        self.write_item("WI-0001", status="Backlog")
        self.write_item("WI-0002", status="Done")

        items = self.backend.list(status="Done")

        self.assertEqual([item["id"] for item in items], ["WI-0002"])

    def test_list_filters_by_owner(self):
        self.write_item("WI-0001", owner="alice")
        self.write_item("WI-0002", owner="bob")

        items = self.backend.list(owner="bob")

        self.assertEqual([item["id"] for item in items], ["WI-0002"])

    # --- get ---

    def test_get_returns_full_item(self):
        self.write_item(
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
        self.write_item("WI-0001", owner="")

        item = self.backend.claim("WI-0001", owner="alice")

        self.assertEqual(item["owner"], "alice")
        self.assertEqual(self.backend.get("WI-0001")["owner"], "alice")

    def test_claim_without_owner_leaves_existing_owner_unchanged(self):
        self.write_item("WI-0001", owner="alice")

        item = self.backend.claim("WI-0001")

        self.assertEqual(item["owner"], "alice")
