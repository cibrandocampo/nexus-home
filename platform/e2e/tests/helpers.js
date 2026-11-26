import { expect } from '@playwright/test';

export const ADMIN = {
  email: process.env.ADMIN_EMAIL ?? 'admin@example.com',
  password: process.env.ADMIN_PASSWORD ?? 'e2e-admin-password-1',
};
const MAILPIT = process.env.MAILPIT_URL ?? 'http://localhost:8025';

// Every spec works with its own accounts, so specs never depend on each other's data.
export function uniqueEmail(tag) {
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  return `e2e-${tag}-${suffix}@example.com`;
}

async function messagesTo(request, email) {
  const response = await request.get(`${MAILPIT}/api/v1/search`, {
    params: { query: `to:"${email}"` },
  });
  expect(response.status(), 'Mailpit search').toBe(200);
  return (await response.json()).messages;
}

// Ids of the emails already sent to `email`; pass them to `newCode` to wait for the next one.
export async function sentIds(request, email) {
  return new Set((await messagesTo(request, email)).map((message) => message.ID));
}

// Waits (polling Mailpit, no fixed sleep) for an email to `email` not in `seen`, returns its code.
export async function newCode(request, email, seen) {
  let code;
  await expect
    .poll(
      async () => {
        const fresh = (await messagesTo(request, email)).find((m) => !seen.has(m.ID));
        code = fresh?.Subject.match(/\b(\d{6})\b/)?.[1];
        return code;
      },
      { message: `a sign-in code for ${email}`, timeout: 15_000 },
    )
    .toBeTruthy();
  return code;
}

export async function startLogin(page, email) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByRole('button', { name: 'Continue' }).click();
}

export async function enterCode(page, code) {
  await page.getByLabel('Code digit 1 of 6').click();
  await page.keyboard.type(code);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

// Sign in (or sign up) with an emailed code.
export async function loginWithCode(page, email) {
  const seen = await sentIds(page.request, email);
  await startLogin(page, email);
  await expect(page.getByText('We have sent a 6-digit code to')).toBeVisible();
  await enterCode(page, await newCode(page.request, email, seen));
}

export async function loginWithPassword(page, email, password) {
  await startLogin(page, email);
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

export async function loginAsAdmin(page) {
  await loginWithPassword(page, ADMIN.email, ADMIN.password);
  await expect(page.getByRole('heading', { name: 'Welcome', exact: true })).toBeVisible();
}

// A new account through self sign-up, named, left waiting for access.
export async function signUp(page, email, { first = 'Ana', last = 'Pérez' } = {}) {
  await loginWithCode(page, email);
  await expect(page.getByRole('heading', { name: 'Welcome!' })).toBeVisible();
  await page.getByLabel('First name').fill(first);
  await page.getByLabel('Last name').fill(last);
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Waiting for access' })).toBeVisible();
}

export async function logout(page) {
  await page.goto('/profile');
  await page.getByRole('button', { name: 'Log out' }).click();
  await expect(page.getByRole('heading', { name: /^Sign in/ })).toBeVisible();
}

// The admin's users page, filtered to one account.
export async function openUser(page, email) {
  await page.goto('/admin/users');
  await page.getByRole('textbox', { name: 'Search' }).fill(email);
  const row = page.getByRole('row', { name: new RegExp(email.replace(/[.+]/g, '\\$&')) });
  await expect(row).toBeVisible();
  return row;
}

// Creates an account from the admin's users page (the page must be signed in as an admin).
export async function createUser(
  page,
  { email, first = 'Uxía', last = 'Pérez', role, method, password },
) {
  await page.goto('/admin/users');
  await page.getByRole('button', { name: 'New user' }).click();
  const dialog = page.getByRole('dialog', { name: 'New user' });
  await dialog.getByLabel('Email').fill(email);
  await dialog.getByLabel('First name').fill(first);
  await dialog.getByLabel('Last name').fill(last);
  if (role) {
    await dialog.getByRole('combobox', { name: 'Role' }).click();
    await page.getByRole('option', { name: role, exact: true }).click();
  }
  if (method) {
    await dialog.getByRole('combobox', { name: 'Sign-in method' }).click();
    await page.getByRole('option', { name: method, exact: true }).click();
  }
  if (password)
    await dialog.getByRole('textbox', { name: 'New password', exact: true }).fill(password);
  await dialog.getByRole('button', { name: 'Create user' }).click();
  await expect(page.getByText('User created.')).toBeVisible();
}

export async function grantAccess(page, email) {
  const row = await openUser(page, email);
  await row.getByRole('button', { name: 'Grant access' }).click();
  await expect(page.getByText(`${email} now has access.`)).toBeVisible();
}
