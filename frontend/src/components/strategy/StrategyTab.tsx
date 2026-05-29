import React, { useEffect, useState } from 'react';
import { useSelectedUnderlying, useSetSelectedUnderlying } from '../../store/useStore';
import {
  useStrategyConfig, useSetStrategyConfig, useStrategyUniverse, useStrategyHistory,
  useStrategyBacktest, useStrategyExecute, useStrategySignals,
  type TripleSTConfig, type BacktestResult, type SignalSummary,
} from '../../hooks/useStrategy';
import { card, cardHead, cardBody, grpBox, grpTitle, chipStyle, gridStyle, tint } from '../../styles/terminalUI';
import { DerivativesCandidatesTable } from '../derivatives/DerivativesCandidatesTable';
import { DerivativesPanel } from '../derivatives/DerivativesPanel';
import { DerivativesSettingsButton } from '../derivatives/DerivativesSettingsButton';

/* ── tiny style helpers ───────────────────────────────────────────────────── */
/* card / cardHead / cardBody / grpBox / grpTitle come from the shared
 * terminalUI module so this tab matches ScalpingTab exactly. */

const dim: React.CSSProperties = { color: 'var(--t-dim)', fontSize: 10 };

function SectionCard({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={card}>
      <div style={cardHead}><span>{title}</span>{right && <span style={{ marginLeft: 'auto' }}>{right}</span>}</div>
      <div style={cardBody}>{children}</div>
    </div>
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
const fmtDate = (ms: number) => new Date(ms).toISOString().slice(0, 10);

/* ── config panel (slim — just the new strategy's knobs) ──────────────────── */

function ChipToggle({ label, on, onChange }: { label: string; on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!on)} style={{
      fontSize: 10, fontWeight: 600, padding: '4px 9px', borderRadius: 13, cursor: 'pointer', fontFamily: 'inherit',
      border: `1px solid ${on ? 'var(--t-green)' : 'var(--t-border)'}`,
      background: on ? tint('var(--t-green)') : 'transparent',
      color: on ? 'var(--t-green)' : 'var(--t-dim)', transition: 'all .1s', whiteSpace: 'nowrap',
    }}>{on ? '● ' : '○ '}{label}</button>
  );
}

function ConfigPanel({ cfg, onSave, saving }: { cfg: TripleSTConfig; onSave: (c: TripleSTConfig) => void; saving: boolean }) {
  const [draft, setDraft] = useState<TripleSTConfig>(cfg);
  useEffect(() => { setDraft(cfg); }, [cfg]);
  const set = <K extends keyof TripleSTConfig>(k: K, v: TripleSTConfig[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const dirty = JSON.stringify(draft) !== JSON.stringify(cfg);

  const universeQ = useStrategyUniverse();
  const universe = universeQ.data?.symbols ?? [];
  const allMode = draft.symbols.length === 0;          // [] = scan everything
  const selSet = new Set(draft.symbols);
  const toggleSym = (s: string) => setDraft((d) => {
    const cur = new Set(d.symbols);
    if (cur.has(s)) cur.delete(s); else cur.add(s);
    return { ...d, symbols: [...cur] };
  });

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
      <div style={{ ...dim, marginBottom: 10, lineHeight: 1.5 }}>
        Daily RSI(2) mean-reversion — <b style={{ color: 'var(--t-bright)' }}>Long</b>: close&gt;SMA(trend) &amp;
        RSI&lt;{draft.rsi_oversold}, exit RSI&gt;{draft.rsi_exit}. <b style={{ color: 'var(--t-bright)' }}>Short</b>: the
        mirror (unvalidated).
      </div>
      <div style={gridStyle()}>
        {/* Trend & RSI */}
        <div style={grpBox}>
          <div style={grpTitle}>TREND &amp; RSI</div>
          <NumField label="Trend SMA period" value={draft.trend_sma_period} min={20} max={400} onChange={(v) => set('trend_sma_period', v)} />
          <NumField label="RSI period" value={draft.rsi_period} min={1} max={50} onChange={(v) => set('rsi_period', v)} />
          <NumField label="RSI oversold (buy <)" value={draft.rsi_oversold} step={1} min={1} max={49} onChange={(v) => set('rsi_oversold', v)} />
          <NumField label="RSI exit (sell >)" value={draft.rsi_exit} step={1} min={50} max={99} onChange={(v) => set('rsi_exit', v)} />
          <NumField label="ATR period (stop)" value={draft.atr_period} min={2} max={100} onChange={(v) => set('atr_period', v)} />
        </div>

        {/* Direction */}
        <div style={grpBox}>
          <div style={grpTitle}>DIRECTION</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            <ChipToggle label="Long" on={draft.allow_long} onChange={(v) => set('allow_long', v)} />
            <ChipToggle label="Short (mirror)" on={draft.allow_short} onChange={(v) => set('allow_short', v)} />
          </div>
          <NumField label="Warm-up (daily bars)" value={draft.warmup_bars} min={20} max={420} onChange={(v) => set('warmup_bars', v)} />
        </div>

        {/* Risk */}
        <div style={grpBox}>
          <div style={grpTitle}>RISK &amp; SIZING</div>
          <NumField label="Risk % / trade" value={draft.risk_percent} step={0.05} min={0.05} max={5} onChange={(v) => set('risk_percent', v)} />
          <NumField label="Stop ATR ×" value={draft.sl_atr_mult} step={0.1} min={0.5} max={10} onChange={(v) => set('sl_atr_mult', v)} />
          <NumField label="Max position %" value={draft.max_position_pct} step={1} min={1} max={100} onChange={(v) => set('max_position_pct', v)} />
          <NumField label="Max slippage %" value={draft.max_slippage} step={0.1} min={0} max={5} onChange={(v) => set('max_slippage', v)} />
          <NumField label="Account equity $" value={draft.account_equity} step={1000} min={100} onChange={(v) => set('account_equity', v)} />
        </div>
      </div>

      {/* Symbols — scanner allowlist ([] = all) */}
      <div style={{ ...grpBox, marginTop: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={grpTitle}>SYMBOLS</span>
          <span style={{ fontSize: 9, color: 'var(--t-dim)' }}>
            {allMode ? `scanning all ${universe.length}` : `${draft.symbols.length} selected`}
          </span>
          <button onClick={() => set('symbols', [] as string[])} style={{
            fontSize: 9, fontWeight: 700, padding: '2px 9px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit',
            border: `1px solid ${allMode ? 'var(--t-blue)' : 'var(--t-border)'}`,
            background: allMode ? 'var(--t-bg3)' : 'transparent',
            color: allMode ? 'var(--t-blue)' : 'var(--t-dim)',
          }}>ALL</button>
          <span style={{ fontSize: 9, color: 'var(--t-dim)', marginLeft: 'auto' }}>
            {allMode ? 'click coins to scan only those' : 'ALL clears the filter'}
          </span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 150, overflow: 'auto' }}>
          {universe.map((s) => {
            const on = !allMode && selSet.has(s);
            return (
              <button key={s} onClick={() => toggleSym(s)} style={chipStyle(on)}>{s}</button>
            );
          })}
          {universe.length === 0 && <span style={dim}>{universeQ.isLoading ? 'loading universe…' : 'no symbols available'}</span>}
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
    ['Avg hold', `${fmt(s.avg_bars_held, 0)}d`, 'var(--t-bright)'],
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
      {!res && !bt.isPending && <div style={dim}>Run a backtest over {underlying} — daily bars resampled from up to 3 years of stored history (≈2y available).</div>}
      {res && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Pill text="1D" color="var(--t-blue)" />
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
                    {['Dir', 'Entry', 'Exit', 'Days', 'R', 'Exit'].map((h) => (
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
                      <td style={{ padding: '3px 8px', color: 'var(--t-dim)' }}>{t.exit_reason}</td>
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

function Cond({ label, value, against, gt, usd }: { label: string; value: number; against: number; gt: boolean; usd?: boolean }) {
  const color = gt ? 'var(--t-green)' : 'var(--t-red)';
  const f = (v: number) => (usd ? fmtUsd(v) : fmt(v, 0));
  return (
    <div title={`${label}: ${f(value)} ${gt ? '>' : '<'} ${f(against)}`}>
      <div style={{ fontSize: 8.5, letterSpacing: '0.04em', color: 'var(--t-dim)' }}>{label}</div>
      <div style={{ fontSize: 11, fontWeight: 700, color }}>
        {gt ? '▲' : '▼'} {f(value)} <span style={{ color: 'var(--t-dim)', fontWeight: 400 }}>{gt ? '>' : '<'}</span> {f(against)}
      </div>
    </div>
  );
}

function RsiChip({ rsi, oversold, exit, triggered }: { rsi: number; oversold: number; exit: number; triggered: boolean }) {
  // Color by proximity to the oversold (buy) trigger so near-signals stand out.
  const near = rsi <= oversold * 2;   // within 2× of the trigger → warming up
  const color = triggered ? 'var(--t-green)' : rsi > exit ? 'var(--t-red)' : near ? 'var(--t-amber)' : 'var(--t-dim)';
  return (
    <div title={`RSI ${fmt(rsi, 1)} — buy < ${oversold}, exit > ${exit}`}>
      <div style={{ fontSize: 8.5, letterSpacing: '0.04em', color: 'var(--t-dim)' }}>RSI · buy&lt;{fmt(oversold, 0)}</div>
      <div style={{ fontSize: 11, fontWeight: 700, color }}>{triggered ? '▼ ' : ''}{fmt(rsi, 0)}</div>
    </div>
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
  // Eligible-but-flat: in an uptrend, just waiting for RSI to dip oversold.
  const watching = !long && !short && s.in_uptrend;
  const dirColor = long ? 'var(--t-green)' : short ? 'var(--t-red)' : 'var(--t-dim)';
  // Accent reflects regime so a flat board still reads at a glance.
  const accent = long ? 'var(--t-green)' : short ? 'var(--t-red)' : watching ? 'var(--t-blue)' : 'var(--t-dim)';
  return (
    <div onClick={onSelect} style={{
      display: 'flex', borderRadius: 8, overflow: 'hidden', cursor: 'pointer',
      border: `1px solid ${selected ? tint(accent, 45) : 'var(--t-border)'}`,
      background: s.entry_ok ? tint(accent, 7) : watching ? tint('var(--t-blue)', 6) : 'var(--t-bg2)',
      transition: 'border-color .1s',
    }}>
      <div style={{ width: 4, background: accent, flexShrink: 0 }} />
      <div style={{ flex: 1, padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 9, minWidth: 0 }}>
        {/* row 1 — identity + conditions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--t-bright)', minWidth: 42 }}>{s.underlying}</span>
          <span style={{ fontSize: 12, color: 'var(--t-dim)' }}>{fmtUsd(s.close)}</span>
          <span style={{ fontSize: 11, fontWeight: 800, color: accent, letterSpacing: '0.04em' }}>
            {long ? '▲ LONG' : short ? '▼ SHORT' : watching ? '○ WATCH' : '— FLAT'}
          </span>
          {s.entry_ok && <Pill text="ARMED" color={dirColor} />}
          {watching && <Pill text="UPTREND" color="var(--t-blue)" />}
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap' }}>
            <Cond label="CLOSE / SMA200" value={s.close} against={s.sma} gt={s.in_uptrend} usd />
            <RsiChip rsi={s.rsi} oversold={s.rsi_oversold} exit={s.rsi_exit} triggered={s.oversold} />
          </span>
        </div>
        {/* row 2 — plan + execute */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          {s.entry != null ? (
            <div style={{ display: 'flex', gap: 20, flex: 1, flexWrap: 'wrap' }}>
              <Stat label="ENTRY" value={fmtUsd(s.entry)} />
              <Stat label="STOP" value={fmtUsd(s.stop_loss)} color="var(--t-red)" />
              <Stat label="EXIT" value={`RSI>${fmt(s.rsi_exit, 0)}`} color="var(--t-amber)" />
              <Stat label="RISK" value={s.risk_pct != null ? `${fmt(s.risk_pct, 2)}%` : '—'} />
              <Stat label="LEV" value={s.leverage != null ? `${fmt(s.leverage, 1)}x` : '—'} />
            </div>
          ) : (
            <div style={{ flex: 1, fontSize: 10, color: 'var(--t-dim)' }}>{s.reason}</div>
          )}
          <button
            disabled={!s.executable || executing}
            onClick={(e) => { e.stopPropagation(); onExecute(); }}
            title={s.executable ? 'Armed — execute via current Paper/Live mode' : s.reason}
            style={{
              fontSize: 11, fontWeight: 800, letterSpacing: '0.06em', padding: '7px 18px', borderRadius: 7,
              fontFamily: 'inherit', flexShrink: 0,
              color: !s.executable ? 'var(--t-dim)' : '#fff',
              cursor: s.executable && !executing ? 'pointer' : 'default',
              border: '1px solid transparent',
              background: !s.executable ? 'var(--t-border)' : dirColor,
              opacity: s.executable ? 1 : 0.5,
            }}
          >
            {executing ? '…' : 'EXECUTE'}
          </button>
        </div>
        {!s.executable && s.entry != null && (
          <div style={{ fontSize: 9.5, color: 'var(--t-dim)' }}>{s.reason}</div>
        )}
        {result && <div style={{ fontSize: 10, color: result.startsWith('✓') ? 'var(--t-green)' : 'var(--t-amber)' }}>{result}</div>}
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

function RecentSignals() {
  const [open, setOpen] = useState(false);
  const q = useStrategyHistory(open);   // lazy: only fetches once expanded
  const d = q.data;
  return (
    <div style={card}>
      <button onClick={() => setOpen((o) => !o)} style={{
        ...cardHead, width: '100%', border: 'none', background: 'none', cursor: 'pointer', fontFamily: 'inherit',
      }}>
        <span>{open ? '▾' : '▸'} RECENT SIGNALS</span>
        <span style={{ marginLeft: 8, color: 'var(--t-dim)', fontWeight: 400 }}>
          {d ? `${d.count} trades · ${Math.round(d.win_rate * 100)}% win · last 12m` : 'last 12 months'}
        </span>
      </button>
      {open && (
        <div style={cardBody}>
          {q.isLoading && <div style={dim}>computing history across the universe… (~10s, then cached)</div>}
          {q.isError && <div style={{ color: 'var(--t-red)', fontSize: 10 }}>{(q.error as Error).message}</div>}
          {d && d.trades.length === 0 && <div style={dim}>No completed trades in the window.</div>}
          {d && d.trades.length > 0 && (
            <div style={{ maxHeight: 280, overflow: 'auto', border: '1px solid var(--t-border)', borderRadius: 6 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
                <thead>
                  <tr style={{ color: 'var(--t-dim)', textAlign: 'left' }}>
                    {['Entry', 'Symbol', 'Dir', 'Entry $', 'Exit $', 'Held', 'R', 'Exit'].map((h) => (
                      <th key={h} style={{ padding: '4px 8px', position: 'sticky', top: 0, background: 'var(--t-bg2)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {d.trades.map((t, i) => (
                    <tr key={i} style={{ borderTop: '1px solid var(--t-border)' }}>
                      <td style={{ padding: '3px 8px', color: 'var(--t-dim)' }}>{fmtDate(t.entry_ts)}</td>
                      <td style={{ padding: '3px 8px', fontWeight: 700, color: 'var(--t-bright)' }}>{t.underlying}</td>
                      <td style={{ padding: '3px 8px', color: t.direction === 'long' ? 'var(--t-green)' : 'var(--t-red)' }}>{t.direction === 'long' ? 'L' : 'S'}</td>
                      <td style={{ padding: '3px 8px', color: 'var(--t-dim)' }}>{fmtUsd(t.entry_price)}</td>
                      <td style={{ padding: '3px 8px', color: 'var(--t-dim)' }}>{fmtUsd(t.exit_price)}</td>
                      <td style={{ padding: '3px 8px', color: 'var(--t-dim)' }}>{t.bars_held}d</td>
                      <td style={{ padding: '3px 8px', fontWeight: 700, color: t.pnl_r >= 0 ? 'var(--t-green)' : 'var(--t-red)' }}>{t.pnl_r >= 0 ? '+' : ''}{fmt(t.pnl_r, 2)}</td>
                      <td style={{ padding: '3px 8px', color: 'var(--t-dim)' }}>{t.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SignalsScanner({ selected, onSelect, onOpenSettings }: {
  selected: string; onSelect: (s: string) => void; onOpenSettings: () => void;
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
  const shorts = data?.signals.filter((s) => s.direction === 'short').length ?? 0;
  // Eligible coins in an uptrend, waiting for RSI to dip oversold (the live watchlist).
  const watching = data?.signals.filter((s) => s.in_uptrend && !s.entry_ok).length ?? 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Controls row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={() => setArmedOnly((v) => !v)} style={{
          fontSize: 10, fontWeight: 700, padding: '5px 12px', borderRadius: 6, fontFamily: 'inherit', cursor: 'pointer',
          border: `1px solid ${armedOnly ? 'var(--t-green)' : 'var(--t-border)'}`,
          background: armedOnly ? tint('var(--t-green)') : 'transparent',
          color: armedOnly ? 'var(--t-green)' : 'var(--t-dim)',
        }}>{armedOnly ? '● ARMED ONLY' : '○ ARMED ONLY'}</button>
        <button onClick={onOpenSettings} title="Strategy settings & backtest" style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', padding: '5px 12px', borderRadius: 6, fontFamily: 'inherit',
          cursor: 'pointer', border: '1px solid var(--t-blue)', background: 'var(--t-bg3)', color: 'var(--t-blue)',
        }}>⚙ SETTINGS</button>
        <DerivativesSettingsButton onClick={onOpenSettings} />
      </div>

      {/* summary tiles */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <SummaryTile label="ARMED" value={String(data?.armed_count ?? '–')} color={(data?.armed_count ?? 0) > 0 ? 'var(--t-green)' : 'var(--t-bright)'} />
        <SummaryTile label="WATCHING" value={String(watching)} color={watching > 0 ? 'var(--t-blue)' : 'var(--t-bright)'} />
        <SummaryTile label="SCANNED" value={String(data?.count ?? '–')} />
        {shorts > 0 && <SummaryTile label="SHORT" value={String(shorts)} color="var(--t-red)" />}
      </div>

      {scanQ.isError && <div style={{ color: 'var(--t-red)', fontSize: 11 }}>{(scanQ.error as Error).message}</div>}
      {scanQ.isLoading && <div style={dim}>scanning…</div>}
      {data && data.signals.length === 0 && (
        <div style={{ ...dim, padding: '20px 0', textAlign: 'center' }}>
          {armedOnly ? 'No armed signals — toggle off to see all.' : 'No instruments on this data source.'}
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

      {/* recent signal history */}
      <RecentSignals />

      {/* Derivatives candidates table — populated by selector when triple_st profile.enabled */}
      <DerivativesCandidatesTable strategy="triple_st" />


      {data && data.signals.length > 0 && (
        <div style={{ fontSize: 9, color: 'var(--t-dim)', lineHeight: 1.5 }}>
          EXECUTE routes through Paper/Live mode. A symbol is <b>ARMED</b> when price is in an uptrend and RSI(2) is oversold.
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

  // Close the drawer on Escape.
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setDrawer(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawer]);

  return (
    <div style={{ flex: 1, overflow: 'visible', padding: 0 }}>
      <SignalsScanner selected={selected} onSelect={setSelected} onOpenSettings={() => setDrawer(true)} />

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
              <DerivativesPanel strategy="triple_st" />
              <BacktestPanel underlying={selected} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default StrategyTab;
