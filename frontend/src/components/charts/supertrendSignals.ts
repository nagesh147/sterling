export type SupertrendDirection = 'up' | 'down';

export interface SupertrendPointLike {
  direction?: SupertrendDirection | null;
}

export interface SupertrendSignalMarker {
  time: number;
  position: 'aboveBar' | 'belowBar';
  color: string;
  shape: 'arrowUp' | 'arrowDown';
}

interface MarkerOptions {
  upColor?: string;
  downColor?: string;
}

/**
 * Convert SuperTrend direction changes into Kite-style buy/sell arrows.
 * The seeded first direction is intentionally ignored: only genuine flips
 * produce a marker.
 */
export function supertrendFlipMarkers(
  points: SupertrendPointLike[],
  times: number[],
  options: MarkerOptions = {},
): SupertrendSignalMarker[] {
  const upColor = options.upColor || '#089981';
  const downColor = options.downColor || '#f23645';
  const length = Math.min(points.length, times.length);
  const markers: SupertrendSignalMarker[] = [];

  for (let index = 1; index < length; index += 1) {
    const previous = points[index - 1]?.direction;
    const current = points[index]?.direction;
    const time = times[index];
    if (!previous || !current || previous === current || !Number.isFinite(time)) continue;

    markers.push(current === 'up'
      ? { time, position: 'belowBar', color: upColor, shape: 'arrowUp' }
      : { time, position: 'aboveBar', color: downColor, shape: 'arrowDown' });
  }

  return markers;
}

/** Merge markers from multiple SuperTrend variants without stacking duplicates. */
export function mergeSupertrendMarkers(...groups: SupertrendSignalMarker[][]): SupertrendSignalMarker[] {
  const unique = new Map<string, SupertrendSignalMarker>();
  groups.flat().forEach((marker) => {
    unique.set(`${marker.time}:${marker.position}`, marker);
  });
  return [...unique.values()].sort((a, b) => a.time - b.time);
}
