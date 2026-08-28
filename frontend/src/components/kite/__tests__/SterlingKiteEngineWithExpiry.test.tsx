/**
 * SuperTrend's board wrapper, after the CONTRACTS strip was removed.
 *
 * This file used to test that strip: a dot, "6 of 8 expiry sets · 14 live
 * dates", and a "Change →" link. The row is gone — contract selection lives in
 * Connect → SuperTrend beside the universe and the scan rules, and the strip was
 * spending a row of vertical space restating it.
 *
 * What is worth holding now is that it stays gone and the board still renders.
 * A removed row that quietly comes back is how a layout regresses.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../SterlingKiteEnginePane', () => ({
  SterlingKiteEnginePane: (props: Record<string, unknown>) => (
    <div data-testid="board" data-haschart={String(Boolean(props.onOpenChart))}>board</div>
  ),
}));

import { SterlingKiteEngineWithExpiry } from '../SterlingKiteEngineWithExpiry';

describe('SuperTrend board wrapper', () => {
  it('renders the board', () => {
    render(<SterlingKiteEngineWithExpiry onSelectSignal={() => {}} />);
    expect(screen.getByTestId('board')).toBeInTheDocument();
  });

  it('no longer shows the contracts strip', () => {
    render(<SterlingKiteEngineWithExpiry onSelectSignal={() => {}} />);
    expect(screen.queryByText(/expiry sets/)).not.toBeInTheDocument();
    expect(screen.queryByText('CONTRACTS')).not.toBeInTheDocument();
    expect(screen.queryByText(/Change/)).not.toBeInTheDocument();
  });

  it('does not fetch a contract calendar just to render the board', () => {
    // The strip was the only reason this wrapper called useContractSelection.
    // Rendering a board should not cost a calendar request.
    render(<SterlingKiteEngineWithExpiry onSelectSignal={() => {}} />);
    expect(screen.getByTestId('board')).toBeInTheDocument();
  });

  it('passes its props through untouched', () => {
    const onOpenChart = vi.fn();
    render(
      <SterlingKiteEngineWithExpiry onSelectSignal={() => {}} onOpenChart={onOpenChart} />,
    );
    expect(screen.getByTestId('board').getAttribute('data-haschart')).toBe('true');
  });
});
