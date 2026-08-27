#!/usr/bin/env bash
# conformance-run.sh — run this repository's shipped checks against real
# consumer projects, as part of this repository's own verification.
# Design: docs/adr/ADR-0010-conformance-runs-against-consumers.md.
#
# WAVE 2 (this file, as of WI-0124): the skeleton (Wave 1) plus the
# classifier — every covered, non-optional consumer now has the five shipped
# checks in CHECK_NAMES below actually run against it, and every finding is
# sorted into exactly one of C1 (contract violation), C2 (zero scope over a
# non-empty target), Could-Not-Run (Wave 2b — the check refused to run
# against this target and said so on stderr; not a defect, not folded into
# the exit code, but never allowed to look like a clean pass either — see
# the **Checks:** accounting line and _run_and_classify_check's own
# could-not-run comment) or P (a real finding in the consumer's own
# documents, never CCPR-attributable). Pins (Wave 3, class C3) are not read
# by this wave at all — see the module comment above CHECK_SCRIPT_DIR
# below. The report shape Wave 1 decided did not change underneath it: the
# same headings are still there, now populated instead of empty, plus the
# one Wave 2b adds.
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
#   1  at least one CCPR-attributable finding (C1 or C2 this wave; C3 joins
#      in Wave 3), OR --require-consumers was given and zero consumers are
#      configured.
#   2  the run could not be performed as asked: bad usage, a configured
#      consumer with no usable path, a non-optional consumer whose path does
#      not exist or is not readable, or a malformed conformance config.
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
# `pins` (ADR-0010 §5, class C3) are Wave 3. This wave reads only
# conformance.consumers[] (`id`, `path`, `optional`) and never looks at
# `pins` at all — not even to validate its shape — so a `pins` block, in
# whatever state a consumer's own config happens to carry it, can never make
# this wave's run fail.

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

# Finding accumulators — the same "growing string, one entry per line" shape
# CONSUMER_REPORT already uses below, for the same reason (a `set -u`-safe
# alternative to appending to a possibly-empty array whose emptiness is the
# common case).
C1_FINDINGS=""
C2_FINDINGS=""
P_FINDINGS=""
COULD_NOT_RUN_FINDINGS=""
C1_COUNT=0
C2_COUNT=0
P_COUNT=0
COULD_NOT_RUN_COUNT=0
# TOTAL_CHECKS_INVOKED — every call into _run_and_classify_check, whatever
# it classifies to (C1/C2/P/could-not-run/clean); the scope-accounting line
# below reports it alongside COULD_NOT_RUN_COUNT so "N checks ran" is never
# just asserted, it is CHECKS_RAN = TOTAL_CHECKS_INVOKED - COULD_NOT_RUN_COUNT.
TOTAL_CHECKS_INVOKED=0

# _run_and_classify_check <check-index> <consumer-id> <consumer-path> —
# invokes one check against one covered consumer and appends AT MOST ONE
# finding to exactly one of the three accumulators above (ADR-0010 decision
# 2: every finding is exactly one of C1/C2/C3/P; C3 is Wave 3 pins and is
# never read by this wave at all — this wave classifies only C1, C2 and P).
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
# configured consumer on stdout: "CONSUMER\t<id>\t<path>\t<0|1 optional>".
# An absent config file, an absent `conformance` key, an absent or empty
# `consumers` list all print NOTHING and exit 0 — that is the not-configured
# state, decided by the caller, not by this reader. Anything the reader
# cannot safely interpret (invalid JSON, `conformance`/`consumers` present
# but the wrong shape, a consumer entry missing a usable `id` or `path`)
# prints exactly one "ERROR\t<message>" record and exits 1 — the caller
# refuses to run rather than guess at a shortened or reinterpreted scope.
# `pins` is never read, valid shape or not (see the module header above).
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

conformance = cfg.get("conformance")
if conformance is None:
    sys.exit(0)
if not isinstance(conformance, dict):
    print("ERROR\t'conformance' is not an object")
    sys.exit(1)

consumers = conformance.get("consumers")
if consumers is None:
    sys.exit(0)
if not isinstance(consumers, list):
    print("ERROR\t'conformance.consumers' is not a list")
    sys.exit(1)

for position, c in enumerate(consumers, start=1):
    if not isinstance(c, dict):
        print("ERROR\tconsumers[%d] is not an object" % position)
        sys.exit(1)
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
while IFS=$'\t' read -r rec_type rec_id rec_path rec_optional; do
  [ "$rec_type" = "CONSUMER" ] || continue
  CONSUMER_IDS+=("$rec_id")
  CONSUMER_PATHS+=("$rec_path")
  CONSUMER_OPTIONAL+=("$rec_optional")
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
# Four headings, always printed, always in this order (ADR-0010 decision
# 2's C1/C2/C3/P split, plus the could-not-run class WI-0124 Wave 2b adds
# alongside it) -- C3 (pins) is Wave 3 and never populated by this wave, so
# it has no heading of its own yet; adding one here would claim a
# classification this wave cannot produce. Could-not-run is deliberately
# its own heading, not folded into C1 or P: it is neither a contract
# violation (the check behaved exactly as documented) nor a consumer
# finding (there is no report to attribute one from) — see
# _run_and_classify_check's own could-not-run comment for the measurement
# that separates it from both.
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

# Only C1 and C2 are CCPR-attributable this wave (C3 is Wave 3) -- P never
# escalates the exit code (ADR-0010 decision 2/3: "P-class findings ...
# never escalate a run's exit code"). ATTRIBUTABLE is what the split proof
# in test group C pins: a run with only P findings must exit 0.
#
# COULD_NOT_RUN_COUNT is DELIBERATELY not folded into ATTRIBUTABLE either
# (WI-0124 Wave 2b): the check behaved exactly as documented -- an
# unsuitable target, refused, reason given on stderr -- so escalating the
# exit for that is punishing correct behaviour, not catching a defect.
# What must never happen instead is silence: the **Checks:** accounting
# line above and this class's own report heading make a could-not-run
# impossible to miss even though it does not fail the run by itself.
ATTRIBUTABLE=$((C1_COUNT + C2_COUNT))
echo "**Summary:** $CONFIGURED configured, $COVERED covered, $ATTRIBUTABLE CCPR-attributable finding(s) (C1/C2), $P_COUNT consumer finding(s) (P), $COULD_NOT_RUN_COUNT could-not-run"

if [ "$CONFIGURED" -eq 0 ]; then
  warn "$PROG: consumers NOT CONFIGURED — the conformance check DID NOT RUN. Set conformance.consumers in $CFG."
fi

if { [ "$REQUIRE_CONSUMERS" -eq 1 ] && [ "$CONFIGURED" -eq 0 ]; } || [ "$ATTRIBUTABLE" -gt 0 ]; then
  echo "**Exit:** 1"
  exit 1
fi

echo "**Exit:** 0"
exit 0
