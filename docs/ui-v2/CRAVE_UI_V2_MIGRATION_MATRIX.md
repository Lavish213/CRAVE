# CRAVE UI V2 Migration Matrix

**Status:** active execution map
**Base:** UIV2-00 census + UIV2-01 semantics + UIV2-02 tokens

## 1. Foundation phases

| Phase | Deliverable | Status | Production code allowed? |
|---|---|---|---|
| UIV2-00 | Repository census | COMPLETE | No |
| UIV2-01 | Semantic contract | COMPLETE | No |
| UIV2-02 | Token contract | COMPLETE | No |
| UIV2-03 | Primitives | NEXT | Yes, foundation-only |
| UIV2-04 | Product components | PENDING | Yes after primitives green |
| UIV2-05 | UI Lab | PENDING | Yes after component contracts exist |
| UIV2-06 | Search/Map pilot | PENDING | Yes after UI Lab can render pilot components |
| UIV2-07 | Automated/runtime certification | PENDING | Verification, not design exploration |

## 2. Foundation target files

### New UI V2 namespace

- `frontend/src/ui-v2/tokens/index.ts`
- `frontend/src/ui-v2/primitives/CraveText.tsx`
- `frontend/src/ui-v2/primitives/CravePressable.tsx`
- `frontend/src/ui-v2/primitives/CraveButton.tsx`
- `frontend/src/ui-v2/primitives/CraveIconButton.tsx`
- `frontend/src/ui-v2/primitives/CraveSurface.tsx`
- `frontend/src/ui-v2/primitives/CraveImage.tsx`
- `frontend/src/ui-v2/primitives/CraveInput.tsx`
- `frontend/src/ui-v2/primitives/CraveToast.tsx`
- `frontend/src/ui-v2/primitives/CraveSheet.tsx`
- `frontend/src/ui-v2/primitives/CraveSkeleton.tsx`
- `frontend/src/ui-v2/primitives/index.ts`

### Product components

- `frontend/src/ui-v2/components/FoodMedia.tsx`
- `frontend/src/ui-v2/components/PlaceIdentityFallback.tsx`
- `frontend/src/ui-v2/components/ReasonLine.tsx`
- `frontend/src/ui-v2/components/ConstraintToken.tsx`
- `frontend/src/ui-v2/components/OperationalStatus.tsx`
- `frontend/src/ui-v2/components/ConfidenceStatement.tsx`
- `frontend/src/ui-v2/components/EvidenceLimitation.tsx`
- `frontend/src/ui-v2/components/InterpretationLine.tsx`
- `frontend/src/ui-v2/components/PlaceResultHero.tsx`
- `frontend/src/ui-v2/components/PlaceResultSupporting.tsx`
- `frontend/src/ui-v2/components/CraveMapPin.tsx`
- `frontend/src/ui-v2/components/MapPlaceCard.tsx`
- `frontend/src/ui-v2/components/DecisionRecovery.tsx`
- `frontend/src/ui-v2/components/SaveAction.tsx`
- `frontend/src/ui-v2/components/index.ts`

### Fixtures/UI Lab

- `frontend/src/ui-v2/fixtures/searchMapFixtures.ts`
- `frontend/app/dev/ui-v2.tsx`

## 3. Existing files allowed to change during Search/Map pilot

Only after UIV2-03/04/05 foundations compile/test:

- `frontend/src/screens/SearchScreen.tsx`
- `frontend/src/screens/MapScreenCore.tsx`
- `frontend/src/components/MapBottomSheet.tsx` only if needed to compose `MapPlaceCard`
- `frontend/src/components/MapMarker.tsx` only as compatibility adapter/retirement bridge
- `frontend/src/components/PlaceCardCompact.tsx` only if needed for compatibility or import migration, not to redesign other surfaces
- `frontend/src/components/FilterSheet.tsx` only to consume shared primitives/tokens without changing constraint semantics
- `frontend/src/constants/colors.ts` only for compatibility exports if necessary; UI V2 should prefer its own namespace
- relevant tests under `frontend/__tests__`, `frontend/src/**/*.test.tsx`

## 4. Files explicitly excluded from Search/Map pilot

- Feed implementation
- Craves implementation
- Rank implementation
- Place Detail hierarchy
- Posting/Wave 8 routes
- Profile/Taste implementation
- backend ranking/data changes
- social feed/leaderboard disposition

A Search/Map UI V2 PR must not opportunistically restyle these.

## 5. Legacy → target mapping

| Legacy owner/pattern | UI V2 target | Retirement condition |
|---|---|---|
| direct `Text` styling in Search/Map | `CraveText` | no pilot-screen direct typography styling remains except platform-required cases |
| `TouchableOpacity` search controls | `CravePressable` / Button / IconButton | accessibility and press feedback parity proven |
| direct `TextInput` Search styling | `CraveInput` | keyboard/submit/clear/a11y parity proven |
| direct image/fallback in result cards | `FoodMedia` / `CraveImage` | hostile media fixtures pass |
| `PlaceCardCompact` as every Search row | `PlaceResultHero` + `PlaceResultSupporting` | Search result hierarchy meets SM-03 contract |
| local interpretation chips | `ConstraintToken` | hard/preferred semantics explicit |
| local stale/uncertain copy | `OperationalStatus` / `EvidenceLimitation` | state-specific tests pass |
| `MapMarkerDot` visual owner | `CraveMapPin` | bounded pin + selected-state + a11y parity proven |
| Map sheet bespoke card content | `MapPlaceCard` | exact candidate, Save/Directions, Place Detail transition preserved |
| local empty/result recovery | `DecisionRecovery` | SM-05/06/10/11 state tests pass |
| existing singleton `Toast` | `CraveToast` adapter/API | no second toast host exists |
| legacy shadow/color imports | semantic tokens | migrated pilot files contain no raw hex and no new arbitrary styling values |

## 6. Search pilot state coverage

Must cover:

- SM-01 Search Home
- SM-02 Input Active
- SM-03 Results
- SM-05 Required Constraint Zero Result
- SM-06 Preferred Constraint No Exact Match
- SM-07 Personalization Low Confidence
- SM-08 Missing Media
- SM-09 Closed Place
- SM-12 Long Restaurant Name
- SM-13 Stale Hours
- SM-14 Filter Editing
- SM-15 Save Confirmation
- SM-16 Native Share Transition is system-owned; CRAVE verifies the transition action rather than drawing a fake share screen.

Search results specifically require:

- context/query + result count + constraints;
- one food-forward top candidate;
- at least two scannable alternatives when available;
- bounded Show More;
- no star averages;
- explicit uncertainty/limitations;
- no silent constraint relaxation.

## 7. Map pilot state coverage

Must cover:

- SM-04 Map
- SM-10 Location Permission Denied
- SM-11 Location Unavailable
- bounded pins;
- selected pin distinct from recommendation meaning;
- exact Search candidate-set parity in Search handoff mode;
- explicit `Search this area` refresh;
- no auto-rerun on pan;
- list-equivalent location fallback;
- partial Place Detail sheet/card handoff.

## 8. Certification gates

### Automated

- `cd frontend && npx tsc --noEmit`
- `cd frontend && npx jest --ci`
- repository conflict-marker guard
- required GitHub CI / CodeQL

### UI Lab visual/resilience

- good photo
- weak photo
- very dark photo
- overexposed photo
- portrait crop
- no photo
- failed photo
- long restaurant name
- long reason
- missing price
- stale hours
- low personalization confidence
- closed
- protected-constraint zero result
- preferred no-exact-match
- location denied/unavailable
- large-text fixture

### Runtime proof after implementation

- actual VoiceOver traversal
- actual Dynamic Type/reflow
- actual touch-target measurement
- actual Reduce Motion behavior
- actual photo/data fixtures through production components
- actual Map/list parity on device/simulator

Until runtime proof exists, docs say **requirement**, not **verified**.

## 9. Propagation after Search/Map certification

Only after pilot passes:

`Place Detail → Feed → Craves → Rank → Posting → Profile → Taste → Other Profile → Activity → Cold Start/Auth → Settings → legacy retirement`.

Search/Map is the reference implementation, not a special one-off theme.
