/**
 * The ATM Premium Imbalance lines in the operator's terminal.
 *
 * This strategy makes one decision a day in the first seconds of the session, so
 * the terminal is where an operator actually watches it think. A backend event
 * whose `kind` the terminal does not recognise renders as an unlabelled line, so
 * the mapping is worth pinning.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';

const events = [
  { ts_ms: 1_787_283_840_000, kind: 'api_replay',
    message: 'replaying 2026-08-21 at 60x — 40 contracts, fixed point target.' },
  { ts_ms: 1_787_283_841_000, kind: 'api_waiting',
    message: "no trade — a quote traded before today's open" },
  { ts_ms: 1_787_283_900_000, kind: 'api_signal',
    message: 'CE 584.90 | PE 267.60 | diff 317.30 → buy the PE' },
  { ts_ms: 1_787_283_901_000, kind: 'api_entry',
    message: 'BUY 40 PE @ limit 268.65 (attempt 1)' },
  { ts_ms: 1_787_283_902_000, kind: 'api_filled',
    message: 'filled 40 PE @ 268.65 — target 283.65' },
  { ts_ms: 1_787_283_903_000, kind: 'api_stop',
    message: 'stop 293.99 (peak 319.55, entry 268.65)' },
  { ts_ms: 1_787_283_904_000, kind: 'api_exit',
    message: 'SELL 40 PE @ limit 287.35 — target_hit' },
  { ts_ms: 1_787_283_905_000, kind: 'api_done',
    message: 'closed PE 40 @ 287.35 — +18.70 pts, P&L ₹+748.00 (target_hit)' },
  { ts_ms: 1_787_283_906_000, kind: 'api_halt',
    message: 'halted — premium_at_risk_exceeded' },
];

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineActivity: () => ({ data: { events, scanning: false } }),
  useEngineServerLogs: () => ({ data: { logs: [] } }),
  useEngineStatus: () => ({ data: { scanning: false } }),
}));

import { EngineTerminal } from '../EngineTerminal';

describe('EngineTerminal — ATM Premium Imbalance', () => {
  it('labels every ATM event kind the backend emits', () => {
    // An unrecognised kind falls back to its raw name, so these assert the
    // mapping exists. Matched as a substring because the label shares its text
    // node with the glyph in front of it.
    const { container } = render(<EngineTerminal />);
    const rendered = container.textContent ?? '';
    for (const label of ['ATM REPLAY', 'ATM WAITING', 'ATM SIGNAL', 'ATM ENTRY',
                         'ATM FILLED', 'ATM STOP', 'ATM EXIT', 'ATM DONE', 'ATM HALT']) {
      expect(rendered, `${label} should be labelled, not rendered bare`).toContain(label);
    }
    // and none of them fell through to the raw kind
    expect(rendered).not.toContain('API_');
  });

  it('shows the premium comparison the decision was made on', () => {
    render(<EngineTerminal />);
    expect(screen.getByText(/CE 584.90 \| PE 267.60 \| diff 317.30 → buy the PE/))
      .toBeInTheDocument();
  });

  it('shows the refusal in plain language', () => {
    render(<EngineTerminal />);
    expect(screen.getByText(/a quote traded before today's open/)).toBeInTheDocument();
  });

  it('shows where a trailing stop has moved to', () => {
    render(<EngineTerminal />);
    expect(screen.getByText(/stop 293.99 \(peak 319.55, entry 268.65\)/)).toBeInTheDocument();
  });

  it('shows the result with points and rupees', () => {
    render(<EngineTerminal />);
    expect(screen.getByText(/\+18.70 pts, P&L ₹\+748.00/)).toBeInTheDocument();
  });
});
