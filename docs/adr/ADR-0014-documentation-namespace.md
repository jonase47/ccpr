---
kind: adr
adr_id: ADR-0014
adr_status: accepted
status: active
last_updated: 05.09.2026
related:
  - ADR-0012-derived-values-are-not-stored.md
  - ../CONSTITUTION.md
  - ../../templates/PHASE_DOC_SCHEMA.md
verified: 05.09.2026
verified_against: ticket/CCP-1150 working tree (05.09.2026)
owner: repo-owner
---

# ADR-0014: The documentation namespace — `docs/` stays framework, humans get `handbook/`

**Status:** Accepted (04.09.2026); post-hoc review by Olli pending — see Deferred review items.
**Decision-makers:** Repo owner (Jonas)

## Context

### Two documentation trees, and only one of them has a defensible name

This repository carries two documentation trees with two different jobs.

`docs/` is the **framework namespace**: the directory CCPR's own tooling owns, in this
repository and in every project CCPR drives. `install.sh:43` lists it among the six framework
entries (`FRAMEWORK=( agents commands docs hooks scripts templates )`);
`scripts/phase-docs-lint.sh:61` walks nine phase folders under it; `scripts/memory-lint.sh`
scans `docs/memory/**`; `scripts/lib/docs-framework-allowlist.txt` draws the boundary between
what ships out of it and what does not.

`Manual/` is the **human handbook**: prose a person reads to understand the system —
`GETTING_STARTED.md`, `SYSTEM_OVERVIEW.md`, `WORKITEMS.md`, the `system/` chapters. It is not
installed at all: `install.sh` contains **zero** occurrences of `manual` in any case
(measured 05.09.2026 with the pattern `[Mm]anual`), and `Manual` is absent from the
`FRAMEWORK` list at `install.sh:43`.

The names do not say any of that. `Manual/` is capitalised, singular, and reads as a product
noun rather than a directory role; `docs/` is the name every developer reaches for when they
want to write documentation, and the framework has already taken it. The result is a standing
ambiguity that costs a sentence of explanation every time either tree is named, and that has
already produced at least one wrong statement of fact in the documentation standard itself —
see below.

### A measured correction: `docs/` is not "the runtime docs"

The documentation standard describes `docs/` as the framework's runtime documentation. That is
wrong, and the ratio is not marginal.

**Exactly five entries under `docs/` are installed** — `adr/`, `logo/`, `CONSTITUTION.md`,
`NEXT_STEPS_REFERENCE.md`, `PROJECT_PHASES.md` — declared once in
`scripts/lib/docs-framework-allowlist.txt:19-23`, which is the single source of truth for both
sides of the boundary (`install.sh` copies exactly those; `artifact-gate.sh` fails a newly
tracked `docs/` path that is not among them; WI-0018 / CCP-1017). The set is pinned as a set by
`scripts/tests/test_install_docs_boundary.py:198`.

**And what "everything else" means depends on which set you count — an index and a filesystem
are two sets, and both readings are load-bearing.** Measured 05.09.2026:

| Set | Instrument | Result |
|---|---|---|
| **Tracked** (the git index) | `git ls-files docs \| wc -l` | **20** files — and **all 20** lie inside the five installed entries (13 ADRs, 4 logo assets, 3 top-level files). **Zero** tracked files under `docs/` fall outside them. |
| **On disk** (the filesystem) | `find docs -type f \| wc -l` | **274** files (this ADR included, before it was committed). 21 are the framework documents themselves (14 ADRs, 4 logo assets, 3 top-level files); one further file, `docs/logo/.DS_Store`, sits physically inside the allowlisted `logo/` entry (follow-up 5). The remaining ~252 are ignored working state. |

The ignored bulk is `docs/HANDOVER.md`, `docs/.handover-archive/`, `docs/decisions/`,
`docs/workitems/`, `docs/memory/`, `docs/workitems-idmap.yml` and the broad `docs/.*` dotfile
rule, all listed in `.gitignore:34-36,65-66,73,106`.

So the corrected sentence has two halves, and which one applies depends on who is asking:

- **In a working machine, `docs/` is a working-state directory with five shipped exceptions.**
  This is the reading that governs the install boundary, because `install.sh` and the allowlist
  read the **filesystem**, not the index (`.gitignore:63-64,88-94`) — which is why an ignored
  file inside an allowlisted directory still ships.
- **In a clone, the inverse holds: `docs/` is 100 % shipped framework**, and every working-state
  file under it is untracked. This is the reading a contributor gets when they ask "what is
  `docs/` in this repository".

Either way, `docs/` is not "the runtime docs", and the claim has to be corrected wherever it is
written — a reader who believes `docs/` is uniformly shipped content will reason about the
install boundary with the wrong set.

The numbers above are of different kinds and are recorded as such (ADR-0012). *Five* is
derivable from `docs-framework-allowlist.txt`, and *20 of 20 tracked files inside it* is
derivable from the index against that file; cite the source, not this sentence. *274 / 21 /
~252* is a dated observation of a working tree that changes daily — it is here to establish an
order of magnitude, not as a register anyone is expected to maintain.

### What forced the decision now

Documentation standard v0.7 introduces three frontmatter reliability fields — `verified`,
`verified_against`, `owner` — and a lint check `(d)` that enforces them.
`templates/PHASE_DOC_SCHEMA.md:172-174` already reserves the letters `(d)` and `(e)` for
exactly this, and says so in the shipped file: *"(d) and (e) are reserved by documentation
standard v0.7 for the frontmatter reliability fields, which are not built yet. Do not renumber
(f) to close it."*

A mandatory frontmatter field needs a **named tree** it is mandatory in. Naming that tree is
not possible while the tree's own name is the thing under dispute, and `docs/` — which carries
its own frontmatter world of `kind:` / `parent_index:` / `phase:` / `subskill:` and five
allowlisted files with schemas of their own — is precisely the tree the answer must not be.
So the namespace question has to be settled before the fields can be, and the fields are what
made it urgent.

Two of the three fields are genuinely new to this repository. Measured 05.09.2026: `verified:`
has **zero** occurrences anywhere in the tree at any indentation, and `verified_against` has
**zero** occurrences of the bare string. `owner:` is **not** new — it appears three times at
line start, all of them in the work-item world (`Manual/WORKITEMS.md:166`,
`scripts/tests/test_workitems_cli.py:24`, `scripts/tests/workitems/test_local.py:31`), where it
means *who has claimed this item* (ADR-0005's claiming protocol). See decision 2's note on the
homonym.

## Decision

### 1. `docs/` stays the framework namespace. Human documentation is `handbook/`, in every repository, with no exceptions.

The install boundary is unchanged: `install.sh:43`'s `FRAMEWORK` list keeps `docs`,
`docs-framework-allowlist.txt` keeps its five entries, `artifact-gate.sh` keeps failing an
unlisted newly-tracked `docs/` path. Nothing about what ships changes.

What changes is the name of the human tree: **`Manual/` becomes `handbook/`**. Lower-case,
because it is a directory and every other top-level directory in this repository is lower-case
(`agents/`, `commands/`, `hooks/`, `scripts/`, `templates/`, `docs/`, `instincts/`). A common
noun, because it describes a role rather than announcing a product. And the same name in
**non-CCPR repositories too**, so that the convention has no exception a reader has to
remember: wherever CCPR's conventions are followed, `handbook/` is where a human reads and
`docs/` is where the framework works.

The cost of the exception-free form is stated rather than hidden: a repository that has never
heard of CCPR and simply wants a place for prose is being asked to use a name it did not
choose, for a reason that lives in another project. That is accepted because the alternative —
"`handbook/` in CCPR-driven repositories, whatever you like elsewhere" — is a rule with a
boundary nobody can locate, and a rule whose scope has to be looked up is a rule that gets
applied by guess.

### 2. The mandatory tree for the reliability fields is `handbook/`. Named concretely, so nobody has to infer it.

`verified`, `verified_against` and `owner` become mandatory frontmatter in **`handbook/`**
(after the rename), and nowhere else. Specifically and by name:

| Tree | Reliability fields | Why |
|---|---|---|
| `handbook/**` | **Mandatory** | The human handbook is the tree whose claims a person acts on without re-deriving them. It is the whole subject of the fields. |
| `docs/<phase>/**`, `docs/memory/**` | **Not mandatory** | The framework namespace, with its own frontmatter world (`phase`/`subskill`/`status`/`last_updated`, `kind`/`parent_index`, the memory schema's `name`/`description`/`type`). Adding a third schema on top of two that already collide (`status` vs. `adr_status`, WI-0128) buys nothing and creates a fourth field-name conflict to police. |
| The five allowlist entries (`docs/adr/`, `docs/logo/`, `docs/CONSTITUTION.md`, `docs/NEXT_STEPS_REFERENCE.md`, `docs/PROJECT_PHASES.md`) | **Not mandatory** | Each already carries its own schema — the ADR frontmatter (`kind`/`adr_id`/`adr_status`/`status`/`last_updated`/`related`), the constitution's (`kind`/`status`/`version`/`last_updated`), and two reference documents that carry none. |

Stated plainly, because this is the sentence a future argument will turn on:
**`PROJECT_PHASES.md` does not need a `verified:` field.** Neither does any ADR, including this
one — see decision 4.

This scope is not only prose. Check `(d)` lives in `scripts/manual-lint.sh`
(`templates/PHASE_DOC_SCHEMA.md:172-174`), and that script is generic over a single root
argument — `ROOT="${1:-$(pwd)}"`, `scripts/manual-lint.sh:61` — which
`scripts/check-all.sh:453` supplies as one path. The check therefore *cannot* reach `docs/`
without someone deliberately pointing it there. The scope decision is enforced by where the
check is aimed, not only by this table.

**The `owner:` homonym, recorded so nobody unifies the two by accident.** `owner:` already
means *who has claimed this work item* in the work-item frontmatter
(`Manual/WORKITEMS.md:166`, ADR-0005). In `handbook/` it means *who is accountable for this
page's accuracy*. The two document worlds do not overlap — work items do not live in the
handbook — so the collision is a homonym, not a conflict. It is written down here because the
next person to notice two `owner:` fields will otherwise assume one of them is a mistake, and
"unify them" is the wrong repair.

### 3. The Warning → Error switch is mechanical, not procedural.

Check `(d)` cannot be introduced as an error on day one: on the day it ships, no document in
`handbook/` carries the fields, so every file would fail at once. The obvious sequencing —
"warn now, and once coverage is complete somebody edits the script to escalate" — is rejected.
A manual switching step is a step that can be left undone, and the failure mode is silent: the
check keeps warning, warnings keep being ignored, and nobody notices that the thing which was
supposed to become binding never did.

**The requirement:** check `(d)` **evaluates the completeness condition itself** and reports
`warning` while the condition is unmet and `error` once it is met. Escalation is a *state* the
check computes, not a rebuild action a human performs. **No human switching step sits between
"coverage is complete" and "the check is binding."**

*How* that is realised is deliberately left to the session that builds check `(d)` — whether
the script evaluates the condition inline on each run, or reads a signal a test maintains, is
an implementation detail with real trade-offs (cost per run against an extra moving part) that
should be decided against the code, not here. What is binding is the absence of the human step,
and the fact that a reader can tell from the check's own output which state it is in and why.

One consequence follows and belongs to whoever builds it: a check whose severity depends on a
computed condition has **two** behaviours to prove, and a test that only ever sees one of them
has verified half a check. Both directions need to be seen failing before `(d)` counts as
accepted.

### 4. ADR-0014 carries the reliability fields itself — voluntarily, as a worked example.

This document's own frontmatter carries `verified`, `verified_against` and `owner`. It is the
first document in this repository to do so.

**And by decision 2 it is not required to.** `docs/adr/` is outside the mandatory scope. This
ADR carries the fields as a *worked example* of the migration path it describes — an ADR about
mandatory frontmatter fields that satisfies its own is the cheapest available demonstration of
what the fields look like in a real document. It is not evidence that `docs/` is in scope, and
a later reader must not read it back that way.

No other existing document is given the fields in this cut. The migration is the handbook's,
and it belongs to the cut that builds check `(d)`.

**Field semantics, as this document uses them — and this table is a reconstruction, not a
quotation.** Documentation standard v0.7 names the three fields; the meanings below were derived
from the field names plus `templates/PHASE_DOC_SCHEMA.md:172-174`'s reservation of checks
`(d)`/`(e)`, by someone who had not read v0.7 itself. They are written down so that v0.7 can be
read back against them and the differences seen, not because they are authoritative. Where v0.7
says something else, v0.7 wins and this table is the thing that gets corrected.

| Field | Meaning | Form |
|---|---|---|
| `verified` | The date on which this document's factual claims were last checked against the thing they describe. Not the date the file was edited — that is `last_updated`. | `DD.MM.YYYY` |
| `verified_against` | The identifier of the state the check ran against. A commit SHA is the preferred form. | A commit SHA, or — as here, for a document written before its own commit exists — a branch plus date, which a reader can tell apart from a SHA at a glance. |
| `owner` | Who is accountable for this document's accuracy. A role, not a person, so the field survives a handover. | A role slug (`repo-owner`) |

### 5. This ADR decides the rename. It does not perform it.

Not one file is moved, renamed or re-linked by this cut. The rename `Manual/` → `handbook/` is
its own change, with its own review, carrying the risk register below. That separation is
deliberate: a decision and a 100-plus-site sweep reviewed together are reviewed as one thing,
and the sweep is the half that gets skimmed.

## Option (b) assessed: the framework vacating `docs/` into `.ccpr/`

The alternative shape is the mirror image: leave `docs/` to humans everywhere and move the
framework's own namespace into `.ccpr/` — `.ccpr/architecture/`, `.ccpr/memory/`,
`.ccpr/CONSTITUTION.md`, and `~/.ccpr/` as the install target. It is assessed here rather than
listed among the alternatives below, because it is the only option that would have made this
ADR's opening complaint disappear instead of routing around it, and because the window in
which it is affordable is closing.

**What it would buy.** A namespace split that needs no explanation: everything under `.ccpr/`
is machine-owned, everything under `docs/` is the project's own, in CCPR and in every consumer
project. The `docs/` boundary allowlist would have no boundary left to draw. And the name
`docs/` would go to the thing every developer already expects to find there.

**Why the window is closing, explicitly.** Pre-1.0 is the only affordable moment for this move.
`docs/CONSTITUTION.md:47` makes "stable interfaces and a defined upgrade path" the criterion
for declaring CCPR stable at v1.0, with a `0.x` public beta shipping earlier under flagged
rough edges. Before v1.0, a namespace move is a rough edge among rough edges. After v1.0 it is
a breaking change to every adopter's repository layout, requiring a major version and a
migration every adopter has to run. There is no third moment.

**Why it is rejected anyway.**

1. **The cost is not paid here. It is paid in repositories this project does not control.**
   This is the decisive asymmetry, and it is the difference between the two renames. Renaming
   `Manual/` → `handbook/` touches only files inside this repository: `install.sh:43` never
   shipped `Manual/`, so no installed CCPR and no consumer project has a `Manual/` to migrate.
   Moving `docs/` → `.ccpr/` renames **the consumer's own tree**: every project ever built with
   CCPR carries `docs/architecture/`, `docs/planning/`, `docs/memory/`, `docs/HANDOVER.md`.
   `docs/CONSTITUTION.md:31` requires an ADR *and a documented migration path before the change
   is merged* for any change that invalidates existing artifacts. For `handbook/` that path is
   one `git mv` in one repository. For `.ccpr/` the path has to execute in repositories on
   schedules this project does not set. A migration script can be shipped; that anyone runs it
   cannot be guaranteed, and a migration nobody runs is a migration path only on paper.

2. **The in-repository cost is also large, and larger than it first measures.** Measured
   05.09.2026: **370 lines across 160 files** name one of the four framework `docs/` paths
   (`docs/PROJECT_PHASES.md`, `docs/NEXT_STEPS_REFERENCE.md`, `docs/CONSTITUTION.md`,
   `docs/adr/`, `docs/logo/`). That pattern deliberately does **not** reach references to
   `docs/<phase>/…` — `docs/architecture/`, `docs/planning/`, `docs/memory/` — which are the
   bulk of the namespace's actual surface, nor `~/.claude/docs/` written generically. The real
   number is materially higher; 370 is a floor, and it is already an order of magnitude above
   the `handbook/` sweep.

3. **A dot-directory is the wrong shape for something humans are supposed to read.** The
   framework namespace holds `CONSTITUTION.md` and every phase document — artifacts a person
   opens, edits and reviews. Dot-directories are hidden by default in file browsers, in `ls`,
   and in many editor trees. This repository already uses a leading dot under a doc root to
   mean *volatile, not content*: `.gitignore:106` ignores `docs/.*` wholesale for exactly that
   reason. Moving the framework's readable content into a dot-directory inverts a convention
   this repository is currently relying on.

4. **The name being freed is not the name that is wanted.** The reason to vacate `docs/` would
   be to give human documentation a good home. `handbook/` *is* a better name for a human
   handbook than `docs/` — it says what the tree is, where `docs/` says only that it contains
   documents. Paying a cross-repository migration to acquire a vaguer name is the wrong trade
   even before the migration's cost is counted.

**The weakness in this reasoning, stated rather than smoothed over.** Argument 4 assumes
adopters will accept `handbook/` as natural. If they instead keep creating a `docs/` of their
own, find it occupied by the framework, and have to be told about `handbook/` every time, then
the confusion this ADR set out to remove has been relocated rather than removed — and by the
time enough evidence exists to say so, the pre-1.0 window will have closed and the remedy will
be a major version. That is the risk this decision accepts. It is why the naming choice and
this assessment are both listed as deferred review items, and why the review should happen
while the window is still open rather than after.

**What option (b) would *not* have fixed, and (a) does not fix either.** `.gitignore:50-56`
records a dated, measured finding: because a single allowlist serves both sides of the boundary,
"tracked but not shipped" is not expressible today — the eight flat Tier-1 memory files fail
the gate's docs-boundary check, and the note itself calls the fix "an ADR-sized change".
Neither (a) nor (b) addresses that. It is a property of the one-list design, not of the name.
Recorded here so this ADR is not read as having solved it. The cheap fix — splitting the
allowlist into two lists — is listed under Alternatives below and moves no namespace at all.

## Rename risk, measured — for the cut that performs it

Measured 05.09.2026 with the ripgrep-backed search tool. Three patterns were used, and the
difference between them is itself a finding.

- **P1** `Manual/` — the path form.
- **P2** `\bManual\b` — the word form; catches prose references written without a slash.
- **P3** `["']Manual["']` — a quoted path *segment*, the shape a language runtime builds a path
  from.

**Nothing in the install or gate boundary references the directory.** Measured with `[Mm]anual`,
a superset of all three patterns:

| Location | Occurrences | Note |
|---|---|---|
| `install.sh` | **0** | And `Manual` is absent from `FRAMEWORK=( agents commands docs hooks scripts templates )` at `install.sh:43`. |
| `.gitignore` | **0** | |
| `settings.json` | **0** | |
| `scripts/lib/docs-framework-allowlist.txt` | **0** | Read in full; the file is 24 lines. |
| `hooks/` | 2 | Both the English word — `agent-monitor.py:254` ("manual experiment"), `:411` ("manually"). Zero path references. |
| `scripts/artifact-gate.sh` | 1 | `:460`, the string `scripts/manual-lint.sh` — a script *filename*, which does not change. Zero path references. |

**Five sites in three files do break mechanically, and the naive sweep finds none of them.**
This contradicts the "nothing mechanical breaks" reading the work item started from, and it is
the most important line in this section:

1. `scripts/check-all.sh:453` — `manual-lint) invoke_args=("$PROJECT_DIR/Manual") ;;`. A live
   path argument. After the rename the catalogued `manual-lint` check runs against a directory
   that does not exist. **Measured 05.09.2026 — a missing root exits 0**, and that is the whole
   problem; see the next subsection. This must move in the same commit as the rename.
2. `scripts/tests/test_doc_counts_agree.py:93,96,97` —
   `REPO_ROOT / "Manual" / "README.md"`, `… / "SYSTEM_OVERVIEW.md"`, `… / "SECTIONS_COMMANDS.md"`.
   Three live paths in the module that derives documented counts from the repository.
3. `scripts/tests/test_memory_lint_checklist_binding.py:53` —
   `REPO_ROOT / "Manual" / "system" / "memory-instincts.md"`. A live path.

**None of the five is reached by P1.** Site 1 has no trailing slash; sites 2 and 3 assemble the
path segment by segment, so the literal `Manual/` never appears. A sweep run on P1 alone would
have shipped the rename with five broken call sites and a green-looking search. The lesson for
the executing cut: the path form is not the search, it is one of at least three.

### A missing root exits 0 — the rename can switch the linter off and leave the gate green

Measured 05.09.2026, and it is the single most consequential thing in this section:

```
$ bash scripts/manual-lint.sh handbook
manual-lint: root 'handbook' does not exist        (stderr)
Files scanned: 0
Exit: 0
```

The stderr line names the problem; the **exit code does not**. Two consequences the executing cut
inherits, recorded here so it does not have to rediscover them:

**(a) The obvious acceptance criterion cannot fail.** `bash scripts/manual-lint.sh handbook`
reports exit 0 whether or not the rename happened — before the work and after it. A check that
is as green beforehand as afterwards measures nothing (ADR-0010 §4: a run that reports no scope
is not a pass). The acceptance must assert a **non-zero file count** alongside the exit code
(`Files scanned: 23` today), plus the separate grep proof for `commands/`, `README.md`,
`agents/` and `.github/` — none of which the lint reaches at all.

**(b) `scripts/check-all.sh:453` is load-bearing, not a comment.** It invokes `manual-lint` on
the hard-coded `"$PROJECT_DIR/Manual"`. After the rename that path is gone, the check exits 0,
the baseline (`check-all.baseline.tsv:55`, `manual-lint 0`) expects 0, and the run reports
**"match"**. The rename would silently switch the linter off inside the project's own gate while
the gate stays green — the exact failure shape this repository's checks exist to prevent, arriving
through a rename rather than through a code change. `check-all.sh:453` therefore belongs in the
**same commit** as the `git mv`, not in a follow-up sweep with the misleading comments in
`scripts/`.

**The expensive part is not breakage, it is reach.** These sites do not fail; they quietly point
at nothing.

| Location | Occurrences | Pattern | What it is |
|---|---|---|---|
| `commands/` | **31** across 16 files | P2 (P1 finds 29 — the two extra are `cleanup.md:168` and `:177`, prose without a slash) | Agent reading instructions ("read `Manual/WORKITEMS.md`"). No parser breaks; the agent reaches into nothing and continues. |
| `README.md` | **35** | P2 | The adopter's first document. |
| inside `Manual/` itself | **7** across 6 files (P1); P2 finds 8 lines across 6 files, adding `Manual/README.md` and `system/memory-instincts.md` | P1 + P2 | Absolute self-references: `system/anchored-state.md:365`, `system/file-structure.md:12`, `system/phases-gates.md:33`, `SYSTEM_OVERVIEW.md:843,935,939` (×2). |
| `scripts/` | **43** across 13 files (P1) | P1 | Comments and docstrings, now misleading. Note the line-vs-occurrence gap: a line-counting run reports 39. `scripts/manual-lint.sh` (6) and `scripts/tests/test_manual_lint.py` (10) are entirely commentary — that module explicitly never reads the real tree (`test_manual_lint.py:24-27`). |
| `agents/` | 1 | P2 | `agents/pentester.md`. |
| `.github/ISSUE_TEMPLATE/question.md` | 1 | P2 | `:9`. |

**Sites the work item's own list did not name, found by P2 and confirmed here:**
`CHANGELOG.md` (38 lines — **history; must not be rewritten**), `CLAUDE.md` (1), `BETA.md` (1),
`CONTRIBUTING.md` (2 — including `:191`, which names the `manual-lint.sh` contract),
`docs/CONSTITUTION.md` (2 — one is a `related:` entry at `:9`),
`docs/PROJECT_PHASES.md` (1), `templates/PHASE_DOC_SCHEMA.md` (4),
`templates/MEMORY_SCHEMA.md` (1), `templates/memory-sync.example.json` (1), and one line in each
of eight ADRs under `docs/adr/`. The ADR and CHANGELOG occurrences are records of past state and
should be left alone; the rest are live references.

**What these patterns do not reach, stated so the executing cut does not treat them as coverage:**

- A path assembled from a variable set elsewhere. None was found, but no search can prove their
  absence.
- Binary and non-text files, which the search tool skips by default.
- Anything outside this repository — a maintainer's installed `~/.claude`, a consumer project.
  Files ignored by version control *inside* this repository **are** included, because the search
  reads the filesystem.
- Case variants beyond `M`/`m`. `MANUAL` was searched separately: it occurs only as Python
  constant names (`MANUAL_README_PATH`, `MANUAL_LINT`), never as a directory.
- The lower-case script name `manual-lint.sh`, deliberately excluded from every path count. The
  script's name does not change; only the tree it is pointed at does.

## What this ADR does not decide

- **The migration schedule for the reliability fields inside `handbook/`.** Which pages get
  `verified:` first, and on what cadence, belongs to the cut that builds check `(d)`.
- **Whether adopter projects must follow the `handbook/` convention or merely may.** Decision 1
  states the convention has no exceptions *where CCPR's conventions are followed*. It does not
  make CCPR enforce it in a consumer's repository, and nothing shipped checks for a `handbook/`
  directory.
- **Ticket B stage 4** — the runtime-text sweep over `commands/`, `agents/`, `templates/`,
  `hooks/`. Scoped in the deferred review items below, not settled here.
- **Anything about `.DS_Store`, `assets/`, or the allowlist's filesystem-vs-index behaviour.**
  Noted in the follow-ups because the measurement passed over it, not decided.
- **Whether first names belong in a shipped ADR corpus at all.** This ADR's Status and
  Decision-makers lines name people, as every ADR here does — measured 05.09.2026: 16
  occurrences of one first name and 9 of another across `docs/adr/*.md`, with
  `artifact-gate.sh` reporting zero findings over that tree. The tension with
  `../CONSTITUTION.md`'s "no personal data in shipped artifacts" is therefore a standing
  property of the whole corpus, not something this document introduces, and anonymising this
  one ADR would make it the only inconsistent member of fourteen. Open, corpus-wide, and not
  this ADR's to settle.

## Consequences

**Positive.** The two trees get names that state their roles, and the ambiguity that cost a
sentence of explanation at every mention is removed at the source rather than documented around.
The reliability fields get a tree they can be mandatory in, named concretely enough that
"does `PROJECT_PHASES.md` need `verified:`?" has a written answer. The escalation of check `(d)`
has no human step in it, so the check cannot get stuck warning forever. The install boundary is
untouched — `install.sh:43`, the five allowlist entries and `artifact-gate.sh`'s `docs/` check
all keep working unchanged, and no installed CCPR or consumer project needs to do anything.

**Negative.** `docs/` keeps a name that misdescribes it, and this ADR chooses to live with that
rather than pay a cross-repository migration to fix it — a choice whose window closes at v1.0
and cannot be revisited cheaply afterwards. The rename that follows is over a hundred sites,
none of which fail loudly: an agent instruction pointing at `Manual/WORKITEMS.md` after the
rename reaches nothing and carries on, which is exactly the failure shape that is hardest to
notice. Five call sites in three files break mechanically, none of them visible to the obvious
search pattern, and one of them (`check-all.sh:453`) would take the project's own `manual-lint`
gate offline while the gate keeps reporting a match. And a fourth frontmatter schema now exists in a repository that already has
three, with `owner:` deliberately reused as a homonym of the work-item field — recorded, but a
reader still has to know which world they are in.

## Alternatives considered

**Rename `Manual/` to `docs/` and move the framework's tree somewhere else.** This is option (b)
in substance and is assessed in full above. Rejected there, with reasons and with the closing
window named.

**Leave `Manual/` as it is and only correct the "runtime docs" claim.** Rejected: it fixes the
false sentence and leaves the ambiguity that produced it. The capitalised, singular name is
what makes readers uncertain which tree is which, and a corrected sentence does not change a
directory listing.

**Lower-case `manual/` instead of `handbook/`.** Rejected: it collides in reading with
`manual-lint.sh` and with the adjective "manual" (as in "a manual step"), a word this
repository uses constantly in exactly the sense that must not be confused with a noun. The
search patterns in the section above would also stop being separable from prose.

**`documentation/` or `guide/`.** Rejected: `documentation/` is `docs/` spelled out and
reintroduces the collision this ADR exists to remove; `guide/` collides with the `project-guide`
agent and the `/guide` command.

**Make the reliability fields mandatory across `docs/` as well, for uniformity.** Rejected: the
framework namespace already carries two frontmatter schemas that have collided once
(`status` vs. `adr_status`, WI-0128), and the five allowlist entries carry a third. A third
mandatory triple over trees whose documents are largely machine-written buys accountability for
pages nobody reads as standing claims.

**Ship check `(d)` as a warning and escalate it by a later edit.** Rejected in decision 3: a
manual switching step fails silently, and its failure looks identical to the check working.

**Split `docs-framework-allowlist.txt` into two lists — tracked-but-not-shipped and shipped.**
Not rejected, and not decided here either: it is a different question that this ADR's Context
touched (`.gitignore:50-56`) and that neither namespace option addresses. Recorded so it is not
lost, and so nobody proposes a namespace move to solve it.

## Deferred review items

The documentation standard requires veto points to be findable in the artifact itself, not only
in a plan. These three are open and are recorded here to be found.

1. **The `handbook/` naming choice.** Decision 1 picks it over `manual/`, `documentation/` and
   `guide/` for reasons stated above, none of which is measured against a reader who has not
   read this ADR. Open to post-hoc veto before the rename cut executes.
2. **The assessment of option (b), the `.ccpr/` namespace — and note the closing pre-1.0
   window.** The rejection above is a judgement about migration cost in repositories this
   project does not control, not a measurement. **After v1.0 this move is no longer affordable**
   (`docs/CONSTITUTION.md:47`): it becomes a breaking change to every adopter's layout,
   requiring a major version and a migration each adopter has to run. If option (b) is to be
   reconsidered, it has to be reconsidered while `0.x` still ships flagged rough edges — this
   review item is therefore time-boxed by the release, not by a date.
3. **Ticket B stage 4 — the runtime-text sweep over `commands/`, `agents/`, `templates/`,
   `hooks/`.** 31 occurrences in `commands/`, 1 in `agents/`, 4 in `templates/PHASE_DOC_SCHEMA.md`
   and 1 each in two further template files are agent-facing *instructions*, not code. Whether
   they are rewritten in the rename cut or in a separate pass — and how the result is verified,
   given that none of them fails loudly — is not settled.

## Follow-ups

1. **The rename cut itself** performs `Manual/` → `handbook/` and inherits the risk register
   above, including the five mechanical sites in three files (`scripts/check-all.sh:453`,
   `scripts/tests/test_doc_counts_agree.py:93,96,97`,
   `scripts/tests/test_memory_lint_checklist_binding.py:53`) that the path-form search pattern
   does not reach — with `check-all.sh:453` in the same commit as the `git mv`, and an
   acceptance criterion that asserts a non-zero `Files scanned` rather than exit 0 alone.
2. **Check `(d)` is built** against decision 3's requirement — self-evaluating severity, no human
   switching step, both severity states seen failing before it counts as accepted.
3. **The "runtime docs" claim is corrected** wherever the documentation standard states it, using
   the numbers in this ADR's Context — and citing
   `scripts/lib/docs-framework-allowlist.txt` for the count of five rather than restating it
   (ADR-0012).
4. **`templates/PHASE_DOC_SCHEMA.md` will need rows for `verified` / `verified_against` /
   `owner`** once they are mandatory somewhere. It is the frontmatter schema register and does
   not describe them today; this ADR forward-declares the fields without touching it. Deliberately
   deferred to the cut that makes them mandatory, so the register never describes a field no
   check enforces.
5. **The allowlist is per top-level entry and reads the filesystem, not the git index**
   (`.gitignore:63-64,88-94`, measured 21.08.2026), so an ignored file inside an allowlisted
   directory still ships. Measured again 05.09.2026: `docs/logo/.DS_Store` exists on disk and is
   inside the allowlisted `logo/` entry. Not a namespace question and not fixed here; recorded
   because the measurement for this ADR walked past it.
