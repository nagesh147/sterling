import React from 'react';
import type { EngineConfigModel, Vehicle, DeepItmMoneyness } from '../../types/kiteEngine';

// ─── Vehicle info cards with plain-English explanations ──────────────────────

const VEHICLE_INFO: Record<Vehicle, { label: string; badge: string; badgeColor: string; desc: string; risk: string }> = {
  otm_options: {
    label: 'OTM Options (Default)',
    badge: '✓ Validated',
    badgeColor: '#4caf50',
    desc: 'Buy out-of-the-money calls/puts. Low cost per lot, but theta decay and IV crush work against you. The existing engine behavior.',
    risk: 'Max loss = premium paid. Theta bleeds ~0.5-2%/day. Edge is consumed by the option wrapper.',
  },
  deep_itm_options: {
    label: 'Deep-ITM Options',
    badge: '⚠ Experimental',
    badgeColor: '#ff9800',
    desc: 'Buy deep-in-the-money options (δ ≈ 0.85–0.95). Moves nearly 1:1 with the underlying, minimal theta bleed, but higher premium = fewer lots.',
    risk: 'Max loss = premium paid (larger than OTM). Reduced theta drag. Better capture of the directional edge.',
  },
  futures: {
    label: 'Index Futures',
    badge: '⚠ Experimental',
    badgeColor: '#f44336',
    desc: 'Trade near-month index futures (δ = 1.0). Full directional exposure with no time decay. Two-sided: can go long or short.',
    risk: 'Notional risk = (entry − stop) × lot_size. No premium decay. Requires margin (≈12-15% of contract). True delta-1 exposure.',
  },
};

const ITM_DEPTH_OPTIONS: { value: DeepItmMoneyness; label: string; desc: string }[] = [
  { value: 'ITM5',  label: 'ITM-5',  desc: '5 strikes in-the-money (~δ0.75)' },
  { value: 'ITM10', label: 'ITM-10', desc: '10 strikes in-the-money (~δ0.85)' },
  { value: 'ITM15', label: 'ITM-15', desc: '15 strikes in-the-money (~δ0.92)' },
  { value: 'ITM20', label: 'ITM-20', desc: '20 strikes in-the-money (~δ0.96)' },
];

// ─── Styles ──────────────────────────────────────────────────────────────────

const S: Record<string, React.CSSProperties> = {
  card: { background: '#fff', border: '1px solid #e0e0e0', borderRadius: 4, padding: 16, marginBottom: 14 },
  title: { color: '#9b9b9b', fontSize: 11, letterSpacing: 1, marginBottom: 12, fontWeight: 700 },
  hint: { color: '#9b9b9b', fontSize: 11, lineHeight: 1.5 },
  row: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 },
  toggle: { width: 36, height: 18, borderRadius: 9, cursor: 'pointer', border: 'none', position: 'relative' as const, transition: 'background 0.2s' },
  toggleDot: { width: 14, height: 14, borderRadius: 7, background: '#fff', position: 'absolute' as const, top: 2, transition: 'left 0.2s', boxShadow: '0 1px 2px rgba(0,0,0,0.2)' },
  vehicleCard: { border: '1px solid #e0e0e0', borderRadius: 4, padding: '10px 12px', cursor: 'pointer', transition: 'all 0.15s', marginBottom: 6 },
  vehicleCardActive: { border: '1px solid #387ed1', background: '#f5f9ff' },
  badge: { fontSize: 9, fontWeight: 700, letterSpacing: 0.5, padding: '2px 6px', borderRadius: 3, color: '#fff', display: 'inline-block', marginLeft: 6 },
  sectionLabel: { fontSize: 10, fontWeight: 700, letterSpacing: 1, color: '#9b9b9b', marginBottom: 6, marginTop: 14 },
  select: { fontSize: 12, padding: '4px 8px', border: '1px solid #ddd', borderRadius: 3, background: '#fff', fontFamily: 'inherit' },
  filterRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 },
  filterLabel: { fontSize: 11, color: '#444' },
  filterInput: { width: 60, fontSize: 11, padding: '3px 6px', border: '1px solid #ddd', borderRadius: 3, textAlign: 'right' as const, fontFamily: 'inherit' },
  divider: { height: 1, background: '#eee', margin: '10px 0' },
};

interface Props {
  cfg: EngineConfigModel;
  onUpdate: (patch: Partial<EngineConfigModel>) => void;
  busy?: boolean;
}

export function DirectionalModePanel({ cfg, onUpdate, busy }: Props) {
  const enabled = cfg.directional_mode;

  return (
    <div style={S.card}>
      <div style={S.title}>DIRECTIONAL MODE</div>

      {/* Master toggle */}
      <div style={S.row}>
        <button
          style={{ ...S.toggle, background: enabled ? '#387ed1' : '#ccc' }}
          onClick={() => onUpdate({ directional_mode: !enabled })}
          disabled={busy}
          title={enabled ? 'Disable directional mode (revert to standard options)' : 'Enable directional mode'}
        >
          <span style={{ ...S.toggleDot, left: enabled ? 20 : 2 }} />
        </button>
        <span style={{ fontSize: 12, fontWeight: 600, color: enabled ? '#387ed1' : '#999' }}>
          {enabled ? 'ON' : 'OFF'}
        </span>
        <span style={S.hint}>
          {enabled
            ? 'Monetize the signal through high-delta instruments.'
            : 'Standard OTM option buying (existing behavior).'}
        </span>
      </div>

      {!enabled && (
        <div style={{ ...S.hint, marginTop: 4, padding: '6px 10px', background: '#f7f7f7', borderRadius: 3 }}>
          When OFF, the engine runs identically to the default — no code path changes.
        </div>
      )}

      {enabled && (
        <>
          {/* Vehicle selector */}
          <div style={S.sectionLabel}>VEHICLE</div>
          {(Object.keys(VEHICLE_INFO) as Vehicle[]).map((v) => {
            const info = VEHICLE_INFO[v];
            const isEnabled = cfg.enabled_vehicles.includes(v);
            const isActive = cfg.vehicle === v;
            return (
              <div
                key={v}
                style={{
                  ...S.vehicleCard,
                  ...(isActive ? S.vehicleCardActive : {}),
                  opacity: isEnabled ? 1 : 0.5,
                }}
                onClick={() => {
                  if (!isEnabled || busy) return;
                  onUpdate({ vehicle: v });
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
                  <input
                    type="checkbox"
                    checked={isEnabled}
                    onChange={(e) => {
                      e.stopPropagation();
                      const next = e.target.checked
                        ? [...cfg.enabled_vehicles, v]
                        : cfg.enabled_vehicles.filter((x) => x !== v);
                      // Must have at least one vehicle enabled
                      if (next.length === 0) return;
                      const patch: Partial<EngineConfigModel> = { enabled_vehicles: next };
                      // If deactivating the current vehicle, switch to another
                      if (!e.target.checked && cfg.vehicle === v) {
                        patch.vehicle = next[0];
                      }
                      onUpdate(patch);
                    }}
                    style={{ marginRight: 6 }}
                    disabled={busy}
                  />
                  <span style={{ fontSize: 12, fontWeight: 600, color: isActive ? '#387ed1' : '#333' }}>
                    {info.label}
                  </span>
                  <span style={{ ...S.badge, background: info.badgeColor }}>{info.badge}</span>
                  {isActive && (
                    <span style={{ ...S.badge, background: '#387ed1', marginLeft: 4 }}>ACTIVE</span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: '#666', lineHeight: 1.4, marginBottom: 4 }}>{info.desc}</div>
                <div style={{ fontSize: 10, color: '#999', lineHeight: 1.4 }}>⚡ {info.risk}</div>
              </div>
            );
          })}

          <div style={S.divider} />

          {/* Deep-ITM config (only visible when deep_itm_options is selected) */}
          {cfg.vehicle === 'deep_itm_options' && (
            <>
              <div style={S.sectionLabel}>DEEP-ITM DEPTH</div>
              <div style={S.filterRow}>
                <span style={S.filterLabel}>Strike depth:</span>
                <select
                  style={S.select}
                  value={cfg.itm_depth || 'ITM10'}
                  onChange={(e) => onUpdate({ itm_depth: e.target.value as DeepItmMoneyness })}
                  disabled={busy}
                >
                  {ITM_DEPTH_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label} — {o.desc}</option>
                  ))}
                </select>
              </div>
              <div style={S.filterRow}>
                <span style={S.filterLabel}>Target delta (override):</span>
                <input
                  type="number"
                  style={S.filterInput}
                  value={cfg.target_delta ?? ''}
                  placeholder="e.g. 0.90"
                  step={0.05}
                  min={0.5}
                  max={0.99}
                  onChange={(e) => {
                    const v = e.target.value ? parseFloat(e.target.value) : null;
                    onUpdate({ target_delta: v });
                  }}
                  disabled={busy}
                />
              </div>
              <div style={{ ...S.hint, marginTop: 2 }}>
                When set, picks the strike with BS delta closest to this value (overrides depth).
              </div>
            </>
          )}

          {/* Futures config */}
          {cfg.vehicle === 'futures' && (
            <>
              <div style={S.sectionLabel}>FUTURES EXPIRY</div>
              <div style={S.filterRow}>
                <span style={S.filterLabel}>Expiry:</span>
                <select
                  style={S.select}
                  value={cfg.futures_expiry}
                  onChange={(e) => onUpdate({ futures_expiry: e.target.value as 'near' | 'next' })}
                  disabled={busy}
                >
                  <option value="near">Near-month (lowest spread)</option>
                  <option value="next">Next-month (more time)</option>
                </select>
              </div>
            </>
          )}

          <div style={S.divider} />

          {/* Entry filters */}
          <div style={S.sectionLabel}>ENTRY QUALITY FILTERS</div>
          <div style={S.hint}>Optional gates — set a minimum to reject weak-trend entries.</div>
          <div style={S.filterRow}>
            <span style={S.filterLabel}>Min ADX:</span>
            <input
              type="number"
              style={S.filterInput}
              value={cfg.adx_min ?? ''}
              placeholder="off"
              step={1}
              min={5}
              max={50}
              onChange={(e) => {
                const v = e.target.value ? parseFloat(e.target.value) : null;
                onUpdate({ adx_min: v });
              }}
              disabled={busy}
            />
          </div>
          <div style={S.filterRow}>
            <span style={S.filterLabel}>Min ATR %ile:</span>
            <input
              type="number"
              style={S.filterInput}
              value={cfg.atr_pct_min ?? ''}
              placeholder="off"
              step={5}
              min={10}
              max={95}
              onChange={(e) => {
                const v = e.target.value ? parseFloat(e.target.value) : null;
                onUpdate({ atr_pct_min: v });
              }}
              disabled={busy}
            />
          </div>

          <div style={S.divider} />

          {/* Risk infra */}
          <div style={S.sectionLabel}>RISK INFRASTRUCTURE</div>
          <div style={S.row}>
            <button
              style={{ ...S.toggle, background: cfg.wire_risk_infra ? '#ff9800' : '#ccc' }}
              onClick={() => onUpdate({ wire_risk_infra: !cfg.wire_risk_infra })}
              disabled={busy}
            >
              <span style={{ ...S.toggleDot, left: cfg.wire_risk_infra ? 20 : 2 }} />
            </button>
            <span style={{ fontSize: 12, fontWeight: 600, color: cfg.wire_risk_infra ? '#ff9800' : '#999' }}>
              {cfg.wire_risk_infra ? 'ON' : 'OFF'}
            </span>
          </div>
          <div style={S.hint}>
            Wires the drawdown circuit breaker (5%/10%/15% thresholds) and cross-asset
            correlation penalty into position sizing. Recommended for multi-position portfolios.
          </div>

          {/* Paper-first warning */}
          <div style={{
            marginTop: 14, padding: '8px 11px', borderRadius: 4,
            background: '#fff3e0', border: '1px solid #ff980055',
            fontSize: 11, color: '#e65100', lineHeight: 1.5,
          }}>
            ⚠ <strong>PAPER-FIRST</strong> — All non-default vehicles must be validated
            in Paper mode before live trading is permitted. New vehicle paths are gated by
            the execution mode toggle above.
          </div>
        </>
      )}
    </div>
  );
}

export default DirectionalModePanel;
