---
name: instincts-files
description: Global instincts for Read/Edit discipline, large-file handling, grep-then-edit recovery and path verification before file access. Loaded as Tier-1-global topic file alongside the slim index in `~/.claude/instincts.md`. Curated starter examples — adapt and extend through your own `/postmortem` runs.
type: instincts
scope: tier-1-global-topic
last_updated: 01.06.2026
---

# File Tooling Instincts

Behavioural rules for reading and editing files safely: avoid token-overflow on large files, recover from `Edit String not found`, and verify paths before reading. Sorted by confidence (descending).

---

### G-017: Large files require offset/limit on Read
**Confidence: 0.9** | Last confirmed: starter set

> **Rule**: Never read files >25k tokens (≈ >20 KB of markdown) as full text — always `Read` with `offset` and `limit`, or use selective `grep -n` for specific anchors first.
>
> **Why**: The tool hard limit is 25k tokens per read. Files like `USER_JOURNEYS.md` (~27k), `ASSUMPTIONS.md` (~30k), `INTERVIEWS.md` (~31k) are typical candidates in P1/P2. `~/.claude/instincts.md` itself can grow into this range during long-running sessions. Full-text reads fail with `File content (XXk tokens) exceeds maximum allowed tokens (25000)`.
>
> **How to apply**:
> - **Before the first read** of an unknown-size file: `wc -l <file>` and `ls -la <file>` for a size estimate
> - At >15 KB, work pre-emptively with `offset` / `limit`
> - **Intra-session sub-rule**: if a file has already failed a read in the session, every subsequent read of the same file must use offset/limit (no repeating the error — the loop-detector logs the repeat)
>
> **HANDOVER.md special case**: `docs/HANDOVER.md` is the project handover snapshot that grows across skill changes. Read it pre-emptively with `head -20` or `Read offset:1 limit:30` instead of full-text, especially at session start.
>
> **Phase-3 detail-files sub-rule**: `docs/architecture/DATA_MODEL.md`, `COMPONENTS.md`, `ARCHITECTURE.md` and similar files grow with every skill. Before reading them in P5+: first `grep -n '^## '` for a section map, then targeted section reads.
>
> **Subagent-briefing sub-rule**: When briefing a subagent to read a known-growing file (HANDOVER, ACCEPTANCE_*, sprint reports), pass an offset/limit hint or a concrete section anchor in the brief — subagents do not internalise G-017 automatically and attempt full reads by default.

---

### G-018: Edit "String not found" → grep-then-edit recovery
**Confidence: 0.9** | Last confirmed: starter set

> **Rule**: After "Edit String to replace not found" or "File has been modified since read": do NOT guess the string again. Run `grep -n` with a unique anchor (a stable substring of the line), copy the EXACT text from the grep output as `old_string`, retry Edit.
>
> **Common causes**:
> 1. Dates / dynamic content in headers shifted between read and edit.
> 2. Subagents (business-analyst, konzeptor, system-architekt, security-master) wrote to shared files (HANDOVER.md, MEMORY.md, ARCHITECTURE.md, Tier-2 memory) without or against the orchestrator's instruction.
> 3. External tools modified the file (Xcode rewriting `.xcodeproj/project.pbxproj`, formatters running on save).
>
> **Sub-rule for subagent-shared files**: After every subagent run that may have touched HANDOVER.md / MEMORY.md / ARCHITECTURE.md / Tier-2 memory, re-read the file before further Edits.
>
> **Sub-rule for boundary-violations**: Subagents regularly ignore explicit briefing prohibitions ("do NOT update X"). Pure prohibitions are not enough. After every subagent run, actively run `git status --short` to see which files actually changed before making further edits. On unwanted changes either revert or accept — but decide consciously, not implicitly.
>
> **Sub-rule for proactive-writes**: Subagents also write output files **without an explicit write instruction** when their brief implies a verdict/detail file (e.g. "evaluate 7 criteria + return structured markdown" + a brief that references a file path). Before every orchestrator-write on a path that could correspond to a subagent output, briefly run `ls -la <path>` or `git status --short`. Highest-risk subagent classes: project-planner (gate files), system-architekt (ADRs, detail architecture files), security-master (threat models), tech-writer (doc files).

---

### G-030: Orchestrator reads with a verified filename via `ls` / `Glob`
**Confidence: 0.5** | Last confirmed: starter set

> **Rule**: Before the orchestrator (not an agent) reads a file whose name does NOT come from an explicit source (user message, recent Bash output, a known CLAUDE.md entry, or a just-read index file with a path link), first run `ls <dir>` or `Glob <pattern>` to get the exact filename. Logically "constructing" a filename from skill context reproducibly leads to read-fails + a re-read loop.
>
> **Anti-pattern**: You take a logical anchor from a subagent verdict ("RECHECK", "TRANCHE-B", "ACCEPTANCE") and construct a path like `docs/reviews/SPRINT-01-RECHECK.md`, without checking that the actual skill convention is `docs/reviews/SPRINT-01-tranche-b-code-recheck.md`. The constructed path is plausible but wrong.
>
> **Mitigation**: For reads into directories with skill naming conventions (`docs/reviews/SPRINT-*`, `docs/quality/acceptance/ACCEPTANCE_*`, generated doc files): first `Glob "docs/reviews/SPRINT-01*"` or `ls docs/reviews/ | head`, then Read the found filename. Saves a read-fail + correction read.
>
> **Distinction from G-009** (agent-briefing paths): G-009 covers paths the orchestrator puts INTO an agent brief — mitigation = exact paths in the brief. G-030 covers paths the orchestrator uses to read itself — mitigation = `ls`/`Glob` before Read. Complementary.
>
> **Context**: Review directories, test-result files, acceptance files, handover archives, source files whose exact filename follows code conventions. Risk rises in multi-convention repos.

---

### G-051: Out-of-scope files — grep only, no Read
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: When a file is explicitly marked "do not touch" / out-of-scope in the current plan, do NOT attempt a verification Read — plain grep sweeps are enough for schema checks, character sweeps and final verification. A Read is only needed when the content is required for a decision or an edit.
>
> **Why**: A large out-of-scope file (e.g. an `instincts.md` >25k tokens) read for "schema verification" fails the token cap — when `grep '[äöüß]' <file>` would have delivered the identical information without a token-limit fail. This is a self-violation of G-017, but the deeper root cause is that the Read was not necessary at all.
>
> **How to apply**:
> 1. **Honor the out-of-scope tag**: if the plan says "X stays unchanged / out of scope" → never use X as a Read target for verification.
> 2. **Grep-first for sweep operations**: final verification of a mass-edit via `grep -rln 'pattern' .` — out-of-scope files may appear in the hits and are consciously ignored (explicit whitelist).
> 3. **Sub-rule to G-017**: if a file is >25 KB AND out-of-scope, a Read is almost always superfluous. Grep delivers what's needed.
>
> **Related**: G-017 (large files require offset/limit) — G-051 is the "skip-the-read-entirely" variant. G-030 (verified filename before read) — same "think before you read" discipline. G-050 in `workflow.md` — grep-based verification as the default.
