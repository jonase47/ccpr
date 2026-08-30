"""test_platform_conditional_skip_budget.py -- WI-0129 CI-hardening: pins
the NUMBER of platform/toolchain-conditional test skips this repository's
test suite produces, so the skip set cannot silently grow.

Why this exists: a skip is a check that did NOT run. `check-all.sh`'s own
could-not-run idiom already treats "verified nothing" as distinct from "a
pass" (KA-G-017) at the CHECK level; nothing did the equivalent at the
individual-TEST level until now. Four sources today carry a
`@unittest.skipUnless`/`skipIf` whose condition depends on the machine
running it rather than on anything the test itself controls:

  * test_shellcheck_run.py -- ShellcheckRunsTest (7 methods) and
    SelfCheckTest's one method, gated on a reachable `shellcheck` binary.
  * test_memory_sync_promote.py -- UsageHintOnBash32Test's one canary
    method, gated on the resolved `/bin/bash` being 3.x.
  * test_quality_scan.py -- QualityScanQuotingMutationTest's two mutation
    tests, gated on the PATH-resolved `bash` being 3.x (ADR-0011 decision
    4: the bash-3.2 parser bug this mutation reproduces does not exist in
    bash 4+, so on a bash-5 machine the mutation reproduces nothing to
    assert against).
  * test_handover_size_hook.py -- one method gated on `os.mkfifo` existing
    (true on every POSIX platform this repo's two CI runners use; kept so a
    future non-POSIX runner is accounted for rather than assumed
    impossible).

NOT a flat "N skips per platform" pin. A first version of this module tried
that (Darwin: 8, Linux: 3) and it is WRONG for any contributor whose local
machine differs from the two CI runners' specific toolchain state -- this
machine has Homebrew shellcheck reachable, so it skips 0 of
test_shellcheck_run.py's tests where the macOS CI runner (no reachable
shellcheck) skips 8. Whether shellcheck happens to be installed is a
per-MACHINE fact, not a per-PLATFORM one. Instead, the expected count is
DERIVED from each source's own already-computed condition -- the exact same
global each `skipUnless` decorator itself reads -- multiplied by a PINNED
per-source method count. That pin is what moves (and fails loudly) when a
method is added to or removed from a gated class; the condition itself
supplies whether that source contributes 0 or its pinned count on THIS
machine, so the same assertion is correct on a contributor's laptop, on the
macOS runner, and on the Ubuntu runner alike.

This module does NOT run `scripts.tests.discover()` -- CLAUDE.md's own
constraint forbids running the full suite from inside a probe, and it would
also be slow for no reason: importing the four modules above is enough,
since Python's `unittest.skipUnless`/`skipIf` evaluate their condition and
stamp `__unittest_skip__`/`__unittest_skip_why__` directly onto the
function or class AT DECORATION TIME (import time), not at run time. Asking
each loaded test for that same attribute the real test runner already
checks in `TestCase.run()` measures what actually happened -- never a
second, independently re-typed copy of each condition (G-134: a literal
register cannot check itself against a copy of itself).
"""

import os
import re
import unittest
from pathlib import Path

from . import test_handover_size_hook
from . import test_memory_sync_promote
from . import test_quality_scan
from . import test_shellcheck_run

TESTS_DIR = Path(__file__).resolve().parent

# `expected_skip_count()` below only knows how to derive a count from these
# four sources -- a brand new `@unittest.skipUnless`/`skipIf` added to some
# FIFTH file would silently sit outside that arithmetic, contributing 0 by
# construction rather than failing loudly. This registers which FILENAMES
# are allowed to carry one at all, closing that gap independently of the
# per-source counting above.
_REGISTERED_SKIP_DECORATOR_FILES = {
    "test_handover_size_hook.py",
    "test_memory_sync_promote.py",
    "test_quality_scan.py",
    "test_shellcheck_run.py",
}

_SKIP_DECORATOR_RE = re.compile(r"@unittest\.skip(?:Unless|If)\(")


def files_with_skip_decorators():
    """A plain textual scan (no `ast`, no `subprocess`) across every
    `scripts/tests/**/*.py` file for a `@unittest.skipUnless`/`skipIf`
    occurrence -- deliberately coarser than counting methods (that is
    `expected_skip_count()`'s job for the four registered sources); this
    only answers "which FILES carry one at all", so a new site anywhere in
    the corpus is caught even before anyone teaches this module how to
    count it."""
    found = set()
    for path in sorted(TESTS_DIR.rglob("*.py")):
        if path.name == "test_platform_conditional_skip_budget.py":
            # This module's own docstring/comments mention the decorator by
            # name in prose -- excluded from the scan of ITSELF to avoid a
            # false positive; it is already in the registered set above.
            continue
        text = path.read_text(encoding="utf-8")
        if _SKIP_DECORATOR_RE.search(text):
            found.add(path.name)
    return found

# Referenced only by attribute (`<module>.<Name>`), never imported by name --
# binding a TestCase subclass into THIS module's namespace would make
# unittest's own discovery pick it up a second time here.
_SKIP_SOURCE_MODULES = (
    test_handover_size_hook,
    test_memory_sync_promote,
    test_quality_scan,
    test_shellcheck_run,
)


def _iter_tests(suite):
    """Flattens a (possibly nested) TestSuite into its individual test
    cases, mirroring how unittest's own runner walks a loaded suite."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def _is_skipped(test):
    """Reproduces `TestCase.run()`'s own skip check EXACTLY
    (`unittest/case.py`): `@unittest.skipUnless`/`skipIf` stamp
    `__unittest_skip__` onto the CLASS when applied to a class, but onto
    the individual test METHOD FUNCTION when applied to a method -- e.g.
    SelfCheckTest's one gated method carries it on the function, not on
    SelfCheckTest itself. `getattr(test_instance, "__unittest_skip__")`
    only ever sees the class-level case (an instance attribute lookup
    named "__unittest_skip__" never reaches a DIFFERENTLY-named method's
    own custom attribute) -- it silently missed every method-level skip
    the first time this module was measured, undercounting by exactly the
    method-level sources. Looking the method up via the class and reading
    THAT function's attribute (a bound method proxies unknown attribute
    access to `__func__`, same as `getattr(testMethod, ...)` inside
    `TestCase.run()` itself) is the only way to see both shapes."""
    test_method = getattr(type(test), test._testMethodName)
    return bool(
        getattr(type(test), "__unittest_skip__", False)
        or getattr(test_method, "__unittest_skip__", False)
    )


def skipped_test_ids():
    """Every test id, across `_SKIP_SOURCE_MODULES`, that unittest has
    ALREADY marked to skip in the current environment -- measured via the
    same `__unittest_skip__` attribute `TestCase.run()` reads, not a
    reimplementation of each module's condition."""
    loader = unittest.TestLoader()
    ids = []
    for module in _SKIP_SOURCE_MODULES:
        for test in _iter_tests(loader.loadTestsFromModule(module)):
            if _is_skipped(test):
                ids.append(test.id())
    return sorted(ids)


# Per-source pinned method counts -- the numbers that move (and must be
# updated here) when a gated class gains or loses a test method. Each is
# multiplied by that source's OWN condition, re-read from the gated
# module's own global, never re-derived independently.
#
#   source / count   when
#   shellcheck / 8   WI-0129 D2 (30.08.2026): ShellcheckRunsTest's 7
#                     methods + SelfCheckTest's 1, all gated on
#                     REAL_SHELLCHECK_DIR.
#   quality_scan / 2 WI-0129 CI-hardening (30.08.2026):
#                     QualityScanQuotingMutationTest's two bash-3.2-only
#                     mutation tests.
#   memory_sync / 1  Pre-existing (WI-0012): UsageHintOnBash32Test's one
#                     canary method.
#   fifo / 1         Pre-existing: test_handover_size_hook.py's one
#                     FIFO-gated method.
def expected_skip_count():
    count = 0
    if test_shellcheck_run.REAL_SHELLCHECK_DIR is None:
        count += 8
    if (test_quality_scan.RESOLVED_BASH_VERSION or (99, 0))[0] >= 4:
        count += 2
    system_bash_version = test_memory_sync_promote._bash_major_minor(
        test_memory_sync_promote.SYSTEM_BASH
    )
    if (system_bash_version or (99, 0))[0] >= 4:
        count += 1
    if not hasattr(os, "mkfifo"):
        count += 1
    return count


class PlatformConditionalSkipBudgetTest(unittest.TestCase):
    def test_skip_count_matches_the_pinned_per_source_budget(self):
        actual_ids = skipped_test_ids()
        self.assertEqual(
            expected_skip_count(), len(actual_ids),
            "the number of platform/toolchain-conditional test skips moved "
            "on this machine. If this is expected -- a method was added to "
            "or removed from a gated class, a new skipUnless/skipIf source "
            "should be added to _SKIP_SOURCE_MODULES, or an existing "
            "condition's shape changed -- re-measure and update the "
            "per-source pinned count in expected_skip_count() plus its "
            f"trajectory comment. Currently skipped: {actual_ids}",
        )

    def test_no_unregistered_skip_decorator_file_exists(self):
        found = files_with_skip_decorators()
        new = found - _REGISTERED_SKIP_DECORATOR_FILES
        stale = _REGISTERED_SKIP_DECORATOR_FILES - found
        self.assertEqual(
            set(), new,
            f"a new platform/toolchain-conditional skipUnless/skipIf "
            f"appeared in a file this module does not know about yet: "
            f"{sorted(new)}. Add it to _SKIP_SOURCE_MODULES and "
            "_REGISTERED_SKIP_DECORATOR_FILES, and teach "
            "expected_skip_count() how to derive its contribution -- do "
            "not let it sit outside the pinned budget uncounted.",
        )
        self.assertEqual(
            set(), stale,
            f"a file registered as carrying a platform/toolchain-"
            f"conditional skip no longer does: {sorted(stale)}. Remove it "
            "from _SKIP_SOURCE_MODULES and _REGISTERED_SKIP_DECORATOR_"
            "FILES, and its contribution from expected_skip_count() -- a "
            "stale entry here hides a scanner that stopped enumerating "
            "what it claims to.",
        )
