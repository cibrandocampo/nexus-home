import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AppRoutes } from '../App';
import { renderWithProviders } from '../test/render';
import { apiError, makeUser, server } from '../test/server';

const startAnswers = (method) =>
  http.post('/api/auth/login/start', () => HttpResponse.json({ method }));

async function enterEmail(email = 'ana@example.com') {
  await userEvent.type(await screen.findByLabelText(/Email/), email);
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
}

async function typeCode(code = '123456') {
  await userEvent.click(await screen.findByRole('textbox', { name: 'Code digit 1 of 6' }));
  await userEvent.keyboard(code);
}

afterEach(() => {
  vi.useRealTimers();
});

describe('LoginPage', () => {
  it('says sign-up is possible when it is open', async () => {
    server.use(http.get('/api/auth/config', () => HttpResponse.json({ allow_self_signup: true })));
    renderWithProviders(<AppRoutes />, { route: '/login' });

    expect(
      await screen.findByRole('heading', { name: 'Sign in or create an account' }),
    ).toBeInTheDocument();
  });

  it('signs in with a password and opens the app', async () => {
    let body;
    server.use(
      startAnswers('password'),
      http.post('/api/auth/login/verify', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ access_token: 't', user: makeUser(), is_new: false });
      }),
    );
    renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail(' ana@example.com ');
    await userEvent.type(await screen.findByLabelText(/Password/), 'correct horse battery');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('heading', { name: 'Welcome' })).toBeInTheDocument();
    expect(body).toEqual({ email: 'ana@example.com', password: 'correct horse battery' });
  });

  it('signs in with a code and sends a new account to the welcome step', async () => {
    let body;
    server.use(
      startAnswers('otp'),
      http.post('/api/auth/login/verify', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({
          access_token: 't',
          user: makeUser({ first_name: '', last_name: '', role: 'none' }),
          is_new: true,
        });
      }),
    );
    renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail();
    expect(await screen.findByText('We have sent a 6-digit code to')).toBeInTheDocument();
    expect(screen.getByText('ana@example.com')).toBeInTheDocument();
    await typeCode('123456');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('heading', { name: 'Welcome!' })).toBeInTheDocument();
    expect(body).toEqual({ email: 'ana@example.com', code: '123456' });
  });

  it('returns to the page that asked for a login', async () => {
    server.use(
      startAnswers('password'),
      http.post('/api/auth/login/verify', () =>
        HttpResponse.json({ access_token: 't', user: makeUser(), is_new: false }),
      ),
    );
    renderWithProviders(<AppRoutes />, { route: '/somewhere' });

    await enterEmail();
    await userEvent.type(await screen.findByLabelText(/Password/), 'correct horse battery');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });

  it.each([
    ['user_not_found', 404, 'There is no account with this email.'],
    ['disposable_email', 400, 'Disposable email addresses cannot be used.'],
    ['account_disabled', 403, 'This account is disabled.'],
    ['rate_limited', 429, 'Too many attempts.'],
    ['something_else', 500, 'Something went wrong.'],
  ])('explains a %s answer to the email step', async (code, status, message) => {
    server.use(http.post('/api/auth/login/start', () => apiError(status, code)));
    renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail();

    expect(await screen.findByRole('alert')).toHaveTextContent(message);
  });

  it.each([
    ['invalid_credentials', 400, 'The code or password is not correct.'],
    ['locked', 429, 'Too many failed attempts.'],
    ['method_mismatch', 400, 'This account uses another sign-in method.'],
  ])('explains a %s answer to the password step', async (code, status, message) => {
    server.use(
      startAnswers('password'),
      http.post('/api/auth/login/verify', () => apiError(status, code)),
    );
    renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail();
    await userEvent.type(await screen.findByLabelText(/Password/), 'wrong password!');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(message);
  });

  it('only allows asking for a new code after 30 seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const start = vi.fn(() => HttpResponse.json({ method: 'otp' }));
    server.use(http.post('/api/auth/login/start', start));
    renderWithProviders(<AppRoutes />, { route: '/login' });
    await enterEmail();

    expect(await screen.findByText('New code in 30 s')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Send a new code' })).not.toBeInTheDocument();
    for (let second = 0; second < 30; second += 1) {
      // One tick per second, as in the browser: each tick schedules the next after rendering.
      await act(() => vi.advanceTimersByTimeAsync(1000));
    }
    await userEvent.click(await screen.findByRole('button', { name: 'Send a new code' }));

    await waitFor(() => expect(start).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('New code in 30 s')).toBeInTheDocument();
  });

  it('goes back to the email step', async () => {
    server.use(startAnswers('password'));
    renderWithProviders(<AppRoutes />, { route: '/login' });
    await enterEmail();

    await userEvent.click(await screen.findByRole('button', { name: 'Use another email' }));

    expect(screen.getByLabelText(/Email/)).toHaveValue('ana@example.com');
    expect(screen.queryByLabelText(/Password/)).not.toBeInTheDocument();
  });

  it('keeps the submit button disabled until the step has its input', async () => {
    server.use(startAnswers('otp'));
    renderWithProviders(<AppRoutes />, { route: '/login' });

    expect(await screen.findByRole('button', { name: 'Continue' })).toBeDisabled();
    await enterEmail();
    await typeCode('123');
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled();
  });

  it('sends a visitor who already has a session to the app', async () => {
    server.use(
      http.post('/api/auth/refresh', () =>
        HttpResponse.json({ access_token: 't', user: makeUser() }),
      ),
    );
    renderWithProviders(<AppRoutes />, { route: '/login' });

    expect(await screen.findByRole('heading', { name: 'Welcome' })).toBeInTheDocument();
  });

  it('names the code group and each of its digits', async () => {
    server.use(startAnswers('otp'));
    renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail();

    expect(await screen.findByRole('group', { name: 'Code' })).toBeInTheDocument();
    for (let position = 1; position <= 6; position += 1) {
      expect(
        screen.getByRole('textbox', { name: `Code digit ${position} of 6` }),
      ).toBeInTheDocument();
    }
  });

  it('checks the email shape before asking the server', async () => {
    const start = vi.fn(() => HttpResponse.json({ method: 'otp' }));
    server.use(http.post('/api/auth/login/start', start));
    renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail('ana@example');

    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a valid email address.');
    expect(start).not.toHaveBeenCalled();
  });

  it('explains a server validation error as an invalid email', async () => {
    server.use(http.post('/api/auth/login/start', () => apiError(422, 'validation_error')));
    renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail('ana@example.com');

    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a valid email address.');
  });

  it('gives password managers the account name on the password step', async () => {
    server.use(startAnswers('password'));
    const { container } = renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail();
    await screen.findByLabelText(/Password/);

    const username = container.querySelector('input[autocomplete="username"]');
    expect(username).toHaveValue('ana@example.com');
  });

  it('keeps the query string and hash of the page that asked for a login', async () => {
    server.use(
      startAnswers('password'),
      http.post('/api/auth/login/verify', () =>
        HttpResponse.json({ access_token: 't', user: makeUser(), is_new: false }),
      ),
    );
    const { router } = renderWithProviders(<AppRoutes />, { route: '/somewhere?tab=2#part' });

    await enterEmail();
    await userEvent.type(await screen.findByLabelText(/Password/), 'correct horse battery');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await screen.findByRole('heading', { name: 'Page not found' });
    expect(router.location).toMatchObject({
      pathname: '/somewhere',
      search: '?tab=2',
      hash: '#part',
    });
  });

  it('moves the focus to the first code digit', async () => {
    server.use(startAnswers('otp'));
    renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail();

    const first = await screen.findByRole('textbox', { name: 'Code digit 1 of 6' });
    await waitFor(() => expect(first).toHaveFocus());
    // Let Mantine's layout effects and transitions settle, then check the focus stayed.
    await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
    expect(screen.getByRole('textbox', { name: 'Code digit 1 of 6' })).toHaveFocus();
  });

  it('moves the focus to the password field', async () => {
    server.use(startAnswers('password'));
    renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail();

    await waitFor(() => expect(screen.getByLabelText(/Password/)).toHaveFocus());
  });

  it('does not blame the email for a validation error after the email step', async () => {
    server.use(
      startAnswers('password'),
      http.post('/api/auth/login/verify', () => apiError(422, 'validation_error')),
    );
    renderWithProviders(<AppRoutes />, { route: '/login' });

    await enterEmail();
    await userEvent.type(await screen.findByLabelText(/Password/), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong.');
  });
});
