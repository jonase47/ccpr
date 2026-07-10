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
#   gate <file>          Run the discipline gate on <file> only (no side effects). Exit 0 = clean.
#   status               Show config + clone state (no network mutation).
#
# Discipline gate (blocks promote): de-personalization, secret scan, content-type (no TODOs).
# Token value is never printed. Requires: git, python3, curl.
#
# Exit: 0 ok, 1 gate/soft failure, 2 hard error.

set -euo pipefail

CONFIG="${MEMORY_SYNC_CONFIG:-$HOME/.claude/memory-sync.json}"

die() { echo "memory-sync: $*" >&2; exit 2; }
note() { echo "memory-sync: $*"; }

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
# Optional gate config: a regex of IPv4 prefixes to allow (e.g. an internal VPN net); empty = flag all.
IP_ALLOWLIST="$(cfg gate.ipAllowlist)"

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

# --- git clone / fetch --------------------------------------------------------
ensure_clone() {
  local aurl; aurl="$(authed_url)"
  if [[ -d "$CLONE/.git" ]]; then
    note "fetching $REPO_URL"
    git -C "$CLONE" remote set-url origin "$REPO_URL" >/dev/null 2>&1 || true
    git -C "$CLONE" fetch --quiet "$aurl" '+refs/heads/*:refs/remotes/origin/*'
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
    git clone --quiet "$aurl" "$CLONE"
    git -C "$CLONE" remote set-url origin "$REPO_URL" >/dev/null 2>&1 || true
  fi
}

# --- discipline gate ----------------------------------------------------------
# Returns 0 if clean, 1 if any finding. Prints findings. Used by promote + `gate`.
run_gate() {
  local f="$1" findings=0
  [[ -f "$f" ]] || { echo "  gate: file not found: $f" >&2; return 2; }

  # 1) Secrets.
  # 1a) keyword = <value> — but NOT when the value is a filesystem path (a location, not a secret):
  #     value must start with an alnum/+ char, so `token: ~/.x` or `token: /root/.x` won't match.
  if grep -nEi '(token|secret|password|passwd|bearer|api[_-]?key)[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9+][A-Za-z0-9._/+=-]{15,}' "$f" >/dev/null; then
    echo "  [secret] possible credential assignment (keyword = <value>)"; findings=1
  fi
  # 1b) high-entropy / known token blobs: hex, base64, base64url, perm-, vendor prefixes.
  if grep -nE '(perm-[A-Za-z0-9._-]{20,}|[A-Fa-f0-9]{40,}|[A-Za-z0-9+/]{40,}={0,2}|[A-Za-z0-9_-]{40,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})' "$f" >/dev/null; then
    echo "  [secret] long token-like string — verify it is a name/path, not a value"; findings=1
  fi
  # 1c) private keys + credential-bearing connection strings (user:pass@host).
  if grep -nE '(-----BEGIN[A-Z ]*PRIVATE KEY-----|://[^/[:space:]:]+:[^/[:space:]@]+@)' "$f" >/dev/null; then
    echo "  [secret] private key block or credential-bearing connection string"; findings=1
  fi

  # 2) Personal data — session hashes, home paths, emails, type:user, personal-context markers.
  if grep -nEi '(claude\.ai/code/session|session[ _-][0-9a-f]{6,}|/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|Rot-Grün|red-green|Accessibility-Familien)' "$f" >/dev/null; then
    echo "  [personal] session hash / home path / personal-context marker"; findings=1
  fi
  if grep -nE '[[:alnum:]._%+-]+@[[:alnum:]]([[:alnum:].-]*[[:alnum:]])?\.[[:alpha:]]{2,}' "$f" >/dev/null; then
    echo "  [personal] email address — remove or generalize"; findings=1
  fi
  if grep -nE '^type:[[:space:]]*user' "$f" >/dev/null; then
    echo "  [personal] type: user is personal-only, never shared"; findings=1
  fi

  # 3) Network — IPv4 literals not in the configured allowlist (gate.ipAllowlist, e.g. an internal VPN net).
  local ips
  ips="$(grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' "$f" || true)"
  if [[ -n "$IP_ALLOWLIST" && -n "$ips" ]]; then ips="$(printf '%s\n' "$ips" | grep -vE "$IP_ALLOWLIST" || true)"; fi
  if [[ -n "$(printf '%s' "$ips" | tr -d '[:space:]')" ]]; then
    echo "  [network] IPv4 literal not in the configured allowlist — verify it is not a third-party/public address"; findings=1
  fi

  # 4) Content-type — no work-items/TODOs in shared memory (belongs in the tracker).
  # Match work-item SHAPES (TODO:/TODO(, FIXME:, checkbox items, open-status, next-steps headings),
  # not the bare word in prose (a rule may legitimately discuss TODOs, or name a "Cancelled" state).
  if grep -nE '(TODO[:(]|FIXME[:(]|^[[:space:]]*[-*][[:space:]]*\[[ xX]\]|^status:[[:space:]]*(open|offen|cancelled|gecancelt|wip)([[:space:]]|$)|^#{1,6}[[:space:]]*(Next Steps|Nächste Schritte|Offene Punkte|TODO)\b)' "$f" >/dev/null; then
    echo "  [content] work-item marker (TODO:/FIXME:/checkbox/open-status/next-steps heading) — track in the ticket system, not in shared memory"; findings=1
  fi

  return "$findings"
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
  # Add an autoload pointer block to the instincts index if the overlay exists and
  # the block is not present yet. Idempotent.
  [[ -f "$INSTINCTS_INDEX" ]] || return 0
  [[ -f "$INSTINCTS_TARGET" ]] || return 0
  local rel="instincts/$(basename "$INSTINCTS_TARGET")"
  local marker="## ${INDEX_BLOCK_TITLE} → ${rel}"
  if ! grep -qF "$marker" "$INSTINCTS_INDEX"; then
    { printf '\n%s\n' "$marker";
      printf '%s\n' "_Synced from ${REPO_URL} via memory-sync.sh (namespace ${NS}-). Read-only overlay — edit in the shared repo, not here._"; } >> "$INSTINCTS_INDEX"
    note "index block added to $INSTINCTS_INDEX"
  fi
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

cmd_promote() {
  local src="$1" dst="${2:-}"
  [[ -n "$src" && -f "$src" ]] || die "promote: source file required and must exist"
  [[ -n "$dst" ]] || die "promote: repo-relative destination required (e.g. instincts/${NS,,}-org.md)"

  echo "Running discipline gate on $src ..."
  if ! run_gate "$src"; then
    die "promote blocked by discipline gate — resolve the findings above (or de-personalize) before sharing."
  fi
  echo "  gate clean."

  ensure_clone
  mkdir -p "$CLONE/$(dirname "$dst")"
  cp "$src" "$CLONE/$dst"
  git -C "$CLONE" add "$dst"
  if git -C "$CLONE" diff --cached --quiet; then
    note "no change to promote (already up to date)."; return 0
  fi
  git -C "$CLONE" commit --quiet -m "memory: promote $(basename "$dst")"
  git -C "$CLONE" push --quiet "$(authed_url)" HEAD:refs/heads/"$(git -C "$CLONE" rev-parse --abbrev-ref HEAD)"
  note "promoted $dst -> $REPO_URL"
}

cmd_status() {
  echo "config:        $CONFIG"
  echo "repo:          $(cfg repo)  ($REPO_URL)"
  echo "namespace:     ${NS}-"
  echo "clone:         $CLONE  ($([[ -d "$CLONE/.git" ]] && echo present || echo absent))"
  echo "token file:    $TOKEN_FILE  ($([[ -f "$TOKEN_FILE" ]] && echo ok || echo MISSING))"
  echo "instincts ->   $INSTINCTS_TARGET  ($([[ -f "$INSTINCTS_TARGET" ]] && echo materialized || echo not-yet))"
  echo "memory ns  ->  $MEM_NS_DIR"
}

# --- dispatch ----------------------------------------------------------------
case "${1:-}" in
  pull)    cmd_pull ;;
  promote) shift; cmd_promote "${1:-}" "${2:-}" ;;
  gate)    shift; run_gate "${1:-}" && echo "gate: clean" || { echo "gate: findings above"; exit 1; } ;;
  status)  cmd_status ;;
  *) echo "usage: memory-sync.sh {pull|promote <src> <repo-dst>|gate <file>|status}" >&2; exit 2 ;;
esac
