import { useQuery } from '@tanstack/react-query';

import { api } from '../api/client';

export const HISTORY_SIZE = 50;

// The global history (/api/events) or one device's (/api/devices/{id}/events), filtered.
export function useEvents({ deviceId, device, events, from, to, page }) {
  const params = new URLSearchParams({ page: String(page), size: String(HISTORY_SIZE) });
  if (device) params.set('device', device);
  for (const event of events) params.append('event', event);
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  const path = deviceId ? `/devices/${deviceId}/events` : '/events';
  return useQuery({
    queryKey: ['events', deviceId ?? 'all', params.toString()],
    queryFn: () => api(`${path}?${params}`),
    placeholderData: (previous) => previous,
    // One device's history shows "Device not found" itself.
    meta: { handlesErrors: Boolean(deviceId) },
    // New events arrive as the boards report them: the first page follows them.
    refetchInterval: page === 1 ? 10_000 : false,
  });
}
