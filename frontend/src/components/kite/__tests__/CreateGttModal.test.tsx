import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { CreateGttModal } from '../CreateGttModal';

const mockMutate = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  usePlaceKiteGtt: () => ({ mutate: mockMutate, isPending: false }),
}));

describe('CreateGttModal', () => {
  beforeEach(() => {
    mockMutate.mockClear();
  });

  it('submits a single-leg GTT with the entered trigger and price', () => {
    render(<CreateGttModal onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Symbol'), { target: { value: 'INFY' } });
    fireEvent.change(screen.getByLabelText('Exchange'), { target: { value: 'NSE' } });
    fireEvent.change(screen.getByLabelText('Last price'), { target: { value: '1500' } });
    fireEvent.change(screen.getByLabelText('Trigger price'), { target: { value: '1400' } });
    fireEvent.change(screen.getByLabelText('Order price'), { target: { value: '1400' } });
    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '10' } });
    fireEvent.click(screen.getByText('Create GTT'));
    expect(mockMutate).toHaveBeenCalledWith(expect.objectContaining({
      trigger_type: 'single', tradingsymbol: 'INFY', exchange: 'NSE',
      last_price: 1500, trigger_values: [1400],
    }));
  });

  it('shows a validation error when the trigger price is missing', () => {
    render(<CreateGttModal onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Create GTT'));
    expect(mockMutate).not.toHaveBeenCalled();
    expect(screen.getByText(/trigger price/i)).toBeInTheDocument();
  });
});
