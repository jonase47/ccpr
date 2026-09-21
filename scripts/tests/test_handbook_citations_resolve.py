"""test_handbook_citations_resolve.py -- CCP-1193: no shipped file cites a
`handbook/` path that install.sh does not ship.

## Why this exists

Found 16.09.2026 during a full consistency audit of the tree at `0003f46`:
15 files under `commands/` plus `CLAUDE.md` cited `handbook/WORKITEMS.md §N`
as "see here for the full rationale" -- but `install.sh:45`'s `FRAMEWORK`
array (`agents commands docs hooks scripts templates`) never lists
`handbook`, and ADR-0014 (`docs/adr/ADR-0014-documentation-namespace.md`)
documents that exclusion as deliberate: `docs/` is the framework namespace,
`handbook/` is the human handbook, and it is not installed at all. Every one
of those citations was therefore unresolvable on a machine that only has an
installed CCPR -- the operative guard text was restated inline in each
command (so no instruction was actually broken), but the "see X for more"
pointer led nowhere.

This module proves two things, not one:

1. **The exclusion is real and read from the source, not asserted.** `handbook`
   is absent from install.sh's own `FRAMEWORK` and `PERSONAL` arrays --
   parsed out of `install.sh` itself (`_shipped_top_level_dirs`), never a
   hand-typed copy of "handbook is unshipped" that could silently go stale if
   install.sh ever changed.
2. **No shipped file cites a concrete `handbook/<file>` path.** Scans
   `commands/*.md`, `agents/*.md`, `templates/*.md` and `CLAUDE.md` -- the
   same scope named in CCP-1193 -- for a `handbook/<name>.md`-shaped citation
   and asserts there are none. A bare `handbook/` mention (the directory named
   as a concept, e.g. "this repository's own `handbook/`") is not flagged --
   only a citation to a *specific file* is, since only that shape promises a
   reader something resolvable.

Mutation-proof: `MutationProofTest` writes a synthetic fixture carrying
exactly the CCP-1193 defect shape and proves the scanner used by the real
test actually fires on it (G-107/G-109) -- otherwise a scanner that matches
nothing could pass this module by never running at all.
"""

import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "install.sh"

# A citation to a *specific* handbook file (".../handbook/<name>.<ext>"),
# inside or outside backticks. Deliberately narrower than a bare "handbook/"
# mention -- see module docstring.
HANDBOOK_FILE_CITATION = re.compile(r"handbook/[A-Za-z0-9_./-]*\.[A-Za-z0-9]+")


def shipped_top_level_dirs():
    """The set of top-level names install.sh actually ships, read straight
    out of its own FRAMEWORK/PERSONAL bash arrays -- never a copy retyped
    into this module (same discipline test_install_docs_boundary.py applies
    to scripts/lib/docs-framework-allowlist.txt)."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    names = set()
    for array_name in ("FRAMEWORK", "PERSONAL", "INSTINCTS"):
        m = re.search(rf"^{array_name}=\(([^)]*)\)", text, re.MULTILINE)
        assert m, f"install.sh no longer defines {array_name}=(...) -- update the parser"
        names.update(m.group(1).split())
    return names


def find_handbook_file_citations(paths):
    """(path, line_no, matched_text) for every concrete handbook/<file>
    citation found across the given files."""
    findings = []
    for path in paths:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in HANDBOOK_FILE_CITATION.finditer(line):
                findings.append((path, line_no, match.group(0)))
    return findings


def shipped_citation_scope():
    """commands/*.md, agents/*.md, templates/*.md and CLAUDE.md -- the scope
    CCP-1193 named. Globbed at runtime, never a hard-coded file list, so a
    future file in these directories is covered automatically."""
    paths = []
    paths.extend(sorted((REPO_ROOT / "commands").glob("*.md")))
    paths.extend(sorted((REPO_ROOT / "agents").glob("*.md")))
    paths.extend(sorted((REPO_ROOT / "templates").glob("*.md")))
    paths.append(REPO_ROOT / "CLAUDE.md")
    return [p for p in paths if p.exists()]


class HandbookIsNotAShippedTreeTest(unittest.TestCase):
    """Pins the precondition the rest of this module relies on: `handbook`
    must actually be absent from what install.sh ships. If a future change
    ever added it to FRAMEWORK/PERSONAL/INSTINCTS, the citations this module
    guards against would stop being a defect -- this test is what would need
    to fail first to make that change legitimate."""

    def test_handbook_is_absent_from_every_shipped_array(self):
        self.assertNotIn("handbook", shipped_top_level_dirs())


class NoShippedFileCitesAnUnresolvableHandbookPathTest(unittest.TestCase):
    """The actual CCP-1193 guard: commands/, agents/, templates/ and
    CLAUDE.md must not cite a concrete handbook/<file> path."""

    def test_no_concrete_handbook_file_citation_in_shipped_scope(self):
        findings = find_handbook_file_citations(shipped_citation_scope())
        self.assertEqual(
            findings, [],
            "shipped file(s) cite an unresolvable handbook/ path -- install.sh's "
            "FRAMEWORK array never ships handbook/ (ADR-0014): " + "; ".join(
                f"{p.relative_to(REPO_ROOT)}:{n}: {text!r}" for p, n, text in findings
            ),
        )

    def test_a_bare_handbook_mention_is_not_flagged(self):
        # Regression guard on the regex's own precision: "this repository's
        # own handbook/" (no filename attached) is a concept reference, not
        # a citation promising a resolvable path -- it must not trip the
        # scanner, or the guard would force rewriting accurate, harmless
        # prose (templates/PHASE_DOC_SCHEMA.md and ADR_TEMPLATE.md both carry
        # exactly this shape today).
        self.assertEqual(HANDBOOK_FILE_CITATION.findall("this repository's own `handbook/`"), [])
        self.assertEqual(HANDBOOK_FILE_CITATION.findall("INSTEAD OF (`handbook/**`, ...)"), [])


class MutationProofTest(unittest.TestCase):
    """Proves find_handbook_file_citations actually fires on the CCP-1193
    defect shape, on a synthetic fixture -- the real command files are fixed
    now, so the real corpus can no longer manufacture a RED case (G-107/G-109,
    same pattern test_manual_lint.py uses for its own mutation proofs)."""

    def test_scanner_fires_on_the_ccp_1193_defect_shape(self):
        with tempfile.TemporaryDirectory(prefix="ccpr-handbook-citation-") as tmp:
            fixture = Path(tmp) / "some-command.md"
            fixture.write_text(
                "See handbook/WORKITEMS.md §8 for the full guard rationale.\n",
                encoding="utf-8",
            )
            findings = find_handbook_file_citations([fixture])
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0][1], 1)
            self.assertEqual(findings[0][2], "handbook/WORKITEMS.md")

    def test_scanner_is_silent_on_a_shipped_adr_citation(self):
        with tempfile.TemporaryDirectory(prefix="ccpr-handbook-citation-") as tmp:
            fixture = Path(tmp) / "some-command.md"
            fixture.write_text(
                "See `docs/adr/ADR-0002-workitem-backend-contract.md` for the rationale.\n",
                encoding="utf-8",
            )
            self.assertEqual(find_handbook_file_citations([fixture]), [])


if __name__ == "__main__":
    unittest.main()
