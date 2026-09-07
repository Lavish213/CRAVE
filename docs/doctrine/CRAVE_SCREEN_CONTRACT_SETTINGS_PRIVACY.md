# CRAVE Screen Contract — Settings / Privacy Controls

Status: **YELLOW — current Settings exists, but required privacy/taste controls are incomplete**

## 1. Purpose
Settings is the control surface for account, permissions, privacy, personalization lifecycle, notifications, and app-level preferences. It must make CRAVE’s data behavior inspectable and controllable without collapsing distinct operations into one vague “reset” or “privacy” button.

## 2. User objective
Understand and change what CRAVE collects, uses, shows, retains, and sends.

## 3. Entry points
- Profile → Settings
- permission/degraded-mode prompts may deep-link to the relevant subsection
- account/privacy lifecycle links from legal/support surfaces

## 4. Current-code reconciliation
`frontend/app/settings.tsx` currently covers city, notifications, legal links, feedback, sign-out, and account deletion. It is a useful shell but is not yet the canonical privacy/control surface.

Target V1 must add the controls already locked in the Privacy Matrix and Taste Profile doctrine while preserving clear separation between:
- app permission state
- content visibility
- recommendation influence
- factual retention
- personalization pause/reset
- inferred-taste reset
- account deletion/export

## 5. Information hierarchy
Recommended sections:
1. **Personalization**
2. **Privacy & Visibility**
3. **Permissions**
4. **Notifications**
5. **Blocked / Hidden**
6. **Account & Data**
7. **App / Legal / Support**

City selection belongs to context/location settings or Profile/app preferences; it must not imply precise-location collection.

## 6. Personalization controls
Expose three distinct operations with explicit consequences:

### Pause personalization
Stops new recommendation influence/active personalization behavior according to the Data/Privacy contract. Does not delete history.

### Reset current recommendations/session
Clears current recommendation/session context only. Does not delete historical evidence or inferred taste.

### Reset inferred taste
Deletes/resets derived/inferred taste state while preserving factual food history and explicit hard constraints unless the user separately changes/deletes them.

Never use one generic “Reset CRAVE” action.

## 7. Privacy & visibility controls
Where V1 capability exists:
- profile discoverability
- default native-post visibility
- visibility of coarse Rank highlights if that opt-in feature is enabled
- specific restaurant hiding from public food identity
- private account setting
- any approved follow/privacy scope controls

Rank, Craves, Taste Profile, and never-posted visit history remain private by default.

## 8. Permissions
Show current status and recovery path for:
- location
- camera
- microphone
- contacts
- notifications

CRAVE should explain why each permission is used and the degraded fallback. It must not repeatedly nag after denial or make core discovery unusable without optional permissions.

No background location control should appear unless CRAVE actually introduces an approved background-location feature; current canon prohibits collection by default.

## 9. Notifications
Separate OS permission from CRAVE category preferences. Categories should support the approved notification taxonomy, with low-priority/followed-post activity generally in-app or off for push by default.

OS denial does not disable Activity Inbox.

## 10. Blocked / hidden controls
- blocked users list and unblock action
- muted users if supported
- “do not use this person’s taste to influence mine” state distinct from mute
- hidden restaurants / excluded public-identity places where supported

Unblocking does not silently restore historical visibility beyond current privacy rules.

## 11. Account & data lifecycle
- export account data
- delete account
- sign out
- correction/deletion explanation where appropriate

Account deletion must remain visually and semantically distinct from Sign Out and must trigger full approved deletion propagation. A successful deletion clears local account state. Failed deletion must not sign the user out and pretend completion.

## 12. State Coverage Table
| State | Required behavior |
|---|---|
| Anonymous | App/legal/permission settings available; account-only sections omitted or sign-in-gated clearly |
| Authenticated | Full applicable controls |
| Loading preference state | Keep section shell stable; do not show guessed toggles |
| Save/update in progress | Disable duplicate writes; optimistic updates only when rollback is safe |
| Update failure | Revert or show unresolved state; never display false success |
| OS permission granted | Show enabled + manage path |
| OS permission denied | Show denied + Settings path + degraded fallback |
| OS permission unavailable | Show unavailable, non-actionable |
| Offline | Local-only settings may change; server-owned privacy settings queue only if semantics guarantee safe reconciliation, otherwise require connection |
| Export pending | Show deterministic state; no fake completion |
| Delete failure | Keep authenticated session and explain retry |

## 13. Data reads
- account identity
- privacy/visibility preferences
- personalization state
- block/mute/hidden entities
- notification category prefs
- OS permission status
- app/build/legal metadata

## 14. Data writes
Each control maps to one explicit mutation contract. No “settings blob” mutation that silently changes unrelated privacy fields.

## 15. Privacy invariant enforcement
Settings UI must never widen defaults during migration. Missing server data resolves to the most privacy-preserving approved default, not the most permissive.

## 16. Accessibility
Toggles expose label, value, consequence, and disabled/loading state. Destructive actions require clear confirmation. Large text and screen-reader navigation must preserve section structure.

## 17. Analytics
Log control-operation success/failure for reliability, with minimal sensitive detail. Do not log raw values of sensitive constraints or exact blocked-user lists into analytics.

## 18. Visual rules
Calm utility design. Destructive actions isolated in a Danger Zone. Privacy explanations use plain language. Avoid giant legal text dumps inside Settings; link to detail when needed.

## 19. Prohibited behavior
- one ambiguous reset button
- public-by-default Rank/Craves/Taste Profile
- hidden expansion of permissions
- repeated permission nagging
- sign-out on failed account deletion
- a UI toggle that changes both visibility and recommendation influence unless canon explicitly defines it
- businesses receiving user-specific taste data through any settings path

## 20. Codex implementation boundary
Codex may extend the current Settings shell and wire approved controls. It may not invent new collection categories, privacy defaults, or data-retention semantics.

## 21. Acceptance criteria
- three personalization lifecycle actions are separately named and implemented
- OS permission and app preference are distinct
- privacy defaults match canonical matrix
- account deletion/export have deterministic error/success states
- block/mute/taste-influence distinctions are preserved
- denied permission always leaves a usable fallback

## 22. Traceability
Governed by Privacy/Permission Matrix, Evidence/Signal Hierarchy, Data & State Map, Taste Profile contract, V1 Scope, Design System.

Forward dependencies: privacy/settings API contracts, deletion/export implementation, permissions deep-link tests, accessibility tests.
