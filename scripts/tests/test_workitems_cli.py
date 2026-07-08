"""test_workitems_cli.py – End-to-end tests for the workitems.py CLI dispatcher (ADR-0002).

Invokes the script as a subprocess (the real entry point: `workitems.py <op> ...`) rather
than importing its internals, so these tests also cover settings.json provider resolution
and JSON-on-stdout behaviour.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "workitems.py"

ITEM_TEXT = """---
id: WI-0001
title: Rate-limit the authentication endpoints
status: Backlog
type: feat
owner:
refs: [ADR-0011]
tags: [security]
created: 2026-07-08
---

Add a limiter to the login endpoint.

## Acceptance Criteria
- Login is limited to N attempts per identifier.

## Result
<!-- append-result writes PR/commit links here -->
"""


class WorkitemsCliTest(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path(tempfile.mkdtemp(prefix="ccpr-workitems-cli-"))
        self.addCleanup(shutil.rmtree, self.project_dir, ignore_errors=True)
        self.workitems_dir = self.project_dir / "docs" / "workitems"
        self.workitems_dir.mkdir(parents=True)
        (self.workitems_dir / "WI-0001.md").write_text(ITEM_TEXT, encoding="utf-8")

    def run_cli(self, *args):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args, "--project", str(self.project_dir)],
            capture_output=True, text=True,
        )
        return result

    def test_create_assigns_id_and_defaults_to_backlog(self):
        result = self.run_cli("create", "--title", "New feature")

        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)
        self.assertTrue(item["id"])
        self.assertEqual(item["title"], "New feature")
        self.assertEqual(item["status"], "Backlog")

        # The created item must be discoverable through the other operations too.
        list_result = self.run_cli("list")
        ids = [i["id"] for i in json.loads(list_result.stdout)]
        self.assertIn(item["id"], ids)

    def test_create_with_owner_and_description(self):
        result = self.run_cli(
            "create", "--title", "New feature",
            "--owner", "alice", "--description", "Some text.",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)
        self.assertEqual(item["owner"], "alice")
        self.assertEqual(item["description"], "Some text.")

    def test_list_defaults_to_local_provider_and_prints_json(self):
        result = self.run_cli("list")

        self.assertEqual(result.returncode, 0, result.stderr)
        items = json.loads(result.stdout)
        self.assertEqual([item["id"] for item in items], ["WI-0001"])

    def test_get_prints_full_item_as_json(self):
        result = self.run_cli("get", "WI-0001")

        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)
        self.assertEqual(item["title"], "Rate-limit the authentication endpoints")

    def test_claim_sets_owner(self):
        result = self.run_cli("claim", "WI-0001", "--owner", "alice")

        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)
        self.assertEqual(item["owner"], "alice")

    def test_set_status_updates_status(self):
        result = self.run_cli("set-status", "WI-0001", "In Progress")

        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)
        self.assertEqual(item["status"], "In Progress")

    def test_set_status_with_unknown_status_fails_with_stderr_message(self):
        result = self.run_cli("set-status", "WI-0001", "Not-A-Status")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown status", result.stderr)

    def test_append_result_adds_reference(self):
        result = self.run_cli("append-result", "WI-0001", "https://example.org/pr/1")

        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)
        self.assertIn("https://example.org/pr/1", item["result-link"])

    def test_unknown_provider_fails_with_stderr_message(self):
        settings_path = self.project_dir / "settings.json"
        settings_path.write_text(
            json.dumps({"workitems": {"provider": "does-not-exist"}}), encoding="utf-8",
        )

        result = self.run_cli("list")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does-not-exist", result.stderr)

    def test_malformed_settings_json_fails_cleanly(self):
        settings_path = self.project_dir / "settings.json"
        settings_path.write_text("{ not valid json", encoding="utf-8")

        result = self.run_cli("list")

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)

    def _write_provider(self, provider_name, source):
        provider_path = SCRIPT_PATH.parent / "lib" / "workitems" / f"{provider_name}.py"
        provider_path.write_text(source, encoding="utf-8")
        self.addCleanup(provider_path.unlink, missing_ok=True)
        return provider_name

    def _use_provider(self, provider_name):
        settings_path = self.project_dir / "settings.json"
        settings_path.write_text(
            json.dumps({"workitems": {"provider": provider_name}}), encoding="utf-8",
        )

    def test_work_item_error_from_backend_create_is_reported_cleanly(self):
        provider_name = self._write_provider(
            "_test_broken_provider",
            "from workitems import WorkItemError\n\n"
            "def create(config):\n"
            "    raise WorkItemError('broken provider: missing token')\n",
        )
        self._use_provider(provider_name)

        result = self.run_cli("list")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("broken provider: missing token", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_dependency_inside_valid_provider_is_not_misreported_as_unknown_provider(self):
        provider_name = self._write_provider(
            "_test_provider_with_missing_dep",
            "import this_dependency_does_not_exist_anywhere\n\n"
            "def create(config):\n"
            "    raise NotImplementedError\n",
        )
        self._use_provider(provider_name)

        result = self.run_cli("list")

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(f"Unknown work-item provider: {provider_name}", result.stderr)


if __name__ == "__main__":
    unittest.main()
