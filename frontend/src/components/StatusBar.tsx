import React from 'react';
import { useDrawdownBreaker } from '../hooks/useDrawdownBreaker';
import { useCalibration } from '../hooks/useCalibration';
import { useSelectedUnderlying } from '../store/useStore';
import { useSnapshot } from '../hooks/useSnapshot';
import { useLivePrices } from '../hooks/useLivePrices';
import { useDataSource } from '../hooks/useExchanges';
import { useTheme, useSetTheme, useZoomLevel, useSetZoomLevel, useResetUI, type Theme } from '../store/useStore';

export function StatusBar() {
  const underlying = useSelectedUnderlying();
  const { data: cb } = useDrawdownBreaker();
  const { data: cal } = useCalibration(underlying);
  const { data: snap } = useSnapshot(underlying);
  const liveP = useLivePrices();
  const { data: ds } = useDataSource();

  /* SSE live price takes precedence over snapshot's polled price */
  const spotPrice = liveP[underlying] ?? snap?.spot_price ?? null;

  const cbState = cb?.state ?? 'clear';
  const cbColor = cbState === 'clear' ? 'var(--t-dim)'
    : cbState === 'warning' ? 'var(--t-amber)'
    : 'var(--t-red)';
  const isHalted = cbState !== 'clear';

  const now = new Date().toLocaleTimeString('en-US', { hour12: false });
  const theme = useTheme();
  const setTheme = useSetTheme();
  const zoomLevel = useZoomLevel();
  const setZoomLevel = useSetZoomLevel();
  const resetUI = useResetUI();

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
      {/* Data source + reachability */}
      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%', display: 'inline-block',
          background: ds?.reachable ? 'var(--t-green)' : ds?.reachable === false ? 'var(--t-red)' : 'var(--t-dim)',
        }} />
        {ds ? ds.exchange.toUpperCase().replace('_', ' ') : 'DERIBIT'}
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
      <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 16 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--t-bg)', padding: '2px 8px', border: '1px solid var(--t-border)' }}>
          <button style={btnStyle} onClick={() => setZoomLevel(zoomLevel - 0.1)}>-</button>
          <span style={{ fontSize: 9, minWidth: 32, textAlign: 'center' }}>{(zoomLevel * 100).toFixed(0)}%</span>
          <button style={btnStyle} onClick={() => setZoomLevel(zoomLevel + 0.1)}>+</button>
        </span>
        
        <span style={{ display: 'flex', alignItems: 'center', gap: 2, background: 'var(--t-bg)', padding: '2px 4px', border: '1px solid var(--t-border)' }}>
          <button style={{ ...btnStyle, background: theme === 'dark' ? 'var(--t-border)' : 'transparent' }} onClick={() => setTheme('dark')}>DK</button>
          <button style={{ ...btnStyle, background: theme === 'grey' ? 'var(--t-border)' : 'transparent' }} onClick={() => setTheme('grey')}>GR</button>
          <button style={{ ...btnStyle, background: theme === 'light' ? 'var(--t-border)' : 'transparent' }} onClick={() => setTheme('light')}>LT</button>
        </span>

        <button style={btnStyle} onClick={() => resetUI()}>RST</button>

        <span>Last: <span className="num">{now}</span></span>
      </span>
    </div>
  );
}

const btnStyle = {
  background: 'transparent', border: 'none', color: 'var(--t-dim)',
  cursor: 'pointer', fontFamily: 'inherit', fontSize: 9, fontWeight: 700,
  padding: '2px 6px', display: 'flex', alignItems: 'center', justifyContent: 'center'
};
