import { describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useAlgoToggles } from '../useAlgoToggles';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

vi.mock('../useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: { engine_enabled: true, auto_execute: true } }),
  usePatchEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../useNavigator', () => ({
  useNavigatorConfig: () => ({
    data: { record: { config: { enabled: true, auto_execute_originated: false }, revision: 1 } },
  }),
  useSetNavigatorConfig: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../useOrbConfig', () => ({
  useOrbConfig: () => ({ data: { config: { enabled: false } } }),
  useSetOrbConfig: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../useGammaMove', () => ({
  useGammaMoveConfig: () => ({ data: { config: { enabled: true, auto_execute: false } } }),
  useUpdateGammaMove: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../useAdaptiveEdge', () => ({
  useAdaptiveEdgeEngineConfig: () => ({ data: { config: { enabled: true, auto_execute: true } } }),
  useSetAdaptiveEdgeEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../useAtmPremiumImbalance', () => ({
  useAtmPremiumImbalanceConfig: () => ({ data: { config: { enabled: true, auto_execute: false } } }),
  useSetAtmPremiumImbalanceConfig: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../useBearToBearish', () => ({
  useBearToBearishConfig: () => ({ data: { enabled: true, auto_execute: true } }),
  useUpdateBearToBearishConfig: () => ({ mutate: vi.fn(), isPending: false }),
}));

describe('useAlgoToggles', () => {
  it('returns all 7 strategies with their respective auto_execute states', () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useAlgoToggles(), { wrapper });
    expect(result.current).toHaveLength(7);

    const ids = result.current.map((t) => t.id);
    expect(ids).toEqual([
      'supertrend',
      'navigator',
      'orb',
      'gamma_move',
      'adaptive_edge',
      'atm_premium_imbalance',
      'bear_to_bearish',
    ]);

    expect(result.current.find((t) => t.id === 'supertrend')?.enabled).toBe(true);
    expect(result.current.find((t) => t.id === 'navigator')?.enabled).toBe(false);
    expect(result.current.find((t) => t.id === 'orb')?.enabled).toBe(true);
    expect(result.current.find((t) => t.id === 'gamma_move')?.enabled).toBe(false);
    expect(result.current.find((t) => t.id === 'adaptive_edge')?.enabled).toBe(true);
    expect(result.current.find((t) => t.id === 'atm_premium_imbalance')?.enabled).toBe(false);
    expect(result.current.find((t) => t.id === 'bear_to_bearish')?.enabled).toBe(true);
  });

  it('ORB Manual/Auto follows Trading Mode, not a strategy-local flag', () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useAlgoToggles(), { wrapper });
    const orb = result.current.find((t) => t.id === 'orb');
    const supertrend = result.current.find((t) => t.id === 'supertrend');
    expect(orb?.enabled).toBe(supertrend?.enabled);
    expect(orb?.description).toMatch(/Trading Mode/);
  });
});
