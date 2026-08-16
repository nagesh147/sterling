import React, { useMemo, useState } from 'react';
import { k } from '../../styles/kiteUI';
import { fmt } from './AdaptiveEdgePanel';
import { roundToTick, fmtTick } from '../../utils/fmt';

/**
 * Standard lot size lookup for major Indian indices and watched F&O equities.
 */
export function getInstrumentLotSize(symbol: string): number {
  const s = symbol.toUpperCase();
  if (s.includes('BANKNIFTY') || s.includes('NIFTY BANK')) return 15;
  if (s.includes('FINNIFTY') || s.includes('NIFTY FIN')) return 25;
  if (s.includes('MIDCPNIFTY')) return 50;
  if (s.includes('SENSEX')) return 10;
  if (s.includes('BANKEX')) return 15;
  if (s.includes('NIFTY')) return 25;

  // Major F&O Equities
  if (s.includes('RELIANCE')) return 250;
  if (s.includes('HDFCBANK')) return 550;
  if (s.includes('ICICIBANK')) return 700;
  if (s.includes('INFY')) return 400;
  if (s.includes('TCS')) return 175;
  if (s.includes('SBIN')) return 750;
  if (s.includes('BHARTIARTL')) return 475;
  if (s.includes('AXISBANK')) return 625;
  if (s.includes('KOTAKBANK')) return 400;
  if (s.includes('LT')) return 150;
  if (s.includes('TATAMOTORS')) return 575;
  if (s.includes('ITC')) return 1600;

  return 25;
}

interface Props {
  symbol: string;
  defaultEntryPrice?: number | null;
  defaultSl?: number | null;
  defaultTsl?: number | null;
  defaultExit?: number | null;
  currentLtp?: number | null;
  optionType?: 'CE' | 'PE';
}

export function AdaptiveEdgePositionCalculator({
  symbol,
  defaultEntryPrice,
  defaultSl,
  defaultTsl,
  defaultExit,
  currentLtp,
  optionType = 'CE',
}: Props) {
  const lotSize = useMemo(() => getInstrumentLotSize(symbol), [symbol]);
  const baseEntry = roundToTick(defaultEntryPrice ?? currentLtp ?? 100) ?? 100;
  const baseSl = roundToTick(defaultSl ?? (baseEntry * 0.8)) ?? Number((baseEntry * 0.8).toFixed(2));
  const baseTsl = roundToTick(defaultTsl ?? baseEntry) ?? baseEntry;
  const baseTarget = roundToTick(defaultExit ?? (baseEntry + Math.abs(baseEntry - baseSl) * 2)) ?? baseEntry;

  // Editable State
  const [numLots, setNumLots] = useState<number>(1);
  const [entryPrice, setEntryPrice] = useState<number>(baseEntry);
  const [slPrice, setSlPrice] = useState<number>(baseSl);
  const [tslPrice, setTslPrice] = useState<number>(baseTsl);
  const [targetPrice, setTargetPrice] = useState<number>(baseTarget);

  const isCustomized =
    numLots !== 1 ||
    entryPrice !== baseEntry ||
    slPrice !== baseSl ||
    tslPrice !== baseTsl ||
    targetPrice !== baseTarget;

  const resetDefaults = () => {
    setNumLots(1);
    setEntryPrice(baseEntry);
    setSlPrice(baseSl);
    setTslPrice(baseTsl);
    setTargetPrice(baseTarget);
  };

  // Calculations
  const totalQty = Math.max(1, numLots * lotSize);
  const totalInvestment = roundToTick(entryPrice * totalQty) ?? (entryPrice * totalQty);
  const liveLtp = roundToTick(currentLtp ?? entryPrice) ?? entryPrice;

  // Covered Points & Return
  const coveredPoints = roundToTick(liveLtp - entryPrice) ?? 0;
  const coveredPct = entryPrice > 0 ? Number(((coveredPoints / entryPrice) * 100).toFixed(2)) : 0;
  const unrealizedPnl = roundToTick(coveredPoints * totalQty) ?? 0;
  const isProfit = coveredPoints >= 0;

  // Hard SL Risk
  const slDistance = Math.max(0, roundToTick(entryPrice - slPrice) ?? 0);
  const slPct = entryPrice > 0 ? Number(((slDistance / entryPrice) * 100).toFixed(2)) : 0;
  const maxRiskAmount = roundToTick(slDistance * totalQty) ?? 0;
  const riskPerLot = roundToTick(slDistance * lotSize) ?? 0;

  // Trailing Stop Loss (TSL) Locked Profit / Risk Protection
  const tslDistance = roundToTick(tslPrice - entryPrice) ?? 0;
  const tslPnl = roundToTick(tslDistance * totalQty) ?? 0;
  const isRiskFree = tslPrice >= entryPrice;

  // Target / Reward
  const targetDistance = Math.max(0, roundToTick(targetPrice - entryPrice) ?? 0);
  const targetReward = roundToTick(targetDistance * totalQty) ?? 0;
  const riskRewardRatio = slDistance > 0 ? (targetDistance / slDistance).toFixed(2) : '1.00';
  const realizedRR = slDistance > 0 ? (coveredPoints / slDistance).toFixed(2) : '0.00';

  return (
    <div
      style={{
        background: k.bg,
        border: `1px solid ${k.border}`,
        borderRadius: 4,
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        fontFamily: k.fontFamily,
      }}
    >
      {/* ── HEADER & CONTROLS ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Position Sizing & P&L Calculator
          </span>
          <span
            style={{
              fontSize: 9.5,
              fontWeight: 600,
              padding: '1px 5px',
              borderRadius: 2,
              background: optionType === 'CE' ? `${k.green}18` : `${k.red}18`,
              color: optionType === 'CE' ? k.green : k.red,
            }}
          >
            {optionType}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {isCustomized && (
            <button
              type="button"
              onClick={resetDefaults}
              style={{
                fontSize: 10.5,
                fontWeight: 500,
                color: k.blue,
                background: 'transparent',
                border: 0,
                cursor: 'pointer',
                padding: '2px 6px',
              }}
            >
              Reset Defaults
            </button>
          )}
          <span style={{ fontSize: 10, color: k.dim }}>
            {totalQty} Qty ({numLots} {numLots === 1 ? 'Lot' : 'Lots'} × {lotSize})
          </span>
        </div>
      </div>

      {/* ── INTERACTIVE INPUT FIELDS ── */}
      <div
        style={{
          background: k.surface,
          border: `1px solid ${k.border}`,
          borderRadius: 3,
          padding: '8px 10px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
          gap: 8,
          alignItems: 'center',
        }}
      >
        {/* Lots Stepper */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <label style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
            Lots
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <button
              type="button"
              onClick={() => setNumLots((prev) => Math.max(1, prev - 1))}
              style={{
                width: 22,
                height: 22,
                borderRadius: 2,
                border: `1px solid ${k.border}`,
                background: k.bg,
                color: k.text,
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 0,
              }}
            >
              -
            </button>
            <input
              type="number"
              min={1}
              max={500}
              value={numLots}
              onChange={(e) => setNumLots(Math.max(1, Number(e.target.value)))}
              style={{
                width: 36,
                height: 22,
                padding: '0 2px',
                fontSize: 11.5,
                fontWeight: 600,
                borderRadius: 2,
                border: `1px solid ${k.border}`,
                background: k.bg,
                color: k.text,
                textAlign: 'center',
                outline: 'none',
              }}
            />
            <button
              type="button"
              onClick={() => setNumLots((prev) => prev + 1)}
              style={{
                width: 22,
                height: 22,
                borderRadius: 2,
                border: `1px solid ${k.border}`,
                background: k.bg,
                color: k.text,
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 0,
              }}
            >
              +
            </button>
          </div>
        </div>

        {/* Lot Size (Fixed Exchange Contract Spec) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <label style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
            Lot Size
          </label>
          <div
            style={{
              height: 22,
              padding: '0 8px',
              fontSize: 11.5,
              fontWeight: 600,
              borderRadius: 2,
              border: `1px solid ${k.border}`,
              background: k.surfaceHover,
              color: k.text,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              userSelect: 'none',
              fontVariantNumeric: 'tabular-nums',
            }}
            title="Exchange-fixed contract lot size"
          >
            {lotSize}
          </div>
        </div>

        {/* Entry Price */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <label style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
            Entry Price (₹)
          </label>
          <input
            type="number"
            step={0.05}
            value={entryPrice}
            onChange={(e) => setEntryPrice(roundToTick(Number(e.target.value)) ?? Number(e.target.value))}
            style={{
              height: 22,
              padding: '0 6px',
              fontSize: 11,
              fontWeight: 600,
              borderRadius: 2,
              border: `1px solid ${k.border}`,
              background: k.bg,
              color: k.text,
              outline: 'none',
            }}
          />
        </div>

        {/* Stop Loss (SL) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <label style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
            Stop Loss (₹)
          </label>
          <input
            type="number"
            step={0.05}
            value={slPrice}
            onChange={(e) => setSlPrice(roundToTick(Number(e.target.value)) ?? Number(e.target.value))}
            style={{
              height: 22,
              padding: '0 6px',
              fontSize: 11,
              fontWeight: 500,
              borderRadius: 2,
              border: `1px solid ${k.border}`,
              background: k.bg,
              color: k.text,
              outline: 'none',
            }}
          />
        </div>

        {/* Total Investment Card */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
            Capital Deployed
          </span>
          <span style={{ fontSize: 12, fontWeight: 600, color: k.text, fontVariantNumeric: 'tabular-nums' }}>
            ₹{fmt(totalInvestment, 2)}
          </span>
        </div>
      </div>

      {/* ── REAL-TIME RESULTS & PERFORMANCE CARDS ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 6 }}>
        {/* 1. Points Covered */}
        <div
          style={{
            background: k.surface,
            border: `1px solid ${k.border}`,
            borderRadius: 3,
            padding: '6px 8px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          <span style={{ fontSize: 9, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
            Points Covered
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: isProfit ? k.green : k.red,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {coveredPoints >= 0 ? '+' : ''}{fmt(coveredPoints, 2)} pts
          </span>
          <span style={{ fontSize: 9.5, color: isProfit ? k.green : k.red }}>
            ({coveredPct >= 0 ? '+' : ''}{fmt(coveredPct, 2)}%)
          </span>
        </div>

        {/* 2. Unrealized MTM P&L */}
        <div
          style={{
            background: isProfit ? `${k.green}10` : `${k.red}10`,
            border: `1px solid ${isProfit ? k.green : k.red}30`,
            borderRadius: 3,
            padding: '6px 8px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          <span style={{ fontSize: 9, fontWeight: 600, color: isProfit ? k.green : k.red, textTransform: 'uppercase' }}>
            Unrealized MTM P&L
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: isProfit ? k.green : k.red,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {unrealizedPnl >= 0 ? '+' : ''}₹{fmt(unrealizedPnl, 2)}
          </span>
          <span style={{ fontSize: 9.5, color: isProfit ? k.green : k.red }}>
            {isProfit ? 'PROFIT' : 'DRAWDOWN'} ({realizedRR}R)
          </span>
        </div>

        {/* 3. Defined Hard SL Risk */}
        <div
          style={{
            background: k.surface,
            border: `1px solid ${k.border}`,
            borderRadius: 3,
            padding: '6px 8px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          <span style={{ fontSize: 9, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
            Defined SL Risk
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: k.red,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            -₹{fmt(maxRiskAmount, 2)}
          </span>
          <span style={{ fontSize: 9.5, color: k.dim }}>
            -{fmt(slDistance, 2)} pts (-₹{fmt(riskPerLot, 2)}/lot)
          </span>
        </div>

        {/* 4. TSL Protection */}
        <div
          style={{
            background: isRiskFree ? `${k.green}08` : k.surface,
            border: `1px solid ${isRiskFree ? `${k.green}30` : k.border}`,
            borderRadius: 3,
            padding: '6px 8px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          <span style={{ fontSize: 9, fontWeight: 600, color: isRiskFree ? k.green : k.dim, textTransform: 'uppercase' }}>
            {isRiskFree ? 'TSL Locked Profit' : 'TSL Risk Buffer'}
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: isRiskFree ? k.green : k.orange,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {tslPnl >= 0 ? `+₹${fmt(tslPnl, 2)}` : `-₹${fmt(Math.abs(tslPnl), 2)}`}
          </span>
          <span style={{ fontSize: 9.5, color: isRiskFree ? k.green : k.dim }}>
            {isRiskFree ? (tslDistance > 0 ? `+${fmt(tslDistance, 2)} pts locked` : 'Break-Even (0 Risk)') : `@ ₹${fmt(tslPrice, 2)}`}
          </span>
        </div>

        {/* 5. Target Reward */}
        <div
          style={{
            background: k.surface,
            border: `1px solid ${k.border}`,
            borderRadius: 3,
            padding: '6px 8px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          <span style={{ fontSize: 9, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
            Target Reward
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: k.purple,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            +₹{fmt(targetReward, 2)}
          </span>
          <span style={{ fontSize: 9.5, color: k.dim }}>
            +{fmt(targetDistance, 2)} pts (1 : {riskRewardRatio} R)
          </span>
        </div>
      </div>
    </div>
  );
}

export default AdaptiveEdgePositionCalculator;
