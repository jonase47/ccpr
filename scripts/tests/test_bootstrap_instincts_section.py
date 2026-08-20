"""test_bootstrap_instincts_section.py -- WI-0057: scripts/bootstrap.sh must
not abort its whole dashboard when an instincts file has zero headings
matching the bracket-ID convention.

## What was measured before fixing anything

The item's summary ("an instincts file with no matching heading aborts
bootstrap") does not reproduce for EVERY empty-instincts-file shape. Two
distinct cases were measured:

  * an instincts.md with literally zero `### ` headings at all (this
    repository's OWN current `~/.claude/instincts.md`, a bullet-point index
    with no H3s) -- `collect_instincts`'s own `count -eq 0` early return
    (line 184) catches this cleanly BEFORE line 206 is ever reached. Exit 0,
    "0 active instincts", no crash. The item's headline scenario, read
    literally, does not reproduce here.
  * an instincts.md that DOES have `### ` headings, just not in the
    `### [ID] ...` bracket form the offending grep looks for (e.g. plain
    `### Some heading` -- the shape this repository's OWN topic files
    actually use: `### G-008: Wingman required ...`, no leading bracket).
    Here `count` (the broad `grep -c '^### '`) is non-zero, the early
    return is skipped, and `grep -E '^### \\['` on line 206 legitimately
    matches nothing, exits 1, and -- under this file's `set -o pipefail`
    -- takes the whole `{ ... } > "${OUTPUT_FILE}"` block down with it.
    This is the reproducible case: exit 1, empty stderr (no diagnostic at
    all), and no "Session context written" confirmation, even though every
    section BEFORE "## Instinct Status" was already written correctly to
    the output file (the block writes as it goes; only the tail is lost).

Root cause, distinguished per the item's own request: this is PURE
`set -o pipefail` on a legitimately empty grep result, not SIGPIPE from
`head -5` closing the pipe early. Verified directly: with zero matches,
`head -5` never even needs to read (grep produces nothing, exits 1, and
the isolated 3-line pipeline `grep | head -5 | while read` aborts the
containing script at that exact statement under pipefail). A second probe
with 200 matching headings (far more than `head -5` will take) still exits
0 for the pipeline itself -- `head` closing the pipe early does not turn
into a SIGPIPE-driven non-zero exit in this shell/OS combination, and it is
not the mechanism in the reported (empty-result) scenario in any case.

## The fix

`grep`'s own documented exit-status contract (verified against both GNU and
BSD grep on this machine) already distinguishes the two directions the item
asks to keep apart: exit 1 means "ran fine, nothing matched" (a normal,
valid state for this optional field), exit 2+ means a real failure (cannot
read the file, bad pattern, ...). The fix captures the grep call's output
and status explicitly, treats 1 as the valid-empty case (no heading lines
printed, no crash), and treats anything higher as a real problem worth a
visible `WARNING`, returning the section early rather than falling through
with stale data. This is NOT a blanket `|| true`: a blanket swallow would
make a genuine grep failure indistinguishable from a legitimate empty
result again -- the exact confusion the item explicitly warns against
recreating in the other direction.
"""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "bootstrap.sh"

HEADINGS_WITHOUT_BRACKETS = (
    "# Instincts\n\n"
    "### Some heading without brackets\n"
    "Body text.\n\n"
    "### Another plain heading\n"
    "More text.\n"
)

HEADINGS_WITH_BRACKETS = (
    "# Instincts\n\n"
    "### [G-001] First tracked instinct\n"
    "Body text.\n\n"
    "### [G-002] Second tracked instinct\n"
    "More text.\n"
)


class BootstrapInstinctsTestBase(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="ccpr-bootstrap-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        (self.home / ".claude").mkdir(parents=True)
        self.project = Path(tempfile.mkdtemp(prefix="ccpr-bootstrap-project-"))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        (self.project / "docs").mkdir()

    def write_instincts(self, content):
        (self.home / ".claude" / "instincts.md").write_text(content, encoding="utf-8")

    def env(self, **extra):
        e = dict(os.environ)
        e["HOME"] = str(self.home)
        e.update(extra)
        return e

    def run_bootstrap(self, **extra_env):
        return subprocess.run(
            ["bash", str(SCRIPT), str(self.project)],
            capture_output=True, text=True, env=self.env(**extra_env),
        )

    def session_context(self):
        return (self.project / "docs" / ".session-context.md").read_text(encoding="utf-8")


class HeadingsWithoutBracketIdTest(BootstrapInstinctsTestBase):
    """The reproducible scenario: `### ` headings exist, none match the
    `^### \\[` bracket-ID convention -- a legitimate empty result for THIS
    grep, not a crash."""

    def test_bootstrap_completes_instead_of_aborting(self):
        self.write_instincts(HEADINGS_WITHOUT_BRACKETS)
        r = self.run_bootstrap()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("Session context written", r.stdout, r.stdout + r.stderr)

    def test_the_instinct_status_section_is_written_with_a_zero_count_and_no_headings(self):
        self.write_instincts(HEADINGS_WITHOUT_BRACKETS)
        self.run_bootstrap()
        content = self.session_context()
        self.assertIn("## Instinct Status", content)
        self.assertIn("- 2 active instincts", content)
        self.assertNotIn("Some heading without brackets", content)

    def test_no_spurious_warning_is_printed_for_a_legitimate_empty_result(self):
        self.write_instincts(HEADINGS_WITHOUT_BRACKETS)
        self.run_bootstrap()
        content = self.session_context()
        self.assertNotIn("could not scan", content)


class HeadingsWithBracketIdStillListedTest(BootstrapInstinctsTestBase):
    """Regression guard: the fix must not stop real matches from being
    listed -- only the legitimate-empty case changes behaviour."""

    def test_matching_headings_are_still_listed(self):
        self.write_instincts(HEADINGS_WITH_BRACKETS)
        r = self.run_bootstrap()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        content = self.session_context()
        self.assertIn("[G-001]", content)
        self.assertIn("[G-002]", content)


class RealGrepFailureIsSurfacedTest(BootstrapInstinctsTestBase):
    """Proves the OTHER direction the item insists stays distinguishable:
    a genuine grep failure (not "nothing matched") must not be silently
    swallowed either. A pattern-aware PATH stub is used deliberately: the
    real grep binary cannot be made to fail on demand for one specific
    pattern while succeeding for another against the same readable file,
    which is exactly what isolating this one call requires."""

    def install_pattern_aware_grep_stub(self):
        stub_dir = Path(tempfile.mkdtemp(prefix="ccpr-bootstrap-grep-stub-"))
        self.addCleanup(shutil.rmtree, stub_dir, ignore_errors=True)
        stub = stub_dir / "grep"
        stub.write_text(
            "#!/usr/bin/env bash\n"
            "for a in \"$@\"; do\n"
            "  if [[ \"$a\" == '^### \\[' ]]; then\n"
            "    echo 'grep: simulated read failure' >&2\n"
            "    exit 2\n"
            "  fi\n"
            "done\n"
            "exec /usr/bin/grep \"$@\"\n",
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        return f"{stub_dir}:/usr/bin:/bin:/usr/sbin:/sbin"

    def test_a_real_grep_error_produces_a_warning_not_a_silent_empty_result(self):
        self.write_instincts(HEADINGS_WITH_BRACKETS)
        path = self.install_pattern_aware_grep_stub()
        r = self.run_bootstrap(PATH=path)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        content = self.session_context()
        self.assertIn("could not scan", content)


class RedProofTest(BootstrapInstinctsTestBase):
    """Mutation proof, inline: restoring the exact pre-fix line (a bare
    `grep -E '^### \\[' ... | head -5 | while read`, no status capture)
    must reproduce the measured abort."""

    def test_reverting_the_status_check_reproduces_the_abort(self):
        pre_fix_block = (
            "    # List instinct IDs with confidence\n"
            "    grep -E '^### \\[' \"${INSTINCTS_FILE}\" 2>/dev/null | "
            "head -5 | while read -r line; do  "
            "# exit-status: exempt known-risk-not-yet-fixed\n"
            "        echo \"  ${line}\"\n"
            "    done\n"
        )
        current = SCRIPT.read_text(encoding="utf-8")
        start = current.index("    # List instinct IDs with confidence")
        end = current.index("\n}", start) + 1  # up to (not incl.) the closing brace
        mutated = current[:start] + pre_fix_block + current[end:]
        self.assertNotEqual(current, mutated)

        scratch = Path(tempfile.mkdtemp(prefix="ccpr-bootstrap-mutant-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        mutant_script = scratch / "bootstrap.sh"
        mutant_script.write_text(mutated, encoding="utf-8")
        mutant_script.chmod(mutant_script.stat().st_mode | stat.S_IEXEC)

        self.write_instincts(HEADINGS_WITHOUT_BRACKETS)
        r = subprocess.run(
            ["bash", str(mutant_script), str(self.project)],
            capture_output=True, text=True, env=self.env(),
        )
        self.assertNotEqual(0, r.returncode)
        self.assertNotIn("Session context written", r.stdout)


if __name__ == "__main__":
    unittest.main()
