import { defineConfig, devices } from '@playwright/test';

// The specs share one database and one administrator; they run one at a time so a guard such as
// "last administrator" sees a known state. Every spec creates its own users with unique emails.
export default defineConfig({
  testDir: './tests',
  globalSetup: './global-setup.js',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  outputDir: 'artifacts/test-results',
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'artifacts/report' }]],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:8000',
    locale: 'en-GB',
    colorScheme: 'light',
    actionTimeout: 15_000,
    navigationTimeout: 15_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
