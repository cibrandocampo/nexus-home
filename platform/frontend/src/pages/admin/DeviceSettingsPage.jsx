import {
  Anchor,
  Button,
  Code,
  CopyButton,
  Group,
  Loader,
  Modal,
  NumberInput,
  Paper,
  PasswordInput,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { DeviceErrorAlert } from '../../devices/DeviceErrorAlert';
import { useDevice } from '../../devices/devicesApi';
import { byteLength, GARAGE_FIELDS } from '../../devices/garageFields';
import {
  useDeviceSettings,
  useRestart,
  useRevealToken,
  useRotateToken,
  useSaveSettings,
  useUpdateDevice,
} from './devicesAdminApi';

const NUMBERS = ['open_s', 'close_s', 'light_s', 'night_level'];

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

// The garage board's stored settings; only the fields that changed are sent.
function SettingsForm({ device, settings }) {
  const { t } = useTranslation();
  const save = useSaveSettings(device.id);
  const form = useForm({
    initialValues: settings,
    validate: {
      name: (value) =>
        !value.trim()
          ? t('adminDevices.form.nameRequired')
          : byteLength(value.trim()) > GARAGE_FIELDS.name.bytes
            ? t('adminDevices.form.nameTooLong')
            : null,
      ...Object.fromEntries(
        NUMBERS.map((key) => [
          key,
          (value) =>
            Number.isInteger(value) &&
            value >= GARAGE_FIELDS[key].min &&
            value <= GARAGE_FIELDS[key].max
              ? null
              : t('adminDevices.form.range', GARAGE_FIELDS[key]),
        ]),
      ),
    },
  });

  const submit = form.onSubmit((values) => {
    const changed = Object.fromEntries(
      Object.entries({ ...values, name: values.name.trim() }).filter(([k, v]) => v !== settings[k]),
    );
    if (Object.keys(changed).length === 0) {
      notifications.show({ message: t('adminDevices.form.nothing') });
      return;
    }
    save.mutate(changed, {
      onSuccess: (saved) => {
        form.setInitialValues(saved);
        form.setValues(saved);
        notifications.show({ color: 'teal', message: t('adminDevices.form.saved') });
      },
      onError: (error) => {
        for (const detail of error.details ?? []) {
          const field = detail.loc?.at(-1);
          if (field in settings) form.setFieldError(field, t('adminDevices.form.refused'));
        }
      },
    });
  });

  const bytes = byteLength(form.values.name.trim());
  return (
    <form onSubmit={submit} noValidate>
      {/* Short values: a narrow column reads better than full-width fields. */}
      <Stack maw="30rem">
        <TextInput
          label={t('adminDevices.form.name')}
          description={t('adminDevices.form.bytes', {
            count: bytes,
            max: GARAGE_FIELDS.name.bytes,
          })}
          {...form.getInputProps('name')}
        />
        {NUMBERS.map((key) => (
          <NumberInput
            key={key}
            label={t(`adminDevices.form.${key}`)}
            description={t(`adminDevices.form.${key}Help`, GARAGE_FIELDS[key])}
            min={GARAGE_FIELDS[key].min}
            max={GARAGE_FIELDS[key].max}
            allowDecimal={false}
            allowNegative={false}
            clampBehavior="none"
            {...form.getInputProps(key)}
          />
        ))}
        <Switch
          label={t('adminDevices.form.display')}
          {...form.getInputProps('display', { type: 'checkbox' })}
        />
        <DeviceErrorAlert error={save.error} />
        <Group justify="flex-end">
          <Button type="submit" loading={save.isPending}>
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

function Confirm({ title, text, action, mutation, onDone, onClose }) {
  const { t } = useTranslation();
  return (
    <Modal
      opened
      onClose={onClose}
      title={title}
      closeButtonProps={{ 'aria-label': t('common.close') }}
    >
      <Stack>
        <Text>{text}</Text>
        <DeviceErrorAlert error={mutation.error} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose} data-autofocus>
            {t('common.cancel')}
          </Button>
          <Button
            loading={mutation.isPending}
            onClick={() =>
              mutation.mutate(undefined, {
                onSuccess: () => {
                  onDone();
                  onClose();
                },
              })
            }
          >
            {action}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function TokenValue({ label, value }) {
  const { t } = useTranslation();
  return (
    <Stack gap={4}>
      <Text size="sm" fw={600}>
        {label}
      </Text>
      <Group gap="xs" wrap="nowrap">
        <Code style={{ overflowWrap: 'anywhere' }}>{value}</Code>
        <CopyButton value={value}>
          {({ copied, copy }) => (
            <Button size="xs" variant="default" onClick={copy}>
              {t(copied ? 'adminDevices.token.copied' : 'adminDevices.token.copy')}
            </Button>
          )}
        </CopyButton>
      </Group>
    </Stack>
  );
}

function RevealDialog({ device, onClose }) {
  const { t } = useTranslation();
  const reveal = useRevealToken(device.id);
  return (
    <Modal
      opened
      onClose={onClose}
      title={t('adminDevices.token.revealTitle', { name: device.name })}
      closeButtonProps={{ 'aria-label': t('common.close') }}
    >
      <Stack>
        {!reveal.data && (
          <>
            <Text>{t('adminDevices.token.revealText')}</Text>
            <DeviceErrorAlert error={reveal.error} />
            <Group justify="flex-end">
              <Button variant="default" onClick={onClose}>
                {t('common.cancel')}
              </Button>
              <Button loading={reveal.isPending} onClick={() => reveal.mutate()} data-autofocus>
                {t('adminDevices.token.show')}
              </Button>
            </Group>
          </>
        )}
        {reveal.data && (
          <>
            <TokenValue label={t('adminDevices.token.current')} value={reveal.data.token} />
            {reveal.data.previous_token && (
              <>
                <Text size="sm" c="dimmed">
                  {t('adminDevices.token.previousHelp')}
                </Text>
                <TokenValue
                  label={t('adminDevices.token.previous')}
                  value={reveal.data.previous_token}
                />
              </>
            )}
            <Group justify="flex-end">
              <Button onClick={onClose} data-autofocus>
                {t('common.close')}
              </Button>
            </Group>
          </>
        )}
      </Stack>
    </Modal>
  );
}

function ConnectionDialog({ device, onClose }) {
  const { t } = useTranslation();
  const update = useUpdateDevice(device.id);
  const [host, setHost] = useState(device.host);
  const [token, setToken] = useState('');

  function submit(event) {
    event.preventDefault();
    const body = {};
    if (host.trim() !== device.host) body.host = host.trim();
    if (token) body.token = token;
    update.mutate(body, {
      onSuccess: () => {
        notifications.show({ color: 'teal', message: t('adminDevices.connection.saved') });
        onClose();
      },
    });
  }

  return (
    <Modal
      opened
      onClose={onClose}
      title={t('adminDevices.connection.title')}
      closeButtonProps={{ 'aria-label': t('common.close') }}
    >
      <form onSubmit={submit}>
        <Stack>
          <TextInput
            label={t('adminDevices.add.host')}
            value={host}
            onChange={(e) => setHost(e.currentTarget.value)}
            required
            data-autofocus
          />
          <PasswordInput
            label={t('adminDevices.connection.token')}
            description={t('adminDevices.connection.tokenHelp')}
            value={token}
            onChange={(e) => setToken(e.currentTarget.value)}
            autoComplete="off"
          />
          <DeviceErrorAlert
            error={update.error}
            messages={{ device_token_invalid: t('adminDevices.add.tokenInvalid') }}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={update.isPending} disabled={!host.trim()}>
              {t('common.save')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

function Actions({ device }) {
  const { t } = useTranslation();
  const restart = useRestart(device.id);
  const rotate = useRotateToken(device.id);
  const [open, setOpen] = useState(null);
  const close = () => setOpen(null);
  return (
    <>
      <Section title={t('adminDevices.board')}>
        <Text size="sm" c="dimmed">
          {t('adminDevices.restart.help')}
        </Text>
        <Group>
          <Button variant="default" onClick={() => setOpen('restart')}>
            {t('adminDevices.restart.action')}
          </Button>
        </Group>
      </Section>
      <Section title={t('adminDevices.token.title')}>
        <Text size="sm" c="dimmed">
          {t('adminDevices.token.help')}
        </Text>
        <Group gap="xs">
          <Button variant="default" onClick={() => setOpen('reveal')}>
            {t('adminDevices.token.show')}
          </Button>
          <Button variant="default" onClick={() => setOpen('rotate')}>
            {t('adminDevices.token.rotate')}
          </Button>
          <Button variant="default" onClick={() => setOpen('connection')}>
            {t('adminDevices.connection.title')}
          </Button>
        </Group>
      </Section>
      {open === 'restart' && (
        <Confirm
          title={t('adminDevices.restart.title', { name: device.name })}
          text={t('adminDevices.restart.text')}
          action={t('adminDevices.restart.action')}
          mutation={restart}
          onDone={() =>
            notifications.show({ color: 'teal', message: t('adminDevices.restart.done') })
          }
          onClose={close}
        />
      )}
      {open === 'rotate' && (
        <Confirm
          title={t('adminDevices.token.rotateTitle', { name: device.name })}
          text={t('adminDevices.token.rotateText')}
          action={t('adminDevices.token.rotate')}
          mutation={rotate}
          onDone={() =>
            notifications.show({ color: 'teal', message: t('adminDevices.token.rotated') })
          }
          onClose={close}
        />
      )}
      {open === 'reveal' && <RevealDialog device={device} onClose={close} />}
      {open === 'connection' && <ConnectionDialog device={device} onClose={close} />}
    </>
  );
}

export function DeviceSettingsPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const device = useDevice(id);
  const settings = useDeviceSettings(id);

  if (device.error) {
    return (
      <Stack>
        <Title order={1}>{t('device.notFound')}</Title>
        <Anchor component={Link} to="/admin/devices">
          {t('adminDevices.back')}
        </Anchor>
      </Stack>
    );
  }
  if (!device.data) return <Loader aria-label={t('common.loading')} />;

  return (
    <Stack>
      <Title order={1}>{t('adminDevices.settingsTitle', { name: device.data.name })}</Title>
      <Group gap="md">
        <Anchor component={Link} to="/admin/devices">
          {t('adminDevices.back')}
        </Anchor>
        <Anchor component={Link} to={`/devices/${id}`}>
          {t('adminDevices.open')}
        </Anchor>
      </Group>
      <Section title={t('adminDevices.stored')}>
        {settings.isPending && <Loader aria-label={t('common.loading')} />}
        {settings.error && <DeviceErrorAlert error={settings.error} />}
        {settings.data && <SettingsForm device={device.data} settings={settings.data} />}
      </Section>
      <Actions device={device.data} />
    </Stack>
  );
}
