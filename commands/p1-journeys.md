# /p1-journeys – Personas & User Journeys

Develops detailed personas, user journeys, and usage scenarios based on the Discovery results. These artefacts form the user foundation for all further conception decisions.

## Argument: $ARGUMENTS = [Persona / scenario focus]

If provided: Focus the work on a specific user type or scenario (e.g. "first-time user", "power user", "mobile usage").
If not provided: Read DISCOVERY.md and CONCEPT.md (if available) and develop personas and journeys for all relevant Target Audience segments. If any context is missing, ask for the focus.

## Execution

### 1. Read Context
Read the following files (if available):
- **DISCOVERY.md** (problem statement, Target Audience sketch)
- **CONCEPT.md** (if already available)
- **FEATURES.md** (if already available)

### 2. Delegate to konzeptor Agent (Lead)
Delegate the content development to the **konzeptor** agent:

> Develop personas and user journeys for the project. Context from DISCOVERY.md: [Insert problem statement, Target Audience]. Focus (if provided): **$ARGUMENTS**
>
> Create:
> 1. **Personas** (2–4): For each persona: name, age, role/occupation, goals, frustrations, technical affinity, typical context of use
> 2. **User Journeys** (at least 3): Per journey: persona, starting situation, steps (actions + thoughts + feelings), touchpoints, pain points, success criterion
> 3. **Scenarios**: Concrete usage scenarios covering edge cases and critical moments
> 4. **Open Questions**: What still needs to be validated with real users?

### 3. Delegate to ux-designer Agent (Support)
Delegate the UX perspective to the **ux-designer** agent:

> Supplement the konzeptor's personas and user journeys with:
> 1. **Information Architecture Implications**: What do the journeys mean for the structure of the application?
> 2. **Critical Interaction Points**: Where are drop-offs or frustration likely?
> 3. **Accessibility Notes**: Which personas have special requirements (visual impairment, motor limitations)?
> 4. **Prioritisation**: Which journey is the most important (critical path)?

### 4. Write Detail File
Write the result to `docs/concept/USER_JOURNEYS.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P1
subskill: journeys
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Personas`, `## User Journeys` (per journey: trigger, steps, pain points, success metric), `## Scenarios`, `## Prioritisation` (which journey is the critical path), `## Open Questions`.

### 5. Update Phase Index
Update `docs/concept/CONCEPT.md` (create from index template if missing — see `~/.claude/docs/PROJECT_PHASES.md`):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[USER_JOURNEYS.md](USER_JOURNEYS.md)` with status `complete`.
- Lift the critical-path persona/journey into **Key Decisions** (e.g. `- Critical journey: <persona> tracking <flow> → see USER_JOURNEYS.md`).
- Add any open question that blocks subsequent subskills under **Open Risks / Open Questions**.

## Result

- **`docs/concept/USER_JOURNEYS.md`** (personas, user journeys, scenarios, open questions)
- **`docs/concept/CONCEPT.md`** (phase index updated)
- Basis for `/p1-features` (feature prioritisation) and `/p3-ux` (UX Concept)

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
