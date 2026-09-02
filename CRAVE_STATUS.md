# CRAVE — Status

Single canonical status doc. Replaces `CRAVE_WHERE_WE_ARE.md`,
`CRAVE_STATE_OF_THE_APP.md`, `CRAVE_TOMORROW_PLAN.md`,
`CRAVE_FULL_STATUS.md`, `CRAVE_ERROR_LOG.md`, `CRAVE_REMEDIATION_PLAN.md`,
and `COWORK_SESSION_SUMMARY.md` (all deleted — content either stale,
already fixed, or folded in below). Keep this one updated instead of
starting a new status file.

**Other docs, and when to use them instead of this one:**
- `CRAVE_REMAINING_WORK.md` — full dated session log, every fix with root
  cause. Read this for *how* something was fixed, not just *whether*.
- `CRAVE_ALGORITHMS.md` — the 5 scoring/ranking formulas in detail.
- `docs/doctrine/` — long-term product vision (Decision Intelligence
  architecture, Product Intelligence Bible).
- `backend/docs/DEBUG_ENDPOINTS.md`, `frontend/docs/*` — feature-specific
  reference docs.
- `docs/CATEGORY_TAXONOMY_DESIGN_2026-08-31.md`,
  `docs/E2_E3_E10_PRODUCT_TRADEOFFS_2026-08-31.md` — the full reasoning
  behind "The Pass"'s decisions (E8/E2/E3/E10), including the options
  *not* chosen and why.
- `docs/SCHEDULER_WORKER_ROLLOUT.md` — the production scheduler's
  current state and full phased-enable plan.
- `.agent-bridge/STATE.md` — the most recent handoff between Claude and
  Codex; usually the single fastest way to see exactly what just
  happened and what's next, more granular than this doc.
- `CRAVE_FRONTEND_GUIDE_FOR_AI_EDITORS.md` — **local-only, gitignored,
  never commit.** House rules for AI editors working in this frontend.

Last updated: 2026-09-02 (Expo SDK 54→55 upgrade, code-level).

---

## Stack

Backend: FastAPI + SQLAlchemy + Alembic + Postgres (prod)/SQLite (tests),
Railway (GitHub-integration auto-deploy, `alembic upgrade head` on start),
separate `scheduler_worker` service for APScheduler jobs. Frontend:
Expo/React Native SDK 55 (React 19.2, React Native 0.83), expo-router,
Zustand, react-query, EAS builds. Auth: Supabase (JWKS, ES256).

## Test status

Backend: **1018 passed, 2 skipped** (`cd backend && python -m pytest -q`).
Frontend: **331 passed**, 34 suites (`cd frontend && npx jest`), `tsc
--noEmit` clean. An E2E Playwright smoke suite also exists (`frontend/e2e/`,
3 journeys) — not part of the Jest count above, run separately via
`npx playwright test`; see `frontend/e2e/README.md` for required env vars.
Branch protection on `main` is now genuinely live (not just a backlog
item): 6 required checks, strict freshness, 1 approving review, dismiss-
stale-approvals, conversation resolution, no force-push/deletion,
administrator bypass retained for the agreed small-fix lane.

## Needs your action (not something I can do)

- [ ] **Rotate `API_KEY`** — pasted in chat multiple times, treat as
  burned. It's `EXPO_PUBLIC_*` anyway (ships in the client bundle), so
  it was never a real secret — rotate and stop relying on it for
  anything sensitive.
- [ ] **Set `DEBUG_API_KEY` in Railway** — the `/debug/*` routes fail
  closed (503) until this is set; see `backend/docs/DEBUG_ENDPOINTS.md`.
- [ ] **Device verification** — fixed in code but still unconfirmed on an
  actual rebuilt device/simulator: global text-contrast fix, signed-out
  white-on-white fix, the missing-config error screen, the new "DECIDE
  NOW" Decision Session section on Feed, Leaderboard/Friends' new
  error-vs-empty distinction, `add-spot`'s real header title,
  record-video's now-hidden native header, the rank/comparison flow
  end-to-end, video record→upload→moderation→push pipeline, signed push
  delivery to a locked physical device, and now the Expo SDK 55 upgrade
  itself (an EAS build/prebuild has never run against it here — see
  "What's solid" below for what's verified and what isn't). (Map
  clustering and the Notifications settings row/tap-routing/
  `UIBackgroundModes` fix are now confirmed on a real iPhone 17 Pro
  Simulator against production data — see "What's solid" below.)
## What's solid right now

- **Expo SDK 54→55 upgrade done at the code/dependency level.** Every
  `expo-*` package, `react`/`react-dom` (19.1.0→19.2.0), `react-native`
  (0.81.5→0.83.10), and their native-module siblings
  (`react-native-reanimated`, `-screens`, `-gesture-handler`, `-maps`,
  `-worklets`) now match the exact versions SDK 55 bundles (read
  straight out of the installed `expo` package's own
  `bundledNativeModules.json`, not guessed) — this is what actually
  fixes the `expo-notifications` Keychain/persisted-registration read
  bug that was the whole reason for the upgrade. Caught and fixed two
  real hoisting/version issues a naive `npm install` would have masked:
  `@expo/vector-icons`'s unbounded `expo-font` peer dependency was
  auto-installing the newest published `expo-font` (SDK 57's line, not
  55's) since nothing pinned it directly — now pinned explicitly, along
  with `expo-asset`, so both hoist to one shared copy instead of a
  broken split tree. Separately, wiping `package-lock.json` to let the
  resolver recompute cleanly let `@shopify/flash-list` float from its
  deliberately-locked `2.0.2` to `2.3.2`, an unrelated version that
  ships ESM-only and broke Jest's transform — reverted to the exact
  pinned `2.0.2`, which has fully permissive peer deps and was never
  actually coupled to this SDK bump. `@testing-library/react-native`
  needed a real bump too (12.9.0→13.3.3, not the newer 14.x line, which
  replaces `react-test-renderer` with a new peer entirely) because
  `expo-router@55` now peer-requires `>=13.2.0`.
  Verified: full frontend suite still 331/331 passed across the same 34
  suites, `tsc --noEmit` clean, `npx expo config` resolves
  `sdkVersion: '55.0.0'` with no plugin/schema errors against the
  existing `app.json` (already had `newArchEnabled`/`edgeToEdgeEnabled`
  set, nothing else to migrate there), and `npm audit` still shows only
  moderate, build-tooling-only findings (19, down from 26 — same class
  as previously documented, nothing high/critical). **Not verified, and
  can't be from here:** an actual EAS build/prebuild has never run
  against these versions, and the Keychain bug this upgrade targets has
  never been reproduced or disproven on a real device in this project —
  that confirmation needs a physical device or EAS build, not more code
  (see "Needs your action" above).

- **"The Pass" shipped end-to-end, plus a gap-closure pass — 8 PRs
  (#100-#102 backend, #104-#106 frontend, #109 gap closure, #111 test
  coverage).** Category
  taxonomy extended to cuisine/venue/dietary/ownership/occasion/
  recognition, `specialty` retired at the DB level, and the Filter UI
  now actually groups by type instead of a flat list that silently hid
  every dietary/ownership/occasion/recognition category behind a
  blacklist. `HitlistSave` gains `visited`/`visited_at`/`notes` plus
  `PATCH /saves/{place_id}/memory`, with a real "I've been here" toggle
  and notes field on Place Detail, plus (PR #109) completing a ranking
  now atomically marks an existing direct save visited in the same
  transaction — exact-user/exact-place scoped, never creates a save,
  never touches discovery-intake rows, preserves an existing visit
  timestamp. A bulk `has_video` signal surfaces as a card badge on
  Feed/Search/Craves/Trending/Recommendations/Decision Session/saved-map
  (PR #109 closed the surfaces PR #102 missed) — Place Detail stays the
  only playback surface. E10 group compatibility stayed correctly
  un-built, held pending Decision Session proving itself solo at real
  volume. See `.agent-bridge/STATE.md` for the full per-PR breakdown,
  including several real bugs caught only by running tests, not reading
  the code: a VARCHAR(9) column too narrow for a new value (real-Postgres
  CI only), an unhandled promise rejection plus a QueryClientProvider
  requirement that broke 5 existing Map tests, and two claims in PR
  #109's own body ("cannot affect discovery-intake rows," "preserves an
  existing visit timestamp") that were true but had zero test coverage
  until independent review added it.

- **Standalone production scheduler is live with four safe free/local jobs.**
  Railway service `CRAVE-scheduler` deploys `main` using
  `cd backend && python -m app.scheduler_worker`. It now runs with
  `SCHEDULER_WORKER_ENABLED=true` and an exact allowlist containing only
  `moderation_queue_health_check`, `share_parser`,
  `image_processing_recovery`, and `video_processing`; deployment
  `38b0556b-e1e9-4395-afea-3c128300b327` logged every other job removed and
  `scheduler_worker_started jobs=4`. All three new jobs had zero actionable
  rows and passed separate no-op canaries. Share parsing and video processing
  subsequently fired naturally and succeeded; the natural video run
  (`3c0260b9-bdef-4631-a2c4-aca7e1d550f1`) completed with an empty batch and
  no error. R2 is wired through Railway references, Railpack installs ffmpeg
  7.1.5, and the build installs ai-edge-litert 2.2.0. Web health stayed fully
  nominal (`db/cache/worker=ok`). Paid Google image ingestion, bulk menu
  enrichment, discovery/population, scoring, and ranking remain disabled.

- **Live population baseline is now measured.** Production has 37,761 active
  places. Coverage is 2.66% for menus (1,005 places), 40.55% for any public
  image (15,313), 36.55% for a primary image (13,802), and 37.43% for a known
  website (14,133). The biggest free-source opportunity is the 13,128 active
  places with a website but no menu; 7,816 website-backed places have no
  public image. These are eligibility counts, not authorization to scrape or
  promote them without reviewed per-source canaries.

- **Oakland population canary applied and closed out.** All 10 staged
  Overture candidates were individually reviewed (existing-match/alias/
  stale/genuinely-new) before anything touched production — see
  `docs/OVERTURE_ENTITY_REVIEW_2026-08-30.md`. Result: 1 new place
  promoted (North Beach Sandwicheez, confirmed live via Place Detail/
  Search/Map/Feed), 3 candidates matched to existing places, 1 alias
  resolved (NIDO → Odin), 5 rejected as stale, and 3 already-live places
  found stale during the review and deactivated (old Forge, old NIDO,
  Tiger's Taproom — confirmed 404 post-deactivation). Entity matcher was
  also fixed in the process: a shared brand website across chain
  locations was being treated as proof of identical physical location,
  which would have wrongly merged the new Jackson Street location into a
  distant branch.

- Auth (Supabase JWKS), Feed, Map, Search, Craves/saves (offline outbox,
  idempotent), personal ranking (binary-insertion comparison, replay-safe),
  social layer (leaderboard/friends-feed/public profile), settings/legal.
- Backend hardening: two-key auth model (public app key vs. server-only
  debug key), fairness-reserve batching in image/menu background workers
  (prevents high-rank places from starving the rest of the catalog),
  offline-outbox idempotency, `try/finally` around every browser-process
  handle, percentile-based tiering computed per-request.
- Frontend hardening: stale-response race guards on every screen that
  fetches by a changeable key (place id, account, city) — Feed, Search,
  Map, add-spot, place detail, craves, rank flow, useTrending all
  confirmed guarded.
- Test coverage: every screen has a dedicated test file (302 frontend
  tests, grown from 172 over several sessions), plus a Playwright E2E
  smoke suite (3 journeys); dependency audit confirms all 26 current npm
  audit findings are build-tooling-only, zero runtime-reachable.
- Profile, Taste Profile, and public-profile screens (and Leaderboard/
  Friends Feed before them) all distinguish a failed fetch from
  genuinely-empty data now — no screen in the app silently shows "no
  data" when the real cause was a request failure.
- Decision Session shipped end-to-end: `GET /api/v1/decision-session`
  (best_fit/safe_bet/wildcard) plus a Feed "DECIDE NOW" section, built
  jointly (backend by Claude, frontend by Codex against a frozen
  contract) — see `docs/decision_session_spec.md`.
- Push notifications: registration, backend delivery (photo/video
  moderation outcomes), Settings status display + contextual opt-in,
  notification-tap routing, and sign-out unregistration all wired
  end-to-end (the register/unregister routes existed already; this pass
  was the missing control layer — see `src/services/pushNotifications.ts`).
  `app.json` now also declares the iOS `fetch`/`remote-notification`
  background modes the notification delegates require.
- First real production E2E evidence for this project: live Playwright
  runs against production (Feed→Detail, Search→Detail passed; Save→Craves
  honestly skipped, no seeded test account yet) and a real native iOS
  build — Xcode simulator installed, launched, and loaded live production
  Feed/Map data on an iPhone 17 Pro Simulator.
- Map is no longer a marker cloud: over-clustering was a real, confirmed
  bug (a geographic cell-size floor that stopped shrinking well before a
  user finished zooming in), now replaced with density-aware screen-space
  collision clustering, confirmed on-device (250 production places →
  roughly a dozen separated clusters). Map query failures now surface as
  retryable 503s instead of a false empty catalog, and tiers use the same
  stable per-city percentile snapshot Feed/Search already use, so a pin's
  tier no longer flips as you pan.
- Feed pagination is now cursor-based, not offset-based: `GET
  /api/v1/places/feed` freezes a bounded, scope-bound snapshot of up to
  200 ranked places for 15 minutes and hands back an opaque cursor, so
  discovery inserts between page fetches can no longer shift or duplicate
  results. The legacy offset `/places` contract is unchanged for other
  callers.
- Menu extraction hardened: a real bug (`ExtractedMenuItem(price=...)` —
  an invalid constructor argument that silently crashed JSON-LD extraction
  and the entire pattern-detector fallback family to empty results on
  every call) is fixed, with an AST-based static test that fails the build
  if that mistake is ever reintroduced anywhere in the menu service tree.
  Deterministic offline replay fixtures, snapshot coverage/drift
  diagnostics, and a safety-gated population preview CLI
  (`backend/scripts/populate_menus.py` — preview by default, requires
  `--execute --confirm POPULATE` to write anything) now exist.
- Population pipeline identity fixed: places with the same name in the
  same city (real chains/branches) can now coexist instead of colliding on
  a name-derived ID; new places get a candidate-derived UUID instead.
  Overture Maps discovery now surfaces real dataset/release failures as
  errors instead of silently recording them as successful empty runs.
- Menu item images are never written or served unmoderated: an
  in-progress change would have piped raw extracted `image_url`s straight
  to `/places/{id}/menu`, bypassing the mandatory `MenuImageBridge`
  classify/score/visibility-assign pipeline — caught before merge and
  reverted; that invariant ("no bypass") now has a regression test.
- Image backfill pipeline hardened: a place's first-ever photo being a
  user upload no longer permanently blocks the scheduled Google-photo job;
  a place stuck `image_blocked` or with accumulated failed attempts now
  gets rehabilitated after its next successful fetch instead of staying
  excluded forever; Google Places Photos (a paid API) is now only called
  when free sources (provider claims, the restaurant's own website) don't
  yield enough images, instead of unconditionally on every place.

## Known gaps — product, not bugs

- **Not personalized yet.** Tiers (CRAVE Pick / Hidden Gem / Worth
  Knowing / Explore) are city-percentile standing, objectively "how good
  is this place" — never "is this good for *you*." No taste model, no
  learned ranking exists yet, deliberately — waiting on real usage data
  before building it (see `docs/doctrine/`).
- **Place Detail already went through its redesign** (a real spec exists:
  `docs/doctrine/CRAVE_PLACE_DETAIL_SPEC.md`; implemented in
  `app/place/[id].tsx` — hero → identity → decision strip → "why this
  fits" → primary CTA → actions → menu → social, matching the spec's
  §3 order). Scored 77/100 confirmed, 79/100 provisional against the
  doctrine's §33 rubric (was 57 baseline) — short of the spec's 85+
  target, and every point still open needs an actual screenshot/device
  look (button-border tap-discoverability, whether the de-boxed "why
  fits" headline reads right), not more code. See
  `CRAVE_REMAINING_WORK.md`'s 2026-08-26 "controlled visual-language
  pass" entry for the full category breakdown.
- **Craves now remembers visited/notes** (E2, "The Pass"), including the
  auto-visited hook (ranking a place atomically marks an existing direct
  save visited — PR #109, gap-closure pass) — but still doesn't
  "resurface saved spots at the right time," that's a separate ranking/
  notification idea, not built. Video record has no discoverable entry
  point beyond a small chip on Place Detail —
  by design (E3), not an oversight; see "Design invariants — don't relitigate these"
  below before proposing a Feed action or a video tab.
- **Search is keyword matching**, no typo tolerance or intent parsing.
- **Category taxonomy is now real** (cuisine/venue/dietary/ownership/
  occasion/recognition, "The Pass" E8) and the Filter UI groups by it.
  What's still open: Option B (each type as its own persistent filter
  chip row, like price-tier already gets) is deferred until usage data
  shows people want that — the current sectioned-single-sheet UI is the
  deliberate v1, not a placeholder.

## Prioritized backlog

**P0** — ~~Require CI checks as branch-protection gates on `main`~~ — done.
~~Feed keyset pagination~~ — done, merged. ~~Map over-clustering~~ — done,
merged, confirmed on-device.

**P1** — ~~Run the menu-population one-city canary~~ — done, fully
applied (see "What's solid right now"). A second city needs its own
scoped entity review, not a copy-paste of this one. ~~Record-video
discoverability~~ — decided (E3, "The Pass"): Place Detail stays the
only playback surface, a has_video badge on Feed/Search/Craves cards
drives discovery instead; see "Design invariants — don't relitigate these" below.
~~Confirm the food-classifier runtime is installed in prod~~ — build logs
confirm `ai-edge-litert 2.2.0`; the 12 MB model is in deployed source and
ffmpeg 7.1.5 is installed in the scheduler image. ~~Prove the real ffmpeg+
classifier pipeline end-to-end~~ — done (PR #121): real ffmpeg frame
extraction from a genuine video container into the real TFLite model,
not mocked ffmpeg or a single static image — a real food video scored
0.972, a real non-food video scored 0.402 against the 0.8 threshold, both
correct. ~~Prove the real upload API -> DB -> scheduler-job -> classifier
chain end-to-end~~ — done (PR #122): `POST /videos/request` ->
`POST /videos/{id}/confirm` -> the real `process_pending_videos` job ->
real ffmpeg -> real classifier -> real approve/reject, all executing for
real in one run, with only the literal R2 network call stubbed (no R2
credentials exist in any dev/CI environment). What's still open is a
real *device-recorded* video through the *production* R2 endpoint
(server logic, up to and including the S3 API boundary, is now fully
proven; only the actual Cloudflare round trip and camera capture are
not) — that piece still needs a physical
device, not more code. Physical-device smoke pass (Auth/Feed/
Search/Place Detail/Save/Map/Upload/Offline/Push/**Decision Session**).
~~Build the Decision-Session auto-visited hook~~ — done (PR #109).

**P2** — ~~Recommendation Ledger fast-follows~~ — done. App Store prep
(hosted Privacy Policy URL, Apple Developer membership, screenshots —
needs the user, not buildable by an agent). ~~Visual regression / E2E
coverage~~ — started: `frontend/e2e/` has the 3 planned journeys
(Feed→Detail, Search→Detail, Save→Craves→Detail). The public Feed and
Search journeys passed against the production API; the authenticated
Save journey remains honestly skipped until a dedicated seeded account is
supplied (see `frontend/e2e/README.md`). ~~Expo SDK 54→55 upgrade~~ —
done at the code level (see "What's solid"); device/EAS-build
confirmation that it actually clears the persisted-registration warning
still needs a human (see "Needs your action").

**P3** — Taste modeling / learned ranking (after real usage data exists,
not before). Splitting the flat category taxonomy into real dimensions.

## What's next — pick a track

Two independent tracks, no overlap between them. Either can be picked up
cold from this doc alone.

**Production (needs Railway/Supabase access — Codex's lane):**
1. ~~Enable and prove `moderation_queue_health_check`, `share_parser`,
   `image_processing_recovery`, `video_processing`~~ — done (PRs #113,
   #114). All four are live on the exact allowlist, each passed a
   bounded zero-queue canary, and share/video have since fired
   naturally and succeeded. Web health and worker CPU/memory stayed
   nominal throughout. Menu enrichment, Google image ingestion,
   discovery/population, score recompute, and ranking remain disabled.
   Keep the kill switch ready; see `docs/SCHEDULER_WORKER_ROLLOUT.md`
   for full evidence and rollback steps.
2. A real synthetic test of `image_processing_recovery`'s actual reclaim
   behavior is queued and ready to run (see
   `.agent-bridge/claude-to-codex.md`) — every production run so far hit
   an empty queue, so only the job's execution was proven, not the
   reclaim logic itself. PR #115 (merged) proves that logic locally
   first; the production run still needs Codex's DB access.
3. The video canary also only ever saw an empty batch — real R2
   transfer/ffmpeg encoding/classifier quality on genuine uploaded media
   still needs a seeded device E2E pass, not another allowlist change.
4. Run `backend/scripts/run_menu_backlog_canary.py` (preview first, then
   `--run --confirm-count N`) against a small reviewed batch from the
   13,128 website/no-menu candidates — the one real attempt so far
   (Itani) surfaced duplicate/contaminated rows and was reversibly
   quarantined, not promoted; see the agent-bridge history for that
   finding before trying again.
5. Free image acquisition for the 7,816 website/no-public-image
   candidates needs its own source-specific canary (the existing image
   worker isn't safe as a first canary — it can fall back to paid Google
   and publishes candidates immediately); a first attempt found zero
   free candidates via static extraction on two sites, confirming low
   recall as the real blocker, not bad data.
6. A7 (broader source discovery), B1 steps 2/4 (real image fetch +
   hand-labeling) — untouched, need production access.

**Product (buildable without production access — Claude's lane):**
1. ~~The Decision-Session auto-visited hook~~ — done (PR #109,
   gap-closure pass): completing a ranking atomically marks an existing
   direct save visited, exact-user/exact-place scoped, never creates a
   save, never touches discovery-intake rows, preserves an existing
   visit timestamp. Both immediate and comparison-flow ranking paths
   covered.
2. ~~Recommendations/trending `has_video` test coverage~~ — done (PR
   #111): both routes now have a dedicated end-to-end test, each
   regression-checked against a deliberately broken version first.
3. E10 group compatibility — do not start, including the simplest
   option, until Decision Session has real proof it works solo. ~5
   outcome events exist as of 2026-09-01; 500 is the proposed
   reconsideration bar (a proposed number, not a hard fact — revisit if
   real usage suggests otherwise). When it's time, build in order: A
   (host proposes, group vetoes) → B (shared hard constraints) → C (full
   group-utility scoring, doctrine's real long-term objective) — never
   jump straight to C.
4. Filter UI Option B (dietary/occasion as their own persistent chip
   rows, not sheet contents) — only once usage data on the current
   sectioned sheet (shipped in "The Pass") shows real demand for it.
5. Physical-device smoke pass — see the P1 backlog item above; this one
   needs a human with a device, not more code.

## Design invariants — don't relitigate these

- City-percentile tier ≠ personal taste. Never conflate the two as
  personalization gets built.
- Log confirmed outcomes, not UI intent — a tap isn't a save.
- A retry preserves identity (reuse the same idempotency key); it never
  mints a new one per attempt.
- Make invalid states structurally impossible (`getTierForPlace()`,
  the two-key auth split) rather than documenting around them.
- **Video stays a Place Detail affordance, not a Feed action or its own
  tab** (E3, "The Pass") — the closest thing in this app's whole surface
  to TikTok's actual lane; doctrine explicitly warns against becoming
  "Yelp+TikTok+Beli+Maps+AI." Revisit only once real upload volume and
  badge tap-through data exist, not on a hunch.
- **Group mode must reduce voting work, not add a swiping ritual** (E10)
  — doctrine's own words: "not turn dinner into Tinder for five people."
  The easy build (everyone swipes, tally votes) is explicitly the wrong
  v1 by that standard.
- **`michelin_rated` is a recognition/badge, not a chosen identity tag**
  — kept in its own `CategoryType.recognition` bucket (E8) precisely so
  it doesn't get grouped with things a place opts into like `vegan` or
  `late_night`.
