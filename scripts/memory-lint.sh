#!/usr/bin/env bash
# memory-lint.sh — Read-only validator for docs/memory/**
# Schema: ~/.claude/templates/MEMORY_SCHEMA.md
#
# Usage:
#   bash ~/.claude/scripts/memory-lint.sh [<project-dir>]
#
# Exit codes: 0 clean, 1 warnings, 2 errors, 3 configuration error.
#
# 3 is a *configuration* failure, not a findings result: the run never produced a
# report, so its findings are unknown. It is deliberately distinct from 0/1/2 so a
# caller cannot mistake a misconfigured script for a clean or a failing lint.
# Currently raised by exactly one condition: MEMORY_INDEX_LINK_SEVERITY holds a
# value outside {err,warn}.

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

# Severity of check (n) — dead Markdown links in the Tier-1 index.
# Ships as `err`, matching check (f), which errors on the same defect class (a
# cross-reference to a non-existent file). This check's extraction used to have
# two known gaps — fenced/inline code examples were false positives, and
# reference-style links were not seen at all — which is why the default started
# at `warn`: erroring on an incomplete extraction would have been a bet on
# completeness that was not backed by evidence. Both gaps are closed (a838a1f),
# so the promotion to `err` is the SemVer-relevant step (ADR-0001): it rejects
# previously-accepted content (a dead index link that used to pass with a
# warning now fails the run), so it must be visible, not silent.
# Overridable from the environment so both values can be exercised without editing
# this file, and as a transitional escape hatch (MEMORY_INDEX_LINK_SEVERITY=warn)
# for callers not yet ready to treat a dead index link as a hard failure; the
# assignment below is the single place that decides the default.
MEMORY_INDEX_LINK_SEVERITY="${MEMORY_INDEX_LINK_SEVERITY:-err}"

# Validate the knob before doing any work. The value used to be expanded in command
# position (`"$MEMORY_INDEX_LINK_SEVERITY" "<message>"`), so a typo aborted the run
# with `command not found` and exit 127 — no report, and indistinguishable from a
# findings result for a caller that only checks "non-zero".
case "$MEMORY_INDEX_LINK_SEVERITY" in
    err|warn) ;;
    *)
        printf 'memory-lint.sh: MEMORY_INDEX_LINK_SEVERITY=%s is invalid — expected "err" or "warn".\n' \
            "$MEMORY_INDEX_LINK_SEVERITY" >&2
        exit 3
        ;;
esac

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

    # (c) type enum — tier-aware. Tier 1 (docs/memory/{type}_{slug}.md) keeps the
    # closed content-type enum and errors on drift. Tier-2 persona topic files
    # (docs/memory/{agent}/{topic}.md) have no defined vocabulary in the schema
    # (WI-0008): two personas independently reached for "patterns", a value the
    # Tier-1 enum does not offer, so it is added there. The Tier-2 set stays open —
    # an unrecognised value is a warning, not an error, so an unforeseen but
    # legitimate persona-specific label does not repeat the defect this fixes.
    parent_dir="$(basename "$(dirname "$file")")"
    type_val="$(fm_field "$file" type || true)"
    if [[ "$parent_dir" == "memory" ]]; then
        case "$type_val" in
            feedback|project|reference|user|"") ;;
            *) err "$rel — type='$type_val' is not in {feedback,project,reference,user}" ;;
        esac
    else
        case "$type_val" in
            feedback|project|reference|user|patterns|"") ;;
            *) warn "$rel — type='$type_val' is not in the Tier-2 topic-file enum {feedback,project,reference,user,patterns}" ;;
        esac
    fi

    # (d) Tier 1 naming convention: {type}_{slug}.md
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

# (n) Dead links in the Tier-1 index — the reverse direction of (g).
# (g) finds Tier-1 files the index forgot; this finds index entries whose target is gone.
# Severity is MEMORY_INDEX_LINK_SEVERITY (top of file), mirroring check (f).
if [[ -f "$TIER1_INDEX" ]]; then
    while IFS= read -r target; do
        [[ -n "$target" ]] || continue
        # Trim whitespace around the target: `[x]( a.md )` addresses `a.md`.
        target="${target#"${target%%[![:space:]]*}"}"
        target="${target%"${target##*[![:space:]]}"}"
        # A title after the target (`[x](a.md "Title")`) is not part of the path, but
        # only a genuine quoted suffix is one — a bare space is no delimiter, so
        # `[x](my file.md)` keeps its space instead of collapsing to `my`.
        case "$target" in
            *[[:space:]]\"*\") target="${target%[[:space:]]\"*}" ;;
            *[[:space:]]\'*\') target="${target%[[:space:]]\'*}" ;;
        esac
        target="${target%"${target##*[![:space:]]}"}"
        # Skip external schemes, in-page anchors and the angle-bracket form.
        case "$target" in
            http://*|https://*|mailto:*|\#*|\<*) continue ;;
        esac
        # `a.md#section` addresses the file a.md — drop the fragment before resolving.
        target="${target%%#*}"
        [[ -n "$target" ]] || continue
        # Targets resolve relative to the index's own directory, as in check (f).
        # Exception: a leading `/` is repo-root-relative — the usual convention in a
        # docs tree rendered from the repository root. Chosen over "report as
        # unsupported" because the form has a single unambiguous meaning inside a
        # project and stays checkable. Treating it as a filesystem-absolute path
        # would leave the project entirely; the previous concatenation produced a
        # doubled path (`docs/memory//docs/memory/x.md`) that can never exist.
        case "$target" in
            /*) resolved="$PROJECT_DIR$target" ;;
            *)  resolved="$MEMORY_DIR/$target" ;;
        esac
        # A trailing slash already forces directory semantics: POSIX pathname
        # resolution rejects `regularfile/`, so `-e` is false for it and true for a
        # directory. A separate `*/` → `-d` branch was therefore dead code — no test
        # could distinguish it, which is exactly what the mutation run showed.
        if [[ -e "$resolved" ]]; then
            continue
        fi
        link_finding="docs/memory/MEMORY.md — link target '$target' does not exist ($resolved)"
        # Dispatch by value — never expand the knob in command position (see the
        # validation at the top of this file).
        case "$MEMORY_INDEX_LINK_SEVERITY" in
            err)  err  "$link_finding" ;;
            warn) warn "$link_finding" ;;
        esac
    done < <(awk '
        # Strip HTML-comment spans before extracting links: parking a retired entry
        # in `<!-- ... -->` is ordinary index practice and must not be linted.
        # in_comment carries the state across lines, so comment blocks work too.
        function decomment(s,   a, b, out) {
            out = ""
            while (length(s) > 0) {
                if (in_comment) {
                    b = index(s, "-->")
                    if (b == 0) return out
                    s = substr(s, b + 3)
                    in_comment = 0
                } else {
                    a = index(s, "<!--")
                    if (a == 0) return out s
                    out = out substr(s, 1, a - 1)
                    s = substr(s, a + 4)
                    in_comment = 1
                }
            }
            return out
        }
        # Strip single-backtick inline code spans (`code`): a span never crosses a
        # line in Markdown, so unlike decomment() this needs no state across
        # records. An index documenting its own link syntax inline
        # (`` `[x](dead.md)` ``) illustrates the syntax; it is not an entry.
        function strip_inline_code(s,   out, a, b) {
            out = ""
            while (length(s) > 0) {
                a = index(s, "`")
                if (a == 0) return out s
                out = out substr(s, 1, a - 1)
                s = substr(s, a + 1)
                b = index(s, "`")
                if (b == 0) return out   # unterminated backtick — drop the remainder
                s = substr(s, b + 1)
            }
            return out
        }
        # A reference-style definition destination is either the bracketed
        # `<...>` form (never contains unescaped whitespace) or a bare token that
        # stops at the first whitespace and may not itself start with `<`
        # (CommonMark link-destination grammar). Anything after it must be empty
        # or a quoted title — otherwise the line is not a reference definition at
        # all, just prose that happens to start with `[label]:`.
        function reference_definition_tail(rest,   d) {
            if (match(rest, /^<([^<>]|\\.)*>/)) return 1
            if (!match(rest, /^[^ \t<][^ \t]*/)) return 0
            d = substr(rest, RSTART + RLENGTH)
            sub(/^[ \t]+/, "", d)
            if (d == "") return 1
            if (match(d, /^"[^"]*"[ \t]*$/)) return 1
            if (match(d, "^" sq "[^" sq "]*" sq "[ \t]*$")) return 1
            return 0
        }
        BEGIN { sq = sprintf("%c", 39) }
        {
            # A fenced code block (```…``` or ~~~…~~~, optionally indented up to 3
            # spaces per CommonMark) is skipped wholesale: an index illustrating its
            # own link syntax inside a fenced example is not a set of live entries.
            # in_fence carries the toggle across lines, same shape as in_comment.
            if (match($0, /^[ ]{0,3}(```+|~~~+)/)) {
                in_fence = !in_fence
                next
            }
            if (in_fence) next

            line = strip_inline_code(decomment($0))

            # Reference-style link definition: `[id]: target "optional title"`.
            # The one-line form `[x](target)` this check already handled leaves
            # `[x][id]` + a separate `[id]: target` definition line unseen — same
            # defect class, one syntax further. Target normalisation (whitespace,
            # quoted-title stripping) happens uniformly on the shell side below,
            # so this only has to isolate the target-plus-optional-title substring
            # — after confirming the line really is a reference definition and not
            # ordinary prose that starts with `[Label]:` (a glossary line, say).
            if (match(line, /^[ ]{0,3}\[[^][]+\]:[ \t]*/)) {
                rest = substr(line, RSTART + RLENGTH)
                if (reference_definition_tail(rest)) {
                    print rest
                    next
                }
                # Not a valid reference definition — fall through so a real
                # `[x](y)` link elsewhere on this line is still found below.
            }

            prev = ""
            while (match(line, /\[[^][]*\]\([^)]*\)/)) {
                if (RSTART > 1) prev = substr(line, RSTART - 1, 1)
                link = substr(line, RSTART, RLENGTH)
                sep = index(link, "](")
                # `![alt](src)` is an image, not an index entry.
                if (prev != "!") print substr(link, sep + 2, length(link) - sep - 2)
                line = substr(line, RSTART + RLENGTH)
                prev = ")"
            }
        }
    ' "$TIER1_INDEX")
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
