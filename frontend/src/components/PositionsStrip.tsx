import React from 'react';
import { usePositions, useClosePosition } from '../hooks/usePositions';
import { useLivePnl } from '../hooks/useLivePnl';
import { fmtUSD } from '../utils/fmt';

export function PositionsStrip() {
  const { data: posData } = usePositions();
  const { data: pnlData } = useLivePnl();
  const { mutate: closePos, isPending: closing } = useClosePosition();

  const open = (posData?.positions ?? []).filter(
    p => p.status === 'open' || p.status === 'partially_closed'
  );
  const closed = (posData?.positions ?? []).filter(p => p.status === 'closed');
  const totalRealizedPnl = closed.reduce((s, p) => s + (p.realized_pnl_usd ?? 0), 0);
  const totalLivePnl = pnlData?.total_estimated_pnl_usd ?? 0;

  if (open.length === 0 && closed.length === 0) return null;

  return (
    <div style={{ background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 14, marginBottom: 14 }}>
      {/* summary row */}
      <div style={{ display: 'flex', gap: 20, marginBottom: open.length > 0 ? 12 : 0, flexWrap: 'wrap' as const }}>
        <div>
          <div style={{ fontSize: 9, color: '#444', letterSpacing: 1 }}>OPEN</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: open.length > 0 ? '#e0e0e0' : '#333' }}>{open.length}</div>
        </div>
        {open.length > 0 && (
          <div>
            <div style={{ fontSize: 9, color: '#444', letterSpacing: 1 }}>LIVE P&amp;L</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: totalLivePnl >= 0 ? '#44cc88' : '#cc4444', fontVariantNumeric: 'tabular-nums' }}>
              {totalLivePnl >= 0 ? '+' : ''}${Math.abs(totalLivePnl).toFixed(0)}
            </div>
          </div>
        )}
        {closed.length > 0 && (
          <div>
            <div style={{ fontSize: 9, color: '#444', letterSpacing: 1 }}>REALIZED</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: totalRealizedPnl >= 0 ? '#44cc88' : '#cc4444', fontVariantNumeric: 'tabular-nums' }}>
              {totalRealizedPnl >= 0 ? '+' : ''}${Math.abs(totalRealizedPnl).toFixed(0)}
            </div>
          </div>
        )}
        <div>
          <div style={{ fontSize: 9, color: '#444', letterSpacing: 1 }}>CLOSED</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#555' }}>{closed.length}</div>
        </div>
      </div>

      {/* open positions list */}
      {open.map(pos => {
        const pnl = pnlData?.positions?.find(p => p.position_id === pos.id);
        const pnlUsd = pnl?.estimated_pnl_usd ?? null;
        const pnlColor = pnlUsd != null && pnlUsd >= 0 ? '#44cc88' : '#cc4444';
        const st = pos.sized_trade;
        const spot = pnl?.current_spot ?? pos.entry_spot_price;

        return (
          <div key={pos.id} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '7px 10px', background: '#111', border: '1px solid #1e1e1e',
            borderRadius: 4, marginBottom: 6, gap: 10,
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#e0e0e0' }}>{pos.underlying}</span>
                <span style={{ fontSize: 10, color: pos.status === 'partially_closed' ? '#f0c040' : '#555' }}>
                  {pos.status === 'partially_closed' ? 'PARTIAL' : 'OPEN'}
                </span>
                <span style={{ fontSize: 10, color: '#444' }}>
                  {st?.structure?.direction?.toUpperCase()} {st?.structure?.structure_type?.replace(/_/g, ' ')}
                </span>
              </div>
              <div style={{ fontSize: 10, color: '#444', marginTop: 2 }}>
                {st?.contracts ?? '?'} contracts · entry ${fmtUSD(pos.entry_spot_price)} · now ${fmtUSD(spot ?? undefined)}
              </div>
            </div>
            <div style={{ textAlign: 'right' as const, flexShrink: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 800, color: pnlColor, fontVariantNumeric: 'tabular-nums' }}>
                {pnlUsd != null ? `${pnlUsd >= 0 ? '+' : ''}$${Math.abs(pnlUsd).toFixed(0)}` : '—'}
              </div>
              <button
                disabled={closing}
                onClick={() => closePos({ id: pos.id, exit_spot_price: spot ?? pos.entry_spot_price })}
                style={{
                  marginTop: 3, background: 'none', border: '1px solid #cc444444',
                  color: '#cc4444', borderRadius: 3, padding: '2px 8px',
                  cursor: 'pointer', fontFamily: 'inherit', fontSize: 10,
                }}
              >
                Close
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
