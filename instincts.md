---
name: instincts-index
description: Slim autoloaded entry point for the global Tier-1 instincts. Demo / starter snapshot shipped with CCPR — your personal `~/.claude/instincts.md` follows the same shape but holds your own session-derived entries. Full Rule / Why / How per theme live in `~/.claude/instincts/{theme}.md`; postmortem history in `~/.claude/instincts-archive/HISTORY.md`.
type: project
scope: tier-1-global-index
last_updated: 01.06.2026
---

# Global Instincts (Index)

Confidence-based rules from session experience (0.3–0.9). This file is the **slim entry point** autoloaded at session start. Full Rule + Why + How to apply per theme in `~/.claude/instincts/{theme}.md`. Full postmortem history + decay narratives in `~/.claude/instincts-archive/HISTORY.md`.

> **CCPR snapshot note**: this file ships as a curated starter set demonstrating the **Index + Topic + Archive** structure. Adopt it as your initial `~/.claude/instincts.md` (and its sibling files under `~/.claude/instincts/` + `~/.claude/instincts-archive/`), then let it mature via `/postmortem`. Personal session-specific entries stay in your local copy and are not pushed back to CCPR. See `templates/STARTER_INSTINCTS.md` for the same content as a single-file alternative if you prefer not to split.

Last updated: 01.06.2026 (snapshot refresh — 27 generalised instincts ported from productive multi-project sessions, raising the starter set from 18 to 45. Project names, session hashes and story IDs anonymised per Constitution Inviolable #2. Confidence values are suggestions — they mature through your own `/postmortem` runs. Platform-specific (Apple/Xcode) and CCPR-maintainer-only instincts are intentionally excluded — see the bottom section.)

- Previous: 19.05.2026 — initial CCPR snapshot of the split structure (Index + 5 Topic-Files + Archive), 18 curated instincts.

## Agent Orchestration → `instincts/agents.md`

18 instincts: subagent briefing, parallel/sequential shapes, wingman consolidation, read discipline, output boundaries, commit-flow boundaries, lint constraints, implement-and-measure split, mass-doc-rebuild integrity.

- G-008 [0.9] Wingman required after parallel agents
- G-009 [0.9] Agent prompts: always specify exact file paths (incl. folder-disambiguation sub-rule)
- G-025 [0.9] Minimise read-heavy pre-briefing when the agent reads on its own
- G-007 [0.8] Max 3 parallel agents
- G-024 [0.8] Consolidate the multi-pass sequence in the first briefing (incl. TDD + multi-tranche sub-rules)
- G-032 [0.8] Verify optional memory / instinct paths beforehand
- G-002 [0.7] Review / consolidation agents — write boundaries (incl. wingman sub-rule)
- G-019 [0.7] Multi-agent skills via temp-files (parallel + sequential)
- G-033 [0.7] Subagent briefing with an explicit output boundary
- G-014 [0.5] Delegate bulk file operations
- G-045 [0.5] AskUserQuestion with preview boxes on worker-output divergence
- G-010 [0.4] Do not read agent outputs yourself
- G-029 [0.4] Re-review loop for HIGH/CRITICAL findings before /p5-bugfix
- G-042 [0.4] Skip the wingman step for structured 2-agent sequences
- G-057 [0.4] Subagent briefs must list project lint constraints explicitly
- G-064 [0.4] Subagent briefs must include "DO NOT commit" when the orchestrator drives the commit flow
- G-070 [0.4] Split implement-and-measure agents into two hand-offs
- G-071 [0.4] Mass doc-rebuild via parallel agents with an ID-integrity proof

## File Tooling → `instincts/files.md`

4 instincts: large-file read discipline, grep-then-edit recovery, path verification, skip-the-read for out-of-scope files.

- G-017 [0.9] Large files require offset/limit on Read (incl. HANDOVER + phase-3 + subagent-briefing sub-rules)
- G-018 [0.9] Edit "String not found" → grep-then-edit (incl. subagent-shared + boundary + proactive-writes sub-rules)
- G-030 [0.5] Orchestrator reads with a verified filename via `ls` / `Glob`
- G-051 [0.4] Out-of-scope files — grep only, no Read

## Skill / Workflow / Sprint → `instincts/workflow.md`

15 instincts: PO decisions, session length, frontmatter-vs-schema, stagnation-warning filter, plan-mode triggers, gate hygiene, conditional-go tracking, doc-language default, skill outputs, doc coverage, PoC-verdict cascade, TaskCreate-reminder filter.

- G-015 [0.9] Document PO decisions immediately
- G-016 [0.9] End sessions after 2 sprints (incl. multi-skill + re-setup + bulk-curation sub-rules)
- G-044 [0.6] Verify skill-prescribed frontmatter against the project schema
- G-067 [0.6] StagnationWarning is a false-positive during long subagents OR user-decision waits
- G-035 [0.5] Clarify open decision points before ExitPlanMode
- G-036 [0.5] Pre-gate working-tree clean sweep
- G-043 [0.5] Track conditional-go conditions with persistent C-IDs
- G-068 [0.5] Skill output language defaults to chat language instead of the project doc convention
- G-049 [0.4] Volatile skill outputs need an immediate gitignore entry
- G-050 [0.4] Doc coverage via Glob list, not from memory
- G-037 [0.4] Plan-mode trigger for multi-wave sprints
- G-039 [0.4] Read skill preconditions before a plan-mode multi-skill sequence
- G-041 [0.4] Offer push points in long pipelines proactively
- G-065 [0.4] PoC-verdict cascade — after a ❌ spike, re-check other assumptions/features/ADRs
- G-069 [0.4] Ignore the TaskCreate reminder in a linear skill flow

## Shell / Git / Mass-Edit → `instincts/shell-git.md`

5 instincts: destructive-action verify, mass-substitution tool choice, tranche discipline, commit-scope form, skill-output commit type.

- G-040 [0.4] Verify user claims before destructive action
- G-048 [0.4] Mass substitution via find+xargs+perl
- G-052 [0.4] Multi-tranche pattern for mass-edit / translation / refactor sweeps
- G-053 [0.4] Conventional-commits scope takes no comma
- G-060 [0.4] Skill-output commits need a standard conventional-commit type

## External APIs / MCP / OS-Quirks → `instincts/external.md`

3 instincts: WebFetch fallback, macOS filename quirks, MCP-server registration order.

- G-020 [0.5] WebFetch bot-protection → Playwright-MCP fallback (incl. academic-paywall sub-rule)
- G-026 [0.5] Avoid `skill.md` / SKILL system filenames on macOS
- G-031 [0.4] `claude mcp add` — server name as first positional

## Decay policy

- Entries with **Confidence ≤ 0.4** are review candidates in the next `/postmortem`. Each topic file's `Last confirmed` line tracks the most recent confirmation date.
- Decay mechanics: 30 days without re-confirmation → −0.1; at Confidence ≤ 0.3 → deletion proposal.
- Bumps: +0.1 per new evidence event, cap at 0.9.
- Full decay history + verbose narratives go to `~/.claude/instincts-archive/HISTORY.md`.

## Hint for `/postmortem`

When adding a new instinct: pick the matching topic file, insert an H3 block there, then update **this index** with a one-liner bullet. For bumps: update only the topic file's `Last confirmed` line and the index confidence value — no fresh postmortem prose in the topic file. That goes to the `HISTORY.md` archive's Header-Snapshot section (newest block on top, the previous `Last updated:` shifts to `Previous:`).

## Intentionally NOT in this starter set

Some global instincts that exist in productive local `~/.claude/instincts.md` files are deliberately kept out of the CCPR snapshot, for three reasons:

**Personal-context (per-user memory / project-specific anti-patterns):**
- **G-005** (skill commits) — has a sub-rule "no Anthropic co-author trailer" rooted in a user-specific commit-message memory.
- **G-046** (project memory pre-default-action) — examples cite personal memory files.
- **G-047** (PII in HTTP calls) — generic in concept, but the trigger example is a personal email in the User-Agent.
- **G-054** (HANDOVER read-overflow pre-check) — emerged from a specific project's HANDOVER growth pattern; useful but project-shape-dependent.
- **G-055** (Bash CWD persistence) — same pattern as the broader CCPR-shipped guidance, but the concrete evidence is project-specific.

**Platform-specific (Apple / Xcode / SwiftPM — irrelevant to non-Apple stacks):**
- **G-056** (pre-commit hooks don't cover the real xcodebuild build), **G-058** (0.000-sec test-failure cluster = signal-trap crash, use xcresult), **G-059** (SourceKit editor index-lag — xcodebuild is ground-truth), **G-063** (XcodeBuildMCP `test_sim` rejects a domain sub-target test filter). Mint your own platform instincts if you work on Apple platforms.

**CCPR-maintainer-only (relevant only to whoever maintains this distribution repo):**
- **G-062** (release-cut hygiene: CHANGELOG rename + link targets + annotated tag). Lives in the maintainer's local instincts, not in the shipped snapshot.

If you encounter similar anti-patterns in your workflow, mint them as new instincts via `/postmortem` — they are not universal enough for a starter set, but they may well belong in your local index.
