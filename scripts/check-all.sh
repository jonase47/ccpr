#!/usr/bin/env bash
# check-all.sh — run every quality check CONTRIBUTING.md asks a contributor to
# remember, and report ACTUAL exit code against an EXPECTED one from a
# versioned baseline, not against "exit 0".
#
# Why "exit 0" is not the pass criterion: two of the seven checks below are
# non-zero BY DESIGN on a clean CCPR checkout right now (memory-lint.sh exits
# 1 on long-standing memory-freshness warnings; doc-volume-check.sh exits 2 on
# known oversized files pending a split). A script that failed on any non-zero
# exit would be permanently red on a correct tree, and a check that is red
# when nothing is wrong gets ignored within a fortnight. So every check's
# expected exit code is declared once, in scripts/check-all.baseline.tsv, and
# this script reports AGREEMENT or DIVERGENCE against it — never bare
# pass/fail against zero.
#
# Usage:
#   check-all.sh [--baseline <path>] [--help] [<project-dir>]
#
#   --baseline <path>   baseline TSV to compare against
#                        (default: <this-script's-own-dir>/check-all.baseline.tsv)
#   <project-dir>        directory to check (default: .)
#
# Exit: 0 every applicable check matches its baseline entry · 1 at least one
# divergence, a catalogue/baseline mismatch, or nothing was actually
# verified (every check could-not-run or was unmatched) · 2 the run could not
# be performed as asked (bad usage, missing/unreadable project dir or
# baseline, or a malformed baseline line).
#
#   0  every check that was actually run agreed with its baseline entry, and
#      at least one check WAS actually run.
#   1  ANY of: a check's actual exit code disagrees with its baseline entry
#      ("divergent"); the baseline names a check the catalogue below does not
#      have, or the catalogue has a check the baseline does not mention
#      ("mismatch" — both are refused rather than silently skipped); or NO
#      check was actually run at all (every one could-not-run or unmatched —
#      the same "a run that verified nothing is not a pass" rule KA-G-017
#      already states for conformance-run.sh, one level further in).
#   2  bad usage/flag, <project-dir> does not exist or is not readable, the
#      baseline file does not exist or is not readable, or a baseline line
#      could not be parsed (name or exit code missing/invalid). The baseline
#      SHAPE is unknown in this case — refused, not guessed at.
#
# A check "could-not-run" is neither a pass nor a failure and is counted in
# neither the match nor the divergence bucket (see "could-not-run" below) —
# reported under its own heading instead, exactly the class conformance-run.sh
# already carves out for the same reason (a check that cannot run must never
# look like a check that ran and found nothing).
#
# --- the seven checks, and which ones apply outside this repository --------
#
# Four are GENERIC over any documentation tree and always attempted, whatever
# <project-dir> is: phase-docs-lint, memory-lint, manual-lint,
# doc-volume-check. Three are CCPR-REPOSITORY-ONLY: artifact-gate.sh sweeps
# THIS repository's own shipped artifacts for the Constitution's Inviolable;
# conformance-run.sh runs THIS repository's own shipped checks against ITS
# consumers (it takes no project-dir argument at all — see its own header);
# python-tests runs the suite under scripts/tests/, which this repository is
# the only one that ships. All three are gated on one existence check:
# "<project-dir>/scripts/tests exists" — chosen over the alternative
# considered (comparing `git -C <project-dir> rev-parse --show-toplevel`
# against this script's own git root, the self-detection artifact-gate.sh
# itself already uses for its docs/-boundary sub-rule) because it is the ONE
# signal all three checks actually need: python-tests needs that exact path
# to exist to have anything to discover, and reusing it for the other two
# keeps a single, uniform "is this the CCPR checkout" answer rather than two
# different mechanisms answering the same question. The git-identity approach
# has its own accepted gap (a project that vendors a copy of this repository
# and points --project-dir at itself would satisfy it too) — not better here,
# just a different trade-off; not worth carrying a git dependency for.
# NEITHER approach is a name comparison against the string "ccpr" — both ask
# what actually exists on disk, which is the point.
#
# --- the seam: CCPR_CHECK_ALL_SCRIPT_DIR -------------------------------------
#
# Six of the seven checks are shipped SIBLING SCRIPTS, invoked as
# "$CHECK_SCRIPT_DIR/<name>.sh <args>". CHECK_SCRIPT_DIR defaults to this
# script's own directory and is overridable via CCPR_CHECK_ALL_SCRIPT_DIR —
# the exact seam conformance-run.sh already ships as CCPR_CONFORMANCE_
# SCRIPT_DIR, for the identical reason stated in its own header: the real
# checks never violate their own documented contracts against this
# repository's own fixtures, so without a stand-in there is nothing for the
# comparison logic to exercise, and running the real ones (four minutes for
# the python suite alone) in every test of the comparison logic would mean
# nobody runs those tests. scripts/tests/test_check_all.py points this
# variable at a scratch directory holding tiny stub scripts that `exit <N>`
# on demand — the SAME shape for every one of the six, so one seam covers
# all of them. A sibling script that does not exist under CHECK_SCRIPT_DIR
# (a scratch dir with no stub for it, or a genuinely broken installation) is
# itself a could-not-run outcome, not a crash — this is also what lets a test
# build the "every check could-not-run" case: point CCPR_CHECK_ALL_SCRIPT_DIR
# at an empty directory and <project-dir> at a location with no scripts/tests.
#
# The seventh check, python-tests, is not a sibling script — it is a fixed
# `python3 -m unittest discover` invocation — and needs no separate seam: it
# is already parametrised by <project-dir> (`-s <project-dir>/scripts/tests
# -t <project-dir>`), so a test simply points <project-dir> at a scratch
# directory carrying a tiny, fast, real test package instead of this
# repository's own ~1850-test, several-minutes suite.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROG="check-all"

say()  { printf '%s\n' "$1"; }
warn() { say "$1" >&2; }
die()  { warn "$PROG: $1"; exit 2; }
usage() {
  # To the first blank line, not a hard-coded line number — the header above
  # is the contract, and a fixed range would silently truncate it the next
  # time it grows (same reasoning as artifact-gate.sh's and
  # conformance-run.sh's own usage()).
  sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'  # exit-status: exempt set-e-sufficient
}

CHECK_SCRIPT_DIR="${CCPR_CHECK_ALL_SCRIPT_DIR:-$HERE}"

# The check catalogue — parallel arrays, not an associative array: this
# repository's floor is bash 3.2 (macOS /bin/bash), which has none (the same
# constraint conformance-run.sh's own table comment states).
CHECK_NAMES=(phase-docs-lint memory-lint manual-lint doc-volume-check artifact-gate conformance-run python-tests)
# "script" — a sibling script under CHECK_SCRIPT_DIR. "python" — the fixed
# unittest-discover invocation (no sibling script, see header above).
CHECK_KIND=(script script script script script script python)
CHECK_SCRIPTS=(phase-docs-lint.sh memory-lint.sh manual-lint.sh doc-volume-check.sh artifact-gate.sh conformance-run.sh "")
# 1 = CCPR-repository-only (gated on <project-dir>/scripts/tests existing —
# see header above).
CHECK_CCPR_ONLY=(0 0 0 0 1 1 1)
CHECK_COUNT=${#CHECK_NAMES[@]}

# --- CLI ---------------------------------------------------------------------

BASELINE_PATH=""
PROJECT_DIR_ARG=""
PROJECT_DIR_SET=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --baseline)
      shift
      [ "$#" -gt 0 ] || die "--baseline needs a path"
      [ -n "$1" ] || die "--baseline needs a non-empty path"
      BASELINE_PATH="$1"
      ;;
    -h|--help) usage; exit 0 ;;
    -*) die "unknown option: $1" ;;
    *)
      [ "$PROJECT_DIR_SET" -eq 0 ] || die "unexpected argument: $1"
      PROJECT_DIR_ARG="$1"
      PROJECT_DIR_SET=1
      ;;
  esac
  shift || true
done

PROJECT_DIR_ARG="${PROJECT_DIR_ARG:-.}"
[ -d "$PROJECT_DIR_ARG" ] || die "project directory does not exist: $PROJECT_DIR_ARG"
PROJECT_DIR="$(cd "$PROJECT_DIR_ARG" && pwd -P)"

[ -n "$BASELINE_PATH" ] || BASELINE_PATH="$CHECK_SCRIPT_DIR/check-all.baseline.tsv"
[ -f "$BASELINE_PATH" ] || die "baseline file not found: $BASELINE_PATH"
[ -r "$BASELINE_PATH" ] || die "baseline file not readable: $BASELINE_PATH"

# --- baseline reader (pure bash — no jq, no external tool; bash 3.2 has no
# associative arrays, so parallel arrays again) -------------------------------

BASELINE_NAMES=()
BASELINE_EXIT=()

# _baseline_index_of <name> — prints the array index of <name> in
# BASELINE_NAMES, or nothing (return 1) if absent. Small N (7 lines), a
# linear scan is plenty.
_baseline_index_of() {
  local target="$1" i n
  n=${#BASELINE_NAMES[@]}
  i=0
  while [ "$i" -lt "$n" ]; do
    [ "${BASELINE_NAMES[$i]}" = "$target" ] && { printf '%s\n' "$i"; return 0; }
    i=$((i + 1))
  done
  return 1
}

line_no=0
while IFS= read -r raw_line || [ -n "$raw_line" ]; do
  line_no=$((line_no + 1))
  case "$raw_line" in
    ''|'#'*) continue ;;
  esac
  b_name="" b_exit="" b_rest=""
  IFS=$'\t' read -r b_name b_exit b_rest <<<"$raw_line"
  [ -n "$b_name" ] || die "baseline line $line_no: missing check name"
  case "$b_exit" in
    ''|*[!0-9]*) die "baseline line $line_no ($b_name): expected exit code must be a non-negative integer, got '${b_exit}'" ;;
  esac
  if _baseline_index_of "$b_name" >/dev/null; then
    die "baseline line $line_no: duplicate check name '$b_name'"
  fi
  BASELINE_NAMES+=("$b_name")
  BASELINE_EXIT+=("$b_exit")
done < "$BASELINE_PATH"

[ "${#BASELINE_NAMES[@]}" -gt 0 ] || die "baseline file has no check entries: $BASELINE_PATH"

# --- catalogue <-> baseline cross-check (WI: "both must be loud") -----------
# A baseline naming a check the catalogue does not have, and a catalogue
# check the baseline does not mention, are both reported here — never
# silently skipped.

MISMATCH_FINDINGS=""
MISMATCH_COUNT=0

ci=0
while [ "$ci" -lt "$CHECK_COUNT" ]; do
  cname="${CHECK_NAMES[$ci]}"
  if ! _baseline_index_of "$cname" >/dev/null; then
    MISMATCH_FINDINGS="${MISMATCH_FINDINGS}- ${cname}: in the catalogue, but the baseline has no entry for it
"
    MISMATCH_COUNT=$((MISMATCH_COUNT + 1))
  fi
  ci=$((ci + 1))
done

bi=0
bn=${#BASELINE_NAMES[@]}
while [ "$bi" -lt "$bn" ]; do
  bname="${BASELINE_NAMES[$bi]}"
  found=0
  ci=0
  while [ "$ci" -lt "$CHECK_COUNT" ]; do
    [ "${CHECK_NAMES[$ci]}" = "$bname" ] && { found=1; break; }
    ci=$((ci + 1))
  done
  if [ "$found" -eq 0 ]; then
    MISMATCH_FINDINGS="${MISMATCH_FINDINGS}- ${bname}: in the baseline, but the catalogue has no check by that name
"
    MISMATCH_COUNT=$((MISMATCH_COUNT + 1))
  fi
  bi=$((bi + 1))
done

# --- run every catalogued check that has a baseline entry -------------------

RESULTS_TEXT=""
DIVERGENT_FINDINGS=""
COULD_NOT_RUN_FINDINGS=""
MATCHED_COUNT=0
DIVERGENT_COUNT=0
COULD_NOT_RUN_COUNT=0
RAN_COUNT=0

ci=0
while [ "$ci" -lt "$CHECK_COUNT" ]; do
  name="${CHECK_NAMES[$ci]}"
  kind="${CHECK_KIND[$ci]}"
  script="${CHECK_SCRIPTS[$ci]}"
  ccpr_only="${CHECK_CCPR_ONLY[$ci]}"

  if ! bidx="$(_baseline_index_of "$name")"; then
    # Already recorded above (a catalogue check the baseline does not
    # mention) — not run, not counted twice.
    ci=$((ci + 1))
    continue
  fi
  expected="${BASELINE_EXIT[$bidx]}"

  state="" reason="" rc=""

  if [ "$ccpr_only" = "1" ] && [ ! -d "$PROJECT_DIR/scripts/tests" ]; then
    state="could-not-run"
    reason="not the CCPR repository itself — $PROJECT_DIR/scripts/tests does not exist"
  fi

  if [ -z "$state" ] && [ "$kind" = "script" ]; then
    script_path="$CHECK_SCRIPT_DIR/$script"
    if [ ! -f "$script_path" ] || [ ! -r "$script_path" ]; then
      state="could-not-run"
      reason="script not found or not readable: $script_path"
    fi
  fi

  if [ -z "$state" ]; then
    stdout_file="$(mktemp)"
    stderr_file="$(mktemp)"

    case "$kind" in
      python)
        # `if CMD; then rc=0; else rc=$?; fi` — never `if ! CMD`, which
        # always captures 0 for `$?` inside its `then` branch (measured
        # directly building conformance-run.sh; same shape reused here).
        if python3 -m unittest discover -s "$PROJECT_DIR/scripts/tests" -t "$PROJECT_DIR" \
            >"$stdout_file" 2>"$stderr_file"; then
          rc=0
        else
          rc=$?
        fi
        ;;
      script)
        script_path="$CHECK_SCRIPT_DIR/$script"
        invoke_args=()
        case "$name" in
          phase-docs-lint|memory-lint) invoke_args=("$PROJECT_DIR") ;;
          manual-lint)                 invoke_args=("$PROJECT_DIR/Manual") ;;
          doc-volume-check)            invoke_args=("$PROJECT_DIR/docs") ;;
          artifact-gate)               invoke_args=(--repo "$PROJECT_DIR" --require-denylist) ;;
          conformance-run)             invoke_args=() ;;
        esac
        # bash 3.2: "${arr[@]}" on a zero-element array is safe under
        # set -u only via this length-gated shape (conformance-run.sh's
        # consumer-array iteration uses the same guard).
        if [ "${#invoke_args[@]}" -gt 0 ]; then
          if bash "$script_path" "${invoke_args[@]}" >"$stdout_file" 2>"$stderr_file"; then
            rc=0
          else
            rc=$?
          fi
        else
          if bash "$script_path" >"$stdout_file" 2>"$stderr_file"; then
            rc=0
          else
            rc=$?
          fi
        fi
        ;;
    esac

    stdout_text="$(cat "$stdout_file")"
    stderr_text="$(cat "$stderr_file")"
    rm -f "$stdout_file" "$stderr_file"

    # conformance-run.sh's own "not configured" state is exit-code-invisible
    # (documented: always exit 0, "so a clean machine is never blocked").
    # Detected instead from the literal report substring its own header
    # promises ("0 configured, 0 covered ... the conformance check DID NOT
    # RUN") — the same "read the report's own words, not a guess" discipline
    # conformance-run.sh's own _report_line_value already applies one level
    # further in.
    if [ "$name" = "conformance-run" ]; then
      case "$stdout_text" in
        *"0 configured, 0 covered"*)
          state="could-not-run"
          reason="no consumers configured (personal, non-distributed config) — nothing to compare against a baseline exit code"
          ;;
      esac
    fi

    if [ -z "$state" ]; then
      rc_str="$rc"
      if [ "$rc_str" = "$expected" ]; then
        state="match"
      else
        state="divergent"
        reason="expected exit ${expected}, got exit ${rc_str}"
      fi
    fi
  fi

  case "$state" in
    match)
      MATCHED_COUNT=$((MATCHED_COUNT + 1))
      RAN_COUNT=$((RAN_COUNT + 1))
      RESULTS_TEXT="${RESULTS_TEXT}- ${name}: exit ${rc} (expected ${expected}) — match
"
      ;;
    divergent)
      DIVERGENT_COUNT=$((DIVERGENT_COUNT + 1))
      RAN_COUNT=$((RAN_COUNT + 1))
      RESULTS_TEXT="${RESULTS_TEXT}- ${name}: exit ${rc} (expected ${expected}) — DIVERGENT
"
      DIVERGENT_FINDINGS="${DIVERGENT_FINDINGS}- ${name}: ${reason}
"
      ;;
    could-not-run)
      COULD_NOT_RUN_COUNT=$((COULD_NOT_RUN_COUNT + 1))
      RESULTS_TEXT="${RESULTS_TEXT}- ${name}: could-not-run — ${reason}
"
      COULD_NOT_RUN_FINDINGS="${COULD_NOT_RUN_FINDINGS}- ${name}: ${reason}
"
      ;;
  esac

  ci=$((ci + 1))
done

# --- report ------------------------------------------------------------------

NOW="$(date '+%d.%m.%Y %H:%M')"

echo "# Check-All Report"
echo
echo "**Project:** $PROJECT_DIR"
echo "**Baseline:** $BASELINE_PATH"
echo "**Checks:** $CHECK_COUNT catalogued, $RAN_COUNT ran, $COULD_NOT_RUN_COUNT could-not-run, $MISMATCH_COUNT mismatched"
echo "**Run:** $NOW"
echo
echo "## Results"
echo
if [ -z "$RESULTS_TEXT" ]; then
  echo "_none run_"
else
  printf '%s' "$RESULTS_TEXT"
fi
echo
echo "## Findings"
echo
echo "### Divergent"
echo
if [ "$DIVERGENT_COUNT" -eq 0 ]; then
  echo "_none_"
else
  printf '%s' "$DIVERGENT_FINDINGS"
fi
echo
echo "### Catalogue / Baseline Mismatch"
echo
if [ "$MISMATCH_COUNT" -eq 0 ]; then
  echo "_none_"
else
  printf '%s' "$MISMATCH_FINDINGS"
fi
echo
echo "### Could Not Run"
echo
if [ "$COULD_NOT_RUN_COUNT" -eq 0 ]; then
  echo "_none_"
else
  printf '%s' "$COULD_NOT_RUN_FINDINGS"
fi
echo
echo "---"
echo

if [ "$RAN_COUNT" -eq 0 ]; then
  warn "$PROG: NOTHING WAS VERIFIED — every catalogued check either could-not-run or had no baseline entry. This is not a pass."
fi

FINDINGS=$((DIVERGENT_COUNT + MISMATCH_COUNT))
echo "**Summary:** $CHECK_COUNT catalogued, $MATCHED_COUNT matched, $DIVERGENT_COUNT divergent, $COULD_NOT_RUN_COUNT could-not-run, $MISMATCH_COUNT mismatched"

if [ "$RAN_COUNT" -eq 0 ] || [ "$FINDINGS" -gt 0 ]; then
  echo "**Exit:** 1"
  exit 1
fi

echo "**Exit:** 0"
exit 0
