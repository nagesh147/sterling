import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { SmartMoneyOptionsSettings } from '../SmartMoneyOptionsSettings';

const mockConfig = {
  enabled: true,
  execution_mode: 'paper' as const,
  universe: ['ABB', 'RELIANCE', 'TATAMOTORS'],
  htf_timeframe: '1d',
  ltf_timeframe: '1h',
  min_consolidation_bars: 8,
  max_consolidation_range_pct: 8.0,
  volume_surge_multiplier: 1.8,
  min_footprint_score: 65.0,
  strike_selection: 'OTM1' as const,
  expiry_policy: 'NEAREST_MONTHLY' as const,
  target_multiplier_1: 2.0,
  target_multiplier_2: 3.0,
  target_multiplier_3: 5.0,
  stop_loss_pct: 35.0,
  trailing_stop_activation: 2.0,
  holding_period_days: 5,
  max_open_positions: 3,
  lots_per_trade: 1,
  data_source: 'kite' as const,
};

let cfgData: any = {
  strategy: {
    id: 'smart_money_options',
    name: 'Smart Money Multi-X Options',
    contract_version: 'SMX.1.0',
    enabled: true,
    live_ready: true,
  },
  config: mockConfig,
  defaults: mockConfig,
  vocabularies: {
    execution_mode: ['paper', 'shadow', 'live'],
    strike_selection: ['ATM', 'OTM1', 'OTM2'],
    expiry_policy: ['NEAREST_MONTHLY', 'CURRENT_EXPIRY', 'NEXT_EXPIRY'],
  },
};

vi.mock('../../hooks/useSmartMoneyOptions', () => ({
  useSmartMoneyOptionsConfig: () => ({ data: cfgData, isLoading: false }),
  useSetSmartMoneyOptionsConfig: () => ({ mutate: vi.fn(), isPending: false }),
}));

describe('SmartMoneyOptionsSettings', () => {
  it('renders title, multi-X targets and configuration sections', () => {
    render(<SmartMoneyOptionsSettings />);
    expect(screen.getByText('Smart Money Multi-X Options')).toBeInTheDocument();
    expect(screen.getByText('Target 1 (2X)')).toBeInTheDocument();
    expect(screen.getByText('Target 3 (5X Multi-X)')).toBeInTheDocument();
    expect(screen.getByText('Volume Surge Multiplier (RVOL)')).toBeInTheDocument();
  });
});
