# Auth / Settings / Activity completion gap log

Date: 2026-09-12
Base: `755f02bb13315c7149a3e110eb05022f3e1b3513` (`origin/main`)
Scope: completion/hardening only; Rank, Food Evidence/Add Spot,
Profile/Taste/social cleanup, Craves, Feed, Search/Map, Place Detail, and
Posting V2 were not reopened.

| Severity | Verified gap | Root cause | Files | Outcome |
| --- | --- | --- | --- | --- |
| P1 | Activity was static copy promising unsupported follow requests/reactions | No screen query and no authenticated self-history route, despite real ranking/follow events already being recorded | `frontend/app/activity.tsx`, `frontend/src/api/social.ts`, `backend/app/api/v1/routes/feed_social.py`, `backend/app/services/social/activity_service.py` | Fixed with a private, chronological, authenticated history over existing factual events only; loading, empty, error, cached/degraded, refresh, and signed-out states are distinct. |
| P1 | Direct account switch could retain Account A query/saves state for Account B | Cleanup lived only in the explicit `signOut()` method | `frontend/src/stores/authStore.ts` | Fixed at the auth-state boundary; account-id changes clear Query and saves state before publishing the new user. Late session hydration can no longer overwrite a newer auth event, and duplicate listeners are disposed. |
| P1 | AuthSheet Terms and Privacy looked interactive but did nothing | Styled nested text had no navigation handler | `frontend/src/components/AuthSheet.tsx` | Fixed with labeled, 44-point link controls to the existing legal routes. |
| P1 | Root notification-response failures and malformed payloads silently lost user-visible intent | Empty catches and an unvalidated `placeId`-only router | `frontend/app/_layout.tsx` | Fixed with controlled user feedback and development diagnostics. Background video/draft/streak failures are explicitly classified as recoverable and retain their existing retry behavior. |
| P1 | Native builds did not register the locked `https://crave.app` universal-link domains | Missing iOS associated domain and Android verified intent filters | `frontend/app.json` | Fixed for `/place`, `/rank`, and `/user`; `crave://` remains the fallback scheme. |
| P2 | Production configuration failure exposed developer environment-variable setup instructions | One development-oriented message rendered in all builds | `frontend/app/_layout.tsx` | Fixed with separate development and production-safe copy. |
| P2 | Sign-out and successful deletion had no explicit completion feedback | Settings invoked completed lifecycle operations without a visible success outcome | `frontend/app/settings.tsx` | Fixed with success confirmation; deletion failure still leaves the session active and reports the failure. |
| Verified closed | Rate CRAVE placeholder | Historical finding was stale | `frontend/app/settings.tsx` | Already removed on current main; no change. |
| Verified closed | Settings Terms/Privacy destinations | Historical concern did not apply to Settings | `frontend/app/settings.tsx`, `frontend/app/legal/*` | Already navigated to real in-app documents; no change. |
| Deferred | Password recovery, provider unlink, and forced reauthentication UI | No complete app route/backend contract exists for these lifecycle operations | Auth/backend contract | Deferred rather than advertising controls that cannot complete. Email sign-in/signup and Apple/Google browser fallback remain unchanged. |
| Deferred | Secure storage migration for Supabase refresh tokens | Current supported implementation uses Supabase's AsyncStorage adapter; no tested migration/rollback or existing SecureStore dependency is present | `frontend/src/lib/supabase.ts` | Intentionally not changed. A security-sensitive storage migration needs a separately approved, device-tested plan. |
| Deferred (outside repo/app scope) | Universal-link web fallback and domain association files | Native registration alone cannot publish `apple-app-site-association`, `assetlinks.json`, or useful web fallback pages on `crave.app` | Web/domain infrastructure | Deployment owner must publish and verify these artifacts before release certification. |
| Deferred | Device proof for cold/warm/background/terminated universal links and OAuth providers | Requires signed native builds, provider credentials, and the deployed domain files | Release certification | Must be completed in the final cross-app accessibility/E2E/release lane. |
