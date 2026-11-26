import {
  Alert,
  Button,
  Group,
  Modal,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { LANGUAGE_NAMES, LANGUAGES } from '../../i18n';

const ERRORS = [
  'email_taken',
  'last_admin',
  'cannot_delete_self',
  'password_required',
  'weak_password',
  'user_not_found',
  'validation_error',
  'forbidden',
];

export function ErrorAlert({ error }) {
  const { t } = useTranslation();
  const ref = useRef(null);
  // The button that failed was disabled while loading and lost focus: move it to the explanation.
  useEffect(() => {
    if (error) ref.current?.focus();
  }, [error]);
  if (!error) return null;
  const code = ERRORS.includes(error.code) ? error.code : 'generic';
  return (
    <Alert color="red" role="alert" ref={ref} tabIndex={-1}>
      {t(`users.errors.${code}`)}
    </Alert>
  );
}

function roleOptions(t) {
  return ['none', 'user', 'admin'].map((value) => ({ value, label: t(`roles.${value}`) }));
}

// Create (no `user`) or edit (`user`) an account.
export function UserFormDialog({ opened, user, mutation, onClose }) {
  const { t } = useTranslation();
  const editing = Boolean(user);
  const form = useForm({
    initialValues: {
      email: user?.email ?? '',
      first_name: user?.first_name ?? '',
      last_name: user?.last_name ?? '',
      role: user?.role ?? 'user',
      auth_method: user?.auth_method ?? 'otp',
      password: '',
      language: user?.language ?? 'en',
      is_active: user?.is_active ?? true,
    },
    validate: {
      email: (value) =>
        editing || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
          ? null
          : t('login.errors.invalid_email'),
      password: (value, values) =>
        !editing && values.auth_method === 'password' && !value ? t('welcome.required') : null,
    },
  });

  const submit = form.onSubmit((values) => {
    const body = editing
      ? {
          id: user.id,
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          role: values.role,
          language: values.language,
          is_active: values.is_active,
          ...(values.auth_method !== user.auth_method ? { auth_method: values.auth_method } : {}),
        }
      : {
          email: values.email.trim(),
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          role: values.role,
          auth_method: values.auth_method,
          language: values.language,
          ...(values.auth_method === 'password' ? { password: values.password } : {}),
        };
    mutation.mutate(body, { onSuccess: onClose });
  });

  return (
    <Modal
      closeButtonProps={{ 'aria-label': t('common.close') }}
      opened={opened}
      onClose={onClose}
      title={editing ? t('users.edit.title') : t('users.create.title')}
    >
      <form onSubmit={submit} noValidate>
        <Stack>
          {editing ? (
            <Text c="dimmed">{user.email}</Text>
          ) : (
            <TextInput
              label={t('login.email')}
              type="email"
              autoComplete="off"
              required
              {...form.getInputProps('email')}
            />
          )}
          <Group grow>
            <TextInput label={t('welcome.firstName')} {...form.getInputProps('first_name')} />
            <TextInput label={t('welcome.lastName')} {...form.getInputProps('last_name')} />
          </Group>
          <Select
            label={t('users.role')}
            data={roleOptions(t)}
            allowDeselect={false}
            {...form.getInputProps('role')}
          />
          <Select
            label={t('users.method.label')}
            data={[
              { value: 'otp', label: t('users.method.otp') },
              { value: 'password', label: t('users.method.password') },
            ]}
            allowDeselect={false}
            {...form.getInputProps('auth_method')}
          />
          {!editing && form.values.auth_method === 'password' && (
            <PasswordInput
              label={t('profile.password.new')}
              description={t('profile.password.rules')}
              autoComplete="new-password"
              required
              {...form.getInputProps('password')}
            />
          )}
          <Select
            label={t('language.label')}
            data={LANGUAGES.map((value) => ({ value, label: LANGUAGE_NAMES[value] }))}
            allowDeselect={false}
            {...form.getInputProps('language')}
          />
          {editing && (
            <Switch
              label={t('users.active')}
              {...form.getInputProps('is_active', { type: 'checkbox' })}
            />
          )}
          <ErrorAlert error={mutation.error} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              {editing ? t('common.save') : t('users.create.submit')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

export function SetPasswordDialog({ opened, user, mutation, onClose }) {
  const { t } = useTranslation();
  const form = useForm({
    initialValues: { password: '' },
    validate: { password: (value) => (value ? null : t('welcome.required')) },
  });

  const submit = form.onSubmit(({ password }) =>
    mutation.mutate({ id: user.id, password }, { onSuccess: onClose }),
  );

  return (
    <Modal
      closeButtonProps={{ 'aria-label': t('common.close') }}
      opened={opened}
      onClose={onClose}
      title={t('users.password.title')}
    >
      <form onSubmit={submit} noValidate>
        <Stack>
          <Text size="sm">{t('users.password.help', { email: user?.email })}</Text>
          <PasswordInput
            label={t('profile.password.new')}
            description={t('profile.password.rules')}
            autoComplete="new-password"
            required
            {...form.getInputProps('password')}
          />
          <ErrorAlert error={mutation.error} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              {t('users.password.submit')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

export function DeleteDialog({ opened, user, mutation, onClose }) {
  const { t } = useTranslation();
  return (
    <Modal
      closeButtonProps={{ 'aria-label': t('common.close') }}
      opened={opened}
      onClose={onClose}
      title={t('users.delete.title')}
    >
      <Stack>
        <Text>{t('users.delete.confirm', { email: user?.email })}</Text>
        <ErrorAlert error={mutation.error} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            color="red"
            loading={mutation.isPending}
            onClick={() => mutation.mutate(user.id, { onSuccess: onClose })}
          >
            {t('users.delete.submit')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
