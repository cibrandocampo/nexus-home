import '@testing-library/jest-dom/vitest';

import { notifications } from '@mantine/notifications';
import { cleanup, configure } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest';

import { setAccessToken } from '../api/client';
import i18n from '../i18n';
import { server } from './server';

// The first render of a file (Mantine, coverage instrumentation, a loaded container) can take more
// than the default 1 s that findBy/waitFor wait.
configure({ asyncUtilTimeout: 3000 });

// jsdom lacks APIs Mantine uses.
window.matchMedia ??= (query) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
  dispatchEvent: () => false,
});
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
Element.prototype.scrollIntoView ??= () => {};
// Web Animations (BottomNav's sliding pill).
Element.prototype.getAnimations ??= () => [];
Element.prototype.animate ??= () => ({ cancel() {}, finish() {} });

beforeAll(async () => {
  server.listen({ onUnhandledRequest: 'error' });
  // Lazy pages (App.jsx): import them once up front so a test's first render does not wait for the
  // module to be transformed.
  await Promise.all([import('../pages/ProfilePage'), import('../pages/admin/UsersPage')]);
});
afterEach(async () => {
  cleanup();
  // Notifications live in a module-level store that outlives each render.
  notifications.clean();
  server.resetHandlers();
  setAccessToken(null);
  localStorage.clear();
  await i18n.changeLanguage('en');
});
afterAll(() => server.close());
