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

import shutil
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "memory-lint.sh"

TODAY = date.today().strftime("%d.%m.%Y")

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

    def lint_env(self, **extra_env):
        """The environment of a lint run — built from scratch, never inherited.

        A call without **extra_env therefore exercises the script's own defaults,
        which is precisely what the default pin needs to be meaningful.
        """
        env = {"HOME": str(self.fake_home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
        env.update(extra_env)
        return env

    def run_lint(self, project_dir=None, **extra_env):
        return subprocess.run(
            ["bash", str(SCRIPT_PATH), str(project_dir or self.project_dir)],
            capture_output=True, text=True, env=self.lint_env(**extra_env),
        )

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

    def test_a_space_inside_the_target_is_not_a_title_delimiter(self):
        """`[X](my file.md)` addresses `my file.md`, not `my`.

        The Markdown title suffix is `](target "Title")`; a bare space is no
        delimiter, so truncating at the first space invented a target.
        """
        self.write_index(CLEAN_INDEX + "- [Spaces](my missing file.md) — dead\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("my missing file.md", findings[0])

    def test_a_target_with_a_space_resolves_when_the_file_exists(self):
        spaced = self.memory_dir / "senior-developer" / "notes with space.md"
        spaced.write_text(TIER2_TOPIC_TEXT, encoding="utf-8")
        self.write_index(CLEAN_INDEX + "- [Spaces](senior-developer/notes with space.md) — live\n")

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
        self.write_index(CLEAN_INDEX + "<!-- retired --> - [Ghost](gone.md) — live entry\n")

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

    def test_an_image_inside_a_single_line_html_comment_is_skipped(self):
        """Both skip mechanisms — comment-stripping and the image exclusion — are
        covered separately elsewhere; this exercises them combined on one line
        (WI-0026). decomment() runs before the image/link distinction, so an
        image markup that sits entirely inside a comment must vanish before
        that distinction is ever made.
        """
        self.write_index(CLEAN_INDEX + "<!-- ![Diagram](dead_diagram.md) --> - [Ghost](gone.md)\n")

        findings = self.link_findings(self.run_lint().stdout)

        self.assertEqual(len(findings), 1, findings)
        self.assertIn("gone.md", findings[0])

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

    def test_reference_style_definition_in_angle_brackets_is_skipped(self):
        """`[id]: <live.md>` — the escaped-destination form, same scope decision
        as the inline `[x](<t.md>)` form pinned below."""
        self.write_index(CLEAN_INDEX + "[ref-angle]: <project_alpha.md>\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

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

    # --- Forms the check deliberately skips, and its scope -------------------------

    def test_angle_bracket_targets_are_skipped(self):
        """`[x](<t.md>)` is the escaped destination form — currently out of scope.

        Pinned as skipped rather than half-checked: without the skip the angle
        brackets end up in the path and every such link is a false positive.
        """
        self.write_index(CLEAN_INDEX + "- [Angle](<project_alpha.md>) — escaped form\n")

        self.assertEqual(self.link_findings(self.run_lint().stdout), [])

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

    # --- The severity knob: the only tests that may notice the default ------------
    # Everything above asserts extraction and is blind to severity. The four tests
    # below set the knob deliberately; the pin asserts the shipped value. Changing
    # the default must turn exactly one of them red.

    def test_the_shipped_default_severity_is_err(self):
        """The default with no override: a dead link is an error, exit 2.

        This is the assertion whose absence let a default flip pass silently. It
        makes the promotion to `err` (WI-0005, ADR-0001) a deliberate red test —
        one failure, here, with the reason written on it — instead of a behaviour
        change that only shows up as an exit code somewhere in CI. Before the
        promotion this pinned `warn`/exit 1; flipping the production default
        without touching this assertion is exactly what turned it red.
        """
        self.assertNotIn(SEVERITY_VAR, self.lint_env(), "the base env must not preset the knob")
        self.write_index(CLEAN_INDEX + "- [Ghost](project_deleted.md) — dead link\n")

        result = self.run_lint()

        errors = self.findings(result.stdout, "Errors")
        self.assertEqual(len(errors), 1, result.stdout)
        self.assertIn("project_deleted.md", errors[0])
        self.assertEqual(self.findings(result.stdout, "Warnings"), [], result.stdout)
        self.assertEqual(result.returncode, 2, result.stdout)

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


if __name__ == "__main__":
    unittest.main()
