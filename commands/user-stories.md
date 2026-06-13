# /user-stories – Create or elaborate user stories

## Purpose
This command creates detailed user stories – either derived from an existing
epic, roadmap, or concept, or standalone from a free description. Each story
contains acceptance criteria, priority, dependencies, and a definition of done.

---

## Execution

### Step 1 – Load context

Check whether the user named a source file:
- Epic file → read from `docs/epics/`
- Roadmap → read from `docs/roadmaps/`
- Concept file → read from `docs/concepts/`
- No file → standalone, work with the description from the prompt

If user stories are already present in the epic (raw drafts from `/epic`):
use these as the starting basis and elaborate them, do not reinvent.

If no source file and no sufficient description is available:
> "Describe briefly what should be implemented, or give me an epic/concept file."

---

### Step 2 – Clarify scope & focus

If derived from an epic and multiple raw stories are present:
> "I see [X] stories in the epic. Elaborate all of them or prioritize specific ones?"

If standalone:
> "For which user group(s) should stories be created?"

---

### Step 3 – Parallel elaboration by sub-agents

Distribute the stories across **parallel sub-agents** using the `Task` tool.
Rule of thumb: up to 3 stories per agent; for many stories use multiple agents.
Mark ambiguities as `[UNCLEAR: ...]`.

Each sub-agent elaborates their assigned stories according to the following schema:

**Per user story:**
- Assign story title & ID (format: `E-{NN}-S{NN}`, see `/p4-backlog` ticket ID schema)
- Check/sharpen story formulation:
  "As a [role] I want [action] so that [benefit]."
- Formulate acceptance criteria (concrete & testable, at least 2-3)
- Justify priority: High / Medium / Low
- Identify dependencies (other stories, epics, external factors)
- Formulate definition of done for this story
- Rough effort estimate: XS / S / M / L / XL

---

### Step 4 – Interactive clarification round

Collect all `[UNCLEAR: ...]` markers from all sub-agents,
prioritize by impact on the stories and ask bundled:

> "Before I finalize the stories, a few questions:
>
> 1. [Question A]
> 2. [Question B]
> ...
>
> You can skip questions – open points will go into the respective story."

Maximum 5 questions. If no ambiguities: skip this step.

---

### Step 5 – Create user stories document

```markdown
# User Stories: [Epic title or topic]

**Created:** [Date]
**Version:** 1.0
**Status:** Draft
**Source:** [Epic / Roadmap / Concept / Standalone + reference]

---

## Overview

| ID | Title | Priority | Effort | Status | Depends on |
|----|-------|----------|--------|--------|------------|
| E-{NN}-S01 | [Short title] | High | M | Open | – |
| E-{NN}-S02 | [Short title] | Medium | S | Open | E-{NN}-S01 |

---

## E-{NN}-S01 – [Title]

**Story:**
As a [role] I want [action] so that [benefit].

**Priority:** High / Medium / Low
**Effort:** XS / S / M / L / XL

**Acceptance Criteria:**
- [ ] [Concrete, testable criterion 1]
- [ ] [Concrete, testable criterion 2]
- [ ] [Concrete, testable criterion 3]

**Definition of Done:**
- [ ] Implemented and tested locally
- [ ] Acceptance criteria fulfilled and accepted
- [ ] [Further project-specific DoD criteria]

**Dependencies:**
- [None / Reference to other story ID or epic]

**Open Questions:**
- [If applicable]

---

## E-{NN}-S02 – [Title]
[same structure as E-{NN}-S01]

---

## Open Points (cross-cutting)
| Point | Affects | Who clarifies? | By when? |
|-------|---------|---------------|----------|
| ...   | E-{NN}-S{NN} | ...       | ...      |
```

---

### Step 6 – Output & wrap-up

**Output format:** Ask once if not specified in the prompt:
> "Save as a file under docs/user-stories/, output directly, or both?"

File name: `docs/user-stories/YYYY-MM-DD_<epic-shortname>.md`

Brief wrap-up summary:
- How many stories were created / elaborated?
- Which have the highest priority?
- Are there critical dependencies that determine the sequence?
- Next sensible step (e.g. carry into backlog, `/roadmap-update`)?

---

## General Notes

- Acceptance criteria must be concrete and testable – no vague statements.
- Dependencies between stories must be explicitly named, even within the same epic.
- Stories should be independently implementable (INVEST principle);
  dependencies are exceptions that must be justified.
- Maximum one clarification round, then creation starts.
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
