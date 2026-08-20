r"""test_external_tool_exit_status.py -- WI-0054: pins every external-tool
invocation (grep, awk, sed, python3, git) in the shipped shell scripts
(scripts/*.sh, scripts/lib/*.sh) to a CONSUMED exit status.

## Why this exists

Three prior rounds closed one recurring defect by READING the source and
enumerating call sites by eye: WI-0051 (20 sites in gate_scan_file), WI-0053
(2 more that inventory had missed, plus a third the sweep then found on its
own: is_text()'s own classifier grep). Each pass kept missing the call that
does not look like the others -- `grep -q` writes nothing, `|| [ ! -s "$1" ]`
is not the `|| true` the eye scans for, and a caller silently discarding a
callee's already-correct return is invisible at the callee. This module
replaces the reading with a check: it re-enumerates every invocation on every
run and asserts, in the POSITIVE form (mirroring
test_handover_epilogue_bullet.py), that each one is either checked or
deliberately exempted -- never merely "not `|| true`", which would pass
vacuously on a file that never had the shape at all. A NEW invocation added
to any of these 15 files tomorrow starts unclassified and fails this test
until a human either wires up a check or adds a marked, reasoned exemption.

## How an invocation is found (the enumeration)

`scan_file()` is a small, deliberately non-general shell scanner -- not a
full parser -- built in three passes over each file's raw text:

1. `_blank_heredocs()` blanks heredoc BODIES (`<<EOF` / `<<'PY'` / `<<-TAG`)
   to spaces, keeping line counts intact. A heredoc body is never parsed as
   shell commands regardless of quoting, so nothing inside one is scanned --
   this is also what keeps a Python string literal like `".git"` inside a
   `python3 <<'PYEOF'` block from being misread as a `git` invocation.
2. `_mask_non_live()` walks the (heredoc-blanked) text character by character
   tracking single-quote, double-quote and comment state, and blanks
   everything inside them to spaces -- EXCEPT the inside of a `$(...)`
   command substitution, which is live shell code even when the enclosing
   context is double-quoted (and gets its own independent quote state once
   entered). It also tracks a parallel `live` array so a bare-word regex
   search never matches a tool name that only exists inside a string.
3. `TOOL_RE` (`\b(grep|awk|sed|python3|git)\b`) is matched against the masked
   text, and each match is additionally required to be a whole, unquoted
   SHELL WORD (bounded by whitespace/operators on both sides -- `\b` alone
   would wrongly match "git" inside an unquoted "git.txt" filename argument).

What this step deliberately does NOT count as an invocation:
  * a tool name mentioned in a comment or inside a quoted string/heredoc body
    (a Python string literal, an error message, a `-- see the grep manual`
    comment);
  * a tool name used as an ARGUMENT to another command rather than being
    executed itself -- `command -v git`, `type python3` -- detected by
    `_is_valid_command_start()`: is there a real separator (or an if/while/
    until/elif/`!`/assignment-prefix chain) directly before this word, or is
    it glued to a preceding plain word with only whitespace, meaning it is
    that word's own argument?
  * a tool name passed as a literal ARGUMENT STRING to a wrapper function
    that execs it internally via `"$@"` -- e.g. `memory-sync.sh`'s
    `git_or_die "git fetch" git -C "$CLONE" fetch ...`: syntactically the
    second "git" is just another word in `git_or_die`'s own argument list;
    the real invocation happens inside `git_or_die`'s body (`out="$("$@" ...)"
    || rc=$?`), which IS itself checked -- verified by reading, not by this
    scan (see "What this check cannot see" below).

## What counts as "consumed"

Per invocation, `_classify()` walks its own top-level statement (through
however many pipeline stages and VAR=val prefixes precede it, transparently
crossing `|`/`&&`/`||`/`!`, since a pipeline or a compound list is one
testable unit under this file's `set -o pipefail`) and assigns exactly one of:

  * **checked-condition**  -- it is (part of) the tested command of an
    `if`/`elif`/`while`/`until`.
  * **checked-captured**   -- its forward statement window contains `$?` or
    `|| return` (propagates the failure upward).
  * **checked-chain**      -- its forward window contains a real `&&`/`||`
    branch that is not just `|| true`.
  * **discard-needs-exemption** -- its forward window contains `|| true`:
    the defect shape this whole work-item chain exists to close. Needs a
    marked, reasoned exemption.
  * **bare-needs-exemption** -- none of the above: no if/while, no capture,
    no real chain, no `|| true` either. Relying on this file's own
    `set -euo pipefail` to abort is sometimes the CORRECT, decided response
    (sed/awk/python3/git, unlike grep, have no "1 = nothing matched, not an
    error" exit convention to confuse with a crash -- see the comment already
    shipped at discipline_gate.sh's tr/sed filter), and sometimes it silently
    over-aborts on an expected empty result (see bootstrap.sh:206 below).
    Either way it needs a human decision, recorded as an exemption.

Edge cases decided along the way:
  * a single `|` is transparent for BACKWARD if/while detection (`if a | b;
    then` tests the whole pipeline, and under pipefail that covers `a` too),
    but `;` and a real newline are hard stops -- an `if` before a `;` does
    not govern whatever comes after it;
  * `&&`/`||` are ALSO backward-transparent (`if a && b; then` governs `b`
    the same way `if a | b; then` does), and so is a leading `!` negation;
  * a real, unescaped newline is a hard separator, but a backslash-continued
    newline and a newline still inside an open quote are NOT -- both are
    folded to a space before any boundary search runs, so a statement that
    spans physical lines (a continued backslash-terminated pipeline, a multi-line
    `python3 -c "..."` argument) is still scanned as the one statement it is;
  * `<(...)` process substitution content is live code (scanned for its own
    invocations) but its exit status is fundamentally unobservable from the
    `while read` loop consuming it -- see `proc-subst-unobservable` below.

## How the exemption list is keyed

Every invocation classified `*-needs-exemption` must carry a trailing marker
comment, `# exit-status: exempt <category>`, ANYWHERE in the physical line
range from the invocation's own line through the line its statement's
forward window ends on (a statement that spans lines via backslash
continuation cannot carry the marker on a continuation line without eating it,
so it goes on the line the statement actually finishes on -- see
artifact-gate.sh:167-168, instinct-check.sh:77-78, run-tests.sh:54-57).
This is keyed on the marker's own source position, the same shape as
discipline_gate.sh's `# gate-pattern-source` marker (visible, greppable,
immune to line-number drift) -- NOT on a line number recorded elsewhere, and
NOT on a bare file+substring pair in this test, which would itself drift the
moment the invocation's own text changes.

`<category>` must be a key in `EXEMPTION_REASONS` below, one shared reason
per category rather than one per site: most of the ~80 exemption sites are
routine (a HANDOVER.md field extraction degrading to blank output, a git
overlay-clone refresh already designed to tolerate failure), and repeating a
bespoke reason at each one would train a reader to stop reading the list --
the two sites that are NOT routine (`known-risk-not-yet-fixed`) are the ones
meant to stand out.

## What this check cannot see

It enumerates INVOCATIONS found in the shell text of these 15 files. It
CANNOT see a status swallowed several frames up a call chain -- that is
exactly WI-0053's site (a): `gate_path_deny_index` checked its own grep
correctly, but both of its callers discarded the function's return with
`|| true`. A per-invocation scan would show that site as clean; only reading
(or a separate, deliberate check on function-return consumption at call
sites) catches it. A green run of this test is not a claim that no status is
swallowed anywhere in these files -- only that every DIRECT invocation this
scanner can see is either checked or has a recorded, reasoned decision.

Two more, narrower blind spots, both individually verified by reading rather
than by this scan:
  * `command -v <tool>` / `type <tool>`: the tool name is an ARGUMENT, not an
    invocation, and is correctly excluded rather than silently miscounted.
  * `git_or_die "label" git ...` (memory-sync.sh): the literal "git" is an
    argument to `git_or_die`, invisible to this scanner; `git_or_die` itself
    captures and checks its `"$@"` invocation's status via `out="$("$@" ...)"
    || rc=$?` -- read and confirmed, not something this scan can verify on
    its own behalf.

This test extends to plain shell FUNCTIONS whose tail command's exit status
becomes the function's own return value ONLY as a documented exemption
category (`propagates-as-function-return`, e.g. `_gate_hits`, `fm_extract`)
-- it does not attempt to trace whether every CALLER of such a function then
checks it. That would require call-graph analysis this scanner does not do;
each such site is a recorded, individually-reasoned decision, not a proof.

## Findings surfaced, not fixed (WI-0054 scope: a test, not a behaviour change)

Two `known-risk-not-yet-fixed` exemptions record real, unfixed risk found
while building this check (reported here rather than silently exempted like
the routine sites, and NOT fixed -- a behaviour change is a separate item):
  * bootstrap.sh:206 -- `grep -E '^### \[' "${INSTINCTS_FILE}" | head -5 |
    while read ...` is completely bare. If the file has zero matching
    headings (a normal, expected state, e.g. a fresh instincts.md), grep
    exits 1 and this whole pipeline aborts bootstrap.sh under
    `set -o pipefail` -- an over-abort on an empty-but-valid result, not a
    swallowed status, but still the wrong "decided" outcome.
  * log-cleanup.sh:141-155 -- the trimmed log is written to a tmpfile by a
    bare `python3 -c "..." 2>/dev/null`, and `mv "${tmpfile}" "${filepath}"`
    on line 155 runs UNCONDITIONALLY afterward. If python3 crashes before
    writing anything, `mv` still succeeds, silently replacing the log with
    an empty file -- a real data-loss shape, not just a missed check.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

TOOL_NAMES = ("grep", "awk", "sed", "python3", "git")
TOOL_RE = re.compile(r"\b(" + "|".join(TOOL_NAMES) + r")\b")
WORD_BOUNDARY_CHARS = set(" \t\n;|&()<>{}")
KEYWORDS_COND = {"if", "elif", "while", "until"}
KEYWORDS_OTHER = {"then", "else", "do", "time", "{"}
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*$")

HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

MARKER_RE = re.compile(r"#\s*exit-status:\s*exempt\s+([A-Za-z0-9_-]+)")

# One shared reason per category (see the module docstring, "How the
# exemption list is keyed"): grouping keeps the routine sites from drowning
# out the two that are a genuine, recorded finding.
EXEMPTION_REASONS = {
    "set-e-sufficient": (
        "sed/awk/python3/git (unlike grep) have no '1 = nothing matched, "
        "not an error' exit convention to confuse with a crash; an "
        "unguarded failure already aborts the script under this file's "
        "`set -euo pipefail`, which is the correct, decided response."
    ),
    "grep-empty-is-valid": (
        "grep exits 1 when it matches nothing, and here that is a normal, "
        "already-handled empty result (a zero count, an empty ID list), "
        "not a crash signal; the discard is deliberate and the caller "
        "treats the empty/zero fallback as valid input."
    ),
    "downstream-checks-result": (
        "the raw exit status is not inspected, but the very next line "
        "tests the OUTPUT for emptiness or shape and already branches on "
        "a missing or malformed result -- the failure is handled through "
        "its output, not its exit code."
    ),
    "doc-field-extraction": (
        "extracts one OPTIONAL section from a project doc (HANDOVER.md, "
        "CLAUDE.md, PROJECT_PLAN.md) for a generated dashboard/summary; a "
        "missing or malformed section degrading to blank output is the "
        "by-design fallback of this generator, not a defect."
    ),
    "best-effort-status-display": (
        "produces a cosmetic status/log/file-listing for a human-facing "
        "dashboard or startup summary; a failure degrades the display, it "
        "does not corrupt any state."
    ),
    "propagates-as-function-return": (
        "the tail command of a small shell helper (_gate_hits, "
        "fm_has/fm_extract/fm_field/fm_list, the discipline_gate.sh "
        "unicode helpers); the function's own exit status IS this "
        "invocation's exit status by design, and every caller captures or "
        "checks the FUNCTION's return -- documented pattern, see "
        "_gate_hits's own comment in discipline_gate.sh."
    ),
    "internal-record-parsing": (
        "awk parsing this same script's own well-formed, tab-delimited "
        "internal record format (_gate_emit's output), not external or "
        "adversarial input -- no crash-vs-empty ambiguity to lose."
    ),
    "git-cache-refresh": (
        "part of memory-sync.sh's overlay-clone maintenance sequence, "
        "already explicitly `|| true`'d by design because the following "
        "statement re-derives or re-establishes the needed state "
        "regardless -- see the shipped comments at ensure_clone()."
    ),
    "test-runner-output-capture": (
        "the underlying test runner (pytest/npm) exits nonzero when tests "
        "FAIL, which is the normal, expected outcome this wrapper script "
        "exists to capture and report as JSON, not a crash signal; both "
        "the JSON-report and raw-output fallback paths already handle an "
        "unreadable or malformed result via their own try/except."
    ),
    "proc-subst-unobservable": (
        "inside a `<(...)` process substitution: bash does not expose "
        "this command's exit status to the `while` loop reading from it "
        "at all -- there is no syntax available here to check it; the "
        "loop degrades to zero iterations, the same tolerated shape as a "
        "missing input file."
    ),
    "optional-config-read": (
        "reads an OPTIONAL external config file (memory-sync.json) that "
        "may not exist or may be malformed; a missing/unreadable config "
        "degrades to the caller's own defaults, which is the intended "
        "fallback, not a defect."
    ),
    "known-risk-not-yet-fixed": (
        "identified while building this check: a real, unfixed risk (see "
        "the module docstring, 'Findings surfaced, not fixed'); left as-is "
        "because this item's scope is a test, not a behaviour change -- "
        "reported to the PO rather than silently absorbed."
    ),
}


# --------------------------------------------------------------------------
# The scanner
# --------------------------------------------------------------------------


def _blank_heredocs(text):
    lines = text.split("\n")
    out = list(lines)
    n = len(lines)
    i = 0
    while i < n:
        m = HEREDOC_RE.search(lines[i])
        if m:
            delim = m.group(2)
            strip_tabs = lines[i][m.start() : m.start() + 3].startswith("<<-")
            j = i + 1
            while j < n:
                probe = lines[j].lstrip("\t") if strip_tabs else lines[j]
                if probe == delim:
                    break
                out[j] = ""
                j += 1
            i = j
        i += 1
    return "\n".join(out)


def _mask_non_live(text):
    """Returns (masked, live). `masked` blanks quoted/comment content to
    spaces (newlines kept verbatim so line numbers stay accurate). `live` is
    a parallel bool array: False for anything inside quotes, inside a
    comment body, or part of a backslash-escape/continuation pair -- i.e.
    NOT real, unquoted shell syntax."""
    n = len(text)
    out = list(text)
    live = [True] * n
    i = 0
    in_single = False
    in_double = False
    stack = []
    while i < n:
        c = text[i]
        if in_single:
            live[i] = False
            if c == "'":
                in_single = False
            if c != "\n":
                out[i] = " "
            i += 1
            continue
        if in_double:
            if c == "\\" and i + 1 < n:
                live[i] = False
                live[i + 1] = False
                out[i] = " "
                if text[i + 1] != "\n":
                    out[i + 1] = " "
                i += 2
                continue
            if c == '"':
                live[i] = False
                out[i] = " "
                in_double = False
                i += 1
                continue
            if c == "$" and i + 1 < n and text[i + 1] == "(":
                # live stays True for these two chars: nested command
                # substitution is live shell code even inside a "..." arg.
                stack.append(True)
                in_double = False
                i += 2
                continue
            live[i] = False
            if c != "\n":
                out[i] = " "
            i += 1
            continue
        # NORMAL (unquoted, live) state
        if c == "\\" and i + 1 < n:
            live[i] = False
            live[i + 1] = False
            out[i] = " "
            if text[i + 1] != "\n":
                out[i + 1] = " "
            i += 2
            continue
        if c == "'":
            in_single = True
            live[i] = False
            out[i] = " "
            i += 1
            continue
        if c == '"':
            in_double = True
            live[i] = False
            out[i] = " "
            i += 1
            continue
        if c == "#":
            prev = text[i - 1] if i > 0 else "\n"
            if prev.isspace() or prev in "(;|&{":
                j = i
                while j < n and text[j] != "\n":
                    out[j] = " "
                    live[j] = False
                    j += 1
                i = j
                continue
            i += 1
            continue
        if c == "<" and i + 1 < n and text[i + 1] == "(":
            stack.append(False)
            i += 2
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
    return "".join(out), live


def _build_scan_text(masked, live):
    """`masked` with every non-live '\\n' turned into a space, so statement-
    boundary scanning never treats a newline embedded in a still-open quote
    or a line-continuation as a real separator."""
    chars = list(masked)
    for i, c in enumerate(chars):
        if c == "\n" and not live[i]:
            chars[i] = " "
    return "".join(chars)


def _compute_depth(scan_text):
    """depth[i] = paren/proc-subst nesting depth BEFORE processing char i."""
    n = len(scan_text)
    depth = [0] * (n + 1)
    d = 0
    for i, c in enumerate(scan_text):
        depth[i] = d
        if c == "(":
            d += 1
        elif c == ")":
            d = max(0, d - 1)
    depth[n] = d
    return depth


def _line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def _skip_assignments_back(scan_text, pos):
    i = pos
    while True:
        j = i
        while j > 0 and scan_text[j - 1] in " \t":
            j -= 1
        if j == 0:
            return i
        prev = scan_text[j - 1]
        if prev in "\n;|&(":
            return i
        k = j
        while k > 0 and scan_text[k - 1] not in " \t\n;|&()":
            k -= 1
        word = scan_text[k:j]
        if word and ASSIGN_RE.match(word):
            i = k
            continue
        return i


def _is_valid_command_start(scan_text, pos):
    """Is `pos` the start of a genuine simple command -- right after a
    separator/keyword/assignment-chain/start-of-text -- or merely an
    ARGUMENT WORD to a preceding command (e.g. the "git" in
    "command -v git", which is never itself executed)?"""
    pos = _skip_assignments_back(scan_text, pos)
    j = pos
    while j > 0 and scan_text[j - 1] in " \t":
        j -= 1
    if j == 0:
        return True
    prev = scan_text[j - 1]
    if prev == "\n" or prev in ";|&(":
        return True
    k = j
    while k > 0 and scan_text[k - 1] not in " \t\n;|&()":
        k -= 1
    word = scan_text[k:j]
    if not word:
        return True
    if word in KEYWORDS_COND or word in KEYWORDS_OTHER or word == "!":
        return True
    return False


def _governing_reason(scan_text, start):
    """Walks backward past every word of every pipeline stage -- arguments,
    the command name, VAR=val prefixes, all transparently skippable -- until
    a true statement boundary (';', real newline, '(', start-of-text) or,
    without crossing one, if/while/until/elif turns up as one of the words
    skipped (always a pipeline/list's OWN first word, so finding it mid-walk
    means it governs everything skipped so far). '|', '&&', '||' and a
    leading '!' are all backward-transparent: a pipeline or a negated/
    chained test is one unit an enclosing if/while governs as a whole."""
    i = start
    while True:
        j = i
        while j > 0 and scan_text[j - 1] in " \t":
            j -= 1
        if j == 0:
            return "start"
        prev = scan_text[j - 1]
        if prev == "\n" or prev == ";" or prev == "(":
            return "operator"
        if prev == "|":
            i = j - 2 if (j >= 2 and scan_text[j - 2] == "|") else j - 1
            continue
        if prev == "&":
            if j >= 2 and scan_text[j - 2] == "&":
                i = j - 2
                continue
            return "operator"  # lone '&' (background) -- not observed here
        k = j
        while k > 0 and scan_text[k - 1] not in " \t\n;|&()":
            k -= 1
        word = scan_text[k:j]
        if not word:
            return "operator"
        if word == "!":
            i = k
            continue
        if word in KEYWORDS_COND:
            return "if-cond"
        if word in KEYWORDS_OTHER:
            return "other-keyword"
        i = k  # ordinary word (argument, command name, or VAR=val) -- skip


def _backward_reason(scan_text, start):
    if not _is_valid_command_start(scan_text, start):
        return "not-command"
    return _governing_reason(scan_text, start)


_RE_OR_TRUE = re.compile(r"\|\|\s*true\b")
_RE_QMARK = re.compile(r"\$\?")
_RE_OR_RETURN = re.compile(r"\|\|\s*return\b")
_RE_REAL_CHAIN = re.compile(r"(\&\&|\|\|)\s*(?!true\b)\S")


def _classify(scan_text, start, end, depth):
    """Returns (disposition, window_end_index). window_end_index is where
    the forward statement-boundary search stopped -- used only to bound
    where an exemption marker is allowed to sit."""
    reason = _backward_reason(scan_text, start)
    if reason == "if-cond":
        return "checked-condition", end
    if reason == "not-command":
        return None, end
    n = len(scan_text)
    i = end
    while i < n:
        c = scan_text[i]
        if depth[i] == 0 and c in ";\n":
            break
        i += 1
    window = scan_text[end:i]
    if _RE_OR_TRUE.search(window):
        return "discard-needs-exemption", i
    if _RE_QMARK.search(window) or _RE_OR_RETURN.search(window):
        return "checked-captured", i
    if _RE_REAL_CHAIN.search(window):
        return "checked-chain", i
    return "bare-needs-exemption", i


NEEDS_EXEMPTION = ("discard-needs-exemption", "bare-needs-exemption")


class Invocation:
    __slots__ = ("path", "tool", "line", "end_line", "disposition")

    def __init__(self, path, tool, line, end_line, disposition):
        self.path = path
        self.tool = tool
        self.line = line
        self.end_line = end_line
        self.disposition = disposition

    def __repr__(self):
        return f"{self.path.name}:{self.line}:{self.tool}:{self.disposition}"


def scan_file(path):
    """Enumerates every grep/awk/sed/python3/git invocation in `path` and
    classifies each one. See the module docstring for the full method."""
    text = path.read_text()
    text = _blank_heredocs(text)
    masked, live = _mask_non_live(text)
    scan_text = _build_scan_text(masked, live)
    depth = _compute_depth(scan_text)
    results = []
    for m in TOOL_RE.finditer(masked):
        start, end = m.start(), m.end()
        before_ok = start == 0 or masked[start - 1] in WORD_BOUNDARY_CHARS
        after_ok = end == len(masked) or masked[end] in WORD_BOUNDARY_CHARS
        if not (before_ok and after_ok):
            continue
        disposition, window_end = _classify(scan_text, start, end, depth)
        if disposition is None:
            continue
        line = _line_of(text, start)
        end_line = _line_of(text, max(end, window_end - 1))
        results.append(Invocation(path, m.group(1), line, end_line, disposition))
    return results


def scan_tree(scripts_dir=SCRIPTS_DIR):
    files = sorted(scripts_dir.glob("*.sh")) + sorted((scripts_dir / "lib").glob("*.sh"))
    invocations = []
    for f in files:
        invocations.extend(scan_file(f))
    return invocations


def find_exemption(path, line, end_line):
    """Searches the marker regex on every physical line from `line` through
    `end_line` (inclusive) -- covers both same-line markers and the small
    number of `\\`-continued statements where the marker has to sit on the
    line the statement actually finishes on. Returns the category name, or
    None."""
    all_lines = path.read_text().split("\n")
    for ln in range(line, end_line + 1):
        if ln < 1 or ln > len(all_lines):
            continue
        m = MARKER_RE.search(all_lines[ln - 1])
        if m:
            return m.group(1)
    return None


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


class ExternalToolExitStatusTest(unittest.TestCase):
    def test_every_invocation_is_checked_or_exempted(self):
        """Positive-form pin (mirrors test_handover_epilogue_bullet.py): every
        grep/awk/sed/python3/git invocation in scripts/*.sh and
        scripts/lib/*.sh is either structurally checked (if/while condition,
        $?/`|| return` capture, a real &&/|| chain) or carries a
        `# exit-status: exempt <category>` marker naming a category in
        EXEMPTION_REASONS. Catches a newly added, unclassified invocation on
        the very next run -- it starts in `*-needs-exemption` with no marker
        and fails here until someone decides which it is."""
        violations = []
        for inv in scan_tree():
            if inv.disposition not in NEEDS_EXEMPTION:
                continue
            category = find_exemption(inv.path, inv.line, inv.end_line)
            if category is None:
                violations.append(
                    f"{inv.path.relative_to(REPO_ROOT)}:{inv.line}: {inv.tool} "
                    f"({inv.disposition}) -- no `# exit-status: exempt <category>` "
                    f"marker found on lines {inv.line}-{inv.end_line}"
                )
            elif category not in EXEMPTION_REASONS:
                violations.append(
                    f"{inv.path.relative_to(REPO_ROOT)}:{inv.line}: {inv.tool} "
                    f"marked exempt with unregistered category {category!r} "
                    f"(not a key in EXEMPTION_REASONS)"
                )
        self.assertEqual(
            [],
            violations,
            "Unclassified external-tool invocation(s) -- check the exit "
            "status explicitly or add a reasoned exemption marker: "
            + "; ".join(violations),
        )

    def test_classification_counts(self):
        """Regression pin on the measured baseline (WI-0054, 20.08.2026):
        125 invocations total across the 15 shipped files, split as below.
        A change in these numbers means either a script changed shape or
        the scanner's own logic changed -- worth a deliberate look either
        way, not a silent drift."""
        invocations = scan_tree()
        by_disposition = {}
        for inv in invocations:
            by_disposition[inv.disposition] = by_disposition.get(inv.disposition, 0) + 1
        self.assertEqual(125, len(invocations))
        self.assertEqual(
            {
                "checked-condition": 16,
                "checked-captured": 4,
                "checked-chain": 13,
                "discard-needs-exemption": 31,
                "bare-needs-exemption": 61,
            },
            by_disposition,
        )

    def test_scanned_files_cover_the_shipped_scope(self):
        """Pins the file-enumeration side of "cannot be forgotten": the glob
        is scripts/*.sh + scripts/lib/*.sh, re-evaluated on every run, so a
        FILE added later is picked up automatically -- this only pins that
        the glob itself still reaches the 15 files known at write time."""
        files = sorted(SCRIPTS_DIR.glob("*.sh")) + sorted((SCRIPTS_DIR / "lib").glob("*.sh"))
        names = sorted(f.relative_to(SCRIPTS_DIR).as_posix() for f in files)
        self.assertEqual(
            [
                "artifact-gate.sh",
                "baseline.sh",
                "bootstrap.sh",
                "doc-volume-check.sh",
                "freeze-phase-docs.sh",
                "instinct-check.sh",
                "lib/discipline_gate.sh",
                "lib/frontmatter.sh",
                "log-cleanup.sh",
                "memory-lint.sh",
                "memory-sync.sh",
                "phase-docs-lint.sh",
                "project-init.sh",
                "quality-scan.sh",
                "run-tests.sh",
            ],
            names,
        )


class ExemptionMarkersAreWellFormedTest(unittest.TestCase):
    """Every marker actually present in the shipped files must name a
    registered category -- catches a typo'd category independently of
    whether that specific line is currently classified as needing one (a
    future scanner refinement could reclassify a site; the marker text
    itself should never silently reference a category nobody defined)."""

    def test_every_marker_category_is_registered(self):
        files = sorted(SCRIPTS_DIR.glob("*.sh")) + sorted((SCRIPTS_DIR / "lib").glob("*.sh"))
        unregistered = []
        for f in files:
            for lineno, line in enumerate(f.read_text().split("\n"), start=1):
                m = MARKER_RE.search(line)
                if m and m.group(1) not in EXEMPTION_REASONS:
                    unregistered.append(f"{f.relative_to(REPO_ROOT)}:{lineno}: {m.group(1)!r}")
        self.assertEqual([], unregistered)


class RedProofTest(unittest.TestCase):
    """Mutation-based RED proof (WI-0037/WI-0044 precedent: a checker of
    this kind is untrustworthy until it has been SEEN red). Both cases
    mutate a scratch copy under a temp dir -- the shipped files are never
    touched by this test."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wi0054-redproof-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_new_unchecked_invocation_is_caught(self):
        """A brand-new, completely unguarded grep call appended to a scratch
        copy has no marker and is not checked structurally -- must fail.
        Also proves the shipped source is untouched: byte-identical content
        and unchanged mode bits after the mutation, read fresh both times."""
        src = SCRIPTS_DIR / "doc-volume-check.sh"
        before_bytes = src.read_bytes()
        before_mode = src.stat().st_mode

        scratch = self.tmpdir / "doc-volume-check.sh"
        scratch.write_text(src.read_text() + '\ngrep "unchecked" "$0"\n')
        invocations = scan_file(scratch)
        offenders = [
            inv
            for inv in invocations
            if inv.disposition in NEEDS_EXEMPTION
            and find_exemption(inv.path, inv.line, inv.end_line) is None
        ]
        self.assertTrue(
            offenders,
            "expected the newly appended, unguarded grep to be flagged as "
            "unclassified -- the scanner did not catch it",
        )

        self.assertEqual(before_bytes, src.read_bytes(), "shipped file content changed")
        self.assertEqual(before_mode, src.stat().st_mode, "shipped file mode bits changed")

    def test_removed_exemption_entry_is_caught(self):
        """Deleting one shipped marker (keeping the invocation itself
        unchanged) must turn that site into a reported violation. Also
        proves the shipped source is untouched, the same way as above."""
        src = SCRIPTS_DIR / "baseline.sh"
        before_bytes = src.read_bytes()
        before_mode = src.stat().st_mode
        original = before_bytes.decode()
        self.assertIn(
            "# exit-status: exempt best-effort-status-display",
            original,
            "fixture assumption broken: baseline.sh no longer carries this "
            "marker -- update the fixture line below",
        )
        mutated = original.replace(
            "  # exit-status: exempt best-effort-status-display", "", 1
        )
        self.assertNotEqual(original, mutated)
        scratch = self.tmpdir / "baseline.sh"
        scratch.write_text(mutated)
        invocations = scan_file(scratch)
        offenders = [
            inv
            for inv in invocations
            if inv.disposition in NEEDS_EXEMPTION
            and find_exemption(inv.path, inv.line, inv.end_line) is None
        ]
        self.assertTrue(
            offenders,
            "expected removing the marker to turn its invocation into an "
            "unclassified violation -- the scanner did not catch it",
        )

        self.assertEqual(before_bytes, src.read_bytes(), "shipped file content changed")
        self.assertEqual(before_mode, src.stat().st_mode, "shipped file mode bits changed")


if __name__ == "__main__":
    unittest.main()
