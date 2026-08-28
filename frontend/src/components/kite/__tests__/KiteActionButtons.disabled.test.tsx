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

/**
 * ...and it is still recognisably ITSELF.
 *
 * The tests above hold "drawn, inert, and explained". They passed while the
 * disabled fill was taken from the border token, which renders near-white — so a
 * kept Buy read as an unknown greyed control rather than as "Buy, not here",
 * losing the identity it was being kept for. Colour is the part of that claim
 * they did not cover.
 */
describe('a disabled action keeps its own colour', () => {
  it('fades the blue rather than replacing it', () => {
    render(<KiteActionButtons onBuy={vi.fn()} buyDisabled variant="long" />);
    const buy = screen.getByRole('button', { name: 'BUY' });
    expect(buy.style.background).toContain('--k-blue');
    expect(buy.style.background).not.toContain('--k-border');
    // Faded enough to read as unavailable, not so faint it vanishes.
    expect(Number(buy.style.opacity)).toBeGreaterThan(0.2);
    expect(Number(buy.style.opacity)).toBeLessThan(0.6);
  });

  it('does not fade an enabled one', () => {
    render(<KiteActionButtons onBuy={vi.fn()} variant="long" />);
    const buy = screen.getByRole('button', { name: 'BUY' });
    expect(buy.style.opacity === '' || buy.style.opacity === '1').toBe(true);
  });

  it('keeps Sell orange rather than borrowing Buy\'s blue', () => {
    render(<KiteActionButtons onSell={vi.fn()} sellDisabled variant="long" />);
    const sell = screen.getByRole('button', { name: 'SELL' });
    expect(sell.style.background).toContain('--k-orange');
    expect(sell.style.background).not.toContain('--k-blue');
  });
});
