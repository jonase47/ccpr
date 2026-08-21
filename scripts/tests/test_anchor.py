"""test_anchor.py -- coverage for scripts/anchor.sh (WI-0021, wave 4a).

Ground-up test module for a script that ships with zero prior coverage.
Design source: docs/adr/ADR-0009-anchored-state-verification.md, especially
Addendum 2 ("A7 resolved -- where the scope anchor lives") and the
"comparison point, measured" section it closes with.

House pattern borrowed from test_phase_docs_lint.py: invoke the real entry
point as a subprocess against the shipped script (never sourced internals),
so the tests also cover report rendering and the documented exit-code
contract. Unlike phase-docs-lint.sh's 0/1/2 severity scale, anchor.sh's
`status`/`check` commands are Stage-1 and DATA-ONLY -- exit 0 means "a
report was produced" (drift or not), exit 2 means "the run could not be
performed as asked" (bad usage, no git repo, no docs/). See the script's
own header comment for the full contract and why it deliberately differs
from phase-docs-lint.sh's.

Every test drives the SHIPPED scripts/anchor.sh against a throwaway git
repository (tempfile.mkdtemp), never this repository's own docs/ or .git.

Each check below was seen red at least once during authoring, via a
targeted mutation of the shipped script (value swap, condition invert,
classification/comparison-point swap -- never a feature removed from the
test itself), then restored to its exact original text. The
mutation-to-test mapping is reported in the session summary, not encoded
here.
"""

import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "anchor.sh"
FRONTMATTER_LIB = Path(__file__).resolve().parents[1] / "lib" / "frontmatter.sh"

VALID_DATE = "18.08.2026"


def frontmatter_block(phase="P3", subskill="arch-index", status="living",
                       last_updated=VALID_DATE, extra_lines=()):
    """Build a minimal frontmatter block. Pass a field as None to omit it."""
    lines = []
    if phase is not None:
        lines.append(f"phase: {phase}")
    if subskill is not None:
        lines.append(f"subskill: {subskill}")
    if status is not None:
        lines.append(f"status: {status}")
    if last_updated is not None:
        lines.append(f"last_updated: {last_updated}")
    lines.extend(extra_lines)
    return "---\n" + "\n".join(lines) + "\n---\n"


def doc_text(body="\n# Doc\n\nBody.\n", **fm_kwargs):
    return frontmatter_block(**fm_kwargs) + body


class FmSetTest(unittest.TestCase):
    """fm_set is the portable frontmatter writer WI-0076 requires (temp
    file + `mv`, no `sed -i` -- ADR-0009 Addendum 1, A8). Exercised
    directly here since both anchor.sh's `set`/`ack` verbs (Part 2/4) and
    freeze-phase-docs.sh (Part 1) depend on its exact contract: replace a
    flat top-level key in place, insert a missing one just before the
    closing `---`, never touch the body -- even a body line that reads
    exactly like `key: value` -- and refuse rather than silently create
    when there is no frontmatter block at all."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-fmset-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write(self, text):
        p = self.tmp / "doc.md"
        p.write_text(text, encoding="utf-8")
        return p

    def fm_set(self, file, key, value):
        script = f'source "{FRONTMATTER_LIB}"; fm_set "$1" "$2" "$3"'
        return subprocess.run(
            ["bash", "-c", script, "--", str(file), key, value],
            capture_output=True, text=True,
        )

    def test_replaces_an_existing_flat_key_in_place(self):
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        result = self.fm_set(f, "status", "frozen")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("---\nphase: P3\nstatus: frozen\n---\nBody.\n", f.read_text())

    def test_inserts_a_missing_key_before_the_closing_marker(self):
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        result = self.fm_set(f, "anchor_commit", "abc123")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "---\nphase: P3\nstatus: draft\nanchor_commit: abc123\n---\nBody.\n",
            f.read_text(),
        )

    def test_never_touches_a_body_line_that_looks_like_the_key(self):
        f = self.write("---\nphase: P3\nstatus: draft\n---\nstatus: frozen (in prose)\n")
        result = self.fm_set(f, "status", "frozen")
        self.assertEqual(0, result.returncode, result.stderr)
        text = f.read_text()
        self.assertIn("status: frozen (in prose)", text)
        # exactly one bare "status: frozen" line -- the rewritten
        # frontmatter key -- the body's prose line must stay untouched
        # alongside it, not collapse into a second identical bare line.
        self.assertEqual(1, text.count("status: frozen\n"))

    def test_does_not_touch_any_other_frontmatter_line(self):
        f = self.write(
            "---\nphase: P3\nsubskill: arch-index\nstatus: draft\n"
            "last_updated: 18.08.2026\n---\nBody.\n"
        )
        result = self.fm_set(f, "status", "frozen")
        self.assertEqual(0, result.returncode, result.stderr)
        text = f.read_text()
        self.assertIn("phase: P3\n", text)
        self.assertIn("subskill: arch-index\n", text)
        self.assertIn("last_updated: 18.08.2026\n", text)

    def test_errors_on_a_file_without_frontmatter_rather_than_creating_one(self):
        f = self.write("# Just a document\n\nNo frontmatter here.\n")
        original = f.read_text()
        result = self.fm_set(f, "status", "frozen")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(original, f.read_text())

    def test_idempotent_second_call_is_byte_identical(self):
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        self.fm_set(f, "status", "frozen")
        first = f.read_text()
        self.fm_set(f, "status", "frozen")
        second = f.read_text()
        self.assertEqual(first, second)

    def test_a_literal_backslash_n_in_the_value_is_not_turned_into_a_real_newline(self):
        """WI-0021 review, Important 1. `awk -v v='a\\nb'` runs the SAME
        backslash-escape processing as an awk string literal, so a value
        that merely CONTAINS the two characters backslash+n (a --note
        argument like `siehe docs\\notes.md`, or any Windows-style path
        fragment) silently becomes a REAL newline byte -- reproduced
        directly: `awk -v v='a\\nb' 'BEGIN{print length(v)}'` prints 3,
        not 4, and `od -c` on the result shows an actual \\n byte. A real
        newline splits one frontmatter line into two, corrupting the
        block fm_set's own body-boundary fold exists to protect."""
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        value = "siehe docs\\notes.md"  # literal backslash + 'n', not a real newline
        result = self.fm_set(f, "anchor_ack_note", value)
        self.assertEqual(0, result.returncode, result.stderr)
        text = f.read_text()
        self.assertIn(f"anchor_ack_note: {value}\n", text)
        # Exactly 5 lines (---, phase, status, anchor_ack_note, ---) plus
        # the body -- a real newline inside the value would add a 6th.
        self.assertEqual(6, text.count("\n"))

    def test_preserves_0644_file_permissions(self):
        """WI-0021 review, Important 2. `mktemp` creates its temp file
        with mode 0600, and `mv` on the same filesystem is a `rename()` --
        the renamed inode carries the SOURCE file's permissions forward,
        not the destination's. Reproduced directly: a 644 file reads 600
        after a plain fm_set. Every `anchor set`/`ack`/freeze run touches
        files it does not own, so a silent permission narrowing is a real
        blast radius, not a cosmetic detail."""
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        os.chmod(f, 0o644)
        result = self.fm_set(f, "status", "frozen")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0o644, stat.S_IMODE(f.stat().st_mode))

    def test_preserves_0755_file_permissions(self):
        """Same as above with a DIFFERENT starting mode -- proves the fix
        actually copies the ORIGINAL's bits rather than happening to land
        on 644 by coincidence (e.g. via a hard-coded chmod)."""
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        os.chmod(f, 0o755)
        result = self.fm_set(f, "status", "frozen")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0o755, stat.S_IMODE(f.stat().st_mode))

    def test_key_is_matched_literally_not_interpolated_into_a_regex(self):
        """Small fix #1 (WI-0021 review): `$0 ~ "^" key ":"` interpolates
        the key unchecked into a regex, so a key containing a regex
        metacharacter (here: the '.') would ALSO match an unrelated line
        whose text merely happens to fit the resulting wildcard pattern.
        Unreachable via any of this repo's current callers (all pass a
        literal identifier), but fm_set is documented as a general write
        path. `index($0, key ":") == 1` is the literal-match fix."""
        f = self.write("---\na.b: original\naxb: unrelated\n---\nBody.\n")
        result = self.fm_set(f, "a.b", "changed")
        self.assertEqual(0, result.returncode, result.stderr)
        text = f.read_text()
        self.assertIn("a.b: changed\n", text)
        self.assertIn("axb: unrelated\n", text)

    def test_file_without_a_trailing_newline_is_written_correctly(self):
        """Small fix / test-gap #2 (WI-0021 review): the body's last line
        has no trailing \\n byte -- fm_set must neither crash nor silently
        add one it was never asked to add."""
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody, no trailing newline.")
        result = self.fm_set(f, "status", "frozen")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "---\nphase: P3\nstatus: frozen\n---\nBody, no trailing newline.",
            f.read_text(),
        )

    def test_frontmatter_longer_than_fifty_lines_is_refused_like_no_frontmatter_at_all(self):
        """Test-gap #1 (WI-0021 review): fm_has's own closing-marker scan
        gives up after 50 lines (its documented search window). fm_set
        gates on fm_has FIRST, so a frontmatter block whose closing `---`
        sits beyond line 50 is refused with the same 'no frontmatter
        block' error as a file with none at all -- a clean, documented
        refusal (original left byte-for-byte untouched), not a silent
        partial write. Locking this in here rather than widening fm_has's
        window, which phase-docs-lint.sh also depends on and is out of
        this work item's scope."""
        lines = [f"k{i}: v{i}" for i in range(1, 60)]
        text = "---\n" + "\n".join(lines) + "\n---\nBody.\n"
        f = self.write(text)
        result = self.fm_set(f, "k1", "changed")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("no frontmatter block", result.stderr)
        self.assertEqual(text, f.read_text())


class FmSetManyTest(unittest.TestCase):
    """fm_set_many is the Critical fix (WI-0021 review): `anchor ack`
    used to write its five keys via five SEPARATE fm_set calls. Each call
    is individually atomic (temp file + `mv`), but the GROUP of five is
    not -- an abort between the first and the second call (signal, full
    disk, write error) leaves a document carrying the NEW anchor_commit
    but NONE of the anchor_ack fields, which `status` then reads as "no
    anchor_ack recorded" -> "not stale" -> the drift silently vanishes
    without ever having been acknowledged (ADR-0009 §6: "the single
    highest-risk detail in the whole design"). fm_set_many closes this
    structurally: one awk pass, one temp file, one `mv` -- there is no
    intermediate state where some keys are written and others are not."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ccpr-fmsetmany-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write(self, text):
        p = self.tmp / "doc.md"
        p.write_text(text, encoding="utf-8")
        return p

    def fm_set_many(self, file, *pairs):
        script = f'source "{FRONTMATTER_LIB}"; fm_set_many "$@"'
        return subprocess.run(
            ["bash", "-c", script, "--", str(file), *pairs],
            capture_output=True, text=True,
        )

    def test_writes_all_given_keys_in_one_call(self):
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        result = self.fm_set_many(
            f, "anchor_commit=abc123", "anchor_date=18.08.2026",
            "anchor_ack=asserted", "anchor_ack_from=old123", "anchor_ack_note=fine",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        text = f.read_text()
        self.assertIn("anchor_commit: abc123\n", text)
        self.assertIn("anchor_date: 18.08.2026\n", text)
        self.assertIn("anchor_ack: asserted\n", text)
        self.assertIn("anchor_ack_from: old123\n", text)
        self.assertIn("anchor_ack_note: fine\n", text)

    def test_replaces_existing_keys_and_inserts_missing_ones_together(self):
        f = self.write("---\nphase: P3\nanchor_commit: old\nstatus: draft\n---\nBody.\n")
        result = self.fm_set_many(f, "anchor_commit=new", "anchor_ack=asserted")
        self.assertEqual(0, result.returncode, result.stderr)
        text = f.read_text()
        self.assertIn("anchor_commit: new\n", text)
        self.assertNotIn("anchor_commit: old", text)
        self.assertIn("anchor_ack: asserted\n", text)
        self.assertIn("status: draft\n", text)

    def test_produces_exactly_one_temp_file_and_leaves_the_directory_clean(self):
        """The atomicity proof, at the filesystem level: while (and
        after) a call runs, the directory holds exactly the original
        target -- never more than one extra temp entry, and never zero
        (the target itself must still exist)."""
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        result = self.fm_set_many(f, "anchor_commit=abc123", "anchor_ack=asserted")
        self.assertEqual(0, result.returncode, result.stderr)
        entries = sorted(p.name for p in self.tmp.iterdir())
        self.assertEqual(["doc.md"], entries)

    def test_an_awk_failure_leaves_all_keys_unwritten_as_a_group(self):
        """Simulates the 'abort between the first and the second write'
        failure mode this function exists to close: `awk` itself fails
        (a stub shadowing the real one on PATH, exiting nonzero) -- and
        the property under test is that NONE of the keys land, not that
        some subset does."""
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        original = f.read_text()
        stub_bin = self.tmp / "stub-bin"
        stub_bin.mkdir()
        stub_awk = stub_bin / "awk"
        stub_awk.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        stub_awk.chmod(0o755)
        script = f'source "{FRONTMATTER_LIB}"; fm_set_many "$@"'
        env = {**os.environ, "PATH": f"{stub_bin}:{os.environ.get('PATH', '')}"}
        result = subprocess.run(
            ["bash", "-c", script, "--", str(f),
             "anchor_commit=abc123", "anchor_ack=asserted", "anchor_ack_note=x"],
            capture_output=True, text=True, env=env,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(original, f.read_text())
        entries = sorted(p.name for p in self.tmp.iterdir() if p != stub_bin)
        self.assertEqual(["doc.md"], entries)

    def test_the_whole_group_lands_within_the_two_awk_calls_a_correct_implementation_needs(self):
        """The group-atomicity proof (WI-0021 review, Critical), simulating
        the exact failure ADR-0009 SS6 warns against: an abort BETWEEN the
        first and the second key write. A stub `awk` succeeds on its
        first TWO invocations (delegating to the real awk) and fails from
        the third onward. A correct fm_set_many makes exactly two awk
        calls for the WHOLE group regardless of key count -- one from its
        own fm_has precondition check, one for the single group-write
        pass -- so ALL FIVE keys land within that budget and the call
        succeeds. A regression back to "one fm_set call per key" needs
        two awk calls PER KEY (that key's own fm_has, then its own
        write), so it would let the FIRST key's fm_set call succeed
        (consuming both allowed invocations) and then abort on the
        SECOND key's own fm_has check -- leaving anchor_commit written
        but every other key missing, the exact partial-write defect this
        function exists to close (mutation-verified directly, see the
        session summary)."""
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        real_awk = shutil.which("awk")
        stub_bin = self.tmp / "stub-bin-counting"
        stub_bin.mkdir()
        counter_file = self.tmp / "awk-call-count"
        counter_file.write_text("0")
        stub_awk = stub_bin / "awk"
        stub_awk.write_text(
            "#!/bin/sh\n"
            f'count_file="{counter_file}"\n'
            'n=$(cat "$count_file")\n'
            'n=$((n + 1))\n'
            'echo "$n" > "$count_file"\n'
            'if [ "$n" -ge 3 ]; then exit 1; fi\n'
            f'exec "{real_awk}" "$@"\n',
            encoding="utf-8",
        )
        stub_awk.chmod(0o755)
        script = f'source "{FRONTMATTER_LIB}"; fm_set_many "$@"'
        env = {**os.environ, "PATH": f"{stub_bin}:{os.environ.get('PATH', '')}"}
        result = subprocess.run(
            ["bash", "-c", script, "--", str(f),
             "anchor_commit=abc123", "anchor_ack=asserted", "anchor_ack_note=x"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        text = f.read_text()
        self.assertIn("anchor_commit: abc123", text)
        self.assertIn("anchor_ack: asserted", text)
        self.assertIn("anchor_ack_note: x", text)

    def test_body_is_never_touched(self):
        f = self.write("---\nphase: P3\nstatus: draft\n---\nstatus: frozen (in prose)\n")
        result = self.fm_set_many(f, "status=frozen")
        self.assertEqual(0, result.returncode, result.stderr)
        text = f.read_text()
        self.assertIn("status: frozen (in prose)", text)
        self.assertEqual(1, text.count("status: frozen\n"))

    def test_errors_on_a_file_without_frontmatter_rather_than_creating_one(self):
        f = self.write("# Just a document\n\nNo frontmatter here.\n")
        original = f.read_text()
        result = self.fm_set_many(f, "anchor_commit=abc123")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(original, f.read_text())

    def test_idempotent_second_call_is_byte_identical(self):
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        r1 = self.fm_set_many(f, "anchor_commit=abc123", "anchor_ack=asserted")
        self.assertEqual(0, r1.returncode, r1.stderr)
        first = f.read_text()
        r2 = self.fm_set_many(f, "anchor_commit=abc123", "anchor_ack=asserted")
        self.assertEqual(0, r2.returncode, r2.stderr)
        second = f.read_text()
        self.assertEqual(first, second)

    def test_preserves_file_permissions(self):
        f = self.write("---\nphase: P3\nstatus: draft\n---\nBody.\n")
        os.chmod(f, 0o644)
        result = self.fm_set_many(f, "anchor_commit=abc123")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0o644, stat.S_IMODE(f.stat().st_mode))


class AnchorTestBase(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path(tempfile.mkdtemp(prefix="ccpr-anchor-"))
        self.addCleanup(shutil.rmtree, self.project_dir, ignore_errors=True)
        self.docs_dir = self.project_dir / "docs"
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@host.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@host.invalid",
        }

    # -- filesystem helpers --------------------------------------------

    def write(self, rel_path, text):
        """rel_path is relative to project_dir, e.g. 'docs/architecture/ARCHITECTURE.md'."""
        path = self.project_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_index(self, folder, index_name, **fm_kwargs):
        return self.write(f"docs/{folder}/{index_name}", doc_text(**fm_kwargs))

    # -- git helpers ------------------------------------------------------

    def init_repo(self):
        subprocess.run(["git", "init", "-q"], cwd=self.project_dir, check=True, env=self.env)

    def commit(self, message="commit"):
        subprocess.run(["git", "add", "-A"], cwd=self.project_dir, check=True, env=self.env)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=self.project_dir,
                        check=True, env=self.env)
        return self.head()

    def head(self):
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project_dir, check=True,
            capture_output=True, text=True, env=self.env,
        ).stdout.strip()

    def commit_date(self, sha):
        """Same format anchor.sh itself uses for anchor_date -- avoids
        hard-coding 'today' in a test, since the test env sets no
        GIT_AUTHOR_DATE and the real commit date is whatever the host
        clock was at commit() time."""
        return subprocess.run(
            ["git", "show", "-s", "--format=%ad", "--date=format:%d.%m.%Y", sha],
            cwd=self.project_dir, check=True,
            capture_output=True, text=True, env=self.env,
        ).stdout.strip()

    # -- script invocation --------------------------------------------------

    def run_anchor(self, *args, cwd=None):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), *args],
            capture_output=True, text=True, env=self.env, cwd=cwd,
        )


class DispatchTest(AnchorTestBase):
    """Subcommand dispatch: status/check/ack/set + the no-arg/unknown case.
    `set` (Part 2) and `ack` (Part 4) are both real as of WI-0021 wave 4b;
    each subcommand's own bad-usage case is validated the same way --  in
    the parser, before require_git_repo ever runs -- so none of these
    dispatch-level checks need a repository."""

    def test_no_subcommand_prints_usage_and_exits_2(self):
        result = self.run_anchor()
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stdout)

    def test_unknown_subcommand_exits_2(self):
        result = self.run_anchor("frobnicate")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown subcommand", result.stderr)

    def test_set_without_scope_exits_2_and_needs_no_repository(self):
        result = self.run_anchor("set", str(self.project_dir))
        self.assertEqual(result.returncode, 2)
        self.assertIn("--scope", result.stderr)

    def test_ack_without_target_exits_2_and_needs_no_repository(self):
        result = self.run_anchor("ack", cwd=str(self.project_dir))
        self.assertEqual(result.returncode, 2)
        self.assertIn("target", result.stderr)

    def test_ack_with_assert_and_update_together_exits_2_and_needs_no_repository(self):
        result = self.run_anchor("ack", "docs/architecture/ARCHITECTURE.md",
                                  "--assert", "--update", "--note", "x",
                                  cwd=str(self.project_dir))
        self.assertEqual(result.returncode, 2)
        self.assertIn("mutually exclusive", result.stderr)

    def test_ack_with_assert_but_no_note_exits_2_and_needs_no_repository(self):
        result = self.run_anchor("ack", "docs/architecture/ARCHITECTURE.md",
                                  "--assert", cwd=str(self.project_dir))
        self.assertEqual(result.returncode, 2)
        self.assertIn("--note", result.stderr)


class OperationalErrorsTest(AnchorTestBase):
    """The six-ish operational preconditions that must exit 2 with a clear
    message, for BOTH status and check -- never a Stage-1 report."""

    def test_status_on_non_git_directory_exits_2(self):
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 2)
        self.assertIn("not a git repository", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_check_on_non_git_directory_exits_2(self):
        result = self.run_anchor("check", str(self.project_dir))
        self.assertEqual(result.returncode, 2)
        self.assertIn("not a git repository", result.stderr)

    def test_status_on_git_repo_without_docs_exits_2(self):
        self.init_repo()
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 2)
        self.assertIn("no docs/", result.stderr)

    def test_check_on_git_repo_without_docs_exits_2(self):
        self.init_repo()
        result = self.run_anchor("check", str(self.project_dir))
        self.assertEqual(result.returncode, 2)
        self.assertIn("no docs/", result.stderr)

    def test_check_unknown_argument_exits_2(self):
        self.init_repo()
        (self.docs_dir).mkdir()
        result = self.run_anchor("check", str(self.project_dir), "--bogus")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown argument", result.stderr)

    def test_status_unknown_argument_exits_2(self):
        self.init_repo()
        (self.docs_dir).mkdir()
        result = self.run_anchor("status", str(self.project_dir), "--bogus")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown argument", result.stderr)

    def test_status_rejects_scope_flag_not_documented_for_it(self):
        self.init_repo()
        (self.docs_dir).mkdir()
        result = self.run_anchor("status", str(self.project_dir), "--scope", "architecture")
        self.assertEqual(result.returncode, 2)

    def test_repository_with_no_commits_does_not_crash(self):
        self.init_repo()
        self.docs_dir.mkdir()
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("repository has no commits yet", result.stdout)

    def test_check_operational_errors_never_print_a_stage1_report(self):
        """An operational failure must not ALSO emit a '# Anchor ... Report'
        heading -- the two are mutually exclusive outcomes. Covers BOTH
        subcommands, per the class docstring and this test's own name --
        until the 21.08.2026 review (Punkt 4) it only ever drove `status`,
        so the `check` half of the contract had zero coverage."""
        status_result = self.run_anchor("status", str(self.project_dir))
        self.assertNotIn("# Anchor", status_result.stdout)

        check_result = self.run_anchor("check", str(self.project_dir))
        self.assertNotIn("# Anchor", check_result.stdout)


class NotVerifiedScopeTest(AnchorTestBase):
    """ADR-0009: a scope with no index, or an index with no anchor_commit,
    is 'not verified' -- neither pass nor fail, and never silent."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        self.write("README.md", "seed\n")
        self.commit("seed")

    def test_missing_phase_index_is_reported_not_verified(self):
        self.docs_dir.mkdir()
        (self.docs_dir / "architecture").mkdir()
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("architecture", result.stdout)
        self.assertIn("not verified", result.stdout)
        self.assertIn("no phase index", result.stdout)

    def test_index_without_anchor_commit_is_reported_not_verified(self):
        self.write_index("architecture", "ARCHITECTURE.md")
        self.commit("index")
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not verified", result.stdout)
        self.assertIn("no anchor_commit", result.stdout)

    def test_folder_without_any_docs_produces_no_scope_line(self):
        """A phase folder that does not exist at all under docs/ (e.g. a
        project that never reached that phase) must not appear in the
        report -- distinct from a folder that exists but lacks an index."""
        self.docs_dir.mkdir()
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("architecture", result.stdout)

    def test_reviews_folder_is_never_part_of_the_anchor_scope(self):
        """reviews/ has no phase index by convention (ADR-0009) and must
        never appear as a scope line, unlike phase-docs-lint.sh which gives
        it its own restricted lint profile."""
        self.write("docs/reviews/2026-08-18-sprint.md", "kind: review\n")
        self.commit("review report")
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("reviews", result.stdout)

    def test_zero_anchored_scopes_report_the_statistics_line_as_zero(self):
        self.docs_dir.mkdir()
        result = self.run_anchor("status", str(self.project_dir))
        self.assertIn("0 anchored", result.stdout)
        self.assertIn("0 asserted without doc change", result.stdout)
        self.assertIn("0 stale", result.stdout)

    def test_anchored_index_with_commits_but_none_touching_code_is_not_verified(self):
        """The repository HAS commits (the seed one from setUp), so this is
        distinct from the "no commits at all" case -- but the anchor points
        at that seed commit and nothing production-code-shaped was ever
        committed, so find_last_prod_commit() finds nothing. Neither pass
        nor fail, same as a missing index."""
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.head()}", "anchor_date: 18.08.2026"])
        self.commit("anchor a docs-only repository")

        result = self.run_anchor("status", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no production-code commit found", result.stdout)


class IndexlessScopeOwnAnchorTest(AnchorTestBase):
    """Befund 1 (WI-0021 review, 21.08.2026): report_scope_check() and
    report_scope_status_line() used to exit with 'not verified -- no phase
    index' BEFORE scope_documents() ever ran, so a document carrying its
    OWN anchor_commit was never resolved even though
    doc_effective_anchor()'s own-anchor branch could have done it.
    Reproduced against the shape all three reference projects actually
    have: docs/quality/ exists, QA.md (the index) does not."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/x.go", "package x\n")
        self.commit("seed code")
        self.anchor_sha = self.head()
        self.write("docs/quality/AUDIT.md", doc_text(
            subskill="audit", status="active",
            extra_lines=[f"anchor_commit: {self.anchor_sha}",
                         "anchor_date: 18.08.2026", "covers:", "  - src/"],
        ))
        self.commit("add audit doc with its own anchor, no phase index")
        self.write("src/x.go", "package x\n\nfunc Y() {}\n")
        self.commit("drift the covered code")

    def test_status_counts_the_own_anchored_document_despite_missing_index(self):
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 anchored", result.stdout)
        self.assertIn("1 stale", result.stdout)

    def test_status_still_reports_the_scope_itself_as_not_verified(self):
        """The scope-level line (no index) and the document's own
        resolution are independent -- fixing one must not silence the
        other."""
        result = self.run_anchor("status", str(self.project_dir))
        self.assertIn("not verified", result.stdout)
        self.assertIn("no phase index", result.stdout)

    def test_check_reports_the_own_anchored_documents_drift(self):
        result = self.run_anchor("check", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("docs/quality/AUDIT.md", result.stdout)
        self.assertIn("src/x.go", result.stdout)

    def test_check_lists_the_own_anchored_document_as_affected(self):
        result = self.run_anchor("check", str(self.project_dir))
        self.assertIn("docs/quality/AUDIT.md — status: active", result.stdout)


class ScopesFoundHeaderTest(AnchorTestBase):
    """Befund 2 (WI-0021 review, 21.08.2026): 'zero scopes checked' and
    'eight scopes checked, all clean' used to print the identical
    '0 anchored / 0 stale' summary line -- a report that does not name its
    own scan scope is indistinguishable from a report that found nothing
    to scan."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        self.write("README.md", "seed\n")
        self.commit("seed")

    def test_status_reports_zero_of_eight_when_no_phase_folder_exists(self):
        self.docs_dir.mkdir()
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Scopes found:", result.stdout)
        self.assertIn("0 of 8", result.stdout)

    def test_status_reports_the_real_count_of_existing_phase_folders(self):
        (self.docs_dir / "architecture").mkdir(parents=True)
        (self.docs_dir / "concept").mkdir(parents=True)
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2 of 8", result.stdout)

    def test_check_reports_zero_of_eight_when_no_phase_folder_exists(self):
        self.docs_dir.mkdir()
        result = self.run_anchor("check", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Scopes found:", result.stdout)
        self.assertIn("0 of 8", result.stdout)

    def test_check_with_scope_flag_reports_the_restricted_count(self):
        (self.docs_dir / "concept").mkdir(parents=True)
        result = self.run_anchor("check", str(self.project_dir), "--scope", "concept")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 of 1", result.stdout)

    def test_check_with_scope_flag_for_a_missing_folder_reports_zero_of_one(self):
        (self.docs_dir / "architecture").mkdir(parents=True)
        result = self.run_anchor("check", str(self.project_dir), "--scope", "concept")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0 of 1", result.stdout)


class StatusCommitDistanceTest(AnchorTestBase):
    """The `status` report's per-scope line must name the commit DISTANCE
    between the anchor and the last production-code commit, not just
    whether a delta exists (the work item names this explicitly:
    "Anker-SHA, Anker-Datum, letzter Produktivcode-Commit, Abstand in
    Commits, und ob ein Delta existiert")."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.commit("seed code")
        self.anchor_sha = self.head()
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.anchor_sha}",
                                       "anchor_date: 18.08.2026"])
        self.commit("anchor the index")

    def test_zero_commits_behind_when_anchor_is_the_last_prod_commit(self):
        result = self.run_anchor("status", str(self.project_dir))
        self.assertIn("0 commit(s) behind", result.stdout)

    def test_distance_is_the_raw_commit_count_between_anchor_and_last_prod_commit(self):
        """Deliberately UNFILTERED: `rev-list --count anchor..last-prod`
        counts every commit in that range (the "anchor the index" commit
        from setUp included), not just production-touching ones -- that raw
        count is what "Abstand in Commits" names, distinct from the
        content-filtered delta reported alongside it. A commit added AFTER
        the last production-code commit (the docs-only one here) must NOT
        be counted -- it lies outside the anchor..last-prod range."""
        self.write("src/a.go", "package a\n\nfunc E() {}\n")
        self.commit("one production commit")
        self.write("docs/architecture/NOTES.md", "# notes\n")
        self.commit("one docs-only commit after the last production commit")

        result = self.run_anchor("status", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        # "anchor the index" (setUp) + "one production commit" = 2, the
        # trailing docs-only commit does not add a third.
        self.assertIn("2 commit(s) behind", result.stdout)


class AnchorInheritanceTest(AnchorTestBase):
    """ADR-0009 Addendum 2: a document inherits the phase index's anchor
    unless it carries its own anchor_commit. No third tier."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.commit("seed code")
        self.seed_sha = self.head()
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.seed_sha}",
                                       "anchor_date: 18.08.2026"])
        self.commit("anchor the index")

    def test_document_without_own_anchor_is_counted_via_the_index(self):
        self.write("docs/architecture/AUTH.md", doc_text(subskill="auth", status="active"))
        self.commit("add auth doc")
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        # ARCHITECTURE.md (the index itself) + AUTH.md, both anchored via
        # the same index anchor.
        self.assertIn("2 anchored", result.stdout)

    def test_document_with_own_anchor_commit_overrides_the_index(self):
        """Drift the INDEX's anchor (a code change after it), then add
        AUTH.md with its OWN anchor set to that same later commit -- so
        AUTH.md's own anchor has zero drift even though the index's does.
        Observable via `status`'s per-document stale count: if resolution
        ignored the own anchor and fell back to the (stale) index anchor
        for every document, both documents would count as stale."""
        (self.project_dir / "other").mkdir()
        self.write("other/b.txt", "x\n")
        self.commit("drift the index's anchor")
        own_sha = self.head()
        self.write("docs/architecture/AUTH.md", doc_text(
            subskill="auth", status="active",
            extra_lines=[f"anchor_commit: {own_sha}", "anchor_date: 20.08.2026", "covers:", "  - other/"],
        ))
        self.commit("add auth doc anchored to the current commit")

        result = self.run_anchor("status", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        # ARCHITECTURE.md (index-anchored, stale) + AUTH.md (2 anchored),
        # but only ARCHITECTURE.md is stale -- AUTH.md's own anchor is
        # already at the last production-code commit.
        self.assertIn("2 anchored", result.stdout)
        self.assertIn("1 stale", result.stdout)


class CheckDeltaReportTest(AnchorTestBase):
    """The `check` report: changed production-code paths, claimed vs.
    unclaimed, per-document affected status -- data only, never a verdict."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.commit("seed code")
        self.anchor_sha = self.head()
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.anchor_sha}",
                                       "anchor_date: 18.08.2026"])
        self.write("docs/architecture/AUTH.md", doc_text(
            subskill="auth", status="active", extra_lines=["covers:", "  - src/"],
        ))
        self.commit("anchor + auth doc")

    def test_no_delta_is_reported_explicitly(self):
        result = self.run_anchor("check", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("none — no delta", result.stdout)

    def test_changed_production_path_claimed_by_covers_is_attributed(self):
        self.write("src/a.go", "package a\n\nfunc B() {}\n")
        self.commit("change code")

        result = self.run_anchor("check", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("src/a.go", result.stdout)
        self.assertIn("claimed by docs/architecture/AUTH.md", result.stdout)

    def test_changed_production_path_with_no_claiming_document_is_unclaimed(self):
        (self.project_dir / "other").mkdir()
        self.write("other/b.txt", "y\n")
        self.commit("unrelated code change")

        result = self.run_anchor("check", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("other/b.txt", result.stdout)
        self.assertIn("other/b.txt — unclaimed", result.stdout)

    def test_docs_only_commit_produces_no_delta(self):
        """A third of real-world commits touch documentation only (ADR-0009)
        -- one here must not be read as drift."""
        self.write("docs/architecture/NOTES.md", "# notes\n")
        self.commit("docs only")

        result = self.run_anchor("check", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("none — no delta", result.stdout)

    def test_document_without_covers_is_affected_by_any_scope_delta(self):
        """ARCHITECTURE.md itself carries no covers: -- per ADR-0009 §3 it
        inherits the WHOLE scope's delta rather than claiming nothing."""
        self.write("src/a.go", "package a\n\nfunc C() {}\n")
        self.commit("change code again")

        result = self.run_anchor("check", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("docs/architecture/ARCHITECTURE.md — status:", result.stdout)

    def test_scope_filter_restricts_the_report_to_one_folder(self):
        self.write_index("concept", "CONCEPT.md",
                          extra_lines=[f"anchor_commit: {self.anchor_sha}",
                                       "anchor_date: 18.08.2026"])
        self.commit("add concept index too")

        result = self.run_anchor("check", str(self.project_dir), "--scope", "concept")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("## concept", result.stdout)
        self.assertNotIn("## architecture", result.stdout)

    def test_report_always_names_the_active_classification(self):
        result = self.run_anchor("check", str(self.project_dir))
        self.assertIn("**Classification:**", result.stdout)
        self.assertIn("source: default", result.stdout)


class OwnAnchorPrecedenceInCheckTest(AnchorTestBase):
    """Befund 3 (WI-0021 review, 21.08.2026), decided: `check` must respect
    the same own-anchor-before-index precedence `status` already applies
    (ADR-0009 Addendum 2). A document with an up-to-date OWN anchor has no
    drift and must not be reported as affected, even though the scope's
    INDEX anchor is older and DOES show drift for that same path."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        (self.project_dir / "other").mkdir()
        self.write("other/a.txt", "seed\n")
        self.commit("seed code")
        self.old_sha = self.head()
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.old_sha}",
                                       "anchor_date: 18.08.2026"])
        self.commit("anchor the index (will go stale)")
        self.write("other/a.txt", "seed\n\n// changed\n")
        self.commit("change the covered path")
        current_sha = self.head()
        self.write("docs/architecture/AUTH.md", doc_text(
            subskill="auth", status="active",
            extra_lines=[f"anchor_commit: {current_sha}", "anchor_date: 20.08.2026",
                         "covers:", "  - other/"],
        ))
        self.commit("add auth doc anchored to the already-changed commit")

    def test_document_with_a_current_own_anchor_is_not_reported_as_affected(self):
        result = self.run_anchor("check", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("docs/architecture/AUTH.md — status:", result.stdout)

    def test_the_index_inherited_document_is_still_reported_as_affected(self):
        """ARCHITECTURE.md itself carries no covers: and inherits the
        INDEX's (stale) anchor -- the fix narrows AUTH.md's case, it must
        not also swallow the ordinary index-inherited case."""
        result = self.run_anchor("check", str(self.project_dir))
        self.assertIn("docs/architecture/ARCHITECTURE.md — status:", result.stdout)

    def test_the_reports_own_anchor_section_shows_no_delta_for_it(self):
        """AUTH.md's OWN anchor already sits at the last production-code
        commit -- its delta must read empty, distinct from the index's
        (which does show other/a.txt as changed)."""
        result = self.run_anchor("check", str(self.project_dir))
        self.assertIn("docs/architecture/AUTH.md", result.stdout)
        self.assertIn("no delta", result.stdout)


class MultipleClaimantsTest(AnchorTestBase):
    """Punkt 3 (WI-0021 review, 21.08.2026): two documents whose covers:
    lists overlap on the same changed path must BOTH be reported as
    claimants -- 'first document wins' silently drops the second, which
    works against covers: only ever REFINING the scope signal (ADR-0009
    §3), never quietly narrowing who is on the hook for a path."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.commit("seed code")
        self.anchor_sha = self.head()
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.anchor_sha}",
                                       "anchor_date: 18.08.2026"])
        self.write("docs/architecture/AUTH.md", doc_text(
            subskill="auth", status="active", extra_lines=["covers:", "  - src/"],
        ))
        self.write("docs/architecture/API.md", doc_text(
            subskill="api", status="active", extra_lines=["covers:", "  - src/"],
        ))
        self.commit("anchor + two overlapping covers documents")

    def test_a_path_claimed_by_two_documents_names_both(self):
        self.write("src/a.go", "package a\n\nfunc B() {}\n")
        self.commit("change code")

        result = self.run_anchor("check", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        line = next(l for l in result.stdout.splitlines() if l.startswith("- src/a.go"))
        self.assertIn("docs/architecture/AUTH.md", line)
        self.assertIn("docs/architecture/API.md", line)


class GlobUnsafeProjectDirTest(AnchorTestBase):
    """Punkt 1 (WI-0021 review, 21.08.2026): PROJECT_DIR used to be
    interpolated UNQUOTED into a Bash pattern-removal
    (`${doc#$PROJECT_DIR/}`), so it was parsed as a glob rather than a
    literal string. A project path containing a glob metacharacter (here:
    '[1]', valid on every POSIX filesystem) used to fail to strip at all,
    reproduced directly at the terminal before this test was written."""

    def test_project_dir_containing_a_glob_bracket_still_strips_correctly(self):
        base = Path(tempfile.mkdtemp(prefix="ccpr-anchor-glob-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        weird_dir = base / "proj[1]"
        weird_dir.mkdir()
        self.project_dir = weird_dir
        self.docs_dir = weird_dir / "docs"
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.commit("seed code")
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.head()}",
                                       "anchor_date: 18.08.2026"])
        self.write("docs/architecture/AUTH.md", doc_text(
            subskill="auth", status="active", extra_lines=["covers:", "  - src/"],
        ))
        self.commit("anchor + auth doc")
        self.write("src/a.go", "package a\n\nfunc B() {}\n")
        self.commit("change code")

        result = self.run_anchor("check", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("claimed by docs/architecture/AUTH.md", result.stdout)


class SetDashEExitSafetyTest(AnchorTestBase):
    """Punkt 2 (WI-0021 review, 21.08.2026): report_scope_check() used to
    end on a bare `[[ "$any_affected" == "0" ]] && echo "_none_"` list. A
    bare `cond && cmd` list's own exit status is the exit status of the
    LAST command that actually ran -- when cond is FALSE, that is `[[ ]]`
    itself (exit 1), not `echo`. So the crash case is the opposite of "no
    affected documents": it fires whenever at least one document IS
    reported affected (any_affected="1"), the exact shape that already
    crashed report_scope_status_line() once under `set -e` earlier in this
    work item (see that function's own comment). Pinned by making
    'operations' -- the LAST entry in PHASE_SCOPES -- the only scope, with
    a real delta and its index document (no covers:, so it automatically
    inherits the whole delta per ADR-0009 §3) reported affected -- the
    vulnerable branch is the very last thing the script executes."""

    def test_an_affected_document_in_the_last_scope_still_exits_0(self):
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.commit("seed code")
        self.write_index("operations", "OPERATIONS.md",
                          extra_lines=[f"anchor_commit: {self.head()}",
                                       "anchor_date: 18.08.2026"])
        self.commit("anchor operations")
        self.write("src/a.go", "package a\n\nfunc B() {}\n")
        self.commit("drift the code -- OPERATIONS.md carries no covers:, "
                     "so it inherits the whole delta and IS affected")

        result = self.run_anchor("check", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("docs/operations/OPERATIONS.md — status:", result.stdout)
        self.assertIn("**Exit:** 0", result.stdout)


class ClassificationConfigTest(AnchorTestBase):
    """ADR-0009 'the comparison point, measured': exclusion-based default
    (docs/, .claude/, *.md), configurable per project."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        self.write("README.md", "seed\n")
        self.commit("seed")

    def test_default_classification_excludes_docs_and_claude_and_md(self):
        (self.project_dir / "docs" / "architecture").mkdir(parents=True)
        self.write(".claude/settings.json", "not read without anchor.excludePaths")
        result = self.run_anchor("status", str(self.project_dir))
        self.assertIn("exclude prefixes: docs/,.claude/", result.stdout)
        self.assertIn("exclude suffixes: .md", result.stdout)
        self.assertIn("source: default", result.stdout)

    def test_project_settings_extend_the_default_exclusion(self):
        self.write(".claude/settings.json",
                    '{"anchor": {"excludePaths": ["vendor/", "*.gen.go"]}}')
        (self.project_dir / "docs" / "architecture").mkdir(parents=True)
        result = self.run_anchor("status", str(self.project_dir))
        classification_line = next(
            line for line in result.stdout.splitlines() if line.startswith("**Classification:**")
        )
        self.assertIn("vendor/", classification_line)
        self.assertIn(".gen.go", classification_line)
        # the default stays present -- extension, not replacement. Checked
        # on the CLASSIFICATION line specifically: "docs/" also occurs,
        # unrelated to classification, inside the "not verified (no phase
        # index: docs/architecture/...)" scope line below it, which would
        # make a whole-output substring check pass even if the config
        # REPLACED the default instead of extending it.
        self.assertIn("docs/", classification_line)
        self.assertIn(".claude/", classification_line)
        self.assertIn(".md", classification_line)
        self.assertIn("source: project (.claude/settings.json)", classification_line)

    def test_vendor_excluded_path_is_not_counted_as_production_code(self):
        self.write(".claude/settings.json", '{"anchor": {"excludePaths": ["vendor/"]}}')
        self.write("vendor/dep.go", "package dep\n")
        self.commit("add vendored dep")
        (self.project_dir / "docs" / "architecture").mkdir(parents=True)
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.head()}",
                                       "anchor_date: 18.08.2026"])
        self.commit("index")
        self.write("vendor/dep.go", "package dep\n\n// changed\n")
        self.commit("change vendored dep only")

        result = self.run_anchor("check", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("**Last production-code commit:** none found", result.stdout)

    def test_malformed_settings_json_falls_back_to_default(self):
        self.write(".claude/settings.json", "{not valid json")
        (self.project_dir / "docs" / "architecture").mkdir(parents=True)
        result = self.run_anchor("status", str(self.project_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("source: default", result.stdout)

    def test_missing_settings_json_falls_back_to_default(self):
        (self.project_dir / "docs" / "architecture").mkdir(parents=True)
        result = self.run_anchor("status", str(self.project_dir))
        self.assertIn("source: default", result.stdout)

    def test_missing_python3_on_path_falls_back_to_default(self):
        """'Fehlt ... python3, gilt der Default' -- reproduced with a
        minimal PATH sandbox that has every tool anchor.sh needs EXCEPT
        python3, so this exercises the real `command -v python3` guard
        rather than assuming it works from reading the code."""
        self.write(".claude/settings.json",
                    '{"anchor": {"excludePaths": ["vendor/"]}}')
        (self.project_dir / "docs" / "architecture").mkdir(parents=True)

        sandbox = Path(tempfile.mkdtemp(prefix="ccpr-anchor-path-sandbox-"))
        self.addCleanup(shutil.rmtree, sandbox, ignore_errors=True)
        needed_tools = ("bash", "git", "awk", "sed", "find", "sort", "date",
                         "dirname", "basename", "cat", "head", "grep", "env")
        for tool in needed_tools:
            resolved = shutil.which(tool)
            if resolved:
                os.symlink(resolved, sandbox / tool)

        env = dict(self.env)
        env["PATH"] = str(sandbox)
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), "status", str(self.project_dir)],
            capture_output=True, text=True, env=env,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("source: default", result.stdout)
        self.assertNotIn("vendor/", result.stdout)


class GitEdgeCaseTest(AnchorTestBase):
    """The six git edge cases named in the work item: shallow clone,
    detached HEAD, dirty tree, no commits, unresolvable anchor, and the
    `.git`-is-a-file worktree/submodule shape."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.commit("seed code")
        self.anchor_sha = self.head()
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.anchor_sha}",
                                       "anchor_date: 18.08.2026"])
        self.commit("anchor the index")

    def test_shallow_clone_reports_cannot_compare_not_no_delta(self):
        clone_dir = Path(tempfile.mkdtemp(prefix="ccpr-anchor-shallow-"))
        self.addCleanup(shutil.rmtree, clone_dir, ignore_errors=True)
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", f"file://{self.project_dir}", str(clone_dir)],
            check=True, env=self.env,
        )

        result = self.run_anchor("status", str(clone_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cannot compare (shallow clone)", result.stdout)
        self.assertNotIn("delta: no", result.stdout)

    def test_shallow_clone_still_finds_the_last_production_code_commit(self):
        """Regression pin for the `--pretty=format:%H` trailing-newline
        defect found while building this: a single-commit `git log`
        (exactly what --depth 1 produces) used to be silently skipped by
        `while read`, reporting 'none found' even though the one commit
        present clearly touches production code."""
        clone_dir = Path(tempfile.mkdtemp(prefix="ccpr-anchor-shallow2-"))
        self.addCleanup(shutil.rmtree, clone_dir, ignore_errors=True)
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", f"file://{self.project_dir}", str(clone_dir)],
            check=True, env=self.env,
        )

        result = self.run_anchor("status", str(clone_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Last production-code commit:** none found", result.stdout)

    def test_unresolvable_anchor_is_reported_not_as_clean(self):
        self.write_index("concept", "CONCEPT.md",
                          extra_lines=["anchor_commit: deadbeefdeadbeef",
                                       "anchor_date: 18.08.2026"])
        self.commit("bogus anchor")

        result = self.run_anchor("status", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("anchor does not resolve", result.stdout)

    def test_detached_head_works(self):
        # Detach onto the current HEAD itself (the commit that already has
        # docs/architecture/ARCHITECTURE.md) -- detaching onto the earlier
        # seed commit would also strip docs/ from the working tree, which
        # would test "no docs/" rather than "detached HEAD".
        current = self.head()
        subprocess.run(["git", "checkout", "-q", "--detach", current],
                        cwd=self.project_dir, check=True, env=self.env)
        symbolic = subprocess.run(
            ["git", "symbolic-ref", "-q", "HEAD"], cwd=self.project_dir, env=self.env,
            capture_output=True,
        )
        self.assertNotEqual(symbolic.returncode, 0, "test setup assumption broken: HEAD must be detached")

        result = self.run_anchor("status", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Anchor Status Report", result.stdout)

    def test_dirty_working_tree_is_noted(self):
        self.write("src/a.go", "package a\n\n// uncommitted\n")

        result = self.run_anchor("status", str(self.project_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("uncommitted changes", result.stdout)

    def test_clean_working_tree_prints_no_dirty_note(self):
        result = self.run_anchor("status", str(self.project_dir))
        self.assertNotIn("uncommitted changes", result.stdout)

    def test_worktree_git_file_is_still_recognised_as_a_repository(self):
        """A linked worktree's `.git` is a FILE (`gitdir: ...`), not a
        directory -- the exact shape phase-docs-lint.sh's GIT_CHECKABLE
        guard once missed (`-d` instead of `-e`). Reproduced here directly
        rather than assumed from reading the guard."""
        worktree_dir = Path(tempfile.mkdtemp(prefix="ccpr-anchor-wt-"))
        shutil.rmtree(worktree_dir)  # git worktree add requires a fresh path
        self.addCleanup(lambda: subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_dir)],
            cwd=self.project_dir, env=self.env, capture_output=True,
        ))
        self.addCleanup(shutil.rmtree, worktree_dir, ignore_errors=True)
        subprocess.run(
            ["git", "worktree", "add", "-q", str(worktree_dir), "-b", "wt-branch"],
            cwd=self.project_dir, check=True, env=self.env,
        )
        self.assertTrue((worktree_dir / ".git").is_file(),
                         "test setup assumption broken: a linked worktree's .git "
                         "must be a file, not a directory")

        result = self.run_anchor("status", str(worktree_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Anchor Status Report", result.stdout)


class AckStatisticsTest(AnchorTestBase):
    """The 'X anchored · Y asserted without doc change · Z stale' line ADR-0009
    requires in EVERY run. anchor_ack does not exist as a writable command
    until wave 4b, but the read side must already count it correctly when
    the field is present (hand-authored here, exactly as `anchor ack` will
    write it later)."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.commit("seed code")
        self.anchor_sha = self.head()
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.anchor_sha}",
                                       "anchor_date: 18.08.2026"])
        self.commit("anchor the index")
        self.write("src/a.go", "package a\n\nfunc D() {}\n")
        self.commit("drift the code")

    def test_undocumented_drift_is_counted_stale(self):
        result = self.run_anchor("status", str(self.project_dir))
        self.assertIn("1 anchored", result.stdout)
        self.assertIn("0 asserted without doc change", result.stdout)
        self.assertIn("1 stale", result.stdout)

    def test_asserted_ack_moves_the_document_out_of_stale(self):
        self.write("docs/architecture/ARCHITECTURE.md", doc_text(
            extra_lines=[f"anchor_commit: {self.anchor_sha}", "anchor_date: 18.08.2026",
                         "anchor_ack: asserted"],
        ))
        self.commit("assert the drift is fine")

        result = self.run_anchor("status", str(self.project_dir))

        self.assertIn("1 anchored", result.stdout)
        self.assertIn("1 asserted without doc change", result.stdout)
        self.assertIn("0 stale", result.stdout)

    def test_updated_ack_moves_the_document_out_of_stale_and_asserted(self):
        self.write("docs/architecture/ARCHITECTURE.md", doc_text(
            extra_lines=[f"anchor_commit: {self.anchor_sha}", "anchor_date: 18.08.2026",
                         "anchor_ack: updated"],
        ))
        self.commit("mark the doc as brought in line")

        result = self.run_anchor("status", str(self.project_dir))

        self.assertIn("1 anchored", result.stdout)
        self.assertIn("0 asserted without doc change", result.stdout)
        self.assertIn("0 stale", result.stdout)


class SetCommandTest(AnchorTestBase):
    """`anchor set` (WI-0021 wave 4b, ADR-0009 Addendum 2): writes
    anchor_commit/anchor_date onto the phase index of a --scope. Refuses
    to overwrite an existing anchor without --force -- a silent overwrite
    would discard drift nobody has reviewed, which ADR-0009 SS6 names as
    the single riskiest detail in the whole design (stated there for
    `ack`, applies here to a bare overwrite just the same)."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.prod_sha = self.commit("seed code")
        self.write_index("architecture", "ARCHITECTURE.md")
        self.commit("add architecture index")

    def _index_text(self):
        return (self.project_dir / "docs/architecture/ARCHITECTURE.md").read_text()

    def _anchor_commit(self):
        m = re.search(r"^anchor_commit:\s*(\S+)", self._index_text(), re.MULTILINE)
        return m.group(1) if m else None

    def _anchor_date(self):
        m = re.search(r"^anchor_date:\s*(\S+)", self._index_text(), re.MULTILINE)
        return m.group(1) if m else None

    def test_set_without_commit_uses_the_last_production_code_commit_not_head(self):
        self.write("docs/README.md", "docs-only change\n")
        self.commit("docs-only commit, HEAD moves past the code commit")

        result = self.run_anchor("set", str(self.project_dir), "--scope", "architecture")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.prod_sha, self._anchor_commit())
        self.assertNotEqual(self.head(), self._anchor_commit())

    def test_set_writes_the_commits_own_date(self):
        result = self.run_anchor("set", str(self.project_dir), "--scope", "architecture")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.commit_date(self.prod_sha), self._anchor_date())

    def test_set_refuses_when_already_anchored_without_force(self):
        first = self.run_anchor("set", str(self.project_dir), "--scope", "architecture")
        self.assertEqual(0, first.returncode, first.stderr)
        existing = self._anchor_commit()

        self.write("src/a.go", "package a\n\nfunc D() {}\n")
        self.commit("drift the code")

        second = self.run_anchor("set", str(self.project_dir), "--scope", "architecture")

        # Exit code 3, NOT the generic bad-usage 2 (WI-0021 review, small
        # fix #2): freeze-phase-docs.sh's anchor hook needs to tell
        # "already anchored" (its own normal, expected second-run
        # outcome) apart from every OTHER `set` failure without coupling
        # the two scripts through a message-text grep alone.
        self.assertEqual(3, second.returncode)
        self.assertIn("already carries an anchor", second.stderr)
        self.assertEqual(existing, self._anchor_commit())

    def test_set_force_overwrites_an_existing_anchor(self):
        first = self.run_anchor("set", str(self.project_dir), "--scope", "architecture")
        self.assertEqual(0, first.returncode, first.stderr)

        self.write("src/a.go", "package a\n\nfunc D() {}\n")
        new_sha = self.commit("drift the code")

        result = self.run_anchor("set", str(self.project_dir), "--scope", "architecture", "--force")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(new_sha, self._anchor_commit())

    def test_set_with_explicit_commit_overrides_the_last_prod_commit(self):
        self.write("src/b.go", "package a\n\nfunc B() {}\n")
        second_prod_sha = self.commit("second prod commit")

        result = self.run_anchor("set", str(self.project_dir), "--scope", "architecture",
                                  "--commit", self.prod_sha)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.prod_sha, self._anchor_commit())
        self.assertNotEqual(second_prod_sha, self._anchor_commit())

    def test_set_with_unresolvable_commit_exits_2_and_writes_nothing(self):
        result = self.run_anchor("set", str(self.project_dir), "--scope", "architecture",
                                  "--commit", "deadbeef")
        self.assertEqual(2, result.returncode)
        self.assertIn("does not resolve", result.stderr)
        self.assertIsNone(self._anchor_commit())

    def test_set_with_missing_index_exits_2_and_creates_no_file(self):
        result = self.run_anchor("set", str(self.project_dir), "--scope", "quality")
        self.assertEqual(2, result.returncode)
        self.assertIn("no phase index", result.stderr)
        self.assertFalse((self.project_dir / "docs/quality").exists())

    def test_set_with_unknown_scope_exits_2(self):
        result = self.run_anchor("set", str(self.project_dir), "--scope", "bogus")
        self.assertEqual(2, result.returncode)
        self.assertIn("unknown scope", result.stderr)

    def test_set_prints_a_confirmation_naming_the_written_commit(self):
        result = self.run_anchor("set", str(self.project_dir), "--scope", "architecture")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(self.prod_sha, result.stdout)


class AckCommandTest(AnchorTestBase):
    """`anchor ack` (WI-0021 wave 4b, ADR-0009 SS6): renders the delta
    before it clears it, writes the five flat keys, keeps `asserted`
    (human judgement) and `updated` (evidence) apart, and refuses when
    there is no drift to acknowledge or when the target carries no
    anchor of its own -- acknowledgement reach is structural (whichever
    file was passed IS the file that gets acked), never a --scope
    shortcut."""

    def setUp(self):
        super().setUp()
        self.init_repo()
        (self.project_dir / "src").mkdir()
        self.write("src/a.go", "package a\n")
        self.old_sha = self.commit("seed code")
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.old_sha}",
                                       "anchor_date: 18.08.2026"])
        self.commit("anchor the index")
        self.write("src/a.go", "package a\n\nfunc D() {}\n")
        self.new_sha = self.commit("drift the code")

    def run_ack(self, *args, input_text=None, env_extra=None):
        env = self.env
        if env_extra:
            env = {**self.env, **env_extra}
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), "ack", *args],
            input=input_text,
            capture_output=True, text=True, env=env, cwd=str(self.project_dir),
        )

    def run_ack_interactive(self, *args, input_text=None):
        """The two interactive-flow tests below drive `ack` through a
        PIPED stdin (subprocess.run's `input=`), which has no TTY --
        exactly the non-interactive shape the Important-4 TTY guard now
        refuses fast rather than letting `read` hang forever on. The env
        var is a documented, test-only escape hatch (see anchor.sh's own
        comment at the guard) so these tests can still exercise the
        interactive asserted/abort flow without opening a real pty."""
        return self.run_ack(*args, input_text=input_text,
                             env_extra={"CCPR_ANCHOR_FORCE_INTERACTIVE": "1"})

    def run_status(self):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), "status", str(self.project_dir)],
            capture_output=True, text=True, env=self.env,
        )

    def _index_text(self):
        return (self.project_dir / "docs/architecture/ARCHITECTURE.md").read_text()

    def _field(self, key):
        m = re.search(rf"^{key}:\s*(.*)$", self._index_text(), re.MULTILINE)
        return m.group(1).strip() if m else None

    def test_assert_writes_the_five_keys(self):
        result = self.run_ack("docs/architecture/ARCHITECTURE.md", "--assert",
                               "--note", "refactor touched only internals")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.new_sha, self._field("anchor_commit"))
        self.assertEqual(self.old_sha, self._field("anchor_ack_from"))
        self.assertEqual("asserted", self._field("anchor_ack"))
        self.assertEqual("refactor touched only internals", self._field("anchor_ack_note"))
        self.assertIsNotNone(self._field("anchor_date"))

    def test_update_kind_is_distinct_from_assert(self):
        result = self.run_ack("docs/architecture/ARCHITECTURE.md", "--update",
                               "--note", "docs brought in line")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("updated", self._field("anchor_ack"))

    def test_note_is_required_with_assert(self):
        result = self.run_ack("docs/architecture/ARCHITECTURE.md", "--assert")
        self.assertEqual(2, result.returncode)
        self.assertIn("--note", result.stderr)
        self.assertIsNone(self._field("anchor_ack"))

    def test_assert_and_update_are_mutually_exclusive(self):
        result = self.run_ack("docs/architecture/ARCHITECTURE.md", "--assert", "--update",
                               "--note", "x")
        self.assertEqual(2, result.returncode)
        self.assertIn("mutually exclusive", result.stderr)

    def test_refuses_when_there_is_no_drift(self):
        self.write_index("architecture", "ARCHITECTURE.md",
                          extra_lines=[f"anchor_commit: {self.new_sha}",
                                       "anchor_date: 18.08.2026"])
        self.commit("re-anchor to the current commit, no drift now")

        result = self.run_ack("docs/architecture/ARCHITECTURE.md", "--assert", "--note", "x")

        self.assertEqual(2, result.returncode)
        self.assertIn("no drift", result.stderr)

    def test_target_without_its_own_anchor_is_refused(self):
        self.write("docs/architecture/AUTH.md", doc_text(status="active"))
        self.commit("add auth doc, no own anchor")

        result = self.run_ack("docs/architecture/AUTH.md", "--assert", "--note", "x")

        self.assertEqual(2, result.returncode)
        self.assertIn("nothing to acknowledge", result.stderr)

    def test_target_outside_every_phase_scope_is_refused(self):
        """Important 3 (WI-0021 review), reproduced directly:
        resolve_ack_target used to check only that the file exists and
        carries its own `anchor_commit:` -- a document under docs/
        somewhere/ (no phase folder) with an anchor could be acked
        successfully and would then be INVISIBLE to `status`'s
        'X anchored / Y asserted / Z stale' line, because
        scope_documents() only ever walks the eight PHASE_SCOPES folders.
        That statistic is ADR-0009 §6's only fallback detection net in
        the absence of a hard technical block on agents -- a target
        outside the scope silently defeats it completely."""
        self.write("docs/somewhere/NOTE.md", doc_text(
            status="active",
            extra_lines=[f"anchor_commit: {self.old_sha}", "anchor_date: 18.08.2026"],
        ))
        self.commit("add a document outside every phase scope, with its own anchor")

        result = self.run_ack("docs/somewhere/NOTE.md", "--assert", "--note", "x")

        self.assertEqual(2, result.returncode)
        self.assertIn("outside every phase scope", result.stderr)
        self.assertEqual(
            self.old_sha,
            re.search(r"^anchor_commit:\s*(\S+)",
                      (self.project_dir / "docs/somewhere/NOTE.md").read_text(),
                      re.MULTILINE).group(1),
        )

    def test_refuses_fast_instead_of_hanging_when_stdin_is_not_a_terminal(self):
        """Important 4 (WI-0021 review): without --assert/--update and an
        OPEN-but-unfed stdin (a CI job, an agent tool call that never
        redirects stdin), the interactive branch's bare `read` blocks
        forever -- as opposed to a CLOSED pipe, which hits EOF
        immediately and already exits cleanly via the existing
        interactive-abort path (verified separately). `stdin=DEVNULL` is
        not a terminal either (`[[ -t 0 ]]` is false for it, same as any
        pipe or redirected file), so this reproduces the guard firing
        without needing a real hang or a real pty."""
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), "ack", "docs/architecture/ARCHITECTURE.md"],
            stdin=subprocess.DEVNULL,
            capture_output=True, text=True, env=self.env, cwd=str(self.project_dir),
            timeout=10,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("stdin is not a terminal", result.stderr)
        self.assertIsNone(self._field("anchor_ack"))

    def test_renders_the_delta_before_writing(self):
        result = self.run_ack("docs/architecture/ARCHITECTURE.md", "--assert", "--note", "x")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(self.old_sha, result.stdout)
        self.assertIn("src/a.go", result.stdout)

    def test_interactive_asserted_flow_via_stdin(self):
        result = self.run_ack_interactive("docs/architecture/ARCHITECTURE.md",
                                           input_text="asserted\nreason from stdin\n")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("asserted", self._field("anchor_ack"))
        self.assertEqual("reason from stdin", self._field("anchor_ack_note"))

    def test_interactive_abort_writes_nothing(self):
        result = self.run_ack_interactive("docs/architecture/ARCHITECTURE.md", input_text="abort\n")
        self.assertEqual(2, result.returncode)
        self.assertIsNone(self._field("anchor_ack"))
        self.assertEqual(self.old_sha, self._field("anchor_commit"))

    def test_status_counter_moves_from_zero_to_one_after_ack(self):
        before = self.run_status()
        self.assertIn("0 asserted without doc change", before.stdout)

        ack = self.run_ack("docs/architecture/ARCHITECTURE.md", "--assert",
                            "--note", "verified fine")
        self.assertEqual(0, ack.returncode, ack.stderr)

        after = self.run_status()
        self.assertIn("1 asserted without doc change", after.stdout)
