"""Tests for WI-0031 — git's own transport stderr bypassing the memory-sync mask.

WI-0016 routed every line `memory-sync.sh` prints ITSELF (note/warn/die) through
`gate_redact_path` + the `$HOME` fold. It did not — could not, without this
change — cover stderr that `git clone`/`git fetch`/`git push` write directly:
a transport failure prints the repository URL verbatim, and that URL is
exactly where a configured tenant/project name lives (see `authed_url()` /
`REPO_URL` in memory-sync.sh). The fix captures that stderr and re-emits it
through `die()`, i.e. the SAME mask path everything else in the script uses.

This is a **new sibling module**, not an addition to `test_memory_sync_promote.py`:
that file's fixture (`PromoteTestBase`) is built around one push against one
fixed bare repo and the destination-path gate. These tests need a state
`pull` can't get from that fixture — a clone that already exists so a SECOND
`pull` exercises `git fetch` (not `git clone`), and a bare repo whose
permissions are flipped mid-test so `git push` fails without ever touching a
network. Bolting that onto `PromoteTestBase` would grow an unrelated fixture
rather than reuse one.

**Offline discipline**: every failing "remote" here is either a refused local
port (`127.0.0.1:1` — nothing listens there, matching the probe recorded for
this work item) or a real local bare repository reached over the filesystem
transport. No test contacts a real host. No real tenant/project name is used
anywhere — `Quuxcorp` throughout, same fictional name as the promote suite.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_SYNC = REPO_ROOT / "scripts" / "memory-sync.sh"

# A fictional tenant/project name — never a real one. Stands in for whatever
# a deny-list entry protects, and is what the masked note/die lines exist to
# hide from a terminal, a shell history or a CI log.
DENY_NAME = "Quuxcorp"

# A connection that fails FAST and OFFLINE: nothing binds port 1, so the
# kernel refuses the connection immediately instead of timing out. Matches
# the probe recorded against git 2.50.1 for this work item.
DEAD_REMOTE = "http://127.0.0.1:1"

# A fixed, obviously-fake token. Pins WI-0031's own measurement that git
# strips `oauth2:<token>@` from its own error text — if a future git stops
# doing that, this string appearing in captured+re-emitted output is exactly
# the regression this pin exists to catch.
FAKE_TOKEN = "ccpr-test-fake-token-9x7q2"


class TransportErrorTestBase(unittest.TestCase):
    """A `pull`/`promote` fixture with a redirected HOME and a local bare repo."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-memory-sync-transport-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.home = self.tmp / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.clone = self.tmp / "clone"
        self.token = self.tmp / "token"
        self.token.write_text(FAKE_TOKEN + "\n", encoding="utf-8")

    # --- fixture -----------------------------------------------------------
    def _git(self, *args, cwd=None):
        return subprocess.run(
            ["git", *[str(a) for a in args]],
            cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, env=self.env(),
        )

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

    def seed_bare_repo(self, remote_path):
        """A bare repo at `remote_path` with one commit on `main` — a
        plausible shared repo that a real `pull`/fetch can succeed against."""
        remote_path = Path(remote_path)
        r = self._git("init", "--quiet", "--bare", "--initial-branch=main", remote_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        seed = self.tmp / (remote_path.name + "-seed")
        self.assertEqual(
            self._git("init", "--quiet", "--initial-branch=main", seed).returncode, 0
        )
        (seed / "README.md").write_text("# shared\n", encoding="utf-8")
        self.assertEqual(self._git("add", "README.md", cwd=seed).returncode, 0)
        self.assertEqual(self._git("commit", "--quiet", "-m", "init", cwd=seed).returncode, 0)
        r = self._git("push", "--quiet", str(remote_path), "main", cwd=seed)
        self.assertEqual(r.returncode, 0, r.stderr)
        shutil.rmtree(seed)
        return remote_path

    def write_config(self, repo_url, deny_names=(DENY_NAME,)):
        cfg = {
            "repoUrl": str(repo_url),
            "namespace": "quuxcorp",
            "tokenFile": str(self.token),
            "clonePath": str(self.clone),
            "gate": {"denyNames": list(deny_names)},
        }
        (self.home / ".claude" / "memory-sync.json").write_text(
            json.dumps(cfg), encoding="utf-8"
        )

    def set_repo_url(self, repo_url):
        """Rewrite ONLY repoUrl in the already-written config (namespace,
        clonePath, denyNames stay put) -- used to turn a working `pull` into
        a failing one without re-creating the whole fixture."""
        cfg_path = self.home / ".claude" / "memory-sync.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["repoUrl"] = str(repo_url)
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    def run_sync(self, *args):
        return subprocess.run(
            ["bash", str(MEMORY_SYNC), *[str(a) for a in args]],
            capture_output=True, text=True, env=self.env(),
        )

    def pull(self):
        return self.run_sync("pull")

    def promote(self, src, dst):
        return self.run_sync("promote", src, dst)

    def write_src(self, name="note.md", text="# Rule\n\nA durable piece of knowledge.\n"):
        p = self.work / name
        p.write_text(text, encoding="utf-8")
        return p

    @staticmethod
    def output(result):
        return result.stdout + result.stderr


# ---------------------------------------------------------------------------
# `git clone` — no clone exists yet, so `ensure_clone` takes the clone branch.
# ---------------------------------------------------------------------------
class CloneFailureTest(TransportErrorTestBase):
    def test_clone_failure_redacts_the_tenant_name_keeps_the_cause_and_fails(self):
        self.write_config(f"{DEAD_REMOTE}/{DENY_NAME}/commons.git")

        r = self.pull()
        out = self.output(r)

        # (c) — the script's own exit status, not git's raw one: git_or_die
        # routes every capture through die(), which always exits 2. A pipe
        # or `&&` chain here would test the WRONG exit code (G-116); this
        # reads subprocess.returncode directly, i.e. the script's own status.
        self.assertEqual(r.returncode, 2, out)
        # (a) — the tenant name, which lived in the URL's path, must not
        # travel. Case-sensitive on purpose: DENY_NAME never appears
        # lowercased or uppercased by git either.
        self.assertNotIn(DENY_NAME, out, out)
        self.assertIn("<redacted>", out, out)
        # (b) — the fix must not have become the option the owner rejected
        # (suppress + generic message): git's own cause text survives.
        self.assertIn("git clone:", out, out)
        self.assertIn("connect", out.lower(), out)

    def test_clone_failure_does_not_leak_the_token(self):
        self.write_config(f"{DEAD_REMOTE}/{DENY_NAME}/commons.git")

        r = self.pull()
        out = self.output(r)

        self.assertEqual(r.returncode, 2, out)
        # Pin for WI-0031's own measurement: git strips `oauth2:<token>@`
        # from its transport error text before this script ever sees it. If
        # a future git regresses on that, this is where it will be caught.
        self.assertNotIn(FAKE_TOKEN, out, out)


# ---------------------------------------------------------------------------
# `git fetch` — a clone from a WORKING local remote already exists, so the
# second `pull` against a broken repoUrl takes the fetch branch, not clone.
# ---------------------------------------------------------------------------
class FetchFailureTest(TransportErrorTestBase):
    def test_fetch_failure_redacts_the_tenant_name_keeps_the_cause_and_fails(self):
        good_remote = self.seed_bare_repo(self.tmp / f"{DENY_NAME}-remote.git")
        self.write_config(good_remote)
        first = self.pull()
        self.assertEqual(first.returncode, 0, self.output(first))
        self.assertTrue((self.clone / ".git").is_dir())

        self.set_repo_url(f"{DEAD_REMOTE}/{DENY_NAME}/commons.git")
        r = self.pull()
        out = self.output(r)

        self.assertEqual(r.returncode, 2, out)
        self.assertNotIn(DENY_NAME, out, out)
        self.assertIn("<redacted>", out, out)
        # Distinguishes this from the clone-failure test: proves the FETCH
        # call site's own capture fired, not the clone one re-triggering.
        self.assertIn("git fetch:", out, out)
        self.assertNotIn("git clone:", out, out)
        self.assertIn("connect", out.lower(), out)


# ---------------------------------------------------------------------------
# `git push` — over the LOCAL filesystem transport (no network at all), made
# to fail by revoking write permission on the bare repo after seeding it, so
# `fetch`/clone succeed (read-only is fine for those) and only push fails.
# ---------------------------------------------------------------------------
class PushFailureTest(TransportErrorTestBase):
    def test_push_failure_redacts_the_tenant_name_keeps_the_cause_and_fails(self):
        remote = self.seed_bare_repo(self.tmp / f"{DENY_NAME}-remote.git")
        self.write_config(remote)
        src = self.write_src()

        # Revoke write access on the bare repo AFTER seeding it: `promote`'s
        # own `ensure_clone` still needs to read it (clone/fetch), only the
        # push at the end must fail.
        os.chmod(remote, remote.stat().st_mode & ~0o222)
        for root, dirs, files in os.walk(remote):
            for name in dirs + files:
                p = Path(root) / name
                os.chmod(p, p.stat().st_mode & ~0o222)
        self.addCleanup(self._restore_write, remote)

        r = self.promote(src, "instincts/note.md")
        out = self.output(r)

        self.assertEqual(r.returncode, 2, out)
        self.assertNotIn(DENY_NAME, out, out)
        self.assertIn("<redacted>", out, out)
        self.assertIn("git push:", out, out)
        # git's own cause for a permission-denied local push (wording varies
        # by git version, but always mentions the failed push itself).
        self.assertIn("failed to push", out.lower(), out)

    @staticmethod
    def _restore_write(remote):
        # addCleanup runs LIFO, before the base class's tmp-dir rmtree
        # cleanup (registered earlier, in setUp) — restoring write access
        # here is what lets that later rmtree succeed at all.
        for root, dirs, files in os.walk(remote):
            for name in dirs + files:
                p = Path(root) / name
                st = p.stat()
                os.chmod(p, st.st_mode | stat.S_IWUSR)
        st = remote.stat()
        os.chmod(remote, st.st_mode | stat.S_IWUSR)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
