#!/usr/bin/env bash
# manual-lint.sh — Read-only validator for a documentation index/detail-file
# contract (WI-0112a). Schema: templates/PHASE_DOC_SCHEMA.md, `## kind`
# section (vocabulary) and the `parent_index` row (resolution rule).
#
# Checks:
#   (a) parent_index resolves to an existing file — document-relative
#       first, root-fallback second. Same cascade phase-docs-lint.sh's
#       checks (f)/(g) already implement (scripts/phase-docs-lint.sh:274-
#       297), reused rather than reinvented: the fallback base there is
#       the project-directory argument (PROJECT_DIR); here, since this
#       script is generic over ANY root rather than hardwired to a
#       project layout, the fallback base is this script's own ROOT
#       argument — the same role, translated to a generic root.
#   (b) the REVERSE direction: an index named as `parent_index` by a
#       detail file must itself link that detail file back (a markdown
#       link whose destination is the document-relative path from the
#       index's own directory to the detail file). PHASE_DOC_SCHEMA.md
#       has named this direction as a documented-but-unvalidated
#       convention since it shipped ("Index-↔-detail consistency" —
#       "Nothing checks them"); this is the first check that does.
#   (c) `kind:` — when set, checked against the vocabulary documented in
#       templates/PHASE_DOC_SCHEMA.md's `## kind` section. That vocabulary is
#       the KNOWN set, not the ALLOWED set: CCPR cannot enumerate every
#       document genre a downstream project will legitimately invent, so an
#       unrecognised value is a WARNING (surface it for deliberate curation),
#       not an error (same open-enum precedent as memory-lint.sh check (c)'s
#       Tier-2 `type:` field — see that script's comment).
#   (f) derived-count markers — a number in prose, guarded by an inline HTML
#       comment on the SAME line, is compared against a value derived from the
#       repository. See the "Check (f)" block below for the full grammar and
#       the reasoning behind each of its rules. Every finding is an ERROR;
#       check (f) raises no warnings.
#
# WHY THE LETTERS JUMP FROM (c) TO (f) — this gap is deliberate, not a
# numbering accident. (d) and (e) are RESERVED by documentation standard v0.7
# for the frontmatter reliability fields, which are not built yet. Do not
# "repair" the sequence by renaming (f) to (d): the letter is referenced from
# the report's `**Checks:**` line, from templates/PHASE_DOC_SCHEMA.md, from
# scripts/tests/test_manual_lint.py and from CHANGELOG.md, and renaming it
# breaks all of them at once for no gain.
#
# Usage:
#   bash scripts/manual-lint.sh [<root-dir>]
#
# Generic over ANY documentation root — NOT hardwired to Manual/.
# install.sh does not copy Manual/ into ~/.claude (see Manual/README.md:2-5),
# so a script that defaulted to it would find nothing on every installed
# CCPR — the exact defect 0e76919 fixed for phase-docs-lint.sh's
# PHASE_FOLDERS default. Point it at whichever tree carries the
# kind/parent_index contract, e.g. `bash scripts/manual-lint.sh Manual`.
#
# Exit-Codes: 0 clean, 1 warnings, 2 errors.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/frontmatter.sh
source "$SCRIPT_DIR/lib/frontmatter.sh"

ROOT="${1:-$(pwd)}"

# The kind: KNOWN set — measured across this repository 26.08.2026 (WI-0112a):
# every distinct value any shipped file, template, or command prescribes.
# Mirrored verbatim in templates/PHASE_DOC_SCHEMA.md's `## kind` section —
# keep both in sync when a new kind is introduced. This is not a closed
# allow-list: a project may legitimately carry its own document genres this
# repository never saw (measured 26.08.2026 against two real CCPR-using
# projects — consumer-b, Org-X — 16 distinct unrecognised-but-legitimate
# values between them). is_valid_kind() below therefore only decides whether
# a value is RECOGNISED; check (c) reports an unrecognised one as a warning,
# not an error (measured 26.08.2026, follow-up to WI-0112a — no separate WI filed).
# Near-miss values seen in that measurement but deliberately NOT added, because
# each already has a canonical equivalent below that the source project deviated
# from rather than a genuinely new genre: `sprint-review` → use `review`;
# `story-index` → use `sub-index`. Don't re-add them without checking this note.
VALID_KINDS="adr api-resource-detail commands-doc-detail component-detail constitution detail entity-detail epic-detail frame learnings promotion-brief review risk-detail setup-detail sprint-detail sub-index system-doc-detail track-decision wireframe-detail"

is_valid_kind() {
    local k="$1"
    for v in $VALID_KINDS; do
        [[ "$k" == "$v" ]] && return 0
    done
    return 1
}

# rel_path <from_dir_abs> <to_file_abs> — the relative path FROM a
# directory TO a file, both given as absolute, already-normalized paths
# (produced via `cd ... && pwd`, so neither carries a ".." segment).
# Purely string-based: bash 3.2 (macOS default) ships no `realpath`, and
# the system `realpath` binary is not guaranteed present either. Splits
# both paths on "/", walks the shared prefix, then emits one "../" per
# remaining `from` segment followed by the remaining `to` segments —
# the canonical document-relative form this repository's own Manual/
# links already use (`[…](system/agents.md)`, no leading "./", no
# fragment): check (b) below does a literal substring match against
# that exact shape, not a general link-destination parser.
rel_path() {
    local from="$1" to="$2"
    local IFS=/
    local -a from_parts to_parts
    read -r -a from_parts <<< "$from"
    read -r -a to_parts <<< "$to"
    local i=0
    while [[ $i -lt ${#from_parts[@]} && $i -lt ${#to_parts[@]} \
        && "${from_parts[$i]}" == "${to_parts[$i]}" ]]; do
        i=$((i + 1))
    done
    local up=$(( ${#from_parts[@]} - i ))
    local result="" j=0
    while [[ $j -lt $up ]]; do
        result="../$result"
        j=$((j + 1))
    done
    local k=$i
    while [[ $k -lt ${#to_parts[@]} ]]; do
        result="${result}${to_parts[$k]}"
        k=$((k + 1))
        [[ $k -lt ${#to_parts[@]} ]] && result="${result}/"
    done
    printf '%s' "$result"
}

# ---------------------------------------------------------------------------
# Check (f) — derived-count markers
# ---------------------------------------------------------------------------
#
# GRAMMAR. An inline HTML comment on the SAME LINE as the number it guards:
#
#     CCPR ships 116 commands. <!-- ${MARKER_WORD} count ../commands/*.md -->
#
# Two verbs, and no others:
#   count <glob>  the derived value must EQUAL the number on the line.
#   floor <glob>  the derived value must be >= the number on the line. A floor
#                 stays silent while its subject GROWS and fires only when the
#                 derived value falls BELOW the claim. The verb exists because
#                 the already-settled README.md test-count decision
#                 ("2,600+ tests") needs >= semantics, and a contract that
#                 cannot express it would push that claim back to a hand-typed
#                 number — the thing this check is here to remove.
#
# RULES. All three are ERRORS (exit 2). Check (f) raises no warnings.
#
#   1. EXACTLY ONE number on the marked line, the marker comment itself
#      excluded. More than one, or none, is an error. The alternative —
#      set-membership semantics, "the derived value must appear among the
#      numbers on the line" — has a hole: `115 commands plus 1 = 116 total`
#      would pass on the presence of 116 while 115 is wrong. The one-number
#      rule closes it, at the price of forcing simple, pinnable sentences.
#      That price is the point: a sentence too tangled to pin is a sentence
#      whose numbers nobody can check either.
#   2. A glob that matches ZERO files is an ERROR, not a warning. A guard that
#      silently checks nothing is worse than no guard, because it also looks
#      like coverage (KA-G-017: "a check run that reports no scope is not a
#      pass"). The milder reading — warn, since a downstream project that
#      inherits this tree may not have the path — was considered and rejected:
#      if the path does not exist there, the claim in front of the marker is
#      unsupported for that project too, and the error points squarely at the
#      line that should have been adapted or deleted at project init.
#   3. Derived value vs. the number on the line: mismatch (`count`) or
#      shortfall (`floor`) is an error.
#
# NUMBER PARSING. A number is its VALUE, not its literal. A thousands
# separator binds into one number (`2,600` → 2600) but only in full
# three-digit groups, so `1,2` reads as two numbers and fails rule 1 rather
# than silently becoming 12. A trailing `+` (`2,600+ tests`, README.md's floor
# form) is prose ornament: it neither creates a number nor alters one. Leading
# zeros are read base-10, never octal.
#
# WHAT CHECK (f) IS NOT. It is OPT-IN BY MARKER and therefore a FALLBACK
# GUARD, NOT A DETECTOR: it can never find an UNMARKED wrong number. It is
# also deliberately limited to SIMPLE SINGLE-NUMBER claims. Multi-number
# anchor sentences — e.g. the command breakdown `3/5/4/23/4/12/22/5/4 = 82` —
# are explicitly NOT check (f) terrain and stay with
# scripts/tests/test_doc_counts_agree.py and its dedicated extractors, which
# can parse a shape this generic shell guard has no business modelling.
#
# VOCABULARY SEPARATION. This markdown marker vocabulary and the Python
# `<hash> pin: <group> <id>` vocabulary in scripts/tests/ are disjoint BY
# CORPUS, verified 05.09.2026 by reading the code rather than by assumption:
# pin_registry.corpus_files() (scripts/tests/pin_registry.py:906-913)
# enumerates scripts/tests/*.py + scripts/tests/workitems/*.py only and never
# sees a markdown file, and its MARKER_RE (pin_registry.py:87) requires a
# leading `#`, which an HTML comment does not have. In particular the Python
# `floor` group's admissibility rule ("a floor is admissible only where the
# same subject also carries a `set` pin", scripts/tests/test_pin_inventory.py)
# does NOT transfer to the markdown `floor` verb here — there is no
# cross-vocabulary rule, and none should be invented.
#
# A marker inside a FENCED CODE BLOCK is documentation OF the marker, not a
# live one, and is skipped. This repository has been bitten by that class
# before: memory-lint.sh's check (n) once reported bracketed text inside a
# code block as a dead link, and freeze-phase-docs.sh hoisted a fenced example
# header as a real `reviewed_head` value (see CHANGELOG.md). The fence rules
# mirror memory-lint.sh's own state machine: an opener is ``` or ~~~ (three or
# more, indented at most 3 spaces) and closes only on its OWN delimiter
# character, at a length at least the opener's.
#
# KNOWN LIMITATION, stated narrowly on purpose: that protection covers FENCED
# blocks only. A marker written inside an INLINE code span (single backticks)
# is still read as live. Closing it would mean parsing inline spans — backtick
# runs of arbitrary length, escapes — which is a markdown parser, not a guard
# clause; and the failure is fail-LOUD (an error nobody can miss), never a
# silent pass. Measured 05.09.2026: no line inside Manual/ — the only tree
# check-all.sh points this linter at — writes the marker syntax inline. Pinned
# by CheckFInlineCodeSpanLimitationTest so the limitation is a decision on
# record rather than something a later reader rediscovers.

# The literal word a marker comment opens with. Held in a variable, never
# written out next to `<!--` anywhere in this file, so that this script's own
# header examples above cannot be mistaken for live markers by any future
# scanner reading this file as documentation.
MARKER_WORD="pin:"

# Both marker regexes match against ONE COMMENT SPAN's content (the text
# between a `<!--` and its own `-->`), never against the raw line. Searching
# the raw line for a marker while counting numbers on the STRIPPED line is two
# different readings of the same text, and they disagree exactly where an
# outer comment encloses the marker: `<!-- TODO … <!-- pin: … -->` is ONE html
# comment (a comment ends at the FIRST `-->`), so the marker is commented out
# and must be inert — the raw-line search saw a live marker anyway and then
# reported the enclosing comment's now-empty prose as "0 numbers". Deriving
# both from the same walk makes that class unrepresentable rather than fixed.
F_MARKER_PRESENT_RE="^[[:space:]]*${MARKER_WORD}"
F_MARKER_RE="^[[:space:]]*${MARKER_WORD}[[:space:]]*([^[:space:]]+)[[:space:]]+([^[:space:]]+)[[:space:]]*$"
F_FENCE_OPEN_RE='^ {0,3}(`{3,}|~{3,})'
F_NUMBER_RE='[0-9]+(,[0-9][0-9][0-9])*'

# f_strip_markup <line> — the line with every complete `<!-- ... -->` span
# replaced by a single space, so rule 1 counts the numbers of the PROSE and
# never the digits of a glob (`assets2/*.txt`, `p3-*.md`). Every HTML comment
# is stripped, not just the marker: a line carrying both an unrelated comment
# and a marker would otherwise count the unrelated one's digits too. Result in
# F_STRIPPED (a global, not a command substitution: a subshell per marked line
# would buy nothing and bash 3.2 does not honour `set -e` inside one anyway).
#
# The two ends MUST be paired through `rest`, never taken independently off
# `$s`. Searching for the closer with `${s#*-->}` looks equivalent and is not:
# on a line carrying a literal `-->` EARLIER than the opener (`Flow A --> B, so
# there are 3 assets. <!-- ... -->`, an arrow in ordinary prose) it advances to
# the STRAY arrow, so the span between arrow and opener is emitted twice and a
# single-number line is rejected as carrying two. Found by an adversarial probe
# after the first implementation shipped green; see CheckFStrayArrowTest.
# An opener with no closer after it ends the loop with the remainder intact —
# an unterminated comment is prose here, not a licence to swallow the rest.
# It also collects each stripped span's CONTENT into F_SPANS, because that is
# where markers are looked for: one walk produces both the prose to count and
# the comments to interpret, so the two can never disagree about where a
# comment begins and ends.
F_STRIPPED=""
F_SPANS=()
f_strip_markup() {
    local s="$1" out="" head="" rest=""
    F_SPANS=()
    while [[ "$s" == *"<!--"* ]]; do
        head="${s%%<!--*}"
        rest="${s#*<!--}"
        [[ "$rest" == *"-->"* ]] || break
        out="$out$head "
        F_SPANS+=("${rest%%-->*}")
        s="${rest#*-->}"
    done
    F_STRIPPED="$out$s"
}

# f_extract_numbers <text> — every number in <text>, normalised to its base-10
# VALUE, into F_NUMBERS. Pure bash: `[[ =~ ]]` is a builtin, so this adds no
# external-tool invocation to the inventory scripts/tests/
# test_external_tool_exit_status.py pins.
F_NUMBERS=()
f_extract_numbers() {
    local text="$1" tok=""
    F_NUMBERS=()
    while [[ "$text" =~ $F_NUMBER_RE ]]; do
        tok="${BASH_REMATCH[0]}"
        F_NUMBERS+=("$((10#${tok//,/}))")
        text="${text#*"$tok"}"
    done
}

# f_count_glob <dir> <pattern> — how many paths <pattern> matches when
# expanded relative to <dir>, into F_GLOB_COUNT. The `cd` happens in a
# subshell so the caller's working directory is untouched and <dir>'s own
# characters never enter the glob word. With `nullglob` off (the default) an
# unmatched pattern expands to itself, which the `-e` test then rejects — so a
# pattern with no wildcard at all is simply a count of one named path.
F_GLOB_COUNT=0
f_count_glob() {
    local dir="$1" pattern="$2" out=""
    F_GLOB_COUNT=0
    [[ -d "$dir" ]] || return 0
    out="$(cd "$dir" && {
        c=0
        for m in $pattern; do
            if [ -e "$m" ]; then c=$((c + 1)); fi
        done
        printf '%s' "$c"
    })" || out=0
    [[ -n "$out" ]] || out=0
    F_GLOB_COUNT="$out"
}

errors=()
warnings=()
infos=()
err()  { errors+=("$1"); }
warn() { warnings+=("$1"); }
info() { infos+=("$1"); }

# Collect files. A missing ROOT is not distinguished from an existing-but-
# empty one in FILES_TOTAL — both end up scanning zero files — but the
# stderr notice below names which of the two it was, since "0 files
# scanned, 0 errors" would otherwise read as a clean pass either way
# (WI-0090/WI-0121 convention: an empty scan says so on stderr, not silence).
FILES=()
if [[ -d "$ROOT" ]]; then
    while IFS= read -r line; do
        FILES+=("$line")
    done < <(find "$ROOT" -type f -name "*.md")
fi
FILES_TOTAL=${#FILES[@]}

if [[ "$FILES_TOTAL" -eq 0 ]]; then
    if [[ ! -d "$ROOT" ]]; then
        echo "manual-lint: root '$ROOT' does not exist" >&2
    else
        echo "manual-lint: no markdown files found under $ROOT" >&2
    fi
fi

# ROOT_ABS — ROOT resolved to an absolute path once, up front, so every
# later "make this path human-readable relative to ROOT" strip (both in
# the per-file loop below and in check (b)) works against the SAME base
# regardless of whether ROOT itself was given relative or absolute on the
# command line. Only computed when ROOT exists — find() above already
# left FILES empty for a missing ROOT, so this is unreachable in that case.
ROOT_ABS=""
[[ -d "$ROOT" ]] && ROOT_ABS="$(cd "$ROOT" && pwd)"

# PARENT_LINKS — "idx_abs_path|child_abs_path" entries, one per file whose
# parent_index resolved (via check (a)'s cascade) to an existing index.
# Consumed by check (b) below, once the per-file pass has finished — bash
# 3.2 has no associative arrays, so this is a flat pair list rather than a
# idx -> [children] map, grouped back out by a sort -u over the idx column.
PARENT_LINKS=()

for file in ${FILES[@]+"${FILES[@]}"}; do
    rel="${file#$ROOT/}"
    base_dir="$(dirname "$file")"

    # (c) kind: vocabulary — opt-in, only fires when kind: is actually set.
    kind_val="$(fm_field "$file" kind || true)"
    if [[ -n "$kind_val" ]] && ! is_valid_kind "$kind_val"; then
        warn "$rel — kind='$kind_val' is not in the known vocabulary (see templates/PHASE_DOC_SCHEMA.md) — add it there deliberately if this project uses it on purpose"
    fi

    # (a) parent_index — document-relative first, ROOT-fallback second,
    # same two-step cascade as phase-docs-lint.sh checks (f)/(g)
    # (scripts/phase-docs-lint.sh:274-297): a document-relative hit stays
    # silent (the documented, preferred form), a ROOT-relative hit is
    # reported as `info` so the fallback usage stays visible rather than
    # unnoticed drift, and neither resolving is an `err`.
    parent_idx="$(fm_field "$file" parent_index || true)"
    idx_resolved=""
    if [[ -n "$parent_idx" ]]; then
        if [[ -f "$base_dir/$parent_idx" ]]; then
            idx_resolved="$base_dir/$parent_idx"
        elif [[ -f "$ROOT/$parent_idx" ]]; then
            idx_resolved="$ROOT/$parent_idx"
            info "$rel — parent_index='$parent_idx' resolved via root fallback ($ROOT/$parent_idx), not found relative to $base_dir"
        else
            err "$rel — parent_index='$parent_idx' points to non-existent file"
        fi
    fi

    if [[ -n "$idx_resolved" ]]; then
        idx_abs="$(cd "$(dirname "$idx_resolved")" && pwd)/$(basename "$idx_resolved")"
        file_abs="$(cd "$base_dir" && pwd)/$(basename "$file")"
        PARENT_LINKS+=("$idx_abs|$file_abs")
    fi

    # (f) derived-count markers — grammar, rules and rationale in the
    # "Check (f)" block above. File-local, so it lives here in the per-file
    # loop rather than in the second pass check (b) needs.
    #
    # `|| [[ -n "$line" ]]` keeps the last line of a file that ends without a
    # newline: `read` returns non-zero there but has still filled $line.
    fence_char=""
    fence_close_re=""
    line_no=0
    while IFS= read -r line || [[ -n "$line" ]]; do
        line_no=$((line_no + 1))

        if [[ -n "$fence_char" ]]; then
            if [[ "$line" =~ $fence_close_re ]]; then
                fence_char=""
                fence_close_re=""
            fi
            continue
        fi
        if [[ "$line" =~ $F_FENCE_OPEN_RE ]]; then
            fence_opener="${BASH_REMATCH[1]}"
            fence_char="${fence_opener:0:1}"
            # A fence closes only on its OWN character, at least as long as
            # the opener — so a ``` inside an open ~~~ fence stays content.
            fence_close_re="^ {0,3}[${fence_char}]{${#fence_opener},}[[:space:]]*$"
            continue
        fi

        # One walk, two products: the prose to count numbers in, and the
        # comment spans to look for markers in (see f_strip_markup).
        f_strip_markup "$line"
        [[ ${#F_SPANS[@]} -gt 0 ]] || continue

        # Pass 1 — marker SHAPE. Every marker span on the line is parsed,
        # not just the first: a marker that is recognised and then silently
        # dropped is exactly the failure this check exists to remove.
        line_markers=()
        for span in ${F_SPANS[@]+"${F_SPANS[@]}"}; do
            [[ "$span" =~ $F_MARKER_PRESENT_RE ]] || continue
            if [[ ! "$span" =~ $F_MARKER_RE ]]; then
                err "$rel:$line_no — malformed derived-count marker (expected '<!-- $MARKER_WORD <count|floor> <glob> -->')"
                continue
            fi
            marker_verb="${BASH_REMATCH[1]}"
            marker_glob="${BASH_REMATCH[2]}"
            case "$marker_verb" in
                count|floor) line_markers+=("$marker_verb $marker_glob") ;;
                *) err "$rel:$line_no — unknown marker verb '$marker_verb' (the vocabulary is: count, floor)" ;;
            esac
        done
        [[ ${#line_markers[@]} -gt 0 ]] || continue

        # Pass 2 — the one-number rule, once per LINE rather than once per
        # marker: the numbers belong to the line, so two markers on it must
        # not produce the same complaint twice.
        f_extract_numbers "$F_STRIPPED"
        if [[ ${#F_NUMBERS[@]} -ne 1 ]]; then
            err "$rel:$line_no — a derived-count marker guards a line carrying ${#F_NUMBERS[@]} numbers; exactly one is required (rewrite the sentence so it states a single number, marker comment excluded)"
            continue
        fi
        declared_value="${F_NUMBERS[0]}"

        # Pass 3 — resolve and compare, per marker.
        for entry in "${line_markers[@]}"; do
            marker_verb="${entry%% *}"
            marker_glob="${entry#* }"

            # Glob resolution — document-relative first, ROOT-fallback
            # second: the same cascade check (a) above already implements for
            # parent_index, reused rather than reinvented, with a fallback hit
            # reported as `info` for the same reason (keep the fallback usage
            # visible instead of letting it become unnoticed drift).
            f_count_glob "$base_dir" "$marker_glob"
            derived_value="$F_GLOB_COUNT"
            if [[ "$derived_value" -eq 0 ]]; then
                f_count_glob "$ROOT" "$marker_glob"
                derived_value="$F_GLOB_COUNT"
                if [[ "$derived_value" -gt 0 ]]; then
                    info "$rel:$line_no — $marker_verb marker '$marker_glob' resolved via root fallback ($ROOT), not relative to $base_dir"
                else
                    err "$rel:$line_no — $marker_verb marker '$marker_glob' matches no files (neither relative to $base_dir nor to $ROOT) — a guard with no scope checks nothing"
                    continue
                fi
            fi

            if [[ "$marker_verb" == "count" ]]; then
                if [[ "$derived_value" -ne "$declared_value" ]]; then
                    err "$rel:$line_no — count marker '$marker_glob' derives $derived_value, but the line states $declared_value"
                fi
            else
                if [[ "$derived_value" -lt "$declared_value" ]]; then
                    err "$rel:$line_no — floor marker '$marker_glob' derives $derived_value, below the $declared_value the line states"
                fi
            fi
        done
    done < "$file"
done

# (b) Reverse direction — the index an existing parent_index resolved to
# must itself link the claiming file back. Grouped by unique index path so
# each index's content is read once, not once per child.
if [[ ${#PARENT_LINKS[@]} -gt 0 ]]; then
    while IFS= read -r idx_path; do
        [[ -z "$idx_path" ]] && continue
        idx_dir="$(dirname "$idx_path")"
        idx_content="$(cat "$idx_path")"
        idx_rel="${idx_path#$ROOT_ABS/}"
        for pair in "${PARENT_LINKS[@]}"; do
            this_idx="${pair%%|*}"
            [[ "$this_idx" == "$idx_path" ]] || continue
            child="${pair#*|}"
            child_rel="${child#$ROOT_ABS/}"
            target="$(rel_path "$idx_dir" "$child")"
            # A here-string, not a pipe: under `set -o pipefail` a
            # `printf | grep -qF` can report the whole pipeline as failed
            # via SIGPIPE precisely when grep exits early on a match while
            # printf is still writing the rest of a large index — turning a
            # real hit into a reported miss (measured 16% false-negative
            # rate at ~37 KB of content). A here-string keeps grep as the
            # only command in the statement, so there is no producer left
            # to receive SIGPIPE. Not switched to `grep -qF ... "$idx_path"`
            # instead, because idx_content is deliberately read ONCE per
            # index above and reused across every child in this inner loop
            # (see the comment on the outer `while` below) — grepping the
            # file directly here would re-read it once per child again. On
            # bash 3.2 (this repo's minimum target) a here-string larger
            # than the pipe buffer is written through a temp file rather
            # than an in-memory fd, which is a performance cost, not a
            # correctness one — real Manual/-sized index files are nowhere
            # near where that would matter.
            if ! grep -qF "]($target)" <<< "$idx_content"; then
                warn "$idx_rel — does not link back to $child_rel, which names it as parent_index (expected a link to '$target')"
            fi
        done
    done < <(printf '%s\n' "${PARENT_LINKS[@]}" | cut -d'|' -f1 | sort -u)
fi

# Report output
NOW="$(date '+%d.%m.%Y %H:%M')"
echo "# Manual Lint Report"
echo
echo "**Root:** $ROOT"
echo "**Checks:** (a) parent_index resolves (document-relative first, root-fallback second) · (b) the resolved index links the claiming file back · (c) kind: is in the known vocabulary (warning if not) · (f) a marked number agrees with the value derived from its glob"
echo "**Run:** $NOW"
echo "**Files scanned:** $FILES_TOTAL"
echo

echo "## Errors (${#errors[@]})"
echo
if [[ ${#errors[@]} -eq 0 ]]; then echo "_none_"; fi
for e in "${errors[@]:-}"; do [[ -n "$e" ]] && echo "- $e"; done
echo

echo "## Warnings (${#warnings[@]})"
echo
if [[ ${#warnings[@]} -eq 0 ]]; then echo "_none_"; fi
for w in "${warnings[@]:-}"; do [[ -n "$w" ]] && echo "- $w"; done
echo

echo "## Info (${#infos[@]})"
echo
if [[ ${#infos[@]} -eq 0 ]]; then echo "_none_"; fi
for i in "${infos[@]:-}"; do [[ -n "$i" ]] && echo "- $i"; done
echo

echo "---"
echo
echo "**Summary:** ${#errors[@]} errors, ${#warnings[@]} warnings, ${#infos[@]} info."

if (( ${#errors[@]} > 0 )); then
    echo "**Exit:** 2"
    exit 2
elif (( ${#warnings[@]} > 0 )); then
    echo "**Exit:** 1"
    exit 1
fi
echo "**Exit:** 0"
exit 0
