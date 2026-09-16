"""test_docs_boundary_default_deny.py -- CCP-1214: the docs/ ignore rule must
be default-deny, keyed to the same allowlist artifact-gate.sh enforces.

## The defect

Three tools decide what may live under docs/, and until this module they
disagreed about the DIRECTION of the rule:

* `scripts/artifact-gate.sh` is default-deny. A tracked docs/ path that is
  not in `scripts/lib/docs-framework-allowlist.txt` is a `[docs-boundary]`
  finding (CCP-1017).
* `install.sh`'s `install_docs()` is default-deny. It copies the allowlisted
  entries and reports the rest as skipped working state (CCP-1017).
* `.gitignore` was default-ALLOW. It enumerated the working-state paths
  somebody had remembered to add -- `docs/HANDOVER.md`, `docs/workitems/`,
  `docs/memory/`, `docs/decisions/`, `docs/workitems-idmap.yml` and the
  `docs/.*` dotfile pattern.

An enumeration only covers what its author thought of. Measured on
16.09.2026 against `0003f46` by this module: **24 top-level docs/ entries,
145 paths**, neither ignored nor allowlisted. 21 of them are genuine working
state -- the nine Full-Track phase folders (`discovery/`, `concept/`,
`validation/`, `architecture/`, `planning/`, `quality/`, `launch/`,
`operations/`, `reviews/`), the Lean-Track and session artefacts
(`instincts.md`, `BASELINE.md`, `FRAME.md`, `CLAUDE-lean.md`, `LEARNINGS.md`,
`PROMOTION_BRIEF.md`, `TRACK_DECISION.md`) and five further folders
(`concepts/`, `epics/`, `roadmaps/`, `user-stories/`, `lean-archive/`).

The other three are the sweep being over-inclusive, and they are reported
rather than filtered: `README.md` and `somewhere/` appear only as
illustrations inside comments, and `chore` is a plain false positive -- it
comes from the string `feat/fix/refactor/docs/chore` in
`templates/CLAUDE_LEAN_TEMPLATE.md`, a list of Conventional-Commit types that
happens to look like a path.

**The over-inclusive bias is deliberate.** A false positive here can only
ever cause a spurious FAILURE, which someone reads and resolves. A false
negative is a path the guard silently stops seeing -- the failure mode this
whole ticket is about. Nothing is filtered on suspicion of being prose.

CCP-1214 itself reported sixteen. The difference is scope and granularity,
not disagreement: it swept `commands/` and `scripts/`, and counted
`BACKLOG.md`, `SPRINT.md` and `PROJECT_PLAN.md` as top-level entries where
the shipped commands actually spell them `docs/planning/BACKLOG.md` and so on
-- already counted here once, as the `planning/` folder. Those three strings
do not occur at the top level anywhere in the repository; this module's own
witness test asserts the `docs/planning/...` forms for exactly that reason.

The one that mattered: `commands/postmortem.md` tells the maintainer to store
project-specific instincts in `docs/instincts.md`. So the command a maintainer
runs at the END of a CCPR session wrote an untracked, un-ignored file into
CCPR's own repository -- one `git add -A` away from the accident CCP-1017
records as having already happened once (17 CCPR work items committed and
pushed into what every user reads as their own state).

## Why this is not a repeat of CCP-1057's mistake

CCP-1057 chose a PATTERN over an enumeration, deliberately, and argued it in
the .gitignore itself: "a pattern nobody has to remember to extend is what
actually keeps pace with a script adding a new report next quarter". That
reasoning was right. The pattern it picked, `docs/.*`, matches DOTFILES only,
and every artefact above is a normal filename -- so the rule was narrower than
the argument for it. This module extends that reasoning to its full width
rather than reversing it.

## What holds the two registers together

Inverting .gitignore to `docs/*` means its re-inclusion lines (`!docs/adr/`
and friends) become a THIRD copy of the allowlist. CCP-1017's own PO decision
named that cost in advance -- "two lists that must agree are exactly the shape
that produced WI-0059 ... derive one from the other or pin their agreement
with a test". `.gitignore` has no include directive, so derivation is
impossible and pinning is the obligation:
`TheGitignoreReinclusionsAreExactlyTheAllowlistTest` reads the two files
independently and fails in BOTH directions.

## Why every ignore probe here passes --no-index

`git check-ignore` is index-aware: it reports a TRACKED path as NOT ignored
even when a pattern plainly matches it (install.sh's `path_is_source_ignored`
comment relies on exactly this). Measured in a throwaway repo whose only rule
was `docs/*`: tracked `docs/adr/A.md` answered "not ignored" index-aware and
"ignored" under `--no-index`.

That makes the index-aware form useless for asserting what the RULES say. An
allowlisted path is tracked, so it would answer "not ignored" whether or not
the re-inclusion line existed at all -- a guard that cannot fail, which is the
shape instinct G-095 names. Every probe below therefore asks `--no-index`, so
each answer is a property of `.gitignore` rather than of today's index.

## What this module does NOT see

The boundary is evaluated per TOP-LEVEL entry under docs/, because that is the
granularity both the allowlist and `install_docs()` use. A file INSIDE an
allowlisted directory is therefore excused here whatever its name -- and under
`docs/*` it is genuinely not ignored, because `!docs/adr/` re-opens the
directory. Measured: with `docs/*` plus `!docs/adr/`, `docs/adr/.hidden.md`
is reported untracked, not ignored.

That hole is real and it is CCP-1156's: `install_docs()` reads the FILESYSTEM,
so a file that lands inside an allowlisted directory ships to every
installation. It is characterised below by
`ReincludedDirectoriesAreTheKnownBlindSpotTest` -- stated, not fixed, since
CCP-1156 is still open.

`test_docs_dotfile_gitignore_coverage.py` is where that hole would ideally be
caught, since these artefacts are its subject. It cannot be: its `DOTFILE_RE`
anchors on `docs/\\.` and only ever finds dotfiles DIRECTLY under docs/.
Proven by mutation -- adding `docs/adr/.session-context.md` to a shipped
command leaves that suite green. Its repo-side gap-1 class became true by
construction under default-deny and was removed rather than left green; see
that module's docstring for the three measurements behind the decision.
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
COMMANDS_DIR = REPO_ROOT / "commands"
HOOKS_DIR = REPO_ROOT / "hooks"
AGENTS_DIR = REPO_ROOT / "agents"
TEMPLATES_DIR = REPO_ROOT / "templates"
GITIGNORE = REPO_ROOT / ".gitignore"
ALLOWLIST = REPO_ROOT / "scripts" / "lib" / "docs-framework-allowlist.txt"

# The default-deny rule itself. Named as a literal because this module is
# what pins its presence -- deriving it from the file it is meant to check
# would assert the file against itself.
DEFAULT_DENY_RULE = "docs/*"

# A concrete docs/ path no shipped file names and nothing tracks. Used to ask
# the rules the direct question "is an entry nobody allowlisted denied?"
# without depending on the sweep finding a witness.
NOVEL_PATHS = (
    "docs/a-file-nobody-added.md",
    "docs/a-folder-nobody-added/deep/nested.md",
)

# docs/ paths as they are spelled in shipped sources. Deliberately narrow:
# a path must start with an alphanumeric (so `docs/$FOLDER`, `docs/<phase>`
# and `docs/{type}_{slug}` placeholders are skipped rather than guessed at)
# and may only carry characters that are legal in the concrete paths these
# tools actually write. The alphanumeric requirement ALSO excludes literal
# top-level dotfiles (`docs/.session-context.md`) -- a side effect, named here
# so the comment matches what the regex does: those are covered instead by
# DefaultDenyIsInForceTest's fixed dotfile probe below, and enumerated in
# detail by test_docs_dotfile_gitignore_coverage.py, which owns that family.
DOCS_PATH_RE = re.compile(r"docs/[A-Za-z0-9][A-Za-z0-9_./-]*")

# Trailing characters prose and truncated placeholders leave behind:
# "see docs/CONSTITUTION.md." -> a sentence full stop; "docs/reviews/SPRINT-"
# -> a name the source completes with a variable this sweep skipped. The
# trailing "/" goes too, so `docs/reviews` and `docs/reviews/` (both occur)
# collapse to one entry; probe_path() below re-decides file-or-directory.
TRAILING_NOISE = "./-_"

# Appended to a swept path that denotes a DIRECTORY, so the probe is a file
# the way a command's actual output is a file. Not cosmetic: a gitignore
# entry written `docs/decisions/` is directory-only, and `git check-ignore
# --no-index docs/decisions` answers "not ignored" because nothing tells it
# the path is a directory. Measured both ways -- `docs/decisions/D.md` is
# ignored, bare `docs/decisions` is not -- so probing the bare name would
# have reported two already-covered entries as CCP-1214 violations.
DIRECTORY_PROBE_LEAF = "a-generated-file.md"


def shipped_source_files():
    """The shipped surface a maintainer can run against this repository.

    Starts from the scope `test_docs_dotfile_gitignore_coverage.py` already
    documents -- top-level `scripts/*.sh` and `scripts/*.py` plus
    `scripts/lib/*`, and all of the flat `commands/` tree -- extended with
    `hooks/`, which CCP-1214's acceptance names explicitly, and with
    `agents/*.md` and `templates/**/*.md`.

    Those last two are here deliberately rather than by inheritance. An
    enumeration of WHICH FILES TO SCAN is the same defect shape CCP-1214
    exists to fix, recursed one level up: it covers what its author thought
    of. An agent definition or a template could be the first place naming a
    new docs/ artefact -- `agents/*.md` name `docs/memory/{agent}/` and
    `docs/HANDOVER.md` today, and `templates/` carries the HANDOVER and
    phase-doc skeletons. Measured when they were added: 34 docs/ paths across
    15 agent files and 30 across 27 templates, zero of them violations, so
    this widening changed no verdict -- it removes a blind spot rather than
    fixing a live finding.

    Two exclusions remain, both load-bearing rather than incidental:
    `scripts/tests/**` is the test suite rather than a shipped artefact, and
    sweeping it would make this module find the docs/ paths in its OWN
    docstring (the reason the dotfile module gives, and it applies here with
    more force -- this docstring names several). `scripts/local-llm/**` is
    user-owned and hardware-specific per install.sh's PROTECTED marking.
    """
    files = []
    for pattern in ("*.sh", "*.py"):
        files.extend(SCRIPTS_DIR.glob(pattern))
        files.extend((SCRIPTS_DIR / "lib").glob(pattern))
        files.extend(HOOKS_DIR.glob(pattern))
    files.extend(COMMANDS_DIR.rglob("*.md"))
    files.extend(AGENTS_DIR.glob("*.md"))
    files.extend(TEMPLATES_DIR.rglob("*.md"))
    return sorted(files)


def swept_docs_paths():
    """Map of concrete `docs/<...>` path -> the shipped files naming it.

    Derived, never hand-listed: CCP-1214 exists because an enumeration went
    stale, so re-typing the witnesses it measured here would reintroduce the
    same defect one layer up. A command that starts writing a new docs/
    artefact tomorrow enters this set on its own.

    No "is this still `docs/` itself" guard is needed: DOCS_PATH_RE requires an
    alphanumeric immediately after `docs/`, and TRAILING_NOISE strips none of
    those, so every candidate carries at least one character of entry name. An
    earlier draft guarded for `docs` / `docs/` anyway; it was unreachable and
    is gone rather than left to read as if it protected something.
    """
    found = {}
    for path in shipped_source_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for raw in DOCS_PATH_RE.findall(text):
            candidate = raw.rstrip(TRAILING_NOISE)
            found.setdefault(candidate, set()).add(
                path.relative_to(REPO_ROOT).as_posix())
    return found


def probe_path(docs_path):
    """The concrete file path to ask `git check-ignore` about.

    A command's output is always a FILE, so that is what gets probed. A swept
    token whose last component carries no extension names a directory and gets
    a sentinel leaf appended; anything with an extension is probed as written.

    The no-extension rule is the one assumption here, and it is stated rather
    than hidden: a docs/ file with no suffix at all would be probed as a
    directory. None exists in the swept set today, and the shipped commands
    write `.md`/`.json` throughout.
    """
    last = docs_path.rsplit("/", 1)[-1]
    if "." not in last:
        return docs_path + "/" + DIRECTORY_PROBE_LEAF
    return docs_path


def allowlist_entries():
    """The framework allowlist, parsed the way both shipped readers parse it:
    one entry per line, `#` comments and blank lines dropped, trailing `/`
    kept because it is what distinguishes a directory entry from a file."""
    entries = []
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def allowlisted_top_level_names():
    """Allowlist entries reduced to the bare top-level name under docs/."""
    return {entry.rstrip("/") for entry in allowlist_entries()}


def top_level_entry(docs_path):
    """`docs/planning/SPRINT.md` -> `planning`. The granularity the allowlist
    and install_docs() both decide at."""
    return docs_path[len("docs/"):].split("/")[0]


def gitignore_lines():
    return GITIGNORE.read_text(encoding="utf-8").splitlines()


def gitignore_docs_reinclusions():
    """Every `!docs/...` re-inclusion line, in file order, as (index, entry)
    where entry is the text after `!docs/` -- directly comparable with an
    allowlist entry."""
    out = []
    for index, line in enumerate(gitignore_lines()):
        stripped = line.strip()
        if stripped.startswith("!docs/"):
            out.append((index, stripped[len("!docs/"):]))
    return out


def is_ignored(rel_path):
    """Would the .gitignore rules alone deny this path?

    `--no-index` is the whole point: see this module's docstring. Without it a
    tracked path answers "not ignored" no matter what the patterns say, and
    every assertion about an allowlisted entry below would pass vacuously.
    """
    return subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "--", rel_path],
        cwd=REPO_ROOT,
    ).returncode == 0


class DocsPathSweepTest(unittest.TestCase):
    """Characterises the sweep itself. A scanner that quietly stops finding
    anything reports a clean tree, which is the failure mode CCP-1017's own
    verification nearly shipped ("a run over nothing nearly passed for a
    pass")."""

    def test_the_sweep_finds_docs_paths_at_all(self):
        self.assertGreater(
            len(swept_docs_paths()), 0,
            "the docs/ path sweep found nothing; an empty scope is a blind "
            "scanner, not a clean repository",
        )

    def test_the_sweep_finds_the_witnesses_ccp_1214_was_filed_for(self):
        """Named individually rather than as a pinned set: these are the
        paths whose exposure motivated the item, and each one reaching this
        sweep is what makes the boundary test below say anything. A pinned
        set would age every time a command adds a phase document; these do
        not age, because removing one means the shipped surface stopped
        naming it.
        """
        swept = swept_docs_paths()
        # commands/postmortem.md -- the item's headline case.
        self.assertIn("docs/instincts.md", swept)
        # The Full-Track phase folders and the Lean-Track artefacts.
        self.assertIn("docs/planning/SPRINT.md", swept)
        self.assertIn("docs/planning/BACKLOG.md", swept)
        self.assertIn("docs/discovery/DISCOVERY.md", swept)
        self.assertIn("docs/architecture/ARCHITECTURE.md", swept)
        self.assertIn("docs/quality/QA.md", swept)
        self.assertIn("docs/FRAME.md", swept)
        self.assertIn("docs/CLAUDE-lean.md", swept)

    def test_the_sweep_skips_placeholders_rather_than_guessing_at_them(self):
        """`docs/<phase-folder>/`, `docs/$FOLDER` and `docs/{type}_{slug}`
        are templates, not paths. Resolving them would mean inventing the
        values; they are dropped, and the concrete siblings the same commands
        spell out carry the coverage instead."""
        swept = swept_docs_paths()
        for path in swept:
            self.assertNotRegex(
                path, r"[<>{}$*]",
                "a placeholder reached the concrete-path sweep: " + path,
            )


class EveryDocsPathTheFrameworkNamesIsIgnoredOrAllowlistedTest(unittest.TestCase):
    """CCP-1214's acceptance criterion, stated over the real witnesses.

    ## What this uniquely detects: nothing, and that is stated rather than
    ## claimed away

    A code review of this module traced the failure conditions and found its
    failure set is a SUBSET of the two classes below, and the trace holds:
    under `docs/*` every path beneath docs/ is denied unless a `!` line
    re-includes it; `TheGitignoreReinclusionsAreExactlyTheAllowlistTest`
    pins those `!` lines to be exactly the allowlist entries; so a swept path
    is either denied (passes here) or sits under an allowlisted entry (passes
    here by the other branch). If `docs/*` itself is removed or narrowed,
    `DefaultDenyIsInForceTest` says so directly, over synthetic probes rather
    than over whatever the sweep happens to find today.

    So this class is NOT what keeps a new command's output from going
    unignored -- `docs/*` does that structurally, which is the entire point of
    the ticket. An earlier version of this docstring claimed primacy it does
    not have ("the class-level statement the sixteen measured entries were
    only the first witnesses of"), and that claim is withdrawn.

    ## Why it is kept anyway

    1. It is the acceptance criterion as written, over REAL paths from the
       shipped surface rather than invented ones. The other two classes prove
       the rule; this one proves the rule covers the actual corpus.
    2. It was the RED witness: 23 top-level entries / 142 paths before the
       change, which is the evidence the defect existed at all.
    3. Its failure message is the actionable one -- it names the offending
       paths grouped by entry, so whoever breaks the boundary is told which
       allowlist line or ignore rule to write.

    Kept deliberately and redundantly, in other words, not because anyone
    believes it is load-bearing. If a future change makes the other two
    classes unable to cover it, that is the moment this note stops being true.
    """

    def test_no_shipped_docs_path_is_both_untracked_and_unignored(self):
        swept = swept_docs_paths()
        allowlisted = allowlisted_top_level_names()
        offenders = []
        for path in sorted(swept):
            if top_level_entry(path) in allowlisted:
                continue
            if is_ignored(probe_path(path)):
                continue
            offenders.append(path)

        # Grouped by top-level entry for the message only: that is the unit
        # somebody has to act on (one .gitignore rule or one allowlist line
        # settles a whole folder), while the assertion stays at full-path
        # granularity so a single uncovered file cannot hide inside a folder
        # that is otherwise fine.
        by_entry = {}
        for path in offenders:
            by_entry.setdefault(top_level_entry(path), []).append(path)
        summary = "; ".join(
            "{} ({} path(s), e.g. {})".format(entry, len(paths), paths[0])
            for entry, paths in sorted(by_entry.items())
        )
        self.assertEqual(
            [], offenders,
            "docs/ paths named by shipped commands or scripts that this "
            "repository neither ignores nor allowlists -- a `git add -A` "
            "after running one of them commits working state into what every "
            "user installs as framework content (CCP-1214). "
            "{} entr(ies): {}".format(len(by_entry), summary),
        )


class DefaultDenyIsInForceTest(unittest.TestCase):
    """The direct statement of the rule, independent of the sweep.

    The boundary test above draws its teeth from the paths the shipped surface
    happens to name today. This one does not: it asks whether an entry nobody
    allowlisted is denied, which is the property `docs/*` exists to provide and
    the one that would silently disappear if that line were dropped or narrowed
    back to `docs/.*`.
    """

    def test_a_path_nobody_added_is_denied(self):
        for rel in NOVEL_PATHS:
            with self.subTest(path=rel):
                self.assertTrue(
                    is_ignored(rel),
                    "docs/ is not default-deny: {} is neither allowlisted nor "
                    "ignored, so an artefact under a new name lands untracked "
                    "and unignored exactly as CCP-1214 measured".format(rel),
                )

    def test_a_dotfile_nobody_added_is_denied_by_the_same_rule(self):
        """CCP-1057's `docs/.*` was the narrower predecessor of `docs/*`.
        Asserted separately so that swapping the wide rule back for the
        dotfile-only one fails HERE as well as above -- `*` matching a
        leading dot is a gitignore behaviour worth pinning rather than
        assuming."""
        self.assertTrue(
            is_ignored("docs/.an-artefact-nobody-added.md"),
            "a generated docs/ dotfile is not denied",
        )


class ReincludedDirectoriesAreTheKnownBlindSpotTest(unittest.TestCase):
    """Characterises the hole default-deny does NOT close, so that it is
    stated in executable form rather than only in a comment.

    CCP-1156's complaint is that the .gitignore comment already documents this
    consequence and "nothing DETECTS it". Inverting the rule does not fix that
    and adds a second edge to it: `!docs/adr/` re-opens the directory, so a
    file landing inside an allowlisted directory is neither ignored here nor
    skipped by `install_docs()`, which reads the FILESYSTEM rather than the
    git index and therefore copies it into every installation.

    This is a CHARACTERISATION test of an open item, not a fix for it. It is
    here rather than in `test_docs_dotfile_gitignore_coverage.py` because that
    module's `DOTFILE_RE` anchors on `docs/\\.` and structurally cannot produce
    a path inside a subdirectory -- proven by mutation, adding
    `docs/adr/.session-context.md` to a shipped command left that suite green.

    If this test ever fails, the hole has been closed (a `docs/**/.*` rule, or
    install.sh filtering by `git ls-files`). That is CCP-1156 landing --
    update this test deliberately, and check whether the boundary assertion
    above can be tightened from top-level-entry to full-path granularity at
    the same time.
    """

    def test_a_file_inside_an_allowlisted_directory_is_not_denied(self):
        directory_entries = []
        for entry in allowlist_entries():
            if entry.endswith("/"):
                directory_entries.append(entry)
        self.assertGreater(
            len(directory_entries), 0,
            "the allowlist has no directory entries, so this "
            "characterisation has nothing to describe",
        )
        for entry in directory_entries:
            for leaf in (".session-context.md", "a-stray-draft.md"):
                probe = "docs/" + entry + leaf
                with self.subTest(probe=probe):
                    self.assertFalse(
                        is_ignored(probe),
                        "{} is now ignored. The CCP-1156 blind spot this test "
                        "characterises has been closed -- re-aim it rather "
                        "than deleting it".format(probe),
                    )


class TheGitignoreReinclusionsAreExactlyTheAllowlistTest(unittest.TestCase):
    """CCP-1017's stated obligation, paid.

    Its PO decision accepted a second register beside the allowlist and named
    the condition: "Whoever builds it must derive one from the other or pin
    their agreement with a test -- not maintain two copies by hand." A
    .gitignore cannot include another file, so derivation is unavailable and
    this is the pin. It reads the two files INDEPENDENTLY -- neither side is
    computed from the other -- so it fails whichever one is edited alone.
    """

    def test_the_default_deny_rule_is_present(self):
        self.assertIn(
            DEFAULT_DENY_RULE, [l.strip() for l in gitignore_lines()],
            "the `docs/*` default-deny rule is gone; every re-inclusion below "
            "it becomes a no-op and docs/ is default-allow again",
        )

    def test_every_allowlist_entry_has_its_re_inclusion_and_no_others_exist(self):
        expected = ["!docs/" + entry for entry in allowlist_entries()]
        actual = ["!docs/" + entry for _, entry in gitignore_docs_reinclusions()]
        self.assertEqual(
            sorted(expected), sorted(actual),
            "the .gitignore re-inclusions and "
            "scripts/lib/docs-framework-allowlist.txt disagree. A framework "
            "document needs BOTH lines: the allowlist entry (so the gate and "
            "install.sh ship it) and the `!docs/` line (so this repository "
            "still tracks it). Adding only the allowlist entry leaves the file "
            "ignored and it silently never gets committed; adding only the "
            "`!docs/` line makes artifact-gate.sh fail it as working state.",
        )

    def test_the_re_inclusions_come_after_the_default_deny_rule(self):
        """Order is not cosmetic, it is the whole mechanism. Measured in a
        throwaway repo: with `!docs/adr/` placed BEFORE `docs/*`, the
        re-inclusion is lost and `docs/adr/A.md` is ignored again -- git
        applies the last matching pattern, so an exception stated first is
        immediately overruled."""
        lines = [l.strip() for l in gitignore_lines()]
        deny_index = lines.index(DEFAULT_DENY_RULE)
        for index, entry in gitignore_docs_reinclusions():
            with self.subTest(entry=entry):
                self.assertGreater(
                    index, deny_index,
                    "!docs/{} is stated before `{}` and is therefore "
                    "overruled by it".format(entry, DEFAULT_DENY_RULE),
                )

    def test_every_allowlisted_entry_is_actually_re_included(self):
        """The behavioural half, so the textual agreement above cannot pass on
        two lists that agree with each other and are both wrong in form. Asks
        git, with --no-index, whether a file under each allowlisted entry
        survives the rules -- the form-sensitivity CCP-1214 warned about
        (`docs/` + `!docs/adr/` erases the whole tree where `docs/*` +
        `!docs/adr/` does not) shows up here and nowhere else."""
        for entry in allowlist_entries():
            with self.subTest(entry=entry):
                probe = "docs/" + entry
                if entry.endswith("/"):
                    probe += "a-framework-file.md"
                self.assertFalse(
                    is_ignored(probe),
                    "docs/{} is allowlisted -- artifact-gate.sh requires it to "
                    "be tracked and install.sh ships it -- but the .gitignore "
                    "rules deny {}. A framework document added here would be "
                    "silently uncommittable.".format(entry, probe),
                )


if __name__ == "__main__":
    unittest.main()
