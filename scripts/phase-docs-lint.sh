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

PHASE_FOLDERS=(discovery concept validation architecture planning quality launch operations reviews)
LIVING_FILES="HANDOVER.md BASELINE.md BACKLOG.md SPRINT.md MEMORY.md instincts.md"
VALID_STATUS="skeleton draft active frozen archived living"
VALID_PHASES="P0 P1 P2 P3 P4 P5 P6 P7 P8"

# doc_profile_for — assigns each file (by its path relative to docs/) to the
# set of checks it must satisfy. bash 3.2 (macOS default) has no associative
# arrays, so this is a case dispatch rather than a lookup table — extend the
# case (not a new array) when another folder needs its own profile, e.g.
# WI-0072's planned dedicated review-report schema.
#
# Profiles:
#   full    — checks (a)-(g), the PHASE_DOC_SCHEMA default.
#   reviews — only check (d) (status enum), and only when status: is set.
#             Review reports predate PHASE_DOC_SCHEMA and follow their own
#             frontmatter shape (kind, sprint, base_commit, reviewer,
#             methodology — WI-0072). Enforcing (a)-(c)/(e)-(g) against them
#             today raises dozens of "required field missing" findings
#             against a schema they were never written for.
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

if [[ ! -d "$DOCS_DIR" ]]; then
    echo "phase-docs-lint: no docs/ structure found under $PROJECT_DIR"
    exit 0
fi

# Collect files
FILES=()
if [[ -n "$SCOPE_GLOB" ]]; then
    while IFS= read -r p; do
        # Bash [[ ... == pattern ]] supports *, ?, [...] (no ** globstar required)
        if [[ "$p" == $SCOPE_GLOB ]]; then
            FILES+=("$DOCS_DIR/$p")
        fi
    done < <(cd "$DOCS_DIR" && find . -type f -name "*.md" 2>/dev/null | sed 's|^\./||')  # exit-status: exempt proc-subst-unobservable
else
    for folder in "${PHASE_FOLDERS[@]}"; do
        [[ -d "$DOCS_DIR/$folder" ]] || continue
        while IFS= read -r line; do
            FILES+=("$line")
        done < <(find "$DOCS_DIR/$folder" -type f -name "*.md")
    done
fi

FILES_TOTAL=${#FILES[@]}

for file in ${FILES[@]+"${FILES[@]}"}; do
    rel="${file#$PROJECT_DIR/}"
    bn="$(basename "$file")"

    # Living files skip — they follow their own header convention
    if is_living_file "$bn"; then
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
    fi

    # (d) status enum — runs in every profile, but only fires when status:
    # is actually set (fm_field returns empty on a file without frontmatter
    # too, so this stays silent there).
    status_val="$(fm_field "$file" status || true)"
    if [[ -n "$status_val" ]] && ! is_valid_status "$status_val"; then
        err "$rel — status='$status_val' is not in {$VALID_STATUS}"
    fi

    if [[ "$profile" == "full" ]]; then
        # (e) last_updated: DD.MM.YYYY, optionally followed by " (note)"
        last_updated="$(fm_field "$file" last_updated || true)"
        if [[ -n "$last_updated" ]] && ! [[ "$last_updated" =~ ^[0-9]{2}\.[0-9]{2}\.[0-9]{4}([[:space:]]+\(.*\))?$ ]]; then
            err "$rel — last_updated='$last_updated' not in format 'DD.MM.YYYY' or 'DD.MM.YYYY (note)'"
        fi

        # (f) related: cross-refs
        base_dir="$(dirname "$file")"
        while IFS= read -r rel_entry; do
            [[ -z "$rel_entry" ]] && continue
            if [[ ! -f "$base_dir/$rel_entry" ]]; then
                err "$rel — related:'$rel_entry' points to non-existent file ($base_dir/$rel_entry)"
            fi
        done < <(fm_list "$file" related)

        # (g) parent_index — if set, the file must exist
        parent_idx="$(fm_field "$file" parent_index || true)"
        if [[ -n "$parent_idx" ]]; then
            if [[ ! -f "$base_dir/$parent_idx" ]]; then
                err "$rel — parent_index='$parent_idx' points to non-existent file"
            fi
        fi
    fi
done

# Report output
NOW="$(date '+%d.%m.%Y %H:%M')"
SCOPE_DESC="${SCOPE_GLOB:-all phase folders}"
echo "# Phase Docs Lint Report"
echo
echo "**Scope:** $DOCS_DIR/ ($SCOPE_DESC)"
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
