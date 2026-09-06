# EAS signing + production build runbook

Permanent runbook. Produces the actual signed release candidate this
whole certification matrix is building toward — everything before this
point is preparation; this is where a real installable binary exists.

## Prerequisites

- Apple Developer Program membership (for iOS signing).
- Google Play Console developer account (for Android signing/upload).
- `eas-cli` authenticated against this project (`eas whoami`).
- `docs/PRODUCTION_ENVIRONMENT_MANIFEST.md`'s frontend section fully
  resolved — a build with wrong `EXPO_PUBLIC_*` values is a build that
  has to be thrown away and redone, not something to catch after.

## Step 1 — confirm the production profile and identity

- `frontend/eas.json`'s `production` profile: `autoIncrement: true`,
  `channel: "production"` (already confirmed present, matrix 5.2 —
  this step re-confirms it hasn't drifted since).
- `frontend/app.json`: `ios.bundleIdentifier` and `android.package`
  both `com.crave.app` (already confirmed, matrix 5.1) — cross-check
  against the actual App Store Connect / Play Console app records to
  confirm these match what's registered there, not just each other.

**Pass:** profile and identifiers match both the repo and the store
consoles.
**Fail:** a bundle ID / package name mismatch between repo and console
means the build will be rejected at upload — fix before building, not
after.

## Step 2 — signing credentials

```bash
eas credentials
```

- iOS: confirm a valid (non-expired) distribution certificate and a
  provisioning profile matching `com.crave.app`, for the `production`
  build profile specifically.
- Android: confirm a production upload keystore exists (not a
  debug/EAS-managed dev keystore) and its SHA-1 is the one registered
  with the Android Maps API key restriction (see
  `RUNBOOK_GOOGLE_MAPS_PLACES_PRODUCTION.md`, Proof 1).

**Pass:** both platforms show valid production-scoped credentials.
**Fail:** generate/renew via `eas credentials`; if the Android keystore
changes, the Maps key restriction (a separate Google Cloud Console
step) must be updated to the new SHA-1 or the map will render blank
gray on the new build.

## Step 3 — build

```bash
eas build --profile production --platform ios
eas build --profile production --platform android
```

- Confirm the build picks up the intended `EXPO_PUBLIC_*` values (EAS
  environment variables scoped to the `production` profile/environment,
  not `preview`/`development`) — a build succeeding with the *wrong*
  environment variables is a worse failure mode than the build failing
  outright, since it looks fine until a device tries to actually talk
  to the wrong backend.
- Record the resulting EAS build ID for both platforms (needed for the
  release-candidate identity record — matrix Section 5.5).

**Pass:** both builds succeed and produce an installable artifact
(`.ipa`/`.aab`).
**Fail:** diagnose from EAS's own build logs first — most production
build failures are credential or environment-variable-scope issues
(Steps 1-2), not genuine native-code bugs; treat a real native-module
build failure as bucket 4 (a narrow bugfix PR), not grounds for
adjusting build config on faith.

## Step 4 — install and smoke-check before full certification

Before running the full device/accessibility/smoke-test runbooks:

- Install the actual built artifact (not a dev/Expo Go build) on one
  real device per platform.
- Confirm `EXPO_PUBLIC_API_URL` actually points at production (the
  app should successfully load real data, not fail every request).
- Confirm the app version/build number shown in Settings (Phase 7's
  fix — native application/build version, not a hardcoded string)
  matches what was just built.

**Pass:** the installed build is confirmed to be this exact production
build, talking to the real production backend.
**Fail:** if it's still hitting a dev/staging backend, re-check EAS's
environment-variable scoping (Step 3) before rebuilding.

## After running this

Record the result — this is also where the release-candidate identity
record (matrix Section 5.5) gets its `EAS build IDs`, `iOS version/
build`, and `Android version/build` fields filled in. Update
`docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md` Sections 5.3/5.4.
