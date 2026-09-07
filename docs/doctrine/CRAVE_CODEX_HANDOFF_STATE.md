# CRAVE Codex Handoff State

**Status:** CODEX HANDOFF CANDIDATE — certify after final main CI

## Purpose

This document records the implementation baseline immediately before broad Codex execution. It does not replace the canonical implementation index or migration plan; it tells Codex what is already complete so those waves are not repeated.

## Completed before Codex broad execution

### Wave 0 — protected release baseline
Protected release-defect behavior from PR #146 remains mandatory:
- Rank retry re-fetches rather than navigating away.
- recording failure is user-visible.
- signed-out Friends leaderboard is an auth state, not false empty.
- Delete Account remains visually distinct and safely confirmed.

### Wave 1 — shared foundations
Merged via PR #170. Broad implementation must reuse rather than duplicate:
- named typography roles
- shared Decision Strip / reason presentation
- centralized resumable auth-gate host/store and reusable protected-action path
- shared recommendation-context types
- explicit privacy-axis primitives
- visit-evidence eligibility primitives
- Activity row primitive and approved shared UI foundations

### Wave 2 — Rank ownership and visit evidence
Merged via PR #172. Broad implementation must reuse rather than reinterpret:
- persisted visit-evidence contract with declared / verified / inferred tiers
- independent factual-history and recommendation-influence semantics
- saved-place explicit visited memory backfilled/written as declared evidence
- inferred-only evidence cannot enter the Rank queue
- authenticated Rank queue excluding already-ranked places
- Rank Home owns the full ranking task/list
- Profile owns only compact Rank status/navigation
- persisted `liked | fine | disliked` remains the ranking-engine evidence model
- Rank Home presentation derives `Elite | Love | Good` using `CRAVE_RANK_PRESENTATION_MAPPING.md`
- `disliked` remains negative evidence and is excluded from ordered Rank

### Wave 3 — navigation topology
Merged via PR #185 (`codex/wave-3-navigation-topology`). Broad implementation must reuse rather than redo:
- exactly five tabs: Feed / Search / Craves / Rank / Profile
- Map stays reachable at `/map`, removed from tab-bar ownership (kept inside `(tabs)/` with `href: null` rather than a literal app-root `Stack.Screen` — achieves the "not a tab" outcome; a future contract audit may still want the literal relocation)
- persistent `+` opens `/food-evidence`, a capture-only entry surface (stops before publish/log commit — that's Wave 8's composer)
- Activity is a header-icon route (`/activity`), not a tab
- no recommendation/evidence semantics changed; no legacy routes removed; no unrelated screen redesign

### Wave 4 — Feed / Decision Session hierarchy
Merged (`feat: Wave 4 Feed and Decision Session hierarchy`). See `CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.1 for the specific Feed dependencies this wave left open (Craves rail sourcing, `friends-feed` social-evidence migration, durable context/reject/correction behavior needing backend state).

## Codex starting point

Codex starts at **Migration Plan Wave 5 — Search and contextual Map**. It must not redo Waves 0–4.

The exact, current, item-by-item remaining checklist — grouped by wave, cross-referenced to the Readiness Audit and API/Integration Contracts, with the explicitly-blocked list and the permanent Definition-of-Done regression gate — is **`CRAVE_MASTER_CODEX_REMAINING_WORK.md`**. Read that file for the concrete next action; this file only records what's already done.

Verified end-to-end against the current `main` head (2026-09-07): backend `compileall`/import/`pytest` clean (1043 passed, 2 skipped), single Alembic head, frontend `tsc --noEmit` and `jest --ci` clean (426/426), conflict-marker guard clean.

## Hard handoff invariants

- `CRAVE_CANONICAL_IMPLEMENTATION_INDEX.md` is START HERE.
- Current code is implementation evidence, not product authority.
- Do not silently resolve product, UX, information-architecture, visual-design, permission, data-semantic, evidence, privacy, or interaction ambiguity.
- Do not implement OPEN / AUDIT REQUIRED / LATER / REJECTED features unless separately promoted by approved canon.
- Do not rewrite historical user evidence merely to satisfy a new presentation.
- Do not weaken hard dietary/allergy/religious-ethical constraints.
- Do not allow inferred-only location evidence to unlock Rank.
- Do not reintroduce full Rank ownership into Profile.
- Do not make Map independently rerank a source screen's candidate set.
- Do not introduce engagement optimization, star-average framing, paid ranking influence, autoplay vertical feeds, swipe-to-decide, public vanity counts, or public-by-default personal taste.
- Preserve #146 regressions and all green tests after every migration wave.

## Stop / escalation conditions

Codex must stop the affected branch of work and surface the ambiguity when:
- canon conflicts in a way the documented authority order cannot resolve;
- implementation would require changing product meaning rather than adding a degraded state;
- a migration would reinterpret existing user data;
- an OPEN feature appears necessary to make a V1-required flow work;
- privacy/evidence semantics would need to be guessed;
- a backend contract required by a screen does not exist and no canonical semantic is defined.

**The goal is not zero unknowns. It is zero invisible unknowns.**
