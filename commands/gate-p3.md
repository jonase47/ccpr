# /gate-p3 – Quality Gate 3: Architecture & Design → Planning

Checks whether all architecture and design decisions are completely documented and robust before transitioning into the planning and implementation phase. No argument – this gate always checks the complete checklist.

## No Argument ($ARGUMENTS not applicable)

Gate commands accept no arguments. They always check the complete current project status.

## Execution

### 1. Read Preflight Report

Read `docs/.gate-preflight-p3.md` as the primary information source. This report contains:
- Artifact existence and required sections (mechanically checked)
- Content check (regex-based: diagrams, data flows, trade-offs, ERD, STRIDE, CI/CD, coverage)
- Document summaries (via Ollama, if available)

If the preflight report does not exist or is older than 10 minutes, read the architecture documents directly instead — **always start with the phase index, then the sub-indexes, then detail files only as needed**:

1. **`docs/architecture/ARCHITECTURE.md`** (phase index) — gives you the detail-file table, key decisions, open risks, gate notes.
2. The three sub-indexes called out in the phase index:
   - **`docs/architecture/SECURITY.md`** (sub-index for `/p3-sec-*`)
   - **`docs/architecture/UX_CONCEPT.md`** (sub-index for `/p3-ux-*`)
   - **`docs/architecture/INFRA.md`** (sub-index for `/p3-infra-*`)
3. Direct phase-level detail files only when content checks demand them:
   - `COMPONENTS.md`, `TECH_STACK.md`, `NFR.md`, `DATA_MODEL.md`, `API_SPEC.md`, `COST_ESTIMATION.md`, `ADR/*.md`
4. Sub-index detail files only when the relevant sub-index flags an open question:
   - Security: `THREATS.md`, `AUTH.md`, `DATA_SECURITY.md`, `API_SECURITY.md`, `CHECKLIST.md`
   - UX: `NAVIGATION.md`, `WIREFRAMES.md`, `DARKMODE.md`, `A11Y.md`
   - Infra: `HOSTING.md`, `CICD.md`, `MONITORING.md`, `TESTSTRATEGY.md`

### 1a. Constitution Inviolables (mandatory pre-gate)

If `docs/CONSTITUTION.md` exists, the preflight report (`docs/.gate-preflight-p3.md`) includes a section **"Constitution Inviolables (Required Read)"** with the project's non-negotiable rules.

These Inviolables are mandatory input for the gate:
- Include the Inviolable bullets verbatim in the agent prompt (Step 2 below).
- The agent must check each architecture/security/UX/infra decision against the Inviolables (especially Tech-Stack ADRs, Threat-Mitigations, A11y-Baseline, Privacy-Architecture).
- Any violation is an **"Inviolable breach"** — surface it explicitly in the verdict and treat it as a No-Go signal (Conditional Go only if the user explicitly waives; document the waiver).

If `docs/CONSTITUTION.md` is missing on a Full-Track project, recommend `/constitution` before proceeding (or document an explicit waiver in the gate verdict).

### 2. Delegation to System Architect Agent

Delegate the gate check to the **system-architekt** agent with a focused prompt:

> Gate P3 check. Preflight report (with summaries):
> [insert preflight content here]
>
> Mechanical checks are complete (file existence, sections, content patterns).
> Evaluate content:
> 1. **Architecture**: Components clear, data flows complete?
> 2. **Tech Stack**: Decisions justified, ADRs present?
> 3. **Data Model**: ERD complete, DSGVO (GDPR) fields marked?
> 4. **API Design**: Endpoints sufficient for MVP, auth concept clear?
> 5. **UX & Accessibility**: Sitemap + wireframes present, WCAG target defined?
> 6. **Security**: STRIDE complete, all critical threats addressed?
> 7. **Infrastructure**: CI/CD defined, monitoring + rollback planned?
> 8. **Test Strategy**: Coverage target, all levels with tools?
> 9. **Costs**: Operating Costs estimated for at least 2 scenarios?
>
> For unclear points: read the relevant detail file selectively (the phase index and sub-indexes already point you there).
> Format: Per point assessment (Fulfilled/Partial/Not fulfilled) + 1-2 sentences.
> Overall recommendation: Go / Conditional Go / No-Go.

### 3. Create Gate Protocol

Create **`docs/architecture/GATE_P3.md`** with:
- Result of the mechanical preflight checks (table taken from report)
- Content assessment by the system architect (9 points)
- List of open points with responsibility
- Go/Conditional Go/No-Go recommendation

Also update **`docs/architecture/ARCHITECTURE.md`** (phase index):
- Set `**Status:** Gate Passed (DD.MM.YYYY)` (or `Conditional Go` / `No-Go`).
- Append the verdict and any Conditional-Go conditions under the **Gate Notes** section.
- Add a row in the detail-file table for `[GATE_P3.md](GATE_P3.md)` with the verdict.

---

## Quality Gate 3 – Reference Checklist

The following points are covered by preflight (mechanical) and agent (content):

**Mechanical (Preflight):**
- Phase index `ARCHITECTURE.md` exists with the standard sections
- Sub-indexes `SECURITY.md`, `UX_CONCEPT.md`, `INFRA.md` exist with the standard sections
- All direct detail files exist with frontmatter `status: active`: `COMPONENTS.md`, `TECH_STACK.md`, `NFR.md`, `DATA_MODEL.md`, `API_SPEC.md`, `COST_ESTIMATION.md`; ADR directory non-empty
- All sub-index detail files exist with frontmatter `status: active`: security (5), ux (4), infra (4)
- Content patterns inside the detail files: diagrams, data flows, trade-offs, ERD, DSGVO fields, endpoints, auth, STRIDE, CI/CD, monitoring, coverage

**Content (Agent):**
- Architecture: components clear, data flows complete
- Tech Stack: decisions justified, ADRs present
- Data Model: ERD complete, DSGVO fields marked
- API Design: endpoints for MVP, auth concept
- UX & Accessibility: sitemap, wireframes, WCAG target
- Security: STRIDE complete, critical threats addressed
- Infrastructure: CI/CD, monitoring, rollback
- Test Strategy: coverage target, all levels with tools
- Costs: Operating Costs for 2+ scenarios

---

## Result

- **`docs/architecture/GATE_P3.md`** (gate protocol with checklist, assessment, recommendation)
- **`docs/architecture/ARCHITECTURE.md`** (phase index updated: status, gate notes)

## Possible Outcomes

| Decision | Meaning | Next Step |
|---|---|---|
| **Go** | All architecture artifacts complete and robust | Start with `/p4-backlog` |
| **Conditional Go** | Minor gaps present, bridgeable | Close gaps, then Go |
| **No-Go** | Significant architecture gaps or open security findings | Add missing artifacts |

> **On Go or Conditional Go — recommend `/specialize` before P5.** The tech stack is now finalized across all P3 tracks (stack, infra/CI, security/auth), so this is the richest point to adapt the technical agents (`senior-developer`, `code-reviewer`, `qa-tester`, `debugger`, `devops`, …) to it. This is the **`docs`-mode trigger** for `/specialize`: suggest it as a next step (a proposal, not automatic — it writes a reviewable diff, no commit). Skip the suggestion if the project already has up-to-date specialized local agents for the current stack.

## Order of Operations (autonomous pipeline)

When this gate runs, perform the operations strictly in this order. The HANDOVER update must precede the cleanup so that an aborted run never leaves a missing handover behind:

1. Write **`docs/architecture/GATE_P3.md`** (gate protocol from §3 above)
2. Update **`docs/architecture/ARCHITECTURE.md`** phase index with gate result (status + gate notes, per §3 above)
3. **On Go only** — freeze Phase-P3 detail files: `bash ~/.claude/scripts/freeze-phase-docs.sh P3` (skipped on Conditional Go / No-Go)
4. Update **`docs/HANDOVER.md`** (see Handover Epilogue below)
5. **Cleanup**: `rm -f docs/.gate-preflight-p3.md` (last operation)

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

### Cleanup
Last operation, only after the Handover Epilogue is complete: `rm -f docs/.gate-preflight-p3.md` (per CLAUDE.md "Gate Checks: Freshness Guarantee").
