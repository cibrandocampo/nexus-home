import { Button, Group, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link, Navigate } from 'react-router';

import { useAuth } from '../auth/useAuth';

// Signed-up account without permissions yet: an administrator has to grant access.
export function WaitingPage() {
  const { t } = useTranslation();
  const { user } = useAuth();

  if (user.role !== 'none') return <Navigate to="/" replace />;

  return (
    <Stack gap="lg" maw={520}>
      <Title order={1}>{t('waiting.title')}</Title>
      <Text>{t('waiting.text', { email: user.email })}</Text>
      <Text c="dimmed">{t('waiting.hint')}</Text>
      <Group>
        <Button component={Link} to="/profile" variant="default">
          {t('waiting.profile')}
        </Button>
      </Group>
    </Stack>
  );
}
