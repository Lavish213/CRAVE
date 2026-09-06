# Provider / data-flow inventory

Maps every external processor CRAVE's production deployment sends
data to, and exactly what data. This is the source document for
Apple's Privacy Nutrition Labels, Google Play's Data Safety
declarations, and the hosted Privacy Policy — all three should be
derived from this table, not drafted independently, so they can't
drift apart from each other or from what the app actually does.

Format: provider — what CRAVE sends it — why — retained by provider? —
user-linkable?

## Supabase

- **Sends**: email/OAuth identity (Google/Apple sign-in), auth tokens.
- **Why**: authentication — Supabase issues and verifies the signed-in
  user's identity token; the backend never sees a password.
- **Retained by provider**: yes, for the lifetime of the account (auth
  provider's own account record).
- **User-linkable**: yes, directly (it *is* the identity).
- **Deletion**: Phase 7's account deletion removes the Supabase auth
  identity itself (via `SUPABASE_SERVICE_ROLE_KEY`, see
  `account_deletion_service.py`), not just app-side data.

## Railway (application backend + Postgres)

- **Sends/stores**: everything the app's own data model holds —
  profile info, rankings, saves, Craves, reports, recommendation
  events (impressions/clicks/saves with `place_id`/`city_id`/session
  context — see `RecommendationEvent`), device push tokens, and
  metadata about uploaded media (not the media bytes themselves — see
  Cloudflare R2 below).
- **Why**: this is CRAVE's own first-party backend — not a third-party
  processor in the privacy-label sense, but still worth documenting
  here since it's the aggregation point for everything else.
- **Retained by provider**: for the lifetime of the account/business
  need; Phase 7 defines what account deletion removes.
- **User-linkable**: yes, directly.

## Cloudflare R2

- **Sends**: user-uploaded photo and video files (the actual media
  bytes).
- **Why**: object storage for place photos/videos.
- **Retained by provider**: until deleted — account deletion removes
  user-uploaded objects (Phase 7); individual photo/video deletion
  removes the specific object.
- **User-linkable**: indirectly — object keys are backend-generated,
  not directly identity-bearing, but the backend's own DB links a key
  to a user.

## Google Maps / Places

- **Sends**: for Places ingestion (backend, `google_places_api_key`) —
  search queries built from place names/locations CRAVE is cataloging,
  not end-user personal data. For Maps rendering (client, Android
  only) — the map viewport/location shown to render tiles; whether
  this includes the *user's own* device location depends on whether
  location permission was granted (see `useLocation`/`add-spot.tsx`'s
  location flows) — if granted, approximate device location is sent to
  Google to center the map and (via the backend) to bias nearby-search
  results.
- **Why**: map rendering, place discovery/ingestion.
- **Retained by provider**: per Google's own API terms, not something
  this app controls.
- **User-linkable**: the Places-ingestion calls are not user-linkable
  (they're catalog-building, not per-user). The Maps-rendering calls
  can carry the user's approximate location, tied to that device/
  session, if location permission was granted.

## Expo (EAS push notification service)

- **Sends**: device push tokens (`DevicePushToken` rows) and
  notification title/body/data payloads (see
  `app/services/notifications/expo_push.py`) — currently only
  triggered by `video_processing_worker.py`'s approve/reject outcomes.
- **Why**: push notification delivery.
- **Retained by provider**: Expo's own push-receipt retention policy,
  not controlled by this app.
- **User-linkable**: yes, via the device push token, which is tied to
  a specific user in `DevicePushToken`.

## Sentry (conditional — only if `SENTRY_DSN` is set)

- **Sends**: backend exception/error data — stack traces, the request
  path, and whatever context `sentry_sdk`'s default integrations
  attach. `send_default_pii=False` is set explicitly, which
  substantially reduces (but per
  `docs/SENTRY_PRODUCTION_VERIFICATION.md`'s own wording, does not
  *guarantee*) that user-identifying data is excluded — a value logged
  or passed to `capture_exception` explicitly would still be captured.
- **Why**: backend crash/error observability.
- **Retained by provider**: per Sentry's own project data-retention
  settings.
- **User-linkable**: not by design (`send_default_pii=False`), but see
  the caveat above — this is exactly why
  `docs/SENTRY_PRODUCTION_VERIFICATION.md`'s Proof 3 requires live-event
  inspection rather than trusting the config flag alone.
- **Client/native**: confirmed absent — no `@sentry/react-native`, no
  Expo Sentry config plugin, no client-side `Sentry.init`/
  `captureException` anywhere in `frontend/`. This is a genuine open
  product decision (does CRAVE want client-side crash reporting before
  release?), not a regression — see matrix Section 2 for the tracked
  decision point.

## Apple / Google (platform-level, not CRAVE-controlled)

- Sign-in with Apple / Google OAuth flows themselves are handled by
  Supabase server-side; CRAVE's own client code doesn't talk to
  Apple's/Google's auth endpoints directly.
- App Store Connect / Play Console receive whatever standard
  diagnostic data Apple/Google collect themselves as platform
  operators (crash reports the OS itself offers to send, install/
  update telemetry) — outside this app's control and outside this
  inventory's scope (it's platform-level, not something CRAVE sends).

## How to use this for privacy declarations

- **Apple Privacy Nutrition Labels**: each provider's "Sends" column
  maps to a data-category checkbox (e.g. Supabase → "Identifiers" /
  "Contact Info"; R2 → "User Content" (photos/videos); Google Maps →
  "Location" if permission is granted; Expo → "Identifiers" (device
  token)).
- **Google Play Data Safety**: same mapping, using Google's own
  category taxonomy — this table's "user-linkable" column maps
  directly to Google's "linked to you" vs. "not linked" distinction.
- **Hosted Privacy Policy**: should name these exact providers by name
  (the in-app policy, `frontend/app/legal/privacy.tsx`, already does
  this per Phase 7 — the hosted version must say the same thing, see
  matrix Section 3.3's parity check).

## Maintenance

Add a new entry here the moment a new third-party service starts
receiving any data from CRAVE — before drafting any store privacy
declaration, re-confirm this table is current against actual runtime
behavior, not assumed from memory.
