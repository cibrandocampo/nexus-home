import { describe, expect, it } from 'vitest';

import i18n from '../i18n';
import { eventCause, eventTitle } from './eventLabels';

const t = i18n.getFixedT('en');

describe('event words', () => {
  it.each([
    [{ event: 'door_opening', value: 0 }, 'Door opening'],
    [{ event: 'light_on', value: 600 }, 'Light on for 10 min'],
    [{ event: 'light_on', value: 0 }, 'Light on, no timer'],
    [{ event: 'close_failed', value: 40 }, 'The door did not close after 40 sec'],
    [{ event: 'something_new', value: 0 }, 'something_new'],
  ])('%o is "%s"', (item, title) => {
    expect(eventTitle(t, item, 'en')).toBe(title);
  });

  it('says who started it and why, leaving out what is unknown', () => {
    expect(eventCause(t, { source: 'button', reason: 'stopped' })).toBe(
      'button or remote, the door was stopped',
    );
    expect(eventCause(t, { source: 'auto', reason: 'none' })).toBe('automatic');
    expect(eventCause(t, { source: 'none', reason: 'startup' })).toBe('read at start-up');
    expect(eventCause(t, { source: 'none', reason: 'none' })).toBe('');
  });
});
