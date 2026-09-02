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

The first exact run, on the branch's old base, materialized an unacceptable
Itani result: 112 active rows represented only 57 distinct names, contained
unrelated-looking dishes/merchandise, and had no provider attribution. It was
immediately quarantined without deletion: all 112 items are inactive, the 112
claims and one truth row are renamed to explicit quarantine types, and the
place's prior menu/failure state was restored.

After rebasing onto `bf0b08c` (including PRs #117/#118), the same exact three
targets were previewed and rerun with `--confirm-count 3`. Result: attempted=3,
materialized=0, no_menu=3, errors=0. Critically, the Itani extraction now
logged `menu_pipeline_rejected reason=low_quality`; none of the prior
contamination was republished. Pizzaiolo still hit a CAPTCHA, and no target
gained a menu.

**Conclusion:** the new gates prevent the confirmed contamination shape, but
they do not increase menu recall on this sample. Recurring menu enrichment
remains disabled; a larger run would create load without evidence of coverage
gain.

## Free-image canary

`backend/scripts/run_free_image_canary.py` adds a preview-first, exact-count,
maximum-10 canary that makes Google structurally unreachable and stages any
new row hidden/non-primary.

The exact two-place run targeted Cantina Frida and the Los Angeles Las Ranas
Cafe row. Both had zero existing image rows; both produced zero free
candidates; zero rows were staged and zero became public.

After rebasing onto `bf0b08c`, the first retry incorrectly returned zero again:
the original canary had written a 24-hour website-fetch cache row, so the retry
never exercised PR #117's new browser path. A regression test now proves the
exact canary bypasses only this cache while ordinary ingestion caching stays
unchanged.

The corrected exact retry (`--confirm-count 2`) produced attempted=2, staged=1,
publicly_visible=0. Cantina Frida yielded one official-site image, stored
hidden/non-primary as `df414329-b95e-4899-a061-6af6f751d038`. Las Ranas still
yielded zero. Direct diagnostics explain both results: Cantina's official site
says it is temporarily closed and reopening; Las Ranas currently serves a
114-byte JavaScript redirect to `/lander`, whose rendered response contains no
restaurant images. A search crawler's restaurant content was cached from the
prior week, so that indexed page is not current extraction evidence.

**Conclusion:** free website acquisition now has a real 1/2 recall signal, but
the only staged result belongs to a temporarily closed venue and must stay
hidden pending review. Las Ranas is a catalog/website-freshness problem, not
evidence that the browser renderer failed. Recurring image ingestion remains
disabled.

## Post-canary production audit

- All three menu targets remain `has_menu=false`; active menu items across the
  exact set=0. Failure counts advanced once, as expected for the bounded run.
- Exact image-target row count=1: the Cantina row above, hidden/non-primary.
- Scheduler worker remains enabled with exactly
  `moderation_queue_health_check,share_parser,image_processing_recovery,video_processing`.
- Latest recorded runs for all four jobs are successful; paid/unbounded jobs
  remain outside the allowlist.

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
streamed by `requests`, with a regression test. After rebasing over PRs
#121/#122, the local-file-backed R2 boundary was updated to exercise the same
signed-HTTP path; the real upload-to-worker tests now pass through ffmpeg and
the classifier for both food and non-food videos. This fix still requires
independent review and deployment before the quarantined production object is
retried. Locked-device push remains unproven.

## Client and release verification

- Bundle ID/package: `com.crave.app`; version `1.0.0`; EAS production profile
  auto-increments the remote build number.
- Camera, microphone, photos, location, remote-notification, and background
  notification declarations are present.
- The old branch's proposed `react-native-worklets` downgrade was dropped
  during rebase. Current `main` remains authoritative at `0.7.1`; native-module
  upgrades are tracked separately and require device validation.
- Prior TypeScript/Jest/Playwright results are historical evidence only; this
  post-rebase pass touched no frontend files and did not relabel them as fresh.
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
6. Improve free-source recall with evidence on new exact targets before any
   recurring menu/image acquisition job is enabled.
