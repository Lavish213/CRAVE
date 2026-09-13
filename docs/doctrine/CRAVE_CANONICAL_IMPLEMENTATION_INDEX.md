# CRAVE Canonical Implementation Index

Status: **START HERE FOR CODEX**

## 1. Purpose
This file is the single entry point for implementation work. It prevents agents from reading one old document or current screen and mistaking it for the latest product authority.

## 2. Authority chain
Read in this order:

1. `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md`
2. `CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md`
3. `CRAVE_PLACE_DETAIL_SPEC.md` as historical/implemented Place Detail foundation
4. `CRAVE_CANON_RECONCILIATION_MAP.md`
5. doctrine inline annotations created by the reconciliation pass
6. `CRAVE_V1_SCOPE.md`
7. `CRAVE_TARGET_SCREEN_REGISTRY.md`
8. `CRAVE_ROUTE_FLOW_MAP.md`
9. `CRAVE_DATA_STATE_MAP.md`
10. `CRAVE_PRIVACY_PERMISSION_MATRIX.md`
11. `CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md`
12. `CRAVE_DESIGN_SYSTEM.md`
13. `CRAVE_COMPONENT_REGISTRY.md`
14. approved `CRAVE_SCREEN_CONTRACT_*.md` files
15. approved screen-specific architecture overlays such as `CRAVE_FEED_V2_MASTER_ARCHITECTURE.md`
16. approved screen-specific execution maps such as `CRAVE_FEED_V2_MIGRATION_MATRIX.md`
17. `CRAVE_RANK_PRESENTATION_MAPPING.md` for the persisted-ranking to Rank-Home presentation boundary
18. `CRAVE_API_INTEGRATION_CONTRACTS.md`
19. `CRAVE_REQUIREMENTS_TRACEABILITY_MATRIX.md`
20. `CRAVE_IMPLEMENTATION_MIGRATION_PLAN.md`
21. `CRAVE_CODEX_IMPLEMENTATION_RULES_V2.md`
22. `CRAVE_CODEX_READINESS_AUDIT.md`
23. `CRAVE_CODEX_HANDOFF_STATE.md` for the concrete completed-wave baseline and next executable wave
24. `CRAVE_MASTER_CODEX_REMAINING_WORK.md` — **the current operational checklist of exactly what remains**; check this before starting any task so scope is not re-derived from scratch

If two documents conflict, later explicitly approved canon supersedes older product/UI decisions while preserving traceability.

## 3. Current implementation boundary
Codex must treat the following as already completed baseline, not work to redo:
- **Wave 0:** protected #146 release/regression baseline.
- **Wave 1:** shared foundations from PR #170, including typography roles, Decision Strip, resumable auth gate, recommendation-context/privacy/evidence primitives.
- **Wave 2:** visit-evidence persistence + Rank queue + Rank Home ownership + Profile handoff from PR #172.
- **Wave 3:** navigation topology from PR #185 — five tabs (Feed/Search/Craves/Rank/Profile), Map off the tab bar but reachable contextually, persistent `+`, Activity as a header route.
- **Wave 4:** initial Feed / Decision Session hierarchy.

Wave 4 remains real shipped baseline. It is **not** permission to treat its current recommendation semantics as final. The later Feed V2 research/audit found that Home currently combines multiple recommendation authorities and overstates the meaning of Best Fit/Wildcard in places. Feed V2 therefore upgrades the existing Wave-4 foundation rather than reopening navigation or discarding the shipped Decision Session.

Verified end-to-end against the then-current `main` head (backend `pytest` 1043 passed/2 skipped, single Alembic head, frontend `tsc`/`jest --ci` clean, conflict-marker guard clean) — 2026-09-07. Later waves and fixes have landed since; always re-check current CI before claiming implementation-ready runtime status.

The handoff details and hard invariants are in `CRAVE_CODEX_HANDOFF_STATE.md`; the concrete remaining checklist is in `CRAVE_MASTER_CODEX_REMAINING_WORK.md`.

## 3.1 Feed V2 doctrine overlay

The following artifacts were authored after a repository census plus external Feed/recommender research:

- `CRAVE_FEED_V2_MASTER_ARCHITECTURE.md`
- `CRAVE_SCREEN_CONTRACT_FEED.md` (upgraded to Feed / Decision Session V2)
- `CRAVE_FEED_V2_MIGRATION_MATRIX.md`

Their central architectural decision is:

> **Feed V2 does not create another recommender. It consolidates CRAVE's existing Feed ranker, collaborative filtering, Decision Session, Craves, Rank, visit evidence, recommendation context, and recommendation ledger into one truthful Home decision architecture.**

And the UI/product decision is:

> **Decision Mode ends. Explore Mode may continue only when deliberately entered.**

These documents are **architecture/design contracts, not production implementation evidence**. Do not mark Feed V2 implemented merely because these files exist.

Implementation sequence is the dedicated FV2-00 through FV2-09 lane defined in `CRAVE_FEED_V2_MASTER_ARCHITECTURE.md` and `CRAVE_FEED_V2_MIGRATION_MATRIX.md`.

Until the Feed V2 doctrine package is explicitly approved, treat it as a proposed higher-specificity overlay, not permission to begin FV2-01 production changes.

## 4. Target V1 navigation
Bottom tabs are exactly:
- Feed
- Search
- Craves
- Rank
- Profile

Additional destinations:
- Map = contextual spatial support
- `+` = record food evidence / log or post
- Activity = event inbox

Any older document or code comment describing Map as a permanent tab, Rank as a Profile subpanel, or `friends-feed` as a final destination is **superseded for target V1**.

## 5. Core product boundaries
- Decision confidence, not engagement.
- Evidence integrity, not behavior mining.
- Personal taste private by default.
- No paid influence in personalized recommendation surfaces.
- No star-average framing.
- No fake fit percentages.
- No background/precise location collection by default.
- No public full Rank by default.
- No swipe-to-decide.
- No autoplay vertical feed.
- No comments/reposts/vanity counts.

## 6. OPEN / DO NOT IMPLEMENT list
Unless a newer canonical decision explicitly promotes them:
- visible social Rank beyond opt-in coarse highlights
- taste-similarity people recommendation feed
- imported “Seen on social” dedicated Place Detail placement
- standalone Leaderboard expansion (AUDIT REQUIRED)
- Shared Craves V1
- Dish Rank
- voice Search
- full reservation/ordering integrations beyond approved deep links
- personal food-history map
- full route-aware discovery
- learned Feed position-debiasing model before sufficient truthful exposure/outcome volume exists
- contextual-bandit/UCB Feed exploration before sufficient data volume and explicit approval
- CRAVE-trained heavy ranking/embedding infrastructure merely because large marketplace apps use it

## 7. Screen-contract rule
A screen contract is the implementation authority for hierarchy, interactions, states, data dependencies, accessibility, and prohibited behavior. Current code is inspected and reused where correct but does not override the contract.

For Feed specifically, the Screen Contract must be read together with `CRAVE_FEED_V2_MASTER_ARCHITECTURE.md`; the Screen Contract owns the user experience while the Master Architecture owns recommendation/evidence/composition responsibility boundaries.

## 8. Stale-document quarantine rule
The following artifact classes are informative only unless explicitly promoted:
- design exploration logs
- old mockup notes
- screenshots
- one-off execution briefs predating the canonical chain
- code comments describing superseded product behavior
- test names that encode old route ownership
- stale README/roadmap copy

When Codex encounters one of these and it conflicts with canon, it must follow canon and update/remove stale references during the relevant migration.

## 9. Promotion rule
No execution brief may be considered complete if it contains a product, UX, data, provenance, accessibility, or implementation rule that exists only inside that brief. Reusable rules must be promoted into canonical documentation.

## 10. Implementation start condition
Codex should begin broad implementation only from the final handoff commit where:
- this canonical chain is present together;
- #146 regression fixes or equivalent preserved fixes are present;
- prior completed waves are preserved;
- frontend/backend/Postgres/security checks are green;
- the target screen is GREEN or the task is explicitly an unblocker for a named YELLOW implementation dependency;
- for Feed V2, FV2-00 has explicit product-owner approval before FV2-01 begins.

## 11. Escalation rule
A technical unknown may be solved locally. A product/UX/data/privacy/evidence/permission/interaction unknown must be made visible rather than guessed.

**The goal is not zero unknowns. It is zero invisible unknowns.**
