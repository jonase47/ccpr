# /konzept-update – Revise an existing rough concept

## Purpose
This command updates an existing rough concept based on new findings,
clarified open questions, or changed requirements.
Each revision is versioned and timestamped so that
the evolution of the concept remains traceable.

---

## Execution

### Step 1 – Load the concept file

Check whether the user named a file:
- If yes: read it completely.
- If no: search the `docs/concepts/` directory for concept files
  and display a compact selection list:
  > "Which concept should be updated?
  > [List of found files with title and current version]"

Wait for the selection before continuing.

---

### Step 2 – Clarify reason for change & context

Check whether the user has already described in the initial prompt what has
changed or what should be updated.

If **not sufficiently described**, ask once briefly:
> "What has changed or should be re-evaluated?
> (e.g. clarified tech stack decision, new scope, changed requirement)"

If the user also named an input file with new notes or decisions:
read it as well and process it as context.

---

### Step 3 – Parallel analysis by sub-agents

Start **three sub-agents in parallel** using the `Task` tool.
Each agent receives both the existing concept and the change context.
Ambiguities are marked as `[UNCLEAR: ...]` – do not make assumptions.

#### Sub-Agent A – What changes in content?
- Which sections of the concept are affected by the change?
- What specifically needs to be reformulated or added?
- Are there contradictions with the existing concept that need to be resolved?

#### Sub-Agent B – Impact on scope & open questions
- Does the change affect the scope (In Scope / Out of Scope)?
- Which previously open questions from Chapter 5 are now answered?
- Do the changes create new open questions or dependencies?

#### Sub-Agent C – Impact on risks & next steps
- Does the change alter the risk assessment?
- Do risks fall away, do new ones arise?
- What are the updated next steps?

---

### Step 4 – Interactive clarification round

Collect all `[UNCLEAR: ...]` markers from the three sub-agents.
Prioritize by relevance and ask bundled in a single message:

> "Before I update the concept, a few quick questions:
>
> 1. [Question A]
> 2. [Question B]
> ...
>
> You can skip individual questions – the point will remain in
> the open questions."

Maximum 5 questions. Wait for answers, then continue with Step 5.
If there are no ambiguities, skip this step.

---

### Step 5 – Create updated concept document

Create a **new file** with an incremented version number.
The original file remains unchanged (version history).

**File name:**
```
docs/concepts/YYYY-MM-DD_<shortname>_v<X.Y>.md
```

**Version number logic:**
- Small content change (individual fields, clarified questions): Minor bump → e.g. 1.0 → 1.1
- Larger change (scope change, new phase, change of direction): Major bump → e.g. 1.1 → 2.0

**Header of the updated document:**
```markdown
# Rough Concept: [Title]

**Created:** [Original date from v1.0]
**Last updated:** [Current date + time, e.g. 2026-02-22, 14:35]
**Version:** [new version number]
**Status:** Draft / Under Review / Approved
**Author:** PO

**Change history:**
| Version | Date + Time           | Change (short form)             |
|---------|-----------------------|---------------------------------|
| 1.0     | [Original date]       | Initial concept                 |
| [new]   | [Date + Time]         | [Brief description of change]   |
```

Carry over all unchanged sections from the predecessor concept.
Only update the affected sections based on the analysis and
the answers from Step 4.

Already clarified open questions from Chapter 5 are **removed from the table**
and instead briefly mentioned in the change history.

---

### Step 6 – Wrap-up

**Output format:** Use the same format as the original `/konzept` call,
unless the user explicitly specifies something else at call time.

Provide a brief summary:
- What was changed (2-3 sentences)?
- New version number and file path (if saved)?
- Remaining open questions from Chapter 5?
- Next sensible step (e.g. `/epic`, `/user-stories`, another `/konzept-update`)?

---

## General Notes

- The predecessor file is **never overwritten** – always create a new file.
- Timestamps for updates always include date **and time** (e.g. `2026-02-22, 14:35`).
- The initial concept (v1.0) intentionally carries only a date without time – this makes it
  recognizable at a glance as the first version.
- Maximum one clarification round – after that the document is created.
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
