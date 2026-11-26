import {
  ActionIcon,
  Alert,
  Anchor,
  Avatar,
  Badge,
  Button,
  Group,
  Modal,
  PasswordInput,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { KeyRound, Pencil, UserRound } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { notifyError } from '../api/queryClient';
import { useAuth } from '../auth/useAuth';
import { LANGUAGE_NAMES, LANGUAGES } from '../i18n';
import { TimeZonePicker } from '../components/TimeZonePicker';
import { browserTimeZone } from '../timeZones';
import classes from './ProfilePage.module.css';

const PASSWORD_ERRORS = ['invalid_credentials', 'weak_password', 'rate_limited'];

// Name and password change rarely: each opens in a dialog over the page. The dialog's content mounts on
// open (fresh fields each time) and Mantine gives the focus back to the button that opened it.
function ProfileDialog({ opened, onClose, title, children }) {
  const { t } = useTranslation();
  return (
    <Modal
      closeButtonProps={{ 'aria-label': t('common.close') }}
      opened={opened}
      onClose={onClose}
      title={title}
    >
      {children}
    </Modal>
  );
}

function NameForm({ onClose }) {
  const { t } = useTranslation();
  const { user, updateProfile } = useAuth();
  const form = useForm({
    initialValues: { first_name: user.first_name, last_name: user.last_name },
    validate: {
      first_name: (value) => (value.trim() ? null : t('welcome.required')),
      last_name: (value) => (value.trim() ? null : t('welcome.required')),
    },
  });

  const save = form.onSubmit(async (values) => {
    try {
      await updateProfile({
        first_name: values.first_name.trim(),
        last_name: values.last_name.trim(),
      });
      notifications.show({ color: 'teal', message: t('profile.saved') });
      onClose();
    } catch (error) {
      notifyError(error);
    }
  });

  return (
    <form onSubmit={save} noValidate>
      <Stack>
        <TextInput
          label={t('welcome.firstName')}
          autoComplete="given-name"
          data-autofocus
          required
          {...form.getInputProps('first_name')}
        />
        <TextInput
          label={t('welcome.lastName')}
          autoComplete="family-name"
          required
          {...form.getInputProps('last_name')}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" loading={form.submitting}>
            {t('profile.saveName')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

function PasswordForm({ onClose }) {
  const { t } = useTranslation();
  const { changePassword } = useAuth();
  const [error, setError] = useState(null);
  const form = useForm({
    initialValues: { current_password: '', new_password: '', confirm: '' },
    validate: {
      current_password: (value) => (value ? null : t('welcome.required')),
      new_password: (value) => (value ? null : t('welcome.required')),
      confirm: (value, values) =>
        value === values.new_password ? null : t('profile.password.mismatch'),
    },
  });

  const save = form.onSubmit(async (values) => {
    setError(null);
    try {
      await changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      });
      notifications.show({ color: 'teal', message: t('profile.password.saved') });
      onClose();
    } catch (err) {
      setError(PASSWORD_ERRORS.includes(err.code) ? err.code : 'generic');
    }
  });

  return (
    <form onSubmit={save} noValidate>
      <Stack>
        <PasswordInput
          label={t('profile.password.current')}
          autoComplete="current-password"
          data-autofocus
          required
          {...form.getInputProps('current_password')}
        />
        <PasswordInput
          label={t('profile.password.new')}
          description={t('profile.password.rules')}
          autoComplete="new-password"
          required
          {...form.getInputProps('new_password')}
        />
        <PasswordInput
          label={t('profile.password.confirm')}
          autoComplete="new-password"
          required
          {...form.getInputProps('confirm')}
        />
        {error && (
          <Alert color="red" role="alert">
            {t(`profile.password.errors.${error}`)}
          </Alert>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" loading={form.submitting}>
            {t('profile.password.change')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

// Who is signed in: picture placeholder, name with its pencil, email and account type. Accounts that
// sign in with a password change it from the key on the right; code accounts have nothing to change.
function Identity() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [nameOpen, name] = useDisclosure(false);
  const [passwordOpen, password] = useDisclosure(false);

  return (
    <Group gap="md" wrap="nowrap" align="center">
      <Avatar size={64} radius="100%" color="slate" variant="filled" aria-hidden>
        <UserRound size={32} />
      </Avatar>
      <Stack gap={4} className={classes.identity}>
        <Group gap={4} wrap="nowrap">
          <Title order={2} size="h3" className={classes.name}>
            {`${user.first_name} ${user.last_name}`.trim()}
          </Title>
          <Tooltip label={t('profile.editName')}>
            <ActionIcon variant="subtle" aria-label={t('profile.editName')} onClick={name.open}>
              <Pencil size={16} aria-hidden />
            </ActionIcon>
          </Tooltip>
        </Group>
        <Group gap="xs">
          <Text c="dimmed" className={classes.email}>
            {user.email}
          </Text>
          <Badge variant="light">{t(`roles.${user.role}`)}</Badge>
        </Group>
      </Stack>
      {user.auth_method === 'password' && (
        <Tooltip label={t('profile.password.change')}>
          <ActionIcon
            variant="default"
            size="lg"
            aria-label={t('profile.password.change')}
            onClick={password.open}
          >
            <KeyRound size={18} aria-hidden />
          </ActionIcon>
        </Tooltip>
      )}
      <ProfileDialog opened={nameOpen} onClose={name.close} title={t('profile.editName')}>
        <NameForm onClose={name.close} />
      </ProfileDialog>
      <ProfileDialog
        opened={passwordOpen}
        onClose={password.close}
        title={t('profile.password.change')}
      >
        <PasswordForm onClose={password.close} />
      </ProfileDialog>
    </Group>
  );
}

// One preference: its name over a full-width control. Every control has the same size.
function Preference({ id, label, children }) {
  return (
    <Stack gap={6}>
      <Text id={id} fw={500}>
        {label}
      </Text>
      {children}
    </Stack>
  );
}

function Preferences() {
  const { t } = useTranslation();
  const { user, updateProfile } = useAuth();
  // Saved at once; the session applies the user's language and colour scheme when they change.
  const save = (changes) => updateProfile(changes).catch(notifyError);
  const detected = browserTimeZone();

  return (
    <section className={classes.section}>
      <Title order={2} size="h3">
        {t('profile.preferences')}
      </Title>
      <Preference id="profile-language" label={t('language.label')}>
        <SegmentedControl
          aria-labelledby="profile-language"
          value={user.language}
          onChange={(language) => save({ language })}
          data={LANGUAGES.map((value) => ({ value, label: LANGUAGE_NAMES[value] }))}
          fullWidth
          classNames={{ root: classes.choice, label: classes.choiceLabel }}
          size="sm"
        />
      </Preference>
      <Preference id="profile-theme" label={t('colorScheme.label')}>
        <SegmentedControl
          aria-labelledby="profile-theme"
          value={user.theme}
          onChange={(theme) => save({ theme })}
          data={[
            { value: 'light', label: t('colorScheme.light') },
            { value: 'dark', label: t('colorScheme.dark') },
            { value: 'system', label: t('colorScheme.auto') },
          ]}
          fullWidth
          classNames={{ root: classes.choice, label: classes.choiceLabel }}
          size="sm"
        />
      </Preference>
      <Preference id="profile-timezone" label={t('timezone.label')}>
        <TimeZonePicker
          labelId="profile-timezone"
          value={user.timezone}
          onChange={(timezone) => save({ timezone })}
          className={classes.field}
        />
        {/* A new account starts in UTC: offer the browser's zone instead of guessing silently. */}
        {user.timezone === 'UTC' && detected && detected !== 'UTC' && (
          <Text size="sm" c="dimmed">
            {t('timezone.detected', { zone: detected })}{' '}
            <Anchor component="button" type="button" onClick={() => save({ timezone: detected })}>
              {t('timezone.useDetected')}
            </Anchor>
          </Text>
        )}
      </Preference>
    </section>
  );
}

export function ProfilePage() {
  const { t } = useTranslation();

  return (
    <Stack gap="xl" maw={560}>
      <Title order={1}>{t('profile.title')}</Title>
      <Identity />
      <Preferences />
    </Stack>
  );
}
