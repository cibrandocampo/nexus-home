import { Anchor, Divider, Group, Paper, Stack, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { DoorControl } from './DoorControl';
import { LightControl } from './LightControl';
import { OnlineStatus } from './OnlineStatus';

// The dashboard's card: the device's door and light with their quick actions.
export function DeviceCard({ device }) {
  const { t } = useTranslation();
  const covers = device.entities.filter((e) => e.type === 'cover');
  const lights = device.entities.filter((e) => e.type === 'light');

  return (
    <Paper
      withBorder
      p="md"
      radius="md"
      component="article"
      aria-labelledby={`device-${device.id}`}
    >
      <Stack gap="md">
        <Group justify="space-between" wrap="wrap" gap="xs">
          <Title order={2} size="h3" id={`device-${device.id}`}>
            <Anchor component={Link} to={`/devices/${device.id}`} inherit underline="hover">
              {device.name}
            </Anchor>
          </Title>
          <OnlineStatus device={device} />
        </Group>
        {covers.map((entity) => (
          <DoorControl key={entity.id} device={device} entity={entity} />
        ))}
        {lights.length > 0 && covers.length > 0 && <Divider />}
        {lights.map((entity) => (
          <LightControl key={entity.id} device={device} entity={entity} />
        ))}
        {covers.length + lights.length === 0 && (
          <Anchor component={Link} to={`/devices/${device.id}`}>
            {t('devices.details')}
          </Anchor>
        )}
      </Stack>
    </Paper>
  );
}
