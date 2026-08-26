import React, { useState } from 'react';
import { useEngineBacktest } from '../../hooks/useSterlingKiteEngine';
import type {
  BacktestDataMode, BacktestRequest, BacktestRun, BacktestStats, ExitMode,
} from '../../types/kiteEngine';

/**
 * Kite options backtest tab (workstream H).
 *
 * Three honest data modes the user picks between:
 *   • synthetic — signal replayed on real underlying history, premium modeled (BS)
 *   • real      — actual fetched premium for a live contract (short lookback)
 *   • both      — synthetic history + a real-contract calibration drift check
 *
 * Every result carries an explicit caveat badge so a MODELED curve is never read
 * as a real-fill track record.
 */

const S: Record<string, React.CSSProperties> = {
  wrap: { width: '100%', height: '100%', overflow: 'auto', padding: '24px 32px', boxSizing: 'border-box' },
  h1: { fontSize: 18, fontWeight: 700, color: 'var(--k-ink-1)', marginBottom: 4 },
  sub: { fontSize: 12, color: 'var(--k-dim)', marginBottom: 20 },
  card: { background: 'var(--k-bg)', border: '1px solid var(--k-border)', borderRadius: 6, padding: 18, marginBottom: 16 },
  label: { display: 'block', fontSize: 11, color: 'var(--k-dim)', fontWeight: 700, letterSpacing: 0.6, marginBottom: 6, textTransform: 'uppercase' },
  input: { width: '100%', background: 'var(--k-bg)', color: 'var(--k-ink-1)', border: '1px solid var(--k-border)', borderRadius: 4, padding: '8px 10px', fontSize: 13, boxSizing: 'border-box', minWidth: 0 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 14 },
  runBtn: { background: 'var(--k-brand)', color: 'var(--k-on-accent)', border: 'none', borderRadius: 4, padding: '10px 22px', fontSize: 14, fontWeight: 700, cursor: 'pointer' },
  statGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 12, marginTop: 14 },
  statBox: { border: '1px solid var(--k-hairline-3)', borderRadius: 4, padding: '10px 12px' },
  statVal: { fontSize: 16, fontWeight: 700, color: 'var(--k-ink-1)' },
  statLbl: { fontSize: 10, color: 'var(--k-dim)', textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 2 },
  caveat: { fontSize: 12, color: '#8a6d00', background: 'rgba(255,193,7,0.12)', border: '1px solid rgba(255,193,7,0.5)', borderRadius: 4, padding: '8px 12px', marginTop: 10 },
};

const modeBtn = (active: boolean): React.CSSProperties => ({
  flex: 1, padding: '8px 10px', fontSize: 12, fontWeight: 700, cursor: 'pointer',
  border: `1px solid ${active ? 'var(--k-brand)' : 'var(--k-border)'}`,
  color: active ? 'var(--k-bg)' : 'var(--k-ink-4)', background: active ? 'var(--k-brand)' : 'var(--k-bg)',
  borderRadius: 4, textAlign: 'center',
});

const MODES: { key: BacktestDataMode; label: string; hint: string }[] = [
  { key: 'both', label: 'Both', hint: 'Modeled history + real-contract drift check (recommended)' },
  { key: 'synthetic', label: 'Synthetic', hint: 'Full history, premium modeled (Black-Scholes)' },
  { key: 'real', label: 'Real premium', hint: 'True prices, live contract only (short lookback)' },
];

function Num({ label, value, onChange, step = 1, min }: {
  label: string; value: number; onChange: (v: number) => void; step?: number; min?: number;
}) {
  return (
    <div>
      <label style={S.label}>{label}</label>
      <input type="number" style={S.input} value={value} step={step} min={min}
        onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

function fmt(n: number, dp = 0): string {
  if (!isFinite(n)) return '∞';
  return n.toLocaleString('en-IN', { maximumFractionDigits: dp, minimumFractionDigits: dp });
}

function Sparkline({ curve }: { curve: number[] }) {
  if (curve.length < 2) return null;
  const w = 320, h = 60;
  const min = Math.min(...curve), max = Math.max(...curve);
  const span = max - min || 1;
  const pts = curve.map((v, i) => {
    const x = (i / (curve.length - 1)) * w;
    const y = h - ((v - min) / span) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const up = curve[curve.length - 1] >= curve[0];
  return (
    <svg width={w} height={h} style={{ marginTop: 10 }}>
      <polyline points={pts} fill="none" stroke={up ? 'var(--k-green)' : 'var(--k-red-strong)'} strokeWidth={1.5} />
    </svg>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={S.statBox}>
      <div style={{ ...S.statVal, color: color ?? 'var(--k-ink-1)' }}>{value}</div>
      <div style={S.statLbl}>{label}</div>
    </div>
  );
}

function RunCard({ run }: { run: BacktestRun }) {
  const s: BacktestStats = run.stats;
  const pnlColor = s.net_pnl >= 0 ? 'var(--k-green-deep)' : 'var(--k-red-crimson)';
  return (
    <div style={S.card}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--k-ink-1)', textTransform: 'capitalize' }}>
          {run.mode} mode
        </span>
        <span style={{ fontSize: 11, color: 'var(--k-dim)' }}>{s.trades} trades</span>
      </div>
      {run.caveat && <div style={S.caveat}>⚠ {run.caveat}</div>}
      <Sparkline curve={run.equity_curve} />
      <div style={S.statGrid}>
        <StatBox label="Net P&L" value={`₹${fmt(s.net_pnl)}`} color={pnlColor} />
        <StatBox label="Return" value={`${fmt(s.return_pct, 1)}%`} color={pnlColor} />
        <StatBox label="Win rate" value={`${fmt(s.win_rate * 100, 1)}%`} />
        <StatBox label="Profit factor" value={fmt(s.profit_factor, 2)} />
        <StatBox label="Sharpe" value={fmt(s.sharpe, 2)} />
        <StatBox label="Max DD" value={`${fmt(s.max_drawdown, 1)}%`} />
        <StatBox label="Expectancy" value={`₹${fmt(s.expectancy)}`} />
        <StatBox label="Total costs" value={`₹${fmt(s.total_costs)}`} color="var(--k-red-crimson)" />
        <StatBox label="Wins / Losses" value={`${s.wins} / ${s.losses}`} />
        <StatBox label="Final capital" value={`₹${fmt(s.final_capital)}`} />
      </div>
    </div>
  );
}

export function BacktestPane() {
  const [symbol, setSymbol] = useState('NIFTY 50');
  const [mode, setMode] = useState<BacktestDataMode>('both');
  const [trail, setTrail] = useState<'fast' | 'mid' | 'slow'>('fast');
  const [exitMode, setExitMode] = useState<ExitMode>('two_red');
  const [lookback, setLookback] = useState(2000);
  const [capital, setCapital] = useState(100000);
  const [qty, setQty] = useState(50);
  const [iv, setIv] = useState(18);
  const [dte, setDte] = useState(7);
  const [offset, setOffset] = useState(0);
  const [slippage, setSlippage] = useState(1);

  const bt = useEngineBacktest();

  const run = () => {
    const req: BacktestRequest = {
      symbol: symbol.trim(),
      data_mode: mode,
      trail_target: trail,
      exit_mode: exitMode,
      lookback_bars: lookback,
      starting_capital: capital,
      qty,
      iv: iv / 100,
      dte_days: dte,
      moneyness_offset_pct: offset,
      slippage_pct: slippage / 100,
    };
    bt.mutate(req);
  };

  const res = bt.data;

  return (
    <div style={S.wrap}>
      <div style={S.h1}>Options Backtest</div>
      <div style={S.sub}>
        Replays the Sterling Kite Engine signal with real Indian F&amp;O costs (STT, brokerage, GST,
        slippage). Pick how option prices are sourced — each mode states its honesty caveat.
      </div>

      <div style={S.card}>
        {/* Data mode selector */}
        <label style={S.label}>Data source</label>
        <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
          {MODES.map((m) => (
            <div key={m.key} style={modeBtn(mode === m.key)} title={m.hint} onClick={() => setMode(m.key)}>
              {m.label}
            </div>
          ))}
        </div>
        <div style={{ fontSize: 11, color: 'var(--k-dim)', marginBottom: 16 }}>
          {MODES.find((m) => m.key === mode)?.hint}
          {mode !== 'real'
            ? "  ·  For synthetic/both, enter the UNDERLYING name (e.g. 'NIFTY 50')."
            : "  ·  For real, enter an option tradingsymbol (e.g. 'NIFTY24JUN24000CE')."}
        </div>

        <div style={S.grid}>
          <div style={{ gridColumn: '1 / -1', maxWidth: 360 }}>
            <label style={S.label}>{mode === 'real' ? 'Option symbol' : 'Underlying'}</label>
            <input style={S.input} value={symbol} onChange={(e) => setSymbol(e.target.value)} />
          </div>
          <div>
            <label style={S.label}>Trail target</label>
            <select style={S.input} value={trail} onChange={(e) => setTrail(e.target.value as 'fast' | 'mid' | 'slow')}>
              <option value="fast">Fast (tight)</option>
              <option value="mid">Mid (balanced)</option>
              <option value="slow">Slow (loose)</option>
            </select>
          </div>
          <div>
            <label style={S.label}>Exit mode</label>
            <select style={S.input} value={exitMode} onChange={(e) => setExitMode(e.target.value as ExitMode)}>
              <option value="one_red">1 red (tightest)</option>
              <option value="two_red">2 red (default)</option>
              <option value="three_red">3 red (loose)</option>
              <option value="three_red_signal">3 red + arrow</option>
            </select>
          </div>
          <Num label="Lookback bars (1H)" value={lookback} onChange={setLookback} step={100} min={100} />
          <Num label="Capital (₹)" value={capital} onChange={setCapital} step={10000} min={0} />
          <Num label="Qty (1 lot)" value={qty} onChange={setQty} step={25} min={1} />
          {mode !== 'real' && <Num label="IV %" value={iv} onChange={setIv} step={1} min={1} />}
          {mode !== 'real' && <Num label="DTE (days)" value={dte} onChange={setDte} step={1} min={1} />}
          {mode !== 'real' && <Num label="Moneyness offset %" value={offset} onChange={setOffset} step={0.5} />}
          <Num label="Slippage % / side" value={slippage} onChange={setSlippage} step={0.25} min={0} />
        </div>

        <div style={{ marginTop: 18 }}>
          <button style={S.runBtn} onClick={run} disabled={bt.isPending || !symbol.trim()}>
            {bt.isPending ? 'Running…' : 'Run backtest'}
          </button>
        </div>
      </div>

      {bt.isError && (
        <div style={{ ...S.card, borderColor: 'var(--k-red-strong)', color: 'var(--k-red-crimson)', fontSize: 13 }}>
          {bt.error?.message ?? 'Backtest failed.'}
        </div>
      )}

      {res && (
        <>
          {res.notes?.length > 0 && (
            <div style={{ ...S.card, background: 'var(--k-surface-2)' }}>
              {res.notes.map((n, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--k-ink-4)', marginBottom: 4 }}>• {n}</div>
              ))}
              {res.bs_vs_real_drift_pct != null && (
                <div style={{ fontSize: 12, color: '#8a6d00', marginTop: 6, fontWeight: 600 }}>
                  Model calibration: BS premium sits ≈ {res.bs_vs_real_drift_pct.toFixed(1)}% from real prices on the live contract.
                </div>
              )}
            </div>
          )}
          {res.runs.length === 0 && (
            <div style={{ ...S.card, fontSize: 13, color: 'var(--k-dim)' }}>
              No runs produced — see the notes above (usually an unresolved symbol or too little data).
            </div>
          )}
          {res.runs.map((r) => <RunCard key={r.mode} run={r} />)}
        </>
      )}
    </div>
  );
}

export default BacktestPane;
