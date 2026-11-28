// A registered garage board as /api/devices answers it.
export const ENTITIES = [
  {
    id: 'door',
    type: 'cover',
    device_class: 'garage',
    state: 'door.state',
    commands: ['open', 'close', 'stop', 'toggle'],
  },
  { id: 'light', type: 'light', state: 'light.state', commands: ['on', 'off', 'toggle'] },
  {
    id: 'door_problem',
    type: 'binary_sensor',
    device_class: 'problem',
    state: 'door.close_failed',
  },
  { id: 'night', type: 'binary_sensor', state: 'night' },
  { id: 'light_level', type: 'sensor', state: 'light_level' },
  { id: 'rssi', type: 'sensor', device_class: 'signal_strength', unit: 'dBm', state: 'wifi.rssi' },
];

export function garageState({ door = {}, light = {}, ...rest } = {}) {
  return {
    rev: 3,
    uptime_s: 3700,
    door: {
      state: 'closed',
      moving: false,
      sensor_closed: true,
      close_failed: false,
      stopped: 'none',
      since_s: 7300,
      last_source: 'button',
      ...door,
    },
    light: { state: 'off', timed: false, remaining_s: 0, ...light },
    night: false,
    light_level: 420,
    button: false,
    display: true,
    wifi: { ip: '10.1.3.103', rssi: -60 },
    ...rest,
  };
}

export function makeDevice({ state, ...overrides } = {}) {
  return {
    id: 1,
    device_id: 'garage-3562d4',
    type: 'garage',
    name: 'Garage',
    model: 'Garage IoT Controller (UNO R4 WiFi)',
    host: '10.1.3.103',
    has_token: true,
    sw_version: '2.0.6',
    modem_fw: '0.6.0',
    mode: 'normal',
    reset_reason: 'power',
    mac: 'B4:3A:45:35:62:D4',
    entities: ENTITIES,
    state: garageState(state),
    rev: 3,
    online: true,
    last_seen_at: '2026-11-27T10:00:00Z',
    uptime_s: 3700,
    created_at: '2026-11-27T09:00:00Z',
    ...overrides,
  };
}

export const page = (items) => ({ items, total: items.length, page: 1, size: 100 });
