/**
 * The two signal tables stay styled alike by construction, not by coincidence.
 *
 * SuperTrend's table is a bespoke implementation; Adaptive Edge's is the shared
 * `SignalBoard`. They are supposed to look like one product, and they mostly did
 * — but SuperTrend restated the numbers as literals instead of reading the spec,
 * so the two agreed only until somebody edited one of them.
 *
 * These assertions are deliberately about the SOURCE rather than the rendered
 * output. A render test would need the authenticated pane and its hooks, and it
 * would still only prove the two matched on the day it ran. What actually breaks
 * parity is a literal creeping back in, so that is what is checked.
 */
import { describe, it, expect } from 'vitest';

// `?raw` rather than node:fs — Vite's own mechanism, typed by the `vite/client`
// reference in `src/vite-env.d.ts`. Reading through node:fs works at runtime but
// needs @types/node, which this tsconfig does not pull in.
import superTrend from '../../SterlingKiteEnginePane.tsx?raw';
import sharedBoard from '../SignalBoard.tsx?raw';
import rowSpec from '../signalRowSpec.ts?raw';

/**
 * The leg-row CSS block, which is where the geometry lives.
 *
 * Ending the slice at the next `}` does not work: the block interpolates
 * `${ROW_METRICS.gap}` and friends, so the first closing brace belongs to the
 * interpolation rather than to the rule. The rule's own brace is the one sitting
 * alone at the block's indent.
 */
const legRowCss = (() => {
  const start = superTrend.indexOf('.st-leg-row {');
  expect(start).toBeGreaterThan(-1);
  const end = superTrend.indexOf('\n        }', start);
  expect(end).toBeGreaterThan(start);
  return superTrend.slice(start, end);
})();

describe('SuperTrend reads the shared row spec', () => {
  it('takes its geometry from ROW_METRICS, not from literals', () => {
    for (const token of ['ROW_METRICS.gap', 'ROW_METRICS.legHeight', 'ROW_METRICS.legPadding']) {
      expect(legRowCss).toContain(token);
    }
    // The literals these replaced. Any of them back means someone hardcoded a
    // value that the shared board no longer controls.
    expect(legRowCss).not.toMatch(/gap:\s*\d+px/);
    expect(legRowCss).not.toMatch(/padding:\s*0\s+\d+px/);
  });

  it('uses a minimum row height, never a fixed one', () => {
    // A fixed height clips a cell that wraps; the shared row has always used a
    // minimum. This is the one geometry difference that could lose data.
    expect(legRowCss).toContain('min-height:');
    expect(legRowCss).not.toMatch(/[^-]height:\s*\d/);
  });
});

describe('both tables share one leg shade', () => {
  it('is defined once and imported by both', () => {
    expect(rowSpec).toContain("LEG_BG = 'var(--k-surface-2)'");
    // Neither file may hold its own copy of the string.
    for (const [name, src] of [['SuperTrend', superTrend], ['SignalBoard', sharedBoard]] as const) {
      expect(src, `${name} imports LEG_BG`).toContain('LEG_BG');
      expect(src, `${name} has no private copy of the shade`).not.toContain("'var(--k-surface-2)'");
    }
  });

  it('does not also draw a line under every leg', () => {
    // The shade is what separates rows. Drawing both gives a heavier grid than
    // the shared board, which is the difference this pairing exists to remove.
    expect(legRowCss).toContain('border-bottom: 1px solid transparent');
    expect(sharedBoard).toContain("isLeg ? 'transparent' : k.border");
  });

  it('reserves the accent gutter so cells never shift sideways', () => {
    expect(legRowCss).toContain('border-left: 3px solid transparent');
  });
});

/**
 * The header strips.
 *
 * These were the real gap, and the first pass at this file missed them entirely
 * because it only ever looked at the row. SuperTrend's column headings were 12px
 * regular sentence-case against the shared board's 8.5px bold uppercase, so the
 * two tables could share every row token and still look nothing alike — the
 * heading strip is the first thing you read.
 */
describe('both tables share one heading scale', () => {
  it('defines the column-heading type once', () => {
    expect(rowSpec).toContain('HEAD_METRICS');
    expect(rowSpec).toContain("fontSize: 8.5");
    for (const [name, src] of [['SuperTrend', superTrend], ['SignalBoard', sharedBoard]] as const) {
      expect(src, `${name} reads HEAD_METRICS`).toContain('HEAD_METRICS.fontSize');
      expect(src, `${name} reads the heading transform`).toContain('HEAD_METRICS.textTransform');
    }
  });

  it('leaves no sentence-case heading strip behind in SuperTrend', () => {
    // The exact literals the old strip used. Their return means somebody set a
    // heading font locally instead of reading the spec.
    expect(superTrend).not.toContain("padding: '12px 16px', fontSize: 12");
    expect(superTrend).not.toMatch(/fontSize: 12, fontWeight: 400, color: k\.dim/);
  });

  it('defines the group band once, and both read it', () => {
    expect(rowSpec).toContain('DAY_HEAD_METRICS');
    for (const [name, src] of [['SuperTrend', superTrend], ['SignalBoard', sharedBoard]] as const) {
      expect(src, `${name} reads DAY_HEAD_METRICS`).toContain('DAY_HEAD_METRICS.padding');
      expect(src, `${name} reads the band transform`).toContain('DAY_HEAD_METRICS.textTransform');
    }
  });

  it('puts the group band on the surface shade, not the row background', () => {
    // Scoped to the band itself. Searching the whole file for `background: k.bg`
    // also hits the trade-rules panel, which legitimately sits on the row
    // background -- the first version of this assertion did exactly that.
    const start = superTrend.indexOf('className="st-group-header"');
    expect(start).toBeGreaterThan(-1);
    const band = superTrend.slice(start, start + 600);
    // A band drawn on k.bg is invisible against the rows it separates, which is
    // what SuperTrend's was.
    expect(band).toContain('background: k.surface');
    expect(band).not.toContain('background: k.bg');
  });
});

/**
 * The cells.
 *
 * The shared board gives every non-instrument cell one size (11px) and tabular
 * figures. SuperTrend's cells ran at 10, 11 and 13 — the stop and trail columns
 * a size smaller, LTP a size larger and semibold — and none of them asked for
 * tabular figures, so columns of prices came out ragged where the shared board's
 * line up.
 */
describe('both tables share one cell scale', () => {
  /** The leg row's cell renderers. */
  const legCells = (() => {
    const start = superTrend.indexOf('const renderLeftCell');
    expect(start).toBeGreaterThan(-1);
    const end = superTrend.indexOf('const renderRightCell', start);
    expect(end).toBeGreaterThan(start);
    return superTrend.slice(start, superTrend.indexOf('</div>', end));
  })();

  it('sizes every cell from ROW_METRICS', () => {
    expect(legCells).toContain('ROW_METRICS.cellFontSize');
    // 10 and 13 were the two off-scale sizes. A bare `fontSize: 10` or 13 back
    // in the cells means somebody sized text rather than a glyph.
    expect(legCells).not.toMatch(/fontSize: 10[,}]/);
    expect(legCells).not.toMatch(/fontSize: 13[,}]/);
  });

  it('renders figures tabular so columns of prices line up', () => {
    // On the wrapper, not per cell: nine spans each remembering it is nine
    // chances to forget.
    const wrappers = superTrend.match(/fontVariantNumeric: 'tabular-nums'/g) ?? [];
    expect(wrappers.length).toBeGreaterThanOrEqual(2);
    expect(sharedBoard).toContain("fontVariantNumeric: 'tabular-nums'");
  });
});
