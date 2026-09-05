"""test_manual_lint.py -- coverage for scripts/manual-lint.sh (WI-0112a).

## Why this exists

No linter in this repository looked at a `kind:`/`parent_index:` documentation
tree at all before this item: `phase-docs-lint.sh` validates a different
schema (`phase`/`subskill`/`status`) under `docs/<phase>/`, `memory-lint.sh`
scans `docs/memory/**` only, and `doc-volume-check.sh` measures size, not
structure. `Manual/` (this repository's own such tree, 22 files) carries
structure that means something and can therefore be wrong -- measured
26.08.2026: `Manual/README.md` calls both `SYSTEM_OVERVIEW.md` and
`SECTIONS_COMMANDS.md` "slim index -> detail files", but `SECTIONS_COMMANDS.md`
links 0 of the 5 chapters that name it as `parent_index`, and
`SYSTEM_OVERVIEW.md` links only 3 of its 10 (`anchored-state`,
`discipline-gate`, `memory-instincts`) -- the other 7 are claimed-as-child by
a `parent_index` their index never links back to. All 15 `parent_index:`
pointers themselves DO resolve -- the forward direction was already correct
before this item, only the reverse direction (check (b) below) was missing.

`scripts/manual-lint.sh` is deliberately generic over ANY root, not hardwired
to `Manual/` -- `install.sh` does not copy `Manual/` into `~/.claude/` (see
`Manual/README.md:2-5`), so a shipped script defaulting to it would find
nothing on every installed CCPR, same defect class 0e76919 fixed for
`phase-docs-lint.sh`'s `PHASE_FOLDERS` default. This module therefore never
reads this repository's own `Manual/` -- like `test_phase_docs_lint.py` never
reads this repository's own `docs/` -- every test drives the shipped script
against a throwaway root (`tempfile.mkdtemp`) built from scratch.

House pattern borrowed from `test_phase_docs_lint.py`: invoke the real entry
point as a subprocess against the shipped script, never sourced internals.

Every mutation-proof test below constructs its own RED state on a synthetic
fixture (G-107/G-109: structural swap, not deletion) since `Manual/` is
read-only for this work item and the real corpus cannot be edited to
manufacture a failure -- see `ReverseLinkMutationProofTest`,
`KindVocabularyMutationProofTest` and `CheckFMutationProofTest`.

## The check letters, and the gap in them (CCP-1152)

The shipped script implements (a), (b), (c) and (f). **(d) and (e) are
RESERVED** by documentation standard v0.7 for the frontmatter reliability
fields, which are not built yet, so the sequence deliberately jumps.
`ReportScopeLineTest.test_the_letters_d_and_e_are_not_claimed` pins that
absence: without it, a future reader "repairing" the numbering by renaming
(f) to (d) would break every reference to the letter at once (the report's
own `**Checks:**` line, templates/PHASE_DOC_SCHEMA.md, this module, and
CHANGELOG.md) while every test stayed green.

Check (f) compares a number in prose against a value derived from a glob,
opt-in via an inline marker on the number's own line. It is therefore a
FALLBACK GUARD, NOT A DETECTOR: it can never find an *unmarked* wrong number,
and `CheckFOneNumberRuleTest.test_an_unmarked_line_carrying_numbers_is_
untouched` pins exactly that. Its silent-direction tests all carry a
deliberately-wrong COMPANION document over the same glob, because "check (f)
ran and correctly stayed silent" and "check (f) never ran" are
indistinguishable from the outside (WI-0128 finding #1).
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

# WI-0126 tranche 5: reuses test_phase_docs_lint.py's read_enum rather than
# growing a near-identical regex for this same "NAME=\"a b c\"" shell-string
# shape (already shared by VALID_STATUS/VALID_PHASES there and LIVING_FILES
# in test_anchor.py). Established cross-test-module pattern
# (test_anchor.py imports read_phase_folders the same way; a fourth relative
# import joins the already-documented set -- CONTRIBUTING.md's "Run the test suite" -- rather
# than a new hazard). Tradeoff: this module now needs `-t .` on `unittest
# discover` too.
from .test_phase_docs_lint import read_enum

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "manual-lint.sh"

# The 19 kind: values manual-lint.sh's VALID_KINDS accepts today, parsed
# from source (WI-0126 tranche 5) rather than retyped -- a retyped copy
# catches the shipped list SHRINKING but not GROWING (a new value is simply
# never swept); KindVocabularyExhaustiveTest's own count-pin test catches
# the shrink side this parse-from-source form cannot. Enumerated
# individually in KindVocabularyExhaustiveTest, same reasoning as
# test_phase_docs_lint.py's VALID_STATUSES/VALID_PHASES: pinning only one
# representative value would leave a later narrowing of the list undetected.
VALID_KINDS = read_enum("VALID_KINDS", SCRIPT_PATH)


def frontmatter_block(kind="detail", parent_index=None, extra_lines=()):
    """Build a minimal frontmatter block. Pass kind=None to omit it."""
    lines = []
    if kind is not None:
        lines.append(f"kind: {kind}")
    if parent_index is not None:
        lines.append(f"parent_index: {parent_index}")
    lines.extend(extra_lines)
    return "---\n" + "\n".join(lines) + "\n---\n"


def doc_text(body="\n# Doc\n\nBody.\n", **fm_kwargs):
    return frontmatter_block(**fm_kwargs) + body


class ManualLintTestBase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="ccpr-manual-lint-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def write_doc(self, rel_path, text):
        """rel_path is relative to self.root, e.g. 'system/agents.md'."""
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_lint(self, *args, root=None):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), str(root if root is not None else self.root), *args],
            capture_output=True, text=True,
        )

    @staticmethod
    def findings(output, heading):
        """Collect the bullet lines of one report section ('Errors' / 'Warnings' / 'Info')."""
        collected = []
        collecting = False
        for line in output.splitlines():
            if line.startswith("## "):
                collecting = line.startswith(f"## {heading} (")
            elif collecting and line.startswith("- "):
                collected.append(line[2:])
        return collected

    @staticmethod
    def files_scanned(output):
        for line in output.splitlines():
            if line.startswith("**Files scanned:**"):
                return int(line.split(":**", 1)[1].strip())
        raise AssertionError(f"no 'Files scanned' line in output: {output!r}")


class CleanCorpusBaselineTest(ManualLintTestBase):
    """The shared negative fixture: an index/child pair that resolves in
    both directions and carries a valid kind: must stay silent. This is what
    makes every other check's "no finding on a clean pair" claim meaningful."""

    def test_valid_index_child_pair_produces_no_findings_and_exits_clean(self):
        self.write_doc("INDEX.md", "# Index\n\n[system/child.md](system/child.md)\n")
        self.write_doc(
            "system/child.md",
            doc_text(kind="detail", parent_index="../INDEX.md"),
        )

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 2)


class CheckAParentIndexResolutionTest(ManualLintTestBase):
    """(a) parent_index -- document-relative first, ROOT-fallback second,
    reusing phase-docs-lint.sh checks (f)/(g)'s cascade (scripts/phase-docs-
    lint.sh:274-297) with this script's ROOT argument standing in for that
    script's PROJECT_DIR."""

    def test_document_relative_resolution_is_silent(self):
        # INDEX.md deliberately does NOT link child.md back -- this test is
        # about check (a) alone, and check (b)'s warning about the missing
        # reverse link is the liveness proof: it can only fire if check (a)'s
        # document-relative resolution actually succeeded and fed the
        # resolved pair into check (b)'s input (WI-0128 finding #1 -- a
        # files-scanned pin would NOT discriminate here, since PARENT_LINKS
        # is populated inside the SAME per-file loop check (a) itself
        # already stayed silent in; only a downstream, check(a)-caused
        # effect proves check (a) ran its resolution logic at all).
        self.write_doc("INDEX.md", "# Index\n")
        self.write_doc(
            "system/child.md",
            doc_text(parent_index="../INDEX.md"),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        infos = self.findings(result.stdout, "Info")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("parent_index=" in e for e in errors), errors)
        self.assertEqual(infos, [], infos)
        self.assertTrue(
            any("does not link back to system/child.md" in w for w in warnings),
            warnings,
        )

    def test_root_fallback_resolution_is_info_not_error(self):
        self.write_doc("INDEX.md", "# Index\n")
        self.write_doc(
            "system/child.md",
            # No "../" prefix -- misses document-relative, hits ROOT-relative.
            doc_text(parent_index="INDEX.md"),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        infos = self.findings(result.stdout, "Info")
        self.assertFalse(any("parent_index=" in e for e in errors), errors)
        self.assertTrue(
            any(
                "child.md" in i and "parent_index='INDEX.md'" in i and "root fallback" in i
                for i in infos
            ),
            infos,
        )

    def test_resolvable_at_neither_base_is_reported_as_error(self):
        self.write_doc(
            "system/child.md",
            doc_text(parent_index="GHOST_INDEX.md"),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any(
                "child.md" in e
                and "parent_index='GHOST_INDEX.md' points to non-existent file" in e
                for e in errors
            ),
            errors,
        )


class CheckBReverseLinkTest(ManualLintTestBase):
    """(b) the reverse direction -- an index resolved via a working
    parent_index: must itself link the claiming file back (a markdown link
    whose destination is the document-relative path from the index's own
    directory to the child), or the pair is reported as a warning."""

    def test_index_that_links_back_produces_no_warning(self):
        # A companion pair that does NOT link back is the liveness proof
        # (WI-0128 finding #1): check (b) runs in its own pass AFTER the
        # per-file loop, entirely decoupled from files_scanned -- a
        # files-scanned pin stays correct even with this whole pass
        # deleted, exactly the "commit anchor family" trap already
        # recorded for phase-docs-lint.sh (docs/memory/senior-developer).
        # The companion's warning firing is what proves the pass executed
        # at all; the absence assertion for the real pair is preserved
        # unchanged below it.
        self.write_doc("INDEX.md", "# Index\n\nSee [system/child.md](system/child.md).\n")
        self.write_doc("system/child.md", doc_text(parent_index="../INDEX.md"))
        self.write_doc("system/unlinked.md", doc_text(parent_index="../INDEX.md"))

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("system/child.md" in w for w in warnings), warnings)
        self.assertTrue(
            any("does not link back to system/unlinked.md" in w for w in warnings),
            warnings,
        )

    def test_index_that_does_not_link_back_is_reported_as_warning(self):
        self.write_doc("INDEX.md", "# Index\n\nNo links to any chapter here.\n")
        self.write_doc("system/child.md", doc_text(parent_index="../INDEX.md"))

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertTrue(
            any(
                "INDEX.md" in w
                and "does not link back to system/child.md" in w
                and "system/child.md" in w
                for w in warnings
            ),
            warnings,
        )
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)

    def test_link_with_extra_text_around_it_is_still_recognised(self):
        """The corpus style this check's substring match is built for --
        Manual/SYSTEM_OVERVIEW.md's real links read like
        `Details: [system/discipline-gate.md](system/discipline-gate.md)`,
        never a bare link on its own line."""
        # Same companion-pair liveness proof as
        # CheckBReverseLinkTest.test_index_that_links_back_produces_no_warning
        # above (WI-0128 finding #1) -- check (b)'s own pass is decoupled
        # from files_scanned, so only a companion that DOES fire proves the
        # pass ran at all.
        self.write_doc(
            "INDEX.md",
            "# Index\n\n"
            "| Script | Details |\n|---|---|\n"
            "| `x.sh` | See [system/child.md](system/child.md) for more. |\n",
        )
        self.write_doc("system/child.md", doc_text(parent_index="../INDEX.md"))
        self.write_doc("system/unlinked.md", doc_text(parent_index="../INDEX.md"))

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("system/child.md" in w for w in warnings), warnings)
        self.assertTrue(
            any("does not link back to system/unlinked.md" in w for w in warnings),
            warnings,
        )


class ReverseLinkRaceStabilityTest(ManualLintTestBase):
    """Check (b)'s reverse-link match reads the resolved index's content
    once per index and greps it for the expected link -- a construct that
    is racy under `set -o pipefail` when the grep sits on the RECEIVING end
    of a pipe: `grep -qF` exits the instant it finds a match, the producer
    upstream can still be mid-write, gets SIGPIPE, exits 141, and under
    pipefail that 141 becomes the PIPELINE's exit status even though grep
    itself found the pattern and returned 0 -- turning a real hit into a
    reported miss. Six consecutive manual runs against an unchanged tree
    (0, 1, 2, 3, 0, 1 findings) first surfaced this; a control isolating the
    mechanism (`printf | grep -qF` vs. a here-string) measured a 16%
    per-run false-negative rate at ~37 KB of index content with the match
    near the top -- reproduced in-repo at this fixture's exact size.

    A single assertion proves nothing against a probabilistic defect: the
    lint runs N=50 times over ONE legitimately-linking index/child pair,
    and every run must report zero warnings. At the measured 16% per-run
    failure rate, a still-racy build's probability of passing all 50 runs
    by chance is (1-0.16)**50 ~= 0.016% -- the residual flake probability
    of this test itself (a false RED on a genuinely fixed build, from the
    complementary tail of the same distribution, is the same order)."""

    RACE_STABILITY_RUNS = 50

    def setUp(self):
        super().setUp()
        # ~37 KB, matching link near the top followed by filler -- the size
        # this repository measured a 16% per-run reproduction rate at
        # (see class docstring). Small enough to keep the N=50 sweep fast
        # (~60 ms/run measured), large enough to exceed the pipe buffer
        # `printf` writes into, which is what lets `grep -qF` finish and
        # SIGPIPE the still-writing producer before it has flushed the rest.
        lines = ["# Index\n\n", "See [system/child.md](system/child.md) for details.\n\n"]
        for i in range(500):
            lines.append(
                f"Filler line {i} with some reasonably long padding text to grow this file.\n"
            )
        self.write_doc("INDEX.md", "".join(lines))
        self.write_doc("system/child.md", doc_text(parent_index="../INDEX.md"))

    def test_reverse_link_check_is_stable_across_repeated_runs(self):
        finding_counts = []
        for _ in range(self.RACE_STABILITY_RUNS):
            result = self.run_lint()
            finding_counts.append(
                (
                    len(self.findings(result.stdout, "Errors")),
                    len(self.findings(result.stdout, "Warnings")),
                )
            )

        self.assertEqual(
            [(0, 0)] * self.RACE_STABILITY_RUNS,
            finding_counts,
            f"expected zero errors/warnings on every one of "
            f"{self.RACE_STABILITY_RUNS} runs against an unchanged, "
            f"legitimately-linking fixture; got {finding_counts}",
        )


class ReverseLinkMutationProofTest(ManualLintTestBase):
    """Mutation proof for check (b), structural not presence-based
    (G-107/G-109): a SWAP, not a deletion. `INDEX.md` genuinely links
    `system/real-child.md` back; a SIBLING file `OTHER.md` exists but links
    nothing. Point `system/real-child.md`'s parent_index at `OTHER.md`
    instead of `INDEX.md` -- `OTHER.md` EXISTS, so check (a) stays silent
    (a dead pointer would make check (a) fire too and prove nothing about
    check (b) specifically); check (b) must fire because `OTHER.md` does
    not link the child back. Reverting the swap must silence it again."""

    def setUp(self):
        super().setUp()
        self.write_doc("INDEX.md", "# Index\n\n[system/real-child.md](system/real-child.md)\n")
        self.write_doc("OTHER.md", "# Other\n\nUnrelated content, no links.\n")
        self.child_path = self.write_doc(
            "system/real-child.md",
            doc_text(parent_index="../INDEX.md"),
        )

    def test_pointing_at_the_true_parent_is_silent(self):
        # Companion liveness proof (WI-0128 finding #1), same reasoning as
        # CheckBReverseLinkTest above: a file scoped to THIS test only (not
        # setUp, so the sibling swap test below is unaffected) whose
        # parent_index resolves but is never linked back -- its warning
        # firing proves check (b)'s pass ran at all.
        self.write_doc("system/broken-child.md", doc_text(parent_index="../INDEX.md"))

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("real-child.md" in w for w in warnings), warnings)
        self.assertTrue(any("broken-child.md" in w for w in warnings), warnings)

    def test_swapping_to_an_existing_non_parent_file_fires_check_b_but_not_check_a(self):
        self.child_path.write_text(
            doc_text(parent_index="../OTHER.md"), encoding="utf-8",
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("parent_index=" in e for e in errors), errors)
        self.assertTrue(
            any(
                "OTHER.md" in w and "does not link back to system/real-child.md" in w
                for w in warnings
            ),
            warnings,
        )

        # Revert the swap -- the warning must disappear again, proving the
        # finding tracks the swapped pointer and not some fixed leftover state.
        self.child_path.write_text(
            doc_text(parent_index="../INDEX.md"), encoding="utf-8",
        )
        reverted = self.run_lint()
        self.assertEqual(self.findings(reverted.stdout, "Warnings"), [], reverted.stdout)


class CheckCKindVocabularyTest(ManualLintTestBase):
    """(c) kind: -- opt-in (only fires when the field is actually set),
    checked against the KNOWN (not ALLOWED) vocabulary documented in
    templates/PHASE_DOC_SCHEMA.md's `## kind` section (WI-0112a follow-up,
    measured 26.08.2026, no separate WI filed). An
    unrecognised value is a WARNING, not an error: CCPR cannot enumerate
    every document genre a downstream project legitimately invents (same
    open-enum precedent as memory-lint.sh check (c)'s Tier-2 `type:`
    field)."""

    def test_unknown_kind_value_is_reported_as_a_warning_not_an_error(self):
        self.write_doc("bogus.md", doc_text(kind="not-a-real-kind"))

        result = self.run_lint()

        self.assertEqual(result.returncode, 1, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertEqual(errors, [], errors)
        self.assertTrue(
            any(
                "bogus.md" in w
                and "kind='not-a-real-kind' is not in the known vocabulary" in w
                for w in warnings
            ),
            warnings,
        )

    def test_known_kind_value_is_not_reported(self):
        self.write_doc("known.md", doc_text(kind="detail"))

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)

    def test_document_without_kind_is_not_reported(self):
        self.write_doc("no-kind.md", doc_text(kind=None))

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)


class KindVocabularyExhaustiveTest(ManualLintTestBase):
    """Every one of the 19 measured kind: values is individually accepted --
    pinning only one representative value would leave a later narrowing of
    the list undetected (same reasoning as test_phase_docs_lint.py's
    VALID_STATUSES/VALID_PHASES sweeps)."""

    def test_valid_kinds_count_is_pinned_at_nineteen(self):
        # WI-0126 tranche 5: VALID_KINDS is now parsed from source, which
        # alone only catches a value being ADDED. This pin catches one
        # being REMOVED -- the retyped copy's converse blind spot.
        self.assertEqual(19, len(VALID_KINDS))

    def test_every_valid_kind_value_is_accepted(self):
        for i, kind in enumerate(VALID_KINDS):
            self.write_doc(f"kind-{i}.md", doc_text(kind=kind))

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), len(VALID_KINDS))


class KindVocabularyMutationProofTest(ManualLintTestBase):
    """Mutation proof for check (c), structural not presence-based
    (G-107/G-109): a value ADJACENT to a real one (a plausible typo),
    not an arbitrary garbage string -- proving the vocabulary match is
    exact rather than merely "looks roughly right"."""

    def setUp(self):
        super().setUp()
        self.doc_path = self.write_doc("adjacent.md", doc_text(kind="sub-index"))

    def test_real_value_is_silent(self):
        # Companion liveness proof (WI-0128 finding #1): a valid kind is
        # indistinguishable, from the OUTSIDE, between "check (c) ran and
        # correctly stayed silent" and "check (c) never ran at all" --
        # both produce zero warnings. An obviously-invalid companion that
        # DOES fire is what proves the vocabulary check executed.
        self.write_doc("companion.md", doc_text(kind="bogus-kind-for-liveness"))

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("adjacent.md" in w for w in warnings), warnings)
        self.assertTrue(any("companion.md" in w for w in warnings), warnings)

    def test_adjacent_typo_fires_and_reverting_silences_it_again(self):
        self.doc_path.write_text(doc_text(kind="sub-indexes"), encoding="utf-8")

        mutated = self.run_lint()
        self.assertEqual(mutated.returncode, 1, mutated.stdout)
        errors = self.findings(mutated.stdout, "Errors")
        warnings = self.findings(mutated.stdout, "Warnings")
        self.assertEqual(errors, [], errors)
        self.assertTrue(
            any("adjacent.md" in w and "kind='sub-indexes'" in w for w in warnings),
            warnings,
        )

        self.doc_path.write_text(doc_text(kind="sub-index"), encoding="utf-8")
        reverted = self.run_lint()
        self.assertEqual(reverted.returncode, 0, reverted.stdout)
        self.assertEqual(self.findings(reverted.stdout, "Errors"), [], reverted.stdout)
        self.assertEqual(self.findings(reverted.stdout, "Warnings"), [], reverted.stdout)


class ReportScopeLineTest(ManualLintTestBase):
    """The report names its scope of CHECKS -- WI-0090/WI-0121 convention,
    landed twice already (artifact-gate.sh's header,
    scripts/phase-docs-lint.sh:165-190)."""

    def test_report_names_every_shipped_check(self):
        self.write_doc("x.md", doc_text())

        result = self.run_lint()

        checks_line = next(
            (line for line in result.stdout.splitlines() if line.startswith("**Checks:**")),
            None,
        )
        self.assertIsNotNone(checks_line, result.stdout)
        self.assertIn("(a)", checks_line)
        self.assertIn("(b)", checks_line)
        self.assertIn("(c)", checks_line)
        self.assertIn("(f)", checks_line)

    def test_the_letters_d_and_e_are_not_claimed(self):
        """The gap between (c) and (f) is deliberate: (d) and (e) are
        RESERVED by documentation standard v0.7 for the frontmatter
        reliability fields, which are not built yet. Pinning the absence
        here so that nobody "repairs" the sequence in a year by renaming
        (f) to (d) and breaking every reference to it."""
        self.write_doc("x.md", doc_text())

        result = self.run_lint()

        checks_line = next(
            (line for line in result.stdout.splitlines() if line.startswith("**Checks:**")),
            None,
        )
        self.assertIsNotNone(checks_line, result.stdout)
        self.assertNotIn("(d)", checks_line)
        self.assertNotIn("(e)", checks_line)


class EmptyScopeTest(ManualLintTestBase):
    """An empty scan says so on stderr, not silently (WI-0090/WI-0121) --
    exercised for BOTH ways a scope can end up empty: the root does not
    exist at all, and the root exists but carries no markdown files. Both
    still render the full report (Files scanned: 0) and exit 0 -- an empty
    scope on a generic, not-hardwired-to-Manual/ script is the NORMAL state
    on a freshly installed CCPR (0e76919's reasoning, translated to this
    script's own generic root)."""

    def test_nonexistent_root_exits_0_with_a_stderr_notice(self):
        ghost_root = self.root / "does-not-exist"

        result = self.run_lint(root=ghost_root)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 0)
        self.assertIn(str(ghost_root), result.stderr)
        self.assertIn("does not exist", result.stderr)

    def test_existing_empty_root_exits_0_with_a_stderr_notice(self):
        result = self.run_lint()  # self.root exists (mkdtemp) but has no .md files

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.files_scanned(result.stdout), 0)
        self.assertIn("no markdown files found", result.stderr)
        self.assertIn(str(self.root), result.stderr)

    def test_default_root_is_the_current_working_directory(self):
        """No positional argument at all -- ROOT defaults to $(pwd), same
        convention as phase-docs-lint.sh's PROJECT_DIR default."""
        self.write_doc("x.md", doc_text())

        result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            capture_output=True, text=True, cwd=self.root,
        )

        self.assertEqual(self.files_scanned(result.stdout), 1)


# ---------------------------------------------------------------------------
# Check (f) -- derived-count markers
# ---------------------------------------------------------------------------

def marker(verb, glob):
    """The markdown marker check (f) reads, exactly as it appears in prose."""
    return "<!-- " + "pin: %s %s -->" % (verb, glob)


def pinned(text, verb, glob):
    """One prose line carrying a claim and the marker that guards it."""
    return "%s %s\n" % (text, marker(verb, glob))


class CheckFMarkerBase(ManualLintTestBase):
    """Shared fixture vocabulary for check (f): a corpus of NON-markdown
    assets to count, so the counted set is independent of how many .md
    documents the lint itself happens to be scanning."""

    def write_assets(self, folder, n, ext="txt"):
        for i in range(n):
            path = self.root / folder / ("asset-%d.%s" % (i, ext))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x\n", encoding="utf-8")

    def pinned_doc(self, rel_path, text, verb, glob, prefix="Intro paragraph.\n\n"):
        return self.write_doc(
            rel_path,
            doc_text(body="\n# Doc\n\n" + prefix + pinned(text, verb, glob)),
        )


class CheckFCountVerbTest(CheckFMarkerBase):
    """(f) `count` -- the derived value must EQUAL the single number on the
    marked line."""

    def test_a_count_that_agrees_with_the_glob_is_silent(self):
        # Companion liveness proof: a second, deliberately wrong claim over
        # the SAME glob. Silence on the correct document is otherwise
        # indistinguishable from check (f) never running at all.
        self.write_assets("assets", 3)
        self.pinned_doc("ok.md", "There are 3 assets.", "count", "assets/*.txt")
        self.pinned_doc("wrong.md", "There are 9 assets.", "count", "assets/*.txt")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("ok.md" in e for e in errors), errors)
        self.assertTrue(any("wrong.md" in e for e in errors), errors)

    def test_a_count_that_disagrees_is_an_error_and_exits_2(self):
        self.write_assets("assets", 3)
        self.pinned_doc("claim.md", "There are 5 assets.", "count", "assets/*.txt")

        result = self.run_lint()

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("claim.md" in e and "derives 3" in e and "states 5" in e for e in errors),
            errors,
        )


class CheckFFloorVerbTest(CheckFMarkerBase):
    """(f) `floor` -- the derived value must be >= the number on the line.
    A floor stays silent while its subject GROWS; it fires only when the
    derived value falls below the claim. This verb exists because README.md's
    already-settled test-count decision ("2,600+ tests") needs >= semantics."""

    def test_a_floor_exactly_at_the_derived_value_is_silent(self):
        self.write_assets("assets", 3)
        self.pinned_doc("ok.md", "At least 3 assets.", "floor", "assets/*.txt")
        self.pinned_doc("wrong.md", "At least 9 assets.", "floor", "assets/*.txt")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("ok.md" in e for e in errors), errors)
        self.assertTrue(any("wrong.md" in e for e in errors), errors)

    def test_a_floor_below_the_derived_value_is_silent(self):
        self.write_assets("assets", 5)
        self.pinned_doc("ok.md", "More than 2 assets.", "floor", "assets/*.txt")
        self.pinned_doc("wrong.md", "More than 8 assets.", "floor", "assets/*.txt")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("ok.md" in e for e in errors), errors)
        self.assertTrue(any("wrong.md" in e for e in errors), errors)

    def test_a_floor_above_the_derived_value_is_an_error(self):
        self.write_assets("assets", 3)
        self.pinned_doc("claim.md", "At least 4 assets.", "floor", "assets/*.txt")

        result = self.run_lint()

        self.assertEqual(result.returncode, 2, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("claim.md" in e and "derives 3" in e and "4" in e for e in errors),
            errors,
        )

    def test_the_same_number_that_passes_as_a_floor_fails_as_a_count(self):
        """The two verbs are not interchangeable -- the discriminating
        case is derived > declared, which `floor` accepts and `count`
        rejects. Without this pair, a `count` implemented as `>=` would
        pass every other test in this module."""
        self.write_assets("assets", 5)
        self.pinned_doc("floored.md", "At least 2 assets.", "floor", "assets/*.txt")
        self.pinned_doc("counted.md", "There are 2 assets.", "count", "assets/*.txt")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("floored.md" in e for e in errors), errors)
        self.assertTrue(any("counted.md" in e for e in errors), errors)


class CheckFGlobScopeTest(CheckFMarkerBase):
    """(f) glob resolution -- document-relative first, ROOT-fallback second
    (check (a)'s cascade, reused not reinvented), and a glob that matches
    NOTHING is an error: a guard that silently checks nothing is worse than
    no guard at all (KA-G-017, "a check run that reports no scope is not a
    pass"). The milder reading -- warn, because a downstream project may not
    have the path -- was considered and rejected: if the path does not exist
    there, the claim in front of the marker is unsupported for that project
    too, and the error points at the line that should have been adapted or
    deleted at project init."""

    def test_a_glob_matching_zero_files_is_an_error(self):
        self.pinned_doc("claim.md", "There are 3 assets.", "count", "ghost/*.txt")

        result = self.run_lint()

        self.assertEqual(result.returncode, 2, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("claim.md" in e and "ghost/*.txt" in e and "matches no files" in e
                for e in errors),
            errors,
        )

    def test_a_document_relative_glob_resolves_without_an_info_line(self):
        self.write_assets("chapters/assets", 2)
        self.pinned_doc("chapters/doc.md", "There are 2 assets.", "count", "assets/*.txt")
        # Liveness companion: same directory, deliberately wrong number.
        self.pinned_doc("chapters/wrong.md", "There are 7 assets.", "count", "assets/*.txt")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("chapters/doc.md" in e for e in errors), errors)
        self.assertTrue(any("chapters/wrong.md" in e for e in errors), errors)
        self.assertEqual(self.findings(result.stdout, "Info"), [], result.stdout)

    def test_a_root_fallback_glob_resolves_and_is_reported_as_info(self):
        # `assets/` sits at the ROOT, not next to the document -- the same
        # fallback check (a) reports as `info` for parent_index.
        self.write_assets("assets", 2)
        self.pinned_doc("chapters/doc.md", "There are 2 assets.", "count", "assets/*.txt")

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        infos = self.findings(result.stdout, "Info")
        self.assertTrue(
            any("chapters/doc.md" in i and "assets/*.txt" in i and "root fallback" in i
                for i in infos),
            infos,
        )

    def test_a_root_fallback_glob_still_compares_the_number(self):
        """The fallback resolves the SCOPE; it does not excuse the claim."""
        self.write_assets("assets", 2)
        self.pinned_doc("chapters/doc.md", "There are 6 assets.", "count", "assets/*.txt")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("chapters/doc.md" in e and "derives 2" in e for e in errors), errors,
        )


class CheckFOneNumberRuleTest(CheckFMarkerBase):
    """(f) exactly ONE number on the marked line, the marker comment itself
    excluded. Set-membership semantics ("the derived value must appear among
    the numbers on the line") has a hole: `115 commands plus 1 = 116 total`
    would pass on the presence of 116 while 115 is wrong. The one-number rule
    closes it and forces simple, pinnable sentences."""

    def test_two_numbers_on_the_marked_line_is_an_error(self):
        self.write_assets("assets", 3)
        self.pinned_doc(
            "claim.md", "There are 3 assets in 1 folder.", "count", "assets/*.txt",
        )

        result = self.run_lint()

        self.assertEqual(result.returncode, 2, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("claim.md" in e and "2 numbers" in e for e in errors), errors,
        )

    def test_no_number_on_the_marked_line_is_an_error(self):
        self.write_assets("assets", 3)
        self.pinned_doc("claim.md", "There are several assets.", "count", "assets/*.txt")

        result = self.run_lint()

        self.assertEqual(result.returncode, 2, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("claim.md" in e and "0 numbers" in e for e in errors), errors,
        )

    def test_digits_inside_the_marker_comment_are_not_counted(self):
        # `assets2/*.txt` carries a digit. If the marker were not excluded
        # from the number scan, this line would read as two numbers (3, 2)
        # and fail the one-number rule instead of comparing 3 against 3.
        self.write_assets("assets2", 3)
        self.pinned_doc("claim.md", "There are 3 assets.", "count", "assets2/*.txt")

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)

    def test_an_unmarked_line_carrying_numbers_is_untouched(self):
        """Check (f) is opt-in by marker, and therefore a FALLBACK GUARD,
        not a detector: it can never find an unmarked wrong number."""
        self.write_doc(
            "prose.md",
            doc_text(body="\n# Doc\n\nCCPR ships 999 commands and 3 agents.\n"),
        )

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)


class CheckFNumberFormTest(CheckFMarkerBase):
    """(f) number parsing -- a number is its VALUE, not its literal. A
    thousands separator (`2,600`) is part of one number; a trailing `+`
    (`2,600+ tests`, README.md's floor form) is prose ornament and neither
    creates nor alters a number."""

    def test_a_thousands_separator_and_a_trailing_plus_read_as_one_number(self):
        # 1000 real files, deliberately: this is the only POSITIVE proof that
        # a separated number parses to its value -- the sibling test below
        # proves the same point from the error text with 3 files, but an
        # error message is the failing direction. A `1,000` claim can only be
        # SATISFIED by a corpus of 1000. Measured cost ~50 ms.
        self.write_assets("assets", 1000)
        self.pinned_doc("ok.md", "Over 1,000+ assets.", "floor", "assets/*.txt")

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)

    def test_a_separated_number_is_compared_by_value_not_by_its_first_group(self):
        # 3 assets against a claimed floor of 1,000: the error must name
        # 1000, not 1 (which would pass) and not "2 numbers" (which would
        # mean the separator split the token).
        self.write_assets("assets", 3)
        self.pinned_doc("claim.md", "Over 1,000 assets.", "floor", "assets/*.txt")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(any("claim.md" in e and "1000" in e for e in errors), errors)
        self.assertFalse(any("numbers" in e for e in errors), errors)


class CheckFVerbVocabularyTest(CheckFMarkerBase):
    """(f) the marker's own grammar. `count` and `floor` are the whole
    vocabulary; anything else is an ERROR, not a silent skip -- a typo'd verb
    would otherwise disable the guard it was written to install."""

    def test_an_unknown_verb_is_an_error(self):
        self.write_assets("assets", 3)
        self.pinned_doc("claim.md", "There are 3 assets.", "eq", "assets/*.txt")

        result = self.run_lint()

        self.assertEqual(result.returncode, 2, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("claim.md" in e and "'eq'" in e for e in errors), errors,
        )

    def test_a_marker_without_a_glob_is_an_error(self):
        self.write_doc(
            "claim.md",
            doc_text(body="\n# Doc\n\nThere are 3 assets. <!-- " + "pin: count -->\n"),
        )

        result = self.run_lint()

        self.assertEqual(result.returncode, 2, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("claim.md" in e and "malformed" in e for e in errors), errors,
        )


class CheckFFencedBlockTest(CheckFMarkerBase):
    """(f) a marker inside a fenced code block is DOCUMENTATION OF the
    marker, not a live one. This repository has been bitten by exactly this
    class before -- see the check (n) history in CHANGELOG.md, where an
    extractor reported bracketed text inside a code block as a dead link,
    and freeze-phase-docs.sh hoisted a fenced example header as a real
    `reviewed_head` value."""

    def test_a_marker_inside_a_fence_does_not_fire(self):
        self.write_assets("assets", 3)
        self.write_doc(
            "guide.md",
            doc_text(
                body="\n# Guide\n\nWrite it like this:\n\n```markdown\n"
                + pinned("There are 999 assets.", "count", "ghost/*.txt")
                + "```\n\n"
                # Liveness companion OUTSIDE the fence, same document: its
                # error is what proves the fence skipped a line rather than
                # check (f) never running on this file at all.
                + pinned("There are 8 assets.", "count", "assets/*.txt")
            ),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("999" in e or "ghost" in e for e in errors), errors)
        self.assertTrue(any("derives 3" in e and "states 8" in e for e in errors), errors)

    def test_a_marker_after_a_closed_fence_still_fires(self):
        self.write_assets("assets", 3)
        self.write_doc(
            "guide.md",
            doc_text(
                body="\n# Guide\n\n```\nsome code\n```\n\n"
                + pinned("There are 8 assets.", "count", "assets/*.txt")
            ),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(any("derives 3" in e and "states 8" in e for e in errors), errors)

    def test_a_tilde_fence_containing_a_backtick_fence_stays_one_block(self):
        """A fence only closes with its OWN delimiter character, at least as
        long as the opener -- the rule memory-lint.sh's own fence state
        machine already implements."""
        self.write_assets("assets", 3)
        self.write_doc(
            "guide.md",
            doc_text(
                body="\n# Guide\n\n~~~markdown\n```\n"
                + pinned("There are 999 assets.", "count", "ghost/*.txt")
                + "```\n~~~\n\n"
                + pinned("There are 8 assets.", "count", "assets/*.txt")
            ),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("999" in e or "ghost" in e for e in errors), errors)
        self.assertTrue(any("derives 3" in e and "states 8" in e for e in errors), errors)


class CheckFMutationProofTest(CheckFMarkerBase):
    """Mutation proof for check (f), structural not presence-based
    (G-107/G-109): the claimed number is moved to a value ADJACENT to the
    true one, so the marker, the glob and the sentence shape all survive
    intact and only the comparison can be what fires. Reverting must
    silence it again."""

    def setUp(self):
        super().setUp()
        self.write_assets("assets", 4)
        self.doc_path = self.pinned_doc(
            "claim.md", "There are 4 assets.", "count", "assets/*.txt",
        )

    def test_the_true_number_is_silent(self):
        # Companion liveness proof: a valid claim is indistinguishable from
        # the OUTSIDE between "check (f) ran and stayed silent" and "check
        # (f) never ran". A wrong companion that DOES fire settles it.
        self.pinned_doc("companion.md", "There are 40 assets.", "count", "assets/*.txt")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("claim.md" in e for e in errors), errors)
        self.assertTrue(any("companion.md" in e for e in errors), errors)

    def test_an_adjacent_number_fires_and_reverting_silences_it_again(self):
        self.doc_path.write_text(
            doc_text(
                body="\n# Doc\n\nIntro paragraph.\n\n"
                + pinned("There are 5 assets.", "count", "assets/*.txt")
            ),
            encoding="utf-8",
        )

        mutated = self.run_lint()
        self.assertEqual(mutated.returncode, 2, mutated.stdout)
        self.assertTrue(
            any("claim.md" in e and "derives 4" in e and "states 5" in e
                for e in self.findings(mutated.stdout, "Errors")),
            mutated.stdout,
        )

        self.doc_path.write_text(
            doc_text(
                body="\n# Doc\n\nIntro paragraph.\n\n"
                + pinned("There are 4 assets.", "count", "assets/*.txt")
            ),
            encoding="utf-8",
        )
        reverted = self.run_lint()
        self.assertEqual(reverted.returncode, 0, reverted.stdout)
        self.assertEqual(self.findings(reverted.stdout, "Errors"), [], reverted.stdout)


class CheckFStrayArrowTest(CheckFMarkerBase):
    """A literal `-->` appearing on the marked line BEFORE the marker's own
    `<!--` must not confuse the markup stripper.

    Found by an adversarial probe, not by the tests above. The first
    implementation took the text before the first `<!--` as the prose head but
    then advanced past the first `-->` ANYWHERE on the line; with a stray arrow
    earlier than the opener those two ends are not a pair, so the span between
    the arrow and the opener is emitted TWICE.

    The reachable failure direction is a false ERROR, and only that -- measured,
    not assumed. The stripper's loop runs again on the remainder and does strip
    the marker comment eventually, so the marker's own glob digits never survive
    into the scan; and the duplication can only ADD occurrences, never remove
    one. So a legitimate single-number line is rejected as carrying two, which
    is what this test pins. An earlier draft of this class also asserted a
    false-PASS direction (a numberless line adopting a digit out of its own
    glob); that case was traced through the buggy stripper by hand, found NOT
    reachable, and the test deleted rather than kept as a passing decoration --
    it would have been green against both the broken and the fixed code."""

    def test_a_stray_arrow_before_the_marker_does_not_duplicate_the_prose(self):
        self.write_assets("assets", 3)
        # The discriminating shape: the number sits BETWEEN the stray arrow
        # and the marker, i.e. inside exactly the span the mispaired ends
        # duplicate. A number before the arrow would be in the prose head
        # only and would survive the defect unharmed.
        self.pinned_doc(
            "arrow.md",
            "Flow A --> B, so there are 3 assets.",
            "count", "assets/*.txt",
        )
        # Liveness companion over the same glob and the same sentence shape.
        self.pinned_doc(
            "arrow-wrong.md",
            "Flow A --> B, so there are 9 assets.",
            "count", "assets/*.txt",
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("arrow.md:" in e for e in errors), errors)
        self.assertTrue(
            any("arrow-wrong.md" in e and "derives 3" in e and "states 9" in e
                for e in errors),
            errors,
        )

    def test_an_unterminated_comment_after_the_marker_is_left_as_prose(self):
        """The stripper must not consume the rest of the line when a second,
        unterminated `<!--` follows a complete marker -- the loop has to stop
        at an opener it cannot pair, not treat the tail as stripped."""
        self.write_assets("assets", 3)
        self.pinned_doc(
            "dangling.md", "There are 3 assets.", "count", "assets/*.txt", prefix="",
        )
        path = self.root / "dangling.md"
        path.write_text(
            path.read_text(encoding="utf-8").rstrip("\n") + " <!-- dangling\n",
            encoding="utf-8",
        )

        result = self.run_lint()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)


class CheckFCommentSpanTest(CheckFMarkerBase):
    """A marker is recognised as a COMMENT SPAN, from the same walk that
    strips comments before the number scan -- not by a separate search over
    the raw line.

    The distinction is the whole finding of the review round: detecting the
    marker on the RAW line while counting numbers on the STRIPPED line means
    two different readings of the same text, and they disagree exactly where
    an outer comment encloses the marker. `<!-- TODO ... <!-- pin: ... -->`
    is ONE html comment (a comment ends at the first `-->`), so the marker is
    commented out and must be inert -- the raw-line search saw a marker
    anyway and then reported the enclosing comment's now-empty prose as
    "0 numbers"."""

    def test_a_marker_nested_inside_an_outer_comment_is_inert(self):
        self.write_assets("assets", 3)
        self.write_doc(
            "nested.md",
            doc_text(
                body="\n# Doc\n\n"
                "<!-- TODO revisit: there are 3 assets " + marker("count", "assets/*.txt")
                + "\n\n"
                # Liveness companion on its own line, OUTSIDE any comment.
                + pinned("There are 8 assets.", "count", "assets/*.txt")
            ),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("numbers" in e for e in errors), errors)
        self.assertTrue(any("derives 3" in e and "states 8" in e for e in errors), errors)

    def test_both_markers_on_one_line_are_checked_not_just_the_first(self):
        """Two markers on one line is a strange thing to write, but the
        second must not be silently dropped -- a marker that is parsed and
        ignored is exactly the silent failure this check exists to remove.
        Both compare against the line's single number."""
        self.write_assets("assets", 3)
        self.write_doc(
            "two.md",
            doc_text(
                body="\n# Doc\n\nThere are 3 assets. "
                + marker("count", "assets/*.txt") + " " + marker("count", "ghost/*.txt")
                + "\n"
            ),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("ghost/*.txt" in e and "matches no files" in e for e in errors), errors,
        )


class CheckFInlineCodeSpanLimitationTest(CheckFMarkerBase):
    """KNOWN LIMITATION, pinned deliberately rather than left to be
    discovered: the fence machine protects FENCED code blocks only. A marker
    written inside an INLINE code span (single backticks) is still read as a
    live marker, because nothing here parses inline spans.

    Raised in review. Not closed in this cut for two reasons, both stated in
    the script header and in templates/PHASE_DOC_SCHEMA.md so the claim is
    narrow rather than optimistic: parsing inline code spans correctly
    (backtick runs of arbitrary length, escapes) is a markdown parser, not a
    guard clause; and the failure is fail-LOUD (an error nobody can miss),
    never a silent pass. Measured at the time of writing: no line inside
    `Manual/` -- the only tree check-all.sh points this linter at -- writes
    the marker syntax inline.

    This test pins the CURRENT behaviour. If the limitation is closed later,
    this test is the one to invert, and its docstring is the reason it
    existed."""

    def test_a_marker_in_an_inline_code_span_is_still_read_as_live(self):
        self.write_doc(
            "guide.md",
            doc_text(
                body="\n# Guide\n\nWrite it as `" + marker("count", "ghost/*.txt")
                + "` in your own document.\n"
            ),
        )

        result = self.run_lint()

        self.assertEqual(result.returncode, 2, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(any("guide.md" in e for e in errors), errors)


class CheckFLongFenceTest(CheckFMarkerBase):
    """Raised in review: the fence machine requires a closing run at least as
    long as the opener, but only the different-DELIMITER nesting case was
    tested. This pins the same-delimiter, different-LENGTH case."""

    def test_a_four_backtick_fence_is_not_closed_by_a_three_backtick_line(self):
        self.write_assets("assets", 3)
        self.write_doc(
            "guide.md",
            doc_text(
                body="\n# Guide\n\n````markdown\n```\n"
                + pinned("There are 999 assets.", "count", "ghost/*.txt")
                + "```\n````\n\n"
                + pinned("There are 8 assets.", "count", "assets/*.txt")
            ),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("999" in e or "ghost" in e for e in errors), errors)
        self.assertTrue(any("derives 3" in e and "states 8" in e for e in errors), errors)


class CheckFSpanBoundaryTest(CheckFMarkerBase):
    """Three properties of the marker/span grammar that no other test in this
    module discriminated. All three were found the same way: after the
    comment-span restructure, the probe suite was re-run against the NEW
    script and three mutations SURVIVED -- the old probes had been written
    against regexes that no longer exist. A surviving mutation is a coverage
    report, so each one is closed here rather than explained away."""

    def test_a_marker_with_extra_tokens_is_malformed(self):
        """The marker grammar anchors at the END of its span. Without that
        anchor `pin: count a b` parses as verb=count, glob=a and silently
        DROPS ` b` -- a marker that means something other than what it says,
        which is worse than one that is rejected."""
        self.write_assets("assets", 3)
        self.write_doc(
            "extra.md",
            doc_text(
                body="\n# Doc\n\nThere are 3 assets. <!-- "
                + "pin: count assets/*.txt extra-token -->\n"
            ),
        )

        result = self.run_lint()

        self.assertEqual(result.returncode, 2, result.stdout)
        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("extra.md" in e and "malformed" in e for e in errors), errors,
        )

    def test_an_ordinary_comment_mentioning_the_marker_word_is_not_a_marker(self):
        """The marker word has to start its span. A prose comment that merely
        MENTIONS the vocabulary is not a marker, and must not be reported as a
        malformed one -- a linter that complains about documentation of itself
        gets switched off."""
        self.write_assets("assets", 3)
        self.write_doc(
            "mention.md",
            doc_text(
                body="\n# Doc\n\n"
                "Some prose. <!-- note: the " + "pin: vocabulary is documented elsewhere -->\n"
                "\n"
                # Liveness companion: a real marker on its own line in the
                # SAME document, so silence on the mention line cannot be
                # confused with check (f) skipping the file.
                + pinned("There are 8 assets.", "count", "assets/*.txt")
            ),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("malformed" in e for e in errors), errors)
        self.assertTrue(any("derives 3" in e and "states 8" in e for e in errors), errors)

    def test_a_marked_line_followed_by_an_unrelated_comment_stays_silent(self):
        """A span ends at ITS OWN `-->`, not at the last one on the line.
        The script header claims a line may carry both an unrelated comment
        and a marker; this is what pins that claim. If a span ran to the final
        `-->`, the marker's own span would swallow the second comment and be
        reported as malformed."""
        self.write_assets("assets", 3)
        self.write_doc(
            "trailing.md",
            doc_text(
                body="\n# Doc\n\nThere are 3 assets. "
                + marker("count", "assets/*.txt") + " <!-- editorial note -->\n\n"
                # Liveness companion, same two-comment shape, wrong number.
                + "There are 8 assets. " + marker("count", "assets/*.txt")
                + " <!-- editorial note -->\n"
            ),
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("malformed" in e for e in errors), errors)
        self.assertFalse(any("states 3" in e for e in errors), errors)
        self.assertTrue(any("derives 3" in e and "states 8" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
