import React, { useState } from 'react';
import { useSignalAlerts } from '../hooks/useSignalAlerts';
import type { SignalAlert } from '../hooks/useSignalAlerts';
import { fmtN } from '../utils/fmt';
import { c as ui, tint } from '../styles/terminalUI';
import { STATE_COLOR } from '../utils/colors';

const DIR_COLOR = { long: ui.green, short: ui.red } as const;
const DIR_LABEL = { long: 'BUY', short: 'SELL' } as const;

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return '—';
  if (v >= 10_000) return '$' + v.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (v >= 100) return '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 });
  return '$' + v.toFixed(4);
}

function fmtAge(ms: number): string {
  const diff = Date.now() - ms;
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  return `${Math.floor(diff / 3_600_000)}h ago`;
}

function PriceGrid({ alert }: { alert: SignalAlert }) {
  const cells: [string, number | null, string][] = [
    ['ENTRY',       alert.entry,       'var(--text-primary)'],
    ['STOP LOSS',   alert.stop_loss,   DIR_COLOR.short],
    ['TAKE PROFIT', alert.take_profit, DIR_COLOR.long],
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 16 }}>
      {cells.map(([label, val, color]) => (
        <div key={label} style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, padding: '8px 6px', textAlign: 'center' }}>
          <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 3 }}>{label}</div>
          <div style={{ fontSize: 13, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>{fmtPrice(val)}</div>
        </div>
      ))}
    </div>
  );
}

function AlertCard({ alert }: { alert: SignalAlert }) {
  const dirColor = DIR_COLOR[alert.direction as keyof typeof DIR_COLOR] ?? ui.dim;
  const stateColor = STATE_COLOR[alert.state] ?? ui.amber;

  return (
    <>
      <div style={{
        background: 'var(--bg-card)', border: `1px solid ${stateColor}44`,
        borderLeft: `4px solid ${stateColor}`, borderRadius: 6, padding: '12px 14px',
        marginBottom: 8, display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' as const,
      }}>
        {/* left: symbol + direction */}
        <div style={{ minWidth: 100 }}>
          <div style={{ fontSize: 16, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: 1 }}>{alert.underlying}</div>
          <div style={{ fontSize: 12, fontWeight: 800, color: dirColor, marginTop: 2 }}>
            {alert.direction === 'long' ? '▲ BUY' : '▼ SELL'}
          </div>
          <div style={{ fontSize: 9, color: stateColor, marginTop: 2, letterSpacing: 0.5 }}>{alert.state_label.replace('⚡ ', '').replace('✅ ', '')}</div>
        </div>

        <div style={{ flex: 1, minWidth: 240 }}><PriceGrid alert={alert} /></div>

        {/* meta */}
        <div style={{ fontSize: 10, color: 'var(--text-dim)', display: 'flex', flexDirection: 'column', gap: 3, minWidth: 80 }}>
          <span>Risk: <b style={{ color: ui.red }}>{alert.risk_pct}%</b></span>
          <span>ADX: {alert.adx}  RSI: {alert.rsi}</span>
          <span>Score: <b style={{ color: ui.amber }}>{alert.score}</b></span>
          <span style={{ color: 'var(--text-faint)', fontSize: 9 }}>{fmtAge(alert.timestamp_ms)}</span>
        </div>

      </div>
    </>
  );
}

export function AlertsPanel() {
  const { data, isLoading } = useSignalAlerts();
  const alerts = data?.alerts ?? [];

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 12, padding: '10px 14px',
        background: '#14291a', border: '1px solid #1e3a22', borderRadius: '6px 6px 0 0',
      }}>
        <span style={{ color: ui.green, fontSize: 12, fontWeight: 900, letterSpacing: 2 }}>
          ● TRADING SIGNALS  <span style={{ color: '#2a4a2a' }}>— Professional Alerts</span>
        </span>
        <span style={{ fontSize: 10, color: '#2a4a2a' }}>{alerts.length} alerts</span>
      </div>

      {isLoading && !data && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '0 0 6px 6px', padding: '20px 14px', color: 'var(--text-faint)', fontSize: 12 }}>
          Waiting for signals…
        </div>
      )}

      {!isLoading && alerts.length === 0 && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '0 0 6px 6px', padding: '24px 14px', textAlign: 'center' as const }}>
          <div style={{ color: 'var(--text-faint)', fontSize: 13, marginBottom: 6 }}>No signals yet</div>
          <div style={{ color: 'var(--text-faint)', fontSize: 11 }}>
            Signals generate when regime + signal align. Background refresh every 30s.
          </div>
        </div>
      )}

      {alerts.length > 0 && (
        <div style={{ border: '1px solid var(--border)', borderTop: 'none', borderRadius: '0 0 6px 6px', padding: 12 }}>
          {alerts.map(alert => <AlertCard key={alert.id} alert={alert} />)}
        </div>
      )}
    </div>
  );
}
