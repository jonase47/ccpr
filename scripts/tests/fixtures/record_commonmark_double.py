#!/usr/bin/env python3
"""record_commonmark_double.py -- WI-0129 Teil 1: captures the REAL
`commonmark` package's output for the synthetic corpus entries
`GeneratorDocumentedIntentValidationTest` (in
scripts/tests/test_memory_lint_commonmark_corpus.py) exercises, and writes
the recording to commonmark_double/commonmark_recorded_outputs.json next to
this script.

Why a recording, not a hand-written double: those three tests run
generate_commonmark_corpus.py as a SUBPROCESS to prove its refusal
branches, and that subprocess needs SOME `commonmark` module on its
PYTHONPATH -- but the real package is a probe dependency
(docs/memory/reference_commonmark-conformance.md), not something every
contributor's machine has. A hand-typed HTML string for what `commonmark`
"should" return would be exactly the class of bug WI-0129 finding F2 was:
the expectation coming from OUR assumption of the tool's behaviour rather
than the tool's actual, measured answer. Recording the real package's
output once (this script) and replaying it verbatim (commonmark_double/
commonmark.py) keeps the assertion pointed at reality instead of at our
own belief about it.

Manual, documented handgrip -- NOT run automatically by the test suite,
mirroring generate_commonmark_corpus.py's own discipline for the identical
reason: a recording is not manufactured from a guess, and its staleness
must be visible (`captured_on` / `commonmark_version` below), never
silently assumed current. Re-run this ONLY when:

  * `GeneratorDocumentedIntentValidationTest`'s three synthetic entries
    (`_ENTRY_INTENT_AGREES` / `_ENTRY_BOTH_BLOCKS` / `_ENTRY_NEITHER_BLOCK`)
    change their markdown, or a fourth synthetic entry is added that needs
    its own recording, or
  * the installed `commonmark` package version changes (this script writes
    the measured version into the JSON as provenance, so a stale recording
    is a dated fact, not a hidden assumption).

Requires the real `commonmark` package installed -- a probe dependency for
THIS script, never a runtime dependency of anything shipped:

    python3 -m pip install --quiet commonmark
    python3 scripts/tests/fixtures/record_commonmark_double.py

The three entries' markdown is read DIRECTLY from the test class's own
attributes below, never retyped here -- a second, independently-typed copy
of the same literal is exactly the kind of drift risk this repository's own
instinct G-134 warns about (two literal registers cannot check each
other).
"""

import json
import sys
from datetime import date
from importlib import metadata as importlib_metadata
from pathlib import Path

import commonmark

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.tests.test_memory_lint_commonmark_corpus import (  # noqa: E402
    GeneratorDocumentedIntentValidationTest as SyntheticEntries,
)

OUTPUT_PATH = Path(__file__).resolve().parent / "commonmark_double" / "commonmark_recorded_outputs.json"

ENTRIES = (
    SyntheticEntries._ENTRY_INTENT_AGREES,
    SyntheticEntries._ENTRY_BOTH_BLOCKS,
    SyntheticEntries._ENTRY_NEITHER_BLOCK,
)


def main():
    version = importlib_metadata.version("commonmark")
    recorded = []
    for entry in ENTRIES:
        markdown_text = entry["markdown"]
        html = commonmark.commonmark(markdown_text)
        recorded.append({"name": entry["name"], "markdown": markdown_text, "html": html})

    fixture = {
        "commonmark_version": version,
        "captured_on": date.today().strftime("%d.%m.%Y"),
        "captured_by": "scripts/tests/fixtures/record_commonmark_double.py",
        "captured_from": commonmark.__file__,
        "entries": recorded,
    }
    OUTPUT_PATH.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH} ({len(recorded)} entries, commonmark {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
