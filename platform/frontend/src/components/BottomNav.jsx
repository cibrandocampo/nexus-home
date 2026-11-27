import { History, House, Router, UserRound, Users } from 'lucide-react';
import { useLayoutEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, matchPath, useLocation } from 'react-router';

import { useAuth } from '../auth/useAuth';
import { useKeyboardOpen } from '../hooks/useKeyboardOpen';
import classes from './BottomNav.module.css';

// Tabs: `match` are the routes that keep a tab current (its own sub-pages included).
const TABS = [
  { to: '/', icon: House, label: 'nav.home', match: ['/', '/devices/:id'], min: 'user' },
  {
    to: '/history',
    icon: History,
    label: 'nav.history',
    match: ['/history', '/devices/:id/history'],
    min: 'user',
  },
  { to: '/profile', icon: UserRound, label: 'nav.profile', match: ['/profile'], min: 'none' },
  {
    to: '/admin/devices',
    icon: Router,
    label: 'nav.devices',
    match: ['/admin/devices/*'],
    min: 'admin',
  },
  { to: '/admin/users', icon: Users, label: 'nav.users', match: ['/admin/users/*'], min: 'admin' },
];
const LEVEL = { none: 0, user: 1, admin: 2 };
// Same duration and easing as the tabs' own transitions (BottomNav.module.css).
const SLIDE = { duration: 200, easing: 'ease', pseudoElement: '::before' };

function boxIn(list, element) {
  const outer = list.getBoundingClientRect();
  const inner = element.getBoundingClientRect();
  return { left: `${inner.left - outer.left}px`, width: `${inner.width}px`, right: 'auto' };
}

// Slides the pill from the previous tab to the current one. The tabs move while their labels fold
// and unfold, so the pill's end is measured with their transitions jumped to the end (then put
// back): both then run the same 200 ms ease and stay together.
function useSlidingPill(listRef, current) {
  const previous = useRef(current);

  useLayoutEffect(() => {
    const from = previous.current;
    previous.current = current;
    const list = listRef.current;
    if (!list || from === current || from < 0 || current < 0) return;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const links = list.querySelectorAll('a');
    const start = boxIn(list, links[from]);
    const transitions = list.getAnimations({ subtree: true });
    transitions.forEach((a) => (a.currentTime = a.effect.getComputedTiming().endTime));
    const end = boxIn(list, links[current]);
    transitions.forEach((a) => (a.currentTime = 0));
    list.animate([start, end], SLIDE);
  }, [listRef, current]);
}

// Bottom navigation, always visible (nudge's bar) in the "expanding label" style: the current tab is a
// pill with its icon and label, the others show their icon only. Labels stay in the DOM, so every tab
// keeps its accessible name.
export function BottomNav() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { pathname } = useLocation();
  const keyboardOpen = useKeyboardOpen();
  const listRef = useRef(null);

  const tabs = TABS.filter((tab) => LEVEL[user.role] >= LEVEL[tab.min]);
  const current = tabs.findIndex(({ match }) => match.some((path) => matchPath(path, pathname)));
  useSlidingPill(listRef, current);

  // A single tab is not navigation (accounts waiting for access only have their profile).
  if (tabs.length < 2 || keyboardOpen) return null;

  return (
    <nav className={classes.nav} aria-label={t('nav.label')} data-bottom-nav>
      <ul className={classes.list} ref={listRef}>
        {tabs.map(({ to, icon: Icon, label }, index) => (
          <li key={to}>
            <Link
              to={to}
              className={classes.tab}
              data-current={index === current || undefined}
              aria-current={index === current ? 'page' : undefined}
            >
              <Icon size={22} aria-hidden />
              <span className={classes.label}>{t(label)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
