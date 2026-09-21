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
   `commands/*.md`, `agents/*.md`, `templates/*.md`, `CLAUDE.md` -- the
   original scope named in CCP-1193 -- and every `*.md` file under `docs/`
   that install.sh actually ships (`shipped_docs_paths()`, derived from
   `scripts/lib/docs-framework-allowlist.txt`) for a `handbook/<name>.md`-
   shaped citation, and asserts there are none. A bare `handbook/` mention
   (the directory named as a concept, e.g. "this repository's own
   `handbook/`") is not flagged -- only a citation to a *specific file* is,
   since only that shape promises a reader something resolvable.

## Post-merge review gap (`docs/` scope)

Code review of the original CCP-1193 fix found `shipped_citation_scope()`
left out `docs/` entirely, even though `docs/` (or at least `docs/adr/*.md`)
is itself shipped (`install.sh`'s `FRAMEWORK` array). Twelve citations of the
same defect shape were hiding there: five ADRs' own `related:` frontmatter
(`ADR-0001`, `ADR-0003`, `ADR-0004`, `ADR-0008`, `ADR-0013`) and seven more in
`docs/CONSTITUTION.md` (frontmatter `related:`, the Lean-Track-sunset
Aspirational measurement, and a historical Changelog entry) plus
`docs/PROJECT_PHASES.md` ("Full spec: `handbook/LEAN_TRACK.md`."). Fixed by
repointing/removing each (ADR-0003/0004/0008 already listed ADR-0002 as a
`related:` entry, so their handbook line was redundant and simply dropped;
ADR-0001/ADR-0013/CONSTITUTION.md's frontmatter had no shipped equivalent to
repoint to, so the entry was removed; the two prose mentions were reworded to
name the handbook chapter without the unresolvable path shape).
`shipped_citation_scope()` now covers this via `shipped_docs_paths()`, so a
new shipped `docs/` document citing an unshipped `handbook/` path is caught
automatically, not just the five files fixed today.

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


DOCS_ALLOWLIST = REPO_ROOT / "scripts" / "lib" / "docs-framework-allowlist.txt"


def shipped_docs_paths():
    """Every `*.md` file under `docs/` that install.sh actually ships,
    derived from `scripts/lib/docs-framework-allowlist.txt` -- the SAME
    single source of truth `test_install_docs_boundary.py`'s own
    `allowlist_entries()` reads, never a copy retyped into this module. A
    review gap (found post-merge, CCP-1193 follow-up): five ADRs cite
    `handbook/` paths in their own `related:` frontmatter --
    `docs/adr/ADR-0001-versioning-and-distribution.md`,
    `ADR-0003-youtrack-backend.md`, `ADR-0004-workitem-lift-and-migrate.md`,
    `ADR-0008-typed-workitem-links.md`, `ADR-0013-server-side-push-gate.md`
    -- and `docs/adr/*.md` was outside the original scope entirely, even
    though `adr/` is the allowlist's own first entry."""
    if not DOCS_ALLOWLIST.exists():
        return []
    paths = []
    for line in DOCS_ALLOWLIST.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        target = REPO_ROOT / "docs" / entry.rstrip("/")
        if entry.endswith("/"):
            paths.extend(sorted(target.rglob("*.md")))
        elif target.suffix == ".md":
            paths.append(target)
    return paths


def shipped_citation_scope():
    """commands/*.md, agents/*.md, templates/*.md, CLAUDE.md -- the scope
    CCP-1193 originally named -- plus every shipped `docs/*.md` file
    (`shipped_docs_paths()`, above). Globbed/derived at runtime, never a
    hard-coded file list, so a future file in any of these locations is
    covered automatically."""
    paths = []
    paths.extend(sorted((REPO_ROOT / "commands").glob("*.md")))
    paths.extend(sorted((REPO_ROOT / "agents").glob("*.md")))
    paths.extend(sorted((REPO_ROOT / "templates").glob("*.md")))
    paths.append(REPO_ROOT / "CLAUDE.md")
    paths.extend(shipped_docs_paths())
    return [p for p in paths if p.exists()]


class HandbookIsNotAShippedTreeTest(unittest.TestCase):
    """Pins the precondition the rest of this module relies on: `handbook`
    must actually be absent from what install.sh ships. If a future change
    ever added it to FRAMEWORK/PERSONAL/INSTINCTS, the citations this module
    guards against would stop being a defect -- this test is what would need
    to fail first to make that change legitimate."""

    def test_handbook_is_absent_from_every_shipped_array(self):
        self.assertNotIn("handbook", shipped_top_level_dirs())


class ShippedDocsScopeCoversAdrTest(unittest.TestCase):
    """Pins the post-merge review gap fix: docs/adr/*.md (the allowlist's own
    first entry) must be part of the scanned scope, derived from the
    allowlist rather than a hard-coded 'docs/adr' glob string."""

    def test_docs_adr_files_are_in_the_derived_scope(self):
        adr_dir = REPO_ROOT / "docs" / "adr"
        scope = {p.resolve() for p in shipped_citation_scope()}
        adr_files = list(adr_dir.glob("*.md"))
        self.assertTrue(adr_files, "docs/adr/*.md is empty -- fixture assumption broken")
        for f in adr_files:
            self.assertIn(f.resolve(), scope, f"{f} missing from shipped_citation_scope()")

    def test_docs_constitution_and_project_phases_are_in_scope(self):
        scope = {p.resolve() for p in shipped_citation_scope()}
        self.assertIn((REPO_ROOT / "docs" / "CONSTITUTION.md").resolve(), scope)
        self.assertIn((REPO_ROOT / "docs" / "PROJECT_PHASES.md").resolve(), scope)

    def test_a_non_allowlisted_docs_file_is_not_in_scope(self):
        # scripts/lib/docs-framework-allowlist.txt does not list docs/memory/
        # or docs/workitems/ (working state, never shipped) -- the derived
        # scope must not pull in a project's own working files, which could
        # legitimately carry an in-repo (not shipped) handbook/ path.
        scope = {p.resolve() for p in shipped_citation_scope()}
        for stray in (REPO_ROOT / "docs" / "HANDOVER.md",
                      REPO_ROOT / "docs" / "adr-notes.md"):
            self.assertNotIn(stray.resolve(), scope)


class DocsPathsMutationProofTest(unittest.TestCase):
    """Proves shipped_docs_paths() actually reads the allowlist file rather
    than always returning some fixed set -- points DOCS_ALLOWLIST at a
    synthetic allowlist and checks the derived set changes accordingly
    (G-107/G-109)."""

    def test_a_synthetic_allowlist_entry_changes_the_derived_set(self):
        import scripts.tests.test_handbook_citations_resolve as mod
        with tempfile.TemporaryDirectory(prefix="ccpr-docs-allowlist-") as tmp:
            tmp_path = Path(tmp)
            fake_repo = tmp_path
            (fake_repo / "docs" / "onlyme").mkdir(parents=True)
            (fake_repo / "docs" / "onlyme" / "a.md").write_text("x\n", encoding="utf-8")
            (fake_repo / "docs" / "skipped.md").write_text("x\n", encoding="utf-8")
            allowlist = fake_repo / "allowlist.txt"
            allowlist.write_text("onlyme/\n", encoding="utf-8")

            original_root, original_allowlist = mod.REPO_ROOT, mod.DOCS_ALLOWLIST
            mod.REPO_ROOT, mod.DOCS_ALLOWLIST = fake_repo, allowlist
            try:
                paths = {p.resolve() for p in mod.shipped_docs_paths()}
            finally:
                mod.REPO_ROOT, mod.DOCS_ALLOWLIST = original_root, original_allowlist

            self.assertIn((fake_repo / "docs" / "onlyme" / "a.md").resolve(), paths)
            self.assertNotIn((fake_repo / "docs" / "skipped.md").resolve(), paths)


class NoShippedFileCitesAnUnresolvableHandbookPathTest(unittest.TestCase):
    """The actual CCP-1193 guard: commands/, agents/, templates/, CLAUDE.md
    and every shipped docs/*.md file must not cite a concrete
    handbook/<file> path."""

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
