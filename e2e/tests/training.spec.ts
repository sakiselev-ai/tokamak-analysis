import { test, expect } from '@playwright/test';
import { loginAsUser } from './helpers';

test.describe('Training', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  // -------------------------------------------------------------------
  // TC-007: Train a Random Forest model and observe progress
  // -------------------------------------------------------------------
  test('TC-007: Train Random Forest model', async ({ page }) => {
    await page.goto('/training');

    // The training page should be visible
    await expect(page.locator('h2:has-text("Обучение моделей")')).toBeVisible();

    // Select Random Forest model type (it is the default, but click to be explicit)
    await page.click('text=Random Forest (baseline)');

    // Ensure "classification" task is selected (default)
    const classificationRadio = page.locator('input[type="radio"][value="classification"]');
    await expect(classificationRadio).toBeChecked();

    // Optionally provide shot IDs (use a small set for speed)
    await page.fill('input[placeholder*="30420"]', '30420');

    // Click "Начать обучение"
    await page.click('button:has-text("Начать обучение")');

    // Wait for confirmation message (run_id shown in green text)
    await expect(
      page
        .locator('text=Обучение запущено')
        .or(page.locator('.text-success')),
    ).toBeVisible({ timeout: 15000 });

    // The training runs table should now contain at least one row
    await expect(page.locator('table.table tbody tr').first()).toBeVisible({
      timeout: 10000,
    });

    // The status badge should show one of the expected statuses
    const statusBadge = page.locator('.badge').filter({
      hasText: /Ожидание|Выполняется|Завершено|Ошибка/,
    });
    await expect(statusBadge.first()).toBeVisible({ timeout: 10000 });
  });
});
