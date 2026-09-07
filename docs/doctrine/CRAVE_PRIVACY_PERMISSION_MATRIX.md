# CRAVE Privacy / Permission Matrix

**Status:** Canonical scope artifact (2026-09-07)
**Purpose:** Built from the canonical chain — Doctrine →
`CRAVE_CANON_RECONCILIATION_MAP.md` → `CRAVE_V1_SCOPE.md` →
`CRAVE_TARGET_SCREEN_REGISTRY.md` → `CRAVE_ROUTE_FLOW_MAP.md` →
`CRAVE_DATA_STATE_MAP.md` → this document. For every meaningful data
class or permission-sensitive action, answers: what CRAVE collects or
infers, why it needs it, who can see/use it, and what control the user
has over it. Not an app-store policy checklist — a product-doctrine
artifact those checklists get satisfied *by*, not the other way around.

**Authority hierarchy:** same as prior artifacts, this document last —
existing doctrine → reconciliation map → annotated supersessions → V1
Scope → Target Screen Registry → Route & Flow Map → Data & State Map →
this document.

---

## 1. Three concepts Codex must never collapse

Every row below keeps these three separate. A single field answering
"is this private" is not enough — a row can be private in visibility,
active in recommendation influence, and permanent in factual retention,
all at once, and those three answers are frequently different from
each other.

- **Visibility** — who can *see* something (another user, a business, a
  screen). Governed by the `Default visibility` field.
- **Recommendation influence** — whether something can *affect
  personalization/ranking*. Governed by the `Recommendation influence`
  field. Independent of visibility — Rank data is private (invisible to
  others) yet has maximal recommendation influence; a caption is
  potentially visible yet has zero recommendation influence.
- **Factual retention** — whether the underlying event/history *still
  exists* at all, regardless of what it's allowed to show or influence.
  Governed by `Retention/lifecycle` and `Deletion behavior`. Correcting
  recommendation influence never touches retention; only an explicit
  deletion action does.

---

## 2. Locked privacy invariants

1. Rank, Craves, Taste Profile, and never-posted visit history are
   private by default.
2. Profile existence/discoverability may be public by default; sensitive
   contents are separately permissioned and stay private regardless.
3. No background or precise-location collection by default — foreground
   location only, ever.
4. Location inference alone cannot silently create a verified visit or
   unlock Rank eligibility.
5. Private "made me crave this" reactions remain anonymous to the
   poster — neither count nor reactor identity is ever shown.
6. Businesses never receive user-specific taste intelligence.
7. Commercial/affiliated evidence never contaminates recommendation
   influence.
8. Deletion/correction must propagate through derived intelligence.
9. A recommendation reset is not a data deletion.
10. Reset inferred taste preserves factual food history.
11. Blocking revokes access to previously visible content.

Every row in §3 is a specific instance of one or more of these.

---

## 3. Data / permission matrix

Each entry: Source · Factual/Inferred/Derived · Sensitivity · Default
visibility · Recommendation influence · Retention/lifecycle · Deletion
behavior · Correction behavior · User control · OS/app permission ·
Downstream processors · Screens/flows · Failure/degraded behavior ·
Codex rule.

### A. Location & visit evidence

**A1. Precise/current location (foreground)**
Source: device GPS, foreground only · F/I/D: factual · Sensitivity:
high · Default visibility: private, never shared with users or
businesses · Recommendation influence: yes — proximity/context in
Feed, Search, Map, Craves · Retention: session-scoped, not persisted
as a location trail · Deletion: nothing beyond the session to delete ·
Correction: n/a · User control: OS permission toggle; manual "Choose an
area" if denied · OS/app permission: location, when-in-use only ·
Downstream processors: recommendation request contract (Data & State
Map §2) · Screens/flows: Feed, Search, Map, Craves, F12 · Failure/
degraded: manual area selection, never a broken feature · **Codex
rule:** never request background/always-allow location; foreground-only,
no exceptions.

**A2. Background location — prohibition**
Source/F-I-D/Sensitivity/Visibility/Influence/Retention/Deletion/
Correction/User control: n/a — this row exists only to prohibit, not
describe a collected class · OS/app permission: never requested ·
Downstream processors: none, ever · Screens/flows: none · Failure/
degraded: n/a · **Codex rule:** background location must never be
requested or collected for any purpose, including visit inference —
the multi-signal visit-evidence model (A3/A4) is the sanctioned
substitute (locked invariant #3).

**A3. Location-derived visit inference**
Source: foreground location matched against a place's coordinates ·
F/I/D: inferred · Sensitivity: high (location + behavior) · Default
visibility: private · Recommendation influence: **none until
confirmed** — surfaces a confirmation prompt only · Retention: the raw
inference isn't persisted unless confirmed · Deletion: n/a
(unconfirmed = nothing persisted) · Correction: declining/ignoring the
prompt discards it · User control: confirm, decline, or ignore ·
OS/app permission: location (foreground) · Downstream processors: visit
evidence contract (Data & State Map §4) · Screens/flows: Route & Flow
Map F5.1 · Failure/degraded: if location is denied, other signals (Rank
action, manual "I went," tagged post) remain fully sufficient — **Codex
rule:** an inferred-only signal may never silently create a
`declared`/`verified` visit record or grant Rank-comparison-eligibility
(locked invariant #4, the exact fix already made to F5.1).

**A4. Declared/verified/inferred visits (the record itself)**
Source: Rank action (verified), manual "I went" (declared), tagged post
(verified), confirmed inference (declared) · F/I/D: factual record,
tier-classified · Sensitivity: moderate-high (reveals where/when) ·
Default visibility: private by default (locked invariant #1) ·
Recommendation influence: tier-gated — declared/verified unlocks Rank
eligibility; any tier suffices for Craves graduation · Retention:
persists indefinitely once created, independent of ranking status ·
Deletion: user-deletable; cascades to derived Rank/Craves state ·
Correction: tier correctable ("I didn't actually go") — removes
influence without necessarily deleting the record · User control: full
— confirm, correct, delete · OS/app permission: none beyond the
underlying signal · Downstream processors: Rank Home, Craves, Place
Detail relationship state · Screens/flows: F5.1-F5.4 · Failure/
degraded: n/a · **Codex rule:** never let an `inferred` record behave
like `declared`/`verified` anywhere downstream.

**A5. Exact vs. approximate visit timing**
Source: A4's timestamp · F/I/D: factual (raw) / derived (display
precision) · Sensitivity: moderate — an exact public timestamp
approaches location-history disclosure · Default visibility: never
public unless posted, and even then approximate recency only, never an
exact date · Recommendation influence: exact timestamp used internally
for recency modeling; only approximate recency ever surfaces publicly ·
Retention/Deletion: same as A4 · Correction: n/a beyond A4 · User
control: post-visibility choice (E3) gates whether any timing shows at
all · OS/app permission: none · Downstream processors: Rank recency
modeling, Native Posting · Screens/flows: Place Detail, Profile, posts ·
Failure/degraded: n/a · **Codex rule:** never display an exact public
timestamp by default — approximate recency, and only when posted.

### B. Constraints

**B1. Dietary/allergy constraints**
Source: user-declared (onboarding calibration or Taste Profile/
Settings) · F/I/D: factual, declared not inferred · Sensitivity: very
high — safety-relevant · Default visibility: private; never exposed to
businesses individually · Recommendation influence: hard constraint —
never relaxed, never soft-weighted · Retention: persists until user
edits it · Deletion: user removes/edits any time · Correction: direct
edit, immediate effect · User control: full · OS/app permission: none ·
Downstream processors: constraint contract (Data & State Map §3),
Search, recommendation request contract, future Shared Craves group
constraints · Screens/flows: onboarding, Taste Profile, Search,
Decision Session · Failure/degraded: if CRAVE can't verify a dietary
claim for a place, it says so explicitly rather than guessing · **Codex
rule:** never silently relax, weight, or override a dietary/allergy
hard constraint under any relaxation logic, anywhere.

**B2. Religious/ethical food restrictions**
Same shape and rules as B1 in every field — sensitivity, hard-constraint
status, and the never-relax rule are identical. Listed as its own row
only because the underlying doctrine treats it as a categorically
distinct declared constraint, not a variant of dietary restriction, for
onboarding-copy and correction-vocabulary purposes. **Codex rule:**
identical to B1 — never relaxed, never soft-weighted, ever.

### C. Core personal intelligence

**C1. Rank data**
Source: Rank Comparison outcomes · F/I/D: factual event → derived
tier/position · Sensitivity: high — the system's highest-integrity
taste signal · Default visibility: private by default (locked invariant
#1) · Recommendation influence: yes, the strongest tier in the evidence
hierarchy · Retention: persists indefinitely as factual history; decays
only in "recent form" weighting, never in the record itself · Deletion:
user can delete a rank entry; cascades per propagation rules ·
Correction: Taste Profile's four-action vocabulary applies to
influence, not the historical record · User control: private by
default; opt-in exposure of coarse tier-level highlights only — exact
position exposure stays governed by the still-**OPEN** visible-social-
Rank question · OS/app permission: none · Downstream processors: Rank
Home, Taste Profile, Other User Profile compatibility display,
recommendation request contract · Screens/flows: Rank Home, Rank
Comparison, Profile, Taste Profile · Failure/degraded: n/a · **Codex
rule:** no UI may expose another user's exact position or full ordered
list without an approved decision closing the OPEN question first.

**C2. Craves**
Source: Save action, the resurfaced/scoped recommendation engine ·
F/I/D: factual save event → derived resurfaced subset · Sensitivity:
moderate-high — reveals unfulfilled interest, arguably more personal
than completed evidence · Default visibility: private by default ·
Recommendation influence: weak-positive evidence · Retention: persists,
decays in weight if untouched, never force-expired · Deletion: user
removes any time · Correction: n/a beyond removal (present/absent, not
graded) · User control: full · OS/app permission: none · Downstream
processors: Craves resurfacing engine, Rank queue (graduation), Map's
Craves layer · Screens/flows: Craves, Feed's Craves rail, Map ·
Failure/degraded: honest "nothing fits right now" if the saved pool
yields nothing · **Codex rule:** never shown publicly by default; never
dumped as a raw list on Map — bounded/prioritized subset only.

**C3. Taste Profile inferences**
Source: derived from Rank/Save/Search/reaction/visit evidence · F/I/D:
inferred/derived · Sensitivity: high — CRAVE's model of the user's food
personality · Default visibility: private, self-facing only — never a
public-facing artifact · Recommendation influence: yes, directly powers
the recommendation request contract · Retention: rebuildable from
retained factual events; resettable without deleting them · Deletion:
"reset inferred taste" discards the derived model only (locked
invariant #10) · Correction: four-action vocabulary (Not true /
Doesn't matter to me / Less of this / More of this); explicit
corrections outrank passive inference · User control: full — inspect,
correct, pause, reset-recommendations, reset-inferred-taste (see C4) ·
OS/app permission: none · Downstream processors: recommendation request
contract · Screens/flows: Taste Profile, Profile · Failure/degraded:
uncertain traits show "still learning this," never a premature claim ·
**Codex rule:** only confident inferences are shown; every shown
inference must be correctable.

**C4. Pause / reset-recommendations / reset-inferred-taste**
Source: explicit Taste Profile action · F/I/D: n/a (an action) ·
Sensitivity: n/a · Default visibility: n/a · Recommendation influence:
**pause** = temporarily stops using taste signal without discarding it;
**reset recommendations** = clears only current Feed/Discovery session
state; **reset inferred taste** = discards the derived model, factual
history untouched · Retention: none of the three deletes factual
history (locked invariants #9, #10) — only account deletion (K2) does
that · Deletion behavior: none of these three *is* a deletion · User
control: is the control · OS/app permission: none · Downstream
processors: recommendation request contract, Feed/Discovery session
state, taste graph · Screens/flows: Taste Profile · Failure/degraded:
n/a · **Codex rule:** these three must never be collapsed into one
"reset" button; none may delete Rank/visit/post history.

### D. Search & anonymous sessions

**D1. Search history**
Source: submitted queries, semantic-intent history · F/I/D: factual
query → weak inferred signal, and only once followed by an action on a
result (search intent alone is never taste evidence) · Sensitivity:
moderate · Default visibility: private, self-facing (recent searches
shown only to the searcher) · Recommendation influence: weak, only
post-action · Retention: recent semantic searches retained for the
zero-state UI, ages out over time · Deletion: user can clear history ·
Correction: n/a · User control: clear all or per-query · OS/app
permission: none · Downstream processors: recommendation request
contract (post-action only), Search's zero-state UI · Screens/flows:
Search · Failure/degraded: n/a · **Codex rule:** a search query alone
must never be logged as positive taste evidence.

**D2. Anonymous-session evidence**
Source: pre-account browsing (F1.1/F1.2) · F/I/D: factual, weak ·
Sensitivity: low-moderate, not yet tied to a real identity · Default
visibility: private, tied to the anonymous session id · Recommendation
influence: weak, powers only that session's own view · Retention:
eligible for migration (D3) on account creation, otherwise ages out ·
Deletion: expires naturally if no account is created; no user-facing
delete action needed pre-account · Correction: n/a · User control:
creating an account is the implicit "claim" action · OS/app permission:
none beyond underlying signals · Downstream processors: recommendation
request contract (anonymous-scoped) · Screens/flows: F1.1, F1.2 ·
Failure/degraded: n/a · **Codex rule:** anonymous evidence must never
be presented as belonging to an account until D3's explicit migration.

**D3. Account migration of anonymous evidence**
Source: F1.4, account creation following anonymous browsing · F/I/D:
factual migration event · Sensitivity: moderate · Default visibility:
private · Recommendation influence: migrated evidence keeps its
original weak weighting, never upgraded retroactively · Retention: the
migration event itself is logged for provenance — origin as "anonymous,
later migrated" stays visible, never rewritten · Deletion: user can
delete migrated evidence same as any other, post-migration ·
Correction: standard rules apply post-migration · User control:
implicit consent via account creation · OS/app permission: none ·
Downstream processors: taste evidence contract · Screens/flows: F1.4 ·
Failure/degraded: partial migration failure must not block account use
· **Codex rule:** migration provenance must remain visible/auditable —
never silently rewritten as native authenticated evidence.

### E. Content & posting

**E1. Native posts**
Source: Native Posting composer (F6) · F/I/D: factual · Sensitivity:
moderate, user-chosen visibility · Default visibility: explicit choice
at publish (private/friends/public), remembered default always shown
and overridable, never silently applied · Recommendation influence:
yes — structured evidence (restaurant→dish→media→reaction) · Retention:
persists until deleted · Deletion: retracts derived evidence, logged as
an auditable retraction · Correction: restaurant/dish attachment
editable post-publish; edits recompute derived signals · User control:
full — edit, delete, change visibility · OS/app permission: camera,
photo library · Downstream processors: social evidence contract, taste
evidence contract · Screens/flows: F6, Feed social rail, Place Detail ·
Failure/degraded: failed publish keeps the draft, never discards ·
**Codex rule:** media required for public/friends visibility;
identification always has a manual-correction path.

**E2. Private logs**
Source: same composer, private-visibility path · F/I/D: factual ·
Sensitivity: low-moderate, never leaves the user's own record · Default
visibility: private, always — the entire point of this row ·
Recommendation influence: yes, same as any logged visit/reaction ·
Retention: persists until deleted · Deletion: user-initiated, standard
propagation · Correction: reaction/attachment editable · User control:
full · OS/app permission: none required — no media required for private
logs · Downstream processors: taste/visit evidence contracts ·
Screens/flows: F6.4 · Failure/degraded: n/a · **Codex rule:** private
logs never require media and never silently convert to a public post.

**E3. Post visibility tiers (private/friends/public)**
Source: explicit choice at F6.4 · F/I/D: n/a, a setting · Sensitivity:
n/a · Default visibility: remembered default, always shown and
overridable at time of posting · Recommendation influence: n/a —
visibility gates who sees the post, not evidence weight · Retention:
tied to the post's lifecycle (E1) · Deletion: n/a beyond E1 ·
Correction: visibility changeable after publish · User control: full,
per-post · OS/app permission: none · Downstream processors: n/a, a
display-gating field · Screens/flows: F6.4, Feed, Place Detail ·
Failure/degraded: n/a · **Codex rule:** visibility is never silently
defaulted without showing the user what it's set to.

**E4. Media / photos / video**
Source: camera or photo library · F/I/D: factual · Sensitivity:
moderate-high — photos can reveal more context than intended · Default
visibility: tied to the post's visibility tier (E3) · Recommendation
influence: powers evidence-driven dish/restaurant presentation ·
Retention: tied to the post's lifecycle · Deletion: deleting the post
deletes the media; independently reportable/removable via moderation ·
Correction: replaceable pre-publish only · User control: full pre-
publish; deletion required to remove post-publish · OS/app permission:
camera, photo library · Downstream processors: dish/place evidence
contracts, alt-text generation · Screens/flows: F6, Place Detail hero,
Discovery · Failure/degraded: permission denied → see Permission
Failure Matrix §4 · **Codex rule:** never autoplay video, never a
muted-autoplay exception — tap-to-play only, always.

**E5. Captions**
Source: optional free text at F6 · F/I/D: factual text, explicitly not
taste evidence · Sensitivity: low-moderate · Default visibility: tied
to post visibility (E3) · Recommendation influence: **none** — never
Rank order, carries less weight than structured reactions · Retention:
tied to post lifecycle · Deletion: tied to post deletion · Correction:
editable like other attachments · User control: full, always optional ·
OS/app permission: none · Downstream processors: none direct — captions
never feed the taste model as structured evidence · Screens/flows: F6 ·
Failure/degraded: n/a · **Codex rule:** never treat free-text captions
as equivalent to a structured reaction signal.

**E6. Private reactions ("Made me crave this")**
Source: another user reacting to a post · F/I/D: factual event ·
Sensitivity: moderate — reactor identity is sensitive · Default
visibility: **private to the poster as a signal only; reactor identity
never shown, and no public count anywhere** (locked invariant #5) ·
Recommendation influence: yes, quietly feeds both the poster's and
reactor's own taste signal · Retention: persists until the reaction or
underlying post is removed · Deletion: retracting a reaction removes
its evidence weight · Correction: n/a beyond retraction · User control:
reactor can retract; poster cannot see who reacted or a count ·
OS/app permission: none · Downstream processors: taste evidence
contract, social evidence contract · Screens/flows: Native posts,
Activity (private notice only) · Failure/degraded: n/a · **Codex
rule:** never expose reactor identity to the poster; never render a
public aggregate count anywhere.

### F. Social graph

**F1. Followed-user evidence**
Source: the Follow graph · F/I/D: factual relationship → derived
similarity weighting · Sensitivity: moderate · Default visibility: the
relationship is visible per profile discoverability (F3); the derived
weighting is never shown as a literal "whose opinion matters more"
statement · Recommendation influence: yes — Feed social-rail weighting,
Other User Profile's taste-compatibility display (approved use,
distinct from the still-**OPEN** follow-suggestion mechanic) ·
Retention: persists while the relationship exists · Deletion:
unfollowing removes it from future weighting, not retroactive (events
are immutable) · Correction: a separate "don't use this person's taste
to influence mine" control exists, distinct from muting · User control:
follow/unfollow, mute (visibility axis), "don't use their taste"
(influence axis) — two distinct controls · OS/app permission: none ·
Downstream processors: recommendation request contract, Feed social
rail · Screens/flows: Feed, Other User Profile, Follow graph management
· Failure/degraded: n/a · **Codex rule:** muting and "don't use this
person's taste" must remain two separate controls, never collapsed.

**F2. Contacts for discovery**
Source: device contacts, opt-in only · F/I/D: factual matching, not
stored contact content beyond match purpose · Sensitivity: high —
third-party PII · Default visibility: never shared; used only to show
the user their own potential matches · Recommendation influence: none
— a discovery/growth mechanism, not a taste signal · Retention: no raw
contact data persisted beyond what's needed to show matches · Deletion:
revoking the permission stops future matching immediately · Correction:
n/a · User control: full opt-in/opt-out via OS permission · OS/app
permission: contacts · Downstream processors: follow-suggestion
matching only · Screens/flows: discovery/invite flows · Failure/
degraded: denied → username/invite-link/QR discovery remain fully
available · **Codex rule:** contacts data is never used beyond showing
the user their own matches; never uploaded to analytics or any
commercial pipeline.

**F3. Profile discoverability**
Source: account existence · F/I/D: n/a, a setting · Sensitivity: low —
existence only, not contents · Default visibility: **public by default**
(locked invariant #2) — a separate axis from Rank/Craves/Taste
Profile/history privacy, which stay private regardless · Recommendation
influence: n/a · Retention: tied to account lifecycle · Deletion: user
can disable discoverability without deleting the account · Correction:
n/a · User control: full toggle · OS/app permission: none · Downstream
processors: Follow graph, Search/username lookup, invite/QR flows ·
Screens/flows: Profile, Settings · Failure/degraded: n/a · **Codex
rule:** "public by default" applies to discoverability only — never
read as authorization to default-expose Rank/Craves/Taste
Profile/history contents.

**F4. Blocked users**
Source: explicit user action · F/I/D: n/a, a control state ·
Sensitivity: moderate · Default visibility: n/a · Recommendation
influence: a blocked user's content/evidence is excluded from the
blocker's surfaces · Retention: block state persists until reversed ·
Deletion: unblocking restores default visibility going forward, not
retroactive · Correction: n/a · User control: full — block/unblock ·
OS/app permission: none · Downstream processors: Feed, Search, Place
Detail, Follow graph, Activity · Screens/flows: any social surface ·
Failure/degraded: n/a · **Codex rule:** blocking must revoke access to
*previously visible* content, not just prevent new visibility (locked
invariant #11).

### G. External/commercial content

**G1. Restaurant/business access**
Source: a claimed, verified business account · F/I/D: n/a, an access
grant · Sensitivity: high — from the standpoint of what it must never
see · Default visibility: n/a · Recommendation influence: **never** —
the access grant itself confers no recommendation influence · Retention:
tied to the claim/verification lifecycle · Deletion: revocable ·
Correction: n/a · User control: n/a (business access, not an
individual user's) · OS/app permission: n/a · Downstream processors:
place operational-data contract (G2) only, never the taste evidence
contract · Screens/flows: Place Detail factual-edit surface (later) ·
Failure/degraded: n/a · **Codex rule:** businesses never receive
user-specific taste intelligence (locked invariant #6) — a claimed
business may edit factual fields only and see aggregate, anonymized
insights at most.

**G2. Restaurant-submitted factual data**
Source: a claimed business editing hours/menu/address/etc. · F/I/D:
factual, business-asserted · Sensitivity: low-moderate · Default
visibility: public — factual place information, same as catalog data ·
Recommendation influence: feeds place operational-data contract only
(freshness/completeness), never fit/confidence · Retention: persists,
versioned/tracked by source · Deletion: business can edit/retract their
own submissions · Correction: users can report incorrect info · User
control: users can report, cannot edit directly · OS/app permission:
n/a · Downstream processors: place operational-data contract (Data &
State Map §6) · Screens/flows: Place Detail · Failure/degraded: user-
reported disputes trigger the existing freshness/provenance honesty
pattern · **Codex rule:** restaurant-submitted content must be visually/
structurally distinguished from user evidence, always.

**G3. Imported "Seen on social"**
Source: user-shared external links, resolved against the catalog ·
F/I/D: factual import event, confidence-gated resolution · Sensitivity:
moderate · Default visibility: **OPEN — display placement unassigned**
(Route & Flow Map §1.1/§5.1a); this row governs data handling only ·
Recommendation influence: feeds the social evidence contract's
`imported_external` bucket, kept structurally distinct from native
posts · Retention: original URL always preserved · Deletion: user can
remove an import · Correction: manual correction always available ·
User control: full — import, correct, delete · OS/app permission: none
beyond share-sheet integration · Downstream processors: social evidence
contract (`imported_external`) · Screens/flows: Craves, Place Detail
(placement OPEN) · Failure/degraded: low confidence surfaces ambiguity,
never silently attaches the wrong place · **Codex rule:** never assign
this content a permanent Place Detail surface until the OPEN placement
question is explicitly resolved.

**G4. Commercial/affiliated content**
Source: sponsored, comped, or employee-affiliated posts · F/I/D:
factual content, mandatory disclosure/classification · Sensitivity:
high — a trust-integrity issue, not just privacy · Default visibility:
must be labeled/disclosed, never presented as organic · Recommendation
influence: **excluded entirely** — never counted as organic evidence ·
Retention: persists per normal content rules, tagged permanently as
`commercial_affiliated` · Deletion: same as any content · Correction:
`source_type` immutable once set, never silently reclassified · User
control: n/a for viewers (a disclosure requirement, not a personal
privacy control) · OS/app permission: n/a · Downstream processors:
social evidence contract, explicitly excluded from taste evidence
contract · Screens/flows: any content surface · Failure/degraded: n/a ·
**Codex rule:** commercial/affiliated evidence never contaminates
recommendation influence (locked invariant #7) — no exceptions.

### H. Dish & commerce

**H1. Dish evidence**
Source: saves/reactions/posts/menu ingestion scoped to a dish id ·
F/I/D: factual events → derived dish-level affinity · Sensitivity:
low-moderate · Default visibility: private by default, same as
restaurant-level evidence · Recommendation influence: yes — Discovery's
dish-first presentation, Place Detail's "For You," Search's dish
results · Retention: persists independently of restaurant-level
evidence · Deletion: deleting the source event retracts the dish
evidence it contributed · Correction: same propagation rules as any
taste evidence · User control: full, via the underlying actions ·
OS/app permission: none · Downstream processors: dish contract (Data &
State Map §8) · Screens/flows: Discovery, Search, Place Detail ·
Failure/degraded: weak evidence → plain menu, never a fabricated "For
You" claim · **Codex rule:** dish evidence never implies dish Rank
exists — no UI may present dish-level comparison as available in V1.

**H2. Reservation/order evidence**
Source: a completed reservation/order via deep-link providers · F/I/D:
factual · Sensitivity: moderate · Default visibility: private ·
Recommendation influence: counts as strong corroborating visit-evidence
(`verified` tier) — but the commercial relationship itself never
influences recommendation order · Retention: persists as visit-evidence
provenance · Deletion: standard propagation rules · Correction: n/a
beyond standard visit-evidence correction · User control: full ·
OS/app permission: none beyond the external provider's own · Downstream
processors: visit evidence contract · Screens/flows: Place Detail CTA,
F5.1 · Failure/degraded: deep-link failure → show address/phone
directly · **Codex rule:** a reservation/ordering partner relationship
must never influence recommendation order — permanent, confirmed.

### I. Notifications & discoverability

**I1. Push notifications**
Source: category-gated events (Rank reminders, follow requests,
reservation events, saved-place reopening) · F/I/D: n/a, a delivery
mechanism · Sensitivity: low, but volume/framing carries engagement-bait
risk · Default visibility: n/a · Recommendation influence: n/a ·
Retention: n/a · Deletion: n/a · Correction: n/a · User control:
per-category toggle, full control · OS/app permission: notifications ·
Downstream processors: Activity inbox (always available regardless of
push permission) · Screens/flows: Settings, Activity · Failure/
degraded: denied → Activity inbox remains fully functional as a
pull-based alternative · **Codex rule:** "come back to the app"
engagement notifications with no concrete food value are permanently
prohibited — no exceptions for growth experiments.

**I2. Hidden restaurants (from public food identity)**
Source: explicit user action on Profile/Place Detail · F/I/D: n/a, a
visibility control · Sensitivity: moderate · Default visibility: hiding
exists so a visit doesn't have to color one's public identity ·
Recommendation influence: **none** — a display control, not a
taste-evidence exclusion; the underlying evidence still informs
recommendations unless separately corrected via Taste Profile ·
Retention: the hide preference persists until reversed · Deletion: n/a ·
Correction: reversible any time · User control: full · OS/app
permission: none · Downstream processors: Profile's public food-
identity display · Screens/flows: Profile · Failure/degraded: n/a ·
**Codex rule:** hiding a restaurant from public identity must never be
conflated with excluding it from recommendation influence — independent
controls, per §1's three-concept separation.

### J. System/telemetry

**J1. Analytics/telemetry**
Source: recommendation events (impressions, clicks, positions), app
usage events · F/I/D: factual · Sensitivity: low-moderate in aggregate,
higher if not properly session-scoped/anonymized · Default visibility:
internal only, never raw user-facing data (aggregated insights may
surface to businesses per G1's strict limits) · Recommendation
influence: this *is* input to recommendation improvement, but never
optimized toward engagement metrics · Retention: position/provenance
retained per event for position-bias auditing; standard retention
practice otherwise (downstream engineering detail) · Deletion: tied to
account deletion/export rights (K1/K2) · Correction: n/a · User control:
covered by account-level export/deletion rights · OS/app permission:
none beyond what underlying features already require · Downstream
processors: recommendation request contract, experimentation framework
· Screens/flows: all · Failure/degraded: n/a · **Codex rule:** no
experiment or dashboard may treat engagement (time-in-app, scroll
depth) as a primary success metric; a confidently-reached "no" must be
recorded as success, never abandonment.

**J2. Crash reporting**
Source: Sentry, already integrated (`send_default_pii=False`) · F/I/D:
factual technical diagnostic data · Sensitivity: moderate — must not
carry PII · Default visibility: internal only · Recommendation
influence: none · Retention: per Sentry's own retention policy
(external processor) · Deletion: not directly controllable by the end
user; tied to the org's data-handling practices · Correction: n/a ·
User control: none granular; governed by the overall privacy policy ·
OS/app permission: none beyond standard app operation · Downstream
processors: Sentry (external, documented in
`SENTRY_PRODUCTION_VERIFICATION.md`) · Screens/flows: all crash paths ·
Failure/degraded: n/a · **Codex rule:** `send_default_pii=False`
substantially reduces but does not guarantee PII exclusion — live-event
inspection remains the authoritative proof, never the config flag
alone.

### K. Lifecycle operations

**K1. Deleted-content propagation**
Source: any deletion action (post, save, rank entry, account) · F/I/D:
n/a, an operation · Recommendation influence: must retract to zero for
the deleted item · Retention: the deletion itself is logged as an
auditable retraction event · Deletion behavior: **is** the row ·
Correction behavior: n/a — deletion and correction are the two distinct
operations this entire matrix keeps separate (§1) · User control: full
— user-initiated by definition · OS/app permission: none · Downstream
processors: every contract in the Data & State Map · Screens/flows: all
deletion entry points · Failure/degraded: partial propagation failure
must surface as in-progress, never presented as complete when it isn't
· **Codex rule:** deletion/correction must propagate through derived
intelligence (locked invariant #8) — this row is that rule's
implementation surface.

**K2. Account deletion / export**
Source: Settings · F/I/D: n/a, an operation · Recommendation
influence: full account deletion removes all derived influence ·
Retention: subject to applicable legal/retention lifecycle (exact
policy is a legal/downstream detail, not decided here) · Deletion
behavior: two-step confirmation (already shipped, `settings.tsx`), full
data removal/anonymization per policy · Correction behavior: n/a · User
control: full — export and delete both basic, always-available rights
· OS/app permission: none · Downstream processors: every contract ·
Screens/flows: Settings · Failure/degraded: n/a · **Codex rule:** export
and full deletion must both remain easy to reach — never buried behind
multiple menu layers.

---

## 4. Permission Failure & Degraded-Mode Matrix

Every denied permission needs a usable fallback. Permission denial must
never become a dead end.

| Permission | Denied/unavailable behavior |
|---|---|
| **Location** | Manual "Choose an area" substitutes for device location across Feed/Search/Map/Craves (F12). Visit-evidence still works via Rank action, manual "I went," or tagged posts — location was never the only path. |
| **Contacts** | Username search, invite link, and QR discovery remain fully available (F2). No feature is contacts-gated to the point of being unusable without it. |
| **Camera** | Photo-library selection remains available for Native Posting (E4). If library access is also denied, the composer still supports a private text-only log (E2) with no media at all. |
| **Microphone** | Video capture proceeds without audio (silent video), or the composer falls back to photo capture — video is never a hard requirement for posting. |
| **Notifications** | The Activity inbox (I1) remains fully functional as a pull-based alternative; nothing push-only exists — every notification category has an in-app equivalent. |
| **Permanently blocked OS permission** (denied twice / "don't ask again") | The manual fallback for that permission (above) becomes the *permanent* path for that user, not a one-time retry loop — the app must not repeatedly prompt or nag for a permission the OS has permanently blocked; a single, calm, one-time path to the OS settings screen is the only re-prompt allowed. |
| **Unavailable/stale provenance** (data source down, freshness expired) | Show last-known data with an honest timestamp (Route & Flow Map F11); facts that are genuinely unsafe when stale (hours, availability) get an explicit caveat beyond the general staleness label — never silently served as current. |

---

## 5. Codex Privacy Invariants

Implementation may not widen **visibility**, **collection**,
**retention**, **recommendation influence**, or **permissions** beyond
what this matrix states, for any row, without an approved canonical
change traceable the same way every other supersession in this project
has been:

1. No row's default visibility may be changed from private to public
   (or vice versa) without an explicit, dated, traceable update to this
   document — never as a side effect of an unrelated feature.
2. No new OS/app permission may be requested beyond what a row already
   names, and no existing permission's scope may be silently widened
   (e.g. foreground location silently becoming background).
3. No data class may be given recommendation influence it doesn't
   already have here (captions, commercial content, contacts) without
   the same traceable process.
4. No retention period may be silently extended, and no deletion
   behavior may be silently weakened (e.g. a "delete" that stops
   short of retracting derived influence).
5. Every "Codex rule" in §3 is binding at the same level as the
   Route & Flow Map's Flow Invariants and the Data & State Map's Data
   Invariants — none of them are suggestions.
6. When a screen contract needs a data class not yet in this matrix,
   the correct response is to add a row here first, not to improvise
   behavior and document it after the fact.

---

## 6. Next artifact

Per the agreed sequence, the next canonical artifact is the
**Evidence / Signal Hierarchy**. This document settled what data is
allowed to exist and move; the Evidence Hierarchy locks how strongly
each allowed signal may influence CRAVE — before screen contracts are
frozen.
