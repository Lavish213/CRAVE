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
15. `CRAVE_API_INTEGRATION_CONTRACTS.md`
16. `CRAVE_REQUIREMENTS_TRACEABILITY_MATRIX.md`
17. `CRAVE_IMPLEMENTATION_MIGRATION_PLAN.md`
18. `CRAVE_CODEX_IMPLEMENTATION_RULES_V2.md`
19. `CRAVE_CODEX_READINESS_AUDIT.md`

If two documents conflict, later explicitly approved canon supersedes older product/UI decisions while preserving traceability.

## 3. Target V1 navigation
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

## 4. Core product boundaries
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

## 5. OPEN / DO NOT IMPLEMENT list
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

## 6. Screen-contract rule
A screen contract is the implementation authority for hierarchy, interactions, states, data dependencies, accessibility, and prohibited behavior. Current code is inspected and reused where correct but does not override the contract.

## 7. Stale-document quarantine rule
The following artifact classes are informative only unless explicitly promoted:
- design exploration logs
- old mockup notes
- screenshots
- one-off execution briefs predating the canonical chain
- code comments describing superseded product behavior
- test names that encode old route ownership
- stale README/roadmap copy

When Codex encounters one of these and it conflicts with canon, it must follow canon and update/remove stale references during the relevant migration.

## 8. Promotion rule
No execution brief may be considered complete if it contains a product, UX, data, provenance, accessibility, or implementation rule that exists only inside that brief. Reusable rules must be promoted into canonical documentation.

## 9. Implementation start condition
Codex should begin broad implementation only from a commit where:
- this canonical chain is present together;
- #146 regression fixes or equivalent preserved fixes are present;
- baseline frontend/backend checks are green or known failures are explicitly classified;
- the target screen being implemented is GREEN or the task is explicitly an unblocker for a named YELLOW dependency.

## 10. Escalation rule
A technical unknown may be solved locally. A product/UX/data/privacy/evidence/permission/interaction unknown must be made visible rather than guessed.

**The goal is not zero unknowns. It is zero invisible unknowns.**
