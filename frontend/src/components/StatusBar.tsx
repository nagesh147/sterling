import React from 'react';
import { useDrawdownBreaker } from '../hooks/useDrawdownBreaker';
import { useCalibration } from '../hooks/useCalibration';
import { useSelectedUnderlying } from '../store/useStore';
import { useSnapshot } from '../hooks/useSnapshot';
import { useLivePrices } from '../hooks/useLivePrices';

export function StatusBar() {
  const underlying = useSelectedUnderlying();
  const { data: cb } = useDrawdownBreaker();
  const { data: cal } = useCalibration(underlying);
  const { data: snap } = useSnapshot(underlying);
  const liveP = useLivePrices();

  /* SSE live price takes precedence over snapshot's polled price */
  const spotPrice = liveP[underlying] ?? snap?.spot_price ?? null;

  const cbState = cb?.state ?? 'clear';
  const cbColor = cbState === 'clear' ? 'var(--t-dim)'
    : cbState === 'warning' ? 'var(--t-amber)'
    : 'var(--t-red)';
  const isHalted = cbState !== 'clear';

  const now = new Date().toLocaleTimeString('en-US', { hour12: false });

  return (
    <div style={{
      height: 28,
      background: 'var(--t-bg2)',
      borderTop: '1px solid var(--t-border)',
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      padding: '0 12px',
      flexShrink: 0,
      fontSize: 10,
      color: 'var(--t-dim)',
    }}>
      {/* Exchange status */}
      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--t-green)', display: 'inline-block' }} />
        DERIBIT
      </span>

      {/* Current price — live from SSE (~2s) */}
      {spotPrice != null && (
        <span>
          <span style={{ color: 'var(--t-dim)' }}>{underlying} </span>
          <span className="num" style={{ color: 'var(--t-bright)' }}>
            ${spotPrice.toLocaleString('en-US', { maximumFractionDigits: spotPrice < 100 ? 2 : 0 })}
          </span>
        </span>
      )}

      {/* Win rate */}
      {cal && (
        <span>
          WR: <span className="num" style={{ color: 'var(--t-text)' }}>{(cal.win_rate * 100).toFixed(0)}%</span>
          {cal.trade_count < 10 && <span style={{ color: 'var(--t-dim)' }}> (low data)</span>}
        </span>
      )}

      {/* Circuit breaker */}
      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        CB:
        <span style={{
          color: cbColor,
          animation: isHalted ? 't-blink 0.8s infinite' : undefined,
          fontFamily: 'var(--mono)',
          fontSize: 10,
          fontWeight: 600,
        }}>
          {cbState.toUpperCase()}
        </span>
      </span>

      {/* Timestamp */}
      <span style={{ marginLeft: 'auto' }}>
        Last: <span className="num">{now}</span>
      </span>
    </div>
  );
}
