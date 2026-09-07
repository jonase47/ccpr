r"""test_manual_lint_check_g.py -- CCP-1151 stage 4 cut 4: manual-lint.sh
gains check (g), a FALLBACK GUARD against a retired prose word walking back
into the tree one commit at a time (see docs/decisions/2026-09-05_skill-
terminology-classification.md and stage 4's own commits: the four-stage
sweep replaced the prose word "skill" with "command" across CCPR, leaving
every REMAINING occurrence held by a named reason -- a frozen frontmatter
field key, a vendor filename, a deferred identifier, a protocol document,
or an explanatory marker cut 5 added).

## Why configuration, not a hardcoded word (Constraint 1)

`manual-lint.sh` ships to every CCPR adopter via `install.sh` and is
generic over ANY documentation root. The forbidden term and its excused
contexts are CCPR's own terminology decision, not a fact about the script
-- hardcoding "skill" into the shipped script would make every downstream
project inherit CCPR's own retired vocabulary. Check (g) is therefore
OPT-IN, exactly like `artifact-gate.sh`'s `gate.denyNames`
(scripts/lib/discipline_gate.sh): a personal, non-distributed
`~/.claude/memory-sync.json` under the new `lint.forbiddenProse` key, or an
env override, `CCPR_LINT_FORBIDDEN_PROSE` (a JSON array, since a
`{term, tokenContexts, lineContains, pathContains}` object per entry has no
natural flat comma-separated shape the way a bare name list does). With
neither configured, check (g) checks nothing -- proven below by
`NotConfiguredTest`, which also proves the silence is a REPORTED info line,
not a plain absence indistinguishable from "check (g) ran and found
nothing" (WI-0090's "a check that ran over nothing is not a pass",
generalised from artifact-gate.sh's own denylist-not-configured notice).

This module drives the shipped script exclusively through
`CCPR_LINT_FORBIDDEN_PROSE`, never through the real, personal
`~/.claude/memory-sync.json` -- reading that file to verify its FORMAT is
`git-scoped-to-this-repo` territory (`templates/memory-sync.example.json`
documents the key), never something a test process should touch.

## The three context lists, and why each is independent (Constraint 3)

An occurrence is excused if ANY of three checks fire, run in this order but
independent of each other (each is proven capable of excusing alone, and of
NOT excusing when the other two also miss):

  * `tokenContexts` -- a list of strings; an occurrence is excused when the
    text immediately preceding the matched term (case-insensitively, no
    character skipped) ends with one of them. This is a PREFIX check, not
    literal token equality, and that distinction is deliberate and
    measured: CCPR's own real corpus carries the frozen field key as
    `subskill:`, but also as `1-subskill` (a ratio in prose,
    `commands/p3-data-model.md`), `per-subskill` (`commands/p4-backlog.md`)
    and the hyphenated `sub-skill` / `Sub-Skill` (a table header
    convention, `templates/QA_SKELETON/*.md`, `README.md`, several
    `handbook/**` files) -- all four are the SAME field concept, and a
    naive "the enclosing alnum-only token equals subskill" rule (matching
    only the PO's literally-listed `subskill`/`Subskill`/`SUBSKILL`/
    `subskills`) would leave the hyphenated and digit-prefixed spellings
    unexcused. `tokenContexts: ["sub", "sub-"]` covers every measured
    spelling with two entries instead of enumerating every prefix that can
    precede a hyphen. See `TokenContextPrefixTest` for the four-shape proof
    and `TokenContextDoesNotOvermatchTest` for the boundary this
    generalisation must NOT cross (a bare, unprefixed occurrence stays an
    error).
  * `lineContains` -- literal, case-SENSITIVE substrings of the raw line
    (markup included, deliberately: cut 5's own `not a missed rename`
    marker sits inside an HTML comment, and check (g) must still read that
    line, not a markup-stripped copy of it). Case-sensitive because every
    configured phrase here is copied verbatim from the real corpus this
    config was measured against (`Agent Skills`, `skill.md`, `SKILL.md`) --
    a looser case-insensitive match would risk excusing a differently-cased
    accidental reintroduction it was never meant to cover.
  * `pathContains` -- literal, case-sensitive substrings of the file's path
    relative to whichever root the file was found under. A match excuses
    the WHOLE FILE for that term, not just one line -- appropriate for
    `CHANGELOG.md` and `docs/adr/**` (protocol, never rewritten
    retroactively) and `scripts/tests/**` (a fixture that pins a pre-sweep
    literal on purpose).

## Mutation proof, structural not deletion (G-107/G-109)

`LengthPreservingContextSwapTest` is the probe Constraint 3.2 asks for
explicitly: reorder two entries in the SAME list so it has the same length
and the same element SET (a permutation, not a change in content) --
G-168's point ("a guard asserted through a scalar proxy is blind to every
length-preserving change") only bites when the swap can be observed to
matter, so this test's fixture is built so that swapping order changes
NOTHING (context lists are checked by set membership, not by position) and
then, separately, `WrongContextValueSwapTest` substitutes one list's VALUE
for a different, unrelated string of the same length -- a change deletion
alone would never distinguish from "the check never ran". Both keep the
list's length and count identical; only content differs.

## The standing regression test (Constraint 3.3)

`RealCorpusRegressionTest.test_wired_roots_produce_zero_check_g_errors` runs
the shipped script, configured with CCPR's own measured
`forbidden_prose_config()` (defined once, at module level, and reused by
every test above so there is exactly one place this config can drift from
what the regression test asserts against), over the roots check-all.sh
now wires manual-lint.sh to (`WIRED_ROOTS` below, `test_manual_lint_multi_root.py`'s subject),
and asserts NO check-(g)-shaped error appears in the output -- filtered to
messages this check itself emits, never a blanket "zero errors of any
kind" assertion, so a real check-(g) regression can never hide behind an
unrelated check (a)/(f) finding on the same root.

A second test, `test_run_against_full_repository_notes_preexisting_
unrelated_findings`, runs the same configuration against the REPOSITORY
ROOT -- but against a `git archive HEAD` snapshot in a scratch directory,
never the live working tree (`RealCorpusRegressionTest`'s own class
docstring explains why: the live tree carries gitignored working state,
`docs/HANDOVER.md` and `docs/.workitems-archive-*/` among it, that
legitimately mentions the retired word in an ever-changing way this item's
own scope never covered). At 187794d, the commit this module was written
against, that clean, tracked-only snapshot carried five genuine strays
outside the five wired roots -- two GitHub issue templates and three lines
in `BETA.md` -- none of them a documented, deliberate exemption the way
the wired roots' sub-skill and meta-narrative cases are; cut 4's own
boundary ("builds a guard, does not sweep") pinned them by name
(`KNOWN_STRAY_FINDINGS`) and reported rather than fixed them. Cut 6
(CCP-1151 stage 4, PO decision 07.09.2026: sweep them and name the corpus
gap rather than pin it as a permanent known finding) swept all five, so
`KNOWN_STRAY_FINDINGS` is now EMPTY rather than a fixed list of five
paths. The comparison stays a set-equality check and stays non-vacuous:
`g_error_files` is measured fresh from a live subprocess run every time
this test runs, never a literal, so `assertEqual(g_error_files,
KNOWN_STRAY_FINDINGS)` still exercises a real comparison and still FAILS
the moment a stray reappears. What an empty pin can no longer do is catch
one of the five silently disappearing -- there is nothing left in the set
to vanish from; that was always the less load-bearing of the two
directions, and it is exactly the one cut 6 is firing on purpose.

**Count re-derived, not copied**: the work item that commissioned this
guard quotes "329 legitimate occurrences" from an earlier measurement.
Repeating that number here without re-running the count would be exactly
the mistake G-165 exists to name (a figure from someone else's measurement,
carried forward instead of re-derived) -- and it would have been wrong,
though not for the reason first guessed here. 329 and 352 are not one
count measured twice; they are two different probes over two different
scopes. 329 is this item's own recipe: a fixed root list (`README.md`,
`handbook`, `docs`, `commands`, `agents`, `templates`, `hooks`, `scripts`,
`instincts.md`, `instincts`, `CLAUDE.md`) counted across every file type.
352 is this module's own probe: every case-insensitive `skill` substring
across every tracked `.md`/`.py`/`.sh` file anywhere in the tree, recipe
root or not. `.github/` and root-level files like `BETA.md` sit inside the
second scope and outside the first -- which is exactly how cut 6 found
the five stray sites the paragraph above describes. Re-derived fresh at
187794d rather than copied from either prior figure, the two counts are
427 (recipe roots) and 453 (tracked-tree probe) -- both have grown since
the 329/352 pair was written, and the roughly 25-occurrence gap between
them was always the recipe/tree scope difference, never a handful of
large files. `EXCUSED_OCCURRENCE_FLOOR` below is a `floor`, not a
`count`, for the same reason `test_doc_counts_agree.py`'s own guidance
argues against `count` for anything that legitimately grows: this
configuration will keep excusing more occurrences as the corpus grows, and
the floor only fires if today's stock of legitimately-excused text
disappears.
"""

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "manual-lint.sh"

ENV_VAR = "CCPR_LINT_FORBIDDEN_PROSE"

# CCPR's OWN dogfood configuration for the retired prose word -- measured
# against this repository's real corpus (see module docstring). This is
# CCPR-project-specific data living in a TEST module, never in the shipped
# script (Constraint 1) and never in check-all.sh's invocation of it either
# (check-all.sh is itself shipped and generic -- baking a CCPR-specific
# word list into it would reproduce the exact problem Constraint 1 warns
# against, one file over). This is the ONE place this configuration is
# written down; every test below reuses it rather than retyping any part of
# it, so a future edit to the real corpus that needs a new exemption has
# exactly one call site to change.
def forbidden_prose_config():
    """CCPR's own check-(g) configuration, carried here so the guard runs in CI
    without anyone's personal `~/.claude/memory-sync.json`.

    NOTHING IS ADDED TO THESE THREE LISTS UNASKED (PO decision 07.09.2026, after
    Olli's review of CCP-1151 stage 4). Every entry EXCUSES an occurrence, so
    growing a list is LOOSENING the guard, and it is the one edit here that can
    make a real regression pass in silence. An entry therefore needs a named
    reason and a decision behind it -- not a green suite, which a new entry
    produces by construction.

    The direction that gets this wrong is always the same: a check fires on
    something legitimate, and the cheapest way to green is to widen the excuse
    rather than to ask whether the finding is real. If a new occurrence trips
    check (g), the first question is whether the word belongs there at all.

    This is a comment, and a comment cannot go red -- so it is not a control.
    Making it one means pinning these lists the way `KNOWN_POST_CONTRACT_EDITS`
    in `test_agent_frontmatter.py` is pinned, so that any growth reddens until
    it is written down deliberately. Recorded here as the known next step rather
    than done silently.
    """
    return [
        {
            "term": "skill",
            "tokenContexts": ["sub", "sub-"],
            "lineContains": [
                "Agent Skills",
                "skill.md",
                "SKILL.md",
                "SKILL system filenames",
                "skill-interface",
                "not a missed rename",
                '"skill" was swept out',
                "CCPR's prose \"skill\" collided with the vendor's",
                "Lean-Track introduced (parallel to Full-Track)",
            ],
            "pathContains": [
                "CHANGELOG.md",
                "docs/adr/",
                "docs/CONSTITUTION.md",
                "scripts/tests/",
                "instincts/external.md",
                "hooks/agent-monitor.py",
            ],
        }
    ]


# The roots check-all.sh now wires manual-lint.sh to (this cut), plus
# the repository root for the "did the guard actually run over real files"
# proof. Kept as a tuple of relative dir names, not re-derived from
# check-all.sh's own invoke_args by parsing shell -- the coupling this
# module cares about is "these roots are clean", which it proves directly
# by running the script, not by trusting a second copy of check-all.sh's
# own list to still say the same thing.
WIRED_ROOTS = ("handbook", "commands", "agents", "templates", "instincts")

# A floor, not a count -- see module docstring's "Count re-derived" section.
EXCUSED_OCCURRENCE_FLOOR = 300


def run_lint(root, config=None, cwd=None):
    env = None
    if config is not None:
        import os
        env = dict(os.environ)
        env[ENV_VAR] = json.dumps(config)
    args = ["bash", str(SCRIPT_PATH)]
    if root is not None:
        args.append(str(root))
    return subprocess.run(args, capture_output=True, text=True, env=env, cwd=cwd)


def findings(output, heading):
    collected, collecting = [], False
    for line in output.splitlines():
        if line.startswith("## "):
            collecting = line.startswith(f"## {heading} (")
        elif collecting and line.startswith("- "):
            collected.append(line[2:])
    return collected


def check_g_errors(output):
    """Errors this check emits, distinguished by their own message shape --
    never by counting ALL errors, which would conflate check (g) with
    checks (a)/(f) on a dirty root (see RealCorpusRegressionTest)."""
    return [e for e in findings(output, "Errors") if "forbidden prose term" in e]


class ManualLintCheckGTestBase(unittest.TestCase):
    def setUp(self):
        import shutil
        import tempfile
        self.root = Path(tempfile.mkdtemp(prefix="ccpr-manual-lint-check-g-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def write(self, rel_path, text):
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_lint(self, config):
        return run_lint(self.root, config=config)


DOC = "---\nkind: detail\n---\n\n# Doc\n\n"


class NotConfiguredTest(ManualLintCheckGTestBase):
    """No config at all (env unset, and this test never touches the real
    personal memory-sync.json) -- check (g) must check nothing, and must
    SAY so rather than reading like a silent pass."""

    def test_absence_of_config_produces_no_errors_and_an_info_notice(self):
        self.write("x.md", DOC + "skill skill skill\n")

        result = run_lint(self.root, config=None)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(check_g_errors(result.stdout), [], result.stdout)
        infos = findings(result.stdout, "Info")
        self.assertTrue(
            any("check (g)" in i and "NOT CONFIGURED" in i for i in infos),
            infos,
        )

    def test_empty_forbidden_prose_list_is_also_not_configured(self):
        self.write("x.md", DOC + "skill\n")

        result = self.run_lint([])

        # Liveness proof (test_absence_only_assertions.py): "no errors"
        # alone cannot distinguish a real, clean run from a crashed
        # subprocess with empty stdout -- assert the file was actually
        # scanned before trusting the absence of an error.
        self.assertIn("**Files scanned:** 1", result.stdout, result.stdout)
        self.assertEqual(check_g_errors(result.stdout), [], result.stdout)
        infos = findings(result.stdout, "Info")
        self.assertTrue(any("NOT CONFIGURED" in i for i in infos), infos)


class BasicViolationTest(ManualLintCheckGTestBase):
    """A configured term, found in ordinary prose with none of its three
    excuse lists matching, is an ERROR -- and the run exits 2 (Constraint
    3's "everything the patterns do not excuse is an ERROR")."""

    def test_bare_forbidden_word_is_an_error_at_exit_2(self):
        self.write("x.md", DOC + "This mentions the skill directly.\n")

        result = self.run_lint([{"term": "skill"}])

        self.assertEqual(result.returncode, 2, result.stdout)
        errs = check_g_errors(result.stdout)
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("x.md", errs[0])
        self.assertIn("skill", errs[0])

    def test_two_occurrences_on_one_line_are_two_separate_findings(self):
        """G-153: grep -c counts lines, not occurrences -- two forbidden
        words on the same line must produce two error entries, distinguished
        by column, not collapse into one."""
        self.write("x.md", DOC + "skill and another skill on one line\n")

        result = self.run_lint([{"term": "skill"}])

        self.assertEqual(len(check_g_errors(result.stdout)), 2, result.stdout)


class TokenContextPrefixTest(ManualLintCheckGTestBase):
    """tokenContexts excuses the FOUR measured real-corpus spellings of the
    frozen field key, all via the two-entry `["sub", "sub-"]` prefix list
    (module docstring's rationale)."""

    def _assert_excused(self, prose):
        self.write("x.md", DOC + prose + "\n")
        result = self.run_lint(
            [{"term": "skill", "tokenContexts": ["sub", "sub-"]}]
        )
        self.assertEqual(check_g_errors(result.stdout), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_plain_subskill_field_key_is_excused(self):
        self._assert_excused("subskill: market")

    def test_digit_prefixed_1_subskill_is_excused(self):
        self._assert_excused("the 1-subskill = 1-file pattern")

    def test_word_prefixed_per_subskill_is_excused(self):
        self._assert_excused("not a per-subskill artefact")

    def test_hyphenated_sub_skill_is_excused(self):
        self._assert_excused("one detail file per sub-skill")

    def test_capitalised_sub_skill_table_header_is_excused(self):
        self._assert_excused("| Sub-Skill | File | Status |")


class TokenContextDoesNotOvermatchTest(ManualLintCheckGTestBase):
    """The prefix check must not swallow an occurrence that merely happens
    to sit near, but is not immediately preceded by, an excused prefix --
    proving `tokenContexts` is a PRECEDING-text check, not "this word
    appears somewhere on the line" (which check (g)'s lineContains already
    covers separately, and conflating the two would silently widen
    lineContains's blast radius to every configured token prefix)."""

    def test_bare_word_after_an_unrelated_hyphenated_word_is_not_excused(self):
        self.write("x.md", DOC + "a well-known skill is needed here\n")

        result = self.run_lint(
            [{"term": "skill", "tokenContexts": ["sub", "sub-"]}]
        )

        self.assertEqual(len(check_g_errors(result.stdout)), 1, result.stdout)


class LineContextTest(ManualLintCheckGTestBase):
    def test_configured_line_phrase_excuses_the_occurrence(self):
        self.write("x.md", DOC + "See Agent Skills for the vendor feature.\n")

        result = self.run_lint(
            [{"term": "skill", "lineContains": ["Agent Skills"]}]
        )

        # Liveness proof (test_absence_only_assertions.py): distinguishes a
        # real clean run from a crashed subprocess with empty stdout.
        self.assertIn("**Files scanned:** 1", result.stdout, result.stdout)
        self.assertEqual(check_g_errors(result.stdout), [], result.stdout)

    def test_html_comment_marker_line_is_read_and_excused(self):
        """Constraint 3's marker lives inside an HTML comment -- check (g)
        must read the RAW line (markup included), not a markup-stripped
        copy the way check (f) works."""
        self.write(
            "x.md",
            DOC + '<!-- "sub-skill" here is the frozen subskill: '
            "frontmatter field key, not a missed rename. -->\n",
        )

        result = self.run_lint(
            [{"term": "skill", "lineContains": ["not a missed rename"]}]
        )

        self.assertIn("**Files scanned:** 1", result.stdout, result.stdout)
        self.assertEqual(check_g_errors(result.stdout), [], result.stdout)

    def test_unconfigured_line_phrase_does_not_excuse(self):
        self.write("x.md", DOC + "See Agent Skills for the vendor feature.\n")

        result = self.run_lint([{"term": "skill", "lineContains": ["Something Else"]}])

        self.assertEqual(len(check_g_errors(result.stdout)), 1, result.stdout)


class PathContextTest(ManualLintCheckGTestBase):
    def test_configured_path_substring_excuses_the_whole_file(self):
        self.write("docs/adr/ADR-0099-x.md", DOC + "a skill mentioned here\n")

        result = self.run_lint(
            [{"term": "skill", "pathContains": ["docs/adr/"]}]
        )

        self.assertIn("**Files scanned:** 1", result.stdout, result.stdout)
        self.assertEqual(check_g_errors(result.stdout), [], result.stdout)

    def test_a_sibling_path_outside_the_configured_substring_still_errors(self):
        self.write("docs/other/x.md", DOC + "a skill mentioned here\n")

        result = self.run_lint(
            [{"term": "skill", "pathContains": ["docs/adr/"]}]
        )

        self.assertEqual(len(check_g_errors(result.stdout)), 1, result.stdout)

    def test_path_substring_matches_via_the_scanned_roots_own_directory_name(self):
        """code-reviewer finding: pathContains entries are written as
        repository-relative substrings ("external/notes.md"), and manual-
        lint.sh may be POINTED directly at that named directory as its own
        ROOT -- stripping ROOT off the path removes exactly the segment the
        exemption names (`grel` alone would be just "notes.md"), unless the
        root's own directory name is reinstated before matching."""
        scan_root = self.root / "external"
        scan_root.mkdir()
        (scan_root / "notes.md").write_text(
            DOC + "a skill mentioned here\n", encoding="utf-8"
        )

        result = run_lint(
            scan_root, config=[{"term": "skill", "pathContains": ["external/notes.md"]}]
        )

        self.assertIn("**Files scanned:** 1", result.stdout, result.stdout)
        self.assertEqual(check_g_errors(result.stdout), [], result.stdout)

    def test_an_ancestor_directory_above_the_root_does_not_leak_into_the_match(self):
        """The fix for the case above must not overshoot into matching the
        file's FULL absolute path -- code-reviewer's Important finding: an
        ancestor directory above the scanned root (here, a parent literally
        named like a configured pathContains entry) must never silently
        excuse a file whose ACTUAL root-relative path never contains that
        substring. Only the scanned root's own directory name, prefixed
        onto the relative path, may match."""
        ancestor = self.root / "docs" / "adr"
        scan_root = ancestor / "actual-root"
        scan_root.mkdir(parents=True)
        (scan_root / "x.md").write_text(
            DOC + "a skill mentioned here\n", encoding="utf-8"
        )

        result = run_lint(
            scan_root, config=[{"term": "skill", "pathContains": ["docs/adr/"]}]
        )

        self.assertIn("**Files scanned:** 1", result.stdout, result.stdout)
        self.assertEqual(len(check_g_errors(result.stdout)), 1, result.stdout)


class LengthPreservingContextSwapTest(ManualLintCheckGTestBase):
    """G-168/Constraint 3.2: reorder two entries in the SAME context list --
    same length, same element set, different order. The check is a set
    membership test, so reordering must change nothing; this is the
    negative control proving the assertion below (WrongContextValueSwapTest)
    is measuring content, not merely "the list is non-empty"."""

    def test_reordering_lineContains_entries_changes_nothing(self):
        self.write("x.md", DOC + "See Agent Skills here, and skill.md there.\n")

        forward = self.run_lint(
            [{"term": "skill", "lineContains": ["Agent Skills", "skill.md"]}]
        )
        reversed_ = self.run_lint(
            [{"term": "skill", "lineContains": ["skill.md", "Agent Skills"]}]
        )

        self.assertIn("**Files scanned:** 1", forward.stdout, forward.stdout)
        self.assertIn("**Files scanned:** 1", reversed_.stdout, reversed_.stdout)
        self.assertEqual(check_g_errors(forward.stdout), [])
        self.assertEqual(check_g_errors(reversed_.stdout), [])


class WrongContextValueSwapTest(ManualLintCheckGTestBase):
    """The mutation Constraint 3.2 actually asks for: substitute ONE
    context-list entry for a different, unrelated string of comparable
    shape. Same list length, same element COUNT, different content -- the
    shape deletion (G-107/G-109) cannot produce, and the shape a
    length-only or count-only assertion (G-168) would not catch."""

    def test_substituting_one_lineContains_entry_stops_excusing_its_line(self):
        self.write("x.md", DOC + "See Agent Skills for the vendor feature.\n")

        correct = self.run_lint(
            [{"term": "skill", "lineContains": ["Agent Skills", "skill.md"]}]
        )
        # Same list length (2), same element count (2), "Agent Skills"
        # swapped for an unrelated phrase of similar shape.
        mutated = self.run_lint(
            [{"term": "skill", "lineContains": ["Agent Tools", "skill.md"]}]
        )

        self.assertEqual(check_g_errors(correct.stdout), [], correct.stdout)
        self.assertEqual(len(check_g_errors(mutated.stdout)), 1, mutated.stdout)

    def test_substituting_one_tokenContexts_entry_stops_excusing_its_prefix(self):
        self.write("x.md", DOC + "one detail file per sub-skill\n")

        correct = self.run_lint(
            [{"term": "skill", "tokenContexts": ["sub", "sub-"]}]
        )
        mutated = self.run_lint(
            [{"term": "skill", "tokenContexts": ["sub", "pre-"]}]
        )

        self.assertEqual(check_g_errors(correct.stdout), [], correct.stdout)
        self.assertEqual(len(check_g_errors(mutated.stdout)), 1, mutated.stdout)


class MultipleTermsTest(ManualLintCheckGTestBase):
    """forbiddenProse is a LIST -- more than one term entry, each with its
    own independent context lists, must both be enforced in one run."""

    def test_two_configured_terms_are_both_checked(self):
        self.write("x.md", DOC + "a skill and a widget are both here\n")

        result = self.run_lint(
            [{"term": "skill"}, {"term": "widget"}]
        )

        errs = check_g_errors(result.stdout)
        self.assertEqual(len(errs), 2, errs)


class MalformedConfigTest(ManualLintCheckGTestBase):
    """A config the operator actually wrote wrong is refused (exit 2, a
    clear stderr reason) rather than silently checking a shortened or
    reinterpreted scope -- the same "refuse rather than guess" discipline
    conformance-run.sh's own config reader already applies to a
    structurally similar list-of-objects config."""

    def test_missing_term_key_is_refused(self):
        result = self.run_lint([{"tokenContexts": ["sub"]}])

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("term", result.stderr.lower())

    def test_unknown_key_is_refused(self):
        result = self.run_lint([{"term": "skill", "unknownField": ["x"]}])

        self.assertEqual(result.returncode, 2, result.stdout)

    def test_a_term_containing_a_newline_is_refused(self):
        # The TSV record transport between the python3 config reader and
        # bash is one "KEY\tVALUE" record per line; a term carrying a
        # literal newline would split into two records, the second
        # unparsable as any known key. tokenContexts/lineContains/
        # pathContains entries already reject this shape -- term must too.
        result = self.run_lint([{"term": "skill\nother"}])

        self.assertEqual(result.returncode, 2, result.stdout)

    def test_invalid_json_env_value_is_refused(self):
        result = run_lint(self.root, config="not json")

        self.assertEqual(result.returncode, 2, result.stdout)


class RealCorpusRegressionTest(unittest.TestCase):
    """Constraint 3.3 -- the standing regression test. CCPR's own measured
    configuration, run against the roots check-all.sh now wires
    manual-lint.sh to, must produce zero check-(g)-shaped errors.

    The "full repository" tests below run against a `git archive` snapshot
    of HEAD, in a scratch directory, rather than the live working tree --
    the working tree carries gitignored working state
    (`docs/HANDOVER.md`, `docs/.workitems-archive-*/`) that legitimately
    mentions the retired word in an ever-changing, session-specific way
    (this very ticket's own HANDOVER.md entry, for one) and is never part
    of "the tree" CCP-1151's own scope was measured against. Same
    boundary `test_handover_cap_sentence_echoes.py`'s `tracked_files()`
    already draws for the identical reason, one call further in: `git
    archive` rather than `git ls-files` because check (g) needs real files
    on disk to `find` and read, not a list of paths."""

    @classmethod
    def setUpClass(cls):
        import shutil
        import tempfile
        cls.archive_dir = Path(tempfile.mkdtemp(prefix="ccpr-manual-lint-archive-"))
        proc = subprocess.run(
            ["git", "archive", "HEAD"], cwd=REPO_ROOT, capture_output=True, check=True,
        )
        subprocess.run(
            ["tar", "-x", "-C", str(cls.archive_dir)],
            input=proc.stdout, capture_output=True, check=True,
        )
        cls._cleanup = lambda: shutil.rmtree(cls.archive_dir, ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        cls._cleanup()

    def test_wired_roots_produce_zero_check_g_errors(self):
        config = forbidden_prose_config()
        for root_name in WIRED_ROOTS:
            root = REPO_ROOT / root_name
            with self.subTest(root=root_name):
                result = run_lint(root, config=config)
                self.assertEqual(  # pin: set wired-roots-check-g-clean
                    check_g_errors(result.stdout), [],
                    f"check (g) found forbidden-prose errors under "
                    f"{root_name}/ with CCPR's own configuration:\n"
                    f"{result.stdout}",
                )

    # At 187794d, the commit this module was written against, five genuine
    # strays sat outside the five wired roots -- two GitHub issue templates
    # and three lines in BETA.md -- that cut 4's own measurement found and
    # deliberately did NOT fix (the boundary was "this cut builds a guard,
    # it does not sweep") and did NOT add to the config either (unlike the
    # sub-skill/meta-narrative cases the wired roots needed, these read as
    # plain leftover prose, not a documented, deliberate exemption -- see
    # the module docstring's "standing regression test" section for the
    # full reasoning). Cut 6 (CCP-1151 stage 4, PO decision 07.09.2026)
    # swept all five, so this pin is now EMPTY rather than a fixed list of
    # five paths.
    #
    # The comparison below stays a set-equality check, not a zero-error
    # one, and it stays non-vacuous: `g_error_files` is measured fresh
    # from a live subprocess run over a `git archive HEAD` snapshot every
    # time this test runs, never a literal, so `assertEqual(g_error_files,
    # KNOWN_STRAY_FINDINGS)` still exercises a real comparison and still
    # FAILS the moment a stray reappears. What it can no longer do is
    # catch one of these five silently disappearing -- there is nothing
    # left in the set to vanish from. That was always the less
    # load-bearing of the two directions: it exists to catch someone
    # fixing a stray without updating this pin, which is exactly what
    # cut 6 is doing on purpose.
    KNOWN_STRAY_FINDINGS = set()

    def test_run_against_full_repository_notes_preexisting_unrelated_findings(self):
        """The repository root, scanned as a CLEAN TRACKED-ONLY checkout
        (this class's own `git archive` snapshot -- see the class
        docstring), carries NO check-(g) findings outside the five wired
        roots (KNOWN_STRAY_FINDINGS above, emptied by cut 6's sweep -- see
        the comment above that assignment) and NO check (f) findings at
        all.

        This is worth stating explicitly because the two check (f)
        findings this item's own briefing measured against the LIVE
        working tree (`docs/memory/code-reviewer/lint-and-prompts.md`,
        `docs/memory/senior-developer/generic-doc-tree-linting.md`) turn
        out to live entirely inside `docs/memory/**` -- gitignored
        persona working state (`.gitignore:66`), never part of the
        tracked corpus at all. A scan of the live working tree would still
        find them; a scan of the tracked-only snapshot below correctly
        does not, and that difference is the whole reason this class uses
        `git archive` rather than pointing straight at REPO_ROOT."""
        config = forbidden_prose_config()
        result = run_lint(self.archive_dir, config=config)

        g_errors = check_g_errors(result.stdout)
        g_error_files = {e.split(":", 1)[0] for e in g_errors}
        self.assertEqual(g_error_files, self.KNOWN_STRAY_FINDINGS, g_errors)

        all_errors = findings(result.stdout, "Errors")
        self.assertEqual(len(all_errors), len(g_errors), all_errors)

    def test_excused_occurrence_floor(self):
        """A floor, not a count (module docstring) -- the configured
        exemptions must still be excusing at least this many real
        occurrences across the tracked tree. Re-derive with:
        `git ls-files -z | xargs -0 /usr/bin/grep -oiE 'skill' | wc -l`
        minus the check-(g) error count over the repo root, both measured
        fresh, never copied from a prior run's own report."""
        files = subprocess.run(
            ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True,
            text=True, check=True,
        ).stdout.split("\0")
        import re
        total = 0
        pattern = re.compile("skill", re.IGNORECASE)
        for rel in files:
            if not rel or not rel.endswith((".md", ".py", ".sh")):
                continue
            try:
                text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            total += len(pattern.findall(text))

        result = run_lint(self.archive_dir, config=forbidden_prose_config())
        error_count = len(check_g_errors(result.stdout))
        excused = total - error_count

        self.assertGreaterEqual(
            excused, EXCUSED_OCCURRENCE_FLOOR,
            f"expected at least {EXCUSED_OCCURRENCE_FLOOR} excused "
            f"occurrences, measured {excused} ({total} total, "
            f"{error_count} check-(g) errors)",
        )


if __name__ == "__main__":
    unittest.main()
