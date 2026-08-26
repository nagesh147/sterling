/**
 * Grouped signals: one idea, its contracts nested underneath.
 *
 * SuperTrend produces ~50 signals carrying ~286 legs, and NIFTY alone can be
 * 37 strikes. Flattened that is a board nobody can read, so the shape of the
 * grouping — and what the parent is allowed to claim — is worth pinning.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { SignalBoard, visibleColumns, COLUMNS } from '../SignalBoard';
import { flattenSignals, hasGroups, type BoardSignal } from '../boardTypes';
import { supertrendToBoard } from '../supertrendAdapter';
import type { EngineSignalRow, OptionLeg } from '../../../../types/kiteEngine';

const IST = (5 * 60 + 30) * 60_000;
const NOW = Date.UTC(2026, 7, 21, 10, 30) - IST;

const leg = (over: Partial<OptionLeg> = {}): OptionLeg => ({
  moneyness: 'ATM', option_type: 'CE', option_symbol: 'NIFTY26AUG24000CE',
  strike: 24000, expiry: '2026-08-27', lot_size: 75,
  premium_spot: 200, entry_sl: 160, premium_sl: 185, is_active: true, ...over,
});

const row = (over: Partial<EngineSignalRow> = {}): EngineSignalRow => ({
  underlying: 'NIFTY 50', token: 1, exchange: 'NFO', regime: 'BULL',
  alignment: { fast: 1, mid: 1, slow: 1 }, direction: 'long', option_type: 'CE',
  legs: [leg(), leg({ option_symbol: 'NIFTY26AUG24100CE', strike: 24100 })],
  spot: 24100, stop_loss: 24000, score: 82, timestamp_ms: NOW, is_active: true,
  source: 'spot', ...over,
});

describe('the SuperTrend adapter groups instead of flattening', () => {
  it('makes one row per signal, not one per leg', () => {
    const board = supertrendToBoard([row(), row({ timestamp_ms: NOW - 1000 })]);
    expect(board).toHaveLength(2);
    expect(board[0].children).toHaveLength(2);
    expect(flattenSignals(board)).toHaveLength(6);
    expect(hasGroups(board)).toBe(true);
  });

  it('leaves the parent’s price columns empty', () => {
    // A thesis has no premium. Lifting one leg's numbers up to stand for the
    // rest would be a lie about which strike you would actually trade.
    const [parent] = supertrendToBoard([row()]);
    expect(parent.levels).toEqual({ ltp: null, entry: null, stop: null, trail: null, target: null, exit: null });
    expect(parent.sizing.atRiskInr).toBeNull();
  });

  it('names the underlying, not a contract', () => {
    const [parent] = supertrendToBoard([row()]);
    expect(parent.instrument.symbol).toBe('NIFTY 50');
    expect(parent.instrument.kind).toBe('index');
    expect(parent.children![0].instrument.symbol).toBe('NIFTY26AUG24000CE');
  });

  it('keeps the thesis evidence on the parent and the contract detail on the legs', () => {
    const [parent] = supertrendToBoard([row()]);
    expect(parent.sections.map((s) => s.title)).toContain('Trend & volatility');
    // The leg keeps its own exit rule; the parent does not pretend to have one.
    expect(parent.children![0].levels.entry).toBe(200);
  });

  it('takes the liveliest leg’s status', () => {
    // One running contract means the signal is running, even if others closed.
    const mixed = row({ legs: [leg({ is_active: false }), leg({ option_symbol: 'B', is_active: true })] });
    expect(supertrendToBoard([mixed])[0].status).toBe('running');
  });

  it('is ended only when every leg has ended', () => {
    const done = row({ legs: [leg({ is_active: false }), leg({ option_symbol: 'B', is_active: false })] });
    expect(supertrendToBoard([done])[0].status).toBe('ended');
  });
});

describe('rendering a grouped board', () => {
  const board = supertrendToBoard([row()]);
  const show = (props: Partial<React.ComponentProps<typeof SignalBoard>> = {}) =>
    render(<SignalBoard signals={board} openId={null} onToggle={() => {}} nowMs={NOW} {...props} />);

  it('shows the signal with its contracts already under it', () => {
    // A board exists to show tradable contracts; making each one cost a click
    // on the board whose job is to show them is worse than the repetition
    // grouping was introduced to fix.
    const { container } = show();
    expect(screen.getByRole('button', { name: /NIFTY 50 long, 2 contracts/ })).toBeInTheDocument();
    // InstrumentLabel splits the contract into readable parts, so match the
    // rendered row rather than the raw symbol.
    expect(container.querySelectorAll('.sb-row:not(.sb-parent)')).toHaveLength(2);
  });

  it('folds a signal away when it is collapsed', () => {
    const { container } = show({ collapsedGroups: new Set([board[0].id]) });
    expect(container.querySelectorAll('.sb-row:not(.sb-parent)')).toHaveLength(0);
  });

  it('states how many contracts the signal holds', () => {
    const { container } = show();
    const parent = container.querySelector('.sb-parent') as HTMLElement;
    expect(parent).toHaveTextContent('2 contracts');
  });

  it('renders the signal as a header, not a line of empty cells', () => {
    // A signal has no premium, strike or stop of its own. Drawing it in the
    // legs' columns produced blanks pretending to be data.
    const { container } = show();
    const parent = container.querySelector('.sb-parent') as HTMLElement;
    expect(parent.textContent).not.toMatch(/—/);
    expect(parent).toHaveTextContent('NIFTY 50');
  });

  it('shows the underlying’s own price on the header', () => {
    const { container } = show();
    expect(container.querySelector('.sb-parent')).toHaveTextContent('24,100.00');
  });

  it('lists every contract of the signal', () => {
    const { container } = show();
    const legs = [...container.querySelectorAll('.sb-row:not(.sb-parent)')].map((l) => l.textContent ?? '');
    expect(legs[0]).toMatch(/24000/);
    expect(legs[1]).toMatch(/24100/);
  });

  it('asks the caller to open a group rather than owning it', () => {
    const onToggleGroup = vi.fn();
    const onToggle = vi.fn();
    show({ onToggleGroup, onToggle });
    fireEvent.click(screen.getByRole('button', { name: /NIFTY 50 long, 2 contracts/ }));
    // A parent's chevron folds its contracts; it does not open its own detail.
    expect(onToggleGroup).toHaveBeenCalledWith(board[0].id);
    expect(onToggle).not.toHaveBeenCalled();
  });

  it('indents a leg so it still reads as part of the signal after a scroll', () => {
    const { container } = show();
    const [parent, first] = [...container.querySelectorAll('.sb-row')] as HTMLElement[];
    expect(parseFloat(first.style.paddingLeft)).toBeGreaterThan(parseFloat(parent.style.paddingLeft || '0'));
  });

  it('keeps the price columns, which only the legs can fill', () => {
    // Asking only the parents would drop every price column on exactly the
    // board that needs them most.
    const ids = visibleColumns(board, COLUMNS.map((c) => c.id)).map((c) => c.id);
    expect(ids).toContain('entry');
    expect(ids).toContain('stop');
  });

  it('never labels a signal by the security kind', () => {
    // The parent of an LT signal used to read "LTINDEX · LONG". LT is a stock.
    show();
    expect(screen.queryByText(/INDEX · LONG/)).not.toBeInTheDocument();
  });

  it('lets each contract carry its own type, the way SuperTrend does', () => {
    // A leg leads with the contract, and the contract name already says CE or
    // PE — so it needs no separate pill, and the header needs no type at all.
    const { container } = show();
    const leg = container.querySelectorAll('.sb-row:not(.sb-parent)')[0] as HTMLElement;
    expect(leg.textContent).toMatch(/CE/);
    const parent = container.querySelector('.sb-parent') as HTMLElement;
    expect(parent.textContent).not.toMatch(/·\s*LONG/);
  });

  it('says only the direction when the legs disagree on type', () => {
    const mixed = supertrendToBoard([row({
      legs: [leg(), leg({ option_symbol: 'NIFTY26AUG24000PE', option_type: 'PE' })],
    })]);
    const { container } = render(<SignalBoard signals={mixed} openId={null} onToggle={() => {}} nowMs={NOW} />);
    const legs = [...container.querySelectorAll('.sb-row:not(.sb-parent)')] as HTMLElement[];
    // Each contract states its own type; they disagree, so nothing on the
    // header speaks for both.
    expect(legs[0].textContent).toMatch(/CE/);
    expect(legs[1].textContent).toMatch(/PE/);
  });

  it('lets the symbol still reach the full detail page', () => {
    const onOpenDetail = vi.fn();
    const { container } = show({ onOpenDetail });
    const parent = container.querySelector('.sb-row') as HTMLElement;
    fireEvent.click(within(parent).getByRole('button', { name: /Open NIFTY 50 detail/ }));
    expect(onOpenDetail).toHaveBeenCalled();
  });
});
