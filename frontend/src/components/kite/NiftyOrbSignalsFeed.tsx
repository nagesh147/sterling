import React from 'react';
import { useOrbSignals } from '../../hooks/useOrbSignals';
import { useOrbConfig, useSetOrbEnabled } from '../../hooks/useOrbConfig';
import { useKiteQuote } from '../../hooks/useKite';
import type { OrbFeedEntry } from '../../utils/niftyOrbSignalAdapter';
import { openSettingsSection } from './config/registry';
import { EngineOffNotice } from './EngineOffNotice';
import { DepthLadder, QuoteStats } from './MarketDepthPanel';
import { AdaptiveEdgePositionCalculator } from './AdaptiveEdgePositionCalculator';
import { k, tint } from '../../styles/kiteUI';

/**
 * ORB signal board.
 *
 * Tradable setups come first and carry the whole ticket — contract, venue,
 * entry, stop, target, live price, size and age. Candidates that did not fire
 * are real information but not a call to action, so they sit behind one
 * disclosure instead of padding the board with reasons nobody asked for.
 *
 * Expanding a setup fetches that contract's live book on demand (never for the
 * whole universe) and hands the numbers to the shared position calculator, so
 * the Buy path is the same order window every other board uses.
 */
const px = (v: number | null | undefined, dp = 2) => (v == null ? '—' : v.toFixed(dp));
const inr = (v: number | null | undefined) => (v == null ? '—' : `₹${Math.round(v).toLocaleString('en-IN')}`);

function hhmm(iso: string | null) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function Cell({ label, value, color = k.text, title }: { label: string; value: React.ReactNode; color?: string; title?: string }) {
  return (
    <div title={title} style={{ minWidth: 0 }}>
      <div style={{ fontSize: 8, color: k.dim, textTransform: 'uppercase', letterSpacing: '.04em', whiteSpace: 'nowrap' }}>{label}</div>
      <div style={{ fontSize: 10.5, fontWeight: 600, color, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</div>
    </div>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke={k.dim} strokeWidth="3" aria-hidden="true"
      style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform .14s ease', flexShrink: 0 }}>
      <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** The live book and Greeks for one contract — mounted only while expanded. */
function SetupDetail({ entry }: { entry: OrbFeedEntry }) {
  const key = entry.exchange && entry.optionSymbol ? `${entry.exchange}:${entry.optionSymbol}` : '';
  // 'full' mode carries the 5-level book; quote mode omits depth entirely.
  const { data } = useKiteQuote(key ? [key] : [], !!key, 5_000, 'full');
  const quote = key ? (data as Record<string, any> | undefined)?.[key] : undefined;

  const greeks = [
    entry.impliedVol != null && { label: 'IV', value: `${(entry.impliedVol * 100).toFixed(1)}%` },
    entry.delta != null && {
      label: 'Δ delta',
      // Say when it is an assumption: this delta is what the premium stop rests on.
      value: entry.deltaSource === 'assumed' ? `${entry.delta.toFixed(3)} assumed` : entry.delta.toFixed(3),
    },
    entry.gamma != null && { label: 'Γ gamma', value: entry.gamma.toFixed(5) },
    entry.thetaPerDay != null && { label: 'Θ theta/day', value: entry.thetaPerDay.toFixed(1) },
    entry.vegaPerPoint != null && { label: 'V vega', value: entry.vegaPerPoint.toFixed(1) },
    entry.lotSize != null && { label: 'Lot', value: String(entry.lotSize) },
  ].filter(Boolean) as { label: string; value: string }[];

  return (
    <div style={{ padding: '10px', background: k.surface, borderBottom: `2px solid ${k.border}`, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 4, padding: 10 }}>
        <div style={{ fontSize: 8.5, fontWeight: 700, color: k.dim, letterSpacing: '.05em', marginBottom: 6 }}>POSITION SIZING &amp; TRADE PLAN</div>
        <AdaptiveEdgePositionCalculator
          key={entry.id}
          symbol={entry.underlying}
          tradingsymbol={entry.optionSymbol ?? entry.underlying}
          exchange={entry.exchange ?? 'NFO'}
          expiry={entry.optionExpiry ?? undefined}
          lotSize={entry.lotSize ?? undefined}
          defaultEntryPrice={entry.optionPremium ?? undefined}
          defaultSl={entry.stopPremium ?? undefined}
          defaultExit={entry.targetPremium ?? undefined}
          currentLtp={quote?.last_price ?? entry.optionPremium ?? undefined}
          optionType={(entry.optionType ?? 'CE') as 'CE' | 'PE'}
          exitState="HOLD"
        />
      </div>

      <div style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 4, padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ fontSize: 8.5, fontWeight: 700, color: k.dim, letterSpacing: '.05em' }}>MARKET DEPTH</div>
        <DepthLadder quote={quote} />
        <QuoteStats
          quote={quote}
          extra={[
            { label: 'Expiry', value: entry.optionExpiry ?? '—' },
            ...greeks,
          ]}
        />
      </div>

      <div style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 4, padding: 10 }}>
        <div style={{ fontSize: 8.5, fontWeight: 700, color: k.dim, letterSpacing: '.05em', marginBottom: 6 }}>UNDERLYING SETUP</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(74px, 1fr))', gap: 6 }}>
          <Cell label="Spot" value={px(entry.spot)} />
          <Cell label="ORB high" value={px(entry.orbHigh)} />
          <Cell label="ORB low" value={px(entry.orbLow)} />
          <Cell label="VWAP" value={px(entry.vwap)} />
          <Cell label="ATR" value={px(entry.atr)} />
          <Cell label="Volume" value={entry.volumeRatio == null ? '—' : `${px(entry.volumeRatio)}×`} />
          <Cell label="U. entry" value={px(entry.underlyingEntry)} />
          <Cell label="U. stop" value={px(entry.underlyingStop)} color={k.red} />
        </div>
        {entry.reason && <div style={{ marginTop: 8, fontSize: 9.5, color: k.dim, lineHeight: 1.5 }}>{entry.reason}</div>}
      </div>
    </div>
  );
}

function SetupRow({ entry, open, onToggle }: { entry: OrbFeedEntry; open: boolean; onToggle: () => void }) {
  const dir = entry.direction === 'long' ? k.green : k.red;
  const stale = entry.quoteAgeS != null && entry.quoteAgeS > 15;
  return (
    <>
      <div
        role="button" tabIndex={0} aria-expanded={open}
        aria-label={`${entry.underlying} ${entry.optionType ?? ''} setup`}
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
        style={{
          padding: '9px 10px', cursor: 'pointer', outlineOffset: -2,
          borderBottom: `1px solid ${k.border}`,
          borderLeft: open ? `3px solid ${k.blue}` : `3px solid ${tint(dir, 55)}`,
          background: open ? k.surfaceHover : 'transparent', transition: 'background .12s ease',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Chevron open={open} />
          <span style={{ fontSize: 11, fontWeight: 700, color: k.text }}>{entry.underlying}</span>
          <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '.05em', color: dir, background: tint(dir, 12), border: `1px solid ${tint(dir, 35)}`, borderRadius: 3, padding: '1px 4px' }}>
            {entry.optionType} · {entry.direction?.toUpperCase()}
          </span>
          <span style={{ fontSize: 8.5, color: k.dim, border: `1px solid ${k.border}`, borderRadius: 3, padding: '1px 4px' }}>{entry.exchange ?? '—'}</span>
          <span style={{ marginLeft: 'auto', fontSize: 8.5, color: stale ? k.red : k.dim, fontVariantNumeric: 'tabular-nums' }}>
            {hhmm(entry.timestamp)}{stale ? ' · stale' : ''}
          </span>
        </div>

        {/* The leg: one contract, named in full — this is what gets bought. */}
        <div style={{ marginTop: 4, paddingLeft: 15, fontSize: 9.5, color: k.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {entry.optionSymbol}
          <span style={{ color: k.dim }}> · {entry.optionStrike ?? '—'} {entry.optionExpiry ?? ''}</span>
        </div>

        <div style={{ marginTop: 5, paddingLeft: 15, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(58px, 1fr))', gap: 6 }}>
          <Cell label="LTP" value={px(entry.optionPremium)} />
          <Cell label="Entry" value={px(entry.optionPremium)} />
          <Cell label="SL" value={px(entry.stopPremium)} color={k.red} />
          <Cell label="Exit" value={px(entry.targetPremium)} color={k.green} />
          <Cell label="Qty" value={entry.quantity ?? '—'} title={entry.lotSize ? `${entry.lotSize} per lot` : undefined} />
          <Cell label="At risk" value={inr(entry.maxLossInr)} title="Full premium outlay — a bought option can expire worthless" />
        </div>
      </div>
      {open && <SetupDetail entry={entry} />}
    </>
  );
}

function QuietRow({ entry }: { entry: OrbFeedEntry }) {
  const color = entry.state === 'ERROR' ? k.red : k.dim;
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, padding: '5px 10px 5px 25px', borderBottom: `1px solid ${k.surface}`, fontSize: 9.5 }}>
      <span style={{ fontWeight: 600, color: k.text, minWidth: 78 }}>{entry.underlying}</span>
      <span style={{ color: k.dim, fontVariantNumeric: 'tabular-nums', minWidth: 58 }}>{px(entry.spot)}</span>
      <span style={{ color, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entry.reason || entry.state.toLowerCase().replace(/_/g, ' ')}</span>
    </div>
  );
}

export function NiftyOrbSignalsFeed() {
  const config = useOrbConfig();
  const setEnabled = useSetOrbEnabled();
  const enabled = config.data?.config?.enabled;
  const { signals, isLoading, error } = useOrbSignals(enabled !== false);
  const [openId, setOpenId] = React.useState<string | null>(null);
  const [showQuiet, setShowQuiet] = React.useState(false);

  if (config.isLoading) return <div style={{ padding: 12, fontSize: 9.5, color: k.dim }}>Loading ORB configuration…</div>;

  if (enabled === false) {
    return (
      <EngineOffNotice
        engine="ORB + VWAP"
        detail="The opening-range engine is switched off, so nothing is being scanned and no setups can appear here. Turning it on starts the scan; it buys calls on LONG and puts on SHORT, and never sells options."
        onEnable={() => setEnabled.mutate(true)}
        pending={setEnabled.isPending}
        onConfigure={() => openSettingsSection('orbOptions')}
        configureLabel="ORB settings"
        error={setEnabled.error ? (setEnabled.error as Error).message : null}
      />
    );
  }

  if (isLoading) return <div style={{ padding: 12, fontSize: 9.5, color: k.dim }}>Scanning ORB universe…</div>;
  if (error) return <div style={{ padding: 12, fontSize: 9.5, color: k.red }}>ORB feed unavailable: {(error as Error).message}</div>;
  if (!signals.length) {
    return (
      <EngineOffNotice
        engine="ORB universe"
        detail="ORB is on, but no underlyings are configured for it to scan. Add indices or single-stock underlyings in ORB settings."
        onConfigure={() => openSettingsSection('orbOptions')}
        configureLabel="Choose underlyings"
      />
    );
  }

  const setups = signals.filter((s) => s.state === 'SIGNAL');
  const quiet = signals.filter((s) => s.state !== 'SIGNAL');
  const failed = quiet.filter((s) => s.state === 'ERROR');

  return (
    <div>
      {failed.length === signals.length && (
        <div style={{ padding: '8px 10px', borderBottom: `1px solid ${k.border}`, background: tint(k.red, 8), color: k.red, fontSize: 9, lineHeight: 1.5 }}>
          Scan failed for all {failed.length} underlyings — {failed[0].reason}
        </div>
      )}

      <div style={{ padding: '7px 10px', borderBottom: `1px solid ${k.border}`, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '.06em', color: k.dim }}>BUY-ONLY · CE / PE</span>
        <span style={{ marginLeft: 'auto', fontSize: 9, color: k.dim }}>
          <b style={{ color: setups.length ? k.green : k.dim }}>{setups.length}</b> tradable · {signals.length} scanned
        </span>
      </div>

      {setups.map((entry) => (
        <SetupRow key={entry.id} entry={entry} open={openId === entry.id}
          onToggle={() => setOpenId((prev) => (prev === entry.id ? null : entry.id))} />
      ))}

      {!setups.length && (
        <div style={{ padding: '14px 12px', fontSize: 9.5, color: k.dim, lineHeight: 1.6 }}>
          No tradable ORB setup right now. The universe is being scanned — the list below says what each
          underlying is waiting on.
        </div>
      )}

      {quiet.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowQuiet((v) => !v)}
            aria-expanded={showQuiet}
            style={{
              width: '100%', textAlign: 'left', padding: '7px 10px', cursor: 'pointer',
              border: 'none', borderTop: `1px solid ${k.border}`, borderBottom: showQuiet ? `1px solid ${k.border}` : 'none',
              background: k.surface, color: k.dim, fontFamily: 'inherit', fontSize: 9,
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <Chevron open={showQuiet} />
            {quiet.length} not signalling
            {failed.length > 0 && <span style={{ color: k.red }}>· {failed.length} errored</span>}
          </button>
          {showQuiet && quiet.map((entry) => <QuietRow key={entry.id} entry={entry} />)}
        </>
      )}
    </div>
  );
}

export default NiftyOrbSignalsFeed;
