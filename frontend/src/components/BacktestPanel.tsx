import React, { useState } from 'react';
import { useBacktest } from '../hooks/useBacktest';
import type { BacktestStats, BacktestBarResult } from '../hooks/useBacktest';

const styles: Record<string, React.CSSProperties> = {
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
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 },
  statCard: { background: '#111', border: '1px solid #1e1e1e', borderRadius: 4, padding: 10 },
  statLabel: { color: '#555', fontSize: 10, letterSpacing: 1, marginBottom: 4 },
  statVal: { fontSize: 18, fontWeight: 700 },
  barChart: { display: 'flex', gap: 2, height: 40, alignItems: 'flex-end', marginBottom: 12 },
  chartBar: { flex: 1, minWidth: 2, borderRadius: 1 },
  legend: { display: 'flex', gap: 12, fontSize: 11, color: '#666', marginBottom: 12 },
  dot: { width: 8, height: 8, borderRadius: '50%', display: 'inline-block', marginRight: 4 },
  error: { color: '#cc4444', fontSize: 12 },
  meta: { color: '#444', fontSize: 11, marginTop: 8 },
  noData: { color: '#444', fontSize: 12, padding: '20px 0', textAlign: 'center' },
};

function StatCard({ label, value, color = '#e0e0e0' }: { label: string; value: number | string; color?: string }) {
  return (
    <div style={styles.statCard}>
      <div style={styles.statLabel}>{label}</div>
      <div style={{ ...styles.statVal, color }}>{value}</div>
    </div>
  );
}

function MiniChart({ bars }: { bars: BacktestBarResult[] }) {
  if (!bars.length) return null;

  const prices = bars.map(b => b.close_1h);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const range = maxP - minP || 1;

  const colorFor = (b: BacktestBarResult) => {
    if (b.macro_regime === 'bullish' && b.signal_trend === 1) return '#44cc88';
    if (b.macro_regime === 'bearish' && b.signal_trend === -1) return '#cc4444';
    if (b.green_arrow || b.red_arrow) return '#f0c040';
    return '#333';
  };

  return (
    <div>
      <div style={styles.legend}>
        <span><span style={{ ...styles.dot, background: '#44cc88' }} />Bullish aligned</span>
        <span><span style={{ ...styles.dot, background: '#cc4444' }} />Bearish aligned</span>
        <span><span style={{ ...styles.dot, background: '#f0c040' }} />Arrow fired</span>
        <span><span style={{ ...styles.dot, background: '#333' }} />Mixed</span>
      </div>
      <div style={styles.barChart}>
        {bars.map((b, i) => {
          const heightPct = ((b.close_1h - minP) / range) * 34 + 6;
          return (
            <div
              key={i}
              title={`${b.macro_regime} · trend ${b.signal_trend} · $${b.close_1h.toFixed(0)}`}
              style={{ ...styles.chartBar, background: colorFor(b), height: `${heightPct}px` }}
            />
          );
        })}
      </div>
    </div>
  );
}

interface Props { underlying: string }

export function BacktestPanel({ underlying }: Props) {
  const [lookback, setLookback] = useState(30);
  const [sampleEvery, setSampleEvery] = useState(4);
  const { mutate, data, isPending, error } = useBacktest();

  const s: BacktestStats | undefined = data?.stats;

  return (
    <div style={styles.card}>
      <div style={styles.title}>BACKTEST — INDICATOR REPLAY (no options data needed)</div>
      <div style={styles.controls}>
        <div style={styles.field}>
          <label style={styles.label}>LOOKBACK DAYS</label>
          <input style={styles.input} type="number" min={7} max={365}
            value={lookback} onChange={e => setLookback(parseInt(e.target.value) || 30)} />
        </div>
        <div style={styles.field}>
          <label style={styles.label}>SAMPLE EVERY N BARS</label>
          <input style={styles.input} type="number" min={1} max={24}
            value={sampleEvery} onChange={e => setSampleEvery(parseInt(e.target.value) || 4)} />
        </div>
        <button
          style={isPending ? { ...styles.runBtn, opacity: 0.5, cursor: 'not-allowed' } : styles.runBtn}
          onClick={() => mutate({ underlying, lookback_days: lookback, sample_every_n_bars: sampleEvery })}
          disabled={isPending}
        >
          {isPending ? 'RUNNING…' : `▶ RUN BACKTEST — ${underlying}`}
        </button>
      </div>

      {error && <div style={styles.error}>{(error as Error).message}</div>}

      {!data && !isPending && (
        <div style={styles.noData}>
          Run backtest to see historical signal replay — regime, signal, arrows, setups.
        </div>
      )}

      {data && s && (
        <>
          <MiniChart bars={data.bars} />
          <div style={styles.statsGrid}>
            <StatCard label="BARS EVALUATED" value={s.total_bars_evaluated} />
            <StatCard label="GREEN ARROWS" value={s.green_arrows} color="#44cc88" />
            <StatCard label="RED ARROWS" value={s.red_arrows} color="#cc4444" />
            <StatCard label="CONFIRMED LONG SETUPS" value={s.confirmed_long_setups} color="#44cc88" />
            <StatCard label="CONFIRMED SHORT SETUPS" value={s.confirmed_short_setups} color="#cc4444" />
            <StatCard label="FILTERED BARS" value={s.filtered_bars} color="#555" />
            <StatCard label="BULLISH REGIME %" value={`${(s.bullish_regime_bars / s.total_bars_evaluated * 100 || 0).toFixed(0)}%`} color="#44cc88" />
            <StatCard label="BEARISH REGIME %" value={`${(s.bearish_regime_bars / s.total_bars_evaluated * 100 || 0).toFixed(0)}%`} color="#cc4444" />
            <StatCard label="EARLY SETUPS (L+S)" value={s.early_long_setups + s.early_short_setups} color="#f0a500" />
          </div>
          <div style={styles.meta}>
            {data.total_1h_candles} × 1H bars | {data.total_4h_candles} × 4H bars | {data.lookback_days}d window
            · ts: {new Date(data.timestamp_ms).toISOString()}
          </div>
        </>
      )}
    </div>
  );
}
