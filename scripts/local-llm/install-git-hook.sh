#!/usr/bin/env bash
# Install a prepare-commit-msg hook that pre-fills the commit message via commit-msg.sh.
# The suggestion is editable in the editor — the hook never finalizes a commit on its own.
#
# Usage: install-git-hook.sh <projectdir>

set -euo pipefail

PROJECT_DIR="${1:-}"
if [[ -z "${PROJECT_DIR}" ]]; then
  echo "Usage: install-git-hook.sh <projectdir>" >&2
  exit 2
fi

cd "${PROJECT_DIR}"

if ! GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)"; then
  echo "install-git-hook: not a git repo: ${PROJECT_DIR}" >&2
  exit 2
fi

HOOK_PATH="${GIT_DIR}/hooks/prepare-commit-msg"

if [[ -f "${HOOK_PATH}" ]]; then
  BACKUP="${HOOK_PATH}.bak.$(date +%Y%m%d_%H%M%S)"
  cp "${HOOK_PATH}" "${BACKUP}"
  echo "install-git-hook: existing hook backed up to ${BACKUP}"
fi

cat > "${HOOK_PATH}" <<'HOOK'
#!/usr/bin/env bash
# Auto-suggest commit message via local LLM. Editable — falls back silently if Ollama is down.
set -e

COMMIT_MSG_FILE="$1"
COMMIT_SOURCE="${2:-}"

# Skip for merges, squashes, amends, templates, messages from -m
case "${COMMIT_SOURCE}" in
  merge|squash|template|message|commit) exit 0 ;;
esac

# Only suggest if message file is empty or contains only comments
if [[ -n "$(grep -v '^#' "${COMMIT_MSG_FILE}" 2>/dev/null | tr -d '[:space:]')" ]]; then
  exit 0
fi

SUGGESTION="$(${HOME}/.claude/scripts/local-llm/commit-msg.sh 2>/dev/null || true)"
if [[ -n "${SUGGESTION// }" ]]; then
  { echo "${SUGGESTION}"; echo; cat "${COMMIT_MSG_FILE}"; } > "${COMMIT_MSG_FILE}.new"
  mv "${COMMIT_MSG_FILE}.new" "${COMMIT_MSG_FILE}"
fi
HOOK

chmod +x "${HOOK_PATH}"
echo "install-git-hook: installed prepare-commit-msg hook at ${HOOK_PATH}"
echo "  -> next 'git commit' (without -m) will pre-fill via local-llm/commit-msg.sh"
