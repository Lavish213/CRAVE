# H-20260906-phase5-video-media-transaction-integrity

Status: ready-for-review
Owner: Claude
Branch: claude/phase5-video-media-transaction-integrity (PR to be
opened against main)
Base SHA: e7766c8 (main, post-Phase-4 squash merge -- PR #133)
Commit SHA: ecf16d5
Allowed next files: none from me -- this branch is in review, no more
code planned here unless CI/review findings require it.

## Outcome

Phase 5 of the canonical `CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_
EXECUTION_SPEC.md` (Video/Media Transaction Integrity), following
Phase 4 (Ranking Transaction Integrity, #133, merged).

Preflight audit read `record-video/[placeId].tsx`, `videoQueueStore.ts`,
the backend `videos.py` route and `video_upload_service.py`. The
backend upload transaction was already solid -- verified-healthy, left
untouched: ownership checks, `client_id` idempotency (with an
`IntegrityError`-race fallback identical in shape to Phase 4's ranking
idempotency), a status-guarded no-op against re-confirming an
already-processed video, and post-upload size enforcement. All already
covered by `test_video_upload_service.py` (12 tests).

Found and fixed three confirmed bugs, all frontend:

1. **Record first, discard silently after (P0)** -- matches the
   spec's exact "forbidden historical pattern": `startRecording`
   called the camera's `recordAsync()` -- a real recording -- and only
   checked `placeId`/`user` *after* it finished, silently discarding a
   completed video with zero feedback if either was missing. Added a
   precondition check before capture activation, a render-level guard
   before the camera even mounts (defense-in-depth beyond the one
   known caller's own sign-in gate), and a truthful toast for the
   narrow sign-out-mid-recording race.
2. **Permanently-blocked permission had no Settings recovery** -- the
   permission prompt always showed "Allow Access" even when
   `canAskAgain` was false (OS won't re-prompt), silently no-op'ing.
   Now routes to `Linking.openSettings()`, matching this app's own
   existing convention.
3. **Missing local file silently deleted the queue row** -- a video
   whose local file no longer existed just vanished from the queue
   with no signal. Added a real `missing_local_file` terminal state;
   both it and `failed` are now excluded from the active-queue cap so
   neither can permanently block new recordings.

## Verification

- Frontend: `npx tsc --noEmit` -> clean. `npx jest` -> 375/375 passed,
  37 suites (370 baseline + 5 new).
- Backend: `python3 -m pytest -q` -> 1041 passed, 2 skipped --
  unchanged from Phase 4's baseline; no backend files touched.

## Known gaps / risks

- **Real iOS/Android device testing was not performed** -- this
  session has no simulator/device access. The spec's Phase 5 gate
  explicitly requires it; not claimed as satisfied.
- No user-facing surface exists for the video queue at all
  (`retryFailedVideo`/`deleteFailedVideo` are dead code, called from no
  screen) -- a real product gap, but building one is a new feature, not
  a transaction-integrity fix, so it's documented rather than built
  speculatively in this phase.
- Phases 6-7 (telemetry/location/async truth, release certification)
  are untouched -- each is its own later phase on its own fresh branch.

## Next action

Codex: this branch touches only `frontend/app/record-video/[placeId].tsx`,
`frontend/src/stores/videoQueueStore.ts`, and their test files -- no
backend changes. Once this merges, Phase 6 (Telemetry, Location &
Async Truth) is next per the spec, not yet claimed -- needs its own
fresh preflight audit against whatever `main` looks like at that
point, not assumed from this note.
