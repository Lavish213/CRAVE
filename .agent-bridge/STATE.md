# Active agent state

Status: ready-for-review
Owner: Claude
Branch: claude/phase5-video-media-transaction-integrity (PR to be opened
against main)
Base SHA: e7766c8 (main, post-Phase-4 squash merge -- PR #133)
Commit SHA: ecf16d5
Scope: Phase 5 of the canonical CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_
EXECUTION_SPEC.md -- Video/Media Transaction Integrity.
Locked files: none -- handoff complete.

## Outcome

Preflight audit read `record-video/[placeId].tsx`, `videoQueueStore.ts`,
`src/api/videos.ts`, the backend `videos.py` route, and
`video_upload_service.py`. The backend upload transaction was already
solid -- verified-healthy, left untouched:

- `request_video_upload_slot`/`confirm_video_upload` already enforce
  ownership (`uploaded_by`/caller mismatch -> 403), idempotency (a
  `client_id` retry reuses the existing row + a freshly-signed URL,
  with an `IntegrityError`-race fallback identical in shape to
  Phase 4's ranking idempotency), a `status != PENDING` no-op guard
  against re-queuing an already-processed video, and post-upload size
  enforcement via `head_object` (a presigned PUT has no built-in cap).
  `get_video_status` also checks ownership. All of this is already
  covered by `test_video_upload_service.py` (12 tests: unsupported
  content-type, unknown place/template, client_id dedupe + cross-user
  forbidden, confirm ownership, no-op re-confirm, missing-upload,
  oversized-upload).

Found and fixed three confirmed bugs, all frontend:

- **P0 -- record first, discard silently after (confirmed, matches
  the spec's exact "forbidden historical pattern")**:
  `record-video/[placeId].tsx`'s `startRecording` called
  `cameraRef.recordAsync(...)` -- a real, full video recording -- and
  only checked `if (!placeId || !user?.id) return;` *after* it
  completed, silently discarding a finished recording with zero
  feedback if either was missing. Fixed with a precondition check
  before the camera ever activates (toast + no-op if invalid), a
  render-level guard before the camera UI even mounts (this screen's
  one known entry point, `PlaceVideoGallery`, already gated on
  sign-in before navigating here, but that guard lived in the caller,
  not this route -- a deep link or any future entry point had zero
  defense-in-depth), and a truthful toast (not a silent return) for the
  narrow remaining race of signing out during the recording itself.
- **Permanently-blocked permission had no Settings recovery** --
  the permission-denied screen always showed "Allow Access" regardless
  of `canAskAgain`; once the OS permanently denies (or ignores a
  repeat request), that button silently no-ops forever. Now checks
  `canAskAgain` and routes to `Linking.openSettings()` instead,
  matching this app's own existing convention (`settings.tsx`'s
  identical handling for notification permissions).
- **Missing local file silently deleted the queue row** --
  `videoQueueStore.ts`'s `syncOne` dropped a video's row entirely (no
  user-facing signal at all) when its local file no longer existed
  (OS storage cleared, etc.). Added a real `missing_local_file`
  terminal `VideoSyncState` instead of erasing the row. Also excluded
  both `failed` and the new `missing_local_file` from
  `MAX_QUEUED_VIDEOS`'s active-queue count (neither will ever change
  state again without an explicit delete, so counting them toward the
  cap could otherwise permanently block new recordings once enough
  accumulated) and let `deleteFailedVideo` clear either terminal state.

## Verification

- Frontend: `npx tsc --noEmit` clean. `npx jest` 375/375 passed, 37
  suites (370 baseline + 5 new: 2 in `record-video.test.tsx`, 3 in
  `videoQueueStore.test.ts`).
- Backend: `python3 -m pytest -q` 1041 passed, 2 skipped -- unchanged
  from Phase 4's baseline; no backend files touched.

## Known gaps / risks

- **Real iOS/Android device testing was NOT performed** -- this
  session runs in a Linux container with no simulator/device access.
  The spec's Phase 5 gate explicitly requires real-device camera/mic/
  permission verification ("Camera/video/location cannot be
  simulator-only"); that requirement is unmet here and should be
  treated as an open item before any release-readiness claim, not
  silently assumed satisfied.
- **No user-facing surface exists for the video queue at all** --
  `retryFailedVideo`/`deleteFailedVideo` exist in the store but are
  never called from any screen (verified: grepped every consumer).
  A permanently-failed or missing-file video is now at least correctly
  *tracked* (not silently erased) and no longer blocks new recordings,
  but a user still has no in-app way to see or act on it. This is a
  real product gap, not a code-level bug this phase's scope covers --
  building that surface would be a new screen/feature, not a
  transaction-integrity fix, so it's flagged here rather than built
  speculatively.
- Malformed-row recovery (a persisted `QueuedVideo` row missing a field
  after a future schema change) was not defensively hardened -- no
  concrete failure scenario exists yet against this codebase's stable,
  unchanged `QueuedVideo` shape; flagged as a documented gap rather
  than speculative code with nothing to verify it against.
- Phases 6-7 (telemetry/location/async truth, performance/
  accessibility/security/release certification) are untouched -- per
  the spec's strict ordering, each is its own later phase on its own
  fresh branch.

## Next action

Push this branch, open a narrow PR against main following the spec's
required PR contract, request CodeRabbit review, hold to the same
three gates Phases 1-4 used (CI green, review threads resolved, no
scope creep) before merge -- explicitly NOT claiming the real-device
gate as satisfied. After merge, Phase 6 (Telemetry, Location & Async
Truth) is next per the spec's strict ordering -- not yet claimed, needs
its own fresh preflight audit against whatever `main` looks like at
that point.
