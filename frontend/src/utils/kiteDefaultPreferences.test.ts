import { describe, expect, it } from 'vitest';
import {
  installKiteDefaultPreferences,
  KITE_DEFAULT_PREFERENCES_MIGRATION_KEY,
  KITE_DEFAULT_PREFERENCES_VERSION,
  KITE_SIGNAL_TABLE_LAYOUT_KEY,
  KITE_TERMINAL_THEME_KEY,
} from './kiteDefaultPreferences';

describe('installKiteDefaultPreferences', () => {
  it('seeds fresh browsers with list signal layout and light terminal theme', () => {
    localStorage.clear();

    installKiteDefaultPreferences(localStorage);

    expect(localStorage.getItem(KITE_SIGNAL_TABLE_LAYOUT_KEY)).toBe('list');
    expect(localStorage.getItem(KITE_TERMINAL_THEME_KEY)).toBe('light');
    expect(localStorage.getItem(KITE_DEFAULT_PREFERENCES_MIGRATION_KEY)).toBe(KITE_DEFAULT_PREFERENCES_VERSION);
  });

  it('migrates the old implicit defaults once for existing browsers', () => {
    localStorage.clear();
    localStorage.setItem(KITE_SIGNAL_TABLE_LAYOUT_KEY, 'grid');
    localStorage.setItem(KITE_TERMINAL_THEME_KEY, 'dark');

    installKiteDefaultPreferences(localStorage);

    expect(localStorage.getItem(KITE_SIGNAL_TABLE_LAYOUT_KEY)).toBe('list');
    expect(localStorage.getItem(KITE_TERMINAL_THEME_KEY)).toBe('light');
    expect(localStorage.getItem(KITE_DEFAULT_PREFERENCES_MIGRATION_KEY)).toBe(KITE_DEFAULT_PREFERENCES_VERSION);
  });

  it('does not override user choices after the migration has already run', () => {
    localStorage.clear();
    localStorage.setItem(KITE_DEFAULT_PREFERENCES_MIGRATION_KEY, KITE_DEFAULT_PREFERENCES_VERSION);
    localStorage.setItem(KITE_SIGNAL_TABLE_LAYOUT_KEY, 'grid');
    localStorage.setItem(KITE_TERMINAL_THEME_KEY, 'dark');

    installKiteDefaultPreferences(localStorage);

    expect(localStorage.getItem(KITE_SIGNAL_TABLE_LAYOUT_KEY)).toBe('grid');
    expect(localStorage.getItem(KITE_TERMINAL_THEME_KEY)).toBe('dark');
  });

  it('keeps boot non-fatal when storage is unavailable', () => {
    expect(() => installKiteDefaultPreferences(null)).not.toThrow();
  });
});
