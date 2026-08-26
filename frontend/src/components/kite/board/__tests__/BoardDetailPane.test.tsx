/**
 * The shared detail page, and the label that opens it.
 *
 * The page renders from BoardSignal alone, so what these tests really pin is
 * that an engine gets a detail page by having an adapter — no per-engine
 * component, no second fetch.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('../../../../hooks/useKite', () => ({ useKiteQuote: () => ({ data: {} }) }));
vi.mock('../../AdaptiveEdgePositionCalculator', () => ({
  AdaptiveEdgePositionCalculator: (p: Record<string, unknown>) => (
    <div data-testid="calc">calc {String(p.tradingsymbol)} entry {String(p.defaultEntryPrice)} state {String(p.exitState)}</div>
  ),
}));

import { BoardDetailPane } from '../BoardDetailPane';
import { SignalBoard } from '../SignalBoard';
import type { BoardSignal } from '../boardTypes';

const NOW = Date.UTC(2026, 7, 21, 5, 0);

function sig(over: Partial<BoardSignal> = {}): BoardSignal {
  return {
    id: 'a', engine: 'adaptive_edge', underlying: 'TCS',
    instrument: {
      symbol: 'TCS26AUG3200CE', exchange: 'NFO', kind: 'option', optionType: 'CE',
      strike: 3200, expiry: '2026-08-27', lotSize: 175, quoteKey: 'NFO:TCS26AUG3200CE',
    },
    direction: 'long', status: 'running', atMs: NOW,
    levels: { ltp: 62, entry: 58, stop: 40, trail: 51, target: 94, exit: null },
    sizing: { lots: 2, quantity: 350, atRiskInr: 6300, deployedInr: 20300 },
    score: 85, reason: null,
    sections: [{ title: 'Spot microstructure & order flow', layout: 'tiles', stats: [{ label: 'POC anchor', value: '₹3195' }] }],
    ...over,
  };
}

describe('BoardDetailPane', () => {
  it('identifies the signal without needing another request', () => {
    render(<BoardDetailPane signal={sig()} onClose={() => {}} />);
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('TCS');
    expect(screen.getByText('NFO:TCS26AUG3200CE')).toBeInTheDocument();
    expect(screen.getByText('CE · LONG')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
  });

  it('lays out the whole price ladder, keeping stop and trail apart', () => {
    render(<BoardDetailPane signal={sig()} onClose={() => {}} />);
    expect(screen.getByText('Stop')).toBeInTheDocument();
    expect(screen.getByText('Trailing stop')).toBeInTheDocument();
    expect(screen.getByText('40.00')).toBeInTheDocument();
    expect(screen.getByText('51.00')).toBeInTheDocument();
  });

  it('states reward against risk only when all three levels are real', () => {
    // (94 - 58) / (58 - 40) = 2.00
    render(<BoardDetailPane signal={sig()} onClose={() => {}} />);
    expect(screen.getByText('2.00R')).toBeInTheDocument();
  });

  it('omits the ratio rather than computing one from a partial ladder', () => {
    render(<BoardDetailPane signal={sig({ levels: { ltp: 62, entry: 58, stop: 40, trail: null, target: null, exit: null } })} onClose={() => {}} />);
    expect(screen.queryByText(/\dR$/)).not.toBeInTheDocument();
  });

  it('says a signal is not sized rather than implying a position', () => {
    render(<BoardDetailPane signal={sig({ sizing: { lots: null, quantity: null, atRiskInr: null, deployedInr: null } })} onClose={() => {}} />);
    expect(screen.getByText('not sized')).toBeInTheDocument();
  });

  it('renders the engine’s own sections verbatim', () => {
    render(<BoardDetailPane signal={sig()} onClose={() => {}} />);
    expect(screen.getByText('Spot microstructure & order flow')).toBeInTheDocument();
    expect(screen.getByText('POC anchor')).toBeInTheDocument();
  });

  it('hands a weakening position to the calculator as an exit', () => {
    // The model has already called EXIT; the order surface should not open
    // as though the trade were being entered.
    render(<BoardDetailPane signal={sig({ status: 'weakening' })} onClose={() => {}} />);
    expect(screen.getByTestId('calc')).toHaveTextContent('state EXIT');
  });

  it('shows an error reason as an error, not as a note', () => {
    const { container } = render(<BoardDetailPane signal={sig({ status: 'error', reason: 'no instrument' })} onClose={() => {}} />);
    const note = screen.getByText('no instrument');
    expect(container.contains(note)).toBe(true);
    expect(note.getAttribute('style')).toMatch(/--k-red/);
  });

  it('closes', () => {
    const onClose = vi.fn();
    render(<BoardDetailPane signal={sig()} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: 'Close detail' }));
    expect(onClose).toHaveBeenCalled();
  });
});

describe('the instrument label on a board row', () => {
  const show = (onOpenDetail?: (s: BoardSignal) => void) =>
    render(
      <SignalBoard signals={[sig()]} openId={null} onToggle={() => {}} nowMs={NOW} onOpenDetail={onOpenDetail} />,
    );

  it('stays plain text when no detail page is offered', () => {
    show();
    expect(screen.queryByRole('button', { name: /Open TCS detail/ })).not.toBeInTheDocument();
  });

  it('opens the detail page without also expanding the row', () => {
    // The row expands on click too, so the label must stop the event or one
    // gesture would do two things.
    const onOpenDetail = vi.fn();
    const onToggle = vi.fn();
    render(<SignalBoard signals={[sig()]} openId={null} onToggle={onToggle} nowMs={NOW} onOpenDetail={onOpenDetail} />);
    fireEvent.click(screen.getByRole('button', { name: /Open TCS detail/ }));
    expect(onOpenDetail).toHaveBeenCalledWith(expect.objectContaining({ id: 'a' }));
    expect(onToggle).not.toHaveBeenCalled();
  });
});
