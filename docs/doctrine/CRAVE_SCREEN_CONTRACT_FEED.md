# CRAVE Screen Contract — Feed / Decision Session

**Status:** Draft contract, pending audit/freeze (2026-09-07)
**Reconciliation basis:** `(tabs)/index.tsx` today is a tiered
structural feed (Crave Pick/Gem/Solid/New catalog-percentile sections,
`FlashList`-backed, real skeleton/error/empty states) with a Decision
Session block already live at the top per the shipped
`useDecisionSession` hook and backend — but, per the earlier screen
audit, that block **competes with the main feed rather than
integrating into it.** This contract reconciles the two into one
hierarchy and makes an explicit call the prior audit only flagged:
**catalog-percentile-tier section headers (CRAVE Pick/Gem/Solid/New as
the feed's primary organizing structure) are superseded by Discovery's
reason-coded rails.** The tier *badge* stays, per card, as a catalog
fact (Design System §6) — the tier is no longer what organizes the
screen.

---

## 1. Purpose

Feed is the "decide" surface (`CRAVE_ROUTE_FLOW_MAP.md` §2) — the
default opening tab. It answers "what should I eat right now" first,
and "what else might I like" second, in that structural order, never
the reverse.

## 2. User objective

Reach a confident decision (act, save, or a considered no) with as
little browsing as possible; secondarily, discover something genuinely
new without having to ask for it.

## 3. Entry points

Default tab on app open. Also reached after completing an action
elsewhere (Place Detail exit, Rank Comparison "done") via normal tab
navigation — no special re-entry framing.

## 4. Exit points

Tap-through to Place Detail (§9 of that contract's Decision-Session/
Discovery entry variants), tap "Map these picks" → Contextual Map
(Route & Flow Map F9.1), tap into the social rail's "see all" → the
temporary `friends-feed.tsx` scaffolding (Route & Flow Map §1.1) until
migration completes, or **no action at all** — a first-class success
terminus (F14), never prompted against.

---

## 5. First viewport

Persistent context chip (top, always visible, tap-to-expand) +
Decision Session's first card(s) — a first-time viewer sees CRAVE's
actual recommendation, not a generic banner, before any scrolling.

---

## 6. Information hierarchy & section order

**Always present:**
1. **Context chip** — current inferred/set context summary ("Solo ·
   Dinner · Nearby"), always visible, tap-to-expand into the
   lightweight override (Just me/Date/Friends/Family, ± budget/
   distance).
2. **Decision Session** — 0-3 cards (`PlaceCard` with `role` set),
   never padded to a fixed count. Honestly labeled lower-confidence
   when applicable (cold start, thin local coverage).

**Conditional, in this order when present:**
3. **Discovery rails** — reason-coded (Design System §5's Reason Block
   grammar drives each rail's header via `SectionHeader`), each rail
   present only when it has real, personalized content: "Because you
   loved X," a hole-in-the-wall rail, "From your Craves." **Never** a
   raw catalog-tier section ("CRAVE Pick," "Hidden Gem") as a rail
   header — those badges still render per-card inside any rail, they
   no longer organize the screen.
4. **Discovery bounded mixed stream** — the finite tail beyond named
   rails, with a real end state ("That's everything new today"), never
   an infinite scroll.
5. **Social rail** — small, personalized (followed-user evidence
   weighted, never raw-chronological), present only with real content;
   absent entirely otherwise, never padded with unrelated posts to fill
   the slot.

---

## 7. Component tree

```
FeedScreen
├─ ContextChip                                    (new — Component Registry §3.6)
├─ DecisionSession
│   └─ PlaceCard × 0-3                             (existing, role set — Component Registry §2 A)
│       └─ ReasonBlock (terse)                      (Component Registry §3.1, shared w/ Place Detail)
├─ DiscoveryRails
│   └─ SectionHeader + PlaceCard/PlaceCardCompact × N   (existing components, reason-coded headers)
├─ DiscoveryStreamTail                              (bounded, FlashList — existing pattern, extended)
└─ SocialRail                                       (sourced from friends-feed's existing query logic, relocated)
```

## 8. Component reuse / new components

**Reused, unchanged:** `PlaceCard` (Decision Session and Discovery
cards alike — no separate card type), `PlaceCardCompact`,
`SectionHeader` (rail headers), `SkeletonCard`/`EmptyState`/
`ErrorState`, `CitySelectorStrip` (location-denied fallback, §16),
`TierBadge` (per-card catalog fact only — never a section header, per
this contract's central reconciliation).

**New:** the Context Chip (Component Registry §3.6) and the Reason
Block renderer (§3.1, shared with Place Detail's Decision Strip/Why
This Fits — one grammar, not a third template).

**Retired from this screen's primary structure:** `TrendingStrip.tsx`
stays dormant (Component Registry §2 A) — this contract does not
revive it; Discovery's reason-coded rails are the superseding
mechanism, not a restyled trending strip.

---

## 9. Context chip behavior

Adaptive, not interrogative (`CRAVE_ROUTE_FLOW_MAP.md` F1/F2): CRAVE
asks for context via the chip's expansion only when uncertainty is
materially high and the answer would change the recommendation set —
never more than once per session before recommending. The chip always
shows the current inferred-or-set state; changing it re-queries
Decision Session and Discovery, it does not require a screen reload.

---

## 10. Decision Session behavior

Per Route & Flow Map F2 exactly — this contract does not re-derive it,
only cites it: card tap carries role/reason/session-id into Place
Detail (F2.1); reject replaces only that slot or shows nothing rather
than a padded weak pick (F2.2); the primary commit action routes
through the adaptive-CTA priority already specified in the Place Detail
contract (F2.3); two consecutive full-set rejections trigger an
explicit "what's off tonight" prompt instead of silent regeneration
(F2.4).

---

## 11. Cold start

Per `CRAVE_ROUTE_FLOW_MAP.md` F1.1-F1.2: Decision Session appears
immediately for a new/anonymous user, honestly labeled lower-confidence,
powered by city-popularity fallback plus whatever anonymous-session
evidence exists (Privacy Matrix D2). The account gate (F10) triggers
only at the first stateful action (Save, a full Decision Session
commit, a rail item's Save) — never at page load, never to merely view
Feed.

---

## 12. Discovery rail sourcing and firewall

Each rail's content is evidence-driven (dish-first vs. restaurant-first
per Evidence Hierarchy §3.16's scope rule), reads the recommendation
request/context contract (Data & State Map §2) scoped to Discovery, and
is subject to the same evidence-contamination firewall as everything
else: no `commercial_affiliated` content in any rail, no rail organized
around raw popularity, ever (Evidence Hierarchy §7).

---

## 13. Social rail sourcing

Sourced from the same query logic `friends-feed.tsx` uses today
(chronological, small, "your friend just ranked X"), reweighted here to
be personalized rather than purely chronological, per the Route & Flow
Map's resolved judgment call (§1.1: content migrates here, the
standalone screen becomes a temporary "see all" scaffold, then is
removed once this rail and Activity both exist). `source_type`
(`followed_user`, not `commercial_affiliated` or `imported_external`)
is enforced the same way it is on Place Detail (Data & State Map §7).

---

## 14. State coverage table

| State | Behavior |
|---|---|
| Anonymous | Decision Session + Discovery both work, lower-confidence labeled per cold-start rules (§11). Social rail is **N/A** — following requires an account, nothing to source. |
| Authenticated | Full hierarchy (§6). |
| Loading (initial) | `SkeletonCard` list matching the eventual card layout. |
| Success | The relationship in §6. |
| Empty (whole-screen — "nothing new") | A real, named, honest state ("Nothing new fits right now — check Search or your Craves"), not a blank screen and not filler content manufactured to avoid looking empty. |
| Partial data (some rails have content, others don't) | Handled entirely by §6's conditional presence — not a distinct state. |
| Stale | Last-known Decision Session/Discovery content + honest timestamp (Route & Flow Map F11). |
| Offline | Same as stale, from local cache; rejections/context-chip changes queue until reconnect. |
| Permission-denied (location) | `CitySelectorStrip` manual area selection substitutes; Feed remains fully functional (F12). |
| Low-confidence | Decision Session's own honest "still learning" labeling (§11); never hidden, never faked confident. |
| Error (fetch failure) | `ErrorState` + retry. |
| Screen-specific: two consecutive full-set rejections | Explicit "what's off tonight" prompt (§10, F2.4) replaces silent regeneration. |

---

## 15. Cross-cutting fields

**Interactions:** tap card → Place Detail; tap reject → §10; tap
context chip → expand/override; tap "Map these picks" → Contextual Map;
scroll → paginate the bounded Discovery tail, never infinitely.

**Navigation/transitions:** tab-level screen, no internal stack of its
own beyond the drill-ins named in §4.

**Data reads:** recommendation request/context contract (Data & State
Map §2, three scoped views: Decision Session, Discovery, social rail's
followed-user query), constraint contract (§3, dietary hard-exclusion
always applied), social evidence contract (§7).

**Data writes/evidence emitted:** impression logging (Tier 6 passive,
Evidence Hierarchy §3.20) for every card shown; click-through with
role/position, `surface=decision_session` or `surface=discovery`
respectively (Data & State Map §9); rejection with reason, tier-
differentiated by role (Evidence Hierarchy §3.10); context-chip changes
write session-scoped constraints (§3 of the Constraint contract).

**Auth:** viewing requires none; Save/commit/full rejection-with-reason
persistence gate through F10 at the point of action.

**Permissions:** location (foreground, optional, §14's fallback).

**Accessibility:** Decision Session and Discovery reasoning are text-
forward by construction (Reason Block renderer) — understandable
without photography or color, per Design System §10. Named typography
roles throughout; 44pt touch targets; full screen-reader/reduced-motion
support.

**Analytics:** `surface` values `decision_session` and `discovery` are
distinct (Data & State Map §9); the social rail is not itself a
`surface` value (it's not a recommendation-generating contract call in
the same sense — it logs under the social evidence contract instead).

**Responsive behavior:** mobile portrait primary and only locked form
factor for V1, consistent with every other contract in this set.

---

## 16. Prohibited behavior

- No infinite scroll without a real end state (§6.4).
- No catalog-percentile tier as a section-organizing header — badge
  only, per card (this contract's central reconciliation).
- No popularity/trending rail, ever.
- No autoplay or muted-autoplay video anywhere in Discovery.
- No color-coded Decision Session roles.
- More than one context-clarifying question per session before
  recommending.
- Padding Decision Session to three cards with a weak pick.
- Continuing silent card regeneration past two consecutive full-set
  rejections.
- Reviving `TrendingStrip.tsx` as a shortcut instead of building
  Discovery's reason-coded rails properly.

---

## 17. Unresolved dependencies

- **Dish Intelligence data model** — blocks true dish-first Discovery
  rail presentation beyond restaurant-level evidence.
- **Craves' own contract** (next in this sequence) — the "From your
  Craves" rail's exact sourcing is finalized there, not here.
- **`friends-feed.tsx` migration** (Route & Flow Map §1.1) — already
  resolved in direction, not yet executed; this contract's social rail
  assumes that migration's target shape.
- **Recommendation request/context contract's literal backend API** —
  deferred to the forthcoming API/Integration Contract artifact; this
  contract specifies the product-level shape only (Data & State Map §2),
  not endpoints/DTOs.

---

## 18. Codex implementation boundary

Codex may: integrate the existing Decision Session block into one
hierarchy per §6; build the Context Chip and reuse the Reason Block
renderer; restructure Feed's rails from catalog-tier sections to
reason-coded Discovery rails; relocate `friends-feed`'s query logic into
the social rail per §13.

Codex may **not**: revive `TrendingStrip.tsx` as a stand-in for
Discovery; keep catalog-tier names as section headers "temporarily";
invent a literal backend endpoint shape ahead of the API/Integration
Contract artifact; build a social rail that's purely chronological
(must be personalized per §13); silently drop the two-consecutive-
rejection prompt as "an edge case for later."

---

## 19. Acceptance criteria

- Decision Session and Discovery read as one integrated hierarchy, not
  two competing sections (the exact defect the prior audit flagged).
- Zero catalog-tier section headers remain; tier badges still render
  per-card.
- The cold-start state (§11), the two-consecutive-rejection state
  (§10), and the whole-screen empty state (§14) are all demonstrably
  distinct in the running app.
- Full frontend test suite + `tsc --noEmit` clean.

---

## 20. Traceability

**Backward:** `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §22.1 (Feed,
including the already-logged `SHOW_FEED_DISCOVERY_STRIPS` decision),
`CRAVE_V1_SCOPE.md` §3.1/§3.2, `CRAVE_TARGET_SCREEN_REGISTRY.md` §3.1,
`CRAVE_ROUTE_FLOW_MAP.md` F1/F2/F9/F14/§1.1, `CRAVE_DATA_STATE_MAP.md`
§2/§3/§7/§9, `CRAVE_PRIVACY_PERMISSION_MATRIX.md` D2/F1/F3,
`CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md` §3.10/§3.16/§3.20/§7,
`CRAVE_DESIGN_SYSTEM.md` §5/§6/§7/§9, `CRAVE_COMPONENT_REGISTRY.md`
§2/§3, and this contract's own upstream sibling,
`CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md` (the Reason Block renderer and
CTA hand-off it shares).

**Forward:** the Craves contract (finalizes "From your Craves" rail
sourcing), the Search contract (shares the constraint contract and the
Map hand-off pattern), the future API/Integration Contract (the
recommendation request/context contract's literal shape), the future
Requirements/Traceability Matrix.

---

## 21. Proposed status

**YELLOW — pending audit.** Named blockers (§17) gate specific
sections (Discovery's dish-first presentation, the Craves rail's exact
sourcing), not the whole contract.
