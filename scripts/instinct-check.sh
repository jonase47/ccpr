#!/usr/bin/env bash
# Check instinct decay and generate suggestions.
# No LLM needed – purely file-based analysis.
#
# Usage: instinct-check.sh [<project-dir>]
#   <project-dir>  optional; defaults to $(pwd). Adds the project-scoped
#                  instinct layers to the report.
#
# LAYOUT NOTE (why this script is not a one-liner):
# Global Tier-1 instincts live in a SLIM INDEX (~/.claude/instincts.md — one
# bullet per instinct, autoloaded at session start) PLUS per-theme topic files
# (~/.claude/instincts/{theme}.md) that carry the full "### <ID>" entries.
# Counting "### " in the index alone reports 0 once the split layout is in use.
# The entries are in the topic files; the index only points at them.
set -euo pipefail

PROJECT_DIR="${1:-$(pwd)}"

GLOBAL_INDEX="${HOME}/.claude/instincts.md"
GLOBAL_TOPICS="${HOME}/.claude/instincts"
GLOBAL_PERSONA="${HOME}/.claude/memory"

# --- helpers ----------------------------------------------------------------

# Entry-heading pattern. Heading LEVEL is not consistent across the ecosystem:
# global Tier-1 topic files and most silos use "### G-100", but project Tier-2
# silos use "## BA-P-001". So match H2 and H3 alike and anchor on the instinct
# ID instead of the level — that also keeps prose headings ("## Decay-Politik")
# out of the count. Covers G-100, KA-G-017, OL-SD-G-001, P-001, BA-P-001, KZ-001.
ENTRY_PATTERN='^#{2,3} [A-Z][A-Z0-9-]*-[0-9]{3}'

# Count instinct entries across the given files. Missing files count as 0.
count_entries() {
    local total=0 f n
    for f in "$@"; do
        [ -f "$f" ] || continue
        n=$(grep -cE "${ENTRY_PATTERN}" "$f" 2>/dev/null || true)
        total=$(( total + ${n:-0} ))
    done
    echo "$total"
}

# Count index bullets. Every index bullet carries a confidence marker "[0.x]",
# which is the reliable marker — ID prefixes vary (G-, KA-G-, OL-G-, SD-G-).
count_index_bullets() {
    local f="$1" n
    [ -f "$f" ] || { echo 0; return; }
    # grep -c prints "0" AND exits 1 on no match — swallow the status, keep the count.
    n=$(grep -cE '^- .*\[0\.[0-9]\]' "$f" 2>/dev/null || true)
    echo "${n:-0}"
}

mtime_of() {
    if [[ "$(uname)" == "Darwin" ]]; then
        stat -f %m "$1"
    else
        stat -c %Y "$1"
    fi
}

# Newest mtime across all given files — the index alone is not the age signal,
# a topic file can be edited without the index changing.
newest_mtime() {
    local newest=0 f m
    for f in "$@"; do
        [ -f "$f" ] || continue
        m=$(mtime_of "$f")
        [ "$m" -gt "$newest" ] && newest="$m"
    done
    echo "$newest"
}

extract_ids() {
    # $1 = heading/bullet prefix regex ("- " for index bullets, "#{2,3} " for entries)
    # remaining args = files
    local prefix="$1"; shift
    grep -hoE "^${prefix}[A-Z][A-Z0-9-]*-[0-9]{3}" "$@" 2>/dev/null \
        | sed -E "s/^${prefix}//" | sort -u || true
}

# --- global Tier-1 ----------------------------------------------------------

if [ ! -f "${GLOBAL_INDEX}" ]; then
    echo "No global instincts.md found at ${GLOBAL_INDEX}."
    exit 0
fi

shopt -s nullglob
TOPIC_FILES=( "${GLOBAL_TOPICS}"/*.md )
PERSONA_FILES=( "${GLOBAL_PERSONA}"/*/instincts.md )
shopt -u nullglob

INDEX_BULLETS=$(count_index_bullets "${GLOBAL_INDEX}")
if [ "${#TOPIC_FILES[@]}" -gt 0 ]; then
    TOPIC_ENTRIES=$(count_entries "${TOPIC_FILES[@]}")
else
    # No split layout — fall back to counting entries in the index itself.
    TOPIC_ENTRIES=$(count_entries "${GLOBAL_INDEX}")
fi

# bash 3.2 (macOS default) treats "${arr[@]}" on an EMPTY array as unbound
# under `set -u` — hence the ${arr[@]+...} guard on every value expansion.
# ${#arr[@]} is safe and needs no guard.
NEWEST=$(newest_mtime "${GLOBAL_INDEX}" ${TOPIC_FILES[@]+"${TOPIC_FILES[@]}"})
AGE_DAYS=$(( ( $(date +%s) - NEWEST ) / 86400 ))

echo "=== Instinct Status ==="
echo "Newest change (index + topic files): ${AGE_DAYS} days ago"
echo ""
echo "--- Global Tier-1 (all projects, all agents) ---"
echo "Index bullets:  ${INDEX_BULLETS}   (${GLOBAL_INDEX##*/})"
echo "Topic entries:  ${TOPIC_ENTRIES}   (across ${#TOPIC_FILES[@]} topic files)"

if [ "${#TOPIC_FILES[@]}" -gt 0 ]; then
    for f in "${TOPIC_FILES[@]}"; do
        printf '  %-26s %s\n' "$(basename "$f")" "$(count_entries "$f")"
    done
fi

# Reconcile index against topic files. A delta is NOT automatically a defect:
# frozen overlay files (imported-*.md, superseded sets) are intentionally not
# listed bullet-by-bullet in the index. Report the IDs and let the human judge.
if [ "${#TOPIC_FILES[@]}" -gt 0 ]; then
    IDX_IDS=$(extract_ids "- " "${GLOBAL_INDEX}")
    TOPIC_IDS=$(extract_ids "#{2,3} " "${TOPIC_FILES[@]}")
    UNLISTED=$(comm -13 <(echo "${IDX_IDS}") <(echo "${TOPIC_IDS}") || true)
    DANGLING=$(comm -23 <(echo "${IDX_IDS}") <(echo "${TOPIC_IDS}") || true)

    if [ -n "${UNLISTED}" ]; then
        echo ""
        echo "INFO: in a topic file but not listed individually in the index:"
        echo "${UNLISTED}" | sed 's/^/  /'
        echo "  Expected for frozen/superseded overlays (e.g. imported-*.md)."
        echo "  Unexpected for native entries — those should carry an index bullet."
    fi
    if [ -n "${DANGLING}" ]; then
        echo ""
        echo "WARNING: listed in the index but no matching entry in any topic file:"
        echo "${DANGLING}" | sed 's/^/  /'
        echo "  The index points at content that does not exist. Fix via /instinct."
    fi
fi

# --- global Tier-2 (persona silos) -----------------------------------------

if [ "${#PERSONA_FILES[@]}" -gt 0 ]; then
    echo ""
    echo "--- Global Tier-2 (persona silos, all projects) ---"
    for f in "${PERSONA_FILES[@]}"; do
        agent="${f#${GLOBAL_PERSONA}/}"; agent="${agent%/instincts.md}"
        printf '  %-26s %s\n' "${agent}" "$(count_entries "$f")"
    done
fi

# --- project layers ---------------------------------------------------------

PROJ_T1="${PROJECT_DIR}/docs/instincts.md"
shopt -s nullglob
PROJ_T2=( "${PROJECT_DIR}"/docs/memory/*/instincts.md )
shopt -u nullglob

if [ -f "${PROJ_T1}" ] || [ "${#PROJ_T2[@]}" -gt 0 ]; then
    echo ""
    echo "--- Project (${PROJECT_DIR}) ---"
    if [ -f "${PROJ_T1}" ]; then
        printf '  %-26s %s\n' "docs/instincts.md" "$(count_entries "${PROJ_T1}")"
    else
        echo "  docs/instincts.md          (none)"
    fi
    for f in ${PROJ_T2[@]+"${PROJ_T2[@]}"}; do
        agent="${f#${PROJECT_DIR}/docs/memory/}"; agent="${agent%/instincts.md}"
        printf '  %-26s %s\n' "memory/${agent}" "$(count_entries "$f")"
    done
else
    echo ""
    echo "--- Project (${PROJECT_DIR}) ---"
    echo "  no project instinct layer found"
fi

# --- decay hint -------------------------------------------------------------

if [ "${AGE_DAYS}" -gt 30 ]; then
    echo ""
    echo "WARNING: instincts not updated for ${AGE_DAYS} days."
    echo "Recommendation: run /postmortem (decay review) or /instinct cleanup"
fi
