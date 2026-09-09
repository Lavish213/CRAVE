# CRAVE Map V2 — Final researched implementation plan

Status: APPROVED FOR IMPLEMENTATION
Date: 2026-09-08
Scope: UI V2 Search/Map pilot only

## 1. Product job

Map is a contextual spatial decision surface. It is not a directory, leaderboard, or independent recommendation engine.

> Map shows the spatial relationship between CRAVE's current few answers.

The default experience should preserve broad discovery while limiting simultaneous visual competition.

## 2. Research synthesis

External research used to pressure-test this plan:

- Airbnb engineering: map attention differs from list attention; limiting map exposure to stronger candidates and treating map presentation as its own ranking/attention problem improved discovery outcomes. Camera placement is part of recommendation UX.
- Uber engineering: a monolithic map controller became fragile as features accumulated. Uber separated layer ownership, padding/viewport concerns, and camera authority so features could not fight over shared map state.
- Yelp: moving the map does not have to silently redefine the search; an explicit "Redo/Search this area" action preserves user intent.
- Google Maps Platform, Apple MapKit, and Mapbox: clustering/collision management exists to reduce overlap and improve readability. Density should be reduced before adding visual complexity.

CRAVE adaptation: use these as architecture/product lessons, not visual templates. Do not copy another app's map UI.

## 3. Locked Map V2 rules

1. Search -> Map preserves the exact Search candidate universe and ordering semantics. Map never independently reranks Search results.
2. Camera movement alone never means "change my recommendation criteria." Manual pan creates eligibility for an explicit Search this area action.
3. Default visible recommendation density targets 5-10 meaningful individual places. Ten is a soft presentation ceiling, not a catalog/data ceiling.
4. More places remain discoverable through zoom, Search this area, Search, refinements, and clustering where spatial collision genuinely requires it.
5. Normal pins do not encode Elite/Gem/Solid/default as a color rainbow.
6. Production pin semantics are limited initially to normal, selected, closed/unavailable when trustworthy operational data exists, and cluster.
7. Gold is brand/selection/primary-action emphasis, not generic ranking/status paint.
8. Selected place receives focus; other pins visually recede without disappearing.
9. Selected-place card is a useful decision surface, not merely a gateway: identity/photo, one supported reason when available, distance/operational truth when available, Directions, Save, and deliberate Place Detail navigation.
10. Protected dietary/allergy constraints are not ordinary removable Map refinements and may never be silently relaxed.
11. Missing media is not failure. Missing hours is not closed. Stale hours is not current operational truth. Low personalization confidence is not a negative restaurant judgment.
12. Map/list parity must exist for accessible task completion. No essential task is map-only or gesture-only.
13. Runtime/device accessibility claims remain unverified until implemented screens are tested.

## 4. Density and clustering policy

Candidate availability and presentation density are separate concepts.

- Search context: keep the handed-off result universe intact. Prefer the first bounded recommendation set for initial presentation; clustering handles unavoidable collisions. Do not fetch replacement candidates merely to fill the map.
- Nearby/city context: presentation policy chooses a bounded, deterministic subset from the fetched candidate set before marker rendering. The backend remains authoritative for candidate ordering until the direct-mode contextual ranking gap is separately resolved.
- Saved context: saved places are user-owned evidence, not recommendations. Preserve access to the saved set; use viewport/cluster presentation rather than pretending only the highest-ranked saves matter.
- Selection: selected place always survives density reduction while selected.
- Cluster tap: zooms/focuses spatially; it does not mutate recommendation order.

No hard truncation may make an originating Search result unreachable from the equivalent list experience.

## 5. Visual hierarchy

Default viewport should read in this order:

1. map geography
2. 5-10 meaningful place marks
3. selected place, if any
4. compact context/refinement controls
5. conditional recovery/action control

Avoid simultaneous stacks of banners and floating buttons.

### Contextual control rules

- Context bar appears when Search/Saved/area context needs explanation or exit.
- Filter/refine control appears only when there are meaningful refinements.
- Search this area appears only after qualifying manual viewport movement in nearby/city mode.
- Recenter appears only when a usable user location exists.
- Saved-context control appears only for authenticated users and should not compete visually with selection.
- Loading/error/empty/recovery occupies one recovery slot. Multiple status pills must not stack.

## 6. Pin contract

`CraveMapPin` becomes the sole production renderer after compatibility retirement.

Semantic props only. No arbitrary color prop from screen code.

Required states:
- normal
- selected
- cluster(count)
- closed/unavailable only when trustworthy data supports it

Accessibility:
- meaningful label
- role supplied by map marker host
- cluster announces count and zoom action
- selected state announced without relying on color
- list equivalent available

## 7. Selected place card

`MapPlaceCard` is the decision surface.

Minimum:
- food/place media or intentional no-media identity treatment
- restaurant name
- category when useful
- distance/travel truth when available
- operational truth only when supported
- one reason/confidence statement when originating context provides evidence
- Directions when actionable
- Save state/action when supported
- View place as deliberate secondary navigation

Do not fabricate reason, hours, distance, or confidence data to fill the card.

## 8. Architecture

`MapScreenCore` must become composition/orchestration rather than a mini-application.

Target responsibility boundaries:

- `mapClustering.ts`: pure deterministic geometry/collision grouping.
- `mapPresentationPolicy.ts`: bounded display policy and selected-place preservation.
- `useMapViewport.ts`: region, camera intent, manual-pan eligibility, Search-this-area state.
- `useMapCandidates.ts`: city/search/saved candidate source and async request ownership.
- `useMapExposureLedger.ts`: impression/click exposure bookkeeping independent of rendering composition.
- `MapContextBar.tsx`: current context and exit/refinement affordance.
- `MapControls.tsx`: conditional location/saved/filter controls.
- `MapRecovery.tsx`: loading/error/empty/location/retry state slot.
- `CraveMapPin.tsx`: production pin renderer.
- `MapPlaceCard.tsx` + `MapBottomSheet.tsx`: selected-place decision surface.
- `MapScreenCore.tsx`: compose these systems and own navigation boundaries.

Implementation may consolidate a boundary when extraction would create indirection without ownership benefit, but network state, camera state, analytics state, geometry, and visual composition must not remain entangled in one component.

## 9. Preserve from current implementation

The rebuild must preserve these proven behaviors unless a test demonstrates a defect:

- Search candidate handoff without Map reranking.
- explicit Search this area after manual pan.
- request-id protection against stale async writes.
- prior-fetch coverage logic that avoids unnecessary city refetches.
- stale pins preserved on retryable map failures where already available.
- visible individual pin impression semantics; fetched/clustered candidates are not automatically impressions.
- click attribution from selected-place open action.
- location denial/no-location fallback to choosing an area.
- cluster zoom behavior.
- authenticated saved-place context.

## 10. Fix/retire

- Retire `MapMarkerDot` and `MapClusterDot` after test parity; no legacy tier-color pins.
- Remove legacy `Colors`/raw color styling from migrated Map composition.
- Replace `TouchableOpacity`/raw `Text` controls in Map V2 composition with UI V2 primitives where behavior permits.
- Remove `as any` from touched Map TypeScript.
- Stop treating dietary categories as visually equivalent to ordinary refinements when they represent protected constraints.
- Avoid duplicate camera-fit implementations.
- Avoid generic feature state being mutated by unrelated context effects.
- Keep the known direct/city Map contextual-ranking backend gap explicit; do not "fix" it by frontend reranking.

## 11. Accessibility requirements — design requirements until runtime verified

- interactive controls target at least 44x44 pt in CRAVE UI
- Dynamic Type reflows without truncating essential actions/content
- VoiceOver/TalkBack order: context -> recovery/action -> selected place actions; map has equivalent list/task path
- no meaning conveyed by color alone
- Reduce Motion removes nonessential animated transitions
- selected/cluster/closed states announced semantically
- bottom sheet dismissible without drag gesture
- location denied/unavailable remains actionable without map manipulation

## 12. Performance requirements

- do not render hundreds of individual React marker views by default
- memoize deterministic clustering/presentation calculations
- camera movement does not trigger network fetch until explicit Search this area
- no per-pin network requests
- preserve bulk backend image/category/video resolution
- marker `tracksViewChanges` remains disabled when safe
- analytics batching remains bounded to genuinely exposed individual pins

## 13. Implementation sequence

M1 — pure map presentation policy + clustering extraction and tests
M2 — migrate pin renderer to `CraveMapPin`; retire tier-color semantics
M3 — extract viewport/camera ownership and preserve Search-this-area behavior
M4 — extract candidate source/request ownership for Search/city/saved
M5 — extract exposure ledger
M6 — rebuild contextual controls/recovery with UI V2 primitives
M7 — upgrade selected-place card using only available truthful data
M8 — retire legacy Map marker bridge and remaining Map legacy styling
M9 — automated certification: TypeScript, focused Jest, full frontend Jest, CI, CodeQL, diff audit, review findings
M10 — runtime certification: real photos, dense city, no media, long names, large text, screen reader, Reduce Motion, location denied/unavailable, offline/stale, iOS/Android device pass

M10 cannot be claimed before executable device evidence exists.

## 14. Acceptance criteria

Map V2 implementation is code-complete when:

- default nearby/city presentation no longer renders an uncontrolled wall of individual pins
- Search -> Map parity remains intact
- Search this area remains explicit
- no normal pin ranking-color rainbow remains
- selected place clearly dominates without hiding all alternatives
- only one contextual/recovery message layer competes with the map at a time
- selected card provides useful actions from truthful available data
- protected constraints cannot be silently relaxed
- legacy marker renderer is retired from production Map
- MapScreenCore responsibility is materially reduced and separated
- focused and full frontend tests pass
- TypeScript passes
- required CI/CodeQL are green
- runtime certification is explicitly marked pending until device evidence is gathered

## 15. Non-goals

- making Map a sixth primary tab
- directory-scale browse UI
- frontend personalization/reranking invention
- full route-aware recommendations
- background location
- social live-location features
- reservation/order integration
- unrelated Expo/React Native modernization
- Wave 8 Posting work

## 16. Final principle

> Reduce simultaneous competition, not restaurant coverage.

CRAVE Map succeeds when a user can understand where the few relevant answers are, select one, understand enough to act, and deliberately expand the search when needed.