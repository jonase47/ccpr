---
disable-model-invocation: true
---
# /cleanup – Doc Hygiene: HANDOVER cap + lint aggregator

Runs a one-shot hygiene pass on a project's docs to keep them lean and
machine-readable: HANDOVER inbox triage and size cap enforcement plus the four
existing lint scripts (`memory-lint.sh`, `phase-docs-lint.sh`, `doc-volume-check.sh`,
`manual-lint.sh`) bundled into one consolidated drift report. Use this between phases (after a Gate)
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

### 1a. Unparseable inbox lines (report only)

The count in §1 is deliberately heading-independent (match on the marker, not the heading) — this
pass is the opposite: it needs the section boundary that count ignores, purely to report drift, not
to change the count.

Search for a line starting with the heading `## Open Points` (any suffix, e.g. the shipped
`## Open Points (append-only inbox)`). If found, collect every line from there up to (not including)
the next `## ` heading or end of file. Within that block, a line is **structure, not a finding** —
excluded from this pass — if it is blank, a blockquote line (starts with `>`), an HTML comment
(`<!-- ... -->`), or a line matching §1's marker pattern. The template's own format example lives
entirely inside the blockquote, so a fresh `project-init` HANDOVER must report **zero** unparseable
lines here — if your count is not zero on an untouched template, the exclusion list above is wrong,
not the fixture.

Every remaining non-empty line is **unparseable, needs reshaping**: it landed in the inbox section
without the five-field marker format (commonly an epilogue bullet writing free prose instead of an
`- INBOX | ...` line — see `commands/p5-polish.md` §6 for what a correctly formatted entry looks
like). Report each such line (verbatim, truncated to 80 chars) and offer to reshape it into the
five-field form on confirmation. Never reshape silently, and never count it toward §1's entry count
— it was never a triageable entry to begin with.

If the `## Open Points` heading is missing entirely, this pass reports nothing, same as §1's own
"heading missing" branch: that is not an error.

### 2. HANDOVER size cap enforcement (auto with confirm)

Read `docs/HANDOVER.md` size (bytes) and line count.

Determine the cap:
- Parse the file's own header for a line like `Size cap: ≤N KB` or `≤N KB`.
- If not present, fall back to the global Template default: **5 KB / 150 lines**.

Express both dimensions as a percentage of their cap and carry the **higher** of the two — the size
hook (see Notes) measures the same way, so a file it warned about is reported at the same level here.

Determine the warn threshold — the percentage from which a file counts as *approaching* its cap.
It is a single calibrated constant; read it instead of restating it:

```
grep -m1 '^HANDOVER_WARN_PCT' ~/.claude/hooks/agent-monitor.py
```

The comment above that constant carries the measurement behind the value: a threshold one skill
run's growth below the cap is the last moment at which a warning is still preventive. If the grep
finds nothing (no hook installed), `/cleanup` still runs — fall back to the two-branch behaviour
below (under cap / over cap) and note in the report that the preventive branch was skipped for lack
of a threshold. Do not invent one: the number is only meaningful because it was measured.

Compare:
- **Below the threshold** → report "HANDOVER under cap (X KB / Y lines, N % of cap)" and continue.
- **At or above the threshold, but still under the cap** → report the percentage, then **offer** to
  archive: name the oldest archivable block (see below) and ask whether to archive it now. The file
  is still legal at this level, so the archive is preventive, not required — **nothing is archived
  unless the user confirms**, and declining is a valid answer. On decline, report "approaching cap,
  archive declined" and continue. On confirm, archive **one** block, re-measure and stop: the goal
  is to leave the warning band, not to empty the file.
- **Over cap** → same candidate, but here archiving is the expected outcome rather than an offer.
  On confirm, re-measure and loop with the next-oldest candidate (re-confirm each time) until the
  file is under cap. On decline, report the over-cap state and continue without archiving.
  If the candidates run out before the file is under cap, stop and report exactly that — "over cap,
  no archivable block left (X KB / Y lines, N % of cap)" — and continue. Do not widen the heuristic
  to invent a new archive target: a file that is over cap with nothing left to archive is carrying
  current content and needs the user to shorten it, not a bigger search.

**Identifying the oldest archivable block.** Heuristic, in order:
  1. The earliest `## Postmortem-Epilogue (DD.MM.YYYY …)` section (datable session block).
  2. Failing that, the earliest top-level `## ` section that contains a date in its heading.
  3. Failing that, the oldest `## Last Action` / `## What Was Achieved` block (when the file uses the template structure).

If no candidate matches, report that and continue — a young HANDOVER can reach the threshold before
it has an archivable block, and there is nothing to offer.

Show the user the candidate block (heading + first 5 lines) and **ask for confirmation** before archiving. Do **not** archive silently.

On confirm:
- Extract the block to `docs/.handover-archive/<YYYY-MM-DD>-<slug>.md`. Pick `<YYYY-MM-DD>` from the block's header date if present, else today. `<slug>` is a kebab-case derivation of the heading.
- Remove the block from `docs/HANDOVER.md`.
- Re-measure (loop only in the over-cap branch, as described above).

### 3. Memory lint (read-only)

Run `bash ~/.claude/scripts/memory-lint.sh [projectdir]`. Show:
- Exit code (0 clean / 1 warnings / 2 errors / 3 configuration error — no report was produced, treat as a run failure rather than a findings result)
- Up to the first 10 issue lines from stdout (truncate the rest with a `… N more` note).

**If exit is 2 on `link target '…' does not exist` lines** — that is check (n), dead links in
`docs/memory/MEMORY.md` and in every `docs/memory/{agent}/MEMORY.md`. It errors by default since
24.08.2026 (WI-0005); it warned before. Fixing the link is the answer. For a run that has to get past
it now, `MEMORY_INDEX_LINK_SEVERITY=warn bash ~/.claude/scripts/memory-lint.sh [projectdir]` reports
the identical findings as warnings (exit 1). The knob takes `err` or `warn` and nothing else — an
empty value is not an off switch, it exits 3.

Do not auto-fix. Lint-suggested actions (e.g. refreshing `last_updated`, or setting
`status: archived`/`superseded` on a file that is deliberately no longer maintained) belong to the user.

### 4. Phase-docs lint (read-only)

Run `bash ~/.claude/scripts/phase-docs-lint.sh [projectdir]`. Same output handling as §3.

### 5. Doc-volume check (read-only)

Run `bash ~/.claude/scripts/doc-volume-check.sh [projectdir]/docs`. Same output handling as §3. Volume warnings (≥25/40/50 KB) typically point at splitting work — surface the top 3 offenders for the user to consider.

### 6. Manual-lint: index-↔-detail contract (read-only)

Run `bash ~/.claude/scripts/manual-lint.sh [projectdir]/docs`. Same output handling as §3.
Validates the `kind`/`parent_index` frontmatter contract (`templates/PHASE_DOC_SCHEMA.md`'s
`## kind` and `## manual-lint.sh` sections) — generic over its root argument, not hardwired to
this repository's own `Manual/` (`install.sh` never ships `Manual/`, see `Manual/README.md:2-5`).
Most projects will scan clean here today (`kind`/`parent_index` are optional fields few sub-
indexes use yet) — that is expected, not a sign the check did not run; the report's own
`Files scanned` line and stderr notice on an empty scope make the difference legible. A project
maintaining its own `Manual`-style tree can point this step at that root instead.

### 7. Consolidated drift report

Print a compact summary table at the end:

```
Drift Report — <project>
| Check               | Status      | Action |
|---|---|---|
| HANDOVER inbox      | 0 entries | N entries | section absent | <triaged: N→backlog, N→decision, N kept, N dropped / none — plus M unparseable, needs reshaping, if any> |
| HANDOVER cap        | ok | approaching | over | n/a | <none / archived N blocks / archive offered, declined / suggested archive> |
| memory-lint         | clean | warn | error | <command to inspect> |
| phase-docs-lint     | clean | warn | error | <command to inspect> |
| doc-volume          | clean | warn | error | <top offender + split hint> |
| manual-lint         | clean | warn | error | <command to inspect> |
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
- When the size hook warns that `docs/HANDOVER.md` is approaching or over its cap (see Notes) — at the approaching level §2 offers the archive, so running it then is the preventive moment
- When `project-guide` flags Cleanup-Awareness (HANDOVER size, inbox entries, stale memory, drift)
- Before `/release-baseline` to surface remaining issues
- Ad hoc between phases if the conversation feels "loud" with stale context

## When NOT to use

- During an active `/p5-implement` TDD cycle (avoid context disruption)
- Inside a Gate skill — gates already do their own cleanup (preflight rm, phase freeze). `/cleanup` is the broader, manual workflow.

## Notes

- Phase-freeze (setting `status: frozen` on phase detail files) is the responsibility of the **Gate skills**, not `/cleanup`. This skill only reports phase-doc status issues; it does not change them.
- The HANDOVER archive convention (`docs/.handover-archive/<YYYY-MM-DD>-<slug>.md`) is already established in real-world projects. `/cleanup` keeps that filename pattern.
- **The cap is watched automatically.** `~/.claude/hooks/agent-monitor.py` measures `docs/HANDOVER.md` at session start and after every write to that file, and prints one stderr warning when it reaches the warn threshold and another once it is over cap. The hook never blocks and never edits anything — it points here. `/cleanup` measures the file itself, so the skill works unchanged when the hook is absent; it must not assume a warning has already been shown.
- The inbox is the receiving end of an existing flow, not a new one: `/p5-polish` already triages sprint TODOs into `polish-now | backlog | handover | drop` and appends its `handover` items to `docs/HANDOVER.md` under "Open Points" — in the same marker format (`commands/p5-polish.md` §6), with the POL-ID in the `ref` field, so they triage here without special-casing. `/p5-polish` runs once per sprint between `/gate-p5` and `/p4-sprint`; `/cleanup` runs any time, which is why the general inbox lives here.
- `/cleanup` does not append to the inbox — it only triages. Appending is for agents that find something while working on something else.
