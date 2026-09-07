# CRAVE V1 Scope

**Status:** Canonical scope artifact (2026-09-07)
**Purpose:** Make unambiguous — for humans and for Codex — what is
launch scope, what is later, what is open, what is rejected, and what
later capability still requires architecture decisions today. This
document does not redesign anything. It does not restate rationale
already settled elsewhere; it cites the governing canon and states the
consequence.

**Authority hierarchy** (highest to lowest, used to resolve any
apparent conflict): existing doctrine foundation
(`CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md`,
`CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md`,
`CRAVE_PLACE_DETAIL_SPEC.md`) → `CRAVE_CANON_RECONCILIATION_MAP.md` →
the annotated supersessions those two produced → the latest explicitly
approved product decisions (this document, and whatever supersedes a
row in it the same traceable way).

---

## 1. Status vocabulary

| Status | Meaning |
|---|---|
| **V1 REQUIRED** | Must exist, in the form described, for first public release. |
| **V1 SUPPORTING** | Not the primary job of the surface, but required alongside it for V1 to function honestly (e.g. a deep-link CTA, a fallback state). |
| **LATER — ARCHITECT NOW** | Not built in V1, but V1's data model/schema/constraint system must accommodate it so it isn't a rewrite later. |
| **LATER — DEFER** | Not built in V1, and nothing about V1 needs to anticipate it structurally. |
| **OPEN — DO NOT IMPLEMENT** | An unresolved product fork. No UI, endpoint, or schema for it may be built until a deliberate decision closes it. |
| **REJECTED / PROHIBITED** | Not a scoping question — permanently excluded from CRAVE regardless of version, business pressure, or future request. |
| **AUDIT REQUIRED** | Neither approved nor rejected; a specific verification (usually against current shipped code) must happen before a status can be assigned. |

---

## 2. The three launch-level prohibitions

These are not preferences and not scoped to V1 — they bind every future
version, every surface, and every business decision that touches
CRAVE. Every row below that enforces one of these says so explicitly;
this section is the rule itself, not a pointer to it.

**No engagement optimization.** CRAVE's north-star is decision
confidence, not conversion. No feature, experiment, or metric may treat
session duration, scroll depth, watch time, posting frequency,
follower growth, or virality as a success signal — in V1 or ever. A
confident "no" is a successful outcome. Enforced concretely in
Discovery, Native Posting, Notifications, and Analytics Principles
below.

**No paid influence inside personalized recommendation surfaces.** No
restaurant, partner, or business relationship may buy placement,
ranking, or visibility inside Feed, Discovery, Search, Map, or Place
Detail's recommendation content — regardless of future monetization
needs. If paid promotion exists at all, it lives in a separate,
structurally distinct, clearly labeled surface that never blends into
recommendation content. Enforced concretely in Restaurant Monetization,
Ads/Sponsorship Boundaries, and Restaurant/Business Tools below.

**No public-by-default personal taste data.** Rank, Craves, Taste
Profile, and unposted food history are private by default, always.
Discoverability of a profile's *existence* is a separate axis from the
privacy of what it contains. Enforced concretely in Profile, Taste
Profile, Rank Home, Craves, and Privacy/Deletion/Correction Propagation
below.

---

## 3. Core decision surfaces

### 3.1 Feed / Decision Session
**Status:** V1 REQUIRED
**V1 responsibility:** Adaptive entry point. Decision Session (Best
Fit / Safe Bet / Wildcard) dominates the top; CRAVE asks for context
only when uncertainty is material and the answer would change the set;
a persistent, correctable context chip is always visible; low
confidence is stated honestly rather than hidden.
**Non-goals:** Not an infinite feed. Never asks more than one context
question before recommending. Never pads to three cards with a weak
pick — three is a default, not a floor.
**Dependencies:** Cold-start fallback ranking; context-inference
pipeline; Craves-resurfacing rail (soft dependency, degrades
gracefully without it).
**Governing canon:** `CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` §9
(ranking), §11 (risk), §14 (roles); reconciliation map entries #1
(navigation) and #2 (role naming — Best Fit, not "Best Tonight").
**Codex rule:** Implement exactly the adaptive-ask/context-chip/honest-
confidence-labeling behavior above. Do not build a "Recommended for
you" strip with unexplained personalization — Bible §22.1 already
records that pattern as hidden until real signal exists; do not revive
it as a cosmetic fix.

### 3.2 Discovery (Personalized Discovery zone within Feed)
**Status:** V1 REQUIRED
**V1 responsibility:** Structured rails (each with a stated reason)
tapering into a bounded, finite mixed stream. Evidence-driven choice
between dish-first and restaurant-first presentation per item.
**Non-goals:** No infinite scroll. No popularity/trending rails. No
autoplay or muted-autoplay video previews — tap-to-play only, no
exception for "just muted."
**Dependencies:** Dish Intelligence (§4.4) data model for dish-first
presentation.
**Governing canon:** Decision Architecture §12 (exploration/
exploitation), §13 (diversity); Bible §5.2 (signal hierarchy).
**Codex rule:** The ranking objective for this zone may never include
dwell-time, scroll-depth, or session-length as a target — this is the
Discovery-specific instance of the No Engagement Optimization
prohibition (§2).

### 3.3 Search
**Status:** V1 REQUIRED
**V1 responsibility:** One input box, literal lookup and semantic
intent both resolved through it. Exact-name matches bypass the results
list. Vague/broad queries return a small reasoned set with an explicit
"Show more" (bounded batches, never a full unroll). Interpreted
constraints render as visible, editable chips.
**Non-goals:** No generic sort (distance/rating/popularity). No
person/profile search in the same box — food/place intent stays
primary. No comprehensive-inventory default for vague queries.
**Dependencies:** Constraint-interpretation engine (shared with Voice
Search and future-time queries, both deferred below).
**Governing canon:** Decision Architecture §3.5 (lookup vs. intent
discovery pipelines); Bible §24.
**Codex rule:** A vague query returning 40+ unfiltered results is a
direct regression Codex may not reintroduce under any framing
("comprehensive," "showing everything just in case").

#### 3.3a Voice Search
**Status:** LATER — DEFER
**V1 responsibility:** None.
**Non-goals:** No microphone input in V1.
**Dependencies:** Reuses 3.3's interpretation engine — no additional
architecture debt if 3.3 is built correctly (input-modality-agnostic).
**Governing canon:** Interview Search section.
**Codex rule:** Do not build. Do not special-case the interpretation
engine around text-only assumptions that would make adding this later
architecturally painful, but do not build the voice input path itself.

### 3.4 Craves
**Status:** V1 REQUIRED
**V1 responsibility:** Active intelligence scoped to saved interest —
the same recommendation engine as Decision Session, applied to a
pre-filtered pool. Opening Craves shows a small reasoned "try these
now" set, not a raw list. Want-to-Try/Tried state adapts automatically
from visit evidence; untouched saves decay in weight over time but are
never force-expired.
**Non-goals:** Not a bookmark dump. No manual-list-creation UI as the
primary organizing mechanism (see 3.4a).
**Dependencies:** Visit-detection (Rank action, manual "I went",
location, tagged post — multi-signal, none required alone); Save
action.
**Governing canon:** Bible §19 (Craves = Personal Food Memory).
**Codex rule:** The dominant content on open must be the reasoned
subset, not the full saved-places list — the full list is a secondary
view, not the landing state.

#### 3.4a Manual Craves lists
**Status:** LATER — DEFER
**V1 responsibility:** Automatic/implicit clustering only (cuisine,
occasion, geography-derived groupings like "Ramen," "Near Home").
**Non-goals:** No user-created custom lists ("Date Night," "Take Mom
Here") in V1.
**Dependencies:** None.
**Governing canon:** Interview Craves section.
**Codex rule:** Build automatic clustering; do not build list-creation/
management UI.

#### 3.4b Shared Craves
**Status:** LATER — ARCHITECT NOW
**V1 responsibility:** None shipped. Per-user taste representations
must be structured so two profiles can be meaningfully intersected
later without a schema rewrite.
**Non-goals:** No shared-space UI, no group Decision Session in V1.
**Dependencies:** A mutual invite/accept mechanism — a deliberate,
narrow exception to the single-Follow-graph rule (§5.3), not a general
second relationship primitive.
**Governing canon:** Interview Craves + Social Graph sections.
**Codex rule:** Do not build the feature. Do keep taste-profile storage
intersectable in principle (e.g. don't collapse it into an opaque blob
that can't be combined across two users later).

### 3.5 Rank Home
**Status:** V1 REQUIRED
**V1 responsibility:** Leads with recent visits waiting to be ranked
(the live task), not a static leaderboard view. Tiers (Elite/Love/
Good/Not for me) are the default display; exact numbers live behind
drill-down. Cuisine/context-scoped views are drill-downs, not separate
pages.
**Non-goals:** No full ordered list shown by default. No manual
placement of a restaurant without going through a comparison.
**Dependencies:** Rank Comparison (3.6); visit confirmation.
**Governing canon:** Decision Architecture §3.6 ("keep as one taste
signal, not the complete taste model"); reconciliation entry #1 (Rank
is a first-class tab, not a You/Profile sub-panel — Bible §26 is
annotated accordingly).
**Codex rule:** Rank is one of the five top-level tabs (§5-adjacent
navigation note below) — do not nest it under Profile.

### 3.6 Rank Comparison
**Status:** V1 REQUIRED
**V1 responsibility:** Restaurant-vs-restaurant is the dependable core
(preserve the existing shipped 3-stage tier→comparing→done flow and
signed comparison tokens exactly). Context-aware/cuisine-scoped
comparisons are allowed once evidence supports them. Real escape paths
exist for "too close to call" and "haven't been to one of these" —
these are legitimate outcomes, not failures to route around.
**Non-goals:** No forced binary choice when the honest answer is a tie.
No cross-category "which is better" comparison outside an explicit
context framing (e.g. "for a quick lunch, X or Y" is fine; a bare
"sushi vs. burger, which is better" is not).
**Dependencies:** None beyond what's already shipped.
**Governing canon:** Existing `frontend/app/rank/[placeId].tsx`
implementation; Decision Architecture §3.6.
**Codex rule:** Extend the existing mechanic with escape-path
affordances; do not rebuild the comparison flow from scratch.

#### 3.6a Dish Rank
**Status:** LATER — DEFER
**V1 responsibility:** None.
**Non-goals:** No dish-level comparison duel in V1.
**Dependencies:** Dish Intelligence (§4.4) data model must exist first
if this is ever built.
**Governing canon:** Interview Rank section.
**Codex rule:** Do not build. Restaurant-level Rank Comparison is the
only ranking mechanic in V1.

### 3.7 Place Detail
**Status:** V1 REQUIRED
**V1 responsibility:** Relationship-aware hierarchy (never-visited /
considering-tonight / visited / regular) changes what the top of the
page leads with. "For You" dish content is evidence-gated — falls back
to the plain menu when evidence is weak, never a fabricated claim.
Single adaptive primary CTA (Reserve > Directions > Save-for-tonight >
Save, in that priority order depending on context). Confidence and
data-completeness are shown as separate, both-honest facts, never
blended.
**Non-goals:** No star ratings — never. No dish-level "recommended for
you" without a real dish-affinity model behind it. No restaurant
public-response capability to user content.
**Dependencies:** Dish Intelligence (§4.4); a real user taste graph for
personalized "Why This Fits" reasoning beyond catalog facts (currently
does not exist — see below).
**Governing canon:** `CRAVE_PLACE_DETAIL_SPEC.md` (already implemented,
scored 75/100 — this is the current baseline, not a proposal);
reconciliation entry #4 (operational status honestly omitted, not
fabricated, until real `hours`/`is_open` data exists) and entry #5
("Seen on social" stays unassigned — see §3.7a below).
**Codex rule:** New work here extends the shipped Place Detail Spec
(relationship-aware states, evidence-gated For You) — it does not
replace its information architecture. Personalized "Why This Fits"
copy implying CRAVE knows the user's taste (not just catalog facts)
may not ship until Decision Architecture's Gate 2 (taste graph) is
real; until then, "Why This Fits" stays limited to percentile tier,
friend-ranking count, and the user's own past ranking, exactly as the
current Spec already correctly does.

#### 3.7a Imported "Seen on social"
**Status:** OPEN — DO NOT IMPLEMENT (a permanent surface placement)
**V1 responsibility:** None — this row exists to prevent a default
decision from being made by accident during other Place Detail work.
**Non-goals:** No permanent UI section for imported social-link content
until explicitly decided. It must not be silently merged with Native
Posting (§5.2) — different evidence class, different provenance/trust
characteristics.
**Dependencies:** Underlying import mechanics (Bible §20 — preserve
URL, resolve with confidence, allow manual correction, store
provenance) may continue to exist/function; only the Place Detail
*display placement* is frozen.
**Governing canon:** Reconciliation entry #5; Place Detail Spec §3.8/§8
item 10.
**Codex rule:** Do not assign this content a permanent Place Detail
section. If the import pipeline itself needs work, that's separate
from — and does not imply — a display decision.

### 3.8 Contextual Map
**Status:** V1 REQUIRED (as a contextual feature — not a top-level
tab; see reconciliation entry #1)
**V1 responsibility:** Spatial decision support (A) and destination
planning (C) are primary; nearby discovery (B) is secondary; a
personal food-history layer (D, see 3.8b) is excluded from V1
entirely. Bounded pin count (5-10 default, hard cap). List/map toggle
always available. "Search this area" reruns the recommendation engine
with the viewport as a constraint — it never retrieves everything in
the rectangle.
**Non-goals:** No top-level tab. No unbounded pin density. No live-
location social layer, ever, under any circumstance — only already-
public, food-relevant content may appear (e.g. a historical post), never
"X is here now."
**Dependencies:** Decision Session's and Search's own curated result
sets — Map visualizes them, it never computes an independent ranking.
**Governing canon:** Bible §23 (content still valid post-reconciliation
— only the tab assignment changed); reconciliation entry #1.
**Codex rule:** Map must render exactly the candidate set Decision
Session or Search already produced for the same query/context. Two
different rankings for the same underlying question is a correctness
bug, not a stylistic choice.

#### 3.8a Route-aware discovery ("on my way home")
**Status:** LATER — ARCHITECT NOW
**V1 responsibility:** None shipped, but the constraint/query schema
must include a route/corridor constraint type now.
**Non-goals:** No live routing computation in V1.
**Dependencies:** Shared query/constraint model with Search and Map.
**Governing canon:** Interview Map section.
**Codex rule:** Add the constraint type to the schema; do not implement
the routing logic behind it.

#### 3.8b Personal food-history map
**Status:** LATER — DEFER
**V1 responsibility:** None.
**Non-goals:** No V1 UI. When eventually built, must be opt-in, never
default-visible, never public, and mutually exclusive with the Craves-
on-map layer (only one personal layer visible at a time).
**Dependencies:** None blocking.
**Governing canon:** Interview Map + Profile privacy sections.
**Codex rule:** Do not build.

---

## 4. Personal identity & intelligence

### 4.1 Profile
**Status:** V1 REQUIRED
**V1 responsibility:** One of the five top-level tabs. Leads with
curated taste identity, then Rank status / food history / posts as
supporting sections. Craves, Rank, and Taste Profile content are
private by default (§2's third prohibition) — profile *existence* is
discoverable, its *contents* are not automatically exposed by that.
**Non-goals:** No numerical status counters (post count, ranked-places
count, visit count) as standalone vanity metrics. No free-text bio
inviting generic personality-performance content — if a bio-like field
exists, it should be an auto-generated food-preference tagline, not an
open box.
**Dependencies:** Taste Profile (4.3); Rank data (3.5).
**Governing canon:** Bible §26 (content valid; navigation superseded
per reconciliation entry #1).
**Codex rule:** Settings lives inside this tab; it is not a separate
tab.

### 4.2 Other User Profile
**Status:** V1 REQUIRED
**V1 responsibility:** Same screen type as 4.1, viewed for someone
else. Shows their food identity plus **taste compatibility with you**
— this specific use of the similarity signal is approved, distinct
from the still-open "follow this person" suggestion mechanic (4.6).
**Non-goals:** No follower-count-led framing. No exact public Rank
position by default (see 4.5, still open).
**Dependencies:** Follow graph (§5.3); the taste-similarity signal
(computed regardless of 4.6's open status — this is a separate,
already-approved use of it).
**Governing canon:** Interview Profile + Social Graph sections.
**Codex rule:** Taste-compatibility display may ship in V1. A "people
you may like" follow-suggestion feed may not (4.6).

### 4.3 Taste Profile
**Status:** V1 REQUIRED
**V1 responsibility:** Dedicated screen reached from Profile (not
Settings). Shows only confident inferences (uncertain traits show
"still learning this," never a premature claim). Every shown inference
is correctable via a four-action vocabulary: Not true / Doesn't matter
to me / Less of this / More of this. Explicit corrections outrank
passive inference and hold until behavior repeatedly contradicts them,
at which point the conflict is surfaced honestly rather than silently
resolved. Pause personalization, reset current recommendations, and
reset inferred taste (without deleting food history) are three
distinct, separately labeled actions.
**Non-goals:** No raw dump of every internal signal (e.g. no exposing
whose ranking opinions were weighted, no exposing raw behavioral event
weights). No fake-precision percentages.
**Dependencies:** User taste graph (Decision Architecture Gate 2).
**Governing canon:** Decision Architecture §6 (User Intelligence
Model), §23 (User Control and Taste Correction).
**Codex rule:** "Reset inferred taste" must never delete the
underlying factual record (Rank data, visit history, posts) — this is
the direct application of the adopted factual-history-vs-recommendation-
influence distinction (§5.1).

### 4.4 Dish intelligence
**Status:** LATER — ARCHITECT NOW
**V1 responsibility:** Dish modeled as a first-class entity with its
own evidence trail (not just menu text belonging to a restaurant) —
required now because Discovery (3.2), Search (3.3), and Place Detail
(3.7) all depend on evidence-driven dish-vs-restaurant presentation
choices in V1. The *data model* is V1-required even though the
screen-level dish features below are deferred.
**Non-goals (deferred, not V1):** No dish-level Rank (3.6a). No
dedicated dish detail pages — dishes lead into their restaurant's
Place Detail. No dish-level Craves as its own surface (a saved dish can
live as an attribute on the restaurant's Craves entry instead).
**Dependencies:** None blocking; this item is itself a dependency for
3.2/3.3/3.7.
**Governing canon:** Decision Architecture §2.4 ("dish and restaurant
affinity are separate"), §10; Bible §10.
**Codex rule:** Build the dish-as-entity data model now. Do not build
dish Rank, a dish detail page, or a dish-Craves surface for V1.

### 4.5 Social Rank
**Status:** OPEN — DO NOT IMPLEMENT
**V1 responsibility:** None. Rank stays private-by-default with no
public exposure surface at all (exact position, tier-only, or
favorites-only) until this is explicitly resolved.
**Non-goals:** No "just in case" toggle or hidden-by-default feature
flag for this — building the surface pre-emptively is itself an
implementation of an open decision.
**Dependencies:** A deliberate product decision, not an engineering
task.
**Governing canon:** Interview Rank section (repeatedly flagged open);
reconciliation map §4 (carried-forward open items).
**Codex rule:** Do not build any UI, endpoint, or schema field whose
only purpose is exposing another user's Rank data, even behind a flag.

### 4.6 Taste-similarity people recommendations
**Status:** OPEN — DO NOT IMPLEMENT (the follow-suggestion mechanic
specifically)
**V1 responsibility:** None for a "people you may like" feed. The
underlying similarity signal itself is approved and already required
for content-ranking (Discovery/Feed social-section weighting) and for
4.2's taste-compatibility display — only the explicit growth-facing
suggestion-to-follow feature is open.
**Non-goals:** No "suggested follows" UI, no follow-suggestion
notification, no onboarding "people to follow" step.
**Dependencies:** A deliberate product decision.
**Governing canon:** Interview Social Graph section; reconciliation map
§4.
**Codex rule:** The similarity signal may power ranking and
compatibility display (already-approved uses). It may not power any UI
whose purpose is growing the follow graph.

---

## 5. Content & social

### 5.1 Private food logging
**Status:** V1 REQUIRED
**V1 responsibility:** Logging (private, personal record) and posting
(shared, public-facing) are two different actions, not one action with
a visibility toggle. A private log requires no media. The private/
share choice is an explicit, visible, one-tap decision at the moment of
logging — never a silent default in either direction.
**Non-goals:** No forced media requirement for private logs. No
silently-applied default visibility.
**Dependencies:** None major.
**Governing canon:** Interview Posting section; reconciliation §2
(factual-history-vs-recommendation-influence applies directly to
correcting/deleting a logged entry's evidence weight vs. deleting the
entry itself).
**Codex rule:** A private log must be fully functional with zero media
attached and must never be converted to a public post without an
explicit user action.

### 5.2 Native posting
**Status:** V1 REQUIRED
**V1 responsibility:** Structured unit only — restaurant → optional
dish → media → optional reaction. Media required, photo-led, single
media per post (no carousel). Restaurant and dish identification both
require explicit confirmation before publishing. Reactions ("Made me
crave this") are private to the poster, never a public count, and the
reactor's identity is never shown to the poster either. No comments —
this is a durable product rule, not a launch-simplification, and
revisiting it later requires real re-justification, not just "more
engineering capacity."
**Non-goals:** No reposts or quote-posts, ever. No public like/follower
counts, ever. No DMs.
**Dependencies:** Dish Intelligence (4.4) for dish attachment; a
manual-search/submit-missing-restaurant fallback for low-confidence
identification.
**Governing canon:** Interview Social/Posting section; reconciliation
§2 (edits/deletion must recompute derived evidence, not just remove
the visible post).
**Codex rule:** The No Engagement Optimization prohibition (§2) applies
here directly — no feature that rewards posting frequency, follower
growth, or virality may be added under any framing ("just an
experiment," "just for launch marketing").

### 5.3 Follow graph
**Status:** V1 REQUIRED
**V1 responsibility:** Exactly one relationship type — Follow.
"Friends" elsewhere in this doc and in product copy is shorthand for
this graph, not a second relationship primitive. Private profiles may
turn following into a request/approval flow. Muting without unfollowing
and a separate "don't use this person's taste to influence mine"
control both exist — these are different axes (content visibility vs.
data-weighting) and must not be collapsed into one control.
**Non-goals:** No second "Friend" graph. Shared Craves' mutual-accept
mechanism (3.4b) is a narrow, explicit exception scoped to that one
feature, not a precedent for a general Friend primitive.
**Dependencies:** None blocking.
**Governing canon:** Interview Social Graph section.
**Codex rule:** One relationship table. Do not add a second one for
"friends" as distinct from "follows."

### 5.4 Activity inbox
**Status:** V1 REQUIRED
**V1 responsibility:** In-app, pull-based, present even when push
notifications are disabled. Holds private social reactions and follow
requests at minimum.
**Non-goals:** Not a sixth top-level tab.
**Dependencies:** Notification category definitions (5.5).
**Governing canon:** Interview App Structure + Notifications sections.
**Codex rule:** Reachable via a header icon from Feed/Profile, not a
tab-bar slot.

### 5.5 Notifications
**Status:** V1 REQUIRED
**V1 responsibility:** Every category individually controllable.
Legitimate for push: Rank reminders after a visit, follow requests,
reservation events (if reservations exist), a saved restaurant
reopening. In-app-only, never push, by default: a saved restaurant
becoming newly relevant, a new taste-matching restaurant, ordinary
friend-posting activity.
**Non-goals/Prohibited:** "Come back to the app" engagement
notifications with no concrete food value are **REJECTED /
PROHIBITED**, not merely deprioritized — this is the Notifications-
specific instance of the No Engagement Optimization prohibition (§2)
and admits no exceptions for growth experiments.
**Dependencies:** Per-category settings UI; Activity inbox (5.4).
**Governing canon:** Interview Notifications section.
**Codex rule:** A blanket single notification toggle is insufficient —
build per-category controls from the start.

### 5.6 Leaderboard
**Status:** AUDIT REQUIRED
**V1 responsibility:** Unchanged from current shipped behavior until
audited — this status is not itself a decision to keep or remove it.
**Non-goals:** Existing merely because it currently exists in code is
not sufficient justification to expand or promote it.
**Dependencies:** A screen-inventory audit verifying Leaderboard
performs a distinct breadth/activity job (places-logged ranking)
without duplicating Rank Home's preference-ordering leaderboard (3.5)
or rewarding posting volume/competition.
**Governing canon:** Interview App Structure section; reconciliation
map §4.
**Codex rule:** Do not redesign, expand, or "clean up" Leaderboard
under this status. It stays exactly as currently shipped until the
audit assigns it a real status (KEEP-scoped-to-breadth or REMOVE).

---

## 6. Commerce & business

### 6.1 Reservations
**Status:** LATER — DEFER (booking) / **V1 SUPPORTING** (deep-link CTA)
**V1 responsibility:** Place Detail's "Reserve" CTA may deep-link to an
external provider. No in-house availability/booking system.
**Non-goals:** No reservation backend, no availability calendar, no
in-app booking flow.
**Dependencies:** None blocking the deep-link case.
**Governing canon:** Interview Reservations/Ordering section.
**Codex rule:** Deep-link only.

### 6.2 Ordering
**Status:** LATER — DEFER
**V1 responsibility:** None. Delivery/pickup stays secondary to the
core discovery product even after V1.
**Non-goals:** No ordering integration of any kind in V1.
**Dependencies:** None.
**Governing canon:** Interview Reservations/Ordering section.
**Codex rule:** Do not build. CRAVE's job is deciding where to eat, not
fulfillment.

### 6.3 Restaurant/business tools
**Status:** LATER — DEFER (factual claiming/editing) with a permanent
**REJECTED / PROHIBITED** boundary on public response capability.
**V1 responsibility:** No business-facing surface ships in V1.
**Non-goals:** No restaurant analytics dashboard in V1. Public response
by a restaurant to user content (posts, reactions) is prohibited
permanently, not deferred — it is a durable rule, like No Comments
(5.2).
**Dependencies:** None blocking V1.
**Governing canon:** Interview Restaurant/Business section.
**Codex rule:** If restaurant-editable factual fields are ever built
(hours, menu, address), they may never include recommendation fit,
personal Rank, user posts, or user reactions. That boundary does not
expire.

### 6.4 Restaurant monetization
**Status:** LATER — DEFER (as a business model), with a permanent
**REJECTED / PROHIBITED** placement boundary.
**V1 responsibility:** No monetization surface of any kind in V1.
**Non-goals:** No paid-placement mechanism in any surface, at any
version — this is the Restaurant-Monetization-specific instance of the
No Paid Influence prohibition (§2).
**Dependencies:** None.
**Governing canon:** Interview Monetization section.
**Codex rule:** The recommendation-placement ban is permanent and
applies to every future version, not a V1 scoping choice that could
later be relaxed by a business decision alone.

### 6.5 Consumer premium
**Status:** LATER — DEFER
**V1 responsibility:** No premium tier in V1.
**Non-goals:** If a premium tier is ever built, it may never make
free-tier recommendation quality worse by comparison — that constraint
is permanent, not V1-scoped.
**Dependencies:** None.
**Governing canon:** Interview Monetization section.
**Codex rule:** Do not build. If asked to design this later, the
"never weaken free-tier quality" constraint carries forward unchanged.

### 6.6 Ads/sponsorship boundaries
**Status:** **REJECTED / PROHIBITED** (inside any personalized
recommendation surface) — permanently. A separate, structurally
distinct, clearly labeled sponsored surface is the only form paid
promotion could ever take, and even that concept is LATER — DEFER, not
V1 scope.
**V1 responsibility:** No sponsored content anywhere in V1.
**Non-goals:** No sponsored ranking, ever, in Feed, Discovery, Search,
Map, or Place Detail's recommendation content, regardless of future
business pressure.
**Dependencies:** None.
**Governing canon:** The No Paid Influence prohibition (§2); Decision
Architecture Banned Architecture List item 21 ("Let sponsored
placement contaminate organic recommendation scores").
**Codex rule:** No code path may let payment affect ranking, placement,
or visibility within any recommendation-content surface. This
prohibition cannot be lifted by a future ticket alone — it requires
the same explicit, traceable supersession process as anything else in
this document, and even then only for a separate, clearly labeled
surface, never the recommendation content itself.

---

## 7. Cross-cutting architecture principles

### 7.1 Privacy / deletion / correction propagation
**Status:** V1 REQUIRED
**V1 responsibility:** The two-operation model is canonical everywhere
user-correctable or user-deletable data exists: **correcting
recommendation influence** (a Taste Profile correction, "don't learn
from this") removes an item's effect on derived taste/ranking without
deleting the underlying factual record; **deleting user data** (account
deletion, a deleted post, a withdrawn save) removes the underlying
record itself, subject to the applicable retention/legal lifecycle.
**Non-goals:** No single blunt "delete everything" operation that
conflates the two.
**Dependencies:** This is itself a dependency of nearly every other row
in this document — it belongs in the data model from day one.
**Governing canon:** Decision Architecture §23-24; reconciliation map
§2 (adopted refinement, superseding the flatter framing used earlier
in product discussion).
**Codex rule:** Every feature that stores correctable or deletable user
data must implement both operations distinctly from the start.
Retrofitting this after the fact is explicitly harder than building it
in now — do not defer it as a "V2 cleanup."

### 7.2 Accessibility
**Status:** V1 REQUIRED
**V1 responsibility:** Screen-reader, low-vision, color-blind, motor-
limitation, larger-text, and reduced-motion support are baseline, not
a later pass. Recommendation meaning must remain understandable
without photography or color (already a free consequence of the
terse-reasoning-text pattern used everywhere). Every Map workflow needs
a list-equivalent. No swipe-only interaction exists anywhere in the
product — swipe-to-decide is a global, durable prohibition (see 5.2's
"No Comments" for the same durability pattern).
**Non-goals:** None — this is not optional scope.
**Dependencies:** None blocking; must be built alongside each item
above, not bolted on after.
**Governing canon:** Bible §33 (rubric category I); interview
Accessibility section.
**Codex rule:** No row in this document is "done" if it fails this
section's requirements, regardless of what its own status says.

### 7.3 Offline behavior
**Status:** V1 REQUIRED
**V1 responsibility:** Saved Craves, recent Place Details, Rank, and
personal food history remain viewable offline. When recommendations
can't refresh, show the last-known set with an honest timestamp rather
than either a fake-live view or a blank screen. Hours and availability
are the facts that become genuinely unsafe when stale; other content
degrades more gracefully.
**Non-goals:** No screen may rely on an infinite loading spinner as its
only offline/error state.
**Dependencies:** None blocking.
**Governing canon:** Bible §41-42; interview Empty/Error/Offline
section.
**Codex rule:** Every screen needs an explicit offline/stale-data state
as part of its definition of done, not an afterthought.

### 7.4 Analytics principles
**Status:** V1 REQUIRED (the discipline; not a specific dashboard)
**V1 responsibility:** North-star metric is successful-decision-rate /
decision-confidence — never engagement, time-in-app, or scroll depth.
Every recommendation event logs presentation position to guard against
training on position-bias feedback loops. Algorithm/model version IDs
are required before any ranking change ships.
**Non-goals:** No experiment or dashboard may report engagement metrics
as a primary success measure, in V1 or ever.
**Dependencies:** Recommendation ledger (Decision Architecture Gate 1,
already partially shipped).
**Governing canon:** Decision Architecture §18-19, §25; the No
Engagement Optimization prohibition (§2).
**Codex rule:** Reject any experiment design whose primary metric is
session duration, scroll depth, or engagement — this applies to
internal experimentation tooling, not just user-facing features.

### 7.5 Commercial-evidence separation
**Status:** V1 REQUIRED
**V1 responsibility:** Every piece of content/evidence carries a
source/provenance distinction — organic user evidence, restaurant-
verified factual content, or compensated/commercial content — visible
and structurally separated everywhere it appears (Place Detail today;
any future surface by the same rule). Compensated or restaurant-
employee-affiliated content must be disclosed and excluded from the
recommendation evidence graph.
**Non-goals:** No surface may blend commercial content into the organic
evidence stream without a visible distinction, regardless of how small
or well-intentioned the exception seems.
**Dependencies:** A source/provenance flag in the content data model —
required now, not addable later without a migration.
**Governing canon:** Decision Architecture §2.2 (evidence first, derived
intelligence second); the No Paid Influence prohibition (§2).
**Codex rule:** Build the source/provenance flag into the schema for
V1. This is a data-model requirement, not a UI-only concern that can be
retrofitted.

---

## 8. Codex Launch Boundary

> Codex may implement only items marked **V1 REQUIRED** or **V1
> SUPPORTING** unless a separate, approved contract explicitly promotes
> another item. **OPEN**, **AUDIT REQUIRED**, **LATER**, and
> **REJECTED** items may not be silently implemented.

This applies uniformly regardless of how small the implementation
looks, how obviously correct it seems, or how much easier it would be
to build now while related code is already open. A row's status in
this document is the only thing that authorizes work against it. If a
task appears to require touching an OPEN, AUDIT REQUIRED, LATER, or
REJECTED item to complete a V1 REQUIRED/SUPPORTING one, that is a
signal to stop and raise it — not a justification to implement the
blocked item incidentally.

Promoting a row's status is itself a product decision and follows the
same traceable process as everything else in this document: it is
recorded here (or in whatever supersedes this document the same way
the reconciliation map's process supersedes the original doctrine),
dated, and never a silent edit.

---

## 9. Next artifact

Per the agreed sequence, the next canonical artifact is the **Target
Screen Registry** — reconciling the existing ~20-route shipped app
against the V1 architecture approved in this document (five tabs:
Feed / Search / Craves / Rank / Profile, Map contextual-entry-only)
before any screen redesign work begins.
