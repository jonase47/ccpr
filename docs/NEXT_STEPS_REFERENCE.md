# Next Steps Reference

Central transition reference for process-compliant recommendations after each command.
Source of truth for the phase model: `~/.claude/docs/PROJECT_PHASES.md`

---

## 0) Track Decision (Entry Point)

Every new project starts with `/track-decision` — chooses **Lean-Track** (Prototyp/PoC/Spike, 4 Skills) or **Full-Track** (P0–P8, full pipeline).

```
/track-decision -> Lean  -> /lean-frame -> [TDD-Build with senior-developer] -> /lean-learn -> {PROMOTE | PIVOT-soft | PIVOT-hard | DROP}
                                                                                                  |          |              |             |
                                                                                                  v          v              v             v
                                                                                          /lean-promote  /lean-frame   /lean-frame    [repo frozen]
                                                                                                  |        (re-frame)  (fresh start)
                                                                                                  v
                                                                                          /project-init -> /constitution -> Full-Track ab P0

/track-decision -> Full  -> /project-init -> /constitution -> /p0-problem ...
```

Mid-flight Re-Assessment via `/track-decision` jederzeit erlaubt (kein Downgrade Full → Lean).

---

## A) Sub-Skill Sequences (within a phase)

Fixed order – the next step follows from the position in the sequence.

### Phase 0 – Discovery
```
p0-problem -> p0-market -> p0-regulatory -> gate-p0
```

### Phase 1 – Conception
```
p1-journeys -> p1-features -> p1-business-model -> p1-financial-plan -> p1-privacy -> gate-p1
```

### Phase 2 – Validation
```
p2-assumptions -> p2-market-validation -> p2-regulatory-check -> p2-poc -> gate-p2
```

### Phase 3 – Architecture & Design

Entry point: `/p3-architecture` (orchestrator for architecture sub-skills)

**Architecture sub-skills (via /p3-architecture):**
```
p3-arch-components -> p3-arch-techstack -> p3-arch-adr -> p3-arch-nfa
```

**After /p3-architecture – parallel tracks (any order):**
```
p3-architecture -> p3-data-model OR p3-security OR p3-ux OR p3-infra OR p3-cost
```

**Security sub-skills (via /p3-security):**
```
p3-sec-threats -> p3-sec-auth -> p3-sec-data -> p3-sec-api -> p3-sec-checklist
```

**UX sub-skills (via /p3-ux):**
```
p3-ux-navigation -> p3-ux-wireframes -> p3-ux-darkmode -> p3-ux-a11y
```

**Infra sub-skills (via /p3-infra):**
```
p3-infra-hosting -> p3-infra-cicd -> p3-infra-monitoring -> p3-infra-teststrategy
```

**When all P3 areas are complete:**
```
-> gate-p3
```

> After Gate-P3 (Go / Conditional Go): optionally run `/specialize` to adapt the generic all-rounder agents to the project's tech stack — it writes project-local specialized agent copies under `.claude/agents/` (with a Project Tech Context block from `TECH_STACK.md` + ADRs), so the P5 agents reason with stack-specific rules. A reviewable diff, no auto-commit.

### Phase 4 – Planning
```
p4-backlog -> p4-setup -> p4-docs -> p4-sprint -> gate-p4
```

### Phase 5 – Implementation (per sprint)

**TDD cycle (via /p5-implement):**
```
p5-impl-red -> p5-impl-green -> p5-impl-refactor
```

**Sprint workflow:**
```
p5-implement -> p5-review -> p5-acceptance (-> p5-bugfix on findings) -> p5-docs
```

**Review sub-skills (via /p5-review), per story:**
```
p5-review-code -> p5-review-security
```

> End-of-sprint: run `/p5-review-sprint` once over the whole sprint (`code-reviewer` @ opus) — a holistic pass complementary to the per-story reviews above, recommended before `/gate-p5`.

**After sprint completion:**
```
-> p5-review-sprint (recommended: holistic opus pass) -> gate-p5 -> p5-polish (recommended) -> p4-sprint (next) OR p6-functional (all sprints done)
```

### Phase 6 – Quality Assurance

**Main sequence:**
```
p6-functional -> p6-exploratory -> p6-a11y -> p6-audit -> p6-pentest -> p6-bugfix
```

**Functional sub-skills (via /p6-functional):**
```
p6-func-integration -> p6-func-e2e -> p6-func-regression
```

**Audit sub-skills (via /p6-audit):**
```
p6-audit-sast -> p6-audit-auth -> p6-audit-deps -> p6-audit-config -> p6-audit-dsgvo
```

**Pentest sub-skills (via /p6-pentest):**
```
p6-pentest-recon -> p6-pentest-auth -> p6-pentest-authz -> p6-pentest-injection -> p6-pentest-logic
```

**A11y sub-skills (via /p6-a11y):**
```
p6-a11y-visual -> p6-a11y-keyboard -> p6-a11y-screenreader
```

**When all P6 areas are complete:**
```
-> gate-p6
```

### Phase 7 – Launch & Deployment
```
p7-prepare -> p7-deploy -> p7-monitoring -> p7-release-docs -> p7-gtm -> gate-p7
```

### Phase 8 – Operations & Evolution
```
p8-ops, p8-business, p8-security -> parallel/continuous
p8-iteration -> Evolution loop (back to P1, P3, or P5)
```

---

## B) Phase Completion -> Gate

When all sub-skills of a phase are done, recommend the corresponding gate:

| Phase done | Gate |
|---|---|
| P0 commands completed | `/gate-p0` |
| P1 commands completed | `/gate-p1` |
| P2 commands completed | `/gate-p2` |
| P3 commands completed | `/gate-p3` |
| P4 commands completed | `/gate-p4` |
| P5 sprint completed | `/gate-p5` |
| P6 commands completed | `/gate-p6` |
| P7 commands completed | `/gate-p7` |

Gate P6 has two sub-gates:
- `/gate-p6-qa` – QA approval
- `/gate-p6-security` – Security approval
- `/gate-p6` – Overall approval (uses both sub-gates)

Gate P7 has two sub-gates:
- `/gate-p7-tech` – Technical go-live review
- `/gate-p7-business` – Business readiness review
- `/gate-p7` – Overall gate (uses both sub-gates)

---

## C) Gate Transitions (only on Go)

Gates define phase transitions. Only on "Go" is the next phase recommended:

| Gate | On Go | Next Command |
|---|---|---|
| `gate-p0` | Go | `/p1-journeys` |
| `gate-p1` | Go | `/p2-assumptions` |
| `gate-p2` | Go | `/p3-architecture` |
| `gate-p3` | Go | `/p4-backlog` |
| `gate-p4` | Go | `/p5-implement` or `/p4-sprint` |
| `gate-p5` | Sprint Done | `/p5-polish` (recommended cleanup) → `/p4-sprint` (next sprint) or `/p6-functional` (all sprints done) |
| `gate-p6` | Go | `/p7-prepare` |
| `gate-p7` | Go | `/p8-ops` |

---

## D) Fallback Rules

| Situation | Back to |
|---|---|
| Gate "Conditional Go" | Close open items in same phase |
| Gate "No-Go" | Back to same phase, create missing artifacts |
| `gate-p5` with findings | `/p5-bugfix` |
| `/p5-polish` empty (nothing to polish) | `/p4-sprint` directly |
| `/p5-polish` blocked (CI red / gate not passed / dirty tree) | Resolve precondition (commit, `/p5-bugfix`, `/gate-p5`), then retry |
| `p6-bugfix` completed | Back to the test command that found the bug |
| `p5-bugfix` completed | Back to review/acceptance test |
| `p8-iteration` | `/p1-journeys` (new feature), `/p3-architecture` (architecture change) or `/p5-implement` (small enhancement) |

---

## E) Utility Commands (cross-phase)

These commands are not bound to a specific phase:

| Command | Typical Context | After |
|---|---|---|
| `/konzept` | Before or during P0/P1 | `/p0-problem` or `/p1-features` |
| `/konzept-update` | Anytime | Back to current phase command |
| `/epic` | During P4 | `/user-stories` or `/p4-backlog` |
| `/user-stories` | During P4 | `/p4-backlog` or `/p4-sprint` |
| `/roadmap` | During P4 | `/p4-backlog` |
| `/roadmap-update` | Anytime | Back to current phase command |
| `/release-baseline [version]` | After Gate-P7 Go | `/p8-ops` or `/p8-iteration` |
| `/decision` | Anytime | Back to current phase command |
| `/project-init` | Project start | `/p0-problem` |

---

## Rules for Recommendations

1. **Always check HANDOVER.md** – The current phase state determines the recommendation
2. **Never skip phases** – No P5 command if Gate-P4 has not been passed
3. **Follow sub-skill sequences** – p5-impl-red -> p5-impl-green, never reversed
4. **Maximum 3 recommendations** – 1 primary next step + max. 2 alternatives
5. **Recommend gate when phase is complete** – Don't jump directly to the next phase
6. **Gates are authoritative** – Only gates open the way to the next phase
