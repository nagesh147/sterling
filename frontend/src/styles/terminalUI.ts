import type { CSSProperties } from 'react';

/* ─────────────────────────────────────────────────────────────────────────
 * Sterling shared UI tokens — the single source of truth for the
 * "card / group-box / responsive-grid / chip" design language first
 * established in SterlingEngineTab. Every panel imports from here so the whole
 * app renders identically; tweak a value here and it propagates everywhere.
 *
 * Color tokens use a CSS fallback chain: the Bloomberg terminal palette
 * (--t-*) resolves inside `.term-root`, otherwise the global app palette
 * (--bg-*, --border, --text-*, --accent …) is used. The same token object
 * therefore works in both the Terminal pages and the global Dashboard.
 *
 * Design rules baked in:
 *  - flat: no box-shadow, no glow, no backdrop-blur
 *  - restrained radii (6 for groups, 8 for cards)
 *  - card body sits on the darkest surface, header strip one step lighter
 * ───────────────────────────────────────────────────────────────────────── */

export const c = {
  bg:      'var(--t-bg, var(--bg))',
  surface: 'var(--t-bg2, var(--bg-card))',
  raised:  'var(--t-bg3, var(--bg-surface))',
  border:  'var(--t-border, var(--border))',
  border2: 'var(--t-br2, var(--border-light))',
  text:    'var(--t-text, var(--text-muted))',
  bright:  'var(--t-bright, var(--text-primary))',
  dim:     'var(--t-dim, var(--text-dim))',
  muted:   'var(--t-muted, var(--text-muted-alt))',
  green:   'var(--t-green, var(--accent))',
  red:     'var(--t-red, var(--danger))',
  amber:   'var(--t-amber, var(--warning))',
  blue:    'var(--t-blue, var(--blue))',
  cyan:    'var(--t-cyan, var(--blue))',
  purple:  'var(--t-purple, var(--purple))',
  pink:    'var(--t-pink, var(--pink))',
  /* Gemini brand gradient (chrome accents only — not trading data) */
  brand:     'var(--brand)',
  brand1:    'var(--brand-1)',
  brand2:    'var(--brand-2)',
  brand3:    'var(--brand-3)',
  brandGrad: 'var(--brand-grad)',
} as const;

/* Translucent tint of any token color — replaces the old `var(--x)1c`
 * string-concat hack (which is invalid CSS). pct is 0–100. */
export function tint(color: string, pct = 12): string {
  return `color-mix(in srgb, ${color} ${pct}%, transparent)`;
}

/** Apply alpha (0–1 fraction) to any CSS variable.
 *  `alpha('var(--t-green)', 0.13)` → `color-mix(in srgb, var(--t-green) 13%, transparent)`
 *  Use this everywhere instead of the broken `${color}22` string concat. */
export function alpha(color: string, opacity: number): string {
  return `color-mix(in srgb, ${color} ${opacity * 100}%, transparent)`;
}

/* ── Card: bordered container with a header strip and a padded body ───────── */
export const card: CSSProperties = {
  background: c.bg,
  border: `1px solid ${c.border}`,
  borderRadius: 16,
  overflow: 'hidden',
  boxShadow: '0 1px 3px rgba(0,0,0,0.18)',
};

export const cardHead: CSSProperties = {
  padding: '12px 16px',
  borderBottom: `1px solid ${c.border}`,
  background: c.surface,
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: '0.06em',
  color: c.bright,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
};

export const cardBody: CSSProperties = { padding: 16 };

/* ── Group box: a labelled sub-section inside a card body ─────────────────── */
export const grpBox: CSSProperties = {
  background: c.surface,
  border: `1px solid ${c.border}`,
  borderRadius: 14,
  padding: 12,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
};

export const grpTitle: CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  letterSpacing: '0.06em',
  color: c.muted,
  marginBottom: 4,
  borderBottom: `1px solid ${c.border}`,
  paddingBottom: 4,
};

/* ── Responsive auto-flowing grid of cards / group boxes ──────────────────── */
export const grid = 'repeat(auto-fit, minmax(240px, 1fr))';

export function gridStyle(minPx = 240, gap = 12): CSSProperties {
  return {
    display: 'grid',
    gridTemplateColumns: `repeat(auto-fit, minmax(${minPx}px, 1fr))`,
    gap,
    alignItems: 'start',
  };
}

/* ── Selectable chip: subtle/dim when off, accent-tinted + bold when on ───── */
export function chipStyle(on: boolean, tone: string = c.green): CSSProperties {
  return {
    fontSize: 10,
    fontWeight: on ? 700 : 500,
    padding: '3px 10px',
    borderRadius: 999,
    cursor: 'pointer',
    fontFamily: 'inherit',
    border: `1px solid ${on ? tone : 'transparent'}`,
    background: on ? tint(tone) : c.raised,
    color: on ? tone : c.dim,
    transition: 'all 0.1s ease',
  };
}

/* ── Modals: flat overlay + plain bordered card (no glow/shadow) ──────────── */
export const overlay: CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.85)',
  zIndex: 3000,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
};

export const modal: CSSProperties = {
  background: c.surface,
  border: `1px solid ${c.border}`,
  borderRadius: 24,
  padding: '22px 24px',
  maxHeight: '90vh',
  overflowY: 'auto',
  boxShadow: '0 8px 40px rgba(0,0,0,0.40)',
};
