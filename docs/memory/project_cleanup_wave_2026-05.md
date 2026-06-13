---
name: Cleanup wave 2026-05-15/16 — structural + conceptual repo hardening
description: Two-day cleanup session that closed 7 structural inconsistencies and 7 conceptual gaps, ratified CCPR's own constitution, introduced global Tier-2 memory, split three reference docs, and established SemVer + CHANGELOG. First tagged baseline v0.1.0.
type: project
last_updated: 16.05.2026 (Note: agent migration verified later same day)
status: active
related:
  - ../CONSTITUTION.md
  - ../adr/ADR-0001-versioning-and-distribution.md
  - ../../CHANGELOG.md
  - project_lean_track_v1.md
  - project_repo_conventions.md
---

Cleanup wave concluded **16.05.2026** with the v0.1.0 tag pushed. Branch range: `87f34ea..73ff91c` (12 commits). Triggered by a `claude` audit that surfaced 7 structural inconsistencies (agent count drift, command count drift, orphan templates, missing `local-llm/` directory referenced in 5 docs, etc.) and 7 conceptual gaps (Full→Lean dead-end, constitution scope, complexity dimensioning, versioning absence, memory tiebreaker drift, self-violating doc-volume thresholds, weak `researcher`-agent justification).

## What changed

- **researcher agent removed** along with `/research` skill — was an experiment; value better expressed as two instincts than a dedicated persona. Agent count 16 → 15, command count 115 → 114.
- **CCPR ratified its own `docs/CONSTITUTION.md` (v1.0)** with six Inviolables: no external services for distribution, no personal/tenant data in shipped artefacts, GDPR as default, English in code and shipped content, no breaking skill-interface changes without ADR + migration, no vendor lock-in.
- **Lean-Track marked transient** with explicit sunset criterion (CCPR v1.0). README + CLAUDE.md make clear that Lean is the fast-test shortcut and bridge into Full — not a peer track for mandant/team projects.
- **Memory model upgraded from 2-tier to 2×2** (tier × scope): added the previously missing global Tier-2 slot at `~/.claude/memory/{agent}/instincts.md`. ID scheme `XX-G-NNN`. 5 persona-specific Apple/iOS-tooling instincts migrated out of global Tier-1.
- **memory-lint.sh enforces** Tier-1-global soft/hard cap (50/100 KB), Tier-2-global schema check, skeleton-silo detection, decay tripwire.
- **Tiebreaker reversed**: old "When in doubt, prefer Tier 1 (visibility wins over isolation)" → new three-step decision order (named agent/file/skill → Tier 2; ≥2 domains → Tier 1; uncertain → start Tier 2, promote at 3rd cross-reference).
- **SYSTEM_OVERVIEW, SECTIONS_COMMANDS, PROJECT_PHASES split** into slim indexes + topic files. `doc-volume-check` now reports 0 warnings (was 3, all above 25 KB).
- **SemVer + CHANGELOG + ADR-0001** established. Initial tag v0.1.0 set retroactively over the wave; tag procedure documented.
- **Agent definitions migrated** to the new schema (15 files): `~/.claude/agents/*.md` first, then propagated to repo via search/replace to avoid local language drift bleeding into distribution.

## Key lessons (for future cleanup waves)

1. **CLAUDE.md schema changes do NOT automatically reach subagents.** Subagents load their own agent definition as primary context; the global CLAUDE.md only reaches the orchestrator. Any schema update must explicitly synchronise `agents/*.md`. Discovered when atime checks on the new global Tier-2 silos appeared unchanged after a 3h real-world project Sprint-5 wave — diagnosis was structurally correct, but the atime methodology turned out to be invalid (see lesson #2). The structural fix (propagating the migration into all 15 agent definitions) was still required.
2. **`atime` on APFS AND `file-history` are unreliable as "was-read" indicators.** macOS APFS effectively never updates atime on reads (verified by `cat`-ing a file twice with unchanged atime afterwards). `~/.claude/file-history/` only logs files that get edited/written, not pure reads of external files. Both indicators were misleading during the migration investigation — they suggested subagents had not loaded their global Tier-2 silos, when in fact they had (verified later via direct subagent question, see follow-up #1). **Do not use `stat -f "%Sa"` or file-history presence as proof of file access**. Reliable alternative: ask the subagent to reproduce the silo content (the verification method that finally worked).
3. **Redundant memory patterns hide broken synchronisation.** The subagent under test passed all SourceKit/FileProtection checks despite never loading its global Tier-2 silo — because the relevant patterns were redundantly present in the project Tier-2 silo (`<project>/docs/memory/senior-developer/swiftdata-tdd-patterns.md`). A fresh iOS project without that redundancy would have surfaced the gap immediately. **Implication**: when migrating memory patterns, also remove the project-Tier-2 copies (or accept the redundancy as a deliberate safety net).
4. **Distribution sync must be selective, not file-copy.** Local `~/.claude/` files carry language drift (e.g. `project-guide.md` is German locally, English in the repo) and personal customisations. Constitution Inviolable #2 ("no personal/tenant data in shipped artifacts") + #4 ("English in code and shipped content") would be violated by a naive `cp -r ~/.claude/agents/* ccpr/agents/`. The pattern that worked: a Python search/replace script that targets only the specific schema-migration string, leaving language drift in place.
5. **Self-violating tooling thresholds destroy credibility.** `doc-volume-check.sh` warned at 25 KB; the CCPR's own reference docs were 29 KB / 29 KB / 36 KB. The Split-Pattern that P3/P6 enforce for project phase docs had not been applied to the meta docs themselves. Fix: index + topic files under `docs/{system,commands,phases}/`. Same enforcement, same outcome.
6. **Constitution must apply to the worker repo, not only to downstream projects.** Before this wave, CCPR mandated a `CONSTITUTION.md` for every Full-Track project but had none itself. That asymmetry is gone; v1.0 of CCPR's constitution exists, and the gate-preflight machinery can now check it against the worker repo's own changes.

## How to apply

- Future schema changes to the memory or doc-splitting model **must** include an agent-definitions sweep in the same wave — preferably as a Python search/replace step in the same commit, not deferred.
- Use the structural pattern from this wave as a template: **audit → bucket inconsistencies into structural vs. conceptual → ask the user to triage by leverage → fix in priority order → one logical commit per concern → tag a baseline at the end.**
- After this wave, the established baseline is **v0.1.0**. Pre-1.0 SemVer rules (per ADR-0001) allow MAJOR-on-MINOR bumps, so substantial schema changes can still ship as `0.2.0`, `0.3.0` without committing to long-term stability. Aim for v1.0 once the four Aspirationals are within reach (multi-tenant readiness, skill consolidation, idempotent installer, Lean-Track sunset).

## Open follow-ups

- ~~**Validate agent migration in next real Sprint**~~ — **✅ verified 16.05.2026 via direct-question test.** A `senior-developer` subagent, started isolated via Task-Tool in the live real-world project session, reproduced SD-G-001 (Confidence 0.9, SourceKit cross-check pattern) and SD-G-002 (Confidence 0.5, `withKnownIssue` Simulator pattern) verbatim from `~/.claude/memory/senior-developer/instincts.md`. End-to-end confirmation that agent definitions are reloaded at every SubagentStart (not cached at session start) and the new schema reaches subagents as intended. Sprint 6 will provide additional real-use validation but is no longer needed for correctness.
- **Skill-drift lint** — write a check that flags drift between the `## Project Memory` section in CLAUDE.md and the memory blocks in `agents/*.md`. Would catch the class of gap this wave discovered.
- **v1.0 installer ADR** — placeholder ADR-0002 once Aspirationals are close. Replaces the silent-overwrite `cp -r` with an idempotent installer that preserves user customisations.
- **Postmortem of agent-coverage discrepancy** — `wingman`, `business-analyst`, `project-guide` have never been assigned project Tier-2 silos in any of the 8 analysed projects, despite the schema offering them. Either the agents do not surface persona-specific patterns (deliberate), or the project-side workflow is missing a "create silo" trigger. Worth a follow-up audit.
