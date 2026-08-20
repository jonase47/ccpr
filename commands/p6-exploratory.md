# /p6-exploratory – Exploratory Tests

Conducts unstructured, experience-based tests that automated tests and defined test cases do not cover. The goal is to find unexpected behaviours, usability issues, and hidden bugs that remain invisible in structured testing.

## Argument: $ARGUMENTS = [focus area, e.g. "form validation", "mobile usage", "error handling"]

If provided: Focus exploratory tests on the specified area.
If not provided: Read FEATURES.md and TESTPROTOCOL_FUNCTIONAL.md and select areas that have received little test attention so far. If any context is missing, ask about the application area.

## 0. Work-item adoption guard (ADR-0002 §8)

Usability findings from this command are **optional** backlog items (see Result) — this guard only
applies if the user chooses to capture one.

Run `python3 ~/.claude/scripts/workitems.py list`.
- **Non-empty array** → the project uses the structured store. If the user opts to capture a
  usability finding as a backlog item, use the CLI (step 3 below) instead of BACKLOG.md prose.
- **`[]` and no `docs/workitems/` directory** → still on prose. Append to BACKLOG.md as before, if
  chosen. Emit one line: *"Tip: run `lift` to adopt the structured work-item store."*
- **`[]` but `docs/workitems/` exists** → adopted store, just empty right now. Treat as adopted: use
  the CLI, not the prose fallback.

See Manual/WORKITEMS.md §8 for the full guard rationale and the status-verb mapping.

## Execution

### 1. Read Context
Read the following files (if present):
- **TESTPROTOCOL_FUNCTIONAL.md** (what has already been tested → identify gaps)
- **USER_JOURNEYS.md** (personas as test perspectives)
- **UX_CONCEPT.md** (UX expectations – does the real behaviour deviate?)
- **FEATURES.md** (full scope of the application)

### 2. Delegation to QA-Tester Agent (Lead)
Delegate the exploratory tests to the **qa-tester** agent:

> Run exploratory tests for: **$ARGUMENTS**
> Context: [Insert previous test results from TESTPROTOCOL_FUNCTIONAL.md, personas from USER_JOURNEYS.md]
>
> Exploratory tests follow no fixed script. Instead, use the following heuristics and techniques:
>
> **A. Perspective Shifts**
> Test from different user perspectives:
> - Experienced user: Fast, unexpected actions (double-clicking, rapid scrolling, multiple tabs)
> - Impatient user: Clicking buttons multiple times, abandoning forms, navigating back
> - Curious user: All edge menus, hidden features, unusual combinations
> - Error-prone user: Invalid inputs, very long texts, special characters, emojis, SQL injections
>
> **B. Explore State Boundaries**
> - What happens with empty states (no data, fresh account)?
> - What happens with large amounts of data (performance, layout)?
> - What happens during transitions between states (simultaneous actions)?
> - What happens with interrupted actions (navigation mid-process)?
>
> **C. Technical Edge Cases**
> - Behaviour on slow connections / timeout
> - Behaviour when external services are unavailable
> - Behaviour with browser back button in critical flows
> - Behaviour on session expiry mid-action
>
> **D. Usability Observations**
> Also document observations that are not bugs but impair the user experience:
> - Confusing error messages
> - Unclear states (is the page still loading? Was the action successful?)
> - Inconsistent behaviour between similar features
>
> For each finding: description, reproduction steps, severity, category (Bug / Usability / Enhancement)

### 3. Optionally Capture Usability Findings as Work Items
Per the Result section below, this is optional — most findings just stay documented in the
EXPLORATORY.md protocol (step 4). Only when the user chooses to carry a usability finding forward
into the backlog, using the guard result from step 0:
- Structured store: `workitems create --title "<finding>" --type chore --description "<finding +
  reproduction>"` (check the full, unfiltered `workitems list` for a matching title first — trim +
  casefold — so a re-run never duplicates an already-captured finding; record the assigned
  `**Work-Item:** WI-NNNN` id in EXPLORATORY.md's `## Findings` entry).
- Prose fallback: add it to `docs/planning/BACKLOG.md` as before.

### 4. Write Detail File
Write the result to `docs/quality/EXPLORATORY.md` (overwrite if it exists). Start with:

```yaml
---
phase: P6
subskill: exploratory
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Test Scope & Heuristics`, `## Findings` (description, reproduction, severity, category per finding), `## Overall Assessment`.

### 5. Update Phase Index
Update `docs/quality/QA.md` (the P6 phase index, created from template if missing — see `~/.claude/docs/PROJECT_PHASES.md`):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[EXPLORATORY.md](EXPLORATORY.md)` with status `complete`.
- Lift any High/Critical bug or recurring usability concern into **Open Risks** of the phase index.

## Result

- **`docs/quality/EXPLORATORY.md`** (exploratory test protocols with findings)
- **`docs/quality/QA.md`** (phase index updated)
- Bugs as input for `/p6-bugfix`
- Usability findings optionally as new work items (structured store) or backlog items in `docs/planning/BACKLOG.md` (prose fallback)

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 useful next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
