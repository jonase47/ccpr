---
name: ccpr Repo Conventions
description: Two cross-cutting conventions for the ccpr distribution repo — HANDOVER parser sync across three files, and the prose-language rule (English by default, German only in specific exceptions).
type: project
last_updated: 26.04.2026
status: active
---

The ccpr repo is a distribution package, not an application — every change here propagates to every project that consumes the config. Two conventions are non-obvious and easy to break.

## 1. HANDOVER parser sync across three files

The HANDOVER.md format is parsed by **three** independent code paths. They must stay in sync; changing one without the others silently breaks projects that consume the config.

- `templates/HANDOVER_TEMPLATE.md` — defines the section headers (`Last Active`, `Phase`, `Status`, `Next Steps`, `Open Decisions`, …)
- `scripts/lib/next_steps.py` — Python parser that uses the same field names
- `scripts/bootstrap.sh` — bash sed patterns for the same fields

**How to apply:**
- Any rename or addition to HANDOVER fields requires updates in all three locations in the same commit.
- When reviewing PRs that touch the template, verify the parsers; when reviewing PRs that touch the parsers, verify the template.

## 2. Prose-language convention

CLAUDE.md and the user's global preferences mandate English. The repo migrated to English on 19.04.2026 (waves 1–7). Two intentional exceptions remain:

- **YAML `description` example fields in agent definitions** may contain German user-input examples — these illustrate the German-speaking user workflow and are explicit migration exceptions.
- **DSGVO / DiGA terminology** stays German because it is the legal vocabulary (e.g. `DSGVO_INITIAL_ASSESSMENT.md` — the artifact filename was deliberately kept after consolidation on 19.04.2026).

`templates/PROJECT_CLAUDE_TEMPLATE.md` line 66 has `"Konzeptor:"` as an illustrative example comment — accepted under the same exception rule.

**How to apply:**
- New prose (commands, scripts, hooks, templates, agent prompts): English only.
- New YAML example fields: German is fine when they demonstrate user-facing input; otherwise English.
- Never translate DSGVO/DiGA artifact names.

## 3. Code-style minima

- Python scripts: **standard library only**, no third-party dependencies — the pipeline must run inside any Claude Code container without extra installs.
- Bash scripts: start with `set -euo pipefail`.
- 1 TDD cycle = 1 commit (Conventional Commits: `feat`/`fix`/`refactor`/`docs`/`chore`).
