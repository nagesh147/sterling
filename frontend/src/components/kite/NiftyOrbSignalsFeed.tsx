import React from 'react';
import { useOrbSignals } from '../../hooks/useOrbSignals';
import { useOrbConfig, useSetOrbEnabled } from '../../hooks/useOrbConfig';
import type { OrbFeedEntry } from '../../utils/niftyOrbSignalAdapter';
import { openSettingsSection } from './config/registry';
import { EngineOffNotice } from './EngineOffNotice';
import { k, tint } from '../../styles/kiteUI';

/**
 * ORB feed for the narrow right dock.
 *
 * One row per candidate with an inline expansion, matching the Adaptive Edge
 * idiom (single-open accordion, blue left rail on the open row, stat cards in
 * the detail). The settings page carries the full wide table; this column cannot
 * show eighteen columns without horizontal scrolling, so the row shows what a
 * trader acts on and the expansion carries the rest.
 */
const money = (v: number | null | undefined) => (v == null ? '—' : `₹${Math.round(v).toLocaleString('en-IN')}`);
const num = (v: number | null | undefined, dp = 2) => (v == null ? '—' : v.toFixed(dp));

const STATE_COLOR: Record<string, string> = {
  SIGNAL: k.green,
  SIGNAL_UNRESOLVED: k.amber,
  REJECTED: k.red,
  ERROR: k.red,
  WATCHING: k.dim,
};

function Stat({ label, value, color = k.text, title }: { label: string; value: string; color?: string; title?: string }) {
  return (
    <div title={title} style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 3, padding: '5px 7px', minWidth: 0 }}>
      <div style={{ fontSize: 8.5, fontWeight: 600, color: k.dim, textTransform: 'uppercase', letterSpacing: '.04em', whiteSpace: 'nowrap' }}>{label}</div>
      <div style={{ fontSize: 11, fontWeight: 600, color, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</div>
    </div>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="9" height="9" viewBox="0 0 24 24" fill="none" stroke={k.dim} strokeWidth="3" aria-hidden="true"
      style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform .14s ease', flexShrink: 0 }}
    >
      <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SignalRow({ entry, open, onToggle }: { entry: OrbFeedEntry; open: boolean; onToggle: () => void }) {
  const actionable = entry.state === 'SIGNAL';
  const stateColor = STATE_COLOR[entry.state] ?? k.dim;
  const dirColor = entry.direction === 'long' ? k.green : entry.direction === 'short' ? k.red : k.dim;
  const stale = entry.quoteAgeS != null && entry.quoteAgeS > 15;

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-label={`${entry.underlying} ${entry.state}`}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); }
        }}
        style={{
          padding: '8px 10px', cursor: 'pointer', outlineOffset: -2,
          borderBottom: `1px solid ${k.border}`,
          borderLeft: open ? `3px solid ${k.blue}` : '3px solid transparent',
          background: open ? k.surfaceHover : actionable ? tint(k.green, 5) : 'transparent',
          transition: 'background .12s ease',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Chevron open={open} />
          <span style={{ fontSize: 10.5, fontWeight: 700, color: k.text }}>{entry.underlying}</span>
          {entry.optionType && (
            <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '.05em', color: dirColor, background: tint(dirColor, 12), border: `1px solid ${tint(dirColor, 35)}`, borderRadius: 3, padding: '1px 4px' }}>
              {entry.optionType}
            </span>
          )}
          <span style={{ marginLeft: 'auto', fontSize: 9, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>{num(entry.spot)}</span>
        </div>

        <div style={{ marginTop: 3, display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 15 }}>
          <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '.05em', color: stateColor }}>{entry.state.replace(/_/g, ' ')}</span>
          {actionable ? (
            <span style={{ fontSize: 9, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>
              {entry.quantity ?? '—'} @ {num(entry.optionPremium)} · at risk <b style={{ color: k.text }}>{money(entry.maxLossInr)}</b>
            </span>
          ) : (
            // The engine names the first unmet gate; showing it is the whole point.
            <span style={{ fontSize: 9, color: k.dim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entry.reason || '—'}</span>
          )}
          {stale && <span title={`Quote ${num(entry.quoteAgeS, 1)}s old`} style={{ marginLeft: 'auto', fontSize: 8.5, color: k.red }}>STALE</span>}
        </div>
      </div>

      {open && (
        <div style={{ padding: '10px 10px 12px', background: k.surface, borderBottom: `2px solid ${k.border}` }}>
          <div style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 4, padding: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div>
              <div style={{ fontSize: 8.5, fontWeight: 700, color: k.dim, letterSpacing: '.05em', marginBottom: 5 }}>UNDERLYING STRUCTURE</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(72px, 1fr))', gap: 5 }}>
                <Stat label="ORB hi" value={num(entry.orbHigh)} />
                <Stat label="ORB lo" value={num(entry.orbLow)} />
                <Stat label="VWAP" value={num(entry.vwap)} />
                <Stat label="ATR" value={num(entry.atr)} />
                <Stat label="Vol" value={entry.volumeRatio == null ? '—' : `${num(entry.volumeRatio)}x`} title="Current bar volume against this session's baseline" />
                <Stat label="Spot" value={num(entry.spot)} />
              </div>
            </div>

            {entry.optionSymbol && (
              <div>
                <div style={{ fontSize: 8.5, fontWeight: 700, color: k.dim, letterSpacing: '.05em', marginBottom: 5 }}>EXECUTION VEHICLE</div>
                <div style={{ fontSize: 9.5, color: k.text, marginBottom: 5, wordBreak: 'break-all' }}>{entry.optionSymbol}</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(72px, 1fr))', gap: 5 }}>
                  <Stat label="Strike" value={entry.optionStrike == null ? '—' : String(entry.optionStrike)} />
                  <Stat label="Expiry" value={entry.optionExpiry || '—'} />
                  <Stat label="Entry" value={num(entry.optionPremium)} />
                  <Stat label="Stop" value={num(entry.stopPremium)} color={k.red} />
                  <Stat label="Target" value={num(entry.targetPremium)} color={k.green} />
                  <Stat label="Qty" value={entry.quantity == null ? '—' : String(entry.quantity)} />
                </div>
              </div>
            )}

            {/* Risk only exists once there is a plan. Rendering the block for a
                candidate that produced none invented a delta source for it. */}
            {entry.maxLossInr != null && (
              <div>
                <div style={{ fontSize: 8.5, fontWeight: 700, color: k.dim, letterSpacing: '.05em', marginBottom: 5 }}>RISK</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(72px, 1fr))', gap: 5 }}>
                  <Stat label="At risk" value={money(entry.maxLossInr)} title="Full premium outlay — what this loses if the option expires worthless" />
                  <Stat label="Stop risk" value={money(entry.riskInr)} title="Modelled loss if the premium stop fills" />
                  <Stat
                    label="Delta"
                    value={entry.deltaSource === 'assumed' ? '0.50 assumed' : entry.deltaSource ?? '—'}
                    color={entry.deltaSource === 'assumed' ? k.amber : k.text}
                    title={entry.deltaSource === 'assumed'
                      ? 'The premium could not be solved for volatility, so 0.50 was assumed — the stop premium armed at the broker rests on that'
                      : 'Solved from the traded premium'}
                  />
                  {entry.impliedVol != null && <Stat label="Implied vol" value={`${(entry.impliedVol * 100).toFixed(1)}%`} />}
                </div>
              </div>
            )}

            <div>
              <div style={{ fontSize: 8.5, fontWeight: 700, color: k.dim, letterSpacing: '.05em', marginBottom: 5 }}>DATA</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(72px, 1fr))', gap: 5 }}>
                <Stat label="Source" value={entry.dataSource || '—'} />
                <Stat label="Quote age" value={entry.quoteAgeS == null ? '—' : `${num(entry.quoteAgeS, 1)}s`} color={stale ? k.red : k.text} />
                <Stat label="State" value={entry.state.replace(/_/g, ' ')} color={stateColor} />
              </div>
            </div>

            {entry.reason && (
              <div>
                <div style={{ fontSize: 8.5, fontWeight: 700, color: k.dim, letterSpacing: '.05em', marginBottom: 3 }}>
                  {actionable ? 'WHY IT FIRED' : 'WHY IT DID NOT'}
                </div>
                <div style={{ fontSize: 9.5, color: k.dim, lineHeight: 1.5 }}>{entry.reason}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export function NiftyOrbSignalsFeed() {
  const config = useOrbConfig();
  const setEnabled = useSetOrbEnabled();
  const enabled = config.data?.config?.enabled;
  const { signals, isLoading, error } = useOrbSignals(enabled !== false);
  const [openId, setOpenId] = React.useState<string | null>(null);

  if (config.isLoading) return <div style={{ padding: 12, fontSize: 9.5, color: k.dim }}>Loading ORB configuration…</div>;

  if (enabled === false) {
    return (
      <EngineOffNotice
        engine="ORB + VWAP"
        detail="The opening-range engine is switched off, so nothing is being scanned and no signals can appear here. Turning it on starts the 5-minute scan; it buys calls on LONG and puts on SHORT, and never sells options."
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

  const actionable = signals.filter((s) => s.state === 'SIGNAL');
  const failed = signals.filter((s) => s.state === 'ERROR');
  const allFailed = failed.length === signals.length;

  return (
    <div>
      {allFailed && (
        // Everything erroring is a broken scan, not a quiet market.
        <div style={{ padding: '8px 10px', borderBottom: `1px solid ${k.border}`, background: tint(k.red, 8), color: k.red, fontSize: 9, lineHeight: 1.5 }}>
          Scan failed for all {failed.length} underlyings — {failed[0].reason}
        </div>
      )}
      <div style={{ padding: '7px 10px', borderBottom: `1px solid ${k.border}`, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '.06em', color: k.dim }}>BUY-ONLY · CE / PE</span>
        <span style={{ marginLeft: 'auto', fontSize: 9, color: k.dim }}>
          <b style={{ color: actionable.length ? k.green : k.dim }}>{actionable.length}</b> actionable · {signals.length} scanned
        </span>
      </div>
      {/* Actionable first: a live plan must never sit below a wall of rejections. */}
      {[...actionable, ...signals.filter((s) => s.state !== 'SIGNAL')].map((entry) => (
        <SignalRow
          key={entry.id}
          entry={entry}
          open={openId === entry.id}
          onToggle={() => setOpenId((prev) => (prev === entry.id ? null : entry.id))}
        />
      ))}
    </div>
  );
}

export default NiftyOrbSignalsFeed;
