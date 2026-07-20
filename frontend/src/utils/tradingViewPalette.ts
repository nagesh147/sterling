const CHART_WORKSPACE_KEY = 'sterling:kite-chart-workspace:v1';
export const TRADINGVIEW_DOWN_RED = '#f23645';

/**
 * Keep the chart palette consistent for both new and existing browsers.
 * Chart appearance is persisted in localStorage, so updating the source default
 * alone does not update users who already opened the chart once.
 */
export function installTradingViewPalette(storage: Pick<Storage, 'getItem' | 'setItem'> | null = typeof window === 'undefined' ? null : window.localStorage): void {
  if (!storage) return;

  try {
    const raw = storage.getItem(CHART_WORKSPACE_KEY);
    const workspace = raw ? JSON.parse(raw) : {};
    const appearance = workspace && typeof workspace.appearance === 'object' && workspace.appearance
      ? workspace.appearance
      : {};

    if (appearance.candleDown === TRADINGVIEW_DOWN_RED) return;

    storage.setItem(CHART_WORKSPACE_KEY, JSON.stringify({
      ...workspace,
      appearance: {
        ...appearance,
        candleDown: TRADINGVIEW_DOWN_RED,
      },
    }));
  } catch {
    // Invalid or unavailable storage must never block app startup.
  }
}
