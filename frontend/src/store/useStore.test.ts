import { beforeEach, describe, expect, it, vi } from 'vitest';

const THEME_DEFAULT_MIGRATION_KEY = 'sterling_theme_default_migrated_v1';

const importStore = async () => {
  vi.resetModules();
  return import('./useStore');
};

describe('Sterling theme preference', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.style.colorScheme = '';
  });

  it('uses the Kite light theme as the default for fresh browser profiles', async () => {
    const { DEFAULT_THEME, useStore } = await importStore();

    expect(DEFAULT_THEME).toBe('light');
    expect(useStore.getState().theme).toBe('light');
    expect(localStorage.getItem('sterling_theme')).toBe('light');
    expect(localStorage.getItem(THEME_DEFAULT_MIGRATION_KEY)).toBe('true');
  });

  it('migrates older browser profiles that still had the terminal dark theme saved', async () => {
    localStorage.setItem('sterling_theme', 'dark');

    const { useStore } = await importStore();

    expect(useStore.getState().theme).toBe('light');
    expect(localStorage.getItem('sterling_theme')).toBe('light');
    expect(localStorage.getItem(THEME_DEFAULT_MIGRATION_KEY)).toBe('true');
  });

  it.each(['light', 'dark', 'grey'] as const)('honors an explicit saved %s theme after migration', async (theme) => {
    localStorage.setItem(THEME_DEFAULT_MIGRATION_KEY, 'true');
    localStorage.setItem('sterling_theme', theme);

    const { useStore } = await importStore();

    expect(useStore.getState().theme).toBe(theme);
  });

  it('falls back to light when a migrated browser profile has a corrupt saved theme', async () => {
    localStorage.setItem(THEME_DEFAULT_MIGRATION_KEY, 'true');
    localStorage.setItem('sterling_theme', 'kite-v1');

    const { useStore } = await importStore();

    expect(useStore.getState().theme).toBe('light');
  });

  it('persists and applies theme changes to the document root', async () => {
    const { useStore } = await importStore();

    useStore.getState().setTheme('dark');

    expect(localStorage.getItem('sterling_theme')).toBe('dark');
    expect(localStorage.getItem(THEME_DEFAULT_MIGRATION_KEY)).toBe('true');
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('resets back to the default Kite light theme', async () => {
    localStorage.setItem(THEME_DEFAULT_MIGRATION_KEY, 'true');
    localStorage.setItem('sterling_theme', 'dark');
    const { useStore } = await importStore();

    useStore.getState().resetUI();

    expect(localStorage.getItem('sterling_theme')).toBe('light');
    expect(localStorage.getItem(THEME_DEFAULT_MIGRATION_KEY)).toBe('true');
    expect(useStore.getState().theme).toBe('light');
    expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  });
});
