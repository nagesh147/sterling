/**
 * The COLUMNS control, shared by two different column models.
 *
 * SuperTrend had no columns button at all. Its five toggles lived in an
 * unlabelled gear inside the search bar, next to BEST LEG, in a panel that also
 * carried watchlist-only settings like Change type — so the options that
 * governed the table were mixed in with options that did nothing to it.
 *
 * The control is presentational because the two boards keep visible columns in
 * different places: the shared board in a BoardView keyed by ColumnId, SuperTrend
 * in the Kite settings store keyed by its own row spec. Mapping one onto the
 * other would be lossy in the direction that silently drops a column.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ColumnsMenu } from '../BoardFilters';

const items = (over: Partial<Record<string, boolean>> = {}) => [
  { id: 'exchange', label: 'Exchange', on: over.exchange ?? true, toggle: vi.fn() },
  { id: 'leg', label: 'Leg', on: over.leg ?? true, toggle: vi.fn() },
  { id: 'chg', label: 'Change', on: over.chg ?? true, toggle: vi.fn() },
];

describe('ColumnsMenu', () => {
  it('is labelled COLUMNS rather than being an unmarked gear', () => {
    render(<ColumnsMenu items={items()} />);
    expect(screen.getByRole('button', { name: 'Columns' })).toBeInTheDocument();
  });

  it('says how many columns are on when some are hidden', () => {
    render(<ColumnsMenu items={items({ leg: false })} />);
    expect(screen.getByRole('button', { name: /1 hidden/ })).toBeInTheDocument();
    expect(screen.getByText(/2\/3/)).toBeInTheDocument();
  });

  it('reports a toggle rather than owning the state', () => {
    const list = items();
    render(<ColumnsMenu items={list} />);
    fireEvent.click(screen.getByRole('button', { name: 'Columns' }));
    fireEvent.click(screen.getByLabelText('Leg'));
    expect(list[1].toggle).toHaveBeenCalledTimes(1);
  });

  it('offers "show all" only when something is hidden', () => {
    const onShowAll = vi.fn();
    const { rerender } = render(<ColumnsMenu items={items()} onShowAll={onShowAll} />);
    fireEvent.click(screen.getByRole('button', { name: 'Columns' }));
    expect(screen.queryByText('Show all columns')).not.toBeInTheDocument();

    rerender(<ColumnsMenu items={items({ chg: false })} onShowAll={onShowAll} />);
    expect(screen.getByText('Show all columns')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Show all columns'));
    expect(onShowAll).toHaveBeenCalled();
  });

  it('renders nothing when a table offers no choices', () => {
    // A control for nothing is worse than no control.
    const { container } = render(<ColumnsMenu items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

/**
 * SuperTrend's real column set.
 *
 * The first version of this menu offered the six `visibleWhen` groups —
 * exchange, leg, premium, chg, chgPct, dir — which is not what the table shows.
 * Four columns (Entry, SL, TSL, Target) hid behind `premium` together, and Exit
 * and LTP were `always` with no way to switch them off at all. So the menu named
 * groups while the header named columns, and they did not correspond.
 */
describe('SuperTrend column choices', () => {
  // Mirrors the pane's construction: real columns, capability-filtered.
  const build = (premiumAvailable: boolean, hidden: string[] = []) => {
    const LEFT = ['exc', 'leg', 'entry', 'sl', 'tsl', 'exit', 'target'];
    const RIGHT = ['chg', 'chgPct', 'dir', 'ltp'];
    const premiumCols = new Set(['entry', 'sl', 'tsl', 'target']);
    return [...LEFT, ...RIGHT]
      .filter((key) => (premiumCols.has(key) ? premiumAvailable : true))
      .map((key) => ({ id: key, label: key, on: !hidden.includes(key), toggle: vi.fn() }));
  };

  it('offers every column the table renders, not visibility groups', () => {
    render(<ColumnsMenu items={build(true)} />);
    fireEvent.click(screen.getByRole('button', { name: 'Columns' }));
    for (const key of ['exc', 'leg', 'entry', 'sl', 'tsl', 'exit', 'target', 'chg', 'chgPct', 'dir', 'ltp']) {
      expect(screen.getByLabelText(key)).toBeInTheDocument();
    }
    expect(screen.queryByLabelText('premium')).not.toBeInTheDocument();
  });

  it('drops the premium columns when the scan cannot fill them', () => {
    // A spot scan produces no premium, so Entry/SL/TSL/Target are unavailable
    // rather than hidden — offering them would invite switching on a column that
    // then does not appear.
    render(<ColumnsMenu items={build(false)} />);
    fireEvent.click(screen.getByRole('button', { name: 'Columns' }));
    for (const key of ['entry', 'sl', 'tsl', 'target']) {
      expect(screen.queryByLabelText(key)).not.toBeInTheDocument();
    }
    expect(screen.getByLabelText('exc')).toBeInTheDocument();
    expect(screen.getByLabelText('ltp')).toBeInTheDocument();
  });

  it('lets Exit and LTP be switched off, which the group model could not', () => {
    const items = build(true, ['exit', 'ltp']);
    render(<ColumnsMenu items={items} />);
    expect(screen.getByRole('button', { name: /2 hidden/ })).toBeInTheDocument();
  });

  it('counts hidden columns against the real total', () => {
    render(<ColumnsMenu items={build(true, ['chg'])} />);
    // 11 real columns, one off.
    expect(screen.getByText(/10\/11/)).toBeInTheDocument();
  });
});
