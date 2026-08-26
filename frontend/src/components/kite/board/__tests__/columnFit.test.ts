/**
 * Progressive column disclosure.
 *
 * This is what makes rendering 1:1 viable. Holding text size constant across
 * monitors — the thing every other site does — means the amount of room varies,
 * so the board has to shed columns rather than clip them behind a scrollbar.
 */
import { describe, it, expect } from 'vitest';
import { fitColumns, COLUMN_PRIORITY, ESSENTIAL_COLUMNS } from '../columnFit';

type Col = { id: string; width: number };

/** Same ids and widths the board uses. */
const COLS: Col[] = [
  { id: 'instrument', width: 0 },
  { id: 'status', width: 66 },
  { id: 'exchange', width: 40 },
  { id: 'leg', width: 78 },
  { id: 'entry', width: 96 },
  { id: 'stop', width: 56 },
  { id: 'trail', width: 56 },
  { id: 'target', width: 58 },
  { id: 'exit', width: 58 },
  { id: 'ltp', width: 70 },
  { id: 'time', width: 78 },
];

const ids = (r: { columns: Col[] }) => r.columns.map((c) => c.id);
const fit = (w: number) => fitColumns(COLS, w);

describe('a board with room keeps everything', () => {
  it('drops nothing when the columns fit', () => {
    const r = fitColumns(COLS, 5000);
    expect(ids(r)).toEqual(COLS.map((c) => c.id));
    expect(r.dropped).toEqual([]);
  });

  it('keeps everything before it has been measured', () => {
    // Width 0 means "no measurement yet". Stripping the table on first paint
    // and restoring it a frame later reads as a glitch.
    expect(ids(fit(0))).toEqual(COLS.map((c) => c.id));
    expect(ids(fit(-1))).toEqual(COLS.map((c) => c.id));
  });

  it('reports what the surviving set needs', () => {
    expect(fitColumns(COLS, 5000).required).toBeGreaterThan(0);
    expect(fitColumns(COLS, 5000).required).toBeLessThanOrEqual(5000);
  });
});

describe('when room runs short', () => {
  it('actually fits inside the width it was given', () => {
    for (const w of [1200, 900, 700, 520, 400]) {
      expect(fit(w).required, `width ${w}`).toBeLessThanOrEqual(w);
    }
  });

  it('sheds the least useful column first', () => {
    // Exchange before the stop; conviction before the price.
    const dropped = fit(700).dropped.map((c) => c.id);
    expect(dropped[0]).toBe('exchange');
    expect(dropped).not.toContain('entry');
  });

  it('sheds progressively, never re-adding as it narrows', () => {
    const wide = new Set(ids(fit(1000)));
    for (const id of ids(fit(600))) expect(wide.has(id), `${id} reappeared`).toBe(true);
  });

  it('keeps the instrument and its price whatever happens', () => {
    // A row without these says nothing at all, so they overflow rather than go.
    for (const w of [400, 200, 60]) {
      for (const id of ESSENTIAL_COLUMNS) expect(ids(fit(w)), `width ${w}`).toContain(id);
    }
  });

  it('stops rather than looping once only essentials remain', () => {
    const r = fit(10);
    expect(ids(r).sort()).toEqual([...ESSENTIAL_COLUMNS].sort());
  });

  it('drops in priority order all the way down', () => {
    const order = fit(300).dropped.map((c) => COLUMN_PRIORITY[c.id] ?? 10);
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });
});

describe('the fit accounts for more than column widths', () => {
  it('leaves room for the action buttons', () => {
    const without = fitColumns(COLS, 900).columns.length;
    const withReserve = fitColumns(COLS, 900, { reserve: 200 }).columns.length;
    expect(withReserve).toBeLessThan(without);
  });

  it('reserves a floor for the instrument cell, which flexes to zero width', () => {
    // Its declared width is 0 because it is the flexible cell; charging 0 for
    // it would let the fit promise columns there is no room to draw.
    const narrow = fitColumns(COLS, 700, { minInstrument: 150 }).columns.length;
    const wide = fitColumns(COLS, 700, { minInstrument: 400 }).columns.length;
    expect(wide).toBeLessThan(narrow);
  });

  it('charges for the gaps between cells', () => {
    expect(fitColumns(COLS, 800, { gap: 40 }).columns.length)
      .toBeLessThan(fitColumns(COLS, 800, { gap: 0 }).columns.length);
  });
});

describe('the user still outranks the fit', () => {
  it('only ever removes from what it was handed', () => {
    // Auto-drop narrows an already-filtered set; it can never switch a column
    // back on that someone turned off by hand.
    const userChose = COLS.filter((c) => c.id !== 'entry');
    expect(ids(fitColumns(userChose, 5000))).not.toContain('entry');
    expect(ids(fitColumns(userChose, 500))).not.toContain('entry');
  });

  it('does not mutate the array it was given', () => {
    const input = [...COLS];
    fitColumns(input, 400);
    expect(input).toHaveLength(COLS.length);
  });
});
