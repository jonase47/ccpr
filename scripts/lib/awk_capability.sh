#!/usr/bin/env bash
# awk_capability.sh — can the awk that will run this repo's CommonMark
# block-structure scanners actually compile and apply the EREs they use?
#
# Source: bash ~/.claude/scripts/lib/awk_capability.sh   (for function calls from other scripts)
#
# WHY THIS EXISTS (CCP-1179)
#
# `mawk 1.3.4 20240123` — the default `/usr/bin/awk` on Debian-family
# systems — aborts its regex compiler on an interval quantifier `{n,m}`
# followed later in the same ERE by a parenthesised group:
#
#     REcompile() - panic:  values still on machine stack for ^[ ]{0,3}(a+|b+)
#
# exit 100. memory-lint.sh's fence/heading/list-marker detection and
# migrate-review-headers.sh's fence tracking both carried that shape.
#
# The abort was loud on the awk CHILD's stderr and invisible on both channels
# automation reads. memory-lint.sh runs its scanner in a process
# substitution, so the child's exit code is unobservable by construction; its
# own report said `**Summary:** 0 errors, 0 warnings, 0 info.` / `**Exit:**
# 0` — a check that parsed nothing reporting clean. That is KA-G-017's "a run
# that verified nothing is not a pass", one level below where the rule was
# written, and check-all.sh's exit-code comparison would have read it as a
# genuine pass.
#
# CCP-1179 rewrote those EREs into a form every awk compiles. This probe is
# the part that stays, and its question is deliberately NOT "does this awk
# have mawk's bug". A probe keyed to one known bug answers no for mawk
# forever, including after the patterns it choked on are gone — which is
# both wrong and exactly the kind of stale taboo that outlives its reason.
# The question asked here is the durable one:
#
#     can this awk compile and CORRECTLY APPLY the regex constructs this
#     repository's block-structure scanners are built out of?
#
# WHAT THE CANARY COVERS, AND WHAT IT DOES NOT
#
# Two EREs, each checked against a string that must match AND a string that
# must not — a compile that succeeds and then matches the wrong thing is the
# failure mode an exit code cannot see:
#
#   1. `^[ ]?[ ]?[ ]?(#+|=+)([ \t]|$)` — an optional-run indent prefix
#      followed by a parenthesised alternation. That is the shape of the
#      fence opener, the setext underline, the ATX heading and the list
#      marker after the CCP-1179 rewrite.
#   2. `"^[ ]?[ ]?[ ]?" run "[~]*[ \t]*$"` — a regex BUILT AT RUNTIME from a
#      string, with a repeated literal run followed by `[x]*`. That is the
#      fence CLOSER, whose delimiter and length are only known per fence.
#      Two separate things are checked here and neither is decoration: that
#      the awk applies a string-built regex at all, and that a run LONGER
#      than the opener still closes the fence. The second is what mawk
#      1.3.4 gets wrong when the same thing is written as `{n,}` — it
#      compiles silently and applies it as `{n}` — which is why the closer
#      no longer uses an interval quantifier and why the canary asserts the
#      longer run explicitly.
#
# No interval quantifier appears in either canary, and that is deliberate
# rather than an omission: after CCP-1179 no awk program in this repository
# uses one. Testing a construct the shipped code does not use would reject
# awks that could run it perfectly well — the same mistake as keying the
# probe to one vendor's bug.
#
# This is a SMOKE TEST over constructs, not a mirror of every shipped
# pattern: a future ERE built from a construct neither canary exercises
# would not be covered. Mechanical detection of that class is CCP-1129's
# line of work, not this file's.
#
# NOT A DEPENDENCY DECLARATION. CCPR runs on what the system ships — the same
# posture ADR-0011's bash-3.2 floor takes one tool over. Nothing here asks a
# contributor to install anything, and `awkcap_could_not_run_reason`
# deliberately does not either: see its own comment for why the remedy it
# names is a bug report rather than a package.

# The canary program. `# awkcap-canary` is a stable marker for test fixtures
# that need to recognise this specific program; nothing in the shipped path
# reads it.
#
# BEGIN-only, so it needs no input and cannot be affected by one. No
# apostrophe anywhere in it (the whole program is a single-quoted bash
# string) and no backtick (which is why the interval canary is spelled with
# `~` rather than with the backtick fence character).
AWKCAP_CANARY_PROG='
BEGIN {
    # awkcap-canary
    n = 0
    if (match("  ## x", /^[ ]?[ ]?[ ]?(#+|=+)([ \t]|$)/)) n++
    if (!match("x## x", /^[ ]?[ ]?[ ]?(#+|=+)([ \t]|$)/)) n++
    run = "~~~"
    if (match(" ~~~~~ ", "^[ ]?[ ]?[ ]?" run "[~]*[ \t]*$")) n++
    if (!match(" ~~ ", "^[ ]?[ ]?[ ]?" run "[~]*[ \t]*$")) n++
    print n
}'

# Four checks, so four is the only passing answer.
AWKCAP_CANARY_EXPECTED='4'

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
    # one is guarded on its own terms regardless; see awkcap_canary_answer
    # below, which reads the exit code, stderr and the result separately.
    #
    # `</dev/null` for the same reason the canary carries one: this library is
    # sourced into non-interactive runs, and an awk that waited on stdin here
    # would hang the caller — a worse failure than any it diagnoses. None of
    # the awks this ticket names reads stdin for `--version`; the redirect
    # costs nothing and removes the question.
    version="$("$awk_bin" --version </dev/null 2>&1 | head -n 1 || true)"
    case "$version" in
        ''|*usage*|*Usage*|*"not found"*) printf '%s' "$resolved" ;;
        *) printf '%s (%s)' "$resolved" "$version" ;;
    esac
}

# awkcap_canary_answer [awk-binary] — what that awk made of the canary, as
# one diagnosable token:
#
#   4                 every check passed
#   <n>               it ran, but got <n> of 4 right
#   exit <rc>         it aborted (mawk's panic is 100)
#   stderr: <text>    it complained, whatever its exit code said
#   not on PATH       there is no such binary
#
# stderr is captured to a file rather than folded into stdout so the two can
# be judged separately — and so a panic never reaches the CALLER's stderr,
# where it would put the unexplained crash back on the channel the
# could-not-run message is supposed to own.
#
# LC_ALL=C mirrors the call sites: memory-lint.sh pins its scanner's locale
# (WI-0099), so the probe must ask the question under the same locale the
# answer will be used in.
awkcap_canary_answer() {
    local awk_bin="${1:-awk}"
    local stderr_file stdout_text stderr_text rc
    if ! command -v "$awk_bin" >/dev/null 2>&1; then
        printf 'not on PATH'
        return 0
    fi
    # A failing mktemp is not an awk problem, and must not be dressed up as
    # one — the answer text is what the caller's message quotes verbatim.
    stderr_file="$(mktemp)" || { printf 'not probed: no usable temp file'; return 0; }
    # CCP-1216: mktemp can also SUCCEED and hand back a path it cannot
    # itself write into (permissions race, an immutable flag set between
    # creation and here). Left unguarded, the `2>"$stderr_file"` redirect
    # below is the thing that then fails — the awk program never runs, and
    # the failure used to fall through to `exit <rc>`, reported downstream
    # as an awk-dialect gap. That is the same "not an awk problem" category
    # as the failing-mktemp case just above, not a different one, so it
    # gets the same "not probed" answer rather than a verdict about awk.
    # `-w` (access(2), W_OK) is what actually observes the immutable flag
    # on this file's target platforms, not the mode bits alone.
    if [ ! -w "$stderr_file" ]; then
        rm -f "$stderr_file" 2>/dev/null || true
        printf 'not probed: temp file not writable'
        return 0
    fi
    rc=0
    stdout_text="$(LC_ALL=C "$awk_bin" "$AWKCAP_CANARY_PROG" </dev/null 2>"$stderr_file")" || rc=$?
    # Guarded the same way as $rc above and the cleanup below: a stderr file
    # that has become unreadable between the write and this read (permissions
    # race, another process removing it) is not the awk-dialect question this
    # function exists to answer either, and must not be what aborts the
    # caller under set -e. An empty stderr_text on that path just means the
    # answer below falls through to reporting stdout_text instead.
    stderr_text="$(cat "$stderr_file" 2>/dev/null)" || stderr_text=""
    # `|| true` for the same reason migrate-review-headers.sh's own temp-file
    # cleanup carries one: this library is SOURCED into scripts running under
    # `set -euo pipefail`, and a temp file that is itself unremovable
    # (permissions race, immutable flag) would abort the caller here — turning
    # a diagnosable dialect gap into an unexplained crash, which is precisely
    # what this file exists to prevent.
    rm -f "$stderr_file" 2>/dev/null || true
    if [ "$rc" -ne 0 ]; then
        printf 'exit %s' "$rc"
    elif [ -n "$stderr_text" ]; then
        # Trimmed to one line: this ends up inside a single report line.
        printf 'stderr: %s' "$(printf '%s' "$stderr_text" | head -n 1)"
    else
        printf '%s' "$stdout_text"
    fi
}

# awkcap_canary_ok [awk-binary] — 0 when that awk answers the canary
# correctly, non-zero otherwise.
awkcap_canary_ok() {
    [ "$(awkcap_canary_answer "${1:-awk}")" = "$AWKCAP_CANARY_EXPECTED" ]
}

# awkcap_could_not_run_reason [awk-binary] — one line naming why a run must
# not proceed, or NOTHING (and exit 0) when that awk is fine.
#
# Single line by contract: both call sites interpolate it into one report line
# and one stderr warning, mirroring shellcheck-run.sh's own could-not-run
# reasons.
awkcap_could_not_run_reason() {
    local awk_bin="${1:-awk}" answer
    answer="$(awkcap_canary_answer "$awk_bin")"
    if [ "$answer" = "$AWKCAP_CANARY_EXPECTED" ]; then
        return 0
    fi
    # THE REMEDY IS A BUG REPORT, NOT A PACKAGE (PO decision, 16.09.2026).
    # This used to end in "install gawk, then run update-alternatives --set
    # awk /usr/bin/gawk". After the CCP-1179 rewrites, no awk program this
    # repository ships uses a construct any known awk chokes on — so the only
    # way to arrive here is an awk dialect CCPR has never seen, and that is a
    # gap in CCPR, not a misconfigured machine. Sending the operator to
    # reconfigure their system-wide awk answered it at the wrong layer twice
    # over: it changes a machine to work around a repository defect, and it
    # guarantees the repository never learns the dialect exists. The clause
    # about another awk on PATH stays because someone mid-run needs a way
    # forward, but it is a passing note without a recipe — no invocation, no
    # package named as the fix.
    #
    # Deliberately free of apostrophes and backticks: the format string is
    # single-quoted (an apostrophe would end it) and a backtick would have to
    # be double-quoted, where it becomes command substitution. Both dodges
    # cost more than writing the sentence without them.
    printf '%s cannot compile and correctly apply the CommonMark block-structure patterns in this repository: the capability canary answered %s where %s of 4 checks must pass. No awk program CCPR ships uses a construct known to fail, so this is a gap in CCPR rather than a misconfiguration on this machine: please report this line as a CCPR issue, referencing CCP-1179 for the context. A different awk on PATH may get past it in the meantime.\n' \
        "$(awkcap_identity "$awk_bin")" "[$answer]" "$AWKCAP_CANARY_EXPECTED"
}
