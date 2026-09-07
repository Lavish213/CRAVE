# CRAVE Screen Contract — Contextual Map

Status: **YELLOW — implementation migration required, no unresolved product decision**

## 1. Purpose
The Map is a **spatial support surface**, not a sixth destination and not an independent ranking engine. It visualizes a bounded candidate set supplied by Feed, Search, Craves, or direct nearby exploration and helps the user understand where viable choices are.

Canonical invariant: **Map never independently reranks the set it receives.**

## 2. User objective
Answer: “Where are the relevant places?” without turning CRAVE into a dense directory or generic maps product.

## 3. Entry points
- Feed / Decision Session: map only the active recommendation set.
- Search: map the exact current result set 1:1.
- Craves: map the prioritized relevant saved subset.
- Place Detail / directions context: spatial support only.
- Lightweight direct Map affordance: show a small nearby CRAVE set when no parent candidate set was supplied.

Map is **not** a bottom-tab destination in target V1 navigation.

## 4. Exit points
- Place Detail through deliberate card/sheet escalation.
- Directions.
- Save/Crave where already supported by the candidate contract.
- Back to the originating surface with its state preserved.

## 5. First viewport
- Maximum useful density by default: roughly 5–10 individually actionable pins, not a city-wide wall of markers.
- When opened directly, prefer a tiny “near you now” set; if location is unavailable, show **Choose an area** rather than failing.
- Preserve the originating candidate order/identity even though geographic placement changes visually.

## 6. Information hierarchy
1. Geographic context / chosen area.
2. Bounded candidate pins.
3. Selected-place preview card/sheet.
4. Explicit **Search this area** control after meaningful pan.
5. Filters or mode controls only when they modify the parent request context rather than create an independent ranking system.

## 7. Component tree
Reuse/extend existing:
- map container / `MapView`
- `MapMarkerDot` / `MapClusterDot`
- `MapBottomSheet`
- `CitySelectorStrip` where an area chooser is appropriate
- `FilterSheet` only for approved shared constraints

Do not create a second Place Detail card system inside Map.

## 8. Current-code reconciliation
Current `frontend/app/(tabs)/map.tsx` is a full tab-level browsing surface, fetches its own city/saved GeoJSON, clusters a potentially broad result set, and contains its own recommendation-ledger session semantics. Target V1 keeps useful map rendering, clustering, saved-place support, and bottom-sheet primitives but changes ownership:
- remove Map from top-level tabs;
- accept a parent candidate-set/context contract when entered from Feed/Search/Craves;
- direct Map exploration uses the shared recommendation request/context contract rather than a private map-ranking interpretation;
- panning never auto-reranks; explicit **Search this area** creates a new request;
- no raw precise location is logged as analytics evidence.

## 9. Core states
- parent candidate set available
- direct-nearby candidate set
- saved/Craves candidate set
- loading
- success
- thin coverage
- no results
- location denied
- location unavailable
- stale operational data
- offline with cached candidate set
- offline without usable cache
- map-provider/render failure

## 10. State Coverage Table
| State | Required behavior |
|---|---|
| Anonymous | Full browsing allowed; stateful Save triggers shared auth gate |
| Authenticated | Same spatial behavior plus approved personal state |
| Loading | Keep geographic shell stable; avoid blank-screen replacement |
| Success | Bounded pins + selected-place preview |
| Empty | Explain no matching places in this area; offer area/context change |
| Partial data | Render known factual location; omit unsupported operational claims |
| Stale | Mark stale actionability where material; fit confidence remains separate |
| Offline | Show cached set with timestamp if safe; no fake “open now” |
| Location denied | Choose an area; never dead-end |
| Low confidence | Preserve parent confidence labels; Map does not strengthen them |
| Error | Retry the failed operation, not navigate away |

## 11. Interactions
- Tap pin → preview only.
- Tap preview / explicit details affordance → Place Detail.
- Tap cluster → zoom/reveal, not recommendation evidence for each child.
- Pan → visual exploration only.
- **Search this area** → explicit new request scoped to visible region.
- No swipe-to-decide.

## 12. Data reads
- candidate set / recommendation request context
- place coordinates
- approved operational facts and freshness
- saved state when relevant
- selected area/location permission state

## 13. Data writes / evidence
- pin impression only when an individual place is actually represented/visible under the existing ledger semantics
- Place Detail click on explicit escalation
- search-this-area request context
- Save through shared save flow

A bare pan, cluster member, or offscreen fetched candidate is not an impression.

## 14. Permissions
Location permission is optional. No background location. No requirement for precise location by default. Denial always degrades to manual area selection.

## 15. Offline / stale behavior
Cached places may render. Current-hours/availability claims must not be presented as current when stale. Menu/photo staleness is tolerated according to provenance rules; operational actionability is stricter.

## 16. Accessibility
Every Map workflow must have a list-equivalent path. Pins cannot be the sole carrier of meaning. Selection, distance, fit/confidence, and CTA meaning must be available to screen readers and without color.

## 17. Analytics
Map analytics describe spatial decision support, not engagement. Do not measure success by dwell, pan count, or repeated browsing. Preserve source surface so Map never receives false credit for creating a recommendation it merely visualized.

## 18. Responsive behavior
Bottom sheet/card must remain readable under large text. Preserve touch targets and safe areas. On smaller displays, reduce visible chrome before reducing actionable text.

## 19. Visual rules
- simple pins;
- no popularity heatmap;
- no sponsored/promotion pin layer;
- no dense generic-directory presentation;
- selected card uses CRAVE’s shared reasoning grammar when reasoning exists.

## 20. Prohibited behavior
- Map as top-level V1 tab
- automatic reranking on pan
- independent popularity ranking
- background location collection
- exact-location social exposure
- paid placement in recommendation pin set
- map-only workflow with no accessible list alternative

## 21. Unresolved dependencies
No product decision blocker. Implementation remains YELLOW until navigation migration and shared candidate-set/request plumbing are completed atomically.

## 22. Codex implementation boundary
Codex may reuse the current rendering/clustering primitives and refactor ownership. Codex may not preserve the current “Map is its own independent recommendation surface” behavior simply because it is already shipped.

## 23. Acceptance criteria
- Map absent from target bottom tabs.
- Search/Feed/Craves sets map without independent reranking.
- Pan does not refresh until explicit Search this area.
- Location denial yields area chooser.
- selected preview escalates deliberately to Place Detail.
- list-equivalent path exists.
- stale/offline operational claims remain honest.

## 24. Traceability
Governed by: CRAVE V1 Scope, Target Screen Registry, Route & Flow Map, Data & State Map, Privacy/Permission Matrix, Evidence/Signal Hierarchy, Design System, Component Registry.

Forward dependencies: shared recommendation request/context API contract, navigation migration plan, MapBottomSheet/marker implementation tasks, screen-level regression tests.
