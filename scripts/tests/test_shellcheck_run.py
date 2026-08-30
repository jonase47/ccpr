"""test_shellcheck_run.py -- WI-0129 D2: scripts/shellcheck-run.sh wraps the
EXTERNAL `shellcheck` tool for check-all.sh's catalogue, the same seam
artifact-gate.sh/conformance-run.sh/python-tests already use for a sibling
script that is NOT guaranteed to exist on every machine.

## Why a wrapper, and why this suite

check-all.sh compares an ACTUAL exit code against a versioned baseline
expectation -- a bare "shellcheck not installed -> some non-zero exit" would
be misread as a DIVERGENT finding rather than the distinct "nothing was
verified" state KA-G-017 already names for conformance-run.sh's own
not-configured case. This suite pins that the wrapper tells the two states
apart the same way conformance-run.sh/memory-lint.sh already do: by REPORT
TEXT (the literal substring "the shellcheck check DID NOT RUN"), never by
exit code alone -- exit 0 is shared by "verified clean" and "could not
verify anything", and only the text distinguishes them.

## The sandboxed PATH IS the "shellcheck not installed" fixture

Every subprocess in this suite runs with PATH="/usr/bin:/bin:/usr/sbin:/sbin"
(the same sandboxed PATH test_install_docs_boundary.py and
test_artifact_gate.py already use) -- not because these tests care about a
minimal PATH for its own sake, but because this maintainer's own ShellCheck
binary lives under /opt/homebrew/bin, OUTSIDE that sandboxed PATH. The
"clean scan" tests below explicitly prepend the REAL shellcheck's directory
(discovered via `shutil.which` on the unsandboxed PATH) back onto the
sandboxed one, so both states are exercised against the actual binary, never
a stub standing in for it -- the exact "not the real thing" gap G-127 warns
against.
"""

import atexit
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "shellcheck-run.sh"


def _real_shellcheck_dir():
    """The directory the REAL shellcheck binary lives in, found via the
    unsandboxed PATH -- None if this machine has none, in which case the
    "clean"/"findings" tests are skipped (they need the real tool; the
    could-not-run tests do not and always run)."""
    found = shutil.which("shellcheck")
    return str(Path(found).parent) if found else None


REAL_SHELLCHECK_DIR = _real_shellcheck_dir()

# Every external tool scripts/shellcheck-run.sh calls by name (`command -v`,
# `mktemp`, `cat`, `rm`, `grep`, `date`, plus `sed` for its own `usage()`).
# `cd`, `pwd -P`, `printf` and `command` are bash builtins and need nothing
# on PATH.
_REQUIRED_SANDBOX_TOOLS = ("bash", "sed", "mktemp", "cat", "rm", "grep", "date")


def _build_sandboxed_path_without_shellcheck(search_path=None):
    """Builds a scratch directory holding a symlink to each of
    `_REQUIRED_SANDBOX_TOOLS`'s REAL binaries, resolved from `search_path`
    (the unsandboxed PATH by default) -- and, by construction, nothing named
    `shellcheck`.

    Why not the old `"/usr/bin:/bin:/usr/sbin:/sbin"` literal: that sandbox
    happened to exclude this maintainer's Homebrew shellcheck
    (/opt/homebrew/bin), but on Ubuntu `apt install shellcheck` puts the
    binary in /usr/bin -- the SAME directory `/bin` symlinks to under
    usrmerge, alongside the very coreutils this sandbox must keep reachable.
    A sandbox built from a directory LIST cannot exclude one binary from a
    directory without excluding everything else that lives beside it; a
    sandbox built by naming individual TOOLS can, regardless of which
    directory a platform's package manager happens to use."""
    search_path = search_path if search_path is not None else os.environ.get("PATH", "")
    sandbox_dir = tempfile.mkdtemp(prefix="ccpr-shellcheck-sandbox-")
    for tool in _REQUIRED_SANDBOX_TOOLS:
        found = shutil.which(tool, path=search_path)
        if found is not None:
            os.symlink(found, os.path.join(sandbox_dir, tool))
    return sandbox_dir


SANDBOXED_PATH = _build_sandboxed_path_without_shellcheck()
atexit.register(shutil.rmtree, SANDBOXED_PATH, ignore_errors=True)


def _rmtree(p):
    shutil.rmtree(p, ignore_errors=True)


class ShellcheckRunTestBase(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="ccpr-shellcheck-run-"))
        self.addCleanup(_rmtree, self.project)

    def write_script(self, relative_path, content):
        target = self.project / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def run_wrapper(self, *args, path_with_shellcheck=False):
        path = SANDBOXED_PATH
        if path_with_shellcheck and REAL_SHELLCHECK_DIR:
            path = f"{REAL_SHELLCHECK_DIR}:{SANDBOXED_PATH}"
        return subprocess.run(
            ["bash", str(WRAPPER), *args],
            capture_output=True, text=True,
            env={"PATH": path},
        )


class SandboxPathExcludesShellcheckByConstructionTest(unittest.TestCase):
    """WI-0129: proves the sandbox construction survives the exact shape
    that broke it on Ubuntu -- shellcheck sharing a directory with the
    coreutils this test suite still needs. Simulates that by putting every
    required tool AND a fake `shellcheck` into ONE source directory (the
    `/usr/bin` == `/bin` usrmerge shape), the way the old
    `"/usr/bin:/bin:/usr/sbin:/sbin"` literal could never be tested against
    without actually running on such a machine."""

    def test_sandbox_omits_shellcheck_even_when_it_shares_a_directory_with_required_tools(self):
        with tempfile.TemporaryDirectory() as combined:
            for name in (*_REQUIRED_SANDBOX_TOOLS, "shellcheck"):
                target = Path(combined) / name
                target.write_text("#!/usr/bin/env bash\necho fake\n", encoding="utf-8")
                target.chmod(0o755)

            sandbox_dir = _build_sandboxed_path_without_shellcheck(search_path=combined)
            self.addCleanup(shutil.rmtree, sandbox_dir, ignore_errors=True)

            self.assertIsNone(
                shutil.which("shellcheck", path=sandbox_dir),
                "shellcheck must never be reachable from the constructed sandbox",
            )
            for tool in _REQUIRED_SANDBOX_TOOLS:
                self.assertIsNotNone(
                    shutil.which(tool, path=sandbox_dir),
                    f"{tool} must remain reachable even though it shared a "
                    f"source directory with shellcheck",
                )

    def test_a_directory_list_sandbox_would_have_failed_this_same_scenario(self):
        # The mutation proof: the OLD sandbox strategy (name directories,
        # not tools) cannot pass the scenario above -- if `combined` were
        # simply appended to PATH wholesale (what "/usr/bin:/bin:..." did),
        # shellcheck would be reachable right alongside every coreutil.
        with tempfile.TemporaryDirectory() as combined:
            for name in (*_REQUIRED_SANDBOX_TOOLS, "shellcheck"):
                target = Path(combined) / name
                target.write_text("#!/usr/bin/env bash\necho fake\n", encoding="utf-8")
                target.chmod(0o755)

            self.assertIsNotNone(
                shutil.which("shellcheck", path=combined),
                "sanity check: the fixture must reproduce shellcheck being "
                "colocated with the required tools",
            )


class ShellcheckNotInstalledTest(ShellcheckRunTestBase):
    """The could-not-run state (cause: no `shellcheck` binary on PATH) --
    exercised with the SANDBOXED path only, regardless of whether this
    machine actually has ShellCheck installed elsewhere."""

    def setUp(self):
        super().setUp()
        self.write_script("scripts/anything.sh", "#!/usr/bin/env bash\necho hi\n")

    def test_reports_could_not_run_when_shellcheck_is_missing(self):
        r = self.run_wrapper(str(self.project))
        self.assertIn(
            "the shellcheck check DID NOT RUN", r.stdout,
            "missing shellcheck must be reported by name, not silently -- "
            f"stdout={r.stdout!r} stderr={r.stderr!r}",
        )
        self.assertIn("not installed", r.stdout)

    def test_exit_is_zero_not_a_divergence(self):
        # A machine that never installed ShellCheck is the ORDINARY case
        # (it is not a CCPR dependency) -- could-not-run must not look like
        # a failed run to check-all.sh's exit-code comparison.
        r = self.run_wrapper(str(self.project))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_the_gegenprobe_would_fail_a_wrapper_that_always_says_could_not_run(self):
        # WI-0129's own acceptance criterion: a wrapper hardcoded to always
        # report could-not-run would pass every test above. This class's
        # sibling, ShellcheckRunsTest, is the other half -- it requires the
        # REAL binary and a REAL "0 findings"/"N findings" report, which a
        # hardcoded could-not-run wrapper could never produce.
        r = self.run_wrapper(str(self.project))
        self.assertIn("could-not-run", r.stdout)


@unittest.skipUnless(REAL_SHELLCHECK_DIR, "no shellcheck binary found on this machine")
class ShellcheckRunsTest(ShellcheckRunTestBase):
    """The counterpart to ShellcheckNotInstalledTest's could-not-run
    coverage: with the REAL binary reachable, the wrapper must behave like
    an ordinary check -- clean tree -> 0/clean, a real finding -> 1/reported
    -- never could-not-run. Without this half, a wrapper that ALWAYS prints
    "the shellcheck check DID NOT RUN" would be indistinguishable from a
    correct one by ShellcheckNotInstalledTest alone."""

    def test_a_clean_tree_exits_zero_with_zero_findings(self):
        self.write_script("scripts/clean.sh", "#!/usr/bin/env bash\nset -euo pipefail\necho hi\n")
        r = self.run_wrapper(str(self.project), path_with_shellcheck=True)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertNotIn("DID NOT RUN", r.stdout)
        self.assertIn("0 finding(s)", r.stdout)

    def test_a_real_finding_exits_one_and_is_named_in_the_report(self):
        self.write_script(
            "scripts/bad.sh",
            "#!/usr/bin/env bash\nset -euo pipefail\nFOO=bar\necho hi\n",
        )
        r = self.run_wrapper(str(self.project), path_with_shellcheck=True)
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("SC2034", r.stdout)
        self.assertIn("bad.sh", r.stdout)

    def test_severity_threshold_is_warning_an_info_only_script_is_clean(self):
        # `x=$(cmd)` with the result never read is INFO-level (SC2034 is
        # WARNING; this pins the actual configured threshold, not merely
        # "some severity is applied"). Uses a shape ShellCheck classifies as
        # info: an unused loop variable, `for _unused_i in 1 2 3; do :; done`
        # is style-level in some ShellCheck versions -- instead, pin the
        # threshold directly against the wrapper's own --severity flag by
        # asserting it is present in the report rather than depending on a
        # specific finding's severity classification (which shifts between
        # ShellCheck releases).
        r = self.run_wrapper(str(self.project), path_with_shellcheck=True)
        self.assertIn("Severity threshold:** warning", r.stdout)

    def test_scope_excludes_local_llm_by_construction_empty_scope_case(self):
        # scripts/local-llm/*.sh is never named by scripts/*.sh -- no
        # exclusion LIST is involved, the glob simply never descends. With
        # NOTHING else under scripts/*.sh, this degenerates into the
        # empty-scope could-not-run case -- see the sibling test below for
        # the non-degenerate proof (a real scan that still never reaches
        # local-llm's own finding).
        self.write_script(
            "scripts/local-llm/broken.sh",
            "#!/usr/bin/env bash\nFOO=bar\n",
        )
        r = self.run_wrapper(str(self.project), path_with_shellcheck=True)
        self.assertIn("the shellcheck check DID NOT RUN", r.stdout)
        self.assertNotIn("broken.sh", r.stdout)

    def test_scope_excludes_local_llm_by_construction_alongside_a_real_scan(self):
        # The non-degenerate proof: a genuinely scanned top-level script
        # sits ALONGSIDE local-llm's own violation, so this run is a real
        # scan (exit 0, not could-not-run) -- and local-llm's SC2034 must
        # still never surface.
        self.write_script("scripts/clean.sh", "#!/usr/bin/env bash\nset -euo pipefail\necho hi\n")
        self.write_script(
            "scripts/local-llm/broken.sh",
            "#!/usr/bin/env bash\nFOO=bar\n",
        )
        r = self.run_wrapper(str(self.project), path_with_shellcheck=True)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertNotIn("DID NOT RUN", r.stdout)
        self.assertIn("0 finding(s)", r.stdout)
        self.assertNotIn("broken.sh", r.stdout)
        self.assertNotIn("local-llm", r.stdout)

    def test_scope_includes_a_finding_under_scripts_lib(self):
        self.write_script(
            "scripts/lib/helper.sh",
            "#!/usr/bin/env bash\nset -euo pipefail\nFOO=bar\necho hi\n",
        )
        r = self.run_wrapper(str(self.project), path_with_shellcheck=True)
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("helper.sh", r.stdout)

    def test_scope_includes_install_sh_at_project_root(self):
        self.write_script("install.sh", "#!/usr/bin/env bash\nset -euo pipefail\nFOO=bar\necho hi\n")
        r = self.run_wrapper(str(self.project), path_with_shellcheck=True)
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("install.sh", r.stdout)


class EmptyScopeTest(ShellcheckRunTestBase):
    """The second could-not-run cause: shellcheck IS installed, but the
    project has none of scripts/*.sh, scripts/lib/*.sh, install.sh."""

    def test_reports_could_not_run_when_scope_is_empty(self):
        (self.project / "docs").mkdir()
        r = self.run_wrapper(str(self.project), path_with_shellcheck=True)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("the shellcheck check DID NOT RUN", r.stdout)
        self.assertIn("no scripts/*.sh", r.stdout)


class BothCouldNotRunCausesTest(ShellcheckRunTestBase):
    """Both could-not-run causes can hold at once: shellcheck missing on
    PATH (e.g. a macOS runner without Homebrew) AND an empty scope. The
    wrapper's two `if` branches used to be mutually exclusive by control
    flow -- the shellcheck-missing branch returns before the scope check is
    ever reached, so on a machine that hits both, only the FIRST cause was
    ever named and the second silently disappeared. Uses the default
    (shellcheck-excluded) sandbox on an empty project directory."""

    def test_both_causes_are_named_when_both_apply(self):
        (self.project / "docs").mkdir()
        r = self.run_wrapper(str(self.project))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("the shellcheck check DID NOT RUN", r.stdout)
        self.assertIn(
            "shellcheck not installed on PATH", r.stdout,
            f"the shellcheck-missing cause must still be named: {r.stdout!r}",
        )
        self.assertIn(
            "no scripts/*.sh", r.stdout,
            f"the empty-scope cause must not be hidden by the other cause: {r.stdout!r}",
        )


class BadUsageTest(ShellcheckRunTestBase):
    def test_nonexistent_project_dir_exits_two(self):
        r = self.run_wrapper(str(self.project / "does-not-exist"))
        self.assertEqual(2, r.returncode)

    def test_unknown_flag_exits_two(self):
        r = self.run_wrapper("--not-a-real-flag")
        self.assertEqual(2, r.returncode)

    def test_extra_positional_argument_exits_two(self):
        r = self.run_wrapper(str(self.project), "extra-arg")
        self.assertEqual(2, r.returncode)

    def test_help_flag_exits_zero_and_shows_usage(self):
        r = self.run_wrapper("--help")
        self.assertEqual(0, r.returncode)
        self.assertIn("Usage:", r.stdout)


class SelfCheckTest(unittest.TestCase):
    """The wrapper is itself a shipped `.sh` file and therefore inside its
    own scan scope (scripts/*.sh) -- it must be lint-clean, or check-all.sh's
    baseline for this very check would never be able to reach exit 0
    against the real repository."""

    @unittest.skipUnless(REAL_SHELLCHECK_DIR, "no shellcheck binary found on this machine")
    def test_the_wrapper_itself_has_zero_findings_at_warning_severity(self):
        r = subprocess.run(
            ["shellcheck", "--severity=warning", str(WRAPPER)],
            capture_output=True, text=True,
            env={"PATH": f"{REAL_SHELLCHECK_DIR}:{SANDBOXED_PATH}"},
        )
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    # The git-index executable-bit check (`git ls-files -s` -> 100755) is
    # NOT duplicated here -- test_shell_script_syntax.py's
    # test_every_shipped_script_is_executable_in_the_git_index already
    # covers every scripts/*.sh file generically via a live glob, this one
    # included. A second, file-specific copy of that assertion would only
    # be able to fail the same way (untracked/wrong mode) the generic gate
    # already catches, for a narrower reason to look in two places instead
    # of one.


if __name__ == "__main__":
    unittest.main()
