# CRAVE Target Screen Registry

**Status:** Canonical scope artifact (2026-09-07)
**Purpose:** Line-by-line reconciliation of the live route tree
(`frontend/app/`, 20 route files + 2 layout files, verified against the
current repo, not the earlier screen-inventory audit alone) against the
V1 architecture approved in `CRAVE_V1_SCOPE.md`. This is not a design
exercise — every current route is accounted for, classified, and given
a Codex readiness state. Net-new routes required by V1 Scope that have
no current file are also registered, so the next artifact (Route & Flow
Map) has a complete surface to work from rather than rediscovering the
app.

**Authority hierarchy:** same as `CRAVE_V1_SCOPE.md` §0 — existing
doctrine → reconciliation map → annotated supersessions → V1 Scope →
this registry.

---

## 1. How to read this document

Each entry has:

- **Current path** — exact file under `frontend/app/`, or "none
  (net-new)."
- **Current purpose** — what the shipped screen actually does today,
  grounded in its own code/comments, not an assumption.
- **Target screen / purpose** — what it becomes under the approved V1
  architecture.
- **Target navigation placement** — tab, contextual-entry, stack push,
  or "not a screen" (chrome/config).
- **Status** — `KEEP` / `REBUILD` / `CREATE` / `REMOVE` / `MERGE` /
  `AUDIT REQUIRED` / `LATER`.
- **V1 requirement level** — the exact row this maps to in
  `CRAVE_V1_SCOPE.md`.
- **Major dependencies** — other rows in this registry or V1 Scope that
  must land first.
- **Governing canon** — same citation convention as V1 Scope.
- **Codex readiness state** — one of:
  - `READY TO SPEC` — a screen contract can be authored once the Route
    & Flow Map exists.
  - `BLOCKED ON DEPENDENCY` — needs another V1-required capability
    (data model, other screen) specified first.
  - `BLOCKED ON OPEN DECISION` — needs an OPEN/AUDIT REQUIRED item
    resolved first.
  - `NOT YET` — correctly excluded from V1; no contract needed now.
  - `NO ACTION` — unaffected by this reconciliation (legal/chrome).

**Route existence is tracked separately from tab status.** A route can
survive (KEEP) while losing its tab-bar registration — Map is the
clearest case, not the only one worth watching for later.

---

## 2. Tab / navigation chrome

### 2.1 `(tabs)/_layout.tsx`
**Current purpose:** Registers five tabs today: Feed (`index`), Map
(`map`), Search (`search`), Craves (`craves`), Profile (`profile`,
titled "You"). Settings already lives behind Profile's gear icon, not
its own tab — that part already matches target.
**Target:** Registers **Feed / Search / Craves / Rank / Profile** —
Map's `<Tabs.Screen name="map">` entry is removed (Map becomes
contextual-entry only); a new `<Tabs.Screen name="rank">` is added; the
`profile` tab's title changes from "You" to "Profile."
**Status:** REBUILD
**V1 requirement:** V1 Scope §1 (App Structure, implicit navigation
row) — five-tab architecture.
**Dependencies:** 3.4 (Rank Home, CREATE) must exist before this file
can register it; 2.2 (Map) must be relocated out of `(tabs)/` first.
**Governing canon:** Reconciliation entry #1.
**Codex readiness:** BLOCKED ON DEPENDENCY (needs 3.4 and 2.2 to land
first — this is a registration change, not independent work).

### 2.2 `(tabs)/map.tsx` + `(tabs)/map.web.tsx`
**Current purpose:** Full native map (react-native-maps), clustering,
bottom-sheet-on-tap, fetches both catalog GeoJSON and **saved-places
GeoJSON** (`fetchSavedPlacesGeoJSON`) — a Craves-on-map layer already
exists in some form today. `map.web.tsx` is a genuine placeholder
screen (native map libraries don't bundle for web), not a degraded map.
**Target:** Contextual Map (V1 Scope §3.8) — same screen content
mostly reused, relocated out of the tab bar, entered from Decision
Session ("Map these picks"), Search ("view on map"), and Craves ("view
on map") instead of a persistent tab.
**Target navigation placement:** Stack push (e.g. `map.tsx` at the app
root, same pattern as `place/[id].tsx`), not `(tabs)/map.tsx`.
**Status:** REBUILD (relocation + bounded-pin-cap/entry-point changes;
existing clustering/sheet mechanics and the saved-places layer are
largely reusable, not a rewrite)
**V1 requirement:** V1 Scope §3.8 — V1 REQUIRED as a contextual
feature, explicitly not a tab.
**Dependencies:** Decision Session's and Search's own result sets (Map
must render exactly what they already produced, never its own
independent ranking — already close to true today since it fetches a
GeoJSON feed rather than computing its own ranking, but this needs
explicit verification once the Route & Flow Map traces the actual data
flow).
**Governing canon:** Reconciliation entry #1; V1 Scope §3.8.
**Codex readiness:** BLOCKED ON DEPENDENCY (file relocation depends on
2.1's tab-registration change happening in the same migration).

### 2.3 Root `_layout.tsx`
**Current purpose:** Registers the stack: `(tabs)`, `record-video/
[placeId]`, `place/[id]`, `rank/[placeId]`, `user/[id]`,
`profile-setup`, `add-spot`, `friends-feed`, `leaderboard`,
`taste-profile/[userId]`, `settings`, `legal/privacy`, `legal/terms`.
**Target:** Same stack, plus new entries for whatever net-new routes
§4/§5 below resolve to (Rank Home lives in `(tabs)`, not here; a
Native Posting composer and Activity Inbox need stack entries added
here once their exact paths are decided in the Route & Flow Map).
**Status:** REBUILD (additive — new `Stack.Screen` entries only, no
existing entry removed except if `map.tsx` needs a top-level
`Stack.Screen` registration added here once it moves out of `(tabs)/`).
**V1 requirement:** Follows from whichever rows below are CREATE.
**Dependencies:** 3.4, 5.2, 5.4 (all CREATE rows below).
**Governing canon:** N/A — pure routing chrome.
**Codex readiness:** BLOCKED ON DEPENDENCY.

---

## 3. Feed / Search / Craves / Rank (the four content tabs)

### 3.1 `(tabs)/index.tsx` — Feed
**Current purpose:** Tiered structural feed (Crave Pick/Gem/Solid/New),
`FlashList`-backed, real skeleton/error/empty states. A Decision
Session block already exists at the top per the shipped
`useDecisionSession` hook and backend (`decision_session_spec.md`,
live since 2026-08-27) — but per the existing screen audit, it
currently **competes with the main feed rather than integrating into
it**. No persistent context chip. No embedded social rail (that content
lives entirely in the separate `friends-feed.tsx`, see §5.3).
**Target:** Feed / Decision Session (V1 Scope §3.1) leading, tapering
into Discovery's structured rails then bounded mixed stream (§3.2),
with a small personalized social rail sourced from what `friends-feed`
does today, and a persistent correctable context chip.
**Target navigation placement:** Tab (`index`) — unchanged.
**Status:** REBUILD
**V1 requirement:** V1 Scope §3.1 (V1 REQUIRED) + §3.2 (V1 REQUIRED).
**Major dependencies:** Dish Intelligence data model (V1 Scope §4.4)
for Discovery's dish-first presentation; §5.3 (`friends-feed.tsx`)
content migration for the social rail; Craves (§3.2 below) for the
"From your Craves" rail.
**Governing canon:** Decision Architecture §9/§11/§14; V1 Scope §3.1,
§3.2.
**Codex readiness:** BLOCKED ON DEPENDENCY (Dish Intelligence data
model must exist first; the social-rail migration from `friends-feed`
needs the Route & Flow Map to define the new data contract).

### 3.2 `(tabs)/craves.tsx` — Craves
**Current purpose:** Three-source stitched list — native saves,
social-matched craves (imported links), manually-added entries — as a
single scrollable list. Two visibly different row styles for the
stitched sources. No confirmation dialog on remove.
**Target:** Active-intelligence engine scoped to saved interest (V1
Scope §3.4) — opening the screen shows a small reasoned "try these now"
subset first, full list as a secondary view; auto-adapting Want-to-Try/
Tried state from visit evidence; automatic clustering (cuisine/
occasion/geography) rather than the current flat stitched list.
**Target navigation placement:** Tab (`craves`) — unchanged.
**Status:** REBUILD
**V1 requirement:** V1 Scope §3.4 (V1 REQUIRED); §3.4a Manual Craves
lists is explicitly LATER — DEFER, so the current "manually-added"
source stays as a data type but gets no new list-management UI in V1.
**Major dependencies:** Visit-detection signals (Rank action, manual
"I went," tagged post) for auto-graduation; the same recommendation
engine Decision Session uses, reapplied to a scoped pool.
**Governing canon:** Bible §19; V1 Scope §3.4.
**Codex readiness:** BLOCKED ON DEPENDENCY (needs the shared
recommendation-engine contract the Route & Flow Map will define, so
Craves isn't built as a second, divergent implementation of the same
logic Decision Session already has).

### 3.3 `(tabs)/search.tsx` — Search
**Current purpose:** Deepest state machine in the app (5+ states by
query length/filters/location), but no semantic-intent parsing, no
editable interpreted-constraint chips, no exact-name bypass to Place
Detail, no Craves/Rank-scoped query understanding.
**Target:** One box, literal + semantic intent (V1 Scope §3.3) — small
reasoned default set with bounded "Show more," visible/editable
constraint chips, exact-name confidence bypass, `from my Craves`/`my
highest-ranked X` query scoping.
**Target navigation placement:** Tab (`search`) — unchanged.
**Status:** REBUILD
**V1 requirement:** V1 Scope §3.3 (V1 REQUIRED); §3.3a Voice Search is
LATER — DEFER, no work now beyond not hard-coding text-only assumptions
into the interpretation engine.
**Major dependencies:** Constraint-interpretation engine (shared with
Map's "search this area" and the future route-aware constraint type,
§4.2 below); Craves (3.2) and Rank Home (3.4) data access for scoped
queries.
**Governing canon:** Decision Architecture §3.5; V1 Scope §3.3.
**Codex readiness:** BLOCKED ON DEPENDENCY (the interpretation engine
is genuinely new backend work, not a frontend-only change — needs its
own contract before a screen contract is meaningful).

### 3.4 `(tabs)/rank.tsx` — Rank Home
**Current path:** none (net-new). Today, "your ranked list" is a
section inside `(tabs)/profile.tsx`, not its own screen.
**Current purpose:** N/A.
**Target:** Rank Home (V1 Scope §3.5) — leads with recent visits
waiting to be ranked, tiers as default view, numbers/cuisine-context
views behind drill-down.
**Target navigation placement:** New tab (`rank`).
**Status:** CREATE
**V1 requirement:** V1 Scope §3.5 (V1 REQUIRED).
**Major dependencies:** `(tabs)/profile.tsx` REBUILD (§3.6 below) to
remove the content migrating here; visit-confirmation signal (shared
with Craves' graduation logic, §3.2).
**Governing canon:** Reconciliation entry #1 ("Rank is a first-class
destination, not a You/Profile sub-panel" — Bible §26 annotated
accordingly); V1 Scope §3.5.
**Codex readiness:** READY TO SPEC once the Route & Flow Map defines
where the migrated ranked-list content and its existing components
(`RankedPlaceRow`, tier logic already used by Leaderboard/Profile) get
reused from.

### 3.5 `rank/[placeId].tsx` — Rank Comparison
**Current purpose:** Already the most distinctive screen in the app —
tier→comparing→done, backend-driven signed comparison tokens,
Tinder-style duel with real haptics/motion. Recently hardened (retry
now actually retries, per the release-defect pass).
**Target:** Same mechanic, preserved exactly, with two additions: an
honest "too close to call / both great" outcome and a "haven't been to
one of these" outcome — both real ranking states, not UI dead-ends.
**Target navigation placement:** Stack push from Place Detail and from
the new Rank Home (3.4) — unchanged in kind, gains a second entry
point.
**Status:** KEEP (core mechanic) — additive changes only, not a
rewrite.
**V1 requirement:** V1 Scope §3.6 (V1 REQUIRED); §3.6a Dish Rank is
LATER — DEFER, no dish-level comparison added here.
**Major dependencies:** None blocking — the two new outcomes are
additive to the existing signed-token flow.
**Governing canon:** Existing implementation itself; V1 Scope §3.6.
**Codex readiness:** READY TO SPEC — this is the closest thing in the
registry to a self-contained, low-risk contract; does not need to wait
on the Route & Flow Map's broader navigation work.

### 3.6 `(tabs)/profile.tsx` — Profile
**Current purpose:** "Who you are, your ranked list, and the two
social surfaces (friends feed, leaderboard) hanging off it" (its own
header comment). Tab title "You," route file already named `profile` —
the file/route naming already matches target, only the content and
title need to change. Settings already reached via a gear icon here,
already matching target placement.
**Target:** Profile (V1 Scope §4.1) — leads with curated taste
identity (from Taste Profile, §5.2), then Rank *status* (not the full
ranked list, which moves to 3.4) / food history / posts as supporting
sections. No numerical vanity counters.
**Target navigation placement:** Tab (`profile`), title changes from
"You" to "Profile."
**Status:** REBUILD
**V1 requirement:** V1 Scope §4.1 (V1 REQUIRED).
**Major dependencies:** Rank Home (3.4) must exist so the ranked-list
content has somewhere to migrate to; Taste Profile (§5.2) for the
leading identity section.
**Governing canon:** Bible §26 (content largely valid, navigation
superseded per reconciliation entry #1); V1 Scope §4.1.
**Codex readiness:** BLOCKED ON DEPENDENCY (must land after or
alongside 3.4 — removing ranked-list content before its destination
exists would be a regression, not a migration).

### 3.7 `settings.tsx`
**Current purpose:** Notification 4-state model, two-step account-
deletion confirmation, City/App/About/Support/Account sections. Already
reached from Profile's gear icon.
**Target:** Unchanged placement — this already matches V1 Scope §4.1
("Settings lives inside this tab"). No navigation change needed.
**Status:** KEEP
**V1 requirement:** Implicit in V1 Scope §4.1.
**Major dependencies:** None.
**Governing canon:** N/A — no reconciliation gap here.
**Codex readiness:** NO ACTION (already correctly placed; any content
fixes here are a separate, unrelated workstream from this
reconciliation).

---

## 4. Map's dependent/adjacent items (already covered under §2.2, cross-referenced here for completeness)

### 4.1 Route-aware discovery ("on my way home")
**Current path:** none.
**Status:** LATER — ARCHITECT NOW (V1 Scope §3.8a) — no screen, but the
Map/Search constraint schema (§2.2, §3.3) must include a route/corridor
constraint type now.
**Codex readiness:** NOT YET (schema note only, folded into 2.2/3.3's
dependency list, not its own contract).

### 4.2 Personal food-history map layer
**Current path:** none.
**Status:** LATER — DEFER (V1 Scope §3.8b).
**Codex readiness:** NOT YET.

---

## 5. Place Detail, dish intelligence, and content/social

### 5.1 `place/[id].tsx` — Place Detail
**Current purpose:** Already implemented against `CRAVE_PLACE_DETAIL_SPEC.md`
and re-scored 75/100 ("credible MVP") — hero → identity → decision
strip (no fabricated open/closed status, real gap tracked) → "why this
fits" (catalog percentile + friend-ranking count + own past ranking,
deliberately not fake personalization) → primary rank CTA → actions row
→ menu → progressive disclosure. "Seen on social" (imported links) is
an already-flagged open placement question (§8 item 10 of that spec).
**Target:** Same information architecture, extended with relationship-
aware states (never-visited/considering/visited/regular change what
leads the page), evidence-gated "For You" dish content, and an adaptive
single primary CTA (Reserve > Directions > Save-for-tonight > Save).
**Status:** REBUILD (additive/extend — the shipped Spec is the current
baseline, not a proposal to replace)
**V1 requirement:** V1 Scope §3.7 (V1 REQUIRED).
**Major dependencies:** Dish Intelligence data model (§5.2 below) for
evidence-gated dish content; a real user taste graph before
personalized (non-catalog-fact) "Why This Fits" copy can honestly ship
— until then, this section stays exactly as scoped today.
**Governing canon:** `CRAVE_PLACE_DETAIL_SPEC.md`; reconciliation
entries #4 (hours) and #5 ("Seen on social," stays unresolved — see
5.1a).
**Codex readiness:** BLOCKED ON DEPENDENCY (relationship-aware states
need the visit/graduation signal shared with Craves and Rank Home to
be specified first).

### 5.1a "Seen on social" placement
**Current path:** N/A (a section within `place/[id].tsx`, unassigned).
**Status:** OPEN — DO NOT IMPLEMENT a permanent placement.
**V1 requirement:** V1 Scope §3.7a.
**Codex readiness:** BLOCKED ON OPEN DECISION.

### 5.2 Dish Intelligence (data model)
**Current path:** none — no dish-level entity exists independent of
menu text on a restaurant today.
**Target:** Dish modeled as a first-class entity with its own evidence
trail (V1 Scope §4.4).
**Status:** CREATE (data model, not a screen)
**V1 requirement:** V1 Scope §4.4 (LATER — ARCHITECT NOW for
screens/Rank; the data model itself is a dependency every V1-required
screen above needs).
**Major dependencies:** Blocks 3.1 (Discovery's dish-first rails), 3.3
(Search's dish results), 5.1 (Place Detail's For You section).
**Governing canon:** Decision Architecture §2.4, §10; Bible §10.
**Codex readiness:** BLOCKED ON DEPENDENCY (this needs its own backend
contract before any of the screens that depend on it can be specified
— it should likely be the *first* thing specified after this registry,
not something discovered mid-screen-contract).

### 5.3 `friends-feed.tsx`
**Current purpose:** Deliberately separate, small, chronological "your
friend just ranked X" feed — explicitly not padded with algorithmic
recommendations (per its own header comment). Currently reached only
from Profile.
**Target:** Its useful job survives, but not as a standalone
first-class destination — a dedicated friends feed risks recreating a
social-network consumption surface CRAVE explicitly does not want.
Native social evidence belongs contextually in Feed's embedded social
rail and in Place Detail; social activity/notifications belong in
Activity (§7.2). The route itself is kept only for migration/deep-link
compatibility until those two surfaces exist, then removed.
**Target navigation placement:** No longer reached from Profile once
migrated; not a permanent destination anywhere.
**Status:** **RESOLVED (2026-09-07) — MERGE / REMOVE AFTER MIGRATION.**
Content and job migrate into Feed's social rail (F2/F7 area) and
Activity; the route is temporary migration/deep-link scaffolding only,
per `CRAVE_ROUTE_FLOW_MAP.md` §1's resolution of this judgment call —
not left open.
**V1 requirement:** Folds into V1 Scope §3.1's social-section
requirement.
**Major dependencies:** Feed (3.1) REBUILD; Activity Inbox (7.2).
**Governing canon:** Interview Feed/Discovery sections (social
subordinate to discovery, personalized not chronological-only at the
Feed-embedded level); `CRAVE_ROUTE_FLOW_MAP.md` §1.
**Codex readiness:** BLOCKED ON DEPENDENCY (depends on 3.1's rebuild
and 7.2's Activity Inbox both landing before this route can actually be
removed — do not remove it prematurely and leave the migration
half-finished).

### 5.4 Native Posting composer
**Current path:** none. `record-video/[placeId].tsx` (§5.5) and
`add-spot.tsx` (§5.6) are partial precursors, not equivalents — neither
has the structured restaurant→dish→media→reaction unit, a private/
public visibility choice, or a quick-take reaction step.
**Target:** Structured native posting (V1 Scope §5.2) — Media First →
intelligent restaurant identification (confidence-gated, degrades to
manual search) → optional dish identification → quick-take reaction
(Loved it/Good/Not for me) → explicit private/friends/public choice.
Reuses `record-video`'s camera capture and permission-handling code
(audit-confirmed "best-in-class") as the media-capture step rather than
rebuilding it.
**Status:** CREATE (composer/flow) with a MERGE relationship to
`record-video/[placeId].tsx`'s existing capture code.
**V1 requirement:** V1 Scope §5.1 (private logging) + §5.2 (native
posting), both V1 REQUIRED.
**Major dependencies:** Dish Intelligence (5.2/§4.4) for dish
attachment; `add-spot.tsx`'s search flow as the "can't find the
restaurant" fallback; the reaction quick-take mechanic (shared with
Rank's post-visit nudge, 3.5).
**Governing canon:** Interview Posting section; reconciliation §2
(edits/deletion must recompute derived evidence).
**Codex readiness:** BLOCKED ON DEPENDENCY (Dish Intelligence data
model is a hard prerequisite; this is likely the single highest-value
target for the next screen-contract round once that lands).

### 5.5 `record-video/[placeId].tsx`
**Current purpose:** Full-bleed camera, floating chrome, circle-to-
square record/stop, tied to a specific already-known place, reached
only from `PlaceVideoGallery` inside Place Detail. Best-in-class
permission handling; one known gap (unstyled blank flash pre-permission)
already logged elsewhere, unrelated to this reconciliation.
**Target:** Its capture/permission code becomes the media-capture step
inside the new Native Posting composer (5.4) rather than a
place-scoped-only side flow.
**Status:** MERGE into 5.4
**V1 requirement:** Folds into V1 Scope §5.2.
**Major dependencies:** 5.4.
**Governing canon:** Interview Posting section (§9, media-required/
photo-led/single-media rules) — video capture becomes one input into
that structured unit, not its own product surface.
**Codex readiness:** BLOCKED ON DEPENDENCY (waits on 5.4's contract).

### 5.6 `add-spot.tsx`
**Current purpose:** GPS-based "find and add a new spot" — fresh
high-accuracy location fix, 150m search radius, submit-a-new-candidate
flow. Reached only from Settings today.
**Target:** Unchanged core purpose — this already matches the "can a
user submit a missing restaurant" requirement (V1 Scope §5.2's
dependency list). Gains a second entry point: the Native Posting
composer's (5.4) "can't find this restaurant" fallback, in addition to
its existing Settings entry point.
**Status:** KEEP (core screen) — REBUILD-lite for the new entry point
only.
**V1 requirement:** Dependency of V1 Scope §5.2.
**Major dependencies:** 5.4.
**Governing canon:** Interview Posting section, Q9 identification-
fallback answer.
**Codex readiness:** BLOCKED ON DEPENDENCY (the new entry point can't
be specified until 5.4 exists; the Settings entry point needs no
change).

---

## 6. Identity surfaces

### 6.1 `profile-setup.tsx`
**Current purpose:** One-time username claim only — debounced live
availability check, five validation states. Gates the profile tab.
Does not currently collect dietary/allergy constraints, a novelty
starting position, or the 3-5 known-restaurant reactions the cold-start
approach requires.
**Target:** **RESOLVED (2026-09-07) — REBUILD / SPLIT BY FUNCTION**, per
`CRAVE_ROUTE_FLOW_MAP.md` §1: this is not one future onboarding page.
Distinct responsibilities, not automatically bundled:
- Pre-account value experience (browsing Feed/Discovery/Search
  anonymously) needs no screen here at all — it's just Feed itself
  (F1.1/F1.2 in the Flow Map), gated later, not part of this file.
- Dietary/allergy hard constraints, a novelty-dial starting position,
  and lightweight reactions to 3-5 self-identified known restaurants
  are cold-start calibration — genuinely part of this flow, reusing
  Rank Comparison's lightweight-reaction UI pattern rather than
  reinventing one.
- True identity setup (username claim — the screen's *current* entire
  job) is account-completion, not cold-start calibration, and must not
  be bloated by adding the calibration items into the same screen
  indiscriminately — it may become an earlier or later step in the same
  stack flow, but is tracked as a functionally distinct responsibility.
**Status:** REBUILD / SPLIT BY FUNCTION
**V1 requirement:** Dependency of V1 Scope's cold-start requirements
(referenced under §3.1/§3.4/§3.5's dependency lists; cold-start itself
doesn't have its own V1 Scope row — it's an onboarding capability those
rows depend on).
**Major dependencies:** Rank Comparison's lightweight-reaction UI
pattern (3.5) — reused here, not reinvented for onboarding.
**Governing canon:** Bible §18 (as annotated — price/travel-willingness
items superseded, rest of the calibration list unaffected);
`CRAVE_ROUTE_FLOW_MAP.md` §1.
**Codex readiness:** BLOCKED ON DEPENDENCY (the exact step ordering
within the split is a screen-contract-level decision, made once the
Data & State Map defines what the calibration step actually needs to
persist).

### 6.2 `user/[id].tsx` — Other User Profile
**Current purpose:** Someone else's ranked list plus a follow button.
Correctly guards against account-switch races; distinguishes 404 from
transient error from blocked.
**Target:** Adds taste-compatibility-with-you display (V1 Scope §4.2,
already-approved use of the similarity signal, distinct from the
still-open follow-suggestion mechanic).
**Status:** REBUILD (additive)
**V1 requirement:** V1 Scope §4.2 (V1 REQUIRED).
**Major dependencies:** The taste-similarity computation (shared with
Taste Profile, 6.3, and with the still-open §4.6 — the computation
itself is approved regardless of §4.6's status).
**Governing canon:** V1 Scope §4.2.
**Codex readiness:** BLOCKED ON DEPENDENCY (similarity computation
needs its own contract; do not build it as a one-off for this screen
only, since Taste Profile needs the same signal).

### 6.3 `taste-profile/[userId].tsx` — Taste Profile
**Current purpose:** Already well-aligned — percentile reframed as
"Top X%," explicit tier vocabulary, viewable on own and a friend's
profile, correctly guards identity races. Deliberately excludes a
match-score (that's folded into the personalized-recommendations
feature per its own header comment — i.e. §4.2/§4.6).
**Target:** Same screen, gains the four-action correction vocabulary
(Not true / Doesn't matter to me / Less of this / More of this),
confidence-gating (only show inferences CRAVE is actually confident
about), and the three distinct actions (pause personalization / reset
current recommendations / reset inferred taste without deleting food
history).
**Status:** REBUILD (additive — closer to KEEP than most rows in this
registry; the foundation is already correct)
**V1 requirement:** V1 Scope §4.3 (V1 REQUIRED).
**Major dependencies:** User taste graph (Decision Architecture Gate
2) — the correction UI has nothing to correct without it.
**Governing canon:** Decision Architecture §6, §23; V1 Scope §4.3.
**Codex readiness:** BLOCKED ON DEPENDENCY (taste graph is the hard
prerequisite; this screen's own UI work is otherwise close to READY TO
SPEC).

---

## 7. Social graph & activity

### 7.1 Follow graph (data layer, powers 5.3, 6.2, `leaderboard.tsx`)
**Current path:** none as a distinct registry item — implemented today
as whatever backs the existing follow button on `user/[id].tsx` and
friends-scoped queries elsewhere.
**Status:** KEEP (single relationship type, per V1 Scope §5.3 — do not
add a second "Friend" primitive).
**Codex readiness:** NO ACTION beyond what 6.2/5.3/7.3 already require.

### 7.2 Activity Inbox
**Current path:** none. Today, push notifications deep-link straight
to `place/[id]` (see root `_layout.tsx`'s notification-response
handler) with no in-app inbox/history surface at all.
**Target:** In-app, pull-based inbox (V1 Scope §5.4) — private social
reactions, follow requests, reachable via a header icon, not a tab.
**Status:** CREATE
**V1 requirement:** V1 Scope §5.4 (V1 REQUIRED).
**Major dependencies:** Notification category definitions (7.4).
**Governing canon:** V1 Scope §5.4.
**Codex readiness:** READY TO SPEC once notification categories (7.4)
are defined — does not block on Dish Intelligence or the taste graph,
so this can move in parallel with the Feed/Craves/Search rebuild track.

### 7.3 `leaderboard.tsx`
**Current purpose:** Solid state handling (skeleton, real error-retry,
scope-aware empty copy), recently fixed to gate the friends-scope
behind sign-in. Reached from Profile today. Content is "places logged"
breadth ranking, not preference ordering.
**Target:** Undetermined pending audit.
**Status:** AUDIT REQUIRED
**V1 requirement:** V1 Scope §5.6 — explicitly neither approved nor
rejected.
**Major dependencies:** The audit itself (verify it performs a distinct
breadth/activity job without duplicating Rank Home's preference-
ordering leaderboard, 3.4).
**Governing canon:** V1 Scope §5.6; reconciliation map §4.
**Codex readiness:** BLOCKED ON OPEN DECISION — do not redesign,
expand, or relocate this screen's entry point until the audit assigns
it a real status.

### 7.4 Notifications (category definitions)
**Current path:** none as a distinct screen — categories aren't
currently split in Settings' notification toggle (single on/off state
machine per the existing 4-state model, which covers permission status,
not per-category routing).
**Status:** CREATE (a settings sub-section, not a new route)
**V1 requirement:** V1 Scope §5.5 (V1 REQUIRED).
**Major dependencies:** Activity Inbox (7.2).
**Governing canon:** V1 Scope §5.5.
**Codex readiness:** READY TO SPEC alongside 7.2.

### 7.5 Social Rank (visible comparative ranking)
**Status:** OPEN — DO NOT IMPLEMENT. No route, no toggle, no hidden
flag.
**V1 requirement:** V1 Scope §4.5.
**Codex readiness:** BLOCKED ON OPEN DECISION.

### 7.6 Taste-similarity people recommendations (follow-suggestion feed)
**Status:** OPEN — DO NOT IMPLEMENT. The underlying signal is approved
for use in 3.1's social rail and 6.2's compatibility display (see V1
Scope §4.6) — only a "people you may like" UI/feed is blocked.
**Codex readiness:** BLOCKED ON OPEN DECISION (for the suggestion
feed only — the signal computation itself is READY TO SPEC as part of
6.2/6.3's dependency work).

### 7.7 Imported "Seen on social"
Cross-referenced from §5.1a — tracked once, not duplicated as a second
open item.

---

## 8. Legal & chrome (no reconciliation gap)

### 8.1 `legal/privacy.tsx`, `legal/terms.tsx`
**Current purpose:** In-app source of truth for privacy/terms content,
bespoke and accurate. Unrelated to this reconciliation.
**Status:** KEEP
**Codex readiness:** NO ACTION.

### 8.2 `+not-found.tsx`
**Current purpose:** Deliberate branded catch-all for unmatched routes/
deep links.
**Status:** KEEP
**Codex readiness:** NO ACTION.

---

## 9. Target V1 Route Topology

```
(tabs)/                      <- Tab bar: Feed / Search / Craves / Rank / Profile
  index.tsx                  Feed (Decision Session + Discovery + social rail)
  search.tsx                 Search
  craves.tsx                 Craves
  rank.tsx                   Rank Home                          [CREATE]
  profile.tsx                Profile (title: "Profile", was "You")

  "+"                        Not a tab. Tab-bar action -> opens
                             Native Posting composer (capture-first
                             action sheet: Take Photo / Choose Photo /
                             Choose Video)

Stack (pushed, not tabbed):
  place/[id].tsx              Place Detail
  rank/[placeId].tsx           Rank Comparison (from Place Detail or Rank Home)
  map.tsx                      Contextual Map (relocated out of (tabs)/) [REBUILD+move]
  user/[id].tsx                 Other User Profile
  taste-profile/[userId].tsx     Taste Profile
  settings.tsx                    Settings (from Profile's gear)
  profile-setup.tsx                 Onboarding (username + cold-start calibration)
  add-spot.tsx                       Submit a missing restaurant
  friends-feed.tsx                     "See all" from Feed's social rail  [MERGE, entry point moves]
  leaderboard.tsx                        Unresolved pending audit          [AUDIT REQUIRED]
  <native posting composer>                New composer                    [CREATE]
  <activity inbox>                           New inbox, header icon entry   [CREATE]
  legal/privacy.tsx, legal/terms.tsx           Unchanged
  +not-found.tsx                                 Unchanged

Deprecated as a distinct capture surface (merged, not removed outright):
  record-video/[placeId].tsx   -> capture/permission code reused inside
                                  the new Native Posting composer
```

---

## 10. Migration Risks / Blockers

- **Deep links to `/map` as a tab route.** Any existing deep link,
  push-notification payload, or test that assumes `map` is a tab
  (rather than a stack push) breaks the moment §2.2/§2.1 land. Audit
  `usePushNotifications`/notification payload shapes and any
  `frontend/__tests__` fixtures that navigate to the Map tab by name
  before removing its `Tabs.Screen` registration.
- **State ownership split between Profile and Rank Home.** Whatever
  local/query-cache state `(tabs)/profile.tsx` currently owns for the
  ranked list must move to `(tabs)/rank.tsx` atomically — a partial
  migration (UI moved, cache key not) would silently duplicate fetches
  or show stale data on one of the two screens.
- **Existing tests reference current screen boundaries.** `rank-place.
  test.tsx`, `leaderboard.test.tsx`, `craves.test.tsx`, `feed.test.tsx`,
  and any `profile.test.tsx` equivalent all encode assumptions about
  which screen owns which content today (e.g. a test asserting
  Profile renders the ranked list will fail correctly once 3.6/3.4
  land — that's expected breakage to update, not a regression to avoid
  by delaying the migration).
- **Analytics/recommendation-event `surface` values.** The Ledger
  (`recommendation_events.surface`) already has fixed values including
  `decision_session`, `search`, presumably `feed`/`map`/`craves`. Moving
  Map out of the tab bar and splitting Rank out of Profile likely needs
  new/renamed `surface` values — decide this explicitly in the Route &
  Flow Map rather than letting inconsistent surface tagging accumulate
  across the migration.
- **Auth gating duplication.** Multiple screens (`leaderboard.tsx`,
  friends-scoped queries, `AuthSheet` usage elsewhere) each implement
  their own sign-in gate. Splitting Rank out of Profile and relocating
  `friends-feed`'s content into Feed multiplies the places this pattern
  needs to be replicated correctly — worth consolidating into one
  shared gate check as part of this migration, not after.
- **Offline/cache behavior for relocated content.** Craves and Rank
  data must remain offline-viewable per V1 Scope §7.3 regardless of
  which screen currently renders them — confirm the query-cache keys
  that provide this today survive the Profile → Rank Home content move
  unchanged.
- **Backend contract for the Native Posting composer is entirely new.**
  Unlike the navigation-only changes above, §5.4 has no existing
  endpoint to reuse beyond `record-video`'s upload path and `add-spot`'s
  candidate-submission path — this is real backend work, not a
  frontend reshuffle, and should not be scheduled as if it were the
  same size as the tab-bar changes.
- **`(tabs)/map.web.tsx`'s placeholder status.** Confirm whether the
  web-placeholder story is still acceptable once Map is contextual-
  entry rather than a persistent tab — a placeholder reached rarely
  (contextual entry) versus one reached every session (a tab) is a
  different UX cost, worth an explicit decision rather than inheriting
  the old assumption.

---

## 11. Next artifact

Per the agreed sequence, the next canonical artifact is the **Route &
Flow Map** — using this registry rather than rediscovering the app
again. It should resolve the items this registry deliberately left as
judgment calls (5.3's exact fate, 6.1's exact step-split) and define
the shared data contracts (recommendation engine reused by Feed/Craves,
constraint schema shared by Search/Map, visit-detection signal shared
by Rank/Craves/Place Detail) that multiple BLOCKED ON DEPENDENCY rows
above are waiting on.
