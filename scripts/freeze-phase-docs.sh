#!/usr/bin/env bash
# freeze-phase-docs.sh — Set `status: frozen` on phase detail files after a Gate Go decision.
#
# Reads the frontmatter of each candidate file (via lib/frontmatter.sh).
# Sets `status: frozen` only when current status is `draft` or `active`.
# Leaves {skeleton, living, archived, frozen} untouched.
# P5 (iterative sprint phase) and P8 (operational phase) are no-ops by design.
#
# Usage:
#   bash ~/.claude/scripts/freeze-phase-docs.sh <phase> [projectdir] [--dry-run] [--scope <glob>]
#
#   phase       P0..P8 (case-insensitive). P5/P8 = no-op.
#   projectdir  defaults to $(pwd)
#   --dry-run   list candidates without writing
#   --scope     glob relative to docs/ (e.g. "quality/AUDIT*") — restricts file set to a sub-tree.
#               Without --scope: phase's standard folder is used.
#
# Exit-Codes: 0 clean, 1 warnings (missing/unknown status), 2 errors (bad args).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/frontmatter.sh
source "$SCRIPT_DIR/lib/frontmatter.sh"

if [[ $# -lt 1 ]]; then
    echo "Usage: $(basename "$0") <phase> [projectdir] [--dry-run] [--scope <glob>]" >&2
    exit 2
fi

PHASE="$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]')"
shift

PROJECT_DIR="$(pwd)"
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
        --)
            shift
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
        *)
            PROJECT_DIR="$1"
            shift
            ;;
    esac
done

# Phase → folder mapping (matches gate skill conventions)
case "$PHASE" in
    P0) FOLDER="discovery" ;;
    P1) FOLDER="concept" ;;
    P2) FOLDER="validation" ;;
    P3) FOLDER="architecture" ;;
    P4) FOLDER="planning" ;;
    P5)
        echo "P5 is the iterative sprint phase — sprint docs are 'living' by design. No freeze action."
        exit 0
        ;;
    P6) FOLDER="quality" ;;
    P7) FOLDER="launch" ;;
    P8)
        echo "P8 is the operational phase — no phase-wide freeze."
        exit 0
        ;;
    *)
        echo "Unknown phase: $PHASE (expected P0..P8)" >&2
        exit 2
        ;;
esac

cd "$PROJECT_DIR" 2>/dev/null || { echo "Project dir not accessible: $PROJECT_DIR" >&2; exit 2; }

# Resolve search root + optional path pattern
if [[ -n "$SCOPE" ]]; then
    SEARCH_ROOT="docs"
    SCOPE_PATH="docs/$SCOPE"
else
    SEARCH_ROOT="docs/$FOLDER"
    SCOPE_PATH=""
    # Quick exit when the default folder doesn't exist yet
    if [[ ! -d "$SEARCH_ROOT" ]]; then
        echo "Phase folder $SEARCH_ROOT not found in $PROJECT_DIR — nothing to freeze."
        exit 0
    fi
fi

CHANGED=0
SKIPPED=0
SKIPPED_INDEX=0
WARNINGS=0

# Collect candidate files via find (Bash-3.2 compatible, no globstar).
if [[ -n "$SCOPE_PATH" ]]; then
    FILE_LIST=$(find "$SEARCH_ROOT" -path "$SCOPE_PATH" -name '*.md' -type f 2>/dev/null || true)
else
    FILE_LIST=$(find "$SEARCH_ROOT" -name '*.md' -type f 2>/dev/null || true)
fi

while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    [[ -f "$file" ]] || continue

    # Files without frontmatter are not phase docs — skip silently.
    if ! fm_has "$file" 2>/dev/null; then
        continue
    fi

    # Only act on files whose `phase:` matches the requested phase.
    doc_phase="$(fm_field "$file" phase 2>/dev/null || true)"
    if [[ "$doc_phase" != "$PHASE" ]]; then
        continue
    fi

    # Index-File-Skip: Phase-Indices and Sub-Indices are living overviews even
    # after the phase gate passes (cross-phase updates land on the index).
    # Detection identical to scripts/local-llm/summarize.sh: filename convention
    # OR `## Detail Files` / `## Detail-Files` section.
    basename_noext="$(basename "$file" .md)"
    case "$basename_noext" in
        CONCEPT|ARCHITECTURE|PROJECT_PLAN|QA|LAUNCH|DISCOVERY|VALIDATION|SPRINT|\
        SECURITY|A11Y|AUDIT|PENTEST|FUNCTIONAL|EXPLORATORY|RELEASE|OPERATIONS|\
        BUGFIX|INFRASTRUCTURE)
            echo "  skipped: $file (phase/sub-index — kept active for cross-phase updates)"
            SKIPPED_INDEX=$((SKIPPED_INDEX + 1))
            continue
            ;;
    esac
    if grep -qE "^## Detail[ -]Files" "$file" 2>/dev/null; then
        echo "  skipped: $file (sub-index with Detail-Files table — kept active)"
        SKIPPED_INDEX=$((SKIPPED_INDEX + 1))
        continue
    fi

    status="$(fm_field "$file" status 2>/dev/null || true)"
    case "$status" in
        draft|active)
            if $DRY_RUN; then
                echo "  [dry-run] would freeze: $file (status: $status → frozen)"
            else
                # Portable frontmatter write (WI-0076): fm_set stops at the
                # closing `---`, so a BODY line that happens to read like
                # "status: active" is never touched -- the BSD-only
                # `sed -i '' -E "s/^status:.../..."` this replaced applied
                # its per-line anchors across the WHOLE file, not just the
                # frontmatter block, and rewrote such a body line too.
                fm_set "$file" status frozen
                echo "  frozen: $file (was: $status)"
            fi
            CHANGED=$((CHANGED + 1))
            ;;
        skeleton|living|archived|frozen)
            SKIPPED=$((SKIPPED + 1))
            ;;
        "")
            echo "  WARNING: no status in frontmatter: $file" >&2
            WARNINGS=$((WARNINGS + 1))
            ;;
        *)
            echo "  WARNING: unknown status '$status' in $file" >&2
            WARNINGS=$((WARNINGS + 1))
            ;;
    esac
done <<< "$FILE_LIST"

# --- anchor hook (WI-0021 wave 4b, ADR-0009 Addendum 2 "A7 resolved") -----
#
# A SECOND, deliberate write path onto the phase INDEX -- the very file
# the Index-File-Skip above always leaves active. One gate pass produces
# one anchor for the whole scope, regardless of how few detail files
# happened to be freezable this run (the freeze-hook coverage problem
# ADR-0009's own A7/Addendum-2 discussion is written against).
#
# Delegates to `anchor set` rather than re-implementing "the last
# production-code commit" here: one classification, one refusal-on-
# overwrite rule, shared by this write path and the read path
# (`anchor status`/`check`). `anchor set` ALREADY refuses when the index
# carries an anchor, which is exactly the "only write if unanchored" rule
# this hook needs -- re-anchoring on drift is `anchor ack`'s job, never a
# side effect of a freeze (ADR-0009 SS6: never a side effect of another
# command).
#
# Best-effort and NON-FATAL by design: freezing the detail files is this
# script's PRIMARY job and must keep succeeding outside a git repository
# or without a phase index -- neither is this script's own precondition
# to enforce, and a --dry-run run must not write anything at all.
if ! $DRY_RUN; then
    INDEX_NAME=""
    case "$FOLDER" in
        discovery)    INDEX_NAME="DISCOVERY.md" ;;
        concept)      INDEX_NAME="CONCEPT.md" ;;
        validation)   INDEX_NAME="VALIDATION.md" ;;
        architecture) INDEX_NAME="ARCHITECTURE.md" ;;
        planning)     INDEX_NAME="PROJECT_PLAN.md" ;;
        quality)      INDEX_NAME="QA.md" ;;
        launch)       INDEX_NAME="LAUNCH.md" ;;
    esac

    ANCHOR_SCRIPT="$SCRIPT_DIR/anchor.sh"
    if [[ -n "$INDEX_NAME" && -f "$ANCHOR_SCRIPT" ]]; then
        # `set +e` around the capture: under this script's own
        # `set -euo pipefail`, a `VAR="$(cmd)"` assignment whose command
        # substitution exits nonzero aborts the WHOLE script immediately --
        # the "already anchored" refusal (anchor.sh's normal, expected
        # outcome on a second run) is not an error THIS script should die
        # on.
        set +e
        ANCHOR_OUTPUT="$(bash "$ANCHOR_SCRIPT" set "$PROJECT_DIR" --scope "$FOLDER" 2>&1)"
        ANCHOR_RC=$?
        set -e

        if [[ $ANCHOR_RC -eq 0 ]]; then
            echo "  $ANCHOR_OUTPUT"
        elif [[ $ANCHOR_RC -eq 3 ]]; then
            # Exit code 3 is `anchor set`'s DEDICATED "already anchored"
            # code (WI-0021 review, small fix #2) -- the CONTRACT this
            # branch gates on. The grep below is a redundant sanity
            # check only, logged but never gating, so the two scripts
            # are not coupled through message text alone.
            if ! printf '%s' "$ANCHOR_OUTPUT" | grep -q "already carries an anchor"; then
                echo "  anchor: unexpected message for exit code 3: $ANCHOR_OUTPUT" >&2
            fi
            EXISTING_SHA="$(fm_field "docs/$FOLDER/$INDEX_NAME" anchor_commit 2>/dev/null || true)"  # exit-status: exempt downstream-checks-result
            EXISTING_DATE="$(fm_field "docs/$FOLDER/$INDEX_NAME" anchor_date 2>/dev/null || true)"  # exit-status: exempt downstream-checks-result
            echo "  anchor already present ($EXISTING_SHA, $EXISTING_DATE) — re-anchoring is \`anchor ack\`"
        else
            echo "  anchor not set: $ANCHOR_OUTPUT"
        fi
    fi
fi

echo ""
if $DRY_RUN; then
    printf "[dry-run] Would freeze %d file(s). Skipped %d (terminal state), %d (index/sub-index).\n" \
        "$CHANGED" "$SKIPPED" "$SKIPPED_INDEX"
else
    printf "Froze %d file(s). Skipped %d (terminal state), %d (index/sub-index).\n" \
        "$CHANGED" "$SKIPPED" "$SKIPPED_INDEX"
fi

if [[ $WARNINGS -gt 0 ]]; then
    printf "Warnings: %d\n" "$WARNINGS"
    exit 1
fi
exit 0
