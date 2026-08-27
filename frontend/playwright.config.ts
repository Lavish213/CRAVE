import { defineConfig, devices } from '@playwright/test';

const browserChannel = process.env.PLAYWRIGHT_BROWSER_CHANNEL as 'chrome' | undefined;

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4197',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium-mobile',
      // The iPhone preset defaults to WebKit. Keep its mobile viewport and
      // touch behavior, but run Chromium so local/CI setup needs one browser.
      use: {
        ...devices['iPhone 13'],
        browserName: 'chromium',
        ...(browserChannel ? { channel: browserChannel } : {}),
      },
    },
  ],
  webServer: {
    command: 'npx expo start --web --port 4197',
    url: 'http://127.0.0.1:4197',
    // Never attach to an unrelated local site just because it owns the
    // expected port; a smoke suite testing the wrong app is worse than red.
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
