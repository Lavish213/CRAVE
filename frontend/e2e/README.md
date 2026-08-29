# CRAVE web smoke tests

The Playwright smoke suite starts Expo web automatically and exercises the
real Feed, Search, Place Detail, and Craves UI against the configured API.

Required application configuration:

- `EXPO_PUBLIC_API_URL`
- `EXPO_PUBLIC_API_KEY`
- `EXPO_PUBLIC_SUPABASE_URL`
- `EXPO_PUBLIC_SUPABASE_ANON_KEY`

The Feed and Search journeys run signed out. The Save → Craves journey needs
a real seeded test account and is skipped unless these are set:

- `CRAVE_E2E_EMAIL`
- `CRAVE_E2E_PASSWORD`

Install Chromium once with `npm run test:e2e:install`, then run the suite with
`npm run test:e2e`. Never commit credentials or add a production auth bypass
for this suite.

If the Playwright browser CDN is unavailable but Google Chrome is already
installed, run with `PLAYWRIGHT_BROWSER_CHANNEL=chrome npm run test:e2e`.

## Current local verification

On 2026-08-28, the suite ran against the production Railway API from the
mobile-Chrome project:

- Feed -> Place Detail passed.
- Search -> Place Detail passed.
- Save -> Craves -> Place Detail was intentionally skipped because no seeded
  account was supplied through `CRAVE_E2E_EMAIL` and `CRAVE_E2E_PASSWORD`.

The production API must allow the exact Playwright web-server origin via
`CORS_ALLOW_ORIGINS` or browser preflights fail before any journey can reach
application data. Do not replace that narrow origin with `*`.
