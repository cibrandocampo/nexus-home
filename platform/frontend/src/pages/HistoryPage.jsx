import {
  Anchor,
  Group,
  Loader,
  MultiSelect,
  Pagination,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link, useParams, useSearchParams } from 'react-router';

import { useAuth } from '../auth/useAuth';
import { dayOf, formatDay, formatTime, startOfDay } from '../devices/days';
import { useDevice, useDevices } from '../devices/devicesApi';
import { EVENT_GROUPS, eventCause, eventTitle } from '../devices/eventLabels';
import { HISTORY_SIZE, useEvents } from '../devices/historyApi';
import classes from './HistoryPage.module.css';

const DAY = /^\d{4}-\d{2}-\d{2}$/;

// Filters live in the URL, so a filtered history can be bookmarked and the back button works.
function useFilters() {
  const [params, setParams] = useSearchParams();
  const filters = {
    device: params.get('device') ?? '',
    events: params.getAll('event'),
    from: DAY.test(params.get('from') ?? '') ? params.get('from') : '',
    to: DAY.test(params.get('to') ?? '') ? params.get('to') : '',
    page: Math.max(1, Number(params.get('page')) || 1),
  };
  function change(patch) {
    const next = { ...filters, page: 1, ...patch };
    const out = new URLSearchParams();
    if (next.device) out.set('device', next.device);
    for (const event of next.events) out.append('event', event);
    if (next.from) out.set('from', next.from);
    if (next.to) out.set('to', next.to);
    if (next.page > 1) out.set('page', String(next.page));
    setParams(out);
  }
  return [filters, change];
}

function Filters({ filters, change, global }) {
  const { t } = useTranslation();
  const devices = useDevices();
  const eventOptions = Object.entries(EVENT_GROUPS).map(([group, events]) => ({
    group: t(`history.groups.${group}`),
    items: events.map((value) => ({ value, label: t(`history.filter.${value}`) })),
  }));
  return (
    <Group align="flex-end" gap="sm" wrap="wrap">
      {global && (
        <Select
          label={t('history.device')}
          placeholder={t('history.allDevices')}
          data={(devices.data?.items ?? []).map((d) => ({ value: String(d.id), label: d.name }))}
          value={filters.device || null}
          onChange={(value) => change({ device: value ?? '' })}
          clearable
          w={200}
        />
      )}
      <MultiSelect
        label={t('history.events.label')}
        placeholder={filters.events.length ? undefined : t('history.allEvents')}
        data={eventOptions}
        value={filters.events}
        onChange={(events) => change({ events })}
        clearable
        w={260}
      />
      <TextInput
        type="date"
        label={t('history.from')}
        value={filters.from}
        max={filters.to || undefined}
        onChange={(e) => change({ from: e.currentTarget.value })}
        w={160}
      />
      <TextInput
        type="date"
        label={t('history.to')}
        value={filters.to}
        min={filters.from || undefined}
        onChange={(e) => change({ to: e.currentTarget.value })}
        w={160}
      />
    </Group>
  );
}

function groupByDay(items, timeZone) {
  const days = [];
  for (const item of items) {
    const day = dayOf(item.at, timeZone);
    if (days.at(-1)?.day !== day) days.push({ day, items: [] });
    days.at(-1).items.push(item);
  }
  return days;
}

function Entry({ item, global }) {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const cause = eventCause(t, item);
  return (
    <li className={classes.entry}>
      <time dateTime={item.at} className={classes.time}>
        {formatTime(item.at, i18n.language, user.timezone)}
      </time>
      <div>
        <Text fw={600}>{eventTitle(t, item, i18n.language)}</Text>
        <Text size="sm" c="dimmed">
          {[
            global ? item.device.name : null,
            cause || null,
            item.user ? t('history.by', { name: item.user.name ?? t('history.someone') }) : null,
          ]
            .filter(Boolean)
            .join(', ')}
        </Text>
      </div>
    </li>
  );
}

export function HistoryPage() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const { id } = useParams();
  const device = useDevice(id ?? 0, { enabled: Boolean(id) });
  const [filters, change] = useFilters();
  const events = useEvents({
    deviceId: id,
    device: id ? '' : filters.device,
    events: filters.events,
    from: filters.from ? startOfDay(filters.from, user.timezone) : '',
    to: filters.to ? startOfDay(filters.to, user.timezone, 1) : '', // the whole "to" day
    page: filters.page,
  });
  const filtered = Boolean(filters.device || filters.events.length || filters.from || filters.to);
  const pastTheEnd = filters.page > 1 && events.data?.items.length === 0 && events.data.total > 0;
  const pages = events.data ? Math.ceil(events.data.total / HISTORY_SIZE) : 0;

  if (id && device.error) {
    return (
      <Stack>
        <Title order={1}>{t('device.notFound')}</Title>
        <Anchor component={Link} to="/history">
          {t('history.all')}
        </Anchor>
      </Stack>
    );
  }

  return (
    <Stack>
      <Title order={1}>
        {id ? t('history.deviceTitle', { name: device.data?.name ?? '' }) : t('history.title')}
      </Title>
      {id && (
        <Anchor component={Link} to={`/devices/${id}`}>
          {t('history.back', { name: device.data?.name ?? '' })}
        </Anchor>
      )}
      <Filters filters={filters} change={change} global={!id} />
      {events.isPending && <Loader aria-label={t('common.loading')} />}
      {events.data && events.data.items.length === 0 && !pastTheEnd && (
        <Text>{t(filtered ? 'history.noMatch' : 'history.empty')}</Text>
      )}
      {pastTheEnd && (
        <Text>
          {t('history.pastTheEnd')}{' '}
          <Anchor component="button" onClick={() => change({ ...filters, page: 1 })}>
            {t('history.firstPage')}
          </Anchor>
        </Text>
      )}
      {events.data &&
        groupByDay(events.data.items, user.timezone).map(({ day, items }) => (
          <section key={day} aria-labelledby={`day-${day}`}>
            <Title order={2} size="h4" id={`day-${day}`} mb="xs">
              {formatDay(day, i18n.language)}
            </Title>
            <ol className={classes.list}>
              {items.map((item) => (
                <Entry key={item.id} item={item} global={!id} />
              ))}
            </ol>
          </section>
        ))}
      {pages > 1 && (
        <Pagination
          total={pages}
          value={filters.page}
          onChange={(page) => change({ ...filters, page })}
          getControlProps={(control) => ({ 'aria-label': t(`history.pages.${control}`) })}
          getItemProps={(page) => ({ 'aria-label': t('history.pages.page', { page }) })}
        />
      )}
    </Stack>
  );
}
