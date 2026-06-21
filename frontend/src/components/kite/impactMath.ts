// ─── Shared "✝ BEST R:R" maths ──────────────────────────────────────────────
// Pure functions reused by the signal rows (TripleSupertrendPane), the Trade
// Impact Calculator, and the detail page so the badges always mean the same
// thing. Kept in their OWN module (no React component exports) so the component
// files stay Fast-Refresh-eligible — mixing utilities with components in one
// file forces Vite into a full-page reload on every edit.

/** A sane default move when there is no usable stop: ~1% of spot, clamped to a
 *  clean 10–100 pt band (e.g. SENSEX 76,803 → 100, not the full index level). */
export function defaultMove(spot: number): number {
  return Math.max(10, Math.min(100, Math.round((spot || 0) * 0.01)));
}

/** 1R unit = distance from spot to the signal stop. A missing/zero stop (where
 *  `d` collapses to the whole spot level) or an absurdly far one is meaningless
 *  as 1R, so we fall back to a clean default move instead. */
export function stopDistance(spot: number, stop: number): number {
  const s = spot || 0;
  const d = Math.abs(s - (stop || 0));
  if (stop > 0 && d > 0 && d <= s * 0.5) return Math.round(d);
  return defaultMove(s);
}

/** Reward:risk + capital efficiency for one leg given a 1R move (= stopDist). */
export function computeLegRR(delta: number, gamma: number, premium: number, stopDist: number): { rr: number | null; effPct: number } {
  const d = Math.abs(delta) || 0;
  const g = Math.abs(gamma) || 0;
  const move = stopDist;
  const optMove = d * move + 0.5 * g * move * move;          // Δpremium ≈ δ·move + ½γ·move²
  const risk = Math.min(premium, d * move);                  // capped at premium paid
  const rr = risk > 0 ? optMove / risk : null;
  const effPct = premium > 0 ? (optMove / premium) * 100 : 0;
  return { rr, effPct };
}

/** Sortable score for picking the best leg (R:R, else capital efficiency). */
export function rrScore(rr: number | null, effPct: number): number {
  return rr ?? effPct / 100;
}
