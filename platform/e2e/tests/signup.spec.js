import { expect, test } from '@playwright/test';

import { grantAccess, loginAsAdmin, signUp, uniqueEmail } from './helpers';

test('a new account signs up with a code, names itself and waits for access', async ({ page }) => {
  const email = uniqueEmail('signup');

  await signUp(page, email);

  await expect(page.getByText(`Your account ${email} is ready`)).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main' })).toHaveCount(0);
});

test('once an administrator grants access, the user reaches the home page', async ({
  page,
  browser,
}) => {
  const email = uniqueEmail('grant');
  await signUp(page, email);

  const admin = await browser.newContext();
  const adminPage = await admin.newPage();
  await loginAsAdmin(adminPage);
  await grantAccess(adminPage, email);
  await admin.close();

  await page.reload();
  await expect(page.getByRole('heading', { name: 'Welcome', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Home', exact: true })).toHaveAttribute(
    'aria-current',
    'page',
  );
});
