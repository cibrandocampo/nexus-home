import { ActionIcon, Menu } from '@mantine/core';
import { Check, Languages } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { notifyError } from '../api/queryClient';
import { useAuth } from '../auth/useAuth';
import { LANGUAGE_NAMES, LANGUAGES } from '../i18n';

export function LanguageMenu() {
  const { t, i18n } = useTranslation();
  const { user, updateProfile } = useAuth();
  const current = i18n.resolvedLanguage;

  const choose = (language) => {
    i18n.changeLanguage(language);
    if (user) updateProfile({ language }).catch(notifyError);
  };

  return (
    <Menu position="bottom-end">
      <Menu.Target>
        <ActionIcon variant="default" size="lg" aria-label={t('language.label')}>
          <Languages size={18} aria-hidden />
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown>
        {LANGUAGES.map((language) => (
          <Menu.Item
            key={language}
            lang={language}
            onClick={() => choose(language)}
            aria-current={language === current ? 'true' : undefined}
            rightSection={language === current ? <Check size={16} aria-hidden /> : null}
          >
            {LANGUAGE_NAMES[language]}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
