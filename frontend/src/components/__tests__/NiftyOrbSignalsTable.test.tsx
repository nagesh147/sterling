import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { OrbFeedEntry } from '../../utils/niftyOrbSignalAdapter';

const signals = vi.hoisted(() => ({ rows: [] as OrbFeedEntry[], isLoading: false, error: null as unknown }));
vi.mock('../../hooks/useOrbSignals', () => ({
  useOrbSignals: () => ({ signals: signals.rows, isLoading: signals.isLoading, error: signals.error }),
}));

import { NiftyOrbSignalsTable } from '../NiftyOrbSignalsTable';

const entry = (over: Partial<OrbFeedEntry> = {}): OrbFeedEntry => ({
  id: over.underlying ?? 'row', strategy: 'ORB', underlying: 'NIFTY', direction: 'long',
  state: 'SIGNAL', spot: 24050, orbHigh: 24012, orbLow: 23988, vwap: 24000, atr: 8,
  volumeRatio: 1.8, optionSymbol: 'NIFTY26AUG24000CE', optionStrike: 24000, optionType: 'CE',
  optionExpiry: '2026-08-27', optionPremium: 18, stopPremium: 14, targetPremium: 26,
  quantity: 150, riskInr: 187.5, maxLossInr: 2700, dataSource: 'kite', quoteAgeS: 3.2,
  reason: 'ORB high break + VWAP + positive VWAP slope + momentum + volume',
  timestamp: '2026-08-21T10:30:00+05:30', deltaIsEstimated: false,
  deltaSource: 'implied', impliedVol: 0.224, ...over,
});

function show(rows: OrbFeedEntry[], state: Partial<typeof signals> = {}) {
  Object.assign(signals, { rows, isLoading: false, error: null }, state);
  return render(<NiftyOrbSignalsTable />);
}

describe('ORB signals table', () => {
  it('shows the full premium at risk next to the modelled stop risk', () => {
    show([entry()]);
    expect(screen.getByText('₹2700')).toBeInTheDocument();   // max loss
    expect(screen.getByText('₹188')).toBeInTheDocument();     // stop risk
    expect(screen.getByText('150')).toBeInTheDocument();
  });

  it('marks a plan whose delta was only assumed', () => {
    show([entry({ deltaSource: 'assumed', deltaIsEstimated: true, impliedVol: null })]);
    expect(screen.getByTitle(/Delta assumed 0\.50/i)).toBeInTheDocument();
  });

  it('does not caveat a delta solved from the traded premium', () => {
    // An implied delta is a measurement, not an assumption, so it carries no marker.
    show([entry({ deltaSource: 'implied', deltaIsEstimated: true, impliedVol: 0.224 })]);
    expect(screen.queryByTitle(/Delta assumed 0\.50/i)).not.toBeInTheDocument();
  });

  it('does not caveat a broker-supplied delta', () => {
    show([entry({ deltaSource: 'broker', deltaIsEstimated: false, impliedVol: null })]);
    expect(screen.queryByTitle(/Delta assumed 0\.50/i)).not.toBeInTheDocument();
  });

  it('summarises which gate is holding the universe back', () => {
    show([
      entry({ underlying: 'NIFTY', state: 'WATCHING', reason: 'volume below confirmation threshold' }),
      entry({ underlying: 'BANKNIFTY', state: 'WATCHING', reason: 'volume below confirmation threshold' }),
      entry({ underlying: 'RELIANCE', state: 'WATCHING', reason: 'regime is RANGE' }),
    ]);
    // The reason appears per-row too, so assert the summary chip specifically:
    // it carries the count beside the reason, which is what makes "why did
    // nothing fire" answerable at a glance.
    const chip = (text: string) =>
      screen.getAllByText((_, el) => el?.textContent?.trim() === text && el.tagName === 'SPAN');
    expect(chip('volume below confirmation threshold 2').length).toBeGreaterThan(0);
    expect(chip('regime is RANGE 1').length).toBeGreaterThan(0);
    expect(screen.getByText('0 actionable · 3 scanned')).toBeInTheDocument();
  });

  it('counts actionable rows separately from scanned rows', () => {
    show([entry({ underlying: 'NIFTY' }), entry({ underlying: 'BANKNIFTY', state: 'WATCHING', reason: 'regime is RANGE' })]);
    expect(screen.getByText('1 actionable · 2 scanned')).toBeInTheDocument();
  });

  it('flags a stale quote', () => {
    show([entry({ quoteAgeS: 42 })]);
    expect(screen.getByText('42.0s')).toBeInTheDocument();
  });

  it('says so when the feed is unavailable rather than showing an empty table', () => {
    show([], { error: new Error('scan failed') });
    expect(screen.getByText(/ORB signal feed unavailable: scan failed/)).toBeInTheDocument();
  });

  it('explains an empty universe', () => {
    show([]);
    expect(screen.getByText(/No configured underlyings are producing ORB signals/)).toBeInTheDocument();
  });
});
