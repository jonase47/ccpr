#!/usr/bin/env bash
# Shared Ollama wrapper. Sends a prompt to the local Ollama Chat API and prints the response.
#
# Usage:
#   echo "your prompt" | ollama-query.sh
#   ollama-query.sh "your prompt"
#   OLLAMA_MODEL=gemma3:4b ollama-query.sh "your prompt"
#
# Env:
#   OLLAMA_HOST   default: http://localhost:11434
#   OLLAMA_MODEL  default: gemma3:4b (format-disciplined; override per call when needed)
#   OLLAMA_TIMEOUT default: 60 (seconds, hard cap)

set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma3:4b}"
OLLAMA_TIMEOUT="${OLLAMA_TIMEOUT:-60}"

# Read prompt from arg or stdin
if [[ $# -gt 0 ]]; then
  PROMPT="$*"
else
  PROMPT="$(cat -)"
fi

if [[ -z "${PROMPT// }" ]]; then
  echo "ollama-query: empty prompt" >&2
  exit 2
fi

# Reachability check (fast fail with clear message)
if ! curl -sf --max-time 3 "${OLLAMA_HOST}/api/tags" >/dev/null; then
  echo "ollama-query: Ollama unreachable at ${OLLAMA_HOST}. Start it with 'ollama serve' or set OLLAMA_HOST." >&2
  exit 3
fi

# JSON-escape via python (avoids jq dependency)
PAYLOAD="$(python3 -c '
import json, sys
print(json.dumps({
  "model": sys.argv[1],
  "messages": [{"role": "user", "content": sys.argv[2]}],
  "stream": False
}))
' "${OLLAMA_MODEL}" "${PROMPT}")"

RESPONSE="$(curl -sf --max-time "${OLLAMA_TIMEOUT}" \
  -H 'Content-Type: application/json' \
  -d "${PAYLOAD}" \
  "${OLLAMA_HOST}/api/chat")" || {
    echo "ollama-query: request failed (model='${OLLAMA_MODEL}', timeout=${OLLAMA_TIMEOUT}s)" >&2
    exit 4
  }

python3 -c '
import json, sys
data = json.loads(sys.stdin.read())
print(data.get("message", {}).get("content", "").strip())
' <<< "${RESPONSE}"
