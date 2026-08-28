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
import os
import re
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
        # WI-0126 tranche 5: was a hand-typed CHECK_FILENAMES tuple "kept in
        # sync by hand" with conformance-run.sh's own CHECK_SCRIPTS array --
        # now a direct binding against parse_full_check_table()'s own
        # CHECK_SCRIPTS column (parsed from source, defined further down in
        # this module; available by the time setUp() actually runs). The
        # count/alignment pin already lives in CheckTableAlignmentTest
        # (5 entries, 7 columns) -- no redundant pin added here.
        for filename in parse_full_check_table()["CHECK_SCRIPTS"]:
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

    def run_conformance(self, *args, script_path=None, cwd=None, **extra_env):
        # script_path/cwd (WI-0126 tranche 4): every existing call site
        # omits both and keeps this method's original behaviour unchanged
        # (SCRIPT_PATH, inherited cwd) -- the two new kwargs exist only for
        # the CHECK_* column transposition/red-proof tests, which must run
        # a SCRATCH-mutated copy of conformance-run.sh (never the shipped
        # file) and, for one of them, a specific cwd so a relative
        # PROJECT_DIR fallback resolves deterministically.
        return subprocess.run(
            ["bash", str(script_path or SCRIPT_PATH), *[str(a) for a in args]],
            capture_output=True, text=True, env=self.env(**extra_env),
            cwd=str(cwd) if cwd else None,
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


# ---------------------------------------------------------------------------
# Group C3 (WI-0124 Wave 3) -- pins: a concrete, dated, per-consumer
# expectation (ADR-0010 decision 2, class C3) that is either expectFinding
# (a substring, or a POSIX ERE when regex: true, that must appear on at
# least minCount report lines -- default 1) or expectField (one of
# exit/errors/warnings/info/filesScanned (Wave 4: anchors.stale and
# anchors.maxBehind were removed -- both described the CONSUMER's own
# working state, never CCPR behaviour, so neither is a valid C3 subject),
# compared against value -- filesScanned is a floor (>=), every other
# field is exact equality). Every pin MUST carry a non-empty why -- its
# absence, an unknown check, an unconfigured consumer id, neither/both of
# expectFinding|expectField, or an unknown expectField name are all
# malformed config (exit 2), the same "refuse to run rather than guess"
# discipline the consumers reader already applies (ADR-0010 §5's
# deliberate divergence from _gate_read_config). A violated pin is C3 and
# escalates the exit status;
# a pin whose own check produced no report this run (could-not-run, or
# the rarer empty-both-streams C1 shape) is NOT EVALUATED -- reported
# under its own heading, never silently counted as satisfied (WI-0124
# Wave 3 briefing: "the one most likely to be got wrong").
# ---------------------------------------------------------------------------
def c3_section(stdout):
    return stdout.split("### Pinned expectations (C3)", 1)[1].split("### Pins Not Evaluated", 1)[0]


def not_evaluated_section(stdout):
    return stdout.split("### Pins Not Evaluated", 1)[1].split("### Consumer findings (P)", 1)[0]


class PinConfigValidationTest(ConformanceRunTestBase):
    """The four config-error shapes the WI-0124 Wave 3 briefing names
    explicitly, plus one defensive extra (both expectFinding AND
    expectField given -- ambiguous, so refused rather than guessed at,
    same reasoning as "neither")."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")

    def _configure(self, pin):
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer)}],
            "pins": [pin],
        })

    def test_pin_without_why_is_exit_2(self):
        self._configure({"consumer": "alpha", "check": "memory-lint", "expectField": "exit", "value": 0})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("why", r.stderr, self.output(r))

    def test_pin_naming_unknown_check_is_exit_2(self):
        self._configure({"consumer": "alpha", "check": "not-a-real-check", "expectField": "exit", "value": 0, "why": "x"})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("not-a-real-check", r.stderr, self.output(r))

    def test_pin_with_neither_expectation_is_exit_2(self):
        self._configure({"consumer": "alpha", "check": "memory-lint", "why": "x"})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("expectFinding", r.stderr, self.output(r))
        self.assertIn("expectField", r.stderr, self.output(r))

    def test_pin_with_both_expectations_is_exit_2(self):
        self._configure({
            "consumer": "alpha", "check": "memory-lint",
            "expectFinding": "x", "expectField": "exit", "value": 0, "why": "x",
        })
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))

    def test_pin_expectfield_unknown_name_is_exit_2(self):
        self._configure({"consumer": "alpha", "check": "memory-lint", "expectField": "commitSha", "value": 1, "why": "x"})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("commitSha", r.stderr, self.output(r))

    def test_pin_expectfield_anchors_stale_is_unknown_field_is_exit_2(self):
        # WI-0124 Wave 4: anchors.stale/anchors.maxBehind were removed --
        # both describe the CONSUMER's own working state (how far its
        # checked-out docs trail its production code), not CCPR behaviour,
        # so they can never be a valid C3 subject (ADR-0010 decision 2).
        # Same shape as the generic unknown-field test above, kept
        # separate (paired with the anchors.maxBehind twin below) so a
        # future regression that reintroduces one of these two specific
        # names by accident is caught by name, not folded into "some
        # unknown field or other".
        self._configure({"consumer": "alpha", "check": "anchor", "expectField": "anchors.stale", "value": 0, "why": "x"})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("anchors.stale", r.stderr, self.output(r))

    def test_pin_expectfield_anchors_maxbehind_is_unknown_field_is_exit_2(self):
        # Twin of the anchors.stale test above (code-reviewer finding,
        # WI-0124 Wave 4: the pair's own stated purpose -- catching a
        # regression that reintroduces "one of these two specific names"
        # -- only held for anchors.stale until this test existed; a
        # regression that reintroduced ONLY anchors.maxBehind would have
        # passed the suite green without it).
        self._configure({"consumer": "alpha", "check": "anchor", "expectField": "anchors.maxBehind", "value": 0, "why": "x"})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("anchors.maxBehind", r.stderr, self.output(r))

    def test_pin_naming_unknown_consumer_id_is_exit_2(self):
        # A pin's `consumer` field naming an id that was never configured
        # (a typo, most likely) can never be evaluated -- the operator
        # wrote an expectation this run can never check. That is a
        # config error (refuse to run), not a runtime could-not-run
        # condition (which only applies to a CONFIGURED consumer whose
        # check declined to run against it this time).
        self._configure({"consumer": "not-configured", "check": "memory-lint", "expectField": "exit", "value": 0, "why": "x"})
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("not-configured", r.stderr, self.output(r))

    def test_pin_naming_unknown_consumer_id_among_several_configured_is_exit_2(self):
        # Code-reviewer note (WI-0124 Wave 4): the single-consumer fixture
        # above never exercises the error message's own
        # ", ".join(sorted(consumer_ids)) formatting with more than one
        # element -- this fixture configures three real consumers and
        # pins a fourth, nonexistent id, so the message an operator
        # actually sees is proven against a realistic multi-consumer
        # shape, not just the degenerate single-consumer case.
        self.write_config(conformance={
            "consumers": [
                {"id": "alpha", "path": str(self.consumer)},
                {"id": "beta", "path": str(self.consumer)},
                {"id": "gamma", "path": str(self.consumer)},
            ],
            "pins": [{"consumer": "delta", "check": "memory-lint", "expectField": "exit", "value": 0, "why": "x"}],
        })
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("delta", r.stderr, self.output(r))
        for known in ("alpha", "beta", "gamma"):
            self.assertIn(known, r.stderr, self.output(r))


class PinFindingEvaluationTest(ConformanceRunTestBase):
    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")

    def _configure(self, pin):
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer)}],
            "pins": [pin],
        })

    def test_substring_satisfied(self):
        self._configure({
            "consumer": "alpha", "check": "memory-lint",
            "expectFinding": "0 errors, 0 warnings", "why": "control fixture stays clean",
        })
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Pins:** 1 checked, 1 satisfied", r.stdout, self.output(r))
        self.assertIn("_none_", c3_section(r.stdout), self.output(r))

    def test_substring_violated(self):
        self._configure({
            "consumer": "alpha", "check": "memory-lint",
            "expectFinding": "this text never appears in the stub report",
            "why": "invented to prove the negative path",
        })
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("**Pins:** 1 checked, 0 satisfied", r.stdout, self.output(r))
        self.assertIn("pin violated", c3_section(r.stdout), self.output(r))
        self.assertIn("invented to prove the negative path", c3_section(r.stdout), self.output(r))

    def test_mincount_not_met_is_violated(self):
        # CLEAN_FILES_SCANNED_REPORT's "## Errors (0)" heading appears
        # exactly once -- a minCount of 2 can never be satisfied by it.
        self._configure({
            "consumer": "alpha", "check": "memory-lint",
            "expectFinding": "## Errors (0)", "minCount": 2,
            "why": "deliberately unsatisfiable minCount",
        })
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("pin violated", c3_section(r.stdout), self.output(r))

    def test_regex_satisfied(self):
        self._configure({
            "consumer": "alpha", "check": "memory-lint",
            "expectFinding": r"^\*\*Files scanned:\*\* [0-9]+$", "regex": True,
            "why": "the files-scanned line must stay a bare integer",
        })
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Pins:** 1 checked, 1 satisfied", r.stdout, self.output(r))

    def test_regex_violated(self):
        self._configure({
            "consumer": "alpha", "check": "memory-lint",
            "expectFinding": r"^\*\*Files scanned:\*\* [a-z]+$", "regex": True,
            "why": "invented -- the stub's own count is numeric, never alphabetic",
        })
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("pin violated", c3_section(r.stdout), self.output(r))


class PinFieldEvaluationTest(ConformanceRunTestBase):
    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")

    def _configure(self, pin):
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer)}],
            "pins": [pin],
        })

    def test_exit_field_satisfied(self):
        self._configure({"consumer": "alpha", "check": "memory-lint", "expectField": "exit", "value": 0, "why": "control stays exit 0"})
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Pins:** 1 checked, 1 satisfied", r.stdout, self.output(r))

    def test_exit_field_violated(self):
        self._configure({"consumer": "alpha", "check": "memory-lint", "expectField": "exit", "value": 7, "why": "invented -- the stub actually exits 0"})
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("pin violated", c3_section(r.stdout), self.output(r))

    def test_errors_field_satisfied(self):
        self._configure({"consumer": "alpha", "check": "memory-lint", "expectField": "errors", "value": 0, "why": "control stays clean"})
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Pins:** 1 checked, 1 satisfied", r.stdout, self.output(r))

    def test_warnings_field_violated(self):
        report = CLEAN_FILES_SCANNED_REPORT.replace(
            "**Summary:** 0 errors, 0 warnings, 0 info.", "**Summary:** 0 errors, 2 warnings, 0 info."
        ).replace("**Exit:** 0", "**Exit:** 1")
        self.write_stub("phase-docs-lint.sh", report, 1)
        self._configure({"consumer": "alpha", "check": "phase-docs-lint", "expectField": "warnings", "value": 0, "why": "invented -- the stub actually reports 2"})
        r = self.run_conformance()
        self.assertIn("pin violated", c3_section(r.stdout), self.output(r))

    def test_info_field_satisfied(self):
        report = CLEAN_FILES_SCANNED_REPORT.replace(
            "**Summary:** 0 errors, 0 warnings, 0 info.", "**Summary:** 0 errors, 0 warnings, 4 info."
        )
        self.write_stub("doc-volume-check.sh", report, 0)
        self._configure({"consumer": "alpha", "check": "doc-volume-check", "expectField": "info", "value": 4, "why": "control"})
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Pins:** 1 checked, 1 satisfied", r.stdout, self.output(r))

    def test_filesscanned_ge_satisfied_by_a_growing_consumer(self):
        # value 2 <= the stub's own "**Files scanned:** 3" -- a floor, not
        # an equality, so a growing consumer only strengthens this pin.
        self._configure({"consumer": "alpha", "check": "memory-lint", "expectField": "filesScanned", "value": 2, "why": "at least 2 files must always exist"})
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Pins:** 1 checked, 1 satisfied", r.stdout, self.output(r))

    def test_filesscanned_ge_violated(self):
        self._configure({"consumer": "alpha", "check": "memory-lint", "expectField": "filesScanned", "value": 10, "why": "invented -- the stub only reports 3"})
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("pin violated", c3_section(r.stdout), self.output(r))

class PinCouldNotRunInteractionTest(ConformanceRunTestBase):
    """WI-0124 Wave 3 briefing: 'A pin that is not evaluated at all because
    its check could-not-run must be reported as such, not silently
    counted as satisfied. That last case is the one most likely to be got
    wrong; give it its own test.' Two tests, deliberately paired: the
    could-not-run pin must land in Pins Not Evaluated and must NOT count
    toward PINS_SATISFIED, while an ordinary satisfied pin on a DIFFERENT,
    cleanly-running check in the SAME run stays green -- proving the
    not-evaluated handling does not blanket-suppress every pin in the run."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        self.write_stub("anchor.sh", "", 2, stderr_text="anchor: not a git repository (or git not on PATH): /fake/path")
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer)}],
            "pins": [
                {"consumer": "alpha", "check": "anchor", "expectField": "errors", "value": 0, "why": "cannot be evaluated -- anchor could not run"},
                {"consumer": "alpha", "check": "memory-lint", "expectField": "exit", "value": 0, "why": "control -- memory-lint's stub runs cleanly"},
            ],
        })

    def test_could_not_run_pin_is_not_evaluated_not_satisfied(self):
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Pins:** 2 checked, 1 satisfied", r.stdout, self.output(r))
        self.assertIn("anchor on alpha", not_evaluated_section(r.stdout), self.output(r))
        self.assertNotIn("anchor on alpha", c3_section(r.stdout), self.output(r))

    def test_ordinary_satisfied_pin_on_a_different_check_stays_green(self):
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertNotIn("memory-lint on alpha", not_evaluated_section(r.stdout), self.output(r))
        self.assertIn("_none_", c3_section(r.stdout), self.output(r))


class PinReportAndExitTest(ConformanceRunTestBase):
    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")

    def test_mixed_satisfied_and_violated_pins_counts_and_why_placement(self):
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer)}],
            "pins": [
                {"consumer": "alpha", "check": "memory-lint", "expectField": "exit", "value": 0, "why": "control stays exit 0"},
                {"consumer": "alpha", "check": "phase-docs-lint", "expectField": "exit", "value": 9, "why": "a reason unique enough to grep for -- WHY-MARKER-42"},
            ],
        })
        r = self.run_conformance()
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("**Pins:** 2 checked, 1 satisfied", r.stdout, self.output(r))
        c3 = c3_section(r.stdout)
        self.assertIn("phase-docs-lint on alpha", c3, self.output(r))
        self.assertIn("WHY-MARKER-42", c3, self.output(r))
        violated_line = [line for line in c3.splitlines() if "phase-docs-lint on alpha" in line][0]
        self.assertIn("WHY-MARKER-42", violated_line, self.output(r))

    def test_a_satisfied_only_run_stays_exit_0(self):
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer)}],
            "pins": [{"consumer": "alpha", "check": "memory-lint", "expectField": "exit", "value": 0, "why": "control"}],
        })
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Pins:** 1 checked, 1 satisfied", r.stdout, self.output(r))

    def test_zero_pins_configured_reports_zero_checked(self):
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Pins:** 0 checked, 0 satisfied", r.stdout, self.output(r))


# ---------------------------------------------------------------------------
# Group H (WI-0124 Wave 4b) -- unknown-key rejection. Measured directly
# (hand-written config, 27.08.2026): nesting `pins` INSIDE a consumer object
# instead of at `conformance.pins[]` produced "**Pins:** 0 checked, 0
# satisfied", exit 0 -- a clean pass, silently discarding every expectation
# the operator wrote. That is the run's own failure mode one level down from
# what ADR-0010 decision 5 already closes for a malformed config as a whole
# (unknown scope -> exit 2): an unknown key at any of the three config
# levels (conformance / consumer / pin) must refuse to run rather than be
# silently ignored, the same "refuse rather than guess" discipline the
# reader already applies to every other malformed shape. `_comment` is the
# one deliberate exception -- the shipped template
# (templates/memory-sync.example.json) uses it as its own documentation
# mechanism at all three levels, so rejecting it would refuse this
# repository's own example.
# ---------------------------------------------------------------------------
class UnknownKeyRejectionTest(ConformanceRunTestBase):
    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")

    def test_pins_nested_inside_a_consumer_is_exit_2_and_names_pins_and_the_consumer(self):
        # The exact hand-written mistake this wave was found by: `pins`
        # belongs at conformance.pins[], not inside a consumer object.
        self.write_config(conformance={
            "consumers": [{
                "id": "consumer-a",
                "path": str(self.consumer),
                "pins": [{"check": "phase-docs-lint", "expectFinding": "x", "why": "y"}],
            }],
        })
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("pins", r.stderr, self.output(r))
        self.assertIn("consumer-a", r.stderr, self.output(r))

    def test_unknown_key_at_the_conformance_level_is_exit_2_and_names_the_key(self):
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer)}],
            "bogusTopLevelKey": True,
        })
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("bogusTopLevelKey", r.stderr, self.output(r))

    def test_unknown_key_inside_a_consumer_is_exit_2_and_names_the_key(self):
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer), "bogusConsumerKey": 1}],
        })
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("bogusConsumerKey", r.stderr, self.output(r))
        self.assertIn("alpha", r.stderr, self.output(r))

    def test_unknown_key_inside_a_pin_is_exit_2_and_names_the_key(self):
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer)}],
            "pins": [{
                "consumer": "alpha", "check": "memory-lint",
                "expectField": "exit", "value": 0, "why": "x",
                "bogusPinKey": 1,
            }],
        })
        r = self.run_conformance()
        self.assertEqual(2, r.returncode, self.output(r))
        self.assertIn("malformed conformance config", r.stderr, self.output(r))
        self.assertIn("bogusPinKey", r.stderr, self.output(r))
        self.assertIn("alpha", r.stderr, self.output(r))

    def test_comment_key_is_accepted_at_the_conformance_level(self):
        self.write_config(conformance={
            "_comment": "documentation only",
            "consumers": [{"id": "alpha", "path": str(self.consumer)}],
        })
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("alpha: covered", r.stdout, self.output(r))

    def test_comment_key_is_accepted_inside_a_consumer(self):
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer), "_comment": "documentation only"}],
        })
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("alpha: covered", r.stdout, self.output(r))

    def test_comment_key_is_accepted_inside_a_pin(self):
        self.write_config(conformance={
            "consumers": [{"id": "alpha", "path": str(self.consumer)}],
            "pins": [{
                "consumer": "alpha", "check": "memory-lint",
                "expectField": "exit", "value": 0, "why": "x",
                "_comment": "documentation only",
            }],
        })
        r = self.run_conformance()
        self.assertEqual(0, r.returncode, self.output(r))
        self.assertIn("**Pins:** 1 checked, 1 satisfied", r.stdout, self.output(r))

    def test_shipped_example_template_produces_no_unknown_key_error(self):
        # Binding test (same idea as Group F/G): the rule enforced above and
        # the shipped example (templates/memory-sync.example.json, which
        # documents this schema for real operators) must never drift apart.
        # Consumer paths are rewritten to real fixture directories -- the
        # template's own `~/path/to/...` values are documentation, not meant
        # to resolve on any machine -- everything else (including every
        # `_comment` and both pins) is passed through verbatim.
        template_path = REPO_ROOT / "templates" / "memory-sync.example.json"
        template_conformance = json.loads(template_path.read_text(encoding="utf-8"))["conformance"]
        for c in template_conformance["consumers"]:
            c["path"] = str(self.make_consumer_dir(c["id"]))
        self.write_config(conformance=template_conformance)
        r = self.run_conformance()
        self.assertNotIn("unknown key", r.stderr, self.output(r))
        self.assertNotIn("malformed conformance config", r.stderr, self.output(r))


# ---------------------------------------------------------------------------
# Group E (WI-0124 Wave 3) -- the contract table stays honest: every
# CHECK_EXIT_SET entry conformance-run.sh's own table declares for a check
# must match what that check's OWN shipped header documents about itself,
# read directly from the file -- never from the table under test. A
# drifted table (a wording change, a widened/narrowed exit set in either
# file) fails HERE, locally, instead of surfacing as a C1 false positive
# against a real consumer months later. The companion class below runs
# each REAL check over a tiny synthetic fixture and pins the mandatory
# report-skeleton lines the classifier's own Rule 3 depends on.
# ---------------------------------------------------------------------------
EXIT_CODES_LINE_RE = re.compile(r"#\s*Exit[- ]Codes?:\s*(.+)", re.IGNORECASE)
BULLETED_EXIT_RE = re.compile(r"^#\s+(\d+)\s+\S")


def parse_documented_exit_set(script_path):
    """The set of exit codes a shipped check's OWN header comment documents
    for itself -- either the single "# Exit codes: 0 clean, 1 warnings,
    ..." line four of the five checks carry (memory-lint.sh's own spelling
    is lowercase "Exit codes:", the other three "Exit-Codes:" -- both
    matched, case-insensitively, by one regex), or, for scripts/anchor.sh,
    the bulleted "#   <code>  <meaning>" block under its own "Exit-code
    contract" heading (scripts/anchor.sh:18-36) -- the two documented
    shapes this repository's five shipped checks actually use. Scanning
    stops at the first non-comment, non-blank line, so nothing outside
    the header (dates, ports, unrelated integers) can leak in."""
    codes = set()
    lines = script_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if not line.startswith("#") and line.strip():
            break
        m = EXIT_CODES_LINE_RE.search(line)
        if m:
            codes.update(int(n) for n in re.findall(r"(\d+)\s+[A-Za-z]", m.group(1)))
    if codes:
        return codes
    for line in lines:
        if not line.startswith("#") and line.strip():
            break
        m = BULLETED_EXIT_RE.match(line)
        if m:
            codes.add(int(m.group(1)))
    return codes


def _parse_paren_array(name, text):
    """Parses one NAME=(...) parenthesized array literal out of shell
    source text, accepting either a bare or a double-quoted token per
    element -- conformance-run.sh's own CHECK_EXIT_SET quotes its elements
    because each one is itself a space-separated set ("0 1 2 3"), while
    every other CHECK_* column is bare, so both forms must be read from the
    same helper rather than assuming one shape. Module-level (WI-0126
    tranche 4) so every CHECK_* column can share it, generalising what used
    to be parse_check_exit_set_table's own private nested _array()."""
    m = re.search(r"^%s=\(([^)]*)\)" % re.escape(name), text, re.MULTILINE)
    assert m is not None, "conformance-run.sh's own %s array not found -- fixture assumption broken" % name
    return [quoted if quoted else bare for quoted, bare in re.findall(r'"([^"]*)"|(\S+)', m.group(1))]


def parse_check_exit_set_table(script_path):
    """conformance-run.sh's own CHECK_NAMES / CHECK_SCRIPTS / CHECK_EXIT_SET
    parallel-array table, read by parsing the shell source directly --
    deliberately not by sourcing the script, which would require invoking
    bash for nothing else this parser needs."""
    text = script_path.read_text(encoding="utf-8")
    names = _parse_paren_array("CHECK_NAMES", text)
    scripts = _parse_paren_array("CHECK_SCRIPTS", text)
    exit_sets = _parse_paren_array("CHECK_EXIT_SET", text)
    assert len(names) == len(scripts) == len(exit_sets), "conformance-run.sh's check-table arrays disagree on length"
    return {name: (scripts[i], set(int(c) for c in exit_sets[i].split())) for i, name in enumerate(names)}


def _table_header_mismatches(table_source_path):
    table = parse_check_exit_set_table(table_source_path)
    mismatches = []
    for name, (script_filename, table_set) in table.items():
        header_set = parse_documented_exit_set(REPO_ROOT / "scripts" / script_filename)
        if header_set != table_set:
            mismatches.append("%s: table says %s, header says %s" % (name, sorted(table_set), sorted(header_set)))
    return mismatches


class ContractTableExitCodeBindingTest(unittest.TestCase):
    def test_every_checks_documented_exit_set_matches_its_own_header(self):
        self.assertEqual([], _table_header_mismatches(SCRIPT_PATH))


class ContractTableExitCodeBindingRedProofTest(unittest.TestCase):
    """Mutation-based RED proof (WI-0037/WI-0044 precedent: a checker of
    this kind is untrustworthy until it has been SEEN red). Drops '3' from
    memory-lint's own CHECK_EXIT_SET entry in a SCRATCH copy of
    conformance-run.sh (the shipped file is never touched) and confirms
    the binding test above goes red, naming memory-lint -- proving Group E
    binds the table to the headers, not merely to itself."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wi0124-redproof-groupE-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_a_narrowed_table_entry_is_caught(self):
        before = SCRIPT_PATH.read_bytes()
        before_mode = SCRIPT_PATH.stat().st_mode
        original = before.decode()
        needle = 'CHECK_EXIT_SET=("0 1 2 3" "0 1 2" "0 1 2" "0 1 2" "0 2 3")'
        self.assertIn(needle, original, "fixture assumption broken -- CHECK_EXIT_SET's own literal line changed, update this test")
        mutated = original.replace(needle, needle.replace('"0 1 2 3"', '"0 1 2"'), 1)
        self.assertNotEqual(original, mutated)
        scratch = self.tmpdir / "conformance-run.sh"
        scratch.write_text(mutated, encoding="utf-8")

        mismatches = _table_header_mismatches(scratch)
        self.assertTrue(
            any(m.startswith("memory-lint:") for m in mismatches),
            "expected the narrowed memory-lint entry to be flagged: %r" % mismatches,
        )

        self.assertEqual(before, SCRIPT_PATH.read_bytes(), "shipped file content changed")
        self.assertEqual(before_mode, SCRIPT_PATH.stat().st_mode, "shipped file mode bits changed")


# WI-0126: PHASE_FOLDER_NAMES (this script, :206) is a verbatim duplicate of
# phase-docs-lint.sh's own PHASE_FOLDERS (scripts/phase-docs-lint.sh:61) --
# deliberately NOT sourced (see this script's own comment directly above
# PHASE_FOLDER_NAMES: the C2 probe must stay independent of the check it is
# probing, ADR-0010 decision 2). Nothing today notices if the two drift
# apart. Parsed from source on both sides, never retyped, following
# test_frontmatter_examples_match_the_lint.py's _read_enum precedent.
PHASE_DOCS_LINT_SCRIPT = REPO_ROOT / "scripts" / "phase-docs-lint.sh"


def _read_bare_array(text, varname):
    """Parses NAME=(bare word1 word2 ...) out of shell source text -- a
    single-line, unquoted bash array (bash 3.2 floor: plain positional
    arrays only, no associative arrays). Fails loudly if the shape changes
    underneath this test rather than silently returning an empty tuple."""
    m = re.search(r"^%s=\(([^)]*)\)" % re.escape(varname), text, re.MULTILINE)
    if m is None:
        raise AssertionError("could not find %s=(...) in source" % varname)
    return tuple(m.group(1).split())


def parse_phase_folders(script_path=PHASE_DOCS_LINT_SCRIPT):
    return _read_bare_array(script_path.read_text(encoding="utf-8"), "PHASE_FOLDERS")


def parse_phase_folder_names(script_path=SCRIPT_PATH):
    return _read_bare_array(script_path.read_text(encoding="utf-8"), "PHASE_FOLDER_NAMES")


class PhaseFolderNamesBindingTest(unittest.TestCase):
    """The highest-value test in WI-0126's tranche 1: the two folder lists
    are typed independently in two different scripts and nothing checks
    they still agree. This is that check."""

    def test_phase_folder_names_equals_phase_folders(self):
        self.assertEqual(parse_phase_folders(), parse_phase_folder_names())


class PhaseFolderNamesBindingRedProofTest(unittest.TestCase):
    """Mutation-based RED proof (WI-0037/WI-0044 precedent), same shape as
    ContractTableExitCodeBindingRedProofTest above: drops ONE entry at a
    time from PHASE_FOLDER_NAMES in a SCRATCH copy of conformance-run.sh
    (the shipped file is never touched, never executed -- this is a pure
    text parse, like the class above) and confirms the binding above would
    go red for exactly that entry, while every other of the nine folders
    is untouched -- one subTest per entry, per G-109 (the mutation must
    change structure, not merely presence)."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wi0126-redproof-folder-names-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_removing_one_entry_breaks_only_that_entrys_binding(self):
        before = SCRIPT_PATH.read_bytes()
        before_mode = SCRIPT_PATH.stat().st_mode
        original = before.decode()
        needle = "PHASE_FOLDER_NAMES=(discovery concept validation architecture planning quality launch operations reviews)"
        self.assertIn(
            needle, original,
            "fixture assumption broken -- PHASE_FOLDER_NAMES's own literal line changed, update this test",
        )

        folders = parse_phase_folders()
        for removed in folders:
            with self.subTest(folder=removed):
                narrowed = " ".join(f for f in folders if f != removed)
                mutated = original.replace(
                    needle, "PHASE_FOLDER_NAMES=(%s)" % narrowed, 1,
                )
                self.assertNotEqual(original, mutated)
                scratch = self.tmpdir / ("conformance-run-%s.sh" % removed)
                scratch.write_text(mutated, encoding="utf-8")

                mutated_names = parse_phase_folder_names(scratch)
                self.assertNotEqual(folders, mutated_names, (removed, mutated_names))
                self.assertNotIn(removed, mutated_names)
                for neighbour in folders:
                    if neighbour != removed:
                        self.assertIn(neighbour, mutated_names, (removed, neighbour))

        self.assertEqual(before, SCRIPT_PATH.read_bytes(), "shipped file content changed")
        self.assertEqual(before_mode, SCRIPT_PATH.stat().st_mode, "shipped file mode bits changed")


class RealCheckSkeletonTest(unittest.TestCase):
    """Companion to the header-binding test above: pins the PARSING
    contract the classifier depends on by running each REAL (non-stub)
    shipped check over a tiny synthetic fixture (an empty git repo with a
    bare docs/) and asserting its own mandatory report-skeleton lines are
    present -- the same lines conformance-run.sh's Rule 3
    (missing-skeleton) requires. Behaviour measured directly before
    writing this test: every one of the five checks takes its normal,
    full-skeleton, zero-scope path over an empty docs/ (no early
    short-circuit with a partial report), unlike phase-docs-lint.sh with
    docs/ entirely ABSENT (ProductionShapeCouldNotRunTest's own docstring
    names that different shape)."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="ccpr-groupE-skeleton-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.project = self.home / "project"
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        (self.project / "docs").mkdir(parents=True)

    def env(self):
        return {"HOME": str(self.home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}

    def _run(self, script, *args):
        return subprocess.run(
            ["bash", str(REPO_ROOT / "scripts" / script), *args],
            capture_output=True, text=True, env=self.env(),
        )

    def test_memory_lint_skeleton(self):
        r = self._run("memory-lint.sh", str(self.project))
        for s in ("**Files scanned:**", "**Summary:**", "**Exit:**"):
            self.assertIn(s, r.stdout, r.stdout + r.stderr)

    def test_phase_docs_lint_skeleton(self):
        r = self._run("phase-docs-lint.sh", str(self.project))
        for s in ("**Files scanned:**", "**Summary:**", "**Exit:**"):
            self.assertIn(s, r.stdout, r.stdout + r.stderr)

    def test_manual_lint_skeleton(self):
        r = self._run("manual-lint.sh", str(self.project / "docs"))
        for s in ("**Files scanned:**", "**Summary:**", "**Exit:**"):
            self.assertIn(s, r.stdout, r.stdout + r.stderr)

    def test_doc_volume_check_skeleton(self):
        r = self._run("doc-volume-check.sh", str(self.project / "docs"))
        for s in ("**Files scanned:**", "**Summary:**", "**Exit:**"):
            self.assertIn(s, r.stdout, r.stdout + r.stderr)

    def test_anchor_skeleton(self):
        r = self._run("anchor.sh", "status", str(self.project))
        for s in ("**Anchors:**", "**Last production-code commit:**"):
            self.assertIn(s, r.stdout, r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# Group F (WI-0124 Wave 3) -- the always-on configuration test: reads the
# REAL gate_config_path() (neither HOME nor MEMORY_SYNC_CONFIG is
# sandboxed here, unlike every other test in this module), and never
# skips. See test_memory_lint_commonmark_corpus.py:5-15 for why this is
# conditional STRENGTHENING rather than a `skipIf` -- skipping on "no real
# config" would make this suite silently green-by-skip on exactly the
# machine (a fresh install, or CI) this test exists to still say
# something true about: the not-configured clean-skip contract (ADR-0010
# decision 4) IS itself an acceptance criterion, so asserting it is
# non-vacuous everywhere, including a machine that will never carry a real
# conformance config. A machine that DOES carry one additionally gets
# every-consumer-resolves / every-pin-has-a-why / never-exit-2 checked
# against WHATEVER the operator actually configured -- never a specific
# FINDING, which would make this suite red on a consumer's own document
# content, the exact conflation ADR-0010 forbids (decision 2).
# ---------------------------------------------------------------------------
class RealConfigurationConformanceTest(unittest.TestCase):
    def _real_config_path(self):
        override = os.environ.get("MEMORY_SYNC_CONFIG")
        if override:
            return Path(override)
        return Path.home() / ".claude" / "memory-sync.json"

    def _real_conformance_block(self):
        path = self._real_config_path()
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        conformance = data.get("conformance")
        return conformance if isinstance(conformance, dict) else None

    def test_real_local_configuration_is_conformant(self):
        cfg_path = self._real_config_path()
        conformance = self._real_conformance_block()
        consumers = conformance.get("consumers") if conformance else None
        consumers = consumers if isinstance(consumers, list) else []

        r = subprocess.run(["bash", str(SCRIPT_PATH)], capture_output=True, text=True, env=None)
        operator_note = (
            "a failure here reflects THIS MACHINE'S OWN local conformance "
            "configuration (%s), not a CCPR defect -- if a consumer moved "
            "or a pin's `why` is missing, fix that config, not this test.\n"
            "returncode: %s\nstdout:\n%s\nstderr:\n%s"
            % (cfg_path, r.returncode, r.stdout, r.stderr)
        )

        if not consumers:
            self.assertEqual(0, r.returncode, operator_note)
            self.assertIn(NOT_CONFIGURED_STATEMENT, r.stdout, operator_note)
            return

        self.assertIn(r.returncode, (0, 1), operator_note)
        for c in consumers:
            cid = c.get("id") if isinstance(c, dict) else None
            if cid:
                self.assertIn(str(cid), r.stdout, operator_note)
        for pin in (conformance.get("pins") or []):
            if isinstance(pin, dict):
                self.assertTrue(pin.get("why"), "pin missing why: %r -- %s" % (pin, operator_note))


# ---------------------------------------------------------------------------
# Group G (WI-0124 Wave 3) -- repository hygiene: this mechanism's own
# shipped source and template stay free of anything Constitution
# Inviolable #2 ("No personal or tenant data in shipped artifacts")
# forbids, and no tracked file could ever be mistaken for a checked-in
# conformance report by its own heading shape.
# ---------------------------------------------------------------------------
FORBIDDEN_PERSONAL_SUBSTRINGS = ("jonascode", "/Users/", "/home/", "erfinderwerkstatt")


class RepositoryHygieneTest(unittest.TestCase):
    def test_shipped_conformance_files_carry_no_personal_or_tenant_data(self):
        offenders = []
        for path in (SCRIPT_PATH, REPO_ROOT / "templates" / "memory-sync.example.json"):
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN_PERSONAL_SUBSTRINGS:
                if needle in text:
                    offenders.append("%s contains %r" % (path.relative_to(REPO_ROOT), needle))
        self.assertEqual([], offenders)

    def test_no_tracked_file_matches_the_conformance_report_heading(self):
        heading = "# Conformance Run Report"
        r = subprocess.run(["git", "ls-files"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
        offenders = []
        for rel in r.stdout.splitlines():
            path = REPO_ROOT / rel
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if heading in text.splitlines():
                offenders.append(rel)
        self.assertEqual([], offenders)


# ---------------------------------------------------------------------------
# WI-0126 tranche 4 -- the seven CHECK_* parallel arrays (:168-197) are
# aligned by POSITION only, and four of the seven columns
# (CHECK_SUBCMD, CHECK_ARG_SHAPE, CHECK_C2_EXEMPT, CHECK_HAS_SUMMARY_LINE)
# had no per-entry coverage before this tranche.
#
# The discriminating mutation for every column below is a SWAP, not a
# removal (G-109): measured directly, a column one entry SHORTER than its
# siblings dies loudly under this file's own `set -euo pipefail`
# (CheckTableShortColumnRedProofTest below) -- but a TRANSPOSED column of
# the same length runs to completion silently, with check N quietly
# getting check M's argument shape, exit set, or exemption. A removal
# proof would therefore pass while proving the wrong thing for these four
# columns; every per-entry proof here swaps two entries in a SCRATCH copy
# of conformance-run.sh (the shipped file is never touched, matching
# ContractTableExitCodeBindingRedProofTest's own convention above) and
# shows the run's behaviour changes for exactly those two checks.
# ---------------------------------------------------------------------------

CHECK_TABLE_COLUMN_NAMES = (
    "CHECK_NAMES",
    "CHECK_SCRIPTS",
    "CHECK_SUBCMD",
    "CHECK_ARG_SHAPE",
    "CHECK_EXIT_SET",
    "CHECK_C2_EXEMPT",
    "CHECK_HAS_SUMMARY_LINE",
)

# Digits included on purpose ([A-Za-z0-9_], not [A-Za-z_]) -- the WI-0126
# briefing measured that a first-draft enumeration regex using [A-Z_] alone
# silently skipped CHECK_C2_EXEMPT, since [A-Z_] excludes the "2".
CHECK_TABLE_ARRAY_RE = re.compile(r"^(CHECK_[A-Za-z0-9_]*)=\(", re.MULTILINE)


def find_check_table_array_names(script_path=SCRIPT_PATH):
    """Every CHECK_*=(...) array literal actually declared in the script,
    found by sweeping the WHOLE file rather than by trusting
    CHECK_TABLE_COLUMN_NAMES's own enumeration -- the point of this sweep
    is to notice a future EIGHTH column nobody added to that tuple, not to
    confirm the seven this test file already knows about."""
    return tuple(CHECK_TABLE_ARRAY_RE.findall(script_path.read_text(encoding="utf-8")))


def parse_full_check_table(script_path=SCRIPT_PATH):
    """All seven of conformance-run.sh's parallel CHECK_* arrays, aligned
    by POSITION only. Returns {column_name: tuple_of_values}. Asserts every
    column has the SAME length -- the alignment invariant WI-0126 tranche 4
    exists to pin: a future eighth column that nobody ties in here, or an
    existing column narrowed by one entry, fails this assertion the moment
    it disagrees in length with its six siblings, rather than silently
    shifting every check after it by one position at runtime."""
    text = script_path.read_text(encoding="utf-8")
    columns = {name: tuple(_parse_paren_array(name, text)) for name in CHECK_TABLE_COLUMN_NAMES}
    lengths = {name: len(values) for name, values in columns.items()}
    assert len(set(lengths.values())) == 1, "conformance-run.sh's CHECK_* columns disagree on length: %r" % (lengths,)
    return columns


class CheckTableAlignmentTest(unittest.TestCase):
    def test_all_seven_columns_are_five_entries_long(self):
        columns = parse_full_check_table()
        self.assertEqual(7, len(columns))
        for name, values in columns.items():
            self.assertEqual(5, len(values), "%s has %d entries, expected 5: %r" % (name, len(values), values))

    def test_exactly_the_seven_named_columns_exist_in_source(self):
        self.assertEqual(CHECK_TABLE_COLUMN_NAMES, find_check_table_array_names())


class CheckTableAlignmentRedProofTest(unittest.TestCase):
    """Mutation-based RED proof (G-107) for the alignment invariant itself:
    a scratch copy with one column shortened by one entry must make
    parse_full_check_table's own length assertion fire, and a scratch copy
    with an EIGHTH CHECK_* array added -- one nobody ties into
    CHECK_TABLE_COLUMN_NAMES -- must make find_check_table_array_names's
    result stop matching the pinned seven. These are the two halves of
    deliverable 1's own promise ("pin both the length (5) and the column
    count (7)")."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wi0126-t4-alignment-redproof-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_a_shortened_column_breaks_the_length_invariant(self):
        before, before_mode = SCRIPT_PATH.read_bytes(), SCRIPT_PATH.stat().st_mode
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        needle = "CHECK_C2_EXEMPT=(0 0 0 0 1)"
        self.assertIn(needle, original, "fixture assumption broken -- update this test")
        mutated = original.replace(needle, "CHECK_C2_EXEMPT=(0 0 0 1)", 1)
        self.assertNotEqual(original, mutated)
        scratch = self.tmpdir / "conformance-run.sh"
        scratch.write_text(mutated, encoding="utf-8")

        with self.assertRaises(AssertionError):
            parse_full_check_table(scratch)

        # Same G-143 safety net every sibling scratch-mutation test in this
        # file carries. These two never open SCRIPT_PATH for writing, so the
        # risk is nil -- but a reader scanning this section learns to expect
        # the assertion, and its absence reads as an oversight rather than as
        # "this one is a pure text parse" (WI-0126 tranche 4 review).
        self.assertEqual(before, SCRIPT_PATH.read_bytes(), "shipped file content changed")
        self.assertEqual(before_mode, SCRIPT_PATH.stat().st_mode, "shipped file mode bits changed")

    def test_an_untied_eighth_column_breaks_the_count_invariant(self):
        before, before_mode = SCRIPT_PATH.read_bytes(), SCRIPT_PATH.stat().st_mode
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        needle = "CHECK_COUNT=${#CHECK_NAMES[@]}"
        self.assertIn(needle, original, "fixture assumption broken -- update this test")
        mutated = original.replace(needle, "CHECK_FOO=(a b c d e)\n" + needle, 1)
        self.assertNotEqual(original, mutated)
        scratch = self.tmpdir / "conformance-run.sh"
        scratch.write_text(mutated, encoding="utf-8")

        found = find_check_table_array_names(scratch)
        self.assertEqual(8, len(found))
        self.assertNotEqual(CHECK_TABLE_COLUMN_NAMES, found)

        self.assertEqual(before, SCRIPT_PATH.read_bytes(), "shipped file content changed")
        self.assertEqual(before_mode, SCRIPT_PATH.stat().st_mode, "shipped file mode bits changed")


DISCIPLINE_GATE_LIB = REPO_ROOT / "scripts" / "lib" / "discipline_gate.sh"


def _write_mutated_conformance_script(tmpdir, mutate_fn):
    """Copies conformance-run.sh AND its own sourced lib/discipline_gate.sh
    (`. "$HERE/lib/discipline_gate.sh"`, :164 -- a scratch copy of
    conformance-run.sh alone dies at that source line before reaching
    anything this tranche mutates, the same lib-alongside-the-script
    requirement list-coverage.md's tranche 1 entry already names for
    phase-docs-lint.sh/anchor.sh) into tmpdir, applying
    mutate_fn(original_text) -> mutated_text to the top-level script only.
    Asserts the shipped files are unchanged afterwards (G-143)."""
    before = SCRIPT_PATH.read_bytes()
    before_mode = SCRIPT_PATH.stat().st_mode
    lib_before = DISCIPLINE_GATE_LIB.read_bytes()

    original = before.decode("utf-8")
    mutated = mutate_fn(original)
    assert mutated != original, "mutation had no effect"

    scratch = tmpdir / "conformance-run.sh"
    scratch.write_text(mutated, encoding="utf-8")
    scratch.chmod(0o755)
    (tmpdir / "lib").mkdir(exist_ok=True)
    shutil.copy2(DISCIPLINE_GATE_LIB, tmpdir / "lib" / "discipline_gate.sh")

    assert before == SCRIPT_PATH.read_bytes(), "shipped conformance-run.sh content changed"
    assert before_mode == SCRIPT_PATH.stat().st_mode, "shipped conformance-run.sh mode bits changed"
    assert lib_before == DISCIPLINE_GATE_LIB.read_bytes(), "shipped lib/discipline_gate.sh content changed"
    return scratch


def _swap_literal(varname, old_line, new_line):
    """A mutate_fn (for _write_mutated_conformance_script) that asserts the
    EXACT literal array line is present before replacing it (G-141) --
    every CHECK_* column's transposition mutation below is built from this
    one helper, differing only in which two positions the literal swaps."""

    def _mutate(original):
        assert old_line in original, (
            "conformance-run.sh's own %s literal line changed -- update this test: %r" % (varname, old_line)
        )
        mutated = original.replace(old_line, new_line, 1)
        assert mutated != original
        return mutated

    return _mutate


class CheckTableShortColumnRedProofTest(ConformanceRunTestBase):
    """WI-0126 tranche 4, deliverable 4: pins the LOUD failure a SHORTENED
    column produces under this file's own `set -euo pipefail` -- the
    opposite of every transposition proof in this section. Measured
    directly: a column one entry short does not silently misalign: it dies
    with 'unbound variable' the instant _run_and_classify_check reaches the
    missing index, before it ever invokes the check script itself. A later
    refactor that added a `${arr[i]:-}` default to one of the CHECK_*
    lookups -- turning this loud case silent -- would flip this test from
    'sees the expected unbound-variable death' to 'sees a clean run
    instead', which is exactly a regression, not a pass."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wi0126-t4-shortcol-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_a_column_one_entry_short_dies_with_unbound_variable(self):
        scratch = _write_mutated_conformance_script(self.tmpdir, _swap_literal(
            "CHECK_SUBCMD",
            'CHECK_SUBCMD=("" "" "" "" status)',
            'CHECK_SUBCMD=("" "" "" "")',
        ))
        r = self.run_conformance(script_path=scratch)
        self.assertEqual(1, r.returncode, self.output(r))
        self.assertIn("unbound variable", r.stderr, self.output(r))


class CheckTableUncoveredColumnsValuesTest(unittest.TestCase):
    """Parsed-from-source pins for the four columns this tranche covers --
    weak alone (list-coverage.md's house-pattern ranking, level 1: a
    hardcoded expectation catches narrowing but proves nothing about
    whether the value actually DRIVES behaviour), paired below with one
    transposition-proof class per column that supplies the missing half."""

    def test_check_subcmd_only_anchor_carries_a_subcommand(self):
        self.assertEqual(("", "", "", "", "status"), parse_full_check_table()["CHECK_SUBCMD"])

    def test_check_arg_shape_is_a_three_two_split(self):
        self.assertEqual(("project", "project", "docs", "docs", "project"), parse_full_check_table()["CHECK_ARG_SHAPE"])

    def test_check_c2_exempt_only_anchor_is_exempt(self):
        self.assertEqual(("0", "0", "0", "0", "1"), parse_full_check_table()["CHECK_C2_EXEMPT"])

    def test_check_has_summary_line_only_anchor_lacks_one(self):
        self.assertEqual(("1", "1", "1", "1", "0"), parse_full_check_table()["CHECK_HAS_SUMMARY_LINE"])


class CheckArgShapeTranspositionTest(ConformanceRunTestBase):
    """WI-0126 tranche 4, deliverable 3: swaps CHECK_ARG_SHAPE's memory-lint
    (idx0, 'project') and manual-lint (idx2, 'docs') entries in a scratch
    copy -- crossing the column's own 3/2 split (briefing :171-183). Both
    stubs branch on whether their own first argument ends in '/docs',
    mirroring DocsRootAsymmetryTest's existing stub shape above (the same
    trap named there: getting this column wrong for a 'docs' check turns a
    populated consumer into a silent Files-scanned:-0 run, which C2 then
    reports as a CCPR defect that is actually our own argument mistake)."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        (self.consumer / "docs" / "memory").mkdir(parents=True)
        (self.consumer / "docs" / "memory" / "note.md").write_text("# note\n", encoding="utf-8")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wi0126-t4-argshape-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    @staticmethod
    def _branching_stub(clean_when_docs_suffixed):
        """Reports CLEAN_FILES_SCANNED_REPORT when its own $1 ends in
        '/docs' and clean_when_docs_suffixed is True (or when it does NOT
        and clean_when_docs_suffixed is False); a Files-scanned:-0 report
        in the other case."""
        clean = CLEAN_FILES_SCANNED_REPORT.rstrip("\n")
        dirty = CLEAN_FILES_SCANNED_REPORT.replace("**Files scanned:** 3", "**Files scanned:** 0").rstrip("\n")
        docs_branch, other_branch = (clean, dirty) if clean_when_docs_suffixed else (dirty, clean)
        return "\n".join([
            "#!/usr/bin/env bash",
            'case "$1" in',
            "  */docs)",
            "    cat <<'STUB_EOF'", docs_branch, "STUB_EOF",
            "    exit 0", "    ;;",
            "  *)",
            "    cat <<'STUB_EOF'", other_branch, "STUB_EOF",
            "    exit 0", "    ;;",
            "esac",
        ]) + "\n"

    def _write_branching_stub(self, filename, clean_when_docs_suffixed):
        path = self.checks_dir / filename
        path.write_text(self._branching_stub(clean_when_docs_suffixed), encoding="utf-8")
        path.chmod(0o755)

    def test_swapping_memory_lint_and_manual_lint_flips_c2_for_exactly_those_two(self):
        # memory-lint's TRUE shape is 'project' (bare path, no /docs
        # suffix) -- clean when NOT suffixed.
        self._write_branching_stub("memory-lint.sh", clean_when_docs_suffixed=False)
        # manual-lint's TRUE shape is 'docs' -- clean when suffixed.
        self._write_branching_stub("manual-lint.sh", clean_when_docs_suffixed=True)

        baseline = self.run_conformance()
        self.assertEqual(0, baseline.returncode, self.output(baseline))
        self.assertNotIn("memory-lint on alpha", baseline.stdout, self.output(baseline))
        self.assertNotIn("manual-lint on alpha", baseline.stdout, self.output(baseline))

        scratch = _write_mutated_conformance_script(self.tmpdir, _swap_literal(
            "CHECK_ARG_SHAPE",
            "CHECK_ARG_SHAPE=(project project docs docs project)",
            "CHECK_ARG_SHAPE=(docs project project docs project)",
        ))
        after = self.run_conformance(script_path=scratch)
        self.assertEqual(1, after.returncode, self.output(after))
        c2_section = after.stdout.split("### Zero scope (C2)", 1)[1].split("### Could Not Run", 1)[0]
        self.assertIn("memory-lint on alpha", c2_section, self.output(after))
        self.assertIn("manual-lint on alpha", c2_section, self.output(after))
        self.assertNotIn("phase-docs-lint", c2_section, self.output(after))
        self.assertNotIn("doc-volume-check", c2_section, self.output(after))
        self.assertNotIn("anchor", c2_section, self.output(after))


class CheckC2ExemptTranspositionTest(ConformanceRunTestBase):
    """WI-0126 tranche 4, deliverable 3: swaps CHECK_C2_EXEMPT's memory-lint
    (idx0, 0) and anchor (idx4, 1) entries. Measured, not assumed: memory-
    lint's half of the swap is a real, two-sided behaviour change (gaining
    exemption silences a C2 finding that fires at baseline); anchor's half
    does NOT observably change, because _c2_probe_has_candidates (:283-311)
    has no `case` arm for 'anchor' at all -- its `*) return 1 ;;` default
    means the probe never reports a candidate for that name regardless of
    the exempt flag. That is a genuine, orthogonal double-guard (the exempt
    flag short-circuits before the probe runs; the probe's own switch would
    catch it even if the flag did not) -- reported here as measured rather
    than forced into a two-sided assertion neither the code nor the run
    supports."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        (self.consumer / "docs" / "memory").mkdir(parents=True)
        (self.consumer / "docs" / "memory" / "note.md").write_text("# note\n", encoding="utf-8")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wi0126-t4-c2exempt-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        # memory-lint reports Files scanned: 0 despite the real candidate
        # planted above -- the exact shape C2 exists to catch.
        self.write_stub("memory-lint.sh", CLEAN_FILES_SCANNED_REPORT.replace("**Files scanned:** 3", "**Files scanned:** 0"), 0)
        # anchor's report is given a hypothetical, non-real 'Files
        # scanned:' line -- anchor's REAL report never has one
        # (CHECK_C2_EXEMPT's own comment calls this "structurally exempt",
        # :186-191); this stub is what tests whether the exempt FLAG, not
        # merely the report's own shape, is what prevents a spurious
        # finding.
        anchor_with_files_line = CLEAN_ANCHOR_REPORT.replace("**Anchors:**", "**Files scanned:** 0\n**Anchors:**", 1)
        self.write_stub("anchor.sh", anchor_with_files_line, 0)

    def test_memory_lint_loses_its_c2_finding_after_gaining_exemption(self):
        baseline = self.run_conformance()
        self.assertEqual(1, baseline.returncode, self.output(baseline))
        self.assertIn("memory-lint on alpha", baseline.stdout.split("### Zero scope (C2)", 1)[1], self.output(baseline))

        scratch = _write_mutated_conformance_script(self.tmpdir, _swap_literal(
            "CHECK_C2_EXEMPT",
            "CHECK_C2_EXEMPT=(0 0 0 0 1)",
            "CHECK_C2_EXEMPT=(1 0 0 0 0)",
        ))
        after = self.run_conformance(script_path=scratch)
        c2_section = after.stdout.split("### Zero scope (C2)", 1)[1].split("### Could Not Run", 1)[0]
        self.assertNotIn("memory-lint on alpha", c2_section, self.output(after))

    def test_anchor_gaining_non_exempt_status_measured_to_not_change_its_own_report(self):
        scratch = _write_mutated_conformance_script(self.tmpdir, _swap_literal(
            "CHECK_C2_EXEMPT",
            "CHECK_C2_EXEMPT=(0 0 0 0 1)",
            "CHECK_C2_EXEMPT=(1 0 0 0 0)",
        ))
        after = self.run_conformance(script_path=scratch)
        # Real liveness guard, not an inference from the section text alone
        # (WI-0125/WI-0126 tranche 4 round 2): both halves of this swap null
        # out -- memory-lint gains exemption and loses its own C2 finding,
        # anchor never had one to begin with (see the class docstring) --
        # so the run's own exit code is measured to be 0, not merely
        # assumed from an empty-looking "_none_" section.
        self.assertEqual(0, after.returncode, self.output(after))
        c2_section = after.stdout.split("### Zero scope (C2)", 1)[1].split("### Could Not Run", 1)[0]
        self.assertNotIn("anchor on alpha", c2_section, self.output(after))


class CheckHasSummaryLineTranspositionTest(ConformanceRunTestBase):
    """WI-0126 tranche 4, deliverable 3: swaps CHECK_HAS_SUMMARY_LINE's
    memory-lint (idx0, 1) and anchor (idx4, 0) entries -- unlike
    CHECK_C2_EXEMPT above, Rule 5 (the internal-contradiction check) has no
    per-name special case, so this swap produces a genuinely two-sided
    flip: the check that LOSES its summary-line flag stops being checked
    for a 0-errors/0-warnings-but-nonzero-exit contradiction (its finding
    demotes from C1 to a plain P finding), and the check that GAINS the
    flag starts being checked for exactly that contradiction (a P finding
    promotes to C1)."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wi0126-t4-hassummary-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        # memory-lint: a self-contradicting report (0 errors, 0 warnings,
        # but a non-zero exit) -- within its own {0,1,2,3} exit set, so
        # Rule 1 does not fire.
        self.write_stub("memory-lint.sh", CLEAN_FILES_SCANNED_REPORT.replace("**Exit:** 0", "**Exit:** 1"), 1)
        # anchor: the same self-contradiction shape, spliced into its own
        # report skeleton (a hypothetical -- anchor's REAL report has no
        # Summary line at all, see CHECK_HAS_SUMMARY_LINE's own comment) --
        # within anchor's {0,2,3} exit set.
        anchor_with_summary = CLEAN_ANCHOR_REPORT.replace(
            "**Anchors:**", "**Summary:** 0 errors, 0 warnings, 0 info.\n**Anchors:**", 1
        ).replace("**Exit:** 0", "**Exit:** 3")
        self.write_stub("anchor.sh", anchor_with_summary, 3)

    def test_swap_flips_which_of_the_two_gets_the_c1_contradiction_finding(self):
        baseline = self.run_conformance()
        c1_before = baseline.stdout.split("### Contract violations (C1)", 1)[1].split("### Zero scope (C2)", 1)[0]
        p_before = baseline.stdout.split("### Consumer findings (P)", 1)[1]
        self.assertIn("memory-lint on alpha", c1_before, self.output(baseline))
        self.assertNotIn("anchor", c1_before, self.output(baseline))
        self.assertIn("anchor on alpha", p_before, self.output(baseline))
        self.assertNotIn("memory-lint", p_before, self.output(baseline))

        scratch = _write_mutated_conformance_script(self.tmpdir, _swap_literal(
            "CHECK_HAS_SUMMARY_LINE",
            "CHECK_HAS_SUMMARY_LINE=(1 1 1 1 0)",
            "CHECK_HAS_SUMMARY_LINE=(0 1 1 1 1)",
        ))
        after = self.run_conformance(script_path=scratch)
        c1_after = after.stdout.split("### Contract violations (C1)", 1)[1].split("### Zero scope (C2)", 1)[0]
        p_after = after.stdout.split("### Consumer findings (P)", 1)[1]
        self.assertIn("anchor on alpha", c1_after, self.output(after))
        self.assertNotIn("memory-lint", c1_after, self.output(after))
        self.assertIn("memory-lint on alpha", p_after, self.output(after))
        self.assertNotIn("anchor", p_after, self.output(after))


class CheckSubcmdTranspositionRealScriptTest(ConformanceRunTestBase):
    """WI-0126 tranche 4, deliverable 3's 'at least one end-to-end shape':
    swaps CHECK_SUBCMD's memory-lint (idx0, '') and anchor (idx4, 'status')
    entries and drives the REAL shipped memory-lint.sh/anchor.sh (never
    stubs) against a real, git-initialised consumer -- the pair whose own
    CLI parsing reacts most differently to gaining/losing a leading
    subcommand token: memory-lint.sh reads only its OWN $1 as the project
    directory (silently ignoring a $2), so gaining a leading 'status'
    token makes it scan the wrong (nonexistent) directory instead of
    erroring; anchor.sh dispatches on its own $1 as a subcommand name, so
    losing 'status' makes the consumer's own absolute path look like an
    unrecognised subcommand."""

    def setUp(self):
        super().setUp()
        self.consumer = self.make_consumer_dir("alpha")
        (self.consumer / "docs").mkdir()
        (self.consumer / "docs" / "memory").mkdir()
        (self.consumer / "docs" / "memory" / "note.md").write_text(
            "---\n"
            "name: fixture\n"
            "description: WI-0126 tranche 4 fixture note\n"
            "type: patterns\n"
            "last_updated: 28.08.2026\n"
            "---\n"
            "# note\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q"], cwd=str(self.consumer), check=True)
        self.write_config(conformance={"consumers": [{"id": "alpha", "path": str(self.consumer)}]})
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wi0126-t4-subcmd-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.real_scripts_dir = str(REPO_ROOT / "scripts")

    def test_swap_turns_memory_lint_into_a_c2_finding_and_anchor_into_could_not_run(self):
        baseline = self.run_conformance(CCPR_CONFORMANCE_SCRIPT_DIR=self.real_scripts_dir)
        could_not_run_before = baseline.stdout.split("### Could Not Run", 1)[1].split("### Pinned expectations", 1)[0]
        self.assertNotIn("anchor on alpha", could_not_run_before, self.output(baseline))
        if "### Zero scope (C2)" in baseline.stdout:
            c2_before = baseline.stdout.split("### Zero scope (C2)", 1)[1].split("### Could Not Run", 1)[0]
            self.assertNotIn("memory-lint on alpha", c2_before, self.output(baseline))

        scratch = _write_mutated_conformance_script(self.tmpdir, _swap_literal(
            "CHECK_SUBCMD",
            'CHECK_SUBCMD=("" "" "" "" status)',
            'CHECK_SUBCMD=(status "" "" "" "")',
        ))
        # cwd=self.tmpdir (an EMPTY scratch dir): memory-lint.sh now reads
        # its own $1 ("status", the entry it stole from anchor) as
        # PROJECT_DIR, a RELATIVE path -- pinning cwd is what keeps
        # "status/docs/memory" deterministically absent rather than
        # depending on wherever this test suite happens to be invoked from.
        after = self.run_conformance(
            script_path=scratch, cwd=self.tmpdir, CCPR_CONFORMANCE_SCRIPT_DIR=self.real_scripts_dir,
        )
        c2_after = after.stdout.split("### Zero scope (C2)", 1)[1].split("### Could Not Run", 1)[0]
        could_not_run_after = after.stdout.split("### Could Not Run", 1)[1].split("### Pinned expectations", 1)[0]
        self.assertIn("memory-lint on alpha", c2_after, self.output(after))
        self.assertIn("anchor on alpha", could_not_run_after, self.output(after))
        self.assertIn("unknown subcommand", could_not_run_after, self.output(after))


if __name__ == "__main__":
    unittest.main()
