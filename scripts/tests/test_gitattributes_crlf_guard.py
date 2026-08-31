"""test_gitattributes_crlf_guard.py -- a repo-level guard against Windows
line endings entering version control, plus a fixture-based proof that the
guard can actually fail.

## Why this exists

Several shell parsers in this repo were CRLF-blind, while the equivalent
Python-based parsers tolerate CRLF without complaint. Net effect: a
CRLF-tainted frontmatter file made the lint report a valid `gate: go` field
as *missing* while the actual gate mechanism (Python) accepted it anyway --
a broken check that LOOKED passed, the dangerous direction. As long as this
repo only ever had one committer on one OS that stayed theoretical; a second
contributor plus the project's first CI (potentially multiple runner OSes)
makes it not theoretical.

Status of that blast radius, updated 31.08.2026 (WI-0131), because the
paragraph that used to stand here said "explicitly OUT of scope for this
change (a separate, later item)" and that later item has since run:

  * `scripts/lib/frontmatter.sh` -- all five comparison sites repaired
    (one shell first-line test, four `awk` blocks). Pinned by
    `scripts/tests/test_frontmatter_crlf.py`.
  * `scripts/memory-lint.sh:517` -- repaired in the same round; it is a
    second, independent parser inside the same branch and the library fix
    alone turned it from accidentally-right into a false "0 bytes of body"
    report.
  * `scripts/migrate-review-headers.sh:267-268` -- STILL CRLF-blind. The
    library fix improved it (one fewer false "missing field") but its own
    `_body_text` scan never advances past a `---\r` opener, so body-borne
    fields are not hoisted out of a CRLF review document. Open finding, not
    a regression.

The old site list is deliberately not kept as line numbers here: it drifted
(`memory-lint.sh:459` pointed at a blank line by the time anyone checked)
and `test_frontmatter_crlf.py` is the register that is actually exercised.

This file only proves the narrower guard rail that keeps CRLF from entering
version control in the first place: a repo-root `.gitattributes` normalizing
tracked text files to LF, plus this test suite that (a) asserts the real repo
is clean today and stays that way, and (b) proves the detector is not
vacuously true by making it fail on a synthetic fixture.

## What "binary" means here, and why it is NOT content-sniffed

`docs/logo/ccpr-wordmark-dark.png` and `docs/logo/ccpr-wordmark-light.png`
are the only two non-text tracked files in this repo (measured via `file`
across all `git ls-files` output). Both are PNGs and, being arbitrary
compressed binary data, both incidentally contain byte sequences that
happen to equal `\r\n` -- confirmed directly:

    >>> data = Path("docs/logo/ccpr-wordmark-dark.png").read_bytes()
    >>> sum(1 for l in data.splitlines(keepends=True) if l.endswith(b"\r\n"))
    1

A content-sniffing exclusion (e.g. "looks binary via `file(1)`-style
heuristics, so skip it") would happen to work today, but it is measuring
the wrong thing: it is not what the FIX declares. This suite instead asks
git's own attribute resolution (`git check-attr binary --`) whether a path
is excluded from text handling -- the exact mechanism `.gitattributes`
itself controls. Before `.gitattributes` existed, `git check-attr binary`
reported "unspecified" for the two PNGs, so nothing was excluded, and the
detector below (correctly, if uncharitably) flagged both PNGs as
CRLF-line-terminated -- this was the file's own genuine RED state, not a
hypothetical one; see `RealRepoCrlfGuardTest`'s docstring for the measured
before/after.

The corollary is a forward-compat trap worth naming explicitly: because
the exclusion is authoritative-but-not-automatic, ANY new binary asset
added to this repo without its own `.gitattributes` `binary` line will
false-positive this guard the same way the two PNGs did before they were
declared. `.gitattributes` carries a matching comment for this reason --
see it before assuming a future red run here means real CRLF.

## What counts as "has a CRLF line ending"

Not "contains byte 0x0D anywhere" (that misfires on binary noise, as shown
above). `has_crlf_line_terminator()` uses `bytes.splitlines(keepends=True)`
and checks whether any line's own terminator is `b"\r\n"` -- i.e. CRLF
acting structurally as a line break, matching what `.gitattributes`'
`eol=lf` normalization actually acts on.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GITATTRIBUTES = REPO_ROOT / ".gitattributes"


def is_declared_binary(relative_path, cwd):
    """Ask git's own attribute resolution whether `relative_path` is
    excluded from text handling -- authoritative for whatever
    `.gitattributes` (if any) declares, not a content-sniffed guess."""
    r = subprocess.run(
        ["git", "check-attr", "binary", "--", str(relative_path)],
        cwd=str(cwd), capture_output=True, text=True,
    )
    return r.stdout.strip().endswith(": binary: set")


def has_crlf_line_terminator(path):
    """True if at least one line in `path` is terminated by CRLF, as a
    structural line break -- not merely "contains a 0x0D byte somewhere"
    (binary data does that too, see module docstring)."""
    data = Path(path).read_bytes()
    return any(line.endswith(b"\r\n") for line in data.splitlines(keepends=True))


def crlf_violations(cwd):
    """Every git-tracked file under `cwd` that is (a) not declared binary
    via `git check-attr` and (b) has at least one CRLF-terminated line."""
    r = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(cwd),
        capture_output=True, text=True, check=True,
    )
    names = [n for n in r.stdout.split("\0") if n]
    violations = []
    for name in names:
        full = Path(cwd) / name
        if not full.is_file():
            continue
        if is_declared_binary(name, cwd):
            continue
        if has_crlf_line_terminator(full):
            violations.append(name)
    return violations


class GitattributesFileTest(unittest.TestCase):
    """The file itself: exists, declares LF normalization, and excludes
    the two logo PNGs from text handling."""

    def test_gitattributes_normalizes_text_to_lf(self):
        self.assertTrue(GITATTRIBUTES.is_file(), ".gitattributes must exist at repo root")
        text = GITATTRIBUTES.read_text(encoding="utf-8")
        self.assertIn("text=auto", text)
        self.assertIn("eol=lf", text)

    def test_logo_pngs_are_declared_binary(self):
        for name in ("docs/logo/ccpr-wordmark-dark.png", "docs/logo/ccpr-wordmark-light.png"):
            with self.subTest(name=name):
                self.assertTrue(
                    is_declared_binary(name, REPO_ROOT),
                    f"{name} must resolve as `binary: set` via git check-attr",
                )

    def test_representative_text_file_resolves_to_lf(self):
        r = subprocess.run(
            ["git", "check-attr", "text", "eol", "--", "scripts/run-tests.sh"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertIn("eol: lf", r.stdout, r.stdout)


class RealRepoCrlfGuardTest(unittest.TestCase):
    """The guard that stays green forever: no tracked, non-binary file in
    THIS repo has a CRLF line ending.

    Measured RED state before `.gitattributes` declared the two PNGs
    binary: `git check-attr binary` reported "unspecified" for both, so
    the exclusion in `crlf_violations()` did not fire, and
    `has_crlf_line_terminator()` found one CRLF-terminated line in EACH
    PNG (binary noise, not real line endings) -- two false-positive
    violations. Confirmed independently before writing this test; see
    module docstring for the raw byte count.
    """

    def test_no_tracked_text_file_has_crlf_line_endings(self):
        violations = crlf_violations(REPO_ROOT)
        self.assertEqual(
            [], violations,
            "Tracked file(s) with a CRLF line ending (or an incomplete "
            "binary exclusion in .gitattributes): " + ", ".join(violations),
        )


class RedProofTest(unittest.TestCase):
    """Fixture-based proof that `crlf_violations()` is not vacuously true
    against a repo that happens to have zero CRLF today: build a scratch
    repo, commit a file with genuine CRLF line endings, and confirm the
    SAME detection logic flags it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-crlf-guard-fixture-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.repo = self.tmp / "scratch-repo"

    def env(self):
        return {
            "HOME": str(self.home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            # git refuses to commit without an identity, and HOME is empty.
            # RFC 2606 reserved domain -- no real mailbox is written down.
            "GIT_AUTHOR_NAME": "ccpr test",
            "GIT_AUTHOR_EMAIL": "ccpr@example.invalid",
            "GIT_COMMITTER_NAME": "ccpr test",
            "GIT_COMMITTER_EMAIL": "ccpr@example.invalid",
        }

    def _git(self, *args, cwd=None):
        return subprocess.run(
            ["git", *[str(a) for a in args]],
            cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, env=self.env(),
        )

    def test_detector_flags_a_genuine_crlf_text_file(self):
        r = self._git("init", "--quiet", "--initial-branch=main", self.repo)
        self.assertEqual(0, r.returncode, r.stderr)

        (self.repo / "windows.txt").write_bytes(b"line one\r\nline two\r\n")
        (self.repo / "unix.txt").write_bytes(b"line one\nline two\n")

        r = self._git("add", "windows.txt", "unix.txt", cwd=self.repo)
        self.assertEqual(0, r.returncode, r.stderr)
        r = self._git("commit", "--quiet", "-m", "seed CRLF fixture", cwd=self.repo)
        self.assertEqual(0, r.returncode, r.stderr)

        violations = crlf_violations(self.repo)
        self.assertEqual(["windows.txt"], violations)


if __name__ == "__main__":
    unittest.main()
