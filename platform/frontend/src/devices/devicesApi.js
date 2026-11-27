import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../api/client';

// The platform polls the boards every 2 s; the pages read the stored state at the same pace while
// they are visible (TanStack Query pauses the interval in a background tab).
export const REFRESH_MS = 2000;

export function useDevices() {
  return useQuery({
    queryKey: ['devices', 'list'],
    queryFn: () => api('/devices?size=100'),
    refetchInterval: REFRESH_MS,
  });
}

export function useDevice(id, options = {}) {
  return useQuery({
    ...options,
    queryKey: ['devices', 'detail', String(id)],
    queryFn: () => api(`/devices/${id}`),
    // The page says "Device not found" itself, and stops asking.
    refetchInterval: (query) => (query.state.error ? false : REFRESH_MS),
    meta: { handlesErrors: true },
  });
}

// A command answers the new state: written into both caches at once, so the page does not wait for
// the next refresh. Errors without a local handler are shown as a toast by the query client.
export function useCommand(device) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entity, command, body }) =>
      api(`/devices/${device.id}/entities/${entity}/${command}`, { method: 'POST', body }),
    onSuccess: ({ state }) => {
      queryClient.setQueryData(['devices', 'detail', String(device.id)], (old) =>
        old ? { ...old, state } : old,
      );
      queryClient.setQueryData(['devices', 'list'], (old) =>
        old
          ? { ...old, items: old.items.map((d) => (d.id === device.id ? { ...d, state } : d)) }
          : old,
      );
    },
  });
}
