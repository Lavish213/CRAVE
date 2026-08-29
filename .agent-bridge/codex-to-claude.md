# H-20260829-feed-cursor-pagination
Status: ready-for-review
Owner: Codex
Branch: codex/feed-keyset-pagination
Base SHA: f8a7f751d9837314ab02eeed326348db7d32249e
Commit SHA: a5cf587
Allowed next files: none until review

## Outcome
Replaced shifting offset pagination on the main Feed with a bounded stable
snapshot. `GET /api/v1/places/feed` freezes up to 200 ranked place IDs for 15
minutes in the existing Redis/local response-cache tier and returns an opaque,
scope-bound cursor. Discovery inserts therefore cannot shift later pages. The
frontend Feed alone opts into the cursor endpoint; the existing `/places`
offset contract remains unchanged for other consumers. Unknown/expired cursors
return 410 and scope reuse returns 400, allowing a clean refresh instead of
silent duplication. The client de-duplication guard remains defense in depth.

## Verification
- `cd backend && /Users/angelowashington/CRAVE/venv/bin/python -m pytest -q
  tests/test_feed_cursor_pagination.py` -> 3 passed.
- `cd backend && /Users/angelowashington/CRAVE/venv/bin/python -m pytest -q`
  -> 820 passed, 3 skipped, 32 warnings in 14.22s.
- `cd frontend && ./node_modules/.bin/jest --runInBand
  __tests__/feed.test.tsx` -> 13 passed.
- `cd frontend && ./node_modules/.bin/jest --runInBand` -> 299 passed, 31
  suites; the repository's known open-handle warning remained after results.
- `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` -> clean.
- `git diff --check` -> clean.

## Known gaps / risks
- Live/native pagination has not been exercised; tests cover the API contract,
  insertion stability, cursor scope/expiry, and frontend cursor chaining.
- Redis is the shared cursor store in production. If Redis is unavailable and
  a later request reaches another backend worker, the local-cache fallback can
  produce an explicit 410 refresh; it will not silently return shifted data.
- Snapshots intentionally cap one feed session at 200 ranked IDs and expire
  after 15 minutes. This controls cache growth and is not infinite scrolling
  through the entire catalog.

## Next action
Fetch commit `a5cf587`, inspect the endpoint and cursor-store diff, rerun the
focused backend and frontend tests, and review the pull request. Do not mark
native behavior verified from automated evidence alone.
