import { test, expect } from '@playwright/test';
import { loginAsUser, getToken, TEST_USER } from './helpers';

test.describe('Authentication', () => {
  // -------------------------------------------------------------------
  // Login with valid credentials
  // -------------------------------------------------------------------
  test('login with valid credentials shows dashboard and username', async ({ page }) => {
    // Ensure the test user exists (register silently)
    try {
      await page.request.post('/api/v1/auth/register', {
        data: {
          email: TEST_USER.email,
          password: TEST_USER.password,
          full_name: TEST_USER.fullName,
          consent_given: true,
        },
      });
    } catch {
      // already registered
    }

    await page.goto('/login');
    await page.locator('input[type="email"]').fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.locator('button[type="submit"]').click();

    // Should redirect to dashboard
    await expect(page).toHaveURL('/', { timeout: 15_000 });

    // Username should appear in header
    await expect(page.locator('header')).toContainText(TEST_USER.fullName);

    // JWT should be stored
    const token = await getToken(page);
    expect(token).toBeTruthy();
  });

  // -------------------------------------------------------------------
  // Register a new account
  // -------------------------------------------------------------------
  test('register new account and land on dashboard', async ({ page }) => {
    const uniqueEmail = `e2e-reg-${Date.now()}@mephi.ru`;

    await page.goto('/login');

    // Switch to register mode
    await page.locator('button:has-text("Зарегистрироваться")').click();

    // Fill registration form
    await page.locator('input[type="text"]').fill('New Test User');
    await page.locator('input[type="email"]').fill(uniqueEmail);
    await page.locator('input[type="password"]').fill('newpassword123');
    await page.locator('button[type="submit"]').click();

    // Should land on dashboard
    await expect(page).toHaveURL('/', { timeout: 15_000 });
    await expect(page.locator('header')).toContainText('New Test User');
  });

  // -------------------------------------------------------------------
  // Logout redirects to login page
  // -------------------------------------------------------------------
  test('logout clears session and redirects to login', async ({ page }) => {
    await loginAsUser(page);

    // Click logout button in header
    await page.locator('header button:has-text("Выйти")').click();

    // Should redirect to login
    await expect(page).toHaveURL('/login', { timeout: 10_000 });

    // Token should be cleared
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(token).toBeNull();
  });

  // -------------------------------------------------------------------
  // Login with invalid credentials shows error
  // -------------------------------------------------------------------
  test('invalid credentials shows error message', async ({ page }) => {
    await page.goto('/login');

    await page.locator('input[type="email"]').fill('wrong@mephi.ru');
    await page.locator('input[type="password"]').fill('wrongpassword123');
    await page.locator('button[type="submit"]').click();

    // Should remain on login page with an error message
    const errorLocator = page.locator('.text-danger');
    await expect(errorLocator).toBeVisible({ timeout: 10_000 });

    // Should NOT redirect
    await expect(page).toHaveURL(/\/login/);
  });

  // -------------------------------------------------------------------
  // Login lockout after failed attempts
  // -------------------------------------------------------------------
  test('lockout or error after repeated failed logins', async ({ page }) => {
    await page.goto('/login');

    for (let i = 0; i < 6; i++) {
      await page.locator('input[type="email"]').fill('lockout-test@mephi.ru');
      await page.locator('input[type="password"]').fill('wrongpassword');
      await page.locator('button[type="submit"]').click();
      // Wait for the request to complete before the next attempt
      await page.waitForTimeout(500);
    }

    // After several failed attempts we expect an error message on the page
    const errorLocator = page.locator('.text-danger');
    await expect(errorLocator).toBeVisible({ timeout: 5_000 });
  });

  // -------------------------------------------------------------------
  // Researcher cannot access admin panel
  // -------------------------------------------------------------------
  test('researcher cannot access admin API', async ({ page }) => {
    await loginAsUser(page, 'researcher-e2e@mephi.ru', 'testpassword123', 'Researcher User');

    const token = await getToken(page);
    expect(token).toBeTruthy();

    // Attempt to hit the admin-only endpoint directly via the API
    const response = await page.request.get('/api/v1/admin/users', {
      headers: { Authorization: `Bearer ${token}` },
    });

    // Expect 403 Forbidden
    expect(response.status()).toBe(403);
  });
});
