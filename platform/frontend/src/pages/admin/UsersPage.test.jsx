import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { AppRoutes } from '../../App';
import { renderWithProviders } from '../../test/render';
import { apiError, makeUser, server, withSession } from '../../test/server';

const ADMIN = makeUser({
  id: 1,
  email: 'admin@example.com',
  first_name: 'Ada',
  last_name: 'Admin',
  role: 'admin',
});
const PENDING = makeUser({
  id: 2,
  email: 'new@example.com',
  first_name: '',
  last_name: '',
  role: 'none',
});
const USER = makeUser({ id: 3, email: 'ana@example.com', role: 'user' });
const OFF = makeUser({ id: 4, email: 'off@example.com', role: 'user', is_active: false });

function listing(items = [ADMIN, PENDING, USER, OFF], total = items.length) {
  const requests = [];
  const handler = http.get('/api/users', ({ request }) => {
    requests.push(new URL(request.url).searchParams);
    return HttpResponse.json({ items, total, page: 1, size: 20 });
  });
  return { handler, requests };
}

async function renderPage(...handlers) {
  server.use(withSession(ADMIN), ...handlers);
  const view = renderWithProviders(<AppRoutes />, { route: '/admin/users' });
  await screen.findByRole('heading', { name: 'Users' });
  return view;
}

const row = (email) => screen.getByRole('row', { name: new RegExp(email) });

// A row's actions live in its "⋯" menu.
async function rowAction(email, item) {
  await userEvent.click(await screen.findByRole('button', { name: `Actions for ${email}` }));
  await userEvent.click(await screen.findByRole('menuitem', { name: item }));
}

describe('UsersPage', () => {
  it('is not found for a user who is not an administrator', async () => {
    server.use(withSession(USER));
    renderWithProviders(<AppRoutes />, { route: '/admin/users' });

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });

  it('lists the users with their role and status', async () => {
    const { handler } = listing();
    await renderPage(handler);

    expect(await screen.findByText('ana@example.com')).toBeInTheDocument();
    expect(within(row('admin@example.com')).getByText('Administrator')).toBeInTheDocument();
    expect(within(row('new@example.com')).getByText('Waiting for access')).toBeInTheDocument();
    expect(within(row('ana@example.com')).queryByText('Disabled')).not.toBeInTheDocument();
    expect(within(row('off@example.com')).getByText('Disabled')).toBeInTheDocument();
  });

  it('does not offer to delete your own account or set its password', async () => {
    const { handler } = listing();
    await renderPage(handler);

    await userEvent.click(
      await screen.findByRole('button', { name: 'Actions for admin@example.com' }),
    );
    const own = await screen.findAllByRole('menuitem');
    expect(own.map((item) => item.textContent)).toEqual(['Edit user']);
    await userEvent.keyboard('{Escape}');

    await userEvent.click(screen.getByRole('button', { name: 'Actions for ana@example.com' }));
    await screen.findByRole('menuitem', { name: 'Delete user' });
    const other = screen.getAllByRole('menuitem');
    expect(other.map((item) => item.textContent)).toEqual([
      'Edit user',
      'Set password',
      'Delete user',
    ]);
  });

  it('searches and filters, back to the first page', async () => {
    const { handler, requests } = listing();
    await renderPage(handler);

    await userEvent.type(screen.getByRole('textbox', { name: 'Search' }), 'ana');
    await waitFor(() => expect(requests.at(-1).get('q')).toBe('ana'), { timeout: 2000 });
    await userEvent.click(screen.getByRole('button', { name: 'Filters' }));
    await userEvent.click(await screen.findByRole('combobox', { name: 'Role' }));
    await userEvent.click(await screen.findByRole('option', { name: 'Waiting for access' }));
    await waitFor(() => expect(requests.at(-1).get('role')).toBe('none'));
    await userEvent.click(screen.getByRole('combobox', { name: 'Status' }));
    await userEvent.click(await screen.findByRole('option', { name: 'Disabled' }));

    await waitFor(() => expect(requests.at(-1).get('active')).toBe('false'));
    expect(requests.at(-1).get('page')).toBe('1');
    expect(screen.getByRole('button', { name: 'Filters (2)' })).toBeInTheDocument();
  });

  it('says when no user matches', async () => {
    const { handler } = listing([]);
    await renderPage(handler);

    expect(await screen.findByText('No users match these filters.')).toBeInTheDocument();
  });

  it('pages through long lists', async () => {
    const { handler, requests } = listing([USER], 45);
    await renderPage(handler);

    await userEvent.click(await screen.findByRole('button', { name: 'Next page' }));

    await waitFor(() => expect(requests.at(-1).get('page')).toBe('2'));
  });

  it('grants access to a waiting account in one click', async () => {
    let body;
    const { handler } = listing();
    await renderPage(
      handler,
      http.patch('/api/users/2', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...PENDING, role: 'user' });
      }),
    );

    await userEvent.click(
      await within(await screen.findByRole('row', { name: /new@example.com/ })).findByRole(
        'button',
        { name: 'Grant access' },
      ),
    );

    await waitFor(() => expect(body).toEqual({ role: 'user' }));
    expect(await screen.findByText('new@example.com now has access.')).toBeInTheDocument();
  });

  it('shows why granting access failed', async () => {
    const { handler } = listing();
    await renderPage(
      handler,
      http.patch('/api/users/2', () => apiError(404, 'user_not_found')),
    );

    await userEvent.click(
      await within(await screen.findByRole('row', { name: /new@example.com/ })).findByRole(
        'button',
        { name: 'Grant access' },
      ),
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('This user no longer exists.');
  });

  it('creates a code user', async () => {
    let body;
    const { handler } = listing();
    await renderPage(
      handler,
      http.post('/api/users', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(makeUser({ id: 9, ...body }), { status: 201 });
      }),
    );

    await userEvent.click(screen.getByRole('button', { name: 'New user' }));
    const dialog = await screen.findByRole('dialog', { name: 'New user' });
    await userEvent.type(within(dialog).getByLabelText(/Email/), 'luis@example.com');
    await userEvent.type(within(dialog).getByLabelText('First name'), 'Luis');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }));

    await waitFor(() =>
      expect(body).toEqual({
        email: 'luis@example.com',
        first_name: 'Luis',
        last_name: '',
        role: 'user',
        auth_method: 'otp',
        language: 'en',
      }),
    );
    expect(await screen.findByText('User created.')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('creates a password user and asks for the password', async () => {
    let body;
    const { handler } = listing();
    await renderPage(
      handler,
      http.post('/api/users', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(makeUser({ id: 9 }), { status: 201 });
      }),
    );

    await userEvent.click(screen.getByRole('button', { name: 'New user' }));
    const dialog = await screen.findByRole('dialog', { name: 'New user' });
    await userEvent.type(within(dialog).getByLabelText(/Email/), 'pw@example.com');
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Sign-in method' }));
    await userEvent.click(await screen.findByRole('option', { name: 'Password' }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }));
    expect(await within(dialog).findByText('Required')).toBeInTheDocument();

    await userEvent.type(within(dialog).getByLabelText(/^New password/), 'a long password!');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }));

    await waitFor(() =>
      expect(body).toMatchObject({ auth_method: 'password', password: 'a long password!' }),
    );
  });

  it('checks the email before creating', async () => {
    const create = vi.fn();
    const { handler } = listing();
    await renderPage(handler, http.post('/api/users', create));

    await userEvent.click(screen.getByRole('button', { name: 'New user' }));
    const dialog = await screen.findByRole('dialog', { name: 'New user' });
    await userEvent.type(within(dialog).getByLabelText(/Email/), 'luis@example');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }));

    expect(await within(dialog).findByText('Enter a valid email address.')).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it.each([
    ['email_taken', 409, 'There is already a user with this email.'],
    ['weak_password', 400, 'This password is too weak'],
    ['something', 500, 'Something went wrong.'],
  ])('explains a %s answer when creating', async (code, status, message) => {
    const { handler } = listing();
    await renderPage(
      handler,
      http.post('/api/users', () => apiError(status, code)),
    );

    await userEvent.click(screen.getByRole('button', { name: 'New user' }));
    const dialog = await screen.findByRole('dialog', { name: 'New user' });
    await userEvent.type(within(dialog).getByLabelText(/Email/), 'luis@example.com');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create user' }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(message);
  });

  it('edits a user, sending the method only when it changed', async () => {
    const bodies = [];
    const { handler } = listing();
    await renderPage(
      handler,
      http.patch('/api/users/3', async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(USER);
      }),
    );

    await rowAction('ana@example.com', 'Edit user');
    let dialog = await screen.findByRole('dialog', { name: 'Edit user' });
    await userEvent.click(within(dialog).getByRole('switch', { name: 'Active (can sign in)' }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({
      first_name: 'Ana',
      last_name: 'Pérez',
      role: 'user',
      language: 'en',
      is_active: false,
    });
    expect(await screen.findByText('Changes saved.')).toBeInTheDocument();

    await rowAction('ana@example.com', 'Edit user');
    dialog = await screen.findByRole('dialog', { name: 'Edit user' });
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Sign-in method' }));
    await userEvent.click(await screen.findByRole('option', { name: 'Password' }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(bodies[1]).toMatchObject({ auth_method: 'password' }));
  });

  it('shows the last-admin guard and closes with Cancel', async () => {
    const { handler } = listing();
    await renderPage(
      handler,
      http.patch('/api/users/1', () => apiError(409, 'last_admin')),
    );

    await rowAction('admin@example.com', 'Edit user');
    const dialog = await screen.findByRole('dialog', { name: 'Edit user' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'At least one active administrator must remain.',
    );

    expect(within(dialog).getByRole('alert')).toHaveFocus();

    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Actions for admin@example.com' })).toHaveFocus(),
    );
  });

  it('names the close button and returns focus to "New user" when the row is gone', async () => {
    const { handler } = listing();
    await renderPage(
      handler,
      http.delete('/api/users/3', () => new HttpResponse(null, { status: 204 })),
    );
    await rowAction('ana@example.com', 'Delete user');
    const dialog = await screen.findByRole('dialog', { name: 'Delete user' });
    expect(within(dialog).getByRole('button', { name: 'Close' })).toBeInTheDocument();

    server.use(listing([ADMIN, PENDING]).handler);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: 'Actions for ana@example.com' }),
      ).not.toBeInTheDocument(),
    );
    await waitFor(() => expect(screen.getByRole('button', { name: 'New user' })).toHaveFocus());
  });

  it('sets a password', async () => {
    let body;
    const { handler } = listing();
    await renderPage(
      handler,
      http.post('/api/users/3/set-password', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(USER);
      }),
    );

    await rowAction('ana@example.com', 'Set password');
    const dialog = await screen.findByRole('dialog', { name: 'Set password' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Set password' }));
    expect(await within(dialog).findByText('Required')).toBeInTheDocument();
    await userEvent.type(within(dialog).getByLabelText(/^New password/), 'a long password!');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Set password' }));

    await waitFor(() => expect(body).toEqual({ password: 'a long password!' }));
    expect(await screen.findByText('Password set.')).toBeInTheDocument();
  });

  it('deletes a user after confirming', async () => {
    const remove = vi.fn(() => new HttpResponse(null, { status: 204 }));
    const { handler } = listing();
    await renderPage(handler, http.delete('/api/users/3', remove));

    await rowAction('ana@example.com', 'Delete user');
    const dialog = await screen.findByRole('dialog', { name: 'Delete user' });
    expect(
      within(dialog).getByText('Delete ana@example.com? This cannot be undone.'),
    ).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(remove).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('ana@example.com has been deleted.')).toBeInTheDocument();
  });

  it('explains a failed delete', async () => {
    const { handler } = listing();
    await renderPage(
      handler,
      http.delete('/api/users/3', () => apiError(409, 'cannot_delete_self')),
    );

    await rowAction('ana@example.com', 'Delete user');
    const dialog = await screen.findByRole('dialog', { name: 'Delete user' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'You cannot delete your own account.',
    );
  });
});
