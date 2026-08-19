#!/usr/bin/env bash
# discipline_gate.sh — the ONE definition of CCPR's discipline-gate patterns.
#
# Sourced by two entry points, never executed directly:
#   scripts/memory-sync.sh   profile "memory"    — may this content be promoted
#                                                  into a shared org-tier repo?
#   scripts/artifact-gate.sh profile "artifact"  — may this content ship in the
#                                                  distribution? (Constitution,
#                                                  Inviolable "No personal or
#                                                  tenant data in shipped
#                                                  artifacts")
#
# The regexes live here once on purpose. A second copy is a second register, and
# a second register drifts.
#
# Profiles differ only in WHICH checks run, never in what a pattern means:
#
#   check              memory  artifact  why
#   secret             yes     yes       a credential leaks the same either way
#   personal           yes     yes       session hashes, home paths, real emails
#   context            yes     NO        the colour-vision / accessibility markers
#                                        are a de-personalisation rule for memory
#                                        content; "red-green" is ordinary   # gate-pattern-source
#                                        vocabulary in a TDD or a11y skill prompt
#   type-user          yes     NO        a promotion rule about where a memory
#                                        file may go, not about leaked data;
#                                        shipped schema docs describe the value
#   network            yes     yes       an internal address is an identifier
#   content            yes     NO        "Next Steps" headings and checkboxes are
#                                        legitimate skill-prompt structure
#   denylist           yes     yes       tenant / project names, from personal
#                                        config only — never from this repo
#
# Contract of gate_scan_file: prints one "<line>\t<category>\t<message>" record
# per finding on stdout and returns 1 when there was at least one, 0 otherwise.

# --- pattern-source self-exemption -------------------------------------------
# A gate that scans its own repository necessarily meets the file that spells out
# what it looks for. That is structural, not a tuning problem: `/Users/<name>/`
# cannot be written down without writing it down.
#
# The exemption is therefore line-scoped AND file-scoped: a line carrying the
# marker below is blanked out (blanked, not deleted — line numbers must stay
# true) only while scanning THIS file. The same marker in any other file is
# ordinary text, so it cannot be used anywhere else as a suppression comment.
# Every exempted line is counted and reported, so the exemption is visible in the
# run rather than silent. Audit them with: grep -n 'gate-pattern''-source' <file>
GATE_EXEMPT_MARKER='gate-pattern-source'   # gate-pattern-source

# --- patterns (each definition line is exempted from self-scanning) ----------

# 1a) credential assignment: keyword = <value>. The value must start with an
#     alphanumeric or '+', so `token: ~/.x` and `token: /root/.x` stay silent —
#     those are locations, not secrets.
#     The key may be quoted. That optional quote is not cosmetic: with `[:=]`
#     required flush against the keyword, `{ "token": "..." }` never matched, so
#     the rule the comment on 1b' calls "the backstop" was blind to JSON — and to
#     every Python/JS dict literal — which is where a credential most often sits.
#     Both quote characters are accepted, mirroring the value side. The widening
#     stops there on purpose: allowing arbitrary text between the keyword and the
#     `[:=]` would match ordinary prose like "the token was rotated: see below".
GATE_RE_SECRET_KV='(token|secret|password|passwd|bearer|api[_-]?key)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9+][A-Za-z0-9._/+=-]{15,}'   # gate-pattern-source

# 1b) vendor-prefixed credentials — short, unambiguous, no length heuristic.
GATE_RE_SECRET_VENDOR='(perm-[A-Za-z0-9._-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})'   # gate-pattern-source

# 1b') token blobs, matched by SHAPE rather than by length. A length threshold
#      alone cannot separate a secret from an identifier: a Markdown table
#      separator, a shell comment rule, `test_a_directory_link_without_a_
#      trailing_slash_resolves` and `LocalBackendAppendResultWithoutSectionTest`
#      all clear 40 characters and none of them is a secret. Every attempt to
#      rescue the length rule with an entropy proxy (an unbroken 20+ run, a digit
#      requirement) breaks on the next legitimate identifier.
#      So the generic rule is dropped in favour of the shapes a machine-generated
#      credential actually has: a hex digest, a JWT, or padded base64. Each of
#      them is unambiguous, and each is silent across every tracked file of this
#      repository. What this deliberately does NOT catch is an unpadded,
#      shapeless custom token; check 1a (keyword = <value>) is the backstop for
#      that, and it is how a credential normally appears in a config or a doc.
GATE_RE_SECRET_BLOB='([A-Fa-f0-9]{32,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}|[A-Za-z0-9+/]{40,}={1,2})'   # gate-pattern-source

# 1c) private key blocks, and connection strings that carry a credential.
GATE_RE_PRIVATE_KEY='-----BEGIN[A-Z ]*PRIVATE KEY-----'   # gate-pattern-source
GATE_RE_CONNSTRING='://[^/[:space:]:]+:[^/[:space:]@]+@'   # gate-pattern-source
# A credential position filled ENTIRELY by a variable, a placeholder or a mask
# is a template, not a leak: `://oauth2:${tok}@`, `://user:$TOKEN@`,
# `://user:<your-token>@`, `://user:{{PASSWORD}}@`, `://user:%s@`,
# `://user:****@`.
#
# "Entirely" is the whole rule, and it is the difference between a filter and a
# hole. Asking only whether the match CONTAINS one of `$ < > { } % *` exempted
# every real credential that happens to use one of those characters -- and `%`
# is precisely the character a correctly written URL password uses, because
# percent-encoding is how a reserved character gets into a URL at all. Under the
# contains-test, `://svc:p%40ss@host` (the correct encoding of the password   # gate-pattern-source
# `p@ss`) was silent while the sloppier `://svc:p@ss@host` fired. A check that   # gate-pattern-source
# rewards writing the credential wrongly is worse than no check.
GATE_RE_PLACEHOLDER_SLOT='(\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*|<[^>]*>|\{\{[^}]*\}\}|%[0-9]*[A-Za-z]|\*+)'   # gate-pattern-source
# Applied to the matches of GATE_RE_CONNSTRING. What enforces "is" rather than
# "contains" is that the slot alternation has to span the whole gap: it starts
# immediately after the user's `:` and must be followed at once by the `@`. That
# works because GATE_RE_CONNSTRING excludes `/` from the user part and both `/`
# and `@` from the slot, so an extracted match holds exactly one `://` and
# exactly one `@`, at its two ends -- `://svc:p%40ss@` cannot be re-parsed to put   # gate-pattern-source
# a placeholder in the slot position. The trailing `$` is belt-and-braces on top
# of that `@`, not a second independent guard; measured by mutation, removing
# either anchor alone changes no behaviour, so this comment does not claim they
# do. The guard that IS load-bearing is the alternation being whole-span.
GATE_RE_PLACEHOLDER='://[^/[:space:]:]+:'"$GATE_RE_PLACEHOLDER_SLOT"'@$'   # gate-pattern-source

# 2a) personal data that identifies a person or a session.
GATE_RE_PERSONAL='(claude\.ai/code/session|session[ _-][0-9a-f]{6,}|/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/)'   # gate-pattern-source

# 2b) personal-context markers — memory profile only (see the table above).
GATE_RE_CONTEXT='(Rot-Grün|red[ -]green|Accessibility-Familien)'   # gate-pattern-source

# 2c) email addresses, minus the domains that exist precisely so documentation
#     can show an address without naming a real mailbox: RFC 2606 (example.com /
#     .net / .org, and the .test / .example / .invalid TLDs) and RFC 6761
#     (localhost). The reserved label must own the whole domain or sit behind a
#     dot, so a real `mytest.de` is still reported.
GATE_RE_EMAIL='[[:alnum:]._%+-]+@[[:alnum:]]([[:alnum:].-]*[[:alnum:]])?\.[[:alpha:]]{2,}'   # gate-pattern-source
GATE_RE_EMAIL_RESERVED='@([A-Za-z0-9-]+\.)*(example\.(com|net|org)|invalid|test|localhost|example)$'   # gate-pattern-source

# 2d) a memory file marked personal-only — memory profile only.
GATE_RE_TYPE_USER='^type:[[:space:]]*user'   # gate-pattern-source

# 3) network literals.
GATE_RE_IPV4='([0-9]{1,3}\.){3}[0-9]{1,3}'   # gate-pattern-source

# 4) work-item shapes — memory profile only. Matches the SHAPE (TODO:/TODO(,   # gate-pattern-source
#    FIXME:, checkbox, open status, next-steps heading), not the bare word.   # gate-pattern-source
GATE_RE_CONTENT='(TODO[:(]|FIXME[:(]|^[[:space:]]*[-*][[:space:]]*\[[ xX]\]|^status:[[:space:]]*(open|offen|cancelled|gecancelt|wip)([[:space:]]|$)|^#{1,6}[[:space:]]*(Next Steps|Nächste Schritte|Offene Punkte|TODO)\b)'   # gate-pattern-source

# --- configuration ------------------------------------------------------------
# Deployment- and tenant-specific values live in a personal, non-distributed
# config — never in this repository. Putting a deny-list of tenant names into a
# shipped file would leak exactly what the Inviolable protects.
GATE_IP_ALLOWLIST=""
GATE_DENY_NAMES=""
GATE_DENY_SOURCE="none"
# Positions of configured deny-list entries that could not be used. Non-empty
# means the effective list is shorter than the configured one; an entry point
# must refuse to run rather than check fewer names than its operator believes.
GATE_DENY_UNUSABLE=""
GATE_LAST_EXEMPT_LINES=0

gate_config_path() {
  printf '%s' "${MEMORY_SYNC_CONFIG:-$HOME/.claude/memory-sync.json}"
}

_gate_read_config() {
  python3 - "$1" <<'PY' 2>/dev/null || true
import json, sys
try:
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(0)
gate = cfg.get("gate") or {}
allow = gate.get("ipAllowlist") or ""
print("IPALLOW\t" + str(allow).replace("\n", " ").replace("\t", " "))
names = gate.get("denyNames") or []
if isinstance(names, str):
    names = [names]
for position, name in enumerate(names, start=1):
    name = str(name).strip()
    # A tab is fine: the record below is split on its FIRST tab only, so an
    # interior one reaches the matcher intact. A newline is not -- the transport
    # is newline-delimited, so such an entry would silently become two shorter
    # names, each matching far more than was configured. An empty entry cannot
    # be matched at all. Both unusable kinds are reported by POSITION so the
    # caller can refuse the configuration; checking fewer names than configured
    # while announcing the list as active is the failure this avoids.
    if not name or "\n" in name:
        print("BADNAME\t" + str(position))
        continue
    print("NAME\t" + name)
PY
}

# gate_load_config — fill GATE_IP_ALLOWLIST / GATE_DENY_NAMES / GATE_DENY_SOURCE.
# An absent config is not an error here; reporting "not configured" is the
# calling entry point's job, because silence is what let the breach through.
gate_load_config() {
  local cfg line key val
  GATE_IP_ALLOWLIST=""
  GATE_DENY_NAMES=""
  GATE_DENY_SOURCE="none"
  GATE_DENY_UNUSABLE=""

  # An environment-supplied list lets a CI job inject names from a secret store
  # without a config file. Newline- or comma-separated.
  if [ -n "${CCPR_GATE_DENY_NAMES:-}" ]; then
    GATE_DENY_NAMES="$(printf '%s\n' "$CCPR_GATE_DENY_NAMES" | tr ',' '\n' \
      | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | grep -v '^$' || true)"
    [ -n "$GATE_DENY_NAMES" ] && GATE_DENY_SOURCE="env"
  fi

  cfg="$(gate_config_path)"
  [ -f "$cfg" ] || return 0
  while IFS= read -r line; do
    key="${line%%	*}"
    val="${line#*	}"
    case "$key" in
      IPALLOW) GATE_IP_ALLOWLIST="$val" ;;
      NAME)
        if [ "$GATE_DENY_SOURCE" != "env" ]; then
          GATE_DENY_NAMES="${GATE_DENY_NAMES}${GATE_DENY_NAMES:+
}$val"
          GATE_DENY_SOURCE="config"
        fi
        ;;
      BADNAME)
        # Only relevant when the config file is the source that would be used.
        if [ "$GATE_DENY_SOURCE" != "env" ]; then
          GATE_DENY_UNUSABLE="${GATE_DENY_UNUSABLE}${GATE_DENY_UNUSABLE:+ }#$val"
        fi
        ;;
    esac
  done <<EOF
$(_gate_read_config "$cfg")
EOF
  return 0
}

# --- deny-listed names in the PATH -------------------------------------------
# A file's name is content that ships. It appears in directory listings, in the
# repository index, in every CI log line that mentions the file — and it was
# appearing, verbatim, in the finding line that claimed the name was redacted.
# So the path is matched like file content, and rendered through a mask before
# anything prints it. Both helpers are reporting-side: gate_scan_file reads
# bytes, these two read the name.

# gate_path_deny_index <path> — print the 1-based index of the first configured
# name occurring in <path>, or return 1 when none does. The name itself is never
# printed, for the same reason a content finding never prints it: a CI log is a
# shipped artifact too.
gate_path_deny_index() {
  [ -n "$GATE_DENY_NAMES" ] || return 1
  local idx=0 name
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    idx=$((idx + 1))
    # A here-string, not a pipe: under `set -o pipefail` a `printf | grep -q`
    # can report the pipeline as failed via SIGPIPE precisely when grep exits
    # early on a match, which would turn a hit into a miss.
    if LC_ALL=C grep -qFi -- "$name" <<<"$1"; then
      printf '%s' "$idx"
      return 0
    fi
  done <<EOF
$GATE_DENY_NAMES
EOF
  return 1
}

# gate_redact_path <path> — <path> with every case-insensitive occurrence of a
# configured name replaced by a fixed mask, so the location stays usable while
# the name does not travel.
#
# Values move through ENVIRON rather than `awk -v`: -v applies backslash-escape
# processing to its argument, so a name or a path containing a backslash would
# come out altered — and an altered name would fail to match and be printed in
# full. Failing open is not an option for this particular function.
gate_redact_path() {
  if [ -z "$GATE_DENY_NAMES" ]; then printf '%s' "$1"; return 0; fi
  GATE_RP_PATH="$1" GATE_RP_NAMES="$GATE_DENY_NAMES" LC_ALL=C awk '
    BEGIN {
      n = split(ENVIRON["GATE_RP_NAMES"], names, "\n")
      s = ENVIRON["GATE_RP_PATH"]
      for (i = 1; i <= n; i++) {
        nm = names[i]
        if (nm == "") continue
        lower_nm = tolower(nm)
        len_nm = length(nm)
        out = ""
        rest = s
        while ((at = index(tolower(rest), lower_nm)) > 0) {
          out = out substr(rest, 1, at - 1) "<redacted>"
          rest = substr(rest, at + len_nm)
        }
        s = out rest
      }
      printf "%s", s
    }'
}

# --- scanning -----------------------------------------------------------------
_gate_abspath() {
  local d b
  d="$(dirname "$1")"
  b="$(basename "$1")"
  ( cd "$d" 2>/dev/null && printf '%s/%s' "$(pwd -P)" "$b" ) || printf '%s' "$1"
}

_GATE_PATTERN_SOURCE="$(_gate_abspath "${BASH_SOURCE[0]}")"

_gate_emit() { printf '%s\t%s\t%s\n' "$1" "$2" "$3"; }

# _gate_lines <content> <grep-flags...> — print "<line>:<match>" records.
_gate_hits() {
  local content="$1"; shift
  printf '%s\n' "$content" | grep "$@" || true
}

# gate_scan_file <file> <profile>
gate_scan_file() {
  local f="$1" profile="${2:-artifact}"
  local content hits ip line found=0
  GATE_LAST_EXEMPT_LINES=0

  if [ "$(_gate_abspath "$f")" = "$_GATE_PATTERN_SOURCE" ]; then
    content="$(LC_ALL=C awk -v m="$GATE_EXEMPT_MARKER" 'index($0,m){print "";next}{print}' "$f")"
    GATE_LAST_EXEMPT_LINES="$(LC_ALL=C awk -v m="$GATE_EXEMPT_MARKER" 'index($0,m){n++}END{print n+0}' "$f")"
    # Callers capture this function's stdout in a command substitution, so the
    # count has to travel as a record, not as a variable. Category "_exempt" is
    # bookkeeping, not a finding: it never sets `found`.
    [ "$GATE_LAST_EXEMPT_LINES" -gt 0 ] && _gate_emit 0 _exempt "$GATE_LAST_EXEMPT_LINES"
  else
    content="$(LC_ALL=C cat "$f")"
  fi

  # --- secrets -------------------------------------------------------------
  hits="$(_gate_hits "$content" -nEi -e "$GATE_RE_SECRET_KV")"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" secret "possible credential assignment (keyword = <value>)"
    found=1
  done <<EOF
$hits
EOF

  hits="$(_gate_hits "$content" -nE -e "$GATE_RE_SECRET_VENDOR")"
  hits="$hits
$(_gate_hits "$content" -nE -e "$GATE_RE_SECRET_BLOB")"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" secret "long token-like string — verify it is a name/path, not a value"
    found=1
  done <<EOF
$hits
EOF

  hits="$(_gate_hits "$content" -nE -e "$GATE_RE_PRIVATE_KEY")"
  hits="$hits
$(printf '%s\n' "$content" | grep -noE -e "$GATE_RE_CONNSTRING" \
    | grep -vE -e "$GATE_RE_PLACEHOLDER" || true)"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" secret "private key block or credential-bearing connection string"
    found=1
  done <<EOF
$hits
EOF

  # --- personal ------------------------------------------------------------
  hits="$(_gate_hits "$content" -nEi -e "$GATE_RE_PERSONAL")"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" personal "session hash / home path"
    found=1
  done <<EOF
$hits
EOF

  hits="$(printf '%s\n' "$content" | grep -noE -e "$GATE_RE_EMAIL" \
    | grep -viE -e "$GATE_RE_EMAIL_RESERVED" || true)"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" personal "email address — remove or generalize"
    found=1
  done <<EOF
$hits
EOF

  if [ "$profile" = "memory" ]; then
    hits="$(_gate_hits "$content" -nEi -e "$GATE_RE_CONTEXT")"
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      _gate_emit "${line%%:*}" context "personal-context marker (colour vision / accessibility) — de-personalize before sharing"
      found=1
    done <<EOF
$hits
EOF

    hits="$(_gate_hits "$content" -nE -e "$GATE_RE_TYPE_USER")"
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      _gate_emit "${line%%:*}" personal "type: user is personal-only, never shared"
      found=1
    done <<EOF
$hits
EOF
  fi

  # --- network -------------------------------------------------------------
  hits="$(printf '%s\n' "$content" | grep -noE -e "$GATE_RE_IPV4" || true)"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    ip="${line#*:}"
    if [ -n "$GATE_IP_ALLOWLIST" ] && printf '%s\n' "$ip" | grep -qE -e "$GATE_IP_ALLOWLIST"; then
      continue
    fi
    _gate_emit "${line%%:*}" network "IPv4 literal not in the configured allowlist — verify it is not a third-party/public address"
    found=1
  done <<EOF
$hits
EOF

  # --- content (memory only) -----------------------------------------------
  if [ "$profile" = "memory" ]; then
    hits="$(_gate_hits "$content" -nE -e "$GATE_RE_CONTENT")"
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      _gate_emit "${line%%:*}" content "work-item marker (TODO:/FIXME:/checkbox/open-status/next-steps heading) — track in the ticket system, not in shared memory"   # gate-pattern-source
      found=1
    done <<EOF
$hits
EOF
  fi

  # --- deny-list -----------------------------------------------------------
  # The configured names are NEVER echoed: a CI log is a shipped artifact too.
  # The index plus the line number is enough to locate the occurrence.
  if [ -n "$GATE_DENY_NAMES" ]; then
    local idx=0 name
    while IFS= read -r name; do
      [ -n "$name" ] || continue
      idx=$((idx + 1))
      hits="$(printf '%s\n' "$content" | grep -nFi -- "$name" || true)"
      while IFS= read -r line; do
        [ -n "$line" ] || continue
        _gate_emit "${line%%:*}" denylist "configured tenant/project name #$idx occurs here (name redacted)"
        found=1
      done <<EOF
$hits
EOF
    done <<EOF
$GATE_DENY_NAMES
EOF
  fi

  [ "$found" -eq 0 ] || return 1
  return 0
}
