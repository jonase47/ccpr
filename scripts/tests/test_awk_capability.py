r"""test_awk_capability.py -- CCP-1179: `scripts/lib/awk_capability.sh`, the
shared probe that answers "can the awk that will actually run this repo's
CommonMark block-structure scanners compile and correctly APPLY the regex
constructs they are built out of?", plus the two shipped scripts' responses
when the answer is no.

## Why a probe exists at all

`mawk 1.3.4 20240123` -- the default `/usr/bin/awk` on Debian-family
systems -- carries two independent regex defects, and they fail in opposite
directions:

  * LOUD: an interval quantifier `{n,m}` followed later in the same ERE by a
    parenthesised group aborts the program with `REcompile() - panic: values
    still on machine stack`, exit 100.
  * QUIET: `X{3,}` compiles fine and is then applied as `X{3}`. A fenced
    block closed by a run LONGER than its opener stops closing, and the rest
    of the file is swallowed as fence content. No error, no exit code.

memory-lint.sh's block-structure scanner hit both. The loud one was still
invisible on the two channels automation reads: the scanner runs inside a
process substitution, so the awk child's exit code is unobservable by
construction, and the report said `0 errors, 0 warnings, 0 info` /
`**Exit:** 0` -- a check that parsed nothing reporting clean (KA-G-017's "a
run that verified nothing is not a pass", one level below where that rule
was written).

CCP-1179 rewrote the patterns so that neither defect is reachable. The probe
is the part that stays.

## The probe does NOT ask "does this awk have mawk's bug"

That question has a shelf life: keyed to one vendor defect, it answers no
for mawk forever, including after the patterns that tripped over it are
gone. The library asks the durable question instead -- can this awk run the
constructs we actually ship -- and its canary is therefore derived from the
shipped patterns, not from the bug. The cost is stated honestly in the
library's own docstring: it is a smoke test over constructs, so a future
pattern built from a construct neither canary exercises is not covered.

## Two-sided coverage, and why the stubs are not the whole story

`CanaryVerdictTest`, `CouldNotRunReasonTest` and the two
`*CouldNotRunTest` classes drive the probe and the shipped scripts with STUB
`awk` binaries. A stub is not the real thing (G-127), and it is used here
for one reason: no single machine can exercise both a capable and an
incapable awk with a real binary, and gating either half on the local awk
variant would leave the shipped could-not-run path verified on some machines
and unverified on others.

`RealAwkAgreementTest` is the other half and uses no stub at all. It
compares the probe's verdict about THIS machine's real awk against the
end-to-end truth measured independently: does the real memory-lint.sh
actually find a known dead link? The two are genuinely independent (G-095)
-- two synthetic EREs in a BEGIN block versus 2000 lines of shell and awk
over a Markdown file -- so a canary that drifted into accepting an awk the
scanner cannot use, or rejecting one it can, breaks it.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "lib" / "awk_capability.sh"
MEMORY_LINT = REPO_ROOT / "scripts" / "memory-lint.sh"

# The same sandboxed PATH test_shellcheck_run.py / test_artifact_gate.py use.
# It is also the PATH test_memory_lint.py hands memory-lint.sh, so the awk a
# probe run here resolves is the awk those runs resolve.
SANDBOX_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"



def _stub_dir(script_body):
    """A throwaway directory holding a single executable `awk` shim."""
    tmp = tempfile.mkdtemp(prefix="ccpr-awk-stub-")
    stub = Path(tmp) / "awk"
    stub.write_text(script_body, encoding="utf-8")
    stub.chmod(0o755)
    return tmp


# All four canary checks passed: the answer a capable awk gives.
CAPABLE_STUB = "#!/bin/sh\nprintf '4\\n'\n"

# The QUIET failure class, and the reason the canary counts correct ANSWERS
# rather than merely a successful exit. An awk can compile every canary ERE,
# exit 0, print nothing on stderr -- and still apply one of them wrongly.
# That is not hypothetical: mawk 1.3.4 compiles `X{3,}` and then applies it as
# `X{3}`, so a fenced block closed by a run LONGER than its opener stops
# closing and the rest of the file is swallowed as fence content. No error, no
# exit code, just a scanner that quietly stops finding things.
WRONG_ANSWER_STUB = "#!/bin/sh\nprintf '3\\n'\n"


def _aborting_stub():
    """An awk that aborts on the capability canary and is a real awk for
    everything else.

    Keyed to the canary program's own `# awkcap-canary` marker. That is a
    deliberate, narrow choice: this fixture's job is to exercise how the
    SHIPPED SCRIPTS RESPOND to an awk that cannot run the probe, not to
    re-detect any particular vendor's bug. Whether the probe's verdict is
    itself correct about a real awk is a different question, and
    RealAwkAgreementTest below answers it against the real binary with no
    stub involved.

    Delegating everything else to the machine's real awk is load-bearing: an
    awk that failed on every argv is a machine nobody runs, and it would make
    memory-lint.sh's unrelated date and frontmatter passes die BEFORE the
    probe ever ran, so these tests would be describing a catastrophic-awk
    scenario rather than the dialect gap CCP-1179 is about.

    The panic text is mawk 1.3.4's, byte-for-byte, because that is the failure
    a reader of these tests will have seen. `--version` is answered the way
    the real binary answers it.
    """
    real = shutil.which("awk", path=SANDBOX_PATH)
    assert real, "the sandboxed PATH must contain an awk to delegate to"
    return (
        "#!/bin/sh\n"
        "case \"$1\" in --version|-W*) echo 'mawk 1.3.4 20240123'; exit 0 ;; esac\n"
        "for _a in \"$@\"; do\n"
        "  case \"$_a\" in *awkcap-canary*)\n"
        "    echo 'REcompile() - panic:  values still on machine stack' >&2\n"
        "    exit 100 ;;\n"
        "  esac\n"
        "done\n"
        f"exec {real} \"$@\"\n"
    )


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
        r = self.call("awkcap_canary_ok", _aborting_stub())
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)

    def test_an_awk_that_exits_clean_without_matching_is_not_capable(self):
        # Exit 0 alone is not the question -- see WRONG_ANSWER_STUB's comment.
        r = self.call("awkcap_canary_ok", WRONG_ANSWER_STUB)
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)

    def test_the_panic_text_never_reaches_the_callers_stderr(self):
        # The probe's job is to REPLACE the raw panic with a sentence a human
        # can act on; leaking it too would put the unexplained crash back on
        # the channel the could-not-run message is supposed to own.
        r = self.call("awkcap_canary_ok || true", _aborting_stub())
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
        r = self.call("awkcap_could_not_run_reason", _aborting_stub())
        self.assertEqual(1, len(r.stdout.strip().splitlines()), r.stdout)

    def test_the_reason_names_the_awk_that_was_probed(self):
        # Kept where a companion "...names the ticket" assertion was dropped,
        # and the criterion is FAILURE MODE, not coverage count -- the two are
        # equally redundant by count, so that would not separate them. The
        # shipped-script classes below assert `/awk` and `CCP-1179` side by
        # side (test_the_report_names_the_awk_and_the_ticket,
        # test_the_refusal_names_the_awk_the_reason_and_the_ticket), so both
        # literals are already caught end-to-end.
        #
        # What differs is how each one can BREAK. `CCP-1179` is a constant
        # typed once into one printf: the only way it disappears is someone
        # editing that literal, and an edit is caught everywhere at once.
        # The awk identity is COMPUTED -- `$(awkcap_identity "$awk_bin")` --
        # so it can go missing with the sentence untouched: a dropped
        # interpolation, an argument threaded wrong, an identity lookup that
        # silently yields nothing. That failure deserves a check at the layer
        # that produces it, naming the function, rather than only a report
        # two scripts downstream that says some larger string looks wrong.
        r = self.call("awkcap_could_not_run_reason", _aborting_stub())
        self.assertIn("/awk", r.stdout, "the resolved awk path must be named")

    def test_the_reason_reports_what_the_canary_actually_answered(self):
        # "it failed" is not diagnosable; "[exit 100]" and "[3]" point at two
        # completely different problems, and the second one is invisible in
        # any exit code.
        r = self.call("awkcap_could_not_run_reason", _aborting_stub())
        self.assertIn("[exit 100]", r.stdout)
        r = self.call("awkcap_could_not_run_reason", WRONG_ANSWER_STUB)
        self.assertIn("[3]", r.stdout)


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


class RealAwkAgreementTest(unittest.TestCase):
    """No stubs anywhere: does the probe's verdict about THIS machine's real
    awk agree with whether the real script really works on it?

    This is the half that keeps the canary honest. The canary is a proxy --
    two EREs standing in for the constructs memory-lint.sh's block scanner is
    built out of -- and a proxy can drift from what it proxies. The check
    below compares it against the end-to-end truth, measured independently:
    run the real script over a fixture with exactly one known dead link and
    see whether it finds it.

    The two are genuinely independent (G-095): one compiles two synthetic
    EREs in a BEGIN block, the other runs 2000 lines of shell and awk over a
    Markdown file. On a capable awk both say yes; on an awk that cannot run
    the scanner the probe says no AND the script reports could-not-run, so
    the link is not found. A canary that drifted into accepting an awk the
    scanner cannot use -- or into rejecting one it can -- breaks this.
    """

    KNOWN_DEAD_LINK_INDEX = "# Memory Index\n\n- [Dead](nonexistent.md) — one dead link.\n"

    def _probe_says_capable(self):
        r = subprocess.run(
            ["bash", "-c", '. "$1"; awkcap_canary_ok', "_", str(LIB)],
            capture_output=True, text=True,
            env={"PATH": SANDBOX_PATH, "HOME": os.environ.get("HOME", "/")},
        )
        return r.returncode == 0

    def _script_finds_the_known_dead_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            (root / "docs" / "memory").mkdir(parents=True)
            (root / "docs" / "memory" / "MEMORY.md").write_text(
                self.KNOWN_DEAD_LINK_INDEX, encoding="utf-8")
            home = Path(tmp) / "home"
            home.mkdir()
            r = subprocess.run(
                ["bash", str(MEMORY_LINT), str(root)],
                capture_output=True, text=True,
                env={"HOME": str(home), "PATH": SANDBOX_PATH},
            )
            return "link target" in r.stdout

    def test_the_probes_verdict_agrees_with_whether_the_script_really_works(self):
        probe = self._probe_says_capable()
        reality = self._script_finds_the_known_dead_link()
        self.assertEqual(
            reality, probe,
            "the capability canary and the scanner it stands in for disagree "
            "about this machine's awk. If the probe says capable and the "
            "script finds nothing, the could-not-run path is not guarding "
            "what it claims to; if the probe says incapable and the script "
            "works, the canary is testing a construct the scanner does not "
            "use and is locking out a perfectly good awk.",
        )

    def test_every_anchored_ere_in_the_scanner_compiles_on_this_awk(self):
        """The one-directional companion: when the probe says capable, EVERY
        anchored ERE literal the scanner ships must actually compile here.

        Catches a pattern added later whose construct neither canary covers
        -- on a machine whose awk cannot compile it. It cannot catch the
        same pattern on a machine whose awk can, which is the boundary the
        library's own docstring names and CCP-1129's line of work addresses.
        """
        if not self._probe_says_capable():
            self.skipTest("the probe already reports this awk as incapable")
        source = MEMORY_LINT.read_text(encoding="utf-8")
        # `(?:[^/\n\\]|\\.)*` rather than a plain `[^/\n]*`: the HTML-block-6
        # opener contains `[\/]`, an ESCAPED slash inside a bracket
        # expression, and a naive scan truncates the literal there and then
        # hands awk a runaway regex of its own making.
        eres = re.findall(r"/(\^(?:[^/\n\\]|\\.)*)/", source)
        # A zero-literal guard, deliberately not a floor pin: the number of
        # anchored EREs in the scanner is legitimately volatile CommonMark
        # work, and pinning it would demand a `set` partner naming all 21 --
        # a list that changes with every block-structure tweak and tells
        # nobody anything. The only thing worth asserting here is that the
        # extraction did not go BLIND, which would make the loop below
        # vacuous. Same shape, and same reasoning, as
        # test_bsd_gnu_portability.py's `assertGreater(len(files), 0)`.
        self.assertGreater(
            len(eres), 0,
            "the anchored-ERE extraction enumerated NOTHING in "
            "memory-lint.sh -- that is a broken scan, not a simpler script, "
            "and it would make the per-ERE check below assert over an empty "
            "list",
        )
        broken = []
        for ere in sorted(set(eres)):
            prog = "BEGIN { if (match(\"x\", /%s/)) n = 1 }" % ere
            r = subprocess.run(
                ["awk", prog], input="", capture_output=True, text=True,
                env={"PATH": SANDBOX_PATH, "LC_ALL": "C"},
            )
            if r.returncode != 0 or r.stderr:
                broken.append((ere, r.returncode, r.stderr.strip()))
        self.assertEqual([], broken)


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
        stub = _stub_dir(stub_body or _aborting_stub())
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


class MemoryLintBothCausesTest(ShippedScriptCouldNotRunTestBase):
    """Both could-not-run causes at once -- an empty scope AND an incapable
    awk.

    memory-lint.sh accumulates its causes in an array rather than
    short-circuiting, and shellcheck-run.sh's own array carries the scar of
    why: two separate early-exit blocks meant a machine hitting both only
    ever saw the first, and the second silently disappeared. That the scar
    exists one script over is not evidence this script is free of it, so the
    combination gets its own fixture: NO docs/memory/ and no ~/.claude at all
    (the empty-scope cause), on the stub awk (the dialect cause).
    """

    SCRIPT = REPO_ROOT / "scripts" / "memory-lint.sh"

    # setUp deliberately creates NOTHING under the project: the base class
    # already gives an empty project dir and an empty fake HOME, which is
    # precisely all four targets absent.

    def test_both_causes_are_named_not_just_the_first(self):
        r = self.run_script()
        self.assertIn("the memory-lint check DID NOT RUN", r.stdout)
        self.assertIn("no docs/memory/", r.stdout,
                      f"the empty-scope cause vanished: {r.stdout!r}")
        self.assertIn("CCP-1179", r.stdout,
                      f"the awk-dialect cause vanished: {r.stdout!r}")

    def test_the_two_causes_are_separated_readably(self):
        r = self.run_script()
        self.assertIn("; ", r.stdout,
                      "accumulated causes are joined with '; ' -- the same "
                      "separator shellcheck-run.sh uses")

    def test_it_still_exits_zero(self):
        r = self.run_script()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)


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
            # A SHORT example SHA, deliberately: the shipped-artifact gate
            # (scripts/artifact-gate.sh, via GATE_RE_SECRET_BLOB's
            # `[A-Fa-f0-9]{32,}`) reads a 40-hex run in a tracked file as a
            # possible secret blob, and it is right to -- it cannot tell an
            # illustrative commit id from a token. Seven hex digits is still a
            # valid anchor value by migrate-review-headers.sh's own shape check
            # (`^[0-9a-fA-F]{7,40}$`), so the fixture keeps the property that
            # matters here: a hoistable-looking anchor line sitting INSIDE a
            # fence, where the fence scanner is the only thing stopping it.
            "```yaml\n"
            "reviewed_head: 0badc0f\n"
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
