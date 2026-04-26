import { useMutation } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { CandidateContract } from '../types';

export interface StradgleStructure {
  structure_type: 'long_straddle' | 'long_strangle';
  legs: CandidateContract[];
  strike?: number;
  call_strike?: number;
  put_strike?: number;
  expiry_date: string;
  dte: number;
  net_debit: number;
  max_loss: number;
  breakeven_up: number;
  breakeven_down: number;
  avg_iv: number;
  health_score: number;
}

export interface VolatilityScanResult {
  underlying: string;
  spot_price: number;
  structures: StradgleStructure[];
  healthy_candidates: number;
  note: string;
  timestamp_ms: number;
}

export function useVolatilityScan() {
  return useMutation<VolatilityScanResult, Error, string>({
    mutationFn: (underlying) =>
      api.post<VolatilityScanResult>(
        `/api/v1/directional/volatility-scan?underlying=${underlying}`
      ),
  });
}
