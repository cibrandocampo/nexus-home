import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../../api/client';

export const PAGE_SIZE = 20;

export function useUsers({ q, role, active, page }) {
  const params = new URLSearchParams({ page: String(page), size: String(PAGE_SIZE) });
  if (q) params.set('q', q);
  if (role) params.set('role', role);
  if (active) params.set('active', active);
  return useQuery({
    queryKey: ['users', q, role, active, page],
    queryFn: () => api(`/users?${params}`),
    placeholderData: (previous) => previous,
  });
}

// Mutations refresh the list; their errors are shown by the dialog that started them.
function useUserMutation(request) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
    onError: () => {},
  });
}

export const useCreateUser = () =>
  useUserMutation((body) => api('/users', { method: 'POST', body }));
export const useUpdateUser = () =>
  useUserMutation(({ id, ...body }) => api(`/users/${id}`, { method: 'PATCH', body }));
export const useSetPassword = () =>
  useUserMutation(({ id, password }) =>
    api(`/users/${id}/set-password`, { method: 'POST', body: { password } }),
  );
export const useDeleteUser = () =>
  useUserMutation((id) => api(`/users/${id}`, { method: 'DELETE' }));
