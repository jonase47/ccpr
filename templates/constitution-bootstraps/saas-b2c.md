# Constitution Bootstrap: SaaS B2C

> Typical Constitution for SaaS web apps with B2C end-users, cloud-hosted, accounts/auth, monthly billing.
> Select this bootstrap and refine or remove individual bullets as needed.

---

## Inviolable (Non-Negotiable)

- **DSGVO-Compliance mandatory:** Privacy policy, data processing agreements (DPA) with all processors (hosting, e-mail, analytics), records of processing activities (Art. 30), no PII in logs without pseudonymisation. For tracking: cookie consent with genuine choice. **Reference:** Art. 13/25/30/32 DSGVO.
- **BFSG-A11y WCAG 2.2 AA (if B2C market access):** Contrast 4.5:1, keyboard navigation, screen-reader support, focus indicators. Verification: axe-DevTools / Lighthouse-A11y + manual VoiceOver/NVDA check. **Reference:** BFSG §3, WCAG 2.2.
- **Authentication standards:** Password hashing with bcrypt/argon2, 2FA option for account owners, session tokens with short lifetime, secure cookie flags (HttpOnly, Secure, SameSite). **Reference:** OWASP ASVS Level 2.
- **No secrets in code:** Tokens, API keys, DB credentials in environment variables or a secret manager only. CI has a secret scanner enabled. **Reference:** OWASP Top 10 A05.

## Default (Deviate with Justification)

- **Tech stack:** {Language} {Framework}, PostgreSQL as DB, Redis for caching, Nginx as reverse proxy. Change via ADR.
- **TDD discipline:** Red → Green → Refactor, 1 cycle = 1 commit, ≥70 % coverage as default target.
- **Language:** UI {target language}, code/docs English.
- **Monetisation:** Subscription (monthly/yearly) with free tier, Stripe as payment provider. Trial period 14 days.
- **Deployment:** Hetzner Cloud via Coolify, Docker containers, GitHub-/Gitea-CI/CD.

## Aspirational

- **Test coverage:** ≥80 % backend, ≥60 % frontend by MVP launch.
- **Performance:** Page-load P95 <1.5 s (Chrome Lighthouse), API latency P95 <300 ms.
- **A11y audit:** Quarterly triple-coding review (designer + UX-A11y specialist + real users with disabilities, n≥2).
- **Uptime:** ≥99.5 % monthly (measured via external monitoring).
- **User onboarding completion:** ≥70 % of sign-ups complete onboarding end-to-end.
