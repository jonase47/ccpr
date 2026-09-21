---
phase: P6
subskill: p6-pentest-authz
status: skeleton
last_updated: {{DD.MM.YYYY}}
parent_index: PENTEST.md
---

# Authorization Tests (P6 Sub-Index) — Index

**Status:** Skeleton — populated by `/p6-pentest-authz`.

> Note: For a single-user, local-only app this sub-index is often minimal —
> the authorization boundary reduces to device/OS-level access control. The slot is kept because
> most projects add a multi-user, networked, or multi-tenant mode later, at which point
> role/permission boundaries, session handling, and cross-tenant isolation must be tested.

## Findings

<!-- /p6-pentest-authz enters findings here. -->

## Test Scenarios

| Scenario | Status |
|---|---|
| Unauthenticated request to a protected resource is denied | pending |
| Authenticated user cannot access another user's/tenant's resources (IDOR/BOLA) | pending |
| Role/permission boundary is enforced — no horizontal or vertical privilege escalation | pending |
| Session/token expiry and revocation take effect immediately, not just on next login | pending |

## Open Risks

<!-- Critical Items. -->
