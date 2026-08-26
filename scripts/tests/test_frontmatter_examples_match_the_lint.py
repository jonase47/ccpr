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

One value is deliberately exempted: `commands/p4-sprint.md`'s
`kind: risk-detail` block's `status: open | mitigated | accepted | closed`
is the RISK lifecycle, not the document-status lifecycle -- a different axis
that happens to collide on the field name `status`. The exemption is keyed
narrowly on `kind: risk-detail` (not on "any block containing a pipe"), see
`RISK_DETAIL_KIND` below, and RiskDetailExemptionIsNarrowTest proves the
exemption is doing real, load-bearing work rather than being vacuously true.

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

REPO_ROOT = Path(__file__).resolve().parents[2]
LINT_SCRIPT = REPO_ROOT / "scripts" / "phase-docs-lint.sh"

# The genre this test exempts from status validation -- narrow and named,
# not a general "ignore any pipe-separated status". See the module
# docstring's "risk-detail" paragraph and RiskDetailExemptionIsNarrowTest.
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


def _read_enum(varname):
    """Reads VALID_PHASES / VALID_STATUS out of phase-docs-lint.sh's own
    source text -- never re-typed here. Fails loudly (not silently returns
    an empty set) if the script's shape changes underneath this test."""
    text = LINT_SCRIPT.read_text(encoding="utf-8")
    m = re.search(r'^{}="([^"]*)"'.format(re.escape(varname)), text, re.MULTILINE)
    if not m:
        raise AssertionError(
            "could not find {}=\"...\" in {}".format(varname, LINT_SCRIPT)
        )
    return set(m.group(1).split())


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
        valid_phases = _read_enum("VALID_PHASES")
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
    that also carries `phase:`) must be accepted by VALID_STATUS -- except
    a `kind: risk-detail` block, whose `status:` is the risk lifecycle, not
    the document lifecycle."""

    def test_every_status_value_in_examples_is_valid(self):
        valid_status = _read_enum("VALID_STATUS")
        violations = []
        for path, fields in _iter_frontmatter_blocks():
            if fields.get("kind", [(None, None)])[0][0] == RISK_DETAIL_KIND:
                continue
            for raw_value, line_no in fields.get("status", []):
                for token, source in _extract_candidates(raw_value):
                    if token not in valid_status:
                        violations.append(
                            "{}:{}  status: {!r} ({}) not in {}".format(
                                path.relative_to(REPO_ROOT), line_no,
                                token, source, sorted(valid_status),
                            )
                        )
        if violations:
            self.fail(
                "status value(s) outside VALID_STATUS:\n" + "\n".join(violations)
            )


class RiskDetailExemptionIsNarrowTest(unittest.TestCase):
    """Proves the risk-detail exemption is load-bearing rather than
    vacuous: the exempted block's own status values really are outside
    VALID_STATUS (so the exemption has something to exempt), and removing
    the exemption reproduces exactly that block's values as new failures --
    nothing else in the corpus changes."""

    def test_exempted_block_exists_and_its_values_are_themselves_invalid(self):
        valid_status = _read_enum("VALID_STATUS")
        found = False
        for path, fields in _iter_frontmatter_blocks():
            if fields.get("kind", [(None, None)])[0][0] != RISK_DETAIL_KIND:
                continue
            found = True
            tokens = [
                token
                for raw_value, _ in fields.get("status", [])
                for token, _source in _extract_candidates(raw_value)
            ]
            self.assertTrue(tokens, "risk-detail block has no status: field")
            self.assertTrue(
                all(t not in valid_status for t in tokens),
                "expected every risk-detail status token to be outside "
                "VALID_STATUS (proving the exemption is not vacuous): "
                "{}".format(tokens),
            )
        self.assertTrue(
            found,
            "no kind: {} block found in the corpus -- the exemption has "
            "nothing to exempt".format(RISK_DETAIL_KIND),
        )

    def test_removing_the_exemption_only_adds_the_risk_detail_violations(self):
        valid_status = _read_enum("VALID_STATUS")

        def violations_with_exemption(apply_exemption):
            found = []
            for path, fields in _iter_frontmatter_blocks():
                if apply_exemption and fields.get("kind", [(None, None)])[0][0] == RISK_DETAIL_KIND:
                    continue
                for raw_value, line_no in fields.get("status", []):
                    for token, source in _extract_candidates(raw_value):
                        if token not in valid_status:
                            found.append((str(path.relative_to(REPO_ROOT)), line_no, token, source))
            return set(found)

        with_exemption = violations_with_exemption(apply_exemption=True)
        without_exemption = violations_with_exemption(apply_exemption=False)

        new_violations = without_exemption - with_exemption
        self.assertTrue(
            new_violations,
            "removing the exemption produced no new violations -- the "
            "exemption is not narrowing anything",
        )
        self.assertTrue(
            all(
                "p4-sprint.md" in path and token in ("open", "mitigated", "accepted", "closed")
                for path, _line_no, token, _source in new_violations
            ),
            "removing the exemption changed more than the risk-detail "
            "block's own values: {}".format(new_violations),
        )
        # And nothing that was ALREADY a violation with the exemption in
        # place disappears once it is removed -- the exemption only ever
        # adds a narrow, known set back in, never subtracts.
        self.assertTrue(with_exemption <= without_exemption)


if __name__ == "__main__":
    unittest.main()
