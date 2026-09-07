# CRAVE API / Integration Contracts

Status: **CANONICAL IMPLEMENTATION BOUNDARY — schema details may be refined during implementation only inside these semantics**

## 1. Purpose
This document prevents frontend and backend implementation from inventing incompatible meanings after the product/data/screen contracts are locked. It does not replace existing working endpoints merely to make them prettier. It defines the interface behavior every V1 flow must satisfy.

The current codebase already has substantial API surface in `backend/app/api/v1/routes/` and `frontend/src/api/` including account, cities, Craves/saves, Decision Session, map/nearby, places, menu, social/follows, recommendation events, ranking, and related functions. Codex must **reuse or extend** those contracts where semantically compatible rather than creating parallel APIs.

## 2. Global API rules
Every new or changed V1 contract must define:
- authentication requirement
- request identity / idempotency semantics for writes
- explicit request and response types
- nullable vs absent fields
- pagination/cursor semantics where collections can grow
- freshness/provenance fields for operational or externally sourced facts
- stable machine-readable error code plus user-safe message mapping
- retry safety
- offline/cache policy
- analytics/evidence side effects
- deletion/correction propagation behavior
- authorization checks at the server, never only in UI

No API may infer a stronger evidence class from a weaker one simply because the client omitted context.

## 3. Shared error envelope
New/modernized endpoints should converge on a consistent shape conceptually equivalent to:
- `code`: stable machine-readable error identifier
- `message`: safe default message
- `details`: optional structured validation/context payload, never secrets
- `retryable`: explicit boolean where useful
- `request_id`: optional observability correlation identifier

Existing endpoint shapes may be normalized in `frontend/src/api/` while migration is in progress. Codex must not rewrite the entire backend solely for envelope consistency.

## 4. Authentication and authorization
- Read-only public discovery endpoints may remain anonymous where canon permits.
- Stateful personal mutations require authenticated identity.
- Every user-specific object enforces ownership/visibility server-side.
- Blocking/privacy changes are checked on reads as well as writes.
- Business/restaurant accounts never receive user-specific taste intelligence.
- Auth success does not imply social-profile setup is complete.

## 5. Contract A — Recommendation Request / Context
One shared conceptual request model serves Decision Session, Discovery, Search, Craves recommendation subset, and direct Map exploration. Surface-specific adapters may exist; semantics may not diverge.

Required conceptual fields:
- `surface`: canonical allowed value
- city/area context
- optional current location only when user permitted and needed
- time/context intent
- explicit query/semantic intent where relevant
- hard constraints
- soft constraints/modifiers
- novelty position/control
- candidate-source scope where relevant (e.g. Craves-only)
- session/request identifier
- pagination/show-more cursor where supported

Response must preserve:
- bounded ranked candidate set
- role/reason code appropriate to surface
- qualitative fit/confidence separately
- confidence basis / low-confidence state
- practical facts only when trustworthy
- provenance/freshness where facts depend on external data
- no star averages as recommendation framing

Map consumes this set; it does not reinterpret the scores.

## 6. Contract B — Decision Session
Preserve shipped Decision Session behavior and API value compatibility, including backend `best_fit` where already used. UI renders canonical role naming Best Fit / Safe Bet / Wildcard.

Must support:
- session/context persistence
- reject reason semantics
- regeneration/replacement
- direct correction after repeated full-set rejection
- chosen/committed place removal from active set
- low-confidence honest response
- successful “confident no” termination state

Idempotency: repeated client retry of the same rejection/commit action must not duplicate evidence.

## 7. Contract C — Search Interpretation
Backend capability required by Search contract:
- literal/exact-name detection
- semantic intent interpretation
- interpreted constraint list with source (`explicit_query`, `filter`, etc.)
- distinction between hard and soft constraints
- one named soft-relaxation proposal for zero results
- never relax dietary/allergy constraints
- bounded result batches

The client must be able to render/edit interpreted constraints without starting a separate chat flow.

## 8. Contract D — Visit Evidence
Visit evidence record must preserve tier:
- `declared`
- `verified`
- `inferred`

And source/provenance, timestamps at privacy-appropriate precision, related place, and correction/deletion status.

Rules:
- inferred-only never unlocks Rank eligibility;
- declared/verified may unlock Rank;
- any tier may be useful as factual/Craves graduation evidence only according to its consuming contract;
- visit proves experience, not preference.

## 9. Contract E — Taste Evidence / Correction
Evidence writes are typed events, not arbitrary score mutations.

Must preserve:
- signal class
- entity scope (restaurant/dish/etc.)
- valence/reason
- source surface
- confidence/evidence tier
- contextual vs long-term relevance
- created time
- retraction/correction relationship

Correction and deletion are distinct operations. Explicit correction outranks inference. Deleted/retracted evidence stops recommendation influence and derived intelligence is recomputed/invalidated according to canonical lifecycle rules.

## 10. Contract F — Rank
Rank Home requires:
- eligible visit queue (declared/verified only)
- current personal tier/list state
- comparison token/pair contract
- tie outcome
- “haven’t been to one” skip/data-integrity outcome
- completion/update result

Rank Comparison mutations must be idempotent and server-validated. Exact personal ranking remains private by default.

## 11. Contract G — Craves / Saves
Preserve Save as **interest**, not love.

Required operations:
- save
- unsave/remove
- list active Craves
- prioritized “makes sense now” subset via shared recommendation context
- closed/materially-changed factual flag
- optional source/provenance for imported/social-matched saves
- graduation state after visit evidence without silently deleting factual save history unless the product contract calls for state transition

Native/manual saves are evidence-equivalent unless explicit source metadata is needed for provenance/debugging.

## 12. Contract H — Place Detail Aggregation
Place Detail may be assembled from multiple endpoints, but the frontend must receive enough typed state to determine:
- relationship state (never visited / considering / visited / regular)
- saved state and saved reason where available
- recommendation entry framing
- qualitative fit + confidence
- trustworthy operational facts + freshness
- hero/media provenance
- menu/dish evidence + freshness
- social evidence source type
- restaurant-submitted vs organic content

Missing data is omitted, not synthesized.

## 13. Contract I — Dish Intelligence
V1 architecture treats dish as first-class even if full inference backend is incomplete.

Dish identity contract must support:
- stable dish ID where known
- restaurant parent ID
- normalized name + source menu record
- freshness/provenance
- optional media/evidence links
- independent user evidence/taste relationship from restaurant

Dish Rank remains out of V1.

## 14. Contract J — Native Posting / Private Logging
Create one shared write model with explicit outcome type rather than treating private log as merely a public post with `visibility=private`.

Required concepts:
- visit/group identifier
- restaurant confirmation
- optional dish confirmation
- media reference(s) according to visibility rules
- quick-take reaction
- optional caption
- explicit visibility
- occurred-at/backdate
- private-log vs native-post outcome
- companion/context metadata only when approved

Evidence is emitted only after successful publish/log commit. Editing/deleting recomputes/retracts derived evidence.

Uploads use deterministic media state (pending/uploaded/failed/removed); orphaned media cleanup must be defined.

## 15. Contract K — Social / Follow / Profile
Required semantics:
- follow or follow-request according to account privacy
- unfollow
- mute distinct from follow
- “do not use this person’s taste influence” distinct from mute
- block with immediate visibility revocation
- profile discoverability separate from sensitive content visibility
- other-user profile returns only fields allowed by viewer relationship/privacy state
- coarse Rank highlights only when owner opted in; never full exact list by default

Taste-similarity people recommendations remain OPEN and cannot be exposed through this API accidentally.

## 16. Contract L — Activity Inbox
Required event fields:
- stable event ID
- event type
- created time
- read state
- safe display payload
- destination descriptor
- actor/content references only if still visible to viewer
- optional action state

Read endpoints must re-enforce current privacy/block/delete state rather than trust historical payload visibility.

## 17. Contract M — Permissions / Privacy / Settings
Avoid a giant opaque settings blob for sensitive controls. Mutations must map to explicit fields/operations for:
- profile discoverability/private account
- post default visibility
- personalization pause
- current-session recommendation reset
- inferred-taste reset
- notification categories
- mute/block/taste-influence controls
- hidden restaurants where supported

OS permission state is client/device state and is not represented as if the backend granted it.

## 18. Contract N — Account Export / Deletion
Deletion:
- authenticated, explicit destructive operation
- deterministic success/failure
- failure leaves session/account intact
- success triggers canonical propagation and local sign-out/clear

Export:
- authenticated request
- explicit request/status/result lifecycle if asynchronous
- no fake completion
- safe delivery mechanism

## 19. Contract O — Anonymous Session Migration
One approved migration operation bridges anonymous evidence to authenticated identity.

Must define:
- which evidence classes are eligible
- deduplication key/idempotency token
- expiration
- conflict resolution
- no evidence-strength promotion
- hard-constraint handling
- failure recovery

Migration must be safe to retry.

## 20. Contract P — Operational Data / Provenance
Hours/open state, menu state, photos, restaurant-submitted facts, and external factual data include provenance/freshness sufficient for the UI to decide whether to display a current claim.

Fit confidence and factual completeness/freshness remain independent.

## 21. Contract Q — Recommendation Ledger / Analytics
Preserve existing recommendation-event infrastructure rather than replacing it casually.

Canonical recommendation-generating `surface` taxonomy remains the Data & State Map authority. Impressions occur only when actually exposed to the user, not merely fetched. Commercial evidence is never written as organic recommendation evidence.

## 22. Pagination and bounded sets
Search/Feed/social/activity endpoints that can grow use cursor-based or otherwise stable pagination. Decision surfaces intentionally return small bounded sets; “show more” is a deliberate continuation, not infinite entertainment scrolling.

## 23. Cache/offline policy
Each frontend API adapter declares one of:
- network-only
- cache-then-revalidate
- cache-safe with timestamp
- local-first mutation with deterministic reconciliation

Operational facts like open-now have stricter stale thresholds than menus/photos. No cache layer may present stale actionability as current.

## 24. API compatibility rules for Codex
Codex may:
- extend existing endpoints;
- add typed adapters;
- add new endpoints where no compatible contract exists;
- migrate gradually with compatibility shims.

Codex may not:
- create separate semantic models for Feed/Search/Map recommendations;
- invent evidence weights in UI/API adapters;
- widen auth/visibility defaults;
- silently change shipped API enum values that other code depends on;
- return fake fields to satisfy a screen;
- collapse operational confidence with taste confidence;
- use LLM output as unvalidated authorization, hard-constraint, or write authority.

## 25. API acceptance gate
Before any screen becomes implementation-GREEN:
1. every data read/write in its screen contract maps to an existing endpoint or named API task;
2. auth and authorization are explicit;
3. error/retry/idempotency semantics are explicit;
4. evidence side effects are explicit;
5. privacy/deletion behavior is explicit;
6. tests cover the happy path plus at least one denied/invalid/retry path for critical writes.

## 26. Traceability
This document is subordinate to the Data & State Map, Privacy/Permission Matrix, Evidence/Signal Hierarchy, Route & Flow Map, and approved Screen Contracts. When an API convenience conflicts with those artifacts, the API changes—not the product meaning.
