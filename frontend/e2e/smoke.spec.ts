import { expect, Page, test } from '@playwright/test';

const PLACE_CARD_NAME = /, .+, (CRAVE Pick|Hidden Gem|Worth Knowing|Explore)$/i;

async function selectFirstCity(page: Page) {
  const city = page.getByRole('button', { name: /^Select / }).first();
  await expect(city).toBeVisible();
  await city.click();
}

async function firstFeedCard(page: Page) {
  const card = page.getByRole('button', { name: PLACE_CARD_NAME }).first();
  if (!(await card.isVisible().catch(() => false))) {
    await selectFirstCity(page);
  }
  await expect(card).toBeVisible();
  return card;
}

async function expectPlaceDetail(page: Page) {
  await expect(page).toHaveURL(/\/place\/[^/]+$/);
  await expect(page.getByTestId('place-detail-hero')).toBeVisible();
  await expect(page.getByRole('heading').first()).toBeVisible();
  await expect(
    page.getByRole('button', { name: /Save to Saves|Remove from Saves/ }),
  ).toBeVisible();
  await expect(page.getByText(/CRAVE PICK|HIDDEN GEM|WORTH KNOWING|EXPLORE/).first()).toBeVisible();
}

async function openTab(page: Page, name: 'Feed' | 'Search' | 'Craves') {
  const routes = { Feed: '/', Search: '/search', Craves: '/craves' } as const;
  await page.goto(routes[name]);
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('CRAVE', { exact: true })).toBeVisible();
});

test('Feed → Place Detail renders the decision surface', async ({ page }) => {
  const card = await firstFeedCard(page);
  await card.click();
  await expectPlaceDetail(page);
});

test('Search → Place Detail renders the selected result', async ({ page }) => {
  await openTab(page, 'Search');
  const input = page.getByLabel('Search input');
  await input.fill('pizza');

  const result = page.getByRole('button', { name: PLACE_CARD_NAME }).first();
  await expect(result).toBeVisible();
  await result.click();
  await expectPlaceDetail(page);
});

test('Save → Craves → Place Detail preserves the saved place', async ({ page }) => {
  const email = process.env.CRAVE_E2E_EMAIL;
  const password = process.env.CRAVE_E2E_PASSWORD;
  test.skip(!email || !password, 'Requires CRAVE_E2E_EMAIL and CRAVE_E2E_PASSWORD for a seeded test account.');

  const card = await firstFeedCard(page);
  const cardName = await card.getAttribute('aria-label');
  const placeName = cardName?.split(',')[0];
  if (!placeName) throw new Error('Feed card did not expose its place name.');

  await page.getByRole('button', { name: `Save ${placeName}` }).click();
  await page.getByRole('button', { name: 'Continue with email' }).click();
  await page.getByLabel('Email').fill(email!);
  await page.getByLabel('Password').fill(password!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('button', { name: `Save ${placeName}` })).toBeVisible();
  await page.getByRole('button', { name: `Save ${placeName}` }).click();
  await expect(page.getByRole('button', { name: `Remove ${placeName} from saves` })).toBeVisible();

  await openTab(page, 'Craves');
  const saved = page.getByRole('button', { name: new RegExp(`^${placeName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')},`) });
  await expect(saved).toBeVisible();
  await saved.click();
  await expectPlaceDetail(page);
});
