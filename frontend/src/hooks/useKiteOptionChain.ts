import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface ChainLeg {
  ltp: number;
  oi: number;
  iv: number;
  delta: number;
  theta: number;
  vega: number;
  gamma: number;
  symbol: string;
}

export interface ChainRow {
  strike: number;
  isAtm: boolean;
  call: ChainLeg | null;
  put: ChainLeg | null;
}

export interface ChainExpiry {
  date: string;   // "2026-06-23"
  dte: number;
  label: string;  // "23 Jun"
}

export interface KiteOptionChain {
  underlying: string;
  spot: number;
  atm_strike: number;
  strike_step: number;
  expiries: ChainExpiry[];
  chain: Record<string, ChainRow[]>;
}

/**
 * Live per-symbol option chain for the Kite OI/Greeks tabs.
 * `symbol` may be "NSE:NIFTY 50" or "NIFTY 50" — the underlying is derived.
 * Returns no data (callers fall back to a placeholder) when the user has no
 * active Kite session or the underlying has no NFO options.
 */
export function useKiteOptionChain(symbol: string) {
  const underlying = (symbol || '').includes(':') ? symbol.split(':')[1] : symbol;
  return useQuery<KiteOptionChain>({
    queryKey: ['kite-option-chain', underlying],
    queryFn: () =>
      api.get<KiteOptionChain>(`/api/v1/kite/option-chain?underlying=${encodeURIComponent(underlying)}`),
    enabled: !!underlying,
    refetchInterval: 15_000,
    retry: false,
  });
}
