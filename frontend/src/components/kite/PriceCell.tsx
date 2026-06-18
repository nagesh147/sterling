import React, { useRef } from 'react';
import { useMacKite } from '../../hooks/useMacKite';
import { MacPriceTicker } from './mac/MacPriceTicker';

/* ─────────────────────────────────────────────────────────────────────────
 * PriceCell — the single seam between a plain Kite number span and the Mac
 * Kite numeric roll.
 *
 *   Off path (Mac Kite off OR framer-motion still loading):
 *     renders the EXACT same <span style={…}>{text}</span> the watchlist uses
 *     today — byte-identical, zero new wrappers, zero perf cost.
 *   On path:
 *     renders <MacPriceTicker/> which rolls the digits and derives the
 *     up/down direction from the numeric delta vs the previous render.
 *
 * Direction is computed HERE (not by the caller) by remembering the previous
 * numeric value in a ref, so call sites stay clean — they just hand us the
 * formatted text, the raw number and the colour.
 *
 * Data integrity: `text` is always the live formatted string read synchronously
 * from the prop; the animation is purely decorative and never gates the value.
 * ───────────────────────────────────────────────────────────────────────── */

export interface PriceCellProps {
  /** Pre-formatted display text — the source of truth the trader reads. */
  text: string;
  /** Raw numeric value, used only to derive roll direction (up/down/flat). */
  value?: number | null;
  /** Text colour (Kite green/red/dim) for both off- and on-path. */
  color?: string;
  /** Off-path span style (the existing inline style of the cell). The on-path
      reuses font-size / weight / width / alignment from it for visual parity. */
  style?: React.CSSProperties;
}

export function PriceCell({ text, value, color, style }: PriceCellProps) {
  const { on } = useMacKite();

  // Track the previous numeric value to derive the roll direction. Kept across
  // renders regardless of mode so the first roll after toggling on is sensible.
  const prevValueRef = useRef<number | null | undefined>(value);
  const prev = prevValueRef.current;

  // Off path: verbatim span. NOTE we update the ref here too so direction is
  // correct on the very first frame after Mac Kite turns on.
  if (!on) {
    prevValueRef.current = value;
    return <span style={{ ...style, color }}>{text}</span>;
  }

  let direction: 'up' | 'down' | 'flat' = 'flat';
  if (value != null && prev != null) {
    if (value > prev) direction = 'up';
    else if (value < prev) direction = 'down';
  }
  prevValueRef.current = value;

  return <MacPriceTicker value={text} direction={direction} color={color} style={style} />;
}
