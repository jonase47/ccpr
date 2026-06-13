# Constitution Bootstrap: On-Device / Privacy-First

> Typical Constitution for on-device apps without a backend, without accounts, Privacy-by-Design.
> Examples: local health trackers, on-device AI apps, offline tools.

---

## Inviolable (Non-Negotiable)

- **On-Device-First Architecture:** Processing runs on the device. Cloud usage is **exclusively** for (a) static content download and (b) an optional opt-in cloud path. User data does not leave the device without explicit consent.
- **DSGVO Household Exemption or Mitigation:** For pure on-device usage, Art. 2(2)(c) DSGVO (household exemption) applies. Conditions: no account, no tracking, no telemetry backend. For CDN logs: IP anonymisation, DPA with host. **Reference:** Art. 2(2)(c) DSGVO, ECJ C-25/17 (Jehovah's Witnesses).
- **BFSG-A11y WCAG 2.1 AA or 2.2 AA:** The A11y standard applies even without a backend. For privacy-first audio apps (e.g. local TTS): audio-first with parallel visual output.
- **Privacy Manifest:** On iOS: `PrivacyInfo.xcprivacy` with no Required-Reason API violations. On Android: Data Safety Form filled out honestly. For third-party libs: check their manifests. **Reference:** Apple Privacy Manifest, Google Data Safety.
- **Zero-Tracking-by-Default:** No telemetry, no crash reporter with data transfer, no analytics. Optionally available as opt-in via self-hosted Sentry or equivalent.

## Default (Deviate with Justification)

- **Tech-Stack:** Native (Swift iOS, Kotlin Android) preferred for full privacy manifest control. Cross-platform (Flutter, RN) only with a small dependency surface.
- **TDD Discipline:** Red → Green → Refactor, 1 cycle = 1 commit, ≥75 % domain coverage.
- **Language:** Localised {target locale + English}, code/docs English.
- **Monetisation:** One-time IAP preferred (no subscription pressure, no "loss" on cancellation). Ads only without trackers (e.g. local, non-personalised ads).
- **Local Data Storage:** SQLite or SwiftData / Room. Encryption at rest via OS mechanisms (NSFileProtectionComplete / EncryptedSharedPreferences).

## Aspirational

- **Privacy Marketing:** Privacy as a selling point, prominently featured on the landing page and App Store description.
- **Test-Coverage:** ≥85 % Domain, ≥40 % UI.
- **Performance:** App runs offline without loss of functionality; online features are declared as "convenience".
- **Reviewer Test in Privacy Mode:** TestFlight / internal test reviewer verifies full app functionality in airplane mode.
- **A11y Audit:** Triple-coding per release including real users with disabilities n≥2.
