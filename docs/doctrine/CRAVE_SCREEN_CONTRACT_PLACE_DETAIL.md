# CRAVE Screen Contract — Place Detail

**Status:** Draft contract, pending audit/freeze (2026-09-07)
**Reconciliation basis:** This is not a copy of
`CRAVE_PLACE_DETAIL_SPEC.md` — it audits that spec against everything
locked since it was written and states what's kept, extended, or
superseded. The old spec was written before a user taste graph, a
visit-evidence contract, an Evidence/Signal Hierarchy, a Design System,
or a Component Registry existed. Its information architecture (Hero →
Identity → Decision Strip → Why This Fits → Primary Action → Actions
Row → Menu → Social → Progressive Disclosure) is **confirmed correct
and kept** — it already scored 75/100 against the Master Brutal Screen
Rubric and its skeleton matches everything decided since. What's new
here is making that skeleton genuinely **relationship-aware** (four
states, not one static template) and reconciling every module against
the contracts frozen in #150-#157.

---

## 1. Purpose

Every other CRAVE surface answers "what should I eat" in the abstract.
Place Detail is the one screen that answers, concretely: **why should
I choose (or why did I choose) THIS place.** It is not itself one of
the eight navigation-verb surfaces (`CRAVE_ROUTE_FLOW_MAP.md` §2) — it
is the shared convergence destination all of them lead to (Feed,
Search, Craves, Map) and the living record of the user's relationship
with a place once they've been.

## 2. User objective

- **Never visited:** decide whether to go.
- **Considering tonight:** decide whether *this* is tonight's answer,
  with urgency.
- **Visited, not regular:** record what happened, or complete the
  taste-teaching loop (react, rank).
- **Regular:** decide what to get this time — not whether to go.

## 3. Entry points

| Source | Framing carried in | Governing flow |
|---|---|---|
| Decision Session card tap | role, reason codes, session id | Route & Flow Map F2.1 |
| Discovery card tap | reason codes (no role) | F2.1-adjacent, Discovery-scoped |
| Search result tap / exact-name resolve | organic or query-scoped context | F3.2 |
| Craves resurfaced choice | Craves-origin flag, original save reason | F4.2 |
| Map card / "Map these picks" pin | inherited role/reason from the surface that produced the pin | F9 |
| Organic (deep link, direct navigation) | none — neutral framing only | — |

## 4. Exit points

- **Acted:** external deep-link (Reserve/Directions/website/order),
  in-app commit (Save-for-tonight, Save), quick-take reaction, Rank
  Comparison hand-off, report/moderation sheet.
- **Confident no:** back-navigation or tab-away with no action taken.
  This is a **first-class successful terminus** (Route & Flow Map
  F14), never treated as failure or prompted against with an "are you
  sure" dialog.

---

## 5. First viewport

Hero (full-bleed) with identity overlaid at its base (name leads,
catalog tier badge second, distance if available) — the Decision
Strip is the first thing below the fold-line on a standard phone
viewport. A first-time viewer must be able to answer "what is this
place, roughly how far, and why am I looking at it" without scrolling.

---

## 6. Information hierarchy & section order

**Always present (the stable skeleton — never conditionally absent):**

1. **Hero** — dynamic evidence-driven photo/video, or the typography-
   led fallback (§9). Never both, never empty.
2. **Identity** — name (leads), catalog tier badge, category, price,
   distance (omitted, not blocked, if location permission is denied).
3. **Decision Strip** — practical facts always render; fit language is
   conditional on entry source and confidence (§10).
4. **Primary CTA** — exactly one, adaptive (§11).
5. **Actions row** — Save / Website / Directions always; Order
   conditional on data availability.

**Conditional — present only when the relationship state or evidence
supports it (this is the section the old spec under-specified by
enumerating everything as if always-on):**

6. **Relationship-status block *or* Why This Fits** — mutually
   exclusive, never both. Never-visited/Considering-tonight shows Why
   This Fits (if real evidence backs it — §12); Visited/Regular shows
   the relationship-status block instead (§13/§14). If neither
   evidence nor a visit record exists, this section is simply absent —
   not rendered as an empty placeholder.
7. **Menu** — "For You" leads only with real dish evidence (§15);
   otherwise the plain Full Menu renders with no "For You" framing at
   all. If no menu exists on file, the existing "no menu on file yet"
   state renders (kept from the old spec) — the section itself is
   still present as an empty-state, since users can act on it
   (submit one).
8. **Social evidence** — present only with real friend-ranking or
   native-post evidence to show; absent, not empty-stated, otherwise
   (§16).
9. **Data-completeness caveat** — present only when the place is
   genuinely thin on data (the hole-in-wall floor case, §8).
10. **Progressive disclosure** — full galleries, full address/hours/
    phone/website, report/moderation entry points. Always reachable,
    always below the fold, never promoted.

**Explicitly not a section in this contract:** imported "Seen on
social" content. Its placement remains OPEN (§21) — this contract
renders nothing for it, rather than guessing at a placement.

---

## 7. Component tree

```
PlaceDetailScreen
├─ Hero
│   ├─ ImageGallery | PlaceVideoGallery         (existing, kept)
│   └─ TypographyFallback                        (Design System §2, when no trustworthy image)
├─ IdentityBlock                                  (name, TierBadge, price, distance)
├─ DecisionStrip                                  (Reason Block renderer — Component Registry §3.1)
├─ PrimaryCTA                                     (adaptive, §11)
├─ ActionsRow                                     (Save / Website / Directions / Order)
├─ RelationshipOrWhyThisFits                       (mutually exclusive, §6.6)
│   ├─ WhyThisFitsBlock  (Reason Block renderer, reused — not a second template)
│   └─ RelationshipStatusBlock  (new, screen-specific; Quick-Take Reaction control — Registry §3.4 — when unreacted)
├─ MenuSection
│   ├─ ForYouDishes      (evidence-gated; Operational status display — Registry §3.2 — for freshness)
│   └─ FullMenu
├─ SocialEvidenceSection                          (friend rankings + native posts, source_type-filtered)
├─ DataCompletenessCaveat                          (conditional)
└─ ProgressiveDisclosure
    ├─ Full ImageGallery / PlaceVideoGallery
    ├─ Full details (address/hours/phone/website)
    ├─ MenuSubmissionSheet                         (existing, kept)
    └─ ReportPhotoSheet                             (existing, kept)
```

## 8. Component reuse / new components

**Reused, unchanged:** `ImageGallery`, `PlaceVideoGallery` (its
"record a new one" entry redirects to the future Native Posting
composer per Component Registry §2 F — out of scope for this
contract, tracked there), `TierBadge` (catalog tier only — never
Rank's personal tier, Design System §6), `MenuSubmissionSheet`,
`ReportPhotoSheet`.

**New, per Component Registry §3:** the Reason Block / Decision Strip
renderer (§3.1 — used twice here: terse in the Decision Strip, full in
Why This Fits, one grammar not two templates), the Operational status
display (§3.2), the Quick-Take Reaction control (§3.4, used in the
Visited/not-regular unreacted state).

**Not reused:** `RankedPlaceRow` is a list-row component for Rank
Home's queue/leaderboard context — Place Detail's own "your rank"
status line is a lightweight inline text treatment (text + at most one
accent moment, per Design System §6), not an embedded
`RankedPlaceRow`.

---

## 9. Hero evidence rule

Dynamic, evidence-driven: a standout dish photo leads when real dish
evidence supports it (Evidence Hierarchy §3.16); restaurant/environment
photography leads otherwise. When no trustworthy image exists at all,
the fallback is a **confident typography-led identity treatment**
(`headline`/`display` type roles, Design System §2, on a cuisine-
appropriate solid/textured background) — never a map thumbnail, never
a generic placeholder icon, never an empty gray box. This matters
disproportionately for hole-in-the-wall places, which are least likely
to have professional photography — a degraded-looking fallback would
quietly bias the whole system against exactly the places it exists to
elevate.

---

## 10. Decision Strip — stable structure, honest content

Structure never changes by entry source; content does (Design System
§5, reconciliation entry #1):

- From Decision Session: `BEST FIT TONIGHT` / `SAFE BET` / `WILDCARD`
  + terse reason.
- From Discovery: `WHY CRAVE SURFACED THIS` + terse reason.
- Organic entry: practical facts only — **no fabricated reason.**
- Fit language is qualitative (`Strong fit`) with confidence stated
  separately (`· High confidence`) — never a percentage, never blended
  into one number (Data & State Map §2's confidence/completeness
  split).
- Operational status (open/closed) renders **only when real
  `hours`/`is_open` data exists** (reconciliation entry #4) — omitted,
  never fabricated, until that ingestion gap closes. Distance and
  price always render when the underlying data exists.

---

## 11. Primary CTA — adaptive priority

One button, never more. Priority by relationship state:

- **Never-visited / Considering-tonight:** Reserve (if available) →
  Directions (if arrived via Decision-Session/"tonight" context) →
  Save-for-tonight (in Decision Session context, uncommitted) → Save
  (default).
- **Visited, not regular, no reaction yet:** the Quick-Take Reaction
  control ("How was it?").
- **Visited, reacted but not ranked:** "Rank it" (routes to Rank
  Comparison).
- **Visited/Regular, already ranked:** "Your rank: [tier] · tap to
  re-rank" (routes to Rank Comparison).

The old spec's "I ate here" manual-declare action is **kept**, but now
explicitly writes to the visit evidence contract (Data & State Map §4)
as a `declared`-tier record, and its "tap to re-rank" destination is
unchanged (`rank/[placeId].tsx`, kept as-is per the Target Screen
Registry's §3.6 KEEP verdict).

---

## 12. Why This Fits — honest content, correctable

Content today, unchanged from the shipped spec until Decision
Architecture's Gate 2 (a real taste graph) lands: catalog percentile
fact ("top 5% in San Francisco" — never phrased as personalization),
real friend-ranking count/names, and the user's own past ranking if one
exists. **Not yet:** any sentence implying a personal cuisine-
preference match ("you tend to like Thai") — that requires Gate 2 to
be real, tracked as an unresolved dependency (§21), not built ahead of
it.

Once shown, every line is correctable via the same four-action
vocabulary as Taste Profile (Not true / Doesn't matter to me / Less of
this / More of this) — this is the one place in the product where that
control surfaces outside Taste Profile itself, and it must call the
same taste evidence/correction contract (Data & State Map §5), not a
local copy of it.

---

## 13. Considering-tonight & saved-unvisited memory

When the entry context is Craves-origin or an active Decision-Session
"tonight" context and no visit record exists, the original save/
recommendation reason is remembered and shown, not regenerated fresh
(Route & Flow Map F4.2) — e.g. "You saved this because: similar to 3
places you've ranked Elite."

---

## 14. Visited / Regular — the relationship record

The page stops persuading and starts showing relationship **after the
first confirmed visit** (any `declared`/`verified` visit evidence
record, Data & State Map §4) — this is the exact transition already
locked, not a new decision.

- **Visited, not regular:** "You visited 3 days ago" + reaction status
  (Quick-Take control if unreacted; the given reaction if already
  given) + a "teach CRAVE more → Rank it" nudge if not yet ranked.
- **Regular** (illustrative threshold: 10+ visits, or an equivalent
  Rank-derived signal — the exact number is a tuning detail, not a
  locked product number): leads with status, not persuasion — "One of
  your favorites — Visited 10× · Elite · #2 ramen." Why This Fits is
  **dropped entirely** in this state (re-persuading a regular is
  redundant, not just unnecessary). Menu/For You becomes the dominant
  early section instead, since the live remaining question is "what do
  I get this time," not "should I go."

---

## 15. Menu — For You vs. Full Menu

"For You" dish suggestions require real dish evidence (Data & State
Map §8) — each carries its own reason (Design System, Evidence
Hierarchy §3.16 dish-scope rule) and respects the operational-data
contract's menu-freshness stamp (§6) independent of the place's overall
taste-fit confidence. With weak/no evidence, the plain Full Menu
renders with **no personalization framing at all** — never a
low-confidence "For You" section that erodes trust the first time it's
visibly wrong.

---

## 16. Social evidence — placement and separation

Friend-ranking content and native posts render personalized (friends
weighted, not raw-chronological), with `source_type` (Data & State Map
§7) enforced structurally: `organic_user`/`followed_user` content
renders in this section; `commercial_affiliated` content is excluded
from here entirely (Evidence Hierarchy §7 firewall) and — if shown at
all anywhere — lives in a visually distinct, factual-only area, never
this one. `imported_external` ("Seen on social") is **not rendered
anywhere in this contract** (§21) regardless of how much of it exists
for a given place.

---

## 17. Operational-data gaps

`Place` has no `hours`/`is_open` field today — a real, already-tracked
ingestion gap (`CRAVE_PLACE_DETAIL_SPEC.md` §6), not a design choice.
This contract's Decision Strip (§10) and Progressive Disclosure both
omit operational status honestly until that lands; nothing in this
contract should be read as authorizing a fabricated "Open until 10 PM."

---

## 18. Trustworthy minimum-data floor

The floor for a usable page at all (V1 Scope §3.7): a **real,
verifiable location** and a **reasonably current open/closed status
where the data exists** — not menu completeness, photo volume, or
review count. A place below even this floor renders the "insufficient
data" state (§19's State Coverage Table), not a degraded version of the
normal page.

---

## 19. State coverage table

`N/A` is a real, deliberate answer below — never a silent omission.

| State | Behavior |
|---|---|
| Anonymous (signed out) | Full page viewable; Save/quick-take/Rank/report gate through the shared auth pattern (Route & Flow Map F10) only at the point of action, never at page load. |
| Authenticated | Full page + all personal sections (relationship state, Why This Fits' own-rank line, correction controls). |
| Loading (initial) | Skeleton matching the hero-first layout (kept from the shipped spec, restyled per Design System tokens). |
| Success | The relationship-aware hierarchy in §6. |
| Empty (whole-screen) | **N/A** — a navigable place always has at least identity + location; emptiness is handled at the sub-section level (§6's conditional-presence rules), not the screen level. |
| Partial data (missing optional fields — no price, no address, etc.) | Explicit "not shown" behavior per field, never a blank gap (kept from the shipped spec's per-field audit). |
| Stale | Last-known content + honest timestamp (Route & Flow Map F11); hours/availability specifically get an explicit caveat beyond the general staleness label (F11.2) — the one place this matters most on this screen. |
| Offline | Same as Stale, sourced from local cache; actions that need connectivity (Reserve/Directions external hand-off, Save sync) queue or degrade per §11's own action-specific rules. |
| Permission-denied | Location: distance omitted, rest of the page unaffected (never blocks viewing). Camera/library: scoped entirely to the add-photo/video entry point, handled by that existing flow, never a whole-page state. |
| Low-confidence (recommendation fit) | Decision Strip omits fit language, falls back to organic-entry framing (practical facts only) rather than showing a fit claim it can't back up. |
| Low-confidence (data completeness) | Data-completeness caveat renders (§6.9, §18) — independent of the fit-confidence case above; the two are never blended (Data & State Map §2). |
| Error (fetch failure) | `ErrorState` + retry (existing, kept) — distinct from Insufficient-Data below, which is a data-quality gate, not a transient failure. |
| Insufficient data (below the §18 floor) | A dedicated state, not a degraded Success and not a generic Error — states plainly that CRAVE doesn't have enough verified information about this place yet. |
| Relationship: Never visited | §6 baseline hierarchy, Why This Fits shown if evidence exists. |
| Relationship: Considering tonight | Same hierarchy, sharpened Decision Strip framing + saved-reason memory (§13). |
| Relationship: Visited, not regular | Relationship-status block replaces Why This Fits (§14). |
| Relationship: Regular | Status-led hierarchy, Why This Fits dropped, Menu/For You promoted (§14). |

---

## 20. Cross-cutting fields

**Interactions:** tap card element → drill deeper (gallery, menu item);
tap primary CTA → §11's routed action; tap Save → optimistic toggle +
toast (kept from shipped spec); tap a Why-This-Fits/Taste-Profile-style
correction control → applies immediately, confirmed only on success
(no optimistic-success lie, per Privacy Matrix C3).

**Navigation/transitions:** entry per §3; exit per §4; internal
drill-ins (full gallery, full menu, Rank Comparison, report sheets) are
stack pushes, not tab changes.

**Data reads:** recommendation request/context contract (role/
reasoning when arriving from a recommending surface), constraint
contract (dietary hard-exclusion applied to menu display), visit
evidence contract (relationship state), taste evidence/correction
contract (own past rank, Why This Fits), place operational-data
contract (hours/price/menu freshness), social evidence contract
(friend rankings/posts, `source_type`-filtered), dish contract (For
You).

**Data writes / evidence emitted:** a view of this page logs as Tier 6
passive engagement (Evidence Hierarchy §3.21) — weak, never treated as
rejection even when the user leaves without acting (§4's confident-no
exit); a click-through from a recommending surface logs with
role/position (Data & State Map §9); Save writes weak-positive taste
evidence; the primary CTA's commit action writes a strong-signal event;
the Quick-Take control writes a structured meal reaction (Evidence
Hierarchy §3.7); "I ate here" writes a `declared` visit evidence record
(§4); report actions write to the moderation queue, not the taste
evidence contract.

**Auth:** page view requires none; every write action gates through
the shared F10 pattern.

**Permissions:** location (foreground, optional, graceful omission);
camera/photo-library (scoped to the existing add-photo/video entry
point only).

**Accessibility:** recommendation meaning (Decision Strip, Why This
Fits) must remain understandable without photography or color — a free
consequence of both being text-forward by construction (Design System
§10). Named typography roles throughout (no raw font sizes). 44pt
minimum touch targets. Full screen-reader/scalable-text/reduced-motion
support, per Design System §10 and V1 Scope §7.2 — not a later pass.

**Analytics:** per Data & State Map §9-§10 — this screen is not itself
a `surface` value (it's a destination, not a recommendation-generating
surface); it logs its own relationship-state views, correction events,
and the write events named above.

**Responsive behavior:** V1 targets mobile portrait as the primary and
only locked form factor. No tablet/landscape layout is specified or
required. If reached on web (e.g. a shared deep link), the page should
degrade gracefully — read-only content, no crash — consistent with
`map.web.tsx`'s existing placeholder precedent for native-only
capabilities (video/map embeds); a dedicated web layout is out of
scope for V1.

---

## 21. Prohibited behavior

- No star ratings, ever.
- No dish-level "For You" claim without real dish evidence backing it.
- No numeric taste-match percentage — qualitative fit + separate
  confidence only.
- No fabricated operational status (open/closed) when real data
  doesn't exist.
- No restaurant public-response capability to user content, anywhere
  on this page.
- No rendering of imported "Seen on social" content in any section —
  the placement question stays OPEN; this contract assigns it nothing,
  not even a tentative "progressive disclosure" slot.
- No re-persuasion (Why This Fits) shown to a Regular-state user.
- No degraded/placeholder-looking hero when no trustworthy image
  exists — the typography-led fallback (§9) is mandatory, not optional
  polish.
- No "are you sure you don't want this" prompt on exit without action —
  a confident no is success (§4).
- No embedding `RankedPlaceRow` or `TierBadge` for the user's own Rank
  status — a lightweight inline text treatment only (§8).

---

## 22. Unresolved dependencies

- **Dish Intelligence data model** (Data & State Map §8) — blocks true
  evidence-backed "For You" dish presentation beyond simple save/
  reaction counts.
- **Decision Architecture Gate 2 (real user taste graph)** — blocks any
  Why This Fits copy implying personal cuisine/flavor preference beyond
  catalog fact + friend-ranking + own past rank.
- **`hours`/`is_open` ingestion** — blocks honest operational-status
  display; currently correctly omitted, not fabricated.
- **"Seen on social" placement** (OPEN) — this contract renders nothing
  for it; resolving the placement question doesn't require reopening
  this contract, just adding a new section once decided.
- Note: the existing per-place **friend-ranking display** (§12) is a
  distinct, already-approved, narrower feature from the still-open
  **visible social Rank** question (V1 Scope §4.5) — this contract's
  friend-ranking content is not blocked by that open item.

---

## 23. Codex implementation boundary

Codex may: implement the relationship-state logic reading from the
visit evidence contract; build the Reason Block/Decision Strip renderer
and Operational status display components (Component Registry §3);
extend the existing `place/[id].tsx` implementation per §6-§18 above;
reuse `ImageGallery`/`PlaceVideoGallery`/`TierBadge`/
`MenuSubmissionSheet`/`ReportPhotoSheet` unchanged; wire the primary
CTA's routing per §11.

Codex may **not**: invent a placement for imported "Seen on social"
content; build personalized (non-catalog-fact) Why This Fits copy ahead
of a confirmed real taste graph; fabricate operational status ahead of
real `hours` data; add a numeric match percentage; create a second
Decision-Strip or Why-This-Fits template instead of reusing the one
Reason Block renderer; reintroduce the old spec's flat, non-
relationship-aware hierarchy as a "simpler first pass."

---

## 24. Acceptance criteria

- All four relationship states (§6, §13-§14) are demonstrably distinct
  in the running app, not merely theoretically supported by a
  conditional.
- Every row in the State Coverage Table (§19) has real, designed UI —
  "works by accident because the fetch hook happens to handle it" does
  not satisfy this contract.
- Decision Strip content matches the Design System §5 grammar exactly,
  including the three entry-source variants.
- No Why-This-Fits content renders without a real evidence source
  backing the specific line shown.
- Existing mechanics explicitly preserved, not touched: the three
  stale-response generation-ref guards (`menuGenerationRef`,
  `cravesGenerationRef`, `friendRankingsGenerationRef`) and the upload-
  status effect's `moderationStatus`-vs-`status` separation, both from
  the shipped spec's forensic inventory.
- Full frontend test suite + `tsc --noEmit` clean.
- Re-scored against `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §33;
  target 85+ (baseline 75, per the shipped spec's own tracked
  progress).

---

## 25. Traceability

**Backward — governs this contract:**
`CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §30-§33,
`CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` (Gate 2 dependency),
`CRAVE_PLACE_DETAIL_SPEC.md` (baseline IA, kept), `CRAVE_V1_SCOPE.md`
§3.7, `CRAVE_TARGET_SCREEN_REGISTRY.md` §5.1/§5.1a,
`CRAVE_ROUTE_FLOW_MAP.md` F2/F3/F4/F5/F9/F11/F13/F14,
`CRAVE_DATA_STATE_MAP.md` §2/§4/§5/§6/§7/§8,
`CRAVE_PRIVACY_PERMISSION_MATRIX.md` A4/A5/C1/E1/E3/E4/E6/G2/G3/G4/H1/I2,
`CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md` §3.5-§3.8/§3.16/§3.17/§3.18/§4/§5,
`CRAVE_DESIGN_SYSTEM.md` §2/§5/§6/§7/§8/§9/§10,
`CRAVE_COMPONENT_REGISTRY.md` §2/§3.

**Forward — depended on by:** the Component Registry's net-new Reason
Block/Decision Strip renderer, Operational status display, and Quick-
Take Reaction control (this is one of their consuming contracts, not
their origin); the future Feed contract (which reuses the same Reason
Block renderer for its own terse card reasoning); the future Rank Home
and Rank Comparison contracts (this screen's CTA hands off to both);
the future Native Posting/Private Logging contract (`PlaceVideoGallery`
's entry point redirects there); the future Requirements/Traceability
Matrix.

---

## 26. Proposed status

**YELLOW — contract drafted, named blockers pending audit:** Dish
Intelligence data model, Gate 2 taste graph, and `hours` ingestion are
real, tracked, unresolved dependencies (§22) that gate specific
sections rather than the whole contract. Everything else in this
document is intended to be freeze-ready. Awaiting your audit before
this becomes GREEN.
