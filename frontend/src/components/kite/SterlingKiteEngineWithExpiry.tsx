import React from 'react';
import { SterlingKiteEnginePane } from './SterlingKiteEnginePane';
import { useContractSelection } from './config/optionContractsMachinery';
import { openSettingsSection } from './config/registry';
import type { SignalChartData } from '../../types/kiteEngine';
import { k } from '../../styles/kiteUI';

/**
 * SuperTrend's board, with a one-line statement of which contracts feed it.
 *
 * The contract picker used to live here as a 56-pixel banner above the table:
 * the loudest element on the screen, sitting on top of the rows it exists to
 * serve, and the only engine whose contract selection was not in settings. It
 * has moved to Connect → SuperTrend, beside where the universe and the scan
 * rules are already configured.
 *
 * What stays is the fact a trader actually needs while reading the board — what
 * is being scanned right now — as a line they can read without opening
 * anything, plus a link for when they want to change it. A summary is not a
 * control, so it does not get a control's weight.
 */
interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number }) => void;
  onOpenChart?: (
    symbol: string,
    tab: 'chart',
    trailTarget?: 'fast' | 'mid' | 'slow',
    signalData?: SignalChartData,
  ) => void;
}

export function SterlingKiteEngineWithExpiry(props: Props) {
  const selection = useContractSelection();

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      <div
        style={{
          flexShrink: 0, display: 'flex', alignItems: 'center', gap: 7,
          padding: '4px 12px', borderBottom: `1px solid ${k.border}`, background: k.bg,
        }}
      >
        <span
          aria-hidden
          title={selection.error ? 'Contract dates unavailable' : 'Live Kite contract dates'}
          style={{ width: 5, height: 5, borderRadius: '50%', flexShrink: 0, background: selection.error ? k.red : k.green }}
        />
        <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '.06em', color: k.dim, flexShrink: 0 }}>CONTRACTS</span>
        <span
          style={{
            fontSize: 10, color: selection.error ? k.red : k.dim, fontVariantNumeric: 'tabular-nums',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}
        >
          {selection.summary}
        </span>
        <button
          type="button"
          onClick={() => openSettingsSection('engine')}
          style={{
            marginLeft: 'auto', flexShrink: 0, border: 'none', background: 'transparent',
            color: k.blue, fontFamily: 'inherit', fontSize: 9.5, fontWeight: 600,
            cursor: 'pointer', padding: '2px 4px', borderRadius: 3,
          }}
        >
          Change →
        </button>
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        <SterlingKiteEnginePane {...props} />
      </div>
    </div>
  );
}

export default SterlingKiteEngineWithExpiry;
