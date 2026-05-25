import React, { useState } from 'react';
import { usePositions, useClosePosition } from '../hooks/usePositions';
import { useLivePnl } from '../hooks/useLivePnl';
import { useExchanges } from '../hooks/useExchanges';
import { fmtUSD } from '../utils/fmt';

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtTime(ms: number): string {
  return new Date(ms).toLocaleString('en-IN', {
    month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: true,
  });
}

function fmtPrice(v: number | null | undefined, decimals = 0): string {
  if (v == null || v === 0) return '—';
  return `$${fmtUSD(v, v < 10 ? 2 : decimals)}`;
}

/** Format a P&L value with appropriate precision — never rounds small amounts to $0. */
function fmtPnl(v: number | null | undefined): string {
  if (v == null || v === 0) return '—';
  const abs = Math.abs(v);
  const sign = v >= 0 ? '+' : '-';
  if (abs >= 1000) return `${sign}$${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  if (abs >= 1)    return `${sign}$${abs.toFixed(2)}`;
  if (abs >= 0.01) return `${sign}$${abs.toFixed(2)}`;
  return '—';   // sub-cent noise — not meaningful
}

// For failed positions where entry is 0, use exit price as a reference if available
function resolveEntryPrice(pos: { entry_spot_price: number; exit_spot_price?: number; order_status?: string | null }): { price: number | null; isProxy: boolean } {
  if (pos.entry_spot_price > 0) return { price: pos.entry_spot_price, isProxy: false };
  // Failed order — order never filled, no real entry. Show exit price as a reference.
  if (pos.exit_spot_price && pos.exit_spot_price > 0) return { price: pos.exit_spot_price, isProxy: true };
  return { price: null, isProxy: false };
}

function fmtDuration(openMs: number, closeMs?: number): string {
  const diff = (closeMs ?? Date.now()) - openMs;
  if (diff <= 0) return '—';
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  const s = Math.floor((diff % 60_000) / 1_000);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  if (s > 0) return `${s}s`;
  return '<1s';
}

const ACCENT  = 'var(--accent)';
const DANGER  = 'var(--danger)';

function DirBadge({ dir }: { dir: string }) {
  const color = dir === 'long' ? ACCENT : dir === 'short' ? DANGER : 'var(--text-dim)';
  const label = dir === 'long' ? '↑ LONG' : dir === 'short' ? '↓ SHORT' : dir.toUpperCase();
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
      color, background: color + '18', borderRadius: 4, padding: '2px 6px',
    }}>
      {label}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; label: string }> = {
    open:             { color: ACCENT,             label: '● OPEN' },
    partially_closed: { color: 'var(--warning)',   label: '◑ PARTIAL' },
    closed:           { color: 'var(--text-dim)',  label: 'CLOSED' },
  };
  const { color, label } = map[status] ?? { color: 'var(--text-faint)', label: status.toUpperCase() };
  return (
    <span style={{ fontSize: 8, fontWeight: 700, color, letterSpacing: '0.08em' }}>{label}</span>
  );
}

function PriceCell({ label, value, color }: { label: string; value: string | null; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.08em', color: 'var(--text-dim)', whiteSpace: 'nowrap' as const }}>
        {label}
      </span>
      <span style={{
        fontSize: 13, fontWeight: 700, fontVariantNumeric: 'tabular-nums',
        color: color ?? 'var(--text-primary)', letterSpacing: '-0.01em',
      }}>
        {value ?? '—'}
      </span>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function PositionsStrip() {
  const { data: exData } = useExchanges();
  const delta  = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const isLive = !!(delta?.has_credentials && !delta.is_paper);
  const mode   = isLive ? 'live' : 'paper';

  const { data: posData }               = usePositions(mode);
  const { data: pnlData }               = useLivePnl();
  const { mutate: closePos, isPending } = useClosePosition();

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter]         = useState<'all' | 'open' | 'closed'>('all');

  const all    = posData?.positions ?? [];
  const open   = all.filter(p => p.status === 'open' || p.status === 'partially_closed');
  const closed = all.filter(p => p.status === 'closed');

  const livePnl     = pnlData?.total_estimated_pnl_usd ?? 0;
  const realizedPnl = closed.reduce((s, p) => s + (p.realized_pnl_usd ?? 0), 0);

  const displayed = filter === 'open'
    ? open
    : filter === 'closed'
      ? closed
      : [...open, ...closed];

  const modeColor = isLive ? ACCENT : 'var(--blue)';

  if (all.length === 0) {
    return (
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 10, padding: '36px 24px', textAlign: 'center',
      }}>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600 }}>
          No positions yet
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>
          Open a signal card to enter a trade. {isLive ? 'Live' : 'Paper'} positions appear here instantly.
        </div>
      </div>
    );
  }

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      overflow: 'hidden',
    }}>

      {/* ── Header bar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--text-primary)',
          }}>
            ORDER BOOK
          </span>
          <span style={{
            fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
            color: modeColor, background: modeColor + '14', borderRadius: 4, padding: '2px 7px',
          }}>
            {isLive ? '● LIVE' : 'PAPER'}
          </span>
        </div>

        {/* Aggregate stats */}
        <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
          <StatChip label="OPEN" value={String(open.length)} color={open.length > 0 ? 'var(--text-primary)' : 'var(--text-dim)'} />
          {open.length > 0 && (
            <StatChip
              label="LIVE P&L"
              value={fmtPnl(livePnl)}
              color={livePnl >= 0 ? ACCENT : DANGER}
            />
          )}
          {closed.length > 0 && (
            <StatChip
              label="REALIZED"
              value={fmtPnl(realizedPnl)}
              color={realizedPnl >= 0 ? ACCENT : DANGER}
            />
          )}
          <StatChip label="CLOSED" value={String(closed.length)} color="var(--text-dim)" />
        </div>
      </div>

      {/* ── Filter pills ── */}
      <div style={{
        display: 'flex', gap: 4, padding: '8px 16px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg)',
      }}>
        {(['all', 'open', 'closed'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: '3px 12px', borderRadius: 5, fontSize: 9, fontWeight: 600,
              letterSpacing: '0.08em', cursor: 'pointer', fontFamily: 'inherit',
              border: filter === f ? '1px solid var(--border-light)' : '1px solid transparent',
              background: filter === f ? 'var(--bg-card)' : 'transparent',
              color: filter === f ? 'var(--text-primary)' : 'var(--text-dim)',
              transition: 'all 0.1s',
            }}
          >
            {f.toUpperCase()}
            <span style={{ marginLeft: 5, color: 'var(--text-faint)', fontWeight: 400 }}>
              {f === 'all' ? all.length : f === 'open' ? open.length : closed.length}
            </span>
          </button>
        ))}
      </div>

      {/* ── Position rows ── */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {displayed.map((pos, idx) => {
          const st       = pos.sized_trade;
          const dir      = st?.structure?.direction ?? '';
          const contracts = st?.contracts ?? 1;
          const pnlEntry = pnlData?.positions?.find(p => p.position_id === pos.id);
          const livePnlUsd = pnlEntry?.estimated_pnl_usd ?? null;
          const entryIsValid = pos.entry_spot_price > 0;
          const { price: entryDisplayPrice, isProxy: entryIsProxy } = resolveEntryPrice(pos);
          // Suppress P&L when entry price is 0 — calculation is meaningless (order never filled)
          const pnlUsd   = !entryIsValid ? null : pos.status === 'closed' ? (pos.realized_pnl_usd ?? null) : livePnlUsd;
          const pnlColor = pnlUsd != null ? (pnlUsd >= 0 ? ACCENT : DANGER) : 'var(--text-faint)';
          const isOpen   = pos.status === 'open' || pos.status === 'partially_closed';
          const currentSpot = pnlEntry?.current_spot ?? null;
          const isExpanded = expandedId === pos.id;

          const initialSl  = pos.initial_sl;
          const currentSl  = pos.current_sl;
          const initialTp  = pos.initial_tp;
          const currentTp  = pos.current_tp;

          let trailStop: number | null = null;
          try {
            const ts = JSON.parse((pos as any).trail_stop_json ?? 'null');
            if (ts?.current_stop) trailStop = Number(ts.current_stop);
          } catch { /* ignore */ }

          return (
            <div
              key={pos.id}
              style={{
                borderBottom: idx < displayed.length - 1 ? '1px solid var(--border)' : 'none',
              }}
            >
              {/* ── Main row ── */}
              <div
                onClick={() => setExpandedId(isExpanded ? null : pos.id)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '100px 1fr 1fr 1fr 1fr auto',
                  alignItems: 'center',
                  gap: 12,
                  padding: '12px 16px',
                  cursor: 'pointer',
                  borderLeft: `3px solid ${dir === 'long' ? ACCENT : dir === 'short' ? DANGER : 'var(--border)'}`,
                  background: isOpen ? 'var(--bg-card)' : 'var(--bg)',
                  transition: 'background 0.1s',
                }}
              >
                {/* Column 1: Symbol + direction + status */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' as const }}>
                    <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '0.02em' }}>
                      {pos.underlying}
                    </span>
                    {pos.status === 'partially_closed' && (
                      <span style={{ fontSize: 8, fontWeight: 700, color: 'var(--warning)', background: 'var(--warning)14', borderRadius: 3, padding: '1px 5px' }}>PARTIAL</span>
                    )}
                    {pos.order_status === 'failed' && (
                      <span style={{ fontSize: 8, fontWeight: 700, color: 'var(--danger)', background: 'var(--danger)14', borderRadius: 3, padding: '1px 5px' }}>FAILED</span>
                    )}
                    {pos.entry_spot_price === 0 && (
                      <span style={{ fontSize: 8, fontWeight: 700, color: 'var(--warning)', background: 'var(--warning)14', borderRadius: 3, padding: '1px 5px' }} title="Entry price not recorded — order may not have filled">NO FILL</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <DirBadge dir={dir} />
                    <StatusBadge status={pos.status} />
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--text-faint)' }}>
                    {contracts} ct · {pos.is_paper ? 'PAPER' : 'LIVE'}
                    {pos.mode ? ` · ${pos.mode.toUpperCase()}` : ''}
                  </div>
                </div>

                {/* Column 2: Entry — proxy label when order never filled */}
                <PriceCell
                  label={entryIsProxy ? 'ENTRY (ref)' : 'ENTRY'}
                  value={fmtPrice(entryDisplayPrice)}
                  color={entryIsProxy ? 'var(--text-dim)' : undefined}
                />

                {/* Column 3: Current / Exit */}
                {isOpen ? (
                  <PriceCell
                    label="NOW"
                    value={fmtPrice(currentSpot)}
                  />
                ) : (
                  <PriceCell
                    label="EXIT"
                    value={fmtPrice(pos.exit_spot_price)}
                  />
                )}

                {/* Column 4: SL / TP summary */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {(currentSl ?? initialSl) ? (
                    <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
                      <span style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.08em', color: 'var(--text-dim)' }}>SL</span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: DANGER, fontVariantNumeric: 'tabular-nums' }}>
                        ${fmtUSD(currentSl ?? initialSl ?? 0, 0)}
                        {trailStop ? ' 🔄' : ''}
                      </span>
                    </div>
                  ) : <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>No SL</span>}

                  {(currentTp ?? initialTp) ? (
                    <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
                      <span style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.08em', color: 'var(--text-dim)' }}>TP</span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: ACCENT, fontVariantNumeric: 'tabular-nums' }}>
                        ${fmtUSD(currentTp ?? initialTp ?? 0, 0)}
                      </span>
                    </div>
                  ) : null}
                </div>

                {/* Column 5: P&L */}
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-dim)', marginBottom: 3 }}>
                    {isOpen ? 'LIVE P&L' : 'REALIZED'}
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: pnlColor, fontVariantNumeric: 'tabular-nums' }}>
                    {fmtPnl(pnlUsd)}
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 2 }}>
                    {fmtDuration(pos.entry_timestamp_ms, pos.exit_timestamp_ms ?? undefined)}
                  </div>
                </div>

                {/* Column 6: Actions */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5, alignItems: 'flex-end' }}>
                  {isOpen && (
                    <button
                      disabled={isPending}
                      onClick={(e) => {
                        e.stopPropagation();
                        closePos({ id: pos.id, exit_spot_price: currentSpot ?? pos.entry_spot_price });
                      }}
                      style={{
                        background: 'var(--danger)18',
                        border: '1px solid var(--danger)40',
                        color: 'var(--danger)',
                        borderRadius: 6,
                        padding: '5px 12px',
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                        fontSize: 10,
                        fontWeight: 700,
                        opacity: isPending ? 0.5 : 1,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {isPending ? '…' : '✕ Close'}
                    </button>
                  )}
                  <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>
                    {isExpanded ? '▲' : '▼'} details
                  </span>
                </div>
              </div>

              {/* ── Expanded detail row ── */}
              {isExpanded && (
                <div style={{
                  background: 'var(--bg)',
                  borderTop: '1px solid var(--border)',
                  padding: '14px 20px 14px 21px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                  gap: '12px 24px',
                }}>
                  {/* Timestamps */}
                  <DetailField label="OPENED" value={fmtTime(pos.entry_timestamp_ms)} />
                  {pos.exit_timestamp_ms && (
                    <DetailField label="CLOSED" value={fmtTime(pos.exit_timestamp_ms)} />
                  )}
                  <DetailField label="DURATION" value={fmtDuration(pos.entry_timestamp_ms, pos.exit_timestamp_ms ?? undefined)} />

                  {/* Prices */}
                  <DetailField
                    label={entryIsProxy ? 'ENTRY PRICE (ref — exit used, order not filled)' : 'ENTRY PRICE'}
                    value={fmtPrice(entryDisplayPrice)}
                    mono
                    color={entryIsProxy ? 'var(--text-dim)' : undefined}
                  />
                  {pos.exit_spot_price != null && (
                    <DetailField label="EXIT PRICE" value={fmtPrice(pos.exit_spot_price)} mono />
                  )}
                  {currentSpot != null && isOpen && (
                    <DetailField label="CURRENT PRICE" value={fmtPrice(currentSpot)} mono />
                  )}

                  {/* Stop Loss */}
                  {initialSl != null && (
                    <DetailField label="INITIAL SL" value={fmtPrice(initialSl)} mono color={DANGER} />
                  )}
                  {currentSl != null && currentSl !== initialSl && (
                    <DetailField label="CURRENT SL" value={fmtPrice(currentSl)} mono color={DANGER} />
                  )}
                  {trailStop != null && (
                    <DetailField label="TRAIL STOP" value={fmtPrice(trailStop)} mono color="var(--warning)" />
                  )}
                  {pos.trail_mode && (
                    <DetailField label="TRAIL MODE" value={pos.trail_mode.toUpperCase()} />
                  )}

                  {/* Take Profit */}
                  {initialTp != null && (
                    <DetailField label="INITIAL TP" value={fmtPrice(initialTp)} mono color={ACCENT} />
                  )}
                  {currentTp != null && currentTp !== initialTp && (
                    <DetailField label="CURRENT TP" value={fmtPrice(currentTp)} mono color={ACCENT} />
                  )}

                  {/* Position sizing */}
                  <DetailField label="CONTRACTS" value={String(contracts)} mono />
                  {st?.position_value != null && (
                    <DetailField label="NOTIONAL" value={fmtPrice(st.position_value)} mono />
                  )}
                  {st?.max_risk_usd != null && (
                    <DetailField label="MAX RISK" value={fmtPrice(st.max_risk_usd)} mono color={DANGER} />
                  )}
                  {st?.capital_at_risk_pct != null && (
                    <DetailField label="RISK %" value={`${(st.capital_at_risk_pct * 100).toFixed(1)}%`} mono color={DANGER} />
                  )}

                  {/* Trade structure */}
                  {st?.structure?.score != null && (
                    <DetailField label="SCORE" value={String(Math.round(st.structure.score))} mono />
                  )}
                  {st?.structure?.risk_reward != null && (
                    <DetailField label="R:R" value={`${st.structure.risk_reward.toFixed(1)}:1`} mono />
                  )}

                  {/* Exchange / order */}
                  {pos.order_id && (
                    <DetailField label="ORDER ID" value={pos.order_id} mono />
                  )}
                  {pos.order_status && (
                    <DetailField label="ORDER STATUS" value={pos.order_status.toUpperCase()} />
                  )}
                  <DetailField label="MODE" value={pos.is_paper ? 'PAPER' : 'LIVE'} />

                  {/* P&L */}
                  {pos.realized_pnl_usd != null && (
                    <DetailField
                      label="REALIZED P&L"
                      value={fmtPnl(pos.realized_pnl_usd)}
                      mono
                      color={pos.realized_pnl_usd >= 0 ? ACCENT : DANGER}
                    />
                  )}
                  {livePnlUsd != null && isOpen && entryIsValid && (
                    <DetailField
                      label="LIVE P&L"
                      value={fmtPnl(livePnlUsd)}
                      mono
                      color={livePnlUsd >= 0 ? ACCENT : DANGER}
                    />
                  )}
                  {!entryIsValid && (
                    <DetailField
                      label="P&L STATUS"
                      value="N/A — order not filled"
                      color="var(--warning)"
                    />
                  )}

                  {/* Notes */}
                  {pos.notes && (
                    <div style={{ gridColumn: '1 / -1' }}>
                      <div style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-dim)', marginBottom: 3 }}>NOTES</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>{pos.notes}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Small helpers ─────────────────────────────────────────────────────────────

function StatChip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ textAlign: 'right' }}>
      <div style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-faint)', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  );
}

function DetailField({
  label, value, mono = false, color,
}: {
  label: string; value: string; mono?: boolean; color?: string;
}) {
  return (
    <div>
      <div style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-dim)', marginBottom: 3 }}>
        {label}
      </div>
      <div style={{
        fontSize: 12,
        fontWeight: 600,
        color: color ?? 'var(--text-primary)',
        fontFamily: mono ? 'monospace' : 'inherit',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {value}
      </div>
    </div>
  );
}
