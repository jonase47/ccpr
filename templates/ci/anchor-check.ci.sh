#!/usr/bin/env sh
# anchor-check.ci.sh — DORMANT CI template. Nothing runs until you wire it up.
#
# CCPR's normal path for the anchored-state check is local: run `/anchor` (which wraps
# `scripts/anchor.sh check`) from your working copy and read Stage 2's judgment into the
# delta yourself. This file is the optional CI tier, and it can only ever run **Stage 1**
# of ADR-0009's two-stage design (docs/adr/ADR-0009-anchored-state-verification.md):
#
#   Stage 1 (mechanical, this script) -- anchor vs. the last production-code commit; lists
#     changed covered paths and paths claimed by no document. Produces DATA, no verdict.
#   Stage 2 (judgment, NOT this script) -- "does this delta invalidate a statement in these
#     documents?" That question needs a reader who can weigh the delta against what the
#     document actually claims -- a CI job cannot fell that judgment, only a human or an
#     agent reading the documents can. This template is NOT a replacement for `/anchor`;
#     it only ever surfaces Stage 1's report so a human goes and runs Stage 2.
#
# --- Why the exit code needs a decision, not a default -------------------------------
#
# `scripts/anchor.sh check` (and `status`) deliberately exit 0 whenever a report was
# produced -- WITH or WITHOUT drift. That is not an oversight: ADR-0009 is explicit that
# "staleness is never itself a verdict", so Stage 1 never renders one via its exit code. A
# non-zero exit from `anchor.sh` means only an OPERATIONAL failure (no git repo, no docs/
# structure, bad usage) -- never a content finding. A CI job that evaluates only the exit
# code of `anchor.sh check` would therefore NEVER report anything: drift is data, not a
# failure, by the script's own contract. This template evaluates the *text* of the report,
# not just the exit code, precisely so that omission does not happen silently.
#
# Given that, three shapes were considered for THIS wrapper's own exit code:
#
#   (a) Always exit 0, mirroring anchor.sh's contract exactly. Honest about Stage 1 never
#       being a verdict, but a CI job that can never fail is easy to stop reading --
#       exactly the "message nobody reads" failure ADR-0009 was written against.
#   (b) Exit non-zero whenever the delta is non-empty (an unclaimed or claimed changed
#       path exists). Rejected: that promotes Stage 1 DATA into a verdict, which is
#       exactly what ADR-0009 forbids -- it would make this template a silent, wrong
#       substitute for Stage 2, failing builds on the routine, expected case of code
#       moving under active documentation.
#   (c) [chosen] Exit 0 for a real report (drift or not) -- Stage 1 stays non-blocking, as
#       designed. Exit 2 for an operational failure (propagated from anchor.sh, unchanged
#       meaning). And ONE additional, opt-in signal: if the run shows that NO scope in the
#       project has ever been anchored at all (`0 anchored` in `anchor.sh status`'s own
#       summary line), that is reported loudly either way, and additionally turned into a
#       failing exit ONLY when REQUIRE_ANCHOR_COVERAGE=1 is set below. Zero-coverage is a
#       legitimate state for a fresh adoption (nothing to compare against yet), so it must
#       not fail by default -- but a project that has decided anchoring is mandatory can
#       opt in and get a real CI failure instead of a report nobody opens.
#
# This mirrors the same instrument this repository has already learned from: "a check run
# that reports no scope is not a pass" -- but here that principle can only ever gate on the
# COVERAGE question (was anything anchored at all), never on the CONTENT question (does the
# delta matter), because only a human or an agent can answer the content question.
#
# --- Activation ---------------------------------------------------------------
#   1. Copy this file into your repository, e.g. to ci/anchor-check.sh, and make it
#      executable. Unlike `artifact-gate.ci.sh` (which checks CCPR's own repo, where
#      `scripts/artifact-gate.sh` genuinely lives in the tree), this template runs
#      against USER projects, where CCPR normally lives under `~/.claude/` via
#      `install.sh`, not vendored into the checked-out repository. It therefore looks
#      for `scripts/anchor.sh` (and the `scripts/lib/frontmatter.sh` it sources) in three
#      places, first match wins:
#        a. $ANCHOR_SH, if set -- an explicit path, for CI setups that stage the script
#           somewhere else.
#        b. <repo-root>/scripts/anchor.sh -- vendored into this repository.
#        c. ${HOME}/.claude/scripts/anchor.sh -- a normal CCPR installation.
#      Make sure your CI job satisfies (b) or (c) -- e.g. run CCPR's `install.sh` as an
#      earlier step, or vendor `scripts/anchor.sh` (and `scripts/lib/frontmatter.sh`) into
#      this repository -- or set $ANCHOR_SH to point at whichever copy your job provides.
#   2. Add a job to your CI configuration whose only command is that script, running from
#      the repository root. It needs a real git working tree with history -- a shallow
#      clone still runs, but every anchor it cannot compare against is reported as
#      "cannot compare (shallow clone)" rather than resolved; fetch enough history
#      (`git fetch --unshallow`, or a depth that reaches your oldest live anchor) if you
#      want shallow clones to resolve.
#   3. Optional: set REQUIRE_ANCHOR_COVERAGE=1 in your CI job's environment once your
#      project has anchored its first scope, so a later project-wide de-anchoring (every
#      anchor removed, every index rewritten without one) fails the build instead of only
#      being visible in the log.
#
# This file names no forge and requires no hosted service -- CCPR's Constitution forbids
# making a hosted service a prerequisite for distribution ("No external services for
# distribution"). Every CI system can invoke a shell script; wire this one in with
# whatever syntax yours uses.
#
# Exit: 0 a report was produced (drift or not -- Stage 1 never fails on drift by design).
#       1 REQUIRE_ANCHOR_COVERAGE=1 and the project-wide report shows 0 anchored
#         documents -- opt-in only, see (c) above.
#       2 operational failure: scripts/anchor.sh not found in any of the three resolved
#         locations (see Activation above), or `anchor.sh check`/`status` itself exited
#         non-zero (bad usage, no git repo, no docs/ structure, or the report's own
#         "**Anchors:**" summary line could not be parsed at all).

set -eu

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel)}"

# Resolution order for scripts/anchor.sh, first match wins (see Activation above):
#   1. $ANCHOR_SH, if the caller set it explicitly.
#   2. <repo-root>/scripts/anchor.sh, if this repository vendors it.
#   3. ${HOME}/.claude/scripts/anchor.sh, a normal CCPR installation.
# ${HOME:-} guards against an unset $HOME under `set -u` (some minimal CI runners don't
# export it) -- an empty HOME simply means step 3 never matches, not a crash.
if [ -n "${ANCHOR_SH:-}" ]; then
  ANCHOR="$ANCHOR_SH"
elif [ -f "$REPO_ROOT/scripts/anchor.sh" ]; then
  ANCHOR="$REPO_ROOT/scripts/anchor.sh"
elif [ -n "${HOME:-}" ] && [ -f "${HOME}/.claude/scripts/anchor.sh" ]; then
  ANCHOR="${HOME}/.claude/scripts/anchor.sh"
else
  ANCHOR=""
fi

# Report DATA, never a verdict from THIS script's own reading either -- default off, see
# (c) above. Set to 1 once your project has anchored its first scope.
REQUIRE_ANCHOR_COVERAGE="${REQUIRE_ANCHOR_COVERAGE:-0}"

if [ -z "$ANCHOR" ] || [ ! -f "$ANCHOR" ]; then
  echo "anchor-check.ci: scripts/anchor.sh not found in any of: \$ANCHOR_SH (${ANCHOR_SH:-unset}), $REPO_ROOT/scripts/anchor.sh (vendored), \${HOME}/.claude/scripts/anchor.sh (installed) -- install CCPR in this CI job, vendor scripts/anchor.sh (and scripts/lib/frontmatter.sh) into this repository, or set ANCHOR_SH to the path of an existing copy." >&2
  exit 2
fi

# Both subcommands are Stage 1 and share the same never-fail-on-content contract (see
# header). `set +e` around them so a non-zero exit is inspected, not treated as this
# wrapper's own crash under `set -eu`.
set +e
CHECK_OUTPUT="$(bash "$ANCHOR" check "$REPO_ROOT" 2>&1)"
CHECK_STATUS=$?
STATUS_OUTPUT="$(bash "$ANCHOR" status "$REPO_ROOT" 2>&1)"
STATUS_STATUS=$?
set -e

echo "$CHECK_OUTPUT"
echo
echo "$STATUS_OUTPUT"
echo

if [ "$CHECK_STATUS" -ne 0 ] || [ "$STATUS_STATUS" -ne 0 ]; then
  echo "anchor-check.ci: scripts/anchor.sh exited non-zero (check=$CHECK_STATUS, status=$STATUS_STATUS) -- an OPERATIONAL failure, not a drift finding (Stage 1 never fails on drift, see header). Read the message above; common causes are a missing git repository or no docs/ structure." >&2
  exit 2
fi

# The acknowledgement / coverage statistic ("**Anchors:** N anchored · M asserted without
# doc change · K stale") lives only in `anchor.sh status`'s own summary line -- it is the
# single most reliable signal for "was anything anchored at all", so this reads that line
# rather than re-deriving coverage from `check`'s per-scope "not verified" text.
ANCHORED_COUNT="$(printf '%s\n' "$STATUS_OUTPUT" | sed -n 's/^\*\*Anchors:\*\* \([0-9][0-9]*\) anchored .*/\1/p')"

if [ -z "$ANCHORED_COUNT" ]; then
  echo "anchor-check.ci: could not read the '**Anchors:** N anchored ...' summary line from 'anchor.sh status' output -- treating this as an operational failure rather than guessing at coverage." >&2
  exit 2
fi

if [ "$ANCHORED_COUNT" -eq 0 ]; then
  echo "anchor-check.ci: 0 anchored -- no scope in this project has ever been anchored. This is not a code failure; Stage 1 has nothing to compare against yet. Run \`/anchor\` locally (scripts/anchor.sh set --scope <folder>) to establish the first anchor(s)." >&2
  if [ "$REQUIRE_ANCHOR_COVERAGE" = "1" ]; then
    echo "anchor-check.ci: REQUIRE_ANCHOR_COVERAGE=1 -- failing the build on zero coverage." >&2
    exit 1
  fi
  exit 0
fi

echo "anchor-check.ci: report produced ($ANCHORED_COUNT anchored). This job never fails on drift by design (Stage 1 renders no verdict) -- run \`/anchor\` locally to review the delta above and decide whether any document needs Stage 2 judgment or re-anchoring." >&2
exit 0
