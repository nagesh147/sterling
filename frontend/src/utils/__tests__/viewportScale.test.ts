/**
 * The property this feature exists for: two different monitors, one layout.
 *
 * The bug was that a browser hands the page a CSS-pixel viewport sized by the
 * display's scale factor. The same window measured 2540 CSS px on one monitor
 * and 1234 on another, so the identical app got half the room on the second —
 * signal columns clipped there and everything read half-size on the first.
 */
import { describe, it, expect } from 'vitest';
import {
  fitScale, layoutSizeFor, resolveScale, legibilityFloor, breakpointFor,
  DESIGN, DENSITY_ORDER, DEFAULT_DENSITY,
  MAX_FIT, MIN_USER_SCALE, MAX_USER_SCALE, BASE_FONT_PX,
  type Density,
} from '../viewportScale';

/**
 * The two displays that produced the bug report. Same physical panel size;
 * they differ only in scale factor, which is exactly what devicePixelRatio
 * reports and what makes normalising between them the right thing to do.
 */
const WIDE = { viewportWidth: 2540, viewportHeight: 1330, devicePixelRatio: 1 };
const NARROW = { viewportWidth: 1234, viewportHeight: 1210, devicePixelRatio: 2.07 };

const layoutOf = (vp: { viewportWidth: number; viewportHeight: number; devicePixelRatio?: number }, over = {}) => {
  const scale = fitScale({ ...vp, ...over });
  return layoutSizeFor(scale, vp.viewportWidth, vp.viewportHeight);
};

describe('the same layout on every monitor', () => {
  it('gives two very different viewports the same layout width', () => {
    expect(layoutOf(WIDE).width).toBeCloseTo(layoutOf(NARROW).width, 6);
  });

  it('lands that width on the density’s design width', () => {
    expect(layoutOf(NARROW).width).toBeCloseTo(DESIGN[DEFAULT_DENSITY].width, 6);
  });

  it('scales in opposite directions to get there', () => {
    // The narrow viewport has physically large CSS pixels and must shrink;
    // the roomy one must grow. Opposite signs is the whole mechanism.
    expect(fitScale(NARROW)).toBeLessThan(1);
    expect(fitScale(WIDE)).toBeGreaterThan(1);
  });

  it('holds for every density, not just the default', () => {
    for (const density of DENSITY_ORDER) {
      expect(layoutOf(WIDE, { density }).width, density)
        .toBeCloseTo(layoutOf(NARROW, { density }).width, 6);
    }
  });

  it('equalises apparent size, which is why it is legible on both', () => {
    // A monitor reporting few CSS pixels has physically large ones, so the
    // same design pixel ends up the same physical size on both.
    const physical = (vp: typeof WIDE) => BASE_FONT_PX * fitScale(vp) * vp.devicePixelRatio;
    expect(physical(NARROW)).toBeCloseTo(physical(WIDE), 0);
  });
});

describe('density chooses how much fits, not whether it fits', () => {
  it('orders the design widths so compact really is denser', () => {
    const widths = DENSITY_ORDER.map((d) => DESIGN[d].width);
    expect(widths).toEqual([...widths].sort((a, b) => a - b));
  });

  it('renders smaller for a denser setting on the same monitor', () => {
    // More design pixels squeezed onto the same glass means each is smaller.
    expect(fitScale({ ...NARROW, density: 'compact' }))
      .toBeLessThan(fitScale({ ...NARROW, density: 'comfortable' }));
  });
});

describe('height is a guard, not a second target', () => {
  it('lets width decide on ordinary displays', () => {
    for (const vp of [WIDE, NARROW, { viewportWidth: 1920, viewportHeight: 950, devicePixelRatio: 2 }]) {
      const box = DESIGN[DEFAULT_DENSITY];
      expect(fitScale(vp), JSON.stringify(vp)).toBeCloseTo(vp.viewportWidth / box.width, 6);
    }
  });

  it('takes over on a viewport too shallow to show the design box', () => {
    // Otherwise the layout is taller than the glass and the terminal's
    // overflow:hidden simply cuts the bottom off. dpr 2 keeps the legibility
    // floor out of the way so this tests the height guard on its own.
    const shallow = { viewportWidth: 3440, viewportHeight: 700, devicePixelRatio: 2 };
    const { height } = layoutSizeFor(fitScale(shallow), shallow.viewportWidth, shallow.viewportHeight);
    expect(height).toBeCloseTo(DESIGN[DEFAULT_DENSITY].height, 6);
  });

  it('yields to the legibility floor, because unreadable text has no recovery', () => {
    // A wide-but-shallow display at 1:1 wants a scale the floor forbids, so
    // matching is abandoned rather than the type being shrunk to suit.
    const shallow = { viewportWidth: 3440, viewportHeight: 700, devicePixelRatio: 1 };
    expect(fitScale(shallow)).toBe(1);
    expect(resolveScale(shallow).mode).toBe('responsive');
  });

  it('never lets the layout exceed the design box in either axis', () => {
    const box = DESIGN[DEFAULT_DENSITY];
    for (const vp of [WIDE, NARROW, { viewportWidth: 3440, viewportHeight: 700, devicePixelRatio: 2 }]) {
      const l = layoutOf(vp);
      expect(Math.min(l.width - box.width, l.height - box.height), JSON.stringify(vp))
        .toBeLessThanOrEqual(1e-6);
    }
  });
});

describe('the manual multiplier', () => {
  it('multiplies the fit rather than replacing it', () => {
    expect(fitScale({ ...NARROW, userScale: 1.5 })).toBeCloseTo(fitScale(NARROW) * 1.5, 6);
  });

  it('is clamped to the range the old zoom control used', () => {
    expect(fitScale({ ...NARROW, userScale: 99 })).toBeCloseTo(fitScale(NARROW) * MAX_USER_SCALE, 6);
    expect(fitScale({ ...NARROW, userScale: 0.01 })).toBeCloseTo(fitScale(NARROW) * MIN_USER_SCALE, 6);
  });

  it('is the only thing left when matching is switched off', () => {
    // Off must be exactly the pre-existing behaviour, so turning it off can
    // never be a regression against how the app shipped before.
    expect(fitScale({ ...WIDE, autoFit: false })).toBe(1);
    expect(fitScale({ ...NARROW, autoFit: false, userScale: 1.25 })).toBe(1.25);
  });
});

describe('guards', () => {
  it('falls back to the user setting when the viewport is unmeasurable', () => {
    // jsdom and a detached document both report 0; scaling by 0 would
    // collapse the app to nothing.
    expect(fitScale({ viewportWidth: 0, viewportHeight: 0 })).toBe(1);
    expect(fitScale({ viewportWidth: 0, viewportHeight: 0, userScale: 1.2 })).toBe(1.2);
  });

  it('renders a pathological window natively rather than unreadably', () => {
    expect(fitScale({ viewportWidth: 120, viewportHeight: 90, devicePixelRatio: 8 })).toBe(1);
  });

  it('caps how far it will scale up', () => {
    expect(fitScale({ viewportWidth: 20000, viewportHeight: 20000 })).toBe(MAX_FIT);
  });

  it('treats an unknown density as the default rather than throwing', () => {
    expect(fitScale({ ...NARROW, density: 'enormous' as Density })).toBeCloseTo(fitScale(NARROW), 6);
  });

  it('survives a NaN user scale', () => {
    expect(fitScale({ ...NARROW, userScale: NaN })).toBeCloseTo(fitScale(NARROW), 6);
  });
});


describe('a device that cannot show the design width', () => {
  // Normalising is right between two monitors differing only in scale factor.
  // It is wrong between a 27" desktop and a small laptop: honouring 2480
  // design px there renders body text at about 7 device pixels.
  const LAPTOP = { viewportWidth: 1440, viewportHeight: 900, devicePixelRatio: 1 };

  it('renders natively instead of shrinking to something microscopic', () => {
    // Honouring 2480 design px here would need a 0.58 scale — about 7px type.
    const wouldHaveBeen = LAPTOP.viewportWidth / DESIGN[DEFAULT_DENSITY].width;
    expect(wouldHaveBeen * BASE_FONT_PX).toBeLessThan(8);   // ~7px type
    expect(fitScale(LAPTOP)).toBe(1);
  });

  it('makes layout width equal viewport width, so media queries stay honest', () => {
    // The reason the fallback is 1:1 rather than a smaller scale. CSS zoom
    // does not affect media-query evaluation, so only at 1:1 do the app's
    // `@media (max-width: …)` rules and its actual layout agree.
    const r = resolveScale(LAPTOP);
    expect(r.layoutWidth).toBe(LAPTOP.viewportWidth);
    expect(r.layoutHeight).toBe(LAPTOP.viewportHeight);
  });

  it('says so, rather than pretending it matched', () => {
    expect(resolveScale(LAPTOP).mode).toBe('responsive');
    expect(resolveScale(WIDE).mode).toBe('matched');
    expect(resolveScale({ ...WIDE, autoFit: false }).mode).toBe('off');
  });

  it('hands the layout less than the design width, so the UI must adapt', () => {
    expect(resolveScale(LAPTOP).layoutWidth).toBeLessThan(DESIGN[DEFAULT_DENSITY].width);
  });

  it('keeps out of the way on a display that has the pixels to spare', () => {
    // A high-ratio display can be scaled down a long way before anything
    // physically shrinks, so the floor must not bind on the real monitors.
    for (const vp of [WIDE, NARROW]) {
      expect(fitScale(vp), JSON.stringify(vp)).toBeGreaterThan(legibilityFloor(vp.devicePixelRatio));
      expect(resolveScale(vp).mode).toBe('matched');
    }
  });

  it('scales the floor with the display ratio', () => {
    expect(legibilityFloor(2)).toBeCloseTo(legibilityFloor(1) / 2, 6);
    expect(legibilityFloor(0)).toBe(legibilityFloor(1));
  });
});

describe('breakpoints describe the layout, not the device', () => {
  // Media queries cannot see this: CSS zoom does not affect their evaluation,
  // so they still test the device viewport while the app may have far more
  // layout room than that.
  it('buckets by layout width', () => {
    expect(breakpointFor(600)).toBe('xs');
    expect(breakpointFor(900)).toBe('sm');
    expect(breakpointFor(1300)).toBe('md');
    expect(breakpointFor(1800)).toBe('lg');
    expect(breakpointFor(2480)).toBe('xl');
  });

  it('reports the roomy bucket on a narrow device that is being matched', () => {
    // The exact disagreement the attribute exists to resolve: 1234px of
    // device viewport, 2480px of layout.
    expect(resolveScale(NARROW).breakpoint).toBe('xl');
  });
});
