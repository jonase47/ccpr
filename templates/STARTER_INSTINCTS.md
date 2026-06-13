---
name: CCPR Starter Instincts
description: Compact flat sampler of 13 high-value generic instincts from productive multi-project sessions. The COMPLETE shipped snapshot (45 instincts) lives in the split layout ~/Workspace/ccpr/{instincts.md, instincts/, instincts-archive/}. Use this flat file only if you want a small starter and prefer not to split; for the full set adopt the split layout.
status: starter-set
last_updated: 01.06.2026
---

# CCPR Starter Instincts (compact sampler)

**What this is:** A flat sampler of 13 high-value behavioural / workflow rules (instincts) that have proven themselves across multiple projects. They are generic enough to serve as an immediate starting point for any CCPR user.

**What this is NOT:** Not the full shipped snapshot. As of 01.06.2026, the **complete** CCPR instinct snapshot holds **45 instincts** and lives in the split layout (`instincts.md` + `instincts/{theme}.md` + `instincts-archive/HISTORY.md`). This single file intentionally stays a small, flat subset to keep the "no-split" path light. If you want everything, adopt the split layout.

**What this is NOT, part 2:** Not a complete substitute for your own session experience. Confidence values are **suggestions** — they should mature organically through your own `/postmortem` runs (confirmed +0.1 or decayed −0.1) until they fit your way of working.

## Two ways to adopt

Pick whichever layout fits your workflow:

- **Split structure (recommended — and the only path that ships the full 45-instinct set)**: the CCPR repo ships `instincts.md` (slim index) + `instincts/{theme}.md` (full Rule/Why/How) + `instincts-archive/HISTORY.md` modelling the layout. Copy them as-is to `~/.claude/` and let `/postmortem` extend them. Five themes: agents / files / workflow / shell-git / external.
- **Single-file alternative (this file)**: a flat list of 13 sampler instincts. Copy the contents into your `~/.claude/instincts.md`. Use this if you prefer not to split AND are happy with a reduced set. You can switch to the split layout later without losing anything.

## How to use

1. **Initial adoption:** copy this file OR the split-structure files into your `~/.claude/` layout (entries that fit your workflow, or all of them).
2. **Adjust the header:** in your `instincts.md`, set a `Last updated: <date> (starter set adopted from CCPR)` entry.
3. **Mature over time:** every instinct confirmed in `/postmortem` gets bumped by `+0.1` (max 0.9). On contradiction `−0.2` (min 0.3). After 30 days without confirmation: decay proposal.
4. **Add your own:** new sessions produce new instincts (G-051+, or agent-specific SD-XXX / PP-XXX / etc.).

## Confidence scale

| Value | Meaning |
|---|---|
| 0.3 | Decay threshold — lowest active confidence; further reduction triggers deletion |
| 0.4 | Initial — newly proposed, not yet confirmed |
| 0.5–0.7 | Maturing — confirmed across multiple sessions |
| 0.8 | Stabilised — pattern fully matured |
| 0.9 | Cap — highest confidence, no further increase |

## ID schema

- **G-XXX** — global (orchestrator-level, cross-project)
- **SD-XXX** — senior-developer (code implementation patterns)
- **PP-XXX** — project-planner (sprint / backlog patterns)
- **QA-XXX** — qa-tester (test strategy patterns)
- **CR-XXX** — code-reviewer
- **KZ-XXX** — konzeptor (product concept)
- **SM-XXX** — security-master
- etc. (see `~/.claude/agents/`)

---

## Global instincts (G-XXX) — starter set

### G-007: Max 3 parallel agents
**Confidence: 0.8** | Type: Generic

> **Rule**: maximum 3 sub-agents in parallel per skill run. For larger workloads, use sequential waves with wingman consolidation between waves.
>
> **Why**: beyond 3 parallel agents, wingman consolidation becomes unwieldy, per-agent token budget drops below the quality threshold, and race conditions on file writes become possible.
>
> **How to apply**:
> - Max 3 parallel explore/review/audit agents per skill
> - Plan-Mode phase 1 (explore) has a hard cap of 3
> - On larger workloads: sequential waves (e.g. P3 architecture: first components + tech-stack + ADR in parallel, then NFR sequentially)

### G-008: Wingman required after parallel agents
**Confidence: 0.9** | Type: Generic

> **Rule**: after every parallel-agent run with ≥2 agents, invoke the `wingman` agent for consolidation instead of reading all output files yourself.
>
> **Why**: wingman summarises detail outputs in max. 15 sentences; the orchestrator saves tokens and keeps an overview. Direct full-text reads cost 2–3k tokens per agent output.
>
> **How to apply**:
> - Agents write their full outputs into files (`docs/...`), return only a brief summary (max. 5 sentences) to the orchestrator
> - Wingman receives the file paths, consolidates them into a cross-file verdict
> - The orchestrator processes only the wingman output, samples agent files only when needed

### G-009: Agent prompts always specify exact file paths
**Confidence: 0.9** | Type: Generic

> **Rule**: when briefing an agent, list all relevant paths as **absolute paths** explicitly — not "read the sprint files" but "read `docs/planning/SPRINT.md`, `docs/planning/BACKLOG.md`, …".
>
> **Why**: agents otherwise guess paths — typical errors: wrong sub-folder (`Plants/` instead of `PlantList/`), wrong spelling, forgotten sub-index files. Leads to file-not-found errors or incomplete outputs.
>
> **How to apply**:
> - Before invoking an agent: verify relevant paths via `Glob` / `ls`
> - In the brief: complete path list, including "optional" files
> - For sub-index architectures (P3-security, P3-UX, P3-infra): name all detail files explicitly

### G-014: Delegate bulk file operations to parallel agents
**Confidence: 0.5** | Type: Generic

> **Rule**: with ≥5 files needing the same operation (frontmatter updates, status changes, index entries) → delegate to an agent instead of doing it yourself in the orchestrator.
>
> **Why**: orchestrator tokens are expensive for mechanical bulk ops. Agents have a dedicated token budget + tool specialisation.
>
> **How to apply**:
> - Bulk indicator: ≥5 files with identical pattern
> - Agent choice depending on operation (project-planner for backlog, system-architekt for ADRs, tech-writer for doc sweeps)
> - Pattern is also applicable sequentially — what matters is the bulk nature, not parallelism

### G-015: Document PO decisions immediately
**Confidence: 0.9** | Type: Generic

> **Rule**: persist stakeholder / product-owner decisions immediately in *all* affected files (key-decisions table in CLAUDE.md, BACKLOG.md, PROJECT_PLAN.md, RISKS.md, possibly sprint files).
>
> **Why**: decisions that live only in the chat get lost across session changes. "Implicitly documented in HANDOVER" is not enough — cross-reference in the domain files is mandatory.
>
> **How to apply**:
> - After every decision: identify affected files (at minimum the CLAUDE.md key-decisions table)
> - Persistence in **one** pass (not "I'll do it later" — that gets forgotten)
> - Date + phase + rationale in the table

### G-016: End sessions after 2 sprints (multi-skill hygiene)
**Confidence: 0.9** | Type: Generic

> **Rule**: limit sessions to max. 2 skill workflows or 1 sprint. At HighToolCount=200 or TokenBudgetWarning@150: close the session cleanly (commit + push + HANDOVER update), then `/compact` or a new session.
>
> **Why**: long sessions accumulate stagnation warnings, the token budget runs low, context drift makes later skills less accurate. Empirically: 4-skill sessions reach 200+ tool calls and reasoning quality drops.
>
> **How to apply**:
> - Watch the indicators: HighToolCount=200, TokenBudgetWarning, ≥100 stagnation warnings
> - Skill limit: max. 2 substantive skills (e.g. `/p5-implement` + `/p5-review`) or 1 large skill (`/p4-backlog`)
> - Sprint limit: 1 sprint close-out per session
> - Before a new session: commit HANDOVER.md, optionally `/compact`

### G-017: Large files require offset/limit on Read
**Confidence: 0.9** | Type: Generic

> **Rule**: never read files >25k tokens (≈ >20 KB of markdown) as full text — always `Read` with `offset` and `limit`, or selective `grep -n` for specific spots.
>
> **Why**: the tool hard limit is 25k tokens per read. Files like `USER_JOURNEYS.md` (27k), `ASSUMPTIONS.md` (30k), `INTERVIEWS.md` (31k) are typical candidates in P1/P2. Full-text reads fail with an error.
>
> **How to apply**:
> - **Before the first read**: `wc -l <file>` and `ls -la <file>` for a size estimate
> - At >15 KB, work pre-emptively with `offset` / `limit`
> - **Intra-session sub-rule**: if a file has already failed a read in the session, every subsequent read of the same file must use offset/limit (no repeating the error!)

### G-025: Read share in skill sessions
**Confidence: 0.9** | Type: Statistical / observational

> **Rule**: in typical skill sessions (P3-architecture, P4-backlog, P5-implement, P5-review, P6-audit) the `Read` tool share lies between **44 % and 54 %** of tool calls. Deviations >60 % indicate full-text reads of unchecked files; <30 % indicate too little context loading.
>
> **Why**: empirical pattern across 6+ skill families. Read is the dominant tool for context build-up — deviations are diagnostic.
>
> **How to apply**:
> - At session end: check `session-summary.json`, compute `by_tool.Read` / `total_tool_calls`
> - If read share >60 %: check whether G-017 violations (full-text reads of large files) happened
> - If <30 %: check whether reasoning relied on too little context (higher risk of hallucinations)

### G-030: Orchestrator reads with verified filename via ls / Glob
**Confidence: 0.7** | Type: Generic

> **Rule**: before the orchestrator (not an agent) reads a file via `Read`, verify the filename via `Glob` pattern or `ls` instead of guessing from memory.
>
> **Why**: guessed paths (pluralisation, sub-folder names, spelling variants) lead to file-not-found. Parallel to G-009 (agent-briefing paths), but for self-operation.
>
> **How to apply**:
> - Before every read on a path that isn't unambiguously known: `ls <parent-dir>/` or `find <root> -name "*<pattern>*"`
> - Also in Bash tool calls: `grep -l '<pattern>' <expected-files>` for verification
> - For phase sub-index architectures: read the phase index first, then pull concrete detail-file paths from it

### G-040: Verify user claims before destructive action
**Confidence: 0.4** | Type: Safety

> **Rule**: when the user claims "X is already gone / done / deleted" and a destructive action is supposed to follow (`git rm -r`, `force-push`, `reset --hard`, etc.): diagnose first (`ls`, `git status`, `git log --diff-filter=AD`), then execute.
>
> **Why**: user perception ≠ repo state. Concrete incidents: "PoC is gone locally" → actually 5 tracked files, 32 KB of code. Blind action would have caused code loss.
>
> **How to apply**:
> - Before destructive Bash calls, ALWAYS run 1 diagnostic call first
> - On a mismatch between user claim ↔ repo state: ask explicitly, don't "trust and execute"
> - Default action: never destructive without diagnosis, even when the user insists

### G-048: Mass substitution via find+xargs+perl instead of a bash for-loop
**Confidence: 0.4** | Type: Tool usage

> **Rule**: for mass substitutions across >5 files: `find <dirs> -type f \( -name "*.md" -o -name "*.py" \) -print0 | xargs -0 perl -i -pe '<single-line>'` instead of `for f in $(grep -rln ...); do perl -i -pe '<multi-line>' "$f"; done`.
>
> **Why**: multi-line perl in a bash for-loop isn't reliable (word splitting, multi-line quoting, "Can't open" / "File name too long" errors). find+xargs is robust against special characters and path variations.
>
> **How to apply**:
> - **>5 files = find+xargs**: `find ... -print0 | xargs -0 perl -i -pe 'SUBST1; SUBST2; ...'` (single-line, `;`-separated)
> - **<5 files = direct perl**: `perl -i -pe 'SUBST' file1 file2 file3` (multiple files as args)
> - **Never**: multi-line perl in a for-loop
> - **Verification required**: `grep -rln 'OLD_PATTERN' <dirs>` to confirm coverage

### G-049: Volatile skill outputs need an immediate gitignore entry
**Confidence: 0.4** | Type: Skill design

> **Rule**: when a skill writes generator output to `docs/.<name>-report.md`, `docs/.<name>-preflight-*.md`, or similar dotfiles, simultaneously produce a `.gitignore` pattern suggestion — either in the skill output or as a warning to the user.
>
> **Why**: pre-commit hooks in the project may accidentally stage volatile dotfiles. Retroactive `.gitignore` extension costs an extra commit. Known skills with volatile output: `gate-preflight`, `cross-check`, `quality-scan`, `bootstrap` (`docs/.session-context.md`).
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

### G-050: Doc coverage via Glob list, not from memory
**Confidence: 0.4** | Type: Workflow

> **Rule**: for cross-phase doc updates (a new feature that must be mentioned in several reference files): build a glob list of all relevant `~/.claude/docs/*.md` and `~/Workspace/<project>/docs/*.md` files, **check each one individually** (Read or grep), and only then confirm coverage.
>
> **Why**: cross-doc updates from memory typically forget 1–2 files. At 5+ files the forgetting probability rises to practically 100 %. Plus: within-file coverage (header + summary tables + TOC + body) is often incomplete — updates in one spot are not enough.
>
> **How to apply**:
> - **Before cross-doc updates**: `ls ~/.claude/docs/*.md` OR `find <docs-root> -name "*.md" -maxdepth 2` for a complete list
> - **Per file**: `grep -l '<feature-keyword>' <file>` AND `grep -n '<old-count>' <file>` — the latter finds stale counts / tables
> - **Within-file check**: check multiple spots (header, summary, TOC, body) — updates in one spot are not enough
> - **Rule of thumb**: at 5+ doc files, never work from memory

---

## What is intentionally NOT in the shipped snapshot

Some global instincts are deliberately kept out of the CCPR snapshot, for three reasons:

**Personal-context (per-user memory / project-specific anti-patterns):**
- **G-005** (skill commits) — sub-rule "no Anthropic co-author trailer" rooted in a user-specific commit-message memory
- **G-046** (project memory pre-default-action) — examples cite personal memory files
- **G-047** (PII in HTTP calls) — generic in concept, but the trigger example is a personal email in the User-Agent
- **G-054** (HANDOVER read-overflow pre-check), **G-055** (Bash CWD persistence) — project-shape-dependent evidence

**Platform-specific (Apple / Xcode / SwiftPM — irrelevant to non-Apple stacks):**
- **G-056**, **G-058**, **G-059**, **G-063** — xcodebuild / SourceKit / xcresult / XcodeBuildMCP quirks. Mint your own platform instincts if you work on Apple platforms.

**CCPR-maintainer-only (relevant only to whoever maintains this distribution repo):**
- **G-062** (release-cut hygiene). Lives in the maintainer's local instincts, not the shipped snapshot.

If you have similar anti-patterns in your workflow, you can mint them as new instincts via `/postmortem` — they aren't universal enough for a starter set.

---

## Agent-specific instincts (SD/PP/QA/CR/…) — not in the starter set

Persona-specific instincts (e.g. SD-005 RED-phase file git-stage discipline, PP-001 wave mechanics in sprint planning, QA-001 conditional-pass stories deferral slot) emerge organically in their respective agent domains. They belong in `docs/memory/{agent}/instincts.md` in the project repo, not in the global starter set.

---

## Maintenance & decay

- **`bash ~/.claude/scripts/instinct-check.sh`** checks age / count drift in the local `~/.claude/instincts.md`
- **`/instinct list`** shows all instincts; **`/instinct cleanup`** suggests decay
- On confirmation in `/postmortem`: +0.1 (max 0.9). On contradiction: −0.2 (min 0.3). After 30 days without confirmation: decay proposal (−0.1).
