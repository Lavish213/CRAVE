# CRAVE Requirements / Traceability Matrix

Status: **CANONICAL TRACEABILITY INDEX**

## 1. Purpose
This matrix ensures every durable V1 requirement has an implementation owner and test destination. A requirement is not complete because it exists in doctrine; it must trace through screen/data/API/component implementation and verification.

Legend:
- **GREEN** = product meaning resolved; implementation may proceed when API/dependency exists.
- **YELLOW** = product meaning resolved but named implementation/data dependency remains.
- **RED** = unresolved product decision; Codex may not implement.

## 2. Core constitutional requirements
| Requirement | Canon source | Primary surfaces | Data/API owner | Verification |
|---|---|---|---|---|
| Decision confidence over engagement/conversion | Master doctrine / V1 Scope | Feed, Search, Place Detail | recommendation contracts | no dwell/virality ranking tests; visual QA |
| Evidence integrity | Evidence Hierarchy | all recommendation/evidence surfaces | taste evidence, ledger | evidence-class unit/integration tests |
| Personal taste private by default | Privacy Matrix | Rank, Craves, Taste Profile, Profile | privacy/profile APIs | authorization/privacy tests |
| No paid influence in personalized recommendations | V1 Scope / Evidence firewall | Feed/Search/Map/Craves | recommendation pipeline | commercial-source exclusion tests |
| No star-average framing | doctrine/design system | Feed/Search/Place Detail | presentation only | snapshot/semantic UI QA |

## 3. Navigation and ownership
| Requirement | Screen contract | Implementation owner | Dependency | Test |
|---|---|---|---|---|
| Five tabs: Feed/Search/Craves/Rank/Profile | Route & Flow / registry | root tab layout | migration plan | route topology test |
| Map contextual only | Contextual Map | navigation + map route | candidate-set plumbing | deep-link/tab test |
| Rank first-class tab | Rank Home | rank route + profile migration | rank API | route/state ownership test |
| `+` action for log/post | Native Posting | root shell/composer | posting API | action/deep-link test |
| Activity header/inbox | Activity | header + activity route | activity API | route/deep-link test |

## 4. Feed / Decision Session
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| Decision Session dominates first viewport | Feed contract | PlaceCard + Decision Session API | visual/ordering test |
| persistent context chip | Feed | context component / request context | interaction test |
| at most one question before recommendation | Feed / Decision Session | session engine | session integration test |
| low confidence labeled honestly | Feed | Reason/Decision Strip | low-confidence fixture |
| after two full-set rejections ask what is wrong | Feed | Decision Session API | state-machine test |
| commit removes chosen place from active set | Feed | Decision Session API | mutation/idempotency test |
| direct taste-extension, hole-in-wall, Craves rails | Feed | shared recommendation request | sourcing test |
| no raw trending/popularity rails | Feed | recommendation pipeline | exclusion test |

## 5. Search
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| single-digit default results | Search | Search Interpretation / recommendation API | result-count contract test |
| editable semantic interpretation | Search | interpreted constraint chip | parser/edit test |
| exact-name jump | Search | place search API | navigation test |
| hard dietary exclusions | Search | constraint contract | safety test |
| one smallest soft relaxation on zero result | Search | search interpretation | zero-result test |
| Search reason language distinct from Decision Session | Search/Design System | reason renderer | content test |
| Map uses same result set 1:1 | Search + Map | candidate-set handoff | equality test |

## 6. Craves
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| prioritized “makes sense now” subset before full pool | Craves | recommendation context + saves | ordering test |
| Save means interest, not love | Evidence Hierarchy | save event | evidence test |
| Want to Try/Tried adapts from visit evidence | Craves | visit evidence | state transition test |
| confirmed-loved visit graduates toward Rank | Craves/Rank | visit + taste evidence | integration test |
| untouched saves may decay in influence but persist factually | Craves/Evidence | save lifecycle | decay semantics test |
| closed/changed place gets factual warning | Craves | operational data | stale/closed fixture |

## 7. Rank
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| eligible queue leads Rank Home | Rank Home | rank queue API | first-viewport test |
| only declared/verified visits unlock queue | Rank Home / Evidence | visit evidence | authorization/eligibility test |
| inferred-only prompts confirmation instead | Rank Home | visit confirmation flow | negative eligibility test |
| comparison only, no manual placement | Rank Comparison | rank API | mutation surface test |
| ties are honest | Rank Comparison | comparison outcome | tie test |
| “Not for me” excluded from ordered tiers | Rank Home | evidence/tier query | list exclusion test |
| exact Rank private by default | Rank/Profile privacy | social/profile API | privacy test |

## 8. Place Detail
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| relationship-aware hierarchy | Place Detail | detail aggregation | four-state visual/state tests |
| trustworthy minimum data | Place Detail | place/operational API | missing-data test |
| typography-led fallback without trustworthy image | Place Detail | hero | media-absence visual test |
| qualitative fit + confidence separated | Place Detail | Decision Strip | content/data-shape test |
| Why This Fits + correction | Place Detail | reason block + taste correction API | correction test |
| adaptive CTA by relationship/context | Place Detail | CTA resolver | relationship-state test |
| Menu For You only with real dish evidence | Place Detail | dish/menu API | evidence-gate test |
| confident “no” is success | Place Detail / flow map | action outcome | analytics/flow test |

## 9. Posting / private logging
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| log and post are distinct outcomes | Native Posting | composer + posting API | payload-type test |
| public/follow-scope post requires media | Native Posting | composer validation | visibility/media test |
| private log works without media | Native Posting | composer | fallback test |
| explicit visibility choice | Native Posting | visibility control | default/choice test |
| multi-dish units grouped by visit | posting/data contract | posting API | payload test |
| edit/delete recomputes/retracts evidence | posting/evidence | evidence pipeline | lifecycle test |
| no autoplay vertical feed | social/Design System | media renderer | UI QA |

## 10. Social / profiles
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| Follow graph only, no Friend graph | Profile/Other Profile | follows API | terminology/data test |
| mute separate from taste influence | Other Profile/Settings | social settings API | independent-control test |
| no vanity counts | Profile/Other Profile | presentation | snapshot QA |
| full Rank not public by default | Other Profile | profile API | field-authorization test |
| compatibility display only on deliberate other-profile navigation | Other Profile | compatibility API | surface-scoping test |
| no DMs/comments/reposts | V1 Scope | n/a | route/component absence audit |

## 11. Taste Profile
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| confident traits only; uncertain “still learning” | Taste Profile | taste graph | confidence-state test |
| explicit correction actions | Taste Profile | correction API | precedence test |
| correction outranks inference | Evidence Hierarchy | taste pipeline | conflict-resolution test |
| three lifecycle controls remain distinct | Taste Profile/Settings | settings API | action semantics test |
| hard constraints never silently relaxed | Taste Profile/Search/Feed | constraint engine | safety regression |

## 12. Map
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| bounded 5–10 pin default | Contextual Map | map renderer | fixture/render test |
| no auto refresh on pan | Contextual Map | map state | interaction test |
| explicit Search this area | Contextual Map | request context | request test |
| location denial → Choose an area | Contextual Map | permission fallback | denied-permission test |
| list-equivalent accessibility path | Contextual Map | map/list UI | accessibility test |
| no sponsored pins | Map/Evidence firewall | recommendation pipeline | exclusion test |

## 13. Cold start / auth
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| value before account | Cold Start/Auth | routing | anonymous journey test |
| hard constraints + novelty + 3–5 known reactions | Cold Start | bootstrap API | payload test |
| no direct price/travel question | Cold Start | UI | screen audit |
| skip creates no negative evidence | Cold Start | evidence pipeline | evidence test |
| stateful action resumes after auth | Auth Gate | resume controller | Save/Rank/Post auth tests |
| auth cancel preserves intent/state | Auth Gate | controller | cancel test |

## 14. Activity / notifications
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| Activity exists even with push denied | Activity | activity API | permission-denied test |
| private reaction identity remains hidden | Activity/Privacy | activity API | privacy test |
| no generic re-engagement push | Notifications | notification service | event taxonomy audit |
| low-priority activity batched/in-app | Notifications | notification preferences | preference test |

## 15. Settings/privacy
| Requirement | Owner | Component/API | Verification |
|---|---|---|---|
| visibility / influence / retention remain separate | Settings/Privacy | explicit mutations | contract test |
| pause personalization ≠ reset session ≠ reset inferred taste | Settings/Taste Profile | settings API | three-action test |
| deleted/retracted evidence stops influence | Privacy/Evidence | lifecycle pipeline | propagation test |
| blocking revokes prior access | Settings/Social | authorization | block regression |
| account deletion failure leaves session active | Settings | account API | failure test |
| denied permission never dead-ends | Settings + affected screen | OS permission handling | denied-state tests |

## 16. Operational/provenance requirements
| Requirement | Owner | Verification |
|---|---|---|
| hours/open status only when trustworthy/current enough | operational data / Place Detail | stale-hours fixture |
| menu/photo provenance/freshness preserved | menu/media APIs | provenance contract test |
| restaurant-submitted facts visually distinguished where needed | Place Detail | content-source fixture |
| external commercial content never becomes recommendation influence | evidence firewall | pipeline test |

## 17. Open / prohibited traceability
The following remain non-implementable unless canon changes:
- visible social Rank beyond explicitly opted-in coarse highlights
- taste-similarity people recommendation feed
- imported “Seen on social” dedicated Place Detail placement
- standalone Leaderboard until AUDIT REQUIRED status is resolved
- Shared Craves V1 implementation
- Dish Rank
- voice Search
- full in-house reservations/ordering
- route-aware discovery beyond architecture hooks

Codex must treat absence of a design for these items as intentional, not as a gap to fill.

## 18. Traceability completion rule
A feature cannot be marked implementation-complete until its row has:
1. a code owner/file set;
2. API/data mapping;
3. regression test mapping;
4. no unresolved OPEN dependency;
5. visual/accessibility QA where user-facing.

If implementation introduces a durable requirement not represented here, promote it into canon before relying on it as precedent.

## 19. Wave 1 implementation evidence
Wave 1 shared foundations were implemented under Issue #169 / PR #170. This table makes the earlier requirement rows concrete without claiming downstream screens are complete.

| Foundation requirement | Production implementation | Regression verification | Status |
|---|---|---|---|
| Canonical typography roles | `frontend/src/constants/colors.ts` (`Typography`) | protected frontend typecheck + full Jest suite | GREEN foundation |
| Shared qualitative reasoning with confidence separate from fit | `frontend/src/components/DecisionStrip.tsx`; consumed by `frontend/src/components/PlaceCard.tsx` | `frontend/src/components/DecisionStrip.test.tsx`; existing Feed tests | GREEN foundation |
| Shared recommendation request/context semantics | `frontend/src/api/recommendationContext.ts`; Decision Session adapter in `frontend/src/api/decisionSession.ts` | `frontend/src/api/recommendationContext.test.ts`; existing `decisionSession.test.ts` | GREEN foundation |
| Hard/soft constraints remain distinct | `frontend/src/api/recommendationContext.ts` | `frontend/src/api/recommendationContext.test.ts` | GREEN foundation |
| Declared/verified-only Rank eligibility | `frontend/src/types/evidence.ts` | `frontend/src/types/evidence.test.ts` | GREEN foundation |
| Visit evidence does not imply preference | `frontend/src/types/evidence.ts` | `frontend/src/types/evidence.test.ts` | GREEN foundation |
| Visibility / recommendation influence / factual retention remain independent | `frontend/src/types/privacyContracts.ts` | `frontend/src/types/privacyContracts.test.ts` | GREEN foundation |
| Stateful action survives auth interruption and resumes after revalidation | `frontend/src/stores/authGateStore.ts`; `frontend/src/hooks/useAuthAction.ts`; `frontend/src/components/AuthGateHost.tsx`; root mount in `frontend/app/_layout.tsx` | `frontend/src/stores/authGateStore.test.ts`; root-layout regression suite | GREEN foundation |
| Auth cancel does not execute pending stateful action | `frontend/src/stores/authGateStore.ts` | `frontend/src/stores/authGateStore.test.ts` | GREEN foundation |
| Account boundary clears pending resume intent | `frontend/src/stores/authStore.ts` | auth-store regression suite + protected full Jest run | GREEN foundation |
| Shared Activity event primitive exists without implementing the Activity screen early | `frontend/src/components/ActivityRow.tsx` | protected frontend typecheck/full Jest; Activity screen-specific tests remain Wave 10 | GREEN foundation |
| #146 release-defect behaviors survive Wave 1 | unchanged Rank retry, record-video feedback, Leaderboard auth state, Settings danger-zone implementations | existing `rank-place`, `record-video`, `leaderboard`, and `settings` suites all pass in protected full Jest | GREEN preserved |

Wave 1 GREEN means the reusable contract/primitives are implementation-ready. It does **not** promote any downstream YELLOW screen to GREEN until that screen's own contract, API dependency, state coverage, and visual/accessibility acceptance criteria are satisfied.