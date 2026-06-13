# Constitution Bootstrap: Mobile App B2C

> Typical Constitution for native mobile apps (iOS/Android), B2C end users, App Store distribution.

---

## Inviolable (Non-Negotiable)

- **DSGVO-Compliance:** Privacy policy linked from app settings; tracking consent obtained before first data flow (including crash reporters); Privacy Manifest (`PrivacyInfo.xcprivacy` iOS / Data Safety Form Android) mandatory. **Reference:** Art. 13/25 DSGVO, Apple Privacy Manifest, Google Data Safety.
- **BFSG-A11y WCAG 2.2 AA:** Full VoiceOver/TalkBack support, Dynamic Type, touch target ≥44×44 pt iOS / 48×48 dp Android, contrast 4.5:1, status never conveyed by color alone. **Reference:** BFSG §3, WCAG 2.2, Apple HIG, Material Design A11y.
- **App-Store-Compliance:** Apple Guidelines + Google Play Policies — no prohibited content, transparent IAP, parental controls for 4+/Everyone rating. **Reference:** Apple App Store Guidelines, Google Play Developer Policy.
- **No Secrets in Code:** No API keys, tokens, or certificates in the repo. Code-signing certificates via secure storage (Keychain Access / Android Keystore).

## Default (Deviate with Justification)

- **Tech-Stack:** {Native Swift/SwiftUI iOS, Kotlin/Compose Android} OR {Cross-Platform Flutter/RN}. Native preferred when A11y or performance is a primary concern.
- **TDD Discipline:** Red → Green → Refactor, 1 Cycle = 1 Commit, ≥60 % coverage domain layer.
- **Language:** Localised UI {primary locale, e.g. English}, code/docs English.
- **Monetisation:** Freemium + In-App Purchase (one-time preferred over subscription); Apple/Google handle tax and refunds.
- **Min-Targets:** iOS 16+ / Android API 26+. Higher targets allowed (e.g. iOS 17 for SwiftData) via ADR.

## Aspirational

- **Test-Coverage:** ≥80 % domain-package unit tests, ≥40 % UI tests (XCUITest / Espresso).
- **Performance:** Cold-start P95 <2.5 s on a mid-range device (iPhone 13/Pixel 6), 60-fps scroll performance.
- **A11y-Audit:** Per release: triple-check (Accessibility Inspector + UX review + real users n≥2).
- **App-Store-Rating:** ≥4.0 after first 100 reviews.
- **Crash-Free-Sessions:** ≥99.5 % (with active crash reporting; otherwise best effort).
