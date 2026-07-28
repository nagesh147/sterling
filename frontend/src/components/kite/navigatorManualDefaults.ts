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
  /** One short, plain-English sentence — what this actually does, no jargon. Always shown. */
  plainExplain: string;
  /** The precise source line, for anyone who wants to check it. Shown smaller/secondary, never hidden. */
  source: string;
  codeRef: string;
}

export const MANUAL_FIELDS: ManualFieldSpec[] = [
  {
    path: 'flow.mode',
    label: 'Oscillator mode',
    defaultValue: 'dynamic',
    displayDefault: 'Dynamic',
    plainExplain: 'Dynamic watches only the strikes closest to the price — best for day trading. Broad watches more strikes for a slower, big-picture read.',
    source: 'Manual §3.2',
    codeRef: 'chain_sampler.py — picks the sampled strike radius',
  },
  {
    path: 'flow.strong_zone',
    label: 'Strong flow zone',
    defaultValue: 68,
    displayDefault: '68',
    plainExplain: 'Past 68 (or below −68), the option flow reading counts as strongly bullish (or bearish).',
    source: 'Manual §3.1',
    codeRef: 'display reference only — not yet consumed by option_flow.py',
  },
  {
    path: 'flow.extreme_zone',
    label: 'Extreme flow zone',
    defaultValue: 96,
    displayDefault: '96',
    plainExplain: 'Past 96 (or below −96), the move looks very strong — but it\'s also riskier to chase from here.',
    source: 'Manual §3.1',
    codeRef: 'display reference only — not yet consumed by option_flow.py',
  },
  {
    path: 'gamma.require_flow_alignment',
    label: 'Gamma requires flow alignment',
    defaultValue: true,
    displayDefault: 'On',
    plainExplain: 'Gamma activity can never trigger a signal by itself — it only counts when the option flow already agrees with it.',
    source: 'Manual §3.3–3.4',
    codeRef: 'gamma_activity.py:233',
  },
  {
    path: 'fusion.min_avwap_grade',
    label: 'Minimum AVWAP grade to confirm',
    defaultValue: 'A',
    displayDefault: 'A',
    plainExplain: 'Only A or A+ graded setups count as confirmed. B-grade setups still show up, but Navigator won\'t call them confirmed.',
    source: 'Manual §2.5',
    codeRef: 'fusion.py — _grade_meets_min() gates CONFIRMED/HIGH_CONVICTION status',
  },
  {
    path: 'volatility.min_direction_confidence',
    label: 'Minimum directional confidence',
    defaultValue: 60,
    displayDefault: '60',
    plainExplain: 'Below a confidence score of 60, Navigator isn\'t sure enough of the direction to act on it.',
    source: 'Manual §4.2',
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
    note: 'When the market goes quiet (compression), Navigator always says wait — no setting can override this.',
  },
  {
    label: 'Gamma never sets direction by itself',
    note: "Gamma activity can support a signal, but it can never be the only reason one fires.",
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
