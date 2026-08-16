import React, { useMemo, useState } from 'react';
import { k } from '../../styles/kiteUI';
import { fmt } from './AdaptiveEdgePanel';
import { roundToTick, fmtTick, fmtINR } from '../../utils/fmt';

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
  exitState?: string | null;
}

export function AdaptiveEdgePositionCalculator({
  symbol,
  defaultEntryPrice,
  defaultSl,
  defaultTsl,
  defaultExit,
  currentLtp,
  optionType = 'CE',
  exitState,
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
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        fontFamily: k.fontFamily,
      }}
    >
      {/* ── TOP INPUTS & POSITION SIZING CARD ── */}
      <div
        style={{
          background: '#ffffff',
          border: `1px solid ${k.border}`,
          borderRadius: 4,
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: k.text }}>Position Sizing & Trade Plan</span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 500,
              padding: '1px 6px',
              borderRadius: 2,
              background: optionType === 'CE' ? `${k.green}18` : `${k.red}18`,
              color: optionType === 'CE' ? k.green : k.red,
            }}
          >
            {optionType}
          </span>
        </div>

        {/* Inputs controls strip */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          {/* Lots */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <label style={{ fontSize: 11.5, color: k.dim }}>Lots</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <button
                type="button"
                onClick={() => setNumLots((prev) => Math.max(1, prev - 1))}
                style={{
                  width: 20,
                  height: 22,
                  borderRadius: 2,
                  border: `1px solid ${k.border}`,
                  background: k.surface,
                  color: k.text,
                  fontSize: 12,
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
                  borderRadius: 2,
                  border: `1px solid ${k.border}`,
                  background: '#ffffff',
                  color: k.text,
                  textAlign: 'center',
                  outline: 'none',
                }}
              />
              <button
                type="button"
                onClick={() => setNumLots((prev) => prev + 1)}
                style={{
                  width: 20,
                  height: 22,
                  borderRadius: 2,
                  border: `1px solid ${k.border}`,
                  background: k.surface,
                  color: k.text,
                  fontSize: 12,
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

          {/* Entry */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <label style={{ fontSize: 11.5, color: k.dim }}>Entry (₹)</label>
            <input
              type="number"
              step={0.05}
              value={entryPrice}
              onChange={(e) => setEntryPrice(roundToTick(Number(e.target.value)) ?? Number(e.target.value))}
              style={{
                width: 68,
                height: 22,
                padding: '0 6px',
                fontSize: 11.5,
                borderRadius: 2,
                border: `1px solid ${k.border}`,
                background: '#ffffff',
                color: k.text,
                outline: 'none',
              }}
            />
          </div>

          {/* SL */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <label style={{ fontSize: 11.5, color: k.dim }}>SL (₹)</label>
            <input
              type="number"
              step={0.05}
              value={slPrice}
              onChange={(e) => setSlPrice(roundToTick(Number(e.target.value)) ?? Number(e.target.value))}
              style={{
                width: 68,
                height: 22,
                padding: '0 6px',
                fontSize: 11.5,
                borderRadius: 2,
                border: `1px solid ${k.border}`,
                background: '#ffffff',
                color: k.text,
                outline: 'none',
              }}
            />
          </div>

          {/* TSL */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <label style={{ fontSize: 11.5, color: k.dim }}>TSL (₹)</label>
            <input
              type="number"
              step={0.05}
              value={tslPrice}
              onChange={(e) => setTslPrice(roundToTick(Number(e.target.value)) ?? Number(e.target.value))}
              style={{
                width: 68,
                height: 22,
                padding: '0 6px',
                fontSize: 11.5,
                borderRadius: 2,
                border: `1px solid ${k.border}`,
                background: '#ffffff',
                color: k.orange,
                outline: 'none',
              }}
            />
          </div>

          {/* Target */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <label style={{ fontSize: 11.5, color: k.dim }}>Target (₹)</label>
            <input
              type="number"
              step={0.05}
              value={targetPrice}
              onChange={(e) => setTargetPrice(roundToTick(Number(e.target.value)) ?? Number(e.target.value))}
              style={{
                width: 68,
                height: 22,
                padding: '0 6px',
                fontSize: 11.5,
                borderRadius: 2,
                border: `1px solid ${k.border}`,
                background: '#ffffff',
                color: k.purple,
                outline: 'none',
              }}
            />
          </div>

          {isCustomized && (
            <button
              type="button"
              onClick={resetDefaults}
              style={{
                fontSize: 11,
                color: k.blue,
                background: 'transparent',
                border: 0,
                cursor: 'pointer',
                padding: 0,
                textDecoration: 'underline',
              }}
            >
              Reset Defaults
            </button>
          )}

          <span style={{ fontSize: 11.5, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>
            {totalQty} Qty ({numLots} {numLots === 1 ? 'Lot' : 'Lots'} × {lotSize})
          </span>
        </div>
      </div>

      {/* ── 3 DISTINCT CARDS ── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 10,
        }}
      >
        {/* CARD 1: POSITION & LIVE MTM */}
        <div
          style={{
            background: '#ffffff',
            border: `1px solid ${k.border}`,
            borderRadius: 4,
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 6, borderBottom: `1px solid ${k.border}` }}>
            <span style={{ fontSize: 11, fontWeight: 500, color: k.text, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Position & MTM
            </span>
            <span style={{ fontSize: 10.5, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>
              {totalQty} Qty
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>Capital deployed</span>
              <span style={{ color: k.text, fontVariantNumeric: 'tabular-nums' }}>{fmtINR(totalInvestment)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>Current LTP</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                <span style={{ color: coveredPoints >= 0 ? k.green : k.red }}>₹{fmtTick(liveLtp)}</span>
                <span style={{ color: coveredPoints >= 0 ? k.green : k.red, fontSize: 11, marginLeft: 6 }}>
                  ({coveredPoints >= 0 ? '+' : ''}{fmtTick(coveredPoints)} pts · {coveredPct >= 0 ? '+' : ''}{coveredPct.toFixed(2)}%)
                </span>
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>Points covered</span>
              <span style={{ color: coveredPoints >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
                {coveredPoints >= 0 ? '+' : ''}{fmtTick(coveredPoints)} pts ({coveredPct >= 0 ? '+' : ''}{coveredPct.toFixed(2)}%)
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>Unrealized MTM P&L</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                <span style={{ color: unrealizedPnl >= 0 ? k.green : k.red }}>
                  {fmtINR(unrealizedPnl, { showSign: true })}
                </span>
                <span style={{ color: unrealizedPnl >= 0 ? k.green : k.red, fontSize: 11, marginLeft: 6 }}>
                  ({isProfit ? 'PROFIT' : 'DRAWDOWN'} · {realizedRR}R)
                </span>
              </span>
            </div>
          </div>
        </div>

        {/* CARD 2: RISK & STOP PROTECTION */}
        <div
          style={{
            background: '#ffffff',
            border: `1px solid ${k.border}`,
            borderRadius: 4,
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 6, borderBottom: `1px solid ${k.border}` }}>
            <span style={{ fontSize: 11, fontWeight: 500, color: k.text, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Risk & Stops
            </span>
            <span style={{ fontSize: 10.5, color: k.red, fontVariantNumeric: 'tabular-nums' }}>
              Max -{fmtINR(maxRiskAmount)}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>Stop (SL)</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                <span style={{ color: k.text }}>₹{fmtTick(slPrice)}</span>
                <span style={{ color: k.dim, fontSize: 11, marginLeft: 6 }}>(-{fmtTick(slDistance)} pts)</span>
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>Defined SL risk</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                <span style={{ color: k.red }}>{fmtINR(-maxRiskAmount)}</span>
                <span style={{ color: k.dim, fontSize: 11, marginLeft: 6 }}>(-{fmtINR(riskPerLot)}/lot)</span>
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>Trail (TSL)</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                <span style={{ color: isRiskFree ? k.green : k.orange }}>₹{fmtTick(tslPrice)}</span>
                <span style={{ color: isRiskFree ? k.green : k.dim, fontSize: 11, marginLeft: 6 }}>
                  ({isRiskFree ? (tslDistance > 0 ? `+${fmtTick(tslDistance)} pts locked` : 'Break-Even') : 'Trail'})
                </span>
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>{isRiskFree ? 'TSL locked profit' : 'TSL risk buffer'}</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                <span style={{ color: isRiskFree ? k.green : k.orange }}>
                  {fmtINR(tslPnl, { showSign: true })}
                </span>
                <span style={{ color: k.dim, fontSize: 11, marginLeft: 6 }}>@ ₹{fmtTick(tslPrice)}</span>
              </span>
            </div>
          </div>
        </div>

        {/* CARD 3: TARGET & EXIT STRATEGY */}
        <div
          style={{
            background: '#ffffff',
            border: `1px solid ${k.border}`,
            borderRadius: 4,
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 6, borderBottom: `1px solid ${k.border}` }}>
            <span style={{ fontSize: 11, fontWeight: 500, color: k.text, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Target & Exit
            </span>
            <span style={{ fontSize: 10.5, color: k.purple, fontVariantNumeric: 'tabular-nums' }}>
              1 : {riskRewardRatio} R
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>Target price</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                <span style={{ color: k.purple }}>₹{fmtTick(targetPrice)}</span>
                <span style={{ color: k.dim, fontSize: 11, marginLeft: 6 }}>(+{fmtTick(targetDistance)} pts)</span>
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>Target reward</span>
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                <span style={{ color: k.purple }}>{fmtINR(targetReward, { showSign: true })}</span>
                <span style={{ color: k.dim, fontSize: 11, marginLeft: 6 }}>(1 : {riskRewardRatio} R)</span>
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ color: k.dim }}>Exit status</span>
              <span style={{ color: exitState && exitState.includes('red') ? k.orange : k.text, fontVariantNumeric: 'tabular-nums' }}>
                {exitState || 'Trailing SuperTrend'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdaptiveEdgePositionCalculator;
