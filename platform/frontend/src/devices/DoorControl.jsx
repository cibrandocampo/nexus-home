import { Alert, Button, Group, Modal, Stack, Text } from '@mantine/core';
import { TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useCommand } from './devicesApi';
import classes from './DoorControl.module.css';
import { formatSeconds, valueAt } from './format';

// What the door shows: the cover's state, and for a garage board the details its own page shows.
function doorView(device, entity) {
  const state = valueAt(device.state ?? {}, entity.state);
  const door = device.type === 'garage' ? device.state?.door : null;
  const stopped = state === 'open' && door?.stopped && door.stopped !== 'none';
  return { state, door, label: stopped ? 'stopped' : state };
}

// Which commands make sense now (the board would answer `noop` or `door_busy` to the others).
function available(state, door) {
  const moving = state === 'opening' || state === 'closing';
  const stopped = door?.stopped && door.stopped !== 'none';
  return {
    // The opposite command while moving is refused (door_busy): only Stop then.
    open: state === 'closed' || (state === 'open' && stopped),
    close: state === 'open',
    stop: moving,
  };
}

export function DoorControl({ device, entity }) {
  const { t, i18n } = useTranslation();
  const command = useCommand(device);
  const [asking, setAsking] = useState(null);
  const { state, door, label } = doorView(device, entity);
  const can = available(state, door);
  const offline = !device.online;

  function confirm() {
    command.mutate({ entity: entity.id, command: asking });
    setAsking(null);
  }

  return (
    <Stack gap="sm">
      <div>
        {/* Announced when it changes, so a screen reader hears the door move. */}
        <Text className={classes.state} role="status" data-state={label ?? 'unknown'}>
          {t(`door.states.${label ?? 'unknown'}`)}
        </Text>
        {door && (
          <Text c="dimmed" size="sm">
            {t('door.since', {
              time: formatSeconds(door.since_s, i18n.language),
              source: t(`door.sources.${door.last_source}`, { defaultValue: door.last_source }),
              context: door.last_source === 'none' ? 'nobody' : undefined,
            })}
          </Text>
        )}
      </div>
      {door?.close_failed && (
        <Alert color="red" icon={<TriangleAlert aria-hidden size={18} />} p="xs">
          {t('door.closeFailed')}
        </Alert>
      )}
      <Group gap="xs">
        {['open', 'close', 'stop'].map((name) =>
          entity.commands?.includes(name) ? (
            <Button
              key={name}
              className={classes.action}
              variant={name === 'stop' ? 'default' : 'filled'}
              disabled={offline || !can[name] || command.isPending}
              onClick={() => setAsking(name)}
            >
              {t(`door.commands.${name}`)}
            </Button>
          ) : null,
        )}
      </Group>
      <Modal
        opened={asking !== null}
        onClose={() => setAsking(null)}
        title={asking && t(`door.confirm.${asking}.title`, { name: device.name })}
        closeButtonProps={{ 'aria-label': t('common.close') }}
      >
        <Stack>
          <Text>{t('door.confirm.text')}</Text>
          <Group justify="flex-end">
            {/* The safe choice gets the focus (a door command is never sent by a stray Enter). */}
            <Button variant="default" onClick={() => setAsking(null)} data-autofocus>
              {t('common.cancel')}
            </Button>
            <Button onClick={confirm}>{asking && t(`door.confirm.${asking}.action`)}</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
