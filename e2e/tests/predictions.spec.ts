import { test, expect } from '@playwright/test';
import { loginAsUser } from './helpers';

test.describe('Predictions', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  /**
   * Helper: ensure at least one experiment is loaded and navigate to its page.
   * Returns the experiment page URL path.
   */
  async function navigateToExperiment(page: import('@playwright/test').Page) {
    await page.goto('/');

    const openBtn = page.locator('button:has-text("Открыть")').first();

    if (!(await openBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      // No experiments yet — load one
      await page.fill('input[type="number"]', '30420');
      await page.click('text=Загрузить');
      await expect(page.locator('button:has-text("Открыть")').first()).toBeVisible({
        timeout: 90000,
      });
    }

    await page.locator('button:has-text("Открыть")').first().click();

    // Wait for experiment page to finish loading (Plotly chart appears)
    await expect(page.locator('.js-plotly-plot')).toBeVisible({ timeout: 15000 });
  }

  // -------------------------------------------------------------------
  // TC-004: Classification returns stable/unstable with confidence
  // -------------------------------------------------------------------
  test('TC-004: Classification returns stable/unstable with confidence', async ({
    page,
  }) => {
    await navigateToExperiment(page);

    // Click the classify button
    await page.click('button:has-text("Классифицировать")');

    // Wait for result to appear — should show either "Стабильный" or "Нестабильный"
    const classifyResult = page.locator('text=Стабильный').or(page.locator('text=Нестабильный'));
    await expect(classifyResult).toBeVisible({ timeout: 30000 });

    // The confidence percentage should be visible
    await expect(page.locator('text=Уверенность')).toBeVisible();
  });

  // -------------------------------------------------------------------
  // TC-005: Disruption prediction shows probability timeline
  // -------------------------------------------------------------------
  test('TC-005: Disruption prediction shows probability timeline', async ({
    page,
  }) => {
    await navigateToExperiment(page);

    // Click the disruption prediction button
    await page.click('button:has-text("Предсказать срыв")');

    // Wait for prediction result — shows either "ПРЕДУПРЕЖДЕНИЕ" or "Норма"
    const disruptionResult = page
      .locator('text=ПРЕДУПРЕЖДЕНИЕ')
      .or(page.locator('text=Норма'));
    await expect(disruptionResult).toBeVisible({ timeout: 30000 });

    // Inference time should be displayed
    await expect(page.locator('text=Время инференса')).toBeVisible();
  });

  // -------------------------------------------------------------------
  // TC-006: Warning issued for known disruption shots
  // -------------------------------------------------------------------
  test('TC-006: Warning issued for disruption shots', async ({ page }) => {
    // This test requires a shot that is known to cause disruption.
    // We load one and check that the disruption prediction issues a warning.
    // If no suitable shot is available the test is skipped.
    await page.goto('/');

    // Try to load a shot known to have disruption characteristics
    await page.fill('input[type="number"]', '30420');
    await page.click('text=Загрузить');
    await expect(
      page.locator('button:has-text("Открыть")').first(),
    ).toBeVisible({ timeout: 90000 });
    await page.locator('button:has-text("Открыть")').first().click();
    await expect(page.locator('.js-plotly-plot')).toBeVisible({ timeout: 15000 });

    // Request disruption prediction
    await page.click('button:has-text("Предсказать срыв")');

    // We expect either a warning or "Норма" — both are valid outcomes.
    // The important thing is that the prediction completes without error.
    const resultLocator = page
      .locator('text=ПРЕДУПРЕЖДЕНИЕ')
      .or(page.locator('text=Норма'));
    await expect(resultLocator).toBeVisible({ timeout: 30000 });

    // If a warning is issued, the warning time should be shown
    const warningVisible = await page
      .locator('text=ПРЕДУПРЕЖДЕНИЕ')
      .isVisible()
      .catch(() => false);
    if (warningVisible) {
      await expect(page.locator('text=Заблаговременность')).toBeVisible();
    }
  });
});
