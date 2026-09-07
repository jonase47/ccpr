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

## The pin, the exhaustion half, and the `why`-field decision (CCP-1163)

`ForbiddenProseContextEntriesPinTest` turns this function's own docstring
rule ("NOTHING IS ADDED TO THESE THREE LISTS UNASKED") into a control:
`PINNED_CONTEXT_ENTRIES` is a set-membership pin (ADR-0012 "set" group) over
every `(term, list_name, value)` triple the config carries, so an add, a
removal, or a same-length SWAP all redden it -- never a scalar count, which
G-168 already names as blind to exactly the swap case.
`RealCorpusRegressionTest.test_every_pinned_context_entry_still_excuses_a_
real_occurrence` is the exhaustion half: every pinned entry must, on its own,
turn at least one real occurrence in scanned scope into a check-(g) error
when removed -- measured by a real subprocess run, never asserted plausible.

**Third cut, correcting the second cut's own two mistakes.** The second cut
measured exhaustion against a `git archive HEAD` snapshot of the WHOLE
repository and found five entries individually spent by that measure --
`skill.md`, `SKILL.md`, `SKILL system filenames`, `skill-interface`, `not a
missed rename` -- pinned as `KNOWN_SPENT_CONTEXT_ENTRIES`. Both the SCOPE and
the METHOD of that measurement were wrong, found by re-deriving rather than
trusting the prior figure (G-165):

1. **Wrong scope.** check-all.sh does not scan the whole repository; it scans
   `WIRED_ROOTS` below, ten roots. An entry can be individually spent against
   the FULL repository archive while still being the only thing excusing a
   real occurrence somewhere inside `WIRED_ROOTS` -- the second cut's
   measurement could not see this gap, because it never restricted itself to
   the scope check-all.sh actually runs. Re-measured against `WIRED_ROOTS`
   (the corrected scope `test_every_pinned_context_entry_still_excuses_a_
   real_occurrence` now uses), the individually-spent count is nine, not
   five -- the four `pathContains` entries for `CHANGELOG.md`, `docs/adr/`,
   `docs/CONSTITUTION.md` and `hooks/agent-monitor.py`, plus `skill-
   interface`, join the original five. These nine are `KNOWN_INDIVIDUALLY_
   SPENT_CONTEXT_ENTRIES` below -- the RAW per-entry result, kept distinct
   from any claim about what is actually redundant.

2. **Wrong method for a necessary pair.** A per-entry probe removes ONE entry
   at a time and can therefore never see a NECESSARY PAIR: `manual-lint.sh`'s
   `g_line_has_any` excuses a whole line the instant ANY configured
   `lineContains` phrase matches it, so on `instincts.md:87` (which carries
   BOTH `skill.md` and `SKILL system filenames`), removing either alone
   changes nothing -- the other still excuses the line -- and a per-entry
   probe reports both "spent". `test_the_individually_spent_set_is_not_
   jointly_spent` below is the control this method was missing: it removes
   the WHOLE `KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES` set AT ONCE and
   asserts the result reddens at exactly `instincts.md:87:22` and
   `:87:34` -- the two `skill` offsets that pair jointly protects. Calling
   both members of that pair "spent" and removing them, one commit at a
   time, each backed by a green per-entry exhaustion subTest, is exactly the
   hole this pin exists to prevent.

Splitting `KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES`'s nine members by their
MEASURED reason (not by assumption -- Finding 2, CCP-1163's own briefing):

* `KNOWN_JOINTLY_LOAD_BEARING_PAIRS` -- `skill.md` + `SKILL system
  filenames`. Each individually spent; removing both together is a real
  regression at `instincts.md:87`. Neither may be removed.
* `KNOWN_OUT_OF_SCOPE_CONTEXT_ENTRIES` -- `CHANGELOG.md`, `docs/adr/`,
  `docs/CONSTITUTION.md`, `hooks/agent-monitor.py` (`pathContains`) and
  `skill-interface` (`lineContains`, but every real occurrence of the
  phrase lives inside those same three out-of-scope paths). These excuse
  nothing TODAY because the paths they protect are never scanned by
  `WIRED_ROOTS` -- not because a sibling entry already covers them.
  `test_out_of_scope_entries_become_load_bearing_once_their_path_is_scanned`
  proves this is a measured, not argued, distinction: removing one of these
  entries and adding its own path as an extra scanned root produces new
  check-(g) errors that are absent with the entry configured. They are
  DEFENSIVE, not redundant -- wiring `docs/` or `hooks/` into `WIRED_ROOTS`
  makes the four `pathContains` entries load-bearing the same day, and
  removing any of them now would open that gap silently. `skill-interface`
  is the SAME group for the SAME reason (its path is unscanned) but a
  WEAKER, two-step risk, not a same-day one (code-reviewer finding,
  CCP-1163 third cut): every real occurrence of the phrase co-occurs with a
  file ALSO covered by a whole-file `pathContains` exemption, so wiring
  `docs/` alone would still leave it masked -- `OUT_OF_SCOPE_ALSO_REMOVE`
  below and its own comment measure this precisely, including the failed
  first attempt at this test that assumed otherwise (0 vs. 0). It only
  becomes load-bearing if `docs/` (or `CHANGELOG.md`) is wired AND its
  co-located `pathContains` exemption is separately narrowed later.
* `KNOWN_SPENT_CONTEXT_ENTRIES` (narrowed to two) -- `SKILL.md` and `not a
  missed rename`. Both genuinely redundant given an in-scope sibling:
  `SKILL.md`'s only real occurrences (`instincts/external.md`) sit inside a
  file already whole-file-excused by the still-configured `pathContains`
  entry for that exact path; `not a missed rename`'s only real occurrences
  sit on lines whose `skill` offset is inside `subskill:`, already excused
  by the still-configured `tokenContexts` entry `sub`.
  `test_genuinely_redundant_entries_are_confirmed_by_their_sibling` proves
  this is measured rather than assumed: removing the entry TOGETHER WITH
  its excusing sibling produces new errors (a real occurrence exists), while
  removing the entry ALONE does not (the sibling alone already excuses it).

`test_the_three_way_classification_partitions_the_individually_spent_set`
pins the arithmetic: the three groups above are pairwise disjoint, and each
carries its stated size (2, 5, 2) -- 2 + 5 + 2 = 9,
`KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES`'s own member count, each
`len()` recomputed from the live constants every run rather than stated
once and trusted. Deliberately NOT also a union-equality assertion against
`KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES` (code-reviewer finding, CCP-1163
third cut): that constant IS the same union expression by definition (its
own assignment above), so comparing the two would be vacuous, not a
cross-check -- the disjointness and the four length pins are what
carries real information.

**A named residual risk (code-reviewer, CCP-1151 stage 4; still applies,
CCP-1163)**: all three named-classification constants are review-discipline
controls, not fully mechanical ones, exactly like `KNOWN_STRAY_FINDINGS`
above and `KNOWN_POST_CONTRACT_EDITS` in test_agent_frontmatter.py. The
mechanical tests this cut adds (`test_the_individually_spent_set_is_not_
jointly_spent`, `test_out_of_scope_entries_become_load_bearing_once_their_
path_is_scanned`, `test_genuinely_redundant_entries_are_confirmed_by_their_
sibling`) narrow the risk relative to the second cut's single unverified
comment, but they cannot distinguish a correctly-classified entry from one a
future contributor placed in the wrong group on purpose to turn a red
subTest green -- reading the diff at commit time is still the only guard for
that. Adding a name to any of these three sets is not a decision to fix
silently; it is a decision to report, which this docstring and each
constant's own comment are what make that reportable.

**The `why`-field question, decided**: `conformance-run.sh`'s pins require a
mandatory `why` string, printed beside a violation (ADR-0010 SS5). This item
asked whether check (g)'s three lists should carry the same. Decided NO for
`templates/memory-sync.example.json`'s `lint.forbiddenProse` schema -- that
shape is the ADOPTER-FACING contract (a project writes its OWN retired-word
config there), and adding a mandatory field to it changes what every
downstream CCPR project must write, which is a schema change this item's
scope does not cover; it is also not this item's decision to make on behalf
of every adopter's own tooling preference. Decided YES in spirit, but NO in
STRUCTURE, for CCPR's own configuration in `forbidden_prose_config()` above:
a `why` travels as a comment at the addition site, the same convention
`KNOWN_POST_CONTRACT_EDITS` already uses in test_agent_frontmatter.py (an
inline comment above each tuple, not a schema field) -- and the reason a
structural field does not fit here is granularity: `PINNED_CONTEXT_ENTRIES`
pins one entry per STRING VALUE inside a list, not per config object, so a
`why` field would need one per value, which is exactly what a grouped
comment block already gives for free without inventing a fourth key
(`term`/`tokenContexts`/`lineContains`/`pathContains`, now `why`) that
`MalformedConfigTest.test_unknown_key_is_refused` would then have to accept
only in this test module and nowhere else, a divergence between CCPR's own
config and the schema it ships that seems worse than the discipline it buys.
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


# CCP-1163: forbidden_prose_config()'s docstring says the three context
# lists "do not grow unasked" (PO decision 07.09.2026), but a docstring is a
# comment and a comment cannot go red -- see docs/decisions/2026-09-05_
# skill-terminology-classification.md Section 13.2 for the identical lesson
# from CCP-1151 ("a register note cannot go red, so the note was not a
# control") and KNOWN_POST_CONTRACT_EDITS in test_agent_frontmatter.py for
# the pin/exhaustion shape this follows.
#
# PINNED_CONTEXT_ENTRIES is a set-membership pin (ADR-0012 "set" group) over
# every (term, list_name, value) triple forbidden_prose_config() currently
# carries. context_entries() flattens the config's list-of-dict shape into
# that triple because dicts and lists are unhashable and cannot sit in a
# frozenset directly -- the triple is also the smallest unit a set-diff
# failure message can name (ForbiddenProseContextEntriesPinTest reports
# exactly which term/list/value arrived or left, never a bare count).
#
def context_entries(config):
    """Flattens forbidden_prose_config()'s list-of-dict shape into the
    (term, list_name, value) triples PINNED_CONTEXT_ENTRIES compares
    against."""
    out = set()
    for entry in config:
        term = entry["term"]
        for list_name in ("tokenContexts", "lineContains", "pathContains"):
            for value in entry.get(list_name, []):
                out.add((term, list_name, value))
    return out


def _config_without_entry(config, term, list_name, value):
    """A copy of `config` with exactly one context-list VALUE removed from
    the matching term entry -- the mutation the exhaustion test measures
    against. Never touches the real forbidden_prose_config() function."""
    mutated = []
    for entry in config:
        entry_copy = dict(entry)
        if entry_copy.get("term") == term and list_name in entry_copy:
            entry_copy[list_name] = [
                v for v in entry_copy[list_name] if v != value
            ]
        mutated.append(entry_copy)
    return mutated


PINNED_CONTEXT_ENTRIES = frozenset({
    # tokenContexts -- TokenContextPrefixTest's four measured real-corpus
    # spellings of the frozen `subskill:` field key (module docstring,
    # "The three context lists" section).
    ("skill", "tokenContexts", "sub"),
    ("skill", "tokenContexts", "sub-"),

    # lineContains -- literal, case-sensitive phrases copied verbatim from
    # the real corpus this config was measured against (module docstring).
    ("skill", "lineContains", "Agent Skills"),
    ("skill", "lineContains", "skill.md"),
    ("skill", "lineContains", "SKILL.md"),
    ("skill", "lineContains", "SKILL system filenames"),
    ("skill", "lineContains", "skill-interface"),
    ("skill", "lineContains", "not a missed rename"),
    ("skill", "lineContains", '"skill" was swept out'),
    ("skill", "lineContains",
     "CCPR's prose \"skill\" collided with the vendor's"),
    ("skill", "lineContains", "Lean-Track introduced (parallel to Full-Track)"),

    # pathContains -- whole-file exemptions for protocol documents and
    # fixtures that pin a pre-sweep literal on purpose (module docstring).
    ("skill", "pathContains", "CHANGELOG.md"),
    ("skill", "pathContains", "docs/adr/"),
    ("skill", "pathContains", "docs/CONSTITUTION.md"),
    ("skill", "pathContains", "scripts/tests/"),
    ("skill", "pathContains", "instincts/external.md"),
    ("skill", "pathContains", "hooks/agent-monitor.py"),
})


# CCP-1163 finding, REPORTED and NOT re-tuned (this item's own boundary:
# "do not change what check (g) detects, and do not change which
# occurrences it currently excuses"). Module docstring's "Third cut"
# section carries the full reasoning; this comment carries the specific,
# re-measured membership.
#
# The second cut (before this one) measured exhaustion against the WHOLE
# repository archive and pinned a flat five-entry KNOWN_SPENT_CONTEXT_
# ENTRIES. That measurement's SCOPE was wrong (check-all.sh only ever scans
# WIRED_ROOTS, not the whole repository) and its METHOD was wrong (a
# per-entry probe cannot see a necessary PAIR). Re-measured against
# WIRED_ROOTS with a joint-removal control
# (test_the_individually_spent_set_is_not_jointly_spent below), the raw
# per-entry result grows from five to nine -- KNOWN_INDIVIDUALLY_SPENT_
# CONTEXT_ENTRIES -- and splits three ways by MEASURED reason, not by
# assumption:
KNOWN_JOINTLY_LOAD_BEARING_PAIRS = frozenset({
    # "skill.md" + "SKILL system filenames": each individually spent (a
    # per-entry probe finds the OTHER still excusing instincts.md:87), but
    # removing BOTH together reddens at instincts.md:87:22 and :87:34 --
    # `test_the_individually_spent_set_is_not_jointly_spent` measures this
    # fresh against the real corpus every run; `JointlyLoadBearingPairTest`
    # above reproduces the same shape on a synthetic fixture.
    frozenset({
        ("skill", "lineContains", "skill.md"),
        ("skill", "lineContains", "SKILL system filenames"),
    }),
})

# Individually spent under WIRED_ROOTS, but ONLY because the path(s) they
# would excuse are never scanned by WIRED_ROOTS at all -- DEFENSIVE, not
# redundant. `OUT_OF_SCOPE_EXTRA_ROOT` below names, per entry, an extra root
# that DOES reach the path; `test_out_of_scope_entries_become_load_bearing_
# once_their_path_is_scanned` measures that adding it turns the entry
# load-bearing again, which is what makes "defensive" a measured claim
# rather than an argument. Wiring `docs/` or `hooks/` into WIRED_ROOTS (a
# real possibility -- check-all.sh's own comment on why `docs/` stays
# unwired today calls it out) would make the four pathContains entries
# load-bearing the SAME DAY; removing any of them now would open that gap
# silently. "skill-interface" is a WEAKER, two-step case, not a same-day
# one (code-reviewer finding, CCP-1163 third cut) -- see
# OUT_OF_SCOPE_ALSO_REMOVE's own comment just below.
KNOWN_OUT_OF_SCOPE_CONTEXT_ENTRIES = frozenset({
    # Every real occurrence of "skill-interface" lives in CHANGELOG.md,
    # docs/adr/** and docs/CONSTITUTION.md -- confirmed by grep, none of it
    # inside any WIRED_ROOTS path.
    ("skill", "lineContains", "skill-interface"),
    ("skill", "pathContains", "CHANGELOG.md"),
    ("skill", "pathContains", "docs/adr/"),
    ("skill", "pathContains", "docs/CONSTITUTION.md"),
    ("skill", "pathContains", "hooks/agent-monitor.py"),
})

OUT_OF_SCOPE_EXTRA_ROOT = {
    ("skill", "lineContains", "skill-interface"): "CHANGELOG.md",
    ("skill", "pathContains", "CHANGELOG.md"): "CHANGELOG.md",
    ("skill", "pathContains", "docs/adr/"): "docs",
    ("skill", "pathContains", "docs/CONSTITUTION.md"): "docs",
    ("skill", "pathContains", "hooks/agent-monitor.py"): "hooks",
}

# code-reviewer finding (CCP-1163 third cut): a bare error-COUNT increase
# cannot distinguish "the expected occurrence surfaced" from "an unrelated
# occurrence in the newly-scanned root surfaced instead". Both tests below
# additionally assert that at least one NEW error's own file portion
# matches the entry's own known location -- weaker than the pair test's
# exact line:column pin (these locations carry more than one occurrence
# and shift line numbers as the files they sit in evolve), but strictly
# stronger than a scalar count.
# The expected substring is written RELATIVE TO THE SCANNED ROOT, not the
# repository -- measured, not assumed (a first version of this dict used
# the repository-relative shape and every DIRECTORY-root case failed, red,
# against the real corpus). manual-lint.sh's own error line uses two
# different bases depending on ROOT's kind: a FILE root (CHANGELOG.md
# here) reports via `$gfile_display` (the file's own basename, e.g.
# "CHANGELOG.md"); a DIRECTORY root (docs, hooks here) reports via `$grel`
# (the path stripped of the ROOT prefix, e.g. "adr/ADR-....md" or
# "agent-monitor.py"), never `$gfile_display`'s root-basename-prefixed form
# -- manual-lint.sh's own comment at its `err` call for check (g) explains
# this is deliberate (the DIRECTORY case's report shape was left alone on
# purpose, out of a narrower fix's scope).
OUT_OF_SCOPE_EXPECTED_NEW_ERROR_FILE = {
    ("skill", "lineContains", "skill-interface"): "CHANGELOG.md",
    ("skill", "pathContains", "CHANGELOG.md"): "CHANGELOG.md",
    ("skill", "pathContains", "docs/adr/"): "adr/",
    ("skill", "pathContains", "docs/CONSTITUTION.md"): "CONSTITUTION.md",
    ("skill", "pathContains", "hooks/agent-monitor.py"): "agent-monitor.py",
}

# "skill-interface" is measured (not assumed) to need one MORE thing than
# the other four out-of-scope entries: every one of its real occurrences
# co-occurs, in the tracked tree, with a file ALSO covered by a whole-file
# pathContains exemption (CHANGELOG.md) -- so scanning its path alone stays
# silent, the co-located pathContains entry masks it first (measured:
# scanning "docs" alone, without also touching CHANGELOG.md's pathContains
# entry, produced 0 vs. 0 -- the first version of this test asserted wrong
# and caught itself). This dict names, per entry that needs it, the ONE
# additional sibling to remove in the SAME probe so the effect is visible --
# the compound scenario ("this path gets wired AND its own whole-file
# exemption gets narrowed later"), not the simpler one the other four need.
OUT_OF_SCOPE_ALSO_REMOVE = {
    ("skill", "lineContains", "skill-interface"): ("pathContains", "CHANGELOG.md"),
}

# Individually spent under WIRED_ROOTS AND genuinely redundant: every real
# occurrence each would excuse sits INSIDE a WIRED_ROOTS path and is already
# excused by a DIFFERENT, still-load-bearing sibling entry.
# `REDUNDANT_ENTRY_SIBLINGS` names that sibling per entry;
# `test_genuinely_redundant_entries_are_confirmed_by_their_sibling` measures
# that removing the entry TOGETHER WITH its sibling produces new errors (a
# real occurrence exists) while removing the entry alone does not (the
# sibling alone already excuses it) -- distinguishing genuine redundancy
# from "never excused anything, anywhere" by measurement, not assumption.
KNOWN_SPENT_CONTEXT_ENTRIES = frozenset({
    # Every real occurrence of "SKILL.md" lives inside instincts/external.md
    # (two occurrences, lines 40 and 46), wholly excused by the still-
    # configured pathContains entry for that exact path.
    ("skill", "lineContains", "SKILL.md"),
    # Every real occurrence sits on a line whose "skill" offset is inside
    # "subskill"/"Subskill" (the frozen field key), already excused by the
    # still-configured tokenContexts entry "sub" -- confirmed at
    # docs/PROJECT_PHASES.md:148 and scripts/project-init.sh:64 among others.
    ("skill", "lineContains", "not a missed rename"),
})

REDUNDANT_ENTRY_SIBLINGS = {
    ("skill", "lineContains", "SKILL.md"): (
        ("pathContains", "instincts/external.md"),
        ("pathContains", "scripts/tests/"),
    ),
    ("skill", "lineContains", "not a missed rename"): (
        ("tokenContexts", "sub"),
    ),
}

# code-reviewer finding (CCP-1163 third cut): see
# OUT_OF_SCOPE_EXPECTED_NEW_ERROR_FILE's own comment -- the same
# strengthening applied here. "not a missed rename" has more than one
# known real site (the marker appears after `subskill:` in several
# WIRED_ROOTS files); any one of them surfacing is sufficient.
# Same relative-to-scanned-root convention as OUT_OF_SCOPE_EXPECTED_NEW_
# ERROR_FILE's own comment: "instincts" and "scripts" are DIRECTORY roots
# in WIRED_ROOTS, so their reports strip the root prefix ("external.md",
# "project-init.sh"); "docs/PROJECT_PHASES.md" is a FILE root, reported via
# its own basename ("PROJECT_PHASES.md").
REDUNDANT_ENTRY_EXPECTED_NEW_ERROR_FILES = {
    ("skill", "lineContains", "SKILL.md"): ("external.md",),
    ("skill", "lineContains", "not a missed rename"): (
        "PROJECT_PHASES.md", "project-init.sh",
    ),
}

# The raw per-entry-probe result (Finding 1's own flawed method, kept as an
# explicit, named intermediate rather than silently folded into "spent"):
# exactly the union of the three groups above, re-derived and pinned by
# `test_the_three_way_classification_partitions_the_individually_spent_set`
# rather than stated once and trusted.
KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES = (
    frozenset().union(*KNOWN_JOINTLY_LOAD_BEARING_PAIRS)
    | KNOWN_OUT_OF_SCOPE_CONTEXT_ENTRIES
    | KNOWN_SPENT_CONTEXT_ENTRIES
)


class ForbiddenProseContextEntriesPinTest(unittest.TestCase):
    """G-160/ADR-0012: forbidden_prose_config()'s three exemption lists may
    not grow, shrink, or swap an entry without this pin being edited in the
    SAME commit -- the docstring's rule ("NOTHING IS ADDED TO THESE THREE
    LISTS UNASKED") made enforceable rather than merely stated."""

    def test_pinned_context_entries_match_the_config(self):
        import sys as _sys
        # Local import rather than a module-level one: CONTRIBUTING.md pins
        # in prose how many modules fail to import without `-t .`, and a new
        # module-level import edge moves those numbers (same reasoning as
        # test_absence_only_assertions.py's identical local import).
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from pin_registry import assert_set_matches

        assert_set_matches(  # pin: set forbidden-prose-context-entries
            self,
            PINNED_CONTEXT_ENTRIES,
            context_entries(forbidden_prose_config()),
            "check (g)'s allowed-context entries",
        )


# The roots check-all.sh now wires manual-lint.sh to (this cut), plus
# the repository root for the "did the guard actually run over real files"
# proof. Kept as a tuple of relative dir/file names, not re-derived from
# check-all.sh's own invoke_args by parsing shell -- the coupling this
# module cares about is "these roots are clean", which it proves directly
# by running the script, not by trusting a second copy of check-all.sh's
# own list to still say the same thing.
#
# CCP-1163: extended by five entries once manual-lint.sh gained single-FILE
# root support (test_manual_lint_single_file_root.py) -- four loose
# top-level documents plus the whole scripts/ tree, all measured clean for
# checks (a)/(b)/(c)/(f) at 1aa705c and, via this module's own regression
# tests below, for check (g) too. `docs/` as a WHOLE stays deliberately
# unwired (pre-existing derived-count-marker errors under the gitignored
# docs/memory/** persona-notes tree, out of this item's scope) --
# docs/PROJECT_PHASES.md is wired as a single file instead, the targeted
# fix check-all.sh's own comment at its manual-lint invocation explains.
WIRED_ROOTS = (
    "handbook", "commands", "agents", "templates", "instincts",
    "CLAUDE.md", "instincts.md", "README.md", "docs/PROJECT_PHASES.md",
    "scripts",
)

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


class JointlyLoadBearingPairTest(ManualLintCheckGTestBase):
    """CCP-1163 (second cut): a synthetic reproduction of the real
    instincts.md:87 shape -- one line carrying TWO forbidden-term offsets,
    each excused by a DIFFERENT lineContains phrase, where `g_line_has_any`
    (manual-lint.sh:848) excuses the whole line the instant EITHER phrase is
    present. Removing either phrase ALONE therefore changes nothing (the
    other still excuses the whole line); only removing BOTH together turns
    the line into two errors.

    This is exactly the case KNOWN_JOINTLY_LOAD_BEARING_PAIRS's own comment
    documents for "skill.md" / "SKILL system filenames": the single-entry
    `test_every_pinned_context_entry_still_excuses_a_real_occurrence`
    exhaustion test classifies BOTH as individually spent, forever -- by
    construction, a per-entry probe cannot observe a NECESSARY PAIR. This
    test is the mechanical, pinned proof that the SHAPE is real (removing
    both together IS an error), on a synthetic fixture rather than the live
    corpus -- module docstring's own convention, and the reason this stays
    true even if instincts.md's own wording changes later.
    `RealCorpusRegressionTest.test_the_individually_spent_set_is_not_
    jointly_spent` is the companion proof against the REAL corpus (CCP-1163
    third cut): that these specific two entries, on this specific real
    line, are the pair -- this test proves the shape is possible, that one
    proves it is what is actually happening at instincts.md:87."""

    def test_removing_either_alone_stays_silent_but_both_together_errors(self):
        self.write(
            "x.md", DOC + "Avoid skill.md and SKILL system filenames alike.\n"
        )
        config = [{
            "term": "skill",
            "lineContains": ["skill.md", "SKILL system filenames"],
        }]

        both = self.run_lint(config)
        without_first = self.run_lint(
            [{"term": "skill", "lineContains": ["SKILL system filenames"]}]
        )
        without_second = self.run_lint(
            [{"term": "skill", "lineContains": ["skill.md"]}]
        )
        without_either = self.run_lint([{"term": "skill", "lineContains": []}])

        # Liveness proof (code-reviewer finding, CCP-1163 second cut, same
        # convention this module's own LineContextTest/PathContextTest
        # already follow): "0 errors" alone cannot distinguish a real clean
        # run from a crashed subprocess with empty stdout -- assert the file
        # was actually scanned on every "silent" sub-case, not just the one
        # that expects errors.
        self.assertIn("**Files scanned:** 1", both.stdout, both.stdout)
        self.assertIn(
            "**Files scanned:** 1", without_first.stdout, without_first.stdout
        )
        self.assertIn(
            "**Files scanned:** 1", without_second.stdout, without_second.stdout
        )
        self.assertIn(
            "**Files scanned:** 1", without_either.stdout, without_either.stdout
        )

        self.assertEqual(check_g_errors(both.stdout), [], both.stdout)
        self.assertEqual(
            check_g_errors(without_first.stdout), [], without_first.stdout
        )
        self.assertEqual(
            check_g_errors(without_second.stdout), [], without_second.stdout
        )
        self.assertEqual(
            len(check_g_errors(without_either.stdout)), 2, without_either.stdout
        )


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

    def _errors_over_roots(self, config, roots):
        """check-(g) error lines from a real subprocess run of manual-lint.sh
        over EACH of `roots` (against this class's `git archive HEAD`
        snapshot, one invocation per root -- the same shape
        test_wired_roots_produce_zero_check_g_errors already uses, factored
        out so the exhaustion tests below can share it). Returns the list of
        raw error strings, not a count, so callers can inspect WHICH site
        changed, not just how many."""
        errors = []
        for root_name in roots:
            root = self.archive_dir / root_name
            result = run_lint(root, config=config)
            errors.extend(check_g_errors(result.stdout))
        return errors

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

    def test_every_pinned_context_entry_still_excuses_a_real_occurrence(self):
        """Exhaustion for PINNED_CONTEXT_ENTRIES -- the second half of the
        pin, KNOWN_POST_CONTRACT_EDITS's shape in test_agent_frontmatter.py.
        A pin stops a list growing silently; this stops a SPENT entry
        lingering as a blanket excuse with nothing behind it, where the next
        drift would hide. An entry earns its place only if REMOVING it turns
        at least one real occurrence into a check-(g) error -- measured
        fresh via a real subprocess run, never guessed or asserted
        plausible.

        SCOPE, corrected (CCP-1163 third cut, module docstring "Third cut"
        section): measured over WIRED_ROOTS, not the whole repository
        archive. check-all.sh never scans the whole repository -- an entry
        that is load-bearing OUTSIDE WIRED_ROOTS but excuses nothing INSIDE
        it is, for THIS check's actual production scope, spent, and the
        prior (whole-archive) scope hid exactly that gap for four
        pathContains entries (module docstring). This test's own per-entry
        result -- the RAW, method-limited measurement, kept honestly
        separate from what is actually redundant -- is
        KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES, not KNOWN_SPENT_CONTEXT_
        ENTRIES (the latter is now the narrower, genuinely-redundant subset;
        see the three constants' own comments and the other tests in this
        class for the joint-removal and out-of-scope controls a per-entry
        probe cannot provide on its own)."""
        full_config = forbidden_prose_config()
        baseline = self._errors_over_roots(full_config, WIRED_ROOTS)
        measured_individually_spent = set()

        for term, list_name, value in sorted(PINNED_CONTEXT_ENTRIES):
            mutated_config = _config_without_entry(
                full_config, term, list_name, value
            )
            mutated = self._errors_over_roots(mutated_config, WIRED_ROOTS)
            is_load_bearing = len(mutated) > len(baseline)
            if (term, list_name, value) in KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES:
                with self.subTest(
                    term=term, list_name=list_name, value=value,
                    expect="known-individually-spent",
                ):
                    self.assertFalse(
                        is_load_bearing,
                        "{}/{} {!r} is pinned in KNOWN_INDIVIDUALLY_SPENT_"
                        "CONTEXT_ENTRIES as non-load-bearing under "
                        "WIRED_ROOTS, but removing it DID turn a real "
                        "occurrence into a check-(g) error -- it has become "
                        "load-bearing again and belongs off every "
                        "classification list".format(term, list_name, value),
                    )
            else:
                with self.subTest(term=term, list_name=list_name, value=value):
                    self.assertTrue(
                        is_load_bearing,
                        "{}/{} {!r} excuses no real occurrence anywhere "
                        "under WIRED_ROOTS -- removing it produced no new "
                        "check-(g) finding, so it is spent".format(
                            term, list_name, value
                        ),
                    )
            if not is_load_bearing:
                measured_individually_spent.add((term, list_name, value))

        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from pin_registry import assert_set_matches

        assert_set_matches(  # pin: set forbidden-prose-spent-entries
            self, KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES,
            measured_individually_spent,
            "check (g)'s currently non-load-bearing-under-WIRED_ROOTS "
            "context entries (per-entry method -- see "
            "test_the_individually_spent_set_is_not_jointly_spent for the "
            "joint-removal control this method cannot provide on its own)",
        )

    def test_the_individually_spent_set_is_not_jointly_spent(self):
        """Finding 1 (CCP-1163 third cut, module docstring): the per-entry
        probe above cannot see a NECESSARY PAIR. Removing
        KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES as a WHOLE must NOT reach
        the WIRED_ROOTS baseline -- it must redden at exactly the two
        `skill` offsets on instincts.md:87 that KNOWN_JOINTLY_LOAD_BEARING_
        PAIRS' one pair jointly protects, and nowhere else."""
        full_config = forbidden_prose_config()
        baseline_errors = self._errors_over_roots(full_config, WIRED_ROOTS)

        joint_removed_config = full_config
        for term, list_name, value in KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES:
            joint_removed_config = _config_without_entry(
                joint_removed_config, term, list_name, value
            )
        joint_errors = self._errors_over_roots(joint_removed_config, WIRED_ROOTS)

        self.assertGreater(
            len(joint_errors), len(baseline_errors),
            "KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES stayed silent when "
            "removed as a whole -- Finding 1's pair is no longer jointly "
            "load-bearing and KNOWN_JOINTLY_LOAD_BEARING_PAIRS is stale "
            "(should shrink)",
        )
        new_sites = {
            line.split(" — ")[0].strip("- ")
            for line in set(joint_errors) - set(baseline_errors)
        }
        self.assertEqual(
            new_sites, {"instincts.md:87:22", "instincts.md:87:34"},
            f"expected the joint removal to redden exactly instincts.md:87's "
            f"two 'skill' offsets; new sites were {new_sites} "
            f"({len(joint_errors)} joint errors, {len(baseline_errors)} "
            f"baseline)",
        )

        # And: removing the individually-spent set MINUS the known pair
        # stays silent -- the regression above is attributable to the pair
        # alone, not spread across the other seven members.
        pair_members = frozenset().union(*KNOWN_JOINTLY_LOAD_BEARING_PAIRS)
        rest_removed_config = full_config
        for term, list_name, value in (
            KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES - pair_members
        ):
            rest_removed_config = _config_without_entry(
                rest_removed_config, term, list_name, value
            )
        rest_errors = self._errors_over_roots(rest_removed_config, WIRED_ROOTS)
        self.assertEqual(
            len(rest_errors), len(baseline_errors),
            "removing the individually-spent set MINUS the known pair "
            "still regresses -- a further jointly load-bearing group "
            "exists beyond KNOWN_JOINTLY_LOAD_BEARING_PAIRS",
        )

    def test_out_of_scope_entries_become_load_bearing_once_their_path_is_scanned(
        self,
    ):
        """Finding 2, group 2 (module docstring): KNOWN_OUT_OF_SCOPE_
        CONTEXT_ENTRIES excuse nothing under WIRED_ROOTS not because a
        sibling already covers them, but because their own path is never
        scanned. Proven by measurement, not argument: for each entry, add
        its own path (OUT_OF_SCOPE_EXTRA_ROOT) as an extra scanned root --
        also stripping OUT_OF_SCOPE_ALSO_REMOVE's one sibling first, for the
        one entry ("skill-interface") whose own occurrences always co-occur
        with a whole-file exemption that would otherwise mask it (that
        dict's own comment explains why -- the first version of this test
        asserted "docs" alone was enough for skill-interface and caught
        itself wrong, 0 vs. 0) -- and confirm removing the entry THEN
        produces MORE errors than removing it WITHOUT the extra root,
        isolating the entry's own effect from whatever pre-existing,
        unrelated findings that root may already carry (docs/, in
        particular, carries findings entirely unrelated to this ticket --
        check-all.sh's own comment on why it stays unwired). A bare count
        increase cannot tell "the expected occurrence surfaced" from "some
        unrelated occurrence surfaced instead" (code-reviewer finding,
        CCP-1163 third cut), so this also asserts at least one of the NEW
        error lines names the entry's own known file
        (OUT_OF_SCOPE_EXPECTED_NEW_ERROR_FILE)."""
        full_config = forbidden_prose_config()
        for term, list_name, value in sorted(KNOWN_OUT_OF_SCOPE_CONTEXT_ENTRIES):
            extra_root = OUT_OF_SCOPE_EXTRA_ROOT[(term, list_name, value)]
            roots = WIRED_ROOTS + (extra_root,)
            baseline_config = full_config
            also_remove = OUT_OF_SCOPE_ALSO_REMOVE.get((term, list_name, value))
            if also_remove:
                baseline_config = _config_without_entry(
                    baseline_config, term, *also_remove
                )
            with self.subTest(term=term, list_name=list_name, value=value):
                with_entry = self._errors_over_roots(baseline_config, roots)
                mutated_config = _config_without_entry(
                    baseline_config, term, list_name, value
                )
                without_entry = self._errors_over_roots(mutated_config, roots)
                self.assertGreater(
                    len(without_entry), len(with_entry),
                    "{}/{} {!r} did not become load-bearing once {}/ was "
                    "scanned -- it may be genuinely redundant, not merely "
                    "out-of-scope, and belongs in KNOWN_SPENT_CONTEXT_"
                    "ENTRIES instead".format(
                        term, list_name, value, extra_root
                    ),
                )
                new_errors = set(without_entry) - set(with_entry)
                expected_file = OUT_OF_SCOPE_EXPECTED_NEW_ERROR_FILE[
                    (term, list_name, value)
                ]
                self.assertTrue(
                    any(expected_file in line for line in new_errors),
                    "{}/{} {!r} produced new errors, but none of them "
                    "named the expected file {!r} -- {}".format(
                        term, list_name, value, expected_file, new_errors
                    ),
                )

    def test_genuinely_redundant_entries_are_confirmed_by_their_sibling(self):
        """Finding 2, group 3 (module docstring): KNOWN_SPENT_CONTEXT_
        ENTRIES excuse nothing under WIRED_ROOTS because a DIFFERENT,
        still-load-bearing sibling already excuses every occurrence they
        would. Proven by measurement: removing the entry TOGETHER WITH its
        named sibling(s) (REDUNDANT_ENTRY_SIBLINGS) must produce MORE errors
        than the WIRED_ROOTS baseline -- a real occurrence exists there, it
        is simply already covered -- distinguishing genuine redundancy from
        "never excused anything, anywhere". A bare count increase cannot
        tell "the expected occurrence surfaced" from "something unrelated
        did" (code-reviewer finding, CCP-1163 third cut), so this also
        asserts at least one of the NEW error lines names one of the
        entry's own known files (REDUNDANT_ENTRY_EXPECTED_NEW_ERROR_FILES)."""
        full_config = forbidden_prose_config()
        baseline_errors = self._errors_over_roots(full_config, WIRED_ROOTS)

        for term, list_name, value in sorted(KNOWN_SPENT_CONTEXT_ENTRIES):
            siblings = REDUNDANT_ENTRY_SIBLINGS[(term, list_name, value)]
            with self.subTest(term=term, list_name=list_name, value=value):
                combined_config = _config_without_entry(
                    full_config, term, list_name, value
                )
                for sibling_list, sibling_value in siblings:
                    combined_config = _config_without_entry(
                        combined_config, term, sibling_list, sibling_value
                    )
                combined_errors = self._errors_over_roots(
                    combined_config, WIRED_ROOTS
                )
                self.assertGreater(
                    len(combined_errors), len(baseline_errors),
                    "{}/{} {!r} removed together with its sibling(s) {} "
                    "stayed at baseline -- no real occurrence was found "
                    "there, so this entry excuses nothing anywhere and does "
                    "not belong in KNOWN_SPENT_CONTEXT_ENTRIES (a genuinely "
                    "dead entry, not a redundant one)".format(
                        term, list_name, value, siblings
                    ),
                )
                new_errors = set(combined_errors) - set(baseline_errors)
                expected_files = REDUNDANT_ENTRY_EXPECTED_NEW_ERROR_FILES[
                    (term, list_name, value)
                ]
                self.assertTrue(
                    any(
                        expected_file in line
                        for line in new_errors
                        for expected_file in expected_files
                    ),
                    "{}/{} {!r} produced new errors, but none of them "
                    "named any of the expected files {!r} -- {}".format(
                        term, list_name, value, expected_files, new_errors
                    ),
                )

    def test_the_three_way_classification_partitions_the_individually_spent_set(
        self,
    ):
        """Sanity/arithmetic check, no subprocess run needed: the three
        MEASURED classification groups (pair, out-of-scope, genuinely
        spent) must be pairwise disjoint and each must carry its stated
        size -- 2 + 5 + 2 = 9, re-derived from the live constants every run
        rather than stated once in a comment and trusted.

        code-reviewer finding (CCP-1163 third cut): this test does NOT also
        assert `pair_members | KNOWN_OUT_OF_SCOPE_CONTEXT_ENTRIES |
        KNOWN_SPENT_CONTEXT_ENTRIES == KNOWN_INDIVIDUALLY_SPENT_CONTEXT_
        ENTRIES` -- that comparison would be VACUOUS, not a cross-check:
        KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES is itself DEFINED as
        exactly that union expression (its own assignment above), so the
        two sides are the same computation written twice and the
        assertion could never fail regardless of what the three source
        sets actually contain. The four length assertions below are what
        actually carries information here: each recomputes `len()` on a
        LIVE constant, so a future edit that duplicates an entry across
        two groups (changing set membership without changing the union)
        or drops one (shrinking a group without the others compensating)
        reddens exactly one of them."""
        pair_members = frozenset().union(*KNOWN_JOINTLY_LOAD_BEARING_PAIRS)
        groups = (
            pair_members,
            KNOWN_OUT_OF_SCOPE_CONTEXT_ENTRIES,
            KNOWN_SPENT_CONTEXT_ENTRIES,
        )
        for a, b in ((0, 1), (0, 2), (1, 2)):
            with self.subTest(disjoint=(a, b)):
                self.assertEqual(
                    groups[a] & groups[b], set(),
                    f"classification groups {a} and {b} overlap",
                )
        self.assertEqual(len(pair_members), 2)
        self.assertEqual(len(KNOWN_OUT_OF_SCOPE_CONTEXT_ENTRIES), 5)
        self.assertEqual(len(KNOWN_SPENT_CONTEXT_ENTRIES), 2)
        self.assertEqual(len(KNOWN_INDIVIDUALLY_SPENT_CONTEXT_ENTRIES), 9)


if __name__ == "__main__":
    unittest.main()
