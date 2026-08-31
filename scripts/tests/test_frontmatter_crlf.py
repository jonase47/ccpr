r"""test_frontmatter_crlf.py -- `scripts/lib/frontmatter.sh` against CRLF input.

## The defect this module pins

Every frontmatter marker comparison in the shared library asked for the
string `---` exactly. `awk` splits records on `\n` alone, so on a file with
Windows line endings the opening and closing markers arrive as `---\r` and
no comparison in the library matched them. The whole block therefore read
as ABSENT -- not as malformed, not as an error, simply not there.

Measured on 31.08.2026, before the fix, against a `docs/architecture/
GATE_P3.md` carrying a plain `gate: go` line in a CRLF frontmatter block:

    $ bash scripts/phase-docs-lint.sh <project>
    - docs/architecture/GATE_P3.md -- required field missing: gate
    - docs/architecture/GATE_P3.md -- no YAML frontmatter (--- block ...)

    $ bash scripts/memory-lint.sh <project>
    - docs/memory/project_alpha.md -- no YAML frontmatter (---) at start

    $ bash scripts/freeze-phase-docs.sh P3 <project> --dry-run
    [dry-run] Would freeze 0 file(s).

    $ bash scripts/manual-lint.sh <root>
    0 errors, 0 warnings, 0 info      (on a file whose parent_index points
                                       at a non-existent document and whose
                                       kind: is not in the vocabulary)

Two error directions, both bad and neither loud. The lints raise a FALSE
ALARM about a field the document plainly carries, and the writer plus the
`kind:`/`parent_index:` checks fall SILENT on documents they are supposed
to act on. The `.gitattributes` added in bc87c9f normalises line endings in
THIS repository; it says nothing about an adopter's project tree, which is
where all four of these scripts actually run. (Reference corpus at the time
of writing: 19 CRLF-terminated `.md` files across the consumer projects,
0 in CCPR itself.)

## Five comparison sites, in two mechanisms

`grep -n '"---"' scripts/lib/frontmatter.sh` finds eight lines, and they do
not all break the same way:

  * `fm_has` line 24 is a SHELL string comparison,
    `[[ "$(head -n1 "$file")" == "---" ]]`. No `awk` runs at that point, so
    an `awk`-level `sub(/\r$/, "")` cannot reach it. It gets its own guard
    (`${first%$'\r'}`) and its own test class below,
    `FmHasShellFirstLineGuardTest`.
  * Four `awk` blocks -- `fm_has` (26-27), `fm_extract` (35-36), `fm_set`
    (295-296), `fm_set_many` (393-394) -- break the way WI-0086 already
    documented for `memory-lint.sh:1668`: a record-leading strip is the one
    position that reaches every later comparison, because every later branch
    reads `$0` or a substring of it.

The two READERS (`fm_has`, `fm_extract`) strip the carriage return off `$0`
itself, which is also what keeps `fm_field`, `fm_list` and
`fm_validate_required` correct without a strip of their own: all three
consume `fm_extract`'s output, never the file.

The two WRITERS cannot do that. `fm_set`/`fm_set_many` print `$0` verbatim
for every line they pass through, and their contract says the body is left
byte-for-byte alone -- a strip on `$0` would silently convert the whole
document to LF. They compare against a stripped COPY and remember the
record's own terminator, so a rewritten or inserted key line carries the
same ending as the line it replaced (or as the closing marker it precedes).
`FmSetCrlfTest` and `FmSetManyCrlfTest` pin both halves.

## Why each block gets its own discriminating fixture

A file that is CRLF throughout cannot tell the five sites apart: with only
one of them fixed it stays broken, so a single "a CRLF file works now" test
would pass or fail as a block and prove nothing about coverage. Two mixed
fixtures separate the two `fm_has` mechanisms:

  * opening marker `---\r\n`, closing marker `---\n` -- only line 24 decides
    (the `awk` block matches the LF closer either way).
  * opening marker `---\n`, closing marker `---\r\n` -- only the `awk` block
    decides (line 24 matches the LF opener either way).

Mixed endings inside one file are not the realistic input; they are the
instrument that makes the two sites individually observable. The realistic,
uniformly-CRLF shape is covered too, by `FmHasUniformCrlfTest`.

## Both directions, always

A change that simply stopped comparing markers at all would make every
"CRLF is recognised" test green while turning `fm_has` into a function that
answers yes to anything -- fail-open in the one library that feeds the gate
verdict check. Every class below therefore carries its negative twin: a
CRLF file with no frontmatter, an unclosed CRLF block, a four-dash opener,
a body line that merely looks like the key, a genuinely missing required
field. Those must stay reported after the fix, on CRLF input.

## Fixture bytes are verified, not assumed

`write_crlf()` writes the bytes and then reads them back, asserting three
things: the bytes match what was intended, at least one line is genuinely
CRLF-terminated (via `has_crlf_line_terminator`, reused from
`test_gitattributes_crlf_guard.py` rather than re-implemented), and no bare
LF survives anywhere. `FixtureIntegrityTest` additionally compares one
fixture against a hand-written byte literal, so the helper itself is
checked against something it did not produce.

`run_bash()` deliberately does NOT pass `text=True`. Python's universal-
newline translation rewrites `\r\n` to `\n` in captured output -- it would
erase the exact byte these tests are about, and every CR-preservation
assertion below would pass against a script that had dropped the CR. All
stdout/stderr assertions here are against `bytes`.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from .test_gitattributes_crlf_guard import has_crlf_line_terminator

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
FRONTMATTER_LIB = SCRIPTS_DIR / "lib" / "frontmatter.sh"
PHASE_DOCS_LINT = SCRIPTS_DIR / "phase-docs-lint.sh"
MEMORY_LINT = SCRIPTS_DIR / "memory-lint.sh"
MANUAL_LINT = SCRIPTS_DIR / "manual-lint.sh"
FREEZE_PHASE_DOCS = SCRIPTS_DIR / "freeze-phase-docs.sh"

# Any date of the right shape; none of the checks exercised here reads the
# calendar, and a fixed literal keeps the fixtures reproducible.
FIXTURE_DATE = "31.08.2026"


def crlf_bytes(text):
    """`text` (written with LF separators for readability) as CRLF bytes."""
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


class CrlfFixtureMixin:
    """Byte-verified fixture writing plus a `bash -c` runner that sources
    the shipped library the same way every real caller does."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="ccpr-fm-crlf-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

    def write_bytes(self, relative_path, data):
        """Write raw bytes and read them back before returning."""
        path = self.work / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.assertEqual(data, path.read_bytes(), "fixture did not land as written")
        return path

    def write_crlf(self, relative_path, text):
        """Write `text` with CRLF terminators, then VERIFY the file really
        carries them -- a fixture that only describes CRLF in a Python
        string literal proves nothing about the bytes on disk."""
        data = crlf_bytes(text)
        path = self.write_bytes(relative_path, data)
        self.assertTrue(
            has_crlf_line_terminator(path),
            f"{relative_path} was meant to be a CRLF fixture but carries no CRLF terminator",
        )
        written = path.read_bytes()
        bare_lf = [
            i for i, b in enumerate(written)
            if b == 0x0A and (i == 0 or written[i - 1] != 0x0D)
        ]
        self.assertEqual(
            [], bare_lf,
            f"{relative_path} still has bare LF terminators at byte offsets {bare_lf}",
        )
        return path

    def write_lf(self, relative_path, text):
        data = text.encode("utf-8")
        path = self.write_bytes(relative_path, data)
        self.assertFalse(
            has_crlf_line_terminator(path),
            f"{relative_path} was meant to be the LF control fixture",
        )
        return path

    def run_bash(self, body):
        """Source the shipped library and run `body`. Returns a
        CompletedProcess with BYTES streams -- see the module docstring on
        why `text=True` would defeat the point of this whole module."""
        script = 'set -euo pipefail\nsource "%s"\n%s\n' % (FRONTMATTER_LIB, body)
        return subprocess.run(["bash", "-c", script], capture_output=True)


# --------------------------------------------------------------------------
# The fixture helper itself
# --------------------------------------------------------------------------


class FixtureIntegrityTest(CrlfFixtureMixin, unittest.TestCase):
    """`write_crlf` is the instrument every other test here depends on, so
    it is measured against a hand-written byte literal it did not produce."""

    def test_the_crlf_writer_lands_the_exact_bytes_it_promises(self):
        path = self.write_crlf("probe.md", "---\nname: x\n---\nbody\n")

        self.assertEqual(b"---\r\nname: x\r\n---\r\nbody\r\n", path.read_bytes())

    def test_the_lf_control_fixture_carries_no_crlf_terminator(self):
        path = self.write_lf("probe.md", "---\nname: x\n---\nbody\n")

        self.assertEqual(b"---\nname: x\n---\nbody\n", path.read_bytes())
        self.assertFalse(has_crlf_line_terminator(path))


# --------------------------------------------------------------------------
# fm_has -- the shell comparison at line 24
# --------------------------------------------------------------------------


class FmHasShellFirstLineGuardTest(CrlfFixtureMixin, unittest.TestCase):
    r"""`[[ "$(head -n1 "$file")" == "---" ]]` runs before any `awk` does,
    so the record-leading `sub(/\r$/, "")` that repairs the four `awk`
    blocks cannot reach it. It needs its own guard, and this class is what
    keeps that guard from being dropped: measured 31.08.2026, removing
    `first="${first%$'\r'}"` and leaving all four `awk` strips correct
    (mutation M5) turned 12 tests red, seven of them here and in
    `FmHasUniformCrlfTest`.

    What this class does NOT claim -- an earlier draft of this docstring
    did, and it was wrong: the fixture below (CRLF opener, LF closer) is
    not an ISOLATOR for line 24. `fm_has`'s shell test and its `awk`
    block's `NR==1` test read the SAME physical line, so no fixture can
    break one while leaving the other satisfied. Mutations M1 (the `awk`
    strip moved behind its comparison) and M5 (the shell guard dropped)
    produce byte-identical red sets for exactly that reason. The fixture's
    value is that it is the MINIMAL CRLF exposure -- one carriage return,
    on line 1 -- so both line-1 mechanisms are exercised by a document
    that is otherwise plain LF.
    """

    def test_a_cr_terminated_opening_marker_still_opens_a_block(self):
        path = self.write_bytes("mixed.md", b"---\r\nname: x\n---\nbody\n")

        result = self.run_bash('fm_has "%s"' % path)

        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_four_dash_opener_with_a_carriage_return_is_still_not_frontmatter(self):
        """The guard trims the terminator, not the content: `----\\r` must
        stay a non-match, or the strip has widened what counts as a marker."""
        path = self.write_crlf("four.md", "----\nname: x\n---\nbody\n")

        result = self.run_bash(
            'if fm_has "%s"; then echo OPENED; else echo REFUSED; fi' % path
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"REFUSED\n", result.stdout)

    def test_a_crlf_file_whose_first_line_is_prose_is_still_not_frontmatter(self):
        path = self.write_crlf("prose.md", "# Title\n---\nname: x\n---\nbody\n")

        result = self.run_bash('fm_has "%s"' % path)

        self.assertNotEqual(0, result.returncode)


# --------------------------------------------------------------------------
# fm_has -- the awk block at lines 26-27
# --------------------------------------------------------------------------


class FmHasAwkClosingMarkerTest(CrlfFixtureMixin, unittest.TestCase):
    """Isolating fixture, the mirror image of the class above: the OPENING
    marker is LF and the closing marker is CRLF. Line 24 matches the LF
    opener with or without its guard, so the `awk` block alone decides."""

    def test_a_cr_terminated_closing_marker_closes_the_block(self):
        path = self.write_bytes("mixed.md", b"---\nname: x\r\n---\r\nbody\r\n")

        result = self.run_bash('fm_has "%s"' % path)

        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_crlf_block_that_is_never_closed_is_still_not_frontmatter(self):
        """The fail-open direction. A change that stopped comparing markers
        altogether would pass every test above; this one is what refuses it.
        60 filler lines put the missing closer past the `NR>50` cutoff too."""
        filler = "".join("line %d\n" % i for i in range(60))
        path = self.write_crlf("open.md", "---\nname: x\n" + filler)

        result = self.run_bash('fm_has "%s"' % path)

        self.assertNotEqual(0, result.returncode)


class FmHasUniformCrlfTest(CrlfFixtureMixin, unittest.TestCase):
    """The realistic shape: a document that is CRLF from end to end."""

    def test_a_uniformly_crlf_document_has_frontmatter(self):
        path = self.write_crlf("doc.md", "---\nname: x\ngate: go\n---\n\n# Doc\n\nBody.\n")

        result = self.run_bash('fm_has "%s"' % path)

        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_uniformly_crlf_document_without_a_block_has_no_frontmatter(self):
        path = self.write_crlf("doc.md", "# Doc\n\nBody with a --- in it.\n")

        result = self.run_bash('fm_has "%s"' % path)

        self.assertNotEqual(0, result.returncode)


# --------------------------------------------------------------------------
# fm_extract and the three readers built on it
# --------------------------------------------------------------------------


class FmExtractCrlfTest(CrlfFixtureMixin, unittest.TestCase):
    """`fm_extract`'s own `awk` block (lines 35-36), plus the reason
    `fm_field`, `fm_list` and `fm_validate_required` need no strip of their
    own: they read this function's output, never the file."""

    def write_doc(self):
        return self.write_crlf(
            "doc.md",
            "---\n"
            "phase: P3\n"
            "gate: go\n"
            "related: [alpha.md, beta.md]\n"
            "---\n"
            "\n"
            "# Doc\n"
            "\n"
            "subskill: leaked-from-body\n",
        )

    def test_fm_extract_emits_the_crlf_block_without_carriage_returns(self):
        path = self.write_doc()

        result = self.run_bash('fm_extract "%s"' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            b"phase: P3\ngate: go\nrelated: [alpha.md, beta.md]\n", result.stdout
        )
        self.assertNotIn(b"\r", result.stdout)

    def test_fm_field_reads_a_value_out_of_a_crlf_block(self):
        path = self.write_doc()

        result = self.run_bash('fm_field "%s" gate' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"go\n", result.stdout)

    def test_fm_field_returns_nothing_for_a_key_absent_from_the_whole_file(self):
        path = self.write_doc()

        result = self.run_bash('fm_field "%s" owner' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"", result.stdout)

    def test_fm_field_does_not_reach_past_the_crlf_closing_marker(self):
        """`subskill:` appears ONLY in the fixture's BODY, past the CRLF
        closing marker. A key that also sat in the block would prove nothing
        here: `fm_field` exits on its first match, so the frontmatter hit
        would shadow a leak no matter how far extraction actually ran. This
        assertion is the one that goes red when the closing-marker
        comparison stops being reached (measured: mutation M7, the strip
        narrowed to `NR==1`, leaves every `gate:`-based assertion green)."""
        path = self.write_doc()

        result = self.run_bash('fm_field "%s" subskill' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"", result.stdout)
        self.assertNotIn(b"leaked-from-body", result.stdout)

    def test_fm_list_reads_an_inline_list_out_of_a_crlf_block(self):
        """`fm_list`'s inline branch anchors on `^\\[.*\\]$`. A trailing
        carriage return defeats the `$`, so this shape stays broken even
        when a bare `fm_field` value would survive on a trailing-space trim
        alone."""
        path = self.write_doc()

        result = self.run_bash('fm_list "%s" related' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"alpha.md\nbeta.md\n", result.stdout)

    def test_fm_list_reads_a_block_list_out_of_a_crlf_block(self):
        path = self.write_crlf(
            "block.md",
            "---\nname: x\nrelated:\n  - alpha.md\n  - beta.md\n---\n\nBody.\n",
        )

        result = self.run_bash('fm_list "%s" related' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"alpha.md\nbeta.md\n", result.stdout)

    def test_fm_validate_required_reports_nothing_for_a_complete_crlf_block(self):
        path = self.write_crlf(
            "complete.md",
            "---\nphase: P3\nsubskill: p3-sec\nstatus: draft\n"
            "last_updated: %s\n---\n\nBody.\n" % FIXTURE_DATE,
        )

        result = self.run_bash(
            'fm_validate_required "%s" "phase,subskill,status,last_updated"' % path
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"", result.stdout)

    def test_fm_validate_required_still_names_the_one_field_a_crlf_block_omits(self):
        """The negative direction for the required-field check itself: the
        false alarm has to disappear WITHOUT the real alarm disappearing
        with it."""
        path = self.write_crlf(
            "incomplete.md",
            "---\nphase: P3\nstatus: draft\nlast_updated: %s\n---\n\nBody.\n" % FIXTURE_DATE,
        )

        result = self.run_bash(
            'fm_validate_required "%s" "phase,subskill,status,last_updated" || true' % path
        )

        self.assertEqual(b"subskill\n", result.stdout)


# --------------------------------------------------------------------------
# fm_set -- the awk block at lines 295-296
# --------------------------------------------------------------------------


class FmSetCrlfTest(CrlfFixtureMixin, unittest.TestCase):
    """The writer half. Two obligations at once: find the block on a CRLF
    document, and leave the document's line endings exactly as they were --
    a record-leading strip on `$0` would satisfy the first and silently
    rewrite the whole file to LF, which is why the writers compare against
    a copy instead."""

    def test_fm_set_replaces_a_key_in_a_crlf_block_and_keeps_crlf(self):
        path = self.write_crlf("doc.md", "---\nstatus: draft\n---\n\n# Doc\n\nBody.\n")

        result = self.run_bash('fm_set "%s" status frozen' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            b"---\r\nstatus: frozen\r\n---\r\n\r\n# Doc\r\n\r\nBody.\r\n",
            path.read_bytes(),
        )

    def test_fm_set_inserts_an_absent_key_into_a_crlf_block_with_crlf(self):
        path = self.write_crlf("doc.md", "---\nname: x\n---\n\nBody.\n")

        result = self.run_bash('fm_set "%s" status frozen' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            b"---\r\nname: x\r\nstatus: frozen\r\n---\r\n\r\nBody.\r\n",
            path.read_bytes(),
        )

    def test_fm_set_leaves_a_crlf_body_line_that_looks_like_the_key_alone(self):
        """`fm_set`'s standing contract (WI-0076) is that scanning stops at
        the closing marker. On a CRLF file that contract only holds if the
        closing marker is recognised in the first place."""
        path = self.write_crlf(
            "doc.md", "---\nstatus: draft\n---\n\nstatus: draft\n"
        )

        result = self.run_bash('fm_set "%s" status frozen' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            b"---\r\nstatus: frozen\r\n---\r\n\r\nstatus: draft\r\n",
            path.read_bytes(),
        )

    def test_fm_set_refuses_a_crlf_file_with_no_frontmatter(self):
        """Fail-open guard: after the fix `fm_has` says yes to CRLF blocks,
        so the refusal path has to be re-proven on CRLF input too."""
        original = crlf_bytes("# Doc\n\nBody.\n")
        path = self.write_bytes("doc.md", original)

        result = self.run_bash('fm_set "%s" status frozen' % path)

        self.assertNotEqual(0, result.returncode)
        self.assertIn(b"no frontmatter block", result.stderr)
        self.assertEqual(original, path.read_bytes())

    def test_fm_set_on_an_lf_file_writes_an_lf_line(self):
        """The other direction of the terminator question: no carriage
        return may leak into a document that never had one."""
        path = self.write_lf("doc.md", "---\nstatus: draft\n---\n\nBody.\n")

        result = self.run_bash('fm_set "%s" status frozen' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"---\nstatus: frozen\n---\n\nBody.\n", path.read_bytes())


# --------------------------------------------------------------------------
# fm_set_many -- the awk block at lines 393-394
# --------------------------------------------------------------------------


class FmSetManyCrlfTest(CrlfFixtureMixin, unittest.TestCase):
    """Same obligations as `fm_set`, in the multi-key single-pass writer.
    It is a separate `awk` program with its own pair of marker comparisons,
    so it is measured separately rather than assumed to follow."""

    def test_fm_set_many_replaces_and_inserts_in_a_crlf_block_keeping_crlf(self):
        path = self.write_crlf("doc.md", "---\nstatus: draft\n---\n\nBody.\n")

        result = self.run_bash(
            'fm_set_many "%s" status=frozen anchor_commit=abc123' % path
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            b"---\r\nstatus: frozen\r\nanchor_commit: abc123\r\n---\r\n\r\nBody.\r\n",
            path.read_bytes(),
        )

    def test_fm_set_many_leaves_a_crlf_body_line_that_looks_like_a_key_alone(self):
        path = self.write_crlf("doc.md", "---\nstatus: draft\n---\n\nstatus: draft\n")

        result = self.run_bash('fm_set_many "%s" status=frozen' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            b"---\r\nstatus: frozen\r\n---\r\n\r\nstatus: draft\r\n",
            path.read_bytes(),
        )

    def test_fm_set_many_refuses_a_crlf_file_with_no_frontmatter(self):
        original = crlf_bytes("# Doc\n\nBody.\n")
        path = self.write_bytes("doc.md", original)

        result = self.run_bash('fm_set_many "%s" status=frozen' % path)

        self.assertNotEqual(0, result.returncode)
        self.assertIn(b"no frontmatter block", result.stderr)
        self.assertEqual(original, path.read_bytes())

    def test_fm_set_many_on_an_lf_file_writes_lf_lines(self):
        path = self.write_lf("doc.md", "---\nstatus: draft\n---\n\nBody.\n")

        result = self.run_bash('fm_set_many "%s" status=frozen extra=1' % path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            b"---\nstatus: frozen\nextra: 1\n---\n\nBody.\n", path.read_bytes()
        )


# --------------------------------------------------------------------------
# Consumers
# --------------------------------------------------------------------------


class ConsumerFixtureMixin(CrlfFixtureMixin):
    """A throwaway project tree plus a subprocess runner for the shipped
    consumer scripts. Never touches this repository's own docs/."""

    def run_script(self, script, *args, home=None):
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "HOME": str(home) if home else str(self.work / "fake-home"),
            "LC_ALL": "C",
        }
        (self.work / "fake-home").mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            ["bash", str(script), *[str(a) for a in args]],
            capture_output=True, cwd=str(self.work), env=env,
        )


class PhaseDocsLintCrlfTest(ConsumerFixtureMixin, unittest.TestCase):
    """`phase-docs-lint.sh` -- the consumer whose false alarm names the
    field the document actually carries. Check (k)'s `gate:` error is the
    sharpest instance: it is what a gate verdict is read out of."""

    def gate_doc(self, gate_line):
        return (
            "---\n"
            "phase: P3\n"
            "subskill: p3-gate\n"
            "status: frozen\n"
            "last_updated: %s\n"
            "%s"
            "---\n"
            "\n"
            "# Gate P3\n"
            "\n"
            "Body.\n" % (FIXTURE_DATE, gate_line)
        )

    def test_a_crlf_gate_document_is_not_reported_as_missing_its_gate_field(self):
        self.write_crlf("docs/architecture/GATE_P3.md", self.gate_doc("gate: go\n"))

        result = self.run_script(PHASE_DOCS_LINT, ".")

        self.assertIn(b"# Phase Docs Lint Report", result.stdout)
        self.assertIn(b"**Files scanned:** 1", result.stdout)
        self.assertNotIn(b"required field missing", result.stdout)
        self.assertNotIn(b"no YAML frontmatter", result.stdout)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_a_crlf_gate_document_that_really_omits_gate_is_still_reported(self):
        """The false alarm has to go without the real alarm going with it."""
        self.write_crlf("docs/architecture/GATE_P3.md", self.gate_doc(""))

        result = self.run_script(PHASE_DOCS_LINT, ".")

        self.assertIn(b"required field missing: gate", result.stdout)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)


class MemoryLintCrlfTest(ConsumerFixtureMixin, unittest.TestCase):
    """`memory-lint.sh` -- the same false alarm at ERROR severity
    ("no YAML frontmatter (---) at start of file")."""

    def seed(self, entry_text):
        self.write_lf(
            "docs/memory/MEMORY.md",
            "# Memory Index\n\n- [Alpha](project_alpha.md) - an entry\n",
        )
        self.write_crlf("docs/memory/project_alpha.md", entry_text)

    def test_a_crlf_memory_file_is_not_reported_as_having_no_frontmatter(self):
        self.seed(
            "---\nname: alpha\ndescription: A Tier-1 memory file.\n"
            "type: project\nlast_updated: %s\n---\n\n# Alpha\n\nBody.\n" % FIXTURE_DATE
        )

        result = self.run_script(MEMORY_LINT, ".")

        self.assertIn(b"# Memory Lint Report", result.stdout)
        self.assertNotIn(b"no YAML frontmatter", result.stdout)
        self.assertNotIn(b"required field missing", result.stdout)
        self.assertIn(b"**Summary:** 0 errors", result.stdout)

    def test_a_crlf_memory_file_missing_a_required_field_is_still_reported(self):
        self.seed(
            "---\nname: alpha\ndescription: A Tier-1 memory file.\n"
            "last_updated: %s\n---\n\n# Alpha\n\nBody.\n" % FIXTURE_DATE
        )

        result = self.run_script(MEMORY_LINT, ".")

        self.assertIn(b"required field missing: type", result.stdout)
        self.assertNotIn(b"no YAML frontmatter", result.stdout)


def report(result):
    """A lint report as text. Decoding bytes is NOT the same hazard as
    `text=True` on subprocess: `bytes.decode` performs no universal-newline
    translation, so a stray carriage return would survive into the string and
    still be visible there. Used only where the assertion is about the
    report WORDING (which carries a non-ASCII em-dash), never about file bytes.
    """
    return result.stdout.decode("utf-8")


def body_size_after_frontmatter(data):
    """The byte count `memory-lint.sh` check (j) is trying to compute:
    everything after the CLOSING frontmatter marker line, terminators
    included -- the Python mirror of `tail -n +$((close_line + 1)) | wc -c`.
    Computed from the fixture bytes rather than retyped as a constant, so a
    CRLF fixture and its LF twin each get their own correct expectation
    (a CRLF body is one byte per line larger, so a shared literal would be
    wrong for one of them)."""
    lines = data.splitlines(keepends=True)
    seen = 0
    for i, line in enumerate(lines):
        if line.rstrip(b"\r\n") == b"---":
            seen += 1
            if seen == 2:
                return sum(len(rest) for rest in lines[i + 1:])
    raise AssertionError("fixture carries no closing frontmatter marker")


class MemoryLintSkeletonSiloCrlfTest(ConsumerFixtureMixin, unittest.TestCase):
    r"""`memory-lint.sh` check (j), the skeleton-silo heuristic -- and the one
    place where hardening the shared library alone made a consumer WORSE.

    Line 505 runs its own `awk 'NR==1 && $0=="---" ...'` to find the closing
    marker's line number, and that `awk` is CRLF-blind in exactly the way the
    library was. The two are coupled through the `if fm_has ...; else` around
    them:

      * before the library fix, `fm_has` said "no frontmatter" on a CRLF silo
        index, the `else` branch counted the WHOLE file, and the check stayed
        silent -- accidentally right;
      * after it, `fm_has` says yes, line 505 still finds no closing marker,
        `close_line` is empty, `body_bytes` stays at its initialised 0, and a
        silo with a full MEMORY.md is reported as `likely skeleton silo
        (0 bytes of body, no topic files)`.

    Measured that way round on 31.08.2026, running the same fixture against a
    pre-fix and a post-fix copy of the library: pre-fix silent, post-fix the
    false report. So this is a regression introduced by the library change,
    fixed in the same round rather than filed onward.

    Both directions live in one run on purpose: the fixture builds TWO silos,
    one with a real body and one genuinely empty, and asserts exactly one of
    them is named. A repair that simply stopped reporting would satisfy the
    first assertion and fail the second.
    """

    FULL_BODY = "Real persona content, comfortably past the 400-byte threshold. " * 12
    EMPTY_BODY = "Stub.\n"

    def silo_text(self, name, body):
        return (
            "---\n"
            "name: %s index\n"
            "description: Persona index used to probe the skeleton-silo check.\n"
            "type: index\n"
            "last_updated: %s\n"
            "---\n"
            "\n"
            "# %s\n"
            "\n"
            "%s\n" % (name, FIXTURE_DATE, name, body)
        )

    def seed(self, writer):
        """`writer` is self.write_crlf or self.write_lf -- the same two silos
        in whichever line ending the test is about."""
        self.write_lf(
            "docs/memory/MEMORY.md",
            "# Memory Index\n"
            "\n"
            "- [Filled silo](senior-developer/)\n"
            "- [Empty silo](qa-tester/)\n",
        )
        filled = writer(
            "docs/memory/senior-developer/MEMORY.md",
            self.silo_text("senior-developer", self.FULL_BODY),
        )
        empty = writer(
            "docs/memory/qa-tester/MEMORY.md",
            self.silo_text("qa-tester", self.EMPTY_BODY),
        )
        return filled, empty

    def test_a_crlf_silo_with_a_real_body_is_not_called_a_skeleton(self):
        """The false alarm, and its own counter-direction in the same run."""
        self.seed(self.write_crlf)

        result = self.run_script(MEMORY_LINT, ".")

        # Liveness before anything else: memory-lint's documented contract is
        # 0 clean / 1 warnings / 2 errors, and a skeleton note is `info`, so a
        # run that reached the end reports 0. Without this, a crashed run with
        # empty stdout would satisfy every assertNotIn below.
        self.assertEqual(0, result.returncode, report(result))
        self.assertIn("# Memory Lint Report", report(result))
        # The positive half BEFORE the negative one: a genuinely empty CRLF
        # silo is still named. If this stops holding, the assertions below
        # would pass for the wrong reason -- a check reporting nothing at all.
        self.assertIn(
            "docs/memory/qa-tester/MEMORY.md — likely skeleton silo",
            report(result),
        )
        self.assertNotIn("docs/memory/senior-developer/MEMORY.md", report(result))
        self.assertNotIn("(0 bytes of body, no topic files)", report(result))

    def test_the_body_size_reported_for_a_crlf_silo_is_the_real_body_size(self):
        """Sharper than "not zero": the number in the message has to be the
        byte count of what actually follows the CRLF closing marker. Pre-fix
        this line read `(0 bytes of body, no topic files)` for every CRLF
        silo, filled or not."""
        _filled, empty = self.seed(self.write_crlf)
        expected = body_size_after_frontmatter(empty.read_bytes())

        result = self.run_script(MEMORY_LINT, ".")

        self.assertGreater(expected, 0, "fixture body must not be empty")
        self.assertIn(
            "likely skeleton silo (%d bytes of body, no topic files)" % expected,
            report(result),
        )

    def test_a_real_skeleton_silo_is_still_reported_on_an_lf_tree(self):
        """The LF control: the repair must not change what an all-LF project
        sees, in either direction."""
        _filled, empty = self.seed(self.write_lf)
        expected = body_size_after_frontmatter(empty.read_bytes())

        result = self.run_script(MEMORY_LINT, ".")

        self.assertEqual(0, result.returncode, report(result))
        self.assertGreater(expected, 0, "fixture body must not be empty")
        self.assertIn(
            "docs/memory/qa-tester/MEMORY.md — likely skeleton silo "
            "(%d bytes of body, no topic files)" % expected,
            report(result),
        )
        self.assertNotIn("docs/memory/senior-developer/MEMORY.md", report(result))


class ManualLintCrlfTest(ConsumerFixtureMixin, unittest.TestCase):
    """`manual-lint.sh` -- the SILENT direction. Its two checks are opt-in
    on `kind:` / `parent_index:`, so a CRLF document does not raise a false
    alarm; it simply drops out of both checks with nothing reported."""

    def test_a_crlf_document_with_a_dangling_parent_index_is_reported(self):
        self.write_lf("root/README.md", "# Root index\n\n- [Chapter](chapter.md)\n")
        self.write_crlf(
            "root/chapter.md",
            "---\nkind: guide\nparent_index: nowhere.md\n---\n\n# Chapter\n\nBody.\n",
        )

        result = self.run_script(MANUAL_LINT, "root")

        self.assertIn(b"# Manual Lint Report", result.stdout)
        self.assertIn(b"**Files scanned:** 2", result.stdout)
        self.assertIn(b"parent_index='nowhere.md' points to non-existent file", result.stdout)

    def test_a_crlf_document_with_a_resolvable_parent_index_stays_clean(self):
        """The negative twin: the check has to see the field, not merely
        shout about every CRLF file it meets."""
        self.write_lf("root/README.md", "# Root index\n\n- [Chapter](chapter.md)\n")
        self.write_crlf(
            "root/chapter.md",
            "---\nkind: guide\nparent_index: README.md\n---\n\n# Chapter\n\nBody.\n",
        )

        result = self.run_script(MANUAL_LINT, "root")

        self.assertIn(b"**Summary:** 0 errors", result.stdout)
        self.assertNotIn(b"non-existent file", result.stdout)


class FreezePhaseDocsCrlfTest(ConsumerFixtureMixin, unittest.TestCase):
    """`freeze-phase-docs.sh` -- the writer consumer, and the one that
    exercises the whole chain in one run: `fm_has`, then `fm_field`, then
    `fm_set`. Its failure mode is the quietest of the four: it reports
    "Would freeze 0 file(s)" and exits 0."""

    def detail_doc(self, status):
        return (
            "---\n"
            "phase: P3\n"
            "subskill: p3-sec-threats\n"
            "status: %s\n"
            "last_updated: %s\n"
            "---\n"
            "\n"
            "# Detail\n"
            "\n"
            "status: draft\n" % (status, FIXTURE_DATE)
        )

    def test_a_crlf_phase_doc_is_frozen_and_keeps_its_line_endings(self):
        path = self.write_crlf("docs/architecture/DETAIL.md", self.detail_doc("draft"))

        result = self.run_script(FREEZE_PHASE_DOCS, "P3", ".")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(b"frozen: docs/architecture/DETAIL.md (was: draft)", result.stdout)
        self.assertEqual(
            crlf_bytes(self.detail_doc("frozen")), path.read_bytes()
        )

    def test_a_crlf_phase_doc_already_in_a_terminal_state_is_left_alone(self):
        original = crlf_bytes(self.detail_doc("archived"))
        path = self.write_bytes("docs/architecture/DETAIL.md", original)

        result = self.run_script(FREEZE_PHASE_DOCS, "P3", ".")

        self.assertIn(b"Skipped 1 (terminal state)", result.stdout)
        self.assertEqual(original, path.read_bytes())

    def test_a_crlf_file_without_frontmatter_is_still_skipped_silently(self):
        original = crlf_bytes("# Not a phase doc\n\nstatus: draft\n")
        path = self.write_bytes("docs/architecture/NOTES.md", original)

        result = self.run_script(FREEZE_PHASE_DOCS, "P3", ".")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(b"Froze 0 file(s)", result.stdout)
        self.assertEqual(original, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
