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
to patch the real `COMMAND_PREREQUISITES` object; the CLI-driven classes
still go through the CLI, because that is the one place this module tests
the tool's actual shipped contract end to end.

## Superseded by WI-0129

The prose Go/No-Go discriminator this module was originally written for is
gone: WI-0129 (findings F3/F4) found it wrong three more times ("Go" inside
"No-Go" and inside "Go-Live"; every gate command instructing authors to
*name* "No-Go" in prose) and replaced it with a `gate:` YAML frontmatter
field, read by `_read_frontmatter_field`. `GateVerdictDiscriminatorTest`
(the class the "Fixture design" section above describes) was replaced by
`GateVerdictFrontmatterVocabularyTest`/`GateVerdictCrossVocabularyTest`/
`GateVerdictMissingFieldTest`/`GateVerdictOutsideVocabularyTest`/
`GateVerdictFrontmatterRegressionTest` -- the last of those carries WI-0129's
own regression fixture (a `no_go` frontmatter verdict alongside a "Go-Live"
prose paragraph) as its direct descendant. `check_gate_passed()` also
changed shape in the same tranche, from a bare bool to `(passed, reason)`,
which retired the reasons-text divergence this docstring's "Fixture design"
section describes (:58-66 above) -- both `check_command()` call sites now
simply forward the same `reason` string, so the divergence no longer
exists; see `CommandPrerequisitesEmptyFilesEntriesRemovalStructuralProofTest`'s
own updated docstring for what replaced that claim.
"""

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "command-check.py"
PHASE_DOCS_LINT_PATH = REPO_ROOT / "scripts" / "phase-docs-lint.sh"


def _load_command_check_module():
    spec = importlib.util.spec_from_file_location("ccpr_command_check", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cc = _load_command_check_module()


def read_verdict_enum(varname: str, script_path: Path = PHASE_DOCS_LINT_PATH) -> tuple:
    """Parses NAME="a b c" (a space-separated shell-string constant) out of
    a shipped script's own source text -- never retyped here. Same parser
    shape as scripts/tests/test_phase_docs_lint.py's own `read_enum`
    (duplicated rather than imported: that module is a subprocess-heavy
    fixture-generating module in its own right, not meant to be imported by
    a sibling test module). Used to bind command-check.py's gate-verdict
    vocabularies to phase-docs-lint.sh's VALID_GATE_VERDICTS/
    VALID_SPRINT_VERDICTS -- CONTRIBUTING.md's "derive a contract test's
    expectation from the other artifact, not the code under test" (WI-0129).
    """
    text = script_path.read_text(encoding="utf-8")
    m = re.search(r'^%s="([^"]*)"' % re.escape(varname), text, re.MULTILINE)
    if m is None:
        raise AssertionError(f'could not find {varname}="..." in {script_path}')
    return tuple(m.group(1).split())


# The two gate-verdict vocabularies, parsed from phase-docs-lint.sh's own
# source (never retyped) -- used by GateVerdictVocabularyMatchesTheLint
# ScriptTest below, and by fixture helpers in this file that need a value
# known to be OUTSIDE one artifact's vocabulary but valid on the other.
GATE_P_VOCABULARY = set(read_verdict_enum("VALID_GATE_VERDICTS"))
SPRINT_VOCABULARY = set(read_verdict_enum("VALID_SPRINT_VERDICTS"))

# The canonical passing/blocking verdict per artifact kind, used by fixture
# helpers below that need "a verdict that passes" / "a verdict that exists
# in-vocabulary but blocks" without caring about the exact value.
_CANONICAL_PASSING_VERDICT = {"GATE_P": "go", "SPRINT": "done"}
_CANONICAL_BLOCKING_VERDICT = {"GATE_P": "no_go", "SPRINT": "not_done"}


def write_gate_file(project_dir: Path, gate: str, verdict: str, body: str = "") -> None:
    """Writes the gate's own protocol file at the path production itself
    reads it from -- `cc.GATE_FILE_PATHS[gate]` (scripts/lib/
    gate_checklists.py) -- with `verdict` set in its YAML frontmatter
    `gate:` field, the ONLY place check_gate_passed() reads a verdict from
    since WI-0129 F3/F4 retired the prose scanner. `body` is optional prose
    appended after the frontmatter block, for fixtures that need to prove
    prose is no longer read at all (e.g. a `no_go` verdict alongside a
    "Go-Live" paragraph in the body -- the exact regression this tranche
    fixes, see GateVerdictFrontmatterRegressionTest below).

    Before this fix (WI-0129, finding F2) this helper hardcoded
    docs/GATE_<PHASE>.md -- the flat legacy path -- so the fixture and the
    code under test agreed by construction and the question "is this path
    right?" could never be asked; that flat path is never written by any
    real gate-pN.md command (see check_gate_passed()'s own docstring).

    Raises KeyError for any gate absent from GATE_FILE_PATHS. None are,
    currently: gate-p5 (docs/planning/SPRINT.md) was the last gate this
    dict omitted, and this tranche gives it an entry too.
    """
    rel_path = cc.GATE_FILE_PATHS[gate]
    full_path = project_dir / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(f"---\ngate: {verdict}\n---\n{body}", encoding="utf-8")


def write_gate_file_without_gate_field(project_dir: Path, gate: str, body: str = "Some prose.\n") -> None:
    """Writes the gate's own artifact WITH a frontmatter block but with no
    `gate:` field inside it at all -- the "field missing" failure shape
    check_gate_passed() must report by name (as opposed to "file missing"
    or "value outside vocabulary")."""
    rel_path = cc.GATE_FILE_PATHS[gate]
    full_path = project_dir / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(f"---\nphase: P3\n---\n{body}", encoding="utf-8")


def _passing_verdict_for(rel_path: str) -> str:
    return _CANONICAL_PASSING_VERDICT[cc.gate_artifact_kind(rel_path)]


def _blocking_verdict_for(rel_path: str) -> str:
    return _CANONICAL_BLOCKING_VERDICT[cc.gate_artifact_kind(rel_path)]


def satisfy_gate(project_dir: Path, gate: str) -> None:
    """Satisfies `gate` in `project_dir` with a passing verdict on its own
    artifact -- 'go' for the seven GATE_P*.md gates, 'done' for gate-p5's
    docs/planning/SPRINT.md (the two vocabularies differ; see
    gate_checklists.GATE_VERDICT_PASSING_VALUES)."""
    rel_path = cc.GATE_FILE_PATHS[gate]
    write_gate_file(project_dir, gate, _passing_verdict_for(rel_path))


def unsatisfy_gate(project_dir: Path, gate: str) -> None:
    """Undoes satisfy_gate() -- removes the gate's own artifact file
    entirely, so check_gate_passed() falls through to the (out-of-scope,
    unchanged) HANDOVER.md phase-comparison branch."""
    (project_dir / cc.GATE_FILE_PATHS[gate]).unlink()


def make_satisfied_project_dir(tmp_root: Path, command: str, spec: dict) -> Path:
    """Builds a scratch project dir that satisfies one COMMAND_PREREQUISITES
    entry exactly: every listed file/dir present, and -- if the entry names
    a gate -- that gate satisfied (see satisfy_gate())."""
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
        satisfy_gate(project_dir, gate)
    return project_dir


class GateVerdictFrontmatterVocabularyTest(unittest.TestCase):
    """Exhaustive per-value coverage of both gate-verdict vocabularies
    (WI-0129, findings F3/F4): every value in GATE_P_VOCABULARY, on its own
    GATE_P*.md artifact (gate-p3), and every value in SPRINT_VOCABULARY, on
    its own SPRINT.md artifact (gate-p5) -- the right pass/block outcome
    for each, `pending` and `pivot`/`not_done` included (both exist in
    their vocabulary but must still BLOCK -- only go/conditional_go and
    done/conditionally_done unblock)."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def _check(self, gate: str, verdict: str):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        write_gate_file(project_dir, gate, verdict)
        return cc.check_gate_passed(gate, str(project_dir))

    def test_every_gate_p_verdict_has_the_expected_outcome(self):
        expected_passing = {"go", "conditional_go"}
        for verdict in GATE_P_VOCABULARY:
            with self.subTest(verdict=verdict):
                passed, reason = self._check("gate-p3", verdict)
                self.assertEqual(passed, verdict in expected_passing, reason)
                if not passed:
                    self.assertIsNotNone(reason)

    def test_every_sprint_verdict_has_the_expected_outcome(self):
        expected_passing = {"done", "conditionally_done"}
        for verdict in SPRINT_VOCABULARY:
            with self.subTest(verdict=verdict):
                passed, reason = self._check("gate-p5", verdict)
                self.assertEqual(passed, verdict in expected_passing, reason)
                if not passed:
                    self.assertIsNotNone(reason)

    def test_pending_blocks_on_both_artifacts(self):
        self.assertFalse(self._check("gate-p3", "pending")[0])
        self.assertFalse(self._check("gate-p5", "pending")[0])

    def test_pivot_blocks_on_gate_p(self):
        self.assertFalse(self._check("gate-p3", "pivot")[0])


class GateVerdictCrossVocabularyTest(unittest.TestCase):
    """The two discriminating cases a SHARED vocabulary would pass: `done`
    (a SPRINT-only passing value) written on a GATE_P*.md artifact, and
    `go` (a GATE_P-only passing value) written on SPRINT.md. Both must
    block -- gate_artifact_kind() selects the vocabulary by the artifact's
    own path, not by whether the value happens to be a passing token on
    SOME vocabulary (WI-0129)."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def test_done_on_a_gate_p_artifact_blocks(self):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        write_gate_file(project_dir, "gate-p3", "done")
        passed, reason = cc.check_gate_passed("gate-p3", str(project_dir))
        self.assertFalse(passed)
        self.assertIn("done", reason)

    def test_go_on_sprint_md_blocks(self):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        write_gate_file(project_dir, "gate-p5", "go")
        passed, reason = cc.check_gate_passed("gate-p5", str(project_dir))
        self.assertFalse(passed)
        self.assertIn("go", reason)


class GateVerdictMissingFieldTest(unittest.TestCase):
    """A gate artifact that EXISTS but carries no `gate:` field at all --
    the old prose scanner's lenient `return True` for this exact shape was
    finding F4. The fixed parser fails closed and names the field in its
    reason."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def test_no_gate_field_blocks_and_names_the_field(self):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        write_gate_file_without_gate_field(project_dir, "gate-p3")
        passed, reason = cc.check_gate_passed("gate-p3", str(project_dir))
        self.assertFalse(passed)
        self.assertIn("gate:", reason)
        self.assertIn("docs/architecture/GATE_P3.md", reason)

    def test_no_frontmatter_block_at_all_blocks_and_names_the_field(self):
        """A gate file that predates the frontmatter schema entirely (no
        `---` block whatsoever) is a stricter case of the same shape --
        _read_frontmatter_field returns None for it the same way."""
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        full_path = project_dir / cc.GATE_FILE_PATHS["gate-p3"]
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text("Verdict: Go\n\nNo frontmatter block here.\n", encoding="utf-8")
        passed, reason = cc.check_gate_passed("gate-p3", str(project_dir))
        self.assertFalse(passed)
        self.assertIn("gate:", reason)


class GateVerdictOutsideVocabularyTest(unittest.TestCase):
    """A `gate:` value outside its artifact's closed vocabulary -- using
    the real prose spelling ("Conditional Go") that motivated this fix in
    the first place (measured across three CCPR-using projects, seven
    different prose spellings; none of them is the declared token
    `conditional_go`). Blocks, naming the offending value."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def test_prose_spelled_value_blocks_and_names_the_value(self):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        write_gate_file(project_dir, "gate-p3", "Conditional Go")
        passed, reason = cc.check_gate_passed("gate-p3", str(project_dir))
        self.assertFalse(passed)
        self.assertIn("Conditional Go", reason)


class GateVerdictFrontmatterRegressionTest(unittest.TestCase):
    """WI-0129's own regression fixture, pinned end to end via the real CLI
    (p4-backlog's own entry has an empty `files` list, so `ready`/`blocked`
    here is driven by the gate-verdict check alone, same subprocess-
    boundary reasoning as the class this replaces): a gate document whose
    `gate:` frontmatter says `no_go` while its PROSE BODY contains a
    "Go-Live" paragraph. Under the pre-fix prose scanner this exact
    document returned `ready`, exit 0 -- the substring "Go" inside
    "Go-Live" satisfied the old `\\bgo\\b` pattern. The fixed parser never
    reads the body at all."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def _run(self, verdict: str, body: str):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        write_gate_file(project_dir, "gate-p3", verdict, body)
        result = __import__("subprocess").run(
            [sys.executable, str(SCRIPT_PATH), "p4-backlog", str(project_dir)],
            capture_output=True,
            text=True,
        )
        return result

    def test_no_go_frontmatter_with_a_go_live_paragraph_is_blocked(self):
        result = self._run(
            "no_go",
            "## Go-Live Checklist\n\nOnce merged, coordinate the Go-Live "
            "window with the release team.\n",
        )
        self.assertEqual(result.stdout.strip().splitlines()[0], "blocked")
        self.assertEqual(result.returncode, 1)

    def test_go_frontmatter_with_a_no_go_mention_is_ready(self):
        """The mirror case: six shipped gate commands instruct writers to
        name "No-Go" in prose when flagging an Inviolable breach. A
        document that does exactly that but carries `gate: go` in its
        frontmatter must still be ready -- the frontmatter field is the
        only signal read, prose is never consulted either way."""
        result = self._run(
            "go",
            "Any violation is treated as a No-Go signal per the "
            "constitution.\n\n## Gate Notes\n\nNo violations found.\n",
        )
        self.assertEqual(result.stdout.strip(), "ready")
        self.assertEqual(result.returncode, 0)


class GateVerdictVocabularyMatchesTheLintScriptTest(unittest.TestCase):
    """CONTRIBUTING.md's "derive a contract test's expectation from the
    other artifact, not the code under test": command-check.py's own
    gate-verdict sets (scripts/lib/gate_checklists.py's
    GATE_VERDICT_VOCABULARIES/GATE_VERDICT_PASSING_VALUES) must equal
    VALID_GATE_VERDICTS/VALID_SPRINT_VERDICTS as parsed straight out of
    scripts/phase-docs-lint.sh's own source -- the lint script's copy,
    never this test's own retyped literal. `templates/PHASE_DOC_SCHEMA.md`
    binds a THIRD copy (the human-readable table) to the same lint-script
    source via test_phase_docs_lint.py's own GateVerdictVocabulary
    MatchesSchemaTest -- together the three tests keep all three copies
    (schema doc, lint enforcement, command-check.py's consumer) from
    drifting from each other unnoticed."""

    def test_gate_p_vocabulary_matches_the_lint_script(self):
        self.assertEqual(cc.GATE_VERDICT_VOCABULARIES["GATE_P"], frozenset(GATE_P_VOCABULARY))

    def test_sprint_vocabulary_matches_the_lint_script(self):
        self.assertEqual(cc.GATE_VERDICT_VOCABULARIES["SPRINT"], frozenset(SPRINT_VOCABULARY))

    def test_the_two_vocabularies_are_not_identical(self):
        # Guards against a future edit collapsing both sets into one shared
        # constant -- the whole point of the split is that 'done' and 'go'
        # are each valid for only ONE artifact.
        self.assertNotEqual(cc.GATE_VERDICT_VOCABULARIES["GATE_P"], cc.GATE_VERDICT_VOCABULARIES["SPRINT"])


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
                unsatisfy_gate(project_dir, gate)
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
    this class proves.

    Before WI-0129, the `reasons` *text* was NOT identical: with the gate
    unsatisfied the two branches formatted two different strings for the
    same fact (`"{gate} not passed (gate file missing or no 'Go')"` vs
    `"{prev_gate} not passed"`), because each branch built its own reason
    string independently. This tranche moved reason-formatting entirely
    into check_gate_passed() itself (it now returns `(passed, reason)`),
    so both call sites simply pass the same reason through -- the wording
    divergence is gone by construction, not by coincidence.
    test_reason_text_is_identical_via_both_branches_when_the_gate_is_not_
    passed below proves that directly. This class proves only what a
    behavioural sweep on the satisfied state cannot: the dict's own count
    and key membership, which a removal cannot fail to change -- same
    shape as next_steps.py's own PhaseCountRemovalRedProofTest."""

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

    def test_reason_text_is_identical_via_both_branches_when_the_gate_is_not_passed(self):
        """Before WI-0129, removing the entry changed the reason WORDING
        even though `ready` stayed the same (the explicit-entry branch and
        the generic fallback each formatted their own string). Since both
        branches now simply forward check_gate_passed()'s own `reason`
        unchanged, the reason text is identical whether the entry is
        present or removed -- proving the removal is now a TRUE no-op for
        this pair, not the partial one the pre-fix docstring described."""
        for command in ("p4-backlog", "p3-architecture"):
            with self.subTest(command=command):
                spec = cc.COMMAND_PREREQUISITES[command]
                project_dir = make_satisfied_project_dir(Path(self.tmp_root), command, spec)
                gate = spec["gate"]
                unsatisfy_gate(project_dir, gate)

                before_ready, before_reasons = cc.check_command(command, str(project_dir))
                self.assertFalse(before_ready)
                self.assertEqual(len(before_reasons), 1)
                self.assertIn(gate, before_reasons[0])

                with patch.dict(cc.COMMAND_PREREQUISITES):
                    del cc.COMMAND_PREREQUISITES[command]

                    after_ready, after_reasons = cc.check_command(command, str(project_dir))
                    self.assertFalse(after_ready)
                    self.assertEqual(before_reasons, after_reasons)

                self.assertIn(command, cc.COMMAND_PREREQUISITES)


GATE_FILE_CLAIM_RE = re.compile(r"^Create \*\*`(docs/[^`]+/GATE_P(\d)\.md)`\*\*", re.MULTILINE)

# gate-p5 claims a different-SHAPED artifact than the other seven: not "this
# command creates its own GATE_P5.md" (it has none), but "this command sets
# the `gate:` frontmatter field on docs/planning/SPRINT.md" (WI-0129).
# Anchored on the exact sentence commands/gate-p5.md's "### 3. Create Gate
# Protocol" section carries -- a differently-shaped bold lead-in than
# GATE_FILE_CLAIM_RE's "Create **`...`**", which is exactly why it needs its
# own pattern rather than a tweak to that one.
SPRINT_GATE_FIELD_CLAIM_RE = re.compile(
    r"\*\*Set `(docs/planning/SPRINT\.md)`'s frontmatter field `gate:`\*\*"
)


def _parse_gate_file_claims(commands_dir: Optional[Path] = None) -> dict:
    """Parses each top-level `commands/gate-p<N>.md`'s own claim about what
    gate artifact it writes into `{"gate-p<N>": "<claimed path>"}`. Seven of
    the eight (gate-p0/1/2/3/4/6/7) claim their own dedicated "Create
    **`docs/<folder>/GATE_P<N>.md`**" file (GATE_FILE_CLAIM_RE); gate-p5
    claims a differently-shaped artifact instead -- setting the `gate:`
    frontmatter field on the shared docs/planning/SPRINT.md
    (SPRINT_GATE_FIELD_CLAIM_RE) -- because it has no dedicated gate file of
    its own (WI-0129: SPRINT.md *is* gate-p5's gate artifact).

    `commands_dir` defaults to the real, tracked `commands/` tree
    (`REPO_ROOT / "commands"`); tests that need to exercise the guards
    below without mutating a tracked file pass a scratch copy instead --
    see `GateFileClaimParserGuardRedProofTest`.

    Keyed off each file's own FILENAME (`path.stem`, e.g. "gate-p3"), never
    off a digit captured out of the matched claim text -- code review found
    two failure shapes in an earlier version that keyed off the captured
    digit alone, both still guarded here for the GATE_FILE_CLAIM_RE shape
    (the SPRINT_GATE_FIELD_CLAIM_RE shape carries no digit to misattribute,
    so it is instead guarded by requiring the match come from "gate-p5"
    specifically -- see below):

    * Misattribution: if `gate-p3.md` ever typo'd its own claim to name
      `GATE_P4.md`, keying off the captured digit would file the claim
      under "gate-p4" -- silently clobbering or being clobbered by
      gate-p4.md's own real claim, depending on sort order, since nothing
      cross-checked the parsed digit against the filename it came from.
      Guarded: the digit inside the matched sentence must agree with the
      filename's own digit, or this raises loudly instead of filing the
      claim under the wrong key.
    * Silent absence: a top-level `gate-pN.md` whose claim sentence has a
      different shape than BOTH patterns above (different verb, no bold,
      wrapped across two lines) produces no regex match at all. This raises
      loudly instead of vanishing from the result -- there is no longer an
      exemption list a genuinely new no-claim gate could quietly hide
      behind (gate-p5 no longer needs one: it makes a claim too, just a
      differently-shaped one).
    * Cross-shape misattribution: if some OTHER gate-pN.md's claim sentence
      ever happened to match SPRINT_GATE_FIELD_CLAIM_RE (e.g. a future gate
      also documented as setting a shared living document's frontmatter),
      filing it under that gate's own key would be correct on its face but
      is exactly the kind of claim shape this parser has not been taught to
      generalise -- guarded by requiring gate-p5 specifically for this
      pattern; any other gate matching it raises loudly rather than being
      silently accepted as "another SPRINT-shaped gate".

    Deliberately does not read the four `gate-p6-qa.md` / `gate-p6-
    security.md` / `gate-p7-business.md` / `gate-p7-tech.md` sub-gate files
    (glob is `gate-p[0-9].md`, a single trailing digit) -- each of those
    says "This sub-gate does not write its own file", so they make no
    claim to parse. This is WI-0129's own methodology (read each command's
    own claim) applied to the test, not just the production fix, so this
    parser cannot repeat the F1 defect's original mistake of treating
    every `docs/<phase>/GATE_PX.md` *mention* (e.g. a sub-gate's "consumed
    by ... to compose docs/quality/GATE_P6.md") as a write claim.
    """
    if commands_dir is None:
        commands_dir = REPO_ROOT / "commands"
    claims = {}
    for path in sorted(commands_dir.glob("gate-p[0-9].md")):
        gate = path.stem
        content = path.read_text(encoding="utf-8")
        match = GATE_FILE_CLAIM_RE.search(content)
        if match is not None:
            claimed_gate = f"gate-p{match.group(2)}"
            if claimed_gate != gate:
                raise AssertionError(
                    f"{path.name} claims to write a GATE_P{match.group(2)}.md "
                    f"file -- that digit disagrees with the file's own name "
                    f"({gate}). Fix the claim sentence or the filename; this "
                    f"parser refuses to guess which one is right."
                )
            claims[gate] = match.group(1)
            continue

        sprint_match = SPRINT_GATE_FIELD_CLAIM_RE.search(content)
        if sprint_match is not None:
            if gate != "gate-p5":
                raise AssertionError(
                    f"{path.name} matches the SPRINT.md frontmatter-field "
                    f"claim shape, but only gate-p5 is known to make that "
                    f"kind of claim -- either this is a genuinely new "
                    f"SPRINT-shaped gate (extend this guard deliberately) "
                    f"or {path.name}'s prose accidentally matches a pattern "
                    f"meant for a different file."
                )
            claims[gate] = sprint_match.group(1)
            continue

        raise AssertionError(
            f"{path.name} makes no recognised gate-file claim -- neither "
            f"'Create **`docs/.../GATE_P<N>.md`**' (GATE_FILE_CLAIM_RE) nor "
            f"gate-p5's SPRINT.md frontmatter-field claim "
            f"(SPRINT_GATE_FIELD_CLAIM_RE). Its claim sentence changed shape "
            f"(update the matching pattern) or this is a genuinely new "
            f"no-claim or differently-shaped gate."
        )
    return claims


class GateFileClaimParserGuardRedProofTest(unittest.TestCase):
    """RED proof for both defect shapes `_parse_gate_file_claims()`'s two
    guards catch (code review round on WI-0129 F1/F2, 29.08.2026) -- see
    that function's own docstring for the failure modes named below.

    Both defects are introduced into a SCRATCH COPY of `commands/`
    (`shutil.copytree` into a `tempfile.mkdtemp()` dir), never into the
    tracked tree -- CONTRIBUTING.md's "Derive a contract test's expectation
    from the other artifact, not the code under test" section two headings
    up names exactly the discipline this class's own fixture would violate
    by editing `commands/gate-p3.md` in place. `setUp` gives every test its
    own fresh copy; `tearDown` (via `addCleanup`) removes it regardless of
    outcome, so a failing assertion can never leave a stray temp dir.

    Measured against the parser as it stood before this fix (keying claims
    off `match.group(2)` alone, `if match:` with no `else`): neither
    mutation below raised anything at all -- the misattribution mutation
    silently filed the claim under "gate-p4" instead of "gate-p3", and the
    reworded-sentence mutation silently dropped "gate-p3" from the result,
    both indistinguishable from correct or from gate-p5's genuine no-claim
    case. That is what "RED proof" means here: written to fail against the
    pre-fix parser, passing only once the two guards exist."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))
        self.commands_copy = Path(self.tmp_root) / "commands"
        __import__("shutil").copytree(REPO_ROOT / "commands", self.commands_copy)

    def _mutate_gate_p3(self, old: str, new: str) -> None:
        path = self.commands_copy / "gate-p3.md"
        content = path.read_text(encoding="utf-8")
        self.assertIn(
            old,
            content,
            f"fixture assumption stale: {old!r} not found in the scratch "
            f"copy of gate-p3.md -- update this test to match the current "
            f"claim sentence",
        )
        path.write_text(content.replace(old, new, 1), encoding="utf-8")

    def test_misattributed_digit_raises_instead_of_filing_under_the_wrong_gate(self):
        """gate-p3.md's own claim SENTENCE typo'd to name GATE_P4.md, its
        digit disagreeing with its own filename ("gate-p3"). Before this
        fix: no exception, claims["gate-p4"] silently overwritten or
        overwriting gate-p4.md's own real claim depending on sort order.

        Anchored on the FULL claim sentence (matching the sibling test
        below), not the bare "GATE_P3.md" substring -- code review found
        that substring also appears at three other lines in gate-p3.md
        (a detail-table cross-reference, an artefact listing, and a
        "Write" instruction outside the parsed claim sentence), so a bare
        `.replace(old, new, 1)` would have silently mutated whichever of
        those four occurrences happens to sort first in the file today,
        not necessarily the one the parser actually reads -- correct only
        by the accident of the claim sentence being positionally first.
        """
        self._mutate_gate_p3(
            "Create **`docs/architecture/GATE_P3.md`** with:",
            "Create **`docs/architecture/GATE_P4.md`** with:",
        )
        with self.assertRaises(AssertionError) as ctx:
            _parse_gate_file_claims(self.commands_copy)
        self.assertIn("gate-p3.md", str(ctx.exception))
        self.assertIn("disagrees", str(ctx.exception))

    def test_unrecognised_claim_sentence_shape_raises_instead_of_vanishing(self):
        """gate-p3.md's claim sentence reworded to drop the recognised
        "Create **`...`**" shape entirely, and not accidentally matching
        the SPRINT_GATE_FIELD_CLAIM_RE shape either. Before the F1/F2 fix:
        no exception, "gate-p3" silently absent from the result --
        indistinguishable from a genuine no-claim gate. There is no longer
        an exemption list a case like this could quietly hide behind, so
        it must raise, not vanish."""
        self._mutate_gate_p3(
            "Create **`docs/architecture/GATE_P3.md`** with:",
            "Write the architecture gate file with:",
        )
        with self.assertRaises(AssertionError) as ctx:
            _parse_gate_file_claims(self.commands_copy)
        self.assertIn("gate-p3.md", str(ctx.exception))
        self.assertIn("no recognised gate-file claim", str(ctx.exception))

    def test_gate_p3_accidentally_matching_the_sprint_shape_raises(self):
        """If gate-p3.md's claim sentence were ever reworded to accidentally
        match SPRINT_GATE_FIELD_CLAIM_RE (the shape reserved for gate-p5's
        differently-structured SPRINT.md claim), the cross-shape
        misattribution guard must raise rather than silently filing gate-p3
        under a claim pattern meant for a different gate."""
        self._mutate_gate_p3(
            "Create **`docs/architecture/GATE_P3.md`** with:",
            "**Set `docs/planning/SPRINT.md`'s frontmatter field `gate:`** with:",
        )
        with self.assertRaises(AssertionError) as ctx:
            _parse_gate_file_claims(self.commands_copy)
        self.assertIn("gate-p3.md", str(ctx.exception))
        self.assertIn("only gate-p5", str(ctx.exception))


class GateFileClaimsStructuralTest(unittest.TestCase):
    """Pins which top-level `gate-pN.md` commands claim to write, and what,
    parsed straight from each file's own statement -- not from a
    hand-maintained table. (The PO's own first attempt at this table, done
    by grepping every `docs/<phase>/GATE_PX.md` mention, mis-classified
    gate-p7 as ambiguous by conflating `gate-p7-tech.md`'s *read*-reference
    to `docs/quality/GATE_P6.md` with a *write* claim -- this parser only
    matches the literal claim sentences, so it does not repeat that
    mistake.)"""

    def test_all_eight_gates_claim_an_artifact(self):
        claims = _parse_gate_file_claims()
        self.assertEqual(
            set(claims),
            {"gate-p0", "gate-p1", "gate-p2", "gate-p3", "gate-p4", "gate-p5", "gate-p6", "gate-p7"},
        )

    def test_gate_p5_claims_sprint_md_not_a_phase_folder_gate_file(self):
        """/gate-p5 (commands/gate-p5.md) never writes a dedicated gate
        file of its own -- its claim names docs/planning/SPRINT.md's own
        `gate:` frontmatter field instead (WI-0129: SPRINT.md *is* its gate
        artifact), a differently-shaped claim than the other seven's
        "Create **`docs/<folder>/GATE_P<N>.md`**"."""
        claims = _parse_gate_file_claims()
        self.assertEqual(claims["gate-p5"], "docs/planning/SPRINT.md")

    def test_claimed_paths_match_the_phase_folder_convention(self):
        claims = _parse_gate_file_claims()
        self.assertEqual(
            claims,
            {
                "gate-p0": "docs/discovery/GATE_P0.md",
                "gate-p1": "docs/concept/GATE_P1.md",
                "gate-p2": "docs/validation/GATE_P2.md",
                "gate-p3": "docs/architecture/GATE_P3.md",
                "gate-p4": "docs/planning/GATE_P4.md",
                "gate-p5": "docs/planning/SPRINT.md",
                "gate-p6": "docs/quality/GATE_P6.md",
                "gate-p7": "docs/launch/GATE_P7.md",
            },
        )


class GateFilePathsMatchesTheCommandsClaimTest(unittest.TestCase):
    """Drift guard: the production mapping (`cc.GATE_FILE_PATHS`, sourced
    from `scripts/lib/gate_checklists.py`) must equal what the gate-pN.md
    commands themselves claim to write, parsed independently above. If a
    future doc restructuring moves a gate's file to a new folder and only
    one side is updated, this fails before the behavioural test below ever
    gets a chance to explain why."""

    def test_production_mapping_equals_parsed_claims(self):
        self.assertEqual(cc.GATE_FILE_PATHS, _parse_gate_file_claims())


class CheckGatePassedProbesThePhaseFolderPathTest(unittest.TestCase):
    """The RED proof for WI-0129 F1: `check_gate_passed` must probe the
    exact path each gate-pN.md command itself claims to write (asserted
    above), not the three flat legacy paths (`docs/GATE_P4.md`,
    `docs/GATE-P4.md`, `docs/gate-p4.md`) the pre-fix implementation
    probed instead. No command, script, template or doc in this repo ever
    WRITES to any of those three flat shapes (grepped repo-wide for
    `docs/GATE_P`, `docs/GATE-P`, `docs/gate-p[0-9]`, 29.08.2026 -- the
    only hits outside this test file are prose that MENTIONS the pattern
    while describing this very fix, in CONTRIBUTING.md's worked example
    and this module's own docstring in command-check.py; re-verified the
    same day after both were added, still zero WRITE targets) -- the
    entire verdict-parsing branch inside `check_gate_passed` was
    unreachable in any project that follows the shipped gate commands.

    Measured against the unfixed tool (before this fix, HEAD 98a6b0a):
    `test_go_verdict_at_the_claimed_path_is_passed` fails for all seven
    gates -- `check_gate_passed` returns `False` for a project whose ONLY
    artefact is the exact file its own gate-pN.md command says it
    writes, with an explicit `Verdict: Go`, and no `docs/HANDOVER.md` to
    fall back on."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def test_go_verdict_at_the_claimed_path_is_passed(self):
        for gate, rel_path in _parse_gate_file_claims().items():
            with self.subTest(gate=gate, path=rel_path):
                project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
                full_path = project_dir / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(
                    f"---\ngate: {_passing_verdict_for(rel_path)}\n---\n", encoding="utf-8"
                )
                passed, reason = cc.check_gate_passed(gate, str(project_dir))
                self.assertTrue(passed, reason)

    def test_no_go_verdict_at_the_claimed_path_is_not_passed(self):
        for gate, rel_path in _parse_gate_file_claims().items():
            with self.subTest(gate=gate, path=rel_path):
                project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
                full_path = project_dir / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(
                    f"---\ngate: {_blocking_verdict_for(rel_path)}\n---\n", encoding="utf-8"
                )
                passed, reason = cc.check_gate_passed(gate, str(project_dir))
                self.assertFalse(passed)

    def test_the_three_legacy_flat_paths_are_no_longer_probed(self):
        """The three pre-fix candidate paths are dropped outright (no
        evidence, repo-wide, that any of them was ever a real write
        target -- see class docstring). A file placed at ANY of the three
        old flat shapes must no longer satisfy the gate -- all three, not
        only the underscore-uppercase one: an earlier version of this test
        exercised just `docs/GATE_P<N>.md` while its own docstring claimed
        all three, which would have missed a fix that dropped only that
        one shape and left the other two reachable by accident."""
        for gate, rel_path in _parse_gate_file_claims().items():
            phase = gate.replace("gate-", "").upper()  # "gate-p3" -> "P3"
            for legacy_filename in (f"GATE_{phase}.md", f"GATE-{phase}.md", f"{gate}.md"):
                with self.subTest(gate=gate, legacy_filename=legacy_filename):
                    project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
                    docs = project_dir / "docs"
                    docs.mkdir(parents=True, exist_ok=True)
                    (docs / legacy_filename).write_text(
                        f"---\ngate: {_passing_verdict_for(rel_path)}\n---\n", encoding="utf-8"
                    )
                    passed, reason = cc.check_gate_passed(gate, str(project_dir))
                    self.assertFalse(passed)


class GateP5UsesSprintMdTest(unittest.TestCase):
    """WI-0129 gives gate-p5 an entry in GATE_FILE_PATHS for the first time
    -- `docs/planning/SPRINT.md`, the one gate artifact that is not its own
    dedicated `GATE_P*.md` file. This replaces the pre-fix class that
    pinned gate-p5's ABSENCE from the mapping; that absence is exactly what
    this tranche changes."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def test_gate_p5_is_mapped_to_sprint_md(self):
        self.assertEqual(cc.GATE_FILE_PATHS["gate-p5"], "docs/planning/SPRINT.md")

    def test_a_phantom_gate_p5_md_at_the_old_guessed_path_does_not_satisfy_gate_p5(self):
        """A hand-authored `docs/planning/GATE_P5.md` (the naming pattern
        every other gate uses, and the guess the pre-fix code explicitly
        refused to make) is not gate-p5's real artifact -- only
        docs/planning/SPRINT.md's own `gate:` field is read."""
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        planning = project_dir / "docs" / "planning"
        planning.mkdir(parents=True)
        (planning / "GATE_P5.md").write_text("---\ngate: go\n---\n", encoding="utf-8")
        passed, reason = cc.check_gate_passed("gate-p5", str(project_dir))
        self.assertFalse(passed)

    def test_sprint_md_with_gate_done_unblocks_gate_p5(self):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        write_gate_file(project_dir, "gate-p5", "done")
        passed, reason = cc.check_gate_passed("gate-p5", str(project_dir))
        self.assertTrue(passed, reason)

    def test_sprint_md_with_gate_not_done_blocks_gate_p5(self):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        write_gate_file(project_dir, "gate-p5", "not_done")
        passed, reason = cc.check_gate_passed("gate-p5", str(project_dir))
        self.assertFalse(passed)

    def test_gate_p5_still_falls_back_to_handover_when_sprint_md_is_absent(self):
        """Finding F5 (out of scope for this tranche): when SPRINT.md does
        not exist at all, gate-p5 falls through to the same HANDOVER.md
        phase-comparison fallback every other gate uses -- unchanged."""
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        docs = project_dir / "docs"
        docs.mkdir(parents=True)
        (docs / "HANDOVER.md").write_text("Phase: P6\n", encoding="utf-8")
        passed, reason = cc.check_gate_passed("gate-p5", str(project_dir))
        self.assertTrue(passed, reason)


class GateP5EndToEndTest(unittest.TestCase):
    """gate-p5 end to end, through the real CLI: docs/planning/SPRINT.md's
    `gate:` field unblocks/blocks /p6-functional exactly like every other
    gate unblocks/blocks its own successor commands."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_root, ignore_errors=True))

    def _run(self, verdict: str):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        for f in cc.COMMAND_PREREQUISITES["p6-functional"]["files"]:
            full = project_dir / f
            if f.endswith("/"):
                full.mkdir(parents=True, exist_ok=True)
                (full / ".keep").write_text("x", encoding="utf-8")
            else:
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text("x", encoding="utf-8")
        write_gate_file(project_dir, "gate-p5", verdict)
        result = __import__("subprocess").run(
            [sys.executable, str(SCRIPT_PATH), "p6-functional", str(project_dir)],
            capture_output=True,
            text=True,
        )
        return result

    def test_sprint_gate_done_unblocks_p6_functional(self):
        result = self._run("done")
        self.assertEqual(result.stdout.strip(), "ready")
        self.assertEqual(result.returncode, 0)

    def test_sprint_gate_not_done_blocks_p6_functional(self):
        result = self._run("not_done")
        self.assertEqual(result.stdout.strip().splitlines()[0], "blocked")
        self.assertEqual(result.returncode, 1)


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
        passed, reason = cc.check_gate_passed("gate-p3", str(project_dir))
        self.assertTrue(passed, reason)

    def test_current_phase_at_or_before_the_gate_is_not_passed(self):
        project_dir = Path(tempfile.mkdtemp(dir=self.tmp_root))
        docs = project_dir / "docs"
        docs.mkdir(parents=True)
        (docs / "HANDOVER.md").write_text("Phase: P2\n", encoding="utf-8")
        passed, reason = cc.check_gate_passed("gate-p3", str(project_dir))
        self.assertFalse(passed)


if __name__ == "__main__":
    unittest.main()
