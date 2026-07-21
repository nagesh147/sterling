import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { PositionHeatmap } from '../PositionHeatmap';
import type { PaperPosition } from '../../types';


describe('PositionHeatmap red progress bars', () => {
  const basePos: PaperPosition = {
    id: '1',
    underlying: 'TEST',
    status: 'open',
    is_paper: true,
    entry_timestamp_ms: Date.now(),
    entry_spot_price: 100,
    notes: '',
    run_once_state: 'ENTERED' as const,
    sized_trade: {
      contracts: 1,
      max_risk_usd: 100,
      capital_at_risk_pct: 0.01,
      position_value: 1000,
      structure: { direction: { value: 'long' }, score: 80, legs: [] },
    } as any,
  } as any;

  it('shows proportional progress before the red threshold is reached', () => {
    const positions: PaperPosition[] = [{
      ...basePos,
      exit_mode: 'two_red',
      current_red_count: 1,
      exit_threshold: 2,
    }];
    const { container } = render(<PositionHeatmap positions={positions} />);
    const progress = container.querySelector('[style*="width: 50%"]') as HTMLElement | null;
    expect(progress).not.toBeNull();
    expect(progress?.style.background).toBe('rgb(74, 164, 74)');
  });

  it('caps progress at 100% and uses the breached state at the threshold', () => {
    const positions: PaperPosition[] = [{
      ...basePos,
      exit_mode: 'one_red',
      current_red_count: 1,
      exit_threshold: 1,
    }];
    const { container } = render(<PositionHeatmap positions={positions} />);
    const progress = container.querySelector('[style*="width: 100%"]') as HTMLElement | null;
    expect(progress).not.toBeNull();
    expect(progress?.style.background).toBe('rgb(255, 68, 68)');
  });
});
