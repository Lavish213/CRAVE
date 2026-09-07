# CRAVE Screen Contract — Cold Start / Onboarding

Status: **YELLOW — backend taste bootstrap and anonymous-to-account migration must be contracted**

## 1. Purpose
Cold start gets the user to a useful Feed as quickly as possible without pretending CRAVE already knows them and without forcing a long account setup sequence.

Canonical rule: **Onboarding is complete when the first usable Feed is available, not when CRAVE has collected every preference it could ask for.**

## 2. Product split
The shipped `profile-setup.tsx` currently combines identity setup language with social/leaderboard framing. Target V1 splits responsibilities:

1. **Food calibration** — pre-account, skippable except where the user chooses to disclose hard constraints.
2. **Identity setup** — username/display name only when account/social identity becomes necessary.

These are not one screen and should not be re-bundled.

## 3. User objective
Get a credible first set of recommendations with minimal effort and transparent confidence.

## 4. Entry points
- first app launch / no meaningful taste evidence
- explicit reset of inferred taste (returns to a learning state, not a new identity signup)
- optional re-calibration from Taste Profile later

## 5. Exit point
Feed / Decision Session with a usable candidate set and visibly lower confidence where evidence is still weak.

## 6. Required calibration inputs
### Hard-constraint capture
Offer direct disclosure for dietary/allergy constraints. Religious/ethical restrictions may be captured through the same constraint model where supported. These constraints are user-owned, editable later, and never inferred from silence.

### Novelty starting position
One lightweight choice establishing familiar-vs-exploratory starting posture.

### Known restaurant reactions
Ask for roughly 3–5 familiar restaurants and one structured reaction per restaurant:
- Loved it
- Good
- Not for me

Do not use Rank duels in onboarding.

### Optional cuisine affinity
At most 2–3 lightweight cuisine affinity taps. Skippable.

## 7. Explicitly prohibited direct questions
Do not directly calibrate price tolerance or travel willingness in onboarding. Those remain contextual/behaviorally inferred unless later explicitly set as constraints elsewhere.

## 8. Account boundary
Users may receive value before account creation. Account is required at the first truly stateful action that needs durable identity, including Save/Craves, Rank, or Post.

Anonymous calibration/session evidence may be retained locally/temporarily according to the Privacy Matrix and migrated only through the approved anonymous-to-account evidence contract after successful auth.

## 9. First viewport / sequencing
Prefer progressive calibration over a long wizard. The first step should explain why CRAVE is asking and make skipping obvious. The flow must be resumable and must never imply that optional answers are required.

Recommended conceptual order:
1. hard constraints
2. novelty starting point
3. known restaurant reactions
4. optional cuisine affinity
5. Feed

Identity/username setup occurs separately when needed.

## 10. Component tree
- onboarding frame/progress affordance (progress without gamification)
- hard-constraint selector
- novelty control
- known-place search/selector
- structured reaction control
- optional cuisine chips
- skip/continue actions
- error/offline state primitives

Reuse global Search/place lookup primitives where possible rather than building a separate restaurant directory.

## 11. Data reads
- city/area context when available
- known places search
- current anonymous calibration state
- existing hard constraints when re-entering after reset/recalibration

## 12. Data writes / evidence
- explicit hard constraints → hard constraint contract
- novelty choice → explicit preference/control signal
- known restaurant reaction → explicit structured taste evidence
- cuisine affinity → weak/moderate explicit bootstrap signal

Skipping a question creates no negative evidence.

## 13. Confidence rules
Cold-start recommendations may use defensible city-level/popularity baseline inputs only as fallback scaffolding; they must not be represented as personalized evidence. Confidence should be lower until personal evidence exists.

## 14. State Coverage Table
| State | Required behavior |
|---|---|
| First launch | Start lightweight calibration or allow skip to low-confidence Feed |
| Anonymous | Fully supported through calibration and Feed browsing |
| Authenticated with no taste | Same calibration semantics; persist directly to account |
| Returning partial calibration | Resume from saved safe checkpoint |
| Loading place search | Keep prior input visible |
| Place lookup empty | Allow another query/skip; never fabricate a place |
| Network error | Preserve entered answers and provide retry/skip where safe |
| Offline | Hard constraints/novelty can be stored locally; place-reaction steps may defer; Feed uses cached/limited mode if available |
| Constraint conflict | Surface clearly; do not silently relax |
| Reset inferred taste | Preserve factual history and hard constraints unless user separately changes/deletes them |

## 15. Identity setup contract
`profile-setup.tsx` remains the basis for username/display-name claiming, including availability checking and retry behavior, but its copy must no longer claim that identity is needed to “see how your taste stacks up” or imply public Rank. Identity setup is a social/account responsibility only.

## 16. Accessibility
All selection controls must expose selected state semantically. No visual-only progress. Large text must not force horizontal clipping. Constraint terminology must be plain and high-honesty.

## 17. Analytics
Measure completion/drop-off only to find friction, not to force completion. Skipping is a valid outcome. Onboarding optimization may not convert optional data collection into dark-pattern pressure.

## 18. Prohibited behavior
- mandatory account before first value
- mandatory optional cuisine/restaurant answers
- Rank duels during onboarding
- direct price/travel willingness calibration
- inferred allergy/dietary constraints from behavior
- fake personalization from city popularity
- bundling username/social setup back into food calibration
- treating skip as negative evidence

## 19. Codex implementation boundary
Codex may split the current profile-setup responsibility and build a calibration flow using approved contracts. Codex may not invent additional preference questions, silently increase required steps, or turn calibration into a long wizard.

## 20. Acceptance criteria
- first usable Feed reachable without creating an account
- only approved calibration categories appear
- all optional inputs are actually skippable
- hard constraints remain explicit and non-relaxable
- anonymous evidence migration is deterministic and tested
- username setup is separate from taste calibration
- reset-inferred-taste does not erase factual history

## 21. Traceability
Governed by Reconciliation Map, V1 Scope, Route & Flow Map, Data & State Map, Privacy/Permission Matrix, Evidence/Signal Hierarchy, Design System.

Forward dependencies: anonymous-session API/storage contract, taste bootstrap contract, auth recovery contract, Feed cold-start state tests.
