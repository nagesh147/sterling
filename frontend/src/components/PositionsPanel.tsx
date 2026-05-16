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

const STATUS_COLOR: Record<PositionStatus, string> = {
  open: '#44cc88',
  partially_closed: '#f0c040',
  closed: '#555',
};

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  counts: { display: 'flex', gap: 12 },
  countBadge: { background: '#1a1a1a', border: '1px solid #222', borderRadius: 3, padding: '3px 10px', fontSize: 11 },
  enterBtn: {
    background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88',
    padding: '6px 14px', borderRadius: 4, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 12, letterSpacing: 1,
  },
  noPos: { color: '#444', fontSize: 12, textAlign: 'center', padding: 20 },
  posCard: {
    background: '#111', border: '1px solid #1e1e1e',
    borderRadius: 4, padding: 12, marginBottom: 8,
  },
  posHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  posType: { color: '#aaddff', fontWeight: 700, fontSize: 13 },
  statusBadge: { fontSize: 11, padding: '2px 8px', borderRadius: 3, fontWeight: 600 },
  posGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, fontSize: 11 },
  cell: { display: 'flex', flexDirection: 'column', gap: 2 },
  key: { color: '#555' },
  val: { color: '#ccc' },
  actions: { display: 'flex', gap: 8, marginTop: 10 },
  closeBtn: {
    background: '#2a1a1a', color: '#cc6644', border: '1px solid #cc6644',
    padding: '4px 12px', borderRadius: 3, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 11,
  },
  deleteBtn: {
    background: '#1a1a1a', color: '#555', border: '1px solid #333',
    padding: '4px 12px', borderRadius: 3, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 11,
  },
  pnl: { fontWeight: 700 },
  error: { color: '#cc4444', fontSize: 11, marginTop: 4 },
};

function fmt(n?: number, d = 2) {
  if (n === undefined || n === null) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
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
      background: '#0d0d0d', border: '1px solid #cc444433',
      borderRadius: 4, padding: '6px 10px', marginTop: 6,
      display: 'flex', alignItems: 'center', gap: 14, fontSize: 11, flexWrap: 'wrap',
    }}>
      <div>
        <span style={{ color: '#555' }}>TRAIL STOP </span>
        <span style={{ color: '#cc6644', fontWeight: 700, fontFamily: 'monospace' }}>
          ${trail.stop.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
        </span>
        <span style={{ color: '#444', marginLeft: 4, fontSize: 10 }}>({trail.mode})</span>
      </div>
      {stopDistPct != null && (
        <div>
          <span style={{ color: '#555' }}>DIST </span>
          <span style={{ color: stopDistPct > 5 ? '#44cc88' : stopDistPct > 2 ? '#f0c040' : '#cc4444' }}>
            {stopDistPct.toFixed(2)}%
          </span>
        </div>
      )}
      {trail.partial_25_done && (
        <span style={{
          background: '#44cc8822', color: '#44cc88',
          border: '1px solid #44cc8844', borderRadius: 3,
          padding: '1px 6px', fontSize: 10, fontWeight: 600,
        }}>25% LOCKED</span>
      )}
      {trail.partial_50_done && (
        <span style={{
          background: '#4499cc22', color: '#4499cc',
          border: '1px solid #4499cc44', borderRadius: 3,
          padding: '1px 6px', fontSize: 10, fontWeight: 600,
        }}>50% LOCKED</span>
      )}
    </div>
  );
}

function MonitorResultInline({ result }: { result: MonitorResult }) {
  const sig = result.exit_signal;
  const pnlColor = result.estimated_pnl_usd >= 0 ? '#44cc88' : '#cc4444';
  const exitColor = sig.should_exit ? '#cc4444' : sig.partial ? '#f0c040' : '#44cc88';
  return (
    <div style={{ background: '#0d0d0d', border: `1px solid ${exitColor}33`, borderRadius: 4, padding: '8px 12px', marginTop: 8, fontSize: 11 }}>
      <div style={{ color: exitColor, fontWeight: 700, marginBottom: 4 }}>
        {sig.should_exit ? `⚠ EXIT: ${sig.exit_type?.toUpperCase()}` : sig.partial ? '↘ PARTIAL PROFIT' : '✓ HOLD'}
      </div>
      <div style={{ color: '#666' }}>{sig.reason}</div>
      <div style={{ display: 'flex', gap: 16, marginTop: 6, color: '#888' }}>
        <span>Spot: ${fmtUSD(result.current_spot)}</span>
        <span style={{ color: pnlColor }}>Est P&L: {(result.estimated_pnl_usd ?? 0) >= 0 ? '+' : ''}{fmtN(result.estimated_pnl_usd, 2)}</span>
        <span>DTE: {result.current_dte}</span>
        <span>Trend: {result.current_signal_trend === 1 ? '▲' : result.current_signal_trend === -1 ? '▼' : '~'}</span>
      </div>
    </div>
  );
}

const ORDER_STATUS_COLORS: Record<string, string> = {
  filled: '#44cc88',
  pending: '#f0c040',
  failed: '#cc4444',
  cancelled: '#888',
  retry: '#4499cc',
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
          background: '#1a2233', color: '#4499cc', border: '1px solid #4499cc66',
          padding: '4px 12px', borderRadius: 3, cursor: 'pointer',
          fontFamily: 'inherit', fontSize: 11, opacity: loading ? 0.6 : 1,
        }}
        onClick={retry}
        disabled={loading}
      >
        {loading ? '⟳ RETRYING…' : '⟳ RETRY ORDER'}
      </button>
      {error && <span style={{ color: '#cc4444', fontSize: 10, marginLeft: 8 }}>{error}</span>}
    </div>
  );
}

function PositionCard({ pos, livePnl }: { pos: PaperPosition; livePnl?: number | null }) {
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
              background: '#4499cc22', color: '#4499cc',
              border: '1px solid #4499cc44', borderRadius: 3,
            }}>LIVE</span>
          )}
        </span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {livePnl != null && (
            <span style={{
              fontSize: 12, fontWeight: 700,
              color: livePnl >= 0 ? '#44cc88' : '#cc4444',
            }}>
              {livePnl >= 0 ? '+' : ''}{fmtN(livePnl, 2)}
            </span>
          )}
          {pos.order_status && (
            <span style={{
              ...styles.statusBadge,
              background: (ORDER_STATUS_COLORS[pos.order_status] ?? '#888') + '22',
              color: ORDER_STATUS_COLORS[pos.order_status] ?? '#888',
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
              <span key={i} style={{ display: 'block', fontSize: 11, color: '#aaa' }}>
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
        {pos.realized_pnl_usd != null && (
          <div style={styles.cell}>
            <span style={styles.key}>REALIZED P&L</span>
            <span style={{
              ...styles.val, ...styles.pnl,
              color: pos.realized_pnl_usd >= 0 ? '#44cc88' : '#cc4444',
            }}>
              {pos.realized_pnl_usd >= 0 ? '+' : ''}{fmt(pos.realized_pnl_usd)}
            </span>
          </div>
        )}
      </div>

      {pos.order_id && (
        <div style={{ marginTop: 6, fontSize: 10, color: '#444' }}>
          ORDER ID: <span style={{ color: '#666', fontFamily: 'monospace' }}>{pos.order_id}</span>
        </div>
      )}
      {isFailed && (
        <div style={{
          marginTop: 8, padding: '6px 10px',
          background: '#cc444411', border: '1px solid #cc444433',
          borderRadius: 4, fontSize: 11,
        }}>
          <div style={{ color: '#cc4444', fontWeight: 700, marginBottom: 6 }}>
            ✕ Order failed — position held for retry
          </div>
          <div style={{ color: '#cc6644', marginBottom: 8 }}>
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
            style={{ ...styles.deleteBtn, color: '#88aaff', borderColor: '#88aaff33' }}
            onClick={() => monitor.mutate(pos.id)}
            disabled={monitor.isPending}
          >
            {monitor.isPending ? '…' : '⟳ MONITOR'}
          </button>
          <button
            style={{ ...styles.deleteBtn, color: '#aaa', borderColor: '#33333344' }}
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
                  background: '#1a1a1a', color: '#ccc', border: '1px solid #333',
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
            style={{ ...styles.deleteBtn, flex: 1, color: '#ccc', border: '1px solid #333', padding: '4px 8px' }}
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
  const { data, isLoading } = usePositions(isLive ? 'live' : 'paper');
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
              color: isLive ? 'var(--accent)' : '#88aaff',
              background: isLive ? 'var(--accent)18' : '#88aaff18',
              border: `1px solid ${isLive ? 'var(--accent)44' : '#88aaff44'}`,
              borderRadius: 3, padding: '1px 6px',
            }}>
              {isLive ? '● LIVE' : 'PAPER'}
            </span>
          </div>
          {data && (
            <div style={styles.counts}>
              <span style={{ ...styles.countBadge, color: '#44cc88' }}>
                {data.open_count} OPEN
                {data.partially_closed_count > 0 && (
                  <span style={{ color: '#f0c040', marginLeft: 4, fontSize: 10 }}>
                    ({data.partially_closed_count} partial)
                  </span>
                )}
              </span>
              <span style={{ ...styles.countBadge, color: '#888' }}>
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
            style={{ background: '#1a1a2a', color: '#88aaff', border: '1px solid #334', padding: '5px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
            onClick={handleMonitorAll}
            disabled={monitorAll.isPending}
            title="Check all open/partial positions for exit signals"
          >
            {monitorAll.isPending ? '…' : '⟳ REFRESH ALL POSITIONS'}
          </button>
          {!showCloseAllConfirm ? (
            <button
              style={{ background: '#2a1a1a', color: '#cc6644', border: '1px solid #cc664433', padding: '5px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
              onClick={() => setShowCloseAllConfirm(true)}
              disabled={(data?.open_count ?? 0) === 0}
              title="Close all open positions at current market price"
            >
              ✕ CLOSE ALL
            </button>
          ) : (
            <>
              <button
                style={{ background: '#2a0d0d', color: '#cc4444', border: '1px solid #cc4444', padding: '5px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
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
                style={{ background: '#1a1a1a', color: '#555', border: '1px solid #333', padding: '5px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
                onClick={() => setShowCloseAllConfirm(false)}
              >CANCEL</button>
            </>
          )}
          {closeAllResult && (
            <div style={{ background: '#0d1a0d', border: '1px solid #44cc8844', borderRadius: 4, padding: '6px 12px', fontSize: 11, color: '#44cc88', marginTop: 6 }}>
              ✓ Closed {closeAllResult.count} position{closeAllResult.count !== 1 ? 's' : ''} · P&L {closeAllResult.pnl >= 0 ? '+' : ''}${closeAllResult.pnl.toFixed(2)}
            </div>
          )}
          {closeAllError && (
            <div style={{ background: '#1a0d0d', border: '1px solid #cc444444', borderRadius: 4, padding: '6px 12px', fontSize: 11, color: '#cc4444', marginTop: 6 }}>
              Close all failed: {closeAllError}
            </div>
          )}
          <button
            style={{ background: '#1a1a2a', color: '#88aaff', border: '1px solid #334', padding: '5px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
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
