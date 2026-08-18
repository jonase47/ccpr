---
name: ccpr Repo Conventions
description: Two cross-cutting conventions for the ccpr distribution repo — HANDOVER parser sync across four files, and the prose-language rule (English by default, German only in specific exceptions).
type: project
last_updated: 18.08.2026
status: active
---

The ccpr repo is a distribution package, not an application — every change here propagates to every project that consumes the config. Two conventions are non-obvious and easy to break.

## 1. HANDOVER parser sync across four files

The HANDOVER.md format is parsed by **four** independent code paths. They must stay in sync; changing one without the others silently breaks projects that consume the config.

- `templates/HANDOVER_TEMPLATE.md` — defines the section headers (`Last Active`, `Phase`, `Status`, `Next Steps`, `Open Decisions`, …) and the header's `Size cap` declaration
- `scripts/lib/next_steps.py` — Python parser that uses the same field names
- `scripts/bootstrap.sh` — bash sed patterns for the same fields
- `hooks/agent-monitor.py` — `parse_handover_cap()` reads the **header**, not the body: it scans only the first `HANDOVER_CAP_HEADER_LINES` (20) lines for a `≤N KB` and an `N lines` pair, and falls back to the template default (5 KB / 150 lines) when neither is found.

**Directional hazard in the header scan:** the two dimensions are matched independently, and the **first** match in the window wins. Any prose placed *above* the `Size cap:` line that happens to contain a number-unit pair therefore silently redefines that project's cap — a quoted "≤25 KB" doc-volume threshold or a "~300 lines" aside in an intro blockquote is enough, and nothing reports the override. Prose *below* the `Size cap:` line is harmless. The shipped template is safe today (`Size cap` is line 3, with only the `# Handover` heading above it); keeping it safe means adding new header prose **after** that line, or verifying the parse when it has to go before.

**How to apply:**
- Any rename or addition to HANDOVER fields requires updates in all four locations in the same commit.
- When reviewing PRs that touch the template, verify the parsers; when reviewing PRs that touch the parsers, verify the template.
- Specifically for the template header: any edit above the `Size cap` line must be checked against `parse_handover_cap()` — number-unit pairs there change behaviour, not just wording.

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
