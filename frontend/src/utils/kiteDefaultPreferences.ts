import { applyKiteBrandIcon, normalizeKiteBrandIcon, type KiteBrandIcon } from './kiteBrandIcon';

export const KITE_SIGNAL_TABLE_LAYOUT_KEY = 'kite_st_view_layout';
export const KITE_TERMINAL_THEME_KEY = 'kite_terminal_theme';
export const KITE_SETTINGS_STORAGE_KEY = 'kite-settings';
export const KITE_DEFAULT_PREFERENCES_MIGRATION_KEY = 'kite_default_preferences_migration';
export const KITE_DEFAULT_PREFERENCES_VERSION = 'list-layout-light-terminal-v1';

type PreferenceStorage = Pick<Storage, 'getItem' | 'setItem'>;

function getBrowserStorage(): PreferenceStorage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function readStoredBrandIcon(storage: PreferenceStorage): KiteBrandIcon {
  try {
    const raw = storage.getItem(KITE_SETTINGS_STORAGE_KEY);
    if (!raw) return 'phoenix';
    return normalizeKiteBrandIcon(JSON.parse(raw)?.state?.brandIcon);
  } catch {
    return 'phoenix';
  }
}

/**
 * Seed and migrate Kite UI defaults without fighting the user forever.
 *
 * Older builds wrote their implicit fallbacks (`grid` signal table + `dark` terminal)
 * into localStorage on first render, so a missing-only default change would not reach
 * existing browsers. This one-time migration moves legacy default values to the new
 * defaults, then marks the migration complete so later manual user choices are kept.
 */
export function installKiteDefaultPreferences(storage: PreferenceStorage | null = getBrowserStorage()): void {
  if (!storage) return;

  try {
    const migrated = storage.getItem(KITE_DEFAULT_PREFERENCES_MIGRATION_KEY) === KITE_DEFAULT_PREFERENCES_VERSION;
    const layout = storage.getItem(KITE_SIGNAL_TABLE_LAYOUT_KEY);
    const theme = storage.getItem(KITE_TERMINAL_THEME_KEY);

    if (!migrated) {
      if (layout === null || layout === 'grid') storage.setItem(KITE_SIGNAL_TABLE_LAYOUT_KEY, 'list');
      if (theme === null || theme === 'dark') storage.setItem(KITE_TERMINAL_THEME_KEY, 'light');
      storage.setItem(KITE_DEFAULT_PREFERENCES_MIGRATION_KEY, KITE_DEFAULT_PREFERENCES_VERSION);
      applyKiteBrandIcon(readStoredBrandIcon(storage));
      return;
    }

    if (layout === null) storage.setItem(KITE_SIGNAL_TABLE_LAYOUT_KEY, 'list');
    if (theme === null) storage.setItem(KITE_TERMINAL_THEME_KEY, 'light');
    applyKiteBrandIcon(readStoredBrandIcon(storage));
  } catch {
    // Storage can be unavailable in restricted/private contexts. Keep boot non-fatal.
  }
}
