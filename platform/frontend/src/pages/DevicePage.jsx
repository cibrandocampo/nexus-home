import { Anchor, Group, Loader, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { Moon, Sun } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { useAuth } from '../auth/useAuth';
import { useDevice } from '../devices/devicesApi';
import { DoorControl } from '../devices/DoorControl';
import { formatDateTime, formatSeconds, valueAt } from '../devices/format';
import { LightControl } from '../devices/LightControl';
import { OnlineStatus } from '../devices/OnlineStatus';
import classes from './DevicePage.module.css';

function Section({ title, children }) {
  return (
    <Paper withBorder p="md" radius="md" component="section" aria-label={title}>
      <Stack gap="sm">
        <Title order={2} size="h3">
          {title}
        </Title>
        {children}
      </Stack>
    </Paper>
  );
}

// A binary sensor or a sensor, in words.
function reading(t, entity, value) {
  if (value === undefined || value === null) return t('entities.unknown');
  if (entity.type === 'binary_sensor')
    return t(`entities.values.${entity.id}.${value}`, {
      defaultValue: t(value ? 'entities.yes' : 'entities.no'),
    });
  return entity.unit ? `${value} ${entity.unit}` : String(value);
}

function Sensors({ device }) {
  const { t } = useTranslation();
  const sensors = device.entities.filter((e) => e.type === 'sensor' || e.type === 'binary_sensor');
  if (sensors.length === 0) return null;
  const night = device.state?.night;
  return (
    <Section title={t('device.sensors')}>
      <dl className={classes.list}>
        {sensors.map((entity) => (
          <div key={entity.id} className={classes.row}>
            <dt>{t(`entities.names.${entity.id}`, { defaultValue: entity.id })}</dt>
            <dd>
              {entity.id === 'light_level' && night !== undefined && (
                <span className={classes.icon}>
                  {night ? <Moon aria-hidden size={16} /> : <Sun aria-hidden size={16} />}
                </span>
              )}
              {reading(t, entity, valueAt(device.state ?? {}, entity.state))}
            </dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}

function About({ device }) {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const rows = [
    ['model', device.model],
    ['firmware', device.sw_version],
    ['modem', device.modem_fw],
    ['address', device.host],
    // The board's own IP, when the device is registered by name or the board moved.
    ['ip', device.state?.wifi?.ip !== device.host ? device.state?.wifi?.ip : null],
    ['id', device.device_id],
    ['uptime', device.uptime_s != null ? formatSeconds(device.uptime_s, i18n.language) : null],
    [
      'lastSeen',
      device.last_seen_at
        ? formatDateTime(device.last_seen_at, i18n.language, user.timezone)
        : null,
    ],
  ].filter(([, value]) => value);
  return (
    <Section title={t('device.about')}>
      <dl className={classes.list}>
        {rows.map(([key, value]) => (
          <div key={key} className={classes.row}>
            <dt>{t(`device.fields.${key}`)}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}

export function DevicePage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { data: device, isPending, error } = useDevice(id);

  if (isPending) return <Loader aria-label={t('common.loading')} />;
  if (error || !device) {
    return (
      <Stack>
        <Title order={1}>{t('device.notFound')}</Title>
        <Anchor component={Link} to="/">
          {t('notFound.back')}
        </Anchor>
      </Stack>
    );
  }
  const covers = device.entities.filter((e) => e.type === 'cover');
  const lights = device.entities.filter((e) => e.type === 'light');

  return (
    <Stack>
      <Group justify="space-between" wrap="wrap" gap="xs" align="baseline">
        <Title order={1}>{device.name}</Title>
        <OnlineStatus device={device} />
      </Group>
      <Anchor component={Link} to={`/devices/${device.id}/history`}>
        {t('device.history')}
      </Anchor>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        {covers.map((entity) => (
          <Section key={entity.id} title={t('device.door')}>
            <DoorControl device={device} entity={entity} />
          </Section>
        ))}
        {lights.map((entity) => (
          <Section key={entity.id} title={t('device.light')}>
            <LightControl device={device} entity={entity} withDuration />
          </Section>
        ))}
        <Sensors device={device} />
        <About device={device} />
      </SimpleGrid>
    </Stack>
  );
}
