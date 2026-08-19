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

    _EVEN_MUTATION_TARGET = "        # in_comment carries the state across lines, so comment blocks work too.\n"

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
            "        # in_comment carries the state's own across lines, so comment blocks work too.\n",
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
            "        # in_comment carries the state's own across lines, so this construct's comment blocks work too.\n",
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


if __name__ == "__main__":
    unittest.main()
