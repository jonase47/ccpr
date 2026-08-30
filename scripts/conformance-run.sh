#!/usr/bin/env bash
# conformance-run.sh — run this repository's shipped checks against real
# consumer projects, as part of this repository's own verification.
# Design: docs/adr/ADR-0010-conformance-runs-against-consumers.md.
#
# WAVE 3 (this file, as of WI-0124): pins (ADR-0010 decision 2, class C3)
# join the classifier Wave 2 added. Every covered, non-optional consumer has
# the five shipped checks in CHECK_NAMES below actually run against it, and
# every finding is sorted into exactly one of C1 (contract violation), C2
# (zero scope over a non-empty target), Could-Not-Run (Wave 2b — the check
# refused to run against this target and said so on stderr; not a defect,
# not folded into the exit code, but never allowed to look like a clean pass
# either — see the **Checks:** accounting line and _run_and_classify_check's
# own could-not-run comment), C3 (Wave 3 — a configured, per-consumer PIN
# was violated: a concrete, dated expectation the operator recorded in
# conformance.pins[], each carrying a mandatory `why` printed next to its
# own violation) or P (a real finding in the consumer's own documents, never
# CCPR-attributable). A pin whose own check produced no report this run
# (could-not-run, or the rarer empty-both-streams C1 shape) is NOT
# EVALUATED — its own heading, never silently counted as satisfied. The
# report shape Wave 1 decided did not change underneath it: the same
# headings are still there, now populated instead of empty, plus the ones
# Wave 2b and Wave 3 each add.
#
# Usage:
#   conformance-run.sh [--require-consumers] [--consumer <id>] [--show-paths] [--help]
#
#   --require-consumers   treat zero configured consumers as a finding (exit 1)
#   --consumer <id>       restrict the run to one configured consumer
#   --show-paths          reveal each consumer's local path in the report
#
# Exit: 0 report produced, no CCPR-attributable finding · 1 a finding, or
# --require-consumers with none configured · 2 the run could not be
# performed as asked.
#
#   0  a report was produced. This includes the not-configured clean skip
#      (below) and a run whose only findings are class P.
#   1  at least one CCPR-attributable finding (C1, C2 or C3 — a violated
#      pin), OR --require-consumers was given and zero consumers are
#      configured.
#   2  the run could not be performed as asked: bad usage, a configured
#      consumer with no usable path, a non-optional consumer whose path does
#      not exist or is not readable, a malformed conformance config, or a
#      malformed pin (missing `why`, an unknown `check`, a `consumer` id
#      that was never configured, neither/both of
#      `expectFinding`/`expectField`, or an unknown `expectField` name).
#
# There is deliberately NO exit 3 (ADR-0010 decision 3, same reasoning
# artifact-gate.sh's header already states for its own two-code contract and
# anchor.sh's header states for its dedicated 3): no caller of this run needs
# a config error told apart from every other "could not run as asked"
# failure by exit code alone. Should one appear, record the new code and its
# reason in ADR-0010, not by reusing 2 for two things that turn out to need
# telling apart.
#
# Consumers are LOCAL FILESYSTEM PATHS ONLY. Nothing is fetched over a
# network — a consumer behind a VPN or with no public remote at all is
# exactly as usable as one that has both (ADR-0010 §2/§5). This is the whole
# answer to "does it run offline": yes, because there is nothing else it
# could do.
#
# Not-configured is exit 0 with a LOUD statement, not a silent pass
# (ADR-0010 §4, KA-G-017: a run reporting no scope is not a pass). The
# consumer list is personal, non-distributed configuration (§5) — a clean
# install of CCPR never has one, so this is the default state of every fresh
# install, not an edge case. The summary line always names how many
# consumers were covered, never only findings, and a stderr notice names the
# config path so a caller that treats stdout as its findings report cannot
# lose it. --require-consumers is the opt-in that turns an empty consumer
# list into a finding, mirroring artifact-gate.sh's --require-denylist for
# the same reason: a CI job that wants "nobody set this up" to be a failure
# asks for that explicitly, rather than the tool assuming it on everyone's
# behalf.
#
# A malformed config is exit 2, DELIBERATELY unlike lib/discipline_gate.sh's
# _gate_read_config, which treats a malformed config as absent
# (`except Exception: sys.exit(0)`). That is the right choice there — a
# broken config there means "use the default deny-list behaviour", itself a
# safe, documented state. It is the wrong choice here: a malformed
# `conformance` block does not mean "no consumers configured", it means the
# configured SCOPE IS UNKNOWN — some consumers may be readable and some may
# not, and reporting that as a clean not-configured skip would produce
# exactly the false-clean result ADR-0010 exists to close. The config
# reader's own exit status is therefore CHECKED below, never `|| true`.
#
# Reports name a consumer only by its configured `id`, never by its `path`
# (ADR-0010 §5) — the path is a local filesystem detail (frequently a home
# directory) with no reason to appear in an output the operator might paste
# or share. --show-paths is the explicit opt-in that reveals it.
#
# `pins` (ADR-0010 §5, class C3) are read starting this wave (Wave 3). Each
# entry names a `consumer` and a `check`, carries a mandatory non-empty
# `why`, and is EXACTLY ONE of:
#   expectFinding  a substring (or, with `regex: true`, a POSIX ERE) that
#                  must appear on at least `minCount` (default 1) lines of
#                  that check's own report for that consumer.
#   expectField    one of exit / errors / warnings / info / filesScanned,
#                  compared against `value`. filesScanned is a FLOOR (>=) —
#                  a growing consumer only strengthens it; every other
#                  field is exact equality. Deliberately never a commit SHA,
#                  and (as of Wave 4) never a fact about the CONSUMER's own
#                  working state either (ADR-0010 decision 2) — a pin's
#                  subject must be something CCPR controls. Wave 3 shipped
#                  two anchor-only fields, anchors.stale and
#                  anchors.maxBehind, that violated exactly this: both
#                  described how far the consumer's checked-out docs trail
#                  its own production code, so the moment that consumer
#                  commits, the pin fires as a false CCPR alarm. Removed in
#                  Wave 4 — see KNOWN_PIN_FIELDS below for the rule this
#                  leaves in place for the next field.
# A pin whose named check never produced a report for that consumer THIS RUN
# (could-not-run, or the rarer empty-both-streams C1 shape) is NOT EVALUATED
# — reported under its own heading, never silently counted as satisfied. A
# violated pin is class C3 and escalates the exit status the same way C1/C2
# already do.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/discipline_gate.sh
. "$HERE/lib/discipline_gate.sh"

PROG="conformance-run"

# No deny-list redaction pipeline here (that is artifact-gate.sh's job, over
# a different scope) — the only thing this script ever withholds by default
# is a consumer's PATH, gated on SHOW_PATHS at each call site below, not on
# a regex mask. The format string is always a literal at call sites; dynamic
# content always arrives as the %s argument, never spliced into the format
# itself.
# shellcheck disable=SC2059
say()  { printf '%s\n' "$1"; }
warn() { say "$1" >&2; }
die()  { warn "$PROG: $1"; exit 2; }
usage() {
  # To the first blank line, not a hard-coded line number — see
  # artifact-gate.sh's identical usage() for why a fixed range would
  # silently truncate the header the next time it grows.
  sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'  # exit-status: exempt set-e-sufficient
}

# --- WAVE 2: the classifier (ADR-0010 decision 2) --------------------------
#
# CCPR_CONFORMANCE_SCRIPT_DIR — defaults to this script's own directory.
# Two independent, both-real uses, not merely a test affordance:
#   1. TEST STUB SEAM — scripts/tests/test_conformance_run.py points this at
#      a scratch directory holding five tiny stub scripts that emit exact
#      bytes and exact exit statuses. The real checks never violate their
#      own documented contracts against this repository's own fixtures, so
#      without a stub there is nothing for C1 to classify.
#   2. WAVE 4 ACCEPTANCE — runs TODAY's classifier against a HISTORICAL
#      checkout of the checks themselves (`git worktree add <scratch>
#      7af990d`), reproducing a real, previously-shipped defect instead of a
#      synthetic one. Both uses point this variable at a directory holding
#      the five check scripts under their real filenames; the classifier
#      itself never knows or cares which reason moved it there.
CHECK_SCRIPT_DIR="${CCPR_CONFORMANCE_SCRIPT_DIR:-$HERE}"

# The check table (ADR-0010 follow-up 1 — "which shipped checks run under
# this mechanism" — Wave 2 settles it for these five). Parallel arrays, not
# an associative array: this repository's floor is bash 3.2 (macOS
# /bin/bash), which has none (lib/discipline_gate.sh's own header states the
# same constraint). commands/cleanup.md:143-196 already encodes the same
# per-check exit-code and argument knowledge in prose, for a human running
# these checks by hand one at a time — this table is the same knowledge,
# read by this script instead. Keeping the two in sync is a manual
# duplication today; unifying them is a separate item, not this wave.
CHECK_NAMES=(memory-lint phase-docs-lint manual-lint doc-volume-check anchor)
CHECK_SCRIPTS=(memory-lint.sh phase-docs-lint.sh manual-lint.sh doc-volume-check.sh anchor.sh)
CHECK_SUBCMD=("" "" "" "" status)
# "project" — invoked with the CONSUMER PATH itself: memory-lint.sh and
# phase-docs-lint.sh each append their OWN docs/ subpath internally
# (docs/memory, the nine PHASE_FOLDERS below), and anchor.sh's `status`
# subcommand does the same via its own PHASE_SCOPES. "docs" — invoked with
# CONSUMER PATH/docs: manual-lint.sh and doc-volume-check.sh are GENERIC
# over any root and do NOT default to docs/ on their own (manual-lint.sh's
# usage is literally "[<root-dir>]"; doc-volume-check.sh defaults an ABSENT
# argument to "$(pwd)/docs", which would resolve against THIS script's own
# cwd, not the consumer's). Getting this column wrong for either "docs"
# check silently turns a real, populated consumer into a Files-scanned:-0
# run — exactly the false positive C2 exists to catch, fed by our own
# argument mistake rather than a real defect (see test group C's
# docs-root-asymmetry test).
CHECK_ARG_SHAPE=(project project docs docs project)
CHECK_EXIT_SET=("0 1 2 3" "0 1 2" "0 1 2" "0 1 2" "0 2 3")
# 1 = this check's report has no "Files scanned:" line at all — anchor.sh's
# `status` counts SCOPES (docs/<phase>/<INDEX>.md), not files, and says so
# under its own "**Anchors:**" line instead. Structurally exempt from C2,
# not merely "never observed to fire" (ADR-0010 Wave 2 briefing: "anchor
# reports no Files scanned: line and is exempt from C2 — say so explicitly
# rather than letting it fall through").
CHECK_C2_EXEMPT=(0 0 0 0 1)
# 1 = this check's report carries a "**Summary:** N <x>, M <y>, K info."
# line the internal-contradiction rule (C1 rule 5 below) parses. anchor's
# report has no error/warning concept to contradict against its exit code.
CHECK_HAS_SUMMARY_LINE=(1 1 1 1 0)
CHECK_COUNT=${#CHECK_NAMES[@]}

# The same nine folder names phase-docs-lint.sh itself hardcodes
# (scripts/phase-docs-lint.sh:61, PHASE_FOLDERS), duplicated here rather
# than sourced — the C2 probe below must stay independent of the check it
# is probing (ADR-0010 decision 2: "an independent per-check candidate
# probe"). If phase-docs-lint.sh's own PHASE_FOLDERS were ever silently
# emptied by the same class of defect this probe exists to catch, sourcing
# it here would blind the probe along with the check.
PHASE_FOLDER_NAMES=(discovery concept validation architecture planning quality launch operations reviews)

# _in_documented_set <code> <space-separated set> — pure bash, no external
# tool. This entire classifier avoids grep/awk/sed/python3/git: every value
# it needs sits on ONE line of a small in-memory report, never piped, so a
# byte-wise `case`/`read` scan is both simpler and cheaper than an external
# regex tool for text this size, and it has no SIGPIPE/pipefail exposure at
# all (G-140) — there is no producer process for a consumer to starve.
_in_documented_set() {
  local code="$1" set_str="$2" candidate
  for candidate in $set_str; do
    [ "$candidate" = "$code" ] && return 0
  done
  return 1
}

# _report_line_value <report-text> <label, WITH trailing ": "> — prints the
# remainder of the FIRST line starting with that exact label, or nothing
# (and a nonzero return) if no such line exists. Reads via process
# substitution, not a pipe (manual-lint.sh:226 uses the same shape for the
# same reason) — a `while read` fed by `cmd | while ...` runs the loop in a
# subshell and can starve the producer with SIGPIPE under `pipefail` if the
# loop returns early on a match; `< <(...)` has no such pipeline for
# pipefail to inspect.
_report_line_value() {
  local text="$1" label="$2" line
  while IFS= read -r line; do
    case "$line" in
      "$label"*)
        printf '%s\n' "${line#$label}"
        return 0
        ;;
    esac
  done < <(printf '%s\n' "$text")
  return 1
}

# _report_summary_counts <report-text> — prints "ERR<TAB>WARN" from the
# first "**Summary:** N <word>, M <word>, K <word>." line, or nothing if
# absent. Tolerates either vocabulary this repository ships
# ("errors"/"warnings" for memory-lint/phase-docs-lint/manual-lint,
# "critical"/"warning" for doc-volume-check) because it never reads the
# WORD, only the two leading integers.
_report_summary_counts() {
  local text="$1" rest part1 part2 err warn
  rest="$(_report_line_value "$text" '**Summary:** ')" || return 1
  IFS=',' read -r part1 part2 _ < <(printf '%s\n' "$rest")
  part1="${part1# }"
  part2="${part2# }"
  err="${part1%% *}"
  warn="${part2%% *}"
  [ -n "$err" ] && [ -n "$warn" ] || return 1
  printf '%s\t%s\n' "$err" "$warn"
}

# _report_exit_code <report-text> — prints the leading integer of the first
# "**Exit:**" line, tolerating trailing prose (anchor.sh's own line reads
# "**Exit:** 0 (Stage 1 — data only, never a verdict)") — takes everything
# up to the first space.
_report_exit_code() {
  local text="$1" rest
  rest="$(_report_line_value "$text" '**Exit:** ')" || return 1
  printf '%s\n' "${rest%% *}"
}

# _has_interpreter_fatal_stderr <stderr-text> — pure bash `case` glob
# matching against the four shapes ADR-0010 names (a crashed interpreter,
# not a check's own deliberate error message).
_has_interpreter_fatal_stderr() {
  case "$1" in
    *"syntax error"*|*"unbound variable"*|*"command not found"*|*"Traceback (most recent call last)"*)
      return 0
      ;;
  esac
  return 1
}

# _c2_probe_has_candidates <check-name> <consumer-path> <docs-arg> —
# ADR-0010's "independent per-check candidate probe" (decision 2). Reads
# the FILESYSTEM directly, never the check's own report — that independence
# is the whole point: a check that is wrong about its own scope cannot also
# be trusted to say so. `find -print -quit` stops at the first match, so
# this never walks a large consumer tree further than it has to.
_c2_probe_has_candidates() {
  local check="$1" consumer_path="$2" docs_arg="$3" folder dir first
  case "$check" in
    memory-lint)
      dir="$consumer_path/docs/memory"
      [ -d "$dir" ] || return 1
      first="$(find "$dir" -type f -name '*.md' -print -quit 2>/dev/null)"
      [ -n "$first" ]
      ;;
    phase-docs-lint)
      for folder in "${PHASE_FOLDER_NAMES[@]}"; do
        dir="$consumer_path/docs/$folder"
        [ -d "$dir" ] || continue
        first="$(find "$dir" -type f -name '*.md' -print -quit 2>/dev/null)"
        [ -n "$first" ] && return 0
      done
      return 1
      ;;
    manual-lint|doc-volume-check)
      dir="$docs_arg"
      [ -d "$dir" ] || return 1
      first="$(find "$dir" -type f -name '*.md' -print -quit 2>/dev/null)"
      [ -n "$first" ]
      ;;
    *)
      return 1
      ;;
  esac
}

# --- WAVE 3: pin field/finding extraction (ADR-0010 §5, class C3) ---------
#
# _report_summary_info_count <report-text> — the third integer ("K" in
# "N errors, M warnings, K info.") on the first **Summary:** line, or
# returns 1 if absent. A SEPARATE function from _report_summary_counts
# above, not an extension of it: that function's own two-variable `read`
# (Rule 5's only caller) would silently swallow a third tab-separated field
# into its LAST variable rather than dropping it, so widening its output
# shape would corrupt an already-tested caller instead of only adding one.
_report_summary_info_count() {
  local text="$1" rest part1 part2 part3 info
  rest="$(_report_line_value "$text" '**Summary:** ')" || return 1
  IFS=',' read -r part1 part2 part3 _ < <(printf '%s\n' "$rest")
  part3="${part3# }"
  info="${part3%% *}"
  [ -n "$info" ] || return 1
  printf '%s\n' "$info"
}

# _pin_field_value <report-text> <actual-rc> <field> — the five
# expectField names ADR-0010's Wave 3/4 pin design supports: exit (the
# ACTUAL process exit status passed in, never the report's own
# self-declared **Exit:** line — the same trust rule every C1 rule above
# already applies), errors/warnings/info (the three **Summary:** counts —
# absent entirely from anchor's report, which has no Summary line at all,
# so this deliberately FAILS rather than guesses), and filesScanned (the
# **Files scanned:** line). Prints the value or returns 1 — a caller never
# sees a guessed value, only a real one or none.
#
# WI-0124 Wave 4 removed two anchor-only fields that lived here through
# Wave 3 (anchors.stale, anchors.maxBehind) — see the comment on
# KNOWN_PIN_FIELDS above (_conformance_read_config) for why: both described
# the CONSUMER's own working state, never CCPR behaviour, so no field like
# them belongs in this function either.
_pin_field_value() {
  local text="$1" actual_rc="$2" field="$3"
  local counts e w
  case "$field" in
    exit)
      printf '%s\n' "$actual_rc"
      ;;
    errors|warnings)
      counts="$(_report_summary_counts "$text")" || return 1
      IFS=$'\t' read -r e w < <(printf '%s\n' "$counts")
      if [ "$field" = "errors" ]; then
        printf '%s\n' "$e"
      else
        printf '%s\n' "$w"
      fi
      ;;
    info)
      _report_summary_info_count "$text"
      ;;
    filesScanned)
      _report_line_value "$text" '**Files scanned:** '
      ;;
    *)
      return 1
      ;;
  esac
}

# _pin_field_matches <field> <actual> <expected> — filesScanned is a floor
# an operator declares ("at least N files"), which only STRENGTHENS as a
# consumer grows (the same reasoning ADR-0010 gives against ever pinning a
# commit SHA: an equality pin on a growing consumer's file count would rot
# the moment the consumer adds one document). Every other field is exact.
_pin_field_matches() {
  local field="$1" actual="$2" expected="$3"
  case "$field" in
    filesScanned)
      [ "$actual" -ge "$expected" ] 2>/dev/null
      ;;
    *)
      [ "$actual" = "$expected" ]
      ;;
  esac
}

# _pin_count_finding_occurrences <report-text> <pattern> <is-regex 0/1> —
# LINES of the report containing <pattern>: a literal substring by default
# (`[[ $line == *"$pattern"* ]]` keeps a quoted variable's own
# `*`/`?`/`[` characters literal even though the surrounding `*`s are real
# wildcards — the standard bash idiom for a literal substring test, no
# external tool), or a POSIX ERE when is-regex is "1" (bash's own built-in
# `[[ =~ ]]` — G-140: no `grep` needed here, so no pipefail/SIGPIPE
# exposure either). One line matching twice still counts once: a pin's
# `why` names a FACT the report must contain, not an occurrence count
# inside a single line.
_pin_count_finding_occurrences() {
  local text="$1" pattern="$2" is_regex="$3" line count=0
  while IFS= read -r line; do
    if [ "$is_regex" = "1" ]; then
      [[ "$line" =~ $pattern ]] && count=$((count + 1))
    else
      [[ "$line" == *"$pattern"* ]] && count=$((count + 1))
    fi
  done < <(printf '%s\n' "$text")
  printf '%s\n' "$count"
}

# Finding accumulators — the same "growing string, one entry per line" shape
# CONSUMER_REPORT already uses below, for the same reason (a `set -u`-safe
# alternative to appending to a possibly-empty array whose emptiness is the
# common case).
C1_FINDINGS=""
C2_FINDINGS=""
P_FINDINGS=""
COULD_NOT_RUN_FINDINGS=""
C3_FINDINGS=""
PIN_NOT_EVALUATED_FINDINGS=""
C1_COUNT=0
C2_COUNT=0
P_COUNT=0
COULD_NOT_RUN_COUNT=0
C3_COUNT=0
PIN_NOT_EVALUATED_COUNT=0
# TOTAL_CHECKS_INVOKED — every call into _run_and_classify_check, whatever
# it classifies to (C1/C2/P/could-not-run/clean); the scope-accounting line
# below reports it alongside COULD_NOT_RUN_COUNT so "N checks ran" is never
# just asserted, it is CHECKS_RAN = TOTAL_CHECKS_INVOKED - COULD_NOT_RUN_COUNT.
TOTAL_CHECKS_INVOKED=0

# RESULT_* — one entry per _run_and_classify_check invocation, keyed by
# position (parallel arrays, bash 3.2 has no associative arrays — same
# constraint as everywhere else in this file), regardless of what that
# invocation classified to. This is Wave 3's own seam: pin evaluation
# (below, after every consumer is resolved) reads a check's raw stdout/rc
# back OUT of these arrays instead of re-invoking anything — a pin must
# see EXACTLY what the classifier already saw, not a second, possibly
# different run of the same check.
RESULT_CONSUMER_IDS=()
RESULT_CHECK_NAMES=()
RESULT_STDOUT=()
RESULT_RC=()

# _run_and_classify_check <check-index> <consumer-id> <consumer-path> —
# invokes one check against one covered consumer, records its raw result
# into RESULT_* above unconditionally, and appends AT MOST ONE finding to
# exactly one of the C1/C2/could-not-run/P accumulators (ADR-0010 decision
# 2: every finding is exactly one of C1/C2/C3/P — C3, pins, is evaluated
# separately below, once every consumer's checks have all run).
_run_and_classify_check() {
  local idx="$1" cid="$2" cpath="$3"
  local name="${CHECK_NAMES[$idx]}" script="${CHECK_SCRIPTS[$idx]}"
  local subcmd="${CHECK_SUBCMD[$idx]}" shape="${CHECK_ARG_SHAPE[$idx]}"
  local exit_set="${CHECK_EXIT_SET[$idx]}" c2_exempt="${CHECK_C2_EXEMPT[$idx]}"
  local has_summary="${CHECK_HAS_SUMMARY_LINE[$idx]}"
  local script_path="$CHECK_SCRIPT_DIR/$script"
  local target docs_arg
  local -a invoke_args
  local stdout_file stderr_file rc stdout_text stderr_text
  local label="${name} on ${cid}"

  TOTAL_CHECKS_INVOKED=$((TOTAL_CHECKS_INVOKED + 1))

  case "$shape" in
    docs) target="$cpath/docs" ;;
    *)    target="$cpath" ;;
  esac
  docs_arg="$cpath/docs"

  if [ -n "$subcmd" ]; then
    invoke_args=("$subcmd" "$target")
  else
    invoke_args=("$target")
  fi

  stdout_file="$(mktemp)"
  stderr_file="$(mktemp)"
  # `if CMD; then rc=0; else rc=$?; fi` — NOT `if ! CMD; then rc=$?; fi`.
  # docs/memory/senior-developer/external-tool-contracts.md's WI-0124 entry
  # measured directly that the `!`-negated form always captures 0, never
  # the real status; this shape (no `!`, real status lives in the `else`)
  # is the same one artifact-gate.sh's own scan loop already uses.
  if bash "$script_path" "${invoke_args[@]}" >"$stdout_file" 2>"$stderr_file"; then
    rc=0
  else
    rc=$?
  fi
  stdout_text="$(cat "$stdout_file")"
  stderr_text="$(cat "$stderr_file")"
  rm -f "$stdout_file" "$stderr_file"

  # Recorded UNCONDITIONALLY, before any classification below runs — a pin
  # (Wave 3) evaluates against whatever this check actually produced,
  # whichever class it lands in (C1/C2/could-not-run/P/clean).
  RESULT_CONSUMER_IDS+=("$cid")
  RESULT_CHECK_NAMES+=("$name")
  RESULT_STDOUT+=("$stdout_text")
  RESULT_RC+=("$rc")

  # Rule 1 — exit code outside the check's own documented set.
  if ! _in_documented_set "$rc" "$exit_set"; then
    C1_FINDINGS="${C1_FINDINGS}- ${label}: exit ${rc} is outside its documented set {${exit_set}}
"
    C1_COUNT=$((C1_COUNT + 1))
    return 0
  fi

  # Rule 2 — non-zero exit with empty stdout AND empty stderr (the
  # regression 5ee931b describes: "exit 1, zero bytes, no report" — on
  # BOTH streams, not just stdout). Measured directly (WI-0124 Wave 2b),
  # this repository's own die()-before-first-echo convention (usage(),
  # artifact-gate.sh's and manual-lint.sh's own die() paths) collides with
  # a stdout-only version of this rule: `anchor.sh status <non-git dir>`
  # exits 2 with 0 bytes on stdout but 166 bytes on stderr ("anchor: not a
  # git repository (or git not on PATH): ..."), while 5ee931b's own
  # regression (phase-docs-lint dying under `set -e`) was 0 bytes on BOTH
  # streams. A deliberate abort SPEAKS — on stderr, if nowhere else. A
  # silent death is silent on both streams. That is the discriminator: a
  # non-zero exit with empty stdout but something on stderr is not this
  # rule, it falls through to the could-not-run class below instead.
  if [ "$rc" -ne 0 ] && [ -z "$stdout_text" ] && [ -z "$stderr_text" ]; then
    C1_FINDINGS="${C1_FINDINGS}- ${label}: exit ${rc} with empty stdout and empty stderr — no report was produced
"
    C1_COUNT=$((C1_COUNT + 1))
    return 0
  fi

  # Rule 6 — an interpreter-fatal shape on stderr: a crashed interpreter,
  # not the check's own deliberate error message. Checked BEFORE the
  # could-not-run class below on purpose — a traceback is a bug in the
  # check itself, never a documented, deliberate refusal to run.
  if _has_interpreter_fatal_stderr "$stderr_text"; then
    C1_FINDINGS="${C1_FINDINGS}- ${label}: interpreter-fatal output on stderr (exit ${rc})
"
    C1_COUNT=$((C1_COUNT + 1))
    return 0
  fi

  # Could-not-run (WI-0124 Wave 2b) — non-zero exit, empty stdout, a
  # non-fatal MESSAGE on stderr (rule 6 above already took the
  # interpreter-fatal shapes). This is the production case the measurement
  # above names: the check refused to run against this target and SAID SO
  # on stderr — anchor.sh's "not a git repository" over a real, non-git
  # consumer path is exactly this, and is the shape Wave 4's historical
  # checkout would otherwise have hit. It is deliberately NOT C1 (the
  # check behaved exactly as it documents itself: an unsuitable target,
  # refused, reason given) and NOT P (there is no finding about the
  # consumer's own documents to report — there is no report at all). A
  # check that could not run must never look like a check that ran and
  # found nothing: that silent-clean shape is the exact failure this class
  # exists to close, one level below where ADR-0010 already guards it for
  # whole runs (KA-G-017). Does not escalate this run's exit code on its
  # own (see ATTRIBUTABLE below) — the check is not misbehaving, it is
  # correctly declining. It DOES decrement the checks-ran count in the
  # accounting line so it can never be missed.
  if [ "$rc" -ne 0 ] && [ -z "$stdout_text" ] && [ -n "$stderr_text" ]; then
    local stderr_first_line="${stderr_text%%$'\n'*}"
    COULD_NOT_RUN_FINDINGS="${COULD_NOT_RUN_FINDINGS}- ${label}: exit ${rc}, could not run — ${stderr_first_line}
"
    COULD_NOT_RUN_COUNT=$((COULD_NOT_RUN_COUNT + 1))
    return 0
  fi

  # Rule 3 — a mandatory report-skeleton line missing. anchor's own report
  # has no Files-scanned/Summary concept (it counts scopes, not files), so
  # its mandatory set is its OWN two lines, not the generic three.
  local missing="" required
  if [ "$name" = "anchor" ]; then
    for required in '**Anchors:**' '**Last production-code commit:**'; do
      case "$stdout_text" in
        *"$required"*) : ;;
        *) missing="${missing}${missing:+, }${required}" ;;
      esac
    done
  else
    for required in '**Files scanned:**' '**Summary:**' '**Exit:**'; do
      case "$stdout_text" in
        *"$required"*) : ;;
        *) missing="${missing}${missing:+, }${required}" ;;
      esac
    done
  fi
  if [ -n "$missing" ]; then
    C1_FINDINGS="${C1_FINDINGS}- ${label}: report is missing mandatory line(s): ${missing}
"
    C1_COUNT=$((C1_COUNT + 1))
    return 0
  fi

  # Rule 4 — the report's self-declared Exit disagrees with the process's
  # actual exit status.
  local declared_exit
  declared_exit="$(_report_exit_code "$stdout_text")" || declared_exit=""
  if [ -n "$declared_exit" ] && [ "$declared_exit" != "$rc" ]; then
    C1_FINDINGS="${C1_FINDINGS}- ${label}: report declares **Exit:** ${declared_exit} but the process actually exited ${rc}
"
    C1_COUNT=$((C1_COUNT + 1))
    return 0
  fi

  # Rule 5 — internal contradiction between the Summary counts and the exit
  # (`0 errors, 0 warnings` alongside a non-zero exit, or N>0 errors
  # alongside an exit other than the documented "errors present" code).
  if [ "$has_summary" = "1" ]; then
    local counts err_n warn_n
    counts="$(_report_summary_counts "$stdout_text")" || counts=""
    if [ -n "$counts" ]; then
      IFS=$'\t' read -r err_n warn_n < <(printf '%s\n' "$counts")
      if [ "$err_n" = "0" ] && [ "$warn_n" = "0" ] && [ "$rc" -ne 0 ]; then
        C1_FINDINGS="${C1_FINDINGS}- ${label}: report claims 0 errors, 0 warnings but exited ${rc}
"
        C1_COUNT=$((C1_COUNT + 1))
        return 0
      fi
      if [ "$err_n" != "0" ] && [ "$rc" -ne 2 ]; then
        C1_FINDINGS="${C1_FINDINGS}- ${label}: report claims ${err_n} error(s) but exited ${rc} (documented: errors imply exit 2)
"
        C1_COUNT=$((C1_COUNT + 1))
        return 0
      fi
    fi
  fi

  # C2 — zero scope over a non-empty target (ADR-0010 decision 2). The
  # WI-0121 reference case (phase-docs-lint over THIS repository: Files
  # scanned: 0, exit 0, because ccpr-gh has none of the nine phase folders)
  # must NOT fire here — the probe below is what tells that legitimate zero
  # apart from a check silently missing real content, and is deliberately
  # never consulted for a check with CHECK_C2_EXEMPT=1.
  if [ "$c2_exempt" != "1" ]; then
    local scanned
    scanned="$(_report_line_value "$stdout_text" '**Files scanned:** ')" || scanned=""
    if [ "$scanned" = "0" ] && _c2_probe_has_candidates "$name" "$cpath" "$docs_arg"; then
      C2_FINDINGS="${C2_FINDINGS}- ${label}: reports Files scanned: 0, but an independent candidate probe finds real documents in this check's own scope under this consumer
"
      C2_COUNT=$((C2_COUNT + 1))
      return 0
    fi
  fi

  # P — everything else: a real finding in the consumer's own documents,
  # attributed to the consumer, never escalating this run's exit code
  # (ADR-0010 decision 2 / decision 3's exit contract). Every check in this
  # table documents exit 0 as "clean" and every non-zero documented exit as
  # "something was found" — so a non-zero exit that survived rules 1-6 and
  # C2 above is, by each check's own contract, a genuine consumer finding.
  if [ "$rc" -ne 0 ]; then
    P_FINDINGS="${P_FINDINGS}- ${label}: exit ${rc} — see the check's own report for detail (consumer finding, not CCPR-attributable)
"
    P_COUNT=$((P_COUNT + 1))
  fi
}

# _conformance_read_config <config-path> — print one tab-separated record per
# configured consumer ("CONSUMER\t<id>\t<path>\t<0|1 optional>") and per
# configured pin ("PIN\t<consumer>\t<check>\t<finding|field>\t<expect-or-
# field>\t<mincount-or-value>\t<0|1 regex>\t<why>", eight columns always,
# so a single `IFS=$'\t' read` shape works for either record once the
# caller has switched on the leading word) on stdout. An absent config
# file, an absent `conformance` key, an absent or empty `consumers` list
# all print NOTHING and exit 0 — that is the not-configured state, decided
# by the caller, not by this reader. Anything the reader cannot safely
# interpret (invalid JSON, `conformance`/`consumers`/`pins` present but the
# wrong shape, a consumer entry missing a usable `id` or `path`, a pin
# missing `why`, naming an unknown `check`, carrying neither/both of
# `expectFinding`/`expectField`, or naming an unknown `expectField`) prints
# exactly one "ERROR\t<message>" record and exits 1 — the caller refuses to
# run rather than guess at a shortened or reinterpreted scope.
#
# This is the tail statement of a small shell helper, and its own exit
# status IS this function's exit status by design — every caller captures or
# checks the FUNCTION's return (same documented shape as
# lib/discipline_gate.sh's _gate_unicode_py). NOT marked
# `optional-config-read`: that category means "the caller's own defaults are
# the intended fallback", and this reader must never fall back — the caller
# below checks the real exit status and refuses to run on anything nonzero.
_conformance_read_config() {
  python3 - "$1" <<'PY'  # exit-status: exempt propagates-as-function-return
import json, os, sys

path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
except FileNotFoundError:
    sys.exit(0)
except Exception as e:
    print("ERROR\t" + str(e).replace("\n", " ").replace("\t", " "))
    sys.exit(1)

# WI-0124 Wave 4b: unknown keys, at all three config levels, are refused
# rather than silently ignored -- measured directly (hand-written config,
# 27.08.2026): nesting `pins` INSIDE a consumer object instead of at
# conformance.pins[] produced "0 checked, 0 satisfied", exit 0, discarding
# every expectation the operator wrote without saying so. This is the same
# "refuse rather than guess" discipline the rest of this reader already
# applies (a malformed shape here means the SCOPE is unknown, never "use a
# narrower default"), one level further in: not just "is this key's VALUE
# well-formed" but "is this key even part of the schema". `_comment` is
# accepted everywhere -- the shipped template
# (templates/memory-sync.example.json) uses it as its own documentation
# mechanism at all three levels, and rejecting it would refuse this
# repository's own example (proven by
# UnknownKeyRejectionTest.test_shipped_example_template_produces_no_unknown_key_error).
def _reject_unknown_keys(obj, known, where):
    unknown = sorted(k for k in obj if k not in known and k != "_comment")
    if unknown:
        print("ERROR\tunknown key(s) %s in %s -- known keys: %s"
              % (", ".join(repr(k) for k in unknown), where, ", ".join(sorted(known))))
        sys.exit(1)

conformance = cfg.get("conformance")
if conformance is None:
    sys.exit(0)
if not isinstance(conformance, dict):
    print("ERROR\t'conformance' is not an object")
    sys.exit(1)
_reject_unknown_keys(conformance, {"consumers", "pins"}, "'conformance'")

consumers = conformance.get("consumers")
if consumers is None:
    sys.exit(0)
if not isinstance(consumers, list):
    print("ERROR\t'conformance.consumers' is not a list")
    sys.exit(1)

# Built up across the consumers loop below, then consulted by the pins loop
# further down -- a pin naming a consumer id this run never configured can
# never be evaluated, which is a config error the operator wrote (most
# likely a typo), not a runtime could-not-run condition (WI-0124 Wave 4).
consumer_ids = set()

for position, c in enumerate(consumers, start=1):
    if not isinstance(c, dict):
        print("ERROR\tconsumers[%d] is not an object" % position)
        sys.exit(1)
    # Named by its own (unvalidated) id when present -- the production shape
    # this wave was found by (a consumer with a real id, holding a
    # misplaced `pins` key) reads far better as "consumer 'consumer-a'" than
    # as a bare position -- falling back to the position when id is absent
    # or not yet a usable string.
    consumer_label = "consumer %r" % c["id"] if isinstance(c.get("id"), str) and c.get("id") else "consumers[%d]" % position
    _reject_unknown_keys(c, {"id", "path", "optional"}, consumer_label)
    cid = c.get("id")
    if not isinstance(cid, str) or not cid:
        print("ERROR\tconsumers[%d] is missing a non-empty string id" % position)
        sys.exit(1)
    cpath = c.get("path")
    if not isinstance(cpath, str) or not cpath:
        print("ERROR\tconsumer %r has no usable path" % cid)
        sys.exit(1)
    # code-reviewer finding (WI-0124): templates/memory-sync.example.json's
    # own conformance.consumers[].path examples are `~`-prefixed, matching
    # ADR-0010 5's shown shape -- but a bare shell variable never
    # tilde-expands, and neither did this reader before this fix. An
    # operator who copies the shipped example literally got a silent "path
    # does not exist" (non-optional) or a silent "not covered" (optional),
    # the exact false-clean outcome this ADR exists to prevent. Same
    # expansion this repo already applies to another path-shaped config
    # field, workitems.youtrack's tokenFile (lib/workitems/youtrack.py).
    cpath = os.path.expanduser(cpath)
    optional = c.get("optional", False)
    if not isinstance(optional, bool):
        print("ERROR\tconsumer %r: optional must be true or false" % cid)
        sys.exit(1)
    # A tab or newline in id/path cannot occur here: both are required to be
    # ordinary JSON strings above, and this record format is itself
    # tab/newline-delimited -- same shape as
    # lib/discipline_gate.sh's NAME/BADNAME records.
    print("CONSUMER\t" + cid + "\t" + cpath + "\t" + ("1" if optional else "0"))
    consumer_ids.add(cid)

# WI-0124 Wave 3 (ADR-0010 decision 2, class C3): pins. CHECK_NAMES_PY
# duplicates conformance-run.sh's own bash CHECK_NAMES array by hand --
# the same accepted duplication commands/cleanup.md:143-196 already has
# relative to that table (module header above CHECK_SCRIPT_DIR), because
# a pin naming an unknown check must be refused HERE, at config-read time,
# and this python process has no access to the calling shell's arrays.
CHECK_NAMES_PY = ["memory-lint", "phase-docs-lint", "manual-lint", "doc-volume-check", "anchor"]
# WI-0124 Wave 4: anchors.stale and anchors.maxBehind were REMOVED from this
# set (they lived here through Wave 3). Both described the CONSUMER's own
# working state -- how far its checked-out docs trail its production code --
# never a CCPR behaviour. The moment that consumer commits production code,
# maxBehind legitimately changes and the pin fires as a false CCPR alarm,
# which is exactly the misattribution ADR-0010 decision 2 forbids; a
# comparison operator instead of equality would only delay that, not
# prevent it. THE RULE THIS ESTABLISHES: a pin's subject must be something
# CCPR controls, never a fact about the consumer's own state, whatever the
# comparison. Keep this comment here so the next field added to this set is
# checked against that rule before it lands.
KNOWN_PIN_FIELDS = {"exit", "errors", "warnings", "info", "filesScanned"}

pins = conformance.get("pins")
if pins is None:
    pins = []
if not isinstance(pins, list):
    print("ERROR\t'conformance.pins' is not a list")
    sys.exit(1)

for position, p in enumerate(pins, start=1):
    if not isinstance(p, dict):
        print("ERROR\tpins[%d] is not an object" % position)
        sys.exit(1)
    # `regex` is a genuine, tested pin key (an expectFinding modifier, read
    # further below) -- KNOWN_PIN_FIELDS above is a different vocabulary
    # entirely (the five expectField NAMES a pin may compare against), not
    # the set of keys a pin object itself may carry.
    pin_label = "pin (consumer %r)" % p["consumer"] if isinstance(p.get("consumer"), str) and p.get("consumer") else "pins[%d]" % position
    _reject_unknown_keys(
        p,
        {"consumer", "check", "expectFinding", "expectField", "value", "minCount", "why", "regex"},
        pin_label,
    )
    p_consumer = p.get("consumer")
    if not isinstance(p_consumer, str) or not p_consumer:
        print("ERROR\tpins[%d] is missing a non-empty string consumer" % position)
        sys.exit(1)
    if p_consumer not in consumer_ids:
        print("ERROR\tpins[%d] names consumer %r, which is not a configured consumer id -- known consumers: %s"
              % (position, p_consumer, ", ".join(sorted(consumer_ids)) or "(none configured)"))
        sys.exit(1)
    p_check = p.get("check")
    if not isinstance(p_check, str) or p_check not in CHECK_NAMES_PY:
        print("ERROR\tpins[%d] (consumer %r) names an unknown check %r -- known checks: %s"
              % (position, p_consumer, p_check, ", ".join(CHECK_NAMES_PY)))
        sys.exit(1)
    # why is a MANDATORY, non-empty explanation (ADR-0010 §5) -- checked
    # before expectFinding/expectField below so a pin missing BOTH why and
    # an expectation still reports the why gap first, deterministically.
    p_why = p.get("why")
    if not isinstance(p_why, str) or not p_why.strip():
        print("ERROR\tpins[%d] (consumer %r, check %r) has no why -- every pin must explain, "
              "at pin time, why this consumer fact is CCPR behaviour rather than consumer content"
              % (position, p_consumer, p_check))
        sys.exit(1)
    p_why_clean = p_why.replace("\n", " ").replace("\t", " ")

    has_finding = "expectFinding" in p
    has_field = "expectField" in p
    if has_finding == has_field:
        print("ERROR\tpins[%d] (consumer %r, check %r) must carry exactly one of expectFinding or expectField"
              % (position, p_consumer, p_check))
        sys.exit(1)

    if has_finding:
        expect = p.get("expectFinding")
        if not isinstance(expect, str) or not expect:
            print("ERROR\tpins[%d] (consumer %r, check %r): expectFinding must be a non-empty string"
                  % (position, p_consumer, p_check))
            sys.exit(1)
        min_count = p.get("minCount", 1)
        if not isinstance(min_count, int) or isinstance(min_count, bool) or min_count < 1:
            print("ERROR\tpins[%d] (consumer %r, check %r): minCount must be a positive integer"
                  % (position, p_consumer, p_check))
            sys.exit(1)
        is_regex = p.get("regex", False)
        if not isinstance(is_regex, bool):
            print("ERROR\tpins[%d] (consumer %r, check %r): regex must be true or false"
                  % (position, p_consumer, p_check))
            sys.exit(1)
        expect_clean = expect.replace("\n", " ").replace("\t", " ")
        print("PIN\t" + p_consumer + "\t" + p_check + "\tfinding\t" + expect_clean + "\t"
              + str(min_count) + "\t" + ("1" if is_regex else "0") + "\t" + p_why_clean)
    else:
        field = p.get("expectField")
        if not isinstance(field, str) or field not in KNOWN_PIN_FIELDS:
            print("ERROR\tpins[%d] (consumer %r, check %r) names an unknown expectField %r -- known fields: %s"
                  % (position, p_consumer, p_check, field, ", ".join(sorted(KNOWN_PIN_FIELDS))))
            sys.exit(1)
        value = p.get("value")
        if not isinstance(value, int) or isinstance(value, bool):
            print("ERROR\tpins[%d] (consumer %r, check %r): value must be an integer"
                  % (position, p_consumer, p_check))
            sys.exit(1)
        print("PIN\t" + p_consumer + "\t" + p_check + "\tfield\t" + field + "\t"
              + str(value) + "\t0\t" + p_why_clean)

sys.exit(0)
PY
}

REQUIRE_CONSUMERS=0
CONSUMER_FILTER=""
SHOW_PATHS=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --require-consumers) REQUIRE_CONSUMERS=1 ;;
    --consumer)
      shift
      [ "$#" -gt 0 ] || die "--consumer needs an id"
      # code-reviewer finding (WI-0124): CONSUMER_FILTER="" is also the
      # unset default below, and the later filter step only checks
      # `[ -n "$CONSUMER_FILTER" ]` -- an empty string given here would
      # silently be indistinguishable from "no filter" and run EVERY
      # configured consumer instead of failing. Refuse it here, at the
      # point where "empty" and "not given" can still be told apart.
      [ -n "$1" ] || die "--consumer needs a non-empty id"
      CONSUMER_FILTER="$1"
      ;;
    --show-paths) SHOW_PATHS=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) die "unknown option: $1" ;;
    *) die "unexpected argument: $1" ;;
  esac
  shift || true
done

CFG="$(gate_config_path)"

# Checked, not `|| true` — see _conformance_read_config's own comment and
# the module header above for why this reader must never fall back.
#
# `|| read_rc=$?`, NOT `if ! CONF_OUT=$(...); then read_rc=$?; fi`: measured
# directly while building this script (bash 3.2.57) that the latter is a
# real trap, not a style preference -- `!` negates the exit status of the
# WHOLE tested command for control-flow purposes, and `$?` inside the
# resulting `then` branch reports THAT negated value (always 0), not the
# command's own status. `CMD || rc=$?` (the same shape
# lib/discipline_gate.sh's _gate_unicode_py callers already use) has no `!`
# in front of the tested command, so `$?` inside the `rc=$?` assignment is
# still the real one.
read_rc=0
CONF_OUT="$(_conformance_read_config "$CFG")" || read_rc=$?
if [ "$read_rc" -ne 0 ]; then
  # awk parses THIS script's own well-formed tab-delimited record above, not
  # external/adversarial input -- same reasoning as
  # lib/discipline_gate.sh's other internal-record-parsing sites.
  err_msg="$(printf '%s\n' "$CONF_OUT" | awk -F'\t' '$1 == "ERROR" { print $2; exit }')"  # exit-status: exempt internal-record-parsing
  die "malformed conformance config ($CFG): ${err_msg:-config could not be parsed}"
fi

CONSUMER_IDS=()
CONSUMER_PATHS=()
CONSUMER_OPTIONAL=()
# WI-0124 Wave 3: PIN_* alongside CONSUMER_* -- CONF_OUT now carries two
# record shapes (see _conformance_read_config's own comment for the
# column layout), dispatched by a `case` on the whole line rather than by
# reading a fixed variable count up front, since CONSUMER records have
# four columns and PIN records have eight.
PIN_CONSUMER=()
PIN_CHECK=()
PIN_KIND=()
PIN_EXPECT=()
PIN_PARAM=()
PIN_REGEX=()
PIN_WHY=()
while IFS= read -r rec_line; do
  case "$rec_line" in
    CONSUMER$'\t'*)
      IFS=$'\t' read -r rec_type rec_id rec_path rec_optional <<<"$rec_line"
      CONSUMER_IDS+=("$rec_id")
      CONSUMER_PATHS+=("$rec_path")
      CONSUMER_OPTIONAL+=("$rec_optional")
      ;;
    PIN$'\t'*)
      # rec_type: a required READ TARGET, never itself consumed (WI-0129
      # D1, ShellCheck SC2034) -- the case pattern above already tells this
      # branch it is "PIN", the same discriminant this read absorbs so the
      # remaining tab-separated columns line up with p_consumer onward.
      # shellcheck disable=SC2034
      IFS=$'\t' read -r rec_type p_consumer p_check p_kind p_expect p_param p_regex p_why <<<"$rec_line"
      PIN_CONSUMER+=("$p_consumer")
      PIN_CHECK+=("$p_check")
      PIN_KIND+=("$p_kind")
      PIN_EXPECT+=("$p_expect")
      PIN_PARAM+=("$p_param")
      PIN_REGEX+=("$p_regex")
      PIN_WHY+=("$p_why")
      ;;
    *)
      : # blank line (an entirely empty CONF_OUT) or anything unrecognised
      ;;
  esac
done <<EOF
$CONF_OUT
EOF

# --consumer restricts the run to one already-configured id -- an id that
# does not resolve is a usage error (exit 2), not a silent narrowing to zero.
if [ -n "$CONSUMER_FILTER" ]; then
  FILTERED_IDS=()
  FILTERED_PATHS=()
  FILTERED_OPTIONAL=()
  i=0
  n=${#CONSUMER_IDS[@]}
  while [ "$i" -lt "$n" ]; do
    if [ "${CONSUMER_IDS[$i]}" = "$CONSUMER_FILTER" ]; then
      FILTERED_IDS+=("${CONSUMER_IDS[$i]}")
      FILTERED_PATHS+=("${CONSUMER_PATHS[$i]}")
      FILTERED_OPTIONAL+=("${CONSUMER_OPTIONAL[$i]}")
    fi
    i=$((i + 1))
  done
  [ "${#FILTERED_IDS[@]}" -gt 0 ] || die "unknown consumer id: $CONSUMER_FILTER (not configured)"
  CONSUMER_IDS=("${FILTERED_IDS[@]}")
  CONSUMER_PATHS=("${FILTERED_PATHS[@]}")
  CONSUMER_OPTIONAL=("${FILTERED_OPTIONAL[@]}")
fi

# --- resolve each consumer -----------------------------------------------
# WI-0021 (project memory): never expand "${arr[@]}" or "${arr[@]:-}" on an
# array that might be empty under `set -u` -- both crash or fabricate a
# phantom element. Length-gated numeric-index iteration is the only safe
# shape, so CONFIGURED=0 (the not-configured case) never touches [@] at all.
CONFIGURED=${#CONSUMER_IDS[@]}
COVERED=0
CONSUMER_REPORT=""

i=0
while [ "$i" -lt "$CONFIGURED" ]; do
  id="${CONSUMER_IDS[$i]}"
  path="${CONSUMER_PATHS[$i]}"
  optional="${CONSUMER_OPTIONAL[$i]}"

  path_suffix=""
  [ "$SHOW_PATHS" -eq 1 ] && path_suffix=" (path: $path)"

  if [ -d "$path" ] && [ -r "$path" ]; then
    COVERED=$((COVERED + 1))
    CONSUMER_REPORT="${CONSUMER_REPORT}- ${id}: covered${path_suffix}
"
    j=0
    while [ "$j" -lt "$CHECK_COUNT" ]; do
      _run_and_classify_check "$j" "$id" "$path"
      j=$((j + 1))
    done
  elif [ "$optional" = "1" ]; then
    CONSUMER_REPORT="${CONSUMER_REPORT}- ${id}: not covered — optional, path missing${path_suffix}
"
  else
    die "consumer ${id}: path does not exist or is not readable${path_suffix}"
  fi
  i=$((i + 1))
done

# --- WAVE 3: pins (ADR-0010 §5, class C3) -----------------------------------
#
# Runs once every consumer's checks have all executed, so RESULT_* above
# holds every (consumer, check) pair this run actually invoked. Every
# configured pin gets EXACTLY one outcome: satisfied, violated (a C3
# finding, escalates the exit status), or not-evaluated (the pin's own
# check produced no report for this consumer this run -- could-not-run, or
# the rarer empty-both-streams C1 shape -- so there is nothing to compare
# the pin against). PINS_TOTAL stays the STATIC count of configured pins
# (never shrunk by a not-evaluated pin) so a pin that silently stops being
# evaluated shows up as a drop in PINS_SATISFIED, not as a hidden,
# shrunk denominator (WI-0124 Wave 3 briefing: "a pin that silently stops
# being evaluated is visible").
PINS_TOTAL=${#PIN_CONSUMER[@]}
PINS_SATISFIED=0
p_i=0
while [ "$p_i" -lt "$PINS_TOTAL" ]; do
  p_consumer="${PIN_CONSUMER[$p_i]}"
  p_check="${PIN_CHECK[$p_i]}"
  p_kind="${PIN_KIND[$p_i]}"
  p_expect="${PIN_EXPECT[$p_i]}"
  p_param="${PIN_PARAM[$p_i]}"
  p_regex="${PIN_REGEX[$p_i]}"
  p_why="${PIN_WHY[$p_i]}"
  pin_label="${p_check} on ${p_consumer}"

  # Linear search over RESULT_* for the (consumer, check) pair this pin
  # names -- small N (consumers × 5 checks), no need for anything fancier
  # on bash 3.2's parallel-array constraint.
  result_idx=""
  r_i=0
  r_n=${#RESULT_CONSUMER_IDS[@]}
  while [ "$r_i" -lt "$r_n" ]; do
    if [ "${RESULT_CONSUMER_IDS[$r_i]}" = "$p_consumer" ] && [ "${RESULT_CHECK_NAMES[$r_i]}" = "$p_check" ]; then
      result_idx="$r_i"
      break
    fi
    r_i=$((r_i + 1))
  done

  # Short-circuit order matters: when result_idx is empty, the second test
  # is never reached, so "${RESULT_STDOUT[$result_idx]}" never expands
  # with an empty index (measured directly: bash evaluates a `||`'s right-
  # hand word only when it actually runs the command).
  if [ -z "$result_idx" ] || [ -z "${RESULT_STDOUT[$result_idx]}" ]; then
    PIN_NOT_EVALUATED_FINDINGS="${PIN_NOT_EVALUATED_FINDINGS}- ${pin_label}: not evaluated — this check produced no report for this consumer this run (see Could Not Run / Contract violations above)
"
    PIN_NOT_EVALUATED_COUNT=$((PIN_NOT_EVALUATED_COUNT + 1))
    p_i=$((p_i + 1))
    continue
  fi

  report_text="${RESULT_STDOUT[$result_idx]}"
  actual_rc="${RESULT_RC[$result_idx]}"
  satisfied=0

  if [ "$p_kind" = "finding" ]; then
    count="$(_pin_count_finding_occurrences "$report_text" "$p_expect" "$p_regex")"
    if [ "$count" -ge "$p_param" ]; then
      satisfied=1
    fi
    detail="expected \"${p_expect}\" at least ${p_param} time(s), found ${count}"
  else
    value="$(_pin_field_value "$report_text" "$actual_rc" "$p_expect")" || value=""
    if [ -n "$value" ] && _pin_field_matches "$p_expect" "$value" "$p_param"; then
      satisfied=1
    fi
    if [ "$p_expect" = "filesScanned" ]; then
      detail="expected ${p_expect} >= ${p_param}, found ${value:-<unparseable>}"
    else
      detail="expected ${p_expect} = ${p_param}, found ${value:-<unparseable>}"
    fi
  fi

  if [ "$satisfied" -eq 1 ]; then
    PINS_SATISFIED=$((PINS_SATISFIED + 1))
  else
    C3_FINDINGS="${C3_FINDINGS}- ${pin_label}: pin violated (${detail}) — ${p_why}
"
    C3_COUNT=$((C3_COUNT + 1))
  fi
  p_i=$((p_i + 1))
done

# --- report ----------------------------------------------------------------
NOT_RUN_SUFFIX=""
[ "$CONFIGURED" -eq 0 ] && NOT_RUN_SUFFIX=" — the conformance check DID NOT RUN"

# CHECKS_RAN — the scope-accounting complement to COULD_NOT_RUN_COUNT
# (WI-0124 Wave 2b): a consumer where checks silently could-not-run must
# never read as fully covered. Printed alongside **Consumers:** so the
# top-of-report accounting names both "how many consumers" and "how many of
# their checks actually ran" — the same discipline KA-G-017 already applies
# to a run with zero consumer scope, one level further in.
CHECKS_RAN=$((TOTAL_CHECKS_INVOKED - COULD_NOT_RUN_COUNT))

NOW="$(date '+%d.%m.%Y %H:%M')"

echo "# Conformance Run Report"
echo
echo "**Consumers:** $CONFIGURED configured, $COVERED covered$NOT_RUN_SUFFIX"
echo "**Checks:** $TOTAL_CHECKS_INVOKED invoked, $CHECKS_RAN ran, $COULD_NOT_RUN_COUNT could not"
# Satisfied pins are reported BY COUNT, not by listing them -- so a pin
# that silently stops being evaluated shows up as PINS_SATISFIED dropping
# below PINS_TOTAL (WI-0124 Wave 3 briefing), never as a shrunk total.
echo "**Pins:** $PINS_TOTAL checked, $PINS_SATISFIED satisfied"
echo "**Scope:** local paths only — nothing is fetched over a network (ADR-0010, decision 5)"
echo "**Run:** $NOW"
echo
echo "## Consumers"
echo
if [ "$CONFIGURED" -eq 0 ]; then
  echo "_none configured_"
else
  printf '%s' "$CONSUMER_REPORT"
fi
echo
echo "## Findings"
echo
# Six headings, always printed, always in this order (ADR-0010 decision
# 2's C1/C2/C3/P split, plus the could-not-run class WI-0124 Wave 2b adds
# and the Pins Not Evaluated class Wave 3 adds). Could-not-run and Pins
# Not Evaluated are each their OWN heading, not folded into C1/C3 or P:
# neither is a contract violation (the check behaved exactly as
# documented) nor a finding to attribute (there is no report, or no
# evaluable comparison, to attribute one from) — see
# _run_and_classify_check's own could-not-run comment, and the pin
# evaluation loop above, for the measurements that separate each from its
# neighbours. Pinned expectations (C3) sits after Could Not Run rather
# than beside C1/C2, the same "append the newest class just before P"
# placement Wave 2b already established for Could Not Run itself — every
# existing report-slice in this suite that reads "from one heading to the
# next" stays valid across each wave that adds one.
echo "### Contract violations (C1)"
echo
if [ "$C1_COUNT" -eq 0 ]; then
  echo "_none_"
else
  printf '%s' "$C1_FINDINGS"
fi
echo
echo "### Zero scope (C2)"
echo
if [ "$C2_COUNT" -eq 0 ]; then
  echo "_none_"
else
  printf '%s' "$C2_FINDINGS"
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
echo "### Pinned expectations (C3)"
echo
if [ "$C3_COUNT" -eq 0 ]; then
  echo "_none_"
else
  printf '%s' "$C3_FINDINGS"
fi
echo
echo "### Pins Not Evaluated"
echo
if [ "$PIN_NOT_EVALUATED_COUNT" -eq 0 ]; then
  echo "_none_"
else
  printf '%s' "$PIN_NOT_EVALUATED_FINDINGS"
fi
echo
echo "### Consumer findings (P)"
echo
if [ "$P_COUNT" -eq 0 ]; then
  echo "_none_"
else
  printf '%s' "$P_FINDINGS"
fi
echo
echo "---"
echo

# C1, C2 and C3 (a violated pin) are CCPR-attributable -- P never escalates
# the exit code (ADR-0010 decision 2/3: "P-class findings ... never
# escalate a run's exit code"). ATTRIBUTABLE is what the split proof in
# test group C pins: a run with only P findings must exit 0.
#
# COULD_NOT_RUN_COUNT and PIN_NOT_EVALUATED_COUNT are DELIBERATELY not
# folded into ATTRIBUTABLE either (WI-0124 Wave 2b / Wave 3): the check
# behaved exactly as documented -- an unsuitable target, refused, reason
# given on stderr -- so escalating the exit for that (or for a pin that
# consequently cannot be evaluated) punishes correct behaviour, not a
# defect. What must never happen instead is silence: the **Checks:** /
# **Pins:** accounting lines above and each class's own report heading
# make both impossible to miss even though neither fails the run alone.
ATTRIBUTABLE=$((C1_COUNT + C2_COUNT + C3_COUNT))
echo "**Summary:** $CONFIGURED configured, $COVERED covered, $ATTRIBUTABLE CCPR-attributable finding(s) (C1/C2/C3), $P_COUNT consumer finding(s) (P), $COULD_NOT_RUN_COUNT could-not-run"

if [ "$CONFIGURED" -eq 0 ]; then
  warn "$PROG: consumers NOT CONFIGURED — the conformance check DID NOT RUN. Set conformance.consumers in $CFG."
fi

if { [ "$REQUIRE_CONSUMERS" -eq 1 ] && [ "$CONFIGURED" -eq 0 ]; } || [ "$ATTRIBUTABLE" -gt 0 ]; then
  echo "**Exit:** 1"
  exit 1
fi

echo "**Exit:** 0"
exit 0
