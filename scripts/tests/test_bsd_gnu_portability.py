r"""test_bsd_gnu_portability.py -- WI-0130: a shipped shell script reaches for
a coreutils construct whose BSD and GNU forms differ, and the difference is
invisible on the platform the script was written on.

## The class, measured three times in one week

1. `mktemp` with a suffix after the `XXXXXX` run (`scripts/run-tests.sh:53`
   and `:186`, pre-fix). BSD `mktemp` substitutes only a TRAILING run of X's
   and otherwise returns the template VERBATIM -- so
   `mktemp /tmp/pytest-report-XXXXXX.json` creates the literal, predictable,
   non-unique path `/tmp/pytest-report-XXXXXX.json` and exits 0. GNU
   substitutes. Silent on BSD. Fixed in `bc87c9f`.
2. `find ... -printf` (`scripts/log-cleanup.sh:69`, pre-fix). GNU-only. On
   BSD it fails outright and the `||` fallback behind it covers for it; on
   GNU it SUCCEEDS -- and there matched every file in the directory rather
   than the intended `*.jsonl` subset, so a session whose summary file had
   just been rewritten looked fresh. Silent on GNU. Fixed in `269d490`.
3. `stat -f` (`scripts/log-cleanup.sh:70` and `:74`, pre-fix). On BSD `-f` is
   the FORMAT string; on GNU `-f` is `--file-system`, an entirely different
   mode that reads the format argument as a second file operand. It does not
   fail in any way the surrounding pipeline notices -- it emits a multi-line
   filesystem block that `sort -rn | head -1` happily reduces to a number.
   Silent on GNU, and the most dangerous of the three: an error wearing the
   shape of a result. Fixed in `269d490`.

## Why a scanner and not three fixes

ShellCheck ran clean at `--severity=warning` over all 22 files in
`scripts/shellcheck-run.sh`'s scope on 30.08.2026 WHILE instances 2 and 3
were live in `log-cleanup.sh`. The eighth check in `check-all.sh`'s catalogue
demonstrably does not cover this class, so it needs its own instrument.

And the correct pattern already exists in this repository TWICE --
`scripts/instinct-check.sh:52-59` (`mtime_of()`) and
`scripts/bootstrap.sh:191-198`, both branching on `uname` between `stat -f %m`
and `stat -c %Y`. `log-cleanup.sh` was the lone outlier. A pattern applied by
hand in two places and forgotten in a third is the shape a check holds and a
fix does not.

## Where it lives (PO decision 30.08.2026, docs/workitems/WI-0130.md)

A stdlib-only unittest module beside the three static scanners this repo
already runs that way (`test_shell_script_syntax.py`,
`test_heredoc_interpolation_scan.py`, `test_absence_only_assertions.py`), NOT
a ninth catalogue entry in `check-all.sh`: it needs no external binary, so it
has no could-not-run state to model and cannot be silenced by a missing tool,
and it runs in BOTH CI jobs today with no new wiring. Folding it into
`shellcheck-run.sh` was rejected explicitly -- that would couple a stdlib scan
to an externally installed tool, so a machine without ShellCheck would skip
the portability scan entirely, which is the very shape of gap this scanner
exists to find.

## Scope: every shipped `.sh` in the tree, 29 files

`install.sh`, `scripts/*.sh`, `scripts/lib/*.sh`, `scripts/local-llm/*.sh`,
`templates/ci/*.sh`. That is WIDER than `scripts/shellcheck-run.sh`'s 22-file
scope, deliberately, because neither of that script's two exclusion reasons
transfers to THIS error class:

  * `templates/ci/*.sh` is excluded from ShellCheck because it is
    `#!/usr/bin/env sh`, not bash, so ShellCheck's bash-specific checks do not
    apply. A BSD/GNU coreutils divergence is a property of the EXTERNAL BINARY
    a script calls, not of the interpreter that calls it -- `stat -f` means
    two different things under `sh` exactly as much as under `bash`. And these
    two templates carry the class's highest-risk profile in the whole
    repository: authored on macOS, executed on a Linux CI runner.
  * `scripts/local-llm/*.sh` is excluded from ShellCheck (and from
    `test_shell_script_syntax.py`) because `install.sh` marks it user-owned
    and PROTECTED, never overwritten on `--update`. That argument is about the
    INSTALLED copy under `~/.claude`. This scan reads the repository's own
    tracked source, which CCPR authors and ships; a user's local edits never
    reach it. If anything, PROTECTED makes an initial defect worse rather than
    exempt, since no update ever repairs it. `test_heredoc_interpolation_scan.py`
    already includes local-llm for the same reason.

Measured 30.08.2026: both added groups carry ZERO occurrences of any adopted
construct, so the wider scope costs nothing today and is purely prospective.
That is stated rather than assumed -- a scope choice whose effect is unmeasured
is not a decision.

`hooks/` is out of scope by construction: it holds one Python file, which
invokes `bash scripts/log-cleanup.sh` as a subprocess and contains no inline
shell of its own. `templates/ci/*.sh` aside, no `.sh` file in this repository
sits outside the five globs above (verified with `find . -name '*.sh'`).

## Adopted constructs, and on which side each one is SILENT

The "silent side" is the load-bearing column: a construct that FAILS on the
wrong platform announces itself and can be covered by a fallback; one that
SUCCEEDS with different semantics cannot. Every rule below names it.

  * `find ... -printf`      GNU-only. Loud on BSD (unknown primary, exit 1).
                            SILENT ON GNU: it runs, and its output set is
                            whatever the surrounding predicates left, which in
                            instance 2 was every file rather than `*.jsonl`.
  * `stat -f`               BSD: format string. GNU: `--file-system`, reading
                            the format as a second file operand.
                            SILENT ON GNU (see instance 3).
  * `stat -c`               GNU: format string. BSD `stat` has no `-c` at all.
                            Loud on BSD (usage error, exit 1).
  * `sed -i`                BSD requires the backup suffix as a SEPARATE
                            operand (`sed -i '' -e ...`); GNU requires it
                            ATTACHED (`sed -i.bak`), and reads a separate
                            argument as the script. No single spelling works on
                            both. SILENT ON BSD for the GNU spelling
                            `sed -i -e 's/x/y/' f`: BSD consumes `-e` as the
                            backup suffix, edits the file, and leaves a stray
                            `f-e` behind. This repository already forbids the
                            construct outright -- ADR-0009 Addendum 1 A8, cited
                            at `scripts/lib/frontmatter.sh:287`.
  * `readlink -f`           GNU, and macOS only since 12.3. Loud on older BSD
                            (illegal option, exit 1).
  * `date -d`               GNU: parse a date string. BSD `-d` sets the
                            kernel's daylight-saving flag and takes its own
                            argument -- a different option that happens to
                            share a letter, exactly `stat -f`'s trap shape.
                            Loud on BSD in practice (the value does not parse
                            as a DST spec), but the shape is the same.
  * `date -v`               BSD: adjust the date. GNU has no `-v`.
                            Loud on GNU.
  * `date -j`               BSD: do not set the clock. GNU has no `-j`.
                            Loud on GNU.
  * `date -r`               BSD: `-r` takes EITHER epoch seconds OR a file.
                            GNU: `-r` takes a file only. SILENT ON GNU for a
                            file argument (both work), loud on GNU for an
                            epoch argument -- so a call written and tested on
                            macOS with a numeric argument breaks on Linux and
                            the same call with a file argument does not. A
                            divergence whose visibility depends on the
                            argument is worth flagging on sight.
  * `grep -P`               GNU/PCRE only. Loud on BSD.
  * `mktemp` template with  BSD substitutes only a trailing X-run and returns
    a suffix after the      the template verbatim otherwise.
    final `XXX...` run      SILENT ON BSD (see instance 1).

## Candidates evaluated and REJECTED, with the reason

A list that names only its hits hides its own shape, so:

  * `xargs -r` -- rejected because the divergence sits in the ABSENCE of the
    flag, not its presence: BSD `xargs` never runs the command on empty input,
    GNU runs it once unless `-r` is given (and macOS `xargs` accepts `-r` as an
    ignored compatibility no-op). A rule matching `-r` would flag the
    COMPATIBLE spelling and miss the incompatible one -- backwards.
  * `sort -V` -- rejected because I cannot state a divergence that holds for
    the two platforms actually in play: the BSD `sort` macOS ships accepts
    `-V`. A candidate whose divergence cannot be named does not belong in a
    list whose docstring must name it.
  * `head`/`tail` "GNU-only flags" -- rejected as stated: every short flag in
    use across this corpus (`-n`, `-c`, `-1`) is POSIX on both. Only the
    `--long` spellings diverge, which folds into the entry below.
  * `cp --parents`, `ls --color`, `base64 -w`, and GNU long options on
    coreutils generally -- rejected on RULE PRECISION, not on absence of
    instances (several adopted rules above also have zero live instances). A
    "coreutils binary followed by `--long`" rule needs a binary allowlist to
    keep `git --porcelain`, `curl --max-time` and `pytest --json-report` out,
    and it would be wrong on the binaries where BSD DOES accept long options
    (FreeBSD/macOS `grep` takes `--include`, `--exclude`, `--color`). Measured
    30.08.2026: every `--long` option in all 29 shipped scripts belongs to
    `git`, `curl`, `pytest`, `jest`, `cargo`, or a CCPR script's own CLI; the
    single coreutils long option anywhere in the tree is `chmod --reference`,
    named inside a comment at `scripts/lib/frontmatter.sh:252` as the GNU-only
    thing that was deliberately NOT used. Left for its own work item if an
    instance ever appears.
  * `mktemp -t` -- rejected. BSD reads the argument as a PREFIX and appends
    its own random suffix; GNU reads it as a template under `$TMPDIR`. Both
    succeed, both yield a usable unique path, and no caller in this corpus
    inspects the resulting NAME. Flagging it would spend the scanner's
    credibility on a difference with no consequence.
  * `echo -e` -- rejected as a different class: a shell BUILTIN divergence
    (bash vs. dash vs. `xpg_echo`), not a BSD/GNU userland one. Its fix
    (`printf`) belongs to a rule with a different owner. Zero occurrences.
  * `realpath` -- rejected as a different class again: a question of whether
    the BINARY EXISTS, not of a flag meaning two things.
    `scripts/manual-lint.sh:77-78` already documents avoiding it.

## How a flag is attached to its command

A rule is a COMMAND pattern plus a FLAG pattern, paired by PAREN DEPTH with a
command-boundary scan at that depth -- not by a character class spanning the
text between them. The difference is not cosmetic. A gap expressed as
"any run of characters that is not `|`, `;`, `&` or `)`" stops at the `)`
closing a nested, unrelated `$(...)` used as an EARLIER argument of the very
command being scanned, so `stat $(dirname "$f") -f %m` and
`find "$(dirname "$0")/logs" -printf '%f\n'` both went unreported -- the
latter a reordered variant of this module's own founding defect.
`FlagPairsWithItsOwnCommandAcrossASubstitutionTest` pins the fix together with
its two discriminators: a flag INSIDE a substitution never pairs with the
outer command (depth equality, not "somewhere to the right"), and a pipe
still separates a command from a later flag (`sed ... | tee -i` is not a
`sed -i`).

## The exemption rule, and why a `||` fallback chain is NOT one

A match is a finding UNLESS one of exactly two things is in sight:

  1. a `uname` occurrence -- the pattern `instinct-check.sh` and
     `bootstrap.sh` already use; or
  2. an explicit marker comment `# portability: exempt <reason>` in the
     construct's marker sight, mirroring the `# exit-status: exempt <reason>`
     idiom this repository already carries in `instinct-check.sh`,
     `memory-sync.sh`, `shellcheck-run.sh` and others. Three things make that
     marker a recorded decision rather than a skip list (R3):

       * The `<reason>` token is MANDATORY. A bare `# portability: exempt`
         names nothing, can be neither reviewed nor seen to go stale, and
         does NOT exempt -- `MarkerWithoutAReasonDoesNotExemptTest`.
       * The sight is the LOGICAL line -- every physical line a backslash
         splices into one command -- plus the one line above it. Not
         `(idx, idx-1)`: a `\`-continued statement cannot carry a comment on
         a middle line without the splice eating the rest of the command, so
         the only legal position on a multi-line `||` chain is the line the
         statement FINISHES on, which sits BELOW the construct. That is
         `scripts/lib/frontmatter.sh:259-261` exactly, and it is the same
         range `test_external_tool_exit_status.py`'s `find_exemption` searches
         for the same reason. Bounded by the statement, not by a distance:
         `MarkerCoversTheWholeContinuedStatementTest` pins four negatives --
         two lines above, the line after, an even backslash run, and a
         backslash followed by whitespace.
       * The set of exempted sites and the set of reasons are both pinned.
         `EXEMPTED_SITES` is set equality on `(path, line, rule, category)`,
         so a site cannot appear, disappear or SWAP categories quietly; every
         category must resolve to a written reason in `EXEMPTION_CATEGORIES`
         and every registered reason must still be carried by some site; and
         `NoStaleMarkerTest` reports a marker that excuses nothing -- the
         accounting direction `NoStaleKnownFindingsTest` enforces for
         `test_absence_only_assertions.py`'s registry.

A `||` fallback chain is deliberately NOT an exemption, and that is a
measured decision rather than a stylistic one. `git show 269d490^:scripts/
log-cleanup.sh` lines 69-70 are precisely such a chain --
`find ... -printf ... || stat -f '%m' ... || echo "0"` -- and they were the
genuine defect this work item exists for. A `||` chain only guards a construct
that FAILS on the wrong platform; half this list's entries do not fail, and in
that historical line the chain additionally sat behind a pipe, so the
pipeline's exit status belonged to `head` and the fallback could never fire at
all. Accepting `||` as a guard would make the scanner green against its own
founding defect, which is the definition of a check that cannot fail.

## "In sight": the enclosing function body, or ten lines at top level

A `uname` branch guards a construct by DOMINATING it in control flow. The
nearest boundary this repository's own two correct instances both respect is
the shell function body:
`instinct-check.sh`'s `mtime_of()` puts the `uname` one line above `stat -f`
and three above `stat -c`; `bootstrap.sh`'s decay block puts it two and seven
lines above the same pair. So: if the construct sits inside a function, "in
sight" is that function's body and nothing else.

Deliberately NOT the whole file. `scripts/log-cleanup.sh` today defines
`mtime_of()` with a correct `uname` branch at line 20 and separately calls
`date -v`/`date -d` in top-level code at line 69; a file-scoped rule would let
that one unrelated `uname` exempt every construct in the script. That is the
same drift `test_heredoc_interpolation_scan.py`'s `KNOWN_FINDINGS` registry
was introduced to prevent -- an exemption nobody re-verifies.

For a construct at top level (outside any function) the window is the ten
physical lines preceding it plus its own, MINUS every line that belongs to
some function body. Ten is measured headroom over the 1-, 2-, 3- and 7-line
spans of the three correct instances in this tree, without reaching across a
whole script. A `uname` more than ten lines above an unguarded construct is a
coincidence, not a guard.

The subtraction matters as much as the window. A function's body only runs
where it is CALLED, so a `uname` branch inside a helper defined just above a
top-level statement does not dominate that statement. Without the filter,
`mtime_of() { if [[ "$(uname)" ... ]]; ... }` followed a few lines later by a
bare top-level `stat -f` would exempt it -- which is `scripts/log-cleanup.sh`'s
exact layout. `OneLineFunctionDetectionUsesBraceBalanceTest` pins both halves,
and `NestedFunctionUsesTheInnermostRangeTest` pins that an outer function's
`uname` does not reach a function nested inside it.

`UnameInAnotherFunctionDoesNotExemptTest` pins the function-scope half against
the file-scope alternative directly, and
`RemovingTheUnameBranchTurnsAShippedSiteIntoAFindingTest` mutates the SHIPPED
`instinct-check.sh` -- keeping the `if`/`else` shape and removing only the
`uname` call -- so an exemption that stops being verified stops being granted.

## What this scan cannot see

  * A construct assembled inside a variable and run through `eval` or `$cmd`.
    The flag rules run over text with quoted content blanked, so
    `cmd="stat -f %m"; $cmd` is invisible. Measured zero such shapes on
    30.08.2026; named rather than silently accepted.
  * A construct inside a heredoc BODY -- a script that writes a script.
    Heredoc bodies are blanked before masking (the same `_blank_heredocs`
    treatment `test_external_tool_exit_status.py` applies for its own,
    unrelated purpose) because an unbalanced quote inside a body would
    otherwise corrupt the quote state for the rest of the file. Measured zero
    candidate constructs inside any heredoc body in the 29 scanned files.
  * A flag written as a COMBINED short cluster -- `stat -Lf %m` rather than
    `stat -L -f %m`. Every rule matches a flag as its own whitespace-preceded
    token. Measured zero clusters in the 29 files; naming it because it is
    the nearest remaining hole in the flag grammar.
  * The GNU LONG spelling of an adopted construct -- `stat --format=%Y`,
    `date --date=...`, `sed --in-place`. Out of scope by the same decision
    that rejected the long-option rule above (see "Candidates evaluated and
    REJECTED"), stated here too because it is a near-miss for the ADOPTED
    rules and not only for the rejected ones. Measured zero occurrences.
  * A marker inside a QUOTED STRING. Markers are searched in heredoc-blanked
    text with comments intact (they have to be -- a marker IS a comment), and
    that view keeps quoted content, so `echo "# portability: exempt x"` would
    be honoured as a decision. Blanking quotes while keeping comments needs a
    fourth mask and the same quote-tracking `_mask_non_live` already does;
    named rather than built because the corpus has none. Measured 31.08.2026:
    5 marker occurrences in the 29 files, all 5 real comments.
    `test_external_tool_exit_status.py`'s `find_exemption` has the identical
    shape and the same exposure.
  * A backslash ending an UNTERMINATED quoted string (`x='a \` continuing on
    the next line) counts as a splice, because the splice view keeps quoted
    content too. Unreachable in practice rather than merely unobserved: the
    next line is then INSIDE that string, so `_mask_non_live` blanks it and
    no construct can be found there to be exempted. Measured 31.08.2026:
    44 continuation backslashes in the 29 files, 0 of them inside a string,
    a comment or a heredoc body (sentinel probe -- the backslash replaced by
    a marker character, the file re-masked, the character checked for
    survival).
  * Whether a flagged site is actually BROKEN. A finding is a SHAPE. Both
    `frontmatter.sh` sites in `KNOWN_FINDINGS` below happen to work today, for
    a reason the scanner cannot check -- see that registry's own note.

## Findings on the current tree: marked, still not fixed (R3)

WI-0130 surfaced nine and repaired none -- its write boundary was this file.
R3 did not repair them either: every repair is a code change and needs its own
red proof and its own round. What R3 added is the REASON, written at the site,
so the next reader does not inherit a `||` chain as an intention.

The nine are not equivalent, and the two categories say which is which:

  * Seven `date` sites are genuine portable idioms. The two forms reject each
    other's flags outright, so the wrong platform's form fails by exit status
    -- the thing the `||` actually reads. Measured 31.08.2026 on one machine
    carrying both implementations, each form under each: `-v` and `-j` are
    `invalid option` on GNU, `-d` is `illegal option` on BSD, all exit 1 with
    empty stdout.
  * The two `stat` sites are NOT. `stat -f` is a VALID GNU option
    (`--file-system`), so GNU does not reject the flag; the chain falls
    through only because GNU reads `%Lp` as a second file operand that does
    not resolve. Put a file named `%Lp` in the working directory and the same
    call exits 0 (measured) with a filesystem block in `mode`, the `||` never
    fires, and the file keeps mktemp's 0600. That site's marker says so in
    its category name.

`KNOWN_FINDINGS` is consequently empty and `EXEMPTED_SITES` holds the nine.
Both are set equalities, and `NoStaleMarkerTest` closes the third direction:
a marker whose construct was repaired or moved is itself reported.
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# The two historical pre-fix states used as red fixtures. Both name the FIX
# commit and are read via `{sha}^`, the same convention
# test_agent_frontmatter.py's PRE_FIX_COMMIT uses (test_command_check.py's
# TEMPLATE_PRE_FIX_COMMIT names the pre-fix state directly instead -- check
# which one a file uses before copying the pattern into a third). Both were
# resolved with `git rev-parse --verify <sha>^{commit}` before being pinned
# here, and _read_git_show re-verifies at run time so a shallow clone ERRORS
# loudly instead of quietly skipping.
LOG_CLEANUP_FIX_COMMIT = "269d490"
RUN_TESTS_FIX_COMMIT = "bc87c9f"

# See the module docstring's '"In sight"' section for both halves.
TOP_LEVEL_WINDOW = 10

# The marker grammar. A REASON TOKEN is mandatory: `# portability: exempt`
# on its own records no decision, cannot be reviewed and cannot be seen to go
# stale -- exactly the unread skip list this module exists to avoid. Same
# shape as `test_external_tool_exit_status.py`'s `MARKER_RE`, which has
# required a `<category>` since it was written. Membership of the token in
# EXEMPTION_CATEGORIES is checked separately, over the shipped tree only, so
# fixtures in this file are not forced to invent shipped categories.
EXEMPTION_MARKER_RE = re.compile(r"#\s*portability:\s*exempt\s+([A-Za-z0-9_-]+)")

HEREDOC_OPEN_RE = re.compile(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

# A function opener: optional `function`, a name, `()`, and an opening brace on
# the same line. Measured 30.08.2026 across the 29 scanned files: 174 shell
# function definitions, every one with the brace on the opener line. A further
# 12 opener-SHAPED lines carry no brace and are correctly not matched -- all of
# them `flush_paragraph()` CALLS inside memory-lint.sh's embedded awk programs,
# which are additionally single-quoted and therefore already blanked by the
# masker before this regex ever sees them.
FUNC_OPEN_RE = re.compile(
    r"^([ \t]*)(?:function[ \t]+)?[A-Za-z_][A-Za-z0-9_]*[ \t]*\([ \t]*\)[ \t]*\{"
)

# A command name in command position: not preceded by `-` (so `--date=short`
# is not a `date` call), by a word character (so `last-modified-date` is not),
# or by `/` or `.` (so `./date` and `foo.date` are not).
_CMD = r"(?<![-\w./])"

# A flag token: preceded by whitespace, and not the prefix of a longer word.
# `-i.bak` and `-v-7d` are deliberately still matches -- both are real
# spellings of the diverging flag -- so the trailing guard excludes word
# characters and, where the flag never takes an attached value, a dot.
def _flag(letters, allow_attached=False):
    tail = "" if allow_attached else (r"(?![\w.])" if len(letters) == 1 else r"\b")
    return re.compile(r"(?<=\s)-" + letters + tail)


# Command boundaries. A flag past one of these, AT THE SAME PAREN DEPTH,
# belongs to a different command.
BOUNDARY_CHARS = "|;&"


def _paren_depths(masked_line):
    """Paren depth at every index of a masked line. Depth is what tells a
    command's own arguments apart from a nested `$(...)`, which is why this
    replaced the earlier character-class gap: that gap stopped at ANY `)`,
    including the one closing an unrelated substitution used as an EARLIER
    argument of the very command being scanned. `stat $(dirname "$f") -f %m`
    and `find "$(dirname "$0")/logs" -printf` both went unreported -- the
    latter a reordered variant of this module's own founding defect."""
    depths = []
    d = 0
    for ch in masked_line:
        if ch == "(":
            depths.append(d)
            d += 1
        elif ch == ")":
            d = max(0, d - 1)
            depths.append(d)
        else:
            depths.append(d)
    depths.append(d)
    return depths


def _command_owns_flag(masked_line, cmd_re, flag_re):
    """True when some `cmd_re` match on the line owns some `flag_re` match:
    same paren depth, with no command boundary at that depth between them."""
    depths = _paren_depths(masked_line)
    for cm in cmd_re.finditer(masked_line):
        depth = depths[cm.start()]
        limit = len(masked_line)
        for k in range(cm.end(), len(masked_line)):
            if masked_line[k] in BOUNDARY_CHARS and depths[k] == depth:
                limit = k
                break
        for fm in flag_re.finditer(masked_line, cm.end(), limit):
            if depths[fm.start()] == depth:
                return True
    return False


class PortabilityRule:
    """One BSD/GNU divergence. `silent_on` records the platform where the
    wrong form SUCCEEDS rather than failing -- the column that decides whether
    a `||` fallback could ever have covered for it. See the module docstring's
    adopted-constructs table for each entry's full account."""

    __slots__ = ("name", "cmd_re", "flag_re", "silent_on", "divergence")

    def __init__(self, name, command, flag_re, silent_on, divergence):
        self.name = name
        self.cmd_re = re.compile(_CMD + command + r"\b")
        self.flag_re = flag_re
        self.silent_on = silent_on
        self.divergence = divergence

    def matches(self, masked_line):
        return _command_owns_flag(masked_line, self.cmd_re, self.flag_re)


FLAG_RULES = [
    PortabilityRule(
        "find-printf", "find", _flag("printf"), "GNU",
        "GNU-only primary; on GNU it runs and its match set is whatever the "
        "other predicates left",
    ),
    PortabilityRule(
        "stat-f", "stat", _flag("f"), "GNU",
        "BSD: format string. GNU: --file-system, reading the format as a "
        "second file operand",
    ),
    PortabilityRule(
        "stat-c", "stat", _flag("c"), None,
        "GNU: format string. BSD stat has no -c",
    ),
    PortabilityRule(
        "sed-i", "sed", _flag(r"i(?![\w])", allow_attached=True), "BSD",
        "BSD takes the backup suffix as a separate operand, GNU attached; the "
        "GNU spelling makes BSD eat the next argument as the suffix",
    ),
    PortabilityRule(
        "readlink-f", "readlink", _flag("f"), None,
        "GNU, and macOS only since 12.3",
    ),
    PortabilityRule(
        "date-d", "date", _flag("d"), None,
        "GNU: parse a date string. BSD: set the kernel daylight-saving flag",
    ),
    PortabilityRule(
        "date-v", "date", _flag("v", allow_attached=True), None,
        "BSD: adjust the date. GNU has no -v",
    ),
    PortabilityRule(
        "date-j", "date", _flag("j"), None,
        "BSD: do not set the clock. GNU has no -j",
    ),
    PortabilityRule(
        "date-r", "date", _flag("r"), "GNU",
        "BSD -r takes epoch seconds OR a file; GNU -r takes a file only",
    ),
    PortabilityRule(
        "grep-P", "grep", _flag("P"), None,
        "GNU-only Perl-compatible regex mode; BSD grep has no -P at all",
    ),
]

MKTEMP_RULE_NAME = "mktemp-suffix-after-x-run"

# A run of at least three X's. BSD substitutes only a TRAILING one.
X_RUN_RE = re.compile(r"X{3,}")

# Characters that END a shell word, so an X-run followed by one of them is the
# template's own tail and needs no substitution beyond it.
WORD_ENDERS = set(" \t\"'`)|;&<>")

MKTEMP_RE = re.compile(rf"{_CMD}mktemp\b")


def _blank_heredocs(text):
    """Replaces every heredoc BODY with blank lines, keeping the line count
    intact. Mirrors test_external_tool_exit_status.py's helper of the same
    name and the terminator rule test_heredoc_interpolation_scan.py
    documents: a body ends at the first line that, after stripping leading
    tabs for `<<-`, equals the delimiter exactly."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = HEREDOC_OPEN_RE.search(lines[i])
        if m:
            delim = m.group(2)
            strip_tabs = lines[i][m.start():m.start() + 3].startswith("<<-")
            j = i + 1
            while j < len(lines):
                probe = lines[j].lstrip("\t") if strip_tabs else lines[j]
                if probe == delim:
                    break
                lines[j] = ""
                j += 1
            i = j
        i += 1
    return "\n".join(lines)


def _mask_non_live(text):
    """Blanks comment bodies and quoted content to spaces, keeping newlines
    (and therefore line numbers and columns) intact.

    Reimplements test_external_tool_exit_status.py's `_mask_non_live` rather
    than importing it: a relative import would make this module unrunnable as
    `python3 -m unittest scripts.tests.test_bsd_gnu_portability` without
    `-t .`, which CONTRIBUTING.md records as already silently skipping 510
    tests across 16 modules. The one behaviour that matters here is copied
    faithfully -- a `$(` inside a double-quoted string stays LIVE, because
    `mode="$(stat -f '%Lp' "$f")"` (scripts/lib/frontmatter.sh:259) is a real
    construct inside a quoted assignment and blanking it wholesale would blind
    the scanner to it."""
    n = len(text)
    out = list(text)
    i = 0
    in_single = False
    in_double = False
    stack = []
    while i < n:
        c = text[i]
        if in_single:
            if c == "'":
                in_single = False
            if c != "\n":
                out[i] = " "
            i += 1
            continue
        if in_double:
            if c == "\\" and i + 1 < n:
                out[i] = " "
                if text[i + 1] != "\n":
                    out[i + 1] = " "
                i += 2
                continue
            if c == '"':
                out[i] = " "
                in_double = False
                i += 1
                continue
            if c == "$" and i + 1 < n and text[i + 1] == "(":
                stack.append(True)
                in_double = False
                i += 2
                continue
            if c != "\n":
                out[i] = " "
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out[i] = " "
            if text[i + 1] != "\n":
                out[i + 1] = " "
            i += 2
            continue
        if c == "'":
            in_single = True
            out[i] = " "
            i += 1
            continue
        if c == '"':
            in_double = True
            out[i] = " "
            i += 1
            continue
        if c == "#":
            prev = text[i - 1] if i > 0 else "\n"
            if prev.isspace() or prev in "(;|&{":
                j = i
                while j < n and text[j] != "\n":
                    out[j] = " "
                    j += 1
                i = j
                continue
            i += 1
            continue
        if c == "(":
            stack.append(False)
            i += 1
            continue
        if c == ")":
            if stack:
                in_double = stack.pop()
            i += 1
            continue
        i += 1
    return "".join(out)


def _strip_comments_only(text):
    """Blanks comment bodies but leaves quoted content intact. The `mktemp`
    rule needs this variant: a temp-file template is routinely a QUOTED word
    (`mktemp "${file}.XXXXXX"`, five of the eleven live call sites), so
    running that rule over fully masked text would blind it to exactly that
    part of its own domain. Measured 30.08.2026: 22 live `mktemp` call sites
    in the 29 scanned files, 7 of them with a quoted template. Comments still
    go, because `scripts/run-tests.sh:53` and `:212` both discuss `XXXXXX`
    templates in prose."""
    n = len(text)
    out = list(text)
    i = 0
    in_single = False
    in_double = False
    while i < n:
        c = text[i]
        if c == "\n":
            in_single = False
            in_double = False
            i += 1
            continue
        if in_single:
            if c == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                in_double = False
            i += 1
            continue
        if c == "'":
            in_single = True
            i += 1
            continue
        if c == '"':
            in_double = True
            i += 1
            continue
        if c == "#":
            prev = text[i - 1] if i > 0 else "\n"
            if prev.isspace() or prev in "(;|&{":
                j = i
                while j < n and text[j] != "\n":
                    out[j] = " "
                    j += 1
                i = j
                continue
        i += 1
    return "".join(out)


def _braces_balanced_from(masked_line, brace_idx):
    """True when the opener's `{` is CLOSED on the same line -- a genuine
    one-line function. Counting balance rather than testing
    `line.rstrip().endswith("}")` is the difference between recognising
    `say()  { printf \'%s\\n\' "$1"; }` and being fooled by
    `foo() { local x=${1}` or `noise() { echo {x}`, whose bodies continue
    below. The decoy is not merely noise: a mis-collapsed range reclassifies
    the real body as top level, so a `uname` inside it drifts into the
    ten-line window of an unrelated construct BELOW the closing brace and
    silently exempts it. Counted on the MASKED line, so a brace inside a
    string or a comment cannot balance anything."""
    depth = 0
    for ch in masked_line[brace_idx:]:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    return depth == 0


def function_ranges(masked_lines):
    """Returns [(start_idx, end_idx)] (inclusive, 0-based) for every shell
    function body. A one-line function (`say() { printf '%s\\n' "$1"; }`, 20+
    instances in this corpus) is its own single-line range. Otherwise the body
    runs to the first later line whose stripped content starts with `}` at the
    opener's own indentation -- run over MASKED lines, so a brace inside a
    string or a comment cannot close a function early."""
    ranges = []
    for i, line in enumerate(masked_lines):  # noqa: E501 -- see _braces_balanced_from
        m = FUNC_OPEN_RE.match(line)
        if not m:
            continue
        indent = m.group(1)
        if _braces_balanced_from(line, m.end() - 1):
            ranges.append((i, i))
            continue
        for j in range(i + 1, len(masked_lines)):
            probe = masked_lines[j]
            if probe.startswith(indent + "}") and probe[len(indent):].strip() == "}":
                ranges.append((i, j))
                break
        else:
            ranges.append((i, len(masked_lines) - 1))
    return ranges


def sight_range(masked_lines, ranges, idx):
    """The line indices "in sight" of the construct on `masked_lines[idx]`:
    the innermost enclosing function body if there is one, else the
    TOP_LEVEL_WINDOW lines above plus the construct's own, MINUS any line
    that belongs to some function body.

    That subtraction is the other half of the one-line-function fix. A
    top-level statement is not dominated by a branch inside a function that
    merely happens to sit above it -- the function's body only runs where it
    is CALLED. Without the filter, `noise() { ...; ref=$(uname); }` followed
    ten lines later by a bare `stat -f` exempts that `stat`, and a decoy
    brace on the opener line is not even needed to trigger it.

    See the module docstring for why the whole file is deliberately not an
    option in either branch."""
    best = None
    for start, end in ranges:
        if start <= idx <= end:
            if best is None or (end - start) < (best[1] - best[0]):
                best = (start, end)
    if best is not None:
        return list(range(best[0], best[1] + 1))
    in_a_function = set()
    for start, end in ranges:
        in_a_function.update(range(start, end + 1))
    return [k for k in range(max(0, idx - TOP_LEVEL_WINDOW), idx + 1)
            if k not in in_a_function]


def _splices(line):
    """True when `line` is spliced into the next one by a trailing backslash.
    The run of trailing backslashes must be ODD (`cmd \\` passes a literal
    backslash and ENDS the command) and nothing may follow it -- a single
    space after the backslash kills the splice in the shell as well. Both
    halves are pinned by `MarkerCoversTheWholeContinuedStatementTest`."""
    run = len(line) - len(line.rstrip("\\"))
    return run % 2 == 1


def logical_line_span(splice_lines, idx):
    """The physical line range [start, end] of the ONE command line `idx`
    belongs to, following backslash splices in both directions.

    `splice_lines` must be the COMMENT-BLANKED, heredoc-blanked variant, not
    the raw text: a comment runs to the end of its line in the shell whether
    or not it ends in a backslash, and a heredoc body is data. Reading either
    as a continuation extends the sight past a boundary the shell itself
    respects -- `MarkerTextIsReadOffLiveSourceTest` pins both."""
    start = idx
    while start > 0 and _splices(splice_lines[start - 1]):
        start -= 1
    end = idx
    while end + 1 < len(splice_lines) and _splices(splice_lines[end]):
        end += 1
    return start, end


def marker_sight(splice_lines, idx):
    r"""The line indices where a `# portability: exempt <reason>` marker counts
    for the construct at `idx`: the whole logical line, plus the one line
    above it.

    Not just `(idx, idx - 1)`. A `\`-continued statement cannot carry a
    comment on a middle line without the splice eating the rest of the
    command, so the only legal place for the marker on a multi-line `||`
    chain is the line the statement FINISHES on -- which sits BELOW the
    construct being exempted. `test_external_tool_exit_status.py`'s
    `find_exemption` searches the same range for the same reason.

    Bounded by the statement, not by a distance: a marker on the line after
    the statement ends, or two lines above where it starts, is not a marker
    for it."""
    start, end = logical_line_span(splice_lines, idx)
    return range(max(0, start - 1), end + 1)


def _exemption_category(marker_lines, splice_lines, idx):
    """The `<reason>` token of a `# portability: exempt <reason>` marker
    anywhere in the construct's marker sight, or None.

    `marker_lines` is the heredoc-blanked text with COMMENTS INTACT -- the
    marker is itself a comment, so `_mask_non_live` and `_strip_comments_only`
    have both already erased it, while the raw text would let a marker-shaped
    line inside a heredoc body (a script writing a script) count as a real
    decision."""
    for probe in marker_sight(splice_lines, idx):
        m = EXEMPTION_MARKER_RE.search(marker_lines[probe])
        if m and m.group(1):
            return m.group(1)
    return None


class PortabilityFinding:
    __slots__ = ("path_label", "line", "rule", "text")

    def __init__(self, path_label, line, rule, text):
        self.path_label = path_label
        self.line = line
        self.rule = rule
        self.text = text

    def key(self):
        return (self.path_label, self.line, self.rule)

    def __repr__(self):
        return f"{self.path_label}:{self.line}:{self.rule}: {self.text.strip()}"


def _mktemp_hits(comment_stripped_line, masked_line):
    """True when the line has a `mktemp` whose OWN template carries a suffix
    after its final X-run. The test is the character right after the run: a
    word ender (whitespace, a quote, `)`, `|`, ...) means the run IS the tail
    and BSD substitutes it; anything else -- `.json`, `-old` -- means BSD
    returns the whole template verbatim.

    The tail is bounded to the mktemp call's own argument span, computed off
    the MASKED line (both variants are position-preserving transforms of the
    same heredoc-blanked text, so the indices line up). Without that bound an
    unrelated later token carrying an `XXXXXX`-shaped tag --
    `tmp=$(mktemp); pkg="dist/app-XXXXXX.tar.gz"` -- turned a correct, bare
    `mktemp` into a false positive, and packaging scripts carry exactly that
    shape. Every `mktemp` on the line is examined, not just the first."""
    depths = _paren_depths(masked_line)
    for m in MKTEMP_RE.finditer(comment_stripped_line):
        depth = depths[m.start()]
        limit = len(comment_stripped_line)
        for k in range(m.end(), len(comment_stripped_line)):
            if depths[k] < depth or (
                masked_line[k] in BOUNDARY_CHARS and depths[k] == depth
            ):
                limit = k
                break
        tail = comment_stripped_line[m.end():limit]
        for run in X_RUN_RE.finditer(tail):
            after = tail[run.end():run.end() + 1]
            if after and after not in WORD_ENDERS:
                return True
    return False


class ScanBases:
    """The three position-preserving views one scan needs, kept together so a
    caller cannot pick the wrong one by accident:

      * `raw`    -- untouched source. Only for the TEXT of a reported finding.
      * `marker` -- heredoc bodies blanked, comments INTACT. For finding
                    `# portability: exempt` markers.
      * `splice` -- heredoc bodies AND comment bodies blanked, escapes intact.
                    For deciding what a backslash continuation joins.

    All three have the same length and the same line numbering."""

    __slots__ = ("raw", "marker", "splice")

    def __init__(self, raw, marker, splice):
        self.raw = raw
        self.marker = marker
        self.splice = splice


def _construct_matches(text):
    """Every line carrying a candidate construct, with BOTH exemption
    dispositions attached rather than short-circuited away:
    `(idx, rule_names, uname_guarded, marker_category)`.

    One loop, three views. `scan_source` reports what neither disposition
    excused, `scan_exemptions` reports what a MARKER excused, and
    `stale_markers` needs the set of lines a marker could legitimately sit on.
    Before R3 the marker branch was a bare `continue`, so an exemption left no
    trace anything could count -- which is how an exemption list starts
    growing unread."""
    body_blanked = _blank_heredocs(text)
    masked = _mask_non_live(body_blanked)
    comment_stripped = _strip_comments_only(body_blanked)
    masked_lines = masked.split("\n")
    stripped_lines = comment_stripped.split("\n")
    raw_lines = text.split("\n")
    ranges = function_ranges(masked_lines)

    marker_lines = body_blanked.split("\n")

    matches = []
    for idx, masked_line in enumerate(masked_lines):
        hits = [rule.name for rule in FLAG_RULES if rule.matches(masked_line)]
        if _mktemp_hits(stripped_lines[idx], masked_line):
            hits.append(MKTEMP_RULE_NAME)
        if not hits:
            continue
        guarded = any("uname" in masked_lines[k]
                      for k in sight_range(masked_lines, ranges, idx))
        matches.append((idx, hits, guarded,
                        _exemption_category(marker_lines, stripped_lines, idx)))
    return ScanBases(raw_lines, marker_lines, stripped_lines), matches


def scan_source(text, path_label):
    """Scans one shell script's SOURCE TEXT (so a historical revision read via
    `git show` is scanned by exactly the same code path as a file on disk).
    Returns a list of PortabilityFinding."""
    bases, matches = _construct_matches(text)
    findings = []
    for idx, hits, guarded, category in matches:
        if category or guarded:
            continue
        for name in hits:
            findings.append(
                PortabilityFinding(path_label, idx + 1, name, bases.raw[idx]))
    return findings


def scan_exemptions(text, path_label):
    """The complement of `scan_source`: `(path, line, rule, category)` for
    every construct a MARKER excused. A construct a `uname` branch already
    guards is NOT listed -- its marker excuses nothing, and `stale_markers`
    reports it as dead instead of quietly counting it as used."""
    _, matches = _construct_matches(text)
    return [(path_label, idx + 1, name, category)
            for idx, hits, guarded, category in matches
            if category and not guarded
            for name in hits]


def stale_markers(text, path_label):
    """Markers that excuse nothing: `(path, line, category)` for every
    `# portability: exempt` whose position is in no construct's marker sight
    -- a construct that moved, was repaired, or was `uname`-guarded all the
    way. Without this, a repaired site leaves its marker behind and the next
    construct that drifts onto that line is silently pre-excused."""
    bases, matches = _construct_matches(text)
    live = set()
    for idx, _hits, guarded, _category in matches:
        if guarded:
            continue
        live.update(marker_sight(bases.splice, idx))
    out = []
    for i, line in enumerate(bases.marker):
        m = EXEMPTION_MARKER_RE.search(line)
        if m and i not in live:
            out.append((path_label, i + 1, m.group(1)))
    return out


def scanned_files(repo_root=REPO_ROOT):
    """The 29 shipped shell scripts -- see the module docstring's "Scope"
    section for why this is wider than scripts/shellcheck-run.sh's 22."""
    scripts = repo_root / "scripts"
    files = (
        [repo_root / "install.sh"]
        + sorted(scripts.glob("*.sh"))
        + sorted((scripts / "lib").glob("*.sh"))
        + sorted((scripts / "local-llm").glob("*.sh"))
        + sorted((repo_root / "templates" / "ci").glob("*.sh"))
    )
    return [f for f in files if f.is_file()]


def _over_tree(fn, repo_root=REPO_ROOT):
    out = []
    for f in scanned_files(repo_root):
        label = f.relative_to(repo_root).as_posix()
        out.extend(fn(f.read_text(), label))
    return out


def scan_tree(repo_root=REPO_ROOT):
    return _over_tree(scan_source, repo_root)


def exemptions_tree(repo_root=REPO_ROOT):
    return _over_tree(scan_exemptions, repo_root)


def stale_markers_tree(repo_root=REPO_ROOT):
    return _over_tree(stale_markers, repo_root)


def _read_git_show(ref_and_path):
    """Reads a file at a historical ref. Verifies the ref RESOLVES first
    (G-082) so a shallow clone -- actions/checkout's `fetch-depth: 1` default,
    which .github/workflows/ci.yml overrides for exactly this reason -- fails
    with a named error instead of an opaque `git show` failure."""
    ref = ref_and_path.split(":", 1)[0]
    subprocess.run(
        ["git", "rev-parse", "--verify", ref + "^{commit}"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    result = subprocess.run(
        ["git", "show", ref_and_path],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout


# Findings on the CURRENT tree that carry NO exemption, keyed (path, line,
# rule) the same way test_heredoc_interpolation_scan.py's own registry is.
#
# Empty since R3. WI-0130 recorded nine here, all `||` fallback chains rather
# than `uname` branches -- the single reason they were flagged; see the module
# docstring on why a `||` chain is not accepted as a guard. R3 did not repair
# any of them (each repair is a code change and needs its own red proof and
# its own round). It wrote down, at each site, WHY the chain carries today,
# and moved the nine into EXEMPTED_SITES below, where two separate checks now
# hold them: the set cannot change silently, and a marker that stops excusing
# anything is reported as stale.
#
# An empty registry makes this test's set equality one-directional in
# practice -- there is nothing left to go stale here -- but not vacuous: a
# NEWLY introduced unexempted construct anywhere in the 29 files still fails
# it on the next run. The direction this registry used to cover is now
# covered by NoStaleMarkerTest for the exemption list instead.
#
# WI-0131 line shift (kept for the record, since EXEMPTED_SITES inherited the
# line numbers): the CRLF fix inserted a 43-line header block ABOVE all five
# frontmatter.sh sites; none of the five lines was itself touched. Proven by
# byte-comparing HEAD:<old line> against <new line> for each (all five
# identical, uniform delta +43) and by the diff carrying 13 removed lines,
# none of them a `date`/`stat` call -- a count of 5-before/5-after alone
# cannot tell a shift from "one gone, one new". R3 itself shifted NOTHING:
# every marker is a trailing comment on a line that already existed, so both
# line-keyed registries survived it untouched.
KNOWN_FINDINGS = set()


# --------------------------------------------------------------------------
# The exemption registry (R3)
# --------------------------------------------------------------------------
#
# One reason text per CATEGORY, not per site -- the same shape
# `test_external_tool_exit_status.py`'s `EXEMPTION_REASONS` uses, and for the
# same reason: the sites within a category share their argument, and nine
# copies of one paragraph is nine chances to drift.
#
# The two categories are NOT equivalent, and the split is the point of this
# registry. Seven sites are portable idioms. Two are not: they work today by
# an accident the scanner cannot see, and the category name says so at every
# site that carries it.
EXEMPTION_CATEGORIES = {
    "bsd-gnu-date-flags-are-mutually-invalid": (
        "A BSD-form-then-GNU-form `date` chain whose two forms reject each "
        "other's flags OUTRIGHT, so the wrong platform's form fails by EXIT "
        "STATUS -- which is exactly what the `||` reads -- and cannot "
        "half-succeed into a plausible wrong answer. Measured 31.08.2026 on "
        "one machine carrying both implementations (BSD /bin/date on Darwin "
        "25.5, GNU coreutils 9.11 date), each of the four forms run under "
        "each: `date -v-7d`, `date -j -f ...` and `date -j -u -f ...` are "
        "`invalid option` on GNU (exit 1, empty stdout); `date -d ...` and "
        "`date -u -d ...` are `illegal option -- d` on BSD (exit 1, empty "
        "stdout). This is an exemption, not a claim that the shape is ideal: "
        "a `uname` branch would state the intent instead of relying on the "
        "flag namespaces staying disjoint. That is its own round."
    ),
    "stat-f-guard-is-an-operand-accident": (
        "NOT a portable idiom -- exempted because it WORKS today, by "
        "accident, and the accident has to be written down where the next "
        "reader of the chain will see it. `stat -f` is a VALID GNU option "
        "(`--file-system`), an entirely different mode, so GNU does not "
        "reject the flag the way it rejects `date -j`. The chain falls "
        "through only because GNU then reads the format string `%Lp` as a "
        "second FILE OPERAND that does not resolve. Measured 31.08.2026 with "
        "GNU coreutils 9.11 stat: `stat -f '%Lp' <file>` exits 1 with "
        "`cannot read file system information for '%Lp'` on stderr WHILE "
        "writing a real filesystem block for <file> to stdout. Create a file "
        "literally named `%Lp` in the working directory and the identical "
        "call exits 0 (measured), `mode` becomes that multi-line block, the "
        "`||` never fires, and `chmod \"$mode\"` fails into its `|| true` -- "
        "leaving the rewritten file at mktemp's 0600 instead of its original "
        "mode. What guards this site is the argument's path-resolvability, "
        "not the flag's portability. The chain's SECOND member is different: "
        "BSD stat rejects `-c` outright (`illegal option -- c`, exit 1, "
        "measured), so only the first half is the accident -- it is filed "
        "under the same category because one marker covers the one statement "
        "they are both part of. This site wants a real `uname` branch; that "
        "is a code change and so its own round, with its own red proof."
    ),
}


# Every site a MARKER excuses, keyed `(path, line, rule, category)`.
#
# Keyed by line number like `KNOWN_FINDINGS` above rather than by the
# marker's own source position (the drift-immune keying
# `test_external_tool_exit_status.py` chose): one module, one convention, and
# a line-keyed set makes an EXCHANGE visible -- swapping which of two
# adjacent sites carries which category changes the set, where a count or a
# per-file tally would not. The cost is the same bookkeeping `KNOWN_FINDINGS`
# already carries, and WI-0131 shows what paying it looks like.
EXEMPTED_SITES = {
    ("scripts/lib/frontmatter.sh", 236, "date-j",
     "bsd-gnu-date-flags-are-mutually-invalid"),
    ("scripts/lib/frontmatter.sh", 237, "date-j",
     "bsd-gnu-date-flags-are-mutually-invalid"),
    ("scripts/lib/frontmatter.sh", 243, "date-d",
     "bsd-gnu-date-flags-are-mutually-invalid"),
    ("scripts/lib/frontmatter.sh", 259, "stat-f",
     "stat-f-guard-is-an-operand-accident"),
    ("scripts/lib/frontmatter.sh", 260, "stat-c",
     "stat-f-guard-is-an-operand-accident"),
    ("scripts/log-cleanup.sh", 69, "date-d",
     "bsd-gnu-date-flags-are-mutually-invalid"),
    ("scripts/log-cleanup.sh", 69, "date-v",
     "bsd-gnu-date-flags-are-mutually-invalid"),
    ("scripts/log-cleanup.sh", 104, "date-j",
     "bsd-gnu-date-flags-are-mutually-invalid"),
    ("scripts/log-cleanup.sh", 105, "date-d",
     "bsd-gnu-date-flags-are-mutually-invalid"),
}


# --------------------------------------------------------------------------
# Fixture helper
# --------------------------------------------------------------------------


def _scan_text(source, label="fixture.sh"):
    return scan_source(source, label)


def _rule_names(findings):
    return sorted(f.rule for f in findings)


# --------------------------------------------------------------------------
# Historical red proofs -- the two real defects, not reconstructions
# --------------------------------------------------------------------------


class HistoricalLogCleanupIsFlaggedTest(unittest.TestCase):
    """Red proof 1: `269d490^:scripts/log-cleanup.sh` is the state in which
    `find -printf` (line 69) and `stat -f` (lines 70 and 74) were live. All
    three must be reported. A scanner that only fires against fixtures written
    for it proves its own regex; one that fires against the real defect proves
    the class."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read_git_show(f"{LOG_CLEANUP_FIX_COMMIT}^:scripts/log-cleanup.sh")

    def test_the_pre_fix_state_carries_the_three_original_sites(self):
        keys = {(f.line, f.rule) for f in _scan_text(self.text, "pre-fix/log-cleanup.sh")}
        for expected in ((69, "find-printf"), (70, "stat-f"), (74, "stat-f")):
            self.assertIn(
                expected, keys,
                f"the historical defect at line {expected[0]} ({expected[1]}) was "
                f"NOT reported -- this scanner cannot see the class it exists "
                f"for. Reported: {sorted(keys)}",
            )

    def test_the_fallback_chain_alone_did_not_exempt_the_historical_sites(self):
        """The three sites above all sat inside `... || ... || echo "0"`
        chains. This asserts the discriminating half directly: the pre-fix
        text CONTAINS the chain, and the sites are findings anyway."""
        lines = self.text.split("\n")
        self.assertIn("-printf", lines[68])
        self.assertIn("||", lines[68])
        flagged = {f.line for f in _scan_text(self.text, "pre-fix/log-cleanup.sh")}
        self.assertIn(69, flagged)

    def test_the_current_log_cleanup_no_longer_carries_the_three_sites(self):
        """Positive-form pin naming the repaired file directly: the `uname`
        branch `269d490` introduced (`mtime_of()`) exempts the `stat` pair,
        and `find -printf` is gone entirely. The `date` chain findings that
        remain are in KNOWN_FINDINGS and are a different, unrepaired site."""
        current = _scan_text(
            (SCRIPTS_DIR / "log-cleanup.sh").read_text(), "scripts/log-cleanup.sh"
        )
        self.assertEqual([], [f for f in current if f.rule in ("find-printf", "stat-f", "stat-c")])


class HistoricalMktempTemplatesAreFlaggedTest(unittest.TestCase):
    """Red proof 2, and the sharper half of the whole exercise:
    `bc87c9f^:scripts/run-tests.sh` carries FIVE `mktemp` templates. Two of
    them (lines 53 and 186) end in `XXXXXX.json` and are the defect; three
    (lines 117, 255, 313) end in a bare `XXXXXX` and are CORRECT. Reporting
    the two while leaving the three alone is what shows the rule matches the
    FORM and not the word `mktemp`."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read_git_show(f"{RUN_TESTS_FIX_COMMIT}^:scripts/run-tests.sh")

    def test_the_two_suffixed_templates_are_flagged(self):
        keys = {(f.line, f.rule) for f in _scan_text(self.text, "pre-fix/run-tests.sh")}
        self.assertIn((53, MKTEMP_RULE_NAME), keys)
        self.assertIn((186, MKTEMP_RULE_NAME), keys)

    def test_the_three_unsuffixed_templates_are_not_flagged(self):
        lines = self.text.split("\n")
        for lineno in (117, 255, 313):
            self.assertIn(
                "mktemp", lines[lineno - 1],
                f"fixture assumption drifted: line {lineno} of "
                f"{RUN_TESTS_FIX_COMMIT}^:scripts/run-tests.sh is no longer a "
                f"mktemp call ({lines[lineno - 1]!r})",
            )
        flagged = {f.line for f in _scan_text(self.text, "pre-fix/run-tests.sh")
                   if f.rule == MKTEMP_RULE_NAME}
        self.assertEqual(
            {53, 186}, flagged,
            "the mktemp rule matched the WORD, not the FORM -- the three "
            "correct bare-XXXXXX templates at 117/255/313 must stay unflagged",
        )

    def test_the_current_run_tests_carries_no_mktemp_finding(self):
        """WI-0133 T3: a `set` pin whose pinned collection is empty. The
        measured side is the live scan of the shipped scripts/run-tests.sh
        filtered to the mktemp rule; the declared side is the whole
        collection, not a count of it, so any finding that reappears changes
        the assertion and the failure names it. There is nothing to swap it
        against -- an empty collection has no interior -- which is why the
        group holds here without the two-direction split the sibling
        register pairs need."""
        current = _scan_text(
            (SCRIPTS_DIR / "run-tests.sh").read_text(), "scripts/run-tests.sh"
        )
        self.assertEqual(  # pin: set run-tests-mktemp-free
            [], [f for f in current if f.rule == MKTEMP_RULE_NAME])


# --------------------------------------------------------------------------
# Structural mutation: the exemption must be verifiable, not merely written
# --------------------------------------------------------------------------


class RemovingTheUnameBranchTurnsAShippedSiteIntoAFindingTest(unittest.TestCase):
    """The exemption form must itself be under test. `scripts/instinct-check.sh`
    is exempt today because `mtime_of()` branches on `uname`. Mutate the
    SHIPPED text so the branch SHAPE survives and only the `uname` call goes
    (`if [[ "$(uname)" == "Darwin" ]]; then` -> `if [[ "Darwin" == "Darwin" ]];
    then`) -- a structural change, not a deletion -- and both `stat` sites must
    come back as findings. Deleting a rule would turn every test red and prove
    nothing; this changes the FORM the exemption depends on."""

    NEEDLE = 'if [[ "$(uname)" == "Darwin" ]]; then'
    MUTANT = 'if [[ "Darwin" == "Darwin" ]]; then'

    def setUp(self):
        self.text = (SCRIPTS_DIR / "instinct-check.sh").read_text()

    def test_the_shipped_file_is_exempt_today(self):
        findings = _scan_text(self.text, "scripts/instinct-check.sh")
        self.assertEqual(
            [], [f for f in findings if f.rule in ("stat-f", "stat-c")],
            "instinct-check.sh's mtime_of() is the repo's own reference "
            "uname branch -- it must not be a finding",
        )

    def test_removing_only_the_uname_call_makes_both_stat_sites_findings(self):
        # G-141: assert the mutation actually GRIPPED before measuring. A
        # replacement that matched nothing would report "passed".
        occurrences = self.text.count(self.NEEDLE)
        self.assertEqual(
            1, occurrences,
            f"mutation needle drifted -- {occurrences} occurrence(s) of "
            f"{self.NEEDLE!r} in scripts/instinct-check.sh, expected exactly 1",
        )
        mutated = self.text.replace(self.NEEDLE, self.MUTANT, 1)
        self.assertEqual(
            occurrences - 1, mutated.count(self.NEEDLE),
            "the replacement did not take effect",
        )
        self.assertEqual(
            self.text.count("uname") - 1, mutated.count("uname"),
            "the mutation removed something other than exactly one `uname` call",
        )
        findings = _scan_text(mutated, "mutant/instinct-check.sh")
        rules = _rule_names([f for f in findings if f.rule in ("stat-f", "stat-c")])
        self.assertEqual(
            ["stat-c", "stat-f"], rules,
            "an exemption that stops being verified must stop being granted; "
            f"got {findings}",
        )


class UnameInAnotherFunctionDoesNotExemptTest(unittest.TestCase):
    """Pins the function-scope half of "in sight" against the file-scope
    alternative. The fixture HAS a `uname` branch -- in the wrong function.
    A file-scoped rule would call this exempt; the shipped rule must not."""

    SOURCE = (
        "#!/usr/bin/env bash\n"
        "portable_mtime() {\n"
        '    if [[ "$(uname)" == "Darwin" ]]; then\n'
        '        stat -f %m "$1"\n'
        "    else\n"
        '        stat -c %Y "$1"\n'
        "    fi\n"
        "}\n"
        "\n"
        "newest_file() {\n"
        '    stat -f %m "$1"\n'
        "}\n"
    )

    def test_a_uname_branch_in_a_different_function_does_not_exempt(self):
        findings = _scan_text(self.SOURCE)
        self.assertEqual(
            [(11, "stat-f")], [(f.line, f.rule) for f in findings],
            "the guarded pair inside portable_mtime() must stay exempt and the "
            "unguarded call inside newest_file() must be reported; "
            f"got {findings}",
        )


class UnameBeyondTheTopLevelWindowDoesNotExemptTest(unittest.TestCase):
    """The top-level half of the same boundary: a `uname` eleven lines above a
    top-level construct is out of sight, ten lines above is in it."""

    def _source(self, gap):
        return (
            "#!/usr/bin/env bash\n"
            'PLATFORM="$(uname)"\n'
            + "".join(f"# filler {i}\n" for i in range(gap))
            + 'stat -f %m "$1"\n'
        )

    def test_uname_within_the_window_exempts(self):
        # uname on line 2, construct on line 2 + 8 + 1 = 11 -> 9 lines apart.
        self.assertEqual([], _scan_text(self._source(8)))

    def test_uname_beyond_the_window_does_not_exempt(self):
        # uname on line 2, construct on line 2 + 12 + 1 = 15 -> 13 lines apart.
        findings = _scan_text(self._source(12))
        self.assertEqual([(15, "stat-f")], [(f.line, f.rule) for f in findings])


class FallbackChainIsNotAnExemptionTest(unittest.TestCase):
    """The founding decision, as a fixture rather than only as prose: the
    exact `||` shape `269d490^:scripts/log-cleanup.sh:69-70` used is a
    finding, twice over."""

    SOURCE = (
        "#!/usr/bin/env bash\n"
        "newest=$(find \"$d\" -type f -printf '%T@\\n' 2>/dev/null | sort -rn | head -1 || \\\n"
        "         stat -f '%m' \"$d\"/*.jsonl 2>/dev/null | sort -rn | head -1 || echo \"0\")\n"
    )

    def test_a_bsd_or_gnu_fallback_chain_is_still_a_finding(self):
        findings = _scan_text(self.SOURCE)
        self.assertEqual(
            [(2, "find-printf"), (3, "stat-f")],
            sorted((f.line, f.rule) for f in findings),
        )


class ExemptionMarkerIsHonouredTest(unittest.TestCase):
    """The second, explicit exemption form -- the same `# <topic>: exempt
    <reason>` idiom this repo already uses for `# exit-status: exempt ...`.
    Recognised on the construct's own line and on the line above it, and
    nowhere else: a marker two lines up is not a marker."""

    def test_marker_on_the_same_line_exempts(self):
        source = (
            "#!/usr/bin/env bash\n"
            'stat -c %Y "$1"  # portability: exempt linux-only-helper\n'
        )
        self.assertEqual([], _scan_text(source))

    def test_marker_on_the_line_above_exempts(self):
        source = (
            "#!/usr/bin/env bash\n"
            "# portability: exempt linux-only-helper\n"
            'stat -c %Y "$1"\n'
        )
        self.assertEqual([], _scan_text(source))

    def test_marker_two_lines_above_does_not_exempt(self):
        source = (
            "#!/usr/bin/env bash\n"
            "# portability: exempt linux-only-helper\n"
            "echo something\n"
            'stat -c %Y "$1"\n'
        )
        self.assertEqual([(4, "stat-c")], [(f.line, f.rule) for f in _scan_text(source)])


class MarkerWithoutAReasonDoesNotExemptTest(unittest.TestCase):
    """R3: a marker is a RECORDED DECISION, so it has to record something. A
    bare `# portability: exempt` with no reason after it names nothing, cannot
    be reviewed and cannot go stale visibly -- it is the "skip list nobody
    re-reads" shape this repo has already grown four times. Same grammar as
    `test_external_tool_exit_status.py`'s `MARKER_RE`, which has required a
    `<category>` token since it was written.

    Mutation note: loosening the grammar to `\\s*([A-Za-z0-9_-]*)` -- which DOES
    match a bare marker -- survives this whole module, and that is an
    EQUIVALENT mutant rather than a gap. Traced and measured: the loosened
    regex matches and returns `''`, which is falsy at `_exemption_category`'s
    single decision point, so all three views (`scan_source`,
    `scan_exemptions`, `stale_markers`) return byte-identical output. The
    explicit `and m.group(1)` there collapses the two guards into one visible
    statement rather than leaving the rule resting on Python truthiness."""

    def test_a_bare_marker_does_not_exempt(self):
        source = (
            "#!/usr/bin/env bash\n"
            "# portability: exempt\n"
            'stat -c %Y "$1"\n'
        )
        self.assertEqual(
            [(3, "stat-c")], [(f.line, f.rule) for f in _scan_text(source)])

    def test_a_marker_whose_reason_is_only_whitespace_does_not_exempt(self):
        source = (
            "#!/usr/bin/env bash\n"
            "# portability: exempt   \n"
            'stat -c %Y "$1"\n'
        )
        self.assertEqual(
            [(3, "stat-c")], [(f.line, f.rule) for f in _scan_text(source)])

    def test_a_marker_with_a_reason_still_exempts(self):
        """The other direction: without this, a grammar that rejects
        EVERYTHING would pass the two tests above."""
        source = (
            "#!/usr/bin/env bash\n"
            "# portability: exempt linux-only-helper\n"
            'stat -c %Y "$1"\n'
        )
        self.assertEqual([], _scan_text(source))


class MarkerCoversTheWholeContinuedStatementTest(unittest.TestCase):
    r"""R3: a `\`-continued statement cannot carry the marker on a middle
    line -- the splice would eat the rest of the command -- so the marker has
    to go on the line the statement FINISHES on. This is not a new idea in
    this repo: `test_external_tool_exit_status.py`'s `find_exemption` searches
    the whole physical range of an invocation for exactly this reason, and
    names the three shipped sites that need it. Without this, the second and
    later members of a backslash-continued `||` chain are structurally
    unmarkable -- `scripts/lib/frontmatter.sh:259-261` is precisely that
    shape.

    The sight is the LOGICAL line (every physical line spliced into one
    command) plus the one line above it -- not "some line nearby". The three
    negative tests below are what makes that a boundary rather than a
    direction."""

    CHAIN = (
        "#!/usr/bin/env bash\n"
        "mode=\"$(stat -f '%Lp' \"$1\" 2>/dev/null)\" \\\n"
        "    || mode=\"$(stat -c '%a' \"$1\" 2>/dev/null)\" \\\n"
        "    || return 0\n"
    )

    def test_without_a_marker_both_members_of_the_chain_are_findings(self):
        """The red half. A `||` chain is not a guard (see
        FallbackChainIsNotAnExemptionTest); both lines are reported."""
        self.assertEqual(
            [(2, "stat-f"), (3, "stat-c")],
            sorted((f.line, f.rule) for f in _scan_text(self.CHAIN)),
        )

    def test_a_marker_on_the_finishing_line_exempts_the_whole_statement(self):
        source = self.CHAIN.replace(
            "    || return 0\n",
            "    || return 0  # portability: exempt fixture-reason\n",
        )
        self.assertEqual([], _scan_text(source))

    def test_a_marker_on_the_line_above_the_statement_exempts_it(self):
        source = self.CHAIN.replace(
            "mode=\"$(stat -f",
            "# portability: exempt fixture-reason\nmode=\"$(stat -f",
        )
        self.assertEqual([], _scan_text(source))

    def test_a_marker_two_lines_above_the_statement_does_not_exempt(self):
        source = self.CHAIN.replace(
            "mode=\"$(stat -f",
            "# portability: exempt fixture-reason\necho unrelated\nmode=\"$(stat -f",
        )
        self.assertEqual(
            [(4, "stat-f"), (5, "stat-c")],
            sorted((f.line, f.rule) for f in _scan_text(source)),
        )

    def test_a_marker_on_the_line_after_the_statement_does_not_exempt(self):
        """The forward boundary. The splice ends at `|| return 0`; a marker on
        the NEXT line is outside the statement and must not reach back into
        it. Without this the fix would be "look downwards until you find
        one", which is a direction, not a scope."""
        source = self.CHAIN + "# portability: exempt fixture-reason\n"
        self.assertEqual(
            [(2, "stat-f"), (3, "stat-c")],
            sorted((f.line, f.rule) for f in _scan_text(source)),
        )

    def test_an_even_backslash_run_is_not_a_continuation(self):
        """`cmd \\` ends the command and passes a literal backslash; only an
        ODD trailing run splices. A naive `endswith("\\")` would splice this
        line into the marker below it and exempt a construct nobody
        exempted."""
        source = (
            "#!/usr/bin/env bash\n"
            'stat -c %Y "$1" \\\\\n'
            "# portability: exempt fixture-reason\n"
        )
        self.assertEqual(
            [(2, "stat-c")], [(f.line, f.rule) for f in _scan_text(source)])

    def test_a_backslash_followed_by_whitespace_is_not_a_continuation(self):
        """A trailing space after the backslash kills the splice in the shell
        too -- the scanner must agree with `bash`, not with a lenient rstrip."""
        source = (
            "#!/usr/bin/env bash\n"
            'stat -c %Y "$1" \\ \n'
            "# portability: exempt fixture-reason\n"
        )
        self.assertEqual(
            [(2, "stat-c")], [(f.line, f.rule) for f in _scan_text(source)])


# --------------------------------------------------------------------------
# Per-rule capability and precision
# --------------------------------------------------------------------------


class EveryAdoptedRuleFiresTest(unittest.TestCase):
    """Every rule in the shipped list must be able to produce a finding. A
    rule whose regex never matches anything is not a lenient rule, it is an
    absent one -- and it would be invisible in the counts below."""

    CASES = {
        "find-printf": 'newest=$(find "$d" -type f -printf \'%T@\\n\')\n',
        "stat-f": 'm=$(stat -f %m "$1")\n',
        "stat-c": 'm=$(stat -c %Y "$1")\n',
        "sed-i": "sed -i -e 's/a/b/' \"$f\"\n",
        "readlink-f": 'root=$(readlink -f "$0")\n',
        "date-d": 'epoch=$(date -d "$iso" +%s)\n',
        "date-v": "cutoff=$(date -v-7d +%Y-%m-%d)\n",
        "date-j": 'epoch=$(date -j -f "%Y-%m-%d" "$d" +%s)\n',
        "date-r": 'stamp=$(date -r 1700000000 +%s)\n',
        "grep-P": "grep -P '(?<=x)y' \"$f\"\n",
        MKTEMP_RULE_NAME: "tmp=$(mktemp /tmp/report-XXXXXX.json)\n",
    }

    def test_every_rule_has_a_case(self):
        expected = {r.name for r in FLAG_RULES} | {MKTEMP_RULE_NAME}
        self.assertEqual(
            expected, set(self.CASES),
            "a rule was added or removed without a matching capability case",
        )

    def test_each_rule_fires_on_its_own_case(self):
        for name, snippet in sorted(self.CASES.items()):
            with self.subTest(rule=name):
                findings = _scan_text("#!/usr/bin/env bash\n" + snippet)
                self.assertEqual(
                    [name], _rule_names(findings),
                    f"rule {name} did not fire on its own capability case",
                )


class PortableFormsAreNotFlaggedTest(unittest.TestCase):
    """Precision cases drawn from constructs actually shipped in this tree --
    each one would be a false positive that costs the scanner its credibility."""

    CASES = {
        "bare mktemp": "tmp=$(mktemp)\n",
        "mktemp trailing X run": 'tmp=$(mktemp "${file}.XXXXXX")\n',
        "mktemp -d trailing X run": "d=$(mktemp -d /tmp/quality-scan-XXXXXX)\n",
        "mktemp -t prefix": "TMP=$(mktemp -t artifact-gate.XXXXXX)\n",
        "date +%s": "now=$(date +%s)\n",
        "date format only": "NOW=$(date '+%d.%m.%Y %H:%M')\n",
        "git long option": 'git log --date=short --pretty=%H\n',
        "sed -n script": "sed -n '2,/^$/p' \"$f\" | sed 's/^# \\{0,1\\}//'\n",
        "sed -E script": 'printf %s "$b" | sed -E "s/^SPRINT-([0-9]+)//"\n',
        "grep -c": "n=$(grep -cE '^- ' \"$f\")\n",
        "find without printf": 'find "$d" -type f -name "*.jsonl"\n',
        "stat construct named in a comment": "# GNU `stat -f` is not BSD `stat -f`\n",
        "stat construct inside a string": 'die "use stat -c on linux"\n',
        "hyphenated word ending in date": "last-modified-date -d foo\n",
    }

    def test_no_portable_form_is_flagged(self):
        for label, snippet in sorted(self.CASES.items()):
            with self.subTest(case=label):
                findings = _scan_text("#!/usr/bin/env bash\n" + snippet)
                self.assertEqual([], findings, f"false positive on {label}: {findings}")


class ConstructInsideAHeredocBodyIsNotScannedTest(unittest.TestCase):
    """A documented boundary, asserted rather than merely claimed: heredoc
    bodies are blanked before masking (see the module docstring's "What this
    scan cannot see"), so a script that WRITES a script carrying the construct
    is invisible to this scan. Measured zero such shapes in the 29 files."""

    def test_a_stat_f_inside_a_heredoc_body_is_not_reported(self):
        source = (
            "#!/usr/bin/env bash\n"
            "cat > out.sh << 'EOS'\n"
            'stat -f %m "$1"\n'
            "EOS\n"
        )
        self.assertEqual([], _scan_text(source))


class QuotedTemplateWithSuffixIsStillFlaggedTest(unittest.TestCase):
    """Why the mktemp rule reads comment-stripped text rather than fully
    masked text: 7 of the corpus's 22 live templates are quoted words. A
    quoted template with a suffix is the same defect as an unquoted one."""

    def test_a_quoted_suffixed_template_is_flagged(self):
        source = '#!/usr/bin/env bash\ntmp="$(mktemp "/tmp/report-XXXXXX.json")"\n'
        self.assertEqual(
            [(2, MKTEMP_RULE_NAME)], [(f.line, f.rule) for f in _scan_text(source)]
        )


class CommandSubstitutionInsideDoubleQuotesStaysLiveTest(unittest.TestCase):
    """`mode="$(stat -f '%Lp' "$f")"` (scripts/lib/frontmatter.sh:259) is a
    live construct inside a quoted assignment. Blanking double-quoted content
    wholesale would hide it -- and it is one of the nine current findings, so
    this is not a hypothetical."""

    def test_a_construct_inside_a_quoted_command_substitution_is_seen(self):
        source = '#!/usr/bin/env bash\nmode="$(stat -f \'%Lp\' "$original")"\n'
        self.assertEqual([(2, "stat-f")], [(f.line, f.rule) for f in _scan_text(source)])


class FlagPairsWithItsOwnCommandAcrossASubstitutionTest(unittest.TestCase):
    """Review finding (Critical 1): a flag that sits AFTER a nested, unrelated
    `$(...)` in the SAME command's argument list must still pair with that
    command. A gap expressed as a character class that simply excludes `)`
    cannot: the `)` closing the nested substitution ends the gap, and the
    rule silently stops firing.

    `find "$(dirname "$0")/logs" -printf` is a reordered variant of this
    module's own founding defect, so the miss is not academic. Pairing is
    therefore by PAREN DEPTH plus a command-boundary scan at that depth, not
    by a character class."""

    def test_a_flag_after_a_nested_substitution_still_pairs(self):
        cases = {
            'stat $(dirname "$f") -f %m "$1"\n': [(2, "stat-f")],
            'find "$(dirname "$0")/logs" -printf \'%f\\n\'\n': [(2, "find-printf")],
        }
        for snippet, expected in sorted(cases.items()):
            with self.subTest(line=snippet.strip()):
                findings = _scan_text("#!/usr/bin/env bash\n" + snippet)
                self.assertEqual(expected, [(f.line, f.rule) for f in findings])

    def test_both_the_outer_and_the_nested_command_are_reported(self):
        """`find ... "$(date -v-7d +%F)" ... -printf` carries TWO independent
        divergences at two depths. Before the depth fix only the nested one
        was reported -- the outer `find -printf`, the more dangerous of the
        pair, was the one that went missing."""
        source = (
            "#!/usr/bin/env bash\n"
            'find "$d" -newer "$(date -v-7d +%F)" -printf \'%p\\n\'\n'
        )
        self.assertEqual(
            [(2, "date-v"), (2, "find-printf")],
            sorted((f.line, f.rule) for f in _scan_text(source)),
        )

    def test_a_flag_inside_a_substitution_does_not_pair_with_the_outer_command(self):
        """The discriminating half: depth pairing must be an EQUALITY, not
        "somewhere to the right".

        The fixture needs the OUTER command and the NESTED flag to belong to
        the same rule, or it proves nothing -- `find "$(stat -f %m x)"` looks
        like a discriminator but is not, because `find`'s only rule is
        `-printf` and dropping the depth test changes its verdict not at all.
        (Measured: that first fixture survived a mutation removing the depth
        equality entirely.) `readlink` and `stat` both key on `-f`, so here a
        depth-blind rule reports `readlink-f` as well, and the assertion sees
        it."""
        source = '#!/usr/bin/env bash\nreadlink "$(stat -f %m "$p")"\n'
        self.assertEqual(
            [(2, "stat-f")], [(f.line, f.rule) for f in _scan_text(source)],
            "the nested `stat -f` is the only finding; the outer `readlink` "
            "must not adopt the inner `-f` as its own",
        )

    def test_a_pipe_still_separates_a_command_from_a_later_flag(self):
        """The boundary half, which the character class DID get right and the
        depth rule must not lose: `sed ... | tee -i` is not a `sed -i`."""
        source = "#!/usr/bin/env bash\nsed 's/a/b/' \"$f\" | tee -i out\n"
        self.assertEqual([], _scan_text(source))


class OneLineFunctionDetectionUsesBraceBalanceTest(unittest.TestCase):
    """Review finding (Critical 2): treating any opener line that merely ENDS
    in `}` as a complete one-line function misreads
    `noise() { echo {x}` (or the likelier `foo() { local x=${1}`) as a
    one-liner. The function then collapses to a single-line range, its real
    body is reclassified as top level, and a `uname` inside it drifts into the
    ten-line window of an unrelated construct BELOW the closing brace -- so
    the failure is a false NEGATIVE on later, unrelated code, not just noise
    near the decoy."""

    DECOY = (
        "#!/usr/bin/env bash\n"
        "noise() { echo {x}\n"
        "    ref=$(uname)\n"
        "}\n"
        'stat -f %m "$1"\n'
    )

    def test_the_decoy_opener_is_not_read_as_a_one_line_function(self):
        masked = _mask_non_live(_blank_heredocs(self.DECOY)).split("\n")
        self.assertEqual(
            [(1, 3)], function_ranges(masked),
            "the function body must run to its real closing brace, not stop "
            "at the decoy `}` on the opener line",
        )

    def test_a_uname_inside_the_decoy_body_does_not_exempt_a_later_construct(self):
        self.assertEqual(
            [(5, "stat-f")], [(f.line, f.rule) for f in _scan_text(self.DECOY)],
            "the top-level construct on line 5 must stay a finding -- the "
            "`uname` on line 3 belongs to noise()'s body, not to its window",
        )

    def test_a_genuine_one_line_function_is_still_recognised(self):
        """The positive control: `say()  { printf '%s\\n' "$1"; }` is the shape
        this corpus carries 20+ times, and it must still be a single-line
        range -- otherwise the fix trades one misclassification for another."""
        source = (
            "#!/usr/bin/env bash\n"
            "say()  { printf '%s\\n' \"$1\"; }\n"
            'stat -f %m "$1"\n'
        )
        masked = _mask_non_live(_blank_heredocs(source)).split("\n")
        self.assertEqual([(1, 1)], function_ranges(masked))
        self.assertEqual([(3, "stat-f")], [(f.line, f.rule) for f in _scan_text(source)])


class NestedFunctionUsesTheInnermostRangeTest(unittest.TestCase):
    """Review note: `sight_range()` picks the smallest enclosing span. A
    function defined inside another function's body is the case that
    distinguishes "innermost" from "any enclosing" -- the outer function's
    `uname` must not reach into the inner one."""

    SOURCE = (
        "#!/usr/bin/env bash\n"
        "outer() {\n"
        '    if [[ "$(uname)" == "Darwin" ]]; then\n'
        "        inner() {\n"
        '            stat -f %m "$1"\n'
        "        }\n"
        "        inner \"$2\"\n"
        "    fi\n"
        "}\n"
    )

    def test_the_inner_function_does_not_inherit_the_outer_uname(self):
        self.assertEqual(
            [(5, "stat-f")], [(f.line, f.rule) for f in _scan_text(self.SOURCE)],
        )


class MktempTailStopsAtTheCommandBoundaryTest(unittest.TestCase):
    """Review finding (Important 1): the mktemp rule scanned the whole rest of
    the physical line for an X-run, so an unrelated later token carrying an
    `XXXXXX`-shaped tag turned a correct, bare `mktemp` into a false positive.
    Build and packaging scripts carry exactly that shape."""

    def test_an_unrelated_later_x_run_does_not_trip_a_bare_mktemp(self):
        source = (
            "#!/usr/bin/env bash\n"
            'tmp=$(mktemp); pkg="dist/app-XXXXXX.tar.gz"\n'
        )
        self.assertEqual([], _scan_text(source))

    def test_a_suffixed_template_on_the_same_line_is_still_flagged(self):
        """Positive control, so the boundary fix cannot be satisfied by
        simply never firing: the same line shape WITH a real defect in the
        mktemp call itself is still reported."""
        source = (
            "#!/usr/bin/env bash\n"
            'tmp=$(mktemp /tmp/report-XXXXXX.json); pkg="dist/app.tar.gz"\n'
        )
        self.assertEqual(
            [(2, MKTEMP_RULE_NAME)], [(f.line, f.rule) for f in _scan_text(source)]
        )

    def test_a_second_mktemp_later_on_the_line_is_still_seen(self):
        """A boundary that stops the tail scan must not stop the SEARCH: two
        mktemp calls on one line, only the second defective."""
        source = (
            "#!/usr/bin/env bash\n"
            "a=$(mktemp); b=$(mktemp /tmp/x-XXXXXX.log)\n"
        )
        self.assertEqual(
            [(2, MKTEMP_RULE_NAME)], [(f.line, f.rule) for f in _scan_text(source)]
        )


# --------------------------------------------------------------------------
# Scope and count pins
# --------------------------------------------------------------------------


class ScannedFilesCoverTheShippedScopeTest(unittest.TestCase):
    """Pins the enumeration, mirroring the identically named test in
    test_shell_script_syntax.py / test_heredoc_interpolation_scan.py: a file
    silently dropped from a glob would make this gate blind to it without
    failing first.

    WI-0133 T3: `test_scanned_files_cover_the_shipped_scope` carries the
    `set` marker -- the pinned value is the file list itself, so one script
    swapped for another changes the assertion and the failure names both
    sides. `test_an_empty_scope_is_never_a_pass` below deliberately carries
    no marker on either of its two assertions. Only ONE of them is in the
    inventory at all: `assertEqual(29, len(files))`, which pins an exact
    COUNT over the same repository-derived population -- the shape none of
    the four registered groups describes truthfully, so it stays in
    test_pin_inventory.py's PENDING until that vocabulary question is
    decided. The `assertGreater(len(files), 0)` above it is the floor in
    substance, but it is not a candidate: its declared side is the literal
    0, and a zero literal is not a stored value. When the question is
    answered, the count assertion is the natural `floor` partner for this
    `set`, under this same id."""

    def test_scanned_files_cover_the_shipped_scope(self):
        names = sorted(f.relative_to(REPO_ROOT).as_posix() for f in scanned_files())
        self.assertEqual(  # pin: set portability-scanned-scope
            [
                "install.sh",
                "scripts/anchor.sh",
                "scripts/artifact-gate.sh",
                "scripts/baseline.sh",
                "scripts/bootstrap.sh",
                "scripts/check-all.sh",
                "scripts/conformance-run.sh",
                "scripts/doc-volume-check.sh",
                "scripts/freeze-phase-docs.sh",
                "scripts/instinct-check.sh",
                "scripts/lib/discipline_gate.sh",
                "scripts/lib/frontmatter.sh",
                "scripts/local-llm/commit-msg.sh",
                "scripts/local-llm/handover-draft.sh",
                "scripts/local-llm/install-git-hook.sh",
                "scripts/local-llm/ollama-query.sh",
                "scripts/local-llm/summarize.sh",
                "scripts/log-cleanup.sh",
                "scripts/manual-lint.sh",
                "scripts/memory-lint.sh",
                "scripts/memory-sync.sh",
                "scripts/migrate-review-headers.sh",
                "scripts/phase-docs-lint.sh",
                "scripts/project-init.sh",
                "scripts/push-gate.sh",
                "scripts/quality-scan.sh",
                "scripts/run-tests.sh",
                "scripts/shellcheck-run.sh",
                "templates/ci/anchor-check.ci.sh",
                "templates/ci/artifact-gate.ci.sh",
            ],
            names,
        )

    def test_an_empty_scope_is_never_a_pass(self):
        """KA-G-017: a run that verifies nothing is not a clean run. The scan
        itself reports its scope, and a scope of zero is a failure -- the
        shape check-all.sh and conformance-run.sh already model for their own
        no-scope states."""
        files = scanned_files()
        self.assertGreater(
            len(files), 0,
            "the portability scan enumerated ZERO files -- that is a broken "
            "scope, not a clean tree",
        )
        self.assertEqual(30, len(files))


class KnownFindingsMatchTheCurrentScanTest(unittest.TestCase):
    def test_the_current_scan_equals_known_findings_exactly(self):
        """Set equality, not a count: neither a NEW unaccounted finding nor a
        STALE entry left behind after a repair passes silently. See
        KNOWN_FINDINGS' own comment for what each of the nine is and why it is
        reported rather than fixed in this round."""
        current = {f.key() for f in scan_tree()}
        self.assertEqual(  # pin: set portability-known-findings
            KNOWN_FINDINGS, current,
            "the portability scan drifted from its recorded baseline.\n"
            "  new:  {}\n  gone: {}".format(
                sorted(current - KNOWN_FINDINGS), sorted(KNOWN_FINDINGS - current),
            ),
        )


class ClassificationCountsTest(unittest.TestCase):
    def test_classification_counts(self):
        """Regression pin on the measured baseline: 29 scanned files, 11
        rules, and -- since R3 -- 0 unexempted findings with all 9 of
        WI-0130's sites moved into the marker-exempted set, still in the same
        2 files. A change in any of these means a script changed shape or
        this scanner's own logic did -- worth a deliberate look either way,
        not a silent drift.

        The exempted count is pinned HERE as well as in EXEMPTED_SITES on
        purpose: `0 findings` on its own is also what a scanner that stopped
        matching anything would report, and the two numbers cannot both be
        right if that happened.

        Bumped 29 -> 30, 03.09.2026 (CCP-1137): added scripts/push-gate.sh.
        Findings/exempted counts unchanged -- confirmed by
        KnownFindingsMatchTheCurrentScanTest passing unmodified, the same
        set-equality check that would have caught a new finding."""
        findings = scan_tree()
        exempted = exemptions_tree()
        self.assertEqual(30, len(scanned_files()))
        self.assertEqual(11, len(FLAG_RULES) + 1)
        self.assertEqual(0, len(findings))
        self.assertEqual(9, len(exempted))
        self.assertEqual(
            {"scripts/lib/frontmatter.sh", "scripts/log-cleanup.sh"},
            {path for path, _line, _rule, _cat in exempted},
        )


# --------------------------------------------------------------------------
# The exemption list, held to the same standard as the findings list (R3)
# --------------------------------------------------------------------------


def _strip_markers(text):
    """Removes every `# portability: exempt ...` marker WITHOUT removing its
    line -- the mutation has to change the exemption and nothing else, so
    line numbers stay put and the restored findings can be compared to
    EXEMPTED_SITES key for key."""
    out = []
    for line in text.split("\n"):
        m = EXEMPTION_MARKER_RE.search(line)
        out.append(line[:m.start()].rstrip() if m else line)
    return "\n".join(out)


def _move_marker(text, anchor, delta):
    """Moves the marker on the line carrying `anchor` by `delta` lines,
    without changing the line count. The structural mutation the R3 briefing
    asks for: not "delete the marker" (which changes its PRESENCE, and any
    exemption rule at all notices that) but "put it one line off", which
    only a rule with a real boundary notices. `delta` is signed because the
    two boundaries are not symmetric -- the sight reaches one line UP from
    the statement's first line and down only to its last."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if anchor not in line:
            continue
        m = EXEMPTION_MARKER_RE.search(line)
        if not m:
            continue
        lines[i] = line[:m.start()].rstrip()
        lines[i + delta] = lines[i + delta] + "  " + line[m.start():]
        return "\n".join(lines)
    raise AssertionError(f"no marker found on a line containing {anchor!r}")


class ExemptedSitesArePinnedTest(unittest.TestCase):
    """The exemption list cannot grow, shrink or SWAP silently. Set equality
    on `(path, line, rule, category)`, the same standard
    `KnownFindingsMatchTheCurrentScanTest` holds the findings list to -- an
    exemption nobody re-verifies is the drift this repo has already grown
    four skip lists' worth of."""

    def test_the_marker_exempted_sites_equal_the_registry(self):
        current = set(exemptions_tree())
        self.assertEqual(  # pin: set portability-exempted-sites
            EXEMPTED_SITES, current,
            "the portability EXEMPTION list drifted from its registry.\n"
            "  new:  {}\n  gone: {}".format(
                sorted(current - EXEMPTED_SITES), sorted(EXEMPTED_SITES - current),
            ),
        )

    def test_the_two_stat_sites_are_not_filed_as_portable_idioms(self):
        """The classification, not just the count. The `stat` chain works by
        an accident of operand shape and the `date` chains do not; filing all
        nine under one category would put a false statement in the shipped
        source, which is the exact register drift this round removes
        elsewhere."""
        by_category = {}
        for path, line, rule, category in exemptions_tree():
            by_category.setdefault(category, set()).add((path, line, rule))
        self.assertEqual(
            {("scripts/lib/frontmatter.sh", 259, "stat-f"),
             ("scripts/lib/frontmatter.sh", 260, "stat-c")},
            by_category.get("stat-f-guard-is-an-operand-accident"),
        )
        self.assertEqual(
            7, len(by_category.get("bsd-gnu-date-flags-are-mutually-invalid", ())))


class EveryMarkerNamesARegisteredCategoryTest(unittest.TestCase):
    """A marker's reason token has to resolve to a written-down reason. A free
    text token would satisfy the grammar and record nothing reviewable.

    WI-0133 T3: the two methods are the two directions of one `set` pin over
    `EXEMPTION_CATEGORIES` and therefore share one id. Same shape and same
    reasoning as test_platform_conditional_skip_budget.py:208/:217, whose
    own new/stale pair already carries two markers in the group `set` under
    the single id `registered-skip-decorator-files` -- spelled apart here
    because a marker written whole inside a docstring becomes a live,
    unregistered marker in the corpus this repository scans (find_markers is
    a line regex with no notion of Python strings). Split across two methods
    on purpose: one
    combined assertion would name only the direction that fired first."""

    def test_every_category_in_the_tree_is_registered(self):
        unregistered = sorted(
            (path, line, category)
            for path, line, _rule, category in exemptions_tree()
            if category not in EXEMPTION_CATEGORIES
        )
        self.assertEqual(  # pin: set portability-exemption-categories
            [], unregistered)

    def test_every_registered_category_is_used(self):
        """The other direction: a category nobody carries any more is a dead
        reason, and dead entries are how a register starts lying."""
        used = {category for _p, _l, _r, category in exemptions_tree()}
        self.assertEqual(  # pin: set portability-exemption-categories
            [], sorted(set(EXEMPTION_CATEGORIES) - used))

    def test_every_registered_reason_is_substantial(self):
        thin = [k for k, v in EXEMPTION_CATEGORIES.items() if len(v) < 200]
        self.assertEqual([], thin)


class NoStaleMarkerTest(unittest.TestCase):
    """A marker at a place that has no finding is itself a finding. Same
    accounting direction `NoStaleKnownFindingsTest` enforces for
    `test_absence_only_assertions.py`'s registry: without it, a repaired site
    leaves its marker behind, and the next construct that drifts onto that
    line arrives pre-excused."""

    def test_no_marker_in_the_tree_excuses_nothing(self):
        self.assertGreater(
            len(exemptions_tree()), 0,
            "no marker-exempted site found at all -- the staleness check "
            "below would pass vacuously; the scan stopped enumerating",
        )
        self.assertEqual([], stale_markers_tree())

    def test_a_marker_on_an_innocent_line_is_reported(self):
        """The red half, on a fixture: without it the assertion above is only
        the claim that `stale_markers` returns an empty list, which the
        function would also do if it were `return []`."""
        source = (
            "#!/usr/bin/env bash\n"
            "echo nothing portable here  # portability: exempt fixture-reason\n"
        )
        self.assertEqual(
            [("fixture.sh", 2, "fixture-reason")], stale_markers(source, "fixture.sh"))

    def test_a_marker_on_a_uname_guarded_construct_is_reported(self):
        """A marker that duplicates a `uname` branch excuses nothing either --
        it is dead the moment it is written, and a category tally that counted
        it would overstate what the marker list is holding up."""
        source = (
            "#!/usr/bin/env bash\n"
            "mtime_of() {\n"
            '    if [[ "$(uname)" == "Darwin" ]]; then\n'
            '        stat -f %m "$1"  # portability: exempt fixture-reason\n'
            "    else\n"
            '        stat -c %Y "$1"\n'
            "    fi\n"
            "}\n"
        )
        self.assertEqual([], scan_source(source, "fixture.sh"))
        self.assertEqual(
            [("fixture.sh", 4, "fixture-reason")], stale_markers(source, "fixture.sh"))


class RemovingTheMarkersRestoresTheFindingsTest(unittest.TestCase):
    """The other direction of the exemption proof, on the SHIPPED files rather
    than on a fixture. `ExemptedSitesArePinnedTest` shows the markers are
    there; this shows they are the only thing standing between the scan and
    nine findings. Without it, an exemption rule that excused everything --
    or a scanner that had quietly stopped matching `date` at all -- would look
    identical."""

    def test_stripping_every_marker_brings_all_nine_findings_back(self):
        restored = set()
        for f in scanned_files():
            label = f.relative_to(REPO_ROOT).as_posix()
            restored.update(
                x.key() for x in scan_source(_strip_markers(f.read_text()), label))
        self.assertEqual({(p, l, r) for p, l, r, _c in EXEMPTED_SITES}, restored)


class MarkerOnTheWrongLineDoesNotExemptTheShippedSiteTest(unittest.TestCase):
    """The structural mutation. Deleting a marker is the weak form -- it
    changes the marker's PRESENCE, and any rule at all notices that. Moving it
    one line down changes only its POSITION, so it shows where the boundary
    actually is: `marker_sight` is the logical line plus the line above, and
    the line BELOW the statement is outside it."""

    def _mutate(self, path, anchor, delta):
        text = (REPO_ROOT / path).read_text()
        mutated = _move_marker(text, anchor, delta)
        self.assertNotEqual(text, mutated, "the mutation did not apply")
        self.assertEqual(
            text.count("portability: exempt"),
            mutated.count("portability: exempt"),
            "the mutation removed a marker instead of moving it",
        )
        self.assertEqual(
            len(text.split("\n")), len(mutated.split("\n")),
            "the mutation changed the line count",
        )
        return sorted(f.key() for f in scan_source(mutated, path))

    def test_moving_the_stat_chain_marker_off_the_statement_restores_both(self):
        self.assertEqual(
            [("scripts/lib/frontmatter.sh", 259, "stat-f"),
             ("scripts/lib/frontmatter.sh", 260, "stat-c")],
            self._mutate("scripts/lib/frontmatter.sh", "|| return 0", +1),
        )

    def test_moving_the_cutoff_date_marker_one_line_up_restores_both(self):
        """The UPPER boundary. This marker sits on the comment line directly
        above its construct, so the mutation that tests the boundary is a move
        AWAY from the construct, not towards it -- one line further up is two
        lines above the construct, and out of sight."""
        self.assertEqual(
            [("scripts/log-cleanup.sh", 69, "date-d"),
             ("scripts/log-cleanup.sh", 69, "date-v")],
            self._mutate("scripts/log-cleanup.sh", "# Current date as reference", -1),
        )

    def test_moving_the_gnu_date_marker_one_line_down_restores_it(self):
        self.assertEqual(
            [("scripts/lib/frontmatter.sh", 243, "date-d")],
            self._mutate("scripts/lib/frontmatter.sh", 'date -u -d "$iso"', +1),
        )


class MarkerTextIsReadOffLiveSourceTest(unittest.TestCase):
    """Code review R3, Important 1 and 2: both the marker search and the
    splice detection ran on the RAW text, while the constructs they are
    matched against are found in text with heredoc bodies blanked. Two
    consequences, neither of them theoretical:

      * a marker-shaped line inside a heredoc BODY -- a script writing a
        script -- can never be in any construct's sight, so `stale_markers`
        reported it as dead on every run. A staleness detector with a
        built-in false positive is not one.
      * a COMMENT ending in a backslash is not a line continuation in the
        shell, but `_splices` read it as one, silently extending the sight
        upwards past it. A marker above such a comment exempted a construct
        below it -- the sight widening quietly, which is exactly what the
        rest of this round exists to prevent.

    Fixed by giving each question the right basis: markers are searched in
    heredoc-blanked text (comments intact, because the marker IS a comment),
    splices in heredoc-AND-comment-blanked text (escapes intact, because the
    continuation IS an escape). Both were already computed."""

    def test_a_marker_inside_a_heredoc_body_is_not_a_stale_marker(self):
        source = (
            "#!/usr/bin/env bash\n"
            "cat > out.sh <<'EOF'\n"
            "# portability: exempt fixture-reason\n"
            "EOF\n"
        )
        self.assertEqual([], stale_markers(source, "fixture.sh"))

    def test_a_marker_inside_a_heredoc_body_does_not_exempt_a_construct(self):
        source = (
            "#!/usr/bin/env bash\n"
            "cat > out.sh <<'EOF'\n"
            "# portability: exempt fixture-reason\n"
            "EOF\n"
            'stat -c %Y "$1"\n'
        )
        self.assertEqual(
            [(5, "stat-c")], [(f.line, f.rule) for f in _scan_text(source)])

    def test_a_comment_ending_in_a_backslash_does_not_extend_the_sight(self):
        """`# ... \\` does NOT continue in the shell -- a comment runs to the
        end of the line, backslash or not. Reading it as a splice pulled the
        marker on line 1 into line 3's sight."""
        source = (
            "# portability: exempt fixture-reason\n"
            "# an ordinary comment that happens to end in a backslash \\\n"
            'stat -c %Y "$1"\n'
        )
        self.assertEqual(
            [(3, "stat-c")], [(f.line, f.rule) for f in _scan_text(source)])

    def test_a_comment_backslash_does_not_keep_a_stale_marker_alive(self):
        """The same wrong basis inside `stale_markers` rather than inside the
        exemption: with the raw text as the splice basis, line 2's comment
        pulls line 1 into line 3's sight, and the dead marker on line 1 looks
        used. Added after a mutation of `stale_markers`' own sight call
        SURVIVED the rest of this class -- the two callers need their own
        discriminator each."""
        source = (
            "# portability: exempt fixture-reason\n"
            "# an ordinary comment that happens to end in a backslash \\\n"
            'stat -c %Y "$1"\n'
        )
        self.assertEqual(
            [("fixture.sh", 1, "fixture-reason")], stale_markers(source, "fixture.sh"))

    def test_a_real_continuation_still_extends_the_sight(self):
        """The other direction, so the fix cannot be "never splice". Same
        chain as MarkerCoversTheWholeContinuedStatementTest, kept here as the
        positive control for the comment-blanked splice basis."""
        source = (
            "#!/usr/bin/env bash\n"
            "mode=\"$(stat -f '%Lp' \"$1\" 2>/dev/null)\" \\\n"
            "    || mode=\"$(stat -c '%a' \"$1\" 2>/dev/null)\" \\\n"
            "    || return 0  # portability: exempt fixture-reason\n"
        )
        self.assertEqual([], _scan_text(source))


class EveryRuleNamesItsDivergenceTest(unittest.TestCase):
    """The briefing's own requirement, held mechanically: a rule without a
    stated divergence is a regex somebody added, not a documented finding
    class. `silent_on` is allowed to be None (meaning: loud on both wrong
    platforms) but `divergence` never is."""

    def test_every_rule_carries_a_divergence_description(self):
        empty = [r.name for r in FLAG_RULES if not r.divergence or len(r.divergence) < 20]
        self.assertEqual([], empty)

    def test_every_rule_name_is_unique(self):
        """The `mktemp` rule is deliberately not a `PortabilityRule` and so has
        no `divergence` field for the test above to check: it is not a
        command/flag pair but a template-SHAPE test, and its account lives in
        `_mktemp_hits`' own docstring. The asymmetry is intentional; the name
        is still pinned here so the two registries cannot collide."""
        names = [r.name for r in FLAG_RULES] + [MKTEMP_RULE_NAME]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
