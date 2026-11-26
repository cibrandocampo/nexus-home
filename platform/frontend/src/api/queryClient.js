import { notifications } from '@mantine/notifications';
import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';

import i18n from '../i18n';

// Errors nobody handles locally are shown as a notification, translated by their API code.
export function notifyError(error) {
  const key = `errors.${error?.code}`;
  notifications.show({
    color: 'red',
    title: i18n.t('errors.title'),
    message: i18n.exists(key) ? i18n.t(key) : i18n.t('errors.generic'),
  });
}

export function createQueryClient() {
  return new QueryClient({
    queryCache: new QueryCache({ onError: notifyError }),
    mutationCache: new MutationCache({
      onError: (error, _vars, _ctx, mutation) => {
        if (!mutation.options.onError) notifyError(error);
      },
    }),
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
}
