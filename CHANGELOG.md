# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/) — see [docs/adr/ADR-0001-versioning-and-distribution.md](docs/adr/ADR-0001-versioning-and-distribution.md) for the version-scoping rules in this meta-repo context.

> Development before this public GitHub release happened in a private repository. This changelog starts fresh at the first public version; the detailed pre-public history is retained privately.

## [Unreleased]

### Fixed
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
- **Two more discipline-gate call sites collapsed "no match" into "the tool failed", plus a third
  found while sweeping for the same class (WI-0053).** WI-0051 closed twenty sites where a crashing
  `grep` inside `gate_scan_file` read as "0 findings" instead of "this check did not run"; two sites
  were deliberately left out of that item's scope, and a sweep of the same three files found a
  third. **(a)** `gate_path_deny_index`'s ASCII fallback for PATH matching (`grep -qFi`) had no
  `|| true` at all, but that did not save it: the call sat inside an `if`, which suspends `errexit`
  the same way a `|| true` does, so a crash there was indistinguishable from "the configured name
  isn't in this path" — measured with a grep that fails only for that invocation shape, a file
  literally named after a configured tenant/project name passed the artifact gate clean. This is
  the LAST matcher on the PATH side — WI-0049's unicode-vs-ASCII fallback sits above it, not below —
  so the fix takes WI-0051's answer (abort, exit 2, naming the check and grep's exit status) rather
  than WI-0049's warn-and-fall-back: there is no third matcher to fall back to. Both callers of
  `gate_path_deny_index` (`artifact-gate.sh`'s own FILE PATH finding, and `memory-sync.sh promote`'s
  destination check — the one irreversible push in either tool) previously routed the function's
  result through `|| true` as well, which would have swallowed the newly-distinguished crash status
  right back into "no name found"; both now capture the real status and abort on it. **(b)**
  `artifact-gate.sh`'s command-line `FILES` list was filtered through `grep -v '^$' | ... || true`.
  This parses arguments, not content, so it cannot hide a leak directly — but a crash there silently
  shrinks WHAT GETS SCANNED, one file dropping out of the scan set without a trace; a file with a
  real credential in it, listed after the file whose path happened to crash the filter, was scanned
  0 times and the run reported clean. **(c)**, found by the sweep and not named in the item's text:
  `is_text()`'s own binary/text classifier (`grep -qI ''`) had the identical shape — a crash read
  back as "not text", which the caller counts as `skipped_binary` and moves past silently, so a file
  already in the scan list was never scanned for content at all. This is the more dangerous of the
  three: (b) only trims the file list before scanning starts, (c) skips a file's content check after
  it was already selected for scanning. All three now fail loudly (exit 2, naming the check and
  grep's exit status) instead of scanning less without saying so — the same answer this repository
  has given every time it has met this shape (WI-0015's dangling-symlink counter, the unreadable-
  file guard, the empty-scope guard, and WI-0051 itself).
- **A crashing `grep` inside the discipline gate's checks used to read as "no findings", not as
  "this check did not run" (WI-0051).** Every check in `gate_scan_file` — and the deny-list's own
  config parsing in `gate_load_config` — routed its `grep` through a trailing `|| true`, which
  folded grep's exit 1 ("no match", the ordinary empty-category case) and exit >=2 ("did not run
  to completion" — a crash, a bad pattern, a locale/encoding fault on malformed multi-byte input)
  into the identical empty result: a file carrying a private key, a credential, or a configured
  tenant name behind a crashed check came back "0 findings", exit 0. That is the same shape the
  empty-scope guard in `artifact-gate.sh` already refuses ("a run that inspected nothing has proved
  nothing"), and grep IS the matcher here — unlike WI-0049's unicode-vs-ASCII fallback, there is no
  degraded-but-real second answer to fall back to, so a crashed check aborts the whole run (exit 2)
  rather than warning and continuing. `_gate_checked` (wrapping `_gate_hits`, which no longer
  swallows grep's status itself) is now the ONE call every check in `gate_scan_file` goes through —
  the plain single-grep checks, the two-stage extract-then-placeholder-filter pairs (both the ones
  that used to route through `_gate_hits` and the ones, like WI-0035's connection-string/email
  pairs, that bypassed it entirely with a direct `printf | grep`), and all three deny-list match
  sites (the plain ASCII path and both of WI-0049's non-ASCII fallback branches). The abort message
  names which check failed and grep's exit status. `gate_scan_file` and `gate_load_config` report
  the failure by returning a status the two entry points (`artifact-gate.sh`, `memory-sync.sh`) now
  explicitly check for and abort on — a plain `|| true`/`return` cannot carry it, because a function
  invoked from an already-tested context (`cmd || true`, `if cmd; then` — exactly how both entry
  points already call `gate_scan_file`) suspends `set -e` for everything inside it, not just its own
  top-level exit status, so a crash several call-levels down used to run the rest of the function to
  completion in silence. The IP-allowlist membership test (`grep -qE` against a configured CIDR/IP
  regex) is deliberately left as-is: a broken allowlist regex there already fails CLOSED — the `&&`
  in `if [ -n "$GATE_IP_ALLOWLIST" ] && grep -qE ...` makes the IP fall through to being reported as
  a finding rather than silently allowlisted — the opposite direction from the defect this item
  fixes.
- **The deny-list content check was ASCII-only and un-normalised, so a configured non-ASCII
  tenant/project name could differ from its occurrence in a file's CONTENT only in case, or only
  in NFD-vs-NFC normalisation, and still pass (WI-0017 part 2).** The path side already escalates
  to a python3 comparison (NFC-normalised, full-Unicode case folding) for a non-ASCII subject or
  name; content matching stayed a plain `grep -nFi` because escalating it the same way the path
  side gates — subject OR name non-ASCII — was measured against this repository's own 271 tracked
  files: 257 of them (94%) carry a non-ASCII byte in ordinary prose, so that gate would add ~4.0s
  (~41%) to every sweep even with a pure-ASCII deny list. The fix gates on the configured NAME
  alone, never on file content, which costs nothing extra when the deny list is pure ASCII: for an
  ASCII name the plain matcher is provably complete rather than merely assumed to be — measured
  with the ASCII name `cafe` against NFD-decomposed content `cafe`+U+0301, `grep -Fi` reports a
  match while python's NFC view reports none, so the ASCII path can only over-report relative to
  the escalation, never miss what it would find. `_gate_content_deny_lines` runs the same
  NFC-normalise-and-fold comparison as the path side, one name at a time, with content passed on
  **stdin** rather than through the environment — the path side's env-based transport is fine for
  a path, but the largest tracked file today (93 KB) fits under `ARG_MAX` (1 MiB) only by chance,
  and a larger one would fail hard with "argument list too long". The exit contract mirrors
  WI-0049's sentinel shape exactly (0 = match, `_GATE_UNICODE_NO_MATCH` = no match, anything else =
  the helper did not run) so the two consumers of the shared library cannot drift apart again; a
  broken interpreter warns and falls back to the ASCII matcher rather than reading as a clean file.
  An earlier `LC_ALL=C` patch for the same line, prepared and parked mid-item, is superseded by
  this fix rather than applied: once the ASCII path only ever runs for ASCII names, locale-dependent
  case folding of an ASCII pattern cannot change the answer, so no locale pin is needed there either.
- **`memory-lint.sh` picked a fixed winner between an HTML comment and a code span, and assumed a
  code span never crosses a line, both of which CommonMark contradicts (WI-0048, WI-0052).**
  `decomment_paragraph()` and `strip_inline_code()` used to be two separate whole-paragraph passes
  in a fixed order — comments stripped first, code spans stripped second, per resulting line. Any
  fixed order between two such passes is wrong in one direction: reordering them would have fixed
  one measured case and broken another that already worked. CommonMark gives precedence to
  whichever construct opens FIRST, reading left to right — the other's delimiters are then literal
  text inside the span that opened first. Separately, `strip_inline_code()`'s own comment stated "a
  span never crosses a line in Markdown, so unlike decomment() this needs no state across records"
  — that premise is false: a code span crosses a paragraph-internal line break exactly like an
  inline HTML comment does, stopping only at the same block boundaries (list item, blank line,
  heading, fence, block-level HTML comment) WI-0050 already established. Both passes are replaced
  by one function, `resolve_paragraph()`: a single left-to-right scan over the whole buffered
  paragraph in which whichever construct — a `dest_mark`-protected link destination, an HTML
  comment opener, or a backtick run — is met first at the current scan position claims its span
  whole; the paragraph-buffering mechanics WI-0050 built (`append_paragraph()`/`flush_paragraph()`)
  are unchanged. `dest_mark` opacity (WI-0042 — a link destination is not inline-parsed) is now
  honoured by the code-span search too, closing a gap the old `strip_inline_code()` never guarded
  at all. Every fixture was settled at a CommonMark reference implementation before being pinned as
  a test — see `docs/memory/reference_commonmark-conformance.md` — and mutation-checked against the
  pre-fix script: an index illustrating its own two-line link syntax inside one code span
  (`` `an entry looks like\n[label](dest) inside a span` ``) used to report the illustrative link as
  a dead target; it no longer does.
- **`memory-lint.sh` treated an unclosed mid-line HTML comment as swallowing the rest of the
  file instead of nothing.** CommonMark HTML block type 2 only applies when `<!--` opens the
  line itself (after up to three spaces); a `<!--` that appears mid-line is inline raw HTML, and
  whether it hides anything downstream of it depends on whether it closes before the current
  paragraph ends — never on the rest of the file. The extractor's `decomment()` used a single
  `in_comment` variable that was never declared local inside `awk`, which makes it GLOBAL: an
  opener with no closer on its own line left that state set, and every following line — in the
  same paragraph, the next paragraph, a later list item, anywhere before end of file — was
  silently treated as still inside the comment. Three shapes, each settled at a CommonMark
  reference implementation before being pinned as a test: a mid-line opener in a LIST ITEM never
  crosses into the next item, because each item is its own block; inside a plain PARAGRAPH it DOES
  cross into a later line of the same paragraph if the closer is there; and an opener that never
  closes before the paragraph ends is literal text — nothing is discarded. The fix buffers the
  current paragraph across physical lines (`append_paragraph()`/`flush_paragraph()`) up to the
  next block boundary — a blank line, a list-item marker, a heading, a fenced code block, or a
  block-level HTML comment — and resolves the whole buffered paragraph in one call to a new
  `decomment_paragraph()`, which uses a genuinely local per-call variable instead of the old bare
  global. Lookahead is bounded to one paragraph and never reaches past a block boundary, closing
  both the crossing-into-the-next-paragraph defect and the case an unclosed opener used to just
  drop the rest of its own line instead of leaving it as literal text.
- **`artifact-gate.sh` followed a tracked symlink instead of treating it as its own name.**
  Two related defects: a dangling symlink vanished from the sweep silently — `[ -f ]` failed and
  the loop `continue`d before the file's own name ever reached the deny-check, so a tracked link
  whose filename carried a configured tenant name went unreported and the scope shrank without a
  word. A *resolving* symlink was worse the other way: `-f` follows a symlink, so its target's
  bytes were read through the link's path, scanning an in-repo target twice (once via its own
  tracked entry, once again through the link) and reporting a leak from an out-of-repo target
  under a repo-relative path — even though that target's bytes never ship. `install.sh` copies
  with `cp -R`, which preserves a symlink AS a link; what CCPR ships for a symlink is the link
  itself, never its target, so the gate's subject is the link's own name, checked exactly like any
  other path, dangling or not — the target is never opened. `test -L` (checked before `-f`, so a
  resolving link cannot fall through into the regular-file branch) now discriminates a symlink
  from a regular file, uniformly for both an explicit file argument and a `git ls-files` sweep
  entry. A new `skipped_symlink` counter and its own summary line ("N symlink(s) skipped — target
  not scanned, names still checked") mirror the existing binary-skip line, so the fix does not
  reproduce the silent-scope-loss defect it closes.
- **A screaming-snake-case placeholder still read as a bearer token or a keyword-assignment
  secret.** `Authorization: Bearer YOUR_TOKEN_HERE_REPLACE_ME` and
  `Authorization: Bearer TODO_INSERT_YOUR_TOKEN_HERE` both fired as `[secret]`, because the value
  opens with a plain alphanumeric — the same class a real credential starts with, and none of
  `GATE_RE_PLACEHOLDER_SLOT`'s shapes (`${...}`, `$VAR`, `<...>`, `{{...}}`, a `%`-format slot,
  `***`) cover it, since all of those open with a non-alphanumeric character instead. A
  shape-based filter (dropping values made only of capitals, digits and underscores) was
  considered and rejected: `GATE_RE_SECRET_VENDOR`'s own `AKIA[0-9A-Z]{16}` is exactly that shape,
  so it would have gone congruent with a real AWS Access Key ID. Added
  `GATE_RE_SECRET_PLACEHOLDER_WORD` instead — a case-insensitive, substring match against a word
  list (`YOUR`, `TODO`, `REPLACE`, `CHANGEME`, `EXAMPLE`, `PLACEHOLDER`, `INSERT`, `DUMMY`,
  `SAMPLE`) — applied only to the keyword-assignment (1a) and bearer-header (1a') checks via the
  same extract-then-drop two-pass idiom `GATE_RE_CONNSTRING`/`GATE_RE_PLACEHOLDER` already use.
  Scoped deliberately: the vendor/blob/private-key/connection-string rules get no such filter, so
  AWS's own documentation key (`AKIA...EXAMPLE`) still fires there, unfiltered. Accepted cost: the
  word list is never complete and will grow — an unlisted word means a placeholder still fires (a
  false positive), never a missed leak.
- **`memory-sync.sh promote` accepted a destination that reads as a command-line flag.**
  `promote <src> --all` and `promote <src> -n` both exited 0 and published a file literally named
  `--all` or `-n`. Not a leak — `git add -- "$dst"`, `dirname -- "$dst"` and `cp -- "$src" "$dst"`
  already treat the destination as a path regardless of a leading dash — but a file with that name
  is almost certainly a mistyped flag, and it reads as a flag again to every tool that later globs
  the directory it landed in. `require_file_destination` now refuses a destination with any
  `/`-separated component starting with `-` (covering both a top-level `-n` and a nested
  `instincts/-n`), the same way it already refuses `.`/`..`/a trailing slash — before the clone is
  touched, before the token is read. The refusal names the actual mistake ("looks like a
  command-line flag") rather than reusing the directory-destination message.
- **A fatally broken `python3` made the deny-list name check pass clean instead of failing.**
  `gate_path_deny_index`'s non-ASCII escalation reads `_gate_unicode_py`'s exit status: 0 for a
  match, and a case arm written to catch "the comparison did not happen" and fall back to the
  ASCII matcher for anything else. That fallback arm signalled "no match" with `sys.exit(1)` — the
  same status a fatally broken interpreter produces on start-up (measured:
  `PYTHONHOME=/nonexistent python3 -c pass` exits 1), before the script's own no-match line ever
  runs. So the arm written for exactly this fault was unreachable for the most likely one, and a
  dead matcher read as a clean path: on a repo with one tracked file named after a configured
  deny-listed name, a working interpreter reported 1 finding and exit 1, a broken one reported
  "scanned 1 files, 0 findings" and exit 0, with the documented "unicode matcher failed" warning
  never printed. "No match" now exits with a dedicated sentinel instead, so every other status —
  including a broken interpreter's 1 — falls through to the existing warn-and-fall-back arm, which
  is now reachable. `gate_redact_path`, the sibling call site that already trusted only `rc -eq 0`
  and fell back to `awk` for everything else, was already correct and is unaffected.
- **`templates/ci/artifact-gate.ci.sh` shipped without any execution check.** Nothing ran the
  template — not even a syntax check — so the first team to activate it in CI would have been the
  first to discover whether it actually worked. Added a `sh -n` syntax test plus a fixture-repo
  invocation that copies the real gate into a throwaway git repo and asserts the template fails a
  repo carrying a planted finding, passes a clean one, exits 2 with its own message when the gate
  is not installed at `$REPO_ROOT`, and passes `REQUIRE_DENYLIST=1` through to the gate as
  `--require-denylist`. Also corrected the template's Activation note: the sweep reads only
  `git ls-files`, not history, so a shallow checkout is fine — what it actually needs is a `.git`
  working tree, not full history as the note previously said.
- **`artifact-gate.sh` reported its own pattern definitions as secrets when run from an
  installation.** The self-exemption that keeps the gate from flagging its own credential-shaped
  pattern definitions is bound to the *resolved path* of the file that defines them
  (`scripts/lib/discipline_gate.sh`), by design — the marker line-comment that grants the exemption
  is honoured only in that one file, so it cannot be used as a suppression backdoor anywhere else. An
  installed copy of the gate (e.g. `~/.claude/scripts/artifact-gate.sh`) scanning a *different*
  checkout therefore meets a `discipline_gate.sh` that is not its own, and reported three genuine
  false positives with no context. Widening the exemption to recognise a foreign copy by name or
  location would reopen exactly the backdoor it exists to close, so the fix does not touch the
  exemption: a finding whose line still carries the exemption marker now names it and says the file
  was not recognised as the pattern source, so a maintainer reads the reason instead of triaging
  three unexplained "secret" findings.
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
  a missing `--` that let a destination named `--all` sweep unrelated files into the push.
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
- **`/p5-polish` wrote its `handover`-triage items into a section that did not exist.** It has always
  instructed agents to record blocked items in `docs/HANDOVER.md` "under Open Points", but no shipped
  template ever contained that heading — the flow dangled unless a project invented the section itself.
  The inbox now provides the destination, and `/p5-polish` writes the same entry format the `/cleanup`
  triage reads, so producer and consumer finally agree.
- **`memory-lint.sh` gained exit code 3 for a configuration error.** The severity knob for the new
  check was expanded in command position, so a typo aborted the run with `command not found`, exit
  127 and no report at all — a caller testing for "non-zero" would have read a dead script as a
  findings result. The value is now validated up front and findings are dispatched by `case`. The
  contract at the top of the script, in `templates/MEMORY_SCHEMA.md` and in `/cleanup` now all name
  the new code.
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
- **`memory-lint.sh` check (n) dropped the rest of the file when a code fence was never closed —
  silently.** An unclosed fence running to end-of-document is correct CommonMark, so the skip itself
  was right; nothing said the scope had shrunk, so a single stray triple-backtick could disable dead-link
  checking for everything below it without any indication in the report. The check now emits a warning
  naming the line where the fence opened, independent of `MEMORY_INDEX_LINK_SEVERITY`.
- **`memory-lint.sh` check (n) validated the Tier-1 index only — nothing checked a persona (Tier-2)
  index's links.** `docs/memory/{agent}/MEMORY.md` carries far more links than the Tier-1 index (deep
  anchors into topic files, one per review/implementation round), and splitting a persona silo found
  three already-dead entries that nothing had noticed. The check now scans every persona index too, in
  addition to the Tier-1 one — a relative target resolves against its own index's directory, not the
  Tier-1 memory dir, so a persona index's target file is checked in the right place. Deliberately a
  floor, not a full fix: it catches a target file that no longer exists, not a wrong anchor into a file
  that still does — anchor resolution needs heading-to-slug modelling and is a separate, unbuilt item.
- **An unclosed HTML comment silently switched check (n) off for everything below it, with no
  warning.** Correct behaviour per CommonMark — a block comment opened at the start of a line and
  never closed swallows the rest of the document as raw HTML, so no link there was ever missed — but
  the failure mode was silent, same class as the unclosed-fence case above. The check now emits a
  warning naming the line where the comment opened, reusing the same end-of-input sentinel mechanism,
  independent of `MEMORY_INDEX_LINK_SEVERITY`.

### Added
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
  *name*. The gate is now split into a pattern library used by both entry points, with profiles
  selecting which checks run rather than what a pattern means. The generic 40-character rule — the
  source of every false positive — was replaced with shapes machine-generated credentials actually
  have. A deny-list of tenant and project names closes the real gap; it is read from personal config
  or an environment variable, never from the repository, and matches are reported with file and line
  while the name itself is redacted from every emitted line, because a CI log is a shipped artifact
  too. An unconfigured deny-list says so loudly instead of passing silently. Ships with a dormant CI
  template that names no forge. The repo currently scans clean: 275 files, 0 findings.
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
- **`memory-lint.sh` now validates the Tier-1 index's own links (check `n`).** The lint checked
  cross-references in one direction only: it found memory files the index had forgotten (check `g`)
  and `related:` entries pointing at nothing (check `f`), but a link *inside* `docs/memory/MEMORY.md`
  whose target had been deleted passed silently — reported from the field, where a manual pass found
  two such links in a live index. Reproduced before the fix: an index with two dead links produced
  zero findings. The check skips images, HTML-commented entries, code-fence-free inline links, anchors
  and external URLs, resolves root-absolute targets against the project root, and reports every dead
  link on a line rather than the first. It ships at **warning** severity: the link extraction does not
  yet see fenced/inline code examples or reference-style links, and erroring on an incomplete
  extraction would claim a completeness that is not evidenced. Promotion to error is tracked
  separately and is the SemVer-relevant step (ADR-0001).
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

### Changed
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
