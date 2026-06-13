---
kind: system-doc-detail
parent_index: ../SYSTEM_OVERVIEW.md
section: command-system
last_updated: 12.06.2026
---

# Command System

## Overview

- **82 phase commands** (P0: 3, P1: 5, P2: 4, P3: 23, P4: 4, P5: 12, P6: 22, P7: 5, P8: 4)
- **12 gates** (8 main gates + 4 sub-gates for P6/P7)
- **2 learning commands** (/postmortem, /instinct)
- **13 utility commands** (/konzept, /konzept-update, /decision, /epic, /user-stories, /roadmap, /roadmap-update, /project-init, /logs-summary, /guide, /release-baseline, /cleanup, /specialize)
- **6 track + cross-cutting commands** (/track-decision, /constitution, /lean-frame, /lean-learn, /lean-promote, /cross-check)
- **Total: 115 commands**

## Naming Convention

```
/p[phase]-[section]     -> e.g. /p6-pentest
/gate-p[phase]          -> e.g. /gate-p0
/p[phase]-[sub-skill]   -> e.g. /p5-impl-red, /p6-audit-sast
```

## Sub-Skill Sequences

Within a phase there are fixed sequences. The most important:

**P3 Architecture** (branches after /p3-architecture):
```
/p3-architecture
    +-- p3-arch-components -> p3-arch-techstack -> p3-arch-adr -> p3-arch-nfa
    |
    +-- /p3-data-model
    +-- /p3-security
    |       +-- p3-sec-threats -> p3-sec-auth -> p3-sec-data -> p3-sec-api -> p3-sec-checklist
    +-- /p3-ux
    |       +-- p3-ux-navigation -> p3-ux-wireframes -> p3-ux-darkmode -> p3-ux-a11y
    +-- /p3-infra
    |       +-- p3-infra-hosting -> p3-infra-cicd -> p3-infra-monitoring -> p3-infra-teststrategy
    +-- /p3-cost
         -> gate-p3
```

**P5 Implementation** (TDD cycle per feature):
```
/p5-implement
    +-- p5-impl-red -> p5-impl-green -> p5-impl-refactor
         -> p5-review (p5-review-code -> p5-review-security)
              -> p5-acceptance (-> p5-bugfix on findings)
                   -> p5-docs
                        -> gate-p5
                             -> p5-polish (recommended cleanup)
                                  -> p4-sprint (next) OR p6-functional (all sprints done)
```

**P6 Quality Assurance:**
```
p6-functional (integration -> e2e -> regression)
    -> p6-exploratory
         -> p6-a11y (visual -> keyboard -> screenreader)
              -> p6-audit (sast -> auth -> deps -> config -> dsgvo)
                   -> p6-pentest (recon -> auth -> authz -> injection -> logic)
                        -> p6-bugfix
                             -> gate-p6 (gate-p6-qa + gate-p6-security)
```

## Next Steps Recommendations

After each command, Claude recommends 1-3 sensible next steps.
Rules:
1. HANDOVER.md determines the current phase state
2. Never skip phases — no P5 command if Gate-P4 has not been passed
3. Follow sub-skill sequences
4. Gates are authoritative — only gates open the way to the next phase

Full transition reference: [NEXT_STEPS_REFERENCE.md](../../docs/NEXT_STEPS_REFERENCE.md)
All commands in detail: [SECTIONS_COMMANDS.md](../SECTIONS_COMMANDS.md)
