// API client: JSON over fetch, access token in memory, one shared refresh on 401.

const REFRESH_PATH = '/auth/refresh';
// Answers that must not trigger a refresh: they are the login and refresh calls themselves.
const NO_REFRESH = ['/auth/login/', REFRESH_PATH, '/auth/logout'];
export const REFRESH_RETRY_DELAY_MS = 300;

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let accessToken = null;
let refreshing = null;
let sessionEndHandler = () => window.location.assign('/login');

export const getAccessToken = () => accessToken;
export const setAccessToken = (token) => {
  accessToken = token;
};
// Called when the session cannot be refreshed (the app sends the user to the login page).
export const onSessionEnd = (handler) => {
  sessionEndHandler = handler;
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function toError(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    // not JSON (proxy error page, empty body)
  }
  const error = body?.error;
  return new ApiError(
    response.status,
    error?.code ?? 'http_error',
    error?.message ?? response.statusText,
    error?.details,
  );
}

function send(path, { method = 'GET', body, headers } = {}) {
  const init = { method, credentials: 'same-origin', headers: { ...headers } };
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  if (accessToken) init.headers.Authorization = `Bearer ${accessToken}`;
  return fetch(`/api${path}`, init);
}

async function refreshOnce() {
  for (let attempt = 1; ; attempt += 1) {
    const response = await fetch(`/api${REFRESH_PATH}`, {
      method: 'POST',
      credentials: 'same-origin',
    });
    if (response.ok) {
      const data = await response.json();
      accessToken = data.access_token;
      return data;
    }
    const error = await toError(response);
    // Another tab rotated the cookie a moment ago: its new cookie arrives shortly, try again once.
    if (error.code === 'refresh_in_progress' && attempt === 1) {
      await sleep(REFRESH_RETRY_DELAY_MS);
      continue;
    }
    if (error.status === 401) accessToken = null; // the session is over
    throw error;
  }
}

// One refresh at a time: shared by the requests of this tab and, where the browser supports
// Web Locks, serialised across tabs. Only a 401 ends the session (once, however many requests
// were waiting); a network error, 5xx or 429 is a temporary failure and keeps it.
export function refreshSession() {
  if (!refreshing) {
    const run = () => refreshOnce();
    const locked = globalThis.navigator?.locks?.request('auth-refresh', run) ?? run();
    refreshing = locked
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) sessionEndHandler();
        throw error;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function parse(response) {
  if (response.status === 204) return null;
  return response.json();
}

export async function api(path, options) {
  let response = await send(path, options);
  if (response.status === 401 && !NO_REFRESH.some((prefix) => path.startsWith(prefix))) {
    const unauthorized = await toError(response);
    try {
      await refreshSession();
    } catch (error) {
      throw error.status === 401 ? unauthorized : error;
    }
    response = await send(path, options);
  }
  if (!response.ok) throw await toError(response);
  return parse(response);
}
