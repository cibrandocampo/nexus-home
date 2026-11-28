import { Group, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../auth/useAuth';
import { formatDateTime } from './format';
import classes from './OnlineStatus.module.css';

export function OnlineStatus({ device }) {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const seen = device.last_seen_at
    ? formatDateTime(device.last_seen_at, i18n.language, user.timezone)
    : null;
  return (
    <Group gap={6} wrap="nowrap">
      <span className={classes.dot} data-online={device.online} aria-hidden />
      <Text size="sm" c={device.online ? undefined : 'dimmed'}>
        {device.online
          ? t('devices.online')
          : seen
            ? t('devices.offlineSince', { time: seen })
            : t('devices.offline')}
      </Text>
    </Group>
  );
}
