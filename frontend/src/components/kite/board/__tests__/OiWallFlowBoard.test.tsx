/**
 * The scan control, the judgement banner, and Buy on an armed row.
 *
 * Thresholds were read off one motivating chain, not fitted to a sample, and
 * that has to be visible above the rows rather than only in a document. A
 * board that renders a confident-looking 3500 CE without it is the failure
 * mode.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render as rtlRender, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { OiWallFlowBoard } from '../OiWallFlowBoard';

function render(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return rtlRender(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

let snap: any = { data: undefined, isLoading: false, error: null };
let scanState: any = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
let armState: any = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
let snapshotArgs: unknown[] = [];

vi.mock('../../../../hooks/useOiWallFlow', () => ({
  useOiWallFlowSnapshot: (...args: unknown[]) => { snapshotArgs = args; return snap; },
  useOiWallFlowScan: () => scanState,
  useArmOiWallFlow: () => armState,
}));

vi.mock('../BoardTicket', () => ({ BoardTicket: () => <div>ticket</div> }));

const CONFIG = {
  enabled: true, skip_atm: true, prefer_wall_strike: true, min_bias_score: 3,
  stop_mode: 'both',
};

const STRATEGY = {
  id: 'oi_wall_flow', name: 'OI Wall Flow',
  headline_finding: 'Thresholds are judgement from one motivating chain, not a calibrated sample.',
  what_to_do: 'Trust the wall and the near-ATM flow on the row.',
  evidence: 'BSE Ltd 29-Sep-2026, spot 3392.50: the engine must arm 3500 CE and must not arm a PE.',
  calibration: {}, calibrated_fields: [], judgement_fields: ['stop_premium_pct'],
};

function row(over: any = {}) {
  return {
    id: 'BSE:2026-09-29', state: 'armed', at_ms: 1756360800000,
    underlying: 'BSE', spot: 3392.5, expiry: '2026-09-29', days_to_expiry: 32, reason: null,
    bias: {
      bias: 'bullish', score: 4.5, reasons: [],
      pcr_oi: 0.72, max_pain: 3400, put_wall: 3300, call_wall: 3500, atm_strike: 3400,
    },
    plan: {
      option_type: 'CE', strike: 3500, entry: 84.15, stop: 50.49, target: 126.23,
      target_2: 168.3, underlying_invalidation: 3300, lot_size: 200, quantity: 200,
      lots: 1, reason: 'first-resistance CE', tradingsymbol: 'BSE26SEP3500CE',
      instrument: {
        instrument_id: '1', tradingsymbol: 'BSE26SEP3500CE', option_type: 'CE',
        strike: 3500, expiry: '2026-09-29', lot_size: 200, tick_size: 0.05, exchange: 'NFO',
      },
    },
    instrument: {
      instrument_id: '1', tradingsymbol: 'BSE26SEP3500CE', option_type: 'CE',
      strike: 3500, expiry: '2026-09-29', lot_size: 200, tick_size: 0.05, exchange: 'NFO',
    },
    levels: { ltp: 84.15, entry: 84.15, stop: 50.49, trail: null, target: 126.23, exit: null },
    sizing: { lots: 1, quantity: 200, at_risk_inr: 6732, deployed_inr: 16830 },
    ...over,
  };
}

function data(over: any = {}) {
  return {
    strategy: STRATEGY, config: CONFIG, scan: {}, session: null,
    candidates: [], positions: [], orphan_positions: [], blockers: [],
    record: { trades: 0, wins: 0, losses: 0, win_rate: null, consecutive_losses: 0,
              consecutive_wins: 0, realised_inr: 0, day_realised_inr: 0, day: '',
              verdict: 'no realised trades yet' },
    mode: { is_paper: true, auto_execute: false, note: '' },
    universe: { underlyings: 14, sample: ['RELIANCE'] },
    ...over,
  };
}

beforeEach(() => {
  snap = { data: data(), isLoading: false, error: null };
  scanState = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
  armState = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
});

describe('OiWallFlowBoard', () => {
  it('leads with what the finding means and what to do about it', () => {
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    expect(screen.getByText('NOT VALIDATED')).toBeTruthy();
    expect(screen.getByText(/judgement from one motivating chain/)).toBeTruthy();
    expect(screen.getByText(/Trust the wall/)).toBeTruthy();
  });

  it('keeps the motivating chain off the banner and on a hover', () => {
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    expect(screen.queryByText(/3500 CE/)).toBeNull();
    const banner = screen.getByText('NOT VALIDATED').closest('[title]');
    expect(banner).toBeTruthy();
    expect(banner!.getAttribute('title')).toContain('3500 CE');
  });

  it('offers a scan and runs it', () => {
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    fireEvent.click(screen.getByRole('button', { name: /scan now/i }));
    expect(scanState.mutate).toHaveBeenCalled();
  });

  it('reads out every blocker rather than sitting silent', () => {
    snap.data = data({ blockers: ['this engine is switched off', 'universe is empty'] });
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    expect(screen.getByText('this engine is switched off')).toBeTruthy();
    expect(screen.getByText(/universe is empty/)).toBeTruthy();
  });

  it('shows the scan cost', () => {
    snap.data = data({
      scan: { underlyings: 17, chains: 14, scanned: 14, armed: 1, quoted: 420, total_seconds: 12 },
    });
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    expect(screen.getByText('17')).toBeTruthy();
    expect(document.body.textContent).toMatch(/1\s*armed of\s*14/);
  });

  it('does not poll while nothing is open', () => {
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    expect(snapshotArgs[1]).toBe(0);
  });

  it('renders an armed row', () => {
    snap.data = data({ candidates: [row()] });
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    expect(screen.getByText(/1 armed/)).toBeTruthy();
    expect(document.body.textContent).toContain('BSE');
    expect(document.body.textContent).toContain('3500');
  });

  it('lets the operator buy an armed row', () => {
    snap.data = data({ candidates: [row()] });
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    fireEvent.click(screen.getByRole('button', { name: /BSE CE Armed/i }));
    fireEvent.click(screen.getByRole('button', { name: /Buy 200 BSE26SEP3500CE/i }));
    expect(armState.mutate).toHaveBeenCalledWith('BSE:2026-09-29');
  });

  it('does not scan or buy while the engine is switched off', () => {
    snap.data = data({ config: { ...CONFIG, enabled: false }, candidates: [row()] });
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    expect(screen.getByRole('button', { name: /scan now/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /BSE CE Armed/i }));
    expect(screen.queryByRole('button', { name: /Buy 200 BSE26SEP3500CE/i })).toBeNull();
  });

  it('surfaces a refused entry instead of failing quietly', () => {
    armState.data = { ok: false, message: 'daily trade limit of 1 reached' };
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    expect(screen.getByText(/daily trade limit of 1 reached/)).toBeTruthy();
  });

  it('warns while size is de-scaled', () => {
    snap.data = data({
      record: { trades: 5, wins: 1, losses: 4, win_rate: 20, consecutive_losses: 3,
                consecutive_wins: 0, realised_inr: -8000, day_realised_inr: -8000,
                day: '2026-08-28', verdict: '1/5 winners' },
    });
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    expect(screen.getByText(/3 consecutive losses/)).toBeTruthy();
  });

  it('reports an error rather than an empty board', () => {
    snap = { data: undefined, isLoading: false, error: new Error('kite is down') };
    render(<OiWallFlowBoard nowMs={Date.now()} />);
    expect(screen.getByText(/kite is down/)).toBeTruthy();
  });
});
