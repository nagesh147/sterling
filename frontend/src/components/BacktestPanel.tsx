import React, { useState } from 'react';
import { useBacktest } from '../hooks/useBacktest';
import type { BacktestStats, BacktestBarResult } from '../hooks/useBacktest';

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

interface Props { underlying: string }

export function BacktestPanel({ underlying }: Props) {
  const [lookback, setLookback] = useState(30);
  const [sampleEvery, setSampleEvery] = useState(4);
  const { mutate, data, isPending, error } = useBacktest();
  const s = data?.stats;
  const totalBars = s?.total_bars_evaluated || 1;

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
        <button
          style={isPending ? { ...S.runBtn, opacity: 0.5, cursor: 'not-allowed' } : S.runBtn}
          onClick={() => mutate({ underlying, lookback_days: lookback, sample_every_n_bars: sampleEvery })}
          disabled={isPending}
        >
          {isPending ? 'RUNNING…' : `▶ RUN BACKTEST — ${underlying}`}
        </button>
      </div>

      {error && <div style={S.error}>{(error as Error).message}</div>}

      {!data && !isPending && (
        <div style={S.noData}>
          Run backtest to replay historical signals — regime, arrows, setup quality, forward returns.
        </div>
      )}

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

          <div style={S.meta}>
            {data.total_1h_candles} × 1H bars · {data.total_4h_candles} × 4H bars · {data.lookback_days}d window · {totalBars} sampled bars
          </div>
        </>
      )}
    </div>
  );
}
