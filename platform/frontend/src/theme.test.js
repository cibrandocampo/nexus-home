import { describe, expect, it } from 'vitest';

import { cssVariablesResolver, theme } from './theme';

describe('theme', () => {
  it("puts nudge's tokens on the shades each scheme uses", () => {
    const shade = (color, scheme) => theme.colors[color][theme.primaryShade[scheme]];

    expect([shade('slate', 'light'), shade('slate', 'dark')]).toEqual(['#454961', '#b9bde0']);
    expect([shade('red', 'light'), shade('red', 'dark')]).toEqual(['#9f1239', '#f87171']);
    expect([shade('teal', 'light'), shade('teal', 'dark')]).toEqual(['#0f766e', '#2dd4bf']);
  });

  it('uses dark text on filled colours in dark mode and white in light mode', () => {
    const { light, dark } = cssVariablesResolver();

    expect([light['--app-color-on-filled'], dark['--app-color-on-filled']]).toEqual([
      '#ffffff',
      '#14161d',
    ]);
    expect(dark['--mantine-primary-color-contrast']).toBe(dark['--app-color-on-filled']);
  });

  it('underlines standalone links', () => {
    expect(theme.components.Anchor.defaultProps.underline).toBe('always');
  });

  it('keeps badges in sentence case and fills the segmented control indicator', () => {
    expect(theme.components.Badge.defaultProps.tt).toBe('none');
    expect(theme.components.SegmentedControl.defaultProps.color).toBe('slate');
  });
});
