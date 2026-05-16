import React from 'react';
import { usePositions, useClosePosition } from '../hooks/usePositions';
import { useLivePnl } from '../hooks/useLivePnl';
import { useExchanges } from '../hooks/useExchanges';
import { fmtUSD } from '../utils/fmt';

export function PositionsStrip() {
  const { data: exData } = useExchanges();
  const delta   = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const isLive  = !!(delta?.has_credentials && !delta.is_paper);
  const mode    = isLive ? 'live' : 'paper';

  const { data: posData }               = usePositions(mode);
  const { data: pnlData }               = useLivePnl();
  const { mutate: closePos, isPending } = useClosePosition();

  const open   = (posData?.positions ?? []).filter(p => p.status === 'open' || p.status === 'partially_closed');
  const closed = (posData?.positions ?? []).filter(p => p.status === 'closed');
  const realizedPnl = closed.reduce((s, p) => s + (p.realized_pnl_usd ?? 0), 0);
  const livePnl     = pnlData?.total_estimated_pnl_usd ?? 0;

  if (open.length === 0 && closed.length === 0) {
    return (
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 8, padding: '32px 20px', textAlign: 'center',
      }}>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 6 }}>No positions yet</div>
        <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>
          Open a signal card to enter a trade. Paper positions appear here instantly.
        </div>
      </div>
    );
  }

  const modeColor  = isLive ? 'var(--accent)' : '#88aaff';
  const modeBg     = isLive ? '#0f2a1a' : '#0d1230';
  const modeBorder = isLive ? 'var(--accent)' : '#4466bb';

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: `1px solid var(--border)`,
      borderRadius: 8,
      overflow: 'hidden',
      marginBottom: 16,
    }}>
      {/* header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 14px',
        background: modeBg,
        borderBottom: `1px solid ${modeBorder}33`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 11, fontWeight: 900, color: modeColor, letterSpacing: 2 }}>
            POSITIONS
          </span>
          <span style={{
            fontSize: 9, fontWeight: 700, letterSpacing: 1,
            color: modeColor, background: modeColor + '18',
            border: `1px solid ${modeColor}44`,
            borderRadius: 3, padding: '1px 6px',
          }}>
            {isLive ? '● LIVE' : 'PAPER'}
          </span>
        </div>

        {/* stats row */}
        <div style={{ display: 'flex', gap: 18, alignItems: 'center' }}>
          <Stat label="OPEN" value={String(open.length)} color={open.length > 0 ? 'var(--text-primary)' : 'var(--text-faint)'} />
          {open.length > 0 && (
            <Stat
              label="LIVE P&L"
              value={(livePnl >= 0 ? '+' : '') + '$' + Math.abs(livePnl).toFixed(0)}
              color={livePnl >= 0 ? 'var(--accent)' : 'var(--danger)'}
            />
          )}
          {closed.length > 0 && (
            <Stat
              label="REALIZED"
              value={(realizedPnl >= 0 ? '+' : '') + '$' + Math.abs(realizedPnl).toFixed(0)}
              color={realizedPnl >= 0 ? 'var(--accent)' : 'var(--danger)'}
            />
          )}
          <Stat label="CLOSED" value={String(closed.length)} color="var(--text-dim)" />
        </div>
      </div>

      {/* open positions */}
      {open.length > 0 && (
        <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {open.map(pos => {
            const pnl      = pnlData?.positions?.find(p => p.position_id === pos.id);
            const pnlUsd   = pnl?.estimated_pnl_usd ?? null;
            const pnlColor = pnlUsd != null && pnlUsd >= 0 ? 'var(--accent)' : 'var(--danger)';
            const st       = pos.sized_trade;
            const spot     = pnl?.current_spot ?? pos.entry_spot_price;
            const dir      = st?.structure?.direction ?? '';
            const dirColor = dir === 'long' ? 'var(--accent)' : dir === 'short' ? 'var(--danger)' : 'var(--text-dim)';

            return (
              <div key={pos.id} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '9px 12px',
                background: 'var(--bg)',
                border: `1px solid ${pnlUsd != null && pnlUsd >= 0 ? 'var(--accent)22' : 'var(--border)'}`,
                borderLeft: `3px solid ${dirColor}`,
                borderRadius: 5,
              }}>
                {/* symbol + direction */}
                <div style={{ minWidth: 100 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--text-primary)' }}>{pos.underlying}</span>
                    <span style={{
                      fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
                      color: dirColor, background: dirColor + '18',
                      border: `1px solid ${dirColor}44`, borderRadius: 3, padding: '1px 5px',
                    }}>
                      {dir === 'long' ? '↑ LONG' : dir === 'short' ? '↓ SHORT' : dir.toUpperCase()}
                    </span>
                    {pos.status === 'partially_closed' && (
                      <span style={{ fontSize: 9, color: 'var(--warning)', background: '#f0c04018', border: '1px solid #f0c04044', borderRadius: 3, padding: '1px 5px' }}>PARTIAL</span>
                    )}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 2 }}>
                    {st?.contracts ?? '?'} contracts · entry ${fmtUSD(pos.entry_spot_price)}
                  </div>
                </div>

                {/* price */}
                <div style={{ flex: 1, display: 'flex', gap: 10, alignItems: 'center' }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 2 }}>NOW</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>${fmtUSD(spot ?? undefined)}</div>
                  </div>
                  {(pos as any).trail_stop_json && (() => {
                    try {
                      const ts = JSON.parse((pos as any).trail_stop_json);
                      if (!ts.current_stop) return null;
                      return (
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 2 }}>TRAIL SL</div>
                          <div style={{ fontSize: 12, fontWeight: 700, color: '#f0c040', fontVariantNumeric: 'tabular-nums' }}>
                            ${Number(ts.current_stop).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                          </div>
                        </div>
                      );
                    } catch { return null; }
                  })()}
                </div>

                {/* P&L + close */}
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontSize: 16, fontWeight: 800, color: pnlColor, fontVariantNumeric: 'tabular-nums' }}>
                    {pnlUsd != null ? `${pnlUsd >= 0 ? '+' : ''}$${Math.abs(pnlUsd).toFixed(0)}` : '—'}
                  </div>
                  <button
                    disabled={isPending}
                    onClick={() => closePos({ id: pos.id, exit_spot_price: spot ?? pos.entry_spot_price })}
                    style={{
                      marginTop: 4, background: 'none',
                      border: '1px solid var(--danger)44',
                      color: 'var(--danger)', borderRadius: 3,
                      padding: '2px 10px', cursor: 'pointer',
                      fontFamily: 'inherit', fontSize: 10, letterSpacing: 0.5,
                      opacity: isPending ? 0.5 : 1,
                    }}
                  >
                    {isPending ? '…' : 'Close'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ textAlign: 'right' }}>
      <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  );
}
