"""commonmark.py -- WI-0129 Teil 1: a RECORDED double of the real
`commonmark` package (never vendored/committed here -- only its measured
OUTPUT is), used exclusively by
test_memory_lint_commonmark_corpus.GeneratorDocumentedIntentValidationTest's
three subprocess invocations of
scripts/tests/fixtures/generate_commonmark_corpus.py.

Why a double is correct here, and why it is BETTER than the real package
for this specific job (PO decision, 30.08.2026): those three tests prove
the generator's refusal branches -- whether it correctly rejects an entry
whose `known_divergence`/`documented_intent` claim does not match what the
two oracles actually measured. The branch taken depends entirely on
`actually_diverges` (reference output vs. check (n)'s output), a value the
real `commonmark` package would compute the SAME way every time for the
same input -- there is nothing about running the genuine CommonMark
algorithm that these tests are trying to verify (that is
CommonmarkCorpusDifferentialTest's and FixtureIntegrityTest's job, against
the frozen 65-entry corpus, elsewhere in the same file). A recorded double
means the value that decides which branch fires is under THIS module's
control, verifiably tied to a real measurement, rather than hoping the
corpus entry happens to land on the right side of whatever a particular
commonmark VERSION currently does.

Every value below is MEASURED, never invented -- see
commonmark_recorded_outputs.json (same directory), which also carries the
package version and capture date. A hand-typed HTML string here would be
exactly finding F2 in new clothes: an expectation built from our own
assumption of what commonmark says, not from what it actually said. This
module only loads that JSON and replays it verbatim by exact markdown-text
lookup -- it contains no CommonMark logic of its own, cannot render a
NOVEL Markdown string, and refuses (loudly, never silently) any input the
recording does not cover.

## What this module does NOT prove

Once this double is on a subprocess's PYTHONPATH, nothing in that run
touches the real `commonmark` package -- the generator's own interaction
with a CURRENT `commonmark` install (whether a future package version
changes `commonmark.commonmark()`'s HTML output shape, its `<a href>`
attribute quoting, or a corner case in entity decoding) is exercised
NOWHERE by GeneratorDocumentedIntentValidationTest, before or after this
double existed. The PO accepted this trade-off explicitly (30.08.2026):
`generate_commonmark_corpus.py` is a manual, occasionally-run handgrip
(see its own docstring), not something CI exercises against a live
package on every run, and the 46 OTHER tests in this module
(CommonmarkCorpusDifferentialTest / FixtureIntegrityTest /
MutationProvesTheDifferentialTestCanFail) already hold the generator's
PAST commonmark interaction accountable via the frozen, 65-entry
`commonmark_corpus.json` -- itself produced by one real run of the real
package, at a version and date that fixture's own provenance field
records. If a future commonmark release changes shape, the person who next
runs `generate_commonmark_corpus.py` by hand (its own docstring names when)
is the one who will see it -- not this test suite, and not this double. If
that gap ever needs closing, the fallback path is the declared-test-
dependency option this decision (rightly) does not choose today: add
`commonmark` to a documented, installed-in-CI test requirement and let the
real package run here again.

## Isolation

This directory is placed on `PYTHONPATH` ONLY by
test_memory_lint_commonmark_corpus.py's `_run_generator_copy()`, and ONLY
for `GeneratorDocumentedIntentValidationTest`'s three tests -- no other
test in that module, no other module in this suite, and no real,
manually-run `generate_commonmark_corpus.py` invocation ever sees this
double. A machine with the real `commonmark` package installed still gets
THIS double in those three subprocesses, because PYTHONPATH entries are
searched before site-packages; a machine WITHOUT it gets the exact same
behaviour, which is the whole point.
"""

import json
from pathlib import Path

_RECORDED_PATH = Path(__file__).resolve().parent / "commonmark_recorded_outputs.json"

with open(_RECORDED_PATH, encoding="utf-8") as _f:
    _RECORDING = json.load(_f)

_HTML_BY_MARKDOWN = {entry["markdown"]: entry["html"] for entry in _RECORDING["entries"]}


def commonmark(markdown_text):
    try:
        return _HTML_BY_MARKDOWN[markdown_text]
    except KeyError:
        raise RuntimeError(
            "commonmark double "
            "(scripts/tests/fixtures/commonmark_double/commonmark.py) has no "
            f"recorded output for this markdown text: {markdown_text!r}. This "
            "double only covers the synthetic entries "
            "GeneratorDocumentedIntentValidationTest uses today -- re-run "
            "scripts/tests/fixtures/record_commonmark_double.py against the "
            "REAL commonmark package to add a recording for a new entry; do "
            "not hand-write one."
        ) from None
