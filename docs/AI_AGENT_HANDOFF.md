# CRAVE engineering handoff for ChatGPT, Codex, and Claude

Last verified: 2026-08-27 on `main` baseline `13a6541`, plus the GitHub AI-comments feature in PR #49.

## Mission

CRAVE should turn “I do not know what to eat” into a confident, explainable food decision. It is not another infinite restaurant directory. The product must combine trustworthy catalog evidence, hard constraints, place quality, current context, and—only when enough real outcomes exist—personal taste.

The near-term quality bar is a complete, reliable iOS product whose five tabs and core journeys work end to end. The long-term system is defined in `docs/doctrine/CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` and `docs/doctrine/CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md`.

## Read in this order

1. `AGENTS.md` — working rules and safety boundaries.
2. `CRAVE_STATUS.md` — canonical current state and prioritized backlog.
3. The relevant code and tests — final authority on whether a claim is still true.
4. `CRAVE_REMAINING_WORK.md` — historical root-cause detail only. Its early sections contain stale claims that later work superseded.
5. Relevant doctrine/spec files. Place Detail, for example, already has `docs/doctrine/CRAVE_PLACE_DETAIL_SPEC.md` and has already been reordered against it.

Do not manufacture work from an old audit. Recent examples of stale findings include the old bundle identifier, map marker cloud, signed-out contrast, missing Place Detail spec, and missing notification plumbing; all were already fixed or reclassified after code inspection.

## Current architecture

- Backend: FastAPI, SQLAlchemy, Alembic, Postgres in production and SQLite in tests.
- Hosting: Railway web service plus a separate scheduler worker.
- Frontend: Expo / React Native SDK 54, expo-router, Zustand, React Query, EAS builds.
- Authentication: Supabase using JWKS/ES256.
- Core product systems: Feed, Decision Session, Map, Search, Craves/offline save outbox, Place Detail, personal pairwise ranking, social/leaderboard, upload/moderation, push registration and delivery.
- Data systems: restaurant discovery, menu extraction, image ingestion, scoring, percentile tiers, recommendation-event ledger, background workers with fairness reserves.

## What is already solid

- Decision Session is shipped end to end: `best_fit`, `safe_bet`, and `wildcard` cards from `GET /api/v1/decision-session`, rendered on Feed.
- Saves are offline-capable and idempotent.
- Ranking comparisons are replay-safe.
- Feed, Search, Map, Place Detail, Craves, rank flow, add-spot, and trending have stale-response protections.
- Recommendation Ledger events already cover Feed plus Search, Craves, and Map. Do not recreate this instrumentation.
- Push registration, moderation-result delivery, Settings visibility/control, notification-tap routing, and sign-out unregistration exist.
- Place Detail already follows hero → identity → decision strip → why it fits → primary action → secondary actions → menu → social.
- Fetch failures on Leaderboard and Friends Feed are distinct from true empty states.

Verified before this handoff:

- Backend: 815 passed, 2 skipped.
- Frontend: 293 passed; TypeScript clean.
- GitHub AI assistant: 27 passed; TypeScript build clean.

## Product invariants

- City-percentile tier is objective local standing, never personal taste.
- Do not build learned personalization before enough real outcome data exists.
- Log confirmed outcomes, not merely taps or UI intent.
- Keep retrieval, ranking, reranking, and presentation separate.
- LLMs may parse intent or explain grounded evidence; they never own place, menu, hours, dietary, price, or user-history truth.
- Keep place affinity and dish affinity separate.
- A retry preserves the same idempotency identity.
- Explanations must be reconstructable from stored evidence.

## Priority execution plan

### P0 — establish release truth on a real iOS build

Do not start another visual rewrite first. Build and test on an iPhone simulator and, when available, a physical device. Capture screenshots, console/network failures, and exact reproduction steps.

Required smoke journeys:

1. Fresh install → OAuth sign-in → profile setup → sign-out → sign-in.
2. Feed → Decision Session → Place Detail → directions/website/menu.
3. Search → result → Place Detail, including no results, server failure, and retry.
4. Save online → Craves → remove; repeat offline → reconnect → verify outbox convergence.
5. Map load → city switch → clustering → marker/detail → recenter.
6. Add spot and photo; record video → upload → moderation → push notification → tap routing.
7. Rank a place through the full comparison flow and verify replay/idempotency.
8. Friends Feed, leaderboard, public profile, Settings, legal links, permission-denied states.

For every journey, test loading, empty, error, retry, signed-out, slow-network, and interrupted states—not only the happy path.

### P1 — close verified App Store blockers

- Require existing CI checks through GitHub branch protection.
- Resolve only defects reproduced by the P0 device pass.
- Add hosted Privacy Policy and support URLs, production screenshots, App Store metadata, and privacy declarations with the owner's input.
- Confirm production configuration and the classifier's real model path instead of silently relying on fallback behavior.
- Confirm scheduler-worker deployment and prevent simultaneous embedded scheduling/double work.
- Run a production-like migration, auth, API, upload, moderation, and push smoke test without exposing secrets.

### P2 — add missing release confidence

- Add deterministic E2E coverage for Feed → Detail, Search → Detail, and Save → Craves → Detail before expanding scope.
- Add screenshot/visual-regression coverage at representative iPhone sizes, dynamic type, light/dark behavior where supported, reduced motion, and long/localized text.
- Audit accessibility labels, roles, focus order, contrast, touch targets, and screen-reader announcements.
- Measure cold launch, Feed/Search/Map latency, image memory, scrolling, offline recovery, and crash-free behavior on release builds.
- Instrument decision-session impressions, selections, confirmed visits, saves, and dismissals with reconstructable recommendation provenance.

### P3 — improve the product after release truth is stable

- Make video contribution discoverable through one deliberate entry point; do not add another tab by reflex.
- Evolve Craves from a static bookmark list into timely resurfacing.
- Add intent discovery separately from exact search (for example, “spicy ramen under $20 open late”).
- Replace offset Feed pagination with cursor/keyset pagination only after telemetry confirms its real impact.
- Split the flat category list into cuisine, meal period, dietary, experience, and ownership dimensions.
- Build taste learning only from sufficient confirmed outcomes, preserving global quality, confidence, context, risk, and diversity as separate signals.

## Data and extraction work

Do not default to Google Places as the answer; cost is a product constraint. Improve coverage through the systems already present:

- Measure extraction coverage and freshness by city/source before adding crawlers.
- Prioritize official restaurant websites and structured data, then source-specific adapters and user-contributed evidence.
- Preserve source URL, observation time, parsing method, confidence, and raw evidence for menus/photos.
- Detect menu drift, stale hours, dead URLs, duplicate places, low-resolution/non-food images, and extraction failure reasons.
- Use fairness-reserve batching so low-ranked or repeatedly skipped places still receive attempts.
- Keep bounded retries/backoff and domain rate limits; never build an uncontrolled crawl loop.
- Any new third-party source must pass legal/terms, robots, privacy, reliability, and cost review before production use.

## Definition of done for every change

A change is not done because code was written or a single unit test passed. Completion requires:

1. The original gap was verified against current code or reproduced.
2. A focused regression test proves the failure and fix where automation is possible.
3. The implementation uses existing architecture instead of duplicating it.
4. Full affected tests and static checks pass.
5. Backend schema changes include a migration and clean upgrade verification.
6. Loading, empty, error, retry, auth, offline, and accessibility implications were considered.
7. Device-only behavior is explicitly listed as unverified until someone actually sees it.
8. Documentation updates replace stale claims rather than creating another conflicting status document.
9. No credentials, private user data, generated build artifacts, or local environment files enter the diff.

## Commands

```bash
# Backend
cd backend
python -m pytest -q

# Frontend
cd frontend
npm ci
npx jest --runInBand
npx tsc --noEmit -p .

# GitHub AI assistant (repository root)
npm ci --ignore-scripts
npm test
npm run build
```

Before reporting success, inspect `git diff`, run the applicable full suites, and state exact counts. Never claim a deploy, device result, App Store readiness, or production data outcome that was not directly verified.

## GitHub AI-comments feature

PR #49 adds collaborator-only `/ask`, `/review`, `/summarize`, and `/help`. It checks out trusted default-branch code, never executes pull-request code, redacts common credential formats, bounds context/output, and deduplicates responses.

It is inert until the owner sets `AI_COMMENTS_ENABLED=true` and an `OPENAI_API_KEY`. A private repository also requires the separate `PRIVATE_CODE_AI_ENABLED=true` consent gate. Exhausted API usage produces one safe failure response; it does not loop, resume itself, or hand work to other bots. Bot-authored commands are rejected to prevent runaway bot conversations.
