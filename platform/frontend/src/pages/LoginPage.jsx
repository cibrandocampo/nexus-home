import {
  Alert,
  Anchor,
  Button,
  Group,
  PasswordInput,
  PinInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { AuthLayout } from '../components/AuthLayout';
import classes from './LoginPage.module.css';

export const RESEND_SECONDS = 30;
// A light check before calling the API; the server validates for real.
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const KNOWN_ERRORS = [
  'invalid_email',
  'user_not_found',
  'disposable_email',
  'account_disabled',
  'invalid_credentials',
  'method_mismatch',
  'locked',
  'rate_limited',
];

function useCountdown() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (seconds <= 0) return undefined;
    const timer = setTimeout(() => setSeconds(seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [seconds]);
  return [seconds, setSeconds];
}

export function LoginPage() {
  const { t } = useTranslation();
  const { loginStart, loginVerify } = useAuth();
  const config = useQuery({ queryKey: ['auth-config'], queryFn: () => api('/auth/config') });

  const [step, setStep] = useState('email'); // email | otp | password
  const [email, setEmail] = useState('');
  const [secret, setSecret] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [resendIn, setResendIn] = useCountdown();
  const secretInput = useRef(null);

  useEffect(() => {
    if (step !== 'email') secretInput.current?.focus();
  }, [step]);

  const run = async (action) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      // Only the email step sends free text the server can reject as invalid.
      const code = err.code === 'validation_error' && step === 'email' ? 'invalid_email' : err.code;
      setError(KNOWN_ERRORS.includes(code) ? code : 'generic');
    } finally {
      setBusy(false);
    }
  };

  const start = () => {
    if (!EMAIL_SHAPE.test(email.trim())) {
      setError('invalid_email');
      return;
    }
    run(async () => {
      const { method } = await loginStart(email.trim());
      setSecret('');
      setStep(method);
      if (method === 'otp') setResendIn(RESEND_SECONDS);
    });
  };

  const resend = () =>
    run(async () => {
      await loginStart(email.trim());
      setResendIn(RESEND_SECONDS);
    });

  // On success the session exists and AnonymousOnly leaves the login page.
  const verify = () =>
    run(async () => {
      const credentials = step === 'otp' ? { code: secret } : { password: secret };
      await loginVerify({ email: email.trim(), ...credentials });
    });

  const back = () => {
    setStep('email');
    setSecret('');
    setError(null);
  };

  const submit = (event) => {
    event.preventDefault();
    if (step === 'email') start();
    else verify();
  };

  const heading = config.data?.allow_self_signup ? t('login.titleSignup') : t('login.title');

  return (
    <AuthLayout>
      <form onSubmit={submit} noValidate>
        <Stack gap="lg">
          <Title order={1}>{heading}</Title>

          {step === 'email' && (
            <>
              <Text c="dimmed">{t('login.emailHelp')}</Text>
              <TextInput
                label={t('login.email')}
                type="email"
                autoComplete="username"
                spellCheck={false}
                autoCapitalize="off"
                required
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
              />
            </>
          )}

          {step === 'otp' && (
            <>
              <Stack gap={2}>
                <Text>{t('login.codeSentTo')}</Text>
                <Text fw={600} className={classes.email}>
                  {email.trim()}
                </Text>
                <Text c="dimmed" size="sm">
                  {t('login.codeValid')}
                </Text>
              </Stack>
              <Stack gap={4}>
                <Text id="login-code-label" fw={500} size="sm">
                  {t('login.code')}
                </Text>
                <PinInput
                  // A fixed id: without it Mantine generates one after mounting and rebuilds the
                  // inputs, which drops the focus just moved to the first digit.
                  id="login-code"
                  length={6}
                  type="number"
                  oneTimeCode
                  value={secret}
                  onChange={setSecret}
                  ref={secretInput}
                  placeholder=""
                  aria-labelledby="login-code-label"
                  getInputProps={(index) => ({
                    'aria-label': t('login.codeDigit', { position: index + 1, total: 6 }),
                  })}
                />
              </Stack>
              <Group justify="space-between">
                <Anchor component="button" type="button" onClick={back}>
                  {t('login.changeEmail')}
                </Anchor>
                {resendIn > 0 ? (
                  <Text c="dimmed" size="sm" aria-live="polite">
                    {t('login.resendIn', { seconds: resendIn })}
                  </Text>
                ) : (
                  <Anchor component="button" type="button" onClick={resend} disabled={busy}>
                    {t('login.resend')}
                  </Anchor>
                )}
              </Group>
            </>
          )}

          {step === 'password' && (
            <>
              <Stack gap={2}>
                <Text>{t('login.passwordFor')}</Text>
                <Text fw={600} className={classes.email}>
                  {email.trim()}
                </Text>
              </Stack>
              {/* Lets password managers tie the password to the account. */}
              <input
                type="text"
                name="username"
                autoComplete="username"
                value={email.trim()}
                readOnly
                hidden
              />
              <PasswordInput
                label={t('login.password')}
                autoComplete="current-password"
                required
                value={secret}
                onChange={(e) => setSecret(e.currentTarget.value)}
                ref={secretInput}
              />
              <Anchor component="button" type="button" onClick={back}>
                {t('login.changeEmail')}
              </Anchor>
            </>
          )}

          {error && (
            <Alert color="red" role="alert">
              {t(`login.errors.${error}`)}
            </Alert>
          )}

          <Button
            type="submit"
            loading={busy}
            disabled={
              step === 'email' ? !email.trim() : step === 'otp' ? secret.length !== 6 : !secret
            }
          >
            {step === 'email' ? t('login.continue') : t('login.signIn')}
          </Button>
        </Stack>
      </form>
    </AuthLayout>
  );
}
