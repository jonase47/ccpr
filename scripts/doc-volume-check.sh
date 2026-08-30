#!/usr/bin/env bash
# doc-volume-check.sh — Read-only watcher for doc volume
# Lists files >25/40/50 KB and suggests splitting candidates.
#
# Thresholds (consistent with PROJECT_PHASES.md Document-Splitting-Convention):
#   info    25–40 KB  — splitting recommended
#   warning 40–50 KB  — splitting urgent
#   error   ≥50 KB    — read-fail risk (cf. G-017)
#
# Splitting heuristic: ≥6 H2 sections → "split-per-H2"
#
# Usage:
#   bash ~/.claude/scripts/doc-volume-check.sh [<docs-root>]
#
# Exit-Codes: 0 clean, 1 warnings, 2 errors.
#
# --- scope: tracked files only, inside a git working tree (WI-0129 Paket B,
# cycle B2) ---------------------------------------------------------------
#
# This check exists to flag oversized SHIPPED documentation pending a split
# (CONTRIBUTING.md's "known, stable baseline of findings"), not an adopter's
# own untracked working state -- drafts, persona memory silos
# (docs/memory/** is gitignored in this repository), generated reports.
# Measured directly on this repository's own working tree (30.08.2026): of
# 19 findings, all 5 critical and all 6 warning were untracked; only 3 of 8
# info findings were tracked -- a CI runner on a fresh checkout reproduces
# every one of those 16 untracked findings every single time, none of them a
# regression.
#
# <docs-root> is one directory BELOW the repository root (it is always
# invoked with <project>/docs, never <project> itself) -- git resolves its
# own working tree by walking up from cwd, so `git -C "$DOCS_ROOT" ...`
# still finds it.
#
# Outside a git working tree (no .git found anywhere above <docs-root>),
# every file under <docs-root> is scanned, exactly as before this cycle --
# there is no "tracked" concept to apply, and this script has always
# supported a bare, non-git docs-root (it takes no project-identity
# argument at all).
#
# Behavioural note for adopters, named rather than left silent: a project
# with real, UNTRACKED docs (drafts not yet committed) will see FEWER
# findings after this change than before. That is intentional -- this check
# is about documentation the project SHIPS, not the author's current
# working state -- but it is a real behaviour change, so the report itself
# names how many files were skipped as untracked (see "Untracked skipped"
# below), the same "say what was NOT covered" discipline artifact-gate.sh
# already applies to its own binary/symlink skips.

set -euo pipefail

DOCS_ROOT="${1:-$(pwd)/docs}"

if [[ ! -d "$DOCS_ROOT" ]]; then
    echo "doc-volume-check: $DOCS_ROOT does not exist"
    exit 0
fi

NOW="$(date '+%d.%m.%Y %H:%M')"

# TRACKED_ONLY is resolved once, before the scan, from whether <docs-root>
# sits inside a git working tree at all -- not from whether any individual
# file inside it happens to be tracked.
TRACKED_ONLY=0
TRACKED_LIST_FILE=""
if git -C "$DOCS_ROOT" rev-parse --show-toplevel >/dev/null 2>&1; then
    TRACKED_ONLY=1
    TRACKED_LIST_FILE="$(mktemp)"
    trap 'rm -f "$TRACKED_LIST_FILE"' EXIT
    # `git -C "$DOCS_ROOT" ls-files` (no pathspec) lists tracked files AT OR
    # BELOW $DOCS_ROOT, with paths already relative to it -- exactly the
    # same `rel` shape the scan loop below computes for every candidate
    # file, so the two can be compared byte-for-byte with no path rewriting.
    git -C "$DOCS_ROOT" ls-files -z 2>/dev/null \
        | while IFS= read -r -d '' relf; do printf '%s\n' "$relf"; done > "$TRACKED_LIST_FILE"  # exit-status: exempt set-e-sufficient
fi

# is_tracked <repo-relative-path> — true when TRACKED_ONLY is off (nothing to
# apply), or when <path> is a line in TRACKED_LIST_FILE. LC_ALL=C: an exact
# byte match against git's own byte-for-byte path output, not a
# locale-sensitive comparison (same reasoning memory-lint.sh's LC_ALL=C awk
# invocations already give for this codebase's grep/awk calls).
is_tracked() {
    local rel="$1"
    [[ "$TRACKED_ONLY" -eq 1 ]] || return 0
    LC_ALL=C grep -qxF -- "$rel" "$TRACKED_LIST_FILE"  # exit-status: exempt propagates-as-function-return
}

# File size in KB via wc -c (portable)
size_kb() {
    local file="$1"
    local bytes
    bytes="$(wc -c < "$file" | tr -d ' ')"
    echo $(( (bytes + 512) / 1024 ))
}

# Number of H2 sections (lines starting with "## " but not "### ")
h2_count() {
    local file="$1"
    local count
    # grep -c PRINTS "0" and STILL exits 1 when nothing matched. An
    # `|| echo 0` arm therefore fires ON TOP of that printed zero and makes
    # this function emit "0\n0", which breaks every (( )) below (WI-0101).
    # The arm must REPLACE the value, never add one -- so it is an
    # assignment, and it only ever takes effect when grep failed for a real
    # reason (exit 2) and printed nothing at all.
    count="$(grep -c '^## [^#]' "$file" 2>/dev/null)" || count=0
    echo "$count"
}

# Splitting suggestion
split_suggestion() {
    local file="$1"
    local h2
    h2="$(h2_count "$file")"
    if (( h2 >= 6 )); then
        echo "split-per-H2 ($h2 H2 sections)"
    elif (( h2 >= 3 )); then
        echo "moderate splitting possible ($h2 H2 sections)"
    else
        echo "no obvious splitting point ($h2 H2 sections) — review content"
    fi
}

errors=()
warnings=()
infos=()

# Scan
FILES_TOTAL=0
UNTRACKED_SKIPPED=0
while IFS= read -r file; do
    rel="${file#$DOCS_ROOT/}"
    if ! is_tracked "$rel"; then
        UNTRACKED_SKIPPED=$((UNTRACKED_SKIPPED + 1))
        continue
    fi
    FILES_TOTAL=$((FILES_TOTAL + 1))
    kb="$(size_kb "$file")"

    if (( kb >= 50 )); then
        errors+=("$rel (${kb} KB) → $(split_suggestion "$file")")
    elif (( kb >= 40 )); then
        warnings+=("$rel (${kb} KB) → $(split_suggestion "$file")")
    elif (( kb >= 25 )); then
        infos+=("$rel (${kb} KB) → $(split_suggestion "$file")")
    fi
done < <(find "$DOCS_ROOT" -type f -name "*.md" -not -path "*/.handover-archive/*")

# Report
echo "# Doc Volume Report"
echo
echo "**Scope:** $DOCS_ROOT/"
echo "**Run:** $NOW"
echo "**Files scanned:** $FILES_TOTAL"
if [[ "$TRACKED_ONLY" -eq 1 && "$UNTRACKED_SKIPPED" -gt 0 ]]; then
    echo "**Untracked skipped:** $UNTRACKED_SKIPPED file(s) not tracked by git — not shipped documentation, not scanned"
fi
echo

echo "## Critical (≥50 KB) — Splitting required (${#errors[@]})"
echo
if [[ ${#errors[@]} -eq 0 ]]; then echo "_none_"; fi
for e in "${errors[@]:-}"; do [[ -n "$e" ]] && echo "- $e"; done
echo

echo "## Warning (40–50 KB) — Splitting urgent (${#warnings[@]})"
echo
if [[ ${#warnings[@]} -eq 0 ]]; then echo "_none_"; fi
for w in "${warnings[@]:-}"; do [[ -n "$w" ]] && echo "- $w"; done
echo

echo "## Info (25–40 KB) — Splitting recommended (${#infos[@]})"
echo
if [[ ${#infos[@]} -eq 0 ]]; then echo "_none_"; fi
for i in "${infos[@]:-}"; do [[ -n "$i" ]] && echo "- $i"; done
echo

echo "---"
echo
echo "**Summary:** ${#errors[@]} critical, ${#warnings[@]} warning, ${#infos[@]} info."

if (( ${#errors[@]} > 0 )); then
    echo "**Exit:** 2"
    exit 2
elif (( ${#warnings[@]} > 0 )); then
    echo "**Exit:** 1"
    exit 1
fi
echo "**Exit:** 0"
exit 0
