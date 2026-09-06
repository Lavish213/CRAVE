# Active agent state

Status: ready-for-review
Owner: Claude
Branch: claude/phase1-identity-isolation (PR #129 open against main)
Base SHA: 6e32ba4 (main)
Commit SHA: 06a1c84
Scope: Phase 1 of an 8-phase frontend production-hardening program (user-
directed) -- identity isolation only. Independent of PR #126, #127, #128
(all still open, no file overlap). Merge before starting Phase 2 (Search)
per explicit user direction -- avoid stacking dependent PRs without a
reason.
Locked files: none -- handoff complete.

## Outcome

Confirmed and fixed (not assumed) three real cross-account data-leak
paths and two real "stale identity still on screen with no loading
indicator" gaps, plus rebuilt useLocation.ts's internal contract:

- `authStore.signOut()` never cleared React Query's cache at all.
  `queryClient` moved out of `app/_layout.tsx` into `src/lib/queryClient.ts`
  so `authStore` can import and clear it without a circular import.
- `['myRankings']` (place/[id].tsx), `['friends-feed']` (friends-feed.tsx),
  and `['leaderboard','friends']` (leaderboard.tsx) carried no user.id --
  now `['myRankings', user?.id]` / `['friends-feed', user?.id]` /
  `['leaderboard', scope, scope==='friends' ? user?.id : null]`.
  `['leaderboard','global']` deliberately left unscoped -- not
  viewer-dependent data, "you" is highlighted client-side against the
  live authStore user, not the cached response.
- `profile.tsx` and `user/[id].tsx`: `loading` only ever flipped back to
  false from the *first* load's own `finally` -- a second `load()` fired
  by a real account switch / id change (not a remount, both screens stay
  mounted) never set it back to true, so the outgoing account's/person's
  profile+rankings rendered with zero loading indicator until the new
  fetch resolved. Both now reset (data + loading) immediately when
  user.id/id differs from what was last loaded, before the fetch starts.
- `taste-profile/[userId].tsx` and `useRecommendations.ts` were
  re-verified against the same claim and are already correct (taste-
  profile sets loading=true on every load(); useRecommendations clears
  its state synchronously on user.id change) -- left untouched.
- `useLocation.ts`: internal state was `UserLocation | null | undefined`
  collapsed to `UserLocation | null` at the public boundary, so "still
  resolving" was indistinguishable from "permission denied" was
  indistinguishable from "granted but the GPS read itself failed."
  Replaced with a real `useLocationStatus()`
  (`resolving|granted|denied|unavailable` + `coords` + `updatedAt`).
  `useLocation()` is now a thin, unchanged-signature wrapper over it --
  deliberate: audited all 5 real call sites (search.tsx, index.tsx,
  map.tsx, place/[id].tsx, ShareLinkSheet.tsx) and none branch on *why*
  a location is unavailable today, so none needed migrating. Future
  consumers that do (e.g. Phase 4's Add Spot permanent-denial -> Settings)
  should use `useLocationStatus()` directly.

Re-verified per explicit instruction, before touching anything --
deliberately NOT fixed here (none of these three files are in this
pass's locked scope):
- Search Retry (`search.tsx`): `onRetry={() => setDebouncedQuery(query)}`
  sets state to the value it already holds when the error fires --
  a no-op. `refetchSearch` is already destructured and correctly wired
  to pull-to-refresh two lines below; the retry button just isn't using
  it.
- Craves failure->empty (`craves.tsx`): `cravesError` is tracked and
  correctly rendered inside the list footer, but the top-level "true
  empty" gate (`saves.length===0 && craves.length===0 &&
  placeSaves.length===0 && !cravesLoading`) never checks it -- a
  craves-fetch failure with zero saves/placeSaves renders "Start your
  food memory" instead of the error. `placeSaves` has no error state
  tracked at all (separate, smaller gap, same class).
- Profile Setup (`profile-setup.tsx`): the username-availability check's
  `.catch()` collapses to `'idle'`, indistinguishable from "haven't
  typed a valid username yet," with no retry path (the debounce effect
  only reruns on text change).

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest` -> 338 passed, 34 suites (331 baseline + 7 new: sign-out
  cache-clear, two account-switch/id-change immediate-reset regression
  tests -- profile.tsx + user/[id].tsx -- and 4 useLocationStatus
  lifecycle tests covering resolving->granted, denied, unavailable, and
  denied->Settings->granted->foreground recovery).
- Manual re-audit of every claimed bug against current code before
  editing (see Outcome above) -- this is what turned up the two
  already-correct screens (taste-profile, useRecommendations) that got
  left alone, and the three genuinely-out-of-scope bugs recorded above
  instead of opportunistically fixed.

## Known gaps / risks

- `queryClient.clear()` is a blunt hard-reset -- every cached query
  (including public catalog data like feed/search/place/trending) is
  dropped on every sign-out, not just viewer-scoped ones. Correct per
  the user's explicit design note ("queryClient.clear() alone is not
  the solution... useful as a hard account-boundary cleanup" -- paired
  with per-key scoping, not instead of it), but means a sign-out costs
  a refetch of catalog data too. Not worth narrowing further without a
  reason to.
- No new automated coverage for `queryClient.clear()` actually being
  called with real query keys populated (the authStore test mocks the
  whole module and asserts `.clear()` was called once) -- an end-to-end
  "populate cache as A, sign out, sign in as B, assert zero A data
  anywhere" pass across multiple real screens would need a much heavier
  test harness; the per-screen regression tests above cover the same
  ground more cheaply per-screen.
- PR #129 open against main (see header). CodeRabbit's review returned 5 actionable findings, all verified against current code and all valid -- fixed in a follow-up commit:
  1. `STATE.md` itself had a stale "No PR opened yet" line contradicting the PR now recorded at the top -- fixed (this line).
  2. `profile.tsx`'s account-switch reset ran inside `load()`'s effect, one render after `user` itself changes -- a genuine single-render gap where the outgoing account's data could still paint. Added a render-time-derived `isStaleForCurrentUser` check (reads `loadedForUserIdRef` directly) so the skeleton gate no longer depends on the effect having fired yet.
  3. `friends-feed.tsx`/`leaderboard.tsx`: `enabled: !!user` (leaderboard: `scope !== 'friends' || !!user`) added to each query, **and** every focus/retry/refresh call site guarded too -- react-query's `refetch()` runs regardless of `enabled`, so the flag alone doesn't stop a manual trigger from firing a live request for a viewer-scoped surface while signed out.
  4. `user/[id].tsx`: `load()`'s stale-guard only tracked the viewed profile's `id`, not the viewer (`me?.id`) -- if the viewer's account changed while `isSelf` happened to evaluate the same both times (neither old nor new viewer is the profile owner), `load()` never got a new reference and stale follow/block state from the *previous* viewer kept rendering. Now tracks both. Applied the same render-time gate as profile.tsx here too, which surfaced its own bug: the ref that unlocks the gate was only ever set on a *successful* fetch, so any error (a 404 included) left the gate permanently stuck on the skeleton -- fixed by marking the id/viewer pairing "attempted" before the fetch settles, not only after it succeeds.
  5. `useLocation.ts`: a real bug in this PR's own rewrite, not a pre-existing one -- the foreground-recheck guard only special-cased `status === 'granted'`, dropping the old code's (incidental but load-bearing) protection against restarting a request that's still resolving. The permission dialog itself can trigger an AppState transition on some platforms while the very first request is in flight; without the fix, that would tear down and restart it. Fixed to also skip while `status` is still unresolved.
  - Verified: `npx tsc --noEmit` clean; `npx jest` 340/340 (34 suites -- 338 baseline + 2 new: a friends-feed signed-out-never-fetches test, a useLocation in-flight-request-not-restarted test).

## Next action

Review/merge this branch independently of #126/#127/#128. Then Phase 2
(per the user's 8-phase plan) is open to claim on a fresh branch: Search
as a proper discovery system, plus the three re-verified-but-unfixed
bugs above (Search Retry, Craves failure->empty, Profile Setup
availability handling) are natural first fixes there since they're
already fully diagnosed.
