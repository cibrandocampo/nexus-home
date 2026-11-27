// The garage driver's settings (backend devices/drivers.py, board settings.h): what the settings
// form shows. The backend checks them too; these give the form its limits and hints.
export const GARAGE_FIELDS = {
  name: { bytes: 32 },
  open_s: { min: 5, max: 100 },
  close_s: { min: 10, max: 100 },
  light_s: { min: 10, max: 600 },
  night_level: { min: 1, max: 1023 },
};

export const byteLength = (text) => new TextEncoder().encode(text).length;
