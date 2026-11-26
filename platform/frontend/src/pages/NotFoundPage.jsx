import { Anchor, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <Stack align="center" mt="xl">
      <Title order={1}>{t('notFound.title')}</Title>
      <Text>{t('notFound.text')}</Text>
      <Anchor component={Link} to="/">
        {t('notFound.back')}
      </Anchor>
    </Stack>
  );
}
