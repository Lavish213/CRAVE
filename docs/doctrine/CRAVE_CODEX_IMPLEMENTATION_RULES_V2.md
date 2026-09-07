# CRAVE Codex Implementation Rules v2

Status: **IMPLEMENTATION CONSTITUTION**

## 1. Core rule
**CODEX MAY RESOLVE IMPLEMENTATION DETAILS. CODEX MAY NOT SILENTLY RESOLVE PRODUCT, UX, INFORMATION-ARCHITECTURE, VISUAL-DESIGN, PERMISSION, DATA-SEMANTIC, OR INTERACTION AMBIGUITY.**

The goal is not zero unknowns. It is zero invisible unknowns.

## 2. Authority order
When instructions conflict, use the newest explicitly approved canonical artifact in this order:
1. canonical doctrine and reconciliation map
2. V1 Scope
3. Target Screen Registry
4. Route & Flow Map
5. Data & State Map
6. Privacy / Permission Matrix
7. Evidence / Signal Hierarchy
8. Design System
9. Component Registry
10. approved Screen Contracts
11. API / Integration Contracts
12. Requirements / Traceability Matrix
13. Migration Plan
14. this Codex rule set and per-task implementation contract

Old implementation comments, screenshots, prior mockups, design exploration logs, or currently shipped UI do not outrank later canon.

## 3. Scope boundary
Codex may implement only:
- V1 REQUIRED
- V1 SUPPORTING
- explicitly approved migration/bug-fix work needed to reach those targets

Codex may not silently implement:
- OPEN — DO NOT IMPLEMENT
- AUDIT REQUIRED
- LATER — ARCHITECT NOW beyond architecture hooks explicitly called for
- LATER — DEFER
- REJECTED / PROHIBITED

## 4. Do-not-redesign rule
Every screen implementation must follow its approved Screen Contract.

Codex may choose:
- file decomposition
- hooks/state organization
- query caching implementation
- internal naming where not externally contracted
- performance-safe rendering techniques
- test structure
- local refactors required to satisfy the contract

Codex may not independently change:
- navigation destination
- section hierarchy
- interaction model
- visibility defaults
- recommendation semantics
- evidence semantics
- copy meaning
- component concept boundaries
- auth requirements
- permission prompts
- ranking behavior
- social product rules

## 5. No speculative feature completion
If a screen contract references a capability that is unavailable and has a defined degraded state, implement the degraded state. Do not fabricate placeholder intelligence, fake menu data, fake open status, fake fit percentages, fake social evidence, or synthetic restaurant media.

## 6. Existing code is evidence, not authority
Shipped code should be reused where it already matches canon. A currently shipped behavior that conflicts with approved canon must be migrated rather than preserved solely because it exists.

Examples already identified:
- Map is currently a tab but target V1 makes it contextual.
- full Rank content currently lives in Profile but target ownership is Rank Home.
- `friends-feed` is migration scaffolding, not a final V1 destination.
- existing Other User Profile full-ranked-list exposure conflicts with private-by-default Rank.
- AuthSheet is useful and should be reused, but invocation/resume semantics must be centralized.

## 7. Component rules
Before creating a component, check the Component Registry.

Codex must not:
- create a second component for the same concept without an approved reason;
- merge two visually similar but semantically distinct concepts;
- reuse catalog percentile tier styling for Rank personal tiers;
- color-code Decision Session roles as separate tier systems;
- create screen-specific variants of the Reason Block/Decision Strip logic when the shared renderer is appropriate.

## 8. TypeScript / frontend quality
- strict TypeScript; no new `any` except a narrowly documented boundary where an untyped external library makes it unavoidable and no safer local type can be written
- explicit loading/error/empty/degraded states
- no swallowed promises for user-visible writes
- no effect race that can overwrite newer request state
- no duplicate query source of truth when one shared state owner exists
- all interactive controls expose accessibility roles/labels/states
- no swipe-only critical action

## 9. Backend quality
- server-side auth/authorization for user-owned/private resources
- explicit Pydantic/request/response contracts
- idempotent critical writes where retries are plausible
- stable error semantics
- transactional updates when evidence + derived state must change atomically
- no business logic hidden in route handlers when a domain/service layer already exists or is clearly warranted
- no direct LLM output trusted as authorization, safety constraint, evidence class, or irreversible write decision

## 10. Evidence rules
Codex may transport, render, collect, and invoke approved evidence semantics. Codex may not:
- invent weights
- collapse signal classes
- reinterpret negative evidence
- convert engagement into preference
- promote inferred visit to verified/declarative visit
- make Save mean “love”
- make Search mean long-term preference without approved reinforcement
- use commercial evidence as recommendation influence

## 11. Privacy rules
Codex may not widen:
- visibility
- data collection
- retention
- recommendation influence
- permission scope

without an approved canonical change.

Private-by-default: Rank, Craves, Taste Profile, never-posted visit history.

No background/precise location collection by default. No user-specific taste intelligence to businesses. Blocking revokes previously visible access.

## 12. Recommendation rules
- no star-average framing
- no paid influence in personalized recommendation surfaces
- no popularity/trending rails as default ranking logic
- no fake fit percentage
- qualitative fit and confidence remain separate
- hard constraints are never silently relaxed
- Map visualizes a set; it does not rerank it
- a confident “no” is a successful outcome

## 13. Social rules
- social supports food decisions; it does not become the app
- no comments
- no follower/following vanity counts
- no public like counts
- no repost/quote-post system
- no autoplay vertical feed
- private anonymous “made me crave this” reactions do not expose reactor identity
- compensated/employee affiliated content never contributes recommendation evidence

## 14. Auth rules
- value before account where canon permits
- first stateful durable action may trigger auth
- auth gate preserves and resumes exact intended action
- auth cancellation is not an error/evidence event
- profile/username setup is not inserted unless the action actually requires social identity

## 15. Data fidelity rules
- missing is missing; do not invent fallback facts
- stale operational data is not presented as current
- provenance/freshness follows the API contract
- exact visit timing stays private unless explicitly posted according to visibility rules
- factual history and recommendation influence remain independent axes

## 16. Migration rules
Codex must follow the migration plan for route/tab ownership changes. It may not delete old routes/components before deep-link/state/test migration is complete.

Every migration task must state:
- old owner
- new owner
- compatibility window
- state/cache migration
- deep-link behavior
- analytics change
- deletion/cleanup condition

## 17. Test gate per implementation unit
A screen/flow PR is incomplete without:
- typecheck
- existing relevant unit/integration tests
- new regression tests for changed behavior
- loading/error/empty coverage
- auth/permission coverage where relevant
- accessibility assertions where practical
- navigation/deep-link assertions for changed routes

Critical evidence/privacy writes require backend tests as well as frontend behavior tests.

## 18. Visual QA
Passing tests do not equal screen approval. After implementation:
1. compare against approved Screen Contract and Design System;
2. verify first viewport hierarchy;
3. verify all required states;
4. verify large text/reduced motion/screen-reader essentials;
5. verify dark-first visual quality;
6. reject accidental generic-template drift.

## 19. Change escalation
If Codex discovers a contradiction or missing product decision:
- stop only the affected semantic decision;
- continue unrelated deterministic implementation if safe;
- record the ambiguity explicitly;
- do not guess;
- request/await canonical resolution before implementing that branch.

A technical implementation choice is not an escalation if it does not alter product meaning.

## 20. Allowed refactor principle
Refactor when it reduces duplication, makes state ownership explicit, improves correctness/performance, or is required by migration. Do not use a screen task as permission for broad unrelated cleanup.

## 21. Repository hygiene
- preserve stable public API names unless migration requires change
- remove dead code only after replacement is verified
- no feature-flag resurrection of rejected/open behavior
- comments explain non-obvious invariants, not obsolete product policy
- update canonical traceability when implementation creates a new durable contract

## 22. Definition of Codex-ready task
A task is ready only when:
- screen/flow status is GREEN or the task is explicitly scoped to unblock a named YELLOW dependency;
- data/API dependencies are named;
- allowed files/surfaces are clear;
- prohibited redesign is explicit;
- acceptance criteria are testable;
- no OPEN product decision is required to complete it.

## 23. Definition of done
Implementation is done when code, tests, state coverage, accessibility, visual QA, analytics/evidence semantics, and migration cleanup all match canon—not when the screen merely renders.
