# CRAVE Data & State Map

**Status:** Canonical scope artifact (2026-09-07)
**Purpose:** Makes the seven data-contract domains named in
`CRAVE_ROUTE_FLOW_MAP.md` §1.3 concrete — what state exists, its
lifecycle, who owns it, who reads it, and the hard rules that govern
it — so screen contracts have exactly one place to check before
inventing their own state shape. This is a product-level state
specification, not literal API/DDL — HTTP shapes, column types, and
migration mechanics are downstream engineering work, not decided here.

**Authority hierarchy:** same as prior artifacts — existing doctrine →
reconciliation map → annotated supersessions → V1 Scope → Target
Screen Registry → Route & Flow Map → this document.

---

## 1. Reconciliation with existing doctrine — this is not a new taxonomy

`CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` §28 already named nine
core data contracts (RecommendationSession, RecommendationCandidate,
RecommendationOutcome, TasteEvent, UserTasteProfile,
UserContextProfile, CurrentDecisionContext, DishIntelligence,
PlaceIntelligence), and §29 already established a Gate-based build
order with an explicit status note: **Gate 1 is partially shipped,
deliberately flattened** — a single `recommendation_events` table
(surface, event_type, position, rank_percentile-at-event-time, place,
user, session, city, query) rather than separate Session/Candidate/
Outcome tables, correct for a phase with no ranking model yet to need
that distinction. This document does not propose replacing that
flattened table today — it maps the Route & Flow Map's seven domains
onto these existing named entities and makes each concrete enough for
screen contracts to build against, while explicitly preserving Decision
Architecture's own discipline: **do not build ahead of need.**

| Route & Flow Map domain (§1.3) | Decision Architecture §28 entity | This document |
|---|---|---|
| 1. Recommendation request/context | RecommendationSession, RecommendationCandidate, CurrentDecisionContext | §2 |
| 2. Constraint | Folded into CurrentDecisionContext + UserContextProfile | §3 |
| 3. Visit evidence | New — extends TasteEvent/RecommendationOutcome (not separately named in §28) | §4 |
| 4. Taste evidence/correction | TasteEvent, UserTasteProfile | §5 |
| 5. Place operational-data | PlaceIntelligence | §6 |
| 6. Social evidence | New — not named in §28, a genuine gap it didn't cover | §7 |
| 7. Dish | DishIntelligence | §8 |

---

## 2. Recommendation request/context contract

**Purpose:** One shared contract for "ask the recommendation engine for
a bounded, personalized set" — used by Decision Session, Discovery, and
Craves' resurfaced choices alike. Three scoped callers, one contract,
never three divergent implementations.

**Request shape (in):** user id (or anonymous session id per F1),
context snapshot using the Context Engine dimensions already
established (Bible §6 — WHO/WHAT/WHEN/WHERE/WITH WHOM/CONSTRAINTS/
MEMORY/SOCIAL), candidate-pool scope (open catalog for Decision
Session/Discovery; saved-only for Craves), algorithm/profile version.

**Response shape (out):** 0-N candidates — never padded to a fixed
count. Each candidate carries: place/dish id, role (`best_fit` /
`safe_bet` / `wildcard` — Decision Session only; Discovery and Craves
use reason-coded framing instead of roles, per the already-locked
naming distinction that Search/Discovery must not borrow Decision
Session's exact vocabulary), reason codes (never free-text-generated —
Decision Architecture §17), confidence, a completeness flag (separate
from confidence, per the already-adopted distinction), and provenance
(which evidence produced this candidate).

**Lifecycle:** request → candidate generation → hard filter (§3) → rank
→ diversify → role-assign (Decision Session only) → respond. Already
partially shipped for Decision Session specifically
(`decision_session_builder.py` + `feed_ranker.py`); Discovery and
Craves need the *same* pipeline applied to a different candidate-pool
scope, not a divergent implementation.

**Ownership:** the backend recommendation service alone. No client ever
computes its own ranking — this is the concrete data-layer enforcement
of Codex Flow Invariant 4 (Map never computes its own candidate
ranking; it only renders what this contract already produced).

**Read access / consumers:** Feed (Decision Session + Discovery),
Craves, Map (read-only render of a set this contract already produced).

**Hard rules:** never pad with low-confidence filler to hit a target
count; never expose one opaque master score (Decision Architecture
§2.1); confidence and completeness stay separate fields, never blended
into one number.

---

## 3. Constraint contract

**Purpose:** Hard vs. soft constraint semantics, shared by Search, the
recommendation request contract (§2), and Map's future route/corridor
constraint.

**Shape:** every constraint carries a type and a source.
- **Always-hard types:** dietary restriction, allergy, religious/
  ethical food restriction.
- **Soft-by-default, user-promotable-to-hard:** budget ceiling,
  distance/travel willingness, chain avoidance.
- **Always-soft, session-scoped:** cuisine, occasion, time-of-day
  intent (Search's interpreted chips).
- **Sources:** a persistent user-level hard-constraint set (managed via
  Taste Profile/Settings), or an ephemeral session-scoped constraint
  attached to one request.

**Lifecycle:** constraints attach to a recommendation request (§2)
before candidate generation. Hard constraints filter *before* ranking
ever runs (Decision Architecture §9); soft constraints influence
ranking and are the only constraints eligible for relaxation (Route &
Flow Map F3.3's "smallest relaxation" behavior).

**Ownership:** the user directly controls persistent hard constraints;
session-scoped constraints are ephemeral, tied to one request/search
session, never silently persisted beyond it.

**Read access / consumers:** Search's interpretation engine, the
recommendation request contract (§2), Map's future route/corridor
constraint type (V1 Scope §3.8a, architect-now).

**Hard rules:** dietary/allergy/religious-ethical constraints are never
eligible for relaxation — a request that would violate one excludes the
candidate entirely, never surfaces it with a caveat instead. This is
the same non-negotiable line already drawn everywhere else this
distinction has come up (onboarding, Search, Shared Craves' most-
restrictive-wins rule).

---

## 4. Visit evidence contract

**Purpose:** Exactly the three-tier model the Route & Flow Map's F5.1
fix just made operational — declared/verified/inferred visit evidence,
and the standing distinction between factual history and recommendation
influence.

**Shape:** a visit evidence record carries: place id, user id, **tier**
(`declared` / `verified` / `inferred`), source signal(s) (Rank action,
manual "I went," tagged native post, location proximity), timestamp,
and — if promoted from inferred — a `confirmed_at` field. Two
independent boolean-like flags travel with every record: "counts as
factual history" (always true once recorded, never unset by a
correction) and "counts as recommendation influence" (true by default,
can be flipped off by an explicit correction without touching the
first flag).

**Lifecycle:** `inferred` → (user confirmation) → `declared`; or direct
entry as `declared`/`verified` (Rank action itself, explicit "I went,"
a tagged post with corroborating media). **Only `declared` or
`verified` evidence unlocks Rank-comparison-eligibility** — an
`inferred`-only record surfaces a confirmation prompt and grants
nothing on its own. Craves' Want-to-Try→Tried graduation accepts any
tier, including `inferred`-only, since that's a separate, lower-stakes
state transition, not a bypass of Rank's stricter requirement (Codex
Flow Invariant 12, already locked in the Route & Flow Map).

**Ownership:** written by Rank Comparison, Craves, the Native Posting
composer, and passive signals (location, only with permission granted
— never background location, per V1 Scope §7.1/interview Map section).

**Read access / consumers:** Rank Home (the ranking queue reads
`declared`/`verified` records only), Craves (graduation reads any
tier), Place Detail (relationship-aware state: never-visited/
considering/visited/regular derives from this record's presence and
tier).

**Hard rules:** an `inferred`-only record must never silently grant
Rank-comparison-eligibility. The factual-history flag persists
regardless of what happens to the recommendation-influence flag.

---

## 5. Taste evidence/correction contract

**Purpose:** The full evidence-strength hierarchy (impression < save <
rejection < visit < rank) as one coherent model, plus the two-operation
correction/deletion model already adopted from Decision Architecture
§23-24.

**Shape:** every taste-relevant event (Save, Rank comparison outcome,
post reaction, a visit evidence record from §4, Search behavior,
explicit Taste Profile corrections) is stored as an **immutable event**
— never a mutated running score with the causal event discarded
(Decision Architecture §2.2). Each event carries: type, strength tier
(from the locked hierarchy), a `recommendation_influence: active |
excluded` flag (independently toggleable, per §4's pattern), and
standard provenance (timestamp, source surface, session id).

**Lifecycle:** event recorded → contributes to the derived
UserTasteProfile (materialized, per Decision Architecture §28) →
correctable (flips the influence flag on one event or one inferred
trait) or deletable (removes the event entirely, triggers a profile
rebuild). The derived profile must always be rebuildable from the
retained event log — already a locked invariant (Decision Architecture
§30: "the derived taste profile can be rebuilt from authoritative
evidence").

**Ownership:** the recommendation/taste service owns the derived
profile; the user owns correction and deletion rights over their own
events via Taste Profile.

**Read access / consumers:** Taste Profile (correction UI), every
consumer of the recommendation request contract (§2) reads the derived
profile, never raw events directly.

**Hard rules:** correcting influence never deletes the underlying
event. Deleting an event always triggers a profile rebuild/retraction,
and that retraction is itself a logged, auditable action — never
assumed silently complete (Route & Flow Map F13.2).

---

## 6. Place operational-data contract

**Purpose:** Hours/status/menu freshness/provenance, matching the
already-shipped Place Detail Spec's honest-omission behavior exactly —
this document does not relitigate that spec, it names the data shape
underneath it.

**Shape:** every operational fact (hours, `is_open`, menu items, price)
carries its own freshness/provenance stamp — source, last-verified-at,
confidence — **independent of the place's overall taste-fit
confidence.** This is the concrete data-layer form of the confidence-
vs-completeness split already locked throughout this project.

**Lifecycle:** ingested from a catalog/menu data source (today, a real,
already-logged gap: no `hours`/`is_open` field exists at all — Place
Detail Spec §6) or submitted by a claimed restaurant (V1 Scope §6.3,
later). Displayed only when confidence crosses an honesty threshold;
**omitted, never fabricated**, otherwise.

**Ownership:** the catalog/menu ingestion pipeline for the base data;
restaurant-submitted factual edits (later capability) write to the same
records but are tagged by source so an ingested fact is always
distinguishable from a restaurant-submitted one.

**Read access / consumers:** Place Detail's Decision Strip and Menu
section, Search's dietary hard-exclusion check (§3), Map's operational-
status display, the dish contract's menu-freshness dependency (§8).

**Hard rules:** never show a fact with more confidence than its actual
source data supports — the same "menu last verified 12 days ago, not
'may have changed'" precedent that's governed every freshness decision
in this project.

---

## 7. Social evidence contract

**Purpose:** Native organic posts, followed-person evidence, commercial/
affiliated content, and imported "Seen on social" content kept visibly,
structurally distinct — a genuine gap Decision Architecture §28 didn't
separately name, since it predates the social/posting design work.

**Shape:** every piece of social content carries a mandatory
`source_type` enum: `organic_user` / `followed_user` / `commercial_
affiliated` / `imported_external`. Reactions ("Made me crave this") are
private-scoped records tied to one poster and one reactor — never
aggregated into a public count field, anywhere.

**Lifecycle:** created via the Native Posting composer (`organic_user`)
or the existing social-link-import pipeline (`imported_external` — Bible
§20: preserve original URL, resolve with confidence, never silently
attach the wrong restaurant, allow manual correction, store
provenance). Deleting or correcting a post retracts its derived
evidence per §5's rules exactly.

**Ownership:** the poster owns edit/delete rights over their own
content. Commercial/affiliated content is restaurant-owned but
structurally separated from the organic evidence stream — never
blended, per the standing prohibition (V1 Scope §6.3/§7.5).

**Read access / consumers:** Feed's social rail, Place Detail's social
section, Craves (the `social_link_imported` event type already named in
Bible §5.1's event taxonomy is this contract's `imported_external`
case).

**Hard rules:** `source_type` is mandatory on every record, set at
creation, never inferred or reclassified after the fact. This contract
defines the data shape only — `imported_external` content's Place
Detail display placement stays explicitly unassigned/OPEN (Route & Flow
Map §1.1/§5.1a) regardless of how cleanly this contract is implemented;
a clean data shape does not itself resolve that open product question.

---

## 8. Dish contract

**Purpose:** Dish as a first-class child of restaurant, with its own
evidence and freshness trail, independent of restaurant-level affinity
(Decision Architecture §2.4, already locked) — while dish Rank stays
explicitly deferred.

**Shape:** a dish entity carries: its own id, parent restaurant id,
name, attributes (spicy/savory/sweet/rich/light/crispy/etc., per Bible
§10), and a menu-freshness stamp sharing §6's freshness model exactly
(a dish's data is only as trustworthy as the menu it came from).
Dish-level evidence (saves, reactions, "For You" eligibility) is its
own accumulation trail, scoped to the dish id, structurally separate
from the parent restaurant's evidence.

**Lifecycle:** a dish is identified via menu ingestion or user
confirmation during Native Posting (Route & Flow Map F6.3); evidence
accumulates the same way restaurant-level evidence does (§5's model),
just at dish scope.

**Ownership:** the same ingestion/restaurant-editing pipeline as §6 for
factual dish data (name, attributes); users write dish-level evidence
via Save, reactions, and posts.

**Read access / consumers:** Discovery's dish-first presentation
choice, Search's dish results, Place Detail's evidence-gated "For You"
section.

**Hard rules:** this contract must not presuppose a dish-comparison
mechanic — dish Rank is out of scope for its V1 form (V1 Scope §3.6a,
LATER — DEFER). The contract is an evidence-accumulation shape only,
not a ranking one.

---

## 9. Cross-cutting: analytics/event-taxonomy contract

Flagged as a dependency in the Route & Flow Map; resolved here rather
than left implicit. The `surface` value on the existing (shipped, Gate-1)
`recommendation_events` table expands to a fixed enum, scoped to
recommendation-generating surfaces specifically (not every screen needs
a `surface` value — Place Detail, Activity, and Profile log their own
distinct event types instead, per §10 below):

- `decision_session`
- `discovery`
- `craves`
- `search`
- `map`
- `map_direct` — the residual contextless-Map-open case (Route & Flow
  Map F9.3), deliberately kept distinct so it's measurable and, if it
  turns out to be common post-migration, worth revisiting rather than
  silently absorbed into `map`.

Rank Comparison is **not** a `surface` value in this sense — it already
has its own distinct event types (`comparison_started`,
`comparison_resolved`) per Decision Architecture §5.1, correctly kept
separate from the impression/click pattern since a comparison isn't a
"recommendation shown, did they click it" event.

**Hard rule:** every event must always log its presentation position
alongside its surface — the concrete data-layer form of Decision
Architecture §19's position-bias guard, already locked and not
renegotiable here.

---

## 10. Cross-cutting: non-recommendation event types

For completeness, since §9 scoped itself deliberately narrow: Activity
(`activity_viewed`, `activity_item_opened`), Place Detail relationship-
state views, Taste Profile corrections (`taste_correction`, three
distinct reset/pause event types per Route & Flow Map F7.3), and auth
gate events (`auth_gate_shown` / `gate_completed` / `gate_abandoned`,
tagged by originating action type) are their own event families, not
folded into the `surface` enum above. This keeps the recommendation-
specific taxonomy in §9 from becoming a dumping ground for every event
in the app.

---

## 11. Codex Data Invariants

Behaviors the data model may not reinterpret, regardless of how a
downstream schema or screen contract phrases them:

1. No client ever computes its own recommendation ranking. The request/
   context contract (§2) is the only source of a ranked candidate set.
2. Confidence and completeness are always separate fields on a
   recommendation candidate — never collapsed into one number.
3. Dietary/allergy/religious-ethical constraints are never eligible for
   relaxation logic, at the data layer or above it.
4. Visit evidence below the `declared`/`verified` tier never grants
   Rank-comparison-eligibility, regardless of which surface wrote the
   `inferred` record.
5. Every taste-relevant event is immutable once written. Corrections
   flip an influence flag; they never rewrite or delete the event they
   apply to.
6. Deleting a user's data always triggers a logged retraction of
   whatever it derived — retraction is a first-class, auditable
   operation, never an assumed side effect.
7. Every operational-data fact (hours, menu, price) carries its own
   freshness/provenance, independent of the place's taste-fit
   confidence — a screen may never infer factual freshness from
   recommendation confidence or vice versa.
8. `source_type` on social content is mandatory at creation and
   immutable thereafter. No content is ever silently reclassified from
   `commercial_affiliated` to `organic_user` or vice versa.
9. Dish-level evidence never implies dish-level ranking exists. A
   consumer reading dish evidence for "For You" personalization must
   not assume a dish-Rank feature is available just because evidence
   accumulation is.
10. Every recommendation event logs presentation position alongside
    surface — no exceptions for "just this once, it's a minor surface."

---

## 12. Downstream dependencies

**Privacy/Permission Matrix** (next-but-one artifact):
- Exactly which fields in §4/§5 are exposed by which correction/
  deletion action, per data type — this document states the two-
  operation *model*, the Permission Matrix states the exhaustive,
  authoritative per-field mapping.
- Auth requirement per contract read/write (this document notes
  ownership; the Permission Matrix is where that becomes the
  exhaustive reference, per the Route & Flow Map's own deferral).
- The location-permission fallback (§4's passive-signal ownership note)
  formalized per surface.

**Component/Design System** (later):
- How confidence/completeness/reason-codes/tiers actually render
  (badges, copy, iconography) — this document defines the fields exist
  and their meaning, not their visual treatment.

**Screen contracts** (once this document + the Component/Design System
exist):
- Rank Home and the Native Posting composer remain the two highest-
  priority contracts — both are now unblocked at the data-model level
  by §4 (visit evidence) and §8 (dish), respectively.
- Onboarding's cold-start calibration step (Route & Flow Map §1.2) can
  now be specified concretely: it writes to §5 (Taste evidence) as
  `declared`-tier lightweight comparisons plus §3 (Constraint) for
  dietary/allergy hard constraints and novelty starting position.

---

## 13. Next artifact

Per the agreed sequence, the next canonical artifact is the
**Privacy/Permission Matrix** — the exhaustive, field-by-field
authority on what's exposed to whom, under what auth state, and what
propagates on correction versus deletion, built directly on the seven
contracts made concrete here rather than rediscovering their shape.
