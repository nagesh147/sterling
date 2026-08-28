import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';
import { useRunScan } from './useSterlingKiteEngine';
import { useRunNavigatorScan } from './useNavigator';
import { useGammaMoveScan } from './useGammaMove';
import { useScanActivity } from '../store/useScanActivity';

/**
 * One re-scan for every strategy that has one.
 *
 * Re-scan used to reach SuperTrend and Navigator — the two engines whose rows
 * share the pane the button sits on. Three others have scan endpoints and were
 * never triggered by it, so pressing re-scan refreshed part of the platform and
 * left the rest on its own background loop.
 *
 * The fan-out lives here rather than in the pane so the pane does not have to
 * import five engines' hooks to own one button, and so the order and the
 * failure handling are in one testable place.
 *
 * **Sequential, always.** Every one of these draws on the same Kite historical
 * budget — roughly three requests a second — so firing them together does not
 * make the scan faster, it makes each one slower and risks the rate limiter
 * rejecting work that would otherwise have completed. `kitelake`'s own cost
 * model is built on that constant.
 *
 * **ATM Premium Imbalance is absent because it has no scan.** It resolves one
 * option pair and arms it; there is no universe to sweep. Listing it here with
 * nothing to call would be a promise the platform cannot keep.
 */
export type ScannableEngine =
  | 'supertrend' | 'navigator' | 'orb' | 'gamma_move' | 'adaptive_edge';

export const SCANNABLE_ENGINE_LABEL: Record<ScannableEngine, string> = {
  supertrend: 'SuperTrend',
  navigator: 'Navigator',
  orb: 'ORB',
  gamma_move: 'Gamma Move',
  adaptive_edge: 'Adaptive Edge',
};

export interface EngineScanResult {
  engine: ScannableEngine;
  ok: boolean;
  /** Present when the scan was refused or failed. */
  error?: string;
}

/** `POST /config/adaptive-edge/scan`. Had no hook before this. */
export function useAdaptiveEdgeScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post('/api/v1/config/adaptive-edge/scan', {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['adaptive-edge-snapshot'] }),
  });
}

export function useScanAllStrategies() {
  const qc = useQueryClient();
  const supertrend = useRunScan();
  const navigator = useRunNavigatorScan();
  const gammaMove = useGammaMoveScan();
  const adaptiveEdge = useAdaptiveEdgeScan();

  // ORB's scan is exposed as a polling query that POSTs, not a mutation, so it
  // is triggered by refetching its key rather than by calling a mutate. Reaching
  // for the same query key the feed uses means the feed shows the result of the
  // scan this button ran, rather than whatever its own 5-second loop last got.
  const orb = () => qc.refetchQueries({ queryKey: ['nifty-orb-options-scan'] });

  const runners: Record<ScannableEngine, () => Promise<unknown>> = {
    supertrend: () => supertrend.mutateAsync(),
    navigator: () => navigator.mutateAsync(),
    orb,
    gamma_move: () => gammaMove.mutateAsync(),
    adaptive_edge: () => adaptiveEdge.mutateAsync(),
  };

  /**
   * Run every engine in `order`, one at a time, and report each outcome.
   *
   * One engine failing never stops the others: the whole point of the button is
   * that everything gets refreshed, and a disabled or misconfigured engine
   * should cost only its own row. Failures come back in the result rather than
   * being swallowed, so a caller can say which engines actually ran.
   */
  const scanAll = async (order: readonly ScannableEngine[]): Promise<EngineScanResult[]> => {
    const results: EngineScanResult[] = [];
    const setCurrent = useScanActivity.getState().setCurrent;
    try {
      for (const engine of order) {
        // Say which engine this is before running it. Four of the five publish no
        // progress of their own, so without this the status line has nothing to
        // report while they run and falls back to "AUTO" mid-sweep.
        setCurrent(engine);
        try {
          await runners[engine]();
          results.push({ engine, ok: true });
        } catch (err) {
          results.push({
            engine,
            ok: false,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }
    } finally {
      // In a `finally` so an abandoned sweep cannot leave the status line
      // claiming an engine is still scanning. A stuck "scanning" is worse than
      // no label: it hides the next real one.
      setCurrent(null);
    }
    return results;
  };

  return {
    scanAll,
    isPending: supertrend.isPending || navigator.isPending
      || gammaMove.isPending || adaptiveEdge.isPending,
  };
}

export default useScanAllStrategies;
