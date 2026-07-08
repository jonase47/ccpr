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

# A self-contained fake provider modeling claim/heartbeat with a runner + a FIXED
# (deliberately old) heartbeat timestamp -- old enough that it is always stale
# relative to the real "now" a sweep CLI invocation uses (there is no clock
# injection at the CLI boundary; sweep()'s clock parameter is for the module-level
# tests). Persists to a JSON state file (config["state_file"]) since claim/heartbeat/
# sweep CLI tests need STATE TO SURVIVE ACROSS SEPARATE SUBPROCESS INVOCATIONS
# (create in one `workitems.py` call, claim in the next) -- an in-memory module
# global (as migrate's single-invocation fake used) resets every time. This is
# purely for proving CLI WIRING (arg parsing, config resolution, dispatch) -- the
# actual claim/heartbeat/sweep LOGIC is covered thoroughly against the real
# youtrack backend in test_youtrack.py / test_sweep.py.
FAKE_CLAIMING_PROVIDER_SOURCE = (
    "import json\n"
    "import os\n"
    "from workitems import WorkItemError\n\n"
    "def create(config):\n"
    "    return _FakeBackend(config['state_file'])\n\n"
    "class _FakeBackend:\n"
    "    def __init__(self, state_file):\n"
    "        self.state_file = state_file\n"
    "        if os.path.isfile(state_file):\n"
    "            with open(state_file, encoding='utf-8') as f:\n"
    "                data = json.load(f)\n"
    "        else:\n"
    "            data = {'items': {}, 'next': 1}\n"
    "        self._items = data['items']\n"
    "        self._next = data['next']\n"
    "    def _save(self):\n"
    "        with open(self.state_file, 'w', encoding='utf-8') as f:\n"
    "            json.dump({'items': self._items, 'next': self._next}, f)\n"
    "    def create(self, title, item_type=None, owner=None, description=None):\n"
    "        item_id = f'FAKE-{self._next}'\n"
    "        self._next += 1\n"
    "        item = {'id': item_id, 'title': title, 'status': 'Backlog',\n"
    "                'description': description or '', 'result-link': [], 'owner': owner,\n"
    "                'runner': None, 'heartbeat': None}\n"
    "        self._items[item_id] = item\n"
    "        self._save()\n"
    "        return dict(item)\n"
    "    def list(self, status=None, owner=None):\n"
    "        items = list(self._items.values())\n"
    "        if status is not None:\n"
    "            items = [i for i in items if i['status'] == status]\n"
    "        return [dict(i) for i in items]\n"
    "    def get(self, item_id):\n"
    "        if item_id not in self._items:\n"
    "            raise WorkItemError(f'Unknown work item: {item_id}')\n"
    "        return dict(self._items[item_id])\n"
    "    def claim(self, item_id, owner=None, runner=None):\n"
    "        if owner is not None:\n"
    "            self._items[item_id]['owner'] = owner\n"
    "        if runner:\n"
    "            self._items[item_id]['runner'] = runner\n"
    "            self._items[item_id]['heartbeat'] = '2026-01-01T00:00:00+00:00'\n"
    "            self._items[item_id]['status'] = 'In Progress'\n"
    "        self._save()\n"
    "        return dict(self._items[item_id])\n"
    "    def heartbeat(self, item_id, runner):\n"
    "        self._items[item_id]['heartbeat'] = '2030-01-01T00:00:00+00:00'\n"
    "        self._save()\n"
    "        return dict(self._items[item_id])\n"
    "    def set_status(self, item_id, status):\n"
    "        self._items[item_id]['status'] = status\n"
    "        self._save()\n"
    "        return dict(self._items[item_id])\n"
    "    def append_result(self, item_id, ref):\n"
    "        self._items[item_id]['result-link'].append(ref)\n"
    "        self._save()\n"
    "        return dict(self._items[item_id])\n"
)


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

    def test_project_flag_before_the_subcommand_is_honored_not_silently_ignored(self):
        # Regression: argparse's subparsers merge a fresh sub-namespace into the
        # outer one after parsing the remaining args. The subcommand's OWN copy of
        # --project (inherited from the shared parent) carried its own
        # os.getcwd() default, which clobbered the value the top-level parser had
        # already parsed when --project appeared BEFORE the subcommand -- silently
        # redirecting every write to whatever directory the CLI happened to be
        # invoked from. Run with an explicit, harmless decoy cwd (never this repo)
        # so that if the bug reproduces, it writes into a throwaway directory
        # instead of polluting the real repository.
        decoy_cwd = Path(tempfile.mkdtemp(prefix="ccpr-workitems-decoy-cwd-"))
        self.addCleanup(shutil.rmtree, decoy_cwd, ignore_errors=True)

        result = subprocess.run(
            [
                sys.executable, str(SCRIPT_PATH), "--project", str(self.project_dir),
                "create", "--title", "New feature", "--type", "feat",
            ],
            capture_output=True, text=True, cwd=decoy_cwd,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)
        created_path = self.project_dir / "docs" / "workitems" / f"{item['id']}.md"
        self.assertTrue(
            created_path.is_file(),
            f"expected {created_path} to exist; --project before the subcommand "
            "must not be overridden by the subcommand's own default",
        )
        # Nothing must have leaked into the decoy cwd.
        self.assertFalse((decoy_cwd / "docs").exists())

    def test_project_flag_after_the_subcommand_still_works(self):
        decoy_cwd = Path(tempfile.mkdtemp(prefix="ccpr-workitems-decoy-cwd-"))
        self.addCleanup(shutil.rmtree, decoy_cwd, ignore_errors=True)

        result = subprocess.run(
            [
                sys.executable, str(SCRIPT_PATH), "create", "--title", "New feature",
                "--type", "feat", "--project", str(self.project_dir),
            ],
            capture_output=True, text=True, cwd=decoy_cwd,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)
        created_path = self.project_dir / "docs" / "workitems" / f"{item['id']}.md"
        self.assertTrue(created_path.is_file())
        self.assertFalse((decoy_cwd / "docs").exists())

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

    def _use_claiming_provider(self, provider_name, claiming_config=None):
        """Like _use_provider, but also gives FAKE_CLAIMING_PROVIDER_SOURCE the
        state_file it needs to persist across separate CLI subprocess invocations."""
        workitems_config = {
            "provider": provider_name,
            provider_name: {"state_file": str(self.project_dir / "_fake_claim_state.json")},
        }
        if claiming_config:
            workitems_config["claiming"] = claiming_config
        settings_path = self.project_dir / "settings.json"
        settings_path.write_text(json.dumps({"workitems": workitems_config}), encoding="utf-8")

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

    def test_claim_with_runner_sets_runner_and_in_progress(self):
        provider_name = self._write_provider("_test_fake_claiming_provider", FAKE_CLAIMING_PROVIDER_SOURCE)
        self._use_claiming_provider(provider_name)
        item = json.loads(self.run_cli("create", "--title", "New feature").stdout)

        result = self.run_cli("claim", item["id"], "--runner", "agent-1")

        self.assertEqual(result.returncode, 0, result.stderr)
        claimed = json.loads(result.stdout)
        self.assertEqual(claimed["runner"], "agent-1")
        self.assertEqual(claimed["status"], "In Progress")

    def test_heartbeat_subcommand_refreshes_the_timestamp(self):
        provider_name = self._write_provider("_test_fake_claiming_provider_hb", FAKE_CLAIMING_PROVIDER_SOURCE)
        self._use_claiming_provider(provider_name)
        item = json.loads(self.run_cli("create", "--title", "New feature").stdout)
        claimed = json.loads(self.run_cli("claim", item["id"], "--runner", "agent-1").stdout)

        result = self.run_cli("heartbeat", item["id"], "--runner", "agent-1")

        self.assertEqual(result.returncode, 0, result.stderr)
        refreshed = json.loads(result.stdout)
        self.assertNotEqual(refreshed["heartbeat"], claimed["heartbeat"])

    def test_sweep_leaves_stale_claim_in_progress_when_there_is_no_git_repo(self):
        # No git repo at all in project_dir: the default has_branch_commits must
        # treat that as "nothing to resume" (False), not raise.
        provider_name = self._write_provider("_test_fake_claiming_provider_sweep1", FAKE_CLAIMING_PROVIDER_SOURCE)
        self._use_claiming_provider(provider_name, claiming_config={"staleAfter": "1h"})
        item = json.loads(self.run_cli("create", "--title", "New feature").stdout)
        self.run_cli("claim", item["id"], "--runner", "agent-1")  # fixed old heartbeat -> always stale

        result = self.run_cli("sweep")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["parked"], [])
        self.assertIn(item["id"], report["left_in_progress"])

    def test_sweep_parks_stale_claim_with_ticket_branch_commits(self):
        provider_name = self._write_provider("_test_fake_claiming_provider_sweep2", FAKE_CLAIMING_PROVIDER_SOURCE)
        self._use_claiming_provider(provider_name, claiming_config={"staleAfter": "1h"})
        item = json.loads(self.run_cli("create", "--title", "New feature").stdout)
        self.run_cli("claim", item["id"], "--runner", "agent-1")

        self._init_git_repo_with_ticket_branch(item["id"])

        result = self.run_cli("sweep")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["parked"], [item["id"]])

    def _init_git_repo_with_ticket_branch(self, item_id):
        def run(*git_args):
            subprocess.run(["git", *git_args], cwd=self.project_dir, check=True, capture_output=True)

        run("init", "-q", "-b", "main")
        run("config", "user.email", "test@example.org")
        run("config", "user.name", "Test")
        (self.project_dir / "README.md").write_text("hello\n", encoding="utf-8")
        run("add", "README.md")
        run("commit", "-q", "-m", "initial")
        run("checkout", "-q", "-b", f"ticket/{item_id}")
        (self.project_dir / "work.txt").write_text("work\n", encoding="utf-8")
        run("add", "work.txt")
        run("commit", "-q", "-m", "did work")

    def test_null_claiming_config_is_treated_as_absent_not_an_error(self):
        # "claiming": null is a common, reasonable JSON idiom for "no value" -- treat
        # it the same as the key being absent (silent defaults), not a hard error.
        settings_path = self.project_dir / "settings.json"
        settings_path.write_text(
            json.dumps({"workitems": {"provider": "local", "claiming": None}}),
            encoding="utf-8",
        )

        result = self.run_cli("list")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_non_object_claiming_config_fails_cleanly_not_with_a_traceback(self):
        settings_path = self.project_dir / "settings.json"
        settings_path.write_text(
            json.dumps({"workitems": {"provider": "local", "claiming": 3600}}),
            encoding="utf-8",
        )

        result = self.run_cli("list")

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
