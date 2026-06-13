# /roadmap – Create an initial roadmap

## Purpose
This command creates a first roadmap based on an existing rough concept.
The roadmap structures epics, milestones, and dependencies either
time-based (quarters/months) or phase-based (MVP, Phase 1, Phase 2...) –
selectable depending on the project character.

---

## Execution

### Step 1 – Load concept & context

Check whether the user named a concept file:
- If yes: read it completely.
- If no: search in `docs/concepts/` and display a selection list:
  > "Which concept should the roadmap be based on?
  > [List of found concept files with title and version]"

After the selection, also read any existing decision documents
from `docs/decisions/` that belong to the same project –
they contain important directional choices for planning.

---

### Step 2 – Choose structure

Ask the user once for the desired structure if not already
specified in the initial prompt:

> "How should the roadmap be structured?
> (a) Time-based – with concrete time periods (months, quarters)
> (b) Phase-based – MVP, Phase 1, Phase 2 etc. without fixed dates
>
> Tip: Time-based is suitable when deadlines or releases are known.
> Phase-based is better when the timeline is still open."

Wait for the answer before continuing.

---

### Step 3 – Parallel analysis by sub-agents

Start **three sub-agents in parallel** using the `Task` tool.
All agents receive the concept, any decision documents, and the
chosen structure as context. Mark ambiguities as `[UNCLEAR: ...]`.

#### Sub-Agent A – Structure epics & features
- Which epics / larger feature blocks can be derived from the concept?
- How can they be meaningfully divided into phases or time periods?
- What is MVP-critical, what is nice-to-have?
- Rough effort estimate per epic: Small / Medium / Large

#### Sub-Agent B – Milestones & dependencies
- Which milestones result from the epics?
  (e.g. "MVP live", "Multi-user active", "First feedback collected")
- Which dependencies exist between epics?
  (What must be done before what?)
- Are there external dependencies (decisions, tools, people)?

#### Sub-Agent C – Risks & planning buffer
- Where are the critical paths in the planning?
- Which epics or dependencies are particularly risky?
- Where should buffer be planned?
- What could jeopardize or delay the planning?

---

### Step 4 – Interactive clarification round

Collect all `[UNCLEAR: ...]` markers, prioritize and ask bundled:

> "Before I create the roadmap, a few quick questions:
>
> 1. [Question A]
> 2. [Question B]
> ...
>
> You can skip questions – open points will go into the roadmap."

Maximum 5 questions. If no ambiguities: skip this step.

---

### Step 5 – Create roadmap document

Create the roadmap document in the following format.
Adapt Section 3 depending on the chosen structure (time-based or phase-based).

```markdown
# Roadmap: [Project title]

**Created:** [Date]
**Version:** 1.0
**Status:** Draft
**Basis:** [Reference to concept file + version]

---

## 1. Overview
[2-3 sentences: What is the goal, which time period / phases does the roadmap cover?]

## 2. Epics & Features

| Epic | Description | Size | Phase/Period | Status |
|------|-------------|------|--------------|--------|
| [Epic 1] | ... | Small/Medium/Large | ... | Open |
| [Epic 2] | ... | ... | ... | Open |

## 3a. Timeline *(only for time-based structure)*

### [Month / Quarter]
- **Milestone:** ...
- **Epics:** ...
- **Goal:** ...

### [Month / Quarter]
...

## 3b. Phase plan *(only for phase-based structure)*

### Phase 1 – [Name, e.g. MVP]
- **Goal:** ...
- **Epics:** ...
- **Milestone:** ...
- **Success criterion:** ...

### Phase 2 – [Name]
...

## 4. Milestones

| Milestone | Description | Phase/Date | Depends on |
|-----------|-------------|------------|------------|
| ...       | ...         | ...        | ...        |

## 5. Dependencies

| Epic / Milestone | Depends on | Type |
|------------------|-----------|------|
| [Epic B] | [Epic A] | must be done first |
| [Epic C] | [Decision X] | external dependency |

## 6. Risks & Buffer
- ...

## 7. Open Points
| Point | Who clarifies? | By when? |
|-------|---------------|----------|
| ...   | ...           | ...      |
```

---

### Step 6 – Output & wrap-up

**Output format:** Ask once if not specified in the prompt:
> "Save as a file under docs/roadmaps/, output directly, or both?"

File name: `docs/roadmaps/YYYY-MM-DD_<shortname>.md`

Provide a brief summary:
- How many epics / phases / milestones were identified?
- Where is the critical path?
- What are the sensible next commands (e.g. `/epic`, `/entscheidung`)?

---

## General Notes

- Roadmap stays rough – no tickets or tasks at this stage.
- Make dependencies explicit, including external ones.
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
