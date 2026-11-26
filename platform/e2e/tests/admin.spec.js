import { expect, test } from '@playwright/test';

import { ADMIN, createUser, loginAsAdmin, openUser, startLogin, uniqueEmail } from './helpers';

test.beforeEach(async ({ page }) => {
  await loginAsAdmin(page);
});

test('an administrator creates a user', async ({ page }) => {
  const email = uniqueEmail('created');

  await createUser(page, { email, first: 'Brais', last: 'Otero' });

  const row = await openUser(page, email);
  await expect(row).toContainText('Brais Otero');
  await expect(row).toContainText('User');
  await expect(row).not.toContainText('Disabled');
});

test('a deactivated user can no longer sign in', async ({ page, browser }) => {
  const email = uniqueEmail('disabled');
  await createUser(page, { email });

  const row = await openUser(page, email);
  await row.getByRole('button', { name: `Actions for ${email}` }).click();
  await page.getByRole('menuitem', { name: 'Edit user' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit user' });
  // Toggled from the keyboard: Mantine's switch input is visually hidden under its track.
  const active = dialog.getByRole('switch', { name: 'Active (can sign in)' });
  await active.focus();
  await page.keyboard.press('Space');
  await expect(active).not.toBeChecked();
  await dialog.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('Changes saved.')).toBeVisible();
  await expect(row).toContainText('Disabled');

  const visitor = await browser.newContext();
  const visitorPage = await visitor.newPage();
  await startLogin(visitorPage, email);
  await expect(visitorPage.getByRole('alert')).toHaveText(
    'This account is disabled. Contact an administrator.',
  );
  await visitor.close();
});

test('the last administrator cannot stop being one', async ({ page }) => {
  const row = await openUser(page, ADMIN.email);
  await row.getByRole('button', { name: `Actions for ${ADMIN.email}` }).click();
  await page.getByRole('menuitem', { name: 'Edit user' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit user' });

  await dialog.getByRole('combobox', { name: 'Role' }).click();
  await page.getByRole('option', { name: 'User', exact: true }).click();
  await dialog.getByRole('button', { name: 'Save changes' }).click();

  await expect(dialog.getByRole('alert')).toHaveText(
    'At least one active administrator must remain.',
  );
});
