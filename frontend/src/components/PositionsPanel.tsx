import React, { useState } from 'react';
import { usePositions, useEnterPosition, useClosePosition, useDeletePosition, useCloseAll } from '../hooks/usePositions';
import { useMonitorPosition, useMonitorAll } from '../hooks/useMonitorPosition';
import { useLivePnl } from '../hooks/useLivePnl';
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

  return (
    <div style={styles.posCard}>
      <div style={styles.posHeader}>
        <span style={styles.posType}>
          {pos.underlying} · {s.structure_type}
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
  const { data, isLoading } = usePositions();
  const enter = useEnterPosition();
  const monitorAll = useMonitorAll();
  const closeAll = useCloseAll();
  const [showCloseAllConfirm, setShowCloseAllConfirm] = useState(false);
  const hasOpen = (data?.open_count ?? 0) > 0;
  const { data: livePnlData } = useLivePnl(hasOpen);
  const livePnlMap = Object.fromEntries(
    (livePnlData?.positions ?? []).map(p => [p.position_id, p.estimated_pnl_usd])
  );

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div>
          <div style={styles.title}>PAPER POSITIONS</div>
          {data && (
            <div style={styles.counts}>
              <span style={{ ...styles.countBadge, color: '#44cc88' }}>
                {data.open_count} OPEN
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
            onClick={() => monitorAll.mutate()}
            disabled={monitorAll.isPending}
            title="Check all open/partial positions for exit signals"
          >
            {monitorAll.isPending ? '…' : '⟳ MONITOR ALL'}
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
                onClick={() => { closeAll.mutate(); setShowCloseAllConfirm(false); }}
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
