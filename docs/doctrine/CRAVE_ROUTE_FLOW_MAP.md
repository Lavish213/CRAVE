# CRAVE Route & Flow Map

**Status:** Canonical scope artifact (2026-09-07)
**Purpose:** Journey- and transition-focused, not another screen
inventory. Answers how a user moves through CRAVE, what state crosses
each boundary, what terminates a flow, and what must never become a
dead end. Resolves the three judgment calls `CRAVE_TARGET_SCREEN_REGISTRY.md`
carried forward rather than leaving them as vague blockers.

**Authority hierarchy:** same as prior artifacts — existing doctrine →
reconciliation map → annotated supersessions → V1 Scope → Target Screen
Registry → this document.

---

## 1. Resolved judgment calls

### 1.1 `friends-feed.tsx` — MERGE / REMOVE AFTER MIGRATION

Not preserved as a standalone first-class destination. Its useful job
survives, split across two homes: native social evidence belongs
contextually in Feed's embedded social rail and in Place Detail; social
activity/notifications belong in Activity (flow F8 below). A dedicated
friends feed risks recreating a social-network consumption surface
CRAVE explicitly does not want (the same reasoning already applied to
rejecting comments, reposts, and follower counts). The route is kept
only as temporary migration/deep-link compatibility scaffolding until
Feed's rail and Activity both exist, then removed. `CRAVE_TARGET_SCREEN_REGISTRY.md`
§5.3 is updated to reflect this resolution, not left as an open
question.

### 1.2 `profile-setup.tsx` — REBUILD / SPLIT BY FUNCTION

Not automatically one future onboarding page. Three genuinely distinct
responsibilities:

- **Pre-account value experience** — needs no screen here at all. It's
  Feed itself, browsed anonymously (F1.1/F1.2 below), gated only at the
  first stateful action.
- **Cold-start calibration** — dietary/allergy hard constraints, a
  novelty-dial starting position, and lightweight reactions to 3-5
  self-identified known restaurants (reusing Rank Comparison's
  lightweight-reaction pattern, not a new mechanic).
- **True identity setup** — the username claim that is this screen's
  *entire current job*. This may be an earlier or later step in the
  same stack flow relative to calibration, but must not be bloated by
  bundling calibration items into it indiscriminately — it stays a
  functionally distinct step, tracked separately, resolved fully once
  the Data & State Map defines what calibration actually needs to
  persist. `CRAVE_TARGET_SCREEN_REGISTRY.md` §6.1 is updated
  accordingly.

### 1.3 Shared data contracts — product-level boundaries, not schemas

Per explicit instruction, this document defines contract *boundaries*
only. Concrete API/schema design is downstream work for the Data &
State Map (§6 below names each one as a dependency). The seven
domains established here:

1. **Recommendation request/context contract** — user/context/
   location/time/session constraints in; bounded personalized
   candidates with role, reasoning, confidence, provenance, and
   completeness out. Powers Decision Session, Craves' resurfaced
   choices, and Discovery alike — one contract, three scoped callers,
   never three divergent implementations.
2. **Constraint contract** — hard vs. soft constraint semantics.
   Dietary/allergy restrictions are never silently relaxed by any
   relaxation logic; only soft constraints (distance, price, cuisine)
   are eligible for the "smallest relaxation" behavior.
3. **Visit evidence contract** — declared / verified / inferred visit
   evidence, each with a confidence and source; and the standing
   distinction between factual history (what happened) and
   recommendation influence (what it's allowed to affect).
4. **Taste evidence/correction contract** — Save, Rank, reactions,
   visits, Search behavior, explicit corrections, and deletion/
   retraction propagation, all as one coherent evidence model with the
   already-locked strength hierarchy (impression < save < rejection <
   visit < rank).
5. **Place operational-data contract** — hours/status/menu freshness
   and provenance, with honest omission (never fabrication) when
   current data is unavailable.
6. **Social evidence contract** — native organic posts, followed-
   person evidence, commercial/affiliated content, and imported
   external "Seen on social" content kept visibly, structurally
   distinct at all times — never blended into one undifferentiated
   evidence type.
7. **Dish contract** — dish as a first-class child of restaurant, with
   its own evidence and freshness, independent of restaurant affinity;
   dish Rank remains a later capability layered on top, not required
   for the contract itself to exist.

---

## 2. Navigation invariants

These are fixed verbs, not descriptions — no flow below may repurpose
a surface for a job that isn't its own:

| Surface | Verb |
|---|---|
| Feed | Decide |
| Search | Ask with intent |
| Craves | Resolve saved intent |
| Rank | Explicitly teach CRAVE |
| Profile | Understand your food identity |
| `+` | Record food evidence |
| Map | Spatial support |
| Activity | Event inbox |

---

## 3. Major V1 flows

Each flow names its transitions (`F<n>.<m>`), used again verbatim in
the Flow Ownership Matrix (§4).

### F1 — Cold start → first useful Feed → account gate on first stateful action

A new/anonymous user must see real value before any account is
required. Feed shows an honestly-labeled, lower-confidence Decision
Session powered by city-popularity fallback plus whatever anonymous-
session evidence exists. The account gate triggers only at the first
stateful action (Save, Rank, Post/Log) — never earlier. Must never dead
end: an abandoned gate must return the user to exactly where they were
with the pending action intact; anonymous evidence must be eligible for
migration once an account exists, not discarded.

- **F1.1** Cold open, no account → Feed shows lower-confidence Decision
  Session.
- **F1.2** Anonymous browsing accumulates weak evidence, attached to
  the anonymous session id.
- **F1.3** First stateful action attempted → account gate shown,
  pending action preserved.
- **F1.4** Account created → eligible anonymous evidence migrates to
  the new identity, migration itself logged for provenance.

### F2 — Feed Decision Session → Place Detail → act/save/reject

The core decision loop. A card tap carries its role/reasoning/session
id into Place Detail, which frames its Decision Strip honestly around
why the user is there. Rejecting a card replaces only that slot and
logs differentiated negative evidence by role. Two consecutive
full-set rejections trigger a direct ask instead of silent infinite
regeneration. Must never dead end: a rejected slot either gets a
trustworthy replacement or an honest "nothing else confident right
now" — never a card that vanishes with no explanation.

- **F2.1** Tap card → Place Detail, entry-source-aware framing.
- **F2.2** Reject one card → that slot only regenerates (or shows
  nothing if no trustworthy replacement exists — never a padded weak
  pick).
- **F2.3** Commit action (Reserve/Directions/Save-for-tonight) → external
  deep-link or in-app confirmation; routes to F10 if unauthenticated
  and the action requires it.
- **F2.4** Two consecutive full-set rejections → explicit "what's off
  tonight" prompt, replacing silent regeneration.

### F3 — Search → interpretation → result → Place Detail/Map

One box, literal or semantic. Interpreted constraints render as
editable chips. Exact-name confidence bypasses the results list.
Zero-result queries always produce a named, specific relaxation offer.
A pivot to Map inherits the exact same candidate set — Map never
re-ranks.

- **F3.1** Query submitted → interpreted, constraint chips rendered.
- **F3.2** Exact-name high confidence → Place Detail directly, organic
  framing (no Decision-Session/Discovery language).
- **F3.3** Zero results → named, specific relaxation offer, not a bare
  "no results."
- **F3.4** Pivot to Map → identical result set rendered spatially.

### F4 — Craves → resurfaced choice → Place Detail/Map

Opening Craves runs the same recommendation engine as Decision Session,
scoped to the saved pool. Selecting a result carries a Craves-specific
origin into Place Detail (distinct framing from Decision Session or
Search). Must never dead end: if nothing saved currently makes sense,
Craves says so honestly and points to Search/Discovery rather than
showing a stale or silently-empty reasoned section.

- **F4.1** Open Craves → reasoned "these make sense tonight" subset
  generated from the saved pool.
- **F4.2** Tap a result → Place Detail, Craves-origin framing,
  original save reason remembered if available.
- **F4.3** View on Map → the intelligently-prioritized subset, never a
  raw dump of every save.

### F5 — Visit/log → Rank queue → comparison → taste update

Any one corroborating signal (Rank action, manual "I went," location,
tagged post) is sufficient to queue a visit for ranking — never
requires all signals, never graduates silently with none. Rank Home
surfaces the queue; the comparison flow (existing, hardened mechanic)
produces a placement or an honest tie/insufficient-data outcome, which
becomes the system's highest-integrity taste signal. A queued item left
unranked decays in priority rather than nagging or vanishing.

- **F5.1** Visit confirmed (any one signal) → enters Rank queue.
- **F5.2** Rank Home → tap queued item → Rank Comparison (existing
  tier→comparing→done flow, unchanged).
- **F5.3** Comparison resolves (win/loss/tie/insufficient-data) → Rank
  data updates; a tie is a real outcome, never a fabricated tiebreak.
- **F5.4** Queued visit left unranked → decays in priority; factual
  visit record persists regardless of ranking status.

### F6 — Persistent `+` → private log or public post

`+` opens a capture sheet, then flows through confidence-gated
restaurant identification (degrading to manual search, never blocking),
optional dish identification, a quick-take reaction, and an explicit
private/friends/public choice. Private logs never require media and
never silently become public. Evidence is only emitted at publish, not
at each intermediate step, so abandoned drafts don't pollute the
Ledger.

- **F6.1** Tap `+` → capture sheet (Take Photo / Choose Photo / Choose
  Video).
- **F6.2** Media captured → restaurant identification shown, or manual
  search fallback if confidence is low.
- **F6.3** Restaurant confirmed → optional dish identification → quick-
  take reaction.
- **F6.4** Explicit visibility choice → publish (private log or
  friends/public post); this is also F5.1's visit-confirmation signal.

### F7 — Profile → Taste Profile → correction

Profile leads with curated taste identity; Taste Profile shows only
confident inferences, each correctable via the four-action vocabulary.
A correction takes effect on recommendation influence immediately
without touching the underlying factual record. Pause/reset-
recommendations/reset-inferred-taste are three distinct actions with
different blast radii, never conflated.

- **F7.1** Profile → Taste Profile.
- **F7.2** Correct a trait → recommendation influence updates; factual
  events untouched (§1.3 domain 3/4 in effect here directly).
- **F7.3** Pause / reset-recommendations / reset-inferred-taste → three
  distinct, separately-logged actions.

### F8 — Activity → relevant event → destination

Pull-based inbox holding private reactions and follow requests at
minimum. Tapping an event routes to its referenced destination. Must
never dead end: a destination that no longer exists (deleted post,
place gone) degrades to an honest "no longer available," never a raw
navigation error.

- **F8.1** Open Activity → event list.
- **F8.2** Tap an event → referenced destination, or an honest
  unavailable-state if it's gone.

### F9 — Contextual Map entry from Feed/Search/Craves

Map has no independent entry point of its own — it only ever renders a
candidate set someone else already produced. A residual contextless
open (if one survives migration) falls back to the same bounded default
Feed itself uses cold.

- **F9.1** Decision Session → "Map these picks" → exactly the up-to-
  three cards, spatially.
- **F9.2** Search/Craves → "view on map" (see F3.4/F4.3 — not
  duplicated here).
- **F9.3** Contextless open (residual) → bounded default ("3 places
  near you right now"), never raw density.

### F10 — Auth-gated stateful actions

The general form of every gate invoked by F1.3, F4.1/F4.2 (Craves
itself requires auth), F5 (Rank), F6.4 (publish), and F7 (corrections).
Consolidated here so Codex implements one shared gate, not five
ad hoc ones — a risk the Target Screen Registry's Migration Risks
section already flagged.

- **F10.1** Any stateful action while signed out → shared AuthSheet,
  pending action preserved and replayed automatically post-auth.

### F11 — Offline/stale-data recovery

One shared pattern, not a per-screen invention. Every screen with live
data shows last-known content with an honest timestamp when a fetch
fails; facts that are genuinely unsafe when stale (hours, availability)
get an explicit caveat beyond the general staleness label.

- **F11.1** Live fetch fails → last-known data + timestamp shown.
- **F11.2** Stale data includes an unsafe fact (hours/availability) →
  explicit caveat, distinct from the general staleness label.

### F12 — Blocked-location fallback

Location permission is optional everywhere with graceful manual
fallback — not just on Map, but anywhere location would otherwise drive
context (Feed, Search, Craves).

- **F12.1** Permission denied/unavailable → manual "Choose an area"
  substitutes for device location for the rest of the session.

### F13 — Deletion/correction propagation

The two-operation model, applied uniformly: correcting recommendation
influence never deletes the factual record; deleting user data always
propagates to derived evidence, and that propagation is itself
auditable, not silently assumed complete.

- **F13.1** Correct recommendation influence → applied to derived
  taste/ranking; factual event retained.
- **F13.2** Delete underlying data (post/save/account) → record
  removed per retention lifecycle; derived evidence retraction is
  logged and required, not best-effort.

### F14 — Successful "confident no" exit path

A session ending in considered rejection or no action is a first-class
terminus, not a failure state to route around — the direct operational
consequence of "decision confidence, not conversion."

- **F14.1** User reviews a reasoned set and takes no action, or
  explicitly declines all → session ends here; this must be recorded as
  a successful outcome, never as abandonment, in any analytics view.

---

## 4. Flow Ownership Matrix

Compact form; full detail for each row lives in the flow narrative
above. Columns: **Source → Trigger → Destination → State carried →
Auth → Offline → Analytics/evidence → Failure recovery.**

### F1 — Cold start

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F1.1 | App launch | First open, anonymous | Feed (low-confidence) | anonymous session id created | none | falls to F11 if offline at cold open | impression, confidence=low | honest empty/failure state, never blank |
| F1.2 | Feed/Discovery/Search | Anonymous engagement | same session | weak evidence attached to session id | none | logging queued/skipped | impression/click under anon id | none needed (best-effort) |
| F1.3 | Any surface | Save/Rank/Post attempted | AuthSheet | pending action preserved for replay | required from here | action queues, gate deferred until online | gate_shown / gate_completed / gate_abandoned (separate) | return to exact prior state, action retained |
| F1.4 | Auth gate | Account created | Feed/Profile, authenticated | anon evidence migrated | authenticated | n/a | migration event, provenance preserved | partial migration must not block account use |

### F2 — Feed Decision Session

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F2.1 | Feed | Tap card | Place Detail | role, reason codes, session id | none to view | last-known + timestamp | click w/ role+position | ErrorState + retry |
| F2.2 | Feed | Reject one card | same slot regenerates | rejection reason by role | none for reject itself | rejection queued, fetch deferred | rejection event w/ role+reason | slot shows nothing if no trustworthy replacement |
| F2.3 | Place Detail | Tap adaptive primary CTA | external deep-link or in-app confirm | strong-signal commit event | required for Save-for-tonight only | Save queues; deep-links need connectivity | strong-signal event, distinct from click | deep-link failure → show address/phone directly |
| F2.4 | Feed | 2 consecutive full-set rejections | direct "what's off" prompt | session-level rejection pattern | none | n/a | session-rejection-pattern event | dismissed prompt → falls to F14 |

### F3 — Search

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F3.1 | Search | Query submitted | results (same screen) | interpreted constraint set | none | cached results + staleness label | search_session_id, impressions | ambiguous parse → literal keyword fallback |
| F3.2 | Search | Exact-name, high confidence | Place Detail (organic framing) | resolved place id only | none | needs connectivity unless cached | "direct resolve" event, distinct from click | n/a (success path) |
| F3.3 | Search | Zero results | same screen, named relaxation offer | original constraint set retained | none | offline looks like zero-result — must show F11 instead | zero-result event w/ constraint set | is itself the recovery path |
| F3.4 | Search | "View on map" | Contextual Map | identical bounded result set | none | list-view fallback if map data unavailable | map-view event w/ search_session_id | list view, not error screen |

### F4 — Craves

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F4.1 | Craves | Tab open | reasoned subset | context inputs, saved-pool scope | required | last-known subset + staleness | impression, surface=craves | honest "nothing fits right now" + pointer to Search |
| F4.2 | Craves | Tap a result | Place Detail (Craves framing) | save reason, Craves-origin flag | required | same as F2.1 | click, surface=craves | same as F2.1 |
| F4.3 | Craves | "View on map" | Contextual Map, Craves layer | prioritized subset, not raw dump | required | last-known layer | map-view, surface=craves | list-view fallback |

### F5 — Visit → Rank → taste update

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F5.1 | Rank/manual/location/post | Any one signal | Rank queue | place, signal type(s), timestamp | required | queued locally, synced later | visit_confirmed w/ source | n/a |
| F5.2 | Rank Home | Tap queued item | Rank Comparison | signed comparison tokens (existing) | required | needs connectivity (existing constraint) | comparison_started | existing retry mechanic |
| F5.3 | Rank Comparison | Winner picked / tie / haven't-been | Rank Home update or retry pair | comparison outcome, tie is real | required | outcome queued if dropped mid-flow | comparison_resolved w/ outcome type | pending, never silently discarded |
| F5.4 | Rank Home | Left unranked | same screen, priority decays | factual visit record persists | required | n/a | optional light dismiss signal | n/a |

### F6 — `+` capture

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F6.1 | Any tab | Tap `+` | capture sheet | none yet | required only at publish | capture works offline, publish queues | composer_opened | existing permission-handling pattern |
| F6.2 | Composer | Media selected/captured | ID shown or manual search | media ref, inferred context | same as F6.1 | inference offline; catalog match needs connectivity | identification_shown w/ confidence | low confidence → manual search, never blocked |
| F6.3 | Composer | Restaurant confirmed | dish suggestion + quick-take | restaurant id, optional dish id, reaction | same as F6.1 | queued if offline | none until publish (avoids draft noise) | dish miscorrection inline before publish |
| F6.4 | Composer | Visibility chosen | private log or public/friends post | full structured unit | required (or defers via F10) | private log completes fully offline (no media required) | post_published/log_created w/ visibility; also feeds F5.1 | failed publish keeps draft, never discards |

### F7 — Profile / Taste Profile

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F7.1 | Profile | Tap taste identity | Taste Profile | none | required | last-known + staleness | taste_profile_viewed | ErrorState + retry |
| F7.2 | Taste Profile | Correction tapped | same screen updates | correction only, factual events untouched | required | queued, applied on reconnect | taste_correction event | no optimistic-success lie |
| F7.3 | Taste Profile | Pause/reset-rec/reset-taste | confirmation | three distinct blast radii | required | queued | three distinct event types | same as F7.2 |

### F8 — Activity

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F8.1 | header icon | Tap | Activity inbox | none | required | cached event list | activity_viewed | ErrorState + retry |
| F8.2 | Activity | Tap event | referenced destination | reference id | required | destination's own offline state applies | activity_item_opened | honest "no longer available" if gone |

### F9 — Contextual Map entry

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F9.1 | Feed | "Map these picks" | Map, exact 3 cards | candidate set, roles, reasoning | inherited from Decision Session | list-view fallback | map-view, surface=decision_session | same as F3.4 |
| F9.3 | (residual entry) | Contextless open | bounded default | none | none for default view | falls to F11 | map-view, surface=map_direct (flag for Data & State Map) | same as other Map entries |

### F10 — Auth gate (general form)

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F10.1 | any surface | Stateful action, signed out | shared AuthSheet | pending action, replayed post-auth | is the gate | queued, gate deferred | auth_gate_shown w/ action type | return to exact prior state |

### F11 — Offline/stale recovery (general form)

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F11.1 | any live-data surface | fetch fails | same screen, last-known + timestamp | cached data | as already required | is the offline state | offline_state_shown | auto-retry on reconnect (AppState-driven) |
| F11.2 | Place Detail/Map/Search | stale unsafe fact | same screen, explicit caveat | same as F11.1 | same | same | same event, tagged fact type | same |

### F12 — Blocked-location fallback

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F12.1 | Feed/Search/Map/Craves | permission denied/absent | manual "Choose an area" | manual area substitutes for device location | none | area list cached; live gen needs connectivity | location_fallback_used | is itself the recovery |

### F13 — Deletion/correction propagation (general form)

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F13.1 | Taste Profile/reactions/etc. | explicit correction | confirmation | recommendation influence changes; factual event kept | required | queued | correction event | same as F7.2 |
| F13.2 | Composer/Craves/Settings | explicit delete | removal | record removed; derived evidence retraction required | required | queued, no false success | deletion + retraction event (separate) | surfaced as in-progress if partial |

### F14 — Confident-no terminus

| ID | Source | Trigger | Destination | State carried | Auth | Offline | Analytics/evidence | Failure recovery |
|---|---|---|---|---|---|---|---|---|
| F14.1 | Feed/Search/Craves | reviewed, no action / explicit decline | session ends here | rejection/no-action evidence, normal weighting | inherited | n/a | **recorded as successful outcome, never abandonment** | n/a — nothing to recover |

---

## 5. Codex Flow Invariants

Behaviors implementation may not reinterpret, regardless of how a
specific screen contract phrases them later:

1. A confident "no" or no-action outcome (F14) is a successful session
   terminus. It must never be logged, dashboarded, or reasoned about as
   abandonment or failure.
2. Decision Session rejection (F2.2) replaces only the rejected slot.
   Two consecutive full-set rejections (F2.4) trigger a direct ask —
   never silent, indefinite regeneration.
3. Auth gating is one shared gate (F10), invoked with the pending
   action preserved and replayed post-auth. No screen may implement its
   own separate gate.
4. Map (F9) never computes its own candidate ranking. It only ever
   renders a set already produced by Decision Session, Search, or
   Craves.
5. Correcting recommendation influence (F7.2/F13.1) never deletes the
   underlying factual record. Deleting user data (F13.2) always
   propagates to derived evidence, and that propagation is itself
   logged, not assumed. These are two different operations, never one
   blunt "reset."
6. Dietary/allergy hard constraints are never silently relaxed by any
   relaxation logic (F3.3's search relaxation, Decision Session's
   fallback behavior, or anything else). Relaxation only ever applies
   to soft constraints.
7. Private logging (F6.4) never requires media and never silently
   becomes a public post.
8. Restaurant/dish identification in the `+` composer (F6.2/F6.3)
   always has a manual-correction escape path. Low confidence never
   blocks the flow.
9. Offline/stale states (F11) always show last-known data with an
   honest timestamp. Never a blank screen; never a silently-faked-live
   view.
10. Location permission denial (F12) always degrades to manual area
    selection. Never a broken feature.
11. Every entry into Place Detail carries its originating surface
    (Decision Session / Discovery / Search / Craves / organic) so the
    Decision Strip's framing is honest about why the user is there —
    never fabricated after the fact.
12. Visit-detection for Rank/Craves-graduation (F5.1) accepts any one
    corroborating signal. It never requires all signals, and it never
    graduates a place with none.

---

## 6. Downstream Contract Dependencies

Items this document establishes the *boundary* for, formalized in the
next artifacts:

**Data & State Map** (next artifact — see §7):
- The seven shared data-contract domains from §1.3, as concrete
  schemas/APIs.
- The unified auth-gate contract (F10) — one implementation, referenced
  by every flow that needs it.
- The analytics/event-taxonomy contract implied by every "analytics/
  evidence emitted" cell above — including the `surface` value
  expansion already flagged in the Target Screen Registry's Migration
  Risks section (new values likely needed: `rank_home`, `craves`,
  distinguished from `decision_session`; `map_direct` flagged in F9.3
  as a residual case worth tracking separately).
- The offline/staleness-label contract (F11) as one shared component/
  pattern, not per-screen reinvention.
- The anonymous-session-to-account evidence migration contract (F1.4).

**Privacy/Permission Matrix** (later artifact):
- Exactly which fields F13.1 vs. F13.2 apply to, per data type (Rank,
  Craves, posts, Taste Profile corrections, account deletion).
- The location-permission fallback (F12) formalized per surface.
- Auth requirement per action, tabulated explicitly (this document
  states auth requirements per transition; the Permission Matrix is
  where that becomes the authoritative, exhaustive reference).

**Screen contracts** (once Data & State Map + Component/Design System
exist):
- Exact composer step ordering for `+` (F6) and the onboarding split
  (§1.2) — both explicitly deferred here as screen-contract-level
  decisions, not resolved in this document.
- Rank Home (net-new, per Target Screen Registry §3.4) and the Native
  Posting composer (net-new, §5.4) are the two highest-priority
  contracts once their data dependencies (visit evidence contract,
  dish contract) are formalized.

---

## 7. Next artifact

Per the agreed sequence, the next canonical artifact is the **Data &
State Map** — locking exactly what state and evidence these flows are
allowed to move around (the seven contract domains from §1.3, made
concrete) before individual screens are frozen. Not the design system
yet.
