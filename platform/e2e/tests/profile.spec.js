import { expect, test } from '@playwright/test';

import {
  createUser,
  loginAsAdmin,
  loginWithCode,
  loginWithPassword,
  logout,
  uniqueEmail,
} from './helpers';

// A code (OTP) account with access, signed in on `page`.
async function signedInUser(page, browser) {
  const email = uniqueEmail('profile');
  const admin = await browser.newContext();
  const adminPage = await admin.newPage();
  await loginAsAdmin(adminPage);
  await createUser(adminPage, { email });
  await admin.close();

  await loginWithCode(page, email);
  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible();
  return email;
}

// Signs in again from a fresh browser: proves a preference was saved on the account, not in
// this browser's storage.
async function freshBrowserSignIn(browser, email) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await loginWithCode(page, email);
  return { context, page };
}

test('the language is saved on the account', async ({ page, browser }) => {
  const email = await signedInUser(page, browser);
  await page.goto('/profile');

  // The radio itself is visually hidden; people click its label.
  await page.locator('label', { hasText: /^Español$/ }).click();
  await expect(page.getByRole('heading', { name: 'Perfil' })).toBeVisible();

  await page.reload();
  await expect(page.getByRole('heading', { name: 'Perfil' })).toBeVisible();
  const other = await freshBrowserSignIn(browser, email);
  await expect(other.page.getByRole('heading', { name: 'Inicio', exact: true })).toBeVisible();
  await other.context.close();
});

test('the colour scheme is saved on the account', async ({ page, browser }) => {
  const email = await signedInUser(page, browser);
  await page.goto('/profile');

  // The radio itself is visually hidden; people click its label.
  await page.locator('label', { hasText: /^Dark$/ }).click();
  await expect(page.getByRole('radio', { name: 'Dark' })).toBeChecked();
  await expect(page.locator('html')).toHaveAttribute('data-mantine-color-scheme', 'dark');

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-mantine-color-scheme', 'dark');
  const other = await freshBrowserSignIn(browser, email);
  await expect(other.page.locator('html')).toHaveAttribute('data-mantine-color-scheme', 'dark');
  await other.context.close();
});

test('the time zone is saved on the account', async ({ page, browser }) => {
  const email = await signedInUser(page, browser);
  await page.goto('/profile');

  const zone = page.getByRole('button', { name: 'Time zone' });
  await zone.click();
  await page.getByRole('textbox', { name: 'Search time zone' }).fill('Lisbon');
  await page.getByRole('option', { name: /^Europe\/Lisbon/ }).click();
  await expect(zone).toHaveText(/^Europe\/Lisbon/);

  const other = await freshBrowserSignIn(browser, email);
  await expect(other.page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible();
  await other.page.goto('/profile');
  await expect(other.page.getByRole('button', { name: 'Time zone' })).toHaveText(/^Europe\/Lisbon/);
  await other.context.close();
});

test('a password account changes its password and signs in with the new one', async ({
  page,
  browser,
}) => {
  const email = uniqueEmail('password');
  const admin = await browser.newContext();
  const adminPage = await admin.newPage();
  await loginAsAdmin(adminPage);
  await createUser(adminPage, { email, method: 'Password', password: 'e2e-first-password-1' });
  await admin.close();
  await loginWithPassword(page, email, 'e2e-first-password-1');
  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible();
  await page.goto('/profile');

  // The key opens a dialog; its submit button has the same name as the key.
  await page.getByRole('button', { name: 'Change password' }).click();
  const dialog = page.getByRole('dialog', { name: 'Change password' });
  await dialog.getByRole('textbox', { name: 'Current password' }).fill('e2e-first-password-1');
  await dialog
    .getByRole('textbox', { name: 'New password', exact: true })
    .fill('e2e-new-password-1');
  await dialog
    .getByRole('textbox', { name: 'Repeat the new password', exact: true })
    .fill('e2e-new-password-1');
  await dialog.getByRole('button', { name: 'Change password' }).click();
  await expect(page.getByText(/Password saved/)).toBeVisible();
  await logout(page);

  await loginWithPassword(page, email, 'e2e-new-password-1');
  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible();
});
