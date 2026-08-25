"""test_memory_lint_commonmark_corpus.py — WI-0005: adversarial round against
check (n) in scripts/memory-lint.sh, using a CommonMark-reference-derived
corpus instead of a hand-derived one.

This module deliberately does NOT `import commonmark`. The corpus/reference
answers are frozen at generation time into
`scripts/tests/fixtures/commonmark_corpus.json` by
`scripts/tests/fixtures/generate_commonmark_corpus.py` (a documented, manual
handgrip — see that file's docstring for when to re-run it). Importing
commonmark here, or `skipIf`-ing on its absence, would make this suite
silently green-by-skip on a machine that never installed the probe
dependency — exactly the pattern this repo has repeatedly measured against
(instinct G-087/G-119: a reported tool gap must be closed, not accepted as a
weaker result; here the risk is a SELF-inflicted gap via `skipIf`). The
fixture is a plain JSON file with no import-time dependency at all.

Two oracles went into every fixture entry, per
docs/memory/reference_commonmark-conformance.md ("Konformitaet wird durch
Ausfuehren entschieden, nie durch Argumentieren"):

  * `reference_checkable_targets` — what the CommonMark reference parser says
    the real, checkable (non-image, non-anchor, non-external-scheme) link
    targets are.
  * `expected_check_n_findings` — what `scripts/memory-lint.sh` check (n)
    ACTUALLY reports today, measured by the generator running it.

Where the two disagree, the entry carries EXACTLY ONE of two explanation
blocks, never both (FixtureIntegrityTest pins the mutual exclusion):

  * `known_divergence` (direction, reason, work_item) — an OPEN gap in
    check (n), tracked for a future fix.
  * `documented_intent` (reason, po_decision, work_item) — WI-0085: a
    disagreement the PO explicitly decided is deliberate, not a bug. check
    (n)'s own contract is narrower than CommonMark conformance ("does the
    index still point at existing files?"), and this is the field for a
    case where that narrower contract is the intended behaviour on purpose.

Either way this test asserts the CURRENT (divergent) behaviour — a frozen,
visible snapshot, not a silent xfail. If the real script's behaviour later
drifts from that frozen snapshot in EITHER direction (the bug gets fixed, or
a different bug appears), the assertion below fails and says so.
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "memory-lint.sh"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "commonmark_corpus.json"
GENERATOR_PATH = Path(__file__).resolve().parent / "fixtures" / "generate_commonmark_corpus.py"

FINDING_RE = re.compile(r"link target '([^']*)' does not exist")

with open(FIXTURE_PATH, encoding="utf-8") as f:
    CORPUS = json.load(f)

# Loaded once at import time and asserted against below (not just trusted) —
# a corpus this test's own coverage-proof depends on must itself have no
# duplicate names, and every known_divergence must be tagged with this work
# item so a future round's own findings are not silently absorbed into this
# one's ledger.
_ENTRY_NAMES = [e["name"] for e in CORPUS["entries"]]


def run_memory_lint_on(markdown_text, script_path=SCRIPT_PATH):
    """Runs `script_path` against one entry, isolated in its own scratch
    project. Mirrors generate_commonmark_corpus.py's run_memory_lint() —
    duplicated rather than imported, because the generator is a manual,
    commonmark-importing tool this test module must not depend on."""
    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp) / "project"
        (project_dir / "docs" / "memory").mkdir(parents=True)
        (project_dir / "docs" / "memory" / "MEMORY.md").write_text(
            "# Memory Index\n\n" + markdown_text, encoding="utf-8"
        )
        fake_home = Path(tmp) / "home"
        fake_home.mkdir()
        result = subprocess.run(
            ["bash", str(script_path), str(project_dir)],
            capture_output=True, text=True,
            env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        )
        return sorted(FINDING_RE.findall(result.stdout))


class FixtureIntegrityTest(unittest.TestCase):
    """The fixture is itself part of what this round delivers — these pins
    keep it honest independent of any live memory-lint.sh run."""

    def test_entry_names_are_unique(self):
        self.assertEqual(
            len(_ENTRY_NAMES), len(set(_ENTRY_NAMES)),
            f"duplicate corpus entry name(s): "
            f"{sorted(n for n in _ENTRY_NAMES if _ENTRY_NAMES.count(n) > 1)}",
        )

    # Closed set of work items allowed to own a `known_divergence` block. WI-0005
    # is the original adversarial-corpus round; WI-0081 (remainder, 23.08.2026)
    # reclassified the named-entity destination row from a "wrong-target" bug
    # into a documented, deliberate non-claim (see that entry's own reason text).
    # WI-0097 is one of the WI-0093 round's three finds -- a stray sentinel byte
    # that pairs with a real one. WI-0098 is the review round's own: a label the
    # paragraph resolver rewrites is keyed differently on the two sides of the
    # reference mechanism, and the FIX for that false positive buys one false
    # negative, which is the divergence class tagged here.
    #
    # WI-0096, that round's third find, is NO LONGER on this list (24.08.2026):
    # the definition-shaped line reported where CommonMark reads none was the
    # last false positive in the corpus and is fixed, so no entry owns that tag
    # any more.
    #
    # WI-0095, the other of the WI-0093 round's three finds, is NO LONGER on
    # this list either (25.08.2026): protect_link_destinations() now checks
    # both a live opener AND escape parity before treating a `](` as a
    # destination, so the wrong span that used to hide a real link inside it no
    # longer forms and both fixtures agree with the reference on both oracles.
    # Both removals are deliberate acts here rather than harmless leftovers, so
    # that re-opening either has to be noticed instead of passing silently. A
    # future round's own findings still get their own new tag, not silently
    # absorbed into any of these three.
    _KNOWN_DIVERGENCE_WORK_ITEMS = {
        "WI-0005", "WI-0081", "WI-0097", "WI-0098",
    }

    def test_every_known_divergence_is_tagged_a_known_work_item(self):
        untagged = [
            e["name"] for e in CORPUS["entries"]
            if e["known_divergence"] is not None
            and e["known_divergence"].get("work_item") not in self._KNOWN_DIVERGENCE_WORK_ITEMS
        ]
        self.assertEqual(untagged, [])

    def test_every_known_divergence_has_a_direction_and_a_reason(self):
        for entry in CORPUS["entries"]:
            kd = entry["known_divergence"]
            if kd is None:
                continue
            with self.subTest(entry=entry["name"]):
                self.assertIn(kd.get("direction"), {"false-positive", "false-negative", "wrong-target"})
                self.assertTrue(kd.get("reason"), "known_divergence.reason must not be empty")

    def test_known_divergence_or_documented_intent_matches_the_frozen_oracle_disagreement(self):
        """The fixture's own internal contract: whenever the two frozen oracle
        fields disagree, the entry must carry an EXPLANATION for that — either
        `known_divergence` (an open gap in check (n)) or `documented_intent`
        (WI-0085: a disagreement the PO decided is deliberate, not a bug —
        check (n)'s own contract is narrower than CommonMark conformance).
        Exactly one of the two, never both, never neither. Catches a
        hand-edited fixture drifting from what the generator actually
        measured, without re-running either oracle."""
        for entry in CORPUS["entries"]:
            with self.subTest(entry=entry["name"]):
                oracles_disagree = (
                    sorted(entry["expected_check_n_findings"])
                    != sorted(entry["reference_checkable_targets"])
                )
                has_kd = entry["known_divergence"] is not None
                has_intent = entry.get("documented_intent") is not None
                self.assertFalse(
                    has_kd and has_intent,
                    f"{entry['name']!r} carries both known_divergence and "
                    f"documented_intent — exactly one may explain a disagreement",
                )
                self.assertEqual(
                    has_kd or has_intent, oracles_disagree,
                    f"known_divergence/documented_intent presence ({has_kd or has_intent}) "
                    f"does not match oracle disagreement ({oracles_disagree}) for "
                    f"{entry['name']!r}",
                )

    def test_every_documented_intent_has_a_reason_a_po_decision_and_a_work_item(self):
        for entry in CORPUS["entries"]:
            intent = entry.get("documented_intent")
            if intent is None:
                continue
            with self.subTest(entry=entry["name"]):
                self.assertTrue(intent.get("reason"), "documented_intent.reason must not be empty")
                self.assertTrue(
                    intent.get("po_decision"), "documented_intent.po_decision must not be empty",
                )
                self.assertTrue(
                    intent.get("work_item"), "documented_intent.work_item must not be empty",
                )


class CommonmarkCorpusDifferentialTest(unittest.TestCase):
    """Replays every corpus entry against the LIVE script and compares its
    findings to the frozen `expected_check_n_findings` — this is the actual
    adversarial round, re-run fresh every time the suite runs.
    """

    def test_every_corpus_entry_is_exercised_against_the_live_script(self):
        """The resolution-proof this round's brief demands: an entry that
        silently never reached an assertion would look identical to one that
        passed. `exercised` is populated inside the SAME loop that asserts,
        so a `continue`/typo that skipped an entry shows up as a count
        mismatch here, not as a suite that quietly ran fewer checks than the
        fixture promises.
        """
        exercised = []
        mismatches = []
        for entry in CORPUS["entries"]:
            exercised.append(entry["name"])
            actual = run_memory_lint_on(entry["markdown"])
            expected = sorted(entry["expected_check_n_findings"])
            if actual != expected:
                mismatches.append((entry["name"], expected, actual))

        self.assertEqual(
            len(exercised), CORPUS["entry_count"],
            f"exercised {len(exercised)} of {CORPUS['entry_count']} declared "
            f"corpus entries — the loop skipped some",
        )
        self.assertEqual(
            sorted(exercised), sorted(_ENTRY_NAMES),
            "the set of exercised entries does not match the fixture's own name list",
        )
        self.assertEqual(
            mismatches, [],
            "live memory-lint.sh diverged from the frozen expectation for "
            "these corpus entries (name, expected, actual):\n" +
            "\n".join(f"  {n}: expected={exp!r} actual={act!r}" for n, exp, act in mismatches),
        )

    # --- Named showcases: the headline divergences, readable on their own ---
    # Same content the comprehensive loop above already covers — kept as
    # separate, documented methods (matching this suite's existing style,
    # e.g. the WI-0048 canonical-repro tests) so a reader scanning test names
    # sees the finding without opening the fixture JSON.

    def _entry(self, name):
        for entry in CORPUS["entries"]:
            if entry["name"] == name:
                return entry
        raise AssertionError(f"no such corpus entry: {name!r}")

    def test_an_escaped_link_is_not_reported_as_dead(self):
        """WI-0079, fixed: `\\[not a link\\](dead.md)` is literal text per
        CommonMark (the brackets are backslash-escaped) — WI-0005's briefing
        originally predicted this as a false positive (check (n)'s label/dest
        regex had no escape awareness and matched from the `[` right after
        the backslash anyway), and the two oracles now agree.
        """
        entry = self._entry("backslash_escaped_link_is_not_a_link")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, [])
        self.assertEqual(entry["reference_checkable_targets"], [])
        self.assertIsNone(entry["known_divergence"])

    def test_an_escaped_bracket_pair_does_not_hide_a_real_link_beside_it(self):
        """Neighbour fixture (WI-0079): the escape-awareness fix must reject
        exactly the escaped span, not the whole line — a live, unescaped link
        right next to a backslash-escaped non-link is still found."""
        entry = self._entry("backslash_escaped_bracket_pair_not_a_link_alongside_a_real_link")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-esc7.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-esc7.md"])
        self.assertIsNone(entry["known_divergence"])

    def test_nested_brackets_in_the_link_text_no_longer_hide_the_link(self):
        """WI-0080, fixed: `[a [b] c](dead.md)` is one ordinary link per
        CommonMark, but check (n)'s label regex `[^][]*` forbade ANY literal
        bracket inside the link text, nested or not, so it never matched the
        span at all. The regex is gone — a bracket-stack scanner now reads the
        label — and both oracles agree. The entry name still records the defect
        it was minted for (same convention as the WI-0082 entries below).
        """
        entry = self._entry("nested_brackets_in_link_text_simple")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-nb1.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-nb1.md"])
        self.assertIsNone(entry["known_divergence"])

    def test_nested_brackets_in_link_text_are_found_mid_paragraph_too(self):
        """WI-0080's second fixture: the same construct in running prose rather
        than a bullet item, so the closure is not pinned to list context."""
        entry = self._entry("nested_brackets_in_link_text_mid_sentence")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-esc2.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-esc2.md"])
        self.assertIsNone(entry["known_divergence"])

    def test_an_escaped_bracket_inside_the_link_text_no_longer_hides_the_link(self):
        """WI-0080's other trigger, same root cause: `[a\\]b](dead.md)`. The
        reference decodes the escape and reads the label as `a]b`; the old label
        class excluded `]` regardless of the preceding backslash. The scanner
        treats an escaped bracket as label CONTENT via is_escaped()."""
        entry = self._entry("backslash_escaped_bracket_in_link_text")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-esc5.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-esc5.md"])
        self.assertIsNone(entry["known_divergence"])

    def test_three_levels_of_nested_brackets_are_one_link(self):
        """WI-0080 depth pin. A repair that tolerated exactly one bracket pair
        would still pass the two entries above; this one discriminates a real
        stack from a special case."""
        entry = self._entry("nested_brackets_three_levels_in_link_text")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-nb3.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-nb3.md"])

    def test_an_unbalanced_closing_bracket_stays_silent(self):
        """WI-0080 negative pin: `[a] b](dead.md)` renders NO link at the
        reference — `[a]` closes on its own and the second `]` has no opener
        left. The obvious wrong repairs (widen the label class; split at the
        last `](`) all report the target here. This entry's value is that it
        stays EMPTY on both sides."""
        entry = self._entry("unbalanced_closing_bracket_is_not_a_link")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, [])
        self.assertEqual(entry["reference_checkable_targets"], [])

    def test_a_link_in_the_link_text_leaves_only_the_inner_link_and_later_ones(self):
        """CommonMark: "Links may not contain other links, at any level of
        nesting". The inner link wins, the outer opener is deactivated — and the
        deactivation must not swallow an independent link further along the same
        line (WI-0080)."""
        entry = self._entry("link_in_link_text_inner_wins_beside_a_later_link")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-nb5-inner.md", "dead-nb5-later.md"])
        self.assertEqual(
            entry["reference_checkable_targets"],
            ["dead-nb5-inner.md", "dead-nb5-later.md"],
        )

    def test_an_image_in_the_link_text_leaves_the_outer_link_live(self):
        """WI-0091, the badge shape `[![alt](badge.png)](target.md)`. Only a
        LINK in the link text disqualifies the enclosing link; an IMAGE does
        not. The image source is never a check (n) finding, so the reference
        column is the link target alone."""
        entry = self._entry("image_in_link_text_badge_pattern")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-img1.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-img1.md"])

    def test_two_nested_images_in_the_link_text_still_leave_one_link(self):
        """WI-0091 at depth: one link, two images, no image reported."""
        entry = self._entry("image_nested_two_deep_in_link_text")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-img2.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-img2.md"])

    def test_an_image_with_a_bracketed_alt_text_is_still_not_a_link(self):
        """WI-0091 negative pin: `![[a]](i.png)` is an image. The old code
        decided that on the byte before `[`; the scanner decides it on the
        opener it pushed, and must reach the same answer for an alt text the
        old label class could never have matched."""
        entry = self._entry("image_with_bracketed_alt_text_is_not_a_link")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, [])
        self.assertEqual(entry["reference_checkable_targets"], [])

    def test_a_resolving_reference_link_in_the_link_text_disqualifies_the_outer_link(self):
        """WI-0093. CommonMark's "no links in links" rule fires on any
        successful LINK, not only an inline one — `[outer [ref5] text](out.md)`
        with `[ref5]:` defined renders ONE link, to the definition's target, and
        the outer `](out.md)` is literal. The WI-0080 scanner deactivated
        enclosing openers only in its inline-destination branch and reported
        `out.md` too: a false positive the regex it replaced never produced."""
        entry = self._entry("shortcut_reference_in_link_text_disqualifies_outer")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-refdis1.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-refdis1.md"])
        self.assertIsNone(entry["known_divergence"])

    def test_a_reference_definition_after_its_use_still_disqualifies_the_outer_link(self):
        """WI-0093's architectural entry, and the reason check (n) reads each
        index TWICE: CommonMark collects reference definitions for the whole
        document before it parses any inline content, so a definition may stand
        after the link that uses it. A single pass cannot answer the rule at the
        moment it reaches the link."""
        entry = self._entry("reference_definition_after_its_use_still_disqualifies")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-refdis2.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-refdis2.md"])
        self.assertIsNone(entry["known_divergence"])

    def test_an_undefined_label_in_the_link_text_leaves_the_outer_link_alive(self):
        """The counter-entry that forbids the cheap repair for WI-0093.
        "Deactivate whenever no inline destination follows" would also kill
        `[a [b] c](t.md)`, WI-0080's central fixture. The only difference
        between the two is whether the inner label RESOLVES — here it does not,
        and this entry's value is that the outer link stays reported."""
        entry = self._entry("undefined_label_in_link_text_keeps_the_outer_link")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-refout3.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-refout3.md"])

    def test_a_failed_full_reference_leaves_the_outer_link_alive(self):
        """Measured, and NOT derivable from the spec text: in `[ref8][nosuch]`
        the FIRST label is defined, but the reference does not fall back to the
        shortcut reading — the failed full reference renders no link at all, so
        nothing is deactivated. The single shape an obvious WI-0093 repair gets
        wrong."""
        entry = self._entry("failed_full_reference_keeps_the_outer_link")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-refout5.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-refout5.md"])

    def test_a_reference_definition_inside_a_fence_defines_nothing(self):
        """A reference definition is a BLOCK construct: inside a fence it is
        code. Pins that WI-0093's label collection runs the same block machine
        as the extraction, rather than grepping the file for definition-shaped
        lines — a pre-scan would define `ref11` and wrongly silence the outer
        link."""
        entry = self._entry("reference_definition_inside_a_fence_defines_nothing")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-refout7.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-refout7.md"])

    def test_an_escaped_bracket_in_a_definition_label_is_still_a_definition(self):
        """WI-0094: the DEFINITION side of the label grammar WI-0080 fixed on
        the usage side. `[a\\]b]: dead-escdefn.md` is one definition at the
        reference; check (n) recognised definitions with `\\[[^][]+\\]:`, which
        excludes `]` regardless of a preceding backslash, so the line was not a
        definition at all and its target went unchecked."""
        entry = self._entry("backslash_escaped_bracket_in_reference_definition_label")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-escdefn.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-escdefn.md"])
        self.assertIsNone(entry["known_divergence"])

    def test_a_wrong_destination_span_no_longer_hides_the_real_link_inside_it(self):
        """WI-0095, CLOSED. protect_link_destinations() used to span the text
        after ANY `](`, live opener or not, and without an escape-parity test
        on the `]`; the WI-0080 scanner skips such a span WHOLESALE, so the
        real link inside a wrong span used to vanish. 4f2ffa7 found it,
        because its regex was blind to the span it scanned through. The fix
        gives protect_link_destinations() the same opener-stack + escape-parity
        scan process_link_line() already runs, so both fixtures now report the
        real link and agree with the reference on both oracles."""
        stray = self._entry("stray_close_bracket_paren_span_hides_a_later_link")
        escaped = self._entry("escaped_close_bracket_paren_span_hides_a_later_link")

        self.assertEqual(run_memory_lint_on(stray["markdown"]), ["dead-span1.md"])
        self.assertEqual(run_memory_lint_on(escaped["markdown"]), ["dead-span2.md"])
        self.assertEqual(stray["reference_checkable_targets"], ["dead-span1.md"])
        self.assertEqual(escaped["reference_checkable_targets"], ["dead-span2.md"])
        for entry in (stray, escaped):
            self.assertIsNone(entry["known_divergence"])

    def test_a_stray_sentinel_byte_swallows_the_link_that_follows_it(self):
        """WI-0097, an OPEN divergence in the same family the now-closed
        WI-0095 belonged to: a span that should not exist, skipped as a unit.
        A literal 0x03 byte in the source is read as the OPENING sentinel of a
        protected destination and pairs with the one opening the next real
        destination, so the link between them disappears. Pathological input,
        false-negative direction, left open rather than fixed in the round
        that measured it — the WI-0095 fix closed the opener/escape gap in
        which SPAN this scan draws, not the WI-0097 gap in which BYTE it
        treats as the span delimiter."""
        entry = self._entry("stray_sentinel_byte_swallows_the_following_link")

        self.assertEqual(run_memory_lint_on(entry["markdown"]), [])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-stray1.md"])
        self.assertEqual(entry["known_divergence"]["direction"], "false-negative")
        self.assertEqual(entry["known_divergence"]["work_item"], "WI-0097")

    def test_a_definition_line_that_cannot_interrupt_a_paragraph_is_not_reported(self):
        """WI-0096, fixed (PO decision 24.08.2026). A link reference definition
        may not interrupt a paragraph, so with prose open above it the
        reference reads the line as ordinary text and renders no link for it.
        check (n) used to report its target anyway — the last false positive in
        the corpus. It now asks the paragraph buffer the same question and
        stays silent; only the OUTER link, which the refmap never treated as
        defined either, is reported. The entry name still records the defect it
        was minted for.

        This is NOT the WI-0085 decision one shape further along, which is why
        the two verdicts differ on the same bytes: the deciding question is
        what the reader sees. WI-0085's lone definition renders as
        nothing, so its dead pointer is invisible and worth reporting; here the
        very same bytes render as visible paragraph prose."""
        entry = self._entry("reference_definition_cannot_interrupt_a_paragraph")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-refout8.md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-refout8.md"])
        self.assertIsNone(
            entry["known_divergence"],
            "the entry must no longer carry a known_divergence — a fixed "
            "divergence that keeps its block would leave the corpus claiming "
            "a false positive this round removed",
        )
        self.assertIsNone(entry.get("documented_intent"))

    def test_a_label_without_a_non_whitespace_character_is_no_definition(self):
        """The sibling of WI-0096, measured 24.08.2026 and answered by the same
        rule through a DIFFERENT gate. A link label needs at least one
        non-whitespace character, so neither `[ ]:` nor `[]:` opens a reference
        definition and the reference renders both lines as visible paragraph
        text — the WI-0096 verdict (prose on the page, not a pointer), not the
        WI-0085 one (a declared destination that renders as nothing).

        check (n) already agreed before this round, but silently and untested;
        it does so through `reflbl != ""` in the definition branch and not
        through the paragraph-buffer gate WI-0096 added. Measured both ways:
        with the paragraph gate removed these two stay silent, with
        `reflbl != ""` removed they report their targets. Pinning it here is
        what turns an incidental agreement into a claim."""
        ws = self._entry("whitespace_only_label_is_not_a_reference_definition")
        empty = self._entry("empty_label_is_not_a_reference_definition")

        for entry in (ws, empty):
            with self.subTest(entry=entry["name"]):
                self.assertEqual(run_memory_lint_on(entry["markdown"]), [])
                self.assertEqual(entry["reference_checkable_targets"], [])
                self.assertIsNone(entry["known_divergence"])
                self.assertIsNone(entry.get("documented_intent"))

    def test_the_label_collision_class_has_two_accumulation_points(self):
        """WI-0098, the whole class rather than the one shape it was minted on
        (measured 24.08.2026). check (n) keys reference labels by their
        RESOLVED shape, and that mapping is not injective: distinct raw labels
        share a key, and once a definition owns that key every other label
        collapsing to it reads as a resolving reference and silences the link
        around it.

        Two accumulation points, three routes measured here:

          * the EMPTY key, reached by a literal `[]` and by a whitespace-only
            `[   ]`. Wider than the code-span shape the class was found on,
            because the REFERENCE never looks an empty label up at all.
          * the `boundary` key, reached by any label that is exactly one closed
            inline comment — `<!--a-->` and `<!--b-->` share nothing else and
            are still interchangeable. No empty label is involved, which is why
            the class is stated as non-injectivity and not as "the empty
            label".

        Each divergent entry is paired with a control carrying the SAME label
        and NO colliding definition, where the outer link IS reported. Without
        those the entries would be equally consistent with "such a label
        silences the link", which is not what happens."""
        collisions = (
            ("literal_empty_label_in_link_text_collides_with_a_definition",
             ["dead-empty-defn.md"]),
            ("whitespace_only_label_in_link_text_collides_with_a_definition",
             ["dead-wslabel-defn.md"]),
            ("boundary_labels_from_two_different_comments_collide",
             ["dead-boundary-defn.md"]),
        )
        for name, expected in collisions:
            entry = self._entry(name)
            with self.subTest(entry=name):
                self.assertEqual(run_memory_lint_on(entry["markdown"]), expected)
                self.assertEqual(entry["known_divergence"]["direction"], "false-negative")
                self.assertEqual(entry["known_divergence"]["work_item"], "WI-0098")
                # The reference renders the outer link the scanner drops.
                self.assertEqual(len(entry["reference_checkable_targets"]), 2)

        controls = (
            ("literal_empty_label_in_link_text_without_a_definition_control",
             ["dead-empty-ctl.md"]),
            ("whitespace_only_label_in_link_text_without_a_definition_control",
             ["dead-wslabel-ctl.md"]),
            ("comment_label_in_link_text_without_a_definition_control",
             ["dead-boundary-ctl.md"]),
        )
        for name, expected in controls:
            entry = self._entry(name)
            with self.subTest(control=name):
                self.assertEqual(run_memory_lint_on(entry["markdown"]), expected)
                self.assertEqual(entry["reference_checkable_targets"], expected)
                self.assertIsNone(entry["known_divergence"])

    def test_a_setext_heading_underline_is_a_recognised_block_boundary(self):
        """WI-0082, fixed: a setext-heading underline (`===`) used to be absent
        from check (n)'s block-boundary list, so the heading text and the
        following paragraph merged into one buffer and an unpaired backtick in
        each paired across the merge, swallowing the first link as a spurious
        code span. The underline is now a boundary and both links are reported,
        matching the reference. The entry name still records the defect it was
        minted for.
        """
        entry = self._entry("setext_heading_swallows_link_via_missing_boundary")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-setext-e.md", "dead-setext-f.md"])
        self.assertEqual(
            entry["reference_checkable_targets"],
            ["dead-setext-e.md", "dead-setext-f.md"],
        )
        self.assertIsNone(entry["known_divergence"])

    def test_a_thematic_break_is_a_recognised_block_boundary(self):
        """Same defect class as the setext case, triggered by a thematic
        break (`***`) instead — closed by the same WI-0082 change."""
        entry = self._entry("thematic_break_swallows_link_via_missing_boundary")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-tb-a.md", "dead-tb-b.md"])
        self.assertEqual(
            entry["reference_checkable_targets"],
            ["dead-tb-a.md", "dead-tb-b.md"],
        )
        self.assertIsNone(entry["known_divergence"])

    def test_multiline_reference_definition_is_invisible_to_check_n(self):
        """New this round: `[ref]:` followed by its destination on the NEXT
        physical line is a valid CommonMark reference definition, but
        `reference_definition_tail()` is invoked with an empty `raw_rest` on
        the definition line itself and returns false — the destination line
        and the `[text][ref]` usage line are both ordinary prose to check (n).
        The single-line control (same reference-style link, destination on
        the SAME line) IS found, isolating the defect to the multiline case
        specifically.
        """
        multiline = self._entry("multiline_reference_definition_target_on_next_line")
        control = self._entry("singleline_reference_definition_control")

        self.assertEqual(run_memory_lint_on(multiline["markdown"]), [])
        self.assertEqual(
            run_memory_lint_on(control["markdown"]), ["dead-refdef-single.md"],
        )

    def test_a_named_entity_in_a_destination_is_filed_as_info_not_claimed_dead(self):
        """CommonMark decodes `&num;` to `#` inside a link destination; check
        (n) deliberately leaves NAMED entities undecoded (WI-0081) rather
        than building the full ~2000-entry CommonMark named-entity table for
        a construct measured at zero occurrences in the field. WI-0081
        (remainder), fixed 23.08.2026: resolving and reporting the raw,
        undecoded text as dead used to claim a verdict check (n) cannot
        back — the decoded target may well exist. Filed as info instead,
        absent from both Errors and Warnings.
        """
        named = self._entry("entity_reference_named_in_destination")

        self.assertEqual(run_memory_lint_on(named["markdown"]), [])
        self.assertEqual(named["reference_checkable_targets"], ["dead#3-ent2.md"])

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "project"
            (project_dir / "docs" / "memory").mkdir(parents=True)
            (project_dir / "docs" / "memory" / "MEMORY.md").write_text(
                "# Memory Index\n\n" + named["markdown"], encoding="utf-8"
            )
            fake_home = Path(tmp) / "home"
            fake_home.mkdir()
            result = subprocess.run(
                ["bash", str(SCRIPT_PATH), str(project_dir)],
                capture_output=True, text=True,
                env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            )
        self.assertIn("dead&num;3-ent2.md", result.stdout)
        self.assertIn("## Info (1)", result.stdout)

    def test_numeric_entities_in_a_destination_are_decoded_before_resolving(self):
        """WI-0081, fixed: `&#35;` (decimal) and `&#x23;` (hex) both decode to
        `#` at the reference. check (n) used to resolve the raw, undecoded
        text, and its own shell-side fragment-stripping (`${target%%#*}`)
        additionally cut at the entity's own literal `#` byte — the two
        oracles now agree for both spellings.
        """
        decimal = self._entry("entity_reference_decimal_in_destination")
        hexform = self._entry("entity_reference_hex_in_destination")

        self.assertEqual(run_memory_lint_on(decimal["markdown"]), ["dead#3-ent3.md"])
        self.assertEqual(decimal["reference_checkable_targets"], ["dead#3-ent3.md"])
        self.assertIsNone(decimal["known_divergence"])

        self.assertEqual(run_memory_lint_on(hexform["markdown"]), ["dead#3-ent4.md"])
        self.assertEqual(hexform["reference_checkable_targets"], ["dead#3-ent4.md"])
        self.assertIsNone(hexform["known_divergence"])

    # --- WI-0005 round 2 (22.08.2026-23.08.2026): new construct classes ----

    def test_an_indented_code_block_is_not_a_link(self):
        """WI-0084, fixed: a line indented >=4 spaces (or one tab), surrounded
        by blank lines, is a CommonMark indented code block -- its content is
        never inline-parsed. check (n) now carries a block-boundary case for
        this (recomputed per line off pbuf_n == 0, memory-lint.sh), so the
        bracketed text inside is no longer extracted at all -- the two
        oracles agree.
        """
        four_space = self._entry("indented_code_block_four_spaces")
        tab = self._entry("indented_code_block_tab_indent")

        self.assertEqual(run_memory_lint_on(four_space["markdown"]), [])
        self.assertEqual(four_space["reference_checkable_targets"], [])
        self.assertIsNone(four_space["known_divergence"])

        self.assertEqual(run_memory_lint_on(tab["markdown"]), [])
        self.assertEqual(tab["reference_checkable_targets"], [])
        self.assertIsNone(tab["known_divergence"])

    def test_an_html_block_other_than_a_comment_is_not_checked_as_html(self):
        """WI-0084, fixed: check (n) used to recognise only `<!--` as an
        HTML-block opener (WI-0041). It now also tracks HTML block type 1
        (script/pre/style, closes on a matching closing tag anywhere in a
        later line) and type 6 (div and the rest of the CommonMark "common
        block tag" list, closes at the next blank line) -- both copied from
        the pinned reference implementation itself, not the abstract spec
        text. The bracketed text inside each is no longer extracted.
        """
        div = self._entry("html_block_div_tag")
        pre = self._entry("html_block_pre_tag")
        script = self._entry("html_block_script_tag")

        self.assertEqual(run_memory_lint_on(div["markdown"]), [])
        self.assertEqual(div["reference_checkable_targets"], [])
        self.assertIsNone(div["known_divergence"])
        self.assertEqual(run_memory_lint_on(pre["markdown"]), [])
        self.assertEqual(pre["reference_checkable_targets"], [])
        self.assertIsNone(pre["known_divergence"])
        self.assertEqual(run_memory_lint_on(script["markdown"]), [])
        self.assertEqual(script["reference_checkable_targets"], [])
        self.assertIsNone(script["known_divergence"])

    def test_an_unused_reference_definition_is_checked_anyway(self):
        """check (n)'s reference-definition branch checks a `[id]: target`
        destination straight off the definition line, unconditionally -- it
        never looks for a matching `[id]` usage anywhere else in the file. A
        definition with no usage at all renders NOTHING at the reference (a
        lone definition produces no `<a href>`), but check (n) reports it as
        a dead target regardless. This is also why the shortcut/collapsed
        reference-link fixtures below happen to agree with the reference:
        check (n) never resolves the usage, it only ever reads the
        definition line.

        WI-0085 (23.08.2026): the PO decided this divergence is INTENDED, not
        a bug -- an unused definition addressing a deleted file is a dead
        POINTER that renders as nothing and is invisible on a normal read,
        exactly the failure mode this check exists to catch even though
        CommonMark itself renders no link. Both entries carry
        `documented_intent` instead of `known_divergence` now; this test's
        own behavioural assertions are unchanged, only the classification is.
        """
        standalone = self._entry("unused_reference_definition_standalone")
        after_prose = self._entry("unused_reference_definition_after_prose")

        self.assertEqual(run_memory_lint_on(standalone["markdown"]), ["dead-unused1.md"])
        self.assertEqual(standalone["reference_checkable_targets"], [])
        self.assertIsNone(standalone["known_divergence"])
        self.assertIsNotNone(standalone["documented_intent"])
        self.assertEqual(standalone["documented_intent"]["work_item"], "WI-0085")

        self.assertEqual(run_memory_lint_on(after_prose["markdown"]), ["dead-unused2.md"])
        self.assertEqual(after_prose["reference_checkable_targets"], [])
        self.assertIsNone(after_prose["known_divergence"])
        self.assertIsNotNone(after_prose["documented_intent"])
        self.assertEqual(after_prose["documented_intent"]["work_item"], "WI-0085")

    def test_a_crlf_blank_line_is_a_recognised_block_boundary(self):
        """WI-0086, fixed: check (n)'s blank-line boundary test is
        `$0 ~ /^[ \\t]*$/`. On a CRLF-terminated file, awk splits records on
        `\\n` and used to leave a bare `\\r` as a blank line's `$0` -- which
        this regex does not match. The paragraph buffer never flushed at that
        blank line, two paragraphs merged into one buffer, and a stray
        backtick in each (each meant to stay unpaired within its own
        block) paired across the merge, swallowing the first paragraph's
        link as a spurious code span. The record now has its trailing
        carriage return stripped before any boundary test runs, so both
        links are reported. The control fixture (same CRLF shape, no stray
        backticks) was green before the fix too, and stays green: this was
        specifically a missing-boundary defect, not CRLF handling breaking
        wholesale.
        """
        swallowed = self._entry("crlf_blank_line_swallows_link_via_missing_boundary")
        control = self._entry("crlf_two_paragraphs_no_confounding_span_control")

        self.assertEqual(
            run_memory_lint_on(swallowed["markdown"]),
            ["dead-crlf-c.md", "dead-crlf-d.md"],
        )
        self.assertIsNone(swallowed["known_divergence"])
        self.assertEqual(
            swallowed["reference_checkable_targets"],
            ["dead-crlf-c.md", "dead-crlf-d.md"],
        )
        self.assertEqual(
            run_memory_lint_on(control["markdown"]),
            ["dead-crlf-a.md", "dead-crlf-b.md"],
        )
        self.assertEqual(
            control["reference_checkable_targets"],
            ["dead-crlf-a.md", "dead-crlf-b.md"],
        )

    def test_an_escaped_paren_in_a_destination_resolves_the_full_target(self):
        """WI-0081, fixed: `[x](dead-esc4\\).md)` — the reference decodes the
        escape (href `dead-esc4).md`, one real link). check (n)'s
        destination capture used to stop at the first literal `)` regardless
        of a preceding backslash, resolving only the truncated `dead-esc4\\`.
        """
        entry = self._entry("backslash_escaped_paren_in_destination")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-esc4).md"])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-esc4).md"])
        self.assertIsNone(entry["known_divergence"])


class MutationProvesTheDifferentialTestCanFail(unittest.TestCase):
    """WI-0005 obligation: the new differential test must have been seen RED
    at least once, by mutation, not merely written and never falsified.

    Mutates a documented exception (the external-scheme/mailto/in-page-anchor
    skip, `http://*|https://*|mailto:*|\\#*) continue ;;`) on an in-memory
    COPY of the script — the same pattern
    test_run_lint_precondition_fails_loudly_on_a_script_that_cannot_parse()
    in test_memory_lint.py already uses — so the shipped script on disk is
    never touched at all; there is nothing to restore. The corpus's own
    `external_scheme_and_anchor_stay_excluded_alongside_a_real_dead_link`
    entry is the fixture this mutation flips: removing the exclusion makes
    check (n) additionally report the external-scheme target as dead,
    changing its finding count from 1 to 2.
    """

    _MUTATION_TARGET = "            http://*|https://*|mailto:*|\\#*) continue ;;\n"

    def test_removing_the_external_scheme_exclusion_flips_the_control_fixture_red(self):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        original_md5_before = __import__("hashlib").md5(original.encode("utf-8")).hexdigest()

        self.assertIn(
            self._MUTATION_TARGET, original,
            "fixture line moved — update the mutation target for this test",
        )
        mutated = original.replace(self._MUTATION_TARGET, "", 1)
        self.assertNotEqual(mutated, original, "mutation did not change the script")

        entry = None
        for e in CORPUS["entries"]:
            if e["name"] == "external_scheme_and_anchor_stay_excluded_alongside_a_real_dead_link":
                entry = e
        self.assertIsNotNone(entry, "control fixture entry missing from the corpus")

        # Sanity: the UNMUTATED script must pass this fixture first, or the
        # mutation below would not prove anything about THIS defect.
        clean_findings = run_memory_lint_on(entry["markdown"])
        self.assertEqual(clean_findings, entry["expected_check_n_findings"])

        with tempfile.TemporaryDirectory() as tmp:
            script_dir = Path(tmp) / "scriptdir"
            import shutil
            shutil.copytree(SCRIPT_PATH.parent / "lib", script_dir / "lib")
            mutant_script = script_dir / "memory-lint.sh"
            mutant_script.write_text(mutated, encoding="utf-8")

            mutant_findings = run_memory_lint_on(entry["markdown"], script_path=mutant_script)

        self.assertNotEqual(
            mutant_findings, entry["expected_check_n_findings"],
            "mutation did not flip the control fixture — the mutation target "
            "no longer discriminates this exclusion",
        )
        self.assertIn("https://example.invalid/dead-ext.md", mutant_findings)

        # The real script on disk was never touched — proven by md5, not assumed.
        after = SCRIPT_PATH.read_text(encoding="utf-8")
        original_md5_after = __import__("hashlib").md5(after.encode("utf-8")).hexdigest()
        self.assertEqual(original_md5_before, original_md5_after)
        self.assertEqual(after, original)


class GeneratorDocumentedIntentValidationTest(unittest.TestCase):
    """WI-0086: `generate_commonmark_corpus.py`'s `main()` now classifies
    every corpus entry's oracle comparison into one of three outcomes —
    match, `known_divergence` (an open gap in check (n)), or
    `documented_intent` (WI-0085: a disagreement the PO decided is
    deliberate) — and refuses to write a fixture whenever an entry's
    `known_divergence`/`documented_intent` fields do not match what the two
    oracles actually measured. This class proves each of the three new
    refusal branches the `documented_intent` field added:

      1. `documented_intent` claimed but the oracles now AGREE (a stale or
         unclaimed intent).
      2. `known_divergence` AND `documented_intent` both present on one
         entry (a contradiction — exactly one may explain a disagreement).
      3. Neither block present but the oracles DISAGREE (an undocumented,
         newly-introduced divergence) — the pre-existing branch, now
         sharing its message with the new field.

    Each test runs a COPY of the real generator, its `CORPUS` list swapped
    for a single synthetic entry built for that scenario — the real corpus
    (65 entries as of WI-0093) is already exercised by
    CommonmarkCorpusDifferentialTest / FixtureIntegrityTest above; re-running
    every entry three more times here would triple this module's real
    `bash`-subprocess cost for no additional coverage. The count is prose, not
    an assertion — FixtureIntegrityTest owns the real one. Never the checked-in generator or fixture — proven
    by md5 before/after, same discipline
    MutationProvesTheDifferentialTestCanFail above uses for the shell
    script.

    Each test ALSO proves it can fail: removing the specific validation
    branch under test from the copy makes the SAME synthetic entry pass
    silently (exit 0, a fixture gets written) instead of being refused
    (exit 1) — mutation of the generator's own logic, not a removed
    assertion.
    """

    _CORPUS_BLOCK_RE = re.compile(r"^CORPUS = \[.*?^\]\n", re.S | re.M)

    _BOTH_BLOCKS_GUARD = (
        '        if claims_divergence and claims_intent:\n'
        '            problems.append(\n'
        '                f"{entry[\'name\']}: carries BOTH known_divergence and "\n'
        '                f"documented_intent — pick exactly one (an open gap in "\n'
        '                f"check (n) vs. a deliberate PO decision) or the fixture "\n'
        '                f"cannot tell which explanation applies"\n'
        '            )\n'
    )
    _INTENT_AGREES_GUARD = (
        '        if claims_intent and not actually_diverges:\n'
        '            problems.append(\n'
        "                f\"{entry['name']}: documented_intent claimed but the two \"\n"
        '                f"oracles AGREE (reference={expected_reference_targets!r}, "\n'
        '                f"check(n)={observed_check_n_findings!r}) — remove the claim, "\n'
        '                f"there is no longer a disagreement for the PO decision to "\n'
        '                f"cover"\n'
        '            )\n'
    )
    _NEITHER_BLOCK_GUARD = (
        '        if not claims_divergence and not claims_intent and actually_diverges:\n'
        '            problems.append(\n'
        "                f\"{entry['name']}: no known_divergence or documented_intent \"\n"
        '                f"recorded but the two oracles DISAGREE "\n'
        '                f"(reference={expected_reference_targets!r}, "\n'
        '                f"check(n)={observed_check_n_findings!r}) — this is a NEW, "\n'
        '                f"previously unrecorded divergence; add a known_divergence "\n'
        '                f"block (an open gap in check (n)) or a documented_intent "\n'
        '                f"block (a deliberate PO decision) before regenerating"\n'
        '            )\n'
    )

    _ENTRY_INTENT_AGREES = {
        "name": "synthetic_intent_agrees",
        "category": "synthetic",
        "markdown": "[x](dead-agree-test.md)\n",
        "known_divergence": None,
        "documented_intent": {
            "reason": "synthetic fixture for GeneratorDocumentedIntentValidationTest",
            "po_decision": "23.08.2026",
            "work_item": "WI-TEST",
        },
    }
    _ENTRY_BOTH_BLOCKS = {
        "name": "synthetic_both_blocks",
        "category": "synthetic",
        # A genuine divergence is needed here: actually_diverges must be True
        # so that only the "both blocks present" guard, and not the "claims a
        # divergence that doesn't exist" guards, can be the one that fires.
        # A NAMED entity in the destination is the construct used for it (see
        # entity_reference_named_in_destination in the real CORPUS, which
        # carries the same known_divergence/WI-0081 classification; the extra
        # documented_intent block below is what makes this fixture synthetic,
        # and is the whole scenario under test) — check (n)
        # deliberately does not decode the ~2000-entry named-entity table and
        # files such a target as Info instead, so the reference sees a link and
        # the differential's errors/warnings view sees nothing. It replaced the
        # nested-bracket construct this fixture used until 23.08.2026, which
        # WI-0080 closed: the two oracles agree on it now, and a synthetic
        # fixture that no longer reproduces a divergence tests nothing.
        "markdown": "[x](dead-both&num;3.md) — named entity in destination\n",
        "known_divergence": {
            "direction": "false-negative",
            "reason": "synthetic fixture for GeneratorDocumentedIntentValidationTest",
            "work_item": "WI-0081",
        },
        "documented_intent": {
            "reason": "synthetic fixture for GeneratorDocumentedIntentValidationTest",
            "po_decision": "23.08.2026",
            "work_item": "WI-TEST",
        },
    }
    _ENTRY_NEITHER_BLOCK = {
        "name": "synthetic_neither_block",
        "category": "synthetic",
        # Same divergent construct as above (named entity in the destination),
        # minus both explanation blocks — no "documented_intent" key at all,
        # mirroring how most real CORPUS entries never carry the key
        # (entry.get(), not entry[...]).
        "markdown": "[x](dead-newgap&num;3.md)\n",
        "known_divergence": None,
    }

    def _run_generator_copy(self, generator_source, corpus_entries):
        """Writes `generator_source` with its CORPUS list swapped for
        `corpus_entries` into an isolated scratch tree (mirrored one level
        deep so the copy's own `parents[3]`-based REPO_ROOT/SCRIPT_PATH
        resolution still lands on a real `memory-lint.sh` + `lib/`), and
        runs it with the SAME Python interpreter this test suite runs
        under."""
        corpus_source = f"CORPUS = {corpus_entries!r}\n"
        mutated = self._CORPUS_BLOCK_RE.sub(lambda m: corpus_source, generator_source, count=1)

        with tempfile.TemporaryDirectory() as tmp:
            scratch_root = Path(tmp) / "repo"
            fixtures_dir = scratch_root / "scripts" / "tests" / "fixtures"
            fixtures_dir.mkdir(parents=True)
            shutil.copy(SCRIPT_PATH, scratch_root / "scripts" / "memory-lint.sh")
            shutil.copytree(SCRIPT_PATH.parent / "lib", scratch_root / "scripts" / "lib")
            generator_copy = fixtures_dir / "generate_commonmark_corpus.py"
            generator_copy.write_text(mutated, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(generator_copy)],
                capture_output=True, text=True,
            )

    def _assert_generator_disk_copy_untouched(self, original_source, original_md5):
        after = GENERATOR_PATH.read_text(encoding="utf-8")
        self.assertEqual(after, original_source)
        self.assertEqual(
            hashlib.md5(after.encode("utf-8")).hexdigest(), original_md5,
            "the checked-in generator was modified by this test run",
        )

    def _assert_scenario(self, entry, guard, expected_message_fragment):
        source = GENERATOR_PATH.read_text(encoding="utf-8")
        original_md5 = hashlib.md5(source.encode("utf-8")).hexdigest()

        clean = self._run_generator_copy(source, [entry])
        self.assertEqual(
            clean.returncode, 1,
            f"expected the generator to refuse this entry, stdout="
            f"{clean.stdout!r} stderr={clean.stderr!r}",
        )
        self.assertIn(expected_message_fragment, clean.stderr)

        # Mutation proof: the guard text must be present verbatim (or this
        # test would falsely pass with a guard that moved/changed shape),
        # and removing it must make the SAME entry pass silently.
        self.assertIn(guard, source, "guard text moved — update this test")
        mutated_source = source.replace(guard, "", 1)
        self.assertNotEqual(mutated_source, source)

        mutant = self._run_generator_copy(mutated_source, [entry])
        self.assertEqual(
            mutant.returncode, 0,
            f"removing the guard should make the generator accept this "
            f"entry silently, but it still refused: {mutant.stderr!r}",
        )

        self._assert_generator_disk_copy_untouched(source, original_md5)

    def test_documented_intent_claimed_but_oracles_agree_is_refused(self):
        self._assert_scenario(
            self._ENTRY_INTENT_AGREES,
            self._INTENT_AGREES_GUARD,
            "synthetic_intent_agrees: documented_intent claimed but the two "
            "oracles AGREE",
        )

    def test_known_divergence_and_documented_intent_together_is_refused(self):
        self._assert_scenario(
            self._ENTRY_BOTH_BLOCKS,
            self._BOTH_BLOCKS_GUARD,
            "synthetic_both_blocks: carries BOTH known_divergence and "
            "documented_intent",
        )

    def test_neither_block_present_but_oracles_disagree_is_refused(self):
        self._assert_scenario(
            self._ENTRY_NEITHER_BLOCK,
            self._NEITHER_BLOCK_GUARD,
            "synthetic_neither_block: no known_divergence or "
            "documented_intent recorded but the two oracles DISAGREE",
        )


if __name__ == "__main__":
    unittest.main()
