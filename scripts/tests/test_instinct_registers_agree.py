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

## The boundary this test does NOT cover

This module closes the DRIFT class of defect: an instinct ID that stops
existing in one file while the other still names it, or an entry count
that moves without anyone noticing. It does NOT close the DESCRIPTION
class: the actual defect that prompted this work item was not an ID going
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


if __name__ == "__main__":
    unittest.main()
