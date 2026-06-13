#!/usr/bin/env bash
# Draft a HANDOVER.md update from git status, recent commits and (if present) the current HANDOVER.
# Output is a STARTING POINT — refine before committing.
#
# Usage: handover-draft.sh [projectdir]
# Env:   OLLAMA_MODEL (format-disciplined default from ollama-query.sh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-$(pwd)}"

if [[ ! -d "${PROJECT_DIR}" ]]; then
  echo "handover-draft: project dir not found: ${PROJECT_DIR}" >&2
  exit 2
fi

cd "${PROJECT_DIR}"

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "handover-draft: not a git repo: ${PROJECT_DIR}" >&2
  exit 2
fi

STATUS="$(git status --short 2>/dev/null | head -c 4000)"
LOG="$(git log --oneline -10 2>/dev/null)"
HANDOVER=""
if [[ -f "docs/HANDOVER.md" ]]; then
  HANDOVER="$(head -c 6000 docs/HANDOVER.md)"
fi
TEMPLATE_HINT=""
if [[ -f "${HOME}/.claude/templates/HANDOVER_TEMPLATE.md" ]]; then
  TEMPLATE_HINT="$(head -c 3000 "${HOME}/.claude/templates/HANDOVER_TEMPLATE.md")"
fi

PROMPT="Draft an updated HANDOVER.md for this project. Follow the template structure exactly. Be concrete: name files, decisions, blockers. No fluff. Output ONLY the markdown content.

# Template structure (shape only — use real project content):
${TEMPLATE_HINT}

# Current HANDOVER (if any):
${HANDOVER}

# Recent commits:
${LOG}

# Working tree state (git status --short):
${STATUS}"

"${SCRIPT_DIR}/ollama-query.sh" "${PROMPT}"
