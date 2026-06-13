# /p3-data-model – Data Model & API Design

Designs the Data Model with entities and relationships as well as the API design with interface specification. The result is DATA_MODEL.md and API_SPEC.md as the binding foundation for implementation.

## Argument: $ARGUMENTS = [Domain/Entity, e.g. "User Management", "Order Process", "Product Catalog"]

If provided: Focus the design on the named domain or entity and its direct relationships.
If not provided: Read ARCHITECTURE.md, FEATURES.md and USER_JOURNEYS.md and develop the complete Data Model for the entire system. If any context is missing, ask for the core entities of the system.

## Execution

### 1. Read Context
Read the following files (if available):
- **ARCHITECTURE.md** (components, data flows – what must the model support?)
- **TECH_STACK.md** (database choice – influences the model design)
- **FEATURES.md** (which features impose which data requirements?)
- **USER_JOURNEYS.md** (what data is generated during usage?)
- **DSGVO_INITIAL_ASSESSMENT.md** (DSGVO (GDPR) privacy constraints: deletability, anonymization)

### 2. Delegation to System Architect Agent (Lead)
Delegate the Data Model and API design to the **system-architekt** agent:

> Design the Data Model and API specification. Focus (if provided): **$ARGUMENTS**
> Context: [insert key points from ARCHITECTURE.md, FEATURES.md, TECH_STACK.md]
>
> **A. Data Model**
> - Entity-Relationship diagram (Mermaid ERD or ASCII)
> - Per entity: fields with data types, required fields, constraints
> - Relationships: 1:1, 1:n, n:m with justification
> - Indexes: which fields are indexed for performance?
> - DSGVO markings: which fields contain personal data?
>
> **B. API Design**
> - API style: REST / GraphQL / tRPC – with justification
> - Resources and endpoints (overview of all routes)
> - Request/Response schemas for critical endpoints
> - Authentication and authorization concept at the API level
> - Error handling: standard error codes and formats
> - Versioning strategy
>
> **C. Database Design Decisions**
> - Normalization level and justification
> - Migration strategy (how are schema changes deployed?)
> - Soft Delete vs. Hard Delete – decision and justification (DSGVO-relevant)
> - Audit trail: which changes are logged?

### 3. Delegation to Senior Developer Agent (Support)
Delegate the implementability check to the **senior-developer** agent:

> Check the system architect's Data Model and API design for implementability:
> 1. Are there N+1 query problems or other performance pitfalls?
> 2. Are the API endpoints consistent and follow a clear pattern?
> 3. Are critical endpoints missing for the must-have features?
> 4. Are data types and constraints compatible with the chosen tech stack (TECH_STACK.md)?

### 4. Write Detail Files
This subskill writes **two** detail-file groups (exception to the 1-subskill = 1-file pattern, because data model and API specification are tightly coupled and produced together). Each group can be written **flat** (single file) or **as sub-index with per-entity / per-resource detail files**, depending on size. See `~/.claude/docs/PROJECT_PHASES.md` ("Sub-Index for growing detail files").

#### 4a. Choose Layout — Data Model

| Condition | Layout |
|---|---|
| ≤6 entities AND result fits in <25 KB | **Flat**: single `DATA_MODEL.md` |
| ≥7 entities OR result ≥25 KB | **Sub-Index**: lean `DATA_MODEL.md` + `data-model/` subfolder with one detail file per entity |

#### 4b. Flat Layout — Data Model (small models)

Write `docs/architecture/DATA_MODEL.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P3
subskill: data-model
kind: detail
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## ER Diagram`, `## Entities` (per entity: fields/types/required/constraints), `## Relationships`, `## Indexes`, `## DSGVO Markings`, `## Design Decisions` (normalization, soft delete, audit trail).

#### 4c. Sub-Index Layout — Data Model (recommended for ≥7 entities)

Write a lean **sub-index** `docs/architecture/DATA_MODEL.md`:

```yaml
---
phase: P3
subskill: data-model
kind: sub-index
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections (lean — keep under ~10 KB):
- `## Status`
- `## ER Diagram` (full diagram stays in the index for navigation)
- `## Entities` — overview table: `Entity | Purpose | DSGVO | Detail-File`
- `## Relationships` — DAG / table only; per-entity FK details live in detail files
- `## Cross-Cutting Indexes` (composite indexes spanning multiple entities)
- `## Design Decisions` (normalization, soft delete, audit trail — cross-cutting)
- `## Detail Files` — link list

Per entity, write one detail file `docs/architecture/data-model/<ENTITY>.md`:

```yaml
---
phase: P3
subskill: data-model
kind: entity-detail
entity: <EntityName>
status: active
last_updated: <DD.MM.YYYY>
---
```

Body: `## Fields` (table: name, type, required, constraints), `## Indexes`, `## Foreign Keys`, `## DSGVO Notes` (which fields are personal data, retention), `## Lifecycle` (creation, mutation, deletion), `## Notes`.

#### 4d. Choose Layout — API

| Condition | Layout |
|---|---|
| ≤8 endpoints AND result fits in <25 KB | **Flat**: single `API_SPEC.md` |
| ≥9 endpoints OR result ≥25 KB | **Sub-Index**: lean `API_SPEC.md` + `api-spec/` subfolder with one detail file per resource |

#### 4e. Flat Layout — API (small specs)

Write `docs/architecture/API_SPEC.md` (overwrite if it exists). Frontmatter:

```yaml
---
phase: P3
subskill: data-model
kind: detail
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections: `## API Style` (REST/GraphQL/tRPC + justification), `## Resources & Endpoints`, `## Schemas` (request/response for critical endpoints), `## Auth & Authorization`, `## Error Handling`, `## Versioning Strategy`.

#### 4f. Sub-Index Layout — API (recommended for ≥9 endpoints)

Write a lean **sub-index** `docs/architecture/API_SPEC.md`:

```yaml
---
phase: P3
subskill: data-model
kind: sub-index
status: active
last_updated: <DD.MM.YYYY>
---
```

Body sections (lean — keep under ~10 KB):
- `## API Style` (cross-cutting decision + justification)
- `## Auth & Authorization` (cross-cutting)
- `## Error Handling` (cross-cutting standard error codes)
- `## Versioning Strategy` (cross-cutting)
- `## Resources` — overview table: `Resource | Path Prefix | Endpoints | Auth Required | Detail-File`
- `## Detail Files` — link list

Per resource, write one detail file `docs/architecture/api-spec/<RESOURCE>.md`:

```yaml
---
phase: P3
subskill: data-model
kind: api-resource-detail
resource: <ResourceName>
status: active
last_updated: <DD.MM.YYYY>
---
```

Body: `## Endpoints` (per endpoint: method, path, request schema, response schema, errors, auth scope, examples), `## Resource-Specific Notes`.

### 5. Update Phase Index
Update `docs/architecture/ARCHITECTURE.md`:
- Set `**Last Updated:** <DD.MM.YYYY>`.
- In **Detail Files** table: ensure rows for `[DATA_MODEL.md](DATA_MODEL.md)` and `[API_SPEC.md](API_SPEC.md)`, both status `complete`.
- Lift load-bearing decisions into **Key Decisions** (e.g. `- API style: REST → see API_SPEC.md`, `- Soft delete for user data → see DATA_MODEL.md`).
- If a DSGVO concern surfaced (e.g. fields that need pseudonymization), add a 1-liner under **Open Risks** referencing `DATA_MODEL.md`.

## Result

- **`docs/architecture/DATA_MODEL.md`** (complete Data Model with ERD)
- **`docs/architecture/API_SPEC.md`** (API specification with endpoints and schemas)
- **`docs/architecture/ARCHITECTURE.md`** (phase index updated)
- Foundation for `/p5-implement` and all implementation work

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
