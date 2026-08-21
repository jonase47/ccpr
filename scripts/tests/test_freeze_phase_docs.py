"""test_freeze_phase_docs.py -- ground-up coverage for
scripts/freeze-phase-docs.sh (WI-0021 wave 4b / WI-0076).

freeze-phase-docs.sh shipped with ZERO test coverage before this module --
the same gap phase-docs-lint.sh had until 8942235 (see WI-0076's own
description). Written while WI-0076's switch from the BSD-only
`sed -i ''` at line 157 to the portable `fm_set` (scripts/lib/frontmatter.sh)
lands, so this module doubles as the regression safety net for that switch.

Every test here except BodyIsNeverTouchedTest passes against BOTH the
pre-switch `sed -i ''` and the post-switch `fm_set` implementation -- the
switch is meant to be a pure portability fix for the FRONTMATTER write,
not a behaviour change to which files get frozen or skipped.
BodyIsNeverTouchedTest is the one exception and is the reason the switch
is worth making beyond portability: measured directly against the shipped
`sed -E "s/^status:.../..."` (no `-z`, so `^`/`$` are PER-LINE anchors,
not frontmatter-block-aware), a document whose BODY happens to contain a
line that reads exactly like the frontmatter key -- e.g. a table row
documenting a `status:` field -- gets that body line silently rewritten
too. `fm_set` stops at the closing `---` by construction (Part 1 of this
work item), which fixes this as a side effect of the portability switch,
not as a separately scoped behaviour change.

Each test was seen red at least once via a targeted mutation of the
FINAL (fm_set-based) script -- BodyIsNeverTouchedTest was additionally
seen red against the ORIGINAL sed-based script, unmodified, as the
characterisation proof for the defect described above. Mapping reported
in the session summary, not encoded here.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "freeze-phase-docs.sh"

VALID_DATE = "18.08.2026"


def frontmatter_block(phase="P3", subskill="arch-index", status="active",
                       last_updated=VALID_DATE, extra_lines=()):
    """Build a minimal frontmatter block. Pass a field as None to omit it."""
    lines = []
    if phase is not None:
        lines.append(f"phase: {phase}")
    if subskill is not None:
        lines.append(f"subskill: {subskill}")
    if status is not None:
        lines.append(f"status: {status}")
    if last_updated is not None:
        lines.append(f"last_updated: {last_updated}")
    lines.extend(extra_lines)
    return "---\n" + "\n".join(lines) + "\n---\n"


def doc_text(body="\n# Doc\n\nBody.\n", **fm_kwargs):
    return frontmatter_block(**fm_kwargs) + body


class FreezeTestBase(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path(tempfile.mkdtemp(prefix="ccpr-freeze-"))
        self.addCleanup(shutil.rmtree, self.project_dir, ignore_errors=True)

    def write(self, rel_path, text):
        """rel_path is relative to project_dir, e.g. 'docs/architecture/foo.md'."""
        path = self.project_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_freeze(self, phase, *args):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), phase, str(self.project_dir), *args],
            capture_output=True, text=True,
        )


class TerminalStatesTest(FreezeTestBase):
    """The four states {skeleton, living, archived, frozen} are terminal --
    freeze-phase-docs.sh must never rewrite them, only {draft, active}."""

    def _assert_unchanged(self, status):
        f = self.write("docs/architecture/foo.md",
                        doc_text(status=status))
        original = f.read_text()

        result = self.run_freeze("P3")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(original, f.read_text())
        self.assertIn(f"status: {status}", f.read_text())
        self.assertIn("Skipped 1 (terminal state)", result.stdout)

    def test_skeleton_is_left_untouched(self):
        self._assert_unchanged("skeleton")

    def test_living_is_left_untouched(self):
        self._assert_unchanged("living")

    def test_archived_is_left_untouched(self):
        self._assert_unchanged("archived")

    def test_already_frozen_is_left_untouched(self):
        self._assert_unchanged("frozen")

    def test_draft_is_frozen(self):
        f = self.write("docs/architecture/foo.md", doc_text(status="draft"))
        result = self.run_freeze("P3")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("status: frozen", f.read_text())
        self.assertIn("Froze 1 file(s)", result.stdout)

    def test_active_is_frozen(self):
        f = self.write("docs/architecture/foo.md", doc_text(status="active"))
        result = self.run_freeze("P3")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("status: frozen", f.read_text())
        self.assertIn("Froze 1 file(s)", result.stdout)


class IndexSkipTest(FreezeTestBase):
    """Phase indexes (by filename) and sub-indexes (by a `## Detail Files`
    heading) stay active even when their own status is draft/active --
    freeze-phase-docs.sh:129-147's skip, unchanged by the fm_set switch."""

    def test_phase_index_filename_is_skipped(self):
        f = self.write("docs/architecture/ARCHITECTURE.md",
                        doc_text(status="active"))
        result = self.run_freeze("P3")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("status: active", f.read_text())
        self.assertIn("skipped:", result.stdout)
        self.assertIn("index/sub-index", result.stdout)

    def test_sub_index_with_detail_files_heading_is_skipped(self):
        body = "\n# Components\n\n## Detail Files\n\n| doc | status |\n"
        f = self.write("docs/architecture/COMPONENTS.md",
                        doc_text(body=body, status="active"))
        result = self.run_freeze("P3")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("status: active", f.read_text())
        self.assertIn("skipped:", result.stdout)
        self.assertIn("sub-index with Detail-Files table", result.stdout)

    def test_non_index_detail_file_is_still_frozen(self):
        """Same folder, same phase, no index filename and no Detail-Files
        heading -- must NOT be caught by either skip."""
        f = self.write("docs/architecture/AUTH.md", doc_text(status="active"))
        result = self.run_freeze("P3")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("status: frozen", f.read_text())


class PhaseMatchingTest(FreezeTestBase):
    """Only files whose own `phase:` field matches the requested phase are
    acted on -- the folder alone (docs/architecture/) is not the filter."""

    def test_document_for_a_different_phase_is_left_untouched(self):
        f = self.write("docs/architecture/future.md",
                        doc_text(phase="P4", status="active"))
        result = self.run_freeze("P3")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("status: active", f.read_text())
        # not counted anywhere -- it was never a candidate for THIS phase
        self.assertIn("Froze 0 file(s)", result.stdout)

    def test_document_for_the_requested_phase_is_frozen(self):
        f = self.write("docs/architecture/current.md",
                        doc_text(phase="P3", status="active"))
        result = self.run_freeze("P3")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("status: frozen", f.read_text())

    def test_phase_argument_is_case_insensitive(self):
        f = self.write("docs/architecture/current.md",
                        doc_text(phase="P3", status="active"))
        result = self.run_freeze("p3")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("status: frozen", f.read_text())


class NoOpPhaseTest(FreezeTestBase):
    """P5 (iterative sprint phase) and P8 (operational phase) are no-ops
    by design -- must exit 0 without touching any file, regardless of what
    is on disk."""

    def test_p5_is_a_no_op(self):
        f = self.write("docs/sprint/SPRINT.md", doc_text(phase="P5", status="active"))
        original = f.read_text()
        result = self.run_freeze("P5")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(original, f.read_text())
        self.assertIn("No freeze action", result.stdout)

    def test_p8_is_a_no_op(self):
        f = self.write("docs/operations/OPERATIONS.md",
                        doc_text(phase="P8", status="active"))
        original = f.read_text()
        result = self.run_freeze("P8")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(original, f.read_text())
        self.assertIn("no phase-wide freeze", result.stdout)


class BodyIsNeverTouchedTest(FreezeTestBase):
    """The defect this module's docstring describes: a body line that
    reads exactly like the frontmatter key/value pair must survive a
    freeze untouched -- only the FRONTMATTER's own status line may
    change. This is the one test in this module that is RED against the
    original, unswitched `sed -i ''` implementation (verified directly,
    see the session summary), because that sed invocation has no concept
    of the frontmatter block boundary and rewrites any matching line in
    the whole file."""

    def test_a_body_line_matching_the_frontmatter_pattern_is_untouched(self):
        body = (
            "\n# Doc\n\nA table row documenting a status field:\n\n"
            "status: active\n\nMore text.\n"
        )
        f = self.write("docs/architecture/foo.md",
                        doc_text(body=body, status="active"))

        result = self.run_freeze("P3")

        self.assertEqual(0, result.returncode, result.stderr)
        text = f.read_text()
        # exactly one "status: frozen" line -- the rewritten frontmatter
        # key -- the body's own "status: active" line must still read
        # "active", not have collapsed into a second "frozen" line.
        self.assertEqual(1, text.count("status: frozen"))
        self.assertIn("status: active\n", text.split("---\n", 2)[-1])


if __name__ == "__main__":
    unittest.main()


class FreezeAnchorHookTest(FreezeTestBase):
    """The freeze hook (WI-0021 wave 4b, ADR-0009 Addendum 2 A7 resolved):
    freeze-phase-docs.sh gains a SECOND, deliberate write path onto the
    phase INDEX it otherwise always skips (IndexSkipTest above), writing
    anchor_commit/anchor_date there once the phase's detail files have
    been frozen -- one gate pass produces one anchor for the whole scope.
    Delegates to `anchor set` (Part 2 of this work item) rather than
    re-implementing commit classification here, so the write path and the
    read path (`anchor status`/`check`) never disagree about what "the
    code" means. Non-fatal by design: freezing the detail files is this
    script's primary job and must keep succeeding outside a git
    repository or without a phase index -- neither is this script's own
    precondition to enforce."""

    def setUp(self):
        super().setUp()
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@host.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@host.invalid",
        }

    def init_repo(self):
        subprocess.run(["git", "init", "-q"], cwd=self.project_dir, check=True, env=self.env)

    def commit(self, message="commit"):
        subprocess.run(["git", "add", "-A"], cwd=self.project_dir, check=True, env=self.env)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=self.project_dir,
                        check=True, env=self.env)
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project_dir, check=True,
            capture_output=True, text=True, env=self.env,
        ).stdout.strip()

    def _index_text(self):
        return (self.project_dir / "docs/architecture/ARCHITECTURE.md").read_text()

    def _anchor_commit(self):
        m = re.search(r"^anchor_commit:\s*(\S+)", self._index_text(), re.MULTILINE)
        return m.group(1) if m else None

    def _seed(self):
        """A git repo with one production-code commit, a phase index and
        one freezable detail document, all committed."""
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        prod_sha = self.commit("seed code")
        self.write("docs/architecture/ARCHITECTURE.md",
                    doc_text(phase="P3", status="active"))
        self.write("docs/architecture/AUTH.md",
                    doc_text(phase="P3", status="active"))
        self.commit("add architecture docs")
        return prod_sha

    def test_freeze_writes_an_anchor_onto_the_phase_index(self):
        prod_sha = self._seed()

        result = self.run_freeze("P3")

        self.assertEqual(0, result.returncode, result.stderr)
        auth_text = (self.project_dir / "docs/architecture/AUTH.md").read_text()
        self.assertIn("status: frozen", auth_text)
        self.assertEqual(prod_sha, self._anchor_commit())
        # the index's OWN status is untouched -- only the anchor changed,
        # the Index-File-Skip for `status:` still applies.
        self.assertIn("status: active", self._index_text())

    def test_second_freeze_run_does_not_move_an_existing_anchor(self):
        self._seed()
        first = self.run_freeze("P3")
        self.assertEqual(0, first.returncode, first.stderr)
        first_anchor = self._anchor_commit()
        self.assertIsNotNone(first_anchor)

        self.write("src/a.go", "package a\n\nfunc D() {}\n")
        self.commit("drift the code after the first freeze")

        second = self.run_freeze("P3")

        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(first_anchor, self._anchor_commit())
        self.assertIn("anchor already present", second.stdout)
        self.assertIn("anchor ack", second.stdout)

    def test_dry_run_writes_no_anchor(self):
        self._seed()
        result = self.run_freeze("P3", "--dry-run")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIsNone(self._anchor_commit())

    def test_freeze_without_a_git_repository_still_succeeds(self):
        self.write("docs/architecture/AUTH.md", doc_text(phase="P3", status="active"))
        result = self.run_freeze("P3")
        self.assertEqual(0, result.returncode, result.stderr)
        auth_text = (self.project_dir / "docs/architecture/AUTH.md").read_text()
        self.assertIn("status: frozen", auth_text)

    def test_freeze_with_no_phase_index_present_still_succeeds(self):
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.commit("seed code")
        self.write("docs/architecture/AUTH.md", doc_text(phase="P3", status="active"))
        self.commit("add auth doc, no index")

        result = self.run_freeze("P3")

        self.assertEqual(0, result.returncode, result.stderr)
        auth_text = (self.project_dir / "docs/architecture/AUTH.md").read_text()
        self.assertIn("status: frozen", auth_text)
