/**
 * The document side of viewport normalisation.
 *
 * Two things are worth pinning down here. The scale has to be gated so an app
 * at exactly 1:1 is untouched — otherwise every user who never opens the
 * setting inherits a pinned document and a zoom property for no reason. And
 * the coordinate helpers have to convert, because measuring in one space and
 * writing back in the other is what put a tooltip 446px from its anchor.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  applyViewportScale, currentScale, layoutViewport, toLayoutPx, layoutRect,
  watchViewportScale,
} from '../applyViewportScale';
import { DESIGN } from '../../utils/viewportScale';

/**
 * jsdom reports devicePixelRatio 1, which would put the legibility floor in
 * the way of every assertion here. The displays being modelled are the two
 * real monitors, so their ratios are supplied along with their sizes.
 */
const setViewport = (w: number, h: number, dpr = 2.07) => {
  Object.defineProperty(window, 'innerWidth', { value: w, configurable: true, writable: true });
  Object.defineProperty(window, 'innerHeight', { value: h, configurable: true, writable: true });
  Object.defineProperty(window, 'devicePixelRatio', { value: dpr, configurable: true, writable: true });
};

const STANDARD = { density: 'standard' as const, userScale: 1, autoFit: true };

beforeEach(() => {
  setViewport(1234, 1210);
  document.documentElement.removeAttribute('data-app-scaled');
  document.documentElement.style.removeProperty('--app-zoom');
});

describe('what lands on the document', () => {
  it('writes the fitted scale into --app-zoom', () => {
    const scale = applyViewportScale(STANDARD);
    expect(document.documentElement.style.getPropertyValue('--app-zoom')).toBe(String(scale));
    expect(currentScale()).toBe(scale);
  });

  it('marks the document so the stylesheet applies the zoom and the pin', () => {
    applyViewportScale(STANDARD);
    expect(document.documentElement.hasAttribute('data-app-scaled')).toBe(true);
  });

  it('leaves an unscaled app completely alone', () => {
    // The stylesheet keys both rules off this attribute, so its absence means
    // no zoom property and no pinned document — byte-for-byte the behaviour
    // before any of this existed.
    applyViewportScale({ ...STANDARD, autoFit: false });
    expect(currentScale()).toBe(1);
    expect(document.documentElement.hasAttribute('data-app-scaled')).toBe(false);
  });

  it('clears the mark when a scaled app returns to 1:1', () => {
    applyViewportScale(STANDARD);
    expect(document.documentElement.hasAttribute('data-app-scaled')).toBe(true);
    applyViewportScale({ ...STANDARD, autoFit: false });
    expect(document.documentElement.hasAttribute('data-app-scaled')).toBe(false);
  });
});

describe('coordinate spaces', () => {
  // getBoundingClientRect() and pointer events report device-facing pixels; a
  // CSS left/top on a positioned element resolves in layout pixels. They are
  // the same number until a scale is applied, which is how the app got away
  // with mixing them.
  it('reports the layout viewport, not the device one', () => {
    applyViewportScale(STANDARD);
    expect(layoutViewport().width).toBeCloseTo(DESIGN.standard.width, 6);
    expect(layoutViewport().width).not.toBeCloseTo(window.innerWidth, 0);
  });

  it('converts a measured coordinate into the space CSS writes in', () => {
    const scale = applyViewportScale(STANDARD);
    expect(toLayoutPx(1192)).toBeCloseTo(1192 / scale, 6);
  });

  it('round-trips: a converted point lands back where it was measured', () => {
    const scale = applyViewportScale(STANDARD);
    expect(toLayoutPx(851.8) * scale).toBeCloseTo(851.8, 6);
  });

  it('is the identity when nothing is scaled', () => {
    applyViewportScale({ ...STANDARD, autoFit: false });
    expect(toLayoutPx(640)).toBe(640);
    expect(layoutViewport().width).toBe(window.innerWidth);
  });

  it('converts an element box as a whole', () => {
    const scale = applyViewportScale(STANDARD);
    const el = document.createElement('div');
    el.getBoundingClientRect = () => ({
      left: 100, top: 50, right: 300, bottom: 90, width: 200, height: 40,
      x: 100, y: 50, toJSON: () => ({}),
    }) as DOMRect;
    const r = layoutRect(el);
    expect(r.left).toBeCloseTo(100 / scale, 6);
    expect(r.width).toBeCloseTo(200 / scale, 6);
    expect(r.right - r.left).toBeCloseTo(r.width, 6);
  });
});

describe('keeping up with the window', () => {
  let raf: { mockRestore: () => void };
  beforeEach(() => {
    // Run the frame synchronously so a resize is observable in the same tick.
    raf = vi.spyOn(window, 'requestAnimationFrame')
      .mockImplementation(((cb: FrameRequestCallback) => { cb(0); return 1; }) as never);
  });
  afterEach(() => raf.mockRestore());

  it('applies once on install', () => {
    const stop = watchViewportScale(() => STANDARD);
    expect(layoutViewport().width).toBeCloseTo(DESIGN.standard.width, 6);
    stop();
  });

  it('re-fits when the window changes size', () => {
    const stop = watchViewportScale(() => STANDARD);
    setViewport(2540, 1330, 1);
    window.dispatchEvent(new Event('resize'));
    // Still the design width — that is the entire point.
    expect(layoutViewport().width).toBeCloseTo(DESIGN.standard.width, 6);
    stop();
  });

  it('stops listening once torn down', () => {
    const stop = watchViewportScale(() => STANDARD);
    const before = currentScale();
    stop();
    setViewport(2540, 1330, 1);
    window.dispatchEvent(new Event('resize'));
    expect(currentScale()).toBe(before);
  });
});
