#!/usr/bin/env bash
# CCPR's wrapper around the EXTERNAL `shellcheck` tool for check-all.sh's
# catalogue (WI-0129 D2), the same seam artifact-gate.sh/conformance-run.sh/
# python-tests already are: check-all.sh invokes a shipped SIBLING SCRIPT,
# never a raw external binary directly, so a missing tool reports as a named,
# loud "could-not-run" finding instead of a bare, unexplained non-zero exit.
#
# Why this exists: this repository ships ten `# shellcheck` directives across
# its own scripts (source= hints, disable= suppressions) but, before this
# check, ran ShellCheck NOWHERE — it would have caught run-tests.sh's
# unquoted `$(pip show ...)` word-splitting (WI-0129 F8) on its own, before
# that shape had to be found by an external review instead.
#
# Usage:
#   bash scripts/shellcheck-run.sh [<project-dir>] [--help]
#
#   <project-dir>   directory to check (default: .)
#
# Scope (a decision, not an accident — see the header comment two paragraphs
# down): <project-dir>/scripts/*.sh, <project-dir>/scripts/lib/*.sh,
# <project-dir>/install.sh, at --severity=warning. scripts/local-llm/*.sh is
# OUT of scope by CONSTRUCTION, not by an exclusion list: a plain `scripts/
# *.sh` glob never descends into a subdirectory, so local-llm's user-owned,
# hardware-specific scripts (PROTECTED by install.sh, exempted from
# test_shell_script_syntax.py's syntax gate for the same reason) are simply
# never named. templates/ci/*.sh is out of scope for a different reason: it
# is `#!/usr/bin/env sh`, not bash — ShellCheck's bash-specific checks do not
# apply, and it already has its own POSIX-sh gate (WI-0027).
#
# Exit: 0 clean (0 findings at the configured severity) OR could-not-run
# (see below — the two are told apart by the REPORT TEXT, not the exit code,
# the same way conformance-run.sh's/memory-lint.sh's own no-scope states
# are: an exit code alone cannot distinguish "verified clean" from "verified
# nothing") · 1 one or more findings at or above the configured severity ·
# 2 bad usage (this wrapper's own CLI) or a ShellCheck-internal failure
# unrelated to a lint finding (e.g. it choked on a file rather than merely
# reporting on it).
#
# could-not-run, two distinct causes, same report idiom check-all.sh already
# reads from conformance-run.sh's "0 configured, 0 covered" and memory-
# lint.sh's "N of 4 targets present" states (KA-G-017: a run that verifies
# nothing is not a pass):
#   * ShellCheck is not installed on PATH -- reproducible on ANY clone that
#     has not separately installed it (it is not a CCPR dependency).
#   * The scope is empty -- no scripts/*.sh, no scripts/lib/*.sh, no
#     install.sh under <project-dir>. Never happens for THIS repository
#     (whose own scope check-all.sh gates this check on already implies
#     scripts/*.sh exists), but this script is runnable standalone against
#     any directory, and a project with none of the three should not be
#     silently misread as "0 findings, all clean".

set -euo pipefail

PROG="shellcheck-run"
SEVERITY="warning"  # WI-0129 D1 PO decision: --severity=error hid the
                     # install.sh:346 finding and the F8-class run-tests.sh
                     # finding; the full default threshold (style) was not
                     # chosen either -- see the work item's own measurement.

say()  { printf '%s\n' "$1"; }
warn() { say "$1" >&2; }
die()  { warn "$PROG: $1"; exit 2; }
usage() {
  # To the first blank line, not a hard-coded line number -- see check-all.sh's
  # own usage() for why (the header above is the contract; a fixed range
  # would silently truncate it the next time it grows).
  sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'  # exit-status: exempt set-e-sufficient
}

PROJECT_DIR_ARG=""
PROJECT_DIR_SET=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -*) die "unknown option: $1" ;;
    *)
      [ "$PROJECT_DIR_SET" -eq 0 ] || die "unexpected argument: $1"
      PROJECT_DIR_ARG="$1"
      PROJECT_DIR_SET=1
      ;;
  esac
  shift
done

PROJECT_DIR_ARG="${PROJECT_DIR_ARG:-.}"
[ -d "$PROJECT_DIR_ARG" ] || die "project directory does not exist: $PROJECT_DIR_ARG"
[ -r "$PROJECT_DIR_ARG" ] || die "project directory not readable: $PROJECT_DIR_ARG"
PROJECT_DIR="$(cd "$PROJECT_DIR_ARG" && pwd -P)"

# --- scope: the three globs named in the header, nullglob-safe under bash
# 3.2 (a no-match glob would otherwise contribute its own literal, unmatched
# pattern string as a "file"). Save/restore nullglob's PRIOR state -- this
# script is sourced by nothing today, but a future caller must not inherit a
# surprise shopt flip, the same discipline install.sh's own dotglob
# save/restore already follows for the identical reason.
FILES=()
_had_nullglob=0
shopt -q nullglob && _had_nullglob=1
shopt -s nullglob
FILES+=("$PROJECT_DIR"/scripts/*.sh)
FILES+=("$PROJECT_DIR"/scripts/lib/*.sh)
[ "$_had_nullglob" -eq 1 ] || shopt -u nullglob
[ -f "$PROJECT_DIR/install.sh" ] && FILES+=("$PROJECT_DIR/install.sh")

FILE_COUNT=${#FILES[@]}

NOW="$(date '+%d.%m.%Y %H:%M')"

_report_header() {
  echo "# ShellCheck Report"
  echo
  echo "**Project:** $PROJECT_DIR"
  echo "**Severity threshold:** $SEVERITY"
  echo "**Run:** $NOW"
  echo
}

# Two independent could-not-run causes -- both are checked and both are
# named when both apply. The causes used to be two separate early-exit `if`
# blocks; the first one (shellcheck missing) returned before the second
# (empty scope) was ever reached, so a machine hitting both only ever saw
# the first cause and the second silently disappeared from the report.
COULD_NOT_RUN_REASONS=()
command -v shellcheck >/dev/null 2>&1 || COULD_NOT_RUN_REASONS+=("shellcheck not installed on PATH")
[ "$FILE_COUNT" -eq 0 ] && COULD_NOT_RUN_REASONS+=("no scripts/*.sh, scripts/lib/*.sh, or install.sh found under $PROJECT_DIR")

if [ "${#COULD_NOT_RUN_REASONS[@]}" -gt 0 ]; then
  reasons_joined=""
  for reason in "${COULD_NOT_RUN_REASONS[@]}"; do
    if [ -z "$reasons_joined" ]; then
      reasons_joined="$reason"
    else
      reasons_joined="$reasons_joined; $reason"
    fi
  done
  _report_header
  echo "**Scope:** $FILE_COUNT file(s) matched — the shellcheck check DID NOT RUN ($reasons_joined)"
  echo
  echo "## Findings"
  echo
  echo "_not evaluated — see Scope above_"
  echo
  echo "---"
  echo
  echo "**Summary:** 0 file(s) scanned, 0 finding(s) — could-not-run"
  echo "**Exit:** 0"
  warn "$PROG: could-not-run — $reasons_joined"
  exit 0
fi

stdout_file="$(mktemp)"
stderr_file="$(mktemp)"
if shellcheck --severity="$SEVERITY" -f gcc "${FILES[@]}" >"$stdout_file" 2>"$stderr_file"; then
  rc=0
else
  rc=$?
fi
stdout_text="$(cat "$stdout_file")"
stderr_text="$(cat "$stderr_file")"
rm -f "$stdout_file" "$stderr_file"

_report_header
echo "**Scope:** $FILE_COUNT file(s) matched (scripts/*.sh, scripts/lib/*.sh, install.sh)"
echo
echo "## Findings"
echo
if [ -z "$stdout_text" ]; then
  echo "_none_"
else
  printf '%s\n' "$stdout_text"
fi
echo
echo "---"
echo

case "$rc" in
  0)
    echo "**Summary:** $FILE_COUNT file(s) scanned, 0 finding(s)"
    echo "**Exit:** 0"
    exit 0
    ;;
  1)
    finding_count=$(printf '%s\n' "$stdout_text" | grep -c ': .*\[SC[0-9]*\]' || true)  # exit-status: exempt grep-empty-is-valid
    echo "**Summary:** $FILE_COUNT file(s) scanned, ${finding_count} finding(s) at or above severity=$SEVERITY"
    echo "**Exit:** 1"
    exit 1
    ;;
  *)
    warn "$PROG: shellcheck itself failed (exit $rc), not a lint finding: ${stderr_text}"
    echo "**Summary:** $FILE_COUNT file(s) scanned, shellcheck failed (exit $rc)"
    echo "**Exit:** 2"
    exit 2
    ;;
esac
