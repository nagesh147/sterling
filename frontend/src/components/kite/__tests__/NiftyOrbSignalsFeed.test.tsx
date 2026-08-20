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

import { NiftyOrbSignalsFeed } from '../NiftyOrbSignalsFeed';

const entry = (over: Partial<OrbFeedEntry> = {}): OrbFeedEntry => ({
  id: over.underlying ?? 'r1', strategy: 'ORB', underlying: 'NIFTY', direction: 'long', state: 'SIGNAL',
  spot: 24050, orbHigh: 24012, orbLow: 23988, vwap: 24000, atr: 8, volumeRatio: 1.8,
  optionSymbol: 'NIFTY26AUG24000CE', optionStrike: 24000, optionType: 'CE', optionExpiry: '2026-08-27',
  optionPremium: 18, stopPremium: 14, targetPremium: 26, quantity: 150, riskInr: 187.5,
  maxLossInr: 2700, dataSource: 'kite', quoteAgeS: 3.2, reason: 'ORB high break + VWAP + momentum',
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

describe('ORB feed — rows', () => {
  it('summarises actionable against scanned', () => {
    show({ rows: [entry({ underlying: 'NIFTY' }), entry({ underlying: 'SBIN', state: 'WATCHING', reason: 'regime is RANGE' })] });
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText(/actionable · 2 scanned/)).toBeInTheDocument();
  });

  it('puts a live plan above the rejections', () => {
    show({ rows: [
      entry({ underlying: 'SBIN', state: 'WATCHING', reason: 'regime is RANGE' }),
      entry({ underlying: 'NIFTY' }),
    ] });
    const rows = screen.getAllByRole('button', { name: /NIFTY|SBIN/ });
    expect(rows[0]).toHaveAccessibleName(/NIFTY SIGNAL/);
  });

  it('shows the gate that stopped a non-signal on the row itself', () => {
    show({ rows: [entry({ state: 'WATCHING', reason: 'volume below confirmation threshold' })] });
    expect(screen.getByText('volume below confirmation threshold')).toBeInTheDocument();
  });

  it('flags a stale quote on the row', () => {
    show({ rows: [entry({ quoteAgeS: 42 })] });
    expect(screen.getByText('STALE')).toBeInTheDocument();
  });

  it('calls out a scan that failed for everything', () => {
    show({ rows: [entry({ state: 'ERROR', reason: "'str' object has no attribute 'zerodha_token'" })] });
    expect(screen.getByText(/Scan failed for all 1 underlyings/)).toBeInTheDocument();
  });
});

describe('ORB feed — expanded row', () => {
  it('keeps the detail collapsed until asked', () => {
    show({ rows: [entry()] });
    expect(screen.queryByText('UNDERLYING STRUCTURE')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /NIFTY/ })).toHaveAttribute('aria-expanded', 'false');
  });

  it('reveals structure, vehicle and risk on expand', () => {
    show({ rows: [entry()] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY/ }));
    expect(screen.getByText('UNDERLYING STRUCTURE')).toBeInTheDocument();
    expect(screen.getByText('EXECUTION VEHICLE')).toBeInTheDocument();
    expect(screen.getByText('RISK')).toBeInTheDocument();
    expect(screen.getByText('NIFTY26AUG24000CE')).toBeInTheDocument();
    // The premium at risk shows in both the row summary and the detail, and the
    // two must agree — an operator reading either should see the same number.
    expect(screen.getAllByText('₹2,700')).toHaveLength(2);
    expect(screen.getByText('22.4%')).toBeInTheDocument();        // implied vol
  });

  it('opens one row at a time', () => {
    show({ rows: [entry({ underlying: 'NIFTY' }), entry({ underlying: 'SBIN' })] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY/ }));
    expect(screen.getByRole('button', { name: /NIFTY/ })).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(screen.getByRole('button', { name: /SBIN/ }));
    expect(screen.getByRole('button', { name: /NIFTY/ })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByRole('button', { name: /SBIN/ })).toHaveAttribute('aria-expanded', 'true');
  });

  it('collapses when clicked again', () => {
    show({ rows: [entry()] });
    const row = screen.getByRole('button', { name: /NIFTY/ });
    fireEvent.click(row);
    fireEvent.click(row);
    expect(row).toHaveAttribute('aria-expanded', 'false');
  });

  it('is keyboard operable', () => {
    show({ rows: [entry()] });
    const row = screen.getByRole('button', { name: /NIFTY/ });
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(row).toHaveAttribute('aria-expanded', 'true');
  });

  it('labels an assumed delta as such, and an implied one plainly', () => {
    show({ rows: [entry({ deltaSource: 'assumed', impliedVol: null })] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY/ }));
    expect(screen.getByText('0.50 assumed')).toBeInTheDocument();
  });

  it('explains why a rejected candidate did not fire', () => {
    show({ rows: [entry({ state: 'WATCHING', reason: 'regime is RANGE', optionSymbol: null })] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY/ }));
    expect(screen.getByText('WHY IT DID NOT')).toBeInTheDocument();
    expect(screen.queryByText('EXECUTION VEHICLE')).not.toBeInTheDocument();
  });

  it('does not invent a delta for a candidate with no plan', () => {
    // The RISK block claimed "implied" for rows that never produced a trade.
    show({ rows: [entry({ state: 'WATCHING', reason: 'outside entry window', optionSymbol: null, maxLossInr: null, riskInr: null, deltaSource: null, impliedVol: null })] });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY/ }));
    expect(screen.queryByText('RISK')).not.toBeInTheDocument();
    expect(screen.queryByText('implied')).not.toBeInTheDocument();
    // The observable facts are still shown.
    expect(screen.getByText('DATA')).toBeInTheDocument();
    expect(screen.getByText('UNDERLYING STRUCTURE')).toBeInTheDocument();
  });
});
