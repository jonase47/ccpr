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
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def shipped_scripts():
    return sorted(SCRIPTS_DIR.glob("*.sh")) + sorted((SCRIPTS_DIR / "lib").glob("*.sh"))


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
                "doc-volume-check.sh",
                "freeze-phase-docs.sh",
                "instinct-check.sh",
                "lib/discipline_gate.sh",
                "lib/frontmatter.sh",
                "log-cleanup.sh",
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
