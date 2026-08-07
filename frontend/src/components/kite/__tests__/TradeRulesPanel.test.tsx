import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { TradeRulesPanel } from '../TradeRulesPanel';

// Full EngineConfigModel fixture. The component reads several fields with
// `?? default` fallbacks, but the fixture carries the real backend defaults so
// the assertions exercise the true starting state.
const baseCfg = {
  engine_enabled: true,
  trail_target: 'fast',
  exit_mode: 'one_red',
  exit_aligned_trail: false,
  price_stop_exit: true,
  strike_moneyness: ['ITM1', 'ATM', 'OTM1'],
  scan_source: 'spot',
  scan_expiries: ['weekly', 'monthly'],
  scan_expiries_indices: null,
  scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'SENSEX'],
  scan_stocks: [],
  scan_all_stocks: false,
  auto_execute: false,
  risk_sizing: true,
  risk_pct: 1.0,
  max_lots: 10,
  expiry_square_off_days: 1,
  time_stop_bars: 0,
  stop_mode: 'both',
  protect_manual_orders: true,
  directional_mode: false,
  vehicle: 'otm_options',
  enabled_vehicles: ['otm_options', 'deep_itm_options'],
  itm_depth: 'ITM10',
  target_delta: null,
  futures_expiry: 'near',
  adx_min: null,
  atr_pct_min: null,
  block_entry_minutes_before_close: 0,
  max_spread_pct: null,
  min_oi: null,
  max_daily_loss_pct: null,
  wire_risk_infra: false,
};

let cfgData: Record<string, unknown> = { ...baseCfg };

const setCfgMutate = vi.fn((_vars: unknown, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.());
const runScanMutate = vi.fn();

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: cfgData }),
  useSetEngineConfig: () => ({ mutate: setCfgMutate, isPending: false }),
  usePatchEngineConfig: () => ({ mutate: setCfgMutate, isPending: false }),
  useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({ data: { rows: [] } }),
  useRunScan: () => ({ mutate: runScanMutate, isPending: false }),
  useStockRegistry: () => ({ data: [] }),
}));

// The vehicle profile panel is a large surface of its own; this suite is about
// where rules live and who they apply to.
vi.mock('../DirectionalModePanel', () => ({ DirectionalModePanel: () => <div>Vehicle profile</div> }));

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <TradeRulesPanel />
    </QueryClientProvider>,
  );
}

/** Open one of the lifecycle groups by its heading. */
function openStage(title: string | RegExp) {
  fireEvent.click(screen.getByText(title));
}

describe('TradeRulesPanel — lifecycle grouping', () => {
  beforeEach(() => {
    localStorage.clear();
    cfgData = { ...baseCfg };
    setCfgMutate.mockClear();
    runScanMutate.mockClear();
  });

  it('orders the rules the way a trade happens, from entry through to the safety net', () => {
    renderPanel();
    const stages = ['1 · Entry', '2 · Position size', '3 · Stop loss', '4 · Trailing stop',
      '5 · Target', '6 · Exit', '7 · Safety net'];
    stages.forEach((stage) => expect(screen.getByText(stage)).toBeInTheDocument());
  });

  it('keeps the expiry square-off input and patches it WITHOUT a rescan', () => {
    renderPanel();
    openStage('6 · Exit');
    const input = screen.getByTestId('expiry-squareoff-input') as HTMLInputElement;
    expect(input.value).toBe('1');
    fireEvent.change(input, { target: { value: '2' } });

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ expiry_square_off_days: 2 }),
      expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('keeps the time-stop input (opt-in, default 0) and patches without a rescan', () => {
    renderPanel();
    openStage('6 · Exit');
    const input = screen.getByTestId('time-stop-input') as HTMLInputElement;
    expect(input.value).toBe('0');
    fireEvent.change(input, { target: { value: '48' } });

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ time_stop_bars: 48 }),
      expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('keeps the late-entry guard and patches without a rescan', () => {
    renderPanel();
    const input = screen.getByTestId('block-entry-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '15' } });

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ block_entry_minutes_before_close: 15 }),
      expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('sets the liquidity guards, without a rescan', () => {
    renderPanel();
    fireEvent.change(screen.getByTestId('max-spread-input'), { target: { value: '5' } });
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ max_spread_pct: 5 }), expect.anything(),
    );
    fireEvent.change(screen.getByTestId('min-oi-input'), { target: { value: '100' } });
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ min_oi: 100 }), expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('clears a liquidity guard back to off when the field is emptied', () => {
    // Seeded BEFORE render: a controlled input already showing "" cannot be
    // "cleared" again, so the change event would never fire.
    cfgData = { ...baseCfg, max_spread_pct: 5 };
    renderPanel();
    const spread = screen.getByTestId('max-spread-input') as HTMLInputElement;
    expect(spread.value).toBe('5');
    fireEvent.change(spread, { target: { value: '' } });
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ max_spread_pct: null }), expect.anything(),
    );
  });

  it('sets the daily-loss breaker, without a rescan', () => {
    renderPanel();
    openStage('7 · Safety net');
    fireEvent.change(screen.getByTestId('daily-loss-input'), { target: { value: '2' } });
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ max_daily_loss_pct: 2 }), expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('clears the daily-loss breaker back to off when emptied', () => {
    cfgData = { ...baseCfg, max_daily_loss_pct: 2 };
    renderPanel();
    openStage('7 · Safety net');
    const input = screen.getByTestId('daily-loss-input') as HTMLInputElement;
    expect(input.value).toBe('2');
    fireEvent.change(input, { target: { value: '' } });
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ max_daily_loss_pct: null }), expect.anything(),
    );
  });
});

describe('TradeRulesPanel — manual / automatic applicability', () => {
  beforeEach(() => {
    localStorage.clear();
    cfgData = { ...baseCfg };
    setCfgMutate.mockClear();
    runScanMutate.mockClear();
  });

  it('labels expiry square-off and the time stop as applying to manual trades too', () => {
    // Regression coverage for a real mislabel: both iterate the whole position
    // registry (service.py:783, :812), which includes hand-placed orders armed
    // by manual protection — yet they used to sit under a heading that said
    // "Advanced auto-execution guards".
    renderPanel();
    openStage('6 · Exit');
    const label = screen.getByText('Expiry square-off').closest('div');
    expect(label).toHaveTextContent('MANUAL + AUTO');
    expect(screen.getByText('Time stop').closest('div')).toHaveTextContent('MANUAL + AUTO');
  });

  it('labels the sizing and entry filters as automatic-only', () => {
    renderPanel();
    expect(screen.getByText('Minimum ADX').closest('div')).toHaveTextContent('AUTO');
    openStage('2 · Position size');
    expect(screen.getByText('Risk-based sizing').closest('div')).toHaveTextContent('AUTO');
  });

  it('labels hand-placed order protection as manual-only', () => {
    renderPanel();
    expect(
      screen.getByText('Protect orders I place by hand').closest('div'),
    ).toHaveTextContent('MANUAL');
  });

  it('hides automatic-only rules when the scope filter is set to Manual', () => {
    renderPanel();
    // Present under the default "All rules" scope…
    expect(screen.getByTestId('block-entry-input')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Manual' }));

    // …gone once the user asks only about the orders they place themselves.
    expect(screen.queryByTestId('block-entry-input')).not.toBeInTheDocument();
    expect(screen.queryByTestId('daily-loss-input')).not.toBeInTheDocument();
    // Rules that genuinely bite on a manual trade stay.
    expect(screen.getByRole('switch', { name: /protect orders i place by hand/i })).toBeInTheDocument();
    expect(screen.getByTestId('expiry-squareoff-input')).toBeInTheDocument();
  });

  it('hides the manual-only protection switch when the scope filter is set to Automatic', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Automatic' }));

    expect(screen.queryByRole('switch', { name: /protect orders i place by hand/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('daily-loss-input')).toBeInTheDocument();
  });

  it('remembers the chosen scope', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Manual' }));
    expect(localStorage.getItem('kite_trade_rules_scope')).toBe('manual');
  });
});

describe('TradeRulesPanel — protection', () => {
  beforeEach(() => {
    localStorage.clear();
    cfgData = { ...baseCfg };
    setCfgMutate.mockClear();
    runScanMutate.mockClear();
  });

  it('toggles hand-placed order protection, which had no coverage before', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('switch', { name: /protect orders i place by hand/i }));

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ protect_manual_orders: false }),
      expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('changes the protection mode without a rescan', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Broker' }));

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ stop_mode: 'broker' }),
      expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('points at the owning engine for the trail and the exit rule rather than duplicating them', () => {
    renderPanel();
    openStage('4 · Trailing stop');
    openStage('6 · Exit');
    const pointers = screen.getAllByRole('button', { name: /Change in SuperTrend/ });
    expect(pointers.length).toBeGreaterThanOrEqual(2);
  });
});
