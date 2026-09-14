# CRAVE Feed V2 — File-by-File Migration Matrix

**Status:** EXECUTION PLANNING CONTRACT — no production implementation yet
**Date:** 2026-09-08
**Depends on:** `CRAVE_FEED_V2_MASTER_ARCHITECTURE.md`, `CRAVE_SCREEN_CONTRACT_FEED.md`

---

## 0. Purpose

This matrix converts Feed V2 doctrine into a bounded implementation plan against the repository that exists today.

It is explicitly **not** a clean-slate rewrite plan.

Every current file is classified as one of:

- **KEEP** — preserve responsibility and behavior;
- **UPGRADE** — preserve identity, strengthen semantics/contract;
- **ADAPT** — preserve most behavior while connecting to Feed V2;
- **CONSOLIDATE** — merge responsibility into a canonical authority;
- **MOVE RESPONSIBILITY** — keep capability but move semantic ownership elsewhere;
- **RETIRE** — remove only after verified parity/dependency proof;
- **NEW** — justified new boundary;
- **BLOCKED/LATER** — intentionally not part of current implementation.

No file may be deleted merely because this matrix says `RETIRE`; retirement happens only after call-site search, test coverage, parity, and a clean production transition.

---

## 1. Global migration rule

The migration sequence is:

> **preserve truth -> establish authority -> build parallel tested capability -> cut Home over -> verify parity -> retire duplicate authority.**

Do not begin with visual cleanup.

Do not begin by deleting the old Feed path.

Do not create a fourth recommendation service.

---

# 2. Frontend — Home / Feed

## `frontend/app/(tabs)/index.tsx`

**Classification:** REBUILD / THIN

### Current responsibility

Currently owns too much:

- general Feed pagination;
- Decision Session query;
- personalized recommendations query;
- Craves state;
- location/city;
- generic filters;
- local discovery-section construction;
- dedupe across sections;
- viewability analytics;
- Save/auth behavior;
- navigation;
- Place Detail prefetch;
- haptics/animation;
- rendering.

### Keep

- tab-screen identity;
- navigation;
- auth gate integration;
- Save action integration;
- Place Detail prefetch where still useful;
- haptic/toast conventions;
- FlashList/viewability mechanism if Explore Mode still uses it;
- loading/error rendering responsibilities;
- UI rendering.

### Remove from screen after backend composition parity

- construction of `MORE IN YOUR LANE`;
- `HOLE-IN-THE-WALL` inference from `gem` tier;
- `FROM YOUR CRAVES` candidate composition;
- local cross-source recommendation dedupe policy;
- semantic ownership of supporting modules;
- independent `useRecommendations()` Home fetch;
- generic FilterSheet as primary Home intent model;
- implicit blending of Decision Session with infinite Feed.

### Target responsibility

Render one typed Home/Decision response plus explicit Explore continuation.

### Verification

- first viewport hierarchy tests;
- thin candidate pool;
- no supporting module;
- rejection/recovery;
- committed state;
- auth Save;
- viewability;
- accessibility;
- no semantic local rail generation.

---

## `frontend/src/hooks/useDecisionSession.ts`

**Classification:** UPGRADE

### Current

Builds params from city/location and a fixed 20-mile radius.

### Target

Consume approved `RecommendationContext` / Decision Session request contract.

### Add only when backend supports

- time context;
- novelty mode;
- explicit session/context overrides;
- hard/soft constraints;
- session id.

### Prohibited

Do not invent client-only values merely to satisfy the type.

---

## `frontend/src/api/decisionSession.ts`

**Classification:** UPGRADE

### Target response evolution

Support, when backend implements them:

- role;
- reason codes;
- confidence semantics;
- composition/session metadata;
- recovery/completion state if this remains the Home endpoint.

Alternative: if a separate composed Home endpoint is introduced, this API can remain a narrower role endpoint for Craves/internal use.

### Decision required during FV2-04

Choose exactly one canonical Home transport:

A. evolve Decision Session endpoint into composed Home response; or
B. create dedicated Home composition endpoint while preserving Decision Session endpoint for shared role use.

Codex may resolve transport implementation only after the response semantics are frozen; it may not create two Home authorities.

---

## `frontend/src/hooks/useRecommendations.ts`

**Classification:** RETIRE FROM HOME / KEEP IF OTHER CONSUMERS REMAIN

### Current

Fetches `/recommendations` independently and feeds `MORE IN YOUR LANE`.

### Migration

Home stops consuming it directly after composition cutover.

### Retirement gate

Search all call sites. If another screen genuinely needs the hook, keep it outside Home.

---

## `frontend/src/api/recommendationContext.ts`

**Classification:** KEEP + EXTEND

### Canonical role

Shared cross-surface recommendation context vocabulary.

### Preserve

- surface;
- location;
- time context;
- query;
- hard/soft constraints;
- novelty;
- candidate scope;
- session id;
- cursor.

### Potential extensions

Only if product/runtime actually supports them:

- explicit meal/occasion key;
- current-session context version;
- context reset identity.

Avoid duplicating existing fields with Feed-specific aliases.

---

## `frontend/src/api/recommendationEvents.ts`

**Classification:** KEEP + EXTEND CAREFULLY

### Preserve

- surface;
- event type;
- position;
- rank percentile;
- query;
- city;
- session;
- search session;
- Decision role;
- client event id.

### Potential Feed V2 event additions

Only once real controls exist:

- rejection;
- context override;
- commitment.

### Required

Any event addition must update backend validation/model semantics/tests/privacy review together.

---

## `frontend/src/utils/recommendationEventQueue.ts`

**Classification:** KEEP

### Role

Existing event-delivery boundary.

Do not build a second Feed telemetry queue.

### Audit during FV2-07

- batching;
- process-loss semantics;
- anonymous session identity;
- whether rejection/commitment need stronger durability than passive telemetry.

---

## `frontend/src/stores/discoveryContextStore.ts`

**Classification:** KEEP SEARCH/MAP-SPECIFIC

Do not expand this store into Home/Feed session state.

It owns exact Search -> Map handoff semantics.

---

## `frontend/src/stores/cravesStore.ts`

**Classification:** KEEP

### Feed use

Source of current Save state and Save mutations.

### Rule

Do not duplicate saved state into a Feed store.

---

## `frontend/src/stores/cityStore.ts`

**Classification:** KEEP

Area selection remains a shared location fallback.

---

## `frontend/src/hooks/useLocation.ts`

**Classification:** KEEP

Foreground current-location source only.

No Feed V2 background-location expansion.

---

## New frontend session store

Suggested path:

`frontend/src/stores/decisionSessionStore.ts`

**Classification:** NEW ONLY IF REQUIRED

### Create only if

React Query/backend state cannot cleanly own temporary session lifecycle.

### Allowed state

- session id;
- local context overrides awaiting request;
- current rejection state if server does not own it;
- commitment state if not returned canonically;
- explicit reset.

### Prohibited

- duplicate durable Taste Profile;
- duplicate Craves;
- hidden long-term preference inference;
- unnecessary persistence.

Default: ephemeral.

---

# 3. Frontend — UI V2 presentation

## `frontend/src/ui-v2/tokens/index.ts`

**Classification:** KEEP

Feed must consume production semantic tokens; no Feed-specific random colors.

---

## `frontend/src/ui-v2/primitives/*`

**Classification:** KEEP

Use existing accessibility/touch/motion/scaling ownership.

Do not recreate Feed-specific primitive buttons/text/image wrappers.

---

## Existing UI V2 product components

### `FoodMedia`
**KEEP / REUSE** — appetite image/fallback behavior.

### `PlaceIdentityFallback`
**KEEP / REUSE** — missing-media identity.

### `ReasonLine`
**KEEP / REUSE** — evidence-backed terse reason.

### `OperationalStatus`
**KEEP / REUSE** — known operational truth.

### `ConfidenceStatement`
**KEEP / REUSE** — personal-evidence uncertainty.

### `SaveAction`
**KEEP / REUSE** — lightweight Save interaction.

### `DecisionRecovery`
**KEEP / ADAPT** — reuse only if its semantics match Feed recovery.

### Search/Map-specific result cards
**DO NOT FORCE-REUSE** if doing so produces conditional semantic overload. Build Feed role composition around shared lower-level primitives instead.

---

## Potential new UI V2 Feed components

### `DecisionContextControl`
**NEW**

Semantic props only.

### `BestFitHero`
**NEW IF NEEDED**

Must remain Feed-role specific and not become another universal restaurant card.

### `DecisionAlternativeCard`
**NEW IF NEEDED**

Safe Bet/Wildcard subordinate presentation.

### `FeedCompletionState`
**NEW**

Explicit successful `You're set` state.

### `FeedSupportingModule`
**NEW / COMPOSITION WRAPPER**

Renders approved backend module types; does not invent their meaning.

---

# 4. Backend — Decision Session

## `backend/app/api/v1/routes/decision_session.py`

**Classification:** UPGRADE / KEEP THIN

### Current

Owns request parsing/candidate retrieval/hydration around `build_decision_session()`.

### Target

Stay a route layer, not intelligence owner.

Depending on FV2-04 transport decision, either:

- evolve into composed Home endpoint; or
- stay narrow while new Home route composes Decision Session + support modules.

### Prohibited

Do not duplicate evaluator/composition logic in route handlers.

---

## `backend/app/services/decision_session/decision_session_builder.py`

**Classification:** UPGRADE — CANONICAL SHARED ROLE AUTHORITY

### Keep

- pure/deterministic shape where practical;
- no-padding invariant;
- shared use from `/craves/reasoned`;
- role constants.

### Replace current semantics

- Best Fit = generic rank #1;
- Safe Bet = percentile + unused category only;
- Wildcard = deterministic explore boost + unused category.

### Target inputs

A typed evaluated-candidate representation containing approved dimensions/reason evidence.

### Target output

0-3 role-qualified cards with reason codes/confidence semantics.

### Test requirements

- no candidates;
- one role only;
- Safe Bet omitted when confidence insufficient;
- Wildcard omitted when novelty is unsupported;
- no hard-constraint violations;
- rejected candidate suppression;
- deterministic ordering;
- Craves reuse parity.

---

# 5. Backend — Feed ranking and candidate infrastructure

## `backend/app/services/feed/feed_ranker.py`

**Classification:** REFACTOR / NARROW RESPONSIBILITY

### Keep

Useful generic foundations:

- rank quality signal;
- proximity calculation;
- deterministic diversity;
- category saturation controls;
- stable ordering/tie behavior.

### Remove semantic overreach

Its final score must not be treated as `personal_fit` or Best Fit authority.

### Likely future role

Generic candidate-quality/context helper used by evaluator or retrieval.

### Do not

Stuff all Feed V2 evidence dimensions into one opaque replacement formula here.

---

## `backend/app/services/feed/feed_cursor_snapshot.py`

**Classification:** KEEP + ADAPT

### Keep

- stable ordering;
- scope-matched cursors;
- TTL snapshot behavior.

### Potential extension

Snapshot/composition version or context hash when required by the final Home/Explore transport.

### Rule

Pagination must never change intelligence policy.

---

## `backend/app/services/feed/feed_bucket_builder.py`

**Classification:** CONSOLIDATE / INVESTIGATE

### Current

Builds city bucket from stable + random discovery sources.

### Target question

Does prebuilt city candidate caching still materially improve generic candidate retrieval after Feed V2 composition exists?

### If yes

Keep as retrieval cache only.

### If no

Retire after call-site/performance proof.

It must not own personal discovery semantics.

---

## `backend/app/services/feed/feed_bucket_manager.py`

**Classification:** CONSOLIDATE / INVESTIGATE

Same boundary as bucket builder: cache/retrieval only, never Home composition authority.

---

## `backend/app/services/feed/feed_bucket_store.py`

**Classification:** KEEP IF BUCKET PATH SURVIVES / RETIRE WITH BUCKET PATH

No independent semantic changes.

---

## `backend/app/services/feed/feed_bucket_types.py`

**Classification:** KEEP IF BUCKET PATH SURVIVES / RETIRE WITH BUCKET PATH

---

## `backend/app/services/query/feed_mixer.py`

**Classification:** DEMOTE / REPLACE AS PERSONAL DISCOVERY SEMANTICS

### Current

4 stable : 1 discovery pattern plus category-streak guard.

### Keep only if useful

Generic catalog mixing for Explore/candidate generation.

### Must not

Define Wildcard, personal novelty, or Home module composition.

---

## `backend/app/services/query/discovery_places.py`

**Classification:** KEEP GENERIC OR RETIRE AFTER PROOF

Random sampling from a high-score pool is generic variation.

It must never be presented as personalized novelty.

---

## `backend/app/services/feed/feed_builder.py`

**Classification:** INVESTIGATE -> LIKELY RETIRE

### Current issue

Accepts lat/lng/radius but currently queries active geocoded places ordered by rank score without using those arguments for actual geographic filtering/ranking.

### Required before retirement

- repository-wide call-site search;
- test inventory;
- fallback behavior audit;
- verify Map/Feed no longer depend on it;
- remove only in a dedicated cleanup PR after canonical path is proven.

---

# 6. Backend — existing personalized recommendations

## `backend/app/services/social/recommendation_service.py`

**Classification:** KEEP + INTEGRATE

### Current

Lightweight collaborative filtering over shared `PlaceRanking` vectors using cosine similarity with cold-start fallback.

### Keep

- sparse-scale approach;
- minimum shared-place threshold;
- blocked-user exclusion;
- ranked/saved candidate exclusion;
- deterministic score ordering;
- cold-start fallback.

### Feed V2 role

Candidate source and personal-fit signal, not independent Home composition authority.

### Do not yet

Replace with embeddings/bandits/heavy ML.

---

## `backend/app/api/v1/routes/recommendations.py`

**Classification:** KEEP / DECOUPLE FROM HOME COMPOSITION

The endpoint can survive for other use cases and debugging.

Home composition should call the underlying service rather than make frontend fetch this endpoint independently.

---

## `frontend/src/api/places.ts::fetchRecommendations`

**Classification:** KEEP API FUNCTION IF OTHER CONSUMERS REMAIN / REMOVE HOME USE

---

# 7. Backend — evidence authority

## New `backend/app/services/feed/user_evidence_resolver.py`

**Classification:** NEW — REQUIRED

### Purpose

Resolve existing typed evidence into Feed-consumable meanings without flattening fact, preference, intent, exposure, and session state.

### Inputs

- `PlaceRanking`;
- VisitEvidence;
- HitlistSave/Craves;
- collaborative-filter support;
- recommendation ledger exposure/outcomes where appropriate;
- approved quick-take/Taste corrections once those systems exist;
- session context/rejections.

### Output categories

- durable preference evidence;
- prospective intent;
- factual history;
- exposure/resolution state;
- session intent.

### Required tests

- visit alone != positive preference;
- inferred visit action-specific behavior;
- explicit negative overrides passive signal;
- session negative does not persist as durable dislike;
- Save and imported Crave provenance remain distinguishable;
- blocked/deleted/retracted evidence excluded.

---

## `backend/app/services/visit_evidence_service.py`

**Classification:** KEEP + CONSUME

Do not rewrite this service into Feed-specific semantics.

Feed resolver reads its factual/eligibility outputs.

---

## `backend/app/api/v1/routes/rankings.py`

**Classification:** KEEP LOCKED

### Preserve

Declared/verified visit requirement for Rank queue.

Rank remains high-authority preference evidence.

Feed V2 must not weaken Rank truth rules.

---

## `backend/app/services/personal_ranking/*`

**Classification:** KEEP

Consume outputs; do not redesign ranking system as part of Feed V2 unless a proven integration gap requires a separate approved change.

---

## `backend/app/services/social/taste_profile_service.py`

**Classification:** KEEP / DO NOT PROMOTE TO FULL TASTE MODEL

Current purpose is aggregation:

- total ranked;
- tier counts;
- favorite cuisine;
- top city;
- percentile.

Useful evidence/summary input, not canonical Feed preference state.

---

## `backend/app/db/models/hitlist_save.py`

**Classification:** KEEP

Preserve save provenance/reason fields.

Feed V2 may consume them; avoid adding generic `feed_score` fields.

---

## `backend/app/db/models/crave_item.py`

**Classification:** KEEP

Imported/social-sighting provenance remains distinct from native saves.

---

# 8. Backend — factual truth / operational state

## `backend/app/db/models/place_claim.py`

**Classification:** KEEP UNCHANGED FOR FEED

Architectural precedent only.

No user taste data belongs here.

---

## `backend/app/db/models/place_truth.py`

**Classification:** KEEP UNCHANGED FOR FEED

Feed evaluator may consume resolved facts.

Do not bypass canonical truth resolution by reading low-confidence raw claims as final operational truth.

---

## hours / operational services

**Classification:** KEEP / CONSUME

Use `hours_status`/truth confidence only where currently supported.

Unknown/stale data must remain unknown/stale.

---

# 9. Backend — new evaluation and composition boundaries

## New `backend/app/services/feed/feed_candidate_evaluator.py`

**Classification:** NEW — REQUIRED

### Responsibility

Produce deterministic candidate dimensions.

Expected semantic outputs:

- `personal_fit`;
- `context_fit`;
- `evidence_confidence`;
- `novelty`;
- `operational_fit`;
- `resolved_state`;
- reason evidence/codes.

### Phase 1

Heuristic/deterministic and inspectable.

### Prohibited

No opaque all-purpose score that recreates the current semantic problem.

---

## New `backend/app/services/feed/feed_composition_policy.py`

**Classification:** NEW — REQUIRED

### Responsibility

One Home composition authority.

Decides:

- Decision Set;
- supporting modules;
- omission;
- completion;
- Explore continuation.

### Must not

Perform database queries directly if service boundaries can supply typed candidates/evidence.

---

## Optional `backend/app/services/feed/decision_session_state.py`

**Classification:** NEW ONLY IF REQUIRED

Use only if server-side temporary session state is needed.

Do not introduce durable DB persistence by default.

---

# 10. Backend — Home transport

## Option A: evolve `decision_session.py`

**Classification:** POSSIBLE

Pros:

- fewer endpoints;
- existing Home concept already uses Decision Session.

Risk:

- endpoint becomes broader than the reusable role builder concept.

## Option B: new `backend/app/api/v1/routes/home.py`

**Classification:** POSSIBLE / LIKELY CLEANER

Pros:

- explicitly represents composed Home;
- Decision Session endpoint can remain reusable/narrow for Craves/internal contexts.

Required if chosen:

- dedicated schema module;
- route registration;
- typed frontend client;
- cache/session semantics;
- tests.

### Locked requirement

Exactly one endpoint/DTO becomes canonical for Home composition.

Do not leave frontend consuming both as independent authorities.

---

# 11. Backend — Search

## `backend/app/services/search/search_engine.py`

**Classification:** KEEP UNCHANGED EXCEPT SHARED TYPES IF NECESSARY

Feed adopts the architectural lesson:

> broad bounded retrieval -> enrichment/rank -> paginate.

Feed does not absorb Search ranking semantics.

---

## Search ranker/query files

**Classification:** KEEP SEARCH-SPECIFIC

No Feed V2 rewrite.

---

# 12. Backend — Craves

## `backend/app/api/v1/routes/craves.py`

**Classification:** KEEP + ADAPT THROUGH SHARED BUILDER

`/craves/reasoned` keeps saved-pool candidate scope and graduation semantics.

When Decision Session builder input changes to evaluated candidates, Craves must adapt to the same shared role semantics without becoming Home-dependent.

### Important

Craves membership semantics may remain broader than Feed preference weight.

Native Save and imported Crave can both be candidates while retaining different evidence provenance.

---

# 13. Backend — Recommendation Ledger

## `backend/app/db/models/recommendation_event.py`

**Classification:** KEEP + CORRECT DOCUMENTATION / EXTEND ONLY WHEN REAL

### Immediate documentation correction

Current Home now uses true viewability (`50%` + `250ms`) before emitting impressions; any comments saying Feed impressions are fetched-page impressions are stale and must be updated in FV2-07.

### Potential schema additions later

Only when real evaluator/composition exists:

- algorithm version;
- composition version;
- reason code;
- candidate-set id/hash;
- rejection/commitment event type.

Do not add speculative columns preemptively.

---

## `backend/app/services/recommendations/recommendation_event_service.py`

**Classification:** KEEP

Canonical event validation/write service.

Extend in lockstep with event schema/client.

---

# 14. Privacy / legal

## `frontend/app/legal/privacy.tsx`

**Classification:** UPDATE BEFORE FEED V2 RELEASE

### Current gap

Policy explains account, location, uploads, created content, notifications, and operational logs but does not clearly describe recommendation interaction telemetry/session personalization.

### Required update if persisted

Disclose:

- recommendation interaction events;
- how rankings/saves/visits affect recommendations;
- session personalization signals where retained;
- location use for recommendation context;
- retention/deletion controls.

### Must preserve

- no ads/ad-tracking claim only if still factually true;
- no data sale claim only if still factually true.

Legal copy must describe actual implementation, not planned capability.

---

# 15. Doctrine / governance files

## `docs/doctrine/CRAVE_FEED_V2_MASTER_ARCHITECTURE.md`

**Classification:** NEW — CANONICAL FEED INTELLIGENCE CONTRACT

## `docs/doctrine/CRAVE_SCREEN_CONTRACT_FEED.md`

**Classification:** UPGRADED — CANONICAL FEED SCREEN CONTRACT

## `docs/doctrine/CRAVE_FEED_V2_MIGRATION_MATRIX.md`

**Classification:** NEW — EXECUTION MAP

## `docs/doctrine/CRAVE_CANONICAL_IMPLEMENTATION_INDEX.md`

**Classification:** UPDATE AFTER APPROVAL

Add the three Feed V2 artifacts and clarify precedence over older Feed implementation assumptions.

## `docs/doctrine/CRAVE_IMPLEMENTATION_MIGRATION_PLAN.md`

**Classification:** UPDATE AFTER APPROVAL

Do not silently splice Feed V2 into old numbered waves before product owner approves this architecture. Add a dedicated Feed V2 lane/wave sequence.

## `docs/doctrine/CRAVE_MASTER_CODEX_REMAINING_WORK.md`

**Classification:** UPDATE AT IMPLEMENTATION CLAIM

Once FV2-00 is approved, register FV2-01 as the next executable Feed task without overwriting unrelated Wave 8-10 ownership.

## `.agent-bridge/STATE.md`

**Classification:** UPDATE ON EACH CLAIM/HANDOFF

Record owner, branch, base SHA, exact allowed files, verification plan, and status.

---

# 16. Test migration matrix

## Existing Decision Session tests

**UPGRADE**

Must cover new role semantics without breaking Craves reuse.

## Existing Feed ranker tests

**KEEP + ADD BOUNDARY TESTS**

Assert generic ranker no longer claims personal-fit semantics.

## Existing Home frontend tests

**REBUILD AROUND COMPOSED RESPONSE**

Cover:

- Best Fit primary hierarchy;
- subordinate alternatives;
- missing role;
- no module;
- module present;
- rejection;
- two full-set rejection recovery;
- completion;
- cold start;
- error vs empty;
- missing media;
- auth Save;
- accessibility labels/order where testable.

## New `user_evidence_resolver` tests

**REQUIRED**

- Rank > passive behavior;
- explicit negative precedence;
- visit fact != like;
- inferred visit cannot create positive preference;
- session rejection stays session-scoped;
- source retraction respected;
- save provenance retained;
- deleted evidence not used.

## New candidate evaluator tests

**REQUIRED**

- hard constraint exclusion;
- low evidence confidence;
- operational unknown does not become closed;
- novelty threshold;
- repeated exposure suppression;
- resolved candidate suppression;
- deterministic output.

## New composition policy tests

**REQUIRED**

- 1/2/3 role responses;
- supporting module omitted;
- duplicate candidate exclusion;
- no unsupported rail type;
- completion suppresses further Decision Mode;
- Explore remains explicit.

## Telemetry tests

**UPGRADE**

- viewability semantics;
- role/position/session;
- new event validation if added;
- no duplicate exposure within session/context;
- rejection/commit durability semantics.

## Privacy/deletion tests

**ADD ONLY IF NEW PERSISTED STATE EXISTS**

---

# 17. Execution waves and exact file envelopes

## FV2-00 — Doctrine and contracts

### Files

- `docs/doctrine/CRAVE_FEED_V2_MASTER_ARCHITECTURE.md`
- `docs/doctrine/CRAVE_SCREEN_CONTRACT_FEED.md`
- `docs/doctrine/CRAVE_FEED_V2_MIGRATION_MATRIX.md`
- after approval only: canonical index/migration-plan references

### Code

None.

### Gate

Human approval that product semantics are correct.

---

## FV2-01 — User evidence resolver

### Expected files

- new `backend/app/services/feed/user_evidence_resolver.py`
- corresponding backend tests
- minimal shared types if justified

### Read-only dependencies

- ranking models/services;
- visit evidence;
- HitlistSave/CraveItem;
- recommendation events;
- recommendation service;
- block/delete/privacy behavior.

### Do not touch

Frontend Home.

### Gate

Backend tests prove typed evidence semantics.

---

## FV2-02 — Context and candidate evaluator

### Expected files

- `recommendationContext` backend/client contract location(s);
- new `feed_candidate_evaluator.py`;
- evaluator tests;
- small Feed ranker adaptations if required.

### Gate

Deterministic dimensions + hard constraints + no unsupported claims.

---

## FV2-03 — Decision Session semantics

### Expected files

- `decision_session_builder.py`;
- Decision Session schemas/routes as needed;
- `/craves/reasoned` adapter as needed;
- tests.

### Gate

Shared role semantics, no padding, Craves parity.

---

## FV2-04 — Home composition authority

### Expected files

- new `feed_composition_policy.py`;
- Home route/schema OR evolved Decision Session transport;
- typed frontend API client;
- integration tests.

### Gate

One response can represent Decision Set, optional modules, recovery/completion metadata without frontend invention.

---

## FV2-05 — Session cognition

### Expected files

- session-state service/store only if required;
- rejection endpoint/event handling if chosen;
- Home route/composition adaptation;
- tests.

### Gate

Two full-set rejection behavior + commitment/completion + correct reset semantics.

---

## FV2-06 — Home UI V2

### Expected files

- `(tabs)/index.tsx`;
- Feed-specific UI V2 components;
- typed Home hook/client;
- frontend tests.

### Gate

Frontend no longer creates recommendation meaning.

---

## FV2-07 — Telemetry / privacy

### Expected files

- recommendation event client/model/service/tests;
- `privacy.tsx`;
- deletion/reset propagation only if new persisted data exists.

### Gate

Data description matches actual runtime.

---

## FV2-08 — Retirement

### Candidate files

- old Home `useRecommendations` consumption;
- unsupported section heuristics;
- legacy Home feed path;
- dead fallback feed builder;
- obsolete bucket/mixer path only if dependency proof permits.

### Gate

Repository-wide call-site proof + CI green + no behavioral parity gap.

---

## FV2-09 — Certification

### Required scenarios

- anonymous cold start;
- signed-in sparse history;
- rich Rank history;
- thin local catalog;
- no Safe Bet;
- no Wildcard;
- hard-constraint zero result;
- location denied;
- location unavailable;
- stale hours;
- missing photo;
- repeated rejection;
- two full-set rejections;
- committed state;
- no supporting modules;
- Explore continuation;
- offline/cache path;
- Dynamic Type;
- VoiceOver;
- Reduced Motion;
- 44pt targets;
- hostile long names/reasons;
- real photo variance.

Final status requires runtime/device evidence, not design claims.

---

# 18. Migration stop conditions

Stop and return to architecture instead of silently deciding if implementation discovers:

1. Best Fit requires a product weighting choice not specified here.
2. hard/soft constraint precedence is ambiguous.
3. a new persistent user signal is required but privacy/deletion semantics are undefined.
4. Craves and Feed need different role meanings.
5. candidate evaluator requires unsupported restaurant attributes.
6. Wildcard cannot be computed without pretending random diversity is personal novelty.
7. Home transport would require two independent composition authorities.
8. a UI component cannot express the contract without changing product meaning.
9. retirement would break a non-Home consumer.
10. runtime data is too sparse to justify a planned learned model.

Canonical governance rule:

> **Zero invisible unknowns.**

---

# 19. Final file ownership summary

### KEEP

- RecommendationContext core contract
- collaborative-filter recommendation service
- Rank system
- visit evidence service
- Craves candidate scope/graduation
- recommendation event queue/service
- PlaceClaim/PlaceTruth factual pipeline
- cursor snapshot
- UI V2 primitives/tokens

### UPGRADE

- Decision Session builder
- Decision Session transport
- Feed ranker's boundary/meaning
- recommendation-event documentation/semantics
- Home screen
- privacy disclosure when runtime changes

### NEW

- User Evidence Resolver
- Candidate Evaluator
- Feed Composition Policy
- Feed completion presentation
- Decision Context presentation
- optional session-state boundary
- optional composed Home route/schema

### RETIRE AFTER PARITY

- Home's independent personalized-recommendation fetch/composition
- `gem` -> hole-in-the-wall heuristic
- frontend-defined supporting-rail authority
- legacy Home feed pagination authority
- dead/duplicate feed builder paths proven unused

### LATER / DATA-LIMITED

- learned position debiasing
- contextual bandits/UCB
- CRAVE-trained recommendation embeddings
- learned novelty calibration
- heavy ML ranking infra

---

# 20. Execution lock

> **Do not start FV2-01 until FV2-00 is approved.**

> **Do not visually rebuild Home until FV2-04 has established one real composition authority.**

> **Do not retire an existing recommendation path until its consumer map and parity are verified.**

> **Codex may resolve implementation mechanics. It may not silently resolve product, evidence, privacy, semantic, or interaction ambiguity.**
