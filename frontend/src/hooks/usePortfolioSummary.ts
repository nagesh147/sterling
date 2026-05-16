import { useAppStream } from './useAppStream';

export interface PortfolioSummary {
  open_count: number;
  partially_closed_count: number;
  closed_count: number;
  total_positions: number;
  total_open_risk_usd: number;
  total_realized_pnl_usd: number;
  largest_open_risk_usd: number;
  underlyings_open: string[];
  avg_capital_at_risk_pct: number;
  timestamp_ms: number;
}

export function usePortfolioSummary() {
  const { data, status } = useAppStream<PortfolioSummary>('portfolio');
  return {
    data: data ?? undefined,
    isLoading: status === 'connecting' && data == null,
    isError: false,
  };
}
