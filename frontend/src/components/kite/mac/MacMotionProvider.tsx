import React, { createContext, useEffect, useRef, useState, useCallback } from 'react';
import { useKiteSettings } from '../../../store/useKiteSettings';
import { MAC_KITE_CSS, springs } from '../../../styles/macMotion';

/* ─────────────────────────────────────────────────────────────────────────
 * MacMotionProvider — the on/off contract for Mac Kite.
 *
 * When macKite is OFF: renders children untouched, imports nothing, no class,
 * no styles. The app is byte-identical to stock Kite.
 *
 * When macKite is ON: lazy-imports framer-motion (so the default bundle path
 * never pays for it), injects the scoped token stylesheet, adds the `mac-kite`
 * class to the wrapper, and exposes the loaded motion handles + resolved
 * spring configs via context.
 * ───────────────────────────────────────────────────────────────────────── */

// The shape of the framer-motion handles we hand to consumers. Typed loosely
// (`any`) on purpose: the module is loaded dynamically, and consumers narrow.
export interface MacMotionContextValue {
  /** True only once framer-motion has finished loading and the mode is on. */
  on: boolean;
  /** OS-level reduced-motion preference — springs collapse to instant. */
  reduced: boolean;
  motion: any | null;
  AnimatePresence: any | null;
  LayoutGroup: any | null;
  springs: typeof springs;
  /** Tell the canvas to dim + scale (order ticket open). */
  setTicketOpen: (open: boolean) => void;
}

export const MacMotionContext = createContext<MacMotionContextValue>({
  on: false,
  reduced: false,
  motion: null,
  AnimatePresence: null,
  LayoutGroup: null,
  springs,
  setTicketOpen: () => {},
});

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() =>
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false
  );
  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!mq) return;
    const cb = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', cb);
    return () => mq.removeEventListener('change', cb);
  }, []);
  return reduced;
}

// Module-level cache so we only ever load framer-motion once per session.
let framerCache: { motion: any; AnimatePresence: any; LayoutGroup: any } | null = null;

export function MacMotionProvider({ children }: { children: React.ReactNode }) {
  const macKite = useKiteSettings((s) => s.macKite);
  const reduced = usePrefersReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const [lib, setLib] = useState(framerCache);
  const engagedFor = useRef(false);

  // Lazy-load framer-motion the first time Mac Kite turns on.
  useEffect(() => {
    if (!macKite || framerCache) return;
    let alive = true;
    import('framer-motion').then((m) => {
      framerCache = { motion: m.motion, AnimatePresence: m.AnimatePresence, LayoutGroup: m.LayoutGroup };
      if (alive) setLib(framerCache);
    });
    return () => { alive = false; };
  }, [macKite]);

  // Toggle the root class. One-time "mode engaged" settle on activation.
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    if (macKite) {
      el.classList.add('mac-kite');
      if (!engagedFor.current) {
        engagedFor.current = true;
        el.classList.add('mac-engaging');
        const t = setTimeout(() => el.classList.remove('mac-engaging'), 600);
        return () => clearTimeout(t);
      }
    } else {
      el.classList.remove('mac-kite', 'mac-engaging', 'mac-ticket-open');
      engagedFor.current = false;
    }
  }, [macKite]);

  const setTicketOpen = useCallback((open: boolean) => {
    rootRef.current?.classList.toggle('mac-ticket-open', open && macKite);
  }, [macKite]);

  const on = macKite && !!lib;
  const value: MacMotionContextValue = {
    on,
    reduced,
    motion: lib?.motion ?? null,
    AnimatePresence: lib?.AnimatePresence ?? null,
    LayoutGroup: lib?.LayoutGroup ?? null,
    springs,
    setTicketOpen,
  };

  return (
    <MacMotionContext.Provider value={value}>
      {/* Scoped stylesheet only mounts in Mac mode; inert otherwise. */}
      {macKite && <style>{MAC_KITE_CSS}</style>}
      <div ref={rootRef} style={{ display: 'contents' }}>
        {children}
      </div>
    </MacMotionContext.Provider>
  );
}
