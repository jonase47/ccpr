#!/usr/bin/env bash
# anchor.sh — Stage-1 (mechanical, no-verdict) anchored-state check.
# Design: docs/adr/ADR-0009-anchored-state-verification.md, especially
# Addendum 2 ("A7 resolved — where the scope anchor lives") and the
# "comparison point, measured" section it closes with.
#
# Usage:
#   bash scripts/anchor.sh status [<project-dir>]
#   bash scripts/anchor.sh check  [<project-dir>] [--scope <folder>]
#   bash scripts/anchor.sh set    [<project-dir>] --scope <folder> [--commit <sha>] [--force]
#   bash scripts/anchor.sh ack    <target> [--assert|--update] --note "<text>" [--by <actor>]
#
# The anchor lives on the phase INDEX (docs/<folder>/<INDEX>.md), not on
# every detail file (ADR-0009 §2/§3, Addendum 2). A document under that
# scope inherits the index's anchor unless it carries its own
# `anchor_commit` (opt-in, typically alongside `covers:`). No third tier.
#
# Exit-code contract — deliberately DIFFERENT from phase-docs-lint.sh:
#   `check` (and `status`) never render a verdict at Stage 1 (ADR-0009,
#   "the check is two-stage, and staleness is never itself a verdict").
#   So: exit 0 once a report was produced, drift or no drift. A nonzero
#   exit means only an OPERATIONAL failure — no git repo, no docs/, an
#   unknown argument — never a content finding. Do not "fix" this to mirror
#   phase-docs-lint's 0/1/2 severity scale; that scale answers a different
#   question than this script does.
#
#   0  status/check: a report was produced (with or without drift).
#      set/ack: the anchor was written/acknowledged.
#   2  the run could not be performed as asked (bad usage, no git repo,
#      no docs/ structure, no drift to acknowledge, a target with no
#      anchor of its own, a target outside every phase scope, or an
#      interactive `ack` aborted by the user)
#   3  set: the index already carries an anchor and --force was not
#      given -- a DEDICATED code (WI-0021 review), not folded into 2, so
#      freeze-phase-docs.sh's anchor hook can tell this apart from every
#      other `set` failure by exit code alone rather than a message grep.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/frontmatter.sh
source "$SCRIPT_DIR/lib/frontmatter.sh"

PROG="anchor"

# --- constants ------------------------------------------------------------

# folder:index pairs — the anchor's scope-resolution convention (ADR-0009
# Addendum 2, "The phase-index naming convention holds where the index
# exists"). No `reviews` entry: review reports have no phase index and are
# out of scope for this mechanism entirely, unlike phase-docs-lint.sh's
# PHASE_FOLDERS (which gives `reviews` its own restricted lint profile).
PHASE_SCOPES=(
    "discovery:DISCOVERY.md"
    "concept:CONCEPT.md"
    "validation:VALIDATION.md"
    "architecture:ARCHITECTURE.md"
    "planning:PROJECT_PLAN.md"
    "quality:QA.md"
    "launch:LAUNCH.md"
    "operations:OPERATIONS.md"
)

# Same living-file set as phase-docs-lint.sh (duplicated rather than
# sourced: that script is an entry point with its own `set -euo pipefail`
# run body, not a library — sourcing it would execute its whole scan).
LIVING_FILES="HANDOVER.md BASELINE.md BACKLOG.md SPRINT.md MEMORY.md instincts.md"

is_living_file() {
    local bn="$1" lf
    for lf in $LIVING_FILES; do
        [[ "$bn" == "$lf" ]] && return 0
    done
    return 1
}

usage() {
    sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'  # exit-status: exempt set-e-sufficient
}

die() {
    echo "$PROG: $*" >&2
    exit 2
}

# --- classification (WI-0021, ADR-0009 "the comparison point, measured") --
#
# A commit is production-code if it touches at least one path that is
# neither under docs/, nor under .claude/, nor a Markdown file — exclusion
# rather than inclusion, because inclusion lists do not travel between
# projects (three reference projects, three unrelated code trees) while
# every CCPR-driven project shares docs/ and .claude/.
#
# Configurable, additively, via .claude/settings.json's `anchor.excludePaths`
# (a list of prefixes ending in "/" or suffixes such as ".md"/"*.md"). This
# EXTENDS the default rather than replacing it — a project narrowing what it
# excludes would silently start treating docs/ or .claude/ as code, which is
# never the intent of adding a project-specific exclusion.
#
# WI-0123: four repo-/editor-hygiene suffixes join the default, decided by
# one question — does the file describe the system that runs, or only how
# the repository or the editor is handled? `.gitignore`, `.gitattributes`,
# `.editorconfig` and `.prettierignore` answer "only how the repo/editor is
# handled" and are excluded. `.dockerignore` (determines image contents),
# `.env.example` (declares required configuration) and
# `.nvmrc`/`.tool-versions` (pin the runtime) answer "the system that runs"
# and are deliberately NOT excluded — see ADR-0009 "The comparison point,
# measured" for the full argument and why this is a shipped default rather
# than a per-project exclusion (every project has these files; none of them
# is production-relevant in any project).
EXCLUDE_PREFIXES=("docs/" ".claude/")
EXCLUDE_SUFFIXES=(".md" ".gitignore" ".gitattributes" ".editorconfig" ".prettierignore")
CLASSIFICATION_SOURCE="default"

# load_exclude_config <project-dir> — best-effort. Missing file, missing
# `anchor` key, or no python3 on PATH: silently keep the default (per the
# work item: "Fehlt die Datei, der Schlüssel oder python3, gilt der
# Default"). Mirrors lib/discipline_gate.sh's `_gate_read_config` shape
# (python3 heredoc, one entry per line, `2>/dev/null || true`) rather than
# inventing a second JSON-reading convention.
load_exclude_config() {
    local project_dir="$1"
    local cfg="$project_dir/.claude/settings.json"
    [[ -f "$cfg" ]] || return 0
    command -v python3 >/dev/null 2>&1 || return 0

    local entry
    while IFS= read -r entry; do
        [[ -z "$entry" ]] && continue
        CLASSIFICATION_SOURCE="project (.claude/settings.json)"
        if [[ "$entry" == */ ]]; then
            EXCLUDE_PREFIXES+=("$entry")
        else
            EXCLUDE_SUFFIXES+=("${entry#\*}")
        fi
    done < <(python3 - "$cfg" <<'PY' 2>/dev/null || true  # exit-status: exempt optional-config-read
import json, sys
try:
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(0)
anchor_cfg = cfg.get("anchor") or {}
paths = anchor_cfg.get("excludePaths") or []
if isinstance(paths, str):
    paths = [paths]
for p in paths:
    p = str(p).strip()
    if p:
        print(p)
PY
)
}

# is_production_path <repo-relative-path>
is_production_path() {
    local p="$1" pre suf
    for pre in "${EXCLUDE_PREFIXES[@]}"; do
        case "$p" in "$pre"*) return 1 ;; esac
    done
    for suf in "${EXCLUDE_SUFFIXES[@]}"; do
        case "$p" in *"$suf") return 1 ;; esac
    done
    return 0
}

classification_description() {
    local pre_list suf_list
    pre_list="$(IFS=,; echo "${EXCLUDE_PREFIXES[*]}")"
    suf_list="$(IFS=,; echo "${EXCLUDE_SUFFIXES[*]}")"
    printf 'exclude prefixes: %s · exclude suffixes: %s (source: %s)' \
        "$pre_list" "$suf_list" "$CLASSIFICATION_SOURCE"
}

# scopes_found_summary <scope-filter-or-empty> — Befund 2 (WI-0021 review,
# 21.08.2026): a report that never states how many of the eight phase
# folders it actually found is indistinguishable from a report that found
# none of them, since both end on the identical "0 anchored" line. Counts
# against the SAME PHASE_SCOPES list report_scope_check()/
# report_scope_status_line() walk, and "found" means only "the folder
# exists under docs/" — never a claim about anchoring, which stays a
# separate, later question.
scopes_found_summary() {
    local scope_filter="$1" total=0 found=0 folder scope_entry
    for scope_entry in "${PHASE_SCOPES[@]}"; do
        folder="${scope_entry%%:*}"
        if [[ -n "$scope_filter" && "$folder" != "$scope_filter" ]]; then
            continue
        fi
        total=$((total + 1))
        [[ -d "$PROJECT_DIR/docs/$folder" ]] && found=$((found + 1))
    done
    if [[ -n "$scope_filter" ]]; then
        printf '%d of %d phase folder (scope: %s)' "$found" "$total" "$scope_filter"
    else
        printf '%d of %d phase folders' "$found" "$total"
    fi
}

# --- git state (the six edge cases named in the work item) ----------------

GIT_CHECKABLE=0
IS_SHALLOW=0
HAS_COMMITS=0
DIRTY_TREE=0
LAST_PROD_SHA=""
LAST_PROD_DATE=""
PROD_COMMIT_SEARCHED=0

# `-e`, not `-d`: a linked worktree's or a submodule's `.git` is a FILE
# (`gitdir: /path/to/real/.git/...`), not a directory — see
# phase-docs-lint.sh's identical guard and its comment for the incident this
# fixed there.
require_git_repo() {
    local project_dir="$1"
    if [[ ! -e "$project_dir/.git" ]] || ! command -v git >/dev/null 2>&1; then
        die "not a git repository (or git not on PATH): $project_dir"
    fi
    GIT_CHECKABLE=1
}

require_docs_dir() {
    local project_dir="$1"
    [[ -d "$project_dir/docs" ]] || die "no docs/ structure found under $project_dir"
}

compute_git_state() {
    local project_dir="$1"

    if [[ "$(git -C "$project_dir" rev-parse --is-shallow-repository 2>/dev/null || true)" == "true" ]]; then  # exit-status: exempt downstream-checks-result
        IS_SHALLOW=1
    fi

    if git -C "$project_dir" rev-parse --verify -q HEAD >/dev/null 2>&1; then
        HAS_COMMITS=1
    fi

    if [[ -n "$(git -C "$project_dir" status --porcelain 2>/dev/null || true)" ]]; then  # exit-status: exempt downstream-checks-result
        DIRTY_TREE=1
    fi
}

# find_last_prod_commit <project-dir> — walks HEAD's history newest-first
# (works identically in a detached HEAD, since it never touches a ref name)
# and returns (via LAST_PROD_SHA/LAST_PROD_DATE) the first commit whose
# changed paths contain at least one production-code path per
# is_production_path(). `--root` on diff-tree so the very first commit of a
# repository is classified too (otherwise diff-tree shows nothing for a
# commit with no parent). Runs once per invocation, not once per scope.
find_last_prod_commit() {
    local project_dir="$1" sha path
    PROD_COMMIT_SEARCHED=1
    [[ "$HAS_COMMITS" == "1" ]] || return 1

    # `--pretty=tformat:%H`, NOT `format:%H`: `format:` deliberately omits
    # the trailing newline after the LAST entry (documented git behaviour),
    # which makes `read` return 1 on that final line and silently skips the
    # loop body for it under `while read`. That is exactly the single-commit
    # repository and the "root commit is the answer" case — reproduced
    # directly against a `--depth 1` shallow clone before this fix, where a
    # one-commit `git log` output produced zero loop iterations and a false
    # "no production-code commit found".
    while IFS= read -r sha; do
        [[ -z "$sha" ]] && continue
        while IFS= read -r path; do
            [[ -z "$path" ]] && continue
            if is_production_path "$path"; then
                LAST_PROD_SHA="$sha"
                LAST_PROD_DATE="$(git -C "$project_dir" show -s --format=%ad --date=format:%d.%m.%Y "$sha" 2>/dev/null || true)"  # exit-status: exempt best-effort-status-display
                return 0
            fi
        done < <(git -C "$project_dir" diff-tree --no-commit-id --name-only -r --root "$sha" 2>/dev/null)  # exit-status: exempt proc-subst-unobservable
    done < <(git -C "$project_dir" log --pretty=tformat:%H 2>/dev/null)  # exit-status: exempt proc-subst-unobservable

    return 1
}

# --- scope / document anchor resolution ------------------------------------

# doc_effective_anchor <file> <index-file-or-empty>
# Sets ANCH_COMMIT / ANCH_DATE / ANCH_SOURCE ("own" / "index" / "none").
# Resolution per ADR-0009 Addendum 2: the document's own anchor_commit if
# present, else its phase index's. No third tier.
doc_effective_anchor() {
    local file="$1" index_file="$2"
    local own_c own_d idx_c idx_d

    own_c="$(fm_field "$file" anchor_commit || true)"
    if [[ -n "$own_c" ]]; then
        ANCH_COMMIT="$own_c"
        ANCH_DATE="$(fm_field "$file" anchor_date || true)"
        ANCH_SOURCE="own"
        return 0
    fi

    if [[ -n "$index_file" && -f "$index_file" ]]; then
        idx_c="$(fm_field "$index_file" anchor_commit || true)"
        if [[ -n "$idx_c" ]]; then
            ANCH_COMMIT="$idx_c"
            ANCH_DATE="$(fm_field "$index_file" anchor_date || true)"
            ANCH_SOURCE="index"
            return 0
        fi
    fi

    ANCH_COMMIT=""
    ANCH_DATE=""
    ANCH_SOURCE="none"
    return 1
}

# scope_documents <project-dir> <folder> — one full-profile, non-living
# document path per line, matching phase-docs-lint.sh's (full profile)
# collection for the same folder (no reviews/ folder is ever passed here,
# see PHASE_SCOPES above, so the reviews-profile distinction never applies).
scope_documents() {
    local project_dir="$1" folder="$2" file bn
    [[ -d "$project_dir/docs/$folder" ]] || return 0
    while IFS= read -r file; do
        bn="$(basename "$file")"
        is_living_file "$bn" && continue
        printf '%s\n' "$file"
    done < <(find "$project_dir/docs/$folder" -type f -name "*.md" | sort)
}

# anchor_compare_state <project-dir> <anchor-sha> — sets the global
# ANCHOR_COMPARE_STATE to one of:
#   ok               comparison possible, CHANGED_PROD_PATHS/ANCHOR_COMPARE_DISTANCE set
#   shallow          IS_SHALLOW=1 — cannot compare
#   unresolvable     <anchor-sha> does not resolve to a commit here
#   no-prod-commit   the repo has commits, but none is production-code
# On "ok", also fills the global array CHANGED_PROD_PATHS with the
# production-code paths that differ between <anchor-sha> and the last
# production-code commit (`git diff` needs no ancestry between the two, so
# an anchor that is not an ancestor of HEAD still compares), and sets
# ANCHOR_COMPARE_DISTANCE to `git rev-list --count <anchor>..<last-prod>`
# — the "Abstand in Commits" the work item's `status` report requires per
# scope. Counted separately from the changed-PATH list: a scope can have a
# large commit distance and a small (or filtered-to-zero) changed-path set,
# or vice versa, and collapsing the two would hide exactly the
# documentation-only-commits case ADR-0009 is written against.
#
# Deliberately NOT called via `$(...)`: this function's whole point is a
# side effect on CHANGED_PROD_PATHS, and a command substitution runs its
# command in a SUBSHELL — an array built there evaporates the instant the
# substitution returns. State travels back through globals instead.
CHANGED_PROD_PATHS=()
ANCHOR_COMPARE_STATE=""
ANCHOR_COMPARE_DISTANCE=""
anchor_compare_state() {
    local project_dir="$1" anchor_sha="$2"
    CHANGED_PROD_PATHS=()
    ANCHOR_COMPARE_STATE=""
    ANCHOR_COMPARE_DISTANCE=""

    if [[ "$IS_SHALLOW" == "1" ]]; then
        ANCHOR_COMPARE_STATE="shallow"
        return 0
    fi
    if ! git -C "$project_dir" rev-parse --verify -q "${anchor_sha}^{commit}" >/dev/null 2>&1; then
        ANCHOR_COMPARE_STATE="unresolvable"
        return 0
    fi
    if [[ "$PROD_COMMIT_SEARCHED" == "1" && -z "$LAST_PROD_SHA" ]]; then
        ANCHOR_COMPARE_STATE="no-prod-commit"
        return 0
    fi

    ANCHOR_COMPARE_DISTANCE="$(git -C "$project_dir" rev-list --count "${anchor_sha}..${LAST_PROD_SHA}" 2>/dev/null || true)"  # exit-status: exempt best-effort-status-display

    local path
    while IFS= read -r path; do
        [[ -z "$path" ]] && continue
        if is_production_path "$path"; then
            CHANGED_PROD_PATHS+=("$path")
        fi
    done < <(git -C "$project_dir" diff --name-only "${anchor_sha}" "${LAST_PROD_SHA}" -- 2>/dev/null)  # exit-status: exempt proc-subst-unobservable

    ANCHOR_COMPARE_STATE="ok"
}

# path_is_covered <path> <covers-entry> — a directory covers: entry (checked
# against the real filesystem, existing-directory or trailing "/") matches
# by prefix; anything else matches only exactly, same distinction
# phase-docs-lint.sh's check (h) already draws for existence, applied here
# to path membership instead.
path_is_covered() {
    local project_dir="$1" path="$2" entry="$3"
    if [[ "$entry" == */ ]] || [[ -d "$project_dir/$entry" ]]; then
        local prefix="${entry%/}/"
        case "$path" in "$prefix"*) return 0 ;; esac
        return 1
    fi
    [[ "$path" == "$entry" ]]
}

# --- check delta helpers (WI-0021 review, 21.08.2026) ----------------------
#
# report_scope_check() resolves each document's delta against its OWN
# effective anchor (ADR-0009 Addendum 2: own anchor_commit before the
# index's), not a single delta shared by the whole scope — Befund 3 of the
# review: a document with an up-to-date own anchor has no drift and must
# not be reported as affected merely because the scope's INDEX anchor is
# older. The two helpers below are shared by the index-inherited delta
# block and the own-anchor block so both go through identical logic.

# claimants_for_path <project-dir> <folder> <idx-anchor> <path> — echoes a
# comma-joined list of every scope document (relative path) whose covers:
# entries match <path>, restricted to documents that share <idx-anchor> as
# their effective anchor (no own anchor_commit, or one equal to
# <idx-anchor>) — a document with a DIFFERING own anchor is resolved, and
# claim-checked, separately in the own-anchor block. Reports ALL
# claimants, not just the first: two covers: lists silently overlapping on
# the same path used to lose the second claimant entirely (review Punkt
# 3) — covers: only ever REFINES the scope signal (ADR-0009 §3), it does
# not get to silently narrow who is on the hook for a path.
claimants_for_path() {
    local project_dir="$1" folder="$2" idx_anchor="$3" path="$4"
    local doc rel_doc own_c covers_entry result=""
    while IFS= read -r doc; do
        [[ -z "$doc" ]] && continue
        own_c="$(fm_field "$doc" anchor_commit || true)"
        [[ -n "$own_c" && "$own_c" != "$idx_anchor" ]] && continue
        while IFS= read -r covers_entry; do
            [[ -z "$covers_entry" ]] && continue
            if path_is_covered "$project_dir" "$path" "$covers_entry"; then
                rel_doc="${doc#"$project_dir"/}"
                if [[ -z "$result" ]]; then
                    result="$rel_doc"
                else
                    result="$result, $rel_doc"
                fi
                break
            fi
        done < <(fm_list "$doc" covers)
    done < <(scope_documents "$project_dir" "$folder")
    printf '%s' "$result"
}

# doc_affected_by_delta <project-dir> <doc> — echoes "1" if <doc> is
# affected by the delta currently held in the global DELTA_PATHS array:
# either at least one of its covers: entries matches a path in
# DELTA_PATHS, or it carries no covers: at all and DELTA_PATHS is
# non-empty (ADR-0009 §3 — a document without covers: inherits the WHOLE
# scope's delta rather than claiming nothing). Echoes "0" otherwise. The
# caller sets the DELTA_PATHS global before calling this — bash 3.2 has no
# `local -n`/nameref for passing an array by name, same constraint
# CHANGED_PROD_PATHS/anchor_compare_state already work around.
DELTA_PATHS=()
doc_affected_by_delta() {
    local project_dir="$1" doc="$2"
    local covers_entry cpath has_covers=0
    while IFS= read -r covers_entry; do
        [[ -z "$covers_entry" ]] && continue
        has_covers=1
        # `[[ ${#DELTA_PATHS[@]} -gt 0 ]]` guard first: a bare
        # `"${DELTA_PATHS[@]}"` on a declared-but-empty array crashes under
        # `set -u` in bash 3.2 (reproduced directly, 21.08.2026) — DELTA_PATHS
        # is empty exactly when the caller found "ok" but zero changed paths.
        if [[ ${#DELTA_PATHS[@]} -gt 0 ]]; then
            for cpath in "${DELTA_PATHS[@]}"; do
                if path_is_covered "$project_dir" "$cpath" "$covers_entry"; then
                    echo 1
                    return 0
                fi
            done
        fi
    done < <(fm_list "$doc" covers)

    if [[ "$has_covers" == "0" && ${#DELTA_PATHS[@]} -gt 0 ]]; then
        echo 1
        return 0
    fi
    echo 0
}

# --- report plumbing --------------------------------------------------------

NOW_FMT() { date '+%d.%m.%Y %H:%M'; }

print_git_notes() {
    if [[ "$DIRTY_TREE" == "1" ]]; then
        echo "**Note:** working tree has uncommitted changes — they are not reflected in the delta below."
    fi
    if [[ "$HAS_COMMITS" == "0" ]]; then
        echo "**Note:** repository has no commits yet."
    fi
}

# --- ack (WI-0021 wave 4b) ---------------------------------------------
#
# Usage: bash anchor.sh ack <target> [--assert|--update] --note "<text>"
# No <project-dir> — the target path is resolved against $(pwd), matching
# how a human runs this from inside their checkout.
#
# ADR-0009 §6: acknowledgement renders the delta BEFORE it clears it, and
# is NEVER a side effect of another command — the single highest-risk
# detail in the whole design. Reach is structural: whichever file is
# passed as <target> IS the file that gets acked (a phase index -> bulk
# acknowledgement, a document with its own anchor_commit -> a document
# acknowledgement) — there is deliberately no --scope option that would
# let the two blur together.

parse_ack_args() {
    TARGET=""
    ASSERT_FLAG=0
    UPDATE_FLAG=0
    NOTE=""
    ACK_BY_OVERRIDE=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --assert)
                ASSERT_FLAG=1
                shift
                ;;
            --update)
                UPDATE_FLAG=1
                shift
                ;;
            --note)
                [[ $# -ge 2 ]] || die "--note needs a value"
                NOTE="$2"
                shift 2
                ;;
            --note=*)
                NOTE="${1#--note=}"
                shift
                ;;
            --by)
                # Overrides the resolved git identity (ADR-0009 Addendum 3,
                # "attribution, not restriction") -- no validation against
                # any allowlist, by design: this is a display value, not an
                # authority check.
                [[ $# -ge 2 ]] || die "--by needs a value"
                ACK_BY_OVERRIDE="$2"
                shift 2
                ;;
            --by=*)
                ACK_BY_OVERRIDE="${1#--by=}"
                shift
                ;;
            -*)
                die "unknown argument '$1'"
                ;;
            *)
                if [[ -z "$TARGET" ]]; then
                    TARGET="$1"
                else
                    die "unknown argument '$1'"
                fi
                shift
                ;;
        esac
    done
    # All argument-shape validation happens HERE, before require_git_repo
    # ever runs -- the same ordering `set`'s parser already uses for its
    # own bad-usage cases.
    [[ -n "$TARGET" ]] || die "anchor ack requires a target path (docs/<folder>/<INDEX>.md or a document carrying its own anchor_commit)"
    if [[ "$ASSERT_FLAG" == "1" && "$UPDATE_FLAG" == "1" ]]; then
        die "--assert and --update are mutually exclusive"
    fi
    if [[ "$ASSERT_FLAG" == "1" || "$UPDATE_FLAG" == "1" ]]; then
        # Non-interactive mode has no prompt to fall back on -- a reason
        # is not optional, it is the ceremony this verb exists to prevent
        # (ADR-0009 §6).
        [[ -n "$NOTE" ]] || die "--note is required and must not be empty when using --assert/--update"
    fi
}

# is_in_anchor_scope <target-file> — true iff <target-file> lives under
# docs/<folder>/ for one of the eight PHASE_SCOPES folders, relative to
# the CURRENT working directory (the same base resolve_ack_target itself
# resolves a relative target against). ADR-0009 §6: the scope-line's
# "X anchored · Y asserted · Z stale" count IS the fallback detection net
# in the absence of a hard technical block on agents -- scope_documents()
# only ever WALKS the eight folders, so a target outside all of them
# would silently never appear in that count, whether or not `ack`
# accepted it (WI-0021 review, Important 3, reproduced directly: a
# document under docs/somewhere/ carrying its own anchor_commit could be
# acked successfully and stayed invisible to `status`'s statistics).
is_in_anchor_scope() {
    local target_file="$1" scope_entry folder prefix
    for scope_entry in "${PHASE_SCOPES[@]}"; do
        folder="${scope_entry%%:*}"
        prefix="$(pwd)/docs/$folder/"
        case "$target_file" in "$prefix"*) return 0 ;; esac
    done
    return 1
}

# ANCHOR_ACK_NO_IDENTITY — the anchor_ack_by placeholder written when no
# git identity is configurable (a CI job, a fresh container: `user.email`
# empty). Deliberately NOT omitted (ADR-0009 Addendum 3: "a missing field
# and an unattributable acknowledgement must not look alike") and
# deliberately containing no "@" -- so it can never be mistaken for, or
# collide with, a real actor's email when `anchor status` groups by it.
ANCHOR_ACK_NO_IDENTITY="unattributable <no-git-identity>"

# get_ack_identity <project-dir> — resolves the "name <email>" actor string
# for anchor_ack_by. Identity is keyed on `user.email` FIRST (ADR-0009
# Addendum 3: the same person can appear under several `user.name` values
# over time -- keying on the display name would record the drift instead
# of the person). `user.name` travels along only for readability, in the
# same "name <email>" shape git itself writes into every commit.
get_ack_identity() {
    local project_dir="$1" name email
    email="$(git -C "$project_dir" config user.email 2>/dev/null || true)"  # exit-status: exempt downstream-checks-result
    if [[ -z "$email" ]]; then
        printf '%s' "$ANCHOR_ACK_NO_IDENTITY"
        return 0
    fi
    name="$(git -C "$project_dir" config user.name 2>/dev/null || true)"  # exit-status: exempt downstream-checks-result
    if [[ -z "$name" ]]; then
        # user.email set but user.name not -- git itself normally refuses
        # to COMMIT in this state, so this is a narrow edge case. Fall back
        # to the email as its own display name rather than writing a
        # malformed "<email>" with no name segment.
        name="$email"
    fi
    printf '%s <%s>' "$name" "$email"
}

# resolve_ack_target <target> — sets TARGET_FILE (absolute path),
# TARGET_REL (relative to $(pwd)), OLD_ANCHOR, OLD_DATE. Structural reach:
# the target's OWN anchor_commit is what gets acknowledged, whether that
# file is a phase index (bulk) or a document with its own opt-in anchor
# (ADR-0009 §3/§6) — no separate index-vs-document branch is needed
# because both shapes store the SAME field on the SAME file.
resolve_ack_target() {
    local target="$1" target_file
    if [[ "$target" = /* ]]; then
        target_file="$target"
    else
        target_file="$(pwd)/$target"
    fi
    [[ -f "$target_file" ]] || die "no such document: $target"

    is_in_anchor_scope "$target_file" || die "$target is outside every phase scope (docs/<discovery|concept|validation|architecture|planning|quality|launch|operations>/) -- acknowledging it would be invisible to 'anchor status's anchored/asserted/stale count (ADR-0009 §6)"

    TARGET_FILE="$target_file"
    TARGET_REL="$target"

    OLD_ANCHOR="$(fm_field "$target_file" anchor_commit || true)"  # exit-status: exempt downstream-checks-result
    [[ -n "$OLD_ANCHOR" ]] || die "$TARGET_REL carries no anchor_commit of its own -- nothing to acknowledge here (a phase index needs 'anchor set' first; a document needs its own opt-in anchor_commit)"
    OLD_DATE="$(fm_field "$target_file" anchor_date || true)"  # exit-status: exempt downstream-checks-result
}

cmd_ack() {
    parse_ack_args "$@"
    PROJECT_DIR="$(pwd)"
    require_git_repo "$PROJECT_DIR"
    require_docs_dir "$PROJECT_DIR"
    load_exclude_config "$PROJECT_DIR"
    compute_git_state "$PROJECT_DIR"
    find_last_prod_commit "$PROJECT_DIR" || true

    resolve_ack_target "$TARGET"

    anchor_compare_state "$PROJECT_DIR" "$OLD_ANCHOR"
    case "$ANCHOR_COMPARE_STATE" in
        shallow)
            die "cannot compare -- shallow clone (anchor $OLD_ANCHOR on $TARGET_REL)"
            ;;
        unresolvable)
            die "anchor_commit '$OLD_ANCHOR' on $TARGET_REL does not resolve to a commit in this repository"
            ;;
        no-prod-commit)
            die "no production-code commit found in this repository -- nothing to compare $TARGET_REL's anchor against"
            ;;
    esac

    if [[ ${#CHANGED_PROD_PATHS[@]} -eq 0 ]]; then
        die "$TARGET_REL has no drift against its anchor ($OLD_ANCHOR) -- no drift means nothing to acknowledge"
    fi

    # "Renders the delta before it clears it" (ADR-0009 §6) — printed
    # BEFORE the interactive prompt (or, in flagged mode, before the
    # write), in both modes alike.
    echo "Anchor  $OLD_ANCHOR  ($OLD_DATE)"
    echo "Last production-code commit  $LAST_PROD_SHA  ($LAST_PROD_DATE)"
    echo
    echo "Changed production-code paths (${#CHANGED_PROD_PATHS[@]}):"
    local changed_path
    for changed_path in "${CHANGED_PROD_PATHS[@]}"; do
        echo "  - $changed_path"
    done
    echo

    local kind note
    if [[ "$ASSERT_FLAG" == "1" ]]; then
        kind="asserted"
        note="$NOTE"
    elif [[ "$UPDATE_FLAG" == "1" ]]; then
        kind="updated"
        note="$NOTE"
    else
        # A closed/non-interactive stdin still reaches this branch (a
        # background CI job, an agent tool call that never redirects
        # stdin) -- without --assert/--update there is no fallback but
        # `read`, which BLOCKS FOREVER on a pipe that is open but never
        # fed. A CLOSED pipe is different: it hits EOF immediately and
        # already exits cleanly via the `read || choice=""` -> "aborted,
        # nothing written" path a few lines down. A fast, clear failure
        # beats an invisible hang in automation (WI-0021 review,
        # Important 4).
        #
        # CCPR_ANCHOR_FORCE_INTERACTIVE is a TEST-ONLY escape hatch
        # (never documented in usage(), never read anywhere else in this
        # script): it lets the test suite drive the interactive
        # asserted/abort flow through a piped stdin (no real TTY)
        # without weakening this guard for a genuine non-interactive
        # run.
        if [[ ! -t 0 && -z "${CCPR_ANCHOR_FORCE_INTERACTIVE:-}" ]]; then
            die "ack requires --assert or --update when stdin is not a terminal"
        fi
        echo "Does the document's claim still hold?  [asserted/updated/abort]"
        local choice
        IFS= read -r choice || choice=""
        case "$choice" in
            asserted|updated)
                kind="$choice"
                ;;
            *)
                echo "anchor ack: aborted, nothing written" >&2
                exit 2
                ;;
        esac
        echo "Reason:"
        IFS= read -r note || note=""
        [[ -n "$note" ]] || die "a reason is required -- acknowledging without one is the ceremony this verb exists to prevent"
    fi

    local ack_by
    if [[ -n "$ACK_BY_OVERRIDE" ]]; then
        ack_by="$ACK_BY_OVERRIDE"
    else
        ack_by="$(get_ack_identity "$PROJECT_DIR")"
    fi

    # ONE atomic group write, not six separate fm_set calls (WI-0021
    # review, Critical fix -- anchor_ack_by rides in the SAME group per
    # ADR-0009 Addendum 3, not a seventh, separate call). Each fm_set call
    # is individually atomic (temp file + `mv`), but the GROUP was not: an
    # abort between the first and the second call (signal, full disk,
    # write error) used to leave the document carrying the NEW
    # anchor_commit but NONE of the anchor_ack fields -- `status` then
    # reads "no anchor_ack" as "anchor up to date", and the drift this
    # command exists to record vanishes without ever having been
    # acknowledged. ADR-0009 §6 names this "the single highest-risk detail
    # in the whole design". No authority check on $ack_by anywhere here --
    # ack records who asserted, it does not gate on it (Addendum 3,
    # "attribution, not restriction").
    fm_set_many "$TARGET_FILE" \
        "anchor_commit=$LAST_PROD_SHA" \
        "anchor_date=$LAST_PROD_DATE" \
        "anchor_ack=$kind" \
        "anchor_ack_from=$OLD_ANCHOR" \
        "anchor_ack_note=$note" \
        "anchor_ack_by=$ack_by"

    echo "anchor ack: $TARGET_REL -> $kind ($OLD_ANCHOR -> $LAST_PROD_SHA)"
    exit 0
}

# --- set ---------------------------------------------------------------

parse_set_args() {
    PROJECT_DIR=""
    SCOPE_FOLDER=""
    COMMIT_SHA=""
    FORCE=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --scope)
                [[ $# -ge 2 ]] || die "--scope needs a folder name"
                SCOPE_FOLDER="$2"
                shift 2
                ;;
            --scope=*)
                SCOPE_FOLDER="${1#--scope=}"
                shift
                ;;
            --commit)
                [[ $# -ge 2 ]] || die "--commit needs a SHA"
                COMMIT_SHA="$2"
                shift 2
                ;;
            --commit=*)
                COMMIT_SHA="${1#--commit=}"
                shift
                ;;
            --force)
                FORCE=1
                shift
                ;;
            -*)
                die "unknown argument '$1'"
                ;;
            *)
                if [[ -z "$PROJECT_DIR" ]]; then
                    PROJECT_DIR="$1"
                else
                    die "unknown argument '$1'"
                fi
                shift
                ;;
        esac
    done
    PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
    # Argument-shape validation happens HERE, before require_git_repo ever
    # runs — same ordering parse_check_args/parse_status_args already use
    # for their own bad-usage cases, so a missing --scope is a usage error
    # that needs no repository to detect.
    [[ -n "$SCOPE_FOLDER" ]] || die "set requires --scope <folder>"
}

# resolve_scope_index <folder> — sets INDEX_NAME to the phase index's
# filename for <folder> per PHASE_SCOPES, or dies naming the known scopes.
resolve_scope_index() {
    local folder="$1" scope_entry candidate
    INDEX_NAME=""
    for scope_entry in "${PHASE_SCOPES[@]}"; do
        candidate="${scope_entry%%:*}"
        if [[ "$candidate" == "$folder" ]]; then
            INDEX_NAME="${scope_entry#*:}"
            return 0
        fi
    done
    die "unknown scope '$folder' (expected one of: discovery, concept, validation, architecture, planning, quality, launch, operations)"
}

# cmd_set — writes anchor_commit/anchor_date onto the phase INDEX of
# --scope (ADR-0009 Addendum 2: the scope anchor lives on the index, not
# on every detail file). Refuses when the index already carries an
# anchor unless --force is given: a silent overwrite discards drift
# nobody has reviewed yet, the same risk ADR-0009 §6 names as the
# highest-risk detail in the whole design for `ack` — a bare `set`
# overwrite is the same shape of mistake, one command earlier.
cmd_set() {
    parse_set_args "$@"
    require_git_repo "$PROJECT_DIR"
    require_docs_dir "$PROJECT_DIR"

    resolve_scope_index "$SCOPE_FOLDER"
    local index_file="$PROJECT_DIR/docs/$SCOPE_FOLDER/$INDEX_NAME"
    [[ -f "$index_file" ]] || die "no phase index found at docs/$SCOPE_FOLDER/$INDEX_NAME -- anchor set does not create one"

    local commit_sha="$COMMIT_SHA" commit_date
    if [[ -n "$commit_sha" ]]; then
        git -C "$PROJECT_DIR" rev-parse --verify -q "${commit_sha}^{commit}" >/dev/null 2>&1 \
            || die "--commit '$commit_sha' does not resolve to a commit in this repository"
    else
        # Without --commit: the last PRODUCTION-CODE commit, never HEAD —
        # the same "the comparison point, measured" classification `check`
        # and `status` already use, so `set` and the read side never
        # disagree about what "the code" means.
        load_exclude_config "$PROJECT_DIR"
        compute_git_state "$PROJECT_DIR"
        find_last_prod_commit "$PROJECT_DIR" || true
        [[ -n "$LAST_PROD_SHA" ]] || die "no production-code commit found -- pass --commit <sha> explicitly"
        commit_sha="$LAST_PROD_SHA"
    fi

    local existing_anchor
    existing_anchor="$(fm_field "$index_file" anchor_commit || true)"  # exit-status: exempt downstream-checks-result
    if [[ -n "$existing_anchor" && "$FORCE" != "1" ]]; then
        # Exit code 3, NOT the generic bad-usage 2 `die` uses (WI-0021
        # review, small fix #2): freeze-phase-docs.sh's anchor hook needs
        # to tell "already anchored" (its own normal, expected
        # second-run outcome) apart from every OTHER `set` failure. The
        # exit code IS the contract; a message grep may still run
        # alongside it as a redundant sanity check, but never as the
        # sole signal coupling the two scripts together.
        echo "$PROG: docs/$SCOPE_FOLDER/$INDEX_NAME already carries an anchor ($existing_anchor) -- re-anchoring without review would silently discard drift nobody has seen; pass --force to overwrite, or use 'anchor ack' to acknowledge it deliberately" >&2
        exit 3
    fi

    commit_date="$(git -C "$PROJECT_DIR" show -s --format=%ad --date=format:%d.%m.%Y "$commit_sha" 2>/dev/null || true)"  # exit-status: exempt best-effort-status-display

    fm_set "$index_file" anchor_commit "$commit_sha"
    fm_set "$index_file" anchor_date "$commit_date"

    echo "anchor set: docs/$SCOPE_FOLDER/$INDEX_NAME -> $commit_sha ($commit_date)"
    exit 0
}

# --- check ------------------------------------------------------------------

parse_check_args() {
    PROJECT_DIR=""
    SCOPE_FOLDER=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --scope)
                [[ $# -ge 2 ]] || die "--scope needs a folder name"
                SCOPE_FOLDER="$2"
                shift 2
                ;;
            --scope=*)
                SCOPE_FOLDER="${1#--scope=}"
                shift
                ;;
            -*)
                die "unknown argument '$1'"
                ;;
            *)
                if [[ -z "$PROJECT_DIR" ]]; then
                    PROJECT_DIR="$1"
                else
                    die "unknown argument '$1'"
                fi
                shift
                ;;
        esac
    done
    PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
}

cmd_check() {
    parse_check_args "$@"
    require_git_repo "$PROJECT_DIR"
    require_docs_dir "$PROJECT_DIR"
    load_exclude_config "$PROJECT_DIR"
    compute_git_state "$PROJECT_DIR"
    find_last_prod_commit "$PROJECT_DIR" || true

    echo "# Anchor Check Report"
    echo
    echo "**Project:** $PROJECT_DIR"
    echo "**Run:** $(NOW_FMT)"
    echo "**Scope:** ${SCOPE_FOLDER:-all phase folders}"
    echo "**Scopes found:** $(scopes_found_summary "$SCOPE_FOLDER")"
    echo "**Classification:** $(classification_description)"
    if [[ -n "$LAST_PROD_SHA" ]]; then
        echo "**Last production-code commit:** $LAST_PROD_SHA ($LAST_PROD_DATE)"
    else
        echo "**Last production-code commit:** none found"
    fi
    print_git_notes
    echo

    local scope_entry folder index_name
    for scope_entry in "${PHASE_SCOPES[@]}"; do
        folder="${scope_entry%%:*}"
        index_name="${scope_entry#*:}"
        if [[ -n "$SCOPE_FOLDER" && "$folder" != "$SCOPE_FOLDER" ]]; then
            continue
        fi
        [[ -d "$PROJECT_DIR/docs/$folder" ]] || continue
        report_scope_check "$folder" "$index_name"
    done

    echo "**Exit:** 0 (Stage 1 — data only, never a verdict)"
    exit 0
}

report_scope_check() {
    local folder="$1" index_name="$2"
    local index_file="$PROJECT_DIR/docs/$folder/$index_name"

    echo "## $folder"
    echo

    local idx_anchor="" idx_date=""
    if [[ -f "$index_file" ]]; then
        idx_anchor="$(fm_field "$index_file" anchor_commit || true)"
        idx_date="$(fm_field "$index_file" anchor_date || true)"
    fi

    # Index-level status. Befund 1 (WI-0021 review, 21.08.2026): this used
    # to `return 0` on every branch here, before scope_documents() ever
    # ran — so a document carrying its OWN anchor_commit under an
    # index-less scope (the normal shape: `quality/QA.md` is missing in
    # all three reference projects while docs/quality/ exists and holds
    # documents) was never resolved. The index's own verdict and the
    # per-document resolution below are now independent.
    local idx_has_delta=0
    local -a idx_changed=()
    if [[ ! -f "$index_file" ]]; then
        echo "**Index:** not verified — no phase index (docs/$folder/$index_name)"
        echo
    elif [[ -z "$idx_anchor" ]]; then
        echo "**Index:** not verified — index has no anchor_commit (docs/$folder/$index_name)"
        echo
    else
        anchor_compare_state "$PROJECT_DIR" "$idx_anchor"
        case "$ANCHOR_COMPARE_STATE" in
            shallow)
                echo "**Index anchor:** $idx_anchor ($idx_date) — cannot compare (shallow clone)"
                echo
                ;;
            unresolvable)
                echo "**Index status:** anchor does not resolve — anchor_commit='$idx_anchor' (docs/$folder/$index_name)"
                echo
                ;;
            no-prod-commit)
                echo "**Index status:** not verified — no production-code commit found in this repository"
                echo
                ;;
            ok)
                idx_has_delta=1
                # NOT `"${CHANGED_PROD_PATHS[@]:-}"`: on a DECLARED-but-EMPTY
                # array, bash 3.2's `${arr[@]:-default}` still applies the
                # default and yields ONE empty-string element, not zero
                # elements — reproduced directly (21.08.2026) as a phantom
                # "- — unclaimed" line. And a bare `"${arr[@]}"` on an empty
                # array crashes under `set -u` (the array-vs-unset
                # distinction bash 3.2 gets wrong either way) — reproduced
                # directly too. The only safe copy is: check the length
                # first, only expand `[@]` when it is provably non-empty.
                idx_changed=()
                if [[ ${#CHANGED_PROD_PATHS[@]} -gt 0 ]]; then
                    idx_changed=("${CHANGED_PROD_PATHS[@]}")
                fi
                echo "**Anchor:** $idx_anchor ($idx_date)"
                echo "**Changed production-code paths (${#idx_changed[@]}):**"
                echo
                if [[ ${#idx_changed[@]} -eq 0 ]]; then
                    echo "_none — no delta_"
                    echo
                else
                    # Claim resolution: which document(s) claim each changed
                    # path via their own covers: entries, restricted to
                    # documents sharing this index anchor (an own-anchored
                    # document with a DIFFERING anchor is resolved, and
                    # claim-checked, separately below). A document without
                    # covers: never individually claims a path — per
                    # ADR-0009 §3, covers: REFINES the scope signal, it
                    # never replaces it.
                    local cpath claimed_by
                    for cpath in "${idx_changed[@]}"; do
                        claimed_by="$(claimants_for_path "$PROJECT_DIR" "$folder" "$idx_anchor" "$cpath")"
                        if [[ -n "$claimed_by" ]]; then
                            echo "- $cpath — claimed by $claimed_by"
                        else
                            echo "- $cpath — unclaimed"
                        fi
                    done
                    echo
                fi
                ;;
        esac
    fi

    # Per-document own-anchor delta (Befund 1 + Befund 3, WI-0021 review
    # 21.08.2026): resolved and reported individually, independently of
    # whether the index above was usable — ADR-0009 Addendum 2's
    # precedence (own anchor before index) applies here exactly as
    # `status` already applies it. A document whose own anchor equals the
    # index's is already covered by the index-level block above.
    local -a own_lines=()
    local doc rel_doc own_c own_date
    while IFS= read -r doc; do
        [[ -z "$doc" ]] && continue
        own_c="$(fm_field "$doc" anchor_commit || true)"
        [[ -z "$own_c" ]] && continue
        [[ "$own_c" == "$idx_anchor" ]] && continue
        rel_doc="${doc#"$PROJECT_DIR"/}"
        own_date="$(fm_field "$doc" anchor_date || true)"
        anchor_compare_state "$PROJECT_DIR" "$own_c"
        case "$ANCHOR_COMPARE_STATE" in
            shallow)
                own_lines+=("- $rel_doc — own anchor $own_c ($own_date) · cannot compare (shallow clone)")
                ;;
            unresolvable)
                own_lines+=("- $rel_doc — own anchor $own_c ($own_date) · anchor does not resolve")
                ;;
            no-prod-commit)
                own_lines+=("- $rel_doc — own anchor $own_c ($own_date) · no production-code commit found")
                ;;
            ok)
                if [[ ${#CHANGED_PROD_PATHS[@]} -eq 0 ]]; then
                    own_lines+=("- $rel_doc — own anchor $own_c ($own_date) · no delta")
                else
                    local joined
                    joined="$(IFS=,; echo "${CHANGED_PROD_PATHS[*]}")"
                    joined="${joined//,/, }"
                    own_lines+=("- $rel_doc — own anchor $own_c ($own_date) · changed production-code path(s) (${#CHANGED_PROD_PATHS[@]}): $joined")
                fi
                ;;
        esac
    done < <(scope_documents "$PROJECT_DIR" "$folder")

    if [[ ${#own_lines[@]} -gt 0 ]]; then
        echo "**Documents with their own anchor:**"
        echo
        local line
        for line in "${own_lines[@]}"; do
            echo "$line"
        done
        echo
    fi

    # Affected documents: a document without its own anchor, or with one
    # equal to the index's, is affected per the index-level delta above; a
    # document with its own DIFFERING anchor is affected per ITS OWN delta
    # only — an up-to-date own anchor has no drift and must not appear
    # here even when the index above is stale (Befund 3, WI-0021 review
    # 21.08.2026: `check` now respects the same own-anchor precedence
    # `status` already applied).
    echo "**Affected documents:**"
    echo
    local any_affected=0 doc_status affected
    while IFS= read -r doc; do
        [[ -z "$doc" ]] && continue
        rel_doc="${doc#"$PROJECT_DIR"/}"
        own_c="$(fm_field "$doc" anchor_commit || true)"
        affected=0

        if [[ -n "$own_c" && "$own_c" != "$idx_anchor" ]]; then
            anchor_compare_state "$PROJECT_DIR" "$own_c"
            if [[ "$ANCHOR_COMPARE_STATE" == "ok" ]]; then
                # Same empty-array caveat as the idx_changed copy above.
                DELTA_PATHS=()
                if [[ ${#CHANGED_PROD_PATHS[@]} -gt 0 ]]; then
                    DELTA_PATHS=("${CHANGED_PROD_PATHS[@]}")
                fi
                affected="$(doc_affected_by_delta "$PROJECT_DIR" "$doc")"
            fi
        elif [[ "$idx_has_delta" == "1" ]]; then
            DELTA_PATHS=()
            if [[ ${#idx_changed[@]} -gt 0 ]]; then
                DELTA_PATHS=("${idx_changed[@]}")
            fi
            affected="$(doc_affected_by_delta "$PROJECT_DIR" "$doc")"
        fi

        if [[ "$affected" == "1" ]]; then
            doc_status="$(fm_field "$doc" status || true)"
            echo "- $rel_doc — status: ${doc_status:-(none)}"
            any_affected=1
        fi
    done < <(scope_documents "$PROJECT_DIR" "$folder")
    # `if`/`fi` here, NOT a bare `[[ cond ]] && echo` list: that shape's own
    # exit status is 1 whenever cond is false, which under `set -e` ends
    # the whole script when this is the LAST statement this function
    # executes on the LAST scope iteration — the exact defect
    # report_scope_status_line() was already fixed against earlier in this
    # work item (Punkt 2, WI-0021 review 21.08.2026). The explicit
    # `return 0` below is the second, independent guard against the same
    # shape, matching that fix.
    if [[ "$any_affected" == "0" ]]; then
        echo "_none_"
    fi
    echo
    return 0
}

# --- status -------------------------------------------------------------

parse_status_args() {
    PROJECT_DIR=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -*)
                die "unknown argument '$1'"
                ;;
            *)
                if [[ -z "$PROJECT_DIR" ]]; then
                    PROJECT_DIR="$1"
                else
                    die "unknown argument '$1'"
                fi
                shift
                ;;
        esac
    done
    PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
}

cmd_status() {
    parse_status_args "$@"
    require_git_repo "$PROJECT_DIR"
    require_docs_dir "$PROJECT_DIR"
    load_exclude_config "$PROJECT_DIR"
    compute_git_state "$PROJECT_DIR"
    find_last_prod_commit "$PROJECT_DIR" || true

    echo "# Anchor Status Report"
    echo
    echo "**Project:** $PROJECT_DIR"
    echo "**Run:** $(NOW_FMT)"
    echo "**Scopes found:** $(scopes_found_summary "")"
    echo "**Classification:** $(classification_description)"
    if [[ -n "$LAST_PROD_SHA" ]]; then
        echo "**Last production-code commit:** $LAST_PROD_SHA ($LAST_PROD_DATE)"
    else
        echo "**Last production-code commit:** none found"
    fi
    print_git_notes
    echo
    echo "## Scopes"
    echo

    local anchored=0 asserted=0 stale=0
    local scope_entry folder index_name
    ASSERTED_ACTOR_KEYS=()
    ASSERTED_ACTOR_COUNTS=()
    for scope_entry in "${PHASE_SCOPES[@]}"; do
        folder="${scope_entry%%:*}"
        index_name="${scope_entry#*:}"
        [[ -d "$PROJECT_DIR/docs/$folder" ]] || continue
        report_scope_status_line "$folder" "$index_name"
        # report_scope_status_line updates the shared counters below via
        # STATUS_LINE_ANCHORED/ASSERTED/STALE globals (bash 3.2 has no
        # `local -n`, so counters are threaded back through globals rather
        # than a by-reference parameter). ASSERTED_ACTOR_KEYS/COUNTS
        # accumulate directly (project-wide, not per-scope), so they are
        # reset once above the loop rather than per scope_entry.
        anchored=$((anchored + STATUS_LINE_ANCHORED))
        asserted=$((asserted + STATUS_LINE_ASSERTED))
        stale=$((stale + STATUS_LINE_STALE))
    done

    echo
    echo "**Anchors:** ${anchored} anchored · ${asserted} asserted without doc change · ${stale} stale"
    print_asserted_actor_breakdown
    echo "**Exit:** 0 (Stage 1 — data only, never a verdict)"
    exit 0
}

STATUS_LINE_ANCHORED=0
STATUS_LINE_ASSERTED=0
STATUS_LINE_STALE=0

# --- per-actor breakdown of `asserted` acknowledgements (ADR-0009
# Addendum 3) --------------------------------------------------------------
#
# bash 3.2 has no associative arrays, so counting "how many asserted
# receipts per actor" uses two parallel INDEXED arrays instead — KEYS[i]
# and COUNTS[i] describe the same actor at the same index i. Reset once
# per `status` run (cmd_status, before the scope loop), not per scope: the
# breakdown is a whole-project statistic, unlike STATUS_LINE_* above.
ASSERTED_ACTOR_KEYS=()
ASSERTED_ACTOR_COUNTS=()

# ack_actor_key <doc> — the grouping key for one asserted document: the
# email out of its own anchor_ack_by ("name <email>"), matching
# get_ack_identity's "keyed on user.email first" reasoning so the same
# person under several display names still counts as one actor. A document
# with no anchor_ack_by at all (a receipt written before this field
# existed) keys to the literal "unattributed" — distinct from
# ANCHOR_ACK_NO_IDENTITY's "no-git-identity" placeholder, which IS present
# as a field value and is grouped like any other (unusual) actor string.
ack_actor_key() {
    local doc="$1" ack_by
    ack_by="$(fm_field "$doc" anchor_ack_by || true)"  # exit-status: exempt downstream-checks-result
    if [[ -z "$ack_by" ]]; then
        printf 'unattributed'
        return 0
    fi
    if [[ "$ack_by" == *"<"*">"* ]]; then
        local email="${ack_by#*<}"
        email="${email%%>*}"
        printf '%s' "$email"
    else
        # No "name <email>" shape at all (a hand-edited or unusual --by
        # value) -- fall back to the raw value rather than guessing.
        printf '%s' "$ack_by"
    fi
}

# record_asserted_actor <key> — linear scan over the parallel arrays
# (small N: one entry per distinct actor in a project, never a hot path).
# Iterates by numeric index rather than "${!ASSERTED_ACTOR_KEYS[@]}" so an
# empty array needs no special case under `set -u`.
record_asserted_actor() {
    local key="$1" i=0 n="${#ASSERTED_ACTOR_KEYS[@]}"
    while [[ "$i" -lt "$n" ]]; do
        if [[ "${ASSERTED_ACTOR_KEYS[$i]}" == "$key" ]]; then
            ASSERTED_ACTOR_COUNTS[$i]=$((ASSERTED_ACTOR_COUNTS[$i] + 1))
            return 0
        fi
        i=$((i + 1))
    done
    ASSERTED_ACTOR_KEYS+=("$key")
    ASSERTED_ACTOR_COUNTS+=(1)
}

# print_asserted_actor_breakdown — the "asserted by: ..." line, printed
# only once more than one distinct actor appears (a single actor carries
# no information beyond what "N asserted" already said). Order: descending
# by count, ties broken by first-seen order (stable bubble sort — swap
# only on STRICT "<", never "<=") — matches the ADR's own worked example
# ("a@example.org (6), b@example.org (1)").
print_asserted_actor_breakdown() {
    local n="${#ASSERTED_ACTOR_KEYS[@]}"
    [[ "$n" -le 1 ]] && return 0

    local order=() i=0
    while [[ "$i" -lt "$n" ]]; do
        order+=("$i")
        i=$((i + 1))
    done

    local j a b
    i=0
    while [[ "$i" -lt "$n" ]]; do
        j=0
        while [[ "$j" -lt $((n - 1 - i)) ]]; do
            a="${order[$j]}"
            b="${order[$((j + 1))]}"
            if [[ "${ASSERTED_ACTOR_COUNTS[$a]}" -lt "${ASSERTED_ACTOR_COUNTS[$b]}" ]]; then
                order[$j]="$b"
                order[$((j + 1))]="$a"
            fi
            j=$((j + 1))
        done
        i=$((i + 1))
    done

    local parts="" idx first=1
    for idx in "${order[@]}"; do
        if [[ "$first" == "1" ]]; then
            parts="${ASSERTED_ACTOR_KEYS[$idx]} (${ASSERTED_ACTOR_COUNTS[$idx]})"
            first=0
        else
            parts="$parts, ${ASSERTED_ACTOR_KEYS[$idx]} (${ASSERTED_ACTOR_COUNTS[$idx]})"
        fi
    done
    echo "   asserted by: $parts"
}

report_scope_status_line() {
    local folder="$1" index_name="$2"
    local index_file="$PROJECT_DIR/docs/$folder/$index_name"
    STATUS_LINE_ANCHORED=0
    STATUS_LINE_ASSERTED=0
    STATUS_LINE_STALE=0

    local idx_anchor="" idx_date=""
    if [[ -f "$index_file" ]]; then
        idx_anchor="$(fm_field "$index_file" anchor_commit || true)"
        idx_date="$(fm_field "$index_file" anchor_date || true)"
    fi

    # Befund 1 (WI-0021 review, 21.08.2026): the missing-index and
    # no-anchor cases used to `return 0` HERE, before the document loop
    # below ever ran — so a document carrying its OWN anchor_commit under
    # an index-less scope (the normal shape: `quality/QA.md` is missing in
    # all three reference projects while docs/quality/ exists and holds
    # documents) was never resolved, even though doc_effective_anchor()'s
    # own-anchor branch does not need an index at all. The scope-level
    # line and the per-document resolution below are now independent: this
    # prints the scope's own verdict but never gates the loop.
    local delta_desc scope_has_delta=0
    if [[ ! -f "$index_file" ]]; then
        echo "- $folder → not verified (no phase index: docs/$folder/$index_name)"
    elif [[ -z "$idx_anchor" ]]; then
        echo "- $folder → not verified (index has no anchor_commit)"
    else
        anchor_compare_state "$PROJECT_DIR" "$idx_anchor"
        case "$ANCHOR_COMPARE_STATE" in
            shallow)
                echo "- $folder → anchor $idx_anchor ($idx_date) · cannot compare (shallow clone)"
                ;;
            unresolvable)
                echo "- $folder → anchor $idx_anchor ($idx_date) · anchor does not resolve"
                ;;
            no-prod-commit)
                echo "- $folder → anchor $idx_anchor ($idx_date) · no production-code commit found"
                ;;
            ok)
                if [[ ${#CHANGED_PROD_PATHS[@]} -gt 0 ]]; then
                    scope_has_delta=1
                    delta_desc="delta: yes (${#CHANGED_PROD_PATHS[@]} path(s))"
                else
                    delta_desc="delta: no"
                fi
                echo "- $folder → anchor $idx_anchor ($idx_date) · last prod-code $LAST_PROD_SHA ($LAST_PROD_DATE) · ${ANCHOR_COMPARE_DISTANCE:-0} commit(s) behind · $delta_desc"
                ;;
        esac
    fi

    # Document-level counters. Effective-anchor resolution follows
    # doc_effective_anchor() (own > index); scope_has_delta / ack fields are
    # read per document so a document opting into its OWN anchor_commit is
    # measured against ITS anchor's resolvability, not silently folded into
    # the scope's state computed above for the index's own anchor.
    local doc doc_ack
    while IFS= read -r doc; do
        [[ -z "$doc" ]] && continue
        if ! doc_effective_anchor "$doc" "$index_file"; then
            continue
        fi
        STATUS_LINE_ANCHORED=$((STATUS_LINE_ANCHORED + 1))

        doc_ack="$(fm_field "$doc" anchor_ack || true)"
        if [[ "$doc_ack" == "asserted" ]]; then
            STATUS_LINE_ASSERTED=$((STATUS_LINE_ASSERTED + 1))
            record_asserted_actor "$(ack_actor_key "$doc")"
            continue
        fi
        if [[ "$doc_ack" == "updated" ]]; then
            continue
        fi

        # No ack recorded. Stale iff a delta exists that applies to this
        # document: its own anchor, when it differs from the index's, is
        # re-compared; otherwise the scope-level delta computed above
        # applies directly (ADR-0009 §3: covers: refines, never replaces).
        #
        # `if cond; then assign; fi` here, NOT a bare `[[ cond ]] && assign`
        # list: reproduced directly (21.08.2026) that the bare form crashes
        # this whole script under `set -e` whenever it is the LAST command
        # this function executes on the LAST loop iteration AND its
        # condition is false — the `&&` list's own exit status is then 1
        # (the executed-but-false `[[ ]]`, since the assignment never ran),
        # which becomes the while-loop's exit status, then this function's
        # own exit status, and this function is called as an unguarded bare
        # statement from cmd_status()'s loop. An `if`/`fi` with no matching
        # branch taken is exit-status 0 by POSIX definition, not 1 — the one
        # difference that makes this form safe. The explicit `return 0`
        # below is a second, independent guard against the same shape.
        if [[ "$ANCH_SOURCE" == "own" && "$ANCH_COMMIT" != "$idx_anchor" ]]; then
            anchor_compare_state "$PROJECT_DIR" "$ANCH_COMMIT"
            if [[ "$ANCHOR_COMPARE_STATE" == "ok" && ${#CHANGED_PROD_PATHS[@]} -gt 0 ]]; then
                STATUS_LINE_STALE=$((STATUS_LINE_STALE + 1))
            fi
        elif [[ "$scope_has_delta" == "1" ]]; then
            STATUS_LINE_STALE=$((STATUS_LINE_STALE + 1))
        fi
    done < <(scope_documents "$PROJECT_DIR" "$folder")

    return 0
}

# --- dispatch ---------------------------------------------------------------

SUBCOMMAND="${1:-}"
[[ $# -gt 0 ]] && shift || true

case "$SUBCOMMAND" in
    status)
        cmd_status "$@"
        ;;
    check)
        cmd_check "$@"
        ;;
    ack)
        cmd_ack "$@"
        ;;
    set)
        cmd_set "$@"
        ;;
    -h|--help|"")
        usage
        exit 2
        ;;
    *)
        echo "$PROG: unknown subcommand '$SUBCOMMAND'" >&2
        usage >&2
        exit 2
        ;;
esac
