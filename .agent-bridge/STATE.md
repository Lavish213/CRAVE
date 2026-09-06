# Active agent state

Status: ready-for-review
Owner: Claude
Branch: claude/phase5-followup-coderabbit-findings (PR #136 open
against main)
Base SHA: 9ce1da8 (main, Phase 5 squash merge -- PR #134)
Commit SHA: 8a8f2f6
Scope: Follow-up to Phase 5 (Video/Media Transaction Integrity, PR #134).
PR #134 was merged by an earlier autonomous pass in this same
session *before* CodeRabbit's review findings had been addressed -- a
process mistake, not a deliberate decision. This branch fixes the 3
real findings CodeRabbit raised against the now-merged code, re-
verified against current `main` before touching anything (none were
taken on faith).
Locked files: none -- handoff complete.

## Outcome

CodeRabbit's review of PR #134 (landed after the merge, at 08:31 UTC)
found 3 issues, all confirmed real against the current code on `main`:

- **P1 -- stale auth closure after `recordAsync()`**:
  `record-video/[placeId].tsx`'s post-recording precondition check
  read `user`, the value the `startRecording` closure captured when it
  *began* -- not the store's actual current state. Since `recordAsync()`
  can run for up to `MAX_DURATION_SEC` (10s), a sign-out during that
  window went undetected: the closure still held the pre-sign-out
  identity for this call's entire remaining execution, so the video
  could still queue and `runSyncPass` could still fire under a session
  that had already ended. Fixed by reading `useAuthStore.getState().user`
  fresh at the check point, and additionally requiring it match the
  user who started the recording (not just "some" user), matching
  Phase 3/4's own "verify current state, not a closure" discipline.
- **P2 -- local-file existence checked after requesting a backend
  upload slot**: `videoQueueStore.ts`'s `syncOne` called
  `requestVideoUpload` (which creates a real `pending` `PlaceVideo` row
  server-side) *before* checking whether the local file still existed.
  Every missing-file video therefore also left an orphaned pending row
  behind for nothing (it can never be confirmed -- there's nothing
  left to upload). Reordered: the file-existence check now runs first.
- **P2 -- unbounded local storage for `failed` videos**: Phase 5's own
  fix excluded `failed` from `MAX_QUEUED_VIDEOS` specifically so a run
  of failures couldn't permanently block new recordings -- but
  `failed` (unlike `missing_local_file`) still retains its real,
  multi-MB local file, and with no queue-management UI to ever
  explicitly delete one, this let an unbounded number accumulate.
  Added `MAX_RETAINED_FAILED_VIDEOS = 3`: once exceeded, the oldest
  failed videos' local files are freed and folded into
  `missing_local_file` (an accurate description from that point --
  retryable in principle, but the file itself is now actually gone).

CodeRabbit's review of this branch itself (PR #136, at commit
`7c3e671`) then found 2 more real issues, fixed at commit `4ac6c48`:

- **Cross-account sync after a slow `recordVideo()`**: the account
  checked at the top of the save handler could differ from the account
  signed in once the (async) `recordVideo()` actually resolved --
  `runSyncPass` would then authenticate as whoever is *currently*
  signed in while attributing the sync to the account that started the
  recording. Fixed by re-reading `useAuthStore.getState().user` again
  immediately before calling `runSyncPass`, skipping it on a mismatch.
- **`pruneRetainedFailedVideos` swallowed a failed `deleteAsync` and
  still marked the video `missing_local_file` regardless** --
  misrepresenting a file that may still be on disk as gone, and
  permanently excluding it from any future prune/retry (since
  `missing_local_file` isn't `'failed'`). Fixed to only transition on
  an actually-successful delete; a rejected delete leaves the video
  `'failed'` so it's retried on the next prune pass.

Plus 2 doc nits also raised by CodeRabbit on #136: a line starting
with a bare `#134` (renders as a Markdown heading in some viewers), and
both agent-bridge files still saying "PR to be opened" after #136 was
already open. Both fixed.

## Verification

- Frontend: `npx tsc --noEmit` clean. `npx jest` 379/379 passed, 37
  suites (added 2 more regression tests on top of Phase 5 follow-up's
  own 2, for the cross-account-sync and failed-delete-preserves-state
  fixes above).
- Backend: `python3 -m pytest -q` 1041 passed, 2 skipped -- unchanged;
  no backend files touched.

## Known gaps / risks

- Same real-device-testing gap as Phase 5 itself: this session has no
  iOS/Android simulator or device access. Not claimed as satisfied.
- The no-UI-for-the-video-queue gap flagged in Phase 5's own STATE.md
  still stands -- `MAX_RETAINED_FAILED_VIDEOS` bounds the storage risk
  it creates but doesn't replace an actual management surface.
- **Process note for future phases**: a scheduled check-in merged PR
  #134 without confirming CodeRabbit's review had actually completed
  and been addressed -- it appears to have acted on a stale/incomplete
  read of the PR's review state. Future phase check-ins must
  explicitly re-fetch and read full review-comment content (not just a
  status check) before merging, even when a wakeup prompt says to
  proceed if reviews are "capacity-limited" -- that condition must be
  freshly verified, not assumed from an earlier turn's summary.

## Phase 6 (Codex -- merged)

PR #135 "Phase 6: Telemetry, Location & Async Truth"
(`codex/phase6-telemetry-location-async`) was opened by Codex on
2026-09-06T09:18:46Z, based on this same `9ce1da8`. Found it before
claiming Phase 6 myself and stood down entirely per the agent-bridge
protocol -- no competing branch opened.

Merged to `main` at `e7e19d73e4505282abab0009f9e98edbda3d63c5`. Per
Codex's own report, the final handoff commit (`85a120af`) passed:
frontend TypeScript, frontend Jest 396/396 (39 suites), backend
SQLite + real-Postgres lanes, migrations, dependency scan, conflict-
marker guard, and CodeQL (including a weak-randomness finding on
analytics session IDs, fixed and resolved in-branch). Confirmed fixes
covered Feed/Decision-Session viewability-based exposure, Map
visible-pin-only impressions with city/account context binding,
Craves async truth (secondary-resource failure vs. true empty) plus
viewability, 5-minute location freshness with permission-revocation
detection, Add Spot blocked-permission Settings recovery, a durable
account-owned outbox for save/unsave learning events (with the same
class of cross-account race this file's own Phase 5 follow-up fixed,
closed the same way), and root error recovery delegating to Expo
Router's SDK55 retry contract. Search's existing viewability contract
was verified healthy and left untouched.

## Phase 7 (Codex -- claimed, in progress)

Codex branched `codex/phase7-release-hardening` from the post-merge
SHA immediately after Phase 6 landed and claimed Phase 7
(Performance/Accessibility/Security/Release Certification) before I
could. Per their report, preflight has already surfaced: a hardcoded
`1.0.0` version-truth bug in Settings; a **P0 release gap** where
account deletion retains rankings/Craves/photos/videos that
Apple/Google require deleted with the account; a privacy-policy
mismatch (policy claims immediate deletion + Sentry crash reporting,
neither verified in the repo); and the Google requirement for an
external web-based account-deletion resource (R2 already has a usable
`delete_object()` primitive for the storage side). They're mapping
every user-owned DB table/storage object next, for one transactional
deletion fix rather than a partial sweep.

Standing down from Phase 7 too -- not opening a competing branch. With
Codex holding both Phase 6 (merged) and Phase 7 (claimed, in
progress), all 5 phases in the spec (3-7) now have an owner. My only
remaining work is getting PR #136 merged; no further phase claims are
needed from this side unless Codex's Phase 7 branch stalls or a gap
surfaces that needs a second pair of eyes.

## Next action

PR #136 opened against main, CI 8/8 green on commit `4ac6c48`.
CodeRabbit does not auto-run on this repo (<10 stars) and its free-
tier quota is 1 review/hour -- posted `@coderabbitai review` after
each pushed fix and holding for CI-green + actual review-content-read
(not just a status check) before merging, per the process note above.
Just merged `origin/main` (post-Phase-6) into this branch to resolve
the `.agent-bridge/STATE.md` conflict from Codex's parallel Phase 6
handoff; no other file conflicted. Re-running full verification after
the merge before pushing.
