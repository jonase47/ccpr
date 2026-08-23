#!/usr/bin/env python3
"""generate_commonmark_corpus.py — WI-0005: builds commonmark_corpus.json.

Manual, documented handgrip — NOT run automatically by the test suite (the
test module deliberately does not import `commonmark` at all, see its own
docstring). Re-run this generator only when:

  * the corpus below gains/loses an entry, or
  * `scripts/memory-lint.sh` check (n)'s extraction logic changes shape, or
  * the installed `commonmark` package version changes (`commonmark_version`
    in the output is the provenance field that would go stale otherwise).

    python3 scripts/tests/fixtures/generate_commonmark_corpus.py

Two independent oracles are queried per entry, per the project's own rule
("Konformitaet wird durch Ausfuehren entschieden, nie durch Argumentieren",
docs/memory/reference_commonmark-conformance.md):

  1. The reference parser (`commonmark` 0.9.2, a probe dependency — not a
     runtime dependency of `scripts/`, see the reference-conformance doc's
     "Why this file exists" section) renders each entry's Markdown and the
     `<a href="...">` targets it produces are the ground truth for "is this
     a link, and to what". Filtered through the SAME exclusions check (n)
     documents (images already excluded structurally — CommonMark never
     renders `<img>` as `<a>` — plus external schemes, mailto, in-page
     anchors) this becomes `reference_checkable_targets`: the file-existence
     questions a fully spec-conformant extractor would ask.
  2. The real `scripts/memory-lint.sh`, invoked exactly as the differential
     test invokes it (isolated scratch project, one entry per file), is the
     second oracle: `expected_check_n_findings` is what it ACTUALLY reports
     today, measured, not derived from reading the awk source.

Where the two oracles disagree, the entry must carry EXACTLY ONE of two
explanation blocks in the CORPUS list below — the generator refuses to write
a fixture where they disagree silently, refuses to write either block when
the measurement does not actually confirm a disagreement (a claimed
divergence/intent must be an observed one), and refuses an entry that
carries both:

  * `known_divergence` (direction, reason, work_item) — an OPEN gap in
    check (n), tracked for a future fix.
  * `documented_intent` (reason, po_decision, work_item) — WI-0085: a
    disagreement the PO explicitly decided is deliberate, not a bug. check
    (n)'s own contract is narrower than CommonMark conformance ("does the
    index still point at existing files?"), and this is the field for a
    case where that narrower contract is the intended behaviour on purpose.

This is the "gezaehlt und benannt" contract WI-0005 asks for: the promotion
criterion ("a round producing no new items") becomes measurable only if
every divergence recorded here was actually seen to diverge.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import commonmark

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "memory-lint.sh"
FIXTURE_PATH = Path(__file__).resolve().parent / "commonmark_corpus.json"

FINDING_RE = re.compile(r"link target '([^']*)' does not exist")

# ---------------------------------------------------------------------------
# The corpus. Each entry is one Markdown fragment, dropped into the body of
# an otherwise-plain Tier-1 index file (`# Memory Index\n\n<markdown>`), the
# same shape CLEAN_INDEX uses in test_memory_lint.py. Every genuine link
# target below is spelled so it does not exist ("dead-*"/"nonexistent")
# regardless of which oracle is asked — the point of each entry is only
# whether a finding is reported at all / under which literal string, never
# whether the target happens to resolve.
#
# `known_divergence`, when present, is AUTHORED here as a claim; the
# generator verifies the claim against both oracles before writing it to the
# fixture (see main() below) — it does not take the claim on faith.
# ---------------------------------------------------------------------------
CORPUS = [
    # --- nested brackets in link text ---------------------------------------
    {
        "name": "nested_brackets_in_link_text_simple",
        "category": "nested-brackets-in-link-text",
        "markdown": "- [a [b] c](dead-nb1.md) — nested brackets in link text\n",
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "check (n)'s label regex is `\\[[^][]*\\]` — ANY literal `]` "
                "or `[` inside the link text breaks the match, nested or not. "
                "The reference renders this as one ordinary link "
                "(`<a href=\"dead-nb1.md\">a [b] c</a>`); check (n) never "
                "matches it at all and stays silent."
            ),
            "work_item": "WI-0005",
        },
    },
    {
        "name": "nested_brackets_in_link_text_mid_sentence",
        "category": "nested-brackets-in-link-text",
        "markdown": "before [a [b] c](dead-esc2.md) after\n",
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "Same defect as nested_brackets_in_link_text_simple, wired as "
                "a second, structurally different fixture (mid-paragraph "
                "prose instead of a list item) so the finding is not "
                "specific to bullet-list context."
            ),
            "work_item": "WI-0005",
        },
    },
    {
        "name": "nested_brackets_outer_literal_inner_real_link",
        "category": "nested-brackets-in-link-text",
        "markdown": "[a [b](dead-nb2-inner.md) c](dead-nb2-outer.md)\n",
        "known_divergence": None,
    },
    # --- autolinks — structurally out of check (n)'s syntax family ---------
    {
        "name": "autolink_http_scheme",
        "category": "autolinks",
        "markdown": "See <https://example.invalid/dead-al1.md> for more.\n",
        "known_divergence": None,
    },
    {
        "name": "autolink_bare_relative_path",
        "category": "autolinks",
        "markdown": "See <dead-al2.md> for more.\n",
        "known_divergence": None,
    },
    {
        "name": "autolink_email",
        "category": "autolinks",
        "markdown": "Contact <dead-al3@example.invalid>.\n",
        "known_divergence": None,
    },
    # --- entity references --------------------------------------------------
    {
        "name": "entity_reference_in_link_text",
        "category": "entity-references",
        "markdown": "[a &amp; b](dead-ent1.md)\n",
        "known_divergence": None,
    },
    {
        "name": "entity_reference_named_in_destination",
        "category": "entity-references",
        "markdown": "[x](dead&num;3-ent2.md) — named entity in destination\n",
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "WI-0081 (remainder), fixed 23.08.2026: check (n) used to "
                "resolve the raw, undecoded destination text and report it "
                "as dead -- for a decoded target that happens to exist on "
                "disk, that is a LIVE link reported as dead, the wrong "
                "direction ADR-0001's severity promotion actually cares "
                "about. check (n) does not build the ~2000-entry CommonMark "
                "named-entity table (see the numeric-entity rows above for "
                "the bounded set it DOES decode), so it cannot tell a dead "
                "named-entity destination apart from a live one -- \"cannot "
                "resolve\" is not license to claim either verdict. The "
                "destination is now filed as an Info finding naming the raw "
                "target instead, and is silent in Errors/Warnings, which is "
                "why the two oracles read as disagreeing here (reference: a "
                "real link to `dead#3-ent2.md`; check (n): nothing in the "
                "errors/warnings section this differential test reads). "
                "Same accepted-exception shape as the empty-destination "
                "rows below (WI-0060/WI-0061) -- silence for a construct "
                "this tool cannot resolve is the deliberate design, not a "
                "conformance gap left open."
            ),
            "work_item": "WI-0081",
        },
    },
    {
        "name": "entity_reference_decimal_in_destination",
        "category": "entity-references",
        "markdown": "[x](dead&#35;3-ent3.md) — decimal entity in destination\n",
        "known_divergence": None,
    },
    {
        "name": "entity_reference_hex_in_destination",
        "category": "entity-references",
        "markdown": "[x](dead&#x23;3-ent4.md) — hex entity in destination\n",
        "known_divergence": None,
    },
    # --- backslash escapes ---------------------------------------------------
    {
        "name": "backslash_escaped_link_is_not_a_link",
        "category": "backslash-escapes",
        "markdown": "before \\[not a link\\](dead-esc1.md) after\n",
        "known_divergence": None,
    },
    {
        "name": "backslash_escaped_bracket_pair_not_a_link_alongside_a_real_link",
        "category": "backslash-escapes",
        "markdown": (
            "\\[escaped pair\\](dead-esc6.md) and "
            "[a real link](dead-esc7.md)\n"
        ),
        "known_divergence": None,
    },
    {
        "name": "backslash_escaped_bracket_in_link_text",
        "category": "backslash-escapes",
        "markdown": "[a\\]b](dead-esc5.md)\n",
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "The reference decodes the escape and renders one ordinary "
                "link (text `a]b`, href `dead-esc5.md`). check (n)'s label "
                "regex `[^][]*` disallows a literal `]` regardless of a "
                "preceding backslash, so it never matches this span at all "
                "— the same root cause as the nested-brackets false "
                "negatives above, triggered via escaping instead of "
                "nesting."
            ),
            "work_item": "WI-0005",
        },
    },
    {
        "name": "backslash_escaped_paren_in_destination",
        "category": "backslash-escapes",
        "markdown": "[x](dead-esc4\\).md)\n",
        "known_divergence": None,
    },
    {
        "name": "backslash_escaped_paren_in_destination_beside_a_plain_one",
        "category": "backslash-escapes",
        "markdown": (
            "[first](dead-esc8\\).md) and [second](dead-esc9.md)\n"
        ),
        "known_divergence": None,
    },
    # --- multiline reference-style definitions ------------------------------
    {
        "name": "multiline_reference_definition_target_on_next_line",
        "category": "multiline-reference-definitions",
        "markdown": (
            "[ref1]:\n"
            "dead-refdef1.md\n"
            "\n"
            "[link with multiline refdef][ref1]\n"
        ),
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "CommonMark allows a reference definition's destination to "
                "sit on the line after `[label]:` (reference href: "
                "`dead-refdef1.md`, one real link). check (n)'s "
                "`reference_definition_tail()` is invoked with an EMPTY "
                "`raw_rest` when the destination is not on the same "
                "physical line, so it returns 0 (not a valid reference "
                "definition) and the line is dropped entirely; the bare "
                "target line that follows and the `[text][ref1]` usage "
                "line are both plain prose to check (n) (neither matches "
                "its `](...)` inline-link pattern), so the link is "
                "invisible end to end. Isolated from the broader (and "
                "unrelated-to-this-item) fact that check (n) never resolves "
                "shortcut/full reference-link USAGES at all — see the "
                "single-line control below, which the definition-line path "
                "DOES catch."
            ),
            "work_item": "WI-0005",
        },
    },
    {
        "name": "singleline_reference_definition_control",
        "category": "multiline-reference-definitions",
        "markdown": (
            "[ref-single]: dead-refdef-single.md\n"
            "\n"
            "[link with single-line refdef][ref-single]\n"
        ),
        "known_divergence": None,
    },
    # --- setext headers -------------------------------------------------------
    {
        "name": "setext_heading_simple",
        "category": "setext-headers",
        "markdown": "[link](dead-setext-d.md)\n===\n",
        "known_divergence": None,
    },
    {
        "name": "setext_heading_swallows_link_via_missing_boundary",
        "category": "setext-headers",
        "markdown": (
            "`code with a [link](dead-setext-e.md) inside\n"
            "===\n"
            "closer` [outer](dead-setext-f.md)\n"
        ),
        "known_divergence": None,
    },
    # --- thematic breaks -------------------------------------------------------
    {
        "name": "thematic_break_simple",
        "category": "thematic-breaks",
        "markdown": "text before\n\n***\n\n[link](dead-tb-c.md)\n",
        "known_divergence": None,
    },
    {
        "name": "thematic_break_swallows_link_via_missing_boundary",
        "category": "thematic-breaks",
        "markdown": (
            "`code with [link](dead-tb-a.md)\n"
            "***\n"
            "closer` [outer](dead-tb-b.md)\n"
        ),
        "known_divergence": None,
    },
    # --- nested lists ------------------------------------------------------
    {
        "name": "nested_list_shallow_indent",
        "category": "nested-lists",
        "markdown": (
            "- Outer item [outer](dead-nl-a.md)\n"
            "  - Inner item [inner](dead-nl-b.md)\n"
            "- Second outer [second](dead-nl-c.md)\n"
        ),
        "known_divergence": None,
    },
    {
        "name": "nested_list_deep_indent_under_ordered_parent",
        "category": "nested-lists",
        "markdown": (
            "1. Outer item [outer](dead-nl-d.md)\n"
            "    - Inner item [inner](dead-nl-e.md)\n"
        ),
        "known_divergence": None,
    },
    # --- lazy continuation ---------------------------------------------------
    {
        "name": "lazy_continuation_in_list_item",
        "category": "lazy-continuation",
        "markdown": (
            "- Item text [first](dead-lazy-a.md)\n"
            "continued text [second](dead-lazy-b.md)\n"
        ),
        "known_divergence": None,
    },
    # --- documented-exceptions control (WI-0005 mutation target) -----------
    # Not one of the ten uncovered constructs itself — a control fixture that
    # ties an already-documented exclusion (external scheme + in-page anchor,
    # both settled in six earlier rounds) INTO this corpus/test module, so the
    # mutation-must-go-red obligation below has an in-corpus fixture to flip.
    # None of the ten new constructs above happen to route through the
    # http/https/mailto/#-anchor shell case block (autolinks never reach it —
    # they never match check (n)'s `](...)` regex at all; see the autolink_*
    # entries), so without this entry the mutation demanded by the work item
    # would have no corpus fixture of its own to discriminate against.
    {
        "name": "external_scheme_and_anchor_stay_excluded_alongside_a_real_dead_link",
        "category": "documented-exceptions-control",
        "markdown": (
            "[Spec](https://example.invalid/dead-ext.md) and "
            "[Top](#dead-anchor) and "
            "[Ghost](dead-control-for-mutation.md)\n"
        ),
        "known_divergence": None,
    },
    # --- tables as a block boundary -----------------------------------------
    {
        "name": "table_like_row_as_block_boundary",
        "category": "tables-as-block-boundary",
        "markdown": "| A | B |\n| --- | --- |\n| [x](dead-tbl-a.md) | y |\n",
        "known_divergence": None,
        "caveat": (
            "The installed reference (`commonmark` 0.9.2) implements only "
            "core CommonMark — no GFM table extension. This entry measures "
            "'does a pipe-delimited row act as an unrecognised block "
            "boundary', not true GFM table-parsing semantics; both oracles "
            "agree it renders as one ordinary paragraph with a live link."
        ),
    },
    # =========================================================================
    # WI-0005, round 2 (22.08.2026-23.08.2026): a second adversarial pass, new
    # construct classes only — the ten covered above (nested brackets,
    # autolinks, entities, escapes, multiline refdefs, setext, thematic
    # breaks, nested lists, lazy continuation, table-as-boundary) and the six
    # earlier rounds' ground (image markers, fence state, HTML comments,
    # comment-vs-code-span precedence, paragraph buffering, three-title-
    # delimiter refdefs) are NOT retested here. Derived from reading check
    # (n)'s own awk block-boundary list, not from a generic construct list:
    # every category below either has NO handling at all in that list
    # (indented code, non-comment HTML blocks), exploits a mechanism the
    # extractor uses for an unrelated reason (the reference-definition-line
    # shortcut, which checks a destination independent of any usage), or
    # targets the boundary REGEX's character class directly (CRLF).
    # --- indented code blocks (4 spaces / one tab) — no handling at all ------
    {
        "name": "indented_code_block_four_spaces",
        "category": "indented-code-blocks",
        "markdown": "before paragraph\n\n    [link](dead-ind1.md)\n\nafter paragraph\n",
        "known_divergence": None,
    },
    {
        "name": "indented_code_block_tab_indent",
        "category": "indented-code-blocks",
        "markdown": "before paragraph\n\n\t[link](dead-ind2.md)\n\nafter paragraph\n",
        "known_divergence": None,
    },
    # --- HTML blocks other than comments — only <!--...--> is handled -------
    {
        "name": "html_block_div_tag",
        "category": "html-blocks-non-comment",
        "markdown": "<div>\n[link](dead-html1.md)\n</div>\n",
        "known_divergence": None,
    },
    {
        "name": "html_block_pre_tag",
        "category": "html-blocks-non-comment",
        "markdown": "<pre>\n[link](dead-html2.md)\n</pre>\n",
        "known_divergence": None,
    },
    {
        "name": "html_block_script_tag",
        "category": "html-blocks-non-comment",
        "markdown": "<script>\nvar x = '[link](dead-html3.md)';\n</script>\n",
        "known_divergence": None,
    },
    # --- reference definitions checked regardless of any usage --------------
    {
        "name": "unused_reference_definition_standalone",
        "category": "unused-reference-definitions",
        "markdown": "[ref9]: dead-unused1.md\n",
        "known_divergence": None,
        "documented_intent": {
            "reason": (
                "PO decision 23.08.2026 (WI-0085): this is INTENDED, not a "
                "bug, despite CommonMark rendering no <a href> for an "
                "unused reference definition. check (n)'s own contract is "
                "narrower than conformance -- does the index still point "
                "at existing files? -- and a reference definition "
                "addressing a deleted file is a dead POINTER regardless of "
                "whether anything currently uses it. It renders as nothing, "
                "so no reader notices it on a normal read; that "
                "invisibility is exactly the failure mode this check "
                "exists to catch. Kept as a corpus entry (not deleted) so "
                "this decision is not silently forgotten on a future "
                "adversarial round -- see "
                "reference_commonmark-conformance.md for the fuller "
                "rationale."
            ),
            "po_decision": "23.08.2026",
            "work_item": "WI-0085",
        },
    },
    {
        "name": "unused_reference_definition_after_prose",
        "category": "unused-reference-definitions",
        "markdown": "Some prose here.\n\n[ref9]: dead-unused2.md\n",
        "known_divergence": None,
        "documented_intent": {
            "reason": (
                "Same PO decision as unused_reference_definition_standalone "
                "(WI-0085, 23.08.2026), wired as a second fixture with an "
                "ordinary paragraph ahead of the definition so the intent "
                "is not read as specific to a definition being the "
                "document's only line."
            ),
            "po_decision": "23.08.2026",
            "work_item": "WI-0085",
        },
    },
    # --- CRLF line endings — the blank-line boundary regex is \n-only -------
    {
        "name": "crlf_blank_line_swallows_link_via_missing_boundary",
        "category": "crlf-line-endings",
        "markdown": (
            "`stray one [a](dead-crlf-c.md)\r\n"
            "\r\n"
            "`stray two [b](dead-crlf-d.md)\r\n"
        ),
        "known_divergence": None,
    },
    {
        "name": "crlf_two_paragraphs_no_confounding_span_control",
        "category": "crlf-line-endings",
        "markdown": (
            "para one [a](dead-crlf-a.md)\r\n"
            "\r\n"
            "para two [b](dead-crlf-b.md)\r\n"
        ),
        "known_divergence": None,
    },
    # --- container vs. boundary — the two shapes that decide whether a -----
    # --- boundary branch may be gated on pbuf_para, added after a review ---
    # --- caught the first gate in the wrong place (WI-0086/WI-0082) --------
    {
        "name": "setext_underline_inside_block_quote_after_paragraph",
        "category": "container-vs-boundary",
        "markdown": (
            "foo\n"
            "> `q [a](dead-bqmid-a.md)\n"
            "===\n"
            "closer` [b](dead-bqmid-b.md)\n"
        ),
        "known_divergence": None,
        "caveat": (
            "A block quote may INTERRUPT an open paragraph, so the container "
            "guard on the setext branch cannot key off what OPENED the "
            "paragraph buffer. It did, briefly, and reported the "
            "code-span-buried first link — a false positive on a shape that "
            "was correct before the setext boundary existed. The reference "
            "keeps the underline inside the quote "
            "(`<code>q [a](…) === closer</code>`), so only the trailing link "
            "is a link."
        ),
    },
    {
        "name": "thematic_break_ends_list_item_ungated",
        "category": "container-vs-boundary",
        "markdown": (
            "- `item [a](dead-tbli-a.md)\n"
            "---\n"
            "closer` [b](dead-tbli-b.md)\n"
        ),
        "known_divergence": None,
        "caveat": (
            "The counterpart of the entry above, and the reason the "
            "thematic-break branch must NOT carry the same pbuf_para gate as "
            "the setext branch: unlike a `=`-run, a `---` line is not lazy "
            "continuation inside a list item. The reference renders "
            "`<ul><li>…</li></ul>`, `<hr />` and a separate paragraph, so the "
            "item's stray backtick never reaches the closing one and BOTH "
            "links are real. Gating the branch would pair them and hide the "
            "first — a false negative."
        ),
    },
    # --- reference-link usage forms — agree, but only via the definition- --
    # --- line shortcut documented above, not by resolving the USAGE --------
    {
        "name": "shortcut_reference_link",
        "category": "reference-link-usage-forms",
        "markdown": "[ref5]: dead-short1.md\n\n[ref5]\n",
        "known_divergence": None,
    },
    {
        "name": "collapsed_reference_link",
        "category": "reference-link-usage-forms",
        "markdown": "[ref6]: dead-short2.md\n\n[ref6][]\n",
        "known_divergence": None,
    },
    {
        "name": "label_normalization_case_insensitive",
        "category": "reference-link-usage-forms",
        "markdown": "[Foo]: dead-norm1.md\n\n[foo]\n",
        "known_divergence": None,
    },
    {
        "name": "label_normalization_whitespace_collapse",
        "category": "reference-link-usage-forms",
        "markdown": "[foo  bar]: dead-norm2.md\n\n[foo bar]\n",
        "known_divergence": None,
    },
    # --- blockquotes and ATX headings — no dedicated boundary, agree by ----
    # --- coincidence (neither is distinguished from ordinary prose) --------
    {
        "name": "blockquote_link",
        "category": "blockquotes-and-headings",
        "markdown": "> [x](dead-bq1.md)\n",
        "known_divergence": None,
    },
    {
        "name": "atx_heading_link",
        "category": "blockquotes-and-headings",
        "markdown": "# [x](dead-h1.md)\n",
        "known_divergence": None,
    },
    # --- empty / whitespace-only destinations, unbracketed form ------------
    # Extends the already-settled WI-0060/WI-0061 exception (`[x](<>)`) to
    # the plain, unbracketed `[x]()` / `[x]( )` forms — not a new gap, the
    # same "nothing to check" design this tool already commits to for an
    # empty destination, confirmed here to hold for the syntax most likely
    # to actually occur in a hand-written index.
    {
        "name": "empty_destination_plain_parens",
        "category": "empty-and-whitespace-destinations",
        "markdown": "[x]()\n",
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "CommonMark renders `[x]()` as `<a href=\"\">x</a>` — "
                "technically a link, to an empty destination. check (n)'s "
                "own `[[ -n \"$target\" ]]` empty-target guard (already "
                "settled for the angle-bracket form `[x](<>)` under "
                "WI-0060/WI-0061) skips it: an empty href has no file to "
                "test existence against, so silence is correct for this "
                "tool's purpose, not a conformance gap. Recorded as a "
                "`known_divergence` only because the generator's oracle "
                "comparison is literal (reference says '', check (n) says "
                "nothing checked) — this fixture extends the existing "
                "exception's scope to the unbracketed form, it does not "
                "add a new one."
            ),
            "work_item": "WI-0005",
        },
    },
    {
        "name": "whitespace_only_destination_plain_parens",
        "category": "empty-and-whitespace-destinations",
        "markdown": "[x]( )\n",
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "Same exception as empty_destination_plain_parens — "
                "CommonMark trims the whitespace-only destination to an "
                "empty href (`<a href=\"\">`), and check (n) lands on the "
                "same empty target, silently skipped by the same guard."
            ),
            "work_item": "WI-0005",
        },
    },
    # --- emphasis inside link text ------------------------------------------
    {
        "name": "emphasis_in_link_text",
        "category": "emphasis-in-link-text",
        "markdown": "[*a* b](dead-em1.md)\n",
        "known_divergence": None,
    },
]


def reference_hrefs(markdown_text):
    html = commonmark.commonmark(markdown_text)
    return re.findall(r'<a href="([^"]*)"', html)


def checkable_targets(hrefs):
    """Mirrors memory-lint.sh's own exclusion list (images already excluded
    structurally — CommonMark never renders `![x](y)` as `<a>`)."""
    out = []
    for href in hrefs:
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        out.append(href)
    return out


def run_memory_lint(markdown_text):
    """Runs the real script against one entry, isolated in its own scratch
    project — the same shape MemoryLintTest.write_index() uses in
    test_memory_lint.py, minus the shared per-class fixture state."""
    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp) / "project"
        (project_dir / "docs" / "memory").mkdir(parents=True)
        (project_dir / "docs" / "memory" / "MEMORY.md").write_text(
            "# Memory Index\n\n" + markdown_text, encoding="utf-8"
        )
        fake_home = Path(tmp) / "home"
        fake_home.mkdir()
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), str(project_dir)],
            capture_output=True, text=True,
            env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        )
        return sorted(FINDING_RE.findall(result.stdout))


def main():
    if shutil.which("bash") is None:
        print("generator requires bash on PATH", file=sys.stderr)
        return 1

    names = [entry["name"] for entry in CORPUS]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        print(f"duplicate corpus entry name(s): {sorted(duplicates)}", file=sys.stderr)
        return 1

    fixture_entries = []
    problems = []

    for entry in CORPUS:
        hrefs = reference_hrefs(entry["markdown"])
        expected_reference_targets = sorted(checkable_targets(hrefs))
        observed_check_n_findings = run_memory_lint(entry["markdown"])

        actually_diverges = observed_check_n_findings != expected_reference_targets
        claims_divergence = entry["known_divergence"] is not None
        claims_intent = entry.get("documented_intent") is not None

        if claims_divergence and claims_intent:
            problems.append(
                f"{entry['name']}: carries BOTH known_divergence and "
                f"documented_intent — pick exactly one (an open gap in "
                f"check (n) vs. a deliberate PO decision) or the fixture "
                f"cannot tell which explanation applies"
            )
        if claims_divergence and not actually_diverges:
            problems.append(
                f"{entry['name']}: known_divergence claimed but the two oracles "
                f"AGREE (reference={expected_reference_targets!r}, "
                f"check(n)={observed_check_n_findings!r}) — remove the claim "
                f"or the entry no longer reproduces it"
            )
        if claims_intent and not actually_diverges:
            problems.append(
                f"{entry['name']}: documented_intent claimed but the two "
                f"oracles AGREE (reference={expected_reference_targets!r}, "
                f"check(n)={observed_check_n_findings!r}) — remove the claim, "
                f"there is no longer a disagreement for the PO decision to "
                f"cover"
            )
        if not claims_divergence and not claims_intent and actually_diverges:
            problems.append(
                f"{entry['name']}: no known_divergence or documented_intent "
                f"recorded but the two oracles DISAGREE "
                f"(reference={expected_reference_targets!r}, "
                f"check(n)={observed_check_n_findings!r}) — this is a NEW, "
                f"previously unrecorded divergence; add a known_divergence "
                f"block (an open gap in check (n)) or a documented_intent "
                f"block (a deliberate PO decision) before regenerating"
            )

        fixture_entries.append({
            "name": entry["name"],
            "category": entry["category"],
            "markdown": entry["markdown"],
            "reference_hrefs": hrefs,
            "reference_checkable_targets": expected_reference_targets,
            "expected_check_n_findings": observed_check_n_findings,
            "known_divergence": entry["known_divergence"],
            **({"caveat": entry["caveat"]} if "caveat" in entry else {}),
            "documented_intent": entry.get("documented_intent"),
        })

    if problems:
        print("Generator refuses to write a fixture with unverified claims:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    fixture = {
        "commonmark_version": getattr(commonmark, "__version__", None) or "0.9.2",
        "generated_by": "scripts/tests/fixtures/generate_commonmark_corpus.py",
        "entry_count": len(fixture_entries),
        "entries": fixture_entries,
    }
    FIXTURE_PATH.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {FIXTURE_PATH} ({len(fixture_entries)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
