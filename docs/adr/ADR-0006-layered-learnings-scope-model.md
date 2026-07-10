---
kind: adr
adr_id: ADR-0006
status: accepted
last_updated: 10.07.2026
related:
  - ADR-0007-shared-vault-storage.md
  - ADR-0002-workitem-backend-contract.md
  - ../CONSTITUTION.md
---

# ADR-0006: Layered learnings / instincts scope model

**Status:** Accepted (10.07.2026) — scope model realized
**Decision-makers:** Repo owner (Jonas), early tester (Olli, @OlArtTro)

> **Implementation (10.07.2026):** The scope model ships via the namespace convention
> (`templates/MEMORY_SCHEMA.md` → "Instinct ID namespaces": native `G-`, imported `{SRC}-`, shared
> org-tier `{ORG}-`) and the org-tier sync tool `scripts/memory-sync.sh` (down-auto materialization as a
> read-only overlay; up-promotion via a de-personalization/secret gate). Physical storage + scaling are
> in ADR-0007.

## Context

CCPR accumulates **instincts and memories** (confidence-scored behavioural rules and factual
knowledge). Today they live in two places: global (`~/.claude/`) and project (`docs/`). That is enough
for a solo developer, but a team or agency running CCPR across many client projects hits two needs the
solo case never has:

1. **Share learnings across projects** — a hard-won pattern should not be re-learned per project.
2. **Never leak client-specific knowledge** — a learning from client A's project must not surface in
   client B's context. This is an NDA / GDPR boundary, not a preference.

These pull in opposite directions: broad sharing vs. strict isolation. A layered **scope model**
resolves them.

## Decision

### The `scope` field and the tiers

Every instinct/learning carries a `scope` in its typed frontmatter. The framework defines four generic
tiers (storage locations are ADR-0007):

| Scope | Content | Visibility |
|---|---|---|
| `framework` | generic CCPR instincts | everyone (the public CCPR repo) |
| `org:<name>` | an organisation's cross-project, **de-customized** know-how | that organisation |
| `product:<name>` | product-specific | that product's team |
| `project:<id>` | project- / client-specific | that project only |

The tiers are generic: an org names its shared tier `org:<name>` (e.g. `org:acme`); the framework
never hardcodes a particular organisation.

### Load order — a runtime overlay

A CCPR instance loads the scopes **generic → specific** (`framework → org → product → project`). On
conflict, the **more specific scope wins**. Contradictions between layers are **flagged, not silently
overwritten** — the human sees the clash.

### Core rules

1. **Learnings are born in the narrowest scope.** In client work the default is `scope: project`;
   nothing is shared by accident.
2. **Down automatically, up only by promotion.** `framework` / `org` / `product` instincts flow into
   project work automatically. The reverse (`project → org`, `org → framework`) happens **only via a
   Pull Request** into the target scope's store — a deliberate, reviewed act.
3. **Generalisation duty on promotion.** The promotion PR must **de-customize**: remove client names,
   domain data, and anything identifying; reduce the learning to the transferable pattern.
   Client-specific content never leaves the project scope. **This is a Constitution rule** (the same
   class of boundary as the claiming rule, ADR-0005 — it protects a hard confidentiality line).
4. **Runtime overlay, not copy.** `org` / `framework` instincts are loaded **read-only at runtime**
   and **never written into the project repo**. Only the project scope is written to the project. A
   client repo therefore contains **only what belongs to the client** and can be handed over at any
   time.
5. **Solo stays intact.** With no remote scopes configured, only the local `project` scope exists —
   behaviour exactly as today, consistent with the work-item backend model (ADR-0002): the layered
   machinery is opt-in, the entry bar does not rise.

### The promotion path is the quality gate

`project → org` (or `org → framework`) is a PR into the target scope's store, carrying the
de-customized pattern. **The review gate *is* the quality filter**: only what survives the
generalisation PR enters the shared scope. This is what keeps a shared scope from degenerating into a
free-for-all wiki — distilled patterns, not raw material.

## Consequences

- **Cross-project sharing without leakage:** the org tier carries reusable, de-customized patterns; the
  project tier keeps client-specifics isolated (the NDA/GDPR requirement is met structurally).
- **Handover-safe client repos:** the runtime overlay means a client repo never accretes shared
  instincts.
- **Solo unaffected:** no remote scopes → today's behaviour.
- **The shared scope stays curated:** the promotion gate bounds its growth.
- Storage, scaling, the tenant tier, and the runner registry are ADR-0007.

## Alternatives considered

- **A single global instinct pool** (today's model, extended to teams): rejected — no isolation;
  client A's learning surfaces for client B.
- **Copying shared instincts into each project repo:** rejected — breaks clean handover; the runtime
  overlay avoids it.
- **Automatic upward promotion:** rejected — client-specifics would leak without the generalisation
  gate; upward must be a reviewed, de-customizing act.

## Notes

Storage of each tier (in particular the shared `org` vault), the loading/scaling mechanics, the
tenant-level tier, and the runner registry are specified in ADR-0007. This ADR defines the **model and
its rules**; ADR-0007 defines **where the tiers live and how they scale**.
