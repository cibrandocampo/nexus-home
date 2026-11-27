import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../../api/client';

export function useScanRanges() {
  return useQuery({
    queryKey: ['devices', 'scan-ranges'],
    queryFn: () => api('/devices/scan-ranges'),
  });
}

// Mutations here show their errors in the page or dialog that started them (no toast).
// `secret`: its inputs or answer carry a device token; the mutation cache drops it as soon as the
// dialog that used it closes (TanStack keeps finished mutations for 5 minutes by default).
function useDeviceMutation(request, { secret = false } = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    ...(secret ? { gcTime: 0 } : {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['devices'] }),
    onError: () => {},
  });
}

export const useScan = () =>
  useMutation({
    mutationFn: (ranges) => api('/devices/scan', { method: 'POST', body: { ranges } }),
    onError: () => {},
  });
export const useAddDevice = () =>
  useDeviceMutation((body) => api('/devices', { method: 'POST', body }), { secret: true });
export const useRemoveDevice = () =>
  useDeviceMutation((id) => api(`/devices/${id}`, { method: 'DELETE' }));
export const useUpdateDevice = (id) =>
  useDeviceMutation((body) => api(`/devices/${id}`, { method: 'PATCH', body }), { secret: true });
export const useSaveSettings = (id) =>
  useDeviceMutation((body) => api(`/devices/${id}/settings`, { method: 'PATCH', body }));
export const useRestart = (id) =>
  useDeviceMutation(() => api(`/devices/${id}/restart`, { method: 'POST' }));
export const useRotateToken = (id) =>
  useDeviceMutation(() => api(`/devices/${id}/rotate-token`, { method: 'POST' }));
// A secret: read on demand, and dropped from the mutation cache when its dialog closes.
export const useRevealToken = (id) =>
  useMutation({ mutationFn: () => api(`/devices/${id}/token`), gcTime: 0, onError: () => {} });

export function useDeviceSettings(id) {
  return useQuery({
    queryKey: ['devices', 'settings', String(id)],
    queryFn: () => api(`/devices/${id}/settings`),
    meta: { handlesErrors: true },
  });
}
