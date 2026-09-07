# CRAVE Screen Contract — Activity Inbox

Status: **GREEN candidate — net-new screen, no unresolved product decision**

## 1. Purpose
Activity is CRAVE’s event inbox. It surfaces relevant social/account/product events without becoming a feed, vanity center, or engagement loop.

## 2. User objective
Quickly understand what changed and take the single relevant next action.

## 3. Entry points
- header activity icon from approved top-level surfaces
- push notification deep link
- internal event completion handoff

Activity is not a bottom tab.

## 4. Exit points
Each item deep-links to its authoritative destination: Place Detail, profile/follow request, Shared Craves later, reservation event destination, moderation/submission status, or relevant settings.

## 5. First viewport
Chronological, compact event list with unread distinction that does not rely on color alone. Highest-value/actionable events may be grouped ahead of passive informational events, but there is no popularity ranking and no infinite-attention design.

## 6. Event classes for V1
Allowed where underlying capability exists:
- private-account follow request
- ordinary followed-person posting activity (primarily in-app; push usually off by default)
- private reaction summary, with reactor identity hidden where canon requires anonymity
- Rank reminder after eligible visit
- saved restaurant reopening / materially relevant operational event
- reservation event if/when integration exists
- user-submitted media/place moderation status where current product already emits it
- account/security notices when appropriate

Later-only features remain later even if an Activity renderer could technically display them.

## 7. Component tree
- screen header
- event group/date section
- ActivityRow (CREATE shared primitive)
- optional action button
- empty/error state primitives

ActivityRow must support icon/semantic type, primary copy, timestamp/approximate recency, unread state, optional thumbnail, and destination action.

## 8. States
- anonymous
- authenticated loading
- success with unread/read mix
- empty
- partial data
- stale item destination
- offline cached list
- network error
- blocked/deleted actor/content

## 9. State Coverage Table
| State | Required behavior |
|---|---|
| Anonymous | No private inbox; show sign-in explanation only if user deliberately opens Activity |
| Authenticated | Load user-specific event stream |
| Loading | Skeleton/compact progress without fake rows |
| Success | Actionable event rows |
| Empty | “Nothing needs your attention” style state; no engagement bait |
| Partial | Render safe copy without exposing missing/private actor details |
| Offline | Cached events may display with stale indicator; unsafe actions retry when online |
| Error | Retry same fetch |
| Blocked actor | Existing visible access revoked; row degrades/removes according to privacy lifecycle |
| Deleted content | Do not dead-link; show unavailable/removal state or remove event |

## 10. Interaction rules
- tap row → authoritative destination
- approve/deny follow request may be inline only if backend operation is deterministic and reversible/clear
- mark-read is product bookkeeping, not taste evidence
- no likes, streaks, unread-pressure badges designed to maximize return frequency

## 11. Data reads
- authenticated activity events
- minimal actor/content preview data allowed by current privacy state
- destination availability

## 12. Data writes / evidence
- read/unread state
- explicit event action such as follow-request response
- no recommendation preference evidence from merely opening Activity or an event

## 13. Privacy
Activity must enforce current visibility at render time, not merely trust historical event payloads. Blocking, deletion, private-account changes, and content-visibility changes revoke access to stale previews.

Private “made me crave this” reactions remain anonymous to the poster; Activity may summarize counts/occurrence only if allowed by the privacy matrix and never expose reactor identity.

## 14. Notifications relationship
Push is a transport, Activity is the durable in-app inbox. Push denial must not remove Activity. Low-priority events are batched/in-app by default. No generic “come back” notifications.

## 15. Accessibility
Rows are individually labeled with event type + actor/context + time + action. Unread state has a semantic label in addition to styling. Swipe-only actions are prohibited.

## 16. Analytics
Measure delivery/open/action correctness, not dwell. No success KPI based on notification-open rate independent of user value.

## 17. Visual rules
Calm utility surface. Compact rows, restrained thumbnails, no social vanity counters, no entertainment-feed card stack.

## 18. Prohibited behavior
- Activity as a content feed
- infinite-scroll engagement optimization
- public reaction counts/status games
- identity leak for anonymous private reactions
- stale preview bypassing block/delete/privacy changes
- creating recommendation evidence from notification/activity opens

## 19. Codex implementation boundary
Codex may implement only event types supported by approved backend/event contracts. It may not invent placeholder event semantics or activate later/open product classes because the row component supports them.

## 20. Acceptance criteria
- new Activity route exists and is not a tab
- signed-out state is explicit
- every event resolves to a valid destination or safe unavailable state
- block/delete changes revoke stale content exposure
- push-off users retain complete in-app Activity behavior
- reaction anonymity preserved

## 21. Traceability
Governed by V1 Scope, Route & Flow Map, Privacy/Permission Matrix, Evidence/Signal Hierarchy, Design System, Component Registry.

Forward dependencies: Activity API contract, notification/event taxonomy, header entry-point tasks, deep-link tests.
