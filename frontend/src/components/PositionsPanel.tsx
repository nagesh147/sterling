import React, { useState } from 'react';
import { usePositions, useEnterPosition, useClosePosition, useDeletePosition, useCloseAll } from '../hooks/usePositions';
import { useExchanges } from '../hooks/useExchanges';
import { useMonitorPosition, useMonitorAll } from '../hooks/useMonitorPosition';
import { useLivePnl } from '../hooks/useLivePnl';
import { useTrailStop } from '../hooks/useTrailStop';
import type { MonitorResult } from '../hooks/useMonitorPosition';
import type { PaperPosition, PositionStatus } from '../types';
import { fmtN, fmtUSD } from '../utils/fmt';
import { api } from '../utils/api';
import { downloadCSV } from '../hooks/useDownload';
import { PnLSparkline } from './PnLSparkline';
import { c as t, tint } from '../styles/terminalUI';

const STATUS_COLOR: Record<PositionStatus, string> = {
  open: t.green,
  partially_closed: t.amber,
  closed: t.dim,
};

const styles: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  counts: { display: 'flex', gap: 12 },
  countBadge: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 3, padding: '3px 10px', fontSize: 11 },
  enterBtn: {
    background: '#1a2a1a', color: t.green, border: `1px solid ${t.green}`,
    padding: '6px 14px', borderRadius: 4, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 12, letterSpacing: 1,
  },
  noPos: { color: t.dim, fontSize: 12, textAlign: 'center', padding: 20 },
  posCard: {
    background: t.bg, border: `1px solid ${t.border}`,
    borderRadius: 4, padding: 12, marginBottom: 8,
  },
  posHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  posType: { color: t.blue, fontWeight: 700, fontSize: 13 },
  statusBadge: { fontSize: 11, padding: '2px 8px', borderRadius: 3, fontWeight: 600 },
  posGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, fontSize: 11 },
  cell: { display: 'flex', flexDirection: 'column', gap: 2 },
  key: { color: t.dim },
  val: { color: t.text },
  actions: { display: 'flex', gap: 8, marginTop: 10 },
  closeBtn: {
    background: t.raised, color: t.red, border: `1px solid ${t.red}`,
    padding: '4px 12px', borderRadius: 3, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 11,
  },
  deleteBtn: {
    background: t.raised, color: t.dim, border: `1px solid ${t.border}`,
    padding: '4px 12px', borderRadius: 3, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 11,
  },
  pnl: { fontWeight: 700 },
  error: { color: t.red, fontSize: 11, marginTop: 4 },
};

function fmt(n?: number, d = 2) {
  if (n === undefined || n === null) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}


// ── G3: Next exit reason pill ─────────────────────────────────────────────
//
// Displays whichever exit boundary is closest to current price. Reason
// priority mirrors backend monitor_engine.check_exits():
//   DTE → SL → TP. Always wrapped in a `title` tooltip with full detail.

interface ExitGuess {
  label: string;
  distance_pct: number;
  color: string;
  detail: string;
}

function nextExitGuess(pos: PaperPosition, currentSpot: number | null): ExitGuess | null {
  const entry = pos.entry_spot_price;
  const sl = pos.current_sl;
  const tp = pos.current_tp;
  const leg = pos.sized_trade?.structure?.legs?.[0];
  const direction = pos.sized_trade?.structure?.direction;

  if (leg?.dte != null) {
    const ageDays = (Date.now() - pos.entry_timestamp_ms) / 86_400_000;
    const remaining = Math.max(0, leg.dte - ageDays);
    if (remaining <= 5) {
      return {
        label: 'DTE',
        distance_pct: 0,
        color: t.red,
        detail: `≈${remaining.toFixed(1)}d to expiry — time stop fires at 3d`,
      };
    }
  }

  const ref = currentSpot ?? entry;
  const candidates: { label: string; price: number; color: string; reason: string }[] = [];
  if (sl && sl > 0) candidates.push({ label: 'SL', price: sl, color: t.red, reason: 'Trail stop hit' });
  if (tp && tp > 0) candidates.push({ label: 'TP', price: tp, color: t.green, reason: 'Take-profit hit' });
  if (candidates.length === 0) return null;

  const filtered = candidates.filter((c) => {
    if (direction === 'long')  return (c.label === 'SL' && c.price < ref) || (c.label === 'TP' && c.price > ref);
    if (direction === 'short') return (c.label === 'SL' && c.price > ref) || (c.label === 'TP' && c.price < ref);
    return true;
  });
  const pool = filtered.length > 0 ? filtered : candidates;
  pool.sort((a, b) => Math.abs(a.price - ref) - Math.abs(b.price - ref));
  const top = pool[0];
  const dist = Math.abs(top.price - ref) / Math.max(ref, 1) * 100;
  return {
    label: top.label,
    distance_pct: dist,
    color: top.color,
    detail: `${top.reason} at $${fmt(top.price)} (${dist.toFixed(2)}% away)`,
  };
}

function NextExitPill({ pos, currentSpot }: { pos: PaperPosition; currentSpot: number | null }) {
  const guess = nextExitGuess(pos, currentSpot);
  if (!guess) return null;
  return (
    <span
      title={guess.detail}
      style={{
        fontSize: 10, padding: '2px 7px', borderRadius: 3,
        background: guess.color + '18',
        border: `1px solid ${guess.color}44`,
        color: guess.color,
        fontWeight: 700, letterSpacing: 0.5, cursor: 'help',
        whiteSpace: 'nowrap',
      }}
    >
      NEXT: {guess.label}
      {guess.distance_pct > 0 && ` ${guess.distance_pct.toFixed(2)}%`}
    </span>
  );
}

function TrailStopRow({ posId, entrySpot, currentSpot }: {
  posId: string; entrySpot: number; currentSpot?: number | null;
}) {
  const { data: trail } = useTrailStop(posId);
  if (!trail?.stop) return null;

  const stopDistPct = currentSpot && currentSpot > 0
    ? ((currentSpot - trail.stop) / currentSpot * 100)
    : null;

  return (
    <div style={{
      background: t.bg, border: '1px solid #cc444433',
      borderRadius: 4, padding: '6px 10px', marginTop: 6,
      display: 'flex', alignItems: 'center', gap: 14, fontSize: 11, flexWrap: 'wrap',
    }}>
      <div>
        <span style={{ color: t.dim }}>TRAIL STOP </span>
        <span style={{ color: t.red, fontWeight: 700, fontFamily: 'monospace' }}>
          ${trail.stop.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
        </span>
        <span style={{ color: t.dim, marginLeft: 4, fontSize: 10 }}>({trail.mode})</span>
      </div>
      {stopDistPct != null && (
        <div>
          <span style={{ color: t.dim }}>DIST </span>
          <span style={{ color: stopDistPct > 5 ? t.green : stopDistPct > 2 ? t.amber : t.red }}>
            {stopDistPct.toFixed(2)}%
          </span>
        </div>
      )}
      {trail.partial_25_done && (
        <span style={{
          background: '#44cc8822', color: t.green,
          border: '1px solid #44cc8844', borderRadius: 3,
          padding: '1px 6px', fontSize: 10, fontWeight: 600,
        }}>25% LOCKED</span>
      )}
      {trail.partial_50_done && (
        <span style={{
          background: '#4499cc22', color: t.blue,
          border: '1px solid #4499cc44', borderRadius: 3,
          padding: '1px 6px', fontSize: 10, fontWeight: 600,
        }}>50% LOCKED</span>
      )}
    </div>
  );
}

function MonitorResultInline({ result }: { result: MonitorResult }) {
  const sig = result.exit_signal;
  const pnlColor = result.estimated_pnl_usd >= 0 ? t.green : t.red;
  const exitColor = sig.should_exit ? t.red : sig.partial ? t.amber : t.green;
  return (
    <div style={{ background: t.bg, border: `1px solid ${exitColor}33`, borderRadius: 4, padding: '8px 12px', marginTop: 8, fontSize: 11 }}>
      <div style={{ color: exitColor, fontWeight: 700, marginBottom: 4 }}>
        {sig.should_exit ? `⚠ EXIT: ${sig.exit_type?.toUpperCase()}` : sig.partial ? '↘ PARTIAL PROFIT' : '✓ HOLD'}
      </div>
      <div style={{ color: t.dim }}>{sig.reason}</div>
      <div style={{ display: 'flex', gap: 16, marginTop: 6, color: t.dim }}>
        <span>Spot: ${fmtUSD(result.current_spot)}</span>
        <span style={{ color: pnlColor }}>Est P&L: {(result.estimated_pnl_usd ?? 0) >= 0 ? '+' : ''}{fmtN(result.estimated_pnl_usd, 2)}</span>
        <span>DTE: {result.current_dte}</span>
        <span>Trend: {result.current_signal_trend === 1 ? '▲' : result.current_signal_trend === -1 ? '▼' : '~'}</span>
      </div>
    </div>
  );
}

const ORDER_STATUS_COLORS: Record<string, string> = {
  filled: t.green,
  pending: t.amber,
  failed: t.red,
  cancelled: t.dim,
  retry: t.blue,
};

function RetryOrderButton({ posId, onDone }: { posId: string; onDone?: () => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const retry = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.post(`/api/v1/trading/retry-order/${posId}`);
      onDone?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Retry failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        style={{
          background: '#1a2233', color: t.blue, border: '1px solid #4499cc66',
          padding: '4px 12px', borderRadius: 3, cursor: 'pointer',
          fontFamily: 'inherit', fontSize: 11, opacity: loading ? 0.6 : 1,
        }}
        onClick={retry}
        disabled={loading}
      >
        {loading ? '⟳ RETRYING…' : '⟳ RETRY ORDER'}
      </button>
      {error && <span style={{ color: t.red, fontSize: 10, marginLeft: 8 }}>{error}</span>}
    </div>
  );
}

export function PositionCard({ pos, livePnl }: { pos: PaperPosition; livePnl?: number | null }) {
  const [closePrice, setClosePrice] = useState('');
  const [showClose, setShowClose] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const [notesText, setNotesText] = useState(pos.notes);
  const close = useClosePosition();
  const del = useDeletePosition();
  const monitor = useMonitorPosition();
  const s = pos.sized_trade.structure;
  const leg = s.legs[0];
  const isFailed = pos.order_status === 'failed';
  const isPending = pos.order_status === 'pending' || pos.order_status === 'retry';
  const isLiveOrder = !pos.is_paper;

  return (
    <div style={{
      ...styles.posCard,
      borderColor: isFailed ? '#cc444433' : isPending ? '#f0c04033' : styles.posCard.borderColor,
    }}>
      <div style={styles.posHeader}>
        <span style={styles.posType}>
          {pos.underlying} · {s.structure_type}
          {isLiveOrder && (
            <span style={{
              marginLeft: 8, fontSize: 10, padding: '1px 6px',
              background: '#4499cc22', color: t.blue,
              border: '1px solid #4499cc44', borderRadius: 3,
            }}>LIVE</span>
          )}
        </span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {(pos.status === 'open' || pos.status === 'partially_closed') && (
            <NextExitPill
              pos={pos}
              currentSpot={
                livePnl != null
                  ? pos.entry_spot_price + livePnl / Math.max(0.01, pos.sized_trade.contracts)
                  : null
              }
            />
          )}
          {livePnl != null && (
            <span style={{
              fontSize: 12, fontWeight: 700,
              color: livePnl >= 0 ? t.green : t.red,
            }}>
              {livePnl >= 0 ? '+' : ''}{fmtN(livePnl, 2)}
            </span>
          )}
          {pos.order_status && (
            <span style={{
              ...styles.statusBadge,
              background: (ORDER_STATUS_COLORS[pos.order_status] ?? t.dim) + '22',
              color: ORDER_STATUS_COLORS[pos.order_status] ?? t.dim,
              marginRight: 4,
            }}>
              {pos.order_status === 'failed' ? '✕ FAILED' :
               pos.order_status === 'filled' ? '✓ FILLED' :
               pos.order_status === 'pending' ? '⟳ PENDING' :
               pos.order_status === 'retry' ? '↻ RETRYING' :
               pos.order_status.toUpperCase()}
            </span>
          )}
          <span style={{
            ...styles.statusBadge,
            background: STATUS_COLOR[pos.status] + '22',
            color: STATUS_COLOR[pos.status],
          }}>
            {pos.status.toUpperCase()}
          </span>
        </div>
      </div>

      <div style={styles.posGrid}>
        <div style={styles.cell}><span style={styles.key}>ID</span><span style={styles.val}>{pos.id}</span></div>
        <div style={styles.cell}>
          <span style={styles.key}>LEGS</span>
          <span style={styles.val}>
            {s.legs.map((l, i) => (
              <span key={i} style={{ display: 'block', fontSize: 11, color: t.text }}>
                {i === 0 ? 'BUY' : 'SELL'} {l.strike.toLocaleString()} {l.expiry_date} {l.option_type.slice(0, 1).toUpperCase()}
              </span>
            ))}
          </span>
        </div>
        <div style={styles.cell}><span style={styles.key}>DTE AT ENTRY</span><span style={styles.val}>{leg?.dte}d</span></div>
        <div style={styles.cell}><span style={styles.key}>CONTRACTS</span><span style={styles.val}>{pos.sized_trade.contracts}</span></div>
        <div style={styles.cell}><span style={styles.key}>ENTRY SPOT</span><span style={styles.val}>${fmt(pos.entry_spot_price)}</span></div>
        <div style={styles.cell}><span style={styles.key}>MAX RISK</span><span style={styles.val}>${fmt(pos.sized_trade.max_risk_usd)}</span></div>
        <div style={styles.cell}><span style={styles.key}>SCORE</span><span style={styles.val}>{fmtN(s.score, 1)}</span></div>
        {pos.exit_mode && (
          <div style={styles.cell}>
            <span style={styles.key}>EXIT MODE</span>
            <span style={{...styles.val, fontSize: 10, background: '#333', padding: '1px 4px', borderRadius: 2}}>
              {pos.exit_mode} {pos.current_red_count != null && pos.exit_threshold != null ? `(${pos.current_red_count}/${pos.exit_threshold} red)` : ''}
            </span>
            {pos.current_red_count != null && pos.exit_threshold != null && pos.exit_threshold > 0 && (
              <div style={{width: 60, height: 8, background: '#222', borderRadius: 4, overflow: 'hidden', marginTop: 2}}>
                <div style={{
                  width: `${Math.min(100, (pos.current_red_count / pos.exit_threshold) * 100)}%`,
                  height: '100%',
                  background: pos.current_red_count >= pos.exit_threshold ? '#f44' : pos.current_red_count > pos.exit_threshold * 0.6 ? '#fa0' : '#4a4',
                  transition: 'width 0.2s'
                }} />
              </div>
            )}
          </div>
        )}
        {pos.last_st_alignment && (
          <div style={styles.cell}>
            <span style={styles.key}>ST ALIGN</span>
            <span style={styles.val}>{pos.last_st_alignment.join('/')}</span>
          </div>
        )}
        {pos.realized_pnl_usd != null && (
          <div style={styles.cell}>
            <span style={styles.key}>REALIZED P&L</span>
            <span style={{
              ...styles.val, ...styles.pnl,
              color: pos.realized_pnl_usd >= 0 ? t.green : t.red,
            }}>
              {pos.realized_pnl_usd >= 0 ? '+' : ''}{fmt(pos.realized_pnl_usd)}
            </span>
          </div>
        )}
      </div>

      {pos.order_id && (
        <div style={{ marginTop: 6, fontSize: 10, color: t.dim }}>
          ORDER ID: <span style={{ color: t.dim, fontFamily: 'monospace' }}>{pos.order_id}</span>
        </div>
      )}
      {isFailed && (
        <div style={{
          marginTop: 8, padding: '6px 10px',
          background: '#cc444411', border: '1px solid #cc444433',
          borderRadius: 4, fontSize: 11,
        }}>
          <div style={{ color: t.red, fontWeight: 700, marginBottom: 6 }}>
            ✕ Order failed — position held for retry
          </div>
          <div style={{ color: t.red, marginBottom: 8 }}>
            {pos.notes?.replace('[ALGO-FAILED] ', '').replace('[ALGO-RETRY] [ALGO-FAILED] ', '')}
          </div>
          <RetryOrderButton posId={pos.id} />
        </div>
      )}
      {(pos.status === 'open' || pos.status === 'partially_closed') && (
        <TrailStopRow
          posId={pos.id}
          entrySpot={pos.entry_spot_price}
          currentSpot={livePnl != null ? pos.entry_spot_price + livePnl / Math.max(0.01, pos.sized_trade.contracts) : null}
        />
      )}

      {pos.status === 'open' && (
        <div style={{ marginTop: 8 }}>
          <PnLSparkline positionId={pos.id} entrySpot={pos.entry_spot_price} />
        </div>
      )}

      {monitor.data && <MonitorResultInline result={monitor.data} />}

      {(pos.status === 'open' || pos.status === 'partially_closed') && (
        <div style={styles.actions}>
          <button
            style={{ ...styles.deleteBtn, color: t.blue, borderColor: '#88aaff33' }}
            onClick={() => monitor.mutate(pos.id)}
            disabled={monitor.isPending}
          >
            {monitor.isPending ? '…' : '⟳ MONITOR'}
          </button>
          <button
            style={{ ...styles.deleteBtn, color: t.text, borderColor: '#33333344' }}
            onClick={() => setShowNotes(!showNotes)}
            title="Edit trade journal notes"
          >
            ✎ NOTES
          </button>
          {!showClose ? (
            <button style={styles.closeBtn} onClick={() => setShowClose(true)}>
              CLOSE
            </button>
          ) : (
            <>
              <input
                type="number"
                placeholder="Exit spot price"
                value={closePrice}
                onChange={e => setClosePrice(e.target.value)}
                style={{
                  background: t.raised, color: t.text, border: `1px solid ${t.border}`,
                  padding: '4px 8px', borderRadius: 3, fontFamily: 'inherit', fontSize: 11, width: 140,
                }}
              />
              <button
                style={styles.closeBtn}
                onClick={() => {
                  if (closePrice) {
                    close.mutate({ id: pos.id, exit_spot_price: parseFloat(closePrice) });
                    setShowClose(false);
                  }
                }}
                disabled={close.isPending}
              >
                {close.isPending ? 'CLOSING…' : 'CONFIRM'}
              </button>
              <button style={styles.deleteBtn} onClick={() => setShowClose(false)}>CANCEL</button>
            </>
          )}
          <button style={styles.deleteBtn} onClick={() => del.mutate(pos.id)}>
            DELETE
          </button>
        </div>
      )}
      {close.error && <div style={styles.error}>{(close.error as Error).message}</div>}

      {showNotes && (
        <div style={{ marginTop: 6, display: 'flex', gap: 6, alignItems: 'center' }}>
          <input
            style={{ ...styles.deleteBtn, flex: 1, color: t.text, border: `1px solid ${t.border}`, padding: '4px 8px' }}
            type="text"
            placeholder="Trade journal notes…"
            value={notesText}
            onChange={e => setNotesText(e.target.value)}
          />
          <button
            style={styles.deleteBtn}
            onClick={() => {
              api.patch(`/api/v1/positions/${pos.id}/notes?notes=${encodeURIComponent(notesText)}`)
                .then(() => setShowNotes(false)).catch(() => {});
            }}
          >
            SAVE
          </button>
        </div>
      )}
    </div>
  );
}

interface Props { underlying: string }

export function PositionsPanel({ underlying }: Props) {
  const { data: exData }  = useExchanges();
  const delta   = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const isLive  = !!(delta?.has_credentials && !delta.is_paper);
  // Show positions from ALL modes (paper / shadow / live). Filtering by the exchange
  // toggle hid paper/shadow positions whenever the account was switched to Live —
  // which made the dashboard read "0 open" while the order book showed them.
  const { data, isLoading } = usePositions();
  const enter = useEnterPosition();
  const monitorAll = useMonitorAll();
  const closeAll = useCloseAll();
  const [showCloseAllConfirm, setShowCloseAllConfirm] = useState(false);
  const monitorDebounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMonitorAll = () => {
    if (monitorAll.isPending) return;
    if (monitorDebounceRef.current) clearTimeout(monitorDebounceRef.current);
    monitorDebounceRef.current = setTimeout(() => monitorAll.mutate(), 400);
  };
  const [closeAllResult, setCloseAllResult] = useState<{ count: number; pnl: number } | null>(null);
  const [closeAllError, setCloseAllError] = useState<string | null>(null);
  const hasOpen = (data?.open_count ?? 0) > 0;
  const { data: livePnlData } = useLivePnl(hasOpen);
  const livePnlMap = Object.fromEntries(
    (livePnlData?.positions ?? []).map(p => [p.position_id, p.estimated_pnl_usd])
  );

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div>
          <div style={{ ...styles.title, display: 'flex', alignItems: 'center', gap: 8 }}>
            POSITIONS
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: 1,
              color: isLive ? 'var(--accent)' : t.blue,
              background: isLive ? 'var(--accent)18' : '#88aaff18',
              border: `1px solid ${isLive ? 'var(--accent)44' : '#88aaff44'}`,
              borderRadius: 3, padding: '1px 6px',
            }}>
              {isLive ? '● LIVE' : 'PAPER'}
            </span>
          </div>
          {data && (
            <div style={styles.counts}>
              <span style={{ ...styles.countBadge, color: t.green }}>
                {data.open_count} OPEN
                {data.partially_closed_count > 0 && (
                  <span style={{ color: t.amber, marginLeft: 4, fontSize: 10 }}>
                    ({data.partially_closed_count} partial)
                  </span>
                )}
              </span>
              <span style={{ ...styles.countBadge, color: t.dim }}>
                {data.closed_count} CLOSED
              </span>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            style={enter.isPending ? { ...styles.enterBtn, opacity: 0.5, cursor: 'not-allowed' } : styles.enterBtn}
            onClick={() => enter.mutate({ underlying })}
            disabled={enter.isPending}
          >
            {enter.isPending ? 'EVALUATING…' : `▶ PAPER ENTER — ${underlying}`}
          </button>
          <button
            style={{ background: t.raised, color: t.blue, border: `1px solid ${t.border}`, padding: '5px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
            onClick={handleMonitorAll}
            disabled={monitorAll.isPending}
            title="Check all open/partial positions for exit signals"
          >
            {monitorAll.isPending ? '…' : '⟳ REFRESH ALL POSITIONS'}
          </button>
          {!showCloseAllConfirm ? (
            <button
              style={{ background: t.raised, color: t.red, border: '1px solid #cc664433', padding: '5px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
              onClick={() => setShowCloseAllConfirm(true)}
              disabled={(data?.open_count ?? 0) === 0}
              title="Close all open positions at current market price"
            >
              ✕ CLOSE ALL
            </button>
          ) : (
            <>
              <button
                style={{ background: '#2a0d0d', color: t.red, border: `1px solid ${t.red}`, padding: '5px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
                onClick={() => {
                  closeAll.mutate(undefined, {
                    onSuccess: (d) => {
                      setShowCloseAllConfirm(false);
                      setCloseAllResult({ count: d.closed_count, pnl: d.total_realized_pnl_usd });
                      setCloseAllError(null);
                      setTimeout(() => setCloseAllResult(null), 5000);
                    },
                    onError: (e) => {
                      setShowCloseAllConfirm(false);
                      setCloseAllError((e as Error).message);
                      setTimeout(() => setCloseAllError(null), 5000);
                    },
                  });
                }}
                disabled={closeAll.isPending}
              >
                {closeAll.isPending ? 'CLOSING…' : 'CONFIRM CLOSE ALL'}
              </button>
              <button
                style={{ background: t.raised, color: t.dim, border: `1px solid ${t.border}`, padding: '5px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
                onClick={() => setShowCloseAllConfirm(false)}
              >CANCEL</button>
            </>
          )}
          {closeAllResult && (
            <div style={{ background: '#0d1a0d', border: '1px solid #44cc8844', borderRadius: 4, padding: '6px 12px', fontSize: 11, color: t.green, marginTop: 6 }}>
              ✓ Closed {closeAllResult.count} position{closeAllResult.count !== 1 ? 's' : ''} · P&L {closeAllResult.pnl >= 0 ? '+' : ''}${closeAllResult.pnl.toFixed(2)}
            </div>
          )}
          {closeAllError && (
            <div style={{ background: '#1a0d0d', border: '1px solid #cc444444', borderRadius: 4, padding: '6px 12px', fontSize: 11, color: t.red, marginTop: 6 }}>
              Close all failed: {closeAllError}
            </div>
          )}
          <button
            style={{ background: t.raised, color: t.blue, border: `1px solid ${t.border}`, padding: '5px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
            onClick={() => downloadCSV('/api/v1/positions/export', 'sterling_paper_positions.csv')}
          >
            ↓ CSV
          </button>
          {enter.error && (
            <div style={styles.error}>{(enter.error as Error).message}</div>
          )}
        </div>
      </div>

      {isLoading && <div style={styles.noPos}>Loading…</div>}

      {!isLoading && data?.positions.length === 0 && (
        <div style={styles.noPos}>No paper positions. Run evaluation and enter to create one.</div>
      )}

      {data?.positions.map(pos => (
        <PositionCard key={pos.id} pos={pos} livePnl={livePnlMap[pos.id]} />
      ))}
    </div>
  );
}
