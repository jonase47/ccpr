# CCPR Manual

The **how** of CCPR. This folder lives in the repository only — it is **not**
copied into `~/.claude/` by `install.sh`. Read it here in the cloned repo or on
the repository host.

The repository [`README.md`](../README.md) covers the **what** (what CCPR is, the
phase system, the agent team, installation). The runtime references Claude reads
*during* project work stay in [`../docs/`](../docs/) (`PROJECT_PHASES.md`,
`NEXT_STEPS_REFERENCE.md`, `CONSTITUTION.md`).

## Contents

| Document | Read it when you want to… |
|---|---|
| [GETTING_STARTED.md](GETTING_STARTED.md) | Onboard from zero — quickstart, then a full read-along walkthrough |
| [WORKFLOW_CHEATSHEET.md](WORKFLOW_CHEATSHEET.md) | Look up commands and scripts quickly during daily work |
| [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | Understand the architecture and every mechanism in depth (slim index → `system/` detail files) |
| [SECTIONS_COMMANDS.md](SECTIONS_COMMANDS.md) | Browse all 116 commands grouped by section (slim index → `commands/` detail files) |
| [LEAN_TRACK.md](LEAN_TRACK.md) | Understand the Lean-Track decision tree and design (transient — sunset at v1.0) |

### Detail files

- [`system/`](system/) — `SYSTEM_OVERVIEW.md` split into agents, phases-gates,
  commands, cross-cutting, monitoring-scripts, memory-instincts, file-structure.
- [`commands/`](commands/) — `SECTIONS_COMMANDS.md` split into phases, gates,
  track, learning, utility.

## A reasonable reading order

1. [GETTING_STARTED.md](GETTING_STARTED.md) — get a project moving.
2. [WORKFLOW_CHEATSHEET.md](WORKFLOW_CHEATSHEET.md) — keep it open while you work.
3. [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) — when you want to know *why* it works.
4. [SECTIONS_COMMANDS.md](SECTIONS_COMMANDS.md) — when you need a specific command.
