# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/) — see [docs/adr/ADR-0001-versioning-and-distribution.md](docs/adr/ADR-0001-versioning-and-distribution.md) for the version-scoping rules in this meta-repo context.

> Development before this public GitHub release happened in a private repository. This changelog starts fresh at the first public version; the detailed pre-public history is retained privately.

## [Unreleased]

### Fixed
- **`memory-lint.sh` excluded every `MEMORY.md` index from its checks, on a stated reason that
  turned out to be false (WI-0108).** The exclusion comment read "indexes have no frontmatter" —
  measured 26.08.2026 across the four reference stores this project draws on (ccpr-gh,
  productdata, Kalza, ccpr): 16 of 27 index files DO carry a frontmatter block, and none of those
  16 had ever been validated, because the `find` populating the checked-files list excluded every
  file literally named `MEMORY.md` regardless of its content.

  The eleven frontmatter-less indexes in that same census decided the shape of the fix: dropping
  the exclusion outright (the item's original framing) would have sent all eleven through the
  "no YAML frontmatter" check as an immediate `err` — eleven errors in files nobody wrote
  frontmatter for on purpose, the opposite of a fix. The rule this change implements instead is
  what `templates/MEMORY_SCHEMA.md` already said and the lint had never actually enforced:
  frontmatter on an index is **optional**, and **validated when present**. An index without one
  stays silent; an index that does carry one now runs the same field/date/cross-ref checks as any
  other memory file — required fields, the `type` enum (now including `index` as a legal value on
  both the Tier-1 closed enum and the Tier-2 open one), `last_updated` form/age, and `related:`
  cross-refs — with one deliberate exception: `docs/memory/MEMORY.md` itself stays exempt from
  the Tier-1 `{type}_{slug}.md` naming check, since it is the index, not a Tier-1 memory file the
  rule was written for.

  Removing the `-not -name "MEMORY.md"` clause from the shared `find` also put the index file
  itself into the same array check (g) walks to warn about Tier-1 files the index forgot to
  reference — without a guard, every project's index would have been required to reference its
  own filename inside its own body, which no index does. That guard is the one change in this fix
  that reaches outside the frontmatter checks proper; measured against this repository's own
  `docs/memory/MEMORY.md`, it is what keeps the lint's own 5-warning baseline at 5 instead of 6.
  `instincts.md` stays excluded from the same `find` — same shape, a different question,
  deliberately untouched here.

  The sibling exclusion in check (i) (Tier-2-global silo validation,
  `[[ "$gbase" == "MEMORY.md" ]] && continue`) was aligned the same way, for consistency rather
  than because it fixes anything measurable today: only one Tier-2-global index exists across the
  reference stores (`~/.claude/memory/kalza/MEMORY.md`), and it has no frontmatter, so this half
  changes zero findings in any store currently in use.

- **`phase-docs-lint.sh`'s empty-scope report read like a clean pass, and the generator commands it
  validates against prescribed values it then rejects (WI-0121).** The item was filed against a
  different claim -- five files "self-declaring" as phase docs while never being validated -- which
  was retracted on re-measurement: those "violations" sat inside fenced `yaml` example blocks, not
  real frontmatter, and a frontmatter parser found the only files carrying real `phase:` frontmatter in
  this repository are the six shipped `templates/QA_SKELETON/*.md`, all valid. What survived
  re-measurement was two smaller, real defects.

  **First, the same empty-scope trap WI-0090 fixed for `artifact-gate.sh`'s deny-list scope.**
  `bash scripts/phase-docs-lint.sh .` on this repository (which has no `docs/<phase-folder>/` yet)
  printed `Files scanned: 0` next to `0 errors, 0 warnings` -- a true sentence that reads as "every
  phase folder was checked and found clean". The exit code is unchanged and stays 0: an empty scope
  here is a *supported* configuration (a project before P3, or on the Lean-Track, has no phase
  folders yet), not an error, for the same Constitution "installable and runnable on a clean
  machine" Inviolable reason WI-0090 decided for artifact-gate.sh's default. What changed is the
  report: a companion `**Phase folders found:**` line now names which of the nine `PHASE_FOLDERS`
  actually exist (or, on a `--scope` run, its own glob already said so), and a run that collects zero
  files emits a notice on **stderr** -- naming the directory and the folder names it looked for --
  so a caller keeping stdout as its findings report cannot lose it. Unlike artifact-gate.sh, nothing
  here routes through a deny-list mask that escalates to `python3` on a non-ASCII byte, so the
  em-dash trap that check found does not apply to this script's summary line.

  **Second, three generator documents prescribed frontmatter values the validator's own
  `VALID_PHASES`/`VALID_STATUS` enums reject** -- `docs/PROJECT_PHASES.md`'s canonical "Detail file
  frontmatter" example (`phase: p0` lowercase; `status: complete` with a `# draft | complete |
  needs-rework` comment, all three of which are outside `VALID_STATUS`), `docs/adr/ADR-0009-...md`
  and a companion local working note (`phase: 3`, missing the `P` prefix), and three `commands/p4-*.md`
  detail-file examples (`status: active | partial | pending`, `status: living | complete`, and a
  comment naming `complete` again) -- so a document written by following one of these examples
  literally would fail the lint meant to accept it. `complete` has no direct counterpart in
  `VALID_STATUS`; `frozen` ("completed (phase passed Gate)" per `templates/PHASE_DOC_SCHEMA.md`) is
  the closest semantic match and is now used at every `complete` site. `p4-setup.md`'s
  `active | partial | pending` maps onto the existing `active`/`draft`/`skeleton` semantics instead
  (`partial` = in progress = `draft`, `pending` = not started = `skeleton`) -- a cleaner fit than
  repurposing `frozen` there. One value was deliberately left alone: `p4-sprint.md`'s
  `kind: risk-detail` block's `status: open | mitigated | accepted | closed` is the RISK lifecycle,
  not the document lifecycle -- a different axis that happens to collide on the field name.

  A new corpus test (`scripts/tests/test_frontmatter_examples_match_the_lint.py`) binds every fenced
  `yaml` frontmatter example under `commands/`, `docs/` and `templates/` to `phase-docs-lint.sh`'s
  own `VALID_PHASES`/`VALID_STATUS` -- read from the script's source text, never re-typed -- so this
  generator/validator disagreement cannot recur silently.

- **`artifact-gate.sh` could report a clean pass on a run where the check it is named after never
  executed (WI-0090).** The deny-list of tenant/project names comes from a personal, non-distributed
  config, so it is unset on every freshly installed CCPR — and on the machine where this was
  measured. On such a run the other checks did all the work and the summary said `scanned 296 files,
  0 findings in 0 files`, a true sentence that reads as "every check ran". The notice above it did
  say the deny-list was unconfigured, but it was printed on **stdout**, next to the findings:
  `artifact-gate.sh --repo . >/dev/null` printed nothing at all and exited 0 — byte-identical to a
  fully configured clean run redirected the same way.

  **The default was measured and kept.** Making an unconfigured deny-list fail by default was the
  first candidate and is the wrong answer here: the list is personal and non-distributed, so the
  Constitution's "installable and runnable on a clean machine" Inviolable makes running without it a
  *supported* configuration, not an error. Measured before deciding — flipping the default turns
  **101 of this repository's 1388 tests** red and contradicts the shipped CI template's documented
  default (`templates/ci/artifact-gate.ci.sh` ships `REQUIRE_DENYLIST=0` and promises the run "does
  not pass silently" rather than fail), which makes it a breaking interface change under ADR-0001
  rather than a style choice. `--require-denylist` remains the opt-in for callers that need the
  strict answer, and the reasoning is now written into the script's header, which is also its
  `--help` text.

  **What changed is the report.** The summary line now names the scope of *checks* as well as the
  scope of *files*: `scanned N files, F findings in D files; deny-list: K name(s) checked`, or
  `; deny-list check DID NOT RUN (no names configured)`. The count and never a name — a CI log is a
  shipped artifact too — which also lets an operator see that a five-entry list arrived as five. And
  the not-configured notice moved to **stderr**, the channel this script already uses for every
  other "the run could not do its job" line, so a caller that keeps stdout as its findings report
  cannot lose it. Two clean runs over the same file, one configured and one not, both still exit 0
  and are now told apart by their summary line.

  **Found by the existing suite while fixing it:** the first version of the summary line used an em
  dash like its neighbours. Every emitted line passes through the deny-list mask, which escalates to
  a `python3` subprocess as soon as either the line or the list carries a non-ASCII byte — so an em
  dash on a line that prints on *every* run started python3 on every run with a configured ASCII
  deny-list, and under a broken interpreter printed a Python fatal-error dump where an ASCII-only run
  is meant to be silent. The summary line is ASCII on purpose, with the reason recorded at the call
  site.

- **The Manual carried the Memory Lint checklist twice, and neither copy matched the script
  (WI-0104).** `Manual/SYSTEM_OVERVIEW.md` and `Manual/system/memory-instincts.md` held the same
  list by intent; the overview had fallen four bullets behind. Copying the four across would have
  restored parity for a day — `Manual/README.md` already declares `SYSTEM_OVERVIEW.md` a *slim
  index* over `system/` detail files, so the duplication was an unfinished split, not a design.
  The chapter is now the single documented list and the overview carries an orientation paragraph
  plus a `**Full chapter**` pointer, the same shape the `/anchor` section in that file already
  uses.

  **Counted in the script rather than inherited from the list.** `memory-lint.sh` runs **fifteen**
  checks — (a)–(n) plus (c2). Both registers named ten of them. Four were undocumented anywhere:
  the tier-aware `type` enum (c), the `last_updated` *form* check added by WI-0106 (e), the
  split-layout topic-file schema and size caps (l), and the archive-presence note (m); the
  project-root fallback in (f) and the two extraction limits in (n) were likewise unmentioned.
  Every bullet now names its check letter, so a sentence can be traced to the code block that
  implements it, and severities are stated — the old list said which checks existed but not which
  of them fail a run.

- **Three German words in shipped English Manual prose, each duplicated across an index/chapter
  pair (WI-0104, Constitution Inviolable "English in shipped content").** `# required, DD.MM.YYYY
  (optional " (Notiz)" suffix)` in both frontmatter examples now reads `DD.MM.YYYY or
  "DD.MM.YYYY (note)"`, matching `PHASE_DOC_SCHEMA.md`'s own wording. `architectural leitplanken`
  and `Lean-Vorlauf` in `SYSTEM_OVERVIEW.md` + `system/cross-cutting.md` are now `architecture
  guardrails from "inviolable"-tagged ADRs` and `Lean pre-run` — the terms `commands/constitution.md`
  itself uses, so the Manual stops describing a mode by a name the command does not have.

- **`SYSTEM_OVERVIEW.md` still taught the tier tiebreaker CLAUDE.md withdrew.** "When in doubt,
  prefer Tier 1 (visibility wins over isolation)" — the exact phrase removed from
  `commands/postmortem.md` under WI-0065 for leaking persona-specific patterns into the globally
  autoloaded file. The correction swept the skill and missed this copy, which is the same defect
  the item above is filed for, one section further on. Replaced with the reversed rule and a
  pointer to the full three-step decision order in `system/memory-instincts.md`.
- **`last_updated` accepted a trailing note that the memory schema never mentioned, and the two
  linters disagreed about which notes were legal (WI-0106).** `MEMORY_SCHEMA.md` specified
  `DD.MM.YYYY` and nothing else, yet ten files in this repository's own store append a note to the
  value — `24.08.2026 (WI-0102)`, `16.05.2026 (Note: agent migration verified later same day)`.
  They passed because `memory-lint.sh` never asked about the value's shape: it handed the raw string
  to `date`, and both implementations accept trailing text after the part they matched. The
  tolerance was therefore real but accidental, and invisible to anyone reading the schema — which is
  how it was rediscovered, as the collateral of a WI-0087 fix shape that would have turned all ten
  into hard errors.

  **Resolved by widening the schema, not the files.** The note says *why* the date moved — which
  round, which item — and that is context no other field carries; the practice is older than the
  rule and better than it. `MEMORY_SCHEMA.md` now specifies the form precisely enough to enforce:
  `DD.MM.YYYY`, optionally followed by whitespace and a single parenthesised group running to the
  end of the value. `PHASE_DOC_SCHEMA.md` had specified the same optional suffix for phase documents
  all along.

  **The tolerance is now checked rather than inherited.** `memory-lint.sh` check (e) matches the
  documented pattern — character-for-character the one `phase-docs-lint.sh` already used — before it
  parses the date, and keeps the parse behind it: the pattern says nothing about whether `32.13.2026`
  is a day, the parse says nothing about what follows the year. Measured across the four live
  inventories: 106 `last_updated` values in scope, 10 annotated, **0 outside the documented form**,
  and every report byte-identical before and after. This rejects nothing that exists today; it
  closes three shapes that were silently accepted here while `phase-docs-lint.sh` rejected them
  (`24.08.2026 a note without parentheses`, `24.08.2026(WI-0102)`, `24.08.2026 (unclosed`).

  **One divergence is left open on purpose.** A well-formed but impossible date (`32.13.2026`,
  `99.99.9999`) is rejected by `memory-lint.sh` and accepted by `phase-docs-lint.sh`, which has no
  date check beyond its pattern. Closing it would reject content that script accepts today — an
  ADR-0001 promotion decision, not the writing-down of an existing practice. Both scripts now say so
  at the check.

- **`phase-docs-lint.sh`'s `last_updated` tolerance was documented but not held by any test.**
  Measured against mutants of check (e)'s pattern: loosening the required space before the note,
  dropping the parentheses from the note group, dropping either anchor — all four survived the
  suite, because the one negative case it had (`2026-05-04`) fails under every variant. Four cases
  added; each kills one mutant. No behaviour change.

- **`memory-lint.sh` reported a file's age as a property of the clock, not of the file (WI-0087,
  rediscovered independently as WI-0103).** `date_to_epoch()` parsed `DD.MM.YYYY` with a BSD format
  string carrying no time component, and BSD `date` fills unnamed fields from the RUNNING wall clock.
  `TODAY_EPOCH` was captured once at script start, so the two sides of the subtraction held different
  times of day and their difference was short by the script's own elapsed runtime — after integer
  truncation, one day low. Measured on a live store before the fix: six consecutive runs over the same
  unchanged inventory reported `93/93/91` four times and `94/94/92` once, with nothing changed between
  them. On a store large enough to take a second to walk, the SAME run disagreed with itself: of 60
  files all 91 days old, 58 reported 90 and stayed silent.

  **The consequence was a silent false negative at exactly the threshold check (e) exists for.** A file
  genuinely `STALE_DAYS + 1` days old was reported as `STALE_DAYS`, the `>` comparison was false, and no
  warning fired. The check under-reported staleness; it never over-reported it.

  **And the two branches disagreed with each other.** The GNU fallback builds an ISO date, which `date -d`
  anchors on midnight, so the same file could warn on Linux and stay silent on macOS. Measured with GNU
  coreutils 9.11 in the script's own GNU path: `94/94/92` on every run, against a BSD path flapping
  between `93/93/91` and `94/94/91`.

  Both ends are now anchored at **UTC** midnight and derived through the same function, so the difference
  is an exact multiple of 86400 by construction. UTC rather than local midnight because two local
  midnights spanning a spring-forward are only 23 h apart, which reintroduces the identical off-by-one
  for every window crossing that transition — measured on both implementations: 01.01.2026 to 01.04.2026
  is 90 days and comes out as 89 when anchored locally. The BSD branch normalises in two steps rather
  than appending a time to the value, so that what counts as a parseable date is unchanged: both
  implementations accept trailing text after the date, ten files across the live stores are written that
  way, and the single-call form turns every one of them into a hard error (measured: 10 new errors, and
  this script moving from exit 1 to exit 2 on its own repository). Whether that tolerance should stay is
  filed separately as WI-0106.

  **This changes reported numbers, which is the point.** Across the four inventories the fix moves ages up
  by one where the old code truncated, adds and removes no finding, and leaves every exit code as it was
  (1/2/1/1). Six consecutive runs per inventory now produce identical reports (bar the report's own
  `**Run:**` timestamp line), and the BSD and GNU paths agree byte for byte on the same store.

  The suite could not have caught this: no test asserted a concrete age. Two now do, and neither adds a
  seam to the script. The first sizes its fixture so the defect reproduces rather than coin-flips; the
  second places the run in a time zone whose calendar day currently differs from UTC's — `TZ` is a plain
  POSIX variable, not something added to make the script testable — which is what pins "today" to the
  local calendar day at any hour of the day.

- **The dependency scan reported "clean" exactly when it found something (WI-0102).** Every external
  scanner `quality-scan.sh` drives shares one shape: it prints its full JSON report AND exits non-zero
  when it finds vulnerabilities. The `|| echo '{}'` arm therefore fired on the FINDINGS case, appending a
  second JSON document to a complete one; `json.load` died on "Extra data", and a bare `except: print(0)`
  turned the crash into a zero. Measured against a throwaway project pinning `minimist 0.0.8`: npm's own
  answer was `{critical: 1, total: 1}` with exit 1, the shipped chain's answer was `0`. Measured on
  `pip-audit 2.10.1` against `jinja2 2.10`: 6 vulnerabilities, exit 1, chain reported `0`. The wrong
  direction is the dangerous one — a zero reads as a clean bill, not as a failed measurement.

  **The count was wrong even when the chain worked.** `sum(meta.values())` added npm's severity buckets
  AND its `total` key, which holds their sum, so one critical advisory came out as `2`. On the Python
  side `len(json.load(...))` counted the report object's two TOP-LEVEL KEYS (`dependencies`, `fixes`), so
  a project with no vulnerabilities at all was reported as "2 Python vulnerabilities found" — a false
  alarm to go with the false all-clear. Both are now counted by what they claim to count: severity
  buckets only, and vulnerabilities summed per dependency (both pip-audit report shapes).

  **No silent fallback is left.** "the tool could not be evaluated" and "the tool found nothing" no longer
  produce the same number: an unusable report becomes a `scan-error` finding carrying the producer's own
  last stderr line, and a lockfile or manifest present with no scanner installed becomes a `scan-skipped`
  finding. Only a tool that ran and genuinely found nothing yields an empty findings list. A non-zero exit
  status outside the range each tool documents as "ran to completion" is a `scan-error` too, even when the
  report happens to parse.

- **`semgrep` findings killed the whole SAST scan whenever a rule message contained an apostrophe
  (WI-0102, found while measuring the above).** The merge step interpolated the semgrep findings JSON
  straight into Python source. Measured against real semgrep 1.174.0: the first rule it hits on a
  `subprocess(..., shell=True)` call is worded `Found 'subprocess' function 'call' with 'shell=True'`, the
  interpolated source failed to parse, `set -e` aborted the run — exit 1, no report written at all. Same
  apostrophe class as WI-0055, one function further down. No shell value is interpolated into Python
  source in this script any more: producers write to a file and the reader receives the PATH in `argv`.
  (semgrep's exit code itself was measured and is the benign one of the three: `--config=auto --json -q`
  exits 0 with findings. The same run with `--error` prints the same report and exits 1, so the shape was
  one flag away from breaking there too, and it is now handled either way.)

- **`set -e` never protected any scan function, on the bash this project pins (WI-0102).** Each scan is
  invoked as `results+=("$(scan_X)")`, and bash 3.2 — macOS `/bin/bash` — does not honour `set -e` inside
  a `$(...)` command substitution: measured, a failing command there aborts neither the function nor the
  script, and the outer run still exits 0. So the `# exit-status: exempt set-e-sufficient` justification
  did not hold inside these functions, and a crashed producer silently contributed nothing. The grep-based
  pattern pass now goes through the same reader as the external tools (a crash becomes a `scan-error`, not
  zero patterns), the report reader is called through an explicit `if !` check, and a scan function that
  produces no record at all now fails the run loudly instead of vanishing from the report.

  Also fixed in passing: a project with both a lockfile and a `requirements.txt` lost its npm findings,
  because both tools wrote the whole scan record to the same file and pip-audit clobbered npm's.

- **check (n) reported the target of a definition-shaped line that cannot open a definition — the last
  false positive in the corpus (WI-0096).** A link reference definition may not INTERRUPT a paragraph.
  With prose open above it, `foo` then `[ref]: dead.md`, the reference reads the second line as ordinary
  text, defines nothing and renders `<p>foo
[ref]: dead.md</p>`. check (n) reported `dead.md` anyway:
  `refmap` already declined to treat the line as a definition (WI-0093), but the REPORTING path was
  gated on nothing. Both now sit behind the same `pbuf_n == 0` gate. Pre-existing — `4f2ffa7` behaves
  identically — and pinned by a mutation that drops the gate and asserts the exact inverse behaviour on
  the same fixture.

  **Why WI-0085 stays** — the two are the same bytes and the opposite verdict, and the line between them
  is what the READER sees, not the syntax. `[ref]: dead.md` standing alone renders as NOTHING: the author
  declared a destination, the file is gone, and no reader will ever notice it. That is invisibly dead, and
  catching it is what check (n) is for, even where CommonMark renders no link at all (PO decision
  23.08.2026). The same line under an open paragraph renders as VISIBLE paragraph text: the path is prose
  on the page, not a pointer, and reporting it said something untrue about a line the reader can read.
  Both verdicts have their own corpus entry, and dropping either gate turns exactly one of them red.

  The `reflbl != ""` half of the same gate answers a third shape by the same rule, and it was measured
  rather than assumed: `[ ]: dead.md` (a label of nothing but whitespace) and `[]: dead.md` are no
  definitions either — a label needs one non-whitespace character — and both render as visible prose.
  `4f2ffa7` reported the whitespace one; the working tree already did not, through `reflbl != ""` and not
  through the paragraph gate. Measured both ways (removing one gate leaves the other shape silent) and
  now pinned by two corpus entries, where before it was an untested accident.

- **`tolower()` on a reference label answered differently depending on the process locale, and the
  harness measured the narrow answer (WI-0099).** Label matching follows the reference normalisation,
  which case-folds — and what `tolower()` does above 0x7F is a property of the LOCALE, not of this
  script. Under a UTF-8 locale `[ÄÖ]:` matched `[äö]` and agreed with the reference; under C/POSIX it did
  not and the enclosing link was reported. The test harness runs the script with a bare environment
  (`HOME` and `PATH` only), i.e. in the C locale, so the suite froze one answer while an interactive run
  gave the other.

  Fixed in two parts, because pinning the locale alone would only have made the wrong answer STABLE.
  (1) `LC_ALL=C` at the awk call site, in line with `artifact-gate.sh`, `memory-sync.sh` and
  `lib/discipline_gate.sh` — the byte-oriented answer is now the same everywhere. (2) A label carrying
  any byte >= 0x80 short-circuits to "resolves" without consulting `refmap` at all, so a non-ASCII label
  is never DECIDED by a folding that cannot fold it. The direction of that short-circuit follows from the
  shape of the caller and not from a sample of inputs: "resolves" only ever deactivates an enclosing
  opener, and the only `print` sits behind an active opener, so the branch can drop a finding and not
  invent one. The detection is byte-wise via `index()` and deliberately not a regex — all three regex
  spellings abort this awk with `towc: multibyte conversion failure`.

  **The trade, named:** an UNDEFINED non-ASCII label now silences the link around it — a false negative
  that is a property of this code, in place of a false positive that was a property of the environment it
  was measured in (PO decision 24.08.2026), with its own corpus entry. Deliberately NOT narrowed on the
  definition side: `[ÄÖ]: dead.md` still reports its target. Whether a label MATCHES is the question
  narrowed here; whether a destination EXISTS is check (n)'s own contract and needs no folding at all.

- **The corpus now carries no `false-positive` divergence at all.** 68 -> 76 entries. Of the 68
  pre-existing rows exactly two move: the WI-0096 row (its `known_divergence` becomes null and
  `dead-interrupt.md` leaves its findings) and the WI-0098 row (its `reason` now states the class rather
  than the one shape). Eight rows are added — two for the whitespace/empty definition labels above, and
  six for the WI-0098 collision class: three divergences, each paired with a control carrying the same
  label and NO colliding definition, where the link IS still reported. Twelve `false-negative`
  divergences remain and three `documented_intent` rows. WI-0096 is also removed from the closed set of
  work items allowed to own a `known_divergence`, so re-opening it has to be a deliberate act.

- **check (n) reported an outer link whose text contains a reference whose label the paragraph
  resolver rewrites — a false positive the two-pass round below introduced (WI-0098).** The two ends of
  the reference mechanism read their label from different text. The definition line reads the RAW
  record; the usage side reads the paragraph after `protect_link_destinations()` and
  `resolve_paragraph()` have run, and those DELETE a code span outright and replace a closed inline
  comment with a boundary sentinel. So ``[`a`]: def.md`` registered the label `` `a` `` while
  ``[outer [`a`] text](out.md)`` looked up the empty string, nothing matched, no deactivation happened
  and `out.md` was reported. Measured three ways: the reference (`commonmark==0.9.2`, HTML and AST) and
  `4f2ffa7` both report only `def.md`; the working tree reported both. `4f2ffa7` was right by accident —
  its `[^][]*` label class could not match a bracketed label at all. The inline-comment spelling
  (`[<!--x-->]`) was measured separately rather than assumed to be the same mechanism; it is.

  Fixed on the definition side, by registering each definition label a SECOND time in the shape the
  scanner will read it in — the raw label put through the same two functions — so that both ends key one
  space. It is an additional key, never a replacement, and that is what bounds the risk: adding keys can
  only make more references RESOLVE, a resolving reference only ever DEACTIVATES an enclosing link, so
  this cannot invent a finding — so long as `protect_link_destinations()` draws correct spans, which is
  WI-0095 and still open. `parse_link_label()` is blind to the destination sentinel, so a `]` inside a
  wrongly drawn span terminates a label and the consuming advance lands inside that span, where the
  argument no longer holds; on bracket-soup input check (n) has been measured reporting targets the
  reference never renders. That precondition is now written into the source next to the argument.

  Under it, the error the fix can make is dropping one, and it makes exactly one — a CLASS, not a shape.
  Label resolution is not INJECTIVE, and it has two accumulation points: the EMPTY key (a code-span-only
  label ``[`x`]``, a literal `[]`, a whitespace-only `[   ]` — the last two wider than the shape this was
  found on, because the reference never looks an empty label up at all) and the `boundary` key (any label
  that is exactly one closed inline comment, so `<!--a-->` and `<!--b-->` are interchangeable with no
  empty label involved). Once any definition owns such a key, every other label collapsing to it reads as
  a resolving reference and silences the link around it. All routes are measured, each against a control
  carrying the same label and NO colliding definition where the link IS reported, so the loss is pinned
  on the collision and not on the label shape. Traded deliberately (PO decision
  24.08.2026 — a false negative may replace a false positive, not the other way round) and counted as
  its own corpus entry. The counter-fixture that forbids the blunt repair has its own test: a code-span
  label with NO definition must keep reporting the outer link, because the reference renders it.

  The fix covers every construct either function rewrites, because the label is put through the
  functions rather than through a list of cases. It does not cover a construct whose resolution depends
  on text OUTSIDE the label (an unpaired backtick finding its partner later in the paragraph), where
  standalone and in-context resolution can still disagree; named in the source, not fixed here.

- **`paren_mark`, the sentinel a link destination's escaped `)` was detoured through, is removed.** Its
  stated reason had already expired: `process_link_line()` used to find a link span with a `[^)]*` scan
  blind to the `dest_mark` opacity, and WI-0080 replaced that scan with one that reads the extent off
  the span. The retention argument — "no test can pin the removal in either direction" — was false, and
  the line below the substitution is why: `decode_numeric_entities()` runs AFTER it, so
  `[x](a&#41;b.md)` has been putting a literal `)` inside a protected destination since WI-0081 and
  resolving correctly. The post-removal state was already pinned by a fixture that predates the removal;
  both spellings now have an explicit one, plus a two-links-on-one-line pin per spelling.

- **The pass-boundary reset now has tests, and three of its lines turn out to be the load-bearing
  ones.** Reading each index twice means pass 2 must start from BEGIN state; five of the reset lines
  were pinned by nothing. The three that can be observed — `in_fence`, `in_html_block1`,
  `in_html_block6` — get one behaviour test each (an unclosed construct at the pass boundary, with a
  dead link in FRONT of it, so an assertion of "one finding" cannot be satisfied by a pass that scanned
  nothing) and one mutation test each that removes exactly that reset line. Two measured details shape
  the fixtures: the dead link has to sit before the first BLANK line of the document, because a leaked
  fence arrives with `fence_char`/`fence_len` already reset and its closer test degenerates into a
  blank-line match, and a leaked type-6 block closes at a blank line by its own rule. The remaining two,
  `fence_char` and `fence_len`, are deliberately left untested and the reason is measured, not assumed:
  removing either changes nothing observable on any of ten fixtures, because both are read only under
  `if (in_fence)` and every path that sets that flag assigns them in the same breath. Nineteen structural
  mutations in that class now, each falsified once by neutralising the mutation.

- **Three corpus entries added: one for a reach that was described rather than pinned, one for a PO
  decision, one for a divergence traded in.** The WI-0097 stray-sentinel entry claimed a reach it could
  not discriminate — a second, independent
  link AFTER the construct shows the loss is the whole remainder of the paragraph, not just the link
  between the two sentinels (`stray_sentinel_byte_swallows_the_rest_of_the_paragraph`). WI-0092 (a link
  inside IMAGE ALT TEXT, `![a [b](in.md) c](out.png)`, which
  the reference renders as plain text and check (n) reports) is filed as `documented_intent` on the
  WI-0085 argument, PO decision 23.08.2026; it is pre-existing and `4f2ffa7` behaves identically. The
  third is `two_labels_with_the_same_resolved_shape_are_interchangeable`, the false negative the WI-0098
  fix above buys — it was counted in the 65 -> 68 total but not named here. The
  generator's docstring now carries the guard that class needs: `documented_intent` may only be assigned
  when the justification would hold even if no criterion depended on it — otherwise a round ends clean
  because a divergence changed its name. Corpus 65 -> 68 entries; all 65 previous entries are
  byte-identical after regeneration.

- **check (n) reported the outer target of a link whose text contains a RESOLVING reference link
  (WI-0093), and did not recognise a reference definition whose label carries an escaped bracket
  (WI-0094).** CommonMark's "links may not contain other links, at any level of nesting" fires on any
  successful LINK, not only an inline one. The WI-0080 scanner (see the entry below) implemented that
  rule in its inline-destination branch only, so `[outer [ref] text](out.md)` with `[ref]:` defined
  reported `out.md` — a FALSE POSITIVE, and one the regex the scanner replaced did not produce. It is
  the shape that blocked the promotion of check (n) to `err`. Fixed by extending the rule to the three
  reference forms, each measured against the pinned `commonmark==0.9.2` reference and not read out of
  the spec: shortcut `[ref]`, collapsed `[ref][]` and full `[text][ref]` all deactivate the enclosing
  openers when they RESOLVE, and consume the span they matched — `[text][ref](x.md)` renders the
  reference link and leaves `(x.md)` as literal text, so a scanner that only deactivated would re-read
  `[ref](x.md)` as an inline link. Three measured details decide the shape of the fix and none of them
  is obvious: (1) a FAILED full reference does not fall back to the shortcut reading, so
  `[ref][nosuch]` renders no link at all even with `[ref]:` defined and the enclosing link survives;
  (2) an IMAGE reference (`![ref]`) resolves but is an image, so it leaves the enclosing link alone,
  exactly as WI-0091 established for the inline form; (3) whether the inner label RESOLVES is the ONLY
  thing separating this from `[a [b] c](t.md)`, WI-0080's central fixture, which must stay one ordinary
  link — so "deactivate whenever no inline destination follows" is not a repair, it is a regression.

  Deciding any of it needs the document's reference-definition labels, and CommonMark collects those
  for the WHOLE document before it parses any inline content — a definition may legally stand AFTER the
  link that uses it (measured). A single pass cannot answer the question at the moment it reaches the
  link, so the extractor now reads each index TWICE: pass 1 prints nothing and only collects labels,
  pass 2 does the extraction with the complete set. Two passes of the SAME program, not a cheap
  pre-scan for definition-shaped lines: whether a line IS a definition depends on its block context —
  inside a fence or an HTML comment it is not one, and it may not interrupt a paragraph, all measured —
  and that context is precisely what the record block already computes. Label matching follows the
  reference's normalisation (internal whitespace collapsed, ends trimmed, case-folded). Case-folding is
  `tolower()`, and what that does to NON-ASCII depends on the process LOCALE, not on this script: under
  a UTF-8 locale `[ÄÖ]:` and `[äö]` match and agree with the reference, under C/POSIX they do not and
  the enclosing link is reported. The test harness runs the script with a bare environment, i.e. in the
  C locale, so the corpus freezes the narrower answer while an interactive run gives the wider one.
  Measured both ways and filed as WI-0099; not fixed in this wave.

  WI-0094 is the sibling defect the same round exposed one function further along: reference
  definitions were recognised with `\[[^][]+\]:`, the very label class WI-0080 had already removed
  from the usage side. A definition whose label carries a backslash-escaped bracket
  (`[a\]b]: dest.md`, one definition at the reference) was therefore not a definition at all — its
  target went unchecked and its label stayed undefined for the rule above. Both sides now share one
  `parse_link_label()` implementing the reference's own label grammar, so the two cannot drift apart
  again. Eight further structural mutations were added on top of WI-0080's six, one per new rule — the
  refmap lookup forced to "yes" and to "no", the two label sources swapped, label collection restricted
  to pass 2 (a BACKWARD definition asserted still working, so the mutation discriminates the
  forward-reference claim and not the feature), the paragraph gate dropped, the consuming advance
  replaced by a one-byte one, an image reference made to deactivate, and the label grammar made to skip
  one byte per escape instead of two. Each was itself falsified once, by neutralising the mutation and
  confirming it goes red — a mutation test that cannot fail proves nothing.

  **Three divergences this round measured and did NOT close**, recorded in the corpus rather than left
  unnamed, all in the false-negative direction: `protect_link_destinations()` spans the text after ANY
  `](` occurrence, live opener or not and escaped or not, and since WI-0080 the scanner skips such a
  span WHOLESALE — so a wrong span now hides the real link inside it, where the previous regex simply
  re-read through it (WI-0095, two entries); a literal 0x03 byte in a source file pairs with the
  opening sentinel of the next real destination and eats the link between them (WI-0097, pathological
  input, one entry); and a definition-shaped line that cannot interrupt a paragraph still has its
  target reported, which may be the WI-0085 decision one shape further along or a defect, and is filed
  as an open question for the PO rather than assumed (WI-0096, one entry). Corpus 52 -> 65 entries; all
  52 previous entries are byte-identical after regeneration.

- **check (n) could not see any link whose label contained a bracket, at any nesting depth, and could
  not see the badge pattern at all (WI-0080, WI-0091).** The extractor matched links with the regex
  `\[[^][]*\]\([^)]*\)`. That label class excludes BOTH bracket characters, so `[a [b] c](target.md)`
  — one ordinary link per CommonMark — never matched, and neither did `[a\]b](target.md)`, where the
  inner `]` is backslash-escaped rather than balanced. Both were silent false negatives. Widening the
  class would not have fixed it: CommonMark link text is a BALANCED construct of arbitrary depth, and a
  regular expression cannot count — the reference renders one link at nesting depth 1, 2, 3, 5, 10, 20,
  50 and 100, with no ceiling (measured, not assumed). The regex is therefore replaced by a scanner with
  an explicit opener stack, implementing four rules, each one measured against the pinned
  `commonmark==0.9.2` reference rather than read out of the spec: (1) `[` pushes, `]` pops, so balanced
  brackets in the label are ordinary content at any depth; (2) a backslash-escaped bracket neither opens
  nor closes, decided by backslash-run PARITY (`\\[x](t.md)` carries an escaped BACKSLASH and a live
  bracket) — the same parity now also decides the image marker, so `\![x](t.md)` is a LINK, not an image;
  (3) "links may not contain other links, at any level of nesting" — on a successful link every enclosing
  opener is deactivated, so the INNER link wins and the outer target is never reported; (4) an IMAGE in
  the link text does NOT disqualify the enclosing link. Rule 3 used to hold by accident, because the
  outer label could not match either — the corpus recorded an agreement no rule was responsible for; it
  is now explicit and pinned. Rule 4 is WI-0091, filed as its own item because its cause is separate:
  `[![build](badge.svg)](ci-url)`, the badge pattern, is a live link whose text is an image, and check
  (n) reported neither the link target nor anything else. It is also the shape that rules out every
  repair short of a real scanner — the LABEL itself contains a `](`, so any "split at the `](`" choice is
  wrong. Nothing is skipped by a match LENGTH any more — the scan only jumps over something it has
  RESOLVED (an opaque destination span, or a link it just consumed) and advances one byte everywhere
  else — so WI-0079's guarantee that a DISQUALIFIED construct cannot hide a real link later on the same
  line is now structural rather than hand-arranged. Mutation-checked by structure, never by deletion: escape parity
  replaced by a one-byte lookbehind, the escape probe moved one byte past each bracket in turn, the
  deactivation predicate INVERTED, the deactivation moved OUT of the image branch so an image disqualifies
  too, and the opener stack CAPPED at one entry (with the flat case asserted still green, so the mutation
  discriminates depth specifically) — six mutations, each confirmed to flip its own fixture, the real
  script untouched and md5-verified. Corpus 46 -> 52 entries; three lose their `known_divergence`
  (`nested_brackets_in_link_text_simple`, `nested_brackets_in_link_text_mid_sentence`,
  `backslash_escaped_bracket_in_link_text`), the other 43 are byte-identical after regeneration, and the
  six additions cover three-level nesting, an unbalanced-bracket negative pin, inner-wins-beside-a-later-link,
  the badge pattern, two nested images, and an image with a bracketed alt text.

  **Upgrade note:** against the last RELEASE (`v0.2.1-beta`) this wave removes no finding — measured,
  with both scripts, on every shape this wave discusses, including the three it regresses on internally
  (below): `v0.2.1-beta` reported none of them either. Against the INTERMEDIATE state `4f2ffa7`, i.e.
  for anyone tracking `main` rather than releases, the claim does not hold and the difference is not
  cosmetic — the WI-0080 scanner skips a `dest_mark` span wholesale where the regex it replaced re-read
  through it, and that costs three shapes, all measured: `x](y [a](t.md) z)` and its escaped twin
  `x\](y [a](t.md) z)` (WI-0095, two corpus entries, `4f2ffa7` reported the inner link, this version
  does not), and a literal 0x03 byte in the source, which now swallows the rest of its paragraph
  (WI-0097, two corpus entries, one defect — `4f2ffa7` reported both links, this version reports
  neither). All three stay open. WI-0098's traded false negative is NOT in this list: `4f2ffa7` did not
  report that shape either, so it is a divergence from CommonMark, not a loss on upgrade.

  Otherwise the direction is additive: it ADDS findings on unchanged content — a store nobody has
  touched can start reporting dead links after the upgrade, because those links were always dead and the
  extractor simply could not see them. On its own this change does not move the EXIT CODE: check (n) was
  filed under `warn` by default (`MEMORY_INDEX_LINK_SEVERITY`), so the new findings landed in Warnings
  and a run that exited 0 still exited 0 unless it already had warnings. **Corrected after this entry
  originally shipped (WI-0005):** it went on to say "the breaking moment is the promotion of check (n) to
  `err`, not this change" — and that promotion is no longer a later release. It is in THIS one, under
  `Changed`. Read together, the exit code does move: a store nobody has touched can go from **exit 0 to
  exit 2** on upgrade, because this entry supplies the new findings and the promotion files them as
  errors. `MEMORY_INDEX_LINK_SEVERITY=warn` restores the severity this entry assumed. Expect
  it wherever an index uses brackets inside link text (`[Release state [measured]](file.md)`) or the badge
  pattern. Measured against four live memory stores with both script versions on the same day: identical
  in all four, because the constructs are almost absent there — a null result that proves nothing, so the
  evidence is a discriminating probe on a COPY of a real memory tree instead, where the old script
  reported 2 warnings and the new one 4, the two additions being exactly the dead nested-label and dead
  badge targets, with the live ones and both image sources correctly silent.
- **check (n)'s paragraph buffer missed three block boundaries CommonMark honours, swallowing real
  links across the merged blocks (WI-0086, WI-0082).** The buffer accumulates a paragraph across
  physical lines so a code span may straddle them, and it flushes only at a boundary it recognises. A
  boundary it did not recognise merged two blocks, letting two backticks that each belonged to a block
  of their own pair across the merge and hide a real link — a false negative in all three cases.
  Closed: (1) a CARRIAGE RETURN is now stripped from every record before any boundary test runs.
  CommonMark counts `\r\n`, `\r` and `\n` all as line endings; awk splits on `\n` only, so on a
  CRLF file — anything authored on Windows, or any checkout with `core.autocrlf=true` — every
  `$`-anchored regex in the extractor silently stopped matching, not just the blank-line test — an empty
  ATX heading, a fence close, and a reference definition carrying a quoted title (`[ref]: x.md "t"`,
  whose destination was then never checked at all) were each confirmed broken by the same cause, the
  last of them in the one branch that does not test the record directly. (2) a THEMATIC BREAK
  (`***`, `---`, `___`, with optional spaces or tabs between the markers) is now a boundary, and
  deliberately an UNGATED one — a break really does end an open list item, measured
  (`<ul><li>...</li></ul><hr />`), so gating it would hide links inside the item. (3) a
  SETEXT-HEADING UNDERLINE is now a boundary, but only where CommonMark actually ends a paragraph
  with one: with the buffer empty the same line is ordinary paragraph text, and with a list item or a
  block quote open the reference keeps a `=`-run as lazy continuation inside that container —
  flushing there would have traded the fixed false negative for a new false positive. That container
  rule is specific to the `=`-runs and the one- and two-dash runs that actually reach the setext
  branch; it does NOT generalise to `---`, which the thematic-break branch claims first and which the
  reference does not treat as lazy continuation either. The guard also has to survive a block quote
  that INTERRUPTS an open paragraph rather than opening it — a review caught the first version keying
  off what opened the paragraph buffer, which reported a code-span-buried link on a shape that had
  been correct before this change; the reference reading (`<code>q [a](...) === closer</code>`) is now
  pinned by a behaviour test and a pre-form-restoration mutation. All container rules were measured
  against the pinned `commonmark==0.9.2` reference, not derived from the
  spec text. The thematic-break branch is deliberately ordered BEFORE the list-marker branch, because
  `- - -` satisfies both patterns and CommonMark gives the break precedence; that ordering closed a
  fourth, previously unrecorded divergence found while measuring — a `- - -` line followed by an
  indented code block used to report the bracketed text inside the code block as a dead link
  (false positive), because the list branch buffers its own line and thereby defeats the indented-code
  branch's empty-buffer gate. Mutation-checked, and by structure rather than deletion: the branch order
  was PERMUTED (both branches still present), the setext gate WIDENED to the naive form the reference
  falsifies, the block-quote guard RESTORED to its exact pre-fix shape, and a pbuf_para gate ADDED to
  the thematic-break branch that must not have one — each confirmed to flip its own fixture, real
  script untouched (md5-verified). The last two came out of the review: nothing had pinned the
  thematic-break branch as ungated, and adding the gate left the whole suite green.
  Re-measured against four live memory stores with both script versions on the same day: identical
  findings in every one, including the 14 persona indexes whose YAML frontmatter CommonMark reads as a
  thematic break plus a setext underline — inside the extractor both `---` lines are claimed by the
  thematic-break branch, which runs first, so the effect is the same but the attribution is not;
  verified by probe links inside and after real frontmatter, found by both versions, not by a bare
  "no new findings" count. Three corpus entries lose their `known_divergence` and two entries are
  added for the container-vs-boundary shapes above; the other 41 are byte-identical after
  regeneration.

  **Upgrade note:** this is a false-negative fix, so a store that has not changed at all can start
  reporting dead links it never reported before — they were always dead, merely hidden by a paragraph
  merge. Expect that on CRLF checkouts and on files using `***`/`---`/`===` between link-bearing
  blocks. **Corrected after this entry originally shipped (WI-0005):** it read "check (n) still defaults
  to `warn`, so such a finding does not fail a run today", and deferred the promotion to `err` to a
  later release under ADR-0001. That promotion is in THIS release, under `Changed`. A store that has not
  changed at all can therefore go from **exit 0 to exit 2** on upgrade — this entry supplies the finding,
  the promotion supplies the severity. `MEMORY_INDEX_LINK_SEVERITY=warn` restores the severity this
  entry assumed.
- **Five of round 2's seven false positives against check (n) closed; the round's one wrong-target
  row moved to a non-claim instead of a decode (WI-0084, WI-0081 remainder).** check (n)'s awk
  block-boundary list now tracks an indented code block (four spaces, or one leading tab — CommonMark
  never inline-parses either) and two non-comment HTML block types, copied from the pinned
  `commonmark==0.9.2` reference's own tag tables rather than guessed: type 1 (`script`/`pre`/`style`,
  closes on a matching closing tag anywhere in a LATER line, a blank line inside does not end it) and
  type 6 (`div` plus roughly sixty more block-level tags, closes at the next blank line — NOT at a
  matching closing tag, measured directly against the construction trap this distinction turns on: a
  link right after `</div>` with no blank line yet is still inside the block). Types 3–5 (processing
  instructions, declarations, CDATA) and type 7 (an arbitrary single tag alone on its own line) are
  deliberately excluded — zero measured field occurrences and a materially different mechanism,
  respectively; the boundary is named in the code, not left to "as complete as it happened to get."
  Separately: a destination containing an unresolved NAMED HTML entity (`&num;`, as opposed to the
  numeric forms already decoded) used to be resolved as raw text and reported as dead regardless of
  whether the entity-decoded target actually existed — a false claim in either direction, since check
  (n) never actually tested the file CommonMark says the link addresses. It is now filed as an `info`
  finding naming the raw target, absent from both Errors and Warnings, rather than asserting a verdict
  the check cannot back. Mutation-checked, all four guards individually reverted on an in-memory copy
  and confirmed to flip their own dedicated fixture, real script untouched (md5-verified). Re-measured
  against four live memory stores: zero occurrences of any of these constructs in the field today —
  this closes correctness gaps, not live findings. **No false-positive-direction divergence remains in
  the CommonMark corpus** after this round; the ten still-open divergences are all false negatives, and
  the two remaining unused-reference-definition rows are reclassified as intended (WI-0085, below), not
  left as unfixed bugs.
- **Two round-2 "false positives" reclassified as intended behaviour, not fixed (WI-0085).** An unused
  `[id]: dead.md` reference definition (no `[id]`/`[id][]`/`[x][id]` usage anywhere in the file) renders
  nothing at all per CommonMark — but check (n) checks its destination anyway, unconditionally. PO
  decision, 23.08.2026: this is deliberate. check (n)'s own contract is narrower than conformance — does
  the index still point at files that exist? — and a definition addressing a deleted file is a dead
  pointer, invisible on a normal read because it renders as nothing, which is exactly the failure mode
  this check exists to catch. No script change; the two corpus entries move from `known_divergence` to a
  new, mutually-exclusive `documented_intent` field (reason, PO decision date, work item) so a future
  round's own tooling can tell an open gap apart from one the PO has already closed.
- **check (n)'s label/destination matcher ignored CommonMark backslash-escapes and inline-resolved
  destinations, closing two of the WI-0079…WI-0083 divergences (WI-0079, WI-0081).** An escaped
  bracket pair (`\[not a link\](x.md)`) is no longer reported as a dead link — either bracket alone
  being escaped is enough to remove its structural meaning, checked by backslash-run parity so an
  escaped backslash (`\\[real](x.md)`) is not mistaken for an escaped bracket. A destination is now
  resolved the way CommonMark resolves it before it becomes a filename to check: an escaped closing
  parenthesis (`[x](a\).md)`) no longer truncates the target to `a\`, and a numeric character
  reference (`&#35;`, `&#x23;`) is decoded to its literal character instead of being checked
  undecoded — protected from the shell-side `#anchor` fragment-strip by a one-byte sentinel so a
  decoded `#` is not mistaken for a fragment separator, the mechanism that previously mangled
  `dead&#35;3-ent3.md` into the unrelated path `dead&`. **Not decoded**: named entities (`&num;`) —
  the full CommonMark named-entity table has roughly 2000 entries, disproportionate for a construct
  measured at zero occurrences across four live memory stores; the raw text is still checked, not
  further garbled. Re-measured against all four stores after the fix: no change — none of the fixed
  constructs occur in the field today.
- **`memory-lint.sh` check (f) resolved `related:` against the file's own directory only, the same
  question WI-0071 already answered for `phase-docs-lint.sh` (WI-0078).** Authors write `related:`
  entries project-root-relative (`docs/memory/foo.md`), not document-relative — a document-relative
  miss now falls back to `$PROJECT_DIR` before the entry is declared dead, mirroring WI-0071's fix
  exactly: same fallback base, same message wording, same severity split (a root-relative hit is
  `info`, naming both candidate paths, not silence — two bases without saying so is the unvalidated
  drift this lint exists to catch). Measured against a real store (productdata): the one file the
  defect was found on, `docs/memory/project_attribute-mapping-slice-b-gap.md`, still errors after
  this fix — its `related:` entry (`planning/sprint/S19-VALUEMAP-ARCH.md`) is written relative to
  `docs/`, not to the project root, so neither base resolves it. That is a genuinely different
  question from the one WI-0071's convention answers, and mirroring that convention here — rather
  than inventing a second, docs/-rooted fallback for this linter alone — was the explicit brief.
- **Ten divergences between check (n) and CommonMark, found by that corpus (WI-0079…WI-0083).** Two
  were predicted from the matcher `\[[^][]*\]\([^)]*\)` before the round ran and both confirmed: an
  escaped bracket pair `\[not a link\](x.md)` is reported although it is not a link (**false
  positive**, the direction that blocks promotion), and a label containing brackets `[a [b] c](x.md)`
  is missed although it is one. Eight were new. The destination is taken literally where CommonMark
  resolves it — an escaped `)` truncates the reported path, and a decimal entity `&#35;` is mangled
  into `dead&` by the fragment-stripping that exists for `#anchor` suffixes, a path that appears
  neither in the input nor in the reference's answer. A setext underline and a thematic break are not
  block boundaries, so a code span pairs across them and swallows a link. And a reference definition
  whose destination sits on the next line is not recognised at all, isolated by a single-line control
  that is found. **Not fixed here** — the round's product is the measurement, and the fix order is a
  decision that wants the whole table on the table first.
- **A second adversarial round against check (n), eight more divergences (WI-0005 round 2).** The
  first round's ten construct classes were deliberately not repeated; this round read check (n)'s own
  awk block-boundary list and searched what it has no case for at all. An indented code block (four
  spaces, or one leading tab) is literal text at the reference — check (n) has a boundary case for a
  fenced code block but none for the indented form, and reports the bracketed text inside as dead. An
  HTML block opened by anything other than `<!--` (`<div>`, `<pre>`, `<script>`) is raw, unparsed HTML
  at the reference for the same reason — check (n) only ever learned the comment form. A reference
  definition with no matching `[id]`/`[id][]`/`[x][id]` usage anywhere in the file renders nothing at
  all, but check (n) checks its destination unconditionally, straight off the definition line — the
  same mechanism that makes shortcut and collapsed reference-link usage, and case-/whitespace-
  insensitive label matching, merely *look* supported without check (n) ever resolving a usage.
  **The most consequential this round**: on a CRLF-terminated file, the blank-line boundary test
  (`$0 ~ /^[ \t]*$/`) does not match the bare `\r` a CRLF blank line leaves behind after `\n`-splitting
  — two paragraphs merge into one buffer and a stray backtick in each pairs across paragraphs it
  should never have reached, swallowing a link. Two further entries extend the already-settled
  WI-0060/WI-0061 empty-destination exception (`[x](<>)`) to the unbracketed forms `[x]()` and
  `[x]( )` — not new gaps, the same intentional "nothing to check" behaviour, confirmed to hold for
  the syntax most likely to actually occur. Eight constructs (blockquotes, ATX headings, emphasis in
  link text, the CRLF case's own non-confounding control) were measured and agree, kept as regression
  pins. Seven of the eight new divergences are false positives — the direction that blocks promoting
  this check to `err`; the corpus grew from 26 to 44 entries, all newly verified against both oracles.
  **Not fixed here**, same as round 1.
- **`memory-lint.sh` told readers to set a value that did nothing (WI-0074).** Its age warning read
  "consider setting `status='stale'`" — and `stale` was not in the suppression list, so following the
  advice produced the same warning on the very next run. Measured across all five cases: unset warns,
  `stale` warns, `archived` and `superseded` are silent. The consequence is visible in the field —
  **`status: stale` appears zero times across all five live memory stores**, because setting it never
  helped anyone. The obvious repair, adding `stale` to the suppression list, was rejected: it buys
  silence with a self-declaration, and "I know it is old" ending a message about being old is the
  ceremony this repo's anchor work spent a whole package refusing. Instead the value is **removed from
  the enum** — it rejects nothing, since nobody uses it — and the message now names the two values
  that legitimately end it (`archived`, `superseded`, both meaning "deliberately no longer
  maintained") and otherwise asks for the refresh it actually wants. The enum is enforced for the
  first time, at **error** severity, and that severity is measured rather than assumed: the single
  schema-foreign value in the field was corrected first, and a sweep of all five stores afterwards
  found nothing outside `{active, archived, superseded}`, so the check rejects nothing that exists.
  Modelled on the neighbouring `type` check rather than invented. `commands/cleanup.md` still cited
  the old suggestion and was corrected in the same pass.
- **The `code-reviewer` agent was told to run commands it has no tool for, and described as something
  it is not (WI-0073).** Its `Context Discovery` section opened every review with `git diff`,
  `git log` and `git diff --cached` in a shell block — while its tool set is `Glob, Grep, Read` plus
  `Edit`/`Write` restricted to its own memory files. No shell, so the first instruction of every
  review was unfollowable, which is why its reports kept explaining that they had read the current
  file state instead. The section now says plainly that there is no shell and names the three ways a
  diff can actually reach it, weakest last, with the instruction to say so when it falls back to
  reviewing current state — because then it cannot tell a new defect from a pre-existing one. Two
  sections were added from what this session's three reviews actually did well: how to hand back a
  finding that needs execution to settle (separate verified from inferred, and name the one command
  that would decide it — a suspicion arriving with its own discriminator gets settled in seconds),
  and where the work-item store is, since it is plain Markdown the agent can read but is gitignored
  and therefore easy to miss. `CLAUDE.md`'s agent table called it "read access only" — the only
  capability claim in a column that otherwise describes focus, and wrong in both directions: it does
  write (its memory silo, by design) and it cannot execute (which nothing said). Checked across every
  other shell-less agent: none had the same defect.
- **`freeze-phase-docs.sh` rewrote prose it had no business touching, and could not run on Linux at all
  (WI-0076).** Its single in-place edit was `sed -i '' -E "s/^status:…/status: frozen/"`. Two defects in
  one line. The empty argument after `-i` is BSD syntax — GNU sed reads a separate `''` as the script
  and pushes the real script into the filename slot, so on Linux the call fails, at the moment a gate
  passes. And `sed` works line-wise with no notion of where the frontmatter block ends: reproduced
  against the committed original, a **body** line reading `status: active` — the kind that appears in
  any document quoting a frontmatter example, as this repo's own schema does — was silently rewritten
  to `status: frozen`. Neither was caught by anything, because the shell sweep only runs `bash -n` and
  the script had no behavioural test module at all. Replaced by a portable `fm_set` (below) and covered
  by `scripts/tests/test_freeze_phase_docs.py`, 20 tests including the four terminal states it must
  skip, the index skip, the P5/P8 no-ops, and the body-protection case that was red against the
  original before the rewrite existed.
- **`related:` and `parent_index:` rejected paths that point at files which exist (WI-0071).** The
  schema documents these as document-relative and the lint resolved them that way; in the field authors
  write them from the repository root. Measured in one project: 13 findings of the form
  `related:'docs/CONSTITUTION.md' points to non-existent file (…/docs/reviews/docs/CONSTITUTION.md)` —
  the doubled `docs/` is the entire defect, and every one of those targets exists. False positives at
  error severity, the direction that breaks a correct run. Resolution is now document-relative first,
  then project-root, and a hit on the second attempt is reported as an **`info`** naming both
  candidates. Silence was the cheaper option and was rejected: two silently permitted bases are the
  unvalidated spread this package exists to stop, and an info finding costs nothing on the exit code
  while keeping the drift countable. Verified against the real project rather than only against
  fixtures — with the reviews profile temporarily widened, those 13 errors become 0 errors and 13 info
  findings.
- **Two shipped documents stated a five-value `status` enum the schema and the linter never had.**
  `templates/PHASE_DOC_SCHEMA.md` and `phase-docs-lint.sh` both carry six values — `living` is a real,
  documented status for detail files designed to keep growing (SPRINT-XX.md, RISKS.md) — while
  `CLAUDE.md` and `templates/PROJECT_CLAUDE_TEMPLATE.md` listed five. Found while measuring the
  precondition for ADR-0009, whose severity model keys off exactly this field: read through the short
  list, the design's `living` row would look like it rests on an invalid value. Every other statement
  of the enum in the repo — the Manual, all phase-command templates — already listed six, so these two
  were the outliers, not the majority. Corrected to six.
- **`PHASE_DOC_SCHEMA.md` claimed two index-consistency checks the linter does not perform.** It said
  "the lint also checks" that every frontmatter-carrying file is listed in its phase index, and that a
  `parent_index:` target must "exist **and list it**". The lint checks path existence and nothing more;
  neither index is ever parsed, and no other script does it either (verified — `parent_index` appears
  in exactly two files, one of them an example block). A statement about the code that was simply
  untrue, and the dangerous direction: a clean lint run read as evidence that index membership holds.
  The section now separates the one enforced check from the two conventions and says plainly that
  nothing validates them.
- **`install.sh --dry-run` announced a wholesale `docs/` copy the real run has not performed since
  WI-0018 (WI-0064).** Found by offering the dry-run as the cheap proof that the docs/ allowlist
  holds, then reading the branch: it exits 0 *before* the artifact loop and prints one
  `$SRC/$item -> $DEST/$item` line per entry. Accurate for the five wholesale artifacts, wrong for
  the sixth — `docs` is the one the loop special-cases into `install_docs()`, which filters every
  top-level child against `scripts/lib/docs-framework-allowlist.txt`. The offered proof would have
  shown the opposite of what it was offered for. The error direction is what made it worth fixing
  rather than noting: a preview exists so an adopter can see what an install will do, and this one
  *overstated* the blast radius in the single place where the answer is subtle, announcing exactly
  the copy the allowlist prevents. A maintainer reading it concludes their working state is about to
  ship and falls back to the clean-clone ritual WI-0018 made unnecessary — the feature stays
  invisible to the audience looking for it. `install_docs()` decided and copied in one pass, so the
  dry-run had nothing to call; the classification is now a side-effect-free `docs_partition()` and
  the skip paragraph a shared `docs_report_skips()`, so preview and run read one verdict and cannot
  drift. The dry-run lists what it would install, what it would skip, and still writes nothing. Six
  tests cover it, including a parity test asserting the dry-run's skip set equals the real run's on
  the same tree, and dotfile coverage (`.handover-archive`, `.DS_Store`) — `dotglob` handling moved
  with the loop, and a mutation removing it turns three tests red.

- **96 skill epilogues told the model to update `docs/HANDOVER.md` without ever telling it to
  replace its own previous block, or what to do when the file is already full (WI-0070).** Measured
  rather than assumed, after a first crude count got the right verdict for the wrong reason: of 115
  commands, 113 write to the HANDOVER and exactly one — `cleanup.md`, the command that enforces the
  cap — mentions it. The other seven apparent hits all referred to a different file's limit
  (CONSTITUTION.md's 8/25 KB, FRAME.md's 5 KB at the same number, the README body,
  `docs/planning/.handover-archive` as a different directory, `/cleanup`'s inbox marker,
  memory-lint's 30 KB topic cap). The obvious diagnosis is nonetheless wrong and is recorded in the
  work item so nobody fixes the wrong thing: `templates/HANDOVER_TEMPLATE.md` line 3 carries the cap
  as a blockquote, so every HANDOVER states it in its third line and any agent reading the file sees
  it. What was missing is that no epilogue names **stacking** as the growth mechanism — appending a
  second block per run rather than replacing the previous one — and none says to measure before
  adding. One run has been clocked at 1021 B, ~20 % of the cap, so five runs take a file from empty
  to breach, which is what the hook's 80 % warn threshold is calibrated against. All 96 epilogue
  sections now open with the same two rules, and the 88 that were boilerplate are normalised to one
  wording (they had drifted into four near-identical variants over `Next Steps`/`Next steps`,
  `useful`/`sensible`, `allowed`/`permitted`, `match`/`fit`). The eight command-specific epilogues
  (`constitution`, `cross-check`, `lean-frame`, `lean-learn`, `lean-promote`, `release-baseline`,
  `specialize`, `track-decision`) keep their own body verbatim and gain only the shared paragraph —
  flattening them into the boilerplate would have silently dropped instructions no other command has.

- **`/postmortem` told users to file ambiguous knowledge one memory tier too high, and refused to
  run on a session whose summary file was missing or stale (WI-0065, WI-0066).** Both found by
  auditing the skill against a run that had just worked around it. §5 instructed "When in doubt,
  prefer Tier 1 (visibility wins over isolation)" while pointing two lines earlier at CLAUDE.md as
  the "full definition" — and CLAUDE.md names that exact phrase as the tiebreaker it withdrew,
  because it caused persona-specific patterns to leak into the globally autoloaded file. The damage
  was directional and silent: nothing fails, the Tier-1 index just accretes, and the cost lands on
  every later session rather than the run that misfiled. Replaced with CLAUDE.md's three-step
  decision order verbatim, including the promotion threshold (3rd cross-reference from a different
  domain), so the two documents cannot drift apart again. Separately, §1 aborted on a missing
  `session-summary.json` — but that file is written at session end, so every postmortem of a running
  session hit it, and on the run before this one the file existed while holding a mid-session
  snapshot (190 tool calls against the session's actual ~3.500). The abort now fires only when all
  three log inputs are unusable, and the skill names the stale-summary case explicitly: a present
  summary is sanity-checked against `activity.jsonl` before its numbers are reported, because
  plausible-looking wrong figures are worse than none.

- **`/postmortem` documented a stored-instinct format that no shipped instinct uses, an archive
  write that `HISTORY.md` describes differently, and a closed list of five topic files
  (WI-0067, WI-0068, WI-0069).** §3's template (`### [ID] Short title` plus a bullet list of
  Confidence/Source/Rule/Context) matches nothing in `instincts/`, where blocks carry a colon in the
  heading, one pipe-separated metadata line, and **Why** plus **How to apply** — the two sections
  that make a stored rule operational, and the two the template omitted entirely. §3 is now labelled
  as the proposal format shown to the user for confirmation, and §6 carries the stored shape it was
  silently assuming, with a note to follow whichever form the target file already uses so one file
  never mixes both. §6 also said to "append a new `Previous:`-style block" to the archive, while
  `instincts-archive/HISTORY.md` states the convention as two moves — new block on top as the
  current head, previous head demoted to `Previous:` — which is what keeps the archive complete once
  the slim index drops a head; the skill now describes both moves and defers to the archive's own
  section. Finally, the write target was hard-coded as
  `~/.claude/instincts/{agents,files,workflow,shell-git,external}.md`. That is correct for the
  shipped starter set and wrong as a permanent contract: the set is designed to grow, and the growth
  pressure comes from inside this system (`memory-lint.sh` warns at a 30 KB soft cap; `/postmortem`
  adds the blocks that get a file there). The five are now presented as the starter themes,
  explicitly not exhaustive, with the instruction to list the directory and pick by theme — and to
  propose a new topic file rather than force an entry into the nearest fit.

- **`memory-lint.sh` check (n) both missed a dead angle-bracket link (WI-0060) and misreported a
  non-link as one (WI-0061) — the same shell-side target-handling case blocks, fixed together.**
  Found in sequence while settling `docs/memory/reference_commonmark-conformance.md`'s table for
  WI-0060: an explicit `\<*` case arm skipped CommonMark's bracket destination form
  (`[x](<target.md>)`) outright, alongside external schemes and in-page anchors it correctly belongs
  with — except the bracket form DOES address a file in the repository, so a dead target written that
  way passed silently, reaching neither the existence check nor even a report under the bracketed
  name. WI-0061, found while settling the same table, is the direction that matters more: the WI-0034
  comment concluding "a bare space is no delimiter, so `[x](my file.md)` keeps its space instead of
  collapsing to `my`" was right about not truncating, but wrong about what to do with the untruncated
  result — per the reference an unescaped, untitled space in an UNBRACKETED destination means the
  whole `[x](...)` construct is not a link at all, so `[x](my file.md)` was being reported as a dead
  target for content that was never a link, the direction `MEMORY_INDEX_LINK_SEVERITY`'s then-`warn`
  default existed to protect against. Fixed by unwrapping the bracket form before resolving (an
  UNCLOSED opener, `[x](<a.md)`, stays skipped — CommonMark reads it as literal text, not a link) and
  by treating a leftover space in an unbracketed target as "not a link" instead of "a target with a
  space in it". Nine fixtures (one per reference-table row, `docs/memory/reference_commonmark-conformance.md`)
  plus the reference-style-definition sibling path (`[id]: <target>`, which shares the same shell
  code) are wired into `scripts/tests/test_memory_lint.py`, each mutation-checked against a scratch
  copy of the pre-fix code restored byte-identical afterward.
- **`scripts/baseline.sh` archived HANDOVER.md into an undotted `docs/handover-archive/`
  directory no convention named (WI-0059).** Found by WI-0058's implementer as out-of-scope drift:
  three other places already agreed on the dotted spelling — `.gitignore` ignores
  `docs/.handover-archive/`, `commands/cleanup.md` documents it twice as the established
  convention, and the only such directory that exists on disk in a real project is the dotted one.
  `scripts/baseline.sh` was the outlier, and duplicated the wrong path a second time as a hardcoded
  literal string in its generated report rather than deriving it from the directory it actually
  wrote to — the duplication is how the two drifted without either being individually wrong-looking.
  Fixed by pointing `ARCHIVE_DIR` at the dotted directory and deriving the report line from that
  same variable instead of a second literal, so the two can no longer disagree. A pre-existing
  undotted directory from an older run is reported by name (contents listed nowhere are moved) and
  left completely untouched — moving a user's files without asking is the action that needs
  consent, leaving them alone does not. New `scripts/tests/test_baseline_archive_directory.py`
  covers the dotted destination, the report/actual-path agreement, the legacy-directory report +
  untouched-contents guarantee, and the pre-existing `docs/.baseline-prep.md` regression path, with
  inline mutation-proof tests for all three changed sites.
- **Twelve generated `docs/` artifacts were not gitignored anywhere they land (WI-0058).** A
  sweep of every `docs/.<name>` path shipped scripts and commands write literally (gate-preflight
  notes for P0–P7, session-context, quality-scan-report, cross-check-report, baseline-prep) found
  three independent gaps, not the one the item's own title named. (1) This repository's own
  `.gitignore` covered none of them — the shape that left `docs/.session-context.md` untracked
  after a verification run, carrying this repo's own git status and paths into the exact class of
  content the artifact gate exists to keep out. (2) `scripts/project-init.sh`'s generated
  `.gitignore` (what a new project actually receives) missed `docs/.cross-check-report.md`, even
  though that path is named explicitly in the "Standard block for `.gitignore` in CCPR projects"
  CCPR itself ships as instinct G-049 — the generator contradicted the rule the framework hands its
  users. (3) `docs/.baseline-prep.md` was in neither the generator nor the shipped standard block,
  newer than both — exactly the drift G-049 exists to prevent, and the block existed in two places
  (`templates/STARTER_INSTINCTS.md`, `instincts/workflow.md`) that had to be fixed together or stay
  disagreeing. Fixed with two different shapes deliberately: this repo's `.gitignore` uses a broad
  `docs/.*` pattern (verified no dotfile under `docs/` is tracked here today, so nothing is
  swallowed, and future generated artifacts need no further edit), while
  `scripts/project-init.sh`'s generated block stays an enumeration (a user's project may
  legitimately track a dotfile under `docs/` that this repo does not, so a broad pattern there
  would be a silent, unrequested behaviour change on every new project). A new
  `scripts/tests/test_docs_dotfile_gitignore_coverage.py` derives its expected set from the same
  sweep method rather than a hand-maintained list, so a script or command added tomorrow that
  writes a new `docs/.<name>` path fails the suite until it is listed in `.gitignore`, the
  generator, and both instinct-block carriers. Documented limitation: the sweep only finds paths
  spelled out literally in source — `scripts/gate-preflight.py`'s actual output path is built from
  an f-string variable, so the eight concrete `docs/.gate-preflight-pN.md` hits it finds come
  entirely from each `commands/gate-pN.md` file documenting that path, not from the generator
  itself; a path assembled purely at runtime and never spelled out anywhere would not be caught.
- **`scripts/log-cleanup.sh` could silently replace a real log with garbage instead of a trimmed
  copy (WI-0056).** Found and deliberately left unfixed by WI-0054's classifier as
  `known-risk-not-yet-fixed`: the trimmed log was written to a tmpfile by a bare
  `python3 -c "..." 2>/dev/null`, followed by an UNCONDITIONAL `mv`. MEASURED first, and the
  item's own headline mechanism did not reproduce: a python3 that FAILS (nonzero exit, via a PATH
  stub or `PYTHONHOME=/nonexistent`) already aborted the whole script under this file's own
  `set -euo pipefail` before the `mv` was ever reached — the log survived, just silently (empty
  stderr, no indication which of the three files failed or why). The actually reproducible shape
  was narrower: a python3 that returns EXIT 0 without doing the real work. Fixed by creating the
  tmpfile in the same directory as the target (atomic rename — a process kill either lands before
  it, original untouched, or after it, fully in place), capturing python3's exit status explicitly
  AND validating its stdout is a well-formed line count before trusting it (closes both the
  exit-nonzero and the exit-0-with-garbage-output shapes), skipping only the failed file instead of
  aborting the whole run, and printing a per-file `[ERROR]` instead of staying silent. A residual,
  deliberately unfixed gap remains: a python3 that returns exit 0 AND prints a plausible but wrong
  line count cannot be told apart from a legitimate full trim by any exit-status check — recorded in
  `docs/memory/senior-developer/scripts-conventions.md`, not silently closed.
- **`scripts/bootstrap.sh` could abort its whole session-context dashboard on a legitimate empty
  result (WI-0057).** Also found and left unfixed by WI-0054 as `known-risk-not-yet-fixed`: a bare
  `grep -E '^### \[' "${INSTINCTS_FILE}" | head -5 | while read ...` — under `set -o pipefail`, a
  grep that matches nothing exits 1 and takes the whole `{ ... } > "${OUTPUT_FILE}"` block down with
  it. MEASURED first: this repository's own current `~/.claude/instincts.md` (a bullet-point index,
  zero `### ` headings at all) never reaches this line — an earlier `count -eq 0` guard already
  returns first, so the item's summary read too broadly for that shape. The reproducible case is an
  instincts file that DOES have `### ` headings, just not in the `### [ID] ...` bracket form (the
  shape this repo's own topic files actually use: `### G-008: ...`, no leading bracket) — there,
  `grep -E '^### \['` legitimately matches nothing and the pipeline abort is pure `pipefail`, not
  SIGPIPE from `head -5` (verified: a 200-heading probe that `head -5` truncates hard still exits 0
  for the pipeline). Fixed by capturing the grep call's output and status explicitly and branching on
  grep's own documented exit-status contract (1 = ran fine, nothing matched; 2+ = grep itself
  failed) — deliberately not a blanket `|| true`, which would recreate the exact "failure read as
  empty result" confusion this fix exists to close, in the other direction, for a genuine grep
  failure.
- **`scripts/quality-scan.sh` could not be parsed by bash and silently exited 0 having scanned
  nothing (WI-0055).** A `python3 << 'PYEOF' ... PYEOF` heredoc was nested inside a `$(...)` command
  substitution (`grep_findings=$(python3 << 'PYEOF' ...)`); the heredoc body's SQL-injection pattern
  carried an apostrophe (`f\'`), and an ODD apostrophe count breaks bash's quote tracking while it
  scans for the substitution's closing `)` — this is the exact mechanism WI-0044 named for
  `memory-lint.sh`'s awk block, on a second shipped script. `bash -n` failed at the line carrying the
  pattern; running the script printed the same syntax error to stderr, wrote no report, and still
  reported exit 0 — traced to the EXIT trap's own `rm -rf` succeeding and silently becoming the
  shell's final exit status once a bash-level parse abort (which never sets `$?` to anything
  reflecting the abort) reached it. Escaping the apostrophe was rejected as the fix, on this
  repository's own history: it is the shape that left `memory-lint.sh` fragile for eight rounds and
  produced WI-0037 and WI-0044. Instead the heredoc body moved to a real file
  (`scripts/lib/quality_scan_sast_patterns.py`), invoked as a plain `python3 <path>` call — no
  parity to defend, independently `py_compile`-able. The other two heredoc-in-substitution-shaped
  blocks in the file were checked and are not affected: neither is nested inside a command
  substitution, so no closing `)` is ever scanned for while bash tracks their quoting. Also added an
  explicit end-of-run check that the report file is non-empty (`docs/quality-scan.sh` used to reach
  its final `cat` step even when nothing upstream had written anything), and a generalised `bash -n`
  gate (`scripts/tests/test_shell_script_syntax.py`) over every shipped script under `scripts/*.sh`
  and `scripts/lib/*.sh`, so the next unparseable script fails the suite instead of shipping quietly
  — the same enumeration `test_external_tool_exit_status.py` (WI-0054) already uses for the same 15
  files. `scripts/tests/test_quality_scan.py` pins that the script actually runs end-to-end across
  multiple scopes against a scratch fixture project (never this repository's own `docs/`), including
  a mutation proof that reintroduces the exact pre-fix construct in a scratch copy and confirms both
  the syntax gate and a real run reproduce the measured pre-fix symptom.
- **`/cleanup`'s unparseable-inbox-line rule rejected the shipped template's own blockquote
  lines.** §1a excluded blockquote lines from the check by requiring a trailing space after `>`,
  but `templates/HANDOVER_TEMPLATE.md` uses bare `>` lines (no trailing space) as paragraph
  separators inside the Open Points blockquote — two of them. An agent following the prompt
  literally would report a false positive on a freshly initialised HANDOVER. Fixed the rule to
  match a bare `>`, and the test mirror now derives the exclusion prefix from cleanup.md's own
  wording instead of a hardcoded literal, so the two cannot drift apart again undetected.
- **`memory-sync.sh promote` published its destination path without checking it.** The discipline
  gate examined the source file's *content* and then wrote the *destination* into a commit message
  that was pushed — so a file with clean content could still carry a tenant name into the shared
  repository through its filename, where it survives deleting the file and only a history rewrite
  removes it. This was the one irreversible path in the tool; everything else the gate protects is
  local. The destination is now checked against the same deny-list before anything is fetched,
  copied, staged or committed, and a match **refuses** rather than warns. Review then found the check
  was bypassable — a directory destination made `cp` append the source's own filename, so the string
  checked and the string published were different strings. Directory destinations are rejected as a
  usage error, which is what the documented contract always said, and that equality is now the reason
  the guard exists. Also fixed with it: ASCII-only case folding, NFC/NFD normalisation on macOS, and
  a missing `--` that let a destination named `--all` sweep unrelated files into the push. A later
  refinement closed one more shape: a destination whose name reads as a command-line flag (`--all`,
  `-n`, or a nested component like `instincts/-n`) exited 0 and published a file literally named
  that — not a leak by itself, since every consumer already treats the destination as a path
  regardless of a leading dash, but a file named that way reads as a flag again to any tool that
  later globs the directory it landed in. `require_file_destination` now refuses it the same way it
  already refuses `.`, `..` and a trailing slash, naming the actual mistake ("looks like a
  command-line flag") instead of reusing the directory-destination message.
- **`memory-sync.sh` failed on macOS's bash in its own usage hint.** `promote` without a destination
  printed `bad substitution` instead of the hint: the message interpolated a bash-4 lowercase
  expansion, and macOS ships bash 3.2. The error path errored. A sweep over all 22 tracked shell
  files found this as the only occurrence, and a regression test now guards everything a user runs.
- **`memory-sync.sh` let a failed `git clone`/`fetch`/`push` print the repository URL straight to the
  terminal, unmasked.** Every line the script emits itself goes through the same deny-list + `$HOME`
  mask `say()` uses — but git's own transport error text never passed through that function, and a
  failing clone or fetch prints the repository URL verbatim, which is exactly where a configured
  tenant/project name lives. Fixed by capturing the subprocess's stderr and re-emitting it through
  `die()`, the same mask path, instead of leaving it alone: the token git injects into the URL for
  auth was already confirmed to be stripped by git itself before this reaches the capture, but the
  host and repository path were not, and now are. Capturing a command substitution's own exit status
  on the same statement (`out="$(cmd 2>&1)" || rc=$?`) keeps a transport failure fatal — piping the
  capture into the mask would otherwise have reported the mask's exit status instead of git's.
  Note one deliberate behaviour change that follows: a transport failure now exits **2**, the script's
  own documented hard-error code, where it previously aborted with git's raw status (measured: 128 for
  a refused connection). The old status was never part of the contract the file's header states
  (`Exit: 0 ok, 1 gate/soft failure, 2 hard error`), so this aligns the script with its own promise —
  but a CI job keyed on 128 rather than "non-zero" will see the difference.
- **`memory-sync.sh`'s push gate read an internal scan failure as a clean file, not as a check that
  never ran (WI-0036).** `run_gate` tested whether `gate_scan_file`'s *output* was empty rather than
  consuming the exit status the function's own header comment already promised callers — a promise
  nothing was reading. An internal failure inside the scan (not "no findings", but "the check did
  not complete") produced the same empty result as a genuinely clean file. `run_gate` now captures
  `gate_scan_file`'s real exit status: an internal failure now reads as dirty where it previously
  read as silently clean, the safe direction for a push gate — fail closed, not open. Verified the
  ordinary paths are unaffected: a clean file still exits 0, a file carrying a bearer token still
  exits 1. The real behaviour change: a broken gate now blocks a push instead of waving it through.
- **`/p5-polish` wrote its `handover`-triage items into a section that did not exist.** It has always
  instructed agents to record blocked items in `docs/HANDOVER.md` "under Open Points", but no shipped
  template ever contained that heading — the flow dangled unless a project invented the section itself.
  The inbox now provides the destination, and `/p5-polish` writes the same entry format the `/cleanup`
  triage reads, so producer and consumer finally agree.
- **HANDOVER's Next Steps extraction no longer matches a field written mid-line (WI-0024).** The
  inbox WI-0002 added works only because the shipped template places `## Open Points` below
  `## Next Steps` — an unanchored `re.search` in `next_steps.py` picks the first match anywhere in
  the document, so an inbox finding whose text happened to contain `Next Steps:` followed by a
  `/command` reference could be read as the real next step. The extraction is now anchored to line
  start (`re.MULTILINE`), which makes the section order irrelevant instead of protected by
  convention. The narrowing is the fix — a field written mid-line
  (`Status ok. **Next Steps:** ... /cmd`) is no longer matched, only the line-start form and the
  `## Next Steps` heading are. The shipped template already uses the heading form, so nothing CCPR
  ships relies on the old match, but the change is silent for a hand-maintained HANDOVER.md that
  wrote its Next Steps field mid-line.
- **`instinct-check.sh` now actually counts instincts.** It reported `Active instincts: 0` in every
  project while hundreds existed. Three independent causes: (1) it counted `### ` headings in
  `~/.claude/instincts.md`, but under the split layout the index holds only bullets — the entries live
  in `instincts/{theme}.md`; (2) heading level is not uniform across the ecosystem (global topic files
  use `### G-100`, project Tier-2 persona silos use `## BA-P-001`), so entries were invisible depending
  on the layer — counting is now anchored on the instinct ID and accepts H2 and H3; (3) the script
  aborted with `unbound variable` on bash 3.2 (the macOS default) whenever a glob matched nothing,
  because `"${arr[@]}"` on an empty array trips `set -u`.
- **`instinct-check.sh` reported a stale age.** File age came from the index mtime alone, so editing a
  theme file without touching the index left the age unchanged. It now uses the newest mtime across
  the index and all theme files.
- **`doc-volume-check.sh` printed a broken report line and a stream of shell syntax errors for any file
  without an H2 heading (WI-0101).** `grep -c` PRINTS `0` and STILL exits 1 when nothing matched, so
  `h2_count()`'s `|| echo 0` arm fired on top of that printed zero and the function returned `"0\n0"`.
  Both `(( ))` tests in `split_suggestion()` then aborted with `((: 0\n0: syntax error in expression`,
  and the report line broke mid-sentence: `... (46 KB) → no obvious splitting point (0` on one line, the
  rest on the next. Against this repository's own `docs/` that was 8 lines on stderr and 2 truncated
  bullets. The arm now REPLACES the value instead of adding one
  (`count="$(grep -c ... )" || count=0`), the same shape `bootstrap.sh` already ships for the identical
  grep call.

  **What did NOT change is the verdict.** Both arithmetic tests failed, so the branch fell through to
  the `else` arm — and "no obvious splitting point" is the correct advice for a file with no H2 section
  to split at. Every file in a before/after run against `docs/` keeps its size band, its KB figure and
  its suggestion; the exit code stays 2. Only the rendered line and the stderr noise changed, which is
  why this is a PATCH under ADR-0001 ("bug fix in scripts ... that does not change any rule") even
  though the script is shipped. It matters because `/cleanup` §5 puts this output in front of a human
  reader, and a sentence that stops mid-line is a defect that reader sees.

  The script shipped with no test of its own; it now has one (`scripts/tests/test_doc_volume_check.py`),
  covering both sides of the defect's precondition — a zero-H2 file across all three size bands, an
  H3-only file (the shape that surfaced it), and H2-carrying positive controls that a fix which simply
  stopped counting could not pass.

### Performance
- **check (n) reads every index TWICE, unconditionally — including indexes with no reference definition
  in them at all.** This is the cost of the two-pass extractor (WI-0093): the awk program is invoked as
  `awk '...' "$INDEX_FILE" "$INDEX_FILE"`, so both the file I/O and the whole block machine — fences,
  HTML blocks, comments, the paragraph buffer, `protect_link_destinations()`, `resolve_paragraph()` —
  run a second time on every index, whether or not pass 1 found a single label. Measured on this repo
  (macOS 26, BSD awk 20200816, `LC_ALL=C`, median of 25 runs): a 46 KB persona index goes from 24.7 ms
  to 50.7 ms (factor 2.05, +26 ms); a 1.8 KB index from 3.5 ms to 4.5 ms, where process startup
  dominates. Across all five indexes in this repo, 54.6 ms -> 103.0 ms per lint run (+48 ms, factor
  1.88) — and **none of those five contains a single reference definition**, so the entire second pass
  is dead weight here today. It is accepted rather than optimised: a "skip pass 2 if refmap is empty"
  shortcut would need pass 1 to be trustworthy about a document it has not finished classifying, and a
  cheap pre-scan for definition-shaped lines is exactly the second block implementation the two-pass
  design exists to avoid. Recorded so the trade is visible if an index ever grows to a size where it
  matters.

### Added
- **A second round against check (n), on ground the first never touched (WI-0005).** The corpus grew
  26 → 44. Eight new divergences, and the interesting part is what they group into rather than the
  count. Five are one cause: the extractor tracks fenced code and HTML *comments*, but neither
  indented code blocks nor the other HTML block types — both contexts where CommonMark parses no
  inline content, so a link written there is not one. An index file is exactly the document that
  explains its own link syntax, which is why fence tracking exists at all; indented and
  HTML-wrapped examples are the same habit in a different notation. Two more are a **decision, not a
  defect**: an unused reference definition creates no link under CommonMark, but check (n)'s purpose
  is narrower than conformance — whether the index still points at files that exist — and a
  definition naming a vanished file is a dangling pointer nobody sees in the rendered document. The
  last is a false negative on CRLF blank lines, measured at zero occurrences today but not idle:
  this framework ships with Windows install guidance. Filed as WI-0084, WI-0085 and WI-0086. Eight
  further construct classes measured clean and kept as regression pins, including shortcut and
  collapsed reference links, block quotes, headings and emphasis in link text.
- **Sprint-review reports get a decided header schema (WI-0072).** `/p5-review-sprint` prescribed
  nothing more than "record the reviewed range in the report header" — measured in the field: five
  different header shapes across two real projects, including a bare `key: value` body with no `---`
  block at all (NutriMatch, 4/4 files) and a project that had already written itself a convention
  document reacting to the same drift. `commands/p5-review-sprint.md` now prescribes YAML frontmatter
  (`kind: review`, `sprint`, `base_commit`, `reviewed_head`, `reviewer`, `last_updated`) in its write
  step and repeats it as a `## Result` acceptance criterion, mirroring `constitution.md`'s pattern.
  `templates/REVIEW_REPORT_TEMPLATE.md` is the skeleton. `phase-docs-lint.sh`'s `reviews` profile
  gains a required-fields check that fires **only** once a document self-identifies via `kind: review`
  — structural backward compatibility, not an assumed one: not one document in the three reference
  projects carries that literal value today, measured before and after the lint change. The base-of-
  reviewed-range field is validated as `base_commit` **or** `reviewed_base` — both already accepted,
  equally validated names in the pre-existing commit-anchor-family check — not `base_commit` alone;
  the template and command still prescribe `base_commit` for new reports (one form, not a choice), the
  alias exists purely so a corpus that already wrote `reviewed_base` under this exact schema is not
  forced into a rewrite. A migration script (`scripts/migrate-review-headers.sh`) backfills
  `kind`+`sprint` onto the exact `SPRINT-<N>-review.md` shape only — never the suffix variants.
  RECONSTRUCTING `base_commit`/`reviewed_head`/`reviewed_base` (inferring a value that is genuinely
  absent) stays forbidden — a wrong guess there lets `/gate-p5` treat a stale review as current, worse
  than the avoidable re-run a missing field costs — but MOVING a value the author already wrote is not
  a guess: a bare `<key>: <value>` body line for one of those three keys, matched only at the exact
  start of a line, is hoisted into frontmatter (the body line itself is never removed; a pre-existing
  frontmatter value is never overwritten, and a body value that contradicts one is reported, not
  silently dropped). `kind: review` is only ever set once every required field is present, counting
  both what the file already had and what this run just hoisted — a document that would still fail
  the required-fields check immediately after being marked is left unmigrated and reported by name
  instead, so a clean lint run never turns into a permanently red one with no path back. The script
  creates the frontmatter block itself where none exists, since `fm_set`/`fm_set_many` refuse to write
  into a file that has none. Running it against the real erfinderwerkstatt corpus caught a live defect
  before any file was written: its zero-padded filenames (`SPRINT-03-review.md`) compared as a string
  against the project's own unpadded `sprint: 3`, producing a false conflict warning — fixed via
  base-10 arithmetic normalisation (`10#$n`, not a bare leading-zero literal, which bash reads as
  octal). A second run against the same corpus then caught the reconstruction-vs-moving conflation and
  the missing base-field alias above (22.08.2026 correction) before either had reached a shipped
  commit. A third pass, still before any commit, caught two more defects in the hoist step itself: a
  fenced code block illustrating the header schema (`commands/p5-review-sprint.md` is itself an
  example) was hoisted verbatim as if it were a real value — `reviewed_head` is exactly the field
  `/gate-p5` trusts for staleness detection, so a wrongly hoisted example is worse than a missing
  field — fixed with two independent checks: fence-tracking in the body extractor (mirroring
  `memory-lint.sh`'s own fence state machine) and a commit-SHA shape check (`^[0-9a-fA-F]{7,40}$`, the
  same form `phase-docs-lint.sh` already enforces) on whatever a fence gap lets through. The other two:
  the script's own temp-file write and the final `mv` into place were both unchecked — a write or move
  failure left an unexplained orphaned file in the caller's project tree with no error message tying
  it to what happened; both are now checked and named in the failure message, mirroring `fm_set`'s own
  write guard (`scripts/lib/frontmatter.sh`, which gained the equivalent `mv` check for the same
  reason).
- **A differential corpus measures check (n) against the CommonMark reference (WI-0005).** The
  promotion of the memory index's dead-link check from `warn` to `err` has been held three times on a
  criterion that is a **rate**, not a state — "a round that produces no new items" — and no round had
  been run since the last fix, so the criterion was neither met nor missed but untested. It is tested
  now. 23 constructs the six previous rounds never touched, each frozen with the reference parser's
  answer in `scripts/tests/fixtures/`, and a test that compares check (n) against that table **without
  importing the parser** — the suite has no third-party dependency, and a `skipIf` on a machine
  without the module would be silently green by skipping, which is the failure this repo keeps
  finding. Divergences are held as named `known_divergence` entries carrying their direction and work
  item, so they are counted rather than tolerated, and any behaviour change trips the test in both
  directions. That turns the promotion criterion into something measurable instead of remembered: a
  round with no new items now means the corpus grew and no new divergence appeared.
- **ADR-0009 is `accepted`.** Decided 18.08.2026, implemented across WI-0019…WI-0022, and completed
  by three addenda: the first correcting nine of its own statements against the shipped code before
  anything was built, the second resolving where the scope anchor lives, the third settling
  acknowledgement authority. Package B is closed.
- **Acknowledgements record who made them (ADR-0009 Addendum 3, WI-0022).** The ADR's fourth open
  point asked what acknowledgement authority means with more than one maintainer. The question hides
  two: *who made this assertion* and *who is allowed to*. This framework has no server and no
  enforcement point, so restriction could only ever be a convention — and a check that reads as
  enforcement without being it is exactly what this ADR refuses to do for agents. So: **record the
  actor, do not restrict them.** A sixth flat key `anchor_ack_by` joins the acknowledgement group in
  the same atomic write, filled from the repository's git identity and overridable with `--by`.
  Identity is keyed on **`user.email`**, and that is the substance of it: in the larger reference
  project two people appear under five display names while their addresses stay stable, so keying on
  the name would have recorded the drift instead of the person — verified, two names on one address
  collapse to one actor. Where no identity is configurable the field says so explicitly
  (`unattributable <no-git-identity>`, deliberately without an `@` so it can never be mistaken for an
  address) rather than being omitted, because a missing field and an unattributable acknowledgement
  must not look alike. And `anchor status` breaks its `asserted` count down by actor once more than
  one appears — the design's guard against acknowledgement becoming ceremony was always the statistic
  rather than a permission, and this is what carries that guard into a team. A test pins the
  **absence** of an authority check, so the decision cannot be quietly reversed into one.
- **The Manual documents the anchor, and a dormant CI template ships beside it (WI-0021).**
  `Manual/system/anchored-state.md` explains the mechanism the way the other `system/` chapters
  explain theirs — the problem, why the anchor sits on the phase index rather than on each document,
  why severity reads the document's own `status`, why the check is two-stage, and what "not verified"
  means — with each design choice carrying the measurement that settled it rather than an assertion.
  It states the agent clause's limit as plainly as the skill does. `templates/ci/anchor-check.ci.sh`
  follows the shipped precedent: POSIX `sh`, no forge named, nothing runs until someone wires it up.
  Two constraints are in its header because leaving them out would produce the message nobody reads:
  **CI can only do stage 1** — the judgement needs an agent, so the template reports a delta and is
  explicitly not a substitute for `/anchor` — and `check` **exits 0 with drift by design**, so a job
  reading only the exit code would report nothing, ever. It therefore reads the output, and says why.
  A run where every scope reports "not verified" is called out rather than passing quietly.
- **`/anchor` — the skill that turns the mechanical delta into a verdict (WI-0021).** Stage 1 is the
  script call and carries no severity; Stage 2 asks one narrow question per affected document — *does
  this delta invalidate a statement here?* — scoped to the changed paths rather than to the whole
  document, which is what keeps the common case (stale) from drowning the rare one (invalidated).
  Severity comes from the document's **own** `status`, never the index's. A confirmed invalidation at
  `active` or `frozen` opens one work item through the existing contract — no contract change — and a
  project that has not adopted the structured store gets the finding in its HANDOVER inbox instead.
  Every run closes with the acknowledgement statistic, because ADR-0009 requires it as the detector
  against the mechanism becoming ceremony. The skill states the exit-code contract explicitly, since
  `check` exits 0 **with** drift and non-zero only on an operational failure — read the other way
  round, a broken run would look like a clean one. The agent clause is binding and stated without
  varnish: `ack` refuses its interactive prompt without a terminal, but the flagged path needs none
  and nothing stops an agent with shell access from calling it, so the clause is prevention, the
  statistic is detection, and only both together are honest.
- **`/cross-check`'s R6 says what it does and what it does not.** The rule is titled
  "CONSTITUTION.md (Inviolable) ↔ ADRs / **Implementation**" and has never opened a code file — the gap
  that prompted ADR-0009 in the first place. Rather than bolt a code rule onto a Markdown-to-Markdown
  checker, R6 now names its own limit and points at `/anchor` for the half it does not cover.
- **`fm_set` and `fm_set_many` in `scripts/lib/frontmatter.sh`** — the first write path in a library
  that was read-only, and now the only in-place writer in the shipped scripts. Temp file in the same
  directory plus `mv`, never `sed -i`; scanning stops at the closing `---`, so the body is left
  byte-for-byte alone; a file without frontmatter is an error rather than a silent create; setting the
  same key twice is byte-identical. `fm_set_many` writes a whole group of keys in **one** awk pass and
  **one** rename, which is what makes an acknowledgement atomic as a unit rather than only per key.
  Four hardening fixes came out of review, three of them confirmed at the terminal before being
  believed: values reach awk through `ENVIRON` rather than `-v`, because `-v` applies escape
  processing — `awk -v v='a\nb'` yields a string of length **3** containing a real newline, so a
  reason mentioning a Windows-style path would have broken the frontmatter block one processing stage
  after the guard that exists to prevent exactly that; the original file's mode is carried onto the
  temp file before the rename, since `mktemp` creates at `0600` and a document checked out at `644`
  was silently becoming `600` on every write; a source file without a trailing newline keeps none,
  because awk's `print` adds one regardless; and keys are matched literally rather than as a regex.
- **`anchor set` and the freeze hook (WI-0021).** `freeze-phase-docs.sh` now writes `anchor_commit` and
  `anchor_date` onto the phase index — the one file it deliberately skips for `status:` — after
  freezing that phase's detail files. **It writes only when no anchor is there yet.** A second gate
  pass leaves the existing anchor alone and says so, because refreshing it silently would clear every
  accumulated drift without anyone having seen it, and ADR-0009 names that the highest-risk detail in
  the whole design. Verified end-to-end and by mutation: adding `--force` to the hook's call moves the
  anchor, wipes the drift, and turns exactly one test red.
- **`anchor ack` — the acknowledgement verb.** Renders the delta **before** it clears it, then writes
  five flat keys: the new `anchor_commit`, `anchor_date`, `anchor_ack` (`asserted` or `updated`),
  `anchor_ack_from` (the **old** SHA), and `anchor_ack_note`. `asserted` and `updated` stay separate
  fields on purpose — collapsing them would destroy the ability to ask later which anchors rest on
  nothing but an assertion, which is exactly what `anchor status` counts. A reason is mandatory in both
  the flag form and the interactive one; there is nothing to acknowledge without a delta, and the verb
  refuses then. Reach is declared structurally by the target file: an index is a bulk acknowledgement,
  a document with its own anchor is not. Measured: the acknowledgement counter really moves from 0 to
  1, so the detector against the mechanism turning into ceremony is live rather than planned. On a
  non-terminal stdin the interactive form reads EOF as **abort** and writes nothing — but a pipe does
  drive it, so the prompt is no barrier to a script or an agent. That is the ADR's own position: this
  harness has no hard boundary, so agents are kept out by an explicit clause plus the visible
  statistic, and the prompt is not a gate. Three review findings hardened it: the five keys are one
  atomic group write (an interrupt after a per-key `anchor_commit` would have left a document with a
  fresh anchor and no acknowledgement, which the status report reads as clean — drift gone with no
  record it was ever cleared, the exact failure ADR-0009 calls its highest-risk detail); a target
  outside the eight phase scopes is refused, because acknowledging one there succeeded while staying
  invisible to the very statistic that is the design's only detection fallback; and a non-terminal
  stdin without `--assert`/`--update` fails fast instead of blocking on a prompt nobody can answer.
  `anchor set` returns a distinct exit code **3** for "already anchored", so the freeze hook reads a
  contract rather than grepping another script's error text.
- **`scripts/anchor.sh` — stage 1 of the anchored state check (WI-0021).** `anchor status` and
  `anchor check` compute the delta between a recorded `anchor_commit` and the last **production-code**
  commit, and nothing else: no severity, no verdict, and **exit 0 whenever data was produced**, drift
  included — a non-zero exit means an operational failure only. That is the property the whole design
  rests on, since the event that fires constantly (staleness) must never reach the user as a verdict.
  The comparison point is not `HEAD`, because a third to a half of commits in real projects touch only
  documentation. Every report names the classification in force and its source, and **how many of the
  eight phase folders were actually found** — without that line, "0 anchored" on a project with no
  phase folders reads exactly like a fully anchored, drift-free one. Anchor resolution is the
  document's own before the index's, in both subcommands, so a document whose own anchor is current is
  not reported as affected; a scope with no index still reports its own-anchored documents rather than
  swallowing them, which matters because `quality/QA.md` is absent in all three reference projects
  while the folder exists. Six git edge cases are data, not crashes: no repository, shallow clone,
  unresolvable anchor, detached HEAD, dirty tree, and a repository with no commits. `ack` and `set` are
  explicit stubs for the write path. Three bugs were found while building it, each reproduced before
  it was fixed: `git log --pretty=format:` omits the trailing newline, so `while read` silently drops
  the last entry — invisible except in the single-commit case, i.e. exactly a `--depth 1` clone;
  a `[[ cond ]] && assignment` as the last command of a function leaves that function's exit status
  non-zero and kills the script under `set -e`; and `"${arr[@]:-}"` on an empty array in bash 3.2
  yields one phantom empty element rather than none — a silent wrong answer, distinct from the known
  crash on a bare `[@]`. 47 tests, suite 958 → 1020.
- **ADR-0009's one open design question is decided (Addendum 2).** The ADR anchors at the Gate-Go
  freeze and makes the scope index carry the bulk acknowledgement, while `freeze-phase-docs.sh` skips
  every index by design — so the freeze event could not write the anchor the design puts there. The
  scope anchor now lives on the **phase index**, written by a second, deliberate write path in the
  freeze; documents inherit it, may opt into their own, and **severity reads each document's own
  `status`, never the index's**. Three measurements settled it. The index's status is not
  machine-guaranteed: in one reference project all five phase indexes carry `frozen` although the
  freeze script skips them by name, so keying severity off the index would make every finding in that
  project error-grade and none in the other two. An index may be absent — `quality/QA.md` is missing in
  two of three projects while the folder exists — which resolves to the ADR's own "not verified" state
  rather than to silence. And the naming convention holds where an index exists, so the scope resolves
  by convention instead of by a registry, which would have been the second register the ADR rejects.
  The alternative — anchoring each frozen detail file — was cheaper to build and fails on coverage: the
  freeze runs only on a Go verdict, and at frozen shares of 12 %, 6 % and 90 % most documents would
  never receive an anchor. On the index, one gate pass per phase anchors the whole scope. Also settled:
  the comparison point is the last **production-code** commit, defined by **exclusion** (not under
  `docs/` or `.claude/`, not a Markdown file) because that travels between projects while a list of
  code directories does not — measured, it lands 1, 2 and 6 commits behind `HEAD` in the three
  projects, which is exactly the documentation-only base rate the design exists to defuse.
- **`covers:` — an optional, lint-validated list of the code paths a phase document describes
  (WI-0020).** Resolved against the **project root** only, with no document-relative fallback: these
  are code paths, not doc references. A path that does not exist is an error; a path that exists but
  contains no file at any depth is a warning, because ADR-0009 requires that a list which has quietly
  stopped covering anything cannot report clean — the first implementation answered "does this
  directory contain any entry", which let a tree of empty subdirectories pass, and now answers "does
  this path cover any code". A directory whose only content is a `.gitkeep` counts as covered; that is
  a deliberate non-decision recorded in place, since treating dotfiles specially is a rule nobody made.
  The check runs in every profile because it is purely opt-in — measured: `covers:` appears zero times
  across three real projects, so it costs a project nothing until it adopts the field.
- **The commit-anchor family CCPR already writes is validated (`base_commit`, `reviewed_head`,
  `reviewed_base`).** `/p4-sprint` writes `base_commit`, `/p5-review-sprint` records `reviewed_head`,
  and `/gate-p5` compares it against `HEAD` to decide whether a sprint review is stale — a recorded SHA
  on a phase document spanning a delta, shipped for months and never checked. In the field: 34
  documents across two projects, roughly ten spellings, none validated. When one of the three keys is
  set, the form is now checked (7–40 hex, error) and, inside a git repository, whether it resolves to a
  commit (warning — a shallow clone, a rewritten history or a foreign SHA are legitimate misses).
  Measured before shipping: all 47 occurrences are well-formed and resolvable, so the check costs zero
  findings today. The repository test initially missed linked worktrees and submodules, where `.git` is
  a **file** — the same unresolvable SHA warned in a main repo and stayed silent in its worktree.
- **`phase-docs-lint.sh` has test coverage for the first time (`scripts/tests/test_phase_docs_lint.py`,
  28 tests).** 207 lines that every CCPR project runs, shipped with nothing but the generic `bash -n`
  sweep and the exit-status inventory pointing at it. Two work items are about to change this exact
  script — a per-directory check profile and a new `covers:` check — so the surface those changes get
  measured against had to exist first. Covers all seven checks (a)–(g) individually with a negative
  control beside each, every required field on its own, **every** value of both enums separately
  (`P0`…`P8`, and the six statuses), both `related:` list syntaxes, all six `LIVING_FILES` names, the
  exit-code precedence, the report's own counts, and the argument edge cases. Every test was seen red
  through a mutation of the **script** — never by deleting the assertion — and the mutations were
  restored byte-identically (md5-checked). Two of them are deliberate boundary **pins** rather than
  requirements, and say so in place: today a document outside the eight `PHASE_FOLDERS` produces no
  finding by default, and `--scope` **does** reach it, because the two collection paths differ (the
  scoped one walks all of `docs/`). The upcoming profile work rewires exactly that switch, so both
  sides of the fence are now marked and it cannot move unnoticed in either direction.
- **ADR-0009 gained an addendum before a line of it was implemented (21.08.2026).** The decision was
  written from measurements on two CCPR-driven projects; re-measuring against three, and against the
  shipped scripts rather than their descriptions, falsified nine statements. The two that change the
  work most: the `status` enum is **already** enforced hard — check (d) errors and the script exits 2,
  and does so today against a real project — so the precondition is scope plus correction, not stricter
  validation; and **the anchor already exists under other names, written by CCPR itself** —
  `/p4-sprint` writes `base_commit`, `/p5-review-sprint` records `reviewed_head`, `/gate-p5` compares
  `reviewed_head` against `HEAD` as a staleness detector, across 34 documents in two projects and
  roughly ten unvalidated spellings. That is the same unvalidated-key rot the ADR cites as its warning
  example. `anchor_commit` stays a distinct key — a sprint base and a freeze point are different
  moments — but it now ships together with validation of the existing family, or the second-register
  objection would apply to its own field. Also corrected: the enum has six values, not five (`living`
  is in the schema and the linter; the five-value list in `CLAUDE.md` is the drifting statement), the
  frozen share is 90/12/6 percent across the three projects rather than one number, `covers:` is not an
  extension of the `related:` check (different base, different node type), and the `covers:` decay rate
  is understated by roughly a factor of five. One open design question is named rather than papered
  over: `freeze-phase-docs.sh` skips every index, so the freeze event cannot write the scope-level
  anchor the design puts there. **Design only — still no shipped surface changes.**
- **Every external-tool invocation in the shipped shell scripts is now pinned to a consumed exit
  status (`scripts/tests/test_external_tool_exit_status.py`, WI-0054).** Three prior rounds
  (WI-0049, WI-0051, WI-0053) closed one recurring defect — a crashing `grep`/`sed`/`awk`/`python3`/
  `git` read as "nothing found" instead of "this check did not run" — by enumerating call sites BY
  READING the source, and each pass kept missing at least one site the eye skipped. A new,
  self-contained shell scanner (no external parser dependency) re-enumerates every invocation in
  `scripts/*.sh` and `scripts/lib/*.sh` on every test run and asserts, in the positive form, that
  each one is either structurally checked (an `if`/`while` condition, a `$?`/`|| return` capture, a
  real `&&`/`||` chain) or carries an inline `# exit-status: exempt <category>` marker naming one of
  eleven shared, reasoned categories — so a newly added, unclassified invocation fails the very next
  run instead of waiting for a fourth sweep. Of 125 invocations found, 33 were already structurally
  checked and 92 needed a marker; two of those markers record a genuine, unfixed risk found while
  building the check (`bootstrap.sh`'s instinct-listing `grep` can abort the whole dashboard on a
  normal empty result; `log-cleanup.sh`'s log trim can silently replace a log with an empty file if
  `python3` crashes) rather than being silently absorbed as routine. The check's own docstring states
  its limitation plainly: it cannot see a status swallowed several call-frames up (WI-0053's own
  `gate_path_deny_index` site), only what it can see reading forward from each invocation.
- **CCPR can now gate its own shipped artifacts (`scripts/artifact-gate.sh`).** The Constitution
  forbids personal or tenant data in shipped artifacts, and that Inviolable was breached — a tenant
  project name sat in an instinct's rationale while the file's own header claimed such details were
  anonymised. Hand sweeps are what let it through. The existing memory gate could not simply be
  pointed at the repo: swept over 273 files it produced 77 files with findings and **zero** true
  positives, and it would not have caught the actual breach, because it has no concept of a tenant
  *name*. The gate is now split into a pattern library (`scripts/lib/discipline_gate.sh`) used by
  both entry points — `artifact-gate.sh` and `memory-sync.sh promote`'s destination check — with
  profiles selecting which checks run rather than what a pattern means. The generic 40-character
  rule — the source of every false positive — was replaced with shapes machine-generated credentials
  actually have, plus a dedicated check for a screaming-snake-case placeholder (`YOUR_TOKEN_HERE`,
  `TODO_INSERT...`) that would otherwise read as a bearer token or a keyword-assignment secret,
  scoped to those two checks only so a real vendor-shaped key (AWS's own `AKIA...EXAMPLE`) still
  fires unfiltered elsewhere. A deny-list of tenant and project names closes the real gap; it is
  read from personal config or an environment variable, never from the repository, matches are
  reported with file and line while the name itself is redacted from every emitted line (a CI log is
  a shipped artifact too), and it escalates to an NFC-normalised, case-folded comparison for a
  non-ASCII subject or name on both the path and — gated on the configured name only, so a pure-ASCII
  deny list costs nothing extra — the file content side; a fatally broken `python3` interpreter now
  falls back to the ASCII matcher with a warning instead of silently reading as a clean file. Every
  check the gate runs — the deny-list matchers, the shared scan-and-report loop, and the file-list
  filter — fails loudly (abort, exit 2, naming the check and the failing tool's exit status) if its
  underlying `grep`/`python3` call crashes, instead of the crash reading as "0 findings", "not text"
  (silently skipping a file already selected for scanning), or a narrower scan scope with no trace.
  A tracked symlink is treated as its own name rather than followed: a dangling one no longer drops
  out of the sweep silently, and a resolving one is never read through — its target's bytes are never
  opened, matching what `install.sh` actually ships for a symlink (the link itself, never its
  target); a `skipped_symlink` counter reports the count. The self-exemption that keeps the gate from
  flagging its own pattern definitions is bound to the resolved path of the one file that defines
  them, so an installed copy scanning a foreign checkout reports the reason a finding was not
  recognised as its own source, rather than unexplained "secret" findings. Ships with a dormant CI
  template (`templates/ci/artifact-gate.ci.sh`, syntax-checked and exercised against a fixture repo)
  that names no forge; its activation note correctly states that the sweep reads only
  `git ls-files`, not history, so a shallow checkout is sufficient. An unconfigured deny-list says so
  loudly instead of passing silently. The repo currently scans clean: 275 files, 0 findings.
- **The HANDOVER size cap is now watched automatically.** The ≤5 KB / 150-line cap was documented in
  the template and enforced by `/cleanup`, but nothing triggered it — the file drifted past its limit
  unnoticed until someone happened to run the command, and `doc-volume-check.sh` does not cover it
  (its thresholds start at 25 KB, five times the cap). `agent-monitor.py` now warns on session start
  and after any HANDOVER write, at **80 %** of the cap as well as above it. The threshold is derived,
  not chosen: one skill run was measured growing a HANDOVER by ~20 % of the cap, so a warning one
  run's growth below the limit is the last moment at which it is still preventive. The warning names
  the numbers and the remedy, and never blocks. `/cleanup` gained the matching level: at or above the
  threshold it *offers* to archive the oldest block, since the file is still legal there and declining
  is a valid answer. `/cleanup` reads the threshold from the hook rather than restating it, so the two
  cannot drift apart — and with no hook installed it falls back to its previous two branches instead
  of inventing a substitute value.
- **The HANDOVER template carries an append-only inbox (`## Open Points`).** Agents working mid-task
  keep finding things outside their assignment — stale docs, a missing check, a worthwhile follow-up —
  and the template offered exactly one collection point, the Open Decisions table. With only a decision
  table such findings either interrupt the task or are lost; this was reported from a productive
  multi-agent setup that has run its own inbox since July. Entries are one greppable line
  (`- INBOX | date | source | finding | ref`), triaged by a new `/cleanup` step into
  `backlog | decision | keep | drop`, with backlog items routed through the work-item adoption guard so
  a project with a ticket system gets a real item and a prose project gets a BACKLOG entry. Reaching
  the ceiling flags rather than blocks: refusing an append would reintroduce the loss the inbox
  prevents. `project-guide` surfaces the count; it may neither append nor clear.
- **`memory-lint.sh` now validates the Tier-1 index's own links, and every Tier-2 persona index's,
  catching a dead link nothing else in the lint saw (check `n`).** The lint checked
  cross-references in one direction only: it found memory files the index had forgotten (check
  `g`) and `related:` entries pointing at nothing (check `f`), but a link *inside* an index passed
  silently even when its target had been deleted. The check resolves every inline link
  (`[x](target)`) and reference-style definition (`[id]: target "title"`, all three CommonMark
  title delimiters — double quotes, single quotes, parentheses) against the file that carries it:
  the Tier-1 index (`docs/memory/MEMORY.md`) and every `docs/memory/{agent}/MEMORY.md` persona
  index (WI-0040) — a persona index carries far more links than the Tier-1 one, deep anchors into
  topic files, and nothing had validated those before. A relative target resolves against its own
  index's directory, not the Tier-1 memory dir; a leading `/` resolves from the project root.
  Comments and inline code spans are resolved paragraph by paragraph, left to right: whichever
  construct — an HTML comment opener or a run of backticks — opens first at a given position
  claims its whole span, and the other's delimiters inside it are literal text (WI-0048); either
  can cross a physical line break inside the same paragraph, stopping only at a real block
  boundary — a blank line, a list-item marker, a heading, a fence, or a block-level comment
  (WI-0050, WI-0052). A code fence or an HTML comment left open at end of file is correct
  CommonMark — the rest of the document genuinely is inside it — but the check no longer lets that
  silently shrink its own scope: both now emit their own warning naming the line where the
  construct opened, independent of severity (WI-0032, WI-0043). Images, in-page anchors and
  external URLs are skipped, correctly — none of them is a link to a file in the repository. A
  destination in CommonMark's angle-bracket form (`[x](<target.md>)`) is unwrapped and resolved like
  any other target (WI-0060, fixed after this entry originally shipped) — the reference parser reads
  it as an ordinary link to a file, so it belongs with the checked forms above, not with the skipped
  ones; an UNCLOSED opener (`[x](<target.md)`) stays skipped, because the reference reads that as
  literal text, not a link. This is a floor, not a full fix: it catches a target file that no longer
  exists, not a wrong anchor into a file that does — anchor resolution needs heading-to-slug
  modelling and is a separate, unbuilt item. Shipped
  at **warning** severity by default; `MEMORY_INDEX_LINK_SEVERITY` is the knob, validated up front so a
  bad value reports a configuration error (exit 3) instead of aborting with `command not found`
  (exit 127), indistinguishable from a findings result. **Corrected after this entry originally shipped
  (WI-0005):** both halves read the other way round in the shipped state. The default is `err` since
  24.08.2026 — the promotion this entry called "tracked separately and the SemVer-relevant step
  (ADR-0001)" is in THIS release, under `Changed` — and the documented escape hatch now points the other
  way, to `warn`.
- **First test coverage for a shell script in this repo.** `scripts/tests/` was Python-only and
  covered the work-item CLI; `scripts/tests/test_memory_lint.py` invokes `memory-lint.sh` as a
  subprocess with `HOME` redirected to a temp directory, so the checks against `~/.claude/**` cannot
  leak the developer's machine state into the result.
- **State verification design (proposed) — `docs/adr/ADR-0009-anchored-state-verification.md`.**
  `/cross-check` compares Markdown to Markdown in all seven rules — R6 even names "Implementation" in
  its title and reads no code — so a fully self-consistent documentation set can be stale against the
  implementation while every gate passes. ADR-0009 introduces an **anchor**: an optional, flat
  `anchor_commit` in phase-document frontmatter, one per scope by default with a lint-validated
  `covers:` opt-in for document-exact resolution. The check is two-stage — a mechanical delta that is
  never itself a verdict, then a scoped evaluation of whether the delta invalidates a claim — with
  severity keyed to the document's `status` (`living` info, `active` warning + work item, `frozen`
  error). Clearing drift is a dedicated `anchor ack` verb that renders the delta before it clears it
  and distinguishes a human assertion from an evidenced update; acknowledgement statistics ship as part
  of every check run so the mechanism turning into ceremony stays visible. Escalation goes through the
  existing work-item contract (ADR-0002) with `local` as default — **no contract change**, and no
  hosted service, so the check runs on a local git comparison. The field is optional by design: no
  existing project artifact becomes invalid. **Design only — no shipped surface changes yet;
  implementation follows.**
- **`instinct-check.sh` takes an optional `<project-dir>`** and reports all four instinct layers
  (global Tier-1 index + theme files, global Tier-2 persona silos, project Tier-1, project Tier-2)
  instead of only the global index. It also reconciles the index against the theme files: IDs present
  in a theme file but not listed in the index are reported as INFO (expected for frozen overlays such
  as `imported-*.md`), while index bullets with no matching entry are a WARNING — the index pointing
  at content that does not exist.
- **The docs/ framework-vs-working-state boundary is now machine-enforced on both sides
  (WI-0018).** `install.sh` shipped every tracked path under `docs/` wholesale, so this repository's
  own working state — 17 work items about CCPR's own defects at the time of measurement, since grown
  to 63 — would reach every user's `~/.claude/docs/` looking like their own state; a checkout carrying
  that state (any long-running contributor's own working copy, not only a stale pre-gitignore clone)
  landed 852 KB of it, exit 0, no warning. `scripts/lib/docs-framework-allowlist.txt` is a new file
  naming the five framework paths currently tracked (`adr/`, `logo/`, `CONSTITUTION.md`,
  `NEXT_STEPS_REFERENCE.md`, `PROJECT_PHASES.md`) and is the single source of truth for both sides —
  neither script keeps its own copy of the list, which is the shape that produced WI-0059 once
  already (an archive path held in a variable and again as a literal). `scripts/artifact-gate.sh`
  fails a newly tracked `docs/` path that is not on the list (`[docs-boundary]`, naming both remedies:
  add it to the allowlist if it is framework documentation, or to `.gitignore` if it is working
  state). `install.sh` now copies only the allowlisted entries out of `docs/` and reports what it
  skipped, by name and approximate size, naming the likely cause — including dotfiles/dot-directories
  (`docs/.handover-archive/`), which a plain `*` glob would otherwise drop from both the install and
  the report silently. This is a separate mechanism from the existing `PROTECTED` stash-and-restore
  concept: `PROTECTED` preserves the *target's* user-owned files across a wholesale directory replace,
  this skips *source*-side working-state files from ever being copied in the first place.
  **Follow-up fix, same day:** the `[docs-boundary]` rule fired on every repository `artifact-gate.sh`
  swept, not only CCPR's own — a project adopting CCPR and running the shipped gate against its own
  `--repo` was told its own `docs/README.md` and `docs/workitems/` belonged in `.gitignore`. Scoped by
  self-detection, mirroring the gate's existing pattern-source self-exemption
  (`_GATE_PATTERN_SOURCE` in `lib/discipline_gate.sh`, which resolves the gate's own file path to
  recognise itself): the rule now only applies when the repository being swept is the SAME repository
  the running gate script lives in (`_GATE_OWN_REPO_ROOT` / `DOCS_BOUNDARY_APPLIES`), no new flag or
  configuration. An installed copy under `~/.claude` — ordinarily not a git repository itself — is
  correctly inert against any `--repo` it is pointed at. Known, accepted gap: a project that vendors a
  copy of this script into its own repository and points `--repo` at itself satisfies the equality too;
  self-detection by location cannot distinguish "the same location" from "CCPR's project identity".

### Changed
- **`last_updated`'s date check was one rule hand-typed twice, and the two copies had never agreed
  (WI-0107).** `phase-docs-lint.sh` check (e) matched the `DD.MM.YYYY[ (note)]` shape and stopped
  there; `memory-lint.sh` check (e) matched the identical shape and then ran the value through a
  real parse (`date_to_epoch`, WI-0106/WI-0087). Consequence, measured 26.08.2026: a well-formed
  value that names no real calendar day (`32.13.2026`, `99.99.9999`) was accepted by
  phase-docs-lint.sh and rejected by memory-lint.sh — the exact drift both linters' own comments
  already admitted, in one implementation each. Both the shape check and the parse now live once,
  in `scripts/lib/frontmatter.sh` (`fm_date_shape_ok` / `fm_date_to_epoch`, the latter moved
  verbatim from memory-lint.sh's `date_to_epoch`, only renamed for the library's `fm_` prefix
  convention), sourced by both scripts.

  **`phase-docs-lint.sh` now rejects an impossible date, and that is a promotion (ADR-0001), not a
  write-down.** It turns content that lints clean today into an error, so the blast radius was
  measured before shipping it, not assumed: neither reference project's `docs/<phase>/**` store nor
  this repository's own carries a shape-valid-but-impossible `last_updated` value. `memory-lint.sh`'s
  behaviour is unchanged — same two messages (`not in format 'DD.MM.YYYY' or 'DD.MM.YYYY (note)'`
  for a shape failure, `cannot be parsed as DD.MM.YYYY` for a shape-valid-but-impossible date), same
  verdicts, pinned by the existing `LastUpdatedFormTest`. `phase-docs-lint.sh` keeps its single
  message for both failure modes, since it never distinguished shape from date in its report.

- **check (n) — a dead Markdown link in a memory index is an ERROR by default (WI-0005, ADR-0001).**
  `MEMORY_INDEX_LINK_SEVERITY` still ships as the single knob that decides it; only its default moves,
  `warn` -> `err`. **Scope, stated plainly, because it is wider than the Tier-1 index:** since WI-0040
  check (n) reads the Tier-1 index `docs/memory/MEMORY.md` **and every Tier-2 persona index
  `docs/memory/{agent}/MEMORY.md`**, and the persona indexes are where the links are. Counted in this
  repo: 7 link constructs in the Tier-1 index against 66 across the four persona indexes, 52 of them in
  a single one. A project meets this promotion on the persona indexes first.

  Per ADR-0001 this is the SemVer-relevant step in the whole check (n) series, because it is the one
  that **rejects content that was previously accepted**: a project whose index points at a file that no
  longer exists now exits 2 where it exited 1. **The class is MAJOR.** ADR-0001's MAJOR row is
  "schema-breaking change in memory or phase-docs", illustrated with *"changing `memory-lint.sh` to
  reject previously-valid frontmatter"* — this is the same shape one field over: the same script
  rejecting index content it previously accepted. It ships inside a `0.x` MINOR under ADR-0001's own
  pre-1.0 caveat (semver §4), which permits a MAJOR-class change on a MINOR bump below v1.0. Naming the
  class here so the release cut does not have to re-derive it.

  **The criterion, and why it changed.** Promotion used to wait for "a round that produces no new
  items". That criterion was replaced by PO decision on 23.08.2026 because it was shown to be
  unreachable rather than merely unmet — two probing rounds against ground no earlier round had touched
  produced eighteen divergences, and the construct classes were not exhausted. CommonMark is large and
  an awk extractor will always diverge somewhere. The criterion in force is narrower and matches the
  reason ADR-0001 sets a threshold at all: **no known FALSE-POSITIVE divergence**. Only a false positive
  rejects previously accepted content; a false negative rejects nothing and breaks no run.

  **What satisfied it, measured:**

  | Measurement | Result |
  |---|---|
  | Conformance corpus (`scripts/tests/fixtures/commonmark_corpus.json`) | 76 entries, **0 false-positive** divergences, 12 false-negative, 3 `documented_intent`. **The zero is over a corpus WI-0100 was deliberately kept out of** — see below: adding it unasked would have moved the very number this round was judged by, so that call was left to the PO and the class is named in prose instead of counted here. |
  | Corpus regeneration against the flipped script | **byte-identical** to the committed file — the flip does not touch the extraction, and the instrument is stable |
  | Field measurement | 18 real index files, **131 link extractions, 0** targets the reference does not render |

  **Effect on real runs today: none.** Measured on four inventories, old default against new default,
  same script, same moment, only the knob differing:

  | Inventory | Findings | Exit (old default `warn`) | Exit (new default `err`) |
  |---|---|---|---|
  | ccpr-gh | identical | 1 | 1 |
  | productdata | identical | 2 | 2 |
  | NutriMatch | identical | 1 | 1 |
  | erfinderwerkstatt | identical | 1 | 1 |

  check (n) contributes zero findings in all four, so there is nothing for the severity to reclassify.

  **The caveat, named rather than footnoted — WI-0100.** A bounded random probe over 3000 lines of
  bracket soup produces **210 findings the reference never renders**, 178 of which already reproduce
  before the WI-0080 bracket scanner. The minimal witness is `[](()`, which check (n) reports with a
  target named `(`. The cause is WI-0095: `protect_link_destinations()` spans the text after ANY `](`
  without checking that a live opener precedes it. This class is **reachable but not reached** — that
  is exactly what the field measurement says, and all it says. A promotion that hid a known
  false-positive class would be the thing ADR-0001's threshold exists to prevent, so it is stated here
  and in the source comment above the assignment.

  **What this flip is not.** It makes the check **louder, not complete**. The 12 false-negative
  divergences stay in the corpus, named, each with its direction and work item, and are fixed on their
  own merits rather than as a precondition for this line.

  **One consistency the flip repairs in passing.** The source comment over check (n) has read "severity
  is `MEMORY_INDEX_LINK_SEVERITY`, mirroring check (f)" since the check was written. Check (f) — a
  `related:` cross-ref pointing at a file that does not exist — reports `err`. Under the `warn` default
  the comment was simply untrue: the same defect, a reference to a file that is gone, was an error in
  one check and a warning in the other, decided by nothing but which field it was written in. The two
  agree for the first time.

  **And its actual reach, stated plainly.** Measured across this framework: the only consumer of this
  script's exit code is **`/cleanup`** (`commands/cleanup.md` §3), which turns it into a status word —
  "0 clean / 1 warnings / 2 errors" — and holds 3 apart as a configuration error to be treated as a run
  failure rather than a findings result. There is no hook, no CI job and no gate that treats exit 2
  differently from exit 1. Today this change moves one word in one report. It is still the right change
  — the signal should be true before anyone builds on it — but the entry should not promise more than
  it delivers.

  **What the null result does NOT cover.** The four inventories above are the ones this framework is
  run against; they are not a sample of anyone else's. A foreign store meets this promotion through two
  changes in the same release, not one: the false-negative fixes further up **add findings on content
  nobody touched**, and this line files them as errors. The combination moves such a store from exit 0
  to **exit 2** without a single file having been edited. The zero measured here says the four
  inventories carry no check (n) finding to reclassify — it says nothing about a store that does.

  **Migration, for a run this catches off guard:** `MEMORY_INDEX_LINK_SEVERITY=warn` restores the
  previous behaviour exactly, and that is measured rather than asserted — on a throwaway project with
  one dead index link, the shipped default yields 1 error / exit 2 and the override yields the same
  finding as 1 warning / exit 1. Look for the dead targets in the persona indexes
  (`docs/memory/{agent}/MEMORY.md`) as well as in `docs/memory/MEMORY.md` — check (n) has covered both
  since WI-0040, and the persona indexes carry the deep links. The escape hatch is documented where a
  reader hits the word "error": `commands/cleanup.md` §3 and the Memory Lint checklist in
  `Manual/system/memory-instincts.md` and `Manual/SYSTEM_OVERVIEW.md`.

  The knob is validated before any work happens, so a bad value still exits 3 (configuration error)
  instead of being mistaken for a findings result — and **an EMPTY value now reaches that validation**.
  `MEMORY_INDEX_LINK_SEVERITY=` used to take the default branch (`${VAR:-err}`) and land silently on the
  strict side of the promotion it was reaching to escape, exit 2, no message. It is `${VAR-err}` now: an
  empty string is not a severity, so it exits 3 and says so. Emptying a variable is the most likely
  wrong grip on a knob that has no off position.

  `test_the_shipped_default_severity_is_warn` was **rewritten, not deleted** — it exists so this default
  cannot move silently, and it did its job: it went red on the flip before anything else was touched. It
  is now `test_the_shipped_default_severity_is_err_and_warn_remains_reachable` and pins the escape hatch
  in the same test as the default it qualifies. Both halves were confirmed load-bearing by mutation
  (restoring the `warn` default, and neutering the `warn` dispatch branch, each turn it red). Restoring
  the `warn` default turns **exactly one** test in `test_memory_lint.py` red — that one — and leaves the
  42 corpus tests untouched, which is the design the severity/extraction split exists for.
  `test_an_empty_severity_is_a_configuration_error_not_the_strict_default` is new alongside it and pins
  the `${VAR-err}` half.
- **`phase-docs-lint.sh` scans `docs/reviews/`, with a check profile of its own (WI-0019).** The
  status enum was never the weak part — check (d) already errors and exits 2, and had been doing so
  unnoticed against a real project for months. What let invalid values survive is that the scan only
  ever visited eight hard-coded folders, and `docs/reviews/` was not one of them. Taking it in with the
  full check set was measured first and rejected: it yields 47 errors in one project and 54 in another,
  almost all "required field missing" against a schema review reports never followed — only 13 of 30
  carry all four required fields, and in a third project four carry no frontmatter at all. Review
  reports are a genre of their own; their schema is tracked separately. So `reviews` gets a profile
  that runs **only** the status enum, and only when `status:` is set — including silence on missing
  frontmatter, without which one project would have moved from a clean exit to exit 1. The profile is
  derived from the file's path **after** the two collection paths converge, so `--scope 'reviews/*'`
  and the default walk agree on the same file (measured: that invocation went from 47 findings to 6).
  Implemented as a `case` dispatch, not an associative array — the platform's `/bin/bash` is 3.2.
  Backwards compatibility was measured, not asserted, before and after on three projects: one stays at
  exit 0, one gains exactly the six invalid values it was hiding and no other finding class, one gains
  exactly one. A mutation that lets the frontmatter check into the reviews profile turns four tests red
  **and** moves the clean project to exit 1 — the regression the constraint forbids is caught by the
  suite, not only by the manual run.
- **The Handover-Epilogue "Open points"/"Open items" bullet, shipped identically in 104 command
  prompts, named a destination without saying which of the two `docs/HANDOVER.md` sections it
  meant.** The template offers two places for a mid-task finding: the `## Open Decisions` table
  (what the PO must decide about THIS command's own assignment) and the `## Open Points`
  append-only inbox (a finding made OUTSIDE the current assignment). The bullet an agent actually
  followed just said "Open points" (91 files) or, in a further 12 files (`gate-p7*`, `p7-*`,
  `p8-*`), "Open items" — same block, same position, same three-bullet shape, same ambiguity,
  different word; found while measuring the first 92, initially treated as a separate finding and
  folded into the same fix on review, since the defect is the missing destination, not the literal
  string searched for. `/cleanup`'s unparseable-line report made the resulting drift visible
  rather than silently absorbing it. No ADR: the Constitution's Inviolable triggers on a change
  that *invalidates* an existing project artifact, and naming a destination more precisely
  invalidates nothing — settled against the volume of files touched, not the wording. 103 files
  carried a bare bullet, one (`p5-review-sprint.md`) a suffixed sibling keeping its own
  CRITICAL/HIGH qualifier; all 104 now name the `## Open Decisions` table for a PO decision and
  the `## Open Points` inbox for an out-of-scope finding explicitly, applied as two scripted
  substitutions (not 104 hand edits) with a five-point integrity proof run over each tranche:
  before/after occurrence counts, `git diff --stat` at exactly 1 insertion + 1 deletion per file,
  a diff-line filter proving no neighbouring line moved, and a byte-count delta check per file.
  Pinned by a new `scripts/tests/test_handover_epilogue_bullet.py`, which asserts the positive
  form (every Handover-Epilogue "Open ..." bullet is the disambiguated wording or the one, named,
  genuinely unrelated `specialize.md` exception) rather than merely the old string's absence — an
  allowlist for files carrying the same defect the test exists to prevent was rejected as reading
  like a sanctioned exception rather than a gap.

## [0.2.1-beta] - 2026-07-10

### Fixed
- **Instincts are now actually loaded at session start.** CLAUDE.md claimed the index was "loaded at
  session start", but Claude Code does not auto-inject `~/.claude/instincts.md` — it injects CLAUDE.md
  files and imports. Added an `@instincts.md` import to the shipped CLAUDE.md so the slim index (native
  + shared org-tier bullets) is really pulled into context each session; theme files stay on-demand.

### Changed
- **`memory-sync.sh pull` now lists the shared instincts in the autoloaded index.** The `{ORG}`-tier
  index block previously held only a pointer to the overlay topic file, so a session-start reader saw
  *that* a shared set exists but not *what's in it* — no trigger to load it. `pull` now generates a
  one-liner bullet per `### <ID>: <headline>` (with confidence) into a delimited, self-updating block,
  matching the visibility of native/imported instinct sections. Migrates a prior undelimited block in place.

## [0.2.0-beta] - 2026-07-10

### Added
- **Team setup — shared org-tier memory/instincts (`scripts/memory-sync.sh`).** First shipped surface of
  the layered-learnings scope model (ADR-0006) and shared vault (ADR-0007), previously design-only: a
  generic, config-driven sync tool that materializes a shared org-tier repo as a **read-only overlay**
  in `~/.claude` (`pull`) and shares local entries with a **discipline gate** (`promote`) that blocks
  secrets, personal data (home paths, emails, session hashes, `type: user`), non-allowlisted IPs, and
  work-item/TODO markers. All deployment specifics live in a personal, non-distributed
  `~/.claude/memory-sync.json` (template: `templates/memory-sync.example.json`); the script stays
  generic. Namespaces (`{ORG}-G-NNN` shared, `{SRC}-G-NNN` imported, native `G-NNN`) documented in
  `templates/MEMORY_SCHEMA.md`. Gate is a client-side best-effort lint — add a CI/pre-receive backstop
  before a large contributor circle. See CLAUDE.md → "Sharing instincts/memory across a team (org tier)".
- **`tokenFile` fallback for the YouTrack work-item backend** — `workitems.youtrack.tokenFile` names a
  file path (outside the repo, e.g. mode 600) the backend reads the token from when `tokenEnv` isn't
  set or its named environment variable is empty. Env still wins when both are configured and resolve.
  Removes the need to export an env var in every session; the token value still never enters
  `.claude/settings.json` or any tracked file.
- **"See it in action" demo section in the README** — a concise end-to-end command walkthrough (`/track-decision → /project-init → /p0-problem → /gate-p0 → …`) with a placeholder for a recorded asciinema/GIF demo, so first-time visitors grasp the phase-and-gate flow before installing.
- **Work-item backend design (proposed) — `Manual/WORKITEMS.md` + ADR-0002…0007.** A backend-neutral work-item contract (`create`/`list`/`get`/`claim`/`set-status`/`append-result`) so CCPR works **with or without a ticket system**, `local` (structured Markdown at `docs/workitems/<id>.md`) staying first-class: the contract + provider model (ADR-0002), the first remote backend — self-hosted YouTrack, resolved by name (ADR-0003), `lift`/`migrate` onboarding (ADR-0004), the claiming / branch-runner protocol with `Parked` resume (ADR-0005), and the layered learnings scope model (`framework`/`org:<name>`/`product`/`project`, ADR-0006) + shared Git vault (ADR-0007). **Design only — no shipped surface changes yet; implementation follows.**

### Changed
- **README restructured for clarity.** Added an audience-first introduction ("who it's for" / "what it covers"), a Table of Contents, and a new **Requirements** section; grouped Two Tracks + Phase System + Agent Team under a single "How it works" and moved the demo up front. Content, facts (15 agents, 115 commands), links and version are unchanged — structure and the intro only.

## [v0.1.0-beta] – 13.06.2026

Initial public release on GitHub. CCPR (Claude Code Project Runner) is a phase-based project framework for Claude Code: specialised agents, slash commands, quality gates, templates, and local automation scripts that drive a software (or business) venture from discovery to operations.

### Added
- **Agent team (15):** 13 domain agents (konzeptor, business-analyst, system-architekt, project-planner, ux-designer, senior-developer, code-reviewer, qa-tester, debugger, devops, security-master, pentester, tech-writer) plus `project-guide` (entry point / status snapshots / disambiguation) and `wingman` (result consolidation).
- **115 slash commands** covering the full phase pipeline P0–P8, quality gates, the Lean-Track, learning commands (`/postmortem`, `/instinct`), and utilities (`/guide`, `/project-init`, `/cleanup`, `/release-baseline`, `/specialize`, …).
- **Phase system P0–P8 with quality gates** — a hybrid linear-plus-iterative model; each gate is a checklist that must pass before the next phase. Includes the holistic end-of-sprint review (`/p5-review-sprint`) and per-story reviews.
- **Two tracks:** Full-Track (P0–P8, gates, mandatory Constitution) and a transient **Lean-Track** (4 skills, no gates) for fast experimentation and as a bridge into Full. `/track-decision` chooses based on knockouts + indicators.
- **Constitution + Cross-Check** — `/constitution` ratifies a project's Inviolable/Default/Aspirational rules (5 domain bootstraps); gates read the Inviolables as binding input. `/cross-check` is an optional pre-gate consistency check.
- **Memory & instinct system** — two-tier × two-scope memory (global/project × cross-cutting/persona) plus confidence-scored instincts that mature via `/postmortem`. Lint scripts validate schema, naming, cross-refs and size.
- **Documentation split** — runtime references in `docs/` (read by Claude during work: `PROJECT_PHASES.md`, `NEXT_STEPS_REFERENCE.md`, `CONSTITUTION.md`) vs. the human-facing **`Manual/`** (repo-only, not installed) for the "how to drive CCPR" guides.
- **Automation scripts & monitoring hook** — `scripts/` (context bootstrap, gate pre-flight, test runner, quality scans, doc-hygiene lints) and a single `hooks/agent-monitor.py` (activity/error logging, loop & stagnation detection, approximate token tracking).
- **Safe installer** — `install.sh` with timestamped backup, overwrite preview, `--update` (framework-only, preserves personal files + matured instincts) and `--dry-run`; user-owned sub-paths preserved across wholesale replace. Windows guidance (WSL / Git Bash / PowerShell fallback) in the README.
- **Open-source scaffolding** — `LICENSE` (MIT), `AUTHORS`, `CONTRIBUTING.md`, `SECURITY.md`, `BETA.md` (public-beta charter), and GitHub issue templates under `.github/ISSUE_TEMPLATE/` (bug / feedback / question).

[Unreleased]: https://github.com/jonase47/ccpr/compare/v0.2.1-beta...HEAD
[0.2.1-beta]: https://github.com/jonase47/ccpr/compare/v0.2.0-beta...v0.2.1-beta
[0.2.0-beta]: https://github.com/jonase47/ccpr/compare/v0.1.0-beta...v0.2.0-beta
[v0.1.0-beta]: https://github.com/jonase47/ccpr/releases/tag/v0.1.0-beta
