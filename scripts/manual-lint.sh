#!/usr/bin/env bash
# manual-lint.sh — Read-only validator for a documentation index/detail-file
# contract (WI-0112a). Schema: templates/PHASE_DOC_SCHEMA.md, `## kind`
# section (vocabulary) and the `parent_index` row (resolution rule).
#
# Checks:
#   (a) parent_index resolves to an existing file — document-relative
#       first, root-fallback second. Same cascade phase-docs-lint.sh's
#       checks (f)/(g) already implement (scripts/phase-docs-lint.sh:274-
#       297), reused rather than reinvented: the fallback base there is
#       the project-directory argument (PROJECT_DIR); here, since this
#       script is generic over ANY root rather than hardwired to a
#       project layout, the fallback base is this script's own ROOT
#       argument — the same role, translated to a generic root.
#   (b) the REVERSE direction: an index named as `parent_index` by a
#       detail file must itself link that detail file back (a markdown
#       link whose destination is the document-relative path from the
#       index's own directory to the detail file). PHASE_DOC_SCHEMA.md
#       has named this direction as a documented-but-unvalidated
#       convention since it shipped ("Index-↔-detail consistency" —
#       "Nothing checks them"); this is the first check that does.
#   (c) `kind:` — when set, must be one of the vocabulary documented in
#       templates/PHASE_DOC_SCHEMA.md's `## kind` section.
#
# Usage:
#   bash scripts/manual-lint.sh [<root-dir>]
#
# Generic over ANY documentation root — NOT hardwired to Manual/.
# install.sh does not copy Manual/ into ~/.claude (see Manual/README.md:2-5),
# so a script that defaulted to it would find nothing on every installed
# CCPR — the exact defect 0e76919 fixed for phase-docs-lint.sh's
# PHASE_FOLDERS default. Point it at whichever tree carries the
# kind/parent_index contract, e.g. `bash scripts/manual-lint.sh Manual`.
#
# Exit-Codes: 0 clean, 1 warnings, 2 errors.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/frontmatter.sh
source "$SCRIPT_DIR/lib/frontmatter.sh"

ROOT="${1:-$(pwd)}"

# The kind: vocabulary — measured across this repository 26.08.2026 (WI-0112a):
# every distinct value any shipped file, template, or command prescribes.
# Mirrored verbatim in templates/PHASE_DOC_SCHEMA.md's `## kind` section —
# keep both in sync when a new kind is introduced.
VALID_KINDS="adr api-resource-detail commands-doc-detail component-detail constitution detail entity-detail epic-detail frame learnings promotion-brief review risk-detail setup-detail sprint-detail sub-index system-doc-detail track-decision wireframe-detail"

is_valid_kind() {
    local k="$1"
    for v in $VALID_KINDS; do
        [[ "$k" == "$v" ]] && return 0
    done
    return 1
}

# rel_path <from_dir_abs> <to_file_abs> — the relative path FROM a
# directory TO a file, both given as absolute, already-normalized paths
# (produced via `cd ... && pwd`, so neither carries a ".." segment).
# Purely string-based: bash 3.2 (macOS default) ships no `realpath`, and
# the system `realpath` binary is not guaranteed present either. Splits
# both paths on "/", walks the shared prefix, then emits one "../" per
# remaining `from` segment followed by the remaining `to` segments —
# the canonical document-relative form this repository's own Manual/
# links already use (`[…](system/agents.md)`, no leading "./", no
# fragment): check (b) below does a literal substring match against
# that exact shape, not a general link-destination parser.
rel_path() {
    local from="$1" to="$2"
    local IFS=/
    local -a from_parts to_parts
    read -r -a from_parts <<< "$from"
    read -r -a to_parts <<< "$to"
    local i=0
    while [[ $i -lt ${#from_parts[@]} && $i -lt ${#to_parts[@]} \
        && "${from_parts[$i]}" == "${to_parts[$i]}" ]]; do
        i=$((i + 1))
    done
    local up=$(( ${#from_parts[@]} - i ))
    local result="" j=0
    while [[ $j -lt $up ]]; do
        result="../$result"
        j=$((j + 1))
    done
    local k=$i
    while [[ $k -lt ${#to_parts[@]} ]]; do
        result="${result}${to_parts[$k]}"
        k=$((k + 1))
        [[ $k -lt ${#to_parts[@]} ]] && result="${result}/"
    done
    printf '%s' "$result"
}

errors=()
warnings=()
infos=()
err()  { errors+=("$1"); }
warn() { warnings+=("$1"); }
info() { infos+=("$1"); }

# Collect files. A missing ROOT is not distinguished from an existing-but-
# empty one in FILES_TOTAL — both end up scanning zero files — but the
# stderr notice below names which of the two it was, since "0 files
# scanned, 0 errors" would otherwise read as a clean pass either way
# (WI-0090/WI-0121 convention: an empty scan says so on stderr, not silence).
FILES=()
if [[ -d "$ROOT" ]]; then
    while IFS= read -r line; do
        FILES+=("$line")
    done < <(find "$ROOT" -type f -name "*.md")
fi
FILES_TOTAL=${#FILES[@]}

if [[ "$FILES_TOTAL" -eq 0 ]]; then
    if [[ ! -d "$ROOT" ]]; then
        echo "manual-lint: root '$ROOT' does not exist" >&2
    else
        echo "manual-lint: no markdown files found under $ROOT" >&2
    fi
fi

# ROOT_ABS — ROOT resolved to an absolute path once, up front, so every
# later "make this path human-readable relative to ROOT" strip (both in
# the per-file loop below and in check (b)) works against the SAME base
# regardless of whether ROOT itself was given relative or absolute on the
# command line. Only computed when ROOT exists — find() above already
# left FILES empty for a missing ROOT, so this is unreachable in that case.
ROOT_ABS=""
[[ -d "$ROOT" ]] && ROOT_ABS="$(cd "$ROOT" && pwd)"

# PARENT_LINKS — "idx_abs_path|child_abs_path" entries, one per file whose
# parent_index resolved (via check (a)'s cascade) to an existing index.
# Consumed by check (b) below, once the per-file pass has finished — bash
# 3.2 has no associative arrays, so this is a flat pair list rather than a
# idx -> [children] map, grouped back out by a sort -u over the idx column.
PARENT_LINKS=()

for file in ${FILES[@]+"${FILES[@]}"}; do
    rel="${file#$ROOT/}"
    base_dir="$(dirname "$file")"

    # (c) kind: vocabulary — opt-in, only fires when kind: is actually set.
    kind_val="$(fm_field "$file" kind || true)"
    if [[ -n "$kind_val" ]] && ! is_valid_kind "$kind_val"; then
        err "$rel — kind='$kind_val' is not in the defined vocabulary (see templates/PHASE_DOC_SCHEMA.md)"
    fi

    # (a) parent_index — document-relative first, ROOT-fallback second,
    # same two-step cascade as phase-docs-lint.sh checks (f)/(g)
    # (scripts/phase-docs-lint.sh:274-297): a document-relative hit stays
    # silent (the documented, preferred form), a ROOT-relative hit is
    # reported as `info` so the fallback usage stays visible rather than
    # unnoticed drift, and neither resolving is an `err`.
    parent_idx="$(fm_field "$file" parent_index || true)"
    idx_resolved=""
    if [[ -n "$parent_idx" ]]; then
        if [[ -f "$base_dir/$parent_idx" ]]; then
            idx_resolved="$base_dir/$parent_idx"
        elif [[ -f "$ROOT/$parent_idx" ]]; then
            idx_resolved="$ROOT/$parent_idx"
            info "$rel — parent_index='$parent_idx' resolved via root fallback ($ROOT/$parent_idx), not found relative to $base_dir"
        else
            err "$rel — parent_index='$parent_idx' points to non-existent file"
        fi
    fi

    if [[ -n "$idx_resolved" ]]; then
        idx_abs="$(cd "$(dirname "$idx_resolved")" && pwd)/$(basename "$idx_resolved")"
        file_abs="$(cd "$base_dir" && pwd)/$(basename "$file")"
        PARENT_LINKS+=("$idx_abs|$file_abs")
    fi
done

# (b) Reverse direction — the index an existing parent_index resolved to
# must itself link the claiming file back. Grouped by unique index path so
# each index's content is read once, not once per child.
if [[ ${#PARENT_LINKS[@]} -gt 0 ]]; then
    while IFS= read -r idx_path; do
        [[ -z "$idx_path" ]] && continue
        idx_dir="$(dirname "$idx_path")"
        idx_content="$(cat "$idx_path")"
        idx_rel="${idx_path#$ROOT_ABS/}"
        for pair in "${PARENT_LINKS[@]}"; do
            this_idx="${pair%%|*}"
            [[ "$this_idx" == "$idx_path" ]] || continue
            child="${pair#*|}"
            child_rel="${child#$ROOT_ABS/}"
            target="$(rel_path "$idx_dir" "$child")"
            # A here-string, not a pipe: under `set -o pipefail` a
            # `printf | grep -qF` can report the whole pipeline as failed
            # via SIGPIPE precisely when grep exits early on a match while
            # printf is still writing the rest of a large index — turning a
            # real hit into a reported miss (measured 16% false-negative
            # rate at ~37 KB of content). A here-string keeps grep as the
            # only command in the statement, so there is no producer left
            # to receive SIGPIPE. Not switched to `grep -qF ... "$idx_path"`
            # instead, because idx_content is deliberately read ONCE per
            # index above and reused across every child in this inner loop
            # (see the comment on the outer `while` below) — grepping the
            # file directly here would re-read it once per child again. On
            # bash 3.2 (this repo's minimum target) a here-string larger
            # than the pipe buffer is written through a temp file rather
            # than an in-memory fd, which is a performance cost, not a
            # correctness one — real Manual/-sized index files are nowhere
            # near where that would matter.
            if ! grep -qF "]($target)" <<< "$idx_content"; then
                warn "$idx_rel — does not link back to $child_rel, which names it as parent_index (expected a link to '$target')"
            fi
        done
    done < <(printf '%s\n' "${PARENT_LINKS[@]}" | cut -d'|' -f1 | sort -u)
fi

# Report output
NOW="$(date '+%d.%m.%Y %H:%M')"
echo "# Manual Lint Report"
echo
echo "**Root:** $ROOT"
echo "**Checks:** (a) parent_index resolves (document-relative first, root-fallback second) · (b) the resolved index links the claiming file back · (c) kind: is in the defined vocabulary"
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
