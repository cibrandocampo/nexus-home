import { expect, test } from '@playwright/test';

import {
  createUser,
  loginAsAdmin,
  loginWithPassword,
  logout,
  signUp,
  uniqueEmail,
} from './helpers';

// Two simulated garage boards (platform/simulator) in the e2e stack, at fixed addresses inside the
// server's SCAN_RANGES: "E2E Garage" with a token, "New Garage" without one. The specs build on each
// other (the boards are added once), so they run in order.
const SIM = process.env.SIM_URL ?? 'http://localhost:8081';
const SIM_TOKEN = process.env.SIM_TOKEN ?? 'e2e-sim-token';
const USER = { email: uniqueEmail('devices'), password: 'e2e-devices-user-1', first: 'Ana' };

test.describe.configure({ mode: 'serial' });

async function loginAsUser(page) {
  await loginWithPassword(page, USER.email, USER.password);
  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible();
}

// A simulator test hook (not on real boards): button presses, going offline…
async function hook(request, name, body = {}) {
  const response = await request.post(`${SIM}/sim/${name}`, { data: body });
  expect(response.status(), `/sim/${name}`).toBe(200);
}

function card(page, name = 'E2E Garage') {
  return page.getByRole('article', { name });
}

// The door's state line (announced as a status), not a button with the same word.
function door(page) {
  return card(page).getByRole('status').first();
}

async function confirmDoor(page, action, title) {
  await card(page).getByRole('button', { name: action, exact: true }).click();
  const dialog = page.getByRole('dialog', { name: title });
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await dialog.getByRole('button', { name: `${action} the door` }).click();
}

test('an administrator scans the network and adds both boards', async ({ page }) => {
  await loginAsAdmin(page);
  await expect(page.getByText('No devices yet.')).toBeVisible();
  await page.getByRole('link', { name: 'Add a device' }).click();
  await expect(page.getByRole('heading', { name: 'Devices', level: 1 })).toBeVisible();

  await expect(page.getByLabel('Network ranges')).toHaveValue('172.31.250.0/28');
  await page.getByRole('button', { name: 'Scan the network' }).click();
  await expect(page.getByText(/^2 devices found among 14 addresses/)).toBeVisible({
    timeout: 30_000,
  });

  // The board with a token: a wrong one is refused, the right one accepted.
  await page.getByRole('button', { name: 'Add E2E Garage' }).click();
  let dialog = page.getByRole('dialog', { name: 'Add a device' });
  await dialog.getByLabel('Access token').fill('not-the-token');
  await dialog.getByRole('button', { name: 'Add device' }).click();
  await expect(dialog.getByRole('alert')).toHaveText(
    'The device refused this token. Check it and try again.',
  );
  await dialog.getByLabel('Access token').fill(SIM_TOKEN);
  await dialog.getByRole('button', { name: 'Add device' }).click();
  await expect(page.getByText('E2E Garage added.')).toBeVisible();

  // The new board without a token: the platform gives it one.
  await page.getByRole('button', { name: 'Add New Garage' }).click();
  dialog = page.getByRole('dialog', { name: 'Add a device' });
  await dialog.getByRole('button', { name: 'Add device' }).click();
  await expect(page.getByText('New Garage added.')).toBeVisible();

  const table = page.getByRole('table');
  await expect(table.getByRole('link', { name: 'E2E Garage' })).toBeVisible();
  await expect(table.getByRole('link', { name: 'New Garage' })).toBeVisible();

  await createUser(page, {
    email: USER.email,
    first: USER.first,
    last: 'Door',
    method: 'Password',
    password: USER.password,
  });
  await logout(page);
});

test('a user opens and closes the door, confirming first', async ({ page }) => {
  await loginAsUser(page);
  await expect(door(page)).toHaveText('Closed');

  await confirmDoor(page, 'Open', 'Open the door of E2E Garage?');
  await expect(door(page)).toHaveText('Opening');
  // 20 s of travel at the simulators' 10× speed.
  await expect(door(page)).toHaveText('Open');
  await expect(card(page).getByText(/moved by the app$/)).toBeVisible();

  await confirmDoor(page, 'Close', 'Close the door of E2E Garage?');
  await expect(door(page)).toHaveText('Closed');
});

test('a user turns the light on for ten minutes from the device page', async ({ page }) => {
  await loginAsUser(page);
  await card(page).getByRole('link', { name: 'E2E Garage' }).click();
  await expect(page.getByRole('heading', { name: 'E2E Garage', level: 1 })).toBeVisible();

  const light = page.getByRole('region', { name: 'Light' });
  await light.getByRole('combobox', { name: 'Keep the light on' }).click();
  await page.getByRole('option', { name: '10 minutes' }).click();
  await light.getByRole('button', { name: 'Turn on' }).click();
  await expect(light.getByText(/^Light on, \d+ mins?(, \d+ secs?)? left$/)).toBeVisible();
  await light.getByRole('button', { name: 'Turn off' }).click();
  await expect(light.getByText('Light off', { exact: true })).toBeVisible();
});

test('a button press shows on the dashboard and in the history, with who did what', async ({
  page,
}) => {
  await loginAsUser(page);
  await hook(page.request, 'button');

  await expect(card(page).getByText(/moved by the button$/)).toBeVisible();
  await expect(door(page)).toHaveText('Open');

  await page.getByRole('link', { name: 'History' }).click();
  await expect(page.getByRole('heading', { name: 'History', level: 1 })).toBeVisible();
  await expect(
    page
      .getByRole('listitem')
      .filter({ hasText: 'Door opening' })
      .filter({ hasText: 'button or remote' })
      .first(),
  ).toBeVisible({ timeout: 20_000 });
  // The user's own command earlier, named.
  await expect(
    page
      .getByRole('listitem')
      .filter({ hasText: 'Door opening' })
      .filter({ hasText: 'by Ana Door' })
      .first(),
  ).toBeVisible();

  // Close it again for the next specs (by the button, as a person would).
  await page.goto('/');
  await expect(door(page)).toHaveText('Open');
  await hook(page.request, 'button');
  await expect(door(page)).toHaveText('Closed');
});

test('a board that stops answering shows offline, then online again', async ({ page }) => {
  await loginAsUser(page);
  await expect(card(page).getByText('Online')).toBeVisible();

  // Real seconds (the simulator's speed does not apply here): long enough to see offline, which the
  // platform notices after about 10 s (three polls that time out), short enough to come back.
  await hook(page.request, 'offline', { seconds: 25 });

  await expect(card(page).getByText(/^Offline, last seen /)).toBeVisible({ timeout: 30_000 });
  await expect(card(page).getByRole('button', { name: 'Turn on' })).toBeDisabled();
  await expect(card(page).getByText('Online')).toBeVisible({ timeout: 30_000 });
});

test('an administrator changes the light time and the token; the board keeps working', async ({
  page,
}) => {
  await loginAsAdmin(page);
  await page.goto('/admin/devices');
  await page.getByRole('link', { name: 'E2E Garage' }).click();
  await expect(page.getByRole('heading', { name: 'Settings of E2E Garage' })).toBeVisible();

  const lightTime = page.getByRole('textbox', { name: 'Light time (seconds)' });
  await expect(lightTime).toHaveValue('120');
  await lightTime.fill('300');
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('Settings saved.')).toBeVisible();

  await page.getByRole('button', { name: 'Change the token' }).click();
  const dialog = page.getByRole('dialog', { name: 'Change the token of E2E Garage?' });
  await dialog.getByRole('button', { name: 'Change the token' }).click();
  await expect(page.getByText('Token changed.')).toBeVisible();

  // The old token no longer works on the board; the platform has the new one.
  const refused = await page.request.post(`${SIM}/api/v1/light/on`, {
    headers: { Authorization: `Bearer ${SIM_TOKEN}` },
  });
  expect(refused.status()).toBe(401);
  await page.goto('/');
  await card(page).getByRole('button', { name: 'Turn on' }).click();
  await expect(card(page).getByText(/^Light on/)).toBeVisible();
  await card(page).getByRole('button', { name: 'Turn off' }).click();
  await expect(card(page).getByText('Light off', { exact: true })).toBeVisible();
});

test('only administrators reach the device administration', async ({ page, browser }) => {
  await loginAsUser(page);
  await page.goto('/admin/devices');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Devices' })).toHaveCount(0);

  // An account without a role waits, also at the device pages.
  const visitor = await browser.newContext();
  const visitorPage = await visitor.newPage();
  await signUp(visitorPage, uniqueEmail('devices-none'));
  await visitorPage.goto('/admin/devices');
  await expect(visitorPage.getByRole('heading', { name: 'Waiting for access' })).toBeVisible();
  await visitorPage.goto('/');
  await expect(visitorPage.getByRole('heading', { name: 'Waiting for access' })).toBeVisible();
  await visitor.close();
});
