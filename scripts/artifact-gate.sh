#!/usr/bin/env bash
# artifact-gate.sh — machine-enforce the Constitution's Inviolable
# "No personal or tenant data in shipped artifacts".
#
# Sweeps every tracked non-binary file of a repository (or the files named on the
# command line) for secrets, personal data, network literals and a configured
# deny-list of tenant / project names. Exists because the breach it is named
# after was found by hand, and hand sweeps are what let it through.
#
# The patterns are NOT defined here — they live once in lib/discipline_gate.sh,
# shared with memory-sync.sh. This script owns scope, reporting and exit codes.
#
# The deny-list of tenant / project names is read from a personal, NON-
# DISTRIBUTED config (~/.claude/memory-sync.json, key gate.denyNames) or from
# CCPR_GATE_DENY_NAMES. It must never be committed to this repository: that
# would put the names into the artifacts the Inviolable protects. When no list
# is configured the run says so out loud instead of passing silently.
#
# Usage:
#   artifact-gate.sh [--repo <dir>] [--require-denylist] [<file> ...]
#
#   --repo <dir>         repository to sweep (default: the git root of $PWD)
#   --require-denylist   treat a missing deny-list as a finding (for CI)
#
# Exit: 0 clean, 1 findings, 2 configuration or zero scope.
#
#   0  nothing found, over a scope that was actually read
#   1  findings — and, with --require-denylist, an unconfigured deny-list
#   2  the run could not be performed as asked: bad usage, an unreadable file,
#      an unusable deny-list entry, or a scan scope that turned out to be empty
#
# --require-denylist deliberately exits 1 and not 2, although the deny-list
# defect next to it (an unusable entry) exits 2. Both readings are defensible,
# so the choice is written down here rather than left to be re-derived: the
# question is whether the run did its job. With --require-denylist it did — the
# scope was read and every configured check ran — and the operator asked for
# "no tenant names were checked" to be treated as a result of that run, which is
# a finding. An unusable entry or an empty scope means the run could not be
# performed as configured, and nothing was established either way. A CI job that
# distinguishes the two must never read "I checked nothing" as "I found
# something".

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/discipline_gate.sh
. "$HERE/lib/discipline_gate.sh"

PROG="artifact-gate"

# Every line this tool emits goes through the deny-list mask — not just the
# finding lines. A CI log is a shipped artifact too, so "a configured name never
# reaches an output" cannot hold for one class of line only: the exemption-audit
# line used to spell out the pattern-source file name on the very run where the
# findings above it masked that identical string, and die() echoed a path handed
# in on the command line. Masking is applied to the FINISHED line, because a
# configured name can straddle the boundary between the literal text and an
# interpolated value. The one deliberate exception is usage(), see above.
#
# The format string is always a literal at the call sites; the variable parts
# travel as %s arguments, so a '%' in a file name cannot be read as a directive.
# shellcheck disable=SC2059
say()  { printf '%s\n' "$(gate_redact_path "$(printf "$@")")"; }
warn() { say "$@" >&2; }
die()  { warn '%s: %s' "$PROG" "$*"; exit 2; }
usage() {
  # To the first blank line, not to a hard-coded line number: the header above
  # is the contract, and a fixed range silently truncates it the next time the
  # contract grows. The header is a shipped artifact that the sweep checks like
  # any other file, so it is the one output that is printed verbatim rather than
  # through the deny-list mask below — masking it would corrupt the usage text
  # for a name the sweep would already have reported.
  sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'  # exit-status: exempt set-e-sufficient
}

# Loaded before the arguments are parsed: die() masks configured names, and it
# can only do that once the list is known. A usage error names whatever the
# caller typed, which is exactly where a tenant-named path arrives from CI.
gate_load_config

REPO=""
REQUIRE_DENYLIST=0
FILES=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) shift; [ "$#" -gt 0 ] || die "--repo needs a directory"; REPO="$1" ;;
    --require-denylist) REQUIRE_DENYLIST=1 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; while [ "$#" -gt 0 ]; do FILES="$FILES$1
"; shift; done ;;
    -*) die "unknown option: $1" ;;
    *) FILES="$FILES$1
" ;;
  esac
  shift || true
done

# A deny-list that quietly lost an entry is the same defect as a pattern that
# quietly lost a shape: the run reports "deny-list active" and checks fewer names
# than its operator configured. Refuse here, before any scanning, so no findings
# can be produced by the shortened list this is complaining about. The entries
# are identified by position -- printing the name would put it in the CI log,
# which is precisely what the deny-list exists to prevent.
if [ -n "$GATE_DENY_UNUSABLE" ]; then
  die "deny-list entry $GATE_DENY_UNUSABLE is unusable (blank, or containing a line break) — fix gate.denyNames in $(gate_config_path). Refusing to run with a shorter list than configured."
fi

# --- collect the scan set -----------------------------------------------------
is_text() {
  # -I makes grep report no match for binary content; an empty file has nothing
  # to leak but is still text.
  #
  # WI-0053 sweep finding (site (c), not named by the item, found while
  # sweeping this file for the same defect class): a crash here used to be
  # swallowed by `||` and read back as "not text", the SAME misclassification
  # a genuine binary produces -- so the caller counted it as `skipped_binary`
  # and moved on, content never scanned, no error anywhere. Measured: a file
  # with a real credential in it, whose only classification grep crashes,
  # came back "scanned 1 files, 0 findings", exit 0, with a "1 binary
  # file(s) skipped" line that reads as routine housekeeping rather than a
  # failure. This is the more dangerous shape of the two sites the item DID
  # name -- (b)'s grep only trims the file LIST, this one skips a file that
  # is already in it -- so it takes the same answer: fail loudly.
  local rc=0
  LC_ALL=C grep -qI '' "$1" 2>/dev/null || rc=$?
  case "$rc" in
    0) return 0 ;;
    1) [ ! -s "$1" ] ;;
    *) die "text/binary classification did not run — grep exited $rc: $1" ;;
  esac
}

TMP="$(mktemp -t artifact-gate.XXXXXX)"
trap 'rm -f "$TMP"' EXIT

if [ -n "$FILES" ]; then
  # WI-0053: this filters the ARGUMENT list, not file content, so it cannot
  # hide a leak the way a content-scanning grep can -- but a crash here
  # silently shrinks WHAT GETS SCANNED, one command-line argument at a time,
  # exactly the shape WI-0015's dangling-symlink counter and the unreadable-
  # file guard below already refuse. `|| true` used to fold that together
  # with the ordinary case (every argument was blank, so `grep -v` finds
  # nothing to keep and exits 1 -- not a failure, an empty scope the guard
  # further down already reports on its own terms). The `if`-around-the-
  # assignment shape distinguishes the two the same way the content scan and
  # the PATH deny-list check below do.
  files_rc=0
  if printf '%s' "$FILES" | grep -v '^$' > "$TMP"; then
    files_rc=0
  else
    files_rc=$?
  fi
  if [ "$files_rc" -ge 2 ]; then
    die "file-list filter did not run — grep exited $files_rc"
  fi
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    [ -f "$f" ] || die "file not found: $f"
  done < "$TMP"
else
  if [ -z "$REPO" ]; then
    REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not a git repository — pass --repo <dir> or file arguments"
  fi
  [ -d "$REPO" ] || die "not a directory: $REPO"
  git -C "$REPO" rev-parse --show-toplevel >/dev/null 2>&1 || die "not a git repository: $REPO"
  git -C "$REPO" ls-files -z 2>/dev/null \
    | while IFS= read -r -d '' rel; do printf '%s\n' "$REPO/$rel"; done > "$TMP"  # exit-status: exempt set-e-sufficient
fi

# --- scan ---------------------------------------------------------------------
scanned=0
skipped_binary=0
skipped_symlink=0
findings=0
dirty_files=0
exempt_lines=0
exempt_file=""

while IFS= read -r f; do
  [ -n "$f" ] || continue

  # WI-0015: `install.sh` ships a symlink by copying it AS a link (`cp -R`
  # preserves symlinks, it does not follow them), so what CCPR ships for a
  # symlink is the link, never its target's bytes. The gate's subject is
  # therefore the link's own name, exactly like any other path -- the target
  # is never opened, resolving or dangling alike. `-L` is checked before `-f`
  # on purpose: `-f` follows a symlink and would fold a resolving link back
  # into the "regular file" branch below, silently reading through it again.
  # `test -L` also works for the same file argument whether it came from a
  # `git ls-files` sweep or from an explicit command-line path, unlike a
  # `git ls-files -s` mode-120000 lookup, which only has an index entry to
  # ask in the sweep case.
  is_symlink=0
  if [ -L "$f" ]; then
    is_symlink=1
  elif [ ! -f "$f" ]; then
    continue
  fi

  rel="$f"
  if [ -n "$REPO" ]; then rel="${f#"$REPO"/}"; fi

  # The name of the file is checked as well as its bytes, and it is checked
  # BEFORE anything is printed. Two separate defects met here: a file called
  # after a tenant with clean contents produced no finding at all, and the
  # finding line for a file that did have one printed the tenant name in its own
  # path prefix while ending in "(name redacted)". Matching the path fixes the
  # first; redacting `rel` once, for every line this file will emit, fixes the
  # second. The repository-relative path is what gets matched: a checkout that
  # merely happens to sit under a tenant-named directory says nothing about the
  # artifact, whereas the path inside the repo ships with it. This runs for a
  # symlink too -- a dangling link whose own filename carries a deny name must
  # still be reported, or the fix below reproduces the silent-scope-loss
  # defect it exists to close.
  # WI-0053: `|| true` used to swallow ANY nonzero status from
  # gate_path_deny_index alike -- "no match" (1, the ordinary case) and "the
  # ASCII matcher itself crashed" (>=2, see the function's own comment for
  # why the PATH side takes WI-0051's abort answer there). Capturing the real
  # status first, the same `if`-around-the-assignment shape the content scan
  # below already uses, is what lets the distinction survive past this line
  # instead of being read back as "no name found".
  path_rc=0
  if path_idx="$(gate_path_deny_index "$rel")"; then
    path_rc=0
  else
    path_rc=$?
  fi
  if [ "$path_rc" -ge 2 ]; then
    die "PATH deny-list check did not run — grep exited $path_rc: $rel"
  fi
  if [ -n "$path_idx" ]; then rel="$(gate_redact_path "$rel")"; fi

  out=""
  if [ "$is_symlink" -eq 1 ]; then
    # Never read through: not the target's content, not even a readability
    # check on it. A dangling link is not readable either, and the point is
    # that this is irrelevant here -- the target does not ship, so whether it
    # exists is not this gate's business. Counted on its own so a run cannot
    # silently shrink by the number of tracked links it walked past.
    skipped_symlink=$((skipped_symlink + 1))
  else
    # A file whose bytes could not be read has not been verified. `is_text`
    # below cannot tell "not text" from "not readable", so a locked file was
    # counted as a binary skip and a scope of one readable file next to it
    # exited 0 — the empty-scope failure shape (a green run over nothing), one
    # file at a time. The header has always promised exit 2 for unreadable
    # input; this is where that promise is kept.
    [ -r "$f" ] || die "unreadable file, nothing was verified: $rel"

    # The name is checked for every file; the CONTENT only for text. A binary's
    # bytes are out of scope by design, but its name ships exactly like any other
    # file's — an image called after a tenant sits in the index, in the checkout
    # and in every log line naming it. Skipping the whole file on `is_text` would
    # have left that visible copy unchecked.
    if ! is_text "$f"; then
      skipped_binary=$((skipped_binary + 1))
    else
      scanned=$((scanned + 1))
      # gate_scan_file's own header comment promises "returns 1 when there was
      # at least one finding, 0 otherwise" -- and, since WI-0051, >=2 when one
      # of its checks did not run to completion (a crashing grep, not a clean
      # file). Capturing the exit status this way (an `if` around the
      # assignment, not `|| true`) is required under `set -e`: the common case
      # IS a nonzero return (a dirty file), and `|| true` exists specifically
      # to survive that under `set -e` -- but it swallowed >=2 right along
      # with 1, which is the defect WI-0051 is about. The `if` form keeps the
      # same survival property for 1 while still letting >=2 through to the
      # check below.
      scan_rc=0
      if out="$(gate_scan_file "$f" artifact)"; then
        scan_rc=0
      else
        scan_rc=$?
      fi
      if [ "$scan_rc" -ge 2 ]; then
        die "$(printf '%s\n' "$out" | awk -F'\t' '$2 == "_error" { print $3; exit }')"  # exit-status: exempt internal-record-parsing
      fi

      # Split the bookkeeping record off before anything is counted as a finding.
      if [ -n "$out" ]; then
        exempt_here="$(printf '%s\n' "$out" | awk -F'\t' '$2 == "_exempt" { print $3 }')"  # exit-status: exempt internal-record-parsing
        if [ -n "$exempt_here" ]; then
          exempt_lines=$((exempt_lines + exempt_here))
          exempt_file="$f"
          out="$(printf '%s\n' "$out" | awk -F'\t' '$2 != "_exempt"')"  # exit-status: exempt internal-record-parsing
        fi
      fi
    fi
  fi

  if [ -z "$out" ] && [ -z "$path_idx" ]; then continue; fi

  dirty_files=$((dirty_files + 1))

  if [ -n "$path_idx" ]; then
    # Line 0: the finding is the name of the file, not a line inside it.
    say '%s:0: [denylist] configured tenant/project name #%s occurs in the FILE PATH (name redacted)' \
      "$rel" "$path_idx"
    findings=$((findings + 1))
  fi

  if [ -z "$out" ]; then continue; fi
  while IFS= read -r rec; do
    [ -n "$rec" ] || continue
    ln="${rec%%	*}"
    rest="${rec#*	}"
    cat_="${rest%%	*}"
    msg="${rest#*	}"
    # WI-0023: this file was not recognised as THE pattern-source file (the
    # self-exemption is bound to a resolved path, see lib/discipline_gate.sh),
    # but the specific line that fired still carries the self-exemption
    # marker. That happens for an installed gate scanning a checkout's own
    # copy of lib/discipline_gate.sh, or a byte-identical copy at any other
    # path. Widening the exemption to recognise it would let any file under
    # that name carry the marker as a suppression backdoor -- the finding
    # stays, only the message gains the context a human needs to triage it.
    if LC_ALL=C sed -n "${ln}p" "$f" 2>/dev/null | LC_ALL=C grep -qF "$GATE_EXEMPT_MARKER"; then
      msg="$msg -- this line carries the gate's own '$GATE_EXEMPT_MARKER' marker but $rel was not recognised as the pattern-source file; verify it is a foreign or differently-resolved copy of scripts/lib/discipline_gate.sh before treating it as a leak"
    fi
    say '%s:%s: [%s] %s' "$rel" "$ln" "$cat_" "$msg"
    findings=$((findings + 1))
  done <<EOF
$out
EOF
done < "$TMP"

# --- report -------------------------------------------------------------------
if [ "$exempt_lines" -gt 0 ]; then
  say '%s: %s pattern-source lines exempted in %s (audit: grep -n %s %s)' \
    "$PROG" "$exempt_lines" "$(basename "$exempt_file")" "$GATE_EXEMPT_MARKER" "$(basename "$exempt_file")"
fi

denylist_missing=0
case "$GATE_DENY_SOURCE" in
  none)
    denylist_missing=1
    say '%s: deny-list NOT CONFIGURED — no tenant/project names were checked. Set gate.denyNames in %s, or pass CCPR_GATE_DENY_NAMES.' \
      "$PROG" "$(gate_config_path)"
    ;;
  *) say '%s: deny-list active (source: %s)' "$PROG" "$GATE_DENY_SOURCE" ;;
esac

say '%s: scanned %s files, %s findings in %s files' "$PROG" "$scanned" "$findings" "$dirty_files"

# Name the part of the scope that was NOT read, so "scanned N files" cannot be
# mistaken for "N files is all there was". Binaries are excluded from the content
# checks by design, but their names were still checked, and saying so is what
# keeps the summary from contradicting a name-only finding above it.
if [ "$skipped_binary" -gt 0 ]; then
  say '%s: %s binary file(s) skipped — content not scanned, names still checked' \
    "$PROG" "$skipped_binary"
fi

# Same shape, same reason: a symlink's target is never read (WI-0015, see the
# scan loop above), so saying nothing here would make "scanned N files" read
# as "N files is all there was" for a tracked link too -- the exact defect
# this line exists to avoid repeating for binaries.
if [ "$skipped_symlink" -gt 0 ]; then
  say '%s: %s symlink(s) skipped — target not scanned, names still checked' \
    "$PROG" "$skipped_symlink"
fi

# A run that inspected nothing has proved nothing. Reporting "0 findings" over an
# empty scope is the failure mode least likely to be noticed, because it looks
# exactly like success: the CI job goes green having verified no artifact at all.
# Every candidate skipped as binary is, from the outside, indistinguishable from
# every candidate found clean. This is a scope error rather than a content
# finding, so it takes exit 2 (bad input) and not exit 1 (findings) — a CI job
# that distinguishes the two must not read "I checked nothing" as "I found
# something".
if [ "$findings" -gt 0 ]; then
  exit 1
fi

if [ "$scanned" -eq 0 ]; then
  warn '%s: no files were scanned — nothing was verified. Check the --repo path or the file arguments; a scope of only binary files or symlinks ends up empty too.' "$PROG"
  exit 2
fi
if [ "$REQUIRE_DENYLIST" -eq 1 ] && [ "$denylist_missing" -eq 1 ]; then
  warn '%s: --require-denylist was given but no deny-list is configured' "$PROG"
  exit 1
fi
exit 0
