# /p3-infra-hosting – Hosting & Deployment Strategy

Plans hosting platform, deployment model, environments and CDN strategy.

## Argument: $ARGUMENTS = [Platform, e.g. "Hetzner", "Vercel", "local"]

If provided: Use the platform as a starting point.
If not provided: Recommend based on architecture and project frame.

## Prerequisites
- ARCHITECTURE.md and TECH_STACK.md exist

## Agent
- **Type**: devops
- **Model**: sonnet

## Context (Orchestrator prepares)
Orchestrator reads beforehand and delivers inline:
- From ARCHITECTURE.md: Components that need to be deployed
- From TECH_STACK.md: Technologies in use
- From CLAUDE.md: Hosting preference (Hetzner, self-hosted)
- From SECURITY.md: Infrastructure-relevant security requirements

## Prompt Template
> **Goal**: Plan hosting and deployment strategy. Platform: $ARGUMENTS
>
> **Context**:
> [inline from ARCHITECTURE.md, TECH_STACK.md, CLAUDE.md]
>
> **Output Format**:
> 1. Hosting platform with justification (1-2 sentences)
> 2. Deployment model: Container / PaaS / VPS / Static
> 3. Environments: Table | Environment | Purpose | URL Schema |
> 4. CDN/Static assets: strategy (1-2 sentences)
> 5. Database hosting: managed vs. self-hosted with justification
>
> **Constraints**:
> - ONLY hosting and deployment, NO CI/CD pipeline, NO monitoring
> - Consider hosting preference from CLAUDE.md
> - Max. 4 environments

## Orchestrator Checkpoint
- [ ] Hosting preference considered or rejected with justification?
- [ ] Deployment model matches the tech stack?

## Write Detail File
Write the result to `docs/architecture/HOSTING.md` (overwrite if it exists). Start with this YAML frontmatter:

```yaml
---
phase: P3
subskill: infra-hosting
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## Hosting Platform` (with justification), `## Deployment Model`, `## Environments` (the table environment / purpose / URL schema), `## CDN / Static Assets`, `## Database Hosting`.

## Update Sub-Index
Update `docs/architecture/INFRA.md` (the infrastructure sub-index, created by `/p3-infra` if missing):
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In its **Detail Files** table: ensure a row for `[HOSTING.md](HOSTING.md)` with status `complete`.
- Lift the hosting platform decision into **Key Decisions** of the sub-index.
- Do not edit `ARCHITECTURE.md` directly.

### Handover Epilogue
Update `docs/HANDOVER.md`:
- What was created/changed
- Open points
- Next Steps (according to `~/.claude/docs/NEXT_STEPS_REFERENCE.md`)

Recommend 1-3 sensible next commands to the user:
1. Read `docs/HANDOVER.md` for the current project status
2. Consult `~/.claude/docs/NEXT_STEPS_REFERENCE.md` for permitted transitions
3. Only suggest commands that match the current phase/sub-skill status
4. If the current phase appears complete: recommend the gate
