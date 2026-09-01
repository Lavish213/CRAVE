# H-20260901-the-pass-gap-closure

Status: ready-for-review
Owner: Codex
Branch: codex/the-pass-gap-closure
Base SHA: d4bb22d
Commit SHA: 624e09f
Allowed next files: none until independent review

## Outcome

Audited the merged PRs #100-#106 from current `main` instead of duplicating
them, then closed two verified integration gaps:

1. `has_video` now uses the existing two-gate approved/visible query on
   Craves, saved-map, Decision Session, Trending, and Recommendations. Those
   surfaces previously defaulted to false even when the place had a visible
   approved video.
2. Completing a ranking now marks an existing direct save visited in the same
   database transaction as the ranking. It is exact-user/exact-place scoped,
   never creates a save, never touches discovery-intake rows, preserves an
   existing visit timestamp, and covers both immediate and comparison flows.

No frontend, scheduler, production configuration, or product-decision change.

## Verification

- `/Users/angelowashington/CRAVE/venv/bin/pytest -q backend/tests/test_ranking_service.py backend/tests/test_social_routes_integration.py backend/tests/test_saves_memory.py backend/tests/test_saved_places_map_query.py backend/tests/test_decision_session_route.py backend/tests/test_place_video_presence.py` -> `61 passed, 24 warnings`
- `/Users/angelowashington/CRAVE/venv/bin/pytest -q backend/tests` -> `981 passed, 2 skipped, 34 warnings`
- `git diff --check` -> clean
- fetched `origin/main`; branch base and remote main both resolved to `d4bb22d` before commit

Warnings are existing Pillow deprecation and short development JWT-key
warnings; no new test failure or skip was introduced.

## Known gaps / risks

- Trending's five-minute response cache can retain an older false default
  until its normal TTL expires after deployment; no cache schema migration is
  necessary.
- This was code/test verification only. Nothing was deployed or mutated in
  production, and no device behavior is claimed.

## Next action

Inspect `git show 624e09f` and independently verify the transaction placement,
cross-account isolation, no-implicit-save behavior, approved-video gates, and
full backend result. Request CodeRabbit on the PR and resolve every actionable
finding before merge.
