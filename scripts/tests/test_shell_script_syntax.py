"""test_shell_script_syntax.py -- WI-0055: every shipped shell script must
parse.

## Why this exists

scripts/quality-scan.sh shipped with an unparseable heredoc nested inside a
command substitution (`grep_findings=$(python3 << 'PYEOF' ... PYEOF)`): an
odd number of apostrophes inside the heredoc BODY broke bash's quote
tracking while it scanned for the closing `)` of the substitution --
`bash -n` failed with "syntax error near unexpected token '('" at the line
carrying the SQL-string detection pattern. No test ran `bash -n` (or
anything else) over the file, so the defect shipped and stayed unnoticed:
running the script printed the same syntax error to stderr, wrote no report,
and still EXITED 0 -- WI-0054's own verification pass found it only by
accident, while checking something unrelated.

This generalises WI-0027's single-file precedent
(`test_the_template_is_syntactically_valid_posix_sh`, over
`templates/ci/artifact-gate.ci.sh`) to every script this project actually
SHIPS as an executable: `scripts/*.sh` and `scripts/lib/*.sh`. That is
deliberately the same enumeration `test_external_tool_exit_status.py`
(WI-0054) already uses for the same 15 files, so the two suites agree on
what "shipped" means and a file added to one scope is automatically in the
other. `scripts/local-llm/*.sh` is out of scope: install.sh's own docstring
marks it user-owned/hardware-specific (PROTECTED, never overwritten on
`--update`), not a "shipped, always-identical" artefact. `templates/ci/*.sh`
already has its own `sh -n` gate from WI-0027.

`bash -n` only proves the file PARSES, not that it WORKS -- WI-0027's own
result recorded exactly that gap ("quoting fidelity is not executability").
`scripts/tests/test_quality_scan.py` covers the "does it actually run and
write its report" half for the one script this item repairs.

## The executable bit

`scripts/check-all.sh` shipped without its executable bit and stayed
unnoticed: every caller in this repository invokes shipped scripts as
`bash scripts/<name>.sh`, so the mode never affected anything the suite
runs -- it was found by hand during an install-verification pass, not by
a mechanism. `test_every_shipped_script_is_executable_in_the_git_index`
closes that gap.

It asserts the GIT INDEX mode (`git ls-files -s` -> `100755` vs
`100644`), not the working tree's filesystem mode. The two usually agree
-- `git checkout` sets the filesystem bit FROM the index -- but the
filesystem mode is what a *particular* working copy happens to have after
whatever sequence of local edits, `chmod`s and partial checkouts produced
it, not what a fresh `git clone` reproducibly gets. The index mode is
what actually SHIPS, and it is exactly the value that was wrong here: a
developer could have `chmod +x`'d their own local copy without ever
fixing the commit, and a filesystem-mode assertion would have stayed
green throughout. `git ls-files -s` needs git; if it is unavailable,
`subprocess.run(..., check=True)` raises and the test ERRORS -- loud, not
a silent pass with an empty scope. A second assertion additionally pins
the scanned-line count against `shipped_scripts()`'s own enumeration
before checking any mode, so a `git ls-files -s` call that returns fewer
lines than expected (wrong cwd, glob typo, git failure swallowed
upstream) cannot be mistaken for "everything's executable" by having
nothing left to check.

`hooks/` is out of scope: nothing under it ships as a `.sh` file (Python
only), so the enumeration this file already shares with
`test_external_tool_exit_status.py` does not need widening for it.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def shipped_scripts():
    return sorted(SCRIPTS_DIR.glob("*.sh")) + sorted((SCRIPTS_DIR / "lib").glob("*.sh"))


def entry_point_scripts():
    """The scripts a user or a caller RUNS: scripts/*.sh only.

    scripts/lib/*.sh is deliberately excluded. Both files there are sourced
    (`. "$HERE/lib/discipline_gate.sh"`, `. "$HERE/lib/frontmatter.sh"`) and
    never executed -- verified across scripts/, hooks/ and scripts/tests/ on
    29.08.2026; a shebang in a sourced file is inert. So the executable bit
    carries no meaning for them, and requiring it would be mode noise
    asserted for its own sake. `discipline_gate.sh` sits at 100644 today and
    that is correct, not a defect; `frontmatter.sh` sits at 100755, which is
    harmless and deliberately left unasserted in either direction.

    The parse check above keeps the wider enumeration on purpose -- a
    library that does not parse is broken whether or not anyone runs it.
    """
    return sorted(SCRIPTS_DIR.glob("*.sh"))


class ShellScriptSyntaxTest(unittest.TestCase):
    def setUp(self):
        # bash -n only parses, never executes -- but every subprocess in
        # this suite is HOME-sandboxed anyway, mirroring
        # test_artifact_gate.py's own reasoning: an unsandboxed invocation
        # here would otherwise go unnoticed if -n were ever accidentally
        # dropped from this test.
        self.home = Path(tempfile.mkdtemp(prefix="ccpr-shell-syntax-home-"))
        self.addCleanup(_rmtree, self.home)

    def env(self):
        return {"HOME": str(self.home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}

    def test_every_shipped_script_parses_with_bash_n(self):
        violations = []
        for f in shipped_scripts():
            r = subprocess.run(
                ["bash", "-n", str(f)],
                capture_output=True, text=True, env=self.env(),
            )
            if r.returncode != 0:
                violations.append(f"{f.relative_to(REPO_ROOT)}: {r.stderr.strip()}")
        self.assertEqual(
            [], violations,
            "Unparseable shipped script(s) -- `bash -n` failed: " + "; ".join(violations),
        )

    def test_every_shipped_script_is_executable_in_the_git_index(self):
        """See the module docstring's "The executable bit" section for why
        the GIT INDEX mode is asserted rather than the working tree's
        filesystem mode, and why a scope-count assertion runs first. Scope is
        entry_point_scripts(), not shipped_scripts() -- see that function for
        why a sourced library's mode is not this check's business."""
        scripts = entry_point_scripts()
        result = subprocess.run(
            ["git", "ls-files", "-s"] + [str(f) for f in scripts],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        self.assertEqual(
            len(scripts), len(lines),
            "`git ls-files -s` returned {} line(s) for {} enumerated shipped "
            "scripts -- scope drift, not a pass:\n{}".format(
                len(lines), len(scripts), result.stdout,
            ),
        )
        non_executable = [
            line.split("\t", 1)[1] for line in lines if not line.startswith("100755")
        ]
        self.assertEqual(
            [], non_executable,
            "Shipped script(s) not executable (mode != 100755) in the git "
            "index: " + ", ".join(non_executable),
        )

    def test_scanned_files_cover_the_shipped_scope(self):
        """Pins the enumeration itself, mirroring
        test_external_tool_exit_status.py's own
        test_scanned_files_cover_the_shipped_scope -- a file silently
        dropped from the glob (renamed, moved out of scripts/lib/) would
        make the syntax gate blind to it without this failing first."""
        names = sorted(f.relative_to(SCRIPTS_DIR).as_posix() for f in shipped_scripts())
        self.assertEqual(
            [
                "anchor.sh",
                "artifact-gate.sh",
                "baseline.sh",
                "bootstrap.sh",
                "check-all.sh",
                "conformance-run.sh",
                "doc-volume-check.sh",
                "freeze-phase-docs.sh",
                "instinct-check.sh",
                "lib/discipline_gate.sh",
                "lib/frontmatter.sh",
                "log-cleanup.sh",
                "manual-lint.sh",
                "memory-lint.sh",
                "memory-sync.sh",
                "migrate-review-headers.sh",
                "phase-docs-lint.sh",
                "project-init.sh",
                "quality-scan.sh",
                "run-tests.sh",
            ],
            names,
        )


def _rmtree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
