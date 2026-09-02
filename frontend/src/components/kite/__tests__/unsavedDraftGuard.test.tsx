/**
 * The settings hub mounts exactly one section at a time, so navigating away
 * unmounts the panel and its unapplied draft goes with it — silently.
 *
 * That was harmless while every control wrote through immediately. The rework made
 * these pages draft-and-Apply, so a click on the rail can now discard a page of
 * edits the user believes are still pending.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import {
  hasUnsavedDraft, resetDraftGuard, setDraftDirty, useUnsavedDraftGuard,
} from '../config/unsavedDraftGuard';

beforeEach(() => resetDraftGuard());

describe('unsavedDraftGuard', () => {
  it('reports nothing pending on a clean slate', () => {
    expect(hasUnsavedDraft()).toBe(false);
  });

  it('reports a dirty panel', () => {
    setDraftDirty('supertrend', true);
    expect(hasUnsavedDraft()).toBe(true);
    setDraftDirty('supertrend', false);
    expect(hasUnsavedDraft()).toBe(false);
  });

  it('stays pending while ANY panel is dirty', () => {
    setDraftDirty('supertrend', true);
    setDraftDirty('navigator', true);
    setDraftDirty('supertrend', false);
    expect(hasUnsavedDraft()).toBe(true);
    setDraftDirty('navigator', false);
    expect(hasUnsavedDraft()).toBe(false);
  });

  it('clears on unmount, so a panel that is already gone cannot block navigation', () => {
    function Panel({ dirty }: { dirty: boolean }) {
      useUnsavedDraftGuard('supertrend', dirty);
      return <div>panel</div>;
    }
    const { unmount } = render(<Panel dirty />);
    expect(hasUnsavedDraft()).toBe(true);
    unmount();
    expect(hasUnsavedDraft()).toBe(false);
  });

  it('tracks the panel switching between dirty and clean', () => {
    function Panel({ dirty }: { dirty: boolean }) {
      useUnsavedDraftGuard('navigator', dirty);
      return <div>panel</div>;
    }
    const { rerender } = render(<Panel dirty={false} />);
    expect(hasUnsavedDraft()).toBe(false);
    rerender(<Panel dirty />);
    expect(hasUnsavedDraft()).toBe(true);
    rerender(<Panel dirty={false} />);
    expect(hasUnsavedDraft()).toBe(false);
  });
});

// ── the hub actually asks ─────────────────────────────────────────────────────
vi.mock('../../../hooks/useKite', () => ({
  useKiteAccounts: () => ({ data: { accounts: [], count: 0 }, isLoading: false }),
  useAddKiteAccount: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useActivateKiteAccount: () => ({ mutate: vi.fn() }),
  useDeleteKiteAccount: () => ({ mutate: vi.fn() }),
  useGenerateKiteSession: () => ({ mutate: vi.fn(), isPending: false }),
  useKiteBasketMargins: () => ({ mutate: vi.fn() }),
  useKiteLoginUrl: () => ({ data: undefined }),
  useKiteLogout: () => ({ mutate: vi.fn() }),
  useKiteOrderCharges: () => ({ mutate: vi.fn() }),
  useKiteOrderMargins: () => ({ mutate: vi.fn() }),
  useKiteMargins: () => ({ data: undefined }),
  useKiteStatus: () => ({ data: undefined }),
  useKiteTickerStatus: () => ({ data: undefined }),
  useKiteTickerSubscribe: () => ({ mutate: vi.fn() }),
  useKiteTickerUnsubscribe: () => ({ mutate: vi.fn() }),
  useRefreshKiteSession: () => ({ mutate: vi.fn() }),
  useTestKiteAccount: () => ({ mutate: vi.fn() }),
  useUpdateKiteAccount: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: { engine_enabled: true } }),
  useSetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  usePatchEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({ data: { rows: [] } }),
  useExpiryCalendar: () => ({ data: undefined, isLoading: false, isError: false, isFetching: false, refetch: vi.fn() }),
  useRunScan: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock('../../../hooks/useNavigator', () => ({
  useNavigatorConfig: () => ({ data: { record: { config: { enabled: false } } } }),
}));
vi.mock('../TradingModePanel', () => ({ TradingModePanel: () => <div>Trading mode controls</div> }));
vi.mock('../SuperTrendEnginePanel', () => ({ SuperTrendEnginePanel: () => <div>SuperTrend strategy panel</div> }));
vi.mock('../NavigatorSettingsPanel', () => ({ NavigatorSettingsPanel: () => <div>Navigator settings panel</div> }));
vi.mock('../NavigatorCalibrationPanel', () => ({ NavigatorCalibrationPanel: () => <div>Navigator calibration panel</div> }));
vi.mock('../TradeRulesPanels', () => ({
  ManualRulesPanel: () => <div>Manual rules panel</div>,
  AutomaticRulesPanel: () => <div>Automatic rules panel</div>,
}));
vi.mock('../KiteTelegramPanel', () => ({
  KiteTelegramPanel: () => <div>Kite alert destinations</div>,
  BrandIconPicker: () => <div>Icon picker</div>,
}));
vi.mock('../MotionStyleSettings', () => ({ MotionStyleSettings: () => <div>Motion style choices</div> }));
vi.mock('../KiteExchangeSettingsCard', () => ({ KiteExchangeSettingsCard: () => <div>Exchange choices</div> }));

describe('the settings hub asks before discarding a draft', () => {
  let confirmSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorage.clear();
    resetDraftGuard();
  });
  afterEach(() => confirmSpy?.mockRestore());

  const openSuperTrend = async () => {
    const { ConnectPane } = await import('../ConnectPane');
    render(<ConnectPane />);
    fireEvent.click(screen.getAllByRole('button', { name: /SuperTrend\s*Scan, entry & exit/i })[0]);
    expect(screen.getByText('SuperTrend strategy panel')).toBeInTheDocument();
  };

  it('does not ask when nothing is pending', async () => {
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true) as unknown as ReturnType<typeof vi.fn>;
    await openSuperTrend();
    fireEvent.click(screen.getAllByRole('button', { name: /Notifications\s*Kite Telegram alerts/i })[0]);
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(screen.getByText('Kite alert destinations')).toBeInTheDocument();
  });

  it('stays put when the user declines', async () => {
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false) as unknown as ReturnType<typeof vi.fn>;
    await openSuperTrend();
    setDraftDirty('supertrend', true);

    fireEvent.click(screen.getAllByRole('button', { name: /Notifications\s*Kite Telegram alerts/i })[0]);

    expect(confirmSpy).toHaveBeenCalled();
    expect(screen.getByText('SuperTrend strategy panel')).toBeInTheDocument();
    expect(screen.queryByText('Kite alert destinations')).not.toBeInTheDocument();
  });

  it('navigates when the user accepts the loss', async () => {
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true) as unknown as ReturnType<typeof vi.fn>;
    await openSuperTrend();
    setDraftDirty('supertrend', true);

    fireEvent.click(screen.getAllByRole('button', { name: /Notifications\s*Kite Telegram alerts/i })[0]);

    expect(confirmSpy).toHaveBeenCalled();
    expect(screen.getByText('Kite alert destinations')).toBeInTheDocument();
  });
});
