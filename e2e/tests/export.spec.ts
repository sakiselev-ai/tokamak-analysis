import { test, expect } from '@playwright/test';
import { loginAsUser, getToken, ensureExperimentAndOpen } from './helpers';

test.describe('Export', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  // -------------------------------------------------------------------
  // Export experiment data as CSV
  // -------------------------------------------------------------------
  test('export CSV returns valid response', async ({ page }) => {
    const experimentId = await ensureExperimentAndOpen(page);
    const token = await getToken(page);

    const csvResponse = await page.request.get(
      `/api/v1/experiments/${experimentId}/export?format=csv`,
      { headers: { Authorization: `Bearer ${token}` } },
    );

    expect(csvResponse.status()).toBe(200);

    const contentType = csvResponse.headers()['content-type'] || '';
    expect(
      contentType.includes('text/csv') || contentType.includes('application/octet-stream'),
    ).toBeTruthy();

    const body = await csvResponse.text();
    expect(body.length).toBeGreaterThan(0);
    // CSV should contain a header row with comma-separated columns
    expect(body).toContain(',');
  });

  // -------------------------------------------------------------------
  // Export experiment data as JSON
  // -------------------------------------------------------------------
  test('export JSON returns valid response', async ({ page }) => {
    const experimentId = await ensureExperimentAndOpen(page);
    const token = await getToken(page);

    const jsonResponse = await page.request.get(
      `/api/v1/experiments/${experimentId}/export?format=json`,
      { headers: { Authorization: `Bearer ${token}` } },
    );

    expect(jsonResponse.status()).toBe(200);

    const contentType = jsonResponse.headers()['content-type'] || '';
    expect(contentType.includes('application/json')).toBeTruthy();

    const jsonBody = await jsonResponse.json();
    expect(jsonBody).toBeTruthy();
  });

  // -------------------------------------------------------------------
  // Export links are present on the experiment page
  // -------------------------------------------------------------------
  test('experiment page shows CSV and JSON export links', async ({ page }) => {
    await ensureExperimentAndOpen(page);

    // The export section should contain buttons for CSV and JSON
    await expect(page.locator('button:has-text("CSV")')).toBeVisible();
    await expect(page.locator('button:has-text("JSON")')).toBeVisible();
  });
});
