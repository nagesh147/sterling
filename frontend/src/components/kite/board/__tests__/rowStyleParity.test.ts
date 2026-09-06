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
    for (const token of ['ROW_METRICS.gap', 'ROW_METRICS.legHeight']) {
      expect(legRowCss).toContain(token);
    }
    // A bare `gap: 16px` back means someone hardcoded a value the shared board
    // no longer controls.
    expect(legRowCss).not.toMatch(/gap:\s*\d+px/);
    // The leg's own padding is the indented form rather than `legPadding` —
    // `legPadding` is the un-indented value, which the parent row still uses.
    expect(legRowCss).toContain('${16 + LEG_INDENT}px');
    expect(superTrend).toContain('padding: ROW_METRICS.parentPadding');
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

  it('defines the group band once, for the table that still has one', () => {
    // The shared board's DAY band is gone: it printed "LIVE NOW / 8 signals"
    // above each group, restating a date every row already carries in its Time
    // column. The grouping itself stays — rows are still bucketed by trading
    // day, live first — so only the label went.
    //
    // SuperTrend still bands by UNDERLYING, which is a different grouping and a
    // real one, so the tokens stay defined and it stays the reader.
    expect(rowSpec).toContain('DAY_HEAD_METRICS');
    expect(superTrend).toContain('DAY_HEAD_METRICS.padding');
    expect(superTrend).toContain('DAY_HEAD_METRICS.textTransform');
  });

  it('labels the shared board day band from sessionDayLabel', () => {
    // Pin the CALL, not the variable name. This asserted `nowMs`, which was
    // renamed to `effectiveNowMs` when the board became replay-aware — the
    // behaviour never changed, only the identifier, and the test went red for
    // a rename.
    expect(sharedBoard).toContain('sessionDayLabel(key,');
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

/**
 * The timestamp, and the toolbar it sits under.
 *
 * SuperTrend printed the time inline on the parent row at 14px weight 800 — the
 * loudest thing in the row — beside a 10px date, while the shared board has
 * always kept it as an ordinary right-aligned cell in a Time column. Same
 * signal, two presentations, and the louder one was shouting the least
 * actionable number on the row.
 */
describe('both tables stamp a signal the same way', () => {
  it('formats through one shared helper', () => {
    // In boardTypes, beside the sessionDay helpers it already depended on.
    expect(rowSpec).toContain("time: { key: 'time'");
    for (const [name, src] of [['SuperTrend', superTrend], ['SignalBoard', sharedBoard]] as const) {
      expect(src, `${name} uses stamp()`).toContain('stamp(');
    }
    // The hand-rolled parts SuperTrend used to build its own stamp from.
    expect(superTrend).not.toContain("{ weekday: 'short' }");
    expect(superTrend).not.toMatch(/fontSize: 14, fontWeight: 800/);
  });

  it('offers Time as a column, not as a line of header text', () => {
    expect(superTrend).toContain("case 'time':");
  });
});

describe('the toolbar row matches the shared filter bar', () => {
  it('uses the shared bar height, not the watchlist’s', () => {
    // 35 made this row half again as tall as the same row on every other board.
    expect(superTrend).not.toContain('height={35}');
    expect(superTrend).toContain('height={22}');
    expect(superTrend).toContain('compact');
  });

  it('uses the shared filter bar’s inset', () => {
    expect(superTrend).toContain("padding: '5px 10px'");
  });
});

/**
 * Hover, focus and the row background.
 *
 * The largest remaining difference was not in either component. A global
 * stylesheet, `kiteSignalTypography.css`, forced
 *
 *     .st-leg-row > span:first-child { font-weight: 100 !important; }
 *
 * on SuperTrend's instrument cell, so it rendered ultra-thin while the shared
 * board renders the same cell at 700 — and no inline `fontWeight` could win
 * against the `!important`. Setting the weight in the component looked correct
 * and did nothing. Its companion rule matched no element at all: the class in
 * the markup is `st-prices-parent`, not `st-prices`.
 *
 * Read from the stylesheet, because that is where the bug was: a component-only
 * check passes while the rendered table is still wrong.
 */
// Read from disk, not via `?raw`: vitest stubs CSS imports here, so `?raw` on a
// stylesheet returns an empty string and every assertion below would pass
// vacuously. There is no @types/node in this tsconfig, hence the narrow
// suppression -- readFileSync is the only thing needed from it.
// @ts-expect-error - no @types/node; see above.
import { readFileSync } from 'node:fs';

// Relative to the working directory, which vitest sets to the package root.
// `import.meta.url` is no good here: under vite its pathname is root-relative
// ("/src/components/...") rather than a filesystem path, so resolving against it
// produced "/src/styles/globals.css" and an ENOENT.
const globalsCss: string = (() => {
  for (const path of ['src/styles/globals.css', 'frontend/src/styles/globals.css']) {
    try { return readFileSync(path, 'utf8'); } catch { /* try the next root */ }
  }
  throw new Error('globals.css not found from the test working directory');
})();

describe('no stylesheet overrides the row type', () => {
  it('does not force a font weight on SuperTrend rows', () => {
    expect(globalsCss).not.toMatch(/\.st-leg-row[^{]*\{[^}]*font-weight/);
  });

  it('has no stylesheet left that thins the instrument cell', () => {
    // The whole file is gone. If it returns, so does the bug.
    expect(globalsCss).not.toContain('font-weight: 100');
  });
});

describe('both tables share hover, focus and active', () => {
  const rowStates = (() => {
    const start = globalsCss.indexOf('.sb-row,');
    expect(start).toBeGreaterThan(-1);
    return globalsCss.slice(start, globalsCss.indexOf('/* ── Engine toolbar', start));
  })();

  it('states them once, for both tables’ rows', () => {
    for (const sel of ['.sb-row', '.st-leg-row', '.st-parent-header', '.st-group-header']) {
      expect(rowStates, `${sel} hover`).toContain(`${sel}:hover`);
      expect(rowStates, `${sel} focus`).toContain(`${sel}:focus-visible`);
      expect(rowStates, `${sel} active`).toContain(`${sel}:active`);
    }
  });

  it('gives SuperTrend the transition it never had', () => {
    // Its old rule was a bare :hover, so the highlight snapped on where the
    // shared board's eases.
    expect(rowStates).toMatch(/transition: background \.12s ease/);
    expect(rowStates).toContain('prefers-reduced-motion');
  });

  it('no longer declares hover locally in the component', () => {
    expect(superTrend).not.toContain('.st-leg-row:hover');
  });
});

/**
 * Keyboard parity.
 *
 * This is the gap that made the previous commit's claim hollow. I added
 * `:focus-visible` to SuperTrend's rows and said keyboard use was no longer a
 * second-class path — but its rows were click-only divs with no `tabIndex`, no
 * `role` and no key handler, so the rule had nothing to fire on and the rows
 * could not be reached, let alone expanded, without a mouse. Its column
 * headings had the same problem: sorting was mouse-only.
 *
 * A focus style is not accessibility on its own. The element has to be
 * focusable first, which is why this is asserted rather than assumed.
 */
describe('SuperTrend rows and headings work without a mouse', () => {
  /** The leg row's opening tag. */
  const legTag = (() => {
    // Anchored on the class EXPRESSION, not a literal `className="st-leg-row"`:
    // the class is now conditional (the sideways-scroll setting adds a second
    // class), and the old literal anchor silently stopped matching.
    const start = superTrend.indexOf("'st-leg-row st-row-scroll'");
    expect(start, 'the leg row is still rendered here').toBeGreaterThan(-1);
    return superTrend.slice(start - 300, start + 1100);
  })();

  it('puts the leg row in the tab order and announces it', () => {
    expect(legTag).toContain('tabIndex={0}');
    expect(legTag).toContain('role="button"');
    expect(legTag).toContain('aria-expanded');
  });

  it('expands a leg row on Enter or Space', () => {
    expect(legTag).toMatch(/onKeyDown/);
    expect(legTag).toMatch(/'Enter'/);
  });

  it('lets a column be sorted from the keyboard', () => {
    const head = superTrend.slice(
      superTrend.indexOf('export function SortHeaderDiv'),
      superTrend.indexOf('export function SortHeaderDiv') + 1600,
    );
    expect(head).toContain('tabIndex={sortKey ? 0 : undefined}');
    expect(head).toContain("'Enter'");
    // The shared heading class, so the focus ring is defined once.
    expect(head).toContain('sb-head');
  });
});

describe('parent rows alternate shade, as the shared board’s do', () => {
  it('threads a striped flag through SignalCard', () => {
    expect(superTrend).toContain('striped?: boolean');
    expect(superTrend).toContain('rowIndex % 2 === 1');
    expect(superTrend).toContain('striped ? LEG_BG : k.bg');
    // The shared board's own rule, unchanged.
    expect(sharedBoard).toContain('striped ? LEG_BG : k.bg');
  });
});

/**
 * The group band stays put while its rows scroll.
 *
 * The shared board pins its day band at `top: 0` and has always been right to.
 * SuperTrend pinned at `var(--st-sticky-head)` instead — the measured height of
 * the toolbar wrapper — on the theory that a band at 0 would slide underneath
 * it. The wrapper is a SIBLING above the scroll container, never inside it, so
 * the scrollport already begins below the toolbar and the offset was counted
 * twice: measured at 59px, every band sat 59px down into its own rows with its
 * first card showing through above it. Which read, correctly, as the band
 * labelling the group below it.
 *
 * Measuring the wrapper was never the fix, so the variable, the ref and the
 * ResizeObserver that maintained it are all gone.
 */
describe('SuperTrend group bands pin to the top of the scroller', () => {
  it('pins at 0, like the shared board', () => {
    expect(superTrend).toContain("position: 'sticky', top: 0, zIndex: 1,");
    expect(sharedBoard).toContain('top: 0,');
  });

  it('keeps no trace of the double-counted offset', () => {
    expect(superTrend).not.toContain('--st-sticky-head');
    expect(superTrend).not.toContain('stickyHeadRef');
    expect(superTrend).not.toContain('paneRootRef');
  });
});

/**
 * The band's micro-type has to sit on the band.
 *
 * The shared board puts fontSize/weight/letterSpacing/textTransform on the day
 * band element, so everything inside it — label and row count alike — inherits
 * one type scale. SuperTrend had them on the label div only, which left
 * "2 signals" at the inherited 12px beside an 8.5px uppercase date: the count
 * was the largest text in a band meant to be the quietest row in the table.
 */
describe('SuperTrend group band type is set on the band', () => {
  it('carries the day-head metrics on the header element itself', () => {
    const header = superTrend.slice(superTrend.indexOf('className="st-group-header"'));
    const decl = header.slice(0, header.indexOf('>'));
    for (const prop of ['fontSize', 'fontWeight', 'letterSpacing', 'textTransform']) {
      expect(decl).toContain(`${prop}: DAY_HEAD_METRICS.${prop}`);
    }
  });

  it('leaves the count free to be lighter, not larger', () => {
    // Weight is the one thing the count still overrides; size and case come
    // from the band, so they cannot drift apart again.
    expect(superTrend).toContain("fontWeight: 500, color: k.dim");
  });
});

/**
 * Nothing in this table hovers orange.
 *
 * One element did: a grid-view leg tile that turned its BORDER orange on
 * mouse-enter, and re-set its background to transparent while doing it. It was
 * the only hover in the app that moved a different property from every other,
 * and orange on the shared board means an active control — not "the pointer is
 * over this".
 */
describe('hover colour is the shared one everywhere', () => {
  it('has no inline hover handler left in SuperTrend', () => {
    expect(superTrend).not.toContain('onMouseEnter');
    expect(superTrend).not.toContain('style.borderColor = k.orange');
  });

  it('gives the grid tile the same states as a row', () => {
    expect(superTrend).toContain('className="st-leg-tile"');
    for (const state of [':hover', ':focus-visible', ':active']) {
      expect(globalsCss, `tile ${state}`).toContain(`.st-leg-tile${state}`);
    }
  });

  it('never paints a leg label with the active-control accent', () => {
    // An accent on every tile leaves nothing to mark the one that matters.
    const tile = superTrend.slice(superTrend.indexOf('className="st-leg-tile"'));
    expect(tile.slice(0, 1400)).not.toContain('color: k.orange');
  });
});

describe('the direction setting reaches every price cell', () => {
  it('tints Chg. and Chg. % as well as the price', () => {
    // These two were hardcoded `k.dim` and `k.text`, so the setting looked
    // broken: the columns named after the price change were the ones it missed.
    const matches = superTrend.match(/color: s\.showPriceDirection \? color : k\.dim/g) ?? [];
    expect(matches.length, 'both change columns follow the setting').toBeGreaterThanOrEqual(2);
  });
});

/**
 * No backtick inside the component's CSS block.
 *
 * `SterlingKiteEnginePane` writes its stylesheet as `<style>{`...`}</style>`.
 * A backtick anywhere inside — including in a comment, which is where it is
 * tempting to write a class name in code font — closes the template literal
 * early and produces dozens of parse errors far from the cause.
 *
 * I have done this three times in this file. Hence a test rather than a
 * resolution.
 */
describe('the component stylesheet stays a valid template literal', () => {
  it('contains no backtick between <style>{` and `}</style>', () => {
    const open = superTrend.indexOf('<style>{`');
    expect(open, 'the style block is still written this way').toBeGreaterThan(-1);
    const body = superTrend.slice(open + '<style>{`'.length);
    const close = body.indexOf('`}</style>');
    expect(close, 'the block terminates').toBeGreaterThan(-1);
    expect(body.slice(0, close), 'a backtick in here closes the literal early')
      .not.toContain('`');
  });
});

describe('legs are indented under their parent', () => {
  it('uses one shared indent, not a number in each file', () => {
    expect(rowSpec).toContain('LEG_INDENT = 14');
    expect(superTrend).toContain('${16 + LEG_INDENT}px');
    expect(sharedBoard).toContain('LEG_INDENT');
  });

  it('gives back the width the indent took, so columns stay aligned', () => {
    // Without this the instrument column is 14px wider than its heading and
    // every cell to its right drifts.
    //
    // The compensation moved from `minWidth` into the flex BASIS, via
    // `instrumentFlex(isLeg)`. A minimum only bounds shrinking, and the cell no
    // longer shrinks — so once `flex-shrink` went to 0 the old form silently
    // stopped compensating anything. Both tables call the one helper now.
    expect(rowSpec).toContain('export function instrumentFlex');
    expect(rowSpec).toContain('isLeg ? LEG_INDENT : 0');
    expect(superTrend).toContain('instrumentFlex(true)');
    expect(sharedBoard).toContain('instrumentFlex(isLeg)');
  });
});
