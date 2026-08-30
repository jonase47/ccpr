"""test_ci_workflow.py -- guards .github/workflows/ci.yml's load-bearing
lines against exactly the kind of quiet "cleanup" that removes them.

## Why this exists

This repository is getting its first CI (WI: first-ci, 30.08.2026). A
workflow file has no test coverage of its own by default -- nothing stops
a future edit from dropping `fetch-depth: 0` as "unused", loosening the
bash-3.2 assert into a warning, or adding `continue-on-error: true` to make
a red job quietly green. Three properties are load-bearing enough that
losing any one of them would make the CI lie about what it actually
verified, so they get a real test instead of only a comment:

1. Every `actions/checkout` step sets `fetch-depth: 0`, justified by a
   comment naming `test_agent_frontmatter.py` -- that test's
   `PRE_FIX_COMMIT` pin (`scripts/tests/test_agent_frontmatter.py:154`)
   reads a commit well over 40 commits behind HEAD via `git show
   <sha>:<path>` with `check=True`; actions/checkout's default
   `fetch-depth: 1` would make that call fail and the test ERROR.
2. The macOS job asserts, before it does anything else meaningful, that
   the bash actually resolved on this runner starts with `3.2` (ADR-0011,
   `docs/adr/ADR-0011-bash-3-2-floor.md`, decision 3) -- the shebang does
   not carry that floor, `env` resolution does, and a runner-image change
   could silently swap it out from under every check that follows.
3. Nothing in the file swallows a failing check: no `continue-on-error`,
   no bare `|| true`.

## Why a purpose-built structural reader, not a plain text grep, and not
   pyyaml

This repository ships no external dependencies (no requirements.txt /
pyproject.toml, see CONTRIBUTING.md) -- `pyyaml` is not an option. A plain
`"fetch-depth: 0" in text` substring check would pass just as happily if
the line sat in a code comment, in the WRONG job, or attached to a step
that is not actually a checkout -- exactly the class of false-negative
G-145 names ("a sighting is only as wide as its pattern"). What this
module needs is JOB and STEP boundaries: "does THIS job's checkout step
carry THIS key, with a comment directly above it", "does the step that
asserts the bash version run BEFORE this job's checkout step". That is
irreducibly structural, so `_find_jobs`/`_find_steps` below parse exactly
that much of the YAML -- indentation-delimited block mappings and
sequences -- and nothing more. It is NOT a general YAML parser: it assumes
the fixed authoring style `ci.yml` actually uses (2-space nesting, `steps:`
is always a job's last key, sequence items always start with `- ` at a
consistent indent). That assumption is asserted, not hoped for --
`RealWorkflowStructureTest` pins the exact job names, `runs-on` values, and
per-job step counts the parser found, so a reflow of the file that this
parser can no longer follow fails loudly here rather than making every
other test in this module vacuously pass on an empty job list.

## The red proof

Every one of the three properties is proven capable of catching its own
absence: `MutationTest*` classes below copy the REAL file's text into a
scratch file, apply ONE targeted structural edit (never a deletion of the
whole file, never commenting a check out), assert the substitution
actually took hold (`re.subn`'s own match count, or an explicit line-count
delta -- a mutation that silently misses its target and reports "still
compliant" would be worse than no test at all, per the mutation-hygiene
lesson already codified for check-all.sh's own RED proofs), and then
assert `lint_ci_workflow` on the mutated copy reports the expected
violation. `RealWorkflowIsCompliantTest` is the GREEN half: the shipped
file, unmutated, reports zero violations.

## What this module does NOT prove

Parsing text is not executing it. This module never invokes `bash`,
`python3`, or GitHub's own workflow engine -- it cannot tell you whether
`echo "/bin" >> "$GITHUB_PATH"` actually puts `/bin/bash` ahead of a
Homebrew one on a real macos-latest runner, whether `actions/checkout@v4`
and `actions/setup-python@v5` still resolve, or whether check-all.sh's
own report format is what this file's comments claim it measured. Those
are exactly the claims only a real GitHub Actions run can settle -- see
the work item's own final write-up for the explicit list.
"""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
AGENT_FRONTMATTER_TEST = REPO_ROOT / "scripts" / "tests" / "test_agent_frontmatter.py"

CHECKOUT_USES_RE = re.compile(r"actions/checkout@")
SETUP_PYTHON_USES_RE = re.compile(r"actions/setup-python@")
FETCH_DEPTH_ZERO_RE = re.compile(r"^\s*fetch-depth:\s*0\s*$")
PYTHON_VERSION_RE = re.compile(r'^\s*python-version:\s*"([^"]+)"\s*$')
FAILING_EXIT_RE = re.compile(r"\bexit\s+1\b")
BASH_VERSION_TOKEN = "BASH_VERSION"
FLOOR_PREFIX_TOKEN = "3.2"
JUSTIFICATION_ANCHOR = "test_agent_frontmatter.py"


# --- the minimal structural reader (see module docstring) -------------------

def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _is_blank_or_comment(line):
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def _find_jobs(lines):
    """Returns {job_name: (body_start, body_end)} for every top-level key
    directly under `jobs:` -- indent 2, ending in ':'. `body_end` is
    exclusive; the next job's name line, or len(lines) for the last job."""
    n = len(lines)
    jobs_line = None
    for i, line in enumerate(lines):
        if not _is_blank_or_comment(line) and _indent(line) == 0 and line.rstrip() == "jobs:":
            jobs_line = i
            break
    if jobs_line is None:
        raise AssertionError("no top-level 'jobs:' key found")

    jobs = {}
    current_name = None
    current_start = None
    i = jobs_line + 1
    while i < n:
        line = lines[i]
        if not _is_blank_or_comment(line):
            indent = _indent(line)
            if indent == 0:
                break  # left the jobs: mapping entirely
            if indent == 2 and line.strip().endswith(":"):
                if current_name is not None:
                    jobs[current_name] = (current_start, i)
                current_name = line.strip()[:-1]
                current_start = i + 1
        i += 1
    if current_name is not None:
        jobs[current_name] = (current_start, i)
    return jobs


def _find_steps(lines, start, end):
    """Returns [(step_start, step_end), ...] for the `steps:` sequence
    inside job body lines[start:end]. Assumes `steps:` is the job's LAST
    key (true for every job this file ships) -- the final step's range
    therefore extends to `end` rather than to a following sibling key."""
    steps_idx = None
    for i in range(start, end):
        if not _is_blank_or_comment(lines[i]) and lines[i].strip() == "steps:":
            steps_idx = i
            break
    if steps_idx is None:
        return []

    item_indent = None
    for i in range(steps_idx + 1, end):
        if _is_blank_or_comment(lines[i]):
            continue
        item_indent = _indent(lines[i])
        break
    if item_indent is None:
        return []

    boundaries = [
        i for i in range(steps_idx + 1, end)
        if not _is_blank_or_comment(lines[i])
        and _indent(lines[i]) == item_indent
        and lines[i].lstrip().startswith("- ")
    ]
    steps = []
    for idx, b in enumerate(boundaries):
        nxt = boundaries[idx + 1] if idx + 1 < len(boundaries) else end
        steps.append((b, nxt))
    return steps


def _comment_block_above(lines, idx, floor):
    """The contiguous run of comment-only lines immediately above
    lines[idx], never reading below `floor` (a step's own start) -- so a
    justification comment attached to an EARLIER step can never satisfy a
    later one's check."""
    j = idx - 1
    block = []
    while j >= floor and lines[j].strip().startswith("#"):
        block.append(lines[j])
        j -= 1
    return "\n".join(reversed(block))


# --- the three checks, plus one bonus consistency check ---------------------

def check_fetch_depth(lines, jobs):
    violations = []
    for job_name, (jstart, jend) in jobs.items():
        for (s, e) in _find_steps(lines, jstart, jend):
            block = lines[s:e]
            if not CHECKOUT_USES_RE.search("\n".join(block)):
                continue
            fd_lines = [s + i for i, l in enumerate(block) if FETCH_DEPTH_ZERO_RE.match(l)]
            if not fd_lines:
                violations.append(
                    f"job '{job_name}': a checkout step has no 'fetch-depth: 0' "
                    "(actions/checkout defaults to fetch-depth: 1, which breaks "
                    f"{JUSTIFICATION_ANCHOR}'s git-show-by-old-SHA test)"
                )
                continue
            for fd_line in fd_lines:
                comment_block = _comment_block_above(lines, fd_line, s)
                if JUSTIFICATION_ANCHOR not in comment_block:
                    violations.append(
                        f"job '{job_name}' line {fd_line + 1}: 'fetch-depth: 0' has "
                        f"no comment above it naming {JUSTIFICATION_ANCHOR} -- a "
                        "future cleanup could drop it as \"unused\""
                    )
    return violations


def check_bash_version_assert(lines, jobs):
    violations = []
    macos_job = None
    for job_name, (jstart, jend) in jobs.items():
        if re.search(r"runs-on:\s*macos-latest", "\n".join(lines[jstart:jend])):
            macos_job = (job_name, jstart, jend)
            break
    if macos_job is None:
        return ["no job runs on macos-latest -- ADR-0011 requires a macOS runner"]

    job_name, jstart, jend = macos_job
    steps = _find_steps(lines, jstart, jend)
    assert_idx = None
    checkout_idx = None
    for i, (s, e) in enumerate(steps):
        text = "\n".join(lines[s:e])
        if (
            assert_idx is None
            and BASH_VERSION_TOKEN in text
            and FLOOR_PREFIX_TOKEN in text
            and FAILING_EXIT_RE.search(text)
        ):
            assert_idx = i
        if checkout_idx is None and CHECKOUT_USES_RE.search(text):
            checkout_idx = i

    if assert_idx is None:
        violations.append(
            f"job '{job_name}': no step asserts the resolved bash version starts "
            "with 3.2 and fails otherwise (ADR-0011 decision 3)"
        )
    elif checkout_idx is not None and assert_idx > checkout_idx:
        violations.append(
            f"job '{job_name}': the bash-3.2 assert step (index {assert_idx}) runs "
            f"after checkout (index {checkout_idx}) -- ADR-0011 requires the "
            "interpreter to be verified before anything else in the job runs"
        )
    return violations


def check_no_swallowed_failures(lines):
    """Scans OPERATIVE lines only (every line whose stripped text does not
    start with '#') -- a YAML top-of-file comment or a shell '#' comment
    inside a `run:` block is free to NAME 'continue-on-error' or '|| true'
    while explaining the rule (this file's own header does exactly that)
    without tripping this check; only a line that could actually take
    effect counts."""
    operative_text = "\n".join(l for l in lines if not l.strip().startswith("#"))
    violations = []
    if "continue-on-error" in operative_text:
        violations.append(
            "'continue-on-error' present -- a divergence must fail the job, "
            "never be swallowed"
        )
    if re.search(r"\|\|\s*true\b", operative_text):
        violations.append(
            "'|| true' present -- same rule as continue-on-error: no swallowed "
            "failures"
        )
    return violations


def check_python_version_pinned(lines, jobs):
    violations = []
    versions = {}
    for job_name, (jstart, jend) in jobs.items():
        block = lines[jstart:jend]
        if not SETUP_PYTHON_USES_RE.search("\n".join(block)):
            continue
        found = [m.group(1) for l in block for m in [PYTHON_VERSION_RE.match(l)] if m]
        if not found:
            violations.append(
                f"job '{job_name}': uses actions/setup-python but does not pin a "
                "quoted python-version"
            )
        else:
            versions[job_name] = found[0]
    if len(set(versions.values())) > 1:
        violations.append(f"jobs pin different python-version values: {versions}")
    return violations


def lint_ci_workflow(path):
    """Returns a list of violation strings for `path` -- empty means every
    checked property holds. Never raises on a compliant OR a merely
    differently-shaped file; `_find_jobs`/`_find_steps` raising is reserved
    for a file this parser cannot make sense of at all (see
    RealWorkflowStructureTest for what IS asserted about the real file's
    shape)."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    jobs = _find_jobs(lines)
    violations = []
    violations += check_fetch_depth(lines, jobs)
    violations += check_bash_version_assert(lines, jobs)
    violations += check_no_swallowed_failures(lines)
    violations += check_python_version_pinned(lines, jobs)
    return violations


def _write_scratch(case, text):
    """Writes `text` to a scratch ci.yml under a throwaway directory,
    registered for cleanup on `case` (the calling TestCase) so mutation
    fixtures do not accumulate under the OS temp dir across runs."""
    tmpdir = Path(tempfile.mkdtemp(prefix="ccpr-ci-workflow-"))
    case.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
    scratch = tmpdir / "ci.yml"
    scratch.write_text(text, encoding="utf-8")
    return scratch


def _mutate_once(text, pattern, replacement):
    """`re.subn` wrapper that asserts the substitution actually matched
    exactly once -- a mutation that silently misses its target would make
    the RED proof it drives report the file's UNCHANGED (compliant) shape,
    passing for the wrong reason (G-141)."""
    mutated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise AssertionError(
            f"mutation pattern matched {count} time(s), expected exactly 1: {pattern!r}"
        )
    return mutated


# --- tests -------------------------------------------------------------------

class RealWorkflowStructureTest(unittest.TestCase):
    """Pins what the structural reader actually found in the real file --
    if `ci.yml` is ever reflowed in a way `_find_jobs`/`_find_steps` can no
    longer follow, this is what turns that into a loud, specific failure
    instead of every other test in this module silently checking nothing."""

    def test_ci_yml_exists(self):
        self.assertTrue(CI_YML.is_file(), f"missing: {CI_YML}")

    def test_job_names_and_runners(self):
        lines = CI_YML.read_text(encoding="utf-8").split("\n")
        jobs = _find_jobs(lines)
        self.assertEqual({"python-tests", "check-all-macos"}, set(jobs.keys()))
        for job_name, (s, e) in jobs.items():
            block = "\n".join(lines[s:e])
            if job_name == "python-tests":
                self.assertIn("runs-on: ubuntu-latest", block)
            else:
                self.assertIn("runs-on: macos-latest", block)

    def test_step_counts_per_job(self):
        lines = CI_YML.read_text(encoding="utf-8").split("\n")
        jobs = _find_jobs(lines)
        self.assertEqual(3, len(_find_steps(lines, *jobs["python-tests"])))
        self.assertEqual(5, len(_find_steps(lines, *jobs["check-all-macos"])))

    def test_agent_frontmatter_test_file_the_comments_reference_actually_exists(self):
        """The comments justifying fetch-depth: 0 name a specific test
        file -- if that file were ever renamed, the comment would still
        read fine while pointing at nothing. Cheap to keep honest."""
        self.assertTrue(
            AGENT_FRONTMATTER_TEST.is_file(),
            f"comments in {CI_YML.name} reference {JUSTIFICATION_ANCHOR}, "
            f"which no longer exists at {AGENT_FRONTMATTER_TEST}",
        )


class RealWorkflowIsCompliantTest(unittest.TestCase):
    """The GREEN half of the RED/GREEN pair every MutationTest below
    provides the RED half for."""

    def test_shipped_workflow_has_no_violations(self):
        self.assertEqual([], lint_ci_workflow(CI_YML))


class FetchDepthMutationTest(unittest.TestCase):
    def setUp(self):
        self.text = CI_YML.read_text(encoding="utf-8")

    def test_fetch_depth_one_instead_of_zero_is_flagged(self):
        mutated = _mutate_once(self.text, r"fetch-depth: 0", "fetch-depth: 1")
        scratch = _write_scratch(self, mutated)
        violations = lint_ci_workflow(scratch)
        self.assertTrue(
            any("fetch-depth: 0" in v for v in violations),
            f"mutation to fetch-depth: 1 was not flagged: {violations}",
        )

    def test_missing_fetch_depth_key_entirely_is_flagged(self):
        # Removes the WHOLE line, not just its value -- a structural
        # absence, not a value swap (already covered above).
        mutated = _mutate_once(self.text, r"\n\s*fetch-depth: 0\n", "\n")
        scratch = _write_scratch(self, mutated)
        violations = lint_ci_workflow(scratch)
        self.assertTrue(
            any("no 'fetch-depth: 0'" in v for v in violations),
            f"mutation removing fetch-depth: 0 entirely was not flagged: {violations}",
        )

    def test_fetch_depth_zero_without_its_justifying_comment_is_flagged(self):
        # Removes ONLY the one comment line naming the anchor test file,
        # from the FIRST (python-tests) job's checkout step -- the
        # fetch-depth: 0 key itself is left completely intact.
        mutated = _mutate_once(
            self.text,
            r"\n\s*# scripts/tests/test_agent_frontmatter\.py:154 pins\n",
            "\n",
        )
        scratch = _write_scratch(self, mutated)
        violations = lint_ci_workflow(scratch)
        self.assertTrue(
            any("no comment above it naming" in v for v in violations),
            f"removing the justifying comment line was not flagged: {violations}",
        )


class BashVersionAssertMutationTest(unittest.TestCase):
    def setUp(self):
        self.text = CI_YML.read_text(encoding="utf-8")

    def test_missing_assert_step_entirely_is_flagged(self):
        # Deletes the whole step block (its name line through its last
        # `esac` line) -- structural removal, not the file.
        mutated = _mutate_once(
            self.text,
            (
                r"\n\s*- name: Assert the resolved bash is 3\.2\.x \(ADR-0011 floor\)\n"
                r"(?:.*\n)*?\s*esac\n"
            ),
            "\n",
        )
        scratch = _write_scratch(self, mutated)
        violations = lint_ci_workflow(scratch)
        self.assertTrue(
            any("no step asserts the resolved bash version" in v for v in violations),
            f"removing the whole assert step was not flagged: {violations}",
        )

    def test_exit_1_softened_to_exit_0_is_flagged(self):
        # A behavioural mutation, not a presence/absence one: the step
        # still exists, still mentions 3.2 and BASH_VERSION, but no longer
        # actually fails the job on a mismatch.
        mutated = _mutate_once(self.text, r"\n\s*exit 1\n", "\n              exit 0\n")
        scratch = _write_scratch(self, mutated)
        violations = lint_ci_workflow(scratch)
        self.assertTrue(
            any("no step asserts the resolved bash version" in v for v in violations),
            f"softening exit 1 to exit 0 was not flagged: {violations}",
        )

    def test_assert_step_moved_after_checkout_is_flagged(self):
        # Swaps the ORDER of two whole step blocks (assert <-> checkout)
        # rather than deleting either -- proves the ordering check fires
        # independently of the presence check.
        checkout_block = (
            "      - name: Check out repository\n"
            "        uses: actions/checkout@v4\n"
            "        with:\n"
            "          # See the python-tests job's identical comment on this key: the\n"
            "          # python-tests check inside check-all.sh below runs the exact\n"
            "          # same scripts/tests/test_agent_frontmatter.py, which needs full\n"
            "          # history to `git show` PRE_FIX_COMMIT.\n"
            "          fetch-depth: 0\n"
        )
        self.assertIn(checkout_block, self.text, "fixture drifted from ci.yml's real text")
        without_checkout = self.text.replace(checkout_block, "", 1)
        assert_marker = "      - name: Assert the resolved bash is 3.2.x (ADR-0011 floor)"
        self.assertIn(assert_marker, without_checkout)
        mutated = without_checkout.replace(assert_marker, checkout_block + assert_marker, 1)
        scratch = _write_scratch(self, mutated)
        violations = lint_ci_workflow(scratch)
        self.assertTrue(
            any("runs after checkout" in v for v in violations),
            f"moving checkout ahead of the assert step was not flagged: {violations}",
        )


class SwallowedFailureMutationTest(unittest.TestCase):
    def setUp(self):
        self.text = CI_YML.read_text(encoding="utf-8")

    def test_continue_on_error_is_flagged(self):
        mutated = _mutate_once(
            self.text,
            r"(\n\s*- name: Run check-all\.sh\n)",
            r"\1        continue-on-error: true\n",
        )
        scratch = _write_scratch(self, mutated)
        violations = lint_ci_workflow(scratch)
        self.assertTrue(
            any("continue-on-error" in v for v in violations),
            f"inserted continue-on-error was not flagged: {violations}",
        )

    def test_bare_or_true_is_flagged(self):
        mutated = _mutate_once(
            self.text,
            r"/bin/bash scripts/check-all\.sh \.\n",
            "/bin/bash scripts/check-all.sh . || true\n",
        )
        scratch = _write_scratch(self, mutated)
        violations = lint_ci_workflow(scratch)
        self.assertTrue(
            any("|| true" in v for v in violations),
            f"inserted '|| true' was not flagged: {violations}",
        )


class PythonVersionConsistencyMutationTest(unittest.TestCase):
    def test_mismatched_python_versions_across_jobs_is_flagged(self):
        text = CI_YML.read_text(encoding="utf-8")
        mutated = _mutate_once(text, r'python-version: "3\.11"\n', 'python-version: "3.12"\n')
        scratch = _write_scratch(self, mutated)
        violations = lint_ci_workflow(scratch)
        self.assertTrue(
            any("different python-version" in v for v in violations),
            f"mismatched python-version across jobs was not flagged: {violations}",
        )
