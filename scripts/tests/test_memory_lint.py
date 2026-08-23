"""test_memory_lint.py – End-to-end tests for scripts/memory-lint.sh.

Invokes the real entry point as a subprocess (`bash memory-lint.sh <project-dir>`)
rather than sourcing internals, so these tests also cover the report rendering and
the documented exit-code contract (0 clean, 1 warnings, 2 errors).

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

The split is what makes the tracked promotion of the default from `warn` to
`err` a single deliberate red test instead of a suite-wide breakage.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

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

TIER2_INDEX_TEXT = """---
name: senior-developer project memory index
description: Index of senior-developer notes.
type: index
last_updated: 01.01.2026
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
    project_attribute-mapping-slice-b-gap.md in productdata) uses the block
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


class MemoryLintTest(unittest.TestCase):
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
        dead link. Deliberately not folded into `run_lint()` (which every one of
        this class's ~600 tests calls) — one extra script invocation per test
        would double the suite's ~60s runtime for no added coverage, since the
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

    def test_status_archived_is_valid(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(status="archived")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("status=" in e for e in errors), errors)

    def test_status_superseded_is_valid(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(status="superseded")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertFalse(any("status=" in e for e in errors), errors)

    def test_status_absent_is_valid(self):
        """No `status:` line at all — the field is optional."""
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(status=None)

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("status=" in e for e in errors), errors)
        self.assertFalse(any("status=" in w for w in warnings), warnings)

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

    def test_superseded_still_suppresses_the_age_warning(self):
        self.write_index(CLEAN_INDEX + "- [Status](project_status.md) — probe\n")
        self.write_status_file(last_updated=OLD_DATE, status="superseded")

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("days old" in w for w in warnings), warnings)

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
        self.write_index(CLEAN_INDEX + "[r]: refdead<!--c-->.md\n")

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
        self.write_index(CLEAN_INDEX + '[ref-titled-dead]: dead_titled.md "A Title"\n')

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
        self.write_index(CLEAN_INDEX + "[ref-paren-dead]: dead_paren.md (A Title)\n")

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
        self.write_index(CLEAN_INDEX + "[ref-angle-dead]: <gone_reference_angle.md>\n")

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
        self.write_index(CLEAN_INDEX + "```\n- [Example](dead_fenced.md)\n```\n")

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("never closed" in w for w in warnings), warnings)

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
        self.write_index(CLEAN_INDEX + "<!--\n- [Example](dead_commented.md)\n-->\n")

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertFalse(any("never closed" in w for w in warnings), warnings)

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

    def test_a_named_entity_in_the_destination_is_still_checked_undecoded(self):
        """`&num;` is a NAMED entity — deliberately left undecoded (WI-0081):
        decoding the full ~2000-entry CommonMark named-entity table is
        disproportionate for a construct that occurs zero times in the field.
        The raw text must still be checked as-is, not mangled — it is a
        documented known_divergence, not silence or a truncated garble."""
        self.write_index(CLEAN_INDEX + "- [Named](gone_ent_named&num;3.md) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone_ent_named&num;3.md", findings[0])

    def test_the_index_is_checked_even_when_no_memory_files_are_scanned(self):
        """An index whose entries are all dead scans zero files — and must still fire.

        The orphan check (g) is gated on FILES_TOTAL because it iterates the files;
        this check iterates the index and must not inherit that gate.
        """
        bare = Path(tempfile.mkdtemp(prefix="ccpr-memory-lint-bare-"))
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        bare_memory = bare / "docs" / "memory"
        bare_memory.mkdir(parents=True)
        (bare_memory / "MEMORY.md").write_text(
            "# Memory Index\n\n- [Ghost](project_deleted.md) — dead link\n", encoding="utf-8"
        )

        result = self.run_lint(project_dir=bare)

        self.assertIn("**Files scanned:** 0", result.stdout)
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
    # Everything above asserts extraction and is blind to severity. The four tests
    # below set the knob deliberately; the pin asserts the shipped value. Changing
    # the default must turn exactly one of them red.

    def test_the_shipped_default_severity_is_warn(self):
        """The default with no override: a dead link is a warning, exit 1.

        This is the assertion whose absence let a default flip pass silently. It
        makes any future change to the shipped default a deliberate red test —
        one failure, here, with the reason written on it — instead of a
        behaviour change that only shows up as an exit code somewhere in CI.
        The promotion to `err` (WI-0005, ADR-0001) was reverted (WI-0005 round
        3, 19.08.2026): see the comment above MEMORY_INDEX_LINK_SEVERITY's
        assignment in memory-lint.sh for why.
        """
        self.assertNotIn(SEVERITY_VAR, self.lint_env(), "the base env must not preset the knob")
        self.write_index(CLEAN_INDEX + "- [Ghost](project_deleted.md) — dead link\n")

        result = self.run_lint()

        warnings = self.findings(result.stdout, "Warnings")
        self.assertEqual(len(warnings), 1, result.stdout)
        self.assertIn("project_deleted.md", warnings[0])
        self.assertEqual(self.findings(result.stdout, "Errors"), [], result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout)

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

    def test_a_severity_value_is_never_executed_as_a_command(self):
        """The knob is dispatched by value, not expanded into command position."""
        canary = self.project_dir / "canary.txt"
        self.write_index(CLEAN_INDEX + "- [Ghost](project_deleted.md) — dead link\n")

        result = self.run_lint(**{SEVERITY_VAR: f"touch {canary}"})

        self.assertFalse(canary.exists(), result.stderr)
        self.assertEqual(result.returncode, 3, (result.stdout, result.stderr))


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


class EscapeAwareLinkExtractionMutationTest(unittest.TestCase):
    """WI-0079 obligation: the new escape-awareness tests must have been seen
    RED by mutation, not merely written and never falsified. Reverts
    `process_link_line()`'s escape guard to its exact pre-fix shape on an
    in-memory COPY of the script (same pattern as
    MutationProvesTheDifferentialTestCanFail above) — the shipped script on
    disk is never touched; proven by md5, not assumed.
    """

    _ESCAPE_GUARD = (
        "                if (is_escaped(line, open_pos) || is_escaped(line, close_pos)) {\n"
        "                    line = substr(line, RSTART + 1)\n"
        "                    continue\n"
        "                }\n"
    )

    def test_removing_the_escape_guard_flips_the_escaped_bracket_fixtures_red(self):
        original = SCRIPT_PATH.read_text(encoding="utf-8")
        original_md5_before = __import__("hashlib").md5(original.encode("utf-8")).hexdigest()

        self.assertIn(
            self._ESCAPE_GUARD, original,
            "fixture line moved — update the mutation target for this test",
        )
        mutated = original.replace(self._ESCAPE_GUARD, "", 1)
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
                "- \\[not a link\\](gone_mut_esc1.md) — not a link\n",
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
            "gone_mut_esc1.md", result.stdout,
            "mutation did not flip the fixture — the escape guard no longer "
            "discriminates WI-0079's defect",
        )

        # The real script on disk was never touched — proven by md5, not assumed.
        after = SCRIPT_PATH.read_text(encoding="utf-8")
        original_md5_after = __import__("hashlib").md5(after.encode("utf-8")).hexdigest()
        self.assertEqual(original_md5_before, original_md5_after)
        self.assertEqual(after, original)


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


if __name__ == "__main__":
    unittest.main()
