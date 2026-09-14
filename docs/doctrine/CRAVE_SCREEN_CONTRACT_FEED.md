# CRAVE Screen Contract — Feed / Decision Session V2

**Status:** DESIGN CONTRACT — implementation not started
**Date:** 2026-09-08
**Architecture dependency:** `CRAVE_FEED_V2_MASTER_ARCHITECTURE.md`
**Screen:** `(tabs)/index.tsx`

---

## 1. Purpose

Feed is CRAVE's default **decide** surface.

Its first job is to answer:

> **What should I eat right now?**

Its second job is to expose a small amount of useful discovery only when that discovery deserves attention.

Feed is not a restaurant directory, popularity board, social timeline, or engagement-maximizing content stream.

Canonical principle:

> **Home shows the next useful decision, not everything CRAVE knows.**

---

## 2. User objective

The user should be able to:

1. understand CRAVE's strongest current answer;
2. understand why it fits;
3. compare at most a small number of meaningfully different alternatives;
4. act, save, reject, or deliberately explore;
5. finish the decision without being pushed into more browsing.

A confident `no` is a valid outcome.

A short successful session is better than a long indecisive one.

---

## 3. Entry points

- default tab on app open;
- normal tab navigation from Search, Craves, Rank, Profile, or Place Detail;
- return from Place Detail after considering a Decision Session recommendation;
- return from an action that does not itself complete the Decision Session.

Feed must not require authentication merely to view recommendations.

---

## 4. Exit points

Primary exits:

- `View Place` -> Place Detail;
- Directions through Place Detail/current action contract;
- Save -> stays in context;
- Search -> explicit intent/refinement;
- Craves -> saved-intent resolution;
- contextual Map -> current candidate set where supported;
- Explore More -> explicit Explore Mode;
- no further action -> valid success.

The screen may also enter a **completion state** without navigation.

---

## 5. First viewport

The first viewport must contain, in order:

1. CRAVE identity/header;
2. a compact **Decision Context** control/summary;
3. `Tonight's answer` / equivalent Decision Session framing;
4. one dominant Best Fit candidate when available;
5. one concise evidence-backed `Why this fits` reason;
6. operational truth relevant to acting now;
7. primary `View Place` action;
8. Save as a secondary lightweight action.

Best Fit must receive more visual weight than Safe Bet/Wildcard.

Home must not open with:

- a generic filter drawer;
- category chips dominating the viewport;
- a social feed;
- a directory list;
- a `Trending` module;
- a greeting that competes with the decision.

---

## 6. Canonical information hierarchy

### 6.1 Decision Context

Examples:

- `Dinner · Nearby · Open now`
- `Lunch · Oakland · Balanced`

This is a compact summary of real/inferred/set context.

It replaces the mental model of a generic directory filter on Home.

Tapping it opens only supported context controls.

Unsupported controls must not appear as fake affordances.

### 6.2 Best Fit

Dominant visual candidate.

Contains:

- food-first media when real media exists;
- restaurant identity;
- `BEST FIT` role;
- one concise evidence-backed reason;
- relevant operational metadata;
- `View Place`;
- Save.

### 6.3 Safe Bet / Wildcard

If legitimately available, present as subordinate alternatives rather than three equal hero cards.

Each role must be semantically qualified by the backend.

If a role has no valid candidate, omit it.

### 6.4 Optional supporting module

After the Decision Set, at most a small number of supporting modules may appear when evidence supports them.

Examples:

- From your Craves;
- Worth stretching for;
- Something different;
- Saved and nearby;
- Because you loved X.

The exact module vocabulary is generated from approved composition-policy types, not improvised by frontend heuristics.

### 6.5 Explore More

Explore is an explicit transition.

The screen must not silently continue the Decision Session into an unbounded general feed.

---

## 7. Component tree

```text
FeedScreen
├─ FeedHeader
│  ├─ Wordmark
│  └─ Activity affordance when globally required
├─ DecisionContextControl
├─ DecisionMode
│  ├─ DecisionHeading
│  ├─ BestFitHero
│  │  ├─ FoodMedia / PlaceIdentityFallback
│  │  ├─ PlaceIdentity
│  │  ├─ DecisionRole
│  │  ├─ ReasonLine / ConfidenceStatement
│  │  ├─ OperationalStatus
│  │  ├─ ViewPlaceAction
│  │  └─ SaveAction
│  ├─ DecisionAlternatives
│  │  ├─ SafeBetCard?
│  │  └─ WildcardCard?
│  ├─ DecisionRecovery?
│  └─ FeedCompletionState?
├─ SupportingModule? × small bounded count
└─ ExploreMoreAction?
```

Where UI V2 product components already exist and are semantically compatible, reuse them rather than building duplicate Feed-only components.

---

## 8. Component reuse / new components

### Reuse where compatible

- UI V2 text/button/surface/image primitives;
- `FoodMedia`;
- `PlaceIdentityFallback`;
- `ReasonLine`;
- `OperationalStatus`;
- `ConfidenceStatement`;
- `SaveAction`;
- `DecisionRecovery` where semantics fit;
- existing auth gate;
- Place Detail prefetch behavior;
- true viewability instrumentation;
- existing toast/haptic conventions.

### New or Feed-specific composition

- `DecisionContextControl`;
- `BestFitHero` if existing result hero cannot express Feed semantics without conditional overload;
- compact role alternatives;
- `FeedCompletionState`;
- supporting-module renderer tied to backend composition types.

### Must not be reused as semantic shortcuts

- `gem` tier as `hole-in-the-wall`;
- `TrendingStrip` as discovery;
- generic FilterSheet as the primary Home context model.

---

## 9. Decision Context behavior

The control summarizes supported current context and exposes only material overrides.

Context may include, once implementation supports it:

- area/location;
- meal/time context;
- novelty mode;
- soft distance/travel preference;
- price/value tendency;
- hard dietary constraints.

### Rules

- no more than one clarifying question before recommending when uncertainty materially changes the result;
- inferred context must remain editable;
- hard constraints stay visibly protected;
- changing context re-runs the Decision Session;
- current-session rejection/commitment state resets only according to the approved session lifecycle;
- context edits do not silently rewrite durable Taste Profile.

---

## 10. Decision Session roles

### Best Fit

Strongest supported overall decision under personal fit, current context, constraints, operational viability, evidence confidence, and resolved state.

### Safe Bet

Strong established fit with lower uncertainty/high confidence.

Safe Bet is not synonymous with popular, chain, or highest percentile.

### Wildcard

Relevant, evidence-backed stretch beyond the user's established norm.

Wildcard is not random diversity.

### Missing role

Omit it.

Never pad to three.

---

## 11. Recommendation explanation

Every role card may show at most a concise reason in the first presentation layer.

Reason must answer:

> **Why this, for me, now?**

Examples of valid source concepts:

- repeated high Rank outcomes for related cuisine/attributes;
- collaborative-filter support plus local/context fit;
- saved intent;
- proximity inside normal/specified range;
- explicit novelty choice;
- a recent explicit preference correction.

Prohibited explanation behavior:

- hallucinated personal facts;
- opaque percentages such as `98% match`;
- `perfect for you`;
- `hidden gem` without evidence for that concept;
- treating missing data as negative evidence.

---

## 12. Confidence semantics

Confidence describes CRAVE's evidence about the match, not restaurant quality.

Examples:

- `Strong confidence`;
- `Still learning your Thai preferences`;
- `Few matching rankings yet`.

Operational uncertainty uses separate language:

- `Hours not recently verified`;
- `Limited menu information`;
- `Photo unavailable`.

Do not collapse every uncertainty into `Still learning`.

---

## 13. Rejection behavior

### Single rejection

Rejecting a candidate:

- records session-level negative intent;
- does not automatically create a permanent dislike;
- replaces only that role when another candidate legitimately qualifies;
- may leave the role empty.

### Full-set rejection

A full-set rejection means the current recommendation framing did not work.

### Two consecutive full-set rejections

Stop regeneration.

Show an explicit recovery interaction such as:

> What's off tonight?

Then allow supported context refinement or route to Search.

Do not silently produce another three restaurants indefinitely.

---

## 14. Commitment and completion

When the user commits to a restaurant, Decision Mode ends.

Canonical completion state:

### You're set

- chosen restaurant;
- relevant context;
- Directions / View Place actions;
- Save state if relevant;
- optional explicit `Explore anyway` action.

The selected restaurant does not get replaced by another recommendation because Home needs content.

Supporting discovery should recede.

---

## 15. Explore Mode

Explore is explicitly entered through `Explore more` or equivalent.

It may contain a bounded/paginated discovery list using stable cursor snapshots.

Rules:

- no semantic leakage from Explore ordering into Best Fit labels;
- no raw popularity/trending framing;
- finite/explicit pagination rather than an attention trap;
- exact availability remains discoverable via Search even when Home shows only a few options.

Canonical principle:

> **Reduce simultaneous competition, not restaurant availability.**

---

## 16. Supporting module policy

Supporting modules come from backend composition policy.

Frontend must not construct them by filtering whatever datasets happen to be loaded.

A module requires:

- an approved module type;
- a truthful reason;
- enough real candidates;
- no duplication against Decision Set;
- no hard-constraint conflict;
- no resolved-state conflict.

If none qualify, render none.

---

## 17. Cold start

### Anonymous / no durable taste

Feed still shows a Decision Session using honest lower-confidence fallback from supported city/location/catalog evidence.

### Signed in but sparse Rank history

Use what is known:

- onboarding reactions when available;
- saves/Craves;
- location/city;
- hard constraints;
- coarse affinity/novelty inputs that actually exist.

Never fabricate personalization language.

Account creation is required only at the first stateful action according to the global auth-gate contract.

---

## 18. State coverage

| State | Required behavior |
|---|---|
| Anonymous | Useful lower-confidence Decision Mode, no fake personal claims. |
| Authenticated | Full evidence-aware Decision Mode. |
| Initial loading | Skeleton matching final hierarchy, not generic spinner-only layout. |
| Refreshing | Preserve current content while refreshing when safe. |
| Success | Decision hierarchy defined in §§5-6. |
| Thin candidate pool | Render fewer roles honestly. |
| Low personalization confidence | Specific confidence language; still provide best supported answer. |
| No qualifying decision | Honest recovery to context/Search/Craves; no filler. |
| Single role rejected | Replace only if a real replacement qualifies. |
| Two full-set rejections | Explicit recovery prompt, no endless regeneration. |
| Committed | `You're set` completion state. |
| Location denied | Manual area/city fallback; Feed remains usable. |
| Location unavailable | Preserve selected/manual area or ask for area, not a broken screen. |
| Stale operational data | Show stale/unknown truth separately from recommendation confidence. |
| Missing media | Typography-led identity/fallback, no fake photo. |
| Offline | Last-known content where cache supports it; no false claim that context/rejection synced if it did not. |
| Network error | Clear retry path; do not mislabel as empty/no matches. |
| Hard-constraint zero result | Name protected constraint/recovery; never silent relaxation. |
| No supporting modules | Omit them cleanly. |
| Explore end | Real end state or bounded Show More behavior. |

---

## 19. Data reads

Feed V2 may read through approved backend composition services:

- RecommendationContext;
- local/catalog candidate retrieval;
- collaborative-filter recommendations;
- Rank history;
- VisitEvidence;
- saves/Craves;
- resolved operational PlaceTruth where applicable;
- recommendation exposure/resolved state;
- session state.

Frontend should not need to independently orchestrate these data sources once FV2-04 is complete.

---

## 20. Data writes

Possible writes only when the corresponding interaction exists:

- visible impression;
- Place Detail click;
- Save/unsave;
- rejection;
- context override;
- commitment;
- Rank outcome later in journey.

Every new persisted event needs:

- named semantics;
- retention/deletion behavior;
- tests;
- privacy review.

---

## 21. Analytics

Keep distinct surfaces/roles.

Decision Session events remain distinguishable from Explore/discovery events.

Required analysis dimensions after Feed V2:

- session id;
- role;
- candidate position;
- context identity/version where safe and necessary;
- visible exposure, not fetched-only exposure;
- rejection/commitment outcomes when implemented;
- algorithm/composition version once a real versioned evaluator exists.

Primary product metrics:

- time to decision;
- commitment/acceptance;
- rejection/correction rate;
- post-visit Rank agreement;
- novelty acceptance;
- abandonment;
- repeat trust.

Do not optimize for session duration or scroll depth.

---

## 22. Accessibility

Design requirements before implementation:

- all meaning available without photography or color;
- minimum 44x44pt interactive targets;
- VoiceOver order follows visual decision hierarchy;
- role labels included in accessible name/description where useful;
- Dynamic Type reflow without clipped reason/operational text;
- Reduced Motion respected;
- no swipe-only rejection/action;
- missing-media fallback fully accessible;
- confidence/constraint/operational state never color-only;
- Explore entry and Decision completion are distinguishable programmatically.

Runtime verification occurs after implementation.

---

## 23. Performance

- Home decision content should load in one composed request where practical;
- avoid frontend waterfalls across multiple independent ranking endpoints;
- no real-time LLM generation in Home critical path;
- reuse bulk hydration for media/percentiles/operational metadata;
- preserve Place Detail prefetch on deliberate press-in where it remains beneficial;
- avoid re-fetch loops caused by context/store identity churn.

---

## 24. Privacy

Before release of richer Feed V2 persistence, update privacy/data-lifecycle documentation to explain recommendation interaction data and personalization use.

Temporary session state should remain ephemeral by default.

No background location by default.

No scraped/purchased external personal behavior.

Account deletion/reset must remove any new persisted user-derived Feed state according to canonical privacy doctrine.

---

## 25. Responsive behavior

V1 remains mobile-first React Native.

Requirements:

- Best Fit remains dominant across supported phone widths;
- long restaurant names wrap without pushing primary action off-screen;
- reason copy reflows;
- large text may move metadata/action rows vertically;
- safe areas respected;
- no layout depends on fixed image text height.

---

## 26. Visual rules

Home follows approved CRAVE UI V2 semantics:

- dark cinematic surface;
- real appetite photography strongest where available;
- calm UI, energetic food media;
- food -> place -> why -> action hierarchy;
- gold limited to brand/selection/primary action;
- uncertainty, positive, protected, destructive, and neutral states use separate semantics;
- no star averages;
- no fake match percentage;
- no giant empty image panel when media is absent;
- no equal-weight wall of cards;
- no generic marketplace/carousel overload.

UI V2 implementation may refine composition spacing, but may not redesign screen behavior or semantics.

---

## 27. Prohibited behavior

- infinite Decision Mode;
- automatic endless recommendation regeneration;
- frontend-created recommendation semantics;
- `gem` -> `hole-in-the-wall` mapping;
- random/deterministic exploration -> `Wildcard` mapping;
- hard constraint silent relaxation;
- popularity/trending rail;
- star ratings/average-review framing;
- fake match percentage;
- visit -> positive preference assumption;
- equal visual weight for all three roles;
- always-present supporting modules;
- account wall before value;
- session rejection silently becoming durable dislike;
- unavailable operational facts presented as known;
- LLM-generated unsupported `Why this fits` copy.

---

## 28. Codex implementation boundary

### Codex may

- implement the approved composed Home response;
- reduce `(tabs)/index.tsx` to a presentation/orchestration shell;
- reuse UI V2 components;
- implement approved Decision Context controls;
- implement role/recovery/completion states;
- add accessibility/performance/test coverage;
- retire old Feed composition only after parity.

### Codex may not

- redefine Best Fit/Safe Bet/Wildcard;
- invent new rail types;
- invent unsupported context fields;
- use existing generic FilterSheet as a substitute for Decision Context without contract approval;
- preserve `MORE IN YOUR LANE`/`HOLE-IN-THE-WALL` merely because they already exist;
- keep independent frontend `useRecommendations` Home composition after backend composition is canonical;
- redesign Search/Map/Craves while implementing Feed;
- call implementation Final before runtime accessibility/device verification.

---

## 29. Acceptance criteria

Feed V2 is implementation-ready only when:

1. Best Fit/Safe Bet/Wildcard backend semantics match the Master Architecture.
2. Decision Context fields are explicitly supported or explicitly omitted.
3. Home composition response is defined.
4. every supporting module type is enumerated and truthfully sourced;
5. rejection lifecycle is defined;
6. completion lifecycle is defined;
7. hard-constraint recovery is defined;
8. cold start is defined without fake personalization;
9. loading/error/offline/stale/missing-media states are covered;
10. analytics semantics are defined;
11. privacy impact is named;
12. Codex has no unresolved product/UX/data ambiguity to silently decide.

Feed V2 is Final only after implementation, automated QA, runtime accessibility QA, real-data/photo QA, and device QA.

---

## 30. Readiness

**Current:** YELLOW — architecture specified, implementation dependencies intentionally unresolved.

### Buildable now after FV2-00 approval

- evidence resolver over existing Rank/visit/save/recommendation data;
- deterministic candidate evaluation;
- shared Decision Session semantic upgrade;
- backend composition policy;
- Home response simplification;
- rejection/completion session mechanics;
- frontend V2 migration;
- privacy/telemetry updates.

### Data-limited / not implementation blockers

- learned position debiasing;
- adaptive bandits/UCB;
- learned novelty calibration;
- CRAVE-trained embeddings.

These are not required for Feed V2 V1.

---

## 31. Traceability

Backward dependencies:

- `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md`;
- `CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md`;
- `CRAVE_ROUTE_FLOW_MAP.md`;
- `CRAVE_DATA_STATE_MAP.md`;
- `CRAVE_PRIVACY_PERMISSION_MATRIX.md`;
- `CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md`;
- `CRAVE_DESIGN_SYSTEM.md`;
- `CRAVE_COMPONENT_REGISTRY.md`;
- `CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md`;
- `CRAVE_SCREEN_CONTRACT_CRAVES.md`;
- `CRAVE_SCREEN_CONTRACT_SEARCH.md`;
- `CRAVE_API_INTEGRATION_CONTRACTS.md`;
- `CRAVE_FEED_V2_MASTER_ARCHITECTURE.md`.

Implementation traceability:

- `CRAVE_FEED_V2_MIGRATION_MATRIX.md`.

---

## 32. Screen lock

> **Feed is a decision system rendered as a calm food-first Home surface, not an endless recommendation feed.**

> **The first viewport should make the strongest decision legible before asking the user to browse.**

> **Once CRAVE has helped the user decide, Home is allowed to become quiet.**
