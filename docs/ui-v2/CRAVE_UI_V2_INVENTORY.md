# CRAVE UI V2 Repository Census

**Status:** UIV2-00 COMPLETE — repository census baseline
**Base SHA:** `1199e27c6ba9f00ac21e1eaf80d482ee38b5937e`
**Scope:** current Expo/React Native frontend only. This document inventories the existing UI battlefield before UI V2 production styling begins.

## 1. Census rules

Every current UI owner is classified as one of:

- **KEEP** — behavior/semantic ownership is correct; no UI V2 structural rewrite required.
- **RESTYLE** — behavior is correct; presentation should migrate to UI V2 tokens/primitives.
- **REBUILD** — current component/screen shape cannot express the approved UI V2 hierarchy cleanly.
- **MERGE** — duplicate ownership should converge into one canonical implementation.
- **ADAPT** — keep the current owner but add semantic variants/props or compose it differently.
- **RETIRE** — remove after all callers migrate and parity is verified.
- **BLOCKED** — implementation depends on a named capability/data contract not yet available.
- **INVESTIGATE** — keep unchanged until its owning product wave resolves its status.

The census does **not** authorize product redesign. Existing route/data/evidence semantics remain authoritative unless a later explicitly-approved UI V2 contract supersedes presentation only.

---

## 2. Current route/screen inventory

### Primary tab shell

| Path | Product owner | Classification | UI V2 action |
|---|---|---|---|
| `frontend/app/(tabs)/_layout.tsx` | tab navigation | ADAPT | Preserve Feed/Search/Craves/Rank/Profile topology; migrate chrome to semantic tokens/primitives only. |
| `frontend/app/(tabs)/index.tsx` | Feed / Decision Session | RESTYLE | Preserve Wave 4 hierarchy; migrate after Search/Map pilot proves UI V2 foundation. |
| `frontend/app/(tabs)/search.tsx` | Search route wrapper | KEEP | Thin wrapper remains; implementation lives in `src/screens/SearchScreen.tsx`. |
| `frontend/app/(tabs)/craves.tsx` | Craves | RESTYLE | Preserve Wave 6 intelligence and state ownership; migrate later. |
| `frontend/app/(tabs)/rank.tsx` | Rank route wrapper | KEEP | Thin redirect/wrapper remains. |
| `frontend/app/(tabs)/profile.tsx` | own Profile | RESTYLE | Preserve product contract; migrate after Rank. |
| `frontend/app/(tabs)/map.tsx` | contextual Map native wrapper | KEEP | Route wrapper remains; core lives in `MapScreenCore.tsx`. |
| `frontend/app/(tabs)/map.web.tsx` | contextual Map web fallback | ADAPT | Keep fallback behavior; align states/tokens after native pilot. |

### Supporting routes

| Path | Owner | Classification | Notes |
|---|---|---|---|
| `frontend/app/place/[id].tsx` | Place Detail | RESTYLE | Wave 7 relationship hierarchy remains canonical; visual migration later. |
| `frontend/app/rank-home.tsx` | Rank Home | RESTYLE | Preserve queue-first hierarchy. |
| `frontend/app/rank/[placeId].tsx` | Rank Comparison | RESTYLE | Preserve comparison semantics and no-swipe interaction. |
| `frontend/app/activity.tsx` | Activity | ADAPT | Move to UI V2 event-row primitive later. |
| `frontend/app/settings.tsx` | Settings | RESTYLE | Keep behavior; migrate presentation later. |
| `frontend/app/taste-profile/[userId].tsx` | Taste Profile | RESTYLE | Product dependencies remain separate from visual migration. |
| `frontend/app/user/[id].tsx` | Other Profile | RESTYLE | Preserve privacy rules. |
| `frontend/app/profile-setup.tsx` | profile setup / cold-start adjacent | INVESTIGATE | Wave 10 owns final cold-start/auth architecture; no opportunistic redesign. |
| `frontend/app/add-spot.tsx` | legacy/manual place contribution | INVESTIGATE | Do not expand during Search/Map pilot. |
| `frontend/app/food-evidence.tsx` | evidence utility | INVESTIGATE | Keep until owning evidence workflow is explicitly migrated. |
| `frontend/app/friends-feed.tsx` | legacy social feed | INVESTIGATE | Social doctrine forbids engagement-first redesign; disposition belongs to later social audit. |
| `frontend/app/leaderboard.tsx` | standalone leaderboard | INVESTIGATE | Canon says standalone only if breadth/activity; do not style into permanence before product disposition. |
| `frontend/app/record-video/[placeId].tsx` | legacy recording route | MERGE | Wave 8 composer eventually absorbs capture flow; do not visually modernize as a standalone destination. |
| `frontend/app/legal/privacy.tsx` | legal | KEEP | No UI V2 product work required beyond token hygiene if touched. |
| `frontend/app/legal/terms.tsx` | legal | KEEP | Same. |
| `frontend/app/+not-found.tsx` | routing fallback | ADAPT | Migrate to primitives after foundation; preserve function. |
| `frontend/app/_layout.tsx` | app root / providers / singleton toast | KEEP | Do not duplicate providers or toast host. |

---

## 3. `frontend/src/screens` owners

| File | Classification | Finding |
|---|---|---|
| `SearchScreen.tsx` | **REBUILD presentation / KEEP behavior** | Search semantics, query state, 8-result batching, exact-match jump, scoped Search, interpreted constraints, recent searches, explicit zero-result relaxation, recommendation logging, and Map handoff are already real. The screen is monolithic and owns raw Text/TextInput/TouchableOpacity/styles locally, so UI V2 should extract presentation into primitives/product components without rewriting search logic. |
| `MapScreenCore.tsx` | **REBUILD presentation / KEEP behavior** | Existing data handoff, clustering, explicit Search-this-area behavior, source attribution, location fallback, and Map session logging stay. Presentation should move to UI V2 pins/card/control primitives. The previously tracked backend direct-mode ranking-source gap is outside this visual pilot. |

---

## 4. Existing shared component inventory

### Recommendation/place presentation

| File | Classification | UI V2 disposition |
|---|---|---|
| `PlaceCard.tsx` | ADAPT | Keep semantic/data owner; progressively compose UI V2 `FoodMedia`, identity, reason, status, and actions. Do not create a parallel generic place card. |
| `PlaceCardCompact.tsx` | ADAPT | Current Search/Craves compact row remains semantic owner during migration. Search V2 will introduce explicit hero/supporting variants, then legacy compact presentation retires only after all callers are mapped. |
| `DecisionStrip.tsx` | ADAPT | Keep its source-specific reason vocabulary separation. UI V2 may split visual subparts (`ReasonLine`, `ConfidenceStatement`) but must retain one reasoning grammar owner. |
| `TierBadge.tsx` | KEEP | Catalog percentile tier only. Never merge with personal Rank tiers. |
| `TrendingStrip.tsx` | INVESTIGATE | Dormant; do not revive during UI V2. |

### Map

| File | Classification | UI V2 disposition |
|---|---|---|
| `MapMarker.tsx` | REBUILD | Replace presentation with `CraveMapPin` semantic variants; preserve candidate identity and bounded-map behavior. |
| `MapBottomSheet.tsx` | ADAPT | Preserve sheet interaction mechanics; compose a UI V2 `MapPlaceCard` inside. |
| `CitySelectorStrip.tsx` | RESTYLE | Shared location fallback; move to tokens/primitives. |

### States

| File | Classification | UI V2 disposition |
|---|---|---|
| `EmptyState.tsx` | ADAPT | Becomes the canonical empty/recovery shell; add semantic recovery variants instead of new screen-local empty cards. |
| `ErrorState.tsx` | ADAPT | Keep single retry/error family; migrate to primitives/tokens. |
| `SkeletonCard.tsx` | ADAPT | Keep shared loading ownership; extend with UI V2 shape variants. |
| `Toast.tsx` | MERGE/ADAPT | Existing singleton behavior stays. New `CraveToast` should be the public primitive contract over the existing host, not a second toast system. |

### Filters/sheets/modals

| File | Classification | UI V2 disposition |
|---|---|---|
| `FilterSheet.tsx` | ADAPT | Preserve filter semantics; migrate controls to UI V2 primitives. Hard constraints remain distinct from ordinary soft filters. |
| `AuthSheet.tsx` | RESTYLE | Preserve auth action replay architecture; no screen-local replacements. |
| `AuthGateHost.tsx` | KEEP | Behavioral infrastructure. |
| `MenuSubmissionSheet.tsx` | RESTYLE | Later Place Detail migration. |
| `ReportPhotoSheet.tsx` | RESTYLE | Later Place Detail migration. |
| `ReportPlaceSheet.tsx` | RESTYLE | Later Place Detail migration. |
| `ShareLinkSheet.tsx` | RESTYLE | Capture semantics unchanged. |

### Rank/social/media/support

| File | Classification | UI V2 disposition |
|---|---|---|
| `ComparisonChoice.tsx` | RESTYLE | Rank-specific; no generic swipe/choice primitive. |
| `RankQueueRow.tsx` | RESTYLE | Preserve visit-evidence semantics. |
| `RankedPlaceRow.tsx` | RESTYLE | Personal Rank presentation stays separate from catalog tiers. |
| `ShareRankCard.tsx` | RESTYLE | External sharing artifact only. |
| `ActivityRow.tsx` | ADAPT | Basis for later event-row primitive. |
| `ImageGallery.tsx` | ADAPT | Later Place Detail media migration. |
| `PlaceVideoGallery.tsx` | ADAPT | Display remains; recording entry eventually redirects into Wave 8 composer. |
| `VideoTemplateStrip.tsx` | KEEP/RELOCATE | Wave 8 composer ownership. |
| `BeatCueOverlay.tsx` | KEEP/RELOCATE | Wave 8 composer ownership. |
| `SectionHeader.tsx` | ADAPT | Shared section label but should consume typography/token primitives. |

---

## 5. Existing style/token system audit

Current source of truth: `frontend/src/constants/colors.ts`.

Existing exported groups:

- `Colors`: `primary`, dark surfaces, border, text, `textSecondary`, disabled-only `textMuted`, success/warning/error, catalog-tier colors.
- `Spacing`: `xs=4`, `sm=8`, `md=12`, `lg=16`, `xl=24`, `xxl=32`.
- `Radius`: `sm=8`, `md=12`, `card=14`, `pill=20`, `full=9999`.
- `Typography`: eight named roles from micro through display.
- `Shadows`: card/control/floating/sheet.

### Confirmed strengths

- Dark base `#0A0A0A` is already canonical.
- Secondary-text contrast was deliberately audited.
- Named typography now exists.
- Spacing/radius/shadow values are centralized.
- Current Search already respects 44pt on several controls after prior certification.

### Confirmed UI V2 gaps

1. **Color names are implementation names, not semantic presentation roles.** `primary` cannot express brand vs selection vs primary action independently, and later visual direction changed from the older cyan treatment toward warm orange/gold.
2. **Screens still use primitives directly.** `Text`, `TextInput`, `TouchableOpacity`, raw Expo `Image`, local `StyleSheet.create`, and raw values remain widespread.
3. **Raw typography remains in active files.** Example: Search still uses `fontSize: 15`, `12`, `13`, `17`, `11`, `10` locally despite the named scale existing.
4. **Raw spacing/radii remain in components.** Example: `PlaceCardCompact` uses gap `12`, padding `10`, radius `10`, etc.
5. **No semantic status-color layer.** Stale/uncertain/hard-constraint/destructive/positive are not modeled as explicit UI V2 meanings.
6. **No centralized motion token contract.** Reduced-motion intent exists in doctrine but not as a primitive-owned runtime contract.
7. **No production component gallery.** There is no `/dev/ui-v2` route rendering torture states.
8. **Search result presentation is one compact row family.** The approved V1.5 direction requires one food-forward top candidate plus at least two scannable alternatives, not a one-card tunnel or identical rows.
9. **Map selection and recommendation meaning are visually entangled.** UI V2 must make selection state distinct from recommendation/evidence state and redundant without color.
10. **Missing-media treatment is component-local.** There is no shared `CraveImage/FoodMedia` contract for missing/failed/hostile media.

---

## 6. Accessibility census

Existing good evidence:

- Search input/clear/filter/map actions include accessibility labels/roles.
- Selected scope chips expose `accessibilityState.selected`.
- Several certified Search controls meet 44pt.
- Place cards expose button roles and descriptive labels.
- `textSecondary` has an explicit contrast audit trail.

Foundation gaps to centralize:

- touch-target enforcement is not owned by one pressable/button primitive;
- text scaling/reflow behavior is mostly screen-dependent;
- Reduced Motion is doctrine, not yet a shared primitive behavior;
- image fallback + accessible labeling are inconsistent by component;
- map/list parity is a product contract but has no UI V2 component-level certification harness;
- color semantics need explicit non-color redundancy requirements.

These are **design/implementation requirements now**, not runtime-verified claims. Runtime proof happens after implementation.

---

## 7. Search/Map pilot migration map

### Preserve behavior/data ownership

- `frontend/src/screens/SearchScreen.tsx`
- `frontend/src/screens/MapScreenCore.tsx`
- `frontend/src/api/search.ts`
- `frontend/src/api/map.ts`
- `frontend/src/stores/discoveryContextStore.ts`
- `frontend/src/stores/recentSearchesStore.ts`
- `frontend/src/hooks/useLocation.ts`
- recommendation event logging utilities

### Add UI V2 foundation

Target new modules:

- `frontend/src/ui-v2/tokens/**`
- `frontend/src/ui-v2/primitives/**`
- `frontend/src/ui-v2/components/**`
- `frontend/src/ui-v2/fixtures/**`
- `frontend/app/dev/ui-v2.tsx` (development-only gallery route; hidden from production navigation)

### Search presentation target

- input/header → primitives + Search-specific composition
- interpretation → `InterpretationLine` + semantic constraint tokens
- top result → `PlaceResultHero`
- supporting results → `PlaceResultSupporting`
- evidence/uncertainty → `ReasonLine` / `ConfidenceStatement` / `EvidenceLimitation`
- zero/no-exact-match → `DecisionRecovery`
- save → `SaveAction`

### Map presentation target

- `MapMarker` presentation → `CraveMapPin`
- selected pin state distinct from recommendation state
- `MapBottomSheet` content → `MapPlaceCard`
- `Search this area` → shared button primitive
- location denied/unavailable → list-equivalent `DecisionRecovery`/area chooser

---

## 8. Legacy retirement rule

No existing component is deleted merely because a UI V2 replacement exists. Retirement requires all of:

1. every caller identified;
2. semantic parity mapped;
3. all callers migrated;
4. tests green;
5. UI Lab/visual QA green for replacement variants;
6. accessibility regression checks green;
7. zero remaining imports confirmed.

Until then old and new may coexist intentionally, with the migration matrix naming the owner.

---

## 9. UIV2-00 completion decision

**GREEN for proceeding to UIV2-01/02.**

The frontend route tree, shared component owners, current token system, Search/Map implementation owners, accessibility ownership gaps, and migration/retirement boundaries are now named. No production visual code was changed during the census.
