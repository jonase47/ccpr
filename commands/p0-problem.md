# /p0-problem – Problem Definition & Target Audience Identification

Defines the core problem of a project or business idea and identifies the first rough Target Audience. The result is a clear problem statement that serves as the foundation for all subsequent phases.

## Argument: $ARGUMENTS = [Project idea / problem area]

If provided: Use as the starting point for the problem analysis.
If not provided: Ask the user for the project idea or problem area before starting. Do not make assumptions.

## Execution

### 1. Read Context
Check whether the phase index `docs/discovery/DISCOVERY.md` and any existing detail files (e.g. `docs/discovery/PROBLEM.md`, `MARKET.md`, `REGULATORY.md`, or legacy `NOTES.md`) exist that can serve as input.

### 2. Delegate to konzeptor Agent
Delegate the main task to the **konzeptor** agent with the following instructions:

> Analyse the following problem area: **$ARGUMENTS**
>
> Work out:
> 1. **Problem Statement** (1 precise sentence: Who has what problem with what consequence?)
> 2. **Problem Deep-Dive** (Why does the problem exist? What are the root causes?)
> 3. **First Target Audience Sketch** (Who suffers most from this problem? 2–3 rough audience segments)
> 4. **Non-Target Groups** (Who is explicitly NOT meant?)
> 5. **Open Questions** (What do you still need to find out to fully understand the problem?)
>
> Ask targeted follow-up questions if the context is insufficient.

### 3. Write Detail File
Write the result to `docs/discovery/PROBLEM.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P0
subskill: problem
status: active   # skeleton | draft | active | frozen | archived | living
last_updated: <DD.MM.YYYY>
---
```

Below the frontmatter, structure the body with the headings: `## Problem Statement`, `## Problem Deep-Dive`, `## Target Audience Sketch`, `## Non-Target Groups`, `## Open Questions`.

### 4. Update Phase Index
Update `docs/discovery/DISCOVERY.md` (create from the index template if missing — see `~/.claude/docs/PROJECT_PHASES.md`):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In the **Detail Files** table: ensure a row exists for `[PROBLEM.md](PROBLEM.md)` with status `complete`.
- Lift the 1-sentence problem statement into **Key Decisions** (e.g. `- Problem: <...> → see PROBLEM.md`).
- If the deep-dive surfaced a critical open question, add a 1-liner under **Open Risks / Open Questions** referencing `PROBLEM.md`.

## Result

- **`docs/discovery/PROBLEM.md`** (detail file with frontmatter and structured body)
- **`docs/discovery/DISCOVERY.md`** (phase index updated)
- Clear problem statement as the basis for `/p0-market` and `/p0-regulatory`

## Note
This command is the first step in P0. Next come `/p0-market` (market assessment) and `/p0-regulatory` (regulatory), before the Go/No-Go Decision is made with `/gate-p0`.

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
