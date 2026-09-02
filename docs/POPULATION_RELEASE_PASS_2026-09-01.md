# Population and release verification — 2026-09-01

This is an evidence record, not authorization for a bulk run. All production
targets were exact-ID canaries; paid and unbounded scheduler jobs stayed off.

## Scheduler safety

The production `CRAVE-scheduler` service remained enabled with exactly:

- `moderation_queue_health_check`
- `share_parser`
- `image_processing_recovery`
- `video_processing`

The forbidden set was checked explicitly and was empty:
`menu_enrichment`, `image_ingestion`, `discovery`, `osm_ingest`,
`overture_ingest`, `score_recompute`, and `ranking_update`.

## Website-menu canary

Three active website-backed, menu-less places were selected by ID and passed
the tool's preview/drift checks:

- Itani Ramen (`a8ef634d-237d-5947-89b6-50c67bd245e9`)
- Pizzaiolo (`4719d690-86a5-55ce-add6-9fd7ebe2e9e4`)
- Cholita Linda (`399e4f7e-75e7-5eef-b472-96ff914f7e59`)

The exact run attempted three, reported one materialized menu and two
`no_menu` outcomes, with no thrown errors. The materialized Itani result was
not acceptable: 112 active rows represented only 57 distinct names, contained
unrelated-looking dishes/merchandise, and had no provider attribution. It was
immediately quarantined without deletion: all 112 items are inactive, the 112
claims and one truth row are renamed to explicit quarantine types, and the
place's prior menu/failure state was restored. Post-check: zero active canary
items and zero public menu truths.

**Conclusion:** do not enable recurring menu enrichment. Extraction needs a
pre-publication entity, deduplication, and provenance quality gate. Raw item
count is not coverage.

## Free-image canary

`backend/scripts/run_free_image_canary.py` adds a preview-first, exact-count,
maximum-10 canary that makes Google structurally unreachable and stages any
new row hidden/non-primary.

The exact two-place run targeted Cantina Frida and Las Ranas Cafe. Both had
zero existing image rows; both produced zero free candidates; zero rows were
staged and zero became public. A direct site diagnostic also reproduced an SSL
failure for Cantina Frida.

**Conclusion:** the safety shape is sound, but the current static website
extractor has insufficient recall for this sample. Add bounded `srcset`, lazy
image attributes, JSON-LD/social metadata, and an optional rendered-page path
before trying a larger free-only canary.

## Real video pipeline canary

A 4,331-byte, two-second synthetic H.264 MP4 was uploaded through the real R2
presigned-upload and confirm flow as video
`c22d6085-2ac9-4bd4-bc55-33048f062b2c`. It was forced to
`moderation_status=pending_review` before queueing, so it could never become
public.

The natural scheduler picked it up twice. Both attempts failed before ffmpeg
with `download_failed: maximum recursion depth exceeded`. An exact-object
one-shot download using the same production credentials succeeded, isolating
the problem to botocore's long-running worker streaming-body path rather than
the object or credentials.

The branch replaces that response-body stream with a five-minute presigned GET
streamed by `requests`, with a regression test. This code must deploy before
the quarantined canary is retried. The current evidence proves upload, object
existence, confirmation, scheduling, and queue pickup; it does **not** yet
prove ffmpeg, classifier, thumbnail/output upload, or locked-device push.

## Client and release verification

- Bundle ID/package: `com.crave.app`; version `1.0.0`; EAS production profile
  auto-increments the remote build number.
- Camera, microphone, photos, location, remote-notification, and background
  notification declarations are present.
- Expo's SDK 54 compatibility check found `react-native-worklets@0.7.1`
  unsupported and expected `0.5.1`; this branch pins the expected version and
  the check is now clean.
- TypeScript is clean. The frontend Jest suite passes. Playwright's live web
  journeys pass Feed → Place Detail and Search → Place Detail; the authenticated
  Save → Craves journey is honestly skipped because no seeded E2E credentials
  are configured.
- A native iPhone 17 Pro simulator build (`com.crave.app`, version 1.0.0/build
  1) launches and renders the live Feed once connected to Metro. It is a dev
  client, not signed-production evidence. The visible SDK-54
  `expo-notifications` persisted-state error remains and supports the planned
  controlled Expo upgrade.
- `npm audit --omit=dev` reports 34 transitive production-tree findings
  (21 moderate, 13 high, 0 critical); most proposed automatic resolutions are
  major Expo/router changes. Do not use `npm audit fix --force`; handle them as
  part of the controlled Expo upgrade and rerun the full native suite.

## Remaining release gates

1. Deploy and independently review the R2 download fix, then requeue only the
   quarantined synthetic video and verify every downstream stage.
2. Supply a seeded, disposable E2E account and run Save → Craves.
3. Produce a fresh EAS production/TestFlight build; the installed simulator
   dev client is not signing or archive evidence.
4. Perform the physical-device matrix, especially camera/video upload,
   background/locked push, permissions, and offline recovery.
5. Host public Privacy Policy and Terms URLs. Apple requires a Privacy Policy
   URL for every app and an accessible in-app link; the latter already exists:
   <https://developer.apple.com/help/app-store-connect/reference/app-privacy/>.
6. Perform the controlled Expo upgrade, clear the notification error, and
   reassess the transitive audit findings without forced major downgrades.
