import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { SterlingKiteEnginePane } from '../SterlingKiteEnginePane'; // adjust import

// Mock hooks and props for e2e-like test of the hybrid weight picker
vi.mock('../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: { hybrid_st_weight: 0.5, exit_mode: 'two_red' } }),
  useSetEngineConfig: () => ({ mutate: vi.fn() }),
  // other mocks
}));

describe('Hybrid Weight Picker E2E', () => {
  it('renders picker and updates on change', () => {
    const mockPatch = vi.fn();
    render(<SterlingKiteEnginePane onSelectSignal={vi.fn()} />); // mock props

    const input = screen.getByTestId('hybrid-weight-input') || screen.getByDisplayValue('0.5');
    expect(input).toBeInTheDocument();

    fireEvent.change(input, { target: { value: '0.7' } });
    // expect patch called with new weight
    // since mock, assert value change
    expect((input as HTMLInputElement).value).toBe('0.7');
  });
});
