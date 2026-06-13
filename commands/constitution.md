# /constitution – Create or revise the project Constitution

Creates or updates `docs/CONSTITUTION.md` — the project Constitution with three sections
(**Inviolable** / **Default** / **Aspirational**). Read as a mandatory input by all Full-Track
Gates and used as a consistency check for every ADR and implementation decision.

## Argument: $ARGUMENTS = [optional: projectdir]

- No argument: operates on `$(pwd)`.

## Prerequisites

- Template: `~/.claude/templates/CONSTITUTION_TEMPLATE.md`
- Domain bootstraps (for Greenfield mode): `~/.claude/templates/constitution-bootstraps/{slug}.md`
  - If the directory does not exist: fully interactive prompting with no bootstrap suggestions.

## Lead Agent

**konzeptor** with **security-master** consultation for Inviolables (DSGVO, BFSG, sector-specific obligations).

## Mode detection (automatic)

### A) Mode "Existing Full-Track"
Trigger: Phase docs already exist from which Constitution content can be derived:
- `docs/discovery/REGULATORY.md` (Inviolables from regulatory analysis)
- `docs/architecture/ADR/` (Inviolables from "inviolable"-tagged ADRs)
- `docs/architecture/A11Y.md` (A11y minimum standard)
- `docs/architecture/SECURITY.md`, `THREATS.md` (security constraints)
- `docs/architecture/NFR.md` (performance/A11y Aspirational)
- `docs/concept/DSGVO_INITIAL_ASSESSMENT.md` (privacy obligations)

### B) Mode "Lean pre-run"
Trigger: `docs/FRAME.md` exists with a "Constitution-Light" section.

### C) Mode "Greenfield"
Trigger: Neither A nor B applies. No source material available.

## Execution

### 1. Detect mode and bootstrap

**Mode A (Existing Full-Track):**
1. Read all source files listed above that exist.
2. Build a draft proposal per section:
   - Inviolable: from REGULATORY obligations, "inviolable"-tagged ADRs, A11Y minimum standard, NFR security
   - Default: from tech-stack ADRs, language, TDD convention, platform targets
   - Aspirational: from NFR performance, NFR coverage, A11y audit goals, user-research goals
3. Present the draft to the user; ask for refinement per bullet (keep / change / drop).

**Mode B (Lean pre-run):**
1. Read `docs/FRAME.md` section 6 "Constitution-Light".
2. For each Lean-Light bullet: propose promotion to Inviolable or Default, with rationale.
3. Ask for additional Inviolables/Defaults/Aspirationals not captured during the frame phase.

**Mode C (Greenfield):**
1. Ask: "Which domain bootstrap should serve as the starting point?"
   - `saas-b2c` — SaaS, web app, cloud-hosted, B2C end users
   - `mobile-b2c` — native mobile app, B2C, app-store distribution
   - `b2b-tool` — internal B2B tool or B2B SaaS
   - `b2c-marketplace` — marketplace with provider + consumer
   - `on-device-privacy` — privacy-first, no backend, no account
   - `custom` — no bootstrap, fully interactive prompting
2. If a bootstrap is chosen: read `~/.claude/templates/constitution-bootstraps/{slug}.md`, present as draft.
3. Ask per bullet: keep / change / drop / new bullet?
4. Add project-specific Inviolables (e.g. "no cookie banner", "DE market only", …).

### 2. Define the three sections

**Inviolable** (non-negotiable):
- DSGVO obligations (Art. 25 Privacy-by-Design, Art. 32 TOM, Art. 9 for special categories)
- BFSG/A11y minimum standard (WCAG 2.1 AA / 2.2 AA)
- Data security (no secrets in code, no PII in logs)
- Sector-specific obligations (KRITIS, MDR, BaFin, EU AI Act)
- Architecture guardrails from "inviolable"-tagged ADRs

**Bullet format:** `**{Short-Name}:** {Rule}. {Rationale}. **Reference:** {ADR-XXX | Art. X DSGVO | …}`

**Default** (deviate with justification):
- Tech stack (language, framework, DB)
- TDD discipline, coding style
- Language (UI/Docs)
- Platform targets
- Monetization pattern

**Bullet format:** `**{Short-Name}:** {Default}. {When is it appropriate to deviate?}. **Rationale:** {…}`

**Aspirational** (aspirational targets):
- Test coverage threshold
- Performance budget
- A11y audit quality
- Minimum user-research volume
- Adoption/engagement KPIs

**Bullet format:** `**{Short-Name}:** {Target value}. {Measurement method}. **Review frequency:** {…}`

### 3. Set versioning

- Initial creation: `version: 1.0`, `status: active`
- Updating an existing Constitution:
  - Typo / clarification: only `last_updated`, no version change
  - Default/Aspirational change: MINOR bump (1.0 → 1.1)
  - Inviolable change: MAJOR bump (1.0 → 2.0) + ADR required

### 4. Write output

Write `docs/CONSTITUTION.md` with:
- YAML frontmatter: `kind`, `status`, `version`, `last_updated`, `track`, optional `bootstrap`, `related`
- Three sections in fixed order: Inviolable → Default → Aspirational
- Changelog section at the end with entry "v{X.Y} (DD.MM.YYYY): {description}"

**Size limit:** Target ≤8 KB, hard cap 25 KB. Warn and recommend condensing if exceeded.

### 5. Gate integration

After creation:
- Notify the user: "Constitution is now a mandatory read for all Full-Track Gates. `gate-preflight.py` extracts the Inviolable section into the preflight report."
- If ADRs exist that now conflict with the Constitution: list them and recommend an ADR update or Constitution MAJOR bump.

## When to use

- **Full-Track project start:** Called automatically by `/project-init`
- **Lean → Full promotion:** Recommended by `/lean-promote` as a follow-up step
- **Mid-flight:** When new Inviolable requirements arise (compliance update, BFSG scope change, new ADR)
- **Standalone:** When an existing project introduces a Constitution retroactively

## When NOT to use

- Pure Lean project where Constitution-Light in FRAME.md is sufficient — invoke only when Light needs to grow beyond the 5-bullet limit

## Result

- `docs/CONSTITUTION.md` created or updated
- Frontmatter consistent (kind: constitution, version, status, last_updated)
- Three sections complete
- ADR conflicts reported if applicable

### Handover Epilogue

Update `docs/HANDOVER.md`:
- Constitution version (initial / updated)
- ADR conflicts as open items if applicable
- Recommend: verify Constitution read-path at the next Gate
