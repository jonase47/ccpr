#!/usr/bin/env bash
# push-gate.sh — CCP-1137: the server-side pre-receive discipline gate.
#
# A Forgejo `pre-receive` hook (see hooks/pre-receive.d/ on the server) pipes
# this script `<oldrev> <newrev> <refname>` lines on stdin, one per updated
# ref, ALL of them for one push, BEFORE any ref is moved. Exit 0 lets the
# push through; any nonzero exit rejects the WHOLE push (pre-receive is an
# all-or-nothing gate, not a per-ref one) and Git discards the incoming
# object quarantine — nothing this script saw ever lands in the repository.
#
# This script owns exactly two things: SCOPE (which paths, at which blobs,
# a push actually introduces) and the translation into an exit code. The
# scanning itself is NOT reimplemented here — every path collected below is
# handed to `artifact-gate.sh` (profile "artifact", every path) and to
# `memory-sync.sh gate` (profile "memory", only paths under
# PUSH_GATE_MEMORY_PATHS), both resolved as SIBLINGS of this script. Copying
# the patterns, the text/binary classification or the finding rendering
# into this file would be a second register of exactly the kind
# lib/discipline_gate.sh exists to prevent.
#
# --- why every new COMMIT is scanned, not the net diff -----------------------
# A leak that commit N introduces and commit N+1 removes is invisible in a
# diff between the push's old and new tip, but it ships in history forever —
# rewriting history to remove it is out of scope by design (no
# `--force`/rewrite path exists here). So the scan set is the union of every
# path touched by every commit `git rev-list "$newrev" --not --all` finds
# (i.e. every commit this push introduces that no existing ref already
# reaches), diffed one at a time with `--root -m` so a root commit or a
# merge's every parent is covered without special-casing. Above
# PUSH_GATE_MAX_COMMITS commits this degrades — loudly, never silently — to
# a single diff against the ref's own old tip (or the empty tree, for a new
# ref): cheaper, but blind to the plant-then-remove shape above. This is a
# documented trade-off, not an oversight.
#
# --- why the gate is not sourced from the pushed tip --------------------------
# The gate's own code (this script and its two siblings) always comes from
# the server's own deployed copy, resolved relative to THIS script's
# location — never from `$newrev:scripts/push-gate.sh`. A gate that judged a
# push using code the SAME push could replace would let a single commit
# rewrite the gate to `exit 0` and have that commit approve itself; that is
# a structural bypass, not a staleness problem, and no amount of freshness
# checking on the pushed copy would close it.
#
# --- two accepted false-rejects, decided on purpose, never worked around ----
# * A push whose only changed paths are binaries ends up with
#   `artifact-gate.sh` seeing scanned == 0 (every file is skipped as
#   binary, not text) and refuses with its own exit 2 — a real push,
#   correctly formed, gets rejected because nothing could be VERIFIED. That
#   is deliberate (see artifact-gate.sh's own header): "0 findings over an
#   empty scope" must never read as a pass.
# * A candidate set that is nonempty but where every single blob is skipped
#   for exceeding PUSH_GATE_MAX_BLOB_BYTES ends up unable to hand
#   artifact-gate.sh any file at all — passing it zero arguments would make
#   it silently fall back to repository-sweep mode, scanning something else
#   entirely. This script refuses that case itself instead, with the same
#   "nothing scanned is not a pass" reasoning, rather than parsing
#   artifact-gate.sh's own message to approximate the same decision.
# A push with SOME oversized blobs among otherwise-scannable content is not
# rejected for that reason alone: the oversized blob is skipped, loudly
# (never silently), and the rest of the push is still scanned normally.
#
# --- environment ---------------------------------------------------------
#   MEMORY_SYNC_CONFIG        config path forwarded to artifact-gate.sh /
#                              memory-sync.sh unchanged (see their own
#                              headers) — resolved the same way by all three.
#   PUSH_GATE_MAX_BLOB_BYTES   size cap per blob before it is skipped
#                              (default 1048576).
#   PUSH_GATE_MAX_COMMITS      per-ref commit cap before the tip-diff
#                              fallback engages (default 200).
#   PUSH_GATE_MEMORY_PATHS     whitespace-separated list of repo-relative
#                              path PREFIXES scanned under the memory
#                              profile in addition to the artifact profile
#                              (default "memory/ instincts/").
#
# Exit: 0 the push may proceed. Nonzero: it may not. The specific nonzero
# value (1 vs 2) mirrors whichever of artifact-gate.sh / memory-sync.sh
# reported the more severe outcome, but Git only distinguishes zero from
# nonzero — do not depend on the exact value from outside this script.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/discipline_gate.sh
. "$HERE/lib/discipline_gate.sh"

PROG="push-gate"

ARTIFACT_GATE="$HERE/artifact-gate.sh"
MEMORY_SYNC="$HERE/memory-sync.sh"

# Same masking discipline as artifact-gate.sh's own say()/warn()/die(): this
# script's OWN messages (gitlink/oversize skip notices) can carry a
# repo-relative PATH, and a configured tenant/project name can sit inside
# one just as easily as inside file content. gate_load_config must run
# before any of these can be called with something to redact.
# shellcheck disable=SC2059
say()  { printf '%s\n' "$(gate_redact_path "$(printf "$@")")"; }
warn() { say "$@" >&2; }
die()  { warn '%s: %s' "$PROG" "$*"; exit 2; }

gate_load_config

[ -f "$ARTIFACT_GATE" ] || die "artifact-gate.sh not found next to this script: $ARTIFACT_GATE"
[ -f "$MEMORY_SYNC" ]   || die "memory-sync.sh not found next to this script: $MEMORY_SYNC"

PUSH_GATE_MAX_BLOB_BYTES="${PUSH_GATE_MAX_BLOB_BYTES:-1048576}"
PUSH_GATE_MAX_COMMITS="${PUSH_GATE_MAX_COMMITS:-200}"
PUSH_GATE_MEMORY_PATHS="${PUSH_GATE_MEMORY_PATHS-memory/ instincts/}"

TMP="$(mktemp -d -t push-gate.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
SCANDIR="$TMP/scan"
mkdir -p "$SCANDIR"

TAB="$(printf '\t')"

# NUL-terminated "<sha><TAB><path>" records, one per (blob, path) a
# non-gitlink ACMRT diff-tree entry introduced. Gitlinks (mode 160000) never
# reach this file — there is no blob for them in this repository's own
# object store, so `git cat-file` on their "sha" would simply fail.
CANDIDATES="$TMP/candidates"
: > "$CANDIDATES"

# process_diff_tree_records <file> — read NUL-terminated raw `git diff-tree
# -z` records (meta, path pairs; see the two invocations below) from <file>
# and append "<sha><TAB><path>\0" to $CANDIDATES for every entry whose mode
# is not a gitlink. A gitlink is skipped LOUDLY, once per occurrence, never
# folded into a silent count — the same "never silent" rule the size cap
# below and artifact-gate.sh's own binary/symlink skip lines already follow.
process_diff_tree_records() {
  local f="$1" meta path rest newmode newsha
  while IFS= read -r -d '' meta && IFS= read -r -d '' path; do
    [ -n "$meta" ] || continue
    # meta = ":<oldmode> <newmode> <oldsha> <newsha> <status>" — mode/sha/
    # status never contain whitespace, so splitting on IFS here is safe
    # regardless of what the PATH (never touched by this split) contains.
    meta="${meta#:}"
    set -- $meta
    newmode="$2"
    newsha="$4"
    if [ "$newmode" = "160000" ]; then
      say '%s: gitlink skipped (submodule reference, no blob in this repository): %s' \
          "$PROG" "$path"
      continue
    fi
    printf '%s%s%s\0' "$newsha" "$TAB" "$path" >> "$CANDIDATES"
  done < "$f"
}

# --- read the pre-receive protocol from stdin ---------------------------------
while read -r oldrev newrev refname; do
  [ -n "${oldrev:-}${newrev:-}${refname:-}" ] || continue

  if [[ "$newrev" =~ ^0+$ ]]; then
    say '%s: %s deleted -- nothing to scan' "$PROG" "$refname"
    continue
  fi

  if ! git rev-list "$newrev" --not --all > "$TMP/commits" 2>"$TMP/err"; then
    die "could not enumerate commits for $refname: $(cat "$TMP/err")"
  fi

  commit_count=0
  while IFS= read -r _c; do
    [ -n "$_c" ] || continue
    commit_count=$((commit_count + 1))
  done < "$TMP/commits"

  if [ "$commit_count" -gt "$PUSH_GATE_MAX_COMMITS" ]; then
    say '%s: %s carries %s new commit(s), over the %s-commit cap -- falling back to a tip diff instead of scanning every commit (a leak planted and removed within this range would not be caught)' \
        "$PROG" "$refname" "$commit_count" "$PUSH_GATE_MAX_COMMITS"
    base="$oldrev"
    if [[ "$oldrev" =~ ^0+$ ]]; then
      # A brand-new ref: diff the tip against "nothing" rather than
      # against oldrev's all-zero placeholder. git recognises the
      # well-known empty-tree object as a tree-ish without it needing to
      # exist in this repository's own object database first (verified
      # directly), so this never writes anything -- `hash-object` alone
      # only ever computes a hash. Computed rather than a hardcoded
      # literal on purpose: the SAME 40 hex characters written as a
      # constant read as a plausible leaked token to the very gate this
      # script exists to run (measured: artifact-gate.sh's own sweep of
      # this file flagged it). A bare, standalone right-hand-side
      # assignment -- this script's own `set -euo pipefail` is the
      # correct, decided response to `git hash-object` failing, the same
      # shape the blob-size read below already uses.
      base="$(git hash-object -t tree --stdin < /dev/null)"  # exit-status: exempt set-e-sufficient
    fi
    if ! git diff-tree -r -z --no-commit-id --diff-filter=ACMRT "$base" "$newrev" \
         > "$TMP/difftree" 2>"$TMP/err"; then
      die "could not compute tip diff for $refname: $(cat "$TMP/err")"
    fi
    process_diff_tree_records "$TMP/difftree"
  else
    while IFS= read -r c; do
      [ -n "$c" ] || continue
      if ! git diff-tree -r -z --no-commit-id --root -m --diff-filter=ACMRT "$c" \
           > "$TMP/difftree" 2>"$TMP/err"; then
        die "could not compute diff for commit $c ($refname): $(cat "$TMP/err")"
      fi
      process_diff_tree_records "$TMP/difftree"
    done < "$TMP/commits"
  fi
done

# --- nothing to scan: a pure deletion, or every touched entry was a gitlink --
if [ ! -s "$CANDIDATES" ]; then
  say '%s: no content-bearing paths in this push' "$PROG"
  exit 0
fi

# --- dedupe on (blob sha, path) — cheap, and keeps the materialize/scan step
# below from doing the same work twice for a blob unchanged across commits.
DEDUPED="$TMP/deduped"
if ! sort -z -u "$CANDIDATES" > "$DEDUPED"; then
  die "could not deduplicate the candidate blob list"
fi

# --- materialize: each SURVIVING (sha, path) pair gets its OWN numbered
# subdirectory under $SCANDIR, so two different blobs that were ever at the
# SAME path (e.g. modified again by a later commit in this push) never
# collide on one output file — gate_scan_file needs a real file per blob,
# not per path.
MATERIALIZED="$TMP/materialized"
: > "$MATERIALIZED"
i=0
while IFS= read -r -d '' rec; do
  [ -n "$rec" ] || continue
  sha="${rec%%"$TAB"*}"
  path="${rec#*"$TAB"}"

  # A bare, standalone right-hand-side assignment: `git cat-file -s` on a
  # sha this script itself just collected from `git diff-tree` should never
  # fail short of object-store corruption, so relying on this script's own
  # `set -euo pipefail` to abort is the correct, decided response here (the
  # same shape memory-sync.sh's own `branch="$(git rev-parse ...)"` already
  # uses) rather than a bespoke `if`/`die` wrapper around it.
  size="$(git cat-file -s "$sha")"  # exit-status: exempt set-e-sufficient
  if [ "$size" -gt "$PUSH_GATE_MAX_BLOB_BYTES" ]; then
    say '%s: blob skipped (%s bytes, over the %s byte limit): %s' \
        "$PROG" "$size" "$PUSH_GATE_MAX_BLOB_BYTES" "$path"
    continue
  fi

  i=$((i + 1))
  dest="$SCANDIR/$i/$path"
  mkdir -p "$(dirname "$dest")"
  if ! git cat-file blob "$sha" > "$dest" 2>"$TMP/err"; then
    die "could not read blob content for $path: $(cat "$TMP/err")"
  fi
  printf '%s/%s%s%s\0' "$i" "$path" "$TAB" "$path" >> "$MATERIALIZED"
done < "$DEDUPED"

# --- build the file lists the two gates run over -------------------------
mem_prefixes=()
if [ -n "$PUSH_GATE_MEMORY_PATHS" ]; then
  read -r -a mem_prefixes <<< "$PUSH_GATE_MEMORY_PATHS"
fi

files_all=()
files_memory=()
if [ -s "$MATERIALIZED" ]; then
  while IFS= read -r -d '' rec; do
    [ -n "$rec" ] || continue
    scanrel="${rec%%"$TAB"*}"
    origpath="${rec#*"$TAB"}"
    files_all+=("$scanrel")
    if [ "${#mem_prefixes[@]}" -gt 0 ]; then
      for pfx in "${mem_prefixes[@]}"; do
        case "$origpath" in
          "$pfx"*) files_memory+=("$scanrel"); break ;;
        esac
      done
    fi
  done < "$MATERIALIZED"
fi

# --- the size-cap-only empty scope: candidates existed, but none could be
# materialized. Refused HERE, deliberately, rather than by calling
# artifact-gate.sh with zero file arguments -- with no `--` arguments it
# would fall back to sweeping a whole repository, which is not what an empty
# materialized set means in this context.
if [ "${#files_all[@]}" -eq 0 ]; then
  say '%s: this push introduced content-bearing path(s), but every blob exceeded the %s byte limit -- refusing rather than treating "nothing scanned" as "nothing found"' \
      "$PROG" "$PUSH_GATE_MAX_BLOB_BYTES"
  exit 2
fi

say '%s: scanned %s file(s) introduced by this push' "$PROG" "${#files_all[@]}"

worst_rc=0

# `if ! CMD; then rc=$?; ...` would be wrong here: `!` negates the exit
# status the `if` tests, so `$?` inside that `then` branch would read back
# the NEGATED (successful) status, not CMD's own failure -- the same
# `if CMD; then rc=0; else rc=$?; fi` shape artifact-gate.sh's own
# `gate_scan_file` call already uses, for the identical reason.
rc=0
if ( cd "$SCANDIR" && bash "$ARTIFACT_GATE" --require-denylist -- "${files_all[@]}" ); then
  rc=0
else
  rc=$?
fi
[ "$rc" -gt "$worst_rc" ] && worst_rc="$rc"

if [ "${#files_memory[@]}" -gt 0 ]; then
  for f in "${files_memory[@]}"; do
    rc=0
    if ( cd "$SCANDIR" && bash "$MEMORY_SYNC" gate "$f" ); then
      rc=0
    else
      rc=$?
    fi
    [ "$rc" -gt "$worst_rc" ] && worst_rc="$rc"
  done
fi

exit "$worst_rc"
