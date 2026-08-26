# /decision – Develop a decision basis

## Purpose
This command analyzes an open decision question, automatically determines
which perspectives are relevant, assembles the appropriate analysis agents,
and develops a structured decision basis (Decision Basis) – without making
the decision itself. That is the PO's responsibility.

---

## Execution

### Step 1 – Understand the decision question

Check whether the user has clearly described the decision question.

If not clear, ask once:
> "What exactly needs to be decided, and are there already known options –
> or do those need to be developed first?"

If an existing concept file was referenced (e.g. from `/konzept`
or `/konzept-update`): read it and extract the relevant open question.

---

### Step 2 – Determine decision type & select agents

Analyze the decision question and independently determine which
perspectives are necessary for a well-founded decision.

Select from the following agent types – **only those actually relevant for this decision**:

| Agent | When to use |
|-------|-------------|
| **Technology Agent** | For tech stack, tool, or architecture decisions |
| **Effort Agent** | When implementation effort or complexity needs to be estimated |
| **Risk Agent** | For decisions with potential dependencies, vendor lock-in, or operational risks |
| **User Agent** | When the decision affects usability or user experience |
| **Strategy Agent** | For decisions with long-term impact on extensibility or direction |
| **Cost Agent** | When licensing, hosting, or operating costs are relevant |
| **Alternatives Agent** | When options still need to be developed or are incomplete |

Briefly communicate to the user which agents you are using and why:
> "For this decision I'm consulting the following perspectives:
> [Agent A] – because ..., [Agent B] – because ..., [Agent C] – because ..."

---

### Step 3 – Parallel analysis by the selected agents

Start all selected agents **in parallel** using the `Task` tool.
Each agent receives the decision question, the known options (if available)
and the relevant context (e.g. concept file content).

Each agent should:
- Elaborate their perspective for each option
- Name strengths and weaknesses from their viewpoint
- Mark open points as `[UNCLEAR: ...]` instead of making assumptions
- State a reasoned tendency (not a final recommendation)

---

### Step 4 – Interactive clarification round

Collect all `[UNCLEAR: ...]` markers from the agent results.
Prioritize by decision relevance and ask bundled:

> "Before I put the decision basis together, I still need
> some information:
>
> 1. [Question A]
> 2. [Question B]
> ...
>
> You can skip questions – that will be factored in as uncertainty."

Maximum 5 questions. Wait for answers, then continue with Step 5.
If there are no ambiguities, skip this step.

---

### Step 5 – Assemble the decision basis

Create a structured decision document in the following format:

```markdown
# Decision: [Title of the question]

**Created:** [Date + Time]
**Status:** Open
**Context:** [Reference to concept etc., if available]

---

## 1. Decision Question
[Clear, precise formulation of the question in 1-2 sentences]

## 2. Options at a Glance

| Criterion         | Option A | Option B | Option C |
|-------------------|----------|----------|----------|
| [Criterion 1]     | ...      | ...      | ...      |
| [Criterion 2]     | ...      | ...      | ...      |
| [Criterion 3]     | ...      | ...      | ...      |
| **Tendency**      | +/-      | +/-      | +/-      |

## 3. Analysis per Option

### Option A – [Name]
**Pro:** ...
**Con:** ...
**Particularly suitable when:** ...

### Option B – [Name]
**Pro:** ...
**Con:** ...
**Particularly suitable when:** ...

### Option C – [Name] *(if applicable)*
...

## 4. Dependencies & Interactions
[What influences this decision? What is influenced by it?]

## 5. Open Uncertainties
[What could not be conclusively evaluated? What information is still missing?]

## 6. Analysis Tendency
[Summary: Which option performs best in the overall picture
and why – as input for the PO, not as a decision.]

## 7. Decision
**Chosen:** [To be filled in by PO]
**Rationale:** [To be filled in by PO]
**Date:** [To be filled in by PO]
```

---

### Step 6 – Output & wrap-up

**Output format:** Ask once if not specified in the initial prompt:
> "Save as a file (docs/decisions/), output directly, or both?"

After the output, provide a brief verbal summary:
- The 2 most important differences between the options
- Where the greatest uncertainty lies
- What makes sense next (e.g. tech stack decision → `/konzept-update`,
  decision made → `/epic`)

---

## General Notes

- **This command does not decide** – it provides a basis; the decision
  always rests with the PO.
- Communicate agent selection transparently (Step 2) so that the PO
  can intervene if a perspective is missing or unnecessary.
- Maximum one clarification round (Step 4), then the template is created.
- File storage under `docs/decisions/YYYY-MM-DD_<shortname>.md`
- Write in English, unless the user specifies otherwise.

### Handover Epilogue
**Before writing.** `docs/HANDOVER.md` is capped — the file states its own limit in its header
(default: ≤5 KB / ~150 lines). Two rules follow from that, and neither is optional:
- **Replace this command's previous epilogue block, do not append a second one.** Stacking is what
  pushes the file over; one skill run has been measured adding 1021 B, ~20 % of the cap.
- **If the file is already near its cap, shorten before you add.** Reading the cap sentence is not
  the same as measuring: check the actual size, and when there is no room, condense existing content
  or hand the user `/cleanup` instead of growing the file further.

Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that fit the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
