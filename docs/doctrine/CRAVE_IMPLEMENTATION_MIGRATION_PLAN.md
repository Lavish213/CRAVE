# CRAVE Implementation / Migration Plan

Status: **CANONICAL EXECUTION ORDER**

## 1. Purpose
CRAVE’s target V1 architecture differs materially from the current route/state ownership. This plan prevents Codex from performing destructive “cleanup” before compatibility, tests, data ownership, and deep links have moved safely.

## 2. Precondition: canonical branch convergence
Before broad implementation begins, the documentation/bug-fix PRs that define the target state must be merged or stacked into one authoritative base. Codex must not start from a `main` commit that lacks the canonical artifacts it is expected to obey.

Preferred merge strategy: dependency order, resolving conflicts explicitly and re-running the baseline after each logical group. Do not cherry-pick only later docs while omitting their prerequisites.

## 3. Preserve #146 release defects
The four confirmed behavior fixes in #146 must survive the redesign:
- Rank retry truly retries
- video recording failure shows user feedback
- signed-out Friends leaderboard state is not false-empty
- Delete Account is visually distinct from Sign Out

If later target architecture deletes/replaces a touched surface, preserve the underlying regression behavior in the replacement and migrate the tests before removing the old code.

## 4. Migration doctrine
For every ownership change:
1. establish new destination/data owner;
2. add compatibility handoff from old owner;
3. migrate tests/deep links/cache/analytics;
4. verify parity and target behavior;
5. remove old ownership;
6. remove compatibility scaffolding only after no callers remain.

Never delete first and rebuild from memory.

## 5. Wave 0 — baseline freeze
Before target implementation:
- merge/canonicalize docs and #146
- run frontend typecheck/tests
- run backend tests/static checks
- record current route/deep-link inventory
- record current API endpoint/frontend adapter inventory
- record current cache/storage keys relevant to Feed, Craves, Rank, Map, auth, and profile
- record analytics/recommendation-ledger surface values

Any failing baseline test is classified before implementation; do not normalize unrelated red tests as acceptable.

## 6. Wave 1 — shared foundations
Implement before major screen migrations:
- typography token migration from Design System
- shared Reason Block / Decision Strip renderer
- centralized auth gate + resumable action envelope
- explicit shared recommendation request/context types/adapters
- privacy/settings mutation contracts
- visit/evidence type enforcement
- shared ActivityRow and other approved net-new registry components

This wave should not redesign screens; it supplies the primitives they already require.

## 7. Wave 2 — Rank ownership migration
### Current
Ranked list lives in Profile; comparison route exists separately.

### Target
Rank Home becomes bottom tab; comparison remains subordinate route.

### Steps
1. implement Rank Home with eligible queue and existing `RankedPlaceRow` reuse;
2. wire declared/verified-only eligibility;
3. preserve comparison route and add tie / “haven’t been” outcomes;
4. point Profile Rank-status summary to Rank Home;
5. migrate tests from Profile-owned list assumptions;
6. remove full ranked-list ownership from Profile only after Rank Home is verified.

### Compatibility
Deep links to existing comparison route remain valid.

## 8. Wave 3 — navigation topology
Target tabs: Feed / Search / Craves / Rank / Profile.

Steps:
- register Rank tab
- remove Map from tab bar but keep route reachable contextually
- add persistent `+` action without creating a sixth tab
- add Activity header entry point
- ensure existing external/internal deep links to Map resolve to contextual Map route rather than 404
- preserve back navigation to source context

Route migration tests are mandatory.

## 9. Wave 4 — initial Feed / Decision Session integration
### Historical purpose
Wave 4 established the shipped Decision Session hierarchy and removed the old catalog-tier section organization as the primary Home structure.

### Current status
This work remains valid shipped baseline and must not be discarded.

A later 2026-09-08 repository census plus Feed/recommender research found a deeper issue: Home still combines generic Feed ranking, Decision Session role assignment, collaborative-filter recommendations, Craves, filters, and frontend-created supporting rails as partially independent authorities.

Therefore Wave 4 is **baseline, not final Feed architecture**.

Do not reopen navigation or delete the shipped Decision Session. Use the dedicated Feed V2 successor lane in §9.1.

## 9.1 Feed V2 successor lane — FV2-00 through FV2-09

**Status:** architecture package authored; FV2-01 must not begin until the Feed V2 doctrine package receives explicit product-owner approval.

Canonical Feed V2 artifacts:

- `CRAVE_FEED_V2_MASTER_ARCHITECTURE.md`
- `CRAVE_SCREEN_CONTRACT_FEED.md`
- `CRAVE_FEED_V2_MIGRATION_MATRIX.md`

Core decision:

> **Feed V2 does not create another recommender. It consolidates CRAVE's existing Feed ranker, collaborative filtering, Decision Session, Craves, Rank, visit evidence, recommendation context, and recommendation ledger into one truthful Home decision architecture.**

### FV2-00 — doctrine and contracts
- repository census/research synthesis
- Feed V2 Master Architecture
- Feed Screen Contract V2
- file-by-file migration matrix
- role/confidence/evidence semantics
- no production code

### FV2-01 — evidence authority
- typed User Evidence Resolver
- reuse Rank/visit/save/recommendation data
- preserve fact/preference/intent/exposure distinctions
- explicit negative precedence

### FV2-02 — context + candidate evaluation
- extend RecommendationContext only with supported fields
- deterministic candidate dimensions
- hard-constraint gate
- resolved-state and saturation rules

### FV2-03 — Decision Session semantic upgrade
- upgrade shared `build_decision_session()`
- preserve Craves reuse
- preserve no-padding invariant
- replace generic rank/hash semantics with evidence/context-qualified roles

### FV2-04 — one Home composition authority
- backend composition policy
- choose one canonical composed Home transport
- remove frontend semantic rail invention only after parity

### FV2-05 — session cognition
- temporary rejection state
- two-full-set rejection recovery
- commitment/completion
- explicit context reset lifecycle

### FV2-06 — Home UI V2
- render approved composed response
- use UI V2 primitives/product components
- Best Fit visually primary; Safe Bet/Wildcard subordinate
- explicit Explore continuation

### FV2-07 — telemetry / privacy
- correct stale recommendation-impression documentation
- add only real event types
- privacy/retention/deletion updates for any persisted Feed V2 state

### FV2-08 — retirement
- retire Home's independent recommendation composition
- retire unsupported `gem` -> hole-in-the-wall heuristic
- retire duplicate/legacy Feed authorities only after dependency and parity proof

### FV2-09 — certification
- full backend/frontend tests
- cold start/sparse market/low-confidence/rejection/completion fixtures
- accessibility/runtime QA
- real-data/photo QA
- device QA

### Feed V2 invariant

**Decision Mode ends. Explore Mode may continue only when deliberately entered.**

Feed V2 is a parallel/successor migration lane for Home. It does not silently reorder unrelated Wave 8-10 work. Whoever claims it must declare branch/files/base/verification in `.agent-bridge/STATE.md` and avoid overlapping another active owner.

## 10. Wave 5 — Search and contextual Map
Implement shared Search interpretation first, then Map handoff.

Steps:
- semantic query/constraint contract
- exact-name bypass
- bounded results/show-more
- zero-result soft relaxation
- result-set handoff to Map
- Map receives candidate set without rerank
- explicit Search this area produces a new shared request
- location-denied area chooser

Retire independent Map ranking/fetch semantics only after direct-map mode uses the shared recommendation context.

## 11. Wave 6 — Craves intelligence
Migrate current stitched saves view toward:
- prioritized “makes sense now” subset
- full pool
- automatic Tried/Want-to-Try state
- closed/changed notices
- visit-driven graduation

Preserve save IDs/history/cache during migration. Do not silently convert saves to likes/love.

## 12. Wave 7 — Place Detail reconciliation
Place Detail already has meaningful shipped implementation. Migrate incrementally:
- relationship-aware hierarchy
- shared Decision Strip renderer
- saved-unvisited reason memory
- adaptive CTA
- trustworthy operational status handling
- dish/menu evidence gating
- media provenance/fallback
- correction action

Do not replace the entire screen solely to satisfy a visual refresh; preserve working integrations while moving sections to the approved conditional hierarchy.

## 13. Wave 8 — Native Posting / Private Logging
### Current precursors
`record-video` and `add-spot` contain reusable camera/permission/search behavior.

### Target
One shared composer with distinct private-log and native-post outcomes.

Steps:
- create composer route
- relocate/reuse video template/cue primitives where still relevant
- reuse place search/add-spot capability
- build media state machine
- enforce media requirement only for public/follow-scope posting
- implement restaurant/dish confirmation
- add visibility choice
- emit evidence only after successful commit
- redirect old record-video entry points to composer after parity
- retire old routes only after deep-link migration

## 14. Wave 9 — Profile / Taste / Other Profile
### Profile
Remove full Rank list after Rank Home migration; add taste identity/status summary.

### Taste Profile
Requires real taste graph capability for substantive trait display. Until ready, use honest “still learning”/limited state rather than fake traits.

### Other User Profile
Remove default full ranked-list exposure. Only approved public identity/content plus opt-in coarse Rank highlights may render. Compatibility/match display is allowed only on deliberate profile navigation and only from approved taste data.

## 15. Wave 10 — Activity / Settings / Cold Start
- add Activity inbox and event deep links
- extend Settings into privacy/permission/personalization control surface
- split food calibration from username identity setup
- implement anonymous-to-account evidence migration
- update stale profile-setup copy that implies public leaderboard/taste exposure

## 16. `friends-feed` retirement
Target fate: **MERGE / REMOVE AFTER MIGRATION**.

Before deletion verify:
- Feed social rail sources the intended useful evidence
- Activity owns notification/event behavior
- no navigation entry points remain
- deep links redirect or safely resolve
- tests no longer assume standalone screen

## 17. Leaderboard handling
Leaderboard remains AUDIT REQUIRED. Do not redesign/expand it during V1 migration.

If temporarily retained:
- preserve #146 signed-out Friends-state fix
- do not expose private Rank details
- do not duplicate ranked-row component work unnecessarily

If later removed/folded, migrate entry points/tests explicitly.

## 18. Cache/storage migration
For every renamed/moved state owner:
- preserve existing stable keys where semantics match;
- version keys when semantics change;
- write one-time migration where user data would otherwise disappear;
- never reinterpret old cached value under a new semantic meaning;
- clear privacy-sensitive cache on sign-out/account deletion as appropriate.

## 19. Analytics migration
- preserve recommendation-ledger event meaning
- migrate `surface` values according to Data & State Map
- Map source attribution remains parent-aware
- do not double-count during dual-render/compatibility windows
- old route events are retired only after callers are migrated
- Feed V2 algorithm/composition version fields are added only when a real versioned evaluator/composer exists, not speculatively

## 20. Deep-link migration
Maintain a table during implementation for every old route:
- old path
- new path
- redirect/handoff behavior
- state parameters preserved
- removal date/condition

Critical routes: Map, friends-feed, record-video/add-spot entry paths, Profile-owned Rank entry points, auth-return routes.

## 21. Rollback strategy
Each wave should be independently mergeable where possible. Feature flags may protect incomplete target surfaces, but flags must not resurrect rejected/open product behavior. Rollback restores prior stable implementation without corrupting evidence/privacy state.

For Feed V2, the shipped Wave-4 Home remains the rollback target until FV2 cutover is fully verified; do not delete old ownership before the new composed path is live and tested.

## 22. Verification after each wave
- typecheck
- targeted unit/integration tests
- full frontend suite at wave completion
- backend tests for changed contracts
- route/deep-link tests
- data migration test where storage changed
- state coverage QA
- accessibility QA
- visual QA against Screen Contract

## 23. Final cleanup gate
Only after all target owners are verified:
- remove dormant/duplicate route code
- remove compatibility adapters with zero callers
- remove stale comments referencing superseded product rules
- update traceability matrix with final code/test locations

## 24. Codex migration invariant
**No old owner is deleted until the new owner is live, state-compatible, tested, and reachable. No new owner may silently reinterpret existing user data.**

For Feed V2 specifically:

**No visual Home migration precedes a truthful composition authority, and no recommendation signal may be promoted beyond what its evidence semantics support.**
