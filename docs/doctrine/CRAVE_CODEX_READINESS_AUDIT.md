# CRAVE Final Codex Readiness Audit

Status: **CONDITIONALLY READY — product ambiguity substantially closed; merge/baseline convergence remains the final operational gate**

## 1. Executive verdict
CRAVE is no longer blocked by broad product-definition ambiguity. The canonical chain now defines scope, navigation, flows, data semantics, privacy, evidence, visual grammar, components, screen behavior, API boundaries, implementation rules, traceability, and migration order.

Codex may begin **controlled implementation/unblocker work** once the canon is present on the implementation base. Full broad screen authority requires the merge/baseline gates in §8.

## 2. Status interpretation
- **GREEN**: no unresolved product decision and no prerequisite that must be built first.
- **YELLOW — IMPLEMENTATION DEPENDENCY**: product meaning is resolved; Codex may work on the named dependency or screen in the prescribed migration wave, but should not fake the missing capability.
- **RED**: unresolved product decision; implementation prohibited.

A YELLOW implementation dependency is not permission for Codex to invent product semantics.

## 3. Screen readiness
| Screen | Status | Named blocker / note |
|---|---|---|
| Place Detail | YELLOW | dish intelligence capability, real taste graph, trustworthy hours/open ingestion for gated sections |
| Feed / Decision Session | YELLOW | literal shared recommendation contract, Craves rail sourcing, dish/taste capability for evidence-gated sections, friends-feed migration |
| Search | YELLOW | semantic constraint-interpretation backend contract/capability |
| Craves | GREEN candidate | core behavior fully specified; existing data foundations available |
| Rank Home | YELLOW | atomic ownership migration with Profile + eligible visit queue integration |
| Rank Comparison | GREEN candidate | narrow existing mechanic; tie and “haven’t been” additions only |
| Native Posting / Private Logging | YELLOW | composer/posting write contract and dish identification capability |
| Profile | YELLOW | atomic Rank ownership migration |
| Taste Profile | YELLOW | real taste graph is substantive prerequisite |
| Other User Profile | YELLOW | privacy decision resolved in canon: full Rank private; implementation still depends on approved coarse-highlight/compatibility data |
| Contextual Map | YELLOW | navigation ownership + shared candidate-set plumbing migration |
| Activity Inbox | GREEN candidate | net-new screen; event API implementation needed but product semantics are complete |
| Cold Start / Onboarding | YELLOW | anonymous bootstrap/migration + taste bootstrap APIs |
| Auth Gate / Recovery | YELLOW | centralized resumable-action controller not yet implemented |
| Settings / Privacy Controls | YELLOW | explicit privacy/personalization/account lifecycle mutations incomplete |

There are **no RED V1-required screens** in this audit.

## 4. OPEN features that remain intentionally blocked
These are not blockers for V1 Codex work because they are outside implementation authority:
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

Codex must not “complete” them while working nearby.

## 5. Cross-cutting readiness
| Area | Status | Notes |
|---|---|---|
| V1 scope | GREEN | explicit status vocabulary and launch boundary |
| target routes/navigation | GREEN contract | migration still required |
| route/flow behavior | GREEN contract | 14 flows and ownership matrix |
| data/state semantics | GREEN contract | shared domains locked |
| privacy/permissions | GREEN contract | 36 classes/actions + degraded modes |
| evidence/signal hierarchy | GREEN contract | 21 classes + negative evidence + firewall |
| design system | GREEN contract | tokens preserved; typography gap closed |
| component registry | GREEN contract | existing inventory classified; net-new primitives named |
| screen contracts | GREEN/YELLOW mix | no RED V1 screen |
| API/integration boundaries | GREEN contract | implementation endpoints/tasks may still be built |
| Codex rules v2 | GREEN | implementation constitution |
| traceability | GREEN | requirements mapped to verification targets |
| migration plan | GREEN | ordered ownership/deep-link/cache/analytics migration |
| canonical index | GREEN | single “start here” entry point |

## 6. Known implementation landmines explicitly contained
The following are no longer invisible:
- Map currently exists as a tab and owns independent fetch/ranking-like behavior.
- Rank list currently lives in Profile.
- `friends-feed` is temporary migration scaffolding.
- `profile-setup` old copy references leaderboard/taste exposure inconsistent with target privacy framing.
- AuthSheet is invoked ad hoc and lacks action-resume orchestration.
- Leaderboard has duplicated ranked-row presentation and remains AUDIT REQUIRED.
- `TrendingStrip` is dormant and may not be resurrected as a generic trending rail.
- `record-video` / `add-spot` are precursors, not final composer architecture.
- Place Detail must omit unavailable evidence instead of fabricating modules.
- existing full Other User Profile Rank exposure must be pulled back to privacy-safe behavior.

Each now has a canonical owner or explicit prohibition.

## 7. Release-defect preservation
PR #146 or equivalent fixes must be in the implementation base. Redesign work must not regress:
1. Rank retry re-fetches.
2. recording failure is user-visible.
3. signed-out Friends leaderboard is an auth state, not false empty.
4. Delete Account remains visually distinct and safely confirmed.

## 8. Final operational gates before broad Codex authority
### Gate A — Canon convergence
Merge/stack the canonical PR chain so the implementation base contains all governing artifacts. Do not point Codex at old `main` that lacks them.

### Gate B — Conflict audit
After merge, search for superseded navigation/product claims in README/docs/comments and annotate/remove them when they could mislead implementation.

### Gate C — Baseline CI
On the exact starting commit:
- frontend TypeScript clean
- frontend tests green
- backend tests/static checks green
- no known broken route/deep-link baseline hidden by redesign work

### Gate D — Implementation task selection
Start with GREEN screens or explicit YELLOW unblockers according to Migration Plan. Do not issue one unconstrained “rebuild the whole app” prompt.

When A–D pass, CRAVE is **CODEX READY**.

## 9. Recommended first Codex execution order
1. shared foundations (types, auth resume, Decision Strip, API adapters)
2. Rank Comparison (GREEN)
3. Craves (GREEN)
4. Rank Home + Profile ownership migration
5. navigation topology
6. Feed / Decision Session
7. Search + Contextual Map
8. Place Detail reconciliation
9. Native Posting / Private Logging
10. Profile/Taste/Other Profile
11. Activity
12. Cold Start / Auth finalization / Settings privacy controls

This order may be adjusted for engineering dependency, but product ownership boundaries may not.

## 10. Stop conditions during implementation
Codex must stop the affected branch of work and surface a decision if it encounters:
- a V1-required behavior with no canonical meaning
- conflicting privacy/evidence rules not resolvable by authority order
- a backend limitation that would require changing product meaning rather than degraded behavior
- a proposed migration that would reinterpret existing user data
- a need to expose an OPEN feature to make another screen work

## 11. Final verdict
**Product definition: READY.**

**Implementation governance: READY.**

**Repository operational state: READY AFTER canonical PR convergence + baseline CI.**

There is no remaining large planning artifact required before Codex. New documentation should be created only when implementation reveals a genuinely new durable contract or contradiction.
