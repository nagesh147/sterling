import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { PositionsTable } from '../paper/PaperResearchTab'; // adjust
import type { PaperPosition } from '../../hooks/usePaperBook';

describe('PaperResearchTab red bars', () => {
  const base: PaperPosition = {
    symbol: 'TEST',
    sleeve: 'swing',
    direction: 'long',
    entry_price: 100,
    sl: 95,
    tp: 110,
    unrealized_pnl: 5,
    exit_mode: 'two_red',
    current_red_count: 1,
    exit_threshold: 2,
  };

  it('matches snapshot with red health column', () => {
    const { container } = render(<PositionsTable positions={[base]} />);
    expect(container.innerHTML).toMatchSnapshot();
  });
});
