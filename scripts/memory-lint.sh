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
# value outside {err,warn} — the EMPTY string included, see the `-` rather than
# `:-` on the assignment below.

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

# Grace period quoted by check (k)'s low-confidence decay hint below — the
# instincts.md "Decay policy" itself ("30 days without re-confirmation"), not
# STALE_DAYS above (which belongs to check (e), the unrelated memory-FILE
# staleness warning). Kept as its own name on purpose: the two thresholds are
# independent policies that happen to both be day-counts, and sharing a name
# is exactly what let `${STALE_DAYS:-30}`'s dead fallback go unnoticed
# (WI-0111) — the `:-30` never fired because STALE_DAYS is always assigned.
DECAY_DAYS=30

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
# Ships as `err` since 24.08.2026 (WI-0005, ADR-0001).
#
# It shipped as `warn` for most of its life. Erroring on an extraction with
# known gaps would have been a bet on completeness that was not backed by
# evidence; a promotion made on that bet (e241ae3) was reverted the same week
# (19.08.2026) when closing the two named gaps exposed three more.
#
# The criterion that governed the promotion was then "a round that produces no
# new items". It was replaced on 23.08.2026 by PO decision, because it was
# shown to be unreachable rather than merely unmet: two rounds against ground
# no earlier round had touched produced eighteen divergences, and the construct
# classes were not exhausted. CommonMark is large and an awk extractor will
# always diverge somewhere, so waiting for a quiet round was waiting for
# something that may never arrive.
#
# The criterion in force is narrower and matches the reason ADR-0001 calls this
# step SemVer-relevant at all: promotion REJECTS PREVIOUSLY ACCEPTED CONTENT,
# and only a false positive does that. A false negative rejects nothing and
# breaks no run. So: no known FALSE-POSITIVE divergence.
#
# What satisfied it, measured rather than argued (24.08.2026):
#   - the conformance corpus in scripts/tests/fixtures/ holds 76 entries with
#     ZERO false-positive divergences (12 false negatives and 3 documented_intent
#     remain, and are named there); regenerating it is byte-identical
#   - the field: 18 real index files, 131 link extractions, 0 targets that the
#     reference does not render
#   - the four inventories this framework is run against produce the same
#     findings and the same exit codes with the flip as without it
#
# The caveat, named rather than left to a footnote — WI-0100: a bounded random
# probe over 3000 lines of bracket soup produces 210 findings the reference
# never renders (178 of them already before the WI-0080 scanner). The minimal
# witness is `[](()`, which reports a target named `(`. WI-0095's merge
# comment named this a duplicate of the missing-opener-check gap ("whoever
# fixes this fixes all three"); measured after that gap was closed
# (25.08.2026), it is not — `[]` IS a live, unescaped opener/closer pair, so
# the opener check does not reject it, and `[](()` still reports `(`
# unchanged. The actual cause is separate: the destination-closing scan takes
# the first unescaped `)` as the delimiter without requiring the parens inside
# a destination to balance, which CommonMark's link-destination grammar does
# require for the non-`<>` form. That gap is REACHABLE but not REACHED — no
# such construct occurs in any measured index, which is what the field
# measurement above says and all it says.
#
# CLOSED 26.08.2026 (WI-0118): the destination-closing scan in
# protect_link_destinations() now tracks a paren depth for the unbracketed
# form, so `[](()` no longer invents a target and `[a](b(c)d.md)` resolves to
# its full, balanced destination. The angle-bracket form's own scan is
# untouched. This caveat is left in place, corrected rather than deleted, as
# the record of what the 24.08.2026 promotion actually shipped with.
#
# What this flip is NOT: it makes the check LOUDER, not complete. The false
# negatives stay, named, in the corpus.
#
# The escape hatch is the reason the promotion is defensible for a run it
# catches off guard: MEMORY_INDEX_LINK_SEVERITY=warn restores the old
# behaviour exactly, and that is pinned by a test rather than promised here.
# Overridable from the environment so both values can be exercised without
# editing this file, and so a caller can opt back out of the promotion; the
# assignment below is the single place that decides the default.
#
# `-`, not `:-`: the default applies to an UNSET variable only. Emptying the
# variable is how a caller reaches for "turn this off", and this knob has no off
# position — under `:-` that attempt took the default branch and landed on the
# STRICT side of the promotion it was trying to escape, silently, exit 2. An
# empty string is not a severity, so it falls through to the validation below
# and exits 3 with the reason on stderr.
MEMORY_INDEX_LINK_SEVERITY="${MEMORY_INDEX_LINK_SEVERITY-err}"

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


declare -a errors warnings infos
errors=()
warnings=()
infos=()

err()  { errors+=("$1"); }
warn() { warnings+=("$1"); }
info() { infos+=("$1"); }

# Date DD.MM.YYYY → epoch of that day's UTC midnight, and the shape check
# that runs in front of it, both moved to scripts/lib/frontmatter.sh
# (WI-0107): `fm_date_to_epoch` (was this file's own `date_to_epoch`) and
# `fm_date_shape_ok`. phase-docs-lint.sh's check (e) used to hand-type the
# same shape pattern with no parse behind it, so the two linters answered a
# well-formed-but-impossible date (`32.13.2026`, `99.99.9999`) differently
# — one rule, one shared implementation now, sourced by both.

# "Today" as the same kind of value every file's last_updated is turned into:
# the UTC midnight of the current LOCAL calendar day. Derived through
# fm_date_to_epoch on purpose — a second, independent way of computing this
# end of the subtraction is exactly how the two ends drifted apart before.
TODAY_EPOCH=$(fm_date_to_epoch "$(date +%d.%m.%Y)")

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

    # (c2) status enum — same case-block structure as check (c), but no tier
    # split: `status` describes the file's maintenance state, not its content
    # type, and that vocabulary is identical on both tiers. `stale` used to be
    # a legal value even though it was the ONE value the age warning below
    # (check e) told the reader to set — and setting it did not suppress that
    # warning, so following the check's own advice reproduced the same
    # warning on the very next run (WI-0074). Removed from the enum outright,
    # not added to the suppression list: `archived`/`superseded` legitimately
    # end the warning because they say "intentionally no longer maintained";
    # `stale` only ever said "is old", which was the warning's premise, not
    # an answer to it. Numbered (c2) rather than renumbering every following
    # letter — the letters after (c) are cross-referenced by later comments
    # in this file, and inserting a fresh letter between them would have
    # meant re-deriving and re-checking every one of those references for no
    # behavioural gain.
    #
    # Severity `err` is deliberate, not the schema's looser default: measured
    # directly before this promotion (21.08.2026) — the one schema-foreign
    # value found across all five live memory stores was corrected
    # (superseded-within → active, 606225f), and a full sweep of the same
    # five stores afterward found no value outside {active,archived,
    # superseded} anywhere. This check therefore rejects nothing that
    # currently exists; it only closes the door `stale` left open.
    status_type_val="$(fm_field "$file" status || true)"
    case "$status_type_val" in
        active|archived|superseded|"") ;;
        *) err "$rel — status='$status_type_val' is not in {active,archived,superseded}" ;;
    esac

    # (d) Tier 1 naming convention: {type}_{slug}.md
    if [[ "$parent_dir" == "memory" ]]; then
        # Tier 1 — filename must start with type_
        basename_file="$(basename "$file")"
        if [[ -n "$type_val" && "$basename_file" != "${type_val}_"* ]]; then
            warn "$rel — Tier-1 naming convention: expected '${type_val}_<slug>.md', got '$basename_file'"
        fi
    fi

    # (e) last_updated — its FORM first, then its age.
    #
    # The form is `DD.MM.YYYY`, optionally followed by whitespace and a
    # parenthesised note, and it is checked here explicitly rather than left to
    # whatever `date` happens to swallow (WI-0106). The note is not a tolerance
    # granted after the fact: it carries WHY the date moved — which round, which
    # item — and that is information no other field holds. Ten files in this
    # repo's own store were already written that way, and PHASE_DOC_SCHEMA.md
    # has specified the same optional suffix for phase documents all along;
    # MEMORY_SCHEMA.md now says so too, and this check is what makes the
    # sentence enforceable.
    #
    # Why an explicit shape check and not the parse alone. Before this, the raw
    # value went straight into date_to_epoch() and "a date came back" WAS the
    # contract. Both `date` implementations accept trailing text after the value
    # they matched, so the annotated form passed — but so did every other
    # trailing text, and the two linters answered the same question differently.
    # Measured 25.08.2026, identical values through both:
    #
    #   `24.08.2026 a note without parentheses`  here: accepted  phase-docs: rejected
    #   `24.08.2026(WI-0102)`  (no space)        here: accepted  phase-docs: rejected
    #   `24.08.2026 (unclosed`                   here: accepted  phase-docs: rejected
    #
    # `fm_date_shape_ok` (scripts/lib/frontmatter.sh) is the same pattern
    # phase-docs-lint.sh's check (e) uses, so the two now answer alike on the
    # form. They used to still differ on the DATE — a well-formed but
    # impossible value (`32.13.2026`, `99.99.9999`) was rejected here by the
    # parse below and accepted there, which had no pattern-independent date
    # check at all. WI-0107 closed that gap (ADR-0001 promotion) by moving
    # both the shape check and the parse into ONE shared implementation in
    # scripts/lib/frontmatter.sh (`fm_date_shape_ok` / `fm_date_to_epoch`),
    # sourced by both linters — one rule, one answer, not two hand-typed
    # copies that had never agreed.
    #
    # The shape check runs in FRONT of the parse, and it does not replace it:
    # the shape check says nothing about whether 32.13.2026 is a day, the
    # parse says nothing about what follows the year. Both are needed, and the
    # test proves the second half — neutering the parse's error branch turns
    # the impossible-date case red (measured).
    #
    # The ORDER, by contrast, is a diagnosis decision, not a verdict one, and
    # the comment used to overclaim it. Measured: swapping the two branches
    # leaves every assertion green, because a malformed value is rejected either
    # way — only the sentence it is rejected with changes ("not in format …"
    # naming the shape, vs. "cannot be parsed …" naming a symptom of it). Same
    # for the pattern's leading `^`: dropping it survives the suite, because a
    # value with anything in front of the date fails the parse anyway. It stays
    # for parity with phase-docs-lint.sh, where no parse follows and the anchor
    # is load-bearing — not because a test here would catch its removal.
    last_updated="$(fm_field "$file" last_updated || true)"
    if [[ -n "$last_updated" ]]; then
        if ! fm_date_shape_ok "$last_updated"; then
            err "$rel — last_updated='$last_updated' not in format 'DD.MM.YYYY' or 'DD.MM.YYYY (note)'"
        else
            epoch="$(fm_date_to_epoch "$last_updated")"
            if [[ "$epoch" != "0" && -n "$epoch" ]]; then
                age_days=$(( (TODAY_EPOCH - epoch) / 86400 ))
                if (( age_days > STALE_DAYS )); then
                    status_val="$(fm_field "$file" status || true)"
                    if [[ "$status_val" != "archived" && "$status_val" != "superseded" ]]; then
                        warn "$rel — last_updated=$last_updated is ${age_days} days old (>${STALE_DAYS}d) — refresh last_updated, or set status='archived'/'superseded' if this file is intentionally no longer maintained"
                    fi
                fi
            else
                err "$rel — last_updated='$last_updated' cannot be parsed as DD.MM.YYYY"
            fi
        fi
    fi

    # (f) related: cross-refs — resolved document-relative first (the
    # documented form: MEMORY_SCHEMA.md says relative to the file's own
    # directory). Authors in the field write these entries project-root-
    # relative instead (e.g. `docs/memory/foo.md`), so a miss falls back to
    # $PROJECT_DIR before being declared dead (WI-0078, mirroring the WI-0071
    # fix already shipped for the identical question in phase-docs-lint.sh
    # check (f)/(g), PO decision 21.08.2026). A root-relative hit is `info`,
    # not silence — accepting two bases without saying so would be exactly
    # the unvalidated drift this lint exists to catch. Deliberately the same
    # fallback base ($PROJECT_DIR) and message wording as phase-docs-lint.sh
    # uses — no second convention for the second linter.
    base_dir="$(dirname "$file")"
    while IFS= read -r rel_entry; do
        [[ -z "$rel_entry" ]] && continue
        if [[ -f "$base_dir/$rel_entry" ]]; then
            : # document-relative hit — the documented, silent case
        elif [[ -f "$PROJECT_DIR/$rel_entry" ]]; then
            info "$rel — related:'$rel_entry' resolved via project-root fallback ($PROJECT_DIR/$rel_entry), not found relative to $base_dir"
        else
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
            close_line=$(awk 'NR==1 && $0=="---" {found=1; next} found && $0=="---" {print NR; exit}' "$silo_memory")  # exit-status: exempt downstream-checks-result
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
    low_conf=$(grep -chE '^\*\*Confidence: 0\.[34]\*\*' "${tier1_low_conf_files[@]}" 2>/dev/null | paste -sd+ - | bc 2>/dev/null || true)  # exit-status: exempt grep-empty-is-valid
    low_conf=${low_conf:-0}
    if (( low_conf > 0 )); then
        if [[ -d "$TIER1_GLOBAL_TOPIC_DIR" ]]; then
            info "Tier-1-global — ${low_conf} entries at Confidence ≤ 0.4 across ~/.claude/instincts.md + ~/.claude/instincts/*.md (review candidates if older than ${DECAY_DAYS}d without confirmation; full decay check belongs in /postmortem)."
        else
            info "~/.claude/instincts.md — ${low_conf} entries at Confidence ≤ 0.4 (review candidates if older than ${DECAY_DAYS}d without confirmation; full decay check belongs in /postmortem)."
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
        # `[x](my file.md)` does not collapse to `my` here. All three CommonMark
        # title delimiters are stripped here (WI-0034): double quotes, single
        # quotes and parentheses. This case must stay in agreement with
        # reference_definition_tail() above — recognising a parenthesised title as
        # a valid reference definition without also stripping it here would leave
        # the title text glued to the checked target, turning a live file into a
        # reported-dead one. A bare space that is NOT part of a recognised title
        # is left in place here on purpose — the next block below decides what an
        # unbracketed leftover space means (WI-0061); this block only strips
        # titles, it does not judge validity.
        case "$target" in
            *[[:space:]]\"*\") target="${target%[[:space:]]\"*}" ;;
            *[[:space:]]\'*\') target="${target%[[:space:]]\'*}" ;;
            *[[:space:]]\(*\)) target="${target%[[:space:]]\(*}" ;;
        esac
        target="${target%"${target##*[![:space:]]}"}"
        # The bracket form `<...>` (CommonMark) exists specifically so a
        # destination MAY contain a space. An UNBRACKETED destination may not —
        # an unescaped space terminates it, and whatever follows (already
        # stripped above if it was a real title) is not a valid title either,
        # so the whole `[x](...)` construct is not a link at all. `[x](my
        # file.md)` is therefore neither a link to `my` (WI-0034, the
        # truncation fix above) nor a dead target to report (WI-0061) — it is
        # not a link, so it is skipped like any other non-link text.
        case "$target" in
            \<*) : ;;
            *[[:space:]]*) continue ;;
        esac
        # Unwrap the bracket form before resolving — the raw `<...>` text
        # reaches here unchanged from protect_link_destinations() (WI-0060).
        # An UNCLOSED opening bracket (`[x](<a.md)`, no matching `>` before the
        # captured text ends) is not a valid link at all per CommonMark and
        # must stay skipped, not have its bracket silently dropped.
        case "$target" in
            \<*\>) target="${target#<}"; target="${target%>}" ;;
            \<*) continue ;;
        esac
        # Skip external schemes and in-page anchors outright — neither
        # addresses a file in the repository. Checked AFTER the bracket
        # unwrap above so a bracket-wrapped external URL
        # (`[x](<http://example.com>)`) is skipped too, instead of being
        # treated as a relative file path.
        case "$target" in
            http://*|https://*|mailto:*|\#*) continue ;;
        esac
        # `a.md#section` addresses the file a.md — drop the fragment before resolving.
        target="${target%%#*}"
        # A "#" decoded from a numeric character reference (WI-0081, e.g.
        # `&#35;`) is destination TEXT, not a fragment separator — the awk
        # side swaps it for hash_mark (a control byte no real target can
        # contain) specifically so the fragment-strip above cannot see it.
        # Restored to a literal "#" only now, after that strip has already run.
        target="${target//$'\x05'/#}"
        [[ -n "$target" ]] || continue
        # WI-0081 (remainder): a destination containing an UNRESOLVED named HTML
        # entity (`&num;`, `&amp;`, ...) cannot be turned into a real path here —
        # decode_numeric_entities() (awk side, above) only resolves the NUMERIC
        # forms (`&#35;`, `&#x23;`); the full ~2000-entry CommonMark named-entity
        # table is deliberately not built for a construct measured at zero
        # occurrences across four live memory stores (see
        # docs/memory/reference_commonmark-conformance.md). Resolving the raw,
        # undecoded string and reporting it as dead used to claim a verdict this
        # check cannot actually back: `dead&num;3.md` decodes to `dead#3.md` at
        # the reference, and if THAT file exists, the raw-string check reported a
        # LIVE link as dead — "cannot resolve" is not license to claim "does not
        # exist" in either direction. Filed as info instead, naming the raw
        # target, and skipped before the existence check below ever runs.
        if [[ "$target" =~ \&[a-zA-Z][a-zA-Z0-9]*\; ]]; then
            info "$index_rel — link target '$target' contains an unresolved named HTML entity reference and could not be checked"
            continue
        fi
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
    # LC_ALL=C is not cosmetic and not a style rule (WI-0099). Two measured
    # reasons, both about this awk program specifically:
    #
    #   1. tolower() case-folds NON-ASCII according to the process locale, so
    #      normalize_label() below matched `[ÄÖ]:` against `[äö]` under a UTF-8
    #      locale and not under C. The test harness runs this script with
    #      env={HOME, PATH} (C); an interactive /cleanup or /postmortem run
    #      inherits the user's UTF-8 one. Same script, same input, two
    #      conformance verdicts, decided by who called it.
    #   2. /usr/bin/awk (20200816) ABORTS with `towc: multibyte conversion
    #      failure` the moment a record contains a byte that is not valid UTF-8
    #      — under a UTF-8 locale only. The whole index is then left unscanned
    #      and every dead link in it disappears from the report, silently.
    #      Byte-oriented C cannot reach that path.
    #
    # The house does the same at scripts/artifact-gate.sh, scripts/memory-sync.sh
    # and scripts/lib/discipline_gate.sh. Pinning fixes the ANSWER in place; it
    # does not by itself make the answer right — see the ASCII short-circuit in
    # reference_link_span() for the other half.
    done < <(LC_ALL=C awk '
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
        # to resolve_paragraph() in one call, so lookahead is bounded to one
        # paragraph and never reaches past a block boundary (blank line,
        # thematic break, setext underline, list marker, heading, fence, or a
        # block-level HTML comment).
        #
        # WI-0048: there is no fixed winner between an HTML comment and a code
        # span — whichever construct opens FIRST, reading left to right, claims
        # its span, and the other constructs delimiters inside that span are
        # literal text. The two used to be two separate whole-paragraph passes
        # (decomment_paragraph() then, per resulting segment, strip_inline_
        # code()) — any fixed order between two such passes is wrong in one
        # direction: a comment opened first correctly hid a backtick inside it,
        # but a code span opened first wrongly let the comment pass re-pair
        # backticks across a comment delimiter it should never have seen,
        # because decomment_paragraph() ran over the whole line before strip_
        # inline_code() ever got to look at it. resolve_paragraph() below
        # replaces both with ONE left-to-right scan: at each position it asks
        # only "does a construct open exactly here", so whichever one is
        # encountered first is exactly the one that gets to claim its span —
        # see docs/memory/reference_commonmark-conformance.md for the four
        # fixtures this was measured against.
        #
        # WI-0052: strip_inline_code() used to carry the premise that a code
        # span never crosses a physical line, so it could run once per line
        # after decomment_paragraph() split the resolved paragraph back into
        # segments. That premise is false — CommonMark lets a code span cross a
        # line break inside one paragraph, exactly like an HTML comment does.
        # resolve_paragraph() therefore runs once over the WHOLE buffered
        # paragraph, the same scope decomment_paragraph() already used for
        # comments, and flush_paragraph() below no longer splits the resolved
        # text into per-line segments at all.
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
        # ever breaks an accidental adjacency — it does not introduce one. A
        # removed code span is not given a boundary of its own: that gap is
        # pre-existing (unchanged by this merge) and out of scope for WI-0048/
        # WI-0052.
        #
        # dest_mark wraps a link destination that protect_link_destinations()
        # has already isolated (WI-0042): CommonMark link-destination grammar is
        # not inline-parsed, so neither a `<!--...-->` sequence nor a backtick
        # inside `[x](dest)` opens or closes anything there — both are literal
        # text, not a delimiter to interpret. A dest_mark..dest_mark span is
        # therefore copied through untouched wherever it is met — at the top
        # level of the scan, and also while resolve_paragraph() is searching for
        # a code spans closing run, which the pre-merge strip_inline_code()
        # never guarded (it ran after dest_mark was already in the text, with no
        # awareness of it at all). The two sentinels are stripped again once the
        # destination has been extracted (strip_dest_mark()). This only ever
        # protects a destination; comment or code-span markup in a link LABEL is
        # ordinary inline content and is still resolved by the scan below,
        # unchanged.
        #
        # All of resolve_paragraph()s working state — out, i, n, run_start,
        # run_len, j, close_len, found, e — is declared as an awk LOCAL (an
        # extra, whitespace-separated function parameter never passed a value),
        # the same discipline WI-0050 established for decomment_paragraph()s
        # local_in_comment: an undeclared bare name defaults to GLOBAL in awk,
        # and a global that survives past the call that set it is exactly how
        # the pre-WI-0050 decomment() leaked an unclosed comment across the rest
        # of the file. resolve_paragraph() goes further than declaring one flag
        # local — because comment and code-span resolution now happen inside
        # the SAME scan, in the SAME call, there is no in_comment-style flag
        # that needs to survive between iterations of the loop at all: an
        # opener is found and its closer is searched for (or the paragraph
        # ends) within the same pass over the same local `s`, so nothing has a
        # chance to leak into the next paragraph or the next file.
        function resolve_paragraph(s,   out, i, n, e, run_start, run_len, j, close_len, found) {
            out = ""
            n = length(s)
            i = 1
            while (i <= n) {
                if (substr(s, i, 1) == dest_mark) {
                    e = index(substr(s, i + 1), dest_mark)
                    # An UNPAIRED sentinel — REACHABLE, and measured, not a
                    # "should not happen" guard (WI-0097). Sentinels are only
                    # ever emitted in pairs, but a source line may carry a
                    # literal 0x03 byte of its own: in `a <0x03> stray and
                    # [x](d.md)` the stray byte pairs with the OPENING sentinel
                    # of the real destination one skip earlier, and the odd one
                    # out arrives here. Copying the remainder verbatim is the
                    # conservative answer — the bytes are handed on untouched,
                    # so nothing is discarded and no code span or comment is
                    # resolved across a boundary this function can no longer
                    # trust. The loss itself is real, sits in the pairing one
                    # skip earlier, and is recorded as WI-0097 (false negative).
                    if (e == 0) {
                        out = out substr(s, i)
                        return out
                    }
                    out = out substr(s, i, e + 1)
                    i = i + e + 1
                    continue
                }
                if (substr(s, i, 4) == "<!--") {
                    e = index(substr(s, i + 4), "-->")
                    if (e == 0) {
                        # Unclosed within this paragraph — literal text, per the
                        # PO decision of 20.08.2026: nothing is discarded.
                        out = out substr(s, i)
                        return out
                    }
                    i = i + 4 + e + 2
                    out = out boundary
                    continue
                }
                if (substr(s, i, 1) != "`") {
                    out = out substr(s, i, 1)
                    i++
                    continue
                }
                # Code-span opener: a run of backticks, closed only by the next
                # run of the SAME length — CommonMark pairs by *run length*, not
                # by position (mirrors the fence rule above, except a fence
                # closes on length >= opener while a code span closes on length
                # == opener). A naive 1st-backtick-pairs-with-2nd-backtick scan
                # gets this wrong: it can pair mismatched run lengths, and,
                # chained from that, later runs on the same paragraph inherit
                # the wrong offset.
                run_start = i
                run_len = 0
                while (i <= n && substr(s, i, 1) == "`") {
                    run_len++
                    i++
                }
                found = 0
                j = i
                while (j <= n) {
                    if (substr(s, j, 1) == dest_mark) {
                        e = index(substr(s, j + 1), dest_mark)
                        # Same unpaired sentinel, met while searching for a code
                        # spans closer, and reachable for the same reason —
                        # measured on a line whose backtick run opens BEFORE the
                        # stray byte is reached, e.g. an unclosed code-span
                        # opener followed by `<0x03> tail and [x](d.md)`.
                        # `break` leaves the search with found == 0, so the
                        # opener run is emitted as literal text (see below) and
                        # the outer loop resumes right after it: the same
                        # conservative "hand the bytes on" answer as the guard
                        # at the top of this function.
                        if (e == 0) break
                        j = j + e + 2
                        continue
                    }
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
                    i = run_start + run_len   # resume right after the opening run
                }
            }
            return out
        }
        # Converts a HEX digit string (no 0x/0X prefix) to its decimal value —
        # a small, bounded helper, not a general parser: called only on the
        # digits already isolated by decode_numeric_entities() below.
        function hex_to_dec(h,   i, c, v, d) {
            v = 0
            for (i = 1; i <= length(h); i++) {
                c = tolower(substr(h, i, 1))
                d = index("0123456789abcdef", c) - 1
                v = v * 16 + d
            }
            return v
        }
        # Decodes a numeric character reference (`&#35;` decimal, `&#x23;`/
        # `&#X23;` hex) to its literal character, but only when the codepoint
        # falls inside printable ASCII (32-126) — the only range a
        # docs/memory/** relative path can plausibly need (WI-0081). Anything
        # else — a NAMED entity (`&num;`), or a numeric one outside that
        # range — is left raw and undecoded rather than guessed at: reporting
        # the untouched source text is an accepted known_divergence, mangling
        # it is not. Decoding a full ~2000-entry named-entity table for a
        # construct measured at zero occurrences in the field would not be
        # proportionate to the gap it closes.
        #
        # A decoded "#" specifically is swapped for hash_mark, a control-byte
        # sentinel no real target can contain, instead of a literal "#" —
        # otherwise the shell-side fragment-anchor strip (`${target%%#*}`)
        # would cut the resolved target right there, exactly the WI-0081
        # case-3 defect this decode step exists to fix. Restored to a literal
        # "#" only after that strip runs (see the shell loop below).
        function decode_numeric_entities(s,   out, i, n, m, num, hexdigits, code, ch) {
            out = ""
            n = length(s)
            i = 1
            while (i <= n) {
                m = 0
                if (substr(s, i, 2) == "&#") {
                    if (match(substr(s, i), /^&#[0-9]+;/)) {
                        num = substr(s, i + 2, RLENGTH - 3)
                        code = num + 0
                        m = RLENGTH
                    } else if (match(substr(s, i), /^&#[xX][0-9A-Fa-f]+;/)) {
                        hexdigits = substr(s, i + 3, RLENGTH - 4)
                        code = hex_to_dec(hexdigits)
                        m = RLENGTH
                    }
                }
                if (m > 0 && code >= 32 && code <= 126) {
                    ch = sprintf("%c", code)
                    out = out (ch == "#" ? hash_mark : ch)
                    i += m
                    continue
                }
                out = out substr(s, i, 1)
                i++
            }
            return out
        }
        # Wraps the raw text after a `](` in dest_mark before resolve_
        # paragraph() ever sees it (WI-0042).
        #
        # A `](` only opens a destination when a live opener precedes the `]`
        # AND that `]` is not itself backslash-escaped (WI-0095, closed). Both
        # conditions are checked by the same left-to-right scan process_
        # link_line() already uses for its own opener stack: `[` pushes an
        # unescaped opener, `]` pops one if any is open. A `]` only starts a
        # destination when it just popped a real opener (`had_opener` below)
        # AND the very next byte is `(` — every other `]`, escaped or with no
        # opener left, is ordinary text and leaves `sp` exactly where a correct
        # bracket count would. That parity matters: an unescaped `]` with no
        # following `(` (`[a] b](t.md)`, no link at the reference) still has to
        # POP its opener here, or a later, unrelated `]` inherits its credit
        # and wrongly opens a span — measured against exactly that fixture
        # during the repair.
        #
        # This scan does NOT reproduce the rule 3 that process_link_line() applies (a
        # successful link deactivates every enclosing opener) — it only asks
        # "is there an unclosed `[` at all", not "is this specific opener still
        # live for a REAL link". An over-eager span drawn on a since-deactivated
        # outer opener (`[a [b](i.md) c](o.md)`) is harmless downstream:
        # process_link_line() finds that outer opener inactive and takes its
        # literal-`]` branch before it ever looks at what follows, so the
        # dest_mark span it walks past is never printed. That is the SAME
        # imprecision the pre-fix regex already had on this exact shape (it
        # matched every `](` unconditionally too), so it is not a new
        # divergence — just not one this repair needed to remove.
        #
        # A second, independent limit — NOT what WI-0095 closed — is now
        # fixed too (WI-0118): the destination-closing scan tracks a paren
        # DEPTH for the unbracketed form, per the CommonMark link-destination
        # grammar. An unescaped `(` opens a nested pair (depth++); an
        # unescaped `)` at depth > 0 closes one and is consumed as
        # destination TEXT (depth--); only an unescaped `)` at depth == 0 is
        # the delimiter. `[](()` no longer invents a target named `(` — the
        # lone `(` never finds a depth-0 `)` to close it, so `dend` stays 0
        # and the whole remainder is carried through unresolved, same as any
        # other unterminated destination. `[a](b(c)d.md)` — balanced parens
        # INSIDE a destination, which CommonMark accepts — now resolves to
        # the full `b(c)d.md` instead of truncating at the first `)`.
        #
        # Where no unescaped `)` closes the destination this still gives up
        # (`dend == 0` below) and carries the whole remainder through
        # UNPROTECTED, so "every destination is isolated" is not a property
        # this function has.
        #
        # The scanner skips a dest_mark span as one unit (WI-0080), which is
        # why the correctness of the stage that DRAWS the spans is not
        # optional — a wrong span here is load-bearing downstream, not
        # harmless. Riding the raw text along inside the normal `line` flow,
        # instead of re-locating it afterward from a parallel scan, keeps it
        # structurally glued to whichever `[text](dest)` span it belongs to —
        # including when that whole span later turns out to be inside a code
        # span or an illustrative backtick example and gets discarded as a
        # unit.
        #
        # The closing `)` is found by a manual scan, not `[^)]*` — a
        # backslash-escaped `)` (WI-0081) is destination TEXT, not the
        # delimiter, and a plain character-class stop cannot tell the two
        # apart. Escape parity reuses count_trailing_backslashes(), the same
        # helper process_link_line() uses for bracket escaping (WI-0079) —
        # one escaping rule, now three call sites (the opener, the destination
        # closer, and the `]` in this function).
        function protect_link_destinations(s,    out, dstart, dend, dest, n, pos,
                                           i, ch, sp, had_opener, pdepth, pch,
                                           is_angle) {
            out = ""
            n = length(s)
            sp = 0
            i = 1
            while (i <= n) {
                ch = substr(s, i, 1)
                if (ch == "[" && !is_escaped(s, i)) {
                    sp++
                    out = out ch
                    i++
                    continue
                }
                if (ch == "]" && !is_escaped(s, i)) {
                    had_opener = (sp > 0)
                    if (had_opener) sp--
                    if (had_opener && substr(s, i + 1, 1) == "(") {
                        dstart = i + 2
                        dend = 0
                        pos = dstart
                        pdepth = 0
                        # The `<...>` bracketed destination form (WI-0060) has
                        # its own termination rule — an unescaped `>` closes
                        # it, and a paren inside has no special meaning at all
                        # (measured against the reference: `[a](<b)c.md>)`
                        # resolves to `b)c.md`, a `)` before the `>`). This
                        # scan does not implement that rule; it only keeps the
                        # paren-depth balance below from firing on it, so the
                        # existing first-unescaped-`)` behaviour is left
                        # exactly as it was for this form (it already resolves
                        # `[a](<b(c.md>)` correctly today because no `)`
                        # appears before the real delimiter in that fixture —
                        # not because this scan parses `<...>` itself).
                        is_angle = (substr(s, dstart, 1) == "<")
                        while (pos <= n) {
                            pch = substr(s, pos, 1)
                            if (pch == ")" && count_trailing_backslashes(s, pos) % 2 == 0) {
                                if (!is_angle && pdepth > 0) {
                                    pdepth--
                                } else {
                                    dend = pos
                                    break
                                }
                            } else if (!is_angle && pch == "(" && count_trailing_backslashes(s, pos) % 2 == 0) {
                                pdepth++
                            }
                            pos++
                        }
                        if (dend == 0) {
                            # No unescaped closing paren anywhere in the rest
                            # of this raw line — not a resolvable single-line
                            # destination; carry the remainder through
                            # untouched and stop looking.
                            return out "](" substr(s, dstart)
                        }
                        dest = substr(s, dstart, dend - dstart)
                        # An escaped ")" is literal destination text, per CommonMark,
                        # so the escape is undone here. It used to be undone into a
                        # paren_mark sentinel and restored to ")" only in
                        # strip_dest_mark(), because process_link_line() located a link
                        # span with a `[^)]*` scan of its own, blind to the dest_mark
                        # opacity, and would have stopped at a decoded ")"
                        # mid-destination. Since WI-0080 that scan is gone: the
                        # destination extent is read off the dest_mark span, so a ")"
                        # inside it is inert.
                        #
                        # The detour was kept one round longer on the grounds that no
                        # test could pin its removal either way. That was wrong, and the
                        # line below is why: decode_numeric_entities() runs AFTER the
                        # substitution, so `[x](a&#41;b.md)` has been putting a literal
                        # ")" inside a dest_mark span since WI-0081 and resolving
                        # correctly — the post-removal state was already pinned, by a
                        # fixture that existed before the removal. Both spellings now
                        # have one.
                        gsub(/\\\)/, ")", dest)
                        dest = decode_numeric_entities(dest)
                        out = out "](" dest_mark dest dest_mark ")"
                        i = dend + 1
                        continue
                    }
                    out = out ch
                    i++
                    continue
                }
                out = out ch
                i++
            }
            return out
        }
        function strip_dest_mark(s) {
            gsub(dest_mark, "", s)
            return s
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
        # Registers a reference-definition LABEL into refmap and, on pass 2,
        # prints its destination for the shell side to check — the two-line
        # body shared by the same-line call site and the WI-0083 next-line
        # lookahead below, so the "two accumulation keys" registration
        # (WI-0098) is expressed once, not twice.
        function register_reference_definition(reflbl, rawlbl, dest,   reslbl) {
            reslbl = normalize_label(resolve_paragraph(protect_link_destinations(rawlbl)))
            refmap[reflbl] = 1
            if (reslbl != reflbl) refmap[reslbl] = 1
            if (pass == 2) print dest
        }
        # Counts the run of backslashes immediately BEFORE position pos in s —
        # not including pos itself. A byte at pos is escaped, per CommonMark,
        # exactly when that count is odd: an escaped backslash (an even-length
        # run) does not itself escape whatever follows it (WI-0079/WI-0081).
        # Checked by trailing-run PARITY, not by a one-byte lookbehind, because
        # a one-byte check cannot tell an escaped backslash (`\\` + real `[`,
        # a live link) apart from an escaped bracket (`\` + `[`, not a link).
        function count_trailing_backslashes(s, pos,   c, p) {
            c = 0
            p = pos - 1
            while (p >= 1 && substr(s, p, 1) == "\\") {
                c++
                p--
            }
            return c
        }
        function is_escaped(s, pos) {
            return (count_trailing_backslashes(s, pos) % 2 == 1)
        }
        # Normalises a reference LABEL the way CommonMark matches one: collapse
        # every internal run of whitespace to a single space, trim the ends,
        # then case-fold. Copied in behaviour from the pinned reference
        # normalize_reference() (commonmark 0.9.2 — measured, see
        # docs/memory/reference_commonmark-conformance.md), with one caveat
        # this comment used to state too flatly (WI-0099). The reference
        # case-FOLDS across all of Unicode; tolower() here folds whatever the
        # process LOCALE says it folds. Measured on /usr/bin/awk (version
        # 20200816), same input, same script: under LANG/LC_ALL=en_US.UTF-8 a
        # definition written `[ÄÖ]:` and used as `[äö]` MATCHES and agrees with
        # the reference; with no locale set, or LC_ALL=C, it does not and the
        # enclosing link is reported. The test harness runs this script with a
        # bare environment, so the corpus freezes the C-locale answer while an
        # interactive run gives the UTF-8 one — the divergence is real, but it
        # is a property of the environment, not of this line. Direction when it
        # bites: the enclosing link is NOT deactivated, i.e. the pre-WI-0093
        # behaviour.
        #
        # Backslash escapes are deliberately NOT decoded — the reference
        # normalises the RAW label source on both sides, so `[a\]b]:` defines
        # exactly the label `[a\]b]` uses, backslash and all.
        function normalize_label(s) {
            gsub(/[ \t\r\n]+/, " ", s)
            sub(/^ /, "", s)
            sub(/ $/, "", s)
            return tolower(s)
        }
        # Returns the LENGTH of the link label starting at `start` (brackets
        # included), or 0 if no valid label starts there. The grammar is the
        # reference regex `reLinkLabel` (`^\[(?:[^\\\[\]]|\\.){0,1000}\]`, plus its
        # length rejection) restated as a scan: unescaped brackets are not
        # allowed inside a label, a backslash escapes exactly one following
        # character and never a line ending, and a label longer than 1001 bytes
        # including its brackets is no label at all.
        #
        # Used from BOTH ends of the reference-link mechanism — the definition
        # line (`[label]: dest`) and the usage (`[text][label]`) — so the two
        # cannot drift apart: a label one side accepts is a label the other
        # accepts. That drift is exactly what WI-0094 found (the definition
        # line still carried the `[^][]+` class WI-0080 had already removed from
        # the usage side, so `[a\]b]: dest.md` was silently not a definition).
        function parse_link_label(s, start,   n, p, c, span) {
            if (substr(s, start, 1) != "[") return 0
            n = length(s)
            p = start + 1
            while (p <= n) {
                c = substr(s, p, 1)
                if (c == "\\") {
                    if (p >= n || substr(s, p + 1, 1) == "\n") return 0
                    p += 2
                    continue
                }
                if (c == "]") {
                    span = p - start + 1
                    return (span > 1001 ? 0 : span)
                }
                if (c == "[") return 0
                p++
            }
            return 0
        }
        # Answers one question at a closing `]` that has NO inline destination
        # after it: does a REFERENCE link resolve here? Returns -1 for "no",
        # otherwise the number of bytes the construct consumes BEYOND the `]`
        # (0 for the shortcut form, which consumes nothing beyond it).
        #
        # Three forms, all measured against the reference (WI-0093):
        #   full       `[text][ref]` — the SECOND label names the definition.
        #   collapsed  `[ref][]`     — the FIRST label does; `[]` is consumed.
        #   shortcut   `[ref]`       — the FIRST label does; nothing follows.
        #
        # A failed FULL reference does not fall back to reading the first label
        # as a shortcut: `[r][nosuch]` renders no link at all even with `[r]:`
        # defined (measured — this is the one shape the obvious implementation
        # gets wrong, and it has its own test).
        #
        # The label read here comes out of the RESOLVED paragraph, not out of
        # the source: resolve_paragraph() has already deleted every code span
        # and replaced every closed inline comment with `boundary`. An empty
        # `lbl` therefore does not mean "the author wrote `[]`" — it can also
        # mean "the author wrote a label that resolved away to nothing", and
        # that is a label a definition can legitimately carry too. The lookup is
        # unguarded for exactly that reason; the definition side registers its
        # labels in this same resolved shape (see the definition branch in the
        # record block), so `""` is a key only when some definition really did
        # resolve to it (WI-0098).
        # True when `s` carries any byte >= 0x80. Byte-wise on purpose — see
        # the high_bytes comment in BEGIN for why this is not a regex.
        function has_non_ascii(s,   i, n) {
            n = length(s)
            for (i = 1; i <= n; i++) if (index(high_bytes, substr(s, i, 1)) > 0) return 1
            return 0
        }
        function reference_link_span(s, i, o_pos,   n, raw, lbl) {
            n = parse_link_label(s, i + 1)
            if (n > 2) raw = substr(s, i + 2, n - 2)
            else raw = substr(s, o_pos + 1, i - o_pos - 1)
            # WI-0099, the second half of the locale fix. Pinning LC_ALL=C
            # makes the answer STABLE; on a non-ASCII label it would also make
            # it stably WRONG, because C-locale tolower() folds nothing above
            # 0x7F and `[ÄÖ]:` would stop matching `[äö]` for everyone rather
            # than only for the harness. So a label carrying a byte >= 0x80 is
            # answered "resolves" without consulting refmap at all.
            #
            # That is the conservative direction, and which direction it is
            # follows from the shape of the caller, not from a sample of
            # inputs: "resolves" only ever DEACTIVATES an enclosing opener and
            # consumes a span, and the sole print() in process_link_line() sits
            # behind an active opener. So this branch can drop a finding and
            # cannot invent one -- SO LONG AS protect_link_destinations() draws
            # correct spans, i.e. only opens one after a live, unescaped
            # opener (WI-0095, closed). parse_link_label() is blind to
            # dest_mark; a `]` sitting inside a WRONGLY-SCOPED span used to
            # terminate a label early, landing the advance this function
            # returns in the middle of that span, where the invariant the
            # argument above rests on no longer held -- exactly the class
            # WI-0095 closed. A second imprecision in the same function
            # (WI-0100/WI-0118, CLOSED 26.08.2026): the destination-closing
            # scan used to not require the parens inside a destination to
            # balance, which could pick the wrong `)` as the delimiter and
            # mis-target an otherwise correctly SCOPED span. That was a wrong
            # TARGET, not a wrongly swallowed `]`, so it never reopened the
            # precondition of this branch -- it bore on the contract of check
            # (n) itself (WI-0100), not this branch, and this branch
            # inherited neither, before or after the fix.
            # The dropped finding is real and is recorded
            # as a corpus entry (`known_divergence`, direction false-negative):
            # an UNDEFINED non-ASCII label now silences the link around it. The
            # trade is the PO decision of 24.08.2026 — a false negative that is
            # a property of this code, in place of a false positive that was a
            # property of the environment it was measured in.
            #
            # Deliberately NOT narrowed on the definition side: `[ÄÖ]: dead.md`
            # still reports its target. Whether a label MATCHES is the question
            # narrowed here; whether a destination EXISTS is check (n)s own
            # contract and needs no label folding at all.
            if (has_non_ascii(raw)) return n
            lbl = normalize_label(raw)
            return ((lbl in refmap) ? n : -1)
        }
        # The effect of rule 3, in one place because it now has two callers (an
        # inline link and a resolved reference link deactivate identically).
        function deactivate_enclosing_link_openers(sp, st_img, st_act,   k) {
            for (k = 1; k <= sp; k++) if (!st_img[k]) st_act[k] = 0
        }
        # Finds every inline link left in the resolved paragraph and prints its
        # destination — images excluded (`![alt](src)` is not an index entry,
        # WI-0029). Called once per resolved paragraph by flush_paragraph().
        #
        # A regex cannot express this (WI-0080). The label class used to be
        # `\[[^][]*\]`, which excludes BOTH bracket characters — so no label
        # carrying a bracket could ever match, and `[a [b] c](t.md)`, one
        # ordinary link at the reference, was silently skipped at every nesting
        # depth. Widening the class is not a fix either: CommonMark link text is
        # a BALANCED, arbitrarily deep construct and a regular expression cannot
        # count. (Measured against commonmark 0.9.2 to depth 100 — the reference
        # imposes no ceiling, so neither does the stack below.)
        #
        # So: a scanner with an explicit opener stack, and four rules, each one
        # measured at the reference rather than read out of the spec.
        #
        #   1. `[` pushes an opener, `]` pops one — balanced brackets in the
        #      label are ordinary content, at any depth.
        #   2. A backslash-escaped bracket is literal text and neither opens nor
        #      closes anything (WI-0079). Decided by is_escaped(), i.e. by
        #      backslash-run PARITY, never by a one-byte lookbehind: `\\[x](t.md)`
        #      carries an escaped BACKSLASH and a live `[`. The same parity
        #      decides the `!` of an image marker — `\![x](t.md)` is a link.
        #   3. "Links may not contain other links, at any level of nesting" — on
        #      a successful LINK every opener still on the stack is deactivated,
        #      so no enclosing bracket can form a link and the INNER link wins.
        #      Before this rewrite that held by accident (the outer label simply
        #      could not match); it is now explicit, and pinned by its own test.
        #   4. An IMAGE in the link text does NOT disqualify the enclosing link:
        #      `[![alt](i.png)](t.md)`, the badge shape, is a live link whose
        #      text is an image (WI-0091). This is also why the split point can
        #      never be "the `](` on the line" — here the LABEL contains one.
        #   5. Rule 3 fires on any successful LINK, not only on an inline one
        #      (WI-0093). A `]` with no `(dest)` after it may still close a
        #      RESOLVING reference link — shortcut `[ref]`, collapsed `[ref][]`
        #      or full `[text][ref]` — and that deactivates the enclosing
        #      openers exactly like an inline link does. Deciding it needs the
        #      documents reference-definition labels, which is why this program
        #      reads each index twice (see the pass gate in the record block).
        #      Whether such a construct RESOLVES is the only difference between
        #      `[a [b] c](t.md)`, one ordinary link, and `[a [ref] c](t.md)`,
        #      which renders no outer link at all — measured, both of them.
        #
        # The destination is not re-parsed here. protect_link_destinations() has
        # already isolated every `](`-destination into an opaque dest_mark span,
        # so an inline link is exactly `]` + `(` + dest_mark span + `)`. The same
        # span is skipped wholesale wherever else it is met, so a bracket inside
        # a destination can never be read as a delimiter.
        #
        # Nothing is ever skipped by a match LENGTH: the scan only ever jumps
        # over something it has RESOLVED — an opaque destination span, or a link
        # it just consumed — and advances one byte everywhere else. A
        # DISQUALIFIED construct therefore consumes exactly its one `]`, and
        # cannot hide a real link later on the same line. WI-0079 had to arrange
        # that by hand with a deliberate one-byte advance; here it follows from
        # the shape of the loop.
        function process_link_line(line,   n, i, ch, e, r, sp, o_img, o_act, o_pos,
                                   prev, st_img, st_act, st_pos) {
            n = length(line)
            sp = 0
            i = 1
            while (i <= n) {
                ch = substr(line, i, 1)
                if (ch == dest_mark) {
                    e = index(substr(line, i + 1), dest_mark)
                    # An UNPAIRED sentinel. Reachable, though it reads as
                    # impossible: protect_link_destinations() only ever emits
                    # them in pairs, but a source file may contain a literal
                    # 0x03 byte of its own. Measured, and it is NOT this branch
                    # that then loses anything — the stray byte has already
                    # PAIRED with the opening sentinel of a real destination one
                    # skip earlier, swallowing the link in between; by the time
                    # the odd one out is met, only a `)` and trailing prose are
                    # left. The loss itself is real and recorded as WI-0097.
                    #
                    # `return` here is output-EQUIVALENT to a one-byte skip, and
                    # that is an argument, not a sample of shapes that happened
                    # to agree. `e == 0` says no further dest_mark occurs in the
                    # rest of this line. The only `print` in this function sits
                    # in the inline-destination branch, which needs TWO more
                    # dest_marks after the current position to fire at all, so
                    # from here on nothing can be printed. Nothing else in the
                    # loop leaves the function: the opener stack is local, and
                    # deactivating openers changes no output once no output is
                    # possible. Continuing would therefore print exactly what
                    # returning prints, which is nothing — so the shorter branch
                    # is not a degradation choice, it is the same behaviour.
                    if (e == 0) return
                    i = i + e + 1
                    continue
                }
                if (ch == "[" && !is_escaped(line, i)) {
                    prev = (i > 1) ? substr(line, i - 1, 1) : ""
                    sp++
                    st_act[sp] = 1
                    st_img[sp] = ((prev == "!") && !is_escaped(line, i - 1)) ? 1 : 0
                    # Where this opener sits — rule 5 needs the label TEXT, not
                    # just the fact that a label was open, to look a shortcut or
                    # collapsed reference up in refmap.
                    st_pos[sp] = i
                    i++
                    continue
                }
                if (ch == "]" && !is_escaped(line, i)) {
                    if (sp == 0) {   # no opener left — a literal `]`
                        i++
                        continue
                    }
                    o_img = st_img[sp]
                    o_act = st_act[sp]
                    o_pos = st_pos[sp]
                    sp--
                    if (!o_act) {
                        # Deactivated by rule 3 — no link of ANY form may close
                        # here, so neither branch below is even tried. Tested
                        # first, in that order, because the reference tests it
                        # first: an inactive opener returns a literal `]` before
                        # a destination or a label is ever looked at.
                        i++
                        continue
                    }
                    e = 0
                    if (substr(line, i + 1, 2) == ("(" dest_mark)) {
                        e = index(substr(line, i + 3), dest_mark)
                        if (e > 0 && substr(line, i + 3 + e, 1) != ")") e = 0
                    }
                    if (e > 0) {
                        if (!o_img) {
                            print strip_dest_mark(substr(line, i + 3, e - 1))
                            deactivate_enclosing_link_openers(sp, st_img, st_act)
                        }
                        i = i + 4 + e
                        continue
                    }
                    # No inline destination — rule 5: a REFERENCE link may still
                    # close here. The span it consumes is not always zero
                    # (`[text][ref]` and `[ref][]` eat their second label), and
                    # consuming it matters: `[text][ref](x.md)` renders the
                    # reference link and leaves `(x.md)` as literal text, so a
                    # scanner that only stepped one byte on would re-read
                    # `[ref](x.md)` as an inline link and report a target nobody
                    # linked. The destination of a reference link is NOT printed
                    # here — its definition line already reports it (WI-0042).
                    r = reference_link_span(line, i, o_pos)
                    if (r < 0) {
                        # No reference resolves either — an ordinary literal `]`.
                        # The opener is gone but nothing is deactivated, so a
                        # later link on the same line is unaffected.
                        i++
                        continue
                    }
                    if (!o_img) deactivate_enclosing_link_openers(sp, st_img, st_act)
                    i = i + 1 + r
                    continue
                }
                i++
            }
        }
        # Buffers one physical line into the current paragraph. protect_link_
        # destinations() runs here, per raw line, exactly where it always ran —
        # only comment/code-span resolution moved to paragraph scope, this did
        # not.
        function append_paragraph(raw_line) {
            if (pbuf_n == 0) pbuf = protect_link_destinations(raw_line)
            else pbuf = pbuf "\n" protect_link_destinations(raw_line)
            pbuf_n++
        }
        # Resolves the buffered paragraph and extracts its links, then clears
        # the buffer. resolve_paragraph() runs once over the WHOLE joined
        # paragraph — both a comment span and a code span can swallow the
        # newlines that used to separate physical lines (WI-0050 for the
        # comment, WI-0052 for the code span), and whichever of the two opens
        # first at a given position claims that span (WI-0048). There is no
        # per-line segment left to loop over afterward: process_link_line()
        # runs exactly once, directly on the fully resolved text — its scanner
        # treats an embedded newline as any other label byte (WI-0080; the
        # `[^][]*` regex it replaced did too), so a link whose label happens to
        # still straddle two original lines (never inside a comment or code
        # span) is found too, at no extra cost.
        function flush_paragraph(   resolved) {
            # Cleared BEFORE the early return, not after the flush, so that
            # "empty buffer implies pbuf_para == 0" holds locally at every exit
            # of this function instead of only globally. The early-return path
            # cannot currently be reached with the flag set — it is only ever
            # raised immediately before an append that lifts pbuf_n to 1 — so
            # this is defensive, not a fix: it costs one assignment and keeps a
            # later conditional append from breaking the setext gate silently.
            pbuf_para = 0
            if (pbuf_n == 0) return
            resolved = resolve_paragraph(pbuf)
            # Pass 1 exists only to fill refmap (see the pass gate in the record
            # block); extracting there would print every finding twice.
            if (pass == 2) process_link_line(resolved)
            pbuf = ""
            pbuf_n = 0
        }
        BEGIN {
            sq = sprintf("%c", 39)
            boundary = sprintf("%c", 1)
            fence_sentinel = sprintf("%c", 2)
            dest_mark = sprintf("%c", 3)
            html_comment_sentinel = sprintf("%c", 4)
            hash_mark = sprintf("%c", 5)
            # Every byte >= 0x80, as a lookup string for has_non_ascii()
            # below. Built with sprintf("%c") rather than written as a regex
            # range for a measured reason: the three regex spellings that also
            # work (`[\x80-\xFF]`, `[\200-\377]`, and the same range built
            # dynamically) all ABORT this awk with `towc: multibyte conversion
            # failure` when the input carries an invalid UTF-8 byte AND the
            # locale says UTF-8. index() does not — it survived both locales on
            # every probe. The LC_ALL=C pin at the call site already rules that
            # combination out, so this is belt AND braces: the one spelling
            # that stays correct if the pin is ever lost.
            for (hb = 128; hb <= 255; hb++) high_bytes = high_bytes sprintf("%c", hb)
            pbuf = ""
            pbuf_n = 0
            pbuf_para = 0
            pass = 0
            refdef_pending = 0
        }
        {
            # WI-0093: this program is handed the SAME index file twice, and
            # runs its whole block machine over it twice. CommonMark collects
            # reference DEFINITIONS for the entire document before it parses any
            # inline content, so a definition may legally stand AFTER the link
            # that uses it (measured) — a single pass cannot answer rule 5 at
            # the moment it reaches the link. Pass 1 therefore prints nothing
            # and only fills refmap; pass 2 does the real extraction with the
            # complete label set.
            #
            # Two passes of the SAME program, rather than a cheap pre-scan for
            # definition-shaped lines: whether a line IS a definition depends on
            # its block context (inside a fence or an HTML comment it is not
            # one, and it may not interrupt a paragraph — all measured), and
            # that context is exactly what this record block computes. A second
            # implementation of it would be a second thing to keep in step.
            #
            # Every scrap of pass-1 state is dropped at the pass boundary;
            # refmap is the only thing that crosses it. Line numbers below are
            # therefore FNR, not NR — NR keeps counting across both passes and
            # would report an unclosed fence at twice its line number.
            if (NR == FNR) {
                pass = 1
            } else if (pass == 1) {
                pass = 2
                in_fence = 0
                fence_char = ""
                fence_len = 0
                fence_open_line = 0
                in_html_comment = 0
                html_comment_open_line = 0
                in_html_block1 = 0
                in_html_block6 = 0
                pbuf = ""
                pbuf_n = 0
                pbuf_para = 0
                # A label still awaiting its destination continuation line at
                # the moment pass 1 ends belongs to pass 1s own input only —
                # without this reset, pass 2s first record would be read as
                # the destination for a label pass 1 saw on ITS last line,
                # corrupting pass 2s very first record.
                refdef_pending = 0
            }
            # WI-0086: CommonMark counts `\r\n`, `\r` and `\n` all as line
            # endings; awk splits records on `\n` only, so a CRLF file hands
            # every record over with a trailing `\r` still attached. That does
            # not break the blank-line boundary test alone — it breaks EVERY
            # `$`-anchored regex below it, each one silently, by never
            # matching. Not an exhaustive list, but the ones with a test:
            # blank line, empty ATX heading, fence close, thematic break,
            # setext underline, reference-definition tail. The full set is
            # larger — it also covers the HTML block type 1 and type 6
            # openers, the type 6 blank-line close, and the indented-code
            # branch, whose blank-line test is negated. The claim that matters
            # here is the reach, not the enumeration. Stripping it once,
            # here, as the first statement of the record block, is the only
            # place that reaches all of them: every branch below reads `$0` (or
            # a substring of it, like the reference-definition `raw_rest`) after
            # this line has run. No field is ever referenced in this program, so
            # the record rebuild `sub()` triggers costs nothing.
            #
            # A bare `\r` INSIDE a line (a classic pre-OS-X Mac line ending) is
            # deliberately NOT handled: awk has already split on `\n`, so such a
            # document arrives as one single record and no per-record strip can
            # recover the line structure it never had.
            sub(/\r$/, "")
            # WI-0083: a reference definitions destination may stand on the
            # line AFTER the label — CommonMarks grammar allows "optional
            # whitespace (including up to one line ending)" between the colon
            # and the destination, and again between the destination and an
            # optional title. The label-line check further below defers a
            # label with nothing after its colon by setting refdef_pending and
            # returning; THIS record is that deferred labels own destination
            # candidate, checked with the SAME reference_definition_tail()
            # grammar the same-line form already uses (so `dest "title"`
            # together on this record is accepted too, for free — a title on
            # a THIRD line is not attempted, since CommonMark already treats
            # the title as optional and a destination alone completes a valid
            # definition). Pinned by fixture
            # "reference_definition_third_line_after_destination_is_not_
            # consumed_as_title" in generate_commonmark_corpus.py: that third
            # line falls through and is scanned as ordinary paragraph prose,
            # not as part of this definition.
            #
            # Placed as the very first thing after the CRLF strip, before
            # in_fence/in_html_comment/etc.: those states describe what a
            # NEW block is allowed to be, and a still-open reference
            # definition attempt is not yet a new block — CommonMark tries to
            # parse the destination from the raw next line first, and only if
            # that fails does the line get to start something else.
            #
            # On failure the deferred label was never a valid definition —
            # CommonMark reverts the whole attempt to ordinary paragraph text
            # starting at the label line. pbuf_n was 0 when the label
            # deferred (the same pbuf_n == 0 gate the same-line form uses), so
            # appending it to pbuf now, one record late, loses nothing; this
            # record ($0, unmodified) then falls through unchanged to every
            # check below, exactly as if refdef_pending had never been set —
            # it may itself open a fence, a blank line, a new label, or
            # ordinary prose.
            if (refdef_pending) {
                refdef_pending = 0
                cand = $0
                sub(/^[ \t]+/, "", cand)
                if (reference_definition_tail(cand)) {
                    register_reference_definition(refdef_reflbl, refdef_rawlbl, cand)
                    next
                }
                # pbuf is guaranteed empty here (see above), so this mirrors
                # the ordinary-paragraph-content fallback at the bottom of
                # this rule without needing its blockquote check — a label
                # line can never itself open with `>`.
                pbuf_para = 1
                append_paragraph(refdef_label_raw)
            }
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
            # HTML block, type 1 (raw-text elements script/pre/style — WI-0084):
            # every line up to and including the one that finally contains a
            # matching closing tag is raw, unparsed HTML — a blank line inside
            # does NOT end it (unlike type 6 below). Gated first, same shape as
            # in_fence above, so nothing below (fence-opener, comment, type 6,
            # ...) ever gets offered a line from inside this block.
            if (in_html_block1) {
                if (tolower($0) ~ /<\/(script|pre|style)>/) in_html_block1 = 0
                next
            }
            # HTML block, type 6 (the CommonMark "common block tag" list — div,
            # table, blockquote, and roughly sixty others — WI-0084): ends at the
            # next BLANK line, not at a matching closing tag (see the type-6
            # opener comment below for the measured trap this gets wrong if
            # assumed otherwise). The blank line itself carries no content, so
            # nothing needs printing — it only ever flips the flag off.
            if (in_html_block6) {
                if ($0 ~ /^[ \t]*$/) in_html_block6 = 0
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
            # $0 via RSTART/RLENGTH BEFORE the flush. That ordering was
            # load-bearing while process_link_line() drove a match() loop of its
            # own; since WI-0080 replaced that loop with a scanner, nothing
            # reachable from flush_paragraph() calls match() any more. Kept
            # anyway, and only as defence: reading a matched substring before
            # calling out is the ordering that stays correct if any callee ever
            # uses match() again.
            if (!in_html_comment && match($0, /^[ ]{0,3}(```+|~~~+)/)) {
                opener = substr($0, RSTART, RLENGTH)
                sub(/^[ ]{0,3}/, "", opener)
                flush_paragraph()
                fence_char = substr(opener, 1, 1)
                fence_len = length(opener)
                in_fence = 1
                fence_open_line = FNR
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
                    html_comment_open_line = FNR
                }
                next
            }

            # HTML block, type 1 opener (WI-0084) — the "raw-text element" set
            # (script/pre/style). Tag set and both boundary conditions (closing
            # tag ANYWHERE in a later line, not required to start it; a blank
            # line inside does NOT end the block; an unclosed block runs to
            # end-of-document) are copied verbatim from the pinned reference,
            # `reHtmlBlockOpen[1]`/`reHtmlBlockClose[1]` (commonmark==0.9.2,
            # measured — docs/memory/reference_commonmark-conformance.md), not
            # derived from the abstract CommonMark spec text: the current spec
            # wording additionally lists `textarea`, this pinned reference does
            # not, and this check matches what is actually installed. Matched
            # case-insensitively via tolower() (this file has no gawk-only
            # IGNORECASE available, see hex_to_dec() above for the same
            # tolower() precedent). Unlike a fence or an HTML comment, an HTML
            # block CAN interrupt a paragraph (only type 7, not implemented
            # here, cannot) — so any buffered paragraph is flushed here, not
            # carried into the block.
            if (match(tolower($0), /^[ ]{0,3}<(script|pre|style)([ \t>]|$)/)) {
                flush_paragraph()
                in_html_block1 = 1
                next
            }
            # HTML block, type 6 opener (WI-0084) — the CommonMark "common
            # block tag" list (div, table, blockquote, and roughly sixty
            # others), tag set copied verbatim from the same pinned reference,
            # `reHtmlBlockOpen[6]`. Ends at the next BLANK line,
            # NOT at a matching closing tag: `<div>` foo `</div>` immediately
            # followed by more content, with no blank line anywhere, stays ONE
            # raw HTML block straight through the `</div>` line — measured
            # directly against the reference (see the div/pre/script
            # constructs in reference_commonmark-conformance.md), not assumed.
            # Interrupts a paragraph, same as type 1 above.
            if (match(tolower($0), /^[ ]{0,3}<[\/]?(address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h1|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|section|source|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)([ \t]|\/?>|$)/)) {
                flush_paragraph()
                in_html_block6 = 1
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
            # raw_rest is read out of the record BEFORE that flush, for the same
            # reason the fence-opener branch above reads its own substring
            # first. It is read via lstart/lnum, i.e. off the label
            # parse_link_label() just measured -- NOT via RSTART/RLENGTH, which
            # since WI-0094 only locate the opening bracket of that label.
            #
            # The label is read with parse_link_label(), the SAME grammar the
            # usage side uses, rather than with a class of its own (WI-0094).
            # The class it replaces, `[^][]+`, excluded `]` outright — so
            # `[a\]b]: dest.md`, one definition at the reference, was not
            # recognised as a definition at all and its target went unchecked.
            # That is the WI-0080 defect one function further along: the same
            # rule expressed twice drifts, expressed once it cannot.
            #
            # This is also where the label set that rule 5 consults is built.
            # Recorded BEFORE the flush, because the pbuf_n gate has to read the
            # buffer state this line arrived in, not the emptied one: a
            # definition may not INTERRUPT a paragraph (measured — with prose
            # open above it the reference reads the line as ordinary text and
            # defines nothing).
            #
            # Reporting the target sits BEHIND THE SAME GATE (WI-0096, PO
            # decision 24.08.2026). It did not before, and the gap was the last
            # false positive in the corpus. The line that draws the boundary
            # between this and WI-0085 is not the syntax, which is identical in
            # both, but what the READER sees:
            #
            #   * `[ref]: dead.md` on its own renders as NOTHING. The author
            #     declared a destination, it is gone, and no reader will ever
            #     notice — invisibly dead, so check (n) reports it under its own
            #     broader contract (WI-0085), even though CommonMark renders no
            #     link either.
            #   * `foo` then `[ref]: dead.md` renders as VISIBLE paragraph
            #     text. The path is prose on the page, not a pointer at all,
            #     and reporting it was a false positive (WI-0096).
            #
            # The `reflbl != ""` half of the gate is a second, independent
            # answer of the same kind: `[ ]: dead.md` is no definition either
            # (a label needs one non-whitespace character) and renders as
            # visible prose. Both halves have their own corpus entry, and
            # removing either one alone turns the matching entry red.
            # refmap, meanwhile, answers only the narrower CommonMark question
            # "does a reference resolve here".
            #
            # The label is registered TWICE, and the second one is the point
            # (WI-0098). This side reads the RAW record; the usage side reads
            # the paragraph after protect_link_destinations() and
            # resolve_paragraph() have run, and those two delete a code span
            # outright and swap a closed inline comment for `boundary`. So
            # ``[`a`]:`` registered `` `a` `` while ``[`a`]`` looked up the
            # empty string, nothing matched, and an outer link the reference
            # does not render was reported — a false positive this round
            # introduced, measured against 4f2ffa7 and against the reference.
            # Running the definition label through the SAME two transformations
            # puts both sides in one key space. It is deliberately an ADDITIONAL
            # key, never a replacement: adding keys can only make more
            # references RESOLVE, and a resolving reference only ever
            # deactivates an enclosing link, so this cannot invent a finding --
            # so long as protect_link_destinations() draws correctly SCOPED
            # spans (WI-0095, closed; see the same proviso on
            # reference_link_span above, which is where a resolving reference
            # also CONSUMES bytes). A second imprecision in that function
            # (WI-0100/WI-0118, CLOSED 26.08.2026 — unbalanced parens inside a
            # destination could pick the wrong `)`) mis-targeted an already
            # correctly scoped span rather than mis-scoping one, so it never
            # reopened this precondition either, before or after the fix.
            # Under that precondition the error it can make is dropping one,
            # and it makes exactly one -- a CLASS, not a shape. The resolution
            # is not INJECTIVE: distinct raw labels share one resolved key, and
            # once any definition owns that key, every other label collapsing
            # to it reads as a resolving reference and silences the link
            # around it. The mapping has two accumulation points:
            #
            #   * the EMPTY key -- a code-span-only label (``[`x`]``), a
            #     literal `[]`, a whitespace-only `[   ]`. The last two are the
            #     wider half: the REFERENCE never looks an empty label up at
            #     all (a label needs one non-whitespace character), while this
            #     side keys on the resolved shape and finds one.
            #   * the `boundary` key -- any label that is exactly one closed
            #     inline comment, so `<!--a-->` and `<!--b-->`, sharing nothing
            #     but their delimiters, are interchangeable here.
            #
            # All four routes are measured, each against a control carrying the
            # same label with NO colliding definition, where the link is still
            # reported -- so the loss is pinned on the collision, not on the
            # label shape. That trade is the PO decision of 24.08.2026 — a
            # false negative in place of a false positive.
            #
            # Which constructs does this cover? Every one either function
            # rewrites, because the label is put through the functions
            # themselves rather than through a list of cases: code spans and
            # closed inline comments from resolve_paragraph(), destination
            # sentinels, escaped-paren marks and decoded numeric entities from
            # protect_link_destinations(). Not covered, and out of scope here:
            # a construct whose resolution depends on text OUTSIDE the label
            # (an unpaired backtick that finds its partner later in the
            # paragraph), where the standalone resolution done here and the
            # in-context resolution done there can still disagree.
            if (match($0, /^[ ]{0,3}\[/)) {
                lstart = RSTART + RLENGTH - 1
                lnum = parse_link_label($0, lstart)
                if (lnum >= 2 && substr($0, lstart + lnum, 1) == ":") {
                    raw_rest = substr($0, lstart + lnum + 1)
                    sub(/^[ \t]+/, "", raw_rest)
                    rawlbl = substr($0, lstart + 1, lnum - 2)
                    reflbl = normalize_label(rawlbl)
                    if (pbuf_n == 0 && reflbl != "" && reference_definition_tail(raw_rest)) {
                        register_reference_definition(reflbl, rawlbl, raw_rest)
                        flush_paragraph()
                        next
                    }
                    # WI-0083: nothing follows the colon on THIS line, but a
                    # definition may still be valid with its destination on
                    # the NEXT one (CommonMark: "optional whitespace,
                    # including up to one line ending", between the colon and
                    # the destination). reference_definition_tail("") itself
                    # always returns 0 (it requires a non-whitespace first
                    # byte), so this can only be reached when the branch
                    # above did not already take it — the two are mutually
                    # exclusive, never a second attempt at the same content.
                    # Deferred, not resolved here: the label and its raw text
                    # are carried into refdef_pending for the NEXT record to
                    # settle (see the check right after the CRLF strip above).
                    if (pbuf_n == 0 && reflbl != "" && raw_rest == "") {
                        refdef_pending = 1
                        refdef_label_raw = $0
                        refdef_reflbl = reflbl
                        refdef_rawlbl = rawlbl
                        next
                    }
                }
                # Not a valid reference definition — fall through so a real
                # `[x](y)` link elsewhere on this line is still found below.
            }

            # WI-0050 block boundaries: a blank line, a list-item marker or a
            # heading each end the current paragraph the way CommonMark ends
            # a block. WI-0082 added the two boundaries WI-0050 left out and
            # named as out of scope: a thematic break and a setext-heading
            # underline. This is still deliberately not a full CommonMark block
            # grammar — a block quote is not modelled as a container (only
            # recognised well enough not to claim a setext boundary inside
            # one), and neither are tables or footnote blocks.
            #
            # A blank line closes the paragraph and carries no content of its
            # own.
            if ($0 ~ /^[ \t]*$/) {
                flush_paragraph()
                next
            }
            # A thematic break (three or more `*`, `-` or `_`, optionally
            # separated by spaces or tabs) is its own block and carries no
            # content of its own — it only ends whatever paragraph was open.
            #
            # ORDER IS LOAD-BEARING, not cosmetic: `- - -` satisfies BOTH this
            # pattern and the list-marker pattern further down, and CommonMark
            # gives the thematic break precedence (measured, `<hr />` — see
            # reference_commonmark-conformance.md). The same collision applies
            # to `* * *`, since `*` is a list marker too; only the `_` form is
            # unambiguous. The consequence is not the break line itself — a
            # line matching this pattern holds nothing but `*`, `-` or `_` plus
            # spaces and tabs, so it never carries a link under either reading
            # — but the line AFTER it: the list branch BUFFERS its own line,
            # leaving pbuf_n at 1, which defeats the indented-code branch below
            # (gated on pbuf_n == 0) and made a link inside a following
            # indented code block visible as a link. This branch buffers
            # nothing, so that gate keeps holding.
            #
            # This branch is deliberately NOT gated on pbuf_para the way the
            # setext branch below is. A break really does end an open list item
            # or block quote (measured: `- item` then `---` gives
            # `<ul><li>item</li></ul><hr />`), so gating it would keep the
            # container buffered and swallow links inside it — a false
            # negative. A mutation test adds the gate and pins that.
            if ($0 ~ /^[ ]{0,3}((\*[ \t]*){3,}|(-[ \t]*){3,}|(_[ \t]*){3,})$/) {
                flush_paragraph()
                next
            }
            # A setext-heading underline closes the paragraph above it into a
            # heading. In PRACTICE this branch only ever sees `=`-runs and the
            # one- and two-character dash runs `-` and `--`: the thematic-break
            # branch above matches three or more dashes and exits with `next`,
            # so no `---` or longer ever reaches here. The reference gives the
            # setext reading precedence over the break for those (measured:
            # a paragraph line then `---` renders `<h2>`, not `<hr />`), but
            # since both branches do nothing except flush, the two orders are
            # indistinguishable in their effect and the order stands.
            #
            # It is a boundary ONLY when there is an ordinary paragraph to
            # underline. With a LIST ITEM or a BLOCK QUOTE open, the reference
            # keeps a `=`-run as lazy continuation INSIDE that container and
            # renders no heading at all (both measured). Flushing there would
            # split a block CommonMark keeps whole and report a link the
            # reference never renders — trading a false negative for a false
            # positive. pbuf_para carries that distinction, and the flag rather
            # than a re-test of the buffered text is what this gate reads: the
            # line that decided is gone by the time the underline arrives.
            #
            # Note the container rule is specific to the runs that reach here.
            # It does NOT generalise to `---`: measured, a list item followed
            # by `---` is not lazy continuation but `<ul><li>…</li></ul><hr />`,
            # and a block quote followed by `---` likewise ends at the break.
            # That is precisely why the thematic-break branch above must stay
            # UNGATED by pbuf_para — see the mutation test that pins it.
            #
            # `pbuf_n > 0` is belt-and-braces, not load-bearing: pbuf_para can
            # only be raised immediately before an append, so a set flag always
            # implies a non-empty buffer, and dropping the pbuf_n test leaves
            # every behaviour test and the whole conformance corpus green
            # (measured). It is kept because it makes the empty-buffer case
            # readable at the gate — with the buffer empty a `=`-run is plain
            # paragraph text (`<p>===</p>` at the reference) and must be
            # buffered rather than flushed.
            #
            # One conservative gap, measured and accepted: an INDENTED
            # underline under a list item (`- item` then `  ===`) renders a
            # heading INSIDE the item at the reference. This branch treats it
            # as a non-boundary, which keeps the paragraph merged — a false
            # negative, the safe direction, and the one this whole gate exists
            # to avoid trading away.
            if (pbuf_n > 0 && pbuf_para && $0 ~ /^[ ]{0,3}(=+|-+)[ \t]*$/) {
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
            # Indented code block (WI-0084): content indented >=4 spaces or a
            # leading tab (a tab reaches the next 4-space stop; matched here by
            # literal-tab presence rather than full tab-stop arithmetic — the
            # only two shapes measured against the reference, see
            # reference_commonmark-conformance.md). Never inline-parsed, so a
            # link inside is not a link. Unlike the HTML blocks above, this
            # construct CANNOT interrupt a paragraph — recomputed per line
            # rather than tracked with a persistent flag: as long as no line is
            # appended to pbuf, pbuf_n stays 0 and every following indented
            # line keeps qualifying (a multi-line block, with or without blank
            # separators inside, is skipped in its entirety this way), while a
            # line that continues an ALREADY-OPEN paragraph (pbuf_n > 0) falls
            # through unchanged to ordinary content below — exactly the
            # "cannot interrupt" rule, without needing its own open/close state.
            if (pbuf_n == 0 && $0 !~ /^[ \t]*$/ && $0 ~ /^(    |\t)/) {
                next
            }
            # Ordinary paragraph content — accumulate, do not resolve yet.
            # This branch also maintains the flag the setext branch above
            # reads: whether what is buffered right now is an ordinary
            # paragraph a setext underline could close.
            #
            # The two halves are deliberately NOT symmetrical, and the
            # asymmetry is the whole point. A block quote may INTERRUPT an
            # open paragraph in CommonMark, so a `>` line clears the flag
            # whether it opens the buffer or arrives mid-paragraph. Measured:
            # a paragraph line, then a quoted line opening a code span around
            # a link, then `===`, then a line closing that span — the
            # reference keeps the underline inside the quote and renders only
            # the trailing link. Gating the clear on pbuf_n == 0 reported the
            # span-buried link as well, a false positive on a shape that was
            # correct before this boundary existed. Setting
            # the flag, by contrast, stays gated on an empty buffer: a
            # continuation line of an already-open container must not promote
            # that container to a plain paragraph.
            #
            # This extractor models no other part of block quotes, and does
            # not start to here — it only declines to claim a setext boundary
            # inside one.
            if ($0 ~ /^[ ]{0,3}>/) pbuf_para = 0
            else if (pbuf_n == 0) pbuf_para = 1
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
        #
        # WI-0084 adds two HTML-block states (in_html_block1, in_html_block6) to
        # this same mutual-exclusion set — each of the four gates at the top of
        # the per-record block unconditionally `next`s, so only one flag can ever
        # be set at a time — but deliberately get NO end-of-input sentinel here.
        # Both are, per CommonMark itself, correctly allowed to run to
        # end-of-document with no closing tag at all ("or the end of the
        # document" is part of the close condition each type defines, not a
        # failure mode) — unlike an unclosed fence or comment, which is virtually always
        # an authoring mistake worth flagging. No case has been measured where a
        # `<div>`/`<pre>`/`<script>` opener left open to EOF was accidental
        # rather than intentional trailing raw HTML.
        END {
            # WI-0083: a label deferred by the last record of the file (a
            # bare `[ref]:` with no following line at all) never got a
            # destination candidate to check — no line 2 exists, so per
            # CommonMark it cannot be a definition, and the deferred label
            # reverts to ordinary paragraph text, same as any other failed
            # lookahead. Resolved before flush_paragraph() runs, same
            # ordering as the per-record check above.
            if (refdef_pending) {
                pbuf_para = 1
                append_paragraph(refdef_label_raw)
            }
            flush_paragraph()
            if (in_fence) print fence_sentinel fence_open_line
            if (in_html_comment) print html_comment_sentinel html_comment_open_line
        }
    ' "$INDEX_FILE" "$INDEX_FILE")  # exit-status: exempt proc-subst-unobservable
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
