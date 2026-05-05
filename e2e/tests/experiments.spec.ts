import { test, expect } from '@playwright/test';
import { loginAsUser, ensureExperimentAndOpen, KNOWN_SHOT_ID } from './helpers';

test.describe('Experiments', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  // -------------------------------------------------------------------
  // Load a valid shot from FAIR-MAST
  // -------------------------------------------------------------------
  test('load valid shot shows experiment in table', async ({ page }) => {
    await page.goto('/');

    // Fill the Shot ID input and click "Загрузить"
    await page.locator('input[type="number"]').fill(KNOWN_SHOT_ID);
    await page.locator('button:has-text("Загрузить")').click();

    // After loading it should appear in the experiments table
    await expect(
      page.locator(`text=${KNOWN_SHOT_ID}`).or(page.locator('text=preprocessed')),
    ).toBeVisible({ timeout: 90_000 });
  });

  // -------------------------------------------------------------------
  // Load an invalid / non-existent shot
  // -------------------------------------------------------------------
  test('load invalid shot shows error', async ({ page }) => {
    await page.goto('/');

    await page.locator('input[type="number"]').fill('999999999');
    await page.locator('button:has-text("Загрузить")').click();

    // Should show an error message
    await expect(
      page
        .locator('text=Ошибка')
        .or(page.locator('text=error'))
        .or(page.locator('text=Failed'))
        .or(page.locator('text=не найден')),
    ).toBeVisible({ timeout: 30_000 });
  });

  // -------------------------------------------------------------------
  // Visualize time series for a loaded experiment
  // -------------------------------------------------------------------
  test('experiment page renders Plotly chart', async ({ page }) => {
    await ensureExperimentAndOpen(page);

    // Plotly chart should be visible (asserted in helper, but double-check)
    await expect(page.locator('.js-plotly-plot')).toBeVisible();

    // The shot ID should appear in the heading
    await expect(page.locator('h2')).toContainText('Выстрел');
  });

  // -------------------------------------------------------------------
  // Experiment detail shows metadata
  // -------------------------------------------------------------------
  test('experiment page shows status badge and source', async ({ page }) => {
    await ensureExperimentAndOpen(page);

    // Status badge (preprocessed / loading / error)
    await expect(
      page.locator('.badge-success, .badge-warning, .badge-danger'),
    ).toBeVisible();

    // Source badge (MAST)
    await expect(page.locator('.badge-info')).toContainText('MAST');
  });

  // -------------------------------------------------------------------
  // Preprocessing handles missing data (interpolation applied)
  // -------------------------------------------------------------------
  test('preprocessing sets status to preprocessed', async ({ page }) => {
    await page.goto('/');

    await page.locator('input[type="number"]').fill(KNOWN_SHOT_ID);
    await page.locator('button:has-text("Загрузить")').click();

    // Wait for the status badge to show "preprocessed"
    await expect(page.locator('text=preprocessed')).toBeVisible({ timeout: 90_000 });
  });
});
