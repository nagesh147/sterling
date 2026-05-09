import React, { useState } from 'react';
import { useSignalAlerts, usePlaceOrder } from '../hooks/useSignalAlerts';
import type { SignalAlert } from '../hooks/useSignalAlerts';
import { fmtN } from '../utils/fmt';

// ── shared constants ──────────────────────────────────────────────────────────

const DIR_COLOR = { long: '#44cc88', short: '#cc4444' } as const;
const DIR_LABEL = { long: 'BUY', short: 'SELL' } as const;
const STATE_COLOR: Record<string, string> = {
  ENTRY_ARMED_PULLBACK: '#44aaff', ENTRY_ARMED_CONTINUATION: '#66ccff',
  CONFIRMED_SETUP_ACTIVE: '#f0c040', EARLY_SETUP_ACTIVE: '#f0a500',
};

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

function OrderModal({ alert, onClose }: { alert: SignalAlert; onClose: () => void }) {
  const [instrType, setInstrType] = useState<'futures' | 'options'>('futures');
  const [leverage, setLeverage] = useState(alert.rec_leverage);
  const [size, setSize] = useState(1);
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null);
  const { mutate: placeOrder, isPending } = usePlaceOrder();

  const dirColor = DIR_COLOR[alert.direction as keyof typeof DIR_COLOR] ?? '#888';
  const side = DIR_LABEL[alert.direction as keyof typeof DIR_LABEL] ?? alert.direction.toUpperCase();

  const handlePlace = () => {
    placeOrder({
      underlying: alert.underlying,
      direction: alert.direction,
      instrument_type: instrType,
      size,
      leverage,
      order_type: 'market',
      stop_loss: alert.stop_loss,
      take_profit: alert.take_profit,
      option_symbol: instrType === 'options' ? (alert.opt_symbol ?? undefined) : undefined,
      notes: `Alert: ${alert.state_label}`,
    }, {
      onSuccess: (data: any) => {
        setStatus({ ok: true, msg: `${data.mode === 'live' ? '✅ LIVE' : '📋 Paper'} order placed — ${data.order_id || data.paper_position_id}` });
        setTimeout(onClose, 2000);
      },
      onError: (e: Error) => setStatus({ ok: false, msg: `Error: ${e.message}` }),
    });
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#000000cc', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={onClose}>
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-light)', borderRadius: 8, padding: 24, width: 380, maxWidth: '95vw' }}
        onClick={e => e.stopPropagation()}>

        {/* header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <span style={{ fontSize: 18, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: 1 }}>{alert.underlying}</span>
            <span style={{ marginLeft: 10, fontSize: 14, fontWeight: 800, color: dirColor }}>{side}</span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: 18 }}>✕</button>
        </div>

        <PriceGrid alert={alert} />

        {/* instrument type toggle */}
        <div style={{ display: 'flex', gap: 0, marginBottom: 12, borderRadius: 4, overflow: 'hidden', border: '1px solid var(--border)' }}>
          {(['futures', 'options'] as const).map(t => (
            <button key={t} onClick={() => setInstrType(t)} style={{
              flex: 1, padding: '8px 0', border: 'none', cursor: 'pointer',
              background: instrType === t ? (t === 'futures' ? '#1a2a1a' : '#1a1a2a') : 'var(--bg)',
              color: instrType === t ? (t === 'futures' ? '#44cc88' : '#88aaff') : 'var(--text-dim)',
              fontFamily: 'inherit', fontSize: 11, fontWeight: 700, letterSpacing: 1,
            }}>{t.toUpperCase()}</button>
          ))}
        </div>

        {instrType === 'futures' ? (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, color: 'var(--text-faint)', marginBottom: 4 }}>SYMBOL: {alert.futures_symbol}</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 9, color: 'var(--text-faint)', marginBottom: 3 }}>LEVERAGE</div>
                <select value={leverage} onChange={e => setLeverage(Number(e.target.value))} style={{
                  width: '100%', background: 'var(--bg)', color: 'var(--text-primary)', border: '1px solid var(--border)',
                  borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 12,
                }}>
                  {[1,2,3,5,10,20,25,50].map(l => <option key={l} value={l}>{l}×</option>)}
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 9, color: 'var(--text-faint)', marginBottom: 3 }}>CONTRACTS</div>
                <input type="number" min={1} max={100} value={size} onChange={e => setSize(Number(e.target.value))} style={{
                  width: '100%', background: 'var(--bg)', color: 'var(--text-primary)', border: '1px solid var(--border)',
                  borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 12,
                }} />
              </div>
            </div>
          </div>
        ) : (
          <div style={{ marginBottom: 12 }}>
            {alert.opt_symbol ? (
              <>
                <div style={{ fontSize: 10, color: 'var(--text-faint)', marginBottom: 4 }}>
                  OPTION: <span style={{ color: '#88aaff', fontWeight: 700 }}>{alert.opt_symbol}</span>
                </div>
                <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
                  <span>Strike: <b style={{ color: 'var(--text-primary)' }}>{fmtPrice(alert.opt_strike)}</b></span>
                  <span>Type: <b style={{ color: alert.opt_type === 'CE' ? '#44cc88' : '#cc4444' }}>{alert.opt_type}</b></span>
                  <span>Expiry: <b style={{ color: 'var(--text-primary)' }}>{alert.opt_expiry}</b></span>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 9, color: 'var(--text-faint)', marginBottom: 3 }}>LOTS</div>
                    <input type="number" min={1} max={50} value={size} onChange={e => setSize(Number(e.target.value))} style={{
                      width: '100%', background: 'var(--bg)', color: 'var(--text-primary)', border: '1px solid var(--border)',
                      borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 12,
                    }} />
                  </div>
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--text-faint)', fontSize: 11 }}>Option chain not available for this instrument.</div>
            )}
          </div>
        )}

        {/* risk info */}
        <div style={{ display: 'flex', gap: 12, fontSize: 10, color: 'var(--text-faint)', marginBottom: 16 }}>
          <span>Risk: <b style={{ color: '#cc4444' }}>{alert.risk_pct}%</b></span>
          <span>ADX: <b style={{ color: 'var(--text-muted)' }}>{alert.adx}</b></span>
          <span>RSI: <b style={{ color: 'var(--text-muted)' }}>{alert.rsi}</b></span>
          <span>Score: <b style={{ color: '#f0c040' }}>{alert.score}</b></span>
        </div>

        {status && (
          <div style={{ marginBottom: 12, padding: '8px 10px', borderRadius: 4,
            background: status.ok ? '#1a2a1a' : '#2a1a1a',
            color: status.ok ? '#44cc88' : '#cc4444',
            border: `1px solid ${status.ok ? '#44cc8833' : '#cc444433'}`,
            fontSize: 11 }}>
            {status.msg}
          </div>
        )}

        <button
          disabled={isPending}
          onClick={handlePlace}
          style={{
            width: '100%', padding: '12px 0',
            background: alert.direction === 'long' ? '#0f2a0f' : '#2a0f0f',
            color: alert.direction === 'long' ? '#44cc88' : '#cc4444',
            border: `1px solid ${alert.direction === 'long' ? '#44cc88' : '#cc4444'}`,
            borderRadius: 5, cursor: 'pointer', fontFamily: 'inherit',
            fontSize: 14, fontWeight: 900, letterSpacing: 1,
          }}
        >
          {isPending ? 'Placing Order…' : `▶ ${side} ${instrType.toUpperCase()} — ${alert.underlying}`}
        </button>
      </div>
    </div>
  );
}

function AlertCard({ alert }: { alert: SignalAlert }) {
  const [showOrder, setShowOrder] = useState(false);
  const dirColor = DIR_COLOR[alert.direction as keyof typeof DIR_COLOR] ?? '#888';
  const stateColor = STATE_COLOR[alert.state] ?? '#f0a500';

  return (
    <>
      {showOrder && <OrderModal alert={alert} onClose={() => setShowOrder(false)} />}
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
          <span>Risk: <b style={{ color: '#cc4444' }}>{alert.risk_pct}%</b></span>
          <span>ADX: {alert.adx}  RSI: {alert.rsi}</span>
          <span>Score: <b style={{ color: '#f0c040' }}>{alert.score}</b></span>
          <span style={{ color: 'var(--text-faint)', fontSize: 9 }}>{fmtAge(alert.timestamp_ms)}</span>
        </div>

        {/* action */}
        <button
          onClick={() => setShowOrder(true)}
          style={{
            padding: '10px 18px', borderRadius: 5, cursor: 'pointer',
            background: alert.direction === 'long' ? '#0f2a0f' : '#2a0f0f',
            color: alert.direction === 'long' ? '#44cc88' : '#cc4444',
            border: `1px solid ${alert.direction === 'long' ? '#44cc88' : '#cc4444'}`,
            fontFamily: 'inherit', fontSize: 12, fontWeight: 800, letterSpacing: 0.5,
          }}
        >
          TRADE
        </button>
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
        <span style={{ color: '#44cc88', fontSize: 12, fontWeight: 900, letterSpacing: 2 }}>
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
