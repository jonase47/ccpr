r"""test_pin_inventory.py -- WI-0133 T1: makes ADR-0012 obligation 1 enforceable.

A PIN stores a derived value on purpose so that a change to its source breaks
the build (docs/adr/ADR-0012-derived-values-are-not-stored.md). Obligation 1 of
that decision says a pin **names itself as a pin, at its own site**. Measured
01.09.2026, before this module existed, not one did (that command's only
match in this tree today is this sentence quoting it): `grep -rlE 'PIN:'
--include='*.py' scripts/tests` returned nothing. Every attempt to take stock of
the pin population therefore had to guess a pattern, and in the round that
produced this module seven guesses produced seven different totals (117 / 126 /
124 / 363 / 480 / 85 / 8).

This module closes that. It derives the candidate population from the sources
(`pin_registry.find_candidates`), derives the declared population from the
`# pin:` markers actually present (`pin_registry.find_markers`), and fails on
any candidate that is neither marked nor listed in `PENDING` below.

## Why the marker shape is borrowed rather than invented

`# pin: <group> <id>` copies test_external_tool_exit_status.py:229's
`# exit-status: exempt <reason>` marker, together with its registry idiom
(`EXEMPTION_REASONS`, :234) and its two guard tests: every marker in the corpus
must name a registered group, and every registered group must be used. A second
marker dialect in the same corpus would be one more thing to keep in sync.

## Why there is no `--update-pins` flag, and must not be one

A mode that rewrites every pin to its measured value satisfies the letter of
"the pin is current" and destroys the thing pins exist for. A pin's whole
function is that a change to its source *stops* someone and makes them look
(ADR-0012, "Breaking is the pin's entire function, not a side effect"). A tool
that clears the stop sign on request converts the guard into a ceremony: the
build stays green, the number stays current, and nobody ever reads why it
moved. The argument for such a flag -- "it reduces hand work" -- is not wrong;
it is simply not the question this module answers. The hand work IS the
control. Anyone reaching for the flag should instead reduce the number of pins,
or convert a count pin into a set pin, where the diff itself names what moved
(see `assert_set_matches`).

## What this module's pattern does NOT reach

`find_candidates` recognises exactly one shape: an equality-family assertion,
inside a `test*` method, in which one side is a declared value (a non-trivial
literal, or a module-level constant bound to a literal) and the other side is
measured from the repository and not from a fixture. Everything below is a pin
in ADR-0012's sense that this pattern cannot see. The list is part of the
contract, and `PatternLimitsTest` tests an instance of each rather than
asserting the gap in prose only.

1. **A number in a docstring or comment.** It carries no assertion, so it can
   never go red, and no AST walk over assertions can find it. Two live
   instances in this tree at the time of writing:
   `test_external_tool_exit_status.py:1228` says "the 18 files known at write
   time" while the list literal below it holds 21 names;
   `test_heredoc_interpolation_scan.py:390` says "the 25 scanned files" while
   the pin at :421 requires 27.
2. **Prose registers** in `Manual/`, `README.md`, `CLAUDE.md`,
   `CONTRIBUTING.md`. CONTRIBUTING.md:85-102 alone carries four discovery
   numbers, known stale.
3. **Numbers in YAML comments**, e.g. `.github/workflows/ci.yml:57` ("1923
   tests"), which no Python parser in this repository reads.
4. **Registers under `docs/memory/**`**, which is gitignored and enumerated by
   nothing.
5. **A value one function level deeper than the assertion.**
   `test_platform_conditional_skip_budget.py:174-187`'s `expected_skip_count()`
   adds four hand-pinned numbers; the assertion at :193 compares two calls and
   contains no literal at all, so this scanner sees nothing there.
6. **A value reached only through a name imported INSIDE a method.**
   The repo-derived fixpoint runs over module-level statements; a local
   `from x import y` is neither in it nor tracked as a local source, so an
   assertion whose measured side reaches the repository only through such a
   name is dropped. The corpus has one local import today
   (`test_absence_only_assertions.py:1848`, deliberate -- see the comment
   above it), and it is safe only because the call it introduces,
   `assert_set_matches`, is recognised by NAME rather than by taint. A future
   pin built on a locally imported *value* would be invisible.
   (A `cls.<attr>` access has the same shape and is likewise untracked; there
   is no instance of it in the corpus today, so it is named here rather than
   tested.)
7. **A pin inside a helper method rather than a `test*` method.**
   `find_candidates` only walks methods whose name starts with `test`, because
   that is what unittest runs. A pin placed in a shared helper -- e.g.
   `test_handover_size_hook.py:783`'s `assert_level`, which every level test
   routes through -- is invisible, even though it runs on every one of those
   tests. Found by measuring, not by reading: of twelve one-line controls that
   turned a fixture assertion into a repository measurement, eleven were
   reported and the twelfth, the one inside `assert_level`, was not.

## PENDING has an expiry date, in the test, not in a promise

T1 can only place markers in the two sites it is allowed to write
(`test_absence_only_assertions.py`'s two pins). Every other candidate is
declared in `PENDING` with the tranche that removes it. `test_pending_is_
exhausted` fails for any entry whose tranche already appears in
`LANDED_TRANCHES`. In T1 `LANDED_TRANCHES` is empty, so it reports nothing --
but it exists and has been seen red, because a transition set with no expiry
becomes the next hand-maintained list, and this repository already carries two
of those.
"""

import ast
import sys
import unittest
from pathlib import Path

# sys.path.insert, deliberately, rather than `from .pin_registry import ...`:
# CONTRIBUTING.md:85-102 pins in prose how many modules fail to import without
# `-t .`, and how many tests are silently skipped as a result. A new relative
# import moves those numbers, and CONTRIBUTING.md is outside this round's write
# boundary. Same idiom as test_next_steps_lists.py:53 and scripts/tests/
# workitems/*.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pin_registry import (  # noqa: E402
    PIN_GROUPS,
    TESTS_DIR,
    corpus_files,
    all_candidates,
    all_markers,
    assert_set_matches,
    candidates_from_source,
    find_candidates,
    find_markers,
)


# ---------------------------------------------------------------------------
# Acceptance corpus for find_candidates
# ---------------------------------------------------------------------------
# Identity is (file, class, method) and NEVER a line number. A line-bearing
# identity reports every insertion above a site as one removal plus one
# addition; test_external_tool_exit_status.py:1173-1178 records the same change
# measured both ways -- 7 additions / 4 removals line-bearing, 3 / 0 line-free.

# Live pins that find_candidates MUST reach. Each was read at its site and
# confirmed to store a value derived from this repository.
NAMED_LIVE_PINS = frozenset({
    ("test_absence_only_assertions.py", "ClassificationCountsTest",
     "test_classification_counts"),
    ("test_absence_only_assertions.py", "ScannedFilesCoverTheShippedScopeTest",
     "test_scanned_files_cover_the_shipped_scope"),
    ("test_agent_frontmatter.py", "AgentCountTest",
     "test_agent_file_count_is_pinned"),
    ("test_bsd_gnu_portability.py", "ClassificationCountsTest",
     "test_classification_counts"),
    ("test_bsd_gnu_portability.py", "ExemptedSitesArePinnedTest",
     "test_the_marker_exempted_sites_equal_the_registry"),
    ("test_bsd_gnu_portability.py", "KnownFindingsMatchTheCurrentScanTest",
     "test_the_current_scan_equals_known_findings_exactly"),
    ("test_bsd_gnu_portability.py", "ScannedFilesCoverTheShippedScopeTest",
     "test_an_empty_scope_is_never_a_pass"),
    ("test_check_all.py", "DroppedBaselineEntryRedProofTest",
     "test_a_baseline_missing_one_entry_is_caught_by_the_contract_comparison"),
    ("test_check_all.py", "NoteColumnQuantityRedProofTest",
     "test_a_reintroduced_quantity_is_caught_in_both_number_forms"),
    ("test_command_check.py", "UnknownCommandTest",
     "test_every_shipped_command_name_is_not_rejected_as_unknown"),
    ("test_command_frontmatter.py", "MeasuredCorpusSizeTest",
     "test_pattern_derived_count_is_pinned"),
    ("test_command_frontmatter.py", "MeasuredCorpusSizeTest",
     "test_total_command_file_count_is_pinned"),
    ("test_conformance_run.py", "CheckTableAlignmentTest",
     "test_exactly_the_seven_named_columns_exist_in_source"),
    ("test_docs_dotfile_gitignore_coverage.py", "DocsDotfileSweepTest",
     "test_sweep_finds_the_thirteen_concrete_artifacts_after_wi_0021s_anchor_report"),
    ("test_docs_dotfile_gitignore_coverage.py", "DocsDotfileSweepTest",
     "test_sweep_normalises_to_the_six_block_patterns_the_generator_uses"),
    ("test_external_tool_exit_status.py", "ExternalToolExitStatusTest",
     "test_classification_counts"),
    ("test_external_tool_exit_status.py", "ExternalToolExitStatusTest",
     "test_scanned_files_cover_the_shipped_scope"),
    ("test_handover_epilogue_bullet.py", "EpilogueOpenBulletTest",
     "test_104_files_carry_the_disambiguated_wording"),
    ("test_heredoc_interpolation_scan.py", "ClassificationCountsTest",
     "test_classification_counts"),
    ("test_heredoc_interpolation_scan.py", "ScannedFilesCoverTheShippedScopeTest",
     "test_scanned_files_cover_the_shipped_scope"),
    ("test_heredoc_interpolation_scan.py", "ScopeMatchesKnownFindingsTest",
     "test_the_measured_findings_match_known_findings_exactly"),
    ("test_instinct_registers_agree.py", "ClassificationCountsTest",
     "test_classification_counts"),
    ("test_manual_lint.py", "KindVocabularyExhaustiveTest",
     "test_valid_kinds_count_is_pinned_at_nineteen"),
    ("test_platform_conditional_skip_budget.py", "PlatformConditionalSkipBudgetTest",
     "test_no_unregistered_skip_decorator_file_exists"),
    ("test_shell_script_syntax.py", "ShellScriptSyntaxTest",
     "test_scanned_files_cover_the_shipped_scope"),
})


# Fixture assertions that find_candidates MUST NOT report. They measure an
# input the test itself constructed (a `mkdtemp` scratch tree, a subprocess
# result over it), so their expected value follows from the construction and
# cannot age. They are not pins in ADR-0012's sense, and a detector that
# reports them turns PENDING into a copy of the suite.
#
# The corpus is derived, not retyped: every `assertEqual(<int literal>,
# len(...))` site in the four named modules, plus the same shape inside
# test_quality_scan.py's two fixture base classes.
FIXTURE_ASSERTION_MODULES = (
    "test_handover_size_hook.py",
    "test_agent_monitor.py",
    "test_bash_exit_status_pipe_hook.py",
    "workitems/test_migrate.py",
)

FIXTURE_ASSERTION_BASE_CLASSES = ("QualityScanTestBase", "ToolReportPyTestBase")

# Measured 01.09.2026. Pinned so that the acceptance corpus cannot silently
# shrink to nothing and make the MUST-NOT half vacuous -- a scanner is only
# proven quiet over a scope that is known to be non-empty.
FIXTURE_ASSERTION_SITE_COUNTS = {
    "test_handover_size_hook.py": 21,
    "test_agent_monitor.py": 16,
    "test_bash_exit_status_pipe_hook.py": 12,
    "workitems/test_migrate.py": 8,
    "test_quality_scan.py": 24,
}


def _fixture_assertion_lines(rel, base_classes=None):
    """`assertEqual(<int literal>, len(<expr>))` sites, either across a whole
    module or restricted to classes deriving from `base_classes`."""
    tree = ast.parse((TESTS_DIR / rel).read_text(encoding="utf-8"))
    out = set()
    for class_def in ast.walk(tree):
        if not isinstance(class_def, ast.ClassDef):
            continue
        if base_classes is not None and not any(
                isinstance(b, ast.Name) and b.id in base_classes
                for b in class_def.bases):
            continue
        for call in ast.walk(class_def):
            if not (isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "assertEqual"
                    and len(call.args) >= 2):
                continue
            first, second = call.args[0], call.args[1]
            for literal, measured in ((first, second), (second, first)):
                if (isinstance(literal, ast.Constant)
                        and isinstance(literal.value, int)
                        and not isinstance(literal.value, bool)
                        and isinstance(measured, ast.Call)
                        and isinstance(measured.func, ast.Name)
                        and measured.func.id == "len"):
                    out.add(call.lineno)
                    break
    return out


# Two sites carry the fixture shape but are, at their own site, real pins over
# the SHIPPED source rather than over a fixture. They are named here instead of
# being dropped from FIXTURE_ASSERTION_BASE_CLASSES, so the disagreement stays
# visible and goes red if either side changes. Reported to the decision-maker
# with WI-0133 T1; the classification is theirs, not this module's.
#
#   test_quality_scan.py:2588-2589, CompletedHandlersBindingTest.
#     `assertEqual(4, len(ns["COMPLETED"]))` over `load_tool_report_module()`,
#     i.e. the shipped scripts/lib/tool_report.py. Its own class docstring
#     (:2579) reads "Count pinned at 4 for both, so a removal shrinks the sweep
#     below instead of narrowing it silently" -- the site calls itself a pin.
#   test_quality_scan.py:2092, PiiPatternsRemovalRedProofTest.
#     `assertEqual(1, len(dict_entry_line(source, name)))` where `source` is
#     scripts/quality-scan.sh read from disk. It ages with the shipped script,
#     not with a fixture, even though its message calls itself a "fixture
#     assumption".
#
# Structurally these are indistinguishable from accepted MUST entries:
# :2588 has the exact shape of test_manual_lint.py:469
# (`assertEqual(19, len(VALID_KINDS))`), and :2092 has the shape of
# test_check_all.py:1209, which parameterises a shipped-file measurement by a
# declared registry entry. Sharpening the detector to drop these two would drop
# those two as well.
CORPUS_DISAGREEMENTS = frozenset({
    ("test_quality_scan.py", "CompletedHandlersBindingTest",
     "test_both_dicts_are_pinned_at_4_entries"),
    ("test_quality_scan.py", "PiiPatternsRemovalRedProofTest",
     "test_removing_a_pii_pattern_entry_makes_its_own_finding_disappear"),
})


def fixture_assertion_sites():
    """rel -> the set of fixture-assertion line numbers in it."""
    sites = {rel: _fixture_assertion_lines(rel)
             for rel in FIXTURE_ASSERTION_MODULES}
    sites["test_quality_scan.py"] = _fixture_assertion_lines(
        "test_quality_scan.py", FIXTURE_ASSERTION_BASE_CLASSES)
    return sites


# One further live pin, found by code review AFTER the acceptance corpus above
# was fixed, and kept separate from it so the record of what came from where
# stays readable. The first version of `find_candidates` dropped it silently:
# its expected value is a class-body literal reached as `self.EXPECTED_FLAGGED`
# (a shape the declared-side test did not recognise, since it only accepted a
# bare Name), and its measurement runs through `self.FIXTURE`, a class-body
# path into `fixtures/` that the `self`-is-a-fixture rule treated as scratch.
# Both were fixed; the fix was proven a pure addition by differencing the
# (file, class, method) sets of the old and new detector over the whole
# corpus -- 139 -> 140, one addition, zero removals.
#
# It is NOT marked at its site: that site is outside this tranche's write
# boundary and was not named in the briefing. It is carried in PENDING (T2)
# and reported to the decision-maker instead of quietly pulled along.
LIVE_PINS_FOUND_IN_REVIEW = frozenset({
    ("test_absence_only_assertions.py", "ParentStateDiscriminationTest",
     "test_the_six_named_methods_are_flagged_and_the_five_siblings_are_not"),
})


class NamedLivePinsAreReachedTest(unittest.TestCase):
    """The MUST half of the acceptance corpus. Without it a scanner that
    reports nothing at all passes the fixture half below."""

    def test_every_named_live_pin_is_a_candidate(self):
        found = {c.key() for c in all_candidates()}
        missing = sorted((NAMED_LIVE_PINS | LIVE_PINS_FOUND_IN_REVIEW) - found)
        self.assertEqual(  # pin: set named-live-pins-corpus
            [], missing,
            "find_candidates no longer reaches {} of the {} named live "
            "pins:\n  {}".format(
                len(missing), len(NAMED_LIVE_PINS | LIVE_PINS_FOUND_IN_REVIEW),
                "\n  ".join(map(str, missing))),
        )


class FixtureAssertionsAreNotReportedTest(unittest.TestCase):
    """The counter-half of the acceptance corpus. Without it a detector that
    reports EVERY assertion would satisfy NamedLivePinsAreReachedTest."""

    def test_the_fixture_corpus_is_the_measured_size(self):
        """A quiet scanner over an empty scope proves nothing (conformance-run's
        Rule C2, turned inward). This pins that the scope is the one measured.

        Grouped `derived`, not `floor`, and the difference is not cosmetic: a
        `floor` is an `assertGreaterEqual`, silent while its subject grows,
        whereas this is an exact per-file count that moves in both directions.
        It shares the floor's one real weakness -- a same-file SWAP (one
        fixture assertion removed, one added) leaves the count unchanged -- and
        that weakness is accepted here rather than fixed with a set pin,
        because the thing this guard protects is the SCOPE of the counter-half
        of the acceptance corpus, and a scope cannot go vacuous by a swap. It
        goes vacuous by emptying, which a count does see."""
        actual = {rel: len(lines) for rel, lines in fixture_assertion_sites().items()}
        self.assertEqual(  # pin: derived fixture-corpus-site-counts
            FIXTURE_ASSERTION_SITE_COUNTS, actual)

    def test_each_declared_disagreement_is_still_reported(self):
        """The exceptions above are exceptions, not deletions: each must still
        be a live candidate. If one stops being reported, the exemption is
        stale and must go -- an exemption nobody re-verifies is the drift this
        repository has already grown four skip lists' worth of
        (test_bsd_gnu_portability.py:1968-1972)."""
        found = {c.key() for c in all_candidates()}
        assert_set_matches(  # pin: set fixture-corpus-disagreements
            self, CORPUS_DISAGREEMENTS, CORPUS_DISAGREEMENTS & found,
            "the declared fixture-corpus disagreements",
        )

    def test_no_fixture_assertion_is_reported_as_a_candidate(self):
        sites = fixture_assertion_sites()
        offenders = []
        for candidate in all_candidates():
            forbidden = sites.get(candidate.rel)
            if not forbidden:
                continue
            if candidate.key() in CORPUS_DISAGREEMENTS:
                continue
            overlap = sorted(set(candidate.assert_linenos) & forbidden)
            if overlap:
                offenders.append((candidate.key(), overlap))
        self.assertEqual(
            [], offenders,
            "find_candidates reported {} fixture assertion(s) as pins:\n  {}".format(
                len(offenders), "\n  ".join(map(str, offenders))),
        )


class AssertSetMatchesTest(unittest.TestCase):
    """The generalised house idiom (test_bsd_gnu_portability.py:1888-1901,
    :1967-1982). A SWAP is the case a count pin cannot see, so it is the case
    tested; the silent direction is tested too, or "always fails" would pass."""

    def test_a_swap_is_reported_in_both_directions(self):
        with self.assertRaises(AssertionError) as raised:
            assert_set_matches(self, {"a", "b"}, {"a", "c"}, "the corpus")
        message = str(raised.exception)
        self.assertIn("the corpus drifted from its recorded baseline", message)
        self.assertIn("new:  ['c']", message)
        self.assertIn("gone: ['b']", message)

    def test_an_unchanged_set_is_silent(self):
        assert_set_matches(self, {"a", "b"}, ["b", "a"], "the corpus")

    def test_an_addition_names_only_the_addition(self):
        with self.assertRaises(AssertionError) as raised:
            assert_set_matches(self, {"a"}, {"a", "b"}, "the corpus")
        message = str(raised.exception)
        self.assertIn("new:  ['b']", message)
        self.assertIn("gone: []", message)


class AssertSetMatchesIsItselfAPinShapeTest(unittest.TestCase):
    """Converting a count pin into an `assert_set_matches` call must not make
    it invisible to the inventory. The idiom is a bare module-level function,
    not `self.assertXxx`, so it needs its own recognition -- without this the
    scanner would go quieter exactly as the repository adopts the better pin
    shape."""

    SOURCE = (
        "from pathlib import Path\n"
        "from pin_registry import assert_set_matches\n"
        "REPO = Path(__file__).resolve().parents[2]\n"
        "EXPECTED = frozenset({'a.md', 'b.md'})\n"
        "class T:\n"
        "    def test_names(self):\n"
        "        names = sorted(p.name for p in REPO.glob('*.md'))\n"
        "        assert_set_matches(self, EXPECTED, names, 'the corpus')\n"
    )

    def test_an_assert_set_matches_call_is_a_candidate(self):
        # Not a pin, and deliberately unmarked: the expected value follows
        # from SOURCE above, which this test wrote, so it cannot age. It is
        # carried in PENDING (T4) rather than marked, because the marker
        # vocabulary has four groups and none of them means "not a pin" --
        # naming that gap is T4's job, not this file's.
        found = [c.key() for c in candidates_from_source(self.SOURCE, "probe.py")]
        self.assertEqual([("probe.py", "T", "test_names")], found)

    def test_the_same_method_without_the_call_is_not_a_candidate(self):
        """Positive control: the recognition must come from the call, not from
        the method merely touching a repository path."""
        without = self.SOURCE.replace(
            "        assert_set_matches(self, EXPECTED, names, 'the corpus')\n",
            "        self.assertTrue(names)\n")
        self.assertEqual([], candidates_from_source(without, "probe.py"))


# ---------------------------------------------------------------------------
# The declared transition set
# ---------------------------------------------------------------------------
# Tranches that have landed. `test_pending_is_exhausted` fails for every
# PENDING entry naming one of these. Empty in T1 -- the guard reports nothing
# yet, and has been seen red by adding "T2" here (see this module's own red
# proofs in the WI-0133 T1 commit message).
LANDED_TRANCHES = ()

DECLARED_TRANCHES = ("T2", "T3", "T4")

# Candidates that are not yet marked at their own site, each with the tranche
# that removes it. T1's write boundary reaches exactly two pin sites, both in
# test_absence_only_assertions.py; everything else is declared here rather than
# left undetected.
#
# Tranche assignment is derived, not editorial: T2 = the named live pins of
# NAMED_LIVE_PINS above (they are read and confirmed, so they only need a
# marker); T3 = every other candidate inside a module that already carries a
# named live pin (its neighbours, judged in the same pass); T4 = the rest.
PENDING = frozenset({
    ('test_absence_only_assertions.py', 'ClassificationCountsTest',
     'test_classification_counts', 'T2'),
    ('test_absence_only_assertions.py', 'ParentStateDiscriminationTest',
     'test_the_six_named_methods_are_flagged_and_the_five_siblings_are_not',
     'T2'),
    ('test_absence_only_assertions.py', 'NoStaleKnownFindingsTest',
     'test_no_stale_known_findings', 'T3'),
    ('test_agent_frontmatter.py', 'AgentCountTest',
     'test_agent_file_count_is_pinned', 'T2'),
    ('test_agent_frontmatter.py', 'ProjectMemoryContractHistoricalRedProofTest',
     'test_removing_the_global_contract_does_not_clear_the_rule', 'T3'),
    ('test_agent_frontmatter.py', 'ProjectMemoryContractHistoricalRedProofTest',
     'test_the_two_states_differ_only_by_the_inserted_sentence', 'T3'),
    ('test_agent_frontmatter.py', 'Tier1WriteDirectiveDetectionTest',
     'test_exactly_one_agent_is_obliged_by_neither_trigger', 'T3'),
    ('test_bsd_gnu_portability.py', 'ClassificationCountsTest',
     'test_classification_counts', 'T2'),
    ('test_bsd_gnu_portability.py', 'EveryMarkerNamesARegisteredCategoryTest',
     'test_every_category_in_the_tree_is_registered', 'T3'),
    ('test_bsd_gnu_portability.py', 'EveryMarkerNamesARegisteredCategoryTest',
     'test_every_registered_category_is_used', 'T3'),
    ('test_bsd_gnu_portability.py', 'ExemptedSitesArePinnedTest',
     'test_the_marker_exempted_sites_equal_the_registry', 'T2'),
    ('test_bsd_gnu_portability.py', 'HistoricalMktempTemplatesAreFlaggedTest',
     'test_the_current_run_tests_carries_no_mktemp_finding', 'T3'),
    ('test_bsd_gnu_portability.py', 'KnownFindingsMatchTheCurrentScanTest',
     'test_the_current_scan_equals_known_findings_exactly', 'T2'),
    ('test_bsd_gnu_portability.py', 'ScannedFilesCoverTheShippedScopeTest',
     'test_an_empty_scope_is_never_a_pass', 'T2'),
    ('test_bsd_gnu_portability.py', 'ScannedFilesCoverTheShippedScopeTest',
     'test_scanned_files_cover_the_shipped_scope', 'T3'),
    ('test_check_all.py', 'CompareAgainstZeroInsteadOfBaselineRedProofTest',
     'test_comparing_against_exit_zero_breaks_the_two_by_design_nonzero_checks', 'T3'),
    ('test_check_all.py', 'CouldNotRunCountsAsPassRedProofTest',
     'test_could_not_run_folded_into_match_breaks_both_pins', 'T3'),
    ('test_check_all.py', 'DroppedBaselineEntryRedProofTest',
     'test_a_baseline_missing_one_entry_is_caught_by_the_contract_comparison', 'T2'),
    ('test_check_all.py', 'InstallVerifyCouldNotRunRedProofTest',
     'test_without_the_report_match_a_no_op_verify_reads_as_a_divergence', 'T3'),
    ('test_check_all.py', 'NoteColumnQuantityRedProofTest',
     'test_a_reintroduced_quantity_is_caught_in_both_number_forms', 'T2'),
    ('test_ci_workflow.py', 'RealWorkflowStructureTest',
     'test_job_names_and_runners', 'T4'),
    ('test_ci_workflow.py', 'RealWorkflowStructureTest',
     'test_step_counts_per_job', 'T4'),
    ('test_command_check.py', 'CommandPrerequisitesEmptyFilesEntriesRemovalStructuralProofTest',
     'test_removal_is_a_check_command_no_op_but_shrinks_the_dict', 'T3'),
    ('test_command_check.py', 'CommandPrerequisitesEmptyFilesEntriesRemovalStructuralProofTest',
     'test_the_two_empty_files_entries_are_exactly_these_two', 'T3'),
    ('test_command_check.py', 'CommandPrerequisitesFilesRemovalRedProofTest',
     'test_removing_the_entry_drops_its_file_reason', 'T3'),
    ('test_command_check.py', 'CommandPrerequisitesP7DeployPointsAtPrepareArtifactTest',
     'test_p7_deploy_prerequisite_is_exactly_the_prepare_artifact', 'T3'),
    ('test_command_check.py', 'CommandPrerequisitesSchemaTest',
     'test_entry_count_is_pinned_at_16', 'T3'),
    ('test_command_check.py', 'GateFileClaimsStructuralTest',
     'test_all_eight_gates_claim_an_artifact', 'T3'),
    ('test_command_check.py', 'GateFileClaimsStructuralTest',
     'test_claimed_paths_match_the_phase_folder_convention', 'T3'),
    ('test_command_check.py', 'GateFileClaimsStructuralTest',
     'test_gate_p5_claims_sprint_md_not_a_phase_folder_gate_file', 'T3'),
    ('test_command_check.py', 'GateP5UsesSprintMdTest',
     'test_gate_p5_is_mapped_to_sprint_md', 'T3'),
    ('test_command_check.py', 'TemplateTreeExcludesGateArtifactsTest',
     'test_gate_p6_and_p7_are_absent_from_the_claim_set_for_a_different_reason', 'T3'),
    ('test_command_check.py', 'TemplateTreeExcludesGateArtifactsTest',
     'test_the_exclusion_has_real_work_to_do', 'T3'),
    ('test_command_check.py', 'UnknownCommandTest',
     'test_every_shipped_command_name_is_not_rejected_as_unknown', 'T2'),
    ('test_command_frontmatter.py', 'MeasuredCorpusSizeTest',
     'test_pattern_derived_count_is_pinned', 'T2'),
    ('test_command_frontmatter.py', 'MeasuredCorpusSizeTest',
     'test_total_command_file_count_is_pinned', 'T2'),
    ('test_conformance_run.py', 'CheckTableAlignmentTest',
     'test_all_seven_columns_are_five_entries_long', 'T3'),
    ('test_conformance_run.py', 'CheckTableAlignmentTest',
     'test_exactly_the_seven_named_columns_exist_in_source', 'T2'),
    ('test_conformance_run.py', 'CheckTableUncoveredColumnsValuesTest',
     'test_check_arg_shape_is_a_three_two_split', 'T3'),
    ('test_conformance_run.py', 'CheckTableUncoveredColumnsValuesTest',
     'test_check_c2_exempt_only_anchor_is_exempt', 'T3'),
    ('test_conformance_run.py', 'CheckTableUncoveredColumnsValuesTest',
     'test_check_has_summary_line_only_anchor_lacks_one', 'T3'),
    ('test_conformance_run.py', 'CheckTableUncoveredColumnsValuesTest',
     'test_check_subcmd_only_anchor_carries_a_subcommand', 'T3'),
    ('test_conformance_run.py', 'RequiredSkeletonLineCountPinTest',
     'test_anchor_branch_requires_two_lines', 'T3'),
    ('test_conformance_run.py', 'RequiredSkeletonLineCountPinTest',
     'test_generic_branch_requires_three_lines', 'T3'),
    ('test_conformance_run.py', 'RequiredSkeletonLineCountPinTest',
     'test_the_required_lines_are_the_documented_ones', 'T3'),
    ('test_docs_dotfile_gitignore_coverage.py', 'DocsDotfileSweepTest',
     'test_sweep_finds_the_thirteen_concrete_artifacts_after_wi_0021s_anchor_report', 'T2'),
    ('test_docs_dotfile_gitignore_coverage.py', 'DocsDotfileSweepTest',
     'test_sweep_normalises_to_the_six_block_patterns_the_generator_uses', 'T2'),
    ('test_external_tool_exit_status.py', 'ExternalToolExitStatusTest',
     'test_classification_counts', 'T2'),
    ('test_external_tool_exit_status.py', 'ExternalToolExitStatusTest',
     'test_scanned_files_cover_the_shipped_scope', 'T2'),
    ('test_handover_epilogue_bullet.py', 'EpilogueOpenBulletTest',
     'test_104_files_carry_the_disambiguated_wording', 'T2'),
    ('test_handover_size_hook.py', 'WriteGateCoverageTest',
     'test_every_declared_write_tool_warns', 'T4'),
    ('test_heredoc_interpolation_scan.py', 'ClassificationCountsTest',
     'test_classification_counts', 'T2'),
    ('test_heredoc_interpolation_scan.py', 'FiveOriginalRunTestsSitesAreNoLongerFlaggedTest',
     'test_run_tests_sh_carries_no_finding_after_the_wi_0129_fix', 'T3'),
    ('test_heredoc_interpolation_scan.py', 'ScannedFilesCoverTheShippedScopeTest',
     'test_scanned_files_cover_the_shipped_scope', 'T2'),
    ('test_heredoc_interpolation_scan.py', 'ScopeMatchesKnownFindingsTest',
     'test_the_measured_findings_match_known_findings_exactly', 'T2'),
    ('test_instinct_registers_agree.py', 'ClassificationCountsTest',
     'test_classification_counts', 'T2'),
    ('test_instinct_registers_agree.py', 'ExclusionRegressionPinTest',
     'test_mention_only_ids_are_not_parsed_as_index_entries', 'T3'),
    ('test_instinct_registers_agree.py', 'ExclusionRegressionPinTest',
     'test_mention_only_ids_are_not_parsed_as_sampler_entries', 'T3'),
    ('test_live_status_claims.py', 'DriftedRegisterHistoricalRedProofTest',
     'test_the_same_file_in_the_working_tree_is_clean', 'T4'),
    ('test_live_status_claims.py', 'HistoryIsLetThroughTest',
     'test_the_whole_history_carrying_files_are_clean_at_the_pinned_commit', 'T4'),
    ('test_manual_lint.py', 'KindVocabularyExhaustiveTest',
     'test_valid_kinds_count_is_pinned_at_nineteen', 'T2'),
    ('test_memory_lint_checklist_binding.py', 'RedProofAddingAnUndefinedChapterBulletTest',
     'test_adding_a_z_bullet_reports_z_as_stale', 'T4'),
    ('test_memory_lint_checklist_binding.py', 'RedProofRemovingAChapterBulletTest',
     'test_removing_the_g_bullet_reports_g_as_undocumented', 'T4'),
    ('test_next_steps_lists.py', 'GateTransitionsCountTest',
     'test_gate_count_is_pinned_at_8', 'T4'),
    ('test_next_steps_lists.py', 'GateTransitionsRemovalRedProofTest',
     'test_removing_one_gate_breaks_the_count_pin', 'T4'),
    ('test_next_steps_lists.py', 'PhaseCountRemovalRedProofTest',
     'test_removing_one_phase_breaks_the_phase_count_pin', 'T4'),
    ('test_next_steps_lists.py', 'PhaseSequencesExistenceTest',
     'test_phase_count_is_pinned_at_9', 'T4'),
    ('test_next_steps_lists.py', 'PhaseSequencesExistenceTest',
     'test_total_command_count_is_pinned_at_50', 'T4'),
    ('test_next_steps_lists.py', 'PhaseSequencesRemovalRedProofTest',
     'test_removing_one_command_breaks_the_total_count_pin', 'T4'),
    ('test_next_steps_lists.py', 'UtilityCommandsRedProofTest',
     'test_removing_one_entry_changes_the_length_by_one', 'T4'),
    ('test_next_steps_lists.py', 'UtilityCommandsVocabularyTest',
     'test_total_command_count_is_pinned_at_8', 'T4'),
    ('test_phase_docs_lint.py', 'CheckCPhaseEnumTest',
     'test_valid_phases_count_is_pinned_at_nine', 'T4'),
    ('test_phase_docs_lint.py', 'CheckDStatusEnumTest',
     'test_valid_statuses_count_is_pinned_at_six', 'T4'),
    ('test_phase_docs_lint.py', 'CheckKGateVerdictTest',
     'test_valid_gate_verdicts_count_is_pinned_at_five', 'T4'),
    ('test_phase_docs_lint.py', 'CheckKGateVerdictTest',
     'test_valid_sprint_verdicts_count_is_pinned_at_four', 'T4'),
    ('test_phase_docs_lint.py', 'LivingFilesSkipTest',
     'test_living_file_names_count_is_pinned_at_six', 'T4'),
    ('test_phase_docs_lint.py', 'LivingFilesSkipTest',
     'test_other_living_filenames_are_skipped_even_with_broken_frontmatter', 'T4'),
    ('test_phase_docs_lint.py', 'PhaseFoldersSweepTest',
     'test_every_phase_folder_is_reached_by_the_default_scan', 'T4'),
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_number_in_a_docstring_is_not_reached', 'T4'),
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_pin_inside_a_helper_method_is_not_reached', 'T4'),
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_value_one_function_level_deeper_is_not_reached', 'T4'),
    ('test_pin_inventory.py', 'PinMarkerInventoryTest',
     'test_a_marker_with_an_unknown_group_is_rejected', 'T4'),
    ('test_pin_inventory.py', 'AssertSetMatchesIsItselfAPinShapeTest',
     'test_an_assert_set_matches_call_is_a_candidate', 'T4'),
    ('test_platform_conditional_skip_budget.py', 'PlatformConditionalSkipBudgetTest',
     'test_no_unregistered_skip_decorator_file_exists', 'T2'),
    ('test_quality_scan.py', 'CompletedHandlersBindingTest',
     'test_both_dicts_are_pinned_at_4_entries', 'T4'),
    ('test_quality_scan.py', 'CompletedHandlersRemovalRedProofTest',
     'test_removing_a_completed_entry_still_present_in_handlers_raises_keyerror', 'T4'),
    ('test_quality_scan.py', 'ConfigFilenamesRemovalRedProofTest',
     'test_removing_a_config_filename_makes_its_own_finding_disappear', 'T4'),
    ('test_quality_scan.py', 'ConfigFilenamesShapeTest',
     'test_config_filenames_list_is_pinned_at_6_entries', 'T4'),
    ('test_quality_scan.py', 'ConsentTermsRemovalRedProofTest',
     'test_removing_a_consent_term_makes_the_finding_fire_again', 'T4'),
    ('test_quality_scan.py', 'ConsentTermsShapeTest',
     'test_consent_terms_list_is_pinned_at_4_entries', 'T4'),
    ('test_quality_scan.py', 'PiiPatternsRemovalRedProofTest',
     'test_removing_a_pii_pattern_entry_makes_its_own_finding_disappear', 'T4'),
    ('test_quality_scan.py', 'PiiPatternsShapeTest',
     'test_pii_patterns_are_pinned_at_4_entries', 'T4'),
    ('test_quality_scan.py', 'SeveritiesRemovalRedProofTest',
     'test_removing_a_severity_silently_drops_its_bucket_from_the_count', 'T4'),
    ('test_quality_scan.py', 'SeveritiesShapeMatchesSourceTest',
     'test_severities_shape_equals_the_extracted_source', 'T4'),
    ('test_quality_scan.py', 'SkipDirsDefinitionsStayEqualTest',
     'test_both_skip_dirs_definitions_are_identical', 'T4'),
    ('test_quality_scan.py', 'SkipDirsMatchesSastModuleTest',
     'test_sast_module_skip_dirs_equals_both_quality_scan_sh_definitions', 'T4'),
    ('test_quality_scan.py', 'ToolReportCompletedShapeMatchesSourceTest',
     'test_completed_shape_equals_the_extracted_source', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'ExtensionCountTest',
     'test_total_extension_count_is_pinned_at_19', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyDoesNotRaiseTest',
     'test_missing_key_is_swallowed_and_the_finding_is_dropped', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyPositionDependentTruncationTest',
     'test_breaking_the_last_rule_in_dict_order_loses_only_the_tail', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyPositionDependentTruncationTest',
     'test_control_finds_both_lines', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PatternsRuleCountRemovalRedProofTest',
     'test_removing_one_rule_breaks_the_count_pin', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PatternsRuleCountTest',
     'test_rule_count_is_pinned_at_5', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PerExtensionPositiveFixtureTest',
     'test_every_claimed_extension_fires_the_rule', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PerExtensionRemovalRedProofTest',
     'test_removing_one_extension_silences_the_rule_for_that_extension', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PerRuleForeignExtensionNegativeTest',
     'test_foreign_extension_produces_no_finding_for_that_rule', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PerRulePositiveFixtureTest',
     'test_each_rule_fires_on_its_own_fixture', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'RuleShapeKeysTest',
     'test_every_rule_has_exactly_the_four_keys', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'TruncationCapTest',
     'test_exactly_50_matches_produce_50_with_no_marker', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'TruncationCapTest',
     'test_more_than_50_matches_are_capped_plus_one_truncation_marker', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'TruncationCapTest',
     'test_the_50_real_findings_preceding_the_marker_are_unaffected', 'T4'),
    ('test_shell_script_syntax.py', 'ShellScriptSyntaxTest',
     'test_scanned_files_cover_the_shipped_scope', 'T2'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_bare_integer_is_seconds', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_days_suffix', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_hours_suffix', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_minutes_suffix', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_numeric_string_is_seconds', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_seconds_suffix', 'T4'),
    ('workitems/test_frontmatter.py', 'FrontmatterRoundTripTest',
     'test_parses_genuine_inline_list', 'T4'),
    ('workitems/test_frontmatter.py', 'FrontmatterRoundTripTest',
     'test_round_trips_title_containing_a_literal_backslash', 'T4'),
    ('workitems/test_frontmatter.py', 'FrontmatterRoundTripTest',
     'test_round_trips_title_containing_hash', 'T4'),
    ('workitems/test_frontmatter.py', 'FrontmatterRoundTripTest',
     'test_round_trips_title_starting_with_bracket', 'T4'),
    ('workitems/test_frontmatter.py', 'FrontmatterRoundTripTest',
     'test_round_trips_title_with_both_apostrophe_and_double_quote', 'T4'),
    ('workitems/test_sweep.py', 'SweepTest',
     'test_stale_heartbeat_with_branch_commits_becomes_parked', 'T4'),
    ('workitems/test_sweep.py', 'SweepTest',
     'test_stale_heartbeat_without_branch_commits_stays_in_progress', 'T4'),
    ('workitems/test_youtrack.py', 'HttpTransportTest',
     'test_sends_bearer_auth_header_and_returns_parsed_json', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackClaimingTest',
     'test_a_non_utc_aware_clock_is_normalized_to_utc_in_the_written_heartbeat', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackCreateFactoryTest',
     'test_env_token_with_trailing_newline_is_stripped', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackCreateFactoryTest',
     'test_happy_path_reads_token_from_environment_not_config', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackCreateRollbackTest',
     'test_create_does_not_delete_when_initial_state_is_accepted', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackLinkTypeNameMapTest',
     'test_renamed_link_type_name_resolves_via_config', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackPaginationTest',
     'test_list_returns_everything_even_when_the_fake_caps_page_size', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackSetEstimateTest',
     'test_scalar_estimate_is_not_confused_with_an_enum_shaped_field', 'T4'),
})


class PinMarkerInventoryTest(unittest.TestCase):
    """(a) The inventory. Derived from the markers actually present, never
    typed: the count of pins is exactly the kind of value ADR-0012 says must
    be generated."""

    def test_the_marker_inventory_is_the_registered_set(self):
        assert_set_matches(  # pin: set pin-marker-inventory
            self,
            {("test_absence_only_assertions.py", "floor", "tests-corpus-files"),
             ("test_absence_only_assertions.py", "set", "tests-corpus-files"),
             ("test_pin_inventory.py", "derived", "fixture-corpus-site-counts"),
             ("test_pin_inventory.py", "set", "fixture-corpus-disagreements"),
             ("test_pin_inventory.py", "set", "named-live-pins-corpus"),
             ("test_pin_inventory.py", "set", "pending-transition-set"),
             ("test_pin_inventory.py", "set", "pin-marker-inventory"),
             ("test_pin_inventory.py", "set", "skip-budget-blind-spot")},
            {m.key() for m in all_markers()},
            "the `# pin:` marker inventory",
        )

    def test_every_marker_names_a_registered_group(self):
        """Mirrors test_external_tool_exit_status.py's identically-shaped
        guard: a typo'd group must fail on its own, independently of whether
        the site it sits on is currently classified."""
        unregistered = [
            (m.rel, m.lineno, m.group) for m in all_markers()
            if m.group not in PIN_GROUPS
        ]
        self.assertEqual(
            [], unregistered,
            "`# pin:` marker(s) naming a group that is not a key of "
            "PIN_GROUPS: {}".format(unregistered),
        )

    def test_every_registered_group_carries_a_reason(self):
        empty = sorted(name for name, reason in PIN_GROUPS.items() if not reason.strip())
        self.assertEqual([], empty)

    def test_a_marker_with_an_unknown_group_is_rejected(self):
        """The guard above is only worth its line if it can fail. Proven on a
        constructed marker rather than by writing a bad one into the tree.

        The needle is assembled from two pieces on purpose. `find_markers` is
        a line regex with no notion of Python strings -- the same shape as the
        marker scanner it is copied from -- so a complete marker written as one
        literal HERE would be a live marker in the corpus this module
        enumerates, and the first draft of this test duly failed its own
        sibling `test_every_marker_names_a_registered_group`. That the scanner
        reads a marker inside a string literal is a documented property, not a
        surprise; splitting the literal is how this file avoids planting one.
        """
        # Same as AssertSetMatchesIsItselfAPinShapeTest: constructed input,
        # so not a pin; carried in PENDING (T4), not marked.
        needle = "x = 1  # " + "pin: bogus some-id\n"
        markers = _markers_in_source(needle)
        self.assertEqual([("bogus", "some-id")],
                         [(m.group, m.pin_id) for m in markers])
        self.assertNotIn("bogus", PIN_GROUPS)


def _markers_in_source(source):
    """find_markers against a string, so the unknown-group proof does not need
    a bad marker committed into the corpus this module enumerates."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(source)
        path = Path(handle.name)
    try:
        return find_markers(path, "probe.py")
    finally:
        path.unlink()


class PinCompletenessTest(unittest.TestCase):
    """(b) Completeness. Every candidate is either marked at its own site or
    declared in PENDING with the tranche that removes it. Nothing sits
    unaccounted for."""

    def test_every_candidate_is_marked_or_pending(self):
        markers = all_markers()
        pending_keys = {(rel, cls, method) for rel, cls, method, _ in PENDING}
        unaccounted = []
        for candidate in all_candidates():
            marked = any(
                m.rel == candidate.rel and candidate.lineno <= m.lineno <= candidate.end_lineno
                for m in markers)
            if marked or candidate.key() in pending_keys:
                continue
            unaccounted.append(candidate.key())
        self.assertEqual(
            [], sorted(unaccounted),
            "{} pin-shaped assertion(s) name themselves neither as a pin nor "
            "as pending (ADR-0012 obligation 1). For each one, EITHER add a "
            "`# pin: <group> <id>` marker on the assertion -- groups: {} -- OR, "
            "if it is not a pin (its expected value follows from an input the "
            "test itself built, so it cannot age), say so at the site and add "
            "it to PENDING with the tranche that resolves it:\n  {}".format(
                len(unaccounted), ", ".join(sorted(PIN_GROUPS)),
                "\n  ".join(map(str, sorted(unaccounted)))),
        )

    def test_no_pending_entry_is_stale(self):
        """Drift in the other direction: an entry that is no longer a
        candidate has either been fixed without being removed from PENDING, or
        the detector stopped seeing it. Both need a look."""
        candidate_keys = {c.key() for c in all_candidates()}
        stale = sorted(key for key in
                       {(rel, cls, m) for rel, cls, m, _ in PENDING}
                       if key not in candidate_keys)
        self.assertEqual(  # pin: set pending-transition-set
            [], stale,
            "PENDING entr(ies) that find_candidates no longer reports:\n  {}"
            .format("\n  ".join(map(str, stale))),
        )

    def test_every_pending_entry_names_a_declared_tranche(self):
        undeclared = sorted({tranche for _, _, _, tranche in PENDING}
                            - set(DECLARED_TRANCHES))
        self.assertEqual([], undeclared)

    def test_pending_is_exhausted(self):
        """(d) The expiry. A transition set without an end date becomes the
        next hand-maintained list; this repository already carries two. Every
        entry names the tranche that removes it, and once that tranche is in
        LANDED_TRANCHES the entry must be gone."""
        overdue = sorted((rel, cls, method, tranche)
                         for rel, cls, method, tranche in PENDING
                         if tranche in LANDED_TRANCHES)
        self.assertEqual(
            [], overdue,
            "{} PENDING entr(ies) name a tranche that has already landed "
            "({}). Landing a tranche means its entries are marked at their "
            "own sites and removed from PENDING, not that the tranche is "
            "declared done:\n  {}".format(
                len(overdue), ", ".join(LANDED_TRANCHES) or "none",
                "\n  ".join(map(str, overdue))),
        )


class PatternLimitsTest(unittest.TestCase):
    """(c) The boundary clause, tested rather than only stated.

    Each case below is paired with a POSITIVE CONTROL on the same input: the
    same value, moved into an assertion, MUST be reported. Without the control
    a scanner that reports nothing at all would pass every one of these.
    """

    def test_a_number_in_a_docstring_is_not_reached(self):
        """Gap 1. Two live instances in this tree at the time of writing:
        test_external_tool_exit_status.py:1228 says "the 18 files known at
        write time" above a list literal holding 21 names, and
        test_heredoc_interpolation_scan.py:390 says "the 25 scanned files"
        above a pin requiring 27. Both are wrong; neither can go red, because
        neither is an assertion. Measured on a constructed instance rather
        than on those two, so that repairing either prose does not make this
        test lie about what the scanner can see."""
        blind = (
            "from pathlib import Path\n"
            "REPO = Path(__file__).resolve().parents[2]\n"
            "class T:\n"
            "    def test_scope(self):\n"
            '        """Pins the 18 files known at write time."""\n'
            "        names = sorted(p.name for p in REPO.glob('*.sh'))\n"
            "        self.assertTrue(names)\n"
        )
        self.assertEqual([], candidates_from_source(blind, "probe.py"))

        seeing = blind.replace(
            "        self.assertTrue(names)\n",
            "        self.assertEqual(18, len(names))\n")
        self.assertEqual(
            [("probe.py", "T", "test_scope")],
            [c.key() for c in candidates_from_source(seeing, "probe.py")],
            "positive control: the same 18, as an assertion, must be reported",
        )

    def test_a_number_in_a_comment_is_not_reached(self):
        """Gap 1 again, in its other form, and the form gaps 2 and 3 reduce
        to. A prose register (Manual/, README.md, CLAUDE.md,
        CONTRIBUTING.md:85-102's four known-stale discovery numbers) and a
        YAML comment (.github/workflows/ci.yml:57's "1923 tests") are the same
        case seen from a Python AST: text no parser in this repository reads
        as a claim."""
        blind = (
            "from pathlib import Path\n"
            "REPO = Path(__file__).resolve().parents[2]\n"
            "class T:\n"
            "    def test_scope(self):\n"
            "        # CONTRIBUTING.md records 1923 tests for this corpus.\n"
            "        names = sorted(p.name for p in REPO.glob('*.sh'))\n"
            "        self.assertTrue(names)\n"
        )
        self.assertEqual([], candidates_from_source(blind, "probe.py"))

    def test_a_pin_inside_a_helper_method_is_not_reached(self):
        """Gap 7. The scanner walks `test*` methods only. A pin in a shared
        helper runs on every test that routes through it and is still
        invisible here. Found by measurement: see the module docstring."""
        # Constructed input, so not a pin; carried in PENDING (T4).
        helper = (
            "from pathlib import Path\n"
            "REPO = Path(__file__).resolve().parents[2]\n"
            "class T:\n"
            "    def assert_scope(self):\n"
            "        names = sorted(p.name for p in REPO.glob('*.sh'))\n"
            "        self.assertEqual(18, len(names))\n"
            "    def test_scope(self):\n"
            "        self.assert_scope()\n"
        )
        self.assertEqual([], candidates_from_source(helper, "probe.py"))

        seeing = helper.replace("    def assert_scope(self):",
                                "    def test_assert_scope(self):")
        self.assertEqual(
            [("probe.py", "T", "test_assert_scope")],
            [c.key() for c in candidates_from_source(seeing, "probe.py")],
            "positive control: the identical body, renamed to test_*, must be "
            "reported -- the blindness is the NAME, not the assertion",
        )

    def test_a_register_outside_the_corpus_is_not_reached(self):
        """Gap 4. `docs/memory/**` is gitignored and enumerated by nothing;
        this module's scope is `corpus_files()`, i.e. scripts/tests/*.py plus
        scripts/tests/workitems/*.py. Proven by the scope itself rather than
        argued: no enumerated file lies outside scripts/tests."""
        outside = [rel for _, rel in corpus_files() if rel.startswith("..")]
        self.assertEqual([], outside)
        self.assertNotIn(
            "docs", {rel.split("/")[0] for _, rel in corpus_files()},
            "the corpus scope silently widened past scripts/tests",
        )

    def test_a_value_one_function_level_deeper_is_not_reached(self):
        """Gap 5, and the sharpest of the five, because it looks covered.
        test_platform_conditional_skip_budget.py:174-187's
        `expected_skip_count()` adds four hand-pinned numbers (8, 2, 1, 1);
        the assertion at :193 reads `assertEqual(expected_skip_count(),
        len(actual_ids))` and contains no literal at all. The pins are real
        and this scanner cannot see them: it looks at assertion operands, not
        through the functions they call."""
        blind = (
            "from pathlib import Path\n"
            "REPO = Path(__file__).resolve().parents[2]\n"
            "def expected():\n"
            "    count = 0\n"
            "    count += 8\n"
            "    count += 2\n"
            "    return count\n"
            "class T:\n"
            "    def test_budget(self):\n"
            "        names = sorted(p.name for p in REPO.glob('*.sh'))\n"
            "        self.assertEqual(expected(), len(names))\n"
        )
        self.assertEqual([], candidates_from_source(blind, "probe.py"))

        seeing = blind.replace(
            "        self.assertEqual(expected(), len(names))\n",
            "        self.assertEqual(10, len(names))\n")
        self.assertEqual(
            [("probe.py", "T", "test_budget")],
            [c.key() for c in candidates_from_source(seeing, "probe.py")],
            "positive control: the same 10, inlined, must be reported",
        )

    def test_the_real_deeper_pin_is_absent_from_the_candidate_set(self):
        """The constructed instance above only shows the scanner CAN be blind
        this way. This shows it IS blind to the real one: the skip-budget
        module is a candidate only through its registration-set assertions
        (:208, :217), never through the count assertion at :193."""
        budget = [c for c in all_candidates()
                  if c.rel == "test_platform_conditional_skip_budget.py"]
        self.assertEqual(  # pin: set skip-budget-blind-spot
            ["test_no_unregistered_skip_decorator_file_exists"],
            sorted(c.method_name for c in budget),
            "the skip-budget module's reported methods changed; if "
            "test_skip_count_matches_the_pinned_per_source_budget now appears, "
            "gap 5 has been closed and this module's boundary clause is stale",
        )


if __name__ == "__main__":
    unittest.main()
