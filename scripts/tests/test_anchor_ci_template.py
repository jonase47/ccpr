"""test_anchor_ci_template.py -- coverage for templates/ci/anchor-check.ci.sh.

Ground-up test module for a dormant CI template that shipped with zero
coverage: the two generic inventories (test_shell_script_syntax.py,
test_external_tool_exit_status.py) both explicitly exclude `templates/ci/*`
(it is a copy-and-adapt artifact, not a "shipped, always-identical" script),
and its sibling template `artifact-gate.ci.sh` has a dedicated suite
(CiTemplateExecutionTest in test_artifact_gate.py) that this module's shape
is deliberately parallel to.

Unlike artifact-gate.ci.sh, this template is never correct pointed only at
$REPO_ROOT/scripts/anchor.sh: that resolution is right for CCPR's OWN repo
(where the script genuinely lives in the tree) but wrong for the template's
actual audience, USER projects, where CCPR is normally installed under
`~/.claude/` via `install.sh` and nothing is vendored. This suite's first
job is therefore the three-way resolution order the fix introduces
($ANCHOR_SH, vendored, installed), not just a syntax and pass/fail check.

House pattern borrowed from test_anchor.py and test_artifact_gate.py: invoke
the real, shipped template as a subprocess (`sh`, since it is POSIX shell,
not bash) against a throwaway git fixture built the same way test_anchor.py
builds one (init, seed a production path, anchor it, drift it). $HOME is
always sandboxed to an empty throwaway directory so a real developer
machine's own ~/.claude/scripts/anchor.sh can never leak into a "not found"
assertion.

Each check below was seen red at least once during authoring, via a
targeted mutation of the shipped template (resolution-order swap,
REQUIRE_ANCHOR_COVERAGE branch inversion, exit-2-to-exit-0 swap -- never a
feature removed from the test itself), then restored to its exact original
text (md5-verified). The mutation-to-test mapping is reported in the
session summary, not encoded here.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ANCHOR_SOURCE = REPO_ROOT / "scripts" / "anchor.sh"
FRONTMATTER_SOURCE = REPO_ROOT / "scripts" / "lib" / "frontmatter.sh"
CI_TEMPLATE = REPO_ROOT / "templates" / "ci" / "anchor-check.ci.sh"

VALID_DATE = "18.08.2026"


def frontmatter_block(phase="P3", subskill="arch-index", status="living",
                       last_updated=VALID_DATE, extra_lines=()):
    lines = [f"phase: {phase}", f"subskill: {subskill}", f"status: {status}",
              f"last_updated: {last_updated}"]
    lines.extend(extra_lines)
    return "---\n" + "\n".join(lines) + "\n---\n"


def doc_text(body="\n# Doc\n\nBody.\n", **fm_kwargs):
    return frontmatter_block(**fm_kwargs) + body


class AnchorCiTemplateTestBase(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="ccpr-anchor-ci-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

        # An empty HOME with no ~/.claude at all: the sandbox for every run,
        # so a real developer machine's own installation can never leak in
        # and mask a "not found" assertion.
        self.empty_home = self.work / "empty-home"
        self.empty_home.mkdir()

        self.git_env = {
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@host.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@host.invalid",
        }

    # -- fixture construction ---------------------------------------------

    def make_repo(self, name="repo"):
        repo = self.work / name
        (repo / "docs").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True,
                        env=self.env())
        return repo

    def write(self, repo, rel_path, text):
        path = repo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit(self, repo, message="commit"):
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True,
                        env=self.env(**self.git_env))
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo,
                        check=True, env=self.env(**self.git_env))
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
            capture_output=True, text=True, env=self.env(**self.git_env),
        ).stdout.strip()

    def vendor_into(self, repo):
        """Copy the real scripts/anchor.sh (+ its frontmatter.sh dependency)
        into <repo>/scripts/, at the same relative layout anchor.sh expects
        of its own SCRIPT_DIR -- mirrors how CiTemplateExecutionTest vendors
        artifact-gate.sh into its own fixtures."""
        target = repo / "scripts"
        (target / "lib").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ANCHOR_SOURCE, target / "anchor.sh")
        (target / "anchor.sh").chmod(0o755)
        shutil.copy2(FRONTMATTER_SOURCE, target / "lib" / "frontmatter.sh")

    def install_into_home(self, home):
        """Same copy, staged under <home>/.claude/scripts/ -- the shape a
        real `install.sh` run produces."""
        target = home / ".claude" / "scripts"
        (target / "lib").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ANCHOR_SOURCE, target / "anchor.sh")
        (target / "anchor.sh").chmod(0o755)
        shutil.copy2(FRONTMATTER_SOURCE, target / "lib" / "frontmatter.sh")

    def anchored_and_drifted_repo(self, name="repo"):
        """Same recipe as test_anchor.py's CheckDeltaReportTest fixture: a
        seeded production path, anchored at its own commit, then genuinely
        changed -- so `check` has real, non-empty delta to report."""
        repo = self.make_repo(name)
        (repo / "src").mkdir()
        self.write(repo, "src/a.go", "package a\n")
        self.commit(repo, "seed code")
        anchor_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
            capture_output=True, text=True, env=self.env(**self.git_env),
        ).stdout.strip()
        self.write(repo, "docs/architecture/ARCHITECTURE.md", doc_text(
            extra_lines=[f"anchor_commit: {anchor_sha}", "anchor_date: " + VALID_DATE],
        ))
        self.write(repo, "docs/architecture/AUTH.md", doc_text(
            subskill="auth", status="active", extra_lines=["covers:", "  - src/"],
        ))
        self.commit(repo, "anchor + auth doc")
        self.write(repo, "src/a.go", "package a\n\nfunc B() {}\n")
        self.commit(repo, "change code")
        return repo

    # -- invocation ---------------------------------------------------------

    def env(self, home=None, **extra):
        e = {"HOME": str(home or self.empty_home),
             "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
        e.update(extra)
        return e

    def run_template(self, repo_root, home=None, **extra_env):
        return subprocess.run(
            ["sh", str(CI_TEMPLATE)],
            capture_output=True, text=True,
            env=self.env(home=home, REPO_ROOT=str(repo_root), **extra_env),
        )


# ---------------------------------------------------------------------------
# 1. The cheap floor: it must at least parse -- as POSIX sh, not just bash.
# ---------------------------------------------------------------------------
class SyntaxTest(unittest.TestCase):
    def test_the_template_is_syntactically_valid_posix_sh(self):
        r = subprocess.run(["sh", "-n", str(CI_TEMPLATE)],
                            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 2. Resolution order: $ANCHOR_SH, then vendored, then installed -- and the
#    case where none of the three resolves.
# ---------------------------------------------------------------------------
class ResolutionOrderTest(AnchorCiTemplateTestBase):
    def test_vendored_repo_local_anchor_sh_is_used_when_present(self):
        repo = self.anchored_and_drifted_repo()
        self.vendor_into(repo)

        r = self.run_template(repo)

        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Anchor Check Report", r.stdout)

    def test_installed_home_claude_anchor_sh_is_used_when_no_vendored_copy(self):
        repo = self.anchored_and_drifted_repo()
        installed_home = self.work / "installed-home"
        installed_home.mkdir()
        self.install_into_home(installed_home)

        r = self.run_template(repo, home=installed_home)

        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Anchor Check Report", r.stdout)

    def test_anchor_sh_env_var_takes_precedence_over_a_vendored_copy(self):
        """A poisoned vendored copy at the repo-local path must never run
        when $ANCHOR_SH points at the real script -- precedence (a) before
        (b), not just (b) working when (a) is absent."""
        repo = self.anchored_and_drifted_repo()
        poison = repo / "scripts" / "anchor.sh"
        poison.parent.mkdir(parents=True, exist_ok=True)
        poison.write_text(
            "#!/usr/bin/env sh\necho 'POISON-VENDORED-SHOULD-NOT-RUN'\nexit 0\n",
            encoding="utf-8",
        )
        poison.chmod(0o755)

        elsewhere = self.work / "elsewhere"
        elsewhere.mkdir()
        real_anchor = elsewhere / "anchor.sh"
        (elsewhere / "lib").mkdir()
        shutil.copy2(ANCHOR_SOURCE, real_anchor)
        real_anchor.chmod(0o755)
        shutil.copy2(FRONTMATTER_SOURCE, elsewhere / "lib" / "frontmatter.sh")

        r = self.run_template(repo, ANCHOR_SH=str(real_anchor))

        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("POISON-VENDORED-SHOULD-NOT-RUN", r.stdout + r.stderr)
        self.assertIn("Anchor Check Report", r.stdout)

    def test_no_resolution_path_exits_2_naming_all_three_locations(self):
        repo = self.make_repo()  # no vendored copy, empty HOME, no ANCHOR_SH

        r = self.run_template(repo)

        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        out = r.stdout + r.stderr
        self.assertIn("ANCHOR_SH", out)
        self.assertIn(str(repo / "scripts" / "anchor.sh"), out)
        self.assertIn(".claude/scripts/anchor.sh", out)


# ---------------------------------------------------------------------------
# 3. Content: does the resolved script's report actually reach the wrapper's
#    exit code, in both directions (drift found, zero coverage)?
# ---------------------------------------------------------------------------
class ContentTest(AnchorCiTemplateTestBase):
    def test_a_drift_run_exits_0_with_delta_lines(self):
        repo = self.anchored_and_drifted_repo()
        self.vendor_into(repo)

        r = self.run_template(repo)

        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("src/a.go", r.stdout)
        self.assertIn("claimed by docs/architecture/AUTH.md", r.stdout)
        # Both ARCHITECTURE.md (own anchor_commit) and AUTH.md (inherits it
        # from the index) resolve to the same anchor -- two anchored
        # documents in one scope, not one.
        self.assertIn("2 anchored", r.stdout)

    def test_zero_coverage_run_exits_0_by_default_with_a_loud_warning(self):
        repo = self.make_repo()
        self.vendor_into(repo)
        self.commit(repo, "docs scaffold only")

        r = self.run_template(repo)

        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = r.stdout + r.stderr
        self.assertIn("0 anchored", out)
        self.assertIn("no scope in this project has ever been anchored", out)

    def test_zero_coverage_run_exits_1_with_require_anchor_coverage(self):
        repo = self.make_repo()
        self.vendor_into(repo)
        self.commit(repo, "docs scaffold only")

        r = self.run_template(repo, REQUIRE_ANCHOR_COVERAGE="1")

        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("failing the build on zero coverage",
                       r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 4. Operational failure: distinguishable from a content finding, not just
#    a nonzero exit code.
# ---------------------------------------------------------------------------
class OperationalFailureTest(AnchorCiTemplateTestBase):
    def test_a_non_git_directory_exits_2_distinct_from_a_drift_finding(self):
        not_a_repo = self.work / "not-a-repo"
        not_a_repo.mkdir()
        (not_a_repo / "scripts" / "lib").mkdir(parents=True)
        shutil.copy2(ANCHOR_SOURCE, not_a_repo / "scripts" / "anchor.sh")
        (not_a_repo / "scripts" / "anchor.sh").chmod(0o755)
        shutil.copy2(FRONTMATTER_SOURCE,
                      not_a_repo / "scripts" / "lib" / "frontmatter.sh")
        # deliberately no `git init` -- anchor.sh's own require_git_repo must
        # be the thing that fails, not this template's own resolution step.

        r = self.run_template(not_a_repo)

        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 2, out)
        self.assertIn("OPERATIONAL failure", out)
        self.assertIn("not a git repository", out)
        # No Stage-1 report was ever rendered -- the marker a drift finding
        # always carries -- so the two failure shapes cannot be confused by
        # exit code alone.
        self.assertNotIn("**Anchors:**", out)


# ---------------------------------------------------------------------------
# 5. Constitution: the template names no hosted forge or CI provider -- a
#    property that must not quietly regress on a comment rewording, so this
#    scans the whole file's content rather than pinning exact wording.
# ---------------------------------------------------------------------------
class NoHostedForgeTest(unittest.TestCase):
    FORBIDDEN_NAMES = (
        "github", "gitlab", "gitea", "forgejo", "bitbucket", "codeberg",
        "azure devops", "circleci", "travis", "jenkins",
    )

    def test_template_names_no_hosted_forge_or_ci_provider(self):
        text = CI_TEMPLATE.read_text(encoding="utf-8").lower()
        found = [name for name in self.FORBIDDEN_NAMES if name in text]
        self.assertEqual(found, [], f"template names a hosted service: {found}")


if __name__ == "__main__":
    unittest.main()
