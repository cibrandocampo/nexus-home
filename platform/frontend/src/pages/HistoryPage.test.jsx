import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { AppRoutes } from '../App';
import { makeDevice, page } from '../test/devices';
import { renderWithProviders } from '../test/render';
import { apiError, makeUser, server, withSession } from '../test/server';

function event(id, at, fields = {}) {
  return {
    id,
    at,
    event: 'door_opening',
    source: 'api',
    reason: 'command',
    value: 0,
    device: { id: 1, name: 'Garage' },
    user: null,
    ...fields,
  };
}

const EVENTS = [
  event(4, '2026-11-27T10:05:00Z', { user: { id: 2, name: 'Ana Pérez' } }),
  event(3, '2026-11-27T09:00:00Z', {
    event: 'light_on',
    source: 'auto',
    reason: 'none',
    value: 120,
    device: { id: 2, name: 'Shed' },
  }),
  event(2, '2026-11-26T23:30:00Z', { event: 'door_closed', source: 'button', reason: 'stopped' }),
  event(1, '2026-11-26T20:00:00Z', {
    event: 'boot',
    source: 'none',
    reason: 'none',
    user: { id: 3, name: null },
  }),
];

// A Mantine select's input (its label also names the option list).
function field(label) {
  return screen.getAllByLabelText(label).find((element) => element.tagName === 'INPUT');
}

// Answers the history and records each request's query.
function serveEvents(items = EVENTS, total = items.length) {
  const asked = [];
  server.use(
    http.get('/api/events', ({ request }) => {
      asked.push(new URL(request.url).searchParams);
      return HttpResponse.json({ items, total, page: 1, size: 50 });
    }),
    http.get('/api/devices', () =>
      HttpResponse.json(page([makeDevice(), makeDevice({ id: 2, name: 'Shed' })])),
    ),
  );
  return asked;
}

describe('history', () => {
  it('lists the events by day, in the user time zone', async () => {
    server.use(withSession(makeUser({ timezone: 'Europe/Madrid' })));
    serveEvents();
    renderWithProviders(<AppRoutes />, { route: '/history' });

    expect(await screen.findByRole('heading', { name: 'History', level: 1 })).toBeInTheDocument();
    const days = await screen.findAllByRole('region');
    expect(days.map((d) => within(d).getByRole('heading').textContent)).toEqual([
      'Friday, November 27, 2026',
      'Thursday, November 26, 2026',
    ]);
    const friday = within(days[0]).getAllByRole('listitem');
    expect(friday.map((li) => li.textContent)).toEqual([
      '11:05 AMDoor openingGarage, app, the door was still, by Ana Pérez',
      '10:00 AMLight on for 2 minShed, automatic',
      '12:30 AMDoor closedGarage, button or remote, the door was stopped',
    ]);
    expect(within(days[1]).getByRole('listitem')).toHaveTextContent(
      '9:00 PMDevice startedGarage, by a user without a name',
    );
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('aria-current', 'page');
  });

  it('filters by device, event and dates, and keeps the filters in the address', async () => {
    server.use(withSession(makeUser({ timezone: 'Europe/Madrid' })));
    const asked = serveEvents();
    const { router } = renderWithProviders(<AppRoutes />, { route: '/history' });
    await screen.findAllByRole('region');

    await userEvent.click(field('Device'));
    await userEvent.click(await screen.findByRole('option', { name: 'Shed' }));
    await userEvent.click(field('Events'));
    await userEvent.click(await screen.findByRole('option', { name: 'Light on' }));
    await userEvent.click(await screen.findByRole('option', { name: 'Close failed' }));
    await userEvent.type(screen.getByLabelText('From'), '2026-11-27');
    await userEvent.type(screen.getByLabelText('To'), '2026-11-27');

    await vi.waitFor(() => {
      const last = asked.at(-1);
      expect(last.get('device')).toBe('2');
      expect(last.getAll('event')).toEqual(['light_on', 'close_failed']);
      expect(last.get('from')).toBe('2026-11-26T23:00:00.000Z');
      expect(last.get('to')).toBe('2026-11-27T23:00:00.000Z');
    });
    expect(router.location.search).toBe(
      '?device=2&event=light_on&event=close_failed&from=2026-11-27&to=2026-11-27',
    );
  });

  it('opens with the filters of its address, ignoring malformed dates', async () => {
    server.use(withSession());
    const asked = serveEvents([]);
    renderWithProviders(<AppRoutes />, { route: '/history?event=night&from=yesterday&page=x' });

    expect(await screen.findByText('No events match these filters.')).toBeInTheDocument();
    expect(asked[0].getAll('event')).toEqual(['night']);
    expect(asked[0].get('from')).toBeNull();
    expect(asked[0].get('page')).toBe('1');
  });

  it('says when nothing has happened yet', async () => {
    server.use(withSession());
    serveEvents([]);
    renderWithProviders(<AppRoutes />, { route: '/history' });

    expect(await screen.findByText('Nothing has happened yet.')).toBeInTheDocument();
  });

  it('pages through long histories', async () => {
    server.use(withSession());
    const asked = serveEvents(EVENTS, 120);
    const { router } = renderWithProviders(<AppRoutes />, { route: '/history' });

    await userEvent.click(await screen.findByRole('button', { name: 'Page 2' }));
    await vi.waitFor(() => expect(asked.at(-1).get('page')).toBe('2'));
    expect(router.location.search).toBe('?page=2');
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }));
    await vi.waitFor(() => expect(asked.at(-1).get('page')).toBe('3'));
  });

  it('shows one device history, reached from its page', async () => {
    let asked;
    server.use(
      withSession(),
      http.get('/api/devices/1', () => HttpResponse.json(makeDevice())),
      http.get('/api/devices/1/events', ({ request }) => {
        asked = new URL(request.url).searchParams;
        return HttpResponse.json({ items: EVENTS.slice(0, 1), total: 1, page: 1, size: 50 });
      }),
    );
    renderWithProviders(<AppRoutes />, { route: '/devices/1' });

    await userEvent.click(await screen.findByRole('link', { name: 'See its history' }));
    expect(await screen.findByRole('heading', { name: 'History of Garage' })).toBeInTheDocument();
    const inputs = screen.queryAllByLabelText('Device').filter((e) => e.tagName === 'INPUT');
    expect(inputs).toEqual([]); // no device filter on one device's history
    expect(within(await screen.findByRole('region')).getByRole('listitem')).toHaveTextContent(
      'Door openingapp, the door was still, by Ana Pérez',
    );
    expect(asked.get('device')).toBeNull();
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('aria-current', 'page');
    await userEvent.click(screen.getByRole('link', { name: 'Back to Garage' }));
    expect(await screen.findByRole('heading', { name: 'Garage', level: 1 })).toBeInTheDocument();
  });

  it('says when the device of a history does not exist', async () => {
    server.use(
      withSession(),
      http.get('/api/devices/9', () => apiError(404, 'device_not_found')),
      http.get('/api/devices/9/events', () => apiError(404, 'device_not_found')),
    );
    renderWithProviders(<AppRoutes />, { route: '/devices/9/history' });

    expect(await screen.findByRole('heading', { name: 'Device not found' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See the history of every device' })).toHaveAttribute(
      'href',
      '/history',
    );
    expect(screen.queryByText('The device no longer exists.')).not.toBeInTheDocument();
  });

  it('leads back from a page past the last one', async () => {
    server.use(withSession());
    const asked = serveEvents([], 3);
    renderWithProviders(<AppRoutes />, { route: '/history?page=4' });

    expect(await screen.findByText('There are no events on this page.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Go to the first page' }));
    await vi.waitFor(() => expect(asked.at(-1).get('page')).toBe('1'));
  });
});
