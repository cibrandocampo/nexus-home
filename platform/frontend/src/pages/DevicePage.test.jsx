import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { AppRoutes } from '../App';
import { makeDevice, page } from '../test/devices';
import { renderWithProviders } from '../test/render';
import { apiError, makeUser, server, withSession } from '../test/server';

function showDevice(device = makeDevice()) {
  server.use(http.get(`/api/devices/${device.id}`, () => HttpResponse.json(device)));
}

function rows(section) {
  return within(section)
    .getAllByRole('term')
    .map((term) => [term.textContent, term.nextElementSibling.textContent]);
}

describe('device page', () => {
  it('shows the door, the light, the sensors and the device', async () => {
    server.use(withSession(makeUser({ timezone: 'Europe/Madrid' })));
    showDevice();
    renderWithProviders(<AppRoutes />, { route: '/devices/1' });

    expect(await screen.findByRole('heading', { name: 'Garage', level: 1 })).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Door' })).getByText('Closed'),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Light' })).getByText('Light off'),
    ).toBeInTheDocument();
    expect(rows(screen.getByRole('region', { name: 'Sensors' }))).toEqual([
      ['Door problem', 'None'],
      ['Night', 'Day'],
      ['Light level', '420'],
      ['WiFi signal', '-60 dBm'],
    ]);
    expect(rows(screen.getByRole('region', { name: 'Device' }))).toEqual([
      ['Model', 'Garage IoT Controller (UNO R4 WiFi)'],
      ['Firmware', '2.0.6'],
      ['WiFi module', '0.6.0'],
      ['Address', '10.1.3.103'],
      ['Device id', 'garage-3562d4'],
      ['Running for', '1 hr, 1 min'],
      ['Last seen', 'Nov 27, 2026, 11:00 AM'],
    ]);
  });

  it('shows a failed close and the night', async () => {
    server.use(withSession());
    showDevice(makeDevice({ state: { door: { state: 'open', close_failed: true }, night: true } }));
    renderWithProviders(<AppRoutes />, { route: '/devices/1' });

    const sensors = await screen.findByRole('region', { name: 'Sensors' });
    expect(rows(sensors)).toContainEqual(['Door problem', 'The door did not close']);
    expect(rows(sensors)).toContainEqual(['Night', 'Night']);
  });

  it.each([
    ['Usual time', ''],
    ['10 minutes', '{"duration":600}'],
    ['1 hour', '{"duration":3600}'],
    ['Until turned off', '{"duration":0}'],
  ])('turns the light on for "%s"', async (choice, body) => {
    let sent;
    server.use(
      withSession(),
      http.post('/api/devices/1/entities/light/on', async ({ request }) => {
        sent = await request.text();
        return HttpResponse.json({ result: 'ok', state: makeDevice().state });
      }),
    );
    showDevice();
    renderWithProviders(<AppRoutes />, { route: '/devices/1' });

    const light = await screen.findByRole('region', { name: 'Light' });
    const [input] = within(light)
      .getAllByLabelText('Keep the light on')
      .filter((element) => element.tagName === 'INPUT');
    await userEvent.click(input);
    await userEvent.click(await screen.findByRole('option', { name: choice }));
    await userEvent.click(within(light).getByRole('button', { name: 'Turn on' }));
    await vi.waitFor(() => expect(sent).toBe(body));
  });

  it('shows unknown readings and leaves out what the device does not report', async () => {
    server.use(withSession());
    const device = makeDevice({ last_seen_at: null, uptime_s: null, modem_fw: '' });
    device.state = { rev: 1, door: { state: 'closed' } };
    showDevice(device);
    renderWithProviders(<AppRoutes />, { route: '/devices/1' });

    const sensors = await screen.findByRole('region', { name: 'Sensors' });
    expect(rows(sensors)).toContainEqual(['Light level', 'Unknown']);
    expect(rows(screen.getByRole('region', { name: 'Device' })).map(([k]) => k)).toEqual([
      'Model',
      'Firmware',
      'Address',
      'Device id',
    ]);
  });

  it('shows a device without sensors', async () => {
    server.use(withSession());
    const bare = makeDevice({ entities: makeDevice().entities.slice(0, 2) });
    bare.state = null;
    showDevice(bare);
    renderWithProviders(<AppRoutes />, { route: '/devices/1' });

    expect(await screen.findByRole('region', { name: 'Door' })).toHaveTextContent('Unknown');
    expect(screen.queryByRole('region', { name: 'Sensors' })).not.toBeInTheDocument();
  });

  it("shows the board's IP when it is registered by name", async () => {
    server.use(withSession());
    showDevice(makeDevice({ host: 'sim-garage-a' }));
    renderWithProviders(<AppRoutes />, { route: '/devices/1' });

    const about = await screen.findByRole('region', { name: 'Device' });
    expect(rows(about)).toContainEqual(['Address', 'sim-garage-a']);
    expect(rows(about)).toContainEqual(['IP address', '10.1.3.103']);
  });

  it('names a yes/no sensor it has no words for', async () => {
    server.use(withSession());
    const device = makeDevice({
      entities: [{ id: 'leak', type: 'binary_sensor', state: 'leak' }],
      state: { rev: 1, leak: true },
    });
    showDevice(device);
    renderWithProviders(<AppRoutes />, { route: '/devices/1' });

    expect(rows(await screen.findByRole('region', { name: 'Sensors' }))).toEqual([['leak', 'Yes']]);
  });

  it('says when the device does not exist', async () => {
    server.use(
      withSession(),
      http.get('/api/devices/9', () => apiError(404, 'device_not_found')),
    );
    renderWithProviders(<AppRoutes />, { route: '/devices/9' });

    expect(await screen.findByRole('heading', { name: 'Device not found' })).toBeInTheDocument();
    expect(screen.queryByText('The device no longer exists.')).not.toBeInTheDocument(); // no toast
    expect(screen.getByRole('link', { name: 'Go to the home page' })).toHaveAttribute('href', '/');
  });

  it('is reached from the dashboard and keeps the home tab current', async () => {
    server.use(
      withSession(),
      http.get('/api/devices', () => HttpResponse.json(page([makeDevice()]))),
    );
    showDevice();
    renderWithProviders(<AppRoutes />);

    await userEvent.click(await screen.findByRole('link', { name: 'Garage' }));
    expect(await screen.findByRole('heading', { name: 'Garage', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page');
  });
});
