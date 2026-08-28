/**
 * The settings panel.
 *
 * Thresholds are judgement from one motivating chain, not a calibrated sample.
 * The panel has to say so next to the controls, and it must not invent a
 * paper-only lock that the code no longer has.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render as rtlRender, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { OiWallFlowSettings } from '../OiWallFlowSettings';

function render(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return rtlRender(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

let cfgQuery: any;
let updateState: any;

vi.mock('../../hooks/useOiWallFlow', () => ({
  useOiWallFlowConfig: () => cfgQuery,
  useUpdateOiWallFlow: () => updateState,
}));

const DEFAULTS = {
  enabled: true,
  scan_indices: ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE'] as string[],
  scan_stocks: [] as string[],
  scan_all_stocks: true, stock_contracts: true,
  oi_chg_deadband_pct: 0.5, ltp_chg_deadband_pct: 0.5, atm_window_strikes: 2,
  min_bias_score: 3, prefer_wall_strike: true, skip_atm: true,
  expiry_selection: 'nearest', expiry_dte_min: 1, expiry_dte_max: 45,
  avoid_expiry_day: true, min_option_oi: 100, min_option_premium: 10,
  scan_expiries_indices: ['weekly', 'monthly'], scan_expiries_stocks: ['monthly'],
  scan_weekly_series_indices: [0, 1, 2, 3], scan_monthly_series_indices: [0, 1],
  scan_monthly_series_stocks: [0, 1],
  stop_premium_pct: 40, target_premium_pct: 50, target_2_premium_pct: 100,
  wall_invalidation: true, stop_mode: 'both',
  session_start: '09:20', session_end: '15:15', scan_interval_seconds: 300,
  lot_size: 1, lots: 1, max_premium_at_risk_inr: 20000,
  max_concurrent_positions: 1, max_new_trades_per_day: 1,
  daily_loss_limit_inr: 15000, descale_after_losses: 3, rescale_after_wins: 2,
  data_source: 'kite',
};

const STRATEGY = {
  id: 'oi_wall_flow', name: 'OI Wall Flow', contract_version: 'A320.1',
  tagline: 'Buy the first-resistance CE (or first-support PE) the chain is writing.',
  how_it_works: 'Reads one expiry’s option chain the way a desk does.',
  provenance: 'Motivated by the BSE Ltd 29-Sep-2026 chain.',
  validated: false, enabled: true,
  calibrated_fields: [] as string[],
  judgement_fields: ['oi_chg_deadband_pct', 'stop_premium_pct', 'min_bias_score'],
  calibration: {
    oi_chg_deadband_pct: '0.5 — noise floor; a 0.00% print is not a buildup',
    stop_premium_pct: '40.0 — premium cut that killed the BSE 3500 CE thesis',
    min_bias_score: '3.0 — three confirming flow votes before a trade',
    prefer_wall_strike: 'True — buy the wall, not ATM, when the wall is first OTM',
    min_option_premium: '10.0 — below this the 0.05 tick is a >0.5% quantum',
    avoid_expiry_day: 'True — OI on expiry day is settlement, not positioning',
  },
  headline_finding: 'Thresholds are judgement from one motivating chain, not a calibrated sample.',
  what_to_do: 'Trust the wall and the near-ATM flow on the row.',
  evidence: 'BSE Ltd 29-Sep-2026, spot 3392.50: the engine must arm 3500 CE.',
};

beforeEach(() => {
  cfgQuery = {
    isLoading: false,
    data: {
      strategy: STRATEGY,
      config: { ...DEFAULTS },
      defaults: { ...DEFAULTS },
      vocabularies: { scan_stocks: ['RELIANCE', 'HDFCBANK'],
                      expiry_selection: ['any', 'monthly', 'nearest', 'weekly'] },
      research_only: {},
      warnings: [],
    },
  };
  updateState = { mutate: vi.fn(), isPending: false };
});

describe('OiWallFlowSettings', () => {
  it('states the finding before any control', () => {
    render(<OiWallFlowSettings />);
    expect(screen.getByText(/Not validated/)).toBeTruthy();
    expect(screen.getByText(/judgement from one motivating chain/)).toBeTruthy();
  });

  it('carries the judgement next to each threshold', () => {
    render(<OiWallFlowSettings />);
    const text = document.body.textContent ?? '';
    expect(text).toContain('Judgement:');
    expect(text).toContain('BSE 3500 CE');
  });

  it('does not send anything until the draft is applied', () => {
    render(<OiWallFlowSettings />);
    fireEvent.click(screen.getByRole('switch', { name: /oi wall flow engine/i }));
    expect(updateState.mutate).not.toHaveBeenCalled();
  });

  it('applies the whole draft when asked', () => {
    render(<OiWallFlowSettings />);
    fireEvent.click(screen.getByRole('switch', { name: /oi wall flow engine/i }));
    const apply = screen.getAllByRole('button')
      .find((b) => /apply/i.test(b.textContent ?? ''));
    expect(apply).toBeTruthy();
    fireEvent.click(apply!);
    expect(updateState.mutate).toHaveBeenCalledTimes(1);
    expect(updateState.mutate.mock.calls[0][0].enabled).toBe(false);
  });

  it('shows a loading state rather than an empty form', () => {
    cfgQuery = { isLoading: true, data: undefined };
    render(<OiWallFlowSettings />);
    expect(screen.getByText(/Loading strategy settings/)).toBeTruthy();
  });
});

describe('OiWallFlowSettings — structure and terminology', () => {
  it('presents Instruments before Contracts, like every other engine', () => {
    render(<OiWallFlowSettings />);
    const text = document.body.textContent ?? '';
    const instruments = text.indexOf('Instruments');
    const contracts = text.indexOf('Contracts');
    expect(instruments).toBeGreaterThan(-1);
    expect(contracts).toBeGreaterThan(instruments);
    expect(text).not.toContain('Universe');
  });

  it('opens the Contracts section rather than hiding it behind a disclosure', () => {
    render(<OiWallFlowSettings />);
    const heading = [...document.querySelectorAll('summary')]
      .find((el) => /Contracts/.test(el.textContent ?? ''));
    expect(heading).toBeTruthy();
    expect((heading!.closest('details') as HTMLDetailsElement).open).toBe(true);
  });

  it('uses the shared contract vocabulary, not a private one', () => {
    render(<OiWallFlowSettings />);
    const text = document.body.textContent ?? '';
    for (const label of ['Expiry', 'Minimum days to expiry',
                         'Maximum days to expiry', 'Expiry day']) {
      expect(text).toContain(label);
    }
  });

  it('hosts the shared Option contracts picker', () => {
    render(<OiWallFlowSettings />);
    expect(document.body.textContent).toContain('Option contracts');
  });

  it('drafts an expiry-window change like any other field', () => {
    render(<OiWallFlowSettings />);
    fireEvent.click(screen.getByRole('switch', { name: /avoid expiry-day entries/i }));
    const apply = screen.getAllByRole('button')
      .find((b) => /apply/i.test(b.textContent ?? ''));
    fireEvent.click(apply!);
    expect(updateState.mutate).toHaveBeenCalledTimes(1);
    expect(updateState.mutate.mock.calls[0][0].avoid_expiry_day).toBe(false);
  });
});

describe('OiWallFlowSettings — a renamed section is a different section', () => {
  beforeEach(() => localStorage.clear());

  it('still honours a choice made against its own key', () => {
    localStorage.setItem('kite-settings-section:oiwf-instruments', '0');
    render(<OiWallFlowSettings />);
    const summary = [...document.querySelectorAll('summary')]
      .find((el) => /Instruments/.test(el.textContent ?? ''));
    expect((summary!.closest('details') as HTMLDetailsElement).open).toBe(false);
  });

  it('opens Contracts even when every other section was collapsed', () => {
    for (const k of ['oiwf-instruments', 'oiwf-chain', 'oiwf-exit', 'oiwf-risk']) {
      localStorage.setItem(`kite-settings-section:${k}`, '0');
    }
    render(<OiWallFlowSettings />);
    const summary = [...document.querySelectorAll('summary')]
      .find((el) => /Contracts/.test(el.textContent ?? ''));
    expect((summary!.closest('details') as HTMLDetailsElement).open).toBe(true);
  });
});

describe('OiWallFlowSettings — the finding reads as guidance, not a paper', () => {
  it('states the claim and shows the evidence in full', () => {
    render(<OiWallFlowSettings />);
    const text = document.body.textContent ?? '';
    expect(text).toContain('judgement from one motivating chain');
    expect(text).toContain('Trust the wall');
    expect(text).toContain('3500 CE');
  });

  it('no longer claims a paper-only lock that was never there', () => {
    render(<OiWallFlowSettings />);
    expect(document.body.textContent).not.toContain('paper-only');
  });
});
