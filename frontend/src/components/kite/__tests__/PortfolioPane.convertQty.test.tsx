import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { ConvertControl } from '../PortfolioPane';

// ConvertControl converts a position between product types (MIS/CNC/NRML).
// This suite covers the partial-quantity behavior added on top of the
// pre-existing full-quantity-only convert action: the qty input defaults to
// the full position size, is bounded to [1, fullQty], and the mutation is
// only fired (with the entered, possibly-partial quantity) when the value
// is in range.
const mutate = vi.fn();

vi.mock('../../../hooks/useKite', () => ({
  useConvertKitePosition: () => ({ isPending: false, isError: false, isSuccess: false, mutate }),
}));

const POSITION = { tradingsymbol: 'RELIANCE', exchange: 'NSE', quantity: 75, product: 'MIS' };

function getQtyInput() {
  return screen.getByTitle('Max: 75') as HTMLInputElement;
}

function getConvertLink() {
  return screen.getByText('convert');
}

describe('ConvertControl partial-quantity conversion', () => {
  beforeEach(() => {
    mutate.mockClear();
  });

  it('defaults the quantity input to the full position size', () => {
    render(<ConvertControl p={POSITION} />);
    expect(getQtyInput().value).toBe('75');
  });

  it('sends the entered partial quantity (not the full quantity) on convert', () => {
    render(<ConvertControl p={POSITION} />);
    fireEvent.change(getQtyInput(), { target: { value: '30' } });
    fireEvent.click(getConvertLink());
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({
      tradingsymbol: 'RELIANCE', exchange: 'NSE', quantity: 30, old_product: 'MIS',
    }));
  });

  it('disables convert (no mutate call) when quantity exceeds the full position size', () => {
    render(<ConvertControl p={POSITION} />);
    fireEvent.change(getQtyInput(), { target: { value: '999' } });
    fireEvent.click(getConvertLink());
    expect(mutate).not.toHaveBeenCalled();
    expect(getConvertLink()).toHaveStyle({ cursor: 'not-allowed' });
  });

  it('disables convert (no mutate call) when quantity is zero or emptied', () => {
    render(<ConvertControl p={POSITION} />);
    fireEvent.change(getQtyInput(), { target: { value: '' } });
    fireEvent.click(getConvertLink());
    expect(mutate).not.toHaveBeenCalled();
    expect(getConvertLink()).toHaveStyle({ cursor: 'not-allowed' });
  });

  it('re-enables convert once the quantity is corrected back into range', () => {
    render(<ConvertControl p={POSITION} />);
    fireEvent.change(getQtyInput(), { target: { value: '999' } });
    fireEvent.change(getQtyInput(), { target: { value: '50' } });
    fireEvent.click(getConvertLink());
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ quantity: 50 }));
  });
});
