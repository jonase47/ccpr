"""test_command_frontmatter.py -- WI-0129: `disable-model-invocation` coverage
over commands/*.md.

## Why this exists

Claude Code 2.1.251 loads `~/.claude/commands/*.md` into the same
model-facing catalogue as skills. A command file with no frontmatter is both
user- and model-invocable; `disable-model-invocation: true` in a three-line
frontmatter block at the top of the file removes it from the model-facing
catalogue while leaving it callable by the user as a slash command. Measured
against the installed binary: flagging one file dropped `/context`'s skill
count from 134 to 133 in a fresh session.

The PO's criterion: a command gets the flag when its write pre-empts a
decision that belongs to the PO -- not merely because it writes versioned
state. That criterion is not fully mechanizable, and this module does not
pretend otherwise. It is split into the three pieces the briefing asked for:

- **Pattern-derived** (Rule A): every `gate-*.md` and `p[0-8]-*.md` file. No
  exception, no weighing -- derived from the filename at runtime, never a
  hard-coded count or name list.
- **Body-derived** (Rule B): any command whose body invokes
  `workitems.py create` touches the work stock and must carry the flag.
  Grepped at runtime, not asserted from a remembered list.
- **Editorial residual** (Rule C): the rest cannot be derived from the
  filename or the body text. It is a hand-classified list, and the point of
  this module is that the list is not allowed to be silently incomplete --
  see ClassificationCoverageTest below. Each entry also carries an
  EVIDENCE CLASS -- `editorial` (Rule A/B genuinely do not reach it) or
  `mechanical` (Rule A or B already covers it, and the entry's presence in
  this dict is a second, independent proof of the same conclusion, not the
  only one). EvidenceClassConsistencyTest recomputes both classes at
  runtime and fails an entry whose declared class does not match what Rule
  A/B actually finds -- see that test's docstring for why this exists.

## The body-derived rule caught fewer files than the briefing assumed

The briefing that ordered this module said Rule B "actually decides `anchor`
and `cleanup`". Measuring it: `anchor.md` does invoke `workitems.py create`
(a literal `python3 ~/.claude/scripts/workitems.py create --title "Anchor
drift: ..."` call). `cleanup.md` does not -- grepping its body for the string
"workitems" returns nothing at all. Its §1 inbox-triage table offers
"create a work item ... or append a BACKLOG.md mini-story" as one of four
PO-confirmed *outcomes* of a triage decision, in prose, never as a coded
invocation. `cleanup` is therefore classified by Rule C (the editorial
residual), not Rule B -- it pre-empts the PO's work-stock decision by putting
a work-item-creation option in front of the PO for confirmation, which is a
judgment call about the PO's decision surface, not a thing the body text
proves mechanically. `anchor` is covered by BOTH Rule B and Rule C (Rule C's
list is not required to be disjoint from Rule A/B -- see the module-level
note on EDITORIAL_IN_SCOPE below).

## The drift property (Rule C's actual job)

A hand-classified list is only as good as the thing that forces it to stay
complete. Without a fourth check, a new command file that matches neither
Rule A's filename pattern nor Rule B's body grep, and that nobody added to
EITHER of Rule C's two lists, lands unclassified and silently gets whatever
default `git diff` happens to leave it with -- never asserted against by any
test. ClassificationCoverageTest is that fourth check: every file under
`commands/` must be classified by at least one of Rule A, Rule B,
EDITORIAL_IN_SCOPE or EDITORIAL_OUT_OF_SCOPE, or the test fails by name.
CommandFrontmatterMutationTest exercises this directly against a synthetic
dummy file (never a real one, per G-107/G-143 -- an in-memory/tempfile
fixture, not a mutation of `commands/*.md`).

## What this module can and cannot catch

It can catch: a file in Rule A's or Rule B's scope missing the flag, a file
in EDITORIAL_OUT_OF_SCOPE carrying the flag it must not have, and a new file
falling outside all four classifications (the drift case). It CANNOT catch a
misjudged editorial call -- if a human deliberately (and wrongly) moves a
command's stem from EDITORIAL_IN_SCOPE to EDITORIAL_OUT_OF_SCOPE, the test
stays green, because Rule C's residual is by definition the part neither the
filename nor the body text can verify. That is the honest boundary of a
criterion that "is not fully mechanizable" (the briefing's own words), not a
gap this module tries to close.
"""

import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "commands"

# Rule A: pattern-derived. Matches on the filename STEM (no `.md`), applied
# at runtime -- never a hard-coded count or a name list. `p[0-8]-` requires
# the digit and the trailing hyphen so `postmortem.md` and `project-init.md`
# (no digit-hyphen after the prefix) do not accidentally match.
PHASE_COMMAND_RE = re.compile(r"^(gate-|p[0-8]-)")

# Rule B: body-derived. The literal invocation seen in the corpus is
# `python3 ~/.claude/scripts/workitems.py create --title ...`; the pattern is
# looser (script name + "create" as separate tokens, arbitrary whitespace)
# so a line-wrapped or differently-flagged invocation of the same script
# still counts, while `workitems.py list`/`workitems list` (a read, not a
# work-stock write) does not match "create".
WORKITEMS_CREATE_RE = re.compile(r"workitems\.py\s+create")

# Rule C: the editorial residual -- see the module docstring's "Rule C" and
# "drift property" sections. Every stem here is required to actually carry
# the flag (CommandFrontmatterCorrectnessTest). The value is the entry's
# EVIDENCE CLASS (see module docstring): `EVIDENCE_EDITORIAL` for a stem
# Rule A/B genuinely cannot reach, `EVIDENCE_MECHANICAL` for one Rule A or B
# already covers, where this dict is a second, independent proof rather than
# the only one. `anchor` invokes `workitems.py create` in its body (Rule B)
# -- declared `EVIDENCE_MECHANICAL` on that basis, not left `editorial`,
# because EvidenceClassConsistencyTest treats an editorial declaration that
# Rule A/B actually covers as a promotable claim, i.e. a failure: the
# collision is resolved here, not papered over. `specialize` writes a
# project-local, never-re-synced shadow copy under `.claude/agents/` that
# takes precedence over the global agent -- an environment decision that
# pre-empts the PO's choice of which agent definition runs, and neither
# Rule A's filename pattern nor Rule B's `workitems.py create` grep can see
# that; declared `EVIDENCE_EDITORIAL`.
EVIDENCE_EDITORIAL = "editorial"
EVIDENCE_MECHANICAL = "mechanical"

EDITORIAL_IN_SCOPE = {
    "anchor": EVIDENCE_MECHANICAL,
    "cleanup": EVIDENCE_EDITORIAL,
    "constitution": EVIDENCE_EDITORIAL,
    "decision": EVIDENCE_EDITORIAL,
    "epic": EVIDENCE_EDITORIAL,
    "instinct": EVIDENCE_EDITORIAL,
    "konzept": EVIDENCE_EDITORIAL,
    "konzept-update": EVIDENCE_EDITORIAL,
    "lean-frame": EVIDENCE_EDITORIAL,
    "lean-learn": EVIDENCE_EDITORIAL,
    "lean-promote": EVIDENCE_EDITORIAL,
    "postmortem": EVIDENCE_EDITORIAL,
    "project-init": EVIDENCE_EDITORIAL,
    "release-baseline": EVIDENCE_EDITORIAL,
    "roadmap": EVIDENCE_EDITORIAL,
    "roadmap-update": EVIDENCE_EDITORIAL,
    "specialize": EVIDENCE_EDITORIAL,
    "track-decision": EVIDENCE_EDITORIAL,
    "user-stories": EVIDENCE_EDITORIAL,
}

# The three commands the PO decided must stay model-invocable. Held out
# explicitly rather than left as "everything Rule A/B/EDITORIAL_IN_SCOPE
# does not reach" so that a file silently falling outside every list is a
# genuine drift failure (see ClassificationCoverageTest), not something that
# defaults into this set by omission -- neither list is a computed
# complement of the other. `specialize` moved here from a prior draft of
# this set once the PO decided it pre-empts a PO-owned environment decision
# (see EDITORIAL_IN_SCOPE's comment above); it is not a candidate for this
# set any more.
EDITORIAL_OUT_OF_SCOPE = frozenset({
    "cross-check", "guide", "logs-summary",
})

FLAG_LINE = "disable-model-invocation: true"


def _iter_command_files():
    return sorted(COMMANDS_DIR.glob("*.md"))


def has_disable_model_invocation_flag(text):
    """True if `text`'s first three lines are exactly the frontmatter block
    `---` / `disable-model-invocation: true` / `---`. Line-positional on
    purpose: Claude Code derives the user-facing slash-command description
    from the first non-empty line AFTER the frontmatter, so a flag block
    anywhere else in the file would not be the thing Claude Code reads."""
    lines = text.splitlines()
    return (
        len(lines) >= 3
        and lines[0].strip() == "---"
        and lines[1].strip() == FLAG_LINE
        and lines[2].strip() == "---"
    )


def matches_phase_pattern(stem):
    """Rule A's detector."""
    return bool(PHASE_COMMAND_RE.match(stem))


def body_invokes_workitems_create(text):
    """Rule B's detector, over the whole file text (commands/*.md files were
    not frontmatter-bearing before this change for 111 of 116 of them, so
    there is no meaningful "body-only" restriction the way agents/*.md's
    detectors have one; the four-line frontmatter this module now expects
    cannot itself contain the invocation string)."""
    return bool(WORKITEMS_CREATE_RE.search(text))


def classify(stem, text):
    """Returns (is_classified, expected_in_scope) for one command file.
    `is_classified` is False exactly for the drift case the module docstring
    describes -- a file in none of Rule A, Rule B, or either editorial
    list."""
    in_scope_reasons = (
        matches_phase_pattern(stem)
        or body_invokes_workitems_create(text)
        or stem in EDITORIAL_IN_SCOPE
    )
    out_of_scope = stem in EDITORIAL_OUT_OF_SCOPE
    if in_scope_reasons:
        return True, True
    if out_of_scope:
        return True, False
    return False, None


class MeasuredCorpusSizeTest(unittest.TestCase):
    """Pins the corpus size the rest of this module's docstring reasons
    about (116 total, 94 pattern-derived, 19 editorial-in, 3 editorial-out).
    Without this pin, a file added or removed elsewhere in commands/ changes
    every other test's coverage silently instead of failing here first.

    Both numbers below are DERIVED values (a file count; a count that
    follows deterministically from PHASE_COMMAND_RE against the current
    tree) stored as literals instead of computed at import time -- normally
    the shape this project's register-drift discipline exists to catch (see
    `docs/memory/senior-developer/register-drift-mechanism.md`, whose R1/R2
    sections close two slices of exactly that class in
    `test_live_status_claims.py` and `check-all.sh`'s catalogue count). This
    pin is a CONSCIOUS exception to that discipline, not an instance of it:
    its entire purpose is to fail the moment `len(_iter_command_files())` or
    the pattern-match count no longer equals the stored literal, so a file
    silently added or removed is caught HERE first rather than surfacing as
    a diffuse failure in every other test in this module. A reader who
    "fixes" drift by replacing the literal with the live computation removes
    the guard.

    On the citation itself: this project's own memory does not carry a rule
    literally named "R1" about derived values -- `register-drift-mechanism.md`
    uses "R1" and "R2" as labels for two specific work sessions (the
    self-reported-failure-state slice and the derivable-count slice), not a
    rule ID. The closest textual match to "derived values are generated, not
    stored" is that same file's line 28, which attributes the idea in
    passing to "the A1 rule" -- but no file in this repository defines an
    "A1 rule" with that content; the "A1" headings that do exist
    (`docs/adr/ADR-0009-anchored-state-verification.md`,
    `docs/decisions/2026-08-18_package-a-hygiene.md`,
    `docs/memory/senior-developer/heuristic-scanners.md`) name unrelated
    work. The closest DOCUMENTED precedent for a deliberate hand-typed pin
    being an authorised exception, rather than a defect, is
    `docs/memory/senior-developer/shipped-script-inventory-pins.md`, which
    lists six existing pins in other test modules on the same grounds. This
    module's two pins join that set."""

    def test_total_command_file_count_is_pinned(self):
        files = _iter_command_files()
        self.assertEqual(
            len(files), 116,
            "commands/*.md file count drifted from the pinned 116 -- "
            "update this pin deliberately if a file was added or removed "
            "on purpose:\n{}".format([p.name for p in files]),
        )

    def test_pattern_derived_count_is_pinned(self):
        matched = [p.stem for p in _iter_command_files()
                   if matches_phase_pattern(p.stem)]
        self.assertEqual(
            len(matched), 94,
            "Rule A's pattern-derived set drifted from the pinned 94:\n{}"
            .format(sorted(matched)),
        )

    def test_editorial_lists_do_not_overlap_each_other(self):
        # EDITORIAL_IN_SCOPE may overlap Rule A/B (see `anchor`); it must
        # never overlap EDITORIAL_OUT_OF_SCOPE, or Rule C's own two lists
        # contradict each other.
        overlap = set(EDITORIAL_IN_SCOPE) & EDITORIAL_OUT_OF_SCOPE
        self.assertFalse(
            overlap,
            "EDITORIAL_IN_SCOPE and EDITORIAL_OUT_OF_SCOPE overlap on: {}"
            .format(sorted(overlap)),
        )


class EvidenceClassConsistencyTest(unittest.TestCase):
    """Two evidence classes looked identical in the test's output before
    this class existed: `cleanup` sits in EDITORIAL_IN_SCOPE on genuinely
    editorial grounds (Rule A/B cannot see it), `anchor` and `p4-backlog`
    would have sat there (or in the mechanical set) on MECHANICAL grounds
    (Rule B greps their body). Indistinguishable evidence classes is the
    shape register drift grows from -- `cleanup` gaining a `workitems.py
    create` invocation later must show up as an evidence-class mismatch
    here, not pass silently the way a bare frozenset membership would.

    This recomputes Rule A/B coverage at runtime for every declared
    EDITORIAL_IN_SCOPE entry and asserts the declared class against it, in
    both directions:

    - declared `editorial` but Rule A or B actually covers it -> fail,
      naming the entry and the rule that covers it (it is PROMOTABLE to
      mechanical -- see EDITORIAL_IN_SCOPE's comment on `anchor`).
    - declared `mechanical` but neither Rule A nor B covers it -> fail,
      naming the entry (the mechanical backing it claims does not exist).
    """

    def _covering_rule(self, stem, text):
        """Returns 'A', 'B', or None -- named so failure messages can say
        which rule does or does not cover an entry, not just whether one
        does."""
        if matches_phase_pattern(stem):
            return "A"
        if body_invokes_workitems_create(text):
            return "B"
        return None

    def test_declared_evidence_class_matches_runtime_coverage(self):
        promotable = []
        unbacked = []
        for stem, evidence_class in EDITORIAL_IN_SCOPE.items():
            path = COMMANDS_DIR / "{}.md".format(stem)
            self.assertTrue(
                path.exists(),
                "EDITORIAL_IN_SCOPE names '{}', no such file at {} -- an "
                "orphaned entry from a rename or deletion".format(stem, path),
            )
            text = path.read_text(encoding="utf-8")
            rule = self._covering_rule(stem, text)
            if evidence_class == EVIDENCE_EDITORIAL and rule is not None:
                promotable.append((stem, rule))
            elif evidence_class == EVIDENCE_MECHANICAL and rule is None:
                unbacked.append(stem)
        self.assertFalse(
            promotable,
            "entry/entries declared 'editorial' are actually covered by a "
            "runtime rule and can be promoted to 'mechanical':\n"
            + "\n".join("{} -- covered by Rule {}".format(s, r)
                         for s, r in sorted(promotable)),
        )
        self.assertFalse(
            unbacked,
            "entry/entries declared 'mechanical' have no runtime rule "
            "backing that claim (neither Rule A's filename pattern nor "
            "Rule B's workitems.py create grep covers them):\n"
            + "\n".join(sorted(unbacked)),
        )


class ClassificationCoverageTest(unittest.TestCase):
    """The drift property from the module docstring: every real file under
    commands/ must be classified by at least one of Rule A, Rule B,
    EDITORIAL_IN_SCOPE or EDITORIAL_OUT_OF_SCOPE. A file matching none of
    the four is command #117 landing silently unclassified -- exactly the
    shape this test exists to make loud instead of silent."""

    def test_every_command_file_is_classified(self):
        unclassified = []
        for path in _iter_command_files():
            text = path.read_text(encoding="utf-8")
            classified, _ = classify(path.stem, text)
            if not classified:
                unclassified.append(path.name)
        self.assertFalse(
            unclassified,
            "command file(s) matched none of Rule A (gate-*/p[0-8]-*), "
            "Rule B (workitems.py create in body), EDITORIAL_IN_SCOPE or "
            "EDITORIAL_OUT_OF_SCOPE -- classify them deliberately:\n"
            + "\n".join(unclassified),
        )


class CommandFrontmatterCorrectnessTest(unittest.TestCase):
    """Both directions, over the full corpus: a file classified in-scope
    must carry the flag, a file classified out-of-scope must not. Iterates
    every real file rather than a remembered list, so this is the test that
    goes red the moment the sweep in commands/*.md has not (yet, or no
    longer) matched the classification."""

    def test_every_in_scope_file_carries_the_flag(self):
        missing = []
        for path in _iter_command_files():
            text = path.read_text(encoding="utf-8")
            classified, expected_in_scope = classify(path.stem, text)
            if classified and expected_in_scope and not has_disable_model_invocation_flag(text):
                missing.append(path.name)
        self.assertFalse(
            missing,
            "in-scope command file(s) missing the "
            "disable-model-invocation frontmatter block:\n"
            + "\n".join(sorted(missing)),
        )

    def test_no_out_of_scope_file_carries_the_flag(self):
        wrongly_flagged = []
        for path in _iter_command_files():
            text = path.read_text(encoding="utf-8")
            classified, expected_in_scope = classify(path.stem, text)
            if classified and not expected_in_scope and has_disable_model_invocation_flag(text):
                wrongly_flagged.append(path.name)
        self.assertFalse(
            wrongly_flagged,
            "out-of-scope command file(s) wrongly carry the "
            "disable-model-invocation flag (PO decided these must stay "
            "model-invocable):\n" + "\n".join(sorted(wrongly_flagged)),
        )


class PatternDerivedRuleTest(unittest.TestCase):
    """Rule A in isolation: every gate-*.md / p[0-8]-*.md file, named
    explicitly (not via classify()) so this test does not share a bug with
    the function it is meant to check."""

    def test_every_gate_and_phase_file_carries_the_flag(self):
        missing = []
        for path in _iter_command_files():
            if not matches_phase_pattern(path.stem):
                continue
            text = path.read_text(encoding="utf-8")
            if not has_disable_model_invocation_flag(text):
                missing.append(path.name)
        self.assertFalse(
            missing,
            "gate-*/p[0-8]-* command file(s) missing the flag:\n"
            + "\n".join(sorted(missing)),
        )


class BodyDerivedRuleTest(unittest.TestCase):
    """Rule B in isolation, and the measured corpus it applies to: today,
    exactly `anchor` and `p4-backlog` invoke `workitems.py create` in their
    body (`p4-backlog` is also covered by Rule A). If this set changes,
    Rule B's premise needs re-triage, not a widened acceptance -- see the
    module docstring's correction of the briefing's `cleanup` claim."""

    def test_the_body_invoking_set_matches_the_measured_corpus(self):
        invoking = set()
        for path in _iter_command_files():
            text = path.read_text(encoding="utf-8")
            if body_invokes_workitems_create(text):
                invoking.add(path.stem)
        self.assertEqual(
            invoking, {"anchor", "p4-backlog"},
            "the set of commands invoking workitems.py create in their "
            "body diverged from the measured corpus; got: {}"
            .format(sorted(invoking)),
        )

    def test_cleanup_does_not_invoke_workitems_create(self):
        # Named regression pin for the briefing correction: cleanup.md's
        # inbox-triage table OFFERS work-item creation as a PO-confirmed
        # outcome in prose; it never invokes the script. If this ever goes
        # true, `cleanup` moves from Rule C to Rule B and the module
        # docstring's correction needs updating, not silent acceptance.
        text = (COMMANDS_DIR / "cleanup.md").read_text(encoding="utf-8")
        self.assertFalse(body_invokes_workitems_create(text))


class FlagDetectorBoundaryTest(unittest.TestCase):
    """Unit-level RED proofs for has_disable_model_invocation_flag itself,
    entirely in-memory -- no real commands/*.md file is read or mutated
    here (G-107/G-143's synthetic-fixture pattern, mirrored from
    test_agent_frontmatter.py's RequiredFieldsTest)."""

    def test_the_real_shape_is_detected(self):
        text = "---\ndisable-model-invocation: true\n---\n# /example – Title\n"
        self.assertTrue(has_disable_model_invocation_flag(text))

    def test_a_file_with_no_frontmatter_is_not_detected(self):
        text = "# /example – Title\n\nBody text.\n"
        self.assertFalse(has_disable_model_invocation_flag(text))

    def test_the_flag_line_must_be_exactly_line_two(self):
        # A block that opens correctly but carries a different or
        # differently-valued second line must not count -- this is the
        # structural check the mutation tests below rely on.
        text = "---\ndisable-model-invocation: false\n---\n# /example\n"
        self.assertFalse(has_disable_model_invocation_flag(text))

    def test_a_flag_block_not_at_the_top_of_the_file_is_not_detected(self):
        text = "# /example – Title\n\n---\ndisable-model-invocation: true\n---\n"
        self.assertFalse(has_disable_model_invocation_flag(text))


class ClassifyFunctionBoundaryTest(unittest.TestCase):
    """Unit-level proofs for classify() itself, entirely synthetic -- proves
    the four-way split (Rule A / Rule B / editorial-in / unclassified) each
    fire on the shape they are meant to, independent of any real file."""

    def test_a_gate_named_file_is_classified_in_scope_by_pattern_alone(self):
        classified, expected = classify("gate-p9", "no workitems mention here")
        self.assertTrue(classified)
        self.assertTrue(expected)

    def test_a_phase_named_file_is_classified_in_scope_by_pattern_alone(self):
        classified, expected = classify("p3-new-subskill", "plain body")
        self.assertTrue(classified)
        self.assertTrue(expected)

    def test_a_body_invoking_file_is_classified_in_scope_by_body_alone(self):
        classified, expected = classify(
            "some-new-command", "run `python3 ~/.claude/scripts/workitems.py create ...`"
        )
        self.assertTrue(classified)
        self.assertTrue(expected)

    def test_an_editorial_in_scope_stem_is_classified_in_scope(self):
        classified, expected = classify("anchor", "no workitems mention here")
        self.assertTrue(classified)
        self.assertTrue(expected)

    def test_an_editorial_out_of_scope_stem_is_classified_out_of_scope(self):
        classified, expected = classify("guide", "plain body")
        self.assertTrue(classified)
        self.assertFalse(expected)

    def test_an_unlisted_plain_stem_is_unclassified(self):
        # This is the drift shape: a stem matching neither pattern nor
        # body, in neither editorial list.
        classified, expected = classify("brand-new-command", "plain body, nothing special")
        self.assertFalse(classified)
        self.assertIsNone(expected)


class CommandFrontmatterMutationTest(unittest.TestCase):
    """RED proofs against real files and a real, disposable temp file --
    mirrors Rule4HistoricalRedProofTest's "both directions from real
    evidence" posture, adapted to this module (no historical git-show
    fixture exists for commands/*.md yet, so the mutations are applied to
    and then verified against the CURRENT tree, exactly as briefed in
    §3 of WI-0129).

    Every mutation here (i) is verified to have landed via a literal grep
    before being measured, (ii) is restored in the same test method that
    applied it, and (iii) never touches `set -e`/pipe semantics, since this
    module runs mutations through direct file writes, not shell pipelines.
    """

    def _read(self, path):
        return path.read_text(encoding="utf-8")

    def test_removing_the_flag_from_a_gate_file_is_detected(self):
        # Mutation (i) from the briefing: strip the flag from one in-scope
        # gate file and confirm PatternDerivedRuleTest's own check goes red.
        target = COMMANDS_DIR / "gate-p1.md"
        original = self._read(target)
        self.assertTrue(
            has_disable_model_invocation_flag(original),
            "fixture assumption broken: gate-p1.md should already carry "
            "the flag before this mutation runs",
        )
        mutated = "\n".join(original.splitlines()[3:]) + "\n"
        try:
            target.write_text(mutated, encoding="utf-8")
            # Verify the mutation actually landed before measuring it.
            on_disk = self._read(target)
            self.assertNotIn(FLAG_LINE, on_disk.splitlines()[:3])
            # Measure: PatternDerivedRuleTest's own logic must now flag it.
            self.assertFalse(has_disable_model_invocation_flag(on_disk))
            missing = [
                p.name for p in _iter_command_files()
                if matches_phase_pattern(p.stem)
                and not has_disable_model_invocation_flag(self._read(p))
            ]
            self.assertIn(
                "gate-p1.md", missing,
                "RED PROOF observed: gate-p1.md correctly reported missing "
                "after the flag was stripped -- missing set: {}"
                .format(sorted(missing)),
            )
        finally:
            target.write_text(original, encoding="utf-8")
            self.assertEqual(self._read(target), original)

    def test_wrongly_adding_the_flag_to_an_exempt_file_is_detected(self):
        # Mutation (ii) from the briefing: add the flag to one of the 4
        # PO-exempt files and confirm the out-of-scope check goes red.
        target = COMMANDS_DIR / "guide.md"
        original = self._read(target)
        self.assertFalse(
            has_disable_model_invocation_flag(original),
            "fixture assumption broken: guide.md should NOT carry the "
            "flag before this mutation runs",
        )
        mutated = "---\n{}\n---\n{}".format(FLAG_LINE, original)
        try:
            target.write_text(mutated, encoding="utf-8")
            on_disk = self._read(target)
            self.assertEqual(on_disk.splitlines()[:3],
                              ["---", FLAG_LINE, "---"])
            self.assertTrue(has_disable_model_invocation_flag(on_disk))
            wrongly_flagged = [
                p.name for p in _iter_command_files()
                if p.stem in EDITORIAL_OUT_OF_SCOPE
                and has_disable_model_invocation_flag(self._read(p))
            ]
            self.assertIn(
                "guide.md", wrongly_flagged,
                "RED PROOF observed: guide.md correctly reported as "
                "wrongly flagged -- wrongly_flagged set: {}"
                .format(sorted(wrongly_flagged)),
            )
        finally:
            target.write_text(original, encoding="utf-8")
            self.assertEqual(self._read(target), original)

    def test_an_unclassified_new_command_file_is_detected_as_drift(self):
        # Mutation (iii) from the briefing, and the one most likely to
        # silently pass: a brand-new command file whose stem matches no
        # pattern, whose body invokes nothing, and that nobody added to
        # either editorial list. Created as a disposable temp file, NEVER
        # inside commands/, so ClassificationCoverageTest's own file-scan is
        # exercised against a synthetic stand-in with the identical logic,
        # not against a real tree mutation this module would then have to
        # clean up out of a live directory.
        stem = "brand-new-dummy-command-wi0129"
        text = "# /{} – Dummy command for drift proof\n\nNo special content.\n".format(stem)
        classified, _ = classify(stem, text)
        self.assertFalse(
            classified,
            "RED PROOF FAILED: a synthetic new command file that matches "
            "no pattern, invokes nothing, and is in neither editorial "
            "list was still classified -- the drift property is broken",
        )

        # End-to-end confirmation using a real (temporary, non-repo) file,
        # so the drift proof also exercises _iter_command_files()'s glob
        # shape, not just classify() in isolation.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            dummy = tmp_dir / (stem + ".md")
            dummy.write_text(text, encoding="utf-8")
            found = sorted(tmp_dir.glob("*.md"))
            self.assertEqual([p.name for p in found], [dummy.name])
            classified, _ = classify(dummy.stem, dummy.read_text(encoding="utf-8"))
            self.assertFalse(
                classified,
                "RED PROOF observed: brand-new-dummy-command-wi0129.md "
                "would land unclassified if it were a real commands/*.md "
                "file -- this is exactly command #117 landing silently, "
                "the shape ClassificationCoverageTest exists to catch",
            )


if __name__ == "__main__":
    unittest.main()
