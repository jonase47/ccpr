"""test_install_docs_boundary.py -- WI-0018: install.sh must not ship
working-state paths under docs/ (docs/workitems/, docs/memory/, docs/HANDOVER.md,
docs/decisions/, ...) into a user's own ~/.claude/docs/.

## Why this exists

install.sh treats "docs" as one opaque framework artifact and copies it
wholesale. Reproduced against this repository's own working tree (which
carries its dogfooding working state exactly like any long-running
contributor checkout): a fresh install with CCPR_DEST pointing at a scratch
target landed docs/workitems/ (63 files, 376K) and docs/memory/ (432K) in the
destination, EXIT 0, no warning -- see docs/workitems/WI-0018.md's PO decision
comment for the original, smaller measurement (17 files / 68K at commit
c312c6a^) that this generalises.

scripts/lib/docs-framework-allowlist.txt is the single source of truth this
fix reads -- the SAME file scripts/artifact-gate.sh enforces against the
repository's own tracked files (test_artifact_gate.py::DocsBoundaryTest).
That is the mechanism, not a second, hand-kept list: this suite proves it by
asserting the fix behaves correctly on the allowlist file's CURRENT content,
never on a copy of its entries re-typed into this test module.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = REPO_ROOT / "install.sh"
GATE = REPO_ROOT / "scripts" / "artifact-gate.sh"
GATE_LIB = REPO_ROOT / "scripts" / "lib" / "discipline_gate.sh"
ALLOWLIST_FILE = REPO_ROOT / "scripts" / "lib" / "docs-framework-allowlist.txt"


def allowlist_entries():
    """Parse scripts/lib/docs-framework-allowlist.txt the same way both
    scripts do (blank/'#' lines ignored) -- read from the file itself, never
    retyped, so this test cannot drift from what it is pinning."""
    entries = []
    for line in ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip("\n")
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def _rmtree(p):
    shutil.rmtree(p, ignore_errors=True)


class InstallTestBase(unittest.TestCase):
    """Builds a minimal, disposable CCPR-checkout-shaped source tree so no
    test ever points install.sh's SRC at the real repository (which would
    make the fixture depend on this maintainer's own dogfooding state) or --
    the one thing that must never happen -- runs install.sh without
    CCPR_DEST pointing at a scratch directory."""

    def setUp(self):
        self.src = Path(tempfile.mkdtemp(prefix="ccpr-install-src-"))
        self.addCleanup(_rmtree, self.src)
        self.dest = Path(tempfile.mkdtemp(prefix="ccpr-install-dest-"))
        self.addCleanup(_rmtree, self.dest)
        # install.sh's sanity check requires agents/ and commands/ to exist.
        (self.src / "agents").mkdir()
        (self.src / "commands").mkdir()
        # install.sh backs up an existing $DEST before writing -- start from
        # an empty, not-yet-existing destination so no backup step runs.
        shutil.rmtree(self.dest)

        docs = self.src / "docs"
        (docs / "adr").mkdir(parents=True)
        (docs / "adr" / "0001-example.md").write_text("# ADR\n", encoding="utf-8")
        (docs / "logo").mkdir(parents=True)
        (docs / "logo" / "mark.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (docs / "CONSTITUTION.md").write_text("# Constitution\n", encoding="utf-8")
        (docs / "NEXT_STEPS_REFERENCE.md").write_text("# Next steps\n", encoding="utf-8")
        (docs / "PROJECT_PHASES.md").write_text("# Phases\n", encoding="utf-8")
        # scripts/lib/docs-framework-allowlist.txt itself must exist under
        # the fixture's SRC, since install.sh reads it from $SRC, not from
        # the real repository -- otherwise every fixture would silently
        # depend on running from inside a real CCPR checkout.
        (self.src / "scripts" / "lib").mkdir(parents=True)
        shutil.copy(ALLOWLIST_FILE, self.src / "scripts" / "lib" / "docs-framework-allowlist.txt")

        # install.sh derives SRC from its OWN location (dirname of
        # BASH_SOURCE), not from cwd -- the copy under test must live inside
        # the disposable fixture tree, or "SRC" would resolve to the real
        # repository regardless of what this fixture built.
        shutil.copy(INSTALL, self.src / "install.sh")

        self.docs = docs

    def add_working_state(self):
        (self.docs / "workitems").mkdir()
        (self.docs / "workitems" / "WI-0001.md").write_text("state\n", encoding="utf-8")
        (self.docs / "workitems" / "WI-0002.md").write_text("state\n", encoding="utf-8")
        (self.docs / "memory").mkdir()
        (self.docs / "memory" / "senior-developer").mkdir()
        (self.docs / "memory" / "senior-developer" / "MEMORY.md").write_text(
            "notes\n", encoding="utf-8",
        )
        (self.docs / "HANDOVER.md").write_text("current state\n", encoding="utf-8")

    def run_install(self, *args):
        return subprocess.run(
            ["bash", str(self.src / "install.sh"), *args],
            cwd=self.src,
            capture_output=True, text=True,
            env={"CCPR_DEST": str(self.dest), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        )


class FreshInstallCopiesAllowlistedDocsTest(InstallTestBase):
    def test_the_five_allowlisted_entries_are_installed(self):
        r = self.run_install("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.dest / "docs" / "adr" / "0001-example.md").exists())
        self.assertTrue((self.dest / "docs" / "logo" / "mark.png").exists())
        self.assertTrue((self.dest / "docs" / "CONSTITUTION.md").exists())
        self.assertTrue((self.dest / "docs" / "NEXT_STEPS_REFERENCE.md").exists())
        self.assertTrue((self.dest / "docs" / "PROJECT_PHASES.md").exists())

    def test_a_clean_source_reports_no_skip(self):
        r = self.run_install("--yes")
        self.assertNotIn("skipped", r.stdout.lower())


class WorkingStateIsSkippedAndReportedTest(InstallTestBase):
    def setUp(self):
        super().setUp()
        self.add_working_state()

    def test_working_state_paths_are_not_installed(self):
        r = self.run_install("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.dest / "docs" / "workitems").exists())
        self.assertFalse((self.dest / "docs" / "memory").exists())
        self.assertFalse((self.dest / "docs" / "HANDOVER.md").exists())

    def test_the_allowlisted_entries_are_still_installed_alongside_the_skip(self):
        r = self.run_install("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.dest / "docs" / "adr" / "0001-example.md").exists())
        self.assertTrue((self.dest / "docs" / "CONSTITUTION.md").exists())

    def test_the_skip_is_reported_by_name_and_count(self):
        r = self.run_install("--yes")
        out = r.stdout
        self.assertIn("skipped", out.lower())
        self.assertIn("workitems", out)
        self.assertIn("memory", out)
        self.assertIn("HANDOVER.md", out)
        self.assertIn("3", out)  # 3 skipped top-level docs/ entries

    def test_the_skip_report_names_the_likely_cause(self):
        r = self.run_install("--yes")
        self.assertIn("gitignore", r.stdout.lower())

    def test_a_name_sharing_an_allowlist_entrys_prefix_is_still_skipped(self):
        # "adr-notes.md" starts with "adr" but is not the allowlisted "adr/"
        # directory -- mirrors test_artifact_gate.py's
        # DocsBoundaryTest.test_a_path_named_like_an_allowlist_entry_but_not_a_prefix_match_fails
        # on the install.sh side of the same boundary.
        (self.docs / "adr-notes.md").write_text("x\n", encoding="utf-8")
        r = self.run_install("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.dest / "docs" / "adr-notes.md").exists())
        self.assertIn("adr-notes.md", r.stdout)

    def test_a_dotfile_under_docs_is_reported_not_silently_dropped(self):
        # `for entry_path in "$src_docs"/*` never matches a dotfile by
        # default -- docs/.DS_Store and docs/.handover-archive/ are exactly
        # this shape in a real working checkout. Silently excluding them
        # from BOTH the install and the skip report would be the same
        # silent-scope-loss defect this check exists to close, only for a
        # glob instead of a git-ignore rule.
        (self.docs / ".handover-archive").mkdir()
        (self.docs / ".handover-archive" / "old.md").write_text("x\n", encoding="utf-8")
        r = self.run_install("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.dest / "docs" / ".handover-archive").exists())
        self.assertIn(".handover-archive", r.stdout)

    def test_an_unlisted_docs_entry_never_reaches_the_destination_even_by_accident(self):
        # Regression guard against a future refactor that copies docs/
        # wholesale again and only prints the skip report as an afterthought.
        r = self.run_install("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        installed = {p.name for p in (self.dest / "docs").iterdir()}
        self.assertEqual(installed, {"adr", "logo", "CONSTITUTION.md",
                                      "NEXT_STEPS_REFERENCE.md", "PROJECT_PHASES.md"})


class ReproducesTheStaleCloneMeasurementTest(InstallTestBase):
    """Direct reproduction of the PO's own measurement shape (WI-0018 comment,
    20.08.2026): a checkout carrying docs/workitems/ + docs/memory/ installed
    with CCPR_DEST into a scratch target used to land those files, exit 0, no
    warning. This asserts the fixed behaviour on the same fixture shape."""

    def setUp(self):
        super().setUp()
        self.add_working_state()

    def test_exit_is_still_zero_a_skip_is_not_a_failure(self):
        # A working checkout is a normal, expected shape (every contributor's
        # own dogfooding directory looks exactly like this) -- skipping and
        # reporting is the fix, not treating the run as broken.
        r = self.run_install("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_destination_carries_no_trace_of_the_working_state(self):
        r = self.run_install("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for path in (self.dest / "docs").rglob("*"):
            self.assertNotIn("WI-0001", path.name)
            self.assertNotIn("WI-0002", path.name)


class UpdateModeAlsoAppliesTheBoundaryTest(InstallTestBase):
    """--update reuses the same docs copy step (it is FRAMEWORK, always
    reinstalled) -- the boundary must hold there too, not only on a fresh
    install."""

    def setUp(self):
        super().setUp()
        self.add_working_state()

    def test_update_mode_also_skips_working_state(self):
        r = self.run_install("--update", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.dest / "docs" / "workitems").exists())
        self.assertTrue((self.dest / "docs" / "CONSTITUTION.md").exists())


# ---------------------------------------------------------------------------
# WI-0018's own trap: two lists that must agree (the repo-side allowlist
# artifact-gate.sh enforces, and install.sh's copy-only-these-entries logic)
# is exactly the shape that produced WI-0059 (an archive path held in a
# variable and again as a literal). Both sides read the SAME data file
# (scripts/lib/docs-framework-allowlist.txt) rather than keeping independent
# copies -- that closes the drift by construction for the DATA. This class
# pins the remaining risk: each script also carries its OWN small matcher
# (gate_docs_boundary_violation in artifact-gate.sh, docs_entry_is_allowlisted
# in install.sh) that INTERPRETS that file's entries, and those two
# interpretations could still diverge if one of them is ever edited alone.
# Every test below runs BOTH tools, end to end, over the SAME entries parsed
# straight out of the shared file -- never a copy retyped into this module --
# and asserts they reach the same accept/reject verdict.
# ---------------------------------------------------------------------------
class AllowlistAgreementTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="ccpr-agreement-home-"))
        self.addCleanup(_rmtree, self.home)
        (self.home / ".claude").mkdir()

        self.gate_repo = Path(tempfile.mkdtemp(prefix="ccpr-agreement-gate-"))
        self.addCleanup(_rmtree, self.gate_repo)
        subprocess.run(["git", "init", "-q"], cwd=self.gate_repo, check=True,
                       env=self._env())
        # artifact-gate.sh's docs-boundary rule self-detects (WI-0018 follow-up,
        # 20.08.2026 PO report): it only applies when the repository being swept
        # is the SAME repository the running gate script lives in. A vendored
        # copy under self.gate_repo/scripts/ makes THIS scratch repo that
        # repository -- exactly install_src's own reason for copying install.sh
        # into itself a few lines below.
        gate_scripts = self.gate_repo / "scripts"
        gate_lib = gate_scripts / "lib"
        gate_lib.mkdir(parents=True)
        shutil.copy(GATE, gate_scripts / "artifact-gate.sh")
        shutil.copy(GATE_LIB, gate_lib / "discipline_gate.sh")
        shutil.copy(ALLOWLIST_FILE, gate_lib / "docs-framework-allowlist.txt")
        self.vendored_gate = gate_scripts / "artifact-gate.sh"

        self.install_src = Path(tempfile.mkdtemp(prefix="ccpr-agreement-install-src-"))
        self.addCleanup(_rmtree, self.install_src)
        (self.install_src / "agents").mkdir()
        (self.install_src / "commands").mkdir()
        (self.install_src / "scripts" / "lib").mkdir(parents=True)
        shutil.copy(ALLOWLIST_FILE,
                    self.install_src / "scripts" / "lib" / "docs-framework-allowlist.txt")
        shutil.copy(INSTALL, self.install_src / "install.sh")
        (self.install_src / "docs").mkdir()

        self.install_dest = Path(tempfile.mkdtemp(prefix="ccpr-agreement-install-dest-"))
        self.addCleanup(_rmtree, self.install_dest)
        shutil.rmtree(self.install_dest)

    def _env(self, **extra):
        e = {"HOME": str(self.home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
        e.update(extra)
        return e

    def gate_accepts(self, docs_relative_path, is_dir):
        target = self.gate_repo / "docs" / docs_relative_path
        if is_dir:
            target.mkdir(parents=True)
            (target / "x.md").write_text("x\n", encoding="utf-8")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.gate_repo, check=True, env=self._env())
        subprocess.run(["git", "commit", "-qm", "x"], cwd=self.gate_repo, check=True,
                       env=self._env(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@host.invalid",
                                     GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@host.invalid"))
        r = subprocess.run(["bash", str(self.vendored_gate), "--repo", str(self.gate_repo)],
                           capture_output=True, text=True, env=self._env())
        return r.returncode == 0

    def install_accepts(self, top_level_name, is_dir):
        src_entry = self.install_src / "docs" / top_level_name
        if is_dir:
            src_entry.mkdir()
            (src_entry / "x.md").write_text("x\n", encoding="utf-8")
        else:
            src_entry.write_text("x\n", encoding="utf-8")
        r = subprocess.run(
            ["bash", str(self.install_src / "install.sh"), "--yes"],
            cwd=self.install_src, capture_output=True, text=True,
            env={"CCPR_DEST": str(self.install_dest), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return (self.install_dest / "docs" / top_level_name).exists()

    def test_every_allowlisted_entry_is_accepted_by_both_tools(self):
        for entry in allowlist_entries():
            is_dir = entry.endswith("/")
            name = entry.rstrip("/")
            with self.subTest(entry=entry):
                self.assertTrue(
                    self.gate_accepts(name, is_dir),
                    f"artifact-gate.sh rejected allowlisted entry {entry!r}",
                )
                self.assertTrue(
                    self.install_accepts(name, is_dir),
                    f"install.sh did not install allowlisted entry {entry!r}",
                )

    def test_an_entry_not_in_the_allowlist_is_rejected_by_both_tools(self):
        name = "not-a-real-framework-doc.md"
        self.assertNotIn(name, allowlist_entries())
        gate_ok = self.gate_accepts(name, is_dir=False)
        install_ok = self.install_accepts(name, is_dir=False)
        self.assertFalse(gate_ok, "artifact-gate.sh accepted a non-allowlisted docs/ path")
        self.assertFalse(install_ok, "install.sh installed a non-allowlisted docs/ path")
