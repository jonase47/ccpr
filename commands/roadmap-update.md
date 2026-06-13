# /roadmap-update – Update an existing roadmap

## Purpose
This command updates an existing roadmap based on new findings,
completed milestones, changed priorities, or new decisions.
Each revision is versioned and timestamped with date + time.

---

## Execution

### Step 1 – Load roadmap & context

Check whether the user named a roadmap file:
- If yes: read it completely.
- If no: search in `docs/roadmaps/` and display a selection list:
  > "Which roadmap should be updated?
  > [List of found files with title and current version]"

Additionally read newer concept or decision documents
that were created after the roadmap's creation date –
they might contain relevant changes.

---

### Step 2 – Clarify reason for change & context

Check whether the user has described what has changed.

If not sufficiently described, ask once:
> "What has changed or should be re-evaluated?
> (e.g. epic completed, priority shifted, new requirement,
> timeline adjusted, new decision made)"

If an input file with new notes or decisions was named:
read it as well.

---

### Step 3 – Parallel analysis by sub-agents

Start **three sub-agents in parallel** using the `Task` tool.
All agents receive the existing roadmap and the change context.
Mark ambiguities as `[UNCLEAR: ...]`.

#### Sub-Agent A – What changes in epics & timeline?
- Which epics or phases are affected by the change?
- Do epics need to be shifted, split, added, or removed?
- Does the structure (time-based/phase-based) need to be adjusted?
- Status updates: What is newly "In Progress" or "Done"?

#### Sub-Agent B – Impact on milestones & dependencies
- Which milestones shift or are dropped?
- Do new dependencies arise from the change?
- Which existing dependencies are thereby resolved?
- Are there domino effects on subsequent epics?

#### Sub-Agent C – Impact on risks & critical path
- Does the critical path change?
- Do new risks arise, do any fall away?
- Is new buffer needed at specific points?
- What jeopardizes the updated planning?

---

### Step 4 – Interactive clarification round

Collect all `[UNCLEAR: ...]` markers, prioritize and ask bundled:

> "Before I update the roadmap, a few quick questions:
>
> 1. [Question A]
> 2. [Question B]
> ...
>
> You can skip questions – open points will go into Chapter 7."

Maximum 5 questions. If no ambiguities: skip this step.

---

### Step 5 – Create updated roadmap

Create a **new file** – the predecessor file remains unchanged.

**File name:**
```
docs/roadmaps/YYYY-MM-DD_<shortname>_v<X.Y>.md
```

**Version number logic:**
- Status updates, minor shifts: Minor bump → e.g. 1.0 → 1.1
- New epics, phase restructuring, major direction change: Major bump → e.g. 1.1 → 2.0

**Header of the updated document:**
```markdown
# Roadmap: [Project title]

**Created:** [Original date from v1.0]
**Last updated:** [Current date + time, e.g. 2026-02-22, 14:35]
**Version:** [new version number]
**Status:** Draft / Active / Completed
**Basis:** [Reference to concept file + version]

**Change history:**
| Version | Date + Time       | Change (short form)              |
|---------|-------------------|----------------------------------|
| 1.0     | [Original date]   | Initial roadmap                  |
| [new]   | [Date + Time]     | [Brief description of change]    |
```

Carry over all unchanged sections from the predecessor roadmap.
Only update the affected sections.
Always explicitly apply status changes for epics and milestones.

---

### Step 6 – Output & wrap-up

Use the same output format as the original `/roadmap`,
unless the user explicitly specifies something else at call time.

Provide a brief summary:
- What was changed (2-3 sentences)?
- New version number and file path (if saved)?
- Has the critical path changed?
- Next sensible step (e.g. `/epic`, `/konzept-update`, another `/roadmap-update`)?

---

## General Notes

- The predecessor file is **never overwritten** – always create a new file.
- Timestamps for updates always include date **and time** (e.g. `2026-02-22, 14:35`).
- The initial roadmap (v1.0) intentionally carries only a date without time.
- Maximum one clarification round, then the document is created.
- Write in English, unless the user specifies otherwise.

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that fit the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
