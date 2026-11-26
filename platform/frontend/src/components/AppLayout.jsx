import { ActionIcon, Anchor, AppShell, Container, Group, Tooltip } from '@mantine/core';
import { LogOut } from 'lucide-react';
import { Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Outlet } from 'react-router';

import { useAuth } from '../auth/useAuth';
import classes from './AppLayout.module.css';
import { BrandMark } from './BrandMark';
import { BottomNav } from './BottomNav';

// Language and colour scheme live in the profile once signed in; the bar's right side holds the
// account action (and whatever actions each app adds).
export function AppLayout() {
  const { t } = useTranslation();
  const { logout } = useAuth();

  return (
    <AppShell header={{ height: 56 }} padding={0}>
      <AppShell.Header className={classes.header}>
        <Container size={1080} h="100%">
          <Group h="100%" justify="space-between" wrap="nowrap">
            <Anchor component={Link} to="/" underline="never" aria-label={t('app.name')}>
              <BrandMark />
            </Anchor>
            <Group gap="xs" wrap="nowrap">
              <Tooltip label={t('user.logout')}>
                <ActionIcon
                  variant="default"
                  size="lg"
                  aria-label={t('user.logout')}
                  onClick={logout}
                >
                  <LogOut size={18} aria-hidden />
                </ActionIcon>
              </Tooltip>
            </Group>
          </Group>
        </Container>
      </AppShell.Header>
      <AppShell.Main>
        <Container size={1080} pt="xl" className={classes.content}>
          {/* Lazy pages: the shell and the bar stay while a page's chunk loads. */}
          <Suspense fallback={null}>
            <Outlet />
          </Suspense>
        </Container>
      </AppShell.Main>
      <BottomNav />
    </AppShell>
  );
}
