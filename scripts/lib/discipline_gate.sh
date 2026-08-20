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

# 1a') bearer-token headers. "bearer" is already a keyword in GATE_RE_SECRET_KV
#      above, but that check requires the keyword immediately before `[:=]`.
#      An HTTP header writes `Authorization: Bearer <token>`: the colon belongs
#      to "Authorization", and "Bearer" is followed by whitespace, not `:` or
#      `=`, so the header falls through 1a unless the token happens to be
#      hex/JWT/padded base64 and lands in GATE_RE_SECRET_BLOB instead. This is
#      new detection, not a repair of 1a — a separate, keyword-specific rule.
#      "bearer" is ordinary English vocabulary (a legal term, a courier, a
#      person carrying something), so the rule needs its own anchor, or it
#      lands in exactly the false-positive class the generic 40-character rule
#      was retired for: a long identifier following a trigger word, not a
#      credential — "the bearer token_handling_and_refresh_strategy section"
#      fires on nothing but a snake_case doc heading. A first version of this
#      pattern shipped WITHOUT that anchor (required nothing before "bearer"
#      but whitespace and the value), and it did exactly that on ordinary
#      prose. The fix is the same shape GATE_RE_SECRET_KV already carries: the
#      trigger must sit immediately after `[:=]` (optional whitespace, optional
#      quote), the way a real header or an env-var assignment actually reads
#      — `Authorization: Bearer …` or `AUTH_HEADER="Bearer …`. A bare "bearer"
#      with no `:`/`=` in front of it is prose, not a header, and stays silent.
#      The value shape mirrors 1a's on purpose: same alphabet, same {15,}
#      floor, so a bearer token is held to the same bar as any other
#      credential assignment. No separate placeholder filter is layered on
#      top of it: every shape GATE_RE_PLACEHOLDER_SLOT enumerates (`${...}`,
#      `$VAR`, `<...>`, `{{...}}`, a `%`-format slot, `***`) opens with a
#      character outside `[A-Za-z0-9+]`, so the value's own start-of-match
#      class already excludes all of them — a second filter here would be
#      unreachable code, not a second guard.
GATE_RE_SECRET_BEARER='[:=][[:space:]]*["'"'"']?bearer[[:space:]]+[A-Za-z0-9+][A-Za-z0-9._/+=-]{15,}'   # gate-pattern-source

# 1a'') placeholder WORDS in a 1a/1a' value (WI-0035). The comment on 1a'
#      above is right that no filter is needed for the six
#      GATE_RE_PLACEHOLDER_SLOT shapes: each of `${...}`, `$VAR`, `<...>`,
#      `{{...}}`, a `%`-format slot and `***` opens with a character outside
#      `[A-Za-z0-9+]`, so the value's own start-of-match class already
#      excludes them. It does NOT cover this shape: a documentation
#      placeholder written in screaming-snake-case —
#      'YOUR_TOKEN_HERE_REPLACE_ME', 'TODO_INSERT_YOUR_TOKEN_HERE' — opens
#      with a plain alphanumeric, same as a real credential, so it reaches
#      1a/1a' untouched. This extends that comment's reasoning to a shape it
#      does not claim to cover, rather than contradicting it.
#
#      Matched as a SUBSTRING of the extracted match (keyword/"bearer" +
#      separator + value together — none of 1a/1a's keyword alternatives
#      collide with a word below, so scoping to the value alone would filter
#      the identical set at extra cost) and CASE-INSENSITIVELY, so a
#      lowercase 'your_token_here' is caught the same as the reported
#      all-caps case. "Contains", not "is": WI-0035's PO decision phrased it
#      that way, and an otherwise credential-shaped value that merely has one
#      of these words sitting mid-string is dropped too — decided, not an
#      oversight.
#
#      Scoped to 1a and 1a' ONLY — not 1b/1b'/1c. WI-0035 measured the
#      shape-based alternative this item first considered (dropping values
#      made only of capitals, digits and underscores) against
#      GATE_RE_SECRET_VENDOR's own 'AKIA[0-9A-Z]{16}': an AWS Access Key ID
#      is exactly that shape, so the proposed filter would have gone
#      congruent with a real credential format this gate is built to catch.
#      Widening this word filter to the vendor/blob/private-key/
#      connection-string rules would carry the same risk for no benefit —
#      AWS's own documentation access key contains a listed word (EXAMPLE)
#      and must keep firing there, unfiltered.
#
#      ACCEPTED COST, decided 20.08.2026: this word list is never complete
#      and will grow. That is the safe direction on purpose — an unlisted
#      word means a placeholder still fires (a false positive), never a
#      missed leak. Do not "fix" this into a shape-based filter; that shape
#      was already measured and rejected for the reason above.
GATE_RE_SECRET_PLACEHOLDER_WORD='(YOUR|TODO|REPLACE|CHANGEME|EXAMPLE|PLACEHOLDER|INSERT|DUMMY|SAMPLE)'   # gate-pattern-source

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
#
# How a configured name is matched, and where that has limits:
#   * in a PATH — case-insensitive over the full Unicode range, both spellings
#     normalised to NFC (see "folding and normalisation" below). Simple case
#     folding: `ß` does not match `ss`.
#   * in FILE CONTENT — `grep -nFi` (ASCII-only, unnormalised) for an ASCII
#     deny NAME; a python3 escalation, normalised to NFC and folded over the
#     whole Unicode range, for a non-ASCII name (WI-0017). Gated on the NAME,
#     not on the content: measured 20.08.2026 that gating on content the way
#     the path side gates it would fire on 94% of this repository's own
#     tracked files (non-ASCII prose is common), while an ASCII name can never
#     miss what the escalation would find — see the comment above
#     _gate_content_deny_lines for the measurement. Configure the spelling
#     that matters if a name folds case only in a locale-dependent way this
#     gate does not follow (simple case folding, same limitation as the path
#     side: `ß` does not match `ss`).
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
  #
  # WI-0051: this list feeds the deny-list check for EVERY file in the run —
  # a crash in the final grep here silently emptied GATE_DENY_NAMES, which
  # disabled the denylist category for the whole run, not just one file's
  # worth of one category. tr/sed are not checked the same way: unlike
  # grep, neither has a "1 = nothing matched, not an error" status to
  # confuse with a crash, so an unprotected failure of either already fails
  # closed under this function's inherited `set -e`.
  if [ -n "${CCPR_GATE_DENY_NAMES:-}" ]; then
    local pre out rc=0
    pre="$(printf '%s\n' "$CCPR_GATE_DENY_NAMES" | tr ',' '\n' \
      | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    out="$(_gate_checked "config/CCPR_GATE_DENY_NAMES blank-line-filter" "$pre" -v '^$')" || rc=$?
    if [ "$rc" -ge 2 ]; then
      printf 'gate: %s\n' "$(printf '%s\n' "$out" | awk -F'\t' '$2 == "_error" { print $3 }')" >&2
      exit 2
    fi
    GATE_DENY_NAMES="$out"
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

# --- folding and normalisation of a name comparison ---------------------------
# `grep -Fi` and awk's tolower() fold ASCII and nothing else, so a destination
# `QUÜXCORP-notes.md` walked straight past a configured `Quüxcorp`. And macOS hands
# out decomposed (NFD) file names while the tree carries the composed (NFC)
# spelling, so the two spellings of one name have to compare equal — the same
# NFD-vs-NFC path-comparison trap this project already records as G-117.
#
# Both are answered in ONE place: when either the subject or the configured list
# contains a non-ASCII byte, the comparison escalates to python3, which
# normalises both sides to NFC and matches case-insensitively over the whole
# Unicode range. The matcher and the mask escalate on the same condition and
# share the same program — a mask that folds less than the matcher would print
# in full the very name the matcher just caught.
#
# The ASCII fast path is not a cheaper approximation of that answer, it IS the
# answer: over pure ASCII, NFC is the identity and `grep -Fi`'s folding is
# complete. It exists because gate_path_deny_index runs once per file in
# artifact-gate's repository sweep, where a python3 process per file would
# dominate the run. A subject that merely LOOKS ASCII cannot slip through it:
# the characters that fold or normalise INTO ASCII (KELVIN SIGN, LATIN SMALL
# LETTER LONG S, the ligatures) are themselves non-ASCII, so their presence is
# what triggers the escalation.
#
# KNOWN LIMITATION, accepted deliberately: matching uses SIMPLE case folding, so
# `ß` and `ss` are not treated as the same name (nor `ﬁ` and `fi`). Full case
# folding changes string length, and the mask below replaces in place — a
# matcher that can find what the mask cannot cover is worse than one that
# declines both. Configure such a name in the spelling it is written in.
_GATE_ASCII_LO="$(printf '\001')"
_GATE_ASCII_HI="$(printf '\177')"
_GATE_UNICODE_WARNED=0

# _gate_is_ascii <string> — no subprocess: this runs per file in a repo sweep.
# LC_ALL=C is set as a LOCAL, because a glob range is collation-ordered rather
# than byte-ordered in a UTF-8 locale, where `[!\001-\177]` matches a pure-ASCII
# string as well and every subject would look non-ASCII.
_gate_is_ascii() {
  local LC_ALL=C
  case "$1" in
    *[!"$_GATE_ASCII_LO"-"$_GATE_ASCII_HI"]*) return 1 ;;
    *) return 0 ;;
  esac
}

# _gate_needs_unicode <subject> — true when the comparison cannot be done by
# ASCII folding alone AND the tool for it is present.
_gate_needs_unicode() {
  if _gate_is_ascii "$1" && _gate_is_ascii "$GATE_DENY_NAMES"; then return 1; fi
  if command -v python3 >/dev/null 2>&1; then return 0; fi
  # Announced, never silent: the ASCII matcher is about to answer a question it
  # cannot answer completely. memory-sync.sh refuses to start without python3,
  # so only an env-supplied list can reach this line. The flag dedupes within
  # one shell only — both callers are usually invoked inside a command
  # substitution, whose subshell resets it, so the warning repeats. Repeating a
  # warning about an incomplete check is the harmless direction.
  if [ "$_GATE_UNICODE_WARNED" -eq 0 ]; then
    printf 'gate: python3 not found — non-ASCII names are folded as ASCII only\n' >&2
    _GATE_UNICODE_WARNED=1
  fi
  return 1
}

# _gate_unicode_py <index|redact> <subject> — the shared Unicode implementation.
# index:  print the 1-based index of the first matching name, exit
#         GATE_U_NO_MATCH (2) if none. WI-0049: "no match" used to be sys.exit(1),
#         the same status a fatally broken interpreter never gets the chance to
#         override (measured: `PYTHONHOME=/nonexistent python3 -c pass` exits 1
#         before this script ever runs) -- so a dead interpreter was
#         indistinguishable from a clean comparison. 2 is reserved for this one
#         meaning; every OTHER non-zero status, whatever it is, means the
#         comparison did not run to completion.
# redact: print the subject with every match replaced by the mask. Never exits
#         via the no-match sentinel -- redact has no "no match" outcome, only
#         "done" (0) or "did not run" (anything else).
# Bytes travel through ENVIRON and are written back with surrogateescape, so a
# path that is not valid UTF-8 comes out as the bytes that went in instead of
# aborting the comparison.
# Load-bearing coupling: the python block below reads this value from the
# environment with a STRICT lookup, so it must be set on every invocation. If
# that heredoc is ever extracted into a standalone script, carry the variable
# with it -- a missing or non-numeric value raises inside python, which exits 1,
# which is exactly the status this sentinel exists to stop colliding with.
_GATE_UNICODE_NO_MATCH=2
_gate_unicode_py() {
  GATE_U_MODE="$1" GATE_U_SUBJECT="$2" GATE_U_NAMES="$GATE_DENY_NAMES" \
    GATE_U_NO_MATCH="$_GATE_UNICODE_NO_MATCH" python3 - <<'PY'
import os, re, sys, unicodedata

def nfc(s):
    return unicodedata.normalize("NFC", s)

mode = os.environ["GATE_U_MODE"]
subject = nfc(os.environ.get("GATE_U_SUBJECT", ""))
idx = 0
for name in os.environ.get("GATE_U_NAMES", "").split("\n"):
    # A blank entry does not consume an index — the shell loop below skips it
    # the same way, and a finding says "#<idx>" out loud, so the two counts
    # have to agree.
    if not name:
        continue
    idx += 1
    pat = re.compile(re.escape(nfc(name)), re.IGNORECASE)
    if mode == "index":
        if pat.search(subject):
            sys.stdout.write(str(idx))
            sys.exit(0)
    else:
        subject = pat.sub("<redacted>", subject)

if mode == "index":
    # WI-0049: this used to be sys.exit(1), colliding with the status a
    # broken interpreter produces before this line ever runs. The sentinel
    # travels from the shell (_GATE_UNICODE_NO_MATCH) instead of being
    # hard-coded twice, so the two sides of the contract cannot drift apart.
    sys.exit(int(os.environ["GATE_U_NO_MATCH"]))
sys.stdout.buffer.write(subject.encode("utf-8", "surrogateescape"))
PY
}

# gate_path_deny_index <path> — print the 1-based index of the first configured
# name occurring in <path>, or return 1 when none does. The name itself is never
# printed, for the same reason a content finding never prints it: a CI log is a
# shipped artifact too.
gate_path_deny_index() {
  [ -n "$GATE_DENY_NAMES" ] || return 1
  local idx=0 name
  if _gate_needs_unicode "$1"; then
    local uidx rc=0
    uidx="$(_gate_unicode_py index "$1")" || rc=$?
    case "$rc" in
      0) printf '%s' "$uidx"; return 0 ;;
      "$_GATE_UNICODE_NO_MATCH") return 1 ;;
      # Any other status (including 1, a broken interpreter's start-up exit
      # code -- WI-0049) means the comparison did not happen. Say so and let
      # the ASCII matcher below answer what it can, rather than reporting a
      # clean path because a helper crashed.
      *) printf 'gate: unicode matcher failed (status %s) — falling back to ASCII folding\n' "$rc" >&2 ;;
    esac
  fi
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
  # Same escalation condition as the matcher, on purpose: see the block above.
  # The masked path comes back NFC-normalised, which is the spelling the tree
  # would have carried anyway.
  if _gate_needs_unicode "$1"; then
    local masked rc=0
    masked="$(_gate_unicode_py redact "$1")" || rc=$?
    if [ "$rc" -eq 0 ]; then printf '%s' "$masked"; return 0; fi
    printf 'gate: unicode masker failed (status %s) — falling back to ASCII folding\n' "$rc" >&2
  fi
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

# --- deny-listed names in FILE CONTENT ----------------------------------------
# WI-0017 part (2): content matching stayed ASCII-only and un-normalised
# (`grep -nFi`, no locale pin) while the path side above escalates to python3
# for Unicode. Escalating on the same condition as the path side — subject OR
# name non-ASCII — was measured and rejected: 257 of this repository's own
# 271 tracked files carry a non-ASCII byte (em dashes, umlauts in prose), so
# that gate would fire on 94% of files and add ~41% to every sweep even when
# the configured deny list is pure ASCII. The escalation below therefore
# gates on the NAME alone, never on the content.
#
# This is provably safe for an ASCII name, not merely assumed: measured with
# the ASCII name `cafe` against NFD-decomposed content `cafe`+U+0301, plain
# `grep -Fi` reports a match while python's NFC-normalised search reports
# none — NFC composes the letter and the accent, removing the ASCII substring
# the byte-literal grep saw. So for an ASCII name the ASCII matcher can only
# OVER-report relative to what python would find, never miss it, which is the
# safe direction for a gate. A locale pin (LC_ALL=C) is not needed at the
# grep call below for the same reason: once this path only ever runs for
# ASCII names, locale-dependent case folding of an ASCII pattern cannot
# change the answer either.
#
# _gate_content_deny_lines <name> — content on stdin, <name> the ONE
# configured entry currently being checked (never the whole list: the
# deny-list loop in gate_scan_file already iterates by name, and keeping this
# to one comparison at a time matches _gate_unicode_py's index mode). Prints
# one 1-based line number per matching line. Exit contract mirrors WI-0049's
# path-side shape exactly, on the same sentinel, so the two consumers of this
# library cannot drift apart again: 0 = at least one match, printed to
# stdout; $_GATE_UNICODE_NO_MATCH = no match; any other status = the helper
# did not run to completion.
#
# Content arrives on STDIN, not through the environment the way the path
# subject does in _gate_unicode_py: an environment value is capped at
# ARG_MAX (measured 1 MiB on this machine), and the largest tracked file
# today (93 KB) fits only by chance — a file above that ceiling would fail
# hard with "argument list too long". `python3 -c` takes the SCRIPT as its
# argument instead: fixed, short, never sized by any file this gate reads —
# leaving stdin free to carry the actual content, unbounded by ARG_MAX.
_gate_content_deny_lines() {
  GATE_CD_NAME="$1" GATE_CD_NO_MATCH="$_GATE_UNICODE_NO_MATCH" python3 -c '
import os, re, sys, unicodedata

def nfc(s):
    return unicodedata.normalize("NFC", s)

no_match = int(os.environ["GATE_CD_NO_MATCH"])
name = nfc(os.environ.get("GATE_CD_NAME", ""))
if not name:
    sys.exit(no_match)
pat = re.compile(re.escape(name), re.IGNORECASE)
text = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")
found = False
for lineno, line in enumerate(text.split("\n"), start=1):
    if pat.search(nfc(line)):
        sys.stdout.write(str(lineno) + "\n")
        found = True
sys.exit(0 if found else no_match)
'
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

# _gate_hits <content> <grep-flags...> — print "<line>:<match>" records.
#
# grep's own exit status IS this function's return status: 0 a match, 1 no
# match (the ordinary empty-category case, silent by design), >=2 grep did
# not run to completion (crash, bad pattern, a locale/encoding fault on
# malformed multi-byte input). Deliberately no "|| true" here (WI-0051):
# that used to fold status 1 and status >=2 into the identical empty
# result, and every caller of this function read "the category is clean"
# either way. _gate_checked below is what turns the distinction into an
# abort — every check in gate_scan_file goes through IT, not this function
# directly.
_gate_hits() {
  local content="$1"; shift
  printf '%s\n' "$content" | grep "$@"
}

# _gate_checked <label> <content> <grep-flags...> — _gate_hits, plus the
# WI-0051 status split every call site below needs.
#
# On a normal run (grep exit 0 or 1) this prints exactly what _gate_hits
# would have and returns the same status. On a crash (exit >=2) it prints
# ONE "_error" record instead of the unreliable/partial match text, and
# returns that status.
#
# The record travels on stdout, the same channel _gate_emit already uses
# for "_exempt" a few lines below: every call site captures this function's
# output inside a "$(...)" command substitution, which forks a subshell,
# and a variable set inside a subshell does not survive it — only what the
# subshell PRINTS does.
#
# gate_scan_file's own callers (artifact-gate.sh, memory-sync.sh) capture
# gate_scan_file itself the same way, which is why every checked call site
# in gate_scan_file explicitly tests the returned status and `return`s
# instead of trusting `set -e` to do it: a function invoked from a tested
# context ("cmd || true", "if cmd; then" — which is exactly how BOTH entry
# points already call gate_scan_file) suspends errexit for everything
# inside it, transitively, not just its own top-level exit status. A crash
# several call-levels down would otherwise run the rest of the function to
# completion in silence. Measured, not assumed.
_gate_checked() {
  local label="$1" content="$2"; shift 2
  local out rc=0
  out="$(_gate_hits "$content" "$@")" || rc=$?
  if [ "$rc" -ge 2 ]; then
    _gate_emit 0 _error "$label check did not run — grep exited $rc"
    return "$rc"
  fi
  printf '%s\n' "$out"
  return "$rc"
}

# gate_scan_file <file> <profile>
gate_scan_file() {
  local f="$1" profile="${2:-artifact}"
  local content hits blob_hits cs_hits ip line found=0 rc=0
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
  # Two-pass, same idiom as GATE_RE_CONNSTRING/GATE_RE_PLACEHOLDER below:
  # extract candidates with `-o`, then drop those whose match contains a
  # placeholder word (WI-0035). `-o` also means a line with more than one
  # candidate now reports once per match instead of once per line — the same
  # granularity the connection-string pair already uses.
  hits="$(_gate_checked "secret/credential-assignment extract" "$content" -noEi -e "$GATE_RE_SECRET_KV")" || rc=$?
  [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
  if [ -n "$hits" ]; then
    rc=0
    hits="$(_gate_checked "secret/credential-assignment placeholder-filter" "$hits" -viE -e "$GATE_RE_SECRET_PLACEHOLDER_WORD")" || rc=$?
    [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
  fi
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" secret "possible credential assignment (keyword = <value>)"
    found=1
  done <<EOF
$hits
EOF

  rc=0
  hits="$(_gate_checked "secret/bearer-token extract" "$content" -noEi -e "$GATE_RE_SECRET_BEARER")" || rc=$?
  [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
  if [ -n "$hits" ]; then
    rc=0
    hits="$(_gate_checked "secret/bearer-token placeholder-filter" "$hits" -viE -e "$GATE_RE_SECRET_PLACEHOLDER_WORD")" || rc=$?
    [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
  fi
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" secret "bearer token header — verify it is not a real credential"
    found=1
  done <<EOF
$hits
EOF

  rc=0
  hits="$(_gate_checked "secret/vendor-token" "$content" -nE -e "$GATE_RE_SECRET_VENDOR")" || rc=$?
  [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
  rc=0
  blob_hits="$(_gate_checked "secret/token-blob" "$content" -nE -e "$GATE_RE_SECRET_BLOB")" || rc=$?
  [ "$rc" -lt 2 ] || { printf '%s\n' "$blob_hits"; return "$rc"; }
  hits="$hits
$blob_hits"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" secret "long token-like string — verify it is a name/path, not a value"
    found=1
  done <<EOF
$hits
EOF

  rc=0
  hits="$(_gate_checked "secret/private-key" "$content" -nE -e "$GATE_RE_PRIVATE_KEY")" || rc=$?
  [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
  rc=0
  cs_hits="$(_gate_checked "secret/connection-string extract" "$content" -noE -e "$GATE_RE_CONNSTRING")" || rc=$?
  [ "$rc" -lt 2 ] || { printf '%s\n' "$cs_hits"; return "$rc"; }
  if [ -n "$cs_hits" ]; then
    rc=0
    cs_hits="$(_gate_checked "secret/connection-string placeholder-filter" "$cs_hits" -vE -e "$GATE_RE_PLACEHOLDER")" || rc=$?
    [ "$rc" -lt 2 ] || { printf '%s\n' "$cs_hits"; return "$rc"; }
  fi
  hits="$hits
$cs_hits"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" secret "private key block or credential-bearing connection string"
    found=1
  done <<EOF
$hits
EOF

  # --- personal ------------------------------------------------------------
  rc=0
  hits="$(_gate_checked "personal/session-home" "$content" -nEi -e "$GATE_RE_PERSONAL")" || rc=$?
  [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" personal "session hash / home path"
    found=1
  done <<EOF
$hits
EOF

  rc=0
  hits="$(_gate_checked "personal/email extract" "$content" -noE -e "$GATE_RE_EMAIL")" || rc=$?
  [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
  if [ -n "$hits" ]; then
    rc=0
    hits="$(_gate_checked "personal/email reserved-domain-filter" "$hits" -viE -e "$GATE_RE_EMAIL_RESERVED")" || rc=$?
    [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
  fi
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    _gate_emit "${line%%:*}" personal "email address — remove or generalize"
    found=1
  done <<EOF
$hits
EOF

  if [ "$profile" = "memory" ]; then
    rc=0
    hits="$(_gate_checked "context/marker" "$content" -nEi -e "$GATE_RE_CONTEXT")" || rc=$?
    [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      _gate_emit "${line%%:*}" context "personal-context marker (colour vision / accessibility) — de-personalize before sharing"
      found=1
    done <<EOF
$hits
EOF

    rc=0
    hits="$(_gate_checked "personal/type-user" "$content" -nE -e "$GATE_RE_TYPE_USER")" || rc=$?
    [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      _gate_emit "${line%%:*}" personal "type: user is personal-only, never shared"
      found=1
    done <<EOF
$hits
EOF
  fi

  # --- network -------------------------------------------------------------
  rc=0
  hits="$(_gate_checked "network/ipv4" "$content" -noE -e "$GATE_RE_IPV4")" || rc=$?
  [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    ip="${line#*:}"
    # WI-0051 does not extend to this membership test: a broken
    # GATE_IP_ALLOWLIST regex here fails CLOSED already (the `&&` makes the
    # `if` false, so the IP falls through to being reported as a finding
    # rather than silently allowlisted), the opposite direction from the
    # "0 findings for a check that never ran" shape this file's other sites
    # were fixed for. Left alone deliberately, not an oversight.
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
    rc=0
    hits="$(_gate_checked "content/marker" "$content" -nE -e "$GATE_RE_CONTENT")" || rc=$?
    [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
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
  #
  # WI-0017: escalation to _gate_content_deny_lines is gated on the NAME
  # being non-ASCII, never on $content — see the comment on that function for
  # why gating on content was measured and rejected. An ASCII name always
  # takes the unchanged `grep -nFi` path below, so an all-ASCII deny list
  # never starts python3 at all.
  if [ -n "$GATE_DENY_NAMES" ]; then
    local idx=0 name
    while IFS= read -r name; do
      [ -n "$name" ] || continue
      idx=$((idx + 1))
      if _gate_is_ascii "$name"; then
        rc=0
        hits="$(_gate_checked "denylist/name #$idx" "$content" -nFi -- "$name")" || rc=$?
        [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
        while IFS= read -r line; do
          [ -n "$line" ] || continue
          _gate_emit "${line%%:*}" denylist "configured tenant/project name #$idx occurs here (name redacted)"
          found=1
        done <<EOF
$hits
EOF
      elif command -v python3 >/dev/null 2>&1; then
        local cd_lines rc=0
        cd_lines="$(printf '%s' "$content" | _gate_content_deny_lines "$name")" || rc=$?
        case "$rc" in
          0)
            while IFS= read -r line; do
              [ -n "$line" ] || continue
              _gate_emit "$line" denylist "configured tenant/project name #$idx occurs here (name redacted)"
              found=1
            done <<EOF
$cd_lines
EOF
            ;;
          "$_GATE_UNICODE_NO_MATCH") : ;;
          # Any other status means the comparison did not run to completion
          # (WI-0049 shape). Say so and let the ASCII matcher below answer
          # what it can, rather than reporting a clean file because the
          # helper crashed.
          *)
            printf 'gate: unicode content matcher failed (status %s) — falling back to ASCII folding\n' "$rc" >&2
            rc=0
            hits="$(_gate_checked "denylist/name #$idx (unicode-fallback)" "$content" -nFi -- "$name")" || rc=$?
            [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
            while IFS= read -r line; do
              [ -n "$line" ] || continue
              _gate_emit "${line%%:*}" denylist "configured tenant/project name #$idx occurs here (name redacted)"
              found=1
            done <<EOF
$hits
EOF
            ;;
        esac
      else
        # Announced, never silent — same message and same one-shot dedupe
        # flag _gate_needs_unicode already uses for the identical condition
        # on the path side.
        if [ "$_GATE_UNICODE_WARNED" -eq 0 ]; then
          printf 'gate: python3 not found — non-ASCII names are folded as ASCII only\n' >&2
          _GATE_UNICODE_WARNED=1
        fi
        rc=0
        hits="$(_gate_checked "denylist/name #$idx (ascii-only, no python3)" "$content" -nFi -- "$name")" || rc=$?
        [ "$rc" -lt 2 ] || { printf '%s\n' "$hits"; return "$rc"; }
        while IFS= read -r line; do
          [ -n "$line" ] || continue
          _gate_emit "${line%%:*}" denylist "configured tenant/project name #$idx occurs here (name redacted)"
          found=1
        done <<EOF
$hits
EOF
      fi
    done <<EOF
$GATE_DENY_NAMES
EOF
  fi

  [ "$found" -eq 0 ] || return 1
  return 0
}
