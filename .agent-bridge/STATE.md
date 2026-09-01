# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: b2439d0 (PR #106 merged)
Scope: Finished "The Pass" -- built the frontend for all three "Now"/"On
Deck" tickets from the backend pass (PRs #100-#102), so E8/E2/E3 are now
actually visible/usable in the app, not just API-level. Shipped as 3
more independently reviewable PRs (#104, #105, #106), same discipline as
every change this session.

## PR #104 -- video badge frontend (E3)

PlaceOut/NormalizedMapFeature gain `has_video`, threaded through both
normalizers' explicit-field mapping. getBadges() gets a Video chip,
additive alongside the existing menu/delivery badge (a place can show
both). No Map pin treatment -- has_menu itself was never rendered
differently on pins either, confirmed via grep before deciding not to
invent a new affordance.

## PR #105 -- Hitlist visited/notes UI (E2)

New SavedPlace type (PlaceOut + visited/visited_at/notes), kept separate
from PlaceOut so Feed/Search/Map stay untouched. cravesStore gets
setSaveMemory() -- optimistic, reconciles with the server-confirmed
response on success (not the local guess), rolls back on failure, no
offline queue (lower-stakes than save/unsave, not worth duplicating that
machinery). Place Detail gets an "I've been here"/"You've been here"
toggle plus a notes field, shown only once saved. Craves list rows get a
presence-only indicator (checkmark + note icon) -- content stays
detail-view-only per the design doc's own call.

## PR #106 -- Filter UI grouped by category type (E8)

Real finding here, not just a relabeling: the old flat "CUISINE" filter
section's GENERIC_FILTER_CATS blacklist turned out to be exactly the 11
former-`specialty` category names -- every dietary/ownership/occasion/
recognition category was completely absent from the Filter UI, not just
unlabeled. Fixed with real type-based sectioning (new useCategoryTypes()
hook, module-cached name->type lookup). Also caught and fixed along the
way: an unhandled promise rejection on a failed category fetch, found by
actually running the affected tests (5 existing map-instrumentation
tests broke on a first react-query-based attempt, which also would have
required wrapping 3 screens' tests in a QueryClientProvider they don't
have -- switched to a self-contained hook instead of forcing that
requirement onto every caller).

## Verification

Full frontend suite on final integrated main: 331 passed, 0 skipped
(302 baseline + 29 new across the three PRs). tsc --noEmit clean. Every
new/changed behavior regression-checked (reverted, confirmed the test
fails, restored) before merging, including two real bugs caught only by
actually running tests rather than reasoning about the code (the
unhandled rejection above, and the QueryClientProvider requirement
breaking existing tests).

## Known gaps / risks

The Decision-Session ranking hook that auto-sets visited=true (E2's "B"
half of "both, B default") is still not built -- explicitly scoped out
of PR #105 as separate follow-up, not forgotten. E10 group compatibility
remains correctly un-built, still held on Decision Session proving
itself solo at real volume.

## Next action

Nothing needed from you on this pass -- all three PRs are merged and
green, this is genuinely done. Standing by for the next
`moderation_queue_health_check` update or whatever's next on the
production side -- unrelated track, no overlap with this work.

## Existing local work excluded from this bridge

The primary checkout's `eas.json`, `package.json`,
`frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` remain unrelated and untouched.
