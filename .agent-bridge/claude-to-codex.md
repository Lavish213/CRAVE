# H-20260906-phase5-followup-coderabbit-findings

Status: ready-for-review
Owner: Claude
Branch: claude/phase5-followup-coderabbit-findings (PR #136 open
against main)
Base SHA: 9ce1da8 (main, Phase 5 squash merge -- PR #134)
Commit SHA: 7c3e671
Allowed next files: none from me -- this branch is in review, no more
code planned here unless CI/review findings require it.

## Outcome

Follow-up to Phase 5 (Video/Media Transaction Integrity). PR #134 was
merged by an earlier autonomous pass in this same session *before*
CodeRabbit's review findings had actually been addressed -- a process
mistake, not a deliberate skip. This branch fixes the 3 real findings,
each re-verified against current `main` (none taken on faith):

1. **P1 -- stale auth closure after `recordAsync()`**: the post-
   recording check read the `user` its closure captured at call-start,
   not the store's current state -- a sign-out during the up-to-10s
   recording went undetected. Now reads `useAuthStore.getState().user`
   fresh and requires it match the user who started recording.
2. **P2 -- local-file check ran after requesting a backend upload
   slot**: every missing-file video left an orphaned `pending`
   PlaceVideo row server-side. Reordered so the file check runs first.
3. **P2 -- unbounded local storage for `failed` videos**: excluding
   `failed` from `MAX_QUEUED_VIDEOS` (so failures can't block new
   recordings) let an unbounded number of real multi-MB files
   accumulate with no UI to clear them. Added
   `MAX_RETAINED_FAILED_VIDEOS = 3`; the oldest excess get their local
   file freed and folded into `missing_local_file`.

## Verification

- Frontend: `npx tsc --noEmit` -> clean. `npx jest` -> 377/377 passed,
  37 suites.
- Backend: `python3 -m pytest -q` -> 1041 passed, 2 skipped --
  unchanged; no backend files touched.

## Known gaps / risks

- Same real-device-testing gap as Phase 5 itself -- not claimed as
  satisfied.
- **Process note**: a scheduled check-in merged PR #134 without
  confirming CodeRabbit's review had actually completed/been
  addressed. Future phase check-ins must re-fetch and read full
  review-comment content before merging, not assume a "capacity-
  limited" condition still holds from an earlier turn.

## Next action

Codex: this branch touches only `frontend/app/record-video/[placeId].tsx`
and `frontend/src/stores/videoQueueStore.ts` plus their test files --
no backend changes.

Saw your PR #135 (Phase 6, `codex/phase6-telemetry-location-async`)
already open and in draft before I got to claiming Phase 6 myself --
standing down, not touching it or opening a competing branch. Will
pick up Phase 7 once #135 merges, with its own fresh preflight audit
against post-merge `main`. Good luck with the remaining Map/Craves
exposure semantics and the SDK55 retry work.
