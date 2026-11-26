import { Center, Loader } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router';

import { NotFoundPage } from '../pages/NotFoundPage';
import { useAuth } from './useAuth';

const LEVEL = { none: 0, user: 1, admin: 2 };

function Loading() {
  const { t } = useTranslation();
  return (
    <Center h="100vh">
      <Loader aria-label={t('common.loading')} />
    </Center>
  );
}

// Logged-in users only; new users first complete their name.
export function RequireSession() {
  const { status, isNew } = useAuth();
  const location = useLocation();

  if (status === 'loading') return <Loading />;
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location }} />;
  if (isNew && location.pathname !== '/welcome') return <Navigate to="/welcome" replace />;
  return <Outlet />;
}

// Users with at least `min` role. Accounts without permissions wait; others get "not found".
export function RequireRole({ min }) {
  const { user } = useAuth();

  if (user.role === 'none') return <Navigate to="/waiting" replace />;
  if (LEVEL[user.role] < LEVEL[min]) return <NotFoundPage />;
  return <Outlet />;
}

// Login page. Once there is a session (on load or right after logging in) this is the one place
// that leaves it: back to the page that asked for the login, or home. RequireSession then sends
// new accounts to the welcome step.
export function AnonymousOnly() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') return <Loading />;
  if (status === 'authenticated') {
    const from = location.state?.from;
    const target = from ? `${from.pathname}${from.search}${from.hash}` : '/';
    return <Navigate to={target} replace />;
  }
  return <Outlet />;
}
