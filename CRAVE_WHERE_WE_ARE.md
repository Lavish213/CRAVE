# CRAVE — Where We Are Right Now

Snapshot as of 2026-08-25, end of this session. For what's next, see
`CRAVE_TOMORROW_PLAN.md`. For how the algorithms actually work, see
`CRAVE_ALGORITHMS.md`. For the long-term product/ranking doctrine, see
`docs/doctrine/`.

---

## Confirmed working, live, right now

- **Sign-in / sign-up** — fixed two stacked, unrelated bugs: EAS cloud
  builds never had real Supabase/backend env vars (only existed in a
  gitignored local `.env`, silently excluded from cloud build uploads),
  and the backend was verifying JWTs against a static HS256 secret that
  can't work at all against Supabase's newer asymmetric (ES256) signing.
  Confirmed live: real 200 in Supabase's own auth logs, app reaches
  profile setup without "Invalid token."
- **Feed screen** — loads real data, real places, real images.
- **Map screen** — loads, renders real place pins.
- **Tier badges (CRAVE Pick / Hidden Gem / Worth Knowing / Explore)** —
  rebuilt on city percentile standing instead of absolute score (the old
  version clustered almost every place into two tiers). Confirmed live
  via device logs: real spread across tiers (`new`, `solid`, `gem`,
  `elite`), not the flat two-tier clustering from before.
- **Record-video screen** — exists, reachable (via a place's detail page,
  not a global entry point — see gaps below), safe-area layout bug fixed
  (close button/record controls no longer risk sitting under the
  notch/home-indicator).

## Broken right now

- **Search returns zero results for every query.** The backend correctly
  finds matches (`total` count is right), but every single result
  silently fails to serialize before reaching the app (`items: []`
  always). Not reproducible against equivalent test data locally —
  something specific to production. The silent-failure logging has been
  fixed (was `logger.debug`, invisible at the app's log level; now
  `logger.exception` with full traceback) so the next attempt will
  actually surface the real error in Railway's logs instead of nothing.
  **This is the first thing to chase next session.**

## Known gaps, not bugs, deliberate product decisions pending

- **No global record-video entry point.** Only reachable by tapping into
  a specific place first. Fine as an MVP shape, but worth a deliberate
  call before launch, not an accident.
- **Photo/menu-photo upload is open to every signed-in user with zero
  review.** You want this restricted to admin/staff/trusted contributors,
  with a "suggest a photo" queue + approval + notify-on-use flow for
  everyone else. Scoped but not built — see `CRAVE_TOMORROW_PLAN.md` P1 #3.

## What shipped this session (chronological)

1. Video moderation, 30s-60s auto-highlight fallback, push notification
   plumbing, real exponential backoff for the offline video queue.
2. Real food-classifier model wired in (MobileNetV2 TFLite), replacing
   whatever placeholder existed before.
3. Two real bugs found via full code review: a crash-window data-loss bug
   in the video processing worker (R2 delete before DB commit), and a
   permanent-block bug in `image_worker.py`'s stale-refresh failure
   counter.
4. Two routes (`/categories`, `/cities`) found genuinely missing rate
   limiting — fixed.
5. Real in-app Privacy Policy and Terms of Service screens, replacing two
   dead placeholder links.
6. The EAS/env-var and JWKS auth fixes described above.
7. Percentile-based tier badges, described above.
8. Record-screen safe-area fix.
9. This session's remaining-work/algorithm/plan docs.

## Test status

Backend: 742 passing, 2 skipped, clean against fresh SQLite. Frontend:
136 passing, `tsc --noEmit` clean. All work pushed to
`claude/project-grade-systems-review-4ot7d0` (PR #48), CI green on every
commit.

## Deploy state — verify this first, next session

Multiple backend commits landed after the one confirmed Railway deploy
this session (auth fix). Confirm `git log --oneline -1` on your local
backend matches `origin/claude/project-grade-systems-review-4ot7d0`
before assuming any of the later fixes (percentile tiering, the search
logging fix) are actually live.
