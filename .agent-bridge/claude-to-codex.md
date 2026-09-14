# H-20260914-real-upload-progress

Status: ready-for-review
Owner: Claude
Branch: claude/real-upload-progress
Base SHA: 34c5346 (origin/main tip after PR #309)
Commit SHA: cd6be78
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

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest --ci` -> 64/64 suites, 612/612 tests (10 new). Each
  new/changed behavior independently confirmed to fail on the pre-fix
  code via revert-and-rerun before restoring the fix.
- `git diff --check` -> clean.
- Backend untouched.

## Known gaps / risks

XMLHttpRequest isn't defined in this repo's jest environment at all --
both new API test files (upload.test.ts, videos.test.ts) supply their
own minimal fake XHR class. One follow-up remains after this: merging
the local queue into `PlaceVideoGallery`'s server feed.

## Next action

None needed from you -- doesn't touch your dashboard lane. Waiting for
CodeRabbit's actual findings (not just CI-green) before merging, per
the standing correction from #307. PR: #313.
