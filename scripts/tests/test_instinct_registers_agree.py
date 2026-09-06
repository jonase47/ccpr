r"""test_instinct_registers_agree.py -- WI-0129 finding F14 (the part that
stayed open): CCPR ships starter instincts in two shapes that nothing
compared before this module. `instincts.md` is the shipped snapshot INDEX
-- entries are `- G-NNN [conf] text` bullets. `templates/STARTER_INSTINCTS.
md` is a flat SAMPLER of the same content -- entries are `### G-NNN: title`
headings. Both files also mention a further nine instinct IDs in bold prose
("Intentionally NOT in this starter set" / "What is intentionally NOT...")
that are deliberately excluded from either file's entry set.

CCP-1152 extends this module a second way: the shipped topic files
(`instincts/*.md`) also carry a structural entry shape of their own -- the
SAME `### G-NNN: title` heading `templates/STARTER_INSTINCTS.md` uses, one
per instinct, spread across five files instead of one. Nothing compared
THAT population against the index either, and the gap was not
hypothetical: `instincts/workflow.md` carried a `### G-056: ...` block with
no matching `- G-056 [...]` bullet in `instincts.md` -- a real instinct,
documented in full, invisible from the index a reader actually starts
from. `TopicFileAgreementTest` below closes it the same way
`SubsetAgreementTest` closes the sampler side: both directions checked,
because a topic block with no index bullet and an index bullet with no
topic block are two different defects a one-directional subset check would
only catch by accident.

## Why this exists

`/postmortem` deletes instincts once confidence decays to 0.3 (G-060,
G-063, G-065 were deleted in the most recent round -- the deletion
mechanism is real and active, not hypothetical). If the sampler names an
instinct ID that the index has since dropped, an adopter following the
sampler lands on a dead reference -- and until this module, nothing would
have noticed. A naive `grep -o 'G-[0-9]\{3\}'` over these files counts 55
and 24 total mentions; that number mixes structural ENTRIES with bare
prose MENTIONS and is not a fact about either file's entry set. The
correct, structural counts are 46 (index) and 13 (sampler) -- see
`ClassificationCountsTest` below.

## What counts as an entry vs. a mention

  * An INDEX entry is a line matching `^- (G-\d{3})\b` -- a bullet at the
    start of a line, the literal hyphen-space CCPR uses for every instinct
    bullet in `instincts.md`. Prose referencing an ID inside a paragraph,
    or inside a bold span (`**G-005**`), does not start a line this way
    and is not counted.
  * A SAMPLER entry is a line matching `^### (G-\d{3})\b` -- an ATX
    level-3 heading, the literal shape every `### G-NNN: title` block in
    `templates/STARTER_INSTINCTS.md` uses. The same bold-prose mentions in
    that file's own "Intentionally NOT..." section do not start a line
    this way either.
  * A MENTION is any other occurrence of the `G-\d{3}` token -- in
    particular the nine `**G-NNN**` bold-prose references both files use to
    document instincts they deliberately left out. `ExclusionRegressionPinTest`
    below pins that these nine never leak into either file's parsed entry
    set, which is exactly the distinction a bare `grep -o` collapses.

`parse_index_entries` / `parse_sampler_entries` take TEXT, not a path --
that is the seam this module's own red-proof (see below) needs: pointing
the same parsing logic at a scratch copy under `$TMPDIR`, never at the
tracked files. `read_index_entries` / `read_sampler_entries` are the thin
production wrapper that reads the real repo file and calls the text-level
parser; every acceptance test below calls the wrapper with its default
argument, so it always measures the tracked file, not a fixture.

## Red-proof, without mutating the tracked files (three discriminating
## mutations, run manually against scratch copies before this module was
## accepted -- see the delegation report for the reproduction transcript
## and the replacement-count proof for each)

  (a) Deleting one index bullet whose ID the sampler still uses turns
      `SubsetAgreementTest` red while `NoDuplicateIdsTest` stays green --
      it proves the subset check is load-bearing, not vacuously true.
  (b) Duplicating one sampler heading (same ID twice) turns
      `NoDuplicateIdsTest` red while `SubsetAgreementTest` stays green --
      the two checks catch different defects, not the same one twice.
  (c) Swapping the parser for a bare `G-\d{3}` mentions-grep (matching
      ANY occurrence of the token, not just `^- ` / `^### ` line starts)
      turns `ExclusionRegressionPinTest` red AND moves both
      `ClassificationCountsTest` pins (45 -> 55, 13 -> 24) -- proving the
      structural/mentions distinction is exactly what the counts and the
      exclusion pin depend on, not decoration.
      `ParserDiscriminatesEntriesFromMentionsTest` below is the permanent,
      committed version of this proof: synthetic text containing both an
      entry and a bold-prose mention of a DIFFERENT id, asserting the
      parser returns only the entry.

## CCP-1160: the registers are also compared on WHAT THEY SAY

Until CCP-1160 all three parsers captured the id token and stopped, so the
module established that the registers agree on WHICH instincts exist and
nothing about their wording. That is the exact blind spot a terminology
sweep walks through: a sweep moves no id, so a one-sided sweep of these
registers passed silently green. It was not hypothetical either -- a strict
comparison of the three register pairs reports 23 disagreements over 15 ids
while the suite is green (see `KNOWN_TITLE_DIVERGENCES` and
`ANNOTATION_ABSORBED`).

  * `parse_index_titles` / `parse_sampler_titles` / `parse_topic_titles`
    are the entry parsers with one capture group more: the title beside the
    id. They capture it RAW.
  * `normalise_title` is the only place the comparison's whitespace rule
    lives, and `collect_titles_by_id` is the seam the synthetic tests use.

**The comparison is whitespace-normalised and otherwise EXACT.** Runs of
whitespace collapse and the ends are stripped; case, punctuation,
backticks, dashes and wording are compared byte-for-byte. Both directions
of that line are a decision with a consequence:

  * normalising further -- case-folding, dropping punctuation or backticks
    -- would silently accept the drift this comparison exists to catch. A
    sweep that rewrites `manual` to `handbook` in one register only is a
    word change, and a word change must fail;
  * normalising less -- exact string equality -- would fail on a trailing
    space or a doubled space, neither of which is visible where the title
    is read, producing a failure message naming two titles that look
    identical.

Measured 06.09.2026: the two spellings select the SAME findings in the
tracked files, so the choice costs nothing today and is purely prospective.
Case-folding was proposed separately and rejected on the same kind of
measurement -- it changes nothing in any of the three register pairs
(12 / 7 / 4 divergences either way), so it would buy no agreement and cost
the ability to see a capitalisation sweep.
`TitleComparisonSemanticsTest` tests both sides of the line rather than
asserting it in prose.

**The three registers do not stand in ONE relation, and comparing them as
if they did books design as debt.** `templates/STARTER_INSTINCTS.md` and
`instincts/*.md` are the SAME kind of artifact -- both are
`### G-NNN: Title` headings -- and they disagree 4 times out of the 13 ids
they share. `instincts.md` is a different artifact: a one-liner carrying a
confidence score, which calls itself a slim entry point. So:

  * **sampler <-> topic is STRICT.** Same artifact, no tolerance.
  * **index <-> sampler and index <-> topic are ANNOTATION-TOLERANT.** The
    index may append a trailing parenthetical the heading does not carry.

Measured over the 46 ids the index and the topic files share: 34 titles are
identical, 12 differ, and of those 12 six involve a trailing parenthetical and six are pure wording
differences with no parenthetical at all. Of those six, FOUR are absorbed
(exactly one side annotated) and TWO -- G-016 and G-019 -- carry a
DIFFERENT parenthetical on each side and stay divergent. So the
index/topic pair contributes 4 absorptions and 8 divergences.
The relation is **annotation, not compression** -- the index appends
`(incl. ... sub-rules)` to the rule the heading states bare.

**The rule is "exactly one side is annotated", NOT "strip the parenthetical
from both sides".** The looser reading was measured and rejected: it also
absorbs G-016 and G-019, where both sides carry a parenthetical and the two
say different things (`(incl. multi-command + re-setup + bulk-curation
sub-rules)` against `(multi-command hygiene)`). Two different annotations on
one stem are two statements, not one statement annotated -- and those two
are half of the four divergences CCP-1159 was originally opened for, so the
looser rule would have blinded this guard to its own founding cases.
`RegisterRelationTest` fixes both halves of that distinction in tests.

**What the annotation rule does not protect, stated so it is not
discovered:** a sweep confined to the index's own trailing parenthetical is
invisible here, by construction. The STEM is always compared strictly, so a
sweep that touches the rule text fails whether or not either side is
annotated. And because a tolerance rule silently REMOVES findings,
`ANNOTATION_ABSORBED` pins what it accepts: widen the rule by accident and
the divergence set merely shrinks, which reads like progress.
`test_the_two_registers_partition_the_strict_population` ties the two pins
together -- under a strict comparison of every pair the population is
exactly the declared divergences plus the declared absorptions, disjoint,
with nothing falling between them.

**The sampler's reduced set is not a divergence.**
`templates/STARTER_INSTINCTS.md` carries 13 of the index's 46 entries on
purpose -- its own header says so, and `SubsetAgreementTest` already
encodes the asymmetry. The comparison therefore applies ONLY where an id
appears in two or more registers, and a register that lacks an id is absent
from that id's map rather than present with an empty title. A comparator
that reached a missing register through a `""` default would report 33 of
46 index entries as sampler divergences and look, from outside, exactly
like a working guard. `SamplerReducedSetBoundaryTest` rules that version
out synthetically and against the tracked files.

**The fifteen are DECLARED, not repaired.** Each is a per-title editorial
decision -- which register carries the true statement -- and that work is
CCP-1159. The declared-known-findings shape is
`test_bsd_gnu_portability.py`'s `KnownFindingsMatchTheCurrentScanTest`,
set equality included: a new divergence fails, and so does a STALE entry
left behind after a reconciliation, because a tolerated finding nobody can
see is how the next one hides.

## The boundary this test does NOT cover

This module closes the DRIFT class of defect: an instinct ID that stops
existing in one file while the other still names it, or an entry count
that moves without anyone noticing. Since CCP-1160 it also closes one
slice of the DESCRIPTION class -- the TITLE beside each id, compared
across the registers that carry it.

Two slices of that class remain open, and naming them is the point of this
section. First, the BODY under each topic heading (the Rule / Why / How to
apply paragraphs) is never read here: two registers can carry the same
title over contradictory bodies and this module stays green. Second, prose
in a THIRD document ABOUT these registers is still out of reach, and that
is the defect that prompted the original work item: it was not an ID going
stale, it was `CLAUDE.md`'s "Two ways to adopt the starter content"
section describing the sampler as "the same 13 generic instincts as one
file" -- prose that could read as characterising the sampler/index
RELATIONSHIP in a misleading way even though every NUMBER in it (13) was
and still is correct. No structural ID-comparison test can see that kind
of defect: the numbers can stay pinned and agree perfectly while a THIRD
document mischaracterises what the two files mean relative to each other.
A reader who believes this module closes the whole of finding F14 is
worse off than one who knows this boundary -- this module is silent about
`CLAUDE.md`, `instincts.md`, and `templates/STARTER_INSTINCTS.md`'s own
prose, and was written without touching any of the three. (That
`CLAUDE.md` wording is quoted above for the historical record of why
finding F14 existed, not as a description of the file today -- the same
work item already corrected it, in the commit that is this repo's current
HEAD as this module was written.)
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "instincts.md"
SAMPLER_PATH = REPO_ROOT / "templates" / "STARTER_INSTINCTS.md"
TOPIC_DIR = REPO_ROOT / "instincts"

INDEX_ENTRY_RE = re.compile(r"^- (G-\d{3})\b", re.MULTILINE)
SAMPLER_ENTRY_RE = re.compile(r"^### (G-\d{3})\b", re.MULTILINE)
TOPIC_ENTRY_RE = re.compile(r"^### (G-\d{3}):", re.MULTILINE)

# The same three shapes again, one capture group wider: the TITLE next to
# the id. `(.*)$` is deliberately greedy-to-end-of-line and does NOT trim
# -- see `parse_index_titles` on why normalisation has exactly one home.
INDEX_TITLE_RE = re.compile(r"^- (G-\d{3}) \[[^\]]*\] (.*)$", re.MULTILINE)
SAMPLER_TITLE_RE = re.compile(r"^### (G-\d{3}): (.*)$", re.MULTILINE)
TOPIC_TITLE_RE = re.compile(r"^### (G-\d{3}): (.*)$", re.MULTILINE)

# The nine IDs both files mention in bold prose ("Intentionally NOT in this
# starter set" / "What is intentionally NOT...") but deliberately exclude
# from their entry sets -- see ExclusionRegressionPinTest. G-056 is
# deliberately NOT here (CCP-1152): it used to be, back when both files'
# platform-specific exclusion note named it by ID -- but that ID collided
# with this repo's own, unrelated G-056 ("reconcile dependent stories' ACs"
# in instincts/workflow.md), which never had an index bullet as a result.
# The exclusion note now names the Apple/Xcode instinct without an ID, and
# G-056 is a real, indexed entry -- so it belongs in neither file's
# exclusion set any more, and asserting it stays out of the parsed entry
# set would be asserting the opposite of what the fix requires.
EXCLUDED_MENTION_ONLY_IDS = frozenset(
    {
        "G-005",
        "G-046",
        "G-047",
        "G-054",
        "G-055",
        "G-058",
        "G-059",
        "G-062",
        "G-063",
    }
)


def parse_index_entries(text):
    """Structural parse of index-shape entries (`- G-NNN [conf] ...`
    bullets) out of TEXT. Takes text, not a path -- the seam scratch-copy
    red-proofs point at."""
    return INDEX_ENTRY_RE.findall(text)


def parse_sampler_entries(text):
    """Structural parse of sampler-shape entries (`### G-NNN: title`
    headings) out of TEXT. Takes text, not a path -- same seam as
    `parse_index_entries`."""
    return SAMPLER_ENTRY_RE.findall(text)


def read_index_entries(path=INDEX_PATH):
    """Production wrapper: reads the real index file and parses it.
    Every acceptance test below calls this with the default argument, so
    it always measures the tracked `instincts.md`, never a fixture."""
    return parse_index_entries(path.read_text(encoding="utf-8"))


def read_sampler_entries(path=SAMPLER_PATH):
    """Production wrapper: reads the real sampler file and parses it.
    Every acceptance test below calls this with the default argument, so
    it always measures the tracked `templates/STARTER_INSTINCTS.md`,
    never a fixture."""
    return parse_sampler_entries(path.read_text(encoding="utf-8"))


def parse_topic_entries(text):
    """Structural parse of topic-file-shape entries (`### G-NNN: title`
    headings, same shape as the sampler's) out of TEXT. Takes text, not a
    path -- same seam as `parse_index_entries` / `parse_sampler_entries`.
    Deliberately its own regex object (`TOPIC_ENTRY_RE`) rather than reused
    from `SAMPLER_ENTRY_RE`, even though the shape is identical today: the
    two populations are checked against different things below (the index,
    not the sampler), and a future divergence in either shape should not
    silently change the other's behaviour."""
    return TOPIC_ENTRY_RE.findall(text)


def read_topic_entries(topic_dir=TOPIC_DIR):
    """Production wrapper: reads every tracked `instincts/*.md` topic file
    and returns rel-filename -> parsed entry IDs. Every acceptance test
    below calls this with the default argument, so it always measures the
    tracked topic files, never a fixture."""
    return {
        path.name: parse_topic_entries(path.read_text(encoding="utf-8"))
        for path in sorted(topic_dir.glob("*.md"))
    }

def parse_index_titles(text):
    """Structural parse of index-shape entries into `id -> RAW title` -- the
    text after the confidence bracket in a `- G-NNN [conf] title` bullet.
    Takes text, not a path: same seam as `parse_index_entries`.

    The title is captured RAW, untrimmed, on purpose. `normalise_title` is
    the single place the comparison's whitespace rule lives; a parser that
    trimmed on its own would put half that rule somewhere no test of the
    rule can see it."""
    return dict(INDEX_TITLE_RE.findall(text))


def parse_sampler_titles(text):
    """Structural parse of sampler-shape entries into `id -> RAW title` --
    the text after the colon in a `### G-NNN: title` heading. Same seam and
    the same raw-capture rule as `parse_index_titles`."""
    return dict(SAMPLER_TITLE_RE.findall(text))


def parse_topic_titles(text):
    """Structural parse of topic-file-shape entries into `id -> RAW title`.
    Its own regex object rather than `SAMPLER_TITLE_RE`, for the reason
    `parse_topic_entries` already states: the shape is identical today, the
    two populations are compared against different things, and a future
    divergence in one shape must not silently move the other."""
    return dict(TOPIC_TITLE_RE.findall(text))


def read_index_titles(path=INDEX_PATH):
    """Production wrapper: the tracked `instincts.md`, never a fixture."""
    return parse_index_titles(path.read_text(encoding="utf-8"))


def read_sampler_titles(path=SAMPLER_PATH):
    """Production wrapper: the tracked `templates/STARTER_INSTINCTS.md`."""
    return parse_sampler_titles(path.read_text(encoding="utf-8"))


def read_topic_titles(topic_dir=TOPIC_DIR):
    """Production wrapper: every tracked `instincts/*.md`, merged into one
    `id -> RAW title` map.

    Merging across files is safe because
    `NoDuplicateIdsTest.test_topic_files_have_no_duplicate_ids_across_files`
    already forbids one id appearing in two topic files; the sorted file
    order below only makes the outcome deterministic if that guard ever
    goes red, so the two failures do not interleave."""
    merged = {}
    for path in sorted(topic_dir.glob("*.md")):
        merged.update(parse_topic_titles(path.read_text(encoding="utf-8")))
    return merged

# The three register labels, in the order the records below sort them.
# `topic` is the whole `instincts/` directory rather than one file per
# entry: which topic file carries an instinct is editorial filing, not a
# statement about what the instinct SAYS, and putting the filename in a
# record's identity would make every topic-file reorganisation look like a
# title divergence.
REGISTER_LABELS = ("index", "sampler", "topic")

# --------------------------------------------------------------------------
# The two relations (CCP-1160 second cut, PO decision 06.09.2026)
# --------------------------------------------------------------------------
#
# The three registers do NOT stand in one relation, and comparing them as if
# they did books design as debt. `templates/STARTER_INSTINCTS.md` and
# `instincts/*.md` are the same kind of artifact -- both are
# `### G-NNN: Title` headings -- and they disagree 4 times out of 13.
# `instincts.md` is a different artifact: a one-liner carrying a confidence
# score, which calls itself a slim entry point.
#
# Measured before the rule was adopted, over the 46 ids the index and the
# topic files share: 34 titles identical, 12 different; of those 12, six involve a trailing parenthetical and six are pure wording
# differences with no parenthetical at all. Of those six, FOUR are absorbed
# (exactly one side annotated) and TWO -- G-016 and G-019 -- carry a
# DIFFERENT parenthetical on each side and stay divergent. So the
# index/topic pair contributes 4 absorptions and 8 divergences.
# The relation is ANNOTATION, not compression -- the index APPENDS
# `(incl. ... sub-rules)` to the rule the heading states bare.
STRICT = "strict"
ANNOTATION_TOLERANT = "annotation-tolerant"

REGISTER_RELATIONS = {
    ("index", "sampler"): ANNOTATION_TOLERANT,
    ("index", "topic"): ANNOTATION_TOLERANT,
    ("sampler", "topic"): STRICT,
}

# A trailing parenthetical, and only a trailing one. Anchored at `$` and
# with `[^()]*` rather than `.*`, so an INTERNAL parenthetical is never
# touched: `instincts/external.md`'s G-026 carries "(and other SKILL system
# filenames)" in the middle of its rule, where it is part of the statement.
# Stripping that would dissolve a real divergence CCP-1159 has to decide.
#
# ONE non-nested trailing group, and no more. Two shapes are deliberately
# NOT stripped, and both fail SAFE -- the stems stay unequal, so the pair is
# reported as a divergence rather than silently absorbed:
#   * a NESTED trailing group ("... (incl. sub (detail) rule)") -- `[^()]*`
#     cannot reach past the inner parens, so the title is left whole;
#   * TWO separate trailing groups ("... (p1) (p2)") -- only the last is
#     removed and the first stays in the stem.
# Measured 06.09.2026: neither shape occurs in any of the 105 titles the
# three registers carry today, so this is a prospective boundary, not a
# live exemption.
TRAILING_PARENTHETICAL_RE = re.compile(r"\s*\([^()]*\)\s*$")


def title_stem(title):
    """A normalised title with one trailing parenthetical removed."""
    return TRAILING_PARENTHETICAL_RE.sub("", title).strip()


def titles_agree(relation, title_a, title_b):
    """Whether two NORMALISED titles agree under `relation`.

    Under `STRICT` this is plain equality. Under `ANNOTATION_TOLERANT` a
    difference is also accepted when the stems are identical AND EXACTLY ONE
    side carries a trailing parenthetical.

    That "exactly one" is the whole rule, and it is not the same as
    "strip the parenthetical from both sides". The looser reading was
    measured and REJECTED: it also absorbs G-016 and G-019, where BOTH sides
    carry a parenthetical and the two say different things
    ("(incl. multi-command + re-setup + bulk-curation sub-rules)" against
    "(multi-command hygiene)"). Those are two statements, not one statement
    annotated -- and they are two of the four divergences CCP-1159 was
    originally opened for, so the looser rule would have made this guard
    blind to half of its own founding cases.

    What the accepted rule does NOT protect is the index's own trailing
    parenthetical: a sweep confined to it is invisible here, by
    construction. The stem is always compared strictly, so a sweep that
    touches the rule text fails whether or not either side is annotated."""
    if title_a == title_b:
        return True
    if relation == STRICT:
        return False
    stem_a, stem_b = title_stem(title_a), title_stem(title_b)
    if stem_a != stem_b:
        return False
    if not stem_a:
        # Both titles reduce to nothing -- one of them IS a parenthetical
        # and the other is empty. An empty title agrees with nothing: it is
        # a malformed entry, not an un-annotated one. Without this the XOR
        # below reports agreement, which is the one wrong answer the rule
        # can give. Guarded again at the source by
        # `test_no_register_carries_an_empty_title`, so the shape stays
        # unreachable in the tracked files rather than merely handled.
        return False
    return (stem_a != title_a) != (stem_b != title_b)


def normalise_title(title):
    """The comparison's whitespace rule, in one place.

    Runs of whitespace collapse to a single space and the ends are
    stripped. Everything else -- case, punctuation, backticks, dashes,
    wording -- is compared EXACTLY. See `TitleComparisonSemanticsTest` for
    the boundary as a test, and the module docstring for why the line sits
    here and not further out.

    Case-folding was proposed and REJECTED on measurement: it changes
    nothing in any of the three register pairs today (12 / 7 / 4
    divergences either way), so it would buy no agreement and cost the
    ability to see a capitalisation sweep.

    One consequence worth naming rather than discovering: `str.split()`
    treats a non-breaking space as whitespace, so a NBSP/space difference
    is accepted too. That is the same class as a doubled space -- invisible
    where the title is read -- and it is accepted on the same grounds."""
    return " ".join(title.split())


def collect_titles_by_id(index_titles, sampler_titles, topic_titles):
    """`id -> {register: NORMALISED title}`, over the three raw title maps.

    Takes maps, not paths: this is the seam the synthetic boundary tests
    below need, the same seam `parse_index_entries` is for the id-level
    checks. A register that does not carry an id is ABSENT from that id's
    map -- never present with an empty title. That distinction is the whole
    sampler-boundary rule (`SamplerReducedSetBoundaryTest`)."""
    by_id = {}
    for register, titles in zip(
            REGISTER_LABELS, (index_titles, sampler_titles, topic_titles)):
        for gid, title in titles.items():
            by_id.setdefault(gid, {})[register] = normalise_title(title)
    return by_id


def _pair_findings(by_id, relation_of):
    """Every `(id, register_a, register_b, title_a, title_b)` record for
    which `relation_of` reports disagreement.

    One record per REGISTER PAIR, not per id: which two registers disagree
    is what CCP-1159 needs in order to decide which one carries the true
    statement, and an id-keyed record hides it. A pair is only examined
    where BOTH its registers carry the id."""
    found = set()
    for gid, registers in by_id.items():
        for (reg_a, reg_b), relation in REGISTER_RELATIONS.items():
            if reg_a not in registers or reg_b not in registers:
                continue
            title_a, title_b = registers[reg_a], registers[reg_b]
            if not relation_of(relation, title_a, title_b):
                found.add((gid, reg_a, reg_b, title_a, title_b))
    return found


def title_divergences(by_id):
    """The findings under each pair's DECLARED relation."""
    return _pair_findings(by_id, titles_agree)


def strict_divergences(by_id):
    """The findings a strict comparison of every pair would report -- the
    population the annotation rule is subtracted from. Pinned alongside the
    divergences so the rule's own effect stays accountable."""
    return _pair_findings(by_id, lambda _relation, a, b: a == b)


def annotation_absorbed(by_id):
    """What the annotation rule accepts that a strict comparison would
    report. A tolerance rule silently REMOVES findings, so this is the set
    that must not grow unnoticed."""
    return strict_divergences(by_id) - title_divergences(by_id)


def _measured_by_id():
    return collect_titles_by_id(
        read_index_titles(), read_sampler_titles(), read_topic_titles())


def measured_title_divergences():
    """Production wrapper: the three tracked registers, never a fixture."""
    return title_divergences(_measured_by_id())


def measured_strict_divergences():
    """Production wrapper for the pre-rule population."""
    return strict_divergences(_measured_by_id())


def measured_annotation_absorbed():
    """Production wrapper for what the annotation rule accepts."""
    return annotation_absorbed(_measured_by_id())


# --------------------------------------------------------------------------
# The declared known title divergences (CCP-1160)
# --------------------------------------------------------------------------
#
# DECLARED, NOT ACCEPTED-AND-FORGOTTEN. Each record is a REGISTER PAIR that
# carries the same instinct id under different wording today. They are
# pinned in full text rather than repaired, because each repair is a
# per-title editorial decision -- which register carries the true statement
# -- and that work is CCP-1159 (extended by PO decision to all of them).
# Reconciling one there removes its record here in the same cut, so the
# accepted count can only go DOWN; the set equality in `TitleAgreementTest`
# fails on a stale record exactly as loudly as on a new divergence.
#
# MEASURED 06.09.2026, and the measurement corrected the work item it came
# from. CCP-1159/CCP-1160 both stated "10 title-bearing instincts in >= 2
# registers (25 occurrences)" and FOUR divergences. Re-measured against the
# tracked files: 46 ids appear in >= 2 registers across 105 occurrences, and
# a strict comparison of all three pairs reports 23 findings over 15 ids
# (index/topic 12, index/sampler 7, sampler/topic 4). Cross-checked with two
# instruments other than this module -- a `/usr/bin/grep` + `sed` extraction
# of all 105 (id, register, title) rows, diffed byte-for-byte, and an `awk`
# pass over that table arriving at the same ids independently.
#
# 18 of those 23 survive the annotation rule, over 11 distinct ids. The
# other five are in ANNOTATION_ABSORBED below.
KNOWN_TITLE_DIVERGENCES = frozenset({
    ('G-009', 'index', 'sampler',
     'Agent prompts: always specify exact file paths (incl. folder-disambiguation sub-rule)',
     'Agent prompts always specify exact file paths'),
    ('G-014', 'index', 'sampler',
     'Delegate bulk file operations',
     'Delegate bulk file operations to parallel agents'),
    ('G-016', 'index', 'sampler',
     'End sessions after 2 sprints (incl. multi-command + re-setup + bulk-curation sub-rules)',
     'End sessions after 2 sprints (multi-command hygiene)'),
    ('G-025', 'index', 'sampler',
     'Minimise read-heavy pre-briefing when the agent reads on its own',
     'Read share in command sessions'),
    ('G-030', 'index', 'sampler',
     'Orchestrator reads with a verified filename via `ls` / `Glob`',
     'Orchestrator reads with verified filename via ls / Glob'),
    ('G-048', 'index', 'sampler',
     'Mass substitution via find+xargs+perl',
     'Mass substitution via find+xargs+perl instead of a bash for-loop'),
    ('G-009', 'index', 'topic',
     'Agent prompts: always specify exact file paths (incl. folder-disambiguation sub-rule)',
     'Agent prompts always specify exact file paths'),
    ('G-016', 'index', 'topic',
     'End sessions after 2 sprints (incl. multi-command + re-setup + bulk-curation sub-rules)',
     'End sessions after 2 sprints (multi-command hygiene)'),
    ('G-018', 'index', 'topic',
     'Edit "String not found" → grep-then-edit (incl. subagent-shared + boundary + proactive-writes sub-rules)',
     'Edit "String not found" → grep-then-edit recovery'),
    ('G-019', 'index', 'topic',
     'Multi-agent commands via temp-files (parallel + sequential)',
     'Multi-agent commands via temp-files (extends G-008; parallel + sequential)'),
    ('G-026', 'index', 'topic',
     'Avoid `skill.md` / SKILL system filenames on macOS',
     'Avoid `skill.md` (and other SKILL system filenames) in `.claude/commands/` on macOS'),
    ('G-031', 'index', 'topic',
     '`claude mcp add` — server name as first positional',
     '`claude mcp add` — server name as the first positional, not after `-s` / `-e` flags'),
    ('G-048', 'index', 'topic',
     'Mass substitution via find+xargs+perl',
     'Mass substitution via find+xargs+perl instead of bash for-loop'),
    ('G-067', 'index', 'topic',
     'StagnationWarning is a false-positive during long subagents OR user-decision waits',
     'StagnationWarning is a false-positive during long-running subagents or user-decision waits'),
    ('G-014', 'sampler', 'topic',
     'Delegate bulk file operations to parallel agents',
     'Delegate bulk file operations'),
    ('G-025', 'sampler', 'topic',
     'Read share in command sessions',
     'Minimise read-heavy pre-briefing when the agent reads on its own'),
    ('G-030', 'sampler', 'topic',
     'Orchestrator reads with verified filename via ls / Glob',
     'Orchestrator reads with a verified filename via `ls` / `Glob`'),
    ('G-048', 'sampler', 'topic',
     'Mass substitution via find+xargs+perl instead of a bash for-loop',
     'Mass substitution via find+xargs+perl instead of bash for-loop'),
})


# What the annotation rule accepts. Four ids, five pairs -- in every one of
# them the index appends a parenthetical to the bare rule the heading states.
#
# Pinned for two different reasons, and only the second is exclusive to it.
# (1) AUDIT: what a tolerance rule swallows should be readable in one place
#     rather than derived by diffing two sets. A widening of the rule moves
#     a record from KNOWN_TITLE_DIVERGENCES to here, and the divergence pin
#     already fails on that by itself.
# (2) DETECTION THE DIVERGENCE PIN CANNOT DO: when an index title GAINS a
#     trailing parenthetical whose heading counterpart is bare, the pair
#     becomes absorbed WITHOUT ever having been a divergence. The strict
#     population grows, the divergence set does not move, and the divergence
#     pin stays green. Only this register sees it. See
#     `RegisterRelationTest.test_a_new_annotation_is_caught_by_the_absorbed_pin_alone`.
ANNOTATION_ABSORBED = frozenset({
    ('G-017', 'index', 'sampler',
     'Large files require offset/limit on Read (incl. HANDOVER + phase-3 + subagent-briefing sub-rules)',
     'Large files require offset/limit on Read'),
    ('G-002', 'index', 'topic',
     'Review / consolidation agents — write boundaries (incl. wingman sub-rule)',
     'Review / consolidation agents — write boundaries'),
    ('G-017', 'index', 'topic',
     'Large files require offset/limit on Read (incl. HANDOVER + phase-3 + subagent-briefing sub-rules)',
     'Large files require offset/limit on Read'),
    ('G-020', 'index', 'topic',
     'WebFetch bot-protection → Playwright-MCP fallback (incl. academic-paywall sub-rule)',
     'WebFetch bot-protection → Playwright-MCP fallback'),
    ('G-024', 'index', 'topic',
     'Consolidate the multi-pass sequence in the first briefing (incl. TDD + multi-tranche sub-rules)',
     'Consolidate the multi-pass sequence in the first briefing'),
})


class SubsetAgreementTest(unittest.TestCase):
    def test_every_sampler_id_exists_in_the_index(self):
        index_ids = set(read_index_entries())
        sampler_ids = read_sampler_entries()
        missing = sorted(gid for gid in sampler_ids if gid not in index_ids)
        self.assertEqual(
            [],
            missing,
            "templates/STARTER_INSTINCTS.md names an instinct ID that "
            "instincts.md no longer carries as an entry -- either the "
            "index deleted it (decay/postmortem) and the sampler is now a "
            "dead reference, or the sampler ID was mistyped: "
            + ", ".join(missing),
        )


class NoDuplicateIdsTest(unittest.TestCase):
    def test_index_has_no_duplicate_ids(self):
        ids = read_index_entries()
        dupes = sorted({gid for gid in ids if ids.count(gid) > 1})
        self.assertEqual(
            [],
            dupes,
            "instincts.md lists the same instinct ID as more than one "
            "bullet entry: " + ", ".join(dupes),
        )

    def test_sampler_has_no_duplicate_ids(self):
        ids = read_sampler_entries()
        dupes = sorted({gid for gid in ids if ids.count(gid) > 1})
        self.assertEqual(
            [],
            dupes,
            "templates/STARTER_INSTINCTS.md lists the same instinct ID "
            "as more than one heading entry: " + ", ".join(dupes),
        )

    def test_topic_files_have_no_duplicate_ids_across_files(self):
        """A duplicate here is worse than a within-file one: two different
        topic files both claiming the same ID is two different Rule/Why/How
        bodies for one index bullet, and nothing about a per-file duplicate
        check would ever see it."""
        by_file = read_topic_entries()
        all_ids = [gid for ids in by_file.values() for gid in ids]
        dupes = sorted({gid for gid in all_ids if all_ids.count(gid) > 1})
        self.assertEqual(
            [],
            dupes,
            "instincts/*.md topic files list the same instinct ID as more "
            "than one heading entry (possibly across different files): "
            + ", ".join(dupes),
        )


class TopicFileAgreementTest(unittest.TestCase):
    """CCP-1152: closes the gap that let `instincts/workflow.md` carry a
    `### G-056: ...` block with no matching index bullet go unnoticed --
    `SubsetAgreementTest` only ever compared the index against the
    SAMPLER, never against the topic files the index itself links to. Both
    directions checked, same reasoning as the sampler's own subset test:
    an index bullet with no topic block (a dangling reference the reader
    follows to nothing) and a topic block with no index bullet (a fully
    written instinct invisible from the autoloaded entry point) are two
    different defects, not one."""

    def test_every_index_id_has_a_matching_topic_block(self):
        index_ids = set(read_index_entries())
        topic_ids = {gid for ids in read_topic_entries().values() for gid in ids}
        missing = sorted(index_ids - topic_ids)
        self.assertEqual(
            [],
            missing,
            "instincts.md carries an index bullet whose ID has no `### "
            "G-NNN: ...` block in any instincts/*.md topic file: "
            + ", ".join(missing),
        )

    def test_every_topic_block_id_has_a_matching_index_bullet(self):
        index_ids = set(read_index_entries())
        topic_ids = {gid for ids in read_topic_entries().values() for gid in ids}
        missing = sorted(topic_ids - index_ids)
        self.assertEqual(
            [],
            missing,
            "An instincts/*.md topic file carries a `### G-NNN: ...` block "
            "with no matching bullet in instincts.md -- the exact CCP-1152 "
            "defect shape (instincts/workflow.md's G-056 had a full Rule/"
            "Why/How block and no index entry): " + ", ".join(missing),
        )


class ExclusionRegressionPinTest(unittest.TestCase):
    """Pin against a future parser regression that starts counting bare
    `G-\\d{3}` mentions (e.g. the nine IDs both files reference in bold
    prose under "Intentionally NOT...") instead of structural entries.
    See mutation (c) in the module docstring: a mentions-grep parser turns
    both assertions here red.

    WI-0133 T3: two `set` pins, one id each. The pinned value is the whole
    leaked collection rather than a count of it, so the failure message can
    name which ID leaked -- the property the group claims. Two ids and not
    one shared id, because the two assertions measure two different parsers
    over two different files (instincts.md and templates/
    STARTER_INSTINCTS.md); a shared id would let one file's regression be
    read as the other's."""

    def test_mention_only_ids_are_not_parsed_as_index_entries(self):
        leaked = sorted(EXCLUDED_MENTION_ONLY_IDS & set(read_index_entries()))
        self.assertEqual(  # pin: set mention-only-ids-index
            [],
            leaked,
            "instincts.md's parser picked up a bold-prose-only mention as "
            "a structural bullet entry: " + ", ".join(leaked),
        )

    def test_mention_only_ids_are_not_parsed_as_sampler_entries(self):
        leaked = sorted(EXCLUDED_MENTION_ONLY_IDS & set(read_sampler_entries()))
        self.assertEqual(  # pin: set mention-only-ids-sampler
            [],
            leaked,
            "templates/STARTER_INSTINCTS.md's parser picked up a "
            "bold-prose-only mention as a structural heading entry: "
            + ", ".join(leaked),
        )


class ParserDiscriminatesEntriesFromMentionsTest(unittest.TestCase):
    """Permanent, committed version of red-proof mutation (c): synthetic
    text containing one real structural entry plus a bold-prose mention of
    a DIFFERENT id, asserting the parser returns only the entry. A parser
    downgraded to a bare `G-\\d{3}` mentions-grep would return both IDs
    here and fail these two tests directly, independent of the real repo
    files' current content."""

    def test_index_parser_ignores_bold_prose_mentions(self):
        text = (
            "- G-001 [0.5] a real bullet entry\n\n"
            "Some prose mentions **G-002** in passing, but it is not a "
            "bullet entry.\n"
        )
        self.assertEqual(["G-001"], parse_index_entries(text))

    def test_sampler_parser_ignores_bold_prose_mentions(self):
        text = (
            "### G-001: a real heading entry\n\n"
            "Some prose mentions **G-002** in passing, but it is not a "
            "heading entry.\n"
        )
        self.assertEqual(["G-001"], parse_sampler_entries(text))


class ClassificationCountsTest(unittest.TestCase):
    def test_classification_counts(self):
        """Regression pin on the measured baseline. `instincts.md` carries
        46 structural index bullet entries; `templates/STARTER_INSTINCTS.md`
        carries 13 structural sampler heading entries. A change in either
        number means an instinct was added/removed/renamed in that file, or
        this scanner's own parsing logic changed -- a deliberate look
        either way, never a silent drift.

        Trajectory, so the history is one line per event rather than a
        growing paragraph:

          index / sampler   when
          45 / 13           WI-0129 finding F14 baseline (29.08.2026):
                             first structural measurement of both files;
                             no prior pin existed to move.
          46 / 13           CCP-1152 (05.09.2026): `instincts.md` gained
                             the `- G-056 [...]` bullet `instincts/
                             workflow.md` had carried without one since
                             before the F14 baseline -- a real instinct
                             becoming index-visible, not a new one minted.
        """
        index_ids = read_index_entries()
        sampler_ids = read_sampler_entries()
        self.assertEqual(
            46,
            len(index_ids),
            "instincts.md's structural bullet-entry count moved off the "
            "pinned baseline -- update the pin deliberately if an "
            "instinct was added, removed, or renamed",
        )
        self.assertEqual(
            13,
            len(sampler_ids),
            "templates/STARTER_INSTINCTS.md's structural heading-entry "
            "count moved off the pinned baseline -- update the pin "
            "deliberately if an instinct was added, removed, or renamed",
        )


class TopicFileClassificationCountTest(unittest.TestCase):
    def test_topic_block_total_equals_the_index_pin(self):
        """A second, independent measurement of the same fact
        `ClassificationCountsTest` pins for the index -- derived from the
        topic files instead of retyped, so the two can drift apart and be
        caught (this is exactly the drift CCP-1152 found: 45 index bullets
        against 46 topic blocks, before the missing G-056 bullet was
        added)."""
        by_file = read_topic_entries()
        total = sum(len(ids) for ids in by_file.values())
        self.assertEqual(
            46,
            total,
            "instincts/*.md topic files' total `### G-NNN: ...` block "
            "count moved off the pinned baseline: " + repr(by_file),
        )


class TitleExtractionTest(unittest.TestCase):
    """Cycle 1: the three registers each carry a TITLE next to the id, and
    nothing extracted it before CCP-1160. The parsers below are the seam the
    title comparison stands on, so they are tested on synthetic text first
    (the same seam `ParserDiscriminatesEntriesFromMentionsTest` uses)."""

    def test_index_title_is_the_text_after_the_confidence_bracket(self):
        text = "- G-008 [0.9] Wingman required after parallel agents\n"
        self.assertEqual(
            {"G-008": "Wingman required after parallel agents"},
            parse_index_titles(text),
        )

    def test_index_title_parser_ignores_bold_prose_mentions(self):
        text = (
            "- G-001 [0.5] a real bullet entry\n\n"
            "Prose mentions **G-002** in passing, but it is not a bullet.\n"
        )
        self.assertEqual({"G-001": "a real bullet entry"}, parse_index_titles(text))

    def test_sampler_title_is_the_text_after_the_colon(self):
        text = "### G-007: Max 3 parallel agents\n"
        self.assertEqual({"G-007": "Max 3 parallel agents"}, parse_sampler_titles(text))

    def test_topic_title_is_the_text_after_the_colon(self):
        text = "### G-051: Out-of-scope files — grep only, no Read\n"
        self.assertEqual(
            {"G-051": "Out-of-scope files — grep only, no Read"},
            parse_topic_titles(text),
        )

    def test_titles_are_captured_raw_so_normalisation_has_one_home(self):
        """The parser must NOT trim: `normalise_title` is the single place
        where the comparison's whitespace rule lives, and a parser that
        silently trimmed would make that rule untestable."""
        self.assertEqual(
            {"G-001": "a title  with  runs   "},
            parse_index_titles("- G-001 [0.5] a title  with  runs   \n"),
        )


class EveryEntryCarriesATitleTest(unittest.TestCase):
    """The scope guard: a title parser that goes blind on one register would
    make the comparison below quietly narrower instead of failing. Each
    register's title population must cover its own entry population exactly
    -- measured against the tracked files, never a fixture."""

    def test_every_index_entry_has_a_title(self):
        missing = sorted(set(read_index_entries()) - set(read_index_titles()))
        self.assertEqual(
            [], missing,
            "instincts.md bullet(s) whose id parses but whose title does "
            "not -- the title regex and the entry regex disagree: "
            + ", ".join(missing),
        )

    def test_every_sampler_entry_has_a_title(self):
        missing = sorted(set(read_sampler_entries()) - set(read_sampler_titles()))
        self.assertEqual(
            [], missing,
            "templates/STARTER_INSTINCTS.md heading(s) whose id parses but "
            "whose title does not: " + ", ".join(missing),
        )

    def test_no_register_carries_an_empty_title(self):
        """A heading or bullet whose title is empty parses fine and is a
        defect in its own right -- and it is also the input that makes the
        annotation rule degenerate (see
        `test_an_empty_title_never_agrees_with_an_annotated_one`). Guarded
        at the source so the degenerate case stays unreachable in the
        tracked files rather than merely handled."""
        empty = sorted(
            (register, gid)
            for register, titles in (("index", read_index_titles()),
                                     ("sampler", read_sampler_titles()),
                                     ("topic", read_topic_titles()))
            for gid, title in titles.items()
            if not normalise_title(title)
        )
        self.assertEqual(
            [], empty,
            "a register entry carries an empty title: " + repr(empty),
        )

    def test_every_topic_entry_has_a_title(self):
        entry_ids = {gid for ids in read_topic_entries().values() for gid in ids}
        missing = sorted(entry_ids - set(read_topic_titles()))
        self.assertEqual(
            [], missing,
            "instincts/*.md heading(s) whose id parses but whose title does "
            "not: " + ", ".join(missing),
        )


class RegisterRelationTest(unittest.TestCase):
    """CCP-1160, second cut (PO decision 06.09.2026): the three registers do
    not stand in ONE relation, and comparing them as if they did books design
    as debt.

    `templates/STARTER_INSTINCTS.md` and `instincts/*.md` are the SAME kind of
    artifact -- both are `### G-NNN: Title` headings -- and they disagree 4
    times out of 13. `instincts.md` is a different artifact: a one-liner
    carrying a confidence score, which calls itself a slim entry point. So the
    sampler/topic pair is compared STRICTLY, and the two index pairs are
    compared with the annotation rule this class fixes in tests.

    MEASURED, not assumed. Of the 46 ids present in both index and topic, 34
    titles are identical and 12 differ; of those 12, six involve a trailing parenthetical and six are pure wording
    differences with no parenthetical at all. Of those six, FOUR are absorbed
    (exactly one side annotated) and TWO -- G-016 and G-019 -- carry a
    DIFFERENT parenthetical on each side and stay divergent. So the
    index/topic pair contributes 4 absorptions and 8 divergences.
    The shape is ANNOTATION, not compression -- the index appends
    `(incl. ... sub-rules)` to the rule the heading states bare."""

    def test_sampler_and_topic_are_compared_strictly(self):
        """The two same-kind registers get no tolerance at all: a trailing
        parenthetical on one side is a divergence between them."""
        found = title_divergences(collect_titles_by_id(
            {}, {"G-001": "A rule (incl. a sub-rule)"}, {"G-001": "A rule"}))
        self.assertEqual(
            {("G-001", "sampler", "topic",
              "A rule (incl. a sub-rule)", "A rule")},
            found,
        )

    def test_the_index_may_annotate_a_heading_with_a_trailing_parenthetical(self):
        """The rule itself: exactly one side carries a trailing
        parenthetical, the stems are identical -> annotation, not
        divergence."""
        self.assertEqual(set(), title_divergences(collect_titles_by_id(
            {"G-001": "A rule (incl. a sub-rule)"}, {}, {"G-001": "A rule"})))

    def test_two_DIFFERENT_parentheticals_on_one_stem_stay_a_divergence(self):
        """The trap in the rule, and the reason it is stated as "exactly one
        side is annotated" rather than "strip the parenthetical from both".

        Stripping both sides would make the comparison blind to G-016 and
        G-019 -- two of the FOUR divergences CCP-1159 was originally opened
        for. Two different annotations on one stem are two statements, not
        one statement annotated."""
        found = title_divergences(collect_titles_by_id(
            {"G-001": "A rule (incl. sub-rules)"}, {},
            {"G-001": "A rule (something else entirely)"}))
        self.assertEqual(
            {("G-001", "index", "topic",
              "A rule (incl. sub-rules)", "A rule (something else entirely)")},
            found,
        )

    def test_the_stem_is_still_compared_strictly_under_the_annotation_rule(self):
        """The rule tolerates the annotation, never the rule text. A sweep
        that rewrites a word in the STEM fails whether or not either side
        carries a parenthetical."""
        found = title_divergences(collect_titles_by_id(
            {"G-001": "Read the handbook (incl. a sub-rule)"}, {},
            {"G-001": "Read the manual"}))
        self.assertEqual({"G-001"}, {rec[0] for rec in found})

    def test_an_internal_parenthetical_is_not_stripped(self):
        """Only a TRAILING parenthetical is annotation. G-026's topic title
        carries `(and other SKILL system filenames)` in the middle of the
        rule, where it is part of the statement -- stripping that would
        dissolve a real divergence CCP-1159 has to decide."""
        found = title_divergences(collect_titles_by_id(
            {"G-001": "Avoid x on macOS"}, {},
            {"G-001": "Avoid x (and other things) on macOS"}))
        self.assertEqual({"G-001"}, {rec[0] for rec in found})

    def test_an_empty_title_never_agrees_with_an_annotated_one(self):
        """The degenerate case in the XOR, found by measuring it rather
        than by reading it: with `title_a = ""` and `title_b = "(x)"` both
        STEMS are empty, exactly one side is annotated, and the rule would
        otherwise report agreement. An empty title agrees with nothing --
        it is a malformed entry, not an un-annotated one.

        Guarded in two places on purpose. Here, so the rule itself cannot
        return a nonsense answer; and at the source, so a register that
        grows an empty title fails loudly instead of being quietly
        tolerated (`test_no_register_carries_an_empty_title`)."""
        self.assertFalse(titles_agree(ANNOTATION_TOLERANT, "", "(x)"))
        self.assertFalse(titles_agree(ANNOTATION_TOLERANT, "(x)", ""))
        self.assertFalse(titles_agree(STRICT, "", "(x)"))

    def test_a_new_annotation_is_caught_by_the_absorbed_pin_alone(self):
        """Why `ANNOTATION_ABSORBED` is a guard and not only an audit list.

        If an index title GAINS a trailing parenthetical whose heading
        counterpart is bare, the pair becomes absorbed: the divergence set
        does not move at all, so its pin stays GREEN. Only the absorbed pin
        sees it. This is the case that makes the second register carry
        detection of its own rather than merely documenting the first."""
        by_id = collect_titles_by_id(
            {"G-001": "A rule (incl. a sub-rule)"}, {}, {"G-001": "A rule"})
        self.assertEqual(set(), title_divergences(by_id))
        self.assertEqual(
            {("G-001", "index", "topic",
              "A rule (incl. a sub-rule)", "A rule")},
            annotation_absorbed(by_id),
        )

    def test_every_register_pair_has_a_declared_relation(self):
        """A pair with no declared relation would be silently uncompared --
        the same vacuum this whole module exists to remove. All three
        unordered pairs of the three registers must be named."""
        expected = {("index", "sampler"), ("index", "topic"),
                    ("sampler", "topic")}
        self.assertEqual(expected, set(REGISTER_RELATIONS))
        self.assertEqual(
            {STRICT, ANNOTATION_TOLERANT}, set(REGISTER_RELATIONS.values()),
            "both relations must actually be in use -- a vocabulary with an "
            "unused member is a rule nobody applies",
        )


class TitleComparisonSemanticsTest(unittest.TestCase):
    """The comparison is WHITESPACE-NORMALISED AND OTHERWISE EXACT, and this
    class is where that choice is a test rather than a sentence in the
    docstring. Both halves are load-bearing:

      * the accepting half -- a trailing space or a doubled internal space
        is not a divergence. Neither is visible in rendered Markdown, and a
        failure message naming two titles that look identical is a failure
        nobody can act on;
      * the rejecting half -- case, punctuation, backticks and words are
        all significant. This is the half the guard exists for: a
        terminology sweep changes WORDS, so a one-sided sweep of these
        registers lands on the failing side by construction.

    Anything more aggressive (case-folding, stripping punctuation or
    backticks) would silently accept exactly the drift this module was
    built to catch. Case-folding in particular was PROPOSED and REJECTED on
    measurement: it changes nothing in any of the three register pairs
    today (12/7/4 divergences either way), so it would buy no agreement and
    cost the ability to see a capitalisation sweep.

    The pair used below is index/topic, i.e. the annotation-tolerant
    relation -- deliberately the WEAKER of the two, so each case here is
    also a statement that the tolerance does not swallow it."""

    def test_a_trailing_space_is_not_a_divergence(self):
        self.assertEqual(set(), title_divergences(collect_titles_by_id(
            {"G-001": "Same title   "}, {}, {"G-001": "Same title"})))

    def test_an_internal_double_space_is_not_a_divergence(self):
        self.assertEqual(set(), title_divergences(collect_titles_by_id(
            {"G-001": "Same  title"}, {}, {"G-001": "Same title"})))

    def test_a_non_breaking_space_is_not_a_divergence(self):
        """The consequence `normalise_title` names in prose, as a test.
        `str.split()` honours Unicode's `White_Space` property, so U+00A0
        collapses like any other run -- the same class as a doubled space,
        invisible where the title is read, and accepted on the same
        grounds. Written as an ESCAPE rather than a literal character so
        that an editor or a copy/paste cannot silently turn it into a plain
        space and leave this test comparing a string with itself; the
        assertNotEqual below is what makes that failure loud instead of
        vacuous."""
        nbsp_title = "Same\u00a0title"
        self.assertNotEqual(
            nbsp_title, "Same title",
            "the fixture lost its non-breaking space, so this test would "
            "be comparing a string with itself",
        )
        self.assertEqual(set(), title_divergences(collect_titles_by_id(
            {"G-001": nbsp_title}, {}, {"G-001": "Same title"})))

    def test_a_case_difference_is_a_divergence(self):
        found = title_divergences(collect_titles_by_id(
            {"G-001": "Same title"}, {}, {"G-001": "Same Title"}))
        self.assertEqual(
            {("G-001", "index", "topic", "Same title", "Same Title")}, found)

    def test_a_backtick_difference_is_a_divergence(self):
        found = title_divergences(collect_titles_by_id(
            {"G-001": "Avoid `skill.md` on macOS"}, {},
            {"G-001": "Avoid skill.md on macOS"}))
        self.assertEqual(
            {("G-001", "index", "topic",
              "Avoid `skill.md` on macOS", "Avoid skill.md on macOS")},
            found,
        )

    def test_a_one_word_difference_is_a_divergence(self):
        """The terminology-sweep shape, and the whole reason this module
        grew a title comparison: a sweep moves no id, so an id-only guard
        stays green through it."""
        found = title_divergences(collect_titles_by_id(
            {"G-001": "Read the handbook first"}, {},
            {"G-001": "Read the manual first"}))
        self.assertEqual(
            {("G-001", "index", "topic",
              "Read the handbook first", "Read the manual first")},
            found,
        )


class SamplerReducedSetBoundaryTest(unittest.TestCase):
    """`templates/STARTER_INSTINCTS.md` is DELIBERATELY a reduced set -- it
    says so in its own header, and `SubsetAgreementTest` above already
    encodes the asymmetry (every sampler id must be in the index, never the
    reverse). "In the index, absent from the sampler" is therefore the
    sampler's DESIGN, not a divergence, and reporting it would make this
    guard cry wolf over 33 of the index's 46 entries -- the fastest possible
    route to having it switched off.

    A pair is compared only where BOTH its registers carry the id. The
    failure mode this class rules out is a comparator that reaches a missing
    register through a `""` default: that version reports every
    sampler-absent id as "index says X, sampler says nothing" and looks,
    from the outside, exactly like a working guard."""

    def test_an_id_in_a_single_register_is_never_compared(self):
        self.assertEqual(set(), title_divergences(collect_titles_by_id(
            {"G-001": "only the index carries this"}, {}, {})))

    def test_a_register_that_lacks_the_id_is_not_filled_with_an_empty_title(self):
        """The discriminating synthetic case: one id in all three registers
        with one differing title, one id the sampler does not carry at all.
        The second must be compared on its index/topic pair ONLY -- and
        produce nothing at all when those two agree."""
        found = title_divergences(collect_titles_by_id(
            {"G-001": "a", "G-002": "b", "G-003": "c"},
            {"G-001": "a-different"},
            {"G-001": "a", "G-002": "b-different", "G-003": "c"},
        ))
        self.assertEqual(
            {
                ("G-001", "index", "sampler", "a", "a-different"),
                ("G-001", "sampler", "topic", "a-different", "a"),
                ("G-002", "index", "topic", "b", "b-different"),
            },
            found,
        )

    def test_no_reported_record_names_a_register_that_lacks_the_id(self):
        """The live half, over the tracked files: both registers named in
        every reported record must actually carry that id."""
        carriers = {
            "index": set(read_index_titles()),
            "sampler": set(read_sampler_titles()),
            "topic": set(read_topic_titles()),
        }
        fabricated = sorted(
            (gid, register)
            for gid, reg_a, reg_b, _ta, _tb in measured_title_divergences()
            for register in (reg_a, reg_b)
            if gid not in carriers[register]
        )
        self.assertEqual(
            [], fabricated,
            "the comparison reported a register/id pair the register does "
            "not carry -- the missing-key-default defect this class exists "
            "for: " + repr(fabricated),
        )

    def test_the_sampler_absent_ids_are_never_charged_against_the_sampler(self):
        """The same rule stated where it actually bites, and not vacuously:
        33 of the index's 46 ids are absent from the sampler by design. No
        record may name `sampler` for any of them."""
        absent = set(read_index_titles()) - set(read_sampler_titles())
        self.assertNotEqual(
            set(), absent,
            "this check is only meaningful while the sampler is a REDUCED "
            "set; it carries every index id today, so the rule below "
            "measures nothing",
        )
        charged = sorted(
            gid for gid, reg_a, reg_b, _ta, _tb in measured_title_divergences()
            if gid in absent and "sampler" in (reg_a, reg_b)
        )
        self.assertEqual(
            [], charged,
            "an id the sampler deliberately omits was reported as a "
            "sampler title divergence: " + ", ".join(charged),
        )


class TitleAgreementTest(unittest.TestCase):
    """CCP-1160: the registers agree on WHICH instincts exist (every test
    above) and, from here, are also measured on WHAT THEY SAY.

    The 18 records in `KNOWN_TITLE_DIVERGENCES` are DECLARED, not repaired:
    reconciling them is editorial work with a per-title decision behind it
    and is filed separately (CCP-1159, extended by PO decision to all of
    them). The declared-known-findings shape is
    `test_bsd_gnu_portability.py`'s `KnownFindingsMatchTheCurrentScanTest`,
    including its set equality: a NEW divergence fails, and so does a STALE
    entry left behind after a reconciliation. A tolerated finding that
    nobody can see is how the next one hides."""

    def test_the_measured_divergences_are_the_declared_set(self):
        current = measured_title_divergences()
        self.assertEqual(  # pin: set instinct-title-divergences
            KNOWN_TITLE_DIVERGENCES, current,
            "the instinct-register title comparison drifted from its "
            "recorded baseline.\n  new:  {}\n  gone: {}".format(
                sorted(current - KNOWN_TITLE_DIVERGENCES),
                sorted(KNOWN_TITLE_DIVERGENCES - current),
            ),
        )

    def test_what_the_annotation_rule_absorbs_is_pinned_too(self):
        """The rule's own effect is measured, not trusted.

        A tolerance rule silently REMOVES findings, so pinning only what
        survives it would leave the rule itself unguarded: widen it by
        accident and the divergence set merely shrinks, which reads like
        progress. This set is what the annotation rule accepts that a strict
        comparison would report -- it may not grow without someone saying
        so."""
        self.assertEqual(  # pin: set instinct-title-annotation-absorbed
            ANNOTATION_ABSORBED, measured_annotation_absorbed(),
            "the set of title pairs accepted by the annotation rule moved. "
            "If it GREW, the rule is now tolerating something it did not "
            "before -- check that it is still 'exactly one side carries a "
            "trailing parenthetical' and not 'strip the parenthetical from "
            "both'.",
        )

    def test_the_two_registers_partition_the_strict_population(self):
        """The accounting that ties the two pins together: under a strict
        comparison of every pair, the population is exactly the declared
        divergences PLUS the declared absorptions, with no overlap. Neither
        register can drift without the other one noticing, and no finding
        can fall between them."""
        strict = measured_strict_divergences()
        self.assertEqual(
            set(), KNOWN_TITLE_DIVERGENCES & ANNOTATION_ABSORBED,
            "a pair cannot be both a declared divergence and absorbed",
        )
        self.assertEqual(
            KNOWN_TITLE_DIVERGENCES | ANNOTATION_ABSORBED, strict,
            "the two declared registers do not add up to the strict "
            "comparison population -- a finding is unaccounted for",
        )

    def test_every_declared_record_names_two_distinct_registers(self):
        """Well-formedness of both registers. A record naming one register
        twice would be a divergence with nothing to diverge from --
        unreachable by the comparison, and so a permanently stale entry."""
        malformed = sorted(
            rec for rec in KNOWN_TITLE_DIVERGENCES | ANNOTATION_ABSORBED
            if rec[1] == rec[2] or (rec[1], rec[2]) not in REGISTER_RELATIONS)
        self.assertEqual([], malformed, repr(malformed))

    def test_every_declared_record_carries_two_distinct_titles(self):
        """The other half: a record whose two titles agree is not a finding
        either, and would likewise never be reported."""
        malformed = sorted(
            rec for rec in KNOWN_TITLE_DIVERGENCES | ANNOTATION_ABSORBED
            if rec[3] == rec[4])
        self.assertEqual([], malformed, repr(malformed))


if __name__ == "__main__":
    unittest.main()
