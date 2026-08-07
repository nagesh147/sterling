import type {
  EngineConfigModel, ExitMode, Moneyness, ScanSource, TrailTarget,
} from '../../../types/kiteEngine';

/**
 * ONE description of every Kite trade setting.
 *
 * Before this module the same field was described independently by each surface
 * that rendered it, and the descriptions had already drifted: `scan_source` was
 * "Derivatives" on the SuperTrend page and "Options" on the shared page, and
 * whether changing a field triggered a rescan depended on which panel you
 * happened to click it in (EngineConfigurationPanel defaulted rescan=false,
 * SharedScanSetupPanel defaulted rescan=true) — so `exit_mode` rescanned from
 * the settings page but not from the board header.
 *
 * Rescan policy, label, help text and ownership are properties of the FIELD, so
 * they live here and every surface reads them. That is what keeps the settings
 * page, the board header shortcuts and the signal-table controls in sync: not a
 * convention, but the absence of a second copy.
 */

// ── Sections of the control center ──────────────────────────────────────────
// Exported so the board and other panes can deep-link without duplicating the
// string literals (they used to pass unvalidated bare strings).
export type SectionId =
  | 'account' | 'mode' | 'market' | 'rules'
  | 'engine' | 'navigator' | 'markets' | 'notifications' | 'experience';

/** Where an order came from. The axis the user asked to see settings split by. */
export type Applies = 'manual' | 'auto' | 'both';

/** Which layer genuinely owns a setting — see the design doc's ownership table. */
export type Owner =
  | 'market'      // what gets scanned / which contracts. BOTH engines read these.
  | 'supertrend'  // only exists because the strategy has three SuperTrend lines.
  | 'execution';  // engine-independent: how an order is sized, guarded, protected.

/** Trade lifecycle stage, used to order the Trade Rules page. */
export type Stage =
  | 'universe' | 'discovery' | 'entry' | 'size'
  | 'stop' | 'trail' | 'target' | 'exit' | 'protection' | 'guard';

export interface FieldDef {
  key: keyof EngineConfigModel;
  /** The one name this setting has, on every surface. */
  label: string;
  help: string;
  owner: Owner;
  applies: Applies;
  stage: Stage;
  /** True when changing it makes the current board rows stale. */
  rescan: boolean;
  /** The section whose page holds the editable control. */
  home: SectionId;
  /**
   * Backend evidence for the `applies` tag. Surfaced in the UI as the chip's
   * tooltip so a claim about real-money behaviour is never unsourced.
   */
  evidence: string;
  /**
   * Whether the Value-Flow Navigator actually reads this field too.
   *
   * Not every setting on the Market & Contracts page is shared, and saying so
   * in one blanket sentence was wrong. `strike_moneyness` and the expiry lists
   * are handed to Navigator on every pass; the instrument universe is shared
   * only while Navigator's scan scope is "shared"; and `scan_source` is not
   * shared at all — Navigator carries its own copy of that field.
   */
  navigator?: 'always' | 'when-scope-shared' | 'never';
}

const F = <T extends Record<string, FieldDef>>(defs: T) => defs;

export const FIELDS = F({
  // ── Market & Contracts — read by BOTH engines ─────────────────────────────
  scan_source: {
    key: 'scan_source',
    label: 'Signal source',
    help: 'Which chart a SuperTrend signal is read from. Navigator keeps its own separate setting for this.',
    owner: 'market', applies: 'both', stage: 'discovery', rescan: true, home: 'market',
    evidence: 'service.scan_user builds the spot/premium/confluence universes from it, and service._make_place_cb uses it for the both-mode cross guard.',
    navigator: 'never',
  },
  strike_moneyness: {
    key: 'strike_moneyness',
    label: 'Strike coverage',
    help: 'Which strikes are resolved for each setup. Also decides which contract an automatic BUY hits.',
    owner: 'market', applies: 'both', stage: 'discovery', rescan: true, home: 'market',
    evidence: 'scanner.option_order_args picks the automatic leg from exactly these strikes; navigator/runtime passes the same list when resolving its own legs.',
    navigator: 'always',
  },
  scan_expiries_indices: {
    key: 'scan_expiries_indices',
    label: 'Index expiries',
    help: 'Contract cycles scanned for indices.',
    owner: 'market', applies: 'both', stage: 'discovery', rescan: true, home: 'market',
    evidence: 'Handed to the scanner, and to navigator/runtime on every pass when it resolves legs for its own setups.',
    navigator: 'always',
  },
  scan_indices: {
    key: 'scan_indices',
    label: 'Indices',
    help: 'The indices included in every scan.',
    owner: 'market', applies: 'both', stage: 'universe', rescan: true, home: 'market',
    evidence: 'Applied to both the spot and derivatives scans, and to Navigator when its scan scope is shared.',
    navigator: 'when-scope-shared',
  },
  scan_stocks: {
    key: 'scan_stocks',
    label: 'F&O stocks',
    help: 'The individual stocks included in every scan.',
    owner: 'market', applies: 'both', stage: 'universe', rescan: true, home: 'market',
    evidence: 'Applied to both the spot and derivatives scans, and to Navigator when its scan scope is shared.',
    navigator: 'when-scope-shared',
  },
  scan_all_stocks: {
    key: 'scan_all_stocks',
    label: 'All F&O stocks',
    help: 'Use the full eligible universe instead of a curated list.',
    owner: 'market', applies: 'both', stage: 'universe', rescan: true, home: 'market',
    evidence: 'Same scan boundary as scan_stocks.',
    navigator: 'when-scope-shared',
  },

  // ── SuperTrend strategy mechanics ─────────────────────────────────────────
  trail_target: {
    key: 'trail_target',
    label: 'Trailing style',
    help: 'Which SuperTrend line the stop follows. Tight is the most out-of-sample robust in the 7.5y sweep.',
    owner: 'supertrend', applies: 'both', stage: 'trail', rescan: true, home: 'engine',
    evidence: 'Computes the board plan that protection.plan_for_symbol hands to a hand-placed arm, as well as the automatic one.',
  },
  exit_mode: {
    key: 'exit_mode',
    label: 'Exit confirmation',
    help: 'How many SuperTrend lines must turn red to close a trade. Entry always needs three green lines and a fresh signal.',
    owner: 'supertrend', applies: 'both', stage: 'exit', rescan: true, home: 'engine',
    evidence: 'protection.arm_position freezes it onto the position at arm time, for manual arms too; the monitor reads it from there.',
  },
  exit_aligned_trail: {
    key: 'exit_aligned_trail',
    label: 'Stop anchor',
    help: 'Anchor the stop to the exit counter instead of the tightest line.',
    owner: 'supertrend', applies: 'both', stage: 'trail', rescan: true, home: 'engine',
    evidence: 'Changes the computed stop, so it changes what a manual arm is given.',
  },
  price_stop_exit: {
    key: 'price_stop_exit',
    label: 'Trailing stop closes a trade',
    help: 'On: a trade is closed the first bar price trades through its trail. Off restores the old rule where only the exit counter could close it.',
    owner: 'supertrend', applies: 'both', stage: 'exit', rescan: true, home: 'engine',
    evidence: 'Governs exits.trail_exit_index — the board’s exit_state/exit_reason. The live tick monitor enforces the trail regardless.',
  },

  // ── Trade Rules — engine-independent execution ────────────────────────────
  stop_mode: {
    key: 'stop_mode',
    label: 'Protection mode',
    help: 'Where the protective stop lives: at the broker as a GTT, in the server-side tick monitor, or both.',
    owner: 'execution', applies: 'both', stage: 'stop', rescan: false, home: 'rules',
    evidence: 'service.arm_manual_option_buy passes it to protection.arm_position, exactly as the automatic path does.',
  },
  protect_manual_orders: {
    key: 'protect_manual_orders',
    label: 'Protect orders I place by hand',
    help: 'Arm your own BUY the same way an automatic one is armed, using the stop this board already shows for that contract.',
    owner: 'execution', applies: 'manual', stage: 'protection', rescan: false, home: 'rules',
    evidence: 'service.place_manual_order / arm_manual_option_buy — consulted only on the hand-placed order path.',
  },
  expiry_square_off_days: {
    key: 'expiry_square_off_days',
    label: 'Expiry square-off',
    help: 'Close an option position this many calendar days before expiry. 0 disables it.',
    owner: 'execution', applies: 'both', stage: 'exit', rescan: false, home: 'rules',
    evidence: 'service._square_off_expiring iterates positions.open_positions — every registered position, hand-placed ones included.',
  },
  time_stop_bars: {
    key: 'time_stop_bars',
    label: 'Time stop',
    help: 'Close a position after this many 1H bars held. 0 disables it.',
    owner: 'execution', applies: 'both', stage: 'exit', rescan: false, home: 'rules',
    evidence: 'service._time_stop_positions iterates positions.open_positions — every registered position, hand-placed ones included.',
  },
  risk_sizing: {
    key: 'risk_sizing',
    label: 'Risk-based sizing',
    help: 'Size automatic orders so the premium at risk stays within a set share of available capital.',
    owner: 'execution', applies: 'auto', stage: 'size', rescan: false, home: 'rules',
    evidence: 'service._make_place_cb only — the automatic placement path.',
  },
  risk_pct: {
    key: 'risk_pct',
    label: 'Risk per trade',
    help: 'Percent of available F&O capital risked on one automatic entry.',
    owner: 'execution', applies: 'auto', stage: 'size', rescan: false, home: 'rules',
    evidence: 'service._make_place_cb only — the automatic placement path.',
  },
  max_lots: {
    key: 'max_lots',
    label: 'Maximum lots',
    help: 'Hard ceiling on the lots one automatic order may place.',
    owner: 'execution', applies: 'auto', stage: 'size', rescan: false, home: 'rules',
    evidence: 'service._make_place_cb / sizing.py, inside the automatic placement path only.',
  },
  adx_min: {
    key: 'adx_min',
    label: 'Minimum ADX',
    help: 'Skip an automatic entry when trend strength is below this. Blank disables it.',
    owner: 'execution', applies: 'auto', stage: 'entry', rescan: false, home: 'rules',
    evidence: 'service._make_place_cb skips an automatic entry only. The board still shows ADX on every row.',
  },
  atr_pct_min: {
    key: 'atr_pct_min',
    label: 'Minimum ATR percentile',
    help: 'Skip an automatic entry when volatility is below this percentile. Blank disables it.',
    owner: 'execution', applies: 'auto', stage: 'entry', rescan: false, home: 'rules',
    evidence: 'service._make_place_cb skips an automatic entry only.',
  },
  block_entry_minutes_before_close: {
    key: 'block_entry_minutes_before_close',
    label: 'Late-entry block',
    help: 'Refuse new automatic entries in the last N minutes before 15:30, so a late signal cannot enter straight into an overnight gap. 0 disables it.',
    owner: 'execution', applies: 'auto', stage: 'entry', rescan: false, home: 'rules',
    evidence: 'service._make_place_cb gates the automatic entry only.',
  },
  max_spread_pct: {
    key: 'max_spread_pct',
    label: 'Maximum spread',
    help: 'Skip an automatic entry whose bid-ask spread is wider than this share of mid. Blank disables it.',
    owner: 'execution', applies: 'auto', stage: 'entry', rescan: false, home: 'rules',
    evidence: 'service._make_place_cb makes one quote call at automatic entry.',
  },
  min_oi: {
    key: 'min_oi',
    label: 'Minimum open interest',
    help: 'Skip an automatic entry into a strike thinner than this. Blank disables it.',
    owner: 'execution', applies: 'auto', stage: 'entry', rescan: false, home: 'rules',
    evidence: 'service._make_place_cb makes one quote call at automatic entry.',
  },
  max_daily_loss_pct: {
    key: 'max_daily_loss_pct',
    label: 'Daily loss limit',
    help: 'Halt new automatic entries once the day’s realised losses reach this share of F&O capital. Never force-closes. Blank disables it.',
    owner: 'execution', applies: 'auto', stage: 'guard', rescan: false, home: 'rules',
    evidence: 'service._make_place_cb blocks new automatic entries only. It never force-closes.',
  },
  wire_risk_infra: {
    key: 'wire_risk_infra',
    label: 'Portfolio risk infrastructure',
    help: 'Feed the drawdown circuit breaker and correlation penalty into automatic sizing.',
    owner: 'execution', applies: 'auto', stage: 'guard', rescan: false, home: 'rules',
    evidence: 'service._make_place_cb — consulted during automatic sizing only.',
  },
  directional_mode: {
    key: 'directional_mode',
    label: 'Directional mode',
    help: 'Monetise a signal through a chosen vehicle instead of the default option leg.',
    owner: 'execution', applies: 'auto', stage: 'entry', rescan: false, home: 'rules',
    evidence: 'Selects the contract the engine buys; a manual trader picks their own contract.',
  },
  vehicle: {
    key: 'vehicle',
    label: 'Vehicle',
    help: 'What an automatic order buys: an option leg, a deep in-the-money option, or an index future.',
    owner: 'execution', applies: 'auto', stage: 'entry', rescan: false, home: 'rules',
    evidence: 'Read by the automatic placement callback when choosing the instrument.',
  },
  target_delta: {
    key: 'target_delta',
    label: 'Target delta',
    help: 'Pick the strike nearest this delta. Takes precedence over a fixed depth.',
    owner: 'execution', applies: 'auto', stage: 'entry', rescan: false, home: 'rules',
    evidence: 'Consulted when the automatic path resolves a deep-ITM leg.',
  },
  itm_depth: {
    key: 'itm_depth',
    label: 'In-the-money depth',
    help: 'How many strike steps into the money. Only used when no target delta is set.',
    owner: 'execution', applies: 'auto', stage: 'entry', rescan: false, home: 'rules',
    evidence: 'Only consulted when no target delta is set — a target delta overrides it.',
  },
  futures_expiry: {
    key: 'futures_expiry',
    label: 'Futures contract',
    help: 'Which futures series an automatic order trades.',
    owner: 'execution', applies: 'auto', stage: 'entry', rescan: false, home: 'rules',
    evidence: 'Read by the automatic placement callback when the vehicle is futures.',
  },
});

export type FieldKey = keyof typeof FIELDS;

/** Look a field up without narrowing to a literal key at every call site. */
export function fieldDef(key: FieldKey): FieldDef {
  return FIELDS[key];
}

/** True when changing this field leaves the current board rows stale. */
export function needsRescan(key: FieldKey): boolean {
  return FIELDS[key].rescan;
}

// ── Option sets ─────────────────────────────────────────────────────────────
// Previously each panel declared its own copy, and they had already diverged —
// scan_source was "Derivatives" in one panel and "Options" in another. One copy
// makes that class of drift impossible rather than merely discouraged.

export const SCAN_SOURCE_OPTIONS: Array<{ value: ScanSource; label: string; hint: string }> = [
  {
    value: 'spot', label: 'Spot',
    hint: 'Read the underlying’s own chart. Option strikes are attached as candidates to buy.',
  },
  {
    value: 'derivatives', label: 'Derivatives',
    hint: 'Read each selected contract’s own premium chart, and buy when that premium turns up.',
  },
  {
    value: 'both', label: 'Both',
    hint: 'Run both scans side by side. Every signal is tagged Spot or DERIV.',
  },
  {
    value: 'confluence', label: 'Confluence',
    hint: 'Strictest: emit a strike only when the underlying fires a fresh entry and that option’s own premium confirms it.',
  },
];

export const EXIT_MODE_OPTIONS: Array<{ value: ExitMode; label: string; hint: string }> = [
  { value: 'one_red', label: '1 Red', hint: 'Any one line turns red — tightest, and the measured best over 7.5 years.' },
  { value: 'two_red', label: '2 Red', hint: 'Any two lines turn red.' },
  { value: 'three_red', label: '3 Red', hint: 'All three lines turn red — a full reversal.' },
  { value: 'three_red_signal', label: '3R + Signal', hint: 'All three red and a fresh counter-arrow — loosest.' },
];

export const TRAIL_OPTIONS: Array<{ value: TrailTarget; label: string; hint: string }> = [
  { value: 'fast', label: 'Tight', hint: 'Follow the fast line. Most out-of-sample robust, and bleeds the least theta.' },
  { value: 'mid', label: 'Balanced', hint: 'Follow the middle line.' },
  { value: 'slow', label: 'Loose', hint: 'Follow the slow line — the widest stop.' },
];

export const STOP_MODE_OPTIONS: Array<{ value: EngineConfigModel['stop_mode']; label: string; hint: string }> = [
  { value: 'both', label: 'Both', hint: 'Broker stop and server monitor together. Recommended for real money.' },
  { value: 'broker', label: 'Broker', hint: 'A GTT/SL-M order sits at Zerodha, so it survives this server going down.' },
  { value: 'monitor', label: 'Monitor', hint: 'The server-side tick monitor exits on a trail breach, intrabar.' },
];

export const STRIKE_GROUPS: Array<{ label: string; hint: string; values: Moneyness[] }> = [
  { label: 'Deep ITM', hint: 'δ ≈ 0.80+', values: ['ITM5', 'ITM4'] },
  { label: 'ITM', hint: 'δ ≈ 0.60–0.80', values: ['ITM3', 'ITM2', 'ITM1'] },
  { label: 'ATM', hint: 'δ ≈ 0.50', values: ['ATM'] },
  { label: 'OTM', hint: 'δ ≈ 0.30–0.45', values: ['OTM1', 'OTM2'] },
  { label: 'Far OTM', hint: 'δ ≲ 0.25', values: ['OTM3', 'OTM4', 'OTM5'] },
];

export const INDEX_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'NIFTY 50', label: 'NIFTY' },
  { value: 'NIFTY BANK', label: 'BANKNIFTY' },
  { value: 'NIFTY FIN SERVICE', label: 'FINNIFTY' },
  { value: 'SENSEX', label: 'SENSEX' },
];

/** The label shown for a scan source, from the one canonical list. */
export function scanSourceLabel(source: ScanSource): string {
  return SCAN_SOURCE_OPTIONS.find((option) => option.value === source)?.label ?? source;
}

export function exitModeLabel(mode: ExitMode): string {
  return EXIT_MODE_OPTIONS.find((option) => option.value === mode)?.label ?? mode;
}

// ── Section navigation ──────────────────────────────────────────────────────

const LEGACY_SECTIONS: Record<string, SectionId> = {
  // The rail was reorganised on 2026-08-07; keep old deep links and stored
  // preferences pointing somewhere sensible instead of silently resetting.
  sharedScan: 'market',
  orderSelection: 'rules',
  // Older still: the nested tab bar that preceded the rail.
  strategy: 'engine',
  tools: 'markets',
  settings: 'experience',
};

export const SECTION_IDS: SectionId[] = [
  'account', 'mode', 'market', 'rules', 'engine', 'navigator',
  'markets', 'notifications', 'experience',
];

export function isSectionId(value: unknown): value is SectionId {
  return typeof value === 'string' && (SECTION_IDS as string[]).includes(value);
}

/** Resolve a stored or externally supplied section id, following renames. */
export function resolveSectionId(value: string | null | undefined): SectionId | null {
  if (!value) return null;
  if (isSectionId(value)) return value;
  return LEGACY_SECTIONS[value] ?? null;
}

/**
 * Open a settings section from anywhere in the app.
 *
 * There used to be two incompatible channels: in-pane jumps dispatched
 * `kite-connect-section`, while the signal board wrote localStorage and
 * dispatched `kite-nav-click`. The first was a no-op when the pane was
 * unmounted, the second a no-op when it was already mounted. This does both,
 * and validates the id so a typo cannot persist a bad value.
 */
export function openSettingsSection(section: SectionId): void {
  if (!isSectionId(section)) return;
  try {
    localStorage.setItem('kite_connect_section', section);
  } catch {
    // Private-mode storage failure must not stop navigation.
  }
  window.dispatchEvent(new CustomEvent('kite-connect-section', { detail: section }));
  window.dispatchEvent(new CustomEvent('kite-nav-click', { detail: 'connect' }));
}
