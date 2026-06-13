#!/usr/bin/env bash
# bootstrap.sh – Collects project context before session start into a compact file.
# Usage: ~/.claude/scripts/bootstrap.sh [project-directory]
# Output: docs/.session-context.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-$(pwd)}"
OUTPUT_FILE="${PROJECT_DIR}/docs/.session-context.md"
HANDOVER_FILE="${PROJECT_DIR}/docs/HANDOVER.md"
INSTINCTS_FILE="${HOME}/.claude/instincts.md"
NEXT_STEPS_PY="${SCRIPT_DIR}/lib/next_steps.py"
ARTEFACTS_PY="${SCRIPT_DIR}/lib/artefacts.py"

# Ensure docs directory exists
mkdir -p "${PROJECT_DIR}/docs"

# -- Helpers --

timestamp() {
    date "+%d.%m.%Y %H:%M"
}

# -- Git Status --

collect_git_status() {
    if ! git -C "${PROJECT_DIR}" rev-parse --is-inside-work-tree &>/dev/null; then
        echo "Not a git repository."
        return
    fi

    local branch uncommitted last_commit

    branch=$(git -C "${PROJECT_DIR}" branch --show-current 2>/dev/null || echo "detached")
    uncommitted=$(git -C "${PROJECT_DIR}" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    last_commit=$(git -C "${PROJECT_DIR}" log -1 --format="%s (%cr)" 2>/dev/null || echo "No commit")

    echo "- Branch: ${branch}"
    echo "- Uncommitted: ${uncommitted} files"
    echo "- Last commit: ${last_commit}"

    if [ "${uncommitted}" -gt 0 ]; then
        echo "- Changed files:"
        git -C "${PROJECT_DIR}" status --porcelain 2>/dev/null | head -10 | while read -r line; do
            echo "  - ${line}"
        done
        local total
        total=$(git -C "${PROJECT_DIR}" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
        if [ "${total}" -gt 10 ]; then
            echo "  - ... and $((total - 10)) more"
        fi
    fi
}

# -- HANDOVER.md --

collect_handover() {
    if [ ! -f "${HANDOVER_FILE}" ]; then
        echo "No HANDOVER.md found – new session or new project."
        return
    fi

    # Extract key sections
    local phase status last_agent next_step

    # Strip markdown bold (**) and extract value after colon
    phase=$(sed -n 's/^[* ]*Phase[* ]*:[[:space:]]*//p' "${HANDOVER_FILE}" 2>/dev/null | sed 's/\*//g; s/^[[:space:]]*//' | head -1) || true
    phase="${phase:-Unknown}"

    # Status: try dedicated field first, fall back to parenthetical in phase line
    status=$(sed -n 's/^[* ]*Status[* ]*:[[:space:]]*//p' "${HANDOVER_FILE}" 2>/dev/null | sed 's/\*//g' | head -1) || true
    if [ -z "${status}" ]; then
        # Extract from phase line, e.g. "P2 Validation (completed, Gate GO)"
        status=$(echo "${phase}" | sed -n 's/.*(\(.*\)).*/\1/p') || true
    fi
    status="${status:-Unknown}"

    # "Next Steps" inline field (not the ## section)
    local next_inline
    next_inline=$(sed -n 's/^[* ]*Next Steps[* ]*:[[:space:]]*//p' "${HANDOVER_FILE}" 2>/dev/null | sed 's/\*//g' | head -1) || true

    last_agent=$(sed -n 's/^[* ]*Last Active[* ]*:[[:space:]]*//p' "${HANDOVER_FILE}" 2>/dev/null | sed 's/\*//g; s/^[[:space:]]*//' | head -1) || true
    last_agent="${last_agent:-Unknown}"

    echo "- Phase: ${phase}"
    echo "- Status: ${status}"
    if [ -n "${next_inline}" ]; then
        echo "- Next: ${next_inline}"
    fi
    echo "- Last: ${last_agent}"

    # Extract next steps from ## Next Steps section
    local next_lines
    next_lines=$(sed -n '/## Next/,/^##/p' "${HANDOVER_FILE}" 2>/dev/null | grep -v '^##' | grep -E '^[0-9]+\.|^-|^/' | head -3) || true
    if [ -n "${next_lines}" ]; then
        echo "- Next Steps:"
        echo "${next_lines}" | while read -r line; do
            echo "  ${line}"
        done
    fi

    # Extract context for next session
    local context_lines
    context_lines=$(sed -n '/## Context/,/^##/p' "${HANDOVER_FILE}" 2>/dev/null | grep -v '^##' | head -5) || true
    if [ -n "${context_lines}" ]; then
        echo ""
        echo "### Context from last session"
        echo "${context_lines}"
    fi
}

# -- Next Steps --

collect_next_steps() {
    if [ ! -f "${NEXT_STEPS_PY}" ]; then
        echo "next_steps.py not found."
        return
    fi

    local result
    result=$(python3 "${NEXT_STEPS_PY}" "${PROJECT_DIR}" 2>/dev/null) || return

    local commands
    commands=$(echo "${result}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for cmd in data.get('allowed_commands', []):
    print(f'- /{cmd}')
" 2>/dev/null) || return

    if [ -n "${commands}" ]; then
        echo "${commands}"
    else
        echo "- No commands derivable (check HANDOVER.md)"
    fi
}

# -- Artefacts --

collect_artefacts() {
    if [ ! -f "${ARTEFACTS_PY}" ]; then
        echo "artefacts.py not found."
        return
    fi

    # Determine phase from HANDOVER or default to p0
    local phase="p0"
    if [ -f "${HANDOVER_FILE}" ]; then
        local p
        p=$(sed -n 's/.*\(P[0-8]\).*/\1/p' "${HANDOVER_FILE}" 2>/dev/null | head -1) || true
        if [ -n "${p}" ]; then
            phase=$(echo "${p}" | tr '[:upper:]' '[:lower:]')
        fi
    fi

    python3 "${ARTEFACTS_PY}" "${phase}" "${PROJECT_DIR}" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
for a in data.get('artefacts', []):
    marker = '[+]' if a['exists'] else '[-]'
    if a['is_dir']:
        detail = f\"{a['lines']} files\" if a['exists'] else ''
    else:
        detail = f\"{a['lines']} lines\" if a['exists'] else ''
    suffix = f' ({detail})' if detail else ''
    print(f\"{marker} {a['path']}{suffix}\")
" 2>/dev/null || echo "Artifact check failed."
}

# -- Instincts --

collect_instincts() {
    if [ ! -f "${INSTINCTS_FILE}" ]; then
        echo "No instincts.md found."
        return
    fi

    # Count active instincts
    local count
    count=$(grep -c '^### ' "${INSTINCTS_FILE}" 2>/dev/null) || count=0
    echo "- ${count} active instincts"

    if [ "${count}" -eq 0 ]; then
        return
    fi

    # Check for decay warnings (instincts not confirmed in >30 days)
    # Simple heuristic: check if file was modified in last 30 days
    local file_age_days
    if [[ "$(uname)" == "Darwin" ]]; then
        local mod_time
        mod_time=$(stat -f %m "${INSTINCTS_FILE}" 2>/dev/null || echo "0")
        local now
        now=$(date +%s)
        file_age_days=$(( (now - mod_time) / 86400 ))
    else
        file_age_days=$(( ($(date +%s) - $(stat -c %Y "${INSTINCTS_FILE}" 2>/dev/null || echo "0")) / 86400 ))
    fi

    if [ "${file_age_days}" -gt 30 ]; then
        echo "- WARNING: instincts.md not updated in ${file_age_days} days"
    fi

    # List instinct IDs with confidence
    grep -E '^### \[' "${INSTINCTS_FILE}" 2>/dev/null | head -5 | while read -r line; do
        echo "  ${line}"
    done
}

# -- Main Output --

{
    echo "# Session Context (generated: $(timestamp))"
    echo ""

    echo "## Git Status"
    collect_git_status
    echo ""

    echo "## Current State (from HANDOVER.md)"
    collect_handover
    echo ""

    echo "## Allowed Next Commands"
    collect_next_steps
    echo ""

    echo "## Available Artifacts"
    collect_artefacts
    echo ""

    echo "## Instinct Status"
    collect_instincts
    echo ""

} > "${OUTPUT_FILE}"

echo "Session context written: ${OUTPUT_FILE}"
