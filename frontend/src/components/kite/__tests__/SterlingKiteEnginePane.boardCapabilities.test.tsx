/**
 * The three board capabilities, as settings.
 *
 * SuperTrend's table grew three things the shared board never had: draggable
 * column headings, rows that scroll sideways on their own, and order buttons in
 * the row. They were the reason for keeping a second table implementation, and
 * the reason a wholesale swap meant choosing for the operator which of them
 * they could live without.
 *
 * They are choices now. What matters here is that each one actually reaches the
 * DOM — a settings checkbox wired to nothing is worse than no checkbox, because
 * it reads as a decision that has been taken.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

const cfg = {
  engine_enabled: true, trail_target: 'fast', exit_mode: 'one_red',
  strike_moneyness: ['ATM'], scan_source: 'derivatives',
  scan_expiries: ['weekly'], scan_expiries_indices: null, scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50'], scan_stocks: [], scan_all_stocks: false,
  auto_execute: false, risk_sizing: true, risk_pct: 1, max_lots: 10,
  stop_mode: 'both', directional_mode: false, vehicle: 'otm_options',
  enabled_vehicles: ['otm_options'], itm_depth: 'ITM10', target_delta: null,
  futures_expiry: 'near', adx_min: null, atr_pct_min: null, wire_risk_infra: false,
};

const SYMBOL = 'BANKNIFTY26AUG57000CE';

function makeRow() {
  return {
    underlying: 'NIFTY BANK', token: 1, exchange: 'NFO', regime: 'BULL',
    alignment: { fast: 1, mid: 1, slow: 1 }, direction: 'long', option_type: 'CE',
    spot: 57147.5, stop_loss: 56891.3, entry_sl: 56500, exit_state: '0/3 red',
    score: 85, timestamp_ms: 1_785_404_700_000, source: 'spot',
    is_active: true, is_fresh: false, target: null,
    legs: [{
      moneyness: 'ITM1', option_type: 'CE', option_symbol: SYMBOL, strike: 57000,
      expiry: '2026-08-25', lot_size: 35, token: 1001, is_active: true,
      premium_spot: 1000, premium_sl: 900, entry_sl: 850, premium_target: null,
    }],
  };
}

function mockPane() {
  vi.doMock('../../../hooks/useSterlingKiteEngine', () => ({
    useEngineConfig: () => ({ data: cfg }),
    useSetEngineConfig: () => ({ mutate: vi.fn() }),
    usePatchEngineConfig: () => ({ mutate: vi.fn() }),
    useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
    useEngineSignals: () => ({
      data: {
        generated_ms: 1, scanning: false, scanning_label: '', rows: [makeRow()],
        next_scan_ms: 0, auto_scan: false, market_open: true,
      },
    }),
    useRunScan: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(() => Promise.resolve()), isPending: false }),
    useCancelScan: () => ({ mutate: vi.fn(), isPending: false }),
    useStockRegistry: () => ({ data: [] }),
  }));
  vi.doMock('../../../hooks/useKite', async () => {
    const actual: any = await vi.importActual('../../../hooks/useKite');
    return { ...actual, useKiteQuote: () => ({ data: { [`NFO:${SYMBOL}`]: { last_price: 1100 } } }) };
  });
}

/** The store the PANE uses — see the note in the migration test about instances. */
async function store() {
  return (await import('../../../store/useKiteSettings')).useKiteSettings;
}

async function renderPane() {
  const { SterlingKiteEnginePane: Pane } = await import('../SterlingKiteEnginePane');
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <Pane onSelectSignal={vi.fn()} />
    </QueryClientProvider>,
  );
}

const legRow = () => document.querySelector('.st-leg-row') as HTMLElement | null;

describe('board capabilities reach the DOM', () => {
  beforeEach(() => { localStorage.clear(); vi.resetModules(); });

  it('scrolls rows sideways by default, and stops when switched off', async () => {
    mockPane();
    await renderPane();
    expect(legRow()?.className, 'on by default').toContain('st-row-scroll');
  });

  it('drops the scroll class when the setting is off', async () => {
    (await store()).setState({ boardRowScroll: false });
    mockPane();
    await renderPane();
    const cls = legRow()?.className ?? '';
    expect(cls).toContain('st-leg-row');
    expect(cls, 'no sideways scroll').not.toContain('st-row-scroll');
  });

  it('makes headings draggable by default and plain when off', async () => {
    mockPane();
    await renderPane();
    const draggable = document.querySelector('[data-col-key]') as HTMLElement | null;
    expect(draggable, 'a column heading is rendered').not.toBeNull();
    expect(draggable!.style.cursor, 'draggable by default').toBe('grab');
  });

  it('leaves the heading a plain sort control when dragging is off', async () => {
    (await store()).setState({ boardDragColumns: false });
    mockPane();
    await renderPane();
    const head = document.querySelector('[data-col-key]') as HTMLElement;
    expect(head.style.cursor, 'no grab cursor').not.toBe('grab');
    // Still laid out identically — a different element shape here would shift
    // every column out from under its heading.
    expect(head.getAttribute('data-col-key')).toBeTruthy();
    expect(head.style.width).toBeTruthy();
  });

  it('keeps the order buttons in the row by default', async () => {
    mockPane();
    await renderPane();
    expect(document.querySelector('.st-actions-persistent'),
           'the trade path is in the row unless asked otherwise').not.toBeNull();
  });

  it('removes them from the row when the setting is off', async () => {
    (await store()).setState({ boardRowActions: false });
    mockPane();
    await renderPane();
    expect(document.querySelector('.st-actions-persistent')).toBeNull();
  });

  it('MOVES the trade buttons rather than deleting them', async () => {
    // The setting's own description says the buttons move into the row you
    // expand. They were inline closures on the collapsed row only, so switching
    // it off removed Buy from the app entirely — the description promising a
    // relocation that did not happen. On an order path that is the worst version
    // of this bug.
    (await store()).setState({ boardRowActions: false });
    mockPane();
    await renderPane();

    // Expand the leg.
    const row = legRow();
    expect(row).not.toBeNull();
    fireEvent.click(row!);

    const buys = screen.queryAllByTitle(/buy/i);
    expect(buys.length, 'Buy is reachable from the expanded row, exactly once').toBe(1);
  });

  it('offers Buy exactly once, whichever way the setting is set', async () => {
    // The property that matters is not where the strip lives but that the action
    // appears once: never zero (unreachable) and never twice (two Buy buttons on
    // one contract is an invitation to double-fire an order).
    mockPane();
    await renderPane();
    fireEvent.click(legRow()!);
    expect(screen.queryAllByTitle(/buy/i).length, 'row carries it').toBe(1);
  });
});

describe('the settings panel offers all three', () => {
  beforeEach(() => { localStorage.clear(); vi.resetModules(); });

  it('names each one in the board settings drawer, wired to the store', async () => {
    mockPane();
    await renderPane();

    // Open the drawer the way an operator does.
    fireEvent.click(screen.getByTitle('Signal table settings'));

    const s = await store();
    for (const [label, key] of [
      ['Drag columns to reorder', 'boardDragColumns'],
      ['Scroll rows sideways', 'boardRowScroll'],
      ['Order buttons in the row', 'boardRowActions'],
    ] as const) {
      const row = screen.getByText(label);
      const box = row.querySelector('input[type=checkbox]') as HTMLInputElement | null;
      expect(box, `${label} is a checkbox`).not.toBeNull();
      expect(box!.checked, `${label} starts on`).toBe(true);

      // And it is wired: pressing it changes the setting the board reads.
      fireEvent.click(box!);
      expect(s.getState()[key], `${label} is wired to ${key}`).toBe(false);
    }
  });

  it('stops promising draggable columns once dragging is off', async () => {
    (await store()).setState({ boardDragColumns: false });
    mockPane();
    await renderPane();
    fireEvent.click(screen.getByTitle('Signal table settings'));
    // The footer hint used to state it unconditionally.
    expect(screen.queryByText(/drag column headers to reorder/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Column dragging is off/i)).toBeInTheDocument();
  });
});
