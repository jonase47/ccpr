#!/usr/bin/env bash
# Mechanical preparation for the release baseline cut.
# Usage: baseline.sh [version] [projectdir]
# Result: docs/.baseline-prep.md
set -euo pipefail

VERSION="${1:?Usage: baseline.sh <version> [projectdir]}"
PROJECT_DIR="${2:-.}"

# Resolve to absolute path
PROJECT_DIR="$(cd "${PROJECT_DIR}" && pwd)"

DOCS_DIR="${PROJECT_DIR}/docs"
HANDOVER="${DOCS_DIR}/HANDOVER.md"
CLAUDE_MD="${PROJECT_DIR}/.claude/CLAUDE.md"
PROJECT_PLAN="${DOCS_DIR}/planning/PROJECT_PLAN.md"
ARCHIVE_DIR="${DOCS_DIR}/handover-archive"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="${DOCS_DIR}/.baseline-prep.md"
TODAY=$(date +%d.%m.%Y)

# Help flag
if [[ "${VERSION}" == "--help" || "${VERSION}" == "-h" ]]; then
    echo "Usage: baseline.sh <version> [projectdir]"
    echo ""
    echo "Mechanical preparation for the release baseline cut."
    echo "Creates docs/.baseline-prep.md with:"
    echo "  - Archived HANDOVER.md"
    echo "  - HANDOVER summary (via Ollama, if available)"
    echo "  - Phase Status Tracker"
    echo "  - Tech Stack"
    echo "  - Milestones"
    echo "  - Git tags"
    echo ""
    echo "Example: baseline.sh v1.0.0 ~/projects/my-project"
    exit 0
fi

echo "=== Baseline preparation for ${VERSION} ==="
echo "Project directory: ${PROJECT_DIR}"

# 1. Archive directory
mkdir -p "${ARCHIVE_DIR}"
echo "[OK] Archive directory: ${ARCHIVE_DIR}"

# 2. Archive HANDOVER.md
if [ -f "${HANDOVER}" ]; then
    ARCHIVE_NAME="HANDOVER_${VERSION}_${TODAY}.md"
    cp "${HANDOVER}" "${ARCHIVE_DIR}/${ARCHIVE_NAME}"
    echo "[OK] HANDOVER.md archived as ${ARCHIVE_NAME}"
else
    echo "[SKIP] No HANDOVER.md found"
    ARCHIVE_NAME=""
fi

# 3. HANDOVER summary via Ollama
HANDOVER_SUMMARY=""
if [ -f "${HANDOVER}" ]; then
    OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
    if curl -s --connect-timeout 2 "${OLLAMA_URL}/api/tags" &>/dev/null; then
        echo "[...] Creating HANDOVER summary via Ollama..."
        # Smart truncation: header (context) + tail (newest content)
        TOTAL_LINES=$(wc -l < "${HANDOVER}" | tr -d ' ')
        if [ "${TOTAL_LINES}" -le 200 ]; then
            CONTENT=$(cat "${HANDOVER}")
        else
            HEADER=$(head -n 20 "${HANDOVER}")
            TAIL=$(tail -n 180 "${HANDOVER}")
            CONTENT="${HEADER}
...
${TAIL}"
        fi
        PROMPT="Summarize this HANDOVER.md. The newest entries are at the end of the document – weight these more heavily. Focus: What is the current project status, which milestones have been reached, which decisions are relevant. Max. 10 sentences in English.

---
${CONTENT}
---"
        HANDOVER_SUMMARY=$("${SCRIPT_DIR}/local-llm/ollama-query.sh" "${PROMPT}" 2>/dev/null || true)
        if [ -n "${HANDOVER_SUMMARY}" ]; then
            echo "[OK] HANDOVER summary created"
        else
            echo "[SKIP] Ollama summary failed"
        fi
    else
        echo "[SKIP] Ollama not reachable – HANDOVER summary skipped"
    fi
fi

# 4. Collect project state
PHASE_TRACKER=""
TECH_STACK=""
MILESTONES=""
GIT_TAGS=""

# Phase Status Tracker from CLAUDE.md
if [ -f "${CLAUDE_MD}" ]; then
    PHASE_TRACKER=$(sed -n '/Phase Status Tracker/,/^##/p' "${CLAUDE_MD}" | head -n -1)
    TECH_STACK=$(sed -n '/Tech Stack/,/^##/p' "${CLAUDE_MD}" | head -n -1)
fi

# Milestones from PROJECT_PLAN.md
if [ -f "${PROJECT_PLAN}" ]; then
    MILESTONES=$(sed -n '/Milestone/,/^##/p' "${PROJECT_PLAN}" | head -n 30)
fi

# Git tags
if git -C "${PROJECT_DIR}" rev-parse --git-dir &>/dev/null; then
    GIT_TAGS=$(git -C "${PROJECT_DIR}" tag -l --sort=-v:refname 2>/dev/null | head -n 10)
fi

# 5. Write output
cat > "${OUTPUT}" << PREP_EOF
# Baseline Preparation: ${VERSION}

**Created**: ${TODAY}
**Project directory**: ${PROJECT_DIR}

## HANDOVER Archive
$(if [ -n "${ARCHIVE_NAME}" ]; then echo "Archived as: \`docs/handover-archive/${ARCHIVE_NAME}\`"; else echo "No HANDOVER.md present"; fi)

## HANDOVER Summary
$(if [ -n "${HANDOVER_SUMMARY}" ]; then echo "${HANDOVER_SUMMARY}"; else echo "_Not available (Ollama not reachable or HANDOVER.md not present)_"; fi)

## Phase Status Tracker
$(if [ -n "${PHASE_TRACKER}" ]; then echo "${PHASE_TRACKER}"; else echo "_Not found in .claude/CLAUDE.md_"; fi)

## Tech Stack
$(if [ -n "${TECH_STACK}" ]; then echo "${TECH_STACK}"; else echo "_Not found in .claude/CLAUDE.md_"; fi)

## Milestones
$(if [ -n "${MILESTONES}" ]; then echo "${MILESTONES}"; else echo "_Not found in docs/planning/PROJECT_PLAN.md_"; fi)

## Git Tags
$(if [ -n "${GIT_TAGS}" ]; then echo "\`\`\`"; echo "${GIT_TAGS}"; echo "\`\`\`"; else echo "_No Git tags present_"; fi)
PREP_EOF

echo ""
echo "[DONE] Baseline preparation written: ${OUTPUT}"
echo "Next step: /release-baseline ${VERSION}"
