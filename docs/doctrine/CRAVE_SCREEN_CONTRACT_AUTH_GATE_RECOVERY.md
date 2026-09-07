# CRAVE Screen Contract — Auth Gate / Stateful Action Recovery

Status: **YELLOW — shared gate exists visually, centralized action-resume contract is not yet implemented**

## 1. Purpose
Authentication is a boundary around durable identity, not a wall in front of CRAVE’s basic value. When an anonymous user takes a stateful action, CRAVE should explain why sign-in is needed, authenticate, then **resume the exact intended action** without forcing the user to retrace their steps.

## 2. Canonical invariant
**Auth may interrupt a stateful action; it may not discard the user’s intent.**

## 3. Actions requiring auth in V1
At minimum:
- Save / add to Craves
- Rank
- Native public/follow-scope post
- durable private food log if account-backed persistence is required
- follow / follow-request response
- profile identity setup
- account/privacy lifecycle operations
- other explicitly account-owned actions in the Route & Flow Map

Browsing Feed, Search, Place Detail, and other read-only discovery value remains available before account creation where data permits.

## 4. Current-code reconciliation
`frontend/src/components/AuthSheet.tsx` already provides Apple/Google/email sign-in and reason-specific copy, but screens invoke it ad hoc and its reason vocabulary is incomplete. The missing system is not another auth UI; it is a **shared gate controller + resumable action envelope**.

Keep the existing authentication implementation unless a separate security/SDK issue requires change. Consolidate invocation semantics.

## 5. Required action envelope
Before opening auth, persist enough local in-memory/navigation-safe state to deterministically resume:
- action type
- target entity ID(s)
- source route/surface
- relevant state payload that is safe to persist briefly
- intended post-auth destination
- whether the action is idempotent
- expiration policy

Never store secrets, raw auth credentials, or unnecessary sensitive context in the resume envelope.

## 6. Recovery outcomes
### Successful auth
1. restore/merge anonymous evidence according to the approved migration contract;
2. revalidate target/action eligibility;
3. execute or reopen the exact intended action;
4. land the user in the correct success state.

### User cancels auth
Return to the prior screen with state intact. Cancellation is not an error and not negative taste evidence.

### Auth succeeds but target became invalid
Explain what changed; do not silently perform a different action.

### Auth failure
Keep original intent available for retry until the envelope expires or user abandons it.

## 7. Auth reasons
Reason copy may include: save, craves, rank, post/log, follow, profile/identity, add-spot, account/privacy, default. Copy explains the value/state being protected without claiming features that are private or OPEN.

Existing `profile` copy referring to seeing “how your taste stacks up” must not imply public Rank visibility.

## 8. Identity setup relationship
Successful account creation does not automatically mean username/social profile setup is required. If the resumed action does not require a public/social identity, do not insert profile setup as an unrelated blocker.

When username is required for the resumed action, route to identity setup and then resume afterward.

## 9. Anonymous evidence migration
Auth recovery must call one approved migration path. It may not duplicate anonymous evidence, promote weak evidence to stronger classes, or turn anonymous session context into permanent factual history beyond the Privacy/Evidence rules.

## 10. State Coverage Table
| State | Required behavior |
|---|---|
| Anonymous read-only | No gate |
| Anonymous stateful action | Capture intent → AuthSheet |
| Auth loading | Disable duplicate submissions; preserve intent |
| Auth success | Revalidate → migrate approved anonymous state → resume |
| Auth cancel | Return intact; no evidence mutation |
| Auth provider error | Actionable retry; intent retained |
| Email confirmation required | Explain next step; do not pretend action completed |
| Resume target deleted/closed | Explain; do not substitute silently |
| Duplicate callback | Idempotency prevents duplicate save/post/rank |
| Offline | If auth cannot complete, preserve safe short-lived intent and explain connectivity requirement |
| Expired resume envelope | Return to originating context with explicit message; never execute stale action |

## 11. Navigation behavior
Use one shared recovery mechanism rather than per-screen “after auth” branches. Deep links and modal dismissal must preserve source route state where possible.

## 12. Data writes / evidence
Authentication itself is not taste evidence. A stateful action emits evidence only after that action succeeds. Opening/canceling AuthSheet never counts as preference/rejection.

## 13. Privacy/security
- minimum resume payload
- short-lived where possible
- no credentials in app state
- revalidate permissions/visibility after auth
- blocking/privacy changes override stale intended access
- sign-out clears pending account-bound action state

## 14. Accessibility
AuthSheet focus must be trapped appropriately while open and returned to the triggering control after cancellation. Errors are announced. All provider/email actions retain 44pt targets.

## 15. Analytics
Track gate reason, auth completion/failure/cancel, and resume success for reliability. Do not optimize conversion by blocking more anonymous value than canon allows.

## 16. Prohibited behavior
- forcing auth before first discovery value
- dropping intended Save/Rank/Post after auth
- duplicate action execution from repeated callbacks
- treating cancel as dislike/negative evidence
- forcing social profile setup for unrelated account actions
- changing visibility defaults during auth
- silently escalating anonymous evidence strength

## 17. Codex implementation boundary
Codex should consolidate gate invocation and build deterministic resume semantics around the existing AuthSheet. It may not redesign authentication product policy or widen the set of actions requiring auth.

## 18. Acceptance criteria
- one reusable auth-gate API exists
- every V1 stateful action declares an auth requirement and resume handler
- Save/Rank/Post flows survive sign-in without retracing
- cancel returns intact
- duplicate callbacks are idempotent
- anonymous evidence migration is tested
- stale/invalid target is surfaced honestly

## 19. Traceability
Governed by V1 Scope, Route & Flow Map, Data & State Map, Privacy/Permission Matrix, Evidence/Signal Hierarchy, Component Registry.

Forward dependencies: API/Integration Contract, navigation migration plan, per-screen stateful action tests.
