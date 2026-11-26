import { Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

export function HomePage() {
  const { t } = useTranslation();

  return (
    <Stack>
      <Title order={1}>{t('home.title')}</Title>
      <Text>{t('home.text')}</Text>
    </Stack>
  );
}
