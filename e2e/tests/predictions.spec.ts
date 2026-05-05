import { test, expect } from '@playwright/test';
import { loginAsUser, ensureExperimentAndOpen } from './helpers';

test.describe('Predictions', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  // -------------------------------------------------------------------
  // Classification returns stable/unstable with confidence
  // -------------------------------------------------------------------
  test('classification returns result with confidence', async ({ page }) => {
    await ensureExperimentAndOpen(page);

    // Click the classify button
    await page.locator('button:has-text("Классифицировать")').click();

    // Wait for result -- should show either "Стабильный" or "Нестабильный"
    const classifyResult = page
      .locator('text=Стабильный')
      .or(page.locator('text=Нестабильный'));
    await expect(classifyResult).toBeVisible({ timeout: 30_000 });

    // The confidence percentage should be visible
    await expect(page.locator('text=Уверенность')).toBeVisible();

    // Inference time should be displayed
    await expect(page.locator('text=Время инференса')).toBeVisible();
  });

  // -------------------------------------------------------------------
  // Disruption prediction shows result
  // -------------------------------------------------------------------
  test('disruption prediction shows warning or normal', async ({ page }) => {
    await ensureExperimentAndOpen(page);

    // Click the disruption prediction button
    await page.locator('button:has-text("Предсказать срыв")').click();

    // Wait for prediction result
    const disruptionResult = page
      .locator('text=ПРЕДУПРЕЖДЕНИЕ')
      .or(page.locator('text=Норма'));
    await expect(disruptionResult).toBeVisible({ timeout: 30_000 });

    // Inference time should be displayed
    await expect(page.locator('text=Время инференса')).toBeVisible();
  });

  // -------------------------------------------------------------------
  // Disruption warning includes lead time when issued
  // -------------------------------------------------------------------
  test('disruption warning shows lead time if issued', async ({ page }) => {
    await ensureExperimentAndOpen(page);

    // Request disruption prediction
    await page.locator('button:has-text("Предсказать срыв")').click();

    // Wait for any result
    const resultLocator = page
      .locator('text=ПРЕДУПРЕЖДЕНИЕ')
      .or(page.locator('text=Норма'));
    await expect(resultLocator).toBeVisible({ timeout: 30_000 });

    // If a warning was issued, the lead time field should be shown
    const warningVisible = await page
      .locator('text=ПРЕДУПРЕЖДЕНИЕ')
      .isVisible()
      .catch(() => false);
    if (warningVisible) {
      await expect(page.locator('text=Заблаговременность')).toBeVisible();
    }
  });
});
