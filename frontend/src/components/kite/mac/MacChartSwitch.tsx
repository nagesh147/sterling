import React from 'react';
import { useMacKite } from '../../../hooks/useMacKite';

/* ─────────────────────────────────────────────────────────────────────────
 * MacChartSwitch — "Magic Move" contextual chart switch (Mac Kite mode).
 *
 *   <MacChartSwitch switchKey={underlyingOrToken}>{chart}</MacChartSwitch>
 *
 * When the charted asset/symbol changes, the outgoing plot scales horizontally
 * + fades out toward the left, and the incoming asset draws in from the RIGHT
 * canvas edge. The effect is a sliding crossfade keyed on `switchKey`.
 *
 * Off-path (Mac Kite off, or framer-motion not yet loaded): a pure passthrough
 * — `<>{children}</>`, zero added DOM / layout / behaviour. Byte-identical.
 *
 * CRITICAL — lightweight-charts safety:
 *   lightweight-charts renders into a <canvas> and measures its parent on mount
 *   + via a ResizeObserver. We therefore animate ONLY a wrapping motion.div
 *   AROUND the chart, using transform (x / scaleX) and opacity — neither of which
 *   triggers layout, so the chart's own container keeps a stable box and its
 *   ResizeObserver never fires spuriously.
 *
 *   Because AnimatePresence keys on `switchKey`, a NEW subtree (and therefore a
 *   fresh chart instance, for callers whose chart effect depends on the same
 *   key) mounts for the incoming symbol once the outgoing one has animated out.
 *
 *   We use `mode="wait"` and an IN-FLOW (position: relative) animated layer
 *   rather than absolute stacking. Why: callers wrap two very different kinds of
 *   host — a fixed-box lightweight-charts canvas (SetupChart) AND auto-height
 *   table content (MarketDataPane). An absolutely-stacked layer would collapse
 *   the auto-height host to zero. An in-flow layer drives the host height
 *   naturally in both cases, and the incoming chart canvas measures the correct
 *   final size from frame one because we animate transform/opacity only (no
 *   layout-affecting properties). `mode="wait"` also guarantees only ONE chart
 *   instance is mounted at a time, so two lightweight-charts canvases never race
 *   for the same box. The trade-off is a sequential (not overlapping) crossfade.
 *
 * framer-motion is NEVER statically imported — handles come from useMacKite().
 * ───────────────────────────────────────────────────────────────────────── */

export interface MacChartSwitchProps {
  /** Identity of the charted asset. A change triggers the Magic Move. */
  switchKey: string | number;
  children: React.ReactNode;
}

export function MacChartSwitch({ switchKey, children }: MacChartSwitchProps) {
  const { on, motion, AnimatePresence, sp } = useMacKite();

  // Off-path: transparent passthrough, identical to stock Kite.
  if (!on) return <>{children}</>;

  const transition = sp('standard');

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={switchKey}
          className="mac-gpu"
          initial={{ x: 24, opacity: 0, scaleX: 0.98 }}
          animate={{ x: 0, opacity: 1, scaleX: 1 }}
          exit={{ x: -12, opacity: 0, scaleX: 0.96 }}
          transition={transition}
          style={{
            // In-flow layer: drives host height for both fixed-box charts and
            // auto-height table content. Transform-only animation never reflows.
            position: 'relative',
            width: '100%',
            height: '100%',
            // scaleX grows/shrinks from the right edge so the incoming plot
            // reads as drawing in from that edge, matching --mac-ease feel.
            transformOrigin: 'right center',
            willChange: 'transform, opacity',
          }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

export default MacChartSwitch;
