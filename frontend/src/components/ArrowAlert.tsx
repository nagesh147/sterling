import React, { useEffect, useRef, useState } from 'react';
import { useSignalStream } from '../hooks/useSignalStream';
import { useQueryClient, useMutation } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { SignalsResponse } from '../hooks/useSignals';

// ── helpers ───────────────────────────────────────────────────────────────────

function fp(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return '—';
  if (v >= 10_000) return '$' + v.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (v >= 100)   return '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 });
  return '$' + v.toFixed(2);
}

function pctStr(entry: number, level: number | null | undefined): string {
  if (!level) return '';
  const p = ((level - entry) / entry) * 100;
  return (p >= 0 ? '+' : '') + p.toFixed(1) + '%';
}

// ── order mutation ────────────────────────────────────────────────────────────

function usePlaceNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: object) => api.post('/api/v1/trading/place-order', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['positions'] });
      qc.invalidateQueries({ queryKey: ['live-pnl'] });
    },
  });
}

// ── notification card ─────────────────────────────────────────────────────────

interface TradeNotif {
  underlying: string;
  direction: string;
  spot: number;
  stopLoss: number | null;
  takeProfit: number | null;
  leverage: number;
  regime: string;
  score: number;
  optSymbol: string | null;
  optStrike: number | null;
  optType: string | null;
  optExpiry: string | null;
  ts: number;
}

function NotifCard({ notif, onDismiss }: { notif: TradeNotif; onDismiss: () => void }) {
  const [orderType, setOrderType] = useState<'futures' | 'options'>('futures');
  const [feedback, setFeedback] = useState('');
  const { mutate: place, isPending } = usePlaceNow();

  const isLong   = notif.direction === 'long';
  const color    = isLong ? 'var(--accent)' : 'var(--danger)';
  const bgDark   = isLong ? '#003d2e' : '#3d0014';
  const side     = isLong ? 'BUY' : 'SELL';
  const arrow    = isLong ? '▲' : '▼';
  const riskPct  = notif.stopLoss && notif.spot
    ? Math.abs((notif.spot - notif.stopLoss) / notif.spot * 100).toFixed(1)
    : null;

  const handleTrade = () => {
    place({
      underlying: notif.underlying,
      direction: notif.direction,
      instrument_type: orderType,
      size: 1,
      leverage: notif.leverage,
      order_type: 'market',
      stop_loss: notif.stopLoss,
      take_profit: notif.takeProfit,
      option_symbol: orderType === 'options' ? notif.optSymbol : null,
      notes: `Arrow signal — ${notif.regime}`,
    }, {
      onSuccess: () => { setFeedback('✅ Order placed!'); setTimeout(onDismiss, 2000); },
      onError:   (e: unknown) => setFeedback(`❌ ${(e as Error).message}`),
    });
  };

  return (
    <div style={{
      position: 'fixed', top: 76, right: 16, zIndex: 9999,
      width: 340,
      background: 'var(--bg-card)',
      border: `1px solid ${color}`,
      borderLeft: `4px solid ${color}`,
      borderRadius: 8,
      boxShadow: `0 8px 32px ${isLong ? '#00d4aa' : '#ff4757'}33`,
      overflow: 'hidden',
    }}>
      {/* header */}
      <div style={{
        background: bgDark,
        padding: '10px 14px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div>
          <span style={{ fontSize: 13, fontWeight: 900, color, letterSpacing: 1 }}>
            {arrow} {side} SIGNAL — {notif.underlying}
          </span>
          <span style={{ fontSize: 10, color: `${color}99`, marginLeft: 10 }}>
            {notif.regime.replace(/_/g, ' ')} · Score {notif.score}
          </span>
        </div>
        <button onClick={onDismiss} style={{
          background: 'none', border: 'none', color: 'var(--text-dim)',
          cursor: 'pointer', fontSize: 18, lineHeight: 1, padding: '0 4px',
        }}>×</button>
      </div>

      {/* prices */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 1,
        background: 'var(--border)', margin: '0',
      }}>
        {[
          ['ENTRY', fp(notif.spot), 'var(--text-primary)', ''],
          ['STOP LOSS', fp(notif.stopLoss), 'var(--danger)', riskPct ? `-${riskPct}%` : ''],
          ['TAKE PROFIT', fp(notif.takeProfit), 'var(--accent)', notif.takeProfit ? pctStr(notif.spot, notif.takeProfit) : ''],
        ].map(([label, val, clr, sub]) => (
          <div key={label} style={{
            background: 'var(--bg-card)', padding: '8px 10px', textAlign: 'center',
          }}>
            <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 2 }}>{label}</div>
            <div style={{ fontSize: 13, fontWeight: 800, color: clr, fontVariantNumeric: 'tabular-nums' }}>{val}</div>
            {sub && <div style={{ fontSize: 9, color: 'var(--text-dim)' }}>{sub}</div>}
          </div>
        ))}
      </div>

      {/* instrument selector */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
        {/* futures */}
        <div
          onClick={() => setOrderType('futures')}
          style={{
            padding: '7px 10px', borderRadius: 4, cursor: 'pointer', marginBottom: 6,
            background: orderType === 'futures' ? bgDark : 'var(--bg)',
            border: `1px solid ${orderType === 'futures' ? color : 'var(--border)'}`,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}
        >
          <div>
            <span style={{ fontSize: 11, fontWeight: 700, color: orderType === 'futures' ? color : 'var(--text-muted)' }}>
              FUTURES
            </span>
            <span style={{ fontSize: 10, color: 'var(--text-faint)', marginLeft: 8 }}>
              {notif.underlying}USDT · {notif.leverage}× leverage
            </span>
          </div>
          <span style={{ fontSize: 9, color: orderType === 'futures' ? color : 'var(--text-faint)', fontWeight: 700 }}>
            {orderType === 'futures' ? '●' : '○'}
          </span>
        </div>

        {/* options */}
        {notif.optSymbol && (
          <div
            onClick={() => setOrderType('options')}
            style={{
              padding: '7px 10px', borderRadius: 4, cursor: 'pointer',
              background: orderType === 'options' ? bgDark : 'var(--bg)',
              border: `1px solid ${orderType === 'options' ? color : 'var(--border)'}`,
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}
          >
            <div>
              <span style={{ fontSize: 11, fontWeight: 700, color: orderType === 'options' ? color : 'var(--text-muted)' }}>
                {notif.optType === 'CE' ? 'CALL' : 'PUT'} OPTION
              </span>
              <span style={{ fontSize: 10, color: 'var(--text-faint)', marginLeft: 8 }}>
                Strike {fp(notif.optStrike)} · {notif.optExpiry}
              </span>
            </div>
            <span style={{ fontSize: 9, color: orderType === 'options' ? color : 'var(--text-faint)', fontWeight: 700 }}>
              {orderType === 'options' ? '●' : '○'}
            </span>
          </div>
        )}
      </div>

      {/* action */}
      <div style={{ padding: '10px 12px' }}>
        {feedback ? (
          <div style={{
            textAlign: 'center', padding: '8px', fontSize: 12, fontWeight: 700,
            color: feedback.startsWith('✅') ? 'var(--accent)' : 'var(--danger)',
          }}>{feedback}</div>
        ) : (
          <button
            onClick={handleTrade}
            disabled={isPending}
            style={{
              width: '100%', padding: '11px 0',
              background: bgDark, color, border: `1px solid ${color}`,
              borderRadius: 5, cursor: 'pointer', fontFamily: 'inherit',
              fontSize: 13, fontWeight: 900, letterSpacing: 1,
              opacity: isPending ? 0.7 : 1,
            }}
          >
            {isPending ? 'Placing…' : `${arrow} ${side} NOW — 1 ${orderType === 'futures' ? `contract ${notif.leverage}×` : 'lot'}`}
          </button>
        )}
        <div style={{ textAlign: 'center', marginTop: 5, fontSize: 9, color: 'var(--text-faint)' }}>
          Paper mode · SL/TP auto-attached · tap × to dismiss
        </div>
      </div>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export function ArrowAlert({ underlying }: { underlying: string }) {
  const { data } = useSignalStream(underlying, 30);
  const [notif, setNotif] = useState<TradeNotif | null>(null);
  const lastTs    = useRef<number>(0);
  const lastState = useRef<string>('');
  const timerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const qc        = useQueryClient();

  useEffect(() => {
    if (!data || data.timestamp_ms === lastTs.current) return;
    lastTs.current = data.timestamp_ms;

    const shouldFire =
      data.green_arrow || data.red_arrow ||
      (
        ['CONFIRMED_SETUP_ACTIVE', 'ENTRY_ARMED_PULLBACK', 'ENTRY_ARMED_CONTINUATION'].includes(data.state ?? '') &&
        !['CONFIRMED_SETUP_ACTIVE', 'ENTRY_ARMED_PULLBACK', 'ENTRY_ARMED_CONTINUATION'].includes(lastState.current)
      );

    lastState.current = data.state ?? '';
    if (!shouldFire) return;
    if (data.direction === 'neutral') return;

    // Pull cached signal data for this underlying to get SL/TP/leverage/options
    const cached = qc.getQueryData<SignalsResponse>(['signals-all']);
    const sig = cached?.signals.find(s => s.underlying === underlying);

    const spot    = data.spot_price ?? 0;
    const isLong  = data.direction === 'long';
    const atr     = sig?.atr ?? spot * 0.02;
    const mult    = sig?.stop_atr_mult ?? 2.0;
    const rr      = 2.0;
    const stopLoss    = sig?.stop_price ?? (isLong ? spot - atr * mult : spot + atr * mult);
    const takeProfit  = sig?.target_price ?? (isLong ? spot + atr * mult * rr : spot - atr * mult * rr);
    const leverage    = sig?.rec_leverage ?? 5;
    const score       = isLong ? (data.score_long ?? 0) : (data.score_short ?? 0);

    // Derive option params if not from cache
    const optStrike   = sig?.opt_strike ?? (spot > 0 ? Math.round(spot / (spot > 10000 ? 500 : 100)) * (spot > 10000 ? 500 : 100) : null);
    const optType     = sig?.opt_type ?? (isLong ? 'CE' : 'PE');
    const optExpiry   = sig?.opt_expiry ?? null;
    const optSymbol   = sig?.opt_symbol ?? (optStrike && optExpiry ? `${optType![0]}-${underlying}-${optStrike}-${optExpiry}` : null);

    setNotif({
      underlying,
      direction: data.direction,
      spot, stopLoss, takeProfit, leverage,
      regime: data.macro_regime ?? '',
      score: Math.round(score),
      optSymbol, optStrike, optType: optType ?? null, optExpiry,
      ts: data.timestamp_ms,
    });

    qc.invalidateQueries({ queryKey: ['signals-all'] });
    qc.invalidateQueries({ queryKey: ['snapshot', underlying] });
    qc.invalidateQueries({ queryKey: ['arrows', underlying] });

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setNotif(null), 30_000);
  }, [data?.timestamp_ms, data?.green_arrow, data?.red_arrow, data?.state, underlying, qc]);

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  if (!notif) return null;
  return <NotifCard notif={notif} onDismiss={() => setNotif(null)} />;
}
