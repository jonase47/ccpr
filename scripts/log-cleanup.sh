#!/usr/bin/env bash
# Log cleanup: Trim old session logs and aggregated logs.
# Usage: log-cleanup.sh [--days N] [--dry-run]
# Default: Remove everything older than 7 days.
set -euo pipefail

LOG_DIR="${HOME}/.claude/logs"
SESSION_DIR="${LOG_DIR}/sessions"
KEEP_DAYS="${KEEP_DAYS:-7}"
DRY_RUN=false

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --days)
            KEEP_DAYS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: log-cleanup.sh [--days N] [--dry-run]"
            echo ""
            echo "Cleans up old Claude Code logs."
            echo ""
            echo "Options:"
            echo "  --days N     Remove logs older than N days (default: 7)"
            echo "  --dry-run    Only show what would be deleted"
            echo ""
            echo "What happens:"
            echo "  1. Delete session directories older than N days"
            echo "     (session-summary.json is kept as archive)"
            echo "  2. Trim aggregated logs (activity/errors/performance.jsonl)"
            echo "     to entries from the last N days"
            echo ""
            echo "Example: log-cleanup.sh --days 14 --dry-run"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

echo "=== Log cleanup (keeping last ${KEEP_DAYS} days) ==="
if $DRY_RUN; then
    echo "[DRY-RUN] No files will be deleted."
fi

# Current date as reference
CUTOFF_DATE=$(date -v-${KEEP_DAYS}d +%Y-%m-%dT00:00:00 2>/dev/null || date -d "${KEEP_DAYS} days ago" +%Y-%m-%dT00:00:00 2>/dev/null)
echo "Cutoff: ${CUTOFF_DATE}"
echo ""

# === 1. Clean up session logs ===
SESSIONS_REMOVED=0
SESSIONS_KEPT=0
BYTES_FREED=0

if [ -d "${SESSION_DIR}" ]; then
    for session in "${SESSION_DIR}"/*/; do
        [ -d "${session}" ] || continue
        session_id=$(basename "${session}")

        # Determine age: newest file in directory
        newest_file=$(find "${session}" -type f -printf '%T@\n' 2>/dev/null | sort -rn | head -1 || \
                      stat -f '%m' "${session}"/*.jsonl 2>/dev/null | sort -rn | head -1 || echo "0")

        # macOS-compatible: directory modification time as fallback
        if [ -z "${newest_file}" ] || [ "${newest_file}" = "0" ]; then
            newest_file=$(stat -f '%m' "${session}" 2>/dev/null || echo "0")
        fi

        cutoff_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${CUTOFF_DATE}" +%s 2>/dev/null || \
                       date -d "${CUTOFF_DATE}" +%s 2>/dev/null || echo "0")

        # Comparison: is the session older than the cutoff?
        if [ "${newest_file%.*}" -lt "${cutoff_epoch}" ] 2>/dev/null; then
            session_size=$(du -sk "${session}" 2>/dev/null | cut -f1)

            # Archive session-summary.json (into archive directory)
            if [ -f "${session}session-summary.json" ]; then
                ARCHIVE_DIR="${LOG_DIR}/session-archive"
                if ! $DRY_RUN; then
                    mkdir -p "${ARCHIVE_DIR}"
                    cp "${session}session-summary.json" "${ARCHIVE_DIR}/${session_id}.json" 2>/dev/null || true
                fi
            fi

            if $DRY_RUN; then
                echo "  [REMOVE] ${session_id} (${session_size}KB)"
            else
                rm -rf "${session}"
            fi
            SESSIONS_REMOVED=$((SESSIONS_REMOVED + 1))
            BYTES_FREED=$((BYTES_FREED + ${session_size:-0}))
        else
            SESSIONS_KEPT=$((SESSIONS_KEPT + 1))
        fi
    done
fi

echo "Sessions: ${SESSIONS_REMOVED} removed, ${SESSIONS_KEPT} kept"
if [ ${SESSIONS_REMOVED} -gt 0 ]; then
    echo "  Summaries archived in: ${LOG_DIR}/session-archive/"
fi

# === 2. Trim aggregated logs ===
LINES_BEFORE=0
LINES_AFTER=0

for logfile in activity.jsonl errors.jsonl performance.jsonl; do
    filepath="${LOG_DIR}/${logfile}"
    [ -f "${filepath}" ] || continue

    lines_before=$(wc -l < "${filepath}" | tr -d ' ')
    LINES_BEFORE=$((LINES_BEFORE + lines_before))

    if $DRY_RUN; then
        # Only count how many lines would remain
        lines_after=$(python3 -c "
import json, sys
cutoff = '${CUTOFF_DATE}'
count = 0
for line in open('${filepath}'):
    try:
        ts = json.loads(line).get('ts', '')
        if ts >= cutoff:
            count += 1
    except: pass
print(count)
" 2>/dev/null || echo "${lines_before}")
        echo "  [TRIM] ${logfile}: ${lines_before} -> ${lines_after} lines"
        LINES_AFTER=$((LINES_AFTER + lines_after))
    else
        # Actually trim
        tmpfile=$(mktemp)
        python3 -c "
import json
cutoff = '${CUTOFF_DATE}'
with open('${filepath}') as f_in, open('${tmpfile}', 'w') as f_out:
    for line in f_in:
        try:
            ts = json.loads(line).get('ts', '')
            if ts >= cutoff:
                f_out.write(line)
        except:
            pass  # Discard broken lines
" 2>/dev/null
        lines_after=$(wc -l < "${tmpfile}" | tr -d ' ')
        LINES_AFTER=$((LINES_AFTER + lines_after))
        mv "${tmpfile}" "${filepath}"
        echo "  [TRIM] ${logfile}: ${lines_before} -> ${lines_after} lines"
    fi
done

# === 3. Remove rotated logs ===
ROTATED_REMOVED=0
for rotated in "${LOG_DIR}"/*.*.jsonl; do
    [ -f "${rotated}" ] || continue
    if $DRY_RUN; then
        echo "  [REMOVE] $(basename "${rotated}")"
    else
        rm -f "${rotated}"
    fi
    ROTATED_REMOVED=$((ROTATED_REMOVED + 1))
done

if [ ${ROTATED_REMOVED} -gt 0 ]; then
    echo "Rotated logs: ${ROTATED_REMOVED} removed"
fi

# === Summary ===
echo ""
echo "=== Result ==="
echo "Sessions: ${SESSIONS_REMOVED} removed, ${SESSIONS_KEPT} kept"
echo "Log lines: ${LINES_BEFORE} -> ${LINES_AFTER} ($(( LINES_BEFORE - LINES_AFTER )) removed)"
if [ ${BYTES_FREED} -gt 0 ]; then
    echo "Space freed: ~${BYTES_FREED}KB"
fi
if $DRY_RUN; then
    echo ""
    echo "Dry run – nothing deleted. Run without --dry-run to clean up."
fi
