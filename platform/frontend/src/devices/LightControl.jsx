import { Button, Group, Select, Text } from '@mantine/core';
import { Lightbulb, LightbulbOff } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useCommand } from './devicesApi';
import classes from './DoorControl.module.css';
import { formatSeconds, valueAt } from './format';

// Light durations offered on the device page (seconds; "default" sends none: the board's light time).
const DURATIONS = ['default', '600', '3600', '0'];

export function LightControl({ device, entity, withDuration = false }) {
  const { t, i18n } = useTranslation();
  const command = useCommand(device);
  const [duration, setDuration] = useState('default');
  const on = valueAt(device.state ?? {}, entity.state) === 'on';
  const light = device.type === 'garage' ? device.state?.light : null;
  const disabled = !device.online || command.isPending;
  const Icon = on ? Lightbulb : LightbulbOff;

  function turnOn() {
    const body = duration === 'default' ? undefined : { duration: Number(duration) };
    command.mutate({ entity: entity.id, command: 'on', body });
  }

  return (
    <Group justify="space-between" wrap="wrap" gap="sm">
      <Group gap="xs" wrap="nowrap">
        <Icon aria-hidden size={20} />
        <Text role="status">
          {on && light?.timed
            ? t('light.onFor', { time: formatSeconds(light.remaining_s, i18n.language) })
            : t(on ? 'light.on' : 'light.off')}
        </Text>
      </Group>
      <Group gap="xs">
        {withDuration && !on && (
          <Select
            aria-label={t('light.duration')}
            data={DURATIONS.map((value) => ({ value, label: t(`light.durations.${value}`) }))}
            value={duration}
            onChange={(value) => setDuration(value ?? 'default')}
            allowDeselect={false}
            w={160}
          />
        )}
        {on ? (
          <Button
            className={classes.action}
            variant="default"
            disabled={disabled}
            onClick={() => command.mutate({ entity: entity.id, command: 'off' })}
          >
            {t('light.turnOff')}
          </Button>
        ) : (
          <Button className={classes.action} variant="default" disabled={disabled} onClick={turnOn}>
            {t('light.turnOn')}
          </Button>
        )}
      </Group>
    </Group>
  );
}
