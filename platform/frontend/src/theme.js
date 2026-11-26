import { createTheme, localStorageColorSchemeManager } from '@mantine/core';

// Visual system (T015, from nudge's palette; documented in the frontend-patterns skill).
// The single place a project changes its look.

// Slate, nudge's primary: shade 7 (#454961) in light, shade 3 (#b9bde0) in dark.
const slate = [
  '#f2f3f8',
  '#e4e6f0',
  '#c9cce0',
  '#b9bde0',
  '#9a9fc0',
  '#7d8197',
  '#5a5f7d',
  '#454961',
  '#383c50',
  '#2a2e42',
];

// Mantine's dark scale drives dark surfaces: 7 = page, 6 = surfaces and inputs, 4 = borders, 0 = text.
const dark = [
  '#e6e7ef',
  '#b8bccc',
  '#9a9fb2',
  '#6f7590',
  '#343849',
  '#2a2e42',
  '#1d2029',
  '#14161d',
  '#101218',
  '#0b0c10',
];

// Zinc neutrals for light borders and muted text.
const gray = [
  '#fafafa',
  '#f4f4f5',
  '#e4e4e7',
  '#d4d4d8',
  '#a1a1aa',
  '#8a8ea1',
  '#63677a',
  '#575c75',
  '#3f3f46',
  '#18181b',
];

// Status colours from nudge, placed so the global shades (7 light, 3 dark) land on its tokens:
// danger #9f1239 / #f87171, success #0f766e / #2dd4bf.
const red = [
  '#fff1f2',
  '#ffe4e6',
  '#fecdd3',
  '#f87171',
  '#e85d75',
  '#c81e4a',
  '#b01542',
  '#9f1239',
  '#881337',
  '#6b1a1a',
];
const teal = [
  '#f0fdfa',
  '#ccfbf1',
  '#99f6e4',
  '#2dd4bf',
  '#14b8a6',
  '#0d9488',
  '#0f8a80',
  '#0f766e',
  '#115e59',
  '#134e4a',
];

// Amber: the brand mark only. Never used for actions or text on the page background.
export const BRAND = { background: '#fcd34d', text: '#78350f' };

export const theme = createTheme({
  colors: { slate, dark, gray, red, teal },
  primaryColor: 'slate',
  primaryShade: { light: 7, dark: 3 },
  black: '#0a0a0a',
  white: '#ffffff',
  fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  headings: {
    fontWeight: '650',
    sizes: {
      h1: { fontSize: '1.75rem', lineHeight: '1.25' },
      h2: { fontSize: '1.375rem', lineHeight: '1.3' },
      h3: { fontSize: '1.125rem', lineHeight: '1.35' },
    },
  },
  radius: { xs: '4px', sm: '6px', md: '8px', lg: '8px', xl: '8px' },
  defaultRadius: 'sm',
  // Borders separate surfaces; shadows only lift floating layers (menus, notifications).
  shadows: {
    xs: 'none',
    sm: 'none',
    md: '0 4px 16px rgba(20, 22, 29, 0.10)',
    lg: '0 8px 24px rgba(20, 22, 29, 0.12)',
    xl: '0 12px 32px rgba(20, 22, 29, 0.14)',
  },
  cursorType: 'pointer',
  respectReducedMotion: true,
  components: {
    // Standalone links must not look like body text (the brand link opts out with underline="never").
    Anchor: { defaultProps: { underline: 'always' } },
    // Sentence case everywhere (visual system): no upper-case badges.
    Badge: { defaultProps: { tt: 'none' } },
    // Mantine's default indicator is a light surface on a light track (1.1:1); a filled one meets 3:1.
    SegmentedControl: { defaultProps: { color: 'slate' } },
  },
});

// Page background, text and border colours Mantine does not take from the colour scales.
export function cssVariablesResolver() {
  return {
    variables: {},
    light: {
      '--mantine-color-body': '#fafafa',
      '--mantine-color-text': '#2a2e42',
      '--mantine-color-dimmed': '#575c75',
      '--mantine-color-default': '#ffffff',
      '--mantine-color-default-border': '#e4e4e7',
      '--app-color-surface': '#ffffff',
      '--app-color-heading': '#0a0a0a',
      '--app-color-control-border': '#8a8ea1',
      '--app-color-on-filled': '#ffffff',
      '--mantine-primary-color-contrast': '#ffffff',
      '--mantine-color-anchor': '#454961',
      '--mantine-color-error': '#9f1239',
    },
    dark: {
      '--mantine-color-body': '#14161d',
      '--mantine-color-text': '#e6e7ef',
      '--mantine-color-dimmed': '#9a9fb2',
      '--mantine-color-default': '#1d2029',
      '--mantine-color-default-border': '#343849',
      '--app-color-surface': '#1d2029',
      '--app-color-heading': '#f4f4f6',
      '--app-color-control-border': '#6f7590',
      '--app-color-on-filled': '#14161d',
      '--mantine-primary-color-contrast': '#14161d',
      '--mantine-color-anchor': '#b9bde0',
      '--mantine-color-error': '#f87171',
    },
  };
}

// light | dark | auto (follows the OS); remembered in this browser, synced with the user's
// saved preference after login.
export const colorSchemeManager = localStorageColorSchemeManager({ key: 'app-color-scheme' });
