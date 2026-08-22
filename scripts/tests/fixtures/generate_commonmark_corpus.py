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

Where the two oracles disagree, the entry must carry a `known_divergence`
block (direction, reason, work_item) in the CORPUS list below — the
generator refuses to write a fixture where they disagree silently, and
refuses to write a `known_divergence` block that the measurement does not
actually confirm (a claimed divergence must be an observed one). This is the
"gezaehlt und benannt" contract WI-0005 asks for: the promotion criterion
("a round producing no new items") becomes measurable only if every
divergence recorded here was actually seen to diverge.
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
            "direction": "wrong-target",
            "reason": (
                "CommonMark decodes `&num;` to `#` in the destination "
                "(reference href: `dead#3-ent2.md`, i.e. file `dead` with "
                "fragment `3-ent2.md`). check (n) never decodes entities in "
                "destinations — it resolves the literal raw substring "
                "`dead&num;3-ent2.md` as one filename instead, a different "
                "existence question than the one CommonMark actually asks."
            ),
            "work_item": "WI-0005",
        },
    },
    {
        "name": "entity_reference_decimal_in_destination",
        "category": "entity-references",
        "markdown": "[x](dead&#35;3-ent3.md) — decimal entity in destination\n",
        "known_divergence": {
            "direction": "wrong-target",
            "reason": (
                "`&#35;` decodes to `#` at the reference (href "
                "`dead#3-ent3.md`) same as the named-entity case, but here "
                "the RAW markdown already contains a literal `#` byte as "
                "part of the entity's own syntax (`&`, `#`, `3`, `5`, `;`). "
                "check (n)'s shell-side fragment-stripping "
                "(`${target%%#*}`) runs on the raw, undecoded text and cuts "
                "at that byte, truncating the resolved target to `dead&` — "
                "a different and more severely garbled path than the named-"
                "entity sibling, same root cause (no entity decoding) "
                "compounded by the pre-existing naive `#`-split."
            ),
            "work_item": "WI-0005",
        },
    },
    # --- backslash escapes ---------------------------------------------------
    {
        "name": "backslash_escaped_link_is_not_a_link",
        "category": "backslash-escapes",
        "markdown": "before \\[not a link\\](dead-esc1.md) after\n",
        "known_divergence": {
            "direction": "false-positive",
            "reason": (
                "`\\[` and `\\]` are CommonMark backslash escapes — the "
                "whole construct renders as literal text "
                "(`[not a link](dead-esc1.md)`), not a link. check (n)'s "
                "label/dest regex has no escape awareness and matches "
                "starting at the `[` right after the first backslash, "
                "reporting `dead-esc1.md` as a dead link target that was "
                "never a link at all. Predicted in the WI-0005 briefing; "
                "confirmed here by measurement."
            ),
            "work_item": "WI-0005",
        },
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
        "known_divergence": {
            "direction": "wrong-target",
            "reason": (
                "The reference decodes the escape (href `dead-esc4).md`, "
                "one real link). check (n)'s destination capture "
                "`[^)]*` stops at the first literal `)` regardless of a "
                "preceding backslash, so it resolves only the truncated, "
                "garbled `dead-esc4\\` — losing `.md)` entirely. Same root "
                "cause as the entity-in-destination cases: a naive "
                "stop-character scan with no escape/entity awareness, "
                "triggered here via a backslash instead of an entity."
            ),
            "work_item": "WI-0005",
        },
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
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "Reference: the setext underline closes the heading block "
                "(`<h1>`code with a <a href=\"dead-setext-e.md\">link</a> "
                "inside</h1>`), so the unpaired backtick in the heading text "
                "stays literal and BOTH links (dead-setext-e.md in the "
                "heading, dead-setext-f.md in the following paragraph) are "
                "real. A setext-heading underline is not in check (n)'s "
                "block-boundary list (blank line / list marker / ATX "
                "heading / fence / block HTML comment, per the WI-0050 "
                "comment in memory-lint.sh) — it falls through to ordinary "
                "paragraph content, so all three lines merge into one "
                "buffer. The two backticks then pair with each other across "
                "the merge, swallowing dead-setext-e.md's link (and the "
                "`===` line) into a spurious code span; only dead-setext-"
                "f.md survives, after the closing backtick."
            ),
            "work_item": "WI-0005",
        },
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
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "Same root cause and shape as the setext case above, with a "
                "thematic break (`***`) in place of a setext underline: "
                "the reference treats it as its own block (`<hr />`), "
                "interrupting the paragraph, so both dead-tb-a.md and "
                "dead-tb-b.md are real, separate links. `***` is also "
                "absent from check (n)'s block-boundary list, so the three "
                "lines merge into one buffer and the two backticks pair "
                "across the `***` line, swallowing dead-tb-a.md's link; "
                "only dead-tb-b.md survives."
            ),
            "work_item": "WI-0005",
        },
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

        if claims_divergence and not actually_diverges:
            problems.append(
                f"{entry['name']}: known_divergence claimed but the two oracles "
                f"AGREE (reference={expected_reference_targets!r}, "
                f"check(n)={observed_check_n_findings!r}) — remove the claim "
                f"or the entry no longer reproduces it"
            )
        if not claims_divergence and actually_diverges:
            problems.append(
                f"{entry['name']}: no known_divergence recorded but the two "
                f"oracles DISAGREE (reference={expected_reference_targets!r}, "
                f"check(n)={observed_check_n_findings!r}) — this is a NEW, "
                f"previously unrecorded divergence; add a known_divergence "
                f"block before regenerating"
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
