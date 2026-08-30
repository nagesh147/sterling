import { useEngineConfig, usePatchEngineConfig } from './useSterlingKiteEngine';
import { useNavigatorConfig, useSetNavigatorConfig } from './useNavigator';
import { useOrbConfig, useSetOrbConfig } from './useOrbConfig';
import { useGammaMoveConfig, useUpdateGammaMove } from './useGammaMove';
import { useAdaptiveEdgeEngineConfig, useSetAdaptiveEdgeEngineConfig } from './useAdaptiveEdge';
import { useAtmPremiumImbalanceConfig, useSetAtmPremiumImbalanceConfig } from './useAtmPremiumImbalance';
import { useBearToBearishConfig, useUpdateBearToBearishConfig } from './useBearToBearish';
import { useEngineEnabled, type EngineToggleId } from './useEngineToggles';

export type AlgoToggleId = EngineToggleId;

export interface AlgoToggle {
  id: AlgoToggleId;
  label: string;
  enabled: boolean;
  engineEnabled: boolean;
  pending: boolean;
  toggle: (() => void) | null;
  description: string;
}

/**
 * Manually control automatic execution (Algo Trade) per strategy.
 *
 * Each strategy engine carries its own `auto_execute` or `auto_execute_originated`
 * setting. This hook centralizes access and toggling for all 7 strategies,
 * ensuring complete parity with `useEngineToggles`.
 */
export function useAlgoToggles(): AlgoToggle[] {
  const engineOn = useEngineEnabled();

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

  const btb = useBearToBearishConfig();
  const btbSet = useUpdateBearToBearishConfig();

  const stAuto = !!st.data?.auto_execute;
  const navRecord = nav.data?.record;
  const navAuto = !!navRecord?.config.auto_execute_originated;
  const orbAuto = !!orb.data?.config?.auto_execute;
  const gmAuto = !!(gm.data?.config as { auto_execute?: boolean } | undefined)?.auto_execute;
  const aeAuto = !!(ae.data?.config as { auto_execute?: boolean } | undefined)?.auto_execute;
  const atmAuto = !!atm.data?.config?.auto_execute;
  const btbAuto = !!btb.data?.auto_execute;

  return [
    {
      id: 'supertrend',
      label: 'SuperTrend',
      enabled: stAuto,
      engineEnabled: engineOn.supertrend,
      pending: stSet.isPending,
      toggle: st.data ? () => stSet.mutate({ auto_execute: !stAuto }) : null,
      description: stAuto
        ? 'Algo Trade ON — places 1-lot option/futures orders on ready SuperTrend signals.'
        : 'Off — manual order placement only for SuperTrend signals.',
    },
    {
      id: 'navigator',
      label: 'Value-Flow Navigator',
      enabled: navAuto,
      engineEnabled: engineOn.navigator,
      pending: navSet.isPending,
      toggle: navRecord
        ? () => navSet.mutate({
            config: { ...navRecord.config, auto_execute_originated: !navAuto },
            expected_revision: navRecord.revision,
          })
        : null,
      description: navAuto
        ? 'Algo Trade ON — places orders automatically on Navigator-originated setups.'
        : 'Off — manual order placement only for Navigator setups.',
    },
    {
      id: 'orb',
      label: 'ORB + VWAP',
      enabled: orbAuto,
      engineEnabled: engineOn.orb,
      pending: orbSet.isPending,
      toggle: orb.data ? () => orbSet.mutate({ auto_execute: !orbAuto }) : null,
      description: orbAuto
        ? 'Algo Trade ON — places orders automatically on index option breakout signals.'
        : 'Off — manual order placement only for ORB + VWAP setups.',
    },
    {
      id: 'gamma_move',
      label: 'Gamma Move',
      enabled: gmAuto,
      engineEnabled: engineOn.gamma_move,
      pending: gmSet.isPending,
      toggle: gm.data ? () => gmSet.mutate({ auto_execute: !gmAuto }) : null,
      description: gmAuto
        ? 'Algo Trade ON — places orders automatically on open-interest unwind triggers.'
        : 'Off — manual order placement only for Gamma Move setups.',
    },
    {
      id: 'adaptive_edge',
      label: 'Adaptive Edge',
      enabled: aeAuto,
      engineEnabled: engineOn.adaptive_edge,
      pending: aeSet.isPending,
      toggle: ae.data
        ? () => aeSet.mutate({ auto_execute: !aeAuto, auto_execute_futures: !aeAuto, auto_execute_options: !aeAuto })
        : null,
      description: aeAuto
        ? 'Algo Trade ON — places orders automatically on order-flow scalping candidates.'
        : 'Off — manual order placement only for Adaptive Edge candidates.',
    },
    {
      id: 'atm_premium_imbalance',
      label: 'ATM Premium Imbalance',
      enabled: atmAuto,
      engineEnabled: engineOn.atm_premium_imbalance,
      pending: atmSet.isPending,
      toggle: atm.data ? () => atmSet.mutate({ auto_execute: !atmAuto }) : null,
      description: atmAuto
        ? 'Algo Trade ON — places orders automatically when straddle/strangle imbalance triggers.'
        : 'Off — manual order placement only for ATM imbalance setups.',
    },
    {
      id: 'bear_to_bearish',
      label: 'Bear to Bearish',
      enabled: btbAuto,
      engineEnabled: engineOn.bear_to_bearish,
      pending: btbSet.isPending,
      toggle: btb.data ? () => btbSet.mutate({ auto_execute: !btbAuto }) : null,
      description: btbAuto
        ? 'Algo Trade ON — places orders automatically on PCR short momentum & lower high signals.'
        : 'Off — manual order placement only for Bear to Bearish signals.',
    },
  ];
}

export default useAlgoToggles;
