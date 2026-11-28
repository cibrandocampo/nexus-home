import { formatSeconds } from './format';

// The garage board's events (README "Event log"), grouped for the history's filter.
export const EVENT_GROUPS = {
  door: [
    'door_opening',
    'door_open',
    'door_closing',
    'door_closed',
    'close_failed',
    'button_ignored',
  ],
  light: ['light_on', 'light_off'],
  daylight: ['night', 'day'],
  device: [
    'boot',
    'wifi_up',
    'wifi_down',
    'wifi_changed',
    'wifi_change_failed',
    'watchdog_reset',
    'settings_changed',
    'settings_save_failed',
    'setup_mode',
  ],
};

// What happened, in words: "Light on for 10 min", "Close failed after 40 sec".
export function eventTitle(t, { event, value }, locale) {
  if (event === 'light_on') {
    return value > 0
      ? t('history.events.light_on_timed', { time: formatSeconds(value, locale) })
      : t('history.events.light_on_untimed');
  }
  if (event === 'close_failed') {
    return t('history.events.close_failed', { time: formatSeconds(value, locale) });
  }
  return t(`history.events.${event}`, { defaultValue: event });
}

// Who started it and why: "Button or remote, the door was stopped".
export function eventCause(t, { source, reason }) {
  const parts = [];
  if (source !== 'none') parts.push(t(`history.sources.${source}`, { defaultValue: source }));
  if (reason !== 'none') parts.push(t(`history.reasons.${reason}`, { defaultValue: reason }));
  return parts.join(', ');
}
