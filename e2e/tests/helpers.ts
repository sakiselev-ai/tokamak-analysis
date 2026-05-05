import { type Page, expect } from '@playwright/test';

/** Default test user credentials. */
export const TEST_USER = {
  email: 'e2e-test@mephi.ru',
  password: 'testpassword123',
  fullName: 'E2E Test User',
};

/** A shot ID known to exist in FAIR-MAST. */
export const KNOWN_SHOT_ID = '30420';

/**
 * Register a test user (ignoring errors if already exists) and then log in via
 * the UI.  After this function returns the page is on the dashboard ("/").
 */
export async function loginAsUser(
  page: Page,
  email = TEST_USER.email,
  password = TEST_USER.password,
  fullName = TEST_USER.fullName,
) {
  // Try to register via API first (silent fail if user already exists)
  try {
    await page.request.post('/api/v1/auth/register', {
      data: {
        email,
        password,
        full_name: fullName,
        consent_given: true,
      },
    });
  } catch {
    // user may already exist -- that is fine
  }

  // Navigate to login page and authenticate through the form
  await page.goto('/login');
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL('/', { timeout: 15_000 });
}

/**
 * Retrieve the JWT access token stored in localStorage.
 */
export async function getToken(page: Page): Promise<string | null> {
  return page.evaluate(() => localStorage.getItem('access_token'));
}

/**
 * Ensure at least one experiment is loaded, then navigate to its detail page.
 * Returns the numeric experiment ID extracted from the URL.
 */
export async function ensureExperimentAndOpen(page: Page): Promise<string> {
  await page.goto('/');

  const openBtn = page.locator('button:has-text("Открыть")').first();

  // If there are no experiments yet, load one
  if (!(await openBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
    await page.locator('input[type="number"]').fill(KNOWN_SHOT_ID);
    await page.locator('button:has-text("Загрузить")').click();
    await expect(openBtn).toBeVisible({ timeout: 90_000 });
  }

  await openBtn.click();

  // Wait for the experiment page (Plotly chart renders)
  await expect(page.locator('.js-plotly-plot')).toBeVisible({ timeout: 15_000 });

  // Extract experiment ID from URL: /experiment/:id
  const url = page.url();
  const match = url.match(/\/experiment\/(\d+)/);
  expect(match).toBeTruthy();
  return match![1];
}
