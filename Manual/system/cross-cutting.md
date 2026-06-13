---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: cross-cutting-mechanisms
last_updated: 15.05.2026
---

# Cross-Cutting Mechanisms

## Constitution (`docs/CONSTITUTION.md`)

Mandatory artifact for every Full-Track project — the project's "constitution"
with three sections that gates load as binding input:

- **Inviolable** (non-negotiable): DSGVO, BFSG/A11y baseline, sectoral compliance, architectural leitplanken from "inviolable" ADRs
- **Default** (deviate with justification): tech stack, TDD discipline, language, platform targets, monetization pattern
- **Aspirational** (goals, measured): test coverage threshold, performance budget, A11y-audit quality, user-research minimum

**Creation** via `/constitution` in three modes:
- **Greenfield**: 5 domain bootstraps available (`saas-b2c`, `mobile-b2c`, `b2b-tool`, `b2c-marketplace`, `on-device-privacy`)
- **Lean-Vorlauf**: reads Constitution-Light from `docs/FRAME.md` Section 6
- **Existing Full-Track**: drafts from existing phase docs (ADRs, REGULATORY.md, A11Y.md, SECURITY.md, NFR.md)

**Versioning**: Semver-light. MINOR-bump for Default/Aspirational changes, MAJOR-bump for Inviolable changes (requires ADR).

**Gate integration**: `gate-preflight.py` extracts the Inviolable section into `docs/.gate-preflight-pX.md`. All 8 gate commands (P0-P7) load it as mandatory pre-gate input. Inviolable violations are flagged as **"Inviolable breach"** = No-Go signal in the verdict.

**CCPR itself** is bound by its own constitution at `docs/CONSTITUTION.md` (v1.0, 15.05.2026) — same discipline applied to the worker repo.

## Cross-Check (`/cross-check`)

Optional pre-gate consistency check across phases. 7 initial rules:

| # | Rule |
|---|---|
| R1 | FEATURES.md <-> AUTH.md (each user-facing feature has an auth flow) |
| R2 | TECH_STACK.md <-> DATA_MODEL.md (DB choice consistent with schema syntax) |
| R3 | THREATS.md <-> AUTH/SECURITY (each threat has a mitigation) |
| R4 | NFR.md <-> TESTSTRATEGY.md (each NFR has a test approach) |
| R5 | ADR-status <-> Components (rejected ADRs not actively referenced) |
| R6 | CONSTITUTION Inviolable <-> ADRs/Implementation (no ADR violates Inviolables) |
| R7 | STORY_INDEX <-> Epic-Detail-Files (bidirectional story-epic consistency) |

**Output**: `docs/.cross-check-report.md` (volatile, regenerated per run).
**Recommendation, not mandatory** — gates list `/cross-check` as a suggested pre-step. Iterative rule expansion expected.

## Handover (HANDOVER.md)

Preserves work state across session transitions. Located in `docs/HANDOVER.md` in the project directory.

**Session Start:**
1. Check if `docs/HANDOVER.md` exists
2. If yes: read it and continue work

**Session End / Before Compact:**
- Update HANDOVER.md with current work state
- Template: `~/.claude/templates/HANDOVER_TEMPLATE.md`

**Strategic Compact:**
1. At 100 tool calls: Compact reminder (via agent-monitor)
2. At 150 tool calls: Urgent HANDOVER warning
3. **Before** /compact: Update HANDOVER.md
4. **After** /compact: Read HANDOVER.md to restore context

## Wingman Consolidation

See [agents.md](agents.md) → Wingman Workflow.

Commands that use the wingman: `/konzept`, `/p1-features`, `/gate-p1`, `/p3-architecture`, `/gate-p3`, `/p5-review` and other commands with parallel agents.

## Token Optimization

Multiple mechanisms work together:

| Mechanism | Token Savings | How |
|---|---|---|
| Wingman consolidation | ~1000+ per agent run | Summary instead of full results in context |
| Local scripts | variable | Mechanical checks outside of Claude |
| Ollama delegation | ~500-1000 per call | Summaries, HANDOVER drafts locally |
| Strategic compact | significant | Context compression on long sessions |
| Agent brief summaries | ~500 per agent | Agents return max. 5 sentences |
