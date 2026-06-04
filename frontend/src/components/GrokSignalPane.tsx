import React, { useState, useEffect, useRef } from 'react';
import { card, cardHead, cardBody, alpha, c } from '../styles/terminalUI';
import { useSignals, SignalItem } from '../hooks/useSignals';
import { useAlgoMode, useSetAlgoMode, usePlaceOrder } from '../hooks/useSignalAlerts';
import { useRouterMode, RouterMode } from '../hooks/useRouterMode';
import { useLivePnl } from '../hooks/useLivePnl';
import { usePositions } from '../hooks/usePositions';
import { FuturesCandidatesTable } from './derivatives/FuturesCandidatesTable';
import { OptionsCandidatesTable } from './derivatives/OptionsCandidatesTable';

// Copy required styles & utilities
const fmtUsd = (v: number | null | undefined): string => v == null || !isFinite(v) ? '—' : '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 });
const fmtTime = (ms: number) => new Date(ms).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
const modeColorOf = (m: string) => m.toUpperCase() === 'LIVE' ? 'var(--t-red)' : m.toUpperCase() === 'SHADOW' ? 'var(--t-amber)' : 'var(--t-blue)';
const fmt = (v: number | null | undefined, d = 2): string => v == null || !isFinite(v) ? '—' : v.toFixed(d);
const fmtSigned = (v: number | null | undefined): string => {
  if (v == null || !isFinite(v)) return '—';
  return v >= 0 ? `+${fmtUsd(v)}` : `−${fmtUsd(Math.abs(v))}`;
};

const MODE_HINT: Record<RouterMode, string> = {
  paper: 'Paper Trading — fills are simulated using live orderbook prices.',
  shadow: 'Shadow Execution — orders are placed and immediately cancelled to test API latency.',
  live: 'Real money — orders execute on the exchange.',
};

function MetricItem({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 60 }}>
      <span style={{ fontSize: 9, letterSpacing: '0.07em', color: 'var(--t-dim)', fontWeight: 600, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ fontSize: 11, fontWeight: 700, color: color || 'var(--t-bright)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{value}</span>
    </div>
  );
}

function ModeSelector({ mode, onChange }: { mode: RouterMode; onChange: (m: RouterMode) => void }) {
  const pick = (m: RouterMode) => { if (m !== mode) onChange(m); };
  return (
    <div style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 3, background: 'var(--t-bg2)', border: '1px solid var(--t-border)', borderRadius: 6, padding: 2 }}>
      {(['paper', 'shadow', 'live'] as RouterMode[]).map((m) => {
        const active = mode === m;
        const col = modeColorOf(m.toUpperCase());
        return (
          <button
            key={m} onClick={() => pick(m)} title={MODE_HINT[m]}
            style={{
              padding: '3px 10px', borderRadius: 4, cursor: active ? 'default' : 'pointer', fontFamily: 'inherit',
              fontSize: 9, fontWeight: active ? 700 : 500, letterSpacing: '0.08em', textTransform: 'uppercase',
              border: `1px solid ${active ? col + '88' : 'transparent'}`, background: active ? col + '20' : 'transparent',
              color: active ? col : 'var(--t-dim)', transition: 'all .12s',
            }}>
            {m === 'paper' ? '◐' : m === 'shadow' ? '◑' : '●'} {m}
          </button>
        );
      })}
    </div>
  );
}

function SectionCard({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={card}>
      <div style={cardHead}><span>{title}</span>{right && <span style={{ marginLeft: 'auto' }}>{right}</span>}</div>
      <div style={cardBody}>{children}</div>
    </div>
  );
}

export function GrokSignalPane({ trackFilter = 'all', statusFilter = 'all', profileFilter = 'all', logExec }: { trackFilter?: string; statusFilter?: string; profileFilter?: string; logExec?: (e: any) => void }) {
  const { data } = useSignals();
  const execute = usePlaceOrder();
  const algoMode = useAlgoMode();

  const algoOn = algoMode.data?.enabled ?? false;
  const routerModeObj = useRouterMode();
  const routerMode = routerModeObj.mode || 'paper';
  const livePnl = useLivePnl();
  const { data: posData } = usePositions();
  
  const [expanded, setExpanded] = useState<string>('');
  const autoExecRef = useRef<Set<string>>(new Set());
  const acceptedRef = useRef<Set<string>>(new Set());
  const activePositions = livePnl.data?.positions || [];
  const getSignalStatus = (s: any) => {
    if (activePositions.some((p: any) => p.underlying === s.underlying && p.direction === s.direction)) return 'open';
    if (s.direction === 'long' || s.direction === 'short') return 'ready';
    return 'idle';
  };

  let signals = data?.signals || [];
  if (trackFilter !== 'all') signals = signals.filter(s => s.track === trackFilter);
  if (profileFilter !== 'all') signals = signals.filter(s => (s.profile?.toLowerCase() || 'scalping') === profileFilter);
  if (statusFilter !== 'all') signals = signals.filter(s => getSignalStatus(s) === statusFilter);

  const handleExecute = async (s: SignalItem, auto: boolean = false) => {
    const key = `${s.underlying}-${s.direction}`;

    try {
      const resp = await execute.mutateAsync({
        underlying: s.underlying,
        direction: s.direction as any,
        instrument_type: "futures",
        size: 1.0,
        leverage: s.rec_leverage || 5.0,
        order_type: "market",
        stop_loss: s.stop_price,
        take_profit: s.target_price,
        notes: `[GROK] ${s.track || s.strategy || 'manual'}`,
      });
      if (logExec) logExec({ ts: Date.now(), key, mode: routerMode.toUpperCase(), ok: true, status: resp?.status || 'sent', reason: resp?.message || '', auto });
      acceptedRef.current.add(`${s.underlying}-${s.direction}`);

    } catch (e: any) {
      console.error(e);
      if (logExec) logExec({ ts: Date.now(), key, mode: routerMode.toUpperCase(), ok: false, status: 'error', reason: e.message, auto });
    }
  };

  useEffect(() => {
    if (!algoOn) {
      autoExecRef.current.clear();
      return;
    }
    for (const s of data?.signals ?? []) {
      if (getSignalStatus(s) !== 'ready') continue;
      const key = `${s.underlying}-${s.direction}`;
      if (acceptedRef.current.has(key)) continue;
      if (autoExecRef.current.has(key)) continue;
      autoExecRef.current.add(key);
      handleExecute(s, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [algoOn, data, routerMode]);

  useEffect(() => {
    // Clear accepted items that are no longer open (or failed previously)
    for (const key of acceptedRef.current) {
      const symbol = key.split('-')[0];
      const direction = key.split('-')[1];
      if (!activePositions.some((p: any) => p.underlying === symbol && p.direction === direction)) {
        acceptedRef.current.delete(key);
        autoExecRef.current.delete(key);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePositions]);


  const TABLE_COL_COUNT = 15;

  const filteredSignals = signals.filter(s => {
    if (['NIFTY', 'BANKNIFTY'].includes(s.underlying.toUpperCase())) return false;
    if (trackFilter !== 'all' && s.track !== trackFilter) return false;
    if (statusFilter !== 'all' && getSignalStatus(s) !== statusFilter) return false;
    if (profileFilter !== 'all' && (s.profile?.toLowerCase() || 'scalping') !== profileFilter) return false;
    return true;
  });

  let finalSignals = [...filteredSignals];
  const signalKeys = new Set(finalSignals.map(s => `${s.underlying}-${s.direction}`));

  const spotPositions = (posData?.positions || []).filter(p => {
    const st = livePnl.data?.positions.find(x => x.position_id === p.id)?.structure_type || p.sized_trade?.structure?.structure_type || '';
    if (st && st !== 'spot') return false;
    if (!p.notes?.includes('[GROK]')) return false;
    if (routerMode === 'live' && p.is_paper) return false;
    if (routerMode !== 'live' && !p.is_paper) return false;
    return true;
  });

  spotPositions.forEach(p => {
    const direction = p.sized_trade?.structure?.direction || 'long';
    const key = `${p.underlying}-${direction}`;
    if (!signalKeys.has(key)) {
      const match = (p.notes || '').match(/(?:scalping|edge|triple_st)\/[a-z_]+/);
      finalSignals.push({
        id: `pos-${p.id}`,
        source: 'GROK',
        strategy: (match ? match[0] : 'manual') as 'legacy' | 'latest' | undefined,
        track: 'unknown',
        profile: 'scalping',
        underlying: p.underlying,
        direction: direction.toUpperCase() as 'LONG' | 'SHORT',
        timestamp_ms: p.entry_timestamp_ms || Date.now(),
        entry_price: p.entry_spot_price || 0,
        target_price: p.initial_tp || 0,
        stop_loss: p.initial_sl || 0,
        expected_r: 0,
        reason: 'Restored from position history',
        status: p.status === 'closed' ? 'CLOSED' : 'OPEN'
      } as unknown as SignalItem);
      signalKeys.add(key);
    }
  });

  // Calculate stats strictly from the tracked spot positions
  const spotPnlStats = spotPositions.reduce((acc, p) => {
    if (p.status !== 'closed') {
      acc.count++;
    }
    const lp = livePnl.data?.positions.find(x => x.position_id === p.id);
    const val = p.status === 'closed' ? p.realized_pnl_usd : lp?.estimated_pnl_usd;
    if (val != null) {
      acc.total += val;
      if (p.status === 'closed') acc.totalRealized += val;
      else acc.totalUnrealized += val;
    }
    return acc;
  }, { count: 0, total: 0, totalUnrealized: 0, totalRealized: 0 });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
      <SectionCard 
        title="GROK ENGINE · SPOT" 
        right={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {algoOn && (
              <span style={{
                fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
                padding: '3px 9px', borderRadius: 5, whiteSpace: 'nowrap',
                background: alpha('var(--t-green)', 0.1), color: 'var(--t-green)', border: '1px solid var(--t-green)44',
              }}>⚡ ALGO AUTO-EXEC</span>
            )}
            <ModeSelector mode={routerMode} onChange={(m) => routerModeObj.setMode(m)} />
          </div>
        }
      >
        <table style={{ width: '100%', minWidth: 920, tableLayout: 'fixed', borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr style={{ background: c.surface, color: c.muted, fontSize: 9, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              {['Symbol', 'ID', 'Time', 'Status', 'Direction', 'Entry', 'Current', 'Dyn SL', 'Target', 'Spent', 'Risk', 'Strategy', 'P&L', 'Type', ''].map((h, i) => (
                <th key={i} style={{ padding: '5px 8px', textAlign: i >= 12 ? 'right' : 'left', borderBottom: `1px solid ${c.border}`, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {finalSignals.map((s) => {
              const sigIdStr = `${s.underlying}-${s.direction}`;
              const sigIdHash = Array.from(sigIdStr).reduce((h, ch) => Math.imul(31, h) + ch.charCodeAt(0) | 0, 0);
              const sigId = Math.abs(sigIdHash).toString(16).substring(0, 5).toUpperCase();
              
              const isExp = expanded === sigId;
              const long = s.direction === 'long';
              const short = s.direction === 'short';
              const dirColor = long ? 'var(--t-green)' : short ? 'var(--t-red)' : 'var(--t-dim)';
              
              const pnlData = livePnl.data?.positions.filter(p => {
                if (p.underlying !== s.underlying) return false;
                if (p.direction !== s.direction) return false;
                if (routerMode === 'live') return !p.is_paper;
                return p.is_paper;
              }) || [];
              const isExecuted = pnlData.length > 0;
              const pnl = pnlData[0] || null;
              
              const hasPlan = s.direction === 'long' || s.direction === 'short';
              const statusColor = isExecuted ? 'var(--t-blue)' : hasPlan ? dirColor : 'var(--t-dim)';
              const statusLabel = isExecuted ? 'OPEN' : hasPlan ? 'READY' : 'IDLE';

              return (
                <React.Fragment key={sigId}>
                  <tr onClick={() => setExpanded(isExp ? '' : sigId)} style={{ cursor: 'pointer', borderBottom: isExp ? 'none' : `1px solid ${c.border2}`, background: isExp ? alpha(statusColor, 0.09) : undefined }}>
                    <td style={{ padding: '5px 8px', fontWeight: 700, color: 'var(--t-bright)' }}>
                      <span style={{ color: dirColor }}>{long ? '▲' : short ? '▼' : '–'}</span> {s.underlying}
                    </td>
                    <td style={{ padding: '5px 8px', fontSize: 9, color: 'var(--t-dim)', fontFamily: 'monospace' }}>{sigId}</td>
                    <td style={{ padding: '5px 8px' }}>{fmtTime((isExecuted && pnl?.entry_timestamp_ms) ? pnl.entry_timestamp_ms : s.timestamp_ms)}</td>
                    <td style={{ padding: '5px 8px', fontWeight: 700, color: statusColor, fontSize: 10, letterSpacing: '0.06em' }}>{statusLabel}</td>
                    <td style={{ padding: '5px 8px', fontWeight: 600, color: dirColor }}>{long ? '▲ LONG' : short ? '▼ SHORT' : '—'}</td>
                    <td style={{ padding: '5px 8px' }}>
                      {(() => {
                        const entryPx = isExecuted && pnl ? (pnl.entry_price_real ?? pnl.entry_spot ?? s.spot_price) : s.spot_price;
                        return hasPlan ? fmtUsd(entryPx) : '—';
                      })()}
                    </td>
                    <td style={{ padding: '5px 8px' }}>
                      {(() => {
                        const entryPx = isExecuted && pnl ? (pnl.entry_price_real ?? pnl.entry_spot ?? s.spot_price) : s.spot_price;
                        const currPx = isExecuted && pnl ? (pnl.current_spot ?? s.spot_price) : s.spot_price;
                        if (!currPx) return '—';
                        if (!hasPlan || !entryPx) return fmtUsd(currPx);
                        
                        const diff = long ? (currPx - entryPx) : (entryPx - currPx);
                        const roundedDiff = parseFloat(diff.toFixed(1));
                        if (Math.abs(roundedDiff) === 0) return <span>{fmtUsd(currPx)}</span>;
                        
                        const sign = roundedDiff > 0 ? '+' : roundedDiff < 0 ? '−' : '';
                        const color = roundedDiff > 0 ? 'var(--t-green)' : 'var(--t-red)';
                        return (
                          <span style={{ color }}>
                            {fmtUsd(currPx)} <span style={{ fontSize: 11, opacity: 0.7, fontWeight: 400 }}>({sign}{Math.abs(roundedDiff).toFixed(1)})</span>
                          </span>
                        );
                      })()}
                    </td>
                    <td style={{ padding: '5px 8px', color: 'var(--t-red)' }}>
                      {(() => {
                        if (!hasPlan) return '—';
                        const initSl = isExecuted ? (pnl?.initial_sl ?? s.stop_price ?? 0) : (s.stop_price ?? 0);
                        const currSl = isExecuted ? pnl?.current_sl : null;
                        if (!currSl || currSl === initSl) {
                           return fmtUsd(initSl);
                        }
                        const diff = long ? (currSl - initSl) : (initSl - currSl);
                        const sign = diff >= 0 ? '+' : '';
                        return (
                          <span style={{ whiteSpace: 'nowrap' }}>
                            <del style={{ opacity: 0.5 }}>{fmtUsd(initSl)}</del>
                            <span style={{ fontSize: 11, marginLeft: 4, opacity: 0.8 }}>({sign}{diff.toFixed(1)})</span>
                          </span>
                        );
                      })()}
                    </td>
                    <td style={{ padding: '5px 8px', color: 'var(--t-amber)' }}>
                      {hasPlan ? fmtUsd(isExecuted && pnl?.current_tp ? pnl.current_tp : s.target_price) : '—'}
                    </td>
                    <td style={{ padding: '5px 8px', fontWeight: 600 }}>
                      {(() => {
                        if (!hasPlan) return '—';
                        const entryPx = isExecuted && pnl ? (pnl.entry_price_real ?? pnl.entry_spot ?? s.spot_price) : s.spot_price;
                        if (!entryPx) return '—';
                        const qty = pnl?.contracts || 1.0;
                        const lev = s.rec_leverage || 1.0;
                        return fmtUsd((entryPx * qty) / lev);
                      })()}
                    </td>
                    <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: 'var(--t-text)' }}>
                      {(() => {
                        if (!hasPlan) return '—';
                        if (pnl?.capital_at_risk_pct != null) return `${fmt(pnl.capital_at_risk_pct)}%`;
                        if (s.spot_price && s.stop_price) {
                           const risk = Math.abs(s.spot_price - s.stop_price) / s.spot_price * 100 * (s.rec_leverage || 1);
                           return `${fmt(risk)}%`;
                        }
                        return '—';
                      })()}
                    </td>
                    <td style={{ padding: '5px 8px', textTransform: 'uppercase', fontSize: 9 }}>
                      {s.strategy ? s.strategy.replace(/_/g, ' ') : '—'}
                    </td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', fontWeight: 700 }}>
                      {(() => {
                        const pnlVal = pnl ? (pnl.status === 'closed' ? pnl.realized_pnl_usd : pnl.estimated_pnl_usd) : null;
                        return pnlVal != null ? <span style={{ color: pnlVal >= 0 ? 'var(--t-green)' : 'var(--t-red)' }}>{pnlVal >= 0 ? '+' : ''}{fmtUsd(pnlVal)}</span> : '—';
                      })()}
                    </td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', fontSize: 9, fontWeight: 600, color: 'var(--t-dim)' }}>
                      {isExecuted ? (pnl.status === 'closed' ? 'REALIZED' : 'OPEN P&L') : '—'}
                    </td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>
                      {isExecuted ? (
                        <span style={{ display: 'inline-block', width: 105, boxSizing: 'border-box', textAlign: 'center', fontSize: 10, fontWeight: 700, padding: '4px 8px', borderRadius: 4, background: alpha(modeColorOf(pnl.is_paper ? (routerMode === 'shadow' ? 'SHADOW' : 'PAPER') : 'LIVE'), 0.1), color: modeColorOf(pnl.is_paper ? (routerMode === 'shadow' ? 'SHADOW' : 'PAPER') : 'LIVE'), whiteSpace: 'nowrap' }}>✓ {(algoOn ? 'AUTO·' : '')}{(pnl.is_paper ? (routerMode === 'shadow' ? 'SHADOW' : 'PAPER') : 'LIVE').toUpperCase()}</span>
                      ) : hasPlan ? (
                        algoOn ? (
                          <span style={{ display: 'inline-block', width: 105, boxSizing: 'border-box', textAlign: 'center', fontSize: 10, fontWeight: 700, padding: '4px 8px', borderRadius: 4, background: alpha(modeColorOf(routerMode), 0.1), color: modeColorOf(routerMode), whiteSpace: 'nowrap' }}>⚡ AUTO·{routerMode.toUpperCase()}</span>
                        ) : (
                          <button disabled={execute.isPending} onClick={(e) => { e.stopPropagation(); handleExecute(s); }} style={{ display: 'inline-block', width: 105, boxSizing: 'border-box', textAlign: 'center', fontSize: 10, fontWeight: 700, padding: '4px 8px', borderRadius: 4, background: dirColor, color: '#fff', border: 'none', cursor: 'pointer', whiteSpace: 'nowrap' }}>EXECUTE</button>
                        )
                      ) : null}
                    </td>
                  </tr>
                  {isExp && (
                    <tr style={{ background: alpha(statusColor, 0.04), borderBottom: `1px solid ${c.border2}` }}>
                      <td colSpan={15} style={{ padding: '12px 14px' }}>
                        {isExecuted && pnl ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                              <span style={{ fontSize: 11, fontWeight: 800, color: 'var(--t-green)', letterSpacing: '0.02em' }}>
                                ✓ {algoOn ? 'Auto-executed' : 'Manual-executed'} on {pnl.is_paper ? (routerMode === 'shadow' ? 'SHADOW' : 'PAPER') : 'LIVE'}
                              </span>
                              <span style={{ fontSize: 9, color: 'var(--t-dim)', fontVariantNumeric: 'tabular-nums' }}>{fmtTime(pnl.entry_timestamp_ms || s.timestamp_ms)}</span>
                              <span style={{ fontSize: 11, color: 'var(--t-dim)', marginLeft: 4 }}>{pnl.status === 'closed' ? 'closed' : 'open'}</span>
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px', paddingTop: 4 }}>
                              <MetricItem label="Qty" value={fmt(pnl.contracts || 1.0000, 4)} />
                              <MetricItem label="Entry" value={fmtUsd(pnl.entry_price_real ?? pnl.entry_spot ?? s.spot_price)} />
                              {pnl.status === 'closed' && (
                                <MetricItem label="Exit" value={fmtUsd(pnl.current_spot)} />
                              )}
                              <MetricItem label="Initial SL" value={fmtUsd(pnl.initial_sl ?? s.stop_price ?? 0)} color="var(--t-red)" />
                              <MetricItem label="Target" value={fmtUsd(pnl.initial_tp ?? s.target_price)} color="var(--t-amber)" />
                              <MetricItem label="Notional" value={fmtUsd((pnl.entry_price_real ?? pnl.entry_spot ?? s.spot_price) * (pnl.contracts || 1.0))} />
                              
                              {(() => {
                                const pnlVal = pnl.status === 'closed' ? pnl.realized_pnl_usd : pnl.estimated_pnl_usd;
                                const pnlColor = pnlVal == null ? 'var(--t-dim)' : pnlVal >= 0 ? 'var(--t-green)' : 'var(--t-red)';
                                return (
                                  <MetricItem 
                                    label={pnl.status === 'closed' ? 'Realized P&L' : 'Open P&L'} 
                                    value={pnlVal == null ? '—' : `${pnlVal >= 0 ? '+' : '−'}${fmtUsd(Math.abs(pnlVal))}`} 
                                    color={pnlColor} 
                                  />
                                );
                              })()}
                              
                              <MetricItem label="Trail" value={pnl.trail_mode || 'percentage'} color="var(--t-blue)" />
                              <MetricItem label="Order" value={pnl.status === 'closed' ? 'closed' : 'filled'} color={pnl.status === 'closed' ? 'var(--t-dim)' : 'var(--t-green)'} />
                              <MetricItem label="Mode" value={pnl.is_paper ? (routerMode === 'shadow' ? 'SHADOW' : 'PAPER') : 'LIVE'} color="var(--t-blue)" />
                              <MetricItem label="Profile" value={s.profile || 'SCALPING'} color="var(--t-bright)" />
                              <MetricItem label="Pattern" value={s.strategy ? s.strategy.replace(/_/g, ' ') : '—'} color="var(--t-amber)" />
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--t-text)', marginTop: 8, display: 'flex', gap: 16 }}>
                              <div><span style={{ color: 'var(--t-dim)', fontWeight: 600 }}>TRACK:</span> {s.track || '—'}</div>
                              <div><span style={{ color: 'var(--t-dim)', fontWeight: 600 }}>STATE:</span> {s.state}</div>
                              {s.mtf_breakdown && (
                                <div><span style={{ color: 'var(--t-dim)', fontWeight: 600 }}>MTF ALIGNMENT:</span> {s.mtf_breakdown.alignment_label}</div>
                              )}
                              {s.veto_reason && <div style={{ color: 'var(--t-amber)' }}>⚠ {s.veto_reason}</div>}
                            </div>
                          </div>
                        ) : (
                          <div style={{ fontSize: 11, color: 'var(--t-text)' }}>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px' }}>
                              <MetricItem label="Profile" value={s.profile?.toUpperCase() || 'SCALPING'} color="var(--t-bright)" />
                              <MetricItem label="Pattern" value={s.strategy ? s.strategy.replace(/_/g, ' ') : '—'} color="var(--t-amber)" />
                              <MetricItem label="Track" value={s.track || '—'} />
                              <MetricItem label="State" value={s.state} />
                            </div>
                            {s.mtf_breakdown && (
                              <div style={{ marginTop: 8 }}>
                                <span style={{ color: 'var(--t-dim)', fontWeight: 600 }}>MTF ALIGNMENT:</span> {s.mtf_breakdown.alignment_label}
                              </div>
                            )}
                            {s.veto_reason && <div style={{ marginTop: 4, color: 'var(--t-amber)' }}>⚠ {s.veto_reason}</div>}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
          {spotPnlStats.count > 0 && (
            <tfoot>
              <tr style={{ borderTop: `2px solid ${c.border}`, color: c.text }}>
                <td colSpan={12} style={{ padding: '7px 8px', fontSize: 10, color: c.dim, letterSpacing: '0.04em', fontWeight: 700 }}>
                  CONSOLIDATED · {spotPnlStats.count} position{spotPnlStats.count === 1 ? '' : 's'}
                  <span style={{ marginLeft: 10, fontWeight: 400 }}>
                    unrealized <b style={{ color: spotPnlStats.totalUnrealized >= 0 ? c.green : c.red }}>{fmtSigned(spotPnlStats.totalUnrealized)}</b>
                    {' · '}realized <b style={{ color: spotPnlStats.totalRealized >= 0 ? c.green : c.red }}>{fmtSigned(spotPnlStats.totalRealized)}</b>
                  </span>
                </td>
                <td style={{ padding: '7px 8px', textAlign: 'right', fontWeight: 800, color: spotPnlStats.total >= 0 ? c.green : c.red }}>
                  {fmtSigned(spotPnlStats.total)}
                </td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          )}
        </table>
      </SectionCard>
      
      <div style={{ height: 16 }} />
      <FuturesCandidatesTable />
      
      <div style={{ height: 16 }} />
      <OptionsCandidatesTable />
      
      <div style={{ height: 32 }} />
    </div>
  );
}
