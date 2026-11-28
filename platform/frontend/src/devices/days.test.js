import { describe, expect, it } from 'vitest';

import { dayOf, formatDay, formatTime, startOfDay } from './days';

describe('days in a time zone', () => {
  it('finds when a day starts, and the next one', () => {
    expect(startOfDay('2026-11-27', 'Europe/Madrid')).toBe('2026-11-26T23:00:00.000Z');
    expect(startOfDay('2026-11-27', 'Europe/Madrid', 1)).toBe('2026-11-27T23:00:00.000Z');
    expect(startOfDay('2026-11-27', 'UTC')).toBe('2026-11-27T00:00:00.000Z');
    expect(startOfDay('2026-11-27', 'America/New_York')).toBe('2026-11-27T05:00:00.000Z');
  });

  it('handles the days the clocks change', () => {
    // Madrid moves to summer time on 29 March 2026: that day has 23 hours.
    expect(startOfDay('2026-03-29', 'Europe/Madrid')).toBe('2026-03-28T23:00:00.000Z');
    expect(startOfDay('2026-03-29', 'Europe/Madrid', 1)).toBe('2026-03-29T22:00:00.000Z');
  });

  it('names the day of an instant and formats it', () => {
    expect(dayOf('2026-11-26T23:30:00Z', 'Europe/Madrid')).toBe('2026-11-27');
    expect(dayOf('2026-11-26T23:30:00Z', 'UTC')).toBe('2026-11-26');
    expect(formatDay('2026-11-27', 'en')).toBe('Friday, November 27, 2026');
    expect(formatTime('2026-11-27T10:05:00Z', 'en', 'Europe/Madrid')).toBe('11:05 AM');
  });
});
