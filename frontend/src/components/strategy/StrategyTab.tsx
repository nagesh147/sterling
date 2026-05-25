import React, { useEffect, useState } from 'react';
import { useSelectedUnderlying, useSetSelectedUnderlying } from '../../store/useStore';
import {
  useStrategyConfig, useSetStrategyConfig,
  useStrategyBacktest, useStrategyExecute, useStrategySignals,
  type TripleSTConfig, type StrategyMode, type AssetClass, type HTFSource,
  type BacktestResult, type SignalSummary,
} from '../../hooks/useStrategy';

/* ── tiny style helpers (terminal token palette) ─────────────────────────── */

const card: React.CSSProperties = {
  background: 'var(--t-bg2)', border: '1px solid var(--t-border)',
  borderRadius: 10, overflow: 'hidden',
};
const cardHead: React.CSSProperties = {
  padding: '8px 12px', borderBottom: '1px solid var(--t-border)',
  fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--t-bright)',
  display: 'flex', alignItems: 'center', gap: 8,
};
const cardBody: React.CSSProperties = { padding: 12 };
const dim: React.CSSProperties = { color: 'var(--t-dim)', fontSize: 10 };

function SectionCard({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={card}>
      <div style={cardHead}><span>{title}</span>{right && <span style={{ marginLeft: 'auto' }}>{right}</span>}</div>
      <div style={cardBody}>{children}</div>
    </div>
  );
}

function Toggle({ label, on, onChange }: { label: string; on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!on)}
      style={{
        display: 'flex', alignItems: 'center', gap: 7, width: '100%',
        background: 'none', border: 'none', cursor: 'pointer', padding: '3px 0',
        fontFamily: 'inherit', fontSize: 11, color: on ? 'var(--t-bright)' : 'var(--t-dim)',
      }}
    >
      <span style={{
        width: 26, height: 14, borderRadius: 8, flexShrink: 0, position: 'relative',
        background: on ? 'var(--t-green)' : 'var(--t-border)', transition: 'background .15s',
      }}>
        <span style={{
          position: 'absolute', top: 2, left: on ? 14 : 2, width: 10, height: 10,
          borderRadius: '50%', background: '#fff', transition: 'left .15s',
        }} />
      </span>
      {label}
    </button>
  );
}

function NumField({ label, value, step = 1, min, max, onChange }: {
  label: string; value: number; step?: number; min?: number; max?: number; onChange: (v: number) => void;
}) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 10, color: 'var(--t-dim)' }}>
      {label}
      <input
        type="number" value={value} step={step} min={min} max={max}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{
          width: 72, background: 'var(--t-bg)', border: '1px solid var(--t-border)',
          borderRadius: 4, color: 'var(--t-bright)', fontFamily: 'inherit', fontSize: 11,
          padding: '3px 6px', textAlign: 'right',
        }}
      />
    </label>
  );
}

function Pill({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', padding: '2px 7px',
      borderRadius: 4, background: color + '22', color, border: `1px solid ${color}44`,
      whiteSpace: 'nowrap',
    }}>{text}</span>
  );
}

const fmt = (v: number | null | undefined, d = 2) => (v == null || !isFinite(v) ? '—' : v.toFixed(d));
const fmtUsd = (v: number | null | undefined) => (v == null || !isFinite(v) ? '—' : '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 }));

/* ── config panel ─────────────────────────────────────────────────────────── */

const MODES: StrategyMode[] = ['Aggressive', 'Balanced', 'Conservative', 'Momentum'];
const ASSETS: AssetClass[] = ['Auto-Detect', 'Large', 'Mid', 'Small'];
const HTF: HTFSource[] = ['SuperTrend', 'EMA', 'Both'];

function Selector<T extends string>({ options, value, onChange }: { options: T[]; value: T; onChange: (v: T) => void }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {options.map((o) => (
        <button key={o} onClick={() => onChange(o)} style={{
          fontSize: 10, padding: '3px 8px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit',
          border: `1px solid ${value === o ? 'var(--t-blue)' : 'var(--t-border)'}`,
          background: value === o ? 'var(--t-bg3)' : 'transparent',
          color: value === o ? 'var(--t-blue)' : 'var(--t-dim)',
        }}>{o}</button>
      ))}
    </div>
  );
}

function ChipToggle({ label, on, onChange }: { label: string; on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!on)} style={{
      fontSize: 10, fontWeight: 600, padding: '4px 9px', borderRadius: 13, cursor: 'pointer', fontFamily: 'inherit',
      border: `1px solid ${on ? 'var(--t-green)' : 'var(--t-border)'}`,
      background: on ? 'var(--t-green)1c' : 'transparent',
      color: on ? 'var(--t-green)' : 'var(--t-dim)', transition: 'all .1s', whiteSpace: 'nowrap',
    }}>{on ? '● ' : '○ '}{label}</button>
  );
}

const grpBox: React.CSSProperties = { background: 'var(--t-bg)', border: '1px solid var(--t-border)', borderRadius: 8, padding: 11, display: 'flex', flexDirection: 'column', gap: 9 };
const grpTitle: React.CSSProperties = { fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--t-dim)' };

function ConfigPanel({ cfg, onSave, saving }: { cfg: TripleSTConfig; onSave: (c: TripleSTConfig) => void; saving: boolean }) {
  const [draft, setDraft] = useState<TripleSTConfig>(cfg);
  useEffect(() => { setDraft(cfg); }, [cfg]);
  const set = <K extends keyof TripleSTConfig>(k: K, v: TripleSTConfig[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const dirty = JSON.stringify(draft) !== JSON.stringify(cfg);

  const filters: [keyof TripleSTConfig, string][] = [
    ['use_ha', 'Heiken-Ashi'], ['use_volume', 'Volume'], ['use_rsi', 'RSI'],
    ['use_macd', 'MACD'], ['use_htf', 'HTF Bias'], ['use_btc_corr', 'BTC Corr'],
    ['use_regime_filter', 'Regime'], ['use_spike_guard', 'Spike Guard'], ['use_gap_protection', 'Gap Protect'],
  ];
  const protections: [keyof TripleSTConfig, string][] = [
    ['use_circuit_breaker', 'Circuit Breaker'], ['use_black_swan', 'Black Swan'], ['use_dynamic_mode', 'Dynamic Mode'],
  ];

  return (
    <SectionCard title="STRATEGY SETTINGS" right={
      <button disabled={!dirty || saving} onClick={() => onSave(draft)} style={{
        fontSize: 9, fontWeight: 700, padding: '3px 12px', borderRadius: 4, fontFamily: 'inherit',
        cursor: dirty && !saving ? 'pointer' : 'default',
        border: `1px solid ${dirty ? 'var(--t-green)' : 'var(--t-border)'}`,
        background: dirty ? 'var(--t-green)22' : 'transparent',
        color: dirty ? 'var(--t-green)' : 'var(--t-dim)',
      }}>{saving ? 'SAVING…' : dirty ? 'APPLY' : 'SAVED'}</button>
    }>
      {/* responsive grouped grid — fills horizontal space, no tall single column */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: 10, alignItems: 'start' }}>
        {/* Strategy */}
        <div style={grpBox}>
          <div style={grpTitle}>STRATEGY</div>
          <div><div style={{ ...dim, marginBottom: 4 }}>Mode</div><Selector options={MODES} value={draft.mode} onChange={(v) => set('mode', v)} /></div>
          <div><div style={{ ...dim, marginBottom: 4 }}>Asset class</div><Selector options={ASSETS} value={draft.asset_type} onChange={(v) => set('asset_type', v)} /></div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <ChipToggle label="Quality Score" on={draft.use_quality_score} onChange={(v) => set('use_quality_score', v)} />
            {draft.use_quality_score && (
              <input type="number" value={draft.quality_threshold} min={40} max={95}
                onChange={(e) => set('quality_threshold', parseInt(e.target.value) || 68)}
                title="Quality threshold (40–95)"
                style={{ width: 52, background: 'var(--t-bg2)', border: '1px solid var(--t-border)', borderRadius: 4, color: 'var(--t-bright)', fontFamily: 'inherit', fontSize: 11, padding: '3px 6px', textAlign: 'right' }} />
            )}
          </div>
        </div>

        {/* Filters */}
        <div style={grpBox}>
          <div style={grpTitle}>FILTERS</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {filters.map(([k, lbl]) => (
              <ChipToggle key={k} label={lbl} on={draft[k] as boolean} onChange={(v) => set(k, v as never)} />
            ))}
          </div>
          {draft.use_htf && (
            <div><div style={{ ...dim, marginBottom: 4 }}>HTF source</div><Selector options={HTF} value={draft.htf_source} onChange={(v) => set('htf_source', v)} /></div>
          )}
        </div>

        {/* Risk */}
        <div style={grpBox}>
          <div style={grpTitle}>RISK &amp; SIZING</div>
          <NumField label="Risk % / trade" value={draft.risk_percent} step={0.05} min={0.05} max={5} onChange={(v) => set('risk_percent', v)} />
          <NumField label="Max position %" value={draft.max_position_pct} step={1} min={1} max={100} onChange={(v) => set('max_position_pct', v)} />
          <NumField label="Daily loss %" value={draft.daily_loss_limit} step={0.5} min={0.5} max={20} onChange={(v) => set('daily_loss_limit', v)} />
          <NumField label="Max slippage %" value={draft.max_slippage} step={0.1} min={0} max={5} onChange={(v) => set('max_slippage', v)} />
          <NumField label="Account equity $" value={draft.account_equity} step={1000} min={100} onChange={(v) => set('account_equity', v)} />
        </div>

        {/* Protection */}
        <div style={grpBox}>
          <div style={grpTitle}>CAPITAL PROTECTION</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {protections.map(([k, lbl]) => (
              <ChipToggle key={k} label={lbl} on={draft[k] as boolean} onChange={(v) => set(k, v as never)} />
            ))}
          </div>
          {draft.use_circuit_breaker && (
            <NumField label="Consec. loss limit" value={draft.consecutive_loss_limit} min={2} max={10} onChange={(v) => set('consecutive_loss_limit', v)} />
          )}
        </div>
      </div>
    </SectionCard>
  );
}

/* ── backtest panel ───────────────────────────────────────────────────────── */

function EquitySpark({ curve }: { curve: { ts: number; equity: number }[] }) {
  if (curve.length < 2) return null;
  const w = 280, h = 56;
  const eq = curve.map((p) => p.equity);
  const lo = Math.min(...eq), hi = Math.max(...eq);
  const rng = hi - lo || 1;
  const pts = curve.map((p, i) => {
    const x = (i / (curve.length - 1)) * w;
    const y = h - ((p.equity - lo) / rng) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const up = eq[eq.length - 1] >= eq[0];
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={up ? 'var(--t-green)' : 'var(--t-red)'} strokeWidth={1.5} />
    </svg>
  );
}

const LOOKBACK_PRESETS: [string, number][] = [['3M', 90], ['6M', 180], ['1Y', 365], ['2Y', 730], ['3Y', 1095]];

function BacktestPanel({ underlying }: { underlying: string }) {
  const [lookback, setLookback] = useState(365);
  const bt = useStrategyBacktest();
  const res: BacktestResult | undefined = bt.data;

  const statTiles = (s: BacktestResult['stats']): [string, string, string][] => ([
    ['Return', `${fmt(s.total_return_pct, 1)}%`, s.total_return_pct >= 0 ? 'var(--t-green)' : 'var(--t-red)'],
    ['Win rate', `${fmt(s.win_rate * 100, 0)}%`, 'var(--t-bright)'],
    ['Trades', String(s.total_trades), 'var(--t-bright)'],
    ['Expectancy', `${fmt(s.expectancy_r, 2)}R`, s.expectancy_r >= 0 ? 'var(--t-green)' : 'var(--t-red)'],
    ['Profit factor', fmt(s.profit_factor, 2), s.profit_factor >= 1 ? 'var(--t-green)' : 'var(--t-red)'],
    ['Max DD', `${fmt(s.max_drawdown_pct, 1)}%`, 'var(--t-amber)'],
    ['Sharpe', fmt(s.sharpe, 2), 'var(--t-bright)'],
    ['Avg hold', `${fmt(s.avg_bars_held, 0)}h`, 'var(--t-bright)'],
  ]);

  return (
    <SectionCard title="BACKTEST" right={
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {LOOKBACK_PRESETS.map(([lbl, d]) => (
          <button key={d} onClick={() => setLookback(d)} style={{
            fontSize: 9, fontWeight: 700, padding: '3px 7px', borderRadius: 4, fontFamily: 'inherit', cursor: 'pointer',
            border: `1px solid ${lookback === d ? 'var(--t-blue)' : 'var(--t-border)'}`,
            background: lookback === d ? 'var(--t-bg3)' : 'transparent',
            color: lookback === d ? 'var(--t-blue)' : 'var(--t-dim)',
          }}>{lbl}</button>
        ))}
        <input type="number" value={lookback} min={14} max={1095}
          onChange={(e) => setLookback(Math.min(1095, Math.max(14, parseInt(e.target.value) || 365)))}
          style={{ width: 56, background: 'var(--t-bg)', border: '1px solid var(--t-border)', borderRadius: 4, color: 'var(--t-bright)', fontFamily: 'inherit', fontSize: 10, padding: '2px 5px', textAlign: 'right' }} />
        <span style={dim}>d</span>
        <button disabled={bt.isPending} onClick={() => bt.mutate({ underlying, lookback_days: lookback })} style={{
          fontSize: 9, fontWeight: 700, padding: '3px 10px', borderRadius: 4, fontFamily: 'inherit', cursor: 'pointer',
          border: '1px solid var(--t-blue)', background: 'var(--t-bg3)', color: 'var(--t-blue)',
        }}>{bt.isPending ? 'RUNNING…' : 'RUN'}</button>
      </span>
    }>
      {bt.isError && <div style={{ color: 'var(--t-red)', fontSize: 10 }}>{bt.error.message}</div>}
      {!res && !bt.isPending && <div style={dim}>Run a backtest over {underlying} — up to 3 years of stored 1H candles (≈2y available).</div>}
      {res && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Pill text={`${res.asset_class}`} color="var(--t-blue)" />
            <span style={dim}>{res.bars_evaluated} bars · {res.stats.long_trades}L / {res.stats.short_trades}S</span>
            <span style={{ marginLeft: 'auto' }}><EquitySpark curve={res.equity_curve} /></span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
            {statTiles(res.stats).map(([k, v, c]) => (
              <div key={k} style={{ background: 'var(--t-bg)', borderRadius: 6, padding: '6px 8px' }}>
                <div style={{ fontSize: 9, color: 'var(--t-dim)' }}>{k}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: c }}>{v}</div>
              </div>
            ))}
          </div>
          {res.trades.length > 0 && (
            <div style={{ maxHeight: 180, overflow: 'auto', border: '1px solid var(--t-border)', borderRadius: 6 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
                <thead>
                  <tr style={{ color: 'var(--t-dim)', textAlign: 'left' }}>
                    {['Dir', 'Entry', 'Exit', 'Bars', 'R', 'Exit reason'].map((h) => (
                      <th key={h} style={{ padding: '4px 8px', position: 'sticky', top: 0, background: 'var(--t-bg2)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {res.trades.slice(-40).reverse().map((t, i) => (
                    <tr key={i} style={{ borderTop: '1px solid var(--t-border)' }}>
                      <td style={{ padding: '3px 8px', color: t.direction === 'long' ? 'var(--t-green)' : 'var(--t-red)' }}>{t.direction === 'long' ? 'L' : 'S'}</td>
                      <td style={{ padding: '3px 8px', color: 'var(--t-dim)' }}>{fmtUsd(t.entry_price)}</td>
                      <td style={{ padding: '3px 8px', color: 'var(--t-dim)' }}>{fmtUsd(t.exit_price)}</td>
                      <td style={{ padding: '3px 8px', color: 'var(--t-dim)' }}>{t.bars_held}</td>
                      <td style={{ padding: '3px 8px', color: t.pnl_r >= 0 ? 'var(--t-green)' : 'var(--t-red)' }}>{fmt(t.pnl_r, 2)}</td>
                      <td style={{ padding: '3px 8px', color: 'var(--t-dim)' }}>{t.exit_reasons[t.exit_reasons.length - 1]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </SectionCard>
  );
}

/* ── signals scanner (primary view — all crypto) ──────────────────────────── */

function ConsensusChip({ count }: { count: number }) {
  const color = count >= 3 ? 'var(--t-green)' : count === 2 ? 'var(--t-amber)' : 'var(--t-dim)';
  return (
    <span style={{ display: 'inline-flex', gap: 2 }}>
      {[0, 1, 2].map((k) => (
        <span key={k} style={{ width: 6, height: 12, borderRadius: 2, background: k < count ? color : 'var(--t-border)' }} />
      ))}
    </span>
  );
}

function QualityMini({ total, pass }: { total: number; pass: boolean }) {
  const pct = Math.max(0, Math.min(100, (total / 112) * 100));
  const color = pass ? 'var(--t-green)' : total >= 50 ? 'var(--t-amber)' : 'var(--t-dim)';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span style={{ width: 44, height: 6, borderRadius: 3, background: 'var(--t-bg)', display: 'inline-block', overflow: 'hidden' }}>
        <span style={{ display: 'block', height: '100%', width: `${pct}%`, background: color }} />
      </span>
      <span style={{ fontSize: 11, fontWeight: 700, color }}>{Math.round(total)}</span>
    </span>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: 8.5, letterSpacing: '0.06em', color: 'var(--t-dim)' }}>{label}</div>
      <div style={{ fontSize: 12, fontWeight: 700, color: color || 'var(--t-bright)' }}>{value}</div>
    </div>
  );
}

function SignalCard({ s, selected, onSelect, onExecute, executing, result }: {
  s: SignalSummary; selected: boolean; onSelect: () => void; onExecute: () => void;
  executing: boolean; result: string | null;
}) {
  const long = s.direction === 'long';
  const short = s.direction === 'short';
  const dirColor = long ? 'var(--t-green)' : short ? 'var(--t-red)' : 'var(--t-dim)';
  return (
    <div onClick={onSelect} style={{
      display: 'flex', borderRadius: 10, overflow: 'hidden', cursor: 'pointer',
      border: `1px solid ${selected ? dirColor + '66' : 'var(--t-border)'}`,
      background: s.entry_ok ? dirColor + '0e' : 'var(--t-bg2)',
      transition: 'border-color .1s',
    }}>
      <div style={{ width: 4, background: dirColor, flexShrink: 0 }} />
      <div style={{ flex: 1, padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 9, minWidth: 0 }}>
        {/* row 1 — identity + state */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--t-bright)', minWidth: 42 }}>{s.underlying}</span>
          <span style={{ fontSize: 12, color: 'var(--t-dim)' }}>{fmtUsd(s.close)}</span>
          <span style={{ fontSize: 11, fontWeight: 800, color: dirColor, letterSpacing: '0.04em' }}>
            {long ? '▲ LONG' : short ? '▼ SHORT' : '— FLAT'}
          </span>
          {s.entry_ok && <Pill text="ARMED" color={dirColor} />}
          {s.arrow && <Pill text="✦ FLIP" color="var(--t-amber)" />}
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={dim}>ST</span><ConsensusChip count={s.consensus_count} /></span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={dim}>Q</span><QualityMini total={s.quality_total} pass={s.quality_pass} /></span>
            <Pill text={s.regime_label} color="#7da7ff" />
          </span>
        </div>
        {/* row 2 — plan + execute */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          {s.entry != null ? (
            <div style={{ display: 'flex', gap: 20, flex: 1, flexWrap: 'wrap' }}>
              <Stat label="ENTRY" value={fmtUsd(s.entry)} />
              <Stat label="STOP" value={fmtUsd(s.stop_loss)} color="var(--t-red)" />
              <Stat label="TARGET" value={fmtUsd(s.take_profit)} color="var(--t-green)" />
              <Stat label="R:R" value={s.rr != null ? `${fmt(s.rr, 1)}` : '—'} />
              <Stat label="LEV" value={s.leverage != null ? `${fmt(s.leverage, 1)}x` : '—'} />
            </div>
          ) : (
            <div style={{ flex: 1, fontSize: 10, color: 'var(--t-dim)' }}>{s.reason}</div>
          )}
          <button
            disabled={!s.executable || executing}
            onClick={(e) => { e.stopPropagation(); onExecute(); }}
            title={s.executable
              ? (s.entry_ok ? 'Armed — execute via current Paper/Live mode' : `Manual (discretionary) execute — ${s.reason}`)
              : s.reason}
            style={{
              fontSize: 11, fontWeight: 800, letterSpacing: '0.06em', padding: '7px 18px', borderRadius: 7,
              fontFamily: 'inherit', flexShrink: 0,
              color: !s.executable ? 'var(--t-dim)' : s.entry_ok ? '#fff' : dirColor,
              cursor: s.executable && !executing ? 'pointer' : 'default',
              border: s.executable && !s.entry_ok ? `1px solid ${dirColor}` : '1px solid transparent',
              background: !s.executable ? 'var(--t-border)' : s.entry_ok ? dirColor : 'transparent',
              opacity: s.executable ? 1 : 0.5,
            }}
          >
            {executing ? '…' : 'EXECUTE'}
          </button>
        </div>
        {result && <div style={{ fontSize: 10, color: result.startsWith('✓') ? 'var(--t-green)' : 'var(--t-amber)' }}>{result}</div>}
        {!s.entry_ok && s.entry != null && (
          <div style={{ fontSize: 9.5, color: 'var(--t-dim)' }}>{s.reason}</div>
        )}
      </div>
    </div>
  );
}

function SummaryTile({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: 'var(--t-bg)', border: '1px solid var(--t-border)', borderRadius: 8, padding: '7px 12px', minWidth: 78 }}>
      <div style={{ fontSize: 9, letterSpacing: '0.06em', color: 'var(--t-dim)' }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 800, color: color || 'var(--t-bright)' }}>{value}</div>
    </div>
  );
}

function SignalsScanner({ selected, onSelect, onOpenSettings, mode }: {
  selected: string; onSelect: (s: string) => void; onOpenSettings: () => void; mode?: string;
}) {
  const [armedOnly, setArmedOnly] = useState(false);
  const scanQ = useStrategySignals(armedOnly);
  const exec = useStrategyExecute();
  const [execSym, setExecSym] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, string>>({});

  const onExecute = (sym: string) => {
    setExecSym(sym);
    exec.mutate({ underlying: sym }, {
      onSuccess: (r) => { setResults((m) => ({ ...m, [sym]: `${r.accepted ? '✓' : '✕'} ${r.mode.toUpperCase()} ${r.status} — ${r.reason}${r.paper_position_id ? ` (#${r.paper_position_id})` : r.order_id ? ` (${r.order_id})` : ''}` })); setExecSym(null); },
      onError: (e) => { setResults((m) => ({ ...m, [sym]: `✕ ${e.message}` })); setExecSym(null); },
    });
  };

  const data = scanQ.data;
  const longs = data?.signals.filter((s) => s.direction === 'long').length ?? 0;
  const shorts = data?.signals.filter((s) => s.direction === 'short').length ?? 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* hero header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: '0.08em', color: 'var(--t-bright)' }}>TRIPLE SUPERTREND</div>
          <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 2 }}>
            Live signals across all crypto{mode ? ` · ${mode} mode` : ''} · {scanQ.isFetching ? 'scanning…' : 'auto-refresh 30s'}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={() => setArmedOnly((v) => !v)} style={{
            fontSize: 10, fontWeight: 700, padding: '6px 12px', borderRadius: 7, fontFamily: 'inherit', cursor: 'pointer',
            border: `1px solid ${armedOnly ? 'var(--t-green)' : 'var(--t-border)'}`,
            background: armedOnly ? 'var(--t-green)1c' : 'transparent',
            color: armedOnly ? 'var(--t-green)' : 'var(--t-dim)',
          }}>{armedOnly ? '● ARMED ONLY' : '○ ARMED ONLY'}</button>
          <button onClick={onOpenSettings} title="Strategy settings & backtest" style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', padding: '6px 14px', borderRadius: 7, fontFamily: 'inherit',
            cursor: 'pointer', border: '1px solid var(--t-blue)', background: 'var(--t-bg3)', color: 'var(--t-blue)',
          }}>⚙ SETTINGS</button>
        </div>
      </div>

      {/* summary tiles */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <SummaryTile label="ARMED" value={String(data?.armed_count ?? '–')} color={(data?.armed_count ?? 0) > 0 ? 'var(--t-green)' : 'var(--t-bright)'} />
        <SummaryTile label="SCANNED" value={String(data?.count ?? '–')} />
        <SummaryTile label="LONG" value={String(longs)} color="var(--t-green)" />
        <SummaryTile label="SHORT" value={String(shorts)} color="var(--t-red)" />
      </div>

      {scanQ.isError && <div style={{ color: 'var(--t-red)', fontSize: 11 }}>{(scanQ.error as Error).message}</div>}
      {scanQ.isLoading && <div style={dim}>scanning instruments…</div>}
      {data && data.signals.length === 0 && (
        <div style={{ ...dim, padding: '20px 0', textAlign: 'center' }}>
          {armedOnly ? 'No armed signals right now — toggle off to see all leans.' : 'No instruments available on this data source.'}
        </div>
      )}

      {/* signal cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {data?.signals.map((s) => (
          <SignalCard
            key={s.underlying} s={s}
            selected={selected === s.underlying}
            onSelect={() => onSelect(s.underlying)}
            onExecute={() => onExecute(s.underlying)}
            executing={execSym === s.underlying}
            result={results[s.underlying] ?? null}
          />
        ))}
      </div>

      {data && data.signals.length > 0 && (
        <div style={{ fontSize: 9, color: 'var(--t-dim)', lineHeight: 1.5 }}>
          EXECUTE routes through your current Paper/Live mode (top-right toggle). <b>Solid</b> = armed (auto-qualified);
          <b> outlined</b> = manual/discretionary (consensus or a filter not fully met). Disabled only when capital protection halts trading.
        </div>
      )}
    </div>
  );
}

/* ── main tab + advanced drawer ───────────────────────────────────────────── */

export function StrategyTab() {
  const selected = useSelectedUnderlying();
  const setSelected = useSetSelectedUnderlying();
  const cfgQ = useStrategyConfig();
  const setCfg = useSetStrategyConfig();
  const [drawer, setDrawer] = useState(false);
  const cfg = cfgQ.data?.config;

  // Lock body scroll while the drawer is open.
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setDrawer(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawer]);

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '14px 16px' }}>
      <SignalsScanner selected={selected} onSelect={setSelected} onOpenSettings={() => setDrawer(true)} mode={cfg?.mode} />

      {/* Advanced settings — right-side slide-out drawer */}
      {drawer && (
        <div
          onClick={() => setDrawer(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.62)', zIndex: 3000, display: 'flex', justifyContent: 'flex-end' }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 'min(580px, 94vw)', height: '100%', background: 'var(--t-bg)',
              borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column',
              boxShadow: '-8px 0 32px rgba(0,0,0,0.4)',
            }}
          >
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '12px 16px', borderBottom: '1px solid var(--t-border)', background: 'var(--t-bg2)', flexShrink: 0,
            }}>
              <span style={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.12em', color: 'var(--t-bright)' }}>STRATEGY · ADVANCED</span>
              <button onClick={() => setDrawer(false)} title="Close (Esc)" style={{
                background: 'none', border: 'none', color: 'var(--t-dim)', cursor: 'pointer', fontSize: 20, lineHeight: 1, padding: 0,
              }}>×</button>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {cfg && <ConfigPanel cfg={cfg} onSave={(c) => setCfg.mutate(c)} saving={setCfg.isPending} />}
              {cfgQ.isLoading && <div style={dim}>loading config…</div>}
              <BacktestPanel underlying={selected} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default StrategyTab;
