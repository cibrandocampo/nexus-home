import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';

import en from './en.json';
import es from './es.json';
import gl from './gl.json';

export const LANGUAGES = ['en', 'es', 'gl'];
// Each language named in itself, so anyone can find theirs.
export const LANGUAGE_NAMES = { en: 'English', es: 'Español', gl: 'Galego' };

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en }, es: { translation: es }, gl: { translation: gl } },
    supportedLngs: LANGUAGES,
    load: 'languageOnly', // es-ES -> es
    fallbackLng: 'en',
    detection: { order: ['localStorage', 'navigator'], caches: ['localStorage'] },
    interpolation: { escapeValue: false }, // React escapes
  });

// Keep <html lang> in step with the interface language (screen readers, hyphenation).
// Resources are bundled, so the language is resolved synchronously by init().
const syncHtmlLang = () => document.documentElement.setAttribute('lang', i18n.resolvedLanguage);
syncHtmlLang();
i18n.on('languageChanged', syncHtmlLang);

export default i18n;
