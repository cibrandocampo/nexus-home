import { expect, test } from '@playwright/test';

import { createUser, loginAsAdmin, loginWithPassword, uniqueEmail } from './helpers';

const PASSWORD = 'e2e-user-password-1';

test.beforeEach(async ({ page }) => {
  await loginAsAdmin(page);
});

async function passwordUser(page) {
  const email = uniqueEmail('pw');
  await createUser(page, { email, method: 'Password', password: PASSWORD });
  await page.context().clearCookies();
  return email;
}

test('a password account signs in', async ({ page }) => {
  const email = await passwordUser(page);

  await loginWithPassword(page, email, PASSWORD);

  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible();
});

test('a wrong password is explained', async ({ page }) => {
  const email = await passwordUser(page);

  await loginWithPassword(page, email, 'not-the-password');

  await expect(page.getByRole('alert')).toHaveText('The code or password is not correct.');
});

test('repeated wrong passwords lock password login, even for the right one', async ({ page }) => {
  const email = await passwordUser(page);
  await loginWithPassword(page, email, 'wrong-password-0');
  const password = page.getByRole('textbox', { name: 'Password', exact: true });
  await expect(page.getByRole('alert')).toBeVisible();
  for (let attempt = 1; attempt < 5; attempt += 1) {
    await password.fill(`wrong-password-${attempt}`);
    // The alert stays from the previous attempt: wait for this attempt's answer instead.
    const answered = page.waitForResponse('**/api/auth/login/verify');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await answered;
  }

  await password.fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByRole('alert')).toHaveText(
    'Too many failed attempts. Try again in 15 minutes.',
  );
});
