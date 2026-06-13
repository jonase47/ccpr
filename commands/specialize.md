# /specialize – Adapt agents to the project's tech stack

Generic CCPR agents are tech-stack-agnostic all-rounders. Once the stack is known,
this command writes **project-local** specialized copies under `.claude/agents/`
(which take precedence over `~/.claude/agents/` via Claude Code's name resolution)
and injects a **Project Tech Context** block carrying stack-specific correctness,
security, and idiom rules — so the developer agent knows the language's footguns
and the reviewer agent knows to check for them.

It runs in two modes from the same machinery — only the knowledge *source* differs:

- **`docs` mode** — the stack was decided through CCPR (P3), so the knowledge is
  read from the architecture docs. Source of truth: `docs/architecture/TECH_STACK.md`,
  the ADRs under `docs/architecture/ADR/`, and the **Tech Stack** / **Key Decisions**
  sections of the project `CLAUDE.md`.
- **`codebase` mode** — an existing codebase with no CCPR history, so the knowledge
  is read from the code itself (dependency manifests, build/CI config,
  language-version files).

## What this command does NOT do
- **No auto-commit.** It writes files and shows a diff. You review and commit.
- **No blind overwrite.** Hand-written agent content is never touched — only the
  marked auto-specialization block is created or replaced (see *Marker Block*).
- **No invented rules.** Stack facts come from the sources below. Anything plausible
  but not verifiable from a source — or that may not match the pinned version — is
  marked `⚠ verify`, never asserted as fact.

## Argument: $ARGUMENTS = [optional: comma-separated agent names to limit the run]
If empty: specialize the default agent set (see step 3).

## Execution

### 1. Detect mode
- If `docs/architecture/TECH_STACK.md` exists → **`docs` mode**. Read it, the ADRs
  under `docs/architecture/ADR/`, and the project `CLAUDE.md` Tech-Stack / Key-Decisions.
- Else → **`codebase` mode**. Scan the repo root for stack signals and read what you find
  (do not guess versions you cannot read):
  - **Language / deps**: `go.mod`, `package.json`, `composer.json`, `requirements.txt`,
    `pyproject.toml`, `Cargo.toml`, `Gemfile`, `pom.xml`, `build.gradle`
  - **Versions**: `.tool-versions`, the `go.mod` go-directive, `.nvmrc`, engine fields
  - **Build / CI / infra**: `Dockerfile`, `docker-compose.yml`, `Makefile`,
    linter configs (`.golangci.yml`, `.eslintrc*`), CI configs (`.woodpecker`,
    `.github/workflows`, `.gitlab-ci.yml`)

### 2. Resolve stack facts (with source discipline)
Build a short fact sheet: languages + versions, frameworks / libraries, datastore,
build / test tooling, hosting / CI, and any project-specific conventions you can cite
(e.g. an ADR mandating in-memory token storage). Keep the source for each fact.
Every rule you later write falls into one of two tiers — treat them differently:

- **Language / idiom rules** — stable, established knowledge of the language or its
  standard libraries (e.g. `defer rows.Close()` after a `pgx` query, `%w` error
  wrapping, `useEffect` cleanup). These follow mechanically from "the stack is
  Go / React" and may be drawn from general knowledge — no source citation, no
  `⚠ verify` needed.
- **Project / library specifics** — anything version-dependent or project-dependent
  (a specific library's API surface, a framework's current component set, a project
  convention like the central api-client path or an ADR-mandated token store).
  These **must** be backed by a source you actually read (TECH_STACK / ADRs / code).
  If plausible but unconfirmed — or you are unsure it matches the pinned version —
  mark it `⚠ verify` instead of asserting it.

This split is the "never invent" rule applied where it matters: stable idioms are
safe to state; fast-moving library details are where a confident-sounding
hallucination does real damage.

### 3. Determine target agents
Default set (only the technical personas benefit):
`senior-developer`, `code-reviewer`, `qa-tester`, `debugger`, `devops`.

Add when the stack warrants it:
- `system-architekt` — when architectural stack idioms are worth pinning
- `security-master`, `pentester` — when the stack has a clear attack surface (web API, auth, DB)
- `ux-designer` — only if a frontend framework is in the stack

Skip the conception / business personas entirely (`konzeptor`, `business-analyst`,
`project-planner`, `tech-writer`, `project-guide`, `wingman`).

A `$ARGUMENTS` list overrides this with an explicit subset.

### 4. Per target agent: create or update the local copy
For each target agent `<name>`:

1. If `.claude/agents/<name>.md` does **not** exist: copy the global base from
   `~/.claude/agents/<name>.md` to `.claude/agents/<name>.md`.
2. Generate the **Project Tech Context** block for *this* persona — only the rules
   relevant to its role: the developer gets idiom + correctness rules; the reviewer
   gets the same concerns phrased as a review checklist; devops gets build / CI /
   deploy specifics; qa-tester gets the test framework + run commands; etc. Keep it
   tight — a focused list beats a wall of text (every line costs tokens on *every*
   invocation of that agent).
3. Insert or replace the marked block (see below). Never modify anything outside
   the markers.

### Marker Block
Generated content lives between fixed markers so re-runs are idempotent:

```markdown
<!-- BEGIN AUTO-SPECIALIZATION (/specialize, <DD.MM.YYYY>, mode=<docs|codebase>) -->
## Project Tech Context
> Auto-generated from <source>. Review before trusting; `⚠ verify` = confirm against the live library / version.

**Stack:** <one-line summary>

**Language idioms** (stable — general knowledge of the language is fine)
<persona-relevant idiom rules, each a one-liner>

**Project / library specifics** (source-backed; `⚠ verify` where unconfirmed)
<persona-relevant project rules, each a one-liner; `⚠ verify` where needed>
<!-- END AUTO-SPECIALIZATION -->
```

- **First run / no existing block** → insert directly after the agent's role-intro
  paragraph (the "You are an experienced …" line), before the first generic section.
- **Re-run / block present** → replace everything between the markers in place;
  leave the rest of the file byte-for-byte unchanged.

### 5. Show diff, stop
Print a per-file diff of what changed (`git diff` if the project is a git repo).
Do **not** commit. Summarize:
- detected mode (docs / codebase) and the resolved stack one-liner
- which agents were **created** vs. **updated**
- every `⚠ verify` item, so the user can confirm them before committing

## Result
- Project-local specialized agents under `.claude/agents/` (precedence over global)
- A reviewable diff — no commit
- A list of `⚠ verify` items needing human confirmation

### Handover Epilogue
If `docs/HANDOVER.md` exists, update it:
- Which agents were specialized, in which mode
- Open `⚠ verify` items
- Next step: review the diff, confirm verify-items, commit

Recommend 1–3 sensible next steps to the user:
1. Review the diff and confirm any `⚠ verify` items against the live libraries
2. Commit the specialized agents
3. Re-run `/specialize` after a significant stack change to refresh the blocks
