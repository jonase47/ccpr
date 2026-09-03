"""test_push_gate.py -- CCP-1137: end-to-end tests for scripts/push-gate.sh,
the server-side pre-receive discipline gate.

`push-gate.sh` is the piece that closes the gap `scripts/artifact-gate.sh` and
`scripts/memory-sync.sh promote` already close on their own client-side paths:
a direct `git commit && git push` reaches neither of them. It owns SCOPE
(which paths a push introduces, across every new commit, not just the net
diff -- a leak planted in one commit and removed in the next still ships in
history) and the translation into a pre-receive exit code; the actual
scanning stays in `scripts/lib/discipline_gate.sh`, reused unmodified via
`artifact-gate.sh` (profile "artifact", over every path) and
`memory-sync.sh gate` (profile "memory", over `memory/`/`instincts/` paths
only). This suite drives the whole thing through a REAL `git push` against a
local bare repository with the gate installed as its `pre-receive` hook --
never by invoking `push-gate.sh` as a library function -- because the
question this item exists to answer is "does the object ever land", and a
bare repository's own state is the only witness to that.

**Server layout, mirrored.** `PushGateTestBase` copies the three real
scripts (`push-gate.sh`, `artifact-gate.sh`, `memory-sync.sh`) plus
`lib/discipline_gate.sh` into a NON-git directory at the same relative
paths the server deployment uses (`<data>/ccpr-gate/<sha>/scripts/...`) --
the same technique `test_artifact_gate.py`'s `CiTemplateExecutionTest.
make_fixture_repo` already uses for the CI template, and for the same
reason: `push-gate.sh` resolves its two siblings relative to its OWN
location, so a fixture that does not reproduce that layout would never
exercise a genuine, working gate invocation.

**Proof by state, never by exit code.** `PromoteTestBase`'s own header
already says it best: "a bypass that ends in `exit 0` and a bypass that
ends in `exit 2` are distinguished by what is in the tree, not by what the
script says." Every rejection test in this file asserts BOTH that the bare
repository's refs and reachable commits did not move (`remote_state()`,
identical shape to `PromoteTestBase.remote_state`) AND that the specific
commit object the push tried to introduce is unreachable afterwards
(`git cat-file -e <sha>` fails) -- pre-receive quarantines incoming objects
and discards the quarantine on rejection, so a genuinely rejected push never
leaves its objects behind, but a hook that merely printed a refusal and then
still let the ref move would pass the first assertion and fail the second.

**The canary.** `Quuxcorp`, the same fictional name
`test_memory_sync_promote.py` already uses as `DENY_NAME`, stands in for a
tenant/project name throughout. Genuine secret and leak SHAPES (a credential
assignment, an oversized/binary blob) are assembled from harmless fragments
via `leak()`, mirroring `test_artifact_gate.py`'s own helper -- spelled out,
they would make this very file a finding on the repository's own sweep.
"""

import json
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
PUSH_GATE = SCRIPTS_DIR / "push-gate.sh"
ARTIFACT_GATE = SCRIPTS_DIR / "artifact-gate.sh"
MEMORY_SYNC = SCRIPTS_DIR / "memory-sync.sh"
LIB = SCRIPTS_DIR / "lib" / "discipline_gate.sh"

# The interpreter the shipped scripts must survive. macOS's system bash is
# 3.2.57; a bash-4-only construct (an unguarded empty-array expansion under
# `set -u` is exactly this shape, not a case expansion or an associative
# array, but the same "silent on bash 5, loud on bash 3.2" family) is only a
# bug because *this* is what runs it.
SYSTEM_BASH = "/bin/bash"


def _bash_major_minor(path):
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True).stdout
    except OSError:
        return None
    m = re.search(r"version (\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else None


def leak(*parts):
    """Assemble a leak-shaped fixture from fragments that are harmless apart.

    See test_artifact_gate.py's own `leak()` for the full rationale -- the
    identical technique, kept file-local so this suite does not depend on
    import order or path tricks to reach a sibling test module.
    """
    return "".join(parts)


# A fictional name, never a real tenant.
DENY_NAME = "Quuxcorp"

# A credential-assignment shape (GATE_RE_SECRET_KV): keyword, `=`, a value
# starting alphanumeric and at least 16 characters long. Split so no single
# fragment is credential-shaped on its own.
CREDENTIAL = leak("api", "_key = \"", "A1b2C3d4E5f6G7h8I9j0K1l2M3\"")

# Clean under BOTH profiles: no work-item shapes the memory profile flags,
# no deny name, no secret/personal/network shape.
CLEAN_TEXT = "# Title\n\nSome ordinary prose about a skill prompt.\n"

# Clean under the artifact profile (no secret/personal/network/denylist
# shape) but dirty under the memory profile: "TODO:" is a work-item marker
# check 'content' flags, and 'content' is deliberately NOT part of the
# artifact profile (see discipline_gate.sh's own profile table).
TODO_TEXT = "# Note\n\nTODO: something still needs doing here.\n"


class PushGateTestBase(unittest.TestCase):
    """A push fixture: a real local bare repo with push-gate.sh installed as
    its pre-receive hook, driven by a real `git push` from a real clone."""

    # Overridden to False by the one test class that needs a bare repo with
    # literally zero refs at push time -- _seed_bare_repo() always lands one
    # commit on `main` BEFORE the hook is installed (a plausible pre-existing
    # shared repo), so the genuinely-empty-repo shape is unreachable through
    # the ordinary fixture and must be opted out of explicitly.
    SEED_BARE_REPO = True

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-push-gate-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.home = self.tmp / "home"
        (self.home / ".claude").mkdir(parents=True)

        # --- server-side gate layout (mirrors CiTemplateExecutionTest) ---
        self.gate_root = self.tmp / "gate-root"
        (self.gate_root / "scripts" / "lib").mkdir(parents=True)
        for src, rel in (
            (PUSH_GATE, "scripts/push-gate.sh"),
            (ARTIFACT_GATE, "scripts/artifact-gate.sh"),
            (MEMORY_SYNC, "scripts/memory-sync.sh"),
            (LIB, "scripts/lib/discipline_gate.sh"),
        ):
            dst = self.gate_root / rel
            shutil.copy2(src, dst)
            dst.chmod(dst.stat().st_mode | 0o111)
        self.push_gate_copy = self.gate_root / "scripts" / "push-gate.sh"

        # A config file OUTSIDE $HOME, on purpose: the real deployment points
        # MEMORY_SYNC_CONFIG at a server-owned path, never at a resolved
        # $HOME -- the hook runs under whatever account Forgejo uses, not
        # under an operator's own home directory.
        self.gate_config = self.tmp / "gate-config.json"

        self.remote = self.tmp / "remote.git"
        r = self._git("init", "--quiet", "--bare", "--initial-branch=main", self.remote)
        self.assertEqual(r.returncode, 0, r.stderr)
        if self.SEED_BARE_REPO:
            self._seed_bare_repo()

        self._work_counter = 0

    # --- fixture -----------------------------------------------------
    def _git(self, *args, cwd=None, env=None, input=None):
        return subprocess.run(
            ["git", *[str(a) for a in args]],
            cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, env=env or self.env(),
            input=input,
        )

    def craft_path_traversal_commit(self, repo, dotdot_levels=1, parent="HEAD"):
        """Raw-plumbing commit whose tree stores one or more literal '..'
        path components, nested `dotdot_levels` deep, wrapping a blob named
        `secret.txt`.

        git's own object model has no opinion on path-component semantics
        -- only `git mktree`'s input format -- and a tree entry literally
        named '..' is accepted without complaint by `git mktree`. Git's OWN
        fsck DOES reject it (confirmed directly: with
        `receive.fsckObjects=true` set on the receiving bare repo, the push
        fails with "hasDotdot: contains '..'"). `receive.fsckObjects`
        defaults to false and is unset on the deployment this hook actually
        runs on, so a commit built on top of one survives a normal
        `git push` there -- `push-gate.sh`'s own `is_unsafe_repo_path()` is
        the only active guard, matching the corrected comment at the top of
        that function.
        `git diff-tree` then reports the PATH field as an innocuous-
        looking string, e.g. `subdir/../secret.txt` for `dotdot_levels=1`
        -- exactly the shape a naive `mkdir -p "$(dirname "$dest")"` +
        `git cat-file blob ... > "$dest"` would happily write through.
        """
        blob = self._git("hash-object", "-w", "--stdin", cwd=repo, input="evil content\n")
        self.assertEqual(blob.returncode, 0, blob.stderr)
        tree_sha = self._git(
            "mktree", cwd=repo, input="100644 blob %s\tsecret.txt\n" % blob.stdout.strip()
        )
        self.assertEqual(tree_sha.returncode, 0, tree_sha.stderr)
        current = tree_sha.stdout.strip()
        for _ in range(dotdot_levels):
            wrapped = self._git("mktree", cwd=repo, input="040000 tree %s\t..\n" % current)
            self.assertEqual(wrapped.returncode, 0, wrapped.stderr)
            current = wrapped.stdout.strip()
        root = self._git("mktree", cwd=repo, input="040000 tree %s\tsubdir\n" % current)
        self.assertEqual(root.returncode, 0, root.stderr)

        parent_sha = self._git("rev-parse", parent, cwd=repo)
        self.assertEqual(parent_sha.returncode, 0, parent_sha.stderr)

        commit = self._git(
            "commit-tree", root.stdout.strip(), "-p", parent_sha.stdout.strip(),
            "-m", "evil", cwd=repo,
        )
        self.assertEqual(commit.returncode, 0, commit.stderr)
        return commit.stdout.strip()

    def craft_traversal_commit_with_parts(self, repo, path_parts, parent="HEAD"):
        """Raw-plumbing commit whose tree encodes EXACTLY `path_parts`, the
        innermost (last) component always the leaf.

        `craft_path_traversal_commit` above always wraps its '..' component
        in an outer "subdir" tree, so it can only ever exercise the middle
        `*/../*` arm of `is_unsafe_repo_path`'s case pattern. This builds
        the tree bottom-up from an arbitrary component list instead, so a
        caller can hit the standalone `..`, leading `../*`, or trailing
        `*/..` arms too -- a case pattern narrowed to only the middle
        alternative would stay green against the existing tests and red
        only here.
        """
        blob = self._git("hash-object", "-w", "--stdin", cwd=repo, input="evil content\n")
        self.assertEqual(blob.returncode, 0, blob.stderr)
        leaf = self._git(
            "mktree", cwd=repo,
            input="100644 blob %s\t%s\n" % (blob.stdout.strip(), path_parts[-1]),
        )
        self.assertEqual(leaf.returncode, 0, leaf.stderr)
        current = leaf.stdout.strip()
        for comp in reversed(path_parts[:-1]):
            wrapped = self._git("mktree", cwd=repo, input="040000 tree %s\t%s\n" % (current, comp))
            self.assertEqual(wrapped.returncode, 0, wrapped.stderr)
            current = wrapped.stdout.strip()

        parent_sha = self._git("rev-parse", parent, cwd=repo)
        self.assertEqual(parent_sha.returncode, 0, parent_sha.stderr)

        commit = self._git(
            "commit-tree", current, "-p", parent_sha.stdout.strip(), "-m", "evil", cwd=repo,
        )
        self.assertEqual(commit.returncode, 0, commit.stderr)
        return commit.stdout.strip()

    def craft_gitlink_commit(self, repo, name="submod", parent="HEAD"):
        """Raw-plumbing commit adding one gitlink (mode 160000) tree entry,
        the shape a submodule reference takes -- pointing at a commit sha
        that does NOT exist in this repository's own object store (exactly
        like a real submodule reference, whose commit lives in a different
        repository). Used to prove the mode-160000 skip in
        process_diff_tree_records happens BEFORE anything tries to read a
        blob for it -- doing so would fail, since no such blob exists here.
        """
        fake_commit_sha = "a" * 40
        tree = self._git(
            "mktree", cwd=repo, input="160000 commit %s\t%s\n" % (fake_commit_sha, name)
        )
        self.assertEqual(tree.returncode, 0, tree.stderr)

        parent_sha = self._git("rev-parse", parent, cwd=repo)
        self.assertEqual(parent_sha.returncode, 0, parent_sha.stderr)

        commit = self._git(
            "commit-tree", tree.stdout.strip(), "-p", parent_sha.stdout.strip(),
            "-m", "add submodule reference", cwd=repo,
        )
        self.assertEqual(commit.returncode, 0, commit.stderr)
        return commit.stdout.strip()

    def craft_merge_commit(self, repo, leak_in_resolution=None):
        """Two branches that CONFLICT on the same file, merged with the
        conflict resolved by writing entirely new content that appears in
        NEITHER parent's own tree.

        A merge whose two sides touch DIFFERENT files does not isolate
        `--root -m`'s own effect: every commit `git rev-list` finds --
        including each SIDE commit, independent of merge topology -- is
        diffed on its own via the main per-commit loop regardless of
        whether the merge commit's own diff-tree call carries `-m` at
        all, so a leak planted in a side commit is caught by THAT
        commit's own diff either way (measured: an earlier version of
        this fixture, with the leak in a side commit's own new file,
        stayed GREEN even with `-m` removed from the merge's diff-tree
        call -- it proved nothing about the flag). Only content
        introduced during CONFLICT RESOLUTION -- committed as part of the
        merge commit ITSELF, never appearing in any single parent's own
        tree -- is exclusively visible through the merge commit's own
        `-m` diff.
        """
        self._git("checkout", "-q", "-b", "merge-side-a", cwd=repo)
        self.write(repo, "shared.md", "side A content\n")
        self.commit_all(repo, "side a")

        self._git("checkout", "-q", "-b", "merge-side-b", "main", cwd=repo)
        self.write(repo, "shared.md", "side B content\n")
        self.commit_all(repo, "side b")

        self._git("checkout", "-q", "merge-side-a", cwd=repo)
        merge = self._git("merge", "--no-ff", "--no-edit", "merge-side-b", cwd=repo)
        self.assertNotEqual(
            merge.returncode, 0,
            "expected a conflict to resolve by hand:\n" + merge.stdout + merge.stderr,
        )

        resolution = "resolved content\n" if leak_in_resolution is None else leak_in_resolution
        self.write(repo, "shared.md", resolution)
        add = self._git("add", "shared.md", cwd=repo)
        self.assertEqual(add.returncode, 0, add.stderr)
        commit = self._git("commit", "--no-edit", cwd=repo)
        self.assertEqual(commit.returncode, 0, commit.stderr)
        merge_sha = self._git("rev-parse", "HEAD", cwd=repo)
        self.assertEqual(merge_sha.returncode, 0, merge_sha.stderr)

        # Still on merge-side-a here, so moving "main" (not the checked-out
        # branch) is a plain fast-moving ref update, not a "force update the
        # current branch" refusal.
        self._git("branch", "-f", "main", "merge-side-a", cwd=repo)
        self._git("checkout", "-q", "main", cwd=repo)
        return merge_sha.stdout.strip()

    def _seed_bare_repo(self):
        """One commit landed on `main`, pushed BEFORE the hook is installed
        -- a plausible pre-existing shared repo, not itself subject to this
        suite's gate. The bare repo itself is already created by setUp;
        skipped entirely when SEED_BARE_REPO is False, leaving self.remote
        with genuinely zero refs at hook-install time."""
        seed = self.tmp / "seed"
        self.assertEqual(
            self._git("init", "--quiet", "--initial-branch=main", seed).returncode, 0
        )
        (seed / "README.md").write_text("# shared\n", encoding="utf-8")
        self.assertEqual(self._git("add", "README.md", cwd=seed).returncode, 0)
        self.assertEqual(self._git("commit", "--quiet", "-m", "init", cwd=seed).returncode, 0)
        r = self._git("push", "--quiet", self.remote, "main", cwd=seed)
        self.assertEqual(r.returncode, 0, r.stderr)
        shutil.rmtree(seed)

    def env(self, **extra):
        e = {
            "HOME": str(self.home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            # git refuses to commit without an identity, and HOME is empty
            # here. A reserved domain (RFC 2606) so no real mailbox is
            # written down.
            "GIT_AUTHOR_NAME": "ccpr test",
            "GIT_AUTHOR_EMAIL": "ccpr@example.invalid",
            "GIT_COMMITTER_NAME": "ccpr test",
            "GIT_COMMITTER_EMAIL": "ccpr@example.invalid",
        }
        e.update(extra)
        return e

    def write_config(self, **gate_keys):
        cfg = {
            "repoUrl": "https://git.invalid/org/repo.git",
            "namespace": "XX",
            "gate": gate_keys,
        }
        self.gate_config.write_text(json.dumps(cfg), encoding="utf-8")

    def install_hook(self, bash_path=None, memory_paths=None,
                      max_blob_bytes=None, max_commits=None):
        """Write <remote>/hooks/pre-receive as a POSIX-sh shim.

        Every value the real deployment would bake in at deploy time is
        exported explicitly here rather than relying on inherited
        environment -- the real hook runs under a service account whose
        $HOME the operator does not control, so MEMORY_SYNC_CONFIG must
        never depend on it (see the comment on self.gate_config above).
        """
        lines = ["#!/bin/sh"]
        lines.append("export MEMORY_SYNC_CONFIG=%s" % shlex.quote(str(self.gate_config)))
        if memory_paths is not None:
            lines.append("export PUSH_GATE_MEMORY_PATHS=%s" % shlex.quote(memory_paths))
        if max_blob_bytes is not None:
            lines.append("export PUSH_GATE_MAX_BLOB_BYTES=%s" % shlex.quote(str(max_blob_bytes)))
        if max_commits is not None:
            lines.append("export PUSH_GATE_MAX_COMMITS=%s" % shlex.quote(str(max_commits)))
        lines.append(
            "exec %s %s"
            % (shlex.quote(bash_path or "bash"), shlex.quote(str(self.push_gate_copy)))
        )
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("\n".join(lines) + "\n", encoding="utf-8")
        hook.chmod(0o755)

    def clone_work(self, name=None):
        name = name or ("work%d" % self._next_work_id())
        work = self.tmp / name
        r = self._git("clone", "--quiet", self.remote, work)
        self.assertEqual(r.returncode, 0, r.stderr)
        return work

    def _next_work_id(self):
        self._work_counter += 1
        return self._work_counter

    def write(self, repo, name, text):
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def write_bytes(self, repo, name, data):
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def commit_all(self, repo, message="x"):
        r = self._git("add", "-A", cwd=repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self._git("commit", "--quiet", "-m", message, cwd=repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self._git("rev-parse", "HEAD", cwd=repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def push(self, repo, refspec="main", extra_args=()):
        return self._git("push", *extra_args, self.remote, refspec, cwd=repo)

    # --- inspecting the "server" --------------------------------------
    def remote_state(self):
        """Everything a push would change: every ref and every commit."""
        refs = self._git("for-each-ref", "--format=%(refname) %(objectname)", cwd=self.remote)
        log = self._git("log", "--all", "--format=%H %s", cwd=self.remote)
        self.assertEqual(refs.returncode, 0, refs.stderr)
        self.assertEqual(log.returncode, 0, log.stderr)
        return refs.stdout, log.stdout

    def object_exists(self, sha):
        r = self._git("cat-file", "-e", sha, cwd=self.remote)
        return r.returncode == 0

    def assert_nothing_published(self, before, planted_sha=None, result=None):
        """The only assertion that counts: the bare repo did not move, and
        the object a rejected push tried to introduce is unreachable.

        Checked against the repository itself, never against an exit code:
        a hook that prints a refusal and still lets the ref move would pass
        an exit-code-only check.
        """
        detail = "" if result is None else "\n" + self.output(result)
        self.assertEqual(self.remote_state(), before, "the shared repo moved" + detail)
        if planted_sha is not None:
            self.assertFalse(
                self.object_exists(planted_sha),
                "a rejected push's own commit object is still present (no "
                "quarantine discard?): %s%s" % (planted_sha, detail),
            )

    @staticmethod
    def output(result):
        return result.stdout + result.stderr

    @staticmethod
    def hook_output(result):
        """Only the lines the SERVER side (this hook) actually emitted --
        `git push` relays them client-side prefixed "remote: ". This is
        deliberately narrower than `output()`: git's own LOCAL porcelain
        (e.g. "! [remote rejected] <local-refspec> -> ... (pre-receive hook
        declined)") echoes back the refspec the caller typed on their own
        command line -- unavoidably, since the pusher already knows the ref
        name they asked to push -- and is not something this hook emits or
        controls. A redaction promise only ever covers text this hook
        itself produces, the text that would actually reach a downstream
        server-side log.
        """
        out = PushGateTestBase.output(result)
        return "\n".join(
            line for line in out.splitlines() if line.startswith("remote:")
        )


# ---------------------------------------------------------------------------
# 1. WI-... -- a deny name planted in file CONTENT is rejected, and the
#    refusal itself never prints the name.
# ---------------------------------------------------------------------------
class PlantedDenyNameInContentIsRejectedTest(PushGateTestBase):
    def test_a_planted_deny_name_in_file_content_is_rejected(self):
        self.write_config(denyNames=[DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "notes.py", "# customer note: %s uses this system\n" % DENY_NAME)
        sha = self.commit_all(work)
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)

    def test_the_refusal_does_not_print_the_configured_name(self):
        self.write_config(denyNames=[DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "notes.py", "# customer note: %s uses this system\n" % DENY_NAME)
        sha = self.commit_all(work)
        before = self.remote_state()
        r = self.push(work)
        # A refusal is the premise this test's own name is about, not
        # something to take on faith from the sibling test above -- without
        # this, a regression that made the redaction path run on an
        # ACCEPTED push would still read as a name-absence pass here.
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)
        self.assertNotIn(DENY_NAME.lower(), self.output(r).lower(), self.output(r))


# ---------------------------------------------------------------------------
# 2. A deny name in the PATH, clean content -- the path-deny check, not the
#    content scan, must be what fires.
# ---------------------------------------------------------------------------
class PlantedDenyNameInThePathIsRejectedTest(PushGateTestBase):
    def test_a_deny_name_in_the_path_is_rejected_with_clean_content(self):
        self.write_config(denyNames=[DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "%s-notes.md" % DENY_NAME, CLEAN_TEXT)
        sha = self.commit_all(work)
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)


# ---------------------------------------------------------------------------
# 3. The incident's own shape: a genuine secret pattern in a `.py` file.
#    Pins K4 -- no extension whitelist, unlike the dormant `*.md`-only hook.
# ---------------------------------------------------------------------------
class LeakInANonMarkdownFileIsRejectedTest(PushGateTestBase):
    def test_a_real_secret_shape_in_a_py_file_is_rejected(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "fixtures/data.py", "SETTINGS = {\n    %s\n}\n" % CREDENTIAL)
        sha = self.commit_all(work)
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)


# ---------------------------------------------------------------------------
# 4. A clean push is accepted, arrives intact, and the hook's own scope
#    line proves it actually ran -- an unconditional `exit 0` hook would
#    pass the first assertion but not the second.
# ---------------------------------------------------------------------------
class CleanPushIsAcceptedTest(PushGateTestBase):
    def test_a_clean_push_is_accepted_and_arrives_intact(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        self.commit_all(work)
        r = self.push(work)
        self.assertEqual(r.returncode, 0, self.output(r))
        tree = self._git("ls-tree", "-r", "--name-only", "main", cwd=self.remote)
        self.assertIn("docs/notes.md", tree.stdout.splitlines())

    def test_the_hook_actually_ran(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        self.commit_all(work)
        r = self.push(work)
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertIn("push-gate:", self.output(r))


# ---------------------------------------------------------------------------
# 5. K5 -- every new commit is scanned, not just the net diff. A leak
#    planted in one commit and removed by the next, in the SAME push,
#    still ships to history and must still be caught.
# ---------------------------------------------------------------------------
class MidPushCommitIsScannedTest(PushGateTestBase):
    def test_a_leak_planted_and_removed_within_one_push_is_still_caught(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "fixtures/data.py", "SETTINGS = {\n    %s\n}\n" % CREDENTIAL)
        planted_sha = self.commit_all(work, "plant")
        (work / "fixtures" / "data.py").unlink()
        self.commit_all(work, "remove")

        # The net diff between the pre-push tip and the new tip is clean --
        # proves this is genuinely a per-commit catch, not an artifact of
        # the file still being present.
        net_diff = self._git("diff", "--name-only", "origin/main", "HEAD", cwd=work)
        self.assertEqual(net_diff.returncode, 0, net_diff.stderr)
        self.assertNotIn("fixtures/data.py", net_diff.stdout)

        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=planted_sha, result=r)


# ---------------------------------------------------------------------------
# 5b. A git tree entry can be literally named '..' -- git's own object
#     model has no opinion on path-component semantics, only `git mktree`'s
#     input format (see PushGateTestBase.craft_path_traversal_commit for
#     how this was confirmed reachable through a real `git push`, even with
#     `receive.fsckObjects=true`). `git diff-tree` then reports the PATH
#     field as an innocuous-looking string, e.g. `subdir/../secret.txt` --
#     exactly the shape a materialization step that trusts the path string
#     could write outside its own scan sandbox with.
# ---------------------------------------------------------------------------
class PathTraversalInTheTreeIsRejectedTest(PushGateTestBase):
    def test_a_tree_entry_named_dotdot_is_rejected(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        sha = self.craft_path_traversal_commit(work, dotdot_levels=1)
        self._git("branch", "-f", "evil-branch", sha, cwd=work)
        before = self.remote_state()
        r = self.push(work, refspec="evil-branch")
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)

    def test_a_deeply_nested_traversal_is_rejected_too(self):
        # Not just the single-level shape above: a guard that merely
        # special-cased "exactly one '..' segment" would miss this.
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        sha = self.craft_path_traversal_commit(work, dotdot_levels=6)
        self._git("branch", "-f", "evil-branch", sha, cwd=work)
        before = self.remote_state()
        r = self.push(work, refspec="evil-branch")
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)


# ---------------------------------------------------------------------------
# 6/7. K2 point 5 -- `--require-denylist` reaches artifact-gate.sh. An
#      unconfigured OR an unusable deny list refuses a push even over
#      otherwise-clean content.
# ---------------------------------------------------------------------------
class UnconfiguredDenyListRefusesPushTest(PushGateTestBase):
    def test_clean_content_is_still_refused_without_a_configured_deny_list(self):
        self.write_config()  # gate: {} -- no denyNames key at all
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        sha = self.commit_all(work)
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)


class UnusableDenyListRefusesPushTest(PushGateTestBase):
    def test_a_blank_deny_list_entry_refuses_the_push(self):
        self.write_config(denyNames=["", DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        sha = self.commit_all(work)
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)

    def test_a_deny_list_entry_with_a_line_break_refuses_the_push(self):
        self.write_config(denyNames=["%s\nother" % DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        sha = self.commit_all(work)
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)


# ---------------------------------------------------------------------------
# 8. K3 -- profile by path, not global. The memory profile's content check
#    (TODO markers) fires under memory/, and must NOT fire outside it.
#    Both directions, or this only pins "something blocks somewhere".
# ---------------------------------------------------------------------------
class ProfileByPathTest(PushGateTestBase):
    def test_a_memory_path_content_marker_is_rejected(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "memory/notes.md", TODO_TEXT)
        sha = self.commit_all(work)
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)

    def test_the_same_content_marker_outside_memory_is_accepted(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", TODO_TEXT)
        self.commit_all(work)
        r = self.push(work)
        self.assertEqual(r.returncode, 0, self.output(r))


# ---------------------------------------------------------------------------
# 9. A branch deletion (newrev = 0{40}) is let through without a scan --
#    there is nothing to scan.
# ---------------------------------------------------------------------------
class BranchDeletionIsAllowedTest(PushGateTestBase):
    def test_a_branch_deletion_goes_through_without_a_scan(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        self._git("checkout", "-q", "-b", "feature-x", cwd=work)
        self.write(work, "docs/feature.md", CLEAN_TEXT)
        self.commit_all(work)
        r = self.push(work, refspec="feature-x")
        self.assertEqual(r.returncode, 0, self.output(r))

        r = self.push(work, refspec=":feature-x")
        self.assertEqual(r.returncode, 0, self.output(r))
        refs = self._git("for-each-ref", "--format=%(refname)", cwd=self.remote)
        self.assertEqual(refs.returncode, 0, refs.stderr)
        self.assertNotIn("feature-x", refs.stdout)


# ---------------------------------------------------------------------------
# 10. K6.1 -- a push containing only a binary file used to end in
#     `scanned == 0` inside artifact-gate.sh, a DELIBERATELY accepted false
#     reject (PO decision E3), not a bug to work around.
#
#     CCP-1137R2 note, flagged rather than resolved (see push-gate.sh's own
#     header, "two FORMER accepted false-rejects"): a commit's own message
#     is now an UNCONDITIONAL scan candidate, so `scanned` is no longer 0
#     for this shape once the commit carries any message at all -- the
#     push below is now ACCEPTED where it used to be refused. The binary
#     file's own CONTENT is still never verified; only the message is.
#     Whether that still satisfies "nothing scanned is not a pass" is a
#     decision for the PO, not settled here -- the second test below is
#     the control that keeps proving the message itself is still checked.
# ---------------------------------------------------------------------------
class BinaryOnlyPushTest(PushGateTestBase):
    def test_a_binary_only_push_with_a_clean_commit_message_is_now_accepted(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        self.write_bytes(work, "assets/blob.bin", bytes(range(256)))
        self.commit_all(work)  # default "x" message: clean under both profiles
        r = self.push(work)
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertIn("binary file(s) skipped", self.output(r))

    def test_a_binary_only_push_with_a_dirty_commit_message_is_still_rejected(self):
        # Control: the binary file's content is not what caught this --
        # the message is, same property CommitMessageIsScannedTest already
        # pins, checked again at this specific binary-only shape.
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        self.write_bytes(work, "assets/blob.bin", bytes(range(256)))
        sha = self.commit_all(work, "SETTINGS = {\n    %s\n}\n" % CREDENTIAL)
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)


# ---------------------------------------------------------------------------
# 11. K4 -- an oversized blob is skipped LOUDLY (never silently), and the
#     rest of an otherwise-clean push still succeeds.
# ---------------------------------------------------------------------------
class LargeBlobIsSkippedLoudlyTest(PushGateTestBase):
    def test_an_oversized_blob_is_skipped_loudly_and_the_push_still_succeeds(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook(max_blob_bytes=10)
        work = self.clone_work()
        self.write(work, "docs/small.md", "hi\n")       # 3 bytes, under the cap
        self.write(work, "docs/big.md", CLEAN_TEXT)      # well over the cap
        self.commit_all(work)
        r = self.push(work)
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertIn("skipped", self.output(r).lower())
        self.assertIn("docs/big.md", self.output(r))


# ---------------------------------------------------------------------------
# 12. ADR-0011 -- push-gate.sh itself must survive bash 3.2, macOS's system
#     bash. The specific regression this pins: an unguarded expansion of an
#     EMPTY array under `set -u` aborts on bash 3.2 but not on bash 4+/5.
# ---------------------------------------------------------------------------
class Bash32Test(PushGateTestBase):
    @unittest.skipUnless(
        (_bash_major_minor(SYSTEM_BASH) or (99, 0))[0] < 4,
        "system bash is not 3.x -- the bash-3.2 empty-array regression "
        "cannot be measured here",
    )
    def test_the_system_bash_this_suite_drives_is_the_one_that_broke(self):
        self.assertLess(_bash_major_minor(SYSTEM_BASH)[0], 4)

    def test_a_clean_push_with_no_memory_paths_survives_bash_3_2(self):
        # Forces BOTH the configured memory-path prefix list AND the actual
        # set of memory-matched files in this push to be empty -- the exact
        # shape that crashes under bash 3.2's `set -u` when an empty array
        # is expanded unguarded (`"${arr[@]}"` on a zero-length array).
        self.write_config(denyNames=["Blorptech"])
        self.install_hook(bash_path=SYSTEM_BASH, memory_paths="")
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        self.commit_all(work)
        r = self.push(work)
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertNotIn("unbound variable", self.output(r).lower(), self.output(r))


# ---------------------------------------------------------------------------
# 13. CCP-1137R2 -- a deny name planted ONLY in the ref/branch NAME (clean
#     file content otherwise) never crossed `git diff-tree` and was accepted
#     silently. The refusal itself must not print the name either, the same
#     discipline the content- and path-deny refusals already carry.
# ---------------------------------------------------------------------------
class RefNameDenyIsRejectedTest(PushGateTestBase):
    def test_a_deny_name_in_the_branch_name_is_rejected_with_clean_content(self):
        self.write_config(denyNames=[DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        sha = self.commit_all(work)
        self._git("branch", "-f", "%s-migration-plan" % DENY_NAME, "HEAD", cwd=work)
        before = self.remote_state()
        r = self.push(work, refspec="%s-migration-plan" % DENY_NAME)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)

    def test_the_refusal_does_not_print_the_configured_name(self):
        # Scoped to hook_output(), not output(): git's OWN local porcelain
        # ("! [remote rejected] <local-refspec> -> ...") echoes back the
        # refspec the test itself typed on the push command line -- outside
        # this hook's control, and not the shape of leak a server-side log
        # (what hook_output() isolates) would ever carry.
        self.write_config(denyNames=[DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        sha = self.commit_all(work)
        self._git("branch", "-f", "%s-migration-plan" % DENY_NAME, "HEAD", cwd=work)
        before = self.remote_state()
        r = self.push(work, refspec="%s-migration-plan" % DENY_NAME)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)
        self.assertNotIn(DENY_NAME.lower(), self.hook_output(r).lower(), self.hook_output(r))

    def test_a_clean_branch_name_with_clean_content_is_still_accepted(self):
        # Control: the ref-name check must not fire on an ordinary name.
        self.write_config(denyNames=[DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        self.commit_all(work)
        self._git("branch", "-f", "feature-ordinary", "HEAD", cwd=work)
        r = self.push(work, refspec="feature-ordinary")
        self.assertEqual(r.returncode, 0, self.output(r))


# ---------------------------------------------------------------------------
# 14. CCP-1137R2 -- a leak planted ONLY in a commit's own MESSAGE (clean
#     file content otherwise) never crossed `git diff-tree` and was accepted
#     silently.
# ---------------------------------------------------------------------------
class CommitMessageIsScannedTest(PushGateTestBase):
    def test_a_secret_shape_in_the_commit_message_is_rejected(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        sha = self.commit_all(work, "internal memo for %s\n\n%s" % (DENY_NAME, CREDENTIAL))
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)

    def test_a_deny_name_in_the_commit_message_is_rejected_with_clean_content(self):
        self.write_config(denyNames=[DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        sha = self.commit_all(work, "internal memo for %s migration project" % DENY_NAME)
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)


# ---------------------------------------------------------------------------
# 15. CCP-1137R2 -- an annotated tag's own PAYLOAD (message) never crossed
#     `git diff-tree` and was accepted silently, in both shapes: a tag on a
#     commit this push does NOT introduce (rev-list finds zero new commits,
#     so no sub-gate ran at all) and a tag on a commit this push DOES
#     introduce (the commit's own content was scanned, the tag's own
#     message never was).
# ---------------------------------------------------------------------------
class TagPayloadIsScannedTest(PushGateTestBase):
    def test_a_deny_name_in_a_tag_on_an_already_published_commit_is_rejected(self):
        self.write_config(denyNames=[DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        # No new commit: the tag names a commit main already carries on the
        # remote (the seeded "init" commit) -- rev-list finds nothing new.
        tag = self._git(
            "tag", "-a", "release-note", "-m",
            "notes for the %s migration" % DENY_NAME, "main", cwd=work,
        )
        self.assertEqual(tag.returncode, 0, tag.stderr)
        before = self.remote_state()
        r = self.push(work, refspec="release-note")
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assertEqual(self.remote_state(), before, "the shared repo moved")

    def test_a_deny_name_in_a_tag_on_a_new_commit_in_this_push_is_rejected(self):
        self.write_config(denyNames=[DENY_NAME])
        self.install_hook()
        work = self.clone_work()
        self.write(work, "docs/notes.md", CLEAN_TEXT)
        sha = self.commit_all(work, "add notes")
        tag = self._git(
            "tag", "-a", "release-note", "-m",
            "notes for the %s migration" % DENY_NAME, "HEAD", cwd=work,
        )
        self.assertEqual(tag.returncode, 0, tag.stderr)
        before = self.remote_state()
        r = self._git("push", self.remote, "main", "release-note", cwd=work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha, result=r)

    def test_a_clean_annotated_tag_on_an_already_published_commit_is_accepted(self):
        # Control, and closes the "tag push" shape of the coverage gap: a
        # genuinely clean annotated tag must still go through.
        self.write_config(denyNames=["Blorptech"])
        self.install_hook()
        work = self.clone_work()
        tag = self._git("tag", "-a", "v1", "-m", "first release", "main", cwd=work)
        self.assertEqual(tag.returncode, 0, tag.stderr)
        r = self.push(work, refspec="v1")
        self.assertEqual(r.returncode, 0, self.output(r))
        tags = self._git("tag", cwd=self.remote)
        self.assertIn("v1", tags.stdout.splitlines())


# ---------------------------------------------------------------------------
# 18. PO decision -- above PUSH_GATE_MAX_COMMITS, the push is now refused
#     OUTRIGHT rather than degraded to a tip-only diff. Pins the boundary
#     (`-gt`, not `-ge`) and the exact attack the degrade-instead-of-refuse
#     shape used to miss: a secret planted in commit N and removed in N+1,
#     spanning a range ABOVE the cap.
# ---------------------------------------------------------------------------
class CommitCapExceededRejectsPushTest(PushGateTestBase):
    def test_a_push_exceeding_the_commit_cap_is_rejected_outright(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook(max_commits=1)
        work = self.clone_work()
        self.write(work, "docs/a.md", CLEAN_TEXT)
        sha1 = self.commit_all(work, "a")
        self.write(work, "docs/b.md", CLEAN_TEXT)
        sha2 = self.commit_all(work, "b")
        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=sha2, result=r)
        self.assertFalse(self.object_exists(sha1))

    def test_a_plant_then_remove_shape_above_the_cap_is_rejected_by_the_cap_itself(self):
        self.write_config(denyNames=["Blorptech"])
        self.install_hook(max_commits=1)
        work = self.clone_work()
        self.write(work, "fixtures/data.py", "SETTINGS = {\n    %s\n}\n" % CREDENTIAL)
        planted_sha = self.commit_all(work, "plant")
        (work / "fixtures" / "data.py").unlink()
        self.commit_all(work, "remove")

        net_diff = self._git("diff", "--name-only", "origin/main", "HEAD", cwd=work)
        self.assertEqual(net_diff.returncode, 0, net_diff.stderr)
        self.assertNotIn("fixtures/data.py", net_diff.stdout)

        before = self.remote_state()
        r = self.push(work)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, planted_sha=planted_sha, result=r)

    def test_a_push_at_exactly_the_cap_is_still_scanned_normally(self):
        # Boundary control: the cap is exclusive ("-gt"), so a push carrying
        # EXACTLY the configured number of commits is not refused for that
        # reason.
        self.write_config(denyNames=["Blorptech"])
        self.install_hook(max_commits=2)
        work = self.clone_work()
        self.write(work, "docs/a.md", CLEAN_TEXT)
        self.commit_all(work, "a")
        self.write(work, "docs/b.md", CLEAN_TEXT)
        self.commit_all(work, "b")
        r = self.push(work)
        self.assertEqual(r.returncode, 0, self.output(r))


if __name__ == "__main__":
    unittest.main()
