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

Where the two disagree, the entry carries a `known_divergence` block
(direction, reason, work_item) and this test asserts the CURRENT (divergent)
behaviour — a frozen, visible snapshot, not a silent xfail. If the real
script's behaviour later drifts from that frozen snapshot in EITHER
direction (the bug gets fixed, or a different bug appears), the assertion
below fails and says so.
"""

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "memory-lint.sh"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "commonmark_corpus.json"

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

    def test_every_known_divergence_is_tagged_wi_0005(self):
        untagged = [
            e["name"] for e in CORPUS["entries"]
            if e["known_divergence"] is not None
            and e["known_divergence"].get("work_item") != "WI-0005"
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

    def test_known_divergence_presence_matches_the_frozen_oracle_disagreement(self):
        """The fixture's own internal contract: a `known_divergence` block is
        present IFF the two frozen oracle fields actually disagree. Catches a
        hand-edited fixture drifting from what the generator actually
        measured, without re-running either oracle."""
        for entry in CORPUS["entries"]:
            with self.subTest(entry=entry["name"]):
                oracles_disagree = (
                    sorted(entry["expected_check_n_findings"])
                    != sorted(entry["reference_checkable_targets"])
                )
                self.assertEqual(
                    entry["known_divergence"] is not None, oracles_disagree,
                    f"known_divergence presence ({entry['known_divergence'] is not None}) "
                    f"does not match oracle disagreement ({oracles_disagree}) for "
                    f"{entry['name']!r}",
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

    def test_predicted_false_negative_nested_brackets_in_link_text_are_not_matched(self):
        """WI-0005 briefing's second prediction, confirmed: `[a [b] c](dead.md)`
        is one ordinary link per CommonMark, but check (n)'s label regex
        `[^][]*` forbids ANY literal bracket inside the text, nested or not,
        so it never matches this span at all.
        """
        entry = self._entry("nested_brackets_in_link_text_simple")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, [])
        self.assertEqual(entry["reference_checkable_targets"], ["dead-nb1.md"])

    def test_setext_heading_underline_is_not_a_recognised_block_boundary(self):
        """New this round: a setext-heading underline (`===`) is absent from
        check (n)'s block-boundary list (blank line / list marker / ATX
        heading / fence / block HTML comment). The heading text and the
        following paragraph merge into one buffer, and an unpaired backtick
        in the heading pairs across the merge with one in the next paragraph,
        swallowing the first link as a spurious code span.
        """
        entry = self._entry("setext_heading_swallows_link_via_missing_boundary")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-setext-f.md"])
        self.assertEqual(
            entry["reference_checkable_targets"],
            ["dead-setext-e.md", "dead-setext-f.md"],
        )

    def test_thematic_break_is_not_a_recognised_block_boundary(self):
        """Same defect class as the setext case, triggered by a thematic
        break (`***`) instead."""
        entry = self._entry("thematic_break_swallows_link_via_missing_boundary")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-tb-b.md"])
        self.assertEqual(
            entry["reference_checkable_targets"],
            ["dead-tb-a.md", "dead-tb-b.md"],
        )

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

    def test_a_named_entity_in_a_destination_is_checked_undecoded(self):
        """CommonMark decodes `&num;` to `#` inside a link destination; check
        (n) deliberately leaves NAMED entities undecoded (WI-0081) rather
        than building the full ~2000-entry CommonMark named-entity table for
        a construct measured at zero occurrences in the field — the raw text
        is checked as-is, not further garbled.
        """
        named = self._entry("entity_reference_named_in_destination")

        self.assertEqual(run_memory_lint_on(named["markdown"]), ["dead&num;3-ent2.md"])
        self.assertEqual(named["reference_checkable_targets"], ["dead#3-ent2.md"])

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
        """New this round: a line indented >=4 spaces (or one tab),
        surrounded by blank lines, is a CommonMark indented code block --
        its content is never inline-parsed. check (n)'s block-boundary list
        has no case for this, so the line falls through to ordinary
        paragraph content and the bracketed text inside is reported dead.
        """
        four_space = self._entry("indented_code_block_four_spaces")
        tab = self._entry("indented_code_block_tab_indent")

        self.assertEqual(run_memory_lint_on(four_space["markdown"]), ["dead-ind1.md"])
        self.assertEqual(four_space["reference_checkable_targets"], [])

        self.assertEqual(run_memory_lint_on(tab["markdown"]), ["dead-ind2.md"])
        self.assertEqual(tab["reference_checkable_targets"], [])

    def test_an_html_block_other_than_a_comment_is_not_checked_as_html(self):
        """New this round: check (n) only recognises `<!--` as an HTML-block
        opener (WI-0041). Every other block-level tag (`<div>`, `<pre>`,
        `<script>`, ...) opens a CommonMark HTML block whose content is raw,
        unparsed HTML -- but check (n) treats it as ordinary paragraph
        prose and reports the bracketed text inside as a dead link.
        """
        div = self._entry("html_block_div_tag")
        pre = self._entry("html_block_pre_tag")
        script = self._entry("html_block_script_tag")

        self.assertEqual(run_memory_lint_on(div["markdown"]), ["dead-html1.md"])
        self.assertEqual(div["reference_checkable_targets"], [])
        self.assertEqual(run_memory_lint_on(pre["markdown"]), ["dead-html2.md"])
        self.assertEqual(pre["reference_checkable_targets"], [])
        self.assertEqual(run_memory_lint_on(script["markdown"]), ["dead-html3.md"])
        self.assertEqual(script["reference_checkable_targets"], [])

    def test_an_unused_reference_definition_is_checked_anyway(self):
        """New this round: check (n)'s reference-definition branch checks a
        `[id]: target` destination straight off the definition line,
        unconditionally -- it never looks for a matching `[id]` usage
        anywhere else in the file. A definition with no usage at all
        renders NOTHING at the reference (a lone definition produces no
        `<a href>`), but check (n) reports it as a dead target regardless.
        This is also why the shortcut/collapsed reference-link fixtures
        below happen to agree with the reference: check (n) never resolves
        the usage, it only ever reads the definition line.
        """
        standalone = self._entry("unused_reference_definition_standalone")
        after_prose = self._entry("unused_reference_definition_after_prose")

        self.assertEqual(run_memory_lint_on(standalone["markdown"]), ["dead-unused1.md"])
        self.assertEqual(standalone["reference_checkable_targets"], [])
        self.assertEqual(run_memory_lint_on(after_prose["markdown"]), ["dead-unused2.md"])
        self.assertEqual(after_prose["reference_checkable_targets"], [])

    def test_a_crlf_blank_line_is_not_a_recognised_block_boundary(self):
        """New this round: check (n)'s blank-line boundary test is
        `$0 ~ /^[ \\t]*$/`. On a CRLF-terminated file, awk splits records on
        `\\n` and leaves a bare `\\r` as a blank line's `$0` -- which this
        regex does not match. The paragraph buffer never flushes at that
        blank line, two paragraphs merge into one buffer, and a stray
        backtick in each (each meant to stay unpaired within its own
        block) pairs across the merge, swallowing the first paragraph's
        link as a spurious code span. The control fixture (same CRLF
        shape, no stray backticks) shows this is specifically a missing-
        boundary defect, not CRLF handling breaking wholesale.
        """
        swallowed = self._entry("crlf_blank_line_swallows_link_via_missing_boundary")
        control = self._entry("crlf_two_paragraphs_no_confounding_span_control")

        self.assertEqual(run_memory_lint_on(swallowed["markdown"]), ["dead-crlf-d.md"])
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


if __name__ == "__main__":
    unittest.main()
