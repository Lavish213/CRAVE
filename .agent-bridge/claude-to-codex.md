# H-20260901-image-recovery-synthetic-test-request

Status: ready-for-execution
Owner: Claude
Branch: main
Base SHA: da74a7c (PR #114 merged)
Allowed next files: none from me -- this is a test request, not a code
change. Whatever you do to execute it is your normal docs-only bridge
handoff afterward.

## Why

`image_processing_recovery` has run twice in production (one bounded
canary, part of the natural schedule) and both times found zero stale
rows, so `reclaimed=0` both times. That proves the job executes and
queries cleanly -- it proves nothing about `reclaim_stale_image_uploads()`
or `process_image_upload()` actually doing their job on a genuinely stuck
row. Same class of gap as the video canary's "empty batch" finding, just
for the image path. Per the user, this is the next synthetic test to run
now, same discipline as your video test: real code path, synthetic/
inert data, non-public blast radius, fully reversible.

## What I read (backend/app/workers/image_processing_worker.py:319-375,
backend/app/scheduler.py:280-303)

`reclaim_stale_image_uploads(limit=50)` selects `PlaceImage` rows with
`status IN ('pending','processing')` and `created_at < now -
photo_stale_processing_minutes` (30 min, `settings.py:193`), then calls
`process_image_upload(image_id)` on each. That function re-fetches the
row, sets `status='processing'`, does `s3.get_object(Bucket=R2_BUCKET,
Key=image.orig_key)`, and on *any* exception (including a missing R2
key) falls through to its outer `except` and sets `status='failed'`
(`image_processing_worker.py:300-312`). On success it sets
`status='ready'` and computes `is_primary`/`visibility_status` relative
to any existing primary image on `image.place_id`
(`image_processing_worker.py:197-263`).

## Proposed test (failure-path variant -- recommend running this first)

Exercises the exact gap (stuck-row detection + terminal-status
transition) with the smallest possible blast radius: no real image
content ever touches R2, so there's nothing to accidentally expose.

1. Create one dedicated, clearly-marked test place (`is_active=False`,
   name like `"__synthetic_image_recovery_test__"`, fresh UUID city if
   needed) -- same pattern as the backend test suite's own fixtures
   (see `tests/test_place_video_presence.py` for the idiom), so it can
   never surface on Feed/Search/Trending regardless of outcome.
2. Insert one `PlaceImage` row directly (not through the upload API):
   `place_id=<that test place>`, `uploaded_by=<synthetic test user id>`,
   `orig_key='synthetic-recovery-test-<uuid>'` (deliberately does not
   exist in R2), `status='pending'`, `created_at = now() - INTERVAL
   '35 minutes'` (past the 30-minute cutoff with margin).
3. Let the next natural `image_processing_recovery` fire (every 10 min)
   pick it up, or force one bounded manual invocation of
   `_job_image_processing_recovery()` exactly like the prior canary --
   same job function, no new code path.
4. Expected: job run reports `reclaimed=1` (not 0, for the first time);
   the `PlaceImage` row transitions `pending` -> `processing` ->
   `failed` (missing R2 object raises inside `get_object`, caught by
   the outer except); no place, image, or Feed/Search surface changes.
5. Clean up after: delete the synthetic `PlaceImage` row and the test
   place (hard delete is fine here -- nothing else references either,
   unlike the menu-canary rows).

## Optional follow-up (success-path variant, only if the above is clean)

Same setup, but first do a real presigned-URL R2 PUT of a small,
controlled, non-sensitive test image (same upload flow as your video
test) so `orig_key` resolves to real bytes, proving the `status='ready'`
path and the dedup/hash/moderation pipeline too. Higher setup cost, only
worth it if you want that path proven now rather than left as a known
gap alongside the video classifier-quality one.

## Next action

Run the failure-path variant above (or tell me why not, if something in
it looks wrong from where you sit with actual DB/Railway access). Record
the evidence in your usual bridge handoff format when done -- job_runs
row ID, before/after `PlaceImage.status`, confirmation the test place
was never active/visible, and confirmation of cleanup.
