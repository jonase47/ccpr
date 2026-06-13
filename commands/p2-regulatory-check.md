# /p2-regulatory-check – Validate Regulatory Feasibility

Validates the regulatory Assumptions from Phase 1 concretely and practically: Is the venture legally implementable? Which hurdles are real, which are surmountable? The result is a robust regulatory validation as the Decision basis for Gate 2.

## Argument: $ARGUMENTS = [Regulation or area, e.g. "DiGA", "DSGVO Art. 9", "GwG", "MDR"]

If provided: Focus the validation on the named regulation or area.
If not provided: Read ASSUMPTIONS.md and DSGVO_INITIAL_ASSESSMENT.md and check all open regulatory Assumptions. If any context is missing, ask for the relevant regulatory areas.

## Execution

### 1. Read Context
Read the following files (if available):
- **ASSUMPTIONS.md** (regulatory Assumptions with prioritisation)
- **DSGVO_INITIAL_ASSESSMENT.md** (results from `/p1-privacy`)
- **DISCOVERY.md** (regulatory assessment from `/p0-regulatory`)
- **CONCEPT.md** / **FEATURES.md** (What exactly is to be implemented?)

### 2. Delegate to security-master Agent (Lead)
Delegate the regulatory validation to the **security-master** agent:

> Validate the regulatory Assumptions for the following area: **$ARGUMENTS**
> Context from ASSUMPTIONS.md and DSGVO_INITIAL_ASSESSMENT.md: [Insert relevant Assumptions]
>
> Check and evaluate concretely:
>
> **A. DSGVO Feasibility**
> - Are the legal bases identified in DSGVO_INITIAL_ASSESSMENT.md actually applicable?
> - Are the planned technical and organisational measures (TOMs) sufficient?
> - Is a Data Protection Impact Assessment (DPIA) required and feasible?
> - Are data processing agreements (DPA) with all relevant third parties possible?
>
> **B. Sector-Specific Regulation** (if $ARGUMENTS is specific)
> - What are the concrete requirements of this regulation?
> - Which certifications or approvals are needed?
> - How long do these processes typically take?
> - What do they cost (time + money)?
>
> **C. Result per Assumption**
> - ✅ Confirmed: Regulatory implementation feasible
> - ⚠️ Feasible with effort: Describe concrete measures and timeline
> - ❌ Not feasible / knock-out criterion: Clear rationale and alternatives
>
> **D. Recommendations for Action**
> - What must be adjusted in the Concept or MVP scope?
> - What should be legally secured (involve a lawyer)?

### 3. Delegate to konzeptor Agent (Support)
Delegate the impact on the Concept to the **konzeptor** agent:

> Evaluate the security-master's regulatory validation results:
> 1. Which features or data processing must be adjusted or removed?
> 2. Which regulatory requirements become mandatory features (e.g. cookie banner, opt-in)?
> 3. Changes to the timeline due to certification processes?

### 4. Write Detail File
Write the result to `docs/validation/REGULATORY_CHECK.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P2
subskill: regulatory-check
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Validation Method`, `## Findings`, `## Mandatory Features Triggered` (cookie banner, opt-in, deletion flows, …), `## Timeline Impact`, `## Recommendation`.

Cross-file updates:
- Refresh validation status of regulatory assumptions in `docs/validation/ASSUMPTIONS.md`.
- If new findings affect the P1 DSGVO assessment: update `docs/concept/DSGVO_INITIAL_ASSESSMENT.md` and bump `last_updated`.

### 5. Update Phase Index
Update `docs/validation/VALIDATION.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[REGULATORY_CHECK.md](REGULATORY_CHECK.md)` with status `complete`.
- Lift the headline verdict (clear / mandatory features / blocker) into **Key Decisions** with 1-line rationale.
- Add any unmitigated regulatory concern into **Open Risks / Open Questions**.

## Result

- **`docs/validation/REGULATORY_CHECK.md`** (regulatory validation with assessments)
- Updated **`docs/validation/ASSUMPTIONS.md`**
- Possibly updated **`docs/concept/DSGVO_INITIAL_ASSESSMENT.md`**
- **`docs/validation/VALIDATION.md`** (phase index updated)
- Basis for `/gate-p2`

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
