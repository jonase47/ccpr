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
per category rather than one per site: most exemption sites are routine (a
HANDOVER.md field extraction degrading to blank output, a git overlay-clone
refresh already designed to tolerate failure). `known-risk-
not-yet-fixed` was, until WI-0056/WI-0057, the category meant to stand out
from the routine ones -- see "Findings surfaced, not fixed" below for why no
site carries it any more.

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

WI-0054 recorded two `known-risk-not-yet-fixed` exemptions for real,
unfixed risk found while building this check (surfaced here rather than
silently exempted like the routine sites, deliberately NOT fixed at the
time -- a behaviour change was a separate item). Both were closed on
20.08.2026 (WI-0056, WI-0057); the category still exists in
`EXEMPTION_REASONS` for any future finding of the same shape, but no site
in the shipped scripts currently carries it:
  * bootstrap.sh:206 (WI-0057) -- `grep -E '^### \[' "${INSTINCTS_FILE}" |
    head -5 | while read ...` was completely bare. MEASURED behaviour did
    not match the item's own summary for every "empty" shape: this
    repository's actual `~/.claude/instincts.md` (a bullet-point index, zero
    `### ` headings at all) never reached this line -- `collect_instincts`'s
    earlier `count -eq 0` guard already returns first. The reproducible case
    was narrower: an instincts file WITH `### ` headings that don't use the
    `### [ID] ...` bracket form (the shape this repo's own topic files use:
    `### G-008: ...`, no leading bracket). There, `grep -E '^### \['`
    legitimately matches nothing, exits 1, and -- under `set -o pipefail`
    -- took the whole `{ ... } > "${OUTPUT_FILE}"` block down with it: exit
    1, completely empty stderr, no "Session context written" confirmation,
    even though every section before "## Instinct Status" had already been
    written correctly. Root cause confirmed as pure `pipefail` on a
    legitimately-empty grep, not SIGPIPE from `head -5` (a 200-heading probe
    that `head -5` truncates hard still exits 0 for the pipeline). Fixed by
    capturing the grep call's output and status explicitly and branching on
    grep's own documented exit-status contract (1 = ran fine, nothing
    matched; 2+ = grep itself failed) -- not a blanket `|| true`, which
    would have re-created the exact confusion this item exists to close, in
    the other direction, for a genuine grep failure.
  * log-cleanup.sh:141-155 (WI-0056) -- the trimmed log was written to a
    tmpfile by a bare `python3 -c "..." 2>/dev/null`, and
    `mv "${tmpfile}" "${filepath}"` ran UNCONDITIONALLY afterward. MEASURED
    behaviour did not match the item's own headline mechanism: a python3
    that FAILS (nonzero exit, whether via a PATH stub or this repo's own
    `PYTHONHOME=/nonexistent` broken-interpreter method) already aborted the
    script under this file's own `set -euo pipefail` BEFORE the unconditional
    `mv` was ever reached -- the log survived, silently (stderr empty, no
    diagnostic, no indication of which of three files failed or why). The
    reproducible data-loss shape was different and narrower: a python3 that
    returns EXIT 0 without doing the real work (a broken shim, not a crash by
    the ordinary meaning of "fails"). Fixed by creating the tmpfile in the
    same directory as the target (atomic rename, closing the "process dies
    between write and mv" question -- either the rename hasn't happened yet,
    original untouched, or it has, fully in place), capturing python3's exit
    status AND validating its stdout is a well-formed line count before
    trusting it (closing both the exit-nonzero AND the exit-0-with-garbage-
    output shapes), skipping only the failed file rather than aborting the
    whole run, and surfacing a per-file `[ERROR]` instead of staying silent.
    A residual, deliberately unfixed gap remains and is recorded in
    docs/memory/senior-developer/: a python3 that returns exit 0 AND prints
    a plausible, well-formed (but wrong) line count cannot be distinguished
    from a legitimate full trim by any exit-status-based check.
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
        "not an error' exit convention to confuse with a crash, so relying "
        "on this file's `set -euo pipefail` to abort on an unguarded "
        "failure is the correct, decided response -- PROVIDED the "
        "invocation's own `$(...)` (if any) is checked by `set -e` at all. "
        "On bash 3.2 that holds in exactly two shapes: (1) it is the "
        "entire bare right-hand side of a `var=\"$(cmd)\"` assignment -- "
        "the LAST substitution, if several are concatenated in the same "
        "word, since only being last matters, not being first or being "
        "textually 'the whole' right-hand side; or (2) it stands alone as "
        "the whole simple command. It does NOT hold when the substitution "
        "is one argument, or part of one argument, to some OTHER command "
        "(`echo`, `printf`, `git commit -m \"...\"`, etc.) -- there, no "
        "substitution's exit status is checked at all, regardless of "
        "position or literal text around it. A separate, unrelated quirk "
        "applies when the thing inside `$(...)` is a same-file shell "
        "FUNCTION rather than an external tool: `set -e` is suspended for "
        "that function body's own internal non-tail statements in both "
        "shapes above -- out of scope for this precondition, and out of "
        "scope for SetESufficientNestingTest below by construction (it "
        "only tracks the 5 external tool names). SetESufficientNestingTest "
        "enforces shapes (1) and (2) directly (WI-0105, 25.08.2026, "
        "verified directly; found and fixed the two shipped sites that "
        "violated this precondition: memory-sync.sh's git-push "
        "branch-name substitution and run-tests.sh's JSON raw_output "
        "encoder)."
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


def _scan_file_raw(path):
    """Internal: the same enumeration as `scan_file()`, but each result also
    carries the invocation's own character START position plus the file's
    `scan_text`/`depth` arrays -- needed by a check that inspects an
    invocation's own LOCAL nesting (e.g. `SetESufficientNestingTest` below)
    without re-deriving a position from a line number, which a file with
    more than one same-tool invocation on one physical line would make
    ambiguous. `scan_file()` is a thin wrapper that drops the extra fields;
    this function exists so both callers share the one enumeration loop
    rather than keeping two independently-maintained copies of it."""
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
        inv = Invocation(path, m.group(1), line, end_line, disposition)
        results.append((inv, start, scan_text, depth))
    return results


def scan_file(path):
    """Enumerates every grep/awk/sed/python3/git invocation in `path` and
    classifies each one. See the module docstring for the full method."""
    return [inv for inv, _start, _scan_text, _depth in _scan_file_raw(path)]


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
# set-e-sufficient nesting check (WI-0105)
# --------------------------------------------------------------------------
#
# `EXEMPTION_REASONS["set-e-sufficient"]` claims an unguarded sed/awk/
# python3/git failure "already aborts the script under this file's
# `set -euo pipefail`". That claim has a precondition the reason text did
# not spell out until this work item: on bash 3.2 (`/bin/bash` on this
# repo's own target platform), a `$(...)` command substitution's exit
# status is checked by `set -e` in exactly two shapes, and NOT checked in a
# third that looks deceptively similar to the first:
#
#   1. Assignment context (`var="...$(...)..."` as the sole simple
#      command): the assignment's own exit status is that of the LAST
#      command substitution in the word. Literal text before/after a
#      substitution is irrelevant; when several substitutions are
#      concatenated in the same word, only being LAST matters, not being
#      first or being textually "the whole" right-hand side.
#   2. Standing alone as the whole simple command (`$(...)` with no
#      assignment at all): checked the same as any other simple command.
#   3. Command-argument context (the `$(...)` is one argument, or PART of
#      one argument, to some OTHER command -- `echo`, `printf`,
#      `git commit -m "..."`, etc.): NO substitution's exit status is
#      checked at all, regardless of position or literal text around it.
#      This is the shape both shipped fixes below addressed.
#
# A separate, unrelated quirk: a shell function called inside any `$(...)`
# (`v="$(some_shell_function)"`) suspends `set -e` for that function body's
# OWN internal non-tail statements, in both assignment and argument
# context alike -- out of scope for this check by construction, since the
# scanner only tracks the 5 external tool names below (grep/awk/sed/
# python3/git), never arbitrary shell functions.
#
# Verified directly (WI-0105, reproduced on this machine's /bin/bash
# 3.2.57, each row a standalone `bash -c '...'` invocation, exit code read
# directly with no `||` guard):
#
#   v="$(false)"                    -> exit 1 (rule 1, sole substitution)
#   v="a$(false)b"                  -> exit 1 (rule 1, literal text is irrelevant)
#   v="$(true)$(false)"             -> exit 1 (rule 1, LAST sibling wins)
#   v="$(false)$(true)"             -> exit 0 (rule 1, first sibling is masked by the trailing one)
#   $(true)$(false)                 -> exit 1 (rule 2, LAST sibling wins standalone too)
#   $(false)$(true)                 -> exit 0 (rule 2, first sibling masked, same as rule 1)
#   echo "x $(false)"               -> exit 0 (rule 3, argument context)
#   printf '%s\n' "$(false)"        -> exit 0 (rule 3, argument context)
#   f(){ false; echo x; }; v="$(f)" -> exit 0 (function-nesting quirk, separate from rules 1-3)
#
# This check finds every `set-e-sufficient`-exempted invocation's own DIRECT
# enclosing `$(...)` (if any) and asserts it is bare/standalone under rule 1
# or rule 2 above -- both share the same "last sibling wins" behaviour when
# several substitutions are concatenated, per the two rows above measuring
# rule 2 (standalone, no `VAR=`) directly rather than inferring it by
# analogy from rule 1 (assignment context). See `SetESufficientNestingTest`'s
# own docstring for what it can and cannot see.

_STMT_BOUNDARY_CHARS = set(";\n(|&")
_VAR_EQ_PREFIX_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def _find_enclosing_paren(scan_text, pos):
    """Backward bracket-stack scan: the position of the nearest UNMATCHED
    '(' before `pos` -- i.e., whatever paren (of any kind: `$(...)`, a plain
    `(...)` grouping, `<(...)` process substitution) is innermost-open at
    `pos`. None if `pos` sits at depth 0 (not nested in any paren at all)."""
    i, counter = pos, 0
    while i > 0:
        i -= 1
        c = scan_text[i]
        if c == ")":
            counter += 1
        elif c == "(":
            if counter > 0:
                counter -= 1
            else:
                return i
    return None


def _find_matching_close(scan_text, open_pos):
    """Forward bracket-depth scan: the position of the ')' that closes the
    '(' at `open_pos`. None if the file text is malformed enough that it
    never closes (should not happen on syntactically valid shell)."""
    depth, i, n = 0, open_pos, len(scan_text)
    while i < n:
        c = scan_text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _find_matching_open(scan_text, close_pos):
    """Reverse counterpart of `_find_matching_close`: the position of the
    '(' that opens the ')' at `close_pos`. None if the file text is
    malformed enough that it never opens (should not happen on
    syntactically valid shell)."""
    depth, i = 0, close_pos
    while i >= 0:
        c = scan_text[i]
        if c == ")":
            depth += 1
        elif c == "(":
            depth -= 1
            if depth == 0:
                return i
        i -= 1
    return None


def _prefix_is_var_eq_then_sibling_chain(scan_text, start, end):
    """True if `scan_text[start:end]` is (whitespace-tolerant) an optional
    `VAR=`, followed by zero or more complete, directly adjacent `$(...)`
    substitutions, and nothing else. This is the general form of "bare
    right-hand side of an assignment": with zero sibling substitutions it
    degenerates to the original bare-assignment check; with one or more, it
    proves the segment carries no OTHER content (literal text, a different
    command) that the trailing target substitution could be hiding behind.
    Whitespace between tokens is tolerated because the scanner's own quote-
    masking turns a `"` into a literal space in `scan_text` -- e.g. the
    quote right after `VAR=` in `var="$(a)$(b)"`."""
    i, n = start, end

    def _skip_ws(pos):
        while pos < n and scan_text[pos] in " \t":
            pos += 1
        return pos

    i = _skip_ws(i)
    m = _VAR_EQ_PREFIX_RE.match(scan_text[i:n])
    if m:
        i += m.end()
    i = _skip_ws(i)
    while i < n:
        if scan_text[i] != "$" or i + 1 >= n or scan_text[i + 1] != "(":
            return False
        close = _find_matching_close(scan_text, i + 1)
        if close is None or close >= n:
            return False
        i = _skip_ws(close + 1)
    return True


def _is_bare_or_standalone_substitution(scan_text, open_pos, close_pos):
    """True if the `$(...)` spanning `open_pos`..`close_pos` is either the
    ENTIRE right-hand side of a `var=$(...)` assignment (including being
    the LAST of several `$(...)` substitutions directly concatenated in the
    same assignment word -- see `_prefix_is_var_eq_then_sibling_chain`) or
    stands alone as the whole simple command -- nothing else present in the
    same statement before the `$` (besides an optional `VAR=` prefix, zero
    or more complete PRECEDING sibling substitutions, and the whitespace
    the scanner's own quote-masking already turned a `"` into) or after the
    matching `)` (besides an optional matching quote, same reason). The
    statement boundary characters mirror `_skip_assignments_back`'s own
    boundary set (`\\n;|&(`) for consistency with the rest of this module.

    The backward walk treats a complete `$(...)` sibling substitution
    immediately behind the cursor as one atomic unit to skip over -- not
    stopping partway through its own interior text -- so a PRECEDING
    sibling never masks the true statement start behind it."""
    n = len(scan_text)
    dollar_pos = open_pos - 1  # position of the '$' that opens "$("
    i = dollar_pos
    while i > 0:
        c = scan_text[i - 1]
        if c in _STMT_BOUNDARY_CHARS:
            break
        if c == ")":
            sibling_open = _find_matching_open(scan_text, i - 1)
            if sibling_open is not None and sibling_open > 0 and scan_text[sibling_open - 1] == "$":
                i = sibling_open - 1
                continue
            # The nearest paren behind the cursor closes something that is
            # not a `$(...)` substitution (a plain `(...)` grouping or a
            # malformed close) -- conservatively stop here rather than risk
            # walking into content this function cannot interpret.
            break
        i -= 1
    backward_ok = _prefix_is_var_eq_then_sibling_chain(scan_text, i, dollar_pos)
    j = close_pos + 1
    while j < n and scan_text[j] in " \t":
        j += 1
    forward_ok = j >= n or scan_text[j] in ";\n)|&"
    return backward_ok and forward_ok


def _set_e_sufficient_nesting_violations(scripts_dir=SCRIPTS_DIR):
    """Every `set-e-sufficient`-exempted invocation whose own DIRECT
    enclosing `$(...)` is not bare/standalone (see the module comment
    above). An invocation with no enclosing paren at all (depth 0 at its own
    tool-name match position) is not nested in anything and is out of scope
    -- `set -e` on that top-level statement always applies normally."""
    violations = []
    files = sorted(scripts_dir.glob("*.sh")) + sorted((scripts_dir / "lib").glob("*.sh"))
    for f in files:
        for inv, start, scan_text, depth in _scan_file_raw(f):
            if inv.disposition not in NEEDS_EXEMPTION:
                continue
            if find_exemption(inv.path, inv.line, inv.end_line) != "set-e-sufficient":
                continue
            if depth[start] == 0:
                continue
            open_pos = _find_enclosing_paren(scan_text, start)
            if open_pos is None or open_pos == 0 or scan_text[open_pos - 1] != "$":
                # The nearest enclosing paren is not a `$(...)` command
                # substitution at all (a plain `(...)` group or a `<(...)`
                # process substitution) -- out of scope, see
                # SetESufficientNestingTest's own "cannot see" list.
                continue
            close_pos = _find_matching_close(scan_text, open_pos)
            if close_pos is None:
                continue
            if not _is_bare_or_standalone_substitution(scan_text, open_pos, close_pos):
                violations.append(inv)
    return violations


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
        """Regression pin on the measured baseline (WI-0054, 20.08.2026;
        updated 20.08.2026 when WI-0056/WI-0057 closed the two
        `known-risk-not-yet-fixed` sites this same baseline recorded --
        both invocations are now explicitly checked, not exempted, so
        `bare-needs-exemption` drops by 2 and the two checked buckets each
        gain one site; updated again the same day when WI-0018's follow-up
        fix added three `git rev-parse --show-toplevel` calls to
        artifact-gate.sh's docs-boundary self-detection -- one discarded
        under `|| true` with a `downstream-checks-result` marker (its
        output is tested for emptiness two lines later), two real `||`
        fallback-assignment branches, so `discard-needs-exemption` gains
        one site and `checked-chain` gains two; updated again 21.08.2026
        when WI-0020's commit-anchor-family check added one
        `git rev-parse --verify -q ... ^{commit}` call to
        phase-docs-lint.sh, tested directly by its `if [[ ... ]] && ! git
        ...; then` condition -- `checked-condition` gains one site; updated
        again the same day when WI-0021 added scripts/anchor.sh, a new
        16th shipped file, with 11 invocations of its own: two `git
        rev-parse --verify -q` calls each tested directly by their own `if`
        condition (`checked-condition` +2); a `sed -n ... | sed ...` pipe
        in usage() and a `diff --name-only`/`diff-tree --name-only`/`log`
        trio feeding `while read` loops via process substitution, none of
        them observable from the reading `while` under bash's own rules
        (`bare-needs-exemption` +5, all five marked
        `proc-subst-unobservable`/`set-e-sufficient`); a `status
        --porcelain`, an `is-shallow-repository` and a `show --format`
        each captured via `$(... || true)` and either branched on by their
        OWN caller's next line or used only for cosmetic display, plus one
        `python3 -` JSON config read already following
        lib/discipline_gate.sh's `_gate_read_config` shape
        (`discard-needs-exemption` +4, marked `downstream-checks-result` x2,
        `best-effort-status-display` x1, `optional-config-read` x1 --
        pre-existing site, not new); updated once more the same day when
        anchor.sh's `status` report grew a per-scope commit-DISTANCE field
        ("Abstand in Commits", ADR-0009's own wording for what `status`
        must show alongside the delta) via one more `git rev-list --count
        anchor..last-prod` call, captured through the same `$(... ||
        true)` shape as the adjacent `git show` display line and marked
        `best-effort-status-display` the same way (`discard-needs-exemption`
        +1)); updated once more 21.08.2026 when WI-0021 wave 4b (`anchor
        set`/`anchor ack`, the portable `fm_set` writer, and the
        freeze-phase-docs.sh anchor hook) added three invocations and
        removed one: `anchor.sh` gains a `git rev-parse --verify -q
        ...^{commit}` for `--commit` validation, itself followed by a real
        `|| die` on the SAME statement rather than being an `if`'s own
        tested command (`checked-chain` +1), and a `git show -s
        --format=%ad` commit-date lookup captured via the same `$(... ||
        true)` shape as the adjacent display lines (`discard-needs-exemption`
        +1, `best-effort-status-display`); `freeze-phase-docs.sh` LOSES its
        one BSD-only `sed -i ''` entirely (WI-0076: replaced by `fm_set`,
        a bash function in a different file, invisible to this scanner)
        and GAINS a `grep -q` inside the anchor hook's own `elif` condition
        (`bare-needs-exemption` -1, `checked-condition` +1, net 0 for this
        file); `lib/frontmatter.sh` gains `fm_set`'s own `if ! awk ...;
        then` guard, tested directly by the `if` (`checked-condition` +1)
        -- the awk failure must not fall through to the following `mv` and
        silently overwrite the original with an empty temp file. Net +3
        invocations (144 total): `checked-condition` +2, `checked-chain`
        +1, `discard-needs-exemption` +1, `bare-needs-exemption` -1);
        updated once more the same day when the still-uncommitted wave 4b
        went through review (WI-0021 review): the Critical fix adds
        `fm_set_many` to `lib/frontmatter.sh`, a second general-purpose
        writer alongside `fm_set` with the exact same "if the awk pass
        fails, do not fall through to `mv`" shape -- one more `if ! awk
        ...; then` guard, tested directly by the `if` (`checked-condition`
        +1). None of the OTHER review fixes (the ENVIRON switch inside
        fm_set's existing awk call, the TTY guard and scope check in
        anchor.sh, the dedicated exit code 3) touch a grep/awk/sed/
        python3/git invocation's SHAPE, only its surrounding logic, so
        they add nothing here. Net +1 invocation (145 total):
        `checked-condition` +1, everything else unchanged.
        Updated once more 21.08.2026 when ADR-0009 Addendum 3
        (`anchor_ack_by`) added `get_ack_identity()` to anchor.sh: two
        `git config user.email` / `git config user.name` reads, each
        captured via the same `$(... || true)` shape as the adjacent
        git-state probes and marked `downstream-checks-result` the same
        way -- an unconfigured identity is a legitimate, expected state
        (ANCHOR_ACK_NO_IDENTITY exists precisely for it), not a failure to
        surface. Net +2 invocations (147 total): `discard-needs-exemption`
        +2, everything else unchanged.
        Updated once more 22.08.2026 when WI-0072 added
        scripts/migrate-review-headers.sh, a new 17th shipped file, with
        exactly one invocation of its own: a `sed -E 's/^SPRINT-.../\1'`
        filename-number extraction inside a plain `var="$(cmd)"`
        assignment (no `if`, no `|| true` discard) -- structurally a bare
        assignment, marked `set-e-sufficient` the same way every other
        sed/awk/git call in this file set is (this file's own
        `set -euo pipefail` already aborts on its failure). Net +1
        invocation (148 total): `bare-needs-exemption` +1, everything else
        unchanged.
        Updated once more the same day (22.08.2026, the base_commit-or-
        reviewed_base correction) when migrate-review-headers.sh gained the
        Korrektur-2 hoist step: an `awk 'NR==1 && ...'` frontmatter/body
        splitter (`_body_text`) and a `sed -nE 's/^${key}:.../\1/p' | head
        -n1` bare-key-line extractor (`_hoist_candidate`) -- both plain
        pipelines with no `if`/`|| true`/`$?` around them, both marked
        `set-e-sufficient` for the same reason as the pre-existing
        sed on this file (no "1 = nothing matched" ambiguity to confuse
        with a crash; a genuine sed/awk parse failure still aborts under
        this file's own `set -euo pipefail`, verified directly: a
        deliberately malformed sed script on the same pipeline shape does
        abort the whole `f() { ... }; v="$(f)"` assignment, not just log a
        warning). Net +2 invocations (150 total): `bare-needs-exemption`
        +2, everything else unchanged.
        Updated once more 24.08.2026 when WI-0102 rebuilt quality-scan.sh's
        scan_deps/scan_sast: the four per-tool `$(... || echo '<empty>')`
        chains and their inline `python3 -c` consumers are gone, replaced by
        a single `run_py()` helper that calls the report reader through
        `if ! python3 "$@"`. That concentrates five separate invocations
        into one CHECKED one -- deliberately, because the `set-e-sufficient`
        justification the old sites carried does not hold inside a `$(...)`
        command substitution on bash 3.2 (measured). Net -7 invocations
        (143 total): `checked-condition` +1, `checked-chain` -4,
        `bare-needs-exemption` -4, everything else unchanged.
        Updated once more 25.08.2026 when WI-0105 (the mechanical successor
        to WI-0102's "measured" note two entries up) added
        `SetESufficientNestingTest` and fixed the two shipped sites it
        found: memory-sync.sh's `git push` branch-name substitution
        (`$(git ... rev-parse --abbrev-ref HEAD)` embedded inline inside
        `HEAD:refs/heads/"..."`) hoisted to its own bare `branch=$(...)`
        assignment (`bare-needs-exemption` +1, still `set-e-sufficient`,
        same disposition/category as before -- an invocation moving to a
        safer line, not a new one), and run-tests.sh's JSON `raw_output`
        encoder (`$(echo "${raw}" | python3 -c ...)` embedded inline inside
        the outer `echo`'s string literal) rewritten with a real `||`
        fallback assignment, turning it from `bare-needs-exemption` into
        `checked-chain` (no exemption marker needed any more). Net 0
        invocations (143 total): `bare-needs-exemption` -1, `checked-chain`
        +1, everything else unchanged.
        Updated once more 26.08.2026 when the four remaining `producer |
        grep -q` sites under `set -o pipefail` (the same SIGPIPE
        false-negative shape scripts/manual-lint.sh's `idx_content` site
        was already fixed for) were converted to here-strings.
        freeze-phase-docs.sh's anchor-message check, run-tests.sh's
        `vitest`/`jest` detection, and discipline_gate.sh's IP-allowlist
        membership test all keep the same disposition: their producer
        (`printf`/`echo`) is not one of this scanner's five tracked tool
        names, and grep stays the direct, first word governed by the
        enclosing `if`/`elif` -- still `checked-condition`, nothing moves.
        artifact-gate.sh's exempt-marker check is the one site where the
        fix DOES move a disposition: pulling sed out of the piped `if`
        condition (`sed ... | grep -qF ...`) and nesting it as `$(sed
        ...)` inside grep's here-string argument takes it out of being,
        transitively via the pipeline, that `if`'s own tested command --
        the substitution is now ARGUMENT context (rule 3 in the
        `set-e-sufficient` precondition above), where no substitution's
        exit status is checked by `set -e` at all. Marked
        `downstream-checks-result` instead: grep, on the very same
        statement, already treats a failed/empty sed extraction as "marker
        not found", the same outcome this branch already tolerated before
        the fix. Net 0 invocations (144 total): `checked-condition` -1,
        `bare-needs-exemption` +1, everything else unchanged.
        Updated once more 27.08.2026 when WI-0124 wave 1 added
        scripts/conformance-run.sh, a new 18th shipped file (ADR-0010's
        skeleton conformance runner): `usage()`'s `sed -n '2,/^$/p' ... |
        sed 's/^# ...//' ` pipeline, the same shape and reason as
        artifact-gate.sh's own usage() (two `sed` invocations, both
        `bare-needs-exemption`, marked `set-e-sufficient`); the
        `_conformance_read_config()` config reader's `python3 - "$1"
        <<'PY'` heredoc, the tail statement of a small shell helper whose
        own exit status IS the function's return by design -- the same
        documented shape as lib/discipline_gate.sh's `_gate_unicode_py`
        (`bare-needs-exemption`, marked `propagates-as-function-return`,
        deliberately NOT `optional-config-read`: that category means "the
        caller's own defaults are the intended fallback", and this reader's
        caller checks the real exit status via `|| read_rc=$?` and refuses
        to run on anything nonzero -- ADR-0010 §5's deliberate divergence
        from `_gate_read_config`'s `except Exception: sys.exit(0)`); and one
        `awk -F'\\t' '$1 == "ERROR" { print $2; exit }'` extracting the
        ERROR record's message from that same reader's own well-formed,
        tab-delimited output (`bare-needs-exemption`, marked
        `internal-record-parsing`, same reasoning as
        lib/discipline_gate.sh's other internal-record-parsing sites --
        this script's own output, not external input). Net +4 invocations
        (148 total): `bare-needs-exemption` +4, everything else unchanged.
        148 invocations total across the 18 shipped files, split as below.
        A change in these numbers means either a script changed shape or
        the scanner's own logic changed -- worth a deliberate look either
        way, not a silent drift.

        Updated 30.08.2026 (WI-0129 Paket B, cycle B2): +3 for
        scripts/doc-volume-check.sh's new tracked-only scope. One `git -C
        "$DOCS_ROOT" rev-parse --show-toplevel >/dev/null 2>&1` is tested
        directly by its own `if` condition (`checked-condition` +1). A
        `git -C "$DOCS_ROOT" ls-files -z ... | while ...; done >
        "$TRACKED_LIST_FILE"` pipeline stands alone under `set -euo
        pipefail`, no `$(...)` involved -- exempted `set-e-sufficient`, the
        same shape artifact-gate.sh's own `git ls-files -z | while ...`
        sweep already uses (`bare-needs-exemption` +1). The `LC_ALL=C grep
        -qxF -- "$rel" "$TRACKED_LIST_FILE"` inside `is_tracked()` is the
        tail statement of a small predicate function whose own exit status
        IS the function's return by design, checked by every CALLER via
        `if ! is_tracked ...` -- the identical documented shape as
        conformance-run.sh's `_conformance_read_config()` and
        lib/discipline_gate.sh's `_gate_unicode_py`, marked
        `propagates-as-function-return` (`bare-needs-exemption` +1). 155
        invocations total: `checked-condition` +1, `bare-needs-exemption`
        +2, everything else unchanged.

        Updated once more 30.08.2026 (WI-0129 D2, ShellCheck adoption):
        scripts/shellcheck-run.sh, a new 21st shipped file, added three
        invocations of its own. Two are a `sed -n '2,/^$/p' ... | sed
        's/^# \\{0,1\\}//'` usage()-extraction pipeline -- the EXACT same
        shape check-all.sh's own usage() already carries (see the
        29.08.2026 entry above), marked `set-e-sufficient` for the
        identical reason: no `$(...)` involved, the pipeline stands alone
        under `set -euo pipefail` (`bare-needs-exemption` +2). The third is
        a `grep -c ': .*\\[SC[0-9]*\\]' || true` finding-count extraction
        inside a `$(...)` assignment -- an intentionally tolerated empty
        result (0 findings greps to nothing, exit 1, not a crash), marked
        `grep-empty-is-valid` (`discard-needs-exemption` +1). 158
        invocations total: `discard-needs-exemption` +1,
        `bare-needs-exemption` +2, everything else unchanged.
        01.09.2026: +3 total for scripts/doc-volume-check.sh's autoloaded-
        context scan -- `checked-condition` +1, `bare-needs-exemption` +2.
        Proven a pure addition by a MULTISET difference over
        (file, tool, disposition) against a worktree of e47587f, deliberately
        NOT over (file, line, ...): inserting code above existing calls shifts
        their line numbers, and a line-bearing identity reports each shift as
        one removal plus one addition. That identity showed 7 additions and 4
        removals for the same change; the line-independent one shows 3 and 0.
        The total pinned here was correct, but the full set of pin registers
        in this repository was NOT known at the time of this bump -- this pin
        was discovered by a red CI run, not from a list (WI-0133)."""
        invocations = scan_tree()
        by_disposition = {}
        for inv in invocations:
            by_disposition[inv.disposition] = by_disposition.get(inv.disposition, 0) + 1
        self.assertEqual(161, len(invocations))
        self.assertEqual(
            {
                # 28.08.2026, open-findings wave 1a: one invocation moved
                # from bare to checked, total unchanged at 148.
                # quality-scan.sh's report combiner was a bare
                # `python3 -c "..."` with three shell values interpolated
                # into Python source -- the very thing this file's target
                # script forbids in its own header. It is now
                # `if ! python3 "${SUMMARY_PY}" ...` with the values in
                # argv, so the exit status is read instead of discarded.
                # (The `mv` the same fix introduced is not tracked here:
                # this scanner pins grep/awk/sed/python3/git only.)
                # 28.08.2026, wave 1b: +1 total. The failure marker's
                # own writer is a new python3 call, and it is checked --
                # `if python3 ... && [ -s ... ]` -- so the growth lands in
                # the checked bucket, not the bare one.
                # 29.08.2026: +3 total for scripts/check-all.sh. Two are
                # the `sed | sed` pipeline in its usage() -- exempted
                # `set-e-sufficient`, correctly: no `$(...)` is involved, the
                # pipeline stands alone under `set -euo pipefail`, so a
                # failure aborts. "bare-needs-exemption" is this scanner's
                # SHAPE label, not a verdict; the marker is honoured and
                # ExemptionMarkersAreWellFormedTest passes on both. The third
                # is its python3 suite runner, written `if python3 ...; then
                # rc=0; else rc=$?; fi`, so it lands in the checked bucket.
                # 30.08.2026: +3 total for scripts/shellcheck-run.sh (WI-0129
                # D2) -- see this test's own docstring entry immediately
                # above for the per-invocation breakdown.
                "checked-condition": 28,
                "checked-captured": 5,
                "checked-chain": 14,
                "discard-needs-exemption": 41,
                "bare-needs-exemption": 73,
            },
            by_disposition,
        )

    def test_scanned_files_cover_the_shipped_scope(self):
        """Pins the file-enumeration side of "cannot be forgotten": the glob
        is scripts/*.sh + scripts/lib/*.sh, re-evaluated on every run, so a
        FILE added later is picked up automatically -- this only pins that
        the glob itself still reaches the 18 files known at write time
        (updated 21.08.2026 when WI-0021 added scripts/anchor.sh; updated
        again 22.08.2026 when WI-0072 added scripts/migrate-review-headers.sh;
        updated again 27.08.2026 when WI-0124 wave 1 added
        scripts/conformance-run.sh; updated again 30.08.2026 when WI-0129 D2
        added scripts/shellcheck-run.sh)."""
        files = sorted(SCRIPTS_DIR.glob("*.sh")) + sorted((SCRIPTS_DIR / "lib").glob("*.sh"))
        names = sorted(f.relative_to(SCRIPTS_DIR).as_posix() for f in files)
        self.assertEqual(  # pin: set external-tool-scanned-scripts
            [
                "anchor.sh",
                "artifact-gate.sh",
                "baseline.sh",
                "bootstrap.sh",
                "check-all.sh",
                "conformance-run.sh",
                "doc-volume-check.sh",
                "freeze-phase-docs.sh",
                "instinct-check.sh",
                "lib/discipline_gate.sh",
                "lib/frontmatter.sh",
                "log-cleanup.sh",
                "manual-lint.sh",
                "memory-lint.sh",
                "memory-sync.sh",
                "migrate-review-headers.sh",
                "phase-docs-lint.sh",
                "project-init.sh",
                "quality-scan.sh",
                "run-tests.sh",
                "shellcheck-run.sh",
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


class SetESufficientNestingTest(unittest.TestCase):
    """WI-0105: `EXEMPTION_REASONS["set-e-sufficient"]` is only true under a
    precondition -- see the module comment above
    `_set_e_sufficient_nesting_violations` for the measured evidence. This
    test enforces that precondition: every `set-e-sufficient`-marked
    invocation's own DIRECT enclosing `$(...)`, if any, must be either the
    entire bare right-hand side of an assignment (the LAST substitution, if
    several are concatenated in the same word) or stand alone as the whole
    simple command -- never one argument, or part of one argument, to some
    other command.

    What this check CAN see: every `set-e-sufficient`-marked invocation's
    own DIRECT/OUTERMOST enclosing `$(...)`, checked one level at a time,
    including recognizing it as bare when it is the LAST of several `$(...)`
    substitutions directly concatenated in the same assignment word (a
    PRECEDING sibling is skipped over as one atomic unit, not walked into
    character by character -- see `_is_bare_or_standalone_substitution`).

    What this check CANNOT see (both confirmed by direct measurement, not
    assumed):
      * A call to a same-file shell FUNCTION that is not one of the 5
        tracked tool names (grep/awk/sed/python3/git) is invisible to
        `TOOL_RE` regardless of nesting. memory-sync.sh's `resolve_token()`
        is exactly this shape: `tok="$(resolve_token)"` inside `authed_url()`
        is textually a bare assignment, yet on bash 3.2 a failing
        intermediate statement inside a function that is itself running
        inside a `$(...)`-spawned subshell does not abort that function
        either (verified directly: `x="$(false)"` as a non-tail statement
        inside a function called via `r="$(fn)"` does not stop the calling
        script under `set -euo pipefail`, while the identical line called
        directly, with no enclosing `$(...)` at all, does). That is a
        second, distinct quirk from the one this check detects, and it is
        out of scope for a scanner that only sees the 5 tracked tool names
        by construction.
      * Nesting depth beyond the DIRECT enclosing `$(...)`: a
        `set-e-sufficient` site nested two or more command-substitution
        levels deep would not be specifically distinguished from one level
        deep by this check. None exist in the shipped corpus at the time
        this check was written -- confirmed by measurement (every
        `set-e-sufficient` site in scripts/*.sh + scripts/lib/*.sh has depth
        0 or 1), not assumed.
      * A `set-e-sufficient` site whose nearest enclosing paren is a plain
        `(...)` subshell grouping or a `<(...)` process substitution rather
        than a genuine `$(...)` command substitution: this check only asks
        the question command-substitution embedding raises, and skips that
        site rather than misclassifying it. Process substitution's own,
        unrelated observability gap is already covered by the
        `proc-subst-unobservable` category.
    """

    def test_set_e_sufficient_invocations_are_not_embedded_inline(self):
        violations = _set_e_sufficient_nesting_violations()
        self.assertEqual(
            [],
            [f"{v.path.relative_to(REPO_ROOT)}:{v.line}: {v.tool}" for v in violations],
            "set-e-sufficient invocation(s) whose own $(...) is not the "
            "bare/standalone shape set -e actually checks on bash 3.2 -- "
            "either it is one argument (or part of one) to some OTHER "
            "command, where no substitution's exit status is ever checked, "
            "or it is a NON-LAST substitution among several concatenated "
            "in the same assignment word, where its own exit status is "
            "masked by the trailing sibling's. Either way, the exemption's "
            "own justification does not hold here. Hoist the substitution "
            "to its own bare `var=\"$(cmd)\"` assignment on a statement by "
            "itself before the line that uses it.",
        )


class SetESufficientRedProofTest(unittest.TestCase):
    """Mutation-based RED proof for SetESufficientNestingTest (same
    precedent as RedProofTest below: a checker of this kind is untrustworthy
    until it has been SEEN red, WI-0037/WI-0044). Once memory-sync.sh and
    run-tests.sh are fixed (WI-0105), the shipped corpus may never again
    contain an embedded-inline set-e-sufficient site on its own -- this
    scratch fixture keeps both the positive and the negative case exercised
    regardless of what the shipped scripts look like. A standalone class
    (not a RedProofTest subclass) per this file's own convention against
    subclassing a concrete test class that carries its own tests."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wi0105-redproof-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_embedded_inline_set_e_sufficient_is_caught(self):
        scratch = self.tmpdir / "scratch.sh"
        scratch.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'echo "wrap: $(git rev-parse --short HEAD)"  '
            "# exit-status: exempt set-e-sufficient\n"
        )
        violations = _set_e_sufficient_nesting_violations(scripts_dir=self.tmpdir)
        self.assertTrue(
            violations,
            "expected the embedded-inline git call to be flagged -- the "
            "nesting check did not catch it",
        )

    def test_bare_assignment_set_e_sufficient_is_not_flagged(self):
        """Companion positive case: the safe shape (the ENTIRE right-hand
        side of a bare assignment) must NOT be flagged, so this check does
        not degenerate into rejecting every nested set-e-sufficient site
        regardless of shape."""
        scratch = self.tmpdir / "scratch.sh"
        scratch.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "local sha\n"
            'sha="$(git rev-parse --short HEAD)"  '
            "# exit-status: exempt set-e-sufficient\n"
            'echo "$sha"\n'
        )
        violations = _set_e_sufficient_nesting_violations(scripts_dir=self.tmpdir)
        self.assertEqual([], violations)

    def test_last_of_two_sibling_substitutions_is_not_flagged(self):
        """WI-0105 refinement: on bash 3.2, an assignment's own exit status
        is that of the LAST `$(...)` in the word when several are
        concatenated -- position relative to a PRECEDING sibling is
        irrelevant, only being last matters (measured directly:
        `v="$(true)$(false)"` under `set -euo pipefail` aborts, exit 1;
        `v="$(false)$(true)"` does not, exit 0). The checked invocation
        here (`git`) is the LAST of two substitutions in one assignment
        word, so it must NOT be flagged."""
        scratch = self.tmpdir / "scratch.sh"
        scratch.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "local combined\n"
            'combined="$(date +%s)$(git rev-parse --short HEAD)"  '
            "# exit-status: exempt set-e-sufficient\n"
            'echo "$combined"\n'
        )
        violations = _set_e_sufficient_nesting_violations(scripts_dir=self.tmpdir)
        self.assertEqual([], violations)

    def test_first_of_two_sibling_substitutions_is_flagged(self):
        """Companion negative case for the row above: the checked
        invocation (`git`) is the FIRST of two substitutions in one
        assignment word -- its own exit status is masked by the trailing
        `$(date +%s)` that runs after it, so this site must stay flagged
        even though it is the entire word's own textual right-hand side
        MINUS the trailing sibling."""
        scratch = self.tmpdir / "scratch.sh"
        scratch.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "local combined\n"
            'combined="$(git rev-parse --short HEAD)$(date +%s)"  '
            "# exit-status: exempt set-e-sufficient\n"
            'echo "$combined"\n'
        )
        violations = _set_e_sufficient_nesting_violations(scripts_dir=self.tmpdir)
        self.assertTrue(
            violations,
            "expected the non-last sibling substitution to stay flagged -- "
            "its exit status is masked by the trailing sibling",
        )

    def test_last_of_three_sibling_substitutions_is_not_flagged(self):
        """The atomic-sibling-skip in `_is_bare_or_standalone_substitution`'s
        backward walk must recurse across MORE THAN ONE preceding sibling,
        not just the single sibling the two-substitution cases above
        exercise -- a chain of two `$(...)` sibling-skips in a row is where
        an off-by-one in that loop would show up (verified directly:
        `v="$(true)$(true)$(false)"` under `set -euo pipefail` aborts,
        exit 1 -- the LAST of three still governs)."""
        scratch = self.tmpdir / "scratch.sh"
        scratch.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "local combined\n"
            'combined="$(date +%s)$(hostname)$(git rev-parse --short HEAD)"  '
            "# exit-status: exempt set-e-sufficient\n"
            'echo "$combined"\n'
        )
        violations = _set_e_sufficient_nesting_violations(scripts_dir=self.tmpdir)
        self.assertEqual([], violations)

    def test_sibling_with_its_own_nested_substitution_is_not_flagged(self):
        """A PRECEDING sibling whose own interior contains a nested
        `$(...)` must still be skipped as one atomic unit -- this is
        exactly what `_find_matching_open`'s generic paren-depth counting
        (not `$(`-aware) exists to get right, as opposed to a naive scan
        that stops at the first unmatched-looking `)` (verified directly:
        `v="$(echo $(echo x))$(false)"` under `set -euo pipefail` aborts,
        exit 1)."""
        scratch = self.tmpdir / "scratch.sh"
        scratch.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "local combined\n"
            'combined="$(echo $(hostname))$(git rev-parse --short HEAD)"  '
            "# exit-status: exempt set-e-sufficient\n"
            'echo "$combined"\n'
        )
        violations = _set_e_sufficient_nesting_violations(scripts_dir=self.tmpdir)
        self.assertEqual([], violations)


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
