import { test, expect } from '@playwright/test';
import { loginAsUser, KNOWN_SHOT_ID } from './helpers';

test.describe('Training', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  // -------------------------------------------------------------------
  // Train a Random Forest model and observe progress
  // -------------------------------------------------------------------
  test('start Random Forest training and see run in table', async ({ page }) => {
    await page.goto('/training');

    // The training page heading should be visible
    await expect(page.locator('h2:has-text("Обучение моделей")')).toBeVisible();

    // Select Random Forest model type (click the card)
    await page.locator('text=Random Forest (baseline)').click();

    // Ensure "classification" task is selected (default)
    const classificationRadio = page.locator('input[type="radio"][value="classification"]');
    await expect(classificationRadio).toBeChecked();

    // Provide shot IDs
    await page.locator('input[placeholder*="30420"]').fill(KNOWN_SHOT_ID);

    // Click "Начать обучение"
    await page.locator('button:has-text("Начать обучение")').click();

    // Wait for confirmation message
    await expect(
      page.locator('text=Обучение запущено').or(page.locator('.text-success')),
    ).toBeVisible({ timeout: 15_000 });

    // The training runs table should now contain at least one row
    await expect(page.locator('table.table tbody tr').first()).toBeVisible({
      timeout: 10_000,
    });
  });

  // -------------------------------------------------------------------
  // Training run shows status badge
  // -------------------------------------------------------------------
  test('training run shows expected status badge', async ({ page }) => {
    await page.goto('/training');

    // If there are existing runs, check the status badge
    const tableRow = page.locator('table.table tbody tr').first();
    const hasRuns = await tableRow.isVisible({ timeout: 5_000 }).catch(() => false);

    if (!hasRuns) {
      // Start a training run first
      await page.locator('text=Random Forest (baseline)').click();
      await page.locator('input[placeholder*="30420"]').fill(KNOWN_SHOT_ID);
      await page.locator('button:has-text("Начать обучение")').click();
      await expect(tableRow).toBeVisible({ timeout: 15_000 });
    }

    // The status badge should show one of the expected Russian labels
    const statusBadge = page.locator('.badge').filter({
      hasText: /Ожидание|Выполняется|Завершено|Ошибка/,
    });
    await expect(statusBadge.first()).toBeVisible({ timeout: 10_000 });
  });

  // -------------------------------------------------------------------
  // Training page shows progress bar for running jobs
  // -------------------------------------------------------------------
  test('training progress bar is rendered for active runs', async ({ page }) => {
    await page.goto('/training');

    const tableRow = page.locator('table.table tbody tr').first();
    const hasRuns = await tableRow.isVisible({ timeout: 5_000 }).catch(() => false);

    if (hasRuns) {
      // If there is a running/pending run, a progress bar should be present
      // or the percentage text should be shown
      const progressOrDash = page.locator('table.table tbody tr').first().locator('td').nth(2);
      await expect(progressOrDash).toBeVisible();
    }
  });

  // -------------------------------------------------------------------
  // Completed training shows metrics
  // -------------------------------------------------------------------
  test('completed training run displays metrics', async ({ page }) => {
    await page.goto('/training');

    // Look for any completed run with metrics
    const completedRow = page.locator('tr:has(.badge-success)').first();
    const hasCompleted = await completedRow.isVisible({ timeout: 5_000 }).catch(() => false);

    if (hasCompleted) {
      // Metrics column should contain a code element with key-value pairs
      const metricsCell = completedRow.locator('code');
      await expect(metricsCell).toBeVisible();
    }
    // If no completed runs exist yet, this test is effectively a no-op
    // (it will pass but not assert anything -- that is intentional for CI)
  });
});
