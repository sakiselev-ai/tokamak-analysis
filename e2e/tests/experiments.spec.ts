import { test, expect } from '@playwright/test';
import { loginAsUser } from './helpers';

test.describe('Experiments', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  // -------------------------------------------------------------------
  // TC-001: Load a valid shot from FAIR-MAST
  // -------------------------------------------------------------------
  test('TC-001: Load valid shot', async ({ page }) => {
    await page.goto('/');

    // Fill the Shot ID input and click "Загрузить"
    await page.fill('input[type="number"]', '30420');
    await page.click('text=Загрузить');

    // The experiment may take a while to load from FAIR-MAST S3.
    // After loading it should show up in the experiments table with status
    // "preprocessed" or the shot id itself.
    await expect(
      page.locator('text=preprocessed').or(page.locator('text=30420')),
    ).toBeVisible({ timeout: 90000 });
  });

  // -------------------------------------------------------------------
  // TC-002: Load an invalid / non-existent shot
  // -------------------------------------------------------------------
  test('TC-002: Load invalid shot', async ({ page }) => {
    await page.goto('/');

    await page.fill('input[type="number"]', '999999999');
    await page.click('text=Загрузить');

    // Should show an error message (Russian "Ошибка" or English fallback)
    await expect(
      page
        .locator('text=Ошибка')
        .or(page.locator('text=error'))
        .or(page.locator('text=Failed'))
        .or(page.locator('text=не найден')),
    ).toBeVisible({ timeout: 30000 });
  });

  // -------------------------------------------------------------------
  // TC-003: Visualize time series for a loaded experiment
  // -------------------------------------------------------------------
  test('TC-003: Visualize time series', async ({ page }) => {
    await page.goto('/');

    // If experiments already exist, click the first "Открыть" button
    const openBtn = page.locator('button:has-text("Открыть")').first();

    // If there are no experiments yet, load one first
    if (!(await openBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      await page.fill('input[type="number"]', '30420');
      await page.click('text=Загрузить');
      await expect(page.locator('button:has-text("Открыть")').first()).toBeVisible({
        timeout: 90000,
      });
    }

    await page.locator('button:has-text("Открыть")').first().click();

    // Wait for the experiment page and verify a Plotly chart is rendered
    await expect(page.locator('.js-plotly-plot')).toBeVisible({ timeout: 15000 });
  });

  // -------------------------------------------------------------------
  // TC-012: Preprocessing handles missing data (interpolation applied)
  // -------------------------------------------------------------------
  test('TC-012: Preprocessing handles missing data', async ({ page }) => {
    await page.goto('/');

    // Load a shot — the backend preprocessing pipeline should interpolate
    // missing values and set the experiment status to "preprocessed".
    await page.fill('input[type="number"]', '30420');
    await page.click('text=Загрузить');

    // Wait for the status badge to show "preprocessed"
    await expect(page.locator('text=preprocessed')).toBeVisible({ timeout: 90000 });
  });
});
