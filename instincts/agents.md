---
name: instincts-agents
description: Global instincts for agent orchestration, briefing discipline, parallel/sequential agent shapes, and wingman consolidation. Loaded as Tier-1-global topic file alongside the slim index in `~/.claude/instincts.md`. Curated starter examples — adapt and extend through your own `/postmortem` runs.
type: instincts
scope: tier-1-global-topic
last_updated: 01.06.2026
---

# Agent Orchestration Instincts

Behavioural rules for briefing, parallelism, wingman consolidation and read discipline when delegating to subagents. Sorted by confidence (descending). Maintain by running `/postmortem` at the end of each session.

---

### G-008: Wingman required after parallel agents
**Confidence: 0.9** | Last confirmed: starter set

> **Rule**: After every parallel-agent run with ≥2 agents, invoke the `wingman` agent for consolidation instead of reading all output files yourself.
>
> **Why**: Wingman summarises detail outputs in max. 15 sentences; the orchestrator saves tokens and keeps an overview. Direct full-text reads cost 2–3k tokens per agent output.
>
> **How to apply**:
> - Agents write their full outputs into files (`docs/...`), return only a brief summary (max. 5 sentences) to the orchestrator
> - Wingman receives the file paths, consolidates them into a cross-file verdict
> - The orchestrator processes only the wingman output, samples agent files only when needed
>
> **Wingman sub-rule**: the `wingman` agent has **no Write tool by definition** (only Read, Grep, Glob). For consolidation jobs like "write to `docs/reviews/SPRINT-X-CONSOLIDATED.md`", it returns the full markdown content in its output and the orchestrator must write the file. Brief wingman explicitly: "return the full markdown content in your output, I will write the file".

---

### G-009: Agent prompts always specify exact file paths
**Confidence: 0.9** | Last confirmed: starter set

> **Rule**: When briefing an agent, list all relevant paths as **absolute paths** explicitly — not "read the sprint files" but "read `docs/planning/SPRINT.md`, `docs/planning/BACKLOG.md`, …".
>
> **Why**: Agents otherwise guess paths — typical errors: wrong sub-folder (`Plants/` instead of `PlantList/`), wrong spelling, forgotten sub-index files. Leads to file-not-found errors or incomplete outputs.
>
> **How to apply**:
> - Before invoking an agent: verify relevant paths via `Glob` / `ls`
> - In the brief: complete path list, including "optional" files
> - For sub-index architectures (P3-security, P3-UX, P3-infra): name all detail files explicitly
>
> **Folder-disambiguation sub-rule**: when a path could semantically be either a file or a folder (e.g. `tests/Photos`, `docs/quality/reviews`, freshly-created sprint subfolders), mark it explicitly as "folder" or "file" in the brief, or hand over a concrete file list instead of a folder anchor. Anti-pattern: "read `docs/quality/reviews/sprint-06-final/`" → the agent tries to read the folder as a file → EISDIR.

---

### G-025: Minimise read-heavy pre-briefing when the agent reads on its own
**Confidence: 0.9** | Last confirmed: starter set

> **Rule**: Before delegating to an agent, only sample-read files for briefing context — do not exhaustively pre-read everything the agent will read itself. A pointer + 1–2 sample files is enough; the agent reads the rest within its own token budget.
>
> **Why**: Empirically, in typical skill sessions (P3/P4/P5/P6) the `Read` tool share lies between 44 % and 54 % of orchestrator tool calls. Deviations >60 % indicate orchestrator full-text reads of files that the agent will read again — pure token waste.
>
> **How to apply**:
> - When the agent brief contains "read X, Y, Z", the orchestrator only needs 1–2 files for brief comprehension (typically the phase-index file + one sample detail file)
> - At session end: check `session-summary.json`, compute `by_tool.Read / total_tool_calls`
> - If read share >60 %: check whether G-017 violations (full-text reads of large files) happened
> - Anti-pattern: read 8 backlog files before the brief, then 4 more files in the verification phase, plus the agent reads all 8 + architecture files again itself

---

### G-007: Max 3 parallel agents
**Confidence: 0.8** | Last confirmed: starter set

> **Rule**: Maximum 3 sub-agents in parallel per skill run. For larger workloads, use sequential waves with wingman consolidation between waves.
>
> **Why**: Beyond 3 parallel agents, wingman consolidation becomes unwieldy, per-agent token budget drops below the quality threshold, and race conditions on file writes become possible.
>
> **How to apply**:
> - Max 3 parallel explore/review/audit agents per skill
> - Plan-Mode phase 1 (explore) has a hard cap of 3
> - On larger workloads: sequential waves (e.g. P3 architecture: components + tech-stack + ADR in parallel, then NFR sequentially)

---

### G-024: Consolidate the multi-pass sequence in the first briefing
**Confidence: 0.8** | Last confirmed: starter set

> **Rule**: When several passes of the same agent type are foreseeable for one user intention (main task → tech validation → corrections → follow-up pass), plan the validation and the foreseeable follow-up passes **before the first brief**. Clarify stakeholder questions that change scope before the first agent run — don't steer corrections in after the first pass.
>
> **Why**: Anti-pattern: wave 3 (16 min) → senior-dev validation (3 min) → correction pass (5 min) → follow-up pass (4 min). The last two passes would have folded into the first pass given a forward-looking stakeholder check. `DuplicateBatchWarning` (the same agent type restarted within the session) is a late warning, not the ideal trigger.
>
> **How to apply**: Before the first brief, invest 30 seconds in "which stakeholder decisions can the agent NOT make on its own?" — clarify that list with `AskUserQuestion` before the brief.
>
> **TDD-phase sub-rule**: `DuplicateBatchWarning` for senior-developer in `/p5-implement` is **expected** and **not** a consolidation trigger when each batch represents a distinct TDD phase (RED → GREEN → REFACTOR — separated by time gaps + a thematic jump + its own conventional commit). The anti-pattern remains: unplanned correction iterations over the same artefact area.
>
> **Multi-tranche-review sub-rule**: `DuplicateBatchWarning` for identical reviewer sets (e.g. `code-reviewer` + `security-master`) across multi-tranche review skills (e.g. `/p5-review` with 4 tranches) is **expected** — each tranche writes its own findings files (output instead of commit as the phase boundary).
>
> **Related**: G-009 (exact paths), G-057 (lint constraints in the brief) — all briefing-completeness rules.

---

### G-032: Verify optional memory / instinct paths beforehand
**Confidence: 0.8** | Last confirmed: starter set

> **Rule**: Before giving a subagent a brief that references memory or instinct files (Tier-1 `docs/memory/MEMORY.md`, Tier-2 `docs/memory/{agent}/MEMORY.md` / `instincts.md`, `docs/instincts.md`), verify orchestrator-side via `ls` or `Glob` which of these files exist. Pass **only the existing paths** by name in the brief. Avoid "read X if it exists" clauses.
>
> **Why**: "If it exists"-worded agent briefs produce repeated ToolFailures on non-existent `docs/instincts.md`, `docs/memory/{agent}/instincts.md` etc. — error-log noise, wasted subagent tool calls, and an avoidable stagnation signal. The failure pattern is cross-persona stable (same on senior-developer, tech-writer, code-reviewer, security-master briefs).
>
> **How to apply**: One orchestrator check before the agent call: `ls docs/memory/{agent}/ 2>/dev/null` plus `ls docs/instincts.md 2>/dev/null`. Then brief e.g. "read `docs/memory/code-reviewer/MEMORY.md` (exists) and `docs/memory/MEMORY.md` (exists). The Tier-2 instincts.md does not exist yet — pass nothing for it." The swap costs 1 `ls` call and saves 1–2 agent fails.
>
> **Related**: G-030 (verified filename before read) and G-040 (verify user claims before destructive action) in their respective files — same verify-first philosophy.

---

### G-002: Review / consolidation agents — write boundaries
**Confidence: 0.7** | Last confirmed: starter set

> **Rule**: Read-analysis agents (security-master, code-reviewer) and the `wingman` have (or appear to have) Write tools but should return findings/report content as **text output** — the orchestrator writes the report files. Phrase prompts as "Analyze and return findings as structured text" / "return the full markdown content in your output" instead of "write to file".
>
> **Why**: Two complementary failure modes exist: (a) some review agents fail when creating new files / directories; (b) the `wingman` agent has **no Write tool by definition** (Read/Grep/Glob only), so on a "write to `docs/reviews/...CONSOLIDATED.md`" job it returns the full file content in its output and the orchestrator must write it. Briefing for output-as-text makes the pattern explicit and saves a tool-search iteration.
>
> **Note**: The opposite problem also exists — subagents that ignore explicit briefing prohibitions and write **too many** files. See G-033 for the ALLOWED-OUTPUTS boundary.

---

### G-019: Multi-agent skills via temp-files (extends G-008; parallel + sequential)
**Confidence: 0.7** | Last confirmed: starter set

> **Rule**: For skills with 2+ agents (Lead+Support, peer, or multi-wave): instruct each agent in the prompt to write its full output DIRECTLY to `/tmp/{prefix}-{agent}.md` via the Write tool, and reply in chat with only a 50–100-word confirmation.
>
> **Two valid orchestration shapes**:
> - **(a) Parallel** (independent agents) → start wingman with all file paths as input; wingman returns a ~1000-word consolidated summary in chat.
> - **(b) Sequential** (wave N needs wave N-1 findings as input) → orchestrator consolidates manually after the last wave by reading the `/tmp/`-files; no wingman needed if outputs are bounded (~30-40 KB total). The trade-off is conscious — pick sequential when data-flow quality matters more than parallel speed.
>
> **Token saving**: ~70-80 % of orchestrator context vs full-text agent chat output (parallel); ~50-70 % (sequential, because the orchestrator reads the `/tmp/`-files at the end).
>
> **Cleanup**: `rm -f /tmp/{prefix}-*.md` after writing the final concept doc.
>
> **Context**: Multi-agent /p1-* /p2-* /p3-* /p6-* skills with Lead+Support or multi-wave, especially when agent outputs are 5+ KB each.

---

### G-033: Subagent briefing with an explicit output boundary
**Confidence: 0.7** | Last confirmed: starter set

> **Rule**: For subagent briefs with Write permission (code-reviewer, security-master, tech-writer, senior-developer, debugger, qa-tester), the brief must **explicitly bound** which files the agent may write. Phrase: "Write ONLY to `<path>`. Do NOT touch HANDOVER.md, SPRINT.md, BACKLOG.md, RISKS.md or any other file."
>
> **Why**: Trigger case: a `security-master` proactively edited `docs/HANDOVER.md` before wingman consolidation, although the brief only named `docs/.review-security-sprint-02.md` as output. The agent interpreted "output" as "primary output file" and "helpfully" added to HANDOVER. Reverting was blocked by the auto-mode classifier as destructive; the sequence became messy and the work doubled. No data loss, but avoidable.
>
> **How to apply**: Standard block at the end of every Write-capable subagent brief:
> ```
> ALLOWED OUTPUTS: Write only to <explicit-path>.
> DO NOT modify HANDOVER.md, SPRINT.md, BACKLOG.md, RISKS.md, or any
> other shared planning file. The orchestrator will consolidate after you finish.
> ```
> For read-only agents (Explore, code-reviewer without Write tools) the block is omitted.
>
> **Sub-rule (Tier-2 persona-silo exception)**: Tier-2 persona-silo files (`docs/memory/{agent}/MEMORY.md`, `instincts.md`, `{topic}.md`) are **explicitly exempt** from the ALLOWED-OUTPUTS block — subagents may bootstrap or update their own silo on their own initiative. This drift is expected and not a boundary violation. After the run, do a `git status` check: verify Tier-2 memory modifications under `docs/memory/{agent}/*` (sensible/safe?), commit them, do NOT revert. G-033 stays active for **foreign orchestrator-state files** (HANDOVER, SPRINT, BACKLOG, RISKS, code/tests/docs outside the primary output paths).

---

### G-014: Delegate bulk file operations
**Confidence: 0.5** | Last confirmed: starter set

> **Rule**: With ≥5 files needing the same operation (frontmatter updates, status changes, index entries, translation sweeps) → delegate to an agent instead of doing it yourself in the orchestrator.
>
> **Why**: Orchestrator tokens are expensive for mechanical bulk ops. Agents have a dedicated token budget + tool specialisation.
>
> **How to apply**:
> - Bulk indicator: ≥5 files with an identical pattern
> - Agent choice depending on operation (project-planner for backlog, system-architekt for ADRs, tech-writer for doc sweeps)
> - Pattern is also applicable sequentially — what matters is the bulk nature, not parallelism
> - Related: G-052 in `shell-git.md` covers the tranche-disciplined self-execution variant of the same pattern

---

### G-045: AskUserQuestion with preview boxes on worker-output divergence
**Confidence: 0.5** | Last confirmed: starter set

> **Rule**: When 2+ worker outputs diverge at user-relevant points (scope variant, trade-off, slot count), present the user 2–3 concrete options via `AskUserQuestion` with `preview` boxes (e.g. SP balance, trade-off rows). Do not silently fall back to the lead-worker default.
>
> **Why**: In a `/p4-sprint` case, the project-planner recommended sprint variant V1 (16 SP) while the senior-developer favoured a tech-coherent V1 variant (17 SP). Instead of taking the planner default, an `AskUserQuestion` with 3 preview boxes (V1 / V1-Tech / Minimal) let the user pick V1-Tech — a materially different sprint plan than the orchestrator would have chosen alone.
>
> **How to apply**:
> 1. After parallel worker consolidation: identify user-relevant divergence points (not pure tech details — those the orchestrator can decide).
> 2. Structure the options with `preview` boxes showing the concrete SP balance / trade-off table / consequence.
> 3. Still mark a pre-recommendation in the question text (e.g. "V1-Tech (Recommended)"), but present the options as visually equal.
>
> **Related**: G-008 (wingman), G-019 (temp-file output separation as a precondition for divergence identification), G-042 (skipping wingman makes divergence identification an explicit orchestrator task).

---

### G-010: Do not read agent outputs yourself
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: After a parallel agent run, do NOT read/process the result files yourself — delegate directly to the wingman. Reading yourself + wingman = double token consumption. Use the wingman summary as the sole basis for user presentation.
>
> **Why**: Reading 3 agent results manually and then running the wingman anyway doubles the cost. The pattern is most often violated by reading a single tempting large output (e.g. a financial plan) in full instead of letting the wingman consolidate it.
>
> **Context**: /p6-pentest, /p6-audit, /p5-review parallel runs. Complements G-008 (wingman after parallel agents).

---

### G-029: Re-review loop for HIGH/CRITICAL findings before /p5-bugfix
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: Before `/p5-bugfix` for HIGH/CRITICAL findings, run a compact verification loop by default: a `/p5-review-code` pass on only the affected files + the findings list as explicit input ("verification review of the N original HIGH findings"). Empirical expectation: 30–60 % of HIGH/CRITICAL findings get identified as false-positive or downgraded to MEDIUM/NOTE.
>
> **Why**: Lower-tier reviewer models (often used in `/p5-review-code` / `/p5-review-security`) tend to escalate severity on suspected pattern violations without reading the affected domain type definitions. Classic anti-pattern: "the mapper needs a `.rawValue` conversion because other mappers do" — without checking whether the domain field is even an enum (it may be a String by design).
>
> **How to apply**:
> 1. After `/p5-review` consolidation (wingman output) and before `/p5-bugfix`: call a re-review subagent (same model class) with a clear verification job.
> 2. Input: bullet points with File:Line + severity + original recommendation. Job: "per finding: existence, severity plausibility, fix-recommendation correctness, plus other spots in the same file. Plus 5–10 additional missed findings in the same files."
> 3. Output file `docs/reviews/SPRINT-X-tranche-Y-code-recheck.md`.
> 4. On discrepancy with the first review: update HANDOVER + SPRINT.md + CONSOLIDATED.md with an erratum block; use the corrected bugfix list.
>
> **Evidence (illustrative)**: a tranche code-review flagged 6 HIGH mapper-layer findings (~2 h fix estimate); re-review identified 4 as false-positive (the domain fields were String by design, no enum existed). Real fix scope: 1 HIGH + 1 MEDIUM (~30 min). Bugfix effort cut ~75 %, 4 unnecessary refactors avoided.
>
> **Context**: Any `/p5-review*` output with HIGH/CRITICAL findings before `/p5-bugfix`. Especially valuable with lower-tier reviewer models (higher severity-escalation tendency).

---

### G-042: Skip the wingman step for structured 2-agent sequences
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: When a skill recommends wingman consolidation, but Lead+Support are only two agents AND both outputs are structurally clearly separated (headings, tables, own sections), consolidate yourself — saves 1 agent call.
>
> **Why**: For `/p1-features` (konzeptor lead + ux-designer support with table-structured corrections), self-consolidation into FEATURES.md was more token-efficient than a wingman hop. For `/p1-privacy` (security-master standalone, no support agent), the support step was explicitly skipped.
>
> **How to apply**:
> 1. Read the skill instruction: is there an explicit "wingman consolidation" phase?
> 2. 2 agents? Both outputs structured (tables + sections)? → wingman skip OK.
> 3. 3+ parallel agents OR unstructured outputs OR a content conflict between agents → keep the wingman.
> 4. On skip: briefly note in the doc body ("wingman step skipped, outputs structurally separated") for an audit trail.
>
> **Anti-pattern**: mechanically calling the wingman when the consolidation output would just concatenate the two agent outputs.

---

### G-057: Subagent briefs must list project lint constraints explicitly
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: Subagent briefs for code-output tasks (TDD RED/GREEN/REFACTOR, new modules, refactors) **must** list project-configured lint constraints as a concrete inline list — not as a blanket reference ("see the lint config") or generically ("mind the linter"). Copy the effectively-enforcing rules from `.swiftlint.yml` / `eslint.config.js` / `ruff.toml` — the frequently-hit ones, not all.
>
> **Why**: Subagents know the project CLAUDE.md only partially (a compact brief outweighs linked files). They apply default language idioms that collide with the project linter. Concrete example: a subagent generated `_`-suffixed fixture identifiers; the pre-commit hook `identifier_name` blocked → recovery via orchestrator rename + re-commit. A one-line brief clause ("naming: no underscore in identifier suffixes — use camelCase or file-scope-private on conflict") would have avoided it.
>
> **How to apply**:
> 1. Before each code-output subagent brief: insert a "pre-commit-hook awareness" block with the concrete lint list (project-specific — e.g. line-length, `type_body_length`, `identifier_name`, `force_unwrapping` for Swift; `max-lines` for ESLint; strict-mode for Ruff).
> 2. On a recurring violation of a specific rule across sessions → a Tier-2 memory entry in the relevant subagent persona (`docs/memory/senior-developer/instincts.md`) instead of repeating it inline.
> 3. **Skip path**: wingman / code-reviewer / qa-tester / security-master (read-only output, no code) — no lint constraints needed in the brief.
>
> **Related**: G-009 (exact paths), G-024 (briefing completeness), G-033 (explicit output boundary), G-064 (DO-NOT-commit clause).

---

### G-064: Subagent briefs must include "DO NOT commit" when the orchestrator drives the commit flow
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: When the orchestrator drives the commit flow itself (test:/feat:/refactor: split, pre-commit-hook recovery, multi-stage staging), **every agent brief MUST include an explicit clause** `**Do NOT commit** — orchestrator handles commit`. Otherwise agents commit on their own initiative when changes look "complete" — typically after a clean test-only file add (RED phase) or after a successful green verify run.
>
> **Why**: Subagents follow a default "task done → save state" heuristic; for code-output tasks a git commit looks like the natural finish. When the orchestrator instead wants to orchestrate multi-commit splits (separate test:, feat:, refactor: commits per TDD convention), an unprompted agent commit breaks the flow — the orchestrator must then either accept the agent commit (breaking the convention) or revert + re-stage.
>
> **How to apply**:
> 1. **Default**: in every code/test/doc-producing agent brief, a constraints section with: `- **Do NOT commit** — orchestrator handles commit (stage changes via Write/Edit only).`
> 2. **Exception**: if the brief explicitly includes "run /commit when done", agent commit is expected — omit the clause.
> 3. **Recovery if the agent committed**: check message + content. Substantially correct → accept + adjust follow-up commits. Problematic → `git reset HEAD~` + re-brief.
>
> **Related**: G-057 (lint constraints), G-009 (exact paths), G-033 (output boundary) — sibling explicit-constraint rules.
>
> **Context**: Multi-cycle TDD skills (`/p5-impl-red` + `/p5-impl-green` + `/p5-impl-refactor`) where the orchestrator organises the per-phase commit split. Most common in RED phases (a clean test-only file → the agent sees "complete").

---

### G-070: Split implement-and-measure agents into two hand-offs
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: When an agent task combines building code **with** a real infra run / benchmark whose duration is unknown in advance, split it into **two hand-offs**: (a) build + smoke run on a small data slice → checkpoint report back to the orchestrator; (b) a separate full-run/measure task (via SendMessage to the same agent or a fresh brief). Do not brief it as one monolith "build and immediately measure at full load".
>
> **Why**: Trigger case (`/p2-poc`): a senior-developer ran ~155 minutes in one hand-off (schema + 6 packages + generator + 3M-record generation + 6 benchmark runs). Result: dozens of CompactUrgent events, massive context build-up, and **no interim checkpoint** to intervene or course-correct. The brief even said "validate 300k first, then scale to 3M" — but as one instruction, so the agent ran straight through without reporting the build state. A 2.5-hour monolith is hard to steer and blocks the session.
>
> **How to apply**:
> 1. Spot the measure/benchmark/load-test portion → plan it as its own hand-off.
> 2. Hand-off (a): "Build + run a smoke run on a small slice (e.g. 1–5 %), report build status + smoke numbers — do NOT run the full run."
> 3. Orchestrator checks the checkpoint (compiles? plausible smoke numbers?), corrects if needed, then commissions hand-off (b) full-run/measure.
> 4. Rule of thumb: expected agent runtime > ~30 min with an execution portion → split.
>
> **Related**: G-024 (briefing completeness — all instructions up front) — complementary; G-070 adds the run-checkpoint dimension for long-running measure tasks. G-016 in `workflow.md` (session length) — run length as a steering quantity.
>
> **Context**: PoC / benchmark / load-test / data-generation tasks with real infra (DB, Docker, large datasets). Not relevant for pure code/doc tasks without an execution portion.

---

### G-071: Mass doc-rebuild via parallel agents with an ID-integrity proof
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: For a mechanical mass doc-rebuild (split / move / merge across several large docs), brief the parallel agents (max 3–4 per wave, G-007) with three mandatory elements:
> (a) an **explicit VERBATIM clause** — move content word-for-word, no paraphrasing / shortening / summarising / adding;
> (b) an **ID-marker count, original vs new, as an integrity gate IN the agent output** — the agent itself reports the count of stable markers (feature IDs, RISK IDs, table rows, …) in the original vs the sum across the produced files; both must match;
> (c) an **independent orchestrator cross-check BEFORE commit** — marker count against `git show HEAD:<file>`, plus lint (phase-docs-lint) and link resolution (all sub-index links exist).
>
> **Why**: Agents tend to paraphrase/shorten content on "rebuild" tasks instead of moving it verbatim — silent content loss in validated docs. The ID-marker count makes loss measurable rather than trust-based. Evidence: 6 oversized docs split in 2 waves of 3 agents each (index + detail files); integrity confirmed (every ID class original = sum-of-new), 0 loss, lint 0/0/0, doc-volume critical/warning reduced to 0/0.
>
> **How to apply**:
> 1. One agent per doc; waves of max 3–4; cross-check after each wave, then the next.
> 2. Pick the most stable marker type per doc (unique IDs > table rows > headings).
> 3. The sub-index keeps the original filename (skill/link compatibility); detail files carry `parent_index` in the same folder.
>
> **Related**: G-018 in `files.md` (grep-then-edit + boundary-violation sub-rule — `git status` after each run), G-033 (output boundary) + G-064 (DO-NOT-commit clause), G-050 in `workflow.md` (doc coverage via glob list).
>
> **Context**: Doc-splitting (index + detail files), mass doc refactor, bulk renames with content moves. Not relevant for single small edits.
