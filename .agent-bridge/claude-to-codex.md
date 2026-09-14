# H-20260914-offline-upload-visibility-fixup

Status: ready-for-review
Owner: Claude
Branch: claude/offline-upload-visibility-fixup
Base SHA: d8e7692 (origin/main tip, PR #307 squash-merged)
Commit SHA: pending (see PR for the authoritative head SHA once pushed)
Allowed next files: none from me pending PR review.

## Outcome

Follow-up to `H-20260914-offline-upload-visibility` (PR #307, merged
`d8e7692`). That PR's CodeRabbit review had not yet posted its actual
line-level findings when CI went green (only the summary/docstring-
coverage note had landed) -- I merged on green CI without waiting for
them, and the 4 real findings arrived seconds later. Fixing all of them
forward here rather than leaving them unaddressed:

1. **Real Major bug (confirmed, not a false positive)**: PR #307's new
   `pruneSyncedVideos` step removed every `'synced'` video row
   unconditionally on the next sync pass. But `syncOne`'s own
   `FileSystem.deleteAsync` call silently swallows a genuine (non-
   "already gone") failure and still marks the row `'synced'` regardless
   -- so a real cleanup failure meant the row, and its `localUri`, was
   permanently lost, orphaning the file on disk with no way to ever
   retry cleanup. Fixed: the prune step now retries the (idempotent)
   delete itself and only removes a row once that retry actually
   succeeds -- mirroring the existing `pruneRetainedFailedVideos`
   pattern exactly. Two new regression tests (one confirming a
   still-failing delete keeps the row and its `localUri`, one confirming
   recovery once a later retry succeeds), both independently confirmed
   to fail on the pre-fix (merged) code.
2. **Minor, real**: Retry/Delete controls in `uploads.tsx` were 32dp
   with no `hitSlop`, short of a real touch target. Added
   `hitSlop={{ top: 8, bottom: 8, left: 6, right: 6 }}` to all four --
   6dp left/right keeps adjacent Retry+Delete pairs (12dp apart) exactly
   flush rather than overlapping, 8dp top/bottom clears 44dp.
3. **Minor, real**: both handoff records said "three" follow-ups remain
   while listing four -- corrected to "four" in both files.
4. **Minor, real**: both handoff records left `Commit SHA: pending` for
   PR #307. `.agent-bridge/STATE.md`'s #307 entry was edited in place --
   its `Commit SHA` field now reads `ec475e9` (squash-merged as
   `d8e7692`). This file's own #307 entry wasn't edited in place; it was
   replaced outright by this new handoff document per this repo's own
   protocol ("Keep inboxes short... replace its body with a compact
   summary" -- `claude-to-codex.md` holds only the latest outgoing
   handoff, unlike `STATE.md`'s stacked log), so the stale value no
   longer appears here at all rather than being literally corrected in
   place. This document's own `Commit SHA` field above is correctly
   `pending` -- it refers to *this* fixup PR, not #307.

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest --ci src/stores/videoQueueStore.test.ts` -> 20/20 (2 new).
  Both new tests independently confirmed to fail against the merged
  pre-fix code via revert-and-rerun before restoring the fix.
- Full `npx jest --ci` and `git diff --check` re-run before push (see PR
  for exact numbers).
- Backend untouched.

## Known gaps / risks

None new. Same four offline-upload-UX follow-ups from the original PR
remain open (per-video status polling, wifi-only NetInfo toggle, real
upload progress via XHR, merged local+server video feed).

## Next action

None needed from you -- this doesn't touch your dashboard lane. This
time I'm holding this PR for the user's explicit merge approval rather
than auto-merging on green CI, since merging #307 the moment CI went
green (without waiting for CodeRabbit's actual findings to post) is what
let these findings land post-merge in the first place.
