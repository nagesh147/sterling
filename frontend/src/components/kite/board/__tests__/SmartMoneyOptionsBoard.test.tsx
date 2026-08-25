import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { SmartMoneyOptionsBoard } from '../SmartMoneyOptionsBoard';

const mockSnapshot = {
  strategy_id: 'smart_money_options',
  strategy_name: 'Smart Money Multi-X Options',
  enabled: true,
  execution_mode: 'paper' as const,
  universe: ['ABB'],
  signals: [
    {
      symbol: 'ABB',
      action: 'BUY_CE' as const,
      spot_price: 7120.0,
      option_type: 'CE' as const,
      strike: 7200.0,
      expiry: '2026-08-27',
      tradingsymbol: 'ABB 7200 CE',
      entry_premium: 220.0,
      stop_loss_premium: 143.0,
      stop_loss_spot: 7010.0,
      targets: {
        target_1_2x: 440.0,
        target_2_3x: 660.0,
        target_3_5x: 1100.0,
        risk_reward_ratio_2x: 2.0,
        risk_reward_ratio_3x: 3.0,
        risk_reward_ratio_5x: 5.0,
      },
      holding_period_days: 5,
      rvol: 2.4,
      footprint_score: 85.0,
      structure_phase: 'BREAKOUT_CONFIRMED',
      reason: 'Bullish BSL Breakout with Smart Money volume 2.4x',
      confidence: 0.9,
      timestamp_ms: Date.now(),
      status: 'armed' as const,
    },
  ],
  positions: [],
  updated_at: new Date().toISOString(),
};

vi.mock('../../../../hooks/useSmartMoneyOptions', () => ({
  useSmartMoneyOptionsConfig: () => ({
    data: {
      strategy: {
        id: 'smart_money_options',
        name: 'Smart Money Multi-X Options',
        contract_version: 'SMX.1.0',
        enabled: true,
        live_ready: true,
      },
      config: {},
      defaults: {},
      vocabularies: {},
    },
    isLoading: false,
  }),
  useSmartMoneyOptionsSnapshot: () => ({
    data: mockSnapshot,
    isLoading: false,
    error: null,
  }),
  useTriggerSmartMoneyScan: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

describe('SmartMoneyOptionsBoard', () => {
  it('renders stats, action button, and signal rows', () => {
    render(<SmartMoneyOptionsBoard nowMs={Date.now()} />);
    expect(screen.getByText('Armed Setups')).toBeInTheDocument();
    expect(screen.getByText('⚡ Scan Universe')).toBeInTheDocument();
    expect(screen.getByText('ABB 7200 CE')).toBeInTheDocument();
  });
});
