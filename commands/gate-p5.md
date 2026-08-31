---
disable-model-invocation: true
---
# /gate-p5 – Sprint Gate: Check Implementation Quality

Checks at the end of each sprint whether all tasks meet quality standards and the sprint can be considered successfully completed. Called repeatedly after each sprint. No argument – this gate always checks the complete current sprint status.

## No Argument ($ARGUMENTS not applicable)

Gate commands do not accept arguments. They always check the complete current sprint status.

## Execution

### 0. Holistic sprint review (runs automatically, opus)

Before evaluating the gate, ensure the whole-sprint code review exists and is current, then feed its findings into the gate.

**Resolve scope + freshness guard:**
1. Determine the current sprint number `<n>` from `docs/planning/SPRINT.md`'s frontmatter field `sprint: <n>` (or the active `sprint/SPRINT-NN.md`'s `sprint: NN` field, if SPRINT.md is a sub-index) — the same file the `base_commit` below already comes from. Also read `base_commit` from that same frontmatter.
2. A report `docs/reviews/SPRINT-<n>-review.md` is **current** if it exists AND its recorded `reviewed_head` equals the current `git rev-parse HEAD`.
3. **Current** → reuse it; do not re-run (opus is not spent again).
4. **Missing or stale** (HEAD moved since it was written, e.g. after a `/p5-bugfix`) → **run `/p5-review-sprint` now**. That command invokes the `code-reviewer` agent on **opus** — the agent default is `sonnet`, so the opus model is passed explicitly via the command's `**Model**: opus` — scoped to `git diff <base_commit>..HEAD`, and writes/refreshes the report. Invoked as a sub-step here: use its findings; ignore its standalone next-step recommendations (we are already in the gate).

**Use the result:** the holistic review feeds the "Code review" criterion (§2.4). Any unresolved CRITICAL/HIGH finding is a gate blocker → `/p5-bugfix`, then re-run the gate (the guard re-runs the review against the new HEAD).

### 0a. Work-item adoption guard (ADR-0002 §8)

Run `python3 ~/.claude/scripts/workitems.py list` **and** explicitly check whether the
`docs/workitems/` directory exists (e.g. `ls docs/workitems/`). Both signals are required — `list`
returns the identical `[]` for an adopted-but-empty store and a never-adopted project; only the
directory's existence tells them apart, and getting this wrong lets the gate **falsely pass** a
sprint with zero actually-tracked story status.
- **Non-empty list** → the project uses the structured store. Use the CLI for all story-status
  data below (the "Story status" criterion in step 2 and the write-back in step 3), instead of
  reading it from BACKLOG.md prose.
- **Empty list, but `docs/workitems/` exists** → the store is adopted, just empty for this query
  (e.g. every story already archived/migrated). **This is a genuine finding for the "Story status"
  criterion — NOT an exemption to fall back to prose.** Evaluate it as "no stories tracked", not as
  "still on prose".
- **Empty list and no `docs/workitems/` directory** → not adopted, still on prose. Read
  SPRINT.md/BACKLOG.md for story status, as before. Emit one line: *"Tip: run `lift` to adopt the
  structured work-item store."*

See Manual/WORKITEMS.md §8 for the full guard rationale, the directory-check requirement, and the
status-verb mapping.

### 1. Read Preflight Report

Read `docs/.gate-preflight-p5.md` as the primary source of information. This report contains:
- Artifact existence and mandatory sections (mechanically checked)
- Content checks (regex-based: story status, sprint goal)
- Document summaries (via Ollama, if available)

If the preflight report does not exist or is older than 10 minutes, read the sprint documents directly instead:
- **SPRINT.md**, **BACKLOG.md** (or `workitems list`, per the §8 guard above), **reviews/**, **tests/**, **RISKS.md**

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
>
> **Per-story verdict table (structured-store projects only, per the §0a guard):** the criteria
> above are judged at the sprint level, but the write-back in step 3 needs a per-story decision.
> Resolve sprint membership via `workitems list --sprint <n>` (`<n>` resolved in step 0.1 above,
> from SPRINT.md's frontmatter — the same place `base_commit` already comes from) — every item in
> that result is a sprint member; use its id and title directly, no fuzzy title-matching against
> SPRINT.md's Sprint Table needed. If SPRINT.md (or the active sprint detail file) carries no
> `sprint:` frontmatter yet (an older sprint plan predating this convention), fall back to reading
> ids from the Sprint Table's Work-Item column instead — the title-matching fallback is removed; a
> Sprint Table row with no Work-Item id must be backfilled before the gate can score it. Output one
> row per story: `Story | Work-Item id | Verdict (Done / Backlog)`. A story is `Done` only if it
> individually meets criteria 2 and 5 above; otherwise `Backlog` (deferred). This table, resolved
> via the sprint field, is what step 3 below applies `set-status` against.

### 3. Create Gate Protocol

Add the gate result to **SPRINT.md** (sprint review and retrospective — this stays prose narrative,
not item state, per Manual/WORKITEMS.md §10).

**Set `docs/planning/SPRINT.md`'s frontmatter field `gate:`** to this sprint's verdict —
`done` / `conditionally_done` / `not_done`, or `pending` while the gate is still being written.
P5 is the one gate with no `GATE_P5.md`: `SPRINT.md` *is* its gate artifact, which is why the
field lives there and why its vocabulary is the sprint's, not the phase gates'. That field, not
the prose narrative above, is what `scripts/command-check.py` reads to decide whether
`/p6-functional`, `/p6-audit` and `/p6-pentest` are unblocked, and `scripts/phase-docs-lint.sh`
reports a missing or misspelled value as an error. `SPRINT.md` is a living document and is
otherwise exempt from `PHASE_DOC_SCHEMA.md` — `gate:` is its single required field.

Using the guard result from step 0a:
- Structured store: apply the per-story verdict table from step 2 — `workitems set-status <id>
  "Done"` for every row marked Done; `workitems set-status <id> "Backlog"` for every row marked
  Backlog. The table's Work-Item ids are the resolution mechanism, never the story title text.
- Prose fallback: update BACKLOG.md — mark completed stories, return deferred stories to the backlog.

Once wired, item status is never hand-edited in SPRINT.md/BACKLOG.md — those are planning views
(Manual/WORKITEMS.md §8).

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
- Work item statuses updated (structured store) or **BACKLOG.md** updated (prose fallback) with
  completed/deferred stories

## Possible Outcomes

| Decision | Meaning | Next Step |
|---|---|---|
| **Sprint Done** | All criteria met, sprint successful | Recommended: `/p5-polish` (collect & resolve small carry-over TODOs) → then `/p4-sprint` (next sprint) or `/p6-functional` (all sprints done) |
| **Conditionally Done** | Minor open points, no blocker | `/p5-polish` (capture open points via triage) → `/p4-sprint` |
| **Not Done** | Critical open points | Fix blockers via `/p5-bugfix` before next sprint starts |

## Order of Operations (autonomous pipeline)

When this gate runs, perform the operations strictly in this order. The HANDOVER update must precede the cleanup so that an aborted run never leaves a missing handover behind:

1. Add gate result to **`docs/planning/SPRINT.md`** (sprint review + retrospective from §3 above)
2. Structured store: `workitems set-status <id> "Done"` / `"Backlog"` per the per-story verdict
   table (§3 above). Prose fallback: update **`docs/planning/BACKLOG.md`** — mark completed stories
   Done, return deferred stories
3. Update **`docs/HANDOVER.md`** (see Handover Epilogue below)
4. **Cleanup**: `rm -f docs/.gate-preflight-p5.md` (last operation)

P5 is the iterative sprint phase — SPRINT.md, BACKLOG.md and RISKS.md are `status: living` documents and are intentionally not frozen on sprint pass. Phase-wide freeze only happens at `/release-baseline` after gate-p7 Go.

### Handover Epilogue
**Before writing.** `docs/HANDOVER.md` is capped — the file states its own limit in its header
(default: ≤5 KB / ~150 lines). Two rules follow from that, and neither is optional:
- **Replace this command's previous epilogue block, do not append a second one.** Stacking is what
  pushes the file over; one skill run has been measured adding 1021 B, ~20 % of the cap.
- **If the file is already near its cap, shorten before you add.** Reading the cap sentence is not
  the same as measuring: check the actual size, and when there is no room, condense existing content
  or hand the user `/cleanup` instead of growing the file further.

Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that fit the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate

### Cleanup
Last operation, only after the Handover Epilogue is complete: `rm -f docs/.gate-preflight-p5.md` (per CLAUDE.md "Gate Checks: Freshness Guarantee").
