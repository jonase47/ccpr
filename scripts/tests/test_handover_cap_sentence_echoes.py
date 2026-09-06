r"""test_handover_cap_sentence_echoes.py -- CCP-1151: the HANDOVER-cap
measurement sentence exists in two wordings, and this module pins exactly
where the older one still stands.

## The subject

One measured statement -- "<one X run> grew docs/HANDOVER.md by 1021 B,
i.e. ~20 % of the 5 KB cap" -- is hand-copied across this repository. The
terminology sweep's stage 2 (CCP-1151, PR #17) rewrote it in 97 `commands/`
files from the older wording to the swept one. Three echoes of the same
sentence live outside `commands/` and were not in that stage's scope, so
they still carry the older wording:

    hooks/agent-monitor.py:82                    the source measurement's own comment
    scripts/tests/test_handover_size_hook.py:77  the constant that quotes that comment
    scripts/tests/test_handover_size_hook.py:718 the docstring that quotes the constant

**This is a known, deliberate split, not an oversight.** It is recorded in
the stage-1 register (`docs/decisions/2026-09-05_skill-terminology-classification.md`
§12.8, "A divergence stage 2 has already created") and resolving it belongs
to **stage 4**, whose corpus is the runtime text under `hooks/` and the
guards that quote it. All three are rename targets (register class K3); none
is contract-bound.

## Why a test and not a register line

A note in a gitignored register cannot go red. Before this module, nothing in
the tree observed the split at all: the sweep could grow a fourth echo, or a
well-meaning repair could silently close one of the three, and the suite would
report the same 2692 OK either way. Stage 4 has to find **exactly three**, and
"exactly" has to be a machine statement by then, not a recollection.

Set equality, not a count, for the reason ADR-0012 obligation 2 gives: a count
cannot tell "one added" from "one added, one gone". The failure message names
both directions, so a bump is its own set proof.

## Scope, declared rather than implied

The scan reads **every tracked file** (`git ls-files`), with two declared
skips, both pinned in `DECLARED_SKIPS` below:

* `CHANGELOG.md` -- **protocol, deliberately excluded**. It carries two
  further echoes, in released entries about a past state, and those are not
  rewritten retroactively -- the same rule G-026's own fix step states and the
  same line `handbook/SYSTEM_OVERVIEW.md`'s Change History was held to during
  the `Manual/` -> `handbook/` rename. **Deliberately cited without line
  numbers**: every new entry is prepended, so a line citation here would be
  stale by the next commit -- which is the drift this module's own "Keys"
  section warns about, in the one place a machine check cannot reach.
  `ExclusionIsNotStaleTest` below checks that the exclusion still excuses
  something rather than sitting there dead.
* the two tracked PNGs under `docs/logo/`, which are not text.

Everything else tracked is scanned, and the boundary is enforced rather than
assumed: `scanned` and `skipped` partition the tracked tree, so a file quietly
dropped from the scan has to appear in the skipped set and reddens the pin. The
floor beside it covers the direction the set cannot see -- a tree that shrinks
without any file changing its bucket.

**What the pair still does not close**, stated because the sentence above reads
more airtight than the mechanism is: a `tracked_files()` regression that narrows
the scope while still returning the three declared skips AND staying above the
floor (organic growth elsewhere can pay for it) passes all three assertions.
That is the documented limitation of the `floor` group itself
(`pin_registry.PIN_GROUPS["floor"]`: "silent while the subject grows"), not a
gap peculiar to this module -- but it is a gap, and pretending otherwise is the
same defect as an unchecked number.

## The needle is assembled, never written out

`OLD_WORDING` and `SWEPT_WORDING` are built by concatenation. Written as
literals they would make this module its own finding: it scans the whole
tracked tree, itself included, and the count would move every time someone
edited a docstring here. The shape is this repository's existing answer to
the self-match case (`test_artifact_gate.py`'s `SelfMatchTest` and its
`"See " + self.NAME + " here"` fixtures). The consequence is the useful one:
this file is inside its own scope, so an echo introduced *here* fails like an
echo anywhere else.

## Keys, and what they cost

`(path, line, column)` with a **1-based character offset of the matched word**
-- the convention the stage-1 register uses for its own occurrence keys, so
the three entries below are the register's `82:83`, `77:26` and `718:23`
verbatim and can be compared against it without a translation step. Column,
not line alone, because two occurrences on one line are two occurrences
(G-153: `grep -c` counts lines and is systematically low on repeated tokens).

Line-keyed registries drift when text is inserted above a site; that cost is
paid knowingly here, exactly as `test_bsd_gnu_portability.py`'s
`EXEMPTED_SITES` pays it, and for the same gain: an EXCHANGE (one echo closed,
another opened) is visible, where a per-file tally or a count would not be.
"""

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = Path(__file__).resolve().parent

# Assembled, not written out -- see the module docstring's "The needle is
# assembled" section. Either wording spelled as a literal would put an
# occurrence of the scanned subject inside the scanner. That is not a
# hypothetical: the first draft of this file spelled both out in this very
# comment, and the pin below went red on ('...test_handover_cap_sentence_
# echoes.py', 91, 29) before the module was ever committed.
OLD_WORDING = "one " + "skill" + " run"
SWEPT_WORDING = "one " + "command" + " run"

# Offset from the start of OLD_WORDING to the word the register keys on.
WORD_OFFSET_IN_WORDING = len("one ")


# The three surviving echoes. Value = why this one is still here.
KNOWN_ECHOES = {
    ("hooks/agent-monitor.py", 82, 83):
        "the measurement's own comment above HANDOVER_WARN_PCT -- the source "
        "every other copy quotes. Stage 4 (runtime text under hooks/) owns it.",
    ("scripts/tests/test_handover_size_hook.py", 77, 26):
        "the comment above SINGLE_RUN_GROWTH_BYTES, which quotes the hook "
        "comment by name. It has to move with its source, not before it.",
    ("scripts/tests/test_handover_size_hook.py", 718, 23):
        "ThresholdDerivationTest's docstring, which quotes the constant above. "
        "Same commit as the other two or the three disagree again.",
}

# Every tracked file the scan does NOT read, and why. The set is pinned:
# a new binary, or a file quietly dropped from the scan, has to arrive here
# and be argued for.
DECLARED_SKIPS = {
    "CHANGELOG.md":
        "protocol. Historical entries are not rewritten retroactively; the "
        "two echoes it carries are statements about a past state.",
    "docs/logo/ccpr-wordmark-dark.png": "binary, not text",
    "docs/logo/ccpr-wordmark-light.png": "binary, not text",
}


def tracked_files():
    """Every path in the git index, in the tracked tree only.

    `git ls-files`, not a filesystem walk: the filesystem carries gitignored
    working state (`docs/HANDOVER.md`, `docs/decisions/`, `docs/memory/`),
    and a scope that includes the register describing this very split would
    measure itself -- the defect CCP-1151's scope v1 was rewritten to remove.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def scan_tree():
    """(found, scanned, skipped).

    `found` is a set of (path, line, column) keys for OLD_WORDING; `scanned`
    and `skipped` are the paths on each side of the scope boundary. Returning
    all three from one pass is what lets the scope be asserted as a partition
    instead of being re-derived by a second, differently-shaped walk.
    """
    found, scanned, skipped = set(), [], []
    for rel in tracked_files():
        if rel in DECLARED_SKIPS:
            skipped.append(rel)
            continue
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append(rel)
            continue
        scanned.append(rel)
        for lineno, line in enumerate(text.split("\n"), start=1):
            start = 0
            while True:
                hit = line.find(OLD_WORDING, start)
                if hit < 0:
                    break
                found.add((rel, lineno, hit + 1 + WORD_OFFSET_IN_WORDING))
                start = hit + 1
    return found, scanned, skipped


def _house_set_assertion():
    """`pin_registry.assert_set_matches`, imported LOCALLY.

    Local rather than module-level for the reason
    test_absence_only_assertions.py:1949 gives at its own call site:
    CONTRIBUTING.md pins in prose how many modules fail to import without
    `-t .`, and a new module-level import edge moves those numbers.

    Returned rather than wrapped: test_pin_inventory.py binds a `# pin:`
    marker to the assertion below it by recognising `assert_set_matches`
    **by name** (test_pin_inventory.py:102). What is matched is the **spelling
    of the local variable at the call site**, not the identity of the callable
    it holds -- `pin_registry._assertion_operands` compares `ast.Name.id`
    against the string, so this is a purely syntactic test and renaming the
    local variable breaks the binding even though the same function is called.
    A local wrapper with a different name therefore leaves every marker over it
    unbound -- measured, not assumed: the first draft of this module wrapped
    the call and `MarkerBindsToOneAssertionTest` reported both `set` markers as
    naming no pin-shaped assertion. That test is also the net: a future rename
    of the local variable goes red there rather than silently.
    """
    import sys as _sys
    _sys.path.insert(0, str(TESTS_DIR))
    from pin_registry import assert_set_matches
    return assert_set_matches


class SurvivingEchoesTest(unittest.TestCase):
    def test_the_old_wording_survives_in_exactly_the_declared_sites(self):
        """Both directions, and that is the whole point.

        A FOURTH echo -- the sweep creating a new copy of the older wording,
        or a stage-4 pass rewriting one site into the old form -- lands in
        `new:`. A CLOSED echo -- someone repairing one of the three ahead of
        stage 4, leaving the three sites disagreeing about a number they all
        quote -- lands in `gone:`. The count can only change deliberately,
        in either direction.
        """
        found, _scanned, _skipped = scan_tree()
        assert_set_matches = _house_set_assertion()
        # The declared side is the bare name, not `set(KNOWN_ECHOES)`:
        # pin_registry._sites_from_tree only recognises a module-level
        # DECLARED constant or a literal there, so wrapping it in `set(...)`
        # makes the assertion invisible to the inventory. `assert_set_matches`
        # takes the set of a dict itself.
        assert_set_matches(  # pin: set handover-cap-sentence-echoes
            self, KNOWN_ECHOES, found,
            "the surviving pre-sweep HANDOVER-cap echoes (CCP-1151 stage 4's "
            "corpus; see this module's docstring)",
        )

    def test_the_swept_wording_is_present_too(self):
        """The other half of the divergence, asserted positively.

        Without it, `found` matching the declared set proves nothing about the
        scan being able to see anything: a mis-assembled needle would find
        zero, and zero is not what this asserts. This one fires on real text
        the sweep wrote, through the same reader.
        """
        _found, scanned, _skipped = scan_tree()
        hits = [rel for rel in scanned
                if SWEPT_WORDING in (REPO_ROOT / rel).read_text(encoding="utf-8")]
        self.assertGreater(
            len(hits), 0,
            "not one file carries the swept wording -- either stage 2 was "
            "reverted or this scan reads nothing",
        )


class ScanScopeTest(unittest.TestCase):
    """KA-G-017: a check that reports no scope is not a pass."""

    def test_scanned_and_skipped_partition_the_tracked_tree(self):
        _found, scanned, skipped = scan_tree()
        self.assertEqual(
            sorted(tracked_files()), sorted(scanned + skipped),
            "the scan lost or duplicated a tracked path",
        )

    def test_the_scan_skips_only_what_it_declares(self):
        """The scope guard proper. `scanned` and `skipped` partition the
        tracked tree (above), so narrowing the scan has to show up as growth
        here -- and a new binary, which no reader can see into, has to be
        declared rather than silently dropped."""
        _found, _scanned, skipped = scan_tree()
        assert_set_matches = _house_set_assertion()
        assert_set_matches(  # pin: set handover-cap-sentence-scope
            self, DECLARED_SKIPS, set(skipped),
            "the files this scan does not read",
        )

    def test_the_scanned_scope_does_not_shrink(self):
        """The direction the set pin structurally cannot see: every file stays
        in its bucket while the tree itself gets smaller. Measured 06.09.2026
        at `f3b06f8` (`ef5a34b` + this module, the module already tracked):
        **352** tracked, 3 declared skips, 349 scanned -- this file included,
        see the docstring on why it is in its own scope. A floor, not an
        equality: files are added here weekly, and a pin that reddens on every
        unrelated addition gets bumped without being read."""
        _found, scanned, _skipped = scan_tree()
        self.assertGreaterEqual(  # pin: floor handover-cap-sentence-scope
            len(scanned), 349,
            "the scan reached {} file(s); it reached 349 when this floor was "
            "measured (06.09.2026). A shrinking scope is a blind scanner, not "
            "a clean tree.".format(len(scanned)),
        )


class ExclusionIsNotStaleTest(unittest.TestCase):
    def test_the_changelog_exclusion_still_excuses_something(self):
        """An exclusion that excuses nothing is a stale exclusion, and it
        should be deleted rather than left standing as an unexamined hole.
        Asserted positively: the file the scan refuses to read does in fact
        carry the wording it is excused for."""
        text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertGreater(
            text.count(OLD_WORDING), 0,
            "CHANGELOG.md no longer carries the pre-sweep wording, so its "
            "entry in DECLARED_SKIPS excuses nothing -- remove the exclusion "
            "instead of keeping an unscanned file",
        )


if __name__ == "__main__":
    unittest.main()
