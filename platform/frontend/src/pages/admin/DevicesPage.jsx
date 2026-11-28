import {
  ActionIcon,
  Anchor,
  Badge,
  Button,
  Group,
  Menu,
  Modal,
  Paper,
  PasswordInput,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { Ellipsis, Plus, Radar, Settings, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { DeviceErrorAlert } from '../../devices/DeviceErrorAlert';
import { useDevices } from '../../devices/devicesApi';
import { useAddDevice, useRemoveDevice, useScan, useScanRanges } from './devicesAdminApi';
import classes from './DevicesPage.module.css';

// Add a board: by address, or from a scan result (address given). The token is optional: a board
// without one gets a new token from the platform (user decision 2026-11-27).
function AddDialog({ host, onClose, onAdded }) {
  const { t } = useTranslation();
  const add = useAddDevice();
  const [address, setAddress] = useState(host ?? '');
  const [token, setToken] = useState('');

  function submit(event) {
    event.preventDefault();
    const body = { host: address.trim(), ...(token ? { token } : {}) };
    add.mutate(body, {
      onSuccess: (device) => {
        notifications.show({
          color: 'teal',
          message: t('adminDevices.added', { name: device.name }),
        });
        onAdded(address.trim());
        onClose();
      },
    });
  }

  return (
    <Modal
      opened
      onClose={onClose}
      title={t('adminDevices.add.title')}
      closeButtonProps={{ 'aria-label': t('common.close') }}
    >
      <form onSubmit={submit}>
        <Stack>
          <TextInput
            label={t('adminDevices.add.host')}
            description={t('adminDevices.add.hostHelp')}
            value={address}
            onChange={(e) => setAddress(e.currentTarget.value)}
            required
            readOnly={Boolean(host)}
            data-autofocus={host ? undefined : true}
          />
          <PasswordInput
            label={t('adminDevices.add.token')}
            description={t('adminDevices.add.tokenHelp')}
            value={token}
            onChange={(e) => setToken(e.currentTarget.value)}
            data-autofocus={host ? true : undefined}
            autoComplete="off"
          />
          <DeviceErrorAlert
            error={add.error}
            messages={{ device_token_invalid: t('adminDevices.add.tokenInvalid') }}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={add.isPending} disabled={!address.trim()}>
              {t('adminDevices.add.submit')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

function RemoveDialog({ device, onClose }) {
  const { t } = useTranslation();
  const remove = useRemoveDevice();
  return (
    <Modal
      opened
      onClose={onClose}
      title={t('adminDevices.remove.title', { name: device.name })}
      closeButtonProps={{ 'aria-label': t('common.close') }}
    >
      <Stack>
        <Text>{t('adminDevices.remove.text')}</Text>
        <DeviceErrorAlert error={remove.error} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose} data-autofocus>
            {t('common.cancel')}
          </Button>
          <Button
            color="red"
            loading={remove.isPending}
            onClick={() =>
              remove.mutate(device.id, {
                onSuccess: () => {
                  notifications.show({
                    color: 'teal',
                    message: t('adminDevices.removed', { name: device.name }),
                  });
                  onClose();
                },
              })
            }
          >
            {t('adminDevices.remove.submit')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Registered({ onRemove }) {
  const { t } = useTranslation();
  const { data } = useDevices();
  if (!data) return null;
  if (data.items.length === 0) return <Text>{t('adminDevices.none')}</Text>;
  return (
    <Table verticalSpacing="sm" className={classes.table}>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>{t('adminDevices.device')}</Table.Th>
          <Table.Th>{t('adminDevices.status')}</Table.Th>
          <Table.Th className={classes.actions}>
            <VisuallyHidden>{t('adminDevices.actions')}</VisuallyHidden>
          </Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {data.items.map((device) => (
          <Table.Tr key={device.id}>
            <Table.Td>
              <Anchor component={Link} to={`/admin/devices/${device.id}`} fw={600}>
                {device.name}
              </Anchor>
              <Text size="sm" c="dimmed">
                {t('adminDevices.where', {
                  id: device.device_id,
                  host: device.host,
                  version: device.sw_version,
                })}
              </Text>
            </Table.Td>
            <Table.Td>
              <Badge color={device.online ? 'teal' : 'gray'} variant="light">
                {t(device.online ? 'devices.online' : 'devices.offline')}
              </Badge>
            </Table.Td>
            <Table.Td className={classes.actions}>
              <Menu position="bottom-end">
                <Menu.Target>
                  <ActionIcon
                    variant="subtle"
                    color="gray"
                    aria-label={t('adminDevices.actionsFor', { name: device.name })}
                  >
                    <Ellipsis size={18} aria-hidden />
                  </ActionIcon>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Item
                    component={Link}
                    to={`/admin/devices/${device.id}`}
                    leftSection={<Settings size={16} aria-hidden />}
                  >
                    {t('adminDevices.settings')}
                  </Menu.Item>
                  <Menu.Divider />
                  <Menu.Item
                    color="red"
                    leftSection={<Trash2 size={16} aria-hidden />}
                    onClick={() => onRemove(device)}
                  >
                    {t('adminDevices.remove.action')}
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function Scan({ onAdd, added }) {
  const { t } = useTranslation();
  const defaults = useScanRanges();
  const scan = useScan();
  // The configured ranges until the admin types (null: untouched).
  const [typed, setTyped] = useState(null);
  const ranges = typed ?? defaults.data?.ranges.join(', ') ?? '';

  function submit(event) {
    event.preventDefault();
    const list = ranges
      .split(',')
      .map((r) => r.trim())
      .filter(Boolean);
    scan.mutate(list.length ? list : null);
  }

  return (
    <Paper withBorder p="md" radius="md" component="section" aria-labelledby="scan-title">
      <Stack gap="sm">
        <Title order={2} size="h3" id="scan-title">
          {t('adminDevices.scan.title')}
        </Title>
        <form onSubmit={submit}>
          <Group align="flex-end" gap="sm">
            <TextInput
              label={t('adminDevices.scan.ranges')}
              description={t('adminDevices.scan.rangesHelp')}
              value={ranges}
              onChange={(e) => setTyped(e.currentTarget.value)}
              className={classes.ranges}
            />
            <Button
              type="submit"
              loading={scan.isPending}
              leftSection={<Radar size={16} aria-hidden />}
            >
              {t('adminDevices.scan.submit')}
            </Button>
          </Group>
        </form>
        {scan.isPending && (
          <Text size="sm" c="dimmed" role="status">
            {t('adminDevices.scan.running')}
          </Text>
        )}
        <DeviceErrorAlert error={scan.error} />
        {scan.data && (
          <Stack gap="xs" role="status">
            <Text size="sm" c="dimmed">
              {t('adminDevices.scan.result', {
                count: scan.data.items.length,
                scanned: scan.data.scanned,
                seconds: scan.data.duration_s,
              })}
            </Text>
            {scan.data.items.map((found) => (
              <Group key={`${found.device_id}-${found.host}`} justify="space-between" wrap="wrap">
                <div>
                  <Text fw={600}>{found.name || found.device_id}</Text>
                  <Text size="sm" c="dimmed">
                    {t('adminDevices.where', {
                      id: found.device_id,
                      host: found.host,
                      version: found.sw_version,
                    })}
                  </Text>
                </div>
                {found.registered || added.includes(found.host) ? (
                  <Badge variant="light" color="gray">
                    {t('adminDevices.scan.registered')}
                  </Badge>
                ) : (
                  <Button
                    variant="default"
                    size="xs"
                    onClick={() => onAdd(found.host)}
                    aria-label={t('adminDevices.scan.addThis', {
                      name: found.name || found.device_id,
                    })}
                  >
                    {t('adminDevices.add.short')}
                  </Button>
                )}
              </Group>
            ))}
          </Stack>
        )}
      </Stack>
    </Paper>
  );
}

export function DevicesPage() {
  const { t } = useTranslation();
  const [adding, setAdding] = useState(null); // null: closed; '': by address; else a scanned host
  const [removing, setRemoving] = useState(null);
  const [added, setAdded] = useState([]); // scanned hosts added since: no longer offered

  return (
    <Stack>
      <Group justify="space-between" wrap="wrap">
        <Title order={1}>{t('adminDevices.title')}</Title>
        <Button
          variant="default"
          leftSection={<Plus size={16} aria-hidden />}
          onClick={() => setAdding('')}
        >
          {t('adminDevices.add.byAddress')}
        </Button>
      </Group>
      <Registered onRemove={setRemoving} />
      <Scan onAdd={setAdding} added={added} />
      {adding !== null && (
        <AddDialog
          host={adding || null}
          onClose={() => setAdding(null)}
          onAdded={(host) => setAdded((hosts) => [...hosts, host])}
        />
      )}
      {removing && <RemoveDialog device={removing} onClose={() => setRemoving(null)} />}
    </Stack>
  );
}
