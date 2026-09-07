# CRAVE Screen Contract — Search

**Status:** Draft contract, pending audit/freeze (2026-09-07)
**Reconciliation basis:** `(tabs)/search.tsx` today has the deepest
state machine in the app (5+ intentionally-designed states by query
length/filters/location) but no semantic-intent parsing, no editable
interpreted-constraint chips, no exact-name bypass to Place Detail, and
no Craves/Rank-scoped query understanding. This contract adds those
without touching what already works well.

---

## 1. Purpose

Search is the "ask with intent" surface (`CRAVE_ROUTE_FLOW_MAP.md` §2)
— one box, literal lookup or semantic intent, always a decision-
reduction surface, never a directory retrieval tool.

## 2. User objective

Find a specific known place fast, or describe a craving and get a
small, reasoned, actionable set — never asked to sift a comprehensive
list.

## 3. Entry points

Search tab. No pre-filled-query entry point is locked anywhere in
current doctrine — not invented here.

## 4. Exit points

Place Detail (exact-name bypass or result tap, organic/query-scoped
framing per that contract's §3), Contextual Map (pivot, F3.4), or a
considered no (F14 applies — leaving without acting is fine).

---

## 5. First viewport

The input box, plus zero-state content (recent semantic searches, a
time/context-relevant intent shortcut) — never a blank box.

---

## 6. Information hierarchy & section order

**Always present:** the single input box.

**Mutually exclusive by query state:**
- **Zero-state** (no query yet): recent semantic searches ("late-night
  ramen near home," not bare keywords), a time-relevant intent
  shortcut, city/location shortcuts. Never generic decorative
  recommendations (V1 Scope §3.3).
- **Query state:** interpreted constraint chips (editable) render
  above the result set; results are a small reasoned set (Reason Block
  renderer, labeled "Best match for you / Safer pick / Worth
  exploring" — **never** Decision Session's exact "Best Fit/Safe Bet/
  Wildcard" vocabulary, a distinction already locked to keep the two
  surfaces conceptually separate) with a bounded "Show more"; manual
  `FilterSheet` quick-filters remain available alongside, feeding the
  same constraint contract.
- **Exact-name, high confidence:** bypasses the results list entirely,
  navigates straight to Place Detail.
- **Zero results:** a named, specific relaxation offer replaces the
  result area — never a bare "no results."

---

## 7. Component tree

```
SearchScreen
├─ SearchInput
├─ ZeroState (RecentSemanticSearches, IntentShortcut)   -- shown pre-query
└─ ResultsArea                                          -- shown post-query
    ├─ ConstraintChips (new -- Component Registry §3.7, editable)
    ├─ PlaceCard / PlaceCardCompact × N  (ReasonBlock, Search-specific labels)
    ├─ ZeroResultRelaxationOffer
    └─ FilterSheet (existing, manual quick-filters)
```

## 8. Component reuse / new components

**Reused:** `PlaceCard`/`PlaceCardCompact`, the Reason Block renderer
(Search-specific label set, not Decision Session's), `FilterSheet`
(unchanged, manual quick-filters), `EmptyState`/`ErrorState`/
`SkeletonCard`.

**New:** the interpreted constraint chip (Component Registry §3.7) —
visually consistent with `FilterSheet`'s chip treatment where
practical, but a distinct origin (AI-interpreted, inline, individually
editable/removable) from a manually-picked filter; the two are never
forced into one component.

---

## 9. Interpretation & constraint chips

Every interpreted query renders its constraint set as visible, editable
chips (Route & Flow Map F3.1) before or alongside results — an
ambiguous parse falls back to literal keyword matching rather than a
blank set. Dietary/allergy constraints, if present in the query, are
hard exclusions (Data & State Map §3) and are never among the chips
offered for relaxation on a zero-result outcome — only soft
constraints (distance, price, cuisine) are ever relaxed.

---

## 10. Exact-name bypass

A high-confidence single-restaurant resolve skips the results list
entirely and opens Place Detail directly, with **organic** framing
(no fabricated Decision-Session/Discovery reasoning) — a results list
containing one obvious answer is itself unnecessary browsing.

---

## 11. Zero-result relaxation

Names the smallest specific relaxation ("2 places match if we expand
your drive from 15→25 min") rather than a generic "try broadening your
search," and only ever proposes relaxing soft constraints (§9).

---

## 12. Search as evidence

A query alone is never taste evidence (Evidence Hierarchy §3.14) — it
becomes evidence only once followed by an action on a result (save,
visit, rank), consistent with Bible §24's already-locked search-
instrumentation addendum. This governs both what gets logged and what
this screen must never imply to the user about "learning" from a
search alone.

---

## 13. Craves/Rank-scoped queries

Queries like "ramen from my Craves" or "my highest-ranked sushi" read
directly from the Craves and Rank data the recommendation request/
context contract already exposes (Data & State Map §2) — this is a
scoping parameter on the same contract, not a second search backend.

---

## 14. State coverage table

| State | Behavior |
|---|---|
| Anonymous | Fully functional — searching and viewing results require no auth; Save/etc. gate through F10 at the point of action. |
| Authenticated | Adds Craves/Rank-scoped query understanding (§13). |
| Loading | `SkeletonCard` list. |
| Success | §6's query-state hierarchy. |
| Empty (whole-screen) | **N/A** — the zero-state (§6) is a real designed content state, not an absence of one. |
| Partial data | N/A beyond normal per-card field omission (inherited from `PlaceCard`'s own rules). |
| Stale | Cached recent results shown with a staleness label; a fresh interpretation requires connectivity. |
| Offline | Same as stale; new queries queue or fail gracefully, cached recent-search zero-state remains usable. |
| Permission-denied (location) | Distance-based interpretation/sorting omitted, not blocked — the rest of Search is unaffected. |
| Low-confidence (weak taste-evidence, strong factual match) | Labeled honestly ("Matches your search, but CRAVE doesn't know your taste for this place yet") rather than blended into the same confidence tier as well-evidenced results. |
| Error (fetch failure) | `ErrorState` + retry. |
| Screen-specific: zero results | §11's named relaxation offer. |

---

## 15. Cross-cutting fields

**Interactions:** type/speak (voice deferred) → debounced interpretation;
tap a chip → edit/remove, re-query; tap exact-name result → §10; tap
"view on map" → Contextual Map, identical result set (F3.4).

**Navigation/transitions:** tab-level screen; drill-ins are stack
pushes (Place Detail, Map).

**Data reads:** recommendation request/context contract (Data & State
Map §2, Search-scoped), constraint contract (§3), Craves/Rank data for
scoped queries (§13).

**Data writes/evidence emitted:** a search-session id groups impressions
and reformulation (Bible §24 addendum, unchanged); a query alone writes
no taste evidence (§12); a subsequent action on a result writes per
that action's own evidence rules (Save/visit/Rank, per the Evidence
Hierarchy).

**Auth:** none required to search or view results; stateful actions
gate through F10.

**Permissions:** location (foreground, optional, gracefully omitted).

**Accessibility:** result reasoning is text-forward (Reason Block
renderer) — understandable without color or photography. Named
typography roles; 44pt touch targets; full screen-reader support.

**Analytics:** `surface=search` (Data & State Map §9); reformulation is
derived at analysis time from consecutive impression batches sharing a
`search_session_id`, never a separately logged event type (Bible §24
addendum, unchanged).

**Responsive behavior:** mobile portrait, consistent with every other
contract.

---

## 16. Prohibited behavior

- No generic sort (distance/rating/popularity) — personalized ranking
  only.
- No comprehensive-inventory default for a vague query — a small
  reasoned set + bounded "Show more," never "here are 50 results."
- No relaxing a dietary/allergy/religious-ethical hard constraint under
  any framing.
- No treating a bare query as positive taste evidence.
- No borrowing Decision Session's exact role vocabulary for Search's
  own reasoned-set labels.
- No person/profile search in this box — food/place intent only.

---

## 17. Unresolved dependencies

- **Constraint-interpretation engine** (the actual NLP/parsing
  backend) — real, new backend work, not a frontend-only change;
  literal API shape deferred to the forthcoming API/Integration
  Contract artifact.
- **Voice Search** — LATER, DEFER (V1 Scope §3.3a); this contract's
  interpretation engine must not hard-code text-only assumptions that
  would make adding it later architecturally painful, but voice itself
  is out of scope here.
- **Route/corridor constraint type** (for a future "on my way" query) —
  architect-now per V1 Scope §3.8a, not built here.

---

## 18. Codex implementation boundary

Codex may: build the interpreted constraint chip component and wire it
to the constraint contract; implement exact-name bypass; implement the
named zero-result relaxation; extend `search.tsx`'s existing state
machine with the above rather than replacing it.

Codex may **not**: invent a comprehensive-results default for vague
queries; relax a hard constraint under any framing; log a bare query as
taste evidence; build voice input; reuse Decision Session's role
vocabulary for Search's reasoned-set labels.

---

## 19. Acceptance criteria

- Exact-name queries bypass the results list in the running app, not
  just in principle.
- A zero-result query always names a specific relaxation, never a
  generic message.
- Constraint chips are genuinely editable, not display-only.
- Full frontend test suite + `tsc --noEmit` clean.

---

## 20. Traceability

**Backward:** `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §24 (incl.
its instrumentation addendum), `CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md`
§3.5, `CRAVE_V1_SCOPE.md` §3.3/§3.3a, `CRAVE_TARGET_SCREEN_REGISTRY.md`
§3.3, `CRAVE_ROUTE_FLOW_MAP.md` F3, `CRAVE_DATA_STATE_MAP.md` §2/§3/§9,
`CRAVE_PRIVACY_PERMISSION_MATRIX.md` D1, `CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md`
§3.12/§3.14, `CRAVE_DESIGN_SYSTEM.md` §5/§7, `CRAVE_COMPONENT_REGISTRY.md`
§2 E/§3.7, `CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md` (exact-name entry
framing), `CRAVE_SCREEN_CONTRACT_FEED.md` (shares the constraint
contract and Map hand-off pattern).

**Forward:** Contextual Map's own contract (consumes Search's identical
result set), the future API/Integration Contract (interpretation
engine's literal shape), the Requirements/Traceability Matrix.

---

## 21. Proposed status

**YELLOW — pending audit.** The interpretation engine itself is real,
unbuilt backend work (§17) — everything else is intended to be
freeze-ready.
