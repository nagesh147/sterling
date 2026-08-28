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
import { afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BOARD_COLUMNS_WITH_DAY_MOVE, COLUMNS, SignalBoard } from '../SignalBoard';
import type { BoardSignal } from '../boardTypes';
import { LEG_INDENT, ROW_METRICS, instrumentFlex } from '../signalRowSpec';

/*
 * These tests write to the PERSISTED settings store, which means localStorage.
 *
 * Left behind, that is a booby trap for whatever file runs next: a stray
 * `boardRenderer: 'shared'` makes a later test render a different component than
 * it was written against, and the failure surfaces far from its cause. This
 * suite already has a history of order-dependent flakes for exactly this reason,
 * so each file clears up after itself rather than only before itself.
 */
afterEach(() => localStorage.clear());


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

/**
 * A signal that resolved to no contract.
 *
 * An engine can fire on the underlying and then fail to find a listed option for
 * the strike and expiry it wants. Rendered as a bare row with nothing under it,
 * that looks like a loading state; the engine already knows why, so it says so.
 *
 * The distinction this rests on is `children: []` versus `children: undefined`.
 * ORB, Gamma Move and the ATM bot leave it undefined — their signals are one
 * instrument and always were — so they must NOT get the note. After `?? []` the
 * two cases are identical, which is the trap.
 */
describe('a signal with no contracts', () => {
  const NOTE = /No listed contract matched/;

  it('says why, in the row', () => {
    board({ signals: [sig({ children: [], reason: 'Strike 24000 is not listed for 27 Aug.' })] });
    expect(screen.getByText('Strike 24000 is not listed for 27 Aug.')).toBeInTheDocument();
  });

  it('falls back to a plain statement when the engine gave no reason', () => {
    board({ signals: [sig({ children: [], reason: null })] });
    expect(screen.getByText(NOTE)).toBeInTheDocument();
  });

  it('leaves a standalone signal alone', () => {
    // `children` undefined: ORB's rows are one instrument by nature, and a note
    // under every one of them would be nonsense.
    board({ signals: [sig({ reason: null })] });
    expect(screen.queryByText(NOTE)).toBeNull();
  });

  it('does not mistake an engine’s exit reason for a resolution failure', () => {
    // A standalone signal carrying a reason is the normal case, not a failure.
    board({ signals: [sig({ reason: 'Trail breached' })] });
    expect(screen.queryByText(NOTE)).toBeNull();
  });
});

/**
 * The engine's own inline badges.
 *
 * `origin` says where a signal came from and there is exactly one of those.
 * These are everything else worth seeing WITHOUT opening the row — and they are
 * data, not a render prop, so the board can draw them while knowing nothing
 * about what any engine's rules mean.
 *
 * The one that earns its place: a trail breach and a red-counter close are not
 * the same event, and they matter most when they disagree. The premium can be
 * through its trail while the counter has not flipped enough lines to close, and
 * that gap is where an open drawdown builds.
 */
describe('inline marks', () => {
  it('draws nothing when an engine supplies none', () => {
    const { container } = board({ signals: [sig()] });
    expect(container.textContent).not.toContain('TSL exit');
  });

  it('draws each one with its label', () => {
    board({
      signals: [sig({
        marks: [
          { label: 'TSL exit', tone: 'amber', hint: 'Closed by the trailing stop.' },
          { label: 're-entry', tone: 'dim', hint: 'Same trend re-arming.' },
          { label: 'Nav CONFIRMED', tone: 'green', hint: 'Navigator agrees.' },
        ],
      })],
    });
    for (const label of ['TSL exit', 're-entry', 'Nav CONFIRMED']) {
      expect(screen.getByText(label), label).toBeInTheDocument();
    }
  });

  it('keeps two marks with the same label but different tone apart', () => {
    // The React key is label+tone; a label alone would collide.
    board({
      signals: [sig({
        marks: [
          { label: 'exit', tone: 'amber', hint: 'a' },
          { label: 'exit', tone: 'dim', hint: 'b' },
        ],
      })],
    });
    expect(screen.getAllByText('exit')).toHaveLength(2);
  });
});

/**
 * The instrument column never gives up its width.
 *
 * It is the only flexible column on the row, so `flex: 1 1 150px` made it absorb
 * ALL the overflow whenever the board was narrower than its columns — and 150px
 * does not hold what the cell draws: an option renders as
 * "BANKNIFTY 26 Aug 57000 CE", around 166px, before the best-R and best-delta
 * badges beside it. A leg indents and gives back the same amount, taking it to
 * 136.
 *
 * The result was the worst possible truncation: the name of the contract clipped
 * while every column of numbers describing it stayed whole.
 */
describe('the instrument column', () => {
  it('grows but never shrinks', () => {
    // flex-shrink 0: the row overflows and scrolls rather than the name clipping.
    expect(instrumentFlex()).toMatch(/^1 0 /);
    expect(instrumentFlex(true)).toMatch(/^1 0 /);
  });

  it('puts the indent compensation in the BASIS, not in minWidth', () => {
    // A leg indents and must give the same back or its column runs past the
    // heading above it. That used to live in `minWidth`, which works only while
    // the cell can shrink — and it no longer can, so a minimum bounds nothing.
    expect(instrumentFlex(true)).toBe(`1 0 ${ROW_METRICS.instrumentMinWidth - LEG_INDENT}px`);
    expect(instrumentFlex()).toBe(`1 0 ${ROW_METRICS.instrumentMinWidth}px`);
  });

  it('keeps a leg’s column edge under its heading', () => {
    // The leg starts LEG_INDENT further right and is LEG_INDENT narrower, so the
    // right edges coincide. If these ever stop cancelling, every cell to the
    // right of the instrument drifts.
    const legStart = 16 + LEG_INDENT;
    const legWidth = ROW_METRICS.instrumentMinWidth - LEG_INDENT;
    expect(legStart + legWidth).toBe(16 + ROW_METRICS.instrumentMinWidth);
  });

  it('is wide enough for a full option label', () => {
    // "BANKNIFTY 26 Aug 57000 CE" is ~166px at 13px, plus two 12px badges and
    // their gaps. 150 was never enough.
    expect(ROW_METRICS.instrumentMinWidth).toBeGreaterThanOrEqual(190);
  });

  it('leaves a leg room even after the indent takes its cut', () => {
    // A leg reduces the cell by LEG_INDENT to keep the column's right edge under
    // its heading, so the usable width is this, not the full basis.
    expect(ROW_METRICS.instrumentMinWidth - LEG_INDENT).toBeGreaterThanOrEqual(170);
  });
});

/**
 * Wrapping a heading for dragging must not resize it.
 *
 * `DraggableColHeader` imposed `width: <the column's width>` with
 * `flex-shrink: 0`. A flex-sized column declares `width: 0` — the number is a
 * placeholder it never uses — so the instrument heading rendered a 200px label
 * inside a 0px box, overflowed it, and painted on top of itself and the heading
 * beside it. On screen "INSTRUMENT" came out as "INSEROMENT".
 *
 * Only reproducible with dragging ON, which is the default, and only on the
 * shared renderer: the bespoke table renders its instrument heading unwrapped.
 */
describe('a dragged heading keeps its own size', () => {
  const instrumentWrapper = (container: HTMLElement) =>
    container.querySelector('[data-col-key="instrument"]') as HTMLElement | null;

  it('never boxes a flex-sized heading at its placeholder width', () => {
    const { container } = board({ onReorderColumn: vi.fn() });
    const wrap = instrumentWrapper(container);
    expect(wrap, 'the instrument heading is draggable').not.toBeNull();
    expect(wrap!.style.width, 'not pinned to the placeholder 0').toBe('');
    expect(wrap!.style.flex, 'sized by flex instead').toBe(instrumentFlex());
  });

  it('lays the heading out as a flex child so it fills the wrapper', () => {
    // Without this the button inside a grown wrapper stops at its min-width.
    const { container } = board({ onReorderColumn: vi.fn() });
    expect(instrumentWrapper(container)!.style.display).toBe('flex');
  });

  it('still pins a fixed-width heading to its width', () => {
    const { container } = board({ onReorderColumn: vi.fn() });
    const ltp = container.querySelector('[data-col-key="ltp"]') as HTMLElement;
    expect(ltp.style.width).toBe('70px');
    expect(ltp.style.flexShrink).toBe('0');
  });

  it('is the only column that needs the flex path', () => {
    // If another flex-sized column appears, it must pass `flex` too — this
    // catches the next one rather than waiting for it to smear on screen.
    const placeholders = COLUMNS.filter((c) => c.width === 0).map((c) => c.id);
    expect(placeholders).toEqual(['instrument']);
  });
});
