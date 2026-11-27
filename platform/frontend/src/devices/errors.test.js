import { describe, expect, it } from 'vitest';

import en from '../i18n/en.json';
import es from '../i18n/es.json';
import gl from '../i18n/gl.json';

// Every error code the devices API answers (platform/backend/app/devices), including the board's
// own codes it passes through: each one has its own message, never the generic one.
const CODES = [
  'command_not_found',
  'device_error',
  'device_exists',
  'device_has_no_token',
  'device_mismatch',
  'device_not_found',
  'device_offline',
  'device_save_failed',
  'device_token_invalid',
  'device_token_required',
  'device_token_unchanged',
  'device_token_unconfirmed',
  'device_token_unreadable',
  'device_unreachable',
  'door_busy',
  'entity_not_found',
  'invalid_close_time',
  'invalid_display',
  'invalid_duration',
  'invalid_light_time',
  'invalid_name',
  'invalid_night_level',
  'invalid_open_time',
  'invalid_params',
  'invalid_scan_ranges',
  'not_a_device',
  'scan_in_progress',
  'scan_too_large',
  'settings_not_supported',
];

describe('device error messages', () => {
  it.each([
    ['en', en],
    ['es', es],
    ['gl', gl],
  ])('exist in %s', (_, messages) => {
    expect(CODES.filter((code) => !messages.errors[code])).toEqual([]);
  });
});
