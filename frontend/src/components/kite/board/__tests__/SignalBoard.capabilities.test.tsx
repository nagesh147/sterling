/**
 * The three capabilities SuperTrend's bespoke table used to own alone.
 *
 * Draggable column headings, rows that scroll sideways, and controls living in
 * the row were the whole reason a second table implementation survived: moving
 * SuperTrend onto this component would have cost all three. They are optional
 * props now, so the move costs nothing and every engine can offer them.
 *
 * The property that protects the other four engines is that omitting a prop
 * leaves the board exactly as it was — so each capability is checked both ways.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SignalBoard } from '../SignalBoard';
import type { BoardSignal } from '../boardTypes';

const IST = (5 * 60 + 30) * 60_000;
const NOW = Date.UTC(2026, 7, 21, 10, 30) - IST;

function sig(over: Partial<BoardSignal> = {}): BoardSignal {
  return {
    id: 'a',
    engine: 'orb',
    underlying: 'NIFTY',
    instrument: {
      symbol: 'NIFTY26AUG24000CE', exchange: 'NFO', kind: 'option',
      optionType: 'CE', strike: 24000, expiry: '2026-08-27', lotSize: 75,
      quoteKey: 'NFO:NIFTY26AUG24000CE',
    },
    direction: 'long',
    status: 'armed',
    atMs: NOW,
    levels: { ltp: 18, entry: 18, stop: 14, trail: null, target: 26, exit: null },
    sizing: { lots: 2, quantity: 150, atRiskInr: 2700, deployedInr: 2700 },
    score: null,
    reason: null,
    sections: [],
    ...over,
  };
}

function board(props: Partial<React.ComponentProps<typeof SignalBoard>> = {}) {
  return render(
    <SignalBoard
      signals={[sig()]}
      openId={null}
      onToggle={() => {}}
      nowMs={NOW}
      {...props}
    />,
  );
}

describe('draggable column headings', () => {
  it('are not offered unless the board is given a reorder callback', () => {
    const { container } = board();
    // No wrapper at all — a board that does not reorder renders exactly what it
    // rendered before this prop existed.
    expect(container.querySelector('[data-col-key]')).toBeNull();
  });

  it('appear as drop targets once it is', () => {
    const { container } = board({ onReorderColumn: vi.fn() });
    const heads = container.querySelectorAll('[data-col-key]');
    expect(heads.length).toBeGreaterThan(1);
    expect((heads[0] as HTMLElement).style.cursor).toBe('grab');
    // All in one run, so any heading can be dropped anywhere.
    const groups = new Set([...heads].map((h) => h.getAttribute('data-col-group')));
    expect(groups).toEqual(new Set(['board']));
  });

  it('still sort when clicked — dragging must not swallow the click', () => {
    const onSortChange = vi.fn();
    board({ onReorderColumn: vi.fn(), onSortChange });
    fireEvent.click(screen.getByRole('button', { name: /LTP/i }));
    expect(onSortChange).toHaveBeenCalled();
  });
});

describe('sideways row scrolling', () => {
  it('is off by default, and the row clips instead', () => {
    const { container } = board();
    const row = container.querySelector('.sb-row') as HTMLElement;
    expect(row.className).not.toContain('sb-row-scroll');
    expect(row.style.overflowX).toBe('hidden');
  });

  it('turns the row and the header into one scrolling pair', () => {
    const { container } = board({ rowScroll: true });
    const row = container.querySelector('.sb-row') as HTMLElement;
    expect(row.className).toContain('sb-row-scroll');
    expect(row.style.overflowX).toBe('auto');
    // The header has to move with them or the columns stop lining up.
    const head = container.querySelector('.sb-head-row') as HTMLElement;
    expect(head.style.overflowX).toBe('auto');
  });
});

describe('row controls', () => {
  it('are absent unless the engine supplies them', () => {
    board();
    expect(screen.queryByRole('button', { name: 'Buy' })).toBeNull();
  });

  it('render inside the row when it does', () => {
    board({ renderRowActions: (s) => <button type="button">Buy {s.underlying}</button> });
    const buy = screen.getByRole('button', { name: /Buy NIFTY/ });
    expect(buy.closest('.sb-row'), 'in the row, not beside the board').not.toBeNull();
  });

  it('do not toggle the row they sit in', () => {
    // The row is itself a button. Without stopping propagation, pressing Buy
    // would also expand the row underneath the order window.
    const onToggle = vi.fn();
    board({
      onToggle,
      renderRowActions: () => <button type="button">Buy</button>,
    });
    fireEvent.click(screen.getByRole('button', { name: 'Buy' }));
    expect(onToggle, 'the row must not expand').not.toHaveBeenCalled();
  });

  it('cannot be switched off by the column picker', () => {
    // They are rendered outside the cell map on purpose: an engine's actions are
    // not a column and must not disappear with one.
    const { container } = board({
      hidden: new Set(['ltp', 'entry', 'stop', 'trail', 'target', 'time'] as never),
      renderRowActions: () => <button type="button">Buy</button>,
    });
    expect(container.querySelector('.sb-row')?.textContent).toContain('Buy');
  });
});
