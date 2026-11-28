import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

export const unauthorized = () =>
  HttpResponse.json(
    { error: { code: 'unauthorized', message: 'Authentication required' } },
    { status: 401 },
  );

export const apiError = (status, code) =>
  HttpResponse.json({ error: { code, message: code } }, { status });

export function makeUser(overrides = {}) {
  return {
    id: 1,
    email: 'ana@example.com',
    first_name: 'Ana',
    last_name: 'Pérez',
    role: 'user',
    auth_method: 'otp',
    language: 'en',
    theme: 'system',
    timezone: 'UTC',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    last_login_at: null,
    ...overrides,
  };
}

// A browser that already has a session for `user` (the refresh cookie restores it).
export const withSession = (user = makeUser()) =>
  http.post('/api/auth/refresh', () => HttpResponse.json({ access_token: 'token', user }));

// Defaults: nobody is logged in and sign-up is closed. Tests override with server.use(...).
export const server = setupServer(
  http.post('/api/auth/refresh', unauthorized),
  http.get('/api/auth/config', () => HttpResponse.json({ allow_self_signup: false })),
  http.get('/api/devices', () => HttpResponse.json({ items: [], total: 0, page: 1, size: 100 })),
);
