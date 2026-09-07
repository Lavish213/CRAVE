# CRAVE Screen Contract — Rank Home

**Status:** Draft contract, pending audit/freeze (2026-09-07)
**Reconciliation basis:** No current file — "your ranked list" lives
inside `(tabs)/profile.tsx` today, a screen this contract's migration
depends on but does not itself rewrite (that's Profile's own contract).
This is genuinely net-new, per the Target Screen Registry §3.4.

---

## 1. Purpose

Rank Home is the "explicitly teach CRAVE" surface
(`CRAVE_ROUTE_FLOW_MAP.md` §2) — a first-class tab, not a Profile
sub-panel (reconciliation entry #1). Its job is the live task (what's
waiting to be ranked), not a static leaderboard.

## 2. User objective

Complete the taste-teaching loop for a recent visit; secondarily, see
where places stand in personal preference order.

## 3. Entry points

Rank tab. Also reached from Place Detail's "Rank it" / "tap to re-rank"
CTA (that contract's §11), which pushes directly into Rank Comparison,
not this screen — Rank Home is a tab landing, not an intermediate stop
on that path.

## 4. Exit points

Rank Comparison (tap a queued item, F5.2), Place Detail (tap a ranked
entry), or leaving with items still queued — not a failure state, per
§10's decay behavior.

---

## 5. First viewport

The "waiting to be ranked" queue — not the tiered leaderboard. If the
queue is empty, the tiered leaderboard becomes the first viewport
instead (§6).

---

## 6. Information hierarchy & section order

**Always present:** the queue section (0-N `Rank Queue Row` items) —
if empty, this section is simply absent, and the tiered leaderboard
below becomes the effective first viewport rather than leaving a
visible gap.

**Conditional/secondary:**
- **Tiered leaderboard** (Elite/Love/Good — never "Not for me," which
  is excluded from the ordering per Evidence Hierarchy's locked rule,
  not shown as a bottom tier) — present once at least one place has
  been ranked; empty state otherwise points to Rank Comparison's own
  entry conditions.
- **Cuisine/context-scoped views** — reached by drill-down/filter on
  the leaderboard, never separate top-level pages.
- **Exact numbered position** — reached by drill-down (tap into a tier),
  never shown by default.

---

## 7. Component tree

```
RankHomeScreen
├─ QueueSection (conditional)
│   └─ RankQueueRow × N              (new -- Component Registry §3.3)
└─ TieredLeaderboard
    ├─ SectionHeader × (Elite/Love/Good)
    └─ RankedPlaceRow × N            (existing, migrated from profile.tsx)
        └─ (drill-down: exact position, cuisine/context filter)
```

## 8. Component reuse / new components

**Reused, migrated:** `RankedPlaceRow` — the existing component
already used inside `profile.tsx`'s ranked-list section; it moves here
wholesale, it is not rebuilt (Component Registry §2 B).

**New:** the Rank Queue Row (Component Registry §3.3) — a visit
awaiting comparison has no position yet and must not be forced into
`RankedPlaceRow`'s numbered-position shape.

---

## 9. Queue population

Per Route & Flow Map F5.1: only `declared`/`verified` visit evidence
enters this queue directly. An `inferred`-only signal (bare location)
never appears here — it surfaces its own confirmation prompt elsewhere
(Place Detail, or wherever the inference occurred) and only queues here
once promoted to `declared`. This is the exact, deliberate fix already
locked against a bare location ping silently creating Rank eligibility.

---

## 10. Queue item decay

A queued item left unranked decays in priority (visually recedes, is
not deleted) rather than nagging the user or vanishing outright (F5.4)
— the underlying factual visit record persists regardless of ranking
status (Data & State Map §4).

---

## 11. Tier presentation

Text label + at most one accent moment for the top tier (Elite) —
never a second four-color badge palette borrowing the catalog-
percentile tier's hues (Design System §6, Component Registry §1's
central worked example). "Not for me" places are excluded from this
list entirely, not shown as its bottom entry (Evidence Hierarchy locked
rule #9) — they live only as negative evidence feeding recommendations
elsewhere, never as a visible Rank tier.

---

## 12. State coverage table

| State | Behavior |
|---|---|
| Anonymous | **N/A** — Rank is inherently a signed-in surface; the tab gates through F10 on first open while signed out. |
| Authenticated | Full hierarchy (§6). |
| Loading | `SkeletonCard`-based queue/list skeleton. |
| Success | §6. |
| Empty (no queue, no rankings at all — new user) | Points toward ranking known restaurants during onboarding, or visiting somewhere and returning (Bible §42's empty-state discipline: a specific next action, not motivational copy). |
| Empty (queue only, leaderboard populated) | Queue section simply absent (§6) — not a placeholder. |
| Partial data | Individual row field omission per `RankedPlaceRow`'s existing rules. |
| Stale | Last-known queue/leaderboard + honest timestamp. |
| Offline | Same as stale; completing a comparison from here still requires connectivity (existing Rank Comparison constraint, unchanged). |
| Permission-denied | N/A — no permission-gated content on this screen. |
| Low-confidence | N/A — Rank data is explicit user judgment, not a confidence-scored recommendation. |
| Error | `ErrorState` + retry. |
| Screen-specific: tie / insufficient-data outcomes | Reflected honestly in the leaderboard (a real tie, not a fabricated tiebreak) — inherited from Rank Comparison's own outcome handling, not re-decided here. |

---

## 13. Cross-cutting fields

**Interactions:** tap queue item → Rank Comparison; tap a leaderboard
row → Place Detail; tap a tier → drill into exact positions; tap a
cuisine/context filter → scoped view.

**Navigation/transitions:** tab-level screen; Rank Comparison is a
stack push from here, not a tab change.

**Data reads:** visit evidence contract (queue population, Data & State
Map §4), taste evidence/correction contract (leaderboard, §5).

**Data writes/evidence emitted:** none directly — this screen reads and
routes; the actual Rank Comparison writes (§5.3 of the Route & Flow
Map) happen in Rank Comparison's own contract.

**Auth:** required for the whole screen.

**Permissions:** none.

**Accessibility:** named typography roles; 44pt touch targets; full
screen-reader support; tier meaning conveyed by text label, not color
alone (Design System §10).

**Analytics:** `surface=rank_home`, distinct from `decision_session`/
`craves` (Data & State Map §9's already-resolved taxonomy).

**Responsive behavior:** mobile portrait, consistent with prior
contracts.

---

## 14. Prohibited behavior

- No "Not for me" places shown as a bottom Rank tier.
- No exact numbered position shown by default (drill-down only).
- No second four-color tier-badge palette borrowed from the catalog
  percentile tier.
- No `inferred`-only visit evidence appearing in the queue.
- No nagging notification for a decaying queue item.
- No separate top-level pages per cuisine/context — drill-downs only.

---

## 15. Unresolved dependencies

- **`profile.tsx`'s content migration** — this screen's launch depends
  on Profile's own contract removing the ranked-list section it
  currently owns; the migration must be atomic (state ownership can't
  split mid-transition, per the Target Screen Registry's Migration
  Risks section).
- **`(tabs)/_layout.tsx` tab registration** — adding this tab is a
  navigation-chrome change tracked in the Target Screen Registry §2.1,
  not this contract.

---

## 16. Codex implementation boundary

Codex may: build this screen as a new tab; migrate `RankedPlaceRow`'s
usage here wholesale; build the new Rank Queue Row component; wire
queue population to the visit evidence contract.

Codex may **not**: show "Not for me" as a tier; show exact position by
default; invent a new tier-color palette; let an `inferred` visit
populate the queue; register this tab before Profile's corresponding
content removal is ready (avoiding a state-ownership split, per the
Migration Risks finding).

---

## 17. Acceptance criteria

- The queue, not the leaderboard, is the default landing content when
  a queue exists.
- `RankedPlaceRow` is reused verbatim from its current `profile.tsx`
  usage, not reimplemented.
- Leaderboard's `surface=rank_home` analytics tag is distinct and
  verifiable in the Ledger.
- Full frontend test suite + `tsc --noEmit` clean.

---

## 18. Traceability

**Backward:** `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §26 (as
annotated superseded — ranking is no longer a You/Profile sub-panel),
`CRAVE_V1_SCOPE.md` §3.5, `CRAVE_TARGET_SCREEN_REGISTRY.md` §3.4/§2.1,
`CRAVE_ROUTE_FLOW_MAP.md` F5, `CRAVE_DATA_STATE_MAP.md` §4/§5/§9,
`CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md` §3.4 (Rank Tier 2)/§4 (locked rule
#9), `CRAVE_DESIGN_SYSTEM.md` §6, `CRAVE_COMPONENT_REGISTRY.md` §2 B/§3.3,
`CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md` (the Rank-it/re-rank CTA hand-
off it shares).

**Forward:** the Rank Comparison contract (next — this screen's own
primary destination), the Profile contract (the migration this screen
depends on), the Requirements/Traceability Matrix.

---

## 19. Proposed status

**YELLOW — pending audit.** Not blocked on any unresolved product
decision; blocked only on sequencing with Profile's own contract/
migration (§15), which is an execution-order concern, not a canon gap.
