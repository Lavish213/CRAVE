# Push notification production configuration runbook

Permanent runbook. Confirms a production-signed build can actually
receive a push notification end-to-end, and flags one real open
question about the backend's push implementation that should be
decided before certifying this item.

## Why this exists

`backend/app/services/notifications/expo_push.py` sends push via a
single plain `POST https://exp.host/--/api/v2/push/send` (no
`exponent-server-sdk` dependency, by design) with no `Authorization`
header — i.e. it does **not** use Expo's optional "Enhanced Push
Notification Security" access token. `send_push_to_user` looks up every
`DevicePushToken` row for a user and calls `send_push_to_tokens`, which
is entirely best-effort: failures are logged and swallowed, never
raised (per the file's own docstring — a failed push must never affect
the caller's own outcome, e.g. an approve/reject action in
`video_processing_worker.py`).

This means "push doesn't arrive" produces no application-level error
anywhere — the only way to know it's broken is to actually receive (or
fail to receive) a real push on a real device.

## Prerequisites

- A physical iOS device and a physical Android device, each with the
  app installed from a real (or EAS preview, at minimum) build.
- Access to Expo's push credential configuration for this project
  (`eas credentials`), Apple Developer (APNs key/cert), and Firebase
  (FCM, for Android) if not already configured through EAS.

## Proof 1 — platform push credentials are registered with Expo

- `eas credentials` (or the EAS dashboard) → confirm an APNs key/cert
  is registered for iOS, and FCM server credentials are registered for
  Android, for the **production** build profile specifically (a
  credential registered only for `development`/`preview` won't carry
  over to `production` automatically).

**Pass:** both platforms show valid, non-expired push credentials
against the production profile.
**Fail:** generate/upload the missing credential via `eas credentials`;
an expired APNs key is a common silent-failure cause — check the
expiration date, not just presence.

## Proof 2 — a device actually registers a push token

- Install a real (production-signed, or EAS-preview-with-production-
  push-config) build, sign in, and grant notification permission.
- Confirm a row appears in the backend's `device_push_token` table for
  that user/device (via `GET /api/v1/debug/...` if a suitable
  read-only debug view exists, or direct DB access) — this confirms
  the token round-trip (device → app → backend →
  `DevicePushToken` row) works before testing delivery.

**Pass:** a token row appears, associated with the signed-in user.
**Fail:** if no row appears, the gap is in the app's own
registration-to-backend call, not Expo/Apple/Google — check that path
before assuming a credentials problem.

## Proof 3 — a real push is sent and received

- Trigger whatever server-side event actually calls `send_push_to_user`
  (per the file's own comment, currently only
  `video_processing_worker.py`'s approve/reject paths) against your own
  test account/device, on both iOS and Android.
- Confirm the notification actually arrives and, on tap, opens the app
  to a reasonable destination.

**Pass:** both devices receive the notification.
**Fail — one platform doesn't receive it:** re-check that platform's
credential (Proof 1) specifically — iOS/Android push failures are
almost always independent of each other. **Fail — neither receives
it:** check Expo's push receipt data (the `receipts` this code already
logs a warning for on non-`"ok"` status — check Railway logs for
`expo_push_delivery_error`) for the actual rejection reason Expo
reports.

## Open question to resolve before marking this PASS

This implementation deliberately skips Expo's optional Enhanced Push
Notification Security access token. That's a legitimate choice (it's
optional, and adds operational complexity), but it should be a
**decision**, not an oversight — confirm whether this app's threat
model requires it (it primarily matters if there's reason to think
someone else could send pushes as this Expo project) before treating
this item as fully certified.

## After running this

Record the result: append a dated Result section to this file, and
update `docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md`'s Section 4.4
status.
