import { useContext } from 'react';
import { MacMotionContext } from '../components/kite/mac/MacMotionProvider';
import { spring as resolveSpring, springs } from '../styles/macMotion';

/* ─────────────────────────────────────────────────────────────────────────
 * useMacKite — the single consumer hook for Mac Kite mode.
 *
 *   const { on, motion, AnimatePresence, springs, sp, reduced } = useMacKite();
 *   if (!on) return <ExistingMarkup/>;     // verbatim off-path
 *   return <motion.div transition={sp('standard')} .../>;
 *
 * `on` is false until framer-motion has finished lazy-loading, so callers
 * always have a safe static path to render (no Suspense boundary required).
 * `sp(key)` resolves a spring honouring the user's reduced-motion preference.
 * ───────────────────────────────────────────────────────────────────────── */
export function useMacKite() {
  const ctx = useContext(MacMotionContext);
  const sp = (key: keyof typeof springs) => resolveSpring(key, ctx.reduced);
  return { ...ctx, sp };
}
