# /p3-ux – UX Concept, Wireframes & Accessibility

Develops the complete UX concept: navigation, wireframes, dark mode and accessibility. Each area is its own sub-skill.

## Argument: $ARGUMENTS = [Focus, e.g. "Onboarding", "Dashboard", "Mobile"]

If provided: Passed through to the sub-skills.
If not provided: All sub-skills run sequentially.

## Flow

### 0. Ensure Sub-Index Exists
Make sure `docs/architecture/UX_CONCEPT.md` exists as a **sub-index** with the standard header (Status / Last Updated / Key Decisions / Open Risks / Detail Files / Gate Notes — see `~/.claude/docs/PROJECT_PHASES.md`). If missing, create it with empty placeholders. The four `p3-ux-*` sub-skills below each refresh their own row in this sub-index's **Detail Files** table.

### 1. Sitemap & Information Architecture
`/p3-ux-navigation $ARGUMENTS` – Creates sitemap, navigation patterns and critical flows.

### 2. Wireframes for Key Screens
`/p3-ux-wireframes $ARGUMENTS` – ASCII art wireframes with interaction descriptions.

### 3. Dark Mode Color Strategy
`/p3-ux-darkmode` – Semantic colors, critical components, toggle mechanism.

### 4. Accessibility Concept
`/p3-ux-a11y` – WCAG target, contrasts, keyboard navigation, screen reader, testing methods.

### 5. Roll Up Sub-Index to Phase Index
After all `p3-ux-*` sub-skills have run, summarise the UX sub-index into the phase index `docs/architecture/ARCHITECTURE.md`:
- Add an entry in the phase-index **Detail Files** table for `[UX_CONCEPT.md](UX_CONCEPT.md)` (the sub-index itself), status `complete` once all four sub-skill rows are `complete`.
- Lift the headline UX decisions (navigation pattern, WCAG target, dark mode toggle) into the phase-index **Key Decisions**.

### 6. Final HANDOVER Update (Orchestrator-owned)

The orchestrator owns the final `docs/HANDOVER.md` update for this P3 section. Sub-skills (`/p3-ux-*`) also contain a Handover Epilogue — this is intentional, so the sub-skills remain usable on their own. **However, when this orchestrator runs, the orchestrator's HANDOVER update is the authoritative one and supersedes individual sub-skill updates.** Consolidate the four UX detail files into a single HANDOVER entry.

## Notes
- Steps 1-2 sequential (wireframes require sitemap)
- Steps 3-4 can run in parallel after 1+2
- Results: `UX_CONCEPT.md` (sub-index) plus `NAVIGATION.md`, `WIREFRAMES.md`, `DARKMODE.md`, `A11Y.md` detail files

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
