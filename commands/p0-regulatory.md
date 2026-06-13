# /p0-regulatory – Regulatory & Legal Knock-Out Criteria

Identifies regulatory requirements, DSGVO (GDPR) obligations, and legal knock-out criteria early on, before significant time is invested in the idea. A regulatory showstopper should be recognised as early as possible.

## Argument: $ARGUMENTS = [Area, e.g. "health data", "financial services", "children's app"]

If provided: Use as the focus for the regulatory check.
If not provided: Read DISCOVERY.md to understand the context (Target Audience, data, industry). If context is missing, ask for the relevant area.

## Execution

### 1. Read Context
Read `docs/discovery/DISCOVERY.md` (phase index), `docs/discovery/PROBLEM.md` (problem statement, Target Audience), and `docs/discovery/MARKET.md` (market context) to understand which regulatory areas are relevant.

### 2. Delegate to security-master Agent (Lead)
Delegate the regulatory analysis to the **security-master** agent:

> Conduct a first regulatory assessment for the following area: **$ARGUMENTS**
> Context from PROBLEM.md and MARKET.md: [Insert problem statement, Target Audience, industry]
>
> Check and evaluate:
> 1. **DSGVO Relevance**: What personal data is processed? Which articles apply (Art. 6, Art. 9, Art. 13/14)?
> 2. **Sector-Specific Regulation**: Are there specific laws or regulations (e.g. MDR for medical devices, DiGA, FINMA, GwG)?
> 3. **Licences and Certifications**: Are permits required?
> 4. **Knock-Out Criteria**: What could legally stop or massively delay the project?
> 5. **Assessment**: 🟢 No significant hurdles / 🟡 Hurdles, but surmountable / 🔴 Critical knock-out criterion
>
> Be concrete and practical. Cite relevant laws/regulations.

### 3. Delegate to konzeptor Agent (Support)
Delegate the classification in the project context to the **konzeptor** agent:

> Evaluate the regulatory findings of the security-master: Are the identified hurdles acceptable? What impact do they have on the Concept (scope, timeline, costs)?

### 4. Write Detail File
Write the result to `docs/discovery/REGULATORY.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P0
subskill: regulatory
status: active   # skeleton | draft | active | frozen | archived | living
last_updated: <DD.MM.YYYY>
---
```

Below the frontmatter, structure the body with the headings: `## DSGVO Relevance`, `## Sector-Specific Regulation`, `## Licences and Certifications`, `## Knock-Out Criteria`, `## Assessment` (with the traffic-light rating 🟢/🟡/🔴).

### 5. Update Phase Index
Update `docs/discovery/DISCOVERY.md` (create from the index template if missing — see `~/.claude/docs/PROJECT_PHASES.md`):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In the **Detail Files** table: ensure a row for `[REGULATORY.md](REGULATORY.md)` with status `complete`.
- Lift the traffic-light verdict into **Key Decisions** (e.g. `- Regulatory: 🟢 No significant hurdles → see REGULATORY.md`).
- If the assessment is 🟡 or 🔴, add the concrete hurdle/knock-out one-liner under **Open Risks / Open Questions** referencing `REGULATORY.md`.

## Result

- **`docs/discovery/REGULATORY.md`** (detail file with frontmatter and structured body)
- **`docs/discovery/DISCOVERY.md`** (phase index updated)
- Clear list of regulatory requirements and knock-out criteria
- Basis for the Go/No-Go Decision in `/gate-p0`

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
