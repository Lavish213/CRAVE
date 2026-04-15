# CRAVE Frontend Design Spec
**Date:** 2026-04-15  
**Status:** Approved by product owner  
**Stack:** Expo 54 / React Native 0.81.5 / expo-router / Zustand / TypeScript

---

## 1. Mission

The frontend translates backend intelligence (scores + signals + menus + images) into user-felt trust, discovery, desire, and action. A new user must understand what CRAVE is doing in under 3 seconds. The app must feel curated, not cluttered — confident, not loud.

**Anti-pattern:** Do not make it feel like Yelp, Uber Eats, or a map with cards. Make it feel like "someone with taste put this in front of me."

---

## 2. Current State Summary (April 2026 Audit)

### What exists and works
- 4-tab navigation: Feed, Map, Search, Hitlist
- Feed: sectioned FlatList (CRAVE Pick/Gem/Solid/New), city selector, trending strip, pagination, skeleton, haptics
- Map: city-aware markers by tier, callout → detail nav
- Search: query submit → results list
- Hitlist: Zustand+AsyncStorage persist, add/remove
- Place detail: gallery, tier badge, trust badges, action buttons, menu section
- API layer: axios client with x-api-key, request-id
- Scoring utils: getTier(), getSignalContext(), getTrustBadges()

### Critical issues (must fix)
1. **Three independent tier color systems** out of sync (colors.ts, scoring.ts, map.tsx)
2. **Silent error swallowing everywhere** — empty `catch(() => {})` on every fetch
3. **Score thresholds duplicated** — buildFeedRows uses hardcoded literals instead of getTier()
4. **Android map callout broken** — onCalloutPress is iOS-only
5. **`userInterfaceStyle: "light"` in app.json** — clashes with dark UI
6. **Search + menu API calls bypass api module** — inconsistent abstraction
7. **No error/toast UI system** — users see blank screens on failure
8. **No request cancellation** — city switching causes race conditions

### Quality gaps to resolve
- PlaceCard, CitySelectorStrip, TrendingStrip are inlined in screen files — extract to src/components/
- NativeWind installed but unused — remove or adopt
- Dead color tokens in colors.ts (accent, tier*, success, warning, error)
- App.tsx dead file at root
- Hitlist empty state says "Tap the star" but UI shows bookmark icon
- via.placeholder.com fallback is external — replace with local asset
- sectionEmoji field in TIERS is always empty string

---

## 3. Global System Locks

### Tier vocabulary (immutable across all screens)
| Backend key | Display label | Color |
|---|---|---|
| `crave_pick` | CRAVE Pick | `#FF4D00` (orange-red) |
| `gem` | Hidden Gem | `#FFB800` (amber) |
| `solid` | Worth Knowing | `#4CAF50` (green) |
| `new` | Explore | `#666666` (gray) |

Single source: `src/utils/scoring.ts`. Map, Feed, Search, Detail all import from there. No inline re-declarations.

### Section subtext (locked copy)
- **CRAVE Picks:** "The strongest signals in the city"
- **Hidden Gems:** "Off the beaten path, locally loved"
- **Worth Knowing:** "Solid choices with real upside"
- **Explore:** "New to CRAVE or still emerging"

### Trust language (approved phrases)
**Positive:** Locally loved · Verified by blogs · Strong signal alignment · Hidden gem · Worth knowing · Full menu · Off the grid · Culturally validated  
**Emerging:** New to CRAVE · Still gaining signal · Worth a look  
**Caution:** Mixed signals · Still being understood · Signal variance · Approach with context

These phrases come from `getSignalContext()` and `getTrustBadges()` in scoring.ts. Never expose raw score numbers to users.

### City context
Selected city is global. Persists across app restarts (add persistence to cityStore). Affects Feed, Search, Map, Hitlist. Never hardcode a default city.

---

## 4. Design System

### Colors (dark theme, single source)
```
background:     #0A0A0A
surface:        #1A1A1A
surfaceElevated:#252525
border:         #2A2A2A
text:           #FFFFFF
textSecondary:  #888888
textMuted:      #555555
primary:        #FF3B30   (CRAVE brand red — UI chrome only)
tierCravePick:  #FF4D00
tierGem:        #FFB800
tierSolid:      #4CAF50
tierNew:        #666666
success:        #30D158
warning:        #FF9F0A
error:          #FF453A
```

Remove unused `accent`, `tierElite`, `tierTrusted`, `tierSolid`(old), `tierDefault` from colors.ts. Add the four canonical `tier*` names listed above.

### Typography hierarchy
- **Screen titles:** 28px, weight 900, letterSpacing 2
- **Card titles:** 17px, weight 700
- **Section labels:** 16px, weight 800, letterSpacing 0.3
- **Body/meta:** 13px, weight 500, color textSecondary
- **Trust line:** 12px, weight 600, tier color
- **Labels/caps:** 10px, weight 800, letterSpacing 1.5, textMuted

### Spacing
- Screen horizontal padding: 16px
- Card list gap: 10px
- Card body internal padding: 12px
- Generous vertical breathing room between sections

### Shapes
- Card border-radius: 14px
- Badges/pills: 6–8px radius
- Inputs: 12px radius
- Modals/sheets: 20px top radius

### Motion (subtle, never showy)
- Card press: activeOpacity 0.85
- Page transitions: default expo-router (slide)
- Image gallery paging: smooth horizontal scroll with dot indicator
- Save action: haptic feedback (notificationAsync Success/Warning)
- Skeleton shimmer: 1000ms loop
- Pull-to-refresh: native RefreshControl

### Accessibility (non-negotiable)
- All interactive elements: accessibilityLabel + accessibilityRole
- Touch targets minimum 44×44pt
- Tier badges: readable contrast (test white text on all tier colors)
- Image overlays: gradient ensures text readability

---

## 5. Component Architecture

### Extract to `src/components/`
```
src/components/
├── SkeletonCard.tsx         (exists, keep)
├── PlaceCard.tsx            (extract from index.tsx)
├── PlaceCardCompact.tsx     (new — for search results, map sheets)
├── SectionHeader.tsx        (extract from index.tsx)
├── CitySelectorStrip.tsx    (extract from index.tsx)
├── TrendingStrip.tsx        (extract from index.tsx)
├── TierBadge.tsx            (new — shared badge component)
├── TrustLine.tsx            (new — single-line signal summary)
├── TrustBadgeRow.tsx        (extract from place/[id].tsx)
├── ErrorState.tsx           (new — retry button + message)
├── EmptyState.tsx           (new — icon + title + body + CTA)
├── Toast.tsx                (new — ephemeral notification)
└── ImageGallery.tsx         (extract from place/[id].tsx, fix Android)
```

### New: `src/hooks/`
```
src/hooks/
├── usePlaces.ts             (feed pagination logic)
├── useSearch.ts             (search debounce + cancellation)
└── useToast.ts              (toast system)
```

### New: `src/api/` additions
```
src/api/
├── search.ts                (extract from search.tsx)
└── menu.ts                  (extract from place/[id].tsx)
```

---

## 6. Screen Specifications

### 6.1 Feed Screen
**File:** `app/(tabs)/index.tsx`

Structure (top → bottom):
1. App header: "CRAVE" title + selected city name
2. City selector strip (horizontal pills, persisted selection)
3. Trending strip (horizontal chips, tier-colored dot + name)
4. Sectioned FlatList:
   - SectionHeader (label + subtext + count)
   - PlaceCard rows

**PlaceCard anatomy:**
1. Hero image (190px height, expo-image, blurhash, cover fit, gradient overlay bottom)
2. Tier badge top-left (TierBadge component)
3. Save button top-right (bookmark icon, haptic)
4. Place name (17px bold)
5. Category · Price tier (13px secondary)
6. Trust line (12px, tier color, from getSignalContext)

**Error state:** ErrorState component with "Couldn't load places" + retry button  
**Empty state:** EmptyState with "Nothing here yet" + "Try another city" CTA  
**Loading:** SkeletonFeed for initial load only; bottom ActivityIndicator for pagination  

**Fixes vs current:**
- Use getTier() in buildFeedRows — no hardcoded thresholds
- Add error state and retry
- Add request cancellation ref for city-change race condition
- Add `sectionSubtext` to SectionHeader from TIERS constant
- Fix potential double-header with explicit headerShown:false

---

### 6.2 Place Detail Screen
**File:** `app/place/[id].tsx`

Structure (top → bottom):
1. Hero gallery (ImageGallery component, full-width, dot indicators)
2. Place identity block: name, TierBadge, category, city, price tier
3. Trust/signal summary row (TrustBadgeRow — horizontal scroll)
4. Summary sentence (1-line from getSignalContext)
5. Action row: Save | Website | Menu (if grubhub_url) | Directions
6. Menu section (grouped by category, 5 items preview → expand, or "No menu yet" fallback)
7. Optional: "Why CRAVE surfaced this" context block (v1: signal summary sentence)

**Action row buttons:** Each is a full-height tappable pill, icon + label, haptic on press  
**Directions:** `maps://` deep link using place lat/lng  
**Replace:** via.placeholder.com → local `assets/placeholder-food.png`  
**Fix:** Extract ImageGallery to component, fix Android nested scroll issue  

---

### 6.3 Search Screen
**File:** `app/(tabs)/search.tsx`

Structure:
1. Search input bar (prominent, with search icon, clear button)
2. City context label beneath input ("Searching in Oakland")
3. Quick filter chips (optional v1: cuisine categories from city)
4. Results: PlaceCardCompact list (image thumbnail, name, category, TierBadge, TrustLine)
5. Empty query state: show trending places for selected city
6. No results state: EmptyState with helpful message + CTA
7. Error state: ErrorState with retry

**Behavior:**
- Debounced live search (300ms) OR explicit submit (keep the button)
- Search is always city-scoped (passes city_id)
- Move API call to `src/api/search.ts`
- Add request cancellation on new query

---

### 6.4 Map Screen
**File:** `app/(tabs)/map.tsx`

Structure:
1. MapView (mutedStandard, city-aware, fallback to selectedCity.lat/lng)
2. Custom marker component per tier (colored dot, not pinColor string)
3. Bottom sheet on pin tap: PlaceCardCompact + "Open" CTA
4. City selector strip at top (same component as Feed)
5. Tier legend bottom-left

**Fixes:**
- Replace `onCalloutPress` (iOS-only) with custom bottom sheet on marker press
- Replace `pinColor` hex string with `<Marker>` containing a custom `<View>` colored dot
- Import TIER_COLORS from scoring.ts — remove inline TIER_COLORS/TIER_LABELS in map.tsx
- Add city selector (currently missing — user can't switch city from Map tab)

---

### 6.5 Hitlist Screen
**File:** `app/(tabs)/hitlist.tsx`

Structure:
1. Saved Places section: list of PlaceCardCompact with remove button
2. Craves section: imported items (matched + unmatched) — v1: show if CraveItem data available from API, else omit section
3. Empty state: "Save places you want to remember" + "Browse the feed" CTA

**Fixes:**
- Fix copy: "Tap the bookmark icon on any place" (not "Tap the star")
- Remove setTimeout hack in handleRefresh — make it a true no-op or call real refresh logic
- Persist selected city to AsyncStorage in cityStore so it survives app restart

---

### 6.6 Error/Toast System (new)
**Files:** `src/components/Toast.tsx`, `src/hooks/useToast.ts`

- Global toast provider in `app/_layout.tsx`
- Ephemeral message (3s auto-dismiss) for: save success, unsave, network error, share confirmed
- Style: bottom of screen, above tab bar, dark pill with text
- Haptic on show (Light)

---

## 7. State Management Additions

### cityStore — add persistence
```ts
persist(cityStore, { name: 'crave-city', storage: AsyncStorage })
```
Selected city survives app restart.

### toastStore (new)
```ts
{ message: string | null, show(msg): void, hide(): void }
```
Used by all screens via useToast hook.

---

## 8. API Layer Completions

Add to `src/api/`:
- `search.ts`: `searchPlaces({ q, city_id, limit })` → `PlaceOut[]`
- `menu.ts`: `getPlaceMenu(placeId)` → `MenuItem[]`

Both follow same axios client pattern with error handling.

---

## 9. app.json Fixes

- `userInterfaceStyle`: `"dark"` (not `"light"`)
- Splash background: `#0A0A0A` (not `#ffffff`)
- `backgroundColor` in android config: `#0A0A0A`

---

## 10. Build Order (Phases)

### Phase 1 — Foundation + Trust Clarity
1. Unify tier color/vocabulary system (scoring.ts → single source)
2. Fix app.json (dark theme, splash)
3. Remove dead color tokens, clean colors.ts
4. Extract components: PlaceCard, SectionHeader, CitySelectorStrip, TrendingStrip, TierBadge, TrustLine
5. Add ErrorState and EmptyState components
6. Add Toast system
7. Add `src/api/search.ts` and `src/api/menu.ts`
8. Add cityStore persistence
9. Fix buildFeedRows to use getTier()
10. Fix Feed error state + request cancellation

### Phase 2 — Interaction Polish
1. Polish Feed: section subtext, improved section headers
2. Polish PlaceCard: gradient overlay on image, refined spacing
3. Polish Detail: extract ImageGallery (fix Android), replace placeholder, add directions button
4. Polish Hitlist: fix copy, real empty state, Craves section stub
5. Polish Search: city context label, debounce, clear button, trending empty state
6. Loading states: verify skeletons match real card shapes on all screens

### Phase 3 — Map + Search Consistency
1. Custom map markers (View-based, not pinColor)
2. Fix Android callout (bottom sheet approach)
3. Add city selector to Map tab
4. Import tier colors from scoring.ts in map.tsx
5. Remove duplicate TIER_COLORS/TIER_LABELS from map.tsx
6. Search: add quick filter chips (category)

### Phase 4 — Crave Loop
1. Hitlist Craves section: fetch pending CraveItems from API, show matched/unmatched
2. Share-to-CRAVE UX: Toast feedback on save, pending indicator for unmatched
3. Final polish pass: spacing, typography, press states, transition smoothness

---

## 11. Out of Scope (v1)
- User auth / accounts
- Backend hitlist sync (stays device-local for v1)
- Advanced filters (neighborhood, distance, date)
- Social features
- Personalization / recommendation engine UI
- Settings screen
- Onboarding flow (app opens to Feed, city auto-selected from API)
- NativeWind adoption (remove from package.json)
- Map clustering (defer until city counts justify it)

---

## 12. Acceptance Criteria

App is frontend-complete when:
- [ ] New user opens app → immediately understands what CRAVE is showing and why
- [ ] CRAVE Picks feel premium and editorial at top of Feed
- [ ] Hidden Gems feel special and intriguing — not generic
- [ ] Detail pages make users want to visit the place
- [ ] Saving feels satisfying (haptic, visual confirmation)
- [ ] No blank screens on network failure — always an error state with retry
- [ ] Map markers are colored by tier and tappable on Android and iOS
- [ ] Search results look as good as Feed cards — not generic list items
- [ ] Hitlist has correct copy, correct icon, and working empty state
- [ ] All screens respect selected city — no hardcoded values
- [ ] Tier vocabulary is 100% consistent: Feed, Search, Map, Detail use identical labels and colors
- [ ] App opens with dark UI chrome on both platforms (status bar, keyboard, system elements)
