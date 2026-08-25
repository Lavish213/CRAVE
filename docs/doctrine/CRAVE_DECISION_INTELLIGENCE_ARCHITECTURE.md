# CRAVE Decision Intelligence Architecture

## Production System Specification - V1 to V5

**Status:** Architecture baseline\
**Purpose:** Define how CRAVE turns catalog evidence, user taste, live
context, and outcomes into trustworthy food decisions.\
**Primary rule:** CRAVE is not a single score, a single recommender, or
an LLM that picks restaurants. It is a staged decision system with
auditable evidence and independently evolvable components.

------------------------------------------------------------------------

## 1. Product Objective

CRAVE's core job is:

> Turn "I don't know what to eat" into a confident decision that gets
> better for each user over time.

The intelligence system must optimize for **successful food decisions**,
not raw clicks, feed depth, session duration, or the number of
recommendations viewed.

A successful system must:

1.  Understand what objectively deserves consideration.
2.  Understand the user's durable taste.
3.  Understand recent behavior without confusing it with durable taste.
4.  Understand what the user wants right now.
5.  Respect hard reality: open status, geography, budget, dietary
    restrictions, availability, and data freshness.
6.  Manage recommendation risk.
7.  Avoid repetitive personalization.
8.  Preserve user control.
9.  Explain recommendations from real evidence.
10. Learn from the outcome after a decision.
11. Make every recommendation reconstructable.
12. Improve without requiring CRAVE to replace deterministic rules with
    unnecessary ML.

------------------------------------------------------------------------

## 2. Non-Negotiable Architectural Doctrine

### 2.1 Never create one master CRAVE score

The following concepts are not interchangeable:

-   catalog completeness
-   place quality
-   dish quality
-   authenticity
-   authority
-   freshness
-   popularity
-   personal affinity
-   contextual relevance
-   confidence
-   risk
-   diversity
-   exploration value
-   recommendation outcome

A high catalog score does not mean a user should eat there tonight.

### 2.2 Evidence first, derived intelligence second

CRAVE stores what actually happened, then derives profiles and features
from those events.

Do not permanently mutate an unexplained field such as:

`user.ramen_score += 1`

without retaining the event that caused the update.

### 2.3 Long-term taste, recent behavior, and current intent are separate

CRAVE must distinguish:

-   **Long-term taste:** "I generally love ramen."
-   **Recent behavior:** "I have eaten ramen three times recently."
-   **Current intent:** "I do not want ramen tonight."

Current intent may temporarily overpower long-term taste without
corrupting it.

### 2.4 Dish and restaurant affinity are separate

A user may love a restaurant but dislike one dish, or love one dish at
an otherwise average restaurant.

CRAVE therefore treats dishes and places as first-class recommendation
entities.

### 2.5 Retrieval, ranking, reranking, and presentation are separate stages

Do not turn `feed_ranker.py` into a 2,000-line recommendation brain.

Candidate generation decides **what may compete**.

Ranking decides **how suitable each candidate is**.

Reranking decides **which combination of candidates should be shown
together**.

Presentation decides **how evidence is communicated to the user**.

### 2.6 LLMs do not own catalog truth or user memory

An LLM must never be the source of truth for:

-   whether a restaurant exists
-   whether it is open
-   menu price
-   dish existence
-   dietary compatibility
-   user preference history
-   recommendation provenance
-   recommendation score
-   outcome history

LLMs may parse ambiguous natural language or render grounded
explanations from structured evidence.

------------------------------------------------------------------------

## 3. Existing CRAVE Systems: Keep, Reframe, or Upgrade

### 3.1 Global `rank_score` -\> Place Prior

**Keep. Reframe its meaning.**

It answers:

> Before knowing the user or current situation, how much evidence
> suggests this place deserves consideration?

It does **not** answer:

> What should this user eat now?

Required evolution:

-   separate data completeness from desirability
-   retain authenticity and authority as evidence dimensions
-   introduce temporal/freshness evidence carefully
-   prevent structural completeness from masquerading as quality
-   expose confidence alongside the prior where appropriate

### 3.2 City percentile tiers

**Keep.**

City-relative percentile ranking is useful for local presentation, but
percentile alone cannot imply excellence.

A future badge should require both:

`relative_percentile_requirement AND absolute_evidence_floor`

Example:

`CRAVE Pick = city_percentile <= 5% AND evidence_confidence >= required_floor`

### 3.3 Feed Ranker

**Keep as discovery/editorial ranking only.**

The feed may deliberately favor local discovery, proximity, quality, and
variety.

It must not become the Decision Ranker.

Editorial priors must yield to explicit user intent in decision mode.

### 3.4 Deterministic exploration bump

**Deprecate as personalization matures.**

Stable pseudo-random exploration is acceptable as an MVP feed-variety
mechanism but is not intelligent exploration.

Replace it with exploration based on:

-   user exploration tolerance
-   candidate uncertainty
-   candidate novelty
-   candidate underexposure
-   taste distance
-   recommendation risk
-   prior wildcard success

### 3.5 Search

**Keep exact lookup simple. Add a second intent-search pipeline.**

Two different jobs:

**Lookup** - "Marufuku" - retrieve the known entity efficiently

**Intent discovery** - "spicy ramen under \$20 open late" - parse
intent - apply constraints - generate candidates - personalize ranking

Do not contaminate exact retrieval with unnecessary recommendation
behavior.

### 3.6 Personal pairwise rankings

**Keep as one taste signal.**

Pairwise restaurant comparisons are valuable evidence of relative
preference within a domain.

They are not the user's complete taste model.

### 3.7 Food image/video classifier

**Keep isolated from ranking.**

Long term, separate:

1.  food/not-food or OOD validity gate
2.  food classification

A closed-set classifier should not be treated as a reliable non-food
detector.

------------------------------------------------------------------------

## 4. Canonical End-to-End Decision Pipeline

``` text
VERIFIED CATALOG
    |
    +-- Place Intelligence
    +-- Dish Intelligence
    +-- Menu Intelligence
    +-- Freshness / Availability Confidence
    |
USER INTELLIGENCE
    |
    +-- Explicit Preferences
    +-- Long-Term Taste
    +-- Recent Behavior
    +-- Taste Modes / Journeys
    +-- Exploration Profile
    +-- Prior Outcomes
    |
CURRENT DECISION CONTEXT
    |
    +-- Craving / Intent
    +-- Meal Period
    +-- Budget
    +-- Geography
    +-- Party
    +-- Occasion
    +-- Dietary Hard Rules
    +-- Temporary Exclusions
    |
    v
CANDIDATE GENERATION
    |
    v
HARD FILTERING
    |
    v
PERSONALIZED RELEVANCE RANKING
    |
    v
QUALITY / FRESHNESS / CONFIDENCE ADJUSTMENT
    |
    v
RECOMMENDATION RISK
    |
    v
REPETITION SUPPRESSION
    |
    v
SEMANTIC DIVERSIFICATION
    |
    v
ROLE ASSIGNMENT
 SAFE BET / BEST TONIGHT / WILDCARD
    |
    v
GROUNDED EXPLANATIONS + TRADEOFFS
    |
    v
USER ACTION
    |
    v
OUTCOME CAPTURE
    |
    v
TASTE / CONTEXT LEARNING
    |
    +--------------------> NEXT DECISION
```

------------------------------------------------------------------------

## 5. Canonical Event Architecture

Raw meaningful events are the historical source of truth.

### 5.1 Core event types

-   recommendation_session_started
-   recommendation_candidate_impressed
-   dish_opened
-   place_opened
-   menu_opened
-   candidate_saved
-   candidate_rejected
-   refinement_applied
-   candidate_selected
-   directions_started
-   reservation_started
-   order_started
-   visit_confirmed
-   would_get_again_submitted
-   preference_corrected
-   taste_signal_excluded
-   recommendation_session_abandoned

### 5.2 Every recommendation event should preserve relevant provenance

Where applicable:

-   event_id
-   user_id or anonymous_session_id
-   session_id
-   recommendation_session_id
-   timestamp
-   dish_id
-   place_id
-   menu_item_id
-   algorithm_version
-   user_profile_version
-   candidate_rank
-   visual_position
-   recommendation_role
-   reason_codes
-   current context snapshot
-   candidate score components
-   data freshness/confidence snapshot
-   experiment assignment

### 5.3 Why this matters

CRAVE must be able to answer:

> What did we show this user?

> Why did we show it?

> What evidence existed at the time?

> What version of the algorithm produced it?

> What did the user do?

> Was the meal ultimately successful?

------------------------------------------------------------------------

## 6. User Intelligence Model

### Layer A - Explicit Preferences

Highest-authority user-provided facts.

Examples:

-   allergies
-   dietary restrictions
-   explicit dislikes
-   explicit likes
-   budget rules
-   "less of this"
-   "do not learn from this"

Safety-critical or hard dietary constraints must never be inferred away.

### Layer B - Long-Term Taste

Slow-moving derived affinities:

-   cuisine
-   dish family
-   flavor
-   ingredient
-   protein
-   texture
-   restaurant
-   dish
-   price behavior
-   travel tolerance
-   wait tolerance
-   portion preference
-   exploration tolerance

Each inferred preference should carry:

-   affinity
-   confidence
-   evidence_count
-   first_observed_at
-   last_observed_at
-   source diversity where useful

### Layer C - Recent Behavior

Responsive short-horizon evidence:

-   recent dishes
-   recent cuisines
-   recent searches
-   recent selections
-   recent rejections
-   recent successful recommendations
-   recent repeated foods

Recent behavior helps infer changing intent but does not automatically
rewrite durable taste.

### Layer D - Taste Modes / Journeys

A mature user may contain multiple food modes rather than one averaged
taste vector.

Examples:

-   cheap weekday lunch
-   comfort-food evening
-   date night
-   adventurous weekend
-   late-night convenience
-   high-protein phase
-   exploring Korean food

These modes may emerge, strengthen, mature, fade, or disappear.

### Layer E - Current Decision Context

Ephemeral state:

-   "spicy"
-   "under \$25"
-   "15 minutes"
-   "not pizza"
-   "two people"
-   "quick"
-   "date night"

This state expires or heavily decays after the decision.

------------------------------------------------------------------------

## 7. Signal Interpretation

CRAVE must not interpret all behavior equally.

### Weak evidence

-   impression
-   brief detail view

### Moderate evidence

-   save
-   meaningful menu exploration
-   repeated detail exploration

### Strong evidence

-   selected for the meal
-   directions started
-   reservation/order initiated
-   confirmed visit

### Very strong evidence

-   "Definitely would get again"
-   repeated selection of the same dish
-   explicit "more like this"

### Negative signals require semantic interpretation

`Too far` - update travel/context tolerance - do not lower cuisine
affinity

`Too expensive` - update price/context tolerance - do not mark
restaurant as disliked

`Had this recently` - temporary repetition suppression - do not reduce
long-term taste

`Not craving it` - current-context negative - little or no long-term
penalty

`Don't like this` - strong persistent negative

`Bad experience` - outcome signal that may affect place/dish affinity
and quality confidence depending on evidence

------------------------------------------------------------------------

## 8. Candidate Generation

Candidate generation should reduce the universe before expensive
personalized ranking.

Possible sources:

-   high-quality local place candidates
-   dish candidates matching intent
-   saved items
-   previously successful places
-   new candidates similar to known preferences
-   underexplored but credible candidates
-   group-compatible candidates

Candidate generation must be recall-oriented: avoid prematurely removing
strong options.

------------------------------------------------------------------------

## 9. Hard Filters

Hard constraints happen before emotional presentation.

Examples:

-   restaurant definitively closed
-   outside maximum geography when user explicitly requires it
-   incompatible hard dietary restriction
-   unavailable when confirmed availability is required
-   invalid/stale entity beyond allowed confidence threshold
-   explicit user block
-   price above a true hard ceiling

Soft preferences should not be misclassified as hard filters.

------------------------------------------------------------------------

## 10. Personalized Relevance Ranking

The ranker should consume independent, inspectable components rather
than an opaque soup of bonuses.

Candidate-level inputs may include:

-   place prior
-   dish prior
-   dish-user affinity
-   place-user affinity
-   cuisine affinity
-   flavor affinity
-   context fit
-   price fit
-   travel fit
-   occasion fit
-   recent-intent fit
-   saved/history signals
-   active journey fit
-   quality confidence
-   freshness confidence
-   novelty fit
-   prior outcome similarity

Early CRAVE should use transparent deterministic/weighted scoring.

Machine learning should be introduced only when data volume and measured
limitations justify it.

------------------------------------------------------------------------

## 11. Recommendation Risk Engine

Being wrong has different costs.

Conceptually:

``` text
recommendation_risk =
financial_cost
+ travel_cost
+ time_cost
+ reservation_friction
+ uncertainty
+ occasion_stakes
```

Examples:

-   \$9 taco, 4 minutes away -\> lower required confidence
-   \$120 dinner, 40 minutes away, anniversary -\> very high required
    confidence

High-risk recommendations may:

-   require higher evidence confidence
-   favor safer candidates
-   expose tradeoffs more prominently
-   suppress poorly verified novelty

------------------------------------------------------------------------

## 12. Repetition and Saturation Control

A strong ranker can still become stupid through repetition.

CRAVE should distinguish:

-   **I dislike ramen** from
-   **I love ramen but have eaten it three times this week**

Recent exposure/consumption creates temporary suppression.

Long-term affinity remains intact unless evidence actually changes.

Suppression may operate on:

-   exact dish
-   restaurant
-   dish family
-   cuisine
-   flavor cluster

------------------------------------------------------------------------

## 13. Semantic Diversification

Diversity is not merely showing three different restaurant IDs.

The set should be diversified across meaningful dimensions:

-   cuisine
-   dish family
-   price
-   distance
-   familiarity
-   experience/occasion
-   restaurant
-   flavor profile

Three ramen dishes at three restaurants may still be psychologically one
option.

Diversification happens **after relevance ranking** and before final
presentation.

------------------------------------------------------------------------

## 14. Safe Bet / Best Tonight / Wildcard

These are recommendation roles, not fixed rank positions.

### Safe Bet

Goal: minimize regret.

Characteristics:

-   high taste confidence
-   familiar or strongly adjacent
-   low uncertainty
-   acceptable cost/friction
-   strong outcome evidence

### Best Tonight

Goal: maximize contextual utility.

Characteristics:

-   strongest overall fit to current intent and constraints
-   may be familiar or novel
-   balances taste, quality, context, cost, and friction

### Wildcard

Goal: controlled discovery.

Characteristics:

-   credible but more novel
-   connected to known taste through explainable similarity
-   exploration risk within user tolerance
-   not merely random

A user may receive fewer than three recommendations if CRAVE cannot
produce three trustworthy candidates.

Never manufacture a Wildcard just to fill UI.

------------------------------------------------------------------------

## 15. Constraint Relaxation

When no strong candidate satisfies all constraints, CRAVE should explain
the bottleneck and relax the least damaging constraint.

Example:

> Nothing strong matches sushi + under \$15 + within 5 minutes + open
> now.

Possible system output:

-   3 strong sushi options within 12 minutes
-   2 options around \$18-\$21 within 5 minutes

The algorithm should evaluate which relaxation causes the smallest loss
in user utility.

Never silently violate a hard constraint.

------------------------------------------------------------------------

## 16. Group Compatibility

Group decisions must not simply average everyone's scores.

Required distinction:

-   hard vetoes
-   dietary restrictions
-   budget ceilings
-   travel constraints
-   soft preferences
-   individual taste
-   group novelty tolerance

A strong group candidate maximizes collective utility while avoiding
severe dissatisfaction for one participant.

Possible future objective:

`maximize group satisfaction subject to hard constraints and minimum individual utility`

Group mode should reduce voting work, not turn dinner into Tinder for
five people.

------------------------------------------------------------------------

## 17. Grounded Recommendation Explanations

The ranker emits structured reason codes.

Examples:

-   HIGH_DISH_AFFINITY
-   HIGH_SPICY_AFFINITY
-   WITHIN_TYPICAL_BUDGET
-   WITHIN_TRAVEL_TOLERANCE
-   OPEN_NOW
-   SAVED_BEFORE
-   REPEAT_WINNER
-   SIMILAR_TO_SUCCESSFUL_DISH
-   HIGH_QUALITY_CONFIDENCE
-   CONTROLLED_NOVELTY
-   ACTIVE_JOURNEY_MATCH

A rendering layer may transform them into:

> You consistently like rich, spicy noodle dishes, and this is within
> your usual dinner budget.

Tradeoffs should also be grounded:

-   farther than usual
-   higher than normal spend
-   limited freshness confidence
-   usually busy
-   more adventurous than normal

Never ask an LLM to invent a reason after the candidate has been
selected.

------------------------------------------------------------------------

## 18. Recommendation Outcome System

CRAVE must optimize for outcomes, not persuasion.

Outcome hierarchy:

``` text
impression
  ->
opened
  ->
saved
  ->
selected
  ->
acted
  ->
visited/ordered
  ->
would_get_again
  ->
returns for another CRAVE decision
```

The strongest optimization targets should be downstream.

### Candidate north-star metric

**Successful Decision Rate**

Percentage of CRAVE-assisted food decisions that lead to a positive
outcome.

Supporting metrics:

-   time to useful recommendation
-   decision completion rate
-   recommendation acceptance
-   post-meal positive outcome
-   repeat decision rate
-   correction/refinement rate
-   abandonment after recommendation
-   Safe/Best/Wildcard acceptance
-   successful discovery rate
-   recommendation regret rate where measurable

------------------------------------------------------------------------

## 19. Position Bias and Feedback Loops

CRAVE must log presentation position.

If Safe Bet always appears first and gets selected most, that does not
prove users inherently prefer Safe Bet.

Required fields include:

-   score rank
-   visual position
-   recommendation role
-   selection
-   outcome

The system must avoid training blindly on behavior created by its own
ranking decisions.

------------------------------------------------------------------------

## 20. Data Freshness and Confidence

Restaurant intelligence decays.

Track freshness independently for:

-   hours
-   menu
-   menu price
-   dish existence
-   restaurant status
-   images
-   availability
-   provider data
-   quality evidence

A candidate can have high taste relevance but insufficient factual
confidence.

Decision mode should be stricter than passive discovery because the cost
of bad information is higher.

------------------------------------------------------------------------

## 21. Momentum

Momentum should not mean "TikTok is talking about it."

If introduced, it should be resistant to manipulation and supported by
independent signals such as:

-   verified outcome velocity
-   save velocity
-   repeat-visit velocity
-   recent quality evidence
-   independent source velocity
-   dish-interest velocity

Momentum should never overwhelm durable quality or user fit.

------------------------------------------------------------------------

## 22. Cold Start

CRAVE must never pretend to know a new user.

Initial ranking should lean more heavily on:

-   explicit current intent
-   local quality
-   open status
-   price
-   distance
-   menu evidence
-   general contextual priors

As evidence accumulates, personalization earns more weight.

Anonymous sessions may collect eligible temporary evidence before
signup.

After value is demonstrated:

> Save your taste?

If the user creates an account, eligible anonymous evidence can be
attached to the new identity through a controlled migration process.

------------------------------------------------------------------------

## 23. User Control and Taste Correction

Users need direct control over corrupted inference.

Possible controls:

-   More of this
-   Less of this
-   Not tonight
-   This wasn't for me
-   Don't learn from this
-   Remove preference
-   Reset inferred preference
-   Exclude this activity from taste

Explicit correction should override weak inference.

Retrieval/history surfaces may still show factual history even when an
interaction is excluded from recommendation influence. Recommendation
memory and factual history are not necessarily the same view.

------------------------------------------------------------------------

## 24. Privacy and Deletion

All personalization records must have a clear ownership and deletion
path.

Requirements:

-   user-linked evidence is traceable to the owning user
-   account deletion can delete or appropriately anonymize associated
    personalization data
-   derived profiles can be rebuilt
-   sensitive hard constraints receive appropriate access controls
-   unnecessary raw prompt/history retention is avoided
-   model inputs use only the minimum relevant context

Do not scatter user preference data through unowned logs that cannot be
deleted.

------------------------------------------------------------------------

## 25. Experimentation Architecture

Personalization and evaluation are separate responsibilities.

Every decision system release must have:

-   algorithm version
-   experiment assignment where applicable
-   predeclared primary metric
-   guardrail metrics
-   short-term evaluation
-   longer-term retention/outcome evaluation

Do not ship a ranker because it "feels smarter."

Do not celebrate CTR improvements without measuring meal outcomes and
repeat use.

A short-term engagement increase may hide long-term repetition fatigue
or reduced satisfaction.

------------------------------------------------------------------------

## 26. Algorithm Evolution Plan

### V1 - Deterministic Evidence System

Build first:

-   raw taste/recommendation events
-   explicit preferences
-   derived affinity tables
-   current session context
-   dish intelligence
-   candidate generation
-   hard filtering
-   transparent weighted ranking
-   freshness confidence
-   risk adjustment
-   repetition suppression
-   semantic diversity
-   Safe/Best/Wildcard
-   grounded reason codes
-   outcome capture
-   algorithm versioning

### V2 - Contextual Personalized Ranker

Add after meaningful outcome data exists:

-   stronger context interactions
-   calibrated confidence
-   improved taste decay
-   learned travel/price behavior
-   taste modes
-   smarter constraint relaxation
-   group compatibility optimization

### V3 - Collaborative and Embedding Retrieval

Add only after sufficient user/item interaction density:

-   user-user taste similarity
-   dish embeddings
-   place embeddings
-   collaborative candidate retrieval
-   similarity-based discovery
-   cold-start content embeddings

### V4 - Sequence Intelligence

Add after event sequences are sufficiently rich:

-   recent-action sequence modeling
-   transient craving detection
-   evolving journey detection
-   session-aware retrieval/ranking
-   stronger separation of deep taste vs immediate intent

### V5 - Learned Multi-Objective Ranking

Add only when CRAVE has the scale and evaluation maturity:

-   learned ranking
-   long-term outcome optimization
-   calibrated exploration
-   multi-objective optimization
-   sophisticated bias correction
-   contextual bandits where justified
-   potentially catalog-grounded generative ranking if it demonstrably
    beats simpler systems

Complexity must be earned by evidence.

------------------------------------------------------------------------

## 27. Banned Architecture List

CRAVE must not:

1.  Use one giant master score for everything.
2.  Treat catalog completeness as restaurant quality.
3.  Treat city percentile as absolute excellence.
4.  Turn Feed ranking into personalized Decision ranking.
5.  Use permanent pseudo-random exploration as the long-term exploration
    strategy.
6.  Treat pairwise restaurant ranking as the entire taste profile.
7.  Treat `Not tonight` as dislike.
8.  Treat `Too far` as negative cuisine preference.
9.  Treat every click as positive taste.
10. Train blindly on position-biased interactions.
11. Optimize recommendations primarily for CTR.
12. Let recent behavior permanently overwrite durable taste.
13. Collapse dish and restaurant preference.
14. Recommend unavailable/closed candidates and reveal the problem
    afterward.
15. Generate candidate restaurants or dishes from an unconstrained LLM.
16. Let an LLM invent recommendation explanations.
17. Feed an LLM the user's entire historical record when a compact
    structured profile is sufficient.
18. Hide hard-constraint relaxation from the user.
19. Force three recommendations when only one or two trustworthy
    candidates exist.
20. Create novelty by randomization alone.
21. Let sponsored placement contaminate organic recommendation scores.
22. Let popularity overwhelm personal fit.
23. Let personalization remove search/browse control.
24. Assume a mature user has one monolithic taste vector.
25. Build giant ML infrastructure before CRAVE has data proving it is
    needed.
26. Ship recommendation changes without algorithm versioning.
27. Store derived taste without retaining enough evidence to rebuild it.
28. Store user learning in locations with no deletion strategy.
29. Conflate factual history with recommendation influence.
30. Call an interaction successful merely because the user clicked.

------------------------------------------------------------------------

## 28. Required Core Data Contracts

At minimum, the future system needs durable contracts for:

### RecommendationSession

Represents one decision attempt.

Key concepts:

-   user/session identity
-   context snapshot
-   algorithm version
-   profile version
-   experiment assignment
-   timestamps
-   completion/abandonment

### RecommendationCandidate

Represents each considered/shown candidate.

Key concepts:

-   dish/place identity
-   raw component scores
-   final relevance
-   confidence
-   risk
-   role
-   visual position
-   reason codes
-   tradeoff codes

### RecommendationOutcome

Represents what happened afterward.

Key concepts:

-   selected/not selected
-   action type
-   confirmed meal where available
-   post-meal feedback
-   would-get-again
-   correction reason
-   downstream repeat behavior

### TasteEvent

Canonical behavioral evidence.

### UserTasteProfile

Materialized, fast-to-read derived intelligence.

### UserContextProfile

Practical/contextual patterns such as price and travel tolerance.

### CurrentDecisionContext

Ephemeral intent and constraints.

### DishIntelligence

Dish-level evidence independent of user preference.

### PlaceIntelligence

Place-level evidence independent of user preference.

------------------------------------------------------------------------

## 29. Build Order

Do not jump directly to ML.

### Gate 1 - Observability foundation

1.  Recommendation event taxonomy
2.  RecommendationSession
3.  RecommendationCandidate
4.  RecommendationOutcome
5.  Algorithm versioning
6.  Position/provenance logging

### Gate 2 - User memory

7.  Explicit preference model
8.  TasteEvent storage
9.  Derived taste profile
10. Recent behavior representation
11. Current decision context
12. Correction/exclusion semantics

### Gate 3 - Catalog intelligence

13. Reframe global rank as Place Prior
14. Separate data confidence
15. Dish intelligence
16. Freshness confidence
17. Availability confidence

### Gate 4 - Decision engine

18. Candidate generation
19. Hard filters
20. Transparent relevance scoring
21. Risk engine
22. Repetition suppression
23. Semantic diversification
24. Safe/Best/Wildcard assignment
25. Constraint relaxation
26. Grounded reasons/tradeoffs

### Gate 5 - Learning loop

27. Post-meal feedback
28. Outcome scoring
29. Profile updater
30. Recommendation success analytics
31. Cohort retention analytics
32. Experiment framework

### Gate 6 - Advanced intelligence

33. Collaborative retrieval
34. Embeddings
35. Taste modes/journeys
36. Sequence modeling
37. Learned ranking
38. Contextual exploration/bandits if justified
39. Multi-objective optimization
40. Catalog-grounded generative ranking only if empirically superior

Every gate must be tested before the next one becomes architectural
dependency.

------------------------------------------------------------------------

## 30. Production Invariants

The following must always remain true:

-   Every shown recommendation can be traced to real catalog entities.
-   Every recommendation has an algorithm version.
-   Every explanation maps to structured evidence.
-   Every hard user constraint is enforced before presentation.
-   Temporary intent cannot silently become permanent taste.
-   User corrections can reduce/remove learned influence.
-   Dish preference and restaurant preference remain independently
    representable.
-   Feed/editorial ranking remains separate from personal decision
    ranking.
-   Recommendation outcomes are stored separately from recommendation
    impressions.
-   The derived taste profile can be rebuilt from authoritative
    evidence.
-   A user can search/browse outside the recommendation system.
-   The system can return fewer results rather than fabricate
    confidence.
-   High-risk recommendations require stronger confidence.
-   Personalization never depends on an LLM remembering the user.
-   ML complexity is introduced only when simpler systems demonstrably
    fail.

------------------------------------------------------------------------

## 31. Research-Backed Design Notes

This architecture deliberately adopts lessons from mature
personalization systems without copying their infrastructure scale.

**Spotify:** behavioral activity can contaminate taste. Spotify built
explicit controls to reduce the recommendation influence of functional
or out-of-context listening, and later expanded taste controls. CRAVE
therefore needs correction/exclusion semantics and must distinguish
factual history from recommendation influence.

**Uber Eats:** recent actions matter enough that Uber moved from
batch-lagged features toward near-real-time event-sourced user context
and sequence-aware restaurant recommendation. CRAVE therefore preserves
events, separates recent behavior from long-term taste, and plans for
online/offline feature parity if learned models arrive.

**Pinterest:** recommendation quality depends on evolving user sequences
and multiple interests, not only a static profile. CRAVE therefore plans
for taste modes/journeys rather than permanently collapsing every
behavior into one vector.

**Netflix:** modern generative ranking research still grounds
recommendation models in the actual catalog, member history/context,
ranking-specific training, and long-term satisfaction objectives. CRAVE
therefore does not use a generic LLM as an unconstrained restaurant
generator.

**Core transfer rule:** copy the conceptual lessons, not the hyperscale
infrastructure.

------------------------------------------------------------------------

## 32. Final System Definition

CRAVE intelligence is not:

> "AI that recommends restaurants."

It is:

> A persistent evidence and decision system that understands what food
> and places exist, what deserves consideration, how a specific user
> tends to eat, what they want in the current moment, what constraints
> are real, how risky a recommendation is, how to present a small
> diverse set of trustworthy choices, and whether those choices actually
> produced good meals.

The flywheel is:

``` text
EVIDENCE
  ->
UNDERSTANDING
  ->
DECISION
  ->
OUTCOME
  ->
LEARNING
  ->
BETTER NEXT DECISION
```

That loop - not the LLM, feed, map, or global rank score - is the core
CRAVE intelligence product.

------------------------------------------------------------------------

## 33. Locked North Star

> CRAVE should get increasingly good at helping each user eat things
> they are glad they chose.

Every algorithm, screen, event, model, and experiment must ultimately
justify itself against that standard.
