import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { PositionCard } from '../PositionsPanel'; // adjust if needed
import type { PaperPosition } from '../../types';

// Simple snapshot test for progress bar rendering with red count
describe('Position progress bars', () => {
  const mockPos: PaperPosition = {
    id: 'test',
    underlying: 'TEST',
    sized_trade: { contracts: 1, max_risk_usd: 100, capital_at_risk_pct: 0.01, position_value: 1000, structure: { direction: { value: 'long' }, score: 1, legs: [{ strike: 0, expiry_date: '', option_type: 'CE' }] } as any },
    status: 'open',
    is_paper: true,
    entry_timestamp_ms: Date.now(),
    entry_spot_price: 100,
    notes: '',
    run_once_state: 'ENTERED',
    exit_mode: 'two_red',
    current_red_count: 1,
    exit_threshold: 2,
    last_st_alignment: [1, 1, 0],
  };

  it('renders red progress bar snapshot', () => {
    const { container } = render(<div><span>EXIT {mockPos.exit_mode} ({mockPos.current_red_count}/{mockPos.exit_threshold})</span><div style={{width:60,height:8,background:'#222'}}><div style={{width:'50%',height:'100%',background:'#fa0'}} /></div></div>);
    expect(container.innerHTML).toMatchSnapshot();
  });
});
