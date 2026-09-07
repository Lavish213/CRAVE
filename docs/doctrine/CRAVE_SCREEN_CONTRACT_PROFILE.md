# CRAVE Screen Contract — Profile

**Status:** Draft contract, pending audit/freeze (2026-09-07)
**Reconciliation basis:** `(tabs)/profile.tsx` today is "who you are,
your ranked list, and the two social surfaces (friends feed,
leaderboard) hanging off it" (its own header comment), tab-titled
"You." The route file is already correctly named `profile` — only the
title, the ranked-list ownership, and the friends-feed link need to
change. This contract's launch now depends only on Rank Home's contract
(already drafted, §15) to receive the migrating content.

---

## 1. Purpose

The "understand your food identity" surface
(`CRAVE_ROUTE_FLOW_MAP.md` §2) — one of five tabs. Identity first,
evidence second, never a vanity-metric dashboard.

## 2. User objective

See a curated, honest picture of your own food identity; reach Taste
Profile, Settings, and (pending its own audit) Leaderboard from here.

## 3. Entry points

Profile tab (title changes from "You" to "Profile").

## 4. Exit points

Taste Profile (drill-in), Settings (gear icon), Rank Home (tapping the
Rank-status summary switches tabs, does not push a stack screen),
Leaderboard (unchanged pending its own AUDIT REQUIRED status).

---

## 5. First viewport

Identity header + the taste-identity summary — a headline-style
personality statement ("42 places ranked. You know this city."),
**sourced from real Taste Profile data structurally**, not decorative
copy independent of it (the one change to an already-praised pattern:
it must actually read from the same data Taste Profile shows, not a
separately-generated string).

---

## 6. Information hierarchy & section order

**Always present:** identity header (photo, name, city), taste-identity
summary, Settings gear icon.

**Conditional:**
- **Rank status summary** — present once any Rank data exists; a
  lightweight inline status line (Design System §6's "text + at most
  one accent moment" rule — never `RankedPlaceRow`, never the full
  list, both of which now live in Rank Home). Absent for a user with no
  rankings yet, replaced by a light nudge toward ranking known
  restaurants.
- **Food history / posts** — present only with real content.
- **Leaderboard entry point** — kept, unchanged, exactly as it exists
  today, pending Leaderboard's own AUDIT REQUIRED resolution
  (V1 Scope §5.6) — this contract does not touch it.

**Removed from this screen (migrated elsewhere):** the full ranked
list (→ Rank Home), the `friends-feed` entry point (→ Feed's social
rail, per the Route & Flow Map's resolved judgment call — Profile no
longer links to it once that migration completes).

---

## 7. Component tree

```
ProfileScreen
├─ IdentityHeader
├─ TasteIdentitySummary        (sourced from Taste Profile data)
├─ RankStatusSummary (conditional; lightweight, links to Rank tab)
├─ FoodHistorySection (conditional)
├─ PostsSection (conditional)
├─ LeaderboardEntry (unchanged)
└─ SettingsGearIcon → Settings (unchanged placement, already correct)
```

## 8. Component reuse / new components

**Reused, unchanged:** `SectionHeader`, `EmptyState`/`ErrorState`/
`SkeletonCard`, the existing gear-to-Settings pattern (already
correctly placed — no change needed, V1 Scope §4.1 confirms this).

**Not reused:** `RankedPlaceRow` no longer renders here — it belongs to
Rank Home exclusively.

**New:** none — the Rank status summary is a lightweight text
treatment, not a new component family, per Design System §6.

---

## 9. No vanity counters, no bio-as-performance

No numerical status counters (post count, ranked-places count, visit
count) as standalone metrics (V1 Scope §4.1, direct consequence of the
"never reward volume" guardrail). If a bio-like field exists at all, it
is an auto-generated food-preference tagline, not an open free-text box
inviting generic personality-performance content.

---

## 10. State coverage table

| State | Behavior |
|---|---|
| Anonymous | **N/A** — inherently a signed-in surface; the tab gates through F10 on first open while signed out (consistent with Craves and Rank Home). |
| Authenticated | Full hierarchy (§6). |
| Loading | `SkeletonCard`-based skeleton. |
| Success | §6. |
| Empty (new user, no Rank/history/posts yet) | Taste-identity summary and Rank-status both show their own honest "not yet" states (§6) rather than one blanket empty screen. |
| Partial data | Independent per-section fetch/error (already a strength of the current implementation, per the earlier screen audit — kept). |
| Stale | Last-known identity/status data + honest timestamp. |
| Offline | Same as stale; Settings/Taste-Profile drill-ins degrade per their own contracts. |
| Permission-denied | N/A — no permission-gated content on this screen. |
| Low-confidence | N/A — this screen displays established facts (rank data, history), not confidence-scored recommendations. |
| Error | `ErrorState` + retry, per-section (existing pattern, kept). |

---

## 11. Cross-cutting fields

**Interactions:** tap taste-identity summary → Taste Profile; tap Rank
status → Rank tab; tap gear → Settings; tap Leaderboard entry →
unchanged existing behavior.

**Navigation/transitions:** tab-level screen; Settings/Taste-Profile/
Leaderboard are stack pushes; Rank is a tab switch, not a stack push.

**Data reads:** taste evidence/correction contract (Data & State Map
§5, for the identity summary and Rank status), no direct read of the
full ranked-list data (that belongs to Rank Home now).

**Data writes/evidence emitted:** none directly — this is a display
screen; corrections happen in Taste Profile, rankings happen in Rank
Home/Rank Comparison.

**Auth:** required for the whole screen (§10).

**Permissions:** none directly (photo upload for the identity header,
if supported, reuses whatever permission pattern Settings/onboarding
already establish — not a new pattern here).

**Accessibility:** named typography roles (the headline-style summary
uses the `headline` role per Design System §2); 44pt touch targets;
full screen-reader support.

**Analytics:** this screen is not a recommendation surface — no
`surface` value; standard screen-view logging only.

**Responsive behavior:** mobile portrait, consistent with prior
contracts.

---

## 12. Prohibited behavior

- No numerical vanity counters, anywhere on this screen.
- No open free-text bio field inviting generic personality content.
- No `RankedPlaceRow` or full ranked list rendered here — Rank Home
  exclusively.
- No `friends-feed` entry point once its migration completes.
- No taste-identity headline copy generated independently of real Taste
  Profile data.

---

## 13. Unresolved dependencies

- **Rank Home's implementation** must exist before this screen's
  ranked-list content can actually be removed (state-ownership
  migration must be atomic, per the Target Screen Registry's Migration
  Risks finding) — the contract for Rank Home is drafted (§15), the
  code migration itself is sequencing, not a canon gap.
- **`friends-feed` migration into Feed's social rail** — same
  sequencing dependency, tracked in Feed's own contract.

---

## 14. Codex implementation boundary

Codex may: change the tab title to "Profile"; remove the full ranked
list and replace it with the lightweight Rank-status summary; remove
the `friends-feed` entry point once Feed's social rail exists; wire the
taste-identity summary to real Taste Profile data.

Codex may **not**: remove the ranked-list content before Rank Home is
ready to receive it (a regression, not a migration, if done out of
order); add a numerical counter "just for now"; add a free-text bio
field; touch the Leaderboard entry point ahead of its own audit
resolution.

---

## 15. Acceptance criteria

- No `RankedPlaceRow` usage remains in `profile.tsx`.
- The taste-identity headline demonstrably reads from the same data
  Taste Profile displays (not a parallel string generator).
- Tab title reads "Profile."
- Full frontend test suite + `tsc --noEmit` clean.

---

## 16. Traceability

**Backward:** `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §26 (as
annotated superseded on navigation, content otherwise valid),
`CRAVE_V1_SCOPE.md` §4.1, `CRAVE_TARGET_SCREEN_REGISTRY.md` §3.6,
`CRAVE_ROUTE_FLOW_MAP.md` F7/§1.1, `CRAVE_DATA_STATE_MAP.md` §5,
`CRAVE_PRIVACY_PERMISSION_MATRIX.md` F3, `CRAVE_DESIGN_SYSTEM.md` §6,
`CRAVE_COMPONENT_REGISTRY.md` §2 B, `CRAVE_SCREEN_CONTRACT_RANK_HOME.md`
(the migration this screen's launch depends on),
`CRAVE_SCREEN_CONTRACT_FEED.md` (the `friends-feed` migration
dependency they share).

**Forward:** Taste Profile's own contract (next), Settings' contract,
the Requirements/Traceability Matrix.

---

## 17. Proposed status

**YELLOW — pending audit.** Blocked only on sequencing with Rank
Home's actual implementation (§13), not on any unresolved product
decision.
