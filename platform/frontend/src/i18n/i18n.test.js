import { describe, expect, it, vi } from 'vitest';

import en from './en.json';
import es from './es.json';
import gl from './gl.json';
import i18n, { LANGUAGES } from '.';

const keys = (object, prefix = '') =>
  Object.entries(object).flatMap(([key, value]) =>
    typeof value === 'object' ? keys(value, `${prefix}${key}.`) : [`${prefix}${key}`],
  );

describe('i18n', () => {
  it('has the same keys in every language', () => {
    expect(keys(es).sort()).toEqual(keys(en).sort());
    expect(keys(gl).sort()).toEqual(keys(en).sort());
  });

  it('supports English, Spanish and Galician', () => {
    expect(LANGUAGES).toEqual(['en', 'es', 'gl']);
  });

  it('maps a regional variant to its language', async () => {
    await i18n.changeLanguage('es-ES');

    expect(i18n.resolvedLanguage).toBe('es');
    expect(i18n.t('nav.home')).toBe('Inicio');
  });

  it('falls back to English for unsupported languages', async () => {
    await i18n.changeLanguage('fr');

    expect(i18n.resolvedLanguage).toBe('en');
    expect(i18n.t('nav.home')).toBe('Home');
  });

  it('keeps the html lang attribute in step', async () => {
    await i18n.changeLanguage('gl');

    expect(document.documentElement.getAttribute('lang')).toBe('gl');
  });

  it('prefers the language saved in this browser over the browser language', async () => {
    localStorage.setItem('i18nextLng', 'gl');
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['es-ES']);

    const fresh = i18n.cloneInstance();
    await fresh.init();

    expect(fresh.resolvedLanguage).toBe('gl');
  });
});
