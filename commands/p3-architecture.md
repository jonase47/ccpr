# /p3-architecture – System Architecture, Tech Stack & ADRs

Designs the system architecture, selects the tech stack and documents architectural decisions. Each concern is its own sub-skill.

## Argument: $ARGUMENTS = [Architecture style, e.g. "Monolith", "Microservices", "Single-File"]

If provided: Passed through to the sub-skills.
If not provided: Sub-skills make their own recommendations.

## Flow

### 0. Ensure Phase Index Exists
Make sure `docs/architecture/ARCHITECTURE.md` exists with the standard phase-index header (Status / Last Updated / Key Decisions / Open Risks / Detail Files / Gate Notes — see `~/.claude/docs/PROJECT_PHASES.md`). If missing, create it with empty placeholders. The sub-skills below each refresh their own row in the **Detail Files** table.

**Lean-Index Rule**: `ARCHITECTURE.md` is an **index**, not a detail file. Keep it ≤15 KB. Component descriptions live in `COMPONENTS.md` (or `components/<COMPONENT>.md` if Sub-Index applies). Tech-stack rationale lives in `TECH_STACK.md`. ADRs live under `adr/`. NFRs live in `NFR.md`. The index aggregates one-line decisions and links — nothing else.

### 1. Component Diagram & Data Flows
`/p3-arch-components $ARGUMENTS` – Creates the system architecture overview with component diagram and data flows.

### 2. Tech Stack Decision
`/p3-arch-techstack $ARGUMENTS` – Selects the tech stack and justifies each decision.

### 3. Architecture Decision Records
`/p3-arch-adr` – Documents all significant decisions as ADRs.

### 4. Non-Functional Requirements
`/p3-arch-nfa` – Defines measurable NFRs (scalability, performance, availability).

### 5. Consolidation via Wingman

After all steps are complete: Start the **wingman** agent with the created result files:
> Consolidate the results from: ARCHITECTURE.md, TECH_STACK.md, ADR/, NFR document.

Use the Wingman summary as the basis for presenting results to the user.

### 6. Final HANDOVER Update (Orchestrator-owned)

The orchestrator owns the final `docs/HANDOVER.md` update for this P3 section. Sub-skills (`/p3-arch-*`) also contain a Handover Epilogue — this is intentional, so the sub-skills remain usable on their own. **However, when this orchestrator runs, the orchestrator's HANDOVER update is the authoritative one and supersedes individual sub-skill updates.** Use the Wingman summary from §5 as the basis for the entry.

## Notes
- Steps 1-2 sequential (tech stack requires components)
- Steps 3-4 can run in parallel after 1+2
- Results: ARCHITECTURE.md, TECH_STACK.md, ADR/ directory

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for permitted transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
