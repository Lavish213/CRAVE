# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/a3-production-diagnosis
Base SHA: 8484f14
Scope: A3 only: read-only production diagnosis of the two historical
Square/Toast menu sources that recorded success without canonical published
items. Add only narrowly scoped diagnostic/test changes proven necessary by
the evidence. No retry, cleanup, or production mutation is authorized.
Locked files: .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md,
docs/A3_PROVIDER_FAILURE_DIAGNOSIS_2026-08-31.md,
backend/app/services/menu/extraction/js/js_hydration_detector.py,
backend/app/services/network/block_classifier.py,
backend/app/services/network/http_fetcher.py, and
backend/tests/test_a3_provider_regressions.py.
Verification plan: clean baseline backend suite; read-only Railway queries;
trace PlaceClaim/PlaceTruth/MenuSource/MenuItem lineage; focused tests for any
confirmed code defect; full backend suite; git diff check.
Implementation commit: 4891f0e
Verification result: focused extraction suite 27 passed; full backend suite
913 passed, 3 skipped, 32 warnings in 6.99s with TZ=UTC; git diff check clean.
Known gaps: no production retry was run; local Toast Playwright escalation
could not launch because the Chromium binary is absent.
Next action: Claude/CodeRabbit independently review commit 4891f0e. After
merge and deployment, any retry must be bounded and verified before A1.

## Prior Claude pass (completed before this claim)

Done this pass (since the last STATE.md update, which covered through
PR #78):
- E5 (empty/error-state audit): PR #79 merged. Found `ErrorState.tsx`
  never got the background-paint fix `EmptyState.tsx` received in
  a068d2b2 -- most of its 11 call sites are bare early-returns
  (`place/[id].tsx`, `rank/[placeId].tsx`, `profile.tsx`,
  `taste-profile/[userId].tsx`) with nothing else to paint over React
  Navigation's near-white default. One-line fix, same pattern. Rest of
  the empty/error-state landscape looked solid on inspection (map.tsx,
  search.tsx, craves.tsx all have distinct, well-designed states already)
  -- did not find more confirmed gaps, didn't force any.
- E6 (accessibility audit, doctrine §33.I): PR #80 merged. Scanned every
  TouchableOpacity/Pressable for icon-only content with no
  accessibilityLabel and no accessible Text child. 2 real gaps found,
  both in `PlaceVideoGallery.tsx` (video-thumbnail touchable, playback
  close button) -- fixed with accessibilityRole/Label + hitSlop (the
  hitSlop pattern already exists elsewhere in this codebase). Also
  added hitSlop to record-video's own close button (same 40x40 target,
  already had a label but no hitSlop). Broader finding (several screens
  have more touchables than labels) flagged but NOT acted on -- most wrap
  visible Text which VoiceOver already reads, confirming each one
  individually needs a dedicated pass, not a guess.
- E7 (onboarding/cold-start review): audited, no code change. Doctrine
  §18 calls for lightweight calibration (rank known restaurants, food
  comparisons) for new users, but doctrine §31 anti-pattern #36 explicitly
  says not to force onboarding questions CRAVE can learn naturally --
  and the Master Plan's own D1 gate says personalization isn't data-ready
  yet (324 events, 1 signed-in user). Current profile-setup.tsx is just a
  username claim, no forced calibration -- this is consistent with both
  constraints, not a gap. Confirmed via reading the actual screen, not
  assumed.
- E4 (Map/Search "search this area" sync) partially scoped, not built:
  map.tsx already has a working debounced auto-refetch-on-pan
  (`handleRegionChangeComplete` -> coverage-cache check via
  `isCoveredByPriorFetch` -> `fetch_places_for_map`'s existing lat/lng/
  radius_km bounding-box query). The Master Plan's "still unfinished"
  note likely means cross-screen sync (Map <-> Search tabs specifically),
  not within-map refetch, which already works. Did not build anything
  here -- the exact intended behavior needs a decision, not a guess, per
  this doc's own "product decision, lay out tradeoffs" standard for
  ambiguous UX asks (same category as E2/E3).

- (Recap from before, already merged) B1: PR #78. E9: PR #77.

Partial / needs your production access (unchanged):
- A3 (2 historical Square/Toast sources): ruled out one hypothesis via
  static tracing, needs your query access on the actual PlaceClaim/
  PlaceTruth rows.
- A1 (13,148-place backlog run): safe to run now that throughput is
  bounded (PR #74) -- needs production access to execute.
- A7 (source discovery): same.
- B1 steps 2 (real image fetch) and 4 (manual holdout labeling).

Locked files: none currently held.
Verification plan: full backend suite green on every backend change (908
passed, 2 skipped); frontend `tsc --noEmit` clean + `jest` 302/302 passed
on every frontend change; every new/changed test independently verified
to catch its corresponding regression before merge.
Next action: Codex, when back: (1) A1 backlog run, (2) A3 with actual
production row data, (3) B1 steps 2/4, (4) if you have a concrete answer
for what E4's "sync" should actually do (Map drives Search's results?
Search drives Map's viewport? both?), that would unblock building it --
otherwise it needs a product decision first, same as E2/E3.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
