import { beforeEach, describe, expect, it } from 'vitest';
import {
  installKiteDefaultPreferences,
  KITE_DEFAULT_PREFERENCES_MIGRATION_KEY,
  KITE_DEFAULT_PREFERENCES_VERSION,
  KITE_SETTINGS_STORAGE_KEY,
  KITE_SIGNAL_TABLE_LAYOUT_KEY,
  KITE_TERMINAL_THEME_KEY,
} from './kiteDefaultPreferences';

describe('installKiteDefaultPreferences', () => {
  beforeEach(() => {
    localStorage.clear();
    document.head.innerHTML = '';
  });

  it('seeds fresh browsers with list signal layout and light terminal theme', () => {
    installKiteDefaultPreferences(localStorage);

    expect(localStorage.getItem(KITE_SIGNAL_TABLE_LAYOUT_KEY)).toBe('list');
    expect(localStorage.getItem(KITE_TERMINAL_THEME_KEY)).toBe('light');
    expect(localStorage.getItem(KITE_DEFAULT_PREFERENCES_MIGRATION_KEY)).toBe(KITE_DEFAULT_PREFERENCES_VERSION);
    expect(document.head.querySelector<HTMLLinkElement>('link[rel="icon"]')?.getAttribute('href')).toContain('data:image/svg+xml');
  });

  it('migrates the old implicit defaults once for existing browsers', () => {
    localStorage.setItem(KITE_SIGNAL_TABLE_LAYOUT_KEY, 'grid');
    localStorage.setItem(KITE_TERMINAL_THEME_KEY, 'dark');

    installKiteDefaultPreferences(localStorage);

    expect(localStorage.getItem(KITE_SIGNAL_TABLE_LAYOUT_KEY)).toBe('list');
    expect(localStorage.getItem(KITE_TERMINAL_THEME_KEY)).toBe('light');
    expect(localStorage.getItem(KITE_DEFAULT_PREFERENCES_MIGRATION_KEY)).toBe(KITE_DEFAULT_PREFERENCES_VERSION);
  });

  it('does not override user choices after the migration has already run', () => {
    localStorage.setItem(KITE_DEFAULT_PREFERENCES_MIGRATION_KEY, KITE_DEFAULT_PREFERENCES_VERSION);
    localStorage.setItem(KITE_SIGNAL_TABLE_LAYOUT_KEY, 'grid');
    localStorage.setItem(KITE_TERMINAL_THEME_KEY, 'dark');

    installKiteDefaultPreferences(localStorage);

    expect(localStorage.getItem(KITE_SIGNAL_TABLE_LAYOUT_KEY)).toBe('grid');
    expect(localStorage.getItem(KITE_TERMINAL_THEME_KEY)).toBe('dark');
  });

  it('applies a persisted terminal brand icon on boot', () => {
    localStorage.setItem(KITE_SETTINGS_STORAGE_KEY, JSON.stringify({ state: { brandIcon: 'terminal' } }));

    installKiteDefaultPreferences(localStorage);

    expect(document.head.querySelector<HTMLLinkElement>('link[rel="icon"]')?.getAttribute('href')).toBe('/favicon-terminal.svg?v=1');
  });

  it('applies a persisted emoji favicon size on boot', () => {
    localStorage.setItem(KITE_SETTINGS_STORAGE_KEY, JSON.stringify({ state: { brandIcon: 'rocket', brandIconSize: 'xlarge' } }));

    installKiteDefaultPreferences(localStorage);

    const href = document.head.querySelector<HTMLLinkElement>('link[rel="icon"]')?.getAttribute('href') ?? '';
    expect(href).toContain('data:image/svg+xml');
    expect(decodeURIComponent(href)).toContain('font-size="66"');
  });

  it('keeps boot non-fatal when storage is unavailable', () => {
    expect(() => installKiteDefaultPreferences(null)).not.toThrow();
  });
});
