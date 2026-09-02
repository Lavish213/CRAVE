# H-20260902-track1-feed-detail-craves

Status: ready-for-review
Owner: Claude
Branch: claude/track1-feed-detail-craves-journey
Base SHA: 6e32ba4 (main, post-PR#125 brief merge)
Commit SHA: 486689b
Allowed next files: none from me -- handoff complete, no more code
planned on this branch pending review.

## Outcome

Track 1 of `docs/CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`
(your brief, PR #125). Two real, confirmed bugs fixed; one item
verified already solid; two items and one observation flagged as
genuinely out of reach from here.

**Item 2 -- missing-media compaction.** `PlaceCard`'s no-image fallback
and `ImageGallery`'s empty Place Detail hero both reserved the *exact
same* vertical space a real photo would (220px / 280px) -- a giant
flat panel with a big initial letter, reading as a stretched/broken
image. This is the concrete mechanism behind the device audit's "blank
beige placeholders occupy most of each card" finding. Extracted a
shared `MissingMediaState` component (camera-outline + "No photo yet",
matching `ImageGallery`'s pre-existing empty-state language) sized
materially smaller at both call sites (96px / 120px), dropped the
now-pointless photo-readability scrim over a flat panel.

**Item 5 -- Save/Craves overlap.** `CravesScreen` renders three
independent lists (direct saves, share-parsed CraveItems, typed-name
PlaceSaveItems) with zero cross-referencing. A place that's both
directly saved and later matched via a shared link (or typed-name add)
rendered as a full row in two or three sections at once -- the "saved
places and typed/matched places appear as two overlapping lists"
finding. Fixed at the render layer only: a matched crave/placeSave
whose resolved place_id is already a direct save is filtered out of
its own section. The underlying CraveItem/PlaceSaveItem records are
untouched (per your explicit instruction not to collapse distinct
domain records) -- their source/reason metadata stays intact for if
the direct save is later removed.

**Item 3 -- Feed decision-surface refinement.** Verified, not changed:
Decision Session already renders via `ListHeaderComponent` (genuinely
first/primary when data exists), each card carries a real explanation
(`reasonCaption`) plus its role badge, error/empty states are already
distinct with retry, and Feed is correctly browsable signed-out
(gated only on the save action). One real observation left unfixed on
purpose -- see Known gaps.

**Items 1, 4, 6 -- not attempted.** Item 4 (Place Detail hierarchy) is
left as-is; `CRAVE_STATUS.md` already records it matching the doctrine
spec, not freshly re-verified here since nothing needed changing.
Items 1 (fresh-build screenshots) and 6 (Dynamic Type/VoiceOver/
reduced-motion device pass) categorically need a simulator/device this
Linux container doesn't have.

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest` -> 334 passed, 35 suites (up from 331/34 -- 3 new tests).
- Each of the 2 behavioral fixes regression-checked individually:
  reverted the height constant / re-enabled the unfiltered list,
  confirmed the corresponding new test fails with the expected
  message, restored, confirmed green again.

## Known gaps / risks

- No simulator/EAS access anywhere in this session -- this is code +
  test-level proof only. The brief's own acceptance criteria require
  "fresh screenshots... before/after screenshots in the PR" -- that
  step is genuinely missing and needs whoever has device access.
- Track 2 (menu/photo coverage) not started at all -- confirmed this
  session has zero production credentials (`DATABASE_URL`,
  `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` all unset), so Phases
  A/B/D/E/F are all unreachable from here, not just the write-risky
  ones. Stays entirely with you.
- Real, unfixed observation: Decision Session's 3 picks and the main
  ranked Feed list are independent queries (`useDecisionSession()` vs.
  `fetchPlaces()`/`useInfiniteQuery`) with no cross-filtering, so the
  same place can appear once in "DECIDE NOW" and again in its normal
  tier section further down. Not named in the device audit or your
  brief's acceptance criteria, and a real fix means coordinating two
  independently-paced queries -- more invasive than a bounded fix, and
  arguably intentional (reinforcing a strong pick isn't obviously
  wrong the way the three-blind-lists Craves bug was). Flagging rather
  than freelancing.

## Next action

Whoever has simulator/EAS access: rebuild against this branch, capture
the Feed/Place Detail/Craves screenshots the brief's acceptance
criteria require, confirm the two fixes actually look right on-device
(no-photo cards genuinely compact, no duplicate saved-place rows), then
review/merge. Track 2 is untouched and ready whenever you pick it up --
nothing here conflicts with it.
