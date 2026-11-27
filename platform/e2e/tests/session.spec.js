import { expect, test } from '@playwright/test';

import { ADMIN, loginAsAdmin, logout } from './helpers';

test('an anonymous visitor is sent to the login page and back after signing in', async ({
  page,
}) => {
  await page.goto('/admin/users');

  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Email').fill(ADMIN.email);
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(ADMIN.password);
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page).toHaveURL(/\/admin\/users$/);
  await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible();
});

test('the session survives a reload (refresh cookie)', async ({ page }) => {
  await loginAsAdmin(page);

  await page.reload();

  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible();
});

test('after logging out, protected pages ask to sign in again', async ({ page }) => {
  await loginAsAdmin(page);

  await logout(page);
  await page.goto('/profile');

  await expect(page).toHaveURL(/\/login$/);
});
