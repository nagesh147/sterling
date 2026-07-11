import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { ModifyOrderModal } from '../ModifyOrderModal';

const mockMutate = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  useModifyKiteOrder: () => ({ mutate: mockMutate, isPending: false }),
}));

const order = {
  order_id: 'o1', variety: 'regular', tradingsymbol: 'INFY', exchange: 'NSE',
  quantity: 10, price: 1500, trigger_price: 0, order_type: 'LIMIT', validity: 'DAY',
};

describe('ModifyOrderModal', () => {
  beforeEach(() => {
    mockMutate.mockClear();
  });

  it('prefills quantity and price from the order', () => {
    render(<ModifyOrderModal order={order} onClose={vi.fn()} />);
    expect(screen.getByDisplayValue('10')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1500')).toBeInTheDocument();
  });

  it('submits the edited quantity and price with the order id and variety', () => {
    render(<ModifyOrderModal order={order} onClose={vi.fn()} />);
    fireEvent.change(screen.getByDisplayValue('10'), { target: { value: '20' } });
    fireEvent.click(screen.getByText('Modify'));
    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'o1', variety: 'regular', quantity: 20, price: 1500 }),
      expect.anything(),
    );
  });

  it('closes on cancel without submitting', () => {
    const onClose = vi.fn();
    render(<ModifyOrderModal order={order} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
    expect(mockMutate).not.toHaveBeenCalled();
  });
});
