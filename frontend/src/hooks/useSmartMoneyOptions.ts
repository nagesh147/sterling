import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type StrikeSelectionPolicy = 'ATM' | 'OTM1' | 'OTM2';
export type ExpiryPolicy = 'NEAREST_MONTHLY' | 'CURRENT_EXPIRY' | 'NEXT_EXPIRY';
export type ExecutionMode = 'paper' | 'shadow' | 'live';

export interface SmartMoneyOptionsConfig {
  enabled: boolean;
  execution_mode: ExecutionMode;
  universe: string[];
  htf_timeframe: string;
  ltf_timeframe: string;
  min_consolidation_bars: number;
  max_consolidation_range_pct: number;
  volume_surge_multiplier: number;
  min_footprint_score: number;
  strike_selection: StrikeSelectionPolicy;
  expiry_policy: ExpiryPolicy;
  target_multiplier_1: number;
  target_multiplier_2: number;
  target_multiplier_3: number;
  stop_loss_pct: number;
  trailing_stop_activation: number;
  holding_period_days: number;
  max_open_positions: number;
  lots_per_trade: number;
  data_source: 'kite' | 'truedata';
}

export interface MultiXTarget {
  target_1_2x: number;
  target_2_3x: number;
  target_3_5x: number;
  risk_reward_ratio_2x: number;
  risk_reward_ratio_3x: number;
  risk_reward_ratio_5x: number;
}

export interface SmartMoneySignal {
  symbol: string;
  action: 'BUY_CE' | 'BUY_PE' | 'NO_TRADE';
  spot_price: number;
  option_type?: 'CE' | 'PE';
  strike?: number | null;
  expiry?: string | null;
  tradingsymbol?: string | null;
  entry_premium?: number | null;
  stop_loss_premium?: number | null;
  stop_loss_spot?: number | null;
  targets?: MultiXTarget | null;
  holding_period_days: number;
  rvol: number;
  footprint_score: number;
  structure_phase: string;
  reason: string;
  confidence: number;
  timestamp_ms: number;
  status: 'watching' | 'armed' | 'running' | 'ended';
}

export interface SmartMoneySnapshot {
  strategy_id: string;
  strategy_name: string;
  enabled: boolean;
  execution_mode: ExecutionMode;
  universe: string[];
  signals: SmartMoneySignal[];
  positions: any[];
  updated_at: string;
}

export interface SmartMoneyDescriptorResponse {
  strategy: {
    id: string;
    name: string;
    contract_version: string;
    enabled: boolean;
    live_ready: boolean;
  };
  config: SmartMoneyOptionsConfig;
  defaults: SmartMoneyOptionsConfig;
  vocabularies: Record<string, string[]>;
}

const CONFIG_QUERY_KEY = ['smart-money-options-config'] as const;
const SNAPSHOT_QUERY_KEY = ['smart-money-options-snapshot'] as const;

export function useSmartMoneyOptionsConfig() {
  return useQuery<SmartMoneyDescriptorResponse>({
    queryKey: CONFIG_QUERY_KEY,
    queryFn: async () => {
      const res = await fetch('/api/v1/config/smart-money-options');
      if (!res.ok) throw new Error(`Failed to load Smart Money config: ${res.statusText}`);
      return res.json();
    },
    staleTime: 5_000,
  });
}

export function useSetSmartMoneyOptionsConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: Partial<SmartMoneyOptionsConfig>) => {
      const res = await fetch('/api/v1/config/smart-money-options', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Failed to update Smart Money config');
      }
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CONFIG_QUERY_KEY });
      qc.invalidateQueries({ queryKey: SNAPSHOT_QUERY_KEY });
    },
  });
}

export function useSmartMoneyOptionsSnapshot(enabled = true) {
  return useQuery<SmartMoneySnapshot>({
    queryKey: SNAPSHOT_QUERY_KEY,
    queryFn: async () => {
      const res = await fetch('/api/v1/config/smart-money-options/snapshot');
      if (!res.ok) throw new Error(`Failed to load snapshot: ${res.statusText}`);
      return res.json();
    },
    enabled,
    refetchInterval: 3_000,
    staleTime: 2_000,
  });
}

export function useTriggerSmartMoneyScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/v1/config/smart-money-options/scan', {
        method: 'POST',
      });
      if (!res.ok) throw new Error(`Scan trigger failed: ${res.statusText}`);
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SNAPSHOT_QUERY_KEY });
    },
  });
}
