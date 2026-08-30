r"""test_run_tests_mktemp_templates.py -- WI-0129: two of run-tests.sh's five
`mktemp` calls use a template with a fixed SUFFIX after the `XXXXXX` run
(`mktemp /tmp/pytest-report-XXXXXX.json`, `mktemp /tmp/jest-report-XXXXXX.json`).

BSD `mktemp` (the shipped macOS `/bin/mktemp`, the floor platform per this
project's own constraint) only substitutes a TRAILING run of `X`s. A
template with literal characters after that run is returned UNSUBSTITUTED on
the first call, and fails outright on any call that follows while the same
literal path still exists on disk:

    $ mktemp /tmp/probe-XXXXXX.txt
    /tmp/probe-XXXXXX.txt                              <- literal, not random
    $ mktemp /tmp/probe-XXXXXX.txt
    mktemp: mkstemp failed on /tmp/probe-XXXXXX.txt: File exists

Every path this produces is therefore PREDICTABLE in a shared, world-writable
`/tmp` -- the actual concern (a concurrent invocation, or a symlink placed at
the guessable name ahead of time, wins the race) is broader than the
second-run failure the reproduction above shows, but the failure is the
cheapest way to prove the underlying defect in a test.

A second, related defect at the same call sites: `run_pytest()` also reads
and writes a hardcoded, non-randomized path (`/tmp/pytest-cov.json`) for the
coverage JSON report, never through `mktemp` at all -- same predictable-
shared-`/tmp` property, different code shape.

## Why a new module

Neither `test_run_tests_argument_quoting.py` (subject: the `TEST_PATH` CLI
argument reaching a runner unquoted) nor `test_run_tests_heredoc_injection.py`
(subject: untrusted runner STDOUT closing a heredoc's Python string early)
touches `mktemp` at all -- grepped both files for `mktemp` before writing
this one, no hits. This module's subject -- the TEMPLATE run-tests.sh hands
to `mktemp` itself, before any runner or heredoc is involved -- is orthogonal
to both, so it gets its own file rather than growing either docstring with
an unrelated concern (same reasoning `test_run_tests_argument_quoting.py`'s
own docstring gives for not extending the heredoc-injection module).

## General rule, not two hardcoded line checks

`_extract_mktemp_templates` scans the actual file content for every `mktemp`
invocation rather than asserting against lines 53 and 186 specifically, so a
future new `mktemp` call added to this file is covered automatically. Ran
the extraction against the file BEFORE any fix was applied and printed the
result to confirm it flags exactly the two known-broken templates
(`/tmp/pytest-report-XXXXXX.json`, `/tmp/jest-report-XXXXXX.json`) and
leaves the three already-correct ones (`pytest-raw`, `cargo-raw`, `go-raw`
-- no suffix after `XXXXXX`) alone.

## Behavioural proof runs the file's OWN templates, not a synthetic one

`test_mktemp_templates_do_not_collide_on_repeated_calls` calls the real
`mktemp` binary twice, back to back, with each template `_extract_mktemp_
templates` found in `scripts/run-tests.sh` -- reproducing the exact
first-call/second-call reproduction from the module docstring above, but
against every template this file actually ships, so it also regression-
guards the three templates that were already correct. Invoking `run-tests.sh`
end to end here would additionally need a real (or faked) `pytest`/`npx`
toolchain and would only exercise ONE mktemp call per full run, since
`run_pytest()`/`run_jest_or_vitest()` each clean up their own tmpfile before
returning -- two full, separate, sequential invocations would not reproduce
the collision at all (the first run's cleanup removes the literal path
before the second run's `mktemp` call ever sees it). Calling `mktemp`
directly with the file's own template, twice, WITHOUT an intervening cleanup
in between, is the minimal harness that actually forces the collision this
bug produces under concurrent/overlapping runs.
"""

import os
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_TESTS = REPO_ROOT / "scripts" / "run-tests.sh"

# Matches an actual `mktemp` INVOCATION -- `$(mktemp ...)` -- not a bare
# mention of the word "mktemp" in a comment. Every call site in this file
# is a command substitution of this shape (`x=$(mktemp <template>)`); a
# plain `\bmktemp\b` would also match prose like "BSD mktemp only
# substitutes..." in an explanatory comment, which is not a call at all.
_MKTEMP_CALL_RE = re.compile(r"\$\(\s*mktemp\b([^)]*)\)")


def _extract_mktemp_templates(script_text):
    """Returns the template argument (if any) of every `mktemp` invocation
    found in `script_text`, in source order. An entry is `""` for a bare
    `mktemp` call with no template argument at all."""
    templates = []
    for match in _MKTEMP_CALL_RE.finditer(script_text):
        rest = match.group(1).strip()
        token = rest.split(None, 1)[0] if rest else ""
        templates.append(token)
    return templates


def _is_safe_template(template):
    """A template is safe if it has no argument at all (bare `mktemp`) or
    if it ends in a trailing run of `X`s with nothing after it -- BSD
    `mktemp` only substitutes a TRAILING run, so any literal character
    after the last `X` is returned verbatim instead of randomized."""
    if template == "":
        return True
    return re.search(r"X+$", template) is not None


class MktempTemplateStructureTest(unittest.TestCase):
    def test_all_mktemp_calls_end_in_a_bare_placeholder_run(self):
        script_text = RUN_TESTS.read_text()
        templates = _extract_mktemp_templates(script_text)

        self.assertTrue(templates, "expected to find mktemp calls in run-tests.sh")

        unsafe = [t for t in templates if not _is_safe_template(t)]
        self.assertEqual(
            [],
            unsafe,
            "run-tests.sh has mktemp template(s) with a literal suffix after "
            f"the XXXXXX run -- BSD mktemp won't randomize these: {unsafe} "
            f"(all templates found: {templates})",
        )

    def test_no_hardcoded_pytest_cov_json_path_remains(self):
        script_text = RUN_TESTS.read_text()
        self.assertNotIn(
            "/tmp/pytest-cov.json",
            script_text,
            "run-tests.sh still references the hardcoded, non-randomized "
            "/tmp/pytest-cov.json path -- it must be generated via mktemp "
            "like every other scratch file in this script",
        )


class MktempTemplateCollisionTest(unittest.TestCase):
    def test_mktemp_templates_do_not_collide_on_repeated_calls(self):
        script_text = RUN_TESTS.read_text()
        templates = _extract_mktemp_templates(script_text)
        self.assertTrue(templates, "expected to find mktemp calls in run-tests.sh")

        created_paths = []
        self.addCleanup(
            lambda: [os.path.exists(p) and os.remove(p) for p in created_paths]
        )

        for template in templates:
            args = ["mktemp"] + ([template] if template else [])

            first = subprocess.run(args, capture_output=True, text=True, timeout=10)
            self.assertEqual(
                0,
                first.returncode,
                f"first `mktemp {template!r}` call failed unexpectedly: "
                f"{first.stderr!r}",
            )
            first_path = first.stdout.strip()
            created_paths.append(first_path)

            second = subprocess.run(args, capture_output=True, text=True, timeout=10)
            if second.returncode == 0:
                created_paths.append(second.stdout.strip())
            self.assertEqual(
                0,
                second.returncode,
                f"second `mktemp {template!r}` call collided with the "
                f"first (BSD mktemp only substitutes a trailing XXXXXX run "
                f"-- a literal suffix after it makes every call return the "
                f"same, non-random path): {second.stderr!r}",
            )
            second_path = second.stdout.strip()
            self.assertNotEqual(
                first_path,
                second_path,
                f"mktemp template {template!r} produced the identical path "
                f"on both calls ({first_path}) -- it is not being randomized",
            )


if __name__ == "__main__":
    unittest.main()
