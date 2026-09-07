# CRAVE Screen Contract — Taste Profile

**Status:** Draft contract, pending audit/freeze (2026-09-07)
**Reconciliation basis:** `taste-profile/[userId].tsx` today already
shows percentile reframed as "Top X%," explicit tier vocabulary, and is
viewable both on the user's own profile and a friend's — correctly
guarding identity races either way. It deliberately excludes a match-
score (folded into a separate compatibility feature instead). **This
contract surfaces and resolves a real tension the prior audit didn't
flag:** `CRAVE_V1_SCOPE.md` §4.3 calls Taste Profile "private, self-
facing only — never a public-facing artifact." The shipped route's
friend-viewable mode isn't a contradiction of that once split out
explicitly (§9) — but it must be stated as two distinct modes, not one
screen with an ambiguous privacy story.

---

## 1. Purpose

The correction interface for CRAVE's model of the user's own taste
(`CRAVE_ROUTE_FLOW_MAP.md` §2, reached from Profile) — "understand your
food identity," specifically the *why*, not just the *what*.

## 2. User objective

**Own mode:** inspect and correct what CRAVE has inferred. **Other's
mode:** see a curated, coarse summary of a followed person's food
identity — never their raw inferences.

## 3. Entry points

Profile's taste-identity summary (own mode); Other User Profile's own
entry point (other's mode, that contract's own concern).

## 4. Exit points

Back to Profile or Other User Profile respectively.

---

## 5. First viewport

**Own mode:** the curated, confidence-gated trait list. **Other's
mode:** the coarse tier/percentile summary only (§9) — no trait list.

---

## 6. Information hierarchy & section order — own mode

**Always present:** confidence-gated inferred traits (cuisine, dish/
flavor tendencies, independent-vs-chain, price/value, travel
willingness, novelty, negative taste) — each shown only if CRAVE is
actually confident about it; unconfident traits show "still learning
this," never a premature claim.

**Always present, per shown trait:** the four-action correction control
(Not true / Doesn't matter to me / Less of this / More of this).

**Always present, screen-level:** three distinct actions — Pause
personalization / Reset current recommendations / Reset inferred taste
— never merged into one "reset" button.

---

## 7. Information hierarchy & section order — other's mode

**Only present, and only if the viewed person has opted into exposing
it (Privacy Matrix C1's "opt-in exposure of coarse tier-level
highlights"):** top cuisines, Elite-ranked-place highlights, tier
vocabulary (e.g., "Top 8% in San Francisco"). **Never present in this
mode:** the raw trait list, any correction control, any pause/reset
action, any percentage implying personal match to the viewer (that's
Other User Profile's separate, already-approved compatibility display,
not this screen).

---

## 8. Component tree

```
TasteProfileScreen
├─ (own mode)
│   ├─ TraitList
│   │   └─ InferredTrait × N
│   │       └─ CorrectionControl        (new -- Component Registry §3.5)
│   └─ ScreenActions (Pause / Reset-Recommendations / Reset-Inferred-Taste)
└─ (other's mode -- gated on the viewed user's own exposure choice)
    └─ CoarseSummary (tier vocabulary, top cuisines, Elite highlights only)
```

## 9. Own mode vs. other's mode — explicit reconciliation

This is one route, two content modes, gated by whether `userId` is
self:

| | Own mode | Other's mode |
|---|---|---|
| Shown | Full confidence-gated trait list | Coarse tier/percentile summary only, and only if opted in |
| Correction controls | Yes, on every shown trait | **Never** |
| Pause/Reset actions | Yes | **Never** |
| Privacy default | Private (V1 Scope §4.3) | Opted-in exposure only (Privacy Matrix C1) — default is still nothing shown |
| Match-score / compatibility | **Not shown here in either mode** | Lives on Other User Profile instead (already-approved, distinct feature) |

---

## 10. Confidence-gating and correction

Only confident inferences render (§6); an unconfident trait shows
"still learning this," never a fake-precision guess. Every shown
inference is correctable via the four-action vocabulary, writing to the
taste evidence/correction contract (Data & State Map §5) — an explicit
correction outranks passive inference (Evidence Hierarchy's locked
precedence, Tier 1) and holds indefinitely, re-examined (not silently
overridden) only if repeatedly contradicted by strong behavior, in
which case the conflict is surfaced honestly rather than resolved
silently.

---

## 11. Pause / reset-recommendations / reset-inferred-taste

Three distinct, separately-logged actions (Evidence Hierarchy §1.2's
locked distinction, Privacy Matrix C4): pause temporarily stops using
taste signal without discarding it; reset-recommendations clears only
current session state; reset-inferred-taste discards the derived model
while preserving factual history (Rank/visits/posts untouched). None of
the three is a data deletion.

---

## 12. State coverage table

| State | Behavior |
|---|---|
| Anonymous | **N/A** — reached only from an already-authenticated Profile/Other-User-Profile context. |
| Authenticated, own mode | §6. |
| Authenticated, other's mode | §7, gated on the viewed user's opt-in. |
| Loading | Existing skeleton, kept. |
| Success | §6/§7 respectively. |
| Empty (no confident inferences yet — new user) | Honest "CRAVE is still learning your taste" state, pointing toward Rank/ranking known restaurants as the way to speed it up. |
| Empty (other's mode, not opted in) | Nothing renders beyond the coarse summary's own absence — not an error, a private choice respected silently (no "this person has hidden their taste profile" message that itself leaks information). |
| Partial data | Individual traits render independently — one unconfident trait doesn't block others from showing. |
| Stale | Last-known traits + honest timestamp. |
| Offline | Same as stale; corrections queue until reconnect. |
| Permission-denied | N/A. |
| Low-confidence | Is the entire point of §6's gating — not a separate error state, the expected default for a new/thin-data user. |
| Error | Existing `ErrorState` + retry, kept. |
| Screen-specific: identity race (viewing while switching accounts) | Existing guard, kept unchanged — already correctly implemented per the prior audit. |

---

## 13. Cross-cutting fields

**Interactions:** tap a correction action → applies immediately,
confirmed only on success (no optimistic-success lie, Privacy Matrix
C3); tap Pause/Reset actions → confirmation of which one occurred.

**Navigation/transitions:** stack push from Profile or Other User
Profile.

**Data reads:** taste evidence/correction contract (Data & State Map
§5) — own mode reads the full derived profile; other's mode reads only
the subset that person has opted to expose.

**Data writes/evidence emitted:** corrections and the three reset-type
actions, each as its own distinct event type (§11) — never conflated
in logging any more than in UI.

**Auth:** required (inherited from entry points).

**Permissions:** none.

**Accessibility:** confidence language and tier vocabulary are text-
forward; named typography roles; 44pt touch targets; full screen-
reader support.

**Analytics:** correction/pause/reset events logged distinctly (§11);
not a recommendation `surface` value.

**Responsive behavior:** mobile portrait, consistent with prior
contracts.

---

## 14. Prohibited behavior

- No raw trait list or correction controls in other's mode, ever.
- No fake-precision inference shown without real confidence backing it.
- No match-score/compatibility percentage on this screen in either
  mode — that's Other User Profile's separate feature.
- No collapsing Pause/Reset-Recommendations/Reset-Inferred-Taste into
  one button.
- No silently overriding an explicit correction with contradicting
  behavior — surface the conflict instead.
- No default-visible other's-mode content — opt-in only, silently
  absent otherwise.

---

## 15. Unresolved dependencies

- **Decision Architecture Gate 2 (a real user taste graph)** — the hard
  prerequisite; without it, there is nothing genuine for the correction
  UI to correct. This is the single blocker for this contract's core
  purpose, not a peripheral one.

---

## 16. Codex implementation boundary

Codex may: build the four-action correction control; build the three
distinct Pause/Reset actions; split the existing route's own-mode and
other's-mode rendering explicitly per §9, gating other's-mode on the
viewed user's own opt-in choice.

Codex may **not**: show raw inferences or correction controls in
other's mode; build a match-score/compatibility display on this screen
(belongs to Other User Profile); ship confidence-gating "loosely" (i.e.
showing an inference because it's interesting even if not confident).

---

## 17. Acceptance criteria

- Other's mode demonstrably cannot render a correction control or the
  raw trait list, even via a direct navigation attempt.
- Own mode's three reset-type actions are distinguishable in the
  running app and in the event log.
- Full frontend test suite + `tsc --noEmit` clean.

---

## 18. Traceability

**Backward:** `CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` §6/§23
(Gate 2), `CRAVE_V1_SCOPE.md` §4.3, `CRAVE_TARGET_SCREEN_REGISTRY.md`
§6.3, `CRAVE_ROUTE_FLOW_MAP.md` F7.2/F7.3, `CRAVE_DATA_STATE_MAP.md`
§5, `CRAVE_PRIVACY_PERMISSION_MATRIX.md` C1/C3/C4,
`CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md` §1 (Tier 1, explicit correction),
`CRAVE_COMPONENT_REGISTRY.md` §3.5, `CRAVE_SCREEN_CONTRACT_PROFILE.md`
(own-mode entry point).

**Forward:** Other User Profile's contract (next — owns the
compatibility display this screen explicitly excludes), the
Requirements/Traceability Matrix.

---

## 19. Proposed status

**YELLOW — pending audit.** One real, named blocker (Gate 2) gates
this contract's actual substance, not just a section — flagged plainly
rather than understated.
