"""test_install_push_gate_hook.py -- CCP-1137 Auflage 2: end-to-end tests
for scripts/install-push-gate-hook.sh, the installer for push-gate.sh's
CLIENT-side `pre-push` hook.

The installed hook is FAST FEEDBACK ONLY -- the server's own `pre-receive`
hook (push-gate.sh invoked with `--server`, see scripts/tests/
test_push_gate.py) is the actual protection line. This suite proves the
installer itself (backup discipline, git-repo check, written-hook shape)
AND drives the installed hook through a REAL `git push` against a local
bare repository, the same "proof by state, never by exit code" discipline
`test_push_gate.py`'s own `PushGateTestBase` already established: a
rejected push must leave the bare repo's refs untouched, not merely print a
refusal.

**Fake `${HOME}/.claude/scripts` layout.** The installed hook resolves the
gate at `${HOME}/.claude/scripts/push-gate.sh` -- the same path a real
`install.sh` / `install.sh --update` run ships it to (see install.sh's own
FRAMEWORK array, which includes `scripts` wholesale). `InstallPushGateHookTestBase`
reproduces that layout under a throwaway `$HOME`, copying this repository's
OWN `push-gate.sh` / `artifact-gate.sh` / `memory-sync.sh` /
`lib/discipline_gate.sh` there -- never a second, hand-written stand-in --
so a change to any of those four is exercised through this suite too.

**The canary.** `Quuxcorp`, the same fictional name
`test_push_gate.py`/`test_memory_sync_promote.py` already use as
`DENY_NAME`, stands in for a tenant/project name. `leak()` assembles a
credential-assignment SHAPE from harmless fragments, mirroring both of
those files' own helper, so this file's own text is never itself a finding
on the repository's own sweep.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
INSTALLER = SCRIPTS_DIR / "install-push-gate-hook.sh"
PUSH_GATE = SCRIPTS_DIR / "push-gate.sh"
ARTIFACT_GATE = SCRIPTS_DIR / "artifact-gate.sh"
MEMORY_SYNC = SCRIPTS_DIR / "memory-sync.sh"
LIB = SCRIPTS_DIR / "lib" / "discipline_gate.sh"


def leak(*parts):
    """Assemble a leak-shaped fixture from fragments that are harmless
    apart -- see test_push_gate.py's own `leak()` for the full rationale."""
    return "".join(parts)


# A fictional name, never a real tenant.
DENY_NAME = "Quuxcorp"

CREDENTIAL = leak("api", "_key = \"", "A1b2C3d4E5f6G7h8I9j0K1l2M3\"")

CLEAN_TEXT = "# Title\n\nSome ordinary prose about a skill prompt.\n"


class InstallPushGateHookTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-install-push-gate-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.home = self.tmp / "home"
        (self.home / ".claude" / "scripts" / "lib").mkdir(parents=True)

    def deploy_gate(self):
        """Populate the fake ${HOME}/.claude/scripts layout with this
        repository's own gate scripts -- opt-in per test, so the
        "gate missing" scenario is reachable simply by never calling this."""
        for src, rel in (
            (PUSH_GATE, "scripts/push-gate.sh"),
            (ARTIFACT_GATE, "scripts/artifact-gate.sh"),
            (MEMORY_SYNC, "scripts/memory-sync.sh"),
            (LIB, "scripts/lib/discipline_gate.sh"),
        ):
            dst = self.home / ".claude" / rel
            shutil.copy2(src, dst)
            dst.chmod(dst.stat().st_mode | 0o111)

    def _prepared_work(self):
        """A remote + a client clone with the hook installed and a deny-list
        configured -- the fixture every real-push test in this file starts
        from. Lives on the shared base, not on any one TestCase, so classes
        exercising different ref SHAPES (a single clean/leaking push here,
        deletions/force-pushes/multi-ref pushes in
        RefShapeEdgeCasesGoThroughTheInstalledHookTest) share it via
        composition rather than one inheriting the other's unrelated test
        methods."""
        self.deploy_gate()
        (self.home / ".claude" / "memory-sync.json").write_text(
            '{"gate": {"denyNames": ["%s"]}}' % DENY_NAME, encoding="utf-8"
        )
        remote = self.init_bare_remote()
        work = self.clone_work(remote)
        r = self.run_installer(work, env=self.env())
        self.assertEqual(r.returncode, 0, self.output(r))
        return remote, work

    def env(self, **extra):
        e = {
            "HOME": str(self.home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "GIT_AUTHOR_NAME": "ccpr test",
            "GIT_AUTHOR_EMAIL": "ccpr@example.invalid",
            "GIT_COMMITTER_NAME": "ccpr test",
            "GIT_COMMITTER_EMAIL": "ccpr@example.invalid",
        }
        e.update(extra)
        return e

    def _git(self, *args, cwd=None, env=None, input=None):
        return subprocess.run(
            ["git", *[str(a) for a in args]],
            cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, env=env or self.env(),
            input=input,
        )

    def run_installer(self, project_dir, env=None):
        return subprocess.run(
            ["bash", str(INSTALLER), str(project_dir)],
            capture_output=True, text=True, env=env or self.env(),
        )

    def init_bare_remote(self):
        remote = self.tmp / "remote.git"
        r = self._git("init", "--quiet", "--bare", "--initial-branch=main", remote)
        self.assertEqual(r.returncode, 0, r.stderr)
        return remote

    def clone_work(self, remote, name="work"):
        work = self.tmp / name
        r = self._git("clone", "--quiet", remote, work)
        self.assertEqual(r.returncode, 0, r.stderr)
        return work

    def write(self, repo, name, text):
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def commit_all(self, repo, message="x"):
        r = self._git("add", "-A", cwd=repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self._git("commit", "--quiet", "-m", message, cwd=repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self._git("rev-parse", "HEAD", cwd=repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def push(self, repo, remote, refspec="main"):
        return self._git("push", remote, refspec, cwd=repo)

    def remote_state(self, remote):
        refs = self._git("for-each-ref", "--format=%(refname) %(objectname)", cwd=remote)
        log = self._git("log", "--all", "--format=%H %s", cwd=remote)
        self.assertEqual(refs.returncode, 0, refs.stderr)
        self.assertEqual(log.returncode, 0, log.stderr)
        return refs.stdout, log.stdout

    @staticmethod
    def output(result):
        return result.stdout + result.stderr


# ---------------------------------------------------------------------------
# 1. A non-git directory refuses installation with exit 2, before writing
#    anything.
# ---------------------------------------------------------------------------
class NotAGitRepoRefusesInstallTest(InstallPushGateHookTestBase):
    def test_a_non_git_directory_exits_2(self):
        plain = self.tmp / "not-a-repo"
        plain.mkdir()
        r = self.run_installer(plain)
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assertFalse((plain / ".git").exists())


# ---------------------------------------------------------------------------
# 2. An existing pre-push hook is backed up, never silently overwritten.
# ---------------------------------------------------------------------------
class ExistingHookIsBackedUpTest(InstallPushGateHookTestBase):
    def test_an_existing_hook_is_preserved_in_a_timestamped_backup(self):
        remote = self.init_bare_remote()
        work = self.clone_work(remote)
        hooks_dir = work / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        original = "#!/bin/sh\necho 'pre-existing hook'\n"
        (hooks_dir / "pre-push").write_text(original, encoding="utf-8")

        r = self.run_installer(work)
        self.assertEqual(r.returncode, 0, self.output(r))

        backups = list(hooks_dir.glob("pre-push.bak.*"))
        self.assertEqual(len(backups), 1, "expected exactly one backup: %s" % backups)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), original)

        new_hook = (hooks_dir / "pre-push").read_text(encoding="utf-8")
        self.assertNotEqual(new_hook, original)
        self.assertIn("push-gate.sh", new_hook)


# ---------------------------------------------------------------------------
# 2b. An existing pre-push hook that is a SYMLINK is refused outright, never
#     followed -- the same "a shape that has no legitimate reason to exist
#     here is its own finding, not routed around" rule
#     push-gate.sh's own is_unsafe_repo_path() already applies to a tree
#     entry escaping its scan sandbox. Hook managers (husky, pre-commit,
#     lefthook) routinely leave `.git/hooks/pre-push` as a symlink onto a
#     file THEY manage -- reproduced directly: the `cp` backup step read
#     the symlink's TARGET content into a file inside the repo (an
#     information leak), and the `cat >` write step overwrote the external
#     target itself (an integrity loss) -- neither step ever checked
#     `[ -L ]` before its own `[ -f ]` test, and a symlink onto an existing
#     file satisfies both.
# ---------------------------------------------------------------------------
class ExistingHookIsASymlinkRefusesInstallTest(InstallPushGateHookTestBase):
    def test_a_symlinked_hook_is_refused_and_the_external_target_is_untouched(self):
        remote = self.init_bare_remote()
        work = self.clone_work(remote)
        hooks_dir = work / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        external_target = self.tmp / "externally-managed-hook.sh"
        original = "#!/bin/sh\necho 'managed by another hook tool'\n"
        external_target.write_text(original, encoding="utf-8")
        (hooks_dir / "pre-push").symlink_to(external_target)

        r = self.run_installer(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assertIn(str(external_target), self.output(r))

        self.assertEqual(
            external_target.read_text(encoding="utf-8"), original,
            "the externally-managed symlink target was overwritten",
        )
        self.assertTrue(
            (hooks_dir / "pre-push").is_symlink(),
            "the pre-existing symlink itself was replaced",
        )
        self.assertEqual(
            list(hooks_dir.glob("pre-push.bak.*")), [],
            "a backup must not be written from a symlink's target content",
        )


# ---------------------------------------------------------------------------
# 3. The written hook is executable and syntactically valid bash.
# ---------------------------------------------------------------------------
class WrittenHookIsExecutableAndSyntacticallyValidTest(InstallPushGateHookTestBase):
    def test_the_installed_hook_is_executable_and_bash_n_clean(self):
        remote = self.init_bare_remote()
        work = self.clone_work(remote)
        r = self.run_installer(work)
        self.assertEqual(r.returncode, 0, self.output(r))

        hook_path = work / ".git" / "hooks" / "pre-push"
        self.assertTrue(hook_path.exists())
        self.assertTrue(os.access(hook_path, os.X_OK), "hook is not executable")

        check = subprocess.run(
            ["bash", "-n", str(hook_path)], capture_output=True, text=True
        )
        self.assertEqual(check.returncode, 0, check.stderr)


# ---------------------------------------------------------------------------
# 4/5. A real `git push`, driven through the installed hook: a planted deny
#      name is rejected (remote state proof), a clean push goes through.
# ---------------------------------------------------------------------------
class InstalledHookDrivesARealPushTest(InstallPushGateHookTestBase):
    def test_a_planted_deny_name_is_rejected_and_the_remote_does_not_move(self):
        remote, work = self._prepared_work()
        self.write(work, "notes.py", "SETTINGS = {\n    %s\n}\n" % CREDENTIAL)
        sha = self.commit_all(work, "plant a secret")
        before = self.remote_state(remote)

        r = self.push(work, remote)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assertEqual(self.remote_state(remote), before, "the remote moved")

        cat = self._git("cat-file", "-e", sha, cwd=remote)
        self.assertNotEqual(
            cat.returncode, 0,
            "a rejected push's own commit object is present on the remote",
        )

    def test_a_clean_push_goes_through(self):
        remote, work = self._prepared_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        self.commit_all(work, "clean change")

        r = self.push(work, remote)
        self.assertEqual(r.returncode, 0, self.output(r))

        tree = self._git("ls-tree", "-r", "--name-only", "main", cwd=remote)
        self.assertIn("docs/notes.md", tree.stdout.splitlines())


# ---------------------------------------------------------------------------
# 5b. Code-review follow-up (CCP-1137 Auflage 2): the installer's own header
#     comments claim three ref shapes need no special-casing in the hook
#     itself because push-gate.sh already handles them (a deletion's
#     all-zero newrev, a force-push's irrelevant oldrev, a multi-ref push's
#     own multi-line stdin loop). Those claims were reasoned from
#     push-gate.sh's SOURCE in the installer's own comments but never driven
#     through the INSTALLED hook via a real `git push` -- this class closes
#     that gap.
# ---------------------------------------------------------------------------
class RefShapeEdgeCasesGoThroughTheInstalledHookTest(InstallPushGateHookTestBase):
    def test_a_branch_deletion_goes_through(self):
        remote, work = self._prepared_work()
        self._git("checkout", "-q", "-b", "feature-x", cwd=work)
        self.write(work, "docs/feature.md", CLEAN_TEXT)
        self.commit_all(work, "feature commit")
        r = self.push(work, remote, refspec="feature-x")
        self.assertEqual(r.returncode, 0, "expected the feature push to land:\n" + self.output(r))

        r = self.push(work, remote, refspec=":feature-x")
        self.assertEqual(r.returncode, 0, "expected the deletion to go through:\n" + self.output(r))

        refs, _log = self.remote_state(remote)
        self.assertNotIn("refs/heads/feature-x", refs)

    def test_a_force_push_carrying_a_new_secret_is_still_rejected(self):
        remote, work = self._prepared_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        self.commit_all(work, "clean change")
        r = self.push(work, remote)
        self.assertEqual(r.returncode, 0, "expected the clean push to land:\n" + self.output(r))
        before = self.remote_state(remote)

        # Amend the SAME commit rather than adding a new one -- this is what
        # makes the second push a force-push (a non-fast-forward rewrite of
        # `main`'s own history), not just another ordinary push.
        self.write(work, "notes.py", "SETTINGS = {\n    %s\n}\n" % CREDENTIAL)
        r = self._git("add", "-A", cwd=work)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self._git("commit", "--quiet", "--amend", "--no-edit", cwd=work)
        self.assertEqual(r.returncode, 0, r.stderr)

        r = self.push(work, remote, refspec="+main")
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assertEqual(self.remote_state(remote), before, "the remote moved")

    def test_two_refs_in_one_push_are_both_blocked_by_one_leak(self):
        remote, work = self._prepared_work()
        before = self.remote_state(remote)

        self._git("checkout", "-q", "-b", "branch-clean", cwd=work)
        self.write(work, "docs/clean.md", CLEAN_TEXT)
        self.commit_all(work, "clean branch commit")

        self._git("checkout", "-q", "-b", "branch-leak", "main", cwd=work)
        self.write(work, "notes.py", "SETTINGS = {\n    %s\n}\n" % CREDENTIAL)
        self.commit_all(work, "leaking branch commit")

        r = self._git(
            "push", remote, "branch-clean", "branch-leak", cwd=work, env=self.env(),
        )
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assertEqual(
            self.remote_state(remote), before,
            "the remote moved -- a leak on one ref must block the WHOLE push, "
            "including the sibling ref that was clean on its own",
        )


# ---------------------------------------------------------------------------
# 6. The gate missing at its expected location: a loud abort, not a silent
#    pass-through.
# ---------------------------------------------------------------------------
class MissingGateAbortsLoudlyTest(InstallPushGateHookTestBase):
    def test_a_push_is_refused_when_push_gate_sh_is_not_installed(self):
        # Deliberately never calling self.deploy_gate() -- $HOME/.claude
        # exists (the installer itself needs no gate to be present) but
        # scripts/push-gate.sh under it does not.
        remote = self.init_bare_remote()
        work = self.clone_work(remote)
        r = self.run_installer(work, env=self.env())
        self.assertEqual(r.returncode, 0, self.output(r))

        self.write(work, "docs/notes.md", CLEAN_TEXT)
        self.commit_all(work, "clean change")
        before = self.remote_state(remote)

        r = self.push(work, remote)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assertEqual(self.remote_state(remote), before, "the remote moved")
        self.assertIn("push-gate.sh not found", self.output(r))


if __name__ == "__main__":
    unittest.main()
