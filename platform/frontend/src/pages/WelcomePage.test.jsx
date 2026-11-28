import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { AppRoutes } from '../App';
import { renderWithProviders } from '../test/render';
import { apiError, makeUser, server, withSession } from '../test/server';

const newUser = makeUser({ first_name: '', last_name: '' });

describe('WelcomePage', () => {
  it('asks for both names', async () => {
    server.use(withSession(newUser));
    renderWithProviders(<AppRoutes />, { route: '/welcome' });

    await userEvent.click(await screen.findByRole('button', { name: 'Continue' }));

    expect(await screen.findAllByText('Required')).toHaveLength(2);
  });

  it('saves the names and opens the app', async () => {
    let saved;
    server.use(
      withSession(newUser),
      http.patch('/api/auth/me', async ({ request }) => {
        saved = await request.json();
        return HttpResponse.json(makeUser(saved));
      }),
    );
    renderWithProviders(<AppRoutes />, { route: '/welcome' });

    await userEvent.type(await screen.findByLabelText(/First name/), ' Uxía ');
    await userEvent.type(screen.getByLabelText(/Last name/), 'Núñez');
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));

    expect(await screen.findByRole('heading', { name: 'Home' })).toBeInTheDocument();
    expect(saved).toEqual({ first_name: 'Uxía', last_name: 'Núñez' });
  });

  it('shows an error when saving fails', async () => {
    server.use(
      withSession(newUser),
      http.patch('/api/auth/me', () => apiError(500, 'boom')),
    );
    renderWithProviders(<AppRoutes />, { route: '/welcome' });

    await userEvent.type(await screen.findByLabelText(/First name/), 'Uxía');
    await userEvent.type(screen.getByLabelText(/Last name/), 'Núñez');
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Unexpected error'));
  });

  it('is skipped by a user who already has a name', async () => {
    server.use(withSession());
    renderWithProviders(<AppRoutes />, { route: '/welcome' });

    expect(await screen.findByRole('heading', { name: 'Home' })).toBeInTheDocument();
  });

  it('lets a new user log out', async () => {
    server.use(
      withSession(newUser),
      http.post('/api/auth/logout', () => new HttpResponse(null, { status: 204 })),
    );
    renderWithProviders(<AppRoutes />, { route: '/welcome' });

    await userEvent.click(await screen.findByRole('button', { name: 'Log out' }));

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});
