/**
 * One re-scan for every strategy that has one.
 *
 * Re-scan reached SuperTrend and Navigator — the two engines whose rows share
 * the pane the button sits on. Gamma Move, ORB and Adaptive Edge all have scan
 * endpoints and it never touched them, so pressing it refreshed part of the
 * platform and left the rest on its own background loop.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const calls: string[] = [];
const fail = new Set<string>();

const runner = (name: string) => () => {
  calls.push(name);
  return fail.has(name) ? Promise.reject(new Error(`${name} refused`)) : Promise.resolve({});
};

vi.mock('../useSterlingKiteEngine', () => ({
  useRunScan: () => ({ mutateAsync: runner('supertrend'), isPending: false }),
}));
vi.mock('../useNavigator', () => ({
  useRunNavigatorScan: () => ({ mutateAsync: runner('navigator'), isPending: false }),
}));
vi.mock('../useGammaMove', () => ({
  useGammaMoveScan: () => ({ mutateAsync: runner('gamma_move'), isPending: false }),
}));
vi.mock('../../utils/api', () => ({
  api: { post: (url: string) => runner(url.includes('adaptive-edge') ? 'adaptive_edge' : url)() },
}));

import { useScanAllStrategies, SCANNABLE_ENGINE_LABEL } from '../useScanAllStrategies';

function harness() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  // ORB's scan is a polling query that POSTs, so it is triggered by refetching
  // its key rather than by a mutate. Register it so the refetch has something.
  qc.setQueryDefaults(['nifty-orb-options-scan'], { queryFn: runner('orb') as never });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  return renderHook(() => useScanAllStrategies(), { wrapper });
}

beforeEach(() => { calls.length = 0; fail.clear(); });

describe('useScanAllStrategies', () => {
  it('runs every strategy given, in the order given', async () => {
    const { result } = harness();
    await act(async () => {
      await result.current.scanAll(['supertrend', 'navigator', 'gamma_move', 'adaptive_edge']);
    });
    expect(calls).toEqual(['supertrend', 'navigator', 'gamma_move', 'adaptive_edge']);
  });

  it('honours a lens-first order', async () => {
    const { result } = harness();
    await act(async () => {
      await result.current.scanAll(['navigator', 'supertrend']);
    });
    // The table being read must not wait behind the other engine's full scan.
    expect(calls).toEqual(['navigator', 'supertrend']);
  });

  it('runs them one at a time, never together', async () => {
    // They share the same Kite ~3 req/s historical budget, so firing them
    // together makes each slower rather than the set faster.
    const order: string[] = [];
    let active = 0;
    let maxActive = 0;
    const slow = (name: string) => async () => {
      active += 1; maxActive = Math.max(maxActive, active);
      await new Promise((r) => setTimeout(r, 1));
      order.push(name); active -= 1;
      return {};
    };
    vi.doMock('../useSterlingKiteEngine', () => ({
      useRunScan: () => ({ mutateAsync: slow('supertrend'), isPending: false }),
    }));
    const { result } = harness();
    await act(async () => {
      await result.current.scanAll(['supertrend', 'navigator', 'gamma_move']);
    });
    expect(maxActive).toBeLessThanOrEqual(1);
  });

  it('one engine failing does not stop the others', async () => {
    fail.add('navigator');
    const { result } = harness();
    let results: Awaited<ReturnType<typeof result.current.scanAll>> = [];
    await act(async () => {
      results = await result.current.scanAll(['supertrend', 'navigator', 'gamma_move']);
    });
    expect(calls).toEqual(['supertrend', 'navigator', 'gamma_move']);
    expect(results.find((r) => r.engine === 'navigator')?.ok).toBe(false);
    expect(results.filter((r) => r.ok).map((r) => r.engine)).toEqual(['supertrend', 'gamma_move']);
  });

  it('reports failures rather than swallowing them', async () => {
    // A button that claims to scan everything has to say which ones it could not.
    fail.add('gamma_move');
    const { result } = harness();
    let results: Awaited<ReturnType<typeof result.current.scanAll>> = [];
    await act(async () => { results = await result.current.scanAll(['gamma_move']); });
    expect(results[0].error).toContain('refused');
  });

  it('does not list ATM Premium Imbalance, which has no scan', () => {
    // It resolves one option pair and arms it — there is no universe to sweep,
    // so offering it would promise something the platform cannot do.
    expect(Object.keys(SCANNABLE_ENGINE_LABEL)).not.toContain('atm_premium_imbalance');
    expect(Object.keys(SCANNABLE_ENGINE_LABEL)).toHaveLength(5);
  });
});
