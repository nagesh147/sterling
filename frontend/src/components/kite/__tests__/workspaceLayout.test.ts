import { describe, expect, it } from 'vitest';
import {
  DEFAULT_WORKSPACE_LAYOUT,
  WORKSPACE_LAYOUT_KEY,
  applyWorkspacePreset,
  clampWorkspaceSizes,
  loadWorkspaceLayout,
  minimizePane,
  movePaneToSlot,
  paneSlot,
  restoreAllPanes,
  restorePane,
  sanitizeWorkspaceLayout,
} from '../workspaceLayout';

function storage(values: Record<string, string> = {}) {
  return { getItem: (key: string) => values[key] ?? null };
}

describe('workspace layout state', () => {
  it('returns independent defaults for missing or malformed values', () => {
    const first = sanitizeWorkspaceLayout(null);
    const second = sanitizeWorkspaceLayout('broken');
    first.minimized.push('watchlist');
    first.sizes.left = 999;

    expect(second).toEqual(DEFAULT_WORKSPACE_LAYOUT);
    expect(second.minimized).toEqual([]);
    expect(second.sizes.left).toBe(360);
  });

  it('repairs duplicate, missing, and unknown pane assignments', () => {
    const next = sanitizeWorkspaceLayout({
      slots: { left: 'dashboard', center: 'dashboard', right: 'unknown' },
      minimized: ['signals', 'signals', 'unknown'],
      sizes: { left: Number.NaN, right: 612, bottom: Infinity },
    });

    expect(new Set(Object.values(next.slots))).toEqual(new Set(['watchlist', 'dashboard', 'signals', 'terminal']));
    expect(next.slots.left).toBe('dashboard');
    expect(next.minimized).toEqual(['signals']);
    expect(next.sizes).toEqual({ left: 360, right: 612, bottom: 220 });
  });

  it('swaps pane positions without losing the displaced pane', () => {
    const next = movePaneToSlot(DEFAULT_WORKSPACE_LAYOUT, 'signals', 'left');

    expect(next.slots.left).toBe('signals');
    expect(next.slots.right).toBe('watchlist');
    expect(paneSlot(next, 'signals')).toBe('left');
    expect(movePaneToSlot(next, 'signals', 'left')).toBe(next);
  });

  it('minimizes idempotently and restores individual or all panes', () => {
    const one = minimizePane(DEFAULT_WORKSPACE_LAYOUT, 'terminal');
    const stillOne = minimizePane(one, 'terminal');
    const two = minimizePane(stillOne, 'signals');

    expect(stillOne).toBe(one);
    expect(two.minimized).toEqual(['terminal', 'signals']);
    expect(restorePane(two, 'terminal').minimized).toEqual(['signals']);
    expect(restoreAllPanes(two).minimized).toEqual([]);
  });

  it('clamps splitters while preserving usable center and content heights', () => {
    expect(clampWorkspaceSizes(
      { left: 900, right: 900, bottom: 900 },
      { width: 1200, height: 700 },
    )).toEqual({ left: 432, right: 432, bottom: 406 });

    const narrow = clampWorkspaceSizes(
      { left: -10, right: 9999, bottom: 0 },
      { width: 600, height: 300 },
    );
    expect(narrow.left).toBeGreaterThanOrEqual(120);
    expect(narrow.right).toBeGreaterThanOrEqual(120);
    expect(narrow.left + narrow.right).toBeLessThanOrEqual(340);
    expect(narrow.bottom).toBeGreaterThanOrEqual(60);
  });

  it('migrates all legacy pane visibility, size, and lock keys', () => {
    const migrated = loadWorkspaceLayout(storage({
      kite_sidebar_width: '475',
      kite_right_sidebar_width: '710',
      kite_bottombar_height: '310',
      kite_sidebar_open: 'false',
      kite_right_sidebar_open: 'false',
      kite_terminal_mode: 'minimized',
      kite_layout_locked: 'true',
    }));

    expect(migrated.sizes).toEqual({ left: 475, right: 710, bottom: 310 });
    expect(migrated.minimized).toEqual(['watchlist', 'signals', 'terminal']);
    expect(migrated.locked).toBe(true);
  });

  it('prefers a valid v2 snapshot over legacy keys', () => {
    const saved = {
      ...DEFAULT_WORKSPACE_LAYOUT,
      slots: { left: 'signals', center: 'dashboard', right: 'watchlist', bottom: 'terminal' },
      minimized: ['watchlist'],
    };
    const loaded = loadWorkspaceLayout(storage({
      [WORKSPACE_LAYOUT_KEY]: JSON.stringify(saved),
      kite_sidebar_open: 'true',
    }));

    expect(loaded.slots.left).toBe('signals');
    expect(loaded.minimized).toEqual(['watchlist']);
  });

  it('applies ergonomic presets, restores every pane, and preserves locking', () => {
    const current = { ...DEFAULT_WORKSPACE_LAYOUT, minimized: ['terminal' as const], locked: true };
    const chart = applyWorkspacePreset(current, 'chart');
    const execution = applyWorkspacePreset(current, 'execution');

    expect(chart.sizes).toEqual({ left: 280, right: 420, bottom: 160 });
    expect(execution.sizes).toEqual({ left: 260, right: 700, bottom: 280 });
    expect(chart.minimized).toEqual([]);
    expect(chart.locked).toBe(true);
    expect(chart.slots).toEqual(DEFAULT_WORKSPACE_LAYOUT.slots);
  });
});
