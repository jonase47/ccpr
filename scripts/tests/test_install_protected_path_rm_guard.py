"""test_install_protected_path_rm_guard.py -- WI-0129 D1 (ShellCheck SC2115):
install.sh's PROTECTED-path restore loop had two `rm -rf` calls against the
same "$DEST/<subpath>" shape a few lines apart -- line 340 already guards
DEST with `${DEST:?}` (a stash-and-replace against the newly-copied
artifact), but line 346 (restoring a stashed PROTECTED sub-path back over
it) did not. Both share the identical risk ShellCheck's SC2115 names: if
DEST were ever empty, `"$DEST/$p"` silently becomes "/$p" -- a wholesale
delete rooted at the filesystem root -- instead of aborting loudly.

## Why DEST cannot actually go empty today, and why the guard still matters

`DEST="${CCPR_DEST:-$HOME/.claude}"` can never resolve to an empty string
through any input this script currently accepts: `${VAR:-default}` falls
back to the default whenever VAR is unset OR empty, and `"$HOME/.claude"`
is never empty by construction (an empty $HOME still yields the literal
string "/.claude"). This test does not claim a reachable exploit against
install.sh AS SHIPPED TODAY -- it pins the invariant the guard establishes
(the same invariant line 340's pre-existing guard already established one
call earlier in the very same loop), and it protects against the next
refactor that computes DEST differently and reintroduces the gap silently.

## What is tested

`RmProtectedPathGuardShippedTest` pins that install.sh actually ships the
guarded form, read from the file itself rather than retyped, so a future
edit that drops `${DEST:?}` again fails this test immediately.
`EmptyDestAbortsRatherThanExpandingTest` reproduces the EXACT guarded
expression install.sh ships (extracted from the file, never hand-copied)
in a disposable scratch script with DEST forced empty, and asserts it
aborts (nonzero exit, `$?`-visible error mentioning the unset-or-null
parameter) instead of silently running `rm -rf` against a bare `/$p`.
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = REPO_ROOT / "install.sh"

GUARDED_EXPRESSION = 'rm -rf "${DEST:?}/$p"'


def _extract_guarded_line():
    """Pulls the exact `rm -rf "${DEST:?}/$p"` statement out of install.sh's
    own text -- never hand-retyped -- so this test cannot silently drift
    from what is actually shipped."""
    text = INSTALL.read_text(encoding="utf-8")
    for line in text.splitlines():
        if GUARDED_EXPRESSION in line:
            return line.strip()
    return None


class RmProtectedPathGuardShippedTest(unittest.TestCase):
    def test_install_sh_ships_the_guarded_rm_of_the_restored_protected_path(self):
        line = _extract_guarded_line()
        self.assertIsNotNone(
            line,
            f"install.sh no longer contains {GUARDED_EXPRESSION!r} -- the "
            "PROTECTED-path restore's rm -rf lost its ${DEST:?} guard "
            "(WI-0129 D1 / ShellCheck SC2115)",
        )


class EmptyDestAbortsRatherThanExpandingTest(unittest.TestCase):
    def test_an_empty_dest_aborts_instead_of_expanding_to_a_bare_root_path(self):
        line = _extract_guarded_line()
        self.assertIsNotNone(line, "guarded expression not found in install.sh")
        # Reproduce the EXACT statement install.sh ships, in a minimal
        # script that binds DEST empty and p to a realistic PROTECTED
        # entry's basename -- the same shape as the real loop's own `for p
        # in "${PROTECTED[@]}"`.
        script = f'DEST=""; p="local-llm"; {line}'
        r = subprocess.run(
            ["bash", "-c", script],
            capture_output=True, text=True,
        )
        self.assertNotEqual(
            0, r.returncode,
            "an empty DEST did not abort the guarded rm -- the guard is "
            f"not doing its job. stdout={r.stdout!r} stderr={r.stderr!r}",
        )
        self.assertTrue(
            re.search(r"DEST.*(unbound|null|unset|parameter)", r.stderr, re.IGNORECASE),
            f"abort message does not name the unset/null DEST parameter: {r.stderr!r}",
        )

    def test_a_populated_dest_still_only_removes_the_intended_subpath(self):
        # Control: the guard must be a no-op on the ordinary, populated
        # case -- otherwise "aborts on empty" could be masking a guard that
        # also breaks the real, non-empty path.
        line = _extract_guarded_line()
        self.assertIsNotNone(line, "guarded expression not found in install.sh")
        import shutil
        import tempfile

        dest = Path(tempfile.mkdtemp(prefix="ccpr-rm-guard-dest-"))
        self.addCleanup(shutil.rmtree, dest, ignore_errors=True)
        (dest / "local-llm").mkdir()
        (dest / "local-llm" / "keep-me.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        (dest / "sibling.txt").write_text("untouched\n", encoding="utf-8")

        script = f'DEST={dest!s}; p="local-llm"; {line}'
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertFalse((dest / "local-llm").exists())
        self.assertTrue((dest / "sibling.txt").exists())


if __name__ == "__main__":
    unittest.main()
