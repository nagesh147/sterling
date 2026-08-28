/**
 * An action that cannot be taken is still drawn.
 *
 * Buy used to be removed from an ended leg by dropping its handler — a button
 * renders only if it has one. Two things went wrong with that. The row's
 * remaining actions shifted left, so the action column stopped lining up with
 * the rows around it; and an absent control reads as "this row has no Buy"
 * rather than "you cannot buy THIS one, because it has ended". Disabled says
 * which, and says why on hover.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { KiteActionButtons } from '../KiteActionButtons';

describe('a disabled action', () => {
  it('is still rendered, so the column keeps its shape', () => {
    render(<KiteActionButtons onBuy={vi.fn()} onSell={vi.fn()} buyDisabled />);
    expect(screen.getByTitle(/Not available|ended/i)).toBeInTheDocument();
    // Both slots still occupied.
    expect(screen.getAllByRole('button')).toHaveLength(2);
  });

  it('refuses the press', () => {
    const onBuy = vi.fn();
    render(<KiteActionButtons onBuy={onBuy} buyDisabled disabledHint="This leg has ended." />);
    const buy = screen.getByTitle('This leg has ended.');
    expect(buy).toBeDisabled();
    fireEvent.click(buy);
    expect(onBuy, 'a disabled Buy must not place an order').not.toHaveBeenCalled();
  });

  it('says why, rather than just looking grey', () => {
    render(<KiteActionButtons onBuy={vi.fn()} buyDisabled disabledHint="This leg has ended." />);
    expect(screen.getByTitle('This leg has ended.')).toBeInTheDocument();
  });

  it('leaves an enabled action alone', () => {
    const onBuy = vi.fn();
    render(<KiteActionButtons onBuy={onBuy} />);
    const buy = screen.getByTitle('Buy');
    expect(buy).not.toBeDisabled();
    fireEvent.click(buy);
    expect(onBuy).toHaveBeenCalled();
  });

  it('still omits an action the caller never supplied', () => {
    // Disabled is for "not on this row"; absent is for "this engine has no such
    // action at all". They are different statements and both are needed.
    render(<KiteActionButtons onSell={vi.fn()} />);
    expect(screen.queryByTitle('Buy')).toBeNull();
    expect(screen.getByTitle('Sell')).toBeInTheDocument();
  });
});
