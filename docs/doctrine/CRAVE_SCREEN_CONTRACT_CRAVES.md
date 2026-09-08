# CRAVE Screen Contract — Craves

**Status:** Draft contract, pending audit/freeze (2026-09-07)
**Reconciliation basis:** `(tabs)/craves.tsx` today stitches three
visual sources — native saves, social-matched/imported craves,
manually-added entries — into one list with two visibly different row
styles and no remove confirmation. This contract keeps all three
*sources* (they're legitimate, per Bible §19 and §20) but collapses
them to the correct number of *evidence types* and replaces the flat
stitched list with the "active intelligence" screen already locked.

---

## 1. Purpose

Craves is the "resolve saved intent" surface (`CRAVE_ROUTE_FLOW_MAP.md`
§2) — the same recommendation engine as Decision Session, scoped to
what the user has already told CRAVE they're interested in. It is not
a bookmark list.

## 2. User objective

Get a confident answer to "which of my saved places should I actually
try, right now" — not to browse everything ever saved.

## 3. Entry points

Craves tab.

## 4. Exit points

Place Detail (Craves-origin framing, F4.2), Contextual Map (F4.3), or a
considered no (F14 — nothing in Craves fitting right now is an honest,
valid outcome, not a failure).

---

## 5. First viewport

The reasoned "these make sense right now" subset — not the full saved
list. The full list is a secondary, explicitly-reached view.

---

## 6. Information hierarchy & section order

**Always present:** the reasoned subset (0-N, same "never pad, never
show nothing wrong just to hit a count" discipline as Decision Session).

**Conditional:**
- **Automatic clusters** (cuisine/occasion/geography-derived — "Ramen,"
  "Near Home," "Worth the Drive") — present only when the saved pool is
  large/varied enough to cluster meaningfully; a small pool shows the
  reasoned subset and a flat full list with no clustering UI at all.
- **Full saved list** — always reachable, never the landing state.
- **Data-integrity notices** (a saved place has closed, or materially
  changed since saving) — conditional, shown inline on the affected
  entry, not a separate section.

**Never present:** manual list-creation/management UI (V1 Scope
§3.4a — LATER, DEFER).

---

## 7. Component tree

```
CravesScreen
├─ ReasonedSubset
│   └─ PlaceCard / PlaceCardCompact × N     (existing, ReasonBlock renderer)
├─ AutomaticClusters (conditional)
│   └─ SectionHeader + PlaceCardCompact × N
└─ FullSavedList
    └─ PlaceCardCompact × N                  (existing per-save memory props)
        └─ DataIntegrityNotice (conditional -- closed/changed)
```

## 8. Component reuse / new components

**Reused, unchanged:** `PlaceCard`, `PlaceCardCompact` (already has
per-save memory props for exactly this screen), `SectionHeader`
(cluster headers), the Reason Block renderer, `EmptyState`/
`ErrorState`/`SkeletonCard`, `ShareLinkSheet` (the intake mechanism for
imported/social-matched entries — unchanged, Component Registry §2 E).

**New:** none — Craves' net-new need is entirely on the intelligence
side (the recommendation request/context contract scoped to the saved
pool), not the component side.

---

## 9. Evidence-source reconciliation

The three visual "sources" in the current implementation reconcile to
**two evidence types**, not three:

- **Save-equivalent** — a native Save action, or a "manually-added"
  entry (typing a place directly into Craves without visiting Place
  Detail first). These are evidence-identical (Evidence Hierarchy
  §3.9, weak-positive) — the manual/native distinction is a UI-entry-
  point detail only, never a scoring difference.
- **Imported/social-matched** — the output of the `ShareLinkSheet`
  intake pipeline (Bible §20, `source_type: imported_external`). This
  is a legitimate, intended Craves state (Bible §19 explicitly lists
  "imported links pending match" and "matched social saves" as Craves
  content) — **the still-OPEN "Seen on social" question is about Place
  Detail's *display placement* for this content, not about whether it
  may appear in Craves' own list, which it already correctly does.**

Both types feed the recommendation request/context contract identically
once resolved to a real place; only their origin/provenance differs
(kept for correction/retraction purposes, Data & State Map §7).

---

## 10. Graduation & decay

Per Data & State Map §4: any one visit-evidence tier (declared,
verified, or inferred-then-confirmed) graduates a saved place out of
the active pool — looser than Rank's declared/verified-only
requirement, since this is a lower-stakes state change. Untouched saves
decay in weight over time but are never force-expired; an occasional,
low-frequency "does this still matter?" check-in may surface in-app,
never as a push notification.

---

## 11. Data integrity

A saved place that has closed, or materially changed since being
saved, is surfaced honestly and inline ("This place has closed" / "This
has changed since you saved it") rather than silently continuing to
recommend it — reading the place operational-data contract's
freshness/provenance stamp (Data & State Map §6), the same mechanism
Place Detail uses.

**Status correction (2026-09-08): blocked, not deferred-and-forgotten.**
This section assumes an operational-data mechanism ("the same as Place
Detail uses") that does not exist anywhere in the app today — confirmed:
`Place`/`PlaceOut` carries no `is_open`, hours, or freshness/provenance
field at all, and Place Detail's own code deliberately omits an
open/closed indicator for exactly that reason (no data to show it from).
There is nothing for this section's inline notice to read. This is the
same class of finding as the Search Screen Contract's §17 offline-layer
correction: real, scoped future work — §3.6 of
`CRAVE_MASTER_CODEX_REMAINING_WORK.md` ("Build trustworthy operational-
data ingestion") — not a Craves-specific gap and not something to
approximate with a fabricated staleness heuristic in the meantime. The
rest of this contract's acceptance criteria (§17) do not depend on this
section, so it does not block Wave 6; it blocks only until §3.6 lands
app-wide, at which point this screen wires into it exactly as specified
above with no further contract change needed.

---

## 12. State coverage table

| State | Behavior |
|---|---|
| Anonymous | **N/A** — Craves is inherently a signed-in, personal surface (Privacy Matrix C2); the tab itself gates through F10 on first open while signed out. |
| Authenticated | Full hierarchy (§6). |
| Loading | `SkeletonCard` list. |
| Success | §6. |
| Empty (no saves at all) | A real empty state: points toward Search/Discovery as the way to start, per Bible §42 — never just "nothing here." |
| Empty (reasoned subset, but saves exist) | Honest "nothing in your Craves fits right now" + pointer to Search/Discovery (F4.1) — distinct from the true empty-list state above. |
| Partial data | Individual save entries missing fields degrade per `PlaceCardCompact`'s existing rules. |
| Stale | Last-known reasoned subset + honest timestamp. |
| Offline | Same as stale, from local cache; new saves/removes queue until reconnect. |
| Permission-denied | N/A directly (location affects the Map pivot and "Near Home" clustering only, gracefully omitted). |
| Low-confidence | N/A as a distinct case — the reasoned subset's own honesty rule (§6) already covers this; a thin pool simply yields fewer entries, not a fake-confident one. |
| Error | `ErrorState` + retry. |
| Screen-specific: saved place closed/changed | §11's inline notice. |

---

## 13. Cross-cutting fields

**Interactions:** tap a card → §4; tap "view on map" → §4.3; remove a
save → confirmation required (a real fix over the current no-
confirmation behavior); tap a cluster → filtered view of the full list.

**Navigation/transitions:** tab-level screen; drill-ins are stack
pushes.

**Data reads:** recommendation request/context contract scoped to the
saved pool (Data & State Map §2), visit evidence contract (§4,
graduation), place operational-data contract (§6, integrity notices).

**Data writes/evidence emitted:** Save/unsave (weak-positive/removed,
Evidence Hierarchy §3.9); viewing the reasoned subset logs an
impression (`surface=craves`, Data & State Map §9); a saved place's
graduation out of the pool is derived, not a separate write.

**Auth:** required for the whole screen (§12).

**Permissions:** location, foreground/optional, affects only "Near
Home" clustering and the Map pivot.

**Accessibility:** Reason Block renderer keeps reasoning text-forward;
named typography roles; 44pt touch targets; full screen-reader support.

**Analytics:** `surface=craves`, distinct from `decision_session` even
though it reuses the same engine (Data & State Map §9).

**Responsive behavior:** mobile portrait, consistent with prior
contracts.

---

## 14. Prohibited behavior

- No raw, unfiltered dump of every saved place as the landing view.
- No manual list-creation/management UI (V1 Scope §3.4a).
- No silently continuing to recommend a closed/materially-changed
  place.
- No force-expiring an untouched save.
- No treating imported/social-matched saves as a different evidence
  type from native saves once resolved to a real place.
- No push notification for "does this still matter?" check-ins.

---

## 15. Unresolved dependencies

- **"Seen on social" Place Detail placement** (still OPEN) — does not
  block this screen; Craves' own listing of imported content is already
  correctly in scope (§9).
- **Shared Craves** (V1 Scope §3.4b) — architect-now for the taste-
  representation structure, not built here.
- **Recommendation request/context contract's literal backend shape**
  — deferred to the API/Integration Contract artifact.

---

## 16. Codex implementation boundary

Codex may: rebuild `craves.tsx`'s landing view around the reasoned
subset; implement automatic clustering; add remove-confirmation; wire
the data-integrity notice to the operational-data contract.

Codex may **not**: build manual list-creation UI; treat imported/
social-matched saves as evidence-distinct from native saves; build a
Shared Craves feature; resolve the "Seen on social" Place Detail
placement question as a side effect of this screen's work.

---

## 17. Acceptance criteria

- Opening Craves shows the reasoned subset first, the full list is a
  secondary, explicitly-reached view.
- The three-visual-source stitching collapses to two evidence types in
  the data layer, with no scoring difference between native and
  manually-added saves.
- Remove now requires confirmation.
- Full frontend test suite + `tsc --noEmit` clean.

---

## 18. Traceability

**Backward:** `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §19/§20,
`CRAVE_V1_SCOPE.md` §3.4/§3.4a/§3.4b, `CRAVE_TARGET_SCREEN_REGISTRY.md`
§3.2, `CRAVE_ROUTE_FLOW_MAP.md` F4/F14, `CRAVE_DATA_STATE_MAP.md`
§2/§4/§6/§7/§9, `CRAVE_PRIVACY_PERMISSION_MATRIX.md` C2,
`CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md` §3.9, `CRAVE_COMPONENT_REGISTRY.md`
§2 A/E, `CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md` (Craves-origin entry
framing, §13 of that contract), `CRAVE_SCREEN_CONTRACT_FEED.md`
("From your Craves" rail, finalized here).

**Forward:** Rank Home's contract (shares the visit-evidence graduation
signal), the future Shared Craves feature (architecture-only
dependency), the Requirements/Traceability Matrix.

---

## 19. Proposed status

**GREEN.** Implemented (2026-09-08): reasoned subset + typed client
(PR #215), screen rebuild around it with remove-confirmation and honest
empty states (PR #216), automatic cuisine/geography clustering (PR #218).
§11's data-integrity notice is the one exception, and is correctly
excluded from this contract's own acceptance criteria (§17) — it is
blocked on the app-wide operational-data foundation (§11's status
correction above), not on anything specific to this screen. The one
remaining tracked gap is cosmetic, not behavioral: the "Craves"/"Added"
sections still render via their own bespoke row style rather than
`PlaceCardCompact`, pending `/craves` and `/hitlist/me` returning full
`PlaceOut` instead of bare IDs (backend work, not scoped to this
contract).
