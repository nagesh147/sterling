import React, { useMemo, useState } from 'react';
import { k } from '../../styles/kiteUI';
import type { EngineDetailResponse, OptionDetail } from '../../types/kiteEngine';
import { stopDistance } from './impactMath';

// ─── Per-strike impact maths ───────────────────────────────────────────────────
// All figures are first-order (delta) with a gamma correction for larger moves,
// using the live Black-Scholes greeks the backend already computed per leg. They
// are decision aids, not fills — real P&L depends on exit IV and spread.
// Shared pure helpers (stopDistance, computeLegRR, rrScore, defaultMove) live in
// ./impactMath so this file exports only components and stays Fast-Refresh-safe.

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
  const spot = data.spot_now || data.spot_at_trigger;
  const stopDist = useMemo(
    () => stopDistance(spot, data.stop_loss),
    [spot, data.stop_loss],
  );
  const hasStop = data.stop_loss > 0 && stopDist <= spot * 0.5;

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

  // Best delta: leg with the highest |delta| (most responsive to the underlying —
  // the deepest ITM strike here moves nearest 1:1 with spot).
  const bestDeltaSym = useMemo(() => {
    if (!rows.length) return null;
    return rows.reduce((best, r) =>
      Math.abs(r.leg.delta) > Math.abs(best.leg.delta) ? r : best
    ).leg.option_symbol;
  }, [rows]);

  if (!data.options.length) return null;

  const dirWord = data.direction === 'long' ? 'up' : 'down';
  const quickMoves: { label: string; v: number }[] = hasStop
    ? [
        { label: '½R', v: Math.round(stopDist / 2) },
        { label: '1R', v: stopDist },
        { label: '2R', v: stopDist * 2 },
        { label: '3R', v: stopDist * 3 },
      ]
    : [
        { label: '50', v: 50 },
        { label: '100', v: 100 },
        { label: '200', v: 200 },
        { label: '300', v: 300 },
      ];

  return (
    <div style={{ border: `1px solid ${k.border}`, borderRadius: 10, marginBottom: 16, overflow: 'hidden', background: k.bg }}>
      <div style={{ padding: '18px 20px', background: k.surface, borderBottom: `1px solid ${k.border}` }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 14, color: k.text, letterSpacing: -0.2 }}>Trade Impact Calculator</span>
          <span style={{ fontSize: 11, color: k.dim, lineHeight: 1.5 }}>
            Live greeks · {data.option_type} · {data.underlying} {data.spot_now ? data.spot_now.toFixed(0) : ''} ·
            {hasStop
              ? ` stop ${data.stop_loss.toFixed(0)} (${stopDist} pts = 1R)`
              : ` no stop set — showing a ${stopDist}-pt move`}
          </span>
          {updatedAt && (
            <span title="These greeks are a snapshot. The detail auto-refreshes every 15s; reopening always re-fetches."
              style={{ marginLeft: 'auto', fontSize: 10, color: k.dim, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: k.green, display: 'inline-block' }} />
              as of {new Date(updatedAt).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })} · refreshes 15s
            </span>
          )}
        </div>

        {/* Move + lots controls — one aligned row with generous spacing */}
        <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap', marginTop: 16 }}>
          <span style={{ fontSize: 10, color: k.dim, fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase' }}>
            IF {data.underlying} MOVES {dirWord.toUpperCase()}
          </span>

          {/* Segmented quick-move presets */}
          <div style={{ display: 'inline-flex', border: `1px solid ${k.border}`, borderRadius: 7, overflow: 'hidden', background: k.bg }}>
            {quickMoves.map((q, i) => {
              const active = move === q.v;
              return (
                <button key={q.label} onClick={() => setMove(q.v)}
                  style={{
                    fontSize: 11, padding: '6px 14px', cursor: 'pointer', fontWeight: 600,
                    border: 'none', borderLeft: i === 0 ? 'none' : `1px solid ${k.border}`,
                    background: active ? k.orange : 'transparent',
                    color: active ? '#fff' : k.dim, transition: 'background .15s, color .15s',
                  }}>{q.label}</button>
              );
            })}
          </div>

          {/* Exact move stepper */}
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: `1px solid ${k.border}`, borderRadius: 7, padding: '5px 10px', background: k.bg }}>
            <input type="number" value={move} step={5}
              onChange={(e) => setMove(Math.max(1, Number(e.target.value) || stopDist))}
              style={{ width: 52, fontSize: 12, fontWeight: 600, border: 'none', outline: 'none', textAlign: 'right', background: 'transparent', color: k.text }} />
            <span style={{ fontSize: 10, color: k.dim }}>pts</span>
          </div>

          {/* Lots */}
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 7, border: `1px solid ${k.border}`, borderRadius: 7, padding: '5px 10px', background: k.bg, marginLeft: 'auto' }}>
            <span style={{ fontSize: 10, color: k.dim, fontWeight: 700, letterSpacing: 0.4 }}>LOTS</span>
            <input type="number" value={lotsMult} min={1} step={1}
              onChange={(e) => setLotsMult(Math.max(1, Number(e.target.value) || 1))}
              style={{ width: 36, fontSize: 12, fontWeight: 600, border: 'none', outline: 'none', textAlign: 'right', background: 'transparent', color: k.text }} />
          </div>
        </div>
      </div>

      {/* Per-strike comparison */}
      <div style={{ overflowX: 'auto', padding: '4px 0' }}>
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
                  style={{ borderBottom: `1px solid ${k.border}`, background: isRec ? 'rgba(76,175,80,0.07)' : 'transparent' }}>
                  <td style={td('left')}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, fontWeight: 700, background: 'rgba(240,100,40,0.12)', color: k.orange }}>
                        {r.leg.moneyness}
                      </span>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>{r.leg.strike}</span>
                      {isRec && (
                        <span title="Best reward-to-risk for this move"
                          style={{ fontSize: 9, fontWeight: 700, color: '#fff', background: k.green, padding: '2px 7px', borderRadius: 4, letterSpacing: 0.3 }}>
                          ✝ BEST R:R
                        </span>
                      )}
                      {r.leg.option_symbol === bestDeltaSym && (
                        <span title="Highest delta — most responsive to the underlying (moves nearest 1:1 with spot)"
                          style={{ fontSize: 9, fontWeight: 700, color: '#fff', background: k.blue, padding: '2px 7px', borderRadius: 4, letterSpacing: 0.3 }}>
                          ▲ BEST Δ
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 10, color: k.dim, marginTop: 4 }}>
                      LTP {r.premium.toFixed(2)} · {r.lot}/lot · {r.leg.dte}d
                    </div>
                  </td>
                  <td style={td('right')}>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{inr(totalCost)}</div>
                    <div style={{ fontSize: 10, color: k.dim, marginTop: 3 }}>max loss</div>
                  </td>
                  <td style={td('right')}>
                    <div style={{ fontSize: 13 }}>{r.leg.delta.toFixed(2)}</div>
                    <div style={{ fontSize: 10, color: k.dim, marginTop: 3 }}>{r.probItm}%</div>
                  </td>
                  <td style={td('right')}>
                    <div style={{ color: k.green, fontWeight: 700, fontSize: 13 }}>+{inr(totalGain)}</div>
                    <div style={{ fontSize: 10, color: k.dim, marginTop: 3 }}>{r.effPct.toFixed(0)}% on cost</div>
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
                        style={{ fontSize: 11, padding: '6px 18px', background: k.blue, color: '#fff', border: 'none', borderRadius: 5, cursor: 'pointer', fontWeight: 700, letterSpacing: 0.3 }}>
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

      {/* Premium breakdown — recommended strike, intrinsic vs time value (graphical) */}
      {(() => {
        const rec = rows.find((r) => r.leg.option_symbol === recommended);
        if (!rec) return null;
        const intrinsic = data.option_type === 'CE'
          ? Math.max(0, spot - rec.leg.strike)
          : Math.max(0, rec.leg.strike - spot);
        const tv = Math.max(0, rec.premium - intrinsic);
        const intrinsicFrac = rec.premium > 0 ? intrinsic / rec.premium : 0;
        return (
          <div style={{ padding: '28px 20px 16px', borderTop: `1px solid ${k.border}` }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: k.dim, marginBottom: 12, letterSpacing: 0.4, textTransform: 'uppercase' }}>
              Premium breakdown (approximate) — {rec.leg.moneyness} {rec.leg.strike} · ₹{rec.premium.toFixed(2)} total
            </div>
            <div style={{ height: 3, borderRadius: 2, overflow: 'hidden', display: 'flex', marginBottom: 10 }}>
              <div title={`Intrinsic ₹${intrinsic.toFixed(0)} — real value, doesn't decay`}
                style={{ width: `${intrinsicFrac * 100}%`, background: k.green, minWidth: intrinsicFrac > 0 ? 3 : 0, transition: 'width .3s' }} />
              <div title={`Time value ₹${tv.toFixed(0)} — theta eats this daily`}
                style={{ flex: 1, background: k.orange, opacity: 0.85 }} />
            </div>
            <div style={{ display: 'flex', gap: 20, fontSize: 11, flexWrap: 'wrap' }}>
              <span style={{ color: k.green, fontWeight: 600 }}>■ Intrinsic ₹{intrinsic.toFixed(0)}</span>
              <span style={{ color: k.orange, fontWeight: 600 }}>■ Time value ₹{tv.toFixed(0)} <span style={{ color: k.dim, fontWeight: 400 }}>— theta decays this daily</span></span>
            </div>
          </div>
        );
      })()}

      {/* Same move, every strike compared — graphical bars */}
      {(() => {
        const maxGain = Math.max(...rows.map((r) => r.projGainPerLot * lotsMult), 1);
        return (
          <div style={{ padding: '16px 20px', borderTop: `1px solid ${k.border}`, background: k.surface }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: k.dim, marginBottom: 14, letterSpacing: 0.4, textTransform: 'uppercase' }}>
              Same {move}-pt move — every strike compared
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {rows.map((r) => {
                const gain = r.projGainPerLot * lotsMult;
                const isRec = r.leg.option_symbol === recommended;
                const w = (gain / maxGain) * 100;
                return (
                  <div key={r.leg.option_symbol}
                    style={{ display: 'grid', gridTemplateColumns: '110px 1fr 84px', gap: 12, alignItems: 'center' }}>
                    <span style={{ fontSize: 11, fontWeight: isRec ? 700 : 500, color: isRec ? k.green : k.text }}>
                      {r.leg.moneyness} {r.leg.strike}
                    </span>
                    <div style={{ height: 3, background: k.border, borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ width: `${w}%`, height: '100%', background: isRec ? k.green : k.blue, opacity: isRec ? 1 : 0.55, transition: 'width .3s' }} />
                    </div>
                    <span style={{ fontSize: 11, textAlign: 'right', color: k.green, fontWeight: 700 }}>+{inr(gain)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* Plain-English read of the recommended strike */}
      {(() => {
        const rec = rows.find((r) => r.leg.option_symbol === recommended);
        if (!rec) return null;
        return (
          <div style={{ padding: '16px 20px', fontSize: 11.5, color: k.dim, lineHeight: 1.7, borderTop: `1px solid ${k.border}`, background: k.surface }}>
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
  return { padding: '10px 14px', textAlign: align, fontWeight: 600, whiteSpace: 'nowrap', letterSpacing: 0.3, textTransform: 'uppercase' };
}
function td(align: 'left' | 'right'): React.CSSProperties {
  return { padding: '13px 14px', textAlign: align, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', verticalAlign: 'middle' };
}

export default SignalImpactCalculator;
