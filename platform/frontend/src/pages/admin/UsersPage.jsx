import {
  ActionIcon,
  Badge,
  Button,
  Group,
  Menu,
  Pagination,
  Popover,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { Ellipsis, KeyRound, ListFilter, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../../auth/useAuth';
import { DeleteDialog, ErrorAlert, SetPasswordDialog, UserFormDialog } from './UserDialogs';
import {
  PAGE_SIZE,
  useCreateUser,
  useDeleteUser,
  useSetPassword,
  useUpdateUser,
  useUsers,
} from './usersApi';
import classes from './UsersPage.module.css';

const fullName = (user) => [user.first_name, user.last_name].filter(Boolean).join(' ');

// Role and status filters: used now and then, so they open from one button that counts the active ones.
function Filters({ role, active, onRole, onActive }) {
  const { t } = useTranslation();
  const count = [role, active].filter(Boolean).length;
  // Inside the popover: a dropdown in a portal would count as a click outside and close it.
  const inline = { withinPortal: false };

  return (
    <Popover position="bottom-start" shadow="md" trapFocus>
      <Popover.Target>
        <Button variant="default" leftSection={<ListFilter size={16} aria-hidden />}>
          {count ? t('users.filters.active', { count }) : t('users.filters.open')}
        </Button>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack gap="sm" w={220}>
          <Select
            label={t('users.role')}
            placeholder={t('users.all')}
            data={['none', 'user', 'admin'].map((value) => ({ value, label: t(`roles.${value}`) }))}
            value={role}
            onChange={onRole}
            clearable
            comboboxProps={inline}
          />
          <Select
            label={t('users.status')}
            placeholder={t('users.all')}
            data={[
              { value: 'true', label: t('users.activeState') },
              { value: 'false', label: t('users.inactiveState') },
            ]}
            value={active}
            onChange={onActive}
            clearable
            comboboxProps={inline}
          />
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

export function UsersPage() {
  const { t } = useTranslation();
  const { user: me } = useAuth();
  const [search, setSearch] = useState('');
  const [q] = useDebouncedValue(search.trim(), 300);
  const [role, setRole] = useState(null);
  const [active, setActive] = useState(null);
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState(null); // { kind: 'create'|'edit'|'password'|'delete', user }

  const users = useUsers({ q, role, active, page });
  const create = useCreateUser();
  const update = useUpdateUser();
  const setPassword = useSetPassword();
  const remove = useDeleteUser();
  const grant = useUpdateUser();

  // Dialogs mount on open, so Mantine cannot return focus itself: put it back on the control that
  // opened the dialog (the row's actions menu, or "New user"), or on "New user" when that row is gone
  // (WCAG 2.4.3).
  const trigger = useRef(null);
  const createButton = useRef(null);
  const rowMenu = useRef(null);
  const open = (kind, user) => {
    for (const mutation of [create, update, setPassword, remove]) mutation.reset();
    trigger.current = kind === 'create' ? createButton.current : rowMenu.current;
    setDialog({ kind, user });
  };
  const close = () => {
    const target = trigger.current;
    setDialog(null);
    setTimeout(() => (target?.isConnected ? target : createButton.current)?.focus());
  };
  const done = (message) => () => {
    notifications.show({ color: 'teal', message });
    close();
  };

  const filters = (change) => (value) => {
    change(value);
    setPage(1);
  };

  const data = users.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Title order={1}>{t('users.title')}</Title>
        <Button
          ref={createButton}
          leftSection={<Plus size={16} aria-hidden />}
          onClick={() => open('create')}
        >
          {t('users.create.open')}
        </Button>
      </Group>

      <Group gap="xs" wrap="nowrap">
        <TextInput
          aria-label={t('users.search')}
          placeholder={t('users.search')}
          leftSection={<Search size={16} aria-hidden />}
          value={search}
          onChange={(event) => {
            setSearch(event.currentTarget.value);
            setPage(1);
          }}
          className={classes.search}
        />
        <Filters
          role={role}
          active={active}
          onRole={filters(setRole)}
          onActive={filters(setActive)}
        />
      </Group>

      <ErrorAlert error={grant.error} />

      {data && data.items.length === 0 ? (
        <Text c="dimmed">{t('users.empty')}</Text>
      ) : (
        <Table verticalSpacing="sm" highlightOnHover className={classes.table}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('users.name')}</Table.Th>
              <Table.Th className={classes.role}>{t('users.role')}</Table.Th>
              <Table.Th className={classes.actions}>
                <VisuallyHidden>{t('users.actions')}</VisuallyHidden>
              </Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data?.items.map((user) => (
              <Table.Tr key={user.id}>
                <Table.Td className={classes.who}>
                  <Text fw={500}>{fullName(user) || '—'}</Text>
                  <Text size="sm" c="dimmed">
                    {user.email}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs" className={classes.badges}>
                    {user.role === 'none' ? (
                      <>
                        <Badge variant="light" color="red">
                          {t('roles.none')}
                        </Badge>
                        <Button
                          size="compact-sm"
                          variant="light"
                          loading={grant.isPending && grant.variables?.id === user.id}
                          onClick={() =>
                            grant.mutate(
                              { id: user.id, role: 'user' },
                              { onSuccess: done(t('users.granted', { email: user.email })) },
                            )
                          }
                        >
                          {t('users.grant')}
                        </Button>
                      </>
                    ) : (
                      <Badge variant="light" color={user.role === 'admin' ? 'slate' : 'gray'}>
                        {t(`roles.${user.role}`)}
                      </Badge>
                    )}
                    {!user.is_active && (
                      <Badge variant="outline" color="gray">
                        {t('users.inactiveState')}
                      </Badge>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td className={classes.actions}>
                  <Menu position="bottom-end">
                    <Menu.Target>
                      <ActionIcon
                        variant="subtle"
                        size="lg"
                        aria-label={t('users.actionsFor', { email: user.email })}
                        onClick={(event) => (rowMenu.current = event.currentTarget)}
                      >
                        <Ellipsis size={18} aria-hidden />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item
                        leftSection={<Pencil size={16} aria-hidden />}
                        onClick={() => open('edit', user)}
                      >
                        {t('users.edit.title')}
                      </Menu.Item>
                      {/* Your own account is managed from the profile; setting your password here
                          would close all your sessions. */}
                      {user.id !== me.id && (
                        <>
                          <Menu.Item
                            leftSection={<KeyRound size={16} aria-hidden />}
                            onClick={() => open('password', user)}
                          >
                            {t('users.password.title')}
                          </Menu.Item>
                          <Menu.Divider />
                          <Menu.Item
                            color="red"
                            leftSection={<Trash2 size={16} aria-hidden />}
                            onClick={() => open('delete', user)}
                          >
                            {t('users.delete.title')}
                          </Menu.Item>
                        </>
                      )}
                    </Menu.Dropdown>
                  </Menu>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {pages > 1 && (
        <Pagination
          total={pages}
          value={page}
          onChange={setPage}
          getControlProps={(control) => ({ 'aria-label': t(`users.pagination.${control}`) })}
          withEdges={false}
        />
      )}

      {dialog?.kind === 'create' && (
        <UserFormDialog
          opened
          mutation={{
            ...create,
            mutate: (body) => create.mutate(body, { onSuccess: done(t('users.create.done')) }),
          }}
          onClose={close}
        />
      )}
      {dialog?.kind === 'edit' && (
        <UserFormDialog
          opened
          user={dialog.user}
          mutation={{
            ...update,
            mutate: (body, options) =>
              update.mutate(body, { ...options, onSuccess: done(t('users.edit.saved')) }),
          }}
          onClose={close}
        />
      )}
      {dialog?.kind === 'password' && (
        <SetPasswordDialog
          opened
          user={dialog.user}
          mutation={{
            ...setPassword,
            mutate: (body) =>
              setPassword.mutate(body, { onSuccess: done(t('users.password.saved')) }),
          }}
          onClose={close}
        />
      )}
      {dialog?.kind === 'delete' && (
        <DeleteDialog
          opened
          user={dialog.user}
          mutation={{
            ...remove,
            mutate: (id) =>
              remove.mutate(id, {
                onSuccess: done(t('users.delete.done', { email: dialog.user.email })),
              }),
          }}
          onClose={close}
        />
      )}
    </Stack>
  );
}
