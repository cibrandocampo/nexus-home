import { describe, expect, it } from 'vitest';

import { formatDateTime, formatSeconds, valueAt } from './format';

describe('device formats', () => {
  it('reads an entity value by its state path', () => {
    const state = { door: { state: 'open' }, wifi: { rssi: -60 }, night: false };

    expect(valueAt(state, 'door.state')).toBe('open');
    expect(valueAt(state, 'wifi.rssi')).toBe(-60);
    expect(valueAt(state, 'night')).toBe(false);
    expect(valueAt(state, 'light.state')).toBeUndefined();
  });

  it('shows the two largest units of a span', () => {
    expect(formatSeconds(0, 'en')).toBe('0 sec');
    expect(formatSeconds(45, 'en')).toBe('45 sec');
    expect(formatSeconds(125, 'en')).toBe('2 min, 5 sec');
    expect(formatSeconds(7300, 'en')).toBe('2 hr, 1 min');
    expect(formatSeconds(90061, 'en')).toBe('1 day, 1 hr');
    expect(formatSeconds(-5, 'en')).toBe('0 sec');
  });

  it('writes spans in the user language', () => {
    expect(formatSeconds(7300, 'es')).toMatch(/2 h/);
  });

  it('shows a time in the user time zone', () => {
    expect(formatDateTime('2026-11-27T10:00:00Z', 'en', 'Europe/Madrid')).toBe(
      'Nov 27, 2026, 11:00 AM',
    );
    expect(formatDateTime('2026-11-27T10:00:00Z', 'en', 'UTC')).toBe('Nov 27, 2026, 10:00 AM');
  });
});
