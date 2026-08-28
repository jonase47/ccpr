"""test_adr_status_mapping.py -- WI-0128 (follow-up to wave 1c): binds
commands/p3-arch-adr.md's `adr_status -> status` mapping table to (1) the
VALID_STATUS enum phase-docs-lint.sh actually enforces and (2) this
repository's own ten ADRs under docs/adr/.

## Why this exists

Wave 1c fixed a document's own `status:` field disagreeing with
phase-docs-lint.sh's enum. This is one level over: the PROMPT that TEACHES
authors how to fill in `adr_status`/`status` prescribed only three
`adr_status` values (`accepted`, `rejected`, `superseded`) while this
repository's own ten dogfooded ADRs actually use three DIFFERENT-shaped
values across their corpus (`accepted`, `proposed`, `partially-implemented`)
-- `proposed` is a standard ADR-lifecycle term the table simply omitted, and
`partially-implemented` is a project-specific value that does not fit a
fixed three-way enum at all. Same defect class as
test_frontmatter_examples_match_the_lint.py's WI-0121 finding (a generator's
own worked example is a client of the validator it exemplifies) -- except
the prescriptive text here is a markdown TABLE, a shape that test's
```yaml-fence parser cannot see at all.

## Design decided, not assumed

The corrected table names FOUR core rows (`accepted`, `proposed`,
`rejected`, `superseded`) -- `proposed` is universal ADR vocabulary, present
in five of this repo's ten ADRs, and belongs in the fixed list. Beyond
those four the vocabulary is stated as OPEN: a project may mint its own
`adr_status` value (this repo's own `partially-implemented`, ADR-0007) as
long as its mapped `status` is one of VALID_STATUS's six values. Rejected
as a design: hard-coding `partially-implemented` as a fifth core row --
the next project's own project-specific value would reproduce exactly the
gap this test module exists to close, just under a different literal.

## Three bindings

1. `StatusColumnValuesAreValidTest` -- every `status` value the table's
   CORE rows name is in VALID_STATUS.
2. `AdrShapedDocumentPassesLintTest` -- a real ADR-shaped frontmatter
   document built from each CORE row passes phase-docs-lint.sh at exit 0
   with no findings, one subTest per row (the acceptance criterion this fix
   exists to satisfy, measured with the real binary -- enum membership in
   (1) alone would not catch a document-shape defect elsewhere in the
   lint).
3. `RealCorpusValuesAreCoveredTest` -- every `adr_status` value this
   repository's OWN docs/adr/*.md files actually use maps (in that same
   file's frontmatter) to a `status` inside VALID_STATUS. This is the check
   that would have caught the original gap automatically (`proposed` and
   `partially-implemented` both real, both previously unvalidated) without
   requiring a human to re-read the corpus by hand, and it does so without
   hard-coding the open-vocabulary values into the test itself.
"""

import re
import unittest
from pathlib import Path

from .test_phase_docs_lint import PhaseDocsLintTestBase, VALID_DATE
from .test_phase_docs_lint import read_enum as _read_enum

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = REPO_ROOT / "commands" / "p3-arch-adr.md"
LINT_SCRIPT = REPO_ROOT / "scripts" / "phase-docs-lint.sh"
ADR_DIR = REPO_ROOT / "docs" / "adr"

# Matches a two-column `| \`left\` | \`right\` |` markdown table row. The
# character class includes underscore so the header row (`| \`adr_status\` |
# \`status\` |`) actually MATCHES this pattern -- it is then filtered out by
# literal value in _parse_mapping_table, neither "adr_status" nor "status"
# being a value either column ever holds. (A narrower class without "_"
# would make the header fail to match at all, leaving the literal-value
# filter below dead code that looked load-bearing but was not -- code
# review caught this on the first version of this regex.)
TABLE_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z_-]*)`\s*\|\s*`([a-z][a-z_-]*)`\s*\|\s*$", re.MULTILINE)

FRONTMATTER_FIELD_RE = re.compile(r"^([A-Za-z_]+):\s*(.+?)\s*$", re.MULTILINE)


def _parse_mapping_table():
    """Returns the list of (adr_status, status) pairs from the CORE rows of
    commands/p3-arch-adr.md's mapping table, in document order."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    rows = []
    for adr_status, status in TABLE_ROW_RE.findall(text):
        if adr_status == "adr_status" and status == "status":
            continue
        rows.append((adr_status, status))
    return rows


def _read_adr_frontmatter(path):
    """Returns a dict of the top-level frontmatter fields of an ADR file
    under docs/adr/. Fails loudly if there is no frontmatter block at all."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?\n)---\n", text, re.DOTALL)
    if m is None:
        raise AssertionError(f"no frontmatter block in {path}")
    fields = {}
    for line in m.group(1).splitlines():
        fm = FRONTMATTER_FIELD_RE.match(line)
        if fm:
            fields.setdefault(fm.group(1), fm.group(2))
    return fields


class StatusColumnValuesAreValidTest(unittest.TestCase):
    """The table is prescriptive text a document author copies, exactly
    like the yaml frontmatter examples test_frontmatter_examples_match_the_
    lint.py already binds -- except a markdown table is a shape that test's
    ```yaml-fence parser never sees."""

    def test_every_core_row_status_value_is_in_valid_status(self):
        valid_status = _read_enum("VALID_STATUS", LINT_SCRIPT)
        rows = _parse_mapping_table()
        self.assertTrue(rows, "no adr_status -> status rows parsed out of the mapping table")
        violations = [
            f"{adr_status!r} -> {status!r}" for adr_status, status in rows
            if status not in valid_status
        ]
        self.assertEqual(
            violations, [],
            f"status value(s) outside VALID_STATUS {sorted(valid_status)}: {violations}",
        )

    def test_core_rows_include_proposed(self):
        # Pin against the exact gap this module exists to close: `proposed`
        # is real (5 of 10 ADRs) and was previously absent from the table.
        rows = dict(_parse_mapping_table())
        self.assertIn("proposed", rows)


class AdrShapedDocumentPassesLintTest(PhaseDocsLintTestBase):
    """Acceptance criterion: an ADR document written to each CORE row of the
    corrected mapping table passes phase-docs-lint.sh at exit 0 with no
    findings. One subTest per row -- report the measurement per value."""

    def test_each_core_row_produces_a_clean_adr_document(self):
        rows = _parse_mapping_table()
        self.assertTrue(rows)
        for index, (adr_status, status) in enumerate(rows, start=1):
            with self.subTest(adr_status=adr_status, status=status):
                adr_id = f"ADR-{index:04d}"
                text = (
                    "---\n"
                    "phase: P3\n"
                    "subskill: arch-adr\n"
                    f"status: {status}\n"
                    f"last_updated: {VALID_DATE}\n"
                    "kind: adr\n"
                    f"adr_id: {adr_id}\n"
                    f"adr_status: {adr_status}\n"
                    "---\n"
                    "\n# Decision\n\nBody.\n"
                )
                self.write_doc(f"architecture/ADR/{adr_id}-x.md", text)

                result = self.run_lint()

                self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
                self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
                self.assertEqual(result.returncode, 0, result.stdout)


class RealCorpusValuesAreCoveredTest(unittest.TestCase):
    """The gap this follow-up closes: every `adr_status` value this
    repository's own docs/adr/*.md files actually use must map, in that
    same file's frontmatter, to a `status` VALID_STATUS accepts -- whether
    or not that adr_status is one of the table's four core rows. Catches
    the original defect shape (`proposed`, `partially-implemented` both
    real, both previously unvalidated) without hard-coding either into this
    test, so a future project-specific value does not need a matching test
    change here."""

    def test_every_real_adr_status_value_maps_to_a_valid_document_status(self):
        valid_status = _read_enum("VALID_STATUS", LINT_SCRIPT)
        adr_paths = sorted(ADR_DIR.glob("ADR-*.md"))
        self.assertTrue(adr_paths, f"no ADRs found under {ADR_DIR}")

        violations = []
        seen_adr_statuses = set()
        for path in adr_paths:
            fields = _read_adr_frontmatter(path)
            adr_status = fields.get("adr_status")
            status = fields.get("status")
            self.assertIsNotNone(adr_status, f"{path.name} has no adr_status field")
            self.assertIsNotNone(status, f"{path.name} has no status field")
            seen_adr_statuses.add(adr_status)
            if status not in valid_status:
                violations.append(
                    f"{path.name}: adr_status={adr_status!r} status={status!r} "
                    f"not in {sorted(valid_status)}"
                )

        self.assertEqual(violations, [], "\n".join(violations))
        # Not vacuous: this repo's real corpus uses more distinct
        # adr_status values than the OLD three-row table named.
        self.assertGreaterEqual(
            len(seen_adr_statuses), 3,
            f"expected at least 3 distinct adr_status values in the real corpus, saw {seen_adr_statuses}",
        )


if __name__ == "__main__":
    unittest.main()
