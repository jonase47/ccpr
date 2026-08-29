"""test_command_check.py -- WI-0128 wave 3a, finding #5: the gate check that
can never reject.

## The defect (measured, HEAD e376348)

`scripts/command-check.py` (`check_gate_passed`, :99-133) is the tool whose
entire job is answering "has this gate been passed" for a downstream command
(`p4-backlog` etc.). Feeding it a `docs/GATE_P3.md` with three different
verdict bodies, against the shipped CLI unchanged:

| `docs/GATE_P3.md` content                          | before this fix |
|-----------------------------------------------------|------------------|
| `Verdict: Go`                                        | `ready`, exit 0  |
| `Verdict: No-Go -- blocked on three findings`        | `ready`, exit 0  |
| `Some text without a verdict`                        | `ready`, exit 0  |

The discriminator (:115, `if re.search(r"\bgo\b", ...) and not re.search(
r"\bno.go\b", ...): return True`) is followed two lines later by an
unconditional `return True` (:118) for every case that first branch does not
catch -- including an explicit No-Go, since `\bno.go\b` matches "no-go" and
therefore the `and not` makes the first branch's condition False, falling
through to the unconditional second `return True`. The comment above :118
("Also accept if the file exists -- some projects may not use Go/No-Go
format") names a real, worth-keeping intent; the fix below keeps that
leniency for gate files that use no Go/No-Go vocabulary at all, but makes an
*explicit* No-Go the one signal that overrides it -- because that is
literally the question `check_gate_passed` exists to answer. No-verdict-at-
all is not a rejection; an explicit rejection is not a case of "no verdict".

## Fixture design

`GateVerdictDiscriminatorTest` drives the real CLI (`python3
command-check.py p4-backlog <dir>`) as a subprocess against a crafted
`docs/GATE_P3.md`, exactly like a caller would invoke it (`main()`'s
contract is stdout `ready`/`blocked` + exit 0/1 -- see :185-203 -- so the
subprocess boundary is the one the tool actually promises). `p4-backlog` is
chosen because its own `COMMAND_PREREQUISITES` entry (:76-79) has an empty
`files` list, isolating the gate-verdict discriminator from any file-
presence noise.

`COMMAND_PREREQUISITES` (:31-96, 16 entries, consumed at exactly one call
site, :152) gets three more test classes per the WI-0126 house pattern
(test_next_steps_lists.py): a per-entry schema/behaviour sweep, a count pin,
and a removal red-proof via `unittest.mock.patch.dict` against the real,
already-imported dict object (never a rebuilt copy -- same reasoning as
`PhaseSequencesRemovalRedProofTest`'s docstring there).

14 of the 16 entries have a non-empty `files` list; removing any of those
from the dict is provably caught by `check_command`'s own reasons list,
because the generic fallback branch (:172-180) never checks any files at
all -- only a gate. The remaining two entries (`p4-backlog`, `p3-
architecture`) have an empty `files` list *and* a `gate` value that
coincidentally equals what the generic fallback would derive on its own
(`get_command_phase` extracts the same leading `pN` the entry itself
targets). That coincidence holds only for the `ready` boolean: both
branches pass the identical gate string into `check_gate_passed()`, so
the fallback can never disagree with the explicit entry on ready/blocked.
It does NOT hold for the `reasons` text -- with the gate unsatisfied, the
explicit-entry branch and the generic fallback format two different
strings for the same fact. `CommandPrerequisitesEmptyFilesEntriesRemoval
StructuralProofTest` documents the `ready`-boolean coincidence structurally
(dict count 16 -> 15, key absence) -- the same shape as `next_steps.py`'s
own `PhaseCountRemovalRedProofTest`, kept for exactly the case a
behavioural sweep on the satisfied state cannot catch -- and a sibling
behavioural test in the same class proves the reasons-text divergence
directly.

`command-check.py` is loaded via `importlib.util` (hyphenated filename, not
importable via `import command-check`) under a name other than `__main__`,
so its `if __name__ == "__main__": main()` guard never fires -- same
technique as `test_handover_size_hook.py`'s `_load_agent_monitor_module`.
Behavioural per-entry and removal tests call the loaded module's functions
directly (not subprocess) for precision on the `reasons` list content and
to patch the real `COMMAND_PREREQUISITES` object; the verdict-discriminator
class above still goes through the CLI, because that is the one place this
module tests the tool's actual shipped contract end to end.
"""

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "command-check.py"


def _load_command_check_module():
    spec = importlib.util.spec_from_file_location("ccpr_command_check", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cc = _load_command_check_module()


def write_gate_file(project_dir: Path, gate: str, body: str) -> None:
    """Writes docs/GATE_<PHASE>.md -- the first path check_gate_passed
    probes (:104) -- with the given raw body."""
    phase = gate.replace("gate-", "").upper()
    docs = project_dir / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / f"GATE_{phase}.md").write_text(body, encoding="utf-8")


def make_satisfied_project_dir(tmp_root: Path, command: str, spec: dict) -> Path:
    """Builds a scratch project dir that satisfies one COMMAND_PREREQUISITES
    entry exactly: every listed file/dir present, and -- if the entry names
    a gate -- that gate's file present with an explicit 'Go' verdict."""
    project_dir = Path(tempfile.mkdtemp(dir=tmp_root))
    for f in spec.get("files", []):
        full = project_dir / f
        if f.endswith("/"):
            full.mkdir(parents=True, exist_ok=True)
            (full / ".keep").write_text("x", encoding="utf-8")
        else:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text("x", encoding="utf-8")
    gate = spec.get("gate")
    if gate:
        write_gate_file(project_dir, gate, "Verdict: Go")
    return project_dir


class GateVerdictDiscriminatorTest(unittest.TestCase):
    """Drives the real CLI against the three verdict shapes from the
    reproduced-defect table above. p4-backlog's own entry has an empty
    `files` list (:76-79), so `ready`/`blocked` here is driven by
    check_gate_passed's Go/No-Go discriminator alone."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def _run(self, gate_body: str):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        write_gate_file(project_dir, "gate-p3", gate_body)
        result = __import__("subprocess").run(
            [sys.executable, str(SCRIPT_PATH), "p4-backlog", str(project_dir)],
            capture_output=True,
            text=True,
        )
        return result

    def test_explicit_go_is_ready(self):
        result = self._run("Verdict: Go")
        self.assertEqual(result.stdout.strip(), "ready")
        self.assertEqual(result.returncode, 0)

    def test_explicit_no_go_is_blocked(self):
        result = self._run("Verdict: No-Go — blocked on three findings")
        self.assertEqual(result.stdout.strip().splitlines()[0], "blocked")
        self.assertEqual(result.returncode, 1)

    def test_no_verdict_at_all_is_ready(self):
        """Documented leniency (:125-128): a gate file that uses no
        Go/No-Go vocabulary at all is not itself a rejection."""
        result = self._run("Some text without a verdict")
        self.assertEqual(result.stdout.strip(), "ready")
        self.assertEqual(result.returncode, 0)

    def test_prose_no_go_mention_before_an_appended_go_verdict_is_ready(self):
        """Six shipped gate commands instruct writers to name "No-Go" in
        prose when flagging an Inviolable breach (gate-p0/p1/p2/p3/p4/p6.md
        all carry language like "treat it as a No-Go signal"). A document
        that does exactly that but still concludes with an appended
        'Verdict: Go' must be ready -- this is the WI-0128 finding-#5
        regression: a "block if no-go appears anywhere" rule returns
        False here (measured against the pre-fix code: False, i.e.
        blocked -- the failure this test is written to catch)."""
        result = self._run(
            "Any violation is treated as a No-Go signal per the "
            "constitution.\n\n## Gate Notes\n\nVerdict: Go\n"
        )
        self.assertEqual(result.stdout.strip(), "ready")
        self.assertEqual(result.returncode, 0)

    def test_prose_go_mention_before_an_appended_no_go_verdict_is_blocked(self):
        """The mirror image of the test above: an early, incidental "go"
        must not outrank an appended 'Verdict: No-Go'. This falsifies the
        naive inversion of the fix above ("pass if go appears anywhere,
        checked first") -- measured against that alternative rule: True,
        i.e. ready -- not against the shipped pre-fix code, which already
        returns blocked here because its own no-go check runs first and
        matches the later "No-Go" token regardless of position."""
        result = self._run(
            "The team is a go for the next milestone.\n\n"
            "## Gate Notes\n\nVerdict: No-Go -- blocked on findings\n"
        )
        self.assertEqual(result.stdout.strip().splitlines()[0], "blocked")
        self.assertEqual(result.returncode, 1)


class CommandPrerequisitesSchemaTest(unittest.TestCase):
    def test_entry_count_is_pinned_at_16(self):
        self.assertEqual(len(cc.COMMAND_PREREQUISITES), 16)

    def test_every_entry_has_the_files_and_gate_keys(self):
        for command, spec in cc.COMMAND_PREREQUISITES.items():
            with self.subTest(command=command):
                self.assertIn("files", spec)
                self.assertIn("gate", spec)
                self.assertIsInstance(spec["files"], list)
                self.assertTrue(spec["gate"] is None or isinstance(spec["gate"], str))


class CommandPrerequisitesP7DeployPointsAtPrepareArtifactTest(unittest.TestCase):
    """P7 doc rename (WI-0128): /p7-prepare writes docs/launch/PREPARE.md
    (p7-prepare.md:71,94) and /p7-deploy itself reads/updates that same file
    (p7-deploy.md:75). Before this fix, p7-deploy's own prerequisite still
    named the pre-rename legacy filename, a file nothing produces — pinning
    the exact artifact /p7-prepare hands off so a future rename cannot
    silently drift the two apart again."""

    def test_p7_deploy_prerequisite_is_exactly_the_prepare_artifact(self):
        self.assertEqual(
            cc.COMMAND_PREREQUISITES["p7-deploy"]["files"],
            ["docs/launch/PREPARE.md"],
        )


class CommandPrerequisitesReadyAndBlockedTest(unittest.TestCase):
    """Per-entry behavioural coverage for all 16 COMMAND_PREREQUISITES
    entries, driving check_command() directly (not the source dict
    retyped)."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def test_satisfied_entry_is_ready_with_no_reasons(self):
        for command, spec in cc.COMMAND_PREREQUISITES.items():
            with self.subTest(command=command):
                project_dir = make_satisfied_project_dir(Path(self.tmp_root), command, spec)
                ready, reasons = cc.check_command(command, str(project_dir))
                self.assertTrue(ready, reasons)
                self.assertEqual(reasons, [])

    def test_each_missing_required_file_blocks_with_a_matching_reason(self):
        for command, spec in cc.COMMAND_PREREQUISITES.items():
            files = spec.get("files", [])
            for missing in files:
                with self.subTest(command=command, missing=missing):
                    project_dir = make_satisfied_project_dir(Path(self.tmp_root), command, spec)
                    target = project_dir / missing
                    if missing.endswith("/"):
                        __import__("shutil").rmtree(target)
                    else:
                        target.unlink()
                    ready, reasons = cc.check_command(command, str(project_dir))
                    self.assertFalse(ready)
                    self.assertTrue(
                        any(missing in reason for reason in reasons),
                        f"no reason mentions {missing!r}: {reasons}",
                    )

    def test_entries_with_a_gate_block_when_the_gate_is_not_passed(self):
        for command, spec in cc.COMMAND_PREREQUISITES.items():
            gate = spec.get("gate")
            if not gate:
                continue
            with self.subTest(command=command, gate=gate):
                project_dir = make_satisfied_project_dir(Path(self.tmp_root), command, spec)
                phase = gate.replace("gate-", "").upper()
                (project_dir / "docs" / f"GATE_{phase}.md").unlink()
                ready, reasons = cc.check_command(command, str(project_dir))
                self.assertFalse(ready)
                self.assertTrue(any(gate in reason for reason in reasons), reasons)


class CommandPrerequisitesFilesRemovalRedProofTest(unittest.TestCase):
    """The 14 entries whose `files` list is non-empty: removing the entry
    from COMMAND_PREREQUISITES (patch.dict against the real, already-
    imported object) drops the file check entirely, because the generic
    fallback branch (:172-180) never inspects any file -- only a gate. The
    reason mentioning the missing file is present before the removal and
    gone after, for every one of the 14 entries and every file each lists."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def test_removing_the_entry_drops_its_file_reason(self):
        entries_with_files = {
            command: spec
            for command, spec in cc.COMMAND_PREREQUISITES.items()
            if spec.get("files")
        }
        self.assertEqual(len(entries_with_files), 14)

        for command, spec in entries_with_files.items():
            for missing in spec["files"]:
                with self.subTest(command=command, missing=missing):
                    project_dir = make_satisfied_project_dir(Path(self.tmp_root), command, spec)
                    target = project_dir / missing
                    if missing.endswith("/"):
                        __import__("shutil").rmtree(target)
                    else:
                        target.unlink()

                    before_ready, before_reasons = cc.check_command(command, str(project_dir))
                    self.assertFalse(before_ready)
                    self.assertTrue(any(missing in r for r in before_reasons))

                    with patch.dict(cc.COMMAND_PREREQUISITES):
                        del cc.COMMAND_PREREQUISITES[command]
                        self.assertEqual(len(cc.COMMAND_PREREQUISITES), 15)

                        after_ready, after_reasons = cc.check_command(command, str(project_dir))
                        self.assertFalse(any(missing in r for r in after_reasons))

                    # patch.dict restored the deleted entry
                    self.assertIn(command, cc.COMMAND_PREREQUISITES)


class CommandPrerequisitesEmptyFilesEntriesRemovalStructuralProofTest(unittest.TestCase):
    """`p4-backlog` and `p3-architecture` are the two entries with an empty
    `files` list AND a `gate` value that coincidentally equals what
    get_command_phase's generic fallback (:172-180) would derive on its own
    for that same command name. The `ready` boolean genuinely never
    diverges for either entry, in any project state: both the explicit-
    entry branch and the generic fallback pass the identical gate string
    into check_gate_passed(), so the fallback can never produce a
    different verdict -- that half of the coincidence is real and is what
    this class proves. The `reasons` *text* is not identical, though: with
    the gate unsatisfied the two branches format two different strings for
    the same fact (`"{gate} not passed (gate file missing or no 'Go')"` vs
    `"{prev_gate} not passed"`) -- proven behaviourally by
    test_removal_changes_the_reason_text_when_the_gate_is_not_passed below,
    not here. This class proves only what a behavioural sweep on the
    satisfied state cannot: the dict's own count and key membership, which
    a removal cannot fail to change regardless of the reasons-text
    divergence -- same shape as next_steps.py's own
    PhaseCountRemovalRedProofTest."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def test_the_two_empty_files_entries_are_exactly_these_two(self):
        empty_files_entries = {
            command
            for command, spec in cc.COMMAND_PREREQUISITES.items()
            if not spec.get("files")
        }
        self.assertEqual(empty_files_entries, {"p4-backlog", "p3-architecture"})

    def test_removal_is_a_check_command_no_op_but_shrinks_the_dict(self):
        for command in ("p4-backlog", "p3-architecture"):
            with self.subTest(command=command):
                spec = cc.COMMAND_PREREQUISITES[command]
                project_dir = make_satisfied_project_dir(Path(self.tmp_root), command, spec)

                before_ready, before_reasons = cc.check_command(command, str(project_dir))

                with patch.dict(cc.COMMAND_PREREQUISITES):
                    del cc.COMMAND_PREREQUISITES[command]
                    self.assertEqual(len(cc.COMMAND_PREREQUISITES), 15)
                    self.assertNotIn(command, cc.COMMAND_PREREQUISITES)

                    after_ready, after_reasons = cc.check_command(command, str(project_dir))
                    # The coincidence this class documents: in the
                    # satisfied state, check_command's own verdict does
                    # not react to this particular removal.
                    self.assertEqual(before_ready, after_ready)
                    self.assertEqual(before_reasons, after_reasons)

                self.assertIn(command, cc.COMMAND_PREREQUISITES)

    def test_removal_changes_the_reason_text_when_the_gate_is_not_passed(self):
        """The structural proof above only shows that the `ready` boolean
        is identical for this removal -- it does NOT show "ZERO observable
        check_command() difference", which an earlier version of this
        class's docstring wrongly claimed. That claim was only ever tested
        in the satisfied state (make_satisfied_project_dir always writes
        'Verdict: Go'), where both branches trivially return
        `reasons == []`. With the gate unsatisfied the two branches
        disagree on the reason wording (measured 28.08.2026, current
        code):

            p4-backlog:  with entry  -> "gate-p3 not passed (gate file missing or no 'Go')"
                         without entry -> "gate-p3 not passed"
            p3-architecture: with entry -> "gate-p2 not passed (gate file missing or no 'Go')"
                             without entry -> "gate-p2 not passed"
        """
        for command in ("p4-backlog", "p3-architecture"):
            with self.subTest(command=command):
                spec = cc.COMMAND_PREREQUISITES[command]
                project_dir = make_satisfied_project_dir(Path(self.tmp_root), command, spec)
                gate = spec["gate"]
                phase = gate.replace("gate-", "").upper()
                (project_dir / "docs" / f"GATE_{phase}.md").unlink()

                before_ready, before_reasons = cc.check_command(command, str(project_dir))
                self.assertFalse(before_ready)
                self.assertEqual(
                    before_reasons,
                    [f"{gate} not passed (gate file missing or no 'Go')"],
                )

                with patch.dict(cc.COMMAND_PREREQUISITES):
                    del cc.COMMAND_PREREQUISITES[command]

                    after_ready, after_reasons = cc.check_command(command, str(project_dir))
                    self.assertFalse(after_ready)
                    self.assertEqual(after_reasons, [f"{gate} not passed"])
                    self.assertNotEqual(before_reasons, after_reasons)

                self.assertIn(command, cc.COMMAND_PREREQUISITES)


class DeadCodeRemovedTest(unittest.TestCase):
    """Static source-text proofs for the two dead-code findings named in
    the briefing. Both citations below are to removed code -- they no
    longer exist in the current file, only at git HEAD (e376348): the
    unused PHASE_SEQUENCES import (before this change, at the old :15,
    sole occurrence in the whole repo per `grep -n "PHASE_SEQUENCES"
    scripts/command-check.py`, measured 28.08.2026) and the unused
    `content` variable read from HANDOVER.md (before this change, at the
    old :120-124, shadowed by extract_phase_from_handover's own re-read of
    the same file two lines later)."""

    def setUp(self):
        self.source = SCRIPT_PATH.read_text(encoding="utf-8")

    def test_phase_sequences_import_is_gone(self):
        self.assertNotIn("PHASE_SEQUENCES", self.source)

    def test_extract_phase_from_handover_is_still_imported(self):
        self.assertRegex(self.source, r"from next_steps import extract_phase_from_handover")

    def test_handover_file_is_not_opened_directly_in_check_gate_passed(self):
        gate_fn_source = self.source.split("def check_gate_passed")[1].split("\ndef ")[0]
        self.assertNotIn("open(handover_path", gate_fn_source)


class HandoverPhaseFallbackStillWorksTest(unittest.TestCase):
    """The dead-variable cleanup above must not disturb the still-live
    behaviour it sits next to: when no GATE_*.md file exists at all,
    check_gate_passed falls back to comparing the current HANDOVER.md phase
    against the gate's own phase number (:130-138)."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def test_current_phase_beyond_the_gate_counts_as_passed(self):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        docs = project_dir / "docs"
        docs.mkdir(parents=True)
        (docs / "HANDOVER.md").write_text("Phase: P4\n", encoding="utf-8")
        self.assertTrue(cc.check_gate_passed("gate-p3", str(project_dir)))

    def test_current_phase_at_or_before_the_gate_is_not_passed(self):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        docs = project_dir / "docs"
        docs.mkdir(parents=True)
        (docs / "HANDOVER.md").write_text("Phase: P2\n", encoding="utf-8")
        self.assertFalse(cc.check_gate_passed("gate-p3", str(project_dir)))


if __name__ == "__main__":
    unittest.main()
