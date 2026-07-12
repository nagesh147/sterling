// --- Original minimal inline SVG line-icons for the toolbar (16x16, stroke=currentColor) ---
// Simple, stroke-based, quick-to-recognize glyphs — not traced from any third-party icon set.
// Extracted verbatim from TradingViewKiteChart.tsx (pure split, zero behavior change).
export const ICON_BASE = {
  viewBox: '0 0 16 16',
  width: 14,
  height: 14,
  fill: 'none' as const,
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

export function IconCrosshair() {
  return (
    <svg {...ICON_BASE}>
      <circle cx="8" cy="8" r="5" />
      <line x1="8" y1="1" x2="8" y2="4" />
      <line x1="8" y1="12" x2="8" y2="15" />
      <line x1="1" y1="8" x2="4" y2="8" />
      <line x1="12" y1="8" x2="15" y2="8" />
    </svg>
  );
}

export function IconHLine() {
  return (
    <svg {...ICON_BASE}>
      <line x1="2" y1="8" x2="14" y2="8" />
      <circle cx="4" cy="8" r="1.3" fill="currentColor" stroke="none" />
      <circle cx="12" cy="8" r="1.3" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconTrendline() {
  return (
    <svg {...ICON_BASE}>
      <line x1="3" y1="13" x2="13" y2="3" />
      <circle cx="3" cy="13" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="13" cy="3" r="1.4" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconRay() {
  return (
    <svg {...ICON_BASE}>
      <line x1="2" y1="13" x2="12" y2="3" />
      <polyline points="7,3 12,3 12,8" />
    </svg>
  );
}

export function IconFib() {
  return (
    <svg {...ICON_BASE}>
      <line x1="2" y1="3" x2="14" y2="3" />
      <line x1="4" y1="6.5" x2="12" y2="6.5" />
      <line x1="2" y1="10" x2="14" y2="10" />
      <line x1="5" y1="13.5" x2="11" y2="13.5" />
    </svg>
  );
}

export function IconFibExt() {
  return (
    <svg {...ICON_BASE}>
      <line x1="1.5" y1="4" x2="9.5" y2="4" />
      <line x1="2.5" y1="8" x2="8.5" y2="8" />
      <line x1="1.5" y1="12" x2="9.5" y2="12" />
      <line x1="12.5" y1="6.5" x2="12.5" y2="10.5" />
      <line x1="10.5" y1="8.5" x2="14.5" y2="8.5" />
    </svg>
  );
}

export function IconFibFan() {
  return (
    <svg {...ICON_BASE}>
      <line x1="2" y1="14" x2="14" y2="14" />
      <line x1="2" y1="14" x2="2" y2="2" />
      <line x1="2" y1="14" x2="14" y2="4" />
      <line x1="2" y1="14" x2="14" y2="8" />
      <line x1="2" y1="14" x2="14" y2="12" />
    </svg>
  );
}

export function IconRect() {
  return (
    <svg {...ICON_BASE}>
      <rect x="2.5" y="3.5" width="11" height="9" rx="1.5" />
    </svg>
  );
}

export function IconPitchfork() {
  return (
    <svg {...ICON_BASE}>
      <line x1="2" y1="8" x2="9" y2="8" />
      <line x1="9" y1="8" x2="14" y2="2" />
      <line x1="9" y1="8" x2="14" y2="8" />
      <line x1="9" y1="8" x2="14" y2="14" />
    </svg>
  );
}

export function IconText() {
  return (
    <svg {...ICON_BASE}>
      <line x1="3" y1="3.5" x2="13" y2="3.5" />
      <line x1="8" y1="3.5" x2="8" y2="13" />
    </svg>
  );
}

export function IconPencil() {
  return (
    <svg {...ICON_BASE}>
      <path d="M3 13 L4 10 L11 3 L13 5 L6 12 Z" />
      <line x1="9.5" y1="4.5" x2="11.5" y2="6.5" />
    </svg>
  );
}

export function IconFullscreen() {
  return (
    <svg {...ICON_BASE}>
      <polyline points="2,6 2,2 6,2" />
      <polyline points="10,2 14,2 14,6" />
      <polyline points="14,10 14,14 10,14" />
      <polyline points="6,14 2,14 2,10" />
    </svg>
  );
}

export function IconClose() {
  return (
    <svg {...ICON_BASE}>
      <line x1="3" y1="3" x2="13" y2="13" />
      <line x1="13" y1="3" x2="3" y2="13" />
    </svg>
  );
}

export function IconMore() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
      <circle cx="3.5" cy="8" r="1.4" />
      <circle cx="8" cy="8" r="1.4" />
      <circle cx="12.5" cy="8" r="1.4" />
    </svg>
  );
}

// New: settings/gear glyph for the per-indicator param editor toggle in the
// Indicators modal. Same stroke-based convention as the other 13 (spreads
// ICON_BASE) — circle hub + 8 spokes to read as a simple gear at 14px.
export function IconGear() {
  return (
    <svg {...ICON_BASE}>
      <circle cx="8" cy="8" r="2.6" />
      <line x1="8" y1="1.5" x2="8" y2="3.4" />
      <line x1="8" y1="12.6" x2="8" y2="14.5" />
      <line x1="1.5" y1="8" x2="3.4" y2="8" />
      <line x1="12.6" y1="8" x2="14.5" y2="8" />
      <line x1="3.05" y1="3.05" x2="4.4" y2="4.4" />
      <line x1="11.6" y1="11.6" x2="12.95" y2="12.95" />
      <line x1="3.05" y1="12.95" x2="4.4" y2="11.6" />
      <line x1="11.6" y1="4.4" x2="12.95" y2="3.05" />
    </svg>
  );
}
