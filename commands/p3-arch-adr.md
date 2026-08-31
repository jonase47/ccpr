---
disable-model-invocation: true
---
# /p3-arch-adr – Write Architecture Decision Records

Documents all significant architectural decisions as ADRs.

## Argument: $ARGUMENTS = [Specific decision, e.g. "ADR-0001 Monolith"]

If provided: Write ADR for the named decision.
If not provided: Create ADRs for all open decisions from architecture and tech stack.

## Prerequisites
- ARCHITECTURE.md and TECH_STACK.md exist

## Agent
- **Type**: system-architekt
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From ARCHITECTURE.md: Architectural decisions made (short list)
- From TECH_STACK.md: Technology decisions with alternatives

## Prompt Template
> **Goal**: Write ADRs for all significant architectural decisions.
>
> **Decisions**:
> [inline from ARCHITECTURE.md + TECH_STACK.md]
>
> **Output Format**:
> One file per ADR with:
> - Title, date
> - Context (1-2 sentences)
> - Options (enumeration)
> - Decision (1 sentence)
> - Justification (1-2 sentences)
> - Consequences (pros/cons as list)
>
> **Follow-ups and Addenda** — once the ADR has shipped and open questions get answered
> later, apply the same two conventions this repository's own ADRs under `docs/adr/`
> use (`CONTRIBUTING.md`, "Record an ADR's resolutions in place"):
> - A resolved follow-up is struck through **in place**, with a pointer to what resolved
>   it — never silently deleted: `~~**original wording**~~ **Resolved in Addendum N
>   (DD.MM.YYYY): the answer, in one sentence.**`
> - An addendum's heading **names what it resolves**: `## Addendum N (DD.MM.YYYY): <what
>   it resolves>` — a reader working down the follow-up list needs the heading to find
>   the answer.
>
> **Constraints**:
> - Only decisions with real alternatives (no trivial decisions)
> - Numbering: ADR-0001, ADR-0002, etc. (four digits, matching this repository's own
>   `docs/adr/` convention)

## Orchestrator Checkpoint
- [ ] Every ADR has context, options and justification?
- [ ] No redundant ADRs?
- [ ] Every ADR's frontmatter has `status` and `adr_status` mapped correctly (never the
  decision word in `status`)?

## Write Detail Files
Write one file per ADR to `docs/architecture/ADR/`, named `ADR-NNNN-slug.md` (four-digit
number, e.g. `ADR-0001-monolith-vs-microservices.md`). `docs/architecture/ADR/` is inside
a phase folder, so `phase-docs-lint.sh` checks it like any other phase-detail file. Start
with this YAML frontmatter:

```yaml
---
phase: P3
subskill: arch-adr
status: active
last_updated: <DD.MM.YYYY>
kind: adr
adr_id: ADR-0001
adr_status: accepted
---
```

`status` and `adr_status` are two different lifecycles and must stay on two different
fields. Writing the decision word into `status` collides with the document-status enum
`phase-docs-lint.sh` enforces (`skeleton | draft | active | frozen | archived | living`)
and fails the lint — the same species of collision `commands/p4-sprint.md`'s
`risk-detail` block had (fixed in `13a0dae`; `risk_status` there, `adr_status` here). Map
`adr_status` to `status` like this:

| `adr_status`  | `status`   |
|---|---|
| `accepted`    | `active`   |
| `proposed`    | `draft`    |
| `rejected`    | `archived` |
| `superseded`  | `archived` |

These four cover the standard ADR lifecycle. Beyond them the left column is
**open**: a project may need an `adr_status` value none of the four fit — this
repository's own `docs/adr/ADR-0007-shared-vault-storage.md` uses
`partially-implemented` (an accepted decision whose implementation has not
fully landed). Any such value is fine as long as its mapped `status` is one of
the six values above. `partially-implemented` maps to `active`, because
`status` describes whether the document is currently governing the codebase —
not how completely the decision behind it has been carried out.

## Update Phase Index
Update `docs/architecture/ARCHITECTURE.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row per ADR, linking to `docs/architecture/ADR/ADR-NNNN-slug.md`.
- Lift load-bearing decisions into **Key Decisions** (1 line each, e.g. `- Backend: PostgreSQL → see ADR-0003`).

### Handover Epilogue
**Before writing.** `docs/HANDOVER.md` is capped — the file states its own limit in its header
(default: ≤5 KB / ~150 lines). Two rules follow from that, and neither is optional:
- **Replace this command's previous epilogue block, do not append a second one.** Stacking is what
  pushes the file over; one skill run has been measured adding 1021 B, ~20 % of the cap.
- **If the file is already near its cap, shorten before you add.** Reading the cap sentence is not
  the same as measuring: check the actual size, and when there is no room, condense existing content
  or hand the user `/cleanup` instead of growing the file further.

Update `docs/HANDOVER.md`:
- What was created/changed
- Open decisions → the `## Open Decisions` table; a finding outside this command's scope goes to the `## Open Points` inbox instead
- Next steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that fit the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
