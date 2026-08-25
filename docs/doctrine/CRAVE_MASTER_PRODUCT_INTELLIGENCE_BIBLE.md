# CRAVE MASTER PRODUCT + INTELLIGENCE BIBLE

## Product, UX, Personalization, Ranking, Retention, Screens, Algorithms, Anti-Slop Rules, and Audit Rubric

**Status:** Master working doctrine\
**Purpose:** Define what CRAVE is, how every major screen and
intelligence system should work, how decisions are made, and what is
banned.

------------------------------------------------------------------------

# 1. NORTH STAR

CRAVE exists to turn:

> "I don't know what to eat."

into:

> "That's exactly what I want."

The core product question is:

> **Given everything CRAVE legitimately knows about my taste, history,
> saves, friends, location, constraints, and what I want right now ---
> what should I eat?**

CRAVE is not primarily a restaurant directory, review database, generic
map, social feed, or AI chatbot.

Its job is **food decision intelligence**.

### Core loop

**Discover → Decide → Eat → Remember → Learn → Better next decision**

The system should optimize successful food decisions rather than
maximizing scrolling, session duration, or content consumption.

------------------------------------------------------------------------

# 2. PRODUCT POSITION

CRAVE should occupy the space between several established behaviors:

-   Maps products answer **what exists and where**.
-   Review products answer **what the crowd thinks**.
-   Restaurant-ranking/social products answer **what I and my friends
    liked**.
-   Social media answers **what looks exciting right now**.
-   CRAVE should answer **what is right for me, in this context, right
    now**.

CRAVE must not become "Yelp + TikTok + Beli + Maps + AI." Every feature
must strengthen Discover, Decide, Eat, Remember, or Learn.

------------------------------------------------------------------------

# 3. LOCKED PRODUCT PRINCIPLES

1.  Successful decisions beat engagement theater.
2.  Long-term taste, recent behavior, current intent, and hard
    constraints are separate concepts.
3.  Hard constraints are applied before ranking.
4.  Dish affinity and restaurant affinity remain separate.
5.  Never create one opaque universal "master CRAVE score."
6.  Recommendations must be auditable.
7.  Explanations must come from real ranking evidence, not generated
    post-hoc fiction.
8.  Users must be able to correct or delete learned preferences.
9.  LLMs may interpret language and enrich data; they do not own catalog
    truth, user memory, or risky final ranking decisions.
10. Feed, Map, Search, Craves, and You are different projections of the
    same food intelligence system.
11. The system earns complexity. Do not ship controls merely because
    competitors have them.
12. Originality comes from interaction logic, information hierarchy,
    memory, and product behavior---not decorative novelty.

------------------------------------------------------------------------

# 4. THE SMALLEST RETENTION INTERACTION

The key retention question is:

> **What is the smallest interaction that makes someone want to use
> CRAVE again the next time they do not know what to eat?**

The answer is not "scroll a beautiful feed."

It is:

> **CRAVE gives a small set of genuinely useful options, the user
> chooses one with confidence, and CRAVE remembers enough that the next
> decision is better.**

A 90-second successful session may be better than 14 minutes of
browsing.

------------------------------------------------------------------------

# 5. INTELLIGENCE ARCHITECTURE

CRAVE should use this pipeline:

**Observe → Understand → Retrieve → Hard-filter → Score → Re-rank →
Diversify → Explain → Present → Observe outcome → Learn**

## 5.1 Event / Behavior Engine

Record behavior as events rather than immediately converting taps into
permanent beliefs.

Examples:

-   `place_impression`
-   `place_opened`
-   `dish_opened`
-   `search_performed`
-   `filter_selected`
-   `place_saved`
-   `place_unsaved`
-   `social_link_imported`
-   `directions_started`
-   `selected`
-   `visited`
-   `ordered`
-   `ranked`
-   `liked`
-   `disliked`
-   `would_get_again`
-   `repeat_visit`
-   `shared`
-   `recommendation_skipped`

Useful context:

-   user
-   place
-   dish
-   timestamp
-   session
-   query
-   active filters
-   recommendation ID
-   position
-   source
-   dwell time
-   location context
-   outcome

A click is evidence, not a conclusion.

## 5.2 Signal hierarchy

Approximate behavioral strength:

**Impression → Click → Long detail view → Repeated search → Save →
Directions/selection → Confirmed visit/order → Post-visit ranking →
Would-get-again → Repeat visit**

Negative evidence also matters:

-   repeated exposure without engagement
-   unsave
-   explicit dislike
-   poor post-visit ranking
-   repeated rejection of a supposedly strong recommendation

## 5.3 User Taste Graph

Maintain structured affinities with strength, confidence, recency, and
context.

Possible dimensions:

-   cuisine
-   dish
-   ingredients
-   flavor
-   texture
-   spice
-   price tolerance
-   restaurant format
-   atmosphere
-   occasion
-   meal period
-   neighborhood
-   novelty preference
-   travel willingness
-   dietary constraints
-   social influence

Example conceptual state:

-   Japanese: strong / high confidence
-   spicy: strong / high confidence
-   fine dining: moderate / medium confidence
-   coffee travel tolerance: low
-   dinner travel tolerance: higher

Do not collapse these into a text profile.

## 5.4 Time horizons

Maintain separate models:

### Long-term taste

What the person generally likes.

### Recent interest

What has been rising or falling recently.

### Session intent

What they want right now.

### Hard constraints

Rules that cannot be violated for the current decision.

Current intent must be allowed to override historical taste.

------------------------------------------------------------------------

# 6. CONTEXT ENGINE

Every decision request should construct a compact context.

### WHO

Taste profile, history, rankings, saves, recent behavior.

### WHAT

Query, dish, cuisine, mood, occasion.

### WHEN

Time, day, meal period, planned time, open state.

### WHERE

Current location, selected city, travel tolerance.

### WITH WHOM

Solo, partner, friends, family/group when known.

### CONSTRAINTS

Budget, dietary needs, travel, availability, explicit filters.

### MEMORY

Visited, saved, rejected, recently shown, repeat favorites.

### SOCIAL

Friend rankings, similarity, trusted signals.

------------------------------------------------------------------------

# 7. CANDIDATE RETRIEVAL

Do not ask an LLM to inspect the entire catalog and "pick the best
restaurant."

Use deterministic retrieval first.

Example:

32,788 total places\
→ geographic eligibility\
→ open/time eligibility\
→ dietary/hard constraints\
→ travel tolerance\
→ query/dish/cuisine compatibility\
→ manageable candidate set\
→ personalized ranking

This improves latency, cost, debuggability, and correctness.

------------------------------------------------------------------------

# 8. HARD CONSTRAINT ENGINE

Hard constraints must be enforced before ranking.

Examples:

-   closed at requested time
-   outside explicit maximum travel
-   explicit dietary exclusion
-   unavailable required service
-   excluded place/history state
-   invalid or insufficient place data when required

A closed 99% taste match is not a good recommendation for "right now."

------------------------------------------------------------------------

# 9. RANKING SYSTEM

## 9.1 Existing baseline logic

Current algorithm references include:

-   global `rank_score`
-   city percentile tiers:
    -   **CRAVE Pick:** ≥95th percentile
    -   **Hidden Gem:** ≥80th percentile
    -   **Worth Knowing:** ≥40th percentile
-   baseline Feed blend:
    -   `0.65 * rank_score`
    -   `0.20 * proximity`
    -   `0.10 * quality`
    -   `0.05 * explore`
    -   plus saturation/chain penalties
-   Search can use distance-first ordering.
-   Personal ranking can be cuisine-scoped and comparison-driven.

These are useful baseline systems, not the final personalized decision
engine.

## 9.2 No single master score

The personalized ranker should retain independently inspectable
dimensions.

Conceptually:

`utility(place, user, context) =` - taste compatibility - current-intent
compatibility - quality confidence - travel utility - value
compatibility - social relevance - novelty - contextual relevance -
minus penalties

Weights change by context and user behavior.

Do not expose a fake precision percentage unless calibrated and
defensible.

## 9.3 Predict choice utility

The deeper target is closer to:

> **P(user chooses and is satisfied with place \| user, place,
> context)**

rather than:

> P(user likes this cuisine)

Two users can share cuisine taste but have radically different
price/travel/novelty utility.

------------------------------------------------------------------------

# 10. DISH + MENU INTELLIGENCE

Restaurant categories are insufficient.

CRAVE needs relationships such as:

**Restaurant → Menu → Dish → Ingredients → Attributes → Cuisine**

Dish attributes may include:

-   spicy
-   savory
-   sweet
-   rich
-   light
-   crispy
-   noodles
-   soup
-   grilled
-   protein
-   dietary compatibility
-   meal type

This allows intent such as "something spicy and warm" to retrieve
relevant dishes without requiring the user to know the restaurant
category.

Dish affinity must remain distinct from restaurant affinity.

------------------------------------------------------------------------

# 11. SOCIAL INTELLIGENCE

Do not reduce social relevance to raw friend counts.

Build similarity/trust signals from legitimate overlapping evidence:

-   common ranked places
-   similar rankings
-   dish overlap
-   cuisine overlap
-   contextual preferences

A highly similar friend's strong recommendation can matter more than
many weak social saves.

Avoid turning CRAVE into a popularity contest.

------------------------------------------------------------------------

# 12. EXPLORATION VS. EXPLOITATION

A recommender that only repeats known favorites becomes boring.

Most recommendations should exploit known preferences while a controlled
share explores adjacent possibilities.

Exploration should respect learned novelty tolerance.

Adjacent exploration is preferable to random novelty.

Potential later technique: contextual-bandit-style experimentation after
sufficient data quality and instrumentation exist.

------------------------------------------------------------------------

# 13. DIVERSITY / RE-RANKING

A mathematically strong top five can still be a terrible user experience
if every result is nearly identical.

Re-rank for useful diversity across:

-   cuisine
-   dish
-   neighborhood
-   price
-   restaurant format
-   novelty
-   previously shown items

Use repetition suppression and semantic diversity.

Useful candidate roles:

-   **Best Tonight**
-   **Safe Bet**
-   **Wildcard**

These roles are more decision-friendly than a homogeneous list.

------------------------------------------------------------------------

# 14. RISK + CONFIDENCE

Use risk-adjusted confidence.

Distinguish:

-   strong recommendation with high evidence
-   promising recommendation with sparse evidence
-   exploratory recommendation
-   weak-data fallback

Cold-start priors should be explicit and should decay as personalized
evidence accumulates.

------------------------------------------------------------------------

# 15. RECOMMENDATION EXPLANATIONS

Explanations must be generated from stored reason codes / scoring
provenance.

Examples:

-   `SAVED_BEFORE`
-   `HIGH_TASTE_MATCH`
-   `FRIEND_MATCH`
-   `DISH_MATCH`
-   `OPEN_NOW`
-   `GOOD_DISTANCE`
-   `NOVELTY_PICK`
-   `REPEAT_FAVORITE`
-   `RECENT_INTEREST`

UI can render:

-   "Because you saved it"
-   "Similar to places you rank highly"
-   "A strong match for what you want tonight"
-   "8 min away · open now"
-   "Something different that still fits your taste"

Never invent explanations after ranking.

------------------------------------------------------------------------

# 16. RECOMMENDATION LEDGER

Every recommendation should be reconstructable.

Store:

-   recommendation ID
-   algorithm/model version
-   candidate set
-   filters
-   context
-   feature values
-   component scores
-   penalties
-   reason codes
-   positions shown
-   final selections
-   later outcomes

This is essential for debugging, experimentation, trust, and future
model evaluation.

------------------------------------------------------------------------

# 17. OUTCOME + LEARNING ENGINE

Track the full funnel:

**impression → opened → saved → selected → acted → visited/ordered →
would_get_again → returns**

Learning should reward successful outcomes more strongly than
superficial engagement.

Important metrics:

-   successful decision rate
-   repeat decision rate
-   time to decision
-   recommendation-to-detail rate
-   recommendation-to-save
-   recommendation-to-directions/action
-   recommendation-to-visit
-   post-visit positive ranking
-   would-get-again
-   repeat visit
-   recommendation acceptance
-   regret/correction rate
-   search reformulation
-   abandonment

Do not make session duration the north star.

------------------------------------------------------------------------

# 18. COLD START

New users cannot wait weeks for personalization.

Use lightweight calibration:

-   food comparisons
-   cuisine/dish winners
-   price preference
-   adventurous vs familiar
-   travel willingness
-   prior restaurant rankings

Ranking known restaurants is especially useful because it creates dense
preference evidence.

Do not make calibration feel like paperwork.

------------------------------------------------------------------------

# 19. CRAVES = PERSONAL FOOD MEMORY

Craves should evolve beyond bookmarks.

A saved/imported item can preserve structured information:

-   original source
-   original URL
-   matched restaurant
-   matched dish
-   creator/source identity where appropriate
-   date saved
-   media reference
-   extracted context
-   match confidence
-   user notes/tags
-   visit state

This enables future queries such as:

-   saved places near me
-   saved places open tonight
-   saved places under my budget
-   that pasta place I saved months ago
-   untried Craves
-   Craves a friend also liked

The original source must remain traceable.

------------------------------------------------------------------------

# 20. SOCIAL LINK IMPORT

The "Share a link" interaction should support legitimate links from
sources such as social/video/article content and convert inspiration
into structured food memory.

Required product behaviors:

1.  preserve original URL
2.  resolve place with confidence
3.  never silently attach the wrong restaurant
4.  surface ambiguity when confidence is insufficient
5.  extract dish/context only when supported
6.  allow manual correction
7.  store provenance

The value is not importing a link. The value is making that link
retrievable and actionable later.

------------------------------------------------------------------------

# 21. UNIFIED DISCOVERY QUERY

Feed, Map, and Search should share a common query/state contract rather
than maintaining incompatible filtering systems.

Conceptual dimensions:

### WHERE

Location, city, radius/travel time.

### WHEN

Now, later, meal period.

### WHAT

Dish, cuisine, query, mood, occasion.

### COST

Budget.

### CONSTRAINTS

Dietary/accessibility/service requirements.

### HISTORY

Saved, visited, unvisited, rejected.

### SOCIAL

Trusted/friend signals.

### INTENT

Quick, date, comfort, adventurous, etc.

Changing a relevant discovery constraint should propagate coherently
between Feed and Map, and Search should understand the same semantics
where appropriate.

------------------------------------------------------------------------

# 22. SCREEN SYSTEM

## 22.1 Feed --- "What should I eat?"

Purpose: personalized decision surface.

Feed should not be a generic endless card stream.

It should prioritize:

-   small, high-confidence candidate sets
-   strong food/place imagery
-   reason-to-care
-   context
-   distance/travel
-   open status where relevant
-   useful price/value information
-   save state
-   fast action
-   recommendation provenance

Potential sections should be dynamic, not permanent template furniture.

Examples:

-   Best for tonight
-   From your Craves
-   Worth the drive
-   Something different
-   Friends with similar taste loved
-   Quick nearby picks

Avoid cluttering the top with weak recommendation chips that are merely
restaurant names.

### Feed current problems observed

-   visual hierarchy is underdeveloped
-   placeholder/empty image regions damage trust
-   cards do not yet communicate why each place matters
-   recommendation chips are weak as a primary personalization device
-   current pagination/log behavior suggests sparse pages and repeated
    loading states should be audited
-   Feed should not repeatedly fetch empty pages while presenting a tiny
    accumulated result set

------------------------------------------------------------------------

# 23. MAP --- "Where are my best options?"

Purpose: spatial projection of the same candidate universe.

Current map issue: hundreds of markers create visual noise and destroy
decision usefulness.

Rules:

-   cluster aggressively
-   prioritize high-value personalized candidates
-   suppress low-value marker noise
-   selected place gets strong focus
-   show contextual tray/card on selection
-   preserve active filters
-   maintain consistent meaning for marker tiers
-   avoid presenting the entire database as equally important

The map is not a database visualization. It is a decision map.

------------------------------------------------------------------------

# 24. SEARCH --- "I know approximately what I want."

Purpose: direct intent.

Search should support:

-   place
-   cuisine
-   dish
-   natural food intent
-   location
-   contextual modifiers

Examples:

-   ramen
-   spicy noodles
-   cheap lunch
-   date night
-   saved Mexican near me
-   something warm open late

Search should have meaningful zero-state content rather than a mostly
empty black screen.

Potential zero-state modules:

-   recent searches
-   recent Craves
-   useful current intents
-   trending only when genuinely relevant
-   city/location shortcuts

Do not fill zero state with generic decorative recommendations.

------------------------------------------------------------------------

# 25. CRAVES --- "What did I want to remember?"

Purpose: personal food memory.

Current empty state has a strong conceptual seed but should evolve into
a true memory system.

Core states:

-   empty
-   saved places
-   imported links pending match
-   matched social saves
-   visited vs unvisited
-   lists/tags later
-   error/offline/loading

Primary actions:

-   share/paste a link
-   add by name
-   browse/save from CRAVE

Avoid making the screen a plain bookmark list.

------------------------------------------------------------------------

# 26. YOU --- "What has CRAVE learned about me?"

Purpose: transparent taste identity + ranking history + social layer +
control.

Should eventually show:

-   rankings
-   taste dimensions
-   preference confidence where useful
-   visited places
-   streak only if behaviorally meaningful
-   friends
-   similarity
-   profile controls
-   corrections
-   privacy/memory controls

Do not turn the page into a dashboard of vanity counters.

"0 followers / 0 following / 0 ranked" is not valuable enough to
dominate early onboarding.

The screen should teach users why ranking improves recommendations
without sounding like homework.

------------------------------------------------------------------------

# 27. FILTER SYSTEM

Current filter concept is too primitive if limited to price + cuisine.

Retain the bottom-sheet pattern but redesign the information
architecture.

## 27.1 Quick filters

High-frequency controls may appear above results:

-   Open now
-   budget
-   travel time
-   cuisine
-   More

Context can change which quick filters are most useful.

## 27.2 Full filter sheet

Recommended V1 hierarchy:

### Time / availability

-   Open now
-   Open late
-   planned time when supported

### Budget

Prefer meaningful spend ranges where reliable, while retaining
price-tier compatibility where necessary.

### Distance / travel

-   walkable
-   short trip
-   moderate trip
-   worth the drive
-   configurable distance/time

### Cuisine

Actual cuisines.

### Dietary needs

Only claims supported by trustworthy data.

### CRAVE memory

-   From my Craves
-   Haven't tried
-   Been before
-   Something new

### Later contextual dimensions

-   occasion
-   service type
-   dish attributes
-   group compatibility
-   reservations
-   social signals

## 27.3 Taxonomy correction

Do not place semantically different dimensions under "Cuisine."

Examples that need separate treatment:

-   Fine Dining → experience/format
-   Breakfast → meal type
-   Vegan → dietary
-   Coffee → food/drink category
-   Pizza/BBQ/Seafood may be user-facing food categories even when
    taxonomy overlaps

The UI taxonomy should serve user decisions rather than mirror a flawed
database taxonomy.

## 27.4 Filter interaction rules

-   progressive disclosure
-   selected filter count
-   persistent applied chips outside sheet
-   explicit Reset
-   explicit Apply / "Show N places"
-   live result count
-   zero-result recovery
-   suggest which constraint can be relaxed
-   preserve state across Feed/Map
-   do not lose edits on accidental dismissal

------------------------------------------------------------------------

# 28. FILTERS ARE ALSO EVIDENCE

A filter selection can contribute weak behavioral evidence but must not
immediately become a permanent preference.

Repeated patterns can gradually strengthen learned signals.

Example:

one Mexican filter selection = tiny evidence\
repeated Mexican search/filter behavior = moderate\
save = stronger\
visit = stronger\
high ranking = very strong\
repeat visit = strongest

------------------------------------------------------------------------

# 29. PERSISTENT PREFERENCES VS. SESSION FILTERS

Never mix these concepts.

### Persistent taste

Usually likes spicy food.

### Persistent constraint

Dietary requirement, if explicitly saved by user.

### Current intent

Wants spicy tonight.

### Query filter

Only show open places within 15 minutes.

These require different storage, expiration, and ranking behavior.

------------------------------------------------------------------------

# 30. SCREEN VISUAL DOCTRINE

CRAVE should feel authored, not generated.

Desired traits:

-   strong information hierarchy
-   purposeful asymmetry when useful
-   content-first imagery
-   restrained CRAVE blue
-   dark mode with deliberate contrast
-   large touch targets
-   clear selected states
-   stable layout
-   typography with hierarchy rather than endless same-weight labels
-   fewer but more meaningful controls
-   progressive disclosure
-   high-confidence whitespace
-   interaction-specific motion rather than decorative motion

------------------------------------------------------------------------

# 31. BANNED / ANTI-AI-SLOP LIST

Avoid these unless a specific product need justifies them:

1.  giant generic gradient hero areas
2.  excessive glassmorphism
3.  random glowing blobs
4.  identical rounded cards for every concept
5.  pill overload
6.  fake "AI" sparkle icons everywhere
7.  "For You" sections with no explainable personalization
8.  generic inspirational empty states
9.  meaningless dashboard statistics
10. arbitrary percentages presented as intelligence
11. huge whitespace with no decision value
12. excessive centered text
13. card-inside-card-inside-card layouts
14. generic stock illustrations
15. decorative charts without user decisions attached
16. cloned template navigation
17. overuse of blue simply because it is the brand color
18. every screen having identical visual rhythm
19. generic AI-generated copy such as "Discover your perfect..."
20. unexplained recommendation badges
21. ungrounded "trending"
22. endless carousels
23. hiding basic utility behind clever gestures
24. premature social proof
25. ratings copied from directory products without strategic purpose
26. giant filter walls
27. fake personalization based on one click
28. chatbots used where direct controls are faster
29. animations that delay decisions
30. skeletons that persist because the data architecture is slow
31. duplicate controls across tabs with different semantics
32. dark-on-dark low-contrast typography
33. empty pages that look unfinished
34. massive marker clouds
35. excessive gamification
36. forcing onboarding questions CRAVE can learn naturally
37. using LLM prose as a substitute for structured product logic

------------------------------------------------------------------------

# 32. ORIGINALITY TEST

For every screen ask:

1.  Could this screenshot belong to 50 other AI-generated apps?
2.  Does the hierarchy reveal CRAVE's actual product thesis?
3.  Is the most important action obvious without explanation?
4.  Is personalization visible through useful behavior rather than
    decorative labels?
5.  Does the screen become more valuable after months of use?
6.  Is any element present merely because a template had it?
7.  Could removing an element improve decision speed?
8.  Does the interface reflect food memory, decision intelligence, or
    taste learning?

If the screen could be reskinned and become a music, travel, finance, or
fitness app with minimal structural changes, it is not CRAVE-specific
enough.

------------------------------------------------------------------------

# 33. MASTER BRUTAL SCREEN RUBRIC --- 100 POINTS

Use this for every CRAVE screen.

## A. Product purpose --- 10

-   clear job
-   obvious primary action
-   directly strengthens CRAVE loop

## B. Information hierarchy --- 10

-   first glance is correct
-   important content dominates
-   secondary controls stay secondary

## C. Decision usefulness --- 15

-   reduces uncertainty
-   provides actionable context
-   avoids unnecessary browsing

## D. Originality / CRAVE identity --- 10

-   unmistakably CRAVE
-   not template-derived
-   product logic is visible

## E. Personalization / memory --- 10

-   uses relevant learned state
-   improves with history
-   avoids fake personalization

## F. Interaction design --- 10

-   touch targets
-   feedback
-   state clarity
-   undo/recovery
-   progressive disclosure

## G. Performance / rendering --- 10

-   stable layout
-   efficient lists/maps
-   virtualization where needed
-   no unnecessary re-render/fetch loops
-   image loading strategy
-   responsive interactions

## H. Error / edge states --- 10

-   loading
-   empty
-   offline
-   network error
-   permission denial
-   partial data
-   zero results
-   retry/recovery

## I. Accessibility --- 5

-   contrast
-   scalable text
-   semantic labels
-   target size
-   screen-reader behavior

## J. Trust / explainability --- 5

-   reason for recommendation
-   data provenance when relevant
-   no misleading precision
-   user correction

## K. Retention contribution --- 5

-   creates memory
-   creates useful signal
-   gives a reason to return

### Grade bands

-   **95--100:** exceptional / ship-level target
-   **90--94:** excellent, minor refinement
-   **80--89:** competitive but not finished
-   **70--79:** credible MVP
-   **60--69:** functional but weak
-   **\<60:** rework/nuke

A visually beautiful screen can still fail if decision usefulness or
product purpose is weak.

------------------------------------------------------------------------

# 34. FORENSIC ENGINEERING AUDIT PROTOCOL

Every code-level screen audit should use four stages.

## 1. Forensic Failure Analysis

Categorize exact failures under:

### State & Data Flow

Race conditions, stale closures, duplicate state, bad lifecycle
triggers, prop drilling, incorrect dependencies.

### Performance & Rendering

Re-render storms, list problems, layout instability, image churn, map
overload, bundle/dependency issues.

### Error Handling & Edge Cases

Network failure, partial payloads, null states, permission denial,
unhandled promise rejection, stale data.

## 2. Root Cause Verification

Explain the framework/runtime mechanics causing each observed failure.

## 3. Complete Refactor Blueprint

When code is requested:

-   complete replacement
-   strict zero-any TypeScript
-   isolated state
-   full lifecycle handling
-   explicit loading/error/empty states
-   appropriate error-boundary strategy
-   existing stack respected
-   no invented libraries
-   no placeholder code

## 4. Verification

Provide a concise regression test/assertion with standard project
tooling.

------------------------------------------------------------------------

# 35. PRODUCT + USER-RESEARCH TRIANGULATION

When external evidence exists, use:

## Technical evidence

GitHub issues, code, crash logs, dependencies.

## User evidence

App Store/Play reviews, complaints, support patterns.

## Behavioral evidence

Drop-off, search reformulation, repeated taps, abandonment, session
outcomes.

Then identify the exact disconnect between implementation and complaint.

Do not use competitor research as aesthetic copying. Extract principles,
failure patterns, and interaction lessons.

------------------------------------------------------------------------

# 36. COMPETITIVE LESSONS

## Restaurant ranking/social products

Learn from:

-   explicit ranking creates dense taste signal
-   friend taste alignment is stronger than anonymous popularity
-   personal maps and want-to-try lists create memory
-   ranking can itself become retention

Do not simply clone their screen structures.

## Maps products

Learn from:

-   geographic completeness
-   hours/location utility
-   navigation
-   strong POI data

CRAVE should not attempt to win by displaying more pins.

## Review/directory products

Learn from:

-   robust explicit filters
-   taxonomy breadth
-   utility data
-   search reliability

Do not inherit directory overload or generic crowd-rating dependence.

## Social/video discovery

Learn from:

-   visual appetite
-   cultural discovery
-   creator-driven inspiration
-   rapid novelty

CRAVE's opportunity is converting ephemeral inspiration into structured,
retrievable food memory.

------------------------------------------------------------------------

# 37. FEED/MAP/SEARCH/CRAVES/YOU RELATIONSHIP

These are not five disconnected products.

### Feed

"What should I eat?"

### Map

"Where are the best relevant options?"

### Search

"I know approximately what I want."

### Craves

"What did I want to remember?"

### You

"What has CRAVE learned about me?"

All should use shared place identity, shared memory, shared discovery
semantics, and shared ranking provenance.

------------------------------------------------------------------------

# 38. RETENTION FLYWHEEL

Search\
→ filter behavior\
→ impressions\
→ detail opens\
→ saves\
→ imported social content\
→ directions/actions\
→ visits/orders\
→ rankings\
→ would-get-again\
→ repeat visits\
→ friend similarity\
→ better taste model\
→ better recommendations\
→ faster decisions\
→ return next time

The accumulating relationship is the moat.

------------------------------------------------------------------------

# 39. USER CONTROL + PRIVACY

CRAVE should expose meaningful control over learned state.

Users should be able to:

-   inspect major learned preferences
-   correct them
-   remove them
-   manage persistent constraints
-   remove history where supported
-   understand why a recommendation appeared

Do not create an invisible permanent behavioral profile that users
cannot correct.

------------------------------------------------------------------------

# 40. EXPERIMENTATION

Every meaningful recommendation or UX change should be measurable.

Experiments should target decision quality, not vanity engagement.

Useful comparisons:

-   three candidates vs long feed
-   reason codes vs no explanation
-   contextual quick filters vs static filters
-   Craves resurfacing vs generic recommendations
-   diversified top set vs pure score order
-   travel-time display vs miles
-   ranking calibration flows vs passive cold start

Maintain algorithm/version IDs in recommendation logs so results can be
attributed correctly.

------------------------------------------------------------------------

# 41. PERFORMANCE REQUIREMENTS

Especially important for React Native / Expo:

-   virtualize long lists
-   avoid rendering entire place catalogs
-   aggressively manage map marker count
-   memoize expensive derived representations only where profiling
    justifies it
-   prevent duplicate fetches caused by focus/effect interactions
-   cancel or ignore stale requests
-   paginate based on server truth
-   prevent empty-page request loops
-   cache normalized place entities
-   use stable IDs
-   avoid duplicate normalization work
-   use image caching/fallback strategy
-   instrument request latency and render cost

Current logs showing repeated Feed loads, repeated empty pages, repeated
Craves renders, and repeated Map loads are audit signals---not
necessarily proof of a single root cause without the source code.

------------------------------------------------------------------------

# 42. EMPTY STATES

An empty state must do one of three things:

1.  explain why the state exists
2.  provide the next useful action
3.  demonstrate future value

Prefer specific actions over motivational copy.

Examples:

### Craves

"Save your first place" / "Import a link"

### Search

Recent searches or current intent shortcuts.

### You

Rank places you already know to improve recommendations.

Never make an empty state look like an unfinished screen.

------------------------------------------------------------------------

# 43. DESIGNING FOR 100/100

A 100-level CRAVE screen requires all of the following simultaneously:

-   obvious purpose
-   fast decision support
-   strong visual hierarchy
-   original product behavior
-   meaningful personalization
-   no template residue
-   stable performance
-   complete edge states
-   accessibility
-   explainability
-   memory contribution
-   measurable outcome

Visual polish alone cannot produce 100.

------------------------------------------------------------------------

# 44. WHAT CRAVE SHOULD NOT OPTIMIZE

Do not optimize the product around:

-   maximum scrolling
-   maximum session duration
-   maximum number of cards viewed
-   notification volume
-   follower counts
-   generic trending content
-   number of filters
-   amount of AI-generated text
-   feature count

Optimize around:

> **How quickly and reliably did CRAVE help this person make a food
> decision they were happy with?**

------------------------------------------------------------------------

# 45. SYSTEM BUILD ORDER

A disciplined order:

1.  canonical place/dish/user event contracts
2.  unified DiscoveryQuery
3.  event instrumentation
4.  hard constraints
5.  deterministic candidate retrieval
6.  baseline ranker
7.  recommendation ledger
8.  Feed decision presentation
9.  Map projection
10. Search intent
11. Craves memory/import
12. You taste/ranking transparency
13. filter architecture
14. outcome capture
15. taste graph
16. recent-interest model
17. social similarity
18. dish intelligence
19. diversification
20. exploration
21. calibrated explanations
22. experimentation framework
23. continual ranking evaluation

Do not jump directly to sophisticated ML while basic event quality,
catalog truth, and outcome instrumentation are unreliable.

------------------------------------------------------------------------

# 46. SHIP GATES

A screen/system is not "done" because it renders.

Before shipping, verify:

-   product purpose
-   data contract
-   loading/error/empty states
-   offline/network degradation
-   stale request handling
-   accessibility
-   analytics
-   recommendation provenance
-   correction path
-   performance
-   regression test
-   cross-tab state consistency
-   visual originality
-   no banned slop patterns

------------------------------------------------------------------------

# 47. FINAL PRODUCT DOCTRINE

CRAVE should become a **personal food memory and decision engine**.

The strongest version of CRAVE does not overwhelm users with more
restaurants. It progressively learns enough to reduce the candidate
universe.

The ideal experience is:

> "CRAVE knows the difference between what I usually like, what I have
> been interested in lately, what I saved months ago, what my trusted
> friends love, what is actually available nearby, and what I want
> tonight. It gives me a handful of defensible options, tells me why
> they fit, remembers what happened, and gets better next time."

That is the standard against which every algorithm, screen, filter,
animation, database field, event, and feature should be judged.

------------------------------------------------------------------------

# 48. ONE-LINE TEST FOR EVERY FUTURE FEATURE

Before adding anything, ask:

> **Does this help CRAVE make a faster, more confident, more personal
> food decision now---or learn enough to make the next one better?**

If the answer is no, the feature does not automatically belong in CRAVE.
