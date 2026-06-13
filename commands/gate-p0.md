# /gate-p0 – Quality Gate 0: Discovery → Conception

Checks whether all criteria of the Discovery phase have been met and prepares the Go/No-Go Decision. No argument – this gate always checks the complete checklist.

## No Argument ($ARGUMENTS not applicable)

Gate commands do not accept arguments. They always check the complete current project status.

## Execution

### 1. Read Preflight Report

Read `docs/.gate-preflight-p0.md` as the primary source of information. This report contains:
- Artefact existence (phase index + detail files), mandatory sections, frontmatter status (mechanically checked)
- Content check (regex-based: problem statement, Target Audience, competitors, Feasibility)
- Document summaries (via Ollama, if available)

If the preflight report does not exist or is older than 10 minutes, read the Discovery documents directly instead — **always start with the phase index**:

1. **`docs/discovery/DISCOVERY.md`** (phase index) — gives you the detail-file table, key decisions, open risks.
2. From the index's detail-file table, load only the detail files you need to confirm content:
   - **`docs/discovery/PROBLEM.md`** (problem statement, target audience, non-target groups)
   - **`docs/discovery/MARKET.md`** (market size, demand, competition, economic assessment)
   - **`docs/discovery/REGULATORY.md`** (DSGVO, sector-specific regulation, knock-out, traffic-light verdict)

### 1a. Constitution Inviolables (mandatory pre-gate)

If `docs/CONSTITUTION.md` exists, the preflight report (`docs/.gate-preflight-p0.md`) includes a section **"Constitution Inviolables (Required Read)"** with the project's non-negotiable rules.

These Inviolables are mandatory input for the gate:
- Include the Inviolable bullets verbatim in the agent prompt (Step 2 below).
- The agent must check each evaluated phase-decision against the Inviolables.
- Any violation is an **"Inviolable breach"** — surface it explicitly in the verdict and treat it as a No-Go signal (Conditional Go only if the user explicitly waives; document the waiver).

If `docs/CONSTITUTION.md` is missing on a Full-Track project, recommend `/constitution` before proceeding (or document an explicit waiver in the gate verdict). For Lean-Track, Constitution is optional (Constitution-Light in FRAME.md suffices).

### 2. Delegate to konzeptor Agent

Delegate the gate check to the **konzeptor** agent with a focused prompt:

> Gate P0 check. Preflight report:
> [Insert preflight content here]
>
> Mechanical checks are done (file existence, sections, content patterns).
> Evaluate the content:
> 1. **Problem Definition**: Clear, specific, solvable? (not too broad/too narrow)
> 2. **Target Audience**: Segments plausible, non-target groups defined?
> 3. **Market**: Genuine demand recognisable, competitors known?
> 4. **Feasibility**: Technical/financial/regulatory – any showstoppers?
> 5. **Economic Potential**: Is the investment in Phase 1 worthwhile?
>
> If unclear: load the relevant detail file (PROBLEM.md / MARKET.md / REGULATORY.md) directly.
> Format: Per point assessment (Met/Partially/Not met) + 1-2 sentences.
> Overall recommendation: Go / Conditional Go / No-Go / Pivot.

### 3. Create Gate Protocol

Create **`docs/discovery/GATE_P0.md`** with:
- Result of the mechanical preflight checks (table taken from report)
- Content evaluation by the konzeptor (5 points)
- List of open points with concrete next steps
- Go/Conditional Go/No-Go/Pivot recommendation

Also update **`docs/discovery/DISCOVERY.md`** (phase index):
- Set `**Status:** Gate Passed (DD.MM.YYYY)` (or `Conditional Go` / `Pivot` / `No-Go`).
- Append the verdict and any Conditional-Go conditions under the **Gate Notes** section (do not bury them inside detail files — they belong on the index).
- Add a row in the detail-file table for `[GATE_P0.md](GATE_P0.md)` with the verdict.

---

## Quality Gate 0 – Reference Checklist

The following points are covered by preflight (mechanical) and agent (content):

**Mechanical (Preflight):**
- `docs/discovery/DISCOVERY.md` exists (phase index) with the standard sections (Status, Key Decisions, Open Risks, Detail Files)
- All three detail files exist with frontmatter `status: active`: `PROBLEM.md`, `MARKET.md`, `REGULATORY.md`
- Content patterns inside the detail files: problem statement, Target Audience, competitors, Feasibility

**Content (Agent):**
- Problem Definition: clear, specific, solvable
- Target Audience: segments plausible, non-target groups defined
- Market: genuine demand, competitors known
- Feasibility: no showstoppers technical/financial/regulatory
- Economic potential: investment in Phase 1 is worthwhile

---

## Result

- **`docs/discovery/GATE_P0.md`** (gate protocol with checklist, evaluation, Decision)
- **`docs/discovery/DISCOVERY.md`** (phase index updated: status, gate notes)
- Clear Go/No-Go Decision as a prerequisite for starting Phase 1

## Possible Outcomes

| Decision | Meaning | Next Step |
|---|---|---|
| **Go** | All criteria met | Start with `/p1-journeys` |
| **Conditional Go** | Minor gaps, but bridgeable | Close gaps, then Go |
| **Pivot** | Core Assumptions need adjusting | Back to `/p0-problem` |
| **No-Go** | Knock-out criterion or insufficient potential | Stop project |

## Order of Operations (autonomous pipeline)

When this gate runs, perform the operations strictly in this order. The HANDOVER update must precede the cleanup so that an aborted run never leaves a missing handover behind:

1. Write **`docs/discovery/GATE_P0.md`** (gate protocol from §3 above)
2. Update **`docs/discovery/DISCOVERY.md`** phase index with gate result (status + gate notes, per §3 above)
3. **On Go only** — freeze Phase-P0 detail files: `bash ~/.claude/scripts/freeze-phase-docs.sh P0` (skipped on Conditional Go / No-Go)
4. Update **`docs/HANDOVER.md`** (see Handover Epilogue below)
5. **Cleanup**: `rm -f docs/.gate-preflight-p0.md` (last operation)

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

### Cleanup
Last operation, only after the Handover Epilogue is complete: `rm -f docs/.gate-preflight-p0.md` (per CLAUDE.md "Gate Checks: Freshness Guarantee").
