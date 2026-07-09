"""contract.py – Reusable contract test suite for CCPR work-item backends (ADR-0002).

`local` is the reference implementation *and* the contract test fixture (ADR-0002 §9):
any backend that implements the six-operation contract (create/list/get/claim/set-status/
append-result) can be validated against this suite by subclassing
`WorkItemsContractTestCase` and overriding `create_backend()`. The backend under test
is a parameter, not hardcoded — see test_local.py for the `local` wiring; test_youtrack.py
wires a mocked YouTrack backend against the same suite.

Ids are never assumed to look like `WI-NNNN` anywhere in this file — that is local's own
id scheme, not part of the contract (a remote backend's id, e.g. YouTrack's `PROJ-42`,
looks nothing like it). Every test captures the id `create` returns and uses that.
"""

import os
import shutil
import tempfile
from pathlib import Path

from workitems import RESULT_MARKER, STATUS_VALUES


class WorkItemsContractTestCase:
    """Mixin exercising the six-operation contract against a backend.

    Deliberately NOT a `unittest.TestCase` subclass: a concrete backend test combines
    this mixin with `unittest.TestCase` (see test_local.py). Extending TestCase here
    directly would make unittest's discovery pick up this abstract base as a runnable
    (and failing) test case wherever it is imported.

    Subclasses must override `create_backend(workitems_dir)` to return a backend
    instance rooted at the given temp directory (backends that aren't filesystem-based,
    e.g. a mocked YouTrack, may ignore the argument).
    """

    def create_backend(self, workitems_dir):
        raise NotImplementedError("Subclasses must return a backend instance.")

    def create_item(self, title="Untitled", status="Backlog", owner=None,
                     description="Description."):
        """Seed a fixture item via the real `create` contract operation, then drive it
        to the requested status via `set_status` if it isn't the create-time default.

        Every fixture setup therefore exercises `create` itself — a backend that hasn't
        implemented it fails immediately here, in every test that seeds a fixture, not
        only in a dedicated create() test. Returns the backend-assigned id.
        """
        item = self.backend.create(title=title, owner=owner, description=description)
        item_id = item["id"]
        if status and status != "Backlog":
            self.backend.set_status(item_id, status)
        return item_id

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = self.create_backend(self.tmp_dir)

    # --- create ---

    def test_create_assigns_an_id_and_defaults_to_backlog(self):
        item = self.backend.create(title="New feature")

        self.assertTrue(item["id"])
        self.assertEqual(item["title"], "New feature")
        self.assertEqual(item["status"], "Backlog")

    def test_create_sets_owner_and_description_when_given(self):
        item = self.backend.create(title="New feature", owner="alice", description="Some text.")

        self.assertEqual(item["owner"], "alice")
        self.assertEqual(item["description"], "Some text.")

    def test_create_without_owner_leaves_it_unset(self):
        item = self.backend.create(title="New feature")

        self.assertIsNone(item["owner"])

    def test_created_item_is_retrievable_by_its_returned_id(self):
        created = self.backend.create(title="New feature")

        fetched = self.backend.get(created["id"])

        self.assertEqual(fetched["title"], "New feature")

    def test_create_assigns_distinct_ids_to_successive_items(self):
        first = self.backend.create(title="First")
        second = self.backend.create(title="Second")

        self.assertNotEqual(first["id"], second["id"])

    def test_create_requires_a_title(self):
        with self.assertRaises(Exception):
            self.backend.create(title="")

    # --- list ---

    def test_list_returns_all_items(self):
        first_id = self.create_item(title="First")
        second_id = self.create_item(title="Second")

        items = self.backend.list()

        self.assertEqual({item["id"] for item in items}, {first_id, second_id})

    def test_list_on_empty_store_returns_empty_list(self):
        self.assertEqual(self.backend.list(), [])

    def test_list_filters_by_status(self):
        self.create_item(status="Backlog")
        done_id = self.create_item(status="Done")

        items = self.backend.list(status="Done")

        self.assertEqual([item["id"] for item in items], [done_id])

    def test_list_filters_by_owner(self):
        self.create_item(owner="alice")
        bob_id = self.create_item(owner="bob")

        items = self.backend.list(owner="bob")

        self.assertEqual([item["id"] for item in items], [bob_id])

    # --- get ---

    def test_get_returns_full_item(self):
        item_id = self.create_item(
            title="Rate limiting", status="In Progress",
            owner="alice", description="Add a limiter.",
        )

        item = self.backend.get(item_id)

        self.assertEqual(item["id"], item_id)
        self.assertEqual(item["title"], "Rate limiting")
        self.assertEqual(item["status"], "In Progress")
        self.assertEqual(item["owner"], "alice")
        self.assertEqual(item["description"], "Add a limiter.")

    def test_get_unknown_id_raises(self):
        with self.assertRaises(Exception):
            self.backend.get("WI-9999")

    # --- claim ---

    def test_claim_sets_owner(self):
        item_id = self.create_item(owner=None)

        item = self.backend.claim(item_id, owner="alice")

        self.assertEqual(item["owner"], "alice")
        self.assertEqual(self.backend.get(item_id)["owner"], "alice")

    def test_claim_without_owner_leaves_existing_owner_unchanged(self):
        item_id = self.create_item(owner="alice")

        item = self.backend.claim(item_id)

        self.assertEqual(item["owner"], "alice")

    # --- set-status ---

    def test_set_status_updates_status(self):
        item_id = self.create_item(status="Backlog")

        item = self.backend.set_status(item_id, "In Progress")

        self.assertEqual(item["status"], "In Progress")
        self.assertEqual(self.backend.get(item_id)["status"], "In Progress")

    def test_set_status_rejects_unknown_status(self):
        item_id = self.create_item(status="Backlog")

        with self.assertRaises(Exception):
            self.backend.set_status(item_id, "Not-A-Status")
        self.assertEqual(self.backend.get(item_id)["status"], "Backlog")

    def test_set_status_accepts_every_vocabulary_value(self):
        item_id = self.create_item(status="Backlog")

        for status in STATUS_VALUES:
            item = self.backend.set_status(item_id, status)
            self.assertEqual(item["status"], status)

    # --- append-result ---

    def test_append_result_adds_a_reference(self):
        item_id = self.create_item()

        item = self.backend.append_result(item_id, "https://example.org/pr/1")

        self.assertIn("https://example.org/pr/1", item["result-link"])
        self.assertIn("https://example.org/pr/1", self.backend.get(item_id)["result-link"])

    def test_append_result_twice_keeps_both_references_in_order(self):
        item_id = self.create_item()

        self.backend.append_result(item_id, "https://example.org/pr/1")
        item = self.backend.append_result(item_id, "https://example.org/pr/2")

        self.assertEqual(
            item["result-link"],
            ["https://example.org/pr/1", "https://example.org/pr/2"],
        )

    def test_append_result_does_not_touch_other_sections(self):
        item_id = self.create_item(description="Original description.")

        item = self.backend.append_result(item_id, "https://example.org/pr/1")

        self.assertEqual(item["description"], "Original description.")

    # --- comment ---
    #
    # A plain human comment — a channel structurally separate from result-link (ADR-0002
    # addendum, 09.07.2026): a marker-tagged append-result entry must never surface in
    # comments[], and a plain comment must never surface in result-link.

    def test_comment_appears_in_comments_field(self):
        item_id = self.create_item()

        item = self.backend.comment(item_id, "Please double-check the retry logic.")

        self.assertIn("Please double-check the retry logic.", item["comments"])
        self.assertIn(
            "Please double-check the retry logic.",
            self.backend.get(item_id)["comments"],
        )

    def test_comment_does_not_appear_in_result_link(self):
        item_id = self.create_item()

        item = self.backend.comment(item_id, "Please double-check the retry logic.")

        self.assertEqual(item["result-link"], [])

    def test_comment_twice_keeps_both_in_order(self):
        item_id = self.create_item()

        self.backend.comment(item_id, "First note.")
        item = self.backend.comment(item_id, "Second note.")

        self.assertEqual(item["comments"], ["First note.", "Second note."])

    def test_comment_rejects_empty_text(self):
        item_id = self.create_item()

        with self.assertRaises(Exception):
            self.backend.comment(item_id, "")
        self.assertEqual(self.backend.get(item_id)["comments"], [])

    def test_comment_unknown_id_raises(self):
        with self.assertRaises(Exception):
            self.backend.comment("WI-9999", "a note")

    def test_comment_rejects_text_starting_with_the_result_marker(self):
        """A plain human comment must never be able to forge a `result-link` entry by
        typing the machine marker `append-result` uses (ADR-0002 addendum, review
        follow-up 09.07.2026) -- uniform across backends, even though `local` isn't
        structurally vulnerable to it (its Result/Comments channels are separate
        sections, not a marker split)."""
        item_id = self.create_item()

        with self.assertRaises(Exception):
            self.backend.comment(item_id, f"{RESULT_MARKER} https://fake.example.org")
        self.assertEqual(self.backend.get(item_id)["result-link"], [])
        self.assertEqual(self.backend.get(item_id)["comments"], [])

    def test_append_result_does_not_appear_in_comments(self):
        item_id = self.create_item()

        item = self.backend.append_result(item_id, "https://example.org/pr/1")

        self.assertEqual(item["comments"], [])

    # --- comments[] model (default shape) ---

    def test_fresh_item_has_an_empty_comments_list(self):
        item_id = self.create_item()

        item = self.backend.get(item_id)

        self.assertEqual(item["comments"], [])

    # --- set-description ---

    def test_set_description_replaces_it(self):
        item_id = self.create_item(description="Original description.")

        item = self.backend.set_description(item_id, "Updated description.")

        self.assertEqual(item["description"], "Updated description.")
        self.assertEqual(self.backend.get(item_id)["description"], "Updated description.")

    def test_set_description_with_empty_string_clears_it(self):
        item_id = self.create_item(description="Original description.")

        item = self.backend.set_description(item_id, "")

        self.assertEqual(item["description"], "")
        self.assertEqual(self.backend.get(item_id)["description"], "")

    def test_set_description_unknown_id_raises(self):
        with self.assertRaises(Exception):
            self.backend.set_description("WI-9999", "text")

    # --- set-title ---

    def test_set_title_replaces_it(self):
        item_id = self.create_item(title="Old title")

        item = self.backend.set_title(item_id, "New title")

        self.assertEqual(item["title"], "New title")
        self.assertEqual(self.backend.get(item_id)["title"], "New title")

    def test_set_title_rejects_empty_string(self):
        item_id = self.create_item(title="Old title")

        with self.assertRaises(Exception):
            self.backend.set_title(item_id, "")
        self.assertEqual(self.backend.get(item_id)["title"], "Old title")

    def test_set_title_unknown_id_raises(self):
        with self.assertRaises(Exception):
            self.backend.set_title("WI-9999", "New title")

    # --- set-type ---

    def test_set_type_replaces_it(self):
        item_id = self.create_item()

        item = self.backend.set_type(item_id, "bug")

        self.assertEqual(item["type"], "bug")
        self.assertEqual(self.backend.get(item_id)["type"], "bug")

    def test_set_type_rejects_empty_string(self):
        item_id = self.create_item()

        with self.assertRaises(Exception):
            self.backend.set_type(item_id, "")

    def test_set_type_unknown_id_raises(self):
        with self.assertRaises(Exception):
            self.backend.set_type("WI-9999", "bug")

    # --- id validation / path traversal ---
    #
    # Ids may end up in filesystem paths (local) today and in `ticket/<id>` branch
    # names (ADR-0005) tomorrow — every backend must reject anything that is not a
    # bare identifier, not just `local`. Every mutating op is covered here -- including
    # the four maintenance ops added by the ADR-0002 addendum (09.07.2026) -- so a
    # future refactor that drops id validation in any one of them turns this red
    # instead of silently reopening the traversal surface.

    def _call_with_id(self, op, item_id):
        """Invokes `op` (one of the contract's mutating operation names) with a
        syntactically-valid extra argument, on the given (possibly malicious) id."""
        args = {
            "get": (item_id,),
            "set_status": (item_id, "Done"),
            "append_result": (item_id, "ref"),
            "comment": (item_id, "a note"),
            "set_description": (item_id, "text"),
            "set_title": (item_id, "New title"),
            "set_type": (item_id, "bug"),
        }[op]
        return getattr(self.backend, op)(*args)

    def test_rejects_ids_with_path_separators_or_dots(self):
        ops = (
            "get", "set_status", "append_result",
            "comment", "set_description", "set_title", "set_type",
        )
        for malicious_id in ("../../x", "/etc/x", "a/b", "a.md"):
            for op in ops:
                with self.subTest(malicious_id=malicious_id, op=op):
                    with self.assertRaises(Exception):
                        self._call_with_id(op, malicious_id)

    def test_path_traversal_id_cannot_read_or_write_outside_workitems_dir(self):
        canary_dir = tempfile.mkdtemp(prefix="ccpr-workitems-canary-")
        self.addCleanup(shutil.rmtree, canary_dir, ignore_errors=True)
        canary_path = Path(canary_dir) / "canary.md"
        canary_path.write_text("original", encoding="utf-8")

        # A relative id that walks out of the workitems dir into the canary dir.
        relative_id = f"{os.path.relpath(canary_dir, self.tmp_dir)}/canary"

        ops = (
            "get", "append_result",
            "comment", "set_description", "set_title", "set_type",
        )
        for op in ops:
            with self.subTest(op=op):
                with self.assertRaises(Exception):
                    self._call_with_id(op, relative_id)

        self.assertEqual(canary_path.read_text(encoding="utf-8"), "original")
