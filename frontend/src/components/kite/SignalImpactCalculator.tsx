import React, { useMemo, useState } from 'react';
import { k } from '../../styles/kiteUI';
import type { EngineDetailResponse, OptionDetail } from '../../types/kiteEngine';

// ─── Per-strike impact maths ───────────────────────────────────────────────────
// All figures are first-order (delta) with a gamma correction for larger moves,
// using the live Black-Scholes greeks the backend already computed per leg. They
// are decision aids, not fills — real P&L depends on exit IV and spread.

interface Row {
  leg: OptionDetail;
  premium: number;
  lot: number;
  costPerLot: number;          // premium × lot
  optMovePerShare: number;     // Δpremium for a favourable `move`
  projGainPerLot: number;      // favourable move → ₹/lot
  riskToStopPerLot: number;    // premium loss per lot if underlying hits the signal stop
  thetaPerLotDay: number;      // ₹/lot/day decay (negative)
  breakEvenPts: number;        // pts the underlying must move to recover premium
  probItm: number;             // ≈ |delta| × 100
  rr: number | null;           // reward : risk (proj gain / risk-to-stop)
  effPct: number;              // proj gain as % of cost deployed
}

// ─── Shared "★ BEST R:R" logic ──────────────────────────────────────────────
// Reused by the signal rows (TripleSupertrendPane) and the detail page so the
// badge always means the same thing: among a signal's option legs, the strike
// with the best reward:risk for a 1R move (ties fall back to capital efficiency).

/** 1R unit = distance from spot to the signal stop; falls back to ~0.5% of spot. */
export function stopDistance(spot: number, stop: number): number {
  const d = Math.abs((spot || 0) - (stop || 0));
  if (d > 0) return Math.round(d);
  return Math.max(10, Math.round((spot || 0) * 0.005));
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

function computeRow(leg: OptionDetail, move: number, stopMove: number): Row {
  const premium = leg.last_price || 0;
  const lot = leg.lot_size || 1;
  const delta = Math.abs(leg.delta) || 0;
  const gamma = Math.abs(leg.gamma) || 0;
  const theta = leg.theta || 0; // per-share per-day, already signed (negative)

  // Δpremium ≈ δ·move + ½·γ·move²  (gamma helps a buyer on a favourable move)
  const optMovePerShare = delta * move + 0.5 * gamma * move * move;
  const projGainPerLot = optMovePerShare * lot;
  const costPerLot = premium * lot;

  // Loss if the underlying runs to the signal's stop: premium drops ≈ δ·stopMove,
  // but it can never fall below zero — capped at the premium paid.
  const lossPerShareAtStop = Math.min(premium, delta * stopMove);
  const riskToStopPerLot = lossPerShareAtStop * lot;

  const thetaPerLotDay = theta * lot;
  const breakEvenPts = delta > 0 ? premium / delta : Infinity;
  const probItm = Math.round(delta * 100);
  const rr = riskToStopPerLot > 0 ? projGainPerLot / riskToStopPerLot : null;
  const effPct = costPerLot > 0 ? (projGainPerLot / costPerLot) * 100 : 0;

  return {
    leg, premium, lot, costPerLot, optMovePerShare, projGainPerLot,
    riskToStopPerLot, thetaPerLotDay, breakEvenPts, probItm, rr, effPct,
  };
}

const inr = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`;

// ─── Component ─────────────────────────────────────────────────────────────────

interface Props {
  data: EngineDetailResponse;
  onBuy?: (leg: OptionDetail) => void;
  updatedAt?: number; // ms epoch of the snapshot these greeks came from
}

export function SignalImpactCalculator({ data, onBuy, updatedAt }: Props) {
  // Natural "1R" unit = distance from spot to the signal's stop. Falls back to
  // ~0.5% of spot when no stop is available.
  const stopDist = useMemo(() => {
    const d = Math.abs((data.spot_now || data.spot_at_trigger) - data.stop_loss);
    if (d > 0) return Math.round(d);
    return Math.max(10, Math.round((data.spot_now || data.spot_at_trigger) * 0.005));
  }, [data]);

  const [move, setMove] = useState<number>(stopDist);
  const [lotsMult, setLotsMult] = useState<number>(1);

  // Recompute when the stop distance changes (new signal selected).
  React.useEffect(() => { setMove(stopDist); }, [stopDist]);

  const rows = useMemo(
    () => data.options.map((leg) => computeRow(leg, move, stopDist)),
    [data.options, move, stopDist],
  );

  // Recommend the strike with the best reward:risk for this move. Ties/no-stop
  // fall back to capital efficiency.
  const recommended = useMemo(() => {
    if (!rows.length) return null;
    const scored = [...rows].sort((a, b) => {
      const ar = a.rr ?? a.effPct / 100;
      const br = b.rr ?? b.effPct / 100;
      return br - ar;
    });
    return scored[0]?.leg.option_symbol ?? null;
  }, [rows]);

  if (!data.options.length) return null;

  const dirWord = data.direction === 'long' ? 'up' : 'down';
  const quickMoves: { label: string; v: number }[] = [
    { label: '½R', v: Math.round(stopDist / 2) },
    { label: '1R', v: stopDist },
    { label: '2R', v: stopDist * 2 },
    { label: '3R', v: stopDist * 3 },
  ];

  return (
    <div style={{ border: `1px solid ${k.border}`, borderRadius: 8, marginBottom: 16, overflow: 'hidden' }}>
      <div style={{ padding: '12px 16px', background: k.surface, borderBottom: `1px solid ${k.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: k.text }}>Trade Impact Calculator</span>
          <span style={{ fontSize: 11, color: k.dim }}>
            Live greeks · {data.option_type} · {data.underlying} {data.spot_now ? data.spot_now.toFixed(0) : ''} ·
            stop {data.stop_loss.toFixed(0)} ({stopDist} pts = 1R)
          </span>
          {updatedAt && (
            <span title="These greeks are a snapshot. The detail auto-refreshes every 15s; reopening always re-fetches."
              style={{ marginLeft: 'auto', fontSize: 10, color: k.dim, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: k.green, display: 'inline-block' }} />
              as of {new Date(updatedAt).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })} · refreshes 15s
            </span>
          )}
        </div>

        {/* Move + lots controls */}
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end', flexWrap: 'wrap', marginTop: 10 }}>
          <div>
            <div style={{ fontSize: 10, color: k.dim, marginBottom: 4, fontWeight: 600 }}>
              IF {data.underlying} MOVES {dirWord.toUpperCase()}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <input type="number" value={move} step={5}
                onChange={(e) => setMove(Math.max(1, Number(e.target.value) || stopDist))}
                style={{ width: 72, fontSize: 12, padding: '4px 8px', border: `1px solid ${k.border}`, borderRadius: 4, textAlign: 'right', background: k.bg, color: k.text }} />
              <span style={{ fontSize: 11, color: k.dim }}>pts</span>
              <div style={{ display: 'flex', gap: 4, marginLeft: 4 }}>
                {quickMoves.map((q) => (
                  <button key={q.label} onClick={() => setMove(q.v)}
                    style={{
                      fontSize: 10, padding: '3px 8px', borderRadius: 4, cursor: 'pointer',
                      border: `1px solid ${move === q.v ? k.orange : k.border}`,
                      background: move === q.v ? k.orange : k.bg,
                      color: move === q.v ? '#fff' : k.dim, fontWeight: 600,
                    }}>{q.label}</button>
                ))}
              </div>
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: k.dim, marginBottom: 4, fontWeight: 600 }}>LOTS</div>
            <input type="number" value={lotsMult} min={1} step={1}
              onChange={(e) => setLotsMult(Math.max(1, Number(e.target.value) || 1))}
              style={{ width: 56, fontSize: 12, padding: '4px 8px', border: `1px solid ${k.border}`, borderRadius: 4, textAlign: 'right', background: k.bg, color: k.text }} />
          </div>
        </div>
      </div>

      {/* Per-strike comparison */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ color: k.dim, fontSize: 10, borderBottom: `1px solid ${k.border}` }}>
              <th style={th('left')}>Strike</th>
              <th style={th('right')} title="Last traded premium and your cost per lot × lots">Cost</th>
              <th style={th('right')} title="Black-Scholes delta ≈ probability of finishing in-the-money">δ / ITM%</th>
              <th style={th('right')} title={`Projected profit if ${data.underlying} moves ${move} pts ${dirWord}`}>If +{move}pts</th>
              <th style={th('right')} title="Premium lost per lot if the underlying runs to the signal's stop">Risk→SL</th>
              <th style={th('right')} title="Reward : risk for this move vs the stop">R:R</th>
              <th style={th('right')} title="Premium lost to time decay per day if nothing moves">θ/day</th>
              <th style={th('right')} title="Points the underlying must move just to recover the premium">B/E</th>
              <th style={th('right')} />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const isRec = r.leg.option_symbol === recommended;
              const totalCost = r.costPerLot * lotsMult;
              const totalGain = r.projGainPerLot * lotsMult;
              const totalRisk = r.riskToStopPerLot * lotsMult;
              const totalTheta = r.thetaPerLotDay * lotsMult;
              return (
                <tr key={r.leg.option_symbol}
                  style={{ borderBottom: `1px solid ${k.border}`, background: isRec ? 'rgba(46,125,50,0.06)' : 'transparent' }}>
                  <td style={td('left')}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, fontWeight: 700, background: 'rgba(240,100,40,0.12)', color: k.orange }}>
                        {r.leg.moneyness}
                      </span>
                      <span style={{ fontWeight: 500 }}>{r.leg.strike}</span>
                      {isRec && (
                        <span title="Best reward-to-risk for this move"
                          style={{ fontSize: 9, fontWeight: 700, color: '#fff', background: k.green, padding: '1px 6px', borderRadius: 3 }}>
                          ★ BEST R:R
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 10, color: k.dim, marginTop: 2 }}>
                      LTP {r.premium.toFixed(2)} · {r.lot}/lot · {r.leg.dte}d
                    </div>
                  </td>
                  <td style={td('right')}>
                    <div style={{ fontWeight: 600 }}>{inr(totalCost)}</div>
                    <div style={{ fontSize: 10, color: k.dim }}>max loss</div>
                  </td>
                  <td style={td('right')}>
                    <div>{r.leg.delta.toFixed(2)}</div>
                    <div style={{ fontSize: 10, color: k.dim }}>{r.probItm}%</div>
                  </td>
                  <td style={td('right')}>
                    <div style={{ color: k.green, fontWeight: 700 }}>+{inr(totalGain)}</div>
                    <div style={{ fontSize: 10, color: k.dim }}>{r.effPct.toFixed(0)}% on cost</div>
                  </td>
                  <td style={td('right')}>
                    <div style={{ color: k.red, fontWeight: 600 }}>−{inr(totalRisk)}</div>
                  </td>
                  <td style={td('right')}>
                    <span style={{
                      fontWeight: 700,
                      color: r.rr == null ? k.dim : r.rr >= 2 ? k.green : r.rr >= 1 ? k.amber : k.red,
                    }}>
                      {r.rr == null ? '—' : `${r.rr.toFixed(1)}:1`}
                    </span>
                  </td>
                  <td style={td('right')}>
                    <span style={{ color: k.red }}>{inr(totalTheta)}</span>
                  </td>
                  <td style={td('right')}>
                    <span style={{ color: k.dim }}>{isFinite(r.breakEvenPts) ? `${Math.round(r.breakEvenPts)}p` : '—'}</span>
                  </td>
                  <td style={td('right')}>
                    {onBuy && (
                      <button onClick={() => onBuy(r.leg)}
                        style={{ fontSize: 11, padding: '3px 12px', background: k.blue, color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>
                        BUY
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Plain-English read of the recommended strike */}
      {(() => {
        const rec = rows.find((r) => r.leg.option_symbol === recommended);
        if (!rec) return null;
        return (
          <div style={{ padding: '10px 16px', fontSize: 11, color: k.dim, lineHeight: 1.6, borderTop: `1px solid ${k.border}`, background: k.surface }}>
            <strong style={{ color: k.text }}>Read:</strong> the <strong>{rec.leg.moneyness} {rec.leg.strike}</strong> gives the best
            reward-to-risk here — a {move}-pt move {dirWord} turns ~{inr(rec.costPerLot * lotsMult)} of premium into
            <strong style={{ color: k.green }}> +{inr(rec.projGainPerLot * lotsMult)}</strong>, against
            <strong style={{ color: k.red }}> −{inr(rec.riskToStopPerLot * lotsMult)}</strong> if it hits the stop instead.
            {rec.probItm < 40 && ' Low delta — it needs the move to come quickly before theta bites.'}
            {rec.probItm >= 60 && ' Higher delta — pricier, but behaves closer to the underlying with less time decay.'}
            <br />Figures are first-order greeks (with a gamma boost on big moves); exit IV and spread will shift the real fill.
          </div>
        );
      })()}
    </div>
  );
}

function th(align: 'left' | 'right'): React.CSSProperties {
  return { padding: '6px 10px', textAlign: align, fontWeight: 500, whiteSpace: 'nowrap' };
}
function td(align: 'left' | 'right'): React.CSSProperties {
  return { padding: '8px 10px', textAlign: align, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' };
}

export default SignalImpactCalculator;
