#!/usr/bin/env bash
# migrate-review-headers.sh — Backfill `kind: review` + `sprint` (plus, since
# the 22.08.2026 correction below, the commit-anchor family) onto holistic
# sprint-review reports that predate WI-0072's header schema
# (commands/p5-review-sprint.md, templates/REVIEW_REPORT_TEMPLATE.md).
#
# Scope: docs/reviews/SPRINT-<N>-review.md ONLY — the exact filename shape
# the holistic sprint review (`/p5-review-sprint`) writes. Suffix variants
# (SPRINT-<N>-review-code.md, SPRINT-<N>-review-pentest-kal155.md, …) carry
# the same sprint number but are per-scope reviews, not the holistic sprint
# review — stamping `kind: review` on them would misclassify the genre, so
# they are left untouched. Per-story protocols (docs/reviews/sprint-NN/*)
# already have their own `kind: story-review` convention and are a
# different filename shape entirely; they never match. A pre-existing
# `kind:` value that is neither `review` nor the sprint number's match
# state (e.g. a project's own pre-WI-0072 `kind: sprint-review`) is
# overwritten to `review` once the file becomes complete (see below) — the
# filename pattern is the entire genre classification, not whatever ad-hoc
# value a project invented before this schema existed.
#
# WI-0072 required exactly five fields once a document opts into the
# genre: sprint, base_commit (or reviewed_base — phase-docs-lint.sh
# correction, 22.08.2026), reviewed_head, reviewer, last_updated. The
# original version of this script never wrote base_commit, reviewed_head or
# reviewed_base under any circumstance — that blanket rule conflated two
# different things and is corrected here (22.08.2026 correction):
#
#   (1) RECONSTRUCTING a value that is genuinely missing — inferring what
#       the historical HEAD probably was, scraping something SHA-shaped out
#       of an unrelated body line — stays permanently forbidden. `/gate-p5`
#       treats a present `reviewed_head` as ground truth for staleness
#       detection (commands/gate-p5.md); a wrong guess there lets a stale
#       review pass as current, strictly worse than the avoidable opus
#       re-run a MISSING field costs.
#
#   (2) MOVING a value the author already wrote is not a guess. When the
#       body contains a line that is, at the very start of the line,
#       exactly `<key>: <value>` for one of the three known anchor keys
#       (base_commit, reviewed_head, reviewed_base), that value is hoisted
#       into frontmatter — narrowly: only those three keys, only an exact
#       line match, only when frontmatter does not already carry the same
#       key. The BODY LINE ITSELF IS NEVER REMOVED — deleting it would be
#       an edit to a fellow reviewer's prose this script has no business
#       making; leaving it costs nothing, since no machine reads the body.
#       If frontmatter already has the key AND the body line disagrees,
#       nothing is touched and it is reported — the same pattern as the
#       pre-existing sprint-conflict check below.
#
# `kind: review` (and `sprint`) are only ever written once ALL FIVE
# required fields are present, counting both what the file already had in
# frontmatter and what this run's own hoist step just moved there (WI-0072,
# Korrektur 3). A document that would still fail phase-docs-lint.sh's
# required-fields check immediately after being marked is not migrated —
# stamping the genre onto it would turn a clean lint run into a
# permanently red one with no path back, which is strictly worse than
# leaving the document unmigrated and reporting exactly what is missing.
# `reviewer` and `last_updated` are NEVER hoisted or invented under any
# circumstance — mtime is not usable for `last_updated` (several real files
# share one mtime from a later bulk checkout, unrelated to any of their own
# edit dates) and no known-key body convention exists for either, so an
# absent field always stays absent until a human supplies it.
#
# A file whose OWN frontmatter already carries a `sprint:` that disagrees
# with the filename-derived number is a genuine ambiguity the script does
# not resolve by guessing — it warns and leaves that one file entirely
# untouched (checked BEFORE the hoist step, so it applies regardless of
# what hoisting would otherwise find).
#
# Usage:
#   bash ~/.claude/scripts/migrate-review-headers.sh [projectdir] [--dry-run] [--scope <glob>]
#
#   projectdir  defaults to $(pwd)
#   --dry-run   list candidates + planned writes without touching any file
#   --scope     glob relative to docs/reviews/ (e.g. "SPRINT-2*-review.md")
#               restricts the file set; default is every *.md under
#               docs/reviews/ (recursive — the filename regex is the real
#               filter, not directory depth, so this is safe against
#               per-story sub-directories too). NOTE: the glob is matched
#               via `find -path "$REVIEWS_DIR/$SCOPE"`, an EXACT match
#               against the full relative path — a bare filename like
#               "SPRINT-5-review.md" only matches a file directly under
#               docs/reviews/, never a nested copy (e.g. docs/reviews/
#               sprint-05/SPRINT-5-review.md); it reports zero matches,
#               silently, not an error. Prefix with `*/` (e.g.
#               "*/SPRINT-5-review.md") to reach into subdirectories too.
#
# Exit codes: 0 clean, 1 warnings (sprint conflict, an anchor-field
# body/frontmatter conflict, or a document left incomplete because required
# fields are still missing after the hoist attempt), 2 errors (bad args).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/frontmatter.sh
source "$SCRIPT_DIR/lib/frontmatter.sh"

PROJECT_DIR=""
DRY_RUN=false
SCOPE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --scope)
            [[ -n "${2:-}" ]] || { echo "--scope needs a glob" >&2; exit 2; }
            SCOPE="$2"
            shift 2
            ;;
        --scope=*)
            SCOPE="${1#--scope=}"
            [[ -n "$SCOPE" ]] || { echo "--scope needs a glob" >&2; exit 2; }
            shift
            ;;
        --)
            shift
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
        *)
            if [[ -z "$PROJECT_DIR" ]]; then
                PROJECT_DIR="$1"
            else
                echo "migrate-review-headers: unknown argument '$1'" >&2
                exit 2
            fi
            shift
            ;;
    esac
done

PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
REVIEWS_DIR="$PROJECT_DIR/docs/reviews"

if [[ ! -d "$REVIEWS_DIR" ]]; then
    echo "migrate-review-headers: no docs/reviews/ found under $PROJECT_DIR — nothing to migrate."
    exit 0
fi

# The three known anchor keys this script will hoist a bare body line for —
# see the header comment's point (2). Any other body key, however
# SHA-shaped its value, is never touched.
ANCHOR_KEYS="base_commit reviewed_head reviewed_base"

# _ensure_frontmatter_block — prepends an empty `---`/`---` block when the
# file has none. fm_set/fm_set_many both refuse to write into a file
# without one (by design, so they never silently invent a frontmatter
# convention) — this is the one narrow place this script must do that
# itself before delegating. Body content is appended after the block via
# `cat`, byte-for-byte, no matter what it happens to contain (including a
# bare `key: value` line that looks like frontmatter — that line stays
# body text, untouched, one line lower than before). Mode is preserved the
# same way fm_set/fm_set_many preserve it (WI-0021: mktemp defaults to
# 0600, and a same-filesystem `mv` carries the SOURCE's permissions
# forward) — reusing the library's own helper rather than re-deriving the
# same fix here.
#
# Both the write into the temp file and the final `mv` are checked
# (22.08.2026 correction, Befund 2+3 in review) — mirroring fm_set's own
# two guards (scripts/lib/frontmatter.sh) rather than re-deriving a
# different convention here. A failed WRITE leaves an incomplete/corrupt
# temp file, which is of no use to anyone, so it is removed (same as
# fm_set's own write-failure branch). A failed MV, by contrast, leaves a
# temp file whose CONTENT is complete and correct — only the rename step
# itself failed (permissions race, immutable flag) — so it is left in
# place on purpose and its path is named in the error, the one piece of
# information a human needs to find and manually apply it. An unguarded
# `mv` failure here was previously indistinguishable from `set -e` simply
# aborting the script — this makes the abort explain itself.
_ensure_frontmatter_block() {
    local file="$1"
    fm_has "$file" && return 0
    local tmp
    tmp="$(mktemp "${file}.XXXXXX")" || return 1
    # Piped through an external `cat` as the final writer, deliberately NOT
    # `{ printf ...; cat "$file"; } > "$tmp"` directly — reproduced
    # directly against bash 3.2 (this repo's target platform, see the
    # header comment): a redirection OPEN failure attached to a `{ }`
    # GROUP command's own trailing redirect is not reflected in that
    # compound command's exit status in this bash version — `if ! { ...; }
    # > "$tmp"` silently took the success branch even though bash printed
    # "Operation not permitted" to stderr for the very same failure.
    # Routing the identical failure through an EXTERNAL command's own
    # redirect (here, the final `cat`) is what fm_set/fm_set_many already
    # do (their write is `awk ... > "$tmp"`) and IS caught correctly —
    # `pipefail` (already `set` file-wide) makes the whole pipeline's exit
    # status the write failure's, not the first stage's success.
    if ! { printf -- '---\n---\n'; cat "$file"; } | cat > "$tmp"; then
        # `|| true` (WI-0072 correction, Befund 2 in review): a corrupt
        # temp file left behind by a plain full-disk/quota failure is the
        # common case `rm -f` handles fine, but a temp file that is ITSELF
        # unremovable (permissions race, immutable flag) must not swallow
        # the diagnostic below — under `set -e`, an unguarded `rm -f`
        # failure here would abort the function before this message ever
        # printed, reproduced directly.
        rm -f "$tmp" 2>/dev/null || true
        echo "_ensure_frontmatter_block: failed to write $tmp" >&2
        return 1
    fi
    _fm_preserve_mode "$file" "$tmp"
    if ! mv "$tmp" "$file"; then
        echo "_ensure_frontmatter_block: failed to move $tmp into place for $file — left behind for inspection" >&2
        return 1
    fi
}

# _body_text <file> — everything AFTER the frontmatter's closing `---`, or
# the ENTIRE file when it has no frontmatter block yet (there is no
# separate "body" region to carve out in that case — the whole file is
# body). Deliberately does not go through _ensure_frontmatter_block first:
# candidate detection must work identically whether or not a block will end
# up being created, so dry-run sees the exact same hoist candidates a real
# run would act on.
#
# ALSO drops every line that falls inside a fenced code block (``` or
# ~~~, optionally indented up to 3 spaces per CommonMark — the fence
# OPENER and CLOSER lines themselves are dropped too, not just their
# content), in BOTH branches — a fenced example is a fenced example
# whether or not the file happens to have a frontmatter block yet (the
# real consumer-a SPRINT-01 shape that motivated the hoist feature
# in the first place has no frontmatter block AT ALL). One shared awk
# pass handles both cases via the ENVIRON-supplied has_fm flag, rather
# than two separate invocations piped together — same invocation COUNT
# as before this correction (still exactly one), not a second one
# test_external_tool_exit_status.py's regression pin would need to
# additionally account for. Mirrors the fence state machine
# memory-lint.sh already carries for the identical problem (WI-0032/
# WI-0045 there) — same delimiter-type/delimiter-length/nested-fence/
# unclosed-fence handling, reduced to what this script needs (no
# link-checking, just "is this line inside a fence or not").
#
# WHY the fence tracking exists (22.08.2026 correction, Befund 1 in
# review): a review report that documents WI-0072's own header schema —
# commands/p5-review-sprint.md is itself an example — routinely contains
# a fenced block showing what frontmatter LOOKS like, e.g. a
# `reviewed_head: <40 example hex chars>` line inside a ```yaml fence.
# Without fence-tracking, _hoist_candidate's line-start anchor
# (`^${key}:`) cannot tell that illustrative line apart from a genuine,
# author-written value — and `reviewed_head` is exactly the field
# `/gate-p5` trusts as ground truth for staleness detection, so a
# wrongly hoisted example value is strictly worse than the missing field
# the "never reconstruct" rule already guards against elsewhere.
#
# A fence only closes with its OWN delimiter character, at least as long
# as the opener — fence_char/fence_len carry that across lines, so a
# `~~~` inside an open backtick fence (or a shorter run of backticks
# inside a longer one) stays content, never a close. An unclosed fence
# swallows the rest of the stream — correct CommonMark behaviour, and the
# safe default here too: nothing after an unclosed opener is ever offered
# to _hoist_candidate.
_body_text() {
    local file="$1"
    local has_fm=0
    fm_has "$file" && has_fm=1
    BODY_TEXT_HAS_FM="$has_fm" awk '
        BEGIN {
            has_fm = ENVIRON["BODY_TEXT_HAS_FM"] + 0
            # No frontmatter block at all -- the whole file is already
            # "body" from line 1, so c starts where the frontmatter branch
            # only REACHES after both `---` markers.
            c = (has_fm ? 0 : 2)
        }
        has_fm && NR==1 && $0=="---" { c=1; next }
        has_fm && c==1 && $0=="---" { c=2; next }
        c==2 {
            if (in_fence) {
                if (match($0, "^[ ]{0,3}" fence_char "{" fence_len ",}[ \t]*$")) {
                    in_fence = 0
                    fence_char = ""
                    fence_len = 0
                }
                next
            }
            if (match($0, /^[ ]{0,3}(```+|~~~+)/)) {
                opener = substr($0, RSTART, RLENGTH)
                sub(/^[ ]{0,3}/, "", opener)
                fence_char = substr(opener, 1, 1)
                fence_len = length(opener)
                in_fence = 1
                next
            }
            print
        }
    ' "$file"  # exit-status: exempt set-e-sufficient
}

# _hoist_candidate <file> <key> — the value of a bare `<key>: <value>` line
# in the body, matched ONLY at the very start of a line (no indentation, no
# partial match against a longer key like reviewed_head_checkpoint_2). Empty
# when no such line exists. First match wins if more than one line happens
# to repeat the key.
_hoist_candidate() {
    local file="$1" key="$2"
    _body_text "$file" | sed -nE "s/^${key}:[[:space:]]*(.*[^[:space:]])[[:space:]]*\$/\1/p" \
        | head -n1  # exit-status: exempt set-e-sufficient
}

# _join_comma <arg>... — joins its arguments with ", ", printing nothing
# for zero arguments. Deliberately NOT `${arr[*]}`/`"${arr[@]}"` on a
# possibly-empty array: under `set -u` in bash 3.2 (macOS default `/bin/
# bash`), expanding either form against an EMPTY array is an unbound-
# variable error, not an empty string — reproduced directly. `"$@"` inside
# a function has no such pitfall even when the caller passes zero
# arguments, so callers pass a possibly-empty array via the established
# `${arr[@]+"${arr[@]}"}` guard (already used elsewhere in this repo's
# scripts, e.g. phase-docs-lint.sh's own file-collection loop) rather than
# expanding it directly.
_join_comma() {
    local out="" first=true a
    for a in "$@"; do
        if $first; then out="$a"; first=false; else out="$out, $a"; fi
    done
    printf '%s' "$out"
}

MIGRATED=0
SKIPPED_PATTERN=0
SKIPPED_ALREADY=0
WARNINGS=0
ANCHOR_CONFLICTS=0
INCOMPLETE=0
MALFORMED_ANCHORS=0

if [[ -n "$SCOPE" ]]; then
    FILE_LIST=$(find "$REVIEWS_DIR" -path "$REVIEWS_DIR/$SCOPE" -name '*.md' -type f 2>/dev/null || true)
else
    FILE_LIST=$(find "$REVIEWS_DIR" -name '*.md' -type f 2>/dev/null || true)
fi

while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    [[ -f "$file" ]] || continue
    bn="$(basename "$file")"
    rel="${file#$PROJECT_DIR/}"

    # Filename pattern is the ENTIRE classification: exactly
    # `SPRINT-<digits>-review.md`, case-sensitive. Everything else in
    # docs/reviews/ — suffix variants, per-story protocols, KONVENTION.md —
    # is a different genre and stays untouched.
    if ! [[ "$bn" =~ ^SPRINT-[0-9]+-review\.md$ ]]; then
        SKIPPED_PATTERN=$((SKIPPED_PATTERN + 1))
        continue
    fi

    sprint_num_raw="$(printf '%s' "$bn" | sed -E 's/^SPRINT-([0-9]+)-review\.md$/\1/')"  # exit-status: exempt set-e-sufficient
    # Normalized via base-10 arithmetic evaluation, NOT the raw filename
    # digits: the real consumer-a corpus zero-pads (SPRINT-03-...)
    # while its own frontmatter already carries the unpadded form
    # (sprint: 3) -- comparing/writing the padded string would both create
    # a false sprint-conflict warning and write a value the project's own
    # convention never used. `10#` forces base 10 explicitly: bash treats
    # a bare leading-zero literal as OCTAL, which would corrupt "08"/"09"
    # (not valid octal digits) rather than merely mis-format them.
    sprint_num=$((10#$sprint_num_raw))

    existing_kind=""
    existing_sprint=""
    if fm_has "$file"; then
        existing_kind="$(fm_field "$file" kind || true)"
        existing_sprint="$(fm_field "$file" sprint || true)"
    fi

    if [[ "$existing_kind" == "review" && "$existing_sprint" == "$sprint_num" ]]; then
        if $DRY_RUN; then
            echo "  [dry-run] already migrated: $rel (kind: review, sprint: $sprint_num)"
        fi
        SKIPPED_ALREADY=$((SKIPPED_ALREADY + 1))
        continue
    fi

    # A pre-existing sprint: that disagrees with the filename is an
    # ambiguity, not a bug in one particular source — leave the file alone
    # rather than pick a side. Checked before the hoist step: an ambiguous
    # sprint number makes the whole file untrustworthy to touch.
    if [[ -n "$existing_sprint" && "$existing_sprint" != "$sprint_num" ]]; then
        echo "  WARNING: $rel — frontmatter sprint='$existing_sprint' conflicts with filename-derived sprint='$sprint_num'; left untouched" >&2
        WARNINGS=$((WARNINGS + 1))
        continue
    fi

    # --- Hoist step (Korrektur 2): move an already-written anchor value
    # from a bare body line into frontmatter, narrowly. ---
    hoist_keys=()
    hoist_vals=()
    for key in $ANCHOR_KEYS; do
        existing_val=""
        if fm_has "$file"; then
            existing_val="$(fm_field "$file" "$key" || true)"
        fi
        candidate_val="$(_hoist_candidate "$file" "$key")"

        # A hoist candidate must have the SHAPE of a commit SHA —
        # `^[0-9a-fA-F]{7,40}$`, the same form phase-docs-lint.sh already
        # enforces for these exact fields (22.08.2026 correction, Befund 1
        # point 2 in review) — the second of two defence lines against
        # wrongly hoisting an illustrative value: fence-tracking in
        # _body_text catches an example sitting inside a fenced code
        # block, this catches anything that slips past a fence gap (a
        # placeholder, a prose sentence that happens to start with the
        # key name, an indented example — 4-space indentation already
        # never matches the line-start anchor, but this is the backstop,
        # not a duplicate of that). A candidate failing the shape check is
        # reported and treated as absent, never silently dropped and never
        # hoisted — same "report exactly what happened" pattern as every
        # other warning branch below.
        if [[ -n "$candidate_val" ]] && ! [[ "$candidate_val" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
            echo "  WARNING: $rel — body $key='$candidate_val' is not a commit-SHA-shaped value (7-40 hex chars); not hoisted" >&2
            MALFORMED_ANCHORS=$((MALFORMED_ANCHORS + 1))
            candidate_val=""
        fi

        if [[ -n "$existing_val" ]]; then
            # Frontmatter already carries this key — never overwritten by a
            # hoist. A body line for the SAME key with a DIFFERENT value is
            # a genuine conflict (the same warn-and-leave-untouched pattern
            # as the sprint conflict above, scoped to this one field rather
            # than the whole file).
            if [[ -n "$candidate_val" && "$candidate_val" != "$existing_val" ]]; then
                echo "  WARNING: $rel — body $key='$candidate_val' conflicts with frontmatter $key='$existing_val'; left untouched" >&2
                ANCHOR_CONFLICTS=$((ANCHOR_CONFLICTS + 1))
            fi
            continue
        fi

        if [[ -n "$candidate_val" ]]; then
            hoist_keys+=("$key")
            hoist_vals+=("$candidate_val")
        fi
    done

    # _effective <key> — the value this file will carry for <key> once the
    # hoist step (if any) has been applied: whatever frontmatter already
    # has, else whatever was just queued for hoisting, else empty.
    _effective() {
        local key="$1" i
        if fm_has "$file"; then
            local v
            v="$(fm_field "$file" "$key" || true)"
            [[ -n "$v" ]] && { printf '%s' "$v"; return; }
        fi
        for i in "${!hoist_keys[@]}"; do
            if [[ "${hoist_keys[$i]}" == "$key" ]]; then
                printf '%s' "${hoist_vals[$i]}"
                return
            fi
        done
    }

    eff_base_commit="$(_effective base_commit)"
    eff_reviewed_base="$(_effective reviewed_base)"
    eff_reviewed_head="$(_effective reviewed_head)"
    eff_reviewer=""
    eff_last_updated=""
    if fm_has "$file"; then
        eff_reviewer="$(fm_field "$file" reviewer || true)"
        eff_last_updated="$(fm_field "$file" last_updated || true)"
    fi

    # --- Completeness gate (Korrektur 3): kind: review is set ONLY when
    # every WI-0072 field will be present after this run. ---
    still_missing=()
    [[ -z "$eff_base_commit" && -z "$eff_reviewed_base" ]] && still_missing+=("base_commit (or reviewed_base)")
    [[ -z "$eff_reviewed_head" ]] && still_missing+=("reviewed_head")
    [[ -z "$eff_reviewer" ]] && still_missing+=("reviewer")
    [[ -z "$eff_last_updated" ]] && still_missing+=("last_updated")

    set_pairs=()
    for i in "${!hoist_keys[@]}"; do
        set_pairs+=("${hoist_keys[$i]}=${hoist_vals[$i]}")
    done

    if [[ ${#still_missing[@]} -eq 0 ]]; then
        set_pairs+=("kind=review" "sprint=$sprint_num")
        hoisted_note=""
        if [[ ${#hoist_keys[@]} -gt 0 ]]; then
            hoisted_note="; hoisted: $(_join_comma "${hoist_keys[@]}")"
        fi
        if $DRY_RUN; then
            echo "  [dry-run] would set: $rel — kind: review, sprint: $sprint_num${hoisted_note}"
            MIGRATED=$((MIGRATED + 1))
            continue
        fi
        _ensure_frontmatter_block "$file"
        fm_set_many "$file" "${set_pairs[@]}"
        echo "  migrated: $rel (kind: review, sprint: $sprint_num${hoisted_note})"
        MIGRATED=$((MIGRATED + 1))
        continue
    fi

    # Still incomplete after the hoist attempt — kind: review is NOT set.
    # Stamping a genre whose required fields nobody can currently supply
    # would turn a clean phase-docs-lint.sh run into a permanently red one
    # with no path back, strictly worse than leaving the document
    # unmigrated and naming exactly what is missing.
    missing_note="$(_join_comma "${still_missing[@]}")"
    if [[ ${#hoist_keys[@]} -gt 0 ]]; then
        hoisted_note="$(_join_comma "${hoist_keys[@]}")"
        if $DRY_RUN; then
            echo "  [dry-run] would hoist: $rel — ${hoisted_note} (kind: review NOT set — still missing: ${missing_note})"
        else
            _ensure_frontmatter_block "$file"
            fm_set_many "$file" "${set_pairs[@]}"
            echo "  hoisted: $rel — ${hoisted_note} (kind: review NOT set — still missing: ${missing_note})"
        fi
    else
        if $DRY_RUN; then
            echo "  [dry-run] incomplete, nothing hoistable: $rel — still missing: ${missing_note} (kind: review NOT set)"
        else
            echo "  incomplete, nothing hoistable: $rel — still missing: ${missing_note} (kind: review NOT set)"
        fi
    fi
    INCOMPLETE=$((INCOMPLETE + 1))
done <<< "$FILE_LIST"

echo
echo "Migrated: $MIGRATED"
echo "Skipped (filename does not match SPRINT-<N>-review.md): $SKIPPED_PATTERN"
echo "Skipped (already migrated): $SKIPPED_ALREADY"
echo "Hoisted but still incomplete (kind: review NOT set): $INCOMPLETE"
echo "Warnings (sprint conflict): $WARNINGS"
echo "Warnings (anchor-field body/frontmatter conflict): $ANCHOR_CONFLICTS"
echo "Warnings (not commit-SHA-shaped, not hoisted): $MALFORMED_ANCHORS"
if $DRY_RUN; then
    echo "(dry-run — no files were written)"
fi

if (( WARNINGS > 0 || ANCHOR_CONFLICTS > 0 || INCOMPLETE > 0 || MALFORMED_ANCHORS > 0 )); then
    exit 1
fi
exit 0
