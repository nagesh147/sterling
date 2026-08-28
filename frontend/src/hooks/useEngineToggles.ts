import { useEngineConfig, usePatchEngineConfig } from './useSterlingKiteEngine';
import { useNavigatorConfig, useSetNavigatorConfig } from './useNavigator';
import { useOrbConfig, useSetOrbConfig } from './useOrbConfig';
import { useGammaMoveConfig, useUpdateGammaMove } from './useGammaMove';
import { useAdaptiveEdgeEngineConfig, useSetAdaptiveEdgeEngineConfig } from './useAdaptiveEdge';
import { useAtmPremiumImbalanceConfig, useSetAtmPremiumImbalanceConfig } from './useAtmPremiumImbalance';

/**
 * Every signal engine's running switch, in one place.
 *
 * Two surfaces need to agree about which engines are on: the "What is running"
 * section, where the operator sets it, and the signals dock, which must not show a
 * tab for an engine that is switched off. They were separate before — the panel
 * offered a switch for SuperTrend alone and a "Configure →" link for Navigator,
 * while the dock kept its own per-engine expressions inline — and this repo's
 * recurring bug is exactly that: two lists of engines, one of them stale. The
 * re-scan button and its own tooltip had the same split until a week ago.
 *
 * Each entry owns its engine's quirks so the callers do not have to:
 *
 * - **SuperTrend** keeps `engine_enabled`, not `enabled`, and patches.
 * - **Navigator** writes under optimistic concurrency: the whole config plus the
 *   revision it was read at. That is why it was a link and not a switch — a
 *   toggle needs both, so `toggle` is null until the config has loaded rather
 *   than sending a half-formed body.
 * - the other four take a plain `{ enabled }`.
 */
export type EngineToggleId =
  | 'supertrend' | 'navigator' | 'orb'
  | 'gamma_move' | 'adaptive_edge' | 'atm_premium_imbalance';

export interface EngineToggle {
  id: EngineToggleId;
  label: string;
  /**
   * ON unless the engine says otherwise.
   *
   * A config still in flight reads as enabled on purpose. The dock hides
   * switched-off engines, so treating "not loaded yet" as off would blink every
   * tab out of existence on each page load and, worse, would look exactly like
   * the operator's own setting.
   */
  enabled: boolean;
  /** True while this engine's own write is in flight — not any other's. */
  pending: boolean;
  /** Null while the engine cannot be written yet. Render the switch disabled. */
  toggle: (() => void) | null;
  /** What being on or off actually means for this engine. */
  description: string;
}

/**
 * Just the on/off answers — no mutation handles.
 *
 * Split out because the signals dock only asks "is this engine on?", and pulling
 * the full toggle list in made every test that renders the dock mock six SETTERS
 * it never calls. A read-only consumer holding write handles is also simply
 * wrong: the dock cannot switch an engine off and should not be able to.
 */
export function useEngineEnabled(): Record<EngineToggleId, boolean> {
  const st = useEngineConfig();
  const nav = useNavigatorConfig();
  const orb = useOrbConfig();
  const gm = useGammaMoveConfig();
  const ae = useAdaptiveEdgeEngineConfig();
  const atm = useAtmPremiumImbalanceConfig();

  // `!== false` throughout: absent or still loading counts as ON. See the note on
  // `EngineToggle.enabled` — hiding on "not loaded" looks like the operator's own
  // setting and blinks every dock tab out on each page load.
  return {
    supertrend: st.data?.engine_enabled !== false,
    navigator: nav.data?.record ? !!nav.data.record.config.enabled : true,
    orb: orb.data?.config?.enabled !== false,
    gamma_move: (gm.data?.config as { enabled?: boolean } | undefined)?.enabled !== false,
    adaptive_edge: (ae.data?.config as { enabled?: boolean } | undefined)?.enabled !== false,
    atm_premium_imbalance: atm.data?.config?.enabled !== false,
  };
}

export function useEngineToggles(): EngineToggle[] {
  const on = useEngineEnabled();
  const st = useEngineConfig();
  const stSet = usePatchEngineConfig();

  const nav = useNavigatorConfig();
  const navSet = useSetNavigatorConfig();

  const orb = useOrbConfig();
  const orbSet = useSetOrbConfig();

  const gm = useGammaMoveConfig();
  const gmSet = useUpdateGammaMove();

  const ae = useAdaptiveEdgeEngineConfig();
  const aeSet = useSetAdaptiveEdgeEngineConfig();

  const atm = useAtmPremiumImbalanceConfig();
  const atmSet = useSetAtmPremiumImbalanceConfig();

  const stOn = on.supertrend;
  const navRecord = nav.data?.record;
  const navOn = on.navigator;
  const orbOn = on.orb;
  const gmOn = on.gamma_move;
  const aeOn = on.adaptive_edge;
  const atmOn = on.atm_premium_imbalance;

  return [
    {
      id: 'supertrend',
      label: 'SuperTrend engine',
      enabled: stOn,
      pending: stSet.isPending,
      toggle: st.data ? () => stSet.mutate({ engine_enabled: !stOn }) : null,
      description: stOn
        ? 'Scanning, producing signals, and eligible for automatic execution.'
        : 'Off — no SuperTrend scanning and no SuperTrend signals.',
    },
    {
      id: 'navigator',
      label: 'Value-Flow Navigator',
      enabled: navOn,
      pending: navSet.isPending,
      // The whole config plus the revision it was read at, or nothing.
      toggle: navRecord
        ? () => navSet.mutate({
            config: { ...navRecord.config, enabled: !navOn },
            expected_revision: navRecord.revision,
          })
        : null,
      description: navOn
        ? 'On. It can confirm SuperTrend setups and originate its own.'
        : 'Off — no Navigator evidence and no Navigator-originated setups.',
    },
    {
      id: 'orb',
      label: 'ORB + VWAP',
      enabled: orbOn,
      pending: orbSet.isPending,
      toggle: orb.data ? () => orbSet.mutate({ enabled: !orbOn }) : null,
      description: orbOn
        ? 'Watching the opening range on the index options.'
        : 'Off — the opening range is not tracked and no ORB signals appear.',
    },
    {
      id: 'gamma_move',
      label: 'Gamma Move',
      enabled: gmOn,
      pending: gmSet.isPending,
      toggle: gm.data ? () => gmSet.mutate({ enabled: !gmOn }) : null,
      description: gmOn
        ? 'Watching open-interest unwind around the levels.'
        : 'Off — no OI unwind scanning and no Gamma Move signals.',
    },
    {
      id: 'adaptive_edge',
      label: 'Adaptive Edge',
      enabled: aeOn,
      pending: aeSet.isPending,
      toggle: ae.data ? () => aeSet.mutate({ enabled: !aeOn }) : null,
      description: aeOn
        ? 'Order-flow scalping. Signals only — live execution stays gated.'
        : 'Off — no order-flow scanning and no Adaptive Edge candidates.',
    },
    {
      id: 'atm_premium_imbalance',
      label: 'ATM Premium Imbalance',
      enabled: atmOn,
      pending: atmSet.isPending,
      toggle: atm.data ? () => atmSet.mutate({ enabled: !atmOn }) : null,
      description: atmOn
        ? 'Resolves one ATM pair per session and arms it. It does not sweep a universe.'
        : 'Off — no pair is resolved and no session can be armed.',
    },
  ];
}

export default useEngineToggles;
