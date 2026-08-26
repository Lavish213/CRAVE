# `/debug` router auth model

`backend/app/api/v1/routes/debug.py` exposes six diagnostic endpoints plus
`/version`. As of 2026-08-26 they are gated by two different mechanisms —
knowing which one applies to which route matters if you're calling these
by hand or adding a new one.

## Why there are two keys

`API_KEY` (header `x-api-key`, dependency `require_api_key` in
`app/core/auth.py`) is the app-wide key every other route in this backend
uses. The frontend sends it on every request via `EXPO_PUBLIC_API_KEY`,
which Expo compiles directly into the shipped JS bundle. Anyone who
extracts the app binary has this value — it is not a secret, only a weak
"this request came from some copy of the app" signal, and
`require_api_key` bypasses entirely when unset (dev-friendly).

That's fine for ordinary product routes, where real per-user authorization
comes from the Supabase JWT. It was never an acceptable boundary for this
router's sensitive endpoints: `recommendation-events` returns raw
per-user event rows, `scheduler` returns job-run internals, and
`map-query-plan`/`categories-query-plan`/`map-query-timing` run genuine
`EXPLAIN ANALYZE` queries against production data. Anyone with the bundle
key had the same access as an operator.

## `DEBUG_API_KEY` / `require_debug_api_key`

- Header: `x-debug-api-key`
- Env var: `DEBUG_API_KEY` — set **only** in Railway (or your local
  `.env`, ungitignored the same as every other secret). Never reference it
  from any `EXPO_PUBLIC_*` var; if it ever ends up in one, it has the same
  problem `API_KEY` had.
- **Fails closed.** Unlike `require_api_key`, an unset `DEBUG_API_KEY`
  rejects every request (503) — there is no open-mode bypass for raw data
  dumps and query-plan execution. If you don't want the debug router
  reachable at all in some environment, simply don't set it.
- Wrong or missing header with a configured key: 401.
- Applies to every route in this file except `/version`, which is
  intentionally public (a plain commit/environment lookup, no sensitive
  data) and carries no auth dependency at all — only the router-level
  `rate_limit`.

## Rotating

Rotate `DEBUG_API_KEY` in Railway like any other secret. Rotating it does
not require touching `API_KEY`/`EXPO_PUBLIC_API_KEY` — the two are
unrelated, and rotating the public one is a separate, independent
hygiene action (do it if it's ever been exposed, e.g. pasted in chat/logs,
but understand it does not by itself close the debug-endpoint gap this
document is about).
