# CRAVE Component Registry

**Status:** Canonical scope artifact (2026-09-07)
**Purpose:** What becomes shared versus screen-specific, verified
against the actual current inventory in `frontend/src/components/`
(22 files today — six more than the earlier screen audit's 13-item
snapshot), so Codex has one registry to check before creating a fifth
version of a primitive that already exists, or — the subtler failure
mode this registry exists equally to prevent — reusing one primitive
across two concepts the doctrine has deliberately kept visually
distinct.

**Authority hierarchy:** existing doctrine → reconciliation map →
annotated supersessions → V1 Scope → Target Screen Registry → Route &
Flow Map → Data & State Map → Privacy/Permission Matrix → Evidence/
Signal Hierarchy → Design System → this document.

---

## 1. The registry principle — and its sharper failure mode

"Shared" means: used by more than one screen today, or explicitly
required to be used by more than one screen contract once written.
"Screen-specific" means: correctly scoped to one flow, and should
*stay* that way rather than being generalized pre-emptively (Bible §3
principle 11: "the system earns complexity").

The failure mode this registry spends the most effort on is not
duplication — it's **incorrect reuse**. `TierBadge.tsx` and
`RankedPlaceRow.tsx` render visually similar things (a colored tier
label next to a place) and could easily be collapsed into one generic
"tier badge" component by someone optimizing for DRY code. They must
never be collapsed: `TierBadge` renders the **catalog percentile
tier** (a fact about the place), `RankedPlaceRow` renders **Rank's
personal tier** (a fact about this user's taste) — the Design System
(§6) already locked that these two systems must never share visual
language, specifically because merging their components would make
that rule impossible to keep in practice. Confirmed in code today:
they already use two entirely separate tier utilities
(`utils/scoring.ts`'s `Tier`/`getTierForPlace` vs. `utils/rankScore.ts`'s
`RankTier`/`tierColor`) and never import each other — correct, and this
registry's job is to keep it that way, not "clean it up."

---

## 2. Existing components

### A. Place / recommendation cards

**`PlaceCard.tsx`** — Status: **KEEP, SHARED.** Full recommendation
card; already imports `DecisionRole` from `../api/decisionSession` and
renders it — confirming `decision_session_spec.md`'s plan ("add an
optional `role` prop... reuse the component, don't fork a new one") is
already implemented. There is no separate "Decision Session card"
component and there should never be one — a Decision Session card *is*
`PlaceCard` with `role` set. Used by: Feed, Discovery, Search results,
Craves. Codex rule: any screen needing a full place card uses this
component; a role/reasoning need is a new prop here, never a new card.

**`PlaceCardCompact.tsx`** — Status: **KEEP, SHARED.** Row-form variant
with per-save memory props (Craves-specific optional fields, undefined
elsewhere). Used by: Craves, any dense list context. Codex rule: the
one compact-card primitive — a "slightly different" compact card for a
new screen is a prop addition here, not a new file.

**`TrendingStrip.tsx`** — Status: **DORMANT, DECISION DEFERRED TO
DISCOVERY REBUILD.** Currently feature-flagged off
(`SHOW_FEED_DISCOVERY_STRIPS = false`, per Bible §22.1 — "confident-
looking personalization UI on top of not-confident-enough data does
more harm than good"). Not revived, not deleted — its fate is decided
by Discovery's rebuild (V1 Scope §3.2, Target Screen Registry §3.1),
not by this registry. Codex rule: do not re-enable or delete this
component outside that rebuild's own screen contract.

**`MapMarker.tsx`** (`MapMarkerDot`/`MapClusterDot`) — Status: **KEEP,
SCREEN-SPECIFIC (Map).** Already used by `(tabs)/map.tsx`. Codex rule:
Map's bounded pin-count rule (Design System, Route & Flow Map F9) is
enforced by what data reaches this component, not by the component
itself — it renders what it's given.

### B. Tier & score presentation

**`TierBadge.tsx`** — Status: **KEEP, SHARED — SCOPE-RESTRICTED.**
Renders the catalog percentile tier only (CRAVE Pick / Hidden Gem /
Worth Knowing / Explore). Generic in code (parameterized by a `Tier`
with `.color`/`.label`), which is exactly why it must not be handed a
Rank personal-tier object — genericness at the code level is not
license to blur two conceptually distinct systems. Codex rule: never
pass a Rank/personal-tier value into this component; see §1.

**`RankedPlaceRow.tsx`** — Status: **KEEP, SHARED.** Renders Rank's
personal tier (its own `RankTier`/`tierColor`, deliberately not
`TierBadge`). "The position number is the point of the whole feature"
(the component's own header comment) — this is the primitive that
migrates into the new Rank Home tab (Target Screen Registry §3.4/§3.6),
not a component to rebuild for that screen. **Known duplication to
fix, not perpetuate:** the earlier screen audit found Leaderboard
hand-rolling its own row instead of reusing this component — exactly
the failure mode this registry exists to prevent. Leaderboard's
eventual fate is still AUDIT REQUIRED (V1 Scope §5.6), but *if* it
survives, it must reuse `RankedPlaceRow`, not its current hand-rolled
row.

### C. Empty / error / loading states

**`EmptyState.tsx`**, **`ErrorState.tsx`**, **`SkeletonCard.tsx`** —
Status: **KEEP, SHARED, UNIVERSAL.** Every screen contract's state
section (Design System §8) must specify its empty/error/loading
content using these three, never a hand-rolled equivalent. Codex rule:
a new screen "needing something slightly different" is a props
addition to one of these three, not a fourth state-component family.

### D. Rank Comparison — deliberately screen-specific

**`ComparisonChoice.tsx`** — Status: **KEEP, SCREEN-SPECIFIC (Rank
Comparison).** One side of the head-to-head duel; deliberately
tap-to-choose, not swipe (the component's own header comment already
states the reasoning the Design System's global swipe-to-decide
prohibition later formalized product-wide). Correctly not generalized
— there is no other two-way visual duel in the product today. Codex
rule: do not generalize this into a "generic comparison" component
ahead of a second real use.

**`ShareRankCard.tsx`** — Status: **KEEP, SCREEN-SPECIFIC (Rank
Comparison's "done" stage).** The external-share artifact — consistent
with the locked rule that external sharing is fine, internally
gamifying it is not (no share-count, no leaderboard-of-shares). Codex
rule: do not add any in-app metric derived from how often this is used.

### E. Sheets & modals

**`AuthSheet.tsx`** — Status: **KEEP, SHARED — INVOCATION NEEDS
CONSOLIDATING.** The sheet itself is correctly shared already. What
is *not* yet consolidated is *when and how* it's triggered — the
Target Screen Registry's Migration Risks section already flagged that
multiple screens each implement their own sign-in gate check today.
This registry states the target plainly: **one shared gate invocation**
implementing Route & Flow Map F10 (pending action preserved, replayed
post-auth), called from every stateful-action entry point, not five
slightly different call sites. Codex rule: a new stateful action gates
through the F10 pattern, never a screen-local `if (!user) { ... }`
ad hoc check.

**`FilterSheet.tsx`** — Status: **KEEP, SHARED.** Manual filter
bottom-sheet (Bible §27's quick-filter/full-sheet architecture). Feeds
the Constraint contract (Data & State Map §3) as explicit, session-
scoped soft constraints. Distinct from Search's *interpreted* constraint
chips (§4 below, net-new) — a manual pick and an AI-interpreted
constraint are different origins even when they render similarly;
consolidating their *visual* chip treatment is fine and expected
(Design System §7), consolidating their *component* is not required
and shouldn't be forced.

**`MapBottomSheet.tsx`** — Status: **KEEP, SCREEN-SPECIFIC (Map).**
Already implements exactly the "map card" pattern locked in the
original design interview and Route & Flow Map F9 (drag-to-dismiss,
tap-to-navigate) — no new component needed for Map's card behavior,
this is the reference implementation the Design System's sheet
guidance (§7) points back to.

**`MenuSubmissionSheet.tsx`**, **`ReportPhotoSheet.tsx`** — Status:
**KEEP, SCREEN-SPECIFIC (Place Detail).** User-correction entry points
for menu and photo data respectively. Note for the eventual Place
Detail screen contract, not decided here: the Privacy Matrix's "users
can report incorrect menu/hours/location information" rule (G2) is
currently only implemented for menu and photos — hours/location
reporting has no equivalent sheet yet. Flagged as a contract-level gap,
not resolved in this registry.

**`ShareLinkSheet.tsx`** — Status: **KEEP, SCREEN-SPECIFIC (Craves).**
The manual paste-a-link *capture* mechanism for the "Seen on social"
import pipeline (Bible §20). This is the intake side only — the
*display placement* of imported content on Place Detail remains
explicitly OPEN (Route & Flow Map §1.1/§5.1a, Evidence Hierarchy §7).
Codex rule: do not let this component's existence be read as license to
resolve the OPEN placement question — capture and display are separate
decisions.

### F. Recording / media — merge targets for the Native Posting composer

**`PlaceVideoGallery.tsx`** — Status: **EXTEND.** Read-only approved-
video gallery stays; its "record a new one" entry point currently opens
`record-video/[placeId]` directly and must be redirected to the new
Native Posting composer once built (Target Screen Registry §5.4/§5.5's
MERGE finding) — the gallery-display half of this component is
unaffected.

**`VideoTemplateStrip.tsx`**, **`BeatCueOverlay.tsx`** — Status:
**KEEP, RELOCATE.** Shot-template picker and timed recording prompts.
These get reused inside the new composer's media-capture step exactly
as they work today — the Route & Flow Map was explicit that
`record-video`'s capture/permission code is reused, not rebuilt.
Codex rule: do not rewrite these two for the new composer; import them
into it.

### G. Navigation & chrome utility

**`SectionHeader.tsx`** — Status: **KEEP, SHARED.** Label/subtext/count
row header, used across Feed's tiered sections today. Codex rule: any
new section header (Rank Home's queue section, Craves' resurfaced
subset) reuses this, not a bespoke header per screen.

**`CitySelectorStrip.tsx`** — Status: **KEEP, SHARED.** City-selection
strip, already used on Map; a candidate for Feed/Search/Craves wherever
location-fallback (Privacy Matrix A1, Permission Failure Matrix)
surfaces a manual "Choose an area" control — the *same* component,
not a per-screen reimplementation of city choice.

**`Toast.tsx`** (`ToastContainer`) — Status: **KEEP, SHARED, SINGLETON.**
Mounted once in the root layout. Codex rule: never mount a second
instance for a new screen — call the existing `useToast` hook.

---

## 3. Net-new components required

None of these exist today. Each is required by a V1 REQUIRED surface
per `CRAVE_V1_SCOPE.md` and is listed here so a screen contract can
cite it rather than re-deriving its shape.

**1. Reason Block / Decision Strip renderer** — Status: **CREATE.**
One shared renderer for the Design System §5 grammar (role/reason
label, "Strong fit" language, practical facts, three entry-source
variants), consuming a candidate's role/reason-codes/confidence/
completeness fields (Data & State Map §2). Used both as `PlaceCard`'s
terse inline reason line and as Place Detail's full Decision Strip —
**one grammar, two rendering densities, not two independent string
templates.** Dependency: the recommendation request contract's
response shape.

**2. Operational status display** — Status: **CREATE.** Renders
hours/open-status/freshness with honest omission when data doesn't
exist (Data & State Map §6, reconciliation entry #4) — specified now
so the display contract is ready the moment `hours`/`is_open` ingestion
lands, rather than improvised then. Dependency: the place operational-
data contract.

**3. Rank Queue Row** — Status: **CREATE.** A visit awaiting comparison
has no position yet — distinct from `RankedPlaceRow`'s numbered-
position row, and must not be forced into that component's shape.
Dependency: the visit evidence contract (Data & State Map §4).

**4. Quick-Take Reaction control** — Status: **CREATE.** The Loved it /
Good / Not for me three-way tap, distinct from `ComparisonChoice`'s
two-way duel (different shape, different meaning — a quick-take is not
a comparison). Used by the Native Posting composer and any standalone
post-visit log. Dependency: the structured meal reaction signal
(Evidence Hierarchy §3.7).

**5. Taste Profile correction control** — Status: **CREATE.** The
four-action vocabulary (Not true / Doesn't matter to me / Less of this
/ More of this) attached to a displayed inference. Dependency: the
taste evidence/correction contract (Data & State Map §5).

**6. Persistent context chip** — Status: **CREATE.** Feed's always-
visible, tap-to-expand context summary ("Solo · Dinner · Nearby").
Visually a chip (Design System §7) but a new interaction (tap-to-
expand into the lightweight context override), not a `FilterSheet`
variant.

**7. Search constraint chip (interpreted, editable)** — Status:
**CREATE.** Visually consistent with `FilterSheet`'s existing chip
treatment where practical, but a distinct origin (AI-interpreted, shown
inline, individually removable/editable) from a manually-picked filter
— see §2 E's note. Dependency: the constraint contract (Data & State
Map §3).

**8. Activity event row** — Status: **CREATE.** Distinct fields from
either place-card family (an event, not a place) — reference,
timestamp, event type, read/unread state. Dependency: none blocking;
independent of the recommendation contracts.

---

## 4. Consolidation actions this audit surfaces

Findings from checking the registry against real code, not assumptions
— none of these are implemented by this document, all are flagged for
the relevant future screen contract:

- **Leaderboard's hand-rolled row** should become `RankedPlaceRow` if
  Leaderboard survives its AUDIT REQUIRED status (§2 B).
- **AuthSheet's invocation** should consolidate into the one F10 gate
  pattern rather than staying duplicated per screen (§2 E).
- **`PlaceVideoGallery`'s record entry point** redirects to the new
  Native Posting composer once it exists, rather than continuing to
  open `record-video` directly (§2 F).
- **Hours/location reporting** has no sheet equivalent to
  `MenuSubmissionSheet`/`ReportPhotoSheet` yet — a real gap for Place
  Detail's eventual screen contract, not resolved here (§2 E).

---

## 5. Codex Component Invariants

1. A new screen's need for "a card that's slightly different" is a
   props addition to an existing shared component, never a new file,
   unless this registry doesn't already have one that fits — in which
   case the correct move is adding a row here, not improvising.
2. `TierBadge` and `RankedPlaceRow` (and any future personal-tier
   component) never converge into one generic tier component, under
   any refactor, ever (§1).
3. Empty/Error/Skeleton states are always the three components in §2
   C — a fourth state-presentation family is never created.
4. Auth gating always uses the shared AuthSheet through the one F10
   invocation pattern — never a screen-local ad hoc check.
5. The Reason Block / Decision Strip renderer (§3.1) is the only
   renderer of recommendation reasoning anywhere in the app — Feed,
   Discovery, Search, Craves, and Place Detail all call it, none
   reimplement its grammar locally.
6. Components reused from `record-video` into the Native Posting
   composer (`VideoTemplateStrip`, `BeatCueOverlay`) are relocated, not
   rewritten.

---

## 6. Next artifact

Per the sequence, the next canonical artifacts are the **individual
Screen Contracts** — the biggest remaining gate before Codex gets
broad implementation authority. Each needs: purpose → first viewport →
hierarchy → sections → component tree (drawing only from this registry
and §3's net-new list) → states → interactions → navigation → data →
permissions → accessibility → analytics/evidence → edge cases → visual
rules → Codex prohibitions. At minimum, contracts are still needed for
Feed, Search, Craves, Rank Home, the Rank Comparison reconciliation,
Profile, Other User Profile, Taste Profile, contextual Map, the Place
Detail reconciliation, Native Posting/Private Logging, Activity,
onboarding/calibration, auth gate behavior, and Settings/privacy
controls — followed by Codex Implementation Rules v2, a Requirements/
Traceability Matrix, an Implementation Order + Migration Plan, and a
final Codex Readiness Audit (GREEN/YELLOW/RED per screen) before any
broad implementation authority is handed over.
