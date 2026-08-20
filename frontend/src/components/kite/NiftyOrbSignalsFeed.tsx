import React from 'react';
import { useOrbSignals } from '../../hooks/useOrbSignals';
import type { OrbFeedEntry } from '../../utils/niftyOrbSignalAdapter';
import { k, tint } from '../../styles/kiteUI';

/**
 * Compact ORB feed for the narrow right dock.
 *
 * The settings page carries the full eighteen-column table; a dock this width
 * cannot show it without horizontal scrolling, so this shows what a trader acts
 * on -- direction, the contract, the premium committed -- and, for anything that
 * did not fire, the gate that stopped it.
 */
const money = (v: number | null) => (v == null ? '—' : `₹${Math.round(v).toLocaleString('en-IN')}`);
const num = (v: number | null, dp = 2) => (v == null ? '—' : v.toFixed(dp));

function DirectionBadge({ entry }: { entry: OrbFeedEntry }) {
  const long = entry.direction === 'long';
  const color = entry.direction ? (long ? k.green : k.red) : k.dim;
  return (
    <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '.06em', color, background: tint(color, 12), border: `1px solid ${tint(color, 35)}`, borderRadius: 3, padding: '1px 4px' }}>
      {entry.optionType ?? (entry.direction ? entry.direction.toUpperCase() : 'FLAT')}
    </span>
  );
}

function SignalRow({ entry }: { entry: OrbFeedEntry }) {
  const actionable = entry.state === 'SIGNAL';
  const stale = entry.quoteAgeS != null && entry.quoteAgeS > 15;
  return (
    <div style={{ padding: '8px 10px', borderBottom: `1px solid ${k.border}`, background: actionable ? tint(k.blue, 4) : 'transparent' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 10.5, fontWeight: 700, color: k.text }}>{entry.underlying}</span>
        <DirectionBadge entry={entry} />
        <span style={{ marginLeft: 'auto', fontSize: 9, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>
          {num(entry.spot)}
        </span>
      </div>

      {actionable && entry.optionSymbol ? (
        <>
          <div style={{ marginTop: 4, fontSize: 9, color: k.dim, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {entry.optionSymbol}
          </div>
          <div style={{ marginTop: 3, display: 'flex', gap: 10, fontSize: 9, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>
            <span>entry <b style={{ color: k.text }}>{num(entry.optionPremium)}</b></span>
            <span>sl <b style={{ color: k.red }}>{num(entry.stopPremium)}</b></span>
            <span>tgt <b style={{ color: k.green }}>{num(entry.targetPremium)}</b></span>
          </div>
          <div style={{ marginTop: 3, display: 'flex', gap: 10, fontSize: 9, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>
            <span>{entry.quantity ?? '—'} qty</span>
            {/* The premium actually committed, not the modelled stop risk. */}
            <span>at risk <b style={{ color: k.text }}>{money(entry.maxLossInr)}</b></span>
            {entry.deltaSource === 'assumed' && (
              <span title="Delta assumed 0.50 — the premium could not be solved for volatility" style={{ color: k.amber }}>≈δ</span>
            )}
            {entry.impliedVol != null && (
              <span title="Implied volatility solved from the traded premium" style={{ color: k.dim }}>
                iv {(entry.impliedVol * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </>
      ) : (
        // Why this candidate did not produce a trade, in the engine's own words.
        <div style={{ marginTop: 4, fontSize: 9, color: k.dim, lineHeight: 1.45 }}>
          {entry.reason || entry.state.toLowerCase().replace(/_/g, ' ')}
        </div>
      )}

      {stale && (
        <div style={{ marginTop: 3, fontSize: 8.5, color: k.red }}>
          quote {num(entry.quoteAgeS, 1)}s old
        </div>
      )}
    </div>
  );
}

export function NiftyOrbSignalsFeed() {
  const { signals, isLoading, error } = useOrbSignals(true);
  const actionable = signals.filter((s) => s.state === 'SIGNAL');
  const rest = signals.filter((s) => s.state !== 'SIGNAL');

  if (isLoading) return <div style={{ padding: 12, fontSize: 9.5, color: k.dim }}>Scanning ORB universe…</div>;
  if (error) return <div style={{ padding: 12, fontSize: 9.5, color: k.red }}>ORB feed unavailable: {(error as Error).message}</div>;
  if (!signals.length) return <div style={{ padding: 12, fontSize: 9.5, color: k.dim }}>No configured underlyings. Enable ORB in Connect → ORB + VWAP Options.</div>;

  const failed = signals.filter((s) => s.state === 'ERROR');
  // A universe where everything errored is a broken scan, not a quiet market.
  const allFailed = failed.length === signals.length;

  return (
    <div>
      {allFailed && (
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
      {/* Actionable first: the dock is scrolled, and a live plan must not sit below a wall of rejections. */}
      {[...actionable, ...rest].map((entry) => <SignalRow key={entry.id} entry={entry} />)}
    </div>
  );
}

export default NiftyOrbSignalsFeed;
