# /p4-docs – README, Contributing Guide & Project Structure Documentation

Creates the foundational project documentation: a meaningful README, a contributing guide, and documentation of the project structure. The result is a documentation base that quickly onboards new developers and bindingly establishes standards.

## Argument: $ARGUMENTS = [Documentation focus, e.g. "README", "Contributing", "API Docs", "Onboarding"]

If provided: Focus the elaboration on the named documentation area.
If not provided: Create all core documents (README.md, CONTRIBUTING.md) in full. If any project context is missing, ask for the project name and tech stack.

## Execution

### 1. Read Context
Read the following files (if available):
- **CONCEPT.md** (project description, value proposition)
- **TECH_STACK.md** (technologies for README badges and setup guide)
- **INFRASTRUCTURE.md** (CI/CD, deployment for developer documentation)
- **ARCHITECTURE.md** (explain project structure)
- **SETUP_LOG.md** (what was set up in `/p4-setup`?)
- **TEST_STRATEGY.md** (test guide for contributing guide)
- **SECURITY.md** (security guidelines for contributing guide)

### 2. Delegation to Tech-Writer Agent (Lead)
Delegate the documentation creation to the **tech-writer** agent:

> Create the project documentation. Focus (if provided): **$ARGUMENTS**
> Context from all project documents: [Insert project name, description, tech stack, setup steps]
>
> **A. README.md**
> Create a complete README with the following sections:
> - **Header**: Project name, short description (1–2 sentences), status badges (CI, coverage, license)
> - **What is [Project Name]?**: Value proposition in 3–5 sentences for developers
> - **Features**: Most important features as a short list
> - **Tech Stack**: Overview of technologies used with links
> - **Prerequisites**: What needs to be installed? (Node.js, Docker, etc. with versions)
> - **Quick Start**: Step-by-step guide for local setup (copy-paste ready)
> - **Development**: Important commands (start dev, tests, lint, build, migrations)
> - **Project Structure**: Directory tree with short explanations
> - **Tests**: How to run tests, what is tested
> - **Deployment**: Short explanation of the deployment process
> - **Contributing**: Link to CONTRIBUTING.md
> - **License**: License information
>
> **B. CONTRIBUTING.md**
> Create a complete contributing guide with:
> - **Welcome**: Short introduction stating what contributions are welcome
> - **Setting Up the Development Environment**: More detailed than README, for external contributors
> - **Branch Strategy**: Which branches exist, how are they named?
> - **Commit Convention**: Conventional Commits with examples (feat, fix, docs, test, refactor...)
> - **Pull Request Process**: How is a PR created? What is checked in review?
> - **Code Style & Linting**: Which standards apply? Which tools enforce them?
> - **Test Requirements**: What must be tested before a PR is merged?
> - **Security Guidelines**: How are security findings reported (responsible disclosure)?
> - **Definition of Done**: When is a change considered complete?

### 3. Delegation to DevOps Agent (Support)
Delegate technical verification of the documentation to the **devops** agent:

> Review README.md and CONTRIBUTING.md from the tech-writer for technical accuracy:
> 1. Are all commands in the quick start guide correct and complete?
> 2. Do the prerequisites (Node version, Docker version, etc.) match the actual setup?
> 3. Is important information for developers missing (e.g. secrets, external services)?
> 4. Is the CI/CD information correct?

### 4. Write Files & Detail File
The primary outputs of this subskill are repo-level files (not under `docs/`):
- **`README.md`** (in the project root) — complete project documentation for developers
- **`CONTRIBUTING.md`** (in the project root) — standards and processes for contributions

In addition, write a short detail file at `docs/planning/DOCS.md` that summarises what was created and links to both root files. Frontmatter:

```yaml
---
phase: P4
subskill: docs
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## README.md Overview` (1-paragraph summary + link to `../../README.md`), `## CONTRIBUTING.md Overview` (1-paragraph summary + link to `../../CONTRIBUTING.md`), `## Documentation Decisions` (license, voice, audience).

### 5. Update Phase Index
Update `docs/planning/PROJECT_PLAN.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[DOCS.md](DOCS.md)` with status `complete`.
- Lift the documentation language and license decision into **Key Decisions** if applicable.

## Result

- **`README.md`** (project root, complete project documentation for developers)
- **`CONTRIBUTING.md`** (project root, standards and processes)
- **`docs/planning/DOCS.md`** (summary + links + decisions)
- **`docs/planning/PROJECT_PLAN.md`** (phase index updated)
- Foundation for Gate 4 and all further development work in Phase 5

### Handover Epilog
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for allowed transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
