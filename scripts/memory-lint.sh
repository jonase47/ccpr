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
# Ships as `warn`. This check's extraction used to have two known gaps —
# fenced/inline code examples were false positives, and reference-style links
# were not seen at all — which is why the default started at `warn`: erroring
# on an incomplete extraction would have been a bet on completeness that was
# not backed by evidence. Both named gaps were closed (a838a1f), and the
# default was promoted to `err` on that basis (e241ae3, WI-0005, ADR-0001).
# The promotion was reverted (WI-0005 round 3, 19.08.2026): closing those two
# gaps did not converge on completeness — three further extraction gaps
# surfaced or were found while closing them (WI-0029, WI-0032, WI-0034) plus
# one false positive found and fixed in the same round (backtick pairing by
# run length, not position). The evidence for completeness is weaker now than
# at promotion time, not stronger. Re-promote once WI-0029/WI-0032/WI-0034 are
# closed and no new gap has surfaced in the round that closes them.
# Overridable from the environment so both values can be exercised without editing
# this file, and to let a caller opt into treating a dead index link as a hard
# failure ahead of the default flip; the assignment below is the single place
# that decides the default.
MEMORY_INDEX_LINK_SEVERITY="${MEMORY_INDEX_LINK_SEVERITY:-warn}"

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
#
# Scope (WI-0040): the Tier-1 index plus every Tier-2 persona index
# (docs/memory/{agent}/MEMORY.md). A persona index carries far more links than
# the Tier-1 one — deep anchors into topic files, one per review/implementation
# round — and nothing validated those before this. This is the floor only: it
# catches a target FILE that does not exist, not a wrong anchor into a file that
# does (that needs heading-to-slug modelling and is a separate, unbuilt item).
INDEX_FILES=()
if [[ -f "$TIER1_INDEX" ]]; then
    INDEX_FILES+=("$TIER1_INDEX")
fi
if [[ -d "$MEMORY_DIR" ]]; then
    while IFS= read -r persona_index; do
        INDEX_FILES+=("$persona_index")
    done < <(find "$MEMORY_DIR" -mindepth 2 -maxdepth 2 -type f -name "MEMORY.md" | sort)
fi

for INDEX_FILE in "${INDEX_FILES[@]:-}"; do
    [[ -n "$INDEX_FILE" ]] || continue
    index_rel="${INDEX_FILE#$PROJECT_DIR/}"
    index_dir="$(dirname "$INDEX_FILE")"

    while IFS= read -r target; do
        [[ -n "$target" ]] || continue
        # The awk program's END block reports an unclosed fence (WI-0032) or an
        # unclosed HTML comment (WI-0043) as its own sentinel line, not as a
        # dead-target candidate — a control character no real link target can
        # start with marks each one, and the two are distinct so the report names
        # which construct actually swallowed the rest of the file. Report it as a
        # warning and move on before any of the target-normalisation logic below
        # runs on it.
        case "$target" in
            $'\x02'*)
                warn "$index_rel — line ${target#?} opens a code fence that is never closed; link checking stopped there for the rest of the file"
                continue
                ;;
            $'\x04'*)
                warn "$index_rel — line ${target#?} opens an HTML comment that is never closed; link checking stopped there for the rest of the file"
                continue
                ;;
        esac
        # Trim whitespace around the target: `[x]( a.md )` addresses `a.md`.
        target="${target#"${target%%[![:space:]]*}"}"
        target="${target%"${target##*[![:space:]]}"}"
        # A title after the target (`[x](a.md "Title")`) is not part of the path, but
        # only a genuine quoted suffix is one — a bare space is no delimiter, so
        # `[x](my file.md)` keeps its space instead of collapsing to `my`. All three
        # CommonMark title delimiters are stripped here (WI-0034): double quotes,
        # single quotes and parentheses. This case must stay in agreement with
        # reference_definition_tail() above — recognising a parenthesised title as
        # a valid reference definition without also stripping it here would leave
        # the title text glued to the checked target, turning a live file into a
        # reported-dead one.
        case "$target" in
            *[[:space:]]\"*\") target="${target%[[:space:]]\"*}" ;;
            *[[:space:]]\'*\') target="${target%[[:space:]]\'*}" ;;
            *[[:space:]]\(*\)) target="${target%[[:space:]]\(*}" ;;
        esac
        target="${target%"${target##*[![:space:]]}"}"
        # Skip external schemes, in-page anchors and the angle-bracket form.
        case "$target" in
            http://*|https://*|mailto:*|\#*|\<*) continue ;;
        esac
        # `a.md#section` addresses the file a.md — drop the fragment before resolving.
        target="${target%%#*}"
        [[ -n "$target" ]] || continue
        # Targets resolve relative to the CURRENT index's own directory, as in check
        # (f) — a persona index's relative links address its own silo, not the Tier-1
        # memory dir (WI-0040). Exception: a leading `/` is repo-root-relative — the
        # usual convention in a docs tree rendered from the repository root. Chosen
        # over "report as unsupported" because the form has a single unambiguous
        # meaning inside a project and stays checkable. Treating it as a
        # filesystem-absolute path would leave the project entirely; the previous
        # concatenation produced a doubled path (`docs/memory//docs/memory/x.md`)
        # that can never exist.
        case "$target" in
            /*) resolved="$PROJECT_DIR$target" ;;
            *)  resolved="$index_dir/$target" ;;
        esac
        # A trailing slash already forces directory semantics: POSIX pathname
        # resolution rejects `regularfile/`, so `-e` is false for it and true for a
        # directory. A separate `*/` → `-d` branch was therefore dead code — no test
        # could distinguish it, which is exactly what the mutation run showed.
        if [[ -e "$resolved" ]]; then
            continue
        fi
        link_finding="$index_rel — link target '$target' does not exist ($resolved)"
        # Dispatch by value — never expand the knob in command position (see the
        # validation at the top of this file).
        case "$MEMORY_INDEX_LINK_SEVERITY" in
            err)  err  "$link_finding" ;;
            warn) warn "$link_finding" ;;
        esac
    done < <(awk '
        # Strip HTML-comment spans before extracting links: parking a retired entry
        # in `<!-- ... -->` is ordinary index practice and must not be linted.
        #
        # WI-0050: a mid-line comment opener is resolved against its own
        # PARAGRAPH, not against the whole file. CommonMark HTML block type 2
        # only applies when a comment OPENS the line (handled separately below,
        # in_html_comment); a comment that opens mid-line is inline raw HTML, and
        # whether it swallows anything depends on whether it closes before the
        # paragraph ends. Three measured shapes (WI-0050 comment, 20.08.2026):
        # a list item never lets a mid-line opener cross into the next item (each
        # item is its own block); a plain paragraph DOES let it cross into a
        # later line of the SAME paragraph, if the closer is there; and an
        # opener that never closes before the paragraph ends is literal text,
        # nothing is discarded. append_paragraph()/flush_paragraph() below buffer
        # the current paragraph across physical lines and hand the whole thing
        # to decomment_paragraph() in one call, so lookahead is bounded to one
        # paragraph and never reaches past a block boundary (blank line, list
        # marker, heading, fence, or a block-level HTML comment).
        #
        # A closed comment is replaced by one `boundary` character rather than by
        # nothing (WI-0029). CommonMark treats an inline HTML comment as its own
        # node in the inline sequence: it does not fuse the text before it with
        # the text after it. Concatenating the two sides directly used to forge
        # syntax the author never wrote — text ending in `!` immediately before a
        # comment, immediately followed by `[`, collapsed into a literal `![`
        # image marker, and the link after it was skipped as an image and never
        # checked. `boundary` is inert for every other regex in this script (not
        # `[`, `]`, `(`, `)`, a backtick, `!`, a quote or whitespace), so it only
        # ever breaks an accidental adjacency — it does not introduce one.
        # dest_mark wraps a link destination that protect_link_destinations()
        # has already isolated (WI-0042): CommonMark link-destination grammar
        # is not inline-parsed, so a `<!--...-->` sequence inside `[x](dest)`
        # is literal text, not a comment to strip. A dest_mark..dest_mark span
        # is therefore copied through untouched here rather than scanned for
        # `<!--`/`-->` — the two sentinels are stripped again once the
        # destination has been extracted (strip_dest_mark()). This only ever
        # protects a destination; comment text in a link LABEL is ordinary
        # inline content and keeps being decommented below, unchanged.
        #
        # local_in_comment is declared as a function parameter (an awk local),
        # not read from a bare global name — that undeclared-global mistake is
        # exactly WI-0050s defect: the old decomment() used a bare `in_comment`,
        # which awk makes GLOBAL by default, so an opener with no closer on its
        # own record left the state set and swallowed every following record
        # (line) until a `-->` turned up or the file ended. A fresh local per
        # call means a paragraph that never closes its opener cannot leak
        # anything into the next paragraph, or the next file.
        function decomment_paragraph(s,   a, b, w, e, out, local_in_comment) {
            out = ""
            local_in_comment = 0
            while (length(s) > 0) {
                if (local_in_comment) {
                    b = index(s, "-->")
                    if (b == 0) {
                        # Unclosed within this paragraph — literal text, per the
                        # PO decision of 20.08.2026: nothing is discarded. Restore
                        # the opener that was already consumed below and stop;
                        # the remainder of s is untouched raw content.
                        out = out "<!--" s
                        return out
                    }
                    s = substr(s, b + 3)
                    local_in_comment = 0
                    out = out boundary
                    continue
                }
                w = index(s, dest_mark)
                a = index(s, "<!--")
                if (w > 0 && (a == 0 || w < a)) {
                    e = index(substr(s, w + 1), dest_mark)
                    if (e == 0) return out s   # malformed guard — should not happen
                    out = out substr(s, 1, w + e)
                    s = substr(s, w + e + 1)
                    continue
                }
                if (a == 0) return out s
                out = out substr(s, 1, a - 1)
                s = substr(s, a + 4)
                local_in_comment = 1
            }
            return out
        }
        # Isolates every inline link destination — the `(...)` immediately
        # after `](` — and wraps its raw text in dest_mark before decomment()
        # or strip_inline_code() ever see it (WI-0042). Riding the raw text
        # along inside the normal `line` flow, instead of re-locating it
        # afterward from a parallel scan, keeps it structurally glued to
        # whichever `[text](dest)` span it belongs to — including when that
        # whole span later turns out to be inside a code span or an
        # illustrative backtick example and gets discarded as a unit.
        function protect_link_destinations(s,    out, dest) {
            out = ""
            while (match(s, /\]\([^)]*\)/)) {
                out = out substr(s, 1, RSTART + 1)   # up through and including the ]( pair
                dest = substr(s, RSTART + 2, RLENGTH - 3)
                out = out dest_mark dest dest_mark ")"
                s = substr(s, RSTART + RLENGTH)
            }
            return out s
        }
        function strip_dest_mark(s) {
            gsub(dest_mark, "", s)
            return s
        }
        # Strip inline code spans (`code`, ``code with a ` in it``): a span never
        # crosses a line in Markdown, so unlike decomment() this needs no state
        # across records. An index documenting its own link syntax inline
        # (`` `[x](dead.md)` ``) illustrates the syntax; it is not an entry.
        #
        # CommonMark pairs by *run length*, not by position: a code span opens
        # with a backtick run of length N and closes at the next run of exactly
        # length N — a run of a different length is skipped over as content, and
        # a run with no same-length partner anywhere ahead is literal text, not
        # an opener (mirrors the fence rule above, except a fence closes on
        # length >= opener while a code span closes on length == opener). A
        # naive 1st-backtick-pairs-with-2nd-backtick scan gets this wrong in two
        # ways: it can pair mismatched run lengths (misreading a lone backtick
        # inside a double-backtick span as that spans closer), and, chained from
        # that, later runs on the same line inherit the wrong offset.
        #
        # WI-0050 keeps this scoped to one paragraph-buffer SEGMENT at a time
        # (see process_link_line() below), the same scope it always ran at —
        # a segment can now be the tail of a comment-joined multi-line span
        # instead of a single raw physical line, but this function itself is
        # unchanged and still never looks past what it is handed.
        function strip_inline_code(s,   out, i, n, run_start, run_len, c, j, close_len, found) {
            out = ""
            n = length(s)
            i = 1
            while (i <= n) {
                c = substr(s, i, 1)
                if (c != "`") {
                    out = out c
                    i++
                    continue
                }
                run_start = i
                run_len = 0
                while (i <= n && substr(s, i, 1) == "`") {
                    run_len++
                    i++
                }
                found = 0
                j = i
                while (j <= n) {
                    if (substr(s, j, 1) != "`") {
                        j++
                        continue
                    }
                    close_len = 0
                    while (j <= n && substr(s, j, 1) == "`") {
                        close_len++
                        j++
                    }
                    if (close_len == run_len) {
                        found = 1
                        break
                    }
                    # A run of a different length is content — not a closer for
                    # this opener, and not a new opener either (that only
                    # happens once we return to the outer loop). Keep scanning
                    # forward for a same-length run without advancing `i`.
                }
                if (found) {
                    i = j   # discard opener..closer, resume right after the closer
                } else {
                    out = out substr(s, run_start, run_len)   # unpaired run — literal
                    # `i` already sits right after the opening run; resume there
                    # instead of dropping the rest of the line (see fix 3, a838a1f).
                }
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
            if (match(d, /^\([^)]*\)[ \t]*$/)) return 1
            return 0
        }
        # Runs the extraction that used to sit directly in the main record
        # block: find every `[text](dest)` span left after decommenting and
        # code-span stripping, and print the destination unless it is an
        # image marker (`![...]`, WI-0029). Factored out unchanged (WI-0050)
        # so flush_paragraph() can call it once per resolved segment.
        function process_link_line(line,   prev, link, sep) {
            prev = ""
            while (match(line, /\[[^][]*\]\([^)]*\)/)) {
                if (RSTART > 1) prev = substr(line, RSTART - 1, 1)
                link = substr(line, RSTART, RLENGTH)
                sep = index(link, "](")
                # `![alt](src)` is an image, not an index entry.
                if (prev != "!") print strip_dest_mark(substr(link, sep + 2, length(link) - sep - 2))
                line = substr(line, RSTART + RLENGTH)
                prev = ")"
            }
        }
        # Buffers one physical line into the current paragraph. protect_link_
        # destinations() runs here, per raw line, exactly where it always ran —
        # only decomment() moved to paragraph scope, this did not.
        function append_paragraph(raw_line) {
            if (pbuf_n == 0) pbuf = protect_link_destinations(raw_line)
            else pbuf = pbuf "\n" protect_link_destinations(raw_line)
            pbuf_n++
        }
        # Resolves the buffered paragraph and extracts its links, then clears
        # the buffer. Joining with a real newline before decomment_paragraph()
        # and splitting on the same character afterward means a comment span
        # that closes on a later line collapses the lines it swallowed into one
        # segment (its newlines were inside the removed span), while a span
        # that never closes leaves every original line boundary intact — no
        # extra bookkeeping needed to tell the two cases apart. strip_inline_
        # code() and process_link_line() still run once per resulting segment,
        # same as they always ran once per physical line, so a code span still
        # cannot cross what was a paragraph-internal line break — a scope
        # decision this fix inherits, not one it makes (out of scope, see
        # WI-0050 and WI-0048).
        function flush_paragraph(   resolved, segments, seg_count, i) {
            if (pbuf_n == 0) return
            resolved = decomment_paragraph(pbuf)
            seg_count = split(resolved, segments, "\n")
            for (i = 1; i <= seg_count; i++) {
                process_link_line(strip_inline_code(segments[i]))
            }
            pbuf = ""
            pbuf_n = 0
        }
        BEGIN {
            sq = sprintf("%c", 39)
            boundary = sprintf("%c", 1)
            fence_sentinel = sprintf("%c", 2)
            dest_mark = sprintf("%c", 3)
            html_comment_sentinel = sprintf("%c", 4)
            pbuf = ""
            pbuf_n = 0
        }
        {
            # A fenced code block (```…``` or ~~~…~~~, optionally indented up to 3
            # spaces per CommonMark) is skipped wholesale: an index illustrating its
            # own link syntax inside a fenced example is not a set of live entries.
            # A fence only closes with its own delimiter character, at least as long
            # as the opener — fence_char/fence_len carry that across lines, so a
            # `~~~` inside an open backtick fence stays content, not a close.
            if (in_fence) {
                if (match($0, "^[ ]{0,3}" fence_char "{" fence_len ",}[ \t]*$")) {
                    in_fence = 0
                    fence_char = ""
                    fence_len = 0
                }
                next
            }
            # Gated on !in_html_comment (WI-0045): a line that merely LOOKS like a
            # fence opener while an HTML comment is already open must not set
            # in_fence — otherwise the comments own closing line is caught by the
            # in_fence branch above on the NEXT record and never reaches the
            # comment-close check below, leaving in_html_comment set forever. The
            # reverse direction needs no such gate: `if (in_fence)` above already
            # runs first and unconditionally `next`s, so nothing inside a real
            # fence is ever offered to the comment-opener check.
            #
            # A fence opener is itself a block boundary, so it flushes whatever
            # paragraph was being buffered — the opener substring is read out of
            # $0 via RSTART/RLENGTH BEFORE the flush, because flush_paragraph()
            # runs process_link_line(), which calls match() itself and would
            # otherwise clobber them.
            if (!in_html_comment && match($0, /^[ ]{0,3}(```+|~~~+)/)) {
                opener = substr($0, RSTART, RLENGTH)
                sub(/^[ ]{0,3}/, "", opener)
                flush_paragraph()
                fence_char = substr(opener, 1, 1)
                fence_len = length(opener)
                in_fence = 1
                fence_open_line = NR
                next
            }

            # An HTML comment that opens a line (after <=3 leading spaces) is
            # CommonMark HTML block type 2, not an inline comment: the WHOLE
            # physical line is raw HTML, including any text after the closing
            # `-->` on that same line, and every full line up to and including
            # the one that finally contains `-->` (WI-0041). This is a
            # different mechanism from the paragraph-scoped state decomment_
            # paragraph() resolves below, which only ever applies to a comment
            # that does NOT open its line.
            # Checked here, before the paragraph is flushed to decomment_
            # paragraph(), so a link written on the closing line of the block is
            # never even offered to the extractor — mirrors the fence handling
            # one block up. A block comment that never closes swallows the rest
            # of the file exactly like an unclosed fence (the WI-0032 mechanism);
            # html_comment_open_line feeds the same end-of-input sentinel
            # reporting that gives (WI-0043). Fence and HTML-comment states
            # cannot both be open at the same time: the fence-opener check just
            # above is gated on !in_html_comment, and the in_fence branch above
            # THAT already runs first and unconditionally `next`s once a fence
            # is open — so there is exactly one sentinel to report, not two.
            # That is a property this gate establishes, not one that held on
            # its own.
            # NOTE: no apostrophes in this awk block — memory-lint.sh embeds it as
            # one single-quoted bash string, and an unescaped apostrophe silently
            # truncates the program (WI-0005 round 3; see awk-scripting.md).
            if (in_html_comment) {
                if ($0 ~ /-->/) in_html_comment = 0
                next
            }
            if (match($0, /^[ ]{0,3}<!--/)) {
                flush_paragraph()
                if ($0 !~ /-->/) {
                    in_html_comment = 1
                    html_comment_open_line = NR
                }
                next
            }

            # Reference-style link definition: `[id]: target "optional title"`.
            # The one-line form `[x](target)` this check already handled leaves
            # `[x][id]` + a separate `[id]: target` definition line unseen — same
            # defect class, one syntax further. Checked directly against the RAW
            # line, before the paragraph flow ever sees it (WI-0042): a
            # reference-definition destination is not inline-parsed by
            # CommonMark, so a comment inside it is literal text, not something
            # to strip — printing the raw remainder verbatim keeps it that way.
            # Target normalisation (whitespace, quoted-title stripping) happens
            # uniformly on the shell side below. A genuine reference definition
            # is its own block, so it flushes whatever paragraph was buffered;
            # raw_rest is read out via RSTART/RLENGTH before that flush, for the
            # same reason the fence-opener branch above reads its own substring
            # first.
            if (match($0, /^[ ]{0,3}\[[^][]+\]:[ \t]*/)) {
                raw_rest = substr($0, RSTART + RLENGTH)
                if (reference_definition_tail(raw_rest)) {
                    flush_paragraph()
                    print raw_rest
                    next
                }
                # Not a valid reference definition — fall through so a real
                # `[x](y)` link elsewhere on this line is still found below.
            }

            # WI-0050 block boundaries: a blank line, a list-item marker or a
            # heading each end the current paragraph the way CommonMark ends
            # a block. This is deliberately not a full CommonMark block
            # grammar — a thematic break (`---` with no following list-marker
            # space) is not recognised as a boundary here, and neither is a
            # setext-heading underline; both fall through to the ordinary
            # content branch below and stay inside whatever paragraph is being
            # buffered, same as they always did (out of scope, see the
            # senior-developer report for WI-0050).
            #
            # A blank line closes the paragraph and carries no content of its
            # own.
            if ($0 ~ /^[ \t]*$/) {
                flush_paragraph()
                next
            }
            # An ATX heading (`#` through `######`) is always exactly one line
            # in CommonMark, so it flushes immediately after buffering itself —
            # it never accumulates a continuation line the way a list item can.
            if ($0 ~ /^[ ]{0,3}#{1,6}([ \t]|$)/) {
                flush_paragraph()
                append_paragraph($0)
                flush_paragraph()
                next
            }
            # A list-item marker starts a new block, but unlike a heading it
            # may run on to further lines (a wrapped list item is still one
            # block) — flush whatever came before, then keep buffering from
            # here until the next boundary.
            if ($0 ~ /^[ ]{0,3}([-+*]|[0-9]{1,9}[.)])[ \t]/) {
                flush_paragraph()
                append_paragraph($0)
                next
            }
            # Ordinary paragraph content — accumulate, do not resolve yet.
            append_paragraph($0)
        }
        # A fence or an HTML comment still open at end-of-input runs to
        # end-of-document — correct CommonMark (WI-0032 for the fence, WI-0041 for
        # the comment), so the skip itself is unchanged in either case. What was
        # silent is the failure MODE: a stray opener disables link checking for the
        # whole remainder of the file with nothing said (WI-0043 for the comment
        # case). Emit one sentinel line, marked with a control character no real
        # link target can start with, so the shell side can tell it apart from an
        # ordinary dead-target finding and report it as its own warning instead. The
        # two states can never both be open at end-of-input (the fence-opener check
        # above is gated on !in_html_comment, see that comment for why), so at most
        # one of these fires. flush_paragraph() runs first so a paragraph still
        # buffered when the file simply ends (no trailing blank line) is not lost —
        # it cannot coexist with either open state, both of which already flushed
        # the buffer on the way in and never touch it again while open.
        END {
            flush_paragraph()
            if (in_fence) print fence_sentinel fence_open_line
            if (in_html_comment) print html_comment_sentinel html_comment_open_line
        }
    ' "$INDEX_FILE")
done

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
