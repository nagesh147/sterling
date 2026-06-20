import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useEngineOpenPositions, useCloseEnginePosition } from '../../hooks/useTripleSupertrend';
import type { EngineOpenPosition, EngineVehicle } from '../../types/kiteEngine';

// ─── Vehicle badge ────────────────────────────────────────────────────────────

const VEHICLE_META: Record<EngineVehicle, { label: string; color: string; bg: string }> = {
  otm_options:     { label: 'OTM',       color: '#1565c0', bg: '#e3f2fd' },
  deep_itm_options:{ label: 'Deep-ITM',  color: '#e65100', bg: '#fff3e0' },
  futures:         { label: 'Futures',   color: '#2e7d32', bg: '#e8f5e9' },
};

function VehicleBadge({ vehicle }: { vehicle: EngineVehicle }) {
  const m = VEHICLE_META[vehicle] ?? { label: vehicle, color: '#666', bg: '#f5f5f5' };
  return (
    <span style={{
      display: 'inline-block', padding: '1px 7px', borderRadius: 10,
      fontSize: 10, fontWeight: 600, letterSpacing: 0.4,
      color: m.color, background: m.bg, border: `1px solid ${m.color}30`,
    }}>
      {m.label}
    </span>
  );
}

function DirectionBadge({ direction }: { direction: 'long' | 'short' }) {
  const isLong = direction === 'long';
  return (
    <span style={{
      display: 'inline-block', padding: '1px 7px', borderRadius: 10,
      fontSize: 10, fontWeight: 600, letterSpacing: 0.4,
      color: isLong ? k.green : k.red,
      background: isLong ? '#e8f5e9' : '#ffebee',
      border: `1px solid ${isLong ? k.green : k.red}30`,
    }}>
      {isLong ? '▲ Long' : '▼ Short'}
    </span>
  );
}

function StatusDot({ status }: { status: string }) {
  const color = status === 'open' ? k.green : status === 'pending' ? k.orange : '#aaa';
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
      background: color, marginRight: 5, verticalAlign: 'middle',
    }} />
  );
}

// ─── Row ─────────────────────────────────────────────────────────────────────

function PositionRow({ p, onClose }: { p: EngineOpenPosition; onClose: (sym: string) => void }) {
  const [confirm, setConfirm] = useState(false);

  const fillPct = p.fill_price > 0 && p.entry_premium > 0
    ? ((p.fill_price - p.entry_premium) / p.entry_premium * 100).toFixed(1)
    : null;
  const age = p.opened_ms ? Math.round((Date.now() - p.opened_ms) / 60_000) : null;

  return (
    <tr style={{ borderBottom: `1px solid ${k.border}` }}>
      <td style={{ padding: '8px 10px', whiteSpace: 'nowrap' }}>
        <StatusDot status={p.status} />
        <span style={{ fontWeight: 500, fontSize: 12 }}>{p.symbol}</span>
        {p.underlying && (
          <span style={{ color: '#888', fontSize: 11, marginLeft: 6 }}>{p.underlying}</span>
        )}
      </td>
      <td style={{ padding: '8px 10px' }}>
        <VehicleBadge vehicle={p.vehicle} />
      </td>
      <td style={{ padding: '8px 10px' }}>
        <DirectionBadge direction={p.direction} />
      </td>
      <td style={{ padding: '8px 10px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontSize: 12 }}>
        {p.qty}
        {p.lot_size > 0 && (
          <span style={{ color: '#888', fontSize: 11 }}> ({p.qty / p.lot_size}L)</span>
        )}
      </td>
      <td style={{ padding: '8px 10px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontSize: 12 }}>
        {p.fill_price > 0 ? p.fill_price.toFixed(2) : p.entry_premium.toFixed(2)}
        {fillPct !== null && (
          <span style={{ color: Number(fillPct) >= 0 ? k.green : k.red, fontSize: 10, marginLeft: 4 }}>
            ({fillPct}%)
          </span>
        )}
      </td>
      <td style={{ padding: '8px 10px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontSize: 12 }}>
        {p.stop_premium > 0 ? p.stop_premium.toFixed(2) : '—'}
      </td>
      <td style={{ padding: '8px 10px', color: '#888', fontSize: 11 }}>
        {age !== null ? (age < 60 ? `${age}m` : `${Math.floor(age / 60)}h${age % 60}m`) : '—'}
      </td>
      <td style={{ padding: '8px 10px' }}>
        {confirm ? (
          <span>
            <button
              onClick={() => { onClose(p.symbol); setConfirm(false); }}
              style={{ fontSize: 11, padding: '2px 8px', marginRight: 4, background: k.red, color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
            >
              Confirm
            </button>
            <button
              onClick={() => setConfirm(false)}
              style={{ fontSize: 11, padding: '2px 8px', background: '#eee', border: 'none', borderRadius: 4, cursor: 'pointer' }}
            >
              Cancel
            </button>
          </span>
        ) : (
          <button
            onClick={() => setConfirm(true)}
            style={{ fontSize: 11, padding: '2px 8px', background: 'transparent', border: `1px solid ${k.border}`, borderRadius: 4, cursor: 'pointer', color: '#666' }}
          >
            Remove
          </button>
        )}
      </td>
    </tr>
  );
}

// ─── Pane ─────────────────────────────────────────────────────────────────────

export function EnginePositionsPane() {
  const { data, isLoading } = useEngineOpenPositions();
  const close = useCloseEnginePosition();

  const positions = data?.positions ?? [];

  return (
    <div style={{ padding: '16px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <span style={{ fontWeight: 600, fontSize: 14, color: k.text }}>Engine Positions</span>
        {positions.length > 0 && (
          <span style={{
            background: '#1565c0', color: '#fff', borderRadius: 12,
            padding: '1px 8px', fontSize: 11, fontWeight: 600,
          }}>
            {positions.length}
          </span>
        )}
      </div>

      {isLoading && (
        <div style={{ color: '#888', fontSize: 13, padding: '24px 0', textAlign: 'center' }}>
          Loading…
        </div>
      )}

      {!isLoading && positions.length === 0 && (
        <div style={{ color: '#aaa', fontSize: 13, padding: '24px 0', textAlign: 'center' }}>
          No engine positions tracked
        </div>
      )}

      {positions.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `2px solid ${k.border}`, color: '#888', fontSize: 11 }}>
                <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 500 }}>Symbol</th>
                <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 500 }}>Vehicle</th>
                <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 500 }}>Direction</th>
                <th style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 500 }}>Qty</th>
                <th style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 500 }}>Entry</th>
                <th style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 500 }}>Stop</th>
                <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 500 }}>Age</th>
                <th style={{ padding: '6px 10px', fontWeight: 500 }} />
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <PositionRow
                  key={p.symbol}
                  p={p}
                  onClose={(sym) => close.mutate(sym)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {close.isError && (
        <div style={{ color: k.red, fontSize: 12, marginTop: 8 }}>
          Failed to remove position: {String(close.error)}
        </div>
      )}
    </div>
  );
}
