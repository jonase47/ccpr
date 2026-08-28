"""test_next_steps_lists.py -- WI-0126 tranche 2: per-entry coverage for the
three enumerated lists in scripts/lib/next_steps.py.

A NEW module, deliberately separate from test_next_steps_placement.py (which
covers a single, narrow WI-0024 parser-anchor fix in
`extract_phase_from_handover` and has nothing to do with the three lists
below). Keeping this module focused on "is every entry of these three lists
tested" avoids diluting either file's own scope statement.

Three lists, three different exposure shapes:
  - PHASE_SEQUENCES (:13, 9 phases / 50 commands) drives get_allowed_commands
    -- its one real consumer. scripts/command-check.py imports the name
    (`from next_steps import extract_phase_from_handover, PHASE_SEQUENCES`,
    :15) but never references it again: `grep -n "PHASE_SEQUENCES"
    scripts/command-check.py` (measured 28.08.2026) returns exactly that one
    line. command-check.py derives phases with its own get_command_phase()
    regex (:18) and its own COMMAND_PREREQUISITES dict (:31), neither derived
    from PHASE_SEQUENCES. That import is a dead import -- a second, smaller
    instance of the same shape UTILITY_COMMANDS is below -- recorded here as
    a finding, not fixed: removing it edits a shipped script outside this
    module's write boundary and is a PO call. Missing from the audit that
    produced WI-0126; the largest list in the file.
  - GATE_TRANSITIONS (:26, 8 entries) drives get_allowed_commands and is
    DERIVABLE from PHASE_SEQUENCES (every target is the next phase's first
    command -- the constant's own comment says so, ":25"). Nothing tested
    that derivation before this module.
  - UTILITY_COMMANDS (:38, 8 entries) is measured DEAD: `grep -rn
    "UTILITY_COMMANDS"` across every .py, .sh and .md in this repo
    (28.08.2026) returns only its own definition line. See
    UtilityCommandsVocabularyTest's docstring for the argued verdict.

House lesson carried over from tranche 1 (test_conformance_run.py's
PhaseFolderNamesBindingRedProofTest / ContractTableExitCodeBindingRedProofTest):
importing a list and sweeping it protects against an ADDED entry, never a
REMOVED one -- the sweep just shrinks and stays green. Every list below gets
both a per-entry sweep (catches a typo/rename -- G-109's "swap", not just
presence) AND a literal count pin (catches a removal, which a sweep alone
cannot). The *-RedProofTest classes are the mutation proof for exactly that
distinction, and run every time this module runs -- they operate on
in-memory copies of the already-imported list values (never a scratch file
on disk, never the shipped module: cross-artifact-binding-tests.md's
argument applies here too -- an in-memory copy has no file to forget).

Constants are imported from source, never retyped (contract.py's
STATUS_VALUES-sweep precedent, per this tranche's briefing).
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from next_steps import (  # noqa: E402
    GATE_TRANSITIONS,
    PHASE_SEQUENCES,
    UTILITY_COMMANDS,
    get_allowed_commands,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "commands"


def command_doc_exists(name: str) -> bool:
    return (COMMANDS_DIR / ("%s.md" % name)).is_file()


def next_phase(phase: str) -> str:
    """"p3" -> "p4". Only ever called with a gate's own originating phase
    (p0..p7), never p8 (which has no gate -- see InvariantA below)."""
    return "p%d" % (int(phase[1:]) + 1)


# ---------------------------------------------------------------------------
# Deliverable 1: PHASE_SEQUENCES per-entry existence sweep + count pins.
# ---------------------------------------------------------------------------

class PhaseSequencesExistenceTest(unittest.TestCase):
    def test_phase_count_is_pinned_at_9(self):
        self.assertEqual(len(PHASE_SEQUENCES), 9)

    def test_total_command_count_is_pinned_at_50(self):
        total = sum(len(commands) for commands in PHASE_SEQUENCES.values())
        self.assertEqual(total, 50)

    def test_every_command_has_a_real_command_doc(self):
        for phase, commands in PHASE_SEQUENCES.items():
            for command in commands:
                with self.subTest(phase=phase, command=command):
                    self.assertTrue(
                        command_doc_exists(command),
                        "commands/%s.md does not exist" % command,
                    )


class PhaseSequencesTypoRedProofTest(unittest.TestCase):
    """Swaps each PHASE_SEQUENCES entry, one at a time, for a name with no
    commands/<name>.md, on an in-memory copy of the command list for that
    phase only. Confirms the existence sweep above would flag exactly the
    mutated entry while every neighbour (same phase and every other phase)
    stays green -- G-109: the mutation changes structure (a rename), not
    merely presence."""

    def test_a_typo_d_entry_is_caught_by_the_existence_check(self):
        for phase, commands in PHASE_SEQUENCES.items():
            for i, command in enumerate(commands):
                with self.subTest(phase=phase, command=command):
                    mutated = list(commands)
                    mutated[i] = command + "-typo-zzz"

                    self.assertFalse(command_doc_exists(mutated[i]))
                    for j, neighbour in enumerate(mutated):
                        if j != i:
                            self.assertTrue(command_doc_exists(neighbour), neighbour)


class PhaseSequencesRemovalRedProofTest(unittest.TestCase):
    """Removes one PHASE_SEQUENCES command at a time -- not from a rebuilt
    in-memory copy, but via unittest.mock.patch.dict against the real,
    already-imported dict object (PHASE_SEQUENCES here IS next_steps.py's
    module-level dict: `from next_steps import PHASE_SEQUENCES` binds this
    name to the same object, it does not copy it). patch.dict saves the
    original mapping and restores it on context exit, even if an assertion
    inside raises.

    This closes the gap a prior version of this test had: rebuilding a
    mutated dict via a dict comprehension and re-summing it re-implements the
    count-pin's formula on a disconnected copy, near-tautological (a list
    minus one element is one element shorter) and coupled to nothing the
    shipped module actually reads. Patching the real object instead means
    the count computed below is the SAME formula read off the SAME object
    get_allowed_commands consults, and the get_allowed_commands call proves
    the shipped code path reacts: before the patch, get_allowed_commands(
    phase, next_step=command) always returns a list starting with `command`
    (next_steps.py:132-138, the next_step branch fires because `command in
    commands` is true); after the patch, `command` is no longer in the
    mutated list, so that branch cannot fire and the returned list can never
    contain `command` -- true for every phase and index, gate commands
    included, unlike the phase-sequence "successor" (last_command) branch,
    whose slice can coincidentally collide with the mutated commands[:3]
    fallback near the start of a short phase."""

    def test_removing_one_command_breaks_the_total_count_pin(self):
        for phase, commands in PHASE_SEQUENCES.items():
            for command in commands:
                with self.subTest(phase=phase, command=command):
                    before = get_allowed_commands(phase, next_step=command)
                    self.assertEqual(before[0], command)

                    mutated_commands = [c for c in commands if c != command]
                    with patch.dict(PHASE_SEQUENCES, {phase: mutated_commands}):
                        total = sum(len(c) for c in PHASE_SEQUENCES.values())
                        self.assertEqual(total, 49)
                        self.assertNotEqual(total, 50)

                        after = get_allowed_commands(phase, next_step=command)
                        self.assertNotIn(command, after)

                    # patch.dict restored the original list for this phase
                    self.assertEqual(PHASE_SEQUENCES[phase], commands)


class PhaseCountRemovalRedProofTest(unittest.TestCase):
    """Removes one whole phase key at a time from the real PHASE_SEQUENCES
    object (patch.dict, restored on exit even if an assertion raises -- see
    PhaseSequencesRemovalRedProofTest's docstring for why patching the real
    object beats rebuilding a copy) and confirms the phase-count pin (9)
    would go red for exactly that removal. Also proves get_allowed_commands
    reacts: `PHASE_SEQUENCES.get(phase, [])` (next_steps.py:127) returns []
    for a phase key that no longer exists, and `if not commands: return []`
    (:128-129) makes that deterministic -- no coincidental-collision risk,
    since every real phase currently returns a non-empty result."""

    def test_removing_one_phase_breaks_the_phase_count_pin(self):
        for phase in list(PHASE_SEQUENCES):
            with self.subTest(phase=phase):
                with patch.dict(PHASE_SEQUENCES):
                    del PHASE_SEQUENCES[phase]
                    self.assertEqual(len(PHASE_SEQUENCES), 8)
                    self.assertNotEqual(len(PHASE_SEQUENCES), 9)
                    self.assertEqual(get_allowed_commands(phase), [])

                # patch.dict restored the deleted key
                self.assertIn(phase, PHASE_SEQUENCES)


# ---------------------------------------------------------------------------
# Deliverable 2: PHASE_SEQUENCES behavioural sweep via get_allowed_commands.
# ---------------------------------------------------------------------------

class GetAllowedCommandsSequenceTest(unittest.TestCase):
    """get_allowed_commands(phase, last_command=cmd) returns cmd's own
    successors within its phase (commands[idx+1:idx+4]) -- swept for every
    phase and every non-gate command in it, per the briefing's per-command
    preference over a single representative per phase.

    Gate commands (p0..p7's terminal "gate-pN") are deliberately excluded
    here: get_allowed_commands checks `cmd in GATE_TRANSITIONS` BEFORE the
    phase-sequence lookup (next_steps.py:146, ahead of :150), so a gate's
    own last_command is intercepted and returns [GATE_TRANSITIONS[cmd]],
    never the (always-empty, since a gate is each sequence's last element)
    in-phase successor slice this class checks. That branch is
    GateTransitionsBehaviouralTest's job below, not this one's -- measured
    directly (this test failed for all 8 gates, expecting [] and getting
    [GATE_TRANSITIONS[cmd]], before this exclusion was added).

    This class has no count assertion of its own; it inherits its
    degenerate-input guard (an empty PHASE_SEQUENCES value) from the sibling
    count-pin classes above (PhaseSequencesExistenceTest et al.). Extracting
    this class on its own later would silently lose that guard."""

    def test_each_command_returns_its_successors_in_the_same_phase(self):
        for phase, commands in PHASE_SEQUENCES.items():
            for idx, command in enumerate(commands):
                if command in GATE_TRANSITIONS:
                    continue
                with self.subTest(phase=phase, command=command):
                    expected = commands[idx + 1: idx + 4]
                    self.assertEqual(
                        get_allowed_commands(phase, last_command=command),
                        expected,
                    )


# ---------------------------------------------------------------------------
# Deliverable 3: GATE_TRANSITIONS per-entry test + invariant A/B.
# ---------------------------------------------------------------------------

class GateTransitionsCountTest(unittest.TestCase):
    def test_gate_count_is_pinned_at_8(self):
        self.assertEqual(len(GATE_TRANSITIONS), 8)


class GateTransitionsBehaviouralTest(unittest.TestCase):
    """For each of the 8 gates, get_allowed_commands(phase, last_command=
    gate) returns exactly [target] -- the GATE_TRANSITIONS branch in
    get_allowed_commands (next_steps.py:146) fires before the phase-sequence
    lookup and is independent of which non-empty phase is passed; the gate's
    own originating phase is used here to match real call sites."""

    def test_each_gate_returns_exactly_its_target(self):
        for gate, target in GATE_TRANSITIONS.items():
            with self.subTest(gate=gate):
                phase = gate.replace("gate-", "")
                self.assertEqual(
                    get_allowed_commands(phase, last_command=gate),
                    [target],
                )


class GateTransitionsRemovalRedProofTest(unittest.TestCase):
    """Removes one gate key at a time from the real GATE_TRANSITIONS object
    (patch.dict, restored on exit -- see PhaseSequencesRemovalRedProofTest's
    docstring) and confirms the count pin (8) would go red for exactly that
    removal. Also proves get_allowed_commands reacts: with the gate removed
    from GATE_TRANSITIONS, `cmd in GATE_TRANSITIONS` (next_steps.py:146) is
    now false, so the function falls through to the phase-sequence lookup;
    the gate is still the LAST entry of its own phase's PHASE_SEQUENCES list
    (untouched here), so `commands[idx + 1 : idx + 4]` with idx ==
    len(commands) - 1 is deterministically []. Before the removal the same
    call always returns [target], and a GATE_TRANSITIONS value is never an
    empty string, so [] vs [target] never coincidentally collide."""

    def test_removing_one_gate_breaks_the_count_pin(self):
        for gate, target in list(GATE_TRANSITIONS.items()):
            with self.subTest(gate=gate):
                phase = gate.replace("gate-", "")
                self.assertEqual(
                    get_allowed_commands(phase, last_command=gate), [target]
                )

                with patch.dict(GATE_TRANSITIONS):
                    del GATE_TRANSITIONS[gate]
                    self.assertEqual(len(GATE_TRANSITIONS), 7)
                    self.assertNotEqual(len(GATE_TRANSITIONS), 8)
                    self.assertEqual(
                        get_allowed_commands(phase, last_command=gate), []
                    )

                # patch.dict restored the deleted key
                self.assertEqual(GATE_TRANSITIONS[gate], target)


class GateTransitionsBindingTest(unittest.TestCase):
    """Invariant B: next_steps.py:25's own comment reads 'gate -> first
    command of next phase'. Nothing tested that GATE_TRANSITIONS actually
    holds that relationship before this test -- it is DERIVABLE from
    PHASE_SEQUENCES and duplicates it. Computed from PHASE_SEQUENCES here,
    never retyped, so the two constants drifting apart would fail this
    test rather than pass silently."""

    def test_every_gate_transition_matches_the_next_phases_first_command(self):
        for gate, target in GATE_TRANSITIONS.items():
            with self.subTest(gate=gate):
                phase = gate.replace("gate-", "")
                expected = PHASE_SEQUENCES[next_phase(phase)][0]
                self.assertEqual(target, expected)


class GateTransitionsBindingRedProofTest(unittest.TestCase):
    """Confirms the equality assertion above is sensitive to a genuine
    mismatch, not merely to inequality-in-general (G-135) -- for every gate,
    a deliberately corrupted target does NOT equal the real next-phase-first-
    command, proving the comparison direction the binding test relies on."""

    def test_a_mismatched_target_is_caught(self):
        for gate, target in GATE_TRANSITIONS.items():
            with self.subTest(gate=gate):
                phase = gate.replace("gate-", "")
                expected = PHASE_SEQUENCES[next_phase(phase)][0]
                wrong_target = target + "-mutated"
                self.assertNotEqual(wrong_target, expected)


class InvariantAGatePlacementTest(unittest.TestCase):
    """Invariant A: p0..p7 each end their own sequence with their own gate;
    p8 is terminal and has none. This is what makes GATE_TRANSITIONS and
    PHASE_SEQUENCES's relationship well-defined (Invariant B above assumes
    it)."""

    def test_p0_through_p7_end_with_their_own_gate(self):
        for n in range(8):
            phase = "p%d" % n
            with self.subTest(phase=phase):
                self.assertEqual(PHASE_SEQUENCES[phase][-1], "gate-%s" % phase)

    def test_p8_has_no_gate(self):
        # Vacuously true if p8's list were ever emptied -- covered in
        # practice by test_total_command_count_is_pinned_at_50 above, which
        # would go red first.
        self.assertTrue(all(not c.startswith("gate-") for c in PHASE_SEQUENCES["p8"]))


class InvariantAGatePlacementRedProofTest(unittest.TestCase):
    def test_a_missing_terminal_gate_is_caught(self):
        for n in range(8):
            phase = "p%d" % n
            with self.subTest(phase=phase):
                mutated_last = PHASE_SEQUENCES[phase][-1] + "-not-a-gate"
                self.assertNotEqual(mutated_last, "gate-%s" % phase)


# ---------------------------------------------------------------------------
# Deliverable 4: UTILITY_COMMANDS -- dead code, vocabulary pin only.
# ---------------------------------------------------------------------------

class UtilityCommandsVocabularyTest(unittest.TestCase):
    """UTILITY_COMMANDS (next_steps.py:38) is measured dead: `grep -rn
    "UTILITY_COMMANDS"` across every .py, .sh and .md in this repo
    (measured 28.08.2026) returns exactly its own definition line and
    nothing else. No code anywhere reads this constant -- not
    get_allowed_commands, not scripts/command-check.py, nothing under
    scripts/tests/ before this file. That means no BEHAVIOURAL per-entry
    test is possible: there is no observable effect to break by removing or
    renaming an entry, so no test here can claim "this entry drives X".

    What follows instead pins a VOCABULARY -- each of the 8 names
    corresponds to a real commands/<name>.md today, and there are exactly 8
    of them -- not a behaviour. This is honest per WI-0126's own acceptance
    criterion ("the audit explicitly states which lists it judged NOT to
    need this and why"): the reason is dead code, not oversight. If a
    future change wires UTILITY_COMMANDS into actual logic, this docstring's
    claim goes stale and a behavioural per-entry test (like
    GetAllowedCommandsSequenceTest above) becomes both possible and required
    at that point.
    """

    def test_total_command_count_is_pinned_at_8(self):
        self.assertEqual(len(UTILITY_COMMANDS), 8)

    def test_every_command_has_a_real_command_doc(self):
        for command in UTILITY_COMMANDS:
            with self.subTest(command=command):
                self.assertTrue(
                    command_doc_exists(command),
                    "commands/%s.md does not exist" % command,
                )


class UtilityCommandsRedProofTest(unittest.TestCase):
    """Unlike PhaseSequencesRemovalRedProofTest / PhaseCountRemovalRedProofTest
    / GateTransitionsRemovalRedProofTest above, this class's count-removal
    test does NOT patch the real UTILITY_COMMANDS object and show a shipped
    function react -- there is no such function to call.
    UtilityCommandsVocabularyTest's docstring already measured this: no code
    anywhere reads UTILITY_COMMANDS, so there is no production code path a
    removal could make react. The method below is what remains honest for a
    dead list: an in-memory length-formula check, named without "count_pin"
    to avoid implying the same evidence strength as the three classes above.
    See WI-0126's Result section (tranche 2, round 2) for the same
    disclosure."""

    def test_removing_one_entry_changes_the_length_by_one(self):
        for command in UTILITY_COMMANDS:
            with self.subTest(command=command):
                mutated = [c for c in UTILITY_COMMANDS if c != command]
                self.assertEqual(len(mutated), 7)
                self.assertNotEqual(len(mutated), 8)

    def test_a_typo_d_entry_is_caught_by_the_existence_check(self):
        for i, command in enumerate(UTILITY_COMMANDS):
            with self.subTest(command=command):
                mutated = list(UTILITY_COMMANDS)
                mutated[i] = command + "-typo-zzz"

                self.assertFalse(command_doc_exists(mutated[i]))
                for j, neighbour in enumerate(mutated):
                    if j != i:
                        self.assertTrue(command_doc_exists(neighbour), neighbour)


if __name__ == "__main__":
    unittest.main()
