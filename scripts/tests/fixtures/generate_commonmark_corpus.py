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

    GUARD ON THIS CLASS (PO decision 24.08.2026). `documented_intent` may
    only be assigned when the justification would still hold if NO criterion
    depended on it. Ask it in that order, and in those words: would this
    still be the right behaviour if reclassifying it changed nothing about
    whether the round counts as clean? If the answer needs the criterion to
    be interesting, the entry is a `known_divergence` and the criterion is
    supposed to notice.

    WI-0085 is the precedent because its reasoning was settled BEFORE any
    promotion criterion was in play: an unused reference definition pointing
    at a deleted file is a dead pointer whether or not anything renders it,
    and the fact that it renders as nothing is what makes it worth reporting
    rather than what excuses it. WI-0092 (a link inside image alt text) was
    admitted on exactly that argument, not on the fact that admitting it
    emptied the ledger.

    The guard exists because the incentive runs the other way: a false
    positive is cheapest to remove by relabelling it, and this field is the
    label. A round that ends clean because a divergence changed its name has
    measured nothing.

    THIS GUARD IS NOT MACHINE-ENFORCEABLE, and saying so is part of it. What
    the code below does check is that the two blocks are mutually exclusive,
    that whichever one is present matches a disagreement the generator
    actually measured, that its required fields are non-empty, and (in
    FixtureIntegrityTest) that its work item is on a closed allowlist. None of
    that can tell a well-reasoned `documented_intent` from a relabelled false
    positive: both carry a reason, a po_decision and a work item, and both
    reproduce. The question above is a question for a READER. Its checkpoint
    is the review of the round that adds or reclassifies an entry, and a
    reclassification is therefore something to raise there explicitly rather
    than to let a green suite carry.

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
        # Divergence closed by WI-0080 (23.08.2026): the `[^][]*` label regex was
        # replaced by a bracket-stack scanner, so a balanced pair in the link text
        # is ordinary content and this entry now agrees with the reference.
        "known_divergence": None,
    },
    {
        "name": "nested_brackets_in_link_text_mid_sentence",
        "category": "nested-brackets-in-link-text",
        "markdown": "before [a [b] c](dead-esc2.md) after\n",
        # Divergence closed by WI-0080 (23.08.2026), same fix as the entry above.
        # Kept as the mid-paragraph-prose variant so the closure is not pinned to
        # bullet-list context alone.
        "known_divergence": None,
    },
    {
        "name": "nested_brackets_outer_literal_inner_real_link",
        "category": "nested-brackets-in-link-text",
        "markdown": "[a [b](dead-nb2-inner.md) c](dead-nb2-outer.md)\n",
        "known_divergence": None,
    },
    {
        # WI-0080: three nesting levels, not one. The regex this round replaced
        # failed at depth 1 already, so a fix that only tolerated a single pair
        # would have looked green on the two entries above — this one discriminates
        # a real stack from a special case. (The reference imposes no depth limit;
        # measured to 100 during the WI-0080 round.)
        "name": "nested_brackets_three_levels_in_link_text",
        "category": "nested-brackets-in-link-text",
        "markdown": "[a [b [c] d] e](dead-nb3.md) — three levels\n",
        "known_divergence": None,
    },
    {
        # WI-0080 negative pin. `[a]` closes on its own, so the second `]` has no
        # opener left and the reference renders NO link. The entry exists because
        # the obvious wrong repair — "widen the label class" or "split at the last
        # `](`" — reports `dead-nb4.md` here. Its value is in staying EMPTY.
        "name": "unbalanced_closing_bracket_is_not_a_link",
        "category": "nested-brackets-in-link-text",
        "markdown": "[a] b](dead-nb4.md) — not a link\n",
        "known_divergence": None,
    },
    {
        # WI-0080: the inner link wins AND the disqualified outer opener must not
        # swallow the rest of the line. Sibling of the entry above with a third,
        # independent link after the nested construct.
        "name": "link_in_link_text_inner_wins_beside_a_later_link",
        "category": "nested-brackets-in-link-text",
        "markdown": (
            "[a [b](dead-nb5-inner.md) c](dead-nb5-outer.md) and "
            "[d](dead-nb5-later.md)\n"
        ),
        "known_divergence": None,
    },
    # --- images inside link text (WI-0091) -----------------------------------
    {
        # WI-0091, the badge pattern. An IMAGE in the link text does not
        # disqualify the enclosing link (only a LINK does), so the reference
        # renders a live `<a href="dead-img1.md">` around an `<img>`. Hardest
        # shape for any non-scanner repair: the LABEL itself contains a `](`.
        "name": "image_in_link_text_badge_pattern",
        "category": "images-in-link-text",
        "markdown": "[![alt](dead-badge1.png)](dead-img1.md) — badge\n",
        "known_divergence": None,
    },
    {
        # WI-0091 at depth: one link, two images, no image ever reported.
        "name": "image_nested_two_deep_in_link_text",
        "category": "images-in-link-text",
        "markdown": "[![![deep](dead-badge2.png)](dead-badge3.png)](dead-img2.md)\n",
        "known_divergence": None,
    },
    {
        # WI-0091 negative pin: a plain image with a BRACKETED alt text. The old
        # code decided "image" on the single byte before `[`; the scanner decides
        # it on the opener it pushed, and must still stay silent on a label the
        # old regex could never have matched.
        "name": "image_with_bracketed_alt_text_is_not_a_link",
        "category": "images-in-link-text",
        "markdown": "![[a]](dead-img3.png) — image\n",
        "known_divergence": None,
    },
    # --- reference links in the link text (WI-0093) --------------------------
    # CommonMark's "no links in links" rule fires on any successful LINK, not
    # only an inline one — a RESOLVING shortcut/collapsed/full reference in the
    # link text deactivates the enclosing openers exactly like `[b](in.md)`
    # does. Whether it resolves is the only thing separating these entries from
    # `nested_brackets_in_link_text_simple` above, which must stay a live link.
    {
        "name": "shortcut_reference_in_link_text_disqualifies_outer",
        "category": "reference-links-in-link-text",
        "markdown": "[ref5]: dead-refdis1.md\n\n[outer [ref5] text](dead-refout1.md)\n",
        "known_divergence": None,
    },
    {
        # The architectural entry: CommonMark collects reference DEFINITIONS for
        # the whole document before parsing any inline content, so a definition
        # may stand AFTER its use. A single-pass extractor cannot answer this at
        # the moment it reaches the link — check (n) reads each index twice.
        "name": "reference_definition_after_its_use_still_disqualifies",
        "category": "reference-links-in-link-text",
        "markdown": "[outer [ref6] text](dead-refout2.md)\n\n[ref6]: dead-refdis2.md\n",
        "known_divergence": None,
    },
    {
        # The counter-entry that forbids the cheap repair ("deactivate whenever
        # no inline destination follows"): an UNDEFINED label in the link text
        # changes nothing and the outer link stays live.
        "name": "undefined_label_in_link_text_keeps_the_outer_link",
        "category": "reference-links-in-link-text",
        "markdown": "[outer [nosuchlabel] text](dead-refout3.md)\n",
        "known_divergence": None,
    },
    {
        "name": "full_reference_in_link_text_disqualifies_outer",
        "category": "reference-links-in-link-text",
        "markdown": "[ref7]: dead-refdis3.md\n\n[outer [txt][ref7] text](dead-refout4.md)\n",
        "known_divergence": None,
    },
    {
        # Measured and NOT obvious: the first label IS defined, but a FAILED
        # full reference does not fall back to the shortcut reading — no link
        # forms inside, so nothing is deactivated. The definition target is an
        # external URL here so that the definition line, which stays unused,
        # does not drag the WI-0085 unused-definition divergence into an entry
        # about something else; both oracles skip an external scheme.
        "name": "failed_full_reference_keeps_the_outer_link",
        "category": "reference-links-in-link-text",
        "markdown": (
            "[ref8]: https://example.com/ref8\n\n"
            "[outer [ref8][nosuchlabel] text](dead-refout5.md)\n"
        ),
        "known_divergence": None,
    },
    {
        # WI-0091's rule restated for the reference form: `![ref]` is an IMAGE
        # even when it resolves, and an image in the link text does not
        # disqualify the enclosing link. External definition target for the same
        # reason as the entry above — an image reference renders `<img>`, never
        # `<a>`, so a checkable one would show up as a WI-0085-shaped divergence.
        "name": "image_reference_in_link_text_keeps_the_outer_link",
        "category": "reference-links-in-link-text",
        "markdown": (
            "[ref9]: https://example.com/ref9.png\n\n"
            "[outer ![ref9] text](dead-refout6.md)\n"
        ),
        "known_divergence": None,
    },
    {
        # A resolved reference link CONSUMES its second label: the reference
        # reads `[txt][ref10]` as the link and leaves `(dead-refparen.md)` as
        # literal text. An extractor that only deactivated, without consuming,
        # would re-read `[ref10](dead-refparen.md)` as an inline link.
        "name": "resolved_reference_link_consumes_a_following_parenthesis",
        "category": "reference-links-in-link-text",
        "markdown": "[ref10]: dead-refdis4.md\n\n[txt][ref10](dead-refparen.md)\n",
        "known_divergence": None,
    },
    {
        # A reference definition is a BLOCK construct: inside a fence it is
        # code and defines nothing, so the outer link stays live. Pins that the
        # label collection runs the same block machine as the extraction rather
        # than grepping the file for definition-shaped lines.
        "name": "reference_definition_inside_a_fence_defines_nothing",
        "category": "reference-links-in-link-text",
        "markdown": (
            "```\n[ref11]: dead-fenced.md\n```\n\n"
            "[outer [ref11] text](dead-refout7.md)\n"
        ),
        "known_divergence": None,
    },
    {
        # A reference definition may not INTERRUPT a paragraph — with prose open
        # above it the reference reads the line as ordinary text, defines
        # nothing and renders the outer link. Divergence closed by WI-0096
        # (24.08.2026): check (n) now asks the paragraph buffer whether a
        # definition-shaped line could open a block at all, and stays silent
        # when it could not. It is NOT the WI-0085 decision one shape further
        # along — the two are separated by what the reader sees. WI-0085's
        # lone `[ref]: dead.md` renders as NOTHING, so its dead pointer is
        # invisible and worth reporting; here the very same bytes render as
        # visible paragraph prose, which makes the path ordinary text rather
        # than a pointer. The refmap deliberately does not treat the line as a
        # definition either, which is why the OUTER link is still reported.
        "name": "reference_definition_cannot_interrupt_a_paragraph",
        "category": "reference-links-in-link-text",
        "markdown": (
            "some prose\n[ref12]: dead-interrupt.md\n\n"
            "[outer [ref12] text](dead-refout8.md)\n"
        ),
        "known_divergence": None,
    },
    {
        # The sibling of the entry above, decided by the same rule and answered
        # by a DIFFERENT gate (measured 24.08.2026). A link label needs at
        # least one non-whitespace character, so `[ ]:` opens no definition and
        # the reference renders the line as visible paragraph text -- the
        # WI-0096 verdict, not the WI-0085 one: nothing here is invisibly dead.
        # check (n) agrees today, and it does so through `reflbl != ""` in the
        # definition branch, not through the paragraph-buffer gate WI-0096
        # added: with the gate removed the line still stays silent, with
        # `reflbl != ""` removed it reports `dead-wsdefn.md`. Untested until
        # now, which is what this entry changes.
        "name": "whitespace_only_label_is_not_a_reference_definition",
        "category": "reference-links-in-link-text",
        "markdown": "[ ]: dead-wsdefn.md\n",
        "known_divergence": None,
    },
    {
        # Same gate, shortest input: an explicitly EMPTY label. Kept beside the
        # whitespace one because the two reach `reflbl == ""` by different
        # routes (nothing to fold vs. folded away) and a repair could easily
        # keep one and lose the other.
        "name": "empty_label_is_not_a_reference_definition",
        "category": "reference-links-in-link-text",
        "markdown": "[]: dead-emptydefn.md\n",
        "known_divergence": None,
    },
    # --- a wrong destination span no longer swallows a real link (WI-0095,
    # closed) ------------------------------------------------------------
    # protect_link_destinations() used to wrap the text after ANY `](` in an
    # opaque dest_mark span, without checking that a live link opener
    # preceded it and without an escape-parity test on the `]` itself. Since
    # WI-0080 the scanner skips a dest_mark span WHOLESALE, so a wrong span
    # used to hide the real link inside it. The repair reuses the same
    # left-to-right opener-stack scan process_link_line() already runs: a
    # `]` only opens a destination when it just closed a live, unescaped `[`
    # AND is immediately followed by `(`. Both fixtures below now agree with
    # the reference on both oracles, so neither carries a known_divergence
    # block any more.
    {
        "name": "stray_close_bracket_paren_span_hides_a_later_link",
        "category": "destination-span-overreach",
        "markdown": "x](y [a](dead-span1.md) z)\n",
        "known_divergence": None,
    },
    {
        # The same construct reached through an ESCAPED `]` — the escape
        # parity half of the same fix. Kept as its own fixture because the
        # escape blindness and the missing opener check were two separate
        # omissions in the same function, and a repair could have closed
        # only one.
        "name": "escaped_close_bracket_paren_span_hides_a_later_link",
        "category": "destination-span-overreach",
        "markdown": "x\\](y [a](dead-span2.md) z)\n",
        "known_divergence": None,
    },
    # --- a stray sentinel byte in the source (WI-0097) -----------------------
    {
        # protect_link_destinations() fences every inline destination between
        # two 0x03 sentinel bytes and the WI-0080 scanner skips such a span
        # wholesale — so a literal 0x03 byte in the SOURCE pairs with the
        # opening sentinel of the next real destination and eats the link
        # between them. Same family as the destination-span entries above: a
        # span that should not exist, skipped as a unit. Direction: false
        # negative. Pathological input (a control byte in a Markdown index),
        # left open rather than fixed in the round that found it.
        "name": "stray_sentinel_byte_swallows_the_following_link",
        "category": "destination-span-overreach",
        "markdown": "a \x03 stray sentinel byte and [x](dead-stray1.md)\n",
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "The reference renders the 0x03 byte as ordinary text and "
                "`[x](dead-stray1.md)` as a link. check (n) reads the stray "
                "byte as the OPENING sentinel of a protected destination, "
                "skips everything up to the next sentinel -- which is the one "
                "opening the real destination -- and the link vanishes. The "
                "loss does not stop there: the sentinel CLOSING that "
                "destination is then unpaired, the scanner returns, and the "
                "whole remainder of the paragraph goes unscanned. See "
                "stray_sentinel_byte_swallows_the_rest_of_the_paragraph for "
                "the fixture that pins that reach. "
                "4f2ffa7 reported it, because its extractor re-scanned inside "
                "a sentinel span instead of skipping it."
            ),
            "work_item": "WI-0097",
        },
    },
    {
        # The reach of the same defect, pinned rather than described. The entry
        # above ends at the swallowed link, so it cannot tell "the link between
        # the two sentinels is lost" apart from "everything from the stray byte
        # on is lost". A second, INDEPENDENT link after the construct settles
        # it: it is also gone, because the unpaired closing sentinel makes the
        # scanner return from the whole paragraph.
        "name": "stray_sentinel_byte_swallows_the_rest_of_the_paragraph",
        "category": "destination-span-overreach",
        "markdown": (
            "a \x03 stray sentinel byte and [x](dead-stray2.md) "
            "and [y](dead-stray3.md)\n"
        ),
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "The reference renders BOTH links. check (n) reports neither: "
                "the stray byte pairs with the first destination's opening "
                "sentinel, that destination's CLOSING sentinel then finds no "
                "partner, and the scanner leaves the paragraph -- so the reach "
                "is the rest of the paragraph, not just the link between the "
                "two sentinels. This is the control line the single-link entry "
                "above lacks: without it, an assertion of no findings is also "
                "satisfied by a scanner that never ran."
            ),
            "work_item": "WI-0097",
        },
    },
    # --- a link inside IMAGE ALT TEXT (WI-0092) ------------------------------
    {
        # `![a [b](in.md) c](out.png)` -- the outer construct is an image, and
        # CommonMark renders its alt text as PLAIN TEXT: the inner `[b](in.md)`
        # produces no <a href> at all. check (n) reports `in.md` anyway,
        # because its scanner excludes the IMAGE from being reported but still
        # walks its label and reports an inline link found there.
        "name": "link_inside_image_alt_text_is_reported",
        "category": "images",
        "markdown": "![a [b](dead-alt-in.md) c](dead-alt-out.png)\n",
        "known_divergence": None,
        "documented_intent": {
            "reason": (
                "PO decision 23.08.2026 (WI-0092): INTENDED, on exactly the "
                "WI-0085 grounds. check (n)'s contract is narrower than "
                "conformance -- does this index still point at existing "
                "files? -- and `dead-alt-in.md` is a path an author wrote and "
                "can delete. The reference renders it as NOTHING (it "
                "collapses into the alt attribute), so no reader notices it "
                "on a normal read, and that invisibility is the failure mode "
                "check (n) was built against. The reasoning stands "
                "independently of any promotion criterion: it is the same "
                "argument WI-0085 settled before a criterion was in play, "
                "applied to the same shape one construct over. Pre-existing "
                "and unchanged by WI-0080/WI-0093 -- 4f2ffa7 behaves "
                "identically, measured."
            ),
            "po_decision": "23.08.2026",
            "work_item": "WI-0092",
        },
    },
    # --- the false negative WI-0098's fix buys (WI-0098) ---------------------
    # THE CLASS, not one shape. The definition side registers its label in the
    # shape the scanner reads (code spans deleted, closed inline comments
    # replaced by `boundary`), so that a rewritten label can match at all. That
    # mapping is NOT INJECTIVE: several distinct raw labels share one resolved
    # key. Once ANY definition owns such a key, every OTHER label collapsing to
    # it looks like a resolving reference and silences the link enclosing it,
    # even though the reference resolves none of them.
    #
    # The mapping has two accumulation points, and both are measured below:
    #
    #   * the EMPTY key -- reached by a code-span-only label (``[`x`]``), by a
    #     literal `[]`, and by a whitespace-only `[   ]`. The last two are the
    #     wider half of the class: the REFERENCE never looks up an empty label
    #     at all (a link label needs one non-whitespace character), while the
    #     scanner keys on the resolved shape and finds one.
    #   * the `boundary` key -- reached by ANY label that is exactly one closed
    #     inline comment, so `[<!--a-->]` and `[<!--b-->]`, two labels with
    #     nothing in common, are interchangeable here.
    #
    # Each divergent entry is paired with a control carrying the SAME label but
    # no colliding definition, where the outer link IS reported: that pins the
    # false negative on the COLLISION and not on the label shape alone.
    # Deliberately traded for the false POSITIVE it replaces.
    {
        "name": "two_labels_with_the_same_resolved_shape_are_interchangeable",
        "category": "reference-links-in-link-text",
        "markdown": (
            "[`r22`]: dead-collide-defn.md\n"
            "\n"
            "Uses it here: [`r22`] and then "
            "[outer [`other`] text](dead-collide-outer.md)\n"
        ),
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "The reference renders two links: the shortcut reference "
                "``[`r22`]`` to dead-collide-defn.md, and the outer link to "
                "dead-collide-outer.md, because ``[`other`]`` is a DIFFERENT "
                "label and resolves to nothing. check (n) compares the two in "
                "their resolved shape, where both are the empty label, so "
                "``[`other`]`` looks like a resolving reference and "
                "deactivates the link enclosing it. This is the whole class, "
                "not this shape: label resolution is not injective, and its "
                "two accumulation points are the EMPTY key (a code-span-only "
                "label, a literal `[]`, a whitespace-only `[   ]`) and the "
                "`boundary` key (any label that is exactly one closed inline "
                "comment). The `[]` and `[   ]` halves are wider than this "
                "entry: the reference does not look up an empty label at all, "
                "while the scanner keys on one -- see the four entries after "
                "this one, each paired with a no-definition control. PO "
                "decision 24.08.2026: accepted in trade for the false "
                "POSITIVE this replaces -- a rewritten label matched no "
                "definition at all before, and an outer link the reference "
                "does not render was reported. A false negative may be traded "
                "in for a false positive; not the other way round."
            ),
            "work_item": "WI-0098",
        },
    },
    {
        # Empty key, reached by a LITERAL `[]` in the link text. The reference
        # never looks an empty label up (a link label needs one non-whitespace
        # character), so it renders the outer link; the scanner resolves
        # ``[`r30`]`` to the same empty key and reads `[]` as resolving.
        "name": "literal_empty_label_in_link_text_collides_with_a_definition",
        "category": "reference-links-in-link-text",
        "markdown": (
            "[`r30`]: dead-empty-defn.md\n"
            "\n"
            "Uses it: [`r30`] and then [outer [] text](dead-empty-outer.md)\n"
        ),
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "WI-0098 class, empty-key half. The reference renders BOTH "
                "links -- the shortcut ``[`r30`]`` and the outer one -- "
                "because a literal `[]` is not a link label at all there. "
                "check (n) resolves the definition label to the empty key and "
                "then reads `[]` in the link text as a reference resolving "
                "against it, which deactivates the enclosing opener and "
                "silences dead-empty-outer.md. Same trade as the entry above."
            ),
            "work_item": "WI-0098",
        },
    },
    {
        # The control that pins the collision. Same `[]` in the same position,
        # no definition resolving to the empty key -- and the outer link IS
        # reported. Without it the entry above would be consistent with "any
        # `[]` in link text silences the link", which is not what happens.
        "name": "literal_empty_label_in_link_text_without_a_definition_control",
        "category": "reference-links-in-link-text",
        "markdown": "[outer [] text](dead-empty-ctl.md)\n",
        "known_divergence": None,
    },
    {
        # Empty key, reached by a WHITESPACE-ONLY label. Same half of the class
        # as the entry above, different route to the key.
        "name": "whitespace_only_label_in_link_text_collides_with_a_definition",
        "category": "reference-links-in-link-text",
        "markdown": (
            "[`r31`]: dead-wslabel-defn.md\n"
            "\n"
            "Uses it: [`r31`] and then "
            "[outer [   ] text](dead-wslabel-outer.md)\n"
        ),
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "WI-0098 class, empty-key half, whitespace route. A label of "
                "nothing but spaces carries no non-whitespace character, so "
                "the reference is not looking at a link label and renders the "
                "outer link. normalize_label() folds it to the empty key, "
                "which the definition ``[`r31`]`` already owns, so check (n) "
                "reads it as resolving and drops dead-wslabel-outer.md."
            ),
            "work_item": "WI-0098",
        },
    },
    {
        "name": "whitespace_only_label_in_link_text_without_a_definition_control",
        "category": "reference-links-in-link-text",
        "markdown": "[outer [   ] text](dead-wslabel-ctl.md)\n",
        "known_divergence": None,
    },
    {
        # The OTHER accumulation point. `<!--a-->` and `<!--b-->` share no
        # bytes beyond the comment delimiters, but resolve_paragraph() replaces
        # each closed comment with the single `boundary` byte, so both labels
        # arrive as the same key.
        "name": "boundary_labels_from_two_different_comments_collide",
        "category": "reference-links-in-link-text",
        "markdown": (
            "[<!--a-->]: dead-boundary-defn.md\n"
            "\n"
            "Uses it: [<!--a-->] and then "
            "[outer [<!--b-->] text](dead-boundary-outer.md)\n"
        ),
        "known_divergence": {
            "direction": "false-negative",
            "reason": (
                "WI-0098 class, `boundary`-key half. The reference renders "
                "both links: `[<!--a-->]` resolves against its definition and "
                "`[<!--b-->]` is simply an undefined label, leaving the outer "
                "link alive. check (n) resolves every closed inline comment to "
                "the same single `boundary` byte, so the two labels are one "
                "key and `[<!--b-->]` deactivates the opener around it. This "
                "is why the class is stated as non-injectivity rather than as "
                "the empty label: no empty label is involved here at all."
            ),
            "work_item": "WI-0098",
        },
    },
    {
        "name": "comment_label_in_link_text_without_a_definition_control",
        "category": "reference-links-in-link-text",
        "markdown": "[outer [<!--b-->] text](dead-boundary-ctl.md)\n",
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
        # Divergence closed by WI-0080 (23.08.2026): the scanner treats an escaped
        # bracket as label CONTENT (is_escaped(), backslash-run parity) instead of
        # excluding the byte from the label class outright.
        "known_divergence": None,
    },
    {
        # WI-0094: the DEFINITION side of the same label grammar WI-0080 fixed
        # on the usage side. `[a\]b]: dest.md` is one definition at the
        # reference (label `a]b`), but check (n) recognised a definition with
        # `\[[^][]+\]:`, which excludes `]` regardless of a preceding
        # backslash -- so the line was not a definition at all, its target went
        # unchecked, and its label stayed undefined for the WI-0093 rule.
        "name": "backslash_escaped_bracket_in_reference_definition_label",
        "category": "backslash-escapes",
        "markdown": "[a\\]b]: dead-escdefn.md\n\ntext [a\\]b] more\n",
        "known_divergence": None,
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
