import { test, expect } from '@playwright/test';
import { loginAsUser, getToken } from './helpers';

test.describe('Export', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  /**
   * Helper: ensure at least one experiment is loaded and navigate to its page.
   * Returns the numeric experiment id extracted from the URL.
   */
  async function navigateToExperiment(page: import('@playwright/test').Page): Promise<string> {
    await page.goto('/');

    const openBtn = page.locator('button:has-text("Открыть")').first();

    if (!(await openBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      await page.fill('input[type="number"]', '30420');
      await page.click('text=Загрузить');
      await expect(page.locator('button:has-text("Открыть")').first()).toBeVisible({
        timeout: 90000,
      });
    }

    await page.locator('button:has-text("Открыть")').first().click();

    // Wait for experiment page
    await expect(page.locator('.js-plotly-plot')).toBeVisible({ timeout: 15000 });

    // Extract experiment id from URL  /experiment/:id
    const url = page.url();
    const match = url.match(/\/experiment\/(\d+)/);
    expect(match).toBeTruthy();
    return match![1];
  }

  // -------------------------------------------------------------------
  // TC-008: Export experiment data as CSV and JSON
  // -------------------------------------------------------------------
  test('TC-008: Export CSV', async ({ page }) => {
    const experimentId = await navigateToExperiment(page);

    // The export links are plain <a> tags pointing to the API.
    // We verify that the CSV export endpoint responds with 200 and correct content type.
    const token = await getToken(page);

    const csvResponse = await page.request.get(
      `/api/v1/experiments/${experimentId}/export?format=csv`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(csvResponse.status()).toBe(200);

    const csvContentType = csvResponse.headers()['content-type'] || '';
    expect(
      csvContentType.includes('text/csv') || csvContentType.includes('application/octet-stream'),
    ).toBeTruthy();

    // Verify the body is non-empty
    const csvBody = await csvResponse.text();
    expect(csvBody.length).toBeGreaterThan(0);
  });

  test('TC-008: Export JSON', async ({ page }) => {
    const experimentId = await navigateToExperiment(page);

    const token = await getToken(page);

    const jsonResponse = await page.request.get(
      `/api/v1/experiments/${experimentId}/export?format=json`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(jsonResponse.status()).toBe(200);

    const jsonContentType = jsonResponse.headers()['content-type'] || '';
    expect(jsonContentType.includes('application/json')).toBeTruthy();

    // Verify the body parses as valid JSON and is non-empty
    const jsonBody = await jsonResponse.json();
    expect(jsonBody).toBeTruthy();
  });
});
