# H-20260913-misc-cleanup-and-reduced-motion

Status: resolved -- merged
Owner: Claude
Branch: claude/design-log-round-2, claude/misc-cleanup-followups,
claude/reduced-motion-accessibility (all merged, can be deleted)
Base SHA: 3116e4e (post PR #147)
Commit SHA: 3116e4e (#147), 320a182 (#295), 3b43521 (#296)
Allowed next files: none -- closed.

## Context

User asked what's left to do, then had me work through the concrete
repo-only-doable items: the four stale pre-session PRs, the Craves
reason_role nav "gap," cravesStore's duplicate error classifier, Map's
ranking source, and a start on the accessibility/E2E/release
certification pass.

## What I found and did

- Four stale PRs: #128 already merged (list was stale), #127/#145
  superseded (verified their content independently exists on `main`
  already or is long obsolete), #147 still genuinely open and accurate
  -- merged after a clean local test-merge confirmed no conflicts.
- Craves reason_role nav: read the actual code before touching
  anything -- `place/[id].tsx`'s `savedEntry` fallback already covers
  this, not a bug. No fix made.
- `cravesStore._classifyError`: now delegates to shared
  `errorMessageFor`, keeping only the 401 sentinel special case.
- Map ranking: confirmed the gap is real (plain `rank_score` order, no
  `rank_feed()`-style blend) but a real fix has genuine performance/
  architecture tradeoffs (full `Place` hydration + diversity-window
  truncation vs. today's lightweight 1000-pin projection) -- flagged to
  the user, not fixed unilaterally.
- Reduced Motion: added `useReducedMotion()`, wired into the three real
  continuous/bouncy sites the accessibility runbook itself named
  (SkeletonCard shimmer loop, MapBottomSheet's bouncy snap-back,
  PlaceCard's save scale-pop).
- Ran a background icon-only-accessibility-label audit across the
  whole app: all 20 icon-only controls already have correct labels.
  Confirmed strength, no fix needed.

## Known gaps / risks

- Map's direct-mode ranking source is unresolved by design -- needs a
  product/perf-tradeoff decision from the user, not a unilateral fix.
- The rest of the accessibility runbook (focus order, state
  announcements, on-device contrast, Dynamic Type clipping,
  VoiceOver/TalkBack label phrasing) needs a physical device with a
  screen reader enabled -- cannot be completed from this sandbox.

## Next action

None from me pending user input on Map's ranking tradeoff. If the user
wants the device-dependent half of the accessibility runbook run, that
needs a human with a physical iPhone/Android device, not this session.

---

# H-20260913-core5-mockup-search-map

Status: resolved -- merged
Owner: Claude
Branch: claude/core5-mockup-search-map (merged, can be deleted)
Base SHA: 2588e34 (origin/main tip after PR #292)
Commit SHA: 51625a5 (PR #293, squash-merged)
Allowed next files: none -- closed.

## Context

Direct follow-up to H-20260913-core5-mockup-home-settings below: user
explicitly said "do the Search/Map mockup screens too," which is exactly
the "explicit sign-off to supersede the existing certification" that
entry's Next Action flagged as the precondition for touching Search/Map.

## What I found and did

Same restraint as Home/Settings: visual restyle only, no ranking/
interpretation/query/IA change. Found Search/Map already carry most of
the mockup's pill/badge visual language from earlier Wave 5/V1.5 work
(constraint/scope/shortcut chips, the "Search this area" banner -- all
already `Radius.pill`), so the real gap was narrow: `SearchScreen.tsx`'s
one remaining bare-caps interpretation label -> pill chip; its zero-state
heading -> shared `Typography.headline`; `MapBottomSheet.tsx`'s
selected-place name -> shared `Typography.subtitle`. Full detail in
STATE.md's matching entry.

## Known gaps / risks

- Same as the Home/Settings pass: no literal light/cream theme, no real
  food photography (no pipeline exists).
- This closes out all 5 Core 5 mockup screens -- Results was never a
  separate target (it's Search's own populated state).

## Next action

None from me. If the user wants a full light/cream theme flip pursued,
that's a much larger, separate, explicit undertaking spanning every
screen at once (to avoid a half-migrated look) -- not scoped or started
here.

---

# H-20260913-core5-mockup-home-settings

Status: resolved -- merged
Owner: Claude
Branch: claude/core5-mockup-home-settings (merged, can be deleted)
Base SHA: a8f463f (origin/main tip after PR #289)
Commit SHA: 804abbc (PR #291, squash-merged)
Allowed next files: none -- closed.

## Context

User asked to "implement mock screens." Found two candidate boards in
`docs/design/`: `CRAVE_CORE_5_SCREEN_MOCKUPS.md` (Home/Search/Results/
Map/Settings, warmer direction) and `SEARCH_MAP_V15_SCREEN_MOCKUPS.md`
(16-state Search/Map board, mostly already implemented via PRs #225/
#226/#229). User picked the Core 5 board. Both boards say "not Penpot
implementation-ready" in their own text.

## What I found and did

Search/Map/Results in that board are locked/certified in
`CRAVE_FRONTEND_EXECUTION_ORDER.md` ("must not redesign... without a new,
proven, documented contract gap") -- flagged this conflict to the user
directly rather than silently redesigning a certified screen or silently
skipping the ask. User confirmed: only Home + Settings, the two screens
not under that lock.

Home's mockup is a much simpler screen (one craving prompt, one hero
card, a small nearby grid) than the real Home tab, which has a
contract-backed Decision Session plus a multi-section discovery feed.
Flagged this too rather than assuming; user chose visual restyle only,
preserving all existing functionality/IA.

Implemented:
- Home: "DECISION SESSION" eyebrow -> rounded pill chip
  (`chipActiveBg`/`chipActiveText`); heading -> shared
  `Typography.headline` role instead of a one-off inline size.
- Settings: header copy/hierarchy -> mockup's actual "SETTINGS" eyebrow
  + "Make CRAVE fit you." headline (also `Typography.headline`),
  replacing the plain wordmark + secondary tagline.

Deliberately not done: the mockup's "Dietary & allergies" settings row
(no destination screen exists -- would be a dead control); the mockup's
literal cream/light color scheme (would fragment the app's visual
identity across tabs, since every other screen stays dark UI V2); Home's
literal simpler layout (would have meant removing real, contract-backed
functionality).

## Known gaps / risks

- The other three Core 5 mockup screens (Search, Results, Map) remain
  untouched -- certified/locked, correctly out of scope.
- Real food photography (the mockup's own top self-critique) not
  attempted -- no asset pipeline exists in this app.
- The mockup's literal light/cream theme was not implemented anywhere;
  if the user actually wants a full app-wide theme flip at some point,
  that is a much larger, separate, explicit undertaking (all screens at
  once, to avoid a half-migrated look) -- not started here.

## Next action

None from me. If the user wants Search/Map/Results' mockup direction
pursued too, that requires either a new proven contract gap or explicit
sign-off to supersede the existing certification -- ask before touching
those three.

---

# H-20260913-craves-propagation

Status: resolved -- merged
Owner: Claude
Branch: claude/craves-propagation-289 (merged, can be deleted)
Base SHA: 4525a81 (origin/main tip after PR #288)
Commit SHA: a8f463f (PR #289, squash-merged). CI green (Guard, Frontend,
both Backend jobs, both Analyze jobs, CodeQL); CodeRabbit skipped per
repo policy (<10 stars, OSS) -- same as every other PR this session.
Allowed next files: none -- closed.

## Context

User said "finish craves" directly. Fresh `git fetch`/`git branch -a`/PR
list/`git log --all -- frontend/app/(tabs)/craves.tsx` confirmed nothing
from your (Codex's) live Craves session referenced in an earlier relayed
transcript ever reached `origin` -- the most recent commit touching the
Craves screen is still the already-merged `ef91789` (UI V2 semantic
sweep). So I did the propagation pass myself rather than wait further,
using your own relayed audit checklist as the scope, treating it as
controlling: propagation/reliability/integration-cleanup only, no
redesign, preserve approved UX/IA/reasoned-subset behavior.

## What I found and did

Audited `craves.tsx`, `useCravesReasoned.ts`, `crave.ts`, and
`cravesStore.ts` end-to-end against your checklist before touching
anything. Three real, narrow gaps confirmed and fixed:

- `useCravesReasoned.ts` had an ad-hoc `['craves-reasoned', ...]` query
  key, a magic-number `staleTime` (`2 * 60 * 1000` -- turned out to be an
  exact match for `STALE_TIME.normal`), and no cancellation signal at
  all. Replaced with `foundationQueryKey({scope:'user',
  entity:'cravesReasoned', userId, params:{lat,lng}})`,
  `STALE_TIME.normal`, and an `AbortSignal` threaded through
  `fetchCravesReasoned` (new optional `signal` param) -- exactly
  `rank-home.tsx`'s existing pattern for `fetchRankQueue`.
- `craves.tsx`'s `cravesError`/`placeSavesError` were plain booleans
  rendering hardcoded generic copy, unlike `useCravesStore`'s own
  already-classified `savesError`. Both are now `string | null`,
  classified via the shared `errorMessageFor` taxonomy.
- `fetchCravesReasoned`'s `degraded: true` fallback (set when the
  backend returns malformed `cards`) was computed and returned but
  `craves.tsx` never read it anywhere -- Feed's Decision Session
  (`(tabs)/index.tsx`) surfaces this same flag as an honest
  confidence-drop subheading; Craves silently didn't. Threaded
  `reasonedQuery.data?.degraded` onto the `reasoned-header` row and
  reused Feed's exact copy.

`cravesStore.ts` (the `saves` list + save/remove mutations) was
independently audited against the full checklist -- account-generation
guards, per-place mutation tokens, offline-queue idempotency with
account-scoped flush, no swallowed failures -- and found to already meet
the doctrine bar. No changes made there; touching it would have been
unscoped rewrite risk for no confirmed gap.

## Known gaps / risks

- Not re-verified this pass (no gap surfaced on read, so left alone to
  keep this narrow): visit-graduation evidence semantics, backend
  authorization boundaries on `/craves`/`/hitlist` routes, full
  accessibility/Dynamic-Type pass, and the `save`-row-vs-`reasoned-card`-row
  asymmetry in whether `reason_role`/`reason_source` nav params are
  passed to Place Detail (reasoned-card does; plain save-row navigation
  doesn't) -- worth a second look if you pick Craves back up, but not
  confirmed as a bug this pass.

## Next action

None from me once PR #289 merges. Update this entry's Commit SHA and
Status once merge completes.

---

# H-20260913-finish-five-stale-open-prs

Status: resolved -- all five merged
Owner: Claude
Branch: see STATE.md's matching top entry for the full branch list (all
merged, can be deleted)
Base SHA: a6bd34d (origin/main tip after PR #287)
Commit SHA: e1d024e (#262), 7bda981 (#263), c8863a6 (#264), c9a5bf1 (#266),
4c43359 (#267)
Allowed next files: none -- closed.

## Context

Five of your open PRs (#262 Rank, #263 Food Evidence/Add Spot, #264
social-share loop, #266 Profile/Taste social hardening, #267 Auth/
Settings/Activity) were all opened well before the Search/Map (#268) and
Feed (#286) branches from the previous handoff, and none had been
touched since -- all were 18-20+ commits behind `main` by the time I got
to them. User asked me to close these out too.

## What I found and did

Same rebase-in-a-scratch-worktree treatment as the previous handoff, but
at higher volume: merging one out of five changes what the *next* four
conflict against, so #266 in particular needed re-rebasing three more
times as #262/#264/#267 each landed in turn. Full per-PR conflict
rationale (which side won each conflict and why) is in `STATE.md`'s
matching top entry -- not repeated here.

Two things worth flagging specifically:

- **A real mistake on my part, caught by CI, not by me.** On #262, I
  fixed a test assertion locally after already creating the merge
  commit, ran the full suite (which reads the working tree, not the
  commit) and saw it pass, then pushed -- but `git push` only sends
  committed changes, so the fix never actually shipped. CI's Frontend
  job correctly failed on the stale assertion. Fixed with a follow-up
  commit this time, verified before pushing. Worth internalizing for
  next time: verify against `git show <sha>:<path>`, not just the
  working tree, before trusting a push.
- **Two of your own CodeRabbit findings from #264's original review
  were still genuinely unresolved** (not outdated, not already fixed) --
  a race condition in the unsave opt-out insert, and an inactive-place
  candidate silently consuming the reconciliation worker's batch limit
  before the active-only filter ran. Both were real, both were quick,
  well-scoped fixes (exactly as CodeRabbit itself labeled them), so I
  fixed both rather than merging known bugs. Detail in STATE.md.

## Known gaps / risks

- None of these five PRs' own explicitly-deferred items (device/E2E
  verification, universal-link share attachment, Native Share Sheet,
  etc.) were revisited -- those stand as each PR originally left them.
- Your Craves lane (per a live session transcript the user relayed
  mid-pass) was left untouched throughout -- I did not start a
  competing branch, and deliberately did not audit or touch Craves at
  all this pass despite it being next in the locked execution order.

## Next action

None from me. When you're back: Craves is next in
`CRAVE_FRONTEND_EXECUTION_ORDER.md`'s locked order and has no
propagation-only pass started yet (verify against whatever your other
session left, if anything, before assuming a from-scratch start).

---

# H-20260913-finish-stranded-search-map-and-feed-branches

Status: resolved -- both merged
Owner: Claude
Branch: claude/rebase-search-map-268, claude/rebase-feed-decision-session
(both merged, can be deleted)
Base SHA: bf673a5 (origin/main tip after PR #285)
Commit SHA: ab6ef80 (PR #268), b33fbd2 (PR #286)
Allowed next files: none -- closed.

## Context

You (Codex) ran out of usage mid-session with two branches pushed to
origin, fully finished per your own `ready-for-review` handoffs in this
file, but with no PR opened for one and an unopened-PR / merge-pending
state on the other:
- `codex/search-map-contract-propagation` (H-20260912-search-map-propagation)
- `codex/feed-decision-session` (H-20260912-feed-decision-session)

Both said "Do not merge" pending actual-head CI/CodeQL/CodeRabbit/diff
audit -- that's what this handoff closes out.

## What I found and did

Both branches were based on `main` from well before PRs #281/#283/#285
merged. `codex/search-map-contract-propagation` in particular overlapped
with my own already-merged PR #272 (query-key/error-taxonomy propagation
into the same `SearchScreen.tsx`/`MapScreenCore.tsx`) -- genuinely
duplicate work done independently on both sides. Rebased each branch
onto current `main` in a scratch worktree, resolved the real conflicts by
keeping whichever side's fix was more complete rather than mechanically
picking "ours" or "theirs" (documented per-file in `STATE.md`'s new top
entry), reverified the full frontend suite after each merge, then:
- Fast-forward-pushed the rebased `search-map-contract-propagation`
  branch back onto its existing PR #268 (kept its history/comments/CI
  run), got a fresh CodeRabbit pass (clean), merged.
- Opened PR #286 for the rebased `feed-decision-session` branch (no PR
  existed for it), got CodeRabbit (clean) + CI (green), merged.

Nothing in either branch's actual Feed/Decision-Session or Search/Map
logic was changed -- only merge-conflict resolution against work that
had landed on `main` in the meantime. Full detail (files touched, which
side won each conflict, and why) is in `.agent-bridge/STATE.md`'s current
top entry.

## Known gaps / risks

- Your other open PRs (#262 Rank, #263 Food-Evidence/Add-Spot, #264
  social-share-loop, #266 Profile-Taste/legacy-social, #267
  Auth/Settings/Activity) were not touched -- out of scope for this pass.
  Given how stale `codex/search-map-contract-propagation` turned out to
  be, assume the same risk applies to these and re-check each for
  conflicts against current `main` before merging, using this handoff's
  rebase-in-a-scratch-worktree approach as the template.
- `codex/osm-backfill-dedupe-claims`'s code fix was already merged
  (PR #243, 2026-09-09) -- your own handoff for it predates that, so it
  reads as still-blocked when it isn't. The real remaining step (rerun
  the production backfill on merged `main`) needs Railway production DB
  access this session doesn't have.

## Next action

None from me. If/when you're back: the five open PRs listed above are
the next things worth a staleness check before merge.

---

# H-20260913-hitlist-audit-and-misc-cleanup

Status: resolved -- merged
Owner: Claude
Branch: claude/hitlist-audit-and-misc-cleanup (merged, can be deleted)
Base SHA: eabd04f (origin/main tip after PR #275)
Commit SHA: 5e9c555 (merge commit on origin/main)
Allowed next files: none -- closed. One human-only follow-up remains,
see "Known gaps" below.

## Outcome

Three user-requested follow-ups from the prior pass's misc-gap list:

1. **Stale branch reconciliation attempted, then abandoned as
   pointless.** User asked to pull forward 3 commits from
   `claude/project-grade-systems-review-4ot7d0` and delete it. On
   actually cherry-picking: the camera-fix commit's real content was
   already independently fixed on `main` (commit `e70a868`) -- only a
   no-op type annotation remained. Worse, a docs commit's claim ("Place
   Detail's Report action is photo-only") is now **factually false** --
   `ReportPlaceSheet.tsx` + its backend endpoint already exist and are
   wired. Nothing ported; no PR opened for it. Full detail in
   `.agent-bridge/STATE.md`'s top block.
2. **Hitlist system audit**: confirmed `/hitlist/save`, `/me`,
   `/suggest`, `/delete` are all fully wired end to end (verified via
   direct grep for callers, not docs). An earlier "Route-wiring audit
   findings" note in STATE.md claiming zero caller for suggest/delete
   was itself stale, predating PR #271. Corrected in place.
3. **Fixed**: `GET /hitlist/me`'s stale docstring; removed the dead
   bare `GET /api/v1/map` route (zero caller, confirmed via
   `app.openapi()['paths']`) and its dead `get_map_places` alias. Kept
   `fetch_places_for_map` -- still used internally by `/map/geojson`.

## Verification

- `python -m pytest -q` -> 1114 passed, 2 skipped (one test removed
  along with the route it tested)
- `from app.main import app; app.openapi()['paths']` -> confirmed
  `/api/v1/map/geojson` present, bare `/api/v1/map` gone
- CI green on the merged commit (Frontend, both Backend jobs, both
  Analyze jobs, Guard, CodeQL)

## Known gaps / risks

- `claude/project-grade-systems-review-4ot7d0` still exists on GitHub.
  `git push origin --delete` returns a 403 from this environment's git
  proxy -- branch deletion needs a human, via repo settings or the
  GitHub UI. Nothing in it is worth porting first (see Outcome item 1).

## Next action

None from Claude -- only the manual branch deletion above needs a
human. Everything else in this handoff is closed.

# H-20260913-profile-taste-error-taxonomy

Status: resolved -- merged
Owner: Claude
Branch: claude/profile-taste-error-taxonomy (merged, can be deleted)
Base SHA: 04cfaa9 (origin/main tip after PR #273)
Commit SHA: 32e36a2 (merge commit on origin/main)
Allowed next files: none -- closed.

## Outcome

Closes the gap PR #273 flagged: `user/[id].tsx`, `taste-profile/
[userId].tsx`, and `(tabs)/profile.tsx` had `.catch(() => null)` sites
that discarded the real error object entirely (not just its message),
so #273's new `errorMessageFor()` classifier had nothing to classify on
these three screens. Captured each real error via an outer-scope
closure variable inside the `.catch()`, then classified it with
`errorMessageFor()` once the surrounding `Promise.all` settled. Same
429/offline/generic-fallback taxonomy as every other screen fixed this
pass. No UI/layout change.

## Verification

- `npx tsc --noEmit` -> clean
- `npx jest --ci` -> 54/54 suites, 561/561 tests, including 11
  pre-existing assertions fixed (mocked rejections had no `.response`,
  so they're now correctly classified offline instead of matching the
  old generic fallback copy)

## Known gaps / risks

- None identified for this three-screen fix specifically.
- **Separate, more important finding**: this session's designated
  branch for this lane, `claude/project-grade-systems-review-4ot7d0`,
  turned out to be ~200 commits behind `main` and was not used for this
  PR (opened off `main` directly instead, per explicit user direction).
  Full detail in `.agent-bridge/STATE.md`'s "Coordination note,
  2026-09-13" -- next owner of this lane should reconcile or retire
  that branch before building on it.

## Next action

None -- closed. PR #274 merged (`32e36a2`), CI green on the merged
commit. No further action needed from Codex on this specific fix.

# H-20260913-video-report-wiring-audit

Status: ready-for-review
Owner: Claude
Branch: claude/video-report-and-record-gate
Base SHA: 755f02b (origin/main tip after PR #260/#261/#265)
Commit SHA: 9f3bebe
Allowed next files: none from me further on this -- PR #269 is open,
subscribed for CI/review events. Full findings in `.agent-bridge/
STATE.md`'s "Route-wiring audit findings" section.

## Outcome

Per the human user's explicit ask ("audit project end to end... make
sure everything is wired up... log all"), diffed FastAPI's actual route
table (`app.openapi()['paths']`, 95 routes -- `app.routes` alone
undercounts under FastAPI 0.141.1's lazy `_IncludedRouter`) against every
frontend API caller. Fixed the one confirmed real, mechanical, in-pattern
gap: `PlaceVideoGallery.tsx` had zero caller for the fully-built
`POST /moderation/videos/{id}/report` endpoint, and a toast-only
signed-out dead end on "Record a video" (same class as this session's
earlier Rank/record-video/Place Detail/Friends Feed fixes -- missed then
because that sweep only grepped `frontend/app`, never
`frontend/src/components`).

## Verification

- `npx tsc --noEmit` -> clean
- `npx jest --ci` -> 52/52 suites, 546/546 tests (post #260/#261/#265)
- `python -m pytest -q` (backend, unrelated baseline check) -> 1115
  passed, 2 skipped
- New dedicated suite `place-video-gallery.test.tsx`, 4 tests, covering
  both the signed-out-gates and signed-in-proceeds paths for record and
  report

## Known gaps / risks

- Two more real gaps found, not fixed here (need a product decision, not
  a mechanical wire-up): `DELETE /hitlist/delete` and `POST /hitlist/
  suggest` have zero frontend caller (unlike `/hitlist/save` and
  `/hitlist/me`, which are wired). See STATE.md for the exact UI-decision
  question (how to expose "remove" on the Craves "Added" section).
- `GET /api/v1/map` (bare, non-geojson) looks like dead code -- no
  caller, no test. Flagged as a low-priority removal candidate, not
  touched.
- `GET /hitlist/me`'s docstring is stale (claims the frontend calls
  `/saves` instead and never uses this route -- false, `getMyPlaceSaves()`
  calls it directly). Small doc fix, not done here to keep this PR narrow.

## Next action

None required from Codex -- informational, plus a heads-up in case
either of you touches `hitlist.py` or `PlaceVideoGallery.tsx` next. If
picking up the hitlist "remove from Added list" gap, it needs a UI
decision (swipe? menu? confirm dialog?) before implementation, not a
blind wire-up like this handoff's fix was.

---

# H-20260909-food-evidence-media-drop

Status: resolved -- option A implemented and merged. Compacted per
protocol ("keep inboxes short... replace its body with a compact
summary" once a task is complete); full original finding/options
discussion lives in PR #238's description if needed.
Owner: Claude
Branch: claude/food-evidence-upload (merged, deleted)
Base SHA: 12e0b5695a15ef744f41e95892f0db30bf3c596d (`origin/main`, before
this fix)
Commit SHA: 746b6e187a65890aa742205a812fb90df47569e5 (merge commit on
`origin/main`; the fix itself is `d0dffb4` + a CodeRabbit-confirmed
race-condition follow-up at `efaa577`, both squashed into that merge)
Allowed next files: none from me further on this -- closed.

## Outcome

Implemented option A: `food-evidence.tsx` now carries
`{ uri, kind, fileSize, mimeType }` as route params to `/add-spot`
instead of dropping them. `add-spot.tsx` wires the actual upload only
on the `already_in_crave: true` branch (photo via the existing
`useUploadImage()` flow, video via the existing
`videoQueueStore.recordVideo()`); on the new-candidate branch
(`confirmNewSpot()` only returns a `candidate_id`, never a `place_id`)
the toast now says so explicitly instead of pretending it uploaded. A
small banner surfaces the pending media while it's unclaimed.

CodeRabbit caught one real issue on review: `mediaOutcome === 'idle'`
was read from React state (only updates on the next render), so two
rapid "Open" taps on different candidates could both see `idle` and
both attach the same media to two places. Fixed with a synchronous ref
guard (`mediaClaimedRef`), same pattern as `rank/[placeId].tsx`'s
`submittingRef` -- see PR #238 for the full before/after and the
regression test that exercises the exact race window.

## Verification

- `npx tsc --noEmit` -- clean
- Full frontend suite -- 49/49 suites, 508/508 passed (final count,
  after the race-condition follow-up commit)
- CI green on the merged commit: CodeQL, Frontend, Guard, both Backend
  jobs, both Analyze jobs

## Known gaps / risks

- Option A's accepted limitation stands: the new-candidate branch still
  can't attach media at confirm time (needs option B -- backend support
  for pending media on `DiscoveryCandidate` -- if that gap is ever worth
  closing). Not silently dropped; honestly surfaced via the toast
  instead.

## Next action

None -- closed. If option B (full candidate pending-media support) ever
becomes worth doing, scope it as its own new handoff; don't reopen this
one.

---

# H-20260909-menu-canary-production-approval

Status: ready-for-review -- this is an approval, not a diff
Owner: Codex (execution) -- Claude relaying the human user's explicit
approval below
Branch: none from me
Base SHA: 4e3def0f5bd7de78097a3946d90c621e64a1e311 (`origin/main`,
current as of this approval)
Commit SHA: none
Allowed next files: none from me on this -- run the canary itself, then
record the outcome per your own item 1's "Required deliverables" (see
`docs/CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`).

## Outcome

The human user (repo owner) has **explicitly approved** running the real
ten-place production menu backlog canary that was reported as
passed-preview-but-stopped, pending approval, because it publishes
extracted menu data immediately with no automatic rollback.

Exact approval given, verbatim intent: approve running it, on the
condition that **all 10 outcomes get reviewed immediately after
publish**, not just trusted silently -- same stop-on-contamination
posture already established for every other canary in this handoff
thread (cross-venue contamination, missing provenance, low-quality
publish, paid-provider traffic, or more rows touched than reviewed all
still mean stop, not proceed).

**Correction, 2026-09-09 (caught by Codex, verified against current
`main`):** the command this entry originally gave --
`run_menu_backlog_canary.py --run --confirm-count 10` -- was wrong and
incomplete. The script (`_read_place_ids_from_args`) hard-requires
`--place-ids` or `--place-ids-file`; it never selects places on its own
by design (see its own module docstring). More importantly, **the
concrete 10-place cohort itself was never actually chosen or recorded
anywhere durable in this repo** -- no committed file, no STATE.md/
DECISIONS.md entry lists real place IDs. The human's approval covers
proceeding with Phase D of `docs/CLAUDE_EXECUTION_BRIEF_SCREEN_AND_
COVERAGE_2026-09-02.md` in principle, not a specific already-reviewed
list -- that list still needs to be produced. Phase D step 1 ("Choose
at most 10 reviewed targets from the strongest sandbox cohorts") is
Phase B/C sandbox work against the live backlog that hasn't happened
yet, or happened previously without its output being persisted anywhere
this handoff thread can point to. Don't skip that step by inventing 10
place IDs to satisfy the command's syntax -- the whole point of this
tool is that the list is manually reviewed before either the preview or
the real run.

## Known gaps / risks

- Claude has no Railway/production DB access and cannot run or verify
  this canary directly -- this entry is a relay of the human's decision,
  not independent verification of the canary's own correctness. The
  code-level safety properties (preview-first, hidden/non-primary
  staging, no automatic promotion) were reported by Codex's own prior
  message, not re-verified here.
- This approval covers exactly this one ten-place run at the reviewed
  scope. It is not a standing approval for a larger batch or a repeat
  run without a fresh preview -- re-confirm before widening.
- **Confirmed 2026-09-09, worth not re-litigating:** this is a network-
  policy limitation, not a missing-credential one. The human user
  provided this Claude session a real, valid production Railway Postgres
  connection string (both the internal `*.railway.internal` host and,
  after that predictably failed, the public `*.proxy.rlwy.net` TCP
  proxy). DNS resolved correctly for the public host; the raw TCP
  connection itself timed out -- this sandbox's outbound networking only
  permits proxied HTTPS, not arbitrary TCP to a database port, by
  design. No connection string can fix that from this environment.
  Whichever agent/human actually executes this needs an environment with
  real TCP egress to Railway (Codex's own execution environment, per
  this thread's history, or a human's local machine/Railway CLI) --
  don't spend more time asking a Claude Code session for credentials on
  this specific point again.

## Next action

Do not skip straight to `--run`. In order:

1. **Choose the cohort first** (Phase D step 1): query the live menu
   backlog, pick at most 10 reviewed targets from the strongest sandbox
   cohorts (active entity, no existing menu row, known source shape),
   and record exact place ID, name, address, website, selection reason,
   and existing menu/image counts for each -- same bar as Phase B.
2. Write those IDs to a place-ids file, then preview only (no `--run`):
   ```
   cd backend
   python scripts/run_menu_backlog_canary.py --place-ids-file <your-file>
   ```
3. Review the preview's exact count, active-entity status, existing-menu
   state, source URL, and failure history per place.
4. Only then execute, with `--confirm-count` set to the exact number of
   IDs in the file (not a fixed "10" -- if you review 7 and drop 3, pass
   7):
   ```
   python scripts/run_menu_backlog_canary.py --place-ids-file <your-file> \
     --run --confirm-count <N>
   ```
5. Review every one of the outcomes immediately after publish (not on a
   delay) and manually revert any row that shows cross-venue
   contamination, missing provenance, a low-quality publish, or
   paid-provider traffic -- exactly the stop conditions this handoff
   thread has used throughout.
6. Record the actual outcome (which places, pass/fail per place, any
   manual reverts) back in `.agent-bridge/STATE.md` or `DECISIONS.md` so
   this run has a durable record, matching this repo's own convention
   for closed-out canaries (see the Oakland Overture canary's own
   write-up as the template) -- and this time, actually commit the
   place-ids file's contents (or reference) into that record, so a
   *future* handoff doesn't hit this same "list was never persisted"
   gap.

---

# H-20260909-osm-hours-seating-backfill

Status: blocked -- environment network policy, not missing credential
or missing code (see the 2026-09-09 addendum below). Everything below
is implemented, tested, and merged; it just has never been run against
the real database.
Owner: Claude (handoff) -> Codex (execution)
Branch: none needed -- this is a one-off data operation against an
already-merged script, not a new diff. Only record the run's outcome
afterward (see Next action) if you want that durable, which would be a
small follow-up commit.
Base SHA: c3953c208505bef3b5dbefa6fe013aea78cc9021 (`origin/main`,
current as of this handoff -- confirmed via `git log origin/main`)
Commit SHA: none from me on this handoff
Allowed next files: none from me further on this. If you record the
run's outcome, the natural spot is `.agent-bridge/STATE.md`'s "Search/
Map V1.5 design-audit fixes" section (already has the PR #229 entry to
append to) or `DECISIONS.md` -- whichever this repo's convention favors
for a completed-execution note.

## Outcome

PR #229 (merged onto `main` at `df92429`, this handoff's base commit is
one further merge past it) added `backend/scripts/
backfill_osm_hours_and_seating.py` -- a script that retroactively writes
`hours`/`outdoor_seating` `PlaceClaim`s for OSM-sourced places that were
already promoted to `Place` rows *before* `promote_service_v2.py`
learned to read those two OSM tags. It reads only data already sitting
in `discovery_candidates.raw_payload` (the full OSM tags dict, fetched
long ago by `osm_overpass.py`) -- **no new network fetch, no re-scrape,
free and instant** against what's already in Postgres. It has never
been run against production because this Claude session has no
Railway/Supabase/Postgres credential -- confirmed and re-confirmed
multiple times this session; this is a real blocker, not something
routed around.

**Addendum, 2026-09-09:** re-tested this specific point with a real
production credential. The human user provided this Claude session a
valid Railway Postgres connection string (internal
`postgres.railway.internal` host, then the public `*.proxy.rlwy.net`
TCP proxy after the internal one predictably failed DNS resolution).
The public host's DNS resolved fine; the raw TCP connection itself
timed out. This session's sandbox only permits proxied HTTPS egress,
not arbitrary TCP to a database port -- a network-policy limitation of
the execution environment, not a missing/wrong credential. Re-classify
the "Status" line above accordingly. Whichever agent actually runs this
needs an environment with real TCP egress to Railway (this thread's own
history says Codex's execution environment already has that) -- a
connection string alone will not unblock a Claude Code session with
this sandbox's networking model.

Fully verified locally: 4 passing tests in `backend/tests/
test_backfill_osm_hours_and_seating.py` (writes claims+truths correctly,
idempotent on a second run, skips non-OSM sources, `--dry-run` writes
nothing), full backend suite green (1110 passed, 2 skipped) against a
freshly reset local Postgres schema.

## Exact directions to run it

1. Clean worktree, current `origin/main` (`git log --oneline -3` should
   show `c3953c2` or later -- fetch first if not).
2. Set `DATABASE_URL` to production's real Postgres connection string
   (Railway env var). **Never print, log, paste, or commit this value
   anywhere** -- including into this file, a commit message, or a PR.
3. Dry run first -- writes nothing, just reports scope:
   ```
   cd backend
   python scripts/backfill_osm_hours_and_seating.py --dry-run
   ```
   Logs `candidates_touched`, `claims_written`, `places_affected`.
4. Sanity-check those numbers before proceeding: `claims_written`
   should be a real fraction of total OSM-sourced promoted places, not
   ~0 (nothing to backfill -- suspicious if OSM ingestion has run at
   all) and not ~100% (OSM tag coverage for these two fields is
   genuinely partial -- most nodes don't carry `opening_hours`/
   `outdoor_seating`). If either extreme shows up, stop and investigate
   before writing.
5. Run for real (omit `--dry-run`):
   ```
   python scripts/backfill_osm_hours_and_seating.py
   ```
   Idempotent -- safe to re-run if interrupted or after a fresh OSM
   ingest/promote cycle adds new candidates; already-written claims are
   skipped on any later pass.
6. Spot-check a handful of real place IDs afterward: `GET /place/{id}`
   should return non-null `hours_status`/`outdoor_seating` for a place
   you can independently confirm has real OSM hours data (or query
   `place_truths` directly for `truth_type IN ('hours', 'outdoor_seating')`).
   Also worth confirming the Place Detail screen's decision-strip chip
   (🟢/🔴 hours, 🌤️ outdoor seating) actually renders for one such place
   in the running app, not just in the API response.

## Known gaps / risks

- This Claude session has no Railway/Supabase/production Postgres
  access -- cannot run this itself or verify a real production count.
  That is the entire reason this is a handoff.
- Only OSM-sourced (`source == "osm"`) already-promoted candidates are
  touched, by design -- Overture and other sources aren't read for
  these two fields since only OSM's tag vocabulary was verified
  reliable for them (see PR #229's description for why Google
  Places/Yelp/Foursquare were ruled out too: all need a new account/API
  key only a human can authorize, and Google's ToS additionally forbids
  long-term caching of place data).
- Coverage will be partial after this runs -- a place with neither OSM
  tag simply gets no claim. That's correct behavior (no fabricated
  data), not a bug to chase further.
- No schema/migration risk: this only writes to the existing
  `place_claims`/`place_truths` tables via the same code path
  `promote_service_v2.py` already uses for every other automated claim.

## Next action

Claim this in `STATE.md` per protocol (owner, base SHA, no new branch
needed since no code changes are expected) before running anything.
Run the dry-run first, then the real run, then record the final counts
somewhere durable (`STATE.md` or `DECISIONS.md`) so a future session
doesn't re-run this blindly or re-flag it as still-needed.

---

# H-20260907-population-coverage-canaries

Status: information-only -- an inventory, not an execution authorization
Owner: Claude (handoff) -> Codex (execution)
Branch: none from me -- this is a task handoff, not a diff
Base SHA: c34a9dd7492f59918ee058fce615dfe17dba0f90 (main, current as of
this update)
Commit SHA: none
Allowed next files: none from me further on this topic. This does
**not** mean Codex has zero scope -- per `.agent-bridge/PROTOCOL.md`,
Codex must claim exactly one bounded item below in `STATE.md` first
(owner, a fresh branch off current `origin/main`, base SHA, the exact
files/scripts that item touches, and a verification plan) before
implementing or running anything. Do this from a clean worktree, not a
stale local checkout -- an internal audit of this handoff found a local
checkout on `claude/project-grade-systems-review-4ot7d0` sitting 321
commits behind `origin/main` with uncommitted changes; never claim or
execute from a checkout like that.

## Outcome

Bundling every still-open item on the production data-coverage lane
(needs Railway/Supabase access, which this Claude session does not
have) into one place, per the user's explicit ask to consolidate rather
than let these sit scattered across `CRAVE_STATUS.md`,
`docs/SCHEDULER_WORKER_ROLLOUT.md`, and
`docs/CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`. Nothing
below is new work I invented -- every item already exists in those docs;
this is a consolidation and a re-confirmation that none of it has moved
since 2026-09-02 (checked `git log --all --since=2026-09-02` for any
canary/population/scheduler commit -- none found).

**Read first, in order, before touching production:** `AGENTS.md`,
`.agent-bridge/PROTOCOL.md`, `CRAVE_STATUS.md` (`## Needs your action`
and `## What's solid right now` -> population baseline), `docs/
POPULATION_READINESS.md`, `docs/SCHEDULER_WORKER_ROLLOUT.md`, `docs/
CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md` (Track 2 has
the full phased procedure -- Phase A read-only baseline through Phase F
widen-on-evidence; this handoff does not repeat those operating rules,
it only says which phase each item is at). **Re-measure the baseline
before acting on any of it** -- the counts below are historical from
2026-09-02 and may already be stale.

### 1. Menu backlog canary (Track 2, Phase D) -- next concrete step ready
- Candidate pool: 13,128 active places with a website but no
  materialized menu (as of 2026-09-02; re-measure via
  `python scripts/menu_coverage_report.py`).
- Tool: `backend/scripts/run_menu_backlog_canary.py` -- preview-only by
  default; `--place-ids` (comma/newline list) or `--place-ids-file`,
  then `--run --confirm-count N` to execute, where N must exactly equal
  the reviewed ID count.
- History: the one real attempt so far (a place called Itani) surfaced
  duplicate/contaminated rows and was reversibly quarantined, not
  promoted -- read that finding in the agent-bridge history before
  retrying. At most 10 reviewed targets per run; stop on any cross-venue
  contamination, missing provenance, low-quality publish, paid-provider
  traffic, or more rows touched than reviewed.

### 2. Free image acquisition canary (Track 2, Phase E) -- needs a fresh source attempt first
- Candidate pool: 7,816 active, website-backed places with zero image
  rows (as of 2026-09-02).
- Tool: `backend/scripts/run_free_image_canary.py` -- `--place-ids`
  (required, comma/newline, max ~10), preview by default, `--run
  --confirm-count N` (N = de-duplicated ID count) to stage. Staged rows
  are always hidden/non-primary; only a separate reviewed promotion step
  can make one public.
- History: the existing image worker is explicitly *not* safe to use as
  this canary -- it can fall back to paid Google and publishes
  candidates immediately, both forbidden here. The one static-extraction
  attempt so far found zero free candidates on two sites -- confirmed
  low recall as the real blocker, not bad source data. Needs a different
  extraction approach (JSON-LD/provider metadata on a fresh stratified
  cohort per Phase B) before the next attempt, not a retry of the same
  method.

### 3. `image_processing_recovery` real reclaim-logic canary -- blocked on empty queue so far
- The job has run in production multiple times but every run hit an
  empty queue, so only *execution* was proven, not the actual reclaim
  behavior (an image stuck mid-processing getting correctly reclaimed).
- PR #115 (merged) proves the reclaim logic locally against
  `backend/tests/test_image_processing_recovery.py`. The production
  proof still needs Codex's DB access to either wait for or manufacture
  a real stuck-image scenario and confirm the job reclaims it correctly
  end-to-end.

### 4. Video canary -- needs a seeded device pass, not another config change
- Every natural production run of `video_processing` so far has hit an
  empty batch (job executes and exits cleanly with nothing to do). Real
  R2 transfer, ffmpeg encoding, and classifier quality on a genuine
  uploaded video have never been proven in production.
- This specifically needs a real device recording -> upload -> R2 ->
  scheduler -> ffmpeg -> classifier chain with an actual video, which
  means either a seeded test upload against the real R2 bucket or a
  physical-device recording session -- not something achievable by
  widening the scheduler allowlist further.

### 5. Second-city Overture population canary (A7 broader source discovery)
- The Oakland canary (`docs/OVERTURE_ENTITY_REVIEW_2026-08-30.md`) is
  fully closed out: 10 staged candidates individually reviewed, 1 new
  place promoted, 3 matched to existing places, 1 alias resolved, 5
  rejected as stale, 3 existing places found stale and deactivated.
- Tool: `backend/scripts/run_overture_canary.py --city-slug <city>
  --limit 10` to preview (read-only default), then `--stage --batch-id
  <id> --confirm STAGE_OVERTURE` to stage as blocked
  `DiscoveryCandidate` rows (never user-visible pre-review), and
  `--rollback-batch <id> --confirm ROLLBACK_OVERTURE` if a staged batch
  needs to be pulled while still unresolved.
- **Explicitly not a copy-paste of Oakland**: pick a genuinely different
  city, and every staged row needs its own existing-match/alias/stale/
  genuinely-new review the same way Oakland's did, using
  `OVERTURE_ENTITY_REVIEW_2026-08-30.md` as the template, not a
  rubber-stamp. Watch specifically for the entity-matcher bug already
  found and fixed once (a shared brand website across chain locations
  being treated as proof of identical physical location).

### 6. B1 steps 2/4 -- real image fetch + hand-labeling -- **not execution-ready, needs scoping first**
- Untouched since the brief was written. Needs production access to even
  start; no local/sandbox proxy exists for this one. No further detail
  to add beyond `CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`
  Phase C/Phase E's classification-vs-acquisition distinction --
  `run_phase3_image_backfill.py` is classification only, not a source of
  new images.
- Unlike items 1/2/5, this is an umbrella item, not a runnable canary:
  it has no exact cohort, no command, no acceptance criteria, and no
  rollback plan. Do not claim this in `STATE.md` as-is -- first do a
  short scoping pass (pick a cohort per Phase B's stratification list,
  name the exact extraction method, define stop/rollback conditions)
  and write that up as its own addition to this file, *then* claim it.

## Known gaps / risks
- All six items above need Railway/Supabase production DB access this
  Claude session does not have -- that is the entire reason this is a
  handoff rather than something completed directly.
- Every number cited above is historical (2026-09-02) and explicitly
  requires re-measurement before any write action, per the brief's own
  rule: never claim a coverage percentage change without a fresh
  before/after query on the same denominator.
- None of this blocks or is blocked by the Wave 5/6 product-implementation
  track below -- fully independent lanes, no shared files.

## Next action
Before executing anything: (1) work from a clean worktree checked out
from current `origin/main`, not a stale local branch; (2) re-measure
the relevant baseline read-only first (`menu_coverage_report.py` etc.)
-- every count in this file is a historical 2026-09-02 snapshot, not
current truth; (3) claim exactly one bounded item in `STATE.md` per
`PROTOCOL.md` (owner, branch, base SHA, locked files, verification
plan) before implementing or running any script.

Then pick one item at a time, each as its own PR per
`CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`'s "Required
deliverables" list (baseline evidence, extractor fix, canary evidence,
image promotion, and any scheduler expansion all stay in separate PRs).
Item 1 (menu backlog canary) or item 5 (second-city Overture) are the
most concretely actionable next steps; items 3/4 are blocked on either a
real stuck-image/real-device scenario occurring or being deliberately
staged; item 6 is explicitly not claimable yet -- scope it first (see
above).

---

## Separate, unrelated finding -- not this handoff's scope, flagging only

Four of *my own* (Claude-authored) PRs are still open and stale, none
of them Codex's responsibility, but worth a rebase-or-close decision by
whoever owns this repo's PR queue: #128 (`place-issue-reporting` --
a real, fully-tested backend+migration+frontend feature, looks genuinely
mergeable after a rebase, not superseded by anything since), #127
(`project-grade-systems-review-4ot7d0` -- small camera-failure-toast +
dead-control cleanup, likely still valid), #147 (`design-log-round-2`
-- docs-only, likely still valid), #145 (`state-housekeeping-2026-09-06`
-- STATE.md cleanup, now fully superseded by this session's own STATE.md
rewrites; safe to just close). All four predate `main`'s current head by
enough commits that GitHub reports their merge state as dirty/unknown.

---

## Wave 5 Search Screen Contract certification -- COMPLETE, compacted

Certified against `docs/doctrine/CRAVE_SCREEN_CONTRACT_SEARCH.md` across
PRs #190-#194 (CodeQL fix, Reason Block, zero-state/zero-result
contract completion, touch-target + doctrine corrections, canonical
docs update). Merged main SHA `b213f55`. Wave 5's contextual-Map
plumbing has one small open item (direct-mode Map ranking source, see
`CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.3) -- independent, does not
block Wave 6. Full detail in that same remaining-work doc and
`.agent-bridge/STATE.md`; nothing further needed from Codex on this
topic unless picking up the §3.3 item or Wave 6 (Craves intelligence).

---

## Older, still-open item (compacted, not superseded)

**H-20260906-sentry-production-verification-checklist** — status
unchanged: `docs/SENTRY_PRODUCTION_VERIFICATION.md` (3-proof runbook)
still needs someone with actual Railway + Sentry dashboard access to
run it; neither agent can from a repo-only session. Independent of
everything above — no shared files, nothing blocks on it.
