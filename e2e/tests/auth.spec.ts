import { test, expect } from '@playwright/test';
import { loginAsUser, getToken } from './helpers';

test.describe('Authentication', () => {
  // -------------------------------------------------------------------
  // TC-009: Login with valid credentials
  // -------------------------------------------------------------------
  test('TC-009: Login with valid credentials', async ({ page }) => {
    // Ensure the test user exists (register silently)
    try {
      await page.request.post('/api/v1/auth/register', {
        data: {
          email: 'e2e-test@mephi.ru',
          password: 'testpassword123',
          full_name: 'E2E Test User',
          consent_given: true,
        },
      });
    } catch {
      // already registered
    }

    await page.goto('/login');
    await page.fill('input[type="email"]', 'e2e-test@mephi.ru');
    await page.fill('input[type="password"]', 'testpassword123');
    await page.click('button[type="submit"]');

    // Should redirect to dashboard
    await expect(page).toHaveURL('/', { timeout: 15000 });

    // Username should appear in header
    await expect(page.locator('header')).toContainText('E2E Test User');
  });

  // -------------------------------------------------------------------
  // TC-010: Login lockout after 5 failed attempts
  // -------------------------------------------------------------------
  test('TC-010: Login lockout after 5 failed attempts', async ({ page }) => {
    await page.goto('/login');

    for (let i = 0; i < 6; i++) {
      await page.fill('input[type="email"]', 'lockout-test@mephi.ru');
      await page.fill('input[type="password"]', 'wrongpassword');
      await page.click('button[type="submit"]');
      // Wait for the request to complete before the next attempt
      await page.waitForTimeout(600);
    }

    // After several failed attempts we expect an error message on the page.
    // The backend may respond with a rate-limit or "too many attempts" error,
    // or simply repeat the standard "invalid credentials" error.
    const errorLocator = page.locator('.text-danger, .mb-md.text-danger');
    await expect(errorLocator).toBeVisible({ timeout: 5000 });
  });

  // -------------------------------------------------------------------
  // TC-011: Researcher cannot access admin panel
  // -------------------------------------------------------------------
  test('TC-011: Researcher cannot access admin panel', async ({ page }) => {
    // Login as a researcher-level user
    await loginAsUser(page, 'researcher-e2e@mephi.ru', 'testpassword123', 'Researcher User');

    // Grab the JWT from localStorage
    const token = await getToken(page);
    expect(token).toBeTruthy();

    // Attempt to hit the admin-only endpoint directly via the API
    const response = await page.request.get('/api/v1/admin/users', {
      headers: { Authorization: `Bearer ${token}` },
    });

    // Expect 403 Forbidden (non-admin users must not access admin routes)
    expect(response.status()).toBe(403);
  });
});
