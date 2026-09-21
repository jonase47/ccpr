"""test_qa_skeleton_single_parent.py -- CCP-1211: every `templates/QA_SKELETON/*.md`
sub-index must have exactly one parent, and that parent must agree with the
file's own `parent_index:` frontmatter field.

## The defect this guards

`templates/QA_SKELETON/AUTHZ.md` declares `parent_index: PENTEST.md` in its
own frontmatter, and `PENTEST.md`'s "Detail Files" table links to it
(`[AUTHZ.md](AUTHZ.md)`) -- the two agree. But `QA.md`'s own "Sub-Indexes"
table ALSO linked to `AUTHZ.md` directly, as if it were a top-level sibling
of `A11Y.md`/`AUDIT.md`/`FUNCTIONAL.md`/`PENTEST.md` rather than nested one
level down inside `PENTEST.md`. A shipped skeleton with two documents both
claiming to parent the same file is exactly the kind of structural drift
`parent_index:` (`templates/PHASE_DOC_SCHEMA.md`) exists to prevent.

## What this test checks, and what it deliberately does not

"Parent" here means: a sibling skeleton file's body contains a markdown
link targeting this file's own filename, e.g. `(AUTHZ.md)` -- the same
shape `QA.md`'s "Sub-Indexes" table and `PENTEST.md`'s "Detail Files" table
both use for every entry. `related:` frontmatter entries are a DIFFERENT,
explicitly non-hierarchical cross-reference (`templates/PHASE_DOC_SCHEMA.md`
line 28: "Paths to related phase docs") and are not scanned here -- QA.md
legitimately keeps `AUTHZ.md` in its `related:` list even though AUTHZ.md's
structural parent is PENTEST.md, and that is not a violation of this
invariant.

`QA.md` itself is the phase index (no `parent_index:` field, by design --
`templates/PHASE_DOC_SCHEMA.md` line 29: "Phase indexes leave this field
empty") and is exempt from the "must have a parent" half of the check, but
still participates as a potential (wrong) linker for every other file.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QA_SKELETON_DIR = REPO_ROOT / "templates" / "QA_SKELETON"

PARENT_INDEX_RE = re.compile(r"^parent_index:\s*(\S+)\s*$", re.MULTILINE)


def _frontmatter_text(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else text


def _declared_parent(path):
    m = PARENT_INDEX_RE.search(_frontmatter_text(path))
    return m.group(1) if m else None


def _skeleton_files():
    return sorted(QA_SKELETON_DIR.glob("*.md"))


def _linkers_of(target_name, files):
    """Every OTHER skeleton file whose body contains a markdown link
    targeting target_name, e.g. '(AUTHZ.md)'."""
    pattern = re.compile(r"\(" + re.escape(target_name) + r"\)")
    linkers = []
    for f in files:
        if f.name == target_name:
            continue
        if pattern.search(f.read_text(encoding="utf-8")):
            linkers.append(f.name)
    return linkers


class QASkeletonSingleParentTest(unittest.TestCase):
    def test_every_skeleton_file_is_linked_by_exactly_one_other_skeleton_file(self):
        files = _skeleton_files()
        self.assertTrue(files, "no templates/QA_SKELETON/*.md files found")

        violations = []
        for f in files:
            linkers = _linkers_of(f.name, files)
            if len(linkers) > 1:
                violations.append(
                    f"{f.name} is linked as a child by {len(linkers)} files: {linkers}"
                )

        self.assertEqual(
            violations, [],
            "skeleton file(s) with more than one parent-linking sibling:\n"
            + "\n".join(violations),
        )

    def test_every_declared_parent_index_matches_its_single_linker(self):
        files = _skeleton_files()

        mismatches = []
        for f in files:
            declared = _declared_parent(f)
            if declared is None:
                continue  # phase index (QA.md) -- exempt, per module docstring
            linkers = _linkers_of(f.name, files)
            if linkers != [declared]:
                mismatches.append(
                    f"{f.name}: parent_index={declared!r} but linked by {linkers}"
                )

        self.assertEqual(
            mismatches, [],
            "skeleton file(s) whose parent_index: disagrees with the sibling "
            "that actually links to them:\n" + "\n".join(mismatches),
        )


if __name__ == "__main__":
    unittest.main()
