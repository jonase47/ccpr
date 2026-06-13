# /cross-check – Cross-Artifact Consistency Check Across Phases

Reads phase indexes and selected detail files, checks inconsistencies **between** phases
(architecture ↔ implementation, features ↔ stories, threats ↔ mitigations, etc.).

Bridges the gap between intra-phase lints (`phase-docs-lint.sh`) and gate content evaluation —
finds contradictions no other skill surfaces.

**Recommendation, not a mandatory step.** Gates list `/cross-check` as an optional pre-flight check.

## Argument: $ARGUMENTS = [optional: projectdir]

- Without argument: operates on `$(pwd)`.

## Prerequisites

- Project has at least 2 completed phases (otherwise there is no "cross")
- Phase indexes exist: `docs/discovery/DISCOVERY.md`, `docs/concept/CONCEPT.md`, `docs/architecture/ARCHITECTURE.md`, `docs/planning/PROJECT_PLAN.md`, optionally `docs/quality/QA.md`
- Optional: `docs/CONSTITUTION.md` (for R6)

## Lead Agent

**code-reviewer** with **system-architekt** as consultant for tech-specific findings.

## Rule Catalogue v1 (7 Rules)

### R1: FEATURES.md ↔ AUTH.md / User-Stories
Every user-facing feature (login, profile, permissions) must have a corresponding flow in AUTH.md.

**Sources:**
- `docs/concept/FEATURES.md` (feature list, MoSCoW)
- `docs/architecture/AUTH.md` (auth flows)
- `docs/planning/BACKLOG.md` (user stories as cross-reference)

**Check:** For each feature tagged as user-facing (heuristic: mentions "login", "account", "profile", "sign-in") → is a matching flow described in AUTH.md?

### R2: TECH_STACK.md ↔ DATA_MODEL.md (DB choice consistent)
If TECH_STACK.md names PostgreSQL, DATA_MODEL.md must not use MongoDB syntax (and vice versa).

**Sources:**
- `docs/architecture/TECH_STACK.md` (DB choice, language, framework)
- `docs/architecture/DATA_MODEL.md` (schema, ERD)
- `docs/architecture/API_SPEC.md` (endpoints)

**Check:** Extract DB term from TECH_STACK (regex `PostgreSQL|MongoDB|SQLite|SwiftData|MySQL`); search DATA_MODEL for syntax markers (CREATE TABLE, NoSQL JSON schema, `@Model` SwiftData decorators). Report inconsistencies.

### R3: THREATS.md ↔ AUTH.md / SECURITY.md (mitigation for every threat)
Every threat in THREATS.md has at least one mitigation in AUTH.md, DATA_SECURITY.md, or CHECKLIST.md.

**Sources:**
- `docs/architecture/THREATS.md` (STRIDE threats, T-01..T-NN)
- `docs/architecture/AUTH.md`, `DATA_SECURITY.md`, `API_SECURITY.md`, `CHECKLIST.md`

**Check:** Extract threat IDs from THREATS (pattern `T-\d+`); search mitigation files for references. Report threats with no mitigation mention.

### R4: NFR.md ↔ TESTSTRATEGY.md (every NFR has a test approach)
Every NFR ID in NFR.md has a test approach in TESTSTRATEGY.md (or a P6 quality file).

**Sources:**
- `docs/architecture/NFR.md` (non-functional requirements, NFR-001..NFR-NN)
- `docs/architecture/TESTSTRATEGY.md` (or `docs/quality/FUNCTIONAL.md`)

**Check:** Extract NFR IDs from NFR.md; search TESTSTRATEGY/FUNCTIONAL files for references. Report NFRs with no test reference.

### R5: ADR status ↔ component references
Rejected ADRs (`status: rejected` or `status: superseded`) must not be actively referenced in components or code.

**Sources:**
- `docs/architecture/ADR/*.md` (all ADRs)
- `docs/architecture/COMPONENTS.md`, `ARCHITECTURE.md`
- Code (`src/`) — optional, header comments only

**Check:** Filter ADRs with `status: rejected|superseded`; grep COMPONENTS/ARCHITECTURE for ADR IDs. Report active references to rejected ADRs.

### R6: CONSTITUTION.md (Inviolable) ↔ ADRs / Implementation
No ADR and no phase decision may violate an Inviolable.

**Sources:**
- `docs/CONSTITUTION.md` (Inviolable section)
- `docs/architecture/ADR/*.md` (all active ADRs)
- `docs/concept/FEATURES.md`, `docs/concept/USER_JOURNEYS.md` (concept decisions)

**Check:** Extract Inviolable bullets (short names). Search ADRs and FEATURES for bullet topics. **Soft heuristic:** if an Inviolable says "local-only" but an ADR describes a "cloud provider" → flag as potential inconsistency; manual review required (LLM-based evaluation rather than regex).

### R7: STORY_INDEX.md ↔ epic detail files (stories have epic references)
Stories in STORY_INDEX.md reference epics; every epic detail file lists its stories.

**Sources:**
- `docs/planning/backlog/STORY_INDEX.md` (or directly from BACKLOG.md)
- `docs/planning/backlog/E*.md` (epic detail files)

**Check:** Stories → epic reference present? Epic detail → story list complete? Bidirectional consistency.

## Execution

### 1. Read phase indexes

Load all available phase indexes (P0-P6) and sub-indexes (SECURITY.md, INFRA.md, UX_CONCEPT.md, QA.md subs). Identify which detail files exist — rule checks run only on existing files.

### 2. Run rules

For each rule R1–R7:
1. Check source files (do they exist?)
2. If not all sources present → skip rule, note "skipped: <missing file>" in the report.
3. Otherwise: run check, collect findings.

### 3. Consolidate findings

Per finding:
- **Rule** (R1–R7)
- **Severity** (info / warning / error)
  - error: hard inconsistency (e.g. T-04 with no mitigation; rejected ADR actively referenced)
  - warning: probable inconsistency, manual review required (e.g. Inviolable potentially violated)
  - info: minor drift (e.g. story with no epic reference)
- **Sources** (file + line number if applicable)
- **Suggestion** (what to do)

### 4. Write report

Output: `docs/.cross-check-report.md` (volatile file, overwritten on every re-run).

Structure:
```markdown
# Cross-Check Report (generated: DD.MM.YYYY HH:MM)

## Summary
- Rules checked: N / 7
- Findings: X errors, Y warnings, Z info
- Skipped: ... (with reason)

## Errors
…

## Warnings
…

## Info
…

## Recommendations
1. {concrete follow-up actions}
```

### 5. Next steps

- On errors: address directly before the next Gate
- On warnings: user decides whether to address now or in the next Sprint
- On info: informational only, no action required

## When to use

- **Before every Gate** (recommendation, not mandatory) — Gates list `/cross-check` as an optional pre-flight check
- **After significant doc updates** (e.g. new ADR, new threats, changed Constitution)
- **On suspected drift** (doc-volume-check reports rapidly growing files)
- **On promotion Lean → Full** (beyond `/lean-promote` for consistency verification)

## When NOT to use

- Before Gate-P0 / Gate-P1 — usually only one phase present, no "cross" to check
- During an active TDD cycle — disruptive

## Iterative Evolution

v1 has 7 rules. Extension is project-driven:
- New rule discovered in pentest or audit? → add R8
- Rule produces too many false positives? → refine or remove
- Constitution Inviolables in R6: add a specialised rule per Inviolable type if needed

The rule catalogue is maintained directly in `~/.claude/commands/cross-check.md` — no separate YAML catalogue (too much overhead for 7 rules).

## Result

- `docs/.cross-check-report.md` (report with findings)
- Console output: short summary (X errors / Y warnings / Z info)

### Handover Epilogue

Update `docs/HANDOVER.md` only if errors are found — otherwise the report file is sufficient.
