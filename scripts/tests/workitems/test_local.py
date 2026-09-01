"""test_local.py – Wires the `local` backend into the shared contract suite (ADR-0002).

Also carries `local`-specific white-box tests that don't belong in the
backend-agnostic contract suite (e.g. the .tmp-file write-failure cleanup below,
which depends on local's own atomic-write implementation detail).
"""

import contextlib
import io
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from workitems import WorkItemError, local  # noqa: E402

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


class LocalBackendSetDescriptionTest(unittest.TestCase):
    """set-description rewrites only the free-text block before the first `## `
    heading -- Acceptance Criteria / Result / Comments sections must survive
    untouched (ADR-0002 addendum, 09.07.2026)."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-setdesc-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def test_other_sections_survive_a_description_replacement(self):
        item = self.backend.create(title="First", description="Original.")
        self.backend.append_result(item["id"], "https://example.org/pr/1")
        self.backend.comment(item["id"], "A note.")

        updated = self.backend.set_description(item["id"], "Replaced.")

        self.assertEqual(updated["description"], "Replaced.")
        self.assertEqual(updated["result-link"], ["https://example.org/pr/1"])
        self.assertEqual(updated["comments"], ["A note."])


class LocalBackendSectionShadowingTest(unittest.TestCase):
    """A user-authored line that reads exactly like a section heading (e.g. `## Comments`)
    must never be mistaken for the real section boundary on the next read -- neither in
    `description` nor in `comment` text. Regression test for the section-shadowing bug
    found in review of the ADR-0002 addendum (09.07.2026): section boundaries used to be
    determined by re-scanning the (user-influenced) body for heading-looking lines, so
    user text containing one could truncate the description early and/or make the real
    `## Comments`/`## Result` section unreachable."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-shadowing-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def test_set_description_with_a_fake_comments_heading_does_not_shadow_the_real_section(self):
        item = self.backend.create(title="First", description="Original.")
        self.backend.comment(item["id"], "Genuine earlier comment.")

        updated = self.backend.set_description(
            item["id"], "New text\n## Comments\nFake entry",
        )

        self.assertEqual(updated["description"], "New text\n## Comments\nFake entry")
        self.assertEqual(updated["comments"], ["Genuine earlier comment."])

    def test_set_description_with_a_fake_result_heading_does_not_shadow_the_real_section(self):
        item = self.backend.create(title="First", description="Original.")
        self.backend.append_result(item["id"], "https://example.org/pr/1")

        updated = self.backend.set_description(
            item["id"], "New text\n## Result\nFake result entry",
        )

        self.assertEqual(updated["description"], "New text\n## Result\nFake result entry")
        self.assertEqual(updated["result-link"], ["https://example.org/pr/1"])

    def test_description_with_a_fake_heading_line_round_trips_unchanged(self):
        item = self.backend.create(title="First", description="Original.")

        first = self.backend.set_description(item["id"], "Text one\n## Comments\nFake one")
        second = self.backend.set_description(item["id"], first["description"])

        self.assertEqual(second["description"], "Text one\n## Comments\nFake one")

    def test_comment_with_a_fake_heading_line_does_not_shadow_the_real_result_section(self):
        item = self.backend.create(title="First", description="Original.")
        self.backend.append_result(item["id"], "https://example.org/pr/1")

        self.backend.comment(item["id"], "## Result\nFake result via comment")

        self.assertEqual(
            self.backend.get(item["id"])["result-link"], ["https://example.org/pr/1"],
        )


class LocalBackendQueryRejectionTest(unittest.TestCase):
    """`local` has no server-side query language to pass through to (ADR-0002 2nd
    addendum, 09.07.2026): `list --query` raises rather than silently ignoring the
    flag or approximating it with a client-side text search -- either of which would
    give a caller a false sense that the same query semantics work on both backends."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-query-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def test_list_with_query_raises(self):
        self.backend.create(title="First")

        with self.assertRaises(WorkItemError):
            self.backend.list(query="Sprint: 4")


class LocalBackendUnknownFilterValueTest(unittest.TestCase):
    """`local`'s frontmatter files can be hand-edited directly -- nothing on the read
    path (`_item_from_path`) enforces STATUS_VALUES/PRIORITY_VALUES; only `set_status`/
    `set_priority` (WRITE) reject a value outside the vocabulary. So a hand-written
    `status:`/`priority:` field outside the vocabulary is a real, reachable item shape
    on this backend today -- `list --status`/`--priority` must still be able to find
    it, with a stderr warning distinguishing that outcome from a caller's plain typo."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-unknown-filter-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def test_list_by_status_finds_a_hand_written_out_of_vocabulary_status(self):
        (Path(self.tmp_dir) / "WI-0001.md").write_text(
            "---\nid: WI-0001\ntitle: Scratch\nstatus: Under Review\n---\nBody.\n",
            encoding="utf-8",
        )

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            items = self.backend.list(status="Under Review")

        self.assertEqual([item["id"] for item in items], ["WI-0001"])
        self.assertIn("Under Review", captured_stderr.getvalue())

    def test_list_by_priority_finds_a_hand_written_out_of_vocabulary_priority(self):
        (Path(self.tmp_dir) / "WI-0001.md").write_text(
            "---\nid: WI-0001\ntitle: Scratch\nstatus: Backlog\n"
            "priority: Urgentissimo\n---\nBody.\n",
            encoding="utf-8",
        )

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            items = self.backend.list(priority="Urgentissimo")

        self.assertEqual([item["id"] for item in items], ["WI-0001"])
        self.assertIn("Urgentissimo", captured_stderr.getvalue())


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


class LocalBackendLinksEncodingTest(unittest.TestCase):
    """`links` is stored as a flat `type:target` string list, not nested objects
    (ADR-0008) -- these tests prove the on-disk shape and a full parse-from-disk
    round-trip, not just the in-memory return value."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-links-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def test_links_are_written_as_type_target_strings_in_frontmatter(self):
        item = self.backend.create(title="First")
        target = self.backend.create(title="Second")

        self.backend.add_link(item["id"], "depends-on", target["id"])

        path = Path(self.tmp_dir) / f"{item['id']}.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(f"links: [depends-on:{target['id']}]", text)

    def test_links_round_trip_after_a_fresh_parse_from_disk(self):
        item = self.backend.create(title="First")
        target = self.backend.create(title="Second")
        self.backend.add_link(item["id"], "depends-on", target["id"])

        reloaded = local.create({"workitems_dir": self.tmp_dir})
        fetched = reloaded.get(item["id"])

        self.assertEqual(
            fetched["links"], [{"type": "depends-on", "target": target["id"]}],
        )


class LocalBackendMultilineEntryShapeTest(unittest.TestCase):
    """On-disk shape assertions for a multi-line Comments/Result entry (findings
    #44/#45), beyond what the backend-neutral contract suite in contract.py checks
    (get()'s return value) -- these read the raw Markdown file itself, since the bug
    was specifically in how an entry is laid out on disk and re-parsed from it."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-multiline-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def _file_text(self, item_id):
        return (Path(self.tmp_dir) / f"{item_id}.md").read_text(encoding="utf-8")

    def test_continuation_lines_keep_their_indentation(self):
        """Boundary condition 1 (measured on WI-0109): a continuation line's leading
        whitespace is part of its content, not incidental formatting to be trimmed."""
        item = self.backend.create(title="First")
        text = "First line.\n  Indented continuation."

        self.backend.comment(item["id"], text)

        self.assertIn("- First line.\n  Indented continuation.\n", self._file_text(item["id"]))
        self.assertEqual(self.backend.get(item["id"])["comments"], [text])

    def test_an_indented_dash_line_is_a_continuation_not_a_new_entry(self):
        """Boundary condition 2 (measured on WI-0044, WI-0109): only a `- ` at column
        0 opens a new entry -- an indented `- ` (a nested sub-bullet inside a
        comment's own text) is content, and must not be split into its own entry."""
        item = self.backend.create(title="First")
        text = "First line.\n  - nested bullet\nMore text."

        self.backend.comment(item["id"], text)

        file_text = self._file_text(item["id"])
        self.assertIn("- First line.\n  - nested bullet\nMore text.\n", file_text)
        # Exactly one column-0 "- " line in the whole file: the indented nested
        # bullet did not spawn a second entry.
        self.assertEqual(len(re.findall(r"(?m)^- ", file_text)), 1)
        self.assertEqual(self.backend.get(item["id"])["comments"], [text])

    def test_blank_lines_inside_an_entry_are_preserved_on_disk(self):
        """Boundary condition 3 (measured on WI-0019 through WI-0072): a blank line
        in the middle of a comment is part of that comment's own text, not a
        separator between two entries -- the flattening bug's most silently-passable
        failure mode (an entry-count assertion alone would not catch it)."""
        item = self.backend.create(title="First")
        text = "First line.\n\nThird line after a blank line."

        self.backend.comment(item["id"], text)

        self.assertIn("- First line.\n\nThird line after a blank line.\n", self._file_text(item["id"]))
        self.assertEqual(self.backend.get(item["id"])["comments"], [text])

    def test_a_dash_line_inside_a_fenced_code_block_is_a_known_limitation(self):
        """Boundary condition 4: the entry boundary rule (`line.startswith("- ")` at
        column 0) is not fence-aware. Checked against the live corpus specimen
        (WI-0121) first: it carries exactly one stray ``` token in running prose, not
        an opening/closing pair, so it does not actually exercise this case. This
        test instead constructs a genuine paired fence with a column-0 `- ` line
        inside it, to name the limit explicitly rather than leave it undiscovered:
        such a line is split into a second entry, same as it would be outside a
        fence. Not fixed here -- ADR-0002's Comments/Result channel has no concept
        of embedded code fences, and a fence-aware parser is out of scope for this
        fix (see local.py's `_section_entries` docstring)."""
        item = self.backend.create(title="First")
        text = "Run this:\n```\n- not a bullet, just shell output\n```\nDone."

        self.backend.comment(item["id"], text)

        comments = self.backend.get(item["id"])["comments"]
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0], "Run this:\n```")
        self.assertEqual(comments[1], "not a bullet, just shell output\n```\nDone.")


class LocalBackendUnbulletedSectionShapeTest(unittest.TestCase):
    """Regression tests for a gap in `_section_entries`: an entry only starts at a
    column-0 `- ` line, so a section whose content begins with a non-bullet line has
    nothing to attach those lines to -- they fell out of the parsed result entirely.
    Measured on the live corpus: docs/workitems/WI-0107.md's `## Result` section is
    ten non-blank lines of hand-written prose with no bullet anywhere in it; the
    reader returned [] for it. 12 of 140 corpus items carry this shape in `## Result`
    (324 dropped non-blank lines total), all hand-written rather than appended
    through `append_result`/`comment`."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="ccpr-workitems-unbulleted-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.backend = local.create({"workitems_dir": self.tmp_dir})

    def _write_raw(self, item_id, result_section_text):
        # Deliberately no blank-line padding between `result_section_text` and the
        # next heading -- `result_section_text` must equal the section's raw content
        # exactly (`lines[heading_idx + 1:end_idx]`), or a byte-identical assertion
        # against it would be testing the fixture's own padding, not the function.
        (Path(self.tmp_dir) / f"{item_id}.md").write_text(
            "---\n"
            f"id: {item_id}\n"
            "title: Hand-written fixture\n"
            "status: Backlog\n"
            "---\n"
            "\n"
            "Description.\n"
            "\n"
            "## Acceptance Criteria\n"
            "\n"
            "## Result\n"
            f"{result_section_text}\n"
            "## Comments\n",
            encoding="utf-8",
        )

    def test_a_section_with_no_bullet_at_all_round_trips_byte_identical(self):
        """Measured shape: docs/workitems/WI-0107.md's `## Result` -- prose, no
        bullet anywhere in the section, including an internal blank line."""
        item_id = "WI-0001"
        prose = (
            "Closed 26.08.2026, commit `e324178`.\n"
            "\n"
            "Second paragraph after a blank line.\n"
            "Third line, no blank line before it."
        )
        self._write_raw(item_id, prose)

        result_links = self.backend.get(item_id)["result-link"]

        self.assertEqual(result_links, [prose])

    def test_unbulleted_prose_before_a_later_bullet_round_trips_byte_identical(self):
        """Measured shape: a hand-written section that opens with prose and only
        later gets a real bulleted entry appended."""
        item_id = "WI-0001"
        preamble = "Preamble line one.\nPreamble line two."
        self._write_raw(item_id, f"{preamble}\n- A real bulleted entry.")

        result_links = self.backend.get(item_id)["result-link"]

        self.assertEqual(result_links, [preamble, "A real bulleted entry."])

    def test_no_non_blank_line_in_a_section_is_absent_from_the_returned_entries(self):
        """The general property, not just the two instances above: whatever shape a
        section has, every non-blank line the file holds must surface somewhere in
        the concatenation of the returned entries. This is the assertion that would
        have caught the WI-0107 regression instead of one fixed example of it."""
        item_id = "WI-0001"
        section_text = (
            "Unbulleted first line.\n"
            "\n"
            "- A bulleted entry.\n"
            "  Continuation of that entry, no dash.\n"
            "Trailing prose after the bullet, still no dash."
        )
        self._write_raw(item_id, section_text)

        entries = self.backend.get(item_id)["result-link"]
        concatenated_lines = "\n".join(entries).split("\n")

        for line in section_text.split("\n"):
            # A returned entry's own bullet marker is stripped (that is the entry's
            # boundary syntax, not its content) -- compare content, not markup.
            content = line[2:] if line.startswith("- ") else line
            if content.strip():
                self.assertIn(content, concatenated_lines)

    def test_appending_to_a_section_that_begins_with_unbulleted_text_preserves_it_byte_identical(self):
        """finding-#44/#45 sibling: `_append_to_section` rewrites the whole section
        from its own parsed entries on every call, so this shape must survive an
        append the same way a purely bulleted section already does."""
        item_id = "WI-0001"
        prose = "Closed prose with no bullet at all,\nspanning two lines."
        self._write_raw(item_id, prose)

        item = self.backend.append_result(item_id, "https://example.org/pr/9")

        self.assertEqual(item["result-link"], [prose, "https://example.org/pr/9"])
        file_text = (Path(self.tmp_dir) / f"{item_id}.md").read_text(encoding="utf-8")
        self.assertIn(f"## Result\n{prose}\n- https://example.org/pr/9\n", file_text)
        self.assertEqual(
            self.backend.get(item_id)["result-link"],
            [prose, "https://example.org/pr/9"],
        )


if __name__ == "__main__":
    unittest.main()
