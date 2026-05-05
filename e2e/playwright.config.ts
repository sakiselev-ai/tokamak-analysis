import { defineConfig } from '@playwright/test';

const isCI = !!process.env.CI;

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: isCI ? 2 : 0,
  workers: isCI ? 1 : undefined,
  forbidOnly: isCI,

  reporter: isCI
    ? [['junit', { outputFile: 'test-results/junit.xml' }]]
    : [['html', { open: 'never' }]],

  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
    actionTimeout: 10_000,
  },

  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
});
