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

## Post-merge review gap #1 (`docs/` scope)

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
repoint to, so the entry was removed; the Aspirational-measurement prose was
reworded to name the handbook chapter without the unresolvable path shape).
`shipped_citation_scope()` now covers this via `shipped_docs_paths()`, so a
new shipped `docs/` document citing an unshipped `handbook/` path is caught
automatically, not just the files fixed today.

## Post-merge review gap #2 (historical Changelog entries)

The first pass also reworded `CONSTITUTION.md`'s v1.3 `## Changelog` entry,
which was wrong: that very entry states the principle that a changelog
record "is not rewritten retroactively" (a PO correction, dated
08.09.2026) -- it names `handbook/README.md` etc. because those were the
paths that existed AT THE TIME that entry was written, which is correct as
history, not a dangling citation. Reverted the rewording and instead taught
`find_handbook_file_citations()` to skip any line inside a markdown section
headed "Changelog" (`_lines_outside_changelog_sections()`, any heading
level, case-insensitive, nested subsections included) -- a structural rule
derived from the heading text, not a hard-coded exception for
`docs/CONSTITUTION.md` by name, so any other shipped document with its own
"## Changelog" section gets the same treatment automatically.
`HistoricalChangelogSectionIsSkippedTest` is the RED/GREEN proof: a citation
inside a Changelog section is ignored (RED for the naive line scanner, GREEN
here), a citation outside one in the SAME document is still caught (stays
GREEN either way), plus edge cases for nested subsections and a sibling
heading that closes the section.

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

# A markdown ATX heading line ("## Changelog", "### v1.3", ...). Used to find
# the boundary of a historical-changelog section -- see
# _lines_outside_changelog_sections()'s own docstring for why that section is
# excluded, generically, rather than by file name.
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


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


def _lines_outside_changelog_sections(text):
    """Yields (line_no, line) for every line NOT inside a markdown section
    headed "Changelog" (any heading level, case-insensitive -- "## Changelog",
    "### Changelog"), including its nested subsections.

    Why: a historical changelog entry records what a document looked like AT
    THE TIME an earlier change was made -- naming a path that existed then is
    correct AS HISTORY, not a dangling citation to fix going forward
    (`docs/CONSTITUTION.md`'s own v1.3 entry states the principle explicitly:
    a changelog entry "is not rewritten retroactively", a PO correction dated
    08.09.2026). The rule is derived structurally from the heading text, not
    a hard-coded file-name exception for CONSTITUTION.md -- any shipped doc
    with its own "## Changelog" section gets the same treatment.

    A nested subsection (e.g. "### v1.3" under "## Changelog") stays excluded
    until a heading at the SAME OR SHALLOWER level than the "Changelog"
    heading itself closes the section -- that new heading is then evaluated
    on its own merits (it might re-open a changelog scope if it is itself
    named "Changelog" at a sibling level, though no known document does
    that).
    """
    changelog_level = None
    for line_no, line in enumerate(text.splitlines(), start=1):
        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if changelog_level is not None and level <= changelog_level:
                changelog_level = None  # left the changelog section
            if changelog_level is None and title.lower() == "changelog":
                changelog_level = level
        if changelog_level is None:
            yield line_no, line


def find_handbook_file_citations(paths):
    """(path, line_no, matched_text) for every concrete handbook/<file>
    citation found across the given files, excluding citations inside a
    historical "## Changelog" section (see
    _lines_outside_changelog_sections())."""
    findings = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for line_no, line in _lines_outside_changelog_sections(text):
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


def shipped_templates_paths():
    """Every TEXT file under `templates/`, recursively -- not just `*.md`.
    `templates/` is copied wholesale by install.sh's `FRAMEWORK` array (a
    whole top-level directory, not filtered by extension), so a citation
    defect can just as easily hide in a shipped `templates/*.json` file as in
    a `templates/*.md` one -- exactly the gap that let
    `templates/workitems.example.json` and `templates/memory-sync.example.json`
    slip past the original `templates/*.md`-only glob (post-merge review
    finding, CCP-1193 follow-up).

    Walked and filtered by content (no NUL byte in the first chunk read),
    never a hard-coded extension allowlist -- so a future non-`.md` template
    file of any text shape is covered automatically, while a genuine binary
    asset (e.g. a logo) is skipped rather than raising a decode error. No
    binary file exists under `templates/` today; the filter is defensive, not
    reactive to a current file."""
    root = REPO_ROOT / "templates"
    if not root.exists():
        return []
    paths = []
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_file():
            continue
        try:
            with candidate.open("rb") as f:
                chunk = f.read(8192)
        except OSError:
            continue
        if b"\x00" in chunk:
            continue
        paths.append(candidate)
    return paths


def shipped_citation_scope():
    """commands/*.md, agents/*.md, every shipped text file under templates/
    (`shipped_templates_paths()`, not just `*.md` -- see its own docstring),
    CLAUDE.md -- the scope CCP-1193 originally named -- plus every shipped
    `docs/*.md` file (`shipped_docs_paths()`, above). Globbed/derived at
    runtime, never a hard-coded file list, so a future file in any of these
    locations is covered automatically."""
    paths = []
    paths.extend(sorted((REPO_ROOT / "commands").glob("*.md")))
    paths.extend(sorted((REPO_ROOT / "agents").glob("*.md")))
    paths.extend(shipped_templates_paths())
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


class ShippedTemplatesScopeCoversNonMdTest(unittest.TestCase):
    """Pins the post-merge review gap fix: `templates/*.json` (not just
    `templates/*.md`) must be part of the scanned scope, since `templates/`
    ships as a whole directory, not filtered by extension."""

    def test_workitems_example_json_is_in_scope(self):
        scope = {p.resolve() for p in shipped_citation_scope()}
        self.assertIn(
            (REPO_ROOT / "templates" / "workitems.example.json").resolve(), scope
        )

    def test_memory_sync_example_json_is_in_scope(self):
        scope = {p.resolve() for p in shipped_citation_scope()}
        self.assertIn(
            (REPO_ROOT / "templates" / "memory-sync.example.json").resolve(), scope
        )

    def test_a_synthetic_binary_file_under_templates_is_excluded(self):
        # Mutation proof (G-107/G-109 pattern, same as DocsPathsMutationProofTest
        # above): swap REPO_ROOT to a synthetic tree carrying one text file and
        # one NUL-containing "binary" file, and prove the derived set keeps the
        # former while dropping the latter -- not just that the real templates/
        # tree happens to be all-text today.
        import scripts.tests.test_handbook_citations_resolve as mod

        with tempfile.TemporaryDirectory(prefix="ccpr-templates-scope-") as tmp:
            fake_repo = Path(tmp)
            templates_dir = fake_repo / "templates"
            templates_dir.mkdir()
            (templates_dir / "some.json").write_text("{}\n", encoding="utf-8")
            (templates_dir / "some.bin").write_bytes(b"\x00\x01\x02binary")

            original_root = mod.REPO_ROOT
            mod.REPO_ROOT = fake_repo
            try:
                paths = {p.resolve() for p in mod.shipped_templates_paths()}
            finally:
                mod.REPO_ROOT = original_root

            self.assertIn((templates_dir / "some.json").resolve(), paths)
            self.assertNotIn((templates_dir / "some.bin").resolve(), paths)


class HistoricalChangelogSectionIsSkippedTest(unittest.TestCase):
    """Review follow-up: a citation inside a document's own "## Changelog"
    section records history (what the document looked like when an earlier
    entry was written) and must not be flagged -- but the same document's
    LIVE content outside that section must still be caught. Derived from the
    heading text ("Changelog", case-insensitive, any level), never a
    hard-coded exception for docs/CONSTITUTION.md by file name."""

    def _fixture(self, tmp, body):
        d = Path(tmp)
        f = d / "some-shipped-doc.md"
        f.write_text(body, encoding="utf-8")
        return f

    def test_red_a_citation_inside_a_changelog_section_is_ignored(self):
        with tempfile.TemporaryDirectory(prefix="ccpr-changelog-skip-") as tmp:
            f = self._fixture(tmp, (
                "# Some Document\n\n"
                "## Changelog\n\n"
                "- **v1.3**: repointed to `handbook/LEAN_TRACK.md`, as it stood then.\n"
            ))
            self.assertEqual(find_handbook_file_citations([f]), [])

    def test_green_a_citation_outside_a_changelog_section_is_still_caught(self):
        with tempfile.TemporaryDirectory(prefix="ccpr-changelog-skip-") as tmp:
            f = self._fixture(tmp, (
                "# Some Document\n\n"
                "See `handbook/WORKITEMS.md` for the full rationale.\n\n"
                "## Changelog\n\n"
                "- **v1.0**: initial version.\n"
            ))
            findings = find_handbook_file_citations([f])
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0][2], "handbook/WORKITEMS.md")

    def test_a_citation_both_inside_and_outside_changelog_only_the_live_one_fires(self):
        # The exact shape CONSTITUTION.md had before this fix: one live
        # citation (frontmatter-adjacent prose) plus one historical mention
        # inside "## Changelog" -- only the first is a real defect.
        with tempfile.TemporaryDirectory(prefix="ccpr-changelog-skip-") as tmp:
            f = self._fixture(tmp, (
                "# Some Document\n\n"
                "*Measurement:* `handbook/LEAN_TRACK.md` removed.\n\n"
                "## Changelog\n\n"
                "- **v1.3**: repointed to `handbook/LEAN_TRACK.md`.\n"
            ))
            findings = find_handbook_file_citations([f])
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0][1], 3)  # the live mention's line, not the changelog one

    def test_a_subsection_nested_under_changelog_stays_excluded(self):
        # "### v1.3" is a deeper heading than "## Changelog" -- it does not
        # close the section, it is part of it.
        with tempfile.TemporaryDirectory(prefix="ccpr-changelog-skip-") as tmp:
            f = self._fixture(tmp, (
                "## Changelog\n\n"
                "### v1.3\n\n"
                "- repointed to `handbook/LEAN_TRACK.md`.\n"
            ))
            self.assertEqual(find_handbook_file_citations([f]), [])

    def test_a_sibling_heading_after_changelog_closes_the_section(self):
        # "## See Also" is the SAME level as "## Changelog" -- it ends the
        # changelog scope, so a citation under it is live content again.
        with tempfile.TemporaryDirectory(prefix="ccpr-changelog-skip-") as tmp:
            f = self._fixture(tmp, (
                "## Changelog\n\n"
                "- v1.0 initial version.\n\n"
                "## See Also\n\n"
                "See `handbook/WORKITEMS.md` for more.\n"
            ))
            findings = find_handbook_file_citations([f])
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0][2], "handbook/WORKITEMS.md")

    def test_matching_is_case_insensitive_on_the_heading_text(self):
        with tempfile.TemporaryDirectory(prefix="ccpr-changelog-skip-") as tmp:
            f = self._fixture(tmp, (
                "## CHANGELOG\n\n"
                "- repointed to `handbook/LEAN_TRACK.md`.\n"
            ))
            self.assertEqual(find_handbook_file_citations([f]), [])


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
