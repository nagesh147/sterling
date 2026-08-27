import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { AdaptiveEdgeEngineScan } from '../AdaptiveEdgeEngineScan';

const { configQuery, snapshotResult } = vi.hoisted(() => ({
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
}));

vi.mock('../../../hooks/useAdaptiveEdge', () => ({
  useAdaptiveEdgeEngineConfig: () => configQuery,
}));

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
  return { ...actual, useQuery: () => ({ data: snapshotResult.current }) };
});

function renderScan(snapshot: Record<string, unknown>) {
  snapshotResult.current = snapshot;
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
