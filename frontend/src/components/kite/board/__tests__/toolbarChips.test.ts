/**
 * One chip family across the engine toolbar.
 *
 * The row carried two shapes at once: `SOURCE`, `EXIT` and `VIEW` were
 * borderless `border-radius: 999` pills with their names floating outside as
 * separate coloured text, while `COLUMNS`, `BEST LEG` and `ENDED` were 22px
 * bordered chips at radius 4 carrying their own names inside
 * ("COLUMNS 12/13"). Three controls labelled one way and three the other, on one
 * line — and the `1H` badge was a third shape again at radius 3.
 *
 * Asserted on the sources rather than on a render: the failure is a number
 * drifting in a style object, which is exactly what a source check catches and
 * what a screenshot-free render test cannot see.
 */
import { describe, it, expect } from 'vitest';

// @ts-expect-error - no @types/node in this tsconfig; readFileSync is all this needs.
import { readFileSync } from 'node:fs';

const read = (rel: string): string => {
  for (const root of ['src/', 'frontend/src/']) {
    try { return readFileSync(root + rel, 'utf8') as string; } catch { /* next root */ }
  }
  throw new Error(`${rel} not found from the test working directory`);
};

const pane = read('components/kite/SterlingKiteEnginePane.tsx');
const filters = read('components/kite/board/BoardFilters.tsx');
const toolbar = read('components/kite/board/EngineToolbar.tsx');

/**
 * The engine toolbar's own controls, where the pills used to live.
 *
 * `scanTitle` is declared ABOVE `engineControls`, so slicing between them in
 * source order yields nothing — my first version of this did exactly that and
 * passed an empty string to every assertion below.
 */
const controls = (() => {
  const start = pane.indexOf('const engineControls = (');
  expect(start).toBeGreaterThan(-1);
  const end = pane.indexOf('\n  );', start);
  expect(end).toBeGreaterThan(start);
  return pane.slice(start, end);
})();

/** The dropdown chip itself, which lives outside `engineControls`. */
const trigger = (() => {
  const at = pane.indexOf('aria-haspopup="listbox"');
  expect(at).toBeGreaterThan(-1);
  return pane.slice(at, at + 900);
})();

describe('the toolbar is one chip family', () => {
  it('has no pill left among the chips', () => {
    // Scoped to the toolbar. The file still has two legitimate `999`s — a
    // 34x19 toggle SWITCH, which is meant to be a pill, and the universe
    // multi-select chips in the settings drawer. Asserting on the whole file
    // called both of those bugs.
    expect(controls).not.toContain('borderRadius: 999');
    expect(trigger).not.toContain('borderRadius: 999');
  });

  it('uses radius 4 for every chip on the row', () => {
    const radii = new Set([
      ...controls.matchAll(/borderRadius: (\d+)/g),
      ...trigger.matchAll(/borderRadius: (\d+)/g),
    ].map((m) => m[1]));
    expect(radii, 'one radius, not three').toEqual(new Set(['4']));
  });

  it('gives the dropdown the same height and padding as COLUMNS', () => {
    // Read off the component the row is matching, so this cannot pass by
    // coincidence if that component is restyled.
    expect(filters).toContain("height: 22, padding: '0 7px'");
    expect(trigger).toContain("height: 22, padding: '0 7px'");
  });
});

describe('a control carries its own name', () => {
  it('renders the label INSIDE the chip', () => {
    expect(pane).toContain('label?: string;');
    for (const label of ['SOURCE', 'EXIT', 'VIEW']) {
      expect(controls, `${label} is passed to the chip`).toContain(`label="${label}"`);
    }
  });

  it('no longer prints it outside as coloured text', () => {
    // ToolbarControl used to render the label itself; it is a tooltip wrapper now.
    const body = toolbar.slice(toolbar.indexOf('export function ToolbarControl'));
    const render = body.slice(body.indexOf('return ('), body.indexOf('export function ScopeDivider'));
    // `{label}` on its own line was the rendered text. The tooltip string
    // `${label} — ${hint}` contains it as a substring, so the check has to be
    // for the JSX expression as a child, not for the characters anywhere.
    expect(render).not.toMatch(/^\s*\{label\}\s*$/m);
    // The explanation must survive: a control that does not say what it changes
    // is worse than one with a redundant prop.
    expect(render).toContain('${label} — ${hint}');
  });
});
