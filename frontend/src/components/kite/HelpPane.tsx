import React, { useState } from 'react';
import { BORDER, DIM, MUTED, Section, TEXT } from './kiteSettingsPrimitives';
import { k } from '../../styles/kiteUI';
import { AdaptiveEdgeHelpVisualizer } from './AdaptiveEdgeHelpVisualizer';

function SectionHeading({ title, description }: { title: string; description: string }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <h2 style={{ margin: 0, color: 'var(--k-ink-1)', fontSize: 19, fontWeight: 750, letterSpacing: '-.02em' }}>{title}</h2>
      <p style={{ margin: '6px 0 0', color: 'var(--k-ink-5)', fontSize: 12, lineHeight: 1.55, maxWidth: 720 }}>{description}</p>
    </div>
  );
}

function ExampleRow({ label, tone, children }: { label: string; tone: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '9px 0', borderTop: `1px solid ${BORDER}` }}>
      <span style={{ flexShrink: 0, marginTop: 1, fontSize: 10, fontWeight: 800, color: tone, background: `${tone}18`, border: `1px solid ${tone}40`, borderRadius: 4, padding: '2px 7px', whiteSpace: 'nowrap' }}>{label}</span>
      <span style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.5 }}>{children}</span>
    </div>
  );
}

function Scenario({ goal, settings }: { goal: string; settings: string }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 14, padding: '11px 0', borderTop: `1px solid ${BORDER}`, alignItems: 'start' }}>
      <div style={{ color: TEXT, fontSize: 12, fontWeight: 650 }}>&ldquo;{goal}&rdquo;</div>
      <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.5 }}>{settings}</div>
    </div>
  );
}

export function HelpPane() {
  const [activeTab, setActiveTab] = useState<'adaptive_edge' | 'navigator'>('adaptive_edge');

  return (
    <div className="kite-settings-hub" style={{ width: '100%', boxSizing: 'border-box', padding: '28px 30px 48px', background: 'var(--k-surface-sunken-2)', minHeight: '100%', fontFamily: k.fontFamily }}>
      <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
        
        {/* Header with Tab Navigation */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <SectionHeading
            title="Help — Signals and the Value-Flow Navigator"
            description="Comprehensive visual guides, end-to-end interactive tutorials, and technical reference for the Adaptive Edge Microstructure engine, options execution, and the Value-Flow Navigator."
          />

          <div style={{ display: 'flex', borderBottom: `1px solid ${k.border}`, gap: 16 }}>
            <button
              type="button"
              onClick={() => setActiveTab('adaptive_edge')}
              style={{
                padding: '8px 14px',
                border: 0,
                borderBottom: activeTab === 'adaptive_edge' ? `2px solid ${k.blue}` : '2px solid transparent',
                background: 'transparent',
                color: activeTab === 'adaptive_edge' ? k.text : k.dim,
                fontSize: 12.5,
                fontWeight: activeTab === 'adaptive_edge' ? 700 : 500,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span>🌊</span> Adaptive Edge Microstructure Engine
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('navigator')}
              style={{
                padding: '8px 14px',
                border: 0,
                borderBottom: activeTab === 'navigator' ? `2px solid ${k.blue}` : '2px solid transparent',
                background: 'transparent',
                color: activeTab === 'navigator' ? k.text : k.dim,
                fontSize: 12.5,
                fontWeight: activeTab === 'navigator' ? 700 : 500,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span>🧭</span> Signals & Value-Flow Navigator
            </button>
          </div>
        </div>

        {/* Tab 1: Adaptive Edge Visualizer */}
        {activeTab === 'adaptive_edge' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <AdaptiveEdgeHelpVisualizer />
          </div>
        )}

        {/* Tab 2: Navigator & Signals Guide (Also rendered in DOM for testing & complete reference) */}
        <div style={{ display: activeTab === 'navigator' ? 'block' : 'none' }}>
          <section style={{ background: 'var(--k-bg)', border: `1px solid ${BORDER}`, borderRadius: 9, overflow: 'hidden', marginBottom: 16, boxShadow: '0 1px 2px rgba(0,0,0,.025)' }}>
            <Section
              title="What the Value-Flow Navigator is"
              description="One paragraph, plain English."
              summary="Start here"
              defaultOpen
            >
              <p style={{ color: MUTED, fontSize: 12, lineHeight: 1.6, margin: '2px 0 0' }}>
                You have two signal engines, and they are peers. The Sterling Kite Engine fires the
                triple-SuperTrend signal. The Value-Flow Navigator reads anchored VWAP structure, projected
                daily/weekly ranges, the volatility regime, and — when you scan options — option flow and
                gamma activity, then fuses all of it into one status: <b>NO_DATA</b>, <b>WAIT</b>,
                <b> CONFLICT</b>, <b>WATCH</b>, <b>CONFIRMED</b>, or <b>HIGH_CONVICTION</b>.
              </p>
              <p style={{ color: MUTED, fontSize: 12, lineHeight: 1.6, margin: '10px 0 0' }}>
                Navigator has its own scan loop, so it keeps working even with the SuperTrend engine switched
                off entirely. It can follow SuperTrend&apos;s instrument list or run on its own universe and its own
                signal source — your choice, under Connect → Value-Flow Navigator → What Navigator scans.
                What it does with what it finds is a separate, stricter choice: by default it only comments on
                setups SuperTrend already triggered, and it puts its own rows on the board only once you turn
                on Signal Origination (below). Navigator is off by default; nothing here changes any existing
                behaviour until you explicitly turn something on.
              </p>
            </Section>

            <Section
              title="The 4 signal lenses"
              description="A LOCAL view filter only — it never changes what's scanned or what can be traded, just which rows you're looking at right now."
              summary="SuperTrend · Navigator · Combined · Common"
            >
              <ExampleRow label="SuperTrend" tone={k.blue}>
                Every triple-SuperTrend setup, Navigator badge hidden even if it has an opinion. Example: NIFTY BANK
                shows a live long setup with SL 51,200 — no Navigator badge, exactly like Navigator doesn't exist.
              </ExampleRow>
              <ExampleRow label="Navigator" tone={k.purple}>
                Rows Navigator owns or has evidence for, viewed through its own status. Example: a NIFTY 50 row
                appears here once Navigator has assessed it — shown as &ldquo;Nav CONFIRMED 82&rdquo; — alongside any
                setup Navigator found by itself. This is the lens to use when SuperTrend is switched off.
              </ExampleRow>
              <ExampleRow label="Combined" tone={k.orange}>
                The default. Every SuperTrend setup, with Navigator's badge alongside when it has one. Example: SENSEX
                shows its normal SuperTrend row, plus a small &ldquo;Nav WATCH&rdquo; tag if Navigator has an opinion.
              </ExampleRow>
              <ExampleRow label="Common" tone={k.green}>
                Only rows where BOTH agree: SuperTrend is live AND Navigator is Confirmed or High Conviction. Example:
                a NIFTY FIN SERVICE setup only shows here once both sides confirm it independently.
              </ExampleRow>
            </Section>

            <Section
              title="The 3 new Navigator settings"
              description="Connect → Value-Flow Navigator → Structure Radar and Signal Origination. All default off — nothing changes until you opt in."
              summary="Structure Radar · Signal Origination · Auto-Execute"
            >
              <ExampleRow label="Structure Radar" tone={k.blue}>
                Off by default. When on, Navigator continuously reads AVWAP + volatility for every underlying you've
                configured — even ones SuperTrend is completely quiet on right now. It never adds a row to your
                signal table by itself; it only keeps the Navigator snapshot/status views populated instead of
                saying &ldquo;no evidence yet&rdquo;.
              </ExampleRow>
              <ExampleRow label="Signal Origination" tone={k.purple}>
                Off by default. <b>Heads-up</b>: Navigator can surface its own setup — no SuperTrend trigger at all
                — as a &ldquo;Navigator idea&rdquo; row, visible everywhere, never executable. <b>Full</b>: the same
                detection, but a real strike gets resolved and the row becomes tradeable like any other row (manual
                execute works; auto-exec is a further, separate choice — see below).
              </ExampleRow>
              <ExampleRow label="Auto-Execute Originated" tone={k.red}>
                Off by default, and only matters once Signal Origination is Full. Lets a Navigator-originated row
                fire through the exact same auto-exec path every other row uses. Safety: this stays locked — exactly
                like Gate mode above it — until you promote a calibration report under Connect → Navigator
                Calibration, which needs at least 20 recorded trading sessions of Navigator's own forward
                accuracy and cannot be shortcut. Turning this on before then changes nothing; the order path
                still refuses. Promotion alone doesn't switch it on either — that stays your explicit choice.
              </ExampleRow>
            </Section>

            <Section
              title="Quick-pick: I want to…"
              description="Match your goal to the settings that get you there."
              summary="Scenario guide"
            >
              <Scenario goal="Ignore Navigator entirely" settings="Signal lens = SuperTrend. (Navigator can stay off, or stay on — the lens hides it either way.)" />
              <Scenario goal="See Navigator's take on my existing trades" settings="Signal lens = Combined or Navigator. Structure Radar and Signal Origination stay off." />
              <Scenario goal="See structure on my indices even when SuperTrend is quiet" settings="Structure Radar = on. Check Connect → Value-Flow Navigator's snapshot/status for a given underlying." />
              <Scenario goal="Let Navigator surface brand-new setups I take manually" settings="Signal Origination = Heads-up (browse only) or Full (tradeable, manual execute)." />
              <Scenario goal="Run Navigator instead of SuperTrend" settings="Turn the Kite engine off, keep Navigator on, Signal Origination = Heads-up or Full, Signal lens = Navigator. Navigator's own scan loop keeps running." />
              <Scenario goal="Scan different instruments than SuperTrend" settings="Connect → Value-Flow Navigator → What Navigator scans = its own universe. Connect → SuperTrend engine → Instruments then drives SuperTrend only." />
              <Scenario goal="Let it trade on its own" settings="Signal Origination = Full, Auto-Execute Originated = on, Kite engine's own Auto-Execute = on. Still blocked until you promote a calibration report." />
            </Section>
          </section>

          <p style={{ color: DIM, fontSize: 10.5, lineHeight: 1.6, maxWidth: 720 }}>
            Full design details: see <code>docs/superpowers/specs/2026-07-28-navigator-structure-radar-origination-design.md</code> in the repo.
          </p>
        </div>
      </div>
    </div>
  );
}

export default HelpPane;
