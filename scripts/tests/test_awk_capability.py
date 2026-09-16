r"""test_awk_capability.py -- CCP-1179: `scripts/lib/awk_capability.sh`, the
shared probe that answers "can the awk that will actually run this repo's
CommonMark block-structure scanners compile the EREs they use?".

## Why a probe exists at all

`mawk 1.3.4 20240123` -- the default `/usr/bin/awk` on Debian-family
systems -- has a regex-compiler bug: an interval quantifier `{n,m}`
followed later in the same ERE by a parenthesised group aborts the whole
program with `REcompile() - panic: values still on machine stack`, exit
100. Two shipped scripts carried exactly that shape in their fence /
heading / list-marker detection. The abort is loud on the awk child's
stderr and INVISIBLE on both channels automation reads: memory-lint.sh's
own report said `0 errors, 0 warnings, 0 info` / `**Exit:** 0` -- a check
that parsed nothing reporting clean (KA-G-017's "a run that verified
nothing is not a pass", one level below where that rule was written).

CCP-1179 rewrote the EREs so every awk compiles them. This probe is the
part that stays: the next dialect surprise must produce a could-not-run
outcome, not a false green.

## Two-sided coverage, and why the stubs are not the whole story

`CanaryVerdictTest` drives the probe with STUB `awk` binaries on PATH.
A stub is not the real thing (G-127), and it is used here for one reason:
the incapable side of the seam cannot be reproduced on a machine whose awk
is capable, and the capable side cannot be reproduced on a machine whose
awk is mawk -- no single machine can exercise both with a real binary, and
gating either half on the local awk variant would mean the shipped
could-not-run path is verified on some machines and not others.

`RealAwkAgreementTest` is the other half and uses no stub at all: it
cross-asserts the probe's verdict about THIS machine's real awk against an
independent, differently-spelled instance of the same ERE shape (the
literal fence-opener pattern memory-lint.sh:1770 shipped before CCP-1179).
That is a genuine cross-assert rather than a tautology (G-095): the canary
and the witness share only the *shape* under test, not their text, and the
assertion is correct on a gawk machine (both compile), on a mawk machine
(neither compiles) and on a `{n,m}`-less awk (neither matches) alike.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "lib" / "awk_capability.sh"

# The same sandboxed PATH test_shellcheck_run.py / test_artifact_gate.py use.
# It is also the PATH test_memory_lint.py hands memory-lint.sh, so the awk a
# probe run here resolves is the awk those runs resolve.
SANDBOX_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"

# The ERE `scripts/memory-lint.sh:1770` and `scripts/migrate-review-headers.sh:278`
# both carried before CCP-1179 -- the CommonMark fence opener. Kept here as a
# WITNESS of the failing shape (interval quantifier, then a parenthesised
# group), not as a claim about what those files contain today: the whole point
# of the fix is that they no longer contain it. Spelled differently from the
# probe's own canary on purpose, so the agreement test below compares two
# independent instances of the shape rather than an expression against itself.
HISTORICAL_FENCE_OPENER_ERE = r"^[ ]{0,3}(```+|~~~+)"


def _stub_dir(script_body):
    """A throwaway directory holding a single executable `awk` shim."""
    tmp = tempfile.mkdtemp(prefix="ccpr-awk-stub-")
    stub = Path(tmp) / "awk"
    stub.write_text(script_body, encoding="utf-8")
    stub.chmod(0o755)
    return tmp


# Compiles and matches: the shape of a capable awk's answer to the canary.
CAPABLE_STUB = "#!/bin/sh\nprintf '1\\n'\n"

def _panicking_stub():
    """An awk that is mawk 1.3.4 in the one respect under test, and a real
    awk in every other.

    It MODELS the measured trigger -- an interval quantifier `{n,m}` followed
    later in the same ERE by a parenthesised group -- rather than matching the
    canary's literal text, and delegates everything else to the machine's real
    awk. Both properties are load-bearing:

    * A stub that panicked on every argv is a machine nobody runs. It would
      also make `memory-lint.sh`'s unrelated date and frontmatter awk passes
      die BEFORE the probe, so the tests below would be describing a
      catastrophic-awk scenario rather than the dialect gap CCP-1179 is about.
    * A stub keyed to the canary's literal spelling would be an expression
      checked against a copy of itself (G-095). Keyed to the SHAPE, it stays a
      real question: change the canary to something that no longer carries the
      shape and this fixture stops panicking, loudly.

    `--version` is answered the way the real binary answers it.
    """
    real = shutil.which("awk", path=SANDBOX_PATH)
    assert real, "the sandboxed PATH must contain an awk to delegate to"
    return (
        "#!/bin/sh\n"
        "case \"$1\" in --version|-W*) echo 'mawk 1.3.4 20240123'; exit 0 ;; esac\n"
        "for _a in \"$@\"; do\n"
        "  if printf '%s' \"$_a\" | grep -qE '[{][0-9]+,[0-9]*[}][^(]*[(]'; then\n"
        "    echo 'REcompile() - panic:  values still on machine stack' >&2\n"
        "    exit 100\n"
        "  fi\n"
        "done\n"
        f"exec {real} \"$@\"\n"
    )

# The quieter dialect gap, and the reason the canary asserts a MATCH rather
# than merely a successful exit: an awk with no interval-quantifier support at
# all (the original one-true-awk, busybox built without them) compiles
# `[ ]{0,3}` as four literal characters, exits 0, and silently matches
# nothing. Every downstream scanner then reports a clean file it never
# understood -- the exact false-green CCP-1179 exists to close.
NO_INTERVALS_STUB = "#!/bin/sh\nprintf '0\\n'\n"


class AwkCapabilityLibTestBase(unittest.TestCase):
    def call(self, snippet, stub_body=None):
        """Sources the shipped lib and runs `snippet` against it.

        `stub_body` installs an `awk` shim at the FRONT of the sandboxed
        PATH; without it the machine's real awk is used.
        """
        path = SANDBOX_PATH
        if stub_body is not None:
            stub = _stub_dir(stub_body)
            self.addCleanup(
                subprocess.run, ["rm", "-rf", stub], check=False
            )
            path = f"{stub}:{SANDBOX_PATH}"
        return subprocess.run(
            ["bash", "-c", f'set -euo pipefail; . "$1"; {snippet}', "_", str(LIB)],
            capture_output=True, text=True,
            env={"PATH": path, "HOME": os.environ.get("HOME", "/")},
        )


class CanaryVerdictTest(AwkCapabilityLibTestBase):
    """`awkcap_canary_ok` against the three dialect states that matter."""

    def test_an_awk_that_compiles_and_matches_the_canary_is_capable(self):
        r = self.call("awkcap_canary_ok", CAPABLE_STUB)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_an_awk_that_aborts_on_the_canary_is_not_capable(self):
        r = self.call("awkcap_canary_ok", _panicking_stub())
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)

    def test_an_awk_that_exits_clean_without_matching_is_not_capable(self):
        # Exit 0 alone is not the question -- see NO_INTERVALS_STUB's comment.
        r = self.call("awkcap_canary_ok", NO_INTERVALS_STUB)
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)

    def test_the_panic_text_never_reaches_the_callers_stderr(self):
        # The probe's job is to REPLACE the raw panic with a sentence a human
        # can act on; leaking it too would put the unexplained crash back on
        # the channel the could-not-run message is supposed to own.
        r = self.call("awkcap_canary_ok || true", _panicking_stub())
        self.assertNotIn("REcompile", r.stderr)
        self.assertNotIn("REcompile", r.stdout)


class CouldNotRunReasonTest(AwkCapabilityLibTestBase):
    """`awkcap_could_not_run_reason` -- the one sentence both shipped
    scripts put in front of a human when the probe fails."""

    def test_a_capable_awk_yields_no_reason_at_all(self):
        r = self.call("awkcap_could_not_run_reason", CAPABLE_STUB)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual("", r.stdout.strip())

    def test_the_reason_is_a_single_line(self):
        # Both call sites interpolate it into one report line / one warn().
        r = self.call("awkcap_could_not_run_reason", _panicking_stub())
        self.assertEqual(1, len(r.stdout.strip().splitlines()), r.stdout)

    def test_the_reason_names_the_awk_that_was_probed(self):
        r = self.call("awkcap_could_not_run_reason", _panicking_stub())
        self.assertIn("/awk", r.stdout, "the resolved awk path must be named")

    def test_the_reason_names_the_ticket(self):
        r = self.call("awkcap_could_not_run_reason", _panicking_stub())
        self.assertIn("CCP-1179", r.stdout)

    def test_the_reason_names_the_ere_shape_that_failed(self):
        r = self.call("awkcap_could_not_run_reason", _panicking_stub())
        self.assertIn("interval", r.stdout)
        self.assertIn("group", r.stdout)

    def test_the_workaround_is_offered_as_interim_and_not_as_a_requirement(self):
        # CCPR runs on what the system ships (ADR-0011's bash-3.2 floor is the
        # same posture one tool over). gawk is a way OUT of a broken run, never
        # a prerequisite for a normal one -- if this ever reads as a dependency,
        # the sentence is wrong, not the test.
        r = self.call("awkcap_could_not_run_reason", _panicking_stub())
        self.assertIn("gawk", r.stdout)
        self.assertIn("interim", r.stdout.lower())
        self.assertIn("not a CCPR requirement", r.stdout)


class IdentityTest(AwkCapabilityLibTestBase):
    def test_identity_names_the_resolved_path(self):
        r = self.call("awkcap_identity", CAPABLE_STUB)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("/awk", r.stdout.strip())

    def test_identity_survives_an_awk_with_no_version_flag(self):
        # The one-true-awk prints usage to stderr and exits 2 for `--version`.
        # A probe that dies there would turn a diagnosable dialect gap into an
        # undiagnosable crash.
        r = self.call(
            "awkcap_identity",
            "#!/bin/sh\necho 'usage: awk ...' >&2\nexit 2\n",
        )
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("/awk", r.stdout.strip())


class RealAwkAgreementTest(AwkCapabilityLibTestBase):
    """No stubs: the probe's verdict about THIS machine's real awk, against
    an independent witness of the same ERE shape."""

    def _real_awk_compiles(self, ere):
        prog = '{ if (match($0, /%s/)) hits++ } END { print hits+0 }' % ere
        r = subprocess.run(
            ["awk", prog],
            input="```\n", capture_output=True, text=True,
            env={"PATH": SANDBOX_PATH, "LC_ALL": "C"},
        )
        return r.returncode == 0 and r.stderr == "" and r.stdout.strip() == "1"

    def test_the_canary_verdict_agrees_with_the_historical_fence_opener(self):
        r = self.call("awkcap_canary_ok")
        probe_says_capable = r.returncode == 0
        witness_compiles = self._real_awk_compiles(HISTORICAL_FENCE_OPENER_ERE)
        self.assertEqual(
            witness_compiles, probe_says_capable,
            "the canary and the ERE shape it stands in for must give the same "
            "answer on this machine's real awk -- if they diverge the canary "
            "no longer reproduces the failing shape and the could-not-run "
            f"path guards nothing. probe={r.stdout!r}/{r.stderr!r}",
        )


class ShippedScriptCouldNotRunTestBase(unittest.TestCase):
    """Drives a shipped script with a deliberately incapable `awk` first on
    PATH. Lives HERE rather than in test_memory_lint.py /
    test_migrate_review_headers.py on purpose: those two suites need a
    WORKING awk to say anything at all, so a could-not-run test parked among
    them would be the first casualty of the very condition it exists to
    describe."""

    SCRIPT = None

    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="ccpr-awk-project-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.project)], check=False)
        self.fake_home = Path(tempfile.mkdtemp(prefix="ccpr-awk-home-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.fake_home)], check=False)

    def run_script(self, *args, stub_body=None):
        stub = _stub_dir(stub_body or _panicking_stub())
        self.addCleanup(subprocess.run, ["rm", "-rf", stub], check=False)
        return subprocess.run(
            ["bash", str(self.SCRIPT), str(self.project), *args],
            capture_output=True, text=True,
            env={
                "HOME": str(self.fake_home),
                "PATH": f"{stub}:{SANDBOX_PATH}",
            },
        )


class MemoryLintCouldNotRunTest(ShippedScriptCouldNotRunTestBase):
    """memory-lint.sh is a CHECK in check-all.sh's catalogue, and check-all
    tells could-not-run apart from pass/fail by the REPORT TEXT, never by the
    exit code (scripts/check-all.sh, the `memory-lint` branch). So the
    contract here is the literal marker plus exit 0 -- the same shape
    shellcheck-run.sh already ships."""

    SCRIPT = REPO_ROOT / "scripts" / "memory-lint.sh"

    def setUp(self):
        super().setUp()
        memory = self.project / "docs" / "memory"
        memory.mkdir(parents=True)
        (memory / "MEMORY.md").write_text(
            "# Memory Index\n\n- [Dead](nonexistent.md) — a probe dead link.\n",
            encoding="utf-8",
        )

    def test_the_report_carries_check_alls_could_not_run_marker(self):
        r = self.run_script()
        self.assertIn("the memory-lint check DID NOT RUN", r.stdout,
                      f"stdout={r.stdout!r} stderr={r.stderr!r}")

    def test_the_report_names_the_awk_and_the_ticket(self):
        r = self.run_script()
        self.assertIn("CCP-1179", r.stdout)
        self.assertIn("/awk", r.stdout)

    def test_the_exit_code_is_zero_so_check_all_reads_the_text_not_a_crash(self):
        r = self.run_script()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_the_findings_sections_say_not_evaluated_never_none(self):
        # THE defect CCP-1179 is about: `_none_` under `## Errors (0)` is a
        # claim that nothing was found. Nothing was LOOKED for.
        r = self.run_script()
        self.assertIn("## Errors (", r.stdout)
        self.assertIn("## Warnings (", r.stdout)
        self.assertIn("## Info (", r.stdout)
        self.assertIn("_not evaluated", r.stdout)
        self.assertNotIn("_none_", r.stdout)

    def test_the_operator_is_told_on_stderr_too(self):
        # A report nobody reads is how this stayed invisible for months.
        r = self.run_script()
        self.assertIn("CCP-1179", r.stderr, f"stdout={r.stdout!r}")

    def test_the_summary_line_replaces_the_verdict_it_used_to_invent(self):
        # THE regression, stated as the pair it is: the summary this script
        # printed on a mawk machine is gone, and what stands in its place says
        # what actually happened. The fixture HAS a dead link -- a run that
        # never looked for it must not answer the question either way.
        r = self.run_script()
        self.assertIn("**Summary:** 0 files scanned, 0 findings — could-not-run",
                      r.stdout)
        self.assertNotIn("**Summary:** 0 errors, 0 warnings, 0 info.", r.stdout)

    def test_the_operator_sees_an_explanation_where_the_raw_panic_used_to_be(self):
        r = self.run_script()
        self.assertIn("CCP-1179", r.stdout)
        self.assertNotIn("REcompile", r.stdout)
        self.assertNotIn("REcompile", r.stderr)


class MigrateReviewHeadersCouldNotRunTest(ShippedScriptCouldNotRunTestBase):
    """migrate-review-headers.sh WRITES to files, and its fence tracking is
    the thing that keeps an illustrative `reviewed_head:` line inside a
    ```yaml block from being hoisted into real frontmatter. A scanner that
    cannot see fences does not degrade into "migrates less" -- it degrades
    into "hoists an example value into the field /gate-p5 trusts as ground
    truth". So unlike memory-lint.sh this one must REFUSE, not report."""

    SCRIPT = REPO_ROOT / "scripts" / "migrate-review-headers.sh"

    def setUp(self):
        super().setUp()
        reviews = self.project / "docs" / "reviews"
        reviews.mkdir(parents=True)
        self.report = reviews / "SPRINT-01-review.md"
        self.report.write_text(
            "# Sprint 1 Review\n"
            "\n"
            "reviewer: someone\n"
            "last_updated: 01.01.2026\n"
            "base_commit: abc1234\n"
            "reviewed_head: def5678\n"
            "\n"
            "```yaml\n"
            "reviewed_head: 0000000000000000000000000000000000000000\n"
            "```\n",
            encoding="utf-8",
        )
        self.before = self.report.read_text(encoding="utf-8")

    def test_it_refuses_with_a_non_zero_exit(self):
        r = self.run_script()
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)

    def test_the_refusal_names_the_awk_the_reason_and_the_ticket(self):
        r = self.run_script()
        message = r.stdout + r.stderr
        self.assertIn("DID NOT RUN", message)
        self.assertIn("CCP-1179", message)
        self.assertIn("/awk", message)

    def test_it_writes_nothing(self):
        self.run_script()
        self.assertEqual(self.before, self.report.read_text(encoding="utf-8"),
                         "a refused migration must leave the tree untouched")

    def test_dry_run_refuses_the_same_way(self):
        # --dry-run's whole purpose is to PREVIEW what a real run would do; a
        # preview computed by a blind scanner is a lie about the real run.
        r = self.run_script("--dry-run")
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("CCP-1179", r.stdout + r.stderr)

    def test_the_operator_sees_an_explanation_where_the_raw_panic_used_to_be(self):
        r = self.run_script()
        # The refusal itself, by its documented code, so the absence claims
        # below are made about a run that really took this path.
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("refusing rather than migrating", r.stderr)
        self.assertNotIn("REcompile", r.stderr)
        self.assertNotIn("REcompile", r.stdout)


if __name__ == "__main__":
    unittest.main()
