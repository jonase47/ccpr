#!/usr/bin/env bash
# Generate a Conventional Commits message from staged diff via local Ollama.
#
# Usage:
#   git add -p
#   commit-msg.sh                 # prints suggestion to stdout
#   commit-msg.sh | git commit -F -
#
# Env: OLLAMA_MODEL (format-disciplined default from ollama-query.sh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find git root from caller's CWD
if ! GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "commit-msg: not in a git repo" >&2
  exit 2
fi

DIFF="$(git -C "${GIT_ROOT}" diff --cached --stat --patch | head -c 12000)"
if [[ -z "${DIFF// }" ]]; then
  echo "commit-msg: no staged changes. Run 'git add' first." >&2
  exit 2
fi

PROMPT="Generate a Conventional Commits message for the following staged diff.

Rules:
- First line: type(scope): subject — imperative, max 72 chars.
  Types: feat, fix, refactor, docs, chore, test, perf, style, ci, build, revert.
- Blank line, then a short body explaining WHY (not what), max 3 lines.
- No trailing footer, no emojis, no markdown fences.
- Output ONLY the commit message, nothing else.

Diff:
---
${DIFF}
---"

"${SCRIPT_DIR}/ollama-query.sh" "${PROMPT}"
