// IANA time zones for the profile's picker, labelled with their current UTC offset.

export function browserTimeZone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function offsetOf(zone) {
  const part = new Intl.DateTimeFormat('en', { timeZone: zone, timeZoneName: 'shortOffset' })
    .formatToParts(new Date())
    .find(({ type }) => type === 'timeZoneName');
  return part?.value.replace('GMT', 'UTC') ?? 'UTC';
}

let options;

// Built once: formatting ~400 zones is not free. UTC is listed first (new accounts start there).
export function timeZoneOptions() {
  options ??= ['UTC', ...Intl.supportedValuesOf('timeZone').filter((zone) => zone !== 'UTC')].map(
    (zone) => ({ value: zone, label: `${zone.replaceAll('_', ' ')} (${offsetOf(zone)})` }),
  );
  return options;
}
