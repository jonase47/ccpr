#!/usr/bin/env bash
# phase-docs-lint.sh — Read-only validator for docs/<phase>/**
# Schema: ~/.claude/templates/PHASE_DOC_SCHEMA.md
#
# Usage:
#   bash ~/.claude/scripts/phase-docs-lint.sh [<project-dir>] [--scope <glob>]
#
# --scope    Glob relative to docs/ (e.g. "architecture/SECURITY*" or "architecture/**")
#            Default: all phase folders.
#
# Exit-Codes: 0 clean, 1 warnings, 2 errors.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/frontmatter.sh
source "$SCRIPT_DIR/lib/frontmatter.sh"

PROJECT_DIR=""
SCOPE_GLOB=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scope)
            SCOPE_GLOB="$2"
            shift 2
            ;;
        --scope=*)
            SCOPE_GLOB="${1#--scope=}"
            shift
            ;;
        *)
            if [[ -z "$PROJECT_DIR" ]]; then
                PROJECT_DIR="$1"
            else
                echo "phase-docs-lint: unknown argument '$1'" >&2
                exit 2
            fi
            shift
            ;;
    esac
done

PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
DOCS_DIR="$PROJECT_DIR/docs"

# Commit-anchor-family resolvability is only attempted once per run, not
# once per file — computed here, consumed by check (i) inside the loop.
# `-e "$PROJECT_DIR/.git"` deliberately checks the given project dir
# itself, not an upward search (`git rev-parse --is-inside-work-tree`
# would climb past PROJECT_DIR into an unrelated enclosing repo). `-e`,
# not `-d`: in a linked worktree or a submodule checkout, `.git` is a FILE
# (`gitdir: /path/to/real/.git/worktrees/...`), not a directory — `-d`
# silently left GIT_CHECKABLE at 0 there, skipping check (i) with no
# indication.
GIT_CHECKABLE=0
if [[ -e "$PROJECT_DIR/.git" ]] && command -v git >/dev/null 2>&1; then
    GIT_CHECKABLE=1
fi

PHASE_FOLDERS=(discovery concept validation architecture planning quality launch operations reviews)
LIVING_FILES="HANDOVER.md BASELINE.md BACKLOG.md SPRINT.md MEMORY.md instincts.md"
VALID_STATUS="skeleton draft active frozen archived living"
VALID_PHASES="P0 P1 P2 P3 P4 P5 P6 P7 P8"
# VALID_GATE_VERDICTS / VALID_SPRINT_VERDICTS — the two closed vocabularies
# for the declared `gate:` frontmatter field (WI-0129, findings F3/F4;
# templates/PHASE_DOC_SCHEMA.md "Gate verdict" section is the source of
# truth these two strings mirror). A GATE_P*.md answers a phase-gate
# question, SPRINT.md answers a sprint question — the two sets are
# deliberately NOT unified: "done" is a real SPRINT.md value that must be
# rejected on a GATE_P*.md, and "go" the other way round (check (k) below).
VALID_GATE_VERDICTS="pending go conditional_go no_go pivot"
VALID_SPRINT_VERDICTS="pending done conditionally_done not_done"
# PLACEHOLDER_NAMES — the vcs-emptiness-marker convention check (h) treats
# as "reserved, not built" rather than real content (WI-0122). Named list
# (AC4 of that work item), not inlined into the predicate below, so a
# project convention this repo doesn't use is one line to add.
PLACEHOLDER_NAMES=".gitkeep .keep .placeholder"

# doc_profile_for — assigns each file (by its path relative to docs/) to the
# set of checks it must satisfy. bash 3.2 (macOS default) has no associative
# arrays, so this is a case dispatch rather than a lookup table — extend the
# case (not a new array) when another folder needs its own profile.
#
# Profiles:
#   full    — checks (a)-(g), the PHASE_DOC_SCHEMA default.
#   reviews — check (d) (status enum, only when status: is set) plus check
#             (j) (WI-0072's review-specific required fields — sprint,
#             base_commit, reviewed_head, reviewer, last_updated — but ONLY
#             once the document opts into the genre via `kind: review`; a
#             document without that marker, or with a different `kind:`
#             such as `story-review`/`review-convention`, stays silent).
#             Review reports predate PHASE_DOC_SCHEMA and follow their own
#             frontmatter shape; checks (a)-(c)/(e)-(g) stay off for this
#             profile — enforcing them against pre-WI-0072 reports would
#             raise dozens of "required field missing" findings against a
#             schema they were never written for.
doc_profile_for() {
    local rel_to_docs="$1"
    case "$rel_to_docs" in
        reviews/*) echo "reviews" ;;
        *)         echo "full" ;;
    esac
}

errors=()
warnings=()
infos=()
err()  { errors+=("$1"); }
warn() { warnings+=("$1"); }
info() { infos+=("$1"); }

is_living_file() {
    local bn="$1"
    for lf in $LIVING_FILES; do
        [[ "$bn" == "$lf" ]] && return 0
    done
    return 1
}

is_valid_status() {
    local s="$1"
    for v in $VALID_STATUS; do
        [[ "$s" == "$v" ]] && return 0
    done
    return 1
}

is_valid_phase() {
    local p="$1"
    for v in $VALID_PHASES; do
        [[ "$p" == "$v" ]] && return 0
    done
    return 1
}

is_valid_gate_verdict() {
    local g="$1"
    for v in $VALID_GATE_VERDICTS; do
        [[ "$g" == "$v" ]] && return 0
    done
    return 1
}

is_valid_sprint_verdict() {
    local g="$1"
    for v in $VALID_SPRINT_VERDICTS; do
        [[ "$g" == "$v" ]] && return 0
    done
    return 1
}

# is_empty_dir — the question is not "does this directory contain any
# entry" but "does it cover any actual file": a tree consisting solely of
# nested empty subdirectories must still count as empty. `find -type f
# -print -quit` is the portable (bash 3.2 has no bulk-line-into-array
# builtins) single-file-or-nothing probe, at any depth. A directory whose
# only content is a `.gitkeep` therefore counts as non-empty — a file is a
# file, and carving out dotfiles as a special case would be a rule nobody
# decided. That case (holds only a placeholder) is not silently accepted
# either — check (h) reports it with its own, distinct warning via
# is_placeholder_only_dir() below (WI-0122, PO decision: a separate
# message, not a widened predicate here — "reserved, not built" is a
# different statement than "holds nothing").
is_empty_dir() {
    local d="$1"
    [[ -z "$(find "$d" -type f -print -quit 2>/dev/null)" ]]
}

is_placeholder_name() {
    local bn="$1" p
    for p in $PLACEHOLDER_NAMES; do
        [[ "$bn" == "$p" ]] && return 0
    done
    return 1
}

# is_placeholder_only_dir — call only once is_empty_dir has already
# established $d holds at least one real file (at any depth); an empty
# directory is a different, pre-existing case (see above) and must keep
# reporting through that branch, unchanged. Walks every file the directory
# covers: if every one of them is a placeholder name, echoes the basename
# of the first one found (so the caller can name it in the warning) and
# returns success. If any single file is not a placeholder name, returns
# failure with no output — a placeholder alongside real content means the
# directory is not "reserved, not built", it is built, and must stay
# silent (AC3).
# check_gate_verdict — (k) Gate verdict (WI-0129, findings F3/F4): a
# GATE_P*.md must declare a `gate:` field from its own closed vocabulary.
# Extracted into a function (WI-0129 follow-up) so it can be invoked from
# TWO sites in the main loop: its original position after the frontmatter
# checks, AND from inside check (a)'s no-frontmatter branch, right before
# that branch's `continue`. A document with no frontmatter at all has no
# `gate:` field either -- that absence is exactly what this check reports,
# so it must not be skipped just because the frontmatter block itself is
# missing. Matched by basename, not by doc_profile_for's full/reviews
# split, because a gate document's shape has nothing to do with the
# reviews genre. See the call sites below for the no-frontmatter rationale.
check_gate_verdict() {
    local file="$1" rel="$2" bn="$3"
    case "$bn" in
        GATE_P*.md)
            local gate_val
            gate_val="$(fm_field "$file" gate || true)"
            if [[ -z "$gate_val" ]]; then
                err "$rel — required field missing: gate (see PHASE_DOC_SCHEMA.md 'Gate verdict')"
            elif ! is_valid_gate_verdict "$gate_val"; then
                err "$rel — gate='$gate_val' is not in {$VALID_GATE_VERDICTS} (GATE_P*.md vocabulary)"
            fi
            ;;
    esac
}

is_placeholder_only_dir() {
    local d="$1" f bn first=""
    while IFS= read -r f; do
        bn="$(basename "$f")"
        is_placeholder_name "$bn" || return 1
        [[ -z "$first" ]] && first="$bn"
    done < <(find "$d" -type f 2>/dev/null)
    echo "$first"
}

if [[ ! -d "$DOCS_DIR" ]]; then
    echo "phase-docs-lint: no docs/ structure found under $PROJECT_DIR"
    exit 0
fi

# Collect files. FOLDERS_FOUND tracks which of PHASE_FOLDERS actually exist
# under docs/ on the default (no --scope) walk -- consumed by the summary
# line and the empty-scope notice below (WI-0121), so a reader can tell
# "every phase folder was checked and none of them existed" apart from
# "phase folders exist but every document in them is clean". Left empty
# (and unused) on a --scope run, which names its own glob instead.
FILES=()
FOLDERS_FOUND=()
if [[ -n "$SCOPE_GLOB" ]]; then
    while IFS= read -r p; do
        # Bash [[ ... == pattern ]] supports *, ?, [...] (no ** globstar required).
        # $SCOPE_GLOB deliberately UNQUOTED (WI-0129 D1, ShellCheck SC2053):
        # quoting it would turn this into a literal string comparison and
        # break the whole point of --scope accepting a glob.
        # shellcheck disable=SC2053
        if [[ "$p" == $SCOPE_GLOB ]]; then
            FILES+=("$DOCS_DIR/$p")
        fi
    done < <(cd "$DOCS_DIR" && find . -type f -name "*.md" 2>/dev/null | sed 's|^\./||')  # exit-status: exempt proc-subst-unobservable
else
    for folder in "${PHASE_FOLDERS[@]}"; do
        [[ -d "$DOCS_DIR/$folder" ]] || continue
        FOLDERS_FOUND+=("$folder")
        while IFS= read -r line; do
            FILES+=("$line")
        done < <(find "$DOCS_DIR/$folder" -type f -name "*.md")
    done
fi

FILES_TOTAL=${#FILES[@]}

# An empty scope is not a pass (WI-0121) -- the same shape WI-0090 already
# fixed for artifact-gate.sh's deny-list scope. "Files scanned: 0" printed
# next to "0 errors, 0 warnings" is a true sentence that reads as "every
# phase folder was checked and found clean"; on a project with no phase
# folders yet (pre-P3, or Lean-Track) it instead means there was nothing to
# check at all. The exit code stays 0 on purpose -- an empty scope is a
# SUPPORTED configuration here, not an error: PHASE_FOLDERS not existing yet
# under docs/ is the normal, expected state for a project before P3, and the
# Constitution's "installable and runnable on a clean machine" Inviolable is
# what makes that the default rather than a failure (mirrors artifact-gate.sh
# NOT failing an unconfigured deny-list by default). The notice goes to
# stderr -- the channel this script already uses for every other "the run
# could not do its job" line -- so a caller that keeps stdout as its findings
# report cannot lose it by redirecting.
if [[ "$FILES_TOTAL" -eq 0 ]]; then
    if [[ -n "$SCOPE_GLOB" ]]; then
        echo "phase-docs-lint: no files matched --scope '$SCOPE_GLOB' under $DOCS_DIR" >&2
    else
        echo "phase-docs-lint: no phase folders found under $DOCS_DIR (looked for: ${PHASE_FOLDERS[*]})" >&2
    fi
fi

for file in ${FILES[@]+"${FILES[@]}"}; do
    rel="${file#$PROJECT_DIR/}"
    bn="$(basename "$file")"

    # Living files skip — they follow their own header convention. SPRINT.md
    # is the one named exception (PHASE_DOC_SCHEMA.md's "Gate verdict"
    # section, WI-0129): it stays a living file for every other purpose, but
    # check (k) below still runs against it, because /gate-p5 records the
    # sprint's own verdict in SPRINT.md's frontmatter and no other document
    # carries it. Every other living file (HANDOVER.md, BASELINE.md,
    # BACKLOG.md, MEMORY.md, instincts.md) keeps skipping everything,
    # unchanged (see LivingFilesSkipTest).
    #
    # Matched by BASENAME, not by the full path docs/planning/SPRINT.md
    # that GATE_FILE_PATHS names -- deliberate, and the same choice check
    # (k) makes for GATE_P*.md below. A gate document in the wrong folder
    # is exactly the document most likely to be wrong, and demanding the
    # field there costs an author one frontmatter line while never causing
    # a false pass (this lint reports; it does not unblock anything).
    # Measured: one reference project carries docs/planning/GATE_P1.md and
    # docs/planning/GATE_P6.md, neither in its canonical phase folder.
    if is_living_file "$bn"; then
        if [[ "$bn" == "SPRINT.md" ]]; then
            gate_val="$(fm_field "$file" gate || true)"
            if [[ -z "$gate_val" ]]; then
                err "$rel — required field missing: gate (see PHASE_DOC_SCHEMA.md 'Gate verdict')"
            elif ! is_valid_sprint_verdict "$gate_val"; then
                err "$rel — gate='$gate_val' is not in {$VALID_SPRINT_VERDICTS} (SPRINT.md vocabulary)"
            fi
        fi
        continue
    fi

    # Profile is derived from the file's path relative to docs/ — not from
    # which collection path (default PHASE_FOLDERS walk vs. --scope's find)
    # found it, so both routes agree on the same file.
    rel_to_docs="${file#$DOCS_DIR/}"
    profile="$(doc_profile_for "$rel_to_docs")"

    if [[ "$profile" == "full" ]]; then
        # (a) Frontmatter present?
        if ! fm_has "$file"; then
            warn "$rel — no YAML frontmatter (--- block at start). Migration to PHASE_DOC_SCHEMA recommended."
            # check (k) still runs here (WI-0129 follow-up, see
            # check_gate_verdict's own comment): a GATE_P*.md with no
            # frontmatter at all has no `gate:` field, which is the error
            # this check exists to report, not something the migration
            # warning above should stand in for. The warning above stays,
            # unchanged, for every document, gate or not -- this only adds
            # a second, more specific finding on top of it for the gate
            # case.
            check_gate_verdict "$file" "$rel" "$bn"
            continue
        fi

        # (b) Required fields
        missing="$(fm_validate_required "$file" "phase,subskill,status,last_updated" || true)"
        if [[ -n "$missing" ]]; then
            while IFS= read -r m; do
                err "$rel — required field missing: $m"
            done <<< "$missing"
        fi

        # (c) phase enum
        phase_val="$(fm_field "$file" phase || true)"
        if [[ -n "$phase_val" ]] && ! is_valid_phase "$phase_val"; then
            err "$rel — phase='$phase_val' is not in {P0…P8}"
        fi
    elif [[ "$profile" == "reviews" ]]; then
        # (j) Review-specific required fields (WI-0072). Fires ONLY when the
        # document self-identifies as the genre via `kind: review` — every
        # other document under docs/reviews/ (no `kind:` at all, or a
        # different `kind:` such as `story-review`/`review-convention`,
        # KONVENTION.md's per-story template) stays silent. That is what
        # makes backward compatibility structural rather than assumed: not
        # one document in the three CCPR reference projects carries the
        # literal `kind: review` today, so this branch cannot fire against
        # the existing corpus, only against documents future commands (or
        # a migration) opt into the genre for.
        kind_val="$(fm_field "$file" kind || true)"
        if [[ "$kind_val" == "review" ]]; then
            missing="$(fm_validate_required "$file" "sprint,reviewed_head,reviewer,last_updated" || true)"
            if [[ -n "$missing" ]]; then
                while IFS= read -r m; do
                    err "$rel — required field missing: $m"
                done <<< "$missing"
            fi

            # The base-of-reviewed-range field is validated as base_commit
            # OR reviewed_base (WI-0072 correction, 22.08.2026), not
            # base_commit alone -- both are already accepted, equally
            # validated names in the (i) commit-anchor-family check below.
            # The real consumer-a corpus writes reviewed_base for
            # every review it authored under this schema and never
            # base_commit; requiring one specific name would fail a
            # document that carries everything the schema asks for, just
            # under the project's own name for it. Fires once per
            # document, naming both accepted keys, so a reader does not
            # have to guess which one is meant.
            base_commit_val="$(fm_field "$file" base_commit || true)"
            reviewed_base_val="$(fm_field "$file" reviewed_base || true)"
            if [[ -z "$base_commit_val" && -z "$reviewed_base_val" ]]; then
                err "$rel — required field missing: base_commit (or reviewed_base)"
            fi
        fi
    fi

    # (k) Gate verdict (WI-0129, findings F3/F4) — the frontmatter-present
    # path. See check_gate_verdict's own comment above for the full
    # rationale (including why "Go"/"No-Go" prose-scraping was replaced)
    # and for the OTHER call site, inside check (a)'s no-frontmatter
    # branch above, which covers the document that never reaches this line
    # at all because it `continue`d first.
    check_gate_verdict "$file" "$rel" "$bn"

    # (d) status enum — runs in every profile, but only fires when status:
    # is actually set (fm_field returns empty on a file without frontmatter
    # too, so this stays silent there).
    status_val="$(fm_field "$file" status || true)"
    if [[ -n "$status_val" ]] && ! is_valid_status "$status_val"; then
        err "$rel — status='$status_val' is not in {$VALID_STATUS}"
    fi

    if [[ "$profile" == "full" ]]; then
        # (e) last_updated: DD.MM.YYYY, optionally followed by " (note)", AND
        # a real calendar day (WI-0107, ADR-0001 promotion).
        #
        # The optional note is specified in PHASE_DOC_SCHEMA.md and carries WHY
        # the date moved (which round, which item). memory-lint.sh's check (e)
        # enforces the identical pattern for memory files (WI-0106).
        #
        # Until WI-0107 this check was shape-only, and a well-formed-but-
        # impossible value (`32.13.2026`, `99.99.9999`) passed here while
        # memory-lint.sh — which additionally parses the value through
        # `fm_date_to_epoch` — rejected it. Measured 25.08.2026 (not read off
        # the source), and left open deliberately at the time: closing the gap
        # rejects content this script had been accepting, which is a
        # promotion decision, not the pinning of an existing rule. The blast
        # radius was then measured before promoting: no impossible-but-
        # well-formed value exists in any of the four reference stores. Both
        # checks now share ONE implementation — `fm_date_shape_ok` for the
        # pattern and `fm_date_to_epoch` for the parse, both in
        # scripts/lib/frontmatter.sh — rather than two independently
        # hand-typed copies that had never agreed.
        last_updated="$(fm_field "$file" last_updated || true)"
        if [[ -n "$last_updated" ]] \
            && { ! fm_date_shape_ok "$last_updated" || [[ "$(fm_date_to_epoch "$last_updated")" == "0" ]]; }; then
            err "$rel — last_updated='$last_updated' not in format 'DD.MM.YYYY' or 'DD.MM.YYYY (note)'"
        fi

        # (f) related: cross-refs — resolved document-relative first (the
        # documented form: PHASE_DOC_SCHEMA.md says "relative to the file's
        # own directory"). Authors in the field write these entries
        # project-root-relative instead (e.g. `docs/CONSTITUTION.md`), so a
        # miss falls back to $PROJECT_DIR before being declared dead
        # (WI-0071, PO decision 21.08.2026). A root-relative hit is `info`,
        # not silence — accepting two bases without saying so would be
        # exactly the unvalidated drift this lint exists to catch.
        base_dir="$(dirname "$file")"
        while IFS= read -r rel_entry; do
            [[ -z "$rel_entry" ]] && continue
            if [[ -f "$base_dir/$rel_entry" ]]; then
                : # document-relative hit — the documented, silent case
            elif [[ -f "$PROJECT_DIR/$rel_entry" ]]; then
                info "$rel — related:'$rel_entry' resolved via project-root fallback ($PROJECT_DIR/$rel_entry), not found relative to $base_dir"
            else
                err "$rel — related:'$rel_entry' points to non-existent file ($base_dir/$rel_entry)"
            fi
        done < <(fm_list "$file" related)

        # (g) parent_index — same document-relative-first, root-fallback
        # resolution as (f) above, same key/schema statement.
        parent_idx="$(fm_field "$file" parent_index || true)"
        if [[ -n "$parent_idx" ]]; then
            if [[ -f "$base_dir/$parent_idx" ]]; then
                : # document-relative hit — the documented, silent case
            elif [[ -f "$PROJECT_DIR/$parent_idx" ]]; then
                info "$rel — parent_index='$parent_idx' resolved via project-root fallback ($PROJECT_DIR/$parent_idx), not found relative to $base_dir"
            else
                err "$rel — parent_index='$parent_idx' points to non-existent file"
            fi
        fi
    fi

    # (h) covers: code paths this document describes (WI-0020) — resolved
    # *exclusively* against $PROJECT_DIR, no document-relative fallback:
    # these are code paths, not doc cross-refs, so there is no "file's own
    # directory" to fall back from (unlike (f)/(g) above). Runs in every
    # profile — opt-in, only fires when covers: is actually set, so it
    # costs a project nothing until it adopts the field. Measured: covers:
    # appears in zero documents across all three CCPR reference projects.
    #
    # Two distinct degenerate-content warnings, deliberately not merged
    # (WI-0122, PO decision): a genuinely empty directory ("holds nothing")
    # and a directory holding only a vcs placeholder ("holds nothing but a
    # placeholder — reserved, not built") say different things to a reader,
    # even though both were true 0-real-file-content until now indistinct
    # under is_empty_dir's `-type f` probe alone.
    while IFS= read -r covers_entry; do
        [[ -z "$covers_entry" ]] && continue
        covers_path="$PROJECT_DIR/$covers_entry"
        if [[ ! -e "$covers_path" ]]; then
            err "$rel — covers:'$covers_entry' points to non-existent path ($covers_path)"
        elif [[ -d "$covers_path" ]] && is_empty_dir "$covers_path"; then
            warn "$rel — covers:'$covers_entry' is an empty directory ($covers_path) — the list covers nothing"
        elif [[ -d "$covers_path" ]]; then
            # `is_placeholder_only_dir` returns 1 (no output) the moment it
            # meets a real, non-placeholder file -- the ordinary case for
            # any directory actually in use. A bare `var=$(cmd)` takes the
            # substitution's exit status as the assignment's own, so under
            # `set -e` that ordinary case killed the whole script (empty
            # stdout, exit 1) before the report was ever printed -- the
            # first real covers: directory in a run took every document
            # after it down with it. `|| true` makes "not a placeholder-
            # only dir" a normal, silent outcome again, matching the
            # function's own contract (failure = no output; $placeholder_hit
            # stays empty either way, since `echo` never ran on that path).
            placeholder_hit="$(is_placeholder_only_dir "$covers_path")" || true
            if [[ -n "$placeholder_hit" ]]; then
                warn "$rel — covers:'$covers_entry' holds only a placeholder ($placeholder_hit, $covers_path) — reserved, not built"
            fi
        fi
    done < <(fm_list "$file" covers)

    # (i) Commit-anchor family: base_commit (/p4-sprint), reviewed_head
    # (/p5-review-sprint, compared against HEAD by /gate-p5), reviewed_base
    # (field variant) — all optional, all CCPR-generated, none validated
    # before this check. Runs in every profile — opt-in, only fires when
    # one of the three keys is actually set. Form (hex, 7-40 chars) is an
    # err; unresolvability against the project's git history is a warn —
    # a shallow clone, rewritten history, or a foreign-repo SHA are all
    # legitimate reasons not to hard-fail a lint run on it. If the project
    # isn't a git repository (or git isn't on PATH), the resolvability
    # half is skipped entirely and silently; the form check still runs.
    for anchor_key in base_commit reviewed_head reviewed_base; do
        anchor_val="$(fm_field "$file" "$anchor_key" || true)"
        [[ -z "$anchor_val" ]] && continue
        if ! [[ "$anchor_val" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
            err "$rel — $anchor_key='$anchor_val' is not a valid commit SHA (7-40 hex chars)"
            continue
        fi
        if [[ "$GIT_CHECKABLE" == "1" ]] \
            && ! git -C "$PROJECT_DIR" rev-parse --verify -q "${anchor_val}^{commit}" >/dev/null 2>&1; then
            warn "$rel — $anchor_key='$anchor_val' does not resolve to a commit in this repository"
        fi
    done
done

# Report output
NOW="$(date '+%d.%m.%Y %H:%M')"
SCOPE_DESC="${SCOPE_GLOB:-all phase folders}"
echo "# Phase Docs Lint Report"
echo
echo "**Scope:** $DOCS_DIR/ ($SCOPE_DESC)"
# Names the scope of FOLDERS as well as the scope of files, same reasoning
# as artifact-gate.sh's deny-list line: "Files scanned: 0" alone does not
# say whether that is because every phase folder was empty or because none
# of them exist. A --scope run already states its own glob on the line
# above, so this companion line is default-scope only.
if [[ -z "$SCOPE_GLOB" ]]; then
    if [[ ${#FOLDERS_FOUND[@]} -gt 0 ]]; then
        echo "**Phase folders found:** ${FOLDERS_FOUND[*]}"
    else
        echo "**Phase folders found:** none (looked for: ${PHASE_FOLDERS[*]})"
    fi
fi
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
