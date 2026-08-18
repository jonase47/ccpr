# /cleanup – Doc Hygiene: HANDOVER cap + lint aggregator

Runs a one-shot hygiene pass on a project's docs to keep them lean and
machine-readable: HANDOVER inbox triage and size cap enforcement plus the three
existing lint scripts (`memory-lint.sh`, `phase-docs-lint.sh`, `doc-volume-check.sh`)
bundled into one consolidated drift report. Use this between phases (after a Gate)
or whenever the project-guide warns about HANDOVER size, an unprocessed inbox,
stale memory or doc volume drift.

## Argument: $ARGUMENTS = [optional: projectdir]

- Without argument: operates on `$(pwd)`.
- With argument: operates on the given project directory.

## Flow

### 1. HANDOVER inbox triage (confirm before removing)

The HANDOVER carries an append-only inbox (`## Open Points`, see
`templates/HANDOVER_TEMPLATE.md`): working agents drop findings there that fall outside their
assignment, and this step is the one place they are cleared again.

Scan `docs/HANDOVER.md` for lines matching the marker pattern `^- INBOX [|]` — match on the
**marker, not the heading**, so entries appended under a differently named heading are still found.

Write the separator as the bracket expression `[|]`, never as a bare `|`: bare, it is alternation in
ERE (`grep -E`) **and** in GNU BRE (`grep '\|'`), where `^- INBOX ` OR *empty* matches every line of
the file. `[|]` is a literal pipe in BRE, ERE and Python `re` alike. Reference command:

```
grep -c '^- INBOX [|]' docs/HANDOVER.md
```

It must return the same count with `-E` added — if the two differ, the pattern is wrong, not the file.

- **No matches** → report `inbox: 0 entries` and continue with §2. Do **not** create the section:
  a project on an older template stays valid without it. If the `## Open Points` heading is missing
  entirely, mention `templates/HANDOVER_TEMPLATE.md` once in the report — as a hint, not an action.
  A fresh `project-init` HANDOVER is expected to report 0: the template's format example lives
  inside the section's blockquote (`> `) and therefore does not match the marker.
- **Matches** → split each line on `|` into `marker | date | source | finding | ref` and present all
  entries as a table with one proposed target each. If a line yields **more than five** fields
  (someone wrote a literal `|` into the finding text), keep field 1 as the marker, fields 2–3 as
  date and source, the **last** field as `ref`, and re-join everything in between as the finding —
  the reference is always last. Never drop the surplus text and never re-cut the line in the file.

| Target | When | Effect on confirm |
|---|---|---|
| `backlog` | worth doing, not now | create a work item (adoption guard: `/p5-polish` §0) or append a BACKLOG.md mini-story, then remove the line |
| `decision` | the PO has to decide | move it into `## Open Decisions` as a row, then remove the line |
| `keep` | still relevant, not yet actionable | line stays verbatim |
| `drop` | duplicate, obsolete, already fixed | remove the line, record the reason in the run report |

**Ask for confirmation** on the table before touching the file; accept per-item overrides. Never
remove or reword an entry silently — the section is append-only for every other role, and this step
is the only exception.

This runs **before** the size cap on purpose: clearing the inbox is a lossless way to shrink the
file and may bring it back under the cap without archiving anything.

### 2. HANDOVER size cap enforcement (auto with confirm)

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

**Never** pick the inbox section as an archive candidate while it still holds lines matching §1's
marker pattern (`grep -c '^- INBOX [|]'` > 0) —
a finding that was never triaged must not disappear into the archive. Once §1 has cleared it, the
empty section costs a few bytes and stays in place.

Show the user the candidate block (heading + first 5 lines) and **ask for confirmation** before archiving. Do **not** archive silently.

On confirm:
- Extract the block to `docs/.handover-archive/<YYYY-MM-DD>-<slug>.md`. Pick `<YYYY-MM-DD>` from the block's header date if present, else today. `<slug>` is a kebab-case derivation of the heading.
- Remove the block from `docs/HANDOVER.md`.
- Re-measure. If still over cap, loop with the next-oldest candidate (re-confirm each time).

On decline: report the over-cap state and continue without archiving.

### 3. Memory lint (read-only)

Run `bash ~/.claude/scripts/memory-lint.sh [projectdir]`. Show:
- Exit code (0 clean / 1 warnings / 2 errors / 3 configuration error — no report was produced, treat as a run failure rather than a findings result)
- Up to the first 10 issue lines from stdout (truncate the rest with a `… N more` note).

Do not auto-fix. Lint-suggested actions (e.g. `status: stale`) belong to the user.

### 4. Phase-docs lint (read-only)

Run `bash ~/.claude/scripts/phase-docs-lint.sh [projectdir]`. Same output handling as §3.

### 5. Doc-volume check (read-only)

Run `bash ~/.claude/scripts/doc-volume-check.sh [projectdir]/docs`. Same output handling as §3. Volume warnings (≥25/40/50 KB) typically point at splitting work — surface the top 3 offenders for the user to consider.

### 6. Consolidated drift report

Print a compact summary table at the end:

```
Drift Report — <project>
| Check               | Status      | Action |
|---|---|---|
| HANDOVER inbox      | 0 entries | N entries | section absent | <triaged: N→backlog, N→decision, N kept, N dropped / none> |
| HANDOVER cap        | ok | over | n/a  | <none / archived N blocks / suggested archive> |
| memory-lint         | clean | warn | error | <command to inspect> |
| phase-docs-lint     | clean | warn | error | <command to inspect> |
| doc-volume          | clean | warn | error | <top offender + split hint> |
```

Then offer 1–3 concrete next-step commands:
- For inbox entries kept: nothing to do — they are carried into the next session on purpose
- For lint warnings: the exact lint invocation to see full output
- For doc volume: the largest file plus a suggested split target
- For phase-doc status issues: a pointer to the schema (`templates/PHASE_DOC_SCHEMA.md`)

## When to use

Recommended triggers:
- After a Gate has been passed (especially gates p4–p7 where phase docs accumulate)
- When an agent reports "inbox full" or the inbox has collected entries over several sessions
- When `project-guide` flags Cleanup-Awareness (HANDOVER size, inbox entries, stale memory, drift)
- Before `/release-baseline` to surface remaining issues
- Ad hoc between phases if the conversation feels "loud" with stale context

## When NOT to use

- During an active `/p5-implement` TDD cycle (avoid context disruption)
- Inside a Gate skill — gates already do their own cleanup (preflight rm, phase freeze). `/cleanup` is the broader, manual workflow.

## Notes

- Phase-freeze (setting `status: frozen` on phase detail files) is the responsibility of the **Gate skills**, not `/cleanup`. This skill only reports phase-doc status issues; it does not change them.
- The HANDOVER archive convention (`docs/.handover-archive/<YYYY-MM-DD>-<slug>.md`) is already established in real-world projects. `/cleanup` keeps that filename pattern.
- The inbox is the receiving end of an existing flow, not a new one: `/p5-polish` already triages sprint TODOs into `polish-now | backlog | handover | drop` and appends its `handover` items to `docs/HANDOVER.md` under "Open Points" — in the same marker format (`commands/p5-polish.md` §6), with the POL-ID in the `ref` field, so they triage here without special-casing. `/p5-polish` runs once per sprint between `/gate-p5` and `/p4-sprint`; `/cleanup` runs any time, which is why the general inbox lives here.
- `/cleanup` does not append to the inbox — it only triages. Appending is for agents that find something while working on something else.
