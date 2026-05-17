import React, { useState, useMemo } from 'react';
import { useBacktest } from '../hooks/useBacktest';
import type { BacktestStats, BacktestBarResult } from '../hooks/useBacktest';

// ── MTF backtest types + hook ─────────────────────────────────────────────────
interface MTFProfileResult {
  underlying: string;
  label: string;
  signal_tf: string;
  regime_tf: string;
  total_signal_bars: number;
  total_regime_bars: number;
  total_trades: number;
  win_rate: number | null;
  sharpe: number | null;
  calmar: number | null;
  sortino: number | null;
  profit_factor: number | null;
  max_drawdown: number | null;
  avg_rr: number | null;
  fwd1_label: string;
  fwd1_long_win_rate: number | null;
  fwd1_short_win_rate: number | null;
  fwd2_label: string;
  fwd2_long_win_rate: number | null;
  fwd2_short_win_rate: number | null;
  fwd3_label: string;
  fwd3_long_win_rate: number | null;
  fwd3_short_win_rate: number | null;
  equity_curve: number[];
  regime_breakdown: Record<string, unknown>;
}
interface MTFBacktestResult {
  underlying: string;
  profiles: Record<string, MTFProfileResult>;
  timestamp_ms: number;
  recommended: string | null;
}
function useMTFBacktest() {
  const [data, setData] = React.useState<MTFBacktestResult | null>(null);
  const [isPending, setIsPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const mutate = React.useCallback(async (body: {
    underlying: string;
    lookback_days: number;
    profiles: string[];
  }) => {
    setIsPending(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/backtest/mtf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t);
      }
      setData(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsPending(false);
    }
  }, []);
  return { data, isPending, error, mutate };
}

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  controls: { display: 'flex', gap: 12, alignItems: 'flex-end', marginBottom: 16, flexWrap: 'wrap' },
  field: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: { color: '#555', fontSize: 11 },
  input: {
    background: '#111', color: '#e0e0e0', border: '1px solid #2a2a2a',
    borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 13, width: 80,
  },
  runBtn: {
    background: '#1a1a2a', color: '#88aaff', border: '1px solid #88aaff',
    padding: '6px 16px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12,
  },
  section: { marginBottom: 16 },
  sectionTitle: { color: '#555', fontSize: 10, letterSpacing: 2, marginBottom: 8 },
  grid3: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 },
  grid4: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 12 },
  grid2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 },
  statCard: { background: '#111', border: '1px solid #1e1e1e', borderRadius: 4, padding: 10 },
  statLabel: { color: '#555', fontSize: 10, letterSpacing: 1, marginBottom: 4 },
  statVal: { fontSize: 18, fontWeight: 700 },
  qualityRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '6px 0', borderBottom: '1px solid #1a1a1a',
  },
  qualityLabel: { color: '#666', fontSize: 11 },
  qualityBar: { display: 'flex', alignItems: 'center', gap: 8 },
  barChart: { display: 'flex', gap: 2, height: 50, alignItems: 'flex-end', marginBottom: 8 },
  chartBar: { flex: 1, minWidth: 2, borderRadius: 1, cursor: 'pointer' },
  legend: { display: 'flex', gap: 12, fontSize: 10, color: '#555', marginBottom: 8, flexWrap: 'wrap' },
  dot: { width: 7, height: 7, borderRadius: '50%', display: 'inline-block', marginRight: 4 },
  error: { color: '#cc4444', fontSize: 12 },
  meta: { color: '#444', fontSize: 10, marginTop: 8 },
  noData: { color: '#444', fontSize: 12, padding: '20px 0', textAlign: 'center' },
};

const winRateStyle = (rate: number): React.CSSProperties => ({
  fontSize: 16, fontWeight: 700,
  color: rate >= 60 ? '#44cc88' : rate >= 50 ? '#f0c040' : '#cc4444',
});

const returnValStyle = (val: number): React.CSSProperties => ({
  fontSize: 14, fontWeight: 600,
  color: val >= 0 ? '#44cc88' : '#cc4444',
});

function StatCard({ label, value, color = '#e0e0e0', sub }: {
  label: string; value: number | string; color?: string; sub?: string;
}) {
  return (
    <div style={S.statCard}>
      <div style={S.statLabel}>{label}</div>
      <div style={{ ...S.statVal, color }}>{value}</div>
      {sub && <div style={{ color: '#444', fontSize: 10, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function WinRateBar({ label, rate, n }: { label: string; rate?: number | null; n?: number }) {
  if (rate == null) return (
    <div style={S.qualityRow}>
      <span style={S.qualityLabel}>{label}</span>
      <span style={{ color: '#333', fontSize: 11 }}>—</span>
    </div>
  );
  const w = Math.min(100, Math.max(0, rate));
  return (
    <div style={S.qualityRow}>
      <span style={S.qualityLabel}>{label}</span>
      <div style={S.qualityBar}>
        <div style={{ width: 80, height: 5, background: '#1e1e1e', borderRadius: 3 }}>
          <div style={{
            width: `${w}%`, height: '100%', borderRadius: 3,
            background: w >= 60 ? '#44cc88' : w >= 50 ? '#f0c040' : '#cc4444',
          }} />
        </div>
        <span style={winRateStyle(rate)}>{rate.toFixed(1)}%</span>
        {n != null && <span style={{ color: '#444', fontSize: 10 }}>n={n}</span>}
      </div>
    </div>
  );
}

function AvgReturn({ label, val }: { label: string; val?: number | null }) {
  if (val == null) return (
    <div style={S.qualityRow}>
      <span style={S.qualityLabel}>{label}</span>
      <span style={{ color: '#333', fontSize: 11 }}>—</span>
    </div>
  );
  return (
    <div style={S.qualityRow}>
      <span style={S.qualityLabel}>{label}</span>
      <span style={returnValStyle(val)}>{val >= 0 ? '+' : ''}{val.toFixed(3)}%</span>
    </div>
  );
}

function MiniChart({ bars }: { bars: BacktestBarResult[] }) {
  const [tooltip, setTooltip] = useState<string | null>(null);
  if (!bars.length) return null;

  const prices = bars.map(b => b.close_1h);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const range = maxP - minP || 1;

  const colorFor = (b: BacktestBarResult) => {
    if (b.green_arrow) return '#f0c040';
    if (b.red_arrow) return '#ff8844';
    if (b.macro_regime === 'bullish' && b.signal_trend === 1) return '#44cc88';
    if (b.macro_regime === 'bearish' && b.signal_trend === -1) return '#cc4444';
    if (b.macro_regime === 'bullish') return '#336644';
    if (b.macro_regime === 'bearish') return '#663333';
    return '#2a2a2a';
  };

  return (
    <div style={S.section}>
      <div style={S.legend}>
        <span><span style={{ ...S.dot, background: '#44cc88' }} />Bull aligned</span>
        <span><span style={{ ...S.dot, background: '#cc4444' }} />Bear aligned</span>
        <span><span style={{ ...S.dot, background: '#f0c040' }} />Green arrow</span>
        <span><span style={{ ...S.dot, background: '#ff8844' }} />Red arrow</span>
        <span><span style={{ ...S.dot, background: '#2a2a2a' }} />Mixed/filtered</span>
      </div>
      {tooltip && (
        <div style={{ color: '#888', fontSize: 10, marginBottom: 4 }}>{tooltip}</div>
      )}
      <div style={S.barChart}>
        {bars.map((b, i) => {
          const heightPx = Math.max(2, ((b.close_1h - minP) / range) * 44 + 4);
          const fwd = b.fwd_return_4h;
          return (
            <div
              key={i}
              style={{ ...S.chartBar, background: colorFor(b), height: `${heightPx}px` }}
              onMouseEnter={() => setTooltip(
                `${new Date(b.timestamp_ms).toLocaleDateString()} · ` +
                `${b.macro_regime} · trend ${b.signal_trend === 1 ? '▲' : b.signal_trend === -1 ? '▼' : '~'} · ` +
                `$${b.close_1h.toFixed(0)}` +
                (fwd != null ? ` · 4H: ${fwd >= 0 ? '+' : ''}${fwd.toFixed(2)}%` : '')
              )}
              onMouseLeave={() => setTooltip(null)}
            />
          );
        })}
      </div>
    </div>
  );
}

function QualityPanel({ s, bars }: { s: BacktestStats; bars: BacktestBarResult[] }) {
  const greenArrowN = bars.filter(b => b.green_arrow && b.fwd_return_4h != null).length;
  const redArrowN = bars.filter(b => b.red_arrow && b.fwd_return_4h != null).length;
  const confLongN = bars.filter(b => b.state === 'CONFIRMED_SETUP_ACTIVE' && b.direction === 'long' && b.fwd_return_4h != null).length;
  const confShortN = bars.filter(b => b.state === 'CONFIRMED_SETUP_ACTIVE' && b.direction === 'short' && b.fwd_return_4h != null).length;

  return (
    <div style={S.section}>
      <div style={S.sectionTitle}>SIGNAL QUALITY — 4H FORWARD RETURN</div>
      <div style={S.grid2}>
        <div style={{ background: '#0d1a0d', border: '1px solid #1a2a1a', borderRadius: 4, padding: 10 }}>
          <div style={{ color: '#44cc88', fontSize: 10, letterSpacing: 1, marginBottom: 6 }}>LONG SIGNALS</div>
          <WinRateBar label="Green arrow win rate (4H)" rate={s.arrow_long_win_rate_4h} n={greenArrowN} />
          <WinRateBar label="Green arrow win rate (12H)" rate={s.arrow_long_win_rate_12h} />
          <WinRateBar label="All-green signal accuracy (4H)" rate={s.signal_accuracy_long_4h} />
          <AvgReturn label="Confirmed setup avg return (4H)" val={s.setup_long_avg_return_4h} />
          <AvgReturn label="Confirmed setup avg return (12H)" val={s.setup_long_avg_return_12h} />
          {confLongN > 0 && <div style={{ color: '#444', fontSize: 10, marginTop: 4 }}>n={confLongN} confirmed long setups</div>}
        </div>
        <div style={{ background: '#1a0d0d', border: '1px solid #2a1a1a', borderRadius: 4, padding: 10 }}>
          <div style={{ color: '#cc4444', fontSize: 10, letterSpacing: 1, marginBottom: 6 }}>SHORT SIGNALS</div>
          <WinRateBar label="Red arrow win rate (4H)" rate={s.arrow_short_win_rate_4h} n={redArrowN} />
          <WinRateBar label="Red arrow win rate (12H)" rate={s.arrow_short_win_rate_12h} />
          <WinRateBar label="All-red signal accuracy (4H)" rate={s.signal_accuracy_short_4h} />
          <AvgReturn label="Confirmed setup avg return (4H)" val={s.setup_short_avg_return_4h != null ? s.setup_short_avg_return_4h : null} />
          <AvgReturn label="Confirmed setup avg return (12H)" val={s.setup_short_avg_return_12h != null ? s.setup_short_avg_return_12h : null} />
          {confShortN > 0 && <div style={{ color: '#444', fontSize: 10, marginTop: 4 }}>n={confShortN} confirmed short setups</div>}
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// SIMULATION ENGINE v2 — multi-step exit, fees, slippage, Kelly, Sharpe/Sortino
// ══════════════════════════════════════════════════════════════════════════════

type SignalFilter  = 'arrows' | 'confirmed' | 'both';
type ExitReason    = 'TP' | 'SL' | 'TRAIL SL' | 'TIMEOUT' | 'CIRCUIT BREAKER';
type SizingMode    = 'pct' | 'fixed' | 'kelly';
type FeeMode       = 'taker' | 'maker' | 'zero';

// Delta Exchange fee rates
const FEE: Record<FeeMode, number> = { taker: 0.0005, maker: 0.0002, zero: 0 };

interface SimParams {
  initialCapital:   number;
  sizingMode:       SizingMode;
  positionPct:      number;     // % of current capital (pct mode)
  positionFixed:    number;     // fixed USD notional (fixed mode)
  stopPct:          number;     // SL distance % from entry
  rrRatio:          number;     // reward:risk (TP = SL × rr)
  leverage:         number;
  trailEnabled:     boolean;
  trailActivation:  number;     // profit % before trail kicks in
  feeMode:          FeeMode;
  slippagePct:      number;
  signalFilter:     SignalFilter;
  fwdHorizon:       '4h' | '12h' | '24h';
  cooldownBars:     number;     // min bars between entries
  circuitBreaker:   number;     // halt if drawdown from peak exceeds this %
}

interface SimTrade {
  n:             number;
  date:          string;
  ts:            number;
  direction:     'long' | 'short';
  entry:         number;
  initialSl:     number;
  trailSl:       number;
  tp:            number;
  exit:          number;
  exitReason:    ExitReason;
  grossPnlPct:   number;        // raw price move %
  feesPct:       number;        // round-trip fee %
  slippagePct:   number;
  netPnlPct:     number;        // after fees + slippage
  positionUsd:   number;        // notional traded
  pnlUsd:        number;        // net USD P&L
  capitalBefore: number;
  capitalAfter:  number;
  isWin:         boolean;
  drawdownPct:   number;        // drawdown from peak at exit
}

interface SimSummary {
  trades:           number;
  wins:             number;
  losses:           number;
  winRate:          number;
  totalPnlUsd:      number;
  totalPnlPct:      number;
  totalFeesUsd:     number;
  totalSlippageUsd: number;
  maxDrawdownPct:   number;
  maxDrawdownUsd:   number;
  profitFactor:     number;
  avgWinUsd:        number;
  avgLossUsd:       number;
  expectancyUsd:    number;
  finalCapital:     number;
  peakCapital:      number;
  sharpe:           number;
  sortino:          number;
  calmar:           number;
  maxConsecWins:    number;
  maxConsecLosses:  number;
  equityCurve:      number[];
  monthlyPnl:       Record<string, { pnl: number; trades: number; wins: number }>;
  pnlDistribution:  number[];   // per-trade net P&L % for histogram
  halted:           boolean;
}

// ── Engine ────────────────────────────────────────────────────────────────────

function computeKellyPct(winRate: number, avgWinPct: number, avgLossPct: number): number {
  if (avgLossPct === 0) return 0.05;
  const b = avgWinPct / avgLossPct;
  const p = winRate / 100;
  const kelly = (b * p - (1 - p)) / b;
  return Math.max(0.01, Math.min(0.25, kelly));  // clamp 1–25%
}

function simulateTrades(
  bars: BacktestBarResult[],
  p: SimParams,
): { trades: SimTrade[]; summary: SimSummary } {
  const { initialCapital, sizingMode, positionPct, positionFixed,
          stopPct, rrRatio, leverage, trailEnabled, trailActivation,
          feeMode, slippagePct, signalFilter, fwdHorizon,
          cooldownBars, circuitBreaker } = p;

  const stopDec      = stopPct / 100;
  const tpDec        = stopDec * rrRatio;
  const feeRate      = FEE[feeMode];
  const slipDec      = slippagePct / 100;
  const roundTrip    = feeRate * 2 + slipDec * 2;  // fees + slippage both sides

  let capital        = initialCapital;
  let peakCap        = initialCapital;
  let maxDD          = 0;
  let maxDDUsd       = 0;
  let grossWins      = 0;
  let grossLoss      = 0;
  let totalFees      = 0;
  let totalSlip      = 0;
  let consecWins     = 0;
  let consecLoss     = 0;
  let maxCW          = 0;
  let maxCL          = 0;
  let lastSignalBar  = -cooldownBars - 1;
  let halted         = false;
  const trades: SimTrade[] = [];
  const returns: number[] = [];

  // Running Kelly estimate (starts at positionPct, converges after ~20 trades)
  let kellyEst = positionPct / 100;

  for (let i = 0; i < bars.length; i++) {
    if (halted) break;
    const bar = bars[i];
    if (capital <= 0) break;

    // Circuit breaker
    const ddFromPeak = (peakCap - capital) / peakCap * 100;
    if (circuitBreaker > 0 && ddFromPeak >= circuitBreaker) { halted = true; break; }

    // Cooldown gate
    if (i - lastSignalBar < cooldownBars) continue;

    // Signal detection
    const wantLong  = signalFilter === 'arrows'    ? bar.green_arrow
                    : signalFilter === 'confirmed'  ? (bar.state === 'CONFIRMED_SETUP_ACTIVE' && bar.direction === 'long')
                    : (bar.green_arrow || (bar.state === 'CONFIRMED_SETUP_ACTIVE' && bar.direction === 'long'));
    const wantShort = signalFilter === 'arrows'    ? bar.red_arrow
                    : signalFilter === 'confirmed'  ? (bar.state === 'CONFIRMED_SETUP_ACTIVE' && bar.direction === 'short')
                    : (bar.red_arrow || (bar.state === 'CONFIRMED_SETUP_ACTIVE' && bar.direction === 'short'));

    if (!wantLong && !wantShort) continue;

    // Forward return(s)
    const fwd4h  = bar.fwd_return_4h  ?? null;
    const fwd12h = bar.fwd_return_12h ?? null;
    const fwd24h = bar.fwd_return_24h ?? null;
    const fwdPrimary = fwdHorizon === '4h' ? fwd4h : fwdHorizon === '12h' ? fwd12h : fwd24h;
    if (fwdPrimary == null) continue;

    lastSignalBar = i;
    const direction: 'long' | 'short' = wantLong ? 'long' : 'short';
    const entry = bar.close_1h;
    if (entry <= 0) continue;

    // SL / TP
    const initialSl = direction === 'long' ? entry * (1 - stopDec) : entry * (1 + stopDec);
    const tp        = direction === 'long' ? entry * (1 + tpDec)   : entry * (1 - tpDec);

    // ── Multi-step exit simulation ──────────────────────────────────────────
    // We model: price path goes through 4h, 12h, 24h checkpoints.
    // SL/TP is checked at each checkpoint. This is more realistic than checking
    // only the final return.
    let trailSl       = initialSl;
    const sign         = direction === 'long' ? 1 : -1;

    const checkpoints: { ret: number | null; label: '4h' | '12h' | '24h' }[] = [
      { ret: fwd4h,  label: '4h'  },
      { ret: fwd12h, label: '12h' },
      { ret: fwd24h, label: '24h' },
    ];

    // Stop at the first checkpoint relevant to the chosen horizon
    const horizonIdx = fwdHorizon === '4h' ? 0 : fwdHorizon === '12h' ? 1 : 2;
    const activeCheckpoints = checkpoints.slice(0, horizonIdx + 1);

    let finalExitPct: number = fwdPrimary * sign / 100;
    let exitReason:   ExitReason = 'TIMEOUT';
    let settled = false;
    for (const cp of activeCheckpoints) {
      if (cp.ret == null) continue;
      const cpMoveSign = cp.ret * sign;  // positive = favourable for this direction

      // Current checkpoint price
      const cpExitPct = cpMoveSign / 100;

      // Trail SL update — activate only after trailActivation % profit
      if (trailEnabled && cpMoveSign >= trailActivation) {
        const newTrail = direction === 'long'
          ? entry * (1 + cpExitPct) * (1 - stopDec)
          : entry * (1 - cpExitPct) * (1 + stopDec);
        if (direction === 'long')  trailSl = Math.max(trailSl, newTrail);
        else                       trailSl = Math.min(trailSl, newTrail);
      }

      // Check TP
      if (cpMoveSign / 100 >= tpDec) {
        finalExitPct = tpDec;
        exitReason   = 'TP';
        settled      = true;
        break;
      }
      // Check trail SL (only if moved past initial)
      const trailMoved = direction === 'long' ? trailSl > initialSl : trailSl < initialSl;
      if (trailMoved) {
        const trailMove = direction === 'long'
          ? (trailSl - entry) / entry
          : (entry - trailSl) / entry;
        if (cpMoveSign / 100 < trailMove) {
          finalExitPct = trailMove;
          exitReason   = 'TRAIL SL';
          settled      = true;
          break;
        }
      }
      // Check initial SL
      if (-cpMoveSign / 100 >= stopDec) {
        finalExitPct = -stopDec;
        exitReason   = 'SL';
        settled      = true;
        break;
      }
    }
    if (!settled) {
      finalExitPct = fwdPrimary * sign / 100;
      exitReason   = 'TIMEOUT';
    }

    // ── P&L calculation ─────────────────────────────────────────────────────
    const positionUsd = sizingMode === 'fixed' ? positionFixed
                      : sizingMode === 'kelly'  ? capital * kellyEst * leverage
                      : capital * (positionPct / 100) * leverage;

    const grossPnlPct = finalExitPct;
    const feePctRT    = feeRate * 2;
    const slipPctRT   = slipDec * 2;
    const netPnlPct   = grossPnlPct - feePctRT - slipPctRT;
    const pnlUsd      = positionUsd * netPnlPct;
    const feesUsd     = positionUsd * feePctRT;
    const slipUsd     = positionUsd * slipPctRT;

    const capitalBefore = capital;
    capital += pnlUsd;
    capital  = Math.max(0, capital);

    totalFees += feesUsd;
    totalSlip += slipUsd;

    peakCap = Math.max(peakCap, capital);
    const dd = (peakCap - capital) / peakCap * 100;
    if (dd > maxDD)    { maxDD = dd; maxDDUsd = peakCap - capital; }

    const isWin = pnlUsd >= 0;
    if (isWin)  { grossWins += pnlUsd; consecWins++; consecLoss = 0; maxCW = Math.max(maxCW, consecWins); }
    else        { grossLoss += Math.abs(pnlUsd); consecLoss++; consecWins = 0; maxCL = Math.max(maxCL, consecLoss); }

    returns.push(netPnlPct * 100);

    // Monthly bucket
    const monthKey = new Date(bar.timestamp_ms).toISOString().slice(0, 7);

    const exitPrice = direction === 'long'
      ? entry * (1 + finalExitPct)
      : entry * (1 - finalExitPct);

    const trade: SimTrade = {
      n: trades.length + 1,
      date: new Date(bar.timestamp_ms).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' }),
      ts:   bar.timestamp_ms,
      direction,
      entry:         Math.round(entry),
      initialSl:     Math.round(initialSl),
      trailSl:       Math.round(trailSl),
      tp:            Math.round(tp),
      exit:          Math.round(exitPrice),
      exitReason,
      grossPnlPct:   finalExitPct * 100,
      feesPct:       feePctRT * 100,
      slippagePct:   slipPctRT * 100,
      netPnlPct:     netPnlPct * 100,
      positionUsd,
      pnlUsd,
      capitalBefore,
      capitalAfter:  capital,
      isWin,
      drawdownPct:   dd,
    };
    trades.push(trade);

    // Update Kelly estimate using trailing window
    if (trades.length >= 10) {
      const recent = trades.slice(-20);
      const rWins    = recent.filter(t => t.isWin).length;
      const rLosses  = recent.length - rWins;
      const rAvgWin  = rWins  > 0 ? recent.filter(t => t.isWin).reduce((s, t) => s + t.netPnlPct, 0) / rWins  : 0;
      const rAvgLoss = rLosses > 0 ? Math.abs(recent.filter(t => !t.isWin).reduce((s, t) => s + t.netPnlPct, 0) / rLosses) : 0;
      kellyEst = computeKellyPct(rWins / recent.length * 100, rAvgWin, rAvgLoss);
    }
  }

  // ── Statistics ─────────────────────────────────────────────────────────────
  const wins   = trades.filter(t => t.isWin).length;
  const losses = trades.length - wins;
  const avgWin = wins   > 0 ? grossWins / wins   : 0;
  const avgLoss = losses > 0 ? grossLoss / losses : 0;

  // Sharpe (annualised, assuming 252 trading days, 4 bars/day sampled)
  const meanRet = returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
  const stdRet  = returns.length > 1
    ? Math.sqrt(returns.map(r => (r - meanRet) ** 2).reduce((a, b) => a + b, 0) / (returns.length - 1))
    : 0;
  const sharpe = stdRet > 0 ? (meanRet / stdRet) * Math.sqrt(252) : 0;

  // Sortino (downside std)
  const downReturns = returns.filter(r => r < 0);
  const downStd = downReturns.length > 1
    ? Math.sqrt(downReturns.map(r => r ** 2).reduce((a, b) => a + b, 0) / downReturns.length)
    : 0;
  const sortino = downStd > 0 ? (meanRet / downStd) * Math.sqrt(252) : 0;

  // Calmar = annualised return / max drawdown
  const annReturn = ((capital / initialCapital - 1) * 100) * (365 / Math.max(1, (trades[trades.length - 1]?.ts ?? Date.now()) / 1000 / 86400 - (trades[0]?.ts ?? Date.now()) / 1000 / 86400));
  const calmar = maxDD > 0 ? annReturn / maxDD : 0;

  // Monthly P&L
  const monthlyPnl: Record<string, { pnl: number; trades: number; wins: number }> = {};
  for (const t of trades) {
    const k = new Date(t.ts).toISOString().slice(0, 7);
    if (!monthlyPnl[k]) monthlyPnl[k] = { pnl: 0, trades: 0, wins: 0 };
    monthlyPnl[k].pnl    += t.pnlUsd;
    monthlyPnl[k].trades += 1;
    if (t.isWin) monthlyPnl[k].wins++;
  }

  return {
    trades,
    summary: {
      trades:           trades.length,
      wins, losses,
      winRate:          trades.length > 0 ? (wins / trades.length) * 100 : 0,
      totalPnlUsd:      capital - initialCapital,
      totalPnlPct:      ((capital - initialCapital) / initialCapital) * 100,
      totalFeesUsd:     totalFees,
      totalSlippageUsd: totalSlip,
      maxDrawdownPct:   maxDD,
      maxDrawdownUsd:   maxDDUsd,
      profitFactor:     grossLoss > 0 ? grossWins / grossLoss : grossWins > 0 ? 999 : 0,
      avgWinUsd:        avgWin,
      avgLossUsd:       avgLoss,
      expectancyUsd:    trades.length > 0 ? (grossWins - grossLoss) / trades.length : 0,
      finalCapital:     capital,
      peakCapital:      peakCap,
      sharpe,  sortino, calmar,
      maxConsecWins:    maxCW,
      maxConsecLosses:  maxCL,
      equityCurve:      trades.map(t => t.capitalAfter),
      monthlyPnl,
      pnlDistribution:  returns,
      halted,
    },
  };
}

// ── Equity curve + drawdown SVG ───────────────────────────────────────────────

function EquityCurve({ curve, initial }: { curve: number[]; initial: number }) {
  if (curve.length < 2) return null;
  const W = 600, H = 100, PB = 24;  // PB = bottom panel for drawdown
  const all   = [initial, ...curve];
  const minV  = Math.min(...all);
  const maxV  = Math.max(...all);
  const range = maxV - minV || 1;
  const toY   = (v: number) => H - PB - ((v - minV) / range) * (H - PB - 4) - 2;
  const pts   = all.map((v, i) => `${((i / (all.length - 1)) * W).toFixed(1)},${toY(v).toFixed(1)}`).join(' ');
  const color = curve[curve.length - 1] >= initial ? '#10B981' : '#EF4444';

  // Drawdown series
  let peak = initial;
  const ddPts = all.map((v, i) => {
    peak = Math.max(peak, v);
    const dd = peak > 0 ? (peak - v) / peak : 0;
    const x  = (i / (all.length - 1)) * W;
    const y  = H - PB / 2 * dd;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="eq-g" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
        <linearGradient id="dd-g" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#EF4444" stopOpacity="0" />
          <stop offset="100%" stopColor="#EF4444" stopOpacity="0.3" />
        </linearGradient>
      </defs>
      {/* Zero line */}
      <line x1={0} y1={toY(initial)} x2={W} y2={toY(initial)}
        stroke="rgba(255,255,255,0.07)" strokeWidth="1" strokeDasharray="5,4" />
      {/* Equity fill */}
      <polygon points={`0,${H - PB} ${pts} ${W},${H - PB}`} fill="url(#eq-g)" />
      {/* Equity line */}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      {/* Drawdown band */}
      <polyline points={ddPts.join(' ')} fill="none" stroke="#EF444460" strokeWidth="1" />
      {/* Labels */}
      <text x={4} y={12} fill="rgba(255,255,255,0.25)" fontSize="7" letterSpacing="1">EQUITY</text>
      <text x={4} y={H - 4} fill="rgba(255,71,71,0.4)" fontSize="7" letterSpacing="1">DRAWDOWN</text>
    </svg>
  );
}

// ── P&L distribution histogram ────────────────────────────────────────────────

function PnLHistogram({ dist }: { dist: number[] }) {
  if (dist.length < 3) return null;
  const buckets = 16;
  const min = Math.min(...dist), max = Math.max(...dist);
  const range = max - min || 1;
  const bucketW = range / buckets;
  const counts  = Array(buckets).fill(0);
  for (const v of dist) {
    const idx = Math.min(buckets - 1, Math.floor((v - min) / bucketW));
    counts[idx]++;
  }
  const maxCount = Math.max(...counts, 1);
  const W = 400, H = 48;

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H + 14}`} style={{ display: 'block' }}>
      {counts.map((c, i) => {
        const bMin = min + i * bucketW;
        const bMax = bMin + bucketW;
        const isLoss = bMax <= 0;
        const isMixed = bMin < 0 && bMax > 0;
        const col = isLoss ? '#EF4444' : isMixed ? '#F59E0B' : '#10B981';
        const bH  = Math.max(2, (c / maxCount) * H);
        const x   = (i / buckets) * W;
        const bW  = (W / buckets) - 1;
        return (
          <g key={i}>
            <rect x={x} y={H - bH} width={bW} height={bH} fill={col} opacity="0.75" rx="1" />
          </g>
        );
      })}
      {/* Zero line */}
      <line
        x1={((-min) / range) * W} y1={0}
        x2={((-min) / range) * W} y2={H}
        stroke="rgba(255,255,255,0.2)" strokeWidth="1" strokeDasharray="3,3"
      />
      <text x={4} y={H + 12} fill="rgba(255,255,255,0.2)" fontSize="7">
        {min.toFixed(1)}%
      </text>
      <text x={W - 4} y={H + 12} fill="rgba(255,255,255,0.2)" fontSize="7" textAnchor="end">
        +{max.toFixed(1)}%
      </text>
    </svg>
  );
}

// ── Simulation panel UI ───────────────────────────────────────────────────────

interface SimPanelProps { bars: BacktestBarResult[]; underlying: string }

const T: React.CSSProperties = { background: 'var(--t-bg2, #141414)', border: '1px solid var(--t-border, #222)' };

function SimulationPanel({ bars, underlying }: SimPanelProps) {
  // ── params ──────────────────────────────────────────────────────────────────
  const [capital,        setCapital]        = useState(100_000);
  const [sizingMode,     setSizingMode]     = useState<SizingMode>('pct');
  const [positionPct,    setPositionPct]    = useState(5);
  const [positionFixed,  setPositionFixed]  = useState(5_000);
  const [stopPct,        setStopPct]        = useState(2);
  const [rrRatio,        setRrRatio]        = useState(2);
  const [leverage,       setLeverage]       = useState(5);
  const [trailEnabled,   setTrailEnabled]   = useState(true);
  const [trailActivation,setTrailActivation]= useState(1.0);
  const [feeMode,        setFeeMode]        = useState<FeeMode>('taker');
  const [slippagePct,    setSlippagePct]    = useState(0.05);
  const [signalFilter,   setSignalFilter]   = useState<SignalFilter>('arrows');
  const [fwdHorizon,     setFwdHorizon]     = useState<'4h' | '12h' | '24h'>('12h');
  const [cooldownBars,   setCooldownBars]   = useState(2);
  const [circuitBreaker, setCircuitBreaker] = useState(20);
  const [showLedger,     setShowLedger]     = useState(false);
  const [showMonthly,    setShowMonthly]    = useState(false);
  const [showParams,     setShowParams]     = useState(true);

  const { trades, summary } = useMemo(() =>
    simulateTrades(bars, {
      initialCapital: capital, sizingMode, positionPct, positionFixed,
      stopPct, rrRatio, leverage, trailEnabled, trailActivation,
      feeMode, slippagePct, signalFilter, fwdHorizon,
      cooldownBars, circuitBreaker,
    }),
    [capital, sizingMode, positionPct, positionFixed, stopPct, rrRatio,
     leverage, trailEnabled, trailActivation, feeMode, slippagePct,
     signalFilter, fwdHorizon, cooldownBars, circuitBreaker, bars],
  );

  // ── helpers ─────────────────────────────────────────────────────────────────
  const fmtMoney = (v: number, signed = true) => {
    const s   = signed ? (v >= 0 ? '+' : '') : '';
    const abs = Math.abs(v);
    if (abs >= 1_000_000) return `${s}$${(abs / 1e6).toFixed(2)}M`;
    if (abs >= 1_000)     return `${s}$${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
    return `${s}$${abs.toFixed(2)}`;
  };
  const fmtPct = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
  const metricColor = (v: number, goodHigh = true) =>
    (goodHigh ? v >= 0 : v <= 0) ? '#10B981' : '#EF4444';
  const rateColor = (v: number) => v >= 60 ? '#10B981' : v >= 50 ? '#F59E0B' : '#EF4444';

  const inp: React.CSSProperties = {
    ...T, borderRadius: 4, padding: '4px 8px',
    color: 'var(--t-bright, #e0e0e0)', fontFamily: 'inherit',
    fontSize: 11, width: 80, outline: 'none',
  };
  const toggle = (active: boolean, color = '#10B981'): React.CSSProperties => ({
    padding: '3px 9px', borderRadius: 4, fontSize: 9, fontWeight: 700,
    cursor: 'pointer', fontFamily: 'inherit',
    border: active ? `1px solid ${color}55` : '1px solid var(--t-border, #2a2a2a)',
    background: active ? `${color}18` : 'transparent',
    color: active ? color : 'var(--t-dim, #555)',
    transition: 'all 0.1s',
  });
  const sectionHdr = (label: string, extra?: React.ReactNode): React.ReactNode => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      marginBottom: 10, paddingBottom: 6, borderBottom: '1px solid var(--t-border, #1e1e1e)' }}>
      <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.14em',
        color: 'var(--t-dim, #555)' }}>{label}</span>
      {extra}
    </div>
  );
  const exitColor = (r: ExitReason) => ({
    TP: '#10B981', SL: '#EF4444', 'TRAIL SL': '#F59E0B',
    TIMEOUT: '#71717A', 'CIRCUIT BREAKER': '#EF4444'
  }[r] ?? '#888');

  // ── render ──────────────────────────────────────────────────────────────────
  return (
    <div style={{ marginTop: 20, borderTop: '1px solid var(--t-border, #1e1e1e)', paddingTop: 16 }}>
      {sectionHdr(`CAPITAL SIMULATION — ${underlying}`,
        <button onClick={() => setShowParams(s => !s)} style={{ ...toggle(false), fontSize: 8 }}>
          {showParams ? '▲ HIDE PARAMS' : '▼ PARAMS'}
        </button>
      )}

      {/* ── Parameters ── */}
      {showParams && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 18 }}>

          {/* Capital */}
          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>STARTING CAPITAL ($)</label>
            <input style={{ ...inp, width: 110 }} type="number" min={1000} step={5000}
              value={capital} onChange={e => setCapital(+e.target.value || 100000)} />
          </div>

          {/* Sizing mode */}
          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>POSITION SIZING</label>
            <div style={{ display: 'flex', gap: 3 }}>
              {(['pct', 'fixed', 'kelly'] as SizingMode[]).map(m => (
                <button key={m} style={toggle(sizingMode === m)} onClick={() => setSizingMode(m)}>
                  {m === 'pct' ? '% CAP' : m === 'fixed' ? 'FIXED $' : 'KELLY'}
                </button>
              ))}
            </div>
            {sizingMode === 'pct' && (
              <input style={{ ...inp, marginTop: 4 }} type="number" min={0.5} max={100} step={0.5}
                value={positionPct} onChange={e => setPositionPct(+e.target.value || 5)}
                placeholder="% of capital" />
            )}
            {sizingMode === 'fixed' && (
              <input style={{ ...inp, marginTop: 4, width: 110 }} type="number" min={100} step={500}
                value={positionFixed} onChange={e => setPositionFixed(+e.target.value || 5000)}
                placeholder="USD notional" />
            )}
            {sizingMode === 'kelly' && (
              <span style={{ fontSize: 8, color: 'var(--t-dim, #555)', marginTop: 4 }}>
                Adaptive Kelly — computed from trailing 20-trade window
              </span>
            )}
          </div>

          {/* SL / TP */}
          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>STOP LOSS %</label>
            <input style={inp} type="number" min={0.1} max={20} step={0.1}
              value={stopPct} onChange={e => setStopPct(+e.target.value || 2)} />
          </div>

          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>R:R RATIO (TP = SL × R:R)</label>
            <input style={inp} type="number" min={0.5} max={10} step={0.5}
              value={rrRatio} onChange={e => setRrRatio(+e.target.value || 2)} />
            <span style={{ fontSize: 8, color: 'var(--t-dim, #555)' }}>TP = {(stopPct * rrRatio).toFixed(1)}% from entry</span>
          </div>

          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>LEVERAGE</label>
            <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
              {[1, 3, 5, 10, 20, 50].map(l => (
                <button key={l} style={toggle(leverage === l)} onClick={() => setLeverage(l)}>{l}×</button>
              ))}
            </div>
          </div>

          {/* Trail SL */}
          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>TRAILING STOP</label>
            <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
              <button style={toggle(trailEnabled)} onClick={() => setTrailEnabled(s => !s)}>
                {trailEnabled ? 'ON' : 'OFF'}
              </button>
              {trailEnabled && (
                <span style={{ fontSize: 8, color: 'var(--t-dim, #555)' }}>activates after</span>
              )}
              {trailEnabled && (
                <input style={{ ...inp, width: 50 }} type="number" min={0.1} max={10} step={0.1}
                  value={trailActivation} onChange={e => setTrailActivation(+e.target.value || 1)} />
              )}
              {trailEnabled && <span style={{ fontSize: 8, color: 'var(--t-dim, #555)' }}>% profit</span>}
            </div>
          </div>

          {/* Fees */}
          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>EXCHANGE FEE</label>
            <div style={{ display: 'flex', gap: 3 }}>
              {(['taker', 'maker', 'zero'] as FeeMode[]).map(f => (
                <button key={f} style={toggle(feeMode === f)} onClick={() => setFeeMode(f)}>
                  {f === 'taker' ? 'TAKER 0.05%' : f === 'maker' ? 'MAKER 0.02%' : 'ZERO'}
                </button>
              ))}
            </div>
            <div style={S.field}>
              <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em', marginTop: 6 }}>SLIPPAGE %</label>
              <input style={{ ...inp, width: 70 }} type="number" min={0} max={1} step={0.01}
                value={slippagePct} onChange={e => setSlippagePct(+e.target.value || 0)} />
            </div>
          </div>

          {/* Signal + horizon */}
          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>SIGNAL TYPE</label>
            <div style={{ display: 'flex', gap: 3 }}>
              {(['arrows', 'confirmed', 'both'] as SignalFilter[]).map(f => (
                <button key={f} style={toggle(signalFilter === f)} onClick={() => setSignalFilter(f)}>
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>EXIT HORIZON</label>
            <div style={{ display: 'flex', gap: 3 }}>
              {(['4h', '12h', '24h'] as const).map(h => (
                <button key={h} style={toggle(fwdHorizon === h)} onClick={() => setFwdHorizon(h)}>
                  {h.toUpperCase()}
                </button>
              ))}
            </div>
            <span style={{ fontSize: 8, color: 'var(--t-dim, #555)', marginTop: 3 }}>
              Multi-step: checks 4H→12H→24H for SL/TP at each step
            </span>
          </div>

          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>COOLDOWN (bars)</label>
            <input style={{ ...inp, width: 60 }} type="number" min={0} max={20}
              value={cooldownBars} onChange={e => setCooldownBars(+e.target.value || 0)} />
          </div>

          <div style={S.field}>
            <label style={{ ...S.label, color: 'var(--t-dim, #555)', fontSize: 9, letterSpacing: '0.1em' }}>CIRCUIT BREAKER %</label>
            <input style={{ ...inp, width: 60 }} type="number" min={0} max={100}
              value={circuitBreaker} onChange={e => setCircuitBreaker(+e.target.value || 0)} />
            <span style={{ fontSize: 8, color: 'var(--t-dim, #555)' }}>0 = disabled</span>
          </div>
        </div>
      )}

      {summary.trades === 0 ? (
        <div style={{ color: 'var(--t-dim, #555)', fontSize: 12, padding: '16px 0', textAlign: 'center' }}>
          No signals in the selected filter / backtest window.
        </div>
      ) : (
        <>
          {summary.halted && (
            <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 6,
              background: '#EF444415', border: '1px solid #EF444440', fontSize: 10, color: '#EF4444' }}>
              ⚠ Circuit breaker triggered — simulation halted at {summary.trades} trades
              (drawdown exceeded {circuitBreaker}% from peak)
            </div>
          )}

          {/* ── Summary grid (4 × 3) ── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 14 }}>
            {[
              { lbl: 'FINAL CAPITAL',   val: fmtMoney(summary.finalCapital, false), col: metricColor(summary.totalPnlUsd) },
              { lbl: 'TOTAL P&L',       val: fmtMoney(summary.totalPnlUsd),         col: metricColor(summary.totalPnlUsd) },
              { lbl: 'RETURN %',        val: fmtPct(summary.totalPnlPct),            col: metricColor(summary.totalPnlPct) },
              { lbl: 'WIN RATE',        val: `${summary.winRate.toFixed(1)}%`,       col: rateColor(summary.winRate) },
              { lbl: 'TRADES',          val: String(summary.trades),                 col: 'var(--t-bright, #e0e0e0)' },
              { lbl: 'WINS / LOSSES',   val: `${summary.wins} / ${summary.losses}`, col: '#888' },
              { lbl: 'PROFIT FACTOR',   val: summary.profitFactor >= 999 ? '∞' : summary.profitFactor.toFixed(2), col: summary.profitFactor >= 1.5 ? '#10B981' : summary.profitFactor >= 1 ? '#F59E0B' : '#EF4444' },
              { lbl: 'MAX DRAWDOWN',    val: `-${summary.maxDrawdownPct.toFixed(1)}%`, col: summary.maxDrawdownPct > 20 ? '#EF4444' : summary.maxDrawdownPct > 10 ? '#F59E0B' : '#10B981' },
              { lbl: 'SHARPE',          val: summary.sharpe.toFixed(2),              col: summary.sharpe >= 1 ? '#10B981' : summary.sharpe >= 0 ? '#F59E0B' : '#EF4444' },
              { lbl: 'SORTINO',         val: summary.sortino.toFixed(2),             col: summary.sortino >= 1.5 ? '#10B981' : summary.sortino >= 0 ? '#F59E0B' : '#EF4444' },
              { lbl: 'CALMAR',          val: summary.calmar.toFixed(2),              col: summary.calmar >= 1 ? '#10B981' : summary.calmar >= 0 ? '#F59E0B' : '#EF4444' },
              { lbl: 'EXPECTANCY',      val: fmtMoney(summary.expectancyUsd),        col: metricColor(summary.expectancyUsd) },
              { lbl: 'AVG WIN',         val: fmtMoney(summary.avgWinUsd, false),     col: '#10B981' },
              { lbl: 'AVG LOSS',        val: fmtMoney(-summary.avgLossUsd),          col: '#EF4444' },
              { lbl: 'MAX CONSEC WINS', val: String(summary.maxConsecWins),          col: '#10B981' },
              { lbl: 'MAX CONSEC LOSS', val: String(summary.maxConsecLosses),        col: '#EF4444' },
              { lbl: 'FEES PAID',       val: fmtMoney(-summary.totalFeesUsd),        col: '#F59E0B' },
              { lbl: 'SLIPPAGE COST',   val: fmtMoney(-summary.totalSlippageUsd),    col: '#71717A' },
              { lbl: 'PEAK CAPITAL',    val: fmtMoney(summary.peakCapital, false),   col: '#F59E0B' },
              { lbl: 'DD FROM PEAK $',  val: fmtMoney(-summary.maxDrawdownUsd),      col: '#EF4444' },
            ].map(({ lbl, val, col }) => (
              <div key={lbl} style={{ ...T, borderRadius: 5, padding: '7px 10px' }}>
                <div style={{ fontSize: 7, color: 'var(--t-dim, #555)', letterSpacing: '0.12em', marginBottom: 3 }}>{lbl}</div>
                <div style={{ fontSize: 14, fontWeight: 800, color: col, fontVariantNumeric: 'tabular-nums' }}>{val}</div>
              </div>
            ))}
          </div>

          {/* Config summary pill */}
          <div style={{ fontSize: 8, color: 'var(--t-dim, #555)', marginBottom: 12,
            display: 'flex', gap: 12, flexWrap: 'wrap', padding: '5px 0', borderBottom: '1px solid var(--t-border, #1e1e1e)' }}>
            <span>${capital.toLocaleString()} capital</span>
            <span>{sizingMode === 'pct' ? `${positionPct}% × ${leverage}× = ${(positionPct * leverage).toFixed(0)}% eff.`
                 : sizingMode === 'fixed' ? `$${positionFixed.toLocaleString()} × ${leverage}×`
                 : `Kelly × ${leverage}×`}</span>
            <span>SL {stopPct}% / TP {(stopPct * rrRatio).toFixed(1)}% (R:R {rrRatio}:1)</span>
            <span>Trail: {trailEnabled ? `on (${trailActivation}% activation)` : 'off'}</span>
            <span>Fee: {feeMode} · slip {slippagePct}%</span>
            <span>Signal: {signalFilter} · horizon: {fwdHorizon}</span>
            {cooldownBars > 0 && <span>Cooldown: {cooldownBars} bars</span>}
            {circuitBreaker > 0 && <span>CB: {circuitBreaker}%</span>}
          </div>

          {/* ── Equity curve ── */}
          <div style={{ marginBottom: 14 }}>
            {sectionHdr('EQUITY CURVE + DRAWDOWN')}
            <div style={{ ...T, borderRadius: 6, padding: '8px 12px' }}>
              <EquityCurve curve={summary.equityCurve} initial={capital} />
            </div>
          </div>

          {/* ── P&L distribution ── */}
          <div style={{ marginBottom: 14 }}>
            {sectionHdr('P&L DISTRIBUTION')}
            <div style={{ ...T, borderRadius: 6, padding: '8px 12px' }}>
              <PnLHistogram dist={summary.pnlDistribution} />
            </div>
          </div>

          {/* ── Monthly P&L ── */}
          <div style={{ marginBottom: 14 }}>
            {sectionHdr('MONTHLY P&L',
              <button onClick={() => setShowMonthly(s => !s)} style={{ ...toggle(false), fontSize: 8 }}>
                {showMonthly ? '▲ HIDE' : '▼ SHOW'}
              </button>
            )}
            {showMonthly && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10, fontVariantNumeric: 'tabular-nums' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--t-border, #1e1e1e)' }}>
                      {['MONTH', 'TRADES', 'WIN RATE', 'P&L $', 'P&L %'].map(h => (
                        <th key={h} style={{ padding: '4px 10px', color: 'var(--t-dim, #555)', fontWeight: 700, textAlign: 'right', fontSize: 9, letterSpacing: '0.08em' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(summary.monthlyPnl).sort().map(([month, m]) => {
                      const wr  = m.trades > 0 ? m.wins / m.trades * 100 : 0;
                      const pct = capital > 0 ? m.pnl / capital * 100 : 0;
                      return (
                        <tr key={month} style={{ borderBottom: '1px solid var(--t-border, #111)', background: m.pnl >= 0 ? 'rgba(16,185,129,0.04)' : 'rgba(239,68,68,0.04)' }}>
                          <td style={{ padding: '4px 10px', color: 'var(--t-bright, #ccc)', textAlign: 'right', fontWeight: 700 }}>{month}</td>
                          <td style={{ padding: '4px 10px', color: 'var(--t-dim, #666)', textAlign: 'right' }}>{m.trades}</td>
                          <td style={{ padding: '4px 10px', textAlign: 'right', color: rateColor(wr) }}>{wr.toFixed(0)}%</td>
                          <td style={{ padding: '4px 10px', textAlign: 'right', fontWeight: 700, color: m.pnl >= 0 ? '#10B981' : '#EF4444' }}>
                            {fmtMoney(m.pnl)}
                          </td>
                          <td style={{ padding: '4px 10px', textAlign: 'right', color: pct >= 0 ? '#10B981' : '#EF4444' }}>
                            {fmtPct(pct)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Trade ledger ── */}
          <div>
            {sectionHdr(`TRADE LEDGER (${trades.length})`,
              <button onClick={() => setShowLedger(s => !s)} style={{ ...toggle(false), fontSize: 8 }}>
                {showLedger ? '▲ HIDE' : '▼ SHOW'}
              </button>
            )}
            {showLedger && (
              <div style={{ overflowX: 'auto', maxHeight: 360, overflowY: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 9, fontVariantNumeric: 'tabular-nums' }}>
                  <thead style={{ position: 'sticky', top: 0, background: 'var(--t-bg2, #141414)', zIndex: 1 }}>
                    <tr style={{ borderBottom: '1px solid var(--t-border, #1e1e1e)' }}>
                      {['#', 'DATE', 'DIR', 'ENTRY', 'SL', 'TRAIL SL', 'TP', 'EXIT', 'REASON', 'GROSS%', 'FEES%', 'NET%', 'P&L $', 'POS $', 'CAPITAL', 'DD%'].map(h => (
                        <th key={h} style={{ padding: '5px 7px', color: 'var(--t-dim, #555)', fontWeight: 700, letterSpacing: '0.05em', textAlign: 'right', whiteSpace: 'nowrap', borderBottom: '1px solid var(--t-border, #222)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map(t => (
                      <tr key={t.n} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', background: t.isWin ? 'rgba(16,185,129,0.04)' : 'rgba(239,68,68,0.04)' }}>
                        <td style={{ padding: '4px 7px', color: 'var(--t-dim, #444)', textAlign: 'right' }}>{t.n}</td>
                        <td style={{ padding: '4px 7px', color: 'var(--t-dim, #666)', textAlign: 'right', whiteSpace: 'nowrap' }}>{t.date}</td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', fontWeight: 800, color: t.direction === 'long' ? '#10B981' : '#EF4444' }}>
                          {t.direction === 'long' ? '↑L' : '↓S'}
                        </td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', color: 'var(--t-bright, #ccc)' }}>${t.entry.toLocaleString()}</td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', color: '#EF4444' }}>${t.initialSl.toLocaleString()}</td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', color: t.trailSl !== t.initialSl ? '#F59E0B' : 'var(--t-dim, #333)' }}>
                          {t.trailSl !== t.initialSl ? `$${t.trailSl.toLocaleString()}` : '—'}
                        </td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', color: '#10B981' }}>${t.tp.toLocaleString()}</td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', color: 'var(--t-bright, #ccc)' }}>${t.exit.toLocaleString()}</td>
                        <td style={{ padding: '4px 7px', textAlign: 'right' }}>
                          <span style={{ color: exitColor(t.exitReason), fontWeight: 800 }}>{t.exitReason}</span>
                        </td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', color: t.grossPnlPct >= 0 ? '#10B981' : '#EF4444' }}>
                          {t.grossPnlPct >= 0 ? '+' : ''}{t.grossPnlPct.toFixed(2)}%
                        </td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', color: '#F59E0B' }}>
                          -{t.feesPct.toFixed(3)}%
                        </td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', fontWeight: 700, color: t.netPnlPct >= 0 ? '#10B981' : '#EF4444' }}>
                          {t.netPnlPct >= 0 ? '+' : ''}{t.netPnlPct.toFixed(2)}%
                        </td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', fontWeight: 700, color: t.pnlUsd >= 0 ? '#10B981' : '#EF4444' }}>
                          {t.pnlUsd >= 0 ? '+' : ''}{Math.abs(t.pnlUsd) >= 1000
                            ? `$${Math.abs(t.pnlUsd).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
                            : `$${Math.abs(t.pnlUsd).toFixed(2)}`}{t.pnlUsd < 0 ? '' : ''}
                        </td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', color: 'var(--t-dim, #666)' }}>
                          ${Math.round(t.positionUsd).toLocaleString()}
                        </td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', color: t.capitalAfter >= t.capitalBefore ? '#10B981' : '#EF4444', fontWeight: 700 }}>
                          {t.capitalAfter >= 1000
                            ? `$${(t.capitalAfter / 1000).toFixed(1)}k`
                            : `$${t.capitalAfter.toFixed(0)}`}
                        </td>
                        <td style={{ padding: '4px 7px', textAlign: 'right', color: t.drawdownPct > 10 ? '#EF4444' : t.drawdownPct > 5 ? '#F59E0B' : 'var(--t-dim, #555)' }}>
                          {t.drawdownPct > 0.01 ? `-${t.drawdownPct.toFixed(1)}%` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
// ── MTF components ────────────────────────────────────────────────────────────
function MTFSparkline({ curve }: { curve: number[] }) {
  if (curve.length < 2) return <span style={{ color: '#333' }}>—</span>;
  const W = 80, H = 24;
  const min = Math.min(...curve), max = Math.max(...curve);
  const range = max - min || 1;
  const pts = curve.map((v, i) =>
    `${((i / (curve.length - 1)) * W).toFixed(1)},${(H - ((v - min) / range) * H).toFixed(1)}`
  ).join(' ');
  const color = curve[curve.length - 1] >= curve[0] ? '#10B981' : '#EF4444';
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

const _MTF_PROFILE_ORDER = ['scalping_15m', 'intraday_1h', 'intraday_4h'];

function MTFSection({ data }: { data: MTFBacktestResult }) {
  const { profiles, recommended } = data;
  const rateCol = (v: number | null) =>
    v == null ? '#444' : v >= 60 ? '#10B981' : v >= 50 ? '#F59E0B' : '#EF4444';
  const numCol = (v: number | null) =>
    v == null ? '#444' : v >= 0 ? '#10B981' : '#EF4444';
  const fmt = (v: number | null, dec = 2) => v == null ? '—' : v.toFixed(dec);

  const th: React.CSSProperties = {
    padding: '5px 10px', color: '#555', fontSize: 9, fontWeight: 700,
    letterSpacing: '0.1em', textAlign: 'right' as const,
    borderBottom: '1px solid #1e1e1e', whiteSpace: 'nowrap' as const,
  };
  const tdBase: React.CSSProperties = {
    padding: '6px 10px', textAlign: 'right' as const,
    fontSize: 12, fontVariantNumeric: 'tabular-nums' as const,
  };

  return (
    <div style={{ marginTop: 20, borderTop: '1px solid #1e1e1e', paddingTop: 16 }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', color: '#555', marginBottom: 12 }}>
        MULTI-TIMEFRAME COMPARISON
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr>
              {['PROFILE', 'TF PAIR', 'TRADES', 'WIN RATE', 'SHARPE', 'CALMAR',
                'PROFIT FACTOR', 'MAX DD', 'FWD1 LONG WR', 'EQUITY', ''].map(h => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {_MTF_PROFILE_ORDER.filter(k => profiles[k]).map(key => {
              const r = profiles[key];
              const isRec = key === recommended;
              return (
                <tr key={key} style={{
                  borderBottom: '1px solid #111',
                  background: isRec ? 'rgba(16,185,129,0.06)' : 'transparent',
                }}>
                  <td style={{ ...tdBase, color: '#e0e0e0', fontWeight: 700, textAlign: 'left' as const }}>
                    {r.label}
                  </td>
                  <td style={{ ...tdBase, color: '#666', fontSize: 10 }}>
                    {r.signal_tf} / {r.regime_tf}
                  </td>
                  <td style={{ ...tdBase, color: '#ccc' }}>{r.total_trades}</td>
                  <td style={{ ...tdBase, color: rateCol(r.win_rate) }}>
                    {r.win_rate != null ? `${r.win_rate.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ ...tdBase, color: numCol(r.sharpe) }}>{fmt(r.sharpe)}</td>
                  <td style={{ ...tdBase, color: numCol(r.calmar) }}>{fmt(r.calmar)}</td>
                  <td style={{ ...tdBase, color: numCol(r.profit_factor) }}>{fmt(r.profit_factor)}</td>
                  <td style={{ ...tdBase, color: r.max_drawdown != null && r.max_drawdown < -20 ? '#EF4444' : '#F59E0B' }}>
                    {r.max_drawdown != null ? `${r.max_drawdown.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ ...tdBase, color: rateCol(r.fwd1_long_win_rate), fontSize: 10 }}>
                    {r.fwd1_long_win_rate != null ? `${r.fwd1_long_win_rate}%` : '—'}
                    <span style={{ color: '#444', marginLeft: 3, fontSize: 9 }}>{r.fwd1_label}</span>
                  </td>
                  <td style={{ padding: '4px 10px', textAlign: 'center' as const }}>
                    <MTFSparkline curve={r.equity_curve} />
                  </td>
                  <td style={{ padding: '4px 8px' }}>
                    {isRec && (
                      <span style={{
                        background: '#10B98122', color: '#10B981',
                        border: '1px solid #10B98155', borderRadius: 3,
                        padding: '2px 6px', fontSize: 8, fontWeight: 800,
                      }}>BEST</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ color: '#333', fontSize: 9, marginTop: 8 }}>
        Recommended = highest Sharpe with ≥5 trades · Fee 0.1% RT · ATR-based exits
      </div>
    </div>
  );
}

interface Props { underlying: string }

export function BacktestPanel({ underlying }: Props) {
  const [lookback, setLookback] = useState(30);
  const [sampleEvery, setSampleEvery] = useState(4);
  const [atmIv, setAtmIv] = useState('');
  const [optionDte, setOptionDte] = useState(30);
  const [mtfLookback, setMtfLookback] = React.useState(30);
  const { mutate, data, isPending, error } = useBacktest();
  const { data: mtfData, isPending: mtfPending, error: mtfError, mutate: runMtf } = useMTFBacktest();
  const s = data?.stats;
  const totalBars = s?.total_bars_evaluated || 1;
  const hasBS = data?.atm_iv_used != null;

  return (
    <div style={S.card}>
      <div style={S.title}>BACKTEST — INDICATOR REPLAY + SIGNAL QUALITY</div>

      <div style={S.controls}>
        <div style={S.field}>
          <label style={S.label}>LOOKBACK DAYS</label>
          <input style={S.input} type="number" min={7} max={365}
            value={lookback} onChange={e => setLookback(parseInt(e.target.value) || 30)} />
        </div>
        <div style={S.field}>
          <label style={S.label}>SAMPLE EVERY N 1H BARS</label>
          <input style={S.input} type="number" min={1} max={24}
            value={sampleEvery} onChange={e => setSampleEvery(parseInt(e.target.value) || 4)} />
        </div>
        <div style={S.field}>
          <label style={S.label}>ATM IV % (optional BS)</label>
          <input style={{ ...S.input, width: 70 }} type="number" min={1} max={500} step={1}
            placeholder="e.g. 80" value={atmIv}
            onChange={e => setAtmIv(e.target.value)}
            title="Current ATM IV in % (e.g. 80 = 80%). Enables theoretical option P&L." />
        </div>
        <div style={S.field}>
          <label style={S.label}>OPTION DTE</label>
          <input style={{ ...S.input, width: 55 }} type="number" min={7} max={90}
            value={optionDte} onChange={e => setOptionDte(parseInt(e.target.value) || 30)} />
        </div>
        <button
          style={isPending ? { ...S.runBtn, opacity: 0.5, cursor: 'not-allowed' } : S.runBtn}
          onClick={() => mutate({
            underlying,
            lookback_days: lookback,
            sample_every_n_bars: sampleEvery,
            atm_iv: atmIv ? parseFloat(atmIv) / 100.0 : undefined,
            option_dte: optionDte,
          })}
          disabled={isPending}
        >
          {isPending ? 'RUNNING…' : `▶ RUN BACKTEST — ${underlying}`}
        </button>
        <div style={{ borderLeft: '1px solid #222', paddingLeft: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <div style={S.field}>
              <label style={S.label}>MTF LOOKBACK</label>
              <input style={{ ...S.input, width: 55 }} type="number" min={14} max={90}
                value={mtfLookback} onChange={e => setMtfLookback(parseInt(e.target.value) || 30)} />
            </div>
            <button
              style={mtfPending
                ? { ...S.runBtn, opacity: 0.5, cursor: 'not-allowed', fontSize: 10 }
                : { ...S.runBtn, fontSize: 10 }}
              onClick={() => runMtf({
                underlying,
                lookback_days: mtfLookback,
                profiles: ['scalping_15m', 'intraday_1h'],
              })}
              disabled={mtfPending}
            >
              {mtfPending ? 'ANALYZING…' : '⊞ MTF ANALYSIS'}
            </button>
          </div>
        </div>
      </div>

      {error && <div style={S.error}>{(error as Error).message}</div>}

      {!data && !isPending && (
        <div style={S.noData}>
          Run backtest to replay historical signals — regime, arrows, setup quality, forward returns.
        </div>
      )}
      {!data && mtfError && <div style={S.error}>{mtfError}</div>}
      {!data && mtfData && <MTFSection data={mtfData} />}

      {data && s && (
        <>
          <MiniChart bars={data.bars} />

          <div style={S.sectionTitle}>REGIME DISTRIBUTION</div>
          <div style={S.grid3}>
            <StatCard label="BULLISH REGIME"
              value={`${(s.bullish_regime_bars / totalBars * 100).toFixed(0)}%`}
              color="#44cc88"
              sub={`${s.bullish_regime_bars} bars`} />
            <StatCard label="BEARISH REGIME"
              value={`${(s.bearish_regime_bars / totalBars * 100).toFixed(0)}%`}
              color="#cc4444"
              sub={`${s.bearish_regime_bars} bars`} />
            <StatCard label="NEUTRAL REGIME"
              value={`${(s.neutral_regime_bars / totalBars * 100).toFixed(0)}%`}
              color="#888"
              sub={`${s.neutral_regime_bars} bars`} />
          </div>

          <div style={S.sectionTitle}>SETUP COUNTS</div>
          <div style={S.grid4}>
            <StatCard label="GREEN ARROWS" value={s.green_arrows} color="#44cc88" />
            <StatCard label="RED ARROWS" value={s.red_arrows} color="#cc4444" />
            <StatCard label="CONFIRMED LONG" value={s.confirmed_long_setups} color="#44cc88" />
            <StatCard label="CONFIRMED SHORT" value={s.confirmed_short_setups} color="#cc4444" />
            <StatCard label="EARLY LONG" value={s.early_long_setups} color="#f0a500" />
            <StatCard label="EARLY SHORT" value={s.early_short_setups} color="#f0a500" />
            <StatCard label="FILTERED" value={s.filtered_bars} color="#555" />
            <StatCard label="IDLE" value={s.idle_bars} color="#333" />
          </div>

          <QualityPanel s={s} bars={data.bars} />

          {hasBS && (
            <>
              <div style={S.sectionTitle}>
                OPTION P&L (BS) — IV {((data.atm_iv_used ?? 0) * 100).toFixed(0)}% · {data.option_dte_used}d DTE
              </div>
              <div style={S.grid4}>
                <StatCard
                  label="CALL WIN RATE 4H"
                  value={s.bs_arrow_long_win_rate_4h != null ? `${s.bs_arrow_long_win_rate_4h.toFixed(0)}%` : '—'}
                  color={s.bs_arrow_long_win_rate_4h != null && s.bs_arrow_long_win_rate_4h >= 50 ? '#44cc88' : '#cc4444'}
                  sub="on green arrows" />
                <StatCard
                  label="PUT WIN RATE 4H"
                  value={s.bs_arrow_short_win_rate_4h != null ? `${s.bs_arrow_short_win_rate_4h.toFixed(0)}%` : '—'}
                  color={s.bs_arrow_short_win_rate_4h != null && s.bs_arrow_short_win_rate_4h >= 50 ? '#44cc88' : '#cc4444'}
                  sub="on red arrows" />
                <StatCard
                  label="AVG CALL P&L 4H"
                  value={s.bs_arrow_long_avg_pnl_4h != null ? `${s.bs_arrow_long_avg_pnl_4h.toFixed(1)}%` : '—'}
                  color={s.bs_arrow_long_avg_pnl_4h != null && s.bs_arrow_long_avg_pnl_4h >= 0 ? '#44cc88' : '#cc4444'}
                  sub="% of premium" />
                <StatCard
                  label="AVG PUT P&L 4H"
                  value={s.bs_arrow_short_avg_pnl_4h != null ? `${s.bs_arrow_short_avg_pnl_4h.toFixed(1)}%` : '—'}
                  color={s.bs_arrow_short_avg_pnl_4h != null && s.bs_arrow_short_avg_pnl_4h >= 0 ? '#44cc88' : '#cc4444'}
                  sub="% of premium" />
              </div>
            </>
          )}

          <div style={S.meta}>
            {data.total_1h_candles} × 1H bars · {data.total_4h_candles} × 4H bars · {data.lookback_days}d window · {totalBars} sampled bars
            {hasBS && ` · BS IV ${((data.atm_iv_used ?? 0) * 100).toFixed(0)}%`}
          </div>

          <SimulationPanel bars={data.bars} underlying={underlying} />
          {mtfError && <div style={S.error}>{mtfError}</div>}
          {mtfData && <MTFSection data={mtfData} />}
        </>
      )}
    </div>
  );
}
