#!/usr/bin/env bash
# memory-sync.sh — sync a shared org-tier memory/instincts repo into ~/.claude as a
# read-only overlay, and promote local entries into it (direct-push with discipline).
#
# The script is GENERIC: every deployment-specific value (repo URL, token file,
# namespace, overlay paths) lives in the config file, never in this script — so it
# stays de-customizable for the framework.
#
# Config: $MEMORY_SYNC_CONFIG or ~/.claude/memory-sync.json
#
# Verbs:
#   pull                 Fetch the shared repo and materialize the local read-only overlay.
#   promote <src> <dst>  Run the discipline gate on <src>, copy it into the clone at repo-
#                        relative <dst>, commit + push. <dst> e.g. instincts/shared.md.
#                        <dst> must be a FILE path, never a directory: what the checks
#                        read has to be the name that ships (see require_file_destination).
#   gate <file>          Run the discipline gate on <file> only (no side effects). Exit 0 = clean.
#   status               Show config + clone state (no network mutation).
#
# Discipline gate (blocks promote): de-personalization, secret scan, content-type (no TODOs).
# Token value is never printed. Requires: git, python3, curl.
#
# Exit: 0 ok, 1 gate/soft failure, 2 hard error.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# The discipline-gate patterns are defined ONCE, in the shared library, and are
# reused by scripts/artifact-gate.sh with a different profile. Do not inline a
# second copy here — a second register drifts.
# shellcheck source=lib/discipline_gate.sh
. "$HERE/lib/discipline_gate.sh"

CONFIG="$(gate_config_path)"

# Loaded before anything is printed, and before the config-existence check
# below: die()/note() route every message through the same deny-list mask
# artifact-gate.sh's say()/warn()/die() use, and that mask can only redact a
# configured name once the deny-list is known. This mirrors artifact-gate.sh's
# "Loaded before the arguments are parsed" placement — the same argument holds
# here even though this script has no argument-parsing loop of its own, it
# dispatches on $1 further down. An absent config is not an error for this
# call: gate_load_config leaves GATE_DENY_NAMES empty and returns 0, which is
# exactly the state die() needs to be able to run under to report that very
# absence a few lines down.
gate_load_config

# Every line this tool emits goes through the deny-list mask AND a $HOME
# shortener — not just promote's destination check. This is the path on which
# memory LEAVES the machine, but `pull`/`status` print repo URLs, clone paths
# and config paths too, and any of them can carry a configured tenant/project
# name — or the operator's OS username, via $HOME — into a terminal, a shell
# history or a CI log wrapping this command. Same shape as artifact-gate.sh's
# say()/warn()/die(), deliberately: a second, differently-behaved copy of "how
# this tool prints" would be the same kind of drift the shared discipline-gate
# library already exists to prevent.
#
# The format string is always a literal at call sites that use say()/warn()
# directly. die()/note() wrap every message in the literal '%s: %s' before it
# reaches printf, so a '%' already interpolated into a message (e.g. inside a
# repo URL) is consumed as a %s ARGUMENT and never read as a directive.
# shellcheck disable=SC2059
say() {
  local msg
  msg="$(gate_redact_path "$(printf "$@")")"
  # An empty $HOME would turn `${msg//$HOME/~}` into "insert ~ between every
  # character" — bash's pattern substitution treats an empty pattern as
  # matching everywhere. Not a real deployment, but guarding it costs one
  # comparison.
  if [[ -n "${HOME:-}" ]]; then msg="${msg//$HOME/~}"; fi
  printf '%s\n' "$msg"
}
warn() { say "$@" >&2; }
die()  { warn '%s: %s' "memory-sync" "$*"; exit 2; }
note() { say '%s: %s' "memory-sync" "$*"; }

[[ -f "$CONFIG" ]] || die "config not found: $CONFIG"
command -v git   >/dev/null || die "git not found"
command -v python3 >/dev/null || die "python3 not found"

# --- config access -----------------------------------------------------------
# cfg <dotted.key> — read a value from the JSON config; empty string if absent.
cfg() {
  python3 - "$CONFIG" "$1" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))
cur = cfg
for part in sys.argv[2].split('.'):
    if isinstance(cur, dict) and part in cur:
        cur = cur[part]
    else:
        print(""); sys.exit(0)
print("" if cur is None else cur)
PY
}

# expand a leading ~ to $HOME
expand() { case "$1" in "~"/*) printf '%s' "$HOME/${1#\~/}";; *) printf '%s' "$1";; esac; }

REPO_URL="$(cfg repoUrl)"
TOKEN_FILE="$(expand "$(cfg tokenFile)")"
CLONE="$(expand "$(cfg clonePath)")"
NS="$(cfg namespace)"
INSTINCTS_IN_REPO="$(cfg overlay.instinctsFileInRepo)"
INSTINCTS_TARGET="$(expand "$(cfg overlay.instinctsTarget)")"
INSTINCTS_INDEX="$(expand "$(cfg overlay.instinctsIndex)")"
INDEX_BLOCK_TITLE="$(cfg overlay.indexBlockTitle)"
PERSONA_TOPIC="$(cfg overlay.personaTopicName)"
MEM_NS_DIR="$(expand "$(cfg overlay.memoryNsDir)")"
MEM_INDEX_PTR="$(expand "$(cfg overlay.memoryIndexPointer)")"

[[ -n "$REPO_URL" ]] || die "config: repoUrl missing"
[[ -n "$NS" ]] || die "config: namespace missing"

# --- auth (token never printed) ----------------------------------------------
resolve_token() {
  [[ -f "$TOKEN_FILE" ]] || die "token file not found: $TOKEN_FILE"
  tr -d '\r\n' < "$TOKEN_FILE"
}

# authed URL for a git op — token injected in-memory, never written to .git/config
authed_url() {
  local tok; tok="$(resolve_token)"
  printf '%s' "$REPO_URL" | sed -E "s#^http://#http://oauth2:${tok}@#; s#^https://#https://oauth2:${tok}@#"
}

# git_or_die <label> <git-command...> — run a git subprocess whose stderr can
# carry the repository URL (clone, fetch, push), and route a failure through
# the same mask everything ELSE this script prints goes through.
#
# git's own error text is written straight to the terminal/CI log; it never
# passes through say(), so on its own it bypasses the deny-list and $HOME
# fold this file exists to apply. Captured here instead of left alone.
#
# `out="$(... 2>&1)" || rc=$?` on one statement is deliberate: under this
# file's `set -e`, a bare failing command substitution would abort the
# script right here with git's own exit status and the message still
# unmasked — exactly the bug this function exists to close. Recording the
# status in `rc` on the same line keeps errexit from firing on the
# assignment, so the `if` below decides the outcome instead of the shell.
# stdout is folded into the same capture (`2>&1`) because --quiet leaves
# nothing there on success and the failure paths below only fire on rc!=0.
#
# The message is passed to die() as ONE argument, never spliced into a
# format string — die() already wraps it in the literal '%s: %s' (see the
# comment above say()), so a '%' inside git's own text (e.g. a URL-encoded
# byte) is consumed as a %s argument, not read as a directive.
git_or_die() {
  local label="$1"; shift
  local out rc=0
  out="$("$@" 2>&1)" || rc=$?
  [[ $rc -eq 0 ]] || die "$label: $out"
}

# --- git clone / fetch --------------------------------------------------------
ensure_clone() {
  local aurl; aurl="$(authed_url)"
  if [[ -d "$CLONE/.git" ]]; then
    note "fetching $REPO_URL"
    git -C "$CLONE" remote set-url origin "$REPO_URL" >/dev/null 2>&1 || true
    git_or_die "git fetch" git -C "$CLONE" fetch --quiet "$aurl" '+refs/heads/*:refs/remotes/origin/*'
    # reset working tree to origin default branch (overlay clone is read-through).
    # symbolic-ref fails when origin/HEAD is unset — keep it errexit-safe (|| true inside the subshell).
    local def
    def="$(git -C "$CLONE" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##' || true)"
    def="${def:-main}"
    git -C "$CLONE" checkout --quiet -B "$def" "origin/$def" 2>/dev/null || git -C "$CLONE" checkout --quiet "$def" 2>/dev/null || true
    git -C "$CLONE" reset --quiet --hard "origin/$def" 2>/dev/null || true
  else
    note "cloning $REPO_URL -> $CLONE"
    mkdir -p "$(dirname "$CLONE")"
    git_or_die "git clone" git clone --quiet "$aurl" "$CLONE"
    git -C "$CLONE" remote set-url origin "$REPO_URL" >/dev/null 2>&1 || true
  fi
}

# --- discipline gate ----------------------------------------------------------
# The shared library reports a configuration defect; refusing to run on it is
# the entry point's job, and this one used to ignore the signal. That is the
# worse half of the pair: artifact-gate reads files that are already here,
# whereas this is the path on which memory LEAVES the machine. A deny-list
# that quietly lost an entry would announce itself as active, check fewer
# names than the operator configured, and push the file anyway. Refused
# before any scan, so no verdict can be produced by the shortened list. The
# entry is identified by position: naming it would put a tenant name into the
# terminal, the shell history and any CI log wrapping this command.
#
# Its own function because the destination-path check below needs the same
# guarantee before it trusts the list, and a second copy of the sentence would
# be a second register.
require_usable_deny_list() {
  [[ -n "$GATE_DENY_UNUSABLE" ]] || return 0
  die "deny-list entry $GATE_DENY_UNUSABLE is unusable (blank, or containing a line break) — fix gate.denyNames in $CONFIG. Refusing to run with a shorter list than configured."
}

# Returns 0 if clean, 1 if any finding. Prints findings. Used by promote + `gate`.
# The checks themselves live in lib/discipline_gate.sh (profile "memory"); this
# wrapper only renders them in the shape this script has always printed: one line
# per distinct finding kind, regardless of how many times it occurs in the file.
run_gate() {
  local f="$1" out
  [[ -f "$f" ]] || { warn '  gate: file not found: %s' "$f"; return 2; }

  # gate_load_config already ran once, at the top of this script (see the
  # comment there) — a second call here would only re-read the same config.
  require_usable_deny_list

  # An absent list is not an error, but silence about it is. The library leaves
  # "say so out loud" to the caller, and promote said nothing at all — so a
  # clean verdict looked identical whether the tenant names had been checked or
  # had never been configured.
  if [[ "$GATE_DENY_SOURCE" == "none" ]]; then
    note "deny-list NOT CONFIGURED — no tenant/project names were checked. Set gate.denyNames in $CONFIG, or pass CCPR_GATE_DENY_NAMES."
  fi

  # gate_scan_file's own header comment promises "returns 1 when there was at
  # least one finding, 0 otherwise" — this is that promise's one consumer.
  # Capturing the exit status this way (an `if` around the assignment, not
  # `|| true`) is required under `set -e`: the common case IS a nonzero
  # return (a dirty file), and `|| true` exists specifically to survive that
  # under `set -e` — swapping it for the `if` form keeps the same survival
  # property while no longer discarding the value it survives.
  local scan_rc=0
  if out="$(gate_scan_file "$f" memory)"; then
    scan_rc=0
  else
    scan_rc=$?
  fi
  [[ "$scan_rc" -eq 0 ]] && return 0

  local rendered
  rendered="$(printf '%s\n' "$out" \
    | awk -F'\t' '$2 != "_exempt" && !seen[$2 FS $3]++ { printf "  [%s] %s\n", $2, $3 }')"
  printf '%s\n' "$rendered"
  return 1
}

# --- verbs -------------------------------------------------------------------
backup_if_exists() {
  local t="$1"
  [[ -e "$t" ]] || return 0
  local bdir="$HOME/.claude/.memory-sync/backups"
  mkdir -p "$bdir"
  cp -R "$t" "$bdir/$(basename "$t").bak" 2>/dev/null || true
}

ensure_index_block() {
  # Refresh the autoloaded index block: heading + note + one-liner bullets generated from the
  # overlay's `### <ID>: <headline>` entries, so the shared set is VISIBLE at session start (not
  # just a pointer). Delimited + regenerated each pull so it self-updates; migrates a prior
  # undelimited pointer block in place.
  [[ -f "$INSTINCTS_INDEX" ]] || return 0
  [[ -f "$INSTINCTS_TARGET" ]] || return 0
  local rel="instincts/$(basename "$INSTINCTS_TARGET")"
  python3 - "$INSTINCTS_INDEX" "$INSTINCTS_TARGET" "$rel" "$INDEX_BLOCK_TITLE" "$REPO_URL" "$NS" <<'PY'
import sys, re
index_path, topic_path, rel, title, repo, ns = sys.argv[1:7]
start, end = f"<!-- memory-sync:{title}:start -->", f"<!-- memory-sync:{title}:end -->"
lines = open(topic_path, encoding="utf-8").read().splitlines()
entries = []
for i, ln in enumerate(lines):
    m = re.match(r'^###\s+([A-Z]{2}-(?:[A-Z]{2}-)?G-\d+):\s*(.+)$', ln)
    if not m:
        continue
    conf = ""
    for j in range(i+1, min(i+4, len(lines))):
        cm = re.search(r'\*\*Confidence[^:]*:\s*([0-9.]+)\*\*', lines[j])
        if cm:
            conf = cm.group(1); break
    entries.append((m.group(1), conf, m.group(2).strip()))
body = [start, f"## {title} → {rel}",
        f"_Synced from {repo} via memory-sync.sh (namespace {ns}-). Read-only overlay — edit in the shared repo, not here._", ""]
for idn, conf, head in entries:
    body.append(f"- {idn}" + (f" [{conf}]" if conf else "") + f" {head}")
block = "\n".join(body + [end])
txt = open(index_path, encoding="utf-8").read()
if start in txt and end in txt:
    txt = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, txt, flags=re.S)
else:
    # migrate a prior undelimited pointer block (heading + its `_..._` note line), then append.
    heading = f"## {title} → {rel}"
    keep, rows, k = [], txt.splitlines(), 0
    while k < len(rows):
        if rows[k].strip() == heading:
            k += 1
            while k < len(rows) and rows[k].startswith('_'):
                k += 1
            continue
        keep.append(rows[k]); k += 1
    txt = "\n".join(keep).rstrip() + "\n\n" + block + "\n"
open(index_path, "w", encoding="utf-8").write(txt)
print(len(entries))
PY
  note "index block refreshed in $INSTINCTS_INDEX (${INDEX_BLOCK_TITLE})"
}

ensure_memory_pointer() {
  [[ -n "$MEM_INDEX_PTR" && -f "$MEM_INDEX_PTR" ]] || return 0
  [[ -d "$MEM_NS_DIR" ]] || return 0
  local marker="## ${INDEX_BLOCK_TITLE} (synced memory)"
  if ! grep -qF "$marker" "$MEM_INDEX_PTR"; then
    { printf '\n%s\n' "$marker";
      printf -- '- Geteilte Team-Fakten liegen unter `%s/` (synced via memory-sync.sh, read-only).\n' "${MEM_NS_DIR/#$HOME/~}"; } >> "$MEM_INDEX_PTR"
    note "memory pointer added to $MEM_INDEX_PTR"
  fi
}

cmd_pull() {
  ensure_clone

  # 1) instincts overlay
  if [[ -n "$INSTINCTS_IN_REPO" && -f "$CLONE/$INSTINCTS_IN_REPO" ]]; then
    backup_if_exists "$INSTINCTS_TARGET"
    mkdir -p "$(dirname "$INSTINCTS_TARGET")"
    cp "$CLONE/$INSTINCTS_IN_REPO" "$INSTINCTS_TARGET"
    note "materialized $(basename "$INSTINCTS_TARGET")"
    ensure_index_block
  fi

  # 2) persona silos: repo memory/{agent}/instincts.md -> ~/.claude/memory/{agent}/<personaTopic>
  if [[ -d "$CLONE/memory" ]]; then
    while IFS= read -r pfile; do
      [[ -n "$pfile" ]] || continue
      local agent; agent="$(basename "$(dirname "$pfile")")"
      local target="$HOME/.claude/memory/$agent/$PERSONA_TOPIC"
      backup_if_exists "$target"
      mkdir -p "$(dirname "$target")"
      cp "$pfile" "$target"
      note "materialized memory/$agent/$PERSONA_TOPIC"
    done < <(find "$CLONE/memory" -mindepth 2 -maxdepth 2 -type f -name "instincts.md" 2>/dev/null)

    # 3) flat shared memory facts: repo memory/*.md (excl MEMORY.md) -> $MEM_NS_DIR/
    mkdir -p "$MEM_NS_DIR"
    # Mark this as a sync-managed overlay dir so memory-lint skips persona-silo checks here.
    printf '%s\n' "Sync-managed org-tier overlay (memory-sync.sh). Do not hand-edit — edit in the shared repo." > "$MEM_NS_DIR/.memory-overlay"
    while IFS= read -r ffile; do
      [[ -n "$ffile" ]] || continue
      cp "$ffile" "$MEM_NS_DIR/$(basename "$ffile")"
      note "materialized $(basename "$MEM_NS_DIR")/$(basename "$ffile")"
    done < <(find "$CLONE/memory" -maxdepth 1 -type f -name "*.md" ! -name "MEMORY.md" 2>/dev/null)
    # carry the shared index too (as reference, not the autoloaded one)
    [[ -f "$CLONE/memory/MEMORY.md" ]] && cp "$CLONE/memory/MEMORY.md" "$MEM_NS_DIR/MEMORY.md"
    ensure_memory_pointer
  fi

  note "pull complete."
}

# The usage hint below used to lowercase the namespace with the bash 4
# case-conversion operator inside the parameter expansion itself. The
# interpreter that runs this script on macOS is /bin/bash 3.2.57, which answers
# `bad substitution` — so the hint WAS the failure: the error path errored, and
# exited 1 instead of this script's hard-error 2. `tr` works everywhere and
# needs no version note. (The construct is deliberately not spelled out here:
# the shipped-scripts scan in scripts/tests/ greps for the family, and quoting
# one in a comment would make the comment a suppression surface.)
ns_lower() { printf '%s' "$NS" | LC_ALL=C tr '[:upper:]' '[:lower:]'; }

# --- the destination must name a FILE ----------------------------------------
# WHY THIS GUARD EXISTS — read before "improving" it into directory support:
#
# Every check on this path reads the string the operator TYPES. What ships is
# the string `cp` PRODUCES, and those two are the same string for exactly as
# long as the destination is a file path. Point `cp` at a directory and it
# appends `basename "$src"`, so the name that lands in the shared tree is one
# no check here has ever looked at: `promote <src>/<tenant>-notes.md .`
# published `<tenant>-notes.md` with a clean gate verdict and exit 0.
#
# A directory was never a supported destination — the header of this file says
# "copy it into the clone at repo-relative destination", and CLAUDE.md calls
# the argument <repo-path>. So the whole class is closed by refusing it, rather
# than by teaching the deny check, the commit subject and every future check a
# second string to look at. Supporting directories again means computing the
# final path FIRST and moving every one of those checks onto it.
#
# It is a usage error, not a finding: nothing about the operator's intent was
# suspicious, the tool simply cannot honour it safely.
reject_directory_destination() {
  # Redacted like every other line: the rejected destination can itself be the
  # thing that must not travel, and a usage error is not an exception to that.
  # The masking is die()'s job now, applied to the finished line — not a
  # manual call here, which is exactly the shape that let other lines in this
  # script ship unmasked (see the comment at the top of this file).
  die "promote refused: the destination must be a FILE path inside the repo (e.g. instincts/$(ns_lower)-org.md), not a directory: $1"
}

# A dash-shaped destination is not a directory — reusing
# reject_directory_destination's message would tell the operator their FILE
# path looks like a DIRECTORY, which is not the mistake that was made. It is
# no longer a leak either: `git add -- "$dst"`, `dirname -- "$dst"` and
# `cp -- "$src" "$dst"` all treat the destination as a path regardless of a
# leading dash, so nothing unexpected ships. What ships is USELESS: a file
# literally named `--all` or `-n`, almost certainly a mistyped flag rather
# than an intended name, and one that reads as a flag again to every future
# tool that globs the directory it landed in. Refused for that reason, the
# same way `.`/`..`/a trailing slash are refused — before the clone is
# touched, before the token is read.
reject_option_shaped_destination() {
  die "promote refused: the destination must be a FILE path, not something that looks like a command-line flag (a component starting with '-'): $1"
}

require_file_destination() {
  local d="$1" part rest
  # Three shapes are decided by the string alone — a trailing slash, and any
  # `.` or `..` component (which covers a bare `.`, and `..`, whose copy lands
  # OUTSIDE the clone entirely).
  case "$d" in
    */) reject_directory_destination "$d" ;;
  esac
  rest="$d"
  while [ -n "$rest" ]; do
    part="${rest%%/*}"
    case "$part" in
      .|..) reject_directory_destination "$d" ;;
      # Every component, not just the destination's first character: a
      # top-level `-n` and a nested `instincts/-n` are the same trap for a
      # tool that later globs `instincts/*`, so both are refused here.
      -*) reject_option_shaped_destination "$d" ;;
    esac
    case "$rest" in
      */*) rest="${rest#*/}" ;;
      *)   rest="" ;;
    esac
  done
  # The fourth shape is not in the string: `instincts` is an ordinary file path
  # until the clone contains a directory of that name. That is why this
  # function is called twice — once before the clone is touched at all, and
  # once after it exists, which is the only moment this line can answer.
  [ ! -d "$CLONE/$d" ] || reject_directory_destination "$d"
}

cmd_promote() {
  local src="$1" dst="${2:-}"
  [[ -n "$src" && -f "$src" ]] || die "promote: source file required and must exist"
  [[ -n "$dst" ]] || die "promote: repo-relative destination required (e.g. instincts/$(ns_lower)-org.md)"

  # The destination path is checked BEFORE anything is copied, staged, committed
  # or pushed — and unlike every other finding this tool produces, a hit here
  # refuses rather than warns.
  #
  # Why this string and why so early: the gate ran on the source file's CONTENT
  # and nothing ever looked at the destination, which is written into the
  # repository tree AND into the commit subject (`memory: promote $(basename
  # "$dst")`) that is then pushed. A file whose content is clean could carry a
  # configured name into a shared repository through its own name. That name
  # survives deleting the file, is visible to everyone with read access, and
  # removing it means rewriting shared history. It is the only irreversible
  # path in this tool; everything else the gate protects is local, which is why
  # a warning is enough there and is not enough here.
  #
  # The whole repo-relative path is matched, not its basename: the commit
  # subject carries only the basename, but the pushed TREE carries every
  # component. Matching is the library's — `gate_path_deny_index` is the same
  # deny-list, case-insensitive and literal, that artifact-gate.sh uses for its
  # FILE PATH finding. No second matcher.
  #
  # The list is verified usable first, for the reason spelled out above
  # require_usable_deny_list: checking a silently shortened list here would
  # announce a check that did not happen on the path where it matters most.
  # gate_load_config already ran once, at the top of this script — a second
  # call here would only re-read the same config.
  require_usable_deny_list
  # Shape before content: a directory destination makes the deny check below
  # meaningless, because it would be matching a string that is not the one
  # that ships.
  require_file_destination "$dst"
  local dst_idx
  dst_idx="$(gate_path_deny_index "$dst" || true)"
  if [[ -n "$dst_idx" ]]; then
    # Redacted like every finding line: the name is what must not travel, and a
    # terminal, a shell history and a CI log are all places it would travel to.
    # The masking is die()'s job now (see the comment at the top of this
    # file), not a manual call here — the path stays printed around the mask
    # so the operator can still see which destination was rejected.
    die "promote refused: destination path carries configured tenant/project name #$dst_idx (name redacted): $dst. A push cannot be taken back — rename the destination."
  fi

  note "Running discipline gate on $src ..."
  if ! run_gate "$src"; then
    die "promote blocked by discipline gate — resolve the findings above (or de-personalize) before sharing."
  fi
  note "  gate clean."

  ensure_clone
  # The second call, and the one that can see a directory the clone already
  # carries — `instincts` names one as soon as anything was promoted below it.
  require_file_destination "$dst"

  # `--` on everything that receives the destination. Without it a leading dash
  # is read as an option by the tool, not as a path by the repository:
  # `git add --all` staged the whole clone into a push that cannot be taken
  # back, `git add -n` staged nothing while the run reported success, and
  # BSD `dirname`/`basename` abort outright on `-n`. The destination is a path
  # in every one of these, so say so.
  mkdir -p "$CLONE/$(dirname -- "$dst")"
  cp -- "$src" "$CLONE/$dst"
  git -C "$CLONE" add -- "$dst"
  if git -C "$CLONE" diff --cached --quiet; then
    note "no change to promote (already up to date)."; return 0
  fi
  git -C "$CLONE" commit --quiet -m "memory: promote $(basename -- "$dst")"
  git_or_die "git push" git -C "$CLONE" push --quiet "$(authed_url)" HEAD:refs/heads/"$(git -C "$CLONE" rev-parse --abbrev-ref HEAD)"
  note "promoted $dst -> $REPO_URL"
}

cmd_status() {
  # Called directly (not via die()/note()), so the format string here is the
  # literal at the call site and every dynamic part travels as its own %s
  # argument — this is the largest surface in the script for both leak
  # classes the mask covers: $CONFIG, $CLONE, $TOKEN_FILE and $INSTINCTS_TARGET
  # all normally sit under $HOME, and $REPO_URL is exactly the value a
  # deny-listed name would appear in.
  say 'config:        %s' "$CONFIG"
  say 'repo:          %s  (%s)' "$(cfg repo)" "$REPO_URL"
  say 'namespace:     %s-' "$NS"
  say 'clone:         %s  (%s)' "$CLONE" "$([[ -d "$CLONE/.git" ]] && echo present || echo absent)"
  say 'token file:    %s  (%s)' "$TOKEN_FILE" "$([[ -f "$TOKEN_FILE" ]] && echo ok || echo MISSING)"
  say 'instincts ->   %s  (%s)' "$INSTINCTS_TARGET" "$([[ -f "$INSTINCTS_TARGET" ]] && echo materialized || echo not-yet)"
  say 'memory ns  ->  %s' "$MEM_NS_DIR"
}

# --- dispatch ----------------------------------------------------------------
case "${1:-}" in
  pull)    cmd_pull ;;
  promote) shift; cmd_promote "${1:-}" "${2:-}" ;;
  gate)    shift; run_gate "${1:-}" && note "gate: clean" || { note "gate: findings above"; exit 1; } ;;
  status)  cmd_status ;;
  *) warn "usage: memory-sync.sh {pull|promote <src> <repo-dst-file>|gate <file>|status}"; exit 2 ;;
esac
