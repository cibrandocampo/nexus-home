import { Alert } from '@mantine/core';
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

// An API error in words (errors.<code>), focused when it appears: the button that failed was
// disabled while it ran and lost the focus.
// `messages` replaces the wording of some codes where the page knows better (a token just typed).
export function DeviceErrorAlert({ error, messages = {} }) {
  const { t, i18n } = useTranslation();
  const ref = useRef(null);
  useEffect(() => {
    if (error) ref.current?.focus();
  }, [error]);
  if (!error) return null;
  const key = `errors.${error.code}`;
  return (
    <Alert color="red" role="alert" ref={ref} tabIndex={-1}>
      {messages[error.code] ?? (i18n.exists(key) ? t(key) : t('errors.generic'))}
    </Alert>
  );
}
