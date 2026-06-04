/**
 * CommonSourceBadge — labels which feed a derivatives candidate came from.
 *
 *  • "edge"   → the backtest-validated 4h winner feed (BACKTEST_EDGE_REPORT).
 *  • "engine" → the live scalping / triple-ST strategy engine.
 *
 * Edge rows are display-only by default (auto_execute stays OFF) — the pill
 * lets the operator tell a proven-setup row apart from an engine row at a glance.
 */
import React from 'react';
import { alpha, c } from '../../styles/terminalUI';

export const CommonSourceBadge: React.FC<{ source?: string }> = ({ source }) => {
  const isEdge = source === 'edge';
  const color = isEdge ? c.green : c.dim;
  return (
    <span
      title={isEdge
        ? 'Backtest-validated edge feed (4h winner) — display-only until enabled'
        : 'Live strategy engine feed'}
      style={{
        display: 'inline-block', padding: '1px 5px', borderRadius: 3,
        background: alpha(color, 0.14), border: `1px solid ${alpha(color, 0.4)}`,
        color, fontSize: 8, fontWeight: 800, letterSpacing: '0.08em',
        marginRight: 6, verticalAlign: 'middle',
      }}
    >
      {isEdge ? 'EDGE' : 'ENG'}
    </span>
  );
};

/** Strip feed prefixes for a clean strategy label. */
export const cleanStrategy = (s: string): string =>
  s.replace('scalping/', '').replace('edge/', '').toUpperCase();

/** The engine a derivatives row belongs to. Each dashboard tab is scoped to
 *  exactly one engine so the Grok and Sterling candidate tables never show the
 *  same rows:
 *   • 'sterling' — the live Sterling (scalping) strategy engine ("scalping/…")
 *   • 'grok'     — the Grok / Arbitrator directional engine ("directional")
 *   • 'edge'     — the backtest-validated edge overlay feed ("edge/…")           */
export type EngineId = 'sterling' | 'grok' | 'edge';

/** Classify a candidate row by its strategy slug + source. The strategy slug is
 *  the single source of truth: scalping rows are "scalping/<name>", directional
 *  rows are "directional", edge rows are "edge/<name>" (source === 'edge'). */
export const candidateEngine = (strategy: string, source?: string): EngineId => {
  if (source === 'edge' || strategy.startsWith('edge')) return 'edge';
  if (strategy.startsWith('directional')) return 'grok';
  return 'sterling';
};

/** Classify an executed derivatives position by the strategy slug stamped into
 *  its notes at execute time (auto-exec and manual both tag it). Returns null
 *  for legacy/untagged positions — those are visible in the POSITIONS tab but
 *  are not attributed to either engine's candidate table. */
export const positionEngine = (notes?: string | null): EngineId | null => {
  const n = notes || '';
  if (/edge\//.test(n)) return 'edge';
  if (/\bdirectional\b/.test(n)) return 'grok';
  if (/scalping\//.test(n)) return 'sterling';
  return null;
};

/** Human label for the engine, used in the candidate-table subtitle. */
export const engineLabel = (e?: EngineId): string =>
  e === 'grok' ? 'Grok' : e === 'edge' ? 'Edge' : 'Sterling';
