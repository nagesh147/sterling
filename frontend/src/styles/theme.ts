/**
 * The app's colour tokens, in both themes.
 *
 * ## Why one token per distinct light value
 *
 * The terminal was written against literal hex, ~1,600 of them, and a lot of
 * near-identical shades carry real meaning: `#4caf50` is a fill, `#2e7d32` is
 * the text you put on top of it, `#059669` is the emerald a different pane
 * chose. Collapsing them into one "green" would be a redesign of light mode
 * smuggled in under a dark-mode change.
 *
 * So every token's `light` value is byte-identical to the hex it replaces.
 * Light mode is provably unchanged — that is the whole point of the shape of
 * this file — and `dark` is the only new information.
 *
 * ## Reading a token
 *
 * Components should use `k` from `./kiteUI`, which resolves to `var(--k-*)`.
 * Canvas and chart libraries cannot resolve a CSS variable, so they call
 * `readThemeHex()` and re-read it when the theme changes.
 */

export type ThemeName = 'light' | 'dark';

/** `[name, light, dark]`, grouped by role. */
type Token = readonly [name: string, light: string, dark: string];

/**
 * Dark surfaces step up in lightness the way paper steps up in shadow, and the
 * base is a blue-black rather than #000 — pure black against bright numerals
 * haloes badly on the OLED panels these terminals tend to run on.
 */
const SURFACES: readonly Token[] = [
  ['bg', '#ffffff', '#0f1115'],
  ['surface', '#f9f9f9', '#171a21'],
  ['surface-2', '#fafafa', '#161920'],
  ['surface-hover', '#f1f1f1', '#1e222b'],
  ['surface-hover-2', '#f0f0f0', '#1d212a'],
  ['surface-sunken', '#f8fafc', '#12151b'],
  ['surface-sunken-2', '#f7f7f8', '#13161c'],
  ['surface-slate', '#f1f5f9', '#1b1f28'],
  ['surface-warm', '#fff5f0', '#241a14'],
  ['border', '#e0e0e0', '#262b36'],
  ['border-slate', '#e2e8f0', '#282e3a'],
  ['border-2', '#e8e8e8', '#242933'],
  ['border-3', '#ececec', '#232831'],
  ['border-strong', '#dfe1e4', '#333a48'],
  ['border-strong-2', '#dcdcdc', '#323947'],
  ['border-strong-4', '#dedede', '#323947'],
  ['border-strong-3', '#ddd', '#313846'],
  ['border-slate-strong', '#cbd5e1', '#3a4150'],
  ['border-brand', '#e2b6a4', '#8a5c48'],
  ['tint-green', '#e8f5e9', '#15291b'],
  ['tint-amber', '#fff3e0', '#2b2113'],
  ['tint-red', '#ffebee', '#2c1719'],
  ['tint-blue', '#e3f2fd', '#12222e'],
  ['tint-warm', '#ffd7c7', '#3a241a'],
  ['tint-warm-2', '#ffe8dc', '#33221a'],
  ['surface-6', '#f4f4f5', '#191d24'],
  ['surface-3', '#fbfbfc', '#14171d'],
  ['surface-4', '#f5f5f5', '#1a1e26'],
  ['surface-5', '#fbfbfb', '#14171d'],
  ['hairline', '#f3f3f3', '#20242d'],
  ['hairline-2', '#f2f2f2', '#20242d'],
  ['hairline-3', '#eee', '#222730'],
];

/**
 * The grey ramp inverts: what was the darkest ink becomes the brightest.
 * Kept as separate steps because the source used all of #333/#444/#555/#666/
 * #777/#888/#999/#aaa/#bbb to mean six different levels of importance.
 */
const INK: readonly Token[] = [
  ['ink-1', '#333', '#f4f6fa'],
  ['ink-slate-1', '#1e293b', '#eef1f6'],
  ['text', '#444444', '#e6e8ee'],
  ['ink-slate-2', '#334155', '#d6dbe5'],
  ['ink-3', '#555', '#c9cfdb'],
  ['ink-4', '#666', '#bcc3d0'],
  ['ink-5', '#777', '#aeb6c3'],
  ['ink-6', '#888', '#a8b0be'],
  ['ink-slate-3', '#64748b', '#98a1b2'],
  ['dim', '#9b9b9b', '#8b93a3'],
  ['dim-2', '#999', '#8b93a3'],
  ['ink-slate-4', '#94a3b8', '#7f8899'],
  ['faint', '#aaa', '#848c99'],
  ['faint-2', '#bbb', '#818997'],
  ['faint-3', '#bdbdbd', '#7f8794'],
  ['ink-7', '#8d8d8d', '#9aa2b0'],
  ['faint-4', '#c6c6c6', '#7d8593'],
  ['faint-5', '#ccc', '#7d8593'],
];

/**
 * Hues hold; lightness and a little saturation move, because a colour that
 * reads as "warning" on white reads as "mud" on near-black. Every one of these
 * clears WCAG AA (4.5:1) as small text on both dark surfaces.
 */
const ACCENTS: readonly Token[] = [
  ['blue', '#4184f3', '#5f9bff'],
  ['blue-kite', '#387ed1', '#5b9ee8'],
  ['blue-strong', '#2563eb', '#5b8def'],
  ['blue-vivid', '#2962ff', '#5b85ff'],
  ['red', '#df514c', '#ef5350'],
  ['red-strong', '#e53935', '#f0605c'],
  ['red-deep', '#dc2626', '#f2554f'],
  ['red-chart', '#f23645', '#ff5a68'],
  ['red-muted', '#cc4444', '#e0706c'],
  ['red-brick', '#c9433e', '#e56a66'],
  ['green', '#4caf50', '#4ec96a'],
  ['green-deep', '#2e7d32', '#4fb356'],
  ['green-mint', '#44cc88', '#52d99a'],
  ['emerald', '#059669', '#34d399'],
  ['emerald-2', '#10b981', '#3ddba6'],
  ['amber', '#f5a623', '#ffb547'],
  ['amber-2', '#ff9800', '#ffab2e'],
  ['amber-3', '#f59e0b', '#ffb03a'],
  ['warn', '#d97706', '#f0951f'],
  ['warn-deep', '#e65100', '#ff8a3d'],
  ['orange', '#ff5722', '#ff7a45'],
  ['brand', '#f06428', '#ff7a45'],
  ['brand-deep', '#d35400', '#ff8544'],
  ['purple', '#9c27b0', '#c07ad4'],
  ['violet', '#7c3aed', '#a78bfa'],
  ['violet-2', '#a371f7', '#b48bff'],
  ['cyan', '#00bcd4', '#22d3ee'],
  // Foreground for anything filled with an accent. It has to flip: the same
  // accents are lightened for dark, and white text on a lightened blue drops
  // to 2.8:1. This is the one token whose dark value is DARKER than its light.
  ['on-accent', '#ffffff', '#0f1115'],
  ['red-soft', '#ef6c63', '#f07b74'],
  ['red-500', '#ef4444', '#f2615c'],
  ['red-crimson', '#c62828', '#e0524e'],
  ['red-rose', '#e05260', '#ef6f7b'],
  ['blue-bar', '#3c80ec', '#5f9bff'],
  ['blue-deep', '#1565c0', '#4d94e0'],
  ['orange-bar', '#ff7043', '#ff8a5c'],
  ['green-500', '#22c55e', '#3ed675'],
  ['green-600', '#16a34a', '#2fbe63'],
  ['violet-3', '#aa88ff', '#bb9dff'],
  ['purple-2', '#ab47bc', '#c477d4'],
  ['gold', '#f0c040', '#f5cf63'],
];

export const THEME_TOKENS: readonly Token[] = [...SURFACES, ...INK, ...ACCENTS];

/** `--k-bg`, `--k-ink-1`, … — the name components write against. */
export const cssVar = (name: string) => `var(--k-${name})`;

const block = (selector: string, index: 1 | 2) =>
  `${selector}{\n${THEME_TOKENS.map((t) => `  --k-${t[0]}: ${t[index]};`).join('\n')}\n}`;

/**
 * Light lives on bare `:root`, so a page that never sets `data-theme` still
 * renders — and the dark tokens attach to the two dark shells the app already
 * had (`dark` and `grey`), rather than inventing a third theme name that the
 * outer terminal would not recognise.
 *
 * The Kite panes used to be hardcoded light while the shell around them was
 * dark. That is why the app looked half-themed: these tokens are what let the
 * inside of the terminal follow the switch the outside always had.
 */
export function themeCss(): string {
  return `${block(':root', 1)}\n${block(':root[data-theme="dark"], :root[data-theme="grey"]', 2)}`;
}

/**
 * The literal colour a token currently resolves to.
 *
 * For canvas and chart libraries only: they paint into a bitmap and never see
 * the cascade, so they need the value, and they need to be told to re-read it
 * when the theme changes.
 */
export function readThemeHex(name: string, fallback = '#000000'): string {
  if (typeof document === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(`--k-${name}`).trim();
  return value || fallback;
}
