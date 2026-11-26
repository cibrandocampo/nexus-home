import { chromium, expect } from '@playwright/test';

import { ADMIN, loginWithPassword } from './tests/helpers.js';

// The administrator created from ADMIN_EMAIL has no name, so its first sign-in goes through the
// onboarding page. Complete it once here so every spec finds the admin in the same state.
export default async function globalSetup(config) {
  const { baseURL } = config.projects[0].use;
  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL });
  await loginWithPassword(page, ADMIN.email, ADMIN.password);
  await expect(page.getByRole('heading', { name: 'Welcome!' })).toBeVisible();
  await page.getByLabel('First name').fill('Ada');
  await page.getByLabel('Last name').fill('Admin');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Welcome', exact: true })).toBeVisible();
  await browser.close();
}
