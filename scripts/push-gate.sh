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
# a push actually introduces — together with the ref name being written,
# every new commit's own message, and any annotated tag's own payload) and
# the translation into an exit code. The scanning itself is NOT
# reimplemented here — every path collected below is handed to
# `artifact-gate.sh` (profile "artifact", every path) and to
# `memory-sync.sh gate` (profile "memory", only paths under
# PUSH_GATE_MEMORY_PATHS), both resolved as SIBLINGS of this script. The ref
# name itself is checked directly against `gate_path_deny_index`, sourced
# from the same lib/discipline_gate.sh both sub-gates already use — never a
# second matcher. Copying the patterns, the text/binary classification or
# the finding rendering into this file would be a second register of
# exactly the kind lib/discipline_gate.sh exists to prevent.
#
# --- why every new COMMIT is scanned, not the net diff -----------------------
# A leak that commit N introduces and commit N+1 removes is invisible in a
# diff between the push's old and new tip, but it ships in history forever —
# rewriting history to remove it is out of scope by design (no
# `--force`/rewrite path exists here). So the scan set is the union of every
# path touched by every commit `git rev-list "$newrev" --not <SCOPE>` finds
# (i.e. every commit this push introduces that no existing ref already
# reaches — see "--server vs the client-safe default" below for what
# <SCOPE> resolves to and why), diffed one at a time with `--root -m` so a
# root commit or a merge's every parent is covered without special-casing. Above
# PUSH_GATE_MAX_COMMITS commits the push is REFUSED outright, not degraded
# to a partial scan: an earlier version of this script fell back to a
# single diff against the ref's own old tip once the cap was exceeded —
# cheaper, but a reviewer reproduced it going blind to exactly the
# plant-then-remove shape above (CCP-1137R2). Refusing is the same "never
# silently weaker" rule PUSH_GATE_MAX_BLOB_BYTES's own loud skip already
# follows, applied to the one case where loud isn't enough because nobody
# server-side reads a hook's stdout.
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
# --- two FORMER accepted false-rejects, now FLAGGED to the PO instead of
# silently kept or discarded ------------------------------------------------
# Two shapes used to leave `artifact-gate.sh` seeing scanned == 0 (every
# file skipped as binary, or every blob skipped for exceeding
# PUSH_GATE_MAX_BLOB_BYTES) and refusing with its own exit 2 — a real
# push, correctly formed, rejected because nothing could be VERIFIED. That
# was deliberate (see artifact-gate.sh's own header): "0 findings over an
# empty scope" must never read as a pass.
#
# CCP-1137R2 changes this as an unrelated SIDE EFFECT, not a conscious
# revisit of either decision: every commit this push introduces now also
# contributes its OWN commit message as a scan candidate (see "why every
# new COMMIT is scanned" above), unconditionally and with no size cap of
# its own — so the overall scope handed to `artifact-gate.sh` is no
# longer empty in EITHER shape once `git rev-list` finds at least one
# commit, binary-only or all-oversized diffs notwithstanding: the message
# alone is enough to keep `scanned` above zero. The file CONTENT in both
# shapes is still never verified, only the message is, and whether
# scanning the message satisfies "nothing scanned is not a pass" for a
# push whose actual file content stays unverified is a DECISION, not a
# mechanical fact — measured and reported to the PO rather than resolved
# here (see BinaryOnlyPushTest in scripts/tests/test_push_gate.py for the
# exact before/after this produced). The size-cap-only-empty-scope
# refusal this script applies to itself below is kept in place as a
# defensive check regardless of how that decision lands.
# A push with SOME oversized blobs among otherwise-scannable content is not
# rejected for that reason alone: the oversized blob is skipped, loudly
# (never silently), and the rest of the push is still scanned normally.
#
# --- --server vs the client-safe default: an asymmetric choice, not a
# preference (CCP-1137R3) -----------------------------------------------
# This script runs in two structurally different places, and
# `git rev-list "$newrev" --not <X>`'s correctness depends on which one:
#
#   * SERVER (Forgejo pre-receive, the only caller today): git invokes
#     this hook BEFORE any ref moves (see "why the gate is not sourced
#     from the pushed tip" above) — the ref this push is updating still
#     points at its OLD value here, so `--not --all` correctly excludes
#     exactly the commits every existing ref (this one included) already
#     reaches, leaving only what the push introduces. A bare repository
#     has no configured remotes at all, so `--remotes` there resolves to
#     nothing to exclude — scanning the ENTIRE history reachable from
#     `$newrev` on every single push: correct, but needlessly slow.
#   * CLIENT (a future pre-push hook, CCP-1137 Auflage 2): a local branch
#     ref has ALREADY moved to the new commit by the time any hook runs —
#     that is how `git commit` works — so `--not --all` finds the new
#     commit trivially reachable from itself via the very ref being
#     pushed and reports ZERO new commits, unconditionally, on every
#     single push (measured directly: a clone with a remote-tracking ref
#     plus one new local commit — `git rev-list HEAD --not --all` -> 0,
#     `git rev-list HEAD --not --remotes` -> 1, the correct count). A
#     silent, universal false negative — exactly the shape this whole
#     script exists to refuse elsewhere (see the empty-scope handling
#     further down; ClientScopeIsTheDefaultTest in
#     scripts/tests/test_push_gate.py reproduces both sides of this).
#
# These two failure directions are NOT symmetric. `--remotes` used where
# `--all` belongs (server) scans MORE than strictly necessary — slow, but
# every leak that was ever findable still gets found. `--all` used where
# `--remotes` belongs (client) scans NOTHING and reports success — fast,
# and silently wrong, on every push, forever. Given a forced choice
# between "too slow" and "silently blind", the DEFAULT is the client-safe
# one — `--remotes` — and the faster-but-narrower `--all` mode is never
# reached by omission: it is requested by the single literal argument
# `--server`, spelled out in full, only by the deployed pre-receive shim
# (below) — the same "a forgotten switch fails toward MORE scanning, never
# toward less" rule PUSH_GATE_MAX_COMMITS's own refuse-outright-above-the-
# cap decision already follows.
#
# What the client-safe default does NOT reach: `--not --remotes` unions
# EVERY `refs/remotes/*` this clone knows about, not only the remote-
# tracking ref of the actual push TARGET. A commit already pushed to one
# remote but never to a second one falls out of scope on the very first
# push to that second remote (0 new commits scanned), because the FIRST
# remote's own remote-tracking ref already reaches it — reproduced
# directly, and it needs no adversarial setup: any ordinary fork+upstream
# or mirror layout with more than one configured remote hits this on a
# normal push. `--not "$oldrev"` (the pre-push stdin line's own
# <remote-sha> field — exactly the pushed-to remote's prior state for THIS
# ref) would close it precisely, but is deliberately not built here: this
# scope computation has already been touched three times in this item,
# each change needing its own mutation probe, and the path it narrows is
# explicitly FAST FEEDBACK ONLY (see install-push-gate-hook.sh's own
# header) — never the enforcement boundary. The SERVER side is unaffected:
# `--server` computes scope from `--not --all`, not `--not --remotes`, and
# a bare pre-receive repository has no `refs/remotes/*` to begin with.
#
# --- invocation from the server-side pre-receive shim ---------------------
# The Forgejo pre-receive shim — a POSIX `sh` one-liner living in the
# separate infra repo, not this one — MUST invoke this script with the
# literal argument below. The exact line the shim has to run:
#
#   exec bash "$GATE_ROOT/scripts/push-gate.sh" --server
#
# ($GATE_ROOT resolved by the shim to the deployed gate's own root — the
# same layout PushGateTestBase mirrors in scripts/tests/test_push_gate.py:
# this script next to its two siblings and lib/discipline_gate.sh.)
# Omitting `--server` does not fail loudly here — it silently falls back
# to the client-safe default, which on THIS repo's bare, remote-less
# layout means "scan every commit reachable from $newrev, every push":
# correct, per the asymmetry above, but not the behavior pre-receive is
# designed around, so a deploy that forgets the flag is a performance
# regression that review must catch — not a scanning gap, because the
# server-shaped fallback direction is the safe one.
#
# What a `verify-gate.sh` (infra repo, does not exist yet) must check to
# keep the DEPLOYED shim honest: (1) the deployed `hooks/pre-receive` file
# invokes this script's own path with the literal `--server` argument
# present — a grep for both together, not either alone, so a shim that
# calls some OTHER script with `--server` or this script with no argument
# both still fail the check; (2) the deployed copies of push-gate.sh /
# artifact-gate.sh / memory-sync.sh / lib/discipline_gate.sh match this
# repository's own copies byte-for-byte (a stale deploy silently running
# an older gate is the same class of bypass as the pushed-tip risk
# discussed above, just introduced by a missed deploy instead of a
# malicious commit); (3) MEMORY_SYNC_CONFIG in the shim resolves to a path
# OUTSIDE any operator's own $HOME (see PushGateTestBase.gate_config's own
# comment for why). None of this is implemented here — it lives in the
# infra repo that owns the shim.
#
# --- arguments -------------------------------------------------------------
#   (none)      the client-safe default — commit reachability is measured
#               against `--not --remotes` (see the asymmetry rationale
#               above). Correct for a future client-side pre-push caller;
#               scans more than strictly necessary on today's server-side
#               caller (a bare repo has no remotes to exclude against).
#   --server    requests `--not --all` instead — correct ONLY where a ref
#               has not yet moved when this script runs (pre-receive).
#               Never pass this from a client-side caller.
#   anything else is refused outright (exit 2) before any scan runs.
#
# --- environment ---------------------------------------------------------
#   MEMORY_SYNC_CONFIG        config path forwarded to artifact-gate.sh /
#                              memory-sync.sh unchanged (see their own
#                              headers) — resolved the same way by all three.
#   PUSH_GATE_MAX_BLOB_BYTES   size cap per blob before it is skipped
#                              (default 1048576).
#   PUSH_GATE_MAX_COMMITS      per-ref commit cap; a ref carrying more new
#                              commits than this is refused outright rather
#                              than degraded to a partial scan (default 200).
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

# --not <PUSH_GATE_NOT_SCOPE> feeds the `git rev-list` call below (see "---
# --server vs the client-safe default" above). `--remotes` is the DEFAULT
# on purpose — reached by simply passing no argument — and `--all` is
# reached only through the single literal `--server` argument, never
# implicitly. Anything else on the command line is a caller mistake this
# script refuses BEFORE any scan runs, rather than silently ignoring an
# argument it does not understand.
PUSH_GATE_NOT_SCOPE="--remotes"
[ "$#" -le 1 ] || die "unrecognized arguments: $* -- this script accepts at most one argument, --server, requested only by the deployed pre-receive shim"
case "${1:-}" in
  '') ;;
  --server) PUSH_GATE_NOT_SCOPE="--all" ;;
  *) die "unrecognized argument: $1 -- this script accepts at most one argument, --server, requested only by the deployed pre-receive shim" ;;
esac

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

# NUL-terminated "<scanrel><TAB><origpath>" records, one per scan candidate
# that has ALREADY been written to disk under $SCANDIR — both the blob-
# backed candidates materialized from $DEDUPED further down AND the two
# synthetic candidate KINDS this script itself generates: a commit's own
# message and an annotated tag's own payload, neither of which is a blob a
# repo-relative path was ever diffed against, so neither could travel
# through $CANDIDATES. One shared counter/file for all three sources keeps
# every subdirectory under $SCANDIR uniquely numbered regardless of which
# source produced it.
MATERIALIZED="$TMP/materialized"
: > "$MATERIALIZED"
i=0

# materialize_extra <content-file> <synthetic-relpath> — write <content-file>
# to its own numbered subdirectory under $SCANDIR and record it in
# $MATERIALIZED, the same shape the blob-backed materialize loop further
# down produces. <synthetic-relpath> is never a real repository path — it
# exists only so a finding can be attributed to what produced it (a
# commit's message or a tag's payload) instead of reading like a file
# finding.
materialize_extra() {
  local src="$1" relpath="$2" dest
  i=$((i + 1))
  dest="$SCANDIR/$i/$relpath"
  mkdir -p "$(dirname "$dest")"
  cp "$src" "$dest"
  printf '%s/%s%s%s\0' "$i" "$relpath" "$TAB" "$relpath" >> "$MATERIALIZED"
}

# is_unsafe_repo_path <path> — true when <path>, later joined onto
# "$SCANDIR/<n>/" and handed to `mkdir -p`/`git cat-file blob >`, could
# write outside its own scan sandbox.
#
# git's tree object format has no opinion on path-COMPONENT semantics: a
# single tree entry literally named ".." is accepted without complaint by
# `git mktree`. Git's OWN fsck DOES reject it when asked to look —
# `receive.fsckObjects=true` on the receiving repository turns a push
# carrying one into `error: hasDotdot: contains '..'` / `fatal: fsck error
# in packed object`, confirmed directly. But `receive.fsckObjects` defaults
# to false, and is unset — not overridden — everywhere on the deployment
# this hook actually runs on (global config, system config, and the bare
# repository's own config all measured empty on the target server, git
# 2.49.1). So a commit built on one survives a normal `git push` there
# today, and `is_unsafe_repo_path()` below is the ONLY active guard against
# it, not a redundant second one. `git diff-tree`'s own path field then
# reads back as an ordinary-looking string, e.g. `subdir/../secret.txt`,
# which this script would otherwise hand straight to `mkdir -p "$(dirname "$dest")"`
# and `git cat-file blob "$sha" > "$dest"` — a real, exploitable escape
# from the scan sandbox, bounded only by the filesystem permissions of
# whichever account runs the hook, and reachable BEFORE either sub-gate
# ever sees the content. Refused outright (the whole push, not just this
# one candidate) rather than skipped-and-continued: a tree entry shaped
# like this has no legitimate reason to exist in a push, so it is treated
# as its own finding, not a benign feature to route around the way a
# gitlink is.
is_unsafe_repo_path() {
  case "$1" in
    /*) return 0 ;;
    ..|../*|*/..|*/../*) return 0 ;;
  esac
  return 1
}

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
    if is_unsafe_repo_path "$path"; then
      die "refusing this push: a tree entry's path escapes its own tree ($path) — never a legitimate shape, always refused rather than routed around"
    fi
    printf '%s%s%s\0' "$newsha" "$TAB" "$path" >> "$CANDIDATES"
  done < "$f"
}

# Both `git diff-tree` invocations below pass `--no-renames` deliberately,
# even though `process_diff_tree_records` was ALREADY correct without it —
# git's own docs on `diff.renames` are explicit that the config default
# "affects only git diff Porcelain like git-diff(1) and git-log(1), and
# not lower level commands such as git-diff-files(1)" (git-diff-tree is
# the same class of lower-level command; confirmed directly, not just
# read: setting `diff.renames = true` in this repository's own config and
# diffing a renamed file through `git diff-tree` — with neither `-M` nor
# `--find-renames` on the command line — still produced a plain
# delete+add pair, never an R-status two-path record). Kept anyway as an
# explicit, self-evident guarantee rather than a fact a future reader
# would need this same git-manual paragraph to rediscover: the parser
# below reads exactly one path per record, and `--no-renames` is what
# makes that shape true by construction instead of by observed default.
while read -r oldrev newrev refname; do
  [ -n "${oldrev:-}${newrev:-}${refname:-}" ] || continue

  if [[ "$newrev" =~ ^0+$ ]]; then
    say '%s: %s deleted -- nothing to scan' "$PROG" "$refname"
    continue
  fi

  # --- the ref/branch name itself is a scan target -------------------------
  # A ref name never travels through `git diff-tree` — it is metadata about
  # the push, not content the push carries — so a tenant/project name
  # planted ONLY in a branch or tag name (clean file content otherwise) sat
  # in `git ls-remote`/every UI branch list forever, unscanned. Checked
  # against the path segment AFTER the ref's own category (`refs/heads/`,
  # `refs/tags/`, `refs/notes/`, ...) — the category itself is never
  # attacker-controlled and never worth matching — and before any content
  # scan runs at all. Same status-capture shape artifact-gate.sh's own
  # `gate_path_deny_index` call already uses (WI-0053): "no match" (1, the
  # ordinary case) must not be folded into "the matcher itself crashed"
  # (>=2).
  refpath="${refname#refs/*/}"
  ref_deny_rc=0
  if gate_path_deny_index "$refpath" >/dev/null; then
    ref_deny_rc=0
  else
    ref_deny_rc=$?
  fi
  if [ "$ref_deny_rc" -ge 2 ]; then
    die "ref-name deny-list check did not run -- grep exited $ref_deny_rc: $refname"
  fi
  if [ "$ref_deny_rc" -eq 0 ]; then
    die "refusing this push: ref name matches a denied name: $refname"
  fi

  if ! git rev-list "$newrev" --not "$PUSH_GATE_NOT_SCOPE" > "$TMP/commits" 2>"$TMP/err"; then
    die "could not enumerate commits for $refname: $(cat "$TMP/err")"
  fi

  commit_count=0
  while IFS= read -r _c; do
    [ -n "$_c" ] || continue
    commit_count=$((commit_count + 1))
  done < "$TMP/commits"

  if [ "$commit_count" -gt "$PUSH_GATE_MAX_COMMITS" ]; then
    die "refusing $refname: $commit_count new commit(s) exceed the $PUSH_GATE_MAX_COMMITS-commit cap -- rejecting outright rather than degrading to a partial scan blind to a plant-then-remove shape spanning the cap"
  fi

  while IFS= read -r c; do
    [ -n "$c" ] || continue
    if ! git diff-tree -r -z --no-commit-id --root -m --no-renames --diff-filter=ACMRT "$c" \
         > "$TMP/difftree" 2>"$TMP/err"; then
      die "could not compute diff for commit $c ($refname): $(cat "$TMP/err")"
    fi
    process_diff_tree_records "$TMP/difftree"

    # --- the commit's own MESSAGE is a scan target, unconditionally --------
    # `git diff-tree` reports tree/blob diffs only — the message field
    # never crosses it, so a leak planted ONLY in a commit message (clean
    # file content otherwise) was never scanned. Materialized for every
    # commit this push introduces, independent of whether that commit
    # touches any scannable path at all (a gitlink-only commit still gets
    # its message scanned).
    if ! git log -1 --format=%B "$c" > "$TMP/commitmsg" 2>"$TMP/err"; then
      die "could not read the commit message for $c ($refname): $(cat "$TMP/err")"
    fi
    materialize_extra "$TMP/commitmsg" "(commit-message)/$c"
  done < "$TMP/commits"

  # --- an annotated tag's own PAYLOAD is a scan target ----------------------
  # A lightweight tag's `newrev` IS the commit it names, already covered by
  # the per-commit loop above. An ANNOTATED tag's `newrev` is a distinct tag
  # object whose own message/payload `git diff-tree` never sees — and when
  # the tag points at a commit this push does not introduce (already
  # reachable from some other ref), `$TMP/commits` is empty and the loop
  # above never runs at all, so the tag object would otherwise go entirely
  # unscanned. Checked for every updated ref, not only ones with new
  # commits.
  #
  # A bare, standalone right-hand-side assignment: `git cat-file -t` on a
  # sha this script itself just read out of the ref update line should
  # never fail short of object-store corruption, so relying on this
  # script's own `set -euo pipefail` to abort is the correct, decided
  # response here -- the same shape the blob-size read further down
  # (`size="$(git cat-file -s "$sha")"`) already uses.
  target_type="$(git cat-file -t "$newrev")"  # exit-status: exempt set-e-sufficient
  if [ "$target_type" = "tag" ]; then
    # The scan candidate is the human-authored MESSAGE alone, not
    # `git cat-file tag`'s raw object bytes. The raw form's own header
    # (`object <sha>`\n`type ...`\n`tag ...`\n`tagger ...`\n\n<message>)
    # puts a bare 40-hex commit sha on its own line, which reads as a
    # "long token-like string" to the generic secret heuristic on EVERY
    # annotated tag, clean or not (measured: a tag with a genuinely clean
    # message was refused on exactly this line before this was fixed).
    # Stripped by printing everything AFTER the first blank line -- the
    # same idea `git log --format=%B` already applies to a commit's own
    # message, but NOT via the porcelain equivalent
    # (`git for-each-ref --format='%(contents)' "$refname"`): pre-receive
    # runs BEFORE any ref is moved, so $refname does not yet point at
    # $newrev here (measured: for-each-ref on it returns nothing, letting
    # a dirty payload through unscanned and silent). Only `git cat-file`,
    # addressing the object by its own sha straight out of the incoming
    # quarantine, sees it at this point.
    if ! git cat-file tag "$newrev" > "$TMP/tagraw" 2>"$TMP/err"; then
      die "could not read the tag object for $refname: $(cat "$TMP/err")"
    fi
    if ! awk 'body { print } /^$/ { body = 1 }' "$TMP/tagraw" > "$TMP/tagpayload" 2>"$TMP/err"; then
      die "could not isolate the tag message for $refname: $(cat "$TMP/err")"
    fi
    materialize_extra "$TMP/tagpayload" "(tag-payload)/$newrev"
  fi
done

# --- dedupe on (blob sha, path) — cheap, and keeps the materialize/scan step
# below from doing the same work twice for a blob unchanged across commits.
# Run unconditionally, even over an empty $CANDIDATES (a pure deletion, a
# push that only touched gitlinks, or a ref update with no new commits and
# no tag payload never adds anything to it) — `sort -z -u` on an empty file
# produces an empty $DEDUPED, and the materialize loop below simply does not
# iterate; the actual "was anything scanned at all" decision happens once,
# after commit-message/tag-payload candidates are folded in too (see the
# check on $MATERIALIZED further down).
DEDUPED="$TMP/deduped"
if ! sort -z -u "$CANDIDATES" > "$DEDUPED"; then
  die "could not deduplicate the candidate blob list"
fi

# --- materialize: each SURVIVING (sha, path) pair gets its OWN numbered
# subdirectory under $SCANDIR, so two different blobs that were ever at the
# SAME path (e.g. modified again by a later commit in this push) never
# collide on one output file — gate_scan_file needs a real file per blob,
# not per path. Continues the SAME numbering / $MATERIALIZED file the
# commit-message and tag-payload candidates from the main loop above may
# already have written into, so nothing here collides with them.
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

# --- an empty final scope is either of two things, told apart by whether
# $CANDIDATES ever held a blob-backed entry -----------------------------
# * $CANDIDATES was NEVER populated: a pure deletion (already `continue`d
#   above before reaching here), a push whose every touched tree entry was
#   a gitlink, or a ref update that introduced no new commit and did not
#   point at a tag object either — genuinely nothing this push introduced.
#   Accepted; there is nothing to verify.
# * $CANDIDATES WAS populated but every single blob was skipped for
#   exceeding PUSH_GATE_MAX_BLOB_BYTES. Refused HERE, deliberately, rather
#   than by calling artifact-gate.sh with zero file arguments -- with no
#   `--` arguments it would fall back to sweeping a whole repository, which
#   is not what an empty materialized set means in this context. See the
#   header comment on why this branch is expected to be unreachable now
#   that every commit's own message is an unconditional scan candidate --
#   kept as a defensive check, not deleted.
if [ "${#files_all[@]}" -eq 0 ]; then
  if [ -s "$CANDIDATES" ]; then
    say '%s: this push introduced content-bearing path(s), but every blob exceeded the %s byte limit -- refusing rather than treating "nothing scanned" as "nothing found"' \
        "$PROG" "$PUSH_GATE_MAX_BLOB_BYTES"
    exit 2
  fi
  say '%s: no content-bearing paths in this push' "$PROG"
  exit 0
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
