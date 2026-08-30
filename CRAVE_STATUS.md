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

Last updated: 2026-08-29.

---

## Stack

Backend: FastAPI + SQLAlchemy + Alembic + Postgres (prod)/SQLite (tests),
Railway (GitHub-integration auto-deploy, `alembic upgrade head` on start),
separate `scheduler_worker` service for APScheduler jobs. Frontend:
Expo/React Native SDK 54, expo-router, Zustand, react-query, EAS builds.
Auth: Supabase (JWKS, ES256).

## Test status

Backend: **820 passed, 3 skipped** (`cd backend && python -m pytest -q`).
Frontend: **299 passed**, `tsc --noEmit` clean (`cd frontend && npx jest`).
An E2E Playwright smoke suite also exists now (`frontend/e2e/`, 3
journeys) — not part of the Jest count above, run separately via
`npx playwright test`; see `frontend/e2e/README.md` for required env vars.
Both clean as of this commit. CI runs both + a Postgres migration
round-trip on every push to `main`, not yet a required branch-protection
gate.

## Needs your action (not something I can do)

- [ ] **Rotate `API_KEY`** — pasted in chat multiple times, treat as
  burned. It's `EXPO_PUBLIC_*` anyway (ships in the client bundle), so
  it was never a real secret — rotate and stop relying on it for
  anything sensitive.
- [ ] **Set `DEBUG_API_KEY` in Railway** — the `/debug/*` routes fail
  closed (503) until this is set; see `backend/docs/DEBUG_ENDPOINTS.md`.
- [ ] **Device verification** — these are fixed in code but unconfirmed
  on an actual rebuilt device/simulator: map over-clustering fix,
  global text-contrast fix, signed-out white-on-white fix, the
  missing-config error screen, the new "DECIDE NOW" Decision Session
  section on Feed, Leaderboard/Friends' new error-vs-empty distinction,
  `add-spot`'s real header title, record-video's now-hidden native
  header, the new Notifications settings row (status display, contextual
  request, OS Settings link) and notification-tap routing, the
  rank/comparison flow end-to-end, video record→upload→moderation→push
  pipeline, push notification delivery.

## What's solid right now

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
- Test coverage: every screen has a dedicated test file (grew from 172
  to 299 tests this pass), plus a Playwright E2E smoke suite (3
  journeys); dependency audit confirms all 26 current npm audit
  findings are build-tooling-only, zero runtime-reachable.
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
- **Feed cursor pagination is implemented but awaiting independent review.**
  The Feed now freezes a bounded, scope-bound ordered-ID snapshot and chains
  opaque cursors, so discovery inserts cannot shift later pages. The legacy
  `/places` offset contract remains available to other callers, and the
  client-side de-dup guard remains as defense in depth. Live/native behavior
  must not be called complete until the review branch is merged and exercised.
- **32 flat categories** mix cuisine/meal-period/dietary/experience/
  ownership in one list — fine today, will constrain filtering/
  personalization eventually.

## Prioritized backlog

**P0** — ~~Require CI checks as branch-protection gates on `main`~~ — done:
six named checks, strict freshness, one approving review, conversation
resolution, and force-push/deletion protection are configured; administrator
bypass is retained for the agreed emergency/small-fix lane.

**P1** — Record-video discoverability (product decision: Feed action
vs. Place Detail affordance vs. tab). Confirm the food-classifier model
is actually installed in prod vs. degrading to its fallback path.
Physical-device smoke pass (Auth/Feed/Search/Place Detail/Save/Map/
Upload/Offline/Push/**Decision Session**).

**P2** — ~~Recommendation Ledger fast-follows~~ — done: Search, Craves,
and Map all already have `surface`-tagged Ledger instrumentation
(confirmed by re-checking the actual files, not just this doc — it was
stale here, already landed in an earlier session per
`CRAVE_REMAINING_WORK.md`'s 2026-08-26 entries). Feed keyset pagination is
implemented on `codex/feed-keyset-pagination` with stable snapshot insertion,
scope-mismatch, expiry, and client cursor-chaining regressions; independent
review and live verification remain before it is marked shipped. App Store prep (hosted Privacy Policy
URL, Apple Developer membership, screenshots — needs the user, not
buildable by an agent). ~~Visual regression / E2E coverage~~ — started:
`frontend/e2e/` has the 3 planned journeys (Feed→Detail, Search→Detail,
Save→Craves→Detail). The public Feed and Search journeys passed against the
production API; the authenticated Save journey remains honestly skipped until
a dedicated seeded account is supplied (see `frontend/e2e/README.md`).

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
