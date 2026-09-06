# CRAVE master release certification matrix

**This is the controlling document for everything remaining before
CRAVE ships.** Every requirement between "code hardening is done"
(Phases 3-7, all merged) and "submitted to the App Store / Play
Store" lives here, with one status, and — where work has actually
been done — the exact evidence, procedure, expected result,
responsible environment, and remediation path. Where work has *not*
been done yet, that's stated plainly rather than papered over.

Nothing here should require "keep looking until the app seems done"
judgment calls. Work straight down the table; when every row reads
PASS or is a physical-device/store-console box waiting on a human,
CRAVE is ready to submit.

## Status legend

| Status | Meaning |
|---|---|
| **PASS** | Verified, with evidence, from inside this repo/CI. Nothing further needed unless a later change invalidates it. |
| **READY FOR HUMAN VERIFICATION** | The procedure exists, is repo-verified where possible, and is ready to run — but running it needs access this session doesn't have (a dashboard, a device, a console). |
| **BLOCKED ON ACCESS** | Same as above, but the *procedure itself* hasn't been written yet, or a prerequisite decision (e.g. hosting location) hasn't been made — there's a gap before "ready to hand to a human," not just the handoff itself. |
| **NOT STARTED** | Acknowledged as remaining work; no procedure, draft, or evidence yet. |
| **FAILED** | Attempted and failed. Becomes a narrow bugfix PR (bucket 4 below), not a reason to reopen a hardening phase. |

## Bucket definitions

These match the four-way split already agreed:

1. **Codex can finish autonomously** — repo-only work: code, docs, audits, drafts.
2. **Codex can prepare, a human must execute** — Codex writes the exact procedure; a human with the right access runs it.
3. **Requires credentials/devices/consoles** — cannot be done from a repo session at all, by anyone, without that access.
4. **Only reopens code if certification fails** — a bucket-3 item failing becomes a narrow, scoped bugfix PR against the specific defect found, never a new giant hardening phase.

---

## Section 1 — Automated engineering (context, not a remaining gate)

| Item | Status | Evidence |
|---|---|---|
| Phases 3-7 (Authorization/Identity, Ranking, Video/Media, Telemetry/Location/Async, Release Hardening) | **PASS** | Merged: PR #132, #133, #134+#136, #135, #138. Full CI (typecheck, 400/400 frontend tests/39 suites, backend SQLite + real-Postgres, CodeQL, dependency scan) green on every merge SHA. See `.agent-bridge/STATE.md`. |

Not re-litigated here. Only reopens under bucket-4 policy (Section 12) if a later certification step proves a real regression.

---

## Section 2 — Credential & monitoring certification

### 2.1 Production credential leakage

- **Bucket**: 1 (done autonomously)
- **Status**: **PASS**
- **Evidence**: `docs/PRODUCTION_CREDENTIAL_LEAKAGE_AUDIT_2026-09-06.md` (PR #141). No committed `.env`/secret files across full git history; no hardcoded API keys/tokens/DSNs/service-role keys/DB URLs anywhere in source/tests/fixtures/scripts/data caches; `EXPO_PUBLIC_*` usage limited to 4 vars that are all legitimately public-safe by design; CI/EAS/GitHub Actions use proper env-var/secrets-context indirection throughout.
- **Procedure**: static repo audit (already run).
- **Expected result**: no plausible real credential found. Achieved.
- **Responsible environment**: repo-only.
- **Remediation path**: n/a. One dependency flagged, not a leak — see 2.3 below.

### 2.2 Sentry production monitoring

- **Bucket**: 2 (instructions prepared) → 3 (execution)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/SENTRY_PRODUCTION_VERIFICATION.md` (PR #140). Repo-side wiring confirmed real: `app/main.py`'s `sentry_sdk.init()` is gated on `settings.sentry_dsn`, tags `environment=settings.app_env`, sets `send_default_pii=False`; `global_exception_handler` calls `capture_exception`; a purpose-built test endpoint (`GET /debug/sentry-test`, gated by `require_debug_api_key`) already exists for triggering a real, safe test event.
- **Procedure**: the doc's 3 ordered proofs — (1) confirm `SENTRY_DSN`/`APP_ENV=prod`/`DEBUG_API_KEY` are set on the production Railway service, (2) `curl` the debug endpoint with the debug key, expect HTTP 500, (3) confirm the resulting event lands in the Sentry dashboard tagged `environment:prod` with no PII/secrets in it. Full fail-path (what to check if no event arrives) is in the doc.
- **Expected result**: exactly one new Sentry event, correctly tagged, clean of sensitive data.
- **Responsible environment**: Railway dashboard + Sentry project dashboard — outside this session's access.
- **Remediation path**: if `SENTRY_DSN` is unset → set it and redeploy (nothing else will work until then). If the event never arrives despite a correct `SENTRY_DSN` → work through the doc's ordered fail-path (redeploy timing, wrong DSN/project, Sentry-side rate limiting, network egress) before treating it as a code defect.

### 2.3 `SECRET_KEY` / prod-config hard-fail gate

- **Bucket**: 3 (depends on Railway's `APP_ENV` being correctly set — see 4.1)
- **Status**: **PASS, conditionally** — the code-side gate is verified; its real-world effectiveness depends on 4.1.
- **Evidence**: `app/main.py`'s `_validate_prod_config()` hard-fails startup (`raise RuntimeError`, not just a log line) if, when `APP_ENV=="prod"`: `SECRET_KEY` is still `"change-me-in-production"` or under 32 bytes, `SUPABASE_URL` is unset, `CORS_ALLOW_ORIGINS` is `"*"`, `DATABASE_URL` is unset, or `API_KEY` is unset. This check only runs `if settings.is_prod`.
- **Procedure**: none needed beyond 4.1 — if `APP_ENV=prod` is confirmed set, this gate is already proven to enforce itself at every boot.
- **Expected result**: production boots refuse to start with any of the above insecure defaults.
- **Responsible environment**: Railway (verifying `APP_ENV`, see 4.1).
- **Remediation path**: if `APP_ENV` is found *not* to be `prod` on the production service, this entire gate is silently bypassed — treat that discovery itself as the finding to fix (set `APP_ENV=prod`), not a code change.

---

## Section 3 — Legal & compliance pages

### 3.1 Hosted Privacy Policy at a permanent public URL

- **Bucket**: 1, once a hosting location is chosen (the choice itself may need a human decision — domain/hosting account — even if the page content and deployment can be done autonomously once decided)
- **Status**: **NOT STARTED** — in-app copy exists and is accurate (`frontend/app/legal/privacy.tsx`, corrected in Phase 7 to match actual deletion/retention behavior and to stop claiming an unverified frontend Sentry integration), but there is no hosted, publicly-reachable URL for it yet. Store metadata requires one.
- **Procedure**: not yet written. Needs: (1) a hosting decision (e.g. GitHub Pages off this repo, a simple static host, or wherever the eventual marketing site lives), (2) publishing the same content as the in-app page, (3) a parity check between hosted and in-app copy whenever either changes.
- **Expected result**: a stable HTTPS URL, reachable without the app installed, whose content matches `legal/privacy.tsx`.
- **Responsible environment**: wherever hosting is chosen — likely bucket 1 once decided, unless the chosen host needs an account a human must create (bucket 3 for that one-time setup).
- **Remediation path**: n/a — this is forward work, not a defect.

### 3.2 Hosted external Google Play account-deletion page

- **Bucket**: 1, same dependency as 3.1
- **Status**: **NOT STARTED**. Google Play requires this even though the in-app deletion flow (Phase 7, `settings.tsx`) already works correctly and matches the privacy policy's stated scope.
- **Procedure**: not yet written. Needs the same hosting decision as 3.1, then a page describing how to delete the account and data (in-app path, and/or a web-based path if Google requires the page itself to support deletion, not just describe it — confirm the current Play Console requirement before drafting).
- **Expected result**: a stable HTTPS URL satisfying Google Play's Data Safety / account-deletion policy.
- **Responsible environment**: same as 3.1; Play Console field entry itself is bucket 3.
- **Remediation path**: n/a — forward work.

### 3.3 Hosted-vs-in-app parity

- **Bucket**: 1
- **Status**: **NOT STARTED** (blocked on 3.1/3.2 existing at all).
- **Procedure**: not yet written — should become a simple recurring check (diff hosted page content against `legal/privacy.tsx`/`terms.tsx`) once both exist.
- **Expected result**: identical legal claims in both places, always.
- **Responsible environment**: repo + wherever hosted.
- **Remediation path**: if they diverge, update whichever is stale — usually the hosted copy, since the in-app copy ships through this repo's own release process.

---

## Section 4 — Production infrastructure verification

### 4.1 `APP_ENV=prod` and related Railway environment variables

- **Bucket**: 2 (procedure) → 3 (execution)
- **Status**: **BLOCKED ON ACCESS** — procedure not yet written as its own doc (unlike Sentry, which got one because it was investigated in depth this session). The dependency is real and load-bearing (see 2.3): if `APP_ENV` isn't `prod`, an entire security hard-fail gate silently no-ops.
- **Procedure**: not yet written. Should cover, at minimum: `APP_ENV=prod`, `SECRET_KEY` (32+ bytes, not the placeholder), `DATABASE_URL`, `SUPABASE_URL`, `CORS_ALLOW_ORIGINS` (not `"*"`), `API_KEY`, `SENTRY_DSN`/`DEBUG_API_KEY` (covered by 2.2) — i.e. formalize `_validate_prod_config()`'s own checklist into a runbook, the same way the Sentry doc formalized Sentry's.
- **Expected result**: every var `_validate_prod_config()` checks is actually set correctly in the real production Railway service (and the service actually boots — a failed boot due to this gate is itself informative, not silent).
- **Responsible environment**: Railway dashboard.
- **Remediation path**: set the missing/wrong var, redeploy, confirm the service boots and `/health` responds.

### 4.2 Supabase production configuration

- **Bucket**: 2 → 3
- **Status**: **NOT STARTED** — no repo-side or dashboard-side check has been run yet.
- **Procedure**: not yet written. Should confirm: production Supabase project URL matches `SUPABASE_URL`/`EXPO_PUBLIC_SUPABASE_URL`, anon key matches `EXPO_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` is set backend-only (never in any `EXPO_PUBLIC_*` var — confirmed absent from frontend in the 2.1 audit), and that Google/Apple OAuth providers are configured for the production Supabase project specifically (not a dev/staging one).
- **Expected result**: sign-in works end-to-end against the real production Supabase project.
- **Responsible environment**: Supabase dashboard + Railway (for the backend env vars).
- **Remediation path**: correct whichever var/provider config is wrong; re-test sign-in.

### 4.3 Cloudflare R2 production bucket/configuration

- **Bucket**: 2 → 3
- **Status**: **NOT STARTED**.
- **Procedure**: not yet written. Should confirm: `R2_ACCOUNT_ID`/`R2_ACCESS_KEY`/`R2_SECRET_KEY`/`R2_BUCKET` point at the real production bucket (not a dev/test one), `R2_PUBLIC_BASE_URL` resolves to a real reachable public URL, and that a real upload → confirm → public-fetch round-trip succeeds against production.
- **Expected result**: photo/video upload and public serving work end-to-end against production R2.
- **Responsible environment**: Cloudflare dashboard + Railway.
- **Remediation path**: correct the misconfigured var; re-test the upload round-trip.

### 4.4 Push notification configuration

- **Bucket**: 2 → 3
- **Status**: **NOT STARTED**.
- **Procedure**: not yet written. Should confirm production push credentials (APNs key/cert for iOS, FCM config for Android) are registered with Expo's push service for the production build specifically, and that a real device receives a test push.
- **Expected result**: a signed production build receives a push notification.
- **Responsible environment**: Apple Developer / Firebase / Expo push service dashboards + a physical device (overlaps Section 6).
- **Remediation path**: fix the credential/config gap; re-send the test push.

### 4.5 Google Maps/Places production keys and restrictions

- **Bucket**: 2 → 3
- **Status**: **NOT STARTED** — `frontend/app.config.js` correctly reads `GOOGLE_MAPS_ANDROID_API_KEY` from the environment (not hardcoded, confirmed in the 2.1 audit) and documents that the key should be restricted to `com.crave.app` + the release signing SHA-1, but that restriction has not been confirmed as actually configured in Google Cloud Console.
- **Procedure**: not yet written. Confirm in Google Cloud Console: the Android key is restricted to the production package name + production signing SHA-1 (not the dev/debug one); confirm `GOOGLE_PLACES_API_KEY` (backend, `google_places_api_key` setting) is a separate, appropriately-scoped key with its own usage cap (the app already has `google_places_max_calls_per_run` as a safety cap — confirm the actual Cloud Console quota/billing alert matches).
- **Expected result**: Maps renders on a production Android build; no key is usable outside its intended scope if extracted from the binary.
- **Responsible environment**: Google Cloud Console.
- **Remediation path**: apply the correct restriction; rebuild if the key value itself needs to change.

---

## Section 5 — EAS + native production build

### 5.1 iOS bundle ID / Android package ID

- **Bucket**: 1
- **Status**: **PASS**
- **Evidence**: `frontend/app.json` — `ios.bundleIdentifier: "com.crave.app"`, `android.package: "com.crave.app"`, consistent across both platforms and matching the Maps key restriction guidance in `app.config.js`'s own comments.
- **Procedure**: repo inspection (done).
- **Expected result**: both IDs are set, non-placeholder, and consistent. Confirmed.
- **Responsible environment**: repo-only.
- **Remediation path**: n/a.

### 5.2 EAS build profiles configured

- **Bucket**: 1
- **Status**: **PASS** (configuration exists) — does not confirm a production build has actually succeeded (see 5.4).
- **Evidence**: `frontend/eas.json` defines `development`, `development-simulator`, `preview`, and `production` profiles; the production profile sets `autoIncrement: true` and `channel: "production"`; `app.json`'s `extra.eas.projectId` is set.
- **Procedure**: repo inspection (done).
- **Expected result**: a real project ID and a production profile exist. Confirmed.
- **Responsible environment**: repo-only for this check.
- **Remediation path**: n/a for this item specifically.

### 5.3 Apple certificates/provisioning, Android signing credentials

- **Bucket**: 3
- **Status**: **BLOCKED ON ACCESS** — cannot be checked from this repo/session at all; requires an Apple Developer account and a Google Play Console / keystore.
- **Procedure**: not applicable to write from here — this is entirely EAS-managed-credentials or manual-credentials territory inside `eas credentials`, run by whoever holds the Apple/Google accounts.
- **Expected result**: valid, non-expired distribution certificate + provisioning profile (iOS) and a production upload keystore (Android) are configured in EAS.
- **Responsible environment**: Apple Developer Program + Google Play Console + EAS.
- **Remediation path**: generate/renew credentials through `eas credentials` or the respective console; re-run the build.

### 5.4 Real production release build produced

- **Bucket**: 3 (depends on 5.3)
- **Status**: **NOT STARTED**.
- **Procedure**: `eas build --profile production --platform all` (or per-platform), once 5.3 is resolved — not a dev/simulator build.
- **Expected result**: a signed, installable production build for both platforms.
- **Responsible environment**: EAS + the credential accounts in 5.3.
- **Remediation path**: any build failure here is diagnosed against EAS's own build logs — a config or credential fix, not an app-code fix, unless the failure is a genuine native-module/build-config bug (bucket 4).

---

## Section 6 — Physical-device certification

- **Bucket**: 2 (test script) → 3 (execution)
- **Status**: **NOT STARTED** — no device-test script has been written yet. The UX/design audit (`docs/SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md`, PR #143) documents the *expected* behavior for several of these (permission denied/blocked flows for camera/mic/location/notifications) in enough detail to seed a real script, but the script itself doesn't exist as a standalone artifact yet.
- **Procedure**: not yet written. Must cover, on at least one real iPhone and one real Android device, against a real production or production-like build: camera, microphone, video recording/upload, photo upload, location, notifications, denied permissions, permanently-denied permissions → Settings recovery, background→foreground transitions, login/logout, account deletion, offline/reconnect behavior.
- **Expected result**: every flow above behaves as designed (per the audit's documented expected states) on real hardware, not just in the Jest/RTL simulation this repo's tests run.
- **Responsible environment**: physical iPhone + physical Android device, ideally running the real production build from Section 5.
- **Remediation path**: a failure here is bucket 4 — a narrow, scoped bugfix PR against the specific defect (e.g. "permanently-denied camera permission doesn't route to Settings on Android 14"), not a new hardening phase.

---

## Section 7 — Accessibility certification

- **Bucket**: 2 (test script) → 3 (execution)
- **Status**: **NOT STARTED** — no accessibility test script exists yet.
- **Procedure**: not yet written. Must cover VoiceOver (iOS) and TalkBack (Android) passes across primary flows (Feed, Place Detail, Rank, Craves, Settings, record-video), Dynamic Type / larger text, screen-reader focus order, accessible labels (spot-checked already in earlier phases — see `ACCESSIBILITY_CONTRAST_AUDIT.md` referenced in `constants/colors.ts`'s own comments), touch-target sizes, contrast, reduced motion, and keyboard/focus behavior where applicable (web).
- **Expected result**: primary flows are fully operable with VoiceOver/TalkBack, text scales without breaking layout, and the existing contrast-audit fixes (e.g. `textSecondary`'s `#8C8C8C` value) hold up under real assistive-tech use, not just automated contrast math.
- **Responsible environment**: physical devices with VoiceOver/TalkBack enabled.
- **Remediation path**: bucket 4 — a failure becomes a narrow accessibility bugfix PR.

---

## Section 8 — App Store / Play Store compliance

### 8.1 Camera/microphone/location/photo-library permission-explanation strings

- **Bucket**: 1
- **Status**: **PASS**
- **Evidence**: `frontend/app.json`'s plugin config — `expo-location`: *"CRAVE uses your location to show nearby restaurants and personalize the map."*; `expo-image-picker`: *"CRAVE needs access to your photos so you can share pictures of food and menus with a place."*; `expo-camera`: cameraPermission *"CRAVE needs camera access so you can record a short video of your food."*, microphonePermission *"CRAVE needs microphone access to record audio with your food videos."* All four are specific to actual app functionality, not generic placeholder text — satisfying Apple's/Google's requirement for a genuine purpose string.
- **Procedure**: repo inspection (done).
- **Expected result**: store review accepts these strings as adequately specific. Cannot be fully confirmed until actual submission (bucket 3), but the strings themselves are already correct.
- **Responsible environment**: repo-only for this check; App Store/Play review is bucket 3.
- **Remediation path**: n/a unless review specifically rejects one.

### 8.2 Apple Privacy Nutrition Labels / Google Play Data Safety mapping

- **Bucket**: 1
- **Status**: **NOT STARTED** — not yet drafted. This is explicitly a bucket-1 item (Codex can map declared data categories from actual runtime behavior — what CRAVE actually collects/sends: location, photos/videos, account identifiers via Supabase, crash/error data via conditional Sentry — without needing store-console access to draft the mapping).
- **Procedure**: not yet written.
- **Expected result**: a drafted mapping ready to paste into App Store Connect / Play Console, accurate to what the app and backend actually do (matching the privacy policy and the Section 2.2 Sentry finding — server-side-only crash reporting, not client SDK).
- **Responsible environment**: repo-only for the draft; console entry is bucket 3.
- **Remediation path**: n/a — forward work.

### 8.3 Google Play external account-deletion URL + Privacy Policy URL fields

- **Bucket**: 3 (depends on 3.1/3.2 existing)
- **Status**: **NOT STARTED**.
- **Procedure**: paste the URLs from 3.1/3.2 into the relevant Play Console fields once they exist.
- **Expected result**: fields populated with reachable, matching URLs.
- **Responsible environment**: Play Console.
- **Remediation path**: n/a.

### 8.4 Age/content rating, app category, support/contact info, screenshots/description/metadata

- **Bucket**: 1 (drafting copy/category recommendation) → 3 (console submission/questionnaire)
- **Status**: **NOT STARTED**.
- **Procedure**: not yet written. Drafting (category recommendation, support email/URL, store description copy, age-rating-questionnaire answers based on actual app content) can happen autonomously; screenshots need either a real or high-fidelity build to capture from (overlaps Section 5/6).
- **Expected result**: complete, accurate store listing.
- **Responsible environment**: repo/drafting is bucket 1; actual console entry and screenshot capture from a real build is bucket 3.
- **Remediation path**: n/a — forward work.

---

## Section 9 — Final release smoke test

- **Bucket**: 2 (script) → 3 (execution)
- **Status**: **NOT STARTED** — no smoke-test script written yet.
- **Procedure**: not yet written. Must cover, on the actual signed store-candidate build pointed at production: fresh account creation, the main CRAVE flows (Feed → Place Detail → Rank, Craves, Map, Search), media upload (photo + video), verifying a recommendation/telemetry event actually lands (the repo already has `GET /debug/recommendation-events` for exactly this kind of check), receiving a push notification, then deleting the account and verifying the deletion contract (matching Phase 7's actual scope and the account-deletion UI walkthrough in the UX audit).
- **Expected result**: every step succeeds against real production infrastructure with no manual workarounds.
- **Responsible environment**: a physical device (or at minimum a real build) + production backend + the debug endpoints (`/debug/version`, `/debug/recommendation-events`) for verification.
- **Remediation path**: bucket 4 — any failure here is a narrow, scoped bugfix PR against the specific step that failed.

---

## Section 10 — Screen/UX design certification track

- **Bucket**: 1 (audit + polish implementation itself is repo-only code work; no devices/consoles needed)
- **Status**: **AUDIT COMPLETE, POLISH NOT STARTED**
- **Evidence**: `docs/SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md` (PR #143) — full inventory of 20 routes + 13 shared components against a 5-category framework. This track runs in parallel with, not blocking, Sections 1-9; it is a product-quality track, not a release-blocking gate the store or a platform enforces, but is explicitly part of "done" per the user's own product bar.
- **Procedure**: the audit's own recommended sequencing — systemic fixes first (a real `Typography` scale, a `Shadows`-adoption decision, consolidating `PlaceCard`/`PlaceCardCompact` and the duplicated ranked-row components), then the screen-specific polish pass in priority order: Feed → Place Detail → Map → Craves/Rankings → Profile/Settings → edge-state screens.
- **Expected result**: each screen reviewed against the audit's specific, named gaps (e.g. Leaderboard reusing `RankedPlaceRow`, Rank's retry button actually retrying, account-deletion's visual weight) and either fixed or explicitly deferred with a reason.
- **Responsible environment**: repo-only.
- **Remediation path**: n/a — this is the forward work itself, tracked as its own set of scoped PRs per screen/system, not a single giant redesign PR.

---

## Section 11 — Full status summary

| # | Item | Bucket | Status |
|---|---|---|---|
| 2.1 | Production credential leakage | 1 | **PASS** |
| 2.2 | Sentry production monitoring | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 2.3 | `SECRET_KEY`/prod-config hard-fail gate | 3 | **PASS, conditional on 4.1** |
| 3.1 | Hosted Privacy Policy URL | 1 | **NOT STARTED** |
| 3.2 | Hosted account-deletion page | 1 | **NOT STARTED** |
| 3.3 | Hosted-vs-in-app parity | 1 | **NOT STARTED** |
| 4.1 | `APP_ENV=prod` + Railway env vars | 2→3 | **BLOCKED ON ACCESS** |
| 4.2 | Supabase production config | 2→3 | **NOT STARTED** |
| 4.3 | R2 production config | 2→3 | **NOT STARTED** |
| 4.4 | Push notification config | 2→3 | **NOT STARTED** |
| 4.5 | Google Maps/Places production keys | 2→3 | **NOT STARTED** |
| 5.1 | iOS bundle ID / Android package ID | 1 | **PASS** |
| 5.2 | EAS build profiles configured | 1 | **PASS** |
| 5.3 | Apple/Android signing credentials | 3 | **BLOCKED ON ACCESS** |
| 5.4 | Real production release build | 3 | **NOT STARTED** |
| 6 | Physical-device certification | 2→3 | **NOT STARTED** |
| 7 | Accessibility certification | 2→3 | **NOT STARTED** |
| 8.1 | Permission-explanation strings | 1 | **PASS** |
| 8.2 | Privacy Nutrition Labels / Data Safety | 1 | **NOT STARTED** |
| 8.3 | Play Console URL fields | 3 | **NOT STARTED** |
| 8.4 | Age rating/category/support/metadata | 1→3 | **NOT STARTED** |
| 9 | Final release smoke test | 2→3 | **NOT STARTED** |
| 10 | Screen/UX design certification track | 1 | **AUDIT COMPLETE, POLISH NOT STARTED** |

**Read of the table**: 5 items are fully **PASS**. 1 is **PASS,
conditional** on a bucket-3 confirmation. 1 is **READY FOR HUMAN
VERIFICATION** (Sentry) — the strongest state short of PASS, since the
procedure is fully written and repo-verified. Everything else is
either **BLOCKED ON ACCESS** (a procedure gap, not just an access
gap) or **NOT STARTED**. The next highest-leverage bucket-1 work is
closing the "procedure not yet written" gaps in Section 4 (mirroring
what was done for Sentry) and starting the Section 8 drafting work —
both are real repo-only work Codex can do next, before this matrix's
remaining rows become purely "wait for human access."

## Section 12 — Bucket-4 policy (when to reopen code)

A certification item **failing** (Sections 6, 7, 9, or a defect
Section 4/5's verification surfaces) is never itself a reason to
reopen Phases 1-7 or start a new giant hardening phase. It becomes a
narrow, scoped bugfix PR: reproduce the specific failure, fix only
that, add a regression test where one is meaningful, and merge through
the same CI/CodeRabbit gate every prior PR in this session has used.
Update this matrix's row for the failed item from **FAILED** back to
**PASS** once the fix is verified — don't delete the failure history,
since a future regression on the same item is exactly what a later
re-certification pass should catch.
