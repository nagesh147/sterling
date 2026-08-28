import { useEngineActivity } from './useSterlingKiteEngine';
import { useScanActivity } from '../store/useScanActivity';
import { SCANNABLE_ENGINE_LABEL } from './useScanAllStrategies';

/**
 * What is scanning, and what it is scanning.
 *
 * The dock's status line used to render `activity.scanning_label` on its own — a
 * bare contract name like "TCS OCT 2300 PE" with nothing saying which strategy it
 * belonged to. `/activity` is SUPERTREND's endpoint, so that label is always
 * SuperTrend's; during a five-engine re-scan the line showed SuperTrend's contract
 * for its turn and then dropped to "AUTO" while the other four ran, which reads as
 * "the label is unrelated to whatever is scanning" — because from the outside it
 * is indistinguishable from exactly that.
 *
 * So the strategy comes first and the contract second, and the strategy named is
 * the one actually running:
 *
 *   SuperTrend · TCS OCT 2300 PE     ← live feed, engine and item both known
 *   Gamma Move · scanning…           ← running, but this engine reports no item
 *
 * `detail` is null rather than invented for the four engines that publish no
 * progress. Naming a contract they are not on would be worse than the bare label
 * this replaces.
 */
export interface ScanStatus {
  scanning: boolean;
  /** The strategy's display name, or null when nothing is scanning. */
  engineLabel: string | null;
  /** What that strategy is currently reading, when it says. */
  detail: string | null;
}

export function useScanStatus(): ScanStatus {
  const activity = useEngineActivity().data;
  const current = useScanActivity((s) => s.current);

  // SuperTrend's own feed wins: it is the only source that knows an ITEM, and if
  // it says it is scanning then it is, whether or not a manual sweep started it.
  if (activity?.scanning) {
    return {
      scanning: true,
      engineLabel: SCANNABLE_ENGINE_LABEL.supertrend,
      detail: activity.scanning_label || null,
    };
  }

  // Otherwise a manual sweep may be working through an engine that reports
  // nothing. Name it; claim no item.
  if (current) {
    return { scanning: true, engineLabel: SCANNABLE_ENGINE_LABEL[current], detail: null };
  }

  return { scanning: false, engineLabel: null, detail: null };
}

export default useScanStatus;
