import { type Page } from '@playwright/test';

/**
 * Register a test user (ignoring errors if already exists) and then log in via the UI.
 * After this function returns the page is on the dashboard ("/").
 */
export async function loginAsUser(
  page: Page,
  email = 'e2e-test@mephi.ru',
  password = 'testpassword123',
  fullName = 'E2E Test User',
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
    // user may already exist — that is fine
  }

  // Navigate to login page and authenticate through the form
  await page.goto('/login');
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('/', { timeout: 15000 });
}

/**
 * Retrieve the JWT access token stored in localStorage.
 */
export async function getToken(page: Page): Promise<string | null> {
  return await page.evaluate(() => localStorage.getItem('access_token'));
}
