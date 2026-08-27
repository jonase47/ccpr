#!/usr/bin/env bash
# conformance-run.sh — run this repository's shipped checks against real
# consumer projects, as part of this repository's own verification.
# Design: docs/adr/ADR-0010-conformance-runs-against-consumers.md.
#
# WAVE 1 (this file, as of WI-0124): the skeleton only. No shipped check is
# invoked yet and no C1/C2/C3/P classification happens — a resolved consumer
# is reported as COVERED with an empty findings section. The classifier
# (Wave 2) and pins (Wave 3) come later and build ON this skeleton, not
# beside it — the report shape decided here does not change underneath them.
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
#      (below) and, once Wave 2 lands, a run whose only findings are class P.
#   1  at least one CCPR-attributable finding (C1/C2/C3 — none possible yet
#      in this wave), OR --require-consumers was given and zero consumers
#      are configured.
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

NOW="$(date '+%d.%m.%Y %H:%M')"

echo "# Conformance Run Report"
echo
echo "**Consumers:** $CONFIGURED configured, $COVERED covered$NOT_RUN_SUFFIX"
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
echo "_none — Wave 1 skeleton, no check has run yet (ADR-0010, follow-up 1)_"
echo
echo "---"
echo
echo "**Summary:** $CONFIGURED configured, $COVERED covered, 0 findings"

if [ "$CONFIGURED" -eq 0 ]; then
  warn "$PROG: consumers NOT CONFIGURED — the conformance check DID NOT RUN. Set conformance.consumers in $CFG."
fi

if [ "$REQUIRE_CONSUMERS" -eq 1 ] && [ "$CONFIGURED" -eq 0 ]; then
  echo "**Exit:** 1"
  exit 1
fi

echo "**Exit:** 0"
exit 0
