import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { PortfolioPane } from '../PortfolioPane';
import { useOrderWindowStore } from '../../../store/useOrderWindowStore';
import { useKiteBasketStore } from '../../../store/useKiteBasketStore';

// Kite's /portfolio/holdings response includes t1_quantity — shares from a
// T+1 settlement that aren't sellable yet. TATASTEEL below has 40 of its 100
// shares still unsettled (60 sellable); INFY is fully settled (t1_quantity 0).
// (Symbols deliberately avoid a trailing "CE"/"PE" — InstrumentLabel's
// fallback formatter inserts a space before a trailing CE/PE assuming an
// options contract, e.g. "RELIANCE" → "RELIAN CE"; a pre-existing quirk
// unrelated to this task, just steered around here.)
const HOLDINGS = [
  { exchange: 'NSE', tradingsymbol: 'TATASTEEL', quantity: 100, t1_quantity: 40, average_price: 2400, last_price: 2450, pnl: 5000, product: 'CNC', day_change: 5, day_change_percentage: 0.2 },
  { exchange: 'NSE', tradingsymbol: 'INFY', quantity: 50, t1_quantity: 0, average_price: 1500, last_price: 1520, pnl: 1000, product: 'CNC', day_change: 2, day_change_percentage: 0.13 },
];

vi.mock('../../../hooks/useKite', () => ({
  useConvertKitePosition: () => ({ isPending: false, isError: false, isSuccess: false, mutate: vi.fn() }),
  useKiteHoldings: () => ({ data: HOLDINGS }),
  useKitePositions: () => ({ data: { net: [] } }),
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

function renderPane() {
  const qc = new QueryClient();
  render(
    <QueryClientProvider client={qc}>
      <PortfolioPane view="holdings" />
    </QueryClientProvider>
  );
}

function rowFor(symbol: string) {
  return screen.getAllByText(symbol).map((el) => el.closest('tr')).find(Boolean)!;
}

beforeEach(() => {
  useOrderWindowStore.setState({ isOpen: false, options: null });
  useKiteBasketStore.setState({ entries: [] });
});

describe('PortfolioPane holdings T1/settled distinction', () => {
  it('shows a T1 badge with the unsettled count for a holding with t1_quantity > 0, and no badge for a fully-settled holding', () => {
    renderPane();
    expect(screen.getByText('T1: 40')).toBeInTheDocument();
    expect(rowFor('INFY').textContent).not.toMatch(/T1:/);
  });

  it('caps the Sell handler quantity at the settled amount (quantity - t1_quantity)', () => {
    renderPane();
    const sellBtn = rowFor('TATASTEEL').querySelector('[title="Exit"]') as HTMLElement;
    fireEvent.click(sellBtn);
    expect(useOrderWindowStore.getState().options?.initialQty).toBe(60); // 100 - 40
  });

  it('does not cap the Sell handler quantity for a fully-settled holding', () => {
    renderPane();
    const sellBtn = rowFor('INFY').querySelector('[title="Exit"]') as HTMLElement;
    fireEvent.click(sellBtn);
    expect(useOrderWindowStore.getState().options?.initialQty).toBe(50);
  });

  it('caps the "Add to basket" quantity at the settled amount', () => {
    renderPane();
    const basketBtn = rowFor('TATASTEEL').querySelector('[title="Add to basket"]') as HTMLElement;
    fireEvent.click(basketBtn);
    expect(useKiteBasketStore.getState().entries[0]?.qty).toBe(60); // 100 - 40
  });
});
