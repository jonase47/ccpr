#!/usr/bin/env sh
# artifact-gate.ci.sh — DORMANT CI template. Nothing runs until you wire it up.
#
# CCPR's normal path for this check is local: run `scripts/artifact-gate.sh` from
# your working copy. This file is the optional second tier for teams that want the
# same check enforced on every push.
#
# It is deliberately a plain POSIX shell script and not a pipeline definition for
# any particular forge: CCPR's Constitution forbids making a hosted service a
# prerequisite ("No external services for distribution"), so the shipped artifact
# names no CI provider. Every CI system can invoke a shell script; wire this one
# in with whatever syntax yours uses.
#
# --- Activation ---------------------------------------------------------------
#   1. Copy this file into your repository, e.g. to ci/artifact-gate.sh, and
#      make it executable.
#   2. Add a job to your CI configuration whose only command is that script,
#      running from the repository root. A shallow checkout is fine -- the
#      sweep only reads `git ls-files`, not history -- but it does need a git
#      working tree: a source archive without a .git directory will not work.
#   3. Optional but recommended: expose the deny-list of tenant / project names
#      from your CI secret store as CCPR_GATE_DENY_NAMES (newline- or
#      comma-separated) and set REQUIRE_DENYLIST=1 below. Without it the run
#      still checks secrets, personal data and network literals, and it reports
#      that the deny-list was not configured -- it does not pass silently.
#      Never commit the names themselves: that would put them into exactly the
#      artifacts this check protects.
#
# Exit: 0 clean, 1 findings, 2 hard error. Findings are printed as
# `<path>:<line>: [<category>] <message>`; configured names are never echoed.

set -eu

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel)}"
GATE="$REPO_ROOT/scripts/artifact-gate.sh"

# Set to 1 once CCPR_GATE_DENY_NAMES is provided, so an unconfigured deny-list
# fails the job instead of only warning.
REQUIRE_DENYLIST="${REQUIRE_DENYLIST:-0}"

if [ ! -f "$GATE" ]; then
  echo "artifact-gate.ci: $GATE not found -- is CCPR installed in this repository?" >&2
  exit 2
fi

if [ "$REQUIRE_DENYLIST" = "1" ]; then
  exec bash "$GATE" --repo "$REPO_ROOT" --require-denylist
fi
exec bash "$GATE" --repo "$REPO_ROOT"
