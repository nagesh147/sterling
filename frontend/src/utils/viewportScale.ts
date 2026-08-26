/**
 * One layout, the same on every monitor.
 *
 * The problem this solves: a browser hands the page a CSS-pixel viewport whose
 * size depends on the monitor's scale factor, not on the monitor. The same
 * window dragged between two displays measured 2540 CSS px on one and 1234 on
 * the other — so the identical layout got half the room, the signal table
 * clipped, and the app read as a different product on each screen.
 *
 * The fix is to stop laying out against "however many pixels we were given"
 * and lay out against a fixed design width, scaling to fit:
 *
 *     zoom = viewportWidth / designWidth        →  layoutWidth === designWidth
 *
 * CSS `zoom` divides the layout space by the zoom, so this lands the layout on
 * exactly `designWidth` on every display. It also equalises apparent size,
 * which is the part that is easy to miss: a monitor with few CSS pixels has
 * physically large ones, so scaling down there and up on the roomy monitor
 * makes text the same physical size in both places. On the two real displays,
 * at the standard design width: 12px × 0.498 × 2.07 = 12.4 device px on the
 * narrow-viewport monitor, and 12px × 1.024 × 1.00 = 12.3 on the roomy one.
 *
 * Height is a guard rather than a second target. The design heights are set
 * deliberately short so width normally decides; height only takes over on a
 * viewport too shallow to show the design box, where the alternative is
 * content cut off by the terminal's `overflow: hidden`.
 */

/** How much of the app you want on screen at once. */
export type Density = 'comfortable' | 'standard' | 'compact';

export interface DesignBox {
  readonly width: number;
  readonly height: number;
}

/**
 * The box each density lays out against.
 *
 * Bigger width = more content at smaller type, because the same physical
 * screen has to hold more design pixels.
 *
 * `standard` is 2480 because that is what the three-dock terminal needs
 * before the signal table starts clipping. The Signals dock takes about 36%
 * of the width, and the column spec adds up to roughly 870px — instrument 150,
 * exc 40, leg 78, entry 96, sl 56, tsl 56, exit 58, target 44, ltp 70, time,
 * plus the gaps. 870 / 0.36 lands here. A first attempt at 1760 clipped the
 * table at TSL on every monitor, which made the roomy display worse than it
 * had been.
 */
export const DESIGN: Readonly<Record<Density, DesignBox>> = {
  comfortable: { width: 2100, height: 1030 },
  standard: { width: 2480, height: 1215 },
  compact: { width: 2800, height: 1370 },
};

export const DENSITY_ORDER: readonly Density[] = ['comfortable', 'standard', 'compact'];
export const DEFAULT_DENSITY: Density = 'standard';

/**
 * Ceiling on how far the app will scale up. There is no matching floor: a fit
 * too small to be legible drops out of matching altogether rather than being
 * clamped to some least-bad scale.
 */
export const MAX_FIT = 2.0;

/**
 * The terminal's base type size, and the smallest it may be rendered at.
 *
 * This is the floor that makes the feature safe on a device that simply
 * cannot show the design width. Normalising is right between two monitors
 * that differ only in scale factor; it is wrong to apply between a 27" desktop
 * and a small laptop, where honouring 2480 design px would render body text
 * at about 7 device pixels.
 *
 * The floor is expressed in device pixels and divided by devicePixelRatio,
 * because that ratio is exactly what separates the two cases. A monitor whose
 * CSS pixels are large reports a high ratio, so scaling down there costs no
 * real size and the floor stays out of the way; a display already at 1:1 has
 * nowhere to go and the floor binds.
 */
export const BASE_FONT_PX = 12;
export const MIN_TEXT_DEVICE_PX = 10.5;

/** Layout-width buckets, for CSS that needs to adapt rather than scale. */
export type Breakpoint = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
const BREAKPOINTS: ReadonlyArray<readonly [Breakpoint, number]> = [
  ['xs', 700], ['sm', 1024], ['md', 1440], ['lg', 2100],
];
export function breakpointFor(layoutWidth: number): Breakpoint {
  for (const [name, max] of BREAKPOINTS) if (layoutWidth < max) return name;
  return 'xl';
}

/**
 * How the app arrived at its size.
 *
 * `matched` means the layout landed on the design width, so this screen looks
 * like every other screen in `matched`. `responsive` means the floor bound and
 * the layout is narrower than the design width — the app has to adapt rather
 * than shrink. `off` is the user opting out.
 */
export type LayoutMode = 'matched' | 'responsive' | 'off';

/** The user's own multiplier on top of the fit, matching the old zoom range. */
export const MIN_USER_SCALE = 0.6;
export const MAX_USER_SCALE = 2.0;

const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));

export interface FitInput {
  viewportWidth: number;
  viewportHeight: number;
  density?: Density;
  /** The user's manual zoom, applied on top of the fit. */
  userScale?: number;
  /** Off renders 1:1 with the browser — the behaviour before this existed. */
  autoFit?: boolean;
  /** Device pixels per CSS pixel; what tells a scaled monitor from a small one. */
  devicePixelRatio?: number;
}

/**
 * The scale to write into `--app-zoom`.
 *
 * Deliberately not quantised. Rounding would make the layout width land a few
 * pixels apart on different monitors, and landing on exactly the same width
 * everywhere is the entire point.
 */
export function fitScale(input: FitInput): number {
  const {
    viewportWidth: vw,
    viewportHeight: vh,
    density = DEFAULT_DENSITY,
    userScale = 1,
    autoFit = true,
  } = input;

  const user = clamp(Number.isFinite(userScale) ? userScale : 1, MIN_USER_SCALE, MAX_USER_SCALE);
  if (!autoFit) return user;
  // jsdom and a detached document both report 0; scaling by 0 would collapse
  // the app, so fall back to the user's own setting.
  if (!(vw > 0) || !(vh > 0)) return user;

  const box = DESIGN[density] ?? DESIGN[DEFAULT_DENSITY];
  const fit = Math.min(vw / box.width, vh / box.height);

  // Below the floor this display cannot show the design width legibly, so the
  // app stops matching and renders 1:1 instead of shrinking further. Falling
  // back to native is better than falling back to a smaller scale on two
  // counts: the type is at its most readable, and layout width then equals
  // the viewport, which is the only condition under which the app's existing
  // width media queries are telling the truth. CSS `zoom` does not affect
  // media-query evaluation, so a scaled app and its `@media (max-width: …)`
  // rules are otherwise reasoning about two different numbers.
  if (fit < legibilityFloor(input.devicePixelRatio)) return user;

  return Math.min(fit, MAX_FIT) * user;
}

/**
 * The smallest scale that still leaves body text readable on this display.
 *
 * Above this the app normalises; at it the app stops shrinking and the layout
 * has to give instead, which is what makes the same code work on a phone and
 * on a 27" panel.
 */
export function legibilityFloor(devicePixelRatio = 1): number {
  const dpr = devicePixelRatio > 0 ? devicePixelRatio : 1;
  return MIN_TEXT_DEVICE_PX / BASE_FONT_PX / dpr;
}

export interface ScaleResult {
  scale: number;
  mode: LayoutMode;
  layoutWidth: number;
  layoutHeight: number;
  breakpoint: Breakpoint;
}

/** Everything the document and the UI need to know, in one call. */
export function resolveScale(input: FitInput): ScaleResult {
  const scale = fitScale(input);
  const { width, height } = layoutSizeFor(scale, input.viewportWidth, input.viewportHeight);
  const box = DESIGN[input.density ?? DEFAULT_DENSITY] ?? DESIGN[DEFAULT_DENSITY];
  // Both axes, because a wide-but-shallow display can clear the design width
  // and still be short of its height — it is adapting, not matching. The
  // tolerance is for float error: the fit is a raw ratio, and exact equality
  // would report `responsive` for a rounding artefact.
  const matched = width >= box.width - 1 && height >= box.height - 1;
  return {
    scale,
    mode: input.autoFit === false ? 'off' : matched ? 'matched' : 'responsive',
    layoutWidth: width,
    layoutHeight: height,
    breakpoint: breakpointFor(width),
  };
}

/** The layout size that scale produces — what the app's own CSS sees. */
export function layoutSizeFor(scale: number, viewportWidth: number, viewportHeight: number): DesignBox {
  const s = scale > 0 ? scale : 1;
  return { width: viewportWidth / s, height: viewportHeight / s };
}
