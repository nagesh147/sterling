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
import { BOARD_COLUMNS_WITH_DAY_MOVE, SignalBoard } from '../SignalBoard';
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

/**
 * Today's move as rendered columns.
 *
 * The tinting is the part worth guarding: it is a subscription, not a snapshot.
 * Reading `useKiteSettings.getState()` inside the cell renderer creates no
 * subscription, so toggling the preference would change nothing until something
 * else repainted the board — which is the exact silent-toggle bug this same
 * setting had on SuperTrend's table.
 */
describe('today’s move', () => {
  const withMove = (abs: number | null, pct: number | null) =>
    sig({ dayMove: abs == null && pct == null ? null : { abs, pct } });

  // Requested explicitly: these three are not in the shared list, because only
  // an adapter with live quotes can fill them. See BOARD_COLUMNS_WITH_DAY_MOVE.
  const moveBoard = (signals: ReturnType<typeof sig>[]) =>
    board({ signals, columns: BOARD_COLUMNS_WITH_DAY_MOVE });

  it('renders rupees, percent and a direction mark', () => {
    moveBoard([withMove(10, 5)]);
    expect(screen.getByText('10.00')).toBeInTheDocument();
    expect(screen.getByText('5.00%')).toBeInTheDocument();
    expect(screen.getByText('▲')).toBeInTheDocument();
  });

  it('shows a dash, never a zero, when there is no quote', () => {
    // A zero reads as "flat"; the truth is "not known".
    const { container } = moveBoard([withMove(null, null)]);
    expect(container.textContent).not.toContain('0.00%');
  });

  it('marks a flat instrument without pointing an arrow nowhere', () => {
    moveBoard([withMove(0, 0)]);
    expect(screen.getByText('∘')).toBeInTheDocument();
    expect(screen.queryByText('▲')).toBeNull();
  });

  it('prints rupees with a dash for percent when the feed gave no base', () => {
    moveBoard([withMove(12, null)]);
    expect(screen.getByText('12.00')).toBeInTheDocument();
    expect(screen.queryByText(/12\.00%/)).toBeNull();
  });

  it('tints by the move, and drops the tint when the preference is off', async () => {
    const { useKiteSettings } = await import('../../../../store/useKiteSettings');
    useKiteSettings.setState({ showPriceDirection: true });
    const up = moveBoard([withMove(10, 5)]);
    expect(screen.getByText('10.00').style.color).toContain('green');
    up.unmount();

    useKiteSettings.setState({ showPriceDirection: false });
    moveBoard([withMove(10, 5)]);
    const colour = screen.getByText('10.00').style.color;
    expect(colour).not.toContain('green');
    expect(colour).not.toContain('red');
    useKiteSettings.setState({ showPriceDirection: true });
  });
});
