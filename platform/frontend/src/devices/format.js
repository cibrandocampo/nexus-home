// Reading a board's state and formatting its times for people.

// An entity's value from its `state` path in /info, e.g. "door.state" or "wifi.rssi".
export function valueAt(state, path) {
  return path.split('.').reduce((value, key) => (value == null ? undefined : value[key]), state);
}

// A span of seconds in words, the two largest units ("2 hr, 5 min"), in the given language.
export function formatSeconds(seconds, locale) {
  const total = Math.max(0, Math.floor(seconds));
  const units = {
    days: Math.floor(total / 86400),
    hours: Math.floor((total % 86400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
  };
  const used = Object.entries(units).filter(([, n]) => n > 0);
  if (used.length === 0) {
    // An all-zero duration formats as an empty string unless the seconds are asked for.
    return new Intl.DurationFormat(locale, { style: 'short', secondsDisplay: 'always' }).format({
      seconds: 0,
    });
  }
  return new Intl.DurationFormat(locale, { style: 'short' }).format(
    Object.fromEntries(used.slice(0, 2)),
  );
}

// A date and time in the user's time zone.
export function formatDateTime(iso, locale, timeZone) {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone,
  }).format(new Date(iso));
}
