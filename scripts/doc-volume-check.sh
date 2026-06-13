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

set -euo pipefail

DOCS_ROOT="${1:-$(pwd)/docs}"

if [[ ! -d "$DOCS_ROOT" ]]; then
    echo "doc-volume-check: $DOCS_ROOT does not exist"
    exit 0
fi

NOW="$(date '+%d.%m.%Y %H:%M')"

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
    grep -c '^## [^#]' "$file" 2>/dev/null || echo 0
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
while IFS= read -r file; do
    FILES_TOTAL=$((FILES_TOTAL + 1))
    kb="$(size_kb "$file")"
    rel="${file#$DOCS_ROOT/}"

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
