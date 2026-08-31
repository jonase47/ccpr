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
  2. an explicit marker comment `# portability: exempt <reason>` on the
     construct's own line or the line directly above it, mirroring the
     `# exit-status: exempt <reason>` idiom this repository already carries in
     `instinct-check.sh`, `memory-sync.sh`, `shellcheck-run.sh` and others.

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
  * Whether a flagged site is actually BROKEN. A finding is a SHAPE. Both
    `frontmatter.sh` sites in `KNOWN_FINDINGS` below happen to work today, for
    a reason the scanner cannot check -- see that registry's own note.

## Findings on the current tree: surfaced, not fixed

This work item's write boundary is this file. The shipped shell scripts are
out of it, so the nine findings the scan produces against the current tree are
recorded in `KNOWN_FINDINGS` and reported, not repaired -- each one needs its
own red proof and its own round. `KnownFindingsMatchTheCurrentScanTest` asserts
SET EQUALITY, so neither a new unaccounted finding nor a stale entry left
behind after a repair passes silently.
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

EXEMPTION_MARKER = "portability: exempt"

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


def _has_exemption_marker(raw_lines, idx):
    """`# portability: exempt <reason>` on the construct's own line or the one
    directly above it. Read off the RAW lines on purpose -- the marker IS a
    comment, and every masked variant has already blanked it."""
    for probe in (idx, idx - 1):
        if 0 <= probe < len(raw_lines) and EXEMPTION_MARKER in raw_lines[probe]:
            return True
    return False


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


def scan_source(text, path_label):
    """Scans one shell script's SOURCE TEXT (so a historical revision read via
    `git show` is scanned by exactly the same code path as a file on disk).
    Returns a list of PortabilityFinding."""
    body_blanked = _blank_heredocs(text)
    masked = _mask_non_live(body_blanked)
    comment_stripped = _strip_comments_only(body_blanked)
    masked_lines = masked.split("\n")
    stripped_lines = comment_stripped.split("\n")
    raw_lines = text.split("\n")
    ranges = function_ranges(masked_lines)

    findings = []
    for idx, masked_line in enumerate(masked_lines):
        hits = [rule.name for rule in FLAG_RULES if rule.matches(masked_line)]
        if _mktemp_hits(stripped_lines[idx], masked_line):
            hits.append(MKTEMP_RULE_NAME)
        if not hits:
            continue
        if _has_exemption_marker(raw_lines, idx):
            continue
        if any("uname" in masked_lines[k]
               for k in sight_range(masked_lines, ranges, idx)):
            continue
        for name in hits:
            findings.append(PortabilityFinding(path_label, idx + 1, name, raw_lines[idx]))
    return findings


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


def scan_tree(repo_root=REPO_ROOT):
    findings = []
    for f in scanned_files(repo_root):
        label = f.relative_to(repo_root).as_posix()
        findings.extend(scan_source(f.read_text(), label))
    return findings


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


# Findings on the CURRENT tree, reported rather than repaired: this work
# item's write boundary is this test module, and every shipped shell script is
# outside it. Keyed (path, line, rule), the same way
# test_heredoc_interpolation_scan.py's own registry is.
#
# All nine are `||` fallback chains rather than `uname` branches, which is the
# single reason they are flagged -- see the module docstring on why a `||`
# chain is not accepted as a guard. Two notes the scanner itself cannot make:
#
#   * scripts/lib/frontmatter.sh:259-260 (`stat -f '%Lp' || stat -c '%a'`)
#     happens to WORK on both platforms, because GNU `stat -f '%Lp' <file>`
#     reads the format as a second, nonexistent file operand and exits 1, so
#     the chain does fall through. That is luck of the exit status, not a
#     guard: the identical shape at log-cleanup.sh:70 pre-fix sat behind a
#     pipe, where the exit status belonged to `head` and the fallback could
#     never fire. Recommended repair is a one-line `# portability: exempt`
#     marker naming that reasoning, not a code change.
#   * scripts/log-cleanup.sh:69 and :104-105 and scripts/lib/frontmatter.sh:
#     236-237,243 are BSD-first-then-GNU `date` chains where the BSD form does
#     fail loudly on GNU, so the chain works. Same recommendation.
#
# Each needs its own round and its own red proof. Filed as findings here, not
# fixed here.
KNOWN_FINDINGS = {
    # WI-0131 line shift: the CRLF fix inserted a 43-line header block
    # ABOVE all five sites; none of the five lines was itself touched.
    # Proven by byte-comparing HEAD:<old line> against <new line> for
    # each (all five identical, uniform delta +43) and by the diff
    # carrying 13 removed lines, none of them a `date`/`stat` call --
    # a count of 5-before/5-after alone cannot tell a shift from
    # "one gone, one new".
    ("scripts/lib/frontmatter.sh", 236, "date-j"),
    ("scripts/lib/frontmatter.sh", 237, "date-j"),
    ("scripts/lib/frontmatter.sh", 243, "date-d"),
    ("scripts/lib/frontmatter.sh", 259, "stat-f"),
    ("scripts/lib/frontmatter.sh", 260, "stat-c"),
    ("scripts/log-cleanup.sh", 69, "date-d"),
    ("scripts/log-cleanup.sh", 69, "date-v"),
    ("scripts/log-cleanup.sh", 104, "date-j"),
    ("scripts/log-cleanup.sh", 105, "date-d"),
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
        current = _scan_text(
            (SCRIPTS_DIR / "run-tests.sh").read_text(), "scripts/run-tests.sh"
        )
        self.assertEqual([], [f for f in current if f.rule == MKTEMP_RULE_NAME])


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
    failing first."""

    def test_scanned_files_cover_the_shipped_scope(self):
        names = sorted(f.relative_to(REPO_ROOT).as_posix() for f in scanned_files())
        self.assertEqual(
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
        self.assertEqual(29, len(files))


class KnownFindingsMatchTheCurrentScanTest(unittest.TestCase):
    def test_the_current_scan_equals_known_findings_exactly(self):
        """Set equality, not a count: neither a NEW unaccounted finding nor a
        STALE entry left behind after a repair passes silently. See
        KNOWN_FINDINGS' own comment for what each of the nine is and why it is
        reported rather than fixed in this round."""
        current = {f.key() for f in scan_tree()}
        self.assertEqual(
            KNOWN_FINDINGS, current,
            "the portability scan drifted from its recorded baseline.\n"
            "  new:  {}\n  gone: {}".format(
                sorted(current - KNOWN_FINDINGS), sorted(KNOWN_FINDINGS - current),
            ),
        )


class ClassificationCountsTest(unittest.TestCase):
    def test_classification_counts(self):
        """Regression pin on the measured baseline (WI-0130, 30.08.2026): 29
        scanned files, 11 rules, 9 findings across 2 files. A change in any of
        these means a script changed shape or this scanner's own logic did --
        worth a deliberate look either way, not a silent drift."""
        findings = scan_tree()
        self.assertEqual(29, len(scanned_files()))
        self.assertEqual(11, len(FLAG_RULES) + 1)
        self.assertEqual(9, len(findings))
        self.assertEqual(
            {"scripts/lib/frontmatter.sh", "scripts/log-cleanup.sh"},
            {f.path_label for f in findings},
        )


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
