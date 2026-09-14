# H-20260914-video-status-polling

Status: ready-for-review
Owner: Claude
Branch: claude/video-status-polling
Base SHA: c33753f (origin/main tip after PR #308)
Commit SHA: 297a901 (original implementation commit; CodeRabbit-fix
commits landed on top since -- see PR #310 for the current head SHA)
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

CodeRabbit's actual review then landed with 3 real findings, all fixed
forward on this branch (not merged first, per the #307 lesson):
1. **Major**: a device holding a legacy persisted `'synced'` row from
   before this version shipped would have it silently pruned as
   "approved" on the next sync pass under the new code. Fixed with a
   zustand `persist` version bump + migrate step: any persisted `'synced'`
   row with a `serverId` becomes `'reviewing'` on rehydration.
2. **Minor**: `useVideoStatusPoll` retried a persistently-failing
   `fetchVideoStatus` forever with nothing surfaced. Added a `pollError`
   state, surfaced in the Uploads row, cleared on the next success.
3. **Minor**: this file's `Commit SHA` field was left `pending` --
   corrected above.

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest --ci` -> 62/62 suites (final count includes 3 more new tests
  from the CodeRabbit fixes: the migration test, and two poll-error
  tests). Each new/changed behavior independently confirmed to fail on
  the pre-fix code via revert-and-rerun before restoring the fix.
- `git diff --check` -> clean.
- Backend untouched.

## Known gaps / risks

Two follow-ups remain after this one: wifi-only NetInfo gating and real
XHR upload progress, plus merging the local queue into
`PlaceVideoGallery`'s server feed. Not started here.

## Next action

None needed from you -- doesn't touch your dashboard lane. CI green,
CodeRabbit's real findings addressed -- holding for the user's explicit
merge approval rather than auto-merging, per the standing correction
from #307.
