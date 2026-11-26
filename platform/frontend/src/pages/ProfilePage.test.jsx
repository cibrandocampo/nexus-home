import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { AppRoutes } from '../App';
import i18n from '../i18n';
import { renderWithProviders } from '../test/render';
import { apiError, makeUser, server, withSession } from '../test/server';

function patchMe(onBody) {
  return http.patch('/api/auth/me', async ({ request }) => {
    const body = await request.json();
    onBody?.(body);
    return HttpResponse.json(makeUser(body));
  });
}

// Name and password are changed rarely: their forms open on demand.
const openName = async () =>
  userEvent.click(await screen.findByRole('button', { name: 'Edit name' }));
const openPassword = async (name) => userEvent.click(await screen.findByRole('button', { name }));
// The dialog's submit button has the same name as the key that opened it.
const submitPassword = () =>
  userEvent.click(
    within(screen.getByRole('dialog', { name: 'Change password' })).getByRole('button', {
      name: 'Change password',
    }),
  );

describe('ProfilePage', () => {
  it('shows the account and saves a new name', async () => {
    let saved;
    server.use(
      withSession(),
      patchMe((body) => (saved = body)),
    );
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    expect(await screen.findByRole('heading', { name: 'Profile' })).toBeInTheDocument();
    expect(screen.getByText('ana@example.com')).toBeInTheDocument();
    await openName();
    const first = screen.getByLabelText(/First name/);
    await waitFor(() => expect(first).toHaveFocus());
    await userEvent.clear(first);
    await userEvent.type(first, ' Uxía ');
    await userEvent.click(screen.getByRole('button', { name: 'Save name' }));

    await waitFor(() => expect(saved).toEqual({ first_name: 'Uxía', last_name: 'Pérez' }));
    expect(await screen.findByText('Profile saved.')).toBeInTheDocument();
    expect(await screen.findByText('Uxía Pérez')).toBeInTheDocument();
    expect(screen.queryByLabelText(/First name/)).not.toBeInTheDocument();
  });

  it('shows who is signed in with the name and password forms closed', async () => {
    server.use(withSession(makeUser({ auth_method: 'password' })));
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    expect(await screen.findByRole('heading', { name: 'Ana Pérez' })).toBeInTheDocument();
    expect(screen.getByText('ana@example.com')).toBeInTheDocument();
    expect(screen.getByText('User')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Change password' })).toBeInTheDocument();
    expect(screen.queryByLabelText(/First name/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Current password/)).not.toBeInTheDocument();
  });

  it('offers no password change to an account that signs in with emailed codes', async () => {
    server.use(withSession());
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await screen.findByRole('heading', { name: 'Ana Pérez' });
    expect(screen.queryByRole('button', { name: 'Change password' })).not.toBeInTheDocument();
  });

  it('closes a form on cancel and gives the focus back to its button', async () => {
    server.use(withSession());
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await openName();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByLabelText(/First name/)).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Edit name' })).toHaveFocus());
  });

  it('requires both names', async () => {
    server.use(withSession());
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await openName();
    await userEvent.clear(screen.getByLabelText(/Last name/));
    await userEvent.click(screen.getByRole('button', { name: 'Save name' }));

    expect(await screen.findByText('Required')).toBeInTheDocument();
  });

  it('notifies when the name cannot be saved', async () => {
    server.use(
      withSession(),
      http.patch('/api/auth/me', () => apiError(500, 'boom')),
    );
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await openName();
    await userEvent.click(screen.getByRole('button', { name: 'Save name' }));

    expect(await screen.findByText('Unexpected error. Please try again.')).toBeInTheDocument();
  });

  it('saves the language and the colour scheme at once', async () => {
    const saved = [];
    server.use(
      withSession(),
      patchMe((body) => saved.push(body)),
    );
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await userEvent.click(await screen.findByRole('radio', { name: 'Dark' }));
    await waitFor(() => expect(saved).toContainEqual({ theme: 'dark' }));
    expect(document.documentElement).toHaveAttribute('data-mantine-color-scheme', 'dark');

    await userEvent.click(screen.getByRole('radio', { name: 'Galego' }));
    await waitFor(() => expect(saved).toContainEqual({ language: 'gl' }));
    await waitFor(() => expect(i18n.resolvedLanguage).toBe('gl'));
  });

  it('saves a time zone picked from the list', async () => {
    const saved = [];
    server.use(
      withSession(makeUser({ timezone: 'Europe/Madrid' })),
      patchMe((body) => saved.push(body)),
    );
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    const zone = await screen.findByRole('button', { name: 'Time zone' });
    expect(zone).toHaveTextContent(/^Europe\/Madrid \(UTC[+-]\d/);
    await userEvent.click(zone);
    const search = await screen.findByRole('textbox', { name: 'Search time zone' });
    await waitFor(() => expect(search).toHaveFocus());
    await userEvent.type(search, 'lisb');
    expect(screen.getAllByRole('option')).toHaveLength(1);
    await userEvent.click(screen.getByRole('option', { name: /^Europe\/Lisbon/ }));

    await waitFor(() => expect(saved).toEqual([{ timezone: 'Europe/Lisbon' }]));
  });

  it('finds a time zone by its city name with spaces and says when none matches', async () => {
    server.use(withSession());
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await userEvent.click(await screen.findByRole('button', { name: 'Time zone' }));
    const search = await screen.findByRole('textbox', { name: 'Search time zone' });
    await userEvent.type(search, 'new_york');
    expect(screen.getByRole('option', { name: /^America\/New York/ })).toBeInTheDocument();

    await userEvent.clear(search);
    await userEvent.type(search, 'atlantis');
    expect(screen.getByText('No time zone matches.')).toBeInTheDocument();
  });

  it("offers the browser's time zone to an account still in UTC", async () => {
    const saved = [];
    const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const zone = detected === 'Europe/Oslo' ? 'Europe/Rome' : 'Europe/Oslo';
    const resolvedOptions = vi
      .spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions')
      .mockReturnValue({ timeZone: zone });
    server.use(
      withSession(),
      patchMe((body) => saved.push(body)),
    );
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    expect(await screen.findByText(`Your browser is in ${zone}.`)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Use it' }));

    await waitFor(() => expect(saved).toEqual([{ timezone: zone }]));
    expect(screen.queryByText(/Your browser is in/)).not.toBeInTheDocument();
    resolvedOptions.mockRestore();
  });

  it('does not offer the browser time zone once one is chosen', async () => {
    server.use(withSession(makeUser({ timezone: 'America/Lima' })));
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await screen.findByRole('button', { name: 'Time zone' });
    expect(screen.queryByText(/Your browser is in/)).not.toBeInTheDocument();
  });

  it('changes the password of a password account and keeps the session', async () => {
    let body;
    server.use(
      withSession(makeUser({ auth_method: 'password' })),
      http.post('/api/auth/change-password', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({
          access_token: 'new',
          user: makeUser({ auth_method: 'password' }),
        });
      }),
    );
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await openPassword('Change password');
    await userEvent.type(screen.getByLabelText(/Current password/), 'old password!');
    await userEvent.type(screen.getByLabelText(/^New password/), 'a new long password');
    await userEvent.type(screen.getByLabelText(/Repeat the new password/), 'a new long password');
    await submitPassword();

    await waitFor(() =>
      expect(body).toEqual({
        current_password: 'old password!',
        new_password: 'a new long password',
      }),
    );
    expect(await screen.findByText(/Password saved/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Current password/)).not.toBeInTheDocument();
  });

  it('requires the first name and every password field', async () => {
    server.use(withSession(makeUser({ auth_method: 'password' })));
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await openName();
    await userEvent.clear(screen.getByLabelText(/First name/));
    await userEvent.click(screen.getByRole('button', { name: 'Save name' }));
    await openPassword('Change password');
    await submitPassword();

    expect(await screen.findAllByText('Required')).toHaveLength(3);
  });

  it('checks the repeated password', async () => {
    server.use(withSession(makeUser({ auth_method: 'password' })));
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await openPassword('Change password');
    await userEvent.type(screen.getByLabelText(/Current password/), 'old password!');
    await userEvent.type(screen.getByLabelText(/^New password/), 'a new long password');
    await userEvent.type(screen.getByLabelText(/Repeat the new password/), 'another one!!');
    await submitPassword();

    expect(await screen.findByText('The passwords do not match.')).toBeInTheDocument();
  });

  it.each([
    ['invalid_credentials', 400, 'The current password is not correct.'],
    ['weak_password', 400, 'This password is too weak.'],
    ['boom', 500, 'The password could not be saved.'],
  ])('explains a %s answer', async (code, status, message) => {
    server.use(
      withSession(makeUser({ auth_method: 'password' })),
      http.post('/api/auth/change-password', () => apiError(status, code)),
    );
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await openPassword('Change password');
    await userEvent.type(screen.getByLabelText(/Current password/), 'old password!');
    await userEvent.type(screen.getByLabelText(/^New password/), 'a new long password');
    await userEvent.type(screen.getByLabelText(/Repeat the new password/), 'a new long password');
    await submitPassword();

    expect(await screen.findByText(new RegExp(message))).toBeInTheDocument();
  });

  it('logs out from the top bar', async () => {
    server.use(
      withSession(),
      http.post('/api/auth/logout', () => new HttpResponse(null, { status: 204 })),
    );
    renderWithProviders(<AppRoutes />, { route: '/profile' });

    await userEvent.click(await screen.findByRole('button', { name: 'Log out' }));

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('is reachable from the waiting page by an account without permissions', async () => {
    server.use(withSession(makeUser({ role: 'none' })));
    const { router } = renderWithProviders(<AppRoutes />);

    await userEvent.click(await screen.findByRole('link', { name: 'Edit your profile' }));

    expect(router.location.pathname).toBe('/profile');
    expect(await screen.findByText('Waiting for access')).toBeInTheDocument(); // role badge
  });
});
