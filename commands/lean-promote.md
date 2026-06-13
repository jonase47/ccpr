# /lean-promote – Promote Lean → Full-Track via Promotion Brief

Creates `docs/PROMOTION_BRIEF.md` as a structured bootstrap input for `/project-init`.
Archives Lean artifacts (FRAME, LEARNINGS, CLAUDE-lean) to `docs/lean-archive/`.
Code stays in the same repo; Full-Track decides per module: keep / refactor / rebuild.

## Argument: $ARGUMENTS = [optional: projectdir]

- Without argument: operates on `$(pwd)`.

## Prerequisites

- `docs/FRAME.md` exists
- `docs/LEARNINGS.md` exists AND `decision: promote` OR a mid-flight promotion trigger has fired
- `docs/TRACK_DECISION.md` exists
- Code baseline is committable (clean working tree recommended)
- Template: `~/.claude/templates/PROMOTION_BRIEF_TEMPLATE.md`

## Lead Agent

**konzeptor** for content consolidation, **project-planner** for catch-up obligations and Backlog proposals.

## Execution

### 1. Prerequisites Check

- If `docs/FRAME.md` or `docs/LEARNINGS.md` is missing → STOP with a note indicating which skill must run first.
- If `LEARNINGS.md` decision is not `promote` AND no mid-flight trigger was specified → ask: "Which promotion trigger? (PROMOTE / mid-flight-1..5)" — for mid-flight, request a rationale.
- Code baseline: `git status` — if the working tree is dirty, ask for user confirmation.
- Capture commit SHA via `git rev-parse HEAD` for frontmatter.

### 2. Read Materials

Load:
- `docs/FRAME.md` (all 8 sections)
- `docs/LEARNINGS.md` (hypothesis check, what works / does not work, surprises)
- `docs/TRACK_DECISION.md` (most recent entry — prerequisites, Knockouts, Indicators)
- `docs/CONSTITUTION.md` if applicable (if Lean already extended it)

### 3. Derive PROMOTION_BRIEF Sections

Consolidate — not a plain copy, but a condensed synthesis:

**1. Validated Findings** (from LEARNINGS "what works" + confirmed hypothesis check)
→ Per finding: concrete statement + 1-line evidence note.

**2. Confirmed Assumptions** (from FRAME section 7 "risk assumptions → what must work" — those that held)
→ Each tagged with Full-Track phase: `→ relevant for P0-problem | P1-features | P3-techstack | …`

**3. Refuted Assumptions** (from LEARNINGS "what does not work" and incorrect FRAME assumptions)
→ With lessons: why not? Full-Track must NOT carry these over.

**4. Open Questions** (from LEARNINGS "surprises" and FRAME questions Lean could not answer)
→ With phase tag: `→ to clarify in: P0 | P1 | P2 | …`

**5. Code Anchors** — module status table:
- If LEARNINGS already has a module table (from a previous pivot): carry it over
- Otherwise: collect interactively per top-level directory in `src/`:
  - `working` — hypothesis-validated, Full-Track can adopt
  - `needs-rebuild` — quick-and-dirty, Full-Track should implement cleanly
  - `needs-tests` — functionally OK, test coverage insufficient

**6. Constitution Candidates** (from FRAME section 6 "Constitution-Light")
→ Per Lean-Light bullet: proposed classification "Inviolable | Default | Aspirational" for the full Constitution.

**7. Catch-Up Obligations** (Full-Track topics that Lean skipped)
→ Default list, extended per project:
- `/p0-regulatory` — regulatory check
- `/p1-privacy` — DSGVO data classification
- `/p3-security` — threat model + auth concept
- `/p3-ux-a11y` — A11y concept (WCAG level specific)
- `/p6-audit` — security audit + dependency check
- `/p6-a11y` — A11y check

### 4. Write PROMOTION_BRIEF.md

Write `docs/PROMOTION_BRIEF.md` with:
- YAML frontmatter: `kind: promotion-brief`, `generated_from: lean-track`, `trigger`, `code_baseline_commit`, `last_updated: DD.MM.YYYY`, `related: [lean-archive/FRAME.md, lean-archive/LEARNINGS.md, TRACK_DECISION.md]`
- 7 sections in fixed order

**Size check:** target ≤10 KB. Condense if exceeded.

### 5. Archiving

Create `docs/lean-archive/` if it does not yet exist. Move:

```
docs/FRAME.md           → docs/lean-archive/FRAME.md
docs/LEARNINGS.md       → docs/lean-archive/LEARNINGS.md
docs/CLAUDE-lean.md     → docs/lean-archive/CLAUDE-lean.md
```

`docs/TRACK_DECISION.md` stays in place — Full-Track continues to read from it (especially `re_assessment_count`).

For pivot versions, do not overwrite existing archives — if `lean-archive/FRAME.md` already exists (e.g. from an earlier pivot), move `FRAME.md` to `lean-archive/FRAME_at_promotion_{DD.MM.YYYY}.md` instead.

### 6. Next Step

Recommend to the user:

```bash
# Stay in the same repo:
/project-init   # reads PROMOTION_BRIEF.md, starts Full-Track
```

Explanation:
- `/project-init` detects PROMOTION_BRIEF.md and uses it as bootstrap (instead of a greenfield questionnaire)
- Validated findings → P0 input
- Constitution candidates → proposal for `/constitution`
- Catch-up obligations → Backlog stories (via `/p4-backlog` later)
- `docs/CLAUDE-lean.md` is archived; `/project-init` creates the full `.claude/CLAUDE.md`

## When to use

- **PROMOTE decision** from `/lean-learn`
- **Mid-flight trigger** (PII introduced, lifespan >3 months, stakeholder requires Gates, compliance audit, codebase >5k LOC)
- **External requirement** (investor, client, compliance audit)

## When NOT to use

- If LEARNINGS says "pivot" or "drop" — other follow-up skills apply there
- If FRAME is not yet stabilised (run `/lean-frame` re-frame first)

## Result

- `docs/PROMOTION_BRIEF.md` created (≤10 KB, 7 sections)
- `docs/lean-archive/` with FRAME, LEARNINGS, CLAUDE-lean (or versioned variants)
- Code baseline commit SHA documented
- TRACK_DECISION.md remains active

### Handover Epilogue

Update `docs/HANDOVER.md`:
- PROMOTION_BRIEF created — note trigger and commit SHA
- Lean artifacts archived
- Recommendation: `/project-init` as next step (in the same repo) — uses the brief as bootstrap
