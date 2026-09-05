r"""test_doc_counts_agree.py -- CCP-1152: living-document counts vs. the
repository they describe (ADR-0012, "Derived values are not stored").

## The dividing line this module enforces (settled 05.09.2026)

A PROTOCOL records a measurement as part of its own evidence and is never
rewritten retroactively -- `docs/adr/ADR-0010-conformance-runs-against-
consumers.md:24` and `docs/memory/project_test-runner.md:49` are examples,
and this module deliberately never reads either. A LIVING DOCUMENT claims a
present-tense fact about the repository ("the shipped suite has N tests",
"CCPR ships N agents") and must be derived, or it ages exactly the way
`README.md`'s "1458-test Python suite", `Manual/README.md`'s "1691-test
suite" and `Manual/SYSTEM_OVERVIEW.md`'s "14 agents" (contradicting its own
line 103's "15 agents" two paragraphs later) had already aged before this
module existed. A date next to a number does not make it a protocol --
CONTRIBUTING.md's own `-t .` paragraph carries a date AND is a living claim,
which is why it is IN this module's scope while the two ADR/memory
exemptions above are not.

## Same house shape as test_instinct_registers_agree.py, deliberately

Every `parse_*` function below takes TEXT, not a path -- the seam that lets
a future red-proof mutate a scratch copy under `$TMPDIR` instead of the
tracked file (`docs/memory/senior-developer/instinct-register-cross-
check.md` documents why this seam matters: it is what made this sibling
module's own red-proofs possible without ever touching a tracked file). A
thin `read_*` wrapper defaults to the real repository path; every
acceptance test below calls the wrapper with its default argument, so
production always measures the tracked docs.

## What this module intentionally does NOT guard

CONTRIBUTING.md's own `-t .` paragraph also quotes the WITHOUT-`-t .`
figures (module count, import-error count, skipped-test count) and a
multi-generation trajectory sentence. Those were refreshed by hand as part
of CCP-1152 (they had gone stale together with the `-t .` figure this
module DOES guard, and leaving them stale next to a freshly-corrected
number would have been worse than leaving the whole paragraph alone -- see
the CCP-1152 session report) but are not pinned here: the `-t .` figure
alone is what every OTHER doc's "N-test suite" claim also states and can be
cross-checked against, while the without-flag figures describe a second,
narrower scenario this module was not briefed to build a structural guard
for. `docs/CONSTITUTION.md`'s own "114-skill surface" (true value 116) is
excluded on purpose too -- explicitly named as a later, separate cleanup in
CCP-1152's own briefing.

## Red-proof (structural, not deletion -- G-107/G-109), run once during
## authoring against the TRACKED `README.md`, then restored

`README.md`'s own "116 slash commands" line is correct at the time this
module was written and is exactly the kind of claim `CommandCountAgreementTest`
below would need to catch if it ever drifted. Verified during authoring by
incrementing that one literal to "117" in the tracked file, in a single
uninterruptible script (mutate -> run -> restore, never `git stash`, never
two separate commands), confirming
`CommandCountAgreementTest.test_docs_agree_with_the_measured_command_count`
(and only that test in the whole module) goes red -- the failing dict diff
names exactly one changed key, `command_readme_structure` (116 -> 117),
every other key still 116, with the test's own custom message ("README.md
claims a command count that disagrees with the measured commands/*.md file
count (116), or one of the other doc locations quoting the same total
does") attached -- then restoring the byte-exact original (`sha256` compared
before/after inside the same script) and confirming `git diff --stat
README.md` reports nothing. The transcript is in this work item's session
report, not encoded here --
matching this module's sibling's own convention of reporting authoring-time
red-proofs rather than shipping a permanent mutation of a tracked file.
"""

import re
import sys
import unittest
from pathlib import Path

# sys.path.insert, deliberately, rather than `from .test_instinct_registers_agree
# import ...`: same idiom as test_pin_inventory.py:244-250's `pin_registry`
# import (and test_manual_lint.py:53's `read_enum` import) -- a relative
# import here would add THIS module to CONTRIBUTING.md's own tracked
# "modules that need -t ." count, which the -t . paragraph this module's
# own TestCountAgreementTest checks explicitly documents as costly to
# discover. This round's write boundary happens to include CONTRIBUTING.md
# already (see the docstring above), but the module is still written the
# same way its siblings are -- one relative-import site fewer to ever need
# auditing again is a fixed cost paid once, not a cost tied to this round.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_instinct_registers_agree import (  # noqa: E402
    read_index_entries,
    read_sampler_entries,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
MANUAL_README_PATH = REPO_ROOT / "Manual" / "README.md"
CONTRIBUTING_PATH = REPO_ROOT / "CONTRIBUTING.md"
CLAUDE_PATH = REPO_ROOT / "CLAUDE.md"
SYSTEM_OVERVIEW_PATH = REPO_ROOT / "Manual" / "SYSTEM_OVERVIEW.md"
SECTIONS_COMMANDS_PATH = REPO_ROOT / "Manual" / "SECTIONS_COMMANDS.md"
AGENTS_DIR = REPO_ROOT / "agents"
COMMANDS_DIR = REPO_ROOT / "commands"
TESTS_DIR = REPO_ROOT / "scripts" / "tests"

PHASE_COUNT = 9  # P0..P8


def _read(path):
    return path.read_text(encoding="utf-8")


def _collapse_ws(text):
    """Markdown prose wraps at ~80 columns; a claim quoted across a
    hand-wrapped line break (e.g. CONTRIBUTING.md's own bolded test-count
    sentence) still needs to match a single-line regex."""
    return re.sub(r"\s+", " ", text)


# ---------------------------------------------------------------------------
# Derived values -- measured from the repository, never typed
# ---------------------------------------------------------------------------

def measured_test_count():
    """The same measurement every "N-test suite" doc claim describes:
    `unittest`'s own loader under the `-t .` convention CONTRIBUTING.md
    documents, counted WITHOUT executing a single test (`countTestCases`
    never calls `run`) -- this module must not become one more test in the
    very count it measures by running the suite itself."""
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS_DIR), top_level_dir=str(REPO_ROOT))
    return suite.countTestCases(), len(loader.errors)


def measured_agent_count():
    return len(list(AGENTS_DIR.glob("*.md")))


def measured_command_count():
    return len(list(COMMANDS_DIR.glob("*.md")))


def measured_phase_command_breakdown():
    """Per-phase command counts, P0..P8. Every phase command file is named
    `p{N}-....md` -- no phase ever ships a bare `p{N}.md`, so this glob
    cannot double-count a lead command against its own sub-skills."""
    return [len(list(COMMANDS_DIR.glob(f"p{i}-*.md"))) for i in range(PHASE_COUNT)]


def measured_gate_command_count():
    return len(list(COMMANDS_DIR.glob("gate-*.md")))


# Editorial classification (ADR-0012's declared-value carve-out: "Where a
# value cannot be derived -- an editorial judgement... this ADR does not
# apply. Such a value is declared, and what is placed under test is
# DRIFT"). Which command belongs to "track + cross-cutting" vs. "continuous
# learning" is a naming judgement, not something a filename glob can derive
# on its own -- but `ClassificationCompletenessTest` below proves this
# declaration partitions the REAL file set exactly, so a renamed or
# newly-added command cannot silently fall through into "utility" (the
# residual bucket) without a test noticing.
TRACK_COMMAND_NAMES = frozenset({
    "track-decision", "constitution", "lean-frame", "lean-learn",
    "lean-promote", "cross-check",
})

LEARNING_COMMAND_NAMES = frozenset({"postmortem", "instinct"})


def _all_command_names():
    return {p.stem for p in COMMANDS_DIR.glob("*.md")}


def _phase_and_gate_command_names():
    names = set()
    for i in range(PHASE_COUNT):
        names.update(p.stem for p in COMMANDS_DIR.glob(f"p{i}-*.md"))
    names.update(p.stem for p in COMMANDS_DIR.glob("gate-*.md"))
    return names


def measured_utility_command_names():
    """Everything that is neither a phase command, a gate, a declared
    track/cross-cutting command, nor a declared learning command."""
    excluded = _phase_and_gate_command_names() | TRACK_COMMAND_NAMES | LEARNING_COMMAND_NAMES
    return _all_command_names() - excluded


# ---------------------------------------------------------------------------
# Claim extraction -- text-in, never path-in (the scratch-copy seam)
# ---------------------------------------------------------------------------

def parse_test_count_claims(readme_text, contributing_text):
    """CCP-1152 follow-up (PO decision, 05.09.2026): only TWO of the three
    former "N-test suite" claims remain typed numbers. Manual/README.md's own
    "the 2623-test suite" phrase is gone -- see `TestCountAgreementTest`'s
    docstring for why a third copy of the same number bought no reader
    benefit its cross-reference to CONTRIBUTING.md didn't already provide.
    README.md now states a FLOOR ("a Python suite of **2,600+ tests**"), not
    the exact count; CONTRIBUTING.md is unchanged, still the exact count.

    Keys are prefixed `test_count_*` -- `parse_agent_count_claims` and
    `parse_command_count_claims` below extract claims from some of the SAME
    files and would otherwise collide on plain names like "readme" or
    "manual_readme"; `ClaimExtractionShapeTest` merges every `parse_*`
    function's dict into one via `dict.update`, and a silent key collision
    there would let a `None` from one parser be overwritten by an unrelated
    parser's real value before the "nothing is unparsed" check ever runs."""
    claims = {}
    m = re.search(r"a Python suite of \*\*([\d,]+)\+ tests\*\*", readme_text)
    claims["test_count_readme_floor"] = int(m.group(1).replace(",", "")) if m else None
    flat = _collapse_ws(contributing_text)
    m = re.search(r"discovery collects \*\*(\d+) tests, (\d+) import errors\*\*", flat)
    claims["contributing_count"] = int(m.group(1)) if m else None
    claims["contributing_errors"] = int(m.group(2)) if m else None
    return claims


def parse_agent_count_claims(readme_text, system_overview_text):
    """Keys prefixed `agent_*` -- see `parse_test_count_claims`'s docstring
    for why (a plain "readme_structure" here would collide with
    `parse_command_count_claims`'s own README-structure-line claim)."""
    claims = {}
    m = re.search(
        r"agents/\s*# 13 domain agents \+ project-guide \+ wingman = (\d+)",
        readme_text,
    )
    claims["agent_readme_structure"] = int(m.group(1)) if m else None
    m = re.search(r"\+------\+ \+------\+ \+------\+\s+(\d+) agents", system_overview_text)
    claims["ascii_box"] = int(m.group(1)) if m else None
    m = re.search(r'Agents\["(\d+) agents', system_overview_text)
    claims["mermaid"] = int(m.group(1)) if m else None
    m = re.search(
        r"13 domain subagents \+ `project-guide` \+ `wingman` = (\d+) agents",
        system_overview_text,
    )
    claims["summary_line"] = int(m.group(1)) if m else None
    return claims


def parse_command_count_claims(
    readme_text, manual_readme_text, system_overview_text, sections_commands_text,
):
    """Keys prefixed `command_*` -- see `parse_test_count_claims`'s
    docstring for why (both "readme_structure" and "manual_readme" here
    would otherwise collide with a sibling `parse_*` function's own keys)."""
    claims = {}
    m = re.search(
        r"commands/\s*# (\d+) slash commands \(P0-P8 \+ Lean-Track \+ cross-cutting\)",
        readme_text,
    )
    claims["command_readme_structure"] = int(m.group(1)) if m else None
    m = re.search(r"All (\d+) commands, grouped by section", readme_text)
    claims["readme_table"] = int(m.group(1)) if m else None
    m = re.search(r"Browse all (\d+) commands grouped by section", manual_readme_text)
    claims["command_manual_readme"] = int(m.group(1)) if m else None
    flat_overview = _collapse_ws(system_overview_text)
    m = re.search(r"\*\*Total: (\d+) commands\*\*", flat_overview)
    claims["system_overview_total"] = int(m.group(1)) if m else None
    flat_sections = _collapse_ws(sections_commands_text)
    m = re.search(r"\*\*(\d+) Commands\*\* – full granularity", flat_sections)
    claims["sections_commands_top"] = int(m.group(1)) if m else None
    m = re.search(r"## Summary: (\d+) Commands", flat_sections)
    claims["sections_commands_summary_heading"] = int(m.group(1)) if m else None
    m = re.search(r"\*\*Total\*\* \| \*\*(\d+)\*\*", flat_sections)
    claims["sections_commands_summary_table"] = int(m.group(1)) if m else None
    return claims


def parse_command_breakdown_claims(system_overview_text, sections_commands_text):
    claims = {}
    flat_overview = _collapse_ws(system_overview_text)
    m = re.search(
        r"\*\*(\d+) phase commands\*\* \(P0: (\d+), P1: (\d+), P2: (\d+), "
        r"P3: (\d+), P4: (\d+), P5: (\d+), P6: (\d+), P7: (\d+), P8: (\d+)\)",
        flat_overview,
    )
    if m:
        claims["overview_phase_total"] = int(m.group(1))
        claims["overview_phase_breakdown"] = [int(m.group(i)) for i in range(2, 11)]
    else:
        claims["overview_phase_total"] = None
        claims["overview_phase_breakdown"] = None
    m = re.search(r"\*\*(\d+) gates\*\*", flat_overview)
    claims["overview_gates"] = int(m.group(1)) if m else None
    m = re.search(r"\*\*(\d+) learning commands\*\*", flat_overview)
    claims["overview_learning"] = int(m.group(1)) if m else None
    m = re.search(r"\*\*(\d+) utility commands\*\*", flat_overview)
    claims["overview_utility"] = int(m.group(1)) if m else None
    m = re.search(r"\*\*(\d+) track \+ cross-cutting commands\*\*", flat_overview)
    claims["overview_track"] = int(m.group(1)) if m else None

    flat_sections = _collapse_ws(sections_commands_text)
    m = re.search(r"Phase Commands \(P0–P8, (\d+) commands\)", flat_sections)
    claims["sections_phase_header"] = int(m.group(1)) if m else None
    m = re.search(r"Gates \((\d+) commands\)", flat_sections)
    claims["sections_gates_header"] = int(m.group(1)) if m else None
    m = re.search(r"Continuous Learning \((\d+) commands\)", flat_sections)
    claims["sections_learning_header"] = int(m.group(1)) if m else None
    m = re.search(r"Utility \((\d+) commands\)", flat_sections)
    claims["sections_utility_header"] = int(m.group(1)) if m else None
    m = re.search(r"Track-Skills \(Cross-Cutting, (\d+) commands\)", flat_sections)
    claims["sections_track_header"] = int(m.group(1)) if m else None
    m = re.search(r"\*\*Subtotal — phase commands\*\* \| \*\*(\d+)\*\*", flat_sections)
    claims["sections_phase_subtotal"] = int(m.group(1)) if m else None
    m = re.search(r"Gates \(main \+ sub-gates\) \| (\d+)", flat_sections)
    claims["sections_gates_row"] = int(m.group(1)) if m else None
    m = re.search(r"\| Continuous Learning \| (\d+) \|", flat_sections)
    claims["sections_learning_row"] = int(m.group(1)) if m else None
    m = re.search(r"\| Utility \| (\d+) \|", flat_sections)
    claims["sections_utility_row"] = int(m.group(1)) if m else None
    m = re.search(r"Track \+ Cross-Cutting \([^)]*\) \| (\d+) \|", flat_sections)
    claims["sections_track_row"] = int(m.group(1)) if m else None
    return claims


def parse_instinct_count_claims(readme_text, starter_instincts_text, claude_text):
    """CCP-1152 Auftrag 2 added `claude_split_layout_total`: `CLAUDE.md`'s own
    "carry **N instincts**" sentence drifted to 45 against a measured 46 in
    the very commit that built this module's own `InstinctCountAgreementTest`
    -- the ADR-0012 enforcement pass introduced fresh drift in the doc every
    session loads at start. Pinned here rather than left to prose review."""
    claims = {}
    m = re.search(
        r"compact 13-instinct sampler \(split layout ships the full (\d+)\)",
        readme_text,
    )
    claims["readme_index_total"] = int(m.group(1)) if m else None
    flat = _collapse_ws(starter_instincts_text)
    m = re.search(r"COMPLETE shipped snapshot \((\d+) instincts\)", flat)
    claims["frontmatter_index_total"] = int(m.group(1)) if m else None
    m = re.search(r"\*\*complete\*\* CCPR instinct snapshot holds \*\*(\d+) instincts\*\*", flat)
    claims["body_index_total"] = int(m.group(1)) if m else None
    m = re.search(r"ships the full (\d+)-instinct set", flat)
    claims["split_layout_total"] = int(m.group(1)) if m else None
    m = re.search(r"carry \*\*(\d+) instincts\*\*", claude_text)
    claims["claude_split_layout_total"] = int(m.group(1)) if m else None
    return claims


# ---------------------------------------------------------------------------
# Acceptance tests -- always read the tracked files (default arguments)
# ---------------------------------------------------------------------------

class TestCountAgreementTest(unittest.TestCase):
    """CCP-1152 follow-up (PO decision, 05.09.2026): the exact test-suite
    size used to be typed identically into three docs, and that institutes a
    tax on every test-adding commit -- this very work item's own commits
    moved the number 2606 -> 2623, three files touched for one addition.
    Now only CONTRIBUTING.md states the exact count (unchanged: it is the
    one doc that already argues its correlated figures should be re-measured
    together, not adjusted one at a time). README.md states a FLOOR instead
    -- an order of magnitude that keeps the adopter signal but only breaks
    if the suite SHRINKS, which is exactly when someone should be woken up.
    Manual/README.md carries no number at all any more: it already
    cross-references CONTRIBUTING.md for the invocation, and a third typed
    copy of the same fact bought nothing a reader couldn't get from that
    link. All three checks below still require a clean `-t .` discovery --
    an import error would make every doc claim meaningless."""

    def test_measured_count_has_zero_import_errors(self):
        _, errors = measured_test_count()
        self.assertEqual(
            0, errors,
            "`-t .` discovery has import errors -- the doc claims this "
            "module checks assume a clean discovery",
        )

    def test_contributing_agrees_with_the_measured_test_count(self):
        count, _ = measured_test_count()
        claims = parse_test_count_claims(_read(README_PATH), _read(CONTRIBUTING_PATH))
        expected = {"contributing_count": count, "contributing_errors": 0}
        actual = {
            "contributing_count": claims["contributing_count"],
            "contributing_errors": claims["contributing_errors"],
        }
        self.assertEqual(
            expected, actual,
            f"CONTRIBUTING.md quotes a test-suite size that disagrees with "
            f"the measured unittest-discover count ({count})",
        )

    def test_readme_floor_still_holds(self):
        """A FLOOR, not an equality (PIN_GROUPS["floor"] in
        scripts/tests/pin_registry.py names this exact shape): it protects
        against one thing only -- the measured count dropping below what
        README.md still claims, i.e. the suite shrinking or the scanner
        going blind -- and stays silent while the suite grows. The floor
        value is not duplicated as a literal here: it lives in README.md's
        own prose and is compared against dynamically, so raising it is a
        one-line README edit, made by hand, at leisure -- never typed here
        under the pressure of a red run. Both sides are DERIVED (measured
        count vs. parsed doc claim), which is also why neither is a literal
        this corpus's `# pin:` marker machinery would flag as a candidate --
        that machinery targets a HARD-CODED number drifting out of sync with
        its source, and there is no hard-coded number at this site to drift."""
        count, _ = measured_test_count()
        claims = parse_test_count_claims(_read(README_PATH), _read(CONTRIBUTING_PATH))
        floor = claims["test_count_readme_floor"]
        self.assertGreaterEqual(
            count, floor,
            f"the measured unittest-discover test count ({count}) fell "
            f"below the floor README.md states (\"{floor}+ tests\") -- "
            f"either the suite shrank (investigate) or the floor is stale "
            f"and due a deliberate raise in README.md",
        )


class AgentCountAgreementTest(unittest.TestCase):
    def test_docs_agree_with_the_measured_agent_count(self):
        count = measured_agent_count()
        claims = parse_agent_count_claims(_read(README_PATH), _read(SYSTEM_OVERVIEW_PATH))
        expected = {
            "agent_readme_structure": count,
            "ascii_box": count,
            "mermaid": count,
            "summary_line": count,
        }
        self.assertEqual(
            expected, claims,
            f"README.md and/or Manual/SYSTEM_OVERVIEW.md quote an agent "
            f"count that disagrees with the measured agents/*.md file "
            f"count ({count})",
        )


class CommandCountAgreementTest(unittest.TestCase):
    def test_docs_agree_with_the_measured_command_count(self):
        count = measured_command_count()
        claims = parse_command_count_claims(
            _read(README_PATH), _read(MANUAL_README_PATH),
            _read(SYSTEM_OVERVIEW_PATH), _read(SECTIONS_COMMANDS_PATH),
        )
        expected = {
            "command_readme_structure": count,
            "readme_table": count,
            "command_manual_readme": count,
            "system_overview_total": count,
            "sections_commands_top": count,
            "sections_commands_summary_heading": count,
            "sections_commands_summary_table": count,
        }
        self.assertEqual(
            expected, claims,
            f"README.md claims a command count that disagrees with the "
            f"measured commands/*.md file count ({count}), or one of the "
            f"other doc locations quoting the same total does",
        )


class CommandBreakdownAgreementTest(unittest.TestCase):
    """The per-category breakdown (phase/gates/learning/utility/track) that
    Manual/SYSTEM_OVERVIEW.md and Manual/SECTIONS_COMMANDS.md both state in
    full -- two independent doc locations for the same derived facts, both
    checked against the same measured values so neither can drift alone."""

    def test_docs_agree_with_the_measured_breakdown(self):
        phase_breakdown = measured_phase_command_breakdown()
        phase_total = sum(phase_breakdown)
        gates = measured_gate_command_count()
        learning = len(LEARNING_COMMAND_NAMES)
        utility = len(measured_utility_command_names())
        track = len(TRACK_COMMAND_NAMES)

        claims = parse_command_breakdown_claims(
            _read(SYSTEM_OVERVIEW_PATH), _read(SECTIONS_COMMANDS_PATH),
        )
        expected = {
            "overview_phase_total": phase_total,
            "overview_phase_breakdown": phase_breakdown,
            "overview_gates": gates,
            "overview_learning": learning,
            "overview_utility": utility,
            "overview_track": track,
            "sections_phase_header": phase_total,
            "sections_gates_header": gates,
            "sections_learning_header": learning,
            "sections_utility_header": utility,
            "sections_track_header": track,
            "sections_phase_subtotal": phase_total,
            "sections_gates_row": gates,
            "sections_learning_row": learning,
            "sections_utility_row": utility,
            "sections_track_row": track,
        }
        self.assertEqual(
            expected, claims,
            "Manual/SYSTEM_OVERVIEW.md and/or Manual/SECTIONS_COMMANDS.md "
            "quotes a phase/gate/learning/utility/track command breakdown "
            "that disagrees with the measured commands/*.md classification",
        )


class ClassificationCompletenessTest(unittest.TestCase):
    """Proves the declared TRACK_COMMAND_NAMES / LEARNING_COMMAND_NAMES
    classification (an editorial judgement, ADR-0012's declared-value
    carve-out) actually partitions the real `commands/*.md` file set: every
    declared name is a real file, no file is claimed by two categories, and
    together with the derived phase/gate globs they cover every command
    with none left over and none double-counted. Without this, a renamed
    or removed command could silently vanish from every category (utility
    undercounts) or a newly added one could silently land in "utility" by
    default without ever being classified on purpose."""

    def test_declared_names_are_real_command_files(self):
        all_names = _all_command_names()
        ghosts = sorted(
            (TRACK_COMMAND_NAMES | LEARNING_COMMAND_NAMES) - all_names
        )
        self.assertEqual(
            [], ghosts,
            "TRACK_COMMAND_NAMES/LEARNING_COMMAND_NAMES names a command "
            "with no commands/*.md file: " + ", ".join(ghosts),
        )

    def test_no_command_name_is_claimed_by_two_categories(self):
        phase_and_gate = _phase_and_gate_command_names()
        overlap_track = sorted(phase_and_gate & TRACK_COMMAND_NAMES)
        overlap_learning = sorted(phase_and_gate & LEARNING_COMMAND_NAMES)
        overlap_track_learning = sorted(TRACK_COMMAND_NAMES & LEARNING_COMMAND_NAMES)
        self.assertEqual([], overlap_track, "phase/gate vs. track overlap")
        self.assertEqual([], overlap_learning, "phase/gate vs. learning overlap")
        self.assertEqual([], overlap_track_learning, "track vs. learning overlap")

    def test_every_command_is_classified_exactly_once(self):
        all_names = _all_command_names()
        phase_and_gate = _phase_and_gate_command_names()
        classified = phase_and_gate | TRACK_COMMAND_NAMES | LEARNING_COMMAND_NAMES
        utility = measured_utility_command_names()
        # utility is defined as the residual, so this is a tautology for
        # "covers everything" -- the real check is that the residual
        # doesn't silently swallow a name that SHOULD have been declared
        # track/learning, which the two tests above catch. This test pins
        # the partition arithmetic itself: classified + utility == all,
        # disjoint.
        self.assertEqual(
            all_names, classified | utility,
            "classified + residual utility commands do not cover every "
            "commands/*.md file",
        )
        self.assertEqual(
            set(), classified & utility,
            "a command name is both explicitly classified and counted as "
            "residual utility",
        )


class InstinctCountAgreementTest(unittest.TestCase):
    """README.md's structure listing, templates/STARTER_INSTINCTS.md's own
    self-description, and (since CCP-1152 Auftrag 2) CLAUDE.md's own "Two
    ways to adopt the starter content" sentence all state the shipped
    index's total bullet count -- must equal `read_index_entries()`'s own
    pinned baseline (`test_instinct_registers_agree.py`'s
    `ClassificationCountsTest`), not retyped here. CLAUDE.md's own claim
    (45) drifted against a measured 46 in the very commit that first built
    this class -- the ADR-0012 enforcement pass introduced fresh drift in
    the doc every session loads at start, which is why it is pinned rather
    than left to prose review a second time."""

    def test_docs_agree_with_the_measured_index_total(self):
        total = len(read_index_entries())
        claims = parse_instinct_count_claims(
            _read(README_PATH),
            _read(REPO_ROOT / "templates" / "STARTER_INSTINCTS.md"),
            _read(CLAUDE_PATH),
        )
        expected = {
            "readme_index_total": total,
            "frontmatter_index_total": total,
            "body_index_total": total,
            "split_layout_total": total,
            "claude_split_layout_total": total,
        }
        self.assertEqual(
            expected, claims,
            f"README.md, templates/STARTER_INSTINCTS.md and/or CLAUDE.md "
            f"quotes an instincts.md index total that disagrees with the "
            f"measured index bullet count ({total})",
        )

    def test_sampler_count_matches_its_own_pin(self):
        """Sanity cross-check, not a new measurement: the sampler count
        this module's claim-extraction relies on is the same one
        `test_instinct_registers_agree.py` already pins."""
        self.assertEqual(13, len(read_sampler_entries()))


class ClaimExtractionShapeTest(unittest.TestCase):
    """Every `parse_*` function above must find its anchor phrase in the
    real, tracked doc TODAY -- if a claim's wording changes (a rewrite, a
    rephrase) without this module being updated, every `parse_*` call
    silently returns `None` for that key and the acceptance test's dict
    comparison reports a `None` mismatch that reads like "the doc says
    nothing" rather than "the doc changed its wording". This class turns
    that into an explicit, named failure instead of a confusing diff."""

    def test_no_claim_is_unparsed(self):
        all_claims = {}
        all_claims.update(parse_test_count_claims(
            _read(README_PATH), _read(CONTRIBUTING_PATH),
        ))
        all_claims.update(parse_agent_count_claims(
            _read(README_PATH), _read(SYSTEM_OVERVIEW_PATH),
        ))
        all_claims.update(parse_command_count_claims(
            _read(README_PATH), _read(MANUAL_README_PATH),
            _read(SYSTEM_OVERVIEW_PATH), _read(SECTIONS_COMMANDS_PATH),
        ))
        all_claims.update(parse_command_breakdown_claims(
            _read(SYSTEM_OVERVIEW_PATH), _read(SECTIONS_COMMANDS_PATH),
        ))
        all_claims.update(parse_instinct_count_claims(
            _read(README_PATH), _read(REPO_ROOT / "templates" / "STARTER_INSTINCTS.md"),
            _read(CLAUDE_PATH),
        ))
        unparsed = sorted(key for key, value in all_claims.items() if value is None)
        self.assertEqual(
            [], unparsed,
            "the following claims' anchor phrases were not found in their "
            "doc -- the wording changed and this module's regex needs "
            "updating, not the doc: " + ", ".join(unparsed),
        )


class ParserDiscriminatesFromUnrelatedNumbersTest(unittest.TestCase):
    """Permanent, committed proof that EVERY extractor's anchor phrase is
    specific enough not to grab an unrelated nearby number -- synthetic
    text with a decoy number next to the real one, asserting only the
    anchored value is returned. CCP-1152 Auftrag 3 closed the gap the
    class docstring already claimed was closed: 2 of the 5 `parse_*`
    functions above had a red-proof test here and 3 did not
    (`parse_command_count_claims`, `parse_command_breakdown_claims`,
    `parse_instinct_count_claims`) -- an extractor with no specificity
    proof is the same failure class as a check stage never seen red: it
    can look correct while being one loose regex away from silently
    reading the wrong number out of a doc that quotes several. The PO
    decided against narrowing this docstring instead: the riskiest
    extractor, `parse_command_breakdown_claims` (ten integers anchored in
    one sentence, five more scattered nearby), is exactly the one a
    narrowed docstring would have left unverified."""

    def test_test_count_extractor_ignores_an_adjacent_unrelated_number(self):
        readme = (
            "In 2026 the scripts are covered by a Python suite of "
            "**2,606+ tests**, see page 42 for details.\n"
        )
        contributing = (
            "Measured on 05.09.2026 (issue #17): discovery collects "
            "**2606 tests, 0\nimport errors**, exit 0.\n"
        )
        claims = parse_test_count_claims(readme, contributing)
        self.assertEqual(2606, claims["test_count_readme_floor"])
        self.assertEqual(2606, claims["contributing_count"])
        self.assertEqual(0, claims["contributing_errors"])

    def test_agent_count_extractor_ignores_an_adjacent_unrelated_number(self):
        readme = (
            "+-- v2/\n"
            "+-- agents/                # 13 domain agents + project-guide + wingman = 15\n"
        )
        overview = (
            "|         +------+ +------+ +------+   15 agents               |\n"
            "    CC --> Agents[\"15 agents (incl. wingman) · max 3-4 parallel\"]\n"
            "13 domain subagents + `project-guide` + `wingman` = 15 agents. Step 2.\n"
        )
        claims = parse_agent_count_claims(readme, overview)
        self.assertEqual(15, claims["agent_readme_structure"])
        self.assertEqual(15, claims["ascii_box"])
        self.assertEqual(15, claims["mermaid"])
        self.assertEqual(15, claims["summary_line"])

    def test_command_count_extractor_ignores_an_adjacent_unrelated_number(self):
        readme = (
            "+-- v2/\n"
            "+-- commands/                # 116 slash commands (P0-P8 + Lean-Track "
            "+ cross-cutting), see issue 42\n"
            "\n"
            "Filed under issue 42, see All 116 commands, grouped by section for "
            "the full list.\n"
        )
        manual_readme = "Issue #7: Browse all 116 commands grouped by section here.\n"
        overview = "Released in v2.3 (issue 42): **Total: 116 commands**, up from 82.\n"
        sections = (
            "Chapter 5 (page 42) covers **116 Commands** – full granularity, "
            "see page 7.\n\n"
            "## Summary: 116 Commands\n\n"
            "Filed under issue #9 (was 42).\n\n"
            "| Category | Count |\n"
            "|---|---|\n"
            "| **Total** | **116** |\n"
        )
        claims = parse_command_count_claims(readme, manual_readme, overview, sections)
        self.assertEqual(116, claims["command_readme_structure"])
        self.assertEqual(116, claims["readme_table"])
        self.assertEqual(116, claims["command_manual_readme"])
        self.assertEqual(116, claims["system_overview_total"])
        self.assertEqual(116, claims["sections_commands_top"])
        self.assertEqual(116, claims["sections_commands_summary_heading"])
        self.assertEqual(116, claims["sections_commands_summary_table"])

    def test_command_breakdown_extractor_ignores_adjacent_unrelated_numbers(self):
        """The riskiest extractor: ten integers anchored in one sentence
        (the P0..P8 breakdown) plus four more scattered decoys nearby, all
        distinct from the real values -- a loose capture group here would
        silently read a page number, an issue number or a stale historical
        figure into a documented breakdown instead of the real one."""
        overview = (
            "See page 999 for the roadmap. **82 phase commands** (P0: 3, P1: 5, "
            "P2: 4, P3: 23, P4: 4, P5: 12, P6: 22, P7: 5, P8: 4). Historical "
            "count was 79 in v1.\n\n"
            "**12 gates** (was 11 last release), **2 learning commands** "
            "(roadmap adds 1 more), **14 utility commands** (issue #42), and "
            "**6 track + cross-cutting commands** (see page 3).\n"
        )
        sections = (
            "Phase Commands (P0–P8, 82 commands), previously 79 -- see "
            "issue 42.\n\n"
            "Gates (12 commands), up from 11.\n\n"
            "Continuous Learning (2 commands), roadmap +1.\n\n"
            "Utility (14 commands), issue #42.\n\n"
            "Track-Skills (Cross-Cutting, 6 commands), see page 3.\n\n"
            "**Subtotal — phase commands** | **82** |\n\n"
            "Gates (main + sub-gates) | 12 | previously 11\n\n"
            "| Continuous Learning | 2 | +1 roadmap |\n\n"
            "| Utility | 14 | issue 42 |\n\n"
            "Track + Cross-Cutting (track + learning) | 6 | page 3\n"
        )
        claims = parse_command_breakdown_claims(overview, sections)
        self.assertEqual(82, claims["overview_phase_total"])
        self.assertEqual([3, 5, 4, 23, 4, 12, 22, 5, 4], claims["overview_phase_breakdown"])
        self.assertEqual(12, claims["overview_gates"])
        self.assertEqual(2, claims["overview_learning"])
        self.assertEqual(14, claims["overview_utility"])
        self.assertEqual(6, claims["overview_track"])
        self.assertEqual(82, claims["sections_phase_header"])
        self.assertEqual(12, claims["sections_gates_header"])
        self.assertEqual(2, claims["sections_learning_header"])
        self.assertEqual(14, claims["sections_utility_header"])
        self.assertEqual(6, claims["sections_track_header"])
        self.assertEqual(82, claims["sections_phase_subtotal"])
        self.assertEqual(12, claims["sections_gates_row"])
        self.assertEqual(2, claims["sections_learning_row"])
        self.assertEqual(14, claims["sections_utility_row"])
        self.assertEqual(6, claims["sections_track_row"])

    def test_instinct_count_extractor_ignores_an_adjacent_unrelated_number(self):
        readme = (
            "The index ships a compact 13-instinct sampler (split layout ships "
            "the full 46), see page 42.\n"
        )
        starter = (
            "status: COMPLETE shipped snapshot (46 instincts), not the sampler.\n\n"
            "This **complete** CCPR instinct snapshot holds **46 instincts** as "
            "of issue #17.\n\n"
            "The split layout ships the full 46-instinct set, page 7.\n"
        )
        claude = "the layout and carry **46 instincts** (issue #42). Copy them as-is.\n"
        claims = parse_instinct_count_claims(readme, starter, claude)
        self.assertEqual(46, claims["readme_index_total"])
        self.assertEqual(46, claims["frontmatter_index_total"])
        self.assertEqual(46, claims["body_index_total"])
        self.assertEqual(46, claims["split_layout_total"])
        self.assertEqual(46, claims["claude_split_layout_total"])


if __name__ == "__main__":
    unittest.main()
