# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/) — see [docs/adr/ADR-0001-versioning-and-distribution.md](docs/adr/ADR-0001-versioning-and-distribution.md) for the version-scoping rules in this meta-repo context.

> Development before this public GitHub release happened in a private repository. This changelog starts fresh at the first public version; the detailed pre-public history is retained privately.

## [Unreleased]

### Fixed
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
  target for content that was never a link, the direction `MEMORY_INDEX_LINK_SEVERITY`'s `warn`
  default exists to protect against. Fixed by unwrapping the bracket form before resolving (an
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

### Added
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
  modelling and is a separate, unbuilt item. Ships
  at **warning** severity by default; `MEMORY_INDEX_LINK_SEVERITY` is the documented escape hatch
  to `err`, validated up front so a typo reports a configuration error (exit 3) instead of
  aborting with `command not found` (exit 127), indistinguishable from a findings result.
  Promotion to error is tracked separately and is the SemVer-relevant step (ADR-0001).
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
