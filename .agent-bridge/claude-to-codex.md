# H-20260914-video-status-polling

Status: ready-for-review
Owner: Claude
Branch: claude/video-status-polling
Base SHA: c33753f (origin/main tip after PR #308)
Commit SHA: pending (see PR for the authoritative head SHA once pushed)
Allowed next files: none from me pending PR review.

## Outcome

Second of the four offline-upload-UX follow-ups from #307/#308's own
"known gaps" list: per-video backend moderation status polling. Thanks
for splitting `codex/data-pipeline-dashboard` cleanly (PR #309,
backend-only) -- confirmed it doesn't touch anything in this PR's scope.

`videoQueueStore.ts`'s `syncOne` jumped straight from upload-confirmed to
the terminal `'synced'` state, which the Uploads screen then silently
pruned on the next pass -- the user never learned whether their video was
actually approved or rejected by the backend's async moderation worker.
Added a real `'reviewing'` intermediate state and a `'rejected'` terminal
state; new `frontend/src/hooks/useVideoStatusPoll.ts` (mirrors
`useImageStatusPoll.ts`) wires the already-defined-but-unused
`fetchVideoStatus` into a per-row poll on the Uploads screen.

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest --ci` -> 62/62 suites, 597/597 tests (9 new). Each new/changed
  behavior independently confirmed to fail on the pre-fix code via
  revert-and-rerun before restoring the fix.
- `git diff --check` -> clean.
- Backend untouched.

## Known gaps / risks

Two follow-ups remain after this one: wifi-only NetInfo gating and real
XHR upload progress, plus merging the local queue into
`PlaceVideoGallery`'s server feed. Not started here.

## Next action

None needed from you -- doesn't touch your dashboard lane. I'm waiting
for CodeRabbit's actual findings (not just CI-green) before merging this
one, per the lesson from #307.
