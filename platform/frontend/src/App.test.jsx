import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import App, { AppRoutes } from './App';
import { renderWithProviders } from './test/render';
import { makeUser, server, withSession } from './test/server';

describe('App', () => {
  it('shows the home page inside the shell to a user with a session', async () => {
    server.use(withSession());
    renderWithProviders(<AppRoutes />);

    expect(await screen.findByRole('heading', { name: 'Home' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'nexusHome' })).toBeInTheDocument();
  });

  it('sends visitors without a session to the login page', async () => {
    renderWithProviders(<AppRoutes />);

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('shows a not-found page with a way home', async () => {
    server.use(withSession());
    renderWithProviders(<AppRoutes />, { route: '/nowhere' });

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('link', { name: 'Go to the home page' }));
    expect(screen.getByRole('heading', { name: 'Home' })).toBeInTheDocument();
  });

  it('switches the colour scheme and saves it in the profile (welcome step)', async () => {
    let saved;
    server.use(
      withSession(makeUser({ first_name: '', last_name: '' })),
      http.patch('/api/auth/me', async ({ request }) => {
        saved = await request.json();
        return HttpResponse.json(makeUser({ first_name: '', last_name: '', theme: saved.theme }));
      }),
    );
    renderWithProviders(<AppRoutes />);

    await userEvent.click(await screen.findByRole('button', { name: 'Colour scheme' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Dark' }));

    expect(document.documentElement).toHaveAttribute('data-mantine-color-scheme', 'dark');
    expect(localStorage.getItem('app-color-scheme')).toBe('dark');
    await vi.waitFor(() => expect(saved).toEqual({ theme: 'dark' }));
  });

  it('marks the active colour scheme in the menu', async () => {
    localStorage.setItem('app-color-scheme', 'dark');
    renderWithProviders(<AppRoutes />);

    await userEvent.click(await screen.findByRole('button', { name: 'Colour scheme' }));

    const items = await screen.findAllByRole('menuitem');
    const current = items.filter((item) => item.getAttribute('aria-current') === 'true');
    expect(items).toHaveLength(3);
    expect(current.map((item) => item.textContent)).toEqual(['Dark']);
  });

  it('applies the colour scheme saved in this browser on load', () => {
    localStorage.setItem('app-color-scheme', 'dark');

    renderWithProviders(<AppRoutes />);

    expect(document.documentElement).toHaveAttribute('data-mantine-color-scheme', 'dark');
  });

  it('renders the whole app with its own providers and router', async () => {
    window.history.pushState({}, '', '/');
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});
