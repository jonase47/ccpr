"""test_install_provenance.py -- install.sh must leave a record of WHERE it
installed from, and there must be a runnable, checkable statement about
whether the installed tree still agrees with that record.

## Why this exists

A measurement on 31.08.2026 wanted to say something about `~/.claude/
commands/`. Before it could, it had to establish what that directory even
IS a copy of -- and the only way available was a hand comparison against a
checkout: 116 files each side, same names, byte-identical, all mtimes on
one day. The answer was usable, but only by luck: `commands/` had not been
touched since that install. Had it been, nothing on disk could have said
which state was installed. `install.sh` wrote no such record.

That is the provenance shape `d85c2bd` already closed one level in (the
baseline's note column: a freshness claim nobody can check is not a
claim), applied one level OUT -- outside the repository, on the adopter's
own machine.

## Two questions, deliberately not merged

  * ORIGIN -- which state was installed? Answered by the marker install.sh
    writes into the target. It is a record, not a measurement.
  * PRESENT -- does the installed tree still agree with that state?
    Answered by `install.sh --verify`, which compares. A user can edit
    `~/.claude/commands/` by hand and the marker will not change; nothing
    but a comparison can see that.

Neither replaces the other, and this module keeps them apart: the marker
tests assert what was RECORDED, the verify tests assert what was
COMPARED.

## Fail-open is the failure mode this module is built against

Three states must never be reported as "clean":

  * no marker at all (every installation predating this change),
  * a marker whose source was not a git checkout (unzipped archive, copied
    directory) -- there is no recorded commit to compare against,
  * a marker whose source tree was DIRTY at install time -- what was
    installed is that commit PLUS uncommitted changes, so a difference
    found now cannot be attributed to either.

All three are could-not-run: nothing was compared, and the report says so
in those words. `MarkerAbsenceIsNotCleanTest` and its siblings below pin
that, because "the check found nothing wrong" and "the check could not
look" are the two outcomes an exit code alone cannot tell apart --
the same distinction `scripts/memory-lint.sh`, `scripts/conformance-run.sh`
and `scripts/shellcheck-run.sh` each carve out one level further in, and
which `scripts/check-all.sh` reads back out of their own reports.

## The structural mutation

`VerifyReadsTheMarkerNotOnlyItsPresenceTest` is the load-bearing one.
Deleting the comparison would turn every test here red, which proves
little. Instead it rewrites the marker's `source_commit=` to a commit that
EXISTS in the same fixture repository but is not the one installed. A
verify that merely checks the marker is PRESENT stays green on that; only
one that actually reads the recorded SHA and resolves it goes red.

## Every run is sandboxed

No test here touches the real `~/.claude`. Every `install.sh` invocation
gets both `HOME` and `CCPR_DEST` pointed at scratch directories, and
`install.sh` derives its target from exactly those two
(`DEST="${CCPR_DEST:-$HOME/.claude}"`, install.sh:27) -- verified by
`SandboxContractTest` below rather than assumed, because every other test
in this module depends on it.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = REPO_ROOT / "install.sh"

SCOPE_DIRS = ("agents", "commands", "hooks", "templates")


def shipped_marker_name():
    """The marker's filename, read out of install.sh's own source rather
    than retyped here -- the same "never a second copy of the register"
    discipline test_install_protected_path_rm_guard.py applies to the
    guarded `rm -rf` expression."""
    text = INSTALL.read_text(encoding="utf-8")
    m = re.search(r'^PROVENANCE_FILE="([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else None


def _rmtree(p):
    shutil.rmtree(p, ignore_errors=True)


def parse_marker(text):
    """Reads the marker the same way install.sh --verify does: `key=value`
    lines, `#` comments and blank lines ignored, first `=` splits."""
    out = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if sep:
            out[key.strip()] = value
    return out


class InstallProvenanceBase(unittest.TestCase):
    """A disposable CCPR-checkout-shaped source tree that is also a real git
    repository, so the git/non-git/dirty branches can each be produced on
    demand. Mirrors test_install_docs_boundary.py's InstallTestBase, with
    the git initialisation added and the docs fixture reduced to what
    install.sh's own sanity check and this module's scope need."""

    git_init = True

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="ccpr-prov-home-"))
        self.addCleanup(_rmtree, self.home)
        self.src = Path(tempfile.mkdtemp(prefix="ccpr-prov-src-"))
        self.addCleanup(_rmtree, self.src)
        self.dest = Path(tempfile.mkdtemp(prefix="ccpr-prov-dest-"))
        self.addCleanup(_rmtree, self.dest)
        # install.sh backs up an existing $DEST before writing -- start from
        # a not-yet-existing destination so no backup step runs.
        shutil.rmtree(self.dest)

        # install.sh's sanity check requires agents/ and commands/.
        (self.src / "agents").mkdir()
        (self.src / "agents" / "konzeptor.md").write_text("# konzeptor\n", encoding="utf-8")
        (self.src / "commands").mkdir()
        (self.src / "commands" / "guide.md").write_text("# guide\n", encoding="utf-8")
        (self.src / "hooks").mkdir()
        (self.src / "hooks" / "notify.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        (self.src / "templates").mkdir()
        (self.src / "templates" / "HANDOVER.md").write_text("# handover\n", encoding="utf-8")

        # install.sh derives SRC from its OWN location, so the copy under
        # test must live inside the fixture tree.
        shutil.copy(INSTALL, self.src / "install.sh")

        if self.git_init:
            self.git("init", "-q")
            self.git("add", "-A")
            self.commit("initial")

    # -- helpers ----------------------------------------------------------

    def env(self, **extra):
        e = {
            "HOME": str(self.home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "CCPR_DEST": str(self.dest),
            "GIT_CONFIG_NOSYSTEM": "1",
            "LC_ALL": "C",
        }
        e.update(extra)
        return e

    def git(self, *args, **kw):
        r = subprocess.run(
            ["git", "-C", str(self.src), *args],
            capture_output=True, text=True, env=self.env(**kw.pop("env_extra", {})),
        )
        if kw.get("check", True):
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        return r

    def commit(self, message):
        self.git(
            "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false",
            "commit", "-q", "-m", message,
        )
        return self.git("rev-parse", "HEAD").stdout.strip()

    def run_install(self, *args, stdin=None):
        return subprocess.run(
            ["bash", str(self.src / "install.sh"), *args],
            cwd=str(self.src), input=stdin,
            capture_output=True, text=True, env=self.env(),
        )

    def marker_path(self):
        return self.dest / shipped_marker_name()

    def marker(self):
        return parse_marker(self.marker_path().read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The sandbox contract every other test in this module rests on
# ---------------------------------------------------------------------------


class SandboxContractTest(unittest.TestCase):
    def test_install_sh_takes_its_target_from_ccpr_dest_or_home(self):
        """If install.sh ever stopped honouring CCPR_DEST/HOME, every test
        below would silently start writing into the real ~/.claude. Pinned
        from the shipped line, not retyped prose."""
        text = INSTALL.read_text(encoding="utf-8")
        self.assertIn('DEST="${CCPR_DEST:-$HOME/.claude}"', text)

    def test_the_marker_name_is_declared_in_install_sh(self):
        self.assertIsNotNone(
            shipped_marker_name(),
            "install.sh declares no PROVENANCE_FILE -- this module reads the "
            "marker's name from the shipped source rather than keeping a "
            "second copy of it",
        )


# ---------------------------------------------------------------------------
# ORIGIN -- what the marker records
# ---------------------------------------------------------------------------


class MarkerRecordsACleanGitSourceTest(InstallProvenanceBase):
    def test_a_fresh_install_writes_the_marker(self):
        r = self.run_install("--yes")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertTrue(self.marker_path().is_file(),
                        f"no provenance marker at {self.marker_path()}")

    def test_the_marker_names_the_commit_that_was_installed(self):
        head = self.git("rev-parse", "HEAD").stdout.strip()
        r = self.run_install("--yes")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        m = self.marker()
        self.assertEqual("git", m.get("source_kind"))
        self.assertEqual(head, m.get("source_commit"))
        self.assertEqual("clean", m.get("source_state"))

    def test_the_marker_records_the_install_mode_and_source_path(self):
        r = self.run_install("--yes")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        m = self.marker()
        self.assertEqual("fresh", m.get("install_mode"))
        self.assertEqual(
            os.path.realpath(str(self.src)), m.get("source_path"),
        )
        self.assertRegex(m.get("installed_at", ""),
                         r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_the_run_says_it_wrote_the_marker(self):
        r = self.run_install("--yes")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn(shipped_marker_name(), r.stdout)


class MarkerRecordsADirtySourceAsDirtyTest(InstallProvenanceBase):
    """A bare SHA on a dirty tree claims more than is true: what was
    installed is that commit PLUS whatever was uncommitted."""

    def test_a_modified_tracked_file_makes_the_state_dirty(self):
        head = self.git("rev-parse", "HEAD").stdout.strip()
        (self.src / "commands" / "guide.md").write_text("# guide EDITED\n", encoding="utf-8")
        r = self.run_install("--yes")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        m = self.marker()
        self.assertEqual("dirty", m.get("source_state"))
        self.assertEqual(head, m.get("source_commit"),
                         "the commit is still recorded -- 'dirty' qualifies it, "
                         "it does not replace it")

    def test_an_untracked_file_also_makes_the_state_dirty(self):
        (self.src / "commands" / "scratch.md").write_text("# scratch\n", encoding="utf-8")
        r = self.run_install("--yes")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual("dirty", self.marker().get("source_state"),
                         "an untracked file under a scope directory IS installed, "
                         "so it belongs in the dirty verdict")

    def test_a_clean_tree_is_not_reported_dirty(self):
        # Counter-proof: without this, a marker that always says "dirty"
        # would pass both tests above.
        r = self.run_install("--yes")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual("clean", self.marker().get("source_state"))


class MarkerOnANonGitSourceInventsNothingTest(InstallProvenanceBase):
    """An unzipped archive or a copied directory has no commit. The marker
    must not make one up, and must still say something true."""

    git_init = False

    def test_no_commit_is_recorded(self):
        r = self.run_install("--yes")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        m = self.marker()
        self.assertEqual("non-git", m.get("source_kind"))
        self.assertNotIn("source_commit", m)
        self.assertEqual("unknown", m.get("source_state"))

    def test_the_marker_still_records_what_it_does_know(self):
        r = self.run_install("--yes")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        m = self.marker()
        self.assertEqual(os.path.realpath(str(self.src)), m.get("source_path"))
        self.assertRegex(m.get("installed_at", ""),
                         r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_a_source_inside_an_unrelated_git_repository_is_not_claimed_as_its_own(self):
        """`git rev-parse HEAD` walks UP the directory tree. A copied
        directory that happens to sit inside somebody else's checkout must
        not inherit that repository's HEAD."""
        outer = Path(tempfile.mkdtemp(prefix="ccpr-prov-outer-"))
        self.addCleanup(_rmtree, outer)
        subprocess.run(["git", "-C", str(outer), "init", "-q"],
                       check=True, capture_output=True, env=self.env())
        (outer / "seed.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(outer), "add", "-A"],
                       check=True, capture_output=True, env=self.env())
        subprocess.run(
            ["git", "-C", str(outer),
             "-c", "user.name=F", "-c", "user.email=f@example.invalid",
             "-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed"],
            check=True, capture_output=True, env=self.env(),
        )
        inner = outer / "ccpr-copy"
        shutil.copytree(self.src, inner)
        r = subprocess.run(
            ["bash", str(inner / "install.sh"), "--yes"],
            cwd=str(inner), capture_output=True, text=True, env=self.env(),
        )
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        m = self.marker()
        self.assertEqual("non-git", m.get("source_kind"))
        self.assertNotIn("source_commit", m)


class MarkerIsReplacedNotStackedOnUpdateTest(InstallProvenanceBase):
    def test_update_leaves_exactly_one_recorded_commit_and_it_is_the_new_one(self):
        first = self.git("rev-parse", "HEAD").stdout.strip()
        self.run_install("--yes")
        self.assertEqual(first, self.marker().get("source_commit"))

        (self.src / "commands" / "guide.md").write_text("# guide v2\n", encoding="utf-8")
        self.git("add", "-A")
        second = self.commit("second")
        self.assertNotEqual(first, second)

        r = self.run_install("--update", "--yes")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        text = self.marker_path().read_text(encoding="utf-8")
        self.assertEqual(
            1, len([ln for ln in text.splitlines() if ln.startswith("source_commit=")]),
            "the marker gained a second source_commit line -- it must be "
            "replaced, not appended to:\n" + text,
        )
        self.assertEqual(second, self.marker().get("source_commit"))
        self.assertEqual("update", self.marker().get("install_mode"))


class NoMarkerWithoutAnActualInstallTest(InstallProvenanceBase):
    def test_a_dry_run_writes_no_marker(self):
        r = self.run_install("--dry-run")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertFalse(self.dest.exists(),
                         "the dry-run created the destination it only described")

    def test_the_dry_run_still_announces_the_marker_it_would_write(self):
        # WI-0064's rule: the preview must not disagree with the run it
        # previews. A run that writes a file the preview never mentions is
        # the same defect in the other direction.
        r = self.run_install("--dry-run")
        self.assertIn(shipped_marker_name(), r.stdout)

    def test_an_aborted_confirmation_writes_no_marker(self):
        r = self.run_install(stdin="n\n")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertFalse(self.marker_path().exists(),
                         "an aborted install left a provenance marker behind")


# ---------------------------------------------------------------------------
# PRESENT -- what --verify compares
# ---------------------------------------------------------------------------


COULD_NOT_RUN_PHRASE = "the install-provenance check DID NOT RUN"


class VerifyBase(InstallProvenanceBase):
    def verify(self):
        return self.run_install("--verify")

    def assertCouldNotRun(self, r, needle=None):
        self.assertEqual(
            3, r.returncode,
            "could-not-run must have its own exit code, distinct from both "
            f"a clean verify (0) and a divergence (1):\n{r.stdout}{r.stderr}",
        )
        self.assertIn(COULD_NOT_RUN_PHRASE, r.stdout)
        # The VERDICT line, not the substring "no divergence": the
        # could-not-run paragraph deliberately contains that phrase inside
        # the sentence that denies it ("this is NOT the same as 'no
        # divergence'"). Asserting on the substring made this helper reject
        # the very wording it exists to require.
        self.assertNotIn("Result: VERIFIED", r.stdout)
        self.assertNotIn("Result: DIVERGENT", r.stdout)
        if needle:
            self.assertIn(needle, r.stdout)


class VerifyAgreesWithAnUntouchedInstallationTest(VerifyBase):
    def test_an_untouched_installation_verifies_clean(self):
        self.assertEqual(0, self.run_install("--yes").returncode)
        r = self.verify()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("Result: VERIFIED", r.stdout)
        self.assertIn("no divergence", r.stdout.lower())

    def test_the_verify_reports_how_many_files_it_compared(self):
        """KA-G-017: a run that reports no scope is not a pass. The fixture
        ships four scope files, so the count is checkable, not merely
        present."""
        self.run_install("--yes")
        r = self.verify()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"compared\s+4\s+file")

    def test_the_verify_names_the_commit_it_compared_against(self):
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.run_install("--yes")
        r = self.verify()
        self.assertIn(head, r.stdout,
                      "the report answers 'origin' as well as 'present' -- it "
                      "must name the recorded commit it resolved")

    def test_the_verify_names_the_scope_it_compared(self):
        self.run_install("--yes")
        r = self.verify()
        for name in SCOPE_DIRS:
            self.assertIn(name, r.stdout)

    def test_the_verify_changes_nothing(self):
        self.run_install("--yes")
        before = sorted(
            (p.relative_to(self.dest).as_posix(), p.stat().st_size)
            for p in self.dest.rglob("*") if p.is_file()
        )
        marker_before = self.marker_path().read_text(encoding="utf-8")
        self.assertEqual(0, self.verify().returncode)
        after = sorted(
            (p.relative_to(self.dest).as_posix(), p.stat().st_size)
            for p in self.dest.rglob("*") if p.is_file()
        )
        self.assertEqual(before, after)
        self.assertEqual(marker_before, self.marker_path().read_text(encoding="utf-8"))


class VerifyReportsDivergenceTest(VerifyBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(0, self.run_install("--yes").returncode)

    def test_an_edited_installed_file_is_reported_by_name(self):
        (self.dest / "commands" / "guide.md").write_text("# tampered\n", encoding="utf-8")
        r = self.verify()
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("commands/guide.md", r.stdout)

    def test_a_deleted_installed_file_is_reported_as_missing(self):
        (self.dest / "agents" / "konzeptor.md").unlink()
        r = self.verify()
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("agents/konzeptor.md", r.stdout)
        self.assertIn("missing", r.stdout.lower())

    def test_an_extra_installed_file_is_reported_as_unexpected(self):
        (self.dest / "templates" / "MINE.md").write_text("# mine\n", encoding="utf-8")
        r = self.verify()
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("templates/MINE.md", r.stdout)

    def test_a_whole_missing_scope_directory_is_a_divergence_not_an_empty_scope(self):
        shutil.rmtree(self.dest / "hooks")
        r = self.verify()
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("hooks/notify.sh", r.stdout)

    def test_the_divergent_report_does_not_also_claim_agreement(self):
        (self.dest / "commands" / "guide.md").write_text("# tampered\n", encoding="utf-8")
        r = self.verify()
        self.assertNotIn("Result: VERIFIED", r.stdout)
        self.assertNotIn("no divergence", r.stdout.lower())


class VerifyReadsTheMarkerNotOnlyItsPresenceTest(VerifyBase):
    """The structural mutation, and the two halves do NOT do the same job.
    Deleting the comparison outright turns most of this module red and
    proves little; these two turn on WHICH commit is read.

    The FIRST test catches a presence-only implementation (marker exists ->
    report clean): it installs one commit, points the marker at a second,
    real commit whose tree differs inside the compared scope, and requires
    a divergence. It does NOT catch a HEAD-based implementation -- by that
    point in the fixture the second commit IS `HEAD`, so "read the marker"
    and "just use HEAD" compute the identical expected tree. Measured, not
    assumed: mutating `ls-tree -r "$p_commit"` to `HEAD` leaves this test
    green.

    The SECOND test is the one that catches it, and is therefore the
    load-bearing half for the HEAD property: the installation is untouched
    and the marker still names the installed commit while the CHECKOUT has
    moved on. Only an implementation that resolves the RECORDED SHA still
    reports clean. That same mutation turns exactly this test, and only
    this test, red.

    Neither half is redundant: without the second, a HEAD-based
    implementation passes; without the first, an implementation that always
    reports divergence passes."""

    def test_a_marker_pointing_at_a_different_existing_commit_reports_divergence(self):
        first = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(0, self.run_install("--yes").returncode)

        # A second, real commit in the same repository, differing in one
        # file that is inside the compared scope.
        (self.src / "commands" / "guide.md").write_text("# guide v2\n", encoding="utf-8")
        self.git("add", "-A")
        second = self.commit("second")
        self.assertNotEqual(first, second)

        # The installation on disk is `first`. Point the marker at `second`.
        text = self.marker_path().read_text(encoding="utf-8")
        mutated = text.replace(f"source_commit={first}", f"source_commit={second}")
        self.assertNotEqual(
            text, mutated,
            "the mutation did not take -- the literal 'source_commit=<first>' "
            "was not present, so the measurement below would be vacuous",
        )
        self.assertEqual(
            1, mutated.count(f"source_commit={second}"),
            "expected exactly one substitution",
        )
        self.marker_path().write_text(mutated, encoding="utf-8")

        r = self.verify()
        self.assertEqual(
            1, r.returncode,
            "verify agreed with a marker naming a commit whose tree differs "
            f"from what is installed -- it is reading presence, not content:\n{r.stdout}",
        )
        self.assertIn("commands/guide.md", r.stdout)
        self.assertIn(second, r.stdout)

    def test_the_same_installation_verifies_clean_against_its_own_commit(self):
        """The other half. Without it, a verify that always reports
        divergence would pass the mutation test above and be worthless."""
        self.assertEqual(0, self.run_install("--yes").returncode)
        (self.src / "commands" / "guide.md").write_text("# guide v2\n", encoding="utf-8")
        self.git("add", "-A")
        self.commit("second")
        # The marker is untouched and still names the installed commit,
        # even though the checkout has moved on.
        r = self.verify()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("no divergence", r.stdout.lower())


class MarkerAbsenceIsNotCleanTest(VerifyBase):
    def test_an_installation_without_a_marker_is_not_determinable(self):
        self.assertEqual(0, self.run_install("--yes").returncode)
        self.marker_path().unlink()
        r = self.verify()
        self.assertCouldNotRun(r)
        self.assertRegex(r.stdout.lower(), r"not determinable|no provenance marker")

    def test_a_missing_target_is_not_clean_either(self):
        # $DEST never created: nothing installed at all.
        self.assertFalse(self.dest.exists())
        r = self.verify()
        self.assertCouldNotRun(r)

    def test_a_marker_missing_the_source_state_line_entirely_is_refused(self):
        """Distinct from present-but-empty and present-but-'unknown': the
        key never appears, so `p_state` keeps its initial empty value. The
        fall-through must be a refusal, not the 'clean' path -- an absent
        field is the cheapest way for a future marker-format change to
        fail open."""
        self.assertEqual(0, self.run_install("--yes").returncode)
        text = self.marker_path().read_text(encoding="utf-8")
        stripped = "".join(
            ln + "\n" for ln in text.splitlines()
            if not ln.startswith("source_state=")
        )
        self.assertNotIn("source_state", stripped)
        self.assertIn("source_commit=", stripped,
                      "the rest of the marker must stay intact, or this would "
                      "measure the missing-commit branch instead")
        self.marker_path().write_text(stripped, encoding="utf-8")
        r = self.verify()
        self.assertCouldNotRun(r)

    def test_a_marker_with_no_recognisable_fields_is_refused(self):
        self.assertEqual(0, self.run_install("--yes").returncode)
        self.marker_path().write_text("garbage without any key\n", encoding="utf-8")
        r = self.verify()
        self.assertCouldNotRun(r)


class UnattributableSourcesAreCouldNotRunTest(VerifyBase):
    def test_a_non_git_source_cannot_answer_the_present_question(self):
        # Drop the fixture's git directory: same tree, no repository.
        _rmtree(self.src / ".git")
        self.assertEqual(0, self.run_install("--yes").returncode)
        self.assertEqual("non-git", self.marker().get("source_kind"))
        r = self.verify()
        self.assertCouldNotRun(r)

    def test_a_non_git_marker_still_reports_the_origin_it_does_know(self):
        _rmtree(self.src / ".git")
        self.run_install("--yes")
        r = self.verify()
        self.assertIn(os.path.realpath(str(self.src)), r.stdout,
                      "could-not-run for the PRESENT question is not silence "
                      "about the ORIGIN question")

    def test_a_dirty_source_cannot_be_attributed(self):
        (self.src / "commands" / "guide.md").write_text("# guide EDITED\n", encoding="utf-8")
        self.assertEqual(0, self.run_install("--yes").returncode)
        self.assertEqual("dirty", self.marker().get("source_state"))
        r = self.verify()
        self.assertCouldNotRun(r, needle="dirty")

    def test_a_recorded_commit_absent_from_this_checkout_is_refused(self):
        self.assertEqual(0, self.run_install("--yes").returncode)
        text = self.marker_path().read_text(encoding="utf-8")
        real = self.marker().get("source_commit")
        absent = "0" * 40
        self.marker_path().write_text(
            text.replace(f"source_commit={real}", f"source_commit={absent}"),
            encoding="utf-8",
        )
        r = self.verify()
        self.assertCouldNotRun(r)


class AnIncompleteWalkIsNotACleanVerdictTest(VerifyBase):
    """The UNEXPECTED half is the only one that has to walk the installation
    itself; the other two are driven off the git tree. A `find` that dies
    partway just yields FEWER lines, which from the outside is
    indistinguishable from "there was nothing extra there" -- silent scope
    loss inside a check whose whole point is that an uncovered scope is
    never reported as a clean one (KA-G-017, one directory at a time).

    Root guard in setUp rather than a decorator, mirroring
    test_artifact_gate.py's UnreadableInputTest and
    test_agent_monitor.py: root reads every path regardless of mode, so the
    precondition this class needs simply does not exist there."""

    def setUp(self):
        super().setUp()
        if os.geteuid() == 0:
            self.skipTest("root traverses every directory regardless of mode")
        self.assertEqual(0, self.run_install("--yes").returncode)
        self.locked = self.dest / "commands" / "locked"
        self.locked.mkdir()
        (self.locked / "stowaway.md").write_text("# not from any commit\n", encoding="utf-8")
        self.addCleanup(self.locked.chmod, 0o700)
        self.locked.chmod(0o000)
        # The precondition, measured rather than assumed: this really is a
        # subtree `find` cannot walk on this machine.
        probe = subprocess.run(
            ["find", str(self.dest / "commands"), "-type", "f"],
            capture_output=True, text=True, env=self.env(),
        )
        self.assertNotEqual(
            0, probe.returncode,
            "find walked the mode-000 subtree -- the fixture proves nothing",
        )
        self.assertNotIn("stowaway.md", probe.stdout)

    def test_an_unwalkable_subtree_is_not_reported_as_verified(self):
        r = self.verify()
        self.assertCouldNotRun(r)

    def test_a_divergence_found_elsewhere_is_still_reported(self):
        """The refusal must not swallow findings that WERE made -- a
        divergence is a divergence whether or not the rest of the walk
        finished."""
        (self.dest / "agents" / "konzeptor.md").unlink()
        r = self.verify()
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("agents/konzeptor.md", r.stdout)
        self.assertIn("could not be walked completely", r.stdout)


class EmptyScopeIsNotAPassTest(VerifyBase):
    def test_a_commit_whose_scope_holds_no_file_is_could_not_run(self):
        """"0 files compared" at exit 0 would be a fail-open pass. The
        fixture reaches it by committing a tree with none of the four scope
        directories tracked -- install.sh still runs (its sanity check reads
        the working tree, which still has them)."""
        self.assertEqual(0, self.run_install("--yes").returncode)
        self.git("rm", "-r", "-q", "--cached", *SCOPE_DIRS)
        empty = self.commit("drop the scope from the index")
        text = self.marker_path().read_text(encoding="utf-8")
        real = self.marker().get("source_commit")
        self.marker_path().write_text(
            text.replace(f"source_commit={real}", f"source_commit={empty}"),
            encoding="utf-8",
        )
        r = self.verify()
        self.assertCouldNotRun(r)


class VerifyIsAReadOnlyModeTest(InstallProvenanceBase):
    def test_verify_on_an_empty_target_does_not_create_it(self):
        self.assertFalse(self.dest.exists())
        self.run_install("--verify")
        self.assertFalse(self.dest.exists(),
                         "--verify created the target it only inspects")

    def test_verify_is_documented_in_the_help(self):
        r = self.run_install("--help")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("--verify", r.stdout)


if __name__ == "__main__":
    unittest.main()
