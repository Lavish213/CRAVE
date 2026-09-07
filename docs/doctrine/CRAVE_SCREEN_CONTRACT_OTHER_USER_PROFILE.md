# CRAVE Screen Contract — Other User Profile

**Status:** Draft contract, pending audit/freeze (2026-09-07)
**Reconciliation basis:** `user/[id].tsx` today shows, per its own
header comment, "their ranked list plus a follow button." **This is a
real conflict this contract must flag prominently, not paper over:**
`CRAVE_PRIVACY_PERMISSION_MATRIX.md` C1 locks Rank data as private by
default, with exact position or a full ordered list never public
without an explicit, still-**OPEN** decision (visible social Rank,
V1 Scope §4.5). The shipped screen currently exposes more than doctrine
now allows. This contract's job is not purely additive — it must
**pull back** the default full-list exposure as well as add the
approved taste-compatibility display.

---

## 1. Purpose

The public-facing counterpart to Profile — someone else's curated food
identity, plus (an approved, distinct feature) how compatible their
taste is with yours.

## 2. User objective

Decide whether to follow someone, and get a sense of whether their
taste overlaps with your own — without seeing anything about them that
doctrine now says should stay private by default.

## 3. Entry points

Tapped from Feed's social rail, Leaderboard (pending its own audit), a
username/search lookup, or a follow-request notice in Activity.

## 4. Exit points

Follow/unfollow action, back navigation, or drilling into a specific
place they've discussed (Place Detail, via their posts if any are
public).

---

## 5. First viewport

Identity header (photo, name, city) + follow button + taste-
compatibility summary.

---

## 6. Information hierarchy & section order

**Always present:** identity header, follow/unfollow button, taste-
compatibility-with-you summary (the approved use of the similarity
signal — distinct from the still-OPEN follow-suggestion mechanic,
V1 Scope §4.6).

**Conditional, and only if the viewed person has opted into exposing
it:** coarse Rank tier highlights (top cuisines, Elite-tier places) —
**never** an exact position, **never** a full ordered list, by
default, ever, until the OPEN visible-social-Rank question is
explicitly resolved. Their own public posts, if any exist and are
visibility-set to public/followers.

**Removed from the current implementation:** the default full ranked
list. This is a subtraction, not an oversight — the current behavior
predates Rank's privacy lock and must not be extended or "cleaned up"
as if it were already correct.

---

## 7. Component tree

```
OtherUserProfileScreen
├─ IdentityHeader
├─ FollowButton
├─ TasteCompatibilitySummary        (new content, approved feature)
├─ CoarseRankHighlights (conditional, opt-in gated -- NOT the full list)
└─ PublicPostsSection (conditional)
```

## 8. Component reuse / new components

**Reused:** identity-header pattern (shared with Profile), `PlaceCard`/
`PlaceCardCompact` for any shown public posts, `EmptyState`/
`ErrorState`/`SkeletonCard`.

**Not reused:** `RankedPlaceRow` — this screen never renders a full
ranked list; if coarse highlights are shown at all, they use the same
lightweight text treatment as Profile's own Rank-status line (§6 of
that contract), never the list-row component.

**New:** none beyond the taste-compatibility summary, which reuses the
same similarity computation Taste Profile's other's-mode already
depends on (Component Registry, shared dependency).

---

## 9. Taste compatibility — approved, and its exact boundary

Showing "how similar your taste is to theirs" is approved because the
viewer has deliberately navigated to this specific person's profile —
distinct from an unsolicited "people you may like" suggestion (still
OPEN, V1 Scope §4.6). This screen may compute and show compatibility;
it may **not** use the same signal to power a follow-suggestion feed
anywhere else — that remains a separate, blocked decision.

---

## 10. Follow graph

Single Follow relationship (V1 Scope §5.3) — no second "Friend"
primitive. Muting (content-visibility) and "don't use this person's
taste to influence mine" (data-weighting) are two separate controls,
reachable from this screen, never collapsed into one.

---

## 11. State coverage table

| State | Behavior |
|---|---|
| Anonymous (viewer signed out) | Screen viewable read-only (identity, public posts if any); Follow action gates through F10. |
| Authenticated | Full hierarchy (§6), including compatibility and any opted-in coarse highlights. |
| Loading | Existing skeleton, kept — the prior audit found this screen among "the most thoroughly state-audited" in the app. |
| Success | §6. |
| Empty (no public content, no opt-in exposure) | Identity header + follow button only — not an error, a private choice respected silently, same principle as Taste Profile's other's-mode. |
| Partial data | Independent per-section fetch/error (existing strength, kept). |
| Stale | Last-known identity/compatibility + honest timestamp. |
| Offline | Same as stale; follow/unfollow queues until reconnect. |
| Permission-denied | N/A. |
| Low-confidence (compatibility) | If the similarity signal itself is low-confidence (thin data on either side), state so honestly rather than showing a fabricated compatibility score. |
| Error | Existing `ErrorState` + retry, kept. |
| Screen-specific: 404 / blocked / transient error | Existing, already-correct distinction (per the prior audit) — kept unchanged. |
| Screen-specific: account-switch identity race | Existing guard, kept unchanged. |

---

## 12. Cross-cutting fields

**Interactions:** tap follow/unfollow → F10 if unauthenticated; tap a
public post → its own Place Detail context; tap mute / "don't use their
taste" → the two distinct controls (§10).

**Navigation/transitions:** stack push from wherever entered (§3).

**Data reads:** Follow graph, the taste-similarity computation (shared
with Taste Profile), the viewed user's own opt-in exposure setting for
coarse Rank highlights.

**Data writes/evidence emitted:** follow/unfollow events; mute and
taste-influence-exclusion toggles, each independently.

**Auth:** viewing requires none; follow/unfollow gates through F10.

**Permissions:** none.

**Accessibility:** named typography roles; 44pt touch targets; full
screen-reader support; compatibility language is text-forward, not
color-coded.

**Analytics:** not a recommendation `surface` value; standard screen-
view and follow-action logging.

**Responsive behavior:** mobile portrait, consistent with prior
contracts.

---

## 13. Prohibited behavior

- No default full ranked-list display, under any framing — the
  specific regression this contract exists to prevent from being
  extended further.
- No exact Rank position shown without the still-OPEN visible-social-
  Rank question being explicitly resolved first.
- No follower-count-led framing (V1 Scope §4.2).
- No using the compatibility signal to power a "people you may like"
  feed from this screen or any other, ahead of that separate decision.
- No collapsing mute and "don't use their taste" into one control.
- No second Follow-graph-adjacent relationship primitive.

---

## 14. Unresolved dependencies

- **Visible social Rank** (V1 Scope §4.5, OPEN) — this contract's
  coarse-highlights behavior is the correct default regardless of how
  that question eventually resolves; a future resolution would extend
  this contract, not require rewriting it.
- **Taste-similarity computation's literal backend shape** — deferred
  to the API/Integration Contract artifact.

---

## 15. Codex implementation boundary

Codex may: build the taste-compatibility summary; build the opt-in-
gated coarse Rank highlights; build the two distinct mute/taste-
influence controls.

Codex may **not**: preserve or extend the current default full-ranked-
list display; show exact Rank position by default; use the
compatibility signal to power any follow-suggestion UI; treat this
screen's existing 404/blocked/race-guard correctness as something to
"simplify" — it's already correct and should be left alone.

---

## 16. Acceptance criteria

- The current default full-ranked-list display is demonstrably
  removed, replaced by opt-in-gated coarse highlights only.
- Taste-compatibility summary renders using the same computation Taste
  Profile depends on — not a separate implementation.
- Mute and "don't use their taste" are demonstrably two distinct
  controls in the running app.
- Full frontend test suite + `tsc --noEmit` clean.

---

## 17. Traceability

**Backward:** `CRAVE_V1_SCOPE.md` §4.2/§4.5/§4.6/§5.3,
`CRAVE_TARGET_SCREEN_REGISTRY.md` §6.2, `CRAVE_PRIVACY_PERMISSION_MATRIX.md`
C1/F1/F3/F4, `CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md` §3.17 (social
evidence, support-only), `CRAVE_COMPONENT_REGISTRY.md` §2 B,
`CRAVE_SCREEN_CONTRACT_TASTE_PROFILE.md` (shares the similarity
computation and the other's-mode opt-in-gating pattern).

**Forward:** the Requirements/Traceability Matrix; any future
resolution of visible social Rank extends this contract rather than
replacing it.

---

## 18. Proposed status

**YELLOW — pending audit, and this one needs your explicit sign-off on
the privacy pull-back (§13's central point), not just a rubber-stamp.**
Everything else is intended to be freeze-ready.
