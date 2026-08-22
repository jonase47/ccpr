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

    def test_predicted_false_positive_an_escaped_link_is_reported_as_dead(self):
        """WI-0005 briefing's first prediction, confirmed: `\\[not a
        link\\](dead.md)` is literal text per CommonMark (the brackets are
        backslash-escaped), but check (n)'s label/dest regex has no escape
        awareness and matches from the `[` right after the backslash anyway.
        """
        entry = self._entry("backslash_escaped_link_is_not_a_link")
        findings = run_memory_lint_on(entry["markdown"])

        self.assertEqual(findings, ["dead-esc1.md"])
        self.assertEqual(entry["reference_checkable_targets"], [])

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

    def test_entity_reference_in_a_destination_is_checked_undecoded(self):
        """New this round: CommonMark decodes `&num;`/`&#35;` to `#` inside a
        link destination; check (n) never decodes entities and resolves the
        raw text instead. The decimal form additionally contains a literal
        `#` byte in its own syntax, which the shell-side fragment-stripping
        (`${target%%#*}`) then truncates on — a different, more severely
        garbled path than the named-entity sibling.
        """
        named = self._entry("entity_reference_named_in_destination")
        decimal = self._entry("entity_reference_decimal_in_destination")

        self.assertEqual(run_memory_lint_on(named["markdown"]), ["dead&num;3-ent2.md"])
        self.assertEqual(named["reference_checkable_targets"], ["dead#3-ent2.md"])

        self.assertEqual(run_memory_lint_on(decimal["markdown"]), ["dead&"])
        self.assertEqual(decimal["reference_checkable_targets"], ["dead#3-ent3.md"])


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
