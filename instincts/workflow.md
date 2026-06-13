---
name: instincts-workflow
description: Global instincts for skill pipelines, gates, plan-mode triggers, sprint mechanics, PO-decisions, push/commit policy and memory-override awareness. Loaded as Tier-1-global topic file alongside the slim index in `~/.claude/instincts.md`. Curated starter examples — adapt and extend through your own `/postmortem` runs.
type: instincts
scope: tier-1-global-topic
last_updated: 04.06.2026
---

# Skill / Workflow / Sprint Instincts

Behavioural rules for sequencing skills, holding gate preconditions, planning multi-wave sprints, persisting product-owner decisions immediately, and respecting project memory overrides. Sorted by confidence (descending).

---

### G-015: Document PO decisions immediately
**Confidence: 0.9** | Last confirmed: starter set

> **Rule**: Persist stakeholder / product-owner decisions immediately in *all* affected files (key-decisions table in CLAUDE.md, BACKLOG.md, PROJECT_PLAN.md, RISKS.md, possibly sprint files).
>
> **Why**: Decisions that live only in the chat get lost across session changes. "Implicitly documented in HANDOVER" is not enough — cross-reference in the domain files is mandatory.
>
> **How to apply**:
> - After every decision: identify affected files (at minimum the CLAUDE.md key-decisions table)
> - Persistence in **one** pass (not "I'll do it later" — that gets forgotten)
> - Date + phase + rationale in the table

---

### G-016: End sessions after 2 sprints (multi-skill hygiene)
**Confidence: 0.9** | Last confirmed: starter set

> **Rule**: Limit sessions to max. 2 skill workflows or 1 sprint. At HighToolCount=200 or TokenBudgetWarning@150: close the session cleanly (commit + push + HANDOVER update), then `/compact` or a new session.
>
> **Why**: Long sessions accumulate stagnation warnings, the token budget runs low, context drift makes later skills less accurate. Empirically: 4-skill sessions reach 200+ tool calls and reasoning quality drops.
>
> **How to apply**:
> - Watch the indicators: HighToolCount=200, TokenBudgetWarning, ≥100 stagnation warnings
> - Skill limit: max. 2 substantive skills (e.g. `/p5-implement` + `/p5-review`) or 1 large skill (`/p4-backlog`)
> - Sprint limit: 1 sprint close-out per session
> - Before a new session: commit HANDOVER.md, optionally `/compact`
>
> **Multi-skill sub-rule**: the pattern extends from sprint sessions to multi-skill phase sessions. Trigger for session end: after 2 large skills (e.g. `/p3-ux` + `/p3-infra`) proactively commit + `/postmortem` + new session — even when the next skill seems small.
>
> **Re-setup sub-rule**: A skill iteration with extensive re-setup (e.g. wrong template → targets deleted and recreated with source-backup roundtrip + cleanup commits) counts as an additional skill. Trigger for session end: after re-setup proactively split, even when only 1 nominal skill ran.
>
> **Bulk-curation sub-rule**: The pattern also applies to sequential bulk-edit sessions without classical skill structure (source curation, knowledge migration, bulk translation). Rule of thumb: one minor-version bump wave (≥4 curated files) corresponds to one skill in terms of token consumption. After 2 version bumps: proactively split.

---

### G-044: Verify skill-prescribed frontmatter against the project schema
**Confidence: 0.6** | Last confirmed: starter set

> **Rule**: When a skill template instruction prescribes a concrete frontmatter value (e.g. `status: complete`), check it against the project schema (`PHASE_DOC_SCHEMA.md`, `MEMORY_SCHEMA.md`) before writing. On a mismatch, use the semantically closest project-allowed value.
>
> **Why**: A `/p4-sprint` skill instructed `status: complete` for archived files; the project schema (`PHASE_DOC_SCHEMA.md`) only allows `{skeleton, draft, active, frozen, archived, living}`. This produced 1 lint-fail + 1 follow-up edit. `archived` (or `living` for conditionally-done docs with open conditions) was the correct semantic match.
>
> **How to apply**:
> 1. For frontmatter-writing skill steps (especially archive/migrate operations) check the prescribed value against the `enum` list in the project schema.
> 2. Schema paths: `~/.claude/templates/PHASE_DOC_SCHEMA.md`, `~/.claude/templates/MEMORY_SCHEMA.md`.
> 3. If the skill value isn't allowed: take the semantically closest allowed value — do not adopt it blindly.
>
> **Related**: G-032 in `agents.md` (verify optional paths) — same pre-apply verification philosophy. G-068 below (skill-output language default) — analogous skill-default vs project-override pattern.
>
> **Context**: All skill steps that prescribe frontmatter values (status/kind/type fields). Skill templates can lag behind the project schema state.

---

### G-067: StagnationWarning is a false-positive during long-running subagents or user-decision waits
**Confidence: 0.6** | Last confirmed: starter set

> **Rule**: When a StagnationWarning burst occurs while (a) a subagent is actively running (started in the same or previous tool call, no SubagentStop yet) OR (b) the orchestrator is waiting for an answer to a user decision (multi-choice OQ, PO dialog, pending AskUserQuestion), ignore it as a false-positive. The orchestrator wait IS productive — the harness re-invokes on agent completion or a user prompt automatically.
>
> **Why**: StagnationWarning measures orchestrator tool inactivity, not session productivity. Long-running subagents (multi-file sweeps, large GREEN phases, acceptance reports) produce 10-40 min of orchestrator idle; deep PO dialogs with substantial user feedback produce 30-180 min pauses. Reacting to every stagnation warning would falsely abort agents, start polling loops, or interrupt the user with pings — all counterproductive.
>
> **How to apply**:
> 1. **Symptom**: StagnationWarning cluster (3+ in 5 min) without new user prompts.
> 2. **Disambiguate**: (a) is there an `AgentSlow` warning in the same window OR a SubagentStart without a SubagentStop → agent wait. (b) was the last orchestrator output an open question / AskUserQuestion / multi-choice OQ without a user answer → decision wait.
> 3. **Agent running** → ignore. The harness re-invokes on completion.
> 4. **User decision pending** → ignore. The harness re-invokes on the user prompt — no proactive ping.
> 5. **Neither** → real stagnation: close the skill, give a status update, or enter plan-mode for the next step.
>
> **Anti-pattern**: reacting to StagnationWarnings with tool-polling (`ls`/`git status` spam), killing an agent with `TaskStop` because "it seems idle", or interrupting the user with a proactive status ping while they are still answering/researching.
>
> **Related**: G-016 above (end sessions after 2 sprints) — real stagnation triggers (session-length fatigue), not warning clusters.

---

### G-035: Clarify open decision points before ExitPlanMode
**Confidence: 0.5** | Last confirmed: starter set

> **Rule**: When a plan file contains an "Open decision points" / "Open questions" / "To clarify" section that leaves real design decisions open, ask `AskUserQuestion` first and work the answers into the plan before calling `ExitPlanMode`. Don't go into `ExitPlanMode` with them open.
>
> **Why**: In a `/p5-polish` session the plan had two open points; the user rejected the first `ExitPlanMode` call, answered both in plain text, and the plan had to be amended before a second `ExitPlanMode` succeeded. Clean clarification up front would have saved a whole round-trip. Plan-workflow phase 3 (review) is meant exactly for this.
>
> **How to apply**:
> 1. Before `ExitPlanMode`: scan the plan file for "Open decision points", "Open questions", "To clarify", "TBD".
> 2. If present and not purely editorial: `AskUserQuestion` with max 1–3 options per point.
> 3. Work the answers into the plan, remove the section.
> 4. Only then call `ExitPlanMode`.
> 5. Exception: "Optional later extensions" / "Out of scope" lists are fine and don't need clarification — the heuristic only covers real pre-implementation decisions.

---

### G-036: Pre-gate working-tree clean sweep
**Confidence: 0.5** | Last confirmed: starter set

> **Rule**: Before every `/gate-pX` skill trigger, run `git status --porcelain` orchestrator-side. If the output is non-empty: assign and commit all sprint artefacts (tests, worker outputs, memory updates, gate reports, modified docs) explicitly before the gate skill starts.
>
> **Why**: Gate skills (`/gate-p5`, `/gate-p6`, `/gate-p7`) have "working tree clean" as a hard precondition. Uncommitted changes at gate start block the skill — you then have to do mid-skill cleanup, which interrupts the skill output messily.
>
> **How to apply**: A cleanup sequence right before each gate-skill call:
> 1. Run `git status --porcelain`.
> 2. If empty: trigger the skill.
> 3. If non-empty:
>    - **Modified files** (`M ...`): typically SPRINT.md / BACKLOG.md / RISKS.md / HANDOVER.md / Tier-2 memory → bundle into a "pre-gate handover" commit.
>    - **Untracked files** (`?? ...`): typically tests / worker outputs / reports → group by content into 1–2 commits (`chore(s-XX): commit untracked test` or `docs(gate-pX): worker outputs`).
>    - Then trigger the skill.
>
> **Related**: G-032 in `agents.md` (pre-existence check for memory files) — similar pre-check hygiene.

---

### G-043: Track conditional-go conditions with persistent C-IDs
**Confidence: 0.5** | Last confirmed: starter set

> **Rule**: In gate protocols, name conditional-go conditions with a unique ID (C1/C2/…) and reference them in the phase index + HANDOVER open-decisions, so open conditions stay visible through the following phases.
>
> **Why**: A Gate P0 with 5 hard entry conditions had no IDs. Condition 5 was not met by Gate P1 and migrated forward as "C1" — with an ID convention it is more visible and referenceable in HANDOVER, the concept doc's open risks, and the next gate.
>
> **How to apply**:
> 1. In the GATE_PX.md "conditional-go conditions" section, ID every line with C1/C2/…
> 2. In the phase index, point open-risks for the conditions at the gate IDs ("C1 from Gate P1") — not just a description.
> 3. In HANDOVER.md, carry the C-IDs in the decision column.
> 4. At a follow-up gate, status-check which C-IDs from prior gates are still open.
>
> **Related**: G-039 below (skill-precondition sequence check) — same traceable-IDs philosophy. G-065 below (PoC-verdict cascade) — analogous cross-reference discipline.
>
> **Context**: Every `/gate-pX` with a "Conditional Go" verdict. Saves searching in later phases when open conditions are re-activated.

---

### G-068: Skill output language defaults to chat language instead of the project doc convention
**Confidence: 0.5** | Last confirmed: starter set

> **Rule**: Skills that produce user-facing docs (`/p0-*`, `/p1-*`, `/constitution`, `/gate-*`, `/p3-*`, …) tend to write prose in the **chat language** instead of the project's required **doc language**. Before triggering any skill that writes a user-facing document, set the doc-language convention explicitly — via a CONSTITUTION pre-read, a project-memory check, or an explicit language clause in the subagent brief.
>
> **Why**: The chat context (e.g. German) dominates the output language model without an explicit counter-instruction, even when the project-wide standard is English. Constitution defaults and project memory are not auto-prefetched by the skill workflow. Cost per lapse: 1 translate-commit + a review round + user frustration; at 3 lapses/session ~30-45 min wasted + repo noise.
>
> **How to apply**:
> 1. **Pre-skill check (user-facing docs)**: before `/p0-*`, `/p1-*`, `/constitution`, `/gate-*`, `/p3-*`, check whether `docs/CONSTITUTION.md` exists and carries a language rule in Default/Inviolable. Prepend the resulting language convention to the skill.
> 2. **Project-memory lookup**: grep `docs/memory/MEMORY.md` for `*language*` / `*doc-language*` entries before output is produced.
> 3. **Subagent brief**: when delegating doc work, ALWAYS include an explicit "Output language: <X> prose, preserve [legal/domain terms]" clause — not just "<X> + native legal terms" (ambiguous — agents then write whole docs in the wrong language).
> 4. **Self-check post-write**: scan the first 30 lines of the finished doc. Sentences outside the kept legal/domain-term whitelist in the wrong language → translate before commit.
> 5. **Conversation stays in the chat language**: this rule covers doc/code/commit output, not the chat dialog with the user.
>
> **Anti-pattern**: trigger skill → produce output in chat language → await user correction → push a translate-commit afterwards. 3× per session → a pattern, not a one-off.
>
> **Related**: G-044 above (skill-prescribed frontmatter vs project schema) — analogous skill-default vs project-override pattern.
>
> **Context**: Multi-lingual projects with a non-English-speaking PO + English-conventioned doc standards (DACH B2B SaaS, international reviewers/investors/contributors). Especially critical in P0–P3 where skills generate a lot of prose. Legal/DSGVO docs keep a domain-term whitelist (DSGVO, AVV, DSFA, VVT, TOM, Art. X DSGVO, § X TMG, BfDI, DSK, BSI).

---

### G-049: Volatile skill outputs need an immediate gitignore entry
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: When a skill writes generator output to `docs/.<name>-report.md`, `docs/.<name>-preflight-*.md`, or similar dotfiles, simultaneously produce a `.gitignore` pattern suggestion — either in the skill output or as a warning to the user.
>
> **Why**: Pre-commit hooks in the project may accidentally stage volatile dotfiles. Retroactive `.gitignore` extension costs an extra commit. Known skills with volatile output: `gate-preflight`, `cross-check`, `quality-scan`, `bootstrap` (`docs/.session-context.md`).
>
> **How to apply**:
> - **During skill design**: if the skill produces output under `docs/.<...>` → potentially volatile → `.gitignore` recommendation in the skill's "result" block
> - **When migrating to existing projects**: actively check whether the project has a pre-commit hook; adjust `.gitignore` pro-actively
> - **Standard block** for `.gitignore` in CCPR projects:
>   ```
>   # Volatile generator outputs in docs/
>   docs/.gate-preflight-*.md
>   docs/.session-context.md
>   docs/.quality-scan-report.json
>   docs/.cross-check-report.md
>   ```

---

### G-050: Doc coverage via Glob list, not from memory
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: For cross-phase doc updates (a new feature that must be mentioned in several reference files): build a glob list of all relevant `~/.claude/docs/*.md` and project `docs/*.md` files, **check each one individually** (Read or grep), and only then confirm coverage.
>
> **Why**: Cross-doc updates from memory typically forget 1–2 files. At 5+ files the forgetting probability rises to practically 100 %. Plus: within-file coverage (header + summary tables + TOC + body) is often incomplete — updates in one spot are not enough.
>
> **How to apply**:
> - **Before cross-doc updates**: `ls ~/.claude/docs/*.md` OR `find <docs-root> -name "*.md" -maxdepth 2` for a complete list
> - **Per file**: `grep -l '<feature-keyword>' <file>` AND `grep -n '<old-count>' <file>` — the latter finds stale counts / tables
> - **Within-file check**: check multiple spots (header, summary, TOC, body) — updates in one spot are not enough
> - **Rule of thumb**: at 5+ doc files, never work from memory

---

### G-037: Plan-mode trigger for multi-wave sprints
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: Before `/p5-implement` for sprints with **≥10 SP** + **≥3 stories** + **≥1 HIGH-risk story**, first `EnterPlanMode` with a wave sketch (Polish → Foundation → Core-Refactor → Closer). Plan-mode clarifies wave order, the mid-sprint-review slot and wave-end checkpoints **before** the first story commit. For smaller sprints (≤2 stories, ≤5 SP), story-by-story pickoff from SPRINT-NN.md is enough.
>
> **Why**: A 14-SP / 5-story / 1-HIGH-risk sprint executed cleanly with an explicit mid-sprint review after wave 3. Without plan-mode the review would have been ad-hoc — and late-discovered HIGH findings become next-sprint carry-forward instead of being resolved in-scope.
>
> **How to apply**:
> 1. On a `/p5-implement` call, first scan SPRINT-NN.md: SP sum + story count + RISKS.md severity tags of the sprint stories.
> 2. If the trigger criteria are met: `EnterPlanMode`, write a wave sketch.
> 3. `ExitPlanMode` after user approval → only then start the sub-skill calls.
> 4. If criteria are NOT met: go straight to the per-story sub-skill sequence.
>
> **Related**: G-035 above (clarify open points before ExitPlanMode); G-039 below (read skill preconditions before plan-mode) — complementary.

---

### G-039: Read skill preconditions before a plan-mode multi-skill sequence
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: For plan-mode covering a multi-skill sequence (3+ skills in a row, e.g. a wave-5 closeout with `/p5-acceptance` + `/p5-review` + `/p5-polish` + `/p5-docs` + `/gate-p5`), read the individual skill definitions under `~/.claude/commands/{skill}.md` **before** writing the plan. Especially: hard preconditions ("Gate-p5 passed", "working tree clean", "CI green") + the skill's own ordering hint ("runs **between** X and Y").
>
> **Why**: A plan placed `/p5-polish` between `/p5-review` and `/p5-docs`. But `/p5-polish` has the hard precondition "Gate-p5 passed" — it **must** run after `/gate-p5`. The plan had to be corrected mid-skill ("skill convention beats plan sequence"). Reading the skill defs up front would have prevented it — a skill-correction round-trip is more expensive than 5× a skill-spec read.
>
> **How to apply**:
> 1. In plan-mode phase 2 (design): for each planned sub-skill read `~/.claude/commands/{skill}.md`. Check "Preconditions" + the header text ("Runs between X and Y") + "Notes".
> 2. Adjust the plan sequence to the skill constraints before `ExitPlanMode`.
> 3. For skills without plan-mode (direct in the skill loop): not relevant.
>
> **Anti-pattern**: "deriving the order from sprint-N experience" — skills evolve; an order that was OK in sprint 1 can be wrong in sprint 3 because a new hard precondition was introduced.
>
> **Related**: G-035; G-037 above (plan-mode trigger) — complementary: G-037 says WHEN plan-mode, G-039 says HOW the plan is structured.

---

### G-041: Offer push points in long pipelines proactively
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: In autonomous pipelines with 3+ consecutive skill commits, actively offer the user a push point instead of surfacing the backlog only at the pipeline end.
>
> **Why**: A pipeline session ended with 5 unpushed commits. Under a "user pushes themselves" policy, every commit is a user decision; pushing 5+ at once raises the diff-review load and removes the chance to fix interim states on the remote between skills.
>
> **How to apply**:
> 1. After every 2nd–3rd skill commit in an autonomous pipeline: a compact push hint in the status report (e.g. "X commits unpushed, `git push origin main`").
> 2. At skill transitions (e.g. after a sub-skill, before a gate) mention the push option explicitly.
> 3. At the latest after 3 commits without a push hint: actively offer.
>
> **Context**: A "user pushes themselves" policy active AND auto-mode AND >2 consecutive commits without a push. Especially in multi-skill sessions (4+ skills in a row).

---

### G-065: PoC-verdict cascade — after a ❌ spike, re-check other assumptions/features/ADRs
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: When a PoC spike produces a ❌ verdict, run an **explicit cascade round**: which **other** assumptions, features or ADR-relevant decisions share the now-refuted mechanism? Findings go not only into `POC.md` but propagate into `ASSUMPTIONS.md` (falsify other AS-IDs), `FEATURES.md` (affected F-IDs → Won't / to-recheck), `MEMORY.md` (correct outdated key decisions), `CONSTITUTION.md` (if an Inviolable/Default is affected — a MAJOR-bump candidate). Cross-file updates are a mandatory part of the `/p2-poc` output, not "nice to have".
>
> **Why**: PoC skills are scoped to one top-risk assumption. But diagnostic runs follow the mechanism, not the assumption — and often expose systematic problems that falsify several assumptions at once. Example: a spike scoped to "is iCloud VTODO feasible" revealed that the whole CalDAV path is shut off for third-party apps — which would also drop two dependent features and an architectural anchor, but only if propagated. Otherwise P3 starts with stale cross-files and corrects itself only later (worst case in P5 when a sprint goal runs into the wall).
>
> **How to apply**:
> 1. **After a ❌ verdict** (or ⚠️ with a substantial mechanism gap): an explicit cascade round in the skill output.
> 2. **Checklist**: which other ASSUMPTIONS entries share the refuted mechanism (library, API, protocol, architecture pattern)? Which FEATURES IDs hang on the same path? Which earlier "key decision" in MEMORY/CONSTITUTION is now outdated? Which ADRs must be re-opened?
> 3. **Execute the cross-file updates explicitly** and mention them in the POC.md output (section "Cascade updates"). Not "will be done in P3" — the next skill wave is `/gate-p2`, which reads the cross-files.
> 4. **Escalate the pivot severity** (e.g. "Medium → High") when the cascade hits >2 further items.
>
> **Related**: G-043 above (track conditional-go with C-IDs) — analogous cross-reference discipline for gates.
>
> **Context**: P2 phase (`/p2-poc`, `/p2-market-validation`, `/p2-assumptions`, `/p2-regulatory-check`) and any spike with a ❌ outcome. Especially relevant when the spike exposes a **mechanism gap** (API wall, dead library, backend migration, ToS change) rather than just "this one assumption is wrong".

---

### G-069: Ignore the TaskCreate reminder in a linear skill flow
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: Ignore system `TaskCreate` reminders during linear skill sequences (Read → Edit → Commit → index-update without concurrency or parallel streams). Tasks only pay off for multi-stream workflows (3+ agents in parallel, or substantial multi-tranche apply sequences with ≥4 phases that have verification steps between them).
>
> **Why**: The system reminders are prophylactic, not problem-driven — they fire every few minutes of activity regardless of the workflow. For a linear skill script the path is clear (read context → delegate → apply → update indices → commit) and TaskCreate adds only setup overhead with no tracking benefit. Per reminder ignored: ~0 cost. Per reminder followed in a linear flow: ~30-60s of TaskCreate setup + TaskUpdate micromanagement = token burn with no benefit.
>
> **How to apply**:
> 1. On a "task tools haven't been used" reminder, check: is the current workflow linear (one skill, clear sequence) or multi-stream (parallel agents, several apply tranches with verification, long research sequences)?
> 2. Linear → ignore, continue.
> 3. Multi-stream → create tasks (useful for tranche tracking + user visibility).
> 4. **Threshold heuristic**: ≥3 tranches with different file sets + verification steps between them justify tasks. A sub-3-tranche linear flow does not.
>
> **Anti-pattern**: reflexively calling TaskCreate on every system reminder → produces a task list that needs more upkeep than the actual workflow; tasks go stale before they complete.
>
> **Related**: G-016 above (session length) — orthogonal. G-024 in `agents.md` (consolidate multi-pass sequence) — analogous for multi-stream briefs.

---

### G-056: On a requirement change, reconcile dependent stories' ACs immediately
**Confidence: 0.4** | Last confirmed: 04.06.2026

> **Rule**: When a requirement changes mid-project, immediately reconcile (or explicitly flag as stale) the acceptance criteria of all dependent / downstream stories — do not leave them to be re-discovered story-by-story at each story's start.
>
> **Why**: A mid-project change ripples through the backlog, but the dependent stories' ACs were written against the old assumption and look fine until you open them. In a productdata Sprint-2 session a login-model rework (Variante C) silently invalidated the ACs of three downstream stories (S05/S06/S07); each was only caught at its own start, forcing a stop-and-reshape conversation mid-build every time. Reconciling once, at the moment of the change, replaces three context-switches with one and prevents building against a stale AC before the mismatch is noticed.
>
> **How to apply**:
> 1. When a decision/ADR changes a foundational assumption, list the stories that depend on it (same epic + anything referencing the changed mechanism).
> 2. For each, scan its ACs against the new reality; mark the stale ones inline (`AC reshaped post-<change>: …`) or add a one-line deviation note — even if you won't build them yet.
> 3. Surface the deviations to the PO in one batch, not one-by-one at each story start.
>
> **Related**: G-015 (document PO decisions immediately) — the AC reconciliation IS part of capturing the decision's blast radius; PI-003 (stale comments after a decision — grep the rejected term) — the same "decision invalidates downstream artefacts" pattern, at code-comment level.
