import React, { useEffect, useMemo, useReducer, useState } from 'react';
import { SterlingKiteEngineWithExpiry } from './SterlingKiteEngineWithExpiry';
import { rowsFromSnapshot } from './AdaptiveEdgePanel';
import { NiftyOrbSignalsFeed } from './NiftyOrbSignalsFeed';
import { AdaptiveEdgeBoard } from './board/AdaptiveEdgeBoard';
import { AtmPremiumImbalanceBoard } from './board/AtmPremiumImbalanceBoard';
import { GammaMoveBoard } from './board/GammaMoveBoard';
import { BearToBearishBoard } from './board/BearToBearishBoard';
import { EngineTabs, type EngineTabState } from './board/EngineToolbar';
import { adaptiveEdgeToBoard } from './board/adaptiveEdgeAdapter';
import { orbToBoard } from './board/orbAdapter';
import { atmPremiumImbalanceToBoard } from './board/atmPremiumImbalanceAdapter';
import { gammaMoveToBoard } from './board/gammaMoveAdapter';
import { bearToBearishToBoard } from './board/bearToBearishAdapter';
import { supertrendToBoard } from './board/supertrendAdapter';
import { ACTIONABLE, type BoardSignal, type EngineId } from './board/boardTypes';
import { useEngineEnabled } from '../../hooks/useEngineToggles';
import { useAdaptiveEdgeSnapshot } from '../../hooks/useAdaptiveEdge';
import { useEngineSignals, useEngineConfig } from '../../hooks/useSterlingKiteEngine';
import { useOrbSignals } from '../../hooks/useOrbSignals';
import { useAtmPremiumImbalanceSnapshot } from '../../hooks/useAtmPremiumImbalance';
import { useGammaMoveSnapshot } from '../../hooks/useGammaMove';
import { useBearToBearishSnapshot, useBearToBearishConfig } from '../../hooks/useBearToBearish';
import { useOrbConfig } from '../../hooks/useOrbConfig';
import { useNavigatorConfig } from '../../hooks/useNavigator';
import { k, Icons } from '../../styles/kiteUI';
import { useKiteSettings } from '../../store/useKiteSettings';
import { PaneHeaderActions } from './PaneHeaderActions';
import { ToolbarButton } from './board/EngineToolbar';
import { ScanProgressRing } from './board/ScanProgressRing';
import { SignalTableSettingsPanel } from './SterlingKiteEnginePane';
import { SCANNABLE_ENGINE_LABEL, useScanAllStrategies, type ScannableEngine } from '../../hooks/useScanAllStrategies';
import { useCancelScan } from '../../hooks/useSterlingKiteEngine';
import { useCancelNavigatorScan } from '../../hooks/useNavigator';

/**
 * The engine workspace: pick an engine, see its board.
 *
 * The picker used to be three flat words. Choosing between them meant opening
 * each one to find out whether it was running and whether it had anything —
 * which is backwards, because the point of a picker is to make that choice
 * without paying for it.
 *
 * Each tab now carries live state: a dot for running / running-but-quiet / off,
 * and a count of what is live. Every tab therefore has to know its engine's
 * state whether or not it is the visible one, which is why the counts are read
 * here rather than inside each board. All three already poll on their own
 * schedule, so this shares their cached data rather than adding requests.
 */
interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number; source?: string }) => void;
  onOpenChart?: (symbol: string, tab: 'chart', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: any) => void;
  /** Opens a board signal as a full detail page in the centre column. */
  onOpenBoardDetail?: (signal: BoardSignal) => void;
}

/** Which engine each nav destination should land on. */
const NAV_TARGET: Record<string, EngineId> = {
  adaptiveEdge: 'adaptive_edge',
  orbOptions: 'orb',
  atmPremiumImbalance: 'atm_premium_imbalance',
  gammaMove: 'gamma_move',
};

export function AdaptiveEdgeRightSidebar({ onSelectSignal, onOpenChart, onOpenBoardDetail }: Props) {
  const [engine, setEngine] = useState<EngineId>('supertrend');
  // The same list the "What is running" section writes to, so a tab cannot
  // survive its engine being switched off — nor vanish for any other reason.
  const engineOn = useEngineEnabled();
  // Every board's Chart column needs this. Four of the five never received it, so
  // `useBoardRowActions` returned null for the chart cell and the column rendered
  // empty — present in the picker, headed "Chart", and permanently blank.
  const openChartFor = React.useCallback(
    (quoteKey: string) => onOpenChart?.(quoteKey, 'chart'),
    [onOpenChart],
  );

  /**
   * Rescan and the board settings, for every engine.
   *
   * They used to be rendered by SuperTrend's pane, which meant they existed on
   * one tab out of five — yet rescan already scans all five, and every setting in
   * that drawer lives in the shared store and governs every board. Two controls
   * common to the whole dock were reachable from a fifth of it.
   */
  const [settingsOpen, setSettingsOpen] = useState(false);
  const rescanStrategies = useKiteSettings((st) => st.rescanStrategies);
  const { scanAll, isPending: scanPending } = useScanAllStrategies();
  const cancelScan = useCancelScan();
  const cancelNavigatorScan = useCancelNavigatorScan();
  // Re-render once a second so the countdown ring actually counts down.
  const [, tickRing] = useReducer((x: number) => x + 1, 0);
  useEffect(() => {
    const id = setInterval(tickRing, 1000);
    return () => clearInterval(id);
  }, []);
  // One clock per render, so every day heading in a paint agrees on "today".
  const nowMs = Date.now();

  const snapshot = useAdaptiveEdgeSnapshot();
  const engineSignals = useEngineSignals();
  const engineConfig = useEngineConfig();
  const orbConfig = useOrbConfig();
  const orbEnabled = orbConfig.data?.config?.enabled;
  // Same path the pane reads: the flag lives under record.config, and absent
  // means off rather than on — an engine nobody has enabled is not running.
  const navigatorEnabled = useNavigatorConfig().data?.record.config.enabled ?? false;
  const orb = useOrbSignals(orbEnabled !== false);
  const apiSnapshot = useAtmPremiumImbalanceSnapshot();
  const gmSnapshot = useGammaMoveSnapshot();
  const btbSnapshot = useBearToBearishSnapshot();
  const btbConfig = useBearToBearishConfig();

  /**
   * The countdown to the next automatic scan, 0..1.
   *
   * This is the only percentage in the vicinity that is real. A scan in FLIGHT is
   * indeterminate — the engine says it is scanning and which instrument it is on,
   * not how far through a known total — so the ring shows motion for that and a
   * number only for this.
   *
   * Market closed means the loop is paused and `next_scan_ms` is stale, so the
   * ring would sit convincingly at 100% forever. Zero instead.
   */
  const sig = engineSignals.data;
  const scanning = sig?.scanning ?? false;
  const countdown = (() => {
    const gen = sig?.generated_ms ?? 0;
    const next = sig?.next_scan_ms ?? 0;
    const interval = next - gen;
    if (!sig?.auto_scan || interval <= 0 || sig?.market_open === false) return 0;
    return Math.min(1, Math.max(0, (Date.now() - gen) / interval));
  })();

  /**
   * Rescan order: the engine you are looking at first.
   *
   * They share one historical-data budget, so they run one at a time — which
   * makes the order the difference between the board in front of you refreshing
   * now or in twenty seconds.
   */
  const scanOrder = useMemo<ScannableEngine[]>(() => {
    const all: ScannableEngine[] = ['supertrend', 'navigator', 'orb', 'gamma_move', 'adaptive_edge', 'bear_to_bearish'];
    const first = all.filter((e) => e === engine);
    return [...first, ...all.filter((e) => e !== engine)];
  }, [engine]);

  /**
   * The engines a press will ACTUALLY scan.
   *
   * Switched-off engines are skipped. Scanning one would be work the operator has
   * explicitly declined, and it would make the button's own tooltip a lie — it
   * names what it will run, including "Navigator is off".
   *
   * Derived once and used by both the title and the press, because those two
   * disagreeing is exactly the bug this replaces: the old button said "Re-scan
   * both engines" whether it scanned one or two.
   */
  const enabledToScan = useMemo<ScannableEngine[]>(() => scanOrder.filter((e) => {
    // The operator's own choice of what this button covers. Absent means
    // included, so the map only holds exclusions and a new engine is in from the
    // day it appears.
    if (rescanStrategies[e] === false) return false;
    // ANDed with whether the engine is RUNNING, never ORed: a switched-off engine
    // is skipped whatever is ticked in settings, because scanning it would be
    // work already declined.
    if (e === 'supertrend') return engineConfig.data?.engine_enabled !== false;
    if (e === 'navigator') return navigatorEnabled;
    if (e === 'orb') return orbEnabled !== false;
    if (e === 'bear_to_bearish') return btbConfig.data?.enabled !== false;
    return true;
  }), [scanOrder, rescanStrategies, engineConfig.data?.engine_enabled, navigatorEnabled, orbEnabled, btbConfig.data]);

  /**
   * Name what the press will actually run, in the order it will run it.
   *
   * A button that scans five engines one at a time, skipping the ones that are
   * switched off, must say so — otherwise a press that scanned three looks
   * identical to a press that scanned five. This moved up from SuperTrend's pane
   * with the button; the ORDER it names changed from lens-first to
   * ACTIVE-TAB-first, because the button now belongs to the whole dock and the
   * board in front of you is the one you want refreshed first.
   *
   * ATM Premium Imbalance stays unlisted: it has no scan, it arms one resolved
   * pair. Naming it would promise something the platform cannot do.
   */
  const scanTitle = (() => {
    if (scanning) return `Scanning ${sig?.scanning_label || '…'}`;
    const names = enabledToScan.map((e) => SCANNABLE_ENGINE_LABEL[e]);
    const off = !navigatorEnabled ? ' · Navigator is off' : '';
    return names.length
      ? `Re-scan ${names.join(', ')}${off}`
      : `Every strategy is switched off${off}`;
  })();

  const tabs: EngineTabState[] = useMemo(() => {
    const st = supertrendToBoard(engineSignals.data?.rows ?? []);
    const ae = snapshot.data ? adaptiveEdgeToBoard(rowsFromSnapshot(snapshot.data)) : [];
    const ob = orb.signals.map(orbToBoard);
    const api = atmPremiumImbalanceToBoard(apiSnapshot.data);
    const gm = gammaMoveToBoard(gmSnapshot.data);
    const btb = bearToBearishToBoard(btbSnapshot.data);
    const live = (list: typeof st) => list.filter((s) => ACTIONABLE.includes(s.status)).length;
    const all: EngineTabState[] = [
      { id: 'supertrend', running: engineConfig.data?.engine_enabled !== false, live: live(st), scanned: st.length },
      { id: 'adaptive_edge', running: !!snapshot.data, live: live(ae), scanned: ae.length },
      { id: 'orb', running: orbEnabled !== false, live: live(ob), scanned: ob.length },
      // "running" here means armed, not merely enabled: this engine does nothing
      // until a session is armed, so an enabled-but-unarmed tab must not claim to
      // be running.
      { id: 'atm_premium_imbalance',
        running: !!apiSnapshot.data?.session && !apiSnapshot.data.session.finished,
        live: live(api), scanned: api.length },
      // Scanning, not armed: this engine is running whenever it is enabled and
      // inside its session, so the tab follows the config rather than a session.
      { id: 'gamma_move',
        running: gmSnapshot.data?.config?.enabled === true,
        live: live(gm), scanned: gm.length },
      { id: 'bear_to_bearish',
        running: btbConfig.data?.enabled !== false,
        live: live(btb), scanned: btb.length },
    // A switched-off engine gets NO TAB now. It used to get one that explained
    // itself, on the reasoning that a missing tab is harder to understand than a
    // stopped one — but that filled the dock with engines the operator had
    // deliberately stopped, and the explanation is in the switch that stopped it.
    //
    // `!== false` and not `=== true`: an engine whose config has not arrived yet
    // keeps its tab. Hiding on "not loaded" would blink every tab out on each
    // page load and look exactly like the operator's own setting.
    ];
    return all.filter((tab) => {
      // The SuperTrend tab HOSTS Navigator — Navigator has no tab of its own, its
      // rows render in this pane under the signal lens. So this tab survives
      // SuperTrend being switched off as long as Navigator is on, or switching
      // SuperTrend off would silently take a running engine's only surface with
      // it. A test caught this: with SuperTrend off, re-scan stopped naming
      // Navigator first, because the dock had moved to another engine entirely.
      if (tab.id === 'supertrend') return engineOn.supertrend || engineOn.navigator;
      return engineOn[tab.id as keyof typeof engineOn] !== false;
    });
  }, [engineSignals.data, engineConfig.data, snapshot.data, orb.signals, orbEnabled,
      apiSnapshot.data, gmSnapshot.data, btbSnapshot.data, btbConfig.data, engineOn]);

  // Switching off the engine you are looking at must move you somewhere real.
  // Without this the dock keeps rendering a board whose tab is gone, which reads
  // as the setting having failed.
  useEffect(() => {
    if (!tabs.length) return;
    if (!tabs.some((tab) => tab.id === engine)) setEngine(tabs[0].id);
  }, [tabs, engine]);

  useEffect(() => {
    const onNav = (event: Event) => {
      const target = NAV_TARGET[(event as CustomEvent<string>).detail];
      if (target) setEngine(target);
    };
    window.addEventListener('kite-nav-click', onNav);
    return () => window.removeEventListener('kite-nav-click', onNav);
  }, []);

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', background: k.bg }}>
      <div style={{ display: 'flex', flexShrink: 0, borderBottom: `1px solid ${k.border}`, background: k.bg }}>
        <EngineTabs tabs={tabs} active={engine} onSelect={setEngine} />

        {/* Portalled into the pane's own title bar. Rendered here rather than by
            any one engine's board, because both controls are common to all of
            them. */}
        <PaneHeaderActions pane="signals">
          {scanning ? (
            <ToolbarButton
              title="Stop scan"
              // Stops every engine a press could have started. Cancelling only
              // SuperTrend left Navigator running with the button showing idle.
              onClick={() => {
                if (engineConfig.data?.engine_enabled !== false) cancelScan.mutate();
                if (navigatorEnabled) cancelNavigatorScan.mutate();
              }}
              disabled={cancelScan.isPending || cancelNavigatorScan.isPending}
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>
            </ToolbarButton>
          ) : (
            <ToolbarButton title={scanTitle} disabled={scanPending} onClick={() => { void scanAll(enabledToScan); }}>
              <ScanProgressRing fraction={countdown} scanning={scanPending} />
            </ToolbarButton>
          )}
          <span data-signal-table-settings style={{ display: 'inline-flex' }}>
            <ToolbarButton title="Board settings" active={settingsOpen} onClick={() => setSettingsOpen((v) => !v)}>
              <Icons.Settings />
            </ToolbarButton>
          </span>
        </PaneHeaderActions>
      </div>

      {settingsOpen && (
        <div style={{ flexShrink: 0, overflow: 'hidden' }}>
          <SignalTableSettingsPanel />
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {engine === 'supertrend' && (
          <SterlingKiteEngineWithExpiry onSelectSignal={onSelectSignal} onOpenChart={onOpenChart} />
        )}
        {engine === 'adaptive_edge' && <AdaptiveEdgeBoard onOpenChart={openChartFor} nowMs={nowMs} onOpenDetail={onOpenBoardDetail} />}
        {engine === 'orb' && <NiftyOrbSignalsFeed onOpenChart={openChartFor} onOpenDetail={onOpenBoardDetail} />}
        {engine === 'atm_premium_imbalance' && (
          <AtmPremiumImbalanceBoard onOpenChart={openChartFor} nowMs={nowMs} onOpenDetail={onOpenBoardDetail} />
        )}
        {engine === 'gamma_move' && (
          <GammaMoveBoard onOpenChart={openChartFor} nowMs={nowMs} onOpenDetail={onOpenBoardDetail} />
        )}
        {engine === 'bear_to_bearish' && (
          <BearToBearishBoard onOpenChart={openChartFor} nowMs={nowMs} onOpenDetail={onOpenBoardDetail} />
        )}
      </div>
    </div>
  );
}
