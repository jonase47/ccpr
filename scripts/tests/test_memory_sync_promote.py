"""Tests for `scripts/memory-sync.sh promote` — the one irreversible path.

Two work items live here because they sit on the same line of the same
function:

* **WI-0014** — `cmd_promote` ran the discipline gate on the source file's
  *content* and then wrote the *destination path* into a commit message that it
  pushed. A file whose content is clean could still carry a configured
  tenant/project name into a shared repository through its own name. That name
  survives deleting the file, is visible to everyone with read access, and
  removing it means rewriting shared history. Everything else the gate protects
  is local; this is the only place where a finding must **refuse**.

* **WI-0012** — the `die` message that validates the destination interpolated
  `${NS,,}`, a bash 4 lowercase expansion. macOS ships `/bin/bash` 3.2.57, which
  answers `bad substitution` — so the usage hint *was* the failure, and the
  wrong exit code came out with it.

**How the push is isolated.** `promote` pushes, so the fixture gives it a
somewhere to push to that is not a network: `repoUrl` points at a **local bare
repository** in a temp directory. `authed_url()` only rewrites `http://` and
`https://` prefixes, so a filesystem path travels through untouched and git
talks to it over the local transport. No remote is contacted, and every
assertion about "nothing was pushed" is made by inspecting that bare repository
directly — never by trusting an exit code.

`HOME` is redirected to a temp directory so the gate resolves the *fixture*
config instead of the developer's personal `~/.claude/memory-sync.json`; a
personal deny-list or IP allowlist would otherwise change what these tests
measure.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_SYNC = REPO_ROOT / "scripts" / "memory-sync.sh"
SCRIPTS_DIR = REPO_ROOT / "scripts"

# The interpreter the shipped scripts must survive. macOS's system bash is
# 3.2.57; a bash-4 construct is only a bug because *this* is what runs it.
SYSTEM_BASH = "/bin/bash"

# A fictional name, never a real tenant. It is what a deny-list entry stands in
# for throughout this suite.
DENY_NAME = "Quuxcorp"

# Clean under the memory profile: no work-item shapes, no personal markers.
MEMORY_CLEAN_TEXT = "# Rule\n\nA durable piece of knowledge.\n"


def _bash_major_minor(path):
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True).stdout
    except OSError:
        return None
    m = re.search(r"version (\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else None


class PromoteTestBase(unittest.TestCase):
    """A promote fixture: redirected HOME, a local bare repo as the 'remote'."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-memory-sync-promote-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.home = self.tmp / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.work = self.tmp / "work"
        self.work.mkdir()

        self.remote = self.tmp / "remote.git"
        self.clone = self.tmp / "clone"
        self.token = self.tmp / "token"
        self.token.write_text("dummy-token\n", encoding="utf-8")

        self._init_remote()

    # --- fixture ---------------------------------------------------------
    def _git(self, *args, cwd=None):
        return subprocess.run(
            ["git", *[str(a) for a in args]],
            cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, env=self.env(),
        )

    def _init_remote(self):
        """A bare repo with one commit on `main` — a plausible shared repo."""
        self._seed_bare_repo(self.remote, seed_name="seed")

    def _seed_bare_repo(self, remote_path, seed_name):
        """Init a bare repo at `remote_path` with one commit on `main`.

        Factored out of `_init_remote` so a test can stand up a SECOND bare
        repo whose path itself is the fixture under test (e.g. a repoUrl that
        carries a configured deny-listed name), without duplicating the
        seed/push/cleanup dance.
        """
        r = self._git("init", "--quiet", "--bare", "--initial-branch=main", remote_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        seed = self.tmp / seed_name
        self.assertEqual(
            self._git("init", "--quiet", "--initial-branch=main", seed).returncode, 0
        )
        (seed / "README.md").write_text("# shared\n", encoding="utf-8")
        self.assertEqual(self._git("add", "README.md", cwd=seed).returncode, 0)
        self.assertEqual(self._git("commit", "--quiet", "-m", "init", cwd=seed).returncode, 0)
        r = self._git("push", "--quiet", remote_path, "main", cwd=seed)
        self.assertEqual(r.returncode, 0, r.stderr)
        shutil.rmtree(seed)
        return remote_path

    def env(self, **extra):
        e = {
            "HOME": str(self.home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            # git refuses to commit without an identity, and HOME is empty here.
            # A reserved domain (RFC 2606) so no real mailbox is written down.
            "GIT_AUTHOR_NAME": "ccpr test",
            "GIT_AUTHOR_EMAIL": "ccpr@example.invalid",
            "GIT_COMMITTER_NAME": "ccpr test",
            "GIT_COMMITTER_EMAIL": "ccpr@example.invalid",
        }
        e.update(extra)
        return e

    def write_config(self, namespace="XX", **gate_keys):
        cfg = {
            "repoUrl": str(self.remote),
            "namespace": namespace,
            "tokenFile": str(self.token),
            "clonePath": str(self.clone),
            "gate": gate_keys,
        }
        (self.home / ".claude" / "memory-sync.json").write_text(
            json.dumps(cfg), encoding="utf-8"
        )

    def write_src(self, name="m.md", text=MEMORY_CLEAN_TEXT):
        p = self.work / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    # --- driving the entry point ----------------------------------------
    def run_sync(self, *args, bash=None, extra_env=None):
        """Run memory-sync.sh as a subprocess. Exit code measured directly."""
        return subprocess.run(
            [bash or "bash", str(MEMORY_SYNC), *[str(a) for a in args]],
            capture_output=True, text=True, env=self.env(**(extra_env or {})),
        )

    def promote(self, src, dst, bash=None):
        return self.run_sync("promote", src, dst, bash=bash)

    # --- inspecting the shared repository --------------------------------
    def remote_state(self):
        """Everything a push would change: every ref and every commit."""
        refs = self._git("for-each-ref", "--format=%(refname) %(objectname)", cwd=self.remote)
        log = self._git("log", "--all", "--format=%H %s", cwd=self.remote)
        self.assertEqual(refs.returncode, 0, refs.stderr)
        self.assertEqual(log.returncode, 0, log.stderr)
        return refs.stdout, log.stdout

    def remote_tree(self, ref="main"):
        # `core.quotepath=false` so a non-ASCII entry appears as itself rather
        # than as octal escapes: these assertions are read when they FAIL, and
        # "what actually got published" has to be legible in that message.
        r = self._git(
            "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", ref, cwd=self.remote
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return sorted(x for x in r.stdout.splitlines() if x)

    def assert_nothing_published(self, before, result=None):
        """The only assertion that counts: the bare repo did not move.

        Checked against the *repository*, never against an exit code — a
        bypass that ends in `exit 0` and a bypass that ends in `exit 2` are
        distinguished by what is in the tree, not by what the script says.
        """
        detail = "" if result is None else "\n" + self.output(result)
        self.assertEqual(
            self.remote_tree(), ["README.md"],
            "something was published: %r%s" % (self.remote_tree(), detail),
        )
        self.assertEqual(self.remote_state(), before, "the shared repo moved" + detail)

    def remote_messages(self):
        r = self._git("log", "--all", "--format=%B", cwd=self.remote)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    @staticmethod
    def output(result):
        return result.stdout + result.stderr


# ---------------------------------------------------------------------------
# 1. WI-0014 — the destination path is checked, and a finding refuses.
# ---------------------------------------------------------------------------
class DestinationDenyListTest(PromoteTestBase):
    def test_a_destination_carrying_a_configured_name_is_refused(self):
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        r = self.promote(src, "instincts/%s-notes.md" % DENY_NAME)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))

    def test_the_refusal_exit_code_is_two(self):
        # 2 is this script's "hard error" code, and the same code its content
        # gate already refuses with. Measured directly, not after a pipe.
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        r = self.promote(src, "instincts/%s-notes.md" % DENY_NAME)
        self.assertEqual(r.returncode, 2, self.output(r))

    def test_the_refusal_message_does_not_contain_the_configured_name(self):
        # A terminal is a smaller audience than a CI log, but the rule should
        # not have an exception the reader has to remember.
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        r = self.promote(src, "instincts/%s-notes.md" % DENY_NAME)
        self.assertNotIn(DENY_NAME.lower(), self.output(r).lower(), self.output(r))

    def test_the_refusal_message_keeps_the_location_usable(self):
        # Redacted, not withheld: the operator has to be able to see WHICH
        # destination was rejected without the name travelling.
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        r = self.promote(src, "instincts/%s-notes.md" % DENY_NAME)
        out = self.output(r)
        self.assertIn("<redacted>", out, out)
        self.assertIn("instincts/", out, out)
        self.assertIn("-notes.md", out, out)

    def test_the_name_is_matched_case_insensitively(self):
        # The content check uses `grep -Fi`; a destination check that only
        # matched exactly would be a hole one keystroke wide.
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        r = self.promote(src, "instincts/%s-notes.md" % DENY_NAME.lower())
        self.assertEqual(r.returncode, 2, self.output(r))

    def test_a_name_in_a_directory_component_is_refused_too(self):
        # The commit message carries only `basename "$dst"`, but the pushed
        # TREE carries every component. A check written against the basename
        # would pass this destination and publish the directory name.
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        r = self.promote(src, "%s/notes.md" % DENY_NAME)
        self.assertEqual(r.returncode, 2, self.output(r))

    def test_an_unconfigured_deny_list_does_not_block_a_promote(self):
        # No list means no names to check — a statement about scope, not a
        # finding. The gate already says so out loud.
        self.write_config(ipAllowlist="")
        src = self.write_src()
        r = self.promote(src, "instincts/xx-org.md")
        self.assertEqual(r.returncode, 0, self.output(r))


# ---------------------------------------------------------------------------
# 2. WI-0014 — the assertion that matters: a refusal changes no git state.
# ---------------------------------------------------------------------------
class RefusalLeavesNoGitStateTest(PromoteTestBase):
    def test_a_refusal_pushes_nothing_to_the_shared_repository(self):
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        before = self.remote_state()
        r = self.promote(src, "instincts/%s-notes.md" % DENY_NAME)
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assertEqual(before, self.remote_state(), "the shared repo moved")

    def test_a_refusal_leaves_the_destination_absent_from_the_shared_tree(self):
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        self.promote(src, "instincts/%s-notes.md" % DENY_NAME)
        self.assertEqual(self.remote_tree(), ["README.md"])

    def test_a_refusal_puts_no_configured_name_into_a_pushed_commit_message(self):
        # The defect in one line: the name reached the commit subject via
        # `memory: promote $(basename "$dst")`, and a commit message cannot be
        # deleted without rewriting shared history.
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        self.promote(src, "instincts/%s-notes.md" % DENY_NAME)
        self.assertNotIn(DENY_NAME.lower(), self.remote_messages().lower())

    def test_a_refusal_stages_and_commits_nothing_in_an_existing_clone(self):
        # A clone left over from an earlier `pull` is the realistic state. The
        # refusal must not leave a staged file or a local commit behind in it,
        # because the next successful promote would carry them along.
        self.write_config(denyNames=[DENY_NAME])
        pull = self.run_sync("pull")
        self.assertEqual(pull.returncode, 0, self.output(pull))
        self.assertTrue((self.clone / ".git").is_dir(), "fixture: no clone to inspect")
        head_before = self._git("rev-parse", "HEAD", cwd=self.clone).stdout.strip()

        src = self.write_src()
        dst = "instincts/%s-notes.md" % DENY_NAME
        r = self.promote(src, dst)
        self.assertEqual(r.returncode, 2, self.output(r))

        status = self._git("status", "--porcelain", cwd=self.clone)
        self.assertEqual(status.stdout, "", "working tree / index dirty:\n" + status.stdout)
        staged = self._git("diff", "--cached", "--name-only", cwd=self.clone)
        self.assertEqual(staged.stdout, "", "something was staged:\n" + staged.stdout)
        head_after = self._git("rev-parse", "HEAD", cwd=self.clone).stdout.strip()
        self.assertEqual(head_before, head_after, "a local commit was made")
        self.assertFalse((self.clone / dst).exists(), "the file was copied into the clone")


# ---------------------------------------------------------------------------
# 3. WI-0014 — the check must not break the path it guards.
# ---------------------------------------------------------------------------
class CleanDestinationStillPromotesTest(PromoteTestBase):
    def test_a_clean_destination_is_pushed_to_the_shared_repository(self):
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        r = self.promote(src, "instincts/xx-org.md")
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertIn("instincts/xx-org.md", self.remote_tree())

    def test_a_clean_destination_reaches_the_commit_message(self):
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        self.promote(src, "instincts/xx-org.md")
        self.assertIn("memory: promote xx-org.md", self.remote_messages())

    def test_the_promoted_content_arrives_intact(self):
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src()
        self.promote(src, "instincts/xx-org.md")
        r = self._git("show", "main:instincts/xx-org.md", cwd=self.remote)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, MEMORY_CLEAN_TEXT)

    def test_a_promote_whose_content_is_dirty_is_still_refused(self):
        # The destination check is added in front of the content gate; the
        # content gate must keep working behind it.
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src(text="# Rule\n\nSee %s for details.\n" % DENY_NAME)
        before = self.remote_state()
        r = self.promote(src, "instincts/xx-org.md")
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assertEqual(before, self.remote_state())


# ---------------------------------------------------------------------------
# 4. WI-0012 — the usage hint must render on the interpreter that runs it.
# ---------------------------------------------------------------------------
class UsageHintOnBash32Test(PromoteTestBase):
    @unittest.skipUnless(
        (_bash_major_minor(SYSTEM_BASH) or (99, 0))[0] < 4,
        "system bash is not 3.x — the bash-4 regression cannot be measured here",
    )
    def test_the_system_bash_this_suite_drives_is_the_one_that_broke(self):
        # Names the instrument: without a 3.x interpreter the tests below prove
        # nothing about the bug they guard.
        self.assertLess(_bash_major_minor(SYSTEM_BASH)[0], 4)

    def test_promote_without_a_destination_renders_the_usage_hint(self):
        self.write_config(namespace="KA")
        src = self.write_src()
        r = self.run_sync("promote", src, bash=SYSTEM_BASH)
        out = self.output(r)
        self.assertNotIn("bad substitution", out.lower(), out)
        self.assertIn("instincts/ka-org.md", out, out)

    def test_the_hint_lowercases_the_configured_namespace(self):
        # `ka-org.md`, not `KA-org.md`: dropping the lowercase step would still
        # print a hint, so the test has to name the transformation.
        self.write_config(namespace="KA")
        src = self.write_src()
        out = self.output(self.run_sync("promote", src, bash=SYSTEM_BASH))
        self.assertNotIn("KA-org.md", out, out)

    def test_promote_without_a_destination_exits_two(self):
        # The failing expansion aborted with 1; this script's hard-error code
        # is 2, and the missing argument is a usage error, not a gate finding.
        self.write_config(namespace="KA")
        src = self.write_src()
        r = self.run_sync("promote", src, bash=SYSTEM_BASH)
        self.assertEqual(r.returncode, 2, self.output(r))

    def test_an_empty_destination_argument_is_refused_the_same_way(self):
        self.write_config(namespace="KA")
        src = self.write_src()
        r = self.run_sync("promote", src, "", bash=SYSTEM_BASH)
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assertIn("instincts/ka-org.md", self.output(r))


# ---------------------------------------------------------------------------
# 5. WI-0012 — the class of construct, not the single occurrence.
# ---------------------------------------------------------------------------
class NoBash4ConstructsInShippedScriptsTest(unittest.TestCase):
    """The bug was one expansion; the risk is the family it belongs to.

    The patterns are assembled from fragments so this file does not match
    itself — the same trick the gate's own fixtures use, and the reason there
    is no suppression comment to abuse.
    """

    # (label, regex) — case expansions, the array builtins, associative arrays,
    # and nameref locals. All bash 4+; all silent until the line is reached.
    PATTERNS = [
        ("case expansion", r"\$\{[A-Za-z_][A-Za-z0-9_]*(\[[^]]*\])?" + "," + ",?" + r"\}"),
        ("case expansion", r"\$\{[A-Za-z_][A-Za-z0-9_]*(\[[^]]*\])?" + r"\^" + r"\^?" + r"\}"),
        ("array builtin", r"\b" + "map" + r"file\b|\b" + "read" + r"array\b"),
        ("associative array", r"\b(declare|typeset)\s+-[A-Za-z]*A\s"),
        ("nameref local", r"\blocal\s+-n\s"),
    ]

    @staticmethod
    def scope():
        """Shell files that run on the USER's machine, so on macOS's bash 3.2.

        `templates/ci/` is deliberately outside: those run on a CI image whose
        interpreter the project chooses, not on a Mac's system bash.
        """
        files = list(SCRIPTS_DIR.rglob("*.sh"))
        installer = REPO_ROOT / "install.sh"
        if installer.is_file():
            files.append(installer)
        return sorted(files)

    def test_no_shipped_shell_script_uses_a_bash_4_only_construct(self):
        offenders = []
        for path in self.scope():
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for label, pattern in self.PATTERNS:
                    if re.search(pattern, line):
                        rel = path.relative_to(REPO_ROOT)
                        offenders.append("%s:%d: %s" % (rel, lineno, label))
        self.assertEqual(offenders, [], "bash-4-only constructs:\n" + "\n".join(offenders))

    def test_the_scan_has_a_non_empty_scope(self):
        # A scan that reports nothing because it looked at nothing is not a
        # pass. Assert the scope before believing the zero above.
        scope = self.scope()
        self.assertGreaterEqual(len(scope), 10)
        self.assertIn("install.sh", [p.name for p in scope])
        self.assertIn("memory-sync.sh", [p.name for p in scope])

    def test_the_scan_detects_a_bash_4_construct_when_one_is_present(self):
        # The mutation runs against the matcher itself: without this, the two
        # tests above pass equally well with a regex that matches nothing.
        sample = "  echo " + "\"${" + "NS" + ",," + "}-org.md\""
        self.assertTrue(
            any(re.search(p, sample) for _, p in self.PATTERNS),
            "the scan would not have seen the original defect",
        )


# ---------------------------------------------------------------------------
# 6. WI-0014 round 2 — B1: the checked string and the shipped string.
#
# The destination check reads the string the operator TYPES. What ships is the
# string `cp` PRODUCES, and those two differ whenever the destination names a
# directory: `cp <src> <dir>` appends `basename "$src"`. So a source file named
# after a tenant, with faultlessly clean content, reached the shared tree under
# its own name without any check ever looking at that name.
#
# The fix is not another matcher. A directory was never a supported
# destination — the tool's own header says "copy it into the clone at repo-
# relative destination", CLAUDE.md calls the argument `<repo-path>` — so a
# destination that names a directory is refused as a usage error, and with a
# file destination the checked string and the shipped string are one string.
# ---------------------------------------------------------------------------
class DirectoryDestinationTest(PromoteTestBase):
    def deny_named_source(self):
        """Clean content, deny-listed name. The content gate has nothing to say."""
        return self.write_src(name="%s-notes.md" % DENY_NAME)

    def test_a_dot_destination_does_not_publish_the_source_basename(self):
        # The reproduction, verbatim: `promote <src>/Quuxcorp-notes.md .`
        # exited 0 and put `Quuxcorp-notes.md` in the shared tree.
        self.write_config(denyNames=[DENY_NAME])
        src = self.deny_named_source()
        before = self.remote_state()
        r = self.promote(src, ".")
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, r)

    def test_a_parent_destination_neither_publishes_nor_escapes_the_clone(self):
        # `cp <src> $CLONE/..` writes OUTSIDE the clone entirely — the one
        # shape where the tool touches a path it does not own.
        self.write_config(denyNames=[DENY_NAME])
        src = self.deny_named_source()
        before = self.remote_state()
        r = self.promote(src, "..")
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, r)
        self.assertFalse(
            (self.clone.parent / src.name).exists(),
            "the source was written next to the clone",
        )

    def test_a_trailing_slash_destination_is_refused(self):
        self.write_config(denyNames=[DENY_NAME])
        src = self.deny_named_source()
        before = self.remote_state()
        r = self.promote(src, "instincts/")
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assert_nothing_published(before, r)

    def test_a_dot_component_destination_is_refused(self):
        # `instincts/.` is a directory the moment `instincts/` exists, and
        # `mkdir -p` makes it exist on the way.
        self.write_config(denyNames=[DENY_NAME])
        src = self.deny_named_source()
        before = self.remote_state()
        r = self.promote(src, "instincts/.")
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assert_nothing_published(before, r)

    def test_a_destination_naming_an_existing_directory_is_refused(self):
        # The shape that no amount of string inspection catches: `instincts`
        # is a perfectly ordinary file path until the clone contains a
        # directory of that name. Established here by promoting a clean file
        # first, which is exactly how the directory gets there in real use.
        self.write_config(denyNames=[DENY_NAME])
        first = self.promote(self.write_src(), "instincts/xx-org.md")
        self.assertEqual(first.returncode, 0, self.output(first))
        before = self.remote_state()

        src = self.deny_named_source()
        r = self.promote(src, "instincts")
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assertNotIn(
            "instincts/%s" % src.name, self.remote_tree(),
            "the source basename was published under the directory",
        )
        self.assertEqual(self.remote_state(), before, "the shared repo moved")

    def test_a_directory_shaped_destination_is_refused_before_anything_is_cloned(self):
        # The shapes that can be decided from the string alone are decided
        # there: no clone, no fetch, no token read. Without that, the refusal
        # still happens (the clone would show the directory) but only after
        # the tool has gone and fetched a repository for a request it was
        # always going to reject.
        self.write_config(denyNames=[DENY_NAME])
        src = self.deny_named_source()
        for dst in (".", "..", "instincts/", "instincts/."):
            with self.subTest(dst=dst):
                shutil.rmtree(self.clone, ignore_errors=True)
                r = self.promote(src, dst)
                self.assertEqual(r.returncode, 2, self.output(r))
                self.assertFalse(
                    self.clone.exists(), "a clone was created for %r" % dst
                )

    def test_a_directory_shaped_destination_is_refused_without_reading_the_token(self):
        # Same property from the other side, and the one that costs something
        # in real use: a missing token would otherwise be the error the
        # operator sees, hiding the actual mistake.
        self.write_config(denyNames=[DENY_NAME])
        self.token.unlink()
        r = self.promote(self.deny_named_source(), "instincts/")
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assertIn("file path", self.output(r).lower(), self.output(r))
        self.assertNotIn("token file", self.output(r).lower(), self.output(r))

    def test_a_directory_that_exists_only_in_the_shared_repo_is_refused(self):
        # The string says nothing here and the local machine says nothing
        # either: `instincts` is a directory in the SHARED repo, and this
        # machine has no clone yet. Removing the clone is what a first run on
        # a second machine looks like — and it is the only state in which the
        # post-clone check is the one doing the work.
        self.write_config(denyNames=[DENY_NAME])
        first = self.promote(self.write_src(), "instincts/xx-org.md")
        self.assertEqual(first.returncode, 0, self.output(first))
        shutil.rmtree(self.clone)
        before = self.remote_state()

        src = self.deny_named_source()
        r = self.promote(src, "instincts")
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assertNotIn(
            "instincts/%s" % src.name, self.remote_tree(),
            "the source basename was published under the directory",
        )
        self.assertEqual(self.remote_state(), before, "the shared repo moved")

    def test_the_refusal_says_the_destination_must_be_a_file_path(self):
        # A usage error has to teach the usage, or the operator retries the
        # same shape with a different name.
        self.write_config(denyNames=[DENY_NAME])
        r = self.promote(self.write_src(), "instincts/")
        self.assertIn("file path", self.output(r).lower(), self.output(r))

    def test_a_directory_destination_carrying_a_configured_name_is_redacted(self):
        # The usage error prints the destination, and the destination can be
        # the very thing that must not travel. The rule "a configured name
        # never reaches an output" has no exception for usage errors.
        self.write_config(denyNames=[DENY_NAME])
        r = self.promote(self.write_src(), "%s/" % DENY_NAME)
        out = self.output(r)
        self.assertEqual(r.returncode, 2, out)
        self.assertNotIn(DENY_NAME.lower(), out.lower(), out)
        self.assertIn("<redacted>", out, out)

    def test_a_file_destination_below_a_new_directory_still_promotes(self):
        # The guard must not cost the supported case: a repo-relative FILE
        # path whose parent directory does not exist yet.
        self.write_config(denyNames=[DENY_NAME])
        r = self.promote(self.write_src(), "instincts/nested/xx-org.md")
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertIn("instincts/nested/xx-org.md", self.remote_tree())


# ---------------------------------------------------------------------------
# 7. WI-0014 round 2 — B2/B3: folding and normalisation of the deny check.
#
# `grep -Fi` under `LC_ALL=C` folds ASCII and nothing else, so an upper-cased
# non-ASCII destination walked past a configured name. And macOS hands out
# decomposed (NFD) file names while the tree carries the composed (NFC) one, so
# the two spellings of one name must compare equal — the project's own G-117.
# ---------------------------------------------------------------------------
class NonAsciiDenyNameTest(PromoteTestBase):
    # Fictional, and non-ASCII on purpose. NFC is the composed spelling.
    NAME = "Quüxcorp"

    @staticmethod
    def nfd(s):
        import unicodedata
        return unicodedata.normalize("NFD", s)

    @staticmethod
    def nfc(s):
        import unicodedata
        return unicodedata.normalize("NFC", s)

    def test_an_upper_cased_non_ascii_destination_is_refused(self):
        self.write_config(denyNames=[self.NAME])
        before = self.remote_state()
        r = self.promote(self.write_src(), "instincts/%s-notes.md" % self.NAME.upper())
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, r)

    def test_the_refusal_does_not_print_the_non_ascii_name(self):
        # The matcher and the mask must agree. A matcher that folds more than
        # the mask does turns every catch into a disclosure.
        self.write_config(denyNames=[self.NAME])
        r = self.promote(self.write_src(), "instincts/%s-notes.md" % self.NAME.upper())
        out = self.output(r)
        for spelling in (self.NAME, self.NAME.upper(), self.nfd(self.NAME),
                         self.nfd(self.NAME).upper()):
            self.assertNotIn(spelling.lower(), out.lower(), out)
        self.assertIn("<redacted>", out, out)

    def test_an_exact_non_ascii_destination_is_still_refused(self):
        # The baseline of the two above: same spelling, same case. `grep -Fi`
        # already catches this one, so it separates "folding is broken" from
        # "non-ASCII is broken".
        self.write_config(denyNames=[self.NAME])
        before = self.remote_state()
        r = self.promote(self.write_src(), "instincts/%s-notes.md" % self.NAME)
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, r)

    def test_a_decomposed_destination_matches_a_composed_deny_entry(self):
        self.write_config(denyNames=[self.nfc(self.NAME)])
        before = self.remote_state()
        r = self.promote(self.write_src(), self.nfd("instincts/%s-notes.md" % self.NAME))
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, r)

    def test_a_composed_destination_matches_a_decomposed_deny_entry(self):
        # Both sides are normalised, not just the one the operator typed.
        self.write_config(denyNames=[self.nfd(self.NAME)])
        before = self.remote_state()
        r = self.promote(self.write_src(), self.nfc("instincts/%s-notes.md" % self.NAME))
        self.assertNotEqual(r.returncode, 0, "expected a refusal:\n" + self.output(r))
        self.assert_nothing_published(before, r)

    def test_an_unrelated_non_ascii_destination_still_promotes(self):
        # Folding wider must not mean matching wider: a diacritic is not a
        # wildcard, and `Grün` is not `Quüxcorp`.
        self.write_config(denyNames=[self.NAME])
        r = self.promote(self.write_src(), "instincts/grün-org.md")
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertIn("instincts/grün-org.md", [self.nfc(x) for x in self.remote_tree()])


# ---------------------------------------------------------------------------
# 8. WI-0014 round 2 — B4: a destination is a path, never an option.
#
# `git add "$dst"` without `--` reads a leading dash as an option. `--all`
# stages the whole clone into the irreversible push; `-n` stages nothing and
# the run reports success over an empty promote.
# ---------------------------------------------------------------------------
class OptionShapedDestinationTest(PromoteTestBase):
    def stray_file_in_clone(self, name="scratch-notes.md"):
        """An unrelated file in the clone — leftovers are the normal state."""
        pull = self.run_sync("pull")
        self.assertEqual(pull.returncode, 0, self.output(pull))
        self.assertTrue((self.clone / ".git").is_dir(), "fixture: no clone")
        (self.clone / name).write_text("scratch\n", encoding="utf-8")
        return name

    def test_an_option_shaped_destination_does_not_sweep_the_clone_into_the_push(self):
        self.write_config(denyNames=[DENY_NAME])
        stray = self.stray_file_in_clone()
        self.promote(self.write_src(), "--all")
        self.assertNotIn(
            stray, self.remote_tree(),
            "an unrelated file in the clone was published: %r" % (self.remote_tree(),),
        )

    def test_a_dry_run_shaped_destination_does_not_report_success_over_nothing(self):
        # `-n` made `git add` a dry run: nothing staged, "no change to
        # promote", exit 0 — a success report for a promote that never
        # happened. Read as a path it is an odd but honest file name, and the
        # rule this suite exists for holds: what was checked is what ships.
        self.write_config(denyNames=[DENY_NAME])
        r = self.promote(self.write_src(), "-n")
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertIn("-n", self.remote_tree(), self.output(r))


# ---------------------------------------------------------------------------
# 9. WI-0014 round 2 — the mutation survivor: an unusable deny-list refuses.
#
# `require_usable_deny_list` was called on this path but nothing measured it.
# An entry the newline-delimited transport cannot carry silently shortens the
# effective list, so the run would check fewer names than the operator
# configured and push anyway — on the one path where a push cannot be undone.
# ---------------------------------------------------------------------------
class UnusableDenyListRefusesPromoteTest(PromoteTestBase):
    def test_a_blank_deny_list_entry_refuses_the_promote(self):
        self.write_config(denyNames=["", DENY_NAME])
        before = self.remote_state()
        r = self.promote(self.write_src(), "instincts/xx-org.md")
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assert_nothing_published(before, r)

    def test_a_deny_list_entry_with_a_line_break_refuses_the_promote(self):
        self.write_config(denyNames=["%s\nother" % DENY_NAME])
        before = self.remote_state()
        r = self.promote(self.write_src(), "instincts/xx-org.md")
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assert_nothing_published(before, r)

    def test_the_refusal_happens_before_any_scan_is_run(self):
        # `run_gate` refuses on an unusable list too, so "promote exits 2" is
        # satisfied without the guard in front of the DESTINATION check —
        # measured by removing that call and watching the four tests above
        # stay green. What the early call buys is that no verdict is ever
        # produced from a shortened list: with it, the run refuses before it
        # so much as announces the scan.
        self.write_config(denyNames=["", DENY_NAME])
        r = self.promote(self.write_src(), "instincts/xx-org.md")
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assertNotIn("Running discipline gate", self.output(r), self.output(r))

    def test_the_refusal_locates_the_entry_by_position_without_naming_it(self):
        self.write_config(denyNames=[DENY_NAME, ""])
        out = self.output(self.promote(self.write_src(), "instincts/xx-org.md"))
        self.assertIn("#2", out, out)
        self.assertNotIn(DENY_NAME.lower(), out.lower(), out)

    def test_a_usable_deny_list_of_the_same_shape_still_promotes(self):
        # Separates "refuses on an unusable entry" from "refuses on any list".
        self.write_config(denyNames=[DENY_NAME, "Blorptech"])
        r = self.promote(self.write_src(), "instincts/xx-org.md")
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertIn("instincts/xx-org.md", self.remote_tree())


# ---------------------------------------------------------------------------
# 10. WI-0016 — every line this tool emits goes through the same mask
# `promote`'s destination check already applies to itself.
#
# `artifact-gate.sh` routes every emitted line through `gate_redact_path` (see
# its `say()`/`warn()`/`die()`). `memory-sync.sh`'s `die()`/`note()` were a
# bare `echo` — the same tool that REFUSES a destination for carrying a
# configured name PRINTED that identical class of name everywhere else it
# appears: the repoUrl on `pull`/`status`, a missing file's own path on
# `gate`, the config path in an unusable-deny-list error, a promoted source's
# own path in the progress line.
# ---------------------------------------------------------------------------
class EmittedOutputMaskingTest(PromoteTestBase):
    def deny_named_remote_config(self):
        """A repoUrl that itself carries the configured deny-listed name.

        A REAL, clonable bare repo — not just a string — so `git clone`/
        `fetch` succeed and nothing about the assertions below is muddied by
        git's own (unmasked) error output on a failed transport.
        """
        remote = self._seed_bare_repo(
            self.tmp / ("%s-shared.git" % DENY_NAME), seed_name="deny-seed"
        )
        cfg = {
            "repoUrl": str(remote),
            "namespace": "XX",
            "tokenFile": str(self.token),
            "clonePath": str(self.clone),
            "gate": {"denyNames": [DENY_NAME]},
        }
        (self.home / ".claude" / "memory-sync.json").write_text(
            json.dumps(cfg), encoding="utf-8"
        )
        return remote

    def test_status_does_not_print_a_configured_name_from_the_repo_url(self):
        self.deny_named_remote_config()
        r = self.run_sync("status")
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertNotIn(DENY_NAME.lower(), self.output(r).lower(), self.output(r))

    def test_pull_does_not_print_a_configured_name_from_the_repo_url(self):
        self.deny_named_remote_config()
        r = self.run_sync("pull")
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertNotIn(DENY_NAME.lower(), self.output(r).lower(), self.output(r))

    def test_pull_reports_progress_with_the_name_redacted_not_silenced(self):
        # Masking, not silence -- the same shape `promote`'s destination
        # refusal already uses.
        self.deny_named_remote_config()
        out = self.output(self.run_sync("pull"))
        self.assertIn("<redacted>", out, out)

    def test_a_second_pull_against_an_existing_clone_is_masked_too(self):
        # `ensure_clone`'s `fetch` branch (a clone already present) is a
        # SEPARATE code path from the first `git clone` -- both print the
        # repo URL.
        self.deny_named_remote_config()
        first = self.run_sync("pull")
        self.assertEqual(first.returncode, 0, self.output(first))
        r = self.run_sync("pull")
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertNotIn(DENY_NAME.lower(), self.output(r).lower(), self.output(r))

    def test_a_missing_gate_target_carrying_a_configured_name_is_masked(self):
        self.write_config(denyNames=[DENY_NAME])
        missing = self.work / ("%s-notes.md" % DENY_NAME)  # never written
        r = self.run_sync("gate", missing)
        # The `gate` dispatch collapses run_gate's own 1 (findings) and 2
        # (usage/setup defect) into a flat exit 1 -- a pre-existing shape of
        # `case ... && note ... || { note ...; exit 1; }`, unrelated to the
        # masking this test measures.
        self.assertEqual(r.returncode, 1, self.output(r))
        self.assertNotIn(DENY_NAME.lower(), self.output(r).lower(), self.output(r))
        self.assertIn("<redacted>", self.output(r), self.output(r))

    def test_the_promote_progress_message_masks_a_configured_name_in_the_source_path(self):
        # The DESTINATION is clean here -- only the SOURCE path carries the
        # name, so the destination-deny check has nothing to refuse and the
        # progress line ("Running discipline gate on $src ...") is reached.
        self.write_config(denyNames=[DENY_NAME])
        src = self.write_src(name="%s-local-notes.md" % DENY_NAME)
        r = self.promote(src, "instincts/xx-org.md")
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertNotIn(DENY_NAME.lower(), self.output(r).lower(), self.output(r))
        self.assertIn("<redacted>", self.output(r), self.output(r))


# ---------------------------------------------------------------------------
# 11. WI-0016 — a second, separate leak class: the operator's OS username via
# $HOME. A deny-list entry never covers it (it is not a configured tenant/
# project name), so it needs its own guard and its own test -- the existing
# idiom for it already lives in this file, at `ensure_memory_pointer`
# (`${MEM_NS_DIR/#$HOME/~}`).
# ---------------------------------------------------------------------------
class HomeDirectoryMaskingTest(PromoteTestBase):
    def test_status_does_not_print_the_home_directory_path(self):
        self.write_config(denyNames=[DENY_NAME])
        r = self.run_sync("status")
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertNotIn(str(self.home), self.output(r), self.output(r))

    def test_status_shortens_the_config_path_to_a_tilde(self):
        self.write_config(denyNames=[DENY_NAME])
        out = self.output(self.run_sync("status"))
        self.assertIn("~/.claude/memory-sync.json", out, out)

    def test_a_missing_config_error_does_not_print_the_home_directory_path(self):
        # No config written at all: the deny-list is empty (nothing configured
        # yet), so this measures the $HOME guard in isolation from the
        # deny-list mask above it.
        r = self.run_sync("status")
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assertNotIn(str(self.home), self.output(r), self.output(r))
        self.assertIn("~/.claude/memory-sync.json", self.output(r), self.output(r))

    def test_the_deny_list_not_configured_note_does_not_print_the_home_path(self):
        self.write_config(ipAllowlist="")  # no denyNames key at all
        src = self.write_src()
        r = self.run_sync("gate", src)
        self.assertEqual(r.returncode, 0, self.output(r))
        self.assertIn("deny-list NOT CONFIGURED", self.output(r), self.output(r))
        self.assertNotIn(str(self.home), self.output(r), self.output(r))

    def test_an_unusable_deny_list_entry_error_does_not_print_the_home_path(self):
        self.write_config(denyNames=["", DENY_NAME])
        src = self.write_src()
        r = self.run_sync("gate", src)
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assertNotIn(str(self.home), self.output(r), self.output(r))


# ---------------------------------------------------------------------------
# 12. WI-0016 — a config path itself carrying a configured deny-listed name,
# on the one path where the config file that would have supplied the
# deny-list is the very thing that is missing. The list has to come from the
# environment instead -- CCPR_GATE_DENY_NAMES, which `gate_load_config` reads
# before it ever looks at the (absent) config file.
# ---------------------------------------------------------------------------
class MissingConfigPathMaskingTest(PromoteTestBase):
    def test_a_missing_config_path_carrying_a_configured_name_is_masked(self):
        cfg_path = self.home / ".claude" / ("%s-memory-sync.json" % DENY_NAME)
        r = self.run_sync(
            "status",
            extra_env={
                "MEMORY_SYNC_CONFIG": str(cfg_path),
                "CCPR_GATE_DENY_NAMES": DENY_NAME,
            },
        )
        self.assertEqual(r.returncode, 2, self.output(r))
        self.assertNotIn(DENY_NAME.lower(), self.output(r).lower(), self.output(r))
        self.assertIn("<redacted>", self.output(r), self.output(r))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
