import { Anchor, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { useAuth } from '../auth/useAuth';
import { DeviceCard } from '../devices/DeviceCard';
import { useDevices } from '../devices/devicesApi';

// The dashboard: every device with its state and quick actions (user decision 2026-11-27).
export function HomePage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { data, isPending } = useDevices();

  return (
    <Stack>
      <Title order={1}>{t('home.title')}</Title>
      {isPending && <Loader aria-label={t('common.loading')} />}
      {data && data.items.length === 0 && (
        <Stack gap="xs">
          <Text>{t('home.empty')}</Text>
          {user.role === 'admin' && (
            <Anchor component={Link} to="/admin/devices">
              {t('home.addDevice')}
            </Anchor>
          )}
        </Stack>
      )}
      {data && data.items.length > 0 && (
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
          {data.items.map((device) => (
            <DeviceCard key={device.id} device={device} />
          ))}
        </SimpleGrid>
      )}
    </Stack>
  );
}
