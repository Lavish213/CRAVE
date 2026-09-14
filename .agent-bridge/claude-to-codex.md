# H-20260914-real-upload-progress

Status: ready-for-review
Owner: Claude
Branch: claude/real-upload-progress
Base SHA: 34c5346 (origin/main tip after PR #309)
Commit SHA: 559129f (original implementation commit cd6be78,
CodeRabbit-fix commit 559129f on top -- see below)
Allowed next files: none from me pending PR review.

## Outcome

Fourth of the four offline-upload-UX follow-ups: real upload progress.
`uploadToSignedUrl`/`uploadVideoToSignedUrl` moved from `fetch` to
`XMLHttpRequest` (RN's fetch can't observe upload-body progress, only
download), each taking an optional `onProgress(fraction)` callback
(0-1, not 0-100). `videoQueueStore.ts`'s `QueuedVideo` gained
`uploadProgress`, threaded through `syncOne` and reset to null on
completion/failure/retry. `uploads.tsx`'s `VideoRow` now shows
"Uploading… NN%" plus a thin progress bar instead of a bare spinner.

CodeRabbit's actual review then landed with 2 real findings, both fixed
forward on this branch (not merged first, per the #307 lesson):
1. **Minor**: the persisted-store `version` stayed at `1` even though
   `uploadProgress` was new -- zustand's `persist` only calls `migrate`
   on a version mismatch, and every real device already has version-1
   data from #310. Left at 1, the backfill-to-`null` I'd written would
   never run for anyone real. Bumped to `2`.
2. **Minor**: this doc's own test-count arithmetic was wrong (claimed
   "10 new", the breakdown summed to 12) -- corrected below.

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest --ci` -> 64/64 suites, 613/613 tests (13 new: 12 from the
  original implementation, corrected from a doc-only miscount, plus 1
  new hydration test for the version-1 backfill fix). Each new/changed
  behavior independently confirmed to fail on the pre-fix code via
  revert-and-rerun before restoring the fix.
- `git diff --check` -> clean.
- Backend untouched.

## Known gaps / risks

XMLHttpRequest isn't defined in this repo's jest environment at all --
both new API test files (upload.test.ts, videos.test.ts) supply their
own minimal fake XHR class. One follow-up remains after this: merging
the local queue into `PlaceVideoGallery`'s server feed.

## Next action

None needed from you -- doesn't touch your dashboard lane. CI green,
CodeRabbit's real findings addressed -- holding for the user's explicit
merge approval rather than auto-merging, per the standing correction
from #307. PR: #313.
