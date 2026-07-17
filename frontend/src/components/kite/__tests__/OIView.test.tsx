import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';

/**
 * OIView renders total OI and (baseline-relative) OI-change by strike.
 * Total OI is a real chain field; ΔOI is current OI minus a day baseline cached
 * in localStorage. These tests lock the stat/diff math for both modes.
 */

let mockData: any = null;
vi.mock('../../../hooks/useKiteOptionChain', () => ({
  useKiteOptionChain: () => ({ data: mockData }),
}));

import { OIView } from '../OIView';

// Mirror of OIView.istDateKey so we can build the exact localStorage key.
function istDateKey(): string {
  try { return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' }); }
  catch { return new Date().toISOString().slice(0, 10); }
}

const leg = (oi: number) => ({ oi, ltp: 1, iv: 1, delta: 0, theta: 0, vega: 0, gamma: 0, symbol: 'x' });
const EXP = '2026-07-24';

function chain() {
  return {
    underlying: 'NIFTY', spot: 24000, atm_strike: 24000, strike_step: 50,
    expiries: [{ date: EXP, dte: 6, label: '24 Jul' }],
    chain: {
      [EXP]: [
        { strike: 23950, isAtm: false, call: leg(12), put: leg(20) },
        { strike: 24000, isAtm: true, call: leg(30), put: leg(5) },
      ],
    },
  };
}

describe('OIView', () => {
  beforeEach(() => {
    mockData = chain();
    localStorage.clear();
  });

  it('total mode: sums Call/Put OI and computes PCR', () => {
    render(<OIView symbol="NSE:NIFTY" mode="total" />);
    // Call OI = 12 + 30 = 42.00 ; Put OI = 20 + 5 = 25.00 ; PCR = 25/42 = 0.60
    expect(screen.getByText('42.00')).toBeTruthy();
    expect(screen.getByText('25.00')).toBeTruthy();
    expect(screen.getByText('0.60')).toBeTruthy();
    expect(screen.getByText('24000')).toBeTruthy(); // ATM strike row
  });

  it('change mode: ΔOI = current − day baseline', () => {
    // Baseline: 24000 CE was 12 (now 30 → +18), 23950 CE was 12 (now 12 → 0).
    const key = `kiteOiBaseline:NIFTY:${EXP}:${istDateKey()}`;
    localStorage.setItem(key, JSON.stringify({
      at: 1_700_000_000_000,
      oi: { '23950': { ce: 12, pe: 20 }, '24000': { ce: 12, pe: 5 } },
    }));

    render(<OIView symbol="NSE:NIFTY" mode="change" />);
    // 24000 call built up +18.00; footer Call ΔOI total also +18.00.
    expect(screen.getAllByText('+18.00').length).toBeGreaterThan(0);
  });
});
