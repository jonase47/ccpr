#!/usr/bin/env bash
# Summarize a file in 3-5 sentences via local Ollama.
#
# Usage: summarize.sh <file>
# Env:   OLLAMA_MODEL (default below — concise summarizer)

set -euo pipefail

# Concise summarizer model; can be overridden per call.
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma3:4b}"

if [[ $# -lt 1 ]]; then
  echo "Usage: summarize.sh <file>" >&2
  exit 2
fi

FILE="$1"
if [[ ! -f "${FILE}" ]]; then
  echo "summarize: file not found: ${FILE}" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTENT="$(cat "${FILE}")"

PROMPT="Summarize the following file in 3-5 sentences. Focus on purpose, key decisions, and open questions. No fluff, no preamble.

---
${CONTENT}
---"

"${SCRIPT_DIR}/ollama-query.sh" "${PROMPT}"
