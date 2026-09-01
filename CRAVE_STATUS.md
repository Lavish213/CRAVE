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
- `CRAVE_FRONTEND_GUIDE_FOR_AI_EDITORS.md` — **local-only, gitignored,
  never commit.** House rules for AI editors working in this frontend.

Last updated: 2026-09-01 (The Pass merged).

---

## Stack

Backend: FastAPI + SQLAlchemy + Alembic + Postgres (prod)/SQLite (tests),
Railway (GitHub-integration auto-deploy, `alembic upgrade head` on start),
separate `scheduler_worker` service for APScheduler jobs. Frontend:
Expo/React Native SDK 54, expo-router, Zustand, react-query, EAS builds.
Auth: Supabase (JWKS, ES256).

## Test status

Backend: **976 passed, 2 skipped** (`cd backend && python -m pytest -q`).
Frontend: **302 passed**, 32 suites (`cd frontend && npx jest`), `tsc
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
  delivery to a locked physical device. (Map clustering and the
  Notifications settings row/tap-routing/`UIBackgroundModes` fix are now
  confirmed on a real iPhone 17 Pro Simulator against production data —
  see "What's solid" below.)
- [ ] **Expo SDK 54→55 upgrade** — `expo-notifications` 0.32.17 has a known
  Keychain/persisted-registration read error, fixed upstream only in the
  SDK 55 package line (`expo-notifications` 55.0.13, expo/expo#43829). Not
  urgent (app keeps running, Feed still loads) but the warning won't clear
  without the upgrade.
## What's solid right now

- **"The Pass" shipped — all four E8/E2/E3/E10 open product decisions
  resolved, 3 PRs (#100-#102).** Category taxonomy extended to
  cuisine/venue/dietary/ownership/occasion/recognition, `specialty`
  retired at the DB level. `HitlistSave` gains `visited`/`visited_at`/
  `notes` plus `PATCH /saves/{place_id}/memory`. A bulk `has_video`
  signal now surfaces on Feed/Search/Map cards (Place Detail stays the
  only playback surface — badge only). E10 group compatibility stayed
  correctly un-built, held pending Decision Session proving itself solo
  at real volume. See `.agent-bridge/STATE.md` for the full per-PR
  breakdown, including a real bug caught by CI's real-Postgres job (a
  VARCHAR(9) column too narrow for a new value — SQLite never would
  have caught it).

- **Standalone production scheduler is provisioned safely, default-off.**
  Railway service `CRAVE-scheduler` deploys `main` using
  `cd backend && python -m app.scheduler_worker`, but `SCHEDULER_WORKER_ENABLED=false` and
  no job allowlist keep it fail-closed. Its first deployment succeeded at
  SHA `93bfeac`; runtime logs say `scheduler_worker_disabled
  no_jobs_will_run`, and a read-only post-start database check found zero job
  runs. No paid provider/storage credentials or scheduler job were enabled.
  Enabling the first allowlisted job remains a separate production gate.

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
- **Craves is a bookmark list**, not yet "resurface saved spots at the
  right time." Video record has no discoverable entry point beyond a
  small chip on Place Detail.
- **Search is keyword matching**, no typo tolerance or intent parsing.
- **32 flat categories** mix cuisine/meal-period/dietary/experience/
  ownership in one list — fine today, will constrain filtering/
  personalization eventually.

## Prioritized backlog

**P0** — ~~Require CI checks as branch-protection gates on `main`~~ — done.
~~Feed keyset pagination~~ — done, merged. ~~Map over-clustering~~ — done,
merged, confirmed on-device.

**P1** — ~~Run the menu-population one-city canary~~ — done, fully
applied (see "What's solid right now"). A second city needs its own
scoped entity review, not a copy-paste of this one. Record-video
discoverability (product decision:
Feed action vs. Place Detail affordance vs. tab). Confirm the
food-classifier model is actually installed in prod vs. degrading to its
fallback path. Physical-device smoke pass (Auth/Feed/Search/Place
Detail/Save/Map/Upload/Offline/Push/**Decision Session**).

**P2** — ~~Recommendation Ledger fast-follows~~ — done. App Store prep
(hosted Privacy Policy URL, Apple Developer membership, screenshots —
needs the user, not buildable by an agent). ~~Visual regression / E2E
coverage~~ — started: `frontend/e2e/` has the 3 planned journeys
(Feed→Detail, Search→Detail, Save→Craves→Detail). The public Feed and
Search journeys passed against the production API; the authenticated
Save journey remains honestly skipped until a dedicated seeded account is
supplied (see `frontend/e2e/README.md`). Expo SDK 54→55 upgrade (clears
the persisted-registration warning; see "Needs your action").

**P3** — Taste modeling / learned ranking (after real usage data exists,
not before). Splitting the flat category taxonomy into real dimensions.

## Design invariants — don't relitigate these

- City-percentile tier ≠ personal taste. Never conflate the two as
  personalization gets built.
- Log confirmed outcomes, not UI intent — a tap isn't a save.
- A retry preserves identity (reuse the same idempotency key); it never
  mints a new one per attempt.
- Make invalid states structurally impossible (`getTierForPlace()`,
  the two-key auth split) rather than documenting around them.
