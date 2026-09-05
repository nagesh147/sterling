import React from 'react';
import { k, tint } from '../../styles/kiteUI';
import { useKiteStatus } from '../../hooks/useKite';
import { useEngineSignals, useEngineConfig } from '../../hooks/useSterlingKiteEngine';
import { useNavigatorConfig } from '../../hooks/useNavigator';
import { useOrbConfig } from '../../hooks/useOrbConfig';
import { useAdaptiveEdgeSnapshot } from '../../hooks/useAdaptiveEdge';
import { useGammaMoveSnapshot } from '../../hooks/useGammaMove';
import { useAtmPremiumImbalanceSnapshot } from '../../hooks/useAtmPremiumImbalance';


/**
 * Broker connection and per-strategy state, in the footer.
 *
 * The replay chip that used to live here has moved to `ReplayFooterChip`.
 * Replay is a mode, not an engine, and sitting in this cluster implied it was
 * a seventh strategy — while duplicating the clock the dock toggle already
 * rendered forty pixels away.
 *
 * **On what these chips can honestly say.** Only SuperTrend reports scan
 * timing — `scanning`, `scanning_label`, `generated_ms`, `next_scan_ms`. ORB and
 * Adaptive Edge expose nothing about scanning at all, and Gamma Move and the ATM
 * bot expose a phase rather than a schedule. So a strip promising
 * "scanning / next scan / last scan" for all five would be inventing four
 * fifths of itself.
 *
 * Each chip therefore shows what its engine actually publishes: whether it is
 * ON, and the scan state where there is one. An engine that reports no schedule
 * says nothing about a schedule rather than showing a plausible dash that reads
 * as "idle". Adding the timing to the other engines is backend work per engine,
 * and this strip is where it would surface once it exists.
 */
export function KiteFooterStatus({ onOpenSession }: { onOpenSession: () => void }) {
  const status = useKiteStatus().data;
  const sig = useEngineSignals().data;
  const engineOn = useEngineConfig().data?.engine_enabled !== false;
  const navOn = useNavigatorConfig().data?.record.config.enabled ?? false;
  const orbOn = useOrbConfig().data?.config?.enabled !== false;
  const aeOn = !!useAdaptiveEdgeSnapshot().data;
  const gmOn = !!useGammaMoveSnapshot().data?.strategy?.enabled;
  const atmArmed = !!useAtmPremiumImbalanceSnapshot().data?.session?.armed;

  // A failed CHECK is not a disconnection: the token is intact and Sterling
  // simply could not ask. Showing it as "offline" is the same conflation that
  // produced a session-expired modal over a good session.
  const unknown = !!status?.transient;
  const connected = !!status?.connected;
  const brokerTone = connected ? k.green : unknown ? k.dim : k.red;
  const brokerText = connected ? 'KITE' : unknown ? 'KITE ?' : 'KITE OFF';
  const brokerHint = connected
    ? `Connected${status?.user_name ? ` · ${status.user_name}` : ''}${
        status?.token_expires_at_ms
          ? ` · expires ${new Date(status.token_expires_at_ms).toLocaleTimeString('en-IN', {
              hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata',
            })} IST`
          : ''}`
    : unknown
      ? 'Could not reach Kite to check the session. The stored token is untouched — nothing has expired.'
      : 'Not connected. Click to reconnect.';

  const strategies: Array<{ label: string; on: boolean; note?: string }> = [
    {
      label: 'ST',
      on: engineOn,
      // The only engine that publishes a schedule, so the only one that gets one.
      note: !engineOn ? 'off'
        : sig?.scanning ? (sig.scanning_label || 'scanning')
        : sig?.auto_scan === false ? 'manual'
        : sig?.market_open === false ? 'market closed'
        : 'auto',
    },
    { label: 'NAV', on: navOn, note: navOn ? undefined : 'off' },
    { label: 'ORB', on: orbOn, note: orbOn ? undefined : 'off' },
    { label: 'AE', on: aeOn, note: aeOn ? undefined : 'off' },
    { label: 'GM', on: gmOn, note: gmOn ? undefined : 'off' },
    { label: 'ATM', on: atmArmed, note: atmArmed ? 'armed' : 'not armed' },
  ];

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
      <button
        type="button"
        onClick={onOpenSession}
        title={brokerHint}
        className="sb-tool"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 4, height: 20, padding: '0 6px',
          border: `1px solid ${tint(brokerTone, 40)}`, borderRadius: 4,
          background: tint(brokerTone, 10), color: brokerTone,
          fontFamily: 'inherit', fontSize: 8.5, fontWeight: 800, letterSpacing: '.05em',
          cursor: 'pointer', whiteSpace: 'nowrap',
        }}
      >
        <span style={{ width: 5, height: 5, borderRadius: '50%', background: brokerTone, flexShrink: 0 }} />
        {brokerText}
      </button>

      <span style={{ width: 1, height: 13, background: 'var(--k-border)', flexShrink: 0 }} />

      {strategies.map((s) => (
        <span
          key={s.label}
          title={`${s.label} — ${s.on ? 'on' : 'off'}${s.note ? ` · ${s.note}` : ''}`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 3, flexShrink: 0,
            fontSize: 8.5, fontWeight: 750, letterSpacing: '.04em',
            color: s.on ? k.text : 'var(--k-faint-2)',
          }}
        >
          <span style={{
            width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
            background: s.on ? k.green : 'var(--k-faint-2)',
          }} />
          {s.label}
          {/* Only where the engine genuinely publishes one. */}
          {s.note && s.on && (
            <span style={{
              color: k.dim, fontWeight: 500, maxWidth: 130,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {s.note}
            </span>
          )}
        </span>
      ))}
    </span>
  );
}

export default KiteFooterStatus;
