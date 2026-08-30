r"""test_live_status_claims.py -- a register that states the CURRENT outcome of
its own subject drifts, because the register and the subject are maintained
separately.

## The class

A REGISTER is a place that records a claim about the state of something else:
a module docstring about the outcome of its own test, a file header about its
own data rows, a status line about a work item, a list of open findings. The
register and its subject are edited at different times by different hands, so
the register goes stale silently -- nothing reads it, so nothing contradicts
it.

Six instances in this repository in a fortnight (nine ADR follow-ups that
outlived their answers; a module docstring claiming RED while the tree was
green; a findings list that counted eleven and omitted one; the note numbers
in `scripts/check-all.baseline.tsv`, four times in three days; `check-all.sh`'s
header against its own baseline; four closed findings still listed as open).
Every one of them got a sweep. None of them got a mechanism -- which is why
the class kept returning.

## What this module mechanises, and why exactly this slice

Of all the claims a register can make, ONE is derivable from an invariant this
repository already enforces, with no measurement at all:

    a claim that a check in this repository, as it currently ships,
    fails right now is false the moment it is committed.

CCPR's own standard (CLAUDE.md, "Code Standards") is that the suite is green
before a commit. A test that is genuinely red against a real, unfixed defect
is reported and routed, never committed green-washed -- so a committed tree
never contains a failing shipped check. A live failure claim in that tree
therefore needs no verification run to be refuted: it is unconditionally
false. Derivable, so it is GENERATED here rather than STORED in prose.

The asymmetry is deliberate and is the reason only one direction is scanned.
A live PASSING claim ("clean today") is automatically TRUE under the same
invariant, so it cannot drift into falsehood the way a failing claim does. It
is out of scope for that reason, not by oversight.

## Living claim vs. dated history -- the discrimination, and how it was chosen

A naive "a docstring that says RED" detector is worthless here (measured
30.08.2026: 143 mentions of "red" across 29 test modules), and nearly all of
them are legitimate -- red proofs, mutation narratives, dated trajectory rows.
Frozen history is SUPPOSED to say what was true on its date.

The discriminator is not a keyword list and not a date pattern. It is the
question the sentence answers: WHAT IS THE CLAIM ABOUT, and IS IT BEING MADE
OR SHOWN? Four conditions must hold together, and each was chosen because a
real sentence in this tree is excluded by it:

1. **A now-anchor.** The sentence binds itself to the present state of the
   real repository: `today`, `currently`, `right now`, `at present`,
   `the real tree`, `the current tree`, `at HEAD`. A dated sentence anchors
   to its date instead and never satisfies this -- which is how frozen
   history is let through STRUCTURALLY, without a date-shaped exemption rule
   that would have to be maintained. Real instance excluded here:
   `test_check_all.py`'s `CompareAgainstZeroInsteadOfBaselineRedProofTest`,
   which says a pin "must go red against this mutated copy" and names
   30.08.2026 -- its object is a mutated scratch copy, not the tree.

2. **A present-indicative failure PREDICATE.** `is`/`are` (no modal, no past
   tense) followed directly by a failure-state adjective (`red`, `failing`,
   `broken`, `a failure`), with at most a short adverbial gap. This is a
   position test, not a bag of words: the failure word must sit in the
   predicate slot of a present-tense assertion. Real instances excluded here:
   `test_quality_scan.py`'s "nothing else records a failed run today
   (measured 28.08.2026: ...)" -- a now-anchor and a failure word, but the
   failure word is a noun modifier, not a predicate; and
   `test_agent_frontmatter.py`'s own "if this test goes red" -- `goes` is not
   a present-indicative copula, and the clause is conditional.

3. **Nothing quoted or emphasised.** Conditions 1 and 2 run against the
   sentence with `"..."`, `` `...` ``, `*...*` and `_..._` spans removed. A
   claim inside quotation marks is being SHOWN, not made. Real instances
   excluded here: `CHANGELOG.md`'s entry for this very work item, which
   quotes the one derivable claim as an italic example, and its next
   paragraph, which quotes the drifted sentence in order to report that it
   was corrected.

4. **A self-referential subject, before the copula.** `this`/`these`/`those`,
   a bare `it`, or a CamelCase test-class identifier. The sentences that
   actually drift name their own subject; a sentence whose subject is
   generic is describing the shape. Real instance excluded here:
   `test_absence_only_assertions.py`'s pin docstring, "a docstring claiming
   its own check is failing RIGHT NOW" -- `its` is not `it`, and there is no
   CamelCase before the copula. The requirement is BEFORE the copula rather
   than anywhere, because a self-reference in a trailing clause ("... and
   this module would report it") does not make the subject self-referential.

Conditions 3 and 4 exist because of a defect found the day this module was
built: the first version made it impossible to WRITE ABOUT the check. Three
sentences tripped it within the hour -- a CHANGELOG entry describing it, a
CHANGELOG paragraph quoting the drift it caught, and the docstring of the
inventory pin it moved. None was an edge case; documenting a check is the
normal case. The alternative -- three `# status-claim: exempt` markers on
day one -- would have been the drifting skip-list this module exists to
prevent.

**Both narrowings are load-bearing and neither is sufficient** (measured
30.08.2026): quotation-stripping alone lets the generic-subject sentence
through, and the subject rule alone lets the italic CHANGELOG example
through -- because that example's own quoted text contains "this" and "it".
`DescriptionIsNotAssertionTest` pins all three with the condition that
excludes each.

Run over the whole in-scope tree, the two conditions together produce exactly
the two known drifted sentences and nothing else -- the count of scanned files
is deliberately NOT pinned in prose here, for the same reason this module
exists. The three-condition
variant that also pattern-matched dates was DROPPED: no sentence in the tree
satisfies both a date stamp and a live failure predicate, so the date clause
was unreachable, and an exemption branch that never runs is not a guard.

## What this module does NOT prove

* **It does not run anything.** It reads prose and never invokes a test. It
  cannot tell you whether any given check actually passes; it relies on the
  green-suite invariant for that. If that invariant is ever abandoned, this
  module's whole argument goes with it.

* **The unanchored form is invisible.** "This test fails." with no now-anchor
  is not flagged, by construction -- `NoAnchorIsOutOfScopeTest` below pins
  that as a deliberate boundary, not an accident. Widening to unanchored
  present-tense claims was measured and rejected: it drags in the
  mutation-narrative sentences (`test_freeze_phase_docs.py`'s "is RED against
  the original, unswitched `sed -i ''` implementation") that are correct as
  written, and a rule that fires on correct prose teaches its readers to
  ignore it.

* **Every other register in the six-instance class is untouched.** Numbers
  (`check-all.baseline.tsv`'s note counts, a docstring restating a pinned
  constant), work-item status lines, and open-findings lists are NOT scanned.
  Their claims are derivable too, but each needs its own generator; this one
  closes the self-reported-failure-state slice only.

* **The gitignored registers are entirely out of reach.** `docs/HANDOVER.md`,
  `docs/.handover-archive/**` and `docs/workitems/**` are gitignored, so they
  are outside `--exclude-standard` and absent from every adopter's checkout. A
  shipped test cannot assert anything about a file that does not exist for
  the person running it, and making it pass silently when the file is missing
  is the fail-open shape this repository has removed twice. They are reported
  as out of scope, not covered.

* **It sees sentence form, not meaning.** The line between asserting a
  claim and describing one is drawn at quotation, emphasis and subject
  shape -- nothing here understands what a sentence means. An unquoted
  paraphrase with a self-referential subject ("this check is broken today",
  written as an example) is indistinguishable from the real thing and will
  be flagged; the answer there is an exemption marker on that line. The
  three pinned fixtures are the current edge of that line, not a proof that
  the line is in the right place.

* **A narrowed rule catches less.** Conditions 3 and 4 removed real
  coverage: a live failure claim about a NAMED but non-self-referential
  subject ("the conformance check is broken today") is no longer flagged.
  That was the price of making the check writable-about, and it is a price,
  not a free improvement.

* **Masking is Python-only.** `.sh`, `.md`, `.yml` and every other suffix
  are scanned as if the whole file were prose, embedded code included. That
  is why the scan is measurably clean rather than provably clean: a future
  shell script whose string literal happens to spell out a live failure
  claim would be flagged, and the answer would be an exemption marker on
  that line, not a wider mask.

* **A sentence is a heuristic unit.** Splitting is done on terminators, blank
  lines and literal `\n` escapes. A file that packs unrelated prose onto one
  logical line can still merge an anchor from one clause with a predicate
  from another; `agents/code-reviewer.md`'s single-line YAML `description:`
  was exactly that case before the `\n` split was added.
"""

import ast
import io
import re
import subprocess
import tokenize
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Condition 1: the sentence binds itself to the present state of the real
# repository. See the module docstring on why this, and not a date pattern,
# is what separates a living claim from frozen history.
NOW_ANCHOR_RE = re.compile(
    r"\b(?:today|currently|right\s+now|at\s+present|as\s+of\s+today)\b"
    r"|\bthe\s+(?:real|current|actual|live|shipped)\s+tree\b"
    r"|\bat\s+HEAD\b",
    re.IGNORECASE,
)

# Condition 2: present-indicative copula in the predicate slot, directly
# followed by a failure-state adjective. `is`/`are` only -- a modal (`must
# be`, `would be`), a past form (`was`, `were`) and a non-copular verb
# (`goes red`) all describe something other than the current state and are
# excluded by this shape, not by a separate exclusion list.
LIVE_FAILURE_PREDICATE_RE = re.compile(
    r"\b(?:is|are)\b"
    r"(?:\s+(?:not|now|still|already|currently|indeed|therefore|thus|also))*"
    r"\s+(?:an?\s+)?"
    r"(?:red|failing|broken|failures?)\b",
    re.IGNORECASE,
)

# Condition 3: a claim inside quotation or emphasis is EXHIBITED, not
# asserted. Stripping these spans is what lets a document QUOTE the drifted
# sentence in order to describe it -- a CHANGELOG entry, a docstring
# explaining this very rule. Without it the check makes it impossible to
# write about the check.
QUOTED_SPAN_RE = re.compile(
    r'"[^"\n]*"'
    r"|\u201c[^\u201d\n]*\u201d"
    r"|'[^'\n]*'"
    r"|`+[^`\n]*`+"
    r"|\*\*[^*\n]+\*\*"
    r"|\*[^*\n]+\*"
    r"|_[^_\n]+_"
)

# Condition 4: the claim needs a SELF-REFERENTIAL subject. The sentences
# that actually drift name their own subject -- `this`, `these`, a bare
# `it`, or a CamelCase test-class identifier. A sentence whose subject is
# generic ("a docstring claiming its own check ...", "exactly one is ...")
# is DESCRIBING the shape, not making the claim. Required to appear BEFORE
# the copula, so a self-reference in a trailing clause does not qualify.
SELF_REFERENCE_RE = re.compile(
    # Scoped inline flags, not a module-wide re.IGNORECASE: the demonstratives
    # are case-irrelevant ("This check ...", "this IS red"), but the CamelCase
    # alternative is a SHAPE and folding its case would match any two words.
    r"(?i:\b(?:this|these|those)\b)"
    r"|(?i:\bit\b)"
    r"|\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b"
)

# Candidate pre-filter. Used ONLY to prove that a negative fixture actually
# REACHED the discriminator: "no finding" is a verdict, and a verdict earned
# because the sentence was never a candidate proves nothing about the rule.
FAILURE_WORD_RE = re.compile(
    r"\b(?:red|fails?|failing|failed|failures?|broken)\b", re.IGNORECASE
)

# Exemption marker, mirroring test_absence_only_assertions.py's
# `# absence-only: exempt <category>` and test_external_tool_exit_status.py's
# `# exit-status: exempt <category>`. Line-scoped: a finding is dropped when
# ANY physical line the sentence spans carries a registered marker.
MARKER_RE = re.compile(
    r"(?:#|<!--)\s*status-claim:\s*exempt\s+([A-Za-z0-9_-]+)"
)

EXEMPTION_REASONS = {
    # No file needs this today: the prose mask already blanks Python
    # string literals, and this module states the claim shape without
    # instantiating it. The category exists for the case the mask cannot
    # reach -- prose in a NON-Python file (a CHANGELOG entry, a doc) that
    # must quote a live failure claim verbatim as evidence. Exercised by
    # ExemptionMarkerSuppressesAClaimTest; pinned unused by
    # ExemptionMarkersAreWellFormedTest.
    "self-fixture": (
        "prose that must quote a live failure claim verbatim as evidence"
    ),
}

# Sentence boundaries: a terminator followed by whitespace, a blank line, or
# a LITERAL backslash-n escape (single-line YAML scalars pack whole
# paragraphs behind those, and treating them as one sentence merged an
# anchor and a predicate from unrelated clauses -- a measured false positive
# in agents/code-reviewer.md).
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\\n")

# A terminator at the very END of a physical line also closes the sentence.
# Hand-wrapped prose puts no whitespace after the period, so the
# lookbehind-plus-`\s+` rule above never fires there, and the next line
# would be appended to the same sentence -- merging an anchor from one claim
# with a predicate from an unrelated one. That is the same false positive the
# literal `\n` split fixes for single-line YAML, in its across-lines form.
TERMINATOR_AT_LINE_END_RE = re.compile(r"""[.!?;]['")\]]*\s*$""")

# Files that cannot be decoded as UTF-8 are skipped. Skipping is only safe
# for genuinely binary content, so the suffix set is declared and asserted
# rather than inferred -- a NEW unreadable suffix must be a deliberate look,
# and a TEXT file that fails to decode must fail loudly.
BINARY_SUFFIXES = frozenset({".png"})

# The drifted state, pinned by commit. At this commit
# test_agent_frontmatter.py's module docstring and its
# AgentBashToolRequiredTest class docstring both assert the test is failing,
# while the module runs 26 tests green. The claim was never true: 961165f
# introduced these two sentences and fixed the three agents they name in the
# SAME commit, so the register was born stale rather than drifting into it.
DRIFT_FIXTURE_COMMIT = "8a6c172"
DRIFTED_REGISTER_PATH = "scripts/tests/test_agent_frontmatter.py"

DRIFT_WITNESS_SUBSTRINGS = (
    "is RED today for exactly these three reasons",
    "this IS red against the real tree",
)

# Real sentences from this tree that the rule must LET THROUGH, each pinned
# at the same commit and each excluded by a DIFFERENT one of the two
# conditions -- so the pass is attributable, not merely observed.
HISTORY_FIXTURES = (
    (
        "scripts/tests/test_quality_scan.py",
        "nothing\n    else records a failed run today (measured 28.08.2026",
        "predicate",
    ),
    (
        "scripts/tests/test_check_all.py",
        "the real baseline's single non-zero entry since 30.08.2026) must go red",
        "anchor",
    ),
    (
        "scripts/tests/test_freeze_phase_docs.py",
        "This is the one test in this module that is RED against the",
        "anchor",
    ),
)

# Real sentences from this tree that DESCRIBE or QUOTE the claim shape
# instead of asserting it -- all three written within an hour of the check
# being built, by someone documenting it, with nobody trying to break it.
# That is the point: writing ABOUT this check is the normal case, not an
# edge case, and a skip-list of exemptions for it would be the very drifting
# register this module exists to prevent. Each is pinned with the condition
# that excludes it, so a narrowing that stops carrying its own weight fails
# loudly rather than being absorbed.
DESCRIPTION_FIXTURES = (
    (
        'CHANGELOG.md',
        '**The inventory came first, and it narrowed the answer sharply.** Of every claim kind a register carries, exactly one is derivable with no measurement at all: *a check in this repository, as it ships, is failing right now*.',
        'quotation',
    ),
    (
        'CHANGELOG.md',
        'Caught: two sentences in `test_agent_frontmatter.py` claiming that module\'s Rule 5 check "is RED today" while it ran 26 tests green — the drift was live and tracked at the moment the check was written.',
        'quotation',
    ),
    (
        'scripts/tests/test_absence_only_assertions.py',
        'Bumped 58 -> 59, 30.08.2026 (R1): added test_live_status_claims.py, which refuses a docstring claiming its own check is failing RIGHT NOW while the suite is green.',
        'subject',
    ),
)

WITNESS_FILES_IN_SCOPE = (
    "scripts/tests/test_agent_frontmatter.py",
    "scripts/tests/test_live_status_claims.py",
    "CHANGELOG.md",
    "CLAUDE.md",
)


class Finding:
    """One live failure claim: the file that carries it, the physical line
    range of the sentence, and the sentence itself."""

    def __init__(self, label, start_line, end_line, sentence):
        self.label = label
        self.start_line = start_line
        self.end_line = end_line
        self.sentence = sentence

    def __repr__(self):
        return "{}:{}-{}: {}".format(
            self.label, self.start_line, self.end_line, self.sentence[:120]
        )


def _flatten(buffer):
    return " ".join(" ".join(buffer).split())


def iter_sentences(text):
    """Yields `(sentence, start_line, end_line)` over `text`, 1-based lines.

    Sentences are accumulated across physical lines so a claim wrapped over
    three lines of a docstring is still seen as one sentence -- both drifted
    instances this module was written for are wrapped that way.
    """
    lines = text.split("\n")
    buffer = []
    start_line = None
    for lineno, raw in enumerate(lines, start=1):
        if not raw.strip():
            if buffer:
                # end_line is the last CONTENT line, not the blank one.
                yield _flatten(buffer), start_line, lineno - 1
                buffer = []
                start_line = None
            continue
        parts = SENTENCE_SPLIT_RE.split(raw)
        for index, part in enumerate(parts):
            if part is None:
                continue
            if start_line is None:
                start_line = lineno
            buffer.append(part)
            if index != len(parts) - 1:
                yield _flatten(buffer), start_line, lineno
                buffer = []
                start_line = None
        if buffer and TERMINATOR_AT_LINE_END_RE.search(buffer[-1]):
            yield _flatten(buffer), start_line, lineno
            buffer = []
            start_line = None
    if buffer:
        yield _flatten(buffer), start_line, len(lines)


def asserted_text(sentence):
    """The part of `sentence` that is being ASSERTED: quoted and emphasised
    spans removed, because their content is exhibited rather than claimed."""
    return QUOTED_SPAN_RE.sub(" ", sentence)


def is_live_failure_claim(sentence):
    """All four conditions, in the order the module docstring states them.

    Conditions 1 and 2 run against `asserted_text`, not the raw sentence, so
    a quoted claim never reaches them. Condition 4 then requires the subject
    to be self-referential.
    """
    probe = asserted_text(sentence)
    if not NOW_ANCHOR_RE.search(probe):
        return False
    predicate = LIVE_FAILURE_PREDICATE_RE.search(probe)
    if not predicate:
        return False
    return bool(SELF_REFERENCE_RE.search(probe[:predicate.start()]))


def exemption_in_range(lines, start_line, end_line):
    """Returns the marker category found on any line the sentence spans, or
    None. Mirrors test_absence_only_assertions.py's `find_exemption`."""
    for ln in range(start_line, end_line + 1):
        if ln < 1 or ln > len(lines):
            continue
        match = MARKER_RE.search(lines[ln - 1])
        if match:
            return match.group(1)
    return None


def python_prose_lines(text):
    """1-based line numbers of PROSE in a Python source: docstrings and `#`
    comments. A string literal in a test body is DATA -- a fixture the module
    feeds to its own detector -- not an assertion about the tree, and
    scanning it makes every scanner that quotes its own subject flag itself.

    Raises SyntaxError / TokenizeError to the caller, which falls back to
    scanning the whole file: a file this cannot parse must be scanned MORE,
    never less.
    """
    prose = set()
    for node in ast.walk(ast.parse(text)):
        body = getattr(node, "body", None)
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ) or not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            prose.update(range(first.lineno, first.end_lineno + 1))
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            prose.add(token.start[0])
    return prose


def prose_only(text, suffix):
    """Position-preserving mask: non-prose lines are blanked, never removed,
    so every reported line number still points at the real file."""
    if suffix != ".py":
        return text
    try:
        prose = python_prose_lines(text)
    except (SyntaxError, tokenize.TokenError, ValueError, RecursionError):
        # IndentationError is a SyntaxError subclass and needs no entry.
        # ValueError covers embedded NUL bytes, RecursionError pathological
        # nesting. Every one of them falls back to scanning the WHOLE file:
        # a file this cannot parse must be scanned more, never less.
        return text
    return "\n".join(
        line if lineno in prose else ""
        for lineno, line in enumerate(text.split("\n"), start=1)
    )


def scan_text(text, label, suffix=""):
    """Text-in, not path-in: the same seam test_instinct_registers_agree.py
    uses, so a historical copy pulled with `git show` runs through the exact
    production code path without any tracked file being touched."""
    lines = text.split("\n")
    findings = []
    for sentence, start_line, end_line in iter_sentences(prose_only(text, suffix)):
        if not is_live_failure_claim(sentence):
            continue
        if exemption_in_range(lines, start_line, end_line):
            continue
        findings.append(Finding(label, start_line, end_line, sentence))
    return findings


def in_scope_files(repo_root=REPO_ROOT):
    """Enumerates version-controlled paths: tracked files PLUS untracked
    files git does not ignore. A file staged for its first commit carries
    the same drift risk as one already in, and a gate that cannot see the
    change being made is a gate that arrives one commit late.

    `.gitignore` is the scope boundary, which is also the honest one: it is
    exactly what an adopter's checkout contains.

    NUL-delimited, because a path may legally contain a newline and a
    whitespace `split()` would silently shrink the scope.
    """
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [rel for rel in result.stdout.split("\0") if rel]


def scan_repo(repo_root=REPO_ROOT):
    """Returns `(findings, scanned, skipped)`.

    `skipped` is returned rather than swallowed: a file dropped from the scan
    is a hole in the scope, and a scan that reports no scope is not a pass
    (KA-G-017).
    """
    findings = []
    scanned = []
    skipped = []
    for rel in in_scope_files(repo_root):
        path = repo_root / rel
        if not path.is_file():
            # A gitlink (submodule) or a symlink with a missing target.
            # Routed to `skipped` rather than dropped: ScopeTest asserts
            # only declared binary suffixes may land there, so this fails
            # loudly instead of shrinking the scope in silence.
            skipped.append(rel)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            skipped.append(rel)
            continue
        scanned.append(rel)
        findings.extend(scan_text(text, rel, path.suffix))
    return findings, scanned, skipped


def read_git_show(ref_and_path):
    """Reads a file at a historical ref. Verifies the ref RESOLVES first
    (G-082), so a shallow clone fails with a named error instead of an opaque
    `git show` failure -- the same guard
    test_bsd_gnu_portability.py's `_read_git_show` carries."""
    ref = ref_and_path.split(":", 1)[0]
    subprocess.run(
        ["git", "rev-parse", "--verify", ref + "^{commit}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    result = subprocess.run(
        ["git", "show", ref_and_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


# --------------------------------------------------------------------------
# Scope -- a run that verified nothing must never report success
# --------------------------------------------------------------------------


class ScopeTest(unittest.TestCase):
    """The scan's own denominator. Without these, "no live status claims" is
    indistinguishable from "no files were read"."""

    @classmethod
    def setUpClass(cls):
        _, cls.scanned, cls.skipped = scan_repo()

    def test_the_scan_covers_a_non_empty_scope(self):
        self.assertTrue(
            self.scanned,
            "git ls-files returned no readable tracked file -- this is a "
            "could-not-run, not a pass",
        )

    def test_the_files_that_carry_the_class_are_in_scope(self):
        missing = [rel for rel in WITNESS_FILES_IN_SCOPE if rel not in self.scanned]
        self.assertFalse(
            missing,
            "enumeration no longer reaches the files this rule exists for: "
            "{}".format(missing),
        )

    def test_every_enumerated_path_is_scanned_or_skipped(self):
        # Closes the arithmetic: without it, a path could leave the
        # enumeration through a branch neither list records.
        self.assertEqual(
            len(in_scope_files()),
            len(self.scanned) + len(self.skipped),
            "a path left the enumeration without being counted as either "
            "scanned or skipped",
        )

    def test_only_binary_files_are_skipped(self):
        unexpected = [
            rel for rel in self.skipped if Path(rel).suffix not in BINARY_SUFFIXES
        ]
        self.assertFalse(
            unexpected,
            "a file that is not a declared binary type could not be decoded "
            "and was dropped from the scan: {}".format(unexpected),
        )


# --------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------


class NoLiveFailureClaimTest(unittest.TestCase):
    """A file in scope must not assert that a check in this repository
    fails right now. See the module docstring for why such a claim is
    unconditionally false in a committed tree rather than merely suspect."""

    def test_no_file_in_scope_claims_a_check_is_failing_now(self):
        findings, _, _ = scan_repo()
        self.assertFalse(
            findings,
            "live failure claim(s) in tracked prose -- the suite is green, so "
            "each of these states something that is not true. Correct the "
            "sentence, or mark it `# status-claim: exempt <category>` with a "
            "registered category:\n" + "\n".join(repr(f) for f in findings),
        )


class ExemptionMarkersAreWellFormedTest(unittest.TestCase):
    """Every marker in the tree must name a registered category, and the set
    of files carrying one is pinned -- an exemption is a deliberate act, so a
    new one must be visible rather than absorbed."""

    @classmethod
    def setUpClass(cls):
        cls.markers = []
        for rel in in_scope_files():
            path = REPO_ROOT / rel
            if not path.is_file() or path.suffix in BINARY_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            # Same prose mask the scan itself uses: a marker inside a string
            # literal is a synthetic fixture for the marker mechanism, not a
            # live exemption, and counting it would make this module's own
            # tests of the mechanism register as uses of it.
            masked = prose_only(text, path.suffix)
            for lineno, line in enumerate(masked.split("\n"), start=1):
                match = MARKER_RE.search(line)
                if match:
                    cls.markers.append((rel, lineno, match.group(1)))

    def test_every_marker_category_is_registered(self):
        unknown = [m for m in self.markers if m[2] not in EXEMPTION_REASONS]
        self.assertFalse(
            unknown,
            "marker(s) naming a category with no entry in EXEMPTION_REASONS: "
            "{}".format(unknown),
        )

    def test_the_set_of_exempted_files_is_pinned(self):
        self.assertEqual(
            sorted({m[0] for m in self.markers}),
            [],
            "the set of files carrying a status-claim exemption moved; no "
            "file needs one today (this module states the shape without "
            "instantiating it), so a new exemption is a deliberate decision "
            "and must be visible here",
        )


# --------------------------------------------------------------------------
# Red proof, both directions, against real content from this tree
# --------------------------------------------------------------------------


class DriftedRegisterHistoricalRedProofTest(unittest.TestCase):
    """The living claim is CAUGHT. Pulled as a text copy from
    DRIFT_FIXTURE_COMMIT, where test_agent_frontmatter.py's own docstrings
    twice assert the module is red while it runs 26 tests green."""

    @classmethod
    def setUpClass(cls):
        cls.drifted_text = read_git_show(
            "{}:{}".format(DRIFT_FIXTURE_COMMIT, DRIFTED_REGISTER_PATH)
        )

    def test_the_fixture_still_carries_both_drifted_sentences(self):
        # Fixture integrity before measurement: if the pinned commit no
        # longer contains these literals, the proof below is measuring
        # something else and must say so loudly (G-141).
        for needle in DRIFT_WITNESS_SUBSTRINGS:
            self.assertIn(needle, self.drifted_text)

    def test_both_drifted_claims_are_flagged_at_the_pinned_commit(self):
        findings = scan_text(self.drifted_text, DRIFTED_REGISTER_PATH, ".py")
        self.assertEqual(
            2,
            len(findings),
            "expected exactly the two known drifted sentences, got: "
            "{}".format(findings),
        )
        flagged = " ".join(f.sentence for f in findings)
        for needle in DRIFT_WITNESS_SUBSTRINGS:
            self.assertIn(" ".join(needle.split()), flagged)

    def test_the_same_file_in_the_working_tree_is_clean(self):
        # The other direction. Without it, "flagged at the pinned commit"
        # could be a detector that flags this file unconditionally.
        # Reads the WORKING TREE, not `git show HEAD:` -- the correction
        # is what has to be clean, and until it is committed HEAD still
        # carries the drifted text this proof deliberately pins.
        current = (REPO_ROOT / DRIFTED_REGISTER_PATH).read_text(encoding="utf-8")
        self.assertEqual([], scan_text(current, DRIFTED_REGISTER_PATH, ".py"))


class HistoryIsLetThroughTest(unittest.TestCase):
    """Frozen history is PASSED. Three real sentences from this tree, each
    pinned at the same commit, each a genuine candidate (it contains failure
    vocabulary) and each excluded by a named condition -- so the pass is
    attributed, not merely observed."""

    def _sentence_for(self, rel, needle):
        text = prose_only(read_git_show("{}:{}".format(DRIFT_FIXTURE_COMMIT, rel)), ".py")
        flat_needle = " ".join(needle.split())
        for sentence, _, _ in iter_sentences(text):
            if flat_needle in sentence:
                return sentence
        self.fail(
            "fixture sentence no longer present in {} at {}: {!r}".format(
                rel, DRIFT_FIXTURE_COMMIT, needle
            )
        )

    def test_each_history_fixture_is_a_candidate_and_is_excluded_by_its_condition(self):
        for rel, needle, excluded_by in HISTORY_FIXTURES:
            with self.subTest(file=rel):
                sentence = self._sentence_for(rel, needle)
                self.assertTrue(
                    FAILURE_WORD_RE.search(sentence),
                    "fixture carries no failure vocabulary, so it never "
                    "reached the discriminator and proves nothing",
                )
                self.assertFalse(is_live_failure_claim(sentence))
                if excluded_by == "anchor":
                    self.assertIsNone(NOW_ANCHOR_RE.search(sentence))
                else:
                    self.assertIsNone(LIVE_FAILURE_PREDICATE_RE.search(sentence))

    def test_the_whole_history_carrying_files_are_clean_at_the_pinned_commit(self):
        for rel, _, _ in HISTORY_FIXTURES:
            with self.subTest(file=rel):
                text = read_git_show("{}:{}".format(DRIFT_FIXTURE_COMMIT, rel))
                self.assertEqual([], scan_text(text, rel, ".py"))


# --------------------------------------------------------------------------
# The discriminator, isolated
# --------------------------------------------------------------------------


class PredicatePositionDiscriminatesTest(unittest.TestCase):
    """The failure word must sit in the PREDICATE slot of a present-tense
    assertion. Each negative below is the same claim in a grammatical form
    that describes something other than the current state -- a bag-of-words
    detector accepts all four."""

    def test_a_present_indicative_predicate_is_a_claim(self):
        self.assertTrue(is_live_failure_claim("This check is red today."))

    def test_a_modal_is_not_a_claim(self):
        self.assertFalse(is_live_failure_claim("This check must be red today."))

    def test_a_past_tense_form_is_not_a_claim(self):
        self.assertFalse(is_live_failure_claim("This check was red today."))

    def test_a_non_copular_verb_is_not_a_claim(self):
        self.assertFalse(is_live_failure_claim("If this check goes red today."))

    def test_a_failure_word_outside_the_predicate_is_not_a_claim(self):
        self.assertFalse(
            is_live_failure_claim("Each one needs its own red proof today.")
        )


class NoAnchorIsOutOfScopeTest(unittest.TestCase):
    """A DECLARED boundary, pinned so it cannot be mistaken for coverage: an
    unanchored present-tense failure claim is NOT flagged. Widening to catch
    it was measured and rejected -- it drags in the mutation narratives that
    are correct as written (see the module docstring)."""

    def test_an_unanchored_failure_claim_is_not_flagged(self):
        sentence = "This check is red."
        self.assertTrue(LIVE_FAILURE_PREDICATE_RE.search(sentence))
        self.assertFalse(is_live_failure_claim(sentence))

    def test_the_same_sentence_with_an_anchor_is_flagged(self):
        self.assertTrue(is_live_failure_claim("This check is red right now."))


class DescriptionIsNotAssertionTest(unittest.TestCase):
    """Writing ABOUT the check must not trip it. Three real sentences from
    the tree, each a genuine candidate under conditions 1+2 alone, each
    excluded by a named later condition -- so the pass is attributed, not
    merely observed."""

    def _sentence_from_source(self, rel, expected):
        path = REPO_ROOT / rel
        text = prose_only(path.read_text(encoding="utf-8"), path.suffix)
        for sentence, _, _ in iter_sentences(text):
            if sentence == expected:
                return sentence
        self.fail(
            "fixture sentence no longer present in {} -- the pinned literal "
            "has drifted from its source and this test is measuring "
            "nothing:\n{!r}".format(rel, expected)
        )

    def test_each_fixture_would_have_been_flagged_by_conditions_1_and_2(self):
        # Without this, "not flagged" could mean the sentence was never a
        # candidate, which would prove nothing about the narrowing.
        for rel, sentence, _ in DESCRIPTION_FIXTURES:
            with self.subTest(source=rel, sentence=sentence[:40]):
                self._sentence_from_source(rel, sentence)
                self.assertTrue(NOW_ANCHOR_RE.search(sentence))
                self.assertTrue(LIVE_FAILURE_PREDICATE_RE.search(sentence))

    def test_each_fixture_is_excluded_by_the_condition_it_names(self):
        for rel, sentence, excluded_by in DESCRIPTION_FIXTURES:
            with self.subTest(source=rel, sentence=sentence[:40]):
                self.assertFalse(is_live_failure_claim(sentence))
                probe = asserted_text(sentence)
                predicate = LIVE_FAILURE_PREDICATE_RE.search(probe)
                if excluded_by == "quotation":
                    # The claim sat inside quotes or emphasis; stripping
                    # those removes the predicate entirely.
                    self.assertIsNone(predicate)
                else:
                    # The predicate survives quotation-stripping; what is
                    # missing is a self-referential subject before it.
                    self.assertIsNotNone(predicate)
                    self.assertIsNone(
                        SELF_REFERENCE_RE.search(probe[:predicate.start()])
                    )

    def test_both_narrowings_are_load_bearing(self):
        # Neither alone carries all three: measured 30.08.2026, quotation
        # alone lets the generic-subject fixture through and self-reference
        # alone lets a quoted example through -- because that example's own
        # quoted text contains "this" and "it".
        by_quotation = {
            s for _, s, why in DESCRIPTION_FIXTURES if why == "quotation"
        }
        by_subject = {
            s for _, s, why in DESCRIPTION_FIXTURES if why == "subject"
        }
        self.assertTrue(by_quotation, "no fixture exercises quotation-stripping")
        self.assertTrue(by_subject, "no fixture exercises the subject rule")
        for sentence in by_subject:
            # Quotation-stripping alone would NOT have saved this one.
            self.assertIsNotNone(
                LIVE_FAILURE_PREDICATE_RE.search(asserted_text(sentence))
            )
        self.assertTrue(
            any(
                SELF_REFERENCE_RE.search(s)
                for s in by_quotation
            ),
            "no quoted fixture carries a self-reference token, so the "
            "measurement that the subject rule alone is insufficient no "
            "longer has a witness",
        )


class SelfReferentialSubjectTest(unittest.TestCase):
    """Condition 4 in isolation: the same predicate, with and without a
    subject that points at something in this repository."""

    def test_a_demonstrative_subject_is_a_claim(self):
        self.assertTrue(is_live_failure_claim("This check is red today."))

    def test_a_test_class_name_is_a_claim(self):
        # The elided-subject case: the copula is coordinated onto an earlier
        # clause, so nothing sits immediately before it. This is the shape
        # the original module-docstring drift had.
        self.assertTrue(
            is_live_failure_claim(
                "AgentBashToolRequiredTest asserts zero violations and is "
                "red today."
            )
        )

    def test_a_generic_subject_is_not_a_claim(self):
        self.assertFalse(
            is_live_failure_claim("A docstring claiming its own check is "
                                  "red today would be refused.")
        )

    def test_a_self_reference_after_the_predicate_does_not_qualify(self):
        self.assertFalse(
            is_live_failure_claim("A check is red today, and this module "
                                  "would report it.")
        )


class QuotationIsExhibitionTest(unittest.TestCase):
    """Condition 3 in isolation: the same claim, asserted and quoted."""

    def test_a_bare_claim_is_a_claim(self):
        self.assertTrue(is_live_failure_claim("This check is red today."))

    def test_a_double_quoted_claim_is_not(self):
        self.assertFalse(
            is_live_failure_claim('This module refuses "the check is red '
                                  'today" as a sentence.')
        )

    def test_a_backticked_claim_is_not(self):
        self.assertFalse(
            is_live_failure_claim("This module refuses `the check is red "
                                  "today` as a sentence.")
        )

    def test_an_emphasised_claim_is_not(self):
        self.assertFalse(
            is_live_failure_claim("This module refuses *the check is red "
                                  "today* as a sentence.")
        )


class SentenceSegmentationTest(unittest.TestCase):
    """Both drifted instances wrap over three docstring lines, so a
    line-at-a-time scan would have missed both. The literal `\\n` split is
    the measured fix for agents/code-reviewer.md's single-line YAML
    description, where an anchor and a predicate from unrelated clauses were
    merged into one sentence."""

    def test_a_claim_wrapped_over_lines_is_seen_as_one_sentence(self):
        text = "Some prose\nand this check\nis red today for a reason.\nMore."
        self.assertTrue(scan_text(text, "x"))

    def test_a_terminator_at_end_of_line_closes_the_sentence(self):
        # Regression: hand-wrapped prose puts no space after the period, so
        # the lookbehind-plus-whitespace rule alone left the sentence open
        # and appended the NEXT line to it. Neither line below is a claim on
        # its own -- the first carries the anchor, the second the predicate
        # -- but merged they were reported as one, a false positive.
        text = "This describes behavior today.\nThat different check is broken."
        self.assertEqual(
            ["This describes behavior today.", "That different check is broken."],
            [sentence for sentence, _, _ in iter_sentences(text)],
        )
        self.assertEqual([], scan_text(text, "x"))

    def test_a_blank_line_reports_the_last_content_line_not_the_blank_one(self):
        text = "this check is red today\n\nunrelated"
        (_, start_line, end_line), = [
            s for s in iter_sentences(text) if "red" in s[0]
        ]
        self.assertEqual((1, 1), (start_line, end_line))

    def test_a_literal_backslash_n_separates_clauses(self):
        text = r"nothing here is broken.\nA later clause mentions today."
        self.assertEqual([], scan_text(text, "x"))

    def test_a_blank_line_separates_clauses(self):
        text = "nothing here is broken\n\nA later clause mentions today"
        self.assertEqual([], scan_text(text, "x"))


class ExemptionMarkerSuppressesAClaimTest(unittest.TestCase):
    """The marker must actually work, and must be scoped to the sentence's
    own lines rather than to the whole file."""

    def test_a_marked_line_suppresses_the_finding(self):
        text = "This check is red today.  # status-claim: exempt self-fixture"
        self.assertEqual([], scan_text(text, "x"))

    def test_an_unregistered_category_still_suppresses_but_is_caught_elsewhere(self):
        # The marker regex accepts any category name; the registry is
        # enforced separately by ExemptionMarkersAreWellFormedTest, so a typo
        # cannot silently become a permanent exemption.
        text = "This check is red today.  # status-claim: exempt typo-here"
        self.assertEqual([], scan_text(text, "x"))
        self.assertNotIn("typo-here", EXEMPTION_REASONS)

    def test_a_marker_on_an_unrelated_line_does_not_suppress(self):
        text = (
            "# status-claim: exempt self-fixture\n"
            "\n"
            "This check is red today."
        )
        self.assertTrue(scan_text(text, "x"))


if __name__ == "__main__":
    unittest.main()
