import {
  applyKiteBrandIcon,
  normalizeKiteBrandIcon,
  normalizeKiteBrandIconSize,
  type KiteBrandIcon,
  type KiteBrandIconSize,
} from './kiteBrandIcon';

export const KITE_SIGNAL_TABLE_LAYOUT_KEY = 'kite_st_view_layout';
export const KITE_TERMINAL_THEME_KEY = 'kite_terminal_theme';
export const KITE_SETTINGS_STORAGE_KEY = 'kite-settings';
export const STERLING_SHOW_CRYPTO_TAB_KEY = 'sterling_show_crypto_tab';
export const KITE_DEFAULT_PREFERENCES_MIGRATION_KEY = 'kite_default_preferences_migration';
export const KITE_DEFAULT_PREFERENCES_VERSION = 'list-layout-light-terminal-v1';
export const KITE_CHART_WORKSPACE_KEY = 'sterling:kite-chart-workspace:v1';
export const KITE_CHART_TEMPLATES_KEY = 'sterling:kite-chart-templates:v1';
export const TRADINGVIEW_DOWN_RED = '#f23645';

const LEGACY_CHART_DOWN_REDS = new Set(['#e05260', '#df514c']);

type PreferenceStorage = Pick<Storage, 'getItem' | 'setItem'>;
type JsonRecord = Record<string, any>;

function getBrowserStorage(): PreferenceStorage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is JsonRecord {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function readStoredKiteSettings(storage: PreferenceStorage): any {
  try {
    const raw = storage.getItem(KITE_SETTINGS_STORAGE_KEY);
    return raw ? JSON.parse(raw)?.state : null;
  } catch {
    return null;
  }
}

function readStoredBrandIcon(storage: PreferenceStorage): KiteBrandIcon {
  return normalizeKiteBrandIcon(readStoredKiteSettings(storage)?.brandIcon);
}

function readStoredBrandIconSize(storage: PreferenceStorage): KiteBrandIconSize {
  return normalizeKiteBrandIconSize(readStoredKiteSettings(storage)?.brandIconSize);
}

function applyStoredBrandIcon(storage: PreferenceStorage): void {
  applyKiteBrandIcon(readStoredBrandIcon(storage), readStoredBrandIconSize(storage));
}

function seedStableDefaults(storage: PreferenceStorage): void {
  if (storage.getItem(STERLING_SHOW_CRYPTO_TAB_KEY) === null) {
    storage.setItem(STERLING_SHOW_CRYPTO_TAB_KEY, 'false');
  }
}

function shouldUseTradingViewDownRed(value: unknown): boolean {
  return typeof value !== 'string' || LEGACY_CHART_DOWN_REDS.has(value.trim().toLowerCase());
}

function migrateWorkspaceAppearance(workspace: JsonRecord): boolean {
  const appearance = isRecord(workspace.appearance) ? workspace.appearance : {};
  if (!isRecord(workspace.appearance)) workspace.appearance = appearance;
  if (!shouldUseTradingViewDownRed(appearance.candleDown)) return false;
  appearance.candleDown = TRADINGVIEW_DOWN_RED;
  return true;
}

/**
 * Move the legacy Sterling/Kite down-candle reds to TradingView's canonical red.
 * Custom user-selected colours are preserved. Saved templates are migrated too,
 * otherwise loading an older template would silently restore the previous shade.
 */
export function migrateTradingViewChartPalette(storage: PreferenceStorage): void {
  try {
    const rawWorkspace = storage.getItem(KITE_CHART_WORKSPACE_KEY);
    if (rawWorkspace === null) {
      storage.setItem(KITE_CHART_WORKSPACE_KEY, JSON.stringify({
        appearance: { candleDown: TRADINGVIEW_DOWN_RED },
      }));
    } else {
      const workspace = JSON.parse(rawWorkspace);
      if (isRecord(workspace) && migrateWorkspaceAppearance(workspace)) {
        storage.setItem(KITE_CHART_WORKSPACE_KEY, JSON.stringify(workspace));
      }
    }
  } catch {
    // A malformed legacy workspace should not block app startup.
  }

  try {
    const rawTemplates = storage.getItem(KITE_CHART_TEMPLATES_KEY);
    if (!rawTemplates) return;
    const templates = JSON.parse(rawTemplates);
    if (!Array.isArray(templates)) return;

    let changed = false;
    for (const template of templates) {
      if (!isRecord(template) || !isRecord(template.snapshot)) continue;
      const workspace = isRecord(template.snapshot.workspace) ? template.snapshot.workspace : {};
      if (!isRecord(template.snapshot.workspace)) template.snapshot.workspace = workspace;
      changed = migrateWorkspaceAppearance(workspace) || changed;
    }
    if (changed) storage.setItem(KITE_CHART_TEMPLATES_KEY, JSON.stringify(templates));
  } catch {
    // Ignore malformed template data and keep boot non-fatal.
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

    seedStableDefaults(storage);
    migrateTradingViewChartPalette(storage);
    if (typeof document !== 'undefined') {
      document.documentElement.style.setProperty('--tradingview-down-red', TRADINGVIEW_DOWN_RED);
    }

    if (!migrated) {
      if (layout === null || layout === 'grid') storage.setItem(KITE_SIGNAL_TABLE_LAYOUT_KEY, 'list');
      if (theme === null || theme === 'dark') storage.setItem(KITE_TERMINAL_THEME_KEY, 'light');
      storage.setItem(KITE_DEFAULT_PREFERENCES_MIGRATION_KEY, KITE_DEFAULT_PREFERENCES_VERSION);
      applyStoredBrandIcon(storage);
      return;
    }

    if (layout === null) storage.setItem(KITE_SIGNAL_TABLE_LAYOUT_KEY, 'list');
    if (theme === null) storage.setItem(KITE_TERMINAL_THEME_KEY, 'light');
    applyStoredBrandIcon(storage);
  } catch {
    // Storage can be unavailable in restricted/private contexts. Keep boot non-fatal.
  }
}
