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

## Codex starting point

Codex starts at **Migration Plan Wave 3 — navigation topology**. It must not redo Waves 0–2.

Wave 3 target:
- exactly five tabs: Feed / Search / Craves / Rank / Profile
- Map remains a reachable contextual route, not a tab
- Rank Home becomes the Rank tab owner without changing Rank semantics
- persistent `+` action is introduced according to the approved route/flow contract
- Activity remains a header/inbox destination, not a tab
- preserve deep links and auth return destinations during route ownership changes
- do not redesign Feed/Search/Craves/Profile content as part of navigation-only work

After Wave 3, continue the order in `CRAVE_IMPLEMENTATION_MIGRATION_PLAN.md`.

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
