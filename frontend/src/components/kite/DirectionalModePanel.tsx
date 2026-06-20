import React from 'react';
import type { EngineConfigModel, Vehicle, DeepItmMoneyness } from '../../types/kiteEngine';

// ─── Vehicle info cards — only vehicles that differ from the default OTM path ─
// otm_options is intentionally excluded: it is identical to directional_mode=OFF
// and showing it as a selectable vehicle would be misleading.

type SelectableVehicle = Exclude<Vehicle, 'otm_options'>;

const VEHICLE_INFO: Record<SelectableVehicle, { label: string; badge: string; badgeColor: string; desc: string; risk: string }> = {
  deep_itm_options: {
    label: 'Deep ITM Options',
    badge: '⚠ Experimental',
    badgeColor: '#ff9800',
    desc: 'Buys calls/puts deep in the money (δ ≈ 0.85–0.95). The option moves nearly 1:1 with Nifty so you capture most of the underlying\'s move — and theta barely touches you. Costs more per lot than OTM, so you get fewer lots for the same capital.',
    risk: 'Still a defined-risk trade — max loss is the premium paid. You\'re buying the index move through an options wrapper rather than futures margin.',
  },
  futures: {
    label: 'Index Futures',
    badge: '⚠ Experimental',
    badgeColor: '#f44336',
    desc: 'Bull signal → buys the future. Bear signal → sells the future short. Delta-1, no IV, no theta — pure price exposure. The stop is in index points (not premium), and the engine sizes lots to keep your risk within budget.',
    risk: 'Losses scale with every point the market moves against you — there is no premium floor. Requires margin (~12–15% of contract value). Only use if you are comfortable with futures and trust the stop discipline.',
  },
};

const ITM_DEPTH_OPTIONS: { value: DeepItmMoneyness; label: string; desc: string }[] = [
  { value: 'ITM5',  label: 'ITM-5',  desc: '5 strikes ITM — δ ≈ 0.75, some theta still present' },
  { value: 'ITM10', label: 'ITM-10', desc: '10 strikes ITM — δ ≈ 0.85, minimal theta bleed' },
  { value: 'ITM15', label: 'ITM-15', desc: '15 strikes ITM — δ ≈ 0.92, near-futures behaviour' },
  { value: 'ITM20', label: 'ITM-20', desc: '20 strikes ITM — δ ≈ 0.96, closest to trading the future outright' },
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
          onClick={() => onUpdate(enabled
            ? { directional_mode: false, vehicle: 'otm_options' }  // reset vehicle when turning off
            : { directional_mode: true, vehicle: cfg.vehicle === 'otm_options' ? 'deep_itm_options' : cfg.vehicle }
          )}
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
            ? 'Standard OTM options are replaced by the vehicle you select below.'
            : 'Signals are traded as standard OTM option buys — CE on bull, PE on bear.'}
        </span>
      </div>

      {!enabled && (
        <div style={{ ...S.hint, marginTop: 4, padding: '6px 10px', background: '#f7f7f7', borderRadius: 3 }}>
          Buy OTM calls/puts. Cheap per lot, but theta decay and IV crush eat into your premium every day — the move needs to happen soon. Max loss is capped at what you paid. Turn ON to trade deep ITM options or futures instead.
        </div>
      )}

      {enabled && (
        <>
          {/* Vehicle selector — only vehicles that differ from the default OTM path */}
          <div style={S.sectionLabel}>VEHICLE</div>
          {(Object.keys(VEHICLE_INFO) as SelectableVehicle[]).map((v) => {
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

          {/* Paper-first warning */}
          <div style={{
            marginTop: 14, padding: '8px 11px', borderRadius: 4,
            background: '#fff3e0', border: '1px solid #ff980055',
            fontSize: 11, color: '#e65100', lineHeight: 1.5,
          }}>
            ⚠ <strong>PAPER-FIRST</strong> — Validate in Paper mode before going live.
          </div>
        </>
      )}

      {/* ── Entry quality filters — apply regardless of vehicle or directional mode ── */}
      <div style={S.divider} />
      <div style={S.sectionLabel}>ENTRY QUALITY FILTERS</div>
      <div style={{ ...S.hint, marginBottom: 8 }}>
        Optional. When set, the engine skips entries where the trend is too weak.
        These apply to all vehicles — OTM options, deep ITM, and futures alike.
      </div>
      <div style={S.filterRow}>
        <span style={S.filterLabel}>
          Min ADX
          <span style={{ ...S.hint, display: 'block' }}>Trend strength. 20+ = decent trend, 30+ = strong.</span>
        </span>
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
        <span style={S.filterLabel}>
          Min ATR %ile
          <span style={{ ...S.hint, display: 'block' }}>Volatility rank vs past year. 50 = above median.</span>
        </span>
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

      {/* ── Risk infrastructure — also applies to all vehicles ── */}
      <div style={S.divider} />
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
        Wires the drawdown circuit breaker and cross-asset correlation penalty into sizing.
        If your account drops 5%/10%/15%, position sizes are scaled down or halted.
        Applies to all vehicles. Recommended once you are trading more than one position at a time.
      </div>
    </div>
  );
}

export default DirectionalModePanel;
