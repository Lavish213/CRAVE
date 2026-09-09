# CRAVE Feed V2 Master Architecture

**Status:** DESIGN/ARCHITECTURE CONTRACT — implementation not started
**Date:** 2026-09-08
**Authority:** This document governs Feed/Home intelligence and composition where it is more specific than older Feed implementation notes. It does not supersede the product constitution, evidence hierarchy, privacy matrix, Search contract, Craves contract, Rank contract, or Place Detail contract.

---

## 0. Executive decision

Feed V2 is **not another recommender**.

It is a consolidation and upgrade of CRAVE's existing recommendation systems so Home can make a small number of truthful, context-aware food decisions without creating a fourth competing ranking authority.

The target is:

> **One Home composition authority, multiple reusable evidence and ranking inputs.**

The Home screen must answer:

> **What food decisions are worth this user's attention right now?**

It must not answer:

> What restaurants can CRAVE keep showing so the user keeps scrolling?

CRAVE optimizes for **decision confidence**, not dwell time, scroll depth, card count, or session duration.

A user who opens CRAVE, confidently chooses dinner, and leaves quickly is a successful Feed session.

---

## 1. Why Feed V2 exists

The current system has good foundations but split authority.

Today:

1. `backend/app/services/feed/feed_ranker.py` ranks generic/local Feed candidates.
2. `backend/app/services/decision_session/decision_session_builder.py` assigns `best_fit`, `safe_bet`, and `wildcard` from that Feed-ranked list.
3. `backend/app/services/social/recommendation_service.py` independently generates collaborative-filtered personalized recommendations from `PlaceRanking` similarity.
4. `/craves/reasoned` reuses the Decision Session builder over the user's saved pool.
5. Search has its own correct query-specific retrieve-wide -> rank -> paginate flow.
6. `frontend/app/(tabs)/index.tsx` independently fetches Decision Session, general Feed, personalized recommendations, Craves, filters, city, and location and then creates Home sections itself.

That produces multiple partially overlapping interpretations of recommendation meaning.

Current semantic overclaims include:

- `Best Fit` = the first generic Feed-ranked candidate, not a fully personalized contextual fit.
- `Wildcard` = a deterministic exploration boost plus category difference, not a personalized stretch at the edge of the user's taste.
- `MORE IN YOUR LANE` = a collaborative-filter list that is personalized, but not aware of the active Decision Session's current occasion, rejection history, or temporary intent.
- `HOLE-IN-THE-WALL` = currently inferred from a catalog tier (`gem`), even though tier is not venue-character evidence.

Feed V2 corrects those semantics before visual polish makes them look more authoritative than the backend can support.

---

## 2. Research synthesis translated into CRAVE rules

External recommender-system research and production engineering repeatedly surface the same failures users complain about:

- overspecialization: one interaction becomes the user's whole identity;
- repetition: users repeatedly see the same or near-identical items;
- engagement optimization masquerading as personalization;
- explicit "not interested" feedback failing to change the system;
- popularity swallowing long-tail discovery;
- stale or low-quality evidence being presented with equal confidence;
- opaque ranking without a useful explanation;
- infinite recommendation loops that increase effort rather than reduce it;
- random diversity presented as serendipity;
- position/exposure feedback loops that cause the system to learn from its own presentation bias.

Production references used in the Feed research included DoorDash's candidate-generation/exploration and homepage-personalization engineering, Uber Eats recommendation/ranking and position-bias work, recommender-system research on serendipity, overspecialization, popularity bias, choice overload, and user satisfaction, plus qualitative complaints from Reddit and food-app reviews.

CRAVE converts those findings into ten non-negotiable laws:

1. **Never optimize Feed for scrolling.**
2. **Never infer a person's entire taste from one behavior.**
3. **Explicit correction outranks passive inference.**
4. **Do not repeatedly recommend resolved/rejected candidates.**
5. **Similarity alone is not personalization.**
6. **Novelty must remain relevant.**
7. **Freshness and provenance affect recommendation confidence.**
8. **Important recommendations need concise human explanations.**
9. **Popularity is evidence, never destiny.**
10. **A successful Feed is allowed to end.**

Research informs these principles. The repository determines what can actually ship now.

---

## 3. Constitutional Feed V2 principles

### 3.1 Decision mode is bounded

Decision Mode exists to reduce uncertainty and end.

It must not silently become an infinite feed after the initial answer set.

Explore Mode may continue, but it must be deliberately entered.

### 3.2 Durable taste is not current intent

A user's long-term preference and tonight's preference are separate concepts.

Example:

- durable evidence: the user consistently ranks ramen highly;
- session evidence: the user rejects ramen twice tonight.

Correct inference:

> Not ramen tonight.

Incorrect inference:

> The user no longer likes ramen.

### 3.3 Fact is not preference

A visit answers **did this happen?**

A rank/reaction answers **how did the user feel?**

A save answers **did the user express prospective interest?**

An exposure answers **did CRAVE show it?**

These cannot be flattened into one generic engagement score.

### 3.4 Evidence strength is action-specific

The same evidence may be sufficient for one action and insufficient for another.

Example already present in CRAVE:

- inferred visit may graduate a place from active Want-to-Try Craves;
- inferred visit may not unlock Rank;
- inferred visit must not imply positive taste.

### 3.5 Explain the decision, not the model

The user needs:

> Why this, for me, now?

They do not need a dump of internal scores or model reasoning.

Explanations must be short, evidence-backed, and omitted when evidence does not support them.

### 3.6 Missing evidence is not negative evidence

Examples:

- no photo != bad place;
- no recent hours verification != closed;
- low personalization confidence != low restaurant quality;
- few ranked restaurants != weak user taste.

### 3.7 Feed ranking and Feed composition are different systems

Ranking asks:

> Which candidates are strongest under the current evidence/context?

Composition asks:

> Which of those candidates deserve scarce Home attention, and in what role?

One function must not silently own both responsibilities.

---

## 4. Existing systems to preserve rather than duplicate

### 4.1 RecommendationContext

`frontend/src/api/recommendationContext.ts` already provides the shared vocabulary for:

- surface;
- location;
- time context;
- query;
- hard constraints;
- soft constraints;
- novelty;
- candidate scope;
- session id;
- cursor.

Feed V2 extends this contract only when a new field is genuinely supported by runtime behavior.

Do not create a competing `DecisionContext` type with overlapping semantics.

### 4.2 Decision Session builder

`build_decision_session()` remains the canonical shared role-assignment boundary.

It is upgraded, not replaced.

Its strongest existing invariant must remain:

> **Never fabricate three cards.**

If only one candidate legitimately qualifies, one card is correct.

### 4.3 Collaborative-filter recommendations

`backend/app/services/social/recommendation_service.py` already implements lightweight collaborative filtering over `PlaceRanking` rows.

It remains useful as:

- a candidate source;
- a personal-fit signal;
- a cold-start-aware personalized recommendation source where enough co-ranking exists.

It must stop acting as an independent Home section authority once Feed V2 composition owns Home.

### 4.4 Visit evidence

`visit_evidence_service.py` already separates factual history and recommendation influence and uses source-scoped retraction.

Preserve that design.

### 4.5 Rank

Rank remains one of CRAVE's highest-authority durable taste inputs because ranking requires declared/verified visit evidence and captures explicit comparative preference.

### 4.6 Craves

`/craves/reasoned` correctly changes the candidate universe while reusing the Decision Session role engine.

Preserve:

> Candidate universe may differ by surface; role semantics do not.

### 4.7 Recommendation Ledger

The recommendation ledger already stores surface, event, position, percentile, session, search session, city, and Decision Session role.

The current Home uses FlashList viewability (`50%` visible for at least `250ms`) before emitting Feed/Decision Session impressions.

Therefore:

- viewability instrumentation already exists in current Home;
- stale comments that describe Feed impressions as fetch-only must be corrected;
- richer event fields should be added only when the product interaction genuinely exists.

### 4.8 PlaceClaim / PlaceTruth

These tables remain factual restaurant truth systems and must not be repurposed for user taste.

However, their architectural philosophy is a useful precedent:

- preserve provenance;
- preserve confidence;
- distinguish raw evidence from resolved interpretation;
- keep resolver output auditable/versioned.

Feed V2's evidence resolver should follow those principles without sharing factual-claim storage.

### 4.9 Cursor snapshot

`feed_cursor_snapshot.py` provides stable ordered snapshots and scope-matched cursors.

This is a good foundation for Explore-mode pagination and potentially composed Home snapshot stability.

---

## 5. Canonical Feed V2 architecture

```text
RecommendationContext
        │
        ▼
Candidate Retrieval
        │
        ├── local/catalog candidates
        ├── collaborative-filter candidates
        ├── Craves candidates
        └── context-specific candidates
        │
        ▼
Hard Constraint Gate
        │
        ▼
User Evidence Resolver
        │
        ├── Rank evidence
        ├── explicit reaction/correction evidence
        ├── Save/Craves evidence
        ├── visit/history evidence
        └── exposure/session evidence
        │
        ▼
Candidate Evaluation
        │
        ├── personal_fit
        ├── context_fit
        ├── evidence_confidence
        ├── novelty
        ├── operational_fit
        └── resolved/exposure state
        │
        ▼
Decision Session Role Assignment
        │
        ├── Best Fit
        ├── Safe Bet
        └── Wildcard
        │
        ▼
Feed Composition Policy
        │
        ├── Decision Set
        ├── optional supporting module(s)
        └── completion state
        │
        ▼
Stable Session / Snapshot
        │
        ▼
Thin Home Renderer
```

---

## 6. Candidate retrieval contract

### 6.1 Retrieval must precede ranking

Feed adopts Search's already-learned invariant:

> **Retrieve a sufficiently broad bounded candidate pool -> apply hard constraints -> evaluate/rank -> diversify -> compose -> paginate/present.**

Never cut an arbitrary page before the intelligence that could promote a candidate runs.

### 6.2 Candidate sources are not final authorities

A candidate can enter the pool through:

- generic/local catalog ranking;
- collaborative filtering;
- Craves;
- proximity/context;
- future dish intelligence;
- future controlled exploration.

Entering the pool does not guarantee presentation.

### 6.3 Popularity

Popularity/rank percentile may be one quality signal.

It may not override strong personal/context mismatch.

### 6.4 Random discovery

Random or deterministic catalog exploration may still be useful for generic Explore-mode variety.

It must never be labeled `Wildcard` or treated as personalized novelty.

---

## 7. Hard constraint gate

Hard constraints must be enforced before candidate role assignment.

Examples:

- allergy;
- dietary/religious/ethical exclusions when represented as hard constraints;
- explicit protected constraints supplied by the recommendation contract;
- known impossible geographic bounds when the user made them hard.

Hard constraints may never be silently relaxed.

If no candidates survive:

1. tell the truth;
2. name the exact constraint causing the shortage when known;
3. require explicit user action before relaxing a hard constraint.

Soft preferences may be relaxed only through the product's explicit recovery rules.

---

## 8. User Evidence Resolver

Feed V2 introduces one new conceptual authority: a typed evidence resolver.

Suggested implementation file:

`backend/app/services/feed/user_evidence_resolver.py`

The resolver does not produce a single "user score."

It resolves evidence into separate meanings.

### 8.1 Durable preference evidence

Highest authority:

- explicit Taste correction when that model exists;
- Rank comparison/result;
- explicit Loved / Good / Not for me reaction once the posting/quick-take system exists.

Strong but below direct preference:

- repeated intentional saves or repeated dish-level preference evidence when supported.

### 8.2 Prospective intent evidence

- native Save;
- imported/matched Crave with provenance preserved;
- repeated deliberate Place Detail engagement if later proven useful.

A saved place and an imported social sighting may both enter Craves but need not carry identical long-term taste weight.

Collection membership and recommendation evidence strength are separate concepts.

### 8.3 Factual history

- declared visit;
- verified visit;
- inferred visit where appropriate.

A visit alone must not imply positive taste.

### 8.4 Session evidence

- current context override;
- current novelty choice;
- current Decision Session rejection;
- full-set rejection count;
- commitment;
- temporary "not tonight" signals.

Session evidence does not silently rewrite durable taste.

### 8.5 Exposure evidence

- true visible recommendation impression;
- click;
- Save outcome;
- Rank outcome.

Impression is weak evidence and primarily useful for saturation/exposure control and future evaluation.

### 8.6 Explicit negative precedence

An explicit negative signal must beat passive positive inference.

Examples:

- `Not for me` must override repeated Feed impressions;
- a deliberate "less of this" correction must materially change later recommendation behavior;
- two session rejections may suppress a category tonight without creating a permanent dislike.

---

## 9. Candidate evaluation contract

Suggested implementation file:

`backend/app/services/feed/feed_candidate_evaluator.py`

Phase 1 must be deterministic, inspectable, and testable.

Do not build heavy ML infrastructure before CRAVE has sufficient truthful outcome volume.

Candidate evaluation should produce separate dimensions.

### 9.1 `personal_fit`

How well the candidate aligns with durable user preference evidence.

Possible current inputs:

- Rank history;
- collaborative-filter recommendation support;
- category/cuisine tendencies derived from ranked places;
- negative ranking state;
- saved/visited/resolved status where relevant.

### 9.2 `context_fit`

How suitable the candidate is for the current Decision Session context.

Current support is limited; initially this may include:

- location/city;
- time context where available;
- active hard/soft constraints;
- session rejections;
- novelty mode.

Do not claim occasion/budget/travel intelligence until those inputs are actually wired.

### 9.3 `evidence_confidence`

How much evidence supports the personal/context conclusion.

This is not restaurant quality.

Low confidence means CRAVE knows less about the match.

### 9.4 `novelty`

Distance from established user preference, bounded by minimum relevance.

A true Wildcard must be:

- meaningfully outside the user's normal pattern;
- still contextually viable;
- supported by enough evidence to be worth the stretch.

### 9.5 `operational_fit`

Known operational truth relevant to acting now, such as:

- closed/open when trustworthy;
- distance/reachability;
- stale/unknown hours state;
- future reservation/delivery capability only if real integrations exist.

Unknown operational data must lower operational confidence rather than fabricate a negative fact.

### 9.6 `resolved_state`

Tracks whether the user has:

- rejected;
- saved;
- visited;
- ranked;
- committed;
- recently consumed;
- been repeatedly exposed.

Resolved candidates should not keep returning as though nothing happened.

---

## 10. Best Fit / Safe Bet / Wildcard semantics

The existing role names stay. Their semantics are upgraded.

### 10.1 Best Fit

The strongest overall decision CRAVE can currently support under:

- durable taste;
- current context;
- hard constraints;
- operational viability;
- evidence confidence;
- resolved-state suppression.

Best Fit must no longer mean merely `ranked[0]` from the generic Feed ranker.

### 10.2 Safe Bet

A candidate with:

- strong established alignment;
- high evidence confidence;
- lower uncertainty;
- contextual viability;
- sufficient distinction from Best Fit to be a real alternative.

"Safe" means lower uncertainty, not boring/popular/chain.

### 10.3 Wildcard

A credible stretch:

- more novel than Best Fit/Safe Bet;
- still above minimum relevance/context thresholds;
- supported by evidence;
- not simply a random category or deterministic hash boost.

### 10.4 Missing roles

A role that does not have a qualifying candidate is omitted.

Never pad.

---

## 11. Feed Composition Policy

Suggested implementation file:

`backend/app/services/feed/feed_composition_policy.py`

This becomes the single Home composition authority.

It decides:

1. what belongs in the primary Decision Set;
2. whether a supporting module deserves to exist;
3. whether the session is complete;
4. whether Explore More should be offered.

### 11.1 Primary Decision Set

Maximum role set:

- Best Fit;
- Safe Bet;
- Wildcard.

Visually, Best Fit is primary. The other roles are subordinate alternatives.

### 11.2 Supporting modules

Supporting modules are conditional, not permanent slots.

Examples when evidence truly supports them:

- From your Craves;
- Worth stretching for;
- Something different;
- Saved and nearby;
- Because you loved X;
- Local discovery.

No module should render merely because Home has space.

### 11.3 Prohibited fabricated modules

Do not create:

- Trending;
- Popular near you as a recommendation authority;
- Hole-in-the-wall unless CRAVE has actual venue-character evidence;
- generic catalog-tier rails disguised as personalization.

### 11.4 Composition count

There is no scientifically magic number of supporting modules.

The correct number is the number justified by evidence and user value, including zero.

---

## 12. Decision Session state and lifecycle

Session state may remain ephemeral unless persistence across app restarts is a product requirement.

Potential runtime fields:

- `session_id`;
- current context overrides;
- rejected place ids;
- temporary category suppression;
- full-set rejection count;
- commitment place id;
- session start/context identity;
- optional novelty mode.

Do not create persistent database state merely because a field exists conceptually.

### 12.1 Rejection

Reject replaces the role only if another candidate legitimately qualifies.

### 12.2 Two full-set rejections

After two complete-set rejections, CRAVE must stop silently regenerating.

Ask what is off tonight or send the user to explicit Search/intent refinement.

### 12.3 Commitment

Once the user commits to a restaurant:

- Decision Mode enters completion state;
- the chosen restaurant stays accessible;
- Directions/View Place become prominent;
- additional recommendations recede.

### 12.4 Reset

Session resets on the canonical conditions already defined by product doctrine: new context/occasion, explicit reset, or new day/session boundary as specified by the finalized screen contract.

---

## 13. Home completion state

Feed must be able to say:

> **You're set.**

Completion is not an empty state or error.

It is a successful state.

A completion response contains:

- committed restaurant;
- relevant context;
- primary action such as Directions/View Place;
- optional Save state;
- no manufactured Decision Session replacements.

Explore remains available as a deliberate secondary action.

---

## 14. Explore mode

Explore is distinct from Decision Mode.

Explore may use:

- stable cursor snapshots;
- bounded pagination;
- generic/local candidate discovery;
- personalized candidate sources;
- category diversity;
- explicit "Show more" or Explore More continuation.

Explore does not retroactively change the semantics of Best Fit/Safe Bet/Wildcard.

Home must not silently blend a bounded decision set into infinite scrolling.

---

## 15. Explanation contract

Every important recommendation reason must be grounded in real available evidence.

Good:

> You keep ranking rich noodle spots highly, and this one is inside your usual dinner range.

Good low-confidence case:

> You haven't ranked enough Thai spots yet, but this matches places you save and is nearby.

Bad:

> 98% match.

Bad:

> Perfect for you.

Bad:

> Hidden gem.

unless the system can support those claims.

The explanation layer must receive reason codes/evidence references from the evaluation/composition path rather than inventing copy from the final restaurant alone.

---

## 16. Confidence and uncertainty language

Different uncertainty sources need different language.

Examples:

- personalization uncertainty: `Still learning your Thai preferences`;
- hours freshness: `Hours not recently verified`;
- menu coverage: `Limited menu information`;
- media: `Photo unavailable`;
- sparse personal evidence: `Few matching rankings yet`.

Do not use `Still learning` as a generic label for all missing data.

---

## 17. Freshness and provenance

Recommendation confidence must be affected by the trustworthiness of underlying facts.

Restaurant evidence should distinguish:

- known current fact;
- stale fact;
- missing fact;
- inferred personal match;
- explicit personal evidence.

`PlaceClaim`/`PlaceTruth` remain the factual provenance source where applicable.

Feed evaluation may consume resolved operational facts, but it must not bypass the truth system and directly treat raw claims as canonical facts unless a specific contract says so.

---

## 18. Bias and exposure control

### 18.1 Phase 1

Buildable now:

- repeated-exposure suppression;
- recent-consumption suppression;
- explicit rejection suppression;
- category saturation limits;
- resolved-state suppression;
- position/viewability-aware analytics collection.

### 18.2 Later, data-limited

Do not prematurely build:

- learned position-debiasing models;
- contextual bandits/UCB;
- adaptive learned exploration;
- large embedding models trained on CRAVE behavior.

These require sufficient event volume and truthful outcomes.

A heuristic-first system is preferred until model complexity is justified by evidence.

---

## 19. Cold start

Cold start must be useful without fake personalization.

The existing collaborative-filter service already falls back to highest-ranked active places when no similar users exist.

Feed V2 should combine cold-start inputs conservatively:

- city/location quality;
- onboarding known-restaurant reactions once available;
- dietary/allergy hard constraints;
- coarse cuisine affinity when supplied;
- novelty starting position;
- known saves/Craves if signed in.

Do not say `because you love X` until CRAVE actually has evidence that the user loves X.

Low confidence should be honest but not apologetic.

---

## 20. Privacy and data lifecycle

Feed V2 introduces richer personalization behavior but does not convert CRAVE into ad tracking.

Before release, privacy documentation must accurately describe:

- recommendation interaction data;
- session-level personalization signals when persisted;
- how saves/rankings/visits affect recommendations;
- location use in recommendations;
- deletion behavior;
- retention of recommendation events;
- controls for personalization when those controls exist.

### 20.1 Persistence minimization

Prefer session-local memory for temporary intent/rejections unless cross-session persistence is explicitly required.

### 20.2 Deletion

If Feed V2 adds persisted user-derived state, account deletion/reset contracts must include it.

### 20.3 No external personal surveillance

Feed may not use scraped/purchased external personal evidence.

---

## 21. Analytics and success metrics

Primary success metrics should reflect decision quality.

Recommended:

- time to confident decision;
- recommendation acceptance/commitment;
- post-visit Rank agreement;
- correction frequency;
- abandonment without decision;
- confident rejection;
- novelty acceptance;
- repeat trust/return after successful decisions.

Diagnostic only, never optimization targets:

- session duration;
- scroll depth;
- cards viewed;
- raw impression count.

A shorter session can be better.

---

## 22. Performance rules

Home must feel immediate.

Do not place slow LLM generation in the Home request path.

If LLMs are later used, appropriate jobs include offline/async derivation of:

- semantic restaurant attributes;
- explanation candidates;
- taste trait summaries;
- content concepts.

Live Home should use deterministic/fast retrieval, evaluation, and composition.

---

## 23. Capability status matrix

### AVAILABLE NOW

- PlaceRanking history;
- collaborative filtering;
- saves/Craves;
- visit evidence;
- city/location context;
- rank percentile;
- operational hours where truth data exists;
- recommendation event ledger;
- true Home viewability instrumentation;
- stable cursor snapshots;
- shared Decision Session builder;
- provenance-bearing saves/reason role;
- hard/soft recommendation constraint type contract.

### REQUIRES EXTENSION

- richer current-intent inputs;
- session rejection state;
- explicit Decision Session corrections;
- User Evidence Resolver;
- contextual candidate evaluator;
- evidence-backed confidence model;
- real Wildcard novelty semantics;
- completion state;
- backend Home composition authority;
- exposure-decay and recent-consumption suppression;
- composed Home response/DTO if chosen.

### DATA-LIMITED

- learned novelty calibration;
- learned position debiasing;
- adaptive exploration;
- per-market learned weighting.

### INFRA-BLOCKED / NOT JUSTIFIED YET

- contextual bandits/UCB;
- heavy ML ranking infrastructure;
- online embeddings trained from CRAVE behavior;
- real-time LLM-composed Home.

### POST-V1

- dish-level ranking influence;
- sophisticated route-aware context;
- full future-time context intelligence;
- full reservation/order context integration.

### PROHIBITED

- engagement-maximizing Feed ranking;
- silent hard-constraint relaxation;
- fake match percentages;
- popularity as substitute for personal fit;
- random discovery called Wildcard;
- visit interpreted as positive preference without sentiment;
- endless recommendation regeneration after the decision is solved.

---

## 24. Required implementation boundaries

### Codex may

- consolidate existing recommendation inputs;
- introduce the resolver/evaluator/composition boundaries described here;
- upgrade `build_decision_session()` while preserving its shared role;
- extend RecommendationContext with approved fields;
- make Home consume one composed response;
- retire duplicate Home composition after verified parity;
- add tests and telemetry required by this architecture.

### Codex may not

- create a second competing Decision Session role engine;
- invent unsupported context fields and treat them as populated;
- introduce ML/bandits because production research uses them at larger scale;
- treat `gem` as `hole-in-the-wall`;
- treat random discovery sampling as personal novelty;
- turn visit history into positive preference automatically;
- persist temporary session state without a contract need;
- redesign Search/Map/Craves semantics while implementing Feed;
- visually redesign Home before the Feed V2 screen contract is approved.

---

## 25. Implementation waves

### FV2-00 — Doctrine and contracts

- this Master Architecture;
- Feed Screen Contract V2;
- file-by-file migration matrix;
- canonical role/confidence/evidence semantics.

No production behavior changes.

### FV2-01 — Evidence authority

- implement typed User Evidence Resolver;
- reuse Rank/visit/save/recommendation data;
- preserve provenance and action-specific strength;
- tests first-class.

### FV2-02 — Context + candidate evaluation

- extend RecommendationContext only with supported fields;
- implement deterministic candidate dimensions;
- hard-constraint gate;
- saturation/resolved-state rules.

### FV2-03 — Decision Session upgrade

- upgrade shared role assignment;
- preserve Craves reuse;
- preserve no-padding invariant;
- add low-confidence semantics/reasons.

### FV2-04 — Home composition authority

- backend composition policy;
- composed Home DTO/endpoint if selected;
- remove frontend section invention;
- support optional module omission.

### FV2-05 — Session cognition

- temporary rejection state;
- two-full-set rejection recovery;
- commitment/completion;
- context override lifecycle.

### FV2-06 — Home UI V2

- visual migration only after intelligence contract is real;
- use production UI V2 tokens/primitives/components;
- do not redesign during implementation.

### FV2-07 — Telemetry and privacy

- correct stale recommendation-event documentation;
- add only real event types;
- privacy/data lifecycle update;
- deletion/reset propagation.

### FV2-08 — Retirement

- remove independent Home `useRecommendations` composition;
- remove unsupported `hole_in_wall` semantics;
- retire/dead-path duplicate feed builders after dependency proof;
- remove legacy page-dependent Home feed path after parity.

### FV2-09 — Certification

- backend/full frontend suites;
- sparse-user/cold-start fixtures;
- thin-city fixtures;
- low-confidence fixtures;
- rejection/completion lifecycle;
- accessibility;
- hostile photo/content fixtures;
- offline/stale behavior;
- real device QA.

---

## 26. Definition of Done

Feed V2 is not complete until all of the following are true:

1. Home has one composition authority.
2. Best Fit is not merely generic rank #1.
3. Safe Bet expresses confidence/low uncertainty, not popularity.
4. Wildcard is evidence-backed novelty, not random discovery.
5. Rank, visit, Save, Craves, exposure, and session evidence retain distinct meanings.
6. Explicit negative feedback outranks passive inference.
7. Decision Session never fabricates missing roles.
8. Hard constraints never relax silently.
9. Supporting modules can be absent.
10. Home can enter a successful `You're set` completion state.
11. Decision Mode does not silently become infinite Explore.
12. Recommendation reasons are evidence-backed and concise.
13. Low-confidence language describes the actual uncertainty source.
14. Privacy/data lifecycle reflects persisted personalization state.
15. Legacy duplicate Home authority is retired after parity.
16. Automated tests and device verification prove runtime behavior.

---

## 27. Canonical lock

> **Feed V2 does not create another recommender. It consolidates CRAVE's existing Feed ranker, collaborative filtering, Decision Session, Craves, Rank, visit evidence, recommendation context, and recommendation ledger into one truthful Home decision architecture.**

> **Home shows the next useful decision, not everything CRAVE knows.**

> **Decision Mode ends. Explore Mode may continue only when deliberately entered.**
