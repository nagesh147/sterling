import React, { useRef } from 'react';
import { useMacKite } from '../../../hooks/useMacKite';

/* ─────────────────────────────────────────────────────────────────────────
 * MacPriceTicker — Apple-grade numeric roll for live prices (Mac Kite mode).
 *
 * A masked, overflow-hidden strip whose digits slide vertically when the value
 * changes: UP for an increase, DOWN for a decrease. The colour rides in WITH the
 * new value (the outgoing value exits in its own colour) so there is never an
 * abrupt colour flash — the value and its colour change in one continuous move.
 *
 * Per-digit odometer enhancement: only the character columns that actually
 * changed roll; unchanged leading characters (e.g. the "1,2" in "1,234.50" when
 * only the cents tick) stay perfectly still. This is both cheaper and reads as a
 * true mechanical odometer. If the formatted-string LENGTH changes (a digit was
 * added/removed, e.g. 999.99 → 1,000.00) we cannot align columns 1:1, so we fall
 * back to rolling the whole value as a single unit — robust over clever.
 *
 * CRITICAL: framer-motion is NEVER statically imported here. We take the
 * `motion` / `AnimatePresence` handles from useMacKite(), which only resolve
 * once the library has lazy-loaded. Off-path callers never reach this file (see
 * PriceCell), so this component always runs with `on === true`.
 * ───────────────────────────────────────────────────────────────────────── */

export interface MacPriceTickerProps {
  /** The already-formatted display text (e.g. "1,234.50", "12.5%", "—"). */
  value: number | string;
  /** Roll direction derived from the numeric delta vs the previous value. */
  direction: 'up' | 'down' | 'flat';
  /** Text colour for the incoming value (Kite green/red/dim). */
  color?: string;
  /** Extra style for the strip (font-size, weight, width, alignment). */
  style?: React.CSSProperties;
}

/** Vertical travel of the roll, in px. Small — these are dense list cells. */
const ROLL = 12;

export function MacPriceTicker({ value, direction, color, style }: MacPriceTickerProps) {
  const { motion, AnimatePresence, sp } = useMacKite();
  const text = String(value);

  // Remember the previous formatted text so we can diff columns for the
  // per-digit odometer. Updated on every render (after we've used the old one).
  const prevTextRef = useRef<string>(text);
  const prevText = prevTextRef.current;
  prevTextRef.current = text;

  // The masked container: fixed height (one line), clips the sliding glyphs.
  const stripStyle: React.CSSProperties = {
    position: 'relative',
    display: 'inline-flex',
    overflow: 'hidden',
    height: '1.25em',
    lineHeight: '1.25em',
    whiteSpace: 'nowrap',
    color,
    ...style,
  };

  // Reduced-motion resolves sp('ticker') to { duration: 0 }, so the same JSX
  // path collapses to an instant swap — no special-casing needed here.
  const transition = sp('ticker');
  const enterY = direction === 'down' ? -ROLL : ROLL; // up ⇒ rise from below
  const exitY = direction === 'down' ? ROLL : -ROLL;  // up ⇒ old leaves upward

  // One animated character column. The whole odometer is built from these; for
  // the whole-value fallback we render a single column holding the entire string.
  const Column = (key: string, content: string) => (
    <span style={{ position: 'relative', display: 'inline-block', overflow: 'hidden', height: '1.25em' }}>
      {/* Reserve width with an invisible copy of the (stable) current glyph so
          the row never reflows horizontally as the value rolls vertically. */}
      <span style={{ visibility: 'hidden' }} aria-hidden>{content}</span>
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={key}
          className="mac-gpu"
          initial={{ y: enterY, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: exitY, opacity: 0 }}
          transition={transition}
          style={{ position: 'absolute', left: 0, top: 0 }}
        >
          {content}
        </motion.span>
      </AnimatePresence>
    </span>
  );

  // Length changed (a column was added/removed) — align is impossible, so roll
  // the entire string as one unit. Robust fallback.
  if (prevText.length !== text.length) {
    return <span style={stripStyle} aria-label={text}>{Column(text, text)}</span>;
  }

  // Same length ⇒ per-character odometer. Each column keys off its OWN glyph so
  // only the columns whose glyph actually changed re-mount and roll; unchanged
  // leading characters keep the same key and stay put.
  return (
    <span style={stripStyle} aria-label={text}>
      {text.split('').map((ch, i) => Column(`${i}:${ch}`, ch))}
    </span>
  );
}
