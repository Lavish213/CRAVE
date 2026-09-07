# CRAVE Final Codex Readiness Audit

Status: **CODEX READY — canonical product definition and implementation governance are converged; Waves 0–2 are complete**

## 1. Executive verdict
CRAVE is ready for broad, controlled Codex implementation beginning at Migration Plan **Wave 3 — navigation topology**.

The canonical chain defines scope, navigation, flows, data semantics, privacy, evidence, visual grammar, components, screen behavior, API boundaries, implementation rules, traceability, and migration order. There are no RED V1-required screens and no remaining pre-Codex product fork that must be silently resolved.

Waves 0–2 are implementation baseline, not work for Codex to repeat:
- Wave 0: protected release baseline / #146 invariants.
- Wave 1: shared foundations merged in PR #170.
- Wave 2: visit evidence + Rank ownership merged in PR #172.

`CRAVE_CODEX_HANDOFF_STATE.md` records the concrete handoff boundary.

## 2. Status interpretation
- **GREEN**: product meaning is resolved and required prerequisites for that surface are present.
- **YELLOW — IMPLEMENTATION DEPENDENCY**: product meaning is resolved; Codex may implement the named dependency/surface in its prescribed wave but must not fake unavailable capability.
- **RED**: unresolved product decision; implementation prohibited.

A YELLOW implementation dependency is implementation work, not permission to invent semantics.

## 3. Screen readiness
| Screen | Status | Named blocker / note |
|---|---|---|
| Place Detail | YELLOW | dish intelligence capability, real taste graph, trustworthy operational-data ingestion for evidence-gated sections |
| Feed / Decision Session | YELLOW | shared recommendation integration, Craves rail sourcing, dish/taste capability for evidence-gated sections, friends-feed migration |
| Search | YELLOW | semantic constraint-interpretation backend capability |
| Craves | GREEN | core behavior fully specified; existing data foundations available |
| Rank Home | GREEN | ownership migration, visit queue, evidence tiers, and presentation mapping implemented in Wave 2 |
| Rank Comparison | GREEN | existing mechanic protected; #146 retry behavior preserved |
| Native Posting / Private Logging | YELLOW | composer/posting write contract implementation and dish identification capability |
| Profile | GREEN for Rank ownership | full Rank ownership removed; compact Rank status/link is the canonical boundary; broader identity/taste migration continues in its later wave |
| Taste Profile | YELLOW | real taste graph is substantive implementation prerequisite |
| Other User Profile | YELLOW | privacy meaning resolved; coarse-highlight/compatibility implementation remains |
| Contextual Map | YELLOW | Wave 3 navigation ownership + later shared candidate-set plumbing |
| Activity Inbox | GREEN contract / implementation pending | event inbox semantics complete; screen/API implementation belongs to later wave |
| Cold Start / Onboarding | YELLOW | anonymous bootstrap/migration + taste bootstrap APIs |
| Auth Gate / Recovery | GREEN foundation | centralized resumable auth gate implemented in Wave 1; call-site migration continues with affected screens |
| Settings / Privacy Controls | YELLOW | explicit privacy/personalization/account lifecycle mutations remain implementation work |

There are **no RED V1-required screens**.

## 4. Completed cross-cutting foundations
### Wave 1 / PR #170
- named typography roles
- shared Decision Strip / reason presentation
- centralized resumable auth-gate host/store
- reusable protected-action path
- shared recommendation-context types
- explicit privacy-axis primitives
- visit-evidence eligibility primitives
- Activity row/shared UI foundations

### Wave 2 / PR #172
- persisted `declared | verified | inferred` visit evidence
- independent factual-history vs recommendation-influence semantics
- existing explicit saved-place visit memory preserved as declared evidence
- inferred-only evidence excluded from Rank eligibility
- authenticated Rank queue excluding already-ranked places
- Rank Home owns ranking task/list
- Profile no longer owns the full ranked list
- deterministic Rank presentation mapping (`Elite | Love | Good`) without rewriting persisted `liked | fine | disliked` evidence
- `disliked` excluded from ordered Rank

## 5. OPEN features that remain intentionally blocked
These are not blockers for V1 implementation and must not be silently pulled into nearby work:
- visible social Rank beyond opt-in coarse highlights
- taste-similarity people recommendation feed
- imported “Seen on social” dedicated Place Detail placement
- standalone Leaderboard final fate (AUDIT REQUIRED)
- Shared Craves implementation
- Dish Rank
- voice Search
- full route-aware discovery
- personal food-history map
- full reservation/ordering integrations

## 6. Cross-cutting readiness
| Area | Status | Notes |
|---|---|---|
| V1 scope | GREEN | explicit status vocabulary and launch boundary |
| target routes/navigation | GREEN contract | Wave 3 implementation begins here |
| route/flow behavior | GREEN contract | 14 flows and ownership matrix |
| data/state semantics | GREEN contract | shared domains locked; visit evidence now implemented |
| privacy/permissions | GREEN contract | 36 classes/actions + degraded modes |
| evidence/signal hierarchy | GREEN contract | 21 classes + negative evidence + contamination firewall |
| design system | GREEN | token system preserved; typography roles implemented |
| component registry | GREEN contract | existing inventory classified; Wave 1 primitives established |
| screen contracts | GREEN/YELLOW implementation mix | no RED V1 screen |
| API/integration boundaries | GREEN contract | remaining endpoint work belongs to prescribed waves |
| Codex rules v2 | GREEN | implementation constitution |
| traceability | GREEN | requirements mapped to verification targets |
| migration plan | GREEN | Waves 0–2 complete; Wave 3 is next |
| canonical index | GREEN | single START HERE entry point |
| Rank presentation semantics | GREEN | canonical deterministic mapping added during Wave 2 |
| Codex handoff state | GREEN candidate | exact completed-wave boundary documented |

## 7. Known implementation landmines now visible
Codex must preserve these boundaries while executing later waves:
- Map is still currently a tab until Wave 3 migrates ownership; target canon says contextual route only.
- `friends-feed` is temporary migration scaffolding, not final IA.
- `profile-setup` still contains legacy responsibilities that must split according to onboarding canon.
- Leaderboard remains AUDIT REQUIRED and cannot become a proxy for social preference ranking.
- `TrendingStrip` must not be resurrected as a raw popularity rail.
- `record-video` / `add-spot` are precursors, not the final posting/logging architecture.
- Place Detail must omit unavailable evidence instead of fabricating modules.
- Other User Profile must not expose full personal Rank by default.
- Existing Rank evidence must not be rewritten merely to satisfy presentation changes.

## 8. Release-defect preservation
The #146 invariants remain hard regression gates:
1. Rank retry re-fetches.
2. recording failure is user-visible.
3. signed-out Friends leaderboard is an auth state, not false empty.
4. Delete Account remains visually distinct and safely confirmed.

## 9. Operational gates
### Gate A — Canon convergence: PASSED
Canonical PR chain is on main, including Rank presentation semantics and the Codex handoff boundary.

### Gate B — Conflict visibility: PASSED FOR HANDOFF
Known stale route/product claims are explicitly quarantined by the canonical index, migration plan, and this audit. Later wave migrations must remove/update stale implementation comments and tests as ownership changes.

### Gate C — Baseline CI: PASSED FOR WAVES 0–2
Wave 2 PR verification passed:
- frontend TypeScript
- frontend full Jest suite
- backend full suite
- real Postgres full migration chain
- newest migration downgrade/re-upgrade
- single Alembic head
- dependency vulnerability audit
- conflict-marker guard
- CodeQL JavaScript/TypeScript and Python

The exact final handoff commit must retain these checks green after this docs-only convergence change.

### Gate D — Implementation task selection: PASSED
Codex begins with Migration Plan **Wave 3**, not an unconstrained app rebuild.

## 10. Codex execution order from here
1. **Wave 3 — navigation topology**
2. Feed / Decision Session integration
3. Search
4. Craves + Contextual Map plumbing
5. Place Detail reconciliation
6. Native Posting / Private Logging
7. Profile / Taste / Other User Profile social-personalization work
8. Activity Inbox
9. Cold Start / remaining auth call-site migration / Settings privacy controls
10. cleanup, legacy-route retirement, final V1 QA

The migration plan is authoritative if its wave labels/order are more specific than this summary.

## 11. Stop conditions during implementation
Codex must stop the affected branch of work and surface the decision if it encounters:
- a V1-required behavior with no canonical meaning
- conflicting privacy/evidence rules not resolvable by authority order
- a backend limitation requiring product-meaning changes rather than degraded behavior
- a migration that would reinterpret existing user data
- a need to expose an OPEN feature to make another screen work
- a need to weaken hard constraints or inferred-visit protections

## 12. Final verdict
**Product definition: READY.**

**Implementation governance: READY.**

**Waves 0–2 baseline: READY.**

**Broad Codex authority: READY beginning at Wave 3, subject only to the final handoff commit remaining CI-green.**

There is no remaining large planning artifact required before Codex. New documentation should be created only when implementation reveals a genuinely new durable contract or contradiction.
