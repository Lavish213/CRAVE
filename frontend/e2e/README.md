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

The suite is discovered correctly and the Playwright configuration passes
TypeScript validation. A real run against the locally configured environment
currently exposes these external/runtime blockers:

- Expo web displays an error because the root layout calls
  `ExpoNotifications.getLastNotificationResponse`, which is unavailable on
  web. The task brief explicitly forbids changing that layout in this pass.
- The configured API returned "Couldn't load places" and no city choices, so
  the Feed and Search journeys had no place data to exercise.
- Save -> Craves is intentionally skipped without a seeded account supplied
  through `CRAVE_E2E_EMAIL` and `CRAVE_E2E_PASSWORD`.

These are reported blockers, not test skips disguised as passing coverage.
