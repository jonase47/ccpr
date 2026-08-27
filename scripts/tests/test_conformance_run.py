"""test_conformance_run.py -- coverage for scripts/conformance-run.sh through
Wave 2 (WI-0124): the skeleton (Wave 1) plus the classifier (C1/C2/P).

## Why this exists

ADR-0010 (docs/adr/ADR-0010-conformance-runs-against-consumers.md) decides
that this repository's shipped checks must run against real consumer
projects as part of its own verification, not as an occasional manual
survey -- four shipped defects were found by hand on 27.08.2026 and every
one of them was structurally invisible from inside this repository's own
fixtures. Groups A/B/D (Wave 1) cover the skeleton: usage/`--help`, the
config reader, the not-configured path, consumer resolution, and the report
skeleton -- for those groups, every covered consumer gets five CLEAN default
stubs (ConformanceRunTestBase.setUp) so the classifier Wave 2 added never
produces a finding that would blur what those groups actually pin. Group C
(Wave 2) covers the classifier itself: C1 (a check's own behaviour disagrees
with what it documents about itself), C2 (zero scope over a target an
independent probe shows is non-empty), and the split between CCPR-
attributable findings (C1/C2, escalate the exit code) and consumer findings
(P, reported but never escalate). Pins (Wave 3, class C3) are not read by
this wave at all.

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

* **C** -- the classifier (Wave 2): `ClassifierContractViolationTest` pins
  the six C1 rules one at a time (exit outside the documented set, empty
  stdout AND empty stderr on a non-zero exit, a missing mandatory skeleton
  line, a self-declared `**Exit:**` disagreeing with the real one, an
  internal summary-count contradiction) plus the clean-report control;
  `ClassifierC2Test` is the discriminating pair (probe finds candidates ->
  fires; no docs at all, the WI-0121 shape -> does not);
  `ClassifierSplitProofTest` is the P/C1 separation a lazy "any finding
  fails" implementation would break; and `DocsRootAsymmetryTest` pins that
  manual-lint.sh is invoked with `<consumer>/docs`, not the bare consumer
  path.
* **Could-Not-Run (Wave 2b, WI-0124)** -- a fifth class, alongside C1/C2/P,
  for a check that exits non-zero with empty stdout and a MESSAGE on
  stderr: not C1 (a deliberate, documented refusal is not a silent death --
  measured directly: `anchor.sh status <non-git dir>` is exit 2, 0 bytes
  stdout, 166 bytes on stderr, while 5ee931b's own regression was 0 bytes
  on BOTH streams) and not P (there is no report to attribute a consumer
  finding from). `CouldNotRunClassifierTest` pins the discriminating pair
  (message on stderr -> could-not-run, not C1; both streams empty -> still
  C1 as before) plus the scope-accounting line (`**Checks:** N invoked, M
  ran, K could not`); `ProductionShapeCouldNotRunTest` runs the REAL
  (non-stub) `anchor.sh` against a real, non-git consumer directory -- the
  shape that would have bitten Wave 4's historical-checkout acceptance run.
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

# Group C (WI-0124 Wave 2): stub-check payloads. The four "Files scanned"
# checks (memory-lint, phase-docs-lint, manual-lint, doc-volume-check) share
# one clean-report shape; anchor's has no Files-scanned/Summary concept at
# all (it counts scopes, not files -- see conformance-run.sh's own
# CHECK_HAS_SUMMARY_LINE comment). Both templates carry every line the
# classifier's Rule 3 (missing-skeleton) requires, and a self-consistent
# **Exit:** 0 so a stub written verbatim, with no substitution, is a clean
# run through every rule -- exactly the "clean stub" default every test in
# this module gets unless it overrides one specific check.
CLEAN_FILES_SCANNED_REPORT = """# Fake Lint Report

**Scope:** stub
**Run:** 01.01.2026 00:00
**Files scanned:** 3

## Errors (0)

_none_

## Warnings (0)

_none_

---

**Summary:** 0 errors, 0 warnings, 0 info.
**Exit:** 0
"""

CLEAN_ANCHOR_REPORT = """# Anchor Status Report

**Project:** stub
**Run:** 01.01.2026 00:00
**Scopes found:** none
**Classification:** stub
**Last production-code commit:** none found

## Scopes

_none_

**Anchors:** 0 anchored · 0 asserted without doc change · 0 stale
**Exit:** 0 (Stage 1 — data only, never a verdict)
"""

# Filenames conformance-run.sh's own CHECK_SCRIPTS table names -- kept in
# sync by hand with that table, the same duplication the script's own
# header comment already accepts for commands/cleanup.md:143-196 (WI-0124
# Wave 2 briefing: "Your check table duplicates it ... note that in a
# comment").
CHECK_FILENAMES = (
    "memory-lint.sh",
    "phase-docs-lint.sh",
    "manual-lint.sh",
    "doc-volume-check.sh",
    "anchor.sh",
)


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
        # Group A/B/D never configure CCPR_CONFORMANCE_SCRIPT_DIR -- without
        # this default they would invoke the REAL shipped checks against a
        # bare `mkdir`ed consumer directory (no .git, no docs/), which is
        # slow, non-deterministic across this repository's own future
        # changes, and exercises Wave 2's classifier as an unplanned side
        # effect of tests that predate it and pin the SKELETON only. Every
        # test in this module gets five clean, deterministic stubs unless it
        # overwrites one via write_stub() -- Group C does exactly that,
        # reusing this same directory rather than a second one.
        self.checks_dir = self.home / "checks"
        self.checks_dir.mkdir()
        for filename in CHECK_FILENAMES:
            self.write_stub(filename, CLEAN_ANCHOR_REPORT if filename == "anchor.sh" else CLEAN_FILES_SCANNED_REPORT, 0)

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

    def write_stub(self, filename, stdout_text, exit_code, stderr_text=""):
        """Write (or overwrite) one check script in self.checks_dir. The
        stub is invoked as `bash <path> ...` by conformance-run.sh, never
        executed directly, so no shebang/chmod is load-bearing -- but both
        are set anyway to match what a real check script looks like.
        Payloads are written via a quoted heredoc (`<<'STUB_EOF'`) so a
        report containing '$' or backticks (none of the fixtures below do,
        but a future one might) is never re-interpreted by the stub's own
        shell -- same reasoning manual-lint.sh's own MEMORY.md testing note
        already gives for keeping a payload out of an unquoted context."""
        path = self.checks_dir / filename
        lines = ["#!/usr/bin/env bash"]
        if stderr_text:
            lines.append("cat <<'STUB_EOF' >&2")
            lines.append(stderr_text)
            lines.append("STUB_EOF")
        if stdout_text:
            lines.append("cat <<'STUB_EOF'")
            lines.append(stdout_text)
            lines.append("STUB_EOF")
        lines.append("exit %d" % exit_code)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path.chmod(0o755)

    def env(self, **extra):
        e = {
            "HOME": str(self.home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "MEMORY_SYNC_CONFIG": str(self.cfg_path),
            "CCPR_CONFORMANCE_SCRIPT_DIR": str(self.checks_dir),
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


# ---------------------------------------------------------------------------
# Group C (WI-0124 Wave 2) -- the classifier: C1 (contract violation), C2
# (zero scope over a non-empty target), and the P split (everything else,
# never escalating the exit code). C3 (pins) is Wave 3 and out of scope
# here; every test below configures exactly one consumer ("alpha") with
# five clean stubs (ConformanceRunTestBase.setUp) and overrides only the
# ONE check under test via write_stub() -- so a finding in the assertions
# below can only have come from the one thing each test actually changed.
# ---------------------------------------------------------------------------
class ClassifierContractViolationTest(ConformanceRunTestBase):
    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})

    def test_exit_outside_documented_set_is_c1(self):
        # memory-lint's own documented set is {0, 1, 2, 3} -- 7 is outside
        # it. The stub's own **Exit:** line is set to 7 too (self-
        # consistent) so Rule 4 (declared-vs-actual mismatch) does not ALSO
        # fire and blur which rule produced this finding.
        report = CLEAN_FILES_SCANNED_REPORT.replace("**Exit:** 0", "**Exit:** 7")
        self.write_stub("memory-lint.sh", report, 7)
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("### Contract violations (C1)", r.stdout, self.output(r))
        self.assertIn("memory-lint on alpha", r.stdout, self.output(r))
        self.assertIn("exit 7", r.stdout, self.output(r))
        # The message names the documented set, not just "wrong exit".
        self.assertIn("0 1 2 3", r.stdout, self.output(r))

    def test_nonzero_exit_with_empty_stdout_is_c1(self):
        # 5ee931b's own regression shape: "exit 1, zero bytes, no report".
        # 2 is within phase-docs-lint's documented set {0, 1, 2} -- the
        # finding here must come from the empty report, not an out-of-set
        # exit code.
        self.write_stub("phase-docs-lint.sh", "", 2)
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("### Contract violations (C1)", r.stdout, self.output(r))
        self.assertIn("phase-docs-lint on alpha", r.stdout, self.output(r))
        self.assertIn("no report", r.stdout, self.output(r))

    def test_declared_exit_disagreeing_with_actual_exit_is_c1(self):
        # The report claims **Exit:** 0 (and, consistently, 0 errors/0
        # warnings) but the process actually exits 1 -- manual-lint's
        # documented set {0, 1, 2} contains 1, so Rule 1 does not fire, and
        # every mandatory line is present, so Rule 3 does not fire either.
        self.write_stub("manual-lint.sh", CLEAN_FILES_SCANNED_REPORT, 1)
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("### Contract violations (C1)", r.stdout, self.output(r))
        self.assertIn("manual-lint on alpha", r.stdout, self.output(r))
        self.assertIn("declares **Exit:** 0", r.stdout, self.output(r))
        self.assertIn("actually exited 1", r.stdout, self.output(r))

    def test_summary_zero_errors_zero_warnings_with_nonzero_exit_is_c1(self):
        # The report's **Exit:** line agrees with the real exit (both 2) --
        # otherwise Rule 4 would fire first and this would test the wrong
        # rule -- but "0 errors, 0 warnings" contradicts a non-zero exit.
        report = CLEAN_FILES_SCANNED_REPORT.replace("**Exit:** 0", "**Exit:** 2")
        self.write_stub("doc-volume-check.sh", report, 2)
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("### Contract violations (C1)", r.stdout, self.output(r))
        self.assertIn("doc-volume-check on alpha", r.stdout, self.output(r))
        self.assertIn("0 errors, 0 warnings", r.stdout, self.output(r))
        self.assertIn("exited 2", r.stdout, self.output(r))

    def test_a_valid_clean_report_produces_no_finding_and_exits_0(self):
        # No override -- every one of the five default stubs from setUp()
        # is used verbatim. This is the control for the four tests above:
        # if THIS one were red, it would mean the classifier fires on a
        # report that violates nothing, not that the four positive tests
        # above are wrong.
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("### Contract violations (C1)", r.stdout, self.output(r))
        self.assertIn("### Zero scope (C2)", r.stdout, self.output(r))
        self.assertIn("### Consumer findings (P)", r.stdout, self.output(r))
        self.assertNotIn("alpha", r.stdout.split("### Contract violations (C1)", 1)[1].split("### Zero scope (C2)", 1)[0])


class ClassifierC2Test(ConformanceRunTestBase):
    """The discriminating pair (WI-0124 Wave 2 briefing): C2 must fire when
    a check reports zero scope AND the independent probe finds real
    candidates, and must NOT fire when the probe finds nothing -- that
    second half is the WI-0121 reference case (docs/workitems/WI-0121.md):
    phase-docs-lint over a consumer with none of the nine phase folders
    reports Files scanned: 0, exit 0, and that zero is legitimate."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})

    def test_c2_fires_when_the_probe_finds_candidates_the_check_missed(self):
        (self.consumer / "docs" / "architecture").mkdir(parents=True)
        for n in range(3):
            (self.consumer / "docs" / "architecture" / ("doc%d.md" % n)).write_text("# doc\n")
        self.write_stub("phase-docs-lint.sh", CLEAN_FILES_SCANNED_REPORT.replace("**Files scanned:** 3", "**Files scanned:** 0"), 0)
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("### Zero scope (C2)", r.stdout, self.output(r))
        self.assertIn("phase-docs-lint on alpha", r.stdout, self.output(r))
        self.assertIn("Files scanned: 0", r.stdout, self.output(r))

    def test_c2_does_not_fire_when_the_consumer_has_no_docs_at_all(self):
        # No docs/ subtree at all under the consumer -- the WI-0121 shape.
        self.write_stub("phase-docs-lint.sh", CLEAN_FILES_SCANNED_REPORT.replace("**Files scanned:** 3", "**Files scanned:** 0"), 0)
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("### Zero scope (C2)", r.stdout, self.output(r))
        self.assertNotIn("phase-docs-lint on alpha", r.stdout, self.output(r))


class ClassifierSplitProofTest(ConformanceRunTestBase):
    """A lazy 'any finding fails' implementation would pass every test
    above but fail here: P-class findings must never escalate the exit
    code, and a run mixing a P and a C1 finding must still list them under
    different headings (ADR-0010 decision 2)."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})

    def test_mixed_p_and_c1_findings_exit_1_under_separate_headings(self):
        # C1: exit outside the documented set.
        c1_report = CLEAN_FILES_SCANNED_REPORT.replace("**Exit:** 0", "**Exit:** 9")
        self.write_stub("manual-lint.sh", c1_report, 9)
        # P: a legitimate, self-consistent "1 warning" finding -- 1 is
        # within phase-docs-lint's documented set, the Exit line agrees
        # with the real exit, and 0 errors/1 warning is not a contradiction.
        p_report = CLEAN_FILES_SCANNED_REPORT.replace(
            "**Summary:** 0 errors, 0 warnings, 0 info.", "**Summary:** 0 errors, 1 warnings, 0 info."
        ).replace("**Exit:** 0", "**Exit:** 1")
        self.write_stub("phase-docs-lint.sh", p_report, 1)

        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        c1_section = r.stdout.split("### Contract violations (C1)", 1)[1].split("### Zero scope (C2)", 1)[0]
        p_section = r.stdout.split("### Consumer findings (P)", 1)[1]
        self.assertIn("manual-lint on alpha", c1_section, self.output(r))
        self.assertNotIn("phase-docs-lint", c1_section, self.output(r))
        self.assertIn("phase-docs-lint on alpha", p_section, self.output(r))
        self.assertNotIn("manual-lint", p_section, self.output(r))

    def test_only_p_findings_exit_0(self):
        p_report = CLEAN_FILES_SCANNED_REPORT.replace(
            "**Summary:** 0 errors, 0 warnings, 0 info.", "**Summary:** 0 errors, 1 warnings, 0 info."
        ).replace("**Exit:** 0", "**Exit:** 1")
        self.write_stub("doc-volume-check.sh", p_report, 1)

        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("doc-volume-check on alpha", r.stdout, self.output(r))
        p_section = r.stdout.split("### Consumer findings (P)", 1)[1]
        self.assertIn("doc-volume-check on alpha", p_section, self.output(r))


class DocsRootAsymmetryTest(ConformanceRunTestBase):
    """WI-0124 Wave 2 briefing: manual-lint.sh and doc-volume-check.sh are
    GENERIC over any root and must be invoked with <consumer>/docs, not the
    bare consumer path -- getting this wrong silently turns a populated
    consumer into a Files-scanned:-0 run, which C2 would then report as a
    CCPR defect that is actually our own argument mistake. This stub
    distinguishes the two: it reports real content when its OWN first
    argument ends in "/docs", and a false zero-scope report otherwise -- so
    a regression back to passing the bare project dir flips this test from
    green (exit 0) to red (a spurious C2 finding), without needing the real
    manual-lint.sh's own scanning logic at all."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        docs = self.consumer / "docs"
        docs.mkdir()
        (docs / "readme.md").write_text("# readme\n")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})

    def test_manual_lint_is_invoked_with_the_docs_suffixed_path(self):
        stub = "\n".join([
            "#!/usr/bin/env bash",
            'case "$1" in',
            '  */docs)',
            '    cat <<STUB_EOF',
            CLEAN_FILES_SCANNED_REPORT.rstrip("\n"),
            'STUB_EOF',
            '    exit 0',
            '    ;;',
            '  *)',
            '    cat <<STUB_EOF',
            CLEAN_FILES_SCANNED_REPORT.replace("**Files scanned:** 3", "**Files scanned:** 0").rstrip("\n"),
            'STUB_EOF',
            '    exit 0',
            '    ;;',
            'esac',
        ])
        (self.checks_dir / "manual-lint.sh").write_text(stub + "\n", encoding="utf-8")
        (self.checks_dir / "manual-lint.sh").chmod(0o755)

        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("### Zero scope (C2)", r.stdout, self.output(r))
        self.assertNotIn("manual-lint on alpha", r.stdout, self.output(r))


class CouldNotRunClassifierTest(ConformanceRunTestBase):
    """WI-0124 Wave 2b -- the discriminating pair the briefing names: a
    non-zero exit with empty stdout and a MESSAGE on stderr is could-not-
    run, not C1; the same shape with an EMPTY stderr too is still C1 (rule
    2, unchanged in effect, tightened in condition). Neither half proves
    anything alone -- a classifier that folded both into one class, or that
    dropped the stderr condition from rule 2 entirely, would pass only one
    of the two tests below."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})

    def test_message_on_stderr_with_empty_stdout_is_could_not_run_not_c1(self):
        # 2 is within anchor's own documented exit set {0, 2, 3}, so Rule 1
        # does not fire -- the finding, if any, must come from the
        # could-not-run classification itself.
        self.write_stub("anchor.sh", "", 2, stderr_text="anchor: not a git repository (or git not on PATH): /fake/path")
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        could_not_run_section = r.stdout.split("### Could Not Run", 1)[1].split("### Consumer findings (P)", 1)[0]
        c1_section = r.stdout.split("### Contract violations (C1)", 1)[1].split("### Zero scope (C2)", 1)[0]
        self.assertIn("anchor on alpha", could_not_run_section, self.output(r))
        self.assertIn("not a git repository", could_not_run_section, self.output(r))
        self.assertNotIn("anchor", c1_section, self.output(r))
        # Could-not-run does not escalate the exit code on its own (the
        # check behaved exactly as it documents itself) -- but it IS
        # visible in the scope-accounting line so it can never be missed.
        self.assertIn("**Checks:** 5 invoked, 4 ran, 1 could not", r.stdout, self.output(r))
        self.assertIn("1 could-not-run", r.stdout, self.output(r))

    def test_empty_stdout_and_empty_stderr_is_still_c1(self):
        # Same non-zero exit, same empty stdout, but NO stderr message at
        # all -- 5ee931b's own regression shape (a silent die()-before-
        # first-echo death, silent on BOTH streams). 1 is within manual-
        # lint's documented set {0, 1, 2}.
        self.write_stub("manual-lint.sh", "", 1)
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        c1_section = r.stdout.split("### Contract violations (C1)", 1)[1].split("### Zero scope (C2)", 1)[0]
        could_not_run_section = r.stdout.split("### Could Not Run", 1)[1].split("### Consumer findings (P)", 1)[0]
        self.assertIn("manual-lint on alpha", c1_section, self.output(r))
        self.assertIn("empty stdout and empty stderr", c1_section, self.output(r))
        self.assertNotIn("manual-lint", could_not_run_section, self.output(r))
        self.assertIn("**Checks:** 5 invoked, 5 ran, 0 could not", r.stdout, self.output(r))


class ProductionShapeCouldNotRunTest(ConformanceRunTestBase):
    """WI-0124 Wave 2b -- the production shape, not a stub: the REAL
    anchor.sh (CCPR_CONFORMANCE_SCRIPT_DIR pointed at this repository's own
    scripts/ directory, overriding ConformanceRunTestBase's clean-stub
    default) run against a consumer that is a genuine directory but not a
    git repository. This is the exact case that would have bitten Wave 4's
    historical-checkout acceptance run (the WI-0124 Wave 2b briefing names
    it explicitly). The consumer's docs/ is present but EMPTY (not absent)
    -- measured by hand before writing this test: with docs/ entirely
    absent, phase-docs-lint.sh takes an early one-line short-circuit with
    no report skeleton at all, which would itself misfire as an unrelated
    C1 finding and blur what this test pins; with docs/ present and empty,
    all four of the other real checks take their normal, full-skeleton,
    zero-scope path (memory-lint, phase-docs-lint, manual-lint,
    doc-volume-check all exit 0 with "Files scanned: 0" and no candidates
    for the C2 probe to find) -- only anchor.sh's own could-not-run finding
    should appear."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        (self.consumer / "docs").mkdir()
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})

    def test_a_non_git_consumer_directory_is_could_not_run_not_c1(self):
        real_scripts_dir = REPO_ROOT / "scripts"
        r = self.run_conformance(CCPR_CONFORMANCE_SCRIPT_DIR=str(real_scripts_dir))
        self.assertEqual(0, r.returncode, self.output(r))
        could_not_run_section = r.stdout.split("### Could Not Run", 1)[1].split("### Consumer findings (P)", 1)[0]
        c1_section = r.stdout.split("### Contract violations (C1)", 1)[1].split("### Zero scope (C2)", 1)[0]
        c2_section = r.stdout.split("### Zero scope (C2)", 1)[1].split("### Could Not Run", 1)[0]
        self.assertIn("anchor on alpha", could_not_run_section, self.output(r))
        self.assertIn("not a git repository", could_not_run_section, self.output(r))
        self.assertNotIn("anchor", c1_section, self.output(r))
        self.assertIn("_none_", c1_section, self.output(r))
        self.assertIn("_none_", c2_section, self.output(r))
        self.assertIn("**Checks:** 5 invoked, 4 ran, 1 could not", r.stdout, self.output(r))


if __name__ == "__main__":
    unittest.main()
