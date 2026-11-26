import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AppRoutes } from '../App';
import { renderWithProviders } from '../test/render';
import { makeUser, server, withSession } from '../test/server';

const nav = () => screen.findByRole('navigation', { name: 'Main' });

describe('BottomNav', () => {
  it('shows Home and Profile to a user, with Home current', async () => {
    server.use(withSession());
    renderWithProviders(<AppRoutes />);

    await nav();
    const home = screen.getByRole('link', { name: 'Home' });
    expect(home).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Profile' })).not.toHaveAttribute('aria-current');
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument();
  });

  it('adds Users for an administrator and marks the current tab after navigating', async () => {
    server.use(withSession(makeUser({ role: 'admin' })));
    const { router } = renderWithProviders(<AppRoutes />);

    await nav();
    await userEvent.click(screen.getByRole('link', { name: 'Profile' }));

    await waitFor(() => expect(router.location.pathname).toBe('/profile'));
    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'Profile' })).toHaveAttribute('aria-current', 'page'),
    );
    expect(screen.getByRole('link', { name: 'Users' })).toBeInTheDocument();
  });

  it('is not shown to an account waiting for access (one tab is not navigation)', async () => {
    server.use(withSession(makeUser({ role: 'none' })));
    renderWithProviders(<AppRoutes />);

    await screen.findByRole('heading', { name: 'Waiting for access' });
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument();
  });

  it('hides while the on-screen keyboard is open', async () => {
    const listeners = {};
    const viewport = {
      height: window.innerHeight,
      addEventListener: (type, fn) => (listeners[type] = fn),
      removeEventListener: () => {},
    };
    Object.defineProperty(window, 'visualViewport', { value: viewport, configurable: true });
    server.use(withSession());
    renderWithProviders(<AppRoutes />);
    await nav();

    viewport.height = window.innerHeight - 300;
    act(() => listeners.resize());

    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument();
    viewport.height = window.innerHeight;
    act(() => listeners.resize());
    expect(await nav()).toBeInTheDocument();
    delete window.visualViewport;
  });

  it('stays visible while the page is pinch-zoomed', async () => {
    const viewport = {
      height: window.innerHeight / 2,
      scale: 2,
      addEventListener: () => {},
      removeEventListener: () => {},
    };
    Object.defineProperty(window, 'visualViewport', { value: viewport, configurable: true });
    server.use(withSession());
    renderWithProviders(<AppRoutes />);

    expect(await nav()).toBeInTheDocument();
    delete window.visualViewport;
  });

  it('leaves the content bottom reserve to its class (no inline padding overrides it)', async () => {
    server.use(withSession());
    renderWithProviders(<AppRoutes />);

    const content = (await screen.findByRole('heading', { name: 'Welcome' })).closest('main > *');
    expect(content.className).toMatch(/content/);
    expect(content.style.paddingBottom).toBe('');
    expect(content.style.paddingBlock).toBe('');
  });

  it('slides the pill to the new tab', async () => {
    const animate = vi.spyOn(Element.prototype, 'animate');
    server.use(withSession());
    renderWithProviders(<AppRoutes />);
    const list = (await nav()).querySelector('ul');

    await userEvent.click(screen.getByRole('link', { name: 'Profile' }));

    await waitFor(() => expect(animate).toHaveBeenCalledTimes(1));
    expect(animate.mock.contexts[0]).toBe(list);
    expect(animate.mock.calls[0][1]).toMatchObject({ duration: 200, pseudoElement: '::before' });
    animate.mockRestore();
  });

  it('does not slide the pill when reduced motion is preferred', async () => {
    const animate = vi.spyOn(Element.prototype, 'animate');
    const matchMedia = vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
      matches: query.includes('reduce'),
      media: query,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
    }));
    server.use(withSession());
    const { router } = renderWithProviders(<AppRoutes />);
    await nav();

    await userEvent.click(screen.getByRole('link', { name: 'Profile' }));

    await waitFor(() => expect(router.location.pathname).toBe('/profile'));
    expect(animate).not.toHaveBeenCalled();
    animate.mockRestore();
    matchMedia.mockRestore();
  });

  // Re-applying the saved colour scheme on every render made Mantine switch every CSS transition
  // off for a moment on each navigation, which cut the pill and label animations.
  it('keeps CSS transitions on while navigating', async () => {
    const appendChild = vi.spyOn(document.head, 'appendChild');
    server.use(withSession());
    const { router } = renderWithProviders(<AppRoutes />);
    await nav();
    appendChild.mockClear();

    await userEvent.click(screen.getByRole('link', { name: 'Profile' }));

    await waitFor(() => expect(router.location.pathname).toBe('/profile'));
    const disabling = appendChild.mock.calls.filter(([node]) =>
      node.hasAttribute?.('data-mantine-disable-transition'),
    );
    expect(disabling).toEqual([]);
    appendChild.mockRestore();
  });
});
