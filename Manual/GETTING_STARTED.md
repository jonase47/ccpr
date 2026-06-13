# Getting Started with CCPR

A read-along guide for new users. By the end of the Quickstart you will
understand *what CCPR is*, *how you talk to it*, and *what it produces*. The
Walkthrough then takes you through two complete example projects so the daily
rhythm becomes concrete.

This guide assumes CCPR is already installed in `~/.claude/`. If not, do the
install first — see the **Installation** section in [`../README.md`](../README.md).
This document does not repeat install steps or the full command list; it explains
how to *use* what you installed. For the exhaustive command tables, keep
[`WORKFLOW_CHEATSHEET.md`](WORKFLOW_CHEATSHEET.md) open in a second tab.

## Confirm your install (60 seconds)

Before the walkthrough, check the install actually landed. Open Claude Code in
any project directory and type:

```
/guide
```

You should get a **status snapshot** (current phase, open points) and a few
**suggested next steps** — that confirms the skills and agents are wired up. If
`/guide` is not recognised, the copy into `~/.claude/` did not take; re-run the
[installer](../README.md#2-run-the-installer).

When that works, start a real project with `/track-decision` (it picks Lean vs.
Full for you). The rest of this guide assumes `/guide` responded.

---

# Part 1 — Quickstart (~15 minutes)

## The mental model in three ideas

CCPR is not an app you launch. It is a **configuration layer for Claude Code**:
a set of skills, agents, templates and scripts that turn Claude Code into a
disciplined software-delivery process. You drive; Claude executes.

**1. Skills are the verbs you type.** Anything starting with `/` is a skill —
`/track-decision`, `/p0-problem`, `/p5-implement`, `/gate-p3`. A skill is a
prepared instruction set: it tells Claude what to do, which agents to involve,
and where to write the result. You do not need to remember all of them; you need
to know *which phase you are in* and the skill names follow from that.

**2. Agents are a specialist team.** Behind the skills sit 13 domain
agents (plus `project-guide` and `wingman`) — a `konzeptor` for product thinking,
a `system-architekt` for architecture, a `senior-developer` who writes code
test-first, a `security-master`, and so on. You rarely call them by name. A skill
pulls in the right specialists automatically (max. 3–4 per step, on purpose). The
full roster is in [`../CLAUDE.md`](../CLAUDE.md) under "Agent Team".

**3. Phases are a pipeline with gates.** Serious projects move through eight
phases, P0 to P8 — Discovery, Conception, Validation, Architecture, Planning,
Implementation, Quality Assurance, Launch, Operations. Between phases sit
**gates** (`/gate-p0`, `/gate-p1`, …): a go / no-go check that the previous phase
actually produced what the next one needs. A gate that fails tells you what is
missing instead of letting you build on sand.

```
P0 Discovery -> P1 Conception <-> P2 Validation -> P3 Architecture -> P4 Planning
   -> P5 Implementation <-> P6 Quality Assurance -> P7 Launch -> P8 Operations
```

## Two tracks: pick the right amount of process

Not every idea deserves the full eight-phase pipeline. The very first thing you
run on any new idea is `/track-decision`. It asks a few questions and routes you to:

- **Lean-Track** — four skills, no gates, no sprint bookkeeping. For prototypes,
  proofs of concept, and spikes where the goal is to *learn fast*. This is the
  best place to start as a new user: low ceremony, quick feedback.
- **Full-Track** — the complete P0–P8 pipeline with gates and a project
  constitution. For anything real, multi-user, or subject to GDPR.

You can always re-run `/track-decision` to reassess. The one rule: there is no
automatic downgrade from Full back to Lean (see [`../CLAUDE.md`](../CLAUDE.md),
"Track Decision").

## Your first ten minutes

Open a terminal in an empty folder, start Claude Code, and type:

```
/track-decision a small tool that converts Markdown notes into flashcards
```

Answer its questions honestly ("just a prototype", "no personal data"). It will
recommend **Lean**. Then:

```
/lean-frame
```

This writes `docs/FRAME.md` — a single-page source of truth for the idea (problem,
scope, the one thing you want to learn) plus a slim `docs/CLAUDE-lean.md`. Read
`FRAME.md`. That file *is* the plan; everything else hangs off it.

From here you build freely — describe a feature and let the `senior-developer`
take over test-first. When you have learned what you wanted, run `/lean-learn` to
capture findings and decide PROMOTE / PIVOT / DROP. That is a complete Lean loop.

## How to read what CCPR produces

Everything the system "thinks" ends up as **Markdown files in `docs/`** — not
hidden state. This is deliberate: you can read, review, and diff every artifact.

- `docs/FRAME.md` (Lean) or the phase folders `docs/discovery/`, `docs/conception/`,
  `docs/architecture/`, … (Full) hold the substance.
- `docs/HANDOVER.md` is the session memory. When you come back tomorrow, Claude
  reads it and continues where you left off. You never have to re-explain context.
- Each phase writes a slim **index file** plus one **detail file per sub-skill**,
  so you can skim the index and drill into detail only when needed.

## When you are not sure what to do next

Type `/guide`. The `project-guide` agent reads your current state and gives you a
status snapshot plus three prioritised next actions — and hands you off to the
right specialist if your request is fuzzy. It is the "I'm lost, orient me" button.

That is the whole loop: **decide a track → run the phase skills → let gates keep
you honest → read the docs → `/guide` when unsure.** The rest of this document
makes each step concrete.

---

# Part 2 — Walkthrough

Two end-to-end examples. Walkthrough A (Lean) is the one to actually try first.
Walkthrough B (Full) shows the heavyweight pipeline so you recognise it when a
real project needs it.

## Choosing a track (in practice)

`/track-decision` runs two checks:

- **Knockout (K1–K5):** does the idea touch personal data, special data
  categories, an imminent launch, a regulated domain, or external sign-off? Any
  hit pushes you to Full — these are things you cannot responsibly improvise.
- **Indicator score (I1–I5):** softer signals (team size, lifespan, complexity)
  that tip the recommendation when no knockout fires.

Trust the recommendation the first few times. You will develop a feel for when a
"prototype" is quietly a real product.

## Walkthrough A — Lean-Track, end to end

Scenario: you want to test whether an LLM can usefully turn meeting notes into
action items. Goal is *learning*, not shipping.

```
/track-decision LLM that extracts action items from meeting notes   -> Lean
/lean-frame
```

Read `docs/FRAME.md`. It states the hypothesis ("an LLM can extract action items
with acceptable precision"), the scope boundary (no UI, paste-in text only), and
the single success signal you will judge against. A Constitution-Light section in
the same file captures the few non-negotiables (e.g. "no real customer data in
test inputs").

Now build. You describe behaviour; the `senior-developer` works test-first
(Red → Green → Refactor), committing one TDD cycle at a time:

```
build a function that takes raw notes text and returns a list of action items
```

Iterate until you can judge the hypothesis. Then:

```
/lean-learn
```

This writes `docs/LEARNINGS.md` and forces a decision:

- **PROMOTE** — it works, turn it into a real project. Run `/lean-promote` (writes
  `docs/PROMOTION_BRIEF.md`), then `/project-init`, which reads the brief and
  starts the Full-Track with your learnings carried over.
- **PIVOT** — the core idea holds but the approach was wrong; reframe and keep the code.
- **DROP** — you learned it is not worth it. That is a *successful* Lean outcome,
  not a failure. You spent days, not months.

The point of Lean: no gates, no backlog, no sprint ceremony — just frame, build,
learn, decide.

## Walkthrough B — Full-Track, end to end

Scenario: the action-item extractor proved valuable and will become a real,
multi-user product handling customer notes (so: personal data → Full-Track).

**Start and constitution.**

```
/track-decision ...        -> Full
/project-init ActionMiner   <- scaffolds the project, then calls /constitution
cd ActionMiner
claude
```

`/project-init` creates the project structure and runs `/constitution`, producing
`docs/CONSTITUTION.md` with three tiers — **Inviolable** (hard rules every gate
enforces), **Default** (standards you follow unless you justify otherwise), and
**Aspirational** (goals). The Inviolables become a mandatory input to every gate:
violate one and the gate verdict reads "Inviolable breach".

**Then the phases, in order. The pattern is always: run the phase skills → run the gate.**

- **P0 Discovery — "Is it worth it?"** `/p0-problem`, `/p0-market`,
  `/p0-regulatory`, then `/gate-p0`. Output: a clear problem, target audience,
  market read, and any legal knockouts. The gate is a genuine go / no-go.
- **P1 Conception — "What are we building?"** `/p1-journeys`, `/p1-features`
  (defines the MVP boundary), `/p1-business-model`, `/p1-financial-plan`,
  `/p1-privacy` (first GDPR pass), then `/gate-p1`.
- **P2 Validation — "Are the assumptions right?"** `/p2-assumptions` surfaces what
  must be true; `/p2-market-validation`, `/p2-poc`, `/p2-regulatory-check` test
  the riskiest ones. `/gate-p2` can say Go, No-Go, or Pivot back to P1.
- **P3 Architecture — "How do we build it?"** The biggest phase. `/p3-architecture`
  (with sub-skills for components, tech stack, ADRs, NFRs), `/p3-data-model`,
  `/p3-ux` (incl. accessibility and dark-mode strategy), `/p3-security` (STRIDE
  threat model, auth concept), `/p3-infra` (hosting, CI/CD, monitoring, test
  strategy), `/p3-cost`. Then `/gate-p3`. Architecture decisions are recorded as
  ADRs so the "why" survives.
- **P4 Planning — "In what order?"** `/p4-backlog` (epics, stories, milestones),
  `/p4-setup` (repo + CI/CD), `/p4-docs`, `/p4-sprint`, then `/gate-p4`. After
  this, work can start "tomorrow morning".
- **P5 Implementation — "Let's build!"** The sprint loop. `/p5-implement <feature>`
  drives a full TDD cycle; `/p5-review` and `/p5-acceptance` verify it;
  `/p5-bugfix` and `/p5-docs` keep things clean. `/gate-p5` checks the sprint is
  actually done. This phase repeats per sprint.
- **P6 Quality Assurance — "Is it stable?"** `/p6-functional` (integration / E2E /
  regression), `/p6-exploratory`, `/p6-a11y` (accessibility), `/p6-audit`
  (security + dependency + GDPR), `/p6-pentest`. The release gate `/gate-p6`
  requires both a QA and a security approval. The release tag (`vX.Y.Z`) is set here.
- **P7 Launch — "Ship it!"** `/p7-prepare`, `/p7-deploy` (+ smoke tests),
  `/p7-monitoring` (and rollback test), `/p7-release-docs`, `/p7-gtm`. `/gate-p7`
  has a technical and a business half.
- **P8 Operations — "Is it running?"** The evolution loop: `/p8-ops` (incidents,
  monitoring), `/p8-business` (KPIs), `/p8-security` (ongoing scans/updates),
  `/p8-iteration` (feedback → backlog → next sprint). New features loop back to
  P1, P3, or P5.

You will not do all of this in one sitting. Across sessions, `HANDOVER.md` keeps
the thread; gates keep the quality. The full theory per phase is in
[`PROJECT_PHASES.md`](../docs/PROJECT_PHASES.md).

## The supporting cast (good to know, not required on day one)

These work quietly in the background; learn them as you go.

- **Local scripts** (`~/.claude/scripts/`) save tokens by doing mechanical work
  outside Claude — e.g. `bootstrap.sh` collects context before a session,
  `run-tests.sh` runs tests and hands Claude structured JSON, `gate-preflight.py`
  pre-checks gate artifacts. Optional but worth the shell aliases in the cheatsheet.
- **HANDOVER.md** is your cross-session memory. Commands update it automatically;
  a fresh session reads it and continues.
- **Instincts** are confidence-scored rules (0.3–0.9) the system learns from your
  sessions. `/postmortem` after a session proposes new ones; over time CCPR adapts
  to how you work.
- **Memory** stores durable project facts in `docs/memory/` so they survive context
  resets — distinct from instincts, which are *behaviours* rather than *facts*.
- **Wingman** consolidates the output of several agents into one short summary, so
  you read a digest instead of five raw reports.

## Where to go next

| You want to… | Read |
|---|---|
| Look up any command quickly | [`WORKFLOW_CHEATSHEET.md`](WORKFLOW_CHEATSHEET.md) |
| Understand a phase in depth | [`PROJECT_PHASES.md`](../docs/PROJECT_PHASES.md) |
| See the whole command catalogue | [`SECTIONS_COMMANDS.md`](SECTIONS_COMMANDS.md) |
| Understand the agent architecture | [`SYSTEM_OVERVIEW.md`](SYSTEM_OVERVIEW.md) |
| Know the rules CCPR binds itself to | [`CONSTITUTION.md`](../docs/CONSTITUTION.md) |
| Install or re-sync the config | [`../README.md`](../README.md) |

The shortest possible summary: **start with `/track-decision`, follow the skills
the phase suggests, let the gates catch problems early, and type `/guide`
whenever you lose the thread.**
