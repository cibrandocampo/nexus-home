import { ActionIcon, Menu, useMantineColorScheme } from '@mantine/core';
import { Check, Monitor, Moon, Sun } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { notifyError } from '../api/queryClient';
import { useAuth } from '../auth/useAuth';

const ICONS = { light: Sun, dark: Moon, auto: Monitor };

export function ColorSchemeMenu() {
  const { t } = useTranslation();
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  const { user, updateProfile } = useAuth();
  const Current = ICONS[colorScheme];

  const choose = (scheme) => {
    setColorScheme(scheme);
    if (user) updateProfile({ theme: scheme === 'auto' ? 'system' : scheme }).catch(notifyError);
  };

  return (
    <Menu position="bottom-end">
      <Menu.Target>
        <ActionIcon variant="default" size="lg" aria-label={t('colorScheme.label')}>
          <Current size={18} aria-hidden />
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown>
        {Object.entries(ICONS).map(([scheme, Icon]) => (
          <Menu.Item
            key={scheme}
            leftSection={<Icon size={16} aria-hidden />}
            onClick={() => choose(scheme)}
            // Mantine fixes role="menuitem"; aria-current marks the active choice for assistive
            // technology and the check mark shows it visually.
            aria-current={scheme === colorScheme ? 'true' : undefined}
            rightSection={scheme === colorScheme ? <Check size={16} aria-hidden /> : null}
          >
            {t(`colorScheme.${scheme}`)}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
