"""test_memory_lint.py – End-to-end tests for scripts/memory-lint.sh.

Invokes the real entry point as a subprocess (`bash memory-lint.sh <project-dir>`)
rather than sourcing internals, so these tests also cover the report rendering and
the documented exit-code contract (0 clean, 1 warnings, 2 errors, 3 configuration error).

HOME is redirected to an empty throwaway directory for every run: memory-lint.sh
derives all Tier-1-/Tier-2-global paths from $HOME, and the checks over
~/.claude/** would otherwise leak the developer's own machine state (file sizes,
missing scope: fields) into the findings and into the exit code.

Two independent questions run through check (n), and they are kept apart on
purpose:

* **Is a link reported at all?** — extraction behaviour (images, comments,
  titles, anchors, spaces, root-absolute targets, several links per line,
  directory semantics, scan scope). Those tests use `link_findings()`, which
  collects the check's findings regardless of the section they were filed under,
  and they assert nothing about the exit code.
* **At what severity is it reported?** — a configuration choice, owned by
  `MEMORY_INDEX_LINK_SEVERITY`. Only the tests in the severity section below set
  the variable, and only the default pin asserts the shipped value.

The split is what made the promotion of the default from `warn` to `err`
(24.08.2026, WI-0005) a single deliberate red test instead of a suite-wide
breakage, and it is what keeps any future move of that default equally cheap to
see. Measured, not assumed: putting the default back to `warn` turns exactly one
test in this file red — the pin — and leaves the 42 corpus tests untouched.
"""

import hashlib
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "memory-lint.sh"

TODAY = date.today().strftime("%d.%m.%Y")

# STALE_DAYS in memory-lint.sh is 90 — 200 days back is unambiguously over that
# threshold regardless of which day the suite happens to run on.
OLD_DATE = (date.today() - timedelta(days=200)).strftime("%d.%m.%Y")

# The environment variable that selects the severity of check (n). Named here so
# the default pin can assert that a plain run really does not set it.
SEVERITY_VAR = "MEMORY_INDEX_LINK_SEVERITY"

# Substring identifying a finding of check (n) in the rendered report. Check (f)
# reports the same defect class ("points to non-existent file") with a different
# wording, so this marker selects check (n)'s findings only.
LINK_FINDING_MARKER = "link target"

TIER1_FILE_TEXT = f"""---
name: alpha decision record
description: A valid Tier-1 memory file used as a live link target.
type: project
last_updated: {TODAY}
---

# Alpha

Body.
"""

TIER2_TOPIC_TEXT = f"""---
name: senior-developer patterns
description: A valid Tier-2 topic file used as a live link target.
type: reference
last_updated: {TODAY}
---

# Patterns

## Section two

Body.
"""

TIER2_INDEX_TEXT = f"""---
name: senior-developer project memory index
description: Index of senior-developer notes.
type: index
last_updated: {TODAY}
---

# Senior-Developer Memory

- [patterns.md](patterns.md) — conventions.
"""

TIER2_TOPIC_TEXT_TYPE_PATTERNS = f"""---
name: senior-developer conventions
description: A Tier-2 topic file using type 'patterns', the value the Tier-1 enum has no slot for (WI-0008).
type: patterns
last_updated: {TODAY}
---

# Conventions

Body.
"""

TIER2_TOPIC_TEXT_TYPE_UNKNOWN = f"""---
name: senior-developer notes
description: A Tier-2 topic file using a type value that is in neither enum.
type: freeform-notes
last_updated: {TODAY}
---

# Notes

Body.
"""

TIER1_FILE_TEXT_TYPE_PATTERNS = f"""---
name: bad Tier-1 file
description: A Tier-1 file borrowing the Tier-2-only 'patterns' value — must still error.
type: patterns
last_updated: {TODAY}
---

# Bad

Body.
"""

# Links that must never be flagged: valid relative file, anchored link into a valid
# file, directory link, external schemes, and a pure in-page anchor.
CLEAN_INDEX = """# Memory Index

- [Alpha](project_alpha.md) — a valid Tier-1 entry
- [Patterns](senior-developer/patterns.md#section-two) — anchored link into an existing file
- [Silo](senior-developer/) — directory link
- [Spec](https://example.com/spec.md) — external https link
- [Legacy](http://example.com/legacy.md) — external http link
- [Mail](mailto:someone@example.com) — mail link
- [Top](#memory-index) — in-page anchor
- [Padded]( project_alpha.md ) — whitespace around the target is not part of it
- [Titled](project_alpha.md "A Title") — double-quoted Markdown title
- [Single](project_alpha.md 'A Title') — single-quoted Markdown title
"""


def tier1_text(name="status probe", last_updated=TODAY, status=None):
    """Builds a valid Tier-1 memory file, optionally with a `status:` line.

    Kept as one parametrised builder rather than one fixture constant per
    status value (WI-0074) — the status/date combination is the axis under
    test, not the surrounding file shape, and every combination below shares
    everything except those two fields.
    """
    status_line = f"status: {status}\n" if status is not None else ""
    return (
        f"---\n"
        f"name: {name}\n"
        f"description: A Tier-1 memory file used to probe the status enum / stale check.\n"
        f"type: project\n"
        f"last_updated: {last_updated}\n"
        f"{status_line}"
        f"---\n\n"
        f"# {name}\n\nBody.\n"
    )


def related_text(name="related probe", related_entries=()):
    """Builds a valid Tier-1 memory file carrying a `related:` block (WI-0078,
    check (f)'s cross-ref field). Block-list form only — the real-world
    fixture this fix was measured against (docs/memory/
    project_attribute-mapping-slice-b-gap.md in consumer-b) uses the block
    form, and fm_list's two spellings are already exercised for phase-docs-lint
    (test_phase_docs_lint.py CheckFRelatedCrossRefsTest) against the same
    shared lib/frontmatter.sh — re-proving both here would test the library,
    not this check's resolution order.
    """
    related_block = "".join(f"  - {entry}\n" for entry in related_entries)
    related_line = f"related:\n{related_block}" if related_entries else ""
    return (
        f"---\n"
        f"name: {name}\n"
        f"description: A Tier-1 memory file used to probe the related: cross-ref check.\n"
        f"type: project\n"
        f"last_updated: {TODAY}\n"
        f"{related_line}"
        f"---\n\n"
        f"# {name}\n\nBody.\n"
    )


class MemoryLintFixture:
    """Shared fixtures for memory-lint.sh end-to-end tests (WI-0111).

    Deliberately NOT a `unittest.TestCase` subclass: `MemoryLintTest` below combines
    this mixin with `unittest.TestCase` and carries ~200 test methods. A second
    class that needs the same fixtures without inheriting those 200 tests
    (`DecayHintGracePeriodTest`) combines this mixin with `unittest.TestCase` on its
    own instead of subclassing `MemoryLintTest` directly — subclassing a concrete
    `TestCase` that itself carries tests makes unittest's discovery run every
    inherited test a second time under the new class name. See
    `scripts/tests/workitems/contract.py` for the same pattern applied to the
    work-items backend contract suite.
    """

    def setUp(self):
        self.project_dir = Path(tempfile.mkdtemp(prefix="ccpr-memory-lint-"))
        self.addCleanup(shutil.rmtree, self.project_dir, ignore_errors=True)
        self.memory_dir = self.project_dir / "docs" / "memory"
        silo_dir = self.memory_dir / "senior-developer"
        silo_dir.mkdir(parents=True)

        (self.memory_dir / "project_alpha.md").write_text(TIER1_FILE_TEXT, encoding="utf-8")
        (silo_dir / "patterns.md").write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        (silo_dir / "MEMORY.md").write_text(TIER2_INDEX_TEXT, encoding="utf-8")

        self.fake_home = Path(tempfile.mkdtemp(prefix="ccpr-memory-lint-home-"))
        self.addCleanup(shutil.rmtree, self.fake_home, ignore_errors=True)

    def write_index(self, text):
        (self.memory_dir / "MEMORY.md").write_text(text, encoding="utf-8")

    def write_persona_index(self, text, agent="senior-developer"):
        (self.memory_dir / agent / "MEMORY.md").write_text(text, encoding="utf-8")

    def lint_env(self, **extra_env):
        """The environment of a lint run — built from scratch, never inherited.

        A call without **extra_env therefore exercises the script's own defaults,
        which is precisely what the default pin needs to be meaningful.
        """
        env = {"HOME": str(self.fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
        env.update(extra_env)
        return env

    def run_lint(self, project_dir=None, **extra_env):
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), str(project_dir or self.project_dir)],
            capture_output=True, text=True, env=self.lint_env(**extra_env),
        )
        self._assert_script_actually_ran(result)
        return result

    @staticmethod
    def _assert_script_actually_ran(result):
        """Precondition for every test in this module (WI-0037).

        A negative-space assertion (`assertEqual(findings, [])`) cannot tell a clean
        run apart from a script that produced no output at all — `[] == []` holds
        either way. A bash parse error (e.g. an unbalanced quote inside the single-
        quoted awk program) makes memory-lint.sh fail before it ever emits a single
        line, and every negative-space test in this module would still report green.

        Pin the one thing every completed run has, that a script which failed to
        parse never reaches: the three report section headers. Checked here, in the
        one shared invocation path, so no individual test can be blind to it.

        Exit 3 is exempt: memory-lint.sh's own header comment documents it as a
        *configuration* failure ("the run never produced a report, so its findings
        are unknown") — a deliberate, reportless contract, not the accidental
        parse failure this precondition guards against.
        """
        if result.returncode == 3:
            return
        for heading in ("## Errors (", "## Warnings (", "## Info ("):
            assert heading in result.stdout, (
                f"memory-lint.sh produced no report (missing {heading!r} section) — "
                f"it likely failed to run at all. "
                f"returncode={result.returncode}, stderr={result.stderr!r}"
            )

    @staticmethod
    def _run_known_dead_link_probe(script_path):
        """Runs `script_path` against a minimal, known-answer fixture (WI-0044).

        One index file, one dead link, one expected finding. Deliberately not a
        report-shape check (WI-0037 already owns that) but a content check: a
        script whose extraction awk silently degraded — e.g. the parity-preserving
        apostrophe mutation, which still parses (`bash -n` green) and still prints
        every report section — exits 0 and reports zero findings where one is due.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "probe-project"
            (root / "docs" / "memory").mkdir(parents=True)
            (root / "docs" / "memory" / "MEMORY.md").write_text(
                "# Memory Index\n\n- [Dead](nonexistent.md) — a probe dead link.\n",
                encoding="utf-8",
            )
            fake_home = Path(tmp) / "probe-home"
            fake_home.mkdir()
            return subprocess.run(
                ["bash", str(script_path), str(root)],
                capture_output=True, text=True,
                env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            )

    @classmethod
    def _assert_known_dead_link_is_found(cls, script_path):
        """WI-0044 precondition, run once per test class (see setUpClass below).

        WI-0037's report-header precondition and the `bash -n` gate are both
        blind to an awk program that gets silently split into positional
        arguments — the script still runs to completion and prints a well-formed,
        clean-looking report. The only way to tell that apart from an actually
        clean run is to already know the answer: a fixture with a single, known
        dead link. Deliberately not folded into `run_lint()` (which every test
        in this class calls) — one extra script invocation per test would
        double the suite's ~60s runtime for no added coverage, since the
        thing being checked (is the awk extraction intact at all) does not vary
        per test. One run before any test in the class executes is exactly the
        "must hold before any other assertion runs" semantics this precondition
        needs, at negligible added cost.
        """
        result = cls._run_known_dead_link_probe(script_path)
        found = result.stdout.count(LINK_FINDING_MARKER)
        assert found == 1, (
            f"known dead-link probe expected exactly one {LINK_FINDING_MARKER!r} "
            f"finding, got {found} — the awk extraction may have silently degraded "
            f"(e.g. a parity-preserving apostrophe inside its single-quoted bash "
            f"string, WI-0044). returncode={result.returncode}, "
            f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        )

    @classmethod
    def setUpClass(cls):
        cls._assert_known_dead_link_is_found(SCRIPT_PATH)

    @staticmethod
    def findings(output, heading):
        """Collect the bullet lines of one report section ('Errors' / 'Warnings' / 'Info')."""
        collected = []
        collecting = False
        for line in output.splitlines():
            if line.startswith("## "):
                collecting = line.startswith(f"## {heading} (")
            elif collecting and line.startswith("- "):
                collected.append(line[2:])
        return collected

    @classmethod
    def link_findings(cls, output):
        """Every dead-link finding of check (n), whichever section it was filed under.

        Extraction tests ask *which* links are reported; the section they land in
        is a separate, configurable decision. Reading across Errors and Warnings
        keeps those tests honest about their own subject and blind to the knob.
        """
        return [
            finding
            for finding in cls.findings(output, "Errors") + cls.findings(output, "Warnings")
            if LINK_FINDING_MARKER in finding
        ]


class MemoryLintTest(MemoryLintFixture, unittest.TestCase):
    # --- Tier-aware type enum (WI-0008): Tier-1 and Tier-2 do not share a vocabulary ---
    # Check (c) used to apply the Tier-1 content-type enum to every file under
    # docs/memory/, including Tier-2 persona topic files, which the schema never gave
    # a fitting value. These three tests pin the split: Tier-2 gets its own, looser
    # enum (adds 'patterns', unrecognised values only warn); Tier-1 stays a hard error.

    def test_tier2_topic_file_with_type_patterns_is_not_an_error(self):
        """'patterns' is the value two personas independently reached for (WI-0008).

        It must not appear in the Errors section of the report at all.
        """
        self.write_index(CLEAN_INDEX)
        (self.memory_dir / "senior-developer" / "conventions.md").write_text(
            TIER2_TOPIC_TEXT_TYPE_PATTERNS, encoding="utf-8"
        )

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        # WI-0128: proves the run actually scanned conventions.md (and not merely
        # that a scan of NOTHING is error-free) — a lint that silently skipped the
        # senior-developer/ silo would pass the assertion above vacuously.
        self.assertIn("**Files scanned:** 5", result.stdout, result.stdout)

    def test_tier1_file_with_type_patterns_still_errors(self):
        """The Tier-1 enum stays closed — 'patterns' is a Tier-2-only allowance."""
        self.write_index(CLEAN_INDEX)
        (self.memory_dir / "project_bad.md").write_text(
            TIER1_FILE_TEXT_TYPE_PATTERNS, encoding="utf-8"
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("project_bad.md" in e and "type='patterns'" in e for e in errors), errors
        )

    def test_tier2_topic_file_with_an_unrecognised_type_only_warns(self):
        """A Tier-2 value outside both enums is a warning, not an error.

        The schema does not close the Tier-2 vocabulary (WI-0008); rejecting an
        unforeseen value outright would repeat the defect this item fixes.
        """
        self.write_index(CLEAN_INDEX)
        (self.memory_dir / "senior-developer" / "notes.md").write_text(
            TIER2_TOPIC_TEXT_TYPE_UNKNOWN, encoding="utf-8"
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("type='freeform-notes'" in e for e in errors), errors)
        warnings = self.findings(result.stdout, "Warnings")
        self.assertTrue(any("type='freeform-notes'" in w for w in warnings), warnings)

    # --- status enum (WI-0074): {active, archived, superseded} -------------------
    # `stale` used to be a legal `status:` value even though it was the ONE value
    # the age-warning below (previously check e) recommended, and setting it did
    # not suppress that warning — the reader followed the check's own advice and
    # got the same warning again on the next run. `stale` is removed from the
    # enum outright (measured: zero occurrences across all five live memory
    # stores) rather than added to the suppression list, which would have bought
    # silence for a status that only ever meant "is old", not "intentionally
    # unmaintained".

    def write_status_file(self, **kwargs):
        (self.memory_dir / "project_status.md").write_text(
            tier1_text(**kwargs), encoding="utf-8"
        )

    def test_status_active_is_valid(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(status="active")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("status=" in e for e in errors), errors)
        # WI-0128: "no status= error" is vacuously true on a run that never
        # reached project_status.md — pin that the fixture (index + the four
        # base files + project_status.md) was actually scanned.
        self.assertIn("**Files scanned:** 5", result.stdout, result.stdout)

    def test_status_archived_is_valid(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(status="archived")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("status=" in e for e in errors), errors)
        self.assertIn("**Files scanned:** 5", result.stdout, result.stdout)

    def test_status_superseded_is_valid(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(status="superseded")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("status=" in e for e in errors), errors)
        self.assertIn("**Files scanned:** 5", result.stdout, result.stdout)

    def test_status_absent_is_valid(self):
        """No `status:` line at all — the field is optional."""
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(status=None)

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("status=" in e for e in errors), errors)
        self.assertFalse(any("status=" in w for w in warnings), warnings)
        self.assertIn("**Files scanned:** 5", result.stdout, result.stdout)

    def test_status_stale_is_no_longer_a_valid_value(self):
        """The literal defect this item fixes: `stale` used to be legal.

        It must now be rejected the same way any other schema-foreign value is.
        """
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(status="stale")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("project_status.md" in e and "status='stale'" in e for e in errors), errors
        )

    def test_status_with_an_arbitrary_unknown_value_is_an_error(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(status="on-hold")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertTrue(
            any("project_status.md" in e and "status='on-hold'" in e for e in errors), errors
        )

    # --- stale-age warning (WI-0074): archived/superseded suppress it, stale ----
    # does not (that is the defect — see above), and the warning text itself
    # must name the two values that actually end it.

    def test_old_last_updated_without_status_produces_the_age_warning(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(last_updated=OLD_DATE, status=None)

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertTrue(any("days old" in w and "project_status.md" in w for w in warnings), warnings)

    def test_age_warning_names_the_two_values_that_suppress_it(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(last_updated=OLD_DATE, status="active")

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        age_warning = next((w for w in warnings if "days old" in w), None)
        self.assertIsNotNone(age_warning, warnings)
        self.assertIn("archived", age_warning)
        self.assertIn("superseded", age_warning)

    def test_archived_still_suppresses_the_age_warning(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(last_updated=OLD_DATE, status="archived")

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("days old" in w for w in warnings), warnings)
        # WI-0128: "no age warning" is vacuous unless project_status.md's
        # OLD_DATE last_updated was actually read.
        self.assertIn("**Files scanned:** 5", result.stdout, result.stdout)

    def test_superseded_still_suppresses_the_age_warning(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(last_updated=OLD_DATE, status="superseded")

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("days old" in w for w in warnings), warnings)
        self.assertIn("**Files scanned:** 5", result.stdout, result.stdout)

    def test_stale_does_not_suppress_the_age_warning(self):
        """The regression pin for the defect itself: a `status: stale` file is now
        BOTH an enum error (invalid value) AND still carries the age warning —
        before this fix it silently swallowed the age warning instead."""
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(last_updated=OLD_DATE, status="stale")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertTrue(any("status='stale'" in e for e in errors), errors)
        self.assertTrue(any("days old" in w for w in warnings), warnings)

    # --- (f) related: cross-refs — document-relative-first, project-root fallback --
    # WI-0078: check (f) used to resolve related: exclusively against the file's own
    # directory. Authors in the field write entries project-root-relative instead
    # (e.g. 'docs/memory/foo.md' from a file that itself lives two levels deeper),
    # so a document-relative miss now falls back to $PROJECT_DIR before the entry is
    # declared dead — mirrors the WI-0071 fix already shipped for the identical
    # question in phase-docs-lint.sh check (f)/(g) (PO decision 21.08.2026), same
    # wording, same severity split (root-relative hit is `info`, not silence — two
    # bases without saying so would be the unvalidated drift this lint exists to
    # catch). Deliberately the same fallback base ($PROJECT_DIR, not e.g. the docs/
    # folder) as phase-docs-lint.sh uses — "no second convention for the second
    # linter" (WI-0078 briefing).

    def test_related_entry_resolved_document_relative_stays_silent(self):
        """The pre-existing, documented case: an entry that resolves relative to
        the file's own directory must stay completely silent — no err, no info."""
        self.write_index(CLEAN_INDEX + "- [Main](project_main-doc-relative.md) — probe\n")
        (self.memory_dir / "project_sidecar-doc-relative.md").write_text(
            related_text(name="sidecar"), encoding="utf-8"
        )
        (self.memory_dir / "project_main-doc-relative.md").write_text(
            related_text(
                name="main",
                related_entries=["project_sidecar-doc-relative.md"],
            ),
            encoding="utf-8",
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        infos = self.findings(result.stdout, "Info")
        self.assertFalse(any("related:" in e for e in errors), errors)
        self.assertFalse(any("related:" in i for i in infos), infos)
        # WI-0128: "no related: finding" is vacuous unless project_main-doc-
        # relative.md's own related: block was actually read and resolved —
        # pin that both sidecar files this test wrote were scanned.
        self.assertIn("**Files scanned:** 6", result.stdout, result.stdout)

    def test_related_entry_resolvable_only_at_project_root_is_info_not_error(self):
        """A file nested under a Tier-2 silo writes a related: entry rooted at the
        repo's docs/ tree (matching how phase-docs-lint's own WI-0071 fixture is
        built) — document-relative misses, the project-root fallback hits."""
        silo_dir = self.memory_dir / "senior-developer"
        (self.memory_dir / "project_root-target.md").write_text(
            related_text(name="root target"), encoding="utf-8"
        )
        (silo_dir / "project_main-root.md").write_text(
            related_text(
                name="main",
                related_entries=["docs/memory/project_root-target.md"],
            ),
            encoding="utf-8",
        )
        self.write_persona_index(
            "---\nname: senior-developer project memory index\n"
            "description: Index of senior-developer notes.\ntype: index\n"
            "last_updated: 01.01.2026\n---\n\n"
            "# Senior-Developer Memory\n\n"
            "- [patterns.md](patterns.md) — conventions.\n"
            "- [main-root](project_main-root.md) — probe.\n"
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        infos = self.findings(result.stdout, "Info")
        self.assertFalse(any("related:" in e for e in errors), errors)
        self.assertTrue(
            any(
                "project_main-root.md" in i
                and "related:'docs/memory/project_root-target.md'" in i
                and "project-root fallback" in i
                for i in infos
            ),
            infos,
        )

    def test_related_entry_resolvable_at_neither_base_stays_an_error(self):
        self.write_index(CLEAN_INDEX + "- [Main](project_main-neither.md) — probe\n")
        (self.memory_dir / "project_main-neither.md").write_text(
            related_text(name="main", related_entries=["docs/memory/project_ghost.md"]),
            encoding="utf-8",
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        infos = self.findings(result.stdout, "Info")
        self.assertTrue(
            any(
                "project_main-neither.md" in e
                and "related:'docs/memory/project_ghost.md' points to non-existent file" in e
                for e in errors
            ),
            errors,
        )
        self.assertFalse(any("project_main-neither.md" in i for i in infos), infos)

    def test_related_entry_resolvable_at_both_bases_resolves_document_relative_and_stays_silent(self):
        """Order guard: the entry resolves at BOTH bases (document-relative AND
        project-root), so a 'check root first' resolution-order regression would
        still succeed silently — but via the wrong branch. Pinning 'no info' here
        only proves the fallback wasn't needed; this cannot pass by accident
        because the two prior tests already pin the wording each branch prints."""
        (self.memory_dir / "project_sidecar-both.md").write_text(
            related_text(name="sidecar"), encoding="utf-8"
        )
        self.write_index(
            CLEAN_INDEX + "- [Main](project_main-both.md) — probe\n"
        )
        (self.memory_dir / "project_main-both.md").write_text(
            related_text(
                name="main",
                # No 'docs/memory/' prefix: resolves document-relative (base_dir
                # IS docs/memory here) *and* — since PROJECT_DIR/project_sidecar-
                # both.md does not exist — only via the document-relative base.
                # To genuinely hit both bases, the entry must also exist relative
                # to PROJECT_DIR: mirror the sidecar file there too.
                related_entries=["project_sidecar-both.md"],
            ),
            encoding="utf-8",
        )
        # Plant the same filename at PROJECT_DIR root so a root-relative
        # resolution would ALSO succeed — proving the document-relative branch,
        # not the fallback, is what actually fired.
        (self.project_dir / "project_sidecar-both.md").write_text(
            related_text(name="root sidecar"), encoding="utf-8"
        )

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        infos = self.findings(result.stdout, "Info")
        self.assertFalse(any("related:" in e for e in errors), errors)
        self.assertFalse(any("related:" in i for i in infos), infos)
        # WI-0128: "no related: finding" is vacuous unless project_main-both.md
        # was actually read — pin that the two docs/memory sidecars this test
        # wrote (the root-planted copy is outside docs/memory/** and does not
        # count) were scanned.
        self.assertIn("**Files scanned:** 6", result.stdout, result.stdout)

    # --- Regression pin for the pre-existing behaviour being extended --------------

    def test_clean_index_produces_no_findings_at_all(self):
        """A Tier-1 index whose local links all resolve must stay silent.

        Pins the shape of the new check so a later change cannot make it fire on
        every link: external schemes, in-page anchors, anchored file links and
        directory links are all legitimate. Asserted over the whole report, not
        just check (n): it also pins the fixture as clean, which is what lets the
        other tests read a single finding as *theirs*.
        """
        self.write_index(CLEAN_INDEX)

        result = self.run_lint()

        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    # --- The defect: dead links in the Tier-1 index pass silently -----------------

    def test_dead_link_in_tier1_index_is_reported(self):
        self.write_index(CLEAN_INDEX + "- [Ghost](project_deleted.md) — dead link\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("project_deleted.md", findings[0])

    def test_every_dead_link_is_reported_not_only_the_first(self):
        self.write_index(
            CLEAN_INDEX
            + "- [Ghost](project_deleted.md) — dead link\n"
            + "- [Ghost2](reference_gone.md) — dead link\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("project_deleted.md" in f for f in findings), findings)
        self.assertTrue(any("reference_gone.md" in f for f in findings), findings)

    def test_dead_link_with_anchor_is_reported_without_the_anchor(self):
        """`[X](a/b.md#section)` must be checked against `a/b.md`, not the raw target."""
        self.write_index(CLEAN_INDEX + "- [Ghost](senior-developer/missing.md#part) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("senior-developer/missing.md", findings[0])
        self.assertNotIn("#part", findings[0])

    def test_dead_directory_link_is_reported(self):
        self.write_index(CLEAN_INDEX + "- [Ghost](nonexistent-silo/) — dead directory link\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("nonexistent-silo/", findings[0])

    def test_a_directory_link_is_not_satisfied_by_a_same_named_file(self):
        """`[X](notes/)` must not resolve against the regular file `notes`.

        Pins the trailing slash as meaningful: dropping it before the existence
        test would silently accept a file where the index promises a silo.
        """
        (self.memory_dir / "notes").write_text("not a directory\n", encoding="utf-8")
        self.write_index(CLEAN_INDEX + "- [Notes](notes/) — file, not a directory\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("notes/", findings[0])

    def test_a_directory_link_without_a_trailing_slash_resolves(self):
        """`[X](senior-developer)` addresses the silo directory and is not a dead link."""
        self.write_index(CLEAN_INDEX + "- [Silo](senior-developer) — directory, no slash\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    # --- Target parsing: only a genuine quoted title may be stripped ---------------

    def test_a_bare_space_in_an_unbracketed_target_is_not_a_link_at_all(self):
        """`[X](my file.md)` is not a link — CommonMark, not this checker's opinion.

        WI-0034 established that a bare space is no truncation delimiter (it
        must not collapse `my file.md` to `my`); it did NOT follow that the
        untruncated string is then a target to check. Per the CommonMark
        reference an unescaped space terminates an unbracketed destination, and
        `file.md)` is not a valid title, so the whole `[X](...)` construct
        fails to parse as a link (WI-0061). It must therefore stay silent even
        though `my missing file.md` does not exist — reporting it would flag
        prose that was never a link.
        """
        self.write_index(CLEAN_INDEX + "- [Spaces](my missing file.md) — not a link\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_an_unbracketed_target_with_a_space_is_silent_even_when_the_file_exists(self):
        """Same non-link verdict as the dead case above — existence is moot.

        `senior-developer/notes with space.md` genuinely exists on disk here;
        the finding list is empty regardless, because `](...)` with an
        unescaped, untitled space in it is not a link to begin with. The
        bracket form directly below is how a destination containing a space is
        actually written and actually resolved.
        """
        spaced = self.memory_dir / "senior-developer" / "notes with space.md"
        spaced.write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        self.write_index(CLEAN_INDEX + "- [Spaces](senior-developer/notes with space.md) — live\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_bracketed_target_with_a_space_resolves_when_the_file_exists(self):
        """`[x](<...>)` is the CommonMark form that exists specifically so a
        destination MAY contain a space (WI-0060) — this is the live control
        for the dead one further down in the angle-bracket section."""
        spaced = self.memory_dir / "senior-developer" / "notes with space.md"
        spaced.write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        self.write_index(
            CLEAN_INDEX + "- [Spaces](<senior-developer/notes with space.md>) — live\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_whitespace_around_the_target_is_trimmed_not_treated_as_a_skip(self):
        """`[x]( a.md)` was dropped silently — the target must still be checked."""
        self.write_index(CLEAN_INDEX + "- [Padded]( project_deleted.md ) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("project_deleted.md", findings[0])

    def test_a_title_followed_by_whitespace_is_still_stripped(self):
        """`[x](a.md "T" )` — whitespace may sit on both sides of the title."""
        self.write_index(CLEAN_INDEX + '- [Titled](project_alpha.md "A Title" ) — live\n')

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_quoted_title_is_stripped_from_a_dead_target(self):
        """The reported target is the path, without the `"Title"` suffix."""
        self.write_index(CLEAN_INDEX + '- [Titled](project_deleted.md "A Title") — dead\n')

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("'project_deleted.md'", findings[0])
        self.assertNotIn("A Title", findings[0])

    def test_a_single_quoted_title_is_stripped_from_a_dead_target(self):
        """The single-quote title form (`](target 'Title')`) strips the same way.

        WI-0026: the double-quote case above is a dedicated dead-target pin; the
        single-quote strip arm (memory-lint.sh) was previously only exercised
        indirectly through CLEAN_INDEX's live 'Single' entry — dropping that arm
        was caught only as a side effect of an unrelated fixture line. This gives
        it its own pin, independent of CLEAN_INDEX.
        """
        self.write_index(CLEAN_INDEX + "- [Titled](project_deleted.md 'A Title') — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("'project_deleted.md'", findings[0])
        self.assertNotIn("A Title", findings[0])

    # --- Root-absolute targets resolve against the project root --------------------

    def test_root_absolute_target_resolves_against_the_project_root(self):
        """`/docs/memory/x.md` is repo-root-relative, not $MEMORY_DIR-relative.

        The old concatenation produced `<project>/docs/memory//docs/memory/x.md`
        — a path that can never exist, i.e. a guaranteed false positive.
        """
        self.write_index(CLEAN_INDEX + "- [Absolute](/docs/memory/project_alpha.md) — live\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_dead_root_absolute_target_is_reported_with_the_project_root_path(self):
        self.write_index(CLEAN_INDEX + "- [Absolute](/docs/memory/root.md) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("'/docs/memory/root.md'", findings[0])
        self.assertIn(f"({self.project_dir}/docs/memory/root.md)", findings[0])
        self.assertNotIn("memory//docs", findings[0])

    # --- Non-entries: images and commented-out entries ------------------------------

    def test_image_links_are_not_index_entries(self):
        """`![Alt](diagram.png)` is an image, not a link to a memory file."""
        self.write_index(CLEAN_INDEX + "![Image](diagram.png)\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_real_link_next_to_an_image_on_the_same_line_is_still_checked(self):
        self.write_index(CLEAN_INDEX + "![Image](diagram.png) see [Ghost](gone.md)\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone.md", findings[0])

    def test_entries_parked_in_a_single_line_html_comment_are_skipped(self):
        """Parking a retired entry in `<!-- ... -->` is ordinary index practice."""
        self.write_index(CLEAN_INDEX + "<!-- - [Commented](old_entry.md) — retired -->\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_live_link_after_a_closed_comment_on_the_same_line_is_checked(self):
        """The comment must not OPEN the line here — a comment starting a line
        (after <=3 leading spaces) is CommonMark HTML block type 2, which
        swallows the whole physical line including anything after `-->`
        (WI-0041); that is a different mechanism, pinned separately below.
        Prefixing with 'Note: ' keeps this test on the INLINE splice path
        (decomment() mid-line, `boundary` carried across the closed span) that
        it was written to cover.
        """
        self.write_index(CLEAN_INDEX + "- Note: <!-- retired --> [Ghost](gone.md) — live entry\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone.md", findings[0])

    def test_entries_parked_in_a_multi_line_html_comment_are_skipped(self):
        self.write_index(
            CLEAN_INDEX
            + "<!--\n"
            + "- [Commented](old_entry.md) — retired\n"
            + "- [Commented2](older_entry.md) — retired\n"
            + "-->\n"
            + "- [Ghost](gone.md) — live entry after the comment block\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone.md", findings[0])

    def test_a_multi_line_html_comments_closing_line_hides_a_link_after_it(self):
        """WI-0041: a block-level HTML comment's closing line is entirely raw
        HTML per CommonMark, including any text after `-->` on that same
        line — not just the comment span itself. Measured against a
        CommonMark reference implementation: `<!--\\nx\\n-->[y](dead.md)`
        renders no `<a href>` at all, so `dead.md` is not a link and must not
        be reported. Before the fix, decomment() only strips the comment span
        and leaves the rest of the closing line to be parsed normally, so the
        link was reported as a false positive.
        """
        self.write_index(CLEAN_INDEX + "<!--\nx\n-->[y](dead.md)\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_single_line_html_comment_opening_the_line_hides_a_link_after_it(self):
        """Same mechanism as the multi-line case above, single-line variant:
        a comment that opens AND closes on the same physical line still
        swallows the whole line if it starts at column 0 (<=3 leading
        spaces). Measured: `<!--x-->[y](dead.md)` renders no `<a href>`.
        """
        self.write_index(CLEAN_INDEX + "<!--x-->[y](dead.md)\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_an_image_inside_a_single_line_html_comment_is_skipped(self):
        """Both skip mechanisms — comment-stripping and the image exclusion — are
        covered separately elsewhere; this exercises them combined on one line
        (WI-0026). decomment() runs before the image/link distinction, so an
        image markup that sits entirely inside a comment must vanish before
        that distinction is ever made. The comment must not OPEN the line —
        see the note on the inline-splice test above (WI-0041) — so this is
        prefixed with 'Note:' to stay on the inline path.
        """
        self.write_index(CLEAN_INDEX + "- Note: <!-- ![Diagram](dead_diagram.md) --> [Ghost](gone.md)\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone.md", findings[0])

    def test_a_bang_before_a_comment_does_not_forge_an_image_marker(self):
        """`!<!--c-->[x](dead.md)` — `decomment()` used to run before the image
        test, so the removed comment fused the `!` and the `[` into a literal
        `![`, and the resulting "image" was skipped without ever being checked
        (WI-0029). A CommonMark reference implementation renders
        `!<!--c--><a href="dead_one.md">x</a>` for this input — the `!` and the
        link are two separate inline nodes, not an image marker, so this is a
        real link and its dead target must be reported."""
        self.write_index(CLEAN_INDEX + "- !<!--c-->[x](dead_one.md)\n- [y](dead_two.md)\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_one.md" in f for f in findings), findings)
        self.assertTrue(any("dead_two.md" in f for f in findings), findings)

    def test_a_comment_inside_a_link_destination_is_literal_text_not_a_comment(self):
        """WI-0042: CommonMark link-destination grammar is not inline-parsed, so
        a `<!--...-->` sequence inside `[x](dest)` is literal text, not an HTML
        comment to strip. Reference-measured: `[x](dead<!--c-->.md)` renders
        `href="dead%3C%21--c--%3E.md"` — the comment markup is part of the
        destination. decomment() used to run over the whole line regardless of
        link structure and stripped it anyway, so the check resolved a path
        nobody wrote (`dead.md`) instead of the real one. Before this fix, a
        boundary byte (chr(1), WI-0029) also leaked into the finding message at
        the comment's former position; this pins both defects closed at once —
        the destination must be the literal text, and no control byte may
        appear anywhere in the report either way.
        """
        self.write_index(CLEAN_INDEX + "- [x](dead<!--c-->.md)\n")

        output = self.run_lint().stdout
        findings = self.link_findings(output)

        self.assertEqual(len(findings), 1, findings)
        self.assertNotIn("\x01", output, output)
        self.assertIn("'dead<!--c-->.md'", findings[0])

    def test_a_comment_inside_a_reference_definition_target_is_literal_text_not_a_comment(self):
        """Same defect, the reference-definition path (`[id]: target`) instead of
        the inline `[x](target)` form (WI-0042) — the two paths extract the
        target independently, so the fix has to cover both."""
        # The blank line between CLEAN_INDEX and the definition is load-bearing,
        # not layout (WI-0096, measured at the reference). CLEAN_INDEX ends in a
        # list item; without the blank line the definition-shaped line is a LAZY
        # CONTINUATION of that item's paragraph, which renders it as visible
        # prose and defines nothing. This fixture is about the definition form,
        # so it has to actually be one.
        self.write_index(CLEAN_INDEX + "\n[r]: refdead<!--c-->.md\n")

        output = self.run_lint().stdout
        findings = self.link_findings(output)

        self.assertEqual(len(findings), 1, findings)
        self.assertNotIn("\x01", output, output)
        self.assertIn("'refdead<!--c-->.md'", findings[0])

    def test_a_comment_inside_link_text_stays_a_comment_and_is_stripped(self):
        """Control probe, the opposite side of WI-0042's direction split: a
        comment in the link LABEL (not the destination) is inline content, so
        CommonMark does not exempt it from ordinary inline parsing the way the
        destination is exempt. Reference-measured: `[te<!--c-->xt](dead.md)`
        renders `<a href="dead.md">te<!--c-->xt</a></a>` — a live link to
        `dead.md`, comment markup included in the (irrelevant, for this check)
        label. Pins that the destination-only fix above does not also start
        exempting label text, which this check never inspects anyway.
        """
        self.write_index(CLEAN_INDEX + "- [te<!--c-->xt](dead_label.md)\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("'dead_label.md'", findings[0])

    # --- WI-0050: a mid-line comment opener is resolved per PARAGRAPH, not per
    # FILE. Before the fix, decomment()'s in_comment state was an undeclared
    # (therefore global, in awk) variable that survived past the record it was
    # set on: an unclosed mid-line opener silently disabled link checking for
    # the rest of the file. Three shapes below are the PO decision's own
    # measurement (20.08.2026), reference-confirmed with a CommonMark
    # implementation before writing each test; a fourth pins the swallow-the-
    # file regression this item is named for; a fifth pins that WI-0043's
    # block-level sentinel still fires; the last two are controls.

    def test_a_mid_line_comment_opener_does_not_cross_into_the_next_list_item(self):
        """Shape (1): a mid-line opener on one list item that only closes on a
        LATER item must not cross the line — each list item is its own block.
        Reference-confirmed: both links render.
        """
        self.write_index(
            CLEAN_INDEX
            + "- one <!-- comment [Dead A](dead_wi0050_list_a.md)\n"
            + "- comment continues --> [Dead B](dead_wi0050_list_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_wi0050_list_a.md" in f for f in findings), findings)
        self.assertTrue(any("dead_wi0050_list_b.md" in f for f in findings), findings)

    def test_a_heading_flushes_immediately_and_does_not_merge_with_a_following_paragraph(self):
        """A third named boundary: an ATX heading is always exactly one line in
        CommonMark, so it must resolve on its own, even with no blank line
        before the paragraph that follows it. The opener is deliberately paired
        with a closer on the FOLLOWING line — if the heading wrongly kept
        buffering past itself, that closer would pair with the heading's
        opener and swallow the link inside the heading; reference-confirmed it
        does not, because the heading and the paragraph after it are separate
        blocks.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "# Heading <!-- opens here [Dead A](dead_wi0050_heading_open_a.md)\n"
            + "closes here --> [Dead B](dead_wi0050_heading_close_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_wi0050_heading_open_a.md" in f for f in findings), findings)
        self.assertTrue(any("dead_wi0050_heading_close_b.md" in f for f in findings), findings)

    def test_a_mid_line_comment_opener_crosses_into_the_next_line_of_the_same_paragraph(self):
        """Shape (2): inside a PLAIN paragraph (no list marker, no blank line
        between), a mid-line opener that closes on a later line DOES span the
        line break — the enclosed link must not be reported, only the link
        after the closer. Reference-confirmed.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "Note: <!-- comment [Dead A](dead_wi0050_para_a.md)\n"
            + "continues --> [Dead B](dead_wi0050_para_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0050_para_b.md", findings[0])

    def test_an_unclosed_mid_line_comment_opener_is_literal_text_within_its_own_paragraph(self):
        """Shape (3): a mid-line opener that never closes anywhere in the file
        is literal text — nothing is discarded, and every link in its own
        paragraph is still found. Reference-confirmed.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "Note: <!-- unclosed [Dead A](dead_wi0050_open_a.md) more [Dead B](dead_wi0050_open_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_wi0050_open_a.md" in f for f in findings), findings)
        self.assertTrue(any("dead_wi0050_open_b.md" in f for f in findings), findings)

    def test_an_unclosed_mid_line_comment_in_one_paragraph_does_not_swallow_a_later_paragraph(self):
        """The defect this item is named for: before the fix, an unclosed
        mid-line opener in one paragraph disabled link checking for the rest of
        the FILE, not just its own paragraph — the two paragraphs below are
        independent CommonMark blocks, reference-confirmed, both links render.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "Note: <!-- unclosed [Dead A](dead_wi0050_swallow_a.md)\n"
            + "\n"
            + "A later paragraph [Dead B](dead_wi0050_swallow_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_wi0050_swallow_a.md" in f for f in findings), findings)
        self.assertTrue(any("dead_wi0050_swallow_b.md" in f for f in findings), findings)

    def test_a_mid_line_comment_opener_does_not_pair_with_a_closer_across_a_blank_line(self):
        """The blank-line boundary itself, isolated: unlike shape (2) above (a
        closer on a later line of the SAME paragraph), a closer that only
        appears AFTER a blank line must not retroactively close an opener in
        the paragraph before it — each paragraph is inlined separately in
        CommonMark, a blank line ends the block. Reference-confirmed: both
        links render, the second paragraph's `-->` is inert literal text with
        no opener of its own to pair with.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "Note: <!-- opens here [Dead A](dead_wi0050_blank_a.md)\n"
            + "\n"
            + "closes here --> [Dead B](dead_wi0050_blank_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_wi0050_blank_a.md" in f for f in findings), findings)
        self.assertTrue(any("dead_wi0050_blank_b.md" in f for f in findings), findings)

    def test_an_unclosed_opener_does_not_leak_into_a_later_paragraphs_own_unrelated_arrow(self):
        """Isolates the exact mechanism WI-0050 names: decomment_paragraph()
        must use a FRESH local per call, not state that survives the call.
        Reference-confirmed the two paragraphs below are independent; the
        second one has nothing to do with a comment at all, it just happens to
        contain the literal text `-->`, which is not special on its own. If
        state leaked from paragraph one (still unresolved) into paragraph two,
        that unrelated `-->` would be wrongly read as a closer and everything
        before it in paragraph two — including its own link — would be
        discarded as if it were comment content.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "Note: <!-- unclosed [Dead A](dead_wi0050_leak_a.md)\n"
            + "\n"
            + "[Dead B](dead_wi0050_leak_b.md) --> more text after an unrelated arrow\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_wi0050_leak_a.md" in f for f in findings), findings)
        self.assertTrue(any("dead_wi0050_leak_b.md" in f for f in findings), findings)

    def test_the_block_level_unclosed_comment_sentinel_still_fires_after_a_buffered_paragraph(self):
        """WI-0050 must not weaken WI-0043: a PLAIN paragraph (not a list item)
        buffered ahead of a block-level HTML comment (opens at column 0, never
        closes) must still flush correctly, and the sentinel must still fire.
        Asserts scope, not only the verdict: the paragraph before the block
        comment must still be scanned (its own dead link found), and the
        content swallowed by the unclosed block comment must not be — a bare
        `assertEqual(findings, [])` here would be satisfied just as well by a
        run that scanned nothing at all.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "A live paragraph pointing at [Dead C](dead_wi0050_sentinel_before.md).\n"
            + "\n"
            + "<!--\n"
            + "- [Example](dead_wi0050_sentinel_after.md)\n"
        )

        result = self.run_lint()

        findings = self.link_findings(result.stdout)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0050_sentinel_before.md", findings[0])
        warnings = self.findings(result.stdout, "Warnings")
        self.assertTrue(any("never closed" in w for w in warnings), warnings)

    def test_a_fenced_code_block_flushes_the_paragraph_buffered_ahead_of_it(self):
        """A fence opener is a block boundary too, the same as the three named
        ones — a paragraph buffered right up against a fence (no blank line
        between) must flush BEFORE the fence is entered, not carry an unclosed
        opener across the fenced block into whatever paragraph follows it.
        Reference-confirmed: the paragraph before the fence, the fenced block
        itself, and the paragraph after it are three independent blocks.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "Note: <!-- unclosed [Dead A](dead_wi0050_fence_a.md)\n"
            + "```\n"
            + "ignored fence content\n"
            + "```\n"
            + "[Dead B](dead_wi0050_fence_b.md) --> more text\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_wi0050_fence_a.md" in f for f in findings), findings)
        self.assertTrue(any("dead_wi0050_fence_b.md" in f for f in findings), findings)

    def test_a_block_level_html_comment_flushes_the_paragraph_buffered_ahead_of_it(self):
        """Same boundary as the fence case above, for the OTHER block-level
        construct: a column-0 HTML comment (WI-0043's block mechanism) must
        also flush whatever paragraph is buffered ahead of it, not carry an
        unclosed mid-line opener across the block comment into the paragraph
        that follows. Reference-confirmed: three independent blocks.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "Note: <!-- unclosed [Dead A](dead_wi0050_htmlblock_a.md)\n"
            + "<!--\n"
            + "- [Ignored](ignored.md)\n"
            + "-->\n"
            + "[Dead B](dead_wi0050_htmlblock_b.md) --> more text\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_wi0050_htmlblock_a.md" in f for f in findings), findings)
        self.assertTrue(any("dead_wi0050_htmlblock_b.md" in f for f in findings), findings)

    def test_a_multi_line_paragraph_without_any_comment_is_unaffected_by_paragraph_buffering(self):
        """Control: WI-0050 introduces paragraph buffering even when no comment
        is present at all. A plain paragraph wrapped over two physical lines,
        each holding a link, must still report both — buffering must not merge
        or drop line-scoped content that decomment_paragraph() never touches.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "A live paragraph with [Dead A](dead_wi0050_plain_a.md) on\n"
            + "its first line and [Dead B](dead_wi0050_plain_b.md) on its second.\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_wi0050_plain_a.md" in f for f in findings), findings)
        self.assertTrue(any("dead_wi0050_plain_b.md" in f for f in findings), findings)

    def test_a_live_link_survives_paragraph_buffering_while_a_dead_one_beside_it_is_still_reported(self):
        """Control: a live link sharing a buffered paragraph with a dead one
        must not be reported — buffering is purely about comment resolution
        scope, not a new source of false positives. The dead sibling proves
        the paragraph was actually scanned, not merely skipped clean.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "A live target [Alpha](project_alpha.md) and a dead one\n"
            + "[Dead A](dead_wi0050_live_control.md) share one buffered paragraph.\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0050_live_control.md", findings[0])
        self.assertNotIn("project_alpha.md", findings[0])

    # --- WI-0048: whichever inline construct opens FIRST claims its span -----------
    # decomment_paragraph() and strip_inline_code() used to be two separate
    # whole-paragraph passes in a fixed order, which gets the precedence between
    # an HTML comment and a code span wrong in one direction no matter which
    # order is picked. resolve_paragraph() replaces both with one left-to-right
    # scan (see memory-lint.sh). All four fixtures below are settled at the
    # CommonMark reference and tracked in
    # docs/memory/reference_commonmark-conformance.md under "Inline precedence:
    # whichever construct opens FIRST claims its span".

    def test_a_code_span_opened_before_a_comment_delimiter_makes_it_literal_and_the_link_is_found(self):
        """Reference-measured (table row, WI-0048): `` a `b<!--c` [x](t.md)`e ``
        renders a genuine link — the backtick opens first, so the `<!--`
        inside the span is literal content, not a comment opener. Pinned as a
        control for this exact fixture shape; it is NOT, on its own, a
        regression pin for the old two-pass design — mutation-checked (see
        the mutation table in the senior-developer report): this specific
        shape has no closing `-->` anywhere in the line, so the OLD
        decomment_paragraph() (already WI-0050-fixed) treats the whole
        `<!--...` as an unclosed, literal comment and never collapses
        anything, after which the OLD strip_inline_code()'s plain run-length
        pairing lands on the same code-span boundary by coincidence. The
        canonical work-item repro below, which DOES include a `-->`, is the
        one that actually discriminates old from new.
        """
        self.write_index(
            CLEAN_INDEX + "a `b<!--c` [x](dead_wi0048_span_first.md)`e\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0048_span_first.md", findings[0])

    def test_wi_0048_canonical_repro_with_a_closed_comment_inside_the_span_still_finds_the_link(self):
        """The work item's own concrete repro (WI-0048, 19.08.2026): a
        backtick-opened span whose content includes both the comment opener
        AND its closer, then a real link, then a closing backtick — reference-
        measured to render the link live, the code span covering only
        `` b<!--c ``. This is the actual regression pin: mutation-checked
        against the pre-fix, two-pass memory-lint.sh (git history), this
        exact fixture goes from 1 finding to 0 — the old decomment_paragraph()
        DOES find and collapse the closed `<!--c-->` span here (unlike the
        control above), which removes one of the two remaining backticks and
        lets the surviving pair re-pair across the real link, swallowing it as
        code — exactly the mechanism the work item describes ("the surviving
        backticks then re-pair across the resulting gap").
        """
        self.write_index(
            CLEAN_INDEX
            + "- a`b<!--c`--> [link](dead_wi0048_ordering_gap.md)`e\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0048_ordering_gap.md", findings[0])

    def test_a_comment_opened_before_a_code_span_makes_the_backtick_literal_and_the_link_is_found(self):
        """Reference-measured: `text <!-- a ` b --> [x](t.md)` renders a
        genuine link too — the comment opens first here, so the backtick
        inside it is literal. The extractor already got this direction right
        before WI-0048 (decomment_paragraph() ran first); this pins it as a
        control so the merge into resolve_paragraph() cannot regress it.
        """
        self.write_index(
            CLEAN_INDEX + "text <!-- a ` b --> [x](dead_wi0048_comment_first.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0048_comment_first.md", findings[0])

    def test_a_mid_line_comment_that_fully_encloses_a_link_on_one_line_hides_it(self):
        """Reference-measured: `text <!-- a [x](t.md) b -->` renders no link at
        all — a mid-line comment does hide a link it fully encloses. A live
        sibling link outside the comment, in the same paragraph, proves the
        paragraph was actually scanned rather than skipped whole.
        """
        self.write_index(
            CLEAN_INDEX
            + "text <!-- a [x](dead_wi0048_enclosed.md) b --> and "
            + "[y](dead_wi0048_enclosed_sibling.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0048_enclosed_sibling.md", findings[0])
        self.assertNotIn("dead_wi0048_enclosed.md", findings[0])

    def test_an_unclosed_mid_line_comment_swallows_nothing_and_the_link_after_it_is_found(self):
        """Reference-measured: `text <!-- a [x](t.md)`, unclosed, renders the
        link — an unclosed INLINE comment swallows nothing, unlike HTML block
        type 2 which needs `<!--` to begin the line. Same shape as the WI-0050
        controls above, restated here as its own row of the WI-0048 precedence
        table (docs/memory/reference_commonmark-conformance.md) so the table
        is traceable one row at a time.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "text <!-- a [x](dead_wi0048_unclosed.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0048_unclosed.md", findings[0])

    # --- WI-0052: a code span crosses physical lines inside one paragraph ----------
    # strip_inline_code() carried the stated premise that a code span never
    # crosses a line, so it ran once per physical line even after WI-0050 gave
    # comments paragraph scope. That premise is false — CommonMark lets a code
    # span cross a line break the same way a comment does. resolve_paragraph()
    # now runs once over the whole buffered paragraph. All four fixtures below
    # are settled at the CommonMark reference and tracked in
    # docs/memory/reference_commonmark-conformance.md.

    def test_a_code_span_crosses_two_physical_lines_and_the_link_after_it_is_found(self):
        """Reference-measured: `` text `code `` / `` more code` [x](a.md) ``
        renders ONE code span containing both lines, with the link outside it
        and live. Before the fix, strip_inline_code() ran per line and never
        saw the two backtick runs as a pair at all — each line kept its own
        stray backtick as literal text and the link was reported as ordinary
        prose, which happened to also find it, so this pins the SPAN, not
        merely the verdict: see the list-item control below for the shape
        where the span must NOT form.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "text `code\n"
            + "more code` [x](dead_wi0052_span_crosses_line.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0052_span_crosses_line.md", findings[0])

    def test_a_list_item_boundary_stops_a_code_span_from_crossing_into_the_next_item(self):
        """Reference-measured: a code span does NOT cross a list-item boundary
        — each item is its own block, the same paragraph-anchored rule WI-0050
        established for comments. Both stray backticks stay literal within
        their own item, and both links (one per item) are found — proving the
        span-crossing fix above is scoped to a PARAGRAPH, not to the raw
        paragraph buffer regardless of block boundaries.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "- text `code [a](dead_wi0052_list_a.md)\n"
            + "- more code` [b](dead_wi0052_list_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("dead_wi0052_list_a.md" in f for f in findings), findings)
        self.assertTrue(any("dead_wi0052_list_b.md" in f for f in findings), findings)

    def test_a_comment_then_a_code_span_both_crossing_lines_are_resolved_in_order(self):
        """Reference-measured: `text <!-- c` / `d --> `e` / `` f` [x](a.md) ``
        resolves the comment first (it opens first), then the code span (it
        opens next), each swallowing the line break inside it in turn, with
        the link outside both and live. Exercises WI-0048's precedence and
        WI-0052's cross-line reach together, in the same buffered paragraph.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "text <!-- c\n"
            + "d --> `e\n"
            + "f` [x](dead_wi0052_comment_then_span.md)\n"
        )

        output = self.run_lint().stdout
        findings = self.link_findings(output)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0052_comment_then_span.md", findings[0])
        self.assertNotIn("\x01", output, output)

    def test_a_code_span_opened_before_a_comment_across_a_line_break_wins_and_the_arrow_after_it_is_literal(self):
        """Reference-measured: `` text `a <!-- b `` / `` c` d --> [x](a.md) ``
        — the code span opens first, crosses the line break, and its content
        (including the `<!--`) is literal; the `-->` after the closing
        backtick is then ordinary literal text too, and the link is live. Pins
        WI-0048's precedence rule for the case where the winning construct is
        the one that spans the line break, not the one that stays on one line.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "text `a <!-- b\n"
            + "c` d --> [x](dead_wi0052_span_wins_then_arrow.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_wi0052_span_wins_then_arrow.md", findings[0])

    def test_a_two_line_illustrative_code_span_in_an_index_entry_produces_no_finding(self):
        """WI-0052's own end-to-end repro: an index documenting its own entry
        syntax across two physical lines, inside one code span, must not have
        its illustrative link reported as a dead target — the reference
        renders no `<a href>` for this input at all. Before the fix,
        memory-lint reported `gone_illustrative.md` as a dead link, exactly
        the WI-0005 gap (1) false-positive class this check exists to avoid,
        one line-break further than WI-0005 originally covered.
        """
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "Example syntax: `an entry looks like\n"
            + "[label](gone_illustrative.md) inside a span`\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    # --- WI-0005: code examples are not entries, reference-style links are ---------

    def test_a_dead_link_shown_inside_a_fenced_code_block_is_not_reported(self):
        """An index illustrating its own link syntax in a fenced example is not a
        set of live entries — the target inside the fence must not be checked."""
        self.write_index(
            CLEAN_INDEX
            + "Example entry format:\n"
            + "\n"
            + "```\n"
            + "- [Example](dead_fenced.md) — illustrative sample\n"
            + "```\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_dead_link_shown_inline_in_backticks_is_not_reported(self):
        """Same illustration, inline: `` `[Example](dead_inline.md)` `` is prose,
        not an entry."""
        self.write_index(
            CLEAN_INDEX + "Entries look like `[Example](dead_inline.md)` in this file.\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_reference_style_definition_with_a_dead_target_is_reported(self):
        """`[x][ref-dead]` plus its definition line `[ref-dead]: dead_reference.md`
        is the same defect class the check exists for, one syntax further."""
        self.write_index(
            CLEAN_INDEX
            + "See [the reference entry][ref-dead] for details.\n"
            + "\n"
            + "[ref-dead]: dead_reference.md\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_reference.md", findings[0])

    def test_a_reference_style_definition_with_a_live_target_is_not_reported(self):
        self.write_index(CLEAN_INDEX + "[ref-live]: project_alpha.md\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    # --- WI-0005 round 2, fix 1: a reference definition needs a real destination ---
    # Regression introduced by a838a1f: the bare `^\[label\]:` prefix match swallowed
    # the whole line as a target, misreading ordinary `[Label]: prose` glossary lines
    # as dead links. Grouped with its own non-regression probes (title, angle
    # brackets, the reference-style control) so this commit is self-contained.

    def test_reference_definition_syntax_requires_a_real_destination(self):
        """`[Label]: prose with spaces` is glossary prose, not a link reference
        definition — CommonMark rejects a destination that contains an unescaped
        space and is not wrapped in `<...>`. The bare `^\\[...\\]:` prefix match
        used to swallow the whole line as a target regardless, misreading two
        ordinary glossary entries as two dead links."""
        self.write_index(
            CLEAN_INDEX
            + "[Confidence]: a float between 0.3 and 0.9\n"
            + "[Tier]: cross-cutting versus persona-specific\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_real_link_survives_on_a_line_that_fails_reference_definition_syntax(self):
        """A line that starts like a reference definition but fails destination
        syntax must fall through to the ordinary link scan, not be swallowed by
        `next` — otherwise a real `[x](y)` link sharing the line is lost too."""
        self.write_index(
            CLEAN_INDEX
            + "[Note]: this is prose with spaces, not a definition, "
            + "but it has a [dead one](dead_after_prose.md) in it\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("target 'dead_after_prose.md'", findings[0])
        self.assertNotIn("this is prose", findings[0])

    def test_reference_style_definition_with_a_title_and_a_dead_target_is_reported(self):
        # The blank line between CLEAN_INDEX and the definition is load-bearing,
        # not layout (WI-0096, measured at the reference). CLEAN_INDEX ends in a
        # list item; without the blank line the definition-shaped line is a LAZY
        # CONTINUATION of that item's paragraph, which renders it as visible
        # prose and defines nothing. This fixture is about the definition form,
        # so it has to actually be one.
        self.write_index(CLEAN_INDEX + '\n[ref-titled-dead]: dead_titled.md "A Title"\n')

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_titled.md", findings[0])

    def test_reference_style_definition_with_a_title_and_a_live_target_is_not_reported(self):
        self.write_index(CLEAN_INDEX + '[ref-titled-live]: project_alpha.md "A Title"\n')

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_reference_style_definition_with_a_parenthesised_title_and_a_dead_target_is_reported(self):
        """`[id]: target (Title)` — CommonMark's third title delimiter, alongside
        `"..."` and `'...'` (WI-0034). A reference definition written this way
        used to be missed entirely, so its dead target was never checked."""
        # The blank line between CLEAN_INDEX and the definition is load-bearing,
        # not layout (WI-0096, measured at the reference). CLEAN_INDEX ends in a
        # list item; without the blank line the definition-shaped line is a LAZY
        # CONTINUATION of that item's paragraph, which renders it as visible
        # prose and defines nothing. This fixture is about the definition form,
        # so it has to actually be one.
        self.write_index(CLEAN_INDEX + "\n[ref-paren-dead]: dead_paren.md (A Title)\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_paren.md", findings[0])

    def test_reference_style_definition_with_a_parenthesised_title_and_a_live_target_is_not_reported(self):
        """The live-target control for the parenthesised-title form: the title
        text itself must be stripped from the checked target, not carried along
        as part of the path (which would falsely report a live file as dead)."""
        self.write_index(CLEAN_INDEX + '[ref-paren-live]: project_alpha.md (A Title)\n')

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_reference_style_definition_in_angle_brackets_resolves_when_live(self):
        """`[id]: <live.md>` — the bracket destination form, unwrapped and
        resolved like the inline `[x](<t.md>)` form pinned below (WI-0060).
        Previously this whole form was skipped outright; it is checked now, so
        this is the live control for the dead one immediately after it."""
        self.write_index(CLEAN_INDEX + "[ref-angle]: <project_alpha.md>\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_dead_reference_style_angle_bracket_target_is_reported(self):
        """Sibling-path parity for WI-0060: the reference-style definition
        `[id]: <target>` shares the same shell-side unwrap/resolve logic as the
        inline `[x](<target>)` form, so a dead target in this form must be
        caught too, not just the inline one."""
        # The blank line between CLEAN_INDEX and the definition is load-bearing,
        # not layout (WI-0096, measured at the reference). CLEAN_INDEX ends in a
        # list item; without the blank line the definition-shaped line is a LAZY
        # CONTINUATION of that item's paragraph, which renders it as visible
        # prose and defines nothing. This fixture is about the definition form,
        # so it has to actually be one.
        self.write_index(CLEAN_INDEX + "\n[ref-angle-dead]: <gone_reference_angle.md>\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_reference_angle.md", findings[0])

    def test_a_dead_reference_link_still_fires_after_the_fix(self):
        """Control probe: the reference-style path must still catch a genuine
        dead reference after the destination-validity gate is added."""
        self.write_index(
            CLEAN_INDEX
            + "See [C2][r3] for details.\n"
            + "\n"
            + "[r3]: also_dead.md\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("also_dead.md", findings[0])

    # --- WI-0005 round 2, fix 2: a fence closes only with its own delimiter type ---
    # Regression introduced by a838a1f: the untyped `in_fence` boolean toggled on
    # any fence-looking line, so a `~~~` inside an open backtick fence both hid
    # real content after the actual close (false negative) and re-opened scanning
    # one line too early on the mismatched delimiter (false positive).

    def test_fence_only_closes_with_its_own_delimiter_type(self):
        """A `~~~` line inside an open backtick fence is fence *content*, not a
        close — CommonMark closes a fence only with the same character, at least
        as long as the opener."""
        self.write_index(
            CLEAN_INDEX
            + "```markdown\n"
            + "- [Example](dead_in_fence.md)\n"
            + "~~~\n"
            + "- [Example2](dead_after_mismatched_close.md)\n"
            + "```\n"
            + "- [AfterFence](dead_after_fence.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_after_fence.md", findings[0])

    def test_dead_link_inside_a_tilde_fence_is_not_reported(self):
        self.write_index(CLEAN_INDEX + "~~~\n- [Example](dead_tilde_fence.md)\n~~~\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_dead_link_inside_a_backtick_fence_with_an_info_string_is_not_reported(self):
        self.write_index(
            CLEAN_INDEX + "```markdown\n- [Example](dead_info_string.md)\n```\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    # The two tests above already pin same-length open/close and delimiter-type
    # mismatch; neither exercises the length inequality the fence regex encodes
    # (`fence_char{fence_len,}` — closer length >= opener length, not ==).

    def test_a_fence_closes_when_the_closing_run_is_longer_than_the_opener(self):
        """CommonMark: a fence closes on a same-character run *at least* as long
        as the opener — a 3-backtick opener closes on 4 backticks."""
        self.write_index(
            CLEAN_INDEX
            + "```\n"
            + "- [Example](dead_in_fence_3_4.md)\n"
            + "````\n"
            + "- [AfterFence](dead_after_fence_3_4.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_after_fence_3_4.md", findings[0])

    def test_a_fence_does_not_close_when_the_closing_run_is_shorter_than_the_opener(self):
        """A 4-backtick opener does not close on 3 backticks — the short run is
        fence content, and everything after it stays fenced until a run of at
        least 4 backticks is seen."""
        self.write_index(
            CLEAN_INDEX
            + "````\n"
            + "- [Example](dead_in_fence_4_3.md)\n"
            + "```\n"
            + "- [StillFenced](dead_still_fenced_4_3.md)\n"
            + "````\n"
            + "- [AfterFence](dead_after_fence_4_3.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_after_fence_4_3.md", findings[0])

    # --- WI-0032: an unclosed fence silently drops the rest of the file ------------
    # An unclosed fence running to end-of-document is correct CommonMark — confirmed
    # against a reference implementation, the link after it really does render
    # inside <pre><code>, not as a link — so the skip itself stays. What was silent
    # is the failure MODE: nothing said the scope had shrunk. These two tests pin a
    # warning naming the opening line, not a change to what gets checked.

    def test_an_unclosed_fence_warns_and_names_its_opening_line(self):
        """A fence opened and never closed swallows every remaining line — link
        checking stops there. That must now be visible, not silent."""
        self.write_index(
            CLEAN_INDEX
            + "```\n"
            + "- [Example](dead_after_unclosed_fence.md)\n"
        )

        result = self.run_lint()

        self.assertEqual(self.link_findings(result.stdout), [])
        warnings = self.findings(result.stdout, "Warnings")
        # CLEAN_INDEX is 12 lines; the fence opens on the next line, 13.
        self.assertTrue(
            any("13" in w and "never closed" in w for w in warnings), warnings
        )

    def test_a_closed_fence_does_not_warn_about_an_unclosed_one(self):
        """Control: a fence that closes before end-of-file must not trigger the
        new warning at all."""
        self.write_index(
            CLEAN_INDEX + "```\n- [Example](dead_fenced.md)\n```\n- [After](dead_after_fenced.md)\n"
        )

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("never closed" in w for w in warnings), warnings)
        # WI-0128: "no 'never closed' warning" is also true of a scan that never
        # ran at all. Prove the fence genuinely re-opened link checking by
        # requiring the dead link written AFTER the close to still be caught —
        # a state-machine regression that left in_fence stuck true would swallow
        # it and this would go red.
        findings = self.link_findings(result.stdout)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_after_fenced.md", findings[0])

    # --- WI-0043: an unclosed HTML comment silently switches the check off too -----
    # Same defect class as the unclosed-fence case above, one construct over: an
    # HTML comment block opened at the start of a line and never closed swallows
    # every remaining line as raw HTML per CommonMark (WI-0041) — correct, and no
    # link there is ever missed. What was silent is the failure MODE: the check's
    # scope shrinks to nothing with no word said. Reuses the same end-of-input
    # sentinel mechanism WI-0032 built for the fence case.

    def test_an_unclosed_html_comment_warns_and_names_its_opening_line(self):
        """A block-level HTML comment opened and never closed swallows every
        remaining line — link checking stops there. That must now be visible."""
        self.write_index(
            CLEAN_INDEX
            + "<!--\n"
            + "- [Example](dead_after_unclosed_comment.md)\n"
        )

        result = self.run_lint()

        self.assertEqual(self.link_findings(result.stdout), [])
        warnings = self.findings(result.stdout, "Warnings")
        # CLEAN_INDEX is 12 lines; the comment opens on the next line, 13.
        self.assertTrue(
            any("13" in w and "never closed" in w for w in warnings), warnings
        )

    def test_a_closed_html_comment_does_not_warn_about_an_unclosed_one(self):
        """Control: a comment block that closes before end-of-file must not
        trigger the new warning at all."""
        self.write_index(
            CLEAN_INDEX + "<!--\n- [Example](dead_commented.md)\n-->\n- [After](dead_after_commented.md)\n"
        )

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("never closed" in w for w in warnings), warnings)
        # WI-0128: same proof as the fence control above — the dead link written
        # AFTER the comment closes must still be caught, or in_html_comment got
        # stuck true and this scan silently stopped checking links.
        findings = self.link_findings(result.stdout)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_after_commented.md", findings[0])

    def test_the_unclosed_comment_warning_names_its_own_construct(self):
        """Both mechanisms report 'never closed' — the message must still say
        WHICH construct opened, so a report reader is not left guessing."""
        self.write_index(CLEAN_INDEX + "<!--\n- [Example](dead_after_unclosed_comment.md)\n")

        warnings = self.findings(self.run_lint().stdout, "Warnings")

        matching = [w for w in warnings if "never closed" in w]
        self.assertEqual(len(matching), 1, matching)
        self.assertIn("HTML comment", matching[0])

    # --- WI-0045: a fence look-alike inside an open comment must not set in_fence --
    # The fence-opener check ran unconditionally, not gated on in_html_comment (the
    # reverse direction already was: `if (in_fence)` runs first and unconditionally
    # `next`s, so nothing inside a real fence can ever be misread as a comment
    # opener). A line that merely LOOKS like a fence opener while a comment is open
    # set in_fence anyway, and the comment's own closing line was then swallowed by
    # the in_fence branch before it ever reached the comment-close check —
    # in_html_comment stayed set forever. Both repros measured against the
    # CommonMark reference implementation before writing these tests.

    def test_a_fence_look_alike_inside_an_open_comment_does_not_block_it_from_closing(self):
        """A bare fence marker inside an open HTML comment must not set in_fence —
        otherwise the comments own closing line is swallowed by the fence branch
        and the comment never closes. Reference-confirmed: the comment does close
        and the link after it is live, so it must be reported dead."""
        self.write_index(
            CLEAN_INDEX
            + "<!--\n"
            + "```\n"
            + "-->\n"
            + "[real link](nope.md)\n"
        )

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("never closed" in w for w in warnings), warnings)
        findings = self.link_findings(result.stdout)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("nope.md", findings[0])

    def test_a_fence_look_alike_inside_a_closed_comment_does_not_hide_a_later_real_fence(self):
        """Second measured repro: once the fence look-alike no longer sets in_fence,
        the comment closes normally, the link between the comment and a REAL fence
        opened afterward is checked (and is dead), and the link inside that real,
        still-open fence stays unreported — matching the reference render exactly."""
        self.write_index(
            CLEAN_INDEX
            + "<!--\n"
            + "```\n"
            + "-->\n"
            + "[between](between.md)\n"
            + "```\n"
            + "[after](after.md)\n"
        )

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("HTML comment" in w for w in warnings), warnings)
        matching = [w for w in warnings if "never closed" in w]
        self.assertEqual(len(matching), 1, matching)
        self.assertIn("code fence", matching[0])
        findings = self.link_findings(result.stdout)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("between.md", findings[0])

    # --- WI-0005 round 2, fix 3: an unpaired backtick is literal text --------------
    # Regression introduced by a838a1f: `strip_inline_code()` dropped everything
    # after a stray backtick once it ran out of a second one, silently losing a
    # real link that followed on the same line — CommonMark treats an unpaired
    # backtick as literal text, not a code-span opener.

    def test_unpaired_backtick_does_not_swallow_the_rest_of_the_line(self):
        """A single stray backtick is not a code-span opener without a matching
        closer — CommonMark leaves it as literal text."""
        self.write_index(
            CLEAN_INDEX
            + "- Note ` unterminated then [Real](dead_after_tick.md)\n"
            + "- Control [Plain](dead_plain.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        joined = " ".join(findings)
        self.assertIn("dead_after_tick.md", joined)
        self.assertIn("dead_plain.md", joined)

    def test_dead_link_inside_nested_double_backticks_is_not_reported(self):
        self.write_index(
            CLEAN_INDEX + "Example: `` a ` b [x](dead_nested_backticks.md) ` `` in prose.\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    # --- WI-0005 round 3, fix 4: pair backticks by run length, not position -------
    # Position-based pairing (1st backtick with 2nd, 3rd with 4th) is not what
    # CommonMark does: a code span opens with a backtick *run* of length N and
    # closes at the next run of exactly length N — a run of a different length
    # is content, not a closer. The double-backtick case below is the one this
    # fix actually changes: pre-fix, the lone backtick inside the span could get
    # paired with one of the span's own delimiters, breaking the pairing for the
    # rest of the line.

    def test_double_backtick_span_containing_a_single_backtick_is_not_reported(self):
        """A run of length 2 closes only with another run of length 2 — a lone
        backtick inside it is content, not a closer for either delimiter."""
        self.write_index(CLEAN_INDEX + "``a ` b [x](dead_inside_double_span.md)``\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_stray_backtick_before_a_paired_span_still_exposes_the_link(self):
        """Not a regression pin for a fix — a documented finding.

        Every backtick in this line is a run of length 1, so run-length pairing
        and position-based pairing agree: the stray backtick (opener) pairs with
        the backtick that precedes "[Example]" (the nearest same-length run),
        consuming the text between them as a code span. The backtick that was
        meant to close the illustration is then unpaired and, per fix 3
        (a838a1f), kept as literal text — which leaves the illustration's own
        link exposed as a live, non-code link. This is not a bug: it is verified
        against a spec-compliant CommonMark implementation (commonmark.py 0.9.x)
        — the identical input renders `<a href="dead_after_stray_tick.md">`, not
        code. Reported 19.08.2026 against the assumption (WI-0005 round 3) that
        run-length pairing alone would silence this case; it does not, because
        the two algorithms only diverge when run lengths differ (see the
        double-backtick test above), and every run here is length 1.
        """
        self.write_index(
            CLEAN_INDEX
            + "- Note: a stray ` mark, then an illustration "
            + "`[Example](dead_after_stray_tick.md)` here.\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_after_stray_tick.md", findings[0])

    def test_a_live_link_inside_a_table_cell_is_not_reported(self):
        self.write_index(
            CLEAN_INDEX
            + "| Name | Link |\n"
            + "| --- | --- |\n"
            + "| Alpha | [Alpha](project_alpha.md) |\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_line_with_an_odd_backtick_count_and_no_link_stays_silent(self):
        self.write_index(CLEAN_INDEX + "- Just an odd backtick ` here, no link at all.\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_simple_dead_link_still_fires_after_the_fix(self):
        """Control probe: the plain-link path this check exists for must be
        untouched by any of the three fixes above."""
        self.write_index(CLEAN_INDEX + "- [Ghost](dead_plain_control.md)\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_plain_control.md", findings[0])

    # --- The angle-bracket destination form `[x](<t.md>)` (WI-0060) ----------------
    # CommonMark's bracket form protects a destination that may contain a space
    # (see the space-form tests above) or other characters that would otherwise
    # need escaping. It used to be skipped outright by an explicit case arm
    # (`\<*`), which made a DEAD target written this way invisible — the report
    # checked nothing, not even under the bracketed name. It is unwrapped and
    # resolved like any other target now; one test per row of the reference
    # table settled in docs/memory/reference_commonmark-conformance.md.

    def test_a_live_angle_bracket_target_is_not_reported(self):
        """`[x](<a.md>)` where `a.md` exists — the live control for the dead
        one directly below. Previously silent because the form was skipped;
        silent now because it resolves and the file is there."""
        self.write_index(CLEAN_INDEX + "- [Angle](<project_alpha.md>) — live\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_dead_angle_bracket_target_is_reported(self):
        """The WI-0060 defect itself: a dead target written in bracket form
        used to pass silently. It must be caught exactly like the plain form."""
        self.write_index(CLEAN_INDEX + "- [Angle](<gone_angle.md>) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_angle.md", findings[0])
        self.assertNotIn("<", findings[0])
        self.assertNotIn(">", findings[0])

    def test_an_angle_bracket_target_with_a_title_outside_the_brackets_resolves(self):
        """`[x](<a.md> "T")` — CommonMark puts the title outside the brackets
        for this form; it must be stripped the same way it is for the plain
        form, leaving `a.md` as the checked target."""
        self.write_index(CLEAN_INDEX + '- [Angle](<project_alpha.md> "A Title") — live\n')

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_an_unclosed_angle_bracket_target_stays_silent(self):
        """`[x](<a.md)` — no matching `>` before the destination ends. Per
        CommonMark this is NOT a valid link at all, unlike the closed form.
        Deliberately pointed at a target that does not exist either, so a
        report here could only come from unwrapping a bracket that was never
        closed — exactly the over-eager fix WI-0060 warns against."""
        self.write_index(CLEAN_INDEX + "- [Angle](<gone_unclosed.md) — not a link\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_an_empty_angle_bracket_target_is_silent(self):
        """`[x](<>)` — an explicitly empty destination. Nothing to resolve, so
        nothing to report; it must not be misread as a same-directory link."""
        self.write_index(CLEAN_INDEX + "- [Angle](<>) — empty destination\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_an_angle_bracket_target_with_a_fragment_resolves_to_the_file(self):
        """`[x](<a.md#sec>)` — the fragment sits inside the brackets here,
        unlike the plain form's `a.md#sec`; it must still be dropped before
        the file existence check, exactly like the plain form."""
        self.write_index(CLEAN_INDEX + "- [Angle](<project_alpha.md#section>) — live\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_root_absolute_angle_bracket_target_resolves(self):
        """`[x](</a.md>)` — root-absolute, same as the plain form's `/a.md`,
        just wrapped. Resolves against the project root once unwrapped."""
        self.write_index(CLEAN_INDEX + "- [Angle](</docs/memory/project_alpha.md>) — live\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    # --- Indented code blocks and non-comment HTML blocks are not inline-parsed ----
    # (WI-0084). Measured at the reference (docs/memory/reference_commonmark-
    # conformance.md, WI-0005 round 2): check (n)'s block-boundary list tracked
    # fences and `<!--` HTML comments, but not an indented code block (>=4 spaces
    # or a leading tab) or any other CommonMark HTML block type (`<div>`, `<pre>`,
    # `<script>`, ...). Both are contexts CommonMark never inline-parses at all —
    # a bracketed `[text](dest)` inside either is literal text, not a link, and
    # reporting its destination as dead is a false positive.

    def test_an_indented_code_block_with_four_spaces_is_not_reported(self):
        """A line indented >=4 spaces, preceded and followed by a blank line, is
        a CommonMark indented code block — its content is never inline-parsed."""
        self.write_index(
            CLEAN_INDEX + "\n" + "    [link](dead_indent_four.md)\n" + "\n" + "after paragraph\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_tab_indented_code_block_is_not_reported(self):
        """Same construct, triggered by a single leading tab instead of four
        literal spaces — CommonMark treats a tab as reaching the next 4-space
        stop, so this is the same indented-code-block shape, not a different one."""
        self.write_index(
            CLEAN_INDEX + "\n" + "\t[link](dead_indent_tab.md)\n" + "\n" + "after paragraph\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_an_indented_line_continuing_an_open_paragraph_is_still_checked(self):
        """An indented code block CANNOT interrupt a paragraph (CommonMark) — a
        4-space-indented line directly continuing an already-open paragraph (no
        blank line before it) is ordinary paragraph continuation text, not a
        code block, and its link must still be checked. Regression control for
        the pbuf_n==0 gate the indented-code skip above relies on."""
        self.write_index(
            CLEAN_INDEX
            + "Paragraph line one\n"
            + "    continuation indented four [link](dead_lazy_indent.md) spaces\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_lazy_indent.md", findings[0])

    def test_a_div_html_block_around_a_link_is_not_reported(self):
        """`<div>`...`</div>` opens a CommonMark HTML block (type 6): every line
        up to the next blank line is raw HTML, not inline-parsed."""
        self.write_index(
            CLEAN_INDEX + "\n" + "<div>\n" + "[link](dead_html_div.md)\n" + "</div>\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_pre_html_block_around_a_link_is_not_reported(self):
        """`<pre>`...`</pre>` — HTML block type 1 (raw-text element), a
        different closing rule than `<div>`'s (see the two tests below)."""
        self.write_index(
            CLEAN_INDEX + "\n" + "<pre>\n" + "[link](dead_html_pre.md)\n" + "</pre>\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_script_html_block_around_a_link_is_not_reported(self):
        """`<script>`...`</script>` — same type-1 mechanism as `<pre>`, the
        bracketed text sits inside a JS string literal rather than prose."""
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "<script>\n"
            + "var x = '[link](dead_html_script.md)';\n"
            + "</script>\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_div_block_closes_at_the_next_blank_line_not_at_the_closing_tag(self):
        """The construction trap this item was measured against: HTML block type
        6 ends at the next BLANK LINE, not at a matching `</div>`. A link on the
        line immediately after `</div>` (no blank line yet) is still inside the
        block and must not be reported; the same link, once a blank line has
        actually occurred, is ordinary markdown again and must be reported."""
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "<div>\n"
            + "foo\n"
            + "</div>\n"
            + "[link](dead_html_div_no_blank.md)\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "<div>\n"
            + "foo\n"
            + "</div>\n"
            + "\n"
            + "[link](dead_html_div_after_blank.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_html_div_after_blank.md", findings[0])

    def test_a_div_block_interrupted_by_a_blank_line_releases_the_link_inside(self):
        """The other half of the same trap, non-consecutive this time: `<div>`,
        blank line, a link, blank line, `</div>` — the blank line right after
        the opener already ends the type-6 block, so the link in the middle
        sits in ordinary markdown (not raw HTML) and must be reported."""
        self.write_index(
            CLEAN_INDEX
            + "\n"
            + "<div>\n"
            + "\n"
            + "[link](dead_html_div_interrupted.md)\n"
            + "\n"
            + "</div>\n"
        )

        findings = self.link_findings(self.run_lint().stdout)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_html_div_interrupted.md", findings[0])

    # --- Backslash escapes remove structural meaning (WI-0079/WI-0081) -------------
    # CommonMark backslash-escapes a bracket or a closing paren exactly the way it
    # escapes any other ASCII punctuation: the escaped character loses whatever
    # structural role it would otherwise have, and becomes literal text instead.
    # Measured at the reference (docs/memory/reference_commonmark-conformance.md,
    # WI-0005 round): `\[text\](t.md)` renders as literal text, not a link — the
    # escape does not need to hit BOTH brackets, either one alone is enough.

    def test_a_backslash_escaped_bracket_pair_is_not_reported_as_a_link(self):
        """`\\[not a link\\](t.md)` — both structural brackets are escaped, so the
        whole construct is literal text per CommonMark (WI-0079). check (n)'s
        label/dest regex used to have no escape awareness at all and matched
        starting at the `[` right after the first backslash, reporting the
        parenthesised text as a dead link target that was never a link."""
        self.write_index(CLEAN_INDEX + "- \\[not a link\\](gone_esc1.md) — not a link\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_an_escaping_backslash_on_only_the_closing_bracket_also_defeats_the_link(self):
        """`[text\\](t.md)` — only the CLOSING bracket is escaped. Measured at the
        reference: also not a link (escaping either one bracket is sufficient,
        not just the pair together)."""
        self.write_index(CLEAN_INDEX + "- [not a link\\](gone_esc_close_only.md) — not a link\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_an_escaped_bracket_pair_does_not_hide_a_real_link_beside_it(self):
        """The fix must reject exactly the escaped span, not the whole line: a
        real, unescaped link right next to an escaped non-link must still be
        found. Neighbour fixture for the corpus addition this work item asks
        for — a construct that is NOT a link beside one that is."""
        self.write_index(
            CLEAN_INDEX
            + "- \\[escaped\\](gone_esc_mix1.md) and [real](gone_esc_mix2.md) — mixed\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_esc_mix2.md", findings[0])
        self.assertNotIn("gone_esc_mix1.md", findings[0])

    def test_a_doubly_escaped_backslash_before_a_bracket_does_not_escape_it(self):
        """`\\\\[text](t.md)` — an escaped backslash (`\\\\` decodes to one
        literal `\\`) followed by an UNESCAPED `[`. Backslash-escape parity,
        not "is the previous byte a backslash": the bracket here structurally
        opens a real link, per the reference. A naive one-byte lookbehind would
        wrongly treat this `[` as escaped and stay silent."""
        self.write_index(CLEAN_INDEX + "- \\\\[real link](gone_esc_dbl.md) — live\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_esc_dbl.md", findings[0])

    # --- A link destination is inline-resolved, not taken literally (WI-0081) ------
    # `[text](dest)` in link TEXT is opaque to CommonMark's inline grammar, but a
    # destination is not — a backslash-escape or a numeric character reference
    # inside it resolves before the destination string exists at all. Measured at
    # the reference (docs/memory/reference_commonmark-conformance.md, WI-0005
    # round): `[x](a\).md)` resolves to `a).md`, and `[x](a&#35;b.md)` resolves to
    # `a#b.md` — the naive stop-at-first-`)`/undecoded-entity scan in
    # protect_link_destinations() used to garble both.

    def test_an_escaped_closing_paren_in_the_destination_resolves_the_full_target(self):
        """`[x](gone_esc_paren\\).md)` — check (n)'s destination capture used to
        stop at the escaped `)`, truncating the target to `gone_esc_paren\\`
        and losing `.md)` entirely. The reference decodes the escape (one
        real link, href `gone_esc_paren).md`)."""
        self.write_index(CLEAN_INDEX + "- [Esc](gone_esc_paren\\).md) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_esc_paren).md", findings[0])
        self.assertNotIn("\\", findings[0])

    def test_a_destination_after_an_escaped_paren_is_still_reached_on_the_same_line(self):
        """Two destinations on one line, the first carrying an escaped `)`: the
        boundary scan must resume right after the REAL closing paren, not
        somewhere inside what would have been the truncated old target — or a
        second link further along the same line would be lost too."""
        self.write_index(
            CLEAN_INDEX
            + "- [First](gone_esc_paren2\\).md) and [Second](gone_esc_paren3.md) — both dead\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 2, findings)
        joined = " ".join(findings)
        self.assertIn("gone_esc_paren2).md", joined)
        self.assertIn("gone_esc_paren3.md", joined)

    def test_an_unbalanced_open_paren_in_the_destination_invents_no_target(self):
        """WI-0100/WI-0118, fixed: `[](()` is plain text at the reference — a
        lone, unbalanced `(` inside the destination never finds a `)` of its
        own to close it. check (n)'s destination-closing scan used to take
        the first unescaped `)` as the delimiter regardless (the `)` that
        actually closes the nested `(`), and reported an invented target
        named `(`."""
        self.write_index(CLEAN_INDEX + "- [](()\n")

        result = self.run_lint()

        self.assertEqual(self.link_findings(result.stdout), [])

    def test_nested_empty_brackets_before_an_unbalanced_paren_invent_no_target(self):
        """WI-0100's second witness: `[[]](()` reaches the same broken scan
        through a different route — the outer `[]` is a live, unescaped
        opener/closer pair (correctly recognised as one), so it still hits
        the unbalanced destination-closing scan the fixture above pins
        directly."""
        self.write_index(CLEAN_INDEX + "- [[]](()\n")

        result = self.run_lint()

        self.assertEqual(self.link_findings(result.stdout), [])

    def test_balanced_parens_inside_a_destination_resolve_to_the_full_path(self):
        """WI-0118, fixed: `[a](gone_bp1(paren)suffix.md)` — a balanced pair
        of parens inside the destination is ordinary destination TEXT per
        CommonMark, not a delimiter. check (n)'s scan used to stop at the
        first `)` (right after "paren"), truncating the reported target to
        `gone_bp1(paren` instead of resolving the full, balanced path."""
        self.write_index(CLEAN_INDEX + "- [a](gone_bp1(paren)suffix.md) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_bp1(paren)suffix.md", findings[0])

    def test_a_destination_after_a_balanced_paren_pair_is_still_reached_on_the_same_line(self):
        """Same companion pattern as the escaped-paren and numeric-entity
        fixtures above: a balanced-paren destination must not swallow a
        second, later destination on the same line."""
        self.write_index(
            CLEAN_INDEX
            + "- [First](gone_bp2(x)y.md) and [Second](gone_bp3.md) — both dead\n"
        )

        findings = self.link_findings(self.run_lint().stdout)
        joined = " ".join(findings)

        self.assertEqual(len(findings), 2, findings)
        self.assertIn("gone_bp2(x)y.md", joined)
        self.assertIn("gone_bp3.md", joined)

    def test_angle_bracket_destination_paren_balance_is_left_untouched(self):
        """WI-0118's negative control: the angle-bracket destination form
        (WI-0060) has its own termination rule — an unescaped `>` closes it,
        and a paren inside carries no balance requirement at all. The fix
        gates its paren-depth counter on the destination NOT starting with
        `<`, so `[a](<gone_bp4(inner.md>)` must keep resolving exactly as it
        did before the fix."""
        self.write_index(CLEAN_INDEX + "- [a](<gone_bp4(inner.md>) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_bp4(inner.md", findings[0])

    def test_a_decimal_numeric_entity_in_the_destination_decodes_before_resolving(self):
        """`&#35;` is CommonMark's decimal numeric character reference for `#`
        — the reference resolves `[x](gone_ent_dec&#35;3.md)` to the single
        target `gone_ent_dec#3.md`. check (n) used to resolve the raw,
        undecoded text, AND its own shell-side fragment-anchor strip
        (`${target%%#*}`) then cut at the entity's own literal `#` byte,
        truncating the report to `gone_ent_dec&` — a decoded `#` is not a
        fragment separator."""
        self.write_index(CLEAN_INDEX + "- [Dec](gone_ent_dec&#35;3.md) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_ent_dec#3.md", findings[0])
        self.assertNotIn("&", findings[0])

    def test_a_numeric_entity_closing_paren_reaches_the_report_as_a_literal_paren(self):
        """`&#41;` decodes to `)` — a closing paren that appears INSIDE the
        destination after decoding, which is the state the whole `paren_mark`
        detour used to exist to avoid. It cannot be avoided here: the decode
        runs after the escape substitution, so this destination has carried a
        literal `)` through every later stage since WI-0081, and the reference
        agrees on the target (`gone_ent_paren)b.md`). That is what makes the
        detour removable rather than merely unpinnable — this fixture already
        pins the post-removal state, and it did so before the removal."""
        self.write_index(CLEAN_INDEX + "- [Ent](gone_ent_paren&#41;b.md) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_ent_paren)b.md", findings[0])
        self.assertNotIn("&", findings[0])

    def test_a_destination_after_an_entity_encoded_paren_is_still_reached_on_the_same_line(self):
        """The escaped-paren line's twin, one encoding over: a decoded `)`
        inside the first destination must not be read as that destination's
        delimiter either, or the second link on the line is lost."""
        self.write_index(
            CLEAN_INDEX
            + "- [First](gone_ent_paren2&#41;b.md) and [Second](gone_ent_paren3.md) — both dead\n"
        )

        findings = self.link_findings(self.run_lint().stdout)
        joined = " ".join(findings)

        self.assertEqual(len(findings), 2, findings)
        self.assertIn("gone_ent_paren2)b.md", joined)
        self.assertIn("gone_ent_paren3.md", joined)

    def test_a_hexadecimal_numeric_entity_in_the_destination_decodes_the_same_way(self):
        """`&#x23;` is the hexadecimal form of the same numeric character
        reference (`#`, codepoint 0x23) — same decode path as the decimal
        case, a second, structurally different fixture so the fix is not
        pinned to the decimal spelling only."""
        self.write_index(CLEAN_INDEX + "- [Hex](gone_ent_hex&#x23;3.md) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_ent_hex#3.md", findings[0])
        self.assertNotIn("&", findings[0])

    def test_a_numeric_entity_decoding_to_a_plain_character_needs_no_hash_protection(self):
        """`&#46;` decodes to `.` (codepoint 46) — proves the decode mechanism
        works generally, not only for the one codepoint (`#`) that needs the
        fragment-strip sentinel."""
        self.write_index(CLEAN_INDEX + "- [Dot](gone_ent_dot&#46;md) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_ent_dot.md", findings[0])

    def test_a_decoded_hash_entity_still_resolves_when_the_file_actually_exists(self):
        """Live control for the decimal-entity case: `gone_ent_dec#3.md`
        (the DECODED name) exists on disk. If the fix instead left the
        fragment-strip cutting the decoded `#`, this would silently pass for
        the wrong reason — pinning the live case catches that."""
        live_target = self.memory_dir / "gone_ent_dec#3.md"
        live_target.write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        self.write_index(CLEAN_INDEX + "- [Dec](gone_ent_dec&#35;3.md) — live\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    # --- Link labels are scanned, not regex-matched (WI-0080/WI-0091) -------------
    # CommonMark's link text may contain balanced brackets at any depth, plus
    # backslash-escaped brackets anywhere. check (n)'s label class used to be
    # `[^][]*`, which excludes BOTH bracket characters — so no label carrying a
    # bracket could ever match, at any depth. Every expectation below was measured
    # against the reference (commonmark 0.9.2), see
    # docs/memory/reference_commonmark-conformance.md.

    def test_balanced_brackets_in_the_link_text_do_not_hide_the_link(self):
        """`[a [b] c](t.md)` — the reference renders one ordinary link
        (`<a href="t.md">a [b] c</a>`). The old `[^][]*` label class could not
        match a label with a bracket in it at all, so check (n) stayed silent
        on every such entry (WI-0080)."""
        self.write_index(CLEAN_INDEX + "- [a [b] c](gone_nb1.md) — nested label\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_nb1.md", findings[0])

    def test_three_levels_of_balanced_brackets_in_the_link_text_are_still_one_link(self):
        """`[a [b [c] d] e](t.md)` — reference-measured as a single link to
        `t.md`. A fix that only tolerated ONE bracket pair would leave this
        one silent, so the depth is pinned separately from the shallow case."""
        self.write_index(CLEAN_INDEX + "- [a [b [c] d] e](gone_nb3.md) — three levels\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_nb3.md", findings[0])

    def test_five_levels_of_balanced_brackets_in_the_link_text_are_still_one_link(self):
        """`[l4 [l3 [l2 [l1 [l0 x r0] r1] r2] r3] r4](t.md)` — the reference
        imposes no nesting limit (measured to depth 100 during the WI-0080
        round; five is the fixture depth kept in the suite). Pins that the
        scanner's bracket stack has no fixed ceiling either."""
        self.write_index(
            CLEAN_INDEX
            + "- [l4 [l3 [l2 [l1 [l0 x r0] r1] r2] r3] r4](gone_nb5.md) — five levels\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_nb5.md", findings[0])

    def test_a_backslash_escaped_closing_bracket_inside_the_label_keeps_the_link(self):
        """`[a\\]b](t.md)` — the escaped `]` is literal label text, so the label
        is `a]b` and the link is live (reference-measured). The old label class
        excluded `]` outright and never matched (WI-0080); the scanner must
        skip an escaped bracket as content instead of ending the label there."""
        self.write_index(CLEAN_INDEX + "- [a\\]b](gone_nb_esc.md) — escaped bracket in label\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_nb_esc.md", findings[0])

    def test_a_link_inside_the_link_text_disqualifies_the_outer_link(self):
        """CommonMark: "Links may not contain other links, at any level of
        nesting" — the INNER link wins and the outer brackets are literal text.
        Reference-measured: `[a [b](in.md) c](out.md)` yields exactly one
        `<a>`, to `in.md`. Before the scanner this happened by accident (the
        outer label simply could not match); now it is an explicit rule and
        needs its own pin."""
        self.write_index(
            CLEAN_INDEX
            + "- [a [b](gone_inner.md) c](gone_outer.md) — link in link text\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_inner.md", findings[0])
        self.assertNotIn("gone_outer.md", " ".join(findings))

    def test_a_disqualified_outer_link_does_not_swallow_a_later_link_on_the_same_line(self):
        """The outer opener is deactivated, not the rest of the line: a further,
        independent link after the nested construct is still found. Reference-
        measured: `[a [b](in.md) c](out.md) and [d](e.md)` yields `in.md` and
        `e.md`, never `out.md`."""
        self.write_index(
            CLEAN_INDEX
            + "- [a [b](gone_in2.md) c](gone_out2.md) and [d](gone_e2.md) — mixed\n"
        )

        findings = self.link_findings(self.run_lint().stdout)
        joined = " ".join(findings)

        self.assertEqual(len(findings), 2, findings)
        self.assertIn("gone_in2.md", joined)
        self.assertIn("gone_e2.md", joined)
        self.assertNotIn("gone_out2.md", joined)

    def test_an_image_inside_the_link_text_does_not_disqualify_the_outer_link(self):
        """`[![alt](img.png)](t.md)` — the badge pattern. An IMAGE in the link
        text is allowed (only a LINK disqualifies), so the reference renders a
        live link to `t.md` whose content is an `<img>`. The hardest shape for
        any `](`-splitting approach, because the label itself contains `](`
        (WI-0091)."""
        self.write_index(
            CLEAN_INDEX + "- [![alt](gone_badge.png)](gone_ci.md) — badge\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_ci.md", findings[0])
        self.assertNotIn("gone_badge.png", " ".join(findings))

    def test_an_image_nested_two_deep_inside_the_link_text_still_leaves_one_link(self):
        """`[![![deep](d1.png)](d2.png)](t.md)` — reference-measured: one link
        (`t.md`), two images (`d2.png`, `d1.png`), no image ever reported.
        Pins that image openers are neither reported nor deactivated at depth."""
        self.write_index(
            CLEAN_INDEX
            + "- [![![deep](gone_d1.png)](gone_d2.png)](gone_d3.md) — nested images\n"
        )

        findings = self.link_findings(self.run_lint().stdout)
        joined = " ".join(findings)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_d3.md", joined)
        self.assertNotIn("gone_d1.png", joined)
        self.assertNotIn("gone_d2.png", joined)

    def test_an_image_whose_alt_text_carries_brackets_is_still_not_a_link(self):
        """Negative pin for the image rule under the new scanner: `![[a]](i.png)`
        is an image, reference-measured (no `<a>` at all). The old code decided
        this on the single byte before `[`; the scanner decides it on the
        bracket opener it pushed, and must reach the same answer with a
        bracketed alt text that the old label class could never have matched."""
        self.write_index(CLEAN_INDEX + "- ![[a]](gone_img_nb.png) — image\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_an_escaped_bang_before_the_bracket_leaves_a_real_link(self):
        """`\\![a](t.md)` — the `!` is backslash-escaped, so it is literal text
        and the bracket opens a LINK, not an image (reference-measured: one
        `<a href="t.md">`). The image test must use escape parity, not a bare
        "previous byte is a bang"."""
        self.write_index(CLEAN_INDEX + "- \\![a](gone_escbang.md) — escaped bang\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_escbang.md", findings[0])

    def test_an_unbalanced_closing_bracket_before_the_destination_is_not_a_link(self):
        """Negative pin, the one shape a bracket-counting fix is most likely to
        break: `[a] b](t.md)`. The reference renders NO link — the `[a]` closes
        on its own and the second `]` has no opener left. A scanner that merely
        looked for the last `](` on the line would wrongly report `t.md`."""
        self.write_index(CLEAN_INDEX + "- [a] b](gone_unbalanced.md) — not a link\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_nested_bracket_link_beside_an_escaped_non_link_is_still_found(self):
        """WI-0079's one-byte-advance guarantee, restated for the scanner: an
        escaped, disqualified construct earlier on the line must not hide a real
        (here: nested-bracket) link later on it. The scanner never skips ahead by
        a match length, so this holds structurally — pinned so a future rewrite
        that reintroduces a skip is caught."""
        self.write_index(
            CLEAN_INDEX
            + "- \\[escaped\\](gone_nb_skip1.md) and [a [b] c](gone_nb_skip2.md) — mixed\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_nb_skip2.md", findings[0])
        self.assertNotIn("gone_nb_skip1.md", " ".join(findings))

    def test_a_nested_bracket_label_combines_with_an_escaped_paren_destination(self):
        """`[a [b] c](t\\).md)` — WI-0080's label scan and WI-0081's destination
        scan on the same construct. Reference-measured: one link, href
        `t).md`. Pins that the scanner reads the destination through the
        `dest_mark` span protect_link_destinations() already built, rather than
        re-finding the closing paren itself."""
        self.write_index(CLEAN_INDEX + "- [a [b] c](gone_nb_paren\\).md) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_nb_paren).md", findings[0])

    def test_a_nested_bracket_link_whose_target_exists_stays_silent(self):
        """Live control for the whole WI-0080 group: the same nested-bracket
        shape, but the target is on disk. Without this, every assertion above
        would also pass for a scanner that reports EVERY bracket construct as
        dead."""
        live_target = self.memory_dir / "live_nb.md"
        live_target.write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        self.write_index(CLEAN_INDEX + "- [a [b] c](live_nb.md) — live\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_badge_style_link_whose_target_exists_stays_silent(self):
        """Live control for the image-in-link-text rule (WI-0091): the badge
        shape resolving to a real file must produce no finding — otherwise the
        rule could be "report the outer destination unconditionally"."""
        live_target = self.memory_dir / "live_ci.md"
        live_target.write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        (self.memory_dir / "live_badge.png").write_text("x", encoding="utf-8")
        self.write_index(CLEAN_INDEX + "- [![alt](live_badge.png)](live_ci.md) — live\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    # --- A reference link in the link text disqualifies the outer link too (WI-0093) ---
    # CommonMark's "no links in links" rule fires on any successful LINK, not only
    # on an inline one: a shortcut (`[ref]`), collapsed (`[ref][]`) or full
    # (`[text][ref]`) reference that RESOLVES against a definition deactivates
    # every enclosing link opener exactly like `[b](in.md)` does. Deciding it
    # needs the document's reference-definition labels, which CommonMark collects
    # for the WHOLE document before any inline parsing — so a definition may sit
    # AFTER its use. Every expectation below was measured against the reference
    # (commonmark 0.9.2), see docs/memory/reference_commonmark-conformance.md.

    def test_a_resolving_shortcut_reference_in_the_link_text_disqualifies_the_outer_link(self):
        """`[outer [r5] text](out.md)` with `[r5]:` defined — the reference
        renders ONE link, to the definition's target, and leaves the outer
        `](out.md)` as literal text. WI-0080's scanner deactivated enclosing
        openers only in the inline-destination branch, so it reported `out.md`
        as well: a false positive the regex it replaced never produced."""
        self.write_index(
            CLEAN_INDEX
            + "\n[r5]: gone_ref_defn.md\n"
            + "\n- [outer [r5] text](gone_ref_outer.md) — reference link inside\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_ref_defn.md", findings[0])
        self.assertNotIn("gone_ref_outer.md", " ".join(findings))

    def test_a_reference_definition_placed_after_its_use_still_disqualifies_the_outer_link(self):
        """The architectural claim, measured: CommonMark collects reference
        DEFINITIONS for the whole document before it parses any inline content,
        so the definition may follow its use. A single-pass extractor cannot
        answer this at the moment it reaches the link — check (n) therefore
        reads each index twice, and this is the fixture that says so."""
        self.write_index(
            CLEAN_INDEX
            + "\n- [outer [r6] text](gone_fwd_outer.md) — used before defined\n"
            + "\n[r6]: gone_fwd_defn.md\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_fwd_defn.md", findings[0])
        self.assertNotIn("gone_fwd_outer.md", " ".join(findings))

    def test_an_undefined_label_in_the_link_text_leaves_the_outer_link_intact(self):
        """The counter-fixture that forbids the cheap repair. "Deactivate
        whenever no inline destination follows" would also kill
        `[a [b] c](t.md)`, WI-0080's central case. The ONLY difference between
        the two is whether the inner label resolves against a definition — here
        it does not, and the reference renders the outer link."""
        self.write_index(
            CLEAN_INDEX + "- [outer [nosuchlabel] text](gone_undef_outer.md) — no definition\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_undef_outer.md", findings[0])

    def test_a_resolving_full_reference_in_the_link_text_disqualifies_the_outer_link(self):
        """The full form `[text][r]` resolves the same way as the shortcut and
        deactivates the same openers (reference-measured)."""
        self.write_index(
            CLEAN_INDEX
            + "\n[r7]: gone_full_defn.md\n"
            + "\n- [outer [txt][r7] text](gone_full_outer.md) — full reference inside\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_full_defn.md", findings[0])
        self.assertNotIn("gone_full_outer.md", " ".join(findings))

    def test_a_resolving_collapsed_reference_in_the_link_text_disqualifies_the_outer_link(self):
        """The collapsed form `[r][]` takes its label from the FIRST bracket
        pair, not the empty second one — a separate code path from the full
        form, so it gets its own pin."""
        self.write_index(
            CLEAN_INDEX
            + "\n[r8]: gone_coll_defn.md\n"
            + "\n- [outer [r8][] text](gone_coll_outer.md) — collapsed reference inside\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_coll_defn.md", findings[0])
        self.assertNotIn("gone_coll_outer.md", " ".join(findings))

    def test_a_full_reference_whose_second_label_is_undefined_leaves_the_outer_link_intact(self):
        """Measured, and NOT obvious: in `[r9][nosuch]` the first label IS
        defined, but the reference does not fall back to the shortcut reading —
        the failed full reference renders no link at all, so nothing is
        deactivated and the outer link stands."""
        self.write_index(
            CLEAN_INDEX
            + "\n[r9]: gone_fallback_defn.md\n"
            + "\n- [outer [r9][nosuchlabel] text](gone_fallback_outer.md) — failed full reference\n"
        )

        findings = self.link_findings(self.run_lint().stdout)
        joined = " ".join(findings)

        self.assertEqual(len(findings), 2, findings)
        self.assertIn("gone_fallback_defn.md", joined)
        self.assertIn("gone_fallback_outer.md", joined)

    def test_an_image_reference_in_the_link_text_leaves_the_outer_link_intact(self):
        """WI-0091's rule, restated for the reference form: `![r]` is an IMAGE
        even when it resolves, and an image in the link text does not
        disqualify the enclosing link (reference-measured)."""
        self.write_index(
            CLEAN_INDEX
            + "\n[r10]: gone_imgref_defn.png\n"
            + "\n- [outer ![r10] text](gone_imgref_outer.md) — image reference inside\n"
        )

        findings = self.link_findings(self.run_lint().stdout)
        joined = " ".join(findings)

        self.assertEqual(len(findings), 2, findings)
        self.assertIn("gone_imgref_defn.png", joined)
        self.assertIn("gone_imgref_outer.md", joined)

    def test_reference_labels_match_case_insensitively(self):
        """CommonMark normalises a label by case-folding it, so `[R11]:` defines
        `[r11]`. Pinned on the deactivation path specifically — the corpus
        already covers normalisation on the definition-reporting path."""
        self.write_index(
            CLEAN_INDEX
            + "\n[R11]: gone_case_defn.md\n"
            + "\n- [outer [r11] text](gone_case_outer.md) — case-folded label\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_case_defn.md", findings[0])

    def test_reference_labels_match_with_internal_whitespace_collapsed(self):
        """Second half of label normalisation: internal whitespace runs collapse
        to one space and the ends are trimmed, so `[r 12]:` defines `[ r  12 ]`."""
        self.write_index(
            CLEAN_INDEX
            + "\n[r 12]: gone_ws_defn.md\n"
            + "\n- [outer [ r  12 ] text](gone_ws_outer.md) — whitespace-folded label\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_ws_defn.md", findings[0])

    def test_a_definition_inside_a_fenced_code_block_defines_nothing(self):
        """A reference definition is a BLOCK construct: inside a fence it is
        code, not a definition, and the reference renders the outer link. Pins
        that the label collection runs the same block machine as the extraction
        rather than grepping the file for definition-shaped lines."""
        self.write_index(
            CLEAN_INDEX
            + "\n```\n[r13]: gone_fenced_defn.md\n```\n"
            + "\n- [outer [r13] text](gone_fenced_outer.md) — definition is code\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_fenced_outer.md", findings[0])
        self.assertNotIn("gone_fenced_defn.md", " ".join(findings))

    def test_a_definition_line_that_cannot_interrupt_a_paragraph_defines_nothing(self):
        """A reference definition may not interrupt a paragraph — with an open
        paragraph above it, `[r14]: x.md` is ordinary paragraph text and defines
        nothing, so the outer link stands (reference-measured).

        WI-0096, PO decision 24.08.2026: that line's target is no longer
        reported either. Measured at the reference, `foo\\n[ref]: dead.md`
        renders `<p>foo\\n[ref]: dead.md</p>` — VISIBLE paragraph text, so the
        path is on the page and a reader can see it is dead. That is what
        separates it from WI-0085's standalone definition, which renders as
        NOTHING: there the invisibility is the defect worth reporting, here
        there is no invisibility to report. The rule stayed "report what is
        invisibly dead"; only this shape stopped meeting it."""
        self.write_index(
            CLEAN_INDEX
            + "\nsome prose\n[r14]: gone_interrupt_defn.md\n"
            + "\n- [outer [r14] text](gone_interrupt_outer.md) — not a definition\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_interrupt_outer.md", findings[0])

    def test_a_standalone_unused_definition_is_still_reported(self):
        """The control WI-0096 must not disturb (WI-0085, PO decision
        23.08.2026, re-affirmed 24.08.2026). `[ref]: dead.md` on its own renders
        as the empty string at the reference — the reader never sees the path,
        so a dead one stays invisible, and that invisibility is exactly what
        check (n) exists to report. Same file, same check, opposite verdict to
        the test above: the discriminator is whether the reader can see the
        path, not whether CommonMark renders a link."""
        self.write_index(CLEAN_INDEX + "\n[r24]: gone_unused_defn.md\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_unused_defn.md", findings[0])

    def test_a_definition_shaped_line_inside_a_paragraph_still_yields_its_own_links(self):
        """The paragraph gate must not swallow the LINE. A definition-shaped
        line that cannot interrupt a paragraph is ordinary paragraph text, and
        ordinary paragraph text is scanned for links — so this line falls
        through into the paragraph buffer instead of being consumed and
        skipped. Reference-measured: `dead-i2.md` is the one link rendered."""
        self.write_index(
            CLEAN_INDEX
            + "\nsome prose\n[r25]: gone_fall_defn.md and [x](gone_fall_link.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_fall_link.md", findings[0])

    def test_a_whitespace_only_label_is_not_a_definition(self):
        """Sibling of WI-0096 found in the same review, measured the same way.
        `[   ]: dead.md` renders as `<p>[   ]: dead.md</p>` — the reference
        refuses a label that normalises to nothing (its own parseReference
        rejects an empty normalised label), so the line is VISIBLE prose and
        the path is on the page. Same verdict as WI-0096, and it falls out of
        the same guard: a label that normalises to the empty string is no
        label, so the line is no definition."""
        self.write_index(
            CLEAN_INDEX
            + "\n[   ]: gone_wsdefn.md\n"
            + "\n- [outer [   ] text](gone_wsouter.md) — whitespace-only label\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_wsouter.md", findings[0])

    def test_an_empty_label_is_not_a_definition(self):
        """The degenerate end of the same rule, pinned so the two shapes are
        governed by ONE guard rather than by two accidents. `[]:` was already
        rejected — by a length test, not by the label rule — and this test is
        what keeps it rejected after the length test was folded into the
        normalised-label guard."""
        self.write_index(
            CLEAN_INDEX
            + "\n[]: gone_emptydefn.md\n"
            + "\n- [outer [] text](gone_emptyouter.md) — empty label\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_emptyouter.md", findings[0])

    # --- WI-0099: the same answer whoever measures ---------------------------
    # awk's tolower() case-folds NON-ASCII only under a UTF-8 locale. The test
    # harness starts the script with env={HOME, PATH}, i.e. in the C locale;
    # an interactive `/cleanup` run inherits the user's UTF-8 one. Same script,
    # same input, two answers — so a conformance question about a non-ASCII
    # label used to be decided by WHO ran it (measured, WI-0099).
    #
    # The fix has two halves and both are pinned below: the awk call is pinned
    # to LC_ALL=C so the folding no longer varies, and a label carrying a byte
    # >= 0x80 short-circuits to "resolves", which is the conservative answer —
    # it can only silence a link, never invent one.
    #
    # The second locale is looked up rather than hard-coded: a machine with no
    # UTF-8 locale installed cannot exhibit the divergence at all, and on such
    # a machine both runs are simply the C run. That does not make these tests
    # vacuous — each one also asserts the ABSOLUTE answer the reference gives,
    # and it is the C run that used to get that wrong.
    @staticmethod
    def _a_utf8_locale():
        """A UTF-8 locale name this machine actually has, or None."""
        out = subprocess.run(
            ["locale", "-a"], capture_output=True, text=True,
        ).stdout.splitlines()
        for preferred in ("en_US.UTF-8", "C.UTF-8"):
            if preferred in out:
                return preferred
        for name in out:
            if name.lower().endswith(("utf-8", "utf8")):
                return name
        return None

    def test_a_resolving_non_ascii_label_answers_the_same_in_every_locale(self):
        """`[ÄÖ]:` defined, `[äö]` used inside a link text. The reference
        renders the inner reference link and therefore NO outer link, so the
        outer target must not be reported. Before the fix the C-locale run
        reported it (tolower left `ÄÖ` alone, the lookup missed) while a UTF-8
        run did not — the divergence WI-0099 records. Both halves of the fix
        are needed here: the LC_ALL=C pin alone would have frozen the false
        positive, the ASCII short-circuit is what removes it."""
        body = (
            CLEAN_INDEX
            + "\n[ÄÖ]: https://example.com/ao\n"
            + "\n- [outer [äö] text](gone_locale_outer.md) — non-ASCII label\n"
        )
        self.write_index(body)

        c_findings = self.link_findings(self.run_lint(LC_ALL="C").stdout)
        utf8 = self._a_utf8_locale()
        utf8_findings = self.link_findings(
            self.run_lint(**({"LC_ALL": utf8} if utf8 else {})).stdout
        )

        self.assertEqual(
            c_findings, utf8_findings,
            f"same script, same input, two answers (LC_ALL=C vs {utf8!r}) — "
            f"the conformance verdict still depends on who measures",
        )
        self.assertEqual(c_findings, [], c_findings)

    def test_an_undefined_non_ascii_label_silences_the_enclosing_link(self):
        """The false negative the ASCII short-circuit knowingly buys, pinned so
        it is a counted cost and not a surprise (WI-0099, PO decision
        24.08.2026). `[äö]` with no definition anywhere: the reference renders
        the OUTER link, check (n) reports nothing. Direction: false NEGATIVE,
        and — this is the point of the trade — it is now a property of the
        CODE (the label carries a byte >= 0x80, so the link is not reported)
        rather than of the locale the caller happened to have."""
        self.write_index(
            CLEAN_INDEX
            + "\n- [outer [äö] text](gone_locale_fn.md) — undefined non-ASCII label\n"
            + "- [outer [nosuch] text](gone_locale_ctl.md) — undefined ASCII label\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn(
            "gone_locale_ctl.md", findings[0],
            "the ASCII control vanished too — this fixture would then also "
            "pass for a scanner that reported nothing at all",
        )

    def test_a_non_ascii_definition_still_reports_its_own_target(self):
        """The control the short-circuit must not touch. Narrowing the USAGE
        side to ASCII says nothing about the DEFINITION side: `[ÄÖ]: dead.md`
        still points at a file, and check (n)'s contract is to check that the
        file exists. Reference-measured: it renders a link here, so both
        oracles agree."""
        self.write_index(
            CLEAN_INDEX + "\n[ÄÖ]: gone_locale_defn.md\n" + "\n- [äö]\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_locale_defn.md", findings[0])

    def test_an_invalid_utf8_byte_does_not_stop_the_scan_under_a_utf8_locale(self):
        """The second, larger thing the LC_ALL=C pin buys — found while
        measuring WI-0099, not asked for. /usr/bin/awk (20200816) ABORTS with
        `towc: multibyte conversion failure` on a byte that is not valid UTF-8
        when the locale says UTF-8. The whole index then goes unscanned and the
        run still exits 0-or-1: every dead link in that file silently
        disappears. Under LC_ALL=C awk is byte-oriented and cannot hit it."""
        raw = (
            CLEAN_INDEX
            + "\nstray \udcff byte and [x](gone_badbyte.md) — invalid UTF-8 above\n"
        ).encode("utf-8", "surrogateescape")
        (self.memory_dir / "MEMORY.md").write_bytes(raw)

        utf8 = self._a_utf8_locale()
        # Run it here rather than through run_lint(): the awk abort message
        # echoes the offending byte to stderr, and decoding that as strict
        # UTF-8 raises inside subprocess before any assertion is reached — an
        # ERROR that hides the finding this test is about.
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), str(self.project_dir)],
            capture_output=True, text=True, errors="replace",
            env=self.lint_env(**({"LC_ALL": utf8} if utf8 else {})),
        )
        self._assert_script_actually_ran(result)
        findings = self.link_findings(result.stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_badbyte.md", findings[0])

    def test_a_backslash_escaped_bracket_in_a_definition_label_is_still_a_definition(self):
        """Sibling of WI-0080's label fix, two functions further along: the
        definition line's own label grammar excluded `]` outright, so
        `[a\\]b]: t.md` was not recognised as a definition at all — its target
        went unchecked and the label went undefined. Reference-measured: it is
        one definition with label `a]b`, and using it deactivates an enclosing
        link."""
        self.write_index(
            CLEAN_INDEX
            + "\n[a\\]b]: gone_escdefn.md\n"
            + "\n- [outer [a\\]b] text](gone_escdefn_outer.md) — escaped bracket label\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_escdefn.md", findings[0])
        self.assertNotIn("gone_escdefn_outer.md", " ".join(findings))

    def test_a_resolved_reference_link_consumes_a_parenthesis_that_follows_it(self):
        """`[txt][r15](paren.md)` — the reference consumes `[txt][r15]` as the
        link and leaves `(paren.md)` as literal text. A scanner that only
        deactivates, without consuming the span, re-reads `[r15](paren.md)` as
        an inline link and reports a target nobody linked."""
        self.write_index(
            CLEAN_INDEX
            + "\n[r15]: gone_consume_defn.md\n"
            + "\n- [txt][r15](gone_consume_paren.md) — the paren is literal text\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_consume_defn.md", findings[0])
        self.assertNotIn("gone_consume_paren.md", " ".join(findings))

    def test_a_reference_disqualified_outer_link_does_not_swallow_a_later_link(self):
        """The deactivation ends with the outer opener, not with the line — an
        independent link after the construct is still found (reference-measured,
        same guarantee WI-0080 pinned for the inline-in-inline case)."""
        self.write_index(
            CLEAN_INDEX
            + "\n[r16]: gone_later_defn.md\n"
            + "\n- [outer [r16] text](gone_later_outer.md) and [d](gone_later_e.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)
        joined = " ".join(findings)

        self.assertEqual(len(findings), 2, findings)
        self.assertIn("gone_later_defn.md", joined)
        self.assertIn("gone_later_e.md", joined)
        self.assertNotIn("gone_later_outer.md", joined)

    def test_a_reference_disqualified_outer_link_whose_targets_exist_stays_silent(self):
        """Live control for the whole reference-deactivation group: the same
        shapes with targets on disk must report nothing. Without it every
        assertion above would also hold for a scanner that reports every
        bracket construct as dead."""
        (self.memory_dir / "live_ref_defn.md").write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        (self.memory_dir / "live_ref_outer.md").write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        self.write_index(
            CLEAN_INDEX
            + "\n[r17]: live_ref_defn.md\n"
            + "\n- [outer [r17] text](live_ref_outer.md) — live\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    # --- A label the paragraph resolver REWRITES still has to match (WI-0098) ---
    # The two sides of the reference-link mechanism read their label from
    # different text: the definition line reads the RAW record, the usage side
    # reads the paragraph after protect_link_destinations() and
    # resolve_paragraph() have run. resolve_paragraph() DISCARDS a code span
    # and replaces a closed inline comment with the boundary sentinel, so the
    # two keyed refmap on different strings and the deactivation never fired.
    # Both shapes below were measured against the reference (commonmark 0.9.2,
    # HTML oracle) and against 4f2ffa7, the commit before the scanner rewrite:
    # both say the outer link is NOT a link. This was a regression, not a
    # pre-existing gap -- 4f2ffa7 was accidentally right, because its
    # `[^][]*` label class could not match a label carrying brackets at all.

    def test_a_code_span_in_a_resolving_shortcut_label_still_disqualifies_the_outer_link(self):
        """`[`a`]` with ``[`a`]:`` defined renders one link, to the definition's
        target; the outer `](out.md)` is literal text. The code span is stripped
        out of the paragraph before the scanner sees the label, so the label the
        scanner reads is empty while the label the definition registered is not
        -- and nothing matched."""
        self.write_index(
            CLEAN_INDEX
            + "\n[`r20`]: gone_cspan_defn.md\n"
            + "\n- [outer [`r20`] text](gone_cspan_outer.md) — code-span label\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_cspan_defn.md", findings[0])
        self.assertNotIn("gone_cspan_outer.md", " ".join(findings))

    def test_an_inline_comment_in_a_resolving_shortcut_label_still_disqualifies_the_outer_link(self):
        """The same defect through the other rewriting construct, measured
        rather than assumed to be the same mechanism: a CLOSED inline comment is
        replaced by the boundary sentinel, so the label the scanner reads is one
        control byte and the label the definition registered is `<!--x-->`."""
        self.write_index(
            CLEAN_INDEX
            + "\n[<!--x-->]: gone_cmt_defn.md\n"
            + "\n- [outer [<!--x-->] text](gone_cmt_outer.md) — inline-comment label\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_cmt_defn.md", findings[0])
        self.assertNotIn("gone_cmt_outer.md", " ".join(findings))

    def test_a_code_span_label_with_no_definition_leaves_the_outer_link_intact(self):
        """The counter-fixture that forbids the blunt repair. "A label the
        resolver rewrote deactivates the enclosing openers" would also kill
        this, and the reference renders the outer link here -- the difference is
        only whether a definition exists, exactly as for a plain label. Green
        before the fix and after it; it is the fixture that must NOT move."""
        self.write_index(
            CLEAN_INDEX + "- [outer [`nosuch`] text](gone_cspan_undef.md) — no definition\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_cspan_undef.md", findings[0])

    def test_a_code_span_labelled_reference_whose_targets_exist_stays_silent(self):
        """Live control for the pair above: the same shapes pointing at real
        files report nothing, so neither assertion is satisfied by a scanner
        that has started reporting every bracket construct."""
        (self.memory_dir / "live_cspan_defn.md").write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        (self.memory_dir / "live_cspan_outer.md").write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        self.write_index(
            CLEAN_INDEX
            + "\n[`r21`]: live_cspan_defn.md\n"
            + "\n- [outer [`r21`] text](live_cspan_outer.md) — live\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_label_emptied_by_the_resolver_matches_any_other_emptied_label(self):
        """The false negative WI-0098's fix knowingly buys, pinned so it is a
        counted cost and not a surprise. The definition label is registered in
        the shape the scanner will see it in, and two DIFFERENT raw labels can
        resolve to the same shape -- here both to the empty one. The reference
        renders the outer link (``[`r22`]`` and ``[`other`]`` are different
        labels); check (n) treats the inner as resolving and drops it.
        Direction: false NEGATIVE, the one the PO decision of 24.08.2026 accepts
        in trade for the false positive above."""
        self.write_index(
            CLEAN_INDEX
            + "\n[`r22`]: gone_collide_defn.md\n"
            + "\n- [outer [`other`] text](gone_collide_outer.md) — different label, same resolved shape\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_collide_defn.md", findings[0])
        self.assertNotIn("gone_collide_outer.md", " ".join(findings))

    # --- Nothing but refmap crosses the pass boundary (WI-0093, S-3) ---------
    # Reading the index twice means pass 2 must start from BEGIN state. Each
    # test below leaves ONE block construct open at end of pass 1 and puts a
    # dead link BEFORE it: if that construct's flag leaks, pass 2 opens inside
    # it and scans nothing at all — and an assertion that only demanded "no
    # finding from inside the construct" would be satisfied by exactly that.
    # The dead link in front is what makes the assertion able to fail. Same
    # shape as the block-comment sentinel test above, which is the one
    # construct of the five that already had it.
    #
    # The indexes below are minimal on purpose, and the missing blank line
    # between the heading and the paragraph is load-bearing — measured, not
    # stylistic. A leaked `in_fence` arrives in pass 2 with `fence_char` and
    # `fence_len` already reset to "" and 0, and the closer test built from
    # those degenerates into a blank-line match, so the leaked fence closes
    # itself at the FIRST blank line of the second pass. A leaked
    # `in_html_block6` closes at the first blank line by its own rule. Anything
    # after that blank line is scanned normally and proves nothing; only a link
    # before it can tell the two states apart.
    _PASS_LEAK_INDEX = "# Memory Index\nA paragraph pointing at [Dead]({dead}).\n\n{opener}\n- [Example]({inner})\n"

    def test_an_unclosed_fence_does_not_leak_into_the_second_pass(self):
        """`in_fence` at the pass boundary. The fence opens in pass 1 and never
        closes, so it is still open when the file is handed over a second
        time."""
        self.write_index(self._PASS_LEAK_INDEX.format(
            dead="dead_pass_fence_before.md", opener="```", inner="dead_pass_fence_after.md",
        ))

        result = self.run_lint()

        findings = self.link_findings(result.stdout)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_pass_fence_before.md", findings[0])
        warnings = self.findings(result.stdout, "Warnings")
        self.assertTrue(any("never closed" in w for w in warnings), warnings)

    def test_an_unclosed_html_block_type_1_does_not_leak_into_the_second_pass(self):
        """`in_html_block1`. A raw-text element (`<script>`) closes only on its
        own closing tag, so an unclosed one runs to end of document — and,
        without the reset, past it."""
        self.write_index(self._PASS_LEAK_INDEX.format(
            dead="dead_pass_b1_before.md", opener="<script>", inner="dead_pass_b1_after.md",
        ))

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_pass_b1_before.md", findings[0])

    def test_an_unclosed_html_block_type_6_does_not_leak_into_the_second_pass(self):
        """`in_html_block6`. A type-6 block ends at the next BLANK line, so a
        file that ends without one leaves the flag set at the pass boundary."""
        self.write_index(self._PASS_LEAK_INDEX.format(
            dead="dead_pass_b6_before.md", opener="<div>", inner="dead_pass_b6_after.md",
        ))

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("dead_pass_b6_before.md", findings[0])

    def test_a_closed_construct_before_the_pass_boundary_scans_both_sides(self):
        """The control the three tests above need: with the construct CLOSED,
        the link in front of it is still the only finding and the run is
        otherwise identical — so "exactly one finding" above is a statement
        about the leak, not about this index shape being unscannable."""
        self.write_index(
            "# Memory Index\nA paragraph pointing at [Dead](dead_pass_closed_before.md).\n"
            "\n```\n- [Example](dead_pass_closed_inner.md)\n```\n"
            "\nAnd [After](dead_pass_closed_after.md).\n"
        )

        findings = self.link_findings(self.run_lint().stdout)
        joined = " ".join(findings)

        self.assertEqual(len(findings), 2, findings)
        self.assertIn("dead_pass_closed_before.md", joined)
        self.assertIn("dead_pass_closed_after.md", joined)
        self.assertNotIn("dead_pass_closed_inner.md", joined)

    def test_a_named_entity_in_the_destination_is_reported_as_info_not_a_dead_link(self):
        """`&num;` is a NAMED entity — deliberately left undecoded (WI-0081):
        decoding the full ~2000-entry CommonMark named-entity table is
        disproportionate for a construct that occurs zero times in the field.
        WI-0081 (remainder): a destination that cannot be resolved must not be
        CLAIMED dead either — the reference resolves `dead&num;3.md` to
        `dead#3.md`, a different filename check (n) never actually tested. A
        named-entity destination is filed as info, naming the raw target and
        the reason, and is absent from both Errors and Warnings."""
        self.write_index(CLEAN_INDEX + "- [Named](gone_ent_named&num;3.md) — dead\n")

        result = self.run_lint()

        self.assertEqual(self.link_findings(result.stdout), [])
        infos = self.findings(result.stdout, "Info")
        self.assertEqual(len(infos), 1, infos)
        self.assertIn("gone_ent_named&num;3.md", infos[0])
        self.assertIn("entity", infos[0].lower())

    def test_a_named_entity_whose_decoded_target_actually_exists_is_still_info_not_silence(self):
        """The other half of the same claim: check (n) cannot tell "cannot
        resolve" apart from "resolves to a live file" without decoding the
        entity — so it must not silently treat this as fine either. Same info
        finding regardless of whether the decoded target exists on disk."""
        (self.memory_dir / "gone_ent_named_live#3.md").write_text(
            TIER2_TOPIC_TEXT, encoding="utf-8"
        )
        self.write_index(CLEAN_INDEX + "- [Named](gone_ent_named_live&num;3.md) — live once decoded\n")

        result = self.run_lint()

        self.assertEqual(self.link_findings(result.stdout), [])
        infos = self.findings(result.stdout, "Info")
        self.assertEqual(len(infos), 1, infos)
        self.assertIn("gone_ent_named_live&num;3.md", infos[0])

    def test_the_index_is_checked_even_when_no_content_files_are_scanned(self):
        """An index whose entries are all dead, with no OTHER memory file around it,
        must still fire — the dead-link check does not depend on there being real
        content files to validate.

        Before WI-0108, docs/memory/MEMORY.md itself was excluded from the FILES
        array by name, so this scenario reported "Files scanned: 0" — the index
        was invisible to the file loop entirely. Since the exclusion is gone, the
        index is now itself one of the scanned files (still with no frontmatter
        here, so check (a) skips it silently) — "Files scanned: 1", not 0. The
        orphan check (g) is gated on FILES_TOTAL because it iterates the files;
        this dead-link check iterates the index directly and never depended on
        that gate — this test now proves that by observing the gate condition is
        actually true (FILES_TOTAL == 1) rather than by forcing it to zero.
        """
        bare = Path(tempfile.mkdtemp(prefix="ccpr-memory-lint-bare-"))
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        bare_memory = bare / "docs" / "memory"
        bare_memory.mkdir(parents=True)
        (bare_memory / "MEMORY.md").write_text(
            "# Memory Index\n\n- [Ghost](project_deleted.md) — dead link\n", encoding="utf-8"
        )

        result = self.run_lint(project_dir=bare)

        self.assertIn("**Files scanned:** 1", result.stdout)
        findings = self.link_findings(result.stdout)
        self.assertEqual(len(findings), 1, result.stdout)
        self.assertIn("project_deleted.md", findings[0])

    def test_two_links_on_one_line_are_both_checked(self):
        self.write_index(CLEAN_INDEX + "- see [A](gone_a.md) and [B](gone_b.md)\n")

        self.assertEqual(len(self.link_findings(self.run_lint().stdout)), 2)

    # --- Tier-2 persona indexes are in scope too (WI-0040) -------------------------
    # Check (n) used to look only at the Tier-1 index (docs/memory/MEMORY.md).
    # A persona index (docs/memory/{agent}/MEMORY.md) carries far more links — deep
    # anchors into topic files, one per review/implementation round — and nothing
    # validated those. This is the floor shape only: it catches a missing FILE, not
    # a wrong anchor into a file that does exist (see the dedicated test below).

    def test_dead_link_in_a_persona_index_is_reported(self):
        self.write_persona_index(TIER2_INDEX_TEXT + "- [Ghost](missing.md) — dead link\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("missing.md", findings[0])
        self.assertIn("senior-developer/MEMORY.md", findings[0])

    def test_a_live_link_in_a_persona_index_is_not_reported(self):
        """Also pins that a persona-index target resolves relative to the persona
        index's OWN directory, not the Tier-1 memory dir: patterns.md only exists
        inside senior-developer/, not at docs/memory/ root."""
        self.write_persona_index(TIER2_INDEX_TEXT)  # unchanged fixture: [patterns.md](patterns.md), live

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_a_wrong_anchor_into_an_existing_persona_file_is_not_reported(self):
        """Acceptance (a), the floor: a missing FILE is caught, a wrong anchor into
        a file that does exist is not — anchor resolution needs heading-to-slug
        modelling and is deliberately out of scope for this fix (WI-0040)."""
        self.write_persona_index(
            TIER2_INDEX_TEXT + "- [Ghost](patterns.md#section-that-does-not-exist) — live file, dead anchor\n"
        )

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

    def test_every_persona_index_is_scanned_not_only_the_first(self):
        """A second persona directory, with its own dead link, must be found too —
        and named by its own path, not folded into another index's finding."""
        other_dir = self.memory_dir / "code-reviewer"
        other_dir.mkdir()
        (other_dir / "MEMORY.md").write_text(
            "# Code-Reviewer Memory\n\n- [Ghost](nonexistent_topic.md) — dead\n",
            encoding="utf-8",
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("code-reviewer/MEMORY.md", findings[0])
        self.assertIn("nonexistent_topic.md", findings[0])

    # --- The severity knob: the only tests that may notice the default ------------
    # Everything above asserts extraction and is blind to severity. All five tests
    # below set the knob deliberately — the pin too, since its second half drives
    # the escape hatch — but only the pin asserts the SHIPPED value. Changing the
    # default must therefore turn exactly one of them red, which is measured rather
    # than assumed: see the module docstring.

    def test_the_shipped_default_severity_is_err_and_warn_remains_reachable(self):
        """The default with no override: a dead link is an error, exit 2.

        This is the assertion whose absence let a default flip pass silently, and
        it keeps that job across the flip: any future change to the shipped
        default stays a deliberate red test — one failure, here, with the reason
        written on it — instead of a behaviour change that only shows up as an
        exit code somewhere in a report.

        The default is `err` since 24.08.2026 (WI-0005, ADR-0001), promoted under
        the criterion the PO set on 23.08.2026: no known FALSE-POSITIVE
        divergence. That criterion replaced "a round that produces no new items",
        which two rounds against untouched ground had shown to be unreachable.
        It supersedes the revert of 19.08.2026, which read an incomplete
        extraction as a reason to stay at `warn`. Only a false positive rejects
        previously accepted content, so only a false positive meets ADR-0001's
        threshold; the false negatives that remain reject nothing. The comment
        above MEMORY_INDEX_LINK_SEVERITY's assignment in memory-lint.sh carries
        the full criterion including its named caveat (WI-0100).

        The second half of this test is the escape hatch, and it belongs HERE
        rather than only in its own test: the promotion is defensible because a
        run it catches off guard can be put back the way it was, and that
        promise has to be measured next to the default it qualifies, not
        asserted somewhere else.
        """
        self.assertNotIn(SEVERITY_VAR, self.lint_env(), "the base env must not preset the knob")
        self.write_index(CLEAN_INDEX + "- [Ghost](project_deleted.md) — dead link\n")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertEqual(len(errors), 1, result.stdout)
        self.assertIn("project_deleted.md", errors[0])
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        self.assertEqual(result.returncode, 2, result.stdout)

        opted_out = self.run_lint(**{SEVERITY_VAR: "warn"})

        opted_out_warnings = self.findings(opted_out.stdout, "Warnings")
        self.assertEqual(len(opted_out_warnings), 1, opted_out.stdout)
        self.assertIn("project_deleted.md", opted_out_warnings[0])
        self.assertEqual(self.findings(opted_out.stdout, "Errors"), [], opted_out.stdout)
        self.assertEqual(opted_out.returncode, 1, opted_out.stdout)

    def test_severity_err_reports_a_dead_link_as_an_error(self):
        """Pins the `err` half of the knob so the default value is a one-line change."""
        self.write_index(CLEAN_INDEX + "- [Ghost](project_deleted.md) — dead link\n")

        result = self.run_lint(**{SEVERITY_VAR: "err"})

        self.assertEqual(len(self.findings(result.stdout, "Errors")), 1, result.stdout)
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_severity_warn_downgrades_a_dead_link_to_a_warning(self):
        """Pins the `warn` half of the knob — same finding, warning severity, exit 1."""
        self.write_index(CLEAN_INDEX + "- [Ghost](project_deleted.md) — dead link\n")

        result = self.run_lint(**{SEVERITY_VAR: "warn"})

        warnings = self.findings(result.stdout, "Warnings")
        self.assertEqual(len(warnings), 1, result.stdout)
        self.assertIn("project_deleted.md", warnings[0])
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_misspelled_severity_fails_fast_instead_of_killing_the_run(self):
        """A typo in the knob must not be executed as a command.

        Before the fix the value was expanded as a command name: `eror` produced
        `command not found`, exit 127 and no report at all — indistinguishable from
        a findings result for a caller that only checks "non-zero".
        """
        self.write_index(CLEAN_INDEX + "- [Ghost](project_deleted.md) — dead link\n")

        result = self.run_lint(**{SEVERITY_VAR: "eror"})

        self.assertEqual(result.returncode, 3, (result.stdout, result.stderr))
        self.assertIn(SEVERITY_VAR, result.stderr)
        self.assertIn("eror", result.stderr)
        self.assertIn("err", result.stderr)
        self.assertIn("warn", result.stderr)
        self.assertNotIn("command not found", result.stderr)

    def test_an_empty_severity_is_a_configuration_error_not_the_strict_default(self):
        """`MEMORY_INDEX_LINK_SEVERITY=` must fail loudly, not fall through to `err`.

        Emptying a variable is how a caller reaches for "turn this knob off", and
        it is the most likely wrong grip on a knob that has no off position. Under
        `${VAR:-err}` the empty value took the DEFAULT branch, so the attempt to
        opt out landed on the strict side of the very promotion it was trying to
        escape — silently, exit 2, indistinguishable from a real findings result.
        An empty value is not a severity, so it belongs where every other value
        that is not a severity already goes: the up-front validation, exit 3, with
        the reason on stderr and no report pretending a run happened.
        """
        self.write_index(CLEAN_INDEX + "- [Ghost](project_deleted.md) — dead link\n")

        result = self.run_lint(**{SEVERITY_VAR: ""})

        self.assertEqual(result.returncode, 3, (result.stdout, result.stderr))
        self.assertIn(SEVERITY_VAR, result.stderr)
        self.assertIn("err", result.stderr)
        self.assertIn("warn", result.stderr)
        self.assertEqual(result.stdout, "", result.stdout)

    def test_a_severity_value_is_never_executed_as_a_command(self):
        """The knob is dispatched by value, not expanded into command position."""
        canary = self.project_dir / "canary.txt"
        self.write_index(CLEAN_INDEX + "- [Ghost](project_deleted.md) — dead link\n")

        result = self.run_lint(**{SEVERITY_VAR: f"touch {canary}"})

        self.assertFalse(canary.exists(), result.stderr)
        self.assertEqual(result.returncode, 3, (result.stdout, result.stderr))


    # --- block boundaries the paragraph buffer used to miss (WI-0086, WI-0082) ---
    # All three shapes below share one root cause: check (n) buffers a paragraph
    # across physical lines so a code span may straddle them, and it flushes that
    # buffer only at a boundary it recognises. A boundary CommonMark honours but
    # the buffer does not merges two blocks into one, letting two backticks that
    # each belong to a block of their own pair across the merge and swallow a real
    # link. Direction of every defect here: false negative.

    def test_a_cr_terminated_blank_line_ends_the_paragraph(self):
        """WI-0086: on a CRLF file awk splits records on `\n` and hands the
        blank line over as a bare `\r`, which `$0 ~ /^[ \t]*$/` does not
        match. CommonMark counts `\r\n` as a line ending, so both paragraphs
        are separate blocks and each stray backtick stays unpaired in its own.
        """
        self.write_index(
            "# Memory Index\r\n"
            "\r\n"
            "`stray one [a](project_crlf_one.md)\r\n"
            "\r\n"
            "`stray two [b](project_crlf_two.md)\r\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_crlf_one.md" in f for f in findings), findings)
        self.assertTrue(any("project_crlf_two.md" in f for f in findings), findings)

    def test_a_cr_terminated_atx_heading_still_ends_the_paragraph(self):
        """The CR strip is not a special case for the blank-line test: every
        `$`-anchored boundary regex in the awk block breaks the same way on a
        CR. The heading here carries NO text on purpose — `## Heading\\r`
        already matches via the regex's `[ \t]` branch and would prove
        nothing; an empty ATX heading (`<h2></h2>` at the reference) can only
        match via the `$` branch, which the carriage return blocks.
        """
        self.write_index(
            "# Memory Index\r\n"
            "\r\n"
            "`stray one [a](project_crlf_atx.md)\r\n"
            "##\r\n"
            "`stray two [b](project_crlf_atx2.md)\r\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_crlf_atx.md" in f for f in findings), findings)
        self.assertTrue(any("project_crlf_atx2.md" in f for f in findings), findings)

    def test_a_cr_terminated_reference_definition_with_a_title_is_seen(self):
        """The reference-definition branch reads its own `raw_rest` substring
        out of `$0`, and `reference_definition_tail()` validates the optional
        quoted title against end-of-line. With the carriage return still
        attached the tail never validated, the whole definition fell through as
        ordinary prose, and its destination was never checked at all — the same
        CR cause, in the one branch that does not test `$0` directly.
        """
        self.write_index(
            "# Memory Index\r\n"
            "\r\n"
            "[ref]: project_crlf_refdef.md \"a title\"\r\n"
            "\r\n"
            "see [x][ref]\r\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_crlf_refdef.md" in f for f in findings), findings)

    def test_a_cr_terminated_fence_closes_the_fence(self):
        """A fence close is `$`-anchored too — with the CR still attached the
        closing line never matches and the fence swallows the rest of the file,
        which the run reports as an unclosed-fence warning.
        """
        self.write_index(
            "# Memory Index\r\n"
            "\r\n"
            "```\r\n"
            "[inside](project_crlf_fenced.md)\r\n"
            "```\r\n"
            "\r\n"
            "- [Real](project_crlf_after.md) — after the fence\r\n"
        )

        result = self.run_lint()
        findings = self.link_findings(result.stdout)

        # The sentinel warning verbatim, and FIRST: it is the root symptom, and
        # a later assertion firing before it would leave this one unproven.
        # An earlier draft asserted the absence of the word "unclosed", which
        # the script emits nowhere — it occurs only in source comments, so that
        # assertion could not go red for the reason it claimed.
        self.assertNotIn(
            "opens a code fence that is never closed", result.stdout
        )
        self.assertFalse(any("project_crlf_fenced.md" in f for f in findings), findings)
        self.assertTrue(any("project_crlf_after.md" in f for f in findings), findings)
        # WI-0128: same fact as the assertTrue above, phrased directly against
        # result.stdout — link_findings() already proves it, but the wrapper is
        # what leaves a crashed-with-empty-stdout run producing an empty
        # findings list and this same assertTrue vacuously true.
        self.assertIn("project_crlf_after.md", result.stdout)


    # --- thematic break and setext underline as boundaries (WI-0082) ----------
    # Every expectation below was measured against the pinned reference parser
    # (commonmark 0.9.2), not derived from the spec text — see
    # docs/memory/reference_commonmark-conformance.md.

    def test_a_thematic_break_ends_the_paragraph(self):
        """`***` is its own block (`<hr />`), so it interrupts the paragraph
        and the two stray backticks never meet."""
        self.write_index(
            "# Memory Index\n\n"
            "`stray one [a](project_tb_a.md)\n"
            "***\n"
            "`stray two [b](project_tb_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_tb_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_tb_b.md" in f for f in findings), findings)

    def test_a_setext_underline_ends_the_paragraph(self):
        """`===` under an open paragraph closes it as a setext heading
        (`<h1>` at the reference), so both links are real and separate."""
        self.write_index(
            "# Memory Index\n\n"
            "`stray one [a](project_setext_a.md)\n"
            "===\n"
            "`stray two [b](project_setext_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_setext_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_setext_b.md" in f for f in findings), findings)

    def test_a_thematic_break_outranks_the_list_marker_it_also_matches(self):
        """`- - -` satisfies the list-marker pattern AND the thematic-break
        pattern; CommonMark gives the break precedence (`<hr />`, measured).

        The discriminating consequence is the line AFTER it: a thematic break
        leaves the paragraph buffer empty, so a following 4-space-indented line
        is an indented code block and its link is not a link. Handled as a list
        marker instead, the `- - -` line itself gets buffered, the indented-code
        branch's `pbuf_n == 0` gate no longer holds, and the buried link is
        wrongly reported.
        """
        self.write_index(
            "# Memory Index\n\n"
            "- - -\n"
            "    [buried](project_prec_code.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertFalse(any("project_prec_code.md" in f for f in findings), findings)

    def test_a_setext_underline_does_not_close_an_open_list_item(self):
        """Measured, not assumed: `===` under a list item is NOT an underline —
        the reference keeps it as lazy continuation inside the `<li>`, so the
        backticks around it DO pair and only the trailing link is real.

        Without this guard the new setext boundary would flush the list item's
        buffer and report a link the reference never renders — a false positive
        traded for the false negative the boundary fixes.
        """
        self.write_index(
            "# Memory Index\n\n"
            "- `item [a](project_li_a.md)\n"
            "===\n"
            "closer` [b](project_li_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertFalse(any("project_li_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_li_b.md" in f for f in findings), findings)

    def test_a_setext_underline_does_not_close_an_open_block_quote(self):
        """Same shape as the list-item guard, one container further: the
        reference keeps `===` inside the blockquote paragraph (measured), so
        only the trailing link is real here too.
        """
        self.write_index(
            "# Memory Index\n\n"
            "> `q [a](project_bq_a.md)\n"
            "===\n"
            "closer` [b](project_bq_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertFalse(any("project_bq_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_bq_b.md" in f for f in findings), findings)

    def test_an_equals_line_with_no_open_paragraph_is_ordinary_content(self):
        """A setext underline needs a paragraph to underline. With the buffer
        empty the reference renders `===` as plain paragraph text (measured),
        so the line must be BUFFERED, not treated as a boundary — otherwise the
        stray backtick below it loses the content it opens against.
        """
        self.write_index(
            "# Memory Index\n\n"
            "===\n"
            "`stray [a](project_noopen_a.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_noopen_a.md" in f for f in findings), findings)

    def test_a_setext_underline_does_not_close_a_block_quote_opened_mid_paragraph(self):
        """The container guard has to survive a block quote that INTERRUPTS an
        open paragraph instead of opening the buffer itself — a `>` line may do
        that in CommonMark, so "what opened the buffer" is not what decides.

        Measured at the reference: `foo` / `> \u0060q …` / `===` / `closer\u0060 …`
        renders `<p>foo</p>` plus a blockquote holding
        `<code>q [a](…) === closer</code>`, i.e. the underline stays lazy
        continuation inside the quote exactly as it does when the quote opens
        the buffer, and only the trailing link is real.
        """
        self.write_index(
            "# Memory Index\n\n"
            "foo\n"
            "> `q [a](project_bqmid_a.md)\n"
            "===\n"
            "closer` [b](project_bqmid_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertFalse(any("project_bqmid_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_bqmid_b.md" in f for f in findings), findings)

    def test_a_thematic_break_ends_an_open_list_item(self):
        """The thematic-break branch must stay UNGATED by pbuf_para, and this
        is the shape that says so: a `---` line is NOT lazy continuation inside
        a list item the way `===` is.

        Measured at the reference: `- \u0060item …` / `---` / `closer\u0060 …`
        renders `<ul><li>\u0060item <a …>a</a></li></ul>`, `<hr />` and a separate
        paragraph — the item's stray backtick never reaches the line below, so
        BOTH links are real. Gating this branch the way the setext branch is
        gated would keep the buffer running, pair the two backticks and swallow
        the first link.
        """
        self.write_index(
            "# Memory Index\n\n"
            "- `item [a](project_tbli_a.md)\n"
            "---\n"
            "closer` [b](project_tbli_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_tbli_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_tbli_b.md" in f for f in findings), findings)

    # --- a block quote interrupting a paragraph (WI-0089) ---------------------
    # WI-0082 already handles the other direction — a `>` line OPENING the
    # buffer — via the pbuf_para flag at the setext branch. It never flushed
    # the paragraph buffer on the interrupt itself: the quote's content was
    # still appended into the SAME buffer as the paragraph above it. A code
    # span straddling that join can then pair across the two blocks and hide
    # a real link, exactly the way an unrecognised boundary always does in
    # this extractor. Measured at the reference (commonmark 0.9.2), not
    # derived from the spec text.

    def test_a_block_quote_interrupting_a_paragraph_does_not_hide_a_link_in_a_straddling_code_span(self):
        """Measured at the reference: `foo `x` / `> bar [a](…) y` [b](…)`
        renders `<p>foo `x</p>` (the backtick never pairs — the quote ends
        the paragraph) plus a blockquote paragraph `bar <a>a</a> y` <a>b</a>`
        (the backtick there is unpaired too). Both links are real. Before the
        fix the two lines share one buffer, the two backticks pair across the
        join, and the first link is swallowed as code.
        """
        self.write_index(
            "# Memory Index\n\n"
            "foo `x\n"
            "> bar [a](project_bqint_a.md) y` [b](project_bqint_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_bqint_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_bqint_b.md" in f for f in findings), findings)

    def test_a_block_quote_interrupting_a_paragraph_without_a_straddling_span_still_finds_both_links(self):
        """Control for the fixture above: without a code span crossing the
        boundary, the merged buffer already found both links before this fix
        — this must stay true after it. Measured at the reference: `foo` /
        `> bar [a](…)` renders `<p>foo</p>` plus a blockquote holding a real
        link.
        """
        self.write_index(
            "# Memory Index\n\n"
            "foo\n"
            "> bar [a](project_bqint_ctrl.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_bqint_ctrl.md" in f for f in findings), findings)

    # --- a block quote interrupting a LIST ITEM's paragraph (WI-0089 gap) ---
    # WI-0089 flushed the buffer when a `>` line interrupts an ordinary,
    # not-yet-quoted paragraph (pbuf_n > 0 && pbuf_para). A list item's own
    # paragraph never sets pbuf_para at all — the list-item branch buffers
    # content without touching the flag, by design, so the WI-0082 setext
    # guard does not fire inside a list item. That leaves the interrupt guard
    # unable to tell "continuing an open quote" (pbuf_para == 0, must NOT
    # flush) apart from "a list item's paragraph is open" (pbuf_para == 0
    # too, but MUST flush) — both read the same flag value. The list-item
    # case falls through unflushed, the quote line joins the list item's
    # buffer, and a code span straddling that join hides a real link.
    # Measured at the reference (commonmark 0.9.2): a block quote interrupts
    # a list item's paragraph the same way it interrupts an ordinary one —
    # two separate blocks, two separate inline-parsing scopes — so both
    # links are real.

    def test_a_block_quote_interrupting_a_list_item_does_not_hide_a_link_in_a_straddling_code_span(self):
        """Measured at the reference: `- foo `x` / `> bar [a](…) y` [b](…)`
        renders `<ul><li>foo `x</li></ul>` (the backtick never pairs — the
        quote ends the list item's paragraph) plus a blockquote paragraph
        `bar <a>a</a> y` <a>b</a>` (its own backtick is unpaired too). Both
        links are real.
        """
        self.write_index(
            "# Memory Index\n\n"
            "- foo `x\n"
            "> bar [a](project_liq_a.md) y` [b](project_liq_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_liq_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_liq_b.md" in f for f in findings), findings)

    def test_a_block_quote_interrupting_an_ordered_list_item_does_not_hide_a_link_in_a_straddling_code_span(self):
        """Same shape, ordered-list marker: the list-item branch's regex
        covers both `[-+*]` and `[0-9]{1,9}[.)]` markers identically, so the
        gap and the fix apply the same way here.
        """
        self.write_index(
            "# Memory Index\n\n"
            "1. foo `x\n"
            "> bar [a](project_oliq_a.md) y` [b](project_oliq_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_oliq_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_oliq_b.md" in f for f in findings), findings)

    def test_a_block_quote_interrupting_a_list_item_hides_a_link_the_same_way_when_indented(self):
        """Same shape, quote line indented under the item (`  > …`): the
        boundary regex allows up to three leading spaces regardless of which
        container is open, so an indented interrupt hits the same gap.
        """
        self.write_index(
            "# Memory Index\n\n"
            "- foo `x\n"
            "  > bar [a](project_ilq_a.md) y` [b](project_ilq_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_ilq_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_ilq_b.md" in f for f in findings), findings)

    def test_a_block_quote_continuing_a_block_quote_keeps_a_straddling_code_span_paired(self):
        """Control that must NOT change: unlike a list item's paragraph, a
        block quote's own paragraph legitimately spans several `>` lines, and
        a code span may straddle THAT join the same way it does inside any
        paragraph (measured). A second `>` line merely CONTINUING an
        already-open quote must not flush — flushing here would split a
        block CommonMark keeps whole and report a link buried in code as
        real.
        """
        self.write_index(
            "# Memory Index\n\n"
            "> foo `x\n"
            "> bar [a](project_bqbq_a.md) y` [b](project_bqbq_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertFalse(any("project_bqbq_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_bqbq_b.md" in f for f in findings), findings)

    def test_an_atx_heading_before_a_block_quote_already_finds_both_links(self):
        """Control that must stay green throughout: an ATX heading flushes
        immediately and buffers nothing (WI-0084), so it never shares a
        buffer with what follows it — the gap above is specific to a list
        item's paragraph, which (unlike a heading) stays open across lines.
        """
        self.write_index(
            "# Memory Index\n\n"
            "# foo `x\n"
            "> bar [a](project_hq_a.md) y` [b](project_hq_b.md)\n"
        )

        findings = self.link_findings(self.run_lint().stdout)

        self.assertTrue(any("project_hq_a.md" in f for f in findings), findings)
        self.assertTrue(any("project_hq_b.md" in f for f in findings), findings)


class ScriptActuallyRanTest(unittest.TestCase):
    """WI-0037: a broken memory-lint.sh must not be able to pass its own tests.

    lines ~421-556 of memory-lint.sh are a single, single-quoted awk program. An
    apostrophe slipped into a comment inside it unbalances the quote and takes the
    whole file down with a bash parse error — before a single line of output is
    produced. Every negative-space test in MemoryLintTest (`assertEqual(x, [])`)
    stayed green against that broken script, because `[] == []` cannot tell "found
    nothing" apart from "ran nothing". These tests pin the fix at two levels: a
    cheap static syntax gate, and a regression test for the dynamic precondition
    now built into MemoryLintTest.run_lint() itself.
    """

    def test_memory_lint_sh_has_valid_bash_syntax(self):
        """Cheapest gate: `bash -n` parses the whole file without running it.

        Catches exactly the WI-0037 defect class (an unbalanced quote breaks
        parsing of the entire script) immediately and independently of any
        project fixture.
        """
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT_PATH)], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_run_lint_precondition_fails_loudly_on_a_script_that_cannot_parse(self):
        """Regression test for MemoryLintTest._assert_script_actually_ran.

        Reproduces the WI-0037 mutation shape programmatically (an apostrophe in a
        comment inside the awk program's single-quoted string) against a scratch
        copy of the real script, so the precondition's own correctness does not
        depend on someone hand-mutating the shipped script to prove it. Asserts
        the precondition raises — i.e. the harness notices — rather than silently
        accepting an empty, script-never-ran report.
        """
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        target = "forward for a same-length run without advancing `i`.\n"
        self.assertIn(
            target, original,
            "fixture line moved — update the mutation target for this test",
        )
        broken = original.replace(target, "forward for a same-length run — don't stop here.\n", 1)
        self.assertNotEqual(broken, original, "mutation did not change the script")

        with tempfile.TemporaryDirectory() as tmp:
            broken_script = Path(tmp) / "memory-lint.sh"
            broken_script.write_text(broken, encoding="utf-8")
            project_dir = Path(tmp) / "project"
            (project_dir / "docs" / "memory").mkdir(parents=True)
            fake_home = Path(tmp) / "home"
            fake_home.mkdir()

            result = subprocess.run(
                ["bash", str(broken_script), str(project_dir)],
                capture_output=True, text=True,
                env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            )

            self.assertEqual(result.stdout, "", "fixture assumption: a parse error produces no stdout")
            with self.assertRaises(AssertionError):
                MemoryLintTest._assert_script_actually_ran(result)

    # WI-0044: both guards above (bash -n and the header precondition) are blind
    # when the number of stray apostrophes inside the awk block is EVEN. Bash
    # toggles quoting at each apostrophe, so an even count restores parity by the
    # intended closing quote — bash -n parses it fine — but the unquoted middle
    # section becomes separate positional arguments, and awk takes only the first,
    # truncated fragment as its program text. That fails at awk *runtime*, not at
    # bash parse time: the script still exits 0 and still prints every report
    # section, it just silently drops findings. The two tests below pin both
    # forms of the SAME mutation target, so the odd/even contrast is measured
    # side by side rather than asserted from memory.

    _EVEN_MUTATION_TARGET = (
        "        # Strip HTML-comment spans before extracting links: parking a retired entry\n"
    )

    def _build_mutated_script(self, mutated_line, expected_delta):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn(
            self._EVEN_MUTATION_TARGET, original,
            "fixture line moved — update the mutation target for this test",
        )
        broken = original.replace(self._EVEN_MUTATION_TARGET, mutated_line, 1)
        self.assertNotEqual(broken, original, "mutation did not change the script")
        self.assertEqual(
            broken.count("'"), original.count("'") + expected_delta,
            "fixture must add exactly the intended apostrophe count",
        )
        return broken

    def test_odd_apostrophe_count_is_still_caught_by_bash_syntax_check(self):
        """The already-shipped half of the contrast: ODD stays caught by bash -n."""
        broken = self._build_mutated_script(
            "        # Strip HTML-comment spans before extracting links: parking a retired entry's own copy\n",
            expected_delta=1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            broken_script = Path(tmp) / "memory-lint.sh"
            broken_script.write_text(broken, encoding="utf-8")
            result = subprocess.run(
                ["bash", "-n", str(broken_script)], capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, "an odd apostrophe count must still fail bash -n")

    def test_even_apostrophe_count_defeats_both_wi_0037_guards_but_not_the_known_dead_link_probe(self):
        """WI-0044's own regression pin: EVEN defeats bash -n *and* the header
        precondition, and only the new known-dead-link probe (MemoryLintTest
        .setUpClass) notices.

        Measured against this exact mutation shape (19.08.2026): a real run
        against a probe carrying one dead link exits 0, prints every report
        section, and reports zero findings where one is due.
        """
        broken = self._build_mutated_script(
            "        # Strip HTML-comment spans before extracting links: parking a retired entry's own copy, don't stop\n",
            expected_delta=2,
        )
        with tempfile.TemporaryDirectory() as tmp:
            script_dir = Path(tmp) / "scriptdir"
            shutil.copytree(SCRIPT_PATH.parent / "lib", script_dir / "lib")
            broken_script = script_dir / "memory-lint.sh"
            broken_script.write_text(broken, encoding="utf-8")

            syntax = subprocess.run(
                ["bash", "-n", str(broken_script)], capture_output=True, text=True,
            )
            self.assertEqual(
                syntax.returncode, 0,
                "fixture assumption: an even apostrophe count must still pass bash -n",
            )

            result = MemoryLintTest._run_known_dead_link_probe(broken_script)
            self.assertEqual(
                result.returncode, 0,
                "fixture assumption: the mangled script still exits clean",
            )
            for heading in ("## Errors (", "## Warnings (", "## Info ("):
                self.assertIn(
                    heading, result.stdout,
                    "fixture assumption: WI-0037's header precondition stays blind here too",
                )
            self.assertEqual(
                result.stdout.count(LINK_FINDING_MARKER), 0,
                "fixture assumption: the known dead link is silently dropped, not just misreported",
            )

            with self.assertRaises(AssertionError):
                MemoryLintTest._assert_known_dead_link_is_found(broken_script)


class LinkScannerMutationTest(unittest.TestCase):
    """WI-0079/WI-0080/WI-0091/WI-0093/WI-0094 obligation: every rule of
    `process_link_line()`'s bracket-stack scanner, and every part of the
    reference-label machinery feeding it, must have been seen RED by a
    STRUCTURAL mutation of the rule itself — never by deletion, with one named
    exception. A deleted branch usually turns the whole suite red and proves
    only that something was removed; a rule replaced by a plausible-but-wrong
    variant proves which fixture discriminates it.

    The named exception is the pass-boundary reset (S-3): three of the nineteen
    mutations below DO remove a line, one `in_*` reset each. Removal is the
    plausible-but-wrong variant there, not a switch-off — the claim is that no
    state survives the boundary, and "survives a little" cannot be written as a
    substitution. What replaces the substitution as the guard against a merely
    broken mutant is a SECOND fixture: each of the three runs the same mutant
    on an open construct (must break) and on a closed one (must still report),
    so a mutant that simply killed the script fails the test. The full argument
    is at the block comment above those three tests. Whenever this discipline
    is relaxed again, name the mutation here and say why substitution could
    not express it.

    Each test mutates an in-memory COPY of the script. The shipped script on
    disk is never touched — proven by md5 before/after, same discipline as
    DestinationEscapeAndEntityMutationTest below.

    Nineteen mutations. Six from the WI-0080/WI-0091 round:

      * escape parity -> one-byte lookbehind (rule 2, WI-0079)
      * escape probed one byte past the OPENING bracket (rule 2)
      * escape probed one byte past the CLOSING bracket (rule 2)
      * image openers also deactivate their enclosing link (rule 4, WI-0091)
      * "deactivate enclosing LINK openers" predicate inverted (rule 3)
      * the opener stack capped at one entry (rule 1, WI-0080's depth claim)

    Eight added for the reference-link rule (rule 5, WI-0093/WI-0094):

      * the refmap lookup forced to "yes" — every inner label resolves
      * the refmap lookup forced to "no" — the WI-0093 false positive returns
      * the full and shortcut label SOURCES swapped
      * label collection restricted to pass 2 — a forward definition breaks
      * the "may not interrupt a paragraph" gate dropped
      * a resolved reference span no longer consumed
      * an image reference deactivates its enclosing opener
      * the label grammar skips one byte per escape instead of two (WI-0094)

    Two added for WI-0098, one per side of the label-key space:

      * the definition label registered without resolve_paragraph() — the
        false positive on a code-span label returns
      * the `lbl != ""` guard put back on the usage-side lookup — likewise

    Three added for the pass-boundary reset (S-3), one reset line removed each:

      * `in_fence = 0` — an unclosed fence swallows the second pass
      * `in_html_block1 = 0` — an unclosed `<script>` block does
      * `in_html_block6 = 0` — an unclosed `<div>` block does

    Every one of the nineteen was itself falsified once, by neutralising the
    mutation (`_mutate` returning the script unchanged) and confirming all
    nineteen go red — a mutation test that cannot fail proves nothing.
    """

    def _run_mutant(self, mutated, index_body, raw=False):
        """Runs `mutated` against a scratch project whose index body is
        `index_body`, and returns the memory-lint stdout.

        `raw=True` writes `index_body` verbatim instead of prefixing the usual
        `# Memory Index` heading and blank line. Needed by the pass-boundary
        tests below, where that blank line is not neutral: it closes a leaked
        fence or type-6 block before the fixture's own link is reached, and the
        mutation then looks harmless."""
        with tempfile.TemporaryDirectory() as tmp:
            script_dir = Path(tmp) / "scriptdir"
            shutil.copytree(SCRIPT_PATH.parent / "lib", script_dir / "lib")
            mutant_script = script_dir / "memory-lint.sh"
            mutant_script.write_text(mutated, encoding="utf-8")

            project_dir = Path(tmp) / "project"
            (project_dir / "docs" / "memory").mkdir(parents=True)
            (project_dir / "docs" / "memory" / "MEMORY.md").write_text(
                index_body if raw else "# Memory Index\n\n" + index_body,
                encoding="utf-8",
            )
            fake_home = Path(tmp) / "home"
            fake_home.mkdir()

            return subprocess.run(
                ["bash", str(mutant_script), str(project_dir)],
                capture_output=True, text=True,
                env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            ).stdout

    def _mutate(self, old, new):
        """Returns the script source with `old` replaced by `new`, asserting the
        target is present exactly once (so a drifted fixture fails loudly here
        instead of silently mutating nothing)."""
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            original.count(old), 1,
            "mutation target moved — update this test's fixture",
        )
        mutated = original.replace(old, new, 1)
        self.assertNotEqual(mutated, original, "mutation did not change the script")
        return original, mutated

    def _mutate_both(self, pairs):
        """Like _mutate(), but applies MULTIPLE independent (old, new) pairs to
        the same original text, each checked for a unique target the same way
        _mutate() does one.

        Needed since WI-0095 (closed): process_link_line()'s bracket-escape
        rule 2 and protect_link_destinations()'s own opener/escape check (the
        WI-0095 fix) now cooperate on the SAME question -- is this `[`/`]`
        live or escaped -- for the inline-destination shape. Either one alone
        being correct is enough to keep a non-link silent, so a single-line
        mutation of process_link_line() no longer flips those fixtures (the
        untouched protect_link_destinations() check masks it). Breaking both
        checks the same way is what the two escape-position tests below need;
        see their docstrings."""
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        mutated = original
        for old, new in pairs:
            self.assertEqual(
                original.count(old), 1,
                "mutation target moved — update this test's fixture",
            )
            mutated = mutated.replace(old, new, 1)
        self.assertNotEqual(mutated, original, "mutation did not change the script")
        return original, mutated

    def _assert_script_untouched(self, original):
        after = SCRIPT_PATH.read_text(encoding="utf-8")
        md5 = __import__("hashlib").md5
        self.assertEqual(
            md5(original.encode("utf-8")).hexdigest(),
            md5(after.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(after, original)

    def test_escape_parity_replaced_by_a_one_byte_lookbehind_flips_a_live_link_silent(self):
        """Rule 2 (WI-0079). The scanner asks is_escaped(), i.e. backslash-run
        PARITY. Replaced here by the naive "is the previous byte a backslash",
        which is wrong for `\\\\[x](t.md)`: that is an escaped BACKSLASH followed
        by a LIVE bracket, and the reference renders a real link. The mutant
        reads the bracket as escaped and stays silent — so the doubly-escaped
        fixture is what discriminates the parity rule, not the single-escape
        one (which both variants get right)."""
        original, mutated = self._mutate(
            '                if (ch == "[" && !is_escaped(line, i)) {',
            '                if (ch == "[" && substr(line, i - 1, 1) != "\\\\") {',
        )

        out = self._run_mutant(
            mutated,
            "- \\\\[real link](gone_mut_dbl.md) — live\n"
            "- [control](gone_mut_ctl1.md) — plain dead link\n",
        )

        self.assertIn(
            "gone_mut_ctl1.md", out,
            "the mutant produced no findings at all — this assertion cannot "
            "discriminate anything (the control link must still be reported)",
        )
        self.assertNotIn(
            "gone_mut_dbl.md", out,
            "mutation did not flip the fixture — the doubly-escaped-backslash "
            "case no longer discriminates parity from a one-byte lookbehind",
        )
        self._assert_script_untouched(original)

    def test_probing_the_escape_one_byte_past_the_opening_bracket_revives_a_non_link(self):
        r"""Rule 2, the OPENING bracket. `\[text](t.md)` is not a link at the
        reference — escaping either bracket alone is enough. The mutation keeps
        the escape test but asks it about the wrong POSITION (`i + 1`, the byte
        after the bracket), which is never preceded by a backslash. The mutant
        pushes an opener that should not exist and reports a target nobody
        linked — a false POSITIVE, the direction that matters most.

        Mutates BOTH process_link_line()'s check and protect_link_
        destinations()'s own opener/escape check (see _mutate_both()) — since
        WI-0095 closed, the latter refuses to even draw a dest_mark span for
        an escaped opener, so mutating process_link_line() alone leaves this
        inline-destination fixture silent regardless (measured: it does)."""
        original, mutated = self._mutate_both([
            ('                if (ch == "[" && !is_escaped(s, i)) {',
             '                if (ch == "[" && !is_escaped(s, i + 1)) {'),
            ('                if (ch == "[" && !is_escaped(line, i)) {',
             '                if (ch == "[" && !is_escaped(line, i + 1)) {'),
        ])

        out = self._run_mutant(mutated, "- \\[text](gone_mut_openesc.md) — not a link\n")

        self.assertIn(
            "gone_mut_openesc.md", out,
            "mutation did not flip the fixture — nothing pins that an escaped "
            "OPENING bracket opens nothing",
        )
        self._assert_script_untouched(original)

    def test_probing_the_escape_one_byte_past_the_closing_bracket_revives_a_non_link(self):
        r"""Rule 2, the CLOSING bracket. `[text\](t.md)` is not a link either.
        Same off-by-one mutation on the `]` branch: the escape test still runs,
        one byte too far along, and the mutant closes a link the reference does
        not render.

        Same reason as the OPENING-bracket test above for mutating BOTH
        functions' checks together (see _mutate_both()) — WI-0095 gave
        protect_link_destinations() the same escape-parity test on `]`, and
        mutating process_link_line() alone no longer flips this fixture."""
        original, mutated = self._mutate_both([
            ('                if (ch == "]" && !is_escaped(s, i)) {',
             '                if (ch == "]" && !is_escaped(s, i + 1)) {'),
            ('                if (ch == "]" && !is_escaped(line, i)) {',
             '                if (ch == "]" && !is_escaped(line, i + 1)) {'),
        ])

        out = self._run_mutant(mutated, "- [text\\](gone_mut_closeesc.md) — not a link\n")

        self.assertIn(
            "gone_mut_closeesc.md", out,
            "mutation did not flip the fixture — nothing pins that an escaped "
            "CLOSING bracket closes nothing",
        )
        self._assert_script_untouched(original)

    def test_letting_an_image_deactivate_its_enclosing_opener_flips_the_badge_silent(self):
        """Rule 4 (WI-0091). Only a LINK in the link text disqualifies the
        enclosing link; an IMAGE does not. The mutation moves the deactivation
        loop OUT of the `!o_img` branch, so an image deactivates too — both
        branches still present, one line differently placed. The badge shape
        `[![alt](b.png)](t.md)` then reports nothing."""
        original, mutated = self._mutate(
            "                        if (!o_img) {\n"
            "                            print strip_dest_mark(substr(line, i + 3, e - 1))\n"
            "                            deactivate_enclosing_link_openers(sp, st_img, st_act)\n"
            "                        }\n",
            "                        if (!o_img) {\n"
            "                            print strip_dest_mark(substr(line, i + 3, e - 1))\n"
            "                        }\n"
            "                        deactivate_enclosing_link_openers(sp, st_img, st_act)\n",
        )

        out = self._run_mutant(
            mutated,
            "- [![alt](gone_mut_badge.png)](gone_mut_ci.md) — badge\n"
            "- [control](gone_mut_ctl2.md) — plain dead link\n",
        )

        self.assertIn(
            "gone_mut_ctl2.md", out,
            "the mutant produced no findings at all — this assertion cannot "
            "discriminate anything (the control link must still be reported)",
        )
        self.assertNotIn(
            "gone_mut_ci.md", out,
            "mutation did not flip the fixture — the badge shape no longer "
            "discriminates 'an image does not disqualify the outer link'",
        )
        self._assert_script_untouched(original)

    def test_inverting_the_deactivation_predicate_reports_the_outer_link_too(self):
        """Rule 3. "Links may not contain other links, at any level of nesting"
        — the inner link wins. The mutation inverts the predicate that decides
        WHICH openers get deactivated (`!st_img[k]` -> `st_img[k]`), so the
        enclosing LINK opener survives and the outer target is reported
        alongside the inner one. Not a removal: the loop still runs, still
        assigns, just to the complementary set."""
        original, mutated = self._mutate(
            "for (k = 1; k <= sp; k++) if (!st_img[k]) st_act[k] = 0",
            "for (k = 1; k <= sp; k++) if (st_img[k]) st_act[k] = 0",
        )

        out = self._run_mutant(
            mutated,
            "- [a [b](gone_mut_in.md) c](gone_mut_out.md) — link in link text\n",
        )

        self.assertIn(
            "gone_mut_out.md", out,
            "mutation did not flip the fixture — nothing pins that a link "
            "inside the link text disqualifies the enclosing one",
        )
        self._assert_script_untouched(original)

    def test_capping_the_opener_stack_at_one_entry_flips_the_nested_label_silent(self):
        """Rule 1 (WI-0080's central claim: the label is a BALANCED construct,
        so the scanner needs a real stack). The mutation caps the stack at a
        single entry — a nested `[` then overwrites the outer opener instead of
        pushing beside it, which is exactly what a "remember the last opener"
        implementation would do. A FLAT link is unaffected (asserted here, so
        the mutation is not simply breaking everything); the nested label goes
        silent.

        The target string includes the following `st_act[sp] = 1` line —
        protect_link_destinations() gained its own, differently-scoped `sp++`
        for the opener check WI-0095 closed, so the bare line alone no longer
        identifies process_link_line()'s copy uniquely."""
        original, mutated = self._mutate(
            "                    sp++\n"
            "                    st_act[sp] = 1\n",
            "                    if (sp < 1) sp++\n"
            "                    st_act[sp] = 1\n",
        )

        out = self._run_mutant(
            mutated,
            "- [a [b] c](gone_mut_nested.md) — nested\n"
            "- [flat](gone_mut_flat.md) — flat control\n",
        )

        self.assertNotIn(
            "gone_mut_nested.md", out,
            "mutation did not flip the fixture — the nested label no longer "
            "discriminates a real opener stack from a single remembered opener",
        )
        self.assertIn(
            "gone_mut_flat.md", out,
            "the mutation broke the flat case too — it is not discriminating "
            "the depth rule specifically",
        )
        self._assert_script_untouched(original)


    _REFMAP_LOOKUP = "            return ((lbl in refmap) ? n : -1)"

    def test_a_refmap_that_answers_yes_to_everything_silences_a_live_nested_link(self):
        """Rule 5 (WI-0093), the direction that matters most. The refmap lookup
        is what separates `[a [ref] c](t.md)`, which renders no outer link, from
        `[a [b] c](t.md)`, WI-0080's central fixture, which renders one. Forced
        to "yes" here — every inner label resolves — the nested-bracket link goes
        silent while a plain link is untouched."""
        original, mutated = self._mutate(
            self._REFMAP_LOOKUP,
            '            return ((lbl != "") ? n : -1)',
        )

        out = self._run_mutant(
            mutated,
            "- [a [b] c](gone_mut_nb_live.md) — nested, no definition anywhere\n"
            "- [control](gone_mut_ctl3.md) — plain dead link\n",
        )

        self.assertIn(
            "gone_mut_ctl3.md", out,
            "the mutant produced no findings at all — this assertion cannot "
            "discriminate anything (the control link must still be reported)",
        )
        self.assertNotIn(
            "gone_mut_nb_live.md", out,
            "mutation did not flip the fixture — nothing pins that an inner "
            "label must RESOLVE before it disqualifies the enclosing link",
        )
        self._assert_script_untouched(original)

    def test_a_refmap_that_answers_no_to_everything_revives_the_false_positive(self):
        """Rule 5, the other direction: neutralising the lookup restores exactly
        the WI-0093 defect — the outer destination of
        `[outer [r] text](out.md)` is reported again although the reference
        renders no link there."""
        original, mutated = self._mutate(
            self._REFMAP_LOOKUP,
            "            return (n < 0 ? n : -1)",
        )

        out = self._run_mutant(
            mutated,
            "[mutref]: gone_mut_refdefn.md\n"
            "\n"
            "- [outer [mutref] text](gone_mut_refouter.md) — reference inside\n",
        )

        self.assertIn(
            "gone_mut_refouter.md", out,
            "mutation did not flip the fixture — nothing pins that a RESOLVING "
            "reference link in the link text disqualifies the enclosing one",
        )
        self._assert_script_untouched(original)

    def test_swapping_the_two_label_sources_breaks_the_full_reference_form(self):
        """Rule 5, the form distinction. A FULL reference `[text][ref]` names
        its definition in the SECOND label; the collapsed and shortcut forms
        name it in the FIRST. The mutation swaps the two `raw` assignments —
        both branches still present, still assigning — so the full form takes
        its label from the link TEXT and looks up `txt`, which is undefined,
        and the outer link is reported again."""
        original, mutated = self._mutate(
            "            if (n > 2) raw = substr(s, i + 2, n - 2)\n"
            "            else raw = substr(s, o_pos + 1, i - o_pos - 1)\n",
            "            if (n > 2) raw = substr(s, o_pos + 1, i - o_pos - 1)\n"
            "            else raw = substr(s, i + 2, n - 2)\n",
        )

        out = self._run_mutant(
            mutated,
            "[mutfull]: gone_mut_fulldefn.md\n"
            "\n"
            "- [outer [txt][mutfull] text](gone_mut_fullouter.md) — full reference\n",
        )

        self.assertIn(
            "gone_mut_fullouter.md", out,
            "mutation did not flip the fixture — nothing pins WHICH of the two "
            "labels a full reference resolves against",
        )
        self._assert_script_untouched(original)

    def test_collecting_labels_in_the_second_pass_only_breaks_a_forward_definition(self):
        """The two-pass architecture (WI-0093). CommonMark collects reference
        definitions for the whole document before parsing any inline content, so
        a definition may stand AFTER its use. The mutation restricts recording
        to pass 2, i.e. reduces the program to a single effective pass. A
        BACKWARD definition still works — asserted here, so the mutation is not
        simply switching the feature off — and only the forward one breaks.

        WI-0083 moved this line into register_reference_definition(), the
        helper both the same-line form and the next-line lookahead now share
        — the mutation target text is the same statement, at the function
        body's own (shallower) indentation."""
        original, mutated = self._mutate(
            "            refmap[reflbl] = 1\n",
            "            if (pass == 2) refmap[reflbl] = 1\n",
        )

        out = self._run_mutant(
            mutated,
            "- [outer [mutfwd] text](gone_mut_fwdouter.md) — used before defined\n"
            "\n"
            "[mutfwd]: gone_mut_fwddefn.md\n"
            "\n"
            "[mutback]: gone_mut_backdefn.md\n"
            "\n"
            "- [outer [mutback] text](gone_mut_backouter.md) — used after defined\n",
        )

        self.assertIn(
            "gone_mut_fwdouter.md", out,
            "mutation did not flip the fixture — nothing pins that a definition "
            "AFTER its use is still collected, i.e. that two passes are needed",
        )
        self.assertNotIn(
            "gone_mut_backouter.md", out,
            "the mutant broke the backward direction too — it is not "
            "discriminating the forward-reference claim specifically",
        )
        self._assert_script_untouched(original)

    def test_dropping_the_paragraph_gate_lets_a_non_definition_define_a_label(self):
        """A link reference definition may not INTERRUPT a paragraph — with
        prose open above it the line is ordinary text and defines nothing
        (measured). The mutation drops that gate, so the line becomes a
        definition again: it defines `mutint`, wrongly silencing an outer link
        the reference renders, and it reports its own target, which is the
        WI-0096 false positive. One gate, both effects — that is why the
        mutant's two assertions below are the exact inverse of the shipped
        script's behaviour on the same fixture."""
        original, mutated = self._mutate(
            '                    if (pbuf_n == 0 && reflbl != "" && reference_definition_tail(raw_rest)) {\n',
            '                    if (pbuf_n >= 0 && reflbl != "" && reference_definition_tail(raw_rest)) {\n',
        )

        out = self._run_mutant(
            mutated,
            "some prose\n"
            "[mutint]: gone_mut_intdefn.md\n"
            "\n"
            "- [outer [mutint] text](gone_mut_intouter.md) — not a definition above\n",
        )

        self.assertIn(
            "gone_mut_intdefn.md", out,
            "the mutant produced no findings at all — this assertion cannot "
            "discriminate anything (the definition line target must still be "
            "reported, it is the outer link that must vanish)",
        )
        self.assertNotIn(
            "gone_mut_intouter.md", out,
            "mutation did not flip the fixture — nothing pins that a "
            "definition-shaped line inside a paragraph defines nothing",
        )
        self._assert_script_untouched(original)

    def test_dropping_the_empty_label_gate_makes_a_whitespace_only_line_a_definition(self):
        """The second half of the same guard (WI-0096 sibling). CommonMark's
        own parseReference rejects a label that normalises to nothing, so
        `[   ]: dead.md` is visible prose, not a definition — measured. The
        mutation neutralises the `reflbl != ""` test WITHOUT removing it (the
        comparison is made trivially true), so the line defines the empty label
        and reports its target: the false positive returns AND the outer link
        the reference renders goes silent. Two effects, one guard, both
        asserted — a mutant that merely broke the script would fail the first
        assertion."""
        original, mutated = self._mutate(
            '                    if (pbuf_n == 0 && reflbl != "" && reference_definition_tail(raw_rest)) {\n',
            '                    if (pbuf_n == 0 && reflbl == reflbl && reference_definition_tail(raw_rest)) {\n',
        )

        out = self._run_mutant(
            mutated,
            "[   ]: gone_mut_wsdefn.md\n"
            "\n"
            "- [outer [   ] text](gone_mut_wsouter.md) — whitespace-only label\n",
        )

        self.assertIn(
            "gone_mut_wsdefn.md", out,
            "the mutant produced no definition finding at all — this assertion "
            "cannot discriminate anything",
        )
        self.assertNotIn(
            "gone_mut_wsouter.md", out,
            "mutation did not flip the fixture — nothing pins that a label "
            "which normalises to nothing is no label",
        )
        self._assert_script_untouched(original)

    _WI0098_RESOLVED_KEY = (
        "            reslbl = normalize_label("
        "resolve_paragraph(protect_link_destinations(rawlbl)))\n"
    )

    def test_registering_only_the_raw_definition_label_revives_the_code_span_false_positive(self):
        """WI-0098, the definition half. The usage side reads its label out of
        the RESOLVED paragraph, so the definition side has to register the
        resolved shape as well. The mutation drops one stage of that pipeline —
        resolve_paragraph(), the stage that deletes a code span — so
        ``[`r`]:`` registers only `` `r` `` again while the scanner looks up the
        empty string, and the outer link the reference does not render comes
        back as a finding.

        WI-0083 moved this line into register_reference_definition() (the
        function body's own, shallower indentation — see _WI0098_RESOLVED_KEY)."""
        original, mutated = self._mutate(
            self._WI0098_RESOLVED_KEY,
            "            reslbl = normalize_label("
            "protect_link_destinations(rawlbl))\n",
        )

        out = self._run_mutant(
            mutated,
            "[`mutcs`]: gone_mut_csdefn.md\n"
            "\n"
            "- [outer [`mutcs`] text](gone_mut_csouter.md) — code-span label\n",
        )

        self.assertIn(
            "gone_mut_csdefn.md", out,
            "the mutant produced no definition finding at all — this assertion "
            "cannot discriminate anything",
        )
        self.assertIn(
            "gone_mut_csouter.md", out,
            "mutation did not flip the fixture — nothing pins that the "
            "definition label is registered in the shape the scanner reads",
        )
        self._assert_script_untouched(original)

    def test_re_guarding_the_empty_label_lookup_revives_the_code_span_false_positive(self):
        """WI-0098, the usage half. A label that resolved away to nothing is
        still a label a definition can carry, so the lookup must not refuse the
        empty string. The mutation puts the `lbl != ""` guard back — the shape
        this code had before the fix — and the same false positive returns."""
        original, mutated = self._mutate(
            self._REFMAP_LOOKUP,
            '            return ((lbl != "" && (lbl in refmap)) ? n : -1)',
        )

        out = self._run_mutant(
            mutated,
            "[`mutcs2`]: gone_mut_cs2defn.md\n"
            "\n"
            "- [outer [`mutcs2`] text](gone_mut_cs2outer.md) — code-span label\n"
            "- [plain [mutplain] text](gone_mut_cs2plain.md) — undefined label, control\n",
        )

        self.assertIn(
            "gone_mut_cs2plain.md", out,
            "the mutant produced no findings at all — this assertion cannot "
            "discriminate anything (the control link must still be reported)",
        )
        self.assertIn(
            "gone_mut_cs2outer.md", out,
            "mutation did not flip the fixture — nothing pins that an emptied "
            "label is still looked up",
        )
        self._assert_script_untouched(original)

    # --- The pass-boundary reset, one removed line at a time (S-3) -----------
    # REMOVAL mutations, which normally prove little — a removal tends to make
    # everything red. Here it is the right shape: the block exists solely so
    # that pass 2 starts from BEGIN state, and the only way to say "this one
    # line is load-bearing" is to take it out. Each test therefore runs the
    # SAME mutant twice — once on a fixture that leaves the construct open at
    # the pass boundary (must break) and once on a fixture that closes it (must
    # still work) — so a mutant that merely broke the script cannot pass.
    #
    # Each target carries the line ABOVE it as an anchor. `in_fence = 0` on its
    # own is a substring of the fence-closing branch's own `in_fence = 0` one
    # indent deeper, and _mutate() would have refused it.
    #
    # Three of the twelve reset lines have NO such test, and that is a measured
    # statement, not an omission: removing `fence_char = ""`, `fence_len = 0` or
    # `fence_open_line = 0` alone changes NOTHING observable, on any of the ten
    # fixtures tried. All three are read only under `if (in_fence)`, and every
    # path that sets `in_fence = 1` assigns fence_char and fence_len in the same
    # breath, so with `in_fence` reset they are unreachable. They are reset so
    # that "pass 2 starts from BEGIN state" is a property of the block rather
    # than a chain of reasoning about which flag guards which — the same
    # discipline the awk-local declarations elsewhere in this script follow.

    def _assert_reset_line_is_load_bearing(self, anchored_target, anchor_only,
                                           open_body, closed_body, target):
        original, mutated = self._mutate(anchored_target, anchor_only)

        leaked = self._run_mutant(mutated, open_body, raw=True)
        intact = self._run_mutant(mutated, closed_body, raw=True)

        self.assertIn(
            target, intact,
            "the mutant reports nothing even with the construct CLOSED — it "
            "broke the script outright and discriminates nothing",
        )
        self.assertNotIn(
            target, leaked,
            "mutation did not flip the fixture — nothing pins that this reset "
            "line stops the flag from crossing the pass boundary",
        )
        self._assert_script_untouched(original)

    # These fixtures need the dead link BEFORE the first blank line of the
    # index, for the reason spelt out at the behaviour tests above — so they are
    # written raw, without _run_mutant()'s usual "# Memory Index\n\n" prefix
    # whose blank line would close the leaked construct first and make every
    # mutation below look harmless. It did, before this was measured.
    _MUT_LEAK_HEAD = "# Memory Index\nA paragraph with [Dead]({dead}).\n\n"

    def test_dropping_the_in_fence_reset_lets_an_unclosed_fence_swallow_the_second_pass(self):
        """`in_fence = 0` at the pass boundary."""
        head = self._MUT_LEAK_HEAD.format(dead="gone_mut_passfence.md")
        self._assert_reset_line_is_load_bearing(
            "                pass = 2\n                in_fence = 0\n",
            "                pass = 2\n",
            head + "```\n- [x](gone_mut_infence.md)\n",
            head + "```\n- [x](gone_mut_infence.md)\n```\n",
            "gone_mut_passfence.md",
        )

    def test_dropping_the_in_html_block1_reset_lets_an_unclosed_script_swallow_the_second_pass(self):
        """`in_html_block1 = 0` at the pass boundary."""
        head = self._MUT_LEAK_HEAD.format(dead="gone_mut_passb1.md")
        self._assert_reset_line_is_load_bearing(
            "                html_comment_open_line = 0\n                in_html_block1 = 0\n",
            "                html_comment_open_line = 0\n",
            head + "<script>\n- [x](gone_mut_inb1.md)\n",
            head + "<script>\n- [x](gone_mut_inb1.md)\n</script>\n",
            "gone_mut_passb1.md",
        )

    def test_dropping_the_in_html_block6_reset_lets_an_unclosed_div_swallow_the_second_pass(self):
        """`in_html_block6 = 0` at the pass boundary."""
        head = self._MUT_LEAK_HEAD.format(dead="gone_mut_passb6.md")
        self._assert_reset_line_is_load_bearing(
            "                in_html_block1 = 0\n                in_html_block6 = 0\n",
            "                in_html_block1 = 0\n",
            head + "<div>\n- [x](gone_mut_inb6.md)\n",
            head + "<div>\n- [x](gone_mut_inb6.md)\n\n",
            "gone_mut_passb6.md",
        )

    def test_not_consuming_a_resolved_reference_span_reports_a_stray_parenthesis(self):
        """Rule 5 consumes the span it matched. `[txt][ref](x.md)` renders the
        reference link and leaves `(x.md)` as literal text; a scanner that only
        deactivated and stepped one byte on re-reads `[ref](x.md)` as an inline
        link. The mutation replaces the consuming advance with the one-byte one
        — a false POSITIVE, a target nobody linked."""
        original, mutated = self._mutate(
            "                    i = i + 1 + r\n",
            "                    i++\n",
        )

        out = self._run_mutant(
            mutated,
            "[mutcons]: gone_mut_consdefn.md\n"
            "\n"
            "- [txt][mutcons](gone_mut_consparen.md) — the paren is literal text\n",
        )

        self.assertIn(
            "gone_mut_consparen.md", out,
            "mutation did not flip the fixture — nothing pins that a resolved "
            "reference link CONSUMES its second label",
        )
        self._assert_script_untouched(original)

    def test_letting_an_image_reference_deactivate_its_enclosing_opener_flips_it_silent(self):
        """Rule 4 meets rule 5: `![ref]` is an IMAGE even when it resolves, and
        an image in the link text does not disqualify the enclosing link. The
        mutation drops the image guard from the reference branch only — the
        inline branch keeps its own — so the badge-shaped reference form
        silences a link the reference renders."""
        original, mutated = self._mutate(
            "                    if (!o_img) deactivate_enclosing_link_openers(sp, st_img, st_act)\n",
            "                    deactivate_enclosing_link_openers(sp, st_img, st_act)\n",
        )

        out = self._run_mutant(
            mutated,
            "[mutimg]: gone_mut_imgdefn.png\n"
            "\n"
            "- [outer ![mutimg] text](gone_mut_imgouter.md) — image reference inside\n",
        )

        self.assertIn(
            "gone_mut_imgdefn.png", out,
            "the mutant produced no findings at all — this assertion cannot "
            "discriminate anything (the definition line target must still be "
            "reported)",
        )
        self.assertNotIn(
            "gone_mut_imgouter.md", out,
            "mutation did not flip the fixture — nothing pins that an IMAGE "
            "reference leaves the enclosing link alone",
        )
        self._assert_script_untouched(original)

    def test_a_one_byte_escape_skip_in_the_label_grammar_unmakes_a_definition(self):
        """WI-0094, the DEFINITION side of the label grammar. A backslash
        escapes exactly ONE following character, so `[a\\]b]` is a five-character
        label ending at the second `]`. The mutation consumes the backslash but
        not what it escapes — the label then ends at the escaped `]`, the line
        stops being a definition, and its target goes unchecked. A plain
        definition on the same file is unaffected (asserted), so the mutation
        discriminates the escape rule and not definitions in general."""
        original, mutated = self._mutate(
            "                if (c == \"\\\\\") {\n"
            "                    if (p >= n || substr(s, p + 1, 1) == \"\\n\") return 0\n"
            "                    p += 2\n"
            "                    continue\n"
            "                }\n",
            "                if (c == \"\\\\\") {\n"
            "                    p++\n"
            "                    continue\n"
            "                }\n",
        )

        out = self._run_mutant(
            mutated,
            "[a\\]b]: gone_mut_escdefn.md\n"
            "\n"
            "[plain]: gone_mut_plaindefn.md\n",
        )

        self.assertIn(
            "gone_mut_plaindefn.md", out,
            "the mutant stopped recognising definitions altogether — it is not "
            "discriminating the escape rule specifically",
        )
        self.assertNotIn(
            "gone_mut_escdefn.md", out,
            "mutation did not flip the fixture — nothing pins that a "
            "backslash-escaped bracket is CONTENT of a definition label",
        )
        self._assert_script_untouched(original)


class LinkScannerAgreementTest(unittest.TestCase):
    """WI-0117 obligation: nothing pins that protect_link_destinations()
    (~1025) and process_link_line() (~1368) AGREE on the one thing WI-0095's
    own consolidation note says they must agree on — where a live, unescaped
    opener sits. LinkScannerMutationTest's _mutate_both() restores mutation
    STRENGTH for the shared case by mutating both copies in lockstep; by
    construction it cannot notice the two copies drifting APART, because a
    lockstep mutation can never produce a disagreement between them. This
    class is the missing instrument: it observes each function's own verdict
    ("is there a live opener open right now") at every unescaped `]`, on the
    identical input text, and pins that the two SEQUENCES of verdicts agree —
    not that the two functions behave identically overall, which they do not
    and are not meant to (rule-3 deactivation, image markers, the per-level
    st_act/st_img/st_pos arrays, and the destination scan itself exist in
    one, not the other).

    Observability. Neither function returns "where the live opener sits" as
    an inspectable value — protect_link_destinations() only exposes it
    indirectly (whether a dest_mark span gets drawn), and process_link_line()
    only exposes it via which branch it takes next. Both compute the verdict
    explicitly, though, as a plain local boolean, right where the shared
    concept lives: `had_opener = (sp > 0)` at ~1041, and the `sp == 0` test
    guarding rule 3 at ~1416. A scratch COPY of the shipped script (never the
    file on disk — proven by md5, same discipline as every other mutation
    test in this module) gets one print statement inserted immediately after
    each of those two decision points, writing the position and the boolean
    to a debug file named by an environment variable. Nothing about either
    function's control flow changes; the insertion is a pure side-effecting
    print placed after the decision is already made and stored in a local.
    Real (non-test) runs never set the environment variable, and the shipped
    script on disk is never touched — this print has never existed there.

    Discriminates by construction, not by accident:
    test_a_deliberate_divergence_between_the_two_scans_is_caught below
    tightens ONLY protect_link_destinations()'s opening-bracket escape check
    (the WI-0079 one-byte-lookbehind mutation LinkScannerMutationTest applies
    to BOTH functions via _mutate_both() — here to ONE only, on purpose) and
    shows the two traces disagree where they used to agree. That is the RED
    step this obligation asks for, kept as a permanent regression test rather
    than a one-off manual check, so the instrument's own discriminating power
    stays proven going forward.

    What this deliberately does NOT test: equality of the two functions'
    full behaviour (they read different texts at different pipeline stages —
    protect_link_destinations() runs per raw line, process_link_line() runs
    once on the fully resolved paragraph via resolve_paragraph(pbuf), where
    pbuf is already protect's own output). The eight fixtures below are
    chosen so that resolved destinations sit at the END of the live-opener
    positions being compared, or draw no destination at all — so a dest_mark
    substitution's length change never lands BETWEEN two `]` positions being
    correlated. A fixture with a second destination following an already-
    resolved one on the same line would need position correlation by ORDINAL
    occurrence instead of raw byte offset; none of the eight need that, and
    adding one that does would need that change made first.
    """

    _DEBUG_ENV = "MEMLINT_WI0117_DEBUG"

    _PROTECT_ANCHOR = (
        '                    had_opener = (sp > 0)\n'
        '                    if (had_opener) sp--\n'
    )
    _PROTECT_INSTRUMENTED = (
        '                    had_opener = (sp > 0)\n'
        '                    if (ENVIRON["' + _DEBUG_ENV + '"] != "") '
        'print "P", i, (had_opener ? 1 : 0) >> ENVIRON["' + _DEBUG_ENV + '"]\n'
        '                    if (had_opener) sp--\n'
    )

    _PROCESS_ANCHOR = (
        '                if (ch == "]" && !is_escaped(line, i)) {\n'
        '                    if (sp == 0) {   # no opener left — a literal `]`\n'
    )
    _PROCESS_INSTRUMENTED = (
        '                if (ch == "]" && !is_escaped(line, i)) {\n'
        '                    if (ENVIRON["' + _DEBUG_ENV + '"] != "") '
        'print "Q", i, (sp > 0 ? 1 : 0) >> ENVIRON["' + _DEBUG_ENV + '"]\n'
        '                    if (sp == 0) {   # no opener left — a literal `]`\n'
    )

    def _instrumented_script(self, extra_pairs=()):
        """Returns (original, instrumented) script text. `extra_pairs` are
        additional (old, new) substitutions applied on top of the two
        instrumentation insertions — used by the divergence test below to
        also mutate one function's escape check. Every anchor is checked for
        a unique target first, same discipline as LinkScannerMutationTest's
        own _mutate()/_mutate_both(), so a drifted line fails this test
        loudly instead of silently instrumenting nothing."""
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        for anchor in (self._PROTECT_ANCHOR, self._PROCESS_ANCHOR):
            self.assertEqual(
                original.count(anchor), 1,
                "instrumentation anchor moved — update this test's fixture",
            )
        mutated = original.replace(self._PROTECT_ANCHOR, self._PROTECT_INSTRUMENTED, 1)
        mutated = mutated.replace(self._PROCESS_ANCHOR, self._PROCESS_INSTRUMENTED, 1)
        for old, new in extra_pairs:
            self.assertEqual(
                original.count(old), 1,
                "mutation target moved — update this test's fixture",
            )
            mutated = mutated.replace(old, new, 1)
        self.assertNotEqual(mutated, original, "mutation did not change the script")
        return original, mutated

    def _traces_for(self, mutated, pattern):
        """Runs `mutated` against a one-line scratch index body holding
        `pattern` as its own paragraph (blank lines on both sides — none of
        the fixtures start with a list marker, blockquote or heading prefix,
        so each is read as ordinary paragraph text), and returns
        (protect_trace, process_trace): ordered (position, is_live) tuples
        read from the debug file the instrumentation writes."""
        with tempfile.TemporaryDirectory() as tmp:
            script_dir = Path(tmp) / "scriptdir"
            shutil.copytree(SCRIPT_PATH.parent / "lib", script_dir / "lib")
            mutant_script = script_dir / "memory-lint.sh"
            mutant_script.write_text(mutated, encoding="utf-8")

            project_dir = Path(tmp) / "project"
            (project_dir / "docs" / "memory").mkdir(parents=True)
            (project_dir / "docs" / "memory" / "MEMORY.md").write_text(
                "# Memory Index\n\n" + pattern + "\n",
                encoding="utf-8",
            )
            fake_home = Path(tmp) / "home"
            fake_home.mkdir()
            debug_file = Path(tmp) / "trace.txt"

            subprocess.run(
                ["bash", str(mutant_script), str(project_dir)],
                capture_output=True, text=True,
                env={
                    "HOME": str(fake_home),
                    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                    self._DEBUG_ENV: str(debug_file),
                },
            )

            protect_trace, process_trace = [], []
            if debug_file.exists():
                for line in debug_file.read_text(encoding="utf-8").splitlines():
                    tag, pos, live = line.split()
                    entry = (int(pos), live == "1")
                    if tag == "P":
                        protect_trace.append(entry)
                    else:
                        process_trace.append(entry)
            # protect_link_destinations() runs once per PASS (WI-0093's
            # two-pass design), twice total for a single-line paragraph, both
            # deterministic and byte-identical — dedup preserving order
            # rather than asserting an exact count, so a genuine THIRD
            # distinct entry (a future architecture change) still shows up
            # instead of being silently averaged away.
            protect_trace = list(dict.fromkeys(protect_trace))
            process_trace = list(dict.fromkeys(process_trace))
            return protect_trace, process_trace

    def _assert_script_untouched(self, original):
        after = SCRIPT_PATH.read_text(encoding="utf-8")
        md5 = __import__("hashlib").md5
        self.assertEqual(
            md5(original.encode("utf-8")).hexdigest(),
            md5(after.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(after, original)

    _AGREEMENT_FIXTURES = [
        ("x](y [a](dead.md) z)", "the round's own false-negative repro (WI-0095)"),
        ("x\\](y [a](dead.md) z)", "the escaped sibling of the same repro"),
        ("[a] b](dead.md)", "an opener that already closed before this ]"),
        ("[](()", "a live opener/closer pair with no resolvable destination"),
        ("[[]](()", "two live openers, neither destination resolves"),
        ("[a](t.md)", "control: the ordinary, single, live case"),
        ("\\[a](t.md)", "control: an ESCAPED opener, agreement via is_escaped"),
        ("[a [b] c](t.md)", "a NESTED live opener at depth 2, not just depth 1"),
    ]

    def test_the_two_scans_agree_on_where_a_live_unescaped_opener_sits(self):
        original, instrumented = self._instrumented_script()
        try:
            for pattern, reason in self._AGREEMENT_FIXTURES:
                with self.subTest(pattern=pattern, reason=reason):
                    protect_trace, process_trace = self._traces_for(instrumented, pattern)
                    self.assertTrue(
                        protect_trace,
                        f"no `]` observed by protect_link_destinations() for "
                        f"{pattern!r} — fixture or instrumentation broke",
                    )
                    self.assertEqual(
                        protect_trace, process_trace,
                        f"the two scans disagree on live-opener position for "
                        f"{pattern!r} ({reason})",
                    )
        finally:
            self._assert_script_untouched(original)

    def test_a_deliberate_divergence_between_the_two_scans_is_caught(self):
        r"""Tightens ONLY protect_link_destinations()'s opening-bracket
        escape check to a naive one-byte lookbehind. `\\[x](t.md)` has an
        EVEN run of backslashes before the `[` — escape PARITY (what both
        functions actually implement) says the bracket is live; a one-byte
        lookbehind sees the immediate backslash and says escaped instead.
        protect_link_destinations() now disagrees with the untouched
        process_link_line(), which still finds the opener live — proving
        this module's agreement test can fail for the reason it claims to,
        not pass because it happens to check nothing discriminating."""
        original, instrumented = self._instrumented_script(extra_pairs=[
            ('                if (ch == "[" && !is_escaped(s, i)) {',
             '                if (ch == "[" && substr(s, i - 1, 1) != "\\\\") {'),
        ])
        try:
            protect_trace, process_trace = self._traces_for(instrumented, "\\\\[x](t.md)")
            self.assertNotEqual(
                protect_trace, process_trace,
                "the injected divergence did not flip the trace — this "
                "instrument cannot discriminate the two scans drifting apart",
            )
        finally:
            self._assert_script_untouched(original)


class DestinationEscapeAndEntityMutationTest(unittest.TestCase):
    """WI-0081 obligation: mutation-proof for the destination-normalisation
    fix (escaped closing paren + numeric-entity decode) — both live inside
    `protect_link_destinations()`, reverted here to its exact PRE-FIX shape
    (not a synthetic no-op) on an in-memory copy, same pattern as the
    mutation tests above. The shipped script on disk is never touched;
    proven by md5, not assumed.
    """

    _PRE_FIX_PROTECT_LINK_DESTINATIONS = (
        "        function protect_link_destinations(s,    out, dest) {\n"
        "            out = \"\"\n"
        "            while (match(s, /\\]\\([^)]*\\)/)) {\n"
        "                out = out substr(s, 1, RSTART + 1)   # up through and including the ]( pair\n"
        "                dest = substr(s, RSTART + 2, RLENGTH - 3)\n"
        "                out = out dest_mark dest dest_mark \")\"\n"
        "                s = substr(s, RSTART + RLENGTH)\n"
        "            }\n"
        "            return out s\n"
        "        }\n"
    )

    def test_reverting_protect_link_destinations_flips_the_wi_0081_fixtures_red(self):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        original_md5_before = __import__("hashlib").md5(original.encode("utf-8")).hexdigest()

        current_fn = re.compile(
            r"        function protect_link_destinations\(.*?\n        \}\n", re.S
        )
        match = current_fn.search(original)
        self.assertIsNotNone(
            match, "protect_link_destinations() not found — update this test's regex",
        )

        mutated = (
            original[: match.start()]
            + self._PRE_FIX_PROTECT_LINK_DESTINATIONS
            + original[match.end():]
        )
        self.assertNotEqual(mutated, original, "mutation did not change the script")

        with tempfile.TemporaryDirectory() as tmp:
            script_dir = Path(tmp) / "scriptdir"
            shutil.copytree(SCRIPT_PATH.parent / "lib", script_dir / "lib")
            mutant_script = script_dir / "memory-lint.sh"
            mutant_script.write_text(mutated, encoding="utf-8")

            project_dir = Path(tmp) / "project"
            (project_dir / "docs" / "memory").mkdir(parents=True)
            (project_dir / "docs" / "memory" / "MEMORY.md").write_text(
                "# Memory Index\n\n"
                "- [Esc](gone_mut_paren\\).md) — escaped paren\n"
                "- [Dec](gone_mut_dec&#35;3.md) — decimal entity\n",
                encoding="utf-8",
            )
            fake_home = Path(tmp) / "home"
            fake_home.mkdir()

            result = subprocess.run(
                ["bash", str(mutant_script), str(project_dir)],
                capture_output=True, text=True,
                env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            )

        # The pre-fix shape truncates the escaped-paren destination at the
        # first literal ")" and leaves the entity destination undecoded, then
        # separately truncated downstream at its own literal "#" byte.
        self.assertIn("gone_mut_paren\\", result.stdout)
        self.assertNotIn("gone_mut_paren).md", result.stdout)
        self.assertNotIn("gone_mut_dec#3.md", result.stdout)

        after = SCRIPT_PATH.read_text(encoding="utf-8")
        original_md5_after = __import__("hashlib").md5(after.encode("utf-8")).hexdigest()
        self.assertEqual(original_md5_before, original_md5_after)
        self.assertEqual(after, original)


class IndentedCodeAndHtmlBlockMutationTest(unittest.TestCase):
    """WI-0084 obligation: each of the three new block-boundary cases (indented
    code, HTML block type 1, HTML block type 6) must have been seen RED by
    mutation, not merely written and never falsified. Removes exactly one
    `if (...) { ... }` guard at a time from an in-memory COPY of the script,
    same pattern as the mutation tests above — the shipped script on disk is
    never touched; proven by md5, not assumed.
    """

    _INDENTED_CODE_GUARD = (
        "            if (pbuf_n == 0 && $0 !~ /^[ \\t]*$/ && $0 ~ /^(    |\\t)/) {\n"
        "                next\n"
        "            }\n"
    )
    _HTML_BLOCK1_OPENER = (
        "            if (match(tolower($0), /^[ ]{0,3}<(script|pre|style)([ \\t>]|$)/)) {\n"
        "                flush_paragraph()\n"
        "                in_html_block1 = 1\n"
        "                next\n"
        "            }\n"
    )
    _HTML_BLOCK6_OPENER = (
        "            if (match(tolower($0), /^[ ]{0,3}<[\\/]?(address|article|aside|base|"
        "basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|"
        "dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h1|head|header|hr|"
        "html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|"
        "param|section|source|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)"
        "([ \\t]|\\/?>|$)/)) {\n"
        "                flush_paragraph()\n"
        "                in_html_block6 = 1\n"
        "                next\n"
        "            }\n"
    )

    def _assert_guard_removal_flips_fixture_red(self, guard, markdown, expected_dead_target):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        original_md5_before = __import__("hashlib").md5(original.encode("utf-8")).hexdigest()

        self.assertIn(
            guard, original, "fixture line moved — update the mutation target for this test",
        )
        mutated = original.replace(guard, "", 1)
        self.assertNotEqual(mutated, original, "mutation did not change the script")

        with tempfile.TemporaryDirectory() as tmp:
            script_dir = Path(tmp) / "scriptdir"
            shutil.copytree(SCRIPT_PATH.parent / "lib", script_dir / "lib")
            mutant_script = script_dir / "memory-lint.sh"
            mutant_script.write_text(mutated, encoding="utf-8")

            project_dir = Path(tmp) / "project"
            (project_dir / "docs" / "memory").mkdir(parents=True)
            (project_dir / "docs" / "memory" / "MEMORY.md").write_text(
                "# Memory Index\n\n" + markdown, encoding="utf-8"
            )
            fake_home = Path(tmp) / "home"
            fake_home.mkdir()

            result = subprocess.run(
                ["bash", str(mutant_script), str(project_dir)],
                capture_output=True, text=True,
                env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            )

        self.assertIn(
            expected_dead_target, result.stdout,
            "mutation did not flip the fixture — this guard no longer "
            "discriminates WI-0084's defect",
        )

        after = SCRIPT_PATH.read_text(encoding="utf-8")
        original_md5_after = __import__("hashlib").md5(after.encode("utf-8")).hexdigest()
        self.assertEqual(original_md5_before, original_md5_after)
        self.assertEqual(after, original)

    def test_removing_the_indented_code_guard_flips_the_indented_fixture_red(self):
        self._assert_guard_removal_flips_fixture_red(
            self._INDENTED_CODE_GUARD,
            "before paragraph\n\n    [link](gone_mut_indent.md)\n\nafter paragraph\n",
            "gone_mut_indent.md",
        )

    def test_removing_the_html_block1_opener_flips_the_pre_fixture_red(self):
        self._assert_guard_removal_flips_fixture_red(
            self._HTML_BLOCK1_OPENER,
            "<pre>\n[link](gone_mut_pre.md)\n</pre>\n",
            "gone_mut_pre.md",
        )

    def test_removing_the_html_block6_opener_flips_the_div_fixture_red(self):
        self._assert_guard_removal_flips_fixture_red(
            self._HTML_BLOCK6_OPENER,
            "<div>\n[link](gone_mut_div.md)\n</div>\n",
            "gone_mut_div.md",
        )


class ParagraphBoundaryMutationTest(unittest.TestCase):
    """WI-0086/WI-0082 obligation: each new boundary must have been seen RED,
    and by a mutation that changes the awk block's STRUCTURE rather than merely
    deleting an assertion.

    Four of the five mutations here are deliberately NOT deletions: the
    branch-order mutation MOVES the thematic-break branch behind the list
    branch (both branches still present, both still reachable), the
    container-guard mutation WIDENS the setext gate to the naive `pbuf_n > 0`
    form the reference falsifies, the block-quote mutation RESTORES the guard
    to its exact pre-fix shape, and the thematic-break mutation ADDS a gate
    where the reference says there must be none. Only the CR strip is
    exercised by removal, because it is a single statement with no order or
    gate to permute.

    Note the two directions. Widening or removing a guard produces a FALSE
    POSITIVE (a link the reference does not render); narrowing one produces a
    FALSE NEGATIVE (a dead link that stops being reported). Check (n) is on
    its way from `warn` to `err` per ADR-0001, which makes the false-positive
    direction the blocking one — but both are covered here, because a boundary
    set can drift either way.

    Every run works on an in-memory COPY; the shipped script is never touched,
    proven by md5 rather than assumed.
    """

    _CR_STRIP = '            sub(/\\r$/, "")\n'
    _THEMATIC_BREAK_BRANCH = (
        "            if ($0 ~ /^[ ]{0,3}((\\*[ \\t]*){3,}|(-[ \\t]*){3,}|(_[ \\t]*){3,})$/) {\n"
        "                flush_paragraph()\n"
        "                next\n"
        "            }\n"
    )
    _LIST_MARKER_BRANCH = (
        "            if ($0 ~ /^[ ]{0,3}([-+*]|[0-9]{1,9}[.)])[ \\t]/) {\n"
        "                flush_paragraph()\n"
        "                append_paragraph($0)\n"
        "                next\n"
        "            }\n"
    )
    _GUARDED_SETEXT = (
        "            if (pbuf_n > 0 && pbuf_para && $0 ~ /^[ ]{0,3}(=+|-+)[ \\t]*$/) {\n"
    )
    _NAIVE_SETEXT = (
        "            if (pbuf_n > 0 && $0 ~ /^[ ]{0,3}(=+|-+)[ \\t]*$/) {\n"
    )
    # Current shape: pbuf_quote (WI-0089 follow-up) answers "is the buffer
    # currently an open quote", which pbuf_para alone could not — a list
    # item's paragraph also reads pbuf_para == 0, the same value as "already
    # continuing a quote", so the flush guard could not tell them apart.
    _CONTAINER_GUARD = (
        "            if ($0 ~ /^[ ]{0,3}>/) {\n"
        "                if (pbuf_n > 0 && !pbuf_quote) flush_paragraph()\n"
        "                pbuf_para = 0\n"
        "                pbuf_quote = 1\n"
        "            }\n"
        "            else if (pbuf_n == 0) pbuf_para = 1\n"
    )
    _CONTAINER_GUARD_PRE_FIX = (
        "            if (pbuf_n == 0) {\n"
        "                if ($0 ~ /^[ ]{0,3}>/) pbuf_para = 0\n"
        "                else pbuf_para = 1\n"
        "            }\n"
    )
    # WI-0089: the shape between the review round above and this fix — the
    # container guard already cleared pbuf_para on an interrupt (so the
    # setext branch stayed correctly gated), but never flushed the
    # paragraph buffer at the interrupt itself.
    _CONTAINER_GUARD_PRE_WI_0089 = (
        "            if ($0 ~ /^[ ]{0,3}>/) pbuf_para = 0\n"
        "            else if (pbuf_n == 0) pbuf_para = 1\n"
    )
    # The shape WI-0089 shipped and this round follows: the interrupt guard
    # reads pbuf_para (rather than pbuf_quote), and so cannot distinguish
    # "continuing an open quote" from "a list item paragraph is open" — both
    # read pbuf_para == 0. A `>` line following an open list item never
    # flushed, and a code span straddling that join hid a real link.
    _CONTAINER_GUARD_PRE_PBUF_QUOTE = (
        "            if ($0 ~ /^[ ]{0,3}>/) {\n"
        "                if (pbuf_n > 0 && pbuf_para) flush_paragraph()\n"
        "                pbuf_para = 0\n"
        "            }\n"
        "            else if (pbuf_n == 0) pbuf_para = 1\n"
    )
    _GATED_THEMATIC_BREAK = (
        "            if (pbuf_para && $0 ~ /^[ ]{0,3}((\\*[ \\t]*){3,}|(-[ \\t]*){3,}|(_[ \\t]*){3,})$/) {\n"
    )

    def _run_mutant(self, mutate, markdown):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        md5_before = hashlib.md5(original.encode("utf-8")).hexdigest()

        mutated = mutate(original)
        self.assertNotEqual(mutated, original, "mutation did not change the script")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                script_dir = Path(tmp) / "scriptdir"
                shutil.copytree(SCRIPT_PATH.parent / "lib", script_dir / "lib")
                mutant_script = script_dir / "memory-lint.sh"
                mutant_script.write_text(mutated, encoding="utf-8")

                project_dir = Path(tmp) / "project"
                (project_dir / "docs" / "memory").mkdir(parents=True)
                (project_dir / "docs" / "memory" / "MEMORY.md").write_text(
                    markdown, encoding="utf-8"
                )
                fake_home = Path(tmp) / "home"
                fake_home.mkdir()

                return subprocess.run(
                    ["bash", str(mutant_script), str(project_dir)],
                    capture_output=True, text=True,
                    env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
                )
        finally:
            after = SCRIPT_PATH.read_text(encoding="utf-8")
            self.assertEqual(hashlib.md5(after.encode("utf-8")).hexdigest(), md5_before)
            self.assertEqual(after, original)

    def test_removing_the_cr_strip_swallows_the_link_before_a_crlf_blank_line(self):
        def mutate(src):
            self.assertIn(self._CR_STRIP, src, "CR strip moved — update this mutation")
            return src.replace(self._CR_STRIP, "", 1)

        result = self._run_mutant(
            mutate,
            "# Memory Index\r\n\r\n"
            "`stray one [a](project_mut_crlf_one.md)\r\n\r\n"
            "`stray two [b](project_mut_crlf_two.md)\r\n",
        )

        self.assertNotIn("project_mut_crlf_one.md", result.stdout)
        self.assertIn("project_mut_crlf_two.md", result.stdout)

    def test_moving_the_thematic_break_behind_the_list_branch_buries_the_code_block(self):
        """Order mutation, not a deletion: both branches survive, only their
        sequence changes — and `- - -` is then claimed by the list branch,
        which buffers its own line and defeats the indented-code gate.
        """
        def mutate(src):
            self.assertIn(self._THEMATIC_BREAK_BRANCH, src)
            self.assertIn(self._LIST_MARKER_BRANCH, src)
            moved = src.replace(self._THEMATIC_BREAK_BRANCH, "", 1)
            return moved.replace(
                self._LIST_MARKER_BRANCH,
                self._LIST_MARKER_BRANCH + self._THEMATIC_BREAK_BRANCH,
                1,
            )

        result = self._run_mutant(
            mutate,
            "# Memory Index\n\n- - -\n    [buried](project_mut_prec.md)\n",
        )

        self.assertIn(
            "project_mut_prec.md", result.stdout,
            "the branch order no longer discriminates — reordering must be visible",
        )

    def test_widening_the_setext_gate_reports_a_link_inside_a_list_item(self):
        """Gate mutation: the guard is replaced by the naive `pbuf_n > 0` form,
        which the reference falsifies (`===` under a list item is lazy
        continuation, not an underline).
        """
        def mutate(src):
            self.assertIn(self._GUARDED_SETEXT, src)
            return src.replace(self._GUARDED_SETEXT, self._NAIVE_SETEXT, 1)

        result = self._run_mutant(
            mutate,
            "# Memory Index\n\n"
            "- `item [a](project_mut_li.md)\n===\ncloser` [b](project_mut_li2.md)\n",
        )

        self.assertIn(
            "project_mut_li.md", result.stdout,
            "the container guard no longer discriminates — the naive gate must "
            "produce the false positive it was added to prevent",
        )

    def test_restoring_the_pre_fix_container_guard_reports_a_link_inside_a_block_quote(self):
        """Pre-form restoration, not a deletion: the guard goes back to the
        exact shape it had before the fix, where the block-quote test was
        nested inside `pbuf_n == 0` and therefore only ran for a quote that
        OPENED the buffer. A quote interrupting an open paragraph then kept
        pbuf_para set, the setext branch fired inside the quote, and the link
        buried in the code span was reported — a false positive on a shape
        that was correct before the boundary existed.
        """
        def mutate(src):
            self.assertIn(self._CONTAINER_GUARD, src)
            return src.replace(
                self._CONTAINER_GUARD, self._CONTAINER_GUARD_PRE_FIX, 1
            )

        result = self._run_mutant(
            mutate,
            "# Memory Index\n\n"
            "foo\n> `q [a](project_mut_bqmid.md)\n===\ncloser` [b](project_mut_bqmid2.md)\n",
        )

        self.assertIn(
            "project_mut_bqmid.md", result.stdout,
            "the mid-paragraph block quote no longer discriminates — the "
            "pre-fix guard must produce the false positive it was fixed for",
        )

    def test_restoring_the_pre_wi_0089_container_guard_hides_a_link_across_the_block_quote_boundary(self):
        """WI-0089's own pre-fix restoration: the guard goes back to its
        EXACT previous form, where a `>` line correctly cleared pbuf_para on
        an interrupt but never flushed the paragraph buffer there — so the
        quote line was still appended into the SAME buffer as the paragraph
        above it, and a code span straddling the join could pair across two
        blocks CommonMark keeps separate.
        """
        def mutate(src):
            self.assertIn(self._CONTAINER_GUARD, src)
            return src.replace(
                self._CONTAINER_GUARD, self._CONTAINER_GUARD_PRE_WI_0089, 1
            )

        result = self._run_mutant(
            mutate,
            "# Memory Index\n\n"
            "foo `x\n> bar [a](project_mut_bqint.md) y` [b](project_mut_bqint2.md)\n",
        )

        self.assertNotIn(
            "project_mut_bqint.md", result.stdout,
            "the block-quote interrupt no longer discriminates — the "
            "pre-WI-0089 guard must reproduce the false negative it was "
            "fixed for",
        )
        self.assertIn("project_mut_bqint2.md", result.stdout)

    def test_restoring_the_pre_pbuf_quote_container_guard_hides_a_link_across_a_list_item_boundary(self):
        """This round's own pre-fix restoration: the guard goes back to its
        EXACT immediately-previous form (the shape WI-0089 shipped), which
        reads pbuf_para for the flush decision. pbuf_para cannot distinguish
        "continuing an open quote" from "a list item paragraph is open" —
        both read pbuf_para == 0 — so a `>` line following an open list item
        never flushed, and a code span straddling that join hid a real link,
        exactly the false negative WI-0089 closed one container over.
        """
        def mutate(src):
            self.assertIn(self._CONTAINER_GUARD, src)
            return src.replace(
                self._CONTAINER_GUARD, self._CONTAINER_GUARD_PRE_PBUF_QUOTE, 1
            )

        result = self._run_mutant(
            mutate,
            "# Memory Index\n\n"
            "- foo `x\n> bar [a](project_mut_liq.md) y` [b](project_mut_liq2.md)\n",
        )

        self.assertNotIn(
            "project_mut_liq.md", result.stdout,
            "the list-item block-quote interrupt no longer discriminates — "
            "the pre-pbuf_quote guard must reproduce the false negative it "
            "was fixed for",
        )
        self.assertIn("project_mut_liq2.md", result.stdout)

    def test_gating_the_thematic_break_hides_a_link_in_the_list_item_above_it(self):
        """The opposite direction from the guard mutations above: this one ADDS
        a gate rather than widening one, and its symptom is a false NEGATIVE.

        Nothing else in the suite pins the thematic-break branch as UNGATED —
        adding `pbuf_para &&` to it left the whole suite green before this test
        existed. It must not be gated: unlike `===`, a `---` line is not lazy
        continuation inside a list item (measured, `<ul><li>…</li></ul><hr />`),
        so gating it keeps the item paragraph buffered, pairs the two backticks
        across the break and swallows the first link entirely.
        """
        def mutate(src):
            self.assertIn(self._THEMATIC_BREAK_BRANCH, src)
            return src.replace(
                self._THEMATIC_BREAK_BRANCH,
                self._GATED_THEMATIC_BREAK
                + self._THEMATIC_BREAK_BRANCH.split("\n", 1)[1],
                1,
            )

        result = self._run_mutant(
            mutate,
            "# Memory Index\n\n"
            "- `item [a](project_mut_tbli.md)\n---\ncloser` [b](project_mut_tbli2.md)\n",
        )

        self.assertNotIn(
            "project_mut_tbli.md", result.stdout,
            "the thematic-break branch no longer discriminates — gating it must "
            "hide the link the ungated branch exposes",
        )
        self.assertIn("project_mut_tbli2.md", result.stdout)


class NamedEntityInfoMutationTest(unittest.TestCase):
    """WI-0081 (remainder) obligation: the info-not-dead-link reclassification
    must have been seen RED by mutation, not merely written and never
    falsified. Removes the named-entity guard from an in-memory COPY of the
    script, same pattern as the mutation tests above — the shipped script on
    disk is never touched; proven by md5, not assumed.
    """

    _NAMED_ENTITY_GUARD = (
        "        if [[ \"$target\" =~ \\&[a-zA-Z][a-zA-Z0-9]*\\; ]]; then\n"
        "            info \"$index_rel — link target '$target' contains an unresolved named HTML entity reference and could not be checked\"\n"
        "            continue\n"
        "        fi\n"
    )

    def test_removing_the_named_entity_guard_flips_the_fixture_back_to_a_dead_claim(self):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        original_md5_before = __import__("hashlib").md5(original.encode("utf-8")).hexdigest()

        self.assertIn(
            self._NAMED_ENTITY_GUARD, original,
            "fixture line moved — update the mutation target for this test",
        )
        mutated = original.replace(self._NAMED_ENTITY_GUARD, "", 1)
        self.assertNotEqual(mutated, original, "mutation did not change the script")

        with tempfile.TemporaryDirectory() as tmp:
            script_dir = Path(tmp) / "scriptdir"
            shutil.copytree(SCRIPT_PATH.parent / "lib", script_dir / "lib")
            mutant_script = script_dir / "memory-lint.sh"
            mutant_script.write_text(mutated, encoding="utf-8")

            project_dir = Path(tmp) / "project"
            (project_dir / "docs" / "memory").mkdir(parents=True)
            (project_dir / "docs" / "memory" / "MEMORY.md").write_text(
                "# Memory Index\n\n- [Named](gone_mut_named&num;3.md) — dead\n",
                encoding="utf-8",
            )
            fake_home = Path(tmp) / "home"
            fake_home.mkdir()

            result = subprocess.run(
                ["bash", str(mutant_script), str(project_dir)],
                capture_output=True, text=True,
                env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            )

        self.assertIn(
            "gone_mut_named&num;3.md", result.stdout,
            "mutation did not flip the fixture — the named-entity guard no "
            "longer discriminates WI-0081's (remainder) defect",
        )
        self.assertIn(
            "does not exist", result.stdout,
            "mutation should restore the pre-fix dead-link CLAIM, not just any finding",
        )

        after = SCRIPT_PATH.read_text(encoding="utf-8")
        original_md5_after = __import__("hashlib").md5(after.encode("utf-8")).hexdigest()
        self.assertEqual(original_md5_before, original_md5_after)
        self.assertEqual(after, original)


# --------------------------------------------------------------------------- #
# WI-0087 — the reported age must be a property of the FILE, not of the CLOCK
# --------------------------------------------------------------------------- #

# The date group is non-greedy rather than \S+: a last_updated may legally carry
# trailing text ("20.08.2026 (WI-0015)"), and a whitespace-free group silently
# stops matching those findings — reporting "no warning" for a file that warned.
AGE_FINDING_RE = re.compile(
    r"^(?P<rel>\S+) — last_updated=(?P<date>.+?) is (?P<age>\d+) days old"
)


class StaleAgeIsAPropertyOfTheFileTest(unittest.TestCase):
    """Check (e) must report an age that depends only on `last_updated` (WI-0087).

    Before this, `date_to_epoch()` parsed a DD.MM.YYYY value with a BSD format
    string carrying no time component, and BSD `date` fills unnamed fields from
    the RUNNING WALL CLOCK. `TODAY_EPOCH` is captured once at script start, so
    the two sides of the subtraction carried different times of day and the gap
    between them was the script's own elapsed runtime. With integer truncation
    that lands one day low: a genuinely 91-day-old file reported 90 and, at
    `STALE_DAYS=90`, did not warn at all — a silent false negative at exactly
    the threshold this check exists to guard.

    Why this fixture is LARGE, and why that is the point. The defect is only
    visible once the wall clock has ticked past a full second between the
    capture of "today" and the parse of the file's date. On a three-file store
    the whole run fits inside that second most of the time, so the buggy code
    reported the true age and a test built on such a store would have been green
    against the very defect it was written for — a test that cannot fail. The
    store below takes roughly two seconds to walk (~30 ms per file, measured),
    so all but the handful of files reached in the script's first second show
    the old behaviour. Measured against the unfixed script: 58 of 60 files that
    were 91 days old did not warn at all.

    That sizing is a mutation-killing property, not a correctness property: with
    the fix in place every assertion below holds for a one-file store just as
    well. A machine fast enough to lint the whole fixture inside one second
    would weaken the red step, not falsify the green one.

    Two cohorts, because silence hides disagreement. Files at STALE_DAYS+1 carry
    the false-negative question, but a file the old code pushed BELOW the
    threshold drops out of the report entirely and can no longer be compared
    with its twins. The second cohort sits far above the threshold, where both
    the true and the truncated age still warn, so a store disagreeing with
    itself shows up as two different numbers rather than as absence.

    No test seam. The script's notion of "today" is never overridden — the
    fixture dates are derived from the same calendar day the script reads from
    the system clock, so there is nothing here that a field run could reach.

    File order is deliberately not assumed: memory-lint.sh collects files with
    `find` and does not sort, so which file is reached late is up to the
    filesystem. Every file in each cohort therefore carries the cohort's date,
    which makes "some file is parsed late" enough and "a specific file is parsed
    late" unnecessary.
    """

    # ~30 ms per file on the reference machine → the fixture takes ~2 s to walk.
    # See the class docstring.
    FILES_PER_COHORT = 30

    # Mirrors STALE_DAYS in memory-lint.sh. The interesting ages are derived from
    # it rather than written out, so the test states the RELATION the check
    # implements ("older than", exclusive) instead of magic numbers.
    STALE_DAYS = 90

    # Far enough above the threshold that an age truncated by one day still
    # warns — see "Two cohorts" in the class docstring.
    OLD_COHORT_DAYS = 200

    @classmethod
    def setUpClass(cls):
        cls.today = date.today()
        cls.threshold_days = cls.STALE_DAYS + 1
        cls.threshold_date = (cls.today - timedelta(days=cls.threshold_days)).strftime("%d.%m.%Y")
        cls.old_date = (cls.today - timedelta(days=cls.OLD_COHORT_DAYS)).strftime("%d.%m.%Y")
        cls.boundary_date = (cls.today - timedelta(days=cls.STALE_DAYS)).strftime("%d.%m.%Y")

        cls.tmp = tempfile.mkdtemp(prefix="ccpr-memory-lint-age-")
        project_dir = Path(cls.tmp) / "project"
        memory_dir = project_dir / "docs" / "memory"
        memory_dir.mkdir(parents=True)

        for index in range(cls.FILES_PER_COHORT):
            (memory_dir / f"project_threshold{index:04d}.md").write_text(
                tier1_text(name=f"threshold probe {index}", last_updated=cls.threshold_date),
                encoding="utf-8",
            )
            (memory_dir / f"project_old{index:04d}.md").write_text(
                tier1_text(name=f"old probe {index}", last_updated=cls.old_date),
                encoding="utf-8",
            )
        (memory_dir / "project_boundary.md").write_text(
            tier1_text(name="boundary probe", last_updated=cls.boundary_date),
            encoding="utf-8",
        )
        (memory_dir / "project_annotated.md").write_text(
            tier1_text(
                name="annotated probe",
                last_updated=f"{cls.threshold_date} (WI-0000 a trailing note)",
            ),
            encoding="utf-8",
        )
        (memory_dir / "MEMORY.md").write_text("# Memory Index\n\nNo entries.\n", encoding="utf-8")

        fake_home = Path(cls.tmp) / "home"
        fake_home.mkdir()
        env = {"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}

        # Two runs, back to back, over an unchanged store: the cross-run half of
        # the guarantee. Cached here rather than re-run per test method — the
        # fixture is deliberately expensive and none of the assertions below
        # need a fresh one.
        cls.runs = []
        for _ in range(2):
            result = subprocess.run(
                ["bash", str(SCRIPT_PATH), str(project_dir)],
                capture_output=True, text=True, env=env,
            )
            for heading in ("## Errors (", "## Warnings (", "## Info ("):
                assert heading in result.stdout, (
                    f"memory-lint.sh produced no report (missing {heading!r}) — "
                    f"returncode={result.returncode}, stderr={result.stderr!r}"
                )
            cls.runs.append(result)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def ages(cls, result, prefix):
        """{relative path: reported age} over one cohort's check-(e) findings."""
        found = {}
        for warning in MemoryLintTest.findings(result.stdout, "Warnings"):
            match = AGE_FINDING_RE.match(warning)
            if match and match.group("rel").startswith(f"docs/memory/project_{prefix}"):
                found[match.group("rel")] = int(match.group("age"))
        return found

    def test_a_file_one_day_past_the_threshold_warns(self):
        """The headline false negative: at STALE_DAYS+1 the warning must fire.

        Under the old arithmetic the age truncated down to STALE_DAYS, the `>`
        comparison was false, and the file the check exists for stayed silent.
        """
        ages = self.ages(self.runs[0], "threshold")
        self.assertEqual(
            len(ages), self.FILES_PER_COHORT,
            f"expected all {self.FILES_PER_COHORT} files at {self.threshold_days} "
            f"days old to warn, got {len(ages)}",
        )

    def test_the_reported_age_is_the_true_age(self):
        """A concrete number, not merely a warning — the assertion the suite
        never carried, and the reason the defect could survive."""
        for prefix, expected in (
            ("threshold", self.threshold_days),
            ("old", self.OLD_COHORT_DAYS),
        ):
            with self.subTest(cohort=prefix):
                ages = self.ages(self.runs[0], prefix)
                self.assertTrue(ages, f"no age findings for cohort {prefix!r}")
                self.assertEqual(
                    sorted(set(ages.values())), [expected],
                    f"every file in cohort {prefix!r} is exactly {expected} days "
                    f"before {self.today.strftime('%d.%m.%Y')}; reported "
                    f"{sorted(set(ages.values()))}",
                )

    def test_files_sharing_a_date_report_the_same_age_within_one_run(self):
        """The defect's own signature: the same store disagreeing with itself.

        The old code made the reported age depend on WHEN IN THE RUN the file
        was reached, so the files parsed in the script's first second read one
        day older than the rest.
        """
        ages = self.ages(self.runs[0], "old")
        distinct = sorted(set(ages.values()))
        self.assertEqual(
            len(distinct), 1,
            f"files with an identical last_updated reported different ages "
            f"({distinct}) — the age is tracking the clock, not the file",
        )

    def test_the_same_store_twice_reports_the_same_ages(self):
        """The core guarantee: same inventory, two runs, same numbers."""
        for prefix in ("threshold", "old"):
            with self.subTest(cohort=prefix):
                first = self.ages(self.runs[0], prefix)
                second = self.ages(self.runs[1], prefix)
                self.assertTrue(first, f"no age findings for cohort {prefix!r}")
                self.assertEqual(first, second)

    def test_a_date_with_a_trailing_note_still_reads_as_that_date(self):
        """What the fix must NOT change (WI-0106).

        Both `date` implementations accept text after the value they matched, so
        `last_updated: 20.08.2026 (WI-0015)` has always been read as 20.08.2026 —
        and ten files across the live stores are written that way. Anchoring the
        BSD branch by appending a time to the value would have turned every one
        of them into a hard parse error and moved this script from exit 1 to
        exit 2 on its own repository. Measured, which is how it was caught: that
        variant produced 10 new errors across the four inventories.

        This pins the tolerance as it stands, not as it ought to be — whether
        the loose form should stay legal is a schema question, filed separately.
        """
        ages = self.ages(self.runs[0], "annotated")
        self.assertEqual(
            ages,
            {"docs/memory/project_annotated.md": self.threshold_days},
            "a last_updated with a trailing note must still be read as its date, "
            "at the same age as the bare form",
        )

    def test_a_file_exactly_at_the_threshold_stays_silent(self):
        """The other side of the boundary: `>` is exclusive, so STALE_DAYS is not
        yet stale. Pinned alongside the fix because moving both sides of the
        subtraction to a common anchor moves this edge by a full day — without
        it, a fix that over-corrected by one would look just as green."""
        ages = self.ages(self.runs[0], "boundary")
        self.assertEqual(
            ages, {},
            f"a file exactly {self.STALE_DAYS} days old must not warn",
        )


class TodayIsTheLocalCalendarDayTest(unittest.TestCase):
    """`TODAY_EPOCH` must be the local calendar day, anchored like every other
    date this script compares against it (WI-0087).

    This is the half of the fix the large fixture above cannot see. Once each
    file's date is anchored at UTC midnight, leaving `TODAY_EPOCH` as a raw
    `date +%s` still produces a stable, plausible-looking number: the leftover
    time-of-day sits on one side only and truncates away — as long as the run
    happens while the local calendar day and the UTC one agree. Between local
    midnight and the zone's UTC offset they do not, and the age comes out a day
    short again. A suite that runs at 20:07 in a UTC+2 zone never sees it, which
    is exactly how such a defect survives.

    Rather than wait for a run at 01:00, the test moves the disagreement into
    view: `TZ` is a plain POSIX environment variable, so the run can be placed in
    a zone whose calendar day differs from UTC's right now. That is not a seam in
    the script — nothing was added to it to make this testable, and the variable
    means the same thing here as it does in the field. The zone is picked from
    the current UTC hour so that one of the two always disagrees, and the
    disagreement itself is asserted before anything else, so the test cannot
    quietly stop testing what it claims to.

    Deliberately a small fixture: the question here is which CALENDAR DAY the
    script calls today, not how far into the run a file is reached.
    """

    @staticmethod
    def _shifted_zone():
        """A zone whose calendar day currently differs from UTC's.

        UTC+14 runs ahead of UTC's date from 10:00 UTC onward, UTC-12 runs behind
        it until 12:00 UTC — so at every instant at least one of the two differs,
        and the 12:00 split stays clear of both edges.
        """
        utc_now = datetime.now(timezone.utc)
        return "Etc/GMT-14" if utc_now.hour >= 12 else "Etc/GMT+12"

    def test_the_age_counts_local_calendar_days(self):
        zone_name = self._shifted_zone()
        zone = ZoneInfo(zone_name)
        utc_now = datetime.now(timezone.utc)
        local_today = utc_now.astimezone(zone).date()

        self.assertNotEqual(
            local_today, utc_now.date(),
            f"{zone_name} was chosen because its calendar day differs from UTC's "
            f"right now; it does not, so this test would prove nothing",
        )

        stale_days = 90
        aged = (local_today - timedelta(days=stale_days + 1)).strftime("%d.%m.%Y")
        fresh = (local_today - timedelta(days=stale_days)).strftime("%d.%m.%Y")

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "project"
            memory_dir = project_dir / "docs" / "memory"
            memory_dir.mkdir(parents=True)
            (memory_dir / "project_aged.md").write_text(
                tier1_text(name="aged probe", last_updated=aged), encoding="utf-8"
            )
            (memory_dir / "project_fresh.md").write_text(
                tier1_text(name="fresh probe", last_updated=fresh), encoding="utf-8"
            )
            (memory_dir / "MEMORY.md").write_text(
                "# Memory Index\n\nNo entries.\n", encoding="utf-8"
            )
            fake_home = Path(tmp) / "home"
            fake_home.mkdir()

            result = subprocess.run(
                ["bash", str(SCRIPT_PATH), str(project_dir)],
                capture_output=True, text=True,
                env={
                    "HOME": str(fake_home),
                    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                    "TZ": zone_name,
                },
            )

        ages = {}
        for warning in MemoryLintTest.findings(result.stdout, "Warnings"):
            match = AGE_FINDING_RE.match(warning)
            if match:
                ages[match.group("rel")] = int(match.group("age"))

        self.assertEqual(
            ages, {"docs/memory/project_aged.md": stale_days + 1},
            f"in {zone_name} today is {local_today}; a file dated {aged} is "
            f"{stale_days + 1} days old and one dated {fresh} is not yet stale. "
            f"stdout={result.stdout!r}",
        )


# --------------------------------------------------------------------------- #
# WI-0106 — the FORM of last_updated, not just whether a date can be read from it
# --------------------------------------------------------------------------- #


class LastUpdatedFormTest(unittest.TestCase):
    """Check (e) must accept exactly the form MEMORY_SCHEMA.md specifies (WI-0106).

    The schema says `DD.MM.YYYY`, optionally followed by a parenthesised note --
    the form ten files in this repo's own store already use, and the form
    PHASE_DOC_SCHEMA.md has spelled out for phase documents all along. Before
    this, check (e) never asked that question: it handed the raw value to
    `date_to_epoch()` and treated "a date came back" as the whole contract. Both
    `date` implementations accept trailing text after the value they matched, so
    the tolerance was real but accidental -- and it was wider than the schema in
    one direction and narrower in another. Measured on 25.08.2026, same values
    through both linters:

        `24.08.2026 a note without parentheses`  memory: accepted  phase: REJECTED
        `24.08.2026(WI-0102)` (no space)         memory: accepted  phase: REJECTED
        `24.08.2026 (unclosed`                   memory: accepted  phase: REJECTED
        `99.99.9999` / `32.13.2026`              memory: REJECTED  phase: accepted

    This class closes the first three -- one rule, one answer -- and leaves the
    fourth as it stands: tightening phase-docs-lint.sh to reject a
    well-formed-but-impossible date rejects content it accepts today, which is a
    separate decision from writing down the tolerance that already exists.

    The date branch is deliberately still exercised (`impossible_day` below): a
    form check alone would let `32.13.2026` through, so that case is what keeps
    the pattern an ADDITION to the parse rather than a replacement for it.

    What this suite kills, and what it does not -- measured against mutants of
    the check, not argued from the source:

        drop the optional `( ... )` group from the pattern   red (3 subtests)
        drop the pattern's trailing `$`                      red (3 subtests)
        `[[:space:]]+` -> `[[:space:]]*` before the `(`      red (1 subtest)
        neuter the date parse's error branch                 red (1 subtest)
        swap the two branches (parse first, form second)     GREEN
        drop the pattern's leading `^`                       GREEN

    The last two survive on purpose, and saying so is the point. Both change
    only the DIAGNOSIS, never the verdict: a malformed value is rejected either
    way, and `^` is redundant here because anything in front of the date already
    fails the parse. (`leading_text` below is kept anyway -- it pins that such a
    value IS rejected, which is a property worth holding even though it does not
    single out the anchor.) In phase-docs-lint.sh, where no parse follows the
    pattern, that anchor is load-bearing; here it is parity, not protection.

    One store, one run: the cases differ only in the value under test, and none
    of them needs a fixture of its own.
    """

    # (slug, value, must_be_rejected)
    CASES = (
        ("plain", TODAY, False),
        ("annotated", f"{TODAY} (WI-0000)", False),
        ("annotated_prose", f"{TODAY} (Note: verified later the same day)", False),
        ("annotated_commas", f"{TODAY} (WI-0096/WI-0099, WI-0101)", False),
        ("word_salad", "banana", True),
        ("iso", "2026-08-24", True),
        ("note_without_parens", f"{TODAY} a trailing note", True),
        ("note_unclosed", f"{TODAY} (unclosed", True),
        ("note_without_space", f"{TODAY}(WI-0000)", True),
        ("leading_text", f"updated {TODAY}", True),
        ("impossible_day", "32.13.2026", True),
    )

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ccpr-memory-lint-form-")
        cls.addClassCleanup(shutil.rmtree, cls.tmp, ignore_errors=True)
        project_dir = Path(cls.tmp) / "project"
        memory_dir = project_dir / "docs" / "memory"
        memory_dir.mkdir(parents=True)

        for slug, value, _ in cls.CASES:
            (memory_dir / f"project_{slug}.md").write_text(
                tier1_text(name=f"{slug} probe", last_updated=value),
                encoding="utf-8",
            )
        (memory_dir / "MEMORY.md").write_text("# Memory Index\n\nNo entries.\n", encoding="utf-8")

        fake_home = Path(cls.tmp) / "home"
        fake_home.mkdir()
        cls.result = subprocess.run(
            ["bash", str(SCRIPT_PATH), str(project_dir)],
            capture_output=True, text=True,
            env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        )
        for heading in ("## Errors (", "## Warnings (", "## Info ("):
            assert heading in cls.result.stdout, (
                f"memory-lint.sh produced no report (missing {heading!r}) — "
                f"returncode={cls.result.returncode}, stderr={cls.result.stderr!r}"
            )

    @classmethod
    def rejected(cls, slug):
        """True iff check (e) filed an error against this probe's last_updated.

        Reads the Errors section only: the age warning also names `last_updated`
        and would make every old-enough file look rejected.
        """
        marker = f"project_{slug}.md"
        return any(
            marker in line and "last_updated" in line
            for line in MemoryLintTest.findings(cls.result.stdout, "Errors")
        )

    def test_the_schema_form_and_its_optional_note_are_accepted(self):
        for slug, value, must_be_rejected in self.CASES:
            if must_be_rejected:
                continue
            with self.subTest(value=value):
                self.assertFalse(
                    self.rejected(slug),
                    f"{value!r} is the form MEMORY_SCHEMA.md specifies and must pass — "
                    f"errors: {MemoryLintTest.findings(self.result.stdout, 'Errors')}",
                )

    def test_a_value_outside_the_schema_form_is_rejected(self):
        for slug, value, must_be_rejected in self.CASES:
            if not must_be_rejected:
                continue
            with self.subTest(value=value):
                self.assertTrue(
                    self.rejected(slug),
                    f"{value!r} is not 'DD.MM.YYYY' with an optional ' (note)' and "
                    f"must be rejected — errors: "
                    f"{MemoryLintTest.findings(self.result.stdout, 'Errors')}",
                )

    def test_a_rejected_value_makes_the_run_fail(self):
        """The verdict, separately from the findings (G-127): a finding that does
        not reach the exit code is a report nobody's gate reads."""
        self.assertEqual(
            self.result.returncode, 2,
            f"a store carrying malformed last_updated values must exit 2, got "
            f"{self.result.returncode}",
        )


# --------------------------------------------------------------------------- #
# WI-0111 — the decay-hint's grace-period NUMBER, not just its presence
# --------------------------------------------------------------------------- #


class DecayHintGracePeriodTest(MemoryLintFixture, unittest.TestCase):
    """Check (k)'s low-confidence hint must quote the DECAY policy's 30 days, not
    check (e)'s unrelated STALE_DAYS=90 (WI-0111).

    Both hint sites resolve `${STALE_DAYS:-30}` — a fallback that never fires
    because `STALE_DAYS` is assigned unconditionally at the top of the script
    for a different check (the memory-FILE staleness warning, check (e)). The
    hint therefore reads "90d" where the decay policy documented in
    instincts.md says "30 days without re-confirmation". A test that only
    checks the hint fires (as the previous, absent coverage would have) passes
    against the unfixed script — it has to pin the NUMBER to mean anything.

    Two sites, two layouts, deliberately both covered: line 478 fires when
    ~/.claude/instincts/*.md exists (split layout), line 480 when only
    ~/.claude/instincts.md exists (flat layout) — they sit in different
    branches of the same `if` and neither is a fallback for the other.
    """

    LOW_CONFIDENCE_ENTRY = "**Confidence: 0.4**\n"

    def test_flat_layout_hint_quotes_the_30_day_decay_policy(self):
        """Only ~/.claude/instincts.md exists — no instincts/ topic dir (else
        branch, line 480)."""
        claude_dir = self.fake_home / ".claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "instincts.md").write_text(self.LOW_CONFIDENCE_ENTRY, encoding="utf-8")

        result = self.run_lint()

        infos = self.findings(result.stdout, "Info")
        matches = [i for i in infos if "review candidates if older than" in i]
        self.assertTrue(
            matches, f"expected a decay-hint Info line, got: {infos!r}"
        )
        self.assertTrue(
            any("older than 30d" in i for i in matches),
            f"decay hint must quote the 30-day decay policy (instincts.md "
            f"'Decay policy': '30 days without re-confirmation'), not "
            f"check (e)'s unrelated STALE_DAYS — got: {matches!r}",
        )

    def test_split_layout_hint_quotes_the_30_day_decay_policy(self):
        """~/.claude/instincts.md AND ~/.claude/instincts/*.md both exist (if
        branch, line 478)."""
        claude_dir = self.fake_home / ".claude"
        topic_dir = claude_dir / "instincts"
        topic_dir.mkdir(parents=True)
        (claude_dir / "instincts.md").write_text("# index\n", encoding="utf-8")
        (topic_dir / "agents.md").write_text(self.LOW_CONFIDENCE_ENTRY, encoding="utf-8")

        result = self.run_lint()

        infos = self.findings(result.stdout, "Info")
        matches = [i for i in infos if "review candidates if older than" in i]
        self.assertTrue(
            matches, f"expected a decay-hint Info line, got: {infos!r}"
        )
        self.assertTrue(
            any("older than 30d" in i for i in matches),
            f"decay hint must quote the 30-day decay policy, not check (e)'s "
            f"unrelated STALE_DAYS — got: {matches!r}",
        )


class NoScopeReportedForCheckAllTest(MemoryLintFixture, unittest.TestCase):
    """memory-lint.sh reads from four independent targets: <project-dir>/
    docs/memory, ~/.claude/instincts.md, ~/.claude/instincts/, and
    ~/.claude/memory/. A CI runner reproduces every run against an empty
    $HOME and a checkout that never ships docs/memory/ (it is working
    state, gitignored, not a shipped artifact) -- all four absent at once.
    memory-lint.sh still exits 0 there (nothing to warn or error about), so
    check-all.sh needs a report substring, not the exit code, to tell that
    apart from "ran and found nothing" (WI-0129 Paket B, cycle B1).

    The counter-proof matters as much as the positive case: a fix that
    unconditionally reports "0 of 4 present" regardless of what actually
    exists would make BOTH tests below pass if only the no-scope shape were
    tested. `test_a_present_target_is_reported_and_the_run_is_normal`
    exercises the opposite input (a real, non-empty target) and pins that
    the run is NOT reported as no-scope.
    """

    def test_all_four_targets_absent_is_reported_as_no_scope(self):
        empty_project_dir = Path(tempfile.mkdtemp(prefix="ccpr-memory-lint-no-scope-"))
        self.addCleanup(shutil.rmtree, empty_project_dir, ignore_errors=True)
        # fake_home (MemoryLintFixture.setUp) is a fresh, empty tmpdir: no
        # .claude/instincts.md, no .claude/instincts/, no .claude/memory/.

        result = self.run_lint(project_dir=empty_project_dir)

        self.assertIn("**Targets:** 0 of 4 present", result.stdout, result.stdout)
        self.assertIn("the memory-lint check DID NOT RUN", result.stdout, result.stdout)
        # Still exit 0 — an absent scope produces no error or warning of its
        # own; check-all.sh, not this script's own exit code, is what turns
        # this into "could-not-run".
        self.assertEqual(0, result.returncode, result.stdout)

    def test_a_present_target_is_reported_and_the_run_is_normal(self):
        # self.project_dir (MemoryLintFixture.setUp) already ships a real
        # docs/memory/ with content — one of the four targets is present,
        # so this must NOT read as no-scope, regardless of the other three.
        result = self.run_lint()

        self.assertNotIn("**Targets:** 0 of 4 present", result.stdout, result.stdout)
        self.assertNotIn("the memory-lint check DID NOT RUN", result.stdout, result.stdout)
        self.assertIn("**Targets:**", result.stdout, result.stdout)

    def test_only_a_global_target_present_is_also_a_normal_run(self):
        # The reverse split: project-local docs/memory absent, but a global
        # target present (the ordinary shape of running CCPR against a
        # foreign project from a machine with a real ~/.claude). This must
        # run normally too -- "could-not-run" is reserved for ALL FOUR
        # targets missing, not merely the project-local one.
        empty_project_dir = Path(tempfile.mkdtemp(prefix="ccpr-memory-lint-global-only-"))
        self.addCleanup(shutil.rmtree, empty_project_dir, ignore_errors=True)
        claude_dir = self.fake_home / ".claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "instincts.md").write_text("# index\n", encoding="utf-8")

        result = self.run_lint(project_dir=empty_project_dir)

        # Positive liveness proof, not just the two negatives below: exactly
        # ONE of the four targets is present here (~/.claude/instincts.md),
        # so the report must name that count precisely -- a script that
        # unconditionally reported "not no-scope" for any input would pass
        # the two assertNotIn calls alone without ever having counted
        # anything.
        self.assertIn("**Targets:** 1 of 4 present", result.stdout, result.stdout)
        self.assertNotIn("**Targets:** 0 of 4 present", result.stdout, result.stdout)
        self.assertNotIn("the memory-lint check DID NOT RUN", result.stdout, result.stdout)


class IndexFrontmatterOptionalTest(MemoryLintFixture, unittest.TestCase):
    """docs/memory/MEMORY.md and docs/memory/{agent}/MEMORY.md carry frontmatter only
    when someone chose to write it (WI-0108). Before this fix, memory-lint.sh excluded
    every MEMORY.md from checks (a)-(f) by filename — the stated reason ("indexes have
    no frontmatter") was false for 16 of 27 index files measured across four reference
    stores, and none of the 16 had ever been validated.

    The rule is not "always required" (that would turn all 11 frontmatter-less indexes
    from that same census into immediate errors) and not "never allowed" (that discards
    information written on purpose) — frontmatter on an index is OPTIONAL, and validated
    when present, matching MEMORY_SCHEMA.md's own "do not require" wording literally
    instead of reading it as "never have".
    """

    # CLEAN_INDEX's body (not just a placeholder "Body.") on purpose: it links
    # project_alpha.md, the one other Tier-1 file the default fixture writes. A
    # body that omits it would trip check (g) ("file not referenced in Tier-1
    # index") as an unrelated true positive, contaminating every assertion below
    # that this fixture is otherwise clean.
    VALID_INDEX_FRONTMATTER = (
        f"""---
name: top-level memory index
description: A Tier-1 index carrying optional frontmatter.
type: index
last_updated: {TODAY}
---

"""
        + CLEAN_INDEX
    )

    def test_index_without_frontmatter_is_silent(self):
        """The pre-existing default: a MEMORY.md with no frontmatter block at all must
        not be reported — this is what the other ~199 write_index()-based tests in this
        module already rely on via CLEAN_INDEX, and it is the case the removed
        exclusion used to cover, just for the wrong stated reason."""
        self.write_index(CLEAN_INDEX)

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("MEMORY.md" in e for e in errors), errors)
        self.assertFalse(any("MEMORY.md" in w for w in warnings), warnings)
        # WI-0128: this class exists to prove MEMORY.md is no longer excluded
        # from FILES (see class docstring) — pin that it was actually counted,
        # not merely that scanning nothing produced no MEMORY.md findings.
        self.assertIn("**Files scanned:** 4", result.stdout, result.stdout)

    def test_index_with_valid_frontmatter_is_silent(self):
        """A MEMORY.md that DOES carry a complete, valid frontmatter block must pass
        checks (a)-(f) like any other memory file — silently, since nothing about it
        is wrong."""
        self.write_index(self.VALID_INDEX_FRONTMATTER)

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("docs/memory/MEMORY.md" in e for e in errors), errors)
        self.assertFalse(any("docs/memory/MEMORY.md" in w for w in warnings), warnings)
        self.assertIn("**Files scanned:** 4", result.stdout, result.stdout)

    def test_type_index_is_accepted_on_the_closed_tier1_enum(self):
        """docs/memory/MEMORY.md sits at parent_dir == 'memory' — the Tier-1 branch of
        check (c), which errors on any type value outside its closed enum. 'index' must
        be a member of that enum, not merely tolerated by the looser Tier-2 one."""
        self.write_index(self.VALID_INDEX_FRONTMATTER)

        result = self.run_lint()
        errors = self.findings(result.stdout, "Errors")

        self.assertFalse(any("type=" in e for e in errors), errors)
        self.assertIn("**Files scanned:** 4", result.stdout, result.stdout)

    def test_index_with_a_missing_required_field_is_reported(self):
        """Once an index carries frontmatter, it is validated like any other file — an
        incomplete block must still be caught, proving 'optional' does not mean
        'unchecked when present'."""
        broken = (
            f"""---
name: broken index
type: index
last_updated: {TODAY}
---

"""
            + CLEAN_INDEX
        )
        self.write_index(broken)

        errors = self.findings(self.run_lint().stdout, "Errors")

        self.assertTrue(
            any("docs/memory/MEMORY.md" in e and "description" in e for e in errors),
            errors,
        )

    def test_tier1_naming_convention_does_not_fire_on_the_index_itself(self):
        """Check (d) expects Tier-1 files to be named '{type}_<slug>.md'. Applied
        literally to docs/memory/MEMORY.md with type: index it would demand
        'index_<slug>.md' — the index is not a Tier-1 memory FILE and must stay exempt
        from this specific check regardless of its type value."""
        self.write_index(self.VALID_INDEX_FRONTMATTER)

        result = self.run_lint()
        warnings = self.findings(result.stdout, "Warnings")

        self.assertFalse(any("Tier-1 naming convention" in w for w in warnings), warnings)
        self.assertIn("**Files scanned:** 4", result.stdout, result.stdout)

    def test_default_fixture_file_count_now_includes_the_persona_index(self):
        """setUp() already writes a Tier-2 persona index (senior-developer/MEMORY.md,
        valid frontmatter, type: index) that used to be excluded by name. Scanning it
        now must show up in the file count the report prints — the scope widening this
        fix makes, pinned to a number rather than 'as expected'.

        Before this fix: project_alpha.md + patterns.md = 2 (the persona index was
        invisible to the FILES array). After: + senior-developer/MEMORY.md = 3.
        """
        result = self.run_lint()

        self.assertIn("**Files scanned:** 3", result.stdout, result.stdout)

    def test_index_with_no_frontmatter_does_not_trigger_the_index_self_reference_check(self):
        """check (g) iterates every file whose parent dir is 'memory' and warns if the
        Tier-1 index does not reference it by name — applied to the index FILE itself
        (parent_dir == 'memory' too, since MEMORY.md is no longer excluded from FILES)
        this would spuriously demand the index reference its own filename inside its
        own body. It must not."""
        self.write_index(CLEAN_INDEX)

        result = self.run_lint()
        warnings = self.findings(result.stdout, "Warnings")

        self.assertFalse(
            any("MEMORY.md' not referenced in Tier-1 index" in w for w in warnings),
            warnings,
        )
        self.assertIn("**Files scanned:** 4", result.stdout, result.stdout)


class Tier2GlobalIndexFrontmatterOptionalTest(MemoryLintFixture, unittest.TestCase):
    """The sibling of IndexFrontmatterOptionalTest for check (i)'s Tier-2-global silo
    scan (WI-0108). Measured: only one Tier-2-global index exists across the reference
    stores (~/.claude/memory/org-x/MEMORY.md) and it has no frontmatter, so aligning
    this site changes nothing today — these two tests exist to prove the alignment is
    behaviour-preserving for the no-frontmatter case and correctly permissive for the
    (currently hypothetical) with-frontmatter case, not because a real fixture needs
    the coverage yet.
    """

    def test_tier2_global_index_without_frontmatter_stays_silent(self):
        agent_dir = self.fake_home / ".claude" / "memory" / "org-x"
        agent_dir.mkdir(parents=True)
        (agent_dir / "MEMORY.md").write_text("# Org-X shared memory\n\nBody.\n", encoding="utf-8")
        # WI-0128: a sibling, non-index file with no frontmatter in the SAME
        # silo directory — proves check (i) actually walked this directory. A
        # broken $TIER2_GLOBAL_DIR/find (or a scan that silently skipped the
        # silo entirely) would leave both this file and MEMORY.md unseen, and
        # every assertion below would be vacuously true.
        (agent_dir / "sibling.md").write_text("# Sibling\n\nBody.\n", encoding="utf-8")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("memory/org-x/MEMORY.md" in e for e in errors), errors)
        self.assertFalse(any("memory/org-x/MEMORY.md" in w for w in warnings), warnings)
        self.assertTrue(
            any(
                "memory/org-x/sibling.md" in e and "without YAML frontmatter" in e
                for e in errors
            ),
            errors,
        )

    def test_tier2_global_index_with_frontmatter_is_validated_like_any_other_silo_file(self):
        agent_dir = self.fake_home / ".claude" / "memory" / "org-x"
        agent_dir.mkdir(parents=True)
        (agent_dir / "MEMORY.md").write_text(
            "---\nname: org-x index\ndescription: shared index\n---\n\n# Org-X\n",
            encoding="utf-8",
        )

        warnings = self.findings(self.run_lint().stdout, "Warnings")

        self.assertTrue(
            any("memory/org-x/MEMORY.md" in w and "scope: tier-2-global" in w for w in warnings),
            warnings,
        )


if __name__ == "__main__":
    unittest.main()
