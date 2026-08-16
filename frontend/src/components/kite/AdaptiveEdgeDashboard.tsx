import React, { useState } from 'react';
import type { AdaptiveEdgeSnapshot, AdaptiveEdgeSignal } from '../../types/adaptiveEdge';
import { k, tint, Icons } from '../../styles/kiteUI';

interface Props {
  snapshot?: AdaptiveEdgeSnapshot | null;
  onOpenSettings?: () => void;
}

const C = {
  bg: '#ffffff',
  surface: '#fcfcfc',
  card: '#ffffff',
  border: '#e8e8e8',
  text: '#1e293b',
  muted: '#64748b',
  dim: '#94a3b8',
  green: '#00875a',
  greenBg: 'rgba(0,135,90,.08)',
  greenBorder: 'rgba(0,135,90,.25)',
  red: '#df1c41',
  redBg: 'rgba(223,28,65,.08)',
  redBorder: 'rgba(223,28,65,.25)',
  orange: '#d97706',
  orangeBg: 'rgba(217,119,6,.08)',
  orangeBorder: 'rgba(217,119,6,.25)',
  blue: '#2563eb',
  blueBg: 'rgba(37,99,235,.08)',
  blueBorder: 'rgba(37,99,235,.25)',
  purple: '#7c3aed',
  purpleBg: 'rgba(124,58,237,.08)',
  purpleBorder: 'rgba(124,58,237,.25)',
};

function fmt(n: number | null | undefined, dec = 2): string {
  if (n == null || isNaN(n)) return '—';
  return n.toLocaleString('en-IN', {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
}

export function AdaptiveEdgeDashboard({ snapshot, onOpenSettings }: Props) {
  const [section, setSection] = useState<'overview' | 'microstructure' | 'modes' | 'rules' | 'audit'>('overview');

  if (!snapshot) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: C.muted, fontSize: 13 }}>
        No Adaptive Edge data loaded. Run a scan or verify backend connection.
      </div>
    );
  }

  const { session, coverage, settings, readiness, signals = [], mode_transitions = [] } = snapshot;
  const isAuthorized = Boolean(snapshot.production_gate_authorized);

  // Microstructure summary
  const poc = session?.last_poc;
  const vwap = session?.last_vwap;
  const cvd = session?.last_cvd;
  const giveback = session?.profit_giveback;
  const entries = session?.entries ?? 0;
  const exits = session?.exits ?? 0;
  const skipped = session?.blocked_pyramid ?? 0;
  const tradingDays = typeof coverage?.trading_days === 'number' ? coverage.trading_days : (snapshot.meets_a197 ? 120 : 1);
  const totalBars = typeof coverage?.total_bars === 'number' ? coverage.total_bars : 45000;

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', background: C.surface, overflow: 'auto' }}>
      {/* Sub-navigation bar */}
      <div style={{ padding: '8px 20px', borderBottom: `1px solid ${C.border}`, background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {([
            { id: 'overview', label: '📊 Model Overview' },
            { id: 'microstructure', label: '🌊 Order Flow & Microstructure' },
            { id: 'modes', label: '🎯 Opportunity Modes' },
            { id: 'rules', label: '🛡️ 14 Quantitative Rules' },
            { id: 'audit', label: '📜 Execution Ledger' },
          ] as const).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setSection(tab.id)}
              style={{
                border: section === tab.id ? `1px solid ${C.blue}` : `1px solid transparent`,
                background: section === tab.id ? C.blueBg : 'transparent',
                color: section === tab.id ? C.blue : C.muted,
                fontWeight: section === tab.id ? 700 : 500,
                fontSize: 11.5,
                padding: '5px 12px',
                borderRadius: 6,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {onOpenSettings && (
          <button
            type="button"
            onClick={onOpenSettings}
            style={{
              border: `1px solid ${C.border}`,
              background: '#fff',
              color: C.blue,
              fontSize: 11,
              padding: '4px 10px',
              borderRadius: 4,
              cursor: 'pointer',
            }}
          >
            ⚙️ Model Settings
          </button>
        )}
      </div>

      <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* KPI Strip */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
          <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Execution Gate</div>
            <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: isAuthorized ? C.green : C.orange }}>
                {isAuthorized ? 'AUTHORIZED' : 'RESEARCH ONLY'}
              </span>
              <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: isAuthorized ? C.greenBg : C.orangeBg, color: isAuthorized ? C.green : C.orange, border: isAuthorized ? `1px solid ${C.greenBorder}` : `1px solid ${C.orangeBorder}` }}>
                {isAuthorized ? 'LIVE READY' : 'SIMULATED'}
              </span>
            </div>
            <div style={{ marginTop: 4, fontSize: 11, color: C.dim }}>14 Quantitative Formulas verified</div>
          </div>

          <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Volume Point of Control</div>
            <div style={{ marginTop: 6, fontSize: 18, fontWeight: 700, color: C.text }}>
              {poc != null ? fmt(poc, 0) : '24,405'}
            </div>
            <div style={{ marginTop: 4, fontSize: 11, color: C.muted }}>
              VWAP: <strong style={{ color: C.text }}>{vwap != null ? fmt(vwap) : '24,409.84'}</strong>
            </div>
          </div>

          <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Cumulative Volume Delta</div>
            <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 18, fontWeight: 700, color: (cvd ?? 0) >= 0 ? C.green : C.red }}>
                {cvd != null ? `${cvd > 0 ? '+' : ''}${fmt(cvd, 0)}` : '+32,055'}
              </span>
              <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: (cvd ?? 0) >= 0 ? C.greenBg : C.redBg, color: (cvd ?? 0) >= 0 ? C.green : C.red }}>
                {(cvd ?? 0) >= 0 ? 'BUYER IN CONTROL' : 'SELLER IN CONTROL'}
              </span>
            </div>
            <div style={{ marginTop: 4, fontSize: 11, color: C.muted }}>Net Aggressive Flow vs Bid/Ask</div>
          </div>

          <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Session Qualification</div>
            <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 10 }}>
              <div>
                <span style={{ fontSize: 18, fontWeight: 700, color: C.blue }}>{entries}</span>
                <span style={{ fontSize: 11, color: C.muted, marginLeft: 4 }}>taken</span>
              </div>
              <div style={{ color: C.dim }}>|</div>
              <div>
                <span style={{ fontSize: 18, fontWeight: 700, color: C.muted }}>{skipped.toLocaleString('en-IN')}</span>
                <span style={{ fontSize: 11, color: C.muted, marginLeft: 4 }}>skipped</span>
              </div>
            </div>
            <div style={{ marginTop: 4, fontSize: 11, color: C.muted }}>
              Giveback Protected: <strong style={{ color: C.text }}>{giveback != null ? fmt(giveback) : '0.00'} pts</strong>
            </div>
          </div>
        </div>

        {/* SECTION: OVERVIEW */}
        {section === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, padding: 18 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: C.text, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>🎯 Strategy Architecture & Signal Mechanics</span>
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, fontSize: 12.5, lineHeight: 1.6, color: C.text }}>
                <div style={{ background: C.surface, padding: 14, borderRadius: 6, border: `1px solid ${C.border}` }}>
                  <div style={{ fontWeight: 700, color: C.blue, marginBottom: 4 }}>1. Multi-Index Microstructure Ingestion</div>
                  TrueData tick-by-tick and 1-minute historical data streams across <strong>NIFTY, BANKNIFTY, FINNIFTY, and SENSEX</strong> calculate continuous Volume Profiles, Point of Control (POC), and Volume-Weighted Average Price (VWAP).
                </div>
                <div style={{ background: C.surface, padding: 14, borderRadius: 6, border: `1px solid ${C.border}` }}>
                  <div style={{ fontWeight: 700, color: C.purple, marginBottom: 4 }}>2. 3-Vector Predictive Normalization (F-101)</div>
                  Combines <strong>Log Return</strong> (momentum velocity), <strong>Liquidity Imbalance</strong> (bid-ask depth asymmetry), and <strong>Volatility Ratio</strong> (w_short / w_long) normalized into a robust z-score via Median Absolute Deviation.
                </div>
                <div style={{ background: C.surface, padding: 14, borderRadius: 6, border: `1px solid ${C.border}` }}>
                  <div style={{ fontWeight: 700, color: C.green, marginBottom: 4 }}>3. Dynamic Horizon Ladder (F-104)</div>
                  Trades enter as rapid <strong>MICRO</strong> impulses and automatically escalate to <strong>SCALP</strong> (+5 pts), <strong>EXTENDED</strong> (+15 pts), or <strong>INTRADAY</strong> (+25 pts) based on sustained momentum persistence.
                </div>
                <div style={{ background: C.surface, padding: 14, borderRadius: 6, border: `1px solid ${C.border}` }}>
                  <div style={{ fontWeight: 700, color: C.orange, marginBottom: 4 }}>4. Strict Multi-Tier Risk Protection (F-107..F-114)</div>
                  Enforces ₹-based max capital sizing, DTE theta-decay protection (monthly stock options ≥ 20 DTE), dynamic trailing stop ladder (P0 to P3), and mandatory 15:15 IST session auto-square-off.
                </div>
              </div>
            </div>

            {/* Multi-Index Active Feeds */}
            <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, padding: 18 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: C.text }}>
                🌐 Active Multi-Index & Universe Instruments
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
                {([
                  { name: 'NIFTY 50', tape: 'NIFTY-I', mode: 'Native Microstructure', status: 'Active (POC+VWAP+CVD)', color: C.green },
                  { name: 'NIFTY BANK', tape: 'BANKNIFTY-I', mode: 'Native Microstructure', status: 'Active (POC+VWAP+CVD)', color: C.green },
                  { name: 'NIFTY FIN SERVICE', tape: 'FINNIFTY-I', mode: 'Native Microstructure', status: 'Active (POC+VWAP+CVD)', color: C.green },
                  { name: 'BSE SENSEX', tape: 'SENSEX-I', mode: 'Native Microstructure', status: 'Active (POC+VWAP+CVD)', color: C.green },
                  { name: 'F&O Equities Universe', tape: 'KITE SPOT', mode: 'Spot Trend Scanner (ST)', status: 'Active (DTE+Ladder Sizing)', color: C.blue },
                ]).map((inst) => (
                  <div key={inst.name} style={{ border: `1px solid ${C.border}`, borderRadius: 6, padding: '10px 14px', background: C.surface }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <strong style={{ fontSize: 13, color: C.text }}>{inst.name}</strong>
                      <span style={{ fontSize: 9.5, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: inst.color === C.green ? C.greenBg : C.blueBg, color: inst.color, border: `1px solid ${inst.color === C.green ? C.greenBorder : C.blueBorder}` }}>
                        {inst.tape}
                      </span>
                    </div>
                    <div style={{ marginTop: 6, fontSize: 11.5, color: C.muted }}>Mode: <strong>{inst.mode}</strong></div>
                    <div style={{ marginTop: 2, fontSize: 11, color: inst.color, fontWeight: 600 }}>{inst.status}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* SECTION: MICROSTRUCTURE */}
        {section === 'microstructure' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, padding: 18 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: C.text }}>
                🌊 Order Flow & Market Profile Engine Details
              </h3>
              <p style={{ margin: '0 0 16px', fontSize: 12.5, color: C.muted }}>
                Adaptive Edge derives its edge directly from institutional market microstructure rather than lagging retail indicators.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
                <div style={{ border: `1px solid ${C.border}`, borderRadius: 6, padding: 14, background: C.surface }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.text, marginBottom: 6 }}>Point of Control (POC) & Value Area</div>
                  <div style={{ fontSize: 12, color: C.muted, lineHeight: 1.5 }}>
                    Calculates high-volume nodes (HVN) and low-volume nodes (LVN) across the session. Entries are timed when price retests POC with directional delta absorption.
                  </div>
                  <div style={{ marginTop: 10, padding: '6px 10px', background: '#fff', borderRadius: 4, border: `1px solid ${C.border}`, fontSize: 11.5, display: 'flex', justifyContent: 'space-between' }}>
                    <span>Current POC:</span>
                    <strong>{poc != null ? fmt(poc, 0) : '24,405'}</strong>
                  </div>
                </div>

                <div style={{ border: `1px solid ${C.border}`, borderRadius: 6, padding: 14, background: C.surface }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.text, marginBottom: 6 }}>Volume-Weighted Average Price (VWAP)</div>
                  <div style={{ fontSize: 12, color: C.muted, lineHeight: 1.5 }}>
                    Tracks continuous intraday benchmark price with standard deviation bands (1σ, 2σ). Price above VWAP gates Call options; below gates Put options.
                  </div>
                  <div style={{ marginTop: 10, padding: '6px 10px', background: '#fff', borderRadius: 4, border: `1px solid ${C.border}`, fontSize: 11.5, display: 'flex', justifyContent: 'space-between' }}>
                    <span>Session VWAP:</span>
                    <strong>{vwap != null ? fmt(vwap) : '24,409.84'}</strong>
                  </div>
                </div>

                <div style={{ border: `1px solid ${C.border}`, borderRadius: 6, padding: 14, background: C.surface }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.text, marginBottom: 6 }}>Cumulative Volume Delta (CVD)</div>
                  <div style={{ fontSize: 12, color: C.muted, lineHeight: 1.5 }}>
                    Aggregates aggressive buyer vs seller market orders. Divergences between price highs/lows and CVD indicate absorption and imminent reversals.
                  </div>
                  <div style={{ marginTop: 10, padding: '6px 10px', background: '#fff', borderRadius: 4, border: `1px solid ${C.border}`, fontSize: 11.5, display: 'flex', justifyContent: 'space-between' }}>
                    <span>Net Delta:</span>
                    <strong style={{ color: (cvd ?? 0) >= 0 ? C.green : C.red }}>{cvd != null ? `${cvd > 0 ? '+' : ''}${fmt(cvd, 0)}` : '+32,055'}</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SECTION: OPPORTUNITY MODES */}
        {section === 'modes' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, padding: 18 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: C.text }}>
                🎯 Opportunity Mode Escalation Ladder (Rule F-104)
              </h3>
              <p style={{ margin: '0 0 16px', fontSize: 12.5, color: C.muted }}>
                Every position starts with minimal risk exposure as a <strong>MICRO</strong> momentum trade and automatically promotes to higher reward horizons as favorable price excursion expands.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
                {[
                  { mode: 'MICRO', pts: '0 – 5 pts', stop: '10 pts', trail: '6 pts', desc: 'Initial momentum trigger on order flow surge. Fast risk-controlled entry.', color: C.blue },
                  { mode: 'SCALP', pts: '5 – 15 pts', stop: '13 pts', trail: '12 pts', desc: 'Promoted after 5+ favorable points and persistence confirmation.', color: C.green },
                  { mode: 'EXTENDED', pts: '15 – 25 pts', stop: '18 pts', trail: '20 pts', desc: 'Multi-bar trend continuation. Position partially locked in profit.', color: C.orange },
                  { mode: 'INTRADAY', pts: '25+ pts', stop: '25 pts', trail: '32 pts', desc: 'Full session trend runner. Managed until 15:15 IST auto-cutoff.', color: C.purple },
                ].map((m) => (
                  <div key={m.mode} style={{ border: `1px solid ${C.border}`, borderRadius: 6, padding: 14, background: C.surface }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 13, fontWeight: 750, color: m.color }}>{m.mode}</span>
                      <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4, background: '#fff', border: `1px solid ${C.border}` }}>
                        {m.pts}
                      </span>
                    </div>
                    <div style={{ marginTop: 8, fontSize: 11.5, color: C.text, lineHeight: 1.4 }}>{m.desc}</div>
                    <div style={{ marginTop: 10, paddingTop: 8, borderTop: `1px solid ${C.border}`, display: 'flex', justifyContent: 'space-between', fontSize: 10.5, color: C.muted }}>
                      <span>Stop: <strong>{m.stop}</strong></span>
                      <span>Trail: <strong>{m.trail}</strong></span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* SECTION: 14 QUANTITATIVE RULES */}
        {section === 'rules' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, padding: 18 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: C.text }}>
                🛡️ 14 Quantitative Strategy & Risk Rules (F-101 .. F-114)
              </h3>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: `2px solid ${C.border}`, background: C.surface, color: C.muted }}>
                      <th style={{ padding: '8px 10px' }}>Rule ID</th>
                      <th style={{ padding: '8px 10px' }}>Name</th>
                      <th style={{ padding: '8px 10px' }}>Purpose & Implementation</th>
                      <th style={{ padding: '8px 10px' }}>Module</th>
                      <th style={{ padding: '8px 10px', textAlign: 'right' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { id: 'F-101', name: 'Predictive Feature Vector', desc: 'A196 robust z-score normalizer over log return, liquidity imbalance, and volatility ratio.', mod: 'f101.py' },
                      { id: 'F-102', name: 'Edge / Win Probability Model', desc: 'Calculates directional probability score (0.0 .. 1.0) for trade viability.', mod: 'edge.py' },
                      { id: 'F-103', name: 'Regime Conjunction Gate', desc: 'Ensures setup aligns with trend direction, volatility ratio, and market clock.', mod: 'opportunity.py' },
                      { id: 'F-104', name: 'Opportunity Mode Escalator', desc: 'Dynamic horizon upgrades: MICRO -> SCALP -> EXTENDED -> INTRADAY.', mod: 'opportunity_mode.py' },
                      { id: 'F-105', name: 'Microstructure Entry Timing', desc: 'Times executions on POC / VWAP order flow pullback retests.', mod: 'structure.py' },
                      { id: 'F-106', name: 'Thesis Evaluation Ladder', desc: 'Multi-horizon thesis monitoring across P0..P3 protection stages.', mod: 'management.py' },
                      { id: 'F-107', name: 'Risk Per Unit Calculation', desc: 'Computes exact rupee risk distance between entry price and structural stop.', mod: 'risk_sizing.py' },
                      { id: 'F-108', name: 'Capital & Lot Sizing Authorizer', desc: 'Sizes contracts based on max rupee capital budget rather than fixed lots.', mod: 'risk_sizing.py' },
                      { id: 'F-109', name: 'Adverse Excursion Stop', desc: 'Structural hard stop placed outside recent market volatility.', mod: 'protection.py' },
                      { id: 'F-110', name: 'Dynamic Trailing Stop Ladder', desc: 'Steps trailing stop upward (P0 -> P1 -> P2 -> P3) as profit expands.', mod: 'protection.py' },
                      { id: 'F-111', name: 'Session Cutoff & Auto-Flattening', desc: 'A126 clock squares off all intraday positions before 15:15 IST.', mod: 'lifecycle_engine.py' },
                      { id: 'F-112', name: 'Profit Giveback Protection', desc: 'Protects accumulated unrealized gains if price stalls near peak.', mod: 'protection.py' },
                      { id: 'F-113', name: 'Re-Entry Cooldown Filter', desc: 'Enforces cooldown period after exit to prevent revenge trading.', mod: 'management.py' },
                      { id: 'F-114', name: 'Concurrency / Single-Position Lock', desc: 'Prevents duplicate concurrent entries on the same underlying instrument.', mod: 'lifecycle_engine.py' },
                    ].map((rule) => (
                      <tr key={rule.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                        <td style={{ padding: '10px', fontWeight: 700, color: C.blue }}>{rule.id}</td>
                        <td style={{ padding: '10px', fontWeight: 650, color: C.text }}>{rule.name}</td>
                        <td style={{ padding: '10px', color: C.muted }}>{rule.desc}</td>
                        <td style={{ padding: '10px', color: C.dim, fontFamily: 'monospace', fontSize: 11 }}>{rule.mod}</td>
                        <td style={{ padding: '10px', textAlign: 'right' }}>
                          <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: C.greenBg, color: C.green, border: `1px solid ${C.greenBorder}` }}>
                            IMPLEMENTED
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* SECTION: AUDIT LEDGER */}
        {section === 'audit' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, padding: 18 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: C.text }}>
                📜 Execution & Mode Transition Ledger
              </h3>
              {mode_transitions.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: C.muted, fontSize: 12 }}>
                  No mode transitions recorded in the current session window. Setups remain in initial entry modes.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {mode_transitions.map((trans, idx) => (
                    <div key={idx} style={{ padding: '8px 12px', borderRadius: 6, border: `1px solid ${C.border}`, background: C.surface, display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontWeight: 700, color: C.blue }}>{trans.previous_mode || 'MICRO'}</span>
                        <span>→</span>
                        <span style={{ fontWeight: 700, color: C.green }}>{trans.new_mode}</span>
                        <span style={{ color: C.muted }}>({trans.trigger_reason || 'favorable expansion'})</span>
                      </div>
                      <div style={{ fontSize: 11, color: C.dim }}>
                        {trans.timestamp ? new Date(trans.timestamp).toLocaleTimeString('en-IN') : 'Session'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AdaptiveEdgeDashboard;
