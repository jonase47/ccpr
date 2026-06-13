# /konzept – Create a rough concept for a feature or (sub-)project

## Purpose
This command guides through the initial conception phase as a Product Owner.
The result is a first structured rough concept that serves as the basis for
further steps (user stories, roadmap, stakeholder presentation).

---

## Execution

### Step 1 – Clarify context & output format

**Input:**
- If a file was mentioned: read it completely.
- If only a short description is available: work with it.
- If both are missing: ask once briefly:
  > "Describe the idea briefly or give me a file with your notes –
  > then I'll get started."

**Output format:**
Check whether the user specified a desired format in the initial prompt.

If **no** format was specified, ask once:
> "How should the result be delivered?
> (a) Save as a Markdown file in the project folder
> (b) Output directly in the terminal
> (c) Both"

Wait for the answer before continuing.
If a format was clearly specified, skip this question.

---

### Step 2 – Parallel analysis by sub-agents

Start **three sub-agents in parallel** using the `Task` tool.

Each sub-agent should **explicitly mark** missing or unclear information in their area
(e.g. `[UNCLEAR: ...]`), but not yet make assumptions – that is handled in Step 3.

#### Sub-Agent A – Problem space & value
- What problem is being solved? For whom?
- What is the concrete benefit / added value?
- Why is this topic relevant now?
- What alternatives or workarounds exist today?

#### Sub-Agent B – Scope & boundaries
- What is **in scope** (core of the solution)?
- What is **deliberately out of scope**?
- Which systems, interfaces, or dependencies are affected?
- First rough size estimate: Small / Medium / Large?

#### Sub-Agent C – Risks & open questions
- What critical ambiguities exist?
- What needs to be validated before moving forward?
- What risks or blockers might arise?
- Which open questions need clarification (internal / external)?

---

### Step 2b – Consolidation by Wingman

Start the **wingman** agent with the results of the three sub-agents:
> Consolidate the results of the parallel analysis (problem space, scope, risks).

Use the Wingman summary as the basis for the clarification round.

### Step 3 – Interactive clarification round

Collect all `[UNCLEAR: ...]` markers from the three sub-agent results.

Prioritize them by relevance to the rough concept and present them to the user
**bundled in a single message** – not one by one.

Format:
> "Before I put the concept together, I have a few questions:
>
> 1. [Question about ambiguity A]
> 2. [Question about ambiguity B]
> 3. [Question about ambiguity C]
>
> You can skip individual questions, then I'll leave that point open."

Wait for the answers. Then process all answers at once in Step 4.

**Important:** Maximum 5 questions per round. If there are more ambiguities,
prioritize the most concept-critical ones and leave the rest as genuine open questions
in the document.

---

### Step 4 – Assemble the concept document

Merge everything – sub-agent analyses + answers from Step 3 – into the following
Markdown document:

```markdown
# Rough Concept: [Title]

**Created:** [Date, Time]
**Version:** 1.0
**Status:** Draft
**Author:** PO

---

## 1. Idea & Initial Situation
[2-4 sentences – what is the idea, what triggered it?]

## 2. Problem Space & Target Group
**Problem:** ...
**Target group:** ...
**Why now:** ...
**Current alternatives:** ...

## 3. Value Proposition
[1-3 clear sentences: What gets better for whom?]

## 4. Scope

### In Scope (now)
- ...

### Out of Scope (deliberate)
- ...

### Affected Systems / Dependencies
- ...

### Initial Size Estimate
[ ] Small (< 2 weeks)  [ ] Medium (2-6 weeks)  [ ] Large (> 6 weeks)

## 5. Open Questions
*(Points that were not clarified in the conversation or still need external validation)*

| Question | Who clarifies? | By when? |
|----------|---------------|----------|
| ...      | ...           | ...      |

## 6. Risks & Blockers
- ...

## 7. Next Steps
- [ ] Align concept with [stakeholder]
- [ ] Clarify open questions from Chapter 5
- [ ] If approved: create user stories / epics
```

**Output according to the chosen format from Step 1:**
- Option (a) – File: save under `docs/concepts/YYYY-MM-DD_<shortname>.md`
- Option (b) – Terminal: output the full document directly
- Option (c) – Both: save **and** output

---

### Step 5 – Wrap-up

Provide a brief summary:
- Where the document is located (if saved)?
- The **2-3 most important still-open points** from Chapter 5.
- Note on a sensible next command (e.g. `/epic`, `/user-stories`).

---

## General Notes

- Do not make assumptions – ask briefly instead.
- Always ask questions **bundled**, never one by one.
- Maximum **one clarification round** – after that the document is created,
  remaining ambiguities go into Chapter 5 (Open Questions).
- Keep the document rough and compact – no overengineering.
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
