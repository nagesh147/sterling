/**
 * Writes the fitted scale onto the document, and tells the rest of the app
 * what coordinate space it is now working in.
 *
 * The scale goes on `<html>`, not on `.term-root` where it used to live. Every
 * one of the app's eight portal sites mounts into `document.body` — modals,
 * tooltips, the order window — so a zoom on the terminal root left all of them
 * rendering at 1:1 over a scaled app. `<html>` is the only element that is an
 * ancestor of both the terminal and the portals.
 *
 * Scaling `<html>` above 1 makes the document taller than the viewport and
 * raises a scrollbar, which then steals width from the layout. The terminal is
 * `position: fixed; inset: 0` and never wanted a document scroll anyway, so
 * the applier pins the document while a scale is active. Measured at 1.5×:
 * pinned, the root fills 1234×1210 exactly with 823×807 of layout space; left
 * unpinned it lost 10px to a scrollbar.
 */
import { resolveScale, layoutSizeFor, type Density, type DesignBox, type ScaleResult } from '../utils/viewportScale';

/** The scale currently on the document. */
let applied = 1;

/** What `--app-zoom` is set to right now. */
export function currentScale(): number {
  return applied;
}

/**
 * Viewport size in the coordinate space the app's own CSS and layout use.
 *
 * Anything positioning against the window edge — a popover clamping itself on
 * screen, a draggable window — must measure with this rather than
 * `window.innerWidth`, which is in device-facing pixels and is a different
 * number the moment a scale is applied.
 */
export function layoutViewport(): DesignBox {
  if (typeof window === 'undefined') return { width: 0, height: 0 };
  return layoutSizeFor(applied, window.innerWidth, window.innerHeight);
}

export interface ScaleSettings {
  density: Density;
  userScale: number;
  autoFit: boolean;
}

/** The last full result, for anything that wants more than the number. */
let lastResult: ScaleResult | null = null;
export function currentLayout(): ScaleResult | null {
  return lastResult;
}

/** Recompute from the live viewport and write it to the document. */
export function applyViewportScale(settings: ScaleSettings): number {
  if (typeof document === 'undefined') return 1;
  const result = resolveScale({
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
    ...settings,
  });
  const { scale } = result;

  const root = document.documentElement;
  root.style.setProperty('--app-zoom', String(scale));
  // Published because media queries cannot see this. CSS `zoom` does not
  // affect media-query evaluation, so `(max-width: 820px)` still tests the
  // device viewport while the app may have 2480px of layout — the two can
  // disagree completely. Anything that needs to adapt to the room the app
  // actually has must key off these rather than a width media query.
  root.style.setProperty('--app-layout-width', `${Math.round(result.layoutWidth)}px`);
  root.style.setProperty('--app-layout-height', `${Math.round(result.layoutHeight)}px`);
  root.setAttribute('data-layout', result.breakpoint);
  root.setAttribute('data-layout-mode', result.mode);

  // The stylesheet keys both the zoom and the document pin off this attribute,
  // so an app at exactly 1:1 is byte-for-byte what it was before any of this
  // existed — no zoom property, no pinned document, nothing to regress.
  if (scale === 1) root.removeAttribute('data-app-scaled');
  else root.setAttribute('data-app-scaled', '');

  applied = scale;
  lastResult = result;
  return scale;
}

/**
 * Keep the scale correct as the window changes.
 *
 * `resize` covers window resizing and most monitor moves. Dragging a window to
 * a display with a different scale factor can change devicePixelRatio without
 * a resize, so the ratio is watched too — and the watcher has to be rebuilt
 * each time, because a `(resolution: Ndppx)` query only ever fires once, on
 * the way out of N.
 */
export function watchViewportScale(read: () => ScaleSettings): () => void {
  if (typeof window === 'undefined') return () => {};

  let frame = 0;
  let dprQuery: MediaQueryList | null = null;

  const apply = () => {
    frame = 0;
    applyViewportScale(read());
  };
  const schedule = () => {
    if (!frame) frame = requestAnimationFrame(apply);
  };

  const onDpr = () => {
    schedule();
    watchDpr();
  };
  function watchDpr() {
    // Absent in jsdom, and `(resolution: …)` is not universally supported;
    // resize alone still catches the common cases, so this stays best-effort.
    if (typeof window.matchMedia !== 'function') return;
    dprQuery?.removeEventListener('change', onDpr);
    try {
      dprQuery = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
      dprQuery.addEventListener('change', onDpr);
    } catch {
      dprQuery = null;
    }
  }

  apply();
  window.addEventListener('resize', schedule);
  watchDpr();

  return () => {
    if (frame) cancelAnimationFrame(frame);
    window.removeEventListener('resize', schedule);
    dprQuery?.removeEventListener('change', onDpr);
  };
}

/**
 * Convert a measured coordinate into the space CSS lengths are written in.
 *
 * These two spaces are the same number until a scale is applied, which is why
 * the app got away with mixing them for so long. Under a scale they diverge:
 * `getBoundingClientRect()` and pointer events report device-facing pixels,
 * while a CSS `left` on a positioned element resolves in layout pixels. Mixing
 * them put a popover 446px from its anchor at a 0.70 scale.
 *
 * Rule of thumb: anything you measured, pass through here before writing it
 * back out as a style.
 */
export function toLayoutPx(devicePx: number): number {
  return applied > 0 ? devicePx / applied : devicePx;
}

/** An element's box in layout space, ready to position against. */
export function layoutRect(el: Element): DesignBox & { left: number; top: number; right: number; bottom: number } {
  const r = el.getBoundingClientRect();
  const s = applied > 0 ? applied : 1;
  return {
    left: r.left / s, top: r.top / s,
    right: r.right / s, bottom: r.bottom / s,
    width: r.width / s, height: r.height / s,
  };
}
