# CRAVE Screen Contract — Rank Comparison

**Status:** Draft contract, pending audit/freeze (2026-09-07)
**Reconciliation basis:** `rank/[placeId].tsx` is already the most
distinctive, best-executed screen in the app — a real tier→comparing→
done flow, backend-driven signed comparison tokens, genuine haptics/
motion, recently hardened (retry now actually retries the fetch instead
of navigating back). **This contract is deliberately narrow.** It does
not redesign the mechanic; it specifies exactly two additive escape
paths the product doctrine has since locked, and states plainly what
must not change.

---

## 1. Purpose

The "explicitly teach CRAVE" mechanic itself (`CRAVE_ROUTE_FLOW_MAP.md`
§2) — a real, retrospective head-to-head duel between places already
visited, producing CRAVE's highest-integrity taste signal.

## 2. User objective

Place a newly-visited restaurant relative to ones already ranked, or
correct an existing placement — quickly, with real haptics/motion
confirming the choice registered.

## 3. Entry points

Rank Home's queue (F5.2), Place Detail's "Rank it"/"tap to re-rank" CTA
(Place Detail contract §11). No other entry points.

## 4. Exit points

"Done" stage (existing, kept — `ShareRankCard`'s external-share option
lives here, unchanged), or back-navigation mid-comparison (now a real
retry-safe state per the existing hardening, not a dead end).

---

## 5-8. Existing structure — kept verbatim

First viewport, information hierarchy, component tree, and component
reuse are **unchanged** from the shipped implementation: tier stage →
comparing stage (`ComparisonChoice`, tap-to-choose, never swipe) → done
stage (score reveal at the `display` typography role, `ShareRankCard`).
This contract does not re-derive any of it. The only additions are §9
and §10 below.

---

## 9. Addition: "Too close to call"

A third, equally-weighted option alongside picking one side —
**produces a genuine tie outcome** (Route & Flow Map F5.3), never a
fabricated tiebreak. This is not a cop-out UI pattern; it's the direct
implementation of the already-locked rule that an honest "can't tell"
is real information, not noise to be steamrolled for a clean signal.

## 10. Addition: "Haven't been to one of these"

A safety valve for genuine memory/data-integrity mismatches — even
though both compared places are required to have `declared`/`verified`
visit evidence to be comparison-eligible in the first place (Evidence
Hierarchy §3.4), a person can still be uncertain in the moment (a
renamed place, a hazy memory, a data error). Selecting this:

- **Skips this specific pairing** and retries with a different
  comparison candidate — it does not end the ranking session.
- **Does not silently downgrade or delete the questioned place's visit-
  evidence record.** A single moment of uncertainty during a comparison
  is not grounds for the system to overwrite a previously `declared`/
  `verified` record — if the user wants that record corrected, that
  happens through its own correction mechanism (Data & State Map §5),
  never as an automatic side effect of tapping this button.

---

## 11. State coverage table

| State | Behavior |
|---|---|
| Anonymous | **N/A** — reachable only from already-authenticated entry points (§3); no anonymous path exists. |
| Authenticated | The existing three-stage flow, plus §9/§10. |
| Loading | Existing skeleton, unchanged. |
| Success | Existing done-stage score reveal, unchanged. |
| Empty | **N/A** — this screen is never entered without a valid comparison candidate. |
| Partial data | N/A — comparison candidates are validated before this screen loads (existing contract, unchanged). |
| Stale | N/A — comparison tokens are short-lived and single-use by design (existing mechanic); a stale token surfaces the existing retry-safe error state, not a stale-data view. |
| Offline | Existing behavior, unchanged: comparison requires connectivity for the token exchange. |
| Permission-denied | N/A — no permissions used on this screen. |
| Low-confidence | N/A — Rank Comparison is explicit user judgment, never a confidence-scored system output. |
| Error | Existing `ErrorState` + real retry (already hardened this session — retry re-fetches, doesn't just navigate back). |
| Screen-specific: tie (§9) | Produces a real tied outcome in the leaderboard, not an arbitrary tiebreak. |
| Screen-specific: haven't-been (§10) | Skips the pairing, retries with a different candidate; visit record untouched. |

---

## 12. Cross-cutting fields

**Interactions:** tap a `ComparisonChoice` side → pick; tap the new
tie/haven't-been affordances → §9/§10; existing tier-stage and done-
stage interactions unchanged.

**Data reads:** the existing comparison-token backend; no new reads.

**Data writes/evidence emitted:** a resolved comparison (win/loss/tie/
insufficient-data) writes to the taste evidence/correction contract as
an immutable event (Data & State Map §5) — `comparison_resolved` with
outcome type, per Route & Flow Map F5.3, extended to include the two
new outcome types from §9/§10.

**Auth:** required (inherited from entry points).

**Permissions:** none.

**Accessibility, analytics, responsive:** unchanged from the existing
implementation — this contract adds two outcomes, not a new visual or
interaction system.

---

## 13. Prohibited behavior

- No forced binary choice when the honest answer is a tie.
- No silent tiebreak fabrication.
- No automatic downgrade/deletion of a visit-evidence record as a side
  effect of "haven't been to one of these."
- No swipe-to-decide — `ComparisonChoice`'s tap-only pattern is
  unchanged and non-negotiable (Design System §9's global prohibition).
- No rebuilding the existing tier→comparing→done flow "while we're in
  here."

---

## 14. Unresolved dependencies

None. This is the one screen in the current set with no named blocker
— everything it needs already exists and is shipped.

---

## 15. Codex implementation boundary

Codex may: add the "too close to call" and "haven't been to one of
these" affordances to the existing comparing stage; extend the outcome-
logging to the two new types.

Codex may **not**: modify the existing tier→comparing→done flow's
structure, the comparison-token mechanic, `ComparisonChoice`'s tap-only
interaction, or the existing retry-hardening — this contract is
additive only, and "improving" anything not named in §9/§10 is out of
scope here.

---

## 16. Acceptance criteria

- Both new outcomes are reachable and produce the exact data effects
  in §9/§10 — no silent tiebreak, no visit-record mutation.
- Everything else about the existing screen is provably unchanged
  (existing regression tests continue to pass without modification
  beyond what's needed to cover the two additions).
- Full frontend test suite + `tsc --noEmit` clean.

---

## 17. Traceability

**Backward:** `CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` §3.6,
`CRAVE_V1_SCOPE.md` §3.6, `CRAVE_TARGET_SCREEN_REGISTRY.md` §3.5,
`CRAVE_ROUTE_FLOW_MAP.md` F5.2/F5.3, `CRAVE_DATA_STATE_MAP.md` §5,
`CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md` §3.4/§5 (conflict-resolution
precedence, the tie/uncertainty categories in §4 of that document),
`CRAVE_DESIGN_SYSTEM.md` §9 (swipe prohibition), `CRAVE_COMPONENT_REGISTRY.md`
§2 D, existing `frontend/app/rank/[placeId].tsx` implementation itself.

**Forward:** Rank Home's contract (consumes the resolved outcomes),
Place Detail's contract (shares the CTA hand-off), the Requirements/
Traceability Matrix.

---

## 18. Proposed status

**GREEN candidate.** No unresolved product decision, no unresolved
technical dependency, narrowest possible change surface. The strongest
GREEN case in this set — recommend prioritizing this one for early
implementation regardless of overall sequencing, since it carries the
least risk and the existing mechanic already does most of the work.
