# Profile / Taste / social cleanup defect log

Status: implementation verification in progress. This is a hardening record,
not a new screen contract. `CRAVE_FRONTEND_EXECUTION_ORDER.md` and the existing
Profile, Taste Profile, Other User Profile, privacy, and API contracts remain
controlling.

| Severity | Defect / gap | Root cause and evidence | Files | Status |
| --- | --- | --- | --- | --- |
| P0 | Public profiles exposed a full ordered Rank list with exact scores and tiers. | `GET /rankings/user/{id}` treated `UserProfile.is_public` as permission for sensitive Rank data, collapsing public identity and Rank visibility. Other User Profile fetched and rendered the response. | `backend/app/api/v1/routes/rankings.py`; `frontend/app/user/[id].tsx`; `frontend/src/api/social.ts` | Fixed: endpoint is owner-only; public UI exposes identity/relationship controls only. |
| P0 | Taste-derived data was public whenever the identity profile was public. | `GET /profile/{id}/taste` reused the identity `is_public` bit despite the privacy matrix requiring Taste Profile to be private by default and no coarse-share opt-in existing. | `backend/app/api/v1/routes/profile.py`; `frontend/app/taste-profile/[userId].tsx` | Fixed: owner-only on server and client; non-owner direct navigation performs no taste fetch. |
| P1 | Taste UI made competitive percentile and pairwise match-percentage claims without the approved sharing/confidence/correction boundary. | The aggregate service emitted a population percentile; the route appended cosine `match_score`; UI rendered both as definitive intelligence. | `backend/app/services/social/taste_profile_service.py`; `backend/app/api/v1/routes/profile.py`; `frontend/src/api/social.ts`; `frontend/app/taste-profile/[userId].tsx` | Fixed: fields removed from this contract/UI; factual aggregates remain and unsupported inference is labeled “Still learning.” |
| P1 | Profile centered follower/following and streak counters and linked directly to Leaderboard/Friends Feed. | The screen predated the food-identity/no-vanity and route-ownership contracts. | `frontend/app/(tabs)/profile.tsx` | Fixed: counters and legacy links removed; Profile now leads with a private, source-backed food-history summary and stable Rank Home/Taste navigation. |
| P1 | Standalone Leaderboard and Friends Feed remained reachable by direct route/API despite retirement/V1 scope. | Navigation cleanup had not propagated to compatibility boundaries. | `frontend/app/leaderboard.tsx`; `frontend/app/friends-feed.tsx`; `backend/app/api/v1/routes/leaderboard.py`; `backend/app/api/v1/routes/feed_social.py`; `frontend/app/_layout.tsx` | Fixed: old app routes redirect to canonical owners; old APIs return explicit HTTP 410 and no private payload. |
| P1 | Signed-out Follow tried viewer-scoped relationship reads and had no preserved auth intent; failed Follow writes reverted silently. | Public-profile viewing and authenticated relationship actions were coupled in one load path; optimistic write rollback had no visible error. | `frontend/app/user/[id].tsx` | Fixed: anonymous reads skip relationship APIs; Follow uses shared PendingIntent auth gate; failures revert and alert. Backend Follow remains idempotent. |
| P2 | Profile Setup still said handles control leaderboard appearance. | Stale pre-doctrine onboarding copy. | `frontend/app/profile-setup.tsx` | Fixed: copy describes optional discoverable identity and explicitly separates private food/Taste data. |
| P2 | Avatar upload API exists but no current app surface invokes it. | The client helper is presently unused; there is no user-visible mutation flow to harden without inventing UI. | `frontend/src/api/social.ts`; `backend/app/api/v1/routes/profile.py` | Deferred: no production behavior changed; a future avatar editor must validate upload ownership and surface PUT/PATCH failures atomically. |
| P2 | Full inferred-trait Taste model, corrections, and three personalization lifecycle controls are unavailable. | Decision Architecture Gate 2 and the explicit settings operations have not landed. Fabricating traits or one generic reset would violate doctrine. | `docs/doctrine/CRAVE_SCREEN_CONTRACT_TASTE_PROFILE.md`; `docs/doctrine/CRAVE_SCREEN_CONTRACT_SETTINGS_PRIVACY.md` | Deferred by named dependency; UI honestly remains “Still learning.” |
| P2 | Offline queued Follow writes are not implemented. | Existing Follow API is online-only; introducing a durable mutation queue is a new shared social system outside this cleanup. | `frontend/src/api/social.ts`; `frontend/app/user/[id].tsx` | Deferred: online failure is explicit and rollback-safe; idempotency is server-enforced. |

## Re-verification results

- Stale Profile Setup leaderboard copy: confirmed on current `main`; fixed.
- Public-profile backend privacy boundaries: identity was gated, but Taste and
  full Rank were coupled to public identity; fixed server-side.
- Taste percentile conflict: confirmed; competitive percentile and match
  percentage removed from the Profile/Taste contract.
- Friends Feed legacy remnants: Profile entry and standalone route/API were
  still active; retired with compatibility handoffs, without changing Feed.
- Leaderboard conflict: global/friends vanity surface and API were still active;
  isolated outside V1 without reviving or redesigning it.
