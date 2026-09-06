# Google Maps / Places production keys runbook

Permanent runbook. Confirms the two separate Google API keys this app
uses (`GOOGLE_MAPS_ANDROID_API_KEY`, client-side; `google_places_api_key`
/`GOOGLE_PLACES_API_KEY`, backend-side) are correctly restricted and
scoped for production — these are two different keys with different
threat models and must not be confused with each other.

## Why this exists

`frontend/app.config.js` reads `GOOGLE_MAPS_ANDROID_API_KEY` from
`process.env` at EAS build time (not hardcoded — confirmed in the
credential-leakage audit) and injects it into
`android.config.googleMaps.apiKey`. Because this key **ships inside
the compiled Android binary**, anyone who extracts the APK has it —
API-key allowlisting on Google's side is not enough by itself; the
key must be restricted to this app's package name + release signing
SHA-1 fingerprint (per the file's own comment).

`backend/app/config/settings.py`'s `google_places_api_key` is a
separate, backend-only key (never shipped to any client) used for
Places ingestion, with its own safety cap
(`google_places_max_calls_per_run`, default 2000) to stop a runaway
loop from silently running up billing.

## Prerequisites

- Access to Google Cloud Console for the project holding both keys.
- The production Android release signing certificate's SHA-1
  fingerprint (from EAS credentials or the keystore directly).

## Proof 1 — the Android Maps key is restricted correctly

- Google Cloud Console → APIs & Services → Credentials → the Android
  Maps key.
- Confirm "Application restrictions" is set to Android apps, with
  exactly `com.crave.app` + the **production** release signing SHA-1
  (not a debug/dev-client SHA-1 — a key restricted to the wrong SHA-1
  will work in dev builds and silently fail only in the real signed
  release, the worst possible time to discover it).
- Confirm "API restrictions" limits this key to the Maps SDK for
  Android (not left unrestricted).

**Pass:** restricted to the exact production package + SHA-1, and to
only the Maps SDK.
**Fail:** if restricted to the wrong/dev SHA-1, the map will render
correctly in every test build and then fail only in the store-signed
release — regenerate/adjust the restriction with the real production
SHA-1 (`eas credentials` can print it) before submission, not after a
rejected/broken store build is discovered.

## Proof 2 — the backend Places key is scoped and capped correctly

- Google Cloud Console → the Places key (separate from the Android
  Maps key above) → confirm "Application restrictions" is set to IP
  addresses (Railway's, if static/known) or left as a server key with
  no client-side restriction possible — confirm it is **not** the same
  key as the Android Maps key.
- Confirm this project's Places API billing/quota alert is set at or
  below what `google_places_max_calls_per_run` (2000/run) implies is
  the app's expected worst-case usage, so an unexpected spike pages
  someone instead of silently accumulating billing.

**Pass:** a distinct, appropriately-scoped server key with a sane
billing alert.
**Fail:** if the same key is used for both Maps (client) and Places
(server), split them — a client-extracted key with unrestricted server
API access is a real abuse vector.

## Proof 3 — the map actually renders on a production Android build

Using a real (or EAS preview, if it shares the production key) Android
build: open the Map tab and confirm markers/tiles render, not a blank
gray box (the app's own documented failure mode when this key is
missing/misconfigured, per `app.config.js`'s comment).

**Pass:** map renders with real tiles and markers.
**Fail:** if it's a blank gray box specifically, this is almost always
Proof 1's restriction being wrong for this exact build's signing
certificate — re-check the SHA-1 used for the build against what's
registered.

## After running this

Record the result: append a dated Result section to this file, and
update `docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md`'s Section 4.5
status.
