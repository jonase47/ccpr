"""test_conformance_run.py -- coverage for scripts/conformance-run.sh, Wave 1
skeleton (WI-0124).

## Why this exists

ADR-0010 (docs/adr/ADR-0010-conformance-runs-against-consumers.md) decides
that this repository's shipped checks must run against real consumer
projects as part of its own verification, not as an occasional manual
survey -- four shipped defects were found by hand on 27.08.2026 and every
one of them was structurally invisible from inside this repository's own
fixtures. Wave 1 (this module) covers only the skeleton: usage/`--help`, the
config reader, the not-configured path, consumer resolution, and the report
skeleton. **No check is invoked yet and no C1/C2/C3/P classification
happens** -- a resolved consumer is reported as covered with an empty
findings section. That is deliberate (see the script's own header): the
skeleton has to be right before Wave 2's classifier and Wave 3's pins rest
on it.

## House pattern

Own `TestBase` in this module, per this repository's convention that test
bases are duplicated per module rather than shared (see
`test_manual_lint.py:82`). `tempfile.mkdtemp` + `addCleanup`, subprocess
against the shipped script (never sourced internals), `MEMORY_SYNC_CONFIG`
pointed at a fixture path as the config seam -- the same shape
`test_memory_sync_promote.py:1017-1023` already uses to isolate a run from
the developer's own real `~/.claude/memory-sync.json`.

No `skipTest` / `skipUnless` anywhere in this module: every fixture here is
synthetic (throwaway directories built by `tempfile.mkdtemp`), so nothing in
this wave depends on a real consumer project being present on the machine
running the suite -- the same reasoning
`test_memory_lint_commonmark_corpus.py:5-15` already argues in writing for
its own corpus-dependent tests.

Every test asserts LIVENESS before content -- the report's own consumer/
scope line, or the die() message's own wording -- never only the absence of
something. A test that only checks "no crash" or "the bad string isn't
there" would pass on a report that silently dropped its scope statement,
exactly the false-clean shape ADR-0010 exists to close (KA-G-017).

## Groups

* **A** -- the not-configured contract: an absent config, an absent
  `conformance` key, and an empty `consumers: []` must all read identically
  to "nothing configured" (exit 0, loud stdout+stderr statement);
  `--require-consumers` turns that into exit 1.
* **B** -- configuration and operational errors: a consumer with no usable
  `path` is a malformed config (exit 2, the SHAPE is unknown -- not a
  runtime fact); a non-optional consumer whose `path` does not resolve on
  disk is exit 2 for a different reason (the shape is fine, the scope
  isn't); an `optional: true` consumer with the same missing path is
  reported as not-covered and does NOT fail the run; malformed JSON and an
  unknown flag are both exit 2.
* **D** -- report shape: every mandatory skeleton line is present, the
  report's own `**Exit:**` line agrees with the actual process exit status
  (the script's own C1 self-check), and `--show-paths` is the only thing
  that puts a consumer's local filesystem path into stdout (ADR-0010 §5:
  reports name a consumer by its `id`, never its `path`, unless asked).

Plus `--consumer <id>` coverage (restrict to one configured consumer /
an unconfigured id is a usage error) and `--help`, since both are in this
wave's flag set per the ADR even though the Group A/B/D split above does
not name them individually.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "conformance-run.sh"

# The mandatory skeleton lines every report this script ever produces (exit
# 0 or 1 -- exit 2 is a usage/config error and, like artifact-gate.sh's and
# manual-lint.sh's own die() paths, never reaches the report at all) must
# carry, regardless of how many consumers are configured or covered.
MANDATORY_SKELETON_SUBSTRINGS = (
    "# Conformance Run Report",
    "**Consumers:**",
    "**Scope:**",
    "**Run:**",
    "## Consumers",
    "## Findings",
    "**Summary:**",
    "**Exit:**",
)

NOT_CONFIGURED_STATEMENT = "0 configured, 0 covered — the conformance check DID NOT RUN"


def exit_line_value(stdout):
    """The integer following the report's own '**Exit:**' line, or None if
    no such line is present (the die()-shortcut usage/config-error paths
    never print one -- see the module docstring, Group D)."""
    for line in stdout.splitlines():
        if line.startswith("**Exit:**"):
            return int(line.split("**Exit:**", 1)[1].strip())
    return None


class ConformanceRunTestBase(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="ccpr-conformance-run-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        (self.home / ".claude").mkdir(parents=True)
        self.cfg_path = self.home / ".claude" / "memory-sync.json"

    # --- fixture -----------------------------------------------------------
    def write_config(self, conformance=None):
        """Write the personal config with a `conformance` block -- or, with
        `conformance=None` (the default), a config file that exists but
        carries no `conformance` key at all (Group A, test 3)."""
        cfg = {}
        if conformance is not None:
            cfg["conformance"] = conformance
        self.cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    def write_raw_config(self, text):
        """For a config fixture that must not parse as JSON at all."""
        self.cfg_path.write_text(text, encoding="utf-8")

    def make_consumer_dir(self, name="consumer"):
        d = self.home / "consumers" / name
        d.mkdir(parents=True)
        return d

    def env(self, **extra):
        e = {
            "HOME": str(self.home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "MEMORY_SYNC_CONFIG": str(self.cfg_path),
        }
        e.update(extra)
        return e

    def run_conformance(self, *args, **extra_env):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), *[str(a) for a in args]],
            capture_output=True, text=True, env=self.env(**extra_env),
        )

    @staticmethod
    def output(r):
        return "returncode: %s\nstdout:\n%s\nstderr:\n%s" % (r.returncode, r.stdout, r.stderr)


# ---------------------------------------------------------------------------
# Group A -- the not-configured contract
# ---------------------------------------------------------------------------
class NotConfiguredContractTest(ConformanceRunTestBase):
    def test_a_missing_config_path_is_exit_0_with_the_scope_statement(self):
        # self.cfg_path is never written -- MEMORY_SYNC_CONFIG points at a
        # path that does not exist.
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn(NOT_CONFIGURED_STATEMENT, r.stdout, self.output(r))
        self.assertIn("NOT CONFIGURED", r.stderr, self.output(r))
        self.assertIn(str(self.cfg_path), r.stderr, self.output(r))

    def test_require_consumers_turns_the_missing_config_into_exit_1(self):
        r = self.run_conformance("--require-consumers")
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn(NOT_CONFIGURED_STATEMENT, r.stdout, self.output(r))

    def test_a_config_with_no_conformance_key_reads_as_not_configured(self):
        self.write_config(conformance=None)
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn(NOT_CONFIGURED_STATEMENT, r.stdout, self.output(r))

    def test_an_empty_consumers_list_reads_as_not_configured(self):
        self.write_config(conformance={"consumers": []})
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn(NOT_CONFIGURED_STATEMENT, r.stdout, self.output(r))


# ---------------------------------------------------------------------------
# Group B -- configuration and operational errors
# ---------------------------------------------------------------------------
class ConfigurationAndOperationalErrorsTest(ConformanceRunTestBase):
    def test_a_consumer_without_a_path_is_a_malformed_config(self):
        self.write_config(conformance={"consumers": [{"id": "no-path"}]})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("no-path", r.stderr, self.output(r))

    def test_a_non_optional_consumer_with_a_missing_path_is_exit_2(self):
        missing = self.home / "consumers" / "does-not-exist"
        self.write_config(conformance={"consumers": [{"id": "gone", "path": str(missing)}]})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("gone", r.stderr, self.output(r))
        self.assertIn("does not exist", r.stderr, self.output(r))

    def test_an_optional_consumer_with_a_missing_path_is_reported_not_covered_not_failed(self):
        missing = self.home / "consumers" / "does-not-exist"
        self.write_config(conformance={
            "consumers": [{"id": "shy", "path": str(missing), "optional": True}],
        })
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Consumers:** 1 configured, 0 covered", r.stdout, self.output(r))
        self.assertIn("shy: not covered", r.stdout, self.output(r))

    def test_conformance_key_not_an_object_is_exit_2(self):
        self.write_config(conformance="not-an-object")
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))

    def test_consumers_not_a_list_is_exit_2(self):
        self.write_config(conformance={"consumers": {"id": "alpha"}})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))

    def test_a_consumer_entry_that_is_not_an_object_is_exit_2(self):
        self.write_config(conformance={"consumers": ["alpha"]})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))

    def test_a_consumer_missing_an_id_is_exit_2(self):
        consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"path": str(consumer)}]})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))

    def test_a_non_bool_optional_value_is_exit_2(self):
        consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(consumer), "optional": "yes"}],
        })
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("alpha", r.stderr, self.output(r))

    def test_malformed_json_is_exit_2(self):
        self.write_raw_config("{ this is not valid json")
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))

    def test_an_unknown_flag_is_exit_2(self):
        r = self.run_conformance("--totally-bogus-flag")
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("unknown option", r.stderr, self.output(r))


# ---------------------------------------------------------------------------
# Group D -- report shape
# ---------------------------------------------------------------------------
class ReportShapeTest(ConformanceRunTestBase):
    def test_every_mandatory_skeleton_line_is_present(self):
        consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(consumer)}]})
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        missing = [s for s in MANDATORY_SKELETON_SUBSTRINGS if s not in r.stdout]
        self.assertEqual([], missing, self.output(r))

    def test_every_mandatory_skeleton_line_is_present_when_not_configured(self):
        # code-reviewer note (WI-0124): the covered-consumer fixture above
        # cannot catch a skeleton line dropped only on the not-configured
        # (0 consumers) path -- that report is assembled with different
        # branches (NOT_RUN_SUFFIX, the "_none configured_" placeholder),
        # so it needs its own pin.
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        missing = [s for s in MANDATORY_SKELETON_SUBSTRINGS if s not in r.stdout]
        self.assertEqual([], missing, self.output(r))

    def test_the_exit_line_matches_the_actual_process_exit_status_when_not_configured(self):
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertEqual(r.returncode, exit_line_value(r.stdout), self.output(r))

    def test_the_exit_line_matches_the_actual_process_exit_status_under_require_consumers(self):
        r = self.run_conformance("--require-consumers")
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertEqual(r.returncode, exit_line_value(r.stdout), self.output(r))

    def test_the_exit_line_matches_the_actual_process_exit_status_with_a_covered_consumer(self):
        consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(consumer)}]})
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertEqual(r.returncode, exit_line_value(r.stdout), self.output(r))

    def test_without_show_paths_no_configured_path_substring_appears_in_stdout(self):
        consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(consumer)}]})
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("alpha: covered", r.stdout, self.output(r))
        self.assertNotIn(str(consumer), r.stdout, self.output(r))

    def test_with_show_paths_the_configured_path_substring_appears_in_stdout(self):
        consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(consumer)}]})
        r = self.run_conformance("--show-paths")
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn(str(consumer), r.stdout, self.output(r))


# ---------------------------------------------------------------------------
# --consumer <id> and --help -- named in ADR-0010's Wave 1 flag set but not
# individually enumerated in the A/B/D groups above.
# ---------------------------------------------------------------------------
class ConsumerFilterAndHelpTest(ConformanceRunTestBase):
    def test_consumer_filter_restricts_the_run_to_the_named_consumer(self):
        alpha = self.make_consumer_dir("alpha")
        beta = self.make_consumer_dir("beta")
        self.write_config(conformance={"consumers": [
            {"id": "alpha", "path": str(alpha)},
            {"id": "beta", "path": str(beta)},
        ]})
        r = self.run_conformance("--consumer", "alpha")
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Consumers:** 1 configured, 1 covered", r.stdout, self.output(r))
        self.assertIn("alpha: covered", r.stdout, self.output(r))
        self.assertNotIn("beta", r.stdout, self.output(r))

    def test_consumer_filter_on_an_unconfigured_id_is_exit_2(self):
        alpha = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(alpha)}]})
        r = self.run_conformance("--consumer", "nonexistent-id")
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("unknown consumer id", r.stderr, self.output(r))
        self.assertIn("nonexistent-id", r.stderr, self.output(r))

    def test_help_exits_0_and_shows_usage(self):
        r = self.run_conformance("--help")
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("Usage:", r.stdout, self.output(r))
        self.assertIn("--require-consumers", r.stdout, self.output(r))

    def test_an_empty_consumer_filter_is_rejected_not_silently_ignored(self):
        # code-reviewer finding (WI-0124): CONSUMER_FILTER="" doubled as both
        # "no filter given" (the unset default) and a legal-looking filter
        # value, so `--consumer ""` used to silently run EVERY configured
        # consumer instead of failing -- the exact silent scope-widening
        # ADR-0010 exists to close (KA-G-017). Two consumers configured so a
        # regression back to "ignore the empty filter" is visible as BOTH
        # showing up, not just as a wrong exit code.
        alpha = self.make_consumer_dir("alpha")
        beta = self.make_consumer_dir("beta")
        self.write_config(conformance={"consumers": [
            {"id": "alpha", "path": str(alpha)},
            {"id": "beta", "path": str(beta)},
        ]})
        r = self.run_conformance("--consumer", "")
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("--consumer", r.stderr, self.output(r))
        self.assertNotIn("alpha: covered", r.stdout, self.output(r))
        self.assertNotIn("beta: covered", r.stdout, self.output(r))


class TildeExpansionTest(ConformanceRunTestBase):
    """code-reviewer finding (WI-0124): the shipped
    templates/memory-sync.example.json documents `conformance.consumers[].path`
    with `~/...`-prefixed example paths, but nothing expanded `~` -- an
    operator copying that example literally would get a silent "path does
    not exist" (non-optional) or a silent "not covered" (optional), the
    false-clean outcome ADR-0010 exists to prevent. Established precedent
    for this exact expansion already exists in this repo (workitems.youtrack
    tokenFile, os.path.expanduser()); the config reader must follow it too.
    HOME is redirected by ConformanceRunTestBase.env(), so `~` here resolves
    to the FIXTURE home, not the real one -- expanduser() honours $HOME."""

    def test_a_tilde_prefixed_path_resolves_against_home(self):
        consumer = self.make_consumer_dir("alpha")
        rel = consumer.relative_to(self.home)
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": "~/%s" % rel.as_posix()}],
        })
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Consumers:** 1 configured, 1 covered", r.stdout, self.output(r))
        self.assertIn("alpha: covered", r.stdout, self.output(r))


if __name__ == "__main__":
    unittest.main()
