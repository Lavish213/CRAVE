# H-20260914-offline-upload-visibility

Status: ready-for-review
Owner: Claude
Branch: claude/offline-upload-visibility
Base SHA: 9653aff (origin/main tip after PR #306)
Commit SHA: pending (see PR for the authoritative head SHA once pushed)
Allowed next files: none from me pending PR review.

## Outcome

Per your `H-20260914-data-pipeline-dashboard-split` handoff, took offline-
upload UX (you kept the backend admin/source dashboard; the other two
items in my half -- universal-link credentials, device certification --
stay blocked on Railway/EAS/App-Store/device access this sandbox doesn't
have).

`videoQueueStore`/`postingDraftStore` already had durable local-first
queues with retry/delete built and tested, but no UI ever surfaced them --
a failed video or an unresolved draft just sat invisibly. New
`frontend/app/uploads.tsx` (linked from a new Settings row showing a live
pending count) lists both stores' non-terminal-success items for the
signed-in user and wires the already-built `retryFailedVideo`/
`deleteFailedVideo`/`attachDraftToPlace`-retry/`deleteDraft` into real
buttons.

Also fixed a real gap found while reading `videoQueueStore.ts` in full:
`syncOne()` marked a video `'synced'` and deleted its local file but never
removed the row from the persisted `videos` array -- unbounded
AsyncStorage-array growth, since nothing reads `'synced'` entries.
Pruned at the *start* of the next `runSyncPass` rather than immediately,
so a caller awaiting the same pass that just synced a video still sees it
(matches the existing test's expectation).

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest --ci` -> 62/62 suites, 586/586 tests. New: `uploads.test.tsx`
  (9 tests), 2 new `settings.test.tsx` tests, 1 new `videoQueueStore.test.ts`
  test. Each new/changed behavior independently confirmed to fail on the
  pre-fix code via revert-and-rerun before restoring the fix.
- `git diff --check` -> clean.
- Backend untouched.

## Known gaps / risks

Visibility/retry/delete only -- not the full offline-upload UX roadmap.
Three more scoped follow-ups remain, deliberately not bundled into this
PR: (1) per-video status polling via the already-defined but unused
`fetchVideoStatus`; (2) `@react-native-community/netinfo` + a wifi-only-
upload Settings toggle gating sync passes; (3) real upload progress via
`XMLHttpRequest.upload.onprogress` instead of plain `fetch`; (4) merging
locally-queued video placeholders into `PlaceVideoGallery`'s server-
approved feed.

## Next action

None needed from you -- this doesn't touch your dashboard lane. Whoever
picks up the next offline-upload-UX slice should start from the four
follow-ups above.
