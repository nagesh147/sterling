import React, { useState, useEffect, useMemo } from 'react';
import { useSnapshot } from '../hooks/useSnapshot';
import { useSignals } from '../hooks/useSignals';
import { usePositions, useClosePosition } from '../hooks/usePositions';
import { useLivePnl } from '../hooks/useLivePnl';
import { useTradingMode } from '../hooks/useTradingMode';
import { usePlaceOrder, useAlgoMode, useSetAlgoMode } from '../hooks/useSignalAlerts';
import { fmtN, fmtUSD, ivrColor } from '../utils/fmt';

// ─── Types ────────────────────────────────────────────────────────────────────

type InstrType = 'futures' | 'options';
type Direction = 'long' | 'short';
type TrailMode = 'off' | 'atr' | 'supertrend' | 'pct';

interface ComputedLevels {
  entry: number;
  stopLoss: number;
  takeProfit: number;
  liquidation: number;
  stopPct: number;
  riskUsd: number;
  rewardUsd: number;
  liqSafe: boolean;
  notional: number;
  margin: number;
}

interface OptionExpiry {
  date: Date;
  label: string;
  dteLabel: string;
  expiryCode: string;
  dte: number;
}

// ─── Pure computations ────────────────────────────────────────────────────────

function computeLevels(
  spot: number,
  direction: Direction,
  leverage: number,
  atr: number,
  stopMult: number,
  rr: number,
  contracts: number
): ComputedLevels {
  const stopDist = atr * stopMult;
  const stopLoss = direction === 'long' ? spot - stopDist : spot + stopDist;
  const takeProfit = direction === 'long' ? spot + stopDist * rr : spot - stopDist * rr;
  const liquidation =
    direction === 'long' ? spot * (1 - 0.9 / leverage) : spot * (1 + 0.9 / leverage);
  const stopPct = Math.abs(spot - stopLoss) / spot * 100;
  const notional = spot * contracts;
  const margin = notional / leverage;
  const riskUsd = stopDist * contracts;
  const rewardUsd = riskUsd * rr;
  const liqSafe =
    direction === 'long'
      ? stopLoss > liquidation * 1.15
      : stopLoss < liquidation * 0.85;
  return { entry: spot, stopLoss, takeProfit, liquidation, stopPct, riskUsd, rewardUsd, liqSafe, notional, margin };
}

function nextFridays(count: number): OptionExpiry[] {
  const result: OptionExpiry[] = [];
  const d = new Date();
  while (result.length < count) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() === 5) {
      const dte = Math.ceil((d.getTime() - Date.now()) / 86400000);
      const dateObj = new Date(d);
      const day = String(dateObj.getDate()).padStart(2, '0');
      const monthShort = dateObj.toLocaleString('en-US', { month: 'short' }).toUpperCase();
      const yr = String(dateObj.getFullYear()).slice(2);
      const expiryCode = `${day}${monthShort}${yr}`;
      const label = dateObj.toLocaleDateString('en-US', {
        day: '2-digit', month: 'short', year: '2-digit',
      }).toUpperCase();
      result.push({ date: dateObj, label, dteLabel: `${dte} DTE`, expiryCode, dte });
    }
  }
  return result;
}

function buildOptionSymbol(
  underlying: string,
  strike: number,
  optionType: 'call' | 'put',
  expiry: OptionExpiry
): string {
  const dir = optionType === 'call' ? 'C' : 'P';
  const exp = expiry.date.toLocaleDateString('en-US', { day: '2-digit', month: '2-digit', year: '2-digit' })
    .replace(/\//g, '');
  return `${dir}-${underlying}-${strike}-${exp}`;
}

// ─── Style constants ──────────────────────────────────────────────────────────

const LONG_COLOR  = 'var(--accent)';   // emerald — BUY / profit
const SHORT_COLOR = 'var(--danger)';   // crimson — SELL / loss
const NEUTRAL_COLOR = 'var(--text-dim)';

const sectionLabel: React.CSSProperties = {
  fontSize: 9,
  color: 'var(--text-dim)',
  letterSpacing: '0.12em',
  marginBottom: 6,
  textTransform: 'uppercase' as const,
  fontWeight: 600,
};

const inputStyle: React.CSSProperties = {
  background: 'var(--bg-surface)',
  color: 'var(--text-primary)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '7px 10px',
  fontFamily: 'inherit',
  fontSize: 13,
  fontVariantNumeric: 'tabular-nums',
  outline: 'none',
};

const card: React.CSSProperties = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  marginBottom: 12,
  overflow: 'hidden',
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function LiveClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-faint)', fontSize: 11 }}>
      {now.toLocaleTimeString('en-US', { hour12: false })}
    </span>
  );
}

function RegimeBadge({ regime, direction }: { regime: string; direction: string }) {
  let color = NEUTRAL_COLOR;
  if (direction === 'long') color = LONG_COLOR;
  if (direction === 'short') color = SHORT_COLOR;
  const icon = direction === 'long' ? '↑' : direction === 'short' ? '↓' : '→';
  const label = regime.replace(/_/g, ' ').toUpperCase();
  return (
    <span style={{
      background: `${color}18`,
      color,
      borderRadius: 5,
      padding: '3px 9px',
      fontSize: 10,
      letterSpacing: '0.06em',
      fontWeight: 700,
    }}>
      {icon} {label}
    </span>
  );
}

function ToggleBtn({
  active, onClick, color, children, style,
}: {
  active: boolean; onClick: () => void; color?: string; children: React.ReactNode; style?: React.CSSProperties;
}) {
  const activeColor = color ?? 'var(--accent)';
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? `${activeColor}18` : 'var(--bg-surface)',
        color: active ? activeColor : 'var(--text-dim)',
        border: `1px solid ${active ? `${activeColor}50` : 'var(--border)'}`,
        borderRadius: 7,
        padding: '6px 16px',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: 12,
        letterSpacing: '0.05em',
        fontWeight: active ? 700 : 400,
        transition: 'all 0.1s',
        ...style,
      }}
    >
      {children}
    </button>
  );
}

function PriceRow({
  label, price, pctDiff, subLabel, color, editable, onChange,
}: {
  label: string; price: number; pctDiff?: number; subLabel?: string;
  color?: string; editable?: boolean; onChange?: (v: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [raw, setRaw] = useState('');

  const handleCommit = () => {
    const n = parseFloat(raw);
    if (!isNaN(n) && onChange) onChange(n);
    setEditing(false);
  };

  const pctStr = pctDiff !== undefined
    ? `${pctDiff >= 0 ? '+' : ''}${fmtN(pctDiff, 2)}%`
    : '';

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      flex: 1,
      padding: '10px 14px',
      borderRight: '1px solid var(--border)',
    }}>
      {/* Label — small, muted, uppercase */}
      <span style={{
        fontSize: 9,
        fontWeight: 600,
        letterSpacing: '0.1em',
        color: 'var(--text-dim)',
        marginBottom: 5,
        textTransform: 'uppercase' as const,
      }}>
        {label}
        {subLabel && (
          <span style={{ marginLeft: 4, color: 'var(--text-faint)', fontWeight: 400, letterSpacing: 0 }}>
            · {subLabel}
          </span>
        )}
      </span>

      {/* Price — large, bold, tabular */}
      {editable && editing ? (
        <input
          autoFocus
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          onBlur={handleCommit}
          onKeyDown={(e) => { if (e.key === 'Enter') handleCommit(); if (e.key === 'Escape') setEditing(false); }}
          style={{ ...inputStyle, padding: '2px 6px', fontSize: 14, width: '100%' }}
        />
      ) : (
        <span
          onClick={() => { if (editable) { setRaw(fmtN(price, 0)); setEditing(true); } }}
          style={{
            fontSize: 15,
            fontVariantNumeric: 'tabular-nums',
            fontWeight: 700,
            color: color ?? 'var(--text-primary)',
            cursor: editable ? 'pointer' : 'default',
            letterSpacing: '-0.01em',
          }}
          title={editable ? 'Click to edit' : undefined}
        >
          ${fmtUSD(price, price < 10 ? 2 : 0)}
        </span>
      )}

      {/* % diff — small below price */}
      {pctStr && (
        <span style={{
          fontSize: 10,
          fontWeight: 500,
          color: color ?? 'var(--text-dim)',
          fontVariantNumeric: 'tabular-nums',
          marginTop: 2,
        }}>
          {pctStr}
        </span>
      )}
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────

interface Props {
  underlying: string;
}

export function TradingTicket({ underlying }: Props) {
  // ── Data hooks ──────────────────────────────────────────────────────────────
  const { data: snap } = useSnapshot(underlying);
  const { data: signalsData } = useSignals();
  const { data: posData } = usePositions();
  const { data: pnlData } = useLivePnl();
  const { data: modeData } = useTradingMode();
  const placeOrder = usePlaceOrder();
  const closePosition = useClosePosition();
  const { data: algoData } = useAlgoMode();
  const setAlgoMode = useSetAlgoMode();
  const algoEnabled = algoData?.enabled ?? false;

  // ── Signal for this underlying ──────────────────────────────────────────────
  const signal = useMemo(
    () => signalsData?.signals?.find((s) => s.underlying === underlying) ?? null,
    [signalsData, underlying]
  );

  // ── Open position for this underlying ──────────────────────────────────────
  const openPos = useMemo(
    () => posData?.positions?.find(
      (p) => p.underlying === underlying && (p.status === 'open' || p.status === 'partially_closed')
    ) ?? null,
    [posData, underlying]
  );

  const openPnl = useMemo(
    () => pnlData?.positions?.find((p) => p.underlying === underlying) ?? null,
    [pnlData, underlying]
  );

  // ── Derived defaults ────────────────────────────────────────────────────────
  const spot = snap?.spot_price ?? 0;
  const direction0: Direction =
    (snap?.direction === 'long' || snap?.direction === 'short') ? snap.direction : 'long';
  const atr0 = signal?.atr ?? (spot > 0 ? spot * 0.02 : 100);
  const stopMult0 = modeData?.config?.stop_atr_mult ?? 2.0;
  const rr0 = modeData?.config?.rr_target ?? 2.0;
  const defaultLev = 3; // default leverage; no rec_leverage on SignalItem

  // ── Local state ─────────────────────────────────────────────────────────────
  const [instrType, setInstrType] = useState<InstrType>('futures');
  const [direction, setDirection] = useState<Direction>(direction0);
  const [leverage, setLeverage] = useState<number>(defaultLev);
  const [contracts, setContracts] = useState<number>(1);
  const [trailMode, setTrailMode] = useState<TrailMode>('off');
  const [customSL, setCustomSL] = useState<number | null>(null);
  const [customTP, setCustomTP] = useState<number | null>(null);

  // Options state
  const [optionDir, setOptionDir] = useState<'call' | 'put'>(direction0 === 'long' ? 'call' : 'put');
  const [selectedExpiry, setSelectedExpiry] = useState<number>(0);
  const [selectedStrikeIdx, setSelectedStrikeIdx] = useState<number>(2);
  const [optionLots, setOptionLots] = useState<number>(1);

  // Sync direction from snapshot changes
  useEffect(() => {
    setDirection(direction0);
    setOptionDir(direction0 === 'long' ? 'call' : 'put');
  }, [direction0]);

  // Sync leverage from signal
  useEffect(() => {
    setLeverage(defaultLev > 0 ? defaultLev : 3);
  }, [defaultLev]);

  // Reset custom SL/TP when key params change
  useEffect(() => {
    setCustomSL(null);
    setCustomTP(null);
  }, [spot, direction, leverage]);

  // ── Computed levels ─────────────────────────────────────────────────────────
  const levels = useMemo(() => {
    if (spot <= 0) return null;
    const base = computeLevels(spot, direction, leverage, atr0, stopMult0, rr0, contracts);
    if (customSL !== null) {
      const slDist = Math.abs(spot - customSL);
      const tp = direction === 'long' ? spot + slDist * rr0 : spot - slDist * rr0;
      return {
        ...base,
        stopLoss: customSL,
        takeProfit: customTP ?? tp,
        stopPct: slDist / spot * 100,
        riskUsd: slDist * contracts,
        rewardUsd: slDist * contracts * rr0,
      };
    }
    if (customTP !== null) {
      return { ...base, takeProfit: customTP };
    }
    return base;
  }, [spot, direction, leverage, atr0, stopMult0, rr0, contracts, customSL, customTP]);

  // ── Option strikes ──────────────────────────────────────────────────────────
  const strikeStep = underlying === 'ETH' ? 100 : 500;
  const strikes = useMemo(() => {
    if (spot <= 0) return [];
    const atm = Math.round(spot / strikeStep) * strikeStep;
    return [-2, -1, 0, 1, 2].map((offset) => atm + offset * strikeStep);
  }, [spot, strikeStep]);

  const expiries = useMemo(() => nextFridays(3), []);

  const currentExpiry = expiries[selectedExpiry];
  const currentStrike = strikes[selectedStrikeIdx] ?? 0;
  const optionSymbol = currentExpiry
    ? buildOptionSymbol(underlying, currentStrike, optionDir, currentExpiry)
    : '';
  const estPremium = atr0 * 0.7 * optionLots;

  // ── Spot % change ───────────────────────────────────────────────────────────
  const st0 = snap?.st_values?.[0] ?? null;
  const spotChangePct =
    st0 && st0 > 0 && spot > 0 ? ((spot - st0) / st0) * 100 : null;

  // ── Score ───────────────────────────────────────────────────────────────────
  const score = direction === 'long' ? (snap?.score_long ?? 0) : (snap?.score_short ?? 0);

  // ── Direction color ─────────────────────────────────────────────────────────
  const dirColor = direction === 'long' ? LONG_COLOR : SHORT_COLOR;

  // ── Place order ─────────────────────────────────────────────────────────────
  const [orderMsg, setOrderMsg] = useState<string | null>(null);

  const canTrade =
    !openPos &&
    snap?.direction !== 'neutral' &&
    spot > 0;

  const handlePlaceFutures = () => {
    if (!canTrade || !levels) return;
    placeOrder.mutate(
      {
        underlying,
        direction,
        instrument_type: 'futures',
        size: contracts,
        leverage,
        order_type: 'market',
        stop_loss: levels.stopLoss,
        take_profit: levels.takeProfit,
        notes: `TradingTicket · ${direction.toUpperCase()} · ${leverage}× · score ${score}`,
      },
      {
        onSuccess: () => setOrderMsg('Order placed!'),
        onError: (e) => setOrderMsg(`Error: ${e.message}`),
      }
    );
  };

  const handlePlaceOptions = () => {
    if (!canTrade || !currentExpiry) return;
    placeOrder.mutate(
      {
        underlying,
        direction,
        instrument_type: 'options',
        size: optionLots,
        leverage: 1,
        order_type: 'market',
        option_symbol: optionSymbol,
        notes: `TradingTicket · ${optionDir.toUpperCase()} · ${currentStrike} · ${currentExpiry.expiryCode}`,
      },
      {
        onSuccess: () => setOrderMsg('Order placed!'),
        onError: (e) => setOrderMsg(`Error: ${e.message}`),
      }
    );
  };

  const handleClose = () => {
    if (!openPos) return;
    closePosition.mutate({ id: openPos.id, exit_spot_price: spot });
  };

  useEffect(() => {
    if (orderMsg) {
      const t = setTimeout(() => setOrderMsg(null), 3000);
      return () => clearTimeout(t);
    }
  }, [orderMsg]);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div style={{ ...card, padding: 0, overflow: 'hidden' }}>
      {/* ═══ ROW 1 — Header ══════════════════════════════════════════════════ */}
      <div style={{
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border)',
        padding: '12px 18px',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        flexWrap: 'wrap',
      }}>
        {/* Symbol */}
        <span style={{
          fontSize: 14,
          fontWeight: 700,
          letterSpacing: '0.08em',
          color: 'var(--text-primary)',
        }}>
          {underlying}
        </span>

        {/* Vertical divider */}
        <div style={{ width: 1, height: 20, background: 'var(--border)', flexShrink: 0 }} />

        {/* Spot price */}
        <span style={{
          fontSize: 20,
          fontVariantNumeric: 'tabular-nums',
          fontWeight: 700,
          color: 'var(--text-primary)',
          letterSpacing: '-0.01em',
        }}>
          ${fmtUSD(spot, spot < 100 ? 2 : 0)}
        </span>

        {/* % change */}
        {spotChangePct !== null && (
          <span style={{
            fontSize: 12,
            fontVariantNumeric: 'tabular-nums',
            fontWeight: 600,
            color: spotChangePct >= 0 ? LONG_COLOR : SHORT_COLOR,
            background: spotChangePct >= 0 ? 'var(--accent)14' : 'var(--danger)14',
            borderRadius: 5,
            padding: '2px 7px',
          }}>
            {spotChangePct >= 0 ? '+' : ''}{fmtN(spotChangePct, 2)}%
          </span>
        )}

        {/* Regime badge + score */}
        {snap && (
          <>
            <RegimeBadge regime={snap.macro_regime ?? 'unknown'} direction={snap.direction ?? 'neutral'} />
            <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
              Score{' '}
              <span style={{
                color: score >= 60 ? LONG_COLOR : score >= 40 ? 'var(--warning)' : SHORT_COLOR,
                fontWeight: 700,
                fontVariantNumeric: 'tabular-nums',
              }}>
                {Math.round(score)}
              </span>
            </span>
          </>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            onClick={() => setAlgoMode.mutate(!algoEnabled)}
            disabled={setAlgoMode.isPending}
            title={algoEnabled ? 'Algo ON — orders go live to Delta Exchange' : 'Algo OFF — orders are paper only'}
            style={{
              background: algoEnabled ? 'var(--accent)18' : 'var(--bg-surface)',
              color: algoEnabled ? 'var(--accent)' : 'var(--text-dim)',
              border: `1px solid ${algoEnabled ? 'var(--accent)50' : 'var(--border)'}`,
              borderRadius: 6,
              padding: '4px 12px',
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.08em',
              transition: 'all 0.15s',
              opacity: setAlgoMode.isPending ? 0.6 : 1,
            }}
          >
            {algoEnabled ? '⚡ ALGO ON' : 'ALGO OFF'}
          </button>
          <LiveClock />
        </div>
      </div>

      {/* ═══ ROW 2 — Signal context strip ════════════════════════════════════ */}
      {snap && (
        <div style={{
          background: 'var(--bg)',
          borderBottom: '1px solid var(--border)',
          padding: '7px 18px',
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          flexWrap: 'wrap',
          fontSize: 11,
        }}>
          {snap.adx !== undefined && snap.adx !== null && (
            <span style={{ color: 'var(--text-dim)', paddingRight: 14 }}>
              ADX{' '}
              <span style={{ color: snap.adx >= 25 ? LONG_COLOR : 'var(--text-muted)', fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
                {fmtN(snap.adx, 0)}
              </span>
            </span>
          )}
          {snap.rsi !== undefined && snap.rsi !== null && (
            <span style={{ color: 'var(--text-dim)', borderLeft: '1px solid var(--border)', paddingLeft: 14, paddingRight: 14 }}>
              RSI{' '}
              <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: snap.rsi >= 70 ? SHORT_COLOR : snap.rsi <= 30 ? LONG_COLOR : 'var(--text-muted)' }}>
                {fmtN(snap.rsi, 0)}
              </span>
            </span>
          )}
          {atr0 > 0 && (
            <span style={{ color: 'var(--text-dim)', borderLeft: '1px solid var(--border)', paddingLeft: 14, paddingRight: 14 }}>
              ATR{' '}
              <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-muted)', fontWeight: 600 }}>
                ${fmtUSD(atr0, atr0 < 10 ? 2 : 0)}
              </span>
            </span>
          )}
          {snap.ivr !== undefined && snap.ivr !== null && (
            <span style={{ color: ivrColor(snap.ivr), borderLeft: '1px solid var(--border)', paddingLeft: 14, paddingRight: 14, fontWeight: 600 }}>
              IVR {fmtN(snap.ivr, 0)}
              <span style={{ color: 'var(--text-faint)', fontWeight: 400, marginLeft: 4 }}>{snap.ivr_band}</span>
            </span>
          )}
          {snap.squeezed && (
            <span style={{ color: 'var(--warning)', fontWeight: 700, letterSpacing: '0.08em', borderLeft: '1px solid var(--border)', paddingLeft: 14, paddingRight: 14, fontSize: 10 }}>
              SQUEEZE
            </span>
          )}
          {snap.exec_mode && (
            <span style={{ marginLeft: 'auto', color: 'var(--blue)', letterSpacing: '0.08em', fontWeight: 700, fontSize: 10 }}>
              {snap.exec_mode.toUpperCase()} MODE
            </span>
          )}
        </div>
      )}

      <div style={{ padding: 16 }}>

        {/* ═══ ROW 3 — Instrument toggle ═══════════════════════════════════════ */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          <ToggleBtn active={instrType === 'futures'} onClick={() => setInstrType('futures')} color="var(--accent)">
            FUTURES
          </ToggleBtn>
          <ToggleBtn active={instrType === 'options'} onClick={() => setInstrType('options')} color="var(--accent)">
            OPTIONS
          </ToggleBtn>
        </div>

        {instrType === 'futures' ? (
          <FuturesSection
            direction={direction}
            setDirection={setDirection}
            leverage={leverage}
            setLeverage={setLeverage}
            contracts={contracts}
            setContracts={setContracts}
            levels={levels}
            setCustomSL={setCustomSL}
            setCustomTP={setCustomTP}
            trailMode={trailMode}
            setTrailMode={setTrailMode}
            dirColor={dirColor}
            canTrade={canTrade}
            openPos={openPos}
            openPnl={openPnl}
            spot={spot}
            atr0={atr0}
            modeData={modeData}
            onPlace={handlePlaceFutures}
            onClose={handleClose}
            placing={placeOrder.isPending}
            closing={closePosition.isPending}
            orderMsg={orderMsg}
          />
        ) : (
          <OptionsSection
            underlying={underlying}
            direction={direction}
            optionDir={optionDir}
            setOptionDir={setOptionDir}
            expiries={expiries}
            selectedExpiry={selectedExpiry}
            setSelectedExpiry={setSelectedExpiry}
            strikes={strikes}
            selectedStrikeIdx={selectedStrikeIdx}
            setSelectedStrikeIdx={setSelectedStrikeIdx}
            optionSymbol={optionSymbol}
            estPremium={estPremium}
            optionLots={optionLots}
            setOptionLots={setOptionLots}
            atr0={atr0}
            canTrade={canTrade}
            openPos={openPos}
            openPnl={openPnl}
            spot={spot}
            dirColor={dirColor}
            onPlace={handlePlaceOptions}
            onClose={handleClose}
            placing={placeOrder.isPending}
            closing={closePosition.isPending}
            orderMsg={orderMsg}
          />
        )}

      </div>
    </div>
  );
}

// ─── Futures Section ──────────────────────────────────────────────────────────

const LEVERAGES = [1, 2, 3, 5, 10, 20, 25, 50];

function FuturesSection({
  direction, setDirection, leverage, setLeverage,
  contracts, setContracts, levels, setCustomSL, setCustomTP,
  trailMode, setTrailMode, dirColor, canTrade, openPos, openPnl,
  spot, atr0, modeData, onPlace, onClose, placing, closing, orderMsg,
}: {
  direction: Direction; setDirection: (d: Direction) => void;
  leverage: number; setLeverage: (l: number) => void;
  contracts: number; setContracts: (c: number) => void;
  levels: ComputedLevels | null; setCustomSL: (v: number | null) => void;
  setCustomTP: (v: number | null) => void; trailMode: TrailMode;
  setTrailMode: (m: TrailMode) => void; dirColor: string;
  canTrade: boolean; openPos: any; openPnl: any; spot: number; atr0: number;
  modeData: any; onPlace: () => void; onClose: () => void;
  placing: boolean; closing: boolean; orderMsg: string | null;
}) {
  const trailAtrMult = modeData?.config?.trail_atr_mult ?? 2.0;
  const trailPct = modeData?.config?.trail_pct ?? 2.5;

  return (
    <>
      {/* ROW 4 — Direction */}
      <div style={{ marginBottom: 14 }}>
        <div style={sectionLabel}>DIRECTION</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <ToggleBtn
            active={direction === 'long'}
            onClick={() => setDirection('long')}
            color={LONG_COLOR}
            style={{ flex: 1, fontSize: 13, fontWeight: 700 }}
          >
            ▲ LONG
          </ToggleBtn>
          <ToggleBtn
            active={direction === 'short'}
            onClick={() => setDirection('short')}
            color={SHORT_COLOR}
            style={{ flex: 1, fontSize: 13, fontWeight: 700 }}
          >
            ▼ SHORT
          </ToggleBtn>
        </div>
      </div>

      {/* ROW 5 — Leverage */}
      <div style={{ marginBottom: 14 }}>
        <div style={sectionLabel}>LEVERAGE</div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {LEVERAGES.map((lv) => (
            <button
              key={lv}
              onClick={() => setLeverage(lv)}
              style={{
                background: leverage === lv ? `${dirColor}22` : 'var(--bg)',
                color: leverage === lv ? dirColor : 'var(--text-dim)',
                border: `1px solid ${leverage === lv ? dirColor : 'var(--border)'}`,
                borderRadius: 3, padding: '4px 10px', cursor: 'pointer',
                fontFamily: 'inherit', fontSize: 12, fontWeight: leverage === lv ? 700 : 400,
                transition: 'all 0.1s',
              }}
            >
              {lv}×
            </button>
          ))}
        </div>
      </div>

      {/* ROW 6 — Contracts + Risk preview */}
      <div style={{ marginBottom: 14, display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
        <div>
          <div style={sectionLabel}>CONTRACTS</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              onClick={() => setContracts(Math.max(1, contracts - 1))}
              style={{
                ...inputStyle, padding: '4px 10px', cursor: 'pointer', fontSize: 14, lineHeight: 1,
              }}
            >
              −
            </button>
            <span style={{ fontSize: 16, fontVariantNumeric: 'tabular-nums', minWidth: 28, textAlign: 'center', color: 'var(--text-primary)' }}>
              {contracts}
            </span>
            <button
              onClick={() => setContracts(contracts + 1)}
              style={{
                ...inputStyle, padding: '4px 10px', cursor: 'pointer', fontSize: 14, lineHeight: 1,
              }}
            >
              +
            </button>
          </div>
        </div>
        {levels && (
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            <div>
              <div style={sectionLabel}>NOTIONAL</div>
              <span style={{ fontSize: 13, fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)' }}>
                ${fmtUSD(levels.notional, 0)}
              </span>
            </div>
            <div>
              <div style={sectionLabel}>MARGIN</div>
              <span style={{ fontSize: 13, fontVariantNumeric: 'tabular-nums', color: 'var(--text-muted)' }}>
                ${fmtUSD(levels.margin, 0)}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ROW 7 — Price levels (clean inline grid, no box-in-box) */}
      {levels && (
        <div style={{ marginBottom: 16 }}>
          <div style={sectionLabel}>PRICE LEVELS</div>
          <div style={{
            display: 'flex',
            border: '1px solid var(--border)',
            borderRadius: 8,
            overflow: 'hidden',
            background: 'var(--bg-card)',
          }}>
            <PriceRow
              label="ENTRY"
              price={levels.entry}
              subLabel="MARKET"
            />
            <PriceRow
              label="STOP LOSS"
              price={levels.stopLoss}
              pctDiff={-Math.abs((levels.stopLoss - levels.entry) / levels.entry * 100)}
              subLabel={`${fmtN(modeData?.config?.stop_atr_mult ?? 2.0, 1)}×ATR`}
              color={SHORT_COLOR}
              editable
              onChange={(v) => setCustomSL(v)}
            />
            <PriceRow
              label="TAKE PROFIT"
              price={levels.takeProfit}
              pctDiff={Math.abs((levels.takeProfit - levels.entry) / levels.entry * 100) * (direction === 'long' ? 1 : -1)}
              subLabel={`${fmtN(modeData?.config?.rr_target ?? 2.0, 1)}:1 R:R`}
              color={LONG_COLOR}
              editable
              onChange={(v) => setCustomTP(v)}
            />
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              flex: 1,
              padding: '10px 14px',
            }}>
              <span style={{
                fontSize: 9, fontWeight: 600, letterSpacing: '0.1em',
                color: 'var(--text-dim)', marginBottom: 5, textTransform: 'uppercase' as const,
              }}>
                LIQ · <span style={{ fontWeight: 400, letterSpacing: 0 }}>{levels.liqSafe ? 'safe ✓' : '⚠ near SL'}</span>
              </span>
              <span style={{
                fontSize: 15, fontVariantNumeric: 'tabular-nums', fontWeight: 700,
                color: levels.liqSafe ? 'var(--text-dim)' : SHORT_COLOR,
                letterSpacing: '-0.01em',
              }}>
                ${fmtUSD(levels.liquidation, levels.liquidation < 10 ? 2 : 0)}
              </span>
              <span style={{
                fontSize: 10, fontWeight: 500, color: levels.liqSafe ? 'var(--text-faint)' : SHORT_COLOR,
                fontVariantNumeric: 'tabular-nums', marginTop: 2,
              }}>
                {`${((levels.liquidation - levels.entry) / levels.entry * 100).toFixed(1)}%`}
              </span>
            </div>
          </div>
          {!levels.liqSafe && (
            <div style={{
              marginTop: 6, fontSize: 10,
              color: SHORT_COLOR,
              background: 'var(--danger)10',
              border: '1px solid var(--danger)25',
              padding: '6px 10px',
              borderRadius: 6,
            }}>
              ⚠ Stop loss within 15% of liquidation — reduce leverage or widen stop
            </div>
          )}
        </div>
      )}

      {/* ROW 8 — Trailing stop */}
      <div style={{ marginBottom: 14 }}>
        <div style={sectionLabel}>TRAILING STOP</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <ToggleBtn active={trailMode === 'off'} onClick={() => setTrailMode('off')} color="var(--text-dim)">
            OFF
          </ToggleBtn>
          {trailMode !== 'off' ? (
            <>
              <ToggleBtn active={trailMode === 'atr'} onClick={() => setTrailMode('atr')} color={dirColor}>
                ATR {trailAtrMult}×
              </ToggleBtn>
              <ToggleBtn active={trailMode === 'supertrend'} onClick={() => setTrailMode('supertrend')} color={dirColor}>
                SuperTrend
              </ToggleBtn>
              <ToggleBtn active={trailMode === 'pct'} onClick={() => setTrailMode('pct')} color={dirColor}>
                {trailPct}%
              </ToggleBtn>
              <span style={{ fontSize: 10, color: 'var(--text-faint)', marginLeft: 4 }}>
                Stop rises with price, never falls back
              </span>
            </>
          ) : (
            <ToggleBtn active={false} onClick={() => setTrailMode('atr')} color="var(--text-dim)">
              ON
            </ToggleBtn>
          )}
        </div>
      </div>

      {/* ROW 9 — Risk summary bar */}
      {levels && (
        <div style={{
          marginBottom: 16,
          display: 'flex',
          gap: 0,
          border: '1px solid var(--border)',
          borderRadius: 8,
          overflow: 'hidden',
          fontSize: 11,
          fontVariantNumeric: 'tabular-nums',
        }}>
          <div style={{
            flex: 1,
            padding: '8px 14px',
            borderRight: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-dim)', marginBottom: 3 }}>RISK</div>
            <span style={{ color: SHORT_COLOR, fontWeight: 700, fontSize: 13 }}>
              ${fmtUSD(levels.riskUsd, 0)}
            </span>
            <span style={{ color: 'var(--text-dim)', marginLeft: 4, fontSize: 10 }}>
              {fmtN(levels.stopPct, 1)}%
            </span>
          </div>
          <div style={{
            flex: 1,
            padding: '8px 14px',
            borderRight: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-dim)', marginBottom: 3 }}>REWARD</div>
            <span style={{ color: LONG_COLOR, fontWeight: 700, fontSize: 13 }}>
              ${fmtUSD(levels.rewardUsd, 0)}
            </span>
            <span style={{ color: 'var(--text-dim)', marginLeft: 4, fontSize: 10 }}>
              {fmtN(levels.stopPct * (modeData?.config?.rr_target ?? 2), 1)}%
            </span>
          </div>
          <div style={{ padding: '8px 14px', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-dim)', marginBottom: 3 }}>R:R</div>
            <span style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: 13 }}>
              {fmtN(modeData?.config?.rr_target ?? 2, 1)}:1
            </span>
          </div>
          <div style={{ padding: '8px 14px', display: 'flex', alignItems: 'center' }}>
            {levels.liqSafe
              ? <span style={{ color: LONG_COLOR, fontWeight: 700, fontSize: 11 }}>Liq ✓</span>
              : <span style={{ color: SHORT_COLOR, fontWeight: 700, fontSize: 11 }}>Liq ⚠</span>}
          </div>
        </div>
      )}

      {/* ROW 10 — Open position or BUY button */}
      {openPos ? (
        <OpenPositionCard
          pos={openPos}
          pnl={openPnl}
          spot={spot}
          onClose={onClose}
          closing={closing}
        />
      ) : (
        <>
          {orderMsg && (
            <div style={{
              marginBottom: 8, padding: '6px 10px', borderRadius: 3, fontSize: 12,
              background: orderMsg.startsWith('Error') ? `${SHORT_COLOR}22` : `${LONG_COLOR}22`,
              color: orderMsg.startsWith('Error') ? SHORT_COLOR : LONG_COLOR,
              border: `1px solid ${orderMsg.startsWith('Error') ? SHORT_COLOR : LONG_COLOR}44`,
            }}>
              {orderMsg}
            </div>
          )}
          <button
            onClick={onPlace}
            disabled={!canTrade || placing}
            style={{
              width: '100%',
              padding: '15px 0',
              borderRadius: 8,
              cursor: canTrade ? 'pointer' : 'not-allowed',
              border: 'none',
              fontFamily: 'inherit',
              fontSize: 13,
              fontWeight: 800,
              letterSpacing: '0.1em',
              textTransform: 'uppercase' as const,
              background: canTrade
                ? direction === 'long'
                  ? 'var(--accent)'
                  : 'var(--danger)'
                : 'var(--bg-surface)',
              color: canTrade ? '#000' : 'var(--text-dim)',
              opacity: (!canTrade || placing) ? 0.65 : 1,
              transition: 'opacity 0.15s',
              boxShadow: canTrade
                ? direction === 'long'
                  ? '0 0 20px var(--accent)30'
                  : '0 0 20px var(--danger)30'
                : 'none',
            }}
          >
            {placing
              ? 'Placing Order…'
              : `${direction === 'long' ? '▲ BUY LONG' : '▼ SELL SHORT'}  ·  ${contracts} contract${contracts > 1 ? 's' : ''}  ·  ${leverage}×`}
          </button>
          {!canTrade && spot > 0 && (
            <div style={{ marginTop: 6, fontSize: 10, color: 'var(--text-faint)', textAlign: 'center' }}>
              {openPos ? 'Position already open' : 'No signal — direction is neutral'}
            </div>
          )}
        </>
      )}
    </>
  );
}

// ─── Options Section ──────────────────────────────────────────────────────────

function OptionsSection({
  underlying, direction, optionDir, setOptionDir, expiries, selectedExpiry,
  setSelectedExpiry, strikes, selectedStrikeIdx, setSelectedStrikeIdx,
  optionSymbol, estPremium, optionLots, setOptionLots, atr0, canTrade,
  openPos, openPnl, spot, dirColor, onPlace, onClose, placing, closing, orderMsg,
}: {
  underlying: string; direction: Direction; optionDir: 'call' | 'put';
  setOptionDir: (d: 'call' | 'put') => void; expiries: OptionExpiry[];
  selectedExpiry: number; setSelectedExpiry: (i: number) => void;
  strikes: number[]; selectedStrikeIdx: number; setSelectedStrikeIdx: (i: number) => void;
  optionSymbol: string; estPremium: number; optionLots: number;
  setOptionLots: (l: number) => void; atr0: number; canTrade: boolean;
  openPos: any; openPnl: any; spot: number; dirColor: string;
  onPlace: () => void; onClose: () => void;
  placing: boolean; closing: boolean; orderMsg: string | null;
}) {
  const currentExp = expiries[selectedExpiry];
  const currentStrike = strikes[selectedStrikeIdx] ?? 0;
  const estStopLoss = estPremium * 0.5 * optionLots;
  const estTakeProfit = estPremium * 1.0 * optionLots;

  return (
    <>
      {/* Options direction */}
      <div style={{ marginBottom: 14 }}>
        <div style={sectionLabel}>DIRECTION</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <ToggleBtn
            active={optionDir === 'call'}
            onClick={() => setOptionDir('call')}
            color={LONG_COLOR}
            style={{ flex: 1, fontSize: 13, fontWeight: 700 }}
          >
            CALL (BUY)
          </ToggleBtn>
          <ToggleBtn
            active={optionDir === 'put'}
            onClick={() => setOptionDir('put')}
            color={SHORT_COLOR}
            style={{ flex: 1, fontSize: 13, fontWeight: 700 }}
          >
            PUT (BUY)
          </ToggleBtn>
        </div>
      </div>

      {/* Expiry selector */}
      <div style={{ marginBottom: 14 }}>
        <div style={sectionLabel}>EXPIRY</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {expiries.map((exp, i) => (
            <ToggleBtn
              key={i}
              active={selectedExpiry === i}
              onClick={() => setSelectedExpiry(i)}
              color="var(--accent)"
            >
              {exp.label} · {exp.dteLabel}
            </ToggleBtn>
          ))}
        </div>
      </div>

      {/* Strike selector */}
      <div style={{ marginBottom: 14 }}>
        <div style={sectionLabel}>STRIKE</div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {strikes.map((strike, i) => {
            const isAtm = i === 2;
            return (
              <button
                key={i}
                onClick={() => setSelectedStrikeIdx(i)}
                style={{
                  background: selectedStrikeIdx === i ? `${'var(--accent)'}22` : 'var(--bg)',
                  color: selectedStrikeIdx === i ? 'var(--accent)' : 'var(--text-dim)',
                  border: `1px solid ${selectedStrikeIdx === i ? 'var(--accent)' : 'var(--border)'}`,
                  borderRadius: 3, padding: '5px 10px', cursor: 'pointer',
                  fontFamily: 'inherit', fontSize: 12, fontVariantNumeric: 'tabular-nums',
                  fontWeight: selectedStrikeIdx === i ? 700 : 400,
                }}
              >
                ${fmtUSD(strike, 0)}{isAtm ? ' ✓ ATM' : ''}
              </button>
            );
          })}
        </div>
      </div>

      {/* Options info row */}
      <div style={{
        marginBottom: 14, padding: '8px 12px',
        background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4,
        display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 11,
      }}>
        <div>
          <div style={sectionLabel}>SYMBOL</div>
          <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)', fontSize: 12 }}>
            {optionSymbol || '—'}
          </span>
        </div>
        <div>
          <div style={sectionLabel}>EST. PREMIUM / LOT</div>
          <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)' }}>
            ~${fmtUSD(atr0 * 0.7, 0)}
          </span>
        </div>
        <div>
          <div style={sectionLabel}>DELTA (EST.)</div>
          <span style={{ color: 'var(--text-muted)' }}>≈0.48</span>
        </div>
        {currentExp && (
          <div>
            <div style={sectionLabel}>DTE</div>
            <span style={{ color: 'var(--text-primary)' }}>{currentExp.dte}</span>
          </div>
        )}
      </div>

      {/* SL/TP for options */}
      <div style={{
        marginBottom: 14, padding: '8px 12px',
        background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4,
        fontSize: 11,
      }}>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <span style={{ color: 'var(--text-faint)', fontSize: 9, letterSpacing: 1 }}>STOP LOSS </span>
            <span style={{ color: SHORT_COLOR, fontVariantNumeric: 'tabular-nums' }}>
              50% of premium = ${fmtUSD(estStopLoss / optionLots, 0)} loss / lot
            </span>
          </div>
          <div>
            <span style={{ color: 'var(--text-faint)', fontSize: 9, letterSpacing: 1 }}>TAKE PROFIT </span>
            <span style={{ color: LONG_COLOR, fontVariantNumeric: 'tabular-nums' }}>
              100% gain = ${fmtUSD(estTakeProfit / optionLots, 0)} / lot
            </span>
          </div>
        </div>
      </div>

      {/* Lots + BUY */}
      <div style={{ marginBottom: 14 }}>
        <div style={sectionLabel}>LOTS</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              onClick={() => setOptionLots(Math.max(1, optionLots - 1))}
              style={{ ...inputStyle, padding: '4px 10px', cursor: 'pointer', fontSize: 14 }}
            >
              −
            </button>
            <span style={{ fontSize: 16, fontVariantNumeric: 'tabular-nums', minWidth: 28, textAlign: 'center', color: 'var(--text-primary)' }}>
              {optionLots}
            </span>
            <button
              onClick={() => setOptionLots(optionLots + 1)}
              style={{ ...inputStyle, padding: '4px 10px', cursor: 'pointer', fontSize: 14 }}
            >
              +
            </button>
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
            Total premium: ~${fmtUSD(estPremium, 0)}
          </span>
        </div>
      </div>

      {openPos ? (
        <OpenPositionCard
          pos={openPos}
          pnl={openPnl}
          spot={spot}
          onClose={onClose}
          closing={closing}
        />
      ) : (
        <>
          {orderMsg && (
            <div style={{
              marginBottom: 8, padding: '6px 10px', borderRadius: 3, fontSize: 12,
              background: orderMsg.startsWith('Error') ? `${SHORT_COLOR}22` : `${LONG_COLOR}22`,
              color: orderMsg.startsWith('Error') ? SHORT_COLOR : LONG_COLOR,
              border: `1px solid ${orderMsg.startsWith('Error') ? SHORT_COLOR : LONG_COLOR}44`,
            }}>
              {orderMsg}
            </div>
          )}
          <button
            onClick={onPlace}
            disabled={!canTrade || placing}
            style={{
              width: '100%',
              padding: '15px 0',
              borderRadius: 8,
              cursor: canTrade ? 'pointer' : 'not-allowed',
              border: 'none',
              fontFamily: 'inherit',
              fontSize: 13,
              fontWeight: 800,
              letterSpacing: '0.1em',
              textTransform: 'uppercase' as const,
              background: canTrade
                ? optionDir === 'call' ? 'var(--accent)' : 'var(--danger)'
                : 'var(--bg-surface)',
              color: canTrade ? '#000' : 'var(--text-dim)',
              opacity: (!canTrade || placing) ? 0.65 : 1,
              transition: 'opacity 0.15s',
            }}
          >
            {placing
              ? 'Placing Order…'
              : `BUY ${optionDir.toUpperCase()}  ·  ${fmtUSD(currentStrike, 0)} strike  ·  ${currentExp?.label ?? '—'}`}
          </button>
        </>
      )}
    </>
  );
}

// ─── Open Position Card ───────────────────────────────────────────────────────

function OpenPositionCard({
  pos, pnl, spot, onClose, closing,
}: {
  pos: any; pnl: any; spot: number; onClose: () => void; closing: boolean;
}) {
  const st = pos.sized_trade?.structure;
  const dir = st?.direction ?? 'unknown';
  const entrySpot = pos.entry_spot_price;
  const pnlUsd = pnl?.estimated_pnl_usd ?? null;
  const pnlPct = pnlUsd !== null && entrySpot > 0
    ? (pnlUsd / (entrySpot * (pos.sized_trade?.contracts ?? 1))) * 100
    : null;
  const pnlColor = pnlUsd !== null ? (pnlUsd >= 0 ? LONG_COLOR : SHORT_COLOR) : 'var(--text-faint)';

  return (
    <div style={{
      border: '1px solid var(--accent)30',
      borderLeft: '3px solid var(--accent)',
      borderRadius: 8,
      padding: '12px 14px',
      background: 'var(--accent)08',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
        <span style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: '0.1em',
          color: 'var(--accent)',
        }}>
          OPEN POSITION
        </span>
        <button
          onClick={onClose}
          disabled={closing}
          style={{
            marginLeft: 'auto',
            background: 'var(--danger)18',
            color: 'var(--danger)',
            border: '1px solid var(--danger)40',
            borderRadius: 6,
            padding: '4px 12px',
            cursor: 'pointer',
            fontFamily: 'inherit',
            fontSize: 11,
            fontWeight: 600,
            opacity: closing ? 0.5 : 1,
          }}
        >
          {closing ? 'Closing…' : '✕ Close Position'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>
        <div>
          <span style={{ color: dir === 'long' ? 'var(--accent)' : 'var(--danger)', fontWeight: 700 }}>
            {dir === 'long' ? '↑' : '↓'} {dir.toUpperCase()}
          </span>
          <span style={{ color: 'var(--text-dim)', marginLeft: 6 }}>
            {pos.sized_trade?.contracts ?? 1} ct
          </span>
        </div>
        <div style={{ color: 'var(--text-dim)' }}>
          Entry <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>${fmtUSD(entrySpot, 0)}</span>
        </div>
        {spot > 0 && (
          <div style={{ color: 'var(--text-dim)' }}>
            Now <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>${fmtUSD(spot, 0)}</span>
          </div>
        )}
        {pnlUsd !== null && (
          <div style={{ marginLeft: 'auto' }}>
            <span style={{ color: pnlColor, fontWeight: 700, fontSize: 13 }}>
              {pnlUsd >= 0 ? '+' : ''}${fmtUSD(pnlUsd, 0)}
              {pnlPct !== null && (
                <span style={{ fontSize: 11, fontWeight: 500, marginLeft: 4 }}>
                  ({fmtN(pnlPct, 1)}%)
                </span>
              )}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
