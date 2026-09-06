# CRAVE Master Release Certification Matrix

Last updated: 2026-09-06

## Purpose

This is the controlling finish-line document for CRAVE release certification. It is intentionally cumulative: keep adding evidence and newly discovered certification gates here until the exact signed production candidate is approved for store submission.

Do not reopen completed hardening phases without a proven regression or explicitly approved new scope. Certification failures should produce narrow remediation work and then be re-tested against the failed gate.

## Status vocabulary

- **PASS** — verified with evidence; no further action unless a regression invalidates the evidence.
- **READY FOR CODEX** — repo-accessible work that can be completed autonomously.
- **READY FOR HUMAN VERIFICATION** — procedure is known/prepared, but execution needs credentials, a physical device, production infrastructure, or a store console.
- **BLOCKED ON ACCESS** — cannot be truthfully verified from the repository/session.
- **FAILED** — verification produced a real release blocker; stop and remediate before release.
- **UNVERIFIED** — evidence is not yet sufficient.

## Release rule

CRAVE is **code-hardening complete, not release-certified**. Store submission is permitted only after all release-blocking rows below are PASS or an explicitly documented non-blocking exception is approved.

---

# A. Engineering hardening baseline

| Gate | Status | Evidence / current truth | Next action |
|---|---|---|---|
| Phases 1–5 hardening | PASS | Merged; Phase 5 follow-up PR #136 merged as `8900039a8c7c14b3db22696af6942fa7113d2dd3`. | Reopen only for proven regression. |
| Phase 6 hardening | PASS | PR #135 merged as `e7e19d73e4505282abab0009f9e98edbda3d63c5`. Recommendation/location/outbox/error-boundary work verified. | Reopen only for proven regression. |
| Phase 7 release hardening | PASS | PR #138 merged as `ee77d30279577cddfdcaaf1c54153bf0597a212f`. | Reopen only for proven regression. |
| Frontend TypeScript | PASS | Phase 7 final verification clean. | Re-run for any release-candidate code change. |
| Frontend Jest | PASS | 400/400, 39 suites at Phase 7 final gate. | Re-run for any release-candidate code change. |
| Backend SQLite tests | PASS | 1035 passed / 6 skipped at verified Phase 7 implementation gate. | Re-run for backend changes. |
| Real Postgres migration/test lane | PASS | Full chain/test lane succeeded. | Re-run for DB/model/migration changes. |
| Alembic migration topology | PASS | Exactly one head at final hardening gate. | Preserve one-head invariant. |
| Dependency vulnerability gate | PASS | `pip-audit` clean at verified implementation gate. | Re-run before final signed candidate if dependencies changed. |
| CodeQL | PASS | Phase 7 CodeQL workflow #477 succeeded. | Re-run on subsequent code PRs. |
| Conflict-marker guard | PASS | Final hardening verification succeeded. | Keep CI guard enabled. |

# B. Critical runtime/data contracts

| Gate | Status | Evidence / current truth | Next action |
|---|---|---|---|
| Account deletion app-side data sweep | PASS | Phase 7 deletes/anonymizes user-associated profile/social/activity/recommendation/saves/craves/streak/push/report/media references and owned R2 objects. | Re-test on production candidate. |
| Account deletion fail-closed semantics | PASS | Storage/DB/auth failures no longer produce false success; frontend retains session on incomplete deletion. | Production smoke test must exercise successful deletion. |
| User-uploaded R2 deletion | PASS | Implemented before DB/auth deletion with retry-safe behavior. | Verify against production R2 during final account-deletion smoke test. |
| Media transaction integrity | PASS | Phase 5 + #136 fixed capture preconditions, stale auth/account boundaries, missing files and retention behavior. | Real-device certification remains required. |
| Recommendation instrumentation | PASS | Phase 6 hardened exposure/viewability/context/session behavior. | Verify representative production flows in smoke test. |
| Location freshness/revocation behavior | PASS | Phase 6 implemented freshness and permission recovery logic. | Physical-device certification required. |
| Root application error boundary | PASS | Added and verified in Phase 6. | Exercise at least one controlled recoverable failure during certification where practical. |

# C. Credential and configuration safety

| Gate | Status | Evidence / current truth | Next action |
|---|---|---|---|
| Production credential leakage audit | PASS* | PR #141 reports no committed real secrets, hardcoded production credentials, unsafe workflow literals, or secret files, including git-history checks. `*` Treat as final PASS once PR #141 is merged. | Merge #141 after CI/review. |
| `.gitignore` secret-file coverage | PASS* | PR #141 reports `.env`, `.env.*`, `.grubhub_env` coverage. | Preserve coverage. |
| Client `EXPO_PUBLIC_*` secret classification | PASS* | Audit found four client vars and classified them public-safe by design. | Re-audit if new `EXPO_PUBLIC_*` vars are introduced. |
| Production `APP_ENV=prod` | BLOCKED ON ACCESS | Repo production safety checks depend on `settings.is_prod`; cannot prove Railway value from repo. | Railway operator confirms exact production service has `APP_ENV=prod`. |
| Production secret-key override | BLOCKED ON ACCESS | Insecure placeholder is protected by production boot validation only when production env is correctly selected. | Confirm production service boots with a non-placeholder secret and `APP_ENV=prod`. |
| Production API URL | BLOCKED ON ACCESS | Repo cannot prove deployed client points at intended production backend. | Verify EAS production env + signed build runtime. |
| Supabase production configuration | BLOCKED ON ACCESS | Requires production project/environment evidence. | Verify URL/anon client config/service-role server config and auth behavior. |
| Cloudflare R2 production configuration | BLOCKED ON ACCESS | Requires production environment/storage access. | Verify bucket, endpoint, credentials, upload/read/delete lifecycle. |
| Google Maps/Places production keys | BLOCKED ON ACCESS | Repo uses environment/secret indirection; actual production key restrictions require console access. | Verify package/bundle/API restrictions and quotas. |
| Push production configuration | BLOCKED ON ACCESS | Requires signed builds, Expo/native credentials and device receipt. | Verify on real iOS + Android devices. |

# D. Sentry / crash observability

| Gate | Status | Evidence / current truth | Next action |
|---|---|---|---|
| Backend Sentry repo wiring | PASS | `sentry-sdk[fastapi]` present; initialization is conditional on `SENTRY_DSN`; environment uses `APP_ENV`; `send_default_pii=False`; global handler captures exceptions. | Keep wiring unchanged unless certification exposes defect. |
| Controlled Sentry test endpoint | PASS | `GET /debug/sentry-test` exists and deliberately raises a static error behind `require_debug_api_key`. | Use only for controlled verification. |
| Sentry production runbook | PASS* | PR #140 adds `docs/SENTRY_PRODUCTION_VERIFICATION.md`. `*` Final PASS once #140 is merged. | Merge #140 after CI/review. |
| Production `SENTRY_DSN` configured | BLOCKED ON ACCESS | Repo cannot inspect Railway production variables. | Execute Proof 1 from Sentry runbook. |
| Production Sentry event delivery | BLOCKED ON ACCESS | Requires Railway + Sentry access. | Trigger `/debug/sentry-test`; verify event lands. |
| Sentry environment tag | BLOCKED ON ACCESS | Depends on real `APP_ENV`. | Confirm event reports `environment:prod`. |
| Sentry sensitive-data inspection | BLOCKED ON ACCESS | Source config alone cannot prove live event contains no sensitive context. | Inspect live controlled event; live inspection is authoritative. |
| Frontend/native Sentry | UNVERIFIED / NOT PRESENT | Current repo audit found no `@sentry/react-native` or Expo Sentry plugin. This is not a Phase 7 regression. | Decide release observability requirement. If client/native crash monitoring is required, approve new scope before adding an SDK. |
| Client/native/unhandled-JS production observability | READY FOR HUMAN VERIFICATION | Must be demonstrated on final production build using whatever final observability strategy is approved. | Certify before store submission. |

# E. Legal and privacy

| Gate | Status | Evidence / current truth | Next action |
|---|---|---|---|
| In-app account deletion | PASS | Implemented and hardened in Phase 7. | Production smoke test. |
| In-app privacy policy deletion wording | PASS | Phase 7 aligned wording to implemented deletion/retention behavior. | Keep synchronized with hosted policy. |
| Crash-reporting privacy wording | READY FOR CODEX | Current wording correctly says no separate in-app crash SDK but hosted/in-app disclosure must accurately cover backend Sentry if production enables it. | Finalize wording against production Sentry decision. |
| Hosted Privacy Policy | READY FOR CODEX | Required public resource; hosting implementation/location still needs completion/verification. | Build/publish permanent public URL; synchronize with in-app policy. |
| Google external account-deletion resource | READY FOR CODEX | Required in addition to in-app deletion path. | Build/publish designated web deletion resource; verify current Google policy requirements before finalizing. |
| Privacy Policy URL in App Store metadata | READY FOR HUMAN VERIFICATION | Depends on hosted URL and App Store Connect access. | Enter and validate URL. |
| Privacy Policy URL in Google Play metadata | READY FOR HUMAN VERIFICATION | Depends on hosted URL and Play Console access. | Enter and validate URL. |
| App Store privacy declarations | READY FOR HUMAN VERIFICATION | Must match final runtime, providers and SDKs. | Complete after production configuration/SDK set is frozen. |
| Google Play Data Safety | READY FOR HUMAN VERIFICATION | Must match final runtime, providers and SDKs. | Complete after production configuration/SDK set is frozen. |
| Retention/deletion disclosure consistency | UNVERIFIED | Must compare hosted policy, in-app policy, deletion page and actual production behavior as one set. | Perform final legal-copy consistency audit. |

# F. Production build and signing

| Gate | Status | Evidence / current truth | Next action |
|---|---|---|---|
| EAS production profile audit | READY FOR CODEX | Repo/config can be inspected before build. | Audit production profile, environment selection, build-number/version behavior and accidental dev flags. |
| iOS bundle identifier | READY FOR HUMAN VERIFICATION | Repo currently uses `com.crave.app`; final Apple registration/signing must match. | Verify in App Store Connect/EAS credentials. |
| Android package identifier | READY FOR HUMAN VERIFICATION | Repo currently uses `com.crave.app`; final Play registration/signing must match. | Verify in Play Console/EAS credentials. |
| iOS signing/certificates/provisioning | BLOCKED ON ACCESS | Needs Apple/EAS credentials. | Produce signed release candidate. |
| Android signing credentials | BLOCKED ON ACCESS | Needs EAS/Play credentials. | Produce signed release candidate. |
| Production iOS build | BLOCKED ON ACCESS | Requires signing/infrastructure. | Build exact candidate after config freeze. |
| Production Android build | BLOCKED ON ACCESS | Requires signing/infrastructure. | Build exact candidate after config freeze. |
| Release candidate commit/version traceability | READY FOR CODEX | `/debug/version` supports backend deployment identity; mobile build version is displayed from native metadata. | Record exact frontend/backend commits, versions, build numbers and deployment IDs used for certification. |
| OTA/update compatibility policy | UNVERIFIED / DELIBERATELY NOT INVENTED | Phase 7 found no proven active `expo-updates` runtime/update policy. | Re-audit only if OTA updates are intended for this release. |

# G. Real-device functional certification

Run against the **actual signed release candidate**, not Expo Go/dev builds.

| Gate | Status | Required proof |
|---|---|---|
| iOS fresh install / launch | READY FOR HUMAN VERIFICATION | Clean install launches and reaches intended auth/onboarding flow. |
| Android fresh install / launch | READY FOR HUMAN VERIFICATION | Same. |
| Login/auth persistence | READY FOR HUMAN VERIFICATION | Login succeeds; restart/background behavior correct. |
| Logout/account switch isolation | READY FOR HUMAN VERIFICATION | No prior-user state/media/outbox crosses account boundary. |
| Camera permission — allow | READY FOR HUMAN VERIFICATION | Capture works. |
| Camera permission — deny | READY FOR HUMAN VERIFICATION | UI remains usable and truthful. |
| Camera permanently blocked → Settings recovery | READY FOR HUMAN VERIFICATION | Recovery path opens settings and recognizes restored permission. |
| Microphone allow/deny/blocked recovery | READY FOR HUMAN VERIFICATION | Video/audio flow behaves correctly in all states. |
| Video recording | READY FOR HUMAN VERIFICATION | Start/stop/cancel lifecycle works. |
| Video upload | READY FOR HUMAN VERIFICATION | Successful upload visible/consistent; failure is retryable/truthful. |
| Photo/image upload | READY FOR HUMAN VERIFICATION | Same lifecycle expectations. |
| Missing/local-file upload edge | READY FOR HUMAN VERIFICATION | No silent success/data loss; terminal/retry state matches implementation. |
| Background → foreground during media flow | READY FOR HUMAN VERIFICATION | No corrupted state or wrong-account upload. |
| Location permission allow | READY FOR HUMAN VERIFICATION | Correct location-driven discovery behavior. |
| Location deny | READY FOR HUMAN VERIFICATION | Graceful fallback. |
| Location permanently blocked → Settings | READY FOR HUMAN VERIFICATION | Recovery works. |
| Location revocation after prior grant | READY FOR HUMAN VERIFICATION | App detects stale/revoked permission correctly. |
| Push notification permission | READY FOR HUMAN VERIFICATION | Prompt/state correct. |
| Push receipt/open behavior | READY FOR HUMAN VERIFICATION | Real device receives and opens intended destination. |
| Offline startup | READY FOR HUMAN VERIFICATION | Explicit offline/error state; no false data. |
| Network loss during primary flow | READY FOR HUMAN VERIFICATION | Retry/recovery does not duplicate destructive or analytics actions. |
| Network reconnect | READY FOR HUMAN VERIFICATION | State reconciles correctly. |
| Account deletion production path | READY FOR HUMAN VERIFICATION | Account/data deletion succeeds and deleted identity cannot continue using old session. |
| App background/foreground general regression | READY FOR HUMAN VERIFICATION | Core screens restore without stale permissions/auth/data. |

# H. Screen logic / UX certification

This is separate from visual redesign. Certification checks whether the existing release candidate behaves correctly and truthfully.

| Gate | Status | Required proof / next action |
|---|---|---|
| Complete route/screen inventory | READY FOR CODEX | Enumerate every Expo Router screen/modal and map entry/exit paths. |
| Primary navigation hierarchy | READY FOR CODEX | Verify Feed/Discovery, Place Detail, Map, Craves/Rankings, Profile/Settings and auth flows have deterministic navigation/back behavior. |
| Loading states | READY FOR CODEX | Every data-dependent primary screen has explicit loading behavior; flag blank/frozen states. |
| Empty states | READY FOR CODEX | No-results/no-saves/no-content states are intentional and actionable where appropriate. |
| Error states | READY FOR CODEX | Errors are visible, truthful, recoverable where possible and do not fake success. |
| Permission states | READY FOR CODEX + DEVICE | Audit code/state machine in repo; certify OS behavior on devices. |
| Destructive-action confirmation | READY FOR CODEX | Account deletion and other destructive flows require clear intent and truthful completion. |
| Async race/account-boundary audit | PASS / CONTINUOUS | Major known races were hardened in Phases 5–6. New screen changes must preserve account/session ownership. |
| Feed/Discovery behavior | READY FOR CODEX | Final screen-state/interaction audit against release candidate. |
| Place Detail behavior | READY FOR CODEX | Audit media, menu, ranking/save/crave/social actions and state recovery. |
| Map behavior | READY FOR CODEX + DEVICE | Audit visible-pin/context logic; device-certify location/gesture/performance. |
| Craves/Rankings behavior | READY FOR CODEX | Audit async truth, loading/error/empty and event behavior. |
| Profile/Settings behavior | READY FOR CODEX | Audit auth/account state, legal links, version display and deletion path. |
| Visual consistency pass | READY FOR CODEX | Inventory typography, spacing, cards, buttons, iconography, imagery, overlays, sheets and motion; do not redesign merely for novelty during certification. |
| CRAVE uniqueness/design-system compliance | READY FOR CODEX | Flag generic/template drift while preserving approved product identity. |

# I. Accessibility certification

| Gate | Status | Required proof |
|---|---|---|
| Static accessibility/code audit | READY FOR CODEX | Labels/roles/hints/state semantics, obvious target-size and focus issues. |
| VoiceOver primary flows | READY FOR HUMAN VERIFICATION | Real iOS signed candidate. |
| TalkBack primary flows | READY FOR HUMAN VERIFICATION | Real Android signed candidate. |
| Dynamic Type / large text | READY FOR HUMAN VERIFICATION | No clipped/hidden critical content/actions. |
| Screen-reader focus order | READY FOR HUMAN VERIFICATION | Logical order on all primary flows/modals. |
| Touch targets | READY FOR CODEX + DEVICE | Static audit plus real-device interaction. |
| Contrast | READY FOR CODEX + DEVICE | Token/static review plus actual rendered screens. |
| Reduced motion | READY FOR CODEX + DEVICE | Respect platform preference where motion exists. |
| Accessible error/permission announcements | READY FOR HUMAN VERIFICATION | Screen reader receives meaningful state changes. |

# J. Performance and resilience certification

| Gate | Status | Required proof / next action |
|---|---|---|
| Cold-start sanity | READY FOR HUMAN VERIFICATION | Measure/observe signed candidate on representative iOS/Android hardware. |
| Feed/list scrolling | READY FOR HUMAN VERIFICATION | No release-blocking jank, runaway rendering or memory behavior. |
| Map interaction/performance | READY FOR HUMAN VERIFICATION | Pan/zoom/pin interactions remain responsive with production data. |
| Image/video memory pressure | READY FOR HUMAN VERIFICATION | Repeated media flows do not crash or degrade catastrophically. |
| API failure resilience | READY FOR CODEX + HUMAN | Repo state audit plus controlled production/staging failures. |
| Upload retry/restart behavior | READY FOR HUMAN VERIFICATION | Pending work survives/reconciles according to contract. |
| Recommendation outbox restart behavior | READY FOR HUMAN VERIFICATION | Durable account-owned events recover after app restart/reconnect. |
| Production backend latency sanity | BLOCKED ON ACCESS | Observe production endpoints and correlate with diagnostics when needed. |

# K. Store metadata and policy certification

| Gate | Status | Required proof / next action |
|---|---|---|
| App name/subtitle/short description | READY FOR CODEX | Draft/finalize truthful store copy. |
| Long description | READY FOR CODEX | Draft/finalize without unsupported claims. |
| Keywords/category | READY FOR CODEX + HUMAN | Prepare recommendation; select in consoles. |
| Screenshots | READY FOR HUMAN VERIFICATION | Capture from final visual/release candidate at required device sizes. |
| App icon/splash assets | READY FOR CODEX + HUMAN | Repo audit then verify rendered native build. |
| Support/contact resource | UNVERIFIED | Confirm public support path/contact details required by stores. |
| Content/age rating | READY FOR HUMAN VERIFICATION | Complete questionnaires based on actual app content/UGC. |
| UGC moderation/reporting representation | READY FOR CODEX + HUMAN | Ensure store answers/copy match actual reporting/blocking/moderation behavior. |
| Camera/microphone/location purpose strings | READY FOR CODEX + DEVICE | Audit config copy and verify OS prompts. |
| Google account-deletion URL | BLOCKED until hosted | Enter designated URL after page is public. |
| Store privacy/data disclosures | BLOCKED until runtime frozen | Complete only after final SDK/provider/config set is frozen. |

# L. Final production smoke test

This must be performed on the exact signed candidate intended for submission.

| Gate | Status | Required proof |
|---|---|---|
| Exact build identity recorded | READY FOR HUMAN VERIFICATION | iOS/Android version + build, commit, backend deployment commit/ID. |
| Fresh account creation/login | READY FOR HUMAN VERIFICATION | New user can enter product normally. |
| Discovery/feed | READY FOR HUMAN VERIFICATION | Production data loads and interactions work. |
| Place detail | READY FOR HUMAN VERIFICATION | Core content/actions work. |
| Save/crave/rank | READY FOR HUMAN VERIFICATION | State persists and reconciles. |
| Map/location | READY FOR HUMAN VERIFICATION | Production location flow works. |
| Media capture/upload | READY FOR HUMAN VERIFICATION | Real image/video path succeeds. |
| Recommendation/event telemetry sanity | READY FOR HUMAN VERIFICATION | Representative events appear once with correct context. |
| Push notification | READY FOR HUMAN VERIFICATION | Real push arrives/opens correctly. |
| Sentry controlled backend event | READY FOR HUMAN VERIFICATION | Production event arrives with correct environment and no observed sensitive leakage. |
| Logout/relogin | READY FOR HUMAN VERIFICATION | State isolation/persistence correct. |
| Account deletion | READY FOR HUMAN VERIFICATION | Final destructive contract works in production. |
| Post-deletion access | READY FOR HUMAN VERIFICATION | Deleted account/session cannot continue as an active identity. |

# M. Submission gates

All of these are release-blocking.

- [ ] Hosted Privacy Policy is public, stable and entered in both stores where required.
- [ ] Google external account-deletion resource is public, functional and entered in Play Console.
- [ ] Production infrastructure configuration is verified.
- [ ] Production Sentry/backend observability is verified, and client/native crash-observability decision is documented.
- [ ] Credential-leak audit PR #141 is merged and remains valid for the release candidate.
- [ ] Sentry runbook PR #140 is merged.
- [ ] Exact signed iOS and Android release candidates are built.
- [ ] Real-device functional matrix passes on iOS and Android.
- [ ] Accessibility matrix passes on iOS and Android.
- [ ] Final privacy/Data Safety declarations match the frozen runtime and SDK/provider set.
- [ ] Store metadata/assets/support details are complete.
- [ ] Final production smoke test passes on the exact submission candidate.
- [ ] No unresolved P0/P1 release blocker remains.
- [ ] Any certification-generated code fix has passed CI/CodeQL/tests and the affected certification gate has been re-run.
- [ ] Final release evidence records exact frontend/backend commits, build numbers, deployment identity and certification date.

# N. Certification failure protocol

When any gate fails:

1. Mark it **FAILED** here with concrete evidence; do not soften it to UNVERIFIED.
2. Identify the exact root cause before editing code/config.
3. If repo remediation is required, create a narrow branch/PR scoped only to the proven failure.
4. Run relevant regression tests plus normal CI/security gates.
5. Rebuild the signed candidate if native/runtime output changed.
6. Re-run the failed certification gate on the new candidate.
7. Mark PASS only with evidence.

# O. Continuous expansion rule

This matrix is not considered frozen until store submission. Add newly discovered release requirements, certification failures, store-review requirements, device-specific regressions, privacy/provider changes, or operational dependencies as new rows rather than keeping them in chat-only notes.

The final objective is simple: **one document must be able to answer exactly what is done, what remains, what is blocked by access, what failed, what evidence proves each PASS, and whether the exact candidate is safe to submit.**
