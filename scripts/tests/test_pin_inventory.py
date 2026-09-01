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
(`pin_registry.find_sites`), derives the declared population from the `# pin:`
markers actually present (`pin_registry.find_markers`), binds each marker to
the assertion it stands over (`pin_registry.bind_markers`), and fails on any
pin-shaped assertion that is neither marked nor listed in `PENDING` below.

## The unit is one ASSERTION, not the method around it (WI-0133 T2c)

Until T2c a method carrying two pin-shaped assertions was ONE record, and the
completeness check asked only whether some marker fell anywhere inside that
method's span. One marker therefore vouched for every assertion in it -- and
the marker's first field is a GROUP, which T3 and T4 read. A marker covering
two subjects of different groups makes the group a false statement exactly
where it is consulted, and no later pass can resolve it.

The corpus at the time of the change: 174 pin-shaped assertions in 147
methods; **25 methods carry more than one**, and **4 of those carry two
different declared shapes** (a scalar on one side, a collection on the other).
Those 4 are the ones a single marker could not describe truthfully. The other
21 are not a problem and were deliberately left alone -- splitting a method
that merely repeats one shape is accounting work with no gain in what the
inventory can say. `DeclaredShapeDivergenceTest` is where that distinction is
checked, in both directions, rather than intended.

Splitting the four mixed methods into separate test methods was considered and
REJECTED (PO): it is an edit to foreign test code for a bookkeeping reason,
carrying its own regression risk and improving none of those tests.

Identity had to get finer without getting a line number in it. See
`pin_registry.subject_of` for what the fourth component is and why an ordinal
inside the method would have reintroduced the exact defect a line number has.

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

`find_sites` recognises exactly one shape: an equality-family assertion,
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
   `find_sites` only walks methods whose name starts with `test`, because
   that is what unittest runs. A pin placed in a shared helper -- e.g.
   `test_handover_size_hook.py:783`'s `assert_level`, which every level test
   routes through -- is invisible, even though it runs on every one of those
   tests. Found by measuring, not by reading: of twelve one-line controls that
   turned a fixture assertion into a repository measurement, eleven were
   reported and the twelfth, the one inside `assert_level`, was not.
8. **A declared side that is COMPUTED from a declared register** rather than
   written out. `assert_set_matches(self, {(n, v) for n, v, _ in TABLE}, ...)`
   stores its value in `TABLE`, but the operand at the assertion is a
   comprehension -- neither a literal nor a bare name -- so `stores_a_value`
   never fires. This module's own
   `test_the_form_table_is_the_measured_behaviour` is an instance: it carries a
   `# pin:` marker and is NOT in the candidate set. Carries the same two
   positive controls every other gap here does -- the register as a bare
   NAME, and the value inlined as a literal, are both reported
   (`test_a_declared_side_computed_from_a_register_is_not_reached`). Left as
   it is rather than reshaped: the alternative writes the ten expected
   results a second time, and two copies of one register cannot check each
   other.

9. **The one entry that points the OTHER way: a name imported FROM the
   standard library is treated as repository-derived.** Gaps 1-8 are all
   silent failures -- a pin the pattern cannot see. This one is not, and it is
   carried here as its own clause rather than mixed in with them so the
   direction is not lost. `STDLIB_IMPORT_NAMES` is an allowlist of MODULE
   names, so `from collections import Counter` leaves `Counter` outside it and
   therefore inside `repo`; `Counter(<a pure literal>)` is then reported as a
   candidate although no repository value is measured anywhere in it. The
   harmless direction: it reports where nothing is, instead of staying quiet
   where something is.

   The precise part, and the reason it is a clause rather than a footnote:
   `ORIGIN_TRACKING_FORMS` carries `stdlib-call-counter` with `reached=True`,
   and **that verdict is correct while its reason is not**. The series uses the
   `collections.Counter` ATTRIBUTE form, which is reached through the
   measurement it carries; the from-import form is reached through the name
   `Counter` alone. A table that pins only "reached / not reached" cannot tell
   those two apart -- it would stay green if someone repaired the true carrier
   and deleted the false one.
   `test_every_reached_form_is_reached_because_of_the_measurement` is what
   surfaced it, and no test in this module distinguishes the two reasons
   today.

   Deliberately NOT repaired here (WI-0133 T2c, PO): closing it means deciding
   what `STDLIB_IMPORT_NAMES` is an allowlist OF, which is a scope decision and
   not this tranche's. It is carried in the round's finding register as #38 --
   and THIS CLAUSE IS ITS ONLY RECORD INSIDE THE REPOSITORY, which is said out
   loud because a bare "#38" would be a reference to nothing a later reader can
   follow. The clause therefore states the defect in full above rather than
   deferring to the number.

## The origin tracking is itself form-dependent

The list above says which SHAPES the pattern cannot see. This says something
narrower and easier to miss: for the shapes it CAN see, whether it sees them
depends on HOW the measured value travelled from the repository to the
assertion. The same measurement, carried three ways, was reported twice and
dropped once -- a direct `len(items)` and a dict comprehension were found, and
`for i in items: tally[i] = ...` was not, because a Subscript target binds no
`ast.Name` and so inherited nothing from the loop it sits in (WI-0133 T2b;
`test_external_tool_exit_status.py`'s `test_classification_counts` accumulates
its disposition register exactly that way and carried only its total).

That gap is closed. The property it revealed is not, and cannot be: the tracker
ENUMERATES the ways a value can travel, so a way nobody has written down yet is
invisible -- and invisible SILENTLY, because a dropped pin produces no output at
all. **Do not read the closed gap as completeness.** Three further forms are
known not to hold today (`out.append(i)`, `seen.add(i)`, `tally.update(...)` in
a loop -- accumulation by method call binds no target either), and they are
recorded rather than repaired.

This clause is a check and not an enumeration, and
`OriginTrackingIsFormDependentTest` is what makes the difference:

* it measures ten forms and pins the RESULT of each, so a form that changes
  behaviour -- in either direction -- fails;
* it keeps the three forms that do NOT hold inside the series, because a
  control series pruned down to the forms that pass stops being able to fail;
* and each reached form carries its OWN cause-removing control, because a
  control that does not grip reports "passed". The first draft used one global
  fixture swap for every form; `helper-function-return` never reads the swapped
  name, so its control left the cause fully intact and the series would have
  called that form evidence.

The obligation on anyone adding a pin in a shape not in that table is to add
the shape to the table first and read what it says.

## Both sides of the comparison run over AST shapes beyond `ast.Name`

The list above says what the pattern cannot see. This says where its two
recognisers actually run, because assuming `ast.Name` on either side is what
made T1 drop a real pin *silently*:

* **The declared side** may be an `ast.Attribute`. A class-body constant is
  written `self.EXPECTED_FLAGGED` at the assertion, not as a bare name.
* **The fixture rule** may have to look *through* an `ast.Attribute`.
  `self.<attr>` is a fixture root and is never followed -- except when the
  class body binds it to a repository-derived expression
  (`FIXTURE = FIXTURES_DIR / "..."`), which is a checked-in file and ages with
  the repository like any module-level constant.

Both cost `ParentStateDiscriminationTest` its place in the T1 candidate set,
and neither failed a test at the time: a detector that drops a real instance
drops it without a sound. `PatternLimitsTest` therefore tests each of the two
with a POSITIVE and a NEGATIVE control (`test_a_class_body_literal_is_a_
declaration_and_not_a_fixture`, `test_a_class_body_repo_path_is_not_a_fixture_
root`). A clause that only describes is an enumeration; it becomes a check when
every shape it names can fail. Both were verified by rolling the T1 fix back to
its exact pre-fix form, one half at a time -- each half turns exactly one of
the two tests red and leaves the other green.

## PENDING has an expiry date, in the test, not in a promise

T1 can only place markers in the two sites it is allowed to write
(`test_absence_only_assertions.py`'s two pins). Every other pin-shaped
assertion is declared in `PENDING` with the tranche that removes it.
`test_pending_is_exhausted` fails for any entry whose tranche already appears
in `LANDED_TRANCHES`. In T1 `LANDED_TRANCHES` is empty, so it reports nothing
-- but it exists and has been seen red, because a transition set with no
expiry becomes the next hand-maintained list, and this repository already
carries two of those.

Since T2c an entry is (file, class, method, SUBJECT, tranche): the identity
had to follow the marker down to the assertion, or a method with two subjects
could not be half-marked and half-pending. The subject is
`pin_registry.subject_of`'s rendering of the measured expression and contains
no line number, by the same argument that keeps one out of the first three
fields.
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
    Marker,
    all_markers,
    all_sites,
    assert_set_matches,
    bind_markers,
    corpus_files,
    find_markers,
    find_sites,
    floors_without_a_set,
    methods_with_divergent_declared_shapes,
    methods_with_multiple_sites,
    sites_from_source,
    subject_of,
)


# ---------------------------------------------------------------------------
# Acceptance corpus for find_sites
# ---------------------------------------------------------------------------
# The two registers below name METHODS -- they were assembled by reading the
# corpus by hand, and a method is what a person reads. They are matched on
# `PinSite.method_key()`. PENDING, which is machine-derived, names ASSERTIONS
# (WI-0133 T2c).
#
# Neither identity contains a line number. A line-bearing identity reports
# every insertion above a site as one removal plus one addition;
# test_external_tool_exit_status.py:1173-1178 records the same change measured
# both ways -- 7 additions / 4 removals line-bearing, 3 / 0 line-free.

# Live pins that find_sites MUST reach. Each was read at its site and
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


# Fixture assertions that find_sites MUST NOT report. They measure an
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
    "test_quality_scan.py": 21,
}


def _fixture_assertion_sites_by_class(rel, base_classes=None):
    """class name -> its `assertEqual(<int literal>, len(<expr>))` line
    numbers, either across a whole module or restricted to classes deriving
    from `base_classes`. Classes carrying none of the shape are absent."""
    tree = ast.parse((TESTS_DIR / rel).read_text(encoding="utf-8"))
    out = {}
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
                    out.setdefault(class_def.name, set()).add(call.lineno)
                    break
    return out


def _fixture_assertion_lines(rel, base_classes=None, excluded_classes=()):
    by_class = _fixture_assertion_sites_by_class(rel, base_classes)
    return {lineno for name, linenos in by_class.items()
            if name not in excluded_classes for lineno in linenos}


# Two classes in test_quality_scan.py derive from a fixture base class and are
# nevertheless NOT fixture assertions: both read the shipped source from disk,
# so their expected value ages with that source. They were transcribed into
# this MUST-NOT half by mistake when the corpus was assembled (WI-0133 T1) and
# `find_sites` was right to report them. What T1 recorded as a corpus/
# detector disagreement was therefore never one, and the construct that held
# it -- a register conserving a premise that had already been refuted -- is
# gone. The correction is to the corpus; the detector is unchanged.
#
#   CompletedHandlersBindingTest.test_both_dicts_are_pinned_at_4_entries
#     asserts `4 == len(ns["COMPLETED"])` (and the same for HANDLERS) over
#     `load_tool_report_module()`, i.e. the shipped scripts/lib/tool_report.py.
#     Its own class docstring calls that count a pin.
#   PiiPatternsRemovalRedProofTest.test_removing_a_pii_pattern_entry_makes_
#     its_own_finding_disappear asserts over `dict_entry_line(source, name)`
#     where `source = SCRIPT.read_text(...)`, i.e. the shipped
#     scripts/quality-scan.sh -- even though its own message calls itself a
#     "fixture assumption".
#
# Both now run as ordinary candidates and are carried in PENDING like every
# other unmarked candidate in their module (T4: test_quality_scan.py carries no
# named live pin, so it is neither a T2 nor a T3 module).
FIXTURE_ASSERTION_EXCLUDED_CLASSES = (
    "CompletedHandlersBindingTest",
    "PiiPatternsRemovalRedProofTest",
)


def fixture_assertion_sites():
    """rel -> the set of fixture-assertion line numbers in it."""
    sites = {rel: _fixture_assertion_lines(rel)
             for rel in FIXTURE_ASSERTION_MODULES}
    sites["test_quality_scan.py"] = _fixture_assertion_lines(
        "test_quality_scan.py", FIXTURE_ASSERTION_BASE_CLASSES,
        FIXTURE_ASSERTION_EXCLUDED_CLASSES)
    return sites


# One further live pin, found by code review AFTER the acceptance corpus above
# was fixed, and kept separate from it so the record of what came from where
# stays readable. The first version of `find_sites` dropped it silently:
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
        """The corpus names METHODS, so it is matched on `method_key()`. A pin
        the inventory reaches through any one of its assertions is reached."""
        found = {s.method_key() for s in all_sites()}
        missing = sorted((NAMED_LIVE_PINS | LIVE_PINS_FOUND_IN_REVIEW) - found)
        self.assertEqual(  # pin: set named-live-pins-corpus
            [], missing,
            "find_sites no longer reaches {} of the {} named live "
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

    def test_every_excluded_class_still_carries_the_shape(self):
        """The exclusions above are exclusions, not deletions: each named class
        must still carry the `assertEqual(<int>, len(...))` shape it is
        excluded for. If one stops carrying it, the exclusion is dead weight
        and must go -- an exemption nobody re-verifies is the drift this
        repository has already grown four skip lists' worth of
        (test_bsd_gnu_portability.py:1968-1972). Class NAMES, never lines: a
        line-keyed exclusion would move on every insertion above it."""
        carrying = set(_fixture_assertion_sites_by_class(
            "test_quality_scan.py", FIXTURE_ASSERTION_BASE_CLASSES))
        declared = set(FIXTURE_ASSERTION_EXCLUDED_CLASSES)
        assert_set_matches(  # pin: set fixture-corpus-exclusion
            self, declared, declared & carrying,
            "the fixture-corpus class exclusion",
        )

    def test_no_fixture_assertion_is_reported_as_a_candidate(self):
        forbidden_by_rel = fixture_assertion_sites()
        offenders = []
        for site in all_sites():
            forbidden = forbidden_by_rel.get(site.rel)
            if not forbidden:
                continue
            if site.lineno in forbidden:
                offenders.append((site.key(), site.lineno))
        self.assertEqual(
            [], offenders,
            "find_sites reported {} fixture assertion(s) as pins:\n  {}".format(
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
        found = [s.method_key() for s in sites_from_source(self.SOURCE, "probe.py")]
        self.assertEqual([("probe.py", "T", "test_names")], found)

    def test_the_same_method_without_the_call_is_not_a_candidate(self):
        """Positive control: the recognition must come from the call, not from
        the method merely touching a repository path."""
        without = self.SOURCE.replace(
            "        assert_set_matches(self, EXPECTED, names, 'the corpus')\n",
            "        self.assertTrue(names)\n")
        self.assertEqual([], sites_from_source(without, "probe.py"))


# ---------------------------------------------------------------------------
# The declared transition set
# ---------------------------------------------------------------------------
# Tranches that have landed. `test_pending_is_exhausted` fails for every
# PENDING entry naming one of these. Empty in T1 -- the guard reports nothing
# yet, and has been seen red by adding "T2" here (see this module's own red
# proofs in the WI-0133 T1 commit message).
#
# STILL EMPTY AFTER T2, deliberately. T2 marked the 10 of its 25 candidates
# whose assertion IS the collection (`set`). The other 15 pin an exact COUNT
# over a repository-derived population -- not a lower bound, not a membership
# guard, not a live derivation, not a commit SHA. None of the four registered
# groups describes them truthfully, and marking them `set` would put the same
# kind of false statement at a site that a `derived` marker over a stored
# literal would. That is a vocabulary finding, reported to the decision-maker
# rather than resolved here (PIN_GROUPS was declared ahead of the
# classification work, see pin_registry.py's docstring). Setting this to
# ("T2",) is the last step of the tranche that answers it, not of this one.
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
     'test_classification_counts',
     'len+recs:call', 'T2'),
    ('test_absence_only_assertions.py', 'NoStaleKnownFindingsTest',
     'test_no_stale_known_findings',
     'stale:name', 'T3'),
    ('test_agent_frontmatter.py', 'AgentCountTest',
     'test_agent_file_count_is_pinned',
     'files+len:call', 'T2'),
    # Newly reachable since WI-0133 T2b widened the origin tracking to
    # subscript accumulation: `invokers[self_name] = invoked` inside a loop
    # over `_iter_agent_files()`, compared against a declared dict literal --
    # the anchor case's shape exactly. It was a pin the whole time; the
    # inventory simply could not see it.
    ('test_agent_frontmatter.py', 'BodyInvocationDetectionTest',
     'test_exactly_one_agent_body_directs_invoking_another',
     'invokers:name', 'T3'),
    ('test_agent_frontmatter.py', 'ProjectMemoryContractHistoricalRedProofTest',
     'test_removing_the_global_contract_does_not_clear_the_rule',
     '.count+CONTRACT_SENTENCE_OWN_SILO+current:call', 'T3'),
    ('test_agent_frontmatter.py', 'ProjectMemoryContractHistoricalRedProofTest',
     'test_removing_the_global_contract_does_not_clear_the_rule',
     '.count+GLOBAL_SILO_CONTRACT_TOKEN+current:call', 'T3'),
    ('test_agent_frontmatter.py', 'ProjectMemoryContractHistoricalRedProofTest',
     'test_the_two_states_differ_only_by_the_inserted_sentence',
     '.count+current+sentence:call', 'T3'),
    ('test_agent_frontmatter.py', 'Tier1WriteDirectiveDetectionTest',
     'test_exactly_one_agent_is_obliged_by_neither_trigger',
     'stating:name', 'T3'),
    ('test_bsd_gnu_portability.py', 'ClassificationCountsTest',
     'test_classification_counts',
     'exempted+len:call', 'T2'),
    ('test_bsd_gnu_portability.py', 'ClassificationCountsTest',
     'test_classification_counts',
     'exempted:setcomp', 'T2'),
    ('test_bsd_gnu_portability.py', 'ClassificationCountsTest',
     'test_classification_counts',
     'len+scanned_files:call', 'T2'),
    ('test_bsd_gnu_portability.py', 'EveryMarkerNamesARegisteredCategoryTest',
     'test_every_category_in_the_tree_is_registered',
     'unregistered:name', 'T3'),
    ('test_bsd_gnu_portability.py', 'EveryMarkerNamesARegisteredCategoryTest',
     'test_every_registered_category_is_used',
     'EXEMPTION_CATEGORIES+set+sorted+used:call', 'T3'),
    ('test_bsd_gnu_portability.py', 'HistoricalMktempTemplatesAreFlaggedTest',
     'test_the_current_run_tests_carries_no_mktemp_finding',
     '.rule+MKTEMP_RULE_NAME+current:listcomp', 'T3'),
    ('test_bsd_gnu_portability.py', 'ScannedFilesCoverTheShippedScopeTest',
     'test_an_empty_scope_is_never_a_pass',
     'files+len:call', 'T2'),
    ('test_bsd_gnu_portability.py', 'ScannedFilesCoverTheShippedScopeTest',
     'test_scanned_files_cover_the_shipped_scope',
     'names:name', 'T3'),
    ('test_check_all.py', 'CompareAgainstZeroInsteadOfBaselineRedProofTest',
     'test_comparing_against_exit_zero_breaks_the_two_by_design_nonzero_checks',
     '.count+needle+original:call', 'T3'),
    ('test_check_all.py', 'CouldNotRunCountsAsPassRedProofTest',
     'test_could_not_run_folded_into_match_breaks_both_pins',
     'occurrences:name', 'T3'),
    ('test_check_all.py', 'DroppedBaselineEntryRedProofTest',
     'test_a_baseline_missing_one_entry_is_caught_by_the_contract_comparison',
     'dropped+len:call', 'T2'),
    ('test_check_all.py', 'InstallVerifyCouldNotRunRedProofTest',
     'test_without_the_report_match_a_no_op_verify_reads_as_a_divergence',
     '.NEEDLE+.count+original:call', 'T3'),
    ('test_check_all.py', 'NoteColumnQuantityRedProofTest',
     'test_a_reintroduced_quantity_is_caught_in_both_number_forms',
     '.count+injected+mutated:call', 'T2'),
    ('test_check_all.py', 'NoteColumnQuantityRedProofTest',
     'test_a_reintroduced_quantity_is_caught_in_both_number_forms',
     'hosts+len:call', 'T2'),
    ('test_ci_workflow.py', 'RealWorkflowStructureTest',
     'test_job_names_and_runners',
     '.keys+jobs+set:call', 'T4'),
    ('test_ci_workflow.py', 'RealWorkflowStructureTest',
     'test_step_counts_per_job',
     '[check-all-macos]+_find_steps+jobs+len+lines:call', 'T4'),
    ('test_ci_workflow.py', 'RealWorkflowStructureTest',
     'test_step_counts_per_job',
     '[python-tests]+_find_steps+jobs+len+lines:call', 'T4'),
    ('test_command_check.py', 'CommandPrerequisitesEmptyFilesEntriesRemovalStructuralProofTest',
     'test_removal_is_a_check_command_no_op_but_shrinks_the_dict',
     '.COMMAND_PREREQUISITES+cc+len:call', 'T3'),
    ('test_command_check.py', 'CommandPrerequisitesEmptyFilesEntriesRemovalStructuralProofTest',
     'test_the_two_empty_files_entries_are_exactly_these_two',
     'empty_files_entries:name', 'T3'),
    ('test_command_check.py', 'CommandPrerequisitesFilesRemovalRedProofTest',
     'test_removing_the_entry_drops_its_file_reason',
     '.COMMAND_PREREQUISITES+cc+len:call', 'T3'),
    ('test_command_check.py', 'CommandPrerequisitesFilesRemovalRedProofTest',
     'test_removing_the_entry_drops_its_file_reason',
     'entries_with_files+len:call', 'T3'),
    ('test_command_check.py', 'CommandPrerequisitesP7DeployPointsAtPrepareArtifactTest',
     'test_p7_deploy_prerequisite_is_exactly_the_prepare_artifact',
     '.COMMAND_PREREQUISITES+[files]+[p7-deploy]+cc:item', 'T3'),
    ('test_command_check.py', 'CommandPrerequisitesSchemaTest',
     'test_entry_count_is_pinned_at_16',
     '.COMMAND_PREREQUISITES+cc+len:call', 'T3'),
    ('test_command_check.py', 'GateFileClaimsStructuralTest',
     'test_all_eight_gates_claim_an_artifact',
     'claims+set:call', 'T3'),
    ('test_command_check.py', 'GateFileClaimsStructuralTest',
     'test_claimed_paths_match_the_phase_folder_convention',
     'claims:name', 'T3'),
    ('test_command_check.py', 'GateFileClaimsStructuralTest',
     'test_gate_p5_claims_sprint_md_not_a_phase_folder_gate_file',
     '[gate-p5]+claims:item', 'T3'),
    ('test_command_check.py', 'GateP5UsesSprintMdTest',
     'test_gate_p5_is_mapped_to_sprint_md',
     '.GATE_FILE_PATHS+[gate-p5]+cc:item', 'T3'),
    ('test_command_check.py', 'TemplateTreeExcludesGateArtifactsTest',
     'test_gate_p6_and_p7_are_absent_from_the_claim_set_for_a_different_reason',
     '[gate-p6]+claims:item', 'T3'),
    ('test_command_check.py', 'TemplateTreeExcludesGateArtifactsTest',
     'test_gate_p6_and_p7_are_absent_from_the_claim_set_for_a_different_reason',
     '[gate-p7]+claims:item', 'T3'),
    ('test_command_check.py', 'TemplateTreeExcludesGateArtifactsTest',
     'test_the_exclusion_has_real_work_to_do',
     'excluded:name', 'T3'),
    ('test_command_check.py', 'UnknownCommandTest',
     'test_every_shipped_command_name_is_not_rejected_as_unknown',
     'len+shipped_names:call', 'T2'),
    ('test_command_frontmatter.py', 'MeasuredCorpusSizeTest',
     'test_pattern_derived_count_is_pinned',
     'len+matched:call', 'T2'),
    ('test_command_frontmatter.py', 'MeasuredCorpusSizeTest',
     'test_total_command_file_count_is_pinned',
     'files+len:call', 'T2'),
    ('test_conformance_run.py', 'CheckTableAlignmentTest',
     'test_all_seven_columns_are_five_entries_long',
     'columns+len:call', 'T3'),
    ('test_conformance_run.py', 'CheckTableAlignmentTest',
     'test_all_seven_columns_are_five_entries_long',
     'len+values:call', 'T3'),
    ('test_conformance_run.py', 'CheckTableUncoveredColumnsValuesTest',
     'test_check_arg_shape_is_a_three_two_split',
     '[CHECK_ARG_SHAPE]+parse_full_check_table:item', 'T3'),
    ('test_conformance_run.py', 'CheckTableUncoveredColumnsValuesTest',
     'test_check_c2_exempt_only_anchor_is_exempt',
     '[CHECK_C2_EXEMPT]+parse_full_check_table:item', 'T3'),
    ('test_conformance_run.py', 'CheckTableUncoveredColumnsValuesTest',
     'test_check_has_summary_line_only_anchor_lacks_one',
     '[CHECK_HAS_SUMMARY_LINE]+parse_full_check_table:item', 'T3'),
    ('test_conformance_run.py', 'CheckTableUncoveredColumnsValuesTest',
     'test_check_subcmd_only_anchor_carries_a_subcommand',
     '[CHECK_SUBCMD]+parse_full_check_table:item', 'T3'),
    ('test_conformance_run.py', 'RequiredSkeletonLineCountPinTest',
     'test_anchor_branch_requires_two_lines',
     '[anchor]+len+parse_rule3_required_lines:call', 'T3'),
    ('test_conformance_run.py', 'RequiredSkeletonLineCountPinTest',
     'test_generic_branch_requires_three_lines',
     '[generic]+len+parse_rule3_required_lines:call', 'T3'),
    ('test_conformance_run.py', 'RequiredSkeletonLineCountPinTest',
     'test_the_required_lines_are_the_documented_ones',
     'parse_rule3_required_lines:call', 'T3'),
    ('test_external_tool_exit_status.py', 'ExternalToolExitStatusTest',
     'test_classification_counts',
     'by_disposition:name', 'T2'),
    ('test_external_tool_exit_status.py', 'ExternalToolExitStatusTest',
     'test_classification_counts',
     'invocations+len:call', 'T2'),
    ('test_handover_epilogue_bullet.py', 'EpilogueOpenBulletTest',
     'test_104_files_carry_the_disambiguated_wording',
     'bare_count:name', 'T2'),
    ('test_handover_epilogue_bullet.py', 'EpilogueOpenBulletTest',
     'test_104_files_carry_the_disambiguated_wording',
     'suffixed_count:name', 'T2'),
    ('test_handover_size_hook.py', 'WriteGateCoverageTest',
     'test_every_declared_write_tool_warns',
     '.HANDOVER_WRITE_TOOLS+AGENT_MONITOR:attr', 'T4'),
    ('test_heredoc_interpolation_scan.py', 'ClassificationCountsTest',
     'test_classification_counts',
     'findings+len:call', 'T2'),
    ('test_heredoc_interpolation_scan.py', 'ClassificationCountsTest',
     'test_classification_counts',
     'len+sites:call', 'T2'),
    ('test_heredoc_interpolation_scan.py', 'FiveOriginalRunTestsSitesAreNoLongerFlaggedTest',
     'test_run_tests_sh_carries_no_finding_after_the_wi_0129_fix',
     'heredoc_openers+len:call', 'T3'),
    ('test_heredoc_interpolation_scan.py', 'ScannedFilesCoverTheShippedScopeTest',
     'test_scanned_files_cover_the_shipped_scope',
     'files+len:call', 'T2'),
    ('test_instinct_registers_agree.py', 'ClassificationCountsTest',
     'test_classification_counts',
     'index_ids+len:call', 'T2'),
    ('test_instinct_registers_agree.py', 'ClassificationCountsTest',
     'test_classification_counts',
     'len+sampler_ids:call', 'T2'),
    ('test_instinct_registers_agree.py', 'ExclusionRegressionPinTest',
     'test_mention_only_ids_are_not_parsed_as_index_entries',
     'leaked:name', 'T3'),
    ('test_instinct_registers_agree.py', 'ExclusionRegressionPinTest',
     'test_mention_only_ids_are_not_parsed_as_sampler_entries',
     'leaked:name', 'T3'),
    ('test_live_status_claims.py', 'DriftedRegisterHistoricalRedProofTest',
     'test_the_same_file_in_the_working_tree_is_clean',
     'DRIFTED_REGISTER_PATH+current+scan_text:call', 'T4'),
    ('test_live_status_claims.py', 'HistoryIsLetThroughTest',
     'test_the_whole_history_carrying_files_are_clean_at_the_pinned_commit',
     'rel+scan_text+text:call', 'T4'),
    ('test_manual_lint.py', 'KindVocabularyExhaustiveTest',
     'test_valid_kinds_count_is_pinned_at_nineteen',
     'VALID_KINDS+len:call', 'T2'),
    ('test_memory_lint_checklist_binding.py', 'RedProofAddingAnUndefinedChapterBulletTest',
     'test_adding_a_z_bullet_reports_z_as_stale',
     'chapter_letters+script_letters:binop', 'T4'),
    ('test_memory_lint_checklist_binding.py', 'RedProofRemovingAChapterBulletTest',
     'test_removing_the_g_bullet_reports_g_as_undocumented',
     'chapter_letters+script_letters:binop', 'T4'),
    ('test_next_steps_lists.py', 'GateTransitionsCountTest',
     'test_gate_count_is_pinned_at_8',
     'GATE_TRANSITIONS+len:call', 'T4'),
    ('test_next_steps_lists.py', 'GateTransitionsRemovalRedProofTest',
     'test_removing_one_gate_breaks_the_count_pin',
     'GATE_TRANSITIONS+len:call', 'T4'),
    ('test_next_steps_lists.py', 'PhaseCountRemovalRedProofTest',
     'test_removing_one_phase_breaks_the_phase_count_pin',
     'PHASE_SEQUENCES+len:call', 'T4'),
    ('test_next_steps_lists.py', 'PhaseSequencesExistenceTest',
     'test_phase_count_is_pinned_at_9',
     'PHASE_SEQUENCES+len:call', 'T4'),
    ('test_next_steps_lists.py', 'PhaseSequencesExistenceTest',
     'test_total_command_count_is_pinned_at_50',
     'total:name', 'T4'),
    ('test_next_steps_lists.py', 'PhaseSequencesRemovalRedProofTest',
     'test_removing_one_command_breaks_the_total_count_pin',
     'total:name', 'T4'),
    ('test_next_steps_lists.py', 'UtilityCommandsRedProofTest',
     'test_removing_one_entry_changes_the_length_by_one',
     'len+mutated:call', 'T4'),
    ('test_next_steps_lists.py', 'UtilityCommandsVocabularyTest',
     'test_total_command_count_is_pinned_at_8',
     'UTILITY_COMMANDS+len:call', 'T4'),
    ('test_phase_docs_lint.py', 'CheckCPhaseEnumTest',
     'test_valid_phases_count_is_pinned_at_nine',
     'VALID_PHASES+len:call', 'T4'),
    ('test_phase_docs_lint.py', 'CheckDStatusEnumTest',
     'test_valid_statuses_count_is_pinned_at_six',
     'VALID_STATUSES+len:call', 'T4'),
    ('test_phase_docs_lint.py', 'CheckKGateVerdictTest',
     'test_valid_gate_verdicts_count_is_pinned_at_five',
     'VALID_GATE_VERDICTS_ENUM+len:call', 'T4'),
    ('test_phase_docs_lint.py', 'CheckKGateVerdictTest',
     'test_valid_sprint_verdicts_count_is_pinned_at_four',
     'VALID_SPRINT_VERDICTS_ENUM+len:call', 'T4'),
    ('test_phase_docs_lint.py', 'LivingFilesSkipTest',
     'test_living_file_names_count_is_pinned_at_six',
     'LIVING_FILE_NAMES+len:call', 'T4'),
    ('test_phase_docs_lint.py', 'LivingFilesSkipTest',
     'test_other_living_filenames_are_skipped_even_with_broken_frontmatter',
     'len+non_sprint_names:call', 'T4'),
    ('test_phase_docs_lint.py', 'PhaseFoldersSweepTest',
     'test_every_phase_folder_is_reached_by_the_default_scan',
     'folders+len:call', 'T4'),
    ('test_pin_inventory.py', 'AssertSetMatchesIsItselfAPinShapeTest',
     'test_an_assert_set_matches_call_is_a_candidate',
     'found:name', 'T4'),
    ('test_pin_inventory.py', 'DeclaredShapeDivergenceTest',
     'test_a_same_shape_pair_is_not_a_divergence',
     'len+sites:call', 'T4'),
    ('test_pin_inventory.py', 'DeclaredShapeDivergenceTest',
     'test_a_same_shape_pair_is_not_a_divergence',
     'methods_with_multiple_sites+sites:call', 'T4'),
    ('test_pin_inventory.py', 'DeclaredShapeDivergenceTest',
     'test_a_scalar_against_a_collection_is_a_divergence',
     'methods_with_divergent_declared_shapes+sites:call', 'T4'),
    ('test_pin_inventory.py', 'FloorRequiresASetTest',
     'test_a_floor_whose_subject_carries_no_set_is_reported',
     'floors_without_a_set+markers:call', 'T4'),
    ('test_pin_inventory.py', 'FloorRequiresASetTest',
     'test_the_pairing_is_per_file_and_not_per_bare_id',
     'floors_without_a_set+markers:call', 'T4'),
    ('test_pin_inventory.py', 'MarkerBindsToOneAssertionTest',
     'test_a_marker_covers_only_the_assertion_it_sits_on',
     '.key+bound+sites+sorted:call', 'T4'),
    ('test_pin_inventory.py', 'MarkerBindsToOneAssertionTest',
     'test_a_marker_covers_only_the_assertion_it_sits_on',
     'bound+sorted:call', 'T4'),
    ('test_pin_inventory.py', 'MarkerBindsToOneAssertionTest',
     'test_a_marker_naming_no_assertion_is_reported_and_not_dropped',
     'unbound:name', 'T4'),
    ('test_pin_inventory.py', 'MarkerBindsToOneAssertionTest',
     'test_a_marker_on_the_line_above_binds_to_the_assertion_below',
     'bound+sorted:call', 'T4'),
    # A pin, and unmarked on purpose: it stores an exact COUNT over a
    # repository-derived population (how many pin-shaped assertions the anchor
    # method carries), which is precisely the shape T2 measured 15 instances of
    # and found no truthful group for. Marking it `set` would put the same
    # false statement at a site that T2 declined to write.
    ('test_pin_inventory.py', 'OriginTrackingIsFormDependentTest',
     'test_the_anchor_case_carries_both_of_its_assertions',
     'found+len:call', 'T4'),
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_class_body_literal_is_a_declaration_and_not_a_fixture',
     '.method_key+declared_in_class_body+sites_from_source:listcomp', 'T4'),
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_class_body_repo_path_is_not_a_fixture_root',
     '.method_key+repo_path_in_class_body+sites_from_source:listcomp', 'T4'),
    # Constructed input like its PatternLimitsTest siblings, so not a pin: its
    # two positive controls compare against source strings the test itself
    # wrote, which cannot age.
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_declared_side_computed_from_a_register_is_not_reached',
     '.method_key+by_name+head+sites_from_source:listcomp', 'T4'),
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_declared_side_computed_from_a_register_is_not_reached',
     '.method_key+head+inline+sites_from_source:listcomp', 'T4'),
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_number_in_a_docstring_is_not_reached',
     '.method_key+seeing+sites_from_source:listcomp', 'T4'),
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_pin_inside_a_helper_method_is_not_reached',
     '.method_key+seeing+sites_from_source:listcomp', 'T4'),
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_value_one_function_level_deeper_is_not_reached',
     '.method_key+seeing+sites_from_source:listcomp', 'T4'),
    ('test_pin_inventory.py', 'PinMarkerInventoryTest',
     'test_a_marker_with_an_unknown_group_is_rejected',
     '.group+.pin_id+markers:listcomp', 'T4'),
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_an_assertion_inserted_between_two_sites_moves_neither',
     'after+before+len:call', 'T4'),
    # WI-0133 T2c's own sites. All four are constructed or structural rather
    # than stored values, and are carried here for the same reason every other
    # PatternLimitsTest sibling is: the marker vocabulary has no group meaning
    # "not a pin", and inventing one is not this tranche's job.
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_the_anchor_method_is_two_sites_with_different_subjects',
     '.declared_shape+found:setcomp', 'T4'),
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_the_anchor_method_is_two_sites_with_different_subjects',
     '.subject+found+len:call', 'T4'),
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_the_anchor_method_is_two_sites_with_different_subjects',
     'found+len:call', 'T4'),
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_the_identity_does_not_depend_on_the_interpreter',
     '.subject+[0]+sites:attr', 'T4'),
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_the_identity_does_not_depend_on_the_interpreter',
     'len+sites:call', 'T4'),
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_two_assertions_in_one_method_are_two_sites',
     '.key+sites:setcomp', 'T4'),
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_two_assertions_in_one_method_are_two_sites',
     'len+sites:call', 'T4'),
    ('test_quality_scan.py', 'CompletedHandlersBindingTest',
     'test_both_dicts_are_pinned_at_4_entries',
     '[COMPLETED]+len+ns:call', 'T4'),
    ('test_quality_scan.py', 'CompletedHandlersBindingTest',
     'test_both_dicts_are_pinned_at_4_entries',
     '[HANDLERS]+len+ns:call', 'T4'),
    ('test_quality_scan.py', 'CompletedHandlersRemovalRedProofTest',
     'test_removing_a_completed_entry_still_present_in_handlers_raises_keyerror',
     '.count+needle+source:call', 'T4'),
    ('test_quality_scan.py', 'ConfigFilenamesRemovalRedProofTest',
     'test_removing_a_config_filename_makes_its_own_finding_disappear',
     '.count+CONFIG_LOOP_NEEDLE+source:call', 'T4'),
    ('test_quality_scan.py', 'ConfigFilenamesShapeTest',
     'test_config_filenames_list_is_pinned_at_6_entries',
     '.count+CONFIG_LOOP_NEEDLE+source:call', 'T4'),
    ('test_quality_scan.py', 'ConsentTermsRemovalRedProofTest',
     'test_removing_a_consent_term_makes_the_finding_fire_again',
     '.count+CONSENT_LOOP_NEEDLE+source:call', 'T4'),
    ('test_quality_scan.py', 'ConsentTermsShapeTest',
     'test_consent_terms_list_is_pinned_at_4_entries',
     '.count+CONSENT_LOOP_NEEDLE+source:call', 'T4'),
    ('test_quality_scan.py', 'PiiPatternsRemovalRedProofTest',
     'test_removing_a_pii_pattern_entry_makes_its_own_finding_disappear',
     'len+lines:call', 'T4'),
    ('test_quality_scan.py', 'PiiPatternsShapeTest',
     'test_pii_patterns_are_pinned_at_4_entries',
     'len+names:call', 'T4'),
    ('test_quality_scan.py', 'SeveritiesRemovalRedProofTest',
     'test_removing_a_severity_silently_drops_its_bucket_from_the_count',
     '.SEVERITIES_NEEDLE+.count+source:call', 'T4'),
    ('test_quality_scan.py', 'SeveritiesShapeMatchesSourceTest',
     'test_severities_shape_equals_the_extracted_source',
     '[SEVERITIES]+ns+tuple:call', 'T4'),
    ('test_quality_scan.py', 'SkipDirsDefinitionsStayEqualTest',
     'test_both_skip_dirs_definitions_are_identical',
     'first+len:call', 'T4'),
    ('test_quality_scan.py', 'SkipDirsDefinitionsStayEqualTest',
     'test_both_skip_dirs_definitions_are_identical',
     'len+tuples:call', 'T4'),
    ('test_quality_scan.py', 'SkipDirsMatchesSastModuleTest',
     'test_sast_module_skip_dirs_equals_both_quality_scan_sh_definitions',
     'len+script_dirs:call', 'T4'),
    ('test_quality_scan.py', 'ToolReportCompletedShapeMatchesSourceTest',
     'test_completed_shape_equals_the_extracted_source',
     '[COMPLETED]+ns:item', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'ExtensionCountTest',
     'test_total_extension_count_is_pinned_at_19',
     'total:name', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyDoesNotRaiseTest',
     'test_missing_key_is_swallowed_and_the_finding_is_dropped',
     '.keys+PATTERNS+rule_name+set:call', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyPositionDependentTruncationTest',
     'test_breaking_the_last_rule_in_dict_order_loses_only_the_tail',
     '[0]+[line]+findings:item', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyPositionDependentTruncationTest',
     'test_breaking_the_last_rule_in_dict_order_loses_only_the_tail',
     'findings+len:call', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyPositionDependentTruncationTest',
     'test_control_finds_both_lines',
     '[0]+[line]+findings:item', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyPositionDependentTruncationTest',
     'test_control_finds_both_lines',
     '[1]+[line]+findings:item', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyPositionDependentTruncationTest',
     'test_control_finds_both_lines',
     'findings+len:call', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PatternsRuleCountRemovalRedProofTest',
     'test_removing_one_rule_breaks_the_count_pin',
     'PATTERNS+len:call', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PatternsRuleCountTest',
     'test_rule_count_is_pinned_at_5',
     'PATTERNS+len:call', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PerExtensionPositiveFixtureTest',
     'test_every_claimed_extension_fires_the_rule',
     'checked:name', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PerExtensionRemovalRedProofTest',
     'test_removing_one_extension_silences_the_rule_for_that_extension',
     'checked:name', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PerExtensionRemovalRedProofTest',
     'test_removing_one_extension_silences_the_rule_for_that_extension',
     'findings:name', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PerRuleForeignExtensionNegativeTest',
     'test_foreign_extension_produces_no_finding_for_that_rule',
     'findings:name', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PerRulePositiveFixtureTest',
     'test_each_rule_fires_on_its_own_fixture',
     '[line]+finding:item', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'PerRulePositiveFixtureTest',
     'test_each_rule_fires_on_its_own_fixture',
     'findings+len:call', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'RuleShapeKeysTest',
     'test_every_rule_has_exactly_the_four_keys',
     '.keys+rule+set:call', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'TruncationCapTest',
     'test_exactly_50_matches_produce_50_with_no_marker',
     'findings+len:call', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'TruncationCapTest',
     'test_more_than_50_matches_are_capped_plus_one_truncation_marker',
     '[type]+marker:item', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'TruncationCapTest',
     'test_more_than_50_matches_are_capped_plus_one_truncation_marker',
     'findings+len:call', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'TruncationCapTest',
     'test_the_50_real_findings_preceding_the_marker_are_unaffected',
     '[type]+finding:item', 'T4'),
    ('test_quality_scan_sast_patterns.py', 'TruncationCapTest',
     'test_the_50_real_findings_preceding_the_marker_are_unaffected',
     'len+real:call', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_bare_integer_is_seconds',
     'parse_duration_seconds:call', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_days_suffix',
     'parse_duration_seconds:call', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_hours_suffix',
     'parse_duration_seconds:call', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_minutes_suffix',
     'parse_duration_seconds:call', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_numeric_string_is_seconds',
     'parse_duration_seconds:call', 'T4'),
    ('workitems/test_duration.py', 'ParseDurationSecondsTest',
     'test_seconds_suffix',
     'parse_duration_seconds:call', 'T4'),
    ('workitems/test_frontmatter.py', 'FrontmatterRoundTripTest',
     'test_parses_genuine_inline_list',
     '[refs]+parsed:item', 'T4'),
    ('workitems/test_frontmatter.py', 'FrontmatterRoundTripTest',
     'test_round_trips_title_containing_a_literal_backslash',
     '[title]+parsed:item', 'T4'),
    ('workitems/test_frontmatter.py', 'FrontmatterRoundTripTest',
     'test_round_trips_title_containing_hash',
     '[title]+parsed:item', 'T4'),
    ('workitems/test_frontmatter.py', 'FrontmatterRoundTripTest',
     'test_round_trips_title_starting_with_bracket',
     '[title]+parsed:item', 'T4'),
    ('workitems/test_frontmatter.py', 'FrontmatterRoundTripTest',
     'test_round_trips_title_with_both_apostrophe_and_double_quote',
     '[title]+parsed:item', 'T4'),
    ('workitems/test_sweep.py', 'SweepTest',
     'test_stale_heartbeat_with_branch_commits_becomes_parked',
     '[parked]+report:item', 'T4'),
    ('workitems/test_sweep.py', 'SweepTest',
     'test_stale_heartbeat_without_branch_commits_stays_in_progress',
     '[left_in_progress]+report:item', 'T4'),
    ('workitems/test_youtrack.py', 'HttpTransportTest',
     'test_sends_bearer_auth_header_and_returns_parsed_json',
     'result:name', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackClaimingTest',
     'test_a_non_utc_aware_clock_is_normalized_to_utc_in_the_written_heartbeat',
     '[heartbeat]+claimed:item', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackCreateFactoryTest',
     'test_env_token_with_trailing_newline_is_stripped',
     '.token+backend:attr', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackCreateFactoryTest',
     'test_happy_path_reads_token_from_environment_not_config',
     '.token+backend:attr', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackCreateRollbackTest',
     'test_create_does_not_delete_when_initial_state_is_accepted',
     '._issues+len+transport:call', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackCreateRollbackTest',
     'test_create_does_not_delete_when_initial_state_is_accepted',
     '[status]+item:item', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackLinkTypeNameMapTest',
     'test_renamed_link_type_name_resolves_via_config',
     '[links]+item:item', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackPaginationTest',
     'test_list_returns_everything_even_when_the_fake_caps_page_size',
     'items+len:call', 'T4'),
    ('workitems/test_youtrack.py', 'YouTrackSetEstimateTest',
     'test_scalar_estimate_is_not_confused_with_an_enum_shaped_field',
     '[estimate]+updated:item', 'T4'),
})


class PinMarkerInventoryTest(unittest.TestCase):
    """(a) The inventory. Derived from the markers actually present, never
    typed: the count of pins is exactly the kind of value ADR-0012 says must
    be generated."""

    def test_the_marker_inventory_is_the_registered_set(self):
        assert_set_matches(  # pin: set pin-marker-inventory
            self,
            {("test_absence_only_assertions.py", "floor", "tests-corpus-files"),
             ("test_absence_only_assertions.py", "set", "parent-state-flagged"),
             ("test_absence_only_assertions.py", "set",
              "parent-state-not-flagged"),
             ("test_absence_only_assertions.py", "set", "tests-corpus-files"),
             ("test_bsd_gnu_portability.py", "set",
              "portability-exempted-sites"),
             ("test_bsd_gnu_portability.py", "set",
              "portability-known-findings"),
             ("test_conformance_run.py", "set", "check-table-column-names"),
             ("test_docs_dotfile_gitignore_coverage.py", "set",
              "docs-dotfile-block-patterns"),
             ("test_docs_dotfile_gitignore_coverage.py", "set",
              "docs-dotfile-concrete-artifacts"),
             ("test_external_tool_exit_status.py", "set",
              "external-tool-scanned-scripts"),
             ("test_heredoc_interpolation_scan.py", "set",
              "heredoc-known-findings"),
             ("test_pin_inventory.py", "derived", "fixture-corpus-site-counts"),
             ("test_pin_inventory.py", "set", "divergent-shape-methods"),
             ("test_pin_inventory.py", "set", "fixture-corpus-exclusion"),
             ("test_pin_inventory.py", "set", "named-live-pins-corpus"),
             ("test_pin_inventory.py", "set",
              "origin-tracking-fixture-control"),
             ("test_pin_inventory.py", "set", "origin-tracking-form-table"),
             ("test_pin_inventory.py", "set", "pending-transition-set"),
             ("test_pin_inventory.py", "set", "pin-marker-inventory"),
             ("test_pin_inventory.py", "set", "same-shape-multi-site-methods"),
             ("test_pin_inventory.py", "set", "skip-budget-blind-spot"),
             ("test_pin_inventory.py", "set", "unbound-markers"),
             ("test_platform_conditional_skip_budget.py", "set",
              "registered-skip-decorator-files"),
             ("test_shell_script_syntax.py", "set",
              "shell-syntax-scanned-scripts")},
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


class FloorRequiresASetTest(unittest.TestCase):
    """The `floor` group's admissibility rule, turned from prose into a check.

    `PIN_GROUPS["floor"]` has said since T1 that a floor is admissible ONLY
    where the same subject also carries a `set` pin, because a floor cannot
    see a swap: one entry out, one entry in, count unchanged. Until now that
    was a sentence in a dict value -- a formulated obligation with no
    mechanism, which is the exact failure shape this module exists to close
    (ADR-0012 obligation 1 stood the same way before T1).

    Written as an INVARIANT rather than as an ordering rule ("place the set
    pin first"). An ordering can be obeyed once and broken afterwards; an
    invariant also holds for a floor added in six months by someone who never
    read this round. It therefore replaces the tranche ordering that would
    otherwise have had to carry the rule.
    """

    def test_no_floor_marker_stands_without_a_set_marker(self):
        self.assertEqual(
            [], floors_without_a_set(all_markers()),
            "`floor` marker(s) whose subject carries no `set` marker. A floor "
            "on its own cannot see a swap, so it is not a membership guard; "
            "either add a `# pin: set <same-id>` beside it or reclassify it.",
        )

    def test_a_floor_whose_subject_carries_no_set_is_reported(self):
        """The red proof. Constructed rather than measured on the live pair,
        so that repairing or moving that pair cannot make this test lie about
        what the invariant can see."""
        # Constructed input, so not a pin; carried in PENDING (T4) for the
        # same reason as AssertSetMatchesIsItselfAPinShapeTest's.
        markers = [Marker("probe.py", 12, "floor", "orphan-subject")]
        self.assertEqual([("probe.py", 12, "orphan-subject")],
                         floors_without_a_set(markers))

    def test_a_set_without_a_floor_is_silent(self):
        """The counter-proof, and the asymmetry is a decision, not an
        oversight (WI-0133 T2, decided by the PO). Most membership guards need
        no lower bound at all; requiring one would force a coupling nobody
        asked for and would make every `set` pin drag a second assertion
        along. Without this test the invariant could quietly be
        "completed" into a symmetric one, and the completion would look like
        a tidy-up rather than the scope change it is."""
        markers = [Marker("probe.py", 12, "set", "lonely-subject")]
        self.assertEqual([], floors_without_a_set(markers))

    def test_the_pairing_is_per_file_and_not_per_bare_id(self):
        """A pin id is a short slug and nothing enforces that it is unique
        across the corpus. Matching a floor to any `set` sharing its bare id
        would let an unrelated pin in another module satisfy the rule by
        coincidence -- a guard an uninvolved source can satisfy is not a
        guard. `Marker.key()` is already (file, group, id) for the same
        reason, so the subject is (file, id)."""
        markers = [Marker("a.py", 1, "floor", "shared-slug"),
                   Marker("b.py", 2, "set", "shared-slug")]
        self.assertEqual([("a.py", 1, "shared-slug")],
                         floors_without_a_set(markers))


class PinCompletenessTest(unittest.TestCase):
    """(b) Completeness. Every candidate is either marked at its own site or
    declared in PENDING with the tranche that removes it. Nothing sits
    unaccounted for."""

    def test_every_assertion_is_marked_or_pending(self):
        """Per ASSERTION since WI-0133 T2c, not per method.

        The predecessor asked whether SOME marker fell anywhere inside the
        method's span, so one marker vouched for every pin-shaped assertion in
        it. `MarkerBindsToOneAssertionTest` is the red proof that it no longer
        does; this is the check that consumes the binding."""
        bound, _unbound = bind_markers(all_sites(), all_markers())
        pending_keys = {(rel, cls, method, subject)
                        for rel, cls, method, subject, _ in PENDING}
        unaccounted = []
        for site in all_sites():
            if site.key() in bound or site.key() in pending_keys:
                continue
            unaccounted.append(site.key())
        self.assertEqual(
            [], sorted(unaccounted),
            "{} pin-shaped assertion(s) name themselves neither as a pin nor "
            "as pending (ADR-0012 obligation 1). For each one, EITHER add a "
            "`# pin: <group> <id>` marker ON THAT ASSERTION -- a marker on a "
            "sibling assertion in the same method does not cover it -- "
            "groups: {} -- OR, "
            "if it is not a pin (its expected value follows from an input the "
            "test itself built, so it cannot age), say so at the site and add "
            "it to PENDING with the tranche that resolves it:\n  {}".format(
                len(unaccounted), ", ".join(sorted(PIN_GROUPS)),
                "\n  ".join(map(str, sorted(unaccounted)))),
        )

    def test_no_pending_entry_is_stale(self):
        """Drift in the other direction: an entry that is no longer a
        candidate has either been fixed without being removed from PENDING, or
        the detector stopped seeing it. Both need a look.

        A third cause is neither, and it is the one that sends people to the
        wrong file: a PENDING entry is identified by (file, class, method,
        subject), and `subject` renders the MEASURED EXPRESSION. Renaming a
        local variable inside a pinned assertion therefore moves the key, and
        the rename happened in another module while the red test lives here.
        That radius is the deliberate price of an identity that hangs on the
        expression rather than on its position -- a key that survives a rename
        is a key that cannot see a swap. The message below says so, because a
        red result without the connection is a false alarm and the same result
        with it is an instruction."""
        site_keys = {s.key() for s in all_sites()}
        stale = sorted(key for key in
                       {(rel, cls, m, subject) for rel, cls, m, subject, _ in PENDING}
                       if key not in site_keys)
        self.assertEqual(  # pin: set pending-transition-set
            [], stale,
            "PENDING entr(ies) that all_sites() no longer reports. Either the "
            "site is gone (remove the entry), or its IDENTITY moved -- the key "
            "ends in the rendered MEASURED EXPRESSION, so renaming a local "
            "variable inside the pinned assertion changes it. In that case the "
            "edit is in the other module and the repair is this tuple:\n  {}"
            .format("\n  ".join(map(str, stale))),
        )

    def test_every_pending_entry_names_a_declared_tranche(self):
        undeclared = sorted({tranche for *_, tranche in PENDING}
                            - set(DECLARED_TRANCHES))
        self.assertEqual([], undeclared)

    def test_pending_is_exhausted(self):
        """(d) The expiry. A transition set without an end date becomes the
        next hand-maintained list; this repository already carries two. Every
        entry names the tranche that removes it, and once that tranche is in
        LANDED_TRANCHES the entry must be gone."""
        overdue = sorted((rel, cls, method, subject, tranche)
                         for rel, cls, method, subject, tranche in PENDING
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
        self.assertEqual([], sites_from_source(blind, "probe.py"))

        seeing = blind.replace(
            "        self.assertTrue(names)\n",
            "        self.assertEqual(18, len(names))\n")
        self.assertEqual(
            [("probe.py", "T", "test_scope")],
            [s.method_key() for s in sites_from_source(seeing, "probe.py")],
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
        self.assertEqual([], sites_from_source(blind, "probe.py"))

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
        self.assertEqual([], sites_from_source(helper, "probe.py"))

        seeing = helper.replace("    def assert_scope(self):",
                                "    def test_assert_scope(self):")
        self.assertEqual(
            [("probe.py", "T", "test_assert_scope")],
            [s.method_key() for s in sites_from_source(seeing, "probe.py")],
            "positive control: the identical body, renamed to test_*, must be "
            "reported -- the blindness is the NAME, not the assertion",
        )

    def test_a_class_body_literal_is_a_declaration_and_not_a_fixture(self):
        """The declared side is not always an `ast.Name`.

        A class-body constant is written `self.EXPECTED` at the assertion,
        i.e. an `ast.Attribute` whose value is `Name("self")`. The first
        version of `find_sites` only accepted a bare `ast.Name` there and
        silently dropped `ParentStateDiscriminationTest`, a real pin, without
        reporting a gap -- it took a reviewer reading the corpus by hand to
        surface it. Named in the boundary clause and tested here so the next
        unforeseen AST shape is a failing test rather than a second silent
        drop.

        Negative control on the same input: the identical name bound in
        `setUp` is a fixture the test itself built and must NOT be reported.
        Without it, a detector that followed every `self.<attr>` would pass
        the positive half."""
        # Constructed input, so not a pin; carried in PENDING (T4).
        declared_in_class_body = (
            "from pathlib import Path\n"
            "REPO = Path(__file__).resolve().parents[2]\n"
            "class T:\n"
            "    EXPECTED = frozenset({'a.sh', 'b.sh'})\n"
            "    def test_names(self):\n"
            "        names = {p.name for p in REPO.glob('*.sh')}\n"
            "        self.assertEqual(self.EXPECTED, names)\n"
        )
        self.assertEqual(
            [("probe.py", "T", "test_names")],
            [s.method_key() for s in sites_from_source(declared_in_class_body,
                                                     "probe.py")],
            "a class-body literal reached as self.EXPECTED is a DECLARATION; "
            "recognising only ast.Name on the declared side drops it",
        )

        bound_in_setup = declared_in_class_body.replace(
            "    EXPECTED = frozenset({'a.sh', 'b.sh'})\n",
            "    def setUp(self):\n"
            "        self.EXPECTED = frozenset({'a.sh', 'b.sh'})\n")
        self.assertEqual(
            [], sites_from_source(bound_in_setup, "probe.py"),
            "negative control: the same name bound in setUp is a fixture the "
            "test built, and must stay unreported",
        )

    def test_a_class_body_repo_path_is_not_a_fixture_root(self):
        """The measured side is not always an `ast.Name` either, and the
        `self.<attr>`-is-a-fixture rule is the reason.

        `FIXTURE = FIXTURES_DIR / "..."` in a class body is a checked-in file,
        so a value measured through `self.FIXTURE` ages with the repository
        exactly as one measured through a module-level constant does. Treating
        every `self.<attr>` as scratch was the second half of the
        `ParentStateDiscriminationTest` drop. The same `repo` fixpoint that
        classifies module-level names decides it, rather than a second rule.

        Negative control: the identical attribute name bound in `setUp` from a
        temporary directory IS scratch and must stay unreported -- otherwise
        the exception would have swallowed the rule it is an exception to."""
        # Constructed input, so not a pin; carried in PENDING (T4).
        repo_path_in_class_body = (
            "import tempfile\n"
            "from pathlib import Path\n"
            "FIXTURES_DIR = Path(__file__).resolve().parent / 'fixtures'\n"
            "class T:\n"
            "    FIXTURE = FIXTURES_DIR / 'sample.txt'\n"
            "    def test_lines(self):\n"
            "        self.assertEqual(7, len(self.FIXTURE.read_text().split()))\n"
        )
        self.assertEqual(
            [("probe.py", "T", "test_lines")],
            [s.method_key() for s in sites_from_source(repo_path_in_class_body,
                                                     "probe.py")],
            "a class-body path into the repository is not scratch; treating "
            "every self.<attr> as a fixture drops the pin measured through it",
        )

        scratch_in_setup = repo_path_in_class_body.replace(
            "    FIXTURE = FIXTURES_DIR / 'sample.txt'\n",
            "    def setUp(self):\n"
            "        self.FIXTURE = Path(tempfile.mkdtemp()) / 'sample.txt'\n")
        self.assertEqual(
            [], sites_from_source(scratch_in_setup, "probe.py"),
            "negative control: the same attribute built in setUp is scratch, "
            "and must stay unreported",
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
        self.assertEqual([], sites_from_source(blind, "probe.py"))

        seeing = blind.replace(
            "        self.assertEqual(expected(), len(names))\n",
            "        self.assertEqual(10, len(names))\n")
        self.assertEqual(
            [("probe.py", "T", "test_budget")],
            [s.method_key() for s in sites_from_source(seeing, "probe.py")],
            "positive control: the same 10, inlined, must be reported",
        )

    def test_a_declared_side_computed_from_a_register_is_not_reached(self):
        """Gap 8, with the two positive controls its clause claims.

        A declared side that is COMPUTED -- here a set comprehension over a
        declared register -- is neither a literal nor an `ast.Name` nor a
        class-body attribute, so `stores_a_value` never fires and the site is
        invisible even though it stores its value in `TABLE`.

        This module's own `test_the_form_table_is_the_measured_behaviour` is a
        live instance: it carries a `# pin:` marker and is absent from the
        candidate set. That is why the gap is stated rather than closed --
        writing the ten expected results out as a literal would put the same
        register in the file twice, and two copies cannot check each other.

        Both controls change ONLY the declared side, so a scanner that simply
        reports nothing here cannot pass.
        """
        head = (
            "from pathlib import Path\n"
            "from pin_registry import assert_set_matches\n"
            "REPO = Path(__file__).resolve().parents[2]\n"
            "TABLE = (('a.md', True), ('b.md', False))\n"
            "class T:\n"
            "    def test_names(self):\n"
            "        got = {(n, bool(REPO.glob(n))) for n, _ in TABLE}\n"
        )
        computed = "        assert_set_matches(self, {(n, v) for n, v in TABLE}, got, 's')\n"
        self.assertEqual([], sites_from_source(head + computed, "probe.py"))

        by_name = "        assert_set_matches(self, TABLE, got, 's')\n"
        self.assertEqual(
            [("probe.py", "T", "test_names")],
            [s.method_key() for s in sites_from_source(head + by_name, "probe.py")],
            "positive control 1: the same register as a bare NAME is reported",
        )

        inline = "        assert_set_matches(self, {('a.md', True)}, got, 's')\n"
        self.assertEqual(
            [("probe.py", "T", "test_names")],
            [s.method_key() for s in sites_from_source(head + inline, "probe.py")],
            "positive control 2: the same value inlined as a literal is reported",
        )

    def test_the_real_deeper_pin_is_absent_from_the_candidate_set(self):
        """The constructed instance above only shows the scanner CAN be blind
        this way. This shows it IS blind to the real one: the skip-budget
        module is a candidate only through its registration-set assertions
        (:208, :217), never through the count assertion at :193."""
        budget = [s for s in all_sites()
                  if s.rel == "test_platform_conditional_skip_budget.py"]
        self.assertEqual(  # pin: set skip-budget-blind-spot
            ["test_no_unregistered_skip_decorator_file_exists"],
            sorted({s.method_name for s in budget}),
            "the skip-budget module's reported methods changed; if "
            "test_skip_count_matches_the_pinned_per_source_budget now appears, "
            "gap 5 has been closed and this module's boundary clause is stale",
        )


# ---------------------------------------------------------------------------
# The origin-tracking control series
# ---------------------------------------------------------------------------
# One measured collection, ten ways of carrying it to the assertion. The point
# of the series is NOT "loops are missing" -- it is that the origin tracking in
# `_taint`/`_local_sources` is FORM-DEPENDENT, so the boundary clause cannot be
# stated as a list of shapes the pattern misses. See this module's docstring,
# "The origin tracking is itself form-dependent".
#
# Every body below measures the SAME repository-derived `items`. A form that is
# not reached is a finding recorded here, not a form removed from the series:
# the series is only worth its lines if it also carries the shapes that fail.

ORIGIN_TRACKING_PROBE_HEAD = (
    "import collections\n"
    "import functools\n"
    "from pathlib import Path\n"
    "REPO = Path(__file__).resolve().parents[2]\n"
    "def collect():\n"
    "    return [p.name for p in REPO.glob('*.md')]\n"
    "def scratch():\n"
    "    return ['a', 'b']\n"
    "class T:\n"
    "    def test_x(self):\n"
    "        items = [p.name for p in REPO.glob('*.md')]\n"
)

# The head above, with the ONLY difference that `items` is built by a fixture
# helper instead of from the repository. Every form the series reports as
# reached must go silent under ITS OWN control, or it was reached for a reason
# that has nothing to do with the measurement.
ORIGIN_TRACKING_FIXTURE_HEAD = ORIGIN_TRACKING_PROBE_HEAD.replace(
    "        items = [p.name for p in REPO.glob('*.md')]\n",
    "        items = self.scratch_names()\n")

# (name, reached, body, control_body). `reached` is measured, never intended.
#
# `control_body` is the SAME form with this form's own repository origin taken
# out, and it is per-form rather than one global head swap because the swap
# must actually remove the cause. Writing it as a head swap alone let
# `helper-function-return` pass a control that never touched it: that form
# never reads `items`, it reads `collect()`, so rebuilding `items` as a fixture
# left its cause fully intact. A control that does not grip reports "passed"
# (WI-0133 T2b).
ORIGIN_TRACKING_FORMS = (
    # --- the three forms that opened WI-0133 T2b -------------------------
    ("direct-len", True,
     "        self.assertEqual(7, len(items))\n", None),
    ("dict-comprehension", True,
     "        tally = {i: 1 for i in items}\n"
     "        self.assertEqual({'a': 1}, tally)\n", None),
    # The anchor case's own shape: origin survived the comprehension and was
    # lost here, because the assignment target is a Subscript and the tracker
    # only bound `ast.Name` targets.
    ("loop-subscript-assign", True,
     "        tally = {}\n"
     "        for i in items:\n"
     "            tally[i] = tally.get(i, 0) + 1\n"
     "        self.assertEqual({'a': 1}, tally)\n", None),
    # --- forms added open-endedly, outcome unknown when written ---------
    ("loop-subscript-augassign", True,
     "        tally = {}\n"
     "        for i in items:\n"
     "            tally.setdefault(i, 0)\n"
     "            tally[i] += 1\n"
     "        self.assertEqual({'a': 1}, tally)\n", None),
    ("stdlib-call-counter", True,
     "        tally = collections.Counter(items)\n"
     "        self.assertEqual({'a': 1}, tally)\n", None),
    ("stdlib-call-reduce", True,
     "        total = functools.reduce(lambda a, b: a + len(b), items, 0)\n"
     "        self.assertEqual(7, total)\n", None),
    # Origin over a FUNCTION boundary. Holds, but not through `_local_sources`:
    # `collect` reaches `REPO`, so the module-level fixpoint puts the FUNCTION
    # NAME itself in `repo`. Gap 5 of the boundary clause is the same boundary
    # crossed the other way -- a literal inside the helper stays invisible.
    ("helper-function-return", True,
     "        got = collect()\n"
     "        self.assertEqual(7, len(got))\n",
     # Its own control: the helper stops reading the repository. Swapping
     # `items` would leave this form untouched.
     "        got = scratch()\n"
     "        self.assertEqual(7, len(got))\n"),
    # --- forms added open-endedly that did NOT hold ---------------------
    # Accumulation by METHOD CALL. `out.append(i)` is an `ast.Expr`, not an
    # assignment, so no target binds `out` to the loop it sits in and the
    # origin is lost. Reported to the decision-maker rather than repaired in
    # the same pass as the subscript form (WI-0133 T2b, PO: report, do not
    # widen the boundary unasked).
    ("loop-list-append", False,
     "        out = []\n"
     "        for i in items:\n"
     "            out.append(i)\n"
     "        self.assertEqual(7, len(out))\n", None),
    ("loop-set-add", False,
     "        seen = set()\n"
     "        for i in items:\n"
     "            seen.add(i)\n"
     "        self.assertEqual({'a'}, seen)\n", None),
    ("loop-dict-update", False,
     "        tally = {}\n"
     "        for i in items:\n"
     "            tally.update({i: 1})\n"
     "        self.assertEqual({'a': 1}, tally)\n", None),
)


class OriginTrackingIsFormDependentTest(unittest.TestCase):
    """The evidence behind the boundary clause's form-dependence sentence.

    A clause that only names shapes is an enumeration and ages into a lie the
    moment someone writes an eleventh form. This series makes the clause a
    check: it measures each form, and the three that do not hold stay in it as
    recorded findings rather than being quietly dropped.
    """

    def test_the_form_table_is_the_measured_behaviour(self):
        measured = {
            (name, bool(sites_from_source(
                ORIGIN_TRACKING_PROBE_HEAD + body, "probe.py")))
            for name, _, body, _ in ORIGIN_TRACKING_FORMS
        }
        assert_set_matches(  # pin: set origin-tracking-form-table
            self,
            {(name, reached) for name, reached, _, _ in ORIGIN_TRACKING_FORMS},
            measured,
            "the origin-tracking form table",
        )

    def test_every_reached_form_is_reached_because_of_the_measurement(self):
        """The discriminating control, and the reason the series is worth more
        than the fix. `reached` on its own does not say the tracker followed
        the measurement -- a form can be reported because some unrelated name
        in it happens to be repo-derived. Rebuilding `items` as a fixture
        removes the cause; anything still reported was never evidence.

        This control has already caught one: `from collections import Counter`
        makes `Counter` a non-allowlisted import and therefore repo-derived all
        by itself, so `Counter(items)` over a PURE LITERAL is reported. The
        series uses the `collections.Counter` attribute form, and the
        from-import defect is reported to the decision-maker unfixed.
        """
        wrongly_reached = sorted(
            name for name, reached, body, control_body in ORIGIN_TRACKING_FORMS
            if reached and sites_from_source(
                ORIGIN_TRACKING_FIXTURE_HEAD + (control_body or body),
                "probe.py"))
        self.assertEqual(  # pin: set origin-tracking-fixture-control
            [], wrongly_reached,
            "form(s) still reported when the measurement they carry is a "
            "fixture -- they are reported for some other reason: {}".format(
                wrongly_reached),
        )

    def test_the_anchor_case_carries_both_of_its_assertions(self):
        """The live instance the constructed series stands for.

        `ExternalToolExitStatusTest.test_classification_counts` asserts a total
        (`assertEqual(161, len(invocations))`) AND a per-disposition register
        over the same live scan. The register is accumulated with
        `by_disposition[inv.disposition] = ...` inside a `for`, and before
        WI-0133 T2b the inventory carried only the first of the two lines --
        the method was in the inventory, but the assertion that names WHICH
        dispositions moved was not.

        Since T2c the two are two SITES rather than one record with two lines,
        which is what makes the difference between them expressible; the shape
        divergence they carry is `DeclaredShapeDivergenceTest`'s subject.
        """
        rel = "test_external_tool_exit_status.py"
        found = [s for s in find_sites(TESTS_DIR / rel, rel)
                 if s.class_name == "ExternalToolExitStatusTest"
                 and s.method_name == "test_classification_counts"]
        self.assertEqual(
            2, len(found),
            "the anchor case must carry BOTH the total and the disposition "
            "register; it carries {}".format(sorted(s.subject for s in found)),
        )


if __name__ == "__main__":
    unittest.main()


# The methods whose pin-shaped assertions do NOT agree on their declared shape
# -- one asserts a scalar (a count, a bound), another a collection. These are
# the ones a single method-wide marker could not describe truthfully, because
# the group it named would have to be true of both.
#
# Measured, never typed. FOUR of them predate WI-0133 T2c and are the reason
# the tranche exists; the other three are this module's own new tests, which is
# self-application working rather than a coincidence.
DIVERGENT_SHAPE_METHODS = frozenset({
    ('test_absence_only_assertions.py', 'ScannedFilesCoverTheShippedScopeTest',
     'test_scanned_files_cover_the_shipped_scope'),
    ('test_bsd_gnu_portability.py', 'ClassificationCountsTest',
     'test_classification_counts'),
    ('test_external_tool_exit_status.py', 'ExternalToolExitStatusTest',
     'test_classification_counts'),
    ('test_pin_inventory.py', 'DeclaredShapeDivergenceTest',
     'test_a_same_shape_pair_is_not_a_divergence'),
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_the_anchor_method_is_two_sites_with_different_subjects'),
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_two_assertions_in_one_method_are_two_sites'),
    ('test_quality_scan_sast_patterns.py', 'PerExtensionRemovalRedProofTest',
     'test_removing_one_extension_silences_the_rule_for_that_extension'),
})

# The counter-half, and the reason T2c is not a rewrite of every
# multi-assertion method in the corpus (WI-0133 T2c, PO): these methods carry
# more than one pin-shaped assertion and every one of them declares the SAME
# shape. Nothing about them is untruthful, so nothing about them changed -- no
# marker moved, no assertion was split, and no foreign test module was written
# to.
#
# The set reconciles as 20 + 2 = 22. 21 methods carried this property at HEAD:
# 20 of them are below unchanged, and the 21st is this module's own
# `test_the_anchor_case_carries_both_of_its_assertions`, which dropped out
# because T2c rewrote its body from two assertions down to one. The remaining
# 2 are new tests of this tranche that happen to carry two same-shape
# assertions each -- self-application, exactly as in the sibling register
# above.
SAME_SHAPE_MULTI_SITE_METHODS = frozenset({
    ('test_absence_only_assertions.py', 'ParentStateDiscriminationTest',
     'test_the_six_named_methods_are_flagged_and_the_five_siblings_are_not'),
    ('test_agent_frontmatter.py', 'ProjectMemoryContractHistoricalRedProofTest',
     'test_removing_the_global_contract_does_not_clear_the_rule'),
    ('test_check_all.py', 'NoteColumnQuantityRedProofTest',
     'test_a_reintroduced_quantity_is_caught_in_both_number_forms'),
    ('test_ci_workflow.py', 'RealWorkflowStructureTest',
     'test_step_counts_per_job'),
    ('test_command_check.py', 'CommandPrerequisitesFilesRemovalRedProofTest',
     'test_removing_the_entry_drops_its_file_reason'),
    ('test_command_check.py', 'TemplateTreeExcludesGateArtifactsTest',
     'test_gate_p6_and_p7_are_absent_from_the_claim_set_for_a_different_reason'),
    ('test_conformance_run.py', 'CheckTableAlignmentTest',
     'test_all_seven_columns_are_five_entries_long'),
    ('test_handover_epilogue_bullet.py', 'EpilogueOpenBulletTest',
     'test_104_files_carry_the_disambiguated_wording'),
    ('test_heredoc_interpolation_scan.py', 'ClassificationCountsTest',
     'test_classification_counts'),
    ('test_instinct_registers_agree.py', 'ClassificationCountsTest',
     'test_classification_counts'),
    ('test_pin_inventory.py', 'MarkerBindsToOneAssertionTest',
     'test_a_marker_covers_only_the_assertion_it_sits_on'),
    ('test_pin_inventory.py', 'PatternLimitsTest',
     'test_a_declared_side_computed_from_a_register_is_not_reached'),
    ('test_pin_inventory.py', 'PinSiteIdentityTest',
     'test_the_identity_does_not_depend_on_the_interpreter'),
    ('test_platform_conditional_skip_budget.py', 'PlatformConditionalSkipBudgetTest',
     'test_no_unregistered_skip_decorator_file_exists'),
    ('test_quality_scan.py', 'CompletedHandlersBindingTest',
     'test_both_dicts_are_pinned_at_4_entries'),
    ('test_quality_scan.py', 'SkipDirsDefinitionsStayEqualTest',
     'test_both_skip_dirs_definitions_are_identical'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyPositionDependentTruncationTest',
     'test_breaking_the_last_rule_in_dict_order_loses_only_the_tail'),
    ('test_quality_scan_sast_patterns.py', 'MissingKeyPositionDependentTruncationTest',
     'test_control_finds_both_lines'),
    ('test_quality_scan_sast_patterns.py', 'PerRulePositiveFixtureTest',
     'test_each_rule_fires_on_its_own_fixture'),
    ('test_quality_scan_sast_patterns.py', 'TruncationCapTest',
     'test_more_than_50_matches_are_capped_plus_one_truncation_marker'),
    ('test_quality_scan_sast_patterns.py', 'TruncationCapTest',
     'test_the_50_real_findings_preceding_the_marker_are_unaffected'),
    ('workitems/test_youtrack.py', 'YouTrackCreateRollbackTest',
     'test_create_does_not_delete_when_initial_state_is_accepted'),
})

# Markers that name no pin-shaped assertion at all. LEGAL, and the register is
# here so the population is visible rather than merely permitted: a marker must
# be allowed on a pin `find_sites` cannot see (boundary clause gap 8), and both
# entries below are exactly that. Nothing enforces marker-implies-site and
# nothing should -- but an unbound marker is also what a MISPLACED marker looks
# like from here, so the two have to be told apart by a person, once, and
# recorded.
UNBOUND_MARKERS = frozenset({
    ('test_pin_inventory.py', 'set', 'fixture-corpus-exclusion'),
    ('test_pin_inventory.py', 'set', 'origin-tracking-form-table'),
})


class PinSiteIdentityTest(unittest.TestCase):
    """The unit of the inventory is one ASSERTION, and its identity carries no
    line number.

    Both halves matter and they pull against each other, which is why they are
    tested together. Making the unit finer is easy with a line number and
    useless: `test_external_tool_exit_status.py:1173-1178` records the same
    change measured both ways, 7 additions / 4 removals line-bearing against
    3 / 0 line-free. `subject_of` is the alternative that keeps the finer unit
    without buying the churn back.
    """

    TWO_SUBJECTS = (
        "from pathlib import Path\n"
        "REPO = Path(__file__).resolve().parents[2]\n"
        "class T:\n"
        "    def test_two(self):\n"
        "        names = sorted(p.name for p in REPO.glob('*.md'))\n"
        "        self.assertEqual(7, len(names))\n"
        "        self.assertEqual(['a.md'], names)\n"
    )

    def test_two_assertions_in_one_method_are_two_sites(self):
        """Constructed input, so not a pin; carried in PENDING (T4)."""
        sites = sites_from_source(self.TWO_SUBJECTS, "probe.py")
        self.assertEqual(2, len(sites))
        assert_set_matches(
            self,
            {("probe.py", "T", "test_two", "len+names:call"),
             ("probe.py", "T", "test_two", "names:name")},
            {s.key() for s in sites},
            "the two sites of one method",
        )

    def test_an_inserted_line_does_not_move_any_identity(self):
        """The property a line number cannot have. An ORDINAL within the
        method would pass a weaker version of this test -- inserting ABOVE the
        method leaves ordinals alone -- and fail the sibling below, which
        inserts a whole assertion BETWEEN the two sites."""
        before = {s.key() for s in sites_from_source(self.TWO_SUBJECTS, "probe.py")}
        shifted = self.TWO_SUBJECTS.replace(
            "class T:\n", "# an unrelated comment\nclass T:\n")
        after = {s.key() for s in sites_from_source(shifted, "probe.py")}
        assert_set_matches(self, before, after, "the site identities")

    def test_an_assertion_inserted_between_two_sites_moves_neither(self):
        """The case that separates this identity from an ordinal. A third
        pin-shaped assertion wedged between the two existing ones is one
        ADDITION and zero removals; with an ordinal it would be one addition
        and one removal, which is the churn the line-free rule exists to
        avoid."""
        before = {s.key() for s in sites_from_source(self.TWO_SUBJECTS, "probe.py")}
        wedged = self.TWO_SUBJECTS.replace(
            "        self.assertEqual(['a.md'], names)\n",
            "        self.assertEqual(3, len(set(names)))\n"
            "        self.assertEqual(['a.md'], names)\n")
        after = {s.key() for s in sites_from_source(wedged, "probe.py")}
        self.assertEqual(set(), before - after, "an insertion removed a site")
        self.assertEqual(1, len(after - before))

    def test_every_site_in_the_corpus_has_a_unique_identity(self):
        """Uniqueness is what makes the identity usable as a key at all. It is
        not free: the bare set of names read by the measured expression
        collided five times over this corpus (`len(ns['COMPLETED'])` against
        `len(ns['HANDLERS'])`, `len(found)` against
        `len(found[0].assert_linenos)`, ...), which is why `subject_of` also
        carries attribute names and constant subscript keys."""
        keys = [s.key() for s in all_sites()]
        self.assertEqual(
            len(keys), len(set(keys)),
            "two pin sites share one identity; PENDING cannot name them "
            "apart: {}".format(sorted(k for k in keys if keys.count(k) > 1)),
        )

    def test_the_identity_does_not_depend_on_the_interpreter(self):
        """`ast.unparse` was the obvious way to render the subject and is the
        wrong one: its output is interpreter-dependent. 3.9 writes a
        comprehension's tuple target parenthesised and 3.12+ does not, which
        over this corpus differs for eleven operands -- one of them a live pin
        site (test_bsd_gnu_portability.py:1923). CI is pinned to 3.11 and the
        machine that writes PENDING is not, so an interpreter-dependent
        identity goes stale on one and not on the other.

        Tested on the shape that actually differs, rather than by asserting a
        version number: whatever this interpreter does with the target, the
        subject must be the same."""
        source = (
            "from pathlib import Path\n"
            "REPO = Path(__file__).resolve().parents[2]\n"
            "PAIRS = (('a.md', 1),)\n"
            "class T:\n"
            "    def test_pairs(self):\n"
            "        found = {(n, len(list(REPO.glob(n)))) for n, _v in PAIRS}\n"
            "        self.assertEqual({('a.md', 1)}, found)\n"
        )
        sites = sites_from_source(source, "probe.py")
        self.assertEqual(1, len(sites))
        self.assertEqual("found:name", sites[0].subject)

    def test_the_subject_is_a_token_set_and_not_a_rendering(self):
        """The two ways `subject_of` is deliberately not injective, as a check
        rather than as a sentence in its docstring (code review, T2c).

        Both are latent: neither has an instance in the corpus, and neither can
        misbind a marker silently -- the failure mode of both is two sites
        sharing one key, which
        `test_every_site_in_the_corpus_has_a_unique_identity` reports over the
        whole corpus. Pinned here so that a later sharpening of the renderer is
        a decision someone makes, not a side effect they discover.

        Each case carries a control that keeps the property being given up, so
        a renderer that collapsed EVERYTHING would fail the second half.
        """
        def subject(expression):
            return subject_of(ast.parse(expression, mode="eval").body)

        # (a) a token set carries no order.
        self.assertEqual(subject("f(a, b)"), subject("f(b, a)"))
        self.assertEqual(subject("a - b"), subject("b - a"))
        self.assertNotEqual(
            subject("f(a, b)"), subject("f(a, c)"),
            "control: a different NAME must still be a different subject")

        # (b) the bound-name subtraction is scope-blind: `x` is subtracted
        #     everywhere because it is a comprehension target somewhere.
        self.assertEqual("sum+y:binop", subject("sum(x for x in y) + x"))
        self.assertEqual(
            "sum+x+y:binop", subject("sum(z for z in y) + x"),
            "control: the free `x` is kept when it does not collide with the "
            "comprehension target -- the loss above is the collision, not a "
            "blanket drop of free names")

    def test_the_anchor_method_is_two_sites_with_different_subjects(self):
        """The live case the whole tranche is for.

        `ExternalToolExitStatusTest.test_classification_counts` pins a COUNT
        (`assertEqual(161, len(invocations))`) on one line and a MEMBERSHIP
        register (`assertEqual({...}, by_disposition)`) on the next. Before
        T2c they were one record; a marker on that record would have had to
        name one group for both, and T3/T4 read that group.
        """
        rel = "test_external_tool_exit_status.py"
        found = [s for s in find_sites(TESTS_DIR / rel, rel)
                 if s.class_name == "ExternalToolExitStatusTest"
                 and s.method_name == "test_classification_counts"]
        self.assertEqual(2, len(found))
        self.assertEqual({"scalar", "collection"},
                         {s.declared_shape for s in found})
        self.assertEqual(2, len({s.subject for s in found}))


class MarkerBindsToOneAssertionTest(unittest.TestCase):
    """A marker names the assertion it stands over -- not the method.

    The predecessor rule asked whether any marker fell inside the METHOD's
    span. One marker therefore vouched for every pin-shaped assertion in that
    method, including one of a different declared shape, and the group it named
    became a false statement at the site where T3 and T4 read it.
    """

    def test_a_marker_covers_only_the_assertion_it_sits_on(self):
        """The mechanism, on a constructed method with two subjects.

        Constructed input, so not a pin; carried in PENDING (T4)."""
        source = PinSiteIdentityTest.TWO_SUBJECTS.replace(
            "        self.assertEqual(7, len(names))\n",
            "        self.assertEqual(7, len(names))  # " + "pin: floor probe-count\n")
        sites = sites_from_source(source, "probe.py")
        bound, unbound = bind_markers(sites, _markers_in_source(source))
        self.assertEqual([], unbound)
        self.assertEqual([("probe.py", "T", "test_two", "len+names:call")],
                         sorted(bound))
        self.assertEqual(
            [("probe.py", "T", "test_two", "names:name")],
            sorted(s.key() for s in sites if s.key() not in bound),
            "the sibling assertion must stay uncovered -- that is the whole "
            "difference between T2c and its predecessor",
        )

    def test_a_marker_on_the_line_above_binds_to_the_assertion_below(self):
        """The second accepted placement. Every one of the 22 markers in the
        corpus today is a trailing comment on its assertion's own first line,
        so without this test the "line directly above" branch would be code
        nothing exercises."""
        source = PinSiteIdentityTest.TWO_SUBJECTS.replace(
            "        self.assertEqual(['a.md'], names)\n",
            "        # " + "pin: set probe-names\n"
            "        self.assertEqual(['a.md'], names)\n")
        sites = sites_from_source(source, "probe.py")
        bound, unbound = bind_markers(sites, _markers_in_source(source))
        self.assertEqual([], unbound)
        self.assertEqual([("probe.py", "T", "test_two", "names:name")],
                         sorted(bound))

    def test_a_marker_naming_no_assertion_is_reported_and_not_dropped(self):
        """A marker on a site `find_sites` cannot see is legal (gap 8), so
        `bind_markers` returns it instead of failing. Silently discarding it
        would also silently discard a misplaced one."""
        source = ("class T:\n"
                  "    def test_nothing(self):\n"
                  "        pass  # " + "pin: set stray-id\n")
        bound, unbound = bind_markers(sites_from_source(source, "probe.py"),
                                      _markers_in_source(source))
        self.assertEqual({}, bound)
        self.assertEqual([("probe.py", 3, "set", "stray-id")], unbound)

    def test_the_unbound_markers_in_the_corpus_are_the_registered_ones(self):
        """The live half. Both entries sit on gap-8 sites -- a declared side
        computed from a register, which carries a marker and is not a
        candidate. Registered rather than merely tolerated, because an unbound
        marker and a MISPLACED marker look identical from here."""
        _bound, unbound = bind_markers(all_sites(), all_markers())
        assert_set_matches(  # pin: set unbound-markers
            self, UNBOUND_MARKERS,
            {(rel, group, pin_id) for rel, _lineno, group, pin_id in unbound},
            "the set of `# pin:` markers naming no pin-shaped assertion",
        )


class DeclaredShapeDivergenceTest(unittest.TestCase):
    """"More than one subject" and "more than one subject of a different kind"
    are two different findings, and only the second one is a problem.

    The distinction is the reason T2c is not a rewrite of the corpus. 22
    methods carry several pin-shaped assertions that all declare the same
    shape; splitting them would be accounting work with no gain in what the
    inventory can say, and the PO ruled it out. The five that DO diverge are
    the ones a single marker could not describe truthfully.

    `declared_shape` is deliberately coarser than a group: scalar against
    collection. It is the one property the four `PIN_GROUPS` disagree about
    that can be derived without doing the classification -- a `set` pin's
    declared side IS the collection, a count or a floor is a scalar -- and
    guessing anything finer here would put the same kind of false statement in
    the mechanism that a wrong marker puts at a site.
    """

    def test_a_same_shape_pair_is_not_a_divergence(self):
        """The negative control. Without it a discriminator that simply
        reported every multi-assertion method would pass the positive half,
        and 22 methods would be dragged into a rewrite for nothing."""
        source = PinSiteIdentityTest.TWO_SUBJECTS.replace(
            "        self.assertEqual(7, len(names))\n",
            "        self.assertEqual(['b.md'], sorted(names))\n")
        sites = sites_from_source(source, "probe.py")
        self.assertEqual(2, len(sites), "the control needs two sites to be one")
        self.assertEqual([("probe.py", "T", "test_two")],
                         methods_with_multiple_sites(sites))
        self.assertEqual([], methods_with_divergent_declared_shapes(sites))

    def test_a_scalar_against_a_collection_is_a_divergence(self):
        """The positive control, on the same two-assertion shape."""
        sites = sites_from_source(PinSiteIdentityTest.TWO_SUBJECTS, "probe.py")
        self.assertEqual([("probe.py", "T", "test_two")],
                         methods_with_divergent_declared_shapes(sites))

    def test_the_divergent_methods_in_the_corpus_are_the_registered_ones(self):
        """The live half of the positive control."""
        assert_set_matches(  # pin: set divergent-shape-methods
            self, DIVERGENT_SHAPE_METHODS,
            set(methods_with_divergent_declared_shapes(all_sites())),
            "the methods whose pin-shaped assertions disagree on their shape",
        )

    def test_the_same_shape_multi_site_methods_stay_silent(self):
        """The live half of the NEGATIVE control, and the one that would go
        red if the discriminator were ever widened to mere multiplicity: this
        set would collapse to empty and name all 22 as gone.

        It is also the record of what T2c did NOT touch. None of these methods
        gained, lost or moved a marker."""
        sites = all_sites()
        silent = (set(methods_with_multiple_sites(sites))
                  - set(methods_with_divergent_declared_shapes(sites)))
        assert_set_matches(  # pin: set same-shape-multi-site-methods
            self, SAME_SHAPE_MULTI_SITE_METHODS, silent,
            "the multi-assertion methods that carry only one declared shape",
        )

    def test_every_marked_multi_site_method_carries_a_marker_per_assertion(self):
        """What the conversion actually moved, as a check rather than as a
        sentence in a report: nothing.

        Measured before the change and pinned after it. Every marker in this
        corpus is a trailing comment on its own assertion's first line, so the
        three multi-assertion methods that carry markers were already marked
        per assertion; the method-wide rule had never in fact been used to
        cover a second subject. Had even one been covered that way, its
        sibling would appear here and the tranche would have had to write a
        marker into a foreign test module."""
        sites = all_sites()
        bound, _unbound = bind_markers(sites, all_markers())
        marked_methods = {key[:3] for key in bound}
        half_marked = sorted(s.key() for s in sites
                             if s.method_key() in marked_methods
                             and s.key() not in bound)
        self.assertEqual(
            [], half_marked,
            "assertion(s) inside a method that carries a marker, but with no "
            "marker of their own. Under the pre-T2c rule these were covered "
            "by a sibling's marker:\n  {}".format(
                "\n  ".join(map(str, half_marked))),
        )
