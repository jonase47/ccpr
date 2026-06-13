# /gate-p5 – Sprint Gate: Check Implementation Quality

Checks at the end of each sprint whether all tasks meet quality standards and the sprint can be considered successfully completed. Called repeatedly after each sprint. No argument – this gate always checks the complete current sprint status.

## No Argument ($ARGUMENTS not applicable)

Gate commands do not accept arguments. They always check the complete current sprint status.

## Execution

### 0. Holistic sprint review (runs automatically, opus)

Before evaluating the gate, ensure the whole-sprint code review exists and is current, then feed its findings into the gate.

**Resolve scope + freshness guard:**
1. Determine the current sprint number `<n>` and its `base_commit` from `docs/planning/SPRINT.md` (or the active `sprint/SPRINT-NN.md` if SPRINT.md is a sub-index).
2. A report `docs/reviews/SPRINT-<n>-review.md` is **current** if it exists AND its recorded `reviewed_head` equals the current `git rev-parse HEAD`.
3. **Current** → reuse it; do not re-run (opus is not spent again).
4. **Missing or stale** (HEAD moved since it was written, e.g. after a `/p5-bugfix`) → **run `/p5-review-sprint` now**. That command invokes the `code-reviewer` agent on **opus** — the agent default is `sonnet`, so the opus model is passed explicitly via the command's `**Model**: opus` — scoped to `git diff <base_commit>..HEAD`, and writes/refreshes the report. Invoked as a sub-step here: use its findings; ignore its standalone next-step recommendations (we are already in the gate).

**Use the result:** the holistic review feeds the "Code review" criterion (§2.4). Any unresolved CRITICAL/HIGH finding is a gate blocker → `/p5-bugfix`, then re-run the gate (the guard re-runs the review against the new HEAD).

### 1. Read Preflight Report

Read `docs/.gate-preflight-p5.md` as the primary source of information. This report contains:
- Artifact existence and mandatory sections (mechanically checked)
- Content checks (regex-based: story status, sprint goal)
- Document summaries (via Ollama, if available)

If the preflight report does not exist or is older than 10 minutes, read the sprint documents directly instead:
- **SPRINT.md**, **BACKLOG.md**, **reviews/**, **tests/**, **RISKS.md**

### 1a. Constitution Inviolables (mandatory pre-gate)

If `docs/CONSTITUTION.md` exists, the preflight report (`docs/.gate-preflight-p5.md`) includes a section **"Constitution Inviolables (Required Read)"** with the project's non-negotiable rules.

These Inviolables are mandatory input for the sprint gate:
- Include the Inviolable bullets verbatim in the agent prompt (Step 2 below).
- The agent must check every shipped story against the Inviolables (e.g. „EXIF-Strip done in image-import", „A11y status-coding uses icon+text").
- Any violation is an **"Inviolable breach"** — surface it explicitly in the sprint verdict; an Inviolable breach is a Sprint-Conditional-Done at best, never a clean Done.

If `docs/CONSTITUTION.md` is missing on a Full-Track project, recommend `/constitution` before further sprints.

### 2. Delegation to Project-Planner Agent

Delegate the sprint gate check to the **project-planner** agent with a focused prompt:

> Sprint gate check. Preflight report:
> [Insert preflight content here]
>
> Mechanical checks are done (file existence, sections, content patterns).
> Evaluate the content:
> 1. **Sprint goal**: Reached (even if not all stories are Done)?
> 2. **Story status**: All Done or justifiably deferred?
> 3. **Tests**: Unit tests green, no ignored tests?
> 4. **Code review**: Per-story review protocols present AND the holistic sprint review (ensured by step 0) has no unresolved CRITICAL/HIGH findings?
> 5. **Acceptance tests**: All Done stories at least "Conditionally Done"?
> 6. **CI pipeline**: Build + tests + lint green on main branch?
> 7. **Velocity**: Story points completed vs. planned – milestone reachable?
>
> If unclear: read the original file selectively.
> Format: Per point a rating (Met/Partially/Not met) + 1-2 sentences.
>
> Also create a 3-point retrospective (what went well / what to improve / velocity).
> Overall recommendation: Sprint Done / Conditionally Done / Not Done.

### 3. Create Gate Protocol

Add the gate result to **SPRINT.md** (sprint review and retrospective).
Update **BACKLOG.md**: mark completed stories, return deferred stories to the backlog.

---

## Quality Gate 5 – Reference Checklist

The following points are covered by preflight (mechanically) and agent (content):

**Mechanical (Preflight):**
- SPRINT.md exists with sprint goal and story status
- src/ and tests/ directories present

**Content (Agent):**
- Sprint goal reached
- Story status: all Done or justifiably deferred
- Tests: unit tests green, none ignored
- Code review: protocols present, no critical findings
- Acceptance tests: Done stories at least "Conditionally Done"
- CI pipeline: build + tests + lint green
- **All sprint changes committed?** (no uncommitted changes)
- **CI green on committed state?** (not just locally)
- Velocity: story points vs. plan, milestone reachable
- Retrospective: what went well / what to improve / velocity

---

## Result

- **SPRINT.md** (updated with gate result, sprint review, retrospective)
- **BACKLOG.md** (updated with deferred stories)

## Possible Outcomes

| Decision | Meaning | Next Step |
|---|---|---|
| **Sprint Done** | All criteria met, sprint successful | Recommended: `/p5-polish` (collect & resolve small carry-over TODOs) → then `/p4-sprint` (next sprint) or `/p6-functional` (all sprints done) |
| **Conditionally Done** | Minor open points, no blocker | `/p5-polish` (capture open points via triage) → `/p4-sprint` |
| **Not Done** | Critical open points | Fix blockers via `/p5-bugfix` before next sprint starts |

## Order of Operations (autonomous pipeline)

When this gate runs, perform the operations strictly in this order. The HANDOVER update must precede the cleanup so that an aborted run never leaves a missing handover behind:

1. Add gate result to **`docs/planning/SPRINT.md`** (sprint review + retrospective from §3 above)
2. Update **`docs/planning/BACKLOG.md`**: mark completed stories Done, return deferred stories
3. Update **`docs/HANDOVER.md`** (see Handover Epilogue below)
4. **Cleanup**: `rm -f docs/.gate-preflight-p5.md` (last operation)

P5 is the iterative sprint phase — SPRINT.md, BACKLOG.md and RISKS.md are `status: living` documents and are intentionally not frozen on sprint pass. Phase-wide freeze only happens at `/release-baseline` after gate-p7 Go.

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
Last operation, only after the Handover Epilogue is complete: `rm -f docs/.gate-preflight-p5.md` (per CLAUDE.md "Gate Checks: Freshness Guarantee").
