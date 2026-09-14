# H-20260914-video-feed-local-placeholders

Status: ready-for-review
Owner: Claude
Branch: claude/video-feed-local-placeholders
Base SHA: 34c5346 (origin/main tip after PR #309)
Commit SHA: c1807ff (original implementation commit 1547159,
CodeRabbit-fix commit c1807ff on top -- see below)
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

CodeRabbit's actual review then landed with 1 real finding, fixed
forward on this branch (not merged first, per the #307 lesson):
- **Major**: the initial-mount fetch and the placeholder-loss refetch
  both applied their result unconditionally, with no ordering guarantee
  -- an older request resolving after a newer one could overwrite it
  with stale data. Unified both under one `refetchFeed()` using a
  monotonically increasing request id so only the most recent request's
  response is ever applied.

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest --ci` -> 63/63 suites, 609/609 tests (9 new total: 8 from
  the original implementation, 1 more from the CodeRabbit fix). Each
  new/changed behavior independently confirmed to fail on the pre-fix
  code via revert-and-rerun before restoring the fix.
- `git diff --check` -> clean.
- Backend untouched.

## Known gaps / risks

This was the last item on the offline-upload-UX follow-up roadmap. No
further follow-ups tracked from that list.

## Next action

None needed from you -- doesn't touch your dashboard lane. CI green,
CodeRabbit's real finding addressed -- holding for the user's explicit
merge approval rather than auto-merging, per the standing correction
from #307. PR: #314.
