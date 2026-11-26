import { Group, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { BRAND } from '../theme';
import classes from './BrandMark.module.css';

// The app's mark: the one amber element in the interface, with the app's name beside it.
export function BrandMark() {
  const { t } = useTranslation();
  const name = t('app.name');

  return (
    <Group gap={10} wrap="nowrap">
      <span
        className={classes.mark}
        style={{ background: BRAND.background, color: BRAND.text }}
        aria-hidden="true"
      >
        {name.charAt(0).toUpperCase()}
      </span>
      <Text component="span" fw={650} fz="md" className={classes.name}>
        {name}
      </Text>
    </Group>
  );
}
