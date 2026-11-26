import { Combobox, InputBase, useCombobox } from '@mantine/core';
import { Search } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { timeZoneOptions } from '../timeZones';

// Picks an IANA time zone from ~400: a field showing the current one opens a list with its own search
// box (by city or region, spaces or underscores alike).
export function TimeZonePicker({ value, onChange, labelId, className }) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const combobox = useCombobox({
    onDropdownOpen: () => combobox.focusSearchInput(),
    onDropdownClose: () => {
      combobox.resetSelectedOption();
      setSearch('');
    },
  });

  const options = timeZoneOptions();
  const query = search.trim().toLowerCase().replaceAll('_', ' ');
  const shown = query
    ? options.filter((option) => option.label.toLowerCase().includes(query))
    : options;

  return (
    <Combobox
      store={combobox}
      onOptionSubmit={(zone) => {
        onChange(zone);
        combobox.closeDropdown();
      }}
    >
      <Combobox.Target>
        <InputBase
          component="button"
          type="button"
          pointer
          aria-labelledby={labelId}
          rightSection={<Combobox.Chevron />}
          rightSectionPointerEvents="none"
          onClick={() => combobox.toggleDropdown()}
          classNames={{ input: className }}
        >
          {options.find((option) => option.value === value)?.label ?? value}
        </InputBase>
      </Combobox.Target>
      <Combobox.Dropdown>
        <Combobox.Search
          value={search}
          onChange={(event) => setSearch(event.currentTarget.value)}
          placeholder={t('timezone.search')}
          aria-label={t('timezone.search')}
          leftSection={<Search size={16} aria-hidden />}
        />
        <Combobox.Options mah={280} style={{ overflowY: 'auto' }}>
          {shown.length > 0 ? (
            shown.map((option) => (
              <Combobox.Option
                key={option.value}
                value={option.value}
                active={option.value === value}
              >
                {option.label}
              </Combobox.Option>
            ))
          ) : (
            <Combobox.Empty>{t('timezone.nothingFound')}</Combobox.Empty>
          )}
        </Combobox.Options>
      </Combobox.Dropdown>
    </Combobox>
  );
}
