import React from 'react';
import { useMacKite } from '../../../hooks/useMacKite';

/* ─────────────────────────────────────────────────────────────────────────
 * MacSectionFade — spatial continuity when switching Kite nav sections.
 *
 * Off-path: a pure passthrough (`<>{children}</>`), zero behaviour change.
 * Mac mode: the outgoing section fades/settles out and the incoming one rises
 * in, keyed on `sectionKey`. Kept to opacity + a small vertical settle (no
 * horizontal slide) so it never spawns a scrollbar inside the content area's
 * overflow:auto host.
 * ───────────────────────────────────────────────────────────────────────── */
export function MacSectionFade({ sectionKey, children }: { sectionKey: string; children: React.ReactNode }) {
  const { on, motion, AnimatePresence, sp } = useMacKite();
  if (!on) return <>{children}</>;
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={sectionKey}
        className="mac-gpu"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={sp('standard')}
        style={{ height: '100%' }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
