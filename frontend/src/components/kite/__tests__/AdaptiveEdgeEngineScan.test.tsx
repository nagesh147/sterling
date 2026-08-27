import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { AdaptiveEdgeEngineScan } from '../AdaptiveEdgeEngineScan';

const { configQuery, snapshotResult, positionsResult, squareOff } = vi.hoisted(() => ({
  configQuery: {
    data: {
      strategy: {
        id: 'adaptive_edge', name: 'Adaptive Edge', validated: false,
        calibrated_fields: [], calibration: {},
        headline_finding: 'Nothing here has been measured yet.',
        what_to_do: 'Run it on paper',
      },
      config: {}, defaults: {}, vocabularies: {}, warnings: [],
    },
  },
  snapshotResult: { current: {} as Record<string, unknown> },
  positionsResult: { current: { positions: [], realised_pnl_today: 0 } as Record<string, unknown> },
  squareOff: vi.fn(),
}));

vi.mock('../../../hooks/useAdaptiveEdge', () => ({
  useAdaptiveEdgeEngineConfig: () => configQuery,
}));

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
  return {
    ...actual,
    /* Dispatch on the key: the component runs two queries and returning the same
       payload for both would let a wrong key pass unnoticed. */
    useQuery: ({ queryKey }: { queryKey: unknown[] }) => ({
      data: String(queryKey[0]).includes('positions')
        ? positionsResult.current
        : snapshotResult.current,
    }),
    useMutation: () => ({ mutate: squareOff, isPending: false }),
  };
});

function renderScan(snapshot: Record<string, unknown>,
                    positions: Record<string, unknown> = { positions: [], realised_pnl_today: 0 }) {
  snapshotResult.current = snapshot;
  positionsResult.current = positions;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <AdaptiveEdgeEngineScan />
    </QueryClientProvider>,
  );
}

describe('AdaptiveEdgeEngineScan', () => {
  it('says why the board is empty rather than just showing nothing', () => {
    renderScan({ scan: { underlyings: 2, chains_read: 2, listed: 0, candidates: [],
                         skipped: { NIFTY: 'no contract inside the expiry and strike windows' } } });
    expect(screen.getByText(/no contract inside the expiry and strike windows/)).toBeInTheDocument();
  });

  it('reports which liquidity filter removed contracts', () => {
    renderScan({ scan: { listed: 5, tradeable: 0, candidates: [], dropped: { 'spread too wide': 3 } } });
    expect(screen.getByText(/3 contracts dropped — spread too wide/)).toBeInTheDocument();
  });

  it('distinguishes "not scanned yet" from "scanned and found nothing"', () => {
    renderScan({ scan: { candidates: [] } });
    expect(screen.getByText(/No scan has run yet/)).toBeInTheDocument();
  });

  it('lists candidates and marks each one not armable while uncalibrated', () => {
    renderScan({
      scan: {
        underlyings: 1, listed: 1, tradeable: 1,
        candidates: [{ symbol: 'NIFTY26090325000CE', strike: 25000, option_type: 'CE',
                       dte: 7, last_price: 120, oi: 60000 }],
      },
    });
    expect(screen.getByText('NIFTY26090325000CE')).toBeInTheDocument();
    expect(screen.getByText(/Not armable — uncalibrated/)).toBeInTheDocument();
  });

  it('states that live execution is blocked, and by which gate', () => {
    renderScan({ scan: { candidates: [] },
                 readiness: { executable: false, promotion_gate_reason: 'strategy_promotion_required' } });
    expect(screen.getByText(/Live execution blocked: strategy_promotion_required/)).toBeInTheDocument();
  });

  it('surfaces scan errors instead of rendering an innocent empty table', () => {
    renderScan({ scan: { candidates: [], errors: ['no active Kite account'] } });
    expect(screen.getByText('no active Kite account')).toBeInTheDocument();
  });
});

const position = (over: Record<string, unknown> = {}) => ({
  symbol: 'SYM', underlying: 'NIFTY', type: 'CE', quantity: 50, entry: 100,
  stop: 70, target: 200, state: 'open', open: true, exit_price: 0,
  exit_reason: '', broker_stop: true, stop_mode: 'both', ...over,
});

describe('AdaptiveEdgeEngineScan — open positions', () => {
  it('shows nothing about positions when flat', () => {
    renderScan({ scan: { candidates: [] } });
    expect(screen.queryByText('Open positions')).toBeNull();
  });

  it('lists what is held with its stop and target', () => {
    renderScan({ scan: { candidates: [] } },
               { positions: [position()], realised_pnl_today: 0 });
    expect(screen.getByText('Open positions')).toBeInTheDocument();
    expect(screen.getByText('SYM')).toBeInTheDocument();
    expect(screen.getByText('Broker stop')).toBeInTheDocument();
  });

  it('names an unprotected position rather than leaving it to a missing badge', () => {
    renderScan({ scan: { candidates: [] } },
               { positions: [position({ broker_stop: false })], realised_pnl_today: 0 });
    expect(screen.getByText(/no broker stop/)).toBeInTheDocument();
    expect(screen.getByText('This process only')).toBeInTheDocument();
  });

  it('does not warn when the stop is deliberately monitor-only', () => {
    renderScan({ scan: { candidates: [] } },
               { positions: [position({ broker_stop: false, stop_mode: 'monitor' })],
                 realised_pnl_today: 0 });
    expect(screen.queryByText(/no broker stop/)).toBeNull();
  });

  it('shows realised P&L for the day, signed', () => {
    renderScan({ scan: { candidates: [] } },
               { positions: [position()], realised_pnl_today: -1250 });
    expect(screen.getByText(/realised today -1,250/)).toBeInTheDocument();
  });

  it('ignores closed positions in the open list', () => {
    renderScan({ scan: { candidates: [] } },
               { positions: [position({ open: false })], realised_pnl_today: 0 });
    expect(screen.queryByText('Open positions')).toBeNull();
  });

  it('offers a square off that an operator can always reach', () => {
    renderScan({ scan: { candidates: [] } },
               { positions: [position()], realised_pnl_today: 0 });
    expect(screen.getByText('Square off all')).toBeInTheDocument();
  });
});
