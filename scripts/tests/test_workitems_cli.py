"""test_workitems_cli.py – End-to-end tests for the workitems.py CLI dispatcher (ADR-0002).

Invokes the script as a subprocess (the real entry point: `workitems.py <op> ...`) rather
than importing its internals, so these tests also cover settings.json provider resolution
and JSON-on-stdout behaviour.
"""

import json
import os
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

    def test_youtrack_provider_config_is_resolved_generically_no_network(self):
        # Proves resolve_provider()/load_backend() work for a non-local provider
        # without any provider-specific dispatcher code — the failure here (missing
        # token env var) happens in youtrack.create()'s config validation, before any
        # HTTP call, so this stays network-free.
        token_env = "CCPR_TEST_YOUTRACK_TOKEN_CLI_MISSING"
        env = dict(os.environ)
        env.pop(token_env, None)
        settings_path = self.project_dir / "settings.json"
        settings_path.write_text(
            json.dumps({
                "workitems": {
                    "provider": "youtrack",
                    "youtrack": {
                        "baseUrl": "https://faketrack.example.org",
                        "project": "TEST",
                        "tokenEnv": token_env,
                    },
                },
            }),
            encoding="utf-8",
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "list", "--project", str(self.project_dir)],
            capture_output=True, text=True, env=env,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(token_env, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

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

    def test_lift_dry_run_writes_nothing(self):
        source_path = self.project_dir / "OLD_BACKLOG.md"
        source_path.write_text("- [ ] Add rate limiting to login endpoint\n", encoding="utf-8")

        result = self.run_cli("lift", str(source_path))

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(len(report["proposed"]), 1)
        self.assertFalse(report["applied"])
        # WI-0001 from setUp's fixture is the only item; dry run created nothing new.
        list_result = self.run_cli("list")
        self.assertEqual(len(json.loads(list_result.stdout)), 1)

    def test_lift_apply_writes_the_proposed_item(self):
        source_path = self.project_dir / "OLD_BACKLOG.md"
        source_path.write_text("- [x] Fix flaky test in auth module\n", encoding="utf-8")

        result = self.run_cli("lift", str(source_path), "--apply")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["applied"])
        self.assertIsNotNone(report["proposed"][0]["id"])

        list_result = self.run_cli("list")
        titles = [item["title"] for item in json.loads(list_result.stdout)]
        self.assertIn("Fix flaky test in auth module", titles)

    def test_lift_exclude_flag_excludes_a_line_with_reason(self):
        source_path = self.project_dir / "OLD_BACKLOG.md"
        source_path.write_text("- [ ] Roll out feature flag for new dashboard\n", encoding="utf-8")

        result = self.run_cli(
            "lift", str(source_path),
            "--exclude", "feature flag=ops rollout note, not a work item",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["proposed"], [])
        self.assertEqual(report["excluded"][0]["reason"], "ops rollout note, not a work item")

    def test_migrate_moves_items_to_target_and_flips_the_active_provider(self):
        # Self-contained in-memory fake target: no network, no cross-invocation
        # persistence needed since this test only makes ONE CLI call and inspects
        # its JSON report plus the on-disk idmap/settings.json artifacts.
        provider_name = self._write_provider(
            "_test_fake_migrate_target",
            "from workitems import WorkItemError\n\n"
            "_ITEMS = {}\n"
            "_NEXT = [1]\n\n"
            "def create(config):\n"
            "    return _FakeBackend()\n\n"
            "class _FakeBackend:\n"
            "    def create(self, title, item_type=None, owner=None, description=None):\n"
            "        item_id = f'FAKE-{_NEXT[0]}'\n"
            "        _NEXT[0] += 1\n"
            "        item = {'id': item_id, 'title': title, 'status': 'Backlog',\n"
            "                'description': description or '', 'result-link': [], 'owner': owner}\n"
            "        _ITEMS[item_id] = item\n"
            "        return dict(item)\n"
            "    def list(self, status=None, owner=None):\n"
            "        return [dict(i) for i in _ITEMS.values()]\n"
            "    def get(self, item_id):\n"
            "        if item_id not in _ITEMS:\n"
            "            raise WorkItemError(f'Unknown work item: {item_id}')\n"
            "        return dict(_ITEMS[item_id])\n"
            "    def claim(self, item_id, owner=None):\n"
            "        if owner is not None:\n"
            "            _ITEMS[item_id]['owner'] = owner\n"
            "        return dict(_ITEMS[item_id])\n"
            "    def set_status(self, item_id, status):\n"
            "        _ITEMS[item_id]['status'] = status\n"
            "        return dict(_ITEMS[item_id])\n"
            "    def append_result(self, item_id, ref):\n"
            "        _ITEMS[item_id]['result-link'].append(ref)\n"
            "        return dict(_ITEMS[item_id])\n",
        )

        result = self.run_cli("migrate", "--to", provider_name)

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(len(report["migrated"]), 1)
        self.assertTrue(report["archived"])

        idmap_path = self.project_dir / "docs" / "workitems-idmap.yml"
        self.assertTrue(idmap_path.is_file())
        self.assertIn("WI-0001", idmap_path.read_text(encoding="utf-8"))

        settings = json.loads((self.project_dir / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["workitems"]["provider"], provider_name)

        # Rollback path: archiving never deletes, but nothing moves it back
        # automatically -- the exact restore command must be spelled out, both in
        # the JSON report and as an informational stderr message for a human
        # running the CLI directly.
        self.assertIn(report["archive_path"], report["restore_instructions"])
        self.assertIn("local", report["restore_instructions"])
        self.assertIn("mv ", result.stderr)
        self.assertIn(report["archive_path"], result.stderr)

    def test_migrating_twice_to_the_same_target_refuses_on_the_second_call(self):
        provider_name = self._write_provider(
            "_test_fake_migrate_target_twice",
            "from workitems import WorkItemError\n\n"
            "_ITEMS = {}\n"
            "_NEXT = [1]\n\n"
            "def create(config):\n"
            "    return _FakeBackend()\n\n"
            "class _FakeBackend:\n"
            "    def create(self, title, item_type=None, owner=None, description=None):\n"
            "        item_id = f'FAKE-{_NEXT[0]}'\n"
            "        _NEXT[0] += 1\n"
            "        item = {'id': item_id, 'title': title, 'status': 'Backlog',\n"
            "                'description': description or '', 'result-link': [], 'owner': owner}\n"
            "        _ITEMS[item_id] = item\n"
            "        return dict(item)\n"
            "    def list(self, status=None, owner=None):\n"
            "        return [dict(i) for i in _ITEMS.values()]\n"
            "    def get(self, item_id):\n"
            "        if item_id not in _ITEMS:\n"
            "            raise WorkItemError(f'Unknown work item: {item_id}')\n"
            "        return dict(_ITEMS[item_id])\n"
            "    def claim(self, item_id, owner=None):\n"
            "        if owner is not None:\n"
            "            _ITEMS[item_id]['owner'] = owner\n"
            "        return dict(_ITEMS[item_id])\n"
            "    def set_status(self, item_id, status):\n"
            "        _ITEMS[item_id]['status'] = status\n"
            "        return dict(_ITEMS[item_id])\n"
            "    def append_result(self, item_id, ref):\n"
            "        _ITEMS[item_id]['result-link'].append(ref)\n"
            "        return dict(_ITEMS[item_id])\n",
        )

        first_result = self.run_cli("migrate", "--to", provider_name)
        self.assertEqual(first_result.returncode, 0, first_result.stderr)
        first_report = json.loads(first_result.stdout)
        self.assertEqual(len(first_report["migrated"]), 1)

        second_result = self.run_cli("migrate", "--to", provider_name)

        self.assertNotEqual(second_result.returncode, 0)
        self.assertIn("already the active provider", second_result.stderr)
        # No duplicate: re-run created nothing new (the CLI refused before doing
        # anything, so there's no target-side count to check here, but the idmap
        # must be untouched from the first run).
        idmap_path = self.project_dir / "docs" / "workitems-idmap.yml"
        self.assertEqual(idmap_path.read_text(encoding="utf-8").count("WI-0001"), 1)

    def test_migrate_from_a_non_local_source_still_flips_provider_on_full_success(self):
        # A non-local source has nothing to archive (source_workitems_dir is None),
        # so report["archived"] is always False for it -- the provider flip must be
        # gated on fully_migrated, not archived, or a non-local->X migration would
        # never flip the active provider even on complete success.
        source_provider_name = self._write_provider(
            "_test_fake_nonlocal_source",
            "from workitems import WorkItemError\n\n"
            "_ITEMS = {'FAKE-SRC-1': {'id': 'FAKE-SRC-1', 'title': 'Existing item',\n"
            "    'status': 'Backlog', 'description': '', 'result-link': [], 'owner': None}}\n"
            "_NEXT = [2]\n\n"
            "def create(config):\n"
            "    return _FakeBackend()\n\n"
            "class _FakeBackend:\n"
            "    def create(self, title, item_type=None, owner=None, description=None):\n"
            "        item_id = f'FAKE-SRC-{_NEXT[0]}'\n"
            "        _NEXT[0] += 1\n"
            "        item = {'id': item_id, 'title': title, 'status': 'Backlog',\n"
            "                'description': description or '', 'result-link': [], 'owner': owner}\n"
            "        _ITEMS[item_id] = item\n"
            "        return dict(item)\n"
            "    def list(self, status=None, owner=None):\n"
            "        return [dict(i) for i in _ITEMS.values()]\n"
            "    def get(self, item_id):\n"
            "        if item_id not in _ITEMS:\n"
            "            raise WorkItemError(f'Unknown work item: {item_id}')\n"
            "        return dict(_ITEMS[item_id])\n"
            "    def claim(self, item_id, owner=None):\n"
            "        if owner is not None:\n"
            "            _ITEMS[item_id]['owner'] = owner\n"
            "        return dict(_ITEMS[item_id])\n"
            "    def set_status(self, item_id, status):\n"
            "        _ITEMS[item_id]['status'] = status\n"
            "        return dict(_ITEMS[item_id])\n"
            "    def append_result(self, item_id, ref):\n"
            "        _ITEMS[item_id]['result-link'].append(ref)\n"
            "        return dict(_ITEMS[item_id])\n",
        )
        self._use_provider(source_provider_name)

        result = self.run_cli("migrate", "--to", "local")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["fully_migrated"])
        self.assertFalse(report["archived"])

        settings = json.loads((self.project_dir / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["workitems"]["provider"], "local")

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
