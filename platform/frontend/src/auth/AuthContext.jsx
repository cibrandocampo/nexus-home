import { useMantineColorScheme } from '@mantine/core';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useEffectEvent, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';

import { api, onSessionEnd, refreshSession, setAccessToken } from '../api/client';
import i18n from '../i18n';
import { AuthContext } from './useAuth';

// The API stores "system"; Mantine calls it "auto".
const toColorScheme = (theme) => (theme === 'system' ? 'auto' : theme);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | anonymous | authenticated
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { colorScheme, setColorScheme } = useMantineColorScheme();

  const signIn = useCallback((session) => {
    setAccessToken(session.access_token);
    setUser(session.user);
    setStatus('authenticated');
  }, []);

  const signOut = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus('anonymous');
    queryClient.clear();
  }, [queryClient]);

  // Restore the session from the refresh cookie on load.
  useEffect(() => {
    refreshSession()
      .then(signIn)
      .catch(() => {
        setUser(null);
        setStatus('anonymous');
      });
  }, [signIn]);

  // A session the server ended (expired, revoked, deleted account): back to the login page.
  useEffect(() => {
    onSessionEnd(() => {
      signOut();
      navigate('/login', { replace: true });
    });
  }, [navigate, signOut]);

  // The user's saved preferences win over this browser's once they are known, and again whenever
  // the saved value changes. Keyed on the saved values only: a choice made in a menu applies at once
  // and must not be undone while it is being saved. The scheme is set only on a real change, since
  // each setColorScheme call switches off every CSS transition for a moment (it would cut the
  // navigation's animations); setColorScheme is a new function every render, hence the effect event.
  const language = user?.language;
  const theme = user?.theme;
  const applyTheme = useEffectEvent((saved) => {
    const scheme = toColorScheme(saved);
    if (colorScheme !== scheme) setColorScheme(scheme);
  });

  useEffect(() => {
    if (language && i18n.resolvedLanguage !== language) i18n.changeLanguage(language);
  }, [language]);

  useEffect(() => {
    if (theme) applyTheme(theme);
  }, [theme]);

  const value = useMemo(() => {
    const loginStart = (email) => api('/auth/login/start', { method: 'POST', body: { email } });

    const loginVerify = async ({ email, code, password }) => {
      const result = await api('/auth/login/verify', {
        method: 'POST',
        body: code === undefined ? { email, password } : { email, code },
      });
      signIn(result);
      return result;
    };

    const updateProfile = async (changes) => {
      const updated = await api('/auth/me', { method: 'PATCH', body: changes });
      setUser(updated);
      return updated;
    };

    // The server ends every other session and answers with a new one for this browser.
    const changePassword = async (body) => {
      const session = await api('/auth/change-password', { method: 'POST', body });
      signIn(session);
      return session;
    };

    const logout = async () => {
      try {
        await api('/auth/logout', { method: 'POST' });
      } catch {
        // Offline or server error: the local session ends anyway; the cookie expires on its own.
      }
      signOut();
      navigate('/login', { replace: true });
    };

    return {
      user,
      status,
      isNew: Boolean(user && !user.first_name && !user.last_name),
      loginStart,
      loginVerify,
      updateProfile,
      changePassword,
      logout,
    };
  }, [user, status, signIn, signOut, navigate]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
