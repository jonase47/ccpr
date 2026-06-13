# Constitution Bootstrap: B2C Marketplace

> Typical Constitution for a marketplace with provider + consumer (two-sided market), B2C, BFSG-relevant, intermediary obligations.

---

## Inviolable (Non-Negotiable)

- **DSGVO Joint-Controller / data processing agreement:** Clarify the arrangement with providers (Joint Controller under Art. 26 or data processing agreement under Art. 28). Privacy policy must be transparent for both sides. **Reference:** Art. 26/28 DSGVO.
- **BFSG-A11y WCAG 2.2 AA:** Marketplace is a B2C consumer offering — BFSG scope is triggered. Full funnel (browse, buy, provider onboarding from the B2C perspective) must be accessible. **Reference:** BFSG §3.
- **EU intermediary obligations / DSA:** At >50 M monthly active users (DSA-VLOP) or when brokering products/services: complaint mechanism, transparency report, trusted-flagger concept required. **Reference:** DSA Art. 16/24.
- **AML / KYC obligations for payment flows:** If the marketplace processes payments: KYC for providers (provider verification), identity proof above defined thresholds. Otherwise: delegate to payment provider (Stripe Connect / Mangopay). **Reference:** GwG, MiCA for crypto.
- **Review system integrity:** Prevent fake reviews (verified purchase, Sybil protection); providers must not be able to delete their own reviews. **Reference:** UWG, EU Omnibus Directive.

## Default (Deviate with Justification)

- **Tech-Stack:** {language} {framework}, PostgreSQL, ElasticSearch/Meilisearch for search, Redis for caching.
- **Payment provider:** Stripe Connect (or Mangopay) as default — KYC, payouts, and tax reporting outsourced.
- **Language:** UI multilingual (DE/EN minimum), content (listings) provider-generated.
- **Search/Ranking:** Algorithm documented, A/B-test capable, no pay-for-placement without disclosure.
- **Monetization:** Commission per transaction (10–15 % default) OR subscription for providers. Mixed model via ADR.

## Aspirational

- **Liquidity metric:** ≥50 % of listings receive an interaction within 30 days.
- **Time-to-First-Match:** <7 days from listing creation to first inquiry.
- **Trust KPIs:** Refund rate <5 %, dispute resolution time <72 h.
- **A11y audit:** Annual triple-coding (designer + UX-A11y + real users with disabilities, n≥3).
- **Provider activity rate:** ≥40 % of providers are monthly active (login + listing update or new inquiries).
