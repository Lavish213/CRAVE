# CRAVE — Nuke Audit & Master Refix

**Date:** 2026-09-14
**Status:** CANONICAL PRODUCT-RECOVERY LEDGER
**Release posture:** NOT READY
**Consumer-product grade at audit start:** 3.0/10
**Engineering/test-infrastructure grade at audit start:** 7.5/10
**Required release grade:** >= 9.0/10 overall, no critical lane below 8.5/10

This file exists because the current application can be technically robust while still failing as a consumer food product. Passing unit tests, clean TypeScript, working routes, and well-defended state machines are not sufficient evidence that CRAVE is useful, rich, trustworthy, discoverable, or release-ready.

From this point forward, release readiness is judged from the outside in: what a real user sees, what data actually exists, whether the primary journeys work on a real device, and whether every visible promise is backed by production data and a production-proven path.

---

## 1. Executive diagnosis

The current app is not failing because nothing was built. It is failing because substantial engineering exists behind a weak visible product layer and a severely under-enriched dataset.

The dominant failure pattern is:

**BUILT -> HIDDEN / BURIED / DATA-STARVED / NOT PRODUCTION-PROVEN**

The screenshots expose five severe disconnects:

1. A sophisticated map implementation exists, but the Map tab is explicitly hidden with `href: null`.
2. Image rendering exists, but production primary-image coverage is only 36.55%, so placeholder-heavy surfaces are structurally guaranteed.
3. Menu systems exist, but only 2.66% of active places have menu coverage.
4. Photo/video contribution systems exist, but their entry points are weak, unlabeled, buried, or depend on auth paths that are not release-proven.
5. The app claims personalization and taste intelligence in the interface while the canonical status document admits there is no learned taste model yet.

The result is a product that feels empty even though the repository is large.

---

## 2. Screenshot-forensic audit

### 2.1 OAuth/browser failure

Observed:

`400 validation_failed: Unsupported provider: provider is not enabled`

Classification: **BUILT BUT CONFIGURATION MISSING** and **RELEASE-GATE FAILURE**.

The frontend always renders Apple and Google OAuth buttons and invokes Supabase OAuth for either provider. There is no runtime capability contract preventing the UI from advertising a provider that the deployed Supabase project has not enabled.

Required fix:

- Add an explicit auth-capability source of truth.
- Never render an OAuth option that is not configured and verified.
- Add a pre-release auth-provider smoke test against the deployment environment.
- Verify deep-link redirect behavior on a real iPhone build.
- Email auth must remain a functioning fallback.
- A visible provider button returning a Supabase validation error is a ship blocker.

### 2.2 Profile screenshot

Observed:

- Two ranked places.
- Sparse summary.
- Most of the screen has no useful content.
- The product asks the user to rank thirteen more places before CRAVE can meaningfully explain their taste.

Classification: **BUILT BUT COLD-START STARVED**.

Required fix:

- Compress the cold-start path dramatically.
- Seed taste through fast preference capture, cuisine/occasion choices, imported saves/history where permitted, and lightweight pairwise choices.
- Never use a large empty canvas to communicate that the product does not know the user yet.
- Profile must show useful identity, activity, saves, collections, contribution stats, taste signals, and recent behavior even before the long-term taste model matures.

### 2.3 Rank screenshot

Observed:

- One visible ranked place.
- Huge dead area.
- Ranking is treated as a destination even when there is almost nothing to manage.

Classification: **BUILT BUT LOW-SIGNAL / BAD EMPTY-STATE PRODUCT DESIGN**.

Required fix:

- Rank should have an active next action when signal volume is low.
- Surface fast comparisons and an explicit progress/reward loop.
- Do not reserve a primary tab for a screen that can be nearly empty for new users unless it immediately creates value.
- Re-evaluate whether Rank deserves permanent primary navigation versus being a high-value mode inside Profile/Discover.

### 2.4 Taste Profile screenshot

Observed:

- `2 ranked`.
- `Still learning`.
- 1 loved, 0 fine, 1 disliked.
- Top city is based on one ranked place.

Classification: **BUILT BUT STATISTICALLY THIN**.

Required fix:

- Suppress faux precision.
- Use confidence bands and minimum evidence thresholds.
- Do not imply a stable city/taste inference from one or two events.
- Show what CRAVE knows, what it does not know, and the fastest action that improves the model.

### 2.5 Craves screenshot

Observed:

- Three saves.
- Repeated restaurants across recommendation and saved sections.
- Multiple image placeholders.
- Weak organization.
- No map context.
- No collection/trip/date-night structure.
- Weak resurfacing value.

Classification: **BUILT BUT DATA-STARVED + PRODUCT-THIN**.

Required fix:

Craves becomes the user's food memory system, not a flat bookmark list:

- Map/list toggle.
- Collections.
- Tags.
- Tried/want-to-try state.
- Personal note.
- Favorite dishes.
- Contextual resurfacing.
- Nearby saved places.
- Share/import flow.
- Rich cards with real imagery.
- No duplicates between recommendation bands and saved results without a deliberate reason.

### 2.6 Search screenshot

Observed:

- Search field.
- Quick-lunch chip.
- City chips.
- Massive blank area.
- No map.
- No nearby visual discovery.

Classification: **BUILT BUT WRONG INFORMATION ARCHITECTURE**.

The repository contains a real map screen, clustering, saved/search modes, user location, filters and bottom-sheet behavior. The tab layout then hides that map with `href: null`. Search only hands off to Map after results exist.

This is the single clearest implementation/product disconnect in the current app.

Required fix:

- Map becomes first-class discovery again.
- Search and Map must be designed as one discovery system, not a hidden secondary route.
- A zero-query state should immediately show useful nearby discovery, recent searches, saved nearby places, trending/occasion shortcuts and map context.
- Blank space is not an acceptable zero state.

---

## 3. Verified production-data reality

Canonical status reports:

- Active places: **37,761**
- Any public image: **15,313 / 40.55%**
- Primary image: **13,802 / 36.55%**
- Menu coverage: **1,005 / 2.66%**
- Known website: **14,133 / 37.43%**
- Website-backed but no menu: **13,128**
- Website-backed but no public image: **7,816**

This means the visual product cannot become good through component polish alone.

### Release consequence

A city is not eligible for consumer launch merely because places exist in the database.

A launchable city must pass a **City Readiness Gate** containing at least:

- active place count
- primary image coverage
- menu/dish coverage
- hours coverage
- coordinates coverage
- website coverage
- phone coverage
- duplicate/stale-place rate
- category/cuisine coverage
- high-confidence top-place coverage
- sample manual QA

No city with widespread blank cards may be called ready.

---

## 4. System-by-system classification

| System | Classification | Current diagnosis | Release posture |
|---|---|---|---|
| Feed | BUILT BUT PRODUCT-THIN | technically functional, weak visual/content density | BLOCKED |
| Map | BUILT BUT HIDDEN | substantial implementation, hidden from tab bar | BLOCKED |
| Search | BUILT BUT WRONG ZERO STATE | results work; zero state wastes screen | BLOCKED |
| Place Detail | BUILT BUT BELOW QUALITY BAR | prior internal score 77/100 confirmed | BLOCKED |
| Craves | BUILT BUT PRODUCT-THIN | saves work, memory/resurfacing weak | BLOCKED |
| Rank | BUILT BUT COLD-START STARVED | sparse until user has signal volume | BLOCKED |
| Taste Profile | BUILT BUT LOW-CONFIDENCE | interface outruns evidence/model maturity | BLOCKED |
| Photos | BUILT BUT DATA-STARVED | render/upload pipeline exists; coverage poor | BLOCKED |
| Menus | BUILT BUT DATA-STARVED | pipeline exists; 2.66% coverage | BLOCKED |
| Video | BUILT BUT BURIED / NOT DEVICE-PROVEN | backend pipeline strong; production camera/R2 path not fully proven | BLOCKED |
| Social | PARTIALLY BUILT | friends/public profile surfaces exist; not core visible value yet | NEEDS PRODUCT PASS |
| Auth | BUILT BUT MISCONFIGURED | disabled OAuth provider exposed to user | BLOCKED |
| Scheduler | BUILT BUT PARTIALLY ENABLED | safe/local jobs live; enrichment jobs intentionally disabled | BLOCKED FOR DATA QUALITY |
| Image enrichment | BUILT BUT DISABLED/LOW COVERAGE | Google job exists; rollout/budget/safety unresolved | BLOCKED |
| Menu enrichment | BUILT BUT DISABLED/LOW COVERAGE | backlog tooling exists; production rollout constrained | BLOCKED |
| Discovery/population | BUILT BUT CONTROLLED | OSM/Overture jobs exist; broader rollout disabled | NEEDS CITY GATES |
| Personalization | NOT BUILT AS LEARNED MODEL | explicit canonical gap | PRODUCT GAP |
| E2E | PARTIAL | 3 web journeys; authenticated save journey skipped | BLOCKED |
| Native physical QA | PARTIAL | simulator evidence exists, full real-device matrix does not | BLOCKED |
| Crash/observability | BUILT BUT CONFIG-DEPENDENT | Sentry no-op if DSN absent | VERIFY |

---

## 5. Why the app feels worse than the codebase

### Root cause A — engineering completeness was mistaken for product completeness

The repository optimized heavily for:

- state correctness
- race protection
- idempotency
- backend invariants
- worker safety
- test counts
- ranking/scoring mechanics
- scheduler safety
- deployment correctness

Those are valuable, but the visible product still depends on data and interaction quality.

### Root cause B — production enrichment is below the UI's assumptions

Cards were designed as if artwork/menu information would usually exist. Production data says otherwise.

A card with a correct fallback placeholder is still a bad consumer experience when placeholders dominate the product.

### Root cause C — key features were built but deliberately hidden or buried

Examples:

- Map route exists but is hidden from the tab bar.
- Video/photo capture is behind an unlabeled global `+` and deeper contribution flow.
- Video playback remains Place-Detail-only.
- Map handoff appears after search results instead of making map discovery foundational.

### Root cause D — cold start is too expensive

The user must produce too much ranking history before the product feels intelligent.

### Root cause E — test strategy overweights implementation invariants

The suite can be green while:

- OAuth providers are disabled in the real Supabase project.
- images are missing in production
- menus are absent
- Search is mostly empty before a query
- Rank has almost no content
- Map is invisible in primary navigation

These are not contradictions. They are missing release tests.

---

## 6. Invisible gaps that must now be treated as first-class defects

1. **Data-readiness gap:** no hard city-level image/menu richness gate before shipping a market.
2. **Navigation gap:** implementation existence was counted as feature availability even when `href: null` hides the feature.
3. **Capability gap:** auth buttons are not driven by deployed provider capabilities.
4. **Cold-start gap:** no short path from zero behavior to useful personalization.
5. **Contribution-discoverability gap:** upload capability exists without obvious user education or contextual entry.
6. **Media-provenance gap:** coverage percentage and freshness are not surfaced as release health.
7. **Content-repetition gap:** recommendation and saved surfaces can recycle the same tiny set of places.
8. **Confidence gap:** UI copy can sound more certain than the evidence supports.
9. **E2E gap:** web smoke tests do not verify native map, camera, media permissions, OAuth, push, or R2 upload behavior.
10. **Operational gap:** enrichment workers being intentionally disabled is compatible with green API tests but incompatible with a rich consumer catalog.
11. **Observability gap:** Sentry is configuration-dependent and therefore must be verified, not assumed.
12. **Scheduler architecture gap:** defaults still allow embedded CPU-heavy jobs; production topology has moved toward a standalone worker and must be validated as an invariant.
13. **Empty-state gap:** too many screens express missing data as unused space rather than a high-value next action.
14. **Place-page utility gap:** a restaurant product needs trustworthy hours, location, directions, call/site/reservation/menu/media at decision time.
15. **Social-proof gap:** rankings are stronger when grounded in people, visits, notes, dishes and visible evidence rather than abstract tiers alone.
16. **Release-evidence gap:** test-count summaries became a proxy for readiness despite known unverified device flows.

---

## 7. Competitor benchmark — what CRAVE is currently missing

### Beli

Beli makes three promises immediately legible: track restaurants, share with friends, discover personalized recommendations. Its product also centers ranked lists/maps, a friend feed, tags, notes, favorite dishes, taste profile and friend match score.

CRAVE lesson:

- Ranking must feed discovery and identity.
- Maps/lists must be central, not hidden.
- Friend activity needs to make the catalog feel alive.
- Favorite dishes and notes provide human texture missing from abstract scores.

### Google Maps

Google Maps makes Explore, saved places and contribution first-class. Restaurant place pages expose photos, menu/dish detail and reviews close to core decision utility.

CRAVE lesson:

- Map is infrastructure for discovery, not a secondary visualization.
- Menu/dish/media contribution must be obvious where the user is already looking.
- A place page without rich evidence feels unfinished.

### Mapstr

Mapstr treats the map as the user's memory: saved places, tags, tried/to-try states, notes/photos, filters, list/map switching, friend maps and imports from social/web/Google Maps.

CRAVE lesson:

- Craves should become a map-backed personal food memory system.
- Imports and organization reduce cold-start pain dramatically.
- Contextual retrieval is as important as saving.

### OpenTable / reservation-class products

High-value restaurant pages put practical decision information, photos, menu and a strong action front and center.

CRAVE lesson:

- Discovery must terminate in action.
- Every Place Detail should answer: what is it, why go, what should I order, is it open, where is it, and what can I do now?

CRAVE should not clone these apps. It should combine their strongest product truths around CRAVE's own decision-intelligence identity.

---

## 8. P0 master refix — no new feature work before these close

### P0.1 Rebuild information architecture around discovery

Owner files/systems:

- `frontend/app/(tabs)/_layout.tsx`
- `frontend/app/(tabs)/map.tsx`
- `frontend/src/screens/MapScreenCore.tsx`
- `frontend/src/screens/SearchScreen.tsx`

Acceptance:

- Map is discoverable in one tap from primary discovery navigation.
- Search and map share state bidirectionally.
- Zero-query search is useful.
- Nearby discovery never becomes a blank page.
- Saved/search/filter map modes work on device.

### P0.2 Auth capability and production smoke gate

Owner:

- `frontend/src/components/AuthSheet.tsx`
- `frontend/src/stores/authStore.ts`
- Supabase project configuration
- E2E release suite

Acceptance:

- Every visible OAuth provider succeeds in the deployment environment.
- Disabled providers are not rendered.
- Redirect-to-app works on real iOS and Android builds.
- Email fallback works.
- Auth failure never dumps raw provider JSON into the user experience.

### P0.3 Catalog richness program

Owner:

- `backend/app/scheduler.py`
- `backend/app/scheduler_worker.py`
- image worker/services
- menu worker/services
- website extraction services
- place/media tables
- city readiness reporting

Acceptance:

- Explicit market thresholds are defined and measured.
- High-value launch cities achieve target image/menu/action-data coverage.
- Paid provider use has caps, attribution/licensing compliance and cost telemetry.
- Broken/stale photos are automatically detected and repaired or removed.
- Menu freshness/provenance is tracked.

### P0.4 Feed product rebuild

Owner:

- `frontend/app/(tabs)/index.tsx`
- `frontend/src/components/PlaceCard.tsx`
- feed API/recommendation assembly

Required card/content vocabulary:

- high-quality image/media
- title + category/cuisine
- distance/location
- open/closed signal where trustworthy
- price
- social/taste evidence
- dish/menu hook where available
- save state
- clear reason for recommendation
- action path to Place Detail/map

Acceptance:

- No placeholder-heavy launch feed.
- No fake personalized language where personalization does not exist.
- Feed has a real hierarchy, visual rhythm and differentiated modules.
- A user can make a restaurant decision from the feed/detail pair.

### P0.5 Place Detail 9/10 rebuild

Owner:

- `frontend/app/place/[id].tsx`
- gallery/menu/video components
- place detail API

Acceptance:

- hero imagery or intentional evidence fallback
- identity
- CRAVE recommendation reason with confidence
- hours/open state
- address/map/directions
- phone/site/reservation when available
- menu/dishes
- image gallery
- video where available
- save/rank/visited/note/contribute actions
- source/provenance handling
- loading/error/offline states
- >= 90/100 against the product rubric and verified by screenshots/device

### P0.6 Craves becomes memory + planning

Owner:

- `frontend/app/(tabs)/craves.tsx`
- saves API
- map saved mode

Acceptance:

- map/list toggle
- collections/tags
- tried/want-to-try
- notes
- nearby resurfacing
- sort/filter
- sharing/import foundation
- no duplicate/noise-heavy recommendation blocks

### P0.7 Contribution becomes obvious and trustworthy

Owner:

- `frontend/app/(tabs)/_layout.tsx`
- `frontend/app/food-evidence.tsx`
- `frontend/app/add-spot.tsx`
- photo/video upload hooks/APIs
- Place Detail contribution actions

Acceptance:

- Global `+` has understandable purpose.
- Photo, menu and video contribution are discoverable contextually.
- Capture draft survives interruptions.
- Upload progress/status/moderation result are visible.
- Real iPhone camera -> R2 -> worker -> moderation -> place page is proven.

### P0.8 Cold-start redesign

Acceptance:

A new user receives useful discovery before having a mature taste model. Within minutes they can establish meaningful signal through a combination of:

- city/location
- cuisine/occasion preferences
- save imports
- known favorites
- fast comparisons
- exclusions/dietary constraints

No screen should ask for 13 more interactions before becoming useful.

### P0.9 Release-test redesign

Add release journeys for:

- signed-out first launch
- sign-up/sign-in
- OAuth per visible provider
- Feed -> Detail
- Search -> Map -> Detail
- Map pan/filter -> Detail
- Save -> Craves -> Map -> Detail
- Rank -> Taste Profile
- photo capture/upload
- menu contribution
- video capture/upload/playback
- network loss/recovery
- permissions denied/granted
- empty city
- data-rich city
- stale/broken image
- missing menu
- provider failure
- app cold start

Unit test counts cannot close these gates.

---

## 9. P1 after P0 is green

1. Learned personalization using real outcome data.
2. Friend-based discovery and visible social proof.
3. Favorite-dish model and dish-level discovery.
4. Collection sharing/collaboration.
5. Import from external saved-place sources where technically and legally supported.
6. Occasion-aware discovery.
7. Reservation/action integrations.
8. Better typo tolerance and semantic/intent search.
9. Location-aware resurfacing of saved places.
10. Contribution reputation/quality system.

---

## 10. P2 — only after the product feels alive

- advanced group decision intelligence
- deeper creator/influencer layers
- sophisticated notification prediction
- richer media editing
- experimental recommendation explanations

Do not hide weak fundamentals under more intelligence features.

---

## 11. File/system audit map

Every file is to be audited under one of these lanes. A lane is not closed because its files compile; it closes when the user journey it supports passes its acceptance tests.

### Frontend routing/navigation

- `frontend/app/**`
- tab/root layouts
- deep links
- auth-gated routes
- back behavior
- modal/overlay behavior

### Frontend screens

- Feed
- Search
- Map
- Craves
- Rank
- Profile/Taste Profile
- Place Detail
- activity/social
- add-spot/contribution
- uploads/video
- settings/legal/onboarding

### Frontend shared components

Audit every component for:

- data source
- empty/error/loading behavior
- image fallback
- accessibility
- touch target
- navigation action
- stale response/race safety
- analytics event
- visual consistency

### Frontend API/data layer

Audit every API module for:

- endpoint ownership
- auth requirements
- response normalization
- abort/stale handling
- pagination
- retry policy
- offline behavior
- schema drift
- null/partial data behavior

### Frontend state

Audit stores for:

- ownership
- persistence
- account scoping
- sign-out clearing
- optimistic update rollback
- idempotency
- cross-screen synchronization

### Backend API routes

Audit every route for:

- auth
- validation
- response contract
- pagination
- failure semantics
- query performance
- data completeness
- source/provenance exposure
- test coverage

### Backend models/migrations

Audit:

- nullable fields versus UI assumptions
- indexes
- uniqueness/entity identity
- stale/inactive semantics
- media/menu provenance
- moderation states
- user data ownership

### Discovery/population

Audit OSM, Overture and any paid-source ingestion for entity matching, duplication, stale businesses, geographical correctness, licensing and source provenance.

### Image pipeline

Audit end-to-end:

source -> candidate -> fetch -> validation -> classification/moderation -> storage -> primary election -> API -> normalization -> card/gallery -> stale refresh.

### Menu pipeline

Audit end-to-end:

website/provider -> extraction -> validation -> normalization -> dedupe -> provenance -> menu/dish DB -> API -> UI -> freshness/recheck.

### Video pipeline

Audit end-to-end:

camera/library -> durable local draft -> request slot -> upload -> confirm -> queue -> ffmpeg -> classifier -> moderation -> thumbnail -> API -> Place Detail -> playback.

### Scheduler/ops

Audit:

- actual production allowlist
- embedded scheduler disabled on web when standalone worker is active
- job duration
- concurrency
- cost budgets
- retries
- dead-letter/stuck states
- backlog age
- alerts
- job-run visibility

### Auth/security

Audit:

- Supabase provider configuration
- redirect allowlist
- token validation
- account deletion
- sign-out cleanup
- API key role
- client-visible configuration
- secrets
- RLS/authorization assumptions

### QA/release

Audit CI plus native release evidence separately. A test is only accepted as proof for the behavior it actually exercises.

---

## 12. Current scheduler contradiction to close

The code supports a large scheduler job set including image ingestion and menu enrichment. Production status says the standalone worker currently allowlists only four safe/local jobs and that paid image ingestion, menu enrichment, discovery/population, score recompute and ranking are disabled.

This is intentional operational caution, but it explains the product starvation.

The fix is not to switch everything on blindly.

The fix is:

1. inventory backlog
2. canary one source/city
3. measure quality and cost
4. repair extraction/source issues
5. define promotion thresholds
6. enable bounded batches
7. observe error/cost/quality
8. expand city by city

---

## 13. Brutal release gates

CRAVE cannot be called 9/10 until all are true:

### Product

- Map is first-class and tested.
- Feed is visually rich and useful for a new account.
- Search zero state is useful.
- Craves is a real memory/planning product.
- Place Detail is >= 9/10 on a device.
- Upload contribution is discoverable.
- No visible feature is backed by a disabled provider.

### Data

- Launch-market data gates pass.
- Image/menu/action coverage meets defined targets.
- Broken media rate is below threshold.
- stale/duplicate business sample audit passes.

### Reliability

- auth providers verified in production config
- native iOS build smoke passes
- native Android build smoke passes
- camera/photo/video permissions pass
- real upload round trip passes
- map permissions/location fallback pass
- offline/degraded behavior passes
- Sentry receives a controlled test error in each environment

### QA

- zero P0/P1 release blockers
- CI green
- E2E matrix green
- physical-device matrix green
- screenshot visual review green
- production-data smoke green

---

## 14. Refix execution order

Do not parallelize visual polish ahead of data readiness.

1. Freeze this ledger as recovery source of truth.
2. Capture production configuration and deployment topology.
3. Fix OAuth capability/config release blocker.
4. Lock new Discovery IA: Search + Map.
5. Make Map first-class.
6. Rebuild Search zero state.
7. Build City Readiness metrics/gates.
8. Run image-enrichment source canaries.
9. Run menu-enrichment source canaries.
10. Raise launch-market richness.
11. Rebuild Feed against rich production data.
12. Rebuild Place Detail to 9/10.
13. Rebuild Craves as map-backed memory/planning.
14. Rework Rank/Taste cold start.
15. Surface contribution clearly.
16. Prove photo upload on device.
17. Prove video upload on device.
18. Strengthen social proof.
19. Add learned personalization only after sufficient outcome data.
20. Expand E2E/native release suite.
21. Nuke-pass every screen and backend lane.
22. Fix findings.
23. Repeat nuke pass.
24. Ship only when all release gates pass.

---

## 15. Nuke-pass protocol

For every screen/system:

### Pass A — visible product

- Does it look alive?
- Is there meaningful content above the fold?
- Does every major action explain itself?
- Is the next action obvious?
- Does it outperform a generic CRUD client?

### Pass B — data lineage

For every visible field, trace:

UI -> normalizer -> client -> endpoint -> service -> DB/provider -> provenance/freshness.

No mystery fields. No assumed coverage.

### Pass C — failure injection

Test:

- 401
- 403
- 404
- 409
- 429
- 500
- timeout
- offline
- partial payload
- stale image
- missing image
- missing menu
- invalid coordinates
- disabled auth provider
- denied permission
- upload interruption

### Pass D — state integrity

Test fast navigation, account change, city change, pagination, pull-to-refresh, retry, optimistic mutations and app background/foreground.

### Pass E — production proof

Real deployment. Real production-like data. Real native build. Real device where capability depends on device APIs.

---

## 16. Definition of done

A feature is **not done** when the code exists.

It is done only when:

1. it is reachable by the intended user;
2. its production data is sufficient;
3. loading/empty/error/offline states are designed;
4. analytics/diagnostics can tell whether it works;
5. automated tests cover the contract;
6. the real deployment configuration supports it;
7. device-dependent behavior is physically proven;
8. a screenshot/product review meets the quality bar;
9. no critical upstream dependency is silently disabled;
10. the full user journey succeeds end to end.

---

## 17. Immediate hard truth

The current screenshots are not a cosmetic problem. They are evidence that CRAVE's engineering and product-readiness definitions drifted apart.

The recovery plan is therefore not another styling pass.

It is a reconnection of:

**navigation + data richness + discovery + place evidence + memory + contribution + personalization + production config + release proof.**

Until those are connected, CRAVE remains a strong technical foundation wrapped around a weak consumer experience.

This ledger supersedes any status language that calls a feature solid solely because its code/tests exist. `CRAVE_STATUS.md` remains the factual engineering status/history document; this file is the product-recovery and release-quality authority until the 9/10 gates above are closed.
