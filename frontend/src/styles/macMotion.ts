/* ─────────────────────────────────────────────────────────────────────────
 * Mac Kite — motion tokens (single source of truth)
 *
 * Apple-grade physics for the Kite app, used ONLY when Mac Kite mode is on.
 * Every Framer Motion consumer and every scoped CSS rule reads from here, so
 * there are no scattered magic numbers. See:
 *   docs/superpowers/specs/2026-06-19-mac-kite-design.md
 * ───────────────────────────────────────────────────────────────────────── */

import type { Transition } from 'framer-motion';

/* ── JS spring configs (Framer Motion) ─────────────────────────────────────
 * Stiff, low-bounce springs that settle fast — the "tactile lightweight
 * object" feel from the brief. `instant` is the reduced-motion substitute. */
export const springs = {
  /** Standard UI motion — panels, cards, morphs. */
  standard: { type: 'spring', stiffness: 400, damping: 30, mass: 0.8 } as Transition,
  /** Price ticker numeric roll — crisper, snappier. */
  ticker: { type: 'spring', stiffness: 450, damping: 35 } as Transition,
  /** Stage Manager panel reflow — slightly heavier so big panels feel weighty. */
  stage: { type: 'spring', stiffness: 350, damping: 32, mass: 0.9 } as Transition,
  /** Reduced-motion / off substitute — resolves immediately, no bounce. */
  instant: { duration: 0 } as Transition,
} as const;

/** Resolve the right spring given the user's reduced-motion preference. */
export function spring(key: keyof typeof springs, reduced: boolean): Transition {
  return reduced ? springs.instant : springs[key];
}

/* ── CSS easing/duration tokens ────────────────────────────────────────────
 * Injected as custom properties scoped under `.mac-kite` by MacMotionProvider.
 * Non-Framer surfaces (hovers, dim overlay, resizer handles) read these. */
export const MAC_EASE = 'cubic-bezier(0.25, 1, 0.5, 1)';       // crisp settle
export const MAC_EASE_POP = 'cubic-bezier(0.16, 1, 0.3, 1)';   // fluid pop-up

/**
 * Scoped stylesheet for Mac Kite mode. Everything lives under `.mac-kite` so
 * it is inert until the root class is present (off-path stays untouched), and
 * it self-disables when the OS asks for reduced motion.
 */
export const MAC_KITE_CSS = `
.mac-kite {
  --mac-ease: ${MAC_EASE};
  --mac-ease-pop: ${MAC_EASE_POP};
  --mac-hover: background-color 0.1s linear;
  --mac-dur-ticker: 150ms;
  --mac-dur-std: 300ms;
  --mac-dur-pop: 500ms;
}

/* GPU hygiene: promote hot layers, contain paint on dense lists. */
.mac-kite .mac-gpu { transform: translate3d(0, 0, 0); }
.mac-kite .mac-contain { contain: layout paint; }

/* Ultra-low-latency hover tint — keeps the row under the cursor, never lags. */
.mac-kite .mac-hover-tint { transition: var(--mac-hover); }

/* Background canvas dim + 2% scale-down while the order ticket is open. */
.mac-kite .mac-canvas {
  transition: transform var(--mac-dur-pop) var(--mac-ease-pop),
              filter var(--mac-dur-std) var(--mac-ease);
  transform-origin: center top;
  will-change: transform;
}
.mac-kite.mac-ticket-open .mac-canvas {
  transform: scale(0.98);
  filter: brightness(0.96);
}

/* One-time "mode engaged" settle — a single subtle breath of the whole canvas. */
@keyframes mac-engage {
  0%   { transform: scale(0.992); opacity: 0.6; }
  100% { transform: scale(1);     opacity: 1; }
}
.mac-kite.mac-engaging .mac-canvas {
  animation: mac-engage var(--mac-dur-pop) var(--mac-ease-pop);
}

/* Respect the user: motion-sensitive folks get the layout, not the bounce. */
@media (prefers-reduced-motion: reduce) {
  .mac-kite.mac-ticket-open .mac-canvas { transform: none; }
  .mac-kite.mac-engaging .mac-canvas { animation: none; }
}
`;
