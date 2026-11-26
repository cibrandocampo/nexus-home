import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { server } from '../test/server';
import {
  ApiError,
  api,
  getAccessToken,
  onSessionEnd,
  refreshSession,
  setAccessToken,
} from './client';

const user = { id: 1, email: 'ana@example.com' };
const unauthorized = () =>
  HttpResponse.json(
    { error: { code: 'unauthorized', message: 'Authentication required' } },
    { status: 401 },
  );

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('api', () => {
  let ended;

  beforeEach(() => {
    ended = vi.fn();
    onSessionEnd(ended);
  });

  it('sends JSON with the access token and parses the answer', async () => {
    setAccessToken('token-1');
    let seen;
    server.use(
      http.post('/api/things', async ({ request }) => {
        seen = { auth: request.headers.get('authorization'), body: await request.json() };
        return HttpResponse.json({ ok: true });
      }),
    );

    const result = await api('/things', { method: 'POST', body: { name: 'x' } });

    expect(result).toEqual({ ok: true });
    expect(seen).toEqual({ auth: 'Bearer token-1', body: { name: 'x' } });
  });

  it('returns null for 204 answers', async () => {
    server.use(http.delete('/api/things/1', () => new HttpResponse(null, { status: 204 })));

    expect(await api('/things/1', { method: 'DELETE' })).toBeNull();
  });

  it('turns the error envelope into an ApiError', async () => {
    server.use(
      http.get('/api/things', () =>
        HttpResponse.json(
          { error: { code: 'validation_error', message: 'Invalid request', details: [1] } },
          { status: 422 },
        ),
      ),
    );

    const error = await api('/things').catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, code: 'validation_error', details: [1] });
  });

  it('handles error answers that are not JSON', async () => {
    server.use(http.get('/api/things', () => new HttpResponse('Bad gateway', { status: 502 })));

    const error = await api('/things').catch((e) => e);

    expect(error).toMatchObject({ status: 502, code: 'http_error' });
  });

  it('refreshes once on 401 and retries with the new token', async () => {
    setAccessToken('expired');
    server.use(
      http.get('/api/things', ({ request }) =>
        request.headers.get('authorization') === 'Bearer fresh'
          ? HttpResponse.json({ ok: true })
          : unauthorized(),
      ),
      http.post('/api/auth/refresh', () => HttpResponse.json({ access_token: 'fresh', user })),
    );

    expect(await api('/things')).toEqual({ ok: true });
    expect(getAccessToken()).toBe('fresh');
  });

  it('shares one refresh between parallel requests', async () => {
    setAccessToken('expired');
    const refresh = vi.fn(() => HttpResponse.json({ access_token: 'fresh', user }));
    server.use(
      http.get('/api/things/:id', ({ request }) =>
        request.headers.get('authorization') === 'Bearer fresh'
          ? HttpResponse.json({ ok: true })
          : unauthorized(),
      ),
      http.post('/api/auth/refresh', refresh),
    );

    await Promise.all([api('/things/1'), api('/things/2'), api('/things/3')]);

    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('ends the session when the refresh fails', async () => {
    setAccessToken('expired');
    server.use(http.get('/api/things', unauthorized), http.post('/api/auth/refresh', unauthorized));

    const error = await api('/things').catch((e) => e);

    expect(error).toMatchObject({ status: 401, code: 'unauthorized' });
    expect(ended).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
  });

  it('ends the session once for parallel requests', async () => {
    setAccessToken('expired');
    server.use(
      http.get('/api/things/:id', unauthorized),
      http.post('/api/auth/refresh', unauthorized),
    );

    await Promise.allSettled([api('/things/1'), api('/things/2'), api('/things/3')]);

    expect(ended).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['a server error', () => new HttpResponse('down', { status: 503 })],
    [
      'a rate limit',
      () => HttpResponse.json({ error: { code: 'rate_limited', message: 'x' } }, { status: 429 }),
    ],
    ['a network error', () => HttpResponse.error()],
  ])('keeps the session when the refresh fails with %s', async (_name, answer) => {
    setAccessToken('expired');
    server.use(http.get('/api/things', unauthorized), http.post('/api/auth/refresh', answer));

    await expect(api('/things')).rejects.toBeTruthy();

    expect(ended).not.toHaveBeenCalled();
    expect(getAccessToken()).toBe('expired');
  });

  it('does not try to refresh for the login calls', async () => {
    const refresh = vi.fn();
    server.use(
      http.post('/api/auth/login/verify', unauthorized),
      http.post('/api/auth/refresh', refresh),
    );

    await expect(api('/auth/login/verify', { method: 'POST', body: {} })).rejects.toMatchObject({
      status: 401,
    });
    expect(refresh).not.toHaveBeenCalled();
  });
});

describe('refreshSession', () => {
  it('retries once after a short delay when another tab is rotating the cookie', async () => {
    let calls = 0;
    server.use(
      http.post('/api/auth/refresh', () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json(
              { error: { code: 'refresh_in_progress', message: 'retry' } },
              { status: 401 },
            )
          : HttpResponse.json({ access_token: 'fresh', user });
      }),
    );

    const data = await refreshSession();

    expect(calls).toBe(2);
    expect(data.user).toEqual(user);
    expect(getAccessToken()).toBe('fresh');
  });

  it('gives up after the single retry', async () => {
    const inProgress = () =>
      HttpResponse.json(
        { error: { code: 'refresh_in_progress', message: 'retry' } },
        { status: 401 },
      );
    server.use(http.post('/api/auth/refresh', inProgress));

    await expect(refreshSession()).rejects.toMatchObject({ code: 'refresh_in_progress' });
  });

  it('uses a Web Lock when the browser has them', async () => {
    const request = vi.fn((_name, run) => run());
    vi.stubGlobal('navigator', { ...navigator, locks: { request } });
    server.use(
      http.post('/api/auth/refresh', () => HttpResponse.json({ access_token: 't', user })),
    );

    await refreshSession();

    expect(request).toHaveBeenCalledWith('auth-refresh', expect.any(Function));
  });

  it('sends the user to the login page by default', async () => {
    vi.resetModules();
    const fresh = await import('./client'); // a new module keeps the default handler
    const assign = vi.fn();
    vi.stubGlobal('location', { ...window.location, assign });
    server.use(http.get('/api/things', unauthorized), http.post('/api/auth/refresh', unauthorized));

    await expect(fresh.api('/things')).rejects.toMatchObject({ status: 401 });

    expect(assign).toHaveBeenCalledWith('/login');
  });
});
