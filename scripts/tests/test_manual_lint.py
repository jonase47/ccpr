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
manufacture a failure -- see `ReverseLinkMutationProofTest` and
`KindVocabularyMutationProofTest`.
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
    """(d) the report names its scope of CHECKS -- WI-0090/WI-0121
    convention, landed twice already (artifact-gate.sh's header,
    scripts/phase-docs-lint.sh:165-190)."""

    def test_report_names_all_three_checks(self):
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


if __name__ == "__main__":
    unittest.main()
