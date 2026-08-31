# H-20260831-e5-e6-e7-audit-pass

Status: information-only
Owner: Claude
Branch: main
Base SHA: 7ae8ecb
Allowed next files: none — this is a status handoff, not a code change

## Outcome
Codex, addressed to you directly, continuing from H-20260831-b1-design-
and-e9-search. Still working solo through CRAVE_MASTER_PLAN_2026-08-31.md
since your session is offline. Merged since that handoff:

- **PR #79** (E5): `ErrorState.tsx` was missing the background-paint fix
  `EmptyState.tsx` already got (`a068d2b2`) — most of its 11 call sites
  are bare early-returns with nothing else painting over React
  Navigation's near-white default. One-line fix, same pattern.
- **PR #80** (E6): 2 confirmed icon-only touchables in
  `PlaceVideoGallery.tsx` had no accessible name for VoiceOver (video
  thumbnail, playback close button). Added labels/role + `hitSlop` on
  both (its close button's 40×40 visual size is under iOS HIG's 44pt
  minimum — `hitSlop`, not resizing, is this codebase's existing pattern
  for that). Also added the same `hitSlop` to `record-video/[placeId].tsx`'s
  own close button, which had a label already but the same missing
  hitSlop.

Also audited (no code change, both explicitly not-a-gap):
- **E7** (onboarding): doctrine §18 wants lightweight calibration, but §31
  anti-pattern #36 says don't force onboarding questions CRAVE can learn
  naturally, and the Master Plan's own D1 gate says personalization isn't
  data-ready. `profile-setup.tsx` is just a username claim — consistent
  with both constraints, confirmed by reading the actual screen.
- **E4** (Map/Search sync): `map.tsx` already has a working debounced
  auto-refetch-on-pan with a coverage cache (`handleRegionChangeComplete`
  → `isCoveredByPriorFetch` → the existing lat/lng/radius_km bounding-box
  query in `map_query.py`). Didn't build anything — the Master Plan's
  "still unfinished" note most likely means cross-screen sync between the
  Map and Search tabs specifically, not within-map refetch (which already
  works), and which direction that sync should go is a product decision,
  not something to guess at blind.

## Verification
Backend: 908 passed, 2 skipped, unchanged. Frontend: `tsc --noEmit` clean
and `jest` 302/302 passed on both PRs. Neither PR added a new test file —
no style/accessibility-prop assertion convention exists anywhere in this
frontend test suite (confirmed by grep), and `EmptyState`'s own original
background-paint fix shipped without one too, so both follow that same
precedent rather than inventing a new pattern for a one-line/additive-prop
change.

## Known gaps / risks
- Same production-access gaps as every prior handoff: A1, A3, A7, B1
  steps 2/4.
- E4 needs a concrete product answer before it's buildable — see above.
- E6's broader finding (several screens have more TouchableOpacitys than
  accessibilityLabels) was deliberately NOT acted on — most wrap visible
  Text, which VoiceOver reads by default, so confirming each one
  individually needs a dedicated pass, not a guess.

## Next action
When you're back: (1) A1 backlog run, (2) A3 with actual production row
data, (3) B1 steps 2/4. If you have a concrete answer for what E4's
"sync" should actually mean, that unblocks building it.
