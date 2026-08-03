// ─── Shared "which strike?" maths ───────────────────────────────────────────
// Pure functions reused by the signal rows (SterlingKiteEnginePane), the Trade
// Impact Calculator, the detail page and the marker store so the badges always
// mean the same thing. Kept in their OWN module (no React component exports) so
// the component files stay Fast-Refresh-eligible — mixing utilities with
// components in one file forces Vite into a full-page reload on every edit.
//
// WHY THE RANKING CHANGED (2026-07-31 audit)
// The previous score was `(δ·m + ½γm²) / min(premium, δ·m)`. Whenever premium
// ≥ δ·m — the common case — that reduces algebraically to `1 + γ·m/(2δ)`, so:
//   * it could never print below 1:1, and
//   * γ/|δ| is monotone across the strike ladder, so the badge deterministically
//     crowned the furthest-OTM leg on every signal, every day, no matter what
//     the premiums were.
// Measured on the repo's own greeks (NIFTY 24000, iv 12%, 1R = 120): a 2-DTE
// ladder scored 1.08 → 1.45 walking out to OTM2, and the badge landed on the
// leg advertising "1.4:1". Include the carry that leg actually pays over one
// day and the same leg scores 0.75 — holding it loses money even when the
// underlying does exactly what the signal predicted. Theta is the one term that
// breaks the tautology, and it was the one term left out.
//
// The score below is therefore an explicitly horizon-dependent, carry-inclusive
// R multiple, not a reward:risk ratio — the engine sets no target for a
// SuperTrend row (`EngineSignalRow.target` is None), so there is no reward to
// divide by, and anything claiming otherwise is inventing one.

/** How long a signal is assumed to be held when charging theta. The engine has
 *  no explicit holding period, so this is a stated assumption rather than a
 *  measured one — it is surfaced in the UI for that reason. */
export const DEFAULT_HOLD_DAYS = 1;

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

export type LegImpactInput = {
  delta: number;
  gamma: number;
  /** Per calendar day, negative for a long option. Pass 0 only if genuinely unknown. */
  theta: number;
  premium: number;
  /** 1R underlying move, from stopDistance(). */
  stopDist: number;
  holdDays?: number;
};

export type LegImpact = {
  /** Premium gained on a 1R favourable move, before carry. */
  grossMove: number;
  /** Theta paid over holdDays — negative. */
  carry: number;
  /** grossMove + carry: what the leg is actually worth if the signal is right. */
  netMove: number;
  /** Premium at risk to the stop, capped at the premium paid. */
  risk: number;
  /** netMove / risk. Below 1 means a correct call still does not pay its carry. */
  netR: number | null;
  /** netMove as a percentage of premium paid — capital efficiency. */
  effPct: number;
};

export function computeLegImpact(input: LegImpactInput): LegImpact {
  const d = Math.abs(input.delta) || 0;
  const g = Math.abs(input.gamma) || 0;
  const move = input.stopDist;
  const holdDays = input.holdDays ?? DEFAULT_HOLD_DAYS;
  const grossMove = d * move + 0.5 * g * move * move;
  // theta is already signed (negative for long premium); never flip it, and never
  // let a positive theta flatter the score.
  const carry = Math.min(0, (input.theta || 0) * holdDays);
  const netMove = grossMove + carry;
  const risk = Math.min(input.premium, d * move);
  return {
    grossMove,
    carry,
    netMove,
    risk,
    netR: risk > 0 ? netMove / risk : null,
    effPct: input.premium > 0 ? (netMove / input.premium) * 100 : 0,
  };
}

/** Sortable score for picking the best leg (net R, else capital efficiency). */
export function rrScore(netR: number | null, effPct: number): number {
  return netR ?? effPct / 100;
}

export type LegCandidate = {
  symbol: string;
  premium: number;
  delta: number;
  gamma: number;
  theta: number;
  /** False when the greeks are the degenerate intrinsic fallback (delta ±1.00,
   *  gamma 0) rather than a solved model. Such a leg wins "highest delta" on
   *  missing data alone, so it is never a candidate. */
  solved: boolean;
};

export type LegSelection = {
  /** Best carry-adjusted R across the signal's strikes, or null. */
  bestR: string | null;
  /** Highest |delta| across the signal's strikes, or null. */
  bestDelta: string | null;
  /** How many legs were rankable. Below 2 there is nothing to be "best" of. */
  rankable: number;
  /** Rankable legs that were dropped, and why — so the UI can say so. */
  skipped: Array<{ symbol: string; reason: 'no-price' | 'unsolved-greeks' }>;
};

/** The single source of truth for which legs wear ✝ and ▲.
 *
 * ONE global winner per signal, not one per moneyness bucket. The card used to
 * pick per bucket while the detail pane, impact calculator and marker store all
 * picked globally, and the shipped default ladder is exactly one leg per bucket
 * (ITM1/ATM/OTM1) — so every leg won both badges, the "Best ✝▲" filter removed
 * nothing, and the watchlist broadcast three simultaneous "best strike" claims
 * for the same signal.
 *
 * Returns nulls when fewer than two legs are rankable: a badge that every
 * candidate wears carries no information, and one that the sole candidate wears
 * is a tautology dressed as advice.
 */
export function selectBestLegs(
  candidates: LegCandidate[], stopDist: number, holdDays: number = DEFAULT_HOLD_DAYS,
): LegSelection {
  const skipped: LegSelection['skipped'] = [];
  const ranked: Array<{ symbol: string; score: number; absDelta: number }> = [];

  for (const leg of candidates) {
    if (!(leg.premium > 0)) {
      skipped.push({ symbol: leg.symbol, reason: 'no-price' });
      continue;
    }
    if (!leg.solved) {
      skipped.push({ symbol: leg.symbol, reason: 'unsolved-greeks' });
      continue;
    }
    const impact = computeLegImpact({
      delta: leg.delta, gamma: leg.gamma, theta: leg.theta,
      premium: leg.premium, stopDist, holdDays,
    });
    ranked.push({
      symbol: leg.symbol,
      score: rrScore(impact.netR, impact.effPct),
      absDelta: Math.abs(leg.delta),
    });
  }

  if (ranked.length < 2) {
    return { bestR: null, bestDelta: null, rankable: ranked.length, skipped };
  }
  // Ties resolve to the first leg in the caller's order (canonical ITM→ATM→OTM),
  // so the badge does not hop between equal legs as quotes tick.
  const bestR = ranked.reduce((a, b) => (b.score > a.score ? b : a));
  const bestDelta = ranked.reduce((a, b) => (b.absDelta > a.absDelta ? b : a));
  return { bestR: bestR.symbol, bestDelta: bestDelta.symbol, rankable: ranked.length, skipped };
}
