r"""test_heredoc_interpolation_scan.py -- WI-0129 finding F7's class scan:
an UNQUOTED heredoc delimiter (`<< PYEOF`, as opposed to `<< 'PYEOF'` or
`<< "PYEOF"`) makes bash perform parameter expansion on the heredoc's own
BODY before handing it to the consuming command's stdin. When that body
also carries a `${...}` substitution of a value the script does not fully
control (a captured subprocess's raw output, in run-tests.sh's case), any
delimiter-shaped substring in that value's content -- `'''` for a Python
heredoc, but the same class applies to any consumer -- terminates whatever
quoting the heredoc body relies on early, and everything after it is
interpreted as live code by the consumer, not as string content. This
module enumerates every heredoc opener in the shipped shell scripts
(scripts/**/*.sh, install.sh) and flags exactly the shape: unquoted
delimiter AND a `${...}` substitution somewhere in the body.

## Same species as test_external_tool_exit_status.py / test_absence_only_
## assertions.py -- a re-enumerating scan, not a one-time inventory

Like its two siblings, this module re-scans the CURRENT tree on every run
rather than trusting a list written down once by hand -- a new heredoc
added to any shipped script tomorrow, with an unquoted delimiter and a
`${...}` in its body, is caught by ClassificationCountsTest's own count
pins the next time this test runs, not silently missed.

## What counts as "a heredoc" here

`HEREDOC_OPEN_RE` matches `<<-?\s*(['"]?)([A-Za-z_]\w*)\1` -- the same
delimiter grammar test_external_tool_exit_status.py's `HEREDOC_RE` already
uses to BLANK heredoc bodies for its own, unrelated purpose (tool-invocation
scanning); this module walks the opposite direction, keeping the body text
to inspect it rather than discarding it. A leading `(?<!<)` excludes a
here-STRING (`<<<`) from ever being mistaken for a heredoc opener: without
it, the substring starting at the SECOND `<` of `<<<"foo"` -- `<<`, then an
opening `"`, then an identifier-shaped word, then a closing `"` -- matches
the same grammar as a genuine quoted heredoc delimiter. Measured: this
codebase carries over a dozen `<<<` here-strings (grep, freeze-phase-docs.sh,
manual-lint.sh, conformance-run.sh, discipline_gate.sh, ...), every single
one feeding a bare `$var`/`"$var"` with no literal identifier text
immediately after the quote -- a variable reference always starts with `$`,
which is never a valid identifier-start character, so none of them would
have tripped this scanner even without the guard. The guard is retained
regardless, as a mechanical proof the class stays closed rather than
"currently unobserved": a delimiter grammar this permissive should not rely
on today's corpus never happening to contain the shape it would mishandle.

## Why a per-line comment strip, not the full quote-masking machinery

test_external_tool_exit_status.py's `_mask_non_live` blanks BOTH comments
and quoted strings to spaces -- reused here it would also blank the
delimiter's OWN quote characters (`'PYEOF'`), destroying exactly the
quoted-vs-unquoted distinction this scanner exists to tell apart. This
module strips only a trailing `#`-comment per line (mirroring
`_mask_non_live`'s own comment-boundary rule: a `#` counts as a comment
start only when preceded by whitespace, start-of-line, or one of `(;|&{`,
and never inside an open quote on that same physical line) before applying
the heredoc-open regex -- enough to rule out a heredoc syntax EXAMPLE
mentioned inside a comment (measured false-positive candidate:
quality-scan.sh:449, `# independently quoted \`python3 << 'PYEOF'\`
heredoc` -- a `#`-comment starting at column 0, correctly excluded) without
touching the delimiter's own quote characters on a genuine opener line.

## The body-collection loop

For a genuine, unquoted opener, `_body_between` reads every subsequent
physical line until one -- after stripping leading tabs, if the operator
was `<<-` -- exactly equals the delimiter, mirroring `_blank_heredocs`'s
own terminator-matching rule. `${` anywhere in that joined body (not the
opener line itself) is the finding signal -- deliberately broader than
requiring a SPECIFIC variable name, since the defect class is "any
attacker-influenced value reaches an unquoted heredoc body", not one named
variable.

## What this scan does NOT claim

A finding here is a SHAPE, not a proof of exploitability: `cat > file <<
EOF ... ${TODAY} ... EOF` (project-init.sh) and `cat > "${OUTPUT}" <<
PREP_EOF ... ${VERSION} ... PREP_EOF` (baseline.sh) both match the shape but
their heredoc BODY becomes literal file content via `cat`, never gets
re-parsed as executable code the way a `python3 << PYEOF` body does -- a
`'''`-shaped value there corrupts the written file, it does not run
anything. Both are reported below as findings (WI-0129 scope: enumerate the
class, do not silently absorb a site outside run-tests.sh's five), NOT
fixed in this pass -- each becomes its own work item if the PO wants the
same treatment applied there. Distinguishing "written verbatim" from
"parsed as code" would require knowing what EVERY possible heredoc consumer
in this corpus does with its own stdin, which is exactly the kind of
call-graph reasoning test_external_tool_exit_status.py's own docstring
already declines to attempt for its own, narrower question ("What this
check cannot see").

## Findings surfaced, not fixed (WI-0129 scope: F7 fixes run-tests.sh only)

Measured 29.08.2026, against the five scanned locations
(scripts/*.sh, scripts/lib/*.sh, scripts/local-llm/*.sh, install.sh): 7
heredoc sites match the shape (unquoted delimiter + `${` in body) out of 41
heredoc openers total. Five are run-tests.sh's own five (lines 62, 119, 175,
222, 265 at write time) -- fixed by this same work item, see run-tests.sh
directly, no longer flagged after the fix (confirmed by
`FiveOriginalRunTestsSitesAreNoLongerFlaggedTest` below). The remaining two
are reported, not fixed, per this work item's write boundary (run-tests.sh
only):

  * baseline.sh:123 (`cat > "${OUTPUT}" << PREP_EOF`) -- body carries
    `${VERSION}`, `${TODAY}`, `${PROJECT_DIR}`, and four further `${...}`
    references inside nested `$(if ...; then ...; fi)` command
    substitutions (`${ARCHIVE_NAME}`, `${HANDOVER_SUMMARY}`,
    `${PHASE_TRACKER}`, `${TECH_STACK}`, `${MILESTONES}`, `${GIT_TAGS}`).
    `HANDOVER_SUMMARY` in particular is Ollama-generated text summarising a
    project's own HANDOVER.md (baseline.sh's own local-llm delegation) --
    the least "this script's own" of the values interpolated here, though
    the heredoc's consumer is `cat` writing a markdown file, not a
    reparsed-as-code sink.
  * project-init.sh:49 (`cat > ".../DISCOVERY.md" <<EOF`) -- body carries
    one `${TODAY}` (this script's own `date` output). Line moved 47 -> 49,
    30.08.2026 (WI-0129 D1): removing project-init.sh's dead `SCRIPT_DIR`
    assignment (ShellCheck SC2034) and replacing it with a three-line
    comment shifted every line below it down by +2 -- same heredoc,
    verified byte-for-byte identical body against the pre-fix commit,
    not a new or vanished finding.

`KNOWN_FINDINGS` below records exactly these two, keyed the same way
test_absence_only_assertions.py's own registry is (module-relative path,
line number, delimiter) -- present so `ScopeMatchesKnownFindingsTest` can
assert the CURRENT scan produces precisely this set, not a silently
drifted one, without hand-copying the two sites into a second, unlinked
comment.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# `(?<!<)` excludes a here-string (`<<<`) -- see the module docstring.
HEREDOC_OPEN_RE = re.compile(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

DOLLAR_BRACE = "${"


def _strip_trailing_comment(line):
    """Truncates `line` at a `#` that starts a real shell comment -- one
    preceded by whitespace, start-of-line, or one of `(;|&{`, and not
    itself inside an open single/double quote on this same physical line.
    Mirrors test_external_tool_exit_status.py's `_mask_non_live` comment
    rule, narrowed to a single line and deliberately NOT touching quote
    characters otherwise (a heredoc delimiter's own `'...'`/`"..."` must
    survive intact for `HEREDOC_OPEN_RE` to see it)."""
    in_single = False
    in_double = False
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
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
            prev = line[i - 1] if i > 0 else " "
            if prev.isspace() or prev in "(;|&{":
                return line[:i]
            i += 1
            continue
        i += 1
    return line


class HeredocSite:
    __slots__ = ("path", "line", "delimiter", "quoted", "has_dollar_brace")

    def __init__(self, path, line, delimiter, quoted, has_dollar_brace):
        self.path = path
        self.line = line
        self.delimiter = delimiter
        self.quoted = quoted
        self.has_dollar_brace = has_dollar_brace

    @property
    def is_finding(self):
        return not self.quoted and self.has_dollar_brace

    def __repr__(self):
        return f"{self.path.name}:{self.line}:{self.delimiter}:quoted={self.quoted}"


def scan_file(path):
    """Enumerates every heredoc opener in `path`, returning one `HeredocSite`
    per opener (whether or not it is a finding -- callers filter on
    `is_finding`). See the module docstring for the full method."""
    lines = path.read_text().split("\n")
    n = len(lines)
    sites = []
    i = 0
    while i < n:
        code_part = _strip_trailing_comment(lines[i])
        m = HEREDOC_OPEN_RE.search(code_part)
        if m:
            quote = m.group(1)
            delim = m.group(2)
            strip_tabs = code_part[m.start() : m.start() + 3].startswith("<<-")
            j = i + 1
            body_lines = []
            while j < n:
                probe = lines[j].lstrip("\t") if strip_tabs else lines[j]
                if probe == delim:
                    break
                body_lines.append(lines[j])
                j += 1
            body = "\n".join(body_lines)
            sites.append(HeredocSite(path, i + 1, delim, bool(quote), DOLLAR_BRACE in body))
            i = j
        i += 1
    return sites


def scan_tree(scripts_dir=SCRIPTS_DIR, repo_root=REPO_ROOT):
    files = (
        sorted(scripts_dir.glob("*.sh"))
        + sorted((scripts_dir / "lib").glob("*.sh"))
        + sorted((scripts_dir / "local-llm").glob("*.sh"))
        + [repo_root / "install.sh"]
    )
    files = [f for f in files if f.is_file()]
    sites = []
    for f in files:
        sites.extend(scan_file(f))
    return sites


# Baseline of pre-existing findings outside this work item's write boundary
# (run-tests.sh only) -- see the module docstring's "Findings surfaced, not
# fixed" section for why each is reported rather than fixed here. Keyed by
# (path relative to REPO_ROOT, line, delimiter).
KNOWN_FINDINGS = {
    ("scripts/baseline.sh", 123, "PREP_EOF"),
    ("scripts/project-init.sh", 49, "EOF"),  # was 47 -- see the module docstring's WI-0129 D1 line-shift note
}


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


class QuotedDelimiterIsNeverFlaggedTest(unittest.TestCase):
    """Discriminating positive case: a QUOTED delimiter with the exact same
    `${...}`-carrying body is not a finding, regardless of body content --
    `<< 'PYEOF'` disables parameter expansion on the whole body, which is
    the fix this work item applies at all five run-tests.sh sites."""

    def test_quoted_delimiter_with_dollar_brace_body_is_not_flagged(self):
        source = (
            "#!/usr/bin/env bash\n"
            "python3 << 'PYEOF'\n"
            "raw = '''${raw}'''\n"
            "PYEOF\n"
        )
        with _fixture(source) as path:
            sites = scan_file(path)
        self.assertEqual(1, len(sites))
        self.assertTrue(sites[0].quoted)
        self.assertFalse(sites[0].is_finding)


class UnquotedDelimiterWithDollarBraceBodyIsFlaggedTest(unittest.TestCase):
    """Red proof this scanner can actually fail: an UNQUOTED delimiter
    whose body carries `${...}` is exactly the shape run-tests.sh shipped
    with (WI-0129 F7) -- must be recognised as a finding, not merely as
    'not obviously safe'."""

    def test_unquoted_delimiter_with_dollar_brace_body_is_flagged(self):
        source = (
            "#!/usr/bin/env bash\n"
            "python3 << PYEOF\n"
            "raw = '''${raw}'''\n"
            "PYEOF\n"
        )
        with _fixture(source) as path:
            sites = scan_file(path)
        self.assertEqual(1, len(sites))
        self.assertFalse(sites[0].quoted)
        self.assertTrue(sites[0].is_finding)


class UnquotedDelimiterWithoutDollarBraceBodyIsNotFlaggedTest(unittest.TestCase):
    """An unquoted delimiter is not itself the defect -- only paired with a
    `${...}` substitution in the body. Mirrors the many `done <<EOF ...
    $hits ... EOF` sites already shipped in discipline_gate.sh/
    artifact-gate.sh/conformance-run.sh: a BARE `$var` (no braces) feeding a
    `while read` loop, never reparsed as code, is a materially different
    shape this scan deliberately does not flag."""

    def test_unquoted_delimiter_with_bare_var_body_is_not_flagged(self):
        source = "#!/usr/bin/env bash\nwhile read -r line; do\n  :\ndone <<EOF\n$hits\nEOF\n"
        with _fixture(source) as path:
            sites = scan_file(path)
        self.assertEqual(1, len(sites))
        self.assertFalse(sites[0].quoted)
        self.assertFalse(sites[0].is_finding)


class HeredocMentionedInsideACommentIsNotAnOpenerTest(unittest.TestCase):
    """Measured false-positive candidate: quality-scan.sh:449 mentions
    `python3 << 'PYEOF'` inside a `#`-comment, describing a DIFFERENT
    heredoc elsewhere in the same file. A naive line-based regex would
    misread the comment's own text as a second, independent heredoc
    opener -- `_strip_trailing_comment` must exclude it."""

    def test_a_heredoc_syntax_example_inside_a_comment_is_not_an_opener(self):
        source = (
            "#!/usr/bin/env bash\n"
            "# independently quoted `python3 << 'PYEOF'` heredoc example\n"
            "echo hi\n"
        )
        with _fixture(source) as path:
            sites = scan_file(path)
        self.assertEqual([], sites)


class HereStringIsNeverMistakenForAHeredocTest(unittest.TestCase):
    """`(?<!<)` guard: a here-string (`<<<`) followed by a literal quoted
    identifier -- the one shape that would otherwise match the same
    delimiter grammar as a genuine quoted heredoc opener -- must not be
    treated as one (there is no heredoc BODY to collect; the very next
    lines are ordinary script, and reading them as a "body" until a
    same-named terminator line would silently swallow real code)."""

    def test_a_here_string_with_a_literal_quoted_word_is_not_an_opener(self):
        source = (
            "#!/usr/bin/env bash\n"
            'grep -q foo <<<"bar"\n'
            "echo bar\n"
            "echo baz\n"
        )
        with _fixture(source) as path:
            sites = scan_file(path)
        self.assertEqual([], sites)


class ScopeMatchesKnownFindingsTest(unittest.TestCase):
    def test_the_measured_findings_match_known_findings_exactly(self):
        """Positive-form pin: the CURRENT scan's finding set, expressed as
        (path, line, delimiter) triples, equals `KNOWN_FINDINGS` exactly --
        neither a NEW unaccounted finding (a heredoc added elsewhere with
        this shape) nor a STALE entry (one of the two recorded sites fixed
        or removed without updating this baseline) passes silently."""
        current = {
            (site.path.relative_to(REPO_ROOT).as_posix(), site.line, site.delimiter)
            for site in scan_tree()
            if site.is_finding
        }
        self.assertEqual(  # pin: set heredoc-known-findings
            KNOWN_FINDINGS, current)


class FiveOriginalRunTestsSitesAreNoLongerFlaggedTest(unittest.TestCase):
    def test_run_tests_sh_carries_no_finding_after_the_wi_0129_fix(self):
        """Positive-form pin naming the fixed file directly (not just
        absent from KNOWN_FINDINGS): run-tests.sh, scanned on its own,
        produces zero findings -- all five original sites (lines 62, 119,
        175, 222, 265 at write time) now use a quoted delimiter."""
        run_tests = SCRIPTS_DIR / "run-tests.sh"
        sites = scan_file(run_tests)
        heredoc_openers = [s for s in sites if s.delimiter == "PYEOF"]
        self.assertEqual(5, len(heredoc_openers))
        findings = [s for s in sites if s.is_finding]
        self.assertEqual([], findings)


class ClassificationCountsTest(unittest.TestCase):
    def test_classification_counts(self):
        """Regression pin on the measured baseline (WI-0129, 29.08.2026):
        41 heredoc openers total across the 25 scanned files (scripts/*.sh,
        scripts/lib/*.sh, scripts/local-llm/*.sh, install.sh), of which 2
        are findings (both in KNOWN_FINDINGS, neither in run-tests.sh -- the
        fix already closed all 5 of run-tests.sh's own sites). A change in
        either number means a script's heredoc shape changed or this
        scanner's own logic changed -- worth a deliberate look either way,
        not a silent drift.

        Bumped 41 -> 42, 03.09.2026 (CCP-1137R3, Auflage 2): +1 opener from
        scripts/install-push-gate-hook.sh's own `<<'HOOK'` block -- see
        ScannedFilesCoverTheShippedScopeTest's own trajectory entry for why
        it is quoted. Findings unchanged at 2 (the quoted delimiter is not
        a finding)."""
        sites = scan_tree()
        findings = [s for s in sites if s.is_finding]
        self.assertEqual(42, len(sites))
        self.assertEqual(2, len(findings))


class ScannedFilesCoverTheShippedScopeTest(unittest.TestCase):
    def test_scanned_files_cover_the_shipped_scope(self):
        """Pins the file-enumeration side, mirroring
        test_external_tool_exit_status.py's identically-named test: 25
        files at write time (scripts/*.sh: 17, scripts/lib/*.sh: 2,
        scripts/local-llm/*.sh: 5, install.sh: 1).

        Bumped 26 -> 27, 30.08.2026 (WI-0129 D2, ShellCheck adoption): added
        scripts/shellcheck-run.sh under scripts/*.sh. It carries no heredoc
        of its own (zero `<<` occurrences), so ClassificationCountsTest's 41
        openers / 2 findings are unchanged by this file-count bump alone.

        Bumped 27 -> 28, 03.09.2026 (CCP-1137): added scripts/push-gate.sh
        under scripts/*.sh. Same shape as the previous bump -- zero `<<`
        occurrences of its own, so ClassificationCountsTest's 41/2 stays
        unchanged by this bump alone too.

        Bumped 28 -> 29, 03.09.2026 (CCP-1137R3, Auflage 2): added
        scripts/install-push-gate-hook.sh under scripts/*.sh. UNLIKE the two
        bumps above, this file DOES carry a heredoc of its own -- the
        `cat > "${HOOK_PATH}" <<'HOOK'` block writing the installed
        pre-push hook's own body -- so ClassificationCountsTest's opener
        count moves too (41 -> 42). Its delimiter is QUOTED ('HOOK'), which
        is exactly what is needed here: the written hook body's own
        `${HOME}` references must reach the INSTALLED file as literal text,
        expanded later when the hook itself runs (a different shell
        invocation entirely, with its own $HOME), not interpolated at
        install time against the installer's own environment. Zero new
        findings -- confirmed by ScopeMatchesKnownFindingsTest passing
        unmodified, the same set-equality check that would have caught an
        unquoted-delimiter finding."""
        files = (
            sorted(SCRIPTS_DIR.glob("*.sh"))
            + sorted((SCRIPTS_DIR / "lib").glob("*.sh"))
            + sorted((SCRIPTS_DIR / "local-llm").glob("*.sh"))
            + [REPO_ROOT / "install.sh"]
        )
        files = [f for f in files if f.is_file()]
        self.assertEqual(29, len(files))
        names = {f.relative_to(REPO_ROOT).as_posix() for f in files}
        self.assertIn("scripts/run-tests.sh", names)
        self.assertIn("scripts/baseline.sh", names)
        self.assertIn("scripts/lib/discipline_gate.sh", names)
        self.assertIn("install.sh", names)


def _fixture(source):
    import tempfile

    class _Ctx:
        def __enter__(self):
            self._tmp = tempfile.TemporaryDirectory()
            path = Path(self._tmp.name) / "fixture.sh"
            path.write_text(source)
            return path

        def __exit__(self, *exc):
            self._tmp.cleanup()

    return _Ctx()


if __name__ == "__main__":
    unittest.main()
