import React, { useMemo, useState } from 'react';
import { k, tint } from '../../styles/kiteUI';
import type { EngineDetailResponse, OptionDetail } from '../../types/kiteEngine';
import { stopDistance, computeLegRR, rrScore } from './impactMath';
import { InstrumentLabel } from './InstrumentLabel';
import { useKiteQuote } from '../../hooks/useKite';
import { useKiteSettings } from '../../store/useKiteSettings';

// Strike-label colour by live price direction — mirrors the Option-legs rows,
// the Triple SuperTrend table, and the watchlist (green up / red down; grey when
// direction colours are off or no live quote yet).
function dirColor(q: any, chgType: string, showDir: boolean): string {
  if (!q) return k.dim;
  const base = chgType === 'close' ? q.ohlc?.close : q.ohlc?.open;
  if (base) return showDir ? (q.last_price - base >= 0 ? k.green : k.red) : k.dim;
  if (q.net_change != null) return showDir ? (q.net_change >= 0 ? k.green : k.red) : k.dim;
  return k.dim;
}

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
  headless?: boolean; // when true, omit the outer card border + title (a wrapper supplies them)
}

export function SignalImpactCalculator({ data, onBuy, updatedAt, headless }: Props) {
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
  const [showRead, setShowRead] = useState<boolean>(false);

  // Live quotes for direction-coloured strike labels (same as the Option legs).
  const s = useKiteSettings();
  const legSyms = useMemo(
    () => data.options.map((o) => `${data.exchange}:${o.option_symbol}`),
    [data.options, data.exchange],
  );
  const { data: legQuotes } = useKiteQuote(legSyms, legSyms.length > 0);

  // Recompute when the stop distance changes (new signal selected).
  React.useEffect(() => { setMove(stopDist); }, [stopDist]);

  // Risk reference distance: the actual stop when one is set (risk-to-SL is then
  // fixed, as it should be — your stop doesn't move with your target). With NO
  // stop, risk against the SAME move magnitude (a symmetric adverse move) so the
  // Risk and R:R columns scale with the move instead of sitting on an arbitrary
  // constant default.
  const riskDist = hasStop ? stopDist : move;
  const rows = useMemo(
    () => data.options.map((leg) => computeRow(leg, move, riskDist)),
    [data.options, move, riskDist],
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

  // Favourable direction is set by the option you'd BUY here, not the signal's
  // bias: a long call gains as the underlying rises, a long put as it falls. The
  // projected-gain maths uses |delta| (always a favourable move), so the label
  // must match the option type or it reads as a contradiction (e.g. a PE "moving up").
  const dirWord = data.option_type === 'PE' ? 'down' : 'up';
  const quickMoves: { label: string; v: number }[] = hasStop
    ? [
        { label: '½R', v: Math.round(stopDist / 2) },
        { label: '1R', v: stopDist },
        { label: '2R', v: stopDist * 2 },
        { label: '3R', v: stopDist * 3 },
      ]
    : [
        { label: '10', v: 10 },
        { label: '25', v: 25 },
        { label: '50', v: 50 },
        { label: '75', v: 75 },
        { label: '100', v: 100 },
      ];

  return (
    <div style={headless ? { overflow: 'hidden', background: k.bg } : { border: `1px solid ${k.border}`, borderRadius: 10, overflow: 'hidden', background: k.bg }}>
      <div style={{ padding: '13px 20px', background: k.bg, borderBottom: `1px solid ${k.border}` }}>
        {!headless && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 14, color: k.text, letterSpacing: -0.2 }}>Trade Impact Calculator</span>
          </div>
        )}

        {/* Move + lots controls — one aligned row */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginTop: headless ? 0 : 11 }}>
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
        {/* tableLayout: fixed + explicit column widths keep the columns from
            jumping when the move value changes the cell/header text widths. */}
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: '26%' }} />
            <col style={{ width: '10%' }} />
            <col style={{ width: '11%' }} />
            <col style={{ width: '12%' }} />
            <col style={{ width: '11%' }} />
            <col style={{ width: '7%' }} />
            <col style={{ width: '10%' }} />
            <col style={{ width: '6%' }} />
            <col style={{ width: '7%' }} />
          </colgroup>
          <thead>
            <tr style={{ color: k.dim, fontSize: 10, borderBottom: `1px solid ${k.border}` }}>
              <th style={th('left')}>Strike</th>
              <th style={th('left')} title="Last traded premium and your cost per lot × lots">Cost</th>
              <th style={th('left')} title="Black-Scholes delta ≈ probability of finishing in-the-money">δ / ITM%</th>
              <th style={th('left')} title={`Projected profit if ${data.underlying} moves ${move} pts ${dirWord}`}>If +{move}pts</th>
              <th style={th('left')} title={hasStop ? "Premium lost per lot if the underlying runs to the signal's stop" : `Premium lost per lot if the underlying moves ${move} pts against you (no stop set)`}>{hasStop ? 'Risk→SL' : 'Risk↓'}</th>
              <th style={th('left')} title={hasStop ? 'Reward : risk for this move vs the stop' : `Reward : risk for a ${move}-pt move either way`}>R:R</th>
              <th style={th('left')} title="Premium lost to time decay per day if nothing moves">θ/day</th>
              <th style={th('left')} title="Points the underlying must move just to recover the premium">B/E</th>
              <th style={th('left')} />
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
                  style={{ borderBottom: `1px solid ${k.border}`, background: 'transparent', height: 41 }}>
                  <td style={{ ...td('left'), overflow: 'hidden', textOverflow: 'ellipsis' }} title={`LTP ${r.premium.toFixed(2)} · ${r.lot}/lot · ${r.leg.dte}d to expiry`}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                      <span style={{ fontSize: 10, padding: '2px 6px', background: tint(k.orange, 10), color: k.orange, borderRadius: 2, fontWeight: 700 }}>
                        {r.leg.moneyness}
                      </span>
                      <span style={{ fontSize: 12, color: dirColor(legQuotes?.[`${data.exchange}:${r.leg.option_symbol}`], s.chgType, s.showPriceDirection), fontWeight: 400 }}><InstrumentLabel symbol={`${data.exchange}:${r.leg.option_symbol}`} /></span>
                      {isRec && (
                        <span title="Best reward-to-risk for this move" style={{ fontSize: 13, fontWeight: 700, color: k.blue }}>✝</span>
                      )}
                      {r.leg.option_symbol === bestDeltaSym && (
                        <span title="Highest delta — most responsive to the underlying (moves nearest 1:1 with spot)" style={{ fontSize: 13, fontWeight: 700, color: k.blue }}>▲</span>
                      )}
                    </span>
                  </td>
                  <td style={td('left')} title="Cost deployed per move = max loss">
                    <span style={{ fontWeight: 500, fontSize: 11 }}>{inr(totalCost)}</span>
                  </td>
                  <td style={td('left')}>
                    <span style={{ fontSize: 11, fontWeight: 500 }}>{r.leg.delta.toFixed(2)}</span>
                    <span style={{ fontSize: 10, color: k.dim, marginLeft: 6 }}>{r.probItm}%</span>
                  </td>
                  <td style={td('left')}>
                    <span style={{ color: k.green, fontWeight: 500, fontSize: 11 }}>+{inr(totalGain)}</span>
                    <span style={{ fontSize: 10, color: k.dim, marginLeft: 6 }}>{r.effPct.toFixed(0)}%</span>
                  </td>
                  <td style={td('left')}>
                    <span style={{ color: k.red, fontWeight: 500, fontSize: 11 }}>−{inr(totalRisk)}</span>
                  </td>
                  <td style={td('left')}>
                    <span style={{
                      fontWeight: 500, fontSize: 11,
                      color: r.rr == null ? k.dim : r.rr >= 2 ? k.green : r.rr >= 1 ? k.amber : k.red,
                    }}>
                      {r.rr == null ? '—' : Math.abs(r.rr - 1) < 0.05 ? '1' : `${r.rr.toFixed(1)}:1`}
                    </span>
                  </td>
                  <td style={td('left')}>
                    <span style={{ color: k.red, fontSize: 11, fontWeight: 500 }}>{inr(totalTheta)}</span>
                  </td>
                  <td style={td('left')}>
                    <span style={{ color: k.dim, fontSize: 11, fontWeight: 500 }}>{isFinite(r.breakEvenPts) ? `${Math.round(r.breakEvenPts)}p` : '—'}</span>
                  </td>
                  <td style={td('left')}>
                    {onBuy && (
                      <button onClick={() => onBuy(r.leg)} title="Buy this strike"
                        style={{ fontSize: 11, padding: '5px 12px', background: k.blue, color: '#fff', border: 'none', borderRadius: 5, cursor: 'pointer', fontWeight: 700, letterSpacing: 0.3 }}>
                        B
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer: plain-English read toggle (left) + freshness stamp (right) */}
      {(() => {
        const rec = rows.find((r) => r.leg.option_symbol === recommended);
        if (!rec && !updatedAt) return null;
        return (
          <div style={{ borderTop: `1px solid ${k.border}`, background: k.bg }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 20px', minHeight: 40 }}>
              {rec ? (
                <button onClick={() => setShowRead((v) => !v)}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, textAlign: 'left', padding: '12px 0', background: 'transparent', border: 'none', cursor: 'pointer', color: k.text, fontSize: 11.5, fontWeight: 600, fontFamily: 'inherit' }}>
                  {showRead ? 'Hide read' : 'Read'}
                </button>
              ) : <span />}
              {updatedAt && (
                <span title="These greeks are a snapshot. The detail auto-refreshes every 15s; reopening always re-fetches."
                  style={{ marginLeft: 'auto', fontSize: 10, color: k.dim, display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap' }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: k.green, display: 'inline-block' }} />
                  as of {new Date(updatedAt).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })} · refreshes 15s
                </span>
              )}
            </div>
            {showRead && rec && (
              <div style={{ padding: '0 20px 16px', fontSize: 11.5, color: k.dim, lineHeight: 1.7 }}>
                The <strong style={{ color: k.text }}>{rec.leg.moneyness} {rec.leg.strike}</strong> gives the best
                reward-to-risk here — a {move}-pt move {dirWord} turns ~{inr(rec.costPerLot * lotsMult)} of premium into
                <strong style={{ color: k.green }}> +{inr(rec.projGainPerLot * lotsMult)}</strong>, against
                <strong style={{ color: k.red }}> −{inr(rec.riskToStopPerLot * lotsMult)}</strong> {hasStop ? 'if it hits the stop instead' : `if it moves ${move} pts against you instead`}.
                {rec.probItm < 40 && ' Low delta — it needs the move to come quickly before theta bites.'}
                {rec.probItm >= 60 && ' Higher delta — pricier, but behaves closer to the underlying with less time decay.'}
                <br />Figures are first-order greeks (with a gamma boost on big moves); exit IV and spread will shift the real fill.
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}

// ─── Premium breakdown — its own card (sibling to Option legs) ───────────────────
// One row per strike, splitting each premium into intrinsic (real, non-decaying)
// vs time value (theta eats this daily). The ✝ marks the best-R:R strike, picked
// with the same shared maths the calculator and the Option-legs list use.

export function PremiumBreakdown({ data, headless }: { data: EngineDetailResponse; headless?: boolean }) {
  const spot = data.spot_now || data.spot_at_trigger;

  // Live quotes for direction-coloured strike labels (same as the Option legs).
  const s = useKiteSettings();
  const legSyms = useMemo(
    () => data.options.map((o) => `${data.exchange}:${o.option_symbol}`),
    [data.options, data.exchange],
  );
  const { data: legQuotes } = useKiteQuote(legSyms, legSyms.length > 0);

  const recSym = useMemo(() => {
    const sd = stopDistance(spot, data.stop_loss);
    let best: string | null = null;
    let bestVal = -Infinity;
    for (const leg of data.options) {
      const premium = leg.last_price || 0;
      if (premium <= 0) continue;
      const { rr, effPct } = computeLegRR(leg.delta, leg.gamma, premium, sd);
      const v = rrScore(rr, effPct);
      if (v > bestVal) { bestVal = v; best = leg.option_symbol; }
    }
    return best;
  }, [data.options, spot, data.stop_loss]);

  // Best delta — highest |delta| among priced legs (matches the ▲ in the table/legs).
  const bestDeltaSym = useMemo(() => {
    let best: string | null = null;
    let bestVal = -Infinity;
    for (const leg of data.options) {
      if ((leg.last_price || 0) <= 0) continue;
      const ad = Math.abs(leg.delta);
      if (ad > bestVal) { bestVal = ad; best = leg.option_symbol; }
    }
    return best;
  }, [data.options]);

  const rows = data.options.filter((leg) => (leg.last_price || 0) > 0);
  if (!rows.length) return null;

  return (
    <div style={headless ? { overflow: 'hidden' } : { border: `1px solid ${k.border}`, borderRadius: 10, overflow: 'hidden' }}>
      {!headless && (
        <div style={{ fontSize: 11, fontWeight: 700, color: k.dim, letterSpacing: 0.5, textTransform: 'uppercase', padding: '14px 18px', background: k.bg, borderBottom: `1px solid ${k.border}`, display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <span>Premium breakdown</span>
          <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>intrinsic vs time value (approximate)</span>
        </div>
      )}
      <div style={{ padding: '4px 18px 14px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            {rows.map((leg) => {
              const premium = leg.last_price || 0;
              const intrinsic = data.option_type === 'CE'
                ? Math.max(0, spot - leg.strike)
                : Math.max(0, leg.strike - spot);
              const tv = Math.max(0, premium - intrinsic);
              const intrinsicFrac = premium > 0 ? intrinsic / premium : 0;
              const isRec = leg.option_symbol === recSym;
              const isBestDelta = leg.option_symbol === bestDeltaSym;
              return (
                <tr key={leg.option_symbol} style={{ borderBottom: `1px solid ${k.border}`, height: 41 }}>
                  {/* instrument */}
                  <td style={{ padding: '0 14px 0 0', whiteSpace: 'nowrap', verticalAlign: 'middle' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontSize: 10, padding: '2px 6px', background: tint(k.orange, 10), color: k.orange, borderRadius: 2, fontWeight: 700 }}>{leg.moneyness}</span>
                      <span style={{ fontSize: 12, color: dirColor(legQuotes?.[`${data.exchange}:${leg.option_symbol}`], s.chgType, s.showPriceDirection), fontWeight: 400 }}><InstrumentLabel symbol={`${data.exchange}:${leg.option_symbol}`} /></span>
                      {isRec && <span title="Best reward-to-risk" style={{ fontSize: 13, fontWeight: 700, color: k.blue }}>✝</span>}
                      {isBestDelta && <span title="Highest delta — most responsive to the underlying" style={{ fontSize: 13, fontWeight: 700, color: k.blue }}>▲</span>}
                    </span>
                  </td>
                  {/* premium total */}
                  <td style={{ padding: '0 16px 0 0', textAlign: 'right', whiteSpace: 'nowrap', fontSize: 12, color: k.text, fontVariantNumeric: 'tabular-nums', verticalAlign: 'middle' }}>₹{premium.toFixed(2)}</td>
                  {/* intrinsic vs time-value bar — absorbs remaining width */}
                  <td style={{ padding: '0 16px', width: '100%', verticalAlign: 'middle' }}>
                    <div style={{ height: 3, borderRadius: 2, overflow: 'hidden', display: 'flex' }}>
                      <div title={`Intrinsic ₹${intrinsic.toFixed(0)} — real value, doesn't decay`}
                        style={{ width: `${intrinsicFrac * 100}%`, background: k.green, minWidth: intrinsicFrac > 0 ? 3 : 0, transition: 'width .3s' }} />
                      <div title={`Time value ₹${tv.toFixed(0)} — theta eats this daily`}
                        style={{ flex: 1, background: k.orange, opacity: 0.85 }} />
                    </div>
                  </td>
                  {/* intrinsic */}
                  <td style={{ padding: '0 16px 0 0', textAlign: 'right', whiteSpace: 'nowrap', fontSize: 11, color: k.green, fontWeight: 600, fontVariantNumeric: 'tabular-nums', verticalAlign: 'middle' }}>■ Intrinsic ₹{intrinsic.toFixed(0)}</td>
                  {/* time value */}
                  <td style={{ padding: '0 0', textAlign: 'right', whiteSpace: 'nowrap', fontSize: 11, color: k.orange, fontWeight: 600, fontVariantNumeric: 'tabular-nums', verticalAlign: 'middle' }}>■ Time value ₹{tv.toFixed(0)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div style={{ fontSize: 10, color: k.dim, marginTop: 10 }}>Time value (orange) is what theta decays daily.</div>
      </div>
    </div>
  );
}

function th(align: 'left' | 'right'): React.CSSProperties {
  return { padding: '10px 14px', textAlign: align, fontWeight: 600, whiteSpace: 'nowrap', letterSpacing: 0.3, textTransform: 'uppercase' };
}
function td(align: 'left' | 'right'): React.CSSProperties {
  // No vertical padding — single-line rows get their height from the <tr> (41px),
  // content vertically centred via verticalAlign middle.
  return { padding: '0 14px', textAlign: align, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', verticalAlign: 'middle' };
}

export default SignalImpactCalculator;
