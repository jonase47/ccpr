---
kind: adr
adr_id: ADR-0015
adr_status: accepted
status: active
last_updated: 08.09.2026
related:
  - ADR-0014-documentation-namespace.md
  - ../CONSTITUTION.md
---

# ADR-0015: A bare first name is not a "real user name" under Constitution Inviolable #2

**Status:** Accepted (08.09.2026)
**Decision-makers:** Repo owner

## Context

### The question ADR-0014 raised and deliberately left open

While drafting ADR-0014 (CCP-1150), the drafting agent flagged its own `Status` and
`Decision-makers` lines against Constitution Inviolable #2 (`../CONSTITUTION.md:28`, before this
ADR's change), which reads that `docs/` — among other framework trees — "must contain no real
user names, client identifiers, personal email addresses, real domains, or sensitive numbers".
Measurement showed the tension is a property of the whole `docs/adr/` corpus, not of the one
document: 16 occurrences of one first name and 9 of a second across `docs/adr/*.md`, both real
people (the repository owner and an external reviewer), present since long before that session —
ADR-0014 added to the pattern, it did not start it (`ADR-0014-documentation-namespace.md:419-426`).
ADR-0014 recorded the question under "What this ADR does not decide" rather than settle it there,
because anonymising one document only would have made it the sole inconsistent member of the
corpus. This ADR is the item (CCP-1157) filed to own that question, and it settles it.

### `docs/adr/` is in scope of the Inviolable; the corpus convention is authorship, not leakage

`docs/adr/` is one of the five entries `scripts/lib/docs-framework-allowlist.txt` allowlists for
distribution (ADR-0014, decision 1), so it is squarely inside the trees Inviolable #2 names — this
is not a question of whether the rule applies, only of what "real user names" means inside it.

Every ADR in this repository's corpus carries a `**Decision-makers:**` line by convention
(`templates/ADR_TEMPLATE.md:152` prescribes it; measured via `grep -n "Decision-makers"
docs/adr/*.md`: all fourteen ADRs preceding this one carry one, several also naming an external
reviewer by first name and handle). That convention is deliberate authorship attribution, not
accidental data leakage: this repository already records who decided what through git commit
authorship and through the `Decision-makers` line itself, on the same footing as any other
version-controlled project that credits its contributors by name in its own history.

### Finding (2) of CCP-1157, corrected before this decision was reached

CCP-1157 also asked whether `scripts/artifact-gate.sh` can detect a bare first name at all — a
guard that has never fired against the class its own Inviolable names is unproven. A later
comment on the item corrected the original framing: the gate's deny-list mechanism does detect
names. An isolated probe via `CCPR_GATE_DENY_NAMES` (the documented environment override,
`scripts/artifact-gate.sh:14-16`), run against the real tree with no change to the personal
config, found a control word occurring nowhere in the tree producing 0 findings over 353 files
scanned, and a word that does occur in the tree producing 87 findings across 54 files, both runs
redacting the matched text in their output. The corpus reports zero findings over `docs/adr/`
because the three entries currently configured in `gate.denyNames` are 10, 11 and 17 characters
long — none the length of a bare first name — not because the mechanism cannot match one. The
gate is proven able to find names; a bare first name is simply not on the list it is asked to
find, and `gate.denyNames` is a personal, non-distributed configuration
(`scripts/artifact-gate.sh:13-17`), not a repository artifact this ADR can amend.

## Decision

### 1. A bare first name does not fall under "real user names" in Inviolable #2

Repo owner decision, 08.09.2026, reasoning translated from the original German: *"The first
names are not critical. We are already listed and named as authors, too."* Authorship is wanted
and disclosed in this repository — the `Decision-makers` line of every ADR is exactly that, on
the same footing as git commit authorship, not a leak the Inviolable was written to prevent.

The reading is narrow and does not extend by implication: it covers a **bare first name** used in
an authorship or attribution role (a `Decision-makers` line, a `Status` line crediting a
reviewer, prose that credits a contributor by first name). It says nothing about a full name, a
handle, a personal email address, a client identifier or a real domain — Inviolable #2 names
those separately and this ADR does not touch that wording.

### 2. The Inviolable's text is unchanged; a reference to this reading is added instead

Repo owner decision, 08.09.2026: the reading belongs in a **new ADR**, which carries the
reasoning and the measurement, **and** `../CONSTITUTION.md` gets a **reference** to it from
Inviolable #2 — in the same `*Reference:*` form the other Inviolables already use. Neither
alone was judged sufficient: an ADR nobody is pointed to from the rule it interprets does not
help the next reader of the Constitution, and a Constitution line with the reasoning folded into
it has no room for the corpus measurement above. The Inviolable's prohibited-category list is
**not edited** — no Inviolable changes in substance, a previously unspoken reading of one is
written down.

### 3. The fourteen ADRs preceding this one are not rewritten

ADRs are protocols: they record a decision as of a date and are not rewritten retroactively (the
same protocol-vs-living-document line settled for `CONSTITUTION.md`'s own changelog in CCP-1152).
Editing the `Decision-makers`/`Status` lines of ratified ADR text would be an act on that
protocol, not on a living document, and doing it to fewer than all of them would produce exactly
the single-inconsistent-document outcome ADR-0014 declined to create. With decision 1 settled,
no rewrite is needed: the corpus was never in violation under the reading this ADR records.

### 4. `scripts/artifact-gate.sh` gets a comment recording this scope decision, not a behaviour change

CCP-1157's acceptance asks that if bare first names are deliberately out of scope, that decision
is written down at the gate itself rather than left as silence. A comment is added to
`scripts/artifact-gate.sh` stating that bare first names are deliberately not a target of its
deny-list check, pointing to this ADR. The deny-list mechanism itself — pattern matching,
`gate.denyNames` loading, redaction — is unchanged; whether to add a contributor's name to that
personal, non-distributed list remains a choice for whoever maintains it locally, not something
this ADR mandates or forecloses.

## Consequences

**Positive.** The fourteen ratified ADRs stay exactly as they are: no retroactive edit, no
document singled out for inconsistent anonymisation. The `Decision-makers` authorship convention
keeps working as designed. The question ADR-0014 deliberately deferred is closed, and closed
where a reader of the Inviolable can find it — Inviolable #2 now points at the ADR that explains
why a bare first name is not inside its scope, rather than leaving that scope to be inferred.
CCP-1157's second finding — that the gate had never been proven against the class its Inviolable
names — is also closed on the record: the gate is shown able to match names generally (the
isolated probe), and the reason `docs/adr/` reports zero findings is now a documented scope
decision rather than an unexplained gap a future reader might mistake for a defect.

**Negative.** Inviolable #2's own text still reads, on a first pass and without following the
`*Reference:*` pointer, as covering any real name including a bare first name — the correction
lives one hop away from the rule itself, and a reader who does not follow the reference can still
reach the wrong conclusion. The boundary this ADR draws — bare first name in an authorship role,
versus a fuller identifier — has no bright syntactic line: an unusual first name that is de facto
identifying on its own, or a first name paired with a distinctive role description, sits close to
the boundary and is not litigated here. And the reading depends on context (authorship
attribution) that this ADR names but does not encode anywhere a tool could check; nothing
mechanical distinguishes "a first name crediting a decision" from "a first name that leaked".

## Alternatives considered

**Anonymise the corpus — replace first names with role nouns (e.g. an "external reviewer" /
"repo owner" form).** Rejected: it is the retroactive rewrite decision 3 declines to make, for
the same reason ADR-0014 declined it for itself — applied to fewer than all fourteen ADRs it
creates exactly one inconsistent document, and applied to all of them it rewrites ratified
protocol text that decision 3 holds is not this ADR's, or any later one's, to edit.

**Record the reading only in the Constitution's Changelog entry, with no new ADR.** Rejected by
the repo owner's second decision: the Changelog is protocol prose describing what changed release
to release, not a place to carry the corpus measurement and reasoning a future reader would need
to re-derive the scope from scratch.

**Record the reading only in an ADR, with no Constitution reference.** Rejected for the mirror
reason: a reader who opens `../CONSTITUTION.md` and reads Inviolable #2 directly has no way to
discover that a scoping ADR exists at all.

**Extend `gate.denyNames` (or the gate's default matching) to flag bare first names.** Rejected:
doing so would fight the very reading this ADR just adopted — a mechanism that flags exactly the
class just declared in scope for authorship would keep reporting `docs/adr/`'s Decision-makers
lines as findings. Whether to add a *specific* contributor's name to that personal,
non-distributed list for an unrelated reason (a tenant/project identifier that happens to also be
someone's first name) is unaffected and stays a local configuration choice.

## What this ADR does not decide

- **Whether fuller identifiers — full names, handles, personal email addresses, client
  identifiers, real domains — fall under Inviolable #2.** They already do, explicitly, by the
  Inviolable's own wording; this ADR narrows only the bare-first-name reading and leaves the rest
  of the category list untouched.
- **Whether any contributor's name should be added to `gate.denyNames`.** That list is a
  personal, non-distributed configuration (`scripts/artifact-gate.sh:13-17`); this ADR neither
  requires nor forbids adding a name to it for a reason unrelated to the authorship convention
  decided here.
- **Whether this reading extends to a CCPR-driven project's own project-level constitution.**
  `../CONSTITUTION.md`'s own Scope note binds CCPR itself, not the constitutions `/constitution`
  generates for downstream projects; this ADR does not reach those.
