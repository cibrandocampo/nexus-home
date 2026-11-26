import { Box, Group, Stack } from '@mantine/core';

import { BrandMark } from './BrandMark';
import classes from './AuthLayout.module.css';
import { ColorSchemeMenu } from './ColorSchemeMenu';
import { LanguageMenu } from './LanguageMenu';

// Screens before the app (login, welcome, waiting): a narrow, left-aligned column on the page
// background, the brand at the top, the preferences in a quiet corner. No card.
export function AuthLayout({ children }) {
  return (
    <Box className={classes.page}>
      <Group justify="space-between" className={classes.top}>
        <BrandMark />
        <Group gap="xs">
          <LanguageMenu />
          <ColorSchemeMenu />
        </Group>
      </Group>
      <Stack component="main" className={classes.column}>
        {children}
      </Stack>
    </Box>
  );
}
