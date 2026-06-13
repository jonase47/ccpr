# Constitution Bootstrap: B2B Tool

> Typical Constitution for an internal B2B tool or B2B SaaS. B2B customers, no BFSG scope, but enterprise topics apply.

---

## Inviolable (Non-Negotiable)

- **DSGVO-Compliance B2B:** Data processing agreement (DPA) with clients (standard contract), sub-processors disclosed, data residency EU (DE preferred), deletion/export obligations (Art. 17/20) implemented. **Reference:** Art. 28 DSGVO.
- **Tenant Isolation:** Multi-tenancy with hard data isolation at application and DB level. Cross-tenant queries are forbidden or require explicit privilege. **Reference:** OWASP ASVS V1, BSI IT-Grundschutz.
- **Audit Trail Mandatory:** All data-mutating operations are logged with actor, timestamp, and diff. Logs immutable or cryptographically secured. **Reference:** ISO 27001 A.12.4, DSGVO Art. 30.
- **No Secrets in Code:** API keys, tokens, DB credentials via secret manager / environment only. Secret scanner active in CI.
- **Explicit Role/Permission Model:** RBAC or ABAC, no implicit trust. Default-deny over default-allow. **Reference:** OWASP ASVS V4.

## Default (Deviate with Justification)

- **Tech Stack:** {language} {framework}, PostgreSQL with row-level security or schema-per-tenant, Redis for sessions.
- **TDD Discipline:** Red → Green → Refactor, 1 cycle = 1 commit, ≥75 % backend coverage.
- **Language:** UI English and German, code/docs English.
- **Deployment:** Self-hosted on Hetzner (Coolify) or customer on-premise. Docker container, Helm chart for K8s.
- **SSO/SAML/OIDC:** Mandatory from mid-market customers (>50 seats).

## Aspirational

- **Test Coverage:** ≥85 % backend, ≥50 % frontend.
- **Performance:** API latency P95 <500 ms, bulk imports scalable to 1 M records.
- **Audit Log Coverage:** 100 % of all write operations.
- **Onboarding Time:** ≤2 h from sign-up to first production user.
- **Contract Standardisation:** Standard DPA, SLA template, penetration test report available annually.
