"""test_frontmatter_examples_match_the_lint.py -- WI-0121: binds every
```yaml frontmatter EXAMPLE shipped in commands/, docs/ and templates/ to
the two enums scripts/phase-docs-lint.sh actually enforces (VALID_PHASES,
VALID_STATUS).

## Why this exists

WI-0121 was filed against a different, retracted claim (five files
"self-declaring" as phase docs while never being validated -- a false
positive: the "violations" sat in ```yaml example fences, not real
frontmatter, and re-measured with a frontmatter parser the only files
carrying real `phase:` frontmatter in this repo are the six shipped
templates/QA_SKELETON/*.md, all valid). What survived re-measurement is the
INVERSE defect: the generator commands and docs that TEACH authors what to
write in a phase-doc's frontmatter prescribe values phase-docs-lint.sh then
rejects -- `phase: p0` (lowercase), `phase: 3` (no P prefix),
`status: active | partial | pending` (partial/pending outside the enum),
`status: living | complete` (complete outside the enum), etc. A document
written by following one of these examples literally would fail the lint
that is supposed to accept it.

## Why a corpus test, not a one-off fix

Re-typing the two enums into this test would recreate the exact defect
shape this file exists to close: a hand-typed copy source and enforcement
disagreeing with each other. `_valid_phases()` / `_valid_status()` below
parse `VALID_PHASES="..."` / `VALID_STATUS="..."` straight out of
scripts/phase-docs-lint.sh's own source text -- there is exactly one place
in this repository that defines what a valid phase or status value is, and
this test reads it from there every run.

## What counts as an example, and what does not

A "phase-doc frontmatter example" is a ```yaml fence containing a top-level
`phase:` key. Documents that carry their OWN, unrelated frontmatter schema
under a `status:` key with no accompanying `phase:` key in the same block
(an ADR's `kind: adr` header, a docs/memory/ file under MEMORY_SCHEMA.md,
Manual/'s memory-instincts status field) are a different vocabulary
entirely and are correctly invisible to this test -- validating them against
VALID_STATUS would be checking the wrong schema, not finding a bug.

`status:` is only validated inside a block that ALSO carries `phase:` --
that is what identifies the block as a phase-doc-schema example rather than
some other document's own header.

No exemption remains. This test used to carry one, keyed on `kind:
risk-detail`: `commands/p4-sprint.md`'s risk-detail block put the RISK
lifecycle (`open | mitigated | accepted | closed`) under the field name
`status`, colliding with the document-status lifecycle this test enforces.
The fix moved the risk lifecycle to its own `risk_status:` field (see
`commands/p4-sprint.md`) and gave the risk-detail block a real document
`status: living` -- a risk detail file is designed to keep growing via its
`## History` section for as long as the risk is tracked, which is exactly
what `living` means in `templates/PHASE_DOC_SCHEMA.md`. With the collision
gone, `status:` means the same thing in every block this test scans, `kind:
risk-detail` included, and RiskDetailHasNoStatusExemptionTest pins that no
kind-based special case has crept back in.

## How a value is parsed out of a line

`phase: p0` / `phase: 3` -- a bare token.
`status: active | partial | pending` -- pipe-separated alternatives IN THE
VALUE are each an independent candidate (matches how a document author
would read "pick one of these").
`status: complete    # draft | complete | needs-rework` -- a trailing
comment that is ITSELF a pipe-separated list is also read as a candidate
set. Decided (not assumed): PROJECT_PHASES.md's canonical example prints
exactly this shape, `status: complete    # draft | complete | needs-rework`,
and every value in that comment -- not just the one after the colon -- is
text a document author copying the example verbatim could reasonably lift
into their own frontmatter. A comment that is plain prose with no `|`
(`# current sprint plan, replaced each call`) is left alone -- there is no
enumerated candidate to extract from it.
"""

import re
import unittest
from pathlib import Path

# WI-0126 tranche 5: this module's own _read_enum was the FIRST instance of
# this parser shape (space-separated NAME="a b c" shell-string constants) --
# lifted into test_phase_docs_lint.py as read_enum(varname, script_path) so
# test_manual_lint.py's VALID_KINDS and test_anchor.py's LIVING_FILES reuse
# it instead of each growing a near-identical regex. Established cross-
# test-module pattern (test_anchor.py imports read_phase_folders the same
# way). Tradeoff: this module now needs `-t .` on `unittest discover` too
# (CONTRIBUTING.md's "Run the test suite"). It joins that already-documented
# set; the running count lives in CONTRIBUTING, not here, so it cannot go
# stale in a comment nobody re-reads.
from .test_phase_docs_lint import read_enum as _read_enum

REPO_ROOT = Path(__file__).resolve().parents[2]
LINT_SCRIPT = REPO_ROOT / "scripts" / "phase-docs-lint.sh"

# The kind that used to be exempted from status validation (see the module
# docstring). No longer special-cased anywhere in this module -- kept only
# as the literal RiskDetailHasNoStatusExemptionTest builds its synthetic
# block against, so that test names the same genre the old exemption did.
RISK_DETAIL_KIND = "risk-detail"

# Directories walked for ```yaml examples. docs/workitems/ is deliberately
# excluded: those are meta-reports ABOUT this corpus (this very item's own
# WI-0121.md quotes some of the lines below in prose), not part of the
# shipped generator surface itself, and are gitignored working state rather
# than something a project author is taught to copy from -- scanning them
# would risk a future work-item write-up that quotes an offending line
# verbatim producing a false failure here. Manual/ is out of scope too: the
# task that authored this test is explicitly barred from touching it, and
# the corpus this test binds to is the set of GENERATOR commands/docs/
# templates, which Manual/ documents rather than belongs to.
SCAN_ROOTS = ("commands", "docs", "templates")
EXCLUDED_DIR = REPO_ROOT / "docs" / "workitems"

YAML_FENCE_RE = re.compile(r"```yaml\n(.*?\n)```", re.DOTALL)
FIELD_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):[ \t]*(.*?)[ \t]*$")
CANDIDATE_TOKEN_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9_-]*)")


def _iter_target_files():
    for root_name in SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if EXCLUDED_DIR in path.parents:
                continue
            yield path


def _extract_candidates(raw_value):
    """Splits a field's raw text (everything after 'key:' on its line) into
    candidate value tokens: each pipe-separated alternative in the value
    itself, plus -- only when the trailing comment is ITSELF a
    pipe-separated list -- each alternative named there too. Returns a list
    of (token, source) pairs, source in {"value", "comment"}."""
    if "#" in raw_value:
        value_part, comment_part = raw_value.split("#", 1)
    else:
        value_part, comment_part = raw_value, ""

    candidates = []
    for tok in value_part.split("|"):
        tok = tok.strip()
        if tok:
            candidates.append((tok, "value"))

    if "|" in comment_part:
        for tok in comment_part.split("|"):
            m = CANDIDATE_TOKEN_RE.match(tok.strip())
            if m:
                candidates.append((m.group(1), "comment"))

    return candidates


def _status_violations(blocks, valid_status):
    """Every `status:` value across `blocks` (an iterable of (path, fields))
    that is not in valid_status. No `kind` is special-cased -- a block's
    `status:` always means the document-status enum, including a `kind:
    risk-detail` block (see RiskDetailHasNoStatusExemptionTest)."""
    violations = []
    for path, fields in blocks:
        for raw_value, line_no in fields.get("status", []):
            for token, source in _extract_candidates(raw_value):
                if token not in valid_status:
                    violations.append(
                        "{}:{}  status: {!r} ({}) not in {}".format(
                            path, line_no, token, source, sorted(valid_status),
                        )
                    )
    return violations


def _iter_frontmatter_blocks():
    """Yields (path, fields, block_start_line) for every ```yaml fence that
    contains a top-level `phase:` key. fields maps field name -> list of
    (raw_value, line_no) -- a block-scoped dict, so a risk-detail block's
    `kind:` is read from the SAME block as its `status:`, never a different
    one in the same file."""
    for path in _iter_target_files():
        text = path.read_text(encoding="utf-8")
        for m in YAML_FENCE_RE.finditer(text):
            block_text = m.group(1)
            block_start_offset = m.start(1)
            fields = {}
            offset = block_start_offset
            for line in block_text.split("\n"):
                fm = FIELD_LINE_RE.match(line)
                if fm:
                    key, val = fm.group(1), fm.group(2)
                    line_no = text.count("\n", 0, offset) + 1
                    fields.setdefault(key, []).append((val, line_no))
                offset += len(line) + 1
            if "phase" in fields:
                yield path, fields


class PhaseValueTest(unittest.TestCase):
    """Every `phase:` value in a phase-doc frontmatter example must be
    accepted by phase-docs-lint.sh's own VALID_PHASES."""

    def test_every_phase_value_in_examples_is_valid(self):
        valid_phases = _read_enum("VALID_PHASES", LINT_SCRIPT)
        violations = []
        for path, fields in _iter_frontmatter_blocks():
            for raw_value, line_no in fields["phase"]:
                for token, source in _extract_candidates(raw_value):
                    if token not in valid_phases:
                        violations.append(
                            "{}:{}  phase: {!r} ({}) not in {}".format(
                                path.relative_to(REPO_ROOT), line_no,
                                token, source, sorted(valid_phases),
                            )
                        )
        if violations:
            self.fail(
                "phase value(s) outside VALID_PHASES:\n" + "\n".join(violations)
            )


class StatusValueTest(unittest.TestCase):
    """Every `status:` value in a phase-doc frontmatter example (a block
    that also carries `phase:`) must be accepted by VALID_STATUS. No kind
    is special-cased, `kind: risk-detail` included -- see
    RiskDetailHasNoStatusExemptionTest and the module docstring."""

    def test_every_status_value_in_examples_is_valid(self):
        valid_status = _read_enum("VALID_STATUS", LINT_SCRIPT)
        blocks = (
            (path.relative_to(REPO_ROOT), fields)
            for path, fields in _iter_frontmatter_blocks()
        )
        violations = _status_violations(blocks, valid_status)
        if violations:
            self.fail(
                "status value(s) outside VALID_STATUS:\n" + "\n".join(violations)
            )


class RiskDetailHasNoStatusExemptionTest(unittest.TestCase):
    """Pins the state after the risk-lifecycle/document-status collision was
    fixed: a `kind: risk-detail` block with an out-of-enum `status:` is
    reported exactly like any other block. Built on a synthetic block, not
    the real corpus -- the real corpus's risk-detail block is now valid
    (`status: living`) precisely because the fix worked, so a corpus-only
    test could not tell "no exemption left" apart from "nothing to catch
    right now". This test would fail again the moment a kind-based special
    case creeps back into `_status_violations`/StatusValueTest."""

    def test_an_out_of_enum_status_in_a_risk_detail_block_is_reported(self):
        valid_status = _read_enum("VALID_STATUS", LINT_SCRIPT)
        synthetic_blocks = [
            (
                "synthetic/RISK-01.md",
                {
                    "phase": [("P4", 1)],
                    "kind": [(RISK_DETAIL_KIND, 2)],
                    # The OLD risk-lifecycle value that used to live under
                    # `status:` before the risk_status: split -- still
                    # outside VALID_STATUS, still must be reported.
                    "status": [("open", 3)],
                },
            )
        ]
        violations = _status_violations(synthetic_blocks, valid_status)
        self.assertTrue(
            violations,
            "a kind: risk-detail block with status: 'open' must be "
            "flagged like any other block -- no exemption should remain",
        )


if __name__ == "__main__":
    unittest.main()
