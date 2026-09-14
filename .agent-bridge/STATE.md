# Active agent state

Status: implementing
Owner: Claude
Branch: claude/frontend-architecture-fixes
Base SHA: 755a722 (origin/main tip after PR #301)
Scope: four independently-verified engineering-audit findings, frontend only:
(1) `usePrefetchPlace.ts`'s prefetch queryKey didn't match Place Detail's real
`foundationQueryKey` cache key, wasting every prefetch-on-tap; (2) three
duplicated ad-hoc error classifiers (`errorMessage.ts`, `cravesStore.ts`'s
`_classifyError`, `place/[id].tsx`'s inline copy) plus `activity.tsx`'s
hardcoded error string, consolidated to delegate to the already-built,
already-tested `foundationGate.ts` taxonomy; (3) `authGateStore.ts`'s
`resume`-after-sign-in contract is fully built/tested but every real call site
no-ops it -- wiring real `resume` closures for the two highest-value cases
(Save on `place/[id].tsx`, Rank on `rank/[placeId].tsx`), leaving the other 4
call sites (`activity.tsx`, `rank-home.tsx`, `user/[id].tsx`,
`PlaceVideoGallery.tsx`) as deliberately-deferred no-ops; (4) four screens'
inline FlashList `renderItem` closures defeat `PlaceCard`/`PlaceCardCompact`'s
`React.memo` -- hoisting with `useCallback` in `(tabs)/index.tsx`,
`(tabs)/craves.tsx`, `SearchScreen.tsx`, `activity.tsx`.
Locked files: `frontend/src/hooks/usePrefetchPlace.ts`,
`frontend/src/utils/errorMessage.ts`, `frontend/src/stores/cravesStore.ts`,
`frontend/src/stores/authGateStore.ts`, `frontend/app/place/[id].tsx`,
`frontend/app/rank/[placeId].tsx`, `frontend/app/activity.tsx`,
`frontend/app/(tabs)/index.tsx`, `frontend/app/(tabs)/craves.tsx`,
`frontend/src/screens/SearchScreen.tsx`, plus each touched file's own test.
Verification plan: `npx tsc --noEmit` clean, `npx jest --ci` fully green
(frontend only -- no backend touched), read own diff before opening the PR.
Explicit exclusions: backend, the other 4 auth-gate call sites' `resume` wiring
(left as documented no-ops), any Rank/Search/Craves screen contract redesign
beyond what each fix specifically requires.

---

Status: ready-for-review
Owner: Codex
Branch: codex/menu-source-governance
Base SHA: 474dec5
Commit SHA: 5066076
Scope: Menu source governance after the 10-place canary. Add a provider/source
classification layer so protected providers like Toast/ChowNow/Cloudflare pages
are treated as access/governance states instead of parser failures; document the
manual/verified menu path for owner/user contribution without inventing fake
provider access. Follow-up audit also preserves manual-menu evidence fields,
latest source failure reasons, and internal image source/provenance metadata so
menu/photo population can be reviewed instead of guessed.
Locked files: .agent-bridge/STATE.md, backend/app/services/menu/**,
backend/scripts/**menu**, backend/tests/**menu**, backend/app/db/models/**,
backend/app/services/images/materialize_image_truth.py,
backend/alembic/versions/e3f4g5h6i7j8_add_menu_governance_audit_fields.py,
docs/**menu** if needed.
Verification: inspected current menu source/manual submission routes; added
focused unit coverage for the source classifier/failure taxonomy; confirmed
Toast/ChowNow are typed `provider_api_required` blocks, Square Site remains a
direct public source, and the legacy MenuOrchestrator path no longer fetches
provider-access-required URLs. Added `menu_sources.last_failure_at/reason`,
manual submission evidence fields, and internal `place_images` source metadata
for third-party attribution/provenance. `python3 -m pytest
backend/tests/test_menu_source_governance.py backend/tests/test_menu_submissions.py
backend/tests/test_image_ingest_service.py -q` -> 24 passed, 1 warning.
`python3 -m compileall -q backend/app/services/menu backend/app/services/images
backend/app/api/v1/routes/menu_submissions.py backend/app/db/models
backend/scripts/run_menu_backlog_canary.py` -> passed. `cd backend && python3
-m alembic heads` -> `e3f4g5h6i7j8 (head)`. `git diff --check` -> passed.
Explicit exclusions: official Toast/ChowNow/Square OAuth/API integrations,
paid provider traffic, production canaries, frontend screen redesign, and any
credential or dashboard work.

---

Status: merged (partially load-bearing -- see gap below)
Owner: Claude
Branch: claude/universal-link-setup (merged, can be deleted)
Base SHA: 85440b9 (origin/main tip after PR #297)
Commit SHA: 8825b81 (PR #298, squash-merged)
Scope: user asked to do the universal-link (https://) setup. Found the
client-side half already existed and was already wired up --
`app.json`'s `applinks:crave.app`/Android `intentFilters`, and
`foundationGate.ts`'s `placeUniversalLink()` contract already used by
Place Detail's share button. The actual missing half was server-side:
- New `backend/app/api/v1/routes/universal_links.py`, mounted at the
  domain root (no `/api` prefix, matching `health.py`'s own pattern):
  `GET /.well-known/apple-app-site-association`,
  `GET /.well-known/assetlinks.json`, and real branded HTML fallback
  pages at `GET /place/{id}`, `/rank/{id}`, `/user/{id}` for anyone
  who taps a link without the app installed. `/user/{id}` reuses
  `profile.py`'s own `is_public` gate before showing any name --
  never leaks what the app itself won't show post-#266's privacy
  retirement.
- Found and fixed a real inconsistency while wiring this up:
  `PlaceCard`'s long-press share (every card, Feed/Search/Craves) sent
  plain text with no link at all, unlike Place Detail's own share
  button. Now uses the same `placeUniversalLink()`/`Platform.OS` split.
- **Genuinely not fixable from this session**: both verification
  files ship with placeholder Apple Team ID / Android SHA-256
  fingerprint. User confirmed neither value is stored in the repo and
  EAS could not reach Expo to retrieve them from this environment --
  independently confirmed here too: `curl https://api.expo.dev` gets a
  403 from this sandbox's own egress proxy (org policy), and
  `eas whoami` reports not logged in. **Until the real values are
  substituted in `universal_links.py`'s `_APPLE_TEAM_ID`/
  `_ANDROID_SHA256_FINGERPRINT` constants, neither OS will actually
  verify the domain** -- a tapped link silently falls through to the
  web fallback page instead of opening the app, with no visible error
  anywhere. Get them via Apple Developer > Membership (or
  `eas credentials -p ios`) and `cd frontend && eas credentials
  --platform android` (Play Console App Signing key fingerprint, not
  the upload-key one, once Play App Signing is enabled).
Locked files: none -- closed for the code half; the two placeholder
constants are the one remaining blocker before this is load-bearing.
Verification: backend `python -m compileall`/`import app.main` clean,
`pytest -q` -> 1139 passed, 2 skipped (8 new). Frontend
`npx tsc --noEmit` clean, `npx jest --ci` -> 59/59 suites, 556/556
tests (1 new).
Next action: handed off to Codex, 2026-09-13 -- see
`claude-to-codex.md`'s `H-20260913-eas-credentials-for-universal-links`
entry for the full retrieval steps (this sandbox has no EAS/Expo
network access at all -- confirmed, not a login issue alone). Once
whoever has real access supplies the real Team ID and SHA-256
fingerprint, swap them into the two constants at the top of
`universal_links.py` and push -- a one-line-each change, no other code
affected. After that, DNS needs to actually point crave.app at the
Railway deploy (user's own infra, not something any agent session can
do), and a real on-device tap-through test on both platforms is the
only way to confirm the whole chain works end to end.

---

Status: merged
Owner: Claude
Branch: claude/misc-cleanup-followups, claude/reduced-motion-accessibility,
claude/design-log-round-2 (all merged, can be deleted)
Base SHA: 3116e4e (origin/main tip after PR #147, itself merged this pass)
Commit SHA: 3116e4e (#147), 320a182 (#295), 3b43521 (#296)
Scope: user asked "so whts left to do" / "wht can u do rn" -- worked
through the concrete, code-doable items from that list (repo-only,
no Railway/Supabase/device access):
- **Four stale pre-session PRs resolved**: #128 was already merged
  (place-issue reporting shipped weeks ago, list was stale). #127 and
  #145 are closed and fully superseded -- verified their actual content
  (camera-failure toast, "Rate CRAVE" removal, old STATE.md SHAs) is
  already independently in `main` or long obsolete; nothing to port.
  #147 (Design Exploration Log Round 2 entry) was still genuinely open
  and still accurate -- its "PROMOTE Decision Session" call matches
  exactly what Feed's real Decision Session became -- verified a clean
  local test-merge against current main before merging for real.
- **Craves save-row reason_role/reason_source "gap" investigated,
  confirmed not a bug**: `place/[id].tsx`'s `savedEntry` already reads
  from the same `useCravesStore().saves` array the plain save row
  iterates, and its fallback chain already reads
  `savedEntry?.reason_role`/`reason_source` before ever needing URL
  params -- only the reasoned-card row (no persisted saves-store entry)
  actually needs them. No code change.
- **`cravesStore._classifyError` consolidated** (PR #295, `320a182`):
  now delegates to the shared `errorMessageFor` for every status except
  401 (kept as the `'auth_required'` sentinel `craves.tsx` checks for
  specially) instead of hand-duplicating the 429/offline copy.
- **Map direct-mode ranking investigated, left as a documented tradeoff,
  not touched**: confirmed `fetch_places_for_map` still orders by plain
  `Place.rank_score` (the Wave 5 audit's flagged gap). Real reason it's
  not a drop-in `rank_feed()` fix: that function expects full `Place`
  ORM objects and applies category-diversity-window truncation sized
  for a ~40-item curated feed; Map's query is a deliberate lightweight
  column-projection fetching up to 1000 pins (a documented prior
  production-timeout fix depends on staying lightweight), and Map's job
  is to show everything nearby spatially, not a diversified top-N. The
  only real-world effect is which pins get cut when a bounding box
  exceeds 1000 candidates. Flagged to the user as a judgment call, not
  fixed unilaterally -- no user decision yet, so left as-is.
- **Reduced Motion support added** (PR #296, `3b43521`): new shared
  `useReducedMotion()` hook (wraps `AccessibilityInfo.
  isReduceMotionEnabled()` + `reduceMotionChanged`), wired into the
  three real continuous/bouncy motion sites
  `RUNBOOK_ACCESSIBILITY_CERTIFICATION.md` itself named as never
  checked anywhere in the app: `SkeletonCard`'s infinite shimmer loop
  (now a static mid-opacity placeholder), `MapBottomSheet`'s
  `Animated.spring(bounciness: 4)` release/terminate snap-back (now a
  plain ~120ms timing, no bounce), `PlaceCard`'s save-button scale-pop
  (now skipped entirely). Toast's and Feed's plain opacity fades were
  deliberately left alone -- Reduce Motion targets bounce/parallax/zoom,
  not a one-shot fade.
- **Icon-only accessibility-label audit (background agent)**: searched
  every `TouchableOpacity`/`Pressable` in `frontend/app` and
  `frontend/src/components` (54 files) rendering only an Ionicons icon
  with no visible text. All 20 such controls already have a correct
  `accessibilityLabel`. Genuinely nothing to fix -- confirmed strength,
  not a gap.
Locked files: none -- closed.
Verification: each item verified independently before merging (see each
PR's own description for exact `tsc`/`jest` numbers) -- all green, no
regressions across the batch.
Next action: the remaining accessibility-runbook items (focus order,
state announcements, contrast on-device, Dynamic Type clipping, VoiceOver/
TalkBack label phrasing) genuinely require a physical device with a
screen reader enabled -- cannot be completed from this sandbox. Map's
direct-mode ranking fix needs a user decision (accept the narrow
edge-case gap vs. a real query/perf rework) before anyone touches it.

---

Status: merged
Owner: Claude
Branch: claude/core5-mockup-search-map (merged, can be deleted)
Base SHA: 2588e34 (origin/main tip after PR #292)
Commit SHA: 51625a5 (PR #293, squash-merged)
Scope: follow-up to the Home/Settings Core 5 mockup pass (PR #291) --
user explicitly asked to do "the Search/Map mockup screens too,"
superseding the Search/Map certification lock in
`CRAVE_FRONTEND_EXECUTION_ORDER.md` for this one narrow visual-restyle
purpose only. No ranking/interpretation/query/IA change of any kind;
the full Search/Map regression suite (search.test.tsx, search-decision-
support.test.tsx, map.test.tsx, map-instrumentation.test.tsx,
legal-and-map-web.test.tsx) passed unchanged, confirming nothing
behavioral moved.
- Found Search/Map already implement most of the mockup's pill/badge
  visual language from earlier Wave 5/V1.5 work
  (`constraintChip`/`scopeChip`/`shortcutChip`, the map's "Search this
  area" banner -- all already `Radius.pill`) -- so the real gap was
  small.
- `SearchScreen.tsx`: the "UNDERSTOOD"/"CHECK THIS SEARCH"
  interpretation label was the one remaining bare-caps text on the
  screen -- wrapped in a rounded pill chip (`chipActiveBg`/
  `chipActiveText`), matching Home's `decisionEyebrowChip`. Zero-state
  "What are you craving?" heading -> shared `Typography.headline` role
  (was a one-off 17px/800 inline style).
- `MapBottomSheet.tsx`: selected-place name -> `Typography.subtitle`
  (was a one-off 16px/700 inline style) -- a proportionate lift for a
  compact sheet, not the full `headline` weight Home/Search's own
  headers use.
- Not touched: `PlaceCard`/`PlaceCardCompact` (shared, already
  token-consistent), the already-pill-styled map banners, any ranking/
  interpretation/query logic, and "Results" (the mockup's Results
  screen is Search's own populated state, not a separate component).
- Still not attempted anywhere in this Core 5 mockup arc: the mockup's
  literal cream/light color scheme (would fragment the app visually
  across screens; every screen stays on the dark UI V2 palette), real
  food photography (no asset pipeline exists).
Locked files: none -- closed.
Verification: `npx tsc --noEmit` clean. `npx jest --ci` -> 57/57
suites, 552/552 tests, no assertions needed updating. CI green (Guard,
Frontend, both Backend jobs, both Analyze jobs, CodeQL); CodeRabbit
rate-limited this time (not a blocker -- same standing as every other
rate-limited CodeRabbit pass this session).
Next action: none from me. All five Core 5 mockup screens (Home,
Search, Results, Map, Settings) are now covered -- Results via Search's
own populated state, no separate work needed. If the user wants the
mockup's literal light/cream theme pursued at some point, that is a
much larger, separate, explicit undertaking (all screens at once, to
avoid a half-migrated look) -- not started here.

---

Status: merged
Owner: Claude
Branch: claude/core5-mockup-home-settings (merged, can be deleted)
Base SHA: a8f463f (origin/main tip after PR #289)
Commit SHA: 804abbc (PR #291, squash-merged)
Scope: user asked to "implement mock screens" from
`docs/design/CRAVE_CORE_5_SCREEN_MOCKUPS.md` (a warmer/premium/food-photo-led
direction across Home/Search/Results/Map/Settings, explicitly marked "not
Penpot implementation-ready"). Clarified scope with the user directly since
Search/Map/Results are locked/certified in
`CRAVE_FRONTEND_EXECUTION_ORDER.md` and the mockup's own light/cream palette
would clash with the app's shipped dark UI V2 theme if applied to only two
screens:
- Only Home ((tabs)/index.tsx) and Settings (settings.tsx) touched --
  user confirmed these are the two NOT under the Search/Map lock.
- Home: user explicitly chose "visual restyle only, keep all
  functionality" over matching the mockup's much simpler literal layout
  (one craving prompt + one hero card + a small grid) -- the real Home
  tab has a contract-backed Decision Session (Best Fit/Safe Bet/Wildcard)
  plus a multi-section discovery feed built earlier this session, and
  matching the mockup literally would have meant hiding/removing that
  real functionality. Restyled only: the "DECISION SESSION" eyebrow is
  now a rounded pill chip (`Colors.chipActiveBg`/`chipActiveText`)
  instead of bare caps text, and the heading uses the shared
  `Typography.headline` role instead of a one-off inline size.
- Settings: header restyled from a plain "CRAVE" wordmark + small
  tagline to the mockup's actual two-line hierarchy -- small "SETTINGS"
  eyebrow + bold "Make CRAVE fit you." headline, via `Typography.headline`.
  Did NOT add the mockup's "Dietary & allergies" preferences row -- no
  such settings screen exists yet (dietary handling lives in Search's
  interpreter/FilterSheet only), so it would have been a dead control.
- Did NOT attempt the mockup's literal cream/light theme -- flipping
  just two screens to light while the rest of the app (Search/Map/
  Craves/Rank/Profile/Place Detail) stays dark UI V2 would read as a
  broken half-migrated app when switching tabs. Kept the existing dark
  token system, pulled over only the typographic hierarchy and pill/
  badge visual language.
Locked files: none -- closed.
Verification: `npx tsc --noEmit` clean. `npx jest --ci` -> 57/57 suites,
552/552 tests, no assertions needed updating. CI green (Guard, Frontend,
both Backend jobs, both Analyze jobs, CodeQL); CodeRabbit actually ran
this time (not rate-limited) -- zero actionable comments, only a
docstring-coverage nudge this repo has never acted on for simple render
helpers (consistent with every prior PR this session).
Next action: none from me. The other four Core 5 mockup screens
(Search, Results, Map) remain untouched by design -- certified/locked;
revisit only with a new, proven, documented contract gap per doctrine,
or explicit user direction to supersede the lock.

---

Status: merged
Owner: Claude
Branch: claude/craves-propagation-289 (merged, can be deleted)
Base SHA: 4525a81 (origin/main tip after PR #288)
Commit SHA: a8f463f (PR #289, squash-merged)
Scope: Craves is next in `CRAVE_FRONTEND_EXECUTION_ORDER.md`'s locked
order. User said "finish craves" directly. Confirmed via fresh
`git fetch`/`git branch -a`/PR listing/`git log --all -- frontend/app/
(tabs)/craves.tsx` that nothing from Codex's separately-relayed live
Craves session ever reached `origin` -- proceeded as a propagation-only
pass (no redesign) against Codex's own relayed audit checklist.
- Fixed `useCravesReasoned.ts`: ad-hoc `['craves-reasoned', ...]` query
  key / magic-number staleTime / no cancellation -> `foundationQueryKey`
  (`scope:'user', entity:'cravesReasoned'`), `STALE_TIME.normal` (an
  exact match for the old `2*60*1000`), `AbortSignal` threaded through
  a new `fetchCravesReasoned({..., signal})` param -- same pattern as
  `rank-home.tsx`'s `fetchRankQueue`.
- Fixed `craves.tsx`'s `cravesError`/`placeSavesError`: were plain
  booleans rendering hardcoded generic copy, unlike the store's own
  already-classified `savesError`. Now `string | null` via the shared
  `errorMessageFor` taxonomy.
- Fixed a real, previously-unread `degraded` flag: `fetchCravesReasoned`
  already returned `degraded: true` on malformed backend data, but
  `craves.tsx` never checked it anywhere -- Feed's Decision Session
  (`(tabs)/index.tsx`) surfaces this exact flag as a confidence-drop
  subheading; Craves silently didn't. Threaded through the
  `reasoned-header` row, reused Feed's copy verbatim.
- Audited `cravesStore.ts` (saves list + save/remove mutations)
  independently against the full checklist -- account-generation
  guards, per-place mutation tokens, offline-queue idempotency with
  account-scoped flush on retry, no swallowed failures -- already meets
  the doctrine bar. No changes made; would have been unscoped rewrite
  risk with no confirmed gap.
Locked files: none -- closed.
Verification: `npx tsc --noEmit` clean. `npx jest --ci` -> 57/57 suites,
552/552 tests (2 pre-existing `craves.test.tsx` assertions updated to
match the now-correct classified copy against a mocked plain
`Error('network')`; 1 new test for the degraded-subheading behavior).
Backend untouched.
Next action: none from me. Next in the locked order after Craves is
Rank/Food Evidence/Profile-Taste/Auth-Settings-Activity propagation --
already done this session (PRs #262/#263/#264/#266/#267, see the
matching top entry below). With Craves also closed, every named slice
through "Auth/Settings/Activity completion" in
`CRAVE_FRONTEND_EXECUTION_ORDER.md`'s locked order is now merged; the
next stage is cross-app accessibility/E2E/release certification --
not started, needs explicit user direction before claiming.

---

Status: merged
Owner: Claude
Branch: claude/rebase-rank-262, claude/fix-rank-262-test,
claude/rebase-fe-263, claude/rebase-share-264 (+v3), claude/fix-share-264-review-findings,
claude/rebase-profile-266 (+v2/v3/v4), claude/rebase-auth-267 (all merged, can be deleted)
Base SHA: a6bd34d (origin/main tip after PR #287)
Scope: the five remaining stale, unmerged Codex branches from before the
"finish stranded branches" pass (H-20260913-finish-stranded-search-map-and-feed-branches,
same top entry pattern below) -- Rank (#262), Food Evidence/Add Spot (#263),
social-share loop (#264), Profile/Taste social hardening (#266), and
Auth/Settings/Activity (#267). All five were opened well before today's
merges and needed the same rebase-in-a-scratch-worktree treatment; #266
in particular needed re-rebasing three more times as each of the other
four merged out from under it (each merge touched a file it also touched).
- **#262 Rank**: 4 conflicts (STATE.md, codex-to-claude.md, rank-home.tsx
  x2). Kept Rank's new AbortSignal-cancellation + explicit `STALE_TIME`
  additions (main had neither) plus a deterministic `params: {limit}` key
  Rank added; deduped a doubled `foundationQueryKey` import. **Caught a
  real process bug post-merge**: a local test-assertion fix
  (`rank-home.test.tsx`, matching the already-shipped `errorMessageFor`
  classification) was made *after* the merge commit and never actually
  got committed before I pushed -- CI's Frontend job failed on exactly
  that stale assertion. Fixed with a follow-up commit, full suite
  re-verified before re-pushing. Merged `e1d024e`.
- **#263 Food Evidence/Add Spot**: 1 conflict (`add-spot.tsx` retry-button
  icon) -- kept the new retry/loading-spinner functionality, swapped a
  leftover `Colors.primary` for this file's own `Colors.brand` convention.
  Merged `7bda981`.
- **#264 social-share loop**: mostly clean auto-merges (STATE.md/
  codex-to-claude.md needed hand reconstruction once; a real backend
  Alembic migration, verified with a full upgrade/downgrade/upgrade
  cycle). **Two real, still-unresolved CodeRabbit findings from the
  original review turned out to still be valid against current code**
  (verified independently, not taken on faith): (1) `saves.py`'s
  `ShareSavePreference` opt-out insert on unsave raced two concurrent
  unsave requests for the same user/place -- both could see no existing
  row and both insert, and the composite-PK conflict on the second would
  500 *and* roll back the delete itself; isolated the insert in a
  SAVEPOINT so a conflicting insert is swallowed instead. (2)
  `reconcile_matched_share_saves` filtered out inactive-place candidates
  *after* SQL applied `limit`, so an inactive place in a batch silently
  occupied a slot a real candidate needed; moved the `is_active` filter
  into the query (a `Place` join) and added a regression test. Needed
  two further re-rebases as #262/#267 merged out from under it (docs-only
  each time). Merged `c8863a6`.
- **#266 Profile/Taste social hardening**: the largest rebase by far --
  genuine overlap between this PR's privacy retirement (drop following/
  followers/streak, drop cross-account Taste Profile viewing, drop the
  public ranked list on `user/[id]`, Friends Feed/Leaderboard become
  redirect stubs) and this session's own already-merged error-taxonomy
  propagation (which had added `errorMessageFor` classification to
  several of the same screens). Resolution throughout: kept this PR's
  retirement scope intact, re-layered `errorMessageFor` onto whatever
  error states survived the retirement, swapped leftover `Colors.primary`/
  hardcoded `'#FFFFFF'` for the current `Colors.brand`/`Colors.actionPrimary`/
  `Colors.onActionPrimary` tokens. `profile.test.tsx` and
  `user-profile.test.tsx` were rebuilt combining this PR's new tests with
  the still-relevant regression coverage (sign-in gate, 404-vs-error
  distinction, retry recovery, block/unblock, race-condition protection)
  its own test-file rewrite had dropped along with the retired features --
  translated to the new mock shape, nothing retired reintroduced. Needed
  three re-rebases total as #262/#264/#267 each merged out from under it
  in turn: `rankings.py` needed both Rank's new
  `rank_eligible_visit_for_place` security fix (kept) and this PR's now
  owner-only `get_user_rankings` (which made Rank's added `is_blocked`
  import dead code here -- dropped); `feed_social.py` needed both
  Auth/Settings/Activity's new real `/feed/activity` endpoint (kept) and
  this PR's `/feed/friends` retirement (410 Gone, kept) to coexist, with
  `social.ts`'s matching `fetchMyActivity`/`ActivityEvent` types kept and
  its own now-dead `fetchFriendsFeed`/`fetchLeaderboard` dropped (nothing
  referenced them). Merged `c9a5bf1`.
- **#267 Auth/Settings/Activity**: fully clean auto-merge, zero conflicts,
  both times. Merged `4c43359`.
Locked files: none -- closed.
Verification: every branch got the same treatment before each push --
`tsc --noEmit` clean, full frontend Jest suite, full backend pytest suite
(where the branch touched backend), plus focused suites for the branch's
own scope. One recurring, confirmed-flaky failure
(`__tests__/place-detail.test.tsx`, unrelated to any of these five PRs'
diffs) showed up on first full-suite runs for #266's v2/v3 rebases and
passed clean on immediate re-run and in isolation each time -- not a
regression, not investigated further.
Next action: none from me. If Codex resumes: the branch names above are
now stale (merged) and safe to delete from GitHub UI. Two things from this
pass are outside my access and still need a human/Codex-with-Railway-access:
(1) OSM backfill's real production re-run (code fix already merged 9/9,
just needs the actual run); (2) nothing else outstanding from this batch.
Codex's Craves lane (per a separate live session transcript relayed by the
user) was deliberately left untouched throughout this entire pass to avoid
collision -- do not start a competing Craves branch without checking its
current state first.

---

Status: merged
Owner: Claude
Branch: claude/rebase-search-map-268, claude/rebase-feed-decision-session (both merged, can be deleted)
Base SHA: bf673a5 (origin/main tip after PR #285)
Scope: Codex ran out of usage mid-session before it could open PRs for two
already-finished, ready-for-review branches it had pushed to origin
(`codex/search-map-contract-propagation`, `codex/feed-decision-session` --
both logged in `codex-to-claude.md` as `ready-for-review`, "Next action:
Open the dedicated PR ... Do not merge"). User confirmed Codex could not
finish and asked Claude to close both out.
- `codex/search-map-contract-propagation` already had an open PR (#268),
  but its base (`755f02b`) predated PRs #281/#283/#285 -- most notably my
  own already-merged PR #272 (`b7c9248`/`d7c8bb2`), which independently
  propagated overlapping Foundation Gate query-key/error-taxonomy fixes
  into the same two screens. Rebased the branch onto current `main` in a
  scratch worktree; resolved 3 real conflicts in `SearchScreen.tsx` by
  keeping whichever side was more complete rather than picking one
  wholesale -- Codex's initial-vs-refetch error split (preserves stale
  cached results instead of blanking them on a background refresh
  failure) combined with my own already-shipped `errorMessageFor()`
  classification and the `myRankings` cache-sharing key `place/[id].tsx`
  already uses. `search.test.tsx`'s two "collided" test blocks were both
  kept (complementary, not actually conflicting). Force-pushed the merge
  as a fast-forward onto the existing PR head so #268 kept its history/
  comments. Full frontend suite reverified post-merge: 55/55 suites,
  571/571 tests; `tsc --noEmit` clean. CodeRabbit review clean (no
  threads). Merged `ab6ef80`.
- `codex/feed-decision-session` had no PR yet. Same rebase treatment: 3
  conflicts (`STATE.md` -- took main's; `(tabs)/index.tsx` -- kept main's
  `errorMessageFor` import/destructure and `Colors.brand`, both needed by
  code Codex's side didn't touch; `PlaceCard.tsx` -- kept main's
  `Colors.mediaScrimSoft` token over Codex's hardcoded `rgba(0,0,0,0.45)`,
  confirmed Codex's actual fix -- the Save control no longer nested inside
  the card's own touchable, real 44x44 target -- survived the merge
  untouched). Opened as PR #286, requested CodeRabbit, verified full
  suite post-merge: 54/54 suites, 566/566 tests; `tsc --noEmit` clean.
  CodeRabbit clean (no threads). Merged `b33fbd2`.
Locked files: none -- closed.
Verification: see per-branch notes above; both merges independently
full-suite-clean on top of each other (rebased #268 after #286 landed,
re-confirmed zero new conflicts before merging).
Next action: none from me on these two. Codex's other open, older PRs
(#262-267, Rank/Food-Evidence/Profile-Taste/Auth-Settings-Activity/
Social-share-loop hardening) were not touched -- out of scope for this
"Codex ran out of usage, finish what's already done" ask; each should be
checked for the same current-`main` staleness before merge whenever
someone picks them up next, using this handoff's rebase approach as the
template. The OSM backfill dedupe fix Codex flagged as blocked
(`codex/osm-backfill-dedupe-claims`) turned out to already be merged
(PR #243, 2026-09-09) -- the only remaining step there is rerunning the
real production backfill from current `main`, which needs Railway
production DB access this repo-only session does not have.

---

Status: merged
Owner: Claude
Branch: claude/amenity-search-constraint (merged, can be deleted)
Base SHA: 4b5509a (origin/main tip after PR #282)
Commit SHA: ea035da (merge commit on origin/main)
Scope: closes the remaining gap from PR #281's Known Gaps -- the SM-05/06
mockup's literal example ("Patio required") couldn't happen in the
running app because the query interpreter had no concept of amenities
at all. User explicitly authorized this ("if easy add amenities, if too
much leave off"); confirmed easy by following the exact pattern already
in this file for `radius_miles` (a Python-side post-filter over the
already-fetched candidate pool, not a second SQL round-trip).
- `query_interpreter.py`: new `required_amenities` field, deliberately
  separate from `required_categories`/`hard_constraints` (documented
  elsewhere as always meaning the dietary/allergy set -- folding
  amenities in would break that invariant and mis-route them into the
  category-table join path). Recognizes "patio"/"outdoor seating";
  negation gets its own wider prefix ("no outdoor seating," not just
  "non-"/"not ") since amenities are far more often negated with a
  plain "no" than dietary categories are.
- `search_engine.py`: `outdoor_seating` turned out not to be a plain
  `Place` column (an earlier assumption, caught before shipping) -- it's
  a resolved `PlaceTruth` row (`truth_value` one of "yes"/"no"/
  "limited", written by `promote_service_v2.py`'s OSM-claim pipeline,
  same as `place_detail_router.py` already reads). One bulk query over
  the candidate pool. Only "yes" satisfies a required amenity --
  "limited" doesn't silently upgrade, and a missing row fails it the
  same as an explicit "no". Never auto-relaxed, threaded through both
  retry calls unchanged -- same standing as a dietary hard constraint.
- Frontend: `required_amenities` renders with the same Required badge
  treatment as `required_categories` (PR #281), combined into
  `zeroResultInfo()`'s honest-attribution message and "keeping" list;
  `CONSTRAINT_PATTERNS` gets a patio/outdoor-seating entry.
Locked files: none -- closed.
Verification: PR #283 (https://github.com/Lavish213/CRAVE/pull/283),
merged `ea035da`. Backend `python -m pytest -q` -> 1120 passed, 2
skipped (6 new: 3 interpreter, 3 search_engine, covering confirmed/no/
limited/missing outdoor_seating and the unfiltered baseline). Frontend
`npx tsc --noEmit` clean, `npx jest --ci` -> 54/54 suites, 566/566 tests
(2 new). CI green (Frontend, both Backend jobs, both Analyze jobs,
Guard, CodeQL).
Next action: none from me. The Search/Map V1.5 mockup's SM-05/06
Required-vs-Preferred contradiction is now fully closed end to end --
mockup (Codex, PR #278) and running app (Claude, PR #281 + this PR)
agree, with a real, tested, filterable amenity constraint behind it.
Broader Search/Map V1.5 propagation (screen-by-screen visual QA,
device/accessibility proof) remains open per Codex's own "brutal truth"
self-assessment on PR #278/#279/#280 -- not this handoff's scope.

## Prior completed UI V2 work (Codex)

PR #278 merged as `70f5546`: durable mockup artifacts, UI V2 token map/audit,
warm semantic token foundation, shared selected/CTA/card/sheet/map marker
treatments, non-color selected Map pin affordance, and Search top-result hero
hierarchy. Verification on PR #278: CI/CodeQL green, local full frontend Jest
54 suites/561 tests.

---

Status: merged
Owner: Codex
Branch: codex/ui-v2-visual-refresh
Base SHA: be0b0fb1d8fa011612721535e70ef1375b27e394
Commit SHA: 70f55469a270a5daf455a96225cb0fd2658b7cd3
Scope: CRAVE UI V2 visual-system foundation and first Search/Map propagation.
Verification: see PR #278.
Explicit exclusions: production data jobs, backend routes/services, recommender
model behavior, Search/Map ranking/product-contract changes, paid data sources,
and deleting stale remote branches.

## Prior completed work (compacted)

Status before this claim: Claude's hitlist audit/misc cleanup merged in PR #276
(`5e9c555`) and follow-up logging merged through PR #277 (`be0b0fb`). Remaining
human-only gap from that lane: delete stale branch
`claude/project-grade-systems-review-4ot7d0` from GitHub UI if desired.

<!-- Previous state history retained below. -->

---

Status: merged
Owner: Claude
Branch: claude/hitlist-audit-and-misc-cleanup (merged, can be deleted)
Base SHA: eabd04f (origin/main tip after PR #275)
Commit SHA: 5e9c555 (merge commit on origin/main)
Scope: three follow-up items from this pass's misc-gap list.

1. **Stale designated-branch reconciliation, attempted then abandoned.**
   User asked to pull forward the 3 non-doctrine commits from
   `claude/project-grade-systems-review-4ot7d0` (d5869e5 camera-fix,
   f734145 + 2e78ef6 docs) and delete that branch. On actually cherry-
   picking them onto current `main`: d5869e5's real content (removing
   the Settings "Rate CRAVE" placeholder row) turned out to already be
   independently fixed on `main` by a separate commit (`e70a868`) --
   only a no-op `: any` type annotation was left. Worse, f734145's doc
   addition ("Place Detail's Report action is photo-only") is now
   **factually false** -- verified `ReportPlaceSheet.tsx` +
   `POST /moderation/places/{id}/report` already exist and are wired
   into `place/[id].tsx`. Merging it would have put a wrong claim back
   into `CRAVE_STATUS.md`. **Nothing from that branch was ported.** No
   PR opened for it. Branch deletion itself is also blocked in this
   environment: `git push origin --delete` returns a 403 from the git
   proxy. The branch still exists on GitHub; a human needs to delete
   `claude/project-grade-systems-review-4ot7d0` directly (repo settings
   or the GitHub UI) -- don't reopen this as a porting task, there's
   nothing left in it worth porting.
2. **Hitlist system audit.** Verified `/hitlist/save`, `/hitlist/me`,
   `/hitlist/suggest`, `/hitlist/delete` are all fully wired: save/
   suggest via `ShareLinkSheet.tsx`'s two modes, me/delete via
   `craves.tsx`'s load + optimistic trash-icon delete with rollback-on-
   failure. The "Route-wiring audit findings" section below (claiming
   zero frontend caller for suggest/delete) was itself stale, predating
   PR #271 which wired both -- no code change needed, working as
   designed.
3. **Fixed the two remaining misc items**: `GET /hitlist/me`'s
   docstring falsely claimed "confirmed unused by the shipped frontend"
   -- corrected (it's called directly by `getMyPlaceSaves()`). Removed
   the dead bare `GET /api/v1/map` route (`map_places`) -- zero frontend
   caller anywhere, confirmed via `app.openapi()['paths']` before/after.
   Its underlying query function `fetch_places_for_map` stays: `/map/
   geojson`'s handler wraps it internally, still load-bearing. Also
   dropped the dead `get_map_places` alias this exposed.

Locked files: none -- closed.
Verification: PR #276 (https://github.com/Lavish213/CRAVE/pull/276),
merged `5e9c555`. `python -m pytest -q` -> 1114 passed, 2 skipped (1115
minus the one test removed for the deleted route's own error-contract
case). CI green (Frontend, both Backend jobs, both Analyze jobs, Guard,
CodeQL).
Known gaps: the stale branch itself (see item 1) is not deleted --
blocked by environment network policy, needs a human. Everything else
from this pass's misc list is closed.
Next action: none from me -- awaiting the user's next screen/feature
ask.

**Coordination note, 2026-09-13:** the branch this file's protocol names
as the designated branch for this lane,
`claude/project-grade-systems-review-4ot7d0`, is ~200 commits behind
`main` (merge-base `6e32ba4`) and carries only 4 commits `main` doesn't
have: a real camera-failure-toast fix (`d5869e5`) that's since been
independently re-fixed on `main` with different copy, two small Place
Detail doc notes (`f734145`, `2e78ef6`), and a doctrine-lock commit
(`f3329bd`) whose STATE.md/doctrine-doc content is superseded by a
later, corrected version already on `main`. It has not been merged into
`main`. This PR (#274) was opened directly off `main` instead, per
explicit user direction, rather than force-pushing a reconciled version
of the stale branch. **Whoever next claims this lane should either
merge `main` into that branch (bringing forward only `d5869e5`,
`f734145`, `2e78ef6` -- drop `f3329bd`, it's superseded) or ask the user
whether the branch should simply be abandoned/deleted** -- don't build
new work on top of it as-is; it's missing all of PRs #246-273.

## Prior completed work (compacted)

- **PR #269** (merged `6bf511e`): route-wiring audit (video-report
  wiring + record-video auth gate). See "Route-wiring audit findings"
  below for full detail, still current.
- **PR #271** (merged `1bb402d`): wired `hitlist/delete` (trash icon on
  Craves "Added" rows) and `hitlist/suggest` (new "Suggest" mode in
  ShareLinkSheet -- name + city, no coordinates). Confirmed the
  corroboration/promotion pipeline the user described (suggestions
  accumulate confidence per distinct contributor via
  candidate_store_v2.py's corroboration_keys, auto-promote at
  promotion_orchestrator_v2.py's 0.72 threshold) already exists exactly
  as intended -- no backend changes needed, just frontend wiring.

## Route-wiring audit findings (Claude, 2026-09-13)

Method: `python3 -c "from app.main import app; print(app.openapi()['paths'])"`
against a fresh checkout gives the ground-truth 95-route backend surface
(FastAPI 0.141.1's lazy `_IncludedRouter` means `app.routes` alone under-
counts -- use `.openapi()`, not `.routes`, for this). Diffed against every
`client.(get|post|put|patch|delete)` call across `frontend/src/**/*.ts`
(not just `frontend/app` -- that scope miss is exactly what let the
video-report gap below go unnoticed).

**Fixed, PR #269:**
- `POST /moderation/videos/{id}/report` had zero frontend caller despite
  being fully built (review queue, auto-hide threshold, identical shape
  to the image/place report endpoints already wired) -- see PlaceVideoGallery.tsx.
- `PlaceVideoGallery.tsx`'s "Record a video" was a toast-only signed-out
  dead end, same bug class as Rank/record-video/Place Detail/Friends Feed
  fixed earlier this session -- missed then because that sweep only
  covered `frontend/app`.

**Resolved since this audit was first written (2026-09-13, PR #271 +
#276) -- corrected here so the stale version below doesn't get
re-discovered from scratch:**
- `DELETE /api/v1/hitlist/delete` and `POST /api/v1/hitlist/suggest`
  turned out to already be fully wired by the time of a fresh re-check:
  `/suggest` and `/save` via `ShareLinkSheet.tsx`'s two composer modes,
  `/delete` via `craves.tsx`'s optimistic trash-icon delete (with
  rollback-on-failure) on the Craves "Added" section. The claim below
  that these had zero frontend caller was itself stale, predating PR
  #271. No UI decision needed after all -- it was already made and
  shipped.
- `GET /hitlist/me`'s stale docstring ("confirmed unused... calls
  /saves instead") corrected in PR #276 -- it's called directly by
  `getMyPlaceSaves()` and backs the Craves "Added" section.
- `GET /api/v1/map` (the bare, non-geojson endpoint) removed entirely
  in PR #276 -- confirmed zero frontend caller via `app.openapi()
  ['paths']` before/after. Its underlying query function
  (`fetch_places_for_map`) stays load-bearing (`/map/geojson` wraps it).

**Original findings as first written, for context (now superseded by
the corrections immediately above):**
- `GET /api/v1/hitlist/analytics/summary`, `POST /api/v1/signals/intake`,
  `POST /api/v1/signals/social-intake` are all `require_api_key`-gated
  with no `get_current_user_id` dependency -- server-to-server/ops
  surfaces (analytics dashboard, external signal ingestion), correctly
  never called from the mobile app. Not gaps.
- Everything under `/debug/*`, `/moderation/*` GET-queue and `*/review`
  routes, `/coverage/summary`, `/enrichment/priority`, and `/health` are
  admin/ops/infra surfaces, correctly frontend-silent. Not gaps.

**Baseline health confirmed clean** (pre-existing, not this audit's doing,
but stress-tested as part of it): backend `python -m pytest -q` -> 1115
passed, 2 skipped; frontend `npx tsc --noEmit` -> clean; frontend
`npx jest --ci` -> 52/52 suites, 546/546 tests, all against current `main`
post #260/#261/#265.

## FRONTEND EXECUTION ORDER — LOCKED (2026-09-11)

A full frontend audit (verified line-by-line against `main`, not taken on
faith — see that doc's "Grounding findings") plus its remediation strategy
are now locked as the controlling order for all frontend work, superseding
the old wave-numbered sequencing for frontend specifically. Full rationale,
rules, Definition of Done, and grounding evidence live in
`docs/doctrine/CRAVE_FRONTEND_EXECUTION_ORDER.md` — **read that file before
claiming any frontend work below.** This section is the short pointer;
that file is the source of truth for detail.

Locked order:
```
Foundation Gate → Place Detail (proving slice) → Feed/Decision Session
→ Search/Map (propagation-only) → Craves → Rank → Food Evidence/Add Spot
→ Profile/Taste/social cleanup → Auth/Settings/Activity completion
→ cross-app accessibility/E2E/release certification
```

Method: vertical-slice migration, not infrastructure-first. Lock the
minimum shared contracts (Foundation Gate) → prove them on Place Detail →
extract only what's proven → propagate slice by slice, each one shipping a
visibly better screen while migrating the architecture underneath it.
Rejected alternative: 20 infrastructure tasks before touching a screen —
too much invisible-progress risk and speculative-abstraction risk.

**Scope boundary, read before touching Search or Map:** that slice may
propagate shared contracts, reliability, data-state conventions, auth/
error/query ownership, accessibility fixes, and integration hardening
*only*. It must not redesign or reopen the certified Search Screen
Contract or approved Search/Map UX without a new, proven, documented
contract gap — Wave 5 (PRs #190-193) and the V1.5 design-audit fixes (PRs
#225/#226/#229) stay certified.

Locked rules (full text in the doctrine doc): React Query migrates
opportunistically per-route (not a mechanical 30-route pass), with
key/cancellation/stale-time/account-isolation/error-semantics conventions
locked at the Foundation Gate first; `catch {}` occurrences get classified
individually (ignorable-cleanup / recoverable-background / user-actionable
/ invariant), never blanket-banned or blanket-ignored;
`RecommendationEvent` stays fact-only (no fabricated `reason_codes`/
`model_version` ahead of a real ranking model); `crave://` stays as
fallback under a new `https://` universal-link primary; E2E coverage is
built journey-by-journey as each slice lands, not as one final sprint.

**Next action for this lane:** Foundation Gate, Place Detail, and Feed/Decision
Session have now merged. The next frontend slice in the locked order is
**Search/Map propagation-only**: reliability/state/query/accessibility
hardening only, with no redesign or reopening of the certified Search/Map UX
unless a new, proven contract gap is documented first. Claim that slice here
(owner, branch, base SHA, allowed files, verification plan) before editing.

### Foundation Gate progress (Claude, 2026-09-11)

Status: **PR #258 merged** (`03bc6cf`, merge commit on `main`). Owner:
Claude. Base at merge time: `main` post-#255/#256/#257 (`40cc186`).

**Real finding:** the `PendingIntent`/auth-gate contract the doctrine
calls for already existed — `authGateStore.ts`'s `AuthResumeEnvelope`
(`actionType`/`reason`/`sourceRoute`/`targetIds`/`payload`/`destination`/
`idempotent`/`expiresAt`/`migrateAnonymous`/`revalidate`/`onInvalid`/
`resume`) plus `AuthGateHost`/`resumePendingAuthAction` is essentially
that contract, already built and already used by Save/Add Spot/posting/
Rank Home. Foundation Gate's actual remaining work here was narrower than
"design a new contract": find and close the screens that don't use the
existing one.

- **Done, PR #258** (branch `claude/foundation-gate-rank-auth-fix`,
  now at `3a71bcd`):
  - `/rank/[placeId].tsx`'s signed-out state was a dead-end static message,
    the first gap of this kind found. Wired into `EmptyState` +
    `requestAuthGate` (`reason: 'rank'`, already a valid enum value),
    matching `rank-home.tsx`'s existing identical pattern exactly.
  - `record-video/[placeId].tsx`'s signed-out state offered a "Go back"
    button and *no sign-in mechanism at all* — worse than a dead end, an
    exit. Now shows a "Sign in" button that opens `AuthSheet` inline
    (`reason: 'default'`, no dedicated copy exists for this action).
  - `place/[id].tsx` had **six separate dead-end sites in one screen** —
    the largest single instance of this bug class found so far: `handleSave`
    (silently no-op'd, not even a toast), `handleAddPhoto`,
    `handleOpenMenuSubmit`, the "Save for tonight" ladder CTA, the "Rank it"
    ladder CTA, "Report the main photo", and "Report an issue" all either
    toasted "Sign in to..." with no way to act on it, or (handleSave) gave
    no feedback whatsoever. All seven call sites now route through a new
    local `gateSignIn` helper wrapping `requestAuthGate`
    (`save`/`rank`/`default` reasons as appropriate; the Rank CTA carries
    `destination: /rank/{id}` back to itself).
  - All three fixes use `resume: () => undefined` (deliberate no-op) —
    matches the established safe pattern: a `resume` closure captured at
    gate-request time would close over that render's `user` (null),
    so auto-resuming the mutation later would run on stale state.
    Component-level `useAuthStore` subscriptions re-render the caller past
    the signed-out branch instead; the user re-taps.
  - Verification: `tsc --noEmit` clean (0 `error TS` across the whole
    project), `place-detail.test.tsx` 35/35 (new signed-out-gate suite
    added), `record-video.test.tsx` 15/15 (new sign-in test added).
    CI green (7/7 real checks: Guard, Frontend, Backend x2, Analyze x2,
    CodeQL), CodeRabbit skipped per repo policy (<10 stars, OSS), no open
    review threads. Merged to `main` at `03bc6cf`.
- **Auth-gate sweep completed this pass** (grepped every screen in
  `frontend/app` for `if (!user)` and `Sign in to`, not just the three
  screens already named above): Craves, Search/Map, Feed
  (`(tabs)/index.tsx`), rank-home, add-spot, food-evidence, Profile, and
  Leaderboard all already gate correctly via `AuthSheet`/`requestAuthGate`
  — verified by reading each site, not assumed. `add-spot.tsx`'s
  `handleConfirm` still has a bare `toast('Sign in to add a new spot')`
  guard, but it's dead code in practice: the whole screen returns an
  `AuthSheet`-gated empty state at the `state === 'unauthenticated'`
  branch before that handler is ever reachable — left as-is, not a real
  gap.
  - **Found and fixed, same PR**: `friends-feed.tsx` had no signed-out
    branch at all — its account-scoped query is simply `enabled: !!user`,
    so signed out it fell through to the generic "Nothing here yet /
    Follow people to see..." empty state, identical to what a genuinely
    friendless signed-in user sees, with a "Find people" CTA that never
    mentioned signing in. Now shows its own "Sign in to see friend
    activity" gate first, same `EmptyState` + `AuthSheet` pattern as the
    others. Test added (9/9 passing), `tsc --noEmit` clean.
  - Also checked: Activity (`activity.tsx`) is a static "coming soon"
    placeholder with no data fetching and nothing to gate; Settings
    (`settings.tsx`) simply hides its ACCOUNT/DANGER ZONE sections when
    signed out (`user ? ... : null`) rather than attempting and blocking
    an action — neither is this bug class. No dedicated Taste Profile
    route exists separately from `(tabs)/profile.tsx`, already covered
    above. This closes out the sweep: every screen in `frontend/app` has
    now been individually checked for this specific gap, not sampled.
- **Still not started**: error taxonomy (offline/timeout/unauthorized/
  forbidden/not_found/rate_limited/server_error/invalid_data/unknown +
  UX mapping), React Query key/cancellation/stale-time/account-isolation
  conventions (only 4 of ~30 routes use RQ at all today), the
  `https://` universal-link contract (still `crave://`-only), and the
  privacy/provenance scopes (private/shareable/display-identity/
  explicit-opt-in; value/source/fetched_at/confidence for place data).
  None of these were touched this pass — don't claim Foundation Gate
  complete from the Rank fix alone.

## Other active lanes (independent, not blocked by the above)

### OSM backfill production run

Status update, 2026-09-11: the duplicate-claim dedupe fix is **merged**
(PR #243, SHA `a271856` on `main`) — confirmed directly by reading the
merged `backend/scripts/backfill_osm_hours_and_seating.py` (the
`scheduled_claim_keys` in-memory set is present). The original crash this
fixed: a first real production attempt reached
`scanned=2500 claims_written=30 places_affected=27` then hit
`psycopg2.errors.UniqueViolation` on a duplicate deterministic claim
within one run; those 30 claims stayed committed, the failing batch
rolled back.

Codex has since relayed (2026-09-11, **not yet independently verified by
this session** — no Railway/Postgres access here) that a fresh dry-run on
the merged fix reproduced the original dry-run numbers exactly
(`osm_candidates_scanned=11239`, `claims_written=4289` from
`candidates_touched=3634`, `places_affected=3631`), then a real apply was
started and was actively progressing batch-by-batch with no errors as of
that report. **Do not treat this as complete** until: (a) the run reports
a final done state with no crash, (b) an idempotent dry-run rerun
afterward reports `claims_written=0`, and (c) a real `GET /place/{id}`
spot-check on a known OSM place shows non-null `hours_status`/
`outdoor_seating`. Whoever confirms all three should record the exact
numbers and the spot-checked place id here, replacing this paragraph.

### Menu backlog canary status

Still not run. Verified blocker, unchanged: current
`backend/scripts/run_menu_backlog_canary.py` requires exact `--place-ids` or
`--place-ids-file`; a bare `--run --confirm-count 10` is insufficient, and
no reviewed 10-place cohort has been recorded anywhere durable yet.

Next action: once production DB access is available, build/record a
reviewed 10-place ID file, preview it, then run with
`--place-ids-file <reviewed-file> --run --confirm-count 10` and review all
outcomes immediately.

### Menu item source provenance — PR #252

Codex's own PR (`codex/menu-provenance-fix`, not this session's), fixing
menu-item source lineage through canonicalization/claim emission and
refusing anonymous claims with no source URL. CI green (8/8, including the
previously-slow real-Postgres suite), CodeRabbit review requested.
Explicitly holds off any new production menu-publish canary run until
after merge + fresh authorization — correct posture, matches this file's
own standing rule for canaries. Not this session's PR to merge; watch for
its outcome, don't act on it uninvited.

### Posting V2 composer stack (Codex, in progress — not yet merged)

Building directly on this session's merged Posting V2-A (PR #244 backend
SHA `e361e1b`, PR #245 frontend SHA `8d3023d`, both on `main`): seven PRs
since 2026-09-09, none merged yet, all still draft —
`#246` (fixes a real race left in the merged #245 draft store: candidate
selection left `outcome='pending'`, letting a rapid existing-place tap
steal the same draft's media — adds an `awaiting_place` outcome to close
it), `#247` (doctrine freeze: `CRAVE_POSTING_MEDIA_V2_ARCHITECTURE.md`,
a Posting screen contract, a backend contract — docs only), `#248`
(composer state fields: intent/reaction/caption/visibility/occurredAt,
persisted-store migration), `#249` (new `FoodContribution` model +
`/api/v1/contributions` API — additive, isolated, own migration, CI
green), `#250`/`#251` (unified composer frontend: `/posting-restaurant` +
rewritten `food-evidence.tsx` composer, replacing the #245
attach-immediately bridge), `#253` (the consolidated end-to-end version of
the whole stack, backend + frontend together, directly against `main`).

This session reviewed the stack (diffs read, not just descriptions) and
found #246/#248/#249 correctly implemented and tested. #253 had a real,
reproducible CI failure — `tsc` errors from stale `DraftOutcome` literals
in `add-spot.test.tsx` plus a type mismatch in `friends-feed.tsx` — that
had silently persisted across #250 and #253 (18+ hours, two PR iterations)
because `tsc` failing meant the Jest step never even ran in CI. Fixed
directly on `chatgpt/posting-v2-composer` (commit `846a3b1`): corrected
the two stale literals, the `friends-feed.tsx` type mismatch, and fully
rewrote both `add-spot.test.tsx` and `food-evidence.test.tsx` (which were
still asserting entirely stale pre-composer copy/behavior — fixing the
types alone would only have moved the failure to Jest). Verified: `tsc
--noEmit` clean, full frontend suite green (50/50 suites, 533/533 tests),
backend untouched and clean, and confirmed green in real CI afterward
(8/8 checks on PR #253, including Frontend typecheck+tests). Not this
session's PR stack to merge — it's Codex's active, still-evolving branch;
this was a narrow CI-unblock, not a claim on the work.

## Previous compacted context

## Wave 6 — Craves intelligence — COMPLETE

All 4 steps merged: (1) backend + typed client, PR #215; (2) screen
rebuild around the reasoned subset, PR #216; (3) automatic cuisine/
geography clustering, PR #218; (4) doctrine correction reclassifying
contract §11 as blocked on §3.6 (operational-data ingestion, app-wide,
not Craves-specific), PR #219. Contract status: **GREEN**. One tracked,
non-blocking gap remains: the "Craves"/"Added" sections still render via
their own bespoke row style, not `PlaceCardCompact`, pending `/craves`
and `/hitlist/me` returning full `PlaceOut` instead of bare IDs.

## Wave 7 — Place Detail relationship hierarchy — COMPLETE

Per `docs/doctrine/CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.5 and
`docs/doctrine/CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md`. Three PRs:

1. **Backend groundwork — PR #221.** `visit_evidence_for_place()`
   single-place lookup; `reason_role`/`reason_source`/
   `visit_confirmation_count` columns on `HitlistSave` (the latter a
   real repeat-visit signal, incremented only on the `visited`
   False→True transition -- not fabricated from data that didn't
   support it); new `GET /place/{id}/relationship` endpoint (per-viewer,
   never cached, same pattern as the existing `.../friends` endpoint).
2. **Frontend rebuild — PR #222 (+ follow-up fix, this PR).** Four
   relationship modes real and distinct in the running app; shared
   `DecisionStrip` reused for a reason threaded from Craves/Search/
   Feed's Decision Session card via new `reason_role`/`reason_source`
   nav params, AND remembered on a later cold visit via the persisted
   `HitlistSave` fields (contract §13 -- the nav-param-only version
   shipped in #222 was a real gap, closed same-day rather than left
   silently incomplete); adaptive CTA ladder (Directions → "Save for
   tonight" → existing rank CTA once visited, relabeled "Rank it").
3. **Doctrine correction (this PR)** to
   `CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md` §22/§26, documenting what
   shipped precisely against the contract's own text and naming every
   simplification, not just the two blockers known up front:
   - **Reserve CTA rung** -- not attempted; no reservation-provider
     integration exists, and full reservations/ordering integration is
     **permanently** out of scope for V1 (`CRAVE_MASTER_CODEX_
     REMAINING_WORK.md` §4), not a "not yet built" item.
   - **§12's 4-action taste-correction vocabulary** -- not attempted;
     needs the Gate 2 taste graph, which doesn't exist.
   - **Quick-Take Reaction control** ("How was it?", §11/§14) --
     genuinely doesn't exist anywhere in the app (no data model, no
     UI). Wave 7 goes straight from "visited" to the existing "Rank it"
     CTA rather than fabricate a reaction control with nothing behind
     it. New finding (not in the original scoping) -- likely lands with
     Wave 8's posting composer "quick take" step
     (`CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.11), tracked there.
   - **§14's relationship-status copy** is simplified vs. the
     contract's exact spec ("visited N days ago" + reaction status) --
     ships as a visit-count-based headline instead, since the reaction
     status half depends on the Quick-Take control above.
   - "Regular"'s threshold is implemented at 2 confirmed visits, not
     the contract's own illustrative "10+" -- explicitly permitted by
     the contract's own text as a tuning detail, not a deviation.

Contract status: **YELLOW, unchanged** -- the real named blockers
(Dish Intelligence, Gate 2, `hours` ingestion, now also the Quick-Take
control) gate specific sections, not the whole contract, same as
before Wave 7. Full verification each PR: `tsc --noEmit` clean, full
frontend suite green (twice, parallel + `--runInBand`), backend suite
1076+ passed against local Postgres with migration upgrade/downgrade/
re-upgrade verified.

**Wave 8 (Posting/Private Logging) is not claimed by this session.**
Per `docs/CLAUDE_EXECUTION_BRIEF_WAVES_7_10_2026-09-08.md`'s own
handoff intent -- read that doc's Wave 8 section, the full Posting
Screen Contract (draft one first if it doesn't exist yet, following the
same audit process used for Search/Craves/Place Detail), the Privacy
Matrix, Evidence Hierarchy, and API contracts before claiming it here.

## What this supersedes

This file previously tracked Phases 1-7 production hardening and release
certification in long-form detail. That work is real and merged but is
compacted here per protocol ("keep inboxes short, move detail to the PR or a
dated archive") since a much larger, newer workstream has since completed and
is now the controlling context.

- Phases 1-7 hardening: merged (Phase 7 PR #138, SHA `ee77d302...`).
- Release-certification prep (Master Matrix, runbooks, credential/Sentry
  audits): merged, tracked in `docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md`.
  Not re-summarized here — read that file directly if resuming that thread.
- Full product-doctrine workstream (V1 Scope through the Canonical
  Implementation Index, all PRs #148-#173): **complete, merged to `main`**.
  Do not re-open or redraft any of these without a proven doctrine gap or
  explicit new user direction.
- Implementation **Wave 3 — navigation topology** (PR #185) and **Wave 4 —
  Feed / Decision Session hierarchy**: both merged. Details in
  `docs/doctrine/CRAVE_CODEX_HANDOFF_STATE.md`.

## Full end-to-end verification (Claude, 2026-09-07, against main post-Wave-4)

Ran the actual CI commands locally, not just read the docs:
- Backend: `python -m compileall app` clean; `import app.main` clean;
  `pytest -q` → **1043 passed, 2 skipped**, 0 failures.
- Backend/Postgres invariant: `alembic heads` → exactly one head.
- Frontend: `npx tsc --noEmit` → **0 errors**.
- Frontend: `npx jest --ci` → **45/45 suites, 426/426 tests passed**.
- Repo-wide conflict-marker guard (the same grep CI runs) → clean.
- Cross-checked every YELLOW blocker in `CRAVE_CODEX_READINESS_AUDIT.md` §3
  against its source screen contract and `CRAVE_API_INTEGRATION_CONTRACTS.md`
  — every one is a genuine engineering/data-capability gap, not a hidden
  product-decision punt. Two cosmetic doc issues flagged, not fixed (low
  priority): some screen contracts still say "deferred to the *forthcoming*
  API/Integration Contract artifact" (that artifact now exists); 4 of 15
  contracts fold "unresolved dependencies" into Traceability's "Forward
  dependencies" line instead of using the mandatory standalone heading —
  content is present and correct either way.

**Net result: whole app (both halves) is green end-to-end on the current
main commit.** No regressions found through Wave 4.

## Wave 5 Search Screen Contract certification (Claude, 2026-09-07)

Wave 5 was originally merged as one commit (`37bebcf`, "Wave 5 semantic
Search and contextual Map") reported as fully finished. Auditing it
against `docs/doctrine/CRAVE_SCREEN_CONTRACT_SEARCH.md` line-by-line
surfaced real gaps one at a time rather than all at once — each was
fixed and merged before moving to the next, per explicit user direction
not to certify over a known gap:

- PR #190: the default GitHub CodeQL check (distinct from this repo's
  custom `Analyze` jobs — a real, repo-specific gotcha) had 3 open
  high-severity `js/insecure-randomness` alerts on `Math.random()`-based
  search-session ids. Replaced with `expo-crypto`'s `randomUUID()`.
- PR #191: the contract's Reason Block labeling requirement ("Best
  match for you / Safer pick / Worth exploring") was entirely unbuilt.
  Implemented via the shared `DecisionStrip` renderer with a
  Search-specific `SearchReasonRole` type kept structurally separate
  from Decision Session's `DecisionRole` — tested to confirm no
  vocabulary leakage either direction.
- PR #192: zero-state had no real decision-support content (contract
  §5/§6) and zero-result messaging was a generic "try broader terms"
  (contract §11, explicitly prohibited by §16). Implemented a
  time-relevant intent shortcut, recent-searches store, and named
  soft-constraint relaxation that never touches a dietary/allergy hard
  constraint.
- PR #193: a final line-by-line pass against all 21 contract sections
  (explicitly requested to stop discovering gaps one at a time) found
  two 40pt touch targets under the 44pt minimum (fixed), and two
  doctrine-text corrections: the constraint-interpretation engine is
  fully built and live, not the unresolved backend work §17 described
  (marked resolved); the app-wide offline/staleness UI layer genuinely
  doesn't exist yet (added as its own explicit §17 dependency instead of
  building Search-only infrastructure for it ad hoc).

Verification per PR: `npx tsc --noEmit` clean, `npx jest --ci` clean
(46/46 suites, 450/450 tests by the final PR), default `CodeQL` check
verified green specifically (not inferred from the custom `Analyze`
jobs alone) before each merge.

**Scope boundary — do not overclaim from this:** this certification
covers the *Search screen* only. Wave 5's other half, contextual Map
plumbing (`CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.3), was checked
against the current code as part of this same pass and is **partial**:
direct/city Map mode (`fetch_places_for_map` in
`backend/app/services/query/map_query.py`) still ranks candidates by a
plain bounding-box-scoped `Place.rank_score`, not the shared
recommendation-context contract Feed/Search use — everything else in
§3.3 (exact candidate handoff, no rerank, "Search this area," no
auto-refetch on pan, location-denied fallback, list/map parity, Map
kept contextual not a tab, source attribution) is implemented and
verified. This one item remains open and is not folded into "Wave 5
complete."

**Merged main SHA verified:** `84d8db31a417ca2e8caa32e64cb3b25d85b1b166`
(`git log origin/main`, confirmed directly, not assumed from the PR
merge response alone).

**Railway deployment status: NOT verifiable from this sandbox** — no
Railway dashboard or API access exists in this execution environment.
Only the merged `main` SHA above was verified; whoever has Railway
access should confirm the corresponding deploy separately before
treating this as fully released, not just merged.

## Current real status

- `docs/doctrine/CRAVE_MASTER_CODEX_REMAINING_WORK.md` (new, this update) is
  the consolidated, current, item-by-item checklist of everything left —
  grouped by Migration Plan wave (5 through 10), cross-referenced to the
  Readiness Audit and API/Integration Contracts, with the explicitly-blocked
  OPEN/LATER/AUDIT-REQUIRED list and the permanent Definition-of-Done
  regression gate at the bottom (not itself a wave). Read this before
  claiming any task — it supersedes re-deriving scope from the Migration
  Plan/Readiness Audit separately.
- `CRAVE_CANONICAL_IMPLEMENTATION_INDEX.md` and `CRAVE_CODEX_HANDOFF_STATE.md`
  were updated in the same pass to point to it and to record Waves 3-4 as
  completed baseline.
- Waves 0-4 are merged and must not be redone: Wave 0 (#146 release-defect
  protection), Wave 1 (shared foundations, #170), Wave 2 (visit-evidence +
  Rank ownership, #172), Wave 3 (navigation topology, #185), Wave 4
  (Feed/Decision Session hierarchy).
- Wave 5 Search Screen Contract is merged and certified (PRs #190-#193)
  and must not be redone or reopened without a proven new contract gap.
  Wave 5 contextual-Map plumbing has one open item (§3.3, direct-mode
  ranking source) — pick that up as its own small, scoped fix, not a
  reason to reopen the Search half.
- Two independent tracks may now proceed in parallel: **implementation**
  (Wave 6 — Craves intelligence, `CRAVE_MASTER_CODEX_REMAINING_WORK.md`
  §3.4) and **design** (a Penpot screen-design package, starting with
  Feed/Decision Session, then Search, then Craves, at Exploratory status
  per the locked workflow: define/approve each screen's purpose, layout,
  states, interactions, data, accessibility, and visual rules first,
  then implement without redesigning). Neither blocks the other.
- Four old open PRs, all Claude-authored, none Codex's responsibility,
  all predating current `main` by enough commits to report dirty/unknown
  merge state — need a rebase-or-close decision: #128 (place-issue
  reporting — real, tested backend+migration+frontend feature, looks
  genuinely mergeable after a rebase), #127 (camera-failure-toast +
  dead-control cleanup, likely still valid), #147 (design log Round 2,
  docs-only, likely still valid), #145 (STATE.md housekeeping — now
  fully superseded by this session's own STATE.md rewrites, safe to
  close). Not touched by this update; flagging only.
- The production data-coverage lane (menu/image/Overture canaries,
  scheduler reclaim/video proofs — needs Railway/Supabase access this
  session doesn't have) is bundled in
  `.agent-bridge/claude-to-codex.md`'s current top handoff
  (H-20260907-population-coverage-canaries). This is an **information-
  only inventory, not execution authorization** — an internal audit of
  it (2026-09-07) confirmed the document content is accurate but flagged
  that whoever picks it up must: work from a clean worktree off current
  `origin/main` (not a stale local checkout — one was found 321 commits
  behind with uncommitted changes), re-measure the baseline read-only
  first (every count is a historical 2026-09-02 snapshot), and claim
  exactly one bounded item in this file per `PROTOCOL.md` before running
  anything. Item 6 in that handoff (B1 steps 2/4) additionally needs its
  own scoping pass before it can be claimed at all — it has no cohort,
  command, or rollback plan yet, unlike items 1/2/5. A fuller,
  self-contained execution version of this same plan -- exact commands,
  operating rules, and untried source avenues beyond the six items
  (municipal permit datasets, AllThePlaces, Foursquare gap-fill) -- now
  lives in `docs/CLAUDE_EXECUTION_BRIEF_POPULATION_COVERAGE_2026-09-07.md`,
  written for whichever Claude session (Codex or otherwise) first has
  verified Railway/Supabase/Postgres access.

## Search/Map V1.5 design-audit fixes (Claude, 2026-09-08) — standalone, not a wave claim

User posted the Search/Map V1.5 "Supporting/Edge States" design board (16
edge states SM-05 through SM-16 + 8 resilience/accessibility evidence
cells) and asked for a backend-readiness audit against it. Findings,
each verified against actual code (not the docs):

- **Fixed, merged PR #225** (SHA `b7248f5`): share deep link
  (`crave://place/{id}`) was entirely missing from the native share
  payload despite the design promising one (SM-16). Partial by design —
  works for a recipient who already has CRAVE installed; does nothing
  for anyone else, since no web domain/universal-link infra exists yet
  (confirmed: no `associatedDomains`/`intentFilters`, no CORS web origin
  anywhere in backend config).
- **Fixed, merged PR #226** (SHA `6219346`): `lat`/`lng` only ever
  affected result *ordering*, never exclusion — a "within N miles"
  filter (SM-05/SM-07/SM-14) had nothing enforcing it. Added optional
  `radius_miles` to `GET /search`, filtered via exact haversine cut in
  `execute_search()`, extended constraint-relaxation to cover radius
  (same soft-preference standing as price), cache key bumped v2→v3.
  Backend now fully ready for a radius control; **no frontend UI for it
  exists yet** — a real, not-yet-scoped follow-up if the product wants
  one surfaced.
- **Fixed, merged PR #229** (SHA `df92429`): `hours`/"Closed Place"
  (SM-09) and outdoor-seating (SM-05/06/14) were reported above as
  blocked on missing data — on closer look, they weren't. OSM's
  Overpass fetch (`osm_overpass.py`) has always stored every tag on a
  node verbatim in `discovery_candidates.raw_payload`, including
  `opening_hours` and `outdoor_seating`, at zero extra ingestion cost;
  nothing downstream ever read those two keys. `promote_service_v2.py`
  now turns them into `PlaceClaim`s (OSM source only) through the
  existing claims/truth-resolver pipeline (new `PlaceTruth` rows, zero
  schema change). New `app/services/hours/opening_hours_service.py`
  (via free/open `opening_hours_py`) + `app/services/geo/
  timezone_lookup.py` (free/offline `timezonefinder`, needed because
  OSM's syntax carries no timezone of its own) compute a live open/
  closed/unknown answer — never a guessed or stale status.
  `GET /place/{id}` now returns `hours_status`/`hours_next_change`/
  `hours_raw`/`outdoor_seating`; Place Detail's decision strip renders
  real chips for both. `scripts/backfill_osm_hours_and_seating.py`
  retroactively claims these fields for already-promoted OSM places —
  pure re-read of already-stored `raw_payload`, no re-scrape, idempotent
  — **still needs someone with Railway/Postgres access to actually run
  it once** against production. Ruled out Google Places/Yelp/Foursquare
  deliberately: all need a new account/API key only the user can
  authorize, and Google's ToS additionally forbids long-term caching of
  place data — OSM had neither problem and was already half-wired here.

All four PRs followed the same verification discipline as everything
else in this file: `tsc --noEmit` / `python -m compileall` + `import
app.main` clean, full frontend suite green (48/48 suites, 486/486 tests
by the final PR), full backend suite (1110 passed, 2 skipped by the
final PR) against a **freshly reset** local Postgres schema.

## App-wide screen audit (Claude, 2026-09-09) — standalone, not a wave claim

User asked for a full screen-by-screen audit of every route in
`frontend/app` (not just Search), same rigor as the Search subsystem
audit below: full file reads, API-contract cross-checks against backend
routes, dead-code/gap/broken-control checks, race-condition review.

- Confirmed **fixed** (no longer gaps) from the earlier
  `SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md`: Rank's retry buttons
  are genuine refetches, record-video's failed `recordAsync()` now
  toasts a real error, Leaderboard has a distinct Friends sign-in gate,
  Craves' remove-a-save now confirms via `Alert.alert`.
- Confirmed a real cross-screen bug class (client-side filtering
  against a capped/paginated fetch) present in Search, Feed, and Map —
  already fixed with three screen-specific patches, merged PR #234
  (SHA `c8abbc5`). Confirmed **absent** elsewhere (`rank-home.tsx`'s
  `list_user_rankings()` is a genuine unbounded fetch).
- Full remaining sweep (rank-home, rank/[placeId], friends-feed,
  add-spot, settings, record-video, user/[id], taste-profile, activity,
  legal, profile-setup, +not-found, both root layouts): no new gaps
  except two, both below.
- **Fixed, merged PR #236**: `taste-profile/[userId].tsx` collapsed any
  non-404 error on `fetchProfile`/`fetchTasteProfile` into the same
  false "not found"/"no taste profile yet" states as a genuine 404 or
  empty profile, with no retry — same anti-pattern its sibling
  `user/[id].tsx` already fixed via `profileError`. Added the matching
  `profileError`/`tasteError` states here too.
- **Fixed, merged PR #238** (SHA `746b6e1`): the "+" FAB's
  `food-evidence.tsx` captured a photo/video, then "Continue" dropped it
  entirely — no upload call, no param passed to `add-spot.tsx`, no
  queue. Implemented option A from
  `.agent-bridge/claude-to-codex.md`'s `H-20260909-food-evidence-media-
  drop` handoff (now resolved/compacted there): `food-evidence.tsx`
  carries `{ uri, kind, fileSize, mimeType }` as route params;
  `add-spot.tsx` wires the actual upload only when a `place_id` already
  exists (`already_in_crave: true` — photo via the existing
  `useUploadImage()` flow, video via the existing
  `videoQueueStore.recordVideo()`); the new-candidate branch
  (`confirmNewSpot()` only ever returns a `candidate_id`, never a
  `place_id`) now says so explicitly instead of pretending it uploaded.
  CodeRabbit caught a real double-attach race on rapid "Open" taps
  (`mediaOutcome` state read before its own setter's render committed);
  fixed with a synchronous `mediaClaimedRef` guard, same pattern as
  `rank/[placeId].tsx`'s `submittingRef`. **Known accepted gap**: the
  new-candidate branch still can't attach media at confirm time —
  that's option B from the handoff (backend support for pending media
  on `DiscoveryCandidate`), not implemented, not silently dropped either
  (the toast says so).

## Next action

Superseded by the top of this file — **frontend work now follows
`docs/doctrine/CRAVE_FRONTEND_EXECUTION_ORDER.md`**. Foundation Gate, Place
Detail, and Feed/Decision Session are merged; the next implementation slice is
Search/Map propagation-only, not a visual redesign. Independent lanes still
open: production data-coverage (OSM backfill apply in progress per Codex's
relay, unverified here — see "Other active lanes" above; menu
canary/population-coverage still need Railway/Supabase access — see
`.agent-bridge/claude-to-codex.md`'s current handoff), and the Posting V2
composer stack (Codex's, in progress, see above). The Penpot/design track is
separate from this implementation order.

Claim any task here before starting it — owner, branch, base SHA (must be
current `main` or later), allowed files, and verification plan — per
`.agent-bridge/PROTOCOL.md`. This repo moves fast between syncs — re-check
`git log origin/main` before assuming this file is current.
