# /epic – Create an epic

## Purpose
This command creates one or more epics – either derived from an existing
concept or roadmap, or standalone from a free description.
An epic can already contain rough associated user stories or be created as
a pure high-level shell – this is selectable per call.

---

## Execution

### Step 1 – Load context

Check whether the user named a source file:
- Concept file → read from `docs/concepts/`
- Roadmap → read from `docs/roadmaps/`
- Both → read both and merge
- No file → standalone, work only with the description from the prompt

If no source file and no sufficient description is available:
> "Describe the epic briefly or give me a concept/roadmap file as a basis."

---

### Step 2 – Clarify scope

Ask once if not specified in the prompt:

> "Should the epic already contain rough user stories,
> or just create the high-level shell?
> (a) Shell + rough user stories
> (b) Epic shell only"

Also, if derived from concept/roadmap and multiple epics are recognizable:
> "I see [X] possible epics. All at once or select a specific one?"

---

### Step 3 – Parallel analysis by sub-agents

Start **three sub-agents in parallel** using the `Task` tool.
Mark ambiguities as `[UNCLEAR: ...]`.

#### Sub-Agent A – Epic definition & goal
- What is the overarching goal of this epic from the user's perspective?
- What value does the epic deliver when it is complete?
- How does it differ from other epics?
- Which user groups are affected?

#### Sub-Agent B – Scope & content
- What belongs in this epic (in scope)?
- What deliberately does not belong (out of scope)?
- If variant (a) selected: which user stories can be roughly derived?
  Format per story: "As a [role] I want [action] so that [benefit]."
- Rough effort estimate: Small / Medium / Large

#### Sub-Agent C – Dependencies & risks
- Does this epic depend on other epics or decisions?
- What must be complete before this epic?
- What risks or blockers exist?
- Are there technical or functional prerequisites?

---

### Step 4 – Interactive clarification round

Collect all `[UNCLEAR: ...]` markers, prioritize and ask bundled:

> "Before I create the epic, a few quick questions:
>
> 1. [Question A]
> 2. [Question B]
> ...
>
> You can skip questions – open points will go into the epic."

Maximum 5 questions. If no ambiguities: skip this step.

---

### Step 5 – Create epic document

```markdown
# Epic: [Title]

**Created:** [Date]
**Version:** 1.0
**Status:** Open
**Priority:** High / Medium / Low
**Size:** Small / Medium / Large
**Source:** [Concept / Roadmap / Standalone + reference to file+version]

---

## 1. Goal & Value
[2-3 sentences: What is achieved when the epic is complete? For whom?]

## 2. Scope

### In Scope
- ...

### Out of Scope
- ...

## 3. Affected User Groups
- ...

## 4. User Stories *(only for variant a)*

| ID | User Story | Priority | Status |
|----|-----------|----------|--------|
| E-{NN}-S01 | As a [role] I want [action] so that [benefit]. | High/Medium/Low | Open |
| E-{NN}-S02 | ... | ... | Open |

*Detailed elaboration of user stories via /user-stories*

## 5. Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| [Epic / Decision X] | must be done first | Open/Done |

## 6. Risks & Prerequisites
- ...

## 7. Definition of Done (Epic)
- [ ] All associated user stories completed
- [ ] Acceptance criteria of all stories fulfilled
- [ ] [Add further project-specific DoD criteria]

## 8. Open Questions
| Question | Who clarifies? | By when? |
|----------|---------------|----------|
| ...      | ...           | ...      |
```

---

### Step 6 – Output & wrap-up

**Output format:** Ask once if not specified in the prompt:
> "Save as a file under docs/epics/, output directly, or both?"

File name: `docs/epics/YYYY-MM-DD_<shortname>.md`

Brief wrap-up summary:
- How many epics were created?
- Most important dependencies at a glance?
- Next sensible step (e.g. `/user-stories` for detailed elaboration)?

---

## General Notes

- Epics stay rough – no implementation details.
- User stories in Step 3b are raw drafts, not finished stories.
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
