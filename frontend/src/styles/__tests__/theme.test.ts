/**
 * The theme's load-bearing invariants.
 *
 * The migration that introduced these tokens rewrote ~2,000 literal colours
 * across the app. It was only safe because of one property — every token's
 * light value is the exact hex it replaced — so that property is worth a test
 * rather than a comment.
 */
import { describe, it, expect } from 'vitest';
import { THEME_TOKENS, themeCss, readThemeHex } from '../theme';
import { k } from '../kiteUI';

const HEX = /^#[0-9a-f]{3,8}$/;

function luminance(hex: string): number {
  let h = hex.slice(1);
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const [r, g, b] = [0, 2, 4].map((i) => {
    const v = parseInt(h.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const contrast = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

describe('theme tokens', () => {
  it('names every token once', () => {
    const names = THEME_TOKENS.map((t) => t[0]);
    expect(new Set(names).size).toBe(names.length);
  });

  it('gives every token a light and a dark value', () => {
    for (const [name, light, dark] of THEME_TOKENS) {
      expect(light, `${name} light`).toMatch(HEX);
      expect(dark, `${name} dark`).toMatch(HEX);
    }
  });

  it('never maps one light colour to two different dark ones', () => {
    // Two tokens may legitimately share a light value only if they agree in
    // dark — otherwise the same on-screen colour would split in two when the
    // theme flips, which is a redesign, not a translation.
    const byLight = new Map<string, Set<string>>();
    for (const [, light, dark] of THEME_TOKENS) {
      const key = light.toLowerCase();
      if (!byLight.has(key)) byLight.set(key, new Set());
      byLight.get(key)!.add(dark.toLowerCase());
    }
    const split = [...byLight.entries()].filter(([, darks]) => darks.size > 1);
    expect(split.map(([l, d]) => `${l} -> ${[...d].join(', ')}`)).toEqual([]);
  });

  it('actually changes colour in dark — no token is a no-op', () => {
    const unchanged = THEME_TOKENS.filter(([, l, d]) => l.toLowerCase() === d.toLowerCase());
    expect(unchanged.map(([n]) => n)).toEqual([]);
  });

  it('keeps every accent legible on the dark surfaces', () => {
    // The dark palette is only worth having if the numbers on it can be read.
    const bg = THEME_TOKENS.find((t) => t[0] === 'bg')![2];
    const surface = THEME_TOKENS.find((t) => t[0] === 'surface')![2];
    // Fills and hairlines are not text and are exempt; on-accent is measured
    // against its accent, not against the page.
    const exempt = /^(bg|surface|border|hairline|tint|on-accent)/;
    const failures: string[] = [];
    for (const [name, , dark] of THEME_TOKENS) {
      if (exempt.test(name)) continue;
      const worst = Math.min(contrast(dark, bg), contrast(dark, surface));
      if (worst < 4.5) failures.push(`${name} ${dark} = ${worst.toFixed(2)}:1`);
    }
    expect(failures).toEqual([]);
  });

  it('inverts on-accent, because the accents lighten for dark', () => {
    const [, light, dark] = THEME_TOKENS.find((t) => t[0] === 'on-accent')!;
    expect(luminance(light)).toBeGreaterThan(0.8);
    expect(luminance(dark)).toBeLessThan(0.05);
  });

  it('reads accent-filled controls in dark', () => {
    // Every accent that a control actually fills with, paired with on-accent.
    const fgDark = THEME_TOKENS.find((t) => t[0] === 'on-accent')![2];
    for (const filled of ['blue-kite', 'blue', 'blue-deep', 'brand', 'orange', 'green', 'violet', 'warn', 'amber-3']) {
      const dark = THEME_TOKENS.find((t) => t[0] === filled)![2];
      expect(contrast(dark, fgDark), `${filled} dark`).toBeGreaterThan(4.5);
    }
  });

  it('records which filled accents were already illegible in light', () => {
    // These predate the theme work: the app has always drawn white on them,
    // and this migration kept light mode byte-identical rather than quietly
    // restyling brand colours. Pinned so the debt stays visible and so a NEW
    // failing pair shows up here as a diff instead of shipping unnoticed.
    const fgLight = THEME_TOKENS.find((t) => t[0] === 'on-accent')![1];
    const failing = ['blue-kite', 'blue', 'blue-deep', 'brand', 'orange', 'green', 'violet', 'warn', 'amber-3']
      .filter((n) => contrast(THEME_TOKENS.find((t) => t[0] === n)![1], fgLight) < 4.5);
    expect(failing).toEqual(['blue-kite', 'blue', 'brand', 'orange', 'green', 'warn', 'amber-3']);
  });
});

describe('themeCss', () => {
  it('declares every token in both blocks', () => {
    const css = themeCss();
    for (const [name] of THEME_TOKENS) {
      expect(css.match(new RegExp(`--k-${name}:`, 'g'))?.length, name).toBe(2);
    }
  });

  it('lets the dark blocks win on specificity', () => {
    const css = themeCss();
    expect(css.indexOf(':root{')).toBeLessThan(css.indexOf('[data-theme="dark"]'));
    // Both dark shells the app already had, so the Kite panes follow the same
    // switch the outer terminal has always used.
    expect(css).toContain('[data-theme="grey"]');
  });
});

describe('the k token object', () => {
  it('resolves entirely through variables, so nothing is pinned to one theme', () => {
    for (const [key, value] of Object.entries(k)) {
      if (key === 'fontFamily') continue;
      expect(value, key).toMatch(/^var\(--k-[a-z0-9-]+\)$/);
    }
  });

  it('points only at tokens that exist', () => {
    const names = new Set(THEME_TOKENS.map((t) => t[0]));
    for (const [key, value] of Object.entries(k)) {
      if (key === 'fontFamily') continue;
      expect(names, key).toContain(value.replace(/^var\(--k-|\)$/g, ''));
    }
  });
});

describe('readThemeHex', () => {
  it('falls back rather than returning empty when a token is absent', () => {
    // Canvas code paints with whatever this returns; '' would silently draw
    // nothing at all.
    expect(readThemeHex('definitely-not-a-token', '#123456')).toBe('#123456');
  });
});
