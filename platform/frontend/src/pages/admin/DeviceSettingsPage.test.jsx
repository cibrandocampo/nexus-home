import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { AppRoutes } from '../../App';
import { makeDevice } from '../../test/devices';
import { renderWithProviders } from '../../test/render';
import { apiError, makeUser, server, withSession } from '../../test/server';

const SETTINGS = {
  name: 'Garage',
  open_s: 20,
  close_s: 40,
  light_s: 120,
  night_level: 700,
  display: true,
};

// `settings` makes a fresh answer per request: a Response body can be read only once.
function setup({ settings = () => HttpResponse.json(SETTINGS), device = makeDevice() } = {}) {
  const sent = [];
  server.use(
    withSession(makeUser({ role: 'admin' })),
    http.get('/api/devices/1', () => HttpResponse.json(device)),
    http.get('/api/devices/1/settings', () => settings()),
    http.patch('/api/devices/1/settings', async ({ request }) => {
      const body = await request.json();
      sent.push(body);
      return HttpResponse.json({ ...SETTINGS, ...body });
    }),
  );
  const { queryClient } = renderWithProviders(<AppRoutes />, { route: '/admin/devices/1' });
  cache = queryClient.getMutationCache();
  return sent;
}

let cache;

const input = (label) =>
  screen.getAllByLabelText(label).find((element) => element.tagName === 'INPUT');

async function loaded() {
  await screen.findByRole('heading', { name: 'Settings of Garage' });
  await waitFor(() => expect(input('Name')).toHaveValue('Garage'));
}

describe('device settings page', () => {
  it('shows the stored settings with their limits', async () => {
    setup();
    await loaded();

    expect(input('Opening time (seconds)')).toHaveValue('20');
    expect(input('Light time (seconds)')).toHaveValue('120');
    expect(screen.getByText('How long the door takes to open: 5 to 100.')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'LED matrix on' })).toBeChecked();
    expect(screen.getByText('6 of 32 bytes (accents count twice)')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to devices' })).toHaveAttribute(
      'href',
      '/admin/devices',
    );
    expect(screen.getByRole('link', { name: 'Open the device page' })).toHaveAttribute(
      'href',
      '/devices/1',
    );
  });

  it('sends only what changed', async () => {
    const sent = setup();
    await loaded();

    await userEvent.clear(input('Light time (seconds)'));
    await userEvent.type(input('Light time (seconds)'), '300');
    await userEvent.click(screen.getByRole('switch', { name: 'LED matrix on' }));
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Settings saved.')).toBeInTheDocument();
    expect(sent).toEqual([{ light_s: 300, display: false }]);
  });

  it('says when there is nothing to save', async () => {
    const sent = setup();
    await loaded();

    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Nothing to save: no changes.')).toBeInTheDocument();
    expect(sent).toEqual([]);
  });

  it('counts the name in bytes, as the device does', async () => {
    const sent = setup();
    await loaded();

    await userEvent.clear(input('Name'));
    await userEvent.type(input('Name'), 'ñ'.repeat(17));
    expect(screen.getByText('34 of 32 bytes (accents count twice)')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Too long for the device: shorten it.')).toBeInTheDocument();
    expect(sent).toEqual([]);
    await userEvent.clear(input('Name'));
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Enter a name.')).toBeInTheDocument();
  });

  it('keeps numbers within the device limits', async () => {
    const sent = setup();
    await loaded();

    await userEvent.clear(input('Night level'));
    await userEvent.type(input('Night level'), '2000');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Between 1 and 1023.')).toBeInTheDocument();
    expect(sent).toEqual([]);
  });

  it('marks a field the server refused, and explains a device refusal', async () => {
    setup();
    await loaded();
    server.use(
      http.patch('/api/devices/1/settings', () =>
        HttpResponse.json(
          {
            error: {
              code: 'validation_error',
              message: 'Invalid request',
              details: [{ loc: ['body', 'name'], message: 'at most 32 bytes' }],
            },
          },
          { status: 422 },
        ),
      ),
    );
    await userEvent.type(input('Name'), ' 2');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('The device refused this value.')).toBeInTheDocument();

    server.use(http.patch('/api/devices/1/settings', () => apiError(400, 'invalid_light_time')));
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The device refused this light time (10 to 600 s).',
    );
  });

  it('explains a device type without settings, or a device that does not answer', async () => {
    setup({ settings: () => apiError(404, 'settings_not_supported') });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This kind of device has no settings here.',
    );
    expect(screen.getByRole('button', { name: 'Restart' })).toBeInTheDocument();
  });

  it('says when the device does not exist', async () => {
    server.use(
      withSession(makeUser({ role: 'admin' })),
      http.get('/api/devices/9', () => apiError(404, 'device_not_found')),
      http.get('/api/devices/9/settings', () => apiError(404, 'device_not_found')),
    );
    renderWithProviders(<AppRoutes />, { route: '/admin/devices/9' });

    expect(await screen.findByRole('heading', { name: 'Device not found' })).toBeInTheDocument();
    expect(screen.queryByText('The device no longer exists.')).not.toBeInTheDocument();
  });

  it('restarts after confirming, and explains a refusal', async () => {
    let calls = 0;
    setup();
    server.use(
      http.post('/api/devices/1/restart', () => {
        calls += 1;
        return calls === 1 ? apiError(409, 'door_busy') : new HttpResponse(null, { status: 204 });
      }),
    );
    await loaded();

    await userEvent.click(screen.getByRole('button', { name: 'Restart' }));
    const dialog = await screen.findByRole('dialog', { name: 'Restart Garage?' });
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Restart' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('The door is moving');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Restart' }));
    expect(await screen.findByText('Restarting.')).toBeInTheDocument();
  });

  it('shows the token on demand, with the previous one when a change was not confirmed', async () => {
    setup();
    server.use(
      http.get('/api/devices/1/token', () =>
        HttpResponse.json({ token: 'new-token-123', previous_token: 'old-token-456' }),
      ),
    );
    await loaded();

    await userEvent.click(screen.getByRole('button', { name: 'Show the token' }));
    const dialog = await screen.findByRole('dialog', { name: 'Access token of Garage' });
    expect(dialog).toHaveTextContent('Showing the token is recorded.');
    expect(within(dialog).queryByText('new-token-123')).not.toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Show the token' }));

    expect(await within(dialog).findByText('new-token-123')).toBeInTheDocument();
    expect(within(dialog).getByText('old-token-456')).toBeInTheDocument();
    expect(within(dialog).getAllByRole('button', { name: 'Copy' })).toHaveLength(2);
    // The last "Close": the dialog's own button, not its corner X.
    await userEvent.click(within(dialog).getAllByRole('button', { name: 'Close' }).at(-1));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    // Nothing of the secret is left in the mutation cache once the dialog is closed.
    await waitFor(() => {
      const cached = JSON.stringify(cache.getAll().map((m) => m.state));
      expect(cached).not.toContain('new-token-123');
      expect(cached).not.toContain('old-token-456');
    });
  });

  it('shows only the token when nothing is pending, and why it could not', async () => {
    setup();
    server.use(http.get('/api/devices/1/token', () => apiError(429, 'rate_limited')));
    await loaded();

    await userEvent.click(screen.getByRole('button', { name: 'Show the token' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Show the token' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Too many attempts');

    server.use(
      http.get('/api/devices/1/token', () =>
        HttpResponse.json({ token: 't-1', previous_token: null }),
      ),
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Show the token' }));
    expect(await within(dialog).findByText('t-1')).toBeInTheDocument();
    expect(within(dialog).queryByText('Previous token')).not.toBeInTheDocument();
  });

  it('changes the token after confirming', async () => {
    let rotated = 0;
    setup();
    server.use(
      http.post('/api/devices/1/rotate-token', () => {
        rotated += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    await loaded();

    await userEvent.click(screen.getByRole('button', { name: 'Change the token' }));
    const dialog = await screen.findByRole('dialog', { name: 'Change the token of Garage?' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Change the token' }));

    expect(await screen.findByText('Token changed.')).toBeInTheDocument();
    expect(rotated).toBe(1);
  });

  it('changes the address or re-enters the token', async () => {
    const sent = [];
    setup();
    server.use(
      http.patch('/api/devices/1', async ({ request }) => {
        const body = await request.json();
        sent.push(body);
        return body.token === 'wrong-token'
          ? apiError(400, 'device_token_invalid')
          : HttpResponse.json(makeDevice({ host: body.host ?? '10.1.3.103' }));
      }),
    );
    await loaded();

    await userEvent.click(screen.getByRole('button', { name: 'Change address or token' }));
    let dialog = await screen.findByRole('dialog', { name: 'Change address or token' });
    await userEvent.type(within(dialog).getByLabelText('Access token'), 'wrong-token');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'The device refused this token.',
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));

    await userEvent.click(screen.getByRole('button', { name: 'Change address or token' }));
    dialog = await screen.findByRole('dialog', { name: 'Change address or token' });
    const address = within(dialog).getByLabelText(/^Address/);
    await userEvent.clear(address);
    await userEvent.type(address, '10.1.3.120');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Connection saved.')).toBeInTheDocument();
    expect(sent).toEqual([{ token: 'wrong-token' }, { host: '10.1.3.120' }]);
  });
});

describe('device settings page access', () => {
  it('is for administrators only', async () => {
    server.use(withSession(makeUser({ role: 'user' })));
    renderWithProviders(<AppRoutes />, { route: '/admin/devices/1' });

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
