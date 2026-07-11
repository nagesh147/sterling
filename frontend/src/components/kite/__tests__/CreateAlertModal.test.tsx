import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { CreateAlertModal } from '../CreateAlertModal';

const mockMutate = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  useCreateKiteAlert: () => ({ mutate: mockMutate, isPending: false }),
}));

describe('CreateAlertModal', () => {
  beforeEach(() => {
    mockMutate.mockClear();
  });

  it('submits a simple price alert', () => {
    render(<CreateAlertModal onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'INFY above 1600' } });
    fireEvent.change(screen.getByLabelText('Symbol'), { target: { value: 'INFY' } });
    fireEvent.change(screen.getByLabelText('Exchange'), { target: { value: 'NSE' } });
    fireEvent.change(screen.getByLabelText('Threshold'), { target: { value: '1600' } });
    fireEvent.click(screen.getByText('Create alert'));
    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'INFY above 1600', lhs_exchange: 'NSE', lhs_tradingsymbol: 'INFY', rhs_constant: 1600,
      }),
      expect.anything(),
    );
  });

  it('requires a name before submitting', () => {
    render(<CreateAlertModal onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Create alert'));
    expect(mockMutate).not.toHaveBeenCalled();
    expect(screen.getByText('Enter a name for this alert')).toBeInTheDocument();
  });

  it('requires a symbol before submitting', () => {
    render(<CreateAlertModal onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'INFY above 1600' } });
    fireEvent.change(screen.getByLabelText('Threshold'), { target: { value: '1600' } });
    fireEvent.click(screen.getByText('Create alert'));
    expect(mockMutate).not.toHaveBeenCalled();
    expect(screen.getByText('Enter a symbol')).toBeInTheDocument();
  });

  it('requires a threshold greater than zero before submitting', () => {
    render(<CreateAlertModal onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'INFY above 1600' } });
    fireEvent.change(screen.getByLabelText('Symbol'), { target: { value: 'INFY' } });
    fireEvent.click(screen.getByText('Create alert'));
    expect(mockMutate).not.toHaveBeenCalled();
    expect(screen.getByText('Enter a threshold value')).toBeInTheDocument();
  });
});
