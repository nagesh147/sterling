import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnapshot } from '../hooks/useSnapshot';
import { usePositions } from '../hooks/usePositions';
import { useLivePnl } from '../hooks/useLivePnl';
import { useInstruments } from '../hooks/useInstruments';
import { fmtN, fmtUSD, ivrColor, fmtAge, fmtState } from '../utils/fmt';
import { api } from '../utils/api';

function useDirectEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { underlying: string; direction: string; leverage: number; notes: string }) =>
      api.post('/api/v1/positions/enter-direct', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['positions'] });
      qc.invalidateQueries({ queryKey: ['live-pnl'] });
    },
  });
}

const STATE_COLOR: Record<string, string> = {
  ENTRY_ARMED_PULLBACK: '#44aaff',
  ENTRY_ARMED_CONTINUATION: '#66ccff',
  CONFIRMED_SETUP_ACTIVE: '#f0c040',
  EARLY_SETUP_ACTIVE: '#f0a500',
  FILTERED: '#555', IDLE: '#333',
};

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 10, color: '#555', letterSpacing: 1 }}>{label}</span>
        <span style={{ fontSize: 16, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>{value.toFixed(0)}</span>
      </div>
      <div style={{ height: 6, background: '#1a1a1a', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', borderRadius: 3,
          background: `linear-gradient(90deg, ${color}88, ${color})`,
          transition: 'width 0.4s ease',
        }} />
      </div>
    </div>
  );
}

function BreakdownBar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const color = value >= max * 0.7 ? '#44cc88' : value >= max * 0.4 ? '#f0c040' : '#555';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
      <span style={{ color: '#444', fontSize: 9, width: 55, flexShrink: 0, letterSpacing: 0.5 }}>{label}</span>
      <div style={{ flex: 1, height: 4, background: '#1a1a1a', borderRadius: 2 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: 10, color, width: 22, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
        {typeof value === 'number' ? value.toFixed(0) : '—'}
      </span>
    </div>
  );
}

function STBadge({ trend, label, value, spot }: { trend: number; label: string; value?: number; spot: number }) {
  const c = trend === 1 ? '#44cc88' : trend === -1 ? '#cc4444' : '#333';
  const arrow = trend === 1 ? '▲' : trend === -1 ? '▼' : '·';
  const dist = value && spot ? `${((Math.abs(spot - value) / spot) * 100).toFixed(1)}%` : null;
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
      background: c + '14', border: `1px solid ${c}33`, borderRadius: 4, padding: '5px 8px',
    }}>
      <span style={{ fontSize: 9, color: '#555' }}>{label}</span>
      <span style={{ fontSize: 14, color: c, lineHeight: 1 }}>{arrow}</span>
      {dist && <span style={{ fontSize: 9, color: '#444' }}>{dist}</span>}
    </div>
  );
}

export function InstrumentDetailCard({ underlying }: { underlying: string }) {
  const { data, isLoading, isError, dataUpdatedAt } = useSnapshot(underlying);
  const { data: posData } = usePositions();
  const { data: pnlData } = useLivePnl();
  const { data: instruments } = useInstruments();
  const { mutate: enterDirect, isPending: entering, error: enterError } = useDirectEntry();
  const [showBreakdown, setShowBreakdown] = useState(false);

  const inst = instruments?.instruments.find(i => i.underlying === underlying);
  // inst is used for dvol_symbol — available if needed
  void inst;
  const updatedAt = dataUpdatedAt ? fmtAge(dataUpdatedAt) : '—';

  const openPositions = (posData?.positions ?? []).filter(
    p => p.underlying === underlying && (p.status === 'open' || p.status === 'partially_closed')
  );

  if (isLoading && !data) return (
    <div style={{ background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 20, marginBottom: 16 }}>
      <span style={{ color: '#333', fontSize: 12 }}>Loading {underlying}…</span>
    </div>
  );
  if (isError || !data) return null;

  const stateColor = STATE_COLOR[data.state] ?? '#444';
  const dirColor = data.direction === 'long' ? '#44cc88' : data.direction === 'short' ? '#cc4444' : '#555';
  const isArmed = data.state.startsWith('ENTRY_ARMED');
  const isConfirmed = data.state === 'CONFIRMED_SETUP_ACTIVE';
  const canEnter = (isArmed || isConfirmed) && !openPositions.length;

  const stTriplet = (data.st_trends ?? []).map((t, i) => ({
    trend: t,
    label: ['ST 7,3', 'ST 14,2', 'ST 21,1'][i] ?? `ST${i}`,
    value: (data.st_values ?? [])[i],
  }));

  const breakdown = data.score_breakdown;
  const BREAKDOWN_LABELS: Record<string, [string, number]> = {
    macro_trend: ['MACRO', 20], signal: ['SIGNAL', 20], entry: ['ENTRY', 15],
    contract_health: ['HEALTH', 20], dte: ['DTE', 15], rr: ['R:R', 10],
  };

  return (
    <div style={{ background: '#141414', border: `1px solid ${isArmed || isConfirmed ? stateColor + '44' : '#222'}`, borderRadius: 6, padding: 16, marginBottom: 12 }}>

      {/* header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
            <span style={{ fontSize: 22, fontWeight: 900, letterSpacing: 2, color: '#e0e0e0' }}>{underlying}</span>
            <span style={{ fontSize: 24, fontWeight: 700, color: '#e0e0e0', fontVariantNumeric: 'tabular-nums' }}>
              ${fmtUSD(data.spot_price)}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 5, flexWrap: 'wrap' as const }}>
            <span style={{ fontSize: 10, color: '#888', letterSpacing: 1 }}>{data.macro_regime.toUpperCase()}</span>
            <span style={{ color: '#333' }}>·</span>
            <span style={{ fontSize: 10, color: dirColor, letterSpacing: 1, fontWeight: 700 }}>{data.direction.toUpperCase()}</span>
            {(data.adx ?? 0) > 0 && <span style={{ color: '#444', fontSize: 10 }}>ADX {(data.adx ?? 0).toFixed(0)}</span>}
            {(data.atr_percentile ?? 0) > 0 && (
              <span style={{ fontSize: 10, color: (data.atr_percentile ?? 0) > 65 ? '#f0c040' : '#555' }}>
                ATR {(data.atr_percentile ?? 0).toFixed(0)}%{(data.atr_percentile ?? 0) > 65 ? ' volatile' : ''}
              </span>
            )}
          </div>
        </div>
        <div style={{ textAlign: 'right' as const }}>
          <div style={{
            display: 'inline-block', padding: '4px 12px', borderRadius: 4,
            background: stateColor + '18', border: `1px solid ${stateColor}44`,
            color: stateColor, fontSize: 11, fontWeight: 700, letterSpacing: 1, marginBottom: 4,
          }}>
            {fmtState(data.state).toUpperCase()}
          </div>
          <div style={{ fontSize: 10, color: '#333' }}>{updatedAt}</div>
        </div>
      </div>

      {/* score bars */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 14 }}>
        <ScoreBar label="LONG SCORE" value={data.score_long} color="#44cc88" />
        <div style={{ width: 1, background: '#1e1e1e', flexShrink: 0 }} />
        <ScoreBar label="SHORT SCORE" value={data.score_short} color="#cc4444" />
      </div>

      {/* arrows + exec row */}
      {(data.green_arrow || data.red_arrow || data.all_green || data.all_red) && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' as const }}>
          {data.green_arrow && (
            <span style={{ background: '#44cc8822', color: '#44cc88', border: '1px solid #44cc8855', borderRadius: 4, padding: '4px 12px', fontWeight: 800, fontSize: 13 }}>▲ GREEN ARROW</span>
          )}
          {data.red_arrow && (
            <span style={{ background: '#cc444422', color: '#cc4444', border: '1px solid #cc444455', borderRadius: 4, padding: '4px 12px', fontWeight: 800, fontSize: 13 }}>▼ RED ARROW</span>
          )}
          {data.all_green && !data.green_arrow && (
            <span style={{ background: '#44cc8818', color: '#44cc88', border: '1px solid #44cc8833', borderRadius: 4, padding: '3px 10px', fontSize: 11 }}>ALL GREEN</span>
          )}
          {data.all_red && !data.red_arrow && (
            <span style={{ background: '#cc444418', color: '#cc4444', border: '1px solid #cc444433', borderRadius: 4, padding: '3px 10px', fontSize: 11 }}>ALL RED</span>
          )}
        </div>
      )}

      {/* ST trends */}
      {stTriplet.length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {stTriplet.map((st, i) => (
            <STBadge key={i} trend={st.trend} label={st.label} value={st.value} spot={data.spot_price} />
          ))}
        </div>
      )}

      {/* metrics row */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' as const, marginBottom: 12, padding: '8px 10px', background: '#111', borderRadius: 4 }}>
        {data.ivr != null && (
          <div>
            <div style={{ fontSize: 9, color: '#444', letterSpacing: 1 }}>IVR</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: ivrColor(data.ivr) }}>{data.ivr.toFixed(1)} <span style={{ fontSize: 9, color: '#555' }}>{data.ivr_band}</span></div>
          </div>
        )}
        {data.rsi != null && (
          <div>
            <div style={{ fontSize: 9, color: '#444', letterSpacing: 1 }}>RSI 14</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: (data.rsi ?? 50) > 70 ? '#cc4444' : (data.rsi ?? 50) < 30 ? '#44cc88' : '#e0e0e0' }}>
              {fmtN(data.rsi, 1)}
            </div>
          </div>
        )}
        {data.perp_price != null && (
          <div>
            <div style={{ fontSize: 9, color: '#444', letterSpacing: 1 }}>PERP SPREAD</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: (data.perp_price - data.spot_price) > 0 ? '#44cc88' : '#cc4444' }}>
              {(data.perp_price - data.spot_price) >= 0 ? '+' : ''}{fmtN(data.perp_price - data.spot_price, 0)}
            </div>
          </div>
        )}
        {data.funding_rate != null && (
          <div>
            <div style={{ fontSize: 9, color: '#444', letterSpacing: 1 }}>FUNDING</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: data.funding_rate > 0.001 ? '#f0c040' : data.funding_rate < -0.001 ? '#44aaff' : '#888' }}>
              {(data.funding_rate * 100).toFixed(4)}%
            </div>
          </div>
        )}
        {data.squeezed != null && (
          <div>
            <div style={{ fontSize: 9, color: '#444', letterSpacing: 1 }}>SQUEEZE</div>
            <div style={{ fontSize: 11, fontWeight: 700, color: data.squeezed ? '#f0c040' : '#333' }}>
              {data.squeezed ? 'ACTIVE' : 'OFF'}
            </div>
          </div>
        )}
        <div>
          <div style={{ fontSize: 9, color: '#444', letterSpacing: 1 }}>EXEC MODE</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: data.exec_mode === 'wait' ? '#444' : '#88aaff' }}>
            {data.exec_mode.toUpperCase()} <span style={{ color: '#555', fontSize: 9 }}>{fmtN(data.exec_confidence * 100, 0)}%</span>
          </div>
        </div>
      </div>

      {/* exec reason */}
      {data.exec_reason && data.exec_reason !== 'ok' && (
        <div style={{ fontSize: 11, color: '#555', marginBottom: 10, fontStyle: 'italic' }}>
          {data.exec_reason}
        </div>
      )}

      {/* score breakdown (collapsible) */}
      {breakdown && Object.keys(breakdown).filter(k => k !== 'total' && k !== 'veto_reason').length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <button
            onClick={() => setShowBreakdown(v => !v)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#444', fontSize: 10, letterSpacing: 1, padding: '2px 0', fontFamily: 'inherit' }}
          >
            SCORE BREAKDOWN {showBreakdown ? '▲' : '▼'}
          </button>
          {showBreakdown && (
            <div style={{ marginTop: 8, padding: '8px 0' }}>
              {Object.entries(BREAKDOWN_LABELS).map(([key, [label, maxVal]]) => {
                const val = Number(breakdown[key] ?? 0);
                if (!val && val !== 0) return null;
                return <BreakdownBar key={key} label={label} value={val} max={maxVal} />;
              })}
              {breakdown.veto_reason && (
                <div style={{ fontSize: 10, color: '#cc4444', marginTop: 4 }}>Veto: {breakdown.veto_reason}</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* open position P&L */}
      {openPositions.length > 0 && (
        <div style={{ marginBottom: 12, padding: '8px 10px', background: '#0f1a0f', border: '1px solid #44cc8833', borderRadius: 4 }}>
          <div style={{ fontSize: 9, color: '#44cc88', letterSpacing: 1, marginBottom: 4 }}>OPEN POSITION</div>
          {openPositions.map(pos => {
            const pnl = pnlData?.positions?.find(p => p.position_id === pos.id);
            return (
              <div key={pos.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: '#888' }}>{pos.sized_trade?.structure?.structure_type?.replace(/_/g, ' ') ?? 'position'} · {pos.sized_trade?.contracts ?? '?'} contracts</span>
                <span style={{ color: pnl?.estimated_pnl_usd != null && pnl.estimated_pnl_usd >= 0 ? '#44cc88' : '#cc4444', fontWeight: 700 }}>
                  {pnl?.estimated_pnl_usd != null ? `${pnl.estimated_pnl_usd >= 0 ? '+' : ''}$${Math.abs(pnl.estimated_pnl_usd).toFixed(0)}` : '—'}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* enter button */}
      {canEnter && (
        <div style={{ marginTop: 4 }}>
          {enterError && <div style={{ color: '#cc4444', fontSize: 11, marginBottom: 6 }}>{(enterError as Error).message}</div>}
          <button
            disabled={entering}
            onClick={() => enterDirect({
              underlying,
              direction: data.direction,
              leverage: 1,
              notes: `Signal entry — ${data.state}`,
            })}
            style={{
              width: '100%', padding: '10px 0',
              background: isArmed ? '#1a2a1a' : '#1a1a2a',
              color: isArmed ? '#44cc88' : '#88aaff',
              border: `1px solid ${isArmed ? '#44cc88' : '#88aaff'}`,
              borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit',
              fontSize: 13, fontWeight: 700, letterSpacing: 1,
            }}
          >
            {entering ? 'Entering…' : `ENTER ${data.direction.toUpperCase()} POSITION`}
          </button>
        </div>
      )}
      {openPositions.length > 0 && (
        <div style={{ fontSize: 10, color: '#444', textAlign: 'center' as const, marginTop: 4 }}>
          Position already open — close it before entering a new one
        </div>
      )}
    </div>
  );
}
