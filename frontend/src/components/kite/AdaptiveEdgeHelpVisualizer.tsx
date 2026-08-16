import React, { useState } from 'react';
import { k, tint } from '../../styles/kiteUI';

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
  
  // Interactive Simulation Sandbox State
  const [simSpot, setSimSpot] = useState<number>(24465);
  const baseSpot = 24465;
  const spotDiff = simSpot - baseSpot;

  // Derived simulation metrics
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
  const optionEntry = 504.35;
  const optionLtp = Math.max(280, Number((optionEntry + spotDiff * 0.55).toFixed(2)));
  const optionDiff = Number((optionLtp - optionEntry).toFixed(2));
  const optionSl = 380.55;
  // Trailing stop ratchets upward as price advances
  const optionTsl = Number((Math.max(473.48, optionEntry + Math.max(0, spotDiff * 0.45) - 30)).toFixed(2));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, fontFamily: k.fontFamily }}>
      
      {/* ── Top Hero Card: Adaptive Edge Summary ── */}
      <div
        style={{
          background: `linear-gradient(135deg, ${tint(k.blue, 6)} 0%, ${tint(k.purple, 6)} 100%)`,
          border: `1px solid ${k.border}`,
          borderRadius: 6,
          padding: '18px 22px',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 18 }}>🌊</span>
            <span style={{ fontSize: 15, fontWeight: 700, color: k.text, letterSpacing: '-0.01em' }}>
              Adaptive Edge — Hybrid Microstructure & Scalp Engine
            </span>
          </div>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: 3,
              background: `${k.blue}18`,
              color: k.blue,
              border: `1px solid ${k.blue}40`,
              letterSpacing: '0.04em',
            }}
          >
            END-TO-END WORKFLOW
          </span>
        </div>
        <p style={{ fontSize: 12, color: k.text, lineHeight: 1.6, margin: 0, opacity: 0.9 }}>
          Unlike standard indicators that only look at lagging bar closes, <b>Adaptive Edge</b> reads the live <b>order flow tape</b>, 
          <b> volume footprint imbalances</b>, and <b>anchored VWAP / POC structures</b>. It automatically translates spot momentum 
          into high-conviction options execution with real-time dynamic trailing stops and multi-stage mode escalation.
        </p>
      </div>

      {/* ── Pictorial Architecture Pipeline Ribbon ── */}
      <div>
        <div style={{ fontSize: 11, fontWeight: 650, color: k.dim, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 10 }}>
          ⚡ End-to-End Architectural Pipeline (Click stage to inspect)
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
        <div style={{ fontSize: 11, fontWeight: 700, color: k.text, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          📊 Dynamic Scalp Escalation & Risk Matrix
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
          {/* Mode 1: MICRO */}
          <div style={{ background: `${k.blue}0a`, border: `1px solid ${k.blue}30`, borderRadius: 4, padding: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, fontWeight: 750, color: k.blue }}>1. MICRO</span>
              <span style={{ fontSize: 9.5, fontWeight: 700, background: `${k.blue}18`, color: k.blue, padding: '1px 5px', borderRadius: 2 }}>1.0R</span>
            </div>
            <div style={{ fontSize: 11, color: k.text, fontWeight: 600 }}>Quick Impulse Scalp</div>
            <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4 }}>
              Entry triggered on initial tape CVD impulse. Hard initial stop with quick 1R profit objective.
            </div>
          </div>

          {/* Mode 2: SCALP */}
          <div style={{ background: `${k.green}0a`, border: `1px solid ${k.green}30`, borderRadius: 4, padding: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, fontWeight: 750, color: k.green }}>2. SCALP (↗)</span>
              <span style={{ fontSize: 9.5, fontWeight: 700, background: `${k.green}18`, color: k.green, padding: '1px 5px', borderRadius: 2 }}>&gt;1.5R</span>
            </div>
            <div style={{ fontSize: 11, color: k.text, fontWeight: 600 }}>Momentum Expansion</div>
            <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4 }}>
              Dynamic upgrade when volume delta exceeds baseline without liquidity absorption resistance.
            </div>
          </div>

          {/* Mode 3: EXTENDED */}
          <div style={{ background: `${k.purple}0a`, border: `1px solid ${k.purple}30`, borderRadius: 4, padding: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, fontWeight: 750, color: k.purple }}>3. EXTENDED (↗)</span>
              <span style={{ fontSize: 9.5, fontWeight: 700, background: `${k.purple}18`, color: k.purple, padding: '1px 5px', borderRadius: 2 }}>&gt;2.5R</span>
            </div>
            <div style={{ fontSize: 11, color: k.text, fontWeight: 600 }}>Trend Continuation</div>
            <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4 }}>
              Value Area breakout sustained by institutional volume flow. Trailing stop ratchets to lock in 1R+.
            </div>
          </div>

          {/* Mode 4: INTRADAY */}
          <div style={{ background: `${k.orange}0a`, border: `1px solid ${k.orange}30`, borderRadius: 4, padding: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, fontWeight: 750, color: k.orange }}>4. INTRADAY (↗)</span>
              <span style={{ fontSize: 9.5, fontWeight: 700, background: `${k.orange}18`, color: k.orange, padding: '1px 5px', borderRadius: 2 }}>&gt;4.0R</span>
            </div>
            <div style={{ fontSize: 11, color: k.text, fontWeight: 600 }}>Full Session Runner</div>
            <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.4 }}>
              Full structural trend day. Trailing stop protects open runner until trend exhausts or TSL hit.
            </div>
          </div>
        </div>

        <div style={{ fontSize: 11, color: k.dim, lineHeight: 1.5, background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4, padding: '8px 12px' }}>
          🛡️ <b>Defensive Decay Guard (↘):</b> When momentum decays or CVD stalls, the badge dynamically reflects decay (e.g. <code>INTRADAY ↘ SCALP ↘ MICRO</code>) and automatically tightens the trailing stop to lock in peak unrealized gains.
        </div>
      </div>

      {/* ── Interactive Live Simulation Sandbox ── */}
      <div
        style={{
          background: k.bg,
          border: `1px solid ${k.border}`,
          borderRadius: 6,
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
          boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: k.blue, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              🎮 Interactive Sandbox Simulation
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: k.text }}>
              Test Live Market Microstructure Reaction (NIFTY 50 @ ₹24,465)
            </div>
          </div>

          {/* Quick Preset Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              type="button"
              onClick={() => setSimSpot(24465)}
              style={{
                padding: '4px 8px',
                fontSize: 10.5,
                fontWeight: 600,
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
                fontWeight: 600,
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
                fontWeight: 600,
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
                fontWeight: 600,
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

        {/* Spot Price Slider Control */}
        <div style={{ background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4, padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
            <span style={{ fontWeight: 650, color: k.text }}>
              Simulated Underlying Spot Price: <span style={{ color: k.blue, fontWeight: 750 }}>₹{simSpot.toLocaleString('en-IN')}</span>
              <span style={{ marginLeft: 6, fontWeight: 600, color: spotDiff >= 0 ? k.green : k.red }}>
                ({spotDiff >= 0 ? '+' : ''}{spotDiff} pts)
              </span>
            </span>
            <span style={{ color: k.dim, fontSize: 10.5 }}>Range: ₹24,400 — ₹24,580</span>
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

        {/* Live Reaction Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
          {/* Microstructure CVD */}
          <div style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 3, padding: '8px 10px' }}>
            <div style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>Order Flow CVD</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: simCvd >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
              {simCvd >= 0 ? '+' : ''}{simCvd.toLocaleString('en-IN')}
            </div>
            <div style={{ fontSize: 9.5, color: k.dim, marginTop: 1 }}>Aggressive Delta</div>
          </div>

          {/* Model Conviction Score */}
          <div style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 3, padding: '8px 10px' }}>
            <div style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>Model Score</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: k.text, fontVariantNumeric: 'tabular-nums' }}>
              {simModelScore.toFixed(2)}
            </div>
            <div style={{ fontSize: 9.5, color: k.green, fontWeight: 600, marginTop: 1 }}>THESIS VALID</div>
          </div>

          {/* Active Mode Escalator */}
          <div style={{ background: `${simModeColor}10`, border: `1px solid ${simModeColor}40`, borderRadius: 3, padding: '8px 10px' }}>
            <div style={{ fontSize: 9.5, fontWeight: 600, color: simModeColor, textTransform: 'uppercase' }}>Active Mode</div>
            <div style={{ fontSize: 13, fontWeight: 750, color: simModeColor }}>
              {simModeBadge}
            </div>
            <div style={{ fontSize: 9.5, color: simModeColor, opacity: 0.8, marginTop: 1 }}>{simMode} Horizon</div>
          </div>

          {/* Option Contract LTP */}
          <div style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 3, padding: '8px 10px' }}>
            <div style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>24500 CE LTP</div>
            <div style={{ fontSize: 13, fontWeight: 750, color: optionDiff >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
              ₹{optionLtp.toFixed(2)}
            </div>
            <div style={{ fontSize: 9.5, fontWeight: 600, color: optionDiff >= 0 ? k.green : k.red, marginTop: 1 }}>
              {optionDiff >= 0 ? '+' : ''}{optionDiff.toFixed(2)} pts
            </div>
          </div>

          {/* Protective Trail Stop (TSL) */}
          <div style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 3, padding: '8px 10px' }}>
            <div style={{ fontSize: 9.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase' }}>Ratcheting Trail (TSL)</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: k.orange, fontVariantNumeric: 'tabular-nums' }}>
              ₹{optionTsl.toFixed(2)}
            </div>
            <div style={{ fontSize: 9.5, color: k.dim, marginTop: 1 }}>Initial SL: ₹{optionSl}</div>
          </div>
        </div>

        {/* Pictorial Execution Bounds Visualizer */}
        <div style={{ background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4, padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: k.text, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              📈 Real-Time Premium Trajectory & Bounds Visualizer
            </span>
            <div style={{ display: 'flex', gap: 10, fontSize: 10, color: k.dim }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 2, background: k.blue }} /> Entry: ₹{optionEntry}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 2, background: k.red }} /> Hard SL: ₹{optionSl}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 2, background: k.orange }} /> Ratcheting Trail (TSL): ₹{optionTsl}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 2, background: k.green }} /> Live LTP: ₹{optionLtp}
              </span>
            </div>
          </div>

          {/* SVG Price Trajectory Infographic */}
          <div style={{ width: '100%', height: 140, background: '#ffffff', border: `1px solid ${k.border}`, borderRadius: 3, position: 'relative', overflow: 'hidden' }}>
            <svg width="100%" height="100%" viewBox="0 0 500 140" preserveAspectRatio="none" style={{ display: 'block' }}>
              {/* Background Value Area Grid */}
              <line x1="0" y1="30" x2="500" y2="30" stroke="#f1f1f1" strokeDasharray="3 3" />
              <line x1="0" y1="70" x2="500" y2="70" stroke="#f1f1f1" strokeDasharray="3 3" />
              <line x1="0" y1="110" x2="500" y2="110" stroke="#f1f1f1" strokeDasharray="3 3" />

              {/* Hard SL line */}
              <line x1="0" y1="120" x2="500" y2="120" stroke={k.red} strokeWidth="1.5" strokeDasharray="4 4" />
              <text x="8" y="116" fill={k.red} fontSize="9" fontWeight="600">SL ₹{optionSl}</text>

              {/* Entry line */}
              <line x1="0" y1="75" x2="500" y2="75" stroke={k.blue} strokeWidth="1.5" />
              <text x="8" y="71" fill={k.blue} fontSize="9" fontWeight="600">Entry ₹{optionEntry}</text>

              {/* Ratcheting TSL line */}
              {(() => {
                // Map TSL to y-coord (500=30, 380=120)
                const tslY = Math.max(35, Math.min(115, 120 - ((optionTsl - 380) / (560 - 380)) * 85));
                return (
                  <>
                    <line x1="200" y1={tslY} x2="500" y2={tslY} stroke={k.orange} strokeWidth="2" strokeDasharray="3 3" />
                    <text x="210" y={tslY - 4} fill={k.orange} fontSize="9" fontWeight="700">Trail (TSL) ₹{optionTsl}</text>
                  </>
                );
              })()}

              {/* Price trajectory curve */}
              {(() => {
                const targetY = Math.max(20, Math.min(130, 75 - ((optionLtp - optionEntry) / 80) * 50));
                return (
                  <>
                    <path
                      d={`M 0 85 Q 120 80, 240 75 T 400 ${(75 + targetY) / 2} T 480 ${targetY}`}
                      fill="none"
                      stroke={optionDiff >= 0 ? k.green : k.red}
                      strokeWidth="2.5"
                    />
                    <circle cx="480" cy={targetY} r="5" fill={optionDiff >= 0 ? k.green : k.red} />
                    <text x="440" y={Math.max(16, targetY - 8)} fill={optionDiff >= 0 ? k.green : k.red} fontSize="10" fontWeight="750">
                      LTP ₹{optionLtp}
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
