// The handful of Navigator settings whose DEFAULT VALUE is taken directly from
// the source document this strategy is built on — the AVWAP Navigator Suite
// (QuantGym), Official Trader's Manual, v1.0 2026 — rather than invented by
// Sterling to make an otherwise-qualitative manual concept computable.
//
// Most of Navigator's ~80 settings (pivot bar counts, ATR periods, grade score
// cutoffs, extension limits, etc.) are STERLING-DESIGNED: the manual describes
// the *behavior* qualitatively (e.g. "signal grades reflect confluence") but
// never discloses its own formula or thresholds (it's a proprietary,
// closed-source indicator suite — see its own "Important Notes" page). Those
// stay ordinary tunable numbers in their existing sections.
//
// This file lists ONLY the fields where the manual gives an actual number or
// an explicit stated preference, verified against Sterling's own code (each
// `codeRef` line is where it's actually consumed) so this list can't silently
// drift from what's true. See docs/superpowers/specs/2026-07-28-navigator-structure-radar-origination-design.md
// for how this was audited.

import type { NavigatorConfigModel } from '../../types/navigator';

export type ManualFieldPath =
  | 'flow.mode'
  | 'flow.strong_zone'
  | 'flow.extreme_zone'
  | 'gamma.require_flow_alignment'
  | 'fusion.min_avwap_grade'
  | 'volatility.min_direction_confidence';

export interface ManualFieldSpec {
  path: ManualFieldPath;
  label: string;
  defaultValue: string | number | boolean;
  displayDefault: string;
  manualQuote: string;
  codeRef: string;
}

export const MANUAL_FIELDS: ManualFieldSpec[] = [
  {
    path: 'flow.mode',
    label: 'Oscillator mode',
    defaultValue: 'dynamic',
    displayDefault: 'Dynamic',
    manualQuote: '"For most intraday traders, Dynamic Analysis is the preferred mode." — §3.2 Two Oscillator Modes',
    codeRef: 'chain_sampler.py — picks the sampled strike radius',
  },
  {
    path: 'flow.strong_zone',
    label: 'Strong flow zone',
    defaultValue: 68,
    displayDefault: '68',
    manualQuote: '"+68 / −68 = Strong bullish/bearish flow" — §3.1 Reference Zones. Shown as a reference band for reading the oscillator, exactly as the manual presents it — not wired to any auto-gate today.',
    codeRef: 'display reference only — not yet consumed by option_flow.py',
  },
  {
    path: 'flow.extreme_zone',
    label: 'Extreme flow zone',
    defaultValue: 96,
    displayDefault: '96',
    manualQuote: '"+96 / −96 = Extreme bullish/bearish flow" — §3.1 Reference Zones. Same as Strong flow zone: a reference band, not an auto-gate.',
    codeRef: 'display reference only — not yet consumed by option_flow.py',
  },
  {
    path: 'gamma.require_flow_alignment',
    label: 'Gamma requires flow alignment',
    defaultValue: true,
    displayDefault: 'On',
    manualQuote: '"Ordinary option-chain bullishness is not enough to trigger a signal. The engine demands flow plus gamma acceleration." — §3.3; a LONG/SHORT Gamma Blast signal requires option-flow AND gamma together — §3.4 Signal Logic. Gamma never determines direction alone.',
    codeRef: 'gamma_activity.py:233',
  },
  {
    path: 'fusion.min_avwap_grade',
    label: 'Minimum AVWAP grade to confirm',
    defaultValue: 'A',
    displayDefault: 'A',
    manualQuote: '"grade A or A+" is the recurring bar in every "Best Conditions" row for P_Buy / P_Sell / Buy / Sell — §2.5 Step 3.',
    codeRef: 'fusion.py — _grade_meets_min() gates CONFIRMED/HIGH_CONVICTION status',
  },
  {
    path: 'volatility.min_direction_confidence',
    label: 'Minimum directional confidence',
    defaultValue: 60,
    displayDefault: '60',
    manualQuote: '"60–80 = Tradable setup" — §4.2 Confidence Score at a Glance. 60 is the manual\'s own floor for a genuinely usable directional read (below it: "Moderate"/"Low conviction, avoid").',
    codeRef: 'volatility.py:360',
  },
];

export const MANUAL_FIELD_MAP: Map<ManualFieldPath, ManualFieldSpec> = new Map(
  MANUAL_FIELDS.map((f) => [f.path, f]),
);

// Behavioral rules the manual states as non-negotiable, already hardcoded in
// the fusion engine — not exposed as a toggle at all, so there's nothing here
// to accidentally change. Listed for visibility only.
export const HARDCODED_MANUAL_RULES: { label: string; note: string }[] = [
  {
    label: 'Compression always forces WAIT',
    note: 'fusion.py — "Compression should force WAIT for trend trades" (§4.1). Not configurable: every decision hits this check before scoring, regardless of any other setting.',
  },
  {
    label: 'Gamma never sets direction by itself',
    note: 'fusion.py — only AVWAP/volatility evidence can ever trigger a decision; gamma only ever contributes a weighted score. Matches the manual\'s framing of Gamma Blast as confirmation, never a standalone signal (§3.3).',
  },
];

export function getManualFieldValue(config: NavigatorConfigModel, path: ManualFieldPath): string | number | boolean {
  const [section, field] = path.split('.') as [keyof NavigatorConfigModel, string];
  return (config[section] as unknown as Record<string, string | number | boolean>)[field];
}

export function resetManualField(config: NavigatorConfigModel, path: ManualFieldPath): NavigatorConfigModel {
  const spec = MANUAL_FIELD_MAP.get(path);
  if (!spec) return config;
  const [section, field] = path.split('.') as [keyof NavigatorConfigModel, string];
  return { ...config, [section]: { ...(config[section] as object), [field]: spec.defaultValue } };
}
