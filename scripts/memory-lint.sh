#!/usr/bin/env bash
# memory-lint.sh — Read-only validator for docs/memory/**
# Schema: ~/.claude/templates/MEMORY_SCHEMA.md
#
# Usage:
#   bash ~/.claude/scripts/memory-lint.sh [<project-dir>]
#
# Exit codes: 0 clean, 1 warnings, 2 errors.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/frontmatter.sh
source "$SCRIPT_DIR/lib/frontmatter.sh"

PROJECT_DIR="${1:-$(pwd)}"
MEMORY_DIR="$PROJECT_DIR/docs/memory"
TIER1_GLOBAL_FILE="$HOME/.claude/instincts.md"
TIER1_GLOBAL_TOPIC_DIR="$HOME/.claude/instincts"
TIER1_GLOBAL_ARCHIVE="$HOME/.claude/instincts-archive/HISTORY.md"
TIER2_GLOBAL_DIR="$HOME/.claude/memory"
STALE_DAYS=90

# Tier-1-global size thresholds (soft cap → warn, hard cap → err).
# 50 KB target keeps the file load-able as session-start context without dominating the budget.
# 100 KB hard cap signals enforced cleanup or persona-silo migration.
# Caps apply to the flat layout; in the split layout the index stays small and
# the topic-file cap (TIER1_TOPIC_*_KB below) is the relevant ceiling.
TIER1_GLOBAL_WARN_KB=50
TIER1_GLOBAL_ERR_KB=100

# Tier-1-global topic-file thresholds (split layout only).
# A topic file holding full Rule/Why/How per theme should stay below 30 KB
# (~6-8 instincts at the current verbosity). Above 50 KB consider splitting
# the theme further or migrating persona-specific entries to Tier-2-global.
TIER1_TOPIC_WARN_KB=30
TIER1_TOPIC_ERR_KB=50

# Skeleton-silo threshold: MEMORY.md with less than N bytes after frontmatter AND
# no topic files in the same directory is treated as a likely skeleton.
SKELETON_BYTES_WARN=400

TODAY_EPOCH=$(date +%s)

declare -a errors warnings infos
errors=()
warnings=()
infos=()

err()  { errors+=("$1"); }
warn() { warnings+=("$1"); }
info() { infos+=("$1"); }

# Date DD.MM.YYYY → epoch (BSD and GNU date compatible).
date_to_epoch() {
    local d="$1"
    # BSD date (macOS): date -j -f "%d.%m.%Y" "$d" "+%s"
    # GNU date: date -d "$(echo $d | awk -F. '{print $3"-"$2"-"$1}')" "+%s"
    if date -j -f "%d.%m.%Y" "$d" "+%s" 2>/dev/null; then
        return 0
    fi
    local iso
    iso="$(printf '%s' "$d" | awk -F. '{print $3"-"$2"-"$1}')"
    date -d "$iso" "+%s" 2>/dev/null || echo "0"
}

FILES=()
if [[ -d "$MEMORY_DIR" ]]; then
    # Collect all .md files under docs/memory/, exclude MEMORY.md (indexes have no frontmatter)
    while IFS= read -r line; do
        FILES+=("$line")
    done < <(find "$MEMORY_DIR" -type f -name "*.md" \
        -not -name "MEMORY.md" \
        -not -name "instincts.md")
else
    info "no docs/memory/ structure under $PROJECT_DIR (project-scope checks skipped)"
fi

FILES_TOTAL=${#FILES[@]}

for file in "${FILES[@]:-}"; do
    [[ -n "$file" ]] || continue
    rel="${file#$PROJECT_DIR/}"

    # (a) Frontmatter present?
    if ! fm_has "$file"; then
        err "$rel — no YAML frontmatter (---) at start of file"
        continue
    fi

    # (b) Required fields
    missing="$(fm_validate_required "$file" "name,description,type,last_updated" || true)"
    if [[ -n "$missing" ]]; then
        while IFS= read -r m; do
            err "$rel — required field missing: $m"
        done <<< "$missing"
    fi

    # (c) type enum
    type_val="$(fm_field "$file" type || true)"
    case "$type_val" in
        feedback|project|reference|user|"") ;;
        *) err "$rel — type='$type_val' is not in {feedback,project,reference,user}" ;;
    esac

    # (d) Tier 1 naming convention: {type}_{slug}.md
    parent_dir="$(basename "$(dirname "$file")")"
    if [[ "$parent_dir" == "memory" ]]; then
        # Tier 1 — filename must start with type_
        basename_file="$(basename "$file")"
        if [[ -n "$type_val" && "$basename_file" != "${type_val}_"* ]]; then
            warn "$rel — Tier-1 naming convention: expected '${type_val}_<slug>.md', got '$basename_file'"
        fi
    fi

    # (e) Stale detection: last_updated older than 90 days
    last_updated="$(fm_field "$file" last_updated || true)"
    if [[ -n "$last_updated" ]]; then
        epoch="$(date_to_epoch "$last_updated")"
        if [[ "$epoch" != "0" && -n "$epoch" ]]; then
            age_days=$(( (TODAY_EPOCH - epoch) / 86400 ))
            if (( age_days > STALE_DAYS )); then
                status_val="$(fm_field "$file" status || true)"
                if [[ "$status_val" != "archived" && "$status_val" != "superseded" ]]; then
                    warn "$rel — last_updated=$last_updated is ${age_days} days old (>${STALE_DAYS}d) — consider setting status='stale'"
                fi
            fi
        else
            err "$rel — last_updated='$last_updated' cannot be parsed as DD.MM.YYYY"
        fi
    fi

    # (f) related: cross-refs pointing to existing files
    base_dir="$(dirname "$file")"
    while IFS= read -r rel_entry; do
        [[ -z "$rel_entry" ]] && continue
        if [[ ! -f "$base_dir/$rel_entry" ]]; then
            err "$rel — related:'$rel_entry' points to non-existent file ($base_dir/$rel_entry)"
        fi
    done < <(fm_list "$file" related)
done

# (g) MEMORY.md index consistency: every Tier-1 file referenced in the index?
TIER1_INDEX="$MEMORY_DIR/MEMORY.md"
if [[ -f "$TIER1_INDEX" && $FILES_TOTAL -gt 0 ]]; then
    for file in "${FILES[@]}"; do
        parent_dir="$(basename "$(dirname "$file")")"
        if [[ "$parent_dir" == "memory" ]]; then
            basename_file="$(basename "$file")"
            if ! grep -qF "$basename_file" "$TIER1_INDEX"; then
                warn "docs/memory/MEMORY.md — file '$basename_file' not referenced in Tier-1 index"
            fi
        fi
    done
fi

# (h) Tier-1-global size cap — ~/.claude/instincts.md must not balloon.
# Drift signal: persona-specific entries leak into global; cleanup or migration needed.
if [[ -f "$TIER1_GLOBAL_FILE" ]]; then
    size_bytes=$(wc -c < "$TIER1_GLOBAL_FILE" | tr -d ' ')
    size_kb=$(( size_bytes / 1024 ))
    if (( size_bytes > TIER1_GLOBAL_ERR_KB * 1024 )); then
        err "~/.claude/instincts.md — ${size_kb} KB exceeds hard cap (${TIER1_GLOBAL_ERR_KB} KB). Migrate persona-specific entries to ~/.claude/memory/{agent}/instincts.md, then prune confirmed-stable entries via /postmortem."
    elif (( size_bytes > TIER1_GLOBAL_WARN_KB * 1024 )); then
        warn "~/.claude/instincts.md — ${size_kb} KB exceeds soft cap (${TIER1_GLOBAL_WARN_KB} KB). Consider migrating persona-specific entries to ~/.claude/memory/{agent}/."
    fi
fi

# (i) Tier-2-global silos — validate schema for ~/.claude/memory/{agent}/*.md.
if [[ -d "$TIER2_GLOBAL_DIR" ]]; then
    while IFS= read -r gfile; do
        grel="${gfile#$HOME/}"
        gbase="$(basename "$gfile")"
        # MEMORY.md indexes have no frontmatter — skip
        [[ "$gbase" == "MEMORY.md" ]] && continue

        if ! fm_has "$gfile"; then
            err "~/${grel} — Tier-2-global file without YAML frontmatter"
            continue
        fi

        # scope: tier-2-global is the new convention marker
        gscope="$(fm_field "$gfile" scope || true)"
        if [[ "$gscope" != "tier-2-global" ]]; then
            warn "~/${grel} — Tier-2-global file should declare 'scope: tier-2-global' (found: '${gscope:-none}')"
        fi

        # agent: matches parent directory name
        gagent="$(fm_field "$gfile" agent || true)"
        expected_agent="$(basename "$(dirname "$gfile")")"
        if [[ -n "$gagent" && "$gagent" != "$expected_agent" ]]; then
            warn "~/${grel} — agent='${gagent}' does not match parent directory '${expected_agent}'"
        elif [[ -z "$gagent" ]]; then
            warn "~/${grel} — missing 'agent:' field (should be '${expected_agent}')"
        fi
    done < <(find "$TIER2_GLOBAL_DIR" -type f -name "*.md" 2>/dev/null)
fi

# (j) Skeleton-silo detection — project Tier-2 silos with empty MEMORY.md and no topic files.
# Be conservative: short MEMORY.md WITH topic files is fine (compact silo, not a skeleton).
# Only flag when MEMORY.md is the only file AND its body is below the threshold.
if [[ -d "$MEMORY_DIR" ]]; then
    for memdir in "$MEMORY_DIR"/*/; do
        [[ -d "$memdir" ]] || continue
        silo="$(basename "${memdir%/}")"
        silo_memory="${memdir%/}/MEMORY.md"
        [[ -f "$silo_memory" ]] || continue

        topic_count=$(find "$memdir" -maxdepth 1 -type f -name "*.md" ! -name "MEMORY.md" 2>/dev/null | wc -l | tr -d ' ')
        if (( topic_count > 0 )); then
            continue
        fi

        # MEMORY.md only — measure body size after the closing frontmatter marker.
        body_bytes=0
        if fm_has "$silo_memory"; then
            # Find second '---' line and count bytes after it
            close_line=$(awk 'NR==1 && $0=="---" {found=1; next} found && $0=="---" {print NR; exit}' "$silo_memory")
            if [[ -n "$close_line" ]]; then
                body_bytes=$(tail -n +$((close_line + 1)) "$silo_memory" | wc -c | tr -d ' ')
            fi
        else
            body_bytes=$(wc -c < "$silo_memory" | tr -d ' ')
        fi

        if (( body_bytes < SKELETON_BYTES_WARN )); then
            info "docs/memory/${silo}/MEMORY.md — likely skeleton silo (${body_bytes} bytes of body, no topic files). Fill it with real persona-specific patterns or remove the directory."
        fi
    done
fi

# (k) Tier-1-global decay light — count low-confidence instinct entries.
# Heuristic: `**Confidence: 0.X**` headers with X ∈ {3,4} are review candidates after 30 days
# without confirmation. Full decay needs per-section date parsing; this is a tripwire only.
# Covers both layouts: flat (entries in TIER1_GLOBAL_FILE) and split (entries in topic files).
tier1_low_conf_files=()
if [[ -f "$TIER1_GLOBAL_FILE" ]]; then
    tier1_low_conf_files+=("$TIER1_GLOBAL_FILE")
fi
if [[ -d "$TIER1_GLOBAL_TOPIC_DIR" ]]; then
    while IFS= read -r tfile; do
        tier1_low_conf_files+=("$tfile")
    done < <(find "$TIER1_GLOBAL_TOPIC_DIR" -maxdepth 1 -type f -name "*.md" 2>/dev/null)
fi
if (( ${#tier1_low_conf_files[@]} > 0 )); then
    low_conf=$(grep -chE '^\*\*Confidence: 0\.[34]\*\*' "${tier1_low_conf_files[@]}" 2>/dev/null | paste -sd+ - | bc 2>/dev/null || true)
    low_conf=${low_conf:-0}
    if (( low_conf > 0 )); then
        if [[ -d "$TIER1_GLOBAL_TOPIC_DIR" ]]; then
            info "Tier-1-global — ${low_conf} entries at Confidence ≤ 0.4 across ~/.claude/instincts.md + ~/.claude/instincts/*.md (review candidates if older than ${STALE_DAYS:-30}d without confirmation; full decay check belongs in /postmortem)."
        else
            info "~/.claude/instincts.md — ${low_conf} entries at Confidence ≤ 0.4 (review candidates if older than ${STALE_DAYS:-30}d without confirmation; full decay check belongs in /postmortem)."
        fi
    fi
fi

# (l) Tier-1-global split-layout — schema + size for ~/.claude/instincts/*.md topic files.
# Only runs when the split-layout directory exists. Each topic file must declare
# `type: instincts` and `scope: tier-1-global-topic`. Size cap per file is independent
# of the index cap above.
if [[ -d "$TIER1_GLOBAL_TOPIC_DIR" ]]; then
    topic_total=0
    while IFS= read -r tfile; do
        topic_total=$((topic_total + 1))
        trel="${tfile#$HOME/}"

        if ! fm_has "$tfile"; then
            err "~/${trel} — Tier-1-global topic file without YAML frontmatter"
            continue
        fi

        ttype="$(fm_field "$tfile" type || true)"
        if [[ "$ttype" != "instincts" ]]; then
            warn "~/${trel} — Tier-1-global topic file should declare 'type: instincts' (found: '${ttype:-none}')"
        fi

        tscope="$(fm_field "$tfile" scope || true)"
        if [[ "$tscope" != "tier-1-global-topic" ]]; then
            warn "~/${trel} — Tier-1-global topic file should declare 'scope: tier-1-global-topic' (found: '${tscope:-none}')"
        fi

        # Per-file size cap
        topic_bytes=$(wc -c < "$tfile" | tr -d ' ')
        topic_kb=$(( topic_bytes / 1024 ))
        if (( topic_bytes > TIER1_TOPIC_ERR_KB * 1024 )); then
            err "~/${trel} — ${topic_kb} KB exceeds Tier-1-global topic hard cap (${TIER1_TOPIC_ERR_KB} KB). Split the theme further (e.g. orchestration vs briefing-discipline) or migrate persona-specific entries to ~/.claude/memory/{agent}/."
        elif (( topic_bytes > TIER1_TOPIC_WARN_KB * 1024 )); then
            warn "~/${trel} — ${topic_kb} KB exceeds Tier-1-global topic soft cap (${TIER1_TOPIC_WARN_KB} KB). Consider further theme split or persona-silo migration."
        fi
    done < <(find "$TIER1_GLOBAL_TOPIC_DIR" -maxdepth 1 -type f -name "*.md" 2>/dev/null)

    if (( topic_total == 0 )); then
        info "~/.claude/instincts/ exists but contains no *.md topic files (split layout incomplete — fill it or remove the directory)."
    fi

    # (m) Archive presence — split layout without the archive is unusual but not fatal.
    if [[ ! -f "$TIER1_GLOBAL_ARCHIVE" ]]; then
        info "~/.claude/instincts-archive/HISTORY.md missing in a split layout — /postmortem expects to append the verbose narrative there. Create it or accept that postmortem history will accumulate elsewhere."
    fi
fi

# Report
NOW="$(date '+%d.%m.%Y %H:%M')"
echo "# Memory Lint Report"
echo
echo "**Scope:** $PROJECT_DIR/docs/memory/**"
echo "**Run:** $NOW"
echo "**Files scanned:** $FILES_TOTAL"
echo

echo "## Errors (${#errors[@]})"
echo
if [[ ${#errors[@]} -eq 0 ]]; then echo "_none_"; fi
for e in "${errors[@]:-}"; do [[ -n "$e" ]] && echo "- $e"; done
echo

echo "## Warnings (${#warnings[@]})"
echo
if [[ ${#warnings[@]} -eq 0 ]]; then echo "_none_"; fi
for w in "${warnings[@]:-}"; do [[ -n "$w" ]] && echo "- $w"; done
echo

echo "## Info (${#infos[@]})"
echo
if [[ ${#infos[@]} -eq 0 ]]; then echo "_none_"; fi
for i in "${infos[@]:-}"; do [[ -n "$i" ]] && echo "- $i"; done
echo

echo "---"
echo
echo "**Summary:** ${#errors[@]} errors, ${#warnings[@]} warnings, ${#infos[@]} info."

if (( ${#errors[@]} > 0 )); then
    echo "**Exit:** 2"
    exit 2
elif (( ${#warnings[@]} > 0 )); then
    echo "**Exit:** 1"
    exit 1
fi
echo "**Exit:** 0"
exit 0
