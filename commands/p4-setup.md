# /p4-setup – Repository, CI/CD & Development Environment Setup

Sets up the repository, CI/CD pipeline and local development environment. The result is a working development infrastructure in which the team can immediately start with `/p5-implement`.

## Argument: $ARGUMENTS = [Project name]

If provided: Use as repository name and project identifier in configuration files.
If not provided: Read CONCEPT.md or PROJECT_PLAN.md and derive the project name. If any context is missing, ask for the project name before starting.

## Execution

### 1. Read Context
Read the following files (if available):
- **TECH_STACK.md** (technologies determine the setup)
- **INFRASTRUCTURE.md** (CI/CD pipeline design, hosting platform)
- **SECURITY.md** (security requirements for pipeline and secrets management)
- **TEST_STRATEGY.md** (test levels determine pipeline stages)

### 2. Delegation to DevOps Agent (Lead)
Delegate the technical setup to the **devops** agent:

> Set up the development infrastructure for project **$ARGUMENTS**.
> Context from TECH_STACK.md and INFRASTRUCTURE.md: [Insert tech stack, CI/CD design, hosting decisions]
>
> **A. Repository Structure**
> - Create the initial directory structure matching the tech stack
> - Basic configuration files: .gitignore, .editorconfig, .nvmrc / .tool-versions
> - Document branching strategy (according to INFRASTRUCTURE.md)
> - Basic git hooks: pre-commit (lint, format), commit-msg (Conventional Commits)
>
> **B. CI/CD Pipeline**
> Implement the pipeline according to INFRASTRUCTURE.md:
> - Configuration file(s) for the chosen CI/CD tool (e.g. .github/workflows/)
> - Stage 1: Lint & Format Check
> - Stage 2: Unit Tests
> - Stage 3: Build
> - Stage 4: Security Scan (SAST, dependency check e.g. with Trivy or Snyk)
> - Stage 5: Deploy to Staging (manually triggered or on main branch)
> - Secrets: placeholders and documentation of which secrets need to be configured
>
> **C. Docker / Containerization**
> If containers are planned (according to TECH_STACK.md):
> - Dockerfile(s) for all services (multi-stage builds for production)
> - docker-compose.yml for local development (app + database + additional services if needed)
> - .env.example with all required environment variables (without real values)
>
> **D. Development Environment**
> - Document the steps for local setup (will be incorporated into README.md)
> - Seed script for test data (populate database with sample data)
> - Make targets or npm scripts for common tasks: dev, test, build, lint, migrate
>
> **E. Configure Environments**
> - Environment variable structure for local / staging / production
> - Implement secrets management approach (according to SECURITY.md)

### 3. Delegation to Senior-Developer Agent (Support)
Delegate development environment verification to the **senior-developer** agent:

> Review the DevOps agent's setup from a developer perspective:
> 1. Can the local development environment actually be set up using the described steps?
> 2. Are all necessary dependencies and their versions clearly documented?
> 3. Do initial tests pass (even if no production code exists yet)?
> 4. Is anything missing that developers will need in their daily workflow?

### 4. Write Detail Files
The setup result is primarily code and configuration in the repository (concrete files outside `docs/`). Document the status in `docs/planning/SETUP.md`. Layout depends on size: flat (single file) or sub-index (with per-topic detail files).

#### 4a. Choose Layout

| Condition | Layout |
|---|---|
| Result fits in <10 KB | **Flat**: single `SETUP.md` |
| Result ≥10 KB OR distinct topics each have meaningful depth | **Sub-Index**: lean `SETUP.md` + `setup/<TOPIC>.md` per topic |

#### 4b. Flat Layout (small projects)

Write `docs/planning/SETUP.md` (overwrite if exists). Frontmatter:

```yaml
---
phase: P4
subskill: setup
kind: detail
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Repository Structure`, `## CI/CD Pipeline Status`, `## Container Setup` (if applicable), `## Environment & Secrets` (what's in .env.example, what still needs manual configuration), `## Open Setup Tasks`.

(File replaces the legacy `SETUP_LOG.md` name — keep `SETUP.md` going forward.)

#### 4c. Sub-Index Layout (recommended for non-trivial setups)

Write a lean **sub-index** `docs/planning/SETUP.md`:

```yaml
---
phase: P4
subskill: setup
kind: sub-index
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections (lean — keep under ~5 KB):
- `## Status` — overall setup status (one line per topic: complete / partial / pending)
- `## Topics` — overview table: `Topic | Status | Detail-File`
- `## Open Setup Tasks` — cross-cutting tasks not yet done (lifted into `PROJECT_PLAN.md` Open Risks if blocking)
- `## Detail Files` — link list

Per topic, write one detail file `docs/planning/setup/<TOPIC>.md`. Common topics:
- `setup/repo-structure.md` — directory layout, base config files, branching strategy
- `setup/ci-cd.md` — pipeline stages, secrets placeholders, environments
- `setup/containers.md` — Dockerfiles, docker-compose, multi-stage build details
- `setup/env-secrets.md` — .env.example contents, secrets management approach
- `setup/local-dev.md` — local setup steps, seed scripts, common make/npm targets

Detail-file frontmatter:

```yaml
---
phase: P4
subskill: setup
kind: setup-detail
topic: <topic-slug>
status: active | partial | pending
last_updated: <DD.MM.YYYY>
---
```

Body: topic-specific. Each detail file ends with a `## Open Tasks` section so the index can roll the cross-cutting view from there.

### 5. Update Phase Index
Update `docs/planning/PROJECT_PLAN.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure a row for `[SETUP.md](SETUP.md)` with status `complete`.
- Lift any unfinished manual setup task into **Open Risks / Open Questions** so it cannot be forgotten before P5.

## Result

- Repository structure with initial configuration files
- CI/CD pipeline (configuration files, running successfully)
- docker-compose.yml and Dockerfiles (if containers are planned)
- .env.example (complete, without real values)
- **`docs/planning/SETUP.md`** (what is set up, what still needs to be configured manually)
- **`docs/planning/PROJECT_PLAN.md`** (phase index updated)
- Foundation for `/p4-docs` (populate README) and immediate start with `/p5-implement`

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
