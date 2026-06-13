# /cleanup – Doc Hygiene: HANDOVER cap + lint aggregator

Runs a one-shot hygiene pass on a project's docs to keep them lean and
machine-readable: HANDOVER size cap enforcement plus the three existing lint
scripts (`memory-lint.sh`, `phase-docs-lint.sh`, `doc-volume-check.sh`) bundled
into one consolidated drift report. Use this between phases (after a Gate)
or whenever the project-guide warns about HANDOVER size, stale memory or doc
volume drift.

## Argument: $ARGUMENTS = [optional: projectdir]

- Without argument: operates on `$(pwd)`.
- With argument: operates on the given project directory.

## Flow

### 1. HANDOVER size cap enforcement (auto with confirm)

Read `docs/HANDOVER.md` size (bytes) and line count.

Determine the cap:
- Parse the file's own header for a line like `Size cap: ≤N KB` or `≤N KB`.
- If not present, fall back to the global Template default: **5 KB / 150 lines**.

Compare:
- **Under cap** → report "HANDOVER under cap (X KB / Y lines)" and continue.
- **Over cap** → identify the oldest archivable block. Heuristic, in order:
  1. The earliest `## Postmortem-Epilogue (DD.MM.YYYY …)` section (datable session block).
  2. Failing that, the earliest top-level `## ` section that contains a date in its heading.
  3. Failing that, the oldest `## Last Action` / `## What Was Achieved` block (when the file uses the template structure).

Show the user the candidate block (heading + first 5 lines) and **ask for confirmation** before archiving. Do **not** archive silently.

On confirm:
- Extract the block to `docs/.handover-archive/<YYYY-MM-DD>-<slug>.md`. Pick `<YYYY-MM-DD>` from the block's header date if present, else today. `<slug>` is a kebab-case derivation of the heading.
- Remove the block from `docs/HANDOVER.md`.
- Re-measure. If still over cap, loop with the next-oldest candidate (re-confirm each time).

On decline: report the over-cap state and continue without archiving.

### 2. Memory lint (read-only)

Run `bash ~/.claude/scripts/memory-lint.sh [projectdir]`. Show:
- Exit code (0 clean / 1 warnings / 2 errors)
- Up to the first 10 issue lines from stdout (truncate the rest with a `… N more` note).

Do not auto-fix. Lint-suggested actions (e.g. `status: stale`) belong to the user.

### 3. Phase-docs lint (read-only)

Run `bash ~/.claude/scripts/phase-docs-lint.sh [projectdir]`. Same output handling as §2.

### 4. Doc-volume check (read-only)

Run `bash ~/.claude/scripts/doc-volume-check.sh [projectdir]/docs`. Same output handling as §2. Volume warnings (≥25/40/50 KB) typically point at splitting work — surface the top 3 offenders for the user to consider.

### 5. Consolidated drift report

Print a compact summary table at the end:

```
Drift Report — <project>
| Check               | Status      | Action |
|---|---|---|
| HANDOVER cap        | ok | over | n/a  | <none / archived N blocks / suggested archive> |
| memory-lint         | clean | warn | error | <command to inspect> |
| phase-docs-lint     | clean | warn | error | <command to inspect> |
| doc-volume          | clean | warn | error | <top offender + split hint> |
```

Then offer 1–3 concrete next-step commands:
- For lint warnings: the exact lint invocation to see full output
- For doc volume: the largest file plus a suggested split target
- For phase-doc status issues: a pointer to the schema (`templates/PHASE_DOC_SCHEMA.md`)

## When to use

Recommended triggers:
- After a Gate has been passed (especially gates p4–p7 where phase docs accumulate)
- When `project-guide` flags Cleanup-Awareness (HANDOVER size, stale memory, drift)
- Before `/release-baseline` to surface remaining issues
- Ad hoc between phases if the conversation feels "loud" with stale context

## When NOT to use

- During an active `/p5-implement` TDD cycle (avoid context disruption)
- Inside a Gate skill — gates already do their own cleanup (preflight rm, phase freeze). `/cleanup` is the broader, manual workflow.

## Notes

- Phase-freeze (setting `status: frozen` on phase detail files) is the responsibility of the **Gate skills**, not `/cleanup`. This skill only reports phase-doc status issues; it does not change them.
- The HANDOVER archive convention (`docs/.handover-archive/<YYYY-MM-DD>-<slug>.md`) is already established in real-world projects. `/cleanup` keeps that filename pattern.
