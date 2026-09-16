#!/usr/bin/env bash
# awk_capability.sh — can the awk that will run this repo's CommonMark
# block-structure scanners actually compile the EREs they use?
#
# Source: bash ~/.claude/scripts/lib/awk_capability.sh   (for function calls from other scripts)
#
# WHY THIS EXISTS (CCP-1179)
#
# `mawk 1.3.4 20240123` — the default `/usr/bin/awk` on Debian-family
# systems — has a regex-compiler bug: an interval quantifier `{n,m}`
# followed later in the same ERE by a parenthesised group aborts the whole
# program with `REcompile() - panic: values still on machine stack`, exit
# 100. memory-lint.sh's fence/heading/list-marker detection and
# migrate-review-headers.sh's fence tracking both carried that shape.
#
# The abort is loud on the awk CHILD's stderr and invisible on both channels
# automation reads. memory-lint.sh runs its scanner in a process
# substitution, so the child's exit code is unobservable by construction;
# its own report said `**Summary:** 0 errors, 0 warnings, 0 info.` /
# `**Exit:** 0` — a check that parsed nothing reporting clean. That is
# KA-G-017's "a run that verified nothing is not a pass", one level below
# where the rule was written, and check-all.sh's exit-code comparison would
# have read it as a genuine pass.
#
# CCP-1179 rewrote the EREs into a form every awk compiles. This probe is the
# part that stays: the NEXT dialect surprise must produce a could-not-run
# outcome, not a false green.
#
# NOT A DEPENDENCY DECLARATION. CCPR runs on what the system ships — the same
# posture ADR-0011's bash-3.2 floor takes one tool over. Nothing here asks a
# contributor to install anything; `awkcap_could_not_run_reason` names gawk
# only as a way OUT of an already-broken run.

# The canary. One ERE, carrying the exact shape that fails: the interval
# quantifier `[ ]{0,3}`, then the parenthesised group `(a+|b+)`.
#
# Deliberately spelled with NOTHING from the real patterns in it — the
# scanners' own EREs no longer carry the shape (that is the fix), so a canary
# copied from one of them would stop reproducing the failure the moment the
# fix landed and this probe would silently start passing on every awk.
#
# The program PRINTS THE MATCH COUNT rather than merely exiting 0. An awk with
# no interval-quantifier support at all (the original one-true-awk; busybox
# built without them) compiles `[ ]{0,3}` as four literal characters, exits 0,
# and silently matches nothing — the quiet half of the same defect class, and
# not distinguishable from success by an exit code.
AWKCAP_CANARY_PROG='{ if (match($0, /^[ ]{0,3}(a+|b+)/)) hits++ } END { print hits+0 }'

# The one input line the canary is measured against: three leading spaces
# (inside `{0,3}`) followed by a run the group must match.
AWKCAP_CANARY_INPUT='   aaa'

# awkcap_identity [awk-binary] — "<resolved path> (<version line>)", or just
# the resolved path when the binary answers no version flag.
#
# Every failure mode here is swallowed on purpose: this function exists to
# make an ALREADY-failing run diagnosable, so it must never itself be the
# thing that aborts. An awk that answers `--version` with usage on stderr and
# exit 2 (the one-true-awk does) is exactly the kind of awk a reader needs
# named.
awkcap_identity() {
    local awk_bin="${1:-awk}"
    local resolved version
    resolved="$(command -v "$awk_bin" 2>/dev/null || true)"
    [ -n "$resolved" ] || resolved="$awk_bin (not found on PATH)"
    # `|| true` covers both a non-zero exit and the SIGPIPE `head` can raise;
    # 2>&1 keeps a usage-on-stderr answer readable instead of empty.
    #
    # No `# exit-status: exempt ...` marker, and not an oversight: every awk
    # call in this file goes through the `$awk_bin` PARAMETER (so the probe
    # can be pointed at a specific binary rather than only at whatever `awk`
    # resolves to), and test_external_tool_exit_status.py's scanner matches
    # tool NAMES literally — it does not see these invocations at all. Each
    # one is guarded on its own terms regardless; see awkcap_canary_ok below,
    # which reads the exit code, stderr and the result separately.
    version="$("$awk_bin" --version 2>&1 | head -n 1 || true)"
    case "$version" in
        ''|*usage*|*Usage*|*"not found"*) printf '%s' "$resolved" ;;
        *) printf '%s (%s)' "$resolved" "$version" ;;
    esac
}

# awkcap_canary_ok [awk-binary] — 0 when that awk compiles AND correctly
# applies the canary ERE, non-zero otherwise.
#
# Three things are required, not one: a zero exit (mawk's panic is 100),
# EMPTY stderr (an awk that warns about the construct but limps on has still
# told us it does not understand it), and the right match count (the silent
# no-intervals case above). stderr is captured to a file rather than folded
# into stdout so the two can be judged separately — and so a panic never
# reaches the caller's own stderr, where it would put the unexplained crash
# back on the channel the could-not-run message is supposed to own.
#
# LC_ALL=C mirrors the call sites: memory-lint.sh pins its scanner's locale
# (WI-0099), so the probe must ask the question under the same locale the
# answer will be used in.
awkcap_canary_ok() {
    local awk_bin="${1:-awk}"
    local stderr_file stdout_text stderr_text rc
    command -v "$awk_bin" >/dev/null 2>&1 || return 1
    stderr_file="$(mktemp)" || return 1
    rc=0
    stdout_text="$(printf '%s\n' "$AWKCAP_CANARY_INPUT" \
        | LC_ALL=C "$awk_bin" "$AWKCAP_CANARY_PROG" 2>"$stderr_file")" || rc=$?
    stderr_text="$(cat "$stderr_file")"
    rm -f "$stderr_file"
    [ "$rc" -eq 0 ] || return 1
    [ -z "$stderr_text" ] || return 1
    [ "$stdout_text" = "1" ] || return 1
    return 0
}

# awkcap_could_not_run_reason [awk-binary] — one line naming why a run must
# not proceed, or NOTHING (and exit 0) when that awk is fine.
#
# Single line by contract: both call sites interpolate it into one report line
# and one stderr warning, mirroring shellcheck-run.sh's own accumulated
# could-not-run reasons.
awkcap_could_not_run_reason() {
    local awk_bin="${1:-awk}"
    if awkcap_canary_ok "$awk_bin"; then
        return 0
    fi
    # Deliberately free of apostrophes and backticks: the format string is
    # single-quoted (an apostrophe would end it) and a backtick would have to
    # be double-quoted, where it becomes command substitution. Both dodges
    # cost more than writing the sentence without them.
    printf '%s cannot compile the CommonMark block-structure patterns in this repository: the canary ERE ^[ ]{0,3}(a+|b+) — an interval quantifier followed by a parenthesised group — did not compile and match (CCP-1179). Interim workaround, not a CCPR requirement: make a capable awk the awk on PATH (Debian-family: install gawk, then run update-alternatives --set awk /usr/bin/gawk).\n' \
        "$(awkcap_identity "$awk_bin")"
}
