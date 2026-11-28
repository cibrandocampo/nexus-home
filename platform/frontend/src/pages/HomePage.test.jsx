import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { AppRoutes } from '../App';
import { makeDevice, page } from '../test/devices';
import { renderWithProviders } from '../test/render';
import { apiError, makeUser, server, withSession } from '../test/server';

function showDevices(...devices) {
  server.use(http.get('/api/devices', () => HttpResponse.json(page(devices))));
}

async function card(name = 'Garage') {
  return within(await screen.findByRole('article', { name }));
}

describe('dashboard', () => {
  it('shows each device with its door, light and status', async () => {
    server.use(withSession(makeUser({ timezone: 'Europe/Madrid' })));
    showDevices(
      makeDevice(),
      makeDevice({ id: 2, name: 'Shed', online: false, last_seen_at: '2026-11-27T10:00:00Z' }),
    );
    renderWithProviders(<AppRoutes />);

    expect(await screen.findByRole('heading', { name: 'Home', level: 1 })).toBeInTheDocument();
    const garage = await card();
    expect(garage.getAllByRole('status').map((s) => s.textContent)).toEqual([
      'Closed',
      'Light off',
    ]);
    expect(garage.getByText('Closed')).toBeInTheDocument();
    expect(garage.getByText('For 2 hr, 1 min, moved by the button')).toBeInTheDocument();
    expect(garage.getByText('Light off')).toBeInTheDocument();
    expect(garage.getByText('Online')).toBeInTheDocument();
    const shed = await card('Shed');
    expect(shed.getByText('Offline, last seen Nov 27, 2026, 11:00 AM')).toBeInTheDocument();
    for (const name of ['Open', 'Close', 'Stop', 'Turn on']) {
      expect(shed.getByRole('button', { name })).toBeDisabled();
    }
  });

  it('asks before moving the door and sends nothing on cancel', async () => {
    let sent = 0;
    server.use(
      withSession(),
      http.post('/api/devices/1/entities/door/open', () => {
        sent += 1;
        return HttpResponse.json({
          result: 'ok',
          state: makeDevice({
            state: { door: { state: 'opening', moving: true, last_source: 'api', since_s: 0 } },
          }).state,
        });
      }),
    );
    showDevices(makeDevice());
    renderWithProviders(<AppRoutes />);

    await userEvent.click((await card()).getByRole('button', { name: 'Open' }));
    const dialog = await screen.findByRole('dialog', { name: 'Open the door of Garage?' });
    expect(within(dialog).getByText('The door is the house entrance.')).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(sent).toBe(0);

    await userEvent.click((await card()).getByRole('button', { name: 'Open' }));
    await userEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Open the door' }),
    );
    expect(await (await card()).findByText('Opening')).toBeInTheDocument();
    expect(sent).toBe(1);
  });

  it.each([
    ['closed', 'none', { Open: true, Close: false, Stop: false }],
    ['open', 'none', { Open: false, Close: true, Stop: false }],
    ['opening', 'none', { Open: false, Close: false, Stop: true }],
    ['closing', 'none', { Open: false, Close: false, Stop: true }],
    ['open', 'up', { Open: true, Close: true, Stop: false }],
  ])('offers what the board accepts: %s, stopped %s', async (state, stopped, enabled) => {
    server.use(withSession());
    showDevices(makeDevice({ state: { door: { state, stopped } } }));
    renderWithProviders(<AppRoutes />);

    const garage = await card();
    for (const [name, on] of Object.entries(enabled)) {
      expect(garage.getByRole('button', { name })).toHaveProperty('disabled', !on);
    }
    if (stopped !== 'none') expect(garage.getByText('Stopped part way')).toBeInTheDocument();
  });

  it('warns when the door did not close', async () => {
    server.use(withSession());
    showDevices(makeDevice({ state: { door: { state: 'open', close_failed: true } } }));
    renderWithProviders(<AppRoutes />);

    expect(
      await (await card()).findByText('The door did not close. Check that nothing is in the way.'),
    ).toBeInTheDocument();
  });

  it('switches the light at once, without asking', async () => {
    const bodies = [];
    server.use(
      withSession(),
      http.post('/api/devices/1/entities/light/on', async ({ request }) => {
        bodies.push(await request.text());
        return HttpResponse.json({
          result: 'ok',
          state: makeDevice({ state: { light: { state: 'on', timed: true, remaining_s: 120 } } })
            .state,
        });
      }),
      http.post('/api/devices/1/entities/light/off', () =>
        HttpResponse.json({ result: 'ok', state: makeDevice().state }),
      ),
    );
    showDevices(makeDevice());
    renderWithProviders(<AppRoutes />);

    await userEvent.click((await card()).getByRole('button', { name: 'Turn on' }));
    expect(await (await card()).findByText('Light on, 2 min left')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(bodies).toEqual(['']);
    await userEvent.click((await card()).getByRole('button', { name: 'Turn off' }));
    expect(await (await card()).findByText('Light off')).toBeInTheDocument();
  });

  it('explains a refused command', async () => {
    server.use(
      withSession(),
      http.post('/api/devices/1/entities/door/close', () => apiError(409, 'door_busy')),
    );
    showDevices(makeDevice({ state: { door: { state: 'open' } } }));
    renderWithProviders(<AppRoutes />);

    await userEvent.click((await card()).getByRole('button', { name: 'Close' }));
    await userEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Close the door' }),
    );
    expect(
      await screen.findByText('The door is moving or was just triggered. Try again in a moment.'),
    ).toBeInTheDocument();
  });

  it('tells a user there are no devices, and shows an admin where to add one', async () => {
    server.use(withSession());
    const { unmount } = renderWithProviders(<AppRoutes />);
    expect(await screen.findByText('No devices yet.')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Add a device' })).not.toBeInTheDocument();
    unmount();

    server.use(withSession(makeUser({ role: 'admin' })));
    renderWithProviders(<AppRoutes />);
    expect(await screen.findByRole('link', { name: 'Add a device' })).toHaveAttribute(
      'href',
      '/admin/devices',
    );
  });

  it('shows who moved the door, or nobody after a restart', async () => {
    server.use(withSession());
    showDevices(makeDevice({ state: { door: { last_source: 'none', since_s: 30 } } }));
    renderWithProviders(<AppRoutes />);

    expect(await (await card()).findByText('For 30 sec')).toBeInTheDocument();
  });

  it('links a device without a door or light to its page', async () => {
    server.use(withSession());
    showDevices(makeDevice({ type: 'sound', name: 'Sound', entities: [ENTITY_SENSOR] }));
    renderWithProviders(<AppRoutes />);

    expect(
      await (await card('Sound')).findByRole('link', { name: 'See the device' }),
    ).toHaveAttribute('href', '/devices/1');
  });

  it('refreshes what the board reports', async () => {
    let calls = 0;
    server.use(
      withSession(),
      http.get('/api/devices', () => {
        calls += 1;
        const state = calls > 1 ? 'opening' : 'closed';
        return HttpResponse.json(page([makeDevice({ state: { door: { state } } })]));
      }),
    );
    renderWithProviders(<AppRoutes />);

    expect(await (await card()).findByText('Closed')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Opening')).toBeInTheDocument(), { timeout: 4000 });
  });

  it('closes the question with Escape, sending nothing', async () => {
    server.use(withSession());
    showDevices(makeDevice());
    renderWithProviders(<AppRoutes />);

    await userEvent.click((await card()).getByRole('button', { name: 'Open' }));
    await screen.findByRole('dialog');
    await userEvent.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('shows a device never seen online', async () => {
    server.use(withSession());
    showDevices(makeDevice({ online: false, last_seen_at: null }));
    renderWithProviders(<AppRoutes />);

    expect(await (await card()).findByText('Offline')).toBeInTheDocument();
  });

  it('updates only the device a command went to', async () => {
    server.use(
      withSession(),
      http.post('/api/devices/2/entities/light/on', () =>
        HttpResponse.json({
          result: 'ok',
          state: makeDevice({ state: { light: { state: 'on' } } }).state,
        }),
      ),
    );
    showDevices(makeDevice(), makeDevice({ id: 2, name: 'Shed' }));
    renderWithProviders(<AppRoutes />);

    await userEvent.click((await card('Shed')).getByRole('button', { name: 'Turn on' }));
    expect(await (await card('Shed')).findByText('Light on')).toBeInTheDocument();
    expect((await card()).getByText('Light off')).toBeInTheDocument();
  });
});

const ENTITY_SENSOR = { id: 'level', type: 'sensor', state: 'level' };
