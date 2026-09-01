#!/usr/bin/env bash
# doc-volume-check.sh — Read-only watcher for doc volume
# Lists files >25/40/50 KB and suggests splitting candidates.
#
# Thresholds (consistent with PROJECT_PHASES.md Document-Splitting-Convention):
#   info    25–40 KB  — splitting recommended
#   warning 40–50 KB  — splitting urgent
#   error   ≥50 KB    — read-fail risk (cf. G-017)
#
# Splitting heuristic: ≥6 H2 sections → "split-per-H2"
#
# Usage:
#   bash ~/.claude/scripts/doc-volume-check.sh [<docs-root>]
#
# Exit-Codes: 0 clean, 1 warnings, 2 errors.
#
# --- scope: tracked files only, inside a git working tree (WI-0129 Paket B,
# cycle B2) ---------------------------------------------------------------
#
# This check exists to flag oversized SHIPPED documentation pending a split
# (CONTRIBUTING.md's "known, stable baseline of findings"), not an adopter's
# own untracked working state -- drafts, persona memory silos
# (docs/memory/** is gitignored in this repository), generated reports.
# Measured directly on this repository's own working tree (30.08.2026): of
# 19 findings, all 5 critical and all 6 warning were untracked; only 3 of 8
# info findings were tracked -- a CI runner on a fresh checkout reproduces
# every one of those 16 untracked findings every single time, none of them a
# regression.
#
# <docs-root> is one directory BELOW the repository root (it is always
# invoked with <project>/docs, never <project> itself) -- git resolves its
# own working tree by walking up from cwd, so `git -C "$DOCS_ROOT" ...`
# still finds it.
#
# Outside a git working tree (no .git found anywhere above <docs-root>),
# every file under <docs-root> is scanned, exactly as before this cycle --
# there is no "tracked" concept to apply, and this script has always
# supported a bare, non-git docs-root (it takes no project-identity
# argument at all).
#
# Behavioural note for adopters, named rather than left silent: a project
# with real, UNTRACKED docs (drafts not yet committed) will see FEWER
# findings after this change than before. That is intentional -- this check
# is about documentation the project SHIPS, not the author's current
# working state -- but it is a real behaviour change, so the report itself
# names how many files were skipped as untracked (see "Untracked skipped"
# below), the same "say what was NOT covered" discipline artifact-gate.sh
# already applies to its own binary/symlink skips.

set -euo pipefail

DOCS_ROOT="${1:-$(pwd)/docs}"

if [[ ! -d "$DOCS_ROOT" ]]; then
    echo "doc-volume-check: $DOCS_ROOT does not exist"
    exit 0
fi

NOW="$(date '+%d.%m.%Y %H:%M')"

# AUTOLOAD_PROJECT_ROOT is computed here, ahead of both git-tracked-detection
# blocks below, because the autoload corpus's own tracked-list needs it and
# it is pure path arithmetic (no dependency on anything scan-related) --
# see the "autoloaded context corpus" comment block further down for what
# AUTOLOAD_PROJECT_ROOT and AUTOLOAD_ROOT_FILE mean.
AUTOLOAD_PROJECT_ROOT="$(dirname "$DOCS_ROOT")"

# TRACKED_ONLY is resolved once, before the scan, from whether <docs-root>
# sits inside a git working tree at all -- not from whether any individual
# file inside it happens to be tracked.
TRACKED_ONLY=0
TRACKED_LIST_FILE=""
if git -C "$DOCS_ROOT" rev-parse --show-toplevel >/dev/null 2>&1; then
    TRACKED_ONLY=1
    TRACKED_LIST_FILE="$(mktemp)"
    # `git -C "$DOCS_ROOT" ls-files` (no pathspec) lists tracked files AT OR
    # BELOW $DOCS_ROOT, with paths already relative to it -- exactly the
    # same `rel` shape the scan loop below computes for every candidate
    # file, so the two can be compared byte-for-byte with no path rewriting.
    git -C "$DOCS_ROOT" ls-files -z 2>/dev/null \
        | while IFS= read -r -d '' relf; do printf '%s\n' "$relf"; done > "$TRACKED_LIST_FILE"  # exit-status: exempt set-e-sufficient
fi

# AUTOLOAD_TRACKED_ONLY mirrors TRACKED_ONLY above, but resolved against
# AUTOLOAD_PROJECT_ROOT instead of DOCS_ROOT -- the autoload corpus's own
# candidates are rooted at the project root (CLAUDE.md and its `@import`
# chain), not under docs/, so they need their own tracked-list computed
# relative to that root. WHY this restriction applies here too (PO override,
# no work item, 01.09.2026 -- reversing the original "does not apply here"
# design below): this tool judges the SHIPPED state -- what `check-all.sh`
# sees from a fresh clone of a given commit -- not one machine's local
# Claude Code setup. An untracked file reachable only through someone's own
# uncommitted `@import` line in their local CLAUDE.md is real context cost
# on THEIR machine, but it does not exist in the shipped commit, so a
# `check-all.sh` run against that same commit from a different machine
# would never see it. Reporting it here made the SAME commit fail
# differently depending on who ran the check -- measured directly: an
# untracked 59 KB file reached via `@autoload-probe.md` in CLAUDE.md turned
# a clean run into "1 critical" / exit 2, with no change to the repository
# at all. This is the class 46fbcf9 (30.08.2026) removed from the
# DOCS_ROOT scope, reached through the autoload corpus instead of docs/.
AUTOLOAD_TRACKED_ONLY=0
AUTOLOAD_TRACKED_LIST_FILE=""
if git -C "$AUTOLOAD_PROJECT_ROOT" rev-parse --show-toplevel >/dev/null 2>&1; then
    AUTOLOAD_TRACKED_ONLY=1
    AUTOLOAD_TRACKED_LIST_FILE="$(mktemp)"
    git -C "$AUTOLOAD_PROJECT_ROOT" ls-files -z 2>/dev/null \
        | while IFS= read -r -d '' relf; do printf '%s\n' "$relf"; done > "$AUTOLOAD_TRACKED_LIST_FILE"  # exit-status: exempt set-e-sufficient
fi

# Single combined trap, set once both tracked-list temp files are known (an
# empty string is a safe no-op `rm -f` argument) -- `trap ... EXIT` REPLACES
# any previous EXIT handler rather than accumulating, so this must not be
# called twice.
trap 'rm -f "$TRACKED_LIST_FILE" "$AUTOLOAD_TRACKED_LIST_FILE"' EXIT

# is_tracked <repo-relative-path> — true when TRACKED_ONLY is off (nothing to
# apply), or when <path> is a line in TRACKED_LIST_FILE. LC_ALL=C: an exact
# byte match against git's own byte-for-byte path output, not a
# locale-sensitive comparison (same reasoning memory-lint.sh's LC_ALL=C awk
# invocations already give for this codebase's grep/awk calls).
is_tracked() {
    local rel="$1"
    [[ "$TRACKED_ONLY" -eq 1 ]] || return 0
    LC_ALL=C grep -qxF -- "$rel" "$TRACKED_LIST_FILE"  # exit-status: exempt propagates-as-function-return
}

# is_autoload_tracked <project-root-relative-path> — same shape as
# is_tracked(), against AUTOLOAD_TRACKED_ONLY / AUTOLOAD_TRACKED_LIST_FILE
# instead. Kept as a separate function rather than parameterising is_tracked
# with indirect variable expansion -- this codebase prefers the small,
# duplicated, obviously-correct form over cleverness (see _autoload_seen_has
# next to it below for the same trade-off already made once in this file).
is_autoload_tracked() {
    local rel="$1"
    [[ "$AUTOLOAD_TRACKED_ONLY" -eq 1 ]] || return 0
    LC_ALL=C grep -qxF -- "$rel" "$AUTOLOAD_TRACKED_LIST_FILE"  # exit-status: exempt propagates-as-function-return
}

# --- autoloaded context corpus ---------------------------------------------
#
# A DIFFERENT subject from the scope above: not "shipped documentation
# pending a split", but "the documents Claude Code loads into EVERY
# session". Those cost every adopter context every time, and nothing
# measured them before this cycle.
#
# Per ADR-0012 (derived values are not stored) the class is DERIVED, not
# typed: starting at <project-root>/CLAUDE.md, follow `^@<path>$` import
# lines transitively, each resolved relative to the FILE THAT IMPORTS IT
# (not the project root, not the file doing the importing two hops back).
# No allowlist, no typed exception -- a file simply NAMED like CLAUDE.md
# (e.g. templates/CLAUDE_LEAN_TEMPLATE.md, a template instantiated per
# adopter project, never itself imported) is excluded by the graph walk
# itself, with nothing to maintain when it changes shape.
#
# <project-root> is one directory ABOVE $DOCS_ROOT -- the mirror image of
# the "<docs-root> is one directory BELOW the repository root" note above,
# since this script is always invoked with <project>/docs.
#
# Scope decisions made explicitly rather than left implicit:
#   - Only the PROJECT ROOT CLAUDE.md is a start point. Claude Code also
#     loads a CLAUDE.md from the cwd/its ancestors and from
#     .claude/CLAUDE.md, but those describe THIS machine's checkout
#     location and local Claude Code installation, not this repository --
#     a script run from a fresh clone cannot know what sits above it on
#     someone else's disk, and .claude/CLAUDE.md is local operator
#     configuration the repository does not ship. Scanning only
#     <project-root>/CLAUDE.md keeps the result identical on every clone.
#   - docs/CLAUDE-lean.md is not a Claude Code autoload source at all (it
#     is a Lean-track artifact adopter PROJECTS generate for themselves);
#     nothing imports it from CLAUDE.md, so the graph walk excludes it
#     without a named exception either way.
#   - The import graph (this section) decides WHICH FILES ARE CANDIDATES;
#     AUTOLOAD_TRACKED_ONLY (see is_autoload_tracked() above) decides WHICH
#     OF THOSE CANDIDATES GET REPORTED. The two are deliberately separate
#     steps: a candidate stays a candidate (counted in "Autoloaded context
#     files found") whether or not it is tracked, but only a TRACKED
#     candidate can raise a finding or move the exit code -- because this
#     tool judges the SHIPPED state (what a fresh clone of a given commit
#     loads), not this one machine's local Claude Code setup. Reversed
#     01.09.2026 (PO override, no work item) from the original "does not apply
#     here" design -- see the AUTOLOAD_TRACKED_ONLY comment above for the
#     measured consequence of the original design and why it was wrong.
AUTOLOAD_ROOT_FILE="$AUTOLOAD_PROJECT_ROOT/CLAUDE.md"

autoload_seen=()
autoload_files=()

# _autoload_seen_has <resolved-key> — linear scan, no associative arrays:
# bash 3.2 (macOS's shipped /bin/bash) has none, and the corpus this walks
# is a handful of files, never a scale where this matters.
_autoload_seen_has() {
    local needle="$1" x
    (( ${#autoload_seen[@]} == 0 )) && return 1
    for x in "${autoload_seen[@]}"; do
        [[ "$x" == "$needle" ]] && return 0
    done
    return 1
}

# _autoload_resolve <path> — an absolute, symlink-normalised dedup key when
# <path> exists on disk; the raw candidate unchanged otherwise (still a
# usable, inspectable key for a broken import, and never crashes the walk).
_autoload_resolve() {
    local candidate="$1" dir
    if [[ -f "$candidate" ]]; then
        dir="$(cd "$(dirname "$candidate")" && pwd -P)"
        printf '%s/%s\n' "$dir" "$(basename "$candidate")"
    else
        printf '%s\n' "$candidate"
    fi
}

# _autoload_collect <root-file> — breadth-first walk of `^@<path>$` import
# lines starting at <root-file>, appending every FILE THAT EXISTS to
# autoload_files. Each import target is resolved relative to the
# DIRECTORY OF THE FILE CONTAINING THE IMPORT LINE, not the walk's own
# starting point -- so a nested import (sub/inner.md importing @deep.md)
# lands on sub/deep.md, not <root>/deep.md.
_autoload_collect() {
    local queue=("$1")
    local current resolved dir line target
    while (( ${#queue[@]} > 0 )); do
        current="${queue[0]}"
        queue=("${queue[@]:1}")
        resolved="$(_autoload_resolve "$current")"
        _autoload_seen_has "$resolved" && continue
        autoload_seen+=("$resolved")
        [[ -f "$current" ]] || continue
        autoload_files+=("$current")
        dir="$(dirname "$current")"
        while IFS= read -r line; do
            line="${line%$'\r'}"
            [[ "$line" =~ ^@(.+)$ ]] || continue
            target="${BASH_REMATCH[1]}"
            queue+=("$dir/$target")
        done < "$current"
    done
}

# File size in KB via wc -c (portable)
size_kb() {
    local file="$1"
    local bytes
    bytes="$(wc -c < "$file" | tr -d ' ')"
    echo $(( (bytes + 512) / 1024 ))
}

# Number of H2 sections (lines starting with "## " but not "### ")
h2_count() {
    local file="$1"
    local count
    # grep -c PRINTS "0" and STILL exits 1 when nothing matched. An
    # `|| echo 0` arm therefore fires ON TOP of that printed zero and makes
    # this function emit "0\n0", which breaks every (( )) below (WI-0101).
    # The arm must REPLACE the value, never add one -- so it is an
    # assignment, and it only ever takes effect when grep failed for a real
    # reason (exit 2) and printed nothing at all.
    count="$(grep -c '^## [^#]' "$file" 2>/dev/null)" || count=0
    echo "$count"
}

# Splitting suggestion
split_suggestion() {
    local file="$1"
    local h2
    h2="$(h2_count "$file")"
    if (( h2 >= 6 )); then
        echo "split-per-H2 ($h2 H2 sections)"
    elif (( h2 >= 3 )); then
        echo "moderate splitting possible ($h2 H2 sections)"
    else
        echo "no obvious splitting point ($h2 H2 sections) — review content"
    fi
}

# Collect and classify the autoloaded-context corpus now that size_kb/
# split_suggestion exist. Same thresholds, same suggestion heuristic as
# DOCS_ROOT -- the two corpora differ in WHICH files are in scope, not in
# how a found file is judged.
_autoload_collect "$AUTOLOAD_ROOT_FILE"

autoload_errors=()
autoload_warnings=()
autoload_infos=()

for file in "${autoload_files[@]:-}"; do
    [[ -n "$file" ]] || continue
    rel="${file#$AUTOLOAD_PROJECT_ROOT/}"
    # A candidate stays a candidate (see the "Scope decisions" comment
    # above _autoload_collect's call site) but only a TRACKED candidate can
    # become a finding -- an untracked candidate is skipped here, silently
    # with respect to the count above (it was already counted as "found"),
    # never counted as a finding.
    is_autoload_tracked "$rel" || continue
    kb="$(size_kb "$file")"

    if (( kb >= 50 )); then
        autoload_errors+=("$rel (${kb} KB, critical) → $(split_suggestion "$file")")
    elif (( kb >= 40 )); then
        autoload_warnings+=("$rel (${kb} KB, warning) → $(split_suggestion "$file")")
    elif (( kb >= 25 )); then
        autoload_infos+=("$rel (${kb} KB, info) → $(split_suggestion "$file")")
    fi
done

errors=()
warnings=()
infos=()

# Scan
FILES_TOTAL=0
UNTRACKED_SKIPPED=0
while IFS= read -r file; do
    rel="${file#$DOCS_ROOT/}"
    if ! is_tracked "$rel"; then
        UNTRACKED_SKIPPED=$((UNTRACKED_SKIPPED + 1))
        continue
    fi
    FILES_TOTAL=$((FILES_TOTAL + 1))
    kb="$(size_kb "$file")"

    if (( kb >= 50 )); then
        errors+=("$rel (${kb} KB) → $(split_suggestion "$file")")
    elif (( kb >= 40 )); then
        warnings+=("$rel (${kb} KB) → $(split_suggestion "$file")")
    elif (( kb >= 25 )); then
        infos+=("$rel (${kb} KB) → $(split_suggestion "$file")")
    fi
done < <(find "$DOCS_ROOT" -type f -name "*.md" -not -path "*/.handover-archive/*")

# Report
echo "# Doc Volume Report"
echo
echo "**Scope:** $DOCS_ROOT/"
echo "**Run:** $NOW"
echo "**Files scanned:** $FILES_TOTAL"
if [[ "$TRACKED_ONLY" -eq 1 && "$UNTRACKED_SKIPPED" -gt 0 ]]; then
    echo "**Untracked skipped:** $UNTRACKED_SKIPPED file(s) not tracked by git — not shipped documentation, not scanned"
fi
echo "**Autoloaded context root:** $AUTOLOAD_ROOT_FILE"
echo "**Autoloaded context files found:** ${#autoload_files[@]}"
echo

echo "## Critical (≥50 KB) — Splitting required (${#errors[@]})"
echo
if [[ ${#errors[@]} -eq 0 ]]; then echo "_none_"; fi
for e in "${errors[@]:-}"; do [[ -n "$e" ]] && echo "- $e"; done
echo

echo "## Warning (40–50 KB) — Splitting urgent (${#warnings[@]})"
echo
if [[ ${#warnings[@]} -eq 0 ]]; then echo "_none_"; fi
for w in "${warnings[@]:-}"; do [[ -n "$w" ]] && echo "- $w"; done
echo

echo "## Info (25–40 KB) — Splitting recommended (${#infos[@]})"
echo
if [[ ${#infos[@]} -eq 0 ]]; then echo "_none_"; fi
for i in "${infos[@]:-}"; do [[ -n "$i" ]] && echo "- $i"; done
echo

autoload_total=$(( ${#autoload_errors[@]} + ${#autoload_warnings[@]} + ${#autoload_infos[@]} ))
echo "## Autoloaded Context (≥25 KB) — documents Claude Code loads into every session ($autoload_total)"
echo
if (( autoload_total == 0 )); then echo "_none_"; fi
for e in "${autoload_errors[@]:-}"; do [[ -n "$e" ]] && echo "- $e"; done
for w in "${autoload_warnings[@]:-}"; do [[ -n "$w" ]] && echo "- $w"; done
for i in "${autoload_infos[@]:-}"; do [[ -n "$i" ]] && echo "- $i"; done
echo

echo "---"
echo
echo "**Summary:** ${#errors[@]} critical, ${#warnings[@]} warning, ${#infos[@]} info."
echo "**Autoloaded summary:** ${#autoload_errors[@]} critical, ${#autoload_warnings[@]} warning, ${#autoload_infos[@]} info."

if (( ${#errors[@]} > 0 || ${#autoload_errors[@]} > 0 )); then
    echo "**Exit:** 2"
    exit 2
elif (( ${#warnings[@]} > 0 || ${#autoload_warnings[@]} > 0 )); then
    echo "**Exit:** 1"
    exit 1
fi
echo "**Exit:** 0"
exit 0
