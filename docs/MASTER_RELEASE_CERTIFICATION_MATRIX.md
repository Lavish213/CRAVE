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

## Evidence conventions

What counts as proof, decided now rather than left to whoever runs a
gate to judge afterward. "Looks good" is never sufficient on its own.

- **Config/code verification**: quote the exact file/line/value, as
  every PASS row in this matrix already does.
- **API/endpoint checks**: the exact command run and its actual output
  (status code, response body) — not a paraphrase of what it probably
  returned.
- **Device/UI verification**: a screen recording for anything with a
  transition, permission dialog, or timing element; a screenshot is
  acceptable only for a static end-state.
- **Third-party dashboard results**: the specific identifier that
  proves it (a Sentry event ID/link, an EAS build ID, a Railway
  deployment ID, a store-console submission status with a timestamp)
  — not "checked the dashboard, looks fine."
- **Server-side confirmation for destructive actions** (account
  deletion, data removal): confirm the actual row/object is gone at
  the data layer, not just that the client showed a success state —
  this exact gap (client claims success, server didn't actually
  finish) was a real Phase 7 finding, and evidence conventions should
  make it structurally impossible to re-introduce during certification.
- **Every result** gets a date and who ran it, recorded in both the
  specific runbook (a dated Result section) and this matrix (the
  item's status line) — see Section 12 for the failure-history
  convention specifically.

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
- **Evidence**: `docs/SENTRY_PRODUCTION_VERIFICATION.md` (PR #140). Repo-side wiring confirmed real: `app/main.py`'s `sentry_sdk.init()` is gated on `settings.sentry_dsn`, tags `environment=settings.app_env`, sets `send_default_pii=False`; `global_exception_handler` calls `capture_exception`; a purpose-built test endpoint (`GET /api/v1/debug/sentry-test`, gated by `require_debug_api_key`) already exists for triggering a real, safe test event.
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

### 3.4 Final policy/current-requirements refresh

- **Bucket**: 1 (the check itself is repo/web research; any resulting doc change is bucket 1)
- **Status**: **NOT STARTED** — deliberately not markable PASS today.
- **Procedure**: immediately before submission (not at any earlier point), re-confirm Apple's and Google Play's *current* privacy-policy, account-deletion, and Data Safety requirements against `docs/PROVIDER_DATA_FLOW_INVENTORY.md` and Sections 3/8 of this matrix — platform rules change, and a requirement satisfied today can drift out of date by submission time.
- **Expected result**: no discrepancy between what this matrix assumes and the platforms' actual current rules at submission time.
- **Responsible environment**: repo/web research, done by whoever runs final submission prep.
- **Remediation path**: update the affected section(s) and re-verify before proceeding — this gate should **never be permanently marked PASS**; treat it as re-run immediately before every submission, including future app updates.

---

## Section 4 — Production infrastructure verification

### 4.1 `APP_ENV=prod` and related Railway environment variables

- **Bucket**: 2 (procedure written) → 3 (execution)
- **Status**: **READY FOR HUMAN VERIFICATION** — the dependency is real and load-bearing (see 2.3): if `APP_ENV` isn't `prod`, an entire security hard-fail gate silently no-ops, so this is one of the highest-leverage items on this matrix.
- **Evidence**: `docs/RAILWAY_PRODUCTION_ENV_VERIFICATION.md` — formalizes `app/main.py`'s own `_validate_prod_config()` checklist (`APP_ENV`, `SECRET_KEY`, `DATABASE_URL`, `SUPABASE_URL`, `CORS_ALLOW_ORIGINS`, `API_KEY`) into a runbook, the same way `docs/SENTRY_PRODUCTION_VERIFICATION.md` formalized Sentry's.
- **Procedure**: the doc's 3 ordered proofs — (1) confirm `APP_ENV=prod` directly in the Railway Variables tab (the single highest-leverage check — everything else is enforced automatically once this is correct, but nothing is enforced until it is), (2) confirm the service actually boots and serves `/health`/`/api/v1/debug/version` (an indirect proof that `_validate_prod_config()`'s full checklist already passed, since the service couldn't have booted otherwise), (3) directly spot-check each variable's value for production-appropriateness, not just presence. Full fail-path (reading the exact `startup_validation_failed` log line if the service won't boot) is in the doc.
- **Expected result**: `APP_ENV=prod`, the service is live and serving the expected deploy, and every checked variable is production-appropriate on inspection.
- **Responsible environment**: Railway dashboard.
- **Remediation path**: set the missing/wrong var, redeploy, confirm the service boots and `/health`/`/api/v1/debug/version` respond. If `SECRET_KEY`/`DATABASE_URL` changed, expect existing signed ranking-comparison tokens to invalidate — expected, not a bug.

### 4.2 Supabase production configuration

- **Bucket**: 2 (procedure written) → 3 (execution)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/RUNBOOK_SUPABASE_PRODUCTION.md` — grounded in `backend/app/core/user_auth.py`'s actual JWKS-based verification (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, ES256/RS256 only) and `account_deletion_service.py`'s use of `SUPABASE_SERVICE_ROLE_KEY`.
- **Procedure**: the doc's 3 proofs — (1) all four Supabase values (backend `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`, frontend `EXPO_PUBLIC_SUPABASE_URL`/`EXPO_PUBLIC_SUPABASE_ANON_KEY`) point at the same real production project, (2) Google/Apple OAuth providers are configured on that specific project, (3) a real end-to-end sign-in succeeds against production.
- **Expected result**: sign-in works end-to-end against the real production Supabase project.
- **Responsible environment**: Supabase dashboard + Railway + EAS env.
- **Remediation path**: correct whichever var/provider config is wrong per the doc's fail-path; re-test sign-in.

### 4.3 Cloudflare R2 production bucket/configuration

- **Bucket**: 2 (procedure written) → 3 (execution)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/RUNBOOK_R2_PRODUCTION.md` — grounded in `backend/app/services/upload/r2_client.py`'s actual env-var usage and the previously-fixed `R2_PUBLIC_BASE_URL` vs. S3-endpoint distinction.
- **Procedure**: the doc's 3 proofs — (1) credentials/bucket identity match the production bucket, (2) the public-serving URL actually resolves, (3) a real upload → read → delete round-trip succeeds against production.
- **Expected result**: photo/video upload and public serving work end-to-end against production R2.
- **Responsible environment**: Cloudflare dashboard + Railway.
- **Remediation path**: correct the misconfigured var per the doc's fail-path; re-test the round-trip.

### 4.4 Push notification configuration

- **Bucket**: 2 (procedure written) → 3 (execution)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/RUNBOOK_PUSH_NOTIFICATIONS_PRODUCTION.md` — grounded in `app/services/notifications/expo_push.py`'s actual implementation (a plain unauthenticated POST to Expo's push API, best-effort/swallowed failures, no Enhanced Push Notification Security token in use — flagged as an open decision, not a defect).
- **Procedure**: the doc's 3 proofs — (1) platform push credentials registered with Expo for the production build, (2) a device actually registers a push token server-side, (3) a real push is sent and received on both platforms.
- **Expected result**: a signed production build receives a push notification on both iOS and Android.
- **Responsible environment**: Apple Developer / Firebase / Expo push service dashboards + a physical device (overlaps Section 6).
- **Remediation path**: fix the credential/config gap per the doc's fail-path; re-send the test push. Separately decide (not a blocking defect) whether Enhanced Push Notification Security should be adopted before certifying this PASS.

### 4.5 Google Maps/Places production keys and restrictions

- **Bucket**: 2 (procedure written) → 3 (execution)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/RUNBOOK_GOOGLE_MAPS_PLACES_PRODUCTION.md` — grounded in `frontend/app.config.js`'s env-driven key injection and `backend/app/config/settings.py`'s separate `google_places_api_key`/`google_places_max_calls_per_run` safety cap.
- **Procedure**: the doc's 3 proofs — (1) the Android Maps key is restricted to `com.crave.app` + the production signing SHA-1, (2) the backend Places key is a distinct, appropriately-scoped/capped server key, (3) the map actually renders on a production Android build.
- **Expected result**: Maps renders on a production Android build; no key is usable outside its intended scope if extracted from the binary.
- **Responsible environment**: Google Cloud Console.
- **Remediation path**: apply the correct restriction per the doc's fail-path; rebuild if the key value itself needs to change.

### 4.6 Client/native crash observability decision

- **Bucket**: 1 (decision + any resulting integration work)
- **Status**: **NOT STARTED** — confirmed absent, not a regression. `docs/PROVIDER_DATA_FLOW_INVENTORY.md`'s Sentry entry confirms no `@sentry/react-native`, no Expo Sentry config plugin, and no client-side `Sentry.init`/`captureException` exists anywhere in `frontend/`. Backend Sentry (Section 2.2) covers server-side errors only — a client-side crash (a JS exception during render, a native crash) currently has no observability path at all.
- **Procedure**: not yet written — this needs a product decision first (does this release need client crash reporting before shipping, or is backend-only observability an acceptable v1 posture), then, if yes, an integration + its own verification runbook mirroring Section 2.2's structure.
- **Expected result**: an explicit, documented decision either way — not silence.
- **Responsible environment**: repo-only for the decision and any resulting integration.
- **Remediation path**: n/a — this is a decision gate, not a defect. Do not mark this PASS by default; mark it PASS only once the decision is made and, if "yes," the integration is verified.

---

## Section 5 — EAS + native production build

### 5.0 Preflight gate (run before spending time on a signed build)

Building a signed candidate is expensive (real EAS build minutes, and
every rebuild invalidates the "one candidate, one certification"
principle in Section 10/13). Confirm all of the following **before**
running `docs/RUNBOOK_EAS_SIGNING_PRODUCTION_BUILD.md`:

- [ ] `main` is clean — no uncommitted changes, no open PRs with
      required fixes still pending merge.
- [ ] CI is green on `main`'s current head (typecheck, full test
      suites, both SQLite and real-Postgres backend lanes).
- [ ] CodeQL is green on `main`'s current head.
- [ ] No unresolved P0/P1 — specifically, the RELEASE DEFECT items in
      `docs/SCREEN_UX_FINDINGS_TRIAGE.md` are either fixed or
      explicitly deferred with a documented reason.
- [ ] The PRE-RELEASE POLISH pass (same triage doc) is done — building
      a candidate and then changing Feed/Place Detail/etc. afterward
      invalidates part of that candidate's certification evidence.
- [ ] Section 3 (legal pages) is at least at a stable state — a candidate
      certified before the hosted privacy policy exists will need its
      store-metadata fields revisited, though not necessarily a rebuild.
- [ ] `docs/PRODUCTION_ENVIRONMENT_MANIFEST.md` is fully resolved (every
      required variable set correctly) — Section 4's runbooks should
      all be at least attempted, ideally PASS, before building.

Only once every box is checked, proceed to build. This gate exists to
avoid rebuilding a signed binary for something that was fully
checkable beforehand.

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

- **Bucket**: 2 (procedure now written) → 3 (execution — genuinely can't be done from a repo session)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/RUNBOOK_EAS_SIGNING_PRODUCTION_BUILD.md` Steps 1-2.
- **Procedure**: confirm bundle/package identity matches store consoles, then `eas credentials` to confirm valid non-expired iOS distribution cert + provisioning profile, and a real (non-debug) Android production upload keystore.
- **Expected result**: valid, non-expired distribution certificate + provisioning profile (iOS) and a production upload keystore (Android) are configured in EAS.
- **Responsible environment**: Apple Developer Program + Google Play Console + EAS.
- **Remediation path**: generate/renew credentials through `eas credentials` or the respective console; re-run the build. If the Android keystore changes, also update the Maps key SHA-1 restriction (Section 4.5).

### 5.4 Real production release build produced

- **Bucket**: 2 (procedure now written) → 3 (execution, depends on 5.3)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/RUNBOOK_EAS_SIGNING_PRODUCTION_BUILD.md` Steps 3-4.
- **Procedure**: `eas build --profile production --platform all`, confirm the build picks up production-scoped `EXPO_PUBLIC_*` values (not `preview`/`development`), install and smoke-check on one real device per platform before proceeding to full certification.
- **Expected result**: a signed, installable production build for both platforms, confirmed talking to the real production backend.
- **Responsible environment**: EAS + the credential accounts in 5.3.
- **Remediation path**: any build failure here is diagnosed against EAS's own build logs — a config or credential fix, not an app-code fix, unless the failure is a genuine native-module/build-config bug (bucket 4).

### 5.5 Release-candidate identity record (template)

Fill in and date-stamp once per certification candidate — this is
what answers "which build actually passed" later, per the standing
concern that certification evidence is worthless if nobody can later
prove which exact binary it applies to.

```
Release candidate identity — <date>
Mobile (frontend) commit:     <git SHA>
Backend commit:               <git SHA>
Backend deployment ID:        <Railway deployment ID, from /api/v1/debug/version>
iOS version / build number:   <e.g. 1.0.0 (4)>
Android version / build:      <e.g. 1.0.0 (4)>
EAS build ID (iOS):           <build ID>
EAS build ID (Android):       <build ID>
Production environment:       <confirm Section 4 status as of this candidate>
Certification date range:     <start> to <end>
Device/OS matrix tested:      <e.g. iPhone 15, iOS 18.x; Pixel 8, Android 15>
Remediation PRs (if any):     <PR #s for any bucket-4 fixes rolled into this candidate>
Result:                       PASS / FAILED — see Section 9 for the smoke test that confirms this
```

---

## Section 6 — Physical-device certification

- **Bucket**: 2 (procedure written) → 3 (execution)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/RUNBOOK_PHYSICAL_DEVICE_CERTIFICATION.md` — a per-flow pass/fail table (auth/account lifecycle, camera/mic/media, location, notifications, background/foreground/connectivity) grounded in the UX audit's documented expected behavior, plus explicit callouts to re-check the 3 RELEASE DEFECT items from `docs/SCREEN_UX_FINDINGS_TRIAGE.md` on real hardware.
- **Procedure**: run the full table on at least one real iPhone and one real Android device, against the signed release candidate from Section 5 (not a dev/Expo-Go build).
- **Expected result**: every flow behaves as designed on real hardware, not just in the Jest/RTL simulation this repo's tests run.
- **Responsible environment**: physical iPhone + physical Android device, running the real production build from Section 5.
- **Remediation path**: a failure here is bucket 4 — a narrow, scoped bugfix PR against the specific defect (e.g. "permanently-denied camera permission doesn't route to Settings on Android 14"), not a new hardening phase.

---

## Section 6a — Performance and resilience certification

- **Bucket**: 2 (procedure) → 3 (execution)
- **Status**: **NOT STARTED** — not covered by any runbook yet; the newest category on this matrix, folded in from an independently-built companion matrix (PR #142) that covered this angle this one didn't originally have.
- **Procedure**: not yet written. Should cover, on the real signed candidate: cold-start time on representative hardware, Feed/list scrolling smoothness under real production data volume, Map pan/zoom/pin responsiveness, image/video memory pressure under repeated media flows (no crash/catastrophic degradation), API failure resilience (does the app degrade gracefully or cascade-fail when a backend call fails), upload retry/restart behavior surviving an app restart, the recommendation-event outbox recovering after restart/reconnect, and a basic production backend latency sanity check.
- **Expected result**: no release-blocking jank, memory crash, or resilience gap under realistic use.
- **Responsible environment**: physical devices (overlaps Section 6) + production backend.
- **Remediation path**: bucket 4 — a failure becomes a narrow performance/resilience bugfix PR, not a new hardening phase.

---

## Section 7 — Accessibility certification

- **Bucket**: 2 (procedure written) → 3 (execution)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/RUNBOOK_ACCESSIBILITY_CERTIFICATION.md` — a per-screen VoiceOver/TalkBack checklist (labels, focus order, state announcements, destructive-action clarity, permission-dialog handling) plus Dynamic Type, touch-target, contrast, and reduced-motion checks, in the UX audit's own priority order.
- **Procedure**: run the full checklist across Feed, Place Detail, Rank, Craves, Map, Profile/Settings, record-video, Search, Leaderboard, with VoiceOver/TalkBack actually enabled on real devices.
- **Expected result**: primary flows are fully operable with VoiceOver/TalkBack, text scales without breaking layout, and the existing contrast-audit fixes (e.g. `textSecondary`'s `#8C8C8C` value) hold up under real assistive-tech use — not just automated contrast math. Reduced-motion support is confirmed as a genuine open question (no `AccessibilityInfo.isReduceMotionEnabled()` usage found anywhere), not assumed already handled.
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

- **Bucket**: 1 (draft done) → 3 (console entry)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/PROVIDER_DATA_FLOW_INVENTORY.md` — maps every external processor (Supabase, Railway, R2, Google Maps/Places, Expo push, conditional Sentry) to exactly what CRAVE sends it, why, retention, and linkability, with an explicit section on how to translate each row into Apple's and Google's own category taxonomies.
- **Procedure**: re-confirm the inventory is current (Section 3.4's final-policy-refresh discipline applies here too), then transcribe into App Store Connect's Privacy Nutrition Label form and Play Console's Data Safety form.
- **Expected result**: a mapping ready to paste into both consoles, accurate to actual runtime behavior — matching the privacy policy and the Section 2.2/4.6 Sentry findings (server-side-only today, client absent).
- **Responsible environment**: repo-only for the draft (done); console entry is bucket 3.
- **Remediation path**: if runtime behavior changes (a new provider, a new data category collected), update the inventory first, then the console declarations — never the reverse.

### 8.3 Google Play external account-deletion URL + Privacy Policy URL fields

- **Bucket**: 3 (depends on 3.1/3.2 existing)
- **Status**: **NOT STARTED**.
- **Procedure**: paste the URLs from 3.1/3.2 into the relevant Play Console fields once they exist.
- **Expected result**: fields populated with reachable, matching URLs.
- **Responsible environment**: Play Console.
- **Remediation path**: n/a.

### 8.4 Age/content rating, app category, support/contact info, screenshots/description/metadata

- **Bucket**: 1 (drafts done) → 3 (console submission/questionnaire, screenshot capture)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/STORE_METADATA_DRAFT.md` (app name/description/category/keywords/support-contact/age-rating draft/review notes) and `docs/SCREENSHOT_CAPTURE_PLAN.md` (required screens, device sizes, ordering, captions, seeded-data plan — not final screenshots, since those wait for the PRE-RELEASE POLISH pass per Section 10/13).
- **Procedure**: fill in the draft's explicitly-marked `[pending]` fields (support URL/email, final legal entity name) with real values, complete the actual age-rating questionnaire against current store wording (not just this draft's recommendation), then capture screenshots per the capture plan once screens are finalized.
- **Expected result**: complete, accurate store listing.
- **Responsible environment**: repo/drafting is bucket 1 (done); actual console entry and screenshot capture from a real build is bucket 3.
- **Remediation path**: n/a — forward work, drafts ready for human completion.

### 8.5 UGC / moderation representation to store reviewers

- **Bucket**: 1 (draft) → 3 (confirm against actual moderation operations)
- **Status**: **NOT STARTED** — a draft exists (`docs/STORE_METADATA_DRAFT.md`'s UGC section, naming `ReportPhotoSheet` and the block flow) but explicitly flags that the actual moderation-response process/SLA has not been confirmed with whoever owns backend moderation operations.
- **Procedure**: confirm the real moderation process (who reviews reports, expected response time, escalation path) and finalize the store-facing description to match — both stores increasingly expect UGC apps to describe real moderation capability, not just that a report button exists.
- **Expected result**: an accurate description of real moderation capability and process.
- **Responsible environment**: repo for the description; confirming actual process is an internal/operational check, not a console or device dependency.
- **Remediation path**: n/a — forward work.

---

## Section 9 — Final release smoke test

- **Bucket**: 2 (procedure written) → 3 (execution)
- **Status**: **READY FOR HUMAN VERIFICATION**
- **Evidence**: `docs/RUNBOOK_FINAL_RELEASE_SMOKE_TEST.md` — a single 13-step linear journey (build-identity confirmation → fresh signup → discovery → Place Detail → rank → save/Craves → media upload → telemetry check via `/api/v1/debug/recommendation-events` → push → Sentry sanity → logout/re-login → account deletion → post-deletion access check) using the disposable-deletion test account from `docs/RELEASE_TEST_ACCOUNTS_AND_FIXTURES.md`.
- **Procedure**: run the full journey once, on the exact signed candidate, after every other certification section has passed — this is explicitly the *last* gate, not a parallel check.
- **Expected result**: every step succeeds against real production infrastructure with no manual workarounds, and step 12's server-side deletion check confirms actual removal, not just a client-side success toast.
- **Responsible environment**: a physical device (or at minimum a real build) + production backend + the debug endpoints for verification.
- **Remediation path**: bucket 4 — any failure here is a narrow, scoped bugfix PR against the specific step that failed; a failure at the integration level specifically (individually-passing pieces that don't work together) should be flagged as such.

---

## Section 10 — Screen/UX design certification track

- **Bucket**: 1 (audit + polish implementation itself is repo-only code work; no devices/consoles needed)
- **Status**: **AUDIT + TRIAGE COMPLETE, POLISH NOT STARTED**
- **Evidence**: `docs/SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md` (PR #143) — full inventory of 20 routes + 13 shared components against a 5-category framework — and `docs/SCREEN_UX_FINDINGS_TRIAGE.md`, which sorts every finding into RELEASE DEFECT (4 items — Rank's non-functional retry, record-video's silent recording failure, Leaderboard's missing Friends-sign-in state, account deletion's under-weighted visual treatment), ACCESSIBILITY (none new — deferred to Section 7's own pass), PRE-RELEASE POLISH (9 items — do before the certification candidate is built), and POST-LAUNCH (8 items — safe to defer). This track runs in parallel with, not blocking, Sections 1-9; it is a product-quality track, not a release-blocking gate the store or a platform enforces, but is explicitly part of "done" per the user's own product bar.
- **Procedure**: fix the 4 RELEASE DEFECT items as narrow bugfix PRs (same discipline as any Section 12 failure); complete the PRE-RELEASE POLISH list before Section 5.0's preflight gate is checked off; leave POST-LAUNCH items tracked but unblocking.
- **Expected result**: each RELEASE DEFECT fixed and verified; each PRE-RELEASE POLISH item fixed or explicitly deferred with a documented reason before the certification candidate is built.
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
| 3.4 | Final policy/current-requirements refresh | 1 | **NOT STARTED** (never permanently PASS) |
| 4.1 | `APP_ENV=prod` + Railway env vars | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 4.2 | Supabase production config | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 4.3 | R2 production config | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 4.4 | Push notification config | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 4.5 | Google Maps/Places production keys | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 4.6 | Client/native crash observability decision | 1 | **NOT STARTED** (decision gate) |
| 5.1 | iOS bundle ID / Android package ID | 1 | **PASS** |
| 5.2 | EAS build profiles configured | 1 | **PASS** |
| 5.3 | Apple/Android signing credentials | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 5.4 | Real production release build | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 5.5 | Release-candidate identity record | 1 | **TEMPLATE READY** (fill in per candidate) |
| 6 | Physical-device certification | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 6a | Performance and resilience certification | 2→3 | **NOT STARTED** |
| 7 | Accessibility certification | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 8.1 | Permission-explanation strings | 1 | **PASS** |
| 8.2 | Privacy Nutrition Labels / Data Safety | 1→3 | **READY FOR HUMAN VERIFICATION** |
| 8.3 | Play Console URL fields | 3 | **NOT STARTED** |
| 8.4 | Age rating/category/support/metadata | 1→3 | **READY FOR HUMAN VERIFICATION** |
| 8.5 | UGC/moderation representation | 1→3 | **NOT STARTED** |
| 9 | Final release smoke test | 2→3 | **READY FOR HUMAN VERIFICATION** |
| 10 | Screen/UX design certification track | 1 | **AUDIT + TRIAGE COMPLETE, POLISH NOT STARTED** |

**Read of the table**: 5 items are fully **PASS**. 1 is **PASS,
conditional** on a bucket-3 confirmation. 11 are **READY FOR HUMAN
VERIFICATION** — every Section 4 config runbook, EAS signing/build,
device certification, accessibility, the final smoke test, and the
Section 8 drafting items now have a complete, repo-verified procedure
waiting only on someone with the right dashboard/device/console access
to execute it. What remains genuinely **NOT STARTED** is now narrow
and specific: the hosted legal pages (blocked on a hosting decision,
Section 3.1-3.3), the final pre-submission policy refresh (3.4, by
design never permanently PASS), the client/native crash-observability
decision (4.6), Performance & Resilience certification (6a, no runbook
yet), Play Console URL field entry (8.3, trivially blocked on 3.1/3.2),
and UGC/moderation representation (8.5, needs one internal
confirmation). Codex's certification run should now be almost entirely
**execution**, not **research**: read this matrix, run the preflight
gate (Section 5.0), execute each prepared runbook in order, attach
evidence, mark PASS/FAIL, open a narrow bugfix PR only if something
fails.

## Submission gates (flat checklist)

Every one of these is release-blocking. This is the same information
as Sections 1-10, restated as a single linear checklist for the moment
of actually deciding to submit — check every box, don't submit until
all are checked.

- [ ] Hosted Privacy Policy is public, stable, and entered in both
      stores (3.1, 8.3).
- [ ] Google Play external account-deletion resource is public,
      functional, and entered in Play Console (3.2, 8.3).
- [ ] Hosted-vs-in-app legal parity confirmed (3.3).
- [ ] Final policy/current-requirements refresh done immediately
      before this submission (3.4).
- [ ] Production infrastructure verified: Railway env vars, Supabase,
      R2, push, Google Maps/Places (Section 4.1-4.5).
- [ ] Client/native crash-observability decision made and, if
      integration was chosen, verified (4.6).
- [ ] Exact signed iOS and Android release candidates built, with a
      completed release-candidate identity record (5.3-5.5).
- [ ] Physical-device functional matrix passes on iOS and Android (6).
- [ ] Performance and resilience certification passes (6a).
- [ ] Accessibility matrix passes on iOS and Android (7).
- [ ] Privacy Nutrition Labels / Data Safety declarations match the
      frozen runtime and provider set (8.2).
- [ ] Store metadata, assets, support details, and UGC/moderation
      representation are complete (8.4, 8.5).
- [ ] Final production smoke test passes on the exact submission
      candidate (9).
- [ ] No unresolved RELEASE DEFECT from the screen/UX triage remains
      (10, `docs/SCREEN_UX_FINDINGS_TRIAGE.md`).
- [ ] No unresolved P0/P1 of any kind remains.
- [ ] Any certification-generated bugfix PR has passed CI/CodeQL/tests
      and the affected gate has been re-run (Section 12).
- [ ] Rollback/release-response procedures are reviewed and current
      (`docs/RELEASE_ROLLBACK_PROCEDURES.md`) before submitting, not
      drafted only after an incident.

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

**Where that history actually lives**: every item's entry gets a
`Failure history` line the first time it fails (add the field if the
item doesn't have one yet). Format: `Failure history: <date> — <one-
line description of what failed> — fixed by PR #<n>.` Append one line
per occurrence; never overwrite a prior entry. An item with no
`Failure history` line has never failed. This makes "don't delete the
history" a checkable convention instead of an unenforced instruction —
a reviewer can grep this file for `Failure history` and see every
item's track record in one pass.

## Section 13 — Operational readiness (post-release)

Certification (everything above) is pre-release. What happens in the
hours/days immediately after release is a separate concern, prepared
now rather than improvised during an incident:
`docs/RELEASE_ROLLBACK_PROCEDURES.md` covers backend rollback,
mid-migration rollback, a critical mobile-build defect, credential
rotation, store rejection, and a post-release observability spike.
Review it before submitting, per the submission checklist above — not
just when something has already gone wrong.

## Section 14 — Continuous expansion rule

This matrix is not considered frozen until store submission. Add
newly discovered release requirements, certification failures,
store-review requirements, device-specific regressions, privacy/
provider changes, or operational dependencies as new rows or sections
rather than keeping them in chat-only notes. The final objective is
simple: **one document must be able to answer exactly what is done,
what remains, what is blocked by access, what failed, what evidence
proves each PASS, and whether the exact candidate is safe to submit.**

This matrix supersedes any other document making the same claim —
in particular, PR #142's independently-built companion matrix was
consolidated into this one (its Performance & Resilience category,
granular device/accessibility framing, explicit crash-observability
callout, and flat submission checklist are now Sections 6a, 6/7's
evidence, 4.6, and the Submission Gates checklist above) and closed
in favor of this document, per explicit direction, so there is exactly
one controlling release-certification document, not two.
