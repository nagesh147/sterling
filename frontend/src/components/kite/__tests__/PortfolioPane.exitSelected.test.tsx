import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { PortfolioPane } from '../PortfolioPane';

const mockMutateAsync = vi.fn();
const mockNotifyOrder = vi.fn();

vi.mock('../../../store/useKiteNotifications', () => ({
  notifyOrder: (...args: any[]) => mockNotifyOrder(...args),
}));

const NET_POSITIONS = [
  { exchange: 'NSE', tradingsymbol: 'INFY', product: 'MIS', quantity: 10, average_price: 1500, last_price: 1510, pnl: 100, multiplier: 1 },
  { exchange: 'NSE', tradingsymbol: 'TCS', product: 'CNC', quantity: -5, average_price: 3600, last_price: 3590, pnl: 50, multiplier: 1 },
];

// useKitePositions() feeds the component's initial render; exitSelected()'s
// staleness guard instead re-reads live data straight out of the react-query
// cache (see renderWithClient below). Mutable so each test can render with
// its own row set (e.g. to add an already-flat row) without a fresh vi.mock.
let mockPositionsNet: any[] = NET_POSITIONS;

vi.mock('../../../hooks/useKite', () => ({
  useConvertKitePosition: () => ({ isPending: false, isError: false, isSuccess: false, mutate: vi.fn() }),
  useKiteHoldings: () => ({ data: [] }),
  useKitePositions: () => ({ data: { net: mockPositionsNet } }),
  useKiteAuctions: () => ({ data: [] }),
  useInitiateHoldingsAuth: () => ({ isPending: false, mutate: vi.fn() }),
  useKiteLtp: () => ({ data: undefined }),
  usePlaceKiteOrder: () => ({ mutateAsync: mockMutateAsync }),
}));

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineOpenPositions: () => ({ data: { positions: [] }, isLoading: false }),
  useEngineSignals: () => ({ data: undefined }),
  useCloseEnginePosition: () => ({ mutate: vi.fn(), isPending: false }),
}));

// exitSelected() reads the live broker snapshot straight out of the
// react-query cache (queryKey ['kite-positions']) immediately before firing
// each leg — independent of the mocked useKitePositions() hook above, which
// only feeds the component's initial render. Tests that exercise the
// staleness guard mutate this cache directly mid-loop to simulate a leg
// closing/shrinking elsewhere (GTT, auto-exec, another device) while the
// sequential loop is still awaiting an earlier leg.
function renderWithClient(net: any[] = NET_POSITIONS) {
  mockPositionsNet = net;
  const qc = new QueryClient();
  qc.setQueryData(['kite-positions'], { net });
  render(
    <QueryClientProvider client={qc}>
      <PortfolioPane view="positions" />
    </QueryClientProvider>
  );
  return qc;
}

beforeEach(() => {
  mockMutateAsync.mockReset();
  mockNotifyOrder.mockReset();
  mockPositionsNet = NET_POSITIONS;
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});

describe('PortfolioPane exitSelected', () => {
  it('does not show the Exit Selected button when nothing is selected', () => {
    renderWithClient();
    expect(screen.queryByText(/Exit Selected/)).not.toBeInTheDocument();
  });

  it('shows the Exit Selected button with a count once rows are selected, and fires one MARKET order per selected leg sequentially', async () => {
    mockMutateAsync.mockResolvedValue({ order_id: 'o1' });
    renderWithClient();

    const checkboxes = screen.getAllByRole('checkbox');
    // checkboxes[0] is "select all"; row checkboxes follow in table order (INFY, TCS).
    fireEvent.click(checkboxes[1]); // INFY

    expect(screen.getByText('Exit Selected (1)')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Exit Selected (1)'));

    expect(window.confirm).toHaveBeenCalledWith('Exit 1 selected position (INFY) at market price?');
    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1));
    expect(mockMutateAsync).toHaveBeenCalledWith(expect.objectContaining({
      tradingsymbol: 'INFY', exchange: 'NSE', transaction_type: 'SELL', quantity: 10,
      order_type: 'MARKET', product: 'MIS', variety: 'regular', validity: 'DAY',
    }));

    // Selection is cleared once the bulk exit completes.
    await waitFor(() => expect(screen.queryByText(/Exit Selected/)).not.toBeInTheDocument());
  });

  it('does not place any orders when the confirm dialog is dismissed', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderWithClient();

    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    fireEvent.click(screen.getByText('Exit Selected (1)'));

    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  it('disables the checkbox for an already-flat (quantity 0) row so it cannot be selected for exit', () => {
    renderWithClient([
      ...NET_POSITIONS,
      { exchange: 'NSE', tradingsymbol: 'WIPRO', product: 'MIS', quantity: 0, average_price: 400, last_price: 405, pnl: 25, multiplier: 1 },
    ]);
    // WIPRO's text appears both in the positions table row and in the
    // Breakdown section below it — find the one inside an actual <tr>.
    const wiproRow = screen.getAllByText('WIPRO').map((el) => el.closest('tr')).find(Boolean)!;
    const wiproCheckbox = wiproRow.querySelector('input[type="checkbox"]') as HTMLInputElement;
    expect(wiproCheckbox).toBeDisabled();
  });

  it('skips a leg that has gone flat elsewhere between click and its turn in the sequential loop, instead of firing a stale-sized order', async () => {
    let resolveFirst: (v: any) => void = () => {};
    mockMutateAsync.mockImplementationOnce(() => new Promise((r) => { resolveFirst = r; }));
    const qc = renderWithClient();

    fireEvent.click(screen.getAllByRole('checkbox')[1]); // INFY
    fireEvent.click(screen.getAllByRole('checkbox')[2]); // TCS
    fireEvent.click(screen.getByText('Exit Selected (2)'));

    // First leg (INFY) is in flight.
    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1));
    expect(mockMutateAsync).toHaveBeenCalledWith(expect.objectContaining({ tradingsymbol: 'INFY' }));

    // While INFY's order is still pending, a GTT/auto-exec/another device
    // closes TCS out from under this loop.
    qc.setQueryData(['kite-positions'], {
      net: [NET_POSITIONS[0], { ...NET_POSITIONS[1], quantity: 0 }],
    });
    resolveFirst({ order_id: 'o1' });

    // The loop must re-check TCS's live quantity before firing its leg, see
    // it's now flat, and skip it — never fire a second mutateAsync call for it.
    await waitFor(() => expect(screen.queryByText(/Exit Selected/)).not.toBeInTheDocument());
    expect(mockMutateAsync).toHaveBeenCalledTimes(1);

    // The user gets a visible notification that a leg was silently skipped
    // (gone flat OR converted to a different product — both look the same
    // to the live lookup), instead of the button just reverting with no signal.
    expect(mockNotifyOrder).toHaveBeenCalledWith(expect.objectContaining({
      kind: 'info',
      message: expect.stringContaining('Exited 1 of 2'),
    }));
  });

  it('does not surface a skip notification when every selected leg is exited', async () => {
    mockMutateAsync.mockResolvedValue({ order_id: 'o1' });
    renderWithClient();

    fireEvent.click(screen.getAllByRole('checkbox')[1]); // INFY
    fireEvent.click(screen.getByText('Exit Selected (1)'));

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.queryByText(/Exit Selected/)).not.toBeInTheDocument());
    expect(mockNotifyOrder).not.toHaveBeenCalled();
  });

  it('resizes a leg to its current live quantity if it shrank (partial close elsewhere) since selection', async () => {
    let resolveFirst: (v: any) => void = () => {};
    mockMutateAsync
      .mockImplementationOnce(() => new Promise((r) => { resolveFirst = r; }))
      .mockImplementationOnce(() => Promise.resolve({ order_id: 'o2' }));
    const qc = renderWithClient();

    fireEvent.click(screen.getAllByRole('checkbox')[1]); // INFY
    fireEvent.click(screen.getAllByRole('checkbox')[2]); // TCS
    fireEvent.click(screen.getByText('Exit Selected (2)'));

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1));

    // TCS partially closed elsewhere: -5 -> -2, while INFY's order is still pending.
    qc.setQueryData(['kite-positions'], {
      net: [NET_POSITIONS[0], { ...NET_POSITIONS[1], quantity: -2 }],
    });
    resolveFirst({ order_id: 'o1' });

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(2));
    // Sized to the fresh live quantity (2), not the stale click-time quantity (5).
    expect(mockMutateAsync).toHaveBeenLastCalledWith(expect.objectContaining({
      tradingsymbol: 'TCS', transaction_type: 'BUY', quantity: 2,
    }));
  });
});
