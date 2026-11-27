import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { AppRoutes } from '../../App';
import { makeDevice, page } from '../../test/devices';
import { renderWithProviders } from '../../test/render';
import { apiError, makeUser, server, withSession } from '../../test/server';

const admin = makeUser({ role: 'admin' });

function found(fields) {
  return {
    device_id: 'garage-33ad84',
    name: 'Bench',
    model: 'Garage IoT Controller (UNO R4 WiFi)',
    sw_version: '2.0.6',
    host: '10.1.3.114',
    auth: false,
    registered: false,
    id: null,
    ...fields,
  };
}

function setup({ devices = [makeDevice()], scan, onScan, onAdd } = {}) {
  server.use(
    withSession(admin),
    http.get('/api/devices', () => HttpResponse.json(page(devices))),
    http.get('/api/devices/scan-ranges', () => HttpResponse.json({ ranges: ['10.1.2.0/23'] })),
    http.post('/api/devices/scan', async ({ request }) => {
      onScan?.(await request.json());
      return scan ?? HttpResponse.json({ items: [], scanned: 510, duration_s: 13.2 });
    }),
    http.post('/api/devices', async ({ request }) => {
      const body = await request.json();
      onAdd?.(body);
      return HttpResponse.json(makeDevice({ id: 9, name: 'Bench', host: body.host }), {
        status: 201,
      });
    }),
  );
  return renderWithProviders(<AppRoutes />, { route: '/admin/devices' });
}

function field(label) {
  return screen.getAllByLabelText(label).find((element) => element.tagName === 'INPUT');
}

describe('devices admin page', () => {
  it('is for administrators only', async () => {
    server.use(withSession(makeUser({ role: 'user' })));
    renderWithProviders(<AppRoutes />, { route: '/admin/devices' });

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Devices' })).not.toBeInTheDocument();
  });

  it('lists the devices with where they are and whether they answer', async () => {
    setup({ devices: [makeDevice(), makeDevice({ id: 2, name: 'Shed', online: false })] });

    const table = await screen.findByRole('table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((row) => row.textContent)).toEqual([
      'Garagegarage-3562d4 at 10.1.3.103, firmware 2.0.6Online',
      'Shedgarage-3562d4 at 10.1.3.103, firmware 2.0.6Offline',
    ]);
    expect(within(rows[0]).getByRole('link', { name: 'Garage' })).toHaveAttribute(
      'href',
      '/admin/devices/1',
    );
    expect(screen.getByRole('link', { name: 'Devices' })).toHaveAttribute('aria-current', 'page');
  });

  it('says how to start when there are no devices', async () => {
    setup({ devices: [] });

    expect(
      await screen.findByText('No devices yet. Scan the network below, or add one by its address.'),
    ).toBeInTheDocument();
  });

  it('scans the configured ranges, or the ones typed', async () => {
    const scans = [];
    setup({
      onScan: (body) => scans.push(body),
      scan: HttpResponse.json({
        items: [
          found(),
          found({
            device_id: 'garage-3562d4',
            name: 'Garage',
            host: '10.1.3.103',
            registered: true,
            id: 1,
          }),
        ],
        scanned: 254,
        duration_s: 8.3,
      }),
    });

    const ranges = await screen.findByLabelText('Network ranges');
    await waitFor(() => expect(ranges).toHaveValue('10.1.2.0/23'));
    await userEvent.click(screen.getByRole('button', { name: 'Scan the network' }));
    expect(
      await screen.findByText('2 devices found among 254 addresses in 8.3 s.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add Bench' })).toBeInTheDocument();
    expect(screen.getByText('Added')).toBeInTheDocument();

    await userEvent.clear(ranges);
    await userEvent.type(ranges, '10.1.3.0/24, 10.1.4.7');
    await userEvent.click(screen.getByRole('button', { name: 'Scan the network' }));
    await waitFor(() => expect(scans).toHaveLength(2));
    expect(scans).toEqual([{ ranges: ['10.1.2.0/23'] }, { ranges: ['10.1.3.0/24', '10.1.4.7'] }]);
  });

  it('scans the defaults when the field is emptied', async () => {
    const scans = [];
    setup({ onScan: (body) => scans.push(body) });

    const ranges = await screen.findByLabelText('Network ranges');
    await waitFor(() => expect(ranges).toHaveValue('10.1.2.0/23'));
    await userEvent.clear(ranges);
    await userEvent.click(screen.getByRole('button', { name: 'Scan the network' }));

    await waitFor(() => expect(scans).toEqual([{ ranges: null }]));
    expect(
      await screen.findByText('0 devices found among 510 addresses in 13.2 s.'),
    ).toBeInTheDocument();
  });

  it('explains a refused scan', async () => {
    setup({ scan: apiError(400, 'scan_too_large') });

    await userEvent.click(await screen.findByRole('button', { name: 'Scan the network' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'These ranges hold more than 1024 addresses. Scan a smaller range.',
    );
  });

  it('adds a scanned board without a token, and stops offering it', async () => {
    const added = [];
    setup({
      onAdd: (body) => added.push(body),
      scan: HttpResponse.json({ items: [found()], scanned: 254, duration_s: 8 }),
    });

    await userEvent.click(await screen.findByRole('button', { name: 'Scan the network' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Add Bench' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add a device' });
    expect(within(dialog).getByLabelText(/^Address/)).toHaveValue('10.1.3.114');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add device' }));

    expect(await screen.findByText('Bench added.')).toBeInTheDocument();
    expect(added).toEqual([{ host: '10.1.3.114' }]);
    expect(screen.queryByRole('button', { name: 'Add Bench' })).not.toBeInTheDocument();
  });

  it('adds a device by its address and token, showing why it failed first', async () => {
    let calls = 0;
    setup();
    server.use(
      http.post('/api/devices', async () => {
        calls += 1;
        return calls === 1
          ? apiError(400, 'device_token_invalid')
          : HttpResponse.json(makeDevice({ id: 9, name: 'Bench' }), { status: 201 });
      }),
    );

    await userEvent.click(await screen.findByRole('button', { name: 'Add by address' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add a device' });
    const address = within(dialog).getByLabelText(/^Address/);
    expect(address).toHaveFocus();
    await userEvent.type(address, 'bench.lan');
    await userEvent.type(within(dialog).getByLabelText('Access token'), 'wrong-token');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add device' }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'The device refused this token. Check it and try again.',
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add device' }));
    expect(await screen.findByText('Bench added.')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('removes a device after confirming', async () => {
    const removed = vi.fn();
    setup();
    server.use(
      http.delete('/api/devices/1', () => {
        removed();
        return new HttpResponse(null, { status: 204 });
      }),
    );

    await userEvent.click(await screen.findByRole('button', { name: 'Actions for Garage' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Remove' }));
    const dialog = await screen.findByRole('dialog', { name: 'Remove Garage?' });
    expect(dialog).toHaveTextContent('Its history is deleted too.');
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Remove device' }));

    expect(await screen.findByText('Garage removed.')).toBeInTheDocument();
    expect(removed).toHaveBeenCalledOnce();
  });

  it('shows why a removal failed and lets the admin cancel', async () => {
    setup();
    server.use(http.delete('/api/devices/1', () => apiError(404, 'device_not_found')));

    await userEvent.click(await screen.findByRole('button', { name: 'Actions for Garage' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Remove' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Remove device' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'The device no longer exists.',
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('opens a device settings from its menu', async () => {
    setup();
    server.use(
      http.get('/api/devices/1', () => HttpResponse.json(makeDevice())),
      http.get('/api/devices/1/settings', () =>
        HttpResponse.json({
          name: 'Garage',
          open_s: 20,
          close_s: 40,
          light_s: 120,
          night_level: 700,
          display: true,
        }),
      ),
    );

    await userEvent.click(await screen.findByRole('button', { name: 'Actions for Garage' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Settings' }));

    expect(await screen.findByRole('heading', { name: 'Settings of Garage' })).toBeInTheDocument();
    expect(field('Name')).toHaveValue('Garage');
  });
});

describe('devices admin page, more', () => {
  it('shows the scan running until it ends', async () => {
    let finish;
    const answered = new Promise((resolve) => (finish = resolve));
    server.use(
      withSession(admin),
      http.get('/api/devices', () => HttpResponse.json(page([]))),
      http.get('/api/devices/scan-ranges', () => HttpResponse.json({ ranges: ['10.1.2.0/23'] })),
      http.post('/api/devices/scan', async () => {
        await answered;
        return HttpResponse.json({ items: [], scanned: 510, duration_s: 13 });
      }),
    );
    renderWithProviders(<AppRoutes />, { route: '/admin/devices' });

    const button = await screen.findByRole('button', { name: 'Scan the network' });
    await userEvent.click(button);
    expect(await screen.findByText('Scanning. It takes a few seconds.')).toBeInTheDocument();
    expect(button).toHaveAttribute('data-loading', 'true');

    finish();
    expect(
      await screen.findByText('0 devices found among 510 addresses in 13 s.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Scanning. It takes a few seconds.')).not.toBeInTheDocument();
    expect(button).not.toHaveAttribute('data-loading');
  });

  it('forgets a typed token once the add dialog closes', async () => {
    const { queryClient } = setup();

    await userEvent.click(await screen.findByRole('button', { name: 'Add by address' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add a device' });
    await userEvent.type(within(dialog).getByLabelText(/^Address/), 'bench.lan');
    await userEvent.type(within(dialog).getByLabelText('Access token'), 'secret-token-1');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add device' }));
    await screen.findByText('Bench added.');

    await waitFor(() =>
      expect(
        JSON.stringify(
          queryClient
            .getMutationCache()
            .getAll()
            .map((m) => m.state),
        ),
      ).not.toContain('secret-token-1'),
    );
  });
});
