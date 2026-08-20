import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { OrbFeedEntry } from '../../../utils/niftyOrbSignalAdapter';

const state = vi.hoisted(() => ({
  rows: [] as OrbFeedEntry[],
  loading: false,
  error: null as unknown,
  enabled: true as boolean | undefined,
  configLoading: false,
  setEnabled: vi.fn(),
  pending: false,
  setError: null as unknown,
}));

vi.mock('../../../hooks/useOrbSignals', () => ({
  useOrbSignals: () => ({ signals: state.rows, isLoading: state.loading, error: state.error }),
}));
vi.mock('../../../hooks/useOrbConfig', () => ({
  useOrbConfig: () => ({ data: { config: { enabled: state.enabled } }, isLoading: state.configLoading }),
  useSetOrbEnabled: () => ({ mutate: state.setEnabled, isPending: state.pending, error: state.setError }),
}));
const openSection = vi.hoisted(() => vi.fn());
vi.mock('../config/registry', () => ({ openSettingsSection: openSection }));
// The expansion pulls a live book and mounts the shared calculator; neither is
// under test here, and both would drag the whole Kite query surface in.
vi.mock('../../../hooks/useKite', () => ({ useKiteQuote: () => ({ data: {} }) }));
vi.mock('../AdaptiveEdgePositionCalculator', () => ({
  AdaptiveEdgePositionCalculator: (p: Record<string, unknown>) => (
    <div data-testid="sizing">sizing {String(p.tradingsymbol)} @ {String(p.defaultEntryPrice)} sl {String(p.defaultSl)} on {String(p.exchange)}</div>
  ),
}));

import { NiftyOrbSignalsFeed } from '../NiftyOrbSignalsFeed';

const entry = (over: Partial<OrbFeedEntry> = {}): OrbFeedEntry => ({
  id: over.underlying ?? 'r1', strategy: 'ORB', underlying: 'NIFTY', direction: 'long', state: 'SIGNAL',
  spot: 24050, orbHigh: 24012, orbLow: 23988, vwap: 24000, atr: 8, volumeRatio: 1.8,
  optionSymbol: 'NIFTY26AUG24000CE', optionStrike: 24000, optionType: 'CE', optionExpiry: '2026-08-27',
  optionPremium: 18, stopPremium: 14, targetPremium: 26, quantity: 150, riskInr: 187.5,
  maxLossInr: 2700, dataSource: 'kite', quoteAgeS: 3.2, reason: 'ORB high break + VWAP + momentum',
  delta: 0.577, gamma: 0.00088, thetaPerDay: -10.0, vegaPerPoint: 16.9, exchange: 'NFO', lotSize: 75,
  underlyingEntry: 24050, underlyingStop: 24040,
  timestamp: '2026-08-21T10:30:00+05:30', deltaIsEstimated: true, deltaSource: 'implied', impliedVol: 0.224,
  ...over,
});

function show(over: Partial<typeof state> = {}) {
  Object.assign(state, { rows: [], loading: false, error: null, enabled: true, configLoading: false, pending: false, setError: null }, over);
  return render(<NiftyOrbSignalsFeed />);
}

beforeEach(() => { state.setEnabled.mockClear(); openSection.mockClear(); });

describe('ORB feed — engine off', () => {
  it('says the engine is off rather than showing an empty list', () => {
    show({ enabled: false });
    expect(screen.getByText('ORB + VWAP is off')).toBeInTheDocument();
    expect(screen.getByText('NOT SCANNING')).toBeInTheDocument();
  });

  it('carries the switch, so the fix is one click away', () => {
    show({ enabled: false });
    fireEvent.click(screen.getByRole('button', { name: /Turn on ORB \+ VWAP/i }));
    expect(state.setEnabled).toHaveBeenCalledWith(true);
  });

  it('shows progress while the toggle is in flight', () => {
    show({ enabled: false, pending: true });
    expect(screen.getByRole('button', { name: /Turning on…/ })).toBeDisabled();
  });

  it('reports a failed enable beside the control', () => {
    show({ enabled: false, setError: new Error('database unavailable') });
    expect(screen.getByText(/Could not turn it on: database unavailable/)).toBeInTheDocument();
  });

  it('offers a route to the settings section', () => {
    show({ enabled: false });
    fireEvent.click(screen.getByRole('button', { name: /ORB settings/i }));
    expect(openSection).toHaveBeenCalledWith('orbOptions');
  });

  it('distinguishes "on but no underlyings" from "off"', () => {
    show({ enabled: true, rows: [] });
    expect(screen.getByText('ORB universe is off')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Choose underlyings/i })).toBeInTheDocument();
    // Nothing to turn on here — the engine is already running.
    expect(screen.queryByRole('button', { name: /Turn on/i })).not.toBeInTheDocument();
  });
});

describe('ORB feed — tradable setups', () => {
  it('counts tradable setups against everything scanned', () => {
    show({ rows: [entry({ underlying: 'NIFTY' }), entry({ underlying: 'SBIN', state: 'WATCHING', reason: 'regime is RANGE' })] });
    expect(screen.getByText(/tradable · 2 scanned/)).toBeInTheDocument();
  });

  it('carries the whole ticket on the row', () => {
    show({ rows: [entry()] });
    expect(screen.getByText('NIFTY26AUG24000CE', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('CE · LONG')).toBeInTheDocument();
    expect(screen.getByText('NFO')).toBeInTheDocument();
    ['LTP', 'Entry', 'SL', 'Exit', 'Qty', 'At risk'].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
    expect(screen.getByText('₹2,700')).toBeInTheDocument();
    expect(screen.getByText('150')).toBeInTheDocument();
  });

  it('shows the signal time and marks a stale quote', () => {
    show({ rows: [entry({ quoteAgeS: 42 })] });
    expect(screen.getByText(/· stale/)).toBeInTheDocument();
  });

  it('keeps candidates that did not fire out of the way', () => {
    // The board is a call to action; reasons are available but not in the path.
    show({ rows: [entry({ underlying: 'NIFTY' }), entry({ underlying: 'SBIN', state: 'WATCHING', reason: 'regime is RANGE' })] });
    expect(screen.queryByText('regime is RANGE')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /1 not signalling/ }));
    expect(screen.getByText('regime is RANGE')).toBeInTheDocument();
  });

  it('says so plainly when nothing is tradable', () => {
    show({ rows: [entry({ state: 'WATCHING', reason: 'outside entry window' })] });
    expect(screen.getByText(/No tradable ORB setup right now/)).toBeInTheDocument();
  });

  it('counts errored underlyings separately in the disclosure', () => {
    show({ rows: [entry({ underlying: 'NIFTY', state: 'WATCHING', reason: 'regime is RANGE' }), entry({ underlying: 'SBIN', state: 'ERROR', reason: 'no instrument' })] });
    expect(screen.getByRole('button', { name: /2 not signalling.*1 errored/ })).toBeInTheDocument();
  });

  it('calls out a scan that failed for everything', () => {
    show({ rows: [entry({ state: 'ERROR', reason: "'str' object has no attribute 'zerodha_token'" })] });
    expect(screen.getByText(/Scan failed for all 1 underlyings/)).toBeInTheDocument();
  });
});

describe('ORB feed — expanded setup', () => {
  it('keeps the detail collapsed until asked', () => {
    show({ rows: [entry()] });
    expect(screen.queryByTestId('sizing')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /NIFTY CE setup/ })).toHaveAttribute('aria-expanded', 'false');
  });

  it('hands the plan to the shared position calculator, which owns the Buy path', () => {
    show({ rows: [entry()] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY CE setup/ }));
    expect(screen.getByTestId('sizing')).toHaveTextContent('sizing NIFTY26AUG24000CE @ 18 sl 14 on NFO');
  });

  it('shows the book and the underlying setup', () => {
    show({ rows: [entry()] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY CE setup/ }));
    expect(screen.getByText('MARKET DEPTH')).toBeInTheDocument();
    expect(screen.getByText('UNDERLYING SETUP')).toBeInTheDocument();
    expect(screen.getByText('ORB high')).toBeInTheDocument();
  });

  it('says when depth is unavailable rather than rendering an empty ladder', () => {
    show({ rows: [entry()] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY CE setup/ }));
    expect(screen.getByText(/Depth unavailable/)).toBeInTheDocument();
  });

  it('opens one setup at a time', () => {
    show({ rows: [entry({ underlying: 'NIFTY' }), entry({ underlying: 'SBIN' })] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY CE setup/ }));
    fireEvent.click(screen.getByRole('button', { name: /SBIN CE setup/ }));
    expect(screen.getByRole('button', { name: /NIFTY CE setup/ })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByRole('button', { name: /SBIN CE setup/ })).toHaveAttribute('aria-expanded', 'true');
  });

  it('is keyboard operable', () => {
    show({ rows: [entry()] });
    const row = screen.getByRole('button', { name: /NIFTY CE setup/ });
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(row).toHaveAttribute('aria-expanded', 'true');
  });

  it('marks an assumed delta where the Greeks are shown', () => {
    show({ rows: [entry({ deltaSource: 'assumed', delta: 0.5, impliedVol: null })] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY CE setup/ }));
    expect(screen.getByText('0.500 assumed')).toBeInTheDocument();
  });

  it('shows solved Greeks without a caveat', () => {
    show({ rows: [entry()] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY CE setup/ }));
    expect(screen.getByText('0.577')).toBeInTheDocument();
    expect(screen.getByText('22.4%')).toBeInTheDocument();
    expect(screen.queryByText(/assumed/)).not.toBeInTheDocument();
  });
});
