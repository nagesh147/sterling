import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { PortfolioPane, ConvertControl } from '../PortfolioPane';

// ConvertControl converts a position between product types (MIS/CNC/NRML).
// This suite covers:
//  (1) the partial-quantity behavior added on top of the pre-existing
//      full-quantity-only convert action, exercised on the isolated
//      component (defaults to full qty, bounded [1, fullQty], mutate fires
//      with the entered — possibly partial — quantity only when in range);
//  (2) that the control is actually reachable from PortfolioPane's real
//      Positions row via a "Convert" toggle — this control had previously
//      been left unreachable (defined but never rendered) after an earlier
//      redesign dropped its call site, so a regression test for "is this
//      genuinely wired in" has standalone value here.
const mutate = vi.fn();

const NET_POSITIONS = [
  { exchange: 'NSE', tradingsymbol: 'INFY', product: 'MIS', quantity: 75, average_price: 2400, last_price: 2450, pnl: 500, multiplier: 1 },
  // Already-flat row, kept only to show its day's realized P&L (Task 13
  // precedent) — the Convert toggle must not appear for it.
  { exchange: 'NSE', tradingsymbol: 'WIPRO', product: 'MIS', quantity: 0, average_price: 400, last_price: 405, pnl: 25, multiplier: 1 },
];

vi.mock('../../../hooks/useKite', () => ({
  useConvertKitePosition: () => ({ isPending: false, isError: false, isSuccess: false, mutate }),
  useKiteHoldings: () => ({ data: [] }),
  useKitePositions: () => ({ data: { net: NET_POSITIONS } }),
  useKiteAuctions: () => ({ data: [] }),
  useInitiateHoldingsAuth: () => ({ isPending: false, mutate: vi.fn() }),
  useKiteLtp: () => ({ data: undefined }),
  usePlaceKiteOrder: () => ({ mutateAsync: vi.fn() }),
}));

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineOpenPositions: () => ({ data: { positions: [] }, isLoading: false }),
  useEngineSignals: () => ({ data: undefined }),
  useCloseEnginePosition: () => ({ mutate: vi.fn(), isPending: false }),
}));

beforeEach(() => {
  mutate.mockClear();
});

// ─── (1) Isolated component behavior ───────────────────────────────────────

const POSITION = { tradingsymbol: 'INFY', exchange: 'NSE', quantity: 75, product: 'MIS' };

function getQtyInput() {
  return screen.getByTitle('Max: 75') as HTMLInputElement;
}

function getConvertLink() {
  return screen.getByText('convert');
}

describe('ConvertControl partial-quantity conversion (isolated)', () => {
  it('defaults the quantity input to the full position size', () => {
    render(<ConvertControl p={POSITION} />);
    expect(getQtyInput().value).toBe('75');
  });

  it('sends the entered partial quantity (not the full quantity) on convert', () => {
    render(<ConvertControl p={POSITION} />);
    fireEvent.change(getQtyInput(), { target: { value: '30' } });
    fireEvent.click(getConvertLink());
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({
      tradingsymbol: 'INFY', exchange: 'NSE', quantity: 30, old_product: 'MIS',
    }));
  });

  it('disables convert (no mutate call) when quantity exceeds the full position size', () => {
    render(<ConvertControl p={POSITION} />);
    fireEvent.change(getQtyInput(), { target: { value: '999' } });
    fireEvent.click(getConvertLink());
    expect(mutate).not.toHaveBeenCalled();
    expect(getConvertLink()).toHaveStyle({ cursor: 'not-allowed' });
  });

  it('disables convert (no mutate call) when quantity is zero or emptied', () => {
    render(<ConvertControl p={POSITION} />);
    fireEvent.change(getQtyInput(), { target: { value: '' } });
    fireEvent.click(getConvertLink());
    expect(mutate).not.toHaveBeenCalled();
    expect(getConvertLink()).toHaveStyle({ cursor: 'not-allowed' });
  });

  it('re-enables convert once the quantity is corrected back into range', () => {
    render(<ConvertControl p={POSITION} />);
    fireEvent.change(getQtyInput(), { target: { value: '999' } });
    fireEvent.change(getQtyInput(), { target: { value: '50' } });
    fireEvent.click(getConvertLink());
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ quantity: 50 }));
  });
});

// ─── (2) Wired into the real Positions row ─────────────────────────────────

function renderPane() {
  const qc = new QueryClient();
  render(
    <QueryClientProvider client={qc}>
      <PortfolioPane view="positions" />
    </QueryClientProvider>
  );
}

function rowFor(symbol: string) {
  return screen.getAllByText(symbol).map((el) => el.closest('tr')).find(Boolean)!;
}

const TOGGLE_TITLE = 'Convert this MIS position to another product type';

describe('PortfolioPane Positions row → ConvertControl wiring', () => {
  it('is reachable from the real Positions row: clicking the Convert toggle reveals the qty input', () => {
    renderPane();
    const row = rowFor('INFY');
    const toggle = row.querySelector(`[title="${TOGGLE_TITLE}"]`) as HTMLElement;
    expect(toggle).toBeTruthy();
    fireEvent.click(toggle);
    expect(row.querySelector('[title="Max: 75"]')).toBeInTheDocument();
  });

  it('does not render the Convert toggle for an already-flat (quantity 0) row', () => {
    renderPane();
    const row = rowFor('WIPRO');
    expect(row.querySelector('[title^="Convert this"]')).toBeNull();
  });

  it('sends the entered partial quantity through convert.mutate when opened from the real row', () => {
    renderPane();
    const row = rowFor('INFY');
    fireEvent.click(row.querySelector(`[title="${TOGGLE_TITLE}"]`) as HTMLElement);
    fireEvent.change(row.querySelector('[title="Max: 75"]') as HTMLInputElement, { target: { value: '20' } });
    fireEvent.click(within(row).getByText('convert'));
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ tradingsymbol: 'INFY', quantity: 20 }));
  });

  it('closes the inline control via the × button, restoring the Chg% display', () => {
    renderPane();
    const row = rowFor('INFY');
    fireEvent.click(row.querySelector(`[title="${TOGGLE_TITLE}"]`) as HTMLElement);
    expect(row.querySelector('[title="Max: 75"]')).toBeInTheDocument();
    fireEvent.click(row.querySelector('[title="Close"]') as HTMLElement);
    expect(row.querySelector('[title="Max: 75"]')).toBeNull();
  });
});
