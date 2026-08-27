import React from 'react';
import { SterlingKiteEnginePane } from './SterlingKiteEnginePane';
import type { SignalChartData } from '../../types/kiteEngine';

/**
 * SuperTrend's board.
 *
 * This used to carry a one-line CONTRACTS strip above the table — a dot, the
 * text "6 of 8 expiry sets · 14 live dates", and a "Change →" link into
 * settings. That row is gone; contract selection lives in
 * Connect → SuperTrend beside the universe and the scan rules, and the strip was
 * spending a row of vertical space on a restatement of it.
 *
 * What remains is a pass-through, kept only so its two callers do not have to
 * change import. It can be inlined whenever someone is in here anyway.
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
  return <SterlingKiteEnginePane {...props} />;
}

export default SterlingKiteEngineWithExpiry;
