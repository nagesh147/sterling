/**
 * GreeksBudgetHeaderChip — always-visible top-bar chip showing portfolio
 * Greek usage vs caps. Green when every Greek is < 70% of cap, amber at
 * 70-90%, red at > 90% (and blinks). Click to open a drawer with the
 * full per-position breakdown — Phase 4 keeps the popover minimal; the
 * full breakdown drawer is wired by the SETTINGS drawer's RISK section.
 */
import React from 'react';
import { c, alpha } from '../styles/terminalUI';
import { useGreeksBudgetState } from '../hooks/useDerivatives';

const fmtPct = (v: number): string => (v * 100).toFixed(0) + '%';

export const GreeksBudgetHeaderChip: React.FC = () => {
  const { data } = useGreeksBudgetState();
  if (!data) return null;

  const usage = data.usage_pct_of_nav;
  const caps = data.budget;
  // Express each Greek as a fraction of its cap; the chip displays the
  // worst (most-stressed) Greek so the operator sees the binding rail.
  const ratios = {
    delta: caps.max_net_delta > 0 ? Math.abs(usage.delta) / caps.max_net_delta : 0,
    gamma: caps.max_net_gamma > 0 ? Math.abs(usage.gamma) / caps.max_net_gamma : 0,
    vega:  caps.max_net_vega  > 0 ? Math.abs(usage.vega)  / caps.max_net_vega  : 0,
    theta: caps.max_net_theta < 0
      ? Math.max(0, -usage.theta / -caps.max_net_theta)
      : 0,
  };
  const worst = Object.entries(ratios).reduce((m, [k, v]) => (v > m.v ? { k, v } : m), { k: 'delta', v: 0 });

  const color =
    worst.v >= 0.9 ? c.red :
    worst.v >= 0.7 ? c.amber :
    c.green;
  const blink = worst.v >= 1.0;

  return (
    <div
      title={`Δ ${fmtPct(ratios.delta)} · Γ ${fmtPct(ratios.gamma)} · ν ${fmtPct(ratios.vega)} · θ ${fmtPct(ratios.theta)}`}
      style={{
        padding: '2px 10px', borderRadius: 4,
        background: alpha(color, 0.13),
        border: `1px solid ${alpha(color, 0.4)}`,
        fontSize: 10, fontWeight: 800, color,
        letterSpacing: '0.08em', textTransform: 'uppercase',
        fontFamily: 'JetBrains Mono, monospace',
        animation: blink ? 't-blink 0.8s infinite' : undefined,
        whiteSpace: 'nowrap',
      }}>
      Γ-BUD {worst.k.toUpperCase()} {fmtPct(worst.v)}
    </div>
  );
};
