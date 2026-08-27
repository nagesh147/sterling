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
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const read = (p: string) => readFileSync(resolve(__dirname, p), 'utf8');
const superTrend = read('../../SterlingKiteEnginePane.tsx');
const sharedBoard = read('../SignalBoard.tsx');

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
    expect(read('../signalRowSpec.ts')).toContain("LEG_BG = 'var(--k-surface-2)'");
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
