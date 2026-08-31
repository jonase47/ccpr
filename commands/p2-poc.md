---
disable-model-invocation: true
---
# /p2-poc – Technical Proof of Concept

Builds a minimal technical Proof of Concept for the riskiest technical area of the project. The goal is not a finished feature but proof that the planned approach fundamentally works – before investing in architecture and implementation.

## Argument: $ARGUMENTS = [Technical risk area, e.g. "real-time synchronisation", "AI integration", "payment API"]

If provided: Build the PoC specifically for the named risk area.
If not provided: Read ASSUMPTIONS.md and identify the most technically risky area yourself. If ASSUMPTIONS.md is missing, ask for the biggest technical risk of the project.

## Execution

### 1. Read Context
Read the following files (if available):
- **ASSUMPTIONS.md** (technical Assumptions with highest priority)
- **CONCEPT.md** / **FEATURES.md** (What should the system do?)
- **DISCOVERY.md** (Feasibility assessment from Phase 0)

### 2. Delegate to system-architekt Agent (Lead)
Delegate PoC planning and technical evaluation to the **system-architekt** agent:

> Plan and evaluate a Proof of Concept for the following risk area: **$ARGUMENTS**
> Context: [Insert relevant technical Assumptions from ASSUMPTIONS.md and requirements from CONCEPT.md]
>
> Work out:
>
> **A. Define PoC Scope**
> - What exactly should the PoC prove? (1 clear question that must be answered)
> - What is deliberately NOT part of the PoC? (Scope Boundary)
> - Success criterion: How do we know the PoC is successful?
>
> **B. Choose Technical Approach**
> - Which technology/library/API should be tested?
> - What alternatives exist and why is this approach preferred?
> - Which dependencies (external APIs, SDKs, services) are needed?
>
> **C. Assessment after PoC Execution**
> - ✅ Feasible: Approach works, recommendation for architecture
> - ⚠️ Feasible with limitations: What needs to be adjusted?
> - ❌ Not feasible: Which alternative approach is recommended?

### 3. Delegate to senior-developer Agent (Support)
Delegate PoC implementation to the **senior-developer** agent:

> Implement the Proof of Concept planned by the system architect for: **$ARGUMENTS**
>
> Rules for PoC code:
> - Minimal, focused code – no production code, no boilerplate
> - Comment critical sections and decisions
> - Document problems, limitations, and surprises that arise during implementation
> - Write a brief results report: Did the approach work? What were the biggest hurdles?

### 4. Write Detail File
Write the result to `docs/validation/POC.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P2
subskill: poc
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## PoC Goal`, `## Approach & Stack`, `## Findings`, `## Feasibility Assessment` (technical recommendation Yes / Conditional / No), `## Hurdles & Open Questions`.

PoC code is stored in the project directory under `poc/` (unchanged).

Cross-file update: refresh validation status of technical assumptions in `docs/validation/ASSUMPTIONS.md` and bump its `last_updated`.

### 5. Update Phase Index
Update `docs/validation/VALIDATION.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[POC.md](POC.md)` with status `complete`.
- Lift the feasibility verdict into **Key Decisions** (e.g. `- Technical feasibility: Conditional — depends on <X> → see POC.md`).

## Result

- **`docs/validation/POC.md`** (PoC result with Feasibility assessment)
- Updated **`docs/validation/ASSUMPTIONS.md`** (technical validation results)
- **`docs/validation/VALIDATION.md`** (phase index updated)
- **poc/** (PoC code with documentation)
- Basis for `/p3-architecture`

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
