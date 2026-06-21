import { useSignalMarkers } from '../../store/useSignalMarkers';

/**
 * Renders the ✝ (best reward:risk) and ▲ (best delta) markers for a symbol when it
 * matches a current Triple SuperTrend signal leg. Grey, by design, to match the
 * markers shown in the signal rows. Returns null when the symbol carries no marker.
 *
 * `color` lets each host pass its own grey (the light-theme watchlist uses k.dim;
 * the dark-theme ticker uses var(--t-dim)).
 */
export function SignalMarker({ symbol, color = 'var(--t-dim)', size = 12 }: { symbol: string; color?: string; size?: number }) {
  const mark = useSignalMarkers((s) => s.markers[symbol]);
  if (!mark || (!mark.rr && !mark.delta)) return null;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, flexShrink: 0 }}>
      {mark.rr && (
        <span title="Best reward-to-risk among this signal's strikes" style={{ fontSize: size, color, lineHeight: 1 }}>✝</span>
      )}
      {mark.delta && (
        <span title="Highest delta — most responsive to the underlying" style={{ fontSize: size - 1, color, lineHeight: 1, opacity: 0.75 }}>▲</span>
      )}
    </span>
  );
}

export default SignalMarker;
