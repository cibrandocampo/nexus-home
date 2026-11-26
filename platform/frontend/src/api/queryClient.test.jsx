import { notifications } from '@mantine/notifications';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from './client';
import { createQueryClient, notifyError } from './queryClient';

describe('error notifications', () => {
  it('translates a known API error code', () => {
    const show = vi.spyOn(notifications, 'show').mockImplementation(() => '');

    notifyError(new ApiError(429, 'rate_limited', 'Too many'));

    expect(show).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Too many attempts. Please wait a moment and try again.',
      }),
    );
    show.mockRestore();
  });

  it('uses a generic message for unknown codes', () => {
    const show = vi.spyOn(notifications, 'show').mockImplementation(() => '');

    notifyError(new ApiError(500, 'something_odd', 'odd'));

    expect(show).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Unexpected error. Please try again.' }),
    );
    show.mockRestore();
  });

  it('notifies failed queries and unhandled mutation errors only', async () => {
    const show = vi.spyOn(notifications, 'show').mockImplementation(() => '');
    const client = createQueryClient();
    const fail = () => Promise.reject(new ApiError(500, 'x', 'x'));

    await client.fetchQuery({ queryKey: ['q'], queryFn: fail }).catch(() => {});
    await client
      .getMutationCache()
      .build(client, { mutationFn: fail })
      .execute()
      .catch(() => {});
    await client
      .getMutationCache()
      .build(client, { mutationFn: fail, onError: () => {} })
      .execute()
      .catch(() => {});

    expect(show).toHaveBeenCalledTimes(2);
    show.mockRestore();
  });
});
