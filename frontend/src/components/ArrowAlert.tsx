import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useSignalStream } from '../hooks/useSignalStream';
import { useQueryClient, useMutation } from '@tanstack/react-query';
import { api } from '../utils/api';
import type { SignalsResponse } from '../hooks/useSignals';
import { injectArrowEntry } from '../hooks/useSignalFeed';
import { useTradingMode } from '../hooks/useTradingMode';
import { fpPrice } from '../utils/fmt';
import { MODE_COLOR } from '../utils/colors';
import { alpha } from '../styles/terminalUI';

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

interface TradeNotif {
  underlying: string;
  direction: string;
  spot: number;
  stopLoss: number | null;
  takeProfit: number | null;
  leverage: number;
  regime: string;
  score: number;
  mode: string;
  optSymbol: string | null;
  optStrike: number | null;
  optType: string | null;
  optExpiry: string | null;
  ts: number;
}

const AUTO_DISMISS_MS = 30_000;

function NotifCard({ notif, onDismiss }: { notif: TradeNotif; onDismiss: () => void }) {
  const [feedback, setFeedback]   = useState('');
  const [progress, setProgress]   = useState(100);
  const { mutate: place, isPending } = usePlaceNow();
  // Stable ref for onDismiss so the interval never captures a stale closure
  const onDismissRef = useRef(onDismiss);
  useEffect(() => { onDismissRef.current = onDismiss; });

  const isLong    = notif.direction === 'long';
  const color     = isLong ? 'var(--accent)' : 'var(--danger)';
  const bgDark    = isLong ? alpha('var(--accent)', 0.08) : alpha('var(--danger)', 0.08);
  const side      = isLong ? 'BUY' : 'SELL';
  const arrow     = isLong ? '▲' : '▼';
  const modeColor = MODE_COLOR[notif.mode] ?? 'var(--text-dim)';

  // Countdown progress bar — uses ref so interval never captures a stale dismiss callback
  useEffect(() => {
    const start = Date.now();
    const tick = setInterval(() => {
      const elapsed = Date.now() - start;
      const pct = Math.max(0, 100 - (elapsed / AUTO_DISMISS_MS) * 100);
      setProgress(pct);
      if (pct === 0) { clearInterval(tick); onDismissRef.current(); }
    }, 200);
    return () => clearInterval(tick);
  }, []); // no dependency — ref stays current

  const handleTrade = () => {
    place({
      underlying: notif.underlying,
      direction: notif.direction,
      instrument_type: 'futures',
      size: 1,
      leverage: notif.leverage,
      order_type: 'market',
      stop_loss: notif.stopLoss,
      take_profit: notif.takeProfit,
      notes: `Arrow signal — ${notif.regime}`,
    }, {
      onSuccess: () => { setFeedback('✅ Placed'); setTimeout(onDismiss, 2000); },
      onError:   (e: unknown) => { setFeedback(`❌ ${(e as Error).message}`); setTimeout(() => setFeedback(''), 6000); },
    });
  };

  return (
    <div style={{
      position: 'fixed', bottom: 28, right: 20, zIndex: 3000,
      width: 300,
      background: 'var(--bg-card)',
      border: `1px solid ${color}44`,
      borderLeft: `3px solid ${color}`,
      borderRadius: 7,
      overflow: 'hidden',
      animation: 'slideUp 0.2s ease',
    }}>
      {/* progress bar — depletes left-to-right over 30s */}
      <div style={{ height: 2, background: 'var(--border)' }}>
        <div style={{
          height: '100%', width: `${progress}%`,
          background: color, transition: 'width 0.2s linear',
        }} />
      </div>

      {/* header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 12px 6px',
        background: bgDark,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 900, color, letterSpacing: 0.5 }}>
            {arrow} {side} — {notif.underlying}
          </span>
          {/* mode badge */}
          <span style={{
            fontSize: 8, fontWeight: 700, letterSpacing: 0.5,
            color: modeColor, background: modeColor + '20',
            border: `1px solid ${modeColor}44`,
            borderRadius: 3, padding: '1px 5px',
          }}>
            {notif.mode.toUpperCase()}
          </span>
          <span style={{
            fontSize: 8, fontWeight: 700, color: `${color}99`,
            background: `${color}15`, border: `1px solid ${color}30`,
            borderRadius: 3, padding: '1px 5px', letterSpacing: 0.5,
          }}>
            SIGNAL
          </span>
        </div>
        <button onClick={onDismiss} style={{
          background: 'none', border: 'none', color: 'var(--text-faint)',
          cursor: 'pointer', fontSize: 15, lineHeight: 1, padding: 0,
        }}>×</button>
      </div>

      {/* prices — compact 3-column */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
        {([
          ['ENTRY', fpPrice(notif.spot), 'var(--text-primary)'],
          ['SL', fpPrice(notif.stopLoss), 'var(--danger)'],
          ['TP', fpPrice(notif.takeProfit), 'var(--accent)'],
        ] as [string, string, string][]).map(([label, val, clr]) => (
          <div key={label} style={{
            flex: 1, textAlign: 'center', padding: '7px 4px',
            borderRight: label !== 'TP' ? '1px solid var(--border)' : 'none',
          }}>
            <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 2 }}>{label}</div>
            <div style={{ fontSize: 12, fontWeight: 800, color: clr, fontVariantNumeric: 'tabular-nums' }}>{val}</div>
          </div>
        ))}
      </div>

      {/* meta + action */}
      <div style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 9, color: 'var(--text-faint)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {notif.regime.replace(/_/g, ' ')} · {notif.leverage}× · Score {notif.score}
          </div>
          {notif.optSymbol && (
            <div style={{ fontSize: 8, color: 'var(--text-faint)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {notif.optType === 'CE' ? 'CALL' : 'PUT'} {fpPrice(notif.optStrike)} · {notif.optExpiry}
            </div>
          )}
        </div>

        {feedback ? (
          <span style={{
            fontSize: 11, fontWeight: 700,
            color: feedback.startsWith('✅') ? 'var(--accent)' : 'var(--danger)',
          }}>
            {feedback}
          </span>
        ) : (
          <button
            onClick={handleTrade}
            disabled={isPending}
            style={{
              flexShrink: 0,
              padding: '7px 14px',
              background: bgDark, color, border: `1px solid ${color}`,
              borderRadius: 5, cursor: 'pointer', fontFamily: 'inherit',
              fontSize: 11, fontWeight: 800, letterSpacing: 0.5,
              opacity: isPending ? 0.6 : 1,
            }}
          >
            {isPending ? '…' : `${side} NOW`}
          </button>
        )}
      </div>

      <style>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

const ARMED_STATES = new Set([
  'CONFIRMED_SETUP_ACTIVE', 'ENTRY_ARMED_PULLBACK', 'ENTRY_ARMED_CONTINUATION',
]);

export function ArrowAlert({ underlying }: { underlying: string }) {
  const { data }     = useSignalStream(underlying, 30);
  const { data: modeData } = useTradingMode();
  const [notif, setNotif]  = useState<TradeNotif | null>(null);
  const lastTs    = useRef<number>(0);
  // Deliberately NOT prefixed with 'sterling_' — useSignalFeed purges all
  // sterling_* keys on load (legacy cleanup), which would reset this state.
  const stateKey  = `sa_state_${underlying}`;
  const arrowKey  = `sa_arrow_ts_${underlying}`;
  const lastState = useRef<string>(
    (() => { try { return sessionStorage.getItem(stateKey) ?? ''; } catch { return ''; } })()
  );
  // Persist last arrow-popup timestamp so page reloads don't re-fire within 2h
  const lastArrowTs = useRef<number>(
    (() => { try { return parseInt(sessionStorage.getItem(arrowKey) ?? '0') || 0; } catch { return 0; } })()
  );
  const timerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const qc        = useQueryClient();

  useEffect(() => {
    if (!data || data.timestamp_ms === lastTs.current) return;
    lastTs.current = data.timestamp_ms;

    const curState = data.state ?? '';
    const prev     = lastState.current;

    // Arrow popup: additionally gated by 2h cooldown (survives page reloads)
    const arrowFiring = data.green_arrow || data.red_arrow;
    const ARROW_POPUP_COOLDOWN_MS = 2 * 60 * 60 * 1000;
    if (arrowFiring && Date.now() - lastArrowTs.current < ARROW_POPUP_COOLDOWN_MS) {
      // Trend already signalled within cooldown — update state tracker but skip popup
      lastState.current = curState;
      try { sessionStorage.setItem(stateKey, curState); } catch { /* ignore */ }
      return;
    }

    const shouldFire =
      arrowFiring ||
      (ARMED_STATES.has(curState) && !ARMED_STATES.has(prev));

    lastState.current = curState;
    try { sessionStorage.setItem(stateKey, curState); } catch { /* ignore */ }

    if (!shouldFire) return;
    if (data.direction === 'neutral') return;

    if (arrowFiring) {
      lastArrowTs.current = Date.now();
      try { sessionStorage.setItem(arrowKey, String(lastArrowTs.current)); } catch { /* ignore */ }
    }

    const cached = qc.getQueryData<SignalsResponse>(['signals-all']);
    const sig    = cached?.signals.find(s => s.underlying === underlying);
    const spot   = data.spot_price ?? 0;
    const isLong = data.direction === 'long';
    const atr    = sig?.atr ?? spot * 0.02;
    const mult   = sig?.stop_atr_mult ?? 2.0;
    const stopLoss   = sig?.stop_price   ?? (isLong ? spot - atr * mult     : spot + atr * mult);
    const takeProfit = sig?.target_price ?? (isLong ? spot + atr * mult * 2 : spot - atr * mult * 2);
    const leverage   = sig?.rec_leverage ?? 5;
    const score      = isLong ? (data.score_long ?? 0) : (data.score_short ?? 0);
    const optType    = isLong ? 'CE' : 'PE';
    const step       = spot > 10_000 ? 500 : 100;
    const optStrike  = sig?.opt_strike  ?? (spot > 0 ? Math.round(spot / step) * step : null);
    const optExpiry  = sig?.opt_expiry  ?? null;
    const optSymbol  = sig?.opt_symbol
      ?? (optStrike && optExpiry ? `${optType[0]}-${underlying}-${optStrike}-${optExpiry}` : null);

    const dir = data.direction as 'long' | 'short';
    setNotif({
      underlying, direction: dir, spot, stopLoss, takeProfit, leverage,
      regime: data.macro_regime ?? '', score: Math.round(score),
      mode: modeData?.name ?? 'scalping',
      optSymbol, optStrike, optType, optExpiry, ts: data.timestamp_ms,
    });

    injectArrowEntry(
      underlying, dir, spot, stopLoss, takeProfit, leverage,
      sig?.futures_symbol ?? `${underlying}USDT`,
      optSymbol, optStrike, optType, optExpiry,
      data.macro_regime ?? '', Math.round(score),
    );

    qc.invalidateQueries({ queryKey: ['snapshot', underlying] });
    qc.invalidateQueries({ queryKey: ['arrows', underlying] });

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setNotif(null), AUTO_DISMISS_MS);
  }, [data?.timestamp_ms, data?.green_arrow, data?.red_arrow, data?.state, underlying, qc]);

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  if (!notif) return null;
  return <NotifCard notif={notif} onDismiss={() => setNotif(null)} />;
}
