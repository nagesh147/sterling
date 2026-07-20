import React from 'react';

export interface PriceCellProps {
  /** Pre-formatted display text — the source of truth the trader reads. */
  text: string;
  /** Retained for call-site compatibility; rendering is intentionally static. */
  value?: number | null;
  color?: string;
  style?: React.CSSProperties;
}

/**
 * Dense trading tables can contain hundreds of numeric cells. The previous Mac
 * mode path mounted an AnimatePresence and motion element for every changed
 * character in every cell, on every live-price batch. That decorative odometer
 * competed with pointer input and made CSS hover feedback visibly late.
 *
 * Zerodha-style responsiveness prioritises instant text replacement and stable
 * tabular columns, so price cells now stay on the browser's cheapest static path.
 */
export const PriceCell = React.memo(function PriceCell({ text, color, style }: PriceCellProps) {
  return (
    <span
      style={{
        display: 'inline-block',
        fontVariantNumeric: 'tabular-nums',
        ...style,
        color,
      }}
    >
      {text}
    </span>
  );
});
