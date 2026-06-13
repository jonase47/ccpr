#!/usr/bin/env bash
# Check instinct decay and generate suggestions.
# No LLM needed – purely file-based analysis.
# Usage: instinct-check.sh
set -euo pipefail

INSTINCTS_FILE="${HOME}/.claude/instincts.md"

if [ ! -f "${INSTINCTS_FILE}" ]; then
    echo "No instincts.md found."
    exit 0
fi

CONTENT=$(cat "${INSTINCTS_FILE}")

# Check file age
if [[ "$(uname)" == "Darwin" ]]; then
    MOD_TIME=$(stat -f %m "${INSTINCTS_FILE}")
else
    MOD_TIME=$(stat -c %Y "${INSTINCTS_FILE}")
fi
NOW=$(date +%s)
AGE_DAYS=$(( (NOW - MOD_TIME) / 86400 ))

echo "=== Instinct Status ==="
echo "File age: ${AGE_DAYS} days"
echo ""

# Count instincts
COUNT=$(grep -c '^### ' "${INSTINCTS_FILE}" 2>/dev/null || true)
COUNT="${COUNT:-0}"
echo "Active instincts: ${COUNT}"

if [ "${AGE_DAYS}" -gt 30 ]; then
    echo ""
    echo "WARNING: Instincts not updated for ${AGE_DAYS} days."
    echo "Recommendation: Run /instinct cleanup"
fi

if [ "${COUNT}" -gt 0 ]; then
    echo ""
    echo "=== Instinct Overview ==="
    grep -A 2 '^### ' "${INSTINCTS_FILE}" 2>/dev/null || true
fi
