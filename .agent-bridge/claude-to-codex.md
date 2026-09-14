# H-20260914-video-feed-local-placeholders

Status: ready-for-review
Owner: Claude
Branch: claude/video-feed-local-placeholders
Base SHA: 34c5346 (origin/main tip after PR #309)
Commit SHA: 1547159
Allowed next files: none from me pending PR review.

## Outcome

Last of the four offline-upload-UX follow-ups: merging the local queue
into `PlaceVideoGallery`'s server feed. The gallery only rendered
`fetchVideoFeed`'s backend-approved videos -- a just-recorded/queued/
uploading/under-review video was invisible on the place's own page
until approved. `PlaceVideoGallery` now reads `useVideoQueueStore`
directly and shows the current user's own in-progress videos for this
place as placeholder tiles ahead of the server feed. Terminal states
(failed/rejected/missing_local_file) excluded -- tapping a placeholder
opens the Uploads screen for those controls instead. A new effect
refetches the server feed once a placeholder disappears (approved and
pruned, or dismissed).

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest --ci` -> 63/63 suites, 608/608 tests (8 new, first dedicated
  coverage for this component). Each new behavior independently
  confirmed to fail on the pre-fix code via revert-and-rerun before
  restoring the fix.
- `git diff --check` -> clean.
- Backend untouched.

## Known gaps / risks

This was the last item on the offline-upload-UX follow-up roadmap. No
further follow-ups tracked from that list.

## Next action

None needed from you -- doesn't touch your dashboard lane. Waiting for
CodeRabbit's actual findings (not just CI-green) before merging, per
the standing correction from #307. PR: #314.
