import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_STATUS, useReplayStore } from '../../../../hooks/useReplayStore';
import { ReplaySummaryModal } from '../ReplaySummaryModal';
import { makeSignal, makeStatus, makeTrade, primeStore, stubFetch } from './testUtils';

function renderModal() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <ReplaySummaryModal />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  stubFetch();
  primeStore({ summaryOpen: true });
});

describe('the modal is actually a modal', () => {
  // Its two class names were referenced in TSX and defined in no stylesheet, so
  // it rendered as an unstyled block inside the workspace column that shoved
  // the footer down. These assertions pin the parts that were missing.
  it('renders nothing when closed', () => {
    primeStore({ summaryOpen: false });
    renderModal();
    expect(screen.queryByTestId('replay-summary')).toBeNull();
  });

  it('is a labelled, modal dialog', () => {
    renderModal();
    const dialog = screen.getByTestId('replay-summary');
    expect(dialog).toHaveAttribute('role', 'dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'rd-summary-title');
  });

  it('portals to the body so it can clear the fullscreen dock', () => {
    renderModal();
    const overlay = screen.getByTestId('replay-summary').parentElement!;
    expect(overlay.parentElement).toBe(document.body);
    expect(overlay.className).toContain('rd-overlay');
  });

  it('locks background scroll while open', () => {
    const { unmount } = renderModal();
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(document.body.style.overflow).toBe('');
  });
});

describe('dismissal', () => {
  it('closes on Escape', async () => {
    renderModal();
    await act(async () => { fireEvent.keyDown(document, { key: 'Escape' }); });
    expect(useReplayStore.getState().summaryOpen).toBe(false);
  });

  it('closes on a scrim press', async () => {
    renderModal();
    const overlay = screen.getByTestId('replay-summary').parentElement!;
    await act(async () => { fireEvent.mouseDown(overlay); });
    expect(useReplayStore.getState().summaryOpen).toBe(false);
  });

  it('does NOT close on a press inside the card', async () => {
    // Otherwise selecting text in the trade log dismisses the summary.
    renderModal();
    await act(async () => { fireEvent.mouseDown(screen.getByTestId('replay-summary')); });
    expect(useReplayStore.getState().summaryOpen).toBe(true);
  });

  it('closes on the Close button', async () => {
    renderModal();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Close' })); });
    expect(useReplayStore.getState().summaryOpen).toBe(false);
  });
});

describe('the numbers', () => {
  it('divides the win rate by CLOSED trades, not by every trade entered', () => {
    // The old summary divided by `trades_entered`, which understates the rate
    // whenever a position is still open at the session close.
    primeStore({
      summaryOpen: true,
      status: makeStatus({
        stats: {
          ...DEFAULT_STATUS.stats,
          wins: 3, losses: 1, pnl: 1000,
          trades: [
            makeTrade({ trade_id: 'A', status: 'WIN' }),
            makeTrade({ trade_id: 'B', status: 'WIN' }),
            makeTrade({ trade_id: 'C', status: 'WIN' }),
            makeTrade({ trade_id: 'D', status: 'LOSS' }),
            makeTrade({ trade_id: 'E', status: 'OPEN' }),
            makeTrade({ trade_id: 'F', status: 'OPEN' }),
          ],
        },
      }),
    });
    renderModal();
    // Scope to the stat grid: the breakdown table renders a Win % column too.
    const box = screen.getByText('Win rate').parentElement!;
    expect(within(box).getByText('75%')).toBeTruthy();
    expect(within(box).queryByText('50%')).toBeNull();
  });

  it('says whether the net figure accounts for friction', () => {
    renderModal();
    expect(screen.getByText('friction not modelled')).toBeTruthy();
  });

  it('reports an em dash for an average with nothing closed', () => {
    primeStore({
      summaryOpen: true,
      status: makeStatus({ stats: { ...DEFAULT_STATUS.stats, trades: [makeTrade({ status: 'OPEN' })] } }),
    });
    renderModal();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
});

describe('strategy breakdown', () => {
  it('merges strategies whose names differ only in case', () => {
    // Keyed on the raw string, `SuperTrend` and `supertrend` appeared as two
    // separate rows for one strategy.
    primeStore({
      summaryOpen: true,
      status: makeStatus({
        stats: {
          ...DEFAULT_STATUS.stats,
          events: [makeSignal({ strategy: 'SuperTrend' })],
          trades: [makeTrade({ strategy: 'supertrend' })],
        },
      }),
    });
    renderModal();
    // One row in the breakdown, not two. (The trade log names it as well, so
    // count rows rather than occurrences of the label.)
    const table = screen.getByText('Strategy breakdown').parentElement!
      .querySelector('tbody')!;
    expect(table.querySelectorAll('tr')).toHaveLength(1);
    expect(within(table).getByText('SuperTrend')).toBeTruthy();
  });

  it('renders an explicit empty row rather than a blank table', () => {
    renderModal();
    expect(screen.getByText('No strategies triggered')).toBeTruthy();
  });
});

describe('replay again', () => {
  it('restarts the replay, not just the dock', async () => {
    // The old button only reopened the dock and left the user hunting for play.
    const fetchSpy = stubFetch();
    primeStore({ summaryOpen: true, open: false });
    renderModal();
    fetchSpy.mockClear();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Replay again/ }));
    });

    expect(useReplayStore.getState().open).toBe(true);
    expect(useReplayStore.getState().summaryOpen).toBe(false);
    expect(fetchSpy.mock.calls.some(([u]) => String(u).includes('/start'))).toBe(true);
  });
});

describe('execution model badge', () => {
  // Ported from main's SimulationSummary test, which asserted a friction badge
  // on the component this one replaces. It names the model the engine actually
  // RAN — inferred from whether any trade carried measured friction — rather
  // than the mode that happened to be requested.
  it('reads REALISTIC when trades carry measured friction', () => {
    primeStore({
      summaryOpen: true,
      status: makeStatus({
        config: { date: '2026-09-04', start_time: '09:00:00', end_time: '15:30:00', speed: 5, resolution: '5m', instruments: [], friction_mode: 'realistic' },
        stats: { ...DEFAULT_STATUS.stats, trades: [makeTrade({ slippage: 12.5 })] },
      }),
    });
    renderModal();
    expect(screen.getByTestId('replay-friction-badge').textContent).toBe('REALISTIC');
    expect(screen.getByText(/spread and slippage applied/i)).toBeTruthy();
  });

  it('reads IDEAL when the run asked for zero friction', () => {
    primeStore({
      summaryOpen: true,
      status: makeStatus({
        config: { date: '2026-09-04', start_time: '09:00:00', end_time: '15:30:00', speed: 5, resolution: '5m', instruments: [], friction_mode: 'ideal' },
        stats: { ...DEFAULT_STATUS.stats, trades: [makeTrade({ slippage: undefined })] },
      }),
    });
    renderModal();
    expect(screen.getByTestId('replay-friction-badge').textContent).toBe('IDEAL');
  });

  it('says the engine modelled none, rather than implying zero', () => {
    primeStore({
      summaryOpen: true,
      status: makeStatus({
        stats: { ...DEFAULT_STATUS.stats, trades: [makeTrade({ slippage: undefined })] },
      }),
    });
    renderModal();
    expect(screen.getByTestId('replay-friction-badge').textContent).toBe('NONE');
    expect(screen.getByText(/not modelled by this engine/i)).toBeTruthy();
  });
});

describe('risk metrics ported from main', () => {
  it('computes profit factor, and declines to when nothing has lost', () => {
    primeStore({
      summaryOpen: true,
      status: makeStatus({
        stats: {
          ...DEFAULT_STATUS.stats, wins: 2, losses: 1,
          trades: [
            makeTrade({ trade_id: 'A', status: 'WIN', pnl_usd: 600 }),
            makeTrade({ trade_id: 'B', status: 'WIN', pnl_usd: 400 }),
            makeTrade({ trade_id: 'C', status: 'LOSS', pnl_usd: -500 }),
          ],
        },
      }),
    });
    renderModal();
    const box = screen.getByText('Profit factor').parentElement!;
    expect(within(box).getByText('2.00')).toBeTruthy();
  });

  it('reports max drawdown as the worst peak-to-trough run', () => {
    primeStore({
      summaryOpen: true,
      status: makeStatus({
        stats: {
          ...DEFAULT_STATUS.stats, wins: 1, losses: 2,
          trades: [
            makeTrade({ trade_id: 'A', status: 'WIN', pnl_usd: 1000 }),
            makeTrade({ trade_id: 'B', status: 'LOSS', pnl_usd: -400 }),
            makeTrade({ trade_id: 'C', status: 'LOSS', pnl_usd: -300 }),
          ],
        },
      }),
    });
    renderModal();
    const box = screen.getByText('Max drawdown').parentElement!;
    expect(within(box).getByText('₹700.00')).toBeTruthy();
  });
});
