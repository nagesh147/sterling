import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { GttOptionsModal } from '../GttOptionsModal';

const mockModify = vi.fn();
const mockDelete = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  useModifyKiteGtt: () => ({ mutate: mockModify, isPending: false }),
  useDeleteKiteGtt: () => ({ mutate: mockDelete, isPending: false }),
}));

const gtt = {
  id: 42,
  condition: { tradingsymbol: 'INFY', exchange: 'NSE', trigger_values: [1400], last_price: 1500 },
  orders: [{ transaction_type: 'SELL', quantity: 10, product: 'CNC', order_type: 'LIMIT', price: 1400 }],
  type: 'single',
};

describe('GttOptionsModal', () => {
  it('prefills the trigger price from the GTT condition', () => {
    render(<GttOptionsModal gtt={gtt} onClose={vi.fn()} />);
    expect(screen.getByDisplayValue('1400')).toBeInTheDocument();
  });

  it('submits a modify with the edited trigger price', () => {
    render(<GttOptionsModal gtt={gtt} onClose={vi.fn()} />);
    fireEvent.change(screen.getByDisplayValue('1400'), { target: { value: '1350' } });
    fireEvent.click(screen.getByText('Save changes'));
    expect(mockModify).toHaveBeenCalledWith(expect.objectContaining({ id: 42, trigger_values: [1350] }), expect.anything());
  });

  it('requires confirmation before deleting', () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<GttOptionsModal gtt={gtt} onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Delete'));
    expect(confirmSpy).toHaveBeenCalled();
    expect(mockDelete).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('deletes when the confirmation is accepted', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<GttOptionsModal gtt={gtt} onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Delete'));
    expect(mockDelete).toHaveBeenCalledWith(42, expect.anything());
    vi.restoreAllMocks();
  });
});
