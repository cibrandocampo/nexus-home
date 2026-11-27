// Calendar days in the user's time zone, for the history's date filters and day headings.

function offsetMs(instant, timeZone) {
  // How far the zone's wall clock is ahead of UTC at this instant.
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone,
      hourCycle: 'h23',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
      .formatToParts(instant)
      .map(({ type, value }) => [type, value]),
  );
  const wall = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
    parts.second,
  );
  return wall - instant.getTime();
}

// The instant a day (YYYY-MM-DD) starts in a time zone, as ISO 8601 UTC. `plusDays` moves the day.
export function startOfDay(day, timeZone, plusDays = 0) {
  const [y, m, d] = day.split('-').map(Number);
  const midnight = Date.UTC(y, m - 1, d + plusDays);
  // Two passes: the offset at the guess, then at the corrected instant (a DST change that day).
  let instant = midnight - offsetMs(new Date(midnight), timeZone);
  instant = midnight - offsetMs(new Date(instant), timeZone);
  return new Date(instant).toISOString();
}

// The calendar day (YYYY-MM-DD) of an instant in a time zone.
export function dayOf(iso, timeZone) {
  return new Intl.DateTimeFormat('en-CA', { timeZone }).format(new Date(iso));
}

export function formatDay(day, locale) {
  const [y, m, d] = day.split('-').map(Number);
  return new Intl.DateTimeFormat(locale, { dateStyle: 'full', timeZone: 'UTC' }).format(
    new Date(Date.UTC(y, m - 1, d)),
  );
}

export function formatTime(iso, locale, timeZone) {
  return new Intl.DateTimeFormat(locale, { timeStyle: 'short', timeZone }).format(new Date(iso));
}
