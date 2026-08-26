import React, { useState } from 'react';
import { k, tint } from '../../styles/kiteUI';
import { roundToTick, fmtTick } from '../../utils/fmt';

interface StepDetail {
  id: number;
  title: string;
  subtitle: string;
  tag: string;
  tagColor: string;
  description: string;
  keyPoints: string[];
}

const STEPS: StepDetail[] = [
  {
    id: 1,
    title: '1. Tape & Order Flow Ingestion',
    subtitle: 'L2/L3 Footprint & Cumulative Delta',
    tag: 'DATA INGESTION',
    tagColor: k.blue,
    description:
      'Adaptive Edge continuously streams tick-by-tick market orders, measuring the exact aggressive buy vs. sell volume at every micro-price level across both Spot and Options chains.',
    keyPoints: [
      'Aggressive market orders calculated into real-time Cumulative Volume Delta (CVD)',
      'Identifies institutional absorption where high volume executes without adverse price movement',
      'Filters out passive resting limit noise from genuine aggressive directional liquidity',
    ],
  },
  {
    id: 2,
    title: '2. Microstructure & POC Anchors',
    subtitle: 'Volume Profile & Session VWAP',
    tag: 'ANCHOR ENGINE',
    tagColor: k.purple,
    description:
      'The engine constructs dynamic 30-minute Market Profile TPO and Volume Profiles, pinpointing the Point of Control (POC), Value Area High (VAH), and Value Area Low (VAL).',
    keyPoints: [
      'Point of Control (POC): Price level with highest traded volume acting as magnetic support/resistance',
      'Session VWAP: Institutional volume-weighted benchmark anchoring macro fair value',
      'Value Area (VA): 70% volume distribution bracket defining value acceptance vs. rejection',
    ],
  },
  {
    id: 3,
    title: '3. Model Scoring & Conviction Trigger',
    subtitle: 'Multi-factor quantitative composite',
    tag: 'SIGNAL SCORER',
    tagColor: k.green,
    description:
      'A multi-variable quantitative algorithm evaluates CVD momentum, VWAP slope, and POC rejection to generate a composite conviction Model Score from -1.00 (Strong Bear) to +1.00 (Strong Bull).',
    keyPoints: [
      'Threshold Gating: Only signals exceeding conviction score (e.g. ≥ +0.60) trigger active setups',
      'Horizon Tagging: Automatically tags trade as IMPULSE (rapid liquidity grab) or SESSION_TREND',
      'Rejection Confirmation: Confirms price bounce off POC / VWAP anchors before strike activation',
    ],
  },
  {
    id: 4,
    title: '4. Strike Mapping & Greeks Calibration',
    subtitle: 'Automatic derivative contract resolution',
    tag: 'OPTIONS RESOLVER',
    tagColor: k.orange,
    description:
      'Once a spot microstructure thesis is confirmed, the engine resolves the optimal option contract (e.g. NIFTY 24500 CE) calibrated for maximum Delta response and minimal Theta bleed.',
    keyPoints: [
      'Selects ATM / near-OTM contracts with optimal Delta (Δ ≈ 0.50 - 0.65) for maximum price sensitivity',
      'Computes carry-adjusted R:R balancing 1R underlying moves against 1 session of Theta (Θ) decay',
      'Establishes exact Entry Premium, Initial Hard Stop (SL), and Trailing Stop (TSL) bounds',
    ],
  },
  {
    id: 5,
    title: '5. Dynamic Scalp Escalation & Protection',
    subtitle: 'MICRO ➔ SCALP ➔ INTRADAY Mode Matrix',
    tag: 'RISK MANAGEMENT',
    tagColor: k.red,
    description:
      'Trades start in MICRO scalp mode and dynamically escalate as momentum proves itself. If momentum decays, the engine automatically defends gains by ratcheting trailing stops.',
    keyPoints: [
      'MICRO (1R target) ↗ SCALP (>1.5R expansion) ↗ INTRADAY (macro session breakout)',
      'Decay Protection: If CVD stalls, defensive downgrade (↘ MICRO) tightens the trailing stop (TSL)',
      '100% Rule-Based Exit: Positions close cleanly when premium hits TSL or red counter completes',
    ],
  },
];

export function AdaptiveEdgeHelpVisualizer() {
  const [activeStep, setActiveStep] = useState<number>(1);
  
  // ── Editable Parameters for Realtime Simulation & PnL ──
  const [lotSize, setLotSize] = useState<number>(25); // Nifty standard lot
  const [numLots, setNumLots] = useState<number>(2); // 2 lots = 50 qty
  const [entryPrice, setEntryPrice] = useState<number>(504.35);
  const [initialSl, setInitialSl] = useState<number>(380.55);
  const [exitTarget, setExitTarget] = useState<number>(620.00);
  const [tslOffset, setTslOffset] = useState<number>(30.0); // trail distance in pts
  const [beTrigger, setBeTrigger] = useState<number>(20.0); // break-even profit threshold in pts

  // ── Interactive Simulation Sandbox State ──
  const [simSpot, setSimSpot] = useState<number>(24465);
  const baseSpot = 24465;
  const spotDiff = simSpot - baseSpot;

  // Derived simulation metrics
  const totalQty = Math.max(1, lotSize * numLots);
  const simCvd = Math.round(39075 + spotDiff * 850);
  const simModelScore = Math.min(0.98, Math.max(0.05, 0.62 + (spotDiff / 100) * 0.35));
  
  // Dynamic Mode calculation based on spot gain
  let simMode = 'MICRO';
  let simModeBadge = 'MICRO';
  let simModeColor = k.blue;
  if (spotDiff >= 60) {
    simMode = 'INTRADAY';
    simModeBadge = 'SCALP ↗ INTRADAY';
    simModeColor = k.orange;
  } else if (spotDiff >= 25) {
    simMode = 'SCALP';
    simModeBadge = 'MICRO ↗ SCALP';
    simModeColor = k.green;
  } else if (spotDiff < -10) {
    simMode = 'MICRO';
    simModeBadge = 'SCALP ↘ MICRO';
    simModeColor = k.purple;
  }

  // Option Strike Simulation (Delta ≈ 0.55)
  const currentLtp = Math.max(10, Number((entryPrice + spotDiff * 0.55).toFixed(2)));
  const ptsDiff = Number((currentLtp - entryPrice).toFixed(2));
  const ptsPct = Number(((ptsDiff / entryPrice) * 100).toFixed(2));
  const netPnlUsd = Number((ptsDiff * totalQty).toFixed(2));

  // Dynamic Trailing Stop Loss (TSL) Logic:
  // 1. If gain < beTrigger: TSL stays at initial hard SL
  // 2. If gain >= beTrigger: TSL ratchets to at least Break-Even (entryPrice)
  // 3. As price advances further: TSL ratchets up to (currentLtp - tslOffset), ratcheting higher only!
  let dynamicTsl = initialSl;
  if (ptsDiff >= beTrigger) {
    dynamicTsl = Math.max(entryPrice, currentLtp - tslOffset);
  }
  dynamicTsl = Number(dynamicTsl.toFixed(2));

  // Locked-In Profit / Defined Risk at TSL
  const tslPtsDiff = Number((dynamicTsl - entryPrice).toFixed(2));
  const tslPnl = Number((tslPtsDiff * totalQty).toFixed(2));
  const isRiskFree = dynamicTsl >= entryPrice;

  // Max Capital at Risk (Initial)
  const initialRiskPts = Math.max(0, entryPrice - initialSl);
  const maxRiskAmount = Number((initialRiskPts * totalQty).toFixed(2));

  // Max Potential Target Profit
  const targetProfitPts = Math.max(0, exitTarget - entryPrice);
  const maxTargetAmount = Number((targetProfitPts * totalQty).toFixed(2));

  // Current Risk-to-Reward (R:R)
  const currentRR = initialRiskPts > 0 ? (ptsDiff / initialRiskPts).toFixed(2) : '1.00';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, fontFamily: k.fontFamily }}>
      
      {/* ── Top Hero Card: Adaptive Edge Summary ── */}
      <div
        style={{
          background: `linear-gradient(135deg, ${tint(k.blue, 6)} 0%, ${tint(k.purple, 6)} 100%)`,
          border: `1px solid ${k.border}`,
          borderRadius: 4,
          padding: '16px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 650, color: k.text, letterSpacing: '-0.01em' }}>
              Adaptive Edge — Hybrid Microstructure & Scalp Engine
            </span>
          </div>
          <span
            style={{
              fontSize: 9.5,
              fontWeight: 600,
              padding: '2px 7px',
              borderRadius: 2,
              background: `${k.blue}15`,
              color: k.blue,
              letterSpacing: '0.04em',
            }}
          >
            END-TO-END WORKFLOW & PNL SIMULATOR
          </span>
        </div>
        <p style={{ fontSize: 12, color: k.text, lineHeight: 1.5, margin: 0, opacity: 0.9 }}>
          Unlike standard indicators that only look at lagging bar closes, <b>Adaptive Edge</b> reads the live <b>order flow tape</b>, 
          <b> volume footprint imbalances</b>, and <b>anchored VWAP / POC structures</b>. It automatically translates spot momentum 
          into high-conviction options execution with real-time dynamic trailing stops and multi-stage mode escalation.
        </p>
      </div>

      {/* ── Pictorial Architecture Pipeline Ribbon ── */}
      <div>
        <div style={{ fontSize: 10.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>
          End-to-End Architectural Pipeline (Click stage to inspect)
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: 8,
          }}
        >
          {STEPS.map((step) => {
            const isSelected = activeStep === step.id;
            return (
              <div
                key={step.id}
                onClick={() => setActiveStep(step.id)}
                style={{
                  background: isSelected ? k.surfaceHover : k.bg,
                  border: `1px solid ${isSelected ? step.tagColor : k.border}`,
                  borderTop: isSelected ? `3px solid ${step.tagColor}` : `1px solid ${k.border}`,
                  borderRadius: 4,
                  padding: '10px 12px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                  boxShadow: isSelected ? '0 2px 4px rgba(0,0,0,0.04)' : 'none',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 9.5, fontWeight: 700, color: step.tagColor, letterSpacing: '0.03em' }}>
                    {step.tag}
                  </span>
                  <span style={{ fontSize: 10, color: isSelected ? step.tagColor : k.dim, fontWeight: 700 }}>
                    #{step.id}
                  </span>
                </div>
                <div style={{ fontSize: 12, fontWeight: 650, color: k.text, lineHeight: 1.3 }}>
                  {step.title.split('. ')[1]}
                </div>
                <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.2 }}>
                  {step.subtitle}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Active Stage Detail Card ── */}
      {(() => {
        const cur = STEPS.find((s) => s.id === activeStep) || STEPS[0];
        return (
          <div
            style={{
              background: k.bg,
              border: `1px solid ${k.border}`,
              borderRadius: 6,
              padding: '18px 20px',
              display: 'flex',
              flexDirection: 'column',
              gap: 14,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: cur.tagColor, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  STAGE {cur.id} OF 5 · {cur.tag}
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, color: k.text, marginTop: 2 }}>
                  {cur.title} — {cur.subtitle}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  type="button"
                  disabled={activeStep === 1}
                  onClick={() => setActiveStep((prev) => Math.max(1, prev - 1))}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    fontWeight: 600,
                    borderRadius: 3,
                    border: `1px solid ${k.border}`,
                    background: k.bg,
                    color: activeStep === 1 ? k.dim : k.text,
                    cursor: activeStep === 1 ? 'not-allowed' : 'pointer',
                  }}
                >
                  ← Prev Stage
                </button>
                <button
                  type="button"
                  disabled={activeStep === 5}
                  onClick={() => setActiveStep((prev) => Math.min(5, prev + 1))}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    fontWeight: 600,
                    borderRadius: 3,
                    border: `1px solid ${k.border}`,
                    background: k.bg,
                    color: activeStep === 5 ? k.dim : k.text,
                    cursor: activeStep === 5 ? 'not-allowed' : 'pointer',
                  }}
                >
                  Next Stage →
                </button>
              </div>
            </div>

            <p style={{ fontSize: 12, color: k.text, lineHeight: 1.6, margin: 0 }}>
              {cur.description}
            </p>

            <div style={{ background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4, padding: '12px 16px' }}>
              <div style={{ fontSize: 10.5, fontWeight: 700, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>
                Key Technical Mechanics:
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 11.5, color: k.text, display: 'flex', flexDirection: 'column', gap: 6, lineHeight: 1.5 }}>
                {cur.keyPoints.map((pt, idx) => (
                  <li key={idx}><b>{pt.split(':')[0]}:</b>{pt.split(':')[1] || ''}</li>
                ))}
              </ul>
            </div>
          </div>
        );
      })()}

      {/* ── Pictorial Visual Graphic & Dynamic Mode Escalator Matrix ── */}
      <div
        style={{
          background: k.bg,
          border: `1px solid ${k.border}`,
          borderRadius: 6,
          padding: '18px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        <div style={{ fontSize: 10.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Dynamic Scalp Escalation & Risk Matrix
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
          {/* Mode 1: MICRO */}
          <div style={{ background: `${k.blue}0a`, border: `1px solid ${k.blue}30`, borderRadius: 4, padding: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, fontWeight: 650, color: k.blue }}>1. MICRO</span>
              <span style={{ fontSize: 9.5, fontWeight: 600, background: `${k.blue}18`, color: k.blue, padding: '1px 5px', borderRadius: 2 }}>1.0R</span>
            </div>
            <div style={{ fontSize: 11, color: k.text, fontWeight: 500 }}>Quick Impulse Scalp</div>
            <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4 }}>
              Entry triggered on initial tape CVD impulse. Hard initial stop with quick 1R profit objective.
            </div>
          </div>

          {/* Mode 2: SCALP */}
          <div style={{ background: `${k.green}0a`, border: `1px solid ${k.green}30`, borderRadius: 4, padding: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, fontWeight: 650, color: k.green }}>2. SCALP (↗)</span>
              <span style={{ fontSize: 9.5, fontWeight: 600, background: `${k.green}18`, color: k.green, padding: '1px 5px', borderRadius: 2 }}>&gt;1.5R</span>
            </div>
            <div style={{ fontSize: 11, color: k.text, fontWeight: 500 }}>Momentum Expansion</div>
            <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4 }}>
              Dynamic upgrade when volume delta exceeds baseline without liquidity absorption resistance.
            </div>
          </div>

          {/* Mode 3: EXTENDED */}
          <div style={{ background: `${k.purple}0a`, border: `1px solid ${k.purple}30`, borderRadius: 4, padding: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, fontWeight: 650, color: k.purple }}>3. EXTENDED (↗)</span>
              <span style={{ fontSize: 9.5, fontWeight: 600, background: `${k.purple}18`, color: k.purple, padding: '1px 5px', borderRadius: 2 }}>&gt;2.5R</span>
            </div>
            <div style={{ fontSize: 11, color: k.text, fontWeight: 500 }}>Trend Continuation</div>
            <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4 }}>
              Value Area breakout sustained by institutional volume flow. Trailing stop ratchets to lock in 1R+.
            </div>
          </div>

          {/* Mode 4: INTRADAY */}
          <div style={{ background: `${k.orange}0a`, border: `1px solid ${k.orange}30`, borderRadius: 4, padding: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, fontWeight: 650, color: k.orange }}>4. INTRADAY (↗)</span>
              <span style={{ fontSize: 9.5, fontWeight: 600, background: `${k.orange}18`, color: k.orange, padding: '1px 5px', borderRadius: 2 }}>&gt;4.0R</span>
            </div>
            <div style={{ fontSize: 11, color: k.text, fontWeight: 500 }}>Full Session Runner</div>
            <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4 }}>
              Full structural trend day. Trailing stop protects open runner until trend exhausts or TSL hit.
            </div>
          </div>
        </div>

        <div style={{ fontSize: 11, color: k.dim, lineHeight: 1.5, background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4, padding: '8px 12px' }}>
          <b>Defensive Decay Guard (↘):</b> When momentum decays or CVD stalls, the badge dynamically reflects decay (e.g. <code>INTRADAY ↘ SCALP ↘ MICRO</code>) and automatically tightens the trailing stop to lock in peak unrealized gains.
        </div>
      </div>

      {/* ── Interactive Live Simulation Sandbox & Editable PnL Model ── */}
      <div
        style={{
          background: k.bg,
          border: `1px solid ${k.border}`,
          borderRadius: 4,
          padding: '18px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 14, fontWeight: 650, color: k.text }}>
                Interactive Sandbox Simulation & Real-Time P&L Engine
              </span>
            </div>
            <div style={{ fontSize: 11, color: k.dim, marginTop: 2 }}>
              Edit lot size, entry, hard SL, exit target, and trailing stop parameters to test how TSL protects and locks in live profits.
            </div>
          </div>

          {/* Quick Preset Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
            <button
              type="button"
              onClick={() => setSimSpot(24465)}
              style={{
                padding: '4px 8px',
                fontSize: 10.5,
                fontWeight: 500,
                borderRadius: 3,
                border: `1px solid ${k.border}`,
                background: simSpot === 24465 ? k.surfaceHover : k.bg,
                color: k.text,
                cursor: 'pointer',
              }}
            >
              Reset Entry (₹24,465)
            </button>
            <button
              type="button"
              onClick={() => setSimSpot(24505)}
              style={{
                padding: '4px 8px',
                fontSize: 10.5,
                fontWeight: 500,
                borderRadius: 3,
                border: `1px solid ${k.green}40`,
                background: `${k.green}10`,
                color: k.green,
                cursor: 'pointer',
              }}
            >
              +40 pts Scalp (₹24,505)
            </button>
            <button
              type="button"
              onClick={() => setSimSpot(24555)}
              style={{
                padding: '4px 8px',
                fontSize: 10.5,
                fontWeight: 500,
                borderRadius: 3,
                border: `1px solid ${k.orange}40`,
                background: `${k.orange}10`,
                color: k.orange,
                cursor: 'pointer',
              }}
            >
              +90 pts Breakout (₹24,555)
            </button>
            <button
              type="button"
              onClick={() => setSimSpot(24435)}
              style={{
                padding: '4px 8px',
                fontSize: 10.5,
                fontWeight: 500,
                borderRadius: 3,
                border: `1px solid ${k.red}40`,
                background: `${k.red}10`,
                color: k.red,
                cursor: 'pointer',
              }}
            >
              -30 pts Pullback (₹24,435)
            </button>
          </div>
        </div>

        {/* ── Editable Configuration Panel (Lot Size, Entry, SL, Target, TSL Offset) ── */}
        <div
          style={{
            background: k.surface,
            border: `1px solid ${k.border}`,
            borderRadius: 4,
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          <div style={{ fontSize: 10.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Editable Trade & Execution Parameters
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(135px, 1fr))',
              gap: 10,
            }}
          >
            {/* Lot Size & Number of Lots */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 10, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
                Lots × Lot Size
              </label>
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={numLots}
                  onChange={(e) => setNumLots(Math.max(1, Number(e.target.value)))}
                  style={{
                    width: 48,
                    padding: '4px 6px',
                    fontSize: 11.5,
                    fontWeight: 500,
                    borderRadius: 3,
                    border: `1px solid ${k.border}`,
                    background: k.bg,
                    color: k.text,
                    textAlign: 'center',
                  }}
                />
                <span style={{ fontSize: 11, color: k.dim }}>×</span>
                <input
                  type="number"
                  min={1}
                  step={5}
                  value={lotSize}
                  onChange={(e) => setLotSize(Math.max(1, Number(e.target.value)))}
                  style={{
                    width: 48,
                    padding: '4px 6px',
                    fontSize: 11.5,
                    fontWeight: 500,
                    borderRadius: 3,
                    border: `1px solid ${k.border}`,
                    background: k.bg,
                    color: k.text,
                    textAlign: 'center',
                  }}
                />
              </div>
              <span style={{ fontSize: 9.5, color: k.dim }}>= <b>{totalQty}</b> total Qty</span>
            </div>

            {/* Entry Premium */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 10, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
                Entry Premium (₹)
              </label>
              <input
                type="number"
                step={0.05}
                value={entryPrice}
                onChange={(e) => setEntryPrice(roundToTick(Number(e.target.value)) ?? Number(e.target.value))}
                style={{
                  padding: '4px 8px',
                  fontSize: 11.5,
                  fontWeight: 500,
                  borderRadius: 3,
                  border: `1px solid ${k.border}`,
                  background: k.bg,
                  color: k.text,
                }}
              />
              <span style={{ fontSize: 9.5, color: k.blue }}>Strike Entry Price</span>
            </div>

            {/* Initial Protective Hard SL */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 10, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
                Initial Hard SL (₹)
              </label>
              <input
                type="number"
                step={0.05}
                value={initialSl}
                onChange={(e) => setInitialSl(roundToTick(Number(e.target.value)) ?? Number(e.target.value))}
                style={{
                  padding: '4px 8px',
                  fontSize: 11.5,
                  fontWeight: 500,
                  borderRadius: 3,
                  border: `1px solid ${k.border}`,
                  background: k.bg,
                  color: k.text,
                }}
              />
              <span style={{ fontSize: 9.5, color: k.red }}>Max Risk: -₹{maxRiskAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>

            {/* Exit Target / Take Profit */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 10, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
                Exit Target (₹)
              </label>
              <input
                type="number"
                step={0.05}
                value={exitTarget}
                onChange={(e) => setExitTarget(roundToTick(Number(e.target.value)) ?? Number(e.target.value))}
                style={{
                  padding: '4px 8px',
                  fontSize: 11.5,
                  fontWeight: 500,
                  borderRadius: 3,
                  border: `1px solid ${k.border}`,
                  background: k.bg,
                  color: k.text,
                }}
              />
              <span style={{ fontSize: 9.5, color: k.green }}>Max Gain: +₹{maxTargetAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>

            {/* Trailing Stop Offset (pts) */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 10, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
                TSL Trail Offset (pts)
              </label>
              <input
                type="number"
                step={5}
                min={5}
                value={tslOffset}
                onChange={(e) => setTslOffset(Math.max(5, Number(e.target.value)))}
                style={{
                  padding: '4px 8px',
                  fontSize: 11.5,
                  fontWeight: 500,
                  borderRadius: 3,
                  border: `1px solid ${k.border}`,
                  background: k.bg,
                  color: k.text,
                }}
              />
              <span style={{ fontSize: 9.5, color: k.orange }}>Trail Buffer</span>
            </div>

            {/* Break-Even Trigger (pts) */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 10, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
                Break-Even Trigger (pts)
              </label>
              <input
                type="number"
                step={5}
                min={5}
                value={beTrigger}
                onChange={(e) => setBeTrigger(Math.max(5, Number(e.target.value)))}
                style={{
                  padding: '4px 8px',
                  fontSize: 11.5,
                  fontWeight: 500,
                  borderRadius: 3,
                  border: `1px solid ${k.border}`,
                  background: k.bg,
                  color: k.text,
                }}
              />
              <span style={{ fontSize: 9.5, color: k.purple }}>Risk-Free @ +{beTrigger} pts</span>
            </div>
          </div>
        </div>

        {/* Spot Price Slider Control */}
        <div style={{ background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4, padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
            <span style={{ fontWeight: 500, color: k.text }}>
              Simulated Spot Price: <span style={{ color: k.blue, fontWeight: 650 }}>₹{simSpot.toLocaleString('en-IN')}</span>
              <span style={{ marginLeft: 6, fontWeight: 500, color: spotDiff >= 0 ? k.green : k.red }}>
                ({spotDiff >= 0 ? '+' : ''}{spotDiff} pts)
              </span>
            </span>
            <span style={{ color: k.dim, fontSize: 10.5 }}>Simulated Option Delta: Δ 0.55</span>
          </div>
          <input
            type="range"
            min={24400}
            max={24580}
            step={5}
            value={simSpot}
            onChange={(e) => setSimSpot(Number(e.target.value))}
            style={{ width: '100%', cursor: 'pointer', accentColor: k.blue }}
          />
        </div>

        {/* ── Real-Time P&L & TSL Reaction Dashboard ── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 }}>
          
          {/* Current Option LTP */}
          <div style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 3, padding: '8px 10px' }}>
            <div style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>Live Option LTP</div>
            <div style={{ fontSize: 14, fontWeight: 650, color: ptsDiff >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
              ₹{currentLtp.toFixed(2)}
            </div>
            <div style={{ fontSize: 9.5, fontWeight: 500, color: ptsDiff >= 0 ? k.green : k.red, marginTop: 1 }}>
              {ptsDiff >= 0 ? '+' : ''}{ptsDiff.toFixed(2)} pts ({ptsPct >= 0 ? '+' : ''}{ptsPct}%)
            </div>
          </div>

          {/* Net Unrealized MTM PnL */}
          <div
            style={{
              background: ptsDiff >= 0 ? `${k.green}10` : `${k.red}10`,
              border: `1px solid ${ptsDiff >= 0 ? k.green : k.red}40`,
              borderRadius: 3,
              padding: '8px 10px',
            }}
          >
            <div style={{ fontSize: 9.5, fontWeight: 600, color: ptsDiff >= 0 ? k.green : k.red, textTransform: 'uppercase' }}>
              Unrealized MTM P&L
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, color: ptsDiff >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
              {netPnlUsd >= 0 ? '+' : ''}₹{netPnlUsd.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div style={{ fontSize: 9.5, color: ptsDiff >= 0 ? k.green : k.red, fontWeight: 500, marginTop: 1 }}>
              {ptsDiff >= 0 ? 'PROFIT' : 'LOSS'} ({totalQty} Qty)
            </div>
          </div>

          {/* Ratcheting Trailing Stop (TSL) */}
          <div style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 3, padding: '8px 10px' }}>
            <div style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>
              Ratcheted TSL
            </div>
            <div style={{ fontSize: 14, fontWeight: 650, color: k.orange, fontVariantNumeric: 'tabular-nums' }}>
              ₹{dynamicTsl.toFixed(2)}
            </div>
            <div style={{ fontSize: 9.5, color: isRiskFree ? k.green : k.dim, fontWeight: isRiskFree ? 600 : 400, marginTop: 1 }}>
              {isRiskFree ? 'RISK-FREE LOCK' : `Initial SL: ₹${initialSl}`}
            </div>
          </div>

          {/* Protected / Locked-In Profit at TSL */}
          <div
            style={{
              background: isRiskFree ? `${k.green}0a` : `${k.red}0a`,
              border: `1px solid ${isRiskFree ? k.green : k.red}30`,
              borderRadius: 3,
              padding: '8px 10px',
            }}
          >
            <div style={{ fontSize: 9.5, fontWeight: 600, color: isRiskFree ? k.green : k.red, textTransform: 'uppercase' }}>
              {isRiskFree ? 'Locked Profit @ TSL' : 'Defined Risk @ TSL'}
            </div>
            <div style={{ fontSize: 14, fontWeight: 650, color: isRiskFree ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
              {tslPnl >= 0 ? '+' : ''}₹{tslPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div style={{ fontSize: 9.5, color: isRiskFree ? k.green : k.red, fontWeight: 500, marginTop: 1 }}>
              {isRiskFree ? `${tslPtsDiff > 0 ? `+${tslPtsDiff} pts` : 'Break-Even (0 risk)'}` : `Max Loss: -₹${Math.abs(tslPnl).toLocaleString('en-IN')}`}
            </div>
          </div>

          {/* Risk-Reward & Mode */}
          <div style={{ background: `${simModeColor}10`, border: `1px solid ${simModeColor}40`, borderRadius: 3, padding: '8px 10px' }}>
            <div style={{ fontSize: 9.5, fontWeight: 600, color: simModeColor, textTransform: 'uppercase' }}>
              Mode & R:R Ratio
            </div>
            <div style={{ fontSize: 13, fontWeight: 650, color: simModeColor }}>
              {simModeBadge}
            </div>
            <div style={{ fontSize: 9.5, color: simModeColor, fontWeight: 500, marginTop: 1 }}>
              R:R: <b>{currentRR}R</b>
            </div>
          </div>
        </div>

        {/* ── Visual TSL Progression Ladder & Timeline Explainer ── */}
        <div style={{ background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            How Trailing Stop Loss (TSL) Protects You Step-by-Step
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8 }}>
            
            {/* Step 1 */}
            <div style={{ background: k.bg, border: `1px solid ${currentLtp < entryPrice + beTrigger ? k.blue : k.border}`, borderRadius: 4, padding: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 650, color: k.blue }}>PHASE 1: TRADE INCEPTION</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: k.text, marginTop: 2 }}>Entry @ ₹{entryPrice}</div>
              <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4, marginTop: 4 }}>
                Initial Hard SL placed at <b>₹{initialSl}</b>. Maximum capital risk defined as <b>-₹{maxRiskAmount.toLocaleString('en-IN')}</b>.
              </div>
            </div>

            {/* Step 2 */}
            <div style={{ background: k.bg, border: `1px solid ${currentLtp >= entryPrice + beTrigger && currentLtp < entryPrice + tslOffset + 15 ? k.green : k.border}`, borderRadius: 4, padding: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 650, color: k.green }}>PHASE 2: BREAK-EVEN RATCHET</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: k.text, marginTop: 2 }}>LTP crosses +{beTrigger} pts (₹{(entryPrice + beTrigger).toFixed(2)})</div>
              <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4, marginTop: 4 }}>
                TSL automatically jumps to <b>₹{entryPrice}</b>. Trade is now <b>100% Risk-Free</b> (Capital is fully preserved).
              </div>
            </div>

            {/* Step 3 */}
            <div style={{ background: k.bg, border: `1px solid ${currentLtp >= entryPrice + tslOffset + 15 && currentLtp < exitTarget ? k.orange : k.border}`, borderRadius: 4, padding: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 650, color: k.orange }}>PHASE 3: PROFIT TRAILING</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: k.text, marginTop: 2 }}>LTP climbs further (e.g. ₹{(entryPrice + 50).toFixed(2)})</div>
              <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4, marginTop: 4 }}>
                TSL ratchets up continuously behind price (LTP - {tslOffset} pts). Automatically locks in guaranteed profit on any pullback.
              </div>
            </div>

            {/* Step 4 */}
            <div style={{ background: k.bg, border: `1px solid ${currentLtp >= exitTarget ? k.purple : k.border}`, borderRadius: 4, padding: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 650, color: k.purple }}>PHASE 4: EXIT / TARGET</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: k.text, marginTop: 2 }}>Target @ ₹{exitTarget} or TSL Trigger</div>
              <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4, marginTop: 4 }}>
                Clean 100% automated rule-based exit when target is reached or when price reverses into the ratcheted TSL.
              </div>
            </div>
          </div>
        </div>

        {/* Pictorial Execution Bounds Visualizer */}
        <div style={{ background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4, padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, flexWrap: 'wrap', gap: 6 }}>
            <span style={{ fontSize: 10.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Real-Time Premium Trajectory & Bounds Visualizer
            </span>
            <div style={{ display: 'flex', gap: 10, fontSize: 10, color: k.dim, flexWrap: 'wrap' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 2, background: k.blue }} /> Entry: ₹{entryPrice}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 2, background: k.red }} /> Hard SL: ₹{initialSl}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 2, background: k.orange }} /> Ratcheted Trail (TSL): ₹{dynamicTsl}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 2, background: k.purple }} /> Target: ₹{exitTarget}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 2, background: ptsDiff >= 0 ? k.green : k.red }} /> Live LTP: ₹{currentLtp}
              </span>
            </div>
          </div>

          {/* SVG Price Trajectory Infographic */}
          <div style={{ width: '100%', height: 160, background: 'var(--k-bg)', border: `1px solid ${k.border}`, borderRadius: 3, position: 'relative', overflow: 'hidden' }}>
            <svg width="100%" height="100%" viewBox="0 0 500 160" preserveAspectRatio="none" style={{ display: 'block' }}>
              {/* Background Value Area Grid */}
              <line x1="0" y1="30" x2="500" y2="30" stroke="var(--k-surface-hover)" strokeDasharray="3 3" />
              <line x1="0" y1="65" x2="500" y2="65" stroke="var(--k-surface-hover)" strokeDasharray="3 3" />
              <line x1="0" y1="100" x2="500" y2="100" stroke="var(--k-surface-hover)" strokeDasharray="3 3" />
              <line x1="0" y1="135" x2="500" y2="135" stroke="var(--k-surface-hover)" strokeDasharray="3 3" />

              {/* Target line */}
              <line x1="0" y1="25" x2="500" y2="25" stroke={k.purple} strokeWidth="1.5" strokeDasharray="3 3" />
              <text x="8" y="21" fill={k.purple} fontSize="9" fontWeight="600">Target ₹{exitTarget} (+₹{maxTargetAmount.toLocaleString('en-IN')})</text>

              {/* Hard SL line */}
              <line x1="0" y1="140" x2="500" y2="140" stroke={k.red} strokeWidth="1.5" strokeDasharray="4 4" />
              <text x="8" y="136" fill={k.red} fontSize="9" fontWeight="600">Hard SL ₹{initialSl} (-₹{maxRiskAmount.toLocaleString('en-IN')})</text>

              {/* Entry line */}
              <line x1="0" y1="90" x2="500" y2="90" stroke={k.blue} strokeWidth="1.5" />
              <text x="8" y="86" fill={k.blue} fontSize="9" fontWeight="600">Entry ₹{entryPrice}</text>

              {/* Ratcheting TSL line */}
              {(() => {
                // Map TSL to y-coord (620=25, 380=140)
                const tslY = Math.max(30, Math.min(140, 140 - ((dynamicTsl - initialSl) / (exitTarget - initialSl)) * 115));
                return (
                  <>
                    <line x1="180" y1={tslY} x2="500" y2={tslY} stroke={k.orange} strokeWidth="2" strokeDasharray="3 3" />
                    <text x="190" y={tslY - 4} fill={k.orange} fontSize="9.5" fontWeight="650">
                      Ratcheted TSL ₹{dynamicTsl} ({tslPnl >= 0 ? `+₹${tslPnl.toLocaleString('en-IN')}` : `-₹${Math.abs(tslPnl).toLocaleString('en-IN')}`})
                    </text>
                  </>
                );
              })()}

              {/* Price trajectory curve */}
              {(() => {
                const targetY = Math.max(15, Math.min(145, 90 - ((currentLtp - entryPrice) / (exitTarget - entryPrice)) * 65));
                const strokeColor = ptsDiff >= 0 ? k.green : k.red;
                return (
                  <>
                    <path
                      d={`M 0 100 Q 120 95, 240 90 T 380 ${(90 + targetY) / 2} T 475 ${targetY}`}
                      fill="none"
                      stroke={strokeColor}
                      strokeWidth="2.5"
                    />
                    <circle cx="475" cy={targetY} r="5.5" fill={strokeColor} />
                    <text x="410" y={Math.max(16, targetY - 8)} fill={strokeColor} fontSize="10" fontWeight="700">
                      LTP ₹{currentLtp} ({netPnlUsd >= 0 ? '+' : ''}₹{netPnlUsd.toLocaleString('en-IN')})
                    </text>
                  </>
                );
              })()}
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
}
