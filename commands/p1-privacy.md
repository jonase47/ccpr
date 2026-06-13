# /p1-privacy – Data Classification & DSGVO Initial Assessment

Conducts a systematic initial assessment of data protection requirements: What personal data is processed, on what legal basis, and what DSGVO (GDPR) obligations arise from this? The result is a well-founded DSGVO initial assessment as a mandatory component of the Concept.

## Argument: $ARGUMENTS = [Data type, e.g. "health data", "payment data", "location data"]

If provided: Focus the analysis on the specified data category and its special requirements.
If not provided: Read FEATURES.md, USER_JOURNEYS.md and BUSINESS_MODEL.md to determine all processed data categories yourself. If any context is missing, ask for the types of data being processed.

## Execution

### 1. Read Context
Read the following files (if available):
- **FEATURES.md** (Which functions process data?)
- **USER_JOURNEYS.md** (What data is generated during usage?)
- **BUSINESS_MODEL.md** (Which data is relevant to the revenue stream?)
- **DISCOVERY.md** (Results from `/p0-regulatory` if available)

### 2. Delegate to security-master Agent (Lead)
Delegate the DSGVO analysis to the **security-master** agent:

> Conduct a DSGVO initial assessment. Focus (if provided): **$ARGUMENTS**
> Context from the project files: [Insert features, user journeys, business model]
>
> Create:
>
> **A. Data Classification**
> | Data Category | Examples | Sensitivity | DSGVO Category |
> |---|---|---|---|
> | (e.g. contact data) | (name, email) | Standard | Art. 4 No. 1 |
> | (e.g. health data) | (diagnoses) | Particularly sensitive | Art. 9 |
>
> **B. Processing Purposes & Legal Bases**
> - For each purpose: Which legal basis applies? (Art. 6 Para. 1 a–f DSGVO)
> - Special categories (Art. 9): Which exception applies?
>
> **C. Data Subject Rights**
> - Access (Art. 15), Rectification (Art. 16), Erasure (Art. 17), Portability (Art. 20)
> - What must be technically implemented?
>
> **D. Obligations & Measures**
> - Privacy policy required? (Art. 13/14)
> - Data processing agreements (DPA) with third parties?
> - Data Protection Impact Assessment (DPIA) required? (Art. 35)
> - Record of processing activities (Art. 30)?
>
> **E. Risk Assessment**
> - What data protection risks exist?
> - Technical and organisational measures (TOMs) recommended?

### 3. Delegate to konzeptor Agent (Support)
Delegate the impact on the Concept to the **konzeptor** agent:

> Evaluate the DSGVO findings of the security-master from a product perspective:
> 1. Which features must be adjusted or removed?
> 2. What must be added to FEATURES.md as a mandatory function (e.g. data deletion, export)?
> 3. Are there privacy features that can be communicated as a differentiating characteristic?

### 4. Write Detail File
Write the result to `docs/concept/DSGVO_INITIAL_ASSESSMENT.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P1
subskill: privacy
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Data Classification`, `## Legal Bases` (Art. 6/9), `## Data Subject Rights`, `## Obligations` (Art. 13/14, AVV, DPIA), `## Risk Assessment`, `## Recommendations`.

If new mandatory features surfaced (data deletion, export, consent flow), append them to `docs/concept/FEATURES.md` and bump that file's `last_updated` frontmatter.

### 5. Update Phase Index
Update `docs/concept/CONCEPT.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[DSGVO_INITIAL_ASSESSMENT.md](DSGVO_INITIAL_ASSESSMENT.md)` with status `complete`.
- Lift the headline data-classification verdict into **Key Decisions** (e.g. `- Processes Art. 9 health data → DPIA required → see DSGVO_INITIAL_ASSESSMENT.md`).
- Add any DSGVO open question into **Open Risks / Open Questions** for `/p3-security` to address.

## Result

- **`docs/concept/DSGVO_INITIAL_ASSESSMENT.md`** (data classification, legal bases, data subject rights, obligations, risk assessment)
- Possibly updated **`docs/concept/FEATURES.md`** (privacy-compliant mandatory functions added)
- **`docs/concept/CONCEPT.md`** (phase index updated)
- Basis for `/p3-security` and DSGVO review in Gate 6

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
